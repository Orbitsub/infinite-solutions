from script_utils import timed_script
import sys
import os

# Add the scripts directory to Python's path
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

def get_wallet_journal(character_id, token):
    """
    Get wallet journal entries for a character.
    ESI paginates this, so we need to fetch multiple pages.
    """
    all_entries = []
    page = 1
    
    print(f"Fetching wallet journal for character {character_id}...")
    
    while True:
        url = f'{ESI_BASE_URL}/characters/{character_id}/wallet/journal/'
        headers = {'Authorization': f'Bearer {token}'}
        params = {'page': page}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            entries = response.json()
            
            if not entries:  # Empty page means we're done
                break
            
            all_entries.extend(entries)
            print(f"  Page {page}: fetched {len(entries)} entries (total: {len(all_entries)})")
            page += 1
            
        else:
            print(f"Error fetching wallet journal page {page}: {response.status_code}")
            break
    
    return all_entries

def insert_journal_entry_into_db(conn, character_id, entry):
    """
    Insert a wallet journal entry into the database.
    Uses INSERT OR IGNORE to avoid duplicates.
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO wallet_journal (
            id, character_id, date, ref_type, amount, balance,
            description, first_party_id, second_party_id, reason,
            tax, tax_receiver_id, context_id, context_id_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        entry['id'],
        character_id,
        entry['date'],
        entry['ref_type'],
        entry.get('amount'),
        entry.get('balance'),
        entry.get('description'),
        entry.get('first_party_id'),
        entry.get('second_party_id'),
        entry.get('reason'),
        entry.get('tax'),
        entry.get('tax_receiver_id'),
        entry.get('context_id'),
        entry.get('context_id_type')
    ))

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    print("=" * 50)
    print("Starting wallet_journal update")
    print("=" * 50)
    
    # Get token (will auto-refresh if needed)
    print("\nGetting access token...")
    token = get_token()
    
    # Connect to database
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Get journal entries
    print("\nFetching wallet journal entries...")
    entries = get_wallet_journal(character_id, token)
    
    if entries:
        print(f"\nInserting {len(entries)} journal entries...")
        for entry in entries:
            insert_journal_entry_into_db(conn, character_id, entry)
    
    # Save and close
    print("\nSaving changes to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("wallet_journal update complete!")
    print(f"Total journal entries processed: {len(entries)}")
    print("=" * 50)

if __name__ == '__main__':
    main()