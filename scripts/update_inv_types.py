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

def get_all_type_ids():
    """
    Get a list of all type IDs from ESI.
    This endpoint is paginated, so we need to fetch all pages.
    """
    all_type_ids = []
    page = 1
    
    print("Fetching list of all type IDs from ESI...")
    
    while True:
        url = f'{ESI_BASE_URL}/universe/types/'
        params = {'page': page}
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            type_ids = response.json()
            
            if not type_ids:  # Empty page means we're done
                break
            
            all_type_ids.extend(type_ids)
            print(f"  Page {page}: fetched {len(type_ids)} type IDs (total so far: {len(all_type_ids)})")
            page += 1
            
        else:
            print(f"Error fetching type IDs page {page}: {response.status_code}")
            break
    
    print(f"\nTotal type IDs found: {len(all_type_ids)}")
    return all_type_ids

def get_type_info(type_id):
    """
    Get detailed information about a specific type from ESI.
    This endpoint doesn't require authentication.
    Returns a dictionary with type information.
    """
    url = f'{ESI_BASE_URL}/universe/types/{type_id}/'
    
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        # Don't print error for every failed type - some are expected
        return None

def insert_type_into_db(conn, type_data):
    """
    Insert a single type into the database.
    Uses INSERT OR REPLACE to handle updates if type already exists.
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO inv_types (
            type_id, group_id, type_name, description, mass, volume,
            capacity, portion_size, race_id, base_price, published,
            market_group_id, icon_id, sound_id, graphic_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        type_data['type_id'],
        type_data.get('group_id'),
        type_data['name'],
        type_data.get('description'),
        type_data.get('mass'),
        type_data.get('volume'),
        type_data.get('capacity'),
        type_data.get('portion_size'),
        type_data.get('race_id'),
        type_data.get('base_price'),
        type_data.get('published', 0),
        type_data.get('market_group_id'),
        type_data.get('icon_id'),
        type_data.get('sound_id'),
        type_data.get('graphic_id')
    ))

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting inv_types update from ESI")
    print("=" * 50)
    
    # Step 1: Get all type IDs (with pagination)
    type_ids = get_all_type_ids()
    
    if not type_ids:
        print("No type IDs found. Exiting.")
        return
    
    # Step 2: Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Step 3: Loop through each type and fetch/insert data
    print("\nFetching and inserting type data...")
    total = len(type_ids)
    successful = 0
    
    for index, type_id in enumerate(type_ids, 1):
        # Show progress every 500 types
        if index % 500 == 0:
            print(f"Progress: {index}/{total} types processed ({successful} successful)...")
        
        # Get detailed info for this type
        type_data = get_type_info(type_id)
        
        if type_data:
            # Insert into database
            insert_type_into_db(conn, type_data)
            successful += 1
            
            # Commit every 500 types to avoid losing progress
            if index % 500 == 0:
                conn.commit()
    
    # Step 4: Save changes and close connection
    print("\nSaving final changes to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("inv_types update complete!")
    print(f"Total type IDs checked: {total}")
    print(f"Successfully inserted: {successful}")
    print("=" * 50)

if __name__ == '__main__':
    main()