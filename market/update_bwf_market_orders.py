import requests
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / 'scripts'))
sys.path.insert(0, str(PROJECT_DIR / 'config'))

from script_utils import timed_script

# Import token manager
from token_manager import get_token

# ============================================
# CONFIGURATION
# ============================================
DB_PATH = str(PROJECT_DIR / 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'
ESI_VERIFY_URL = 'https://esi.evetech.net/verify/'
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
REQUIRED_SCOPE = 'esi-markets.structure_markets.v1'

# ============================================
# BWF-ZZ KEEPSTAR CONFIGURATION
# ============================================

STRUCTURE_ID = 1051346234914  # BWF-ZZ - BWFour Time WWB ChampZZ
STRUCTURE_NAME = "BWF-ZZ - BWFour Time WWB ChampZZ"

from setup import OPS_REGION_ID as REGION_ID

# ============================================
# AUTHENTICATION
# ============================================

def get_authenticated_headers():
    """Get headers with authentication token from token_manager."""
    try:
        token = get_token()
        print("[OK] Access token obtained")
        return {'Authorization': f'Bearer {token}'}
    except Exception as e:
        print(f"[ERROR] Failed to get access token: {e}")
        return None


def verify_token_scopes(headers):
    """Validate token and print scope diagnostics for structure-market access."""
    try:
        response = requests.get(ESI_VERIFY_URL, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as error:
        print(f"[WARNING] Could not verify token scopes: {error}")
        return

    if response.status_code != 200:
        print(f"[WARNING] ESI /verify returned {response.status_code}: {response.text}")
        return

    payload = response.json()
    scopes_raw = payload.get('Scopes', '')
    scopes = set(scopes_raw.split()) if scopes_raw else set()
    character_name = payload.get('CharacterName', 'Unknown')
    character_id = payload.get('CharacterID', 'Unknown')

    print(f"[OK] Token verified for {character_name} ({character_id})")
    if REQUIRED_SCOPE in scopes:
        print(f"[OK] Required scope present: {REQUIRED_SCOPE}")
    else:
        print(f"[WARNING] Missing required scope: {REQUIRED_SCOPE}")
        if scopes:
            print(f"[WARNING] Current scopes: {' '.join(sorted(scopes))}")
        else:
            print("[WARNING] No scopes reported by ESI verify")


def request_structure_orders_page(headers, page):
    """Fetch a single structure-orders page with retry handling for transient failures."""
    url = f'{ESI_BASE_URL}/markets/structures/{STRUCTURE_ID}/'
    params = {'page': page}
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as error:
            last_error = error
            wait_seconds = attempt * 2
            print(f"[WARNING] Request failed on page {page} (attempt {attempt}/{MAX_RETRIES}): {error}")
            if attempt < MAX_RETRIES:
                print(f"[WARNING] Retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
            continue

        if response.status_code in (420, 502, 503, 504):
            wait_seconds = attempt * 2
            print(
                f"[WARNING] Transient ESI error {response.status_code} on page {page} "
                f"(attempt {attempt}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES:
                print(f"[WARNING] Retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue

        return response

    raise RuntimeError(f"Failed to fetch page {page} after {MAX_RETRIES} attempts: {last_error}")

# ============================================
# FUNCTIONS
# ============================================

def get_structure_market_orders(headers):
    """
    Get market orders using the DIRECT structure endpoint.
    This is the key - using /markets/structures/{id}/ instead of region scan.
    """
    all_orders = []
    page = 1
    
    print(f"\nFetching orders from BWF-ZZ Keepstar (direct endpoint)...")
    
    while True:
        response = request_structure_orders_page(headers, page)
        
        if response.status_code == 200:
            orders = response.json()
            
            if not orders:
                break
            
            all_orders.extend(orders)
            
            if len(all_orders) % 1000 == 0:
                print(f"Progress: {len(all_orders)} orders fetched...")
            
            page += 1
            
        elif response.status_code == 404:
            # End of pages
            break
            
        elif response.status_code == 401:
            print(f"[ERROR] Unauthorized (401) on page {page}")
            print(f"[ERROR] Token may be missing {REQUIRED_SCOPE} or no longer valid")
            return None
            
        elif response.status_code == 403:
            print(f"[ERROR] Access denied (403) on page {page}")
            print("You may not have docking/market access to this structure")
            return None
            
        else:
            print(f"[WARNING] Error on page {page}: {response.status_code}")
            print(response.text[:300])
            return None
    
    return all_orders

def create_temp_table(conn):
    """Create temporary table for BWF-ZZ market orders."""
    cursor = conn.cursor()
    
    cursor.execute('DROP TABLE IF EXISTS bwf_market_orders_temp')
    
    cursor.execute('''
        CREATE TABLE bwf_market_orders_temp (
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
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_temp_bwf_orders_type_region 
        ON bwf_market_orders_temp(type_id, region_id, is_buy_order)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_temp_bwf_orders_location 
        ON bwf_market_orders_temp(location_id)
    ''')
    
    conn.commit()
    print("[OK] Temporary table created")

def insert_order_into_temp(conn, order):
    """Insert order into temporary table."""
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    cursor.execute('''
        INSERT OR REPLACE INTO bwf_market_orders_temp (
            order_id, region_id, type_id, location_id,
            is_buy_order, price, volume_remain, volume_total, 
            issued, duration, range, min_volume, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order['order_id'],
        REGION_ID,
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
    Atomically swap temp table to production.
    Temporarily drops/recreates views to avoid validation issues.
    """
    cursor = conn.cursor()
    
    print("\n>>> Swapping tables (INSTANTANEOUS)...")
    
    # Save views that depend on bwf_market_orders
    print("Saving dependent views...")
    cursor.execute("""
        SELECT name, sql 
        FROM sqlite_master 
        WHERE type = 'view' 
        AND sql LIKE '%bwf_market_orders%'
    """)
    views = cursor.fetchall()
    print(f"Found {len(views)} views to temporarily remove")
    
    cursor.execute('BEGIN IMMEDIATE')
    
    try:
        # Drop dependent views temporarily
        for view_name, _ in views:
            cursor.execute(f'DROP VIEW IF EXISTS {view_name}')
        
        # Swap tables
        cursor.execute('DROP TABLE IF EXISTS bwf_market_orders')
        cursor.execute('ALTER TABLE bwf_market_orders_temp RENAME TO bwf_market_orders')
        
        # Recreate views (with error handling)
        failed_views = []
        for view_name, view_sql in views:
            if view_sql:
                try:
                    cursor.execute(view_sql)
                except Exception as view_error:
                    print(f"[WARNING] Could not recreate view {view_name}: {view_error}")
                    failed_views.append(view_name)
        
        conn.commit()
        print("[OK] Tables swapped and views restored - BWF-ZZ DATA NOW LIVE!")
        
        if failed_views:
            print(f"[WARNING] {len(failed_views)} views failed to recreate:")
            for view_name in failed_views:
                print(f"  - {view_name}")
            print("[WARNING] Run fix_views.py to repair these views")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error during swap: {e}")
        raise

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    """
    Update BWF-ZZ Keepstar market orders with authentication.
    Uses the direct structure market endpoint for accurate data.
    """
    
    print(f"Target: {STRUCTURE_NAME}")
    print(f"Structure ID: {STRUCTURE_ID}")
    print(f"Region: Geminate (ID: {REGION_ID})")
    print(f"Method: Direct structure market endpoint")
    print(f"Authentication: ENABLED")
    
    # Get authentication headers
    headers = get_authenticated_headers()
    
    if headers is None:
        print("\n[ERROR] Cannot proceed without authentication")
        return

    verify_token_scopes(headers)
    
    conn = sqlite3.connect(DB_PATH, timeout=30)
    
    try:
        # Create temp table
        create_temp_table(conn)
        
        # Fetch orders using direct structure endpoint
        orders = get_structure_market_orders(headers)

        if orders is None:
            raise RuntimeError(
                "Unable to fetch structure orders due to authentication/access errors. "
                "Re-authorize token with required scope and confirm structure access."
            )
        
        if not orders:
            print(f"\n[WARNING] No orders found for {STRUCTURE_NAME}")
            print("Market may be empty - verify in-game")
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS bwf_market_orders_temp')
            conn.commit()
            conn.close()
            return
        
        print(f"\n[OK] Found {len(orders):,} orders from {STRUCTURE_NAME}")
        
        # Insert into temp table
        print(f"Inserting orders into temporary table...")
        for i, order in enumerate(orders, 1):
            insert_order_into_temp(conn, order)
            
            if i % 500 == 0 or i == len(orders):
                print(f"  Progress: {i}/{len(orders)} ({i/len(orders)*100:.1f}%)")
        
        conn.commit()
        
        # Swap tables
        swap_tables(conn)
        
        conn.close()
        
        print(f"\nBWF-ZZ Keepstar market data is now live!")
        print(f"Query the 'bwf_market_orders' table to access the data")
        
    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        try:
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS bwf_market_orders_temp')
            conn.commit()
        except:
            pass
        conn.close()
        raise

if __name__ == '__main__':
    main()