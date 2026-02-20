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

def get_all_group_ids():
    """
    Get a list of all group IDs from ESI.
    No authentication required.
    """
    url = f'{ESI_BASE_URL}/universe/groups/'
    
    print("Fetching list of all group IDs from ESI...")
    response = requests.get(url)
    
    if response.status_code == 200:
        group_ids = response.json()
        print(f"Found {len(group_ids)} group IDs")
        return group_ids
    else:
        print(f"Error fetching group IDs: {response.status_code}")
        return []

def get_group_info(group_id):
    """
    Get detailed information about a specific group from ESI.
    """
    url = f'{ESI_BASE_URL}/universe/groups/{group_id}/'
    
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching group {group_id}: {response.status_code}")
        return None

def insert_group_into_db(conn, group_data):
    """
    Insert a single group into the database.
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO inv_groups (
            group_id, category_id, group_name, icon_id, use_base_price,
            anchored, anchorable, fittable_non_singleton, published
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        group_data['group_id'],
        group_data['category_id'],
        group_data['name'],
        group_data.get('icon_id'),
        group_data.get('use_base_price', 0),
        group_data.get('anchored', 0),
        group_data.get('anchorable', 0),
        group_data.get('fittable_non_singleton', 0),
        group_data.get('published', 0)
    ))

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting inv_groups update from ESI")
    print("=" * 50)
    
    # Get all group IDs
    group_ids = get_all_group_ids()
    
    if not group_ids:
        print("No group IDs found. Exiting.")
        return
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Loop through each group
    print("\nFetching and inserting group data...")
    total = len(group_ids)
    
    for index, group_id in enumerate(group_ids, 1):
        # Show progress every 50 groups
        if index % 50 == 0:
            print(f"Progress: {index}/{total} groups processed...")
        
        group_data = get_group_info(group_id)
        
        if group_data:
            insert_group_into_db(conn, group_data)
    
    # Save and close
    print("\nSaving changes to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("inv_groups update complete!")
    print(f"Total groups processed: {total}")
    print("=" * 50)

if __name__ == '__main__':
    main()