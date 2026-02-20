from script_utils import timed_script
import sys
import os

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
CHARACTER_ID = 2114278577

# ============================================
# FUNCTIONS
# ============================================

def get_character_skills(character_id, token):
    """Get character skills from ESI."""
    url = f'{ESI_BASE_URL}/characters/{character_id}/skills/'
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"Fetching skills for character {character_id}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching skills: {response.status_code}")
        return None

def update_skills_in_db(conn, character_id, skills_data):
    """
    Update ALL skills in database.
    Skill names come from inv_types table (normalized design).
    """
    if not skills_data or 'skills' not in skills_data:
        return 0
    
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    total_skills = len(skills_data['skills'])
    print(f"Updating {total_skills} skills...")
    
    for skill in skills_data['skills']:
        cursor.execute('''
            INSERT OR REPLACE INTO character_skills (
                character_id, skill_id, active_skill_level, 
                trained_skill_level, last_updated
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            character_id,
            skill['skill_id'],
            skill['active_skill_level'],
            skill['trained_skill_level'],
            current_time
        ))
    
    return total_skills

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    print("=" * 50)
    print("Starting character skills update")
    print("=" * 50)
    
    # Get token
    print("\nGetting access token...")
    token = get_token()
    
    # Connect to database
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Get skills
    print("\nFetching skills from ESI...")
    skills_data = get_character_skills(CHARACTER_ID, token)
    
    if skills_data:
        updated = update_skills_in_db(conn, CHARACTER_ID, skills_data)
        print(f"Updated {updated} skills")
        
        # Show trading skills as confirmation
        print("\nKey trading skills:")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.type_name, cs.active_skill_level
            FROM character_skills cs
            JOIN inv_types t ON cs.skill_id = t.type_id
            WHERE cs.character_id = ?
            AND t.type_name IN ('Broker Relations', 'Accounting', 'Trade', 'Retail', 'Advanced Broker Relations')
        ''', (CHARACTER_ID,))
        
        for row in cursor.fetchall():
            print(f"  {row[0]}: Level {row[1]}")
    
    # Save
    print("\nSaving changes...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("Character skills update complete!")
    print("=" * 50)

if __name__ == '__main__':
    main()