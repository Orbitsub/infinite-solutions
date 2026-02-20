from script_utils import timed_script
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import requests
import sqlite3
from datetime import datetime, timezone, timedelta
from token_manager import get_token

# ============================================
# CONFIGURATION
# ============================================
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'
GEMINATE_REGION_ID = 10000029  # Geminate region

# ============================================
# FUNCTIONS
# ============================================

def get_bwf_traded_type_ids(conn):
    """
    Get ALL type IDs that are currently traded in BWF-ZZ Keepstar.
    This captures everything for manipulation detection.
    """
    cursor = conn.cursor()
    
    print("Identifying all items traded in BWF-ZZ...")
    
    # Get all unique type_ids from BWF market orders
    cursor.execute('''
        SELECT DISTINCT type_id 
        FROM bwf_market_orders
    ''')
    
    bwf_items = [row[0] for row in cursor.fetchall()]
    
    print(f"Found {len(bwf_items)} unique items in BWF-ZZ market")
    
    return bwf_items

def get_market_history(region_id, type_id):
    """
    Get market history for a specific item in Geminate region.
    """
    url = f'{ESI_BASE_URL}/markets/{region_id}/history/'
    params = {'type_id': type_id}
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []
    else:
        return []

def get_recent_history_only(history_records, days=30):
    """
    Filter history to only keep recent records.
    """
    if not history_records:
        return []
    
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    
    recent = []
    for record in history_records:
        record_date = datetime.fromisoformat(record['date']).date()
        if record_date >= cutoff_date:
            recent.append(record)
    
    return recent

def create_temp_history_table(conn):
    """
    Create temporary table for BWF market history.
    """
    cursor = conn.cursor()
    
    print("\n>>> Creating temporary staging table...")
    
    # Drop temp table if exists
    cursor.execute('DROP TABLE IF EXISTS bwf_market_history_temp')
    
    # Create temp table with same structure as market_history
    cursor.execute('''
        CREATE TABLE bwf_market_history_temp (
            type_id INTEGER NOT NULL,
            region_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            average REAL,
            highest REAL,
            lowest REAL,
            order_count INTEGER,
            volume INTEGER,
            PRIMARY KEY (type_id, region_id, date)
        )
    ''')
    
    conn.commit()
    print("[OK] Temporary table created")

def insert_history_into_temp(conn, region_id, type_id, history_records):
    """
    Insert market history records into TEMPORARY table.
    """
    if not history_records:
        return 0
    
    cursor = conn.cursor()
    inserted = 0
    
    for record in history_records:
        cursor.execute('''
            INSERT OR REPLACE INTO bwf_market_history_temp (
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
    
    return inserted

def merge_history_tables(conn):
    """
    Merge temporary table into production table.
    Creates bwf_market_history table if it doesn't exist.
    """
    cursor = conn.cursor()
    
    # Check if bwf_market_history exists, create if not
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='bwf_market_history'
    """)
    
    if not cursor.fetchone():
        print("\n>>> Creating bwf_market_history table (first run)...")
        cursor.execute('''
            CREATE TABLE bwf_market_history (
                type_id INTEGER NOT NULL,
                region_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                average REAL,
                highest REAL,
                lowest REAL,
                order_count INTEGER,
                volume INTEGER,
                PRIMARY KEY (type_id, region_id, date)
            )
        ''')
        conn.commit()
        print("[OK] bwf_market_history table created")
    
    print("\n>>> Merging new data into production table...")
    print(">>> This uses INSERT OR REPLACE - production stays fully accessible!")
    
    # Get count of records to merge
    cursor.execute('SELECT COUNT(*) FROM bwf_market_history_temp')
    temp_count = cursor.fetchone()[0]
    
    print(f">>> Merging {temp_count:,} records...")
    
    # Merge data
    cursor.execute('''
        INSERT OR REPLACE INTO bwf_market_history 
        SELECT * FROM bwf_market_history_temp
    ''')
    
    conn.commit()
    
    print(f"[OK] Successfully merged {temp_count:,} records into bwf_market_history")
    
    # Clean up temp table
    cursor.execute('DROP TABLE IF EXISTS bwf_market_history_temp')
    conn.commit()
    
    print("[OK] Temporary table cleaned up")

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    """
    Update BWF market history with zero downtime.
    Captures ALL items traded in BWF-ZZ for manipulation detection.
    Downloads 30-day price history for all BWF items.
    """
    # Connect to database
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # STEP 1: Create temporary table
        create_temp_history_table(conn)
        
        # STEP 2: Get all items traded in BWF
        print("\nIdentifying all items in BWF-ZZ market...")
        type_ids = get_bwf_traded_type_ids(conn)
        
        if not type_ids:
            print("No items found in BWF market. Run update_bwf_market_orders first.")
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS bwf_market_history_temp')
            conn.commit()
            conn.close()
            return
        
        # STEP 3: Fetch history for ALL BWF items
        print(f"\n>>> Fetching history for {len(type_ids)} BWF items...")
        print(">>> Loading into TEMPORARY table - production stays live!")
        print("(Only last 30 days)\n")
        
        total = len(type_ids)
        items_processed = 0
        total_records = 0
        
        for index, type_id in enumerate(type_ids, 1):
            if index % 50 == 0:
                print(f"Progress: {index}/{total} items... ({total_records} records) - Production live!")
            
            # Get history from Geminate region
            history_records = get_market_history(GEMINATE_REGION_ID, type_id)
            
            # Filter to only recent history (last 30 days)
            recent_history = get_recent_history_only(history_records, days=30)
            
            if recent_history:
                records_added = insert_history_into_temp(conn, GEMINATE_REGION_ID, type_id, recent_history)
                total_records += records_added
                items_processed += 1
            
            # Commit every 50 items
            if index % 50 == 0:
                conn.commit()
        
        # Final commit to temp table
        print("\n>>> Finalizing temporary table...")
        conn.commit()
        
        # STEP 4: Merge temp into production
        merge_history_tables(conn)
        
        conn.close()
        
        # Summary
        print(f"\nItems processed: {items_processed}/{total}")
        print(f"Records updated: {total_records:,}")
        print("BWF market history table updated - ready for manipulation detection!")
        
    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        # Clean up temp table
        try:
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS bwf_market_history_temp')
            conn.commit()
        except:
            pass
        conn.close()
        raise

if __name__ == '__main__':
    main()