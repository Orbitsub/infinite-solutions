"""
==========================================
FETCH CORPORATION MEMBERS (RAW)
==========================================
Fetches complete member list for your corporation from ESI
and stores ALL raw fields.

This bypasses the authentication requirement by using public endpoints.
==========================================
"""

from script_utils import timed_script
import requests
import sqlite3
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# ============================================
# CONFIGURATION
# ============================================

CORPORATION_ID = 98814441  # Your corp ID

DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# ============================================
# FUNCTIONS
# ============================================

def create_corp_members_table(conn):
    """Create table to store corporation members."""
    cursor = conn.cursor()
    
    print("Creating corp_members table...")
    
    # Drop existing table
    cursor.execute('DROP TABLE IF EXISTS corp_members')
    
    # Create table with all character fields from ESI
    cursor.execute('''
        CREATE TABLE corp_members (
            character_id INTEGER PRIMARY KEY,
            character_name TEXT NOT NULL,
            corporation_id INTEGER NOT NULL,
            alliance_id INTEGER,
            faction_id INTEGER,
            birthday TEXT,
            gender TEXT,
            race_id INTEGER,
            bloodline_id INTEGER,
            ancestry_id INTEGER,
            security_status REAL,
            title TEXT,
            last_updated TEXT NOT NULL
        )
    ''')
    
    # Indexes
    cursor.execute('CREATE INDEX idx_corp_members_corp ON corp_members(corporation_id)')
    cursor.execute('CREATE INDEX idx_corp_members_alliance ON corp_members(alliance_id)')
    cursor.execute('CREATE INDEX idx_corp_members_name ON corp_members(character_name)')
    
    conn.commit()
    print("[OK] Table created")

def get_corporation_members_list(corp_id):
    """
    Get list of character IDs in corporation.
    
    Note: This endpoint may require authentication for some corps.
    If it fails with 401, you need director roles.
    """
    url = f'{ESI_BASE_URL}/corporations/{corp_id}/members/'
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        print(f"[ERROR] 401 Unauthorized - This corp requires authentication")
        print("You need director roles to access member list")
        return None
    else:
        print(f"[ERROR] Failed to get members: {response.status_code}")
        return None

def get_character_info(character_id):
    """
    Get complete character information from ESI.
    
    All fields available from /characters/{character_id}/:
    - character_id
    - name
    - corporation_id
    - alliance_id (optional)
    - faction_id (optional)
    - birthday
    - gender
    - race_id
    - bloodline_id
    - ancestry_id (optional)
    - security_status (optional)
    - title (optional)
    """
    url = f'{ESI_BASE_URL}/characters/{character_id}/'
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        return None

def store_character(conn, char_id, char_info):
    """Store character with ALL fields from ESI."""
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    cursor.execute('''
        INSERT OR REPLACE INTO corp_members (
            character_id, character_name, corporation_id, alliance_id, faction_id,
            birthday, gender, race_id, bloodline_id, ancestry_id,
            security_status, title, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        char_id,
        char_info.get('name'),
        char_info.get('corporation_id'),
        char_info.get('alliance_id'),
        char_info.get('faction_id'),
        char_info.get('birthday'),
        char_info.get('gender'),
        char_info.get('race_id'),
        char_info.get('bloodline_id'),
        char_info.get('ancestry_id'),
        char_info.get('security_status'),
        char_info.get('title'),
        current_time
    ))

# ============================================
# MAIN
# ============================================

@timed_script
def main():
    """
    Fetch corporation members and store complete data.
    """
    
    print("=" * 80)
    print("FETCH CORPORATION MEMBERS (RAW)")
    print("=" * 80)
    print(f"\nCorporation ID: {CORPORATION_ID}")
    
    # Get member list
    print("\nFetching member list from ESI...")
    member_ids = get_corporation_members_list(CORPORATION_ID)
    
    if not member_ids:
        print("\n[ERROR] Could not fetch member list")
        print("\nThis could be because:")
        print("  1. The corp member list is private")
        print("  2. You need director roles")
        print("  3. The corporation doesn't exist")
        return
    
    print(f"Found {len(member_ids):,} members")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Create table
        create_corp_members_table(conn)
        
        # Fetch character info for each member
        print(f"\nFetching character data for {len(member_ids):,} members...")
        
        processed = 0
        failed = 0
        
        for i, char_id in enumerate(member_ids, 1):
            if i % 50 == 0:
                print(f"  Processed {i}/{len(member_ids)} members...", end='\r')
            
            char_info = get_character_info(char_id)
            
            if char_info:
                store_character(conn, char_id, char_info)
                processed += 1
            else:
                failed += 1
            
            # Commit every 100 characters
            if i % 100 == 0:
                conn.commit()
        
        conn.commit()
        
        print(f"\n\n[OK] Processed {processed:,} members")
        if failed > 0:
            print(f"[WARNING] Failed to fetch {failed:,} members")
        
        # Show summary
        cursor = conn.cursor()
        
        print("\n" + "=" * 80)
        print("CORPORATION MEMBERS SUMMARY")
        print("=" * 80)
        
        cursor.execute('SELECT COUNT(*) FROM corp_members')
        total = cursor.fetchone()[0]
        print(f"\nTotal Members: {total:,}")
        
        # Alliance members
        cursor.execute('''
            SELECT COUNT(*) FROM corp_members 
            WHERE alliance_id IS NOT NULL
        ''')
        in_alliance = cursor.fetchone()[0]
        print(f"In Alliance: {in_alliance:,}")
        
        # Gender breakdown
        cursor.execute('''
            SELECT gender, COUNT(*) 
            FROM corp_members 
            GROUP BY gender
        ''')
        print("\nGender Breakdown:")
        for gender, count in cursor.fetchall():
            print(f"  {gender}: {count:,}")
        
        # Top 10 members by name
        cursor.execute('''
            SELECT character_name 
            FROM corp_members 
            ORDER BY character_name 
            LIMIT 10
        ''')
        print("\nFirst 10 Members (alphabetically):")
        for (name,) in cursor.fetchall():
            print(f"  - {name}")
        
        print("=" * 80)
        
        print("\n[OK] Corporation members stored!")
        print("\nQuery examples:")
        print("  SELECT * FROM corp_members;")
        print("  SELECT character_name FROM corp_members ORDER BY character_name;")
        print("  SELECT COUNT(*) FROM corp_members WHERE alliance_id = 498125261;")
        
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        raise

if __name__ == '__main__':
    main()