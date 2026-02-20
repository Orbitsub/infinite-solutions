from script_utils import timed_script
import requests
import sqlite3
import os
from datetime import datetime, timezone

# ============================================
# CONFIGURATION
# ============================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Jita 4-4 station ID
JITA_STATION_ID = 60003760
THE_FORGE_REGION_ID = 10000002

# ============================================
# FUNCTIONS
# ============================================

def get_market_orders_for_region(region_id):
    """
    Get all market orders for a region.
    ESI paginates this endpoint - need to fetch all pages.
    """
    all_orders = []
    page = 1
    
    print("\nFetching market orders from ESI...")
    
    while True:
        url = f'{ESI_BASE_URL}/markets/{region_id}/orders/'
        params = {
            'order_type': 'all',
            'page': page
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            orders = response.json()
            
            if not orders:
                break
            
            all_orders.extend(orders)
            
            # Progress indicator every 1000 orders
            if len(all_orders) % 1000 == 0:
                print(f"Progress: {len(all_orders)} orders fetched...")
            
            page += 1
            
        elif response.status_code == 404:
            # End of pages
            break
        else:
            print(f"Error fetching page {page}: {response.status_code}")
            break
    
    print(f"Total orders fetched: {len(all_orders)}")
    return all_orders

def filter_jita_orders(orders, jita_station_id):
    """Filter orders to only include Jita 4-4."""
    jita_orders = [order for order in orders if order['location_id'] == jita_station_id]
    print(f"Filtered to Jita 4-4: {len(jita_orders)} orders")
    return jita_orders

def create_temp_table(conn):
    """
    Create temporary table with same structure as market_orders.
    This allows us to load data without disrupting the live table.
    """
    cursor = conn.cursor()
    
    print("\n>>> Creating temporary staging table...")
    
    # Drop temp table if it exists from a previous failed run
    cursor.execute('DROP TABLE IF EXISTS market_orders_temp')
    
    # Create temp table with exact same structure as market_orders
    cursor.execute('''
        CREATE TABLE market_orders_temp (
            order_id INTEGER PRIMARY KEY,
            region_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            is_buy_order INTEGER NOT NULL,
            price REAL NOT NULL,
            volume_remain INTEGER NOT NULL,
            volume_total INTEGER NOT NULL,
            issued TEXT NOT NULL,
            duration INTEGER NOT NULL,
            range TEXT NOT NULL,
            min_volume INTEGER,
            last_updated TEXT NOT NULL
        )
    ''')
    
    # Create indexes on temp table for better performance during swap
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_temp_market_orders_type_region 
        ON market_orders_temp(type_id, region_id, is_buy_order)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_temp_market_orders_location 
        ON market_orders_temp(location_id)
    ''')
    
    conn.commit()
    print("[OK] Temporary table created with indexes")

def insert_order_into_temp(conn, order, region_id):
    """
    Insert a market order into the TEMPORARY table.
    Production table remains untouched during data loading.
    """
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    cursor.execute('''
        INSERT OR REPLACE INTO market_orders_temp (
            order_id, region_id, type_id, location_id, is_buy_order, price,
            volume_remain, volume_total, issued, duration, range, min_volume, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order['order_id'],
        region_id,
        order['type_id'],
        order['location_id'],
        1 if order['is_buy_order'] else 0,
        order['price'],
        order['volume_remain'],
        order['volume_total'],
        order['issued'],
        order['duration'],
        order.get('range', 'station'),
        order.get('min_volume', 1),
        current_time
    ))

def swap_tables(conn):
    """
    Atomically swap the temporary table with the production table.
    Temporarily drops/recreates views to avoid validation issues.
    """
    cursor = conn.cursor()
    
    print("\n>>> Swapping tables (INSTANTANEOUS)...")
    
    # Save views that depend on market_orders
    print("Saving dependent views...")
    cursor.execute("""
        SELECT name, sql 
        FROM sqlite_master 
        WHERE type = 'view' 
        AND sql LIKE '%market_orders%'
    """)
    views = cursor.fetchall()
    print(f"Found {len(views)} views to temporarily remove")
    
    # Use a transaction to make everything atomic
    cursor.execute('BEGIN IMMEDIATE')
    
    try:
        # Drop dependent views temporarily
        for view_name, _ in views:
            cursor.execute(f'DROP VIEW IF EXISTS {view_name}')
        
        # Swap tables
        cursor.execute('DROP TABLE IF EXISTS market_orders')
        cursor.execute('ALTER TABLE market_orders_temp RENAME TO market_orders')
        
        # Recreate views (with error handling for dependencies)
        failed_views = []
        for view_name, view_sql in views:
            if view_sql:  # Some views might have NULL sql
                try:
                    cursor.execute(view_sql)
                except Exception as view_error:
                    print(f"[WARNING] Could not recreate view {view_name}: {view_error}")
                    failed_views.append(view_name)
        
        # Commit everything
        conn.commit()
        
        print("[OK] Tables swapped and views restored - NEW DATA NOW LIVE!")
        
        if failed_views:
            print(f"[WARNING] {len(failed_views)} views failed to recreate:")
            for view_name in failed_views:
                print(f"  - {view_name}")
            print("[WARNING] Run fix_views.py to repair these views")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] ERROR during table swap: {e}")
        raise

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    """
    Update market orders with zero downtime using temporary table staging.
    Downloads all Jita 4-4 market orders and swaps atomically.
    """
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    
    try:
        # STEP 1: Create temporary table (production stays live)
        create_temp_table(conn)
        
        # STEP 2: Fetch all region orders (production stays live)
        all_orders = get_market_orders_for_region(THE_FORGE_REGION_ID)
        
        if not all_orders:
            print("\n[ERROR] No orders fetched. Exiting without changes.")
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS market_orders_temp')
            conn.commit()
            conn.close()
            return
        
        # STEP 3: Filter to Jita only (production stays live)
        print("\nFiltering for Jita 4-4...")
        jita_orders = filter_jita_orders(all_orders, JITA_STATION_ID)
        
        if not jita_orders:
            print("\n[ERROR] No Jita orders found. Exiting without changes.")
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS market_orders_temp')
            conn.commit()
            conn.close()
            return
        
        # STEP 4: Insert orders into TEMP table (production stays live)
        print("\n>>> Inserting orders into TEMPORARY table...")
        print(">>> Production table remains fully accessible during this time!")
        total = len(jita_orders)
        
        for index, order in enumerate(jita_orders, 1):
            insert_order_into_temp(conn, order, THE_FORGE_REGION_ID)
            
            # Progress indicator every 500 orders
            if index % 500 == 0 or index == total:
                percentage = (index / total) * 100
                print(f"Progress: {index}/{total} orders ({percentage:.1f}%) - Production still live!")
            
            # Commit every 1000 orders to save progress
            if index % 1000 == 0:
                conn.commit()
        
        # Final commit for temp table
        print("\n>>> Finalizing temporary table...")
        conn.commit()
        print(f"[OK] All {len(jita_orders)} orders loaded into temporary table")
        
        # STEP 5: ATOMIC SWAP (happens in milliseconds)
        swap_tables(conn)
        
        conn.close()
        
        # Summary - will be wrapped by @timed_script decorator
        print(f"\nTotal orders now live: {len(jita_orders):,}")
        print("Production table was accessible throughout the entire update!")
        
    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        # Clean up temp table if it exists
        try:
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS market_orders_temp')
            conn.commit()
        except:
            pass
        conn.close()
        raise

if __name__ == '__main__':
    main()