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

def get_all_category_ids():
    """
    Get a list of all category IDs from ESI.
    No authentication required.
    """
    url = f'{ESI_BASE_URL}/universe/categories/'
    
    print("Fetching list of all category IDs from ESI...")
    response = requests.get(url)
    
    if response.status_code == 200:
        category_ids = response.json()
        print(f"Found {len(category_ids)} category IDs")
        return category_ids
    else:
        print(f"Error fetching category IDs: {response.status_code}")
        return []

def get_category_info(category_id):
    """
    Get detailed information about a specific category from ESI.
    """
    url = f'{ESI_BASE_URL}/universe/categories/{category_id}/'
    
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching category {category_id}: {response.status_code}")
        return None

def insert_category_into_db(conn, category_data):
    """
    Insert a single category into the database.
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO inv_categories (
            category_id, category_name, icon_id, published
        ) VALUES (?, ?, ?, ?)
    ''', (
        category_data['category_id'],
        category_data['name'],
        category_data.get('icon_id'),
        category_data.get('published', 0)
    ))

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting inv_categories update from ESI")
    print("=" * 50)
    
    # Get all category IDs
    category_ids = get_all_category_ids()
    
    if not category_ids:
        print("No category IDs found. Exiting.")
        return
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Loop through each category
    print("\nFetching and inserting category data...")
    total = len(category_ids)
    
    for index, category_id in enumerate(category_ids, 1):
        print(f"Processing category {index}/{total}: ID {category_id}")
        
        category_data = get_category_info(category_id)
        
        if category_data:
            insert_category_into_db(conn, category_data)
    
    # Save and close
    print("\nSaving changes to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("inv_categories update complete!")
    print(f"Total categories processed: {total}")
    print("=" * 50)

if __name__ == '__main__':
    main()