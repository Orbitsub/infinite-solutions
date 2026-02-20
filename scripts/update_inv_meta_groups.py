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

def get_all_meta_group_ids():
    """
    Get a list of all dogma attribute IDs that represent meta groups.
    ESI doesn't have a direct meta groups endpoint, so we'll hardcode the known ones.
    Meta groups are relatively static in EVE.
    """
    # Known meta group IDs in EVE Online
    # These correspond to T1, T2, Faction, Deadspace, Officer, etc.
    meta_group_ids = [1, 2, 3, 4, 5, 6, 14, 15, 17, 19, 52, 53]
    print(f"Using {len(meta_group_ids)} known meta group IDs")
    return meta_group_ids

def get_meta_group_info(meta_group_id):
    """
    Get meta group information from dogma attributes endpoint.
    Meta groups in ESI are represented as dogma attributes.
    """
    url = f'{ESI_BASE_URL}/dogma/attributes/{meta_group_id}/'
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        # Transform the attribute data into meta group format
        return {
            'meta_group_id': data['attribute_id'],
            'meta_group_name': data.get('display_name', data.get('name', f'Meta Group {meta_group_id}')),
            'description': data.get('description'),
            'icon_id': data.get('icon_id')
        }
    else:
        print(f"Error fetching meta group {meta_group_id}: {response.status_code}")
        return None

def insert_meta_group_into_db(conn, meta_group_data):
    """
    Insert a single meta group into the database.
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO inv_meta_groups (
            meta_group_id, meta_group_name, description, icon_id
        ) VALUES (?, ?, ?, ?)
    ''', (
        meta_group_data['meta_group_id'],
        meta_group_data['meta_group_name'],
        meta_group_data.get('description'),
        meta_group_data.get('icon_id')
    ))

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting inv_meta_groups update from ESI")
    print("=" * 50)
    
    # Get meta group IDs
    meta_group_ids = get_all_meta_group_ids()
    
    if not meta_group_ids:
        print("No meta group IDs found. Exiting.")
        return
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Loop through each meta group
    print("\nFetching and inserting meta group data...")
    total = len(meta_group_ids)
    
    for index, meta_group_id in enumerate(meta_group_ids, 1):
        print(f"Processing meta group {index}/{total}: ID {meta_group_id}")
        
        meta_group_data = get_meta_group_info(meta_group_id)
        
        if meta_group_data:
            insert_meta_group_into_db(conn, meta_group_data)
    
    # Save and close
    print("\nSaving changes to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("inv_meta_groups update complete!")
    print(f"Total meta groups processed: {total}")
    print("=" * 50)

if __name__ == '__main__':
    main()