"""
Fetch and update blueprints from ESI.
Stores BPO/BPC data with ME/TE in database.
"""
import requests
import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps
import sys

# Add scripts and config directories to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts'))
sys.path.insert(0, os.path.join(PROJECT_DIR, 'config'))

from token_manager import TokenManager

try:
    from script_utils import timed_script
except ImportError:
    # If script_utils doesn't exist, create a simple decorator
    def timed_script(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"\n{'='*60}")
            print(f"{func.__name__.upper().replace('_', ' ')}")
            print(f"Started: {datetime.now().strftime('%I:%M:%S %p')}")
            print(f"{'='*60}\n")
            result = func(*args, **kwargs)
            print(f"\nFinished: {datetime.now().strftime('%I:%M:%S %p')}")
            return result
        return wrapper

# ============================================
# CONFIGURATION
# ============================================
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

ESI_BASE_URL = 'https://esi.evetech.net/latest'
ESI_VERIFY_URL = 'https://esi.evetech.net/verify/'

# ============================================
# ESI API FUNCTIONS
# ============================================

def resolve_character_identity(access_token, creds):
    """Resolve character identity from ESI token verify endpoint."""
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        response = requests.get(ESI_VERIFY_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            payload = response.json()
            return payload.get('CharacterID'), payload.get('CharacterName')
        raise Exception(f"ESI verify failed: {response.status_code} - {response.text}")
    except Exception as verify_error:
        character_id = creds.get('character_id')
        character_name = creds.get('character_name', 'Unknown')

        if character_id:
            print(f"[WARN] Could not verify token with ESI ({verify_error}); using character_id from credentials")
            return character_id, character_name

        raise RuntimeError(
            f"Could not determine character identity: {verify_error}. "
            "Add character_id to config/credentials.json or ensure ESI /verify is reachable."
        )

def fetch_character_blueprints(character_id, access_token):
    """Fetch all blueprints for a character from ESI."""
    url = f"{ESI_BASE_URL}/characters/{character_id}/blueprints/"

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    print(f"Fetching blueprints from ESI...")

    all_blueprints = []
    page = 1

    while True:
        params = {'page': page}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            blueprints = response.json()

            if not blueprints:  # Empty page means we're done
                break

            all_blueprints.extend(blueprints)
            print(f"  Page {page}: {len(blueprints)} blueprints")

            # Check if there are more pages
            total_pages = response.headers.get('X-Pages', '1')
            if page >= int(total_pages):
                break

            page += 1
        else:
            raise Exception(f"ESI request failed: {response.status_code} - {response.text}")

    print(f"[OK] Total blueprints fetched: {len(all_blueprints)}")
    return all_blueprints

# ============================================
# DATABASE FUNCTIONS
# ============================================

def get_blueprint_names(conn, type_ids):
    """Get blueprint names from inv_types table."""
    if not type_ids:
        return {}

    placeholders = ','.join('?' * len(type_ids))
    query = f"""
        SELECT type_id, type_name
        FROM inv_types
        WHERE type_id IN ({placeholders})
    """

    cursor = conn.cursor()
    cursor.execute(query, type_ids)

    return dict(cursor.fetchall())

def store_blueprints(conn, blueprints, type_names):
    """Store blueprints in database."""
    cursor = conn.cursor()

    print(f"\n>>> Storing blueprints in database...")

    # Clear old data
    cursor.execute("DELETE FROM character_blueprints")

    # Insert new data
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            bp['item_id'],
            bp['type_id'],
            type_names.get(bp['type_id'], f"Unknown ({bp['type_id']})"),
            bp['location_id'],
            bp['location_flag'],
            bp['quantity'],
            bp['time_efficiency'],
            bp['material_efficiency'],
            bp['runs'],
            now,
        )
        for bp in blueprints
    ]
    cursor.executemany("""
        INSERT INTO character_blueprints
        (item_id, type_id, type_name, location_id, location_flag,
         quantity, time_efficiency, material_efficiency, runs, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    print(f"[OK] Stored {len(blueprints)} blueprints")

    # Show summary
    cursor.execute("SELECT COUNT(*) FROM character_blueprints WHERE runs = -1")
    bpo_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM character_blueprints WHERE runs > 0")
    bpc_count = cursor.fetchone()[0]

    print(f"     BPOs: {bpo_count}")
    print(f"     BPCs: {bpc_count}")

    return True

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    """Fetch and store blueprints."""

    # Get access token (credentials are loaded inside TokenManager)
    token_mgr = TokenManager()
    creds = token_mgr.credentials

    access_token = token_mgr.get_access_token()
    character_id, character_name = resolve_character_identity(access_token, creds)

    print(f"Character ID: {character_id}")
    print(f"Character Name: {character_name}")

    # Fetch blueprints from ESI
    blueprints = fetch_character_blueprints(character_id, access_token)

    if not blueprints:
        print("[!] No blueprints found")
        return

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    try:
        # Get blueprint names from inv_types
        type_ids = list(set(bp['type_id'] for bp in blueprints))
        print(f"[OK] Found {len(type_ids)} unique blueprint types")

        type_names = get_blueprint_names(conn, type_ids)
        print(f"[OK] Resolved {len(type_names)} blueprint names from database")

        # Store blueprints
        store_blueprints(conn, blueprints, type_names)

        print("\n" + "="*60)
        print("BLUEPRINT UPDATE SUMMARY")
        print("="*60)
        print(f"Total blueprints: {len(blueprints)}")
        print(f"Unique types: {len(type_ids)}")
        print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        print("\n[OK] Blueprint update completed!")

    except Exception as e:
        print(f"[ERROR] {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
