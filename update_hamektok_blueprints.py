"""
Fetch and update Hamektok Hakaari's blueprints from ESI.
Stores BPO/BPC data with ME/TE in database.
"""
import requests
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from base64 import b64encode
import sys

# Add scripts directory to path for utilities
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'scripts'))

try:
    from script_utils import timed_script
except ImportError:
    # If script_utils doesn't exist, create a simple decorator
    def timed_script(func):
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
PROJECT_DIR = SCRIPT_DIR
CREDENTIALS_PATH = os.path.join(PROJECT_DIR, 'config', 'credentials_hamektok.json')
TOKEN_CACHE_PATH = os.path.join(PROJECT_DIR, 'config', 'token_cache_hamektok.json')
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
LOG_PATH = os.path.join(PROJECT_DIR, 'logs', 'blueprint_updates.log')

ESI_TOKEN_URL = 'https://login.eveonline.com/v2/oauth/token'
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# ============================================
# TOKEN MANAGEMENT
# ============================================

class HamektokTokenManager:
    """Token manager for Hamektok Hakaari character."""

    def __init__(self):
        self.credentials = self._load_credentials()
        self.token_cache = self._load_token_cache()

    def _load_credentials(self):
        """Load credentials from Hamektok's config file."""
        with open(CREDENTIALS_PATH, 'r') as f:
            return json.load(f)

    def _load_token_cache(self):
        """Load cached access token if exists."""
        if os.path.exists(TOKEN_CACHE_PATH):
            with open(TOKEN_CACHE_PATH, 'r') as f:
                return json.load(f)
        return {}

    def _save_token_cache(self, access_token, expires_in):
        """Save access token to cache."""
        expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
        cache = {
            'access_token': access_token,
            'expires_at': expiry.isoformat()
        }
        with open(TOKEN_CACHE_PATH, 'w') as f:
            json.dump(cache, f, indent=2)
        self.token_cache = cache

    def _is_token_valid(self):
        """Check if cached token is still valid."""
        if 'access_token' not in self.token_cache or 'expires_at' not in self.token_cache:
            return False
        expiry = datetime.fromisoformat(self.token_cache['expires_at'])
        return datetime.now(timezone.utc) < expiry

    def _refresh_access_token(self):
        """Get new access token from ESI."""
        print("Refreshing access token...")

        client_id = self.credentials['client_id']
        client_secret = self.credentials['client_secret']

        auth_string = f"{client_id}:{client_secret}"
        auth_header = b64encode(auth_string.encode()).decode()

        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.credentials['refresh_token']
        }

        response = requests.post(ESI_TOKEN_URL, headers=headers, data=data)

        if response.status_code == 200:
            token_data = response.json()
            self._save_token_cache(token_data['access_token'], token_data['expires_in'])
            print(f"[OK] New access token obtained")
            return token_data['access_token']
        else:
            raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")

    def get_access_token(self):
        """Get valid access token (cached or refreshed)."""
        if self._is_token_valid():
            print("Using cached access token")
            return self.token_cache['access_token']
        else:
            return self._refresh_access_token()

# ============================================
# ESI API FUNCTIONS
# ============================================

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
    for bp in blueprints:
        type_id = bp['type_id']
        type_name = type_names.get(type_id, f"Unknown ({type_id})")

        cursor.execute("""
            INSERT INTO character_blueprints
            (item_id, type_id, type_name, location_id, location_flag,
             quantity, time_efficiency, material_efficiency, runs, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bp['item_id'],
            type_id,
            type_name,
            bp['location_id'],
            bp['location_flag'],
            bp['quantity'],
            bp['time_efficiency'],
            bp['material_efficiency'],
            bp['runs'],
            datetime.now(timezone.utc).isoformat()
        ))

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
    """Fetch and store Hamektok's blueprints."""

    # Load credentials
    with open(CREDENTIALS_PATH, 'r') as f:
        creds = json.load(f)

    character_id = creds['character_id']
    character_name = creds['character_name']

    print(f"Character ID: {character_id}")
    print(f"Character Name: {character_name}")

    # Get access token
    token_manager = HamektokTokenManager()
    access_token = token_manager.get_access_token()

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
