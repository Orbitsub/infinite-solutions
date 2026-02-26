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
BACKFILL_DAYS = 30

# ============================================
# FUNCTIONS
# ============================================

def get_items_needing_backfill(conn):
    """Get items marked for backfill."""
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT type_id 
        FROM market_history_tracking 
        WHERE needs_backfill = 1
        ORDER BY type_id
    ''')
    
    return [row[0] for row in cursor.fetchall()]

def get_market_history(region_id, type_id, retry_count=0):
    """Get full market history for an item."""
    url = f'{ESI_BASE_URL}/markets/{region_id}/history/'
    params = {'type_id': type_id}
    
    try:
        time.sleep(REQUEST_DELAY)
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []
        elif response.status_code == 420:
            print(f"\n[WARNING] Rate limited! Waiting 60 seconds...")
            time.sleep(60)
            if retry_count < MAX_RETRIES:
                return get_market_history(region_id, type_id, retry_count + 1)
            return []
        else:
            return []
            
    except (requests.exceptions.ConnectionError, 
            requests.exceptions.Timeout) as e:
        
        if retry_count < MAX_RETRIES:
            wait_time = RETRY_DELAY * (retry_count + 1)
            print(f"\n[WARNING] Connection error, retry {retry_count + 1}/{MAX_RETRIES}")
            time.sleep(wait_time)
            return get_market_history(region_id, type_id, retry_count + 1)
        else:
            print(f"\n[ERROR] Failed after {MAX_RETRIES} retries for type_id {type_id}")
            return []
    
    except Exception as e:
        print(f"\n[ERROR] Unexpected error for type_id {type_id}: {e}")
        return []

def filter_recent_history(history_records, days=30):
    """Keep only last N days of history."""
    if not history_records:
        return []
    
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    
    recent = []
    for record in history_records:
        record_date = datetime.fromisoformat(record['date']).date()
        if record_date >= cutoff_date:
            recent.append(record)
    
    return recent

def insert_history_records(conn, region_id, type_id, history_records):
    """Insert multiple history records."""
    if not history_records:
        return 0
    
    cursor = conn.cursor()
    inserted = 0
    
    for record in history_records:
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
            inserted += 1
        except Exception as e:
            print(f"\n[ERROR] Failed to insert record: {e}")
    
    return inserted

def mark_backfill_complete(conn, type_id):
    """Mark item as backfilled."""
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE market_history_tracking
        SET needs_backfill = 0,
            last_updated_date = date('now')
        WHERE type_id = ?
    ''', (type_id,))

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    """
    Backfill script - loads 30 days of history for new priority items.
    Run this weekly or when new items are detected.
    """
    print("=" * 80)
    print(f"MARKET HISTORY BACKFILL - {BACKFILL_DAYS} DAYS")
    print("=" * 80)
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Get items needing backfill
        items_to_backfill = get_items_needing_backfill(conn)
        
        if not items_to_backfill:
            print("\n[INFO] No items need backfill!")
            print("[INFO] All priority items are up to date.")
            conn.close()
            return
        
        print(f"\n[INFO] Found {len(items_to_backfill)} items needing backfill")
        print(f"[INFO] Loading last {BACKFILL_DAYS} days of history for each")
        print()
        
        total = len(items_to_backfill)
        completed = 0
        total_records = 0
        failed = 0
        
        for index, type_id in enumerate(items_to_backfill, 1):
            if index % 10 == 0:
                print(f"Progress: {index}/{total} items... ({total_records} records loaded)")
            
            # Get full history
            history = get_market_history(THE_FORGE_REGION_ID, type_id)
            
            if history:
                # Filter to last 30 days
                recent = filter_recent_history(history, days=BACKFILL_DAYS)
                
                if recent:
                    records = insert_history_records(conn, THE_FORGE_REGION_ID, type_id, recent)
                    total_records += records
                    
                    # Mark as complete
                    mark_backfill_complete(conn, type_id)
                    completed += 1
                else:
                    # No recent data, but mark as complete anyway
                    mark_backfill_complete(conn, type_id)
                    completed += 1
            else:
                failed += 1
            
            # Commit every 25 items
            if index % 25 == 0:
                conn.commit()
        
        # Final commit
        conn.commit()
        
        # Get item names for summary
        cursor = conn.cursor()
        if completed > 0:
            cursor.execute('''
                SELECT it.type_name
                FROM market_history_tracking mht
                JOIN inv_types it ON it.type_id = mht.type_id
                WHERE mht.needs_backfill = 0
                AND mht.type_id IN ({})
                LIMIT 10
            '''.format(','.join('?' * len(items_to_backfill))), items_to_backfill)
            
            example_items = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        # Summary
        print(f"\n{'=' * 80}")
        print("BACKFILL SUMMARY:")
        print(f"{'=' * 80}")
        print(f"Items backfilled: {completed}/{total}")
        print(f"Records loaded: {total_records:,}")
        print(f"Failed: {failed}")
        
        if completed > 0:
            print(f"\nExample items backfilled:")
            for item in example_items[:5]:
                print(f"  - {item}")
        
        print(f"\n[OK] Backfill complete!")
        print("[INFO] Daily updates will now include these items.")
        
    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        conn.close()
        raise

if __name__ == '__main__':
    main()