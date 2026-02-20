from script_utils import timed_script
import sys
import os

# Add the scripts directory to Python's path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import requests
import sqlite3
from datetime import datetime, timezone
from token_manager import get_token

# ============================================
# CONFIGURATION
# ============================================
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Your character ID
CHARACTER_ID = 2114278577

# ============================================
# FUNCTIONS
# ============================================

def get_character_orders(character_id, token):
    """
    Get all orders for a character (both active and historical).
    Requires authentication.
    """
    url = f'{ESI_BASE_URL}/characters/{character_id}/orders/'
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"Fetching orders for character {character_id}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        orders = response.json()
        print(f"Found {len(orders)} active orders")
        return orders
    else:
        print(f"Error fetching character orders: {response.status_code}")
        print(f"Response: {response.text}")
        return []

def get_character_orders_history(character_id, token):
    """
    Get historical orders (completed, cancelled, expired) for a character.
    ESI paginates this endpoint.
    """
    all_orders = []
    page = 1
    
    print(f"Fetching order history for character {character_id}...")
    
    while True:
        url = f'{ESI_BASE_URL}/characters/{character_id}/orders/history/'
        headers = {'Authorization': f'Bearer {token}'}
        params = {'page': page}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            orders = response.json()
            
            if not orders:  # Empty page means we're done
                break
            
            all_orders.extend(orders)
            print(f"  Page {page}: fetched {len(orders)} historical orders (total: {len(all_orders)})")
            page += 1
            
        else:
            print(f"Error fetching order history page {page}: {response.status_code}")
            break
    
    return all_orders

def insert_order_into_db(conn, character_id, order, state='active'):
    """
    Insert or update a character order in the database.
    """
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Handle potential missing or differently named fields
    is_buy = order.get('is_buy_order', order.get('is_buy', False))
    
    cursor.execute('''
        INSERT OR REPLACE INTO character_orders (
            order_id, character_id, type_id, region_id, location_id,
            is_buy_order, is_corporation, price, volume_total, volume_remain,
            issued, duration, escrow, min_volume, range, state, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order['order_id'],
        character_id,
        order['type_id'],
        order['region_id'],
        order['location_id'],
        1 if is_buy else 0,
        1 if order.get('is_corporation', False) else 0,
        order['price'],
        order['volume_total'],
        order['volume_remain'],
        order['issued'],
        order['duration'],
        order.get('escrow'),
        order.get('min_volume', 1),
        order['range'],
        order.get('state', state),
        current_time
    ))

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    print("=" * 50)
    print("Starting character_orders update")
    print("=" * 50)
    
    # Get token (will auto-refresh if needed)
    print("\nGetting access token...")
    token = get_token()
    
    # Connect to database
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Get active orders
    print("\nFetching active orders...")
    active_orders = get_character_orders(CHARACTER_ID, token)
    
    if active_orders:
        print(f"Inserting {len(active_orders)} active orders...")
        for order in active_orders:
            insert_order_into_db(conn, CHARACTER_ID, order, state='active')
    
    # Get historical orders
    print("\nFetching historical orders...")
    historical_orders = get_character_orders_history(CHARACTER_ID, token)
    
    if historical_orders:
        print(f"Inserting {len(historical_orders)} historical orders...")
        for order in historical_orders:
            # Historical orders already have a 'state' field
            insert_order_into_db(conn, CHARACTER_ID, order)
    
    # Save and close
    print("\nSaving changes to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("character_orders update complete!")
    print(f"Active orders: {len(active_orders)}")
    print(f"Historical orders: {len(historical_orders)}")
    print("=" * 50)

if __name__ == '__main__':
    main()