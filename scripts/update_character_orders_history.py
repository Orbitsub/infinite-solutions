from script_utils import timed_script
import requests
import sqlite3
import time
from datetime import datetime

DB_PATH = r'E:\Python Project\mydatabase.db'
ESI_BASE_URL = 'https://esi.evetech.net/latest'

def get_character_token():
    """Get valid access token for character."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT access_token, refresh_token, expires_at 
        FROM auth_tokens 
        WHERE character_id = 2114278577
        ORDER BY expires_at DESC 
        LIMIT 1
    ''')
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise Exception("No auth token found")
    
    access_token, refresh_token, expires_at = result
    expires_dt = datetime.fromisoformat(expires_at)
    
    if datetime.now() >= expires_dt:
        print("Token expired, needs refresh")
        raise Exception("Token expired - run token refresh script")
    
    return access_token

def save_orders_snapshot():
    """Save a snapshot of current orders to history table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create history table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS character_orders_history (
            snapshot_date TEXT NOT NULL,
            order_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            region_id INTEGER NOT NULL,
            is_buy_order INTEGER NOT NULL,
            price REAL NOT NULL,
            volume_remain INTEGER NOT NULL,
            volume_total INTEGER NOT NULL,
            issued TEXT NOT NULL,
            state TEXT NOT NULL,
            PRIMARY KEY (snapshot_date, order_id)
        )
    ''')
    
    # Copy current orders to history
    snapshot_time = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT OR IGNORE INTO character_orders_history
        SELECT 
            ? as snapshot_date,
            order_id,
            character_id,
            type_id,
            location_id,
            region_id,
            is_buy_order,
            price,
            volume_remain,
            volume_total,
            issued,
            state,
            last_updated
        FROM character_orders
        WHERE character_id = 2114278577
    ''', (snapshot_time,))
    
    rows_added = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"Saved snapshot of orders at {snapshot_time}")
    print(f"Added {rows_added} order records to history")
    
    return rows_added

@timed_script
def main():
    print("=" * 60)
    print("CHARACTER ORDERS HISTORY SNAPSHOT")
    print("=" * 60)
    
    try:
        save_orders_snapshot()
        print("\nSnapshot saved successfully!")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == '__main__':
    main()