import requests
import sqlite3
import os

# ============================================
# CONFIGURATION
# ============================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# ============================================
# FUNCTIONS
# ============================================

def get_all_market_group_ids():
    """
    Get a list of all market group IDs from ESI.
    No authentication required.
    """
    url = f'{ESI_BASE_URL}/markets/groups/'
    
    print("Fetching list of all market group IDs from ESI...")
    response = requests.get(url)
    
    if response.status_code == 200:
        market_group_ids = response.json()
        print(f"Found {len(market_group_ids)} market group IDs")
        return market_group_ids
    else:
        print(f"Error fetching market group IDs: {response.status_code}")
        return []

def get_market_group_info(market_group_id):
    """
    Get detailed information about a specific market group from ESI.
    """
    url = f'{ESI_BASE_URL}/markets/groups/{market_group_id}/'
    
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching market group {market_group_id}: {response.status_code}")
        return None

def insert_market_group_into_db(conn, market_group_data):
    """
    Insert a single market group into the database.
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO inv_market_groups (
            market_group_id, parent_group_id, market_group_name, 
            description, icon_id, has_types
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        market_group_data['market_group_id'],
        market_group_data.get('parent_group_id'),
        market_group_data['name'],
        market_group_data.get('description'),
        market_group_data.get('icon_id'),
        market_group_data.get('has_types', 0)
    ))

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting inv_market_groups update from ESI")
    print("=" * 50)
    
    # Get all market group IDs
    market_group_ids = get_all_market_group_ids()
    
    if not market_group_ids:
        print("No market group IDs found. Exiting.")
        return
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Loop through each market group
    print("\nFetching and inserting market group data...")
    total = len(market_group_ids)
    
    for index, market_group_id in enumerate(market_group_ids, 1):
        # Show progress every 50 groups
        if index % 50 == 0:
            print(f"Progress: {index}/{total} market groups processed...")
        
        market_group_data = get_market_group_info(market_group_id)
        
        if market_group_data:
            insert_market_group_into_db(conn, market_group_data)
    
    # Save and close
    print("\nSaving changes to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("inv_market_groups update complete!")
    print(f"Total market groups processed: {total}")
    print("=" * 50)

if __name__ == '__main__':
    main()