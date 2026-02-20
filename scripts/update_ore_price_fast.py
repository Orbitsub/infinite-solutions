"""
==========================================
FAST ORE PRICE UPDATE
==========================================
Updates ONLY compressed ore prices from ESI
Much faster than full market update (40-80 seconds vs 10+ minutes)
Run on-demand before checking arbitrage opportunities
==========================================
"""

import requests
import sqlite3
import time
from datetime import datetime, timezone
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

ESI_BASE_URL = 'https://esi.evetech.net/latest'
JITA_REGION = 10000002
JITA_4_4 = 60003760

def get_ore_type_ids(conn):
    """Get list of ore type IDs to update."""
    cursor = conn.cursor()
    
    cursor.execute('SELECT ore_type_id FROM ore_refine_yields')
    
    type_ids = [row[0] for row in cursor.fetchall()]
    
    print(f"[INFO] Found {len(type_ids)} ore types to update")
    
    return type_ids

def fetch_orders_for_type(type_id, max_retries=3):
    """Fetch market orders for a specific type from ESI."""
    url = f'{ESI_BASE_URL}/markets/{JITA_REGION}/orders/'
    
    params = {
        'datasource': 'tranquility',
        'order_type': 'all',
        'type_id': type_id
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # No orders for this item
                return []
            elif response.status_code == 420:
                # Rate limited
                print(f"[WARN] Rate limited, waiting 60 seconds...")
                time.sleep(60)
                continue
            else:
                print(f"[WARN] Status {response.status_code} for type {type_id}")
                return []
                
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[WARN] Error on attempt {attempt + 1}: {e}")
                time.sleep(2)
            else:
                print(f"[ERROR] Failed after {max_retries} attempts: {e}")
                return []
    
    return []

def filter_jita_orders(orders):
    """Filter orders to only Jita 4-4."""
    return [o for o in orders if o.get('location_id') == JITA_4_4]

def get_best_prices(orders):
    """Get best buy and sell prices from orders."""
    if not orders:
        return None, None
    
    buy_orders = [o for o in orders if o.get('is_buy_order', False)]
    sell_orders = [o for o in orders if not o.get('is_buy_order', False)]
    
    best_buy = max([o['price'] for o in buy_orders]) if buy_orders else None
    best_sell = min([o['price'] for o in sell_orders]) if sell_orders else None
    
    return best_buy, best_sell

def update_ore_prices_temp_table(conn, type_id, best_buy, best_sell):
    """Store prices in temporary table."""
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO ore_prices_temp (type_id, best_buy_price, best_sell_price, updated_at)
        VALUES (?, ?, ?, ?)
    ''', (type_id, best_buy, best_sell, datetime.now(timezone.utc).isoformat()))

def main():
    print("=" * 60)
    print("FAST ORE PRICE UPDATE")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create temporary table for prices
        print("\n[1/4] Creating temporary table...")
        cursor.execute('DROP TABLE IF EXISTS ore_prices_temp')
        cursor.execute('''
            CREATE TABLE ore_prices_temp (
                type_id INTEGER PRIMARY KEY,
                best_buy_price REAL,
                best_sell_price REAL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        
        # Get ore type IDs
        print("\n[2/4] Loading ore list...")
        type_ids = get_ore_type_ids(conn)
        
        # Fetch prices from ESI
        print(f"\n[3/4] Fetching prices from ESI ({len(type_ids)} ore types)...")
        print("This will take ~40-80 seconds with rate limiting...\n")
        
        updated = 0
        errors = 0
        
        for i, type_id in enumerate(type_ids, 1):
            # Fetch orders
            orders = fetch_orders_for_type(type_id)
            
            # Filter to Jita 4-4
            jita_orders = filter_jita_orders(orders)
            
            # Get best prices
            best_buy, best_sell = get_best_prices(jita_orders)
            
            # Store in temp table
            update_ore_prices_temp_table(conn, type_id, best_buy, best_sell)
            
            status = "✓" if (best_buy or best_sell) else "○"
            print(f"  [{i:>2}/{len(type_ids)}] {status} Type {type_id}: Buy={best_buy or 'N/A':>8}  Sell={best_sell or 'N/A':>8}")
            
            if best_buy or best_sell:
                updated += 1
            else:
                errors += 1
            
            # Rate limiting (ESI allows ~150 requests per second, but be conservative)
            time.sleep(0.2)  # 5 requests per second
        
        conn.commit()
        
        print(f"\n[4/4] Creating analysis view...")
        
        # Create view that joins temp prices with ore yields
        cursor.execute('DROP VIEW IF EXISTS v_ore_arbitrage_live')
        cursor.execute('''
            CREATE VIEW v_ore_arbitrage_live AS
            SELECT
                ory.ore_type_id,
                ory.ore_name,
                ory.ore_category,
                ory.tritanium_yield,
                ory.pyerite_yield,
                ory.mexallon_yield,
                ory.isogen_yield,
                ory.nocxium_yield,
                ory.zydrine_yield,
                ory.megacyte_yield,
                opt.best_buy_price,
                opt.best_sell_price,
                opt.updated_at
            FROM ore_refine_yields ory
            LEFT JOIN ore_prices_temp opt ON opt.type_id = ory.ore_type_id
        ''')
        
        conn.commit()
        
        # Summary
        print("\n" + "=" * 60)
        print("UPDATE COMPLETE")
        print("=" * 60)
        print(f"Ore types updated: {updated}/{len(type_ids)}")
        print(f"No prices found: {errors}")
        print(f"Finished: {datetime.now().strftime('%H:%M:%S')}")
        print("\nNow run ore_arbitrage_analysis_live.sql to see opportunities!")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    main()