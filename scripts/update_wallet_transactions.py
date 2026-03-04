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

def get_wallet_transactions(character_id, token):
    """
    Get wallet transactions for a character.
    Returns the most recent transactions (ESI returns last 30 days by default).
    """
    url = f'{ESI_BASE_URL}/characters/{character_id}/wallet/transactions/'
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f"Fetching wallet transactions for character {character_id}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        transactions = response.json()
        print(f"Found {len(transactions)} transactions")
        return transactions
    else:
        print(f"Error fetching wallet transactions: {response.status_code}")
        print(f"Response: {response.text}")
        return []

def insert_transaction_into_db(conn, character_id, transaction):
    """
    Insert a wallet transaction into the database.
    Uses INSERT OR REPLACE to update last_updated for existing transactions.
    """
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    cursor.execute('''
        INSERT OR REPLACE INTO wallet_transactions (
            transaction_id, character_id, date, type_id, location_id,
            quantity, unit_price, client_id, is_buy, is_personal, journal_ref_id,
            last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        transaction['transaction_id'],
        character_id,
        transaction['date'],
        transaction['type_id'],
        transaction['location_id'],
        transaction['quantity'],
        transaction['unit_price'],
        transaction['client_id'],
        1 if transaction['is_buy'] else 0,
        1 if transaction['is_personal'] else 0,
        transaction.get('journal_ref_id'),
        current_time
    ))

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    print("=" * 50)
    print("Starting wallet_transactions update")
    print("=" * 50)
    
    # Get token (will auto-refresh if needed)
    print("\nGetting access token...")
    token = get_token()
    
    # Connect to database
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # Get transactions
    print("\nFetching wallet transactions...")
    transactions = get_wallet_transactions(character_id, token)
    
    if transactions:
        print(f"Inserting {len(transactions)} transactions...")
        for transaction in transactions:
            insert_transaction_into_db(conn, character_id, transaction)
    
    # Save and close
    print("\nSaving changes to database...")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("wallet_transactions update complete!")
    print(f"Total transactions processed: {len(transactions)}")
    print("=" * 50)

if __name__ == '__main__':
    main()