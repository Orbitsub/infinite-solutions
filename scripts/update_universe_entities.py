import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import requests
import sqlite3
from datetime import datetime, timezone

# ============================================
# CONFIGURATION
# ============================================
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Key entities for Jita/High-sec trading
FACTIONS_TO_FETCH = [500001, 500002, 500003, 500004]  # Cal, Min, Amarr, Gal
CORPORATIONS_TO_FETCH = [
    1000035,  # Caldari Navy
    1000125,  # Minmatar Fleet
    1000182,  # Imperial Navy
    1000127,  # Federal Navy
]

# ============================================
# FUNCTIONS
# ============================================

def fetch_all_factions():
    """Fetch all factions from ESI."""
    url = f'{ESI_BASE_URL}/universe/factions/'
    print("Fetching all factions from ESI...")
    
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching factions: {response.status_code}")
        return []

def fetch_corporation(corp_id):
    """Fetch corporation details from ESI."""
    url = f'{ESI_BASE_URL}/corporations/{corp_id}/'
    
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"  Error fetching corporation {corp_id}: {response.status_code}")
        return None

def update_entities_in_db(conn):
    """Populate universe_entities with key trading entities."""
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Fetch and insert factions
    print("\nFetching factions...")
    factions = fetch_all_factions()
    faction_count = 0
    
    for faction in factions:
        cursor.execute('''
            INSERT OR REPLACE INTO universe_entities (
                entity_id, entity_type, entity_name, description, ticker, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            faction['faction_id'],
            'faction',
            faction['name'],
            faction.get('description'),
            None,
            current_time
        ))
        print(f"  Added faction: {faction['name']}")
        faction_count += 1
    
# Fetch and insert key corporations
    print("\nFetching key trading corporations...")
    corp_count = 0
    
    for corp_id in CORPORATIONS_TO_FETCH:
        corp_data = fetch_corporation(corp_id)
        if corp_data:
            cursor.execute('''
                INSERT OR REPLACE INTO universe_entities (
                    entity_id, entity_type, entity_name, description, ticker, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                corp_id,  # Use the corp_id we already have
                'corporation',
                corp_data['name'],
                corp_data.get('description'),
                corp_data.get('ticker'),
                current_time
            ))
            print(f"  Added corporation: {corp_data['name']} [{corp_data.get('ticker')}]")
            corp_count += 1
    
    return faction_count, corp_count

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting universe entities update")
    print("=" * 50)
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Update entities
    faction_count, corp_count = update_entities_in_db(conn)
    
    # Save
    print("\nSaving changes...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("Universe entities update complete!")
    print(f"Factions added: {faction_count}")
    print(f"Corporations added: {corp_count}")
    print("=" * 50)

if __name__ == '__main__':
    main()