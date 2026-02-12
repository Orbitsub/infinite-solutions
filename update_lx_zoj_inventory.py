"""
Update LX-ZOJ Inventory
Fetches inventory from LX-ZOJ citadel via ESI, stores snapshot in database,
and updates index.html with current stock levels.
"""
import requests
import sqlite3
import os
import sys
from datetime import datetime, timezone

# Add scripts directory to path for imports
SCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
sys.path.insert(0, SCRIPT_DIR)

# Import token manager and script utils
from token_manager import get_token

# ============================================
# CONFIGURATION
# ============================================
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
HTML_PATH = os.path.join(PROJECT_DIR, 'index.html')
HTML_BACKUP_PATH = os.path.join(PROJECT_DIR, 'index.backup.html')

ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Your character ID
CHARACTER_ID = 2114278577

# LX-ZOJ Structure ID
LX_ZOJ_STRUCTURE_ID = 1027625808467

# ============================================
# FUNCTIONS
# ============================================

def get_authenticated_headers():
    """Get headers with authentication token."""
    try:
        token = get_token()
        return {'Authorization': f'Bearer {token}'}
    except Exception as e:
        print(f"[ERROR] Failed to get access token: {e}")
        return None

def get_character_assets(headers):
    """Get all character assets from ESI."""
    all_assets = []
    page = 1

    print("Fetching character assets from ESI...")

    while True:
        url = f'{ESI_BASE_URL}/characters/{CHARACTER_ID}/assets/'
        params = {'page': page}

        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            assets = response.json()

            if not assets:
                break

            all_assets.extend(assets)
            print(f"  Page {page}: {len(assets)} assets")
            page += 1

        elif response.status_code == 404:
            break
        else:
            print(f"[ERROR] Fetching assets page {page}: {response.status_code}")
            break

    print(f"[OK] Total assets fetched: {len(all_assets)}")
    return all_assets

def filter_lx_zoj_items(assets):
    """Filter assets to only LX-ZOJ structure hangar."""
    lx_zoj_items = [
        asset for asset in assets
        if asset.get('location_id') == LX_ZOJ_STRUCTURE_ID
        and asset.get('location_flag') == 'Hangar'
    ]

    print(f"[OK] Filtered to LX-ZOJ hangar: {len(lx_zoj_items)} items")
    return lx_zoj_items

def get_tracked_items(conn):
    """Get list of tracked item type_ids from database."""
    cursor = conn.cursor()
    cursor.execute('SELECT type_id, type_name FROM tracked_market_items')
    tracked = {row[0]: row[1] for row in cursor.fetchall()}
    print(f"[OK] Loaded {len(tracked)} tracked items from database")
    return tracked

def match_tracked_inventory(lx_zoj_items, tracked_items):
    """
    Match LX-ZOJ items against tracked items.
    Returns dict: {type_id: quantity}
    """
    inventory = {}

    for asset in lx_zoj_items:
        type_id = asset.get('type_id')
        quantity = asset.get('quantity', 1)

        if type_id in tracked_items:
            # Aggregate quantities for same type
            if type_id in inventory:
                inventory[type_id] += quantity
            else:
                inventory[type_id] = quantity

    print(f"[OK] Matched {len(inventory)} tracked items in LX-ZOJ")
    return inventory

def store_inventory_snapshot(conn, inventory, tracked_items):
    """Store inventory snapshot in lx_zoj_inventory table."""
    cursor = conn.cursor()
    snapshot_time = datetime.now(timezone.utc).isoformat()

    print(f"\n>>> Storing inventory snapshot...")

    items_inserted = 0

    for type_id, quantity in inventory.items():
        type_name = tracked_items[type_id]

        cursor.execute('''
            INSERT INTO lx_zoj_inventory (
                snapshot_timestamp, type_id, type_name,
                quantity, location_id, location_name
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            snapshot_time,
            type_id,
            type_name,
            quantity,
            LX_ZOJ_STRUCTURE_ID,
            'LX-ZOJ'
        ))

        items_inserted += 1

    # Insert 0 quantities for tracked items not in inventory
    for type_id, type_name in tracked_items.items():
        if type_id not in inventory:
            cursor.execute('''
                INSERT INTO lx_zoj_inventory (
                    snapshot_timestamp, type_id, type_name,
                    quantity, location_id, location_name
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                snapshot_time,
                type_id,
                type_name,
                0,
                LX_ZOJ_STRUCTURE_ID,
                'LX-ZOJ'
            ))
            items_inserted += 1

    conn.commit()
    print(f"[OK] Snapshot stored: {items_inserted} items at {snapshot_time}")

    return snapshot_time

def get_current_inventory_from_db(conn):
    """Get the latest inventory snapshot from database."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT type_id, type_name, quantity
        FROM lx_zoj_current_inventory
    ''')

    inventory = {row[1]: row[2] for row in cursor.fetchall()}  # {type_name: quantity}
    return inventory

def update_html_inventory(inventory):
    """Update index.html with current inventory quantities by calling update_html_data.py."""
    print(f"\n>>> Updating HTML file...")

    import subprocess

    try:
        # Run update_html_data.py to regenerate HTML with fresh data from database
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, 'update_html_data.py')],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            # Count how many lines mention "SUCCESS" or similar indicators
            if 'SUCCESS' in result.stdout or 'updated successfully' in result.stdout:
                print(f"[OK] HTML regenerated successfully from database")
                print(f"[OK] index_final.html updated with latest inventory")

                # Copy index_final.html to index.html
                import shutil
                shutil.copy2(
                    os.path.join(PROJECT_DIR, 'index_final.html'),
                    os.path.join(PROJECT_DIR, 'index.html')
                )
                print(f"[OK] Copied to index.html")

                return True
            else:
                print(f"[WARNING] HTML update completed but with unexpected output")
                print(f"Output: {result.stdout}")
                return True
        else:
            print(f"[ERROR] HTML update failed with return code {result.returncode}")
            print(f"Error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[ERROR] HTML update timed out")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to update HTML: {e}")
        return False

def commit_and_push_to_github(snapshot_time):
    """Commit and push index.html changes to GitHub."""
    import subprocess

    print(f"\n>>> Pushing to GitHub...")

    try:
        # Check if there are changes to index.html
        result = subprocess.run(
            ['git', 'diff', '--quiet', 'index.html'],
            cwd=PROJECT_DIR,
            capture_output=True
        )

        if result.returncode == 0:
            print("[!] No changes to commit (inventory unchanged)")
            return True

        # Add index.html
        subprocess.run(
            ['git', 'add', 'index.html'],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True
        )
        print("[OK] Staged index.html")

        # Create commit message
        commit_msg = f"Auto-update inventory - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Commit
        subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True
        )
        print(f"[OK] Committed: {commit_msg}")

        # Push to GitHub
        result = subprocess.run(
            ['git', 'push'],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True,
            text=True
        )
        print("[OK] Pushed to GitHub")
        print("     GitHub Pages will update in 1-2 minutes")

        return True

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Git operation failed: {e}")
        if e.output:
            print(f"        Output: {e.output}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error during git push: {e}")
        return False

# ============================================
# MAIN SCRIPT
# ============================================

def ensure_main_branch():
    """Switch to main branch before making any changes (GitHub Pages builds from main)."""
    import subprocess
    try:
        current_branch = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True
        )
        branch_name = current_branch.stdout.strip()

        if branch_name != 'main':
            print(f"[!] Currently on '{branch_name}' branch, switching to main...")
            subprocess.run(
                ['git', 'checkout', 'main'],
                cwd=PROJECT_DIR,
                check=True,
                capture_output=True
            )
            print("[OK] Switched to main branch")
        else:
            print("[OK] Already on main branch")
    except Exception as e:
        print(f"[ERROR] Could not switch to main branch: {e}")

def main():
    """
    Update LX-ZOJ inventory from ESI.
    Stores snapshot in database and updates HTML.
    """

    print("=" * 60)
    print("UPDATE_LX_ZOJ_INVENTORY")
    print(f"Started: {datetime.now().strftime('%I:%M:%S %p')}")
    print("=" * 60)

    # Switch to main branch FIRST (before modifying any files)
    ensure_main_branch()

    print(f"\nCharacter ID: {CHARACTER_ID}")
    print(f"Structure: LX-ZOJ ({LX_ZOJ_STRUCTURE_ID})")

    # Get authentication
    headers = get_authenticated_headers()
    if headers is None:
        print("\n[ERROR] Cannot proceed without authentication")
        return

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    try:
        # Get tracked items list
        tracked_items = get_tracked_items(conn)

        # Fetch all character assets
        all_assets = get_character_assets(headers)

        if not all_assets:
            print("\n[WARNING] No assets found")
            conn.close()
            return

        # Filter to LX-ZOJ hangar only
        lx_zoj_items = filter_lx_zoj_items(all_assets)

        # Match against tracked items
        inventory = match_tracked_inventory(lx_zoj_items, tracked_items)

        # Store snapshot in database
        snapshot_time = store_inventory_snapshot(conn, inventory, tracked_items)

        # Update HTML file (regenerates from database, so we don't need to pass inventory)
        html_success = update_html_inventory(None)

        # Commit and push to GitHub
        git_success = False
        if html_success:
            git_success = commit_and_push_to_github(snapshot_time)

        # Show summary
        print("\n" + "=" * 60)
        print("INVENTORY UPDATE SUMMARY")
        print("=" * 60)
        print(f"Snapshot time: {snapshot_time}")
        print(f"Items in stock: {len([q for q in inventory.values() if q > 0])}")
        print(f"Items out of stock: {len([q for q in inventory.values() if q == 0]) + (35 - len(inventory))}")
        print(f"HTML updated: {'Yes' if html_success else 'No'}")
        print(f"GitHub pushed: {'Yes' if git_success else 'No'}")
        print("=" * 60)

        conn.close()

        print(f"\n[OK] Inventory update completed!")
        print(f"Finished: {datetime.now().strftime('%I:%M:%S %p')}")

    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        raise

if __name__ == '__main__':
    main()
