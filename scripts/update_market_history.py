from script_utils import timed_script
import requests
import sqlite3
import os
import time
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================
# CONFIGURATION
# ============================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

THE_FORGE_REGION_ID = 10000002
JITA_STATION_ID = 60003760

# Rate limiting: 100 requests per second (conservative)
REQUESTS_PER_SECOND = 100
REQUEST_DELAY = 1.0 / REQUESTS_PER_SECOND

# ============================================
# SETUP SESSION WITH RETRY & POOLING
# ============================================
def create_session():
    """Create a requests session with connection pooling and retries."""
    session = requests.Session()
    
    # Retry on common errors
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504]
    )
    
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,
        pool_maxsize=100
    )
    
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    return session

# ============================================
# FUNCTIONS
# ============================================

def get_jita_traded_type_ids(conn):
    """Get type IDs that currently have active orders in Jita 4-4."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT type_id 
        FROM market_orders 
        WHERE location_id = ?
        AND region_id = ?
        ORDER BY type_id
    ''', (JITA_STATION_ID, THE_FORGE_REGION_ID))
    
    type_ids = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(type_ids)} items with active orders in Jita 4-4")
    return type_ids

def get_already_fetched_today(conn):
    """Get type IDs that already have today's history data."""
    cursor = conn.cursor()
    today = datetime.now().date().isoformat()
    
    cursor.execute('''
        SELECT DISTINCT type_id 
        FROM market_history 
        WHERE region_id = ?
        AND date >= ?
    ''', (THE_FORGE_REGION_ID, today))
    
    fetched = set(row[0] for row in cursor.fetchall())
    print(f"Already have history for {len(fetched)} items today")
    return fetched

def get_market_history(session, region_id, type_id):
    """Get market history for a specific item."""
    url = f'{ESI_BASE_URL}/markets/{region_id}/history/'
    params = {'type_id': type_id}
    
    try:
        response = session.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []
        else:
            return []
    except Exception as e:
        print(f"  Error fetching type {type_id}: {e}")
        return []

def insert_history_into_db(conn, region_id, type_id, history_records):
    """Insert market history records into the database."""
    if not history_records:
        return
    
    cursor = conn.cursor()
    
    for record in history_records:
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

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    print("=" * 60)
    print("MARKET HISTORY UPDATE - Jita 4-4 Items Only")
    print("=" * 60)
    
    start_time = time.time()
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    
    # Create HTTP session with pooling
    session = create_session()
    
    # Get type IDs that have orders in Jita
    print("\nGetting items with active orders in Jita 4-4...")
    all_type_ids = get_jita_traded_type_ids(conn)
    
    # Skip items we already fetched today
    already_fetched = get_already_fetched_today(conn)
    type_ids = [tid for tid in all_type_ids if tid not in already_fetched]
    
    if not type_ids:
        print("\nAll items already have current history data!")
        conn.close()
        return
    
    print(f"\nNeed to fetch history for {len(type_ids)} items")
    print(f"Skipping {len(already_fetched)} items (already current)")
    
    # Estimate time
    estimated_seconds = len(type_ids) * REQUEST_DELAY
    estimated_minutes = estimated_seconds / 60
    print(f"\nEstimated time: {estimated_minutes:.1f} minutes")
    print(f"Rate: {REQUESTS_PER_SECOND} requests/second")
    print("=" * 60)
    
    # Process items
    total = len(type_ids)
    items_with_history = 0
    total_records = 0
    last_progress_time = start_time
    
    for index, type_id in enumerate(type_ids, 1):
        # Get history
        history_records = get_market_history(session, THE_FORGE_REGION_ID, type_id)
        
        if history_records:
            items_with_history += 1
            total_records += len(history_records)
            insert_history_into_db(conn, THE_FORGE_REGION_ID, type_id, history_records)
        
        # Commit every 100 items
        if index % 100 == 0:
            conn.commit()
            
            # Calculate progress stats
            elapsed = time.time() - start_time
            items_per_second = index / elapsed
            remaining_items = total - index
            eta_seconds = remaining_items / items_per_second
            eta_minutes = eta_seconds / 60
            
            print(f"Progress: {index}/{total} ({index/total*100:.1f}%) | "
                  f"{items_with_history} with history | "
                  f"{total_records} records | "
                  f"ETA: {eta_minutes:.1f} min")
        
        # Rate limiting
        time.sleep(REQUEST_DELAY)
    
    # Final commit
    print("\nSaving final changes...")
    conn.commit()
    conn.close()
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("MARKET HISTORY UPDATE COMPLETE")
    print("=" * 60)
    print(f"Items processed: {total}")
    print(f"Items with history: {items_with_history}")
    print(f"Total records: {total_records}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print("=" * 60)

if __name__ == '__main__':
    main()