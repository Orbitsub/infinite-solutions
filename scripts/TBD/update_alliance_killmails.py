"""
==========================================
CORPORATION KILLMAILS VIA ZKILLBOARD
==========================================
This script uses zKillboard's API to fetch killmails
for an entire corporation WITHOUT needing corp member lists.

zKillboard bypasses the ESI corporation membership restriction!

Perfect for:
- Corps where you don't have director roles
- Getting killmails without ESI member list access
==========================================
"""

from script_utils import timed_script
import requests
import sqlite3
import os
import sys
from datetime import datetime, timezone
import time

TBD_DIR     = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(TBD_DIR)
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

# ============================================
# CONFIGURATION
# ============================================

sys.path.insert(0, os.path.join(PROJECT_DIR, 'config'))
from setup import CORPORATION_ID, ALLIANCE_ID

# How many killmails to fetch
# zKillboard returns up to 200 per page
# Set to None to get ALL available killmails (can be thousands!)
MAX_PAGES = None  # ← None = all killmails, or set like: 10

# Database location
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

# API endpoints
ESI_BASE_URL = 'https://esi.evetech.net/latest'
ZKILLBOARD_BASE_URL = 'https://zkillboard.com/api'

# zKillboard requires polite scraping
DELAY_BETWEEN_PAGES = 1.0  # 1 second delay between pages (be nice!)

# ============================================
# FUNCTIONS
# ============================================

def get_zkill_killmails(entity_type, entity_id, max_pages=None):
    """
    Get killmails from zKillboard for a corporation or alliance.
    
    Parameters:
    - entity_type: "corporation" or "alliance"
    - entity_id: The corp/alliance ID
    - max_pages: Maximum pages to fetch (None = all available)
    
    Returns: List of killmail references from zKillboard
    """
    
    all_killmails = []
    page = 1
    
    print(f"\nFetching killmails from zKillboard...")
    print(f"Entity: {entity_type} {entity_id}")
    
    # zKillboard requires a User-Agent
    headers = {
        'User-Agent': 'EVE Market Trading Tool / contact: your_email@example.com'  # ← Add your email
    }
    
    while True:
        # Build URL
        if entity_type == "corporation":
            url = f'{ZKILLBOARD_BASE_URL}/corporationID/{entity_id}/page/{page}/'
        else:  # alliance
            url = f'{ZKILLBOARD_BASE_URL}/allianceID/{entity_id}/page/{page}/'
        
        print(f"  Fetching page {page}...", end='\r')
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            killmails = response.json()
            
            # If no killmails returned, we're done
            if not killmails:
                print(f"\n  No more killmails on page {page}")
                break
            
            all_killmails.extend(killmails)
            print(f"  Page {page}: {len(killmails)} killmails (total: {len(all_killmails):,})")
            
            page += 1
            
            # Check page limit
            if max_pages and page > max_pages:
                print(f"\n  Reached page limit: {max_pages}")
                break
            
            # Be polite - delay between requests
            time.sleep(DELAY_BETWEEN_PAGES)
            
        else:
            print(f"\n  Error fetching page {page}: {response.status_code}")
            break
    
    print(f"\nTotal killmails fetched: {len(all_killmails):,}")
    return all_killmails

def get_killmail_details_from_esi(killmail_id, killmail_hash):
    """
    Get full killmail details from ESI.
    
    Note: This is a PUBLIC endpoint - no auth needed!
    """
    url = f'{ESI_BASE_URL}/killmails/{killmail_id}/{killmail_hash}/'
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        return None

def extract_items_from_killmail(killmail):
    """Extract all items from a killmail."""
    items = []
    
    victim = killmail.get('victim', {})
    ship_type_id = victim.get('ship_type_id')
    
    if ship_type_id:
        items.append({
            'type_id': ship_type_id,
            'quantity': 1,
            'flag': 'Ship',
            'destroyed': True
        })
    
    for item in victim.get('items', []):
        qty_destroyed = item.get('quantity_destroyed', 0)
        qty_dropped = item.get('quantity_dropped', 0)
        total_qty = qty_destroyed + qty_dropped
        
        if total_qty > 0:
            items.append({
                'type_id': item['item_type_id'],
                'quantity': total_qty,
                'flag': item.get('flag', 'Unknown'),
                'destroyed': qty_destroyed > 0
            })
    
    return items

def create_killmail_tables(conn):
    """Create database tables for killmails."""
    cursor = conn.cursor()
    
    print("\n>>> Creating killmail tables...")
    
    # Check if tables already exist
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='corp_killmails'
    """)
    
    if cursor.fetchone():
        print("[INFO] Tables already exist - will update with new killmails")
        return
    
    # Main killmails table
    cursor.execute('''
        CREATE TABLE corp_killmails (
            killmail_id INTEGER PRIMARY KEY,
            killmail_time TEXT NOT NULL,
            character_id INTEGER,
            corporation_id INTEGER NOT NULL,
            alliance_id INTEGER,
            ship_type_id INTEGER NOT NULL,
            solar_system_id INTEGER NOT NULL,
            is_corp_loss INTEGER NOT NULL,
            damage_taken INTEGER NOT NULL,
            num_attackers INTEGER NOT NULL,
            total_value REAL,
            last_updated TEXT NOT NULL
        )
    ''')
    
    # Items table
    cursor.execute('''
        CREATE TABLE corp_killmail_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            killmail_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            flag TEXT,
            destroyed INTEGER NOT NULL,
            FOREIGN KEY (killmail_id) REFERENCES corp_killmails(killmail_id)
        )
    ''')
    
    # Indexes
    cursor.execute('CREATE INDEX idx_corp_km_char ON corp_killmails(character_id)')
    cursor.execute('CREATE INDEX idx_corp_km_corp ON corp_killmails(corporation_id)')
    cursor.execute('CREATE INDEX idx_corp_km_time ON corp_killmails(killmail_time)')
    cursor.execute('CREATE INDEX idx_corp_km_loss ON corp_killmails(is_corp_loss)')
    cursor.execute('CREATE INDEX idx_corp_km_items_type ON corp_killmail_items(type_id)')
    cursor.execute('CREATE INDEX idx_corp_km_items_km ON corp_killmail_items(killmail_id)')
    
    conn.commit()
    print("[OK] Tables created")

def store_killmail(conn, killmail_id, killmail_data, zkb_data, target_corp_id, target_alliance_id):
    """
    Store a killmail in the database.
    
    Parameters:
    - conn: Database connection
    - killmail_id: Killmail ID
    - killmail_data: Full killmail from ESI
    - zkb_data: zKillboard metadata (has value info)
    - target_corp_id: The corp we're tracking (None if tracking alliance)
    - target_alliance_id: The alliance we're tracking (None if tracking corp)
    """
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    victim = killmail_data.get('victim', {})
    attackers = killmail_data.get('attackers', [])
    
    # Determine if this is a loss for our entity
    if target_corp_id:
        # Tracking a corporation
        is_loss = 1 if victim.get('corporation_id') == target_corp_id else 0
    else:
        # Tracking an alliance
        is_loss = 1 if victim.get('alliance_id') == target_alliance_id else 0
    
    # Get zkillboard value data
    zkb = zkb_data.get('zkb', {})
    total_value = zkb.get('totalValue', 0)
    
    # Store main killmail
    cursor.execute('''
        INSERT OR REPLACE INTO corp_killmails (
            killmail_id, killmail_time, character_id, corporation_id, alliance_id,
            ship_type_id, solar_system_id, is_corp_loss, damage_taken, 
            num_attackers, total_value, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        killmail_id,
        killmail_data['killmail_time'],
        victim.get('character_id'),
        victim.get('corporation_id'),
        victim.get('alliance_id'),
        victim.get('ship_type_id', 0),
        killmail_data['solar_system_id'],
        is_loss,
        victim.get('damage_taken', 0),
        len(attackers),
        total_value,
        current_time
    ))
    
    # Delete existing items (in case of re-run)
    cursor.execute('DELETE FROM corp_killmail_items WHERE killmail_id = ?', (killmail_id,))
    
    # Store items
    items = extract_items_from_killmail(killmail_data)
    for item in items:
        cursor.execute('''
            INSERT INTO corp_killmail_items (
                killmail_id, type_id, quantity, flag, destroyed
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            killmail_id,
            item['type_id'],
            item['quantity'],
            item['flag'],
            1 if item['destroyed'] else 0
        ))

def show_summary(conn):
    """Show summary of killmails."""
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("KILLMAIL SUMMARY")
    print("=" * 80)
    
    # Overall stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_corp_loss = 1 THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN is_corp_loss = 0 THEN 1 ELSE 0 END) as kills,
            SUM(CASE WHEN is_corp_loss = 1 THEN total_value ELSE 0 END) as isk_lost
        FROM corp_killmails
    ''')
    
    total, losses, kills, isk_lost = cursor.fetchone()
    
    print(f"\nTotal Killmails: {total:,}")
    print(f"  Losses: {losses:,}")
    print(f"  Kills: {kills:,}")
    print(f"  ISK Lost: {isk_lost:,.0f}")
    
    # Most lost ships
    print("\n" + "-" * 80)
    print("TOP 10 MOST LOST SHIPS")
    print("-" * 80)
    
    cursor.execute('''
        SELECT 
            it.type_name,
            COUNT(*) as times_lost,
            SUM(km.total_value) as total_value
        FROM corp_killmails km
        JOIN inv_types it ON it.type_id = km.ship_type_id
        WHERE km.is_corp_loss = 1
        GROUP BY km.ship_type_id, it.type_name
        ORDER BY times_lost DESC
        LIMIT 10
    ''')
    
    print(f"{'Ship':<40} {'Times Lost':>12} {'Total Value':>20}")
    print("-" * 80)
    for row in cursor.fetchall():
        ship, times, value = row
        print(f"{ship:<40} {times:>12,} {value:>20,.0f} ISK")
    
    # Most lost items
    print("\n" + "-" * 80)
    print("TOP 20 MOST LOST ITEMS")
    print("-" * 80)
    
    cursor.execute('''
        SELECT 
            it.type_name,
            SUM(kmi.quantity) as total_qty
        FROM corp_killmail_items kmi
        JOIN corp_killmails km ON km.killmail_id = kmi.killmail_id
        JOIN inv_types it ON it.type_id = kmi.type_id
        WHERE km.is_corp_loss = 1
          AND kmi.flag != 'Ship'
        GROUP BY kmi.type_id, it.type_name
        ORDER BY total_qty DESC
        LIMIT 20
    ''')
    
    print(f"{'Item':<50} {'Quantity Lost':>15}")
    print("-" * 80)
    for row in cursor.fetchall():
        item, qty = row
        print(f"{item:<50} {qty:>15,}")
    
    print("=" * 80)

# ============================================
# MAIN
# ============================================

@timed_script
def main():
    """
    Fetch corporation/alliance killmails using zKillboard.
    
    This bypasses ESI's member list restrictions!
    """
    
    print("=" * 80)
    print("CORPORATION KILLMAILS VIA ZKILLBOARD")
    print("=" * 80)
    
    # Determine what we're fetching
    if CORPORATION_ID:
        entity_type = "corporation"
        entity_id = CORPORATION_ID
        print(f"\nFetching killmails for Corporation ID: {CORPORATION_ID}")
    elif ALLIANCE_ID:
        entity_type = "alliance"
        entity_id = ALLIANCE_ID
        print(f"\nFetching killmails for Alliance ID: {ALLIANCE_ID}")
    else:
        print("\n[ERROR] Must set either CORPORATION_ID or ALLIANCE_ID")
        return
    
    if MAX_PAGES:
        print(f"Page limit: {MAX_PAGES} pages (~{MAX_PAGES * 200} killmails max)")
    else:
        print(f"Page limit: None (fetching ALL available killmails)")
    
    print(f"\n⚠️  This may take a while...")
    print(f"⚠️  zKillboard rate limit: 1 second between pages")
    
    # Fetch killmails from zKillboard
    zkill_data = get_zkill_killmails(entity_type, entity_id, MAX_PAGES)
    
    if not zkill_data:
        print("\n[WARNING] No killmails found")
        return
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Create tables
        create_killmail_tables(conn)
        
        # Process each killmail
        print(f"\nFetching details for {len(zkill_data):,} killmails from ESI...")
        
        processed = 0
        for i, zkill_km in enumerate(zkill_data, 1):
            killmail_id = zkill_km['killmail_id']
            killmail_hash = zkill_km['zkb']['hash']
            
            # Get full details from ESI
            details = get_killmail_details_from_esi(killmail_id, killmail_hash)
            
            if details:
                store_killmail(conn, killmail_id, details, zkill_km, CORPORATION_ID, ALLIANCE_ID)
                processed += 1
                
                if processed % 100 == 0:
                    print(f"  Processed {processed:,}/{len(zkill_data):,} killmails...", end='\r')
                    conn.commit()
        
        print(f"\n\n[OK] Processed {processed:,} killmails")
        conn.commit()
        
        # Show summary
        show_summary(conn)
        
        print("\n✅ Killmail fetch complete!")
        print("\n💡 Query examples:")
        print("   -- Items your corp commonly loses:")
        print("   SELECT it.type_name, SUM(kmi.quantity) as total")
        print("   FROM corp_killmail_items kmi")
        print("   JOIN corp_killmails km ON km.killmail_id = kmi.killmail_id")
        print("   JOIN inv_types it ON it.type_id = kmi.type_id")
        print("   WHERE km.is_corp_loss = 1")
        print("   GROUP BY kmi.type_id")
        print("   ORDER BY total DESC;")
        
        conn.close()
        
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Saving progress...")
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.commit()
        conn.close()
        raise

if __name__ == '__main__':
    main()