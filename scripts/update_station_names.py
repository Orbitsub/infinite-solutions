from script_utils import timed_script
import requests
import sqlite3
import os
import time

# ============================================
# CONFIGURATION
# ============================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# ============================================
# CREATE TABLE
# ============================================
def create_stations_table(conn):
    """Create table for station/structure names if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stations (
            location_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            last_updated TEXT
        )
    ''')
    conn.commit()

# ============================================
# FETCH NAMES
# ============================================
def get_station_name(location_id):
    """
    Get station/structure name from ESI.
    Handles both NPC stations and player structures.
    """
    # Try as station first (NPC stations, IDs < 70000000)
    if location_id < 70000000:
        url = f'{ESI_BASE_URL}/universe/stations/{location_id}/'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('name'), 'NPC Station'
    
    # Try as structure (player-owned, IDs >= 1000000000000)
    url = f'{ESI_BASE_URL}/universe/structures/{location_id}/'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return data.get('name'), 'Player Structure'
    elif response.status_code == 403:
        # Forbidden - structure exists but you don't have access to see name
        return f'Private Structure {location_id}', 'Private Structure'
    else:
        return f'Unknown Location {location_id}', 'Unknown'

def insert_station_into_db(conn, location_id, name, station_type):
    """Insert or update station name in database."""
    cursor = conn.cursor()
    from datetime import datetime, timezone
    
    cursor.execute('''
        INSERT OR REPLACE INTO stations (location_id, name, type, last_updated)
        VALUES (?, ?, ?, ?)
    ''', (location_id, name, station_type, datetime.now(timezone.utc).isoformat()))

# ============================================
# MAIN SCRIPT
# ============================================
@timed_script
def main():
    print("=" * 60)
    print("STATION NAMES UPDATE")
    print("=" * 60)
    
    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    
    # Create table
    print("Creating stations table...")
    create_stations_table(conn)
    
    # Get all unique location IDs from market orders
    print("\nGetting unique station IDs from market orders...")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT location_id 
        FROM market_orders 
        WHERE region_id = 10000002
        ORDER BY location_id
    ''')
    
    location_ids = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(location_ids)} unique stations/structures")
    
    # Check which ones we already have
    cursor.execute('SELECT location_id FROM stations')
    existing = set(row[0] for row in cursor.fetchall())
    
    to_fetch = [lid for lid in location_ids if lid not in existing]
    print(f"Already have {len(existing)} station names")
    print(f"Need to fetch {len(to_fetch)} new station names")
    
    if not to_fetch:
        print("\nAll station names are up to date!")
        conn.close()
        return
    
    # Fetch names
    print("\nFetching station names from ESI...")
    print("This may take a few minutes...\n")
    
    total = len(to_fetch)
    success_count = 0
    private_count = 0
    error_count = 0
    
    for index, location_id in enumerate(to_fetch, 1):
        if index % 10 == 0:
            print(f"Progress: {index}/{total} ({index/total*100:.1f}%)")
        
        try:
            name, station_type = get_station_name(location_id)
            insert_station_into_db(conn, location_id, name, station_type)
            
            if station_type == 'Private Structure':
                private_count += 1
            else:
                success_count += 1
            
            # Commit every 50 to save progress
            if index % 50 == 0:
                conn.commit()
            
            # Rate limiting - ESI allows 150 req/sec but be conservative
            time.sleep(0.02)  # 50 requests per second
            
        except Exception as e:
            print(f"  Error fetching location {location_id}: {e}")
            error_count += 1
            continue
    
    # Final commit
    print("\nSaving to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print("STATION NAMES UPDATE COMPLETE")
    print("=" * 60)
    print(f"Successfully fetched: {success_count}")
    print(f"Private structures: {private_count}")
    print(f"Errors: {error_count}")
    print(f"Total in database: {success_count + private_count}")
    print("=" * 60)

if __name__ == '__main__':
    main()