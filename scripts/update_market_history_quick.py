from script_utils import timed_script
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import requests
import sqlite3
import time
from datetime import datetime, timezone, timedelta

# ============================================
# CONFIGURATION
# ============================================
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

sys.path.insert(0, os.path.join(PROJECT_DIR, 'config'))
from setup import HOME_REGION_ID as THE_FORGE_REGION_ID

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_DELAY = 0.1

# ============================================
# FUNCTIONS
# ============================================

def setup_tracking_table(conn):
    """Create tracking table if it doesn't exist."""
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_history_tracking (
            type_id INTEGER PRIMARY KEY,
            first_loaded_date TEXT,
            last_updated_date TEXT,
            is_priority INTEGER DEFAULT 1,
            needs_backfill INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()

def get_priority_type_ids(conn):
    """Get current priority items."""
    cursor = conn.cursor()
    
    # Your traded items
    cursor.execute('''
        SELECT DISTINCT type_id 
        FROM character_orders 
        WHERE character_id = 2114278577
    ''')
    your_items = set(row[0] for row in cursor.fetchall())
    
    # Top 500 most traded items
    cursor.execute('''
        SELECT type_id, SUM(volume) as total_volume
        FROM market_history
        WHERE region_id = 10000002
        AND date >= date('now', '-30 days')
        GROUP BY type_id
        ORDER BY total_volume DESC
        LIMIT 500
    ''')
    top_volume_items = set(row[0] for row in cursor.fetchall())
    
    priority_items = your_items.union(top_volume_items)
    
    return list(priority_items), len(your_items), len(top_volume_items)

def identify_new_items(conn, priority_type_ids):
    """Find items not yet in tracking table."""
    cursor = conn.cursor()
    
    # Get items already tracked
    cursor.execute('SELECT type_id FROM market_history_tracking')
    tracked = set(row[0] for row in cursor.fetchall())
    
    # Find new items
    new_items = [tid for tid in priority_type_ids if tid not in tracked]
    
    if new_items:
        print(f"\n[INFO] Found {len(new_items)} NEW priority items")
        print("[INFO] These will be marked for backfill (30-day load)")
        
        # Add to tracking with backfill flag
        for type_id in new_items:
            cursor.execute('''
                INSERT INTO market_history_tracking 
                (type_id, first_loaded_date, needs_backfill)
                VALUES (?, ?, 1)
            ''', (type_id, datetime.now(timezone.utc).date().isoformat()))
        
        conn.commit()
    
    return new_items

def get_market_history_for_date(region_id, type_id, target_date, retry_count=0):
    """
    Get market history for specific item.
    ESI returns ALL history, we filter to target date.
    """
    url = f'{ESI_BASE_URL}/markets/{region_id}/history/'
    params = {'type_id': type_id}
    
    try:
        time.sleep(REQUEST_DELAY)
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            all_history = response.json()
            # Filter to just the target date
            for record in all_history:
                if record['date'] == target_date:
                    return record
            return None  # No data for that date
            
        elif response.status_code == 404:
            return None
        elif response.status_code == 420:
            print(f"\n[WARNING] Rate limited! Waiting 60 seconds...")
            time.sleep(60)
            if retry_count < MAX_RETRIES:
                return get_market_history_for_date(region_id, type_id, target_date, retry_count + 1)
            return None
        else:
            return None
            
    except (requests.exceptions.ConnectionError, 
            requests.exceptions.Timeout) as e:
        
        if retry_count < MAX_RETRIES:
            wait_time = RETRY_DELAY * (retry_count + 1)
            print(f"\n[WARNING] Connection error for type_id {type_id}, retry {retry_count + 1}/{MAX_RETRIES}")
            time.sleep(wait_time)
            return get_market_history_for_date(region_id, type_id, target_date, retry_count + 1)
        else:
            return None
    
    except Exception as e:
        print(f"\n[ERROR] Unexpected error for type_id {type_id}: {e}")
        return None

def insert_history_record(conn, region_id, type_id, record):
    """Insert single history record."""
    if not record:
        return False
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO market_history (
                type_id, region_id, date, average, highest, lowest, order_count, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            type_id,
            region_id,
            record['date'],
            record.get('average'),
            record.get('highest'),
            record.get('lowest'),
            record.get('order_count'),
            record.get('volume')
        ))
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to insert record for type_id {type_id}: {e}")
        return False

def update_tracking(conn, type_id, date):
    """Update tracking table with latest update."""
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE market_history_tracking
        SET last_updated_date = ?
        WHERE type_id = ?
    ''', (date, type_id))

def cleanup_old_history(conn, days=30):
    """Delete history older than X days. Very fast - takes <1 second."""
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    
    print(f"\n>>> Cleaning up history older than {cutoff_date}...")
    
    cursor.execute('''
        DELETE FROM market_history
        WHERE date < ?
    ''', (cutoff_date,))
    
    deleted = cursor.rowcount
    conn.commit()
    
    print(f"[OK] Deleted {deleted:,} old records")
    
    return deleted

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    """
    Fast daily update - only downloads yesterday's data.
    New priority items are marked for backfill (run separate script).
    """
    print("=" * 80)
    print("DAILY MARKET HISTORY UPDATE")
    print("=" * 80)
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Setup tracking table
        setup_tracking_table(conn)
        
        # Get yesterday's date (the data we're fetching)
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        target_date = yesterday.isoformat()
        
        print(f"\nTarget date: {target_date}")
        
        # Get priority items
        print("\nIdentifying priority items...")
        priority_type_ids, your_count, top_count = get_priority_type_ids(conn)
        
        print(f"Your traded items: {your_count}")
        print(f"Top volume items: {top_count}")
        print(f"Total priority items: {len(priority_type_ids)}")
        
        # Check for new items (need backfill)
        new_items = identify_new_items(conn, priority_type_ids)
        
        # Get items that need daily update (not flagged for backfill)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT type_id 
            FROM market_history_tracking 
            WHERE needs_backfill = 0
            AND type_id IN ({})
        '''.format(','.join('?' * len(priority_type_ids))), priority_type_ids)
        
        items_to_update = [row[0] for row in cursor.fetchall()]
        
        print(f"\n>>> Updating {len(items_to_update)} items for {target_date}")
        if new_items:
            print(f">>> Skipping {len(new_items)} new items (run backfill script)")
        print()
        
        total = len(items_to_update)
        updated = 0
        failed = 0
        no_data = 0
        
        for index, type_id in enumerate(items_to_update, 1):
            if index % 50 == 0:
                print(f"Progress: {index}/{total} items... ({updated} updated, {no_data} no data, {failed} failed)")
            
            # Get yesterday's data only
            record = get_market_history_for_date(THE_FORGE_REGION_ID, type_id, target_date)
            
            if record:
                if insert_history_record(conn, THE_FORGE_REGION_ID, type_id, record):
                    update_tracking(conn, type_id, target_date)
                    updated += 1
                else:
                    failed += 1
            else:
                no_data += 1  # Item didn't trade yesterday
            
            # Commit every 100 items
            if index % 100 == 0:
                conn.commit()
        
        # Final commit
        conn.commit()
        
        # Cleanup old data (very fast - typically <1 second)
        deleted = cleanup_old_history(conn, days=30)
        
        conn.close()
        
        # Summary
        print(f"\n{'=' * 80}")
        print("SUMMARY:")
        print(f"{'=' * 80}")
        print(f"Items updated: {updated}/{total}")
        print(f"Items with no data: {no_data} (didn't trade yesterday)")
        print(f"Failed: {failed}")
        print(f"Old records deleted: {deleted:,}")
        
        if new_items:
            print(f"\n[ACTION REQUIRED] {len(new_items)} new items need backfill")
            print("Run: python update_market_history_backfill.py")
        
        print(f"\nNext run: Tomorrow for {(datetime.now(timezone.utc).date()).isoformat()}")
        
    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        conn.close()
        raise

if __name__ == '__main__':
    main()