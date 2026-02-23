from script_utils import timed_script
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import requests
import sqlite3
from datetime import datetime, timezone
from token_manager import get_token, character_id

# ============================================
# CONFIGURATION
# ============================================
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# ============================================
# FUNCTIONS
# ============================================

def get_character_standings(character_id, token):
    """Get character standings from ESI."""
    url = f'{ESI_BASE_URL}/characters/{character_id}/standings/'
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"Fetching standings for character {character_id}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching standings: {response.status_code}")
        return None

def get_or_create_entity(conn, entity_id, entity_type):
    """
    Get entity from universe_entities table, or fetch and create if doesn't exist.
    This caches entity names so we only fetch each one once.
    """
    cursor = conn.cursor()
    
    # Check if entity already exists
    cursor.execute('SELECT entity_name FROM universe_entities WHERE entity_id = ?', (entity_id,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # Entity doesn't exist, fetch from ESI
    entity_name = None
    description = None
    ticker = None
    
    try:
        if entity_type == 'faction':
            url = f'{ESI_BASE_URL}/universe/factions/'
            response = requests.get(url)
            if response.status_code == 200:
                factions = response.json()
                for faction in factions:
                    if faction['faction_id'] == entity_id:
                        entity_name = faction['name']
                        description = faction.get('description')
                        break
        
        elif entity_type == 'corporation':
            url = f'{ESI_BASE_URL}/corporations/{entity_id}/'
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                entity_name = data.get('name')
                ticker = data.get('ticker')
                description = data.get('description')
        
        elif entity_type == 'agent':
            url = f'{ESI_BASE_URL}/agents/{entity_id}/'
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                entity_name = data.get('name')
    
    except Exception as e:
        print(f"  Warning: Could not fetch {entity_type} {entity_id}: {e}")
    
    # Use fallback name if we couldn't fetch
    if not entity_name:
        entity_name = f'{entity_type.title()} {entity_id}'
    
    # Insert into universe_entities
    current_time = datetime.now(timezone.utc).isoformat()
    cursor.execute('''
        INSERT OR REPLACE INTO universe_entities (
            entity_id, entity_type, entity_name, description, ticker, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (entity_id, entity_type, entity_name, description, ticker, current_time))
    
    return entity_name

def update_standings_in_db(conn, character_id, standings_data):
    """
    Update ALL standings in database.
    Entity names are stored in universe_entities (normalized design).
    """
    if not standings_data:
        return 0
    
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    total_standings = len(standings_data)
    print(f"Updating {total_standings} standings...")
    
    for index, standing in enumerate(standings_data, 1):
        if index % 10 == 0:
            print(f"  Progress: {index}/{total_standings}...")
        
        from_id = standing['from_id']
        from_type = standing['from_type']
        
        # Get or create entity (caches the name)
        get_or_create_entity(conn, from_id, from_type)
        
        # Insert standing
        cursor.execute('''
            INSERT OR REPLACE INTO character_standings (
                character_id, from_type, from_id, standing, last_updated
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            character_id,
            from_type,
            from_id,
            standing['standing'],
            current_time
        ))
    
    return total_standings

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    print("=" * 50)
    print("Starting character standings update")
    print("=" * 50)
    
    # Get token
    print("\nGetting access token...")
    token = get_token()
    
    # Connect to database
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Get standings
    print("\nFetching standings from ESI...")
    standings_data = get_character_standings(character_id, token)
    
    if standings_data:
        updated = update_standings_in_db(conn, character_id, standings_data)
        print(f"\nUpdated {updated} standings")
        
        # Show key standings as confirmation
        print("\nKey faction standings:")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ue.entity_name, cs.standing
            FROM character_standings cs
            JOIN universe_entities ue ON cs.from_id = ue.entity_id
            WHERE cs.character_id = ?
            AND ue.entity_type = 'faction'
            ORDER BY cs.standing DESC
        ''', (character_id,))
        
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]:.2f}")
    
    # Save
    print("\nSaving changes...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("Character standings update complete!")
    print("=" * 50)

if __name__ == '__main__':
    main()