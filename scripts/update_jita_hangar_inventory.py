"""
Update Jita Hangar Inventory
Fetches items from your Jita hangar and stores them in the database
"""
from script_utils import timed_script
import requests
import sqlite3
import os
import sys
from datetime import datetime, timezone

# Add scripts directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# Import token manager
from token_manager import get_token

# ============================================
# CONFIGURATION
# ============================================
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Your character ID
CHARACTER_ID = 2114278577

# Jita 4-4 station ID
JITA_STATION_ID = 60003760

# ============================================
# FUNCTIONS
# ============================================

def get_authenticated_headers():
    """Get headers with authentication token."""
    try:
        token = get_token()
        return {'Authorization': f'Bearer {token}'}
    except Exception as e:
        print(f"[ERROR] Failed to get access token: {e}")
        return None

def get_character_assets(headers):
    """Get all character assets from ESI."""
    all_assets = []
    page = 1
    
    print("Fetching character assets from ESI...")
    
    while True:
        url = f'{ESI_BASE_URL}/characters/{CHARACTER_ID}/assets/'
        params = {'page': page}
        
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            assets = response.json()
            
            if not assets:
                break
            
            all_assets.extend(assets)
            page += 1
            
        elif response.status_code == 404:
            break
        else:
            print(f"Error fetching assets page {page}: {response.status_code}")
            break
    
    print(f"Total assets fetched: {len(all_assets)}")
    return all_assets

def filter_jita_hangar(assets):
    """Filter assets to only Jita 4-4 station hangar."""
    jita_items = [
        asset for asset in assets 
        if asset.get('location_id') == JITA_STATION_ID
        and asset.get('location_flag') == 'Hangar'
    ]
    
    print(f"Filtered to Jita 4-4 hangar: {len(jita_items)} items")
    return jita_items

def create_hangar_table(conn):
    """Create or recreate the jita_hangar_inventory table."""
    cursor = conn.cursor()
    
    print("\n>>> Creating hangar inventory table...")
    
    # Drop and recreate table
    cursor.execute('DROP TABLE IF EXISTS jita_hangar_inventory')
    
    cursor.execute('''
        CREATE TABLE jita_hangar_inventory (
            item_id INTEGER PRIMARY KEY,
            type_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            location_flag TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            is_singleton INTEGER NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')
    
    # Create index on type_id for faster joins
    cursor.execute('''
        CREATE INDEX idx_hangar_type_id 
        ON jita_hangar_inventory(type_id)
    ''')
    
    conn.commit()
    print("[OK] Hangar inventory table created")

def insert_hangar_items(conn, items):
    """Insert hangar items into database."""
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    print(f"\n>>> Inserting {len(items)} items into database...")
    
    for item in items:
        cursor.execute('''
            INSERT INTO jita_hangar_inventory (
                item_id, type_id, location_id, location_flag,
                quantity, is_singleton, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            item['item_id'],
            item['type_id'],
            item['location_id'],
            item['location_flag'],
            item.get('quantity', 1),
            1 if item['is_singleton'] else 0,
            current_time
        ))
    
    conn.commit()
    print("[OK] All items inserted")

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    """
    Update Jita hangar inventory from ESI.
    Creates a table you can join against in your queries.
    """
    
    print("Fetching Jita 4-4 hangar inventory...")
    print(f"Character ID: {CHARACTER_ID}")
    print(f"Station: Jita 4-4 ({JITA_STATION_ID})")
    
    # Get authentication
    headers = get_authenticated_headers()
    if headers is None:
        print("\n[ERROR] Cannot proceed without authentication")
        return
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Fetch all character assets
        all_assets = get_character_assets(headers)
        
        if not all_assets:
            print("\n[WARNING] No assets found")
            conn.close()
            return
        
        # Filter to Jita hangar only
        jita_items = filter_jita_hangar(all_assets)
        
        if not jita_items:
            print("\n[WARNING] No items found in Jita 4-4 hangar")
            conn.close()
            return
        
        # Create table
        create_hangar_table(conn)
        
        # Insert items
        insert_hangar_items(conn, jita_items)
        
        # Show summary
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT type_id) as unique_types,
                SUM(quantity) as total_items
            FROM jita_hangar_inventory
        ''')
        unique_types, total_items = cursor.fetchone()
        
        print("\n" + "=" * 50)
        print("JITA HANGAR INVENTORY SUMMARY")
        print("=" * 50)
        print(f"Unique item types: {unique_types:,}")
        print(f"Total items: {total_items:,}")
        print("=" * 50)
        
        conn.close()
        
        print("\n✅ Hangar inventory updated!")
        print("💡 Use this in your query:")
        print("   WHERE pt.type_id IN (SELECT type_id FROM jita_hangar_inventory)")
        
    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        conn.close()
        raise

if __name__ == '__main__':
    main()