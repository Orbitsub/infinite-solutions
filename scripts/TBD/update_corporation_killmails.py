"""
==========================================
UPDATE COMPLETE KILLMAIL DATA (INCREMENTAL)
==========================================
Fetches only NEW killmails and stores ALL raw fields.

Run this regularly to keep data current.
==========================================
"""

from script_utils import timed_script
import requests
import sqlite3
import os
import sys
from datetime import datetime, timezone
import time
import json

TBD_DIR     = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(TBD_DIR)
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

# ============================================
# CONFIGURATION
# ============================================

sys.path.insert(0, os.path.join(PROJECT_DIR, 'config'))
from setup import CORPORATION_ID, ALLIANCE_ID

MAX_PAGES = 3  # Check last 3 pages for new killmails

DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'
ZKILLBOARD_BASE_URL = 'https://zkillboard.com/api'
DELAY_BETWEEN_PAGES = 1.0

# ============================================
# FUNCTIONS
# ============================================

def killmail_exists(conn, killmail_id):
    """Check if killmail already exists."""
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM raw_killmails WHERE killmail_id = ?', (killmail_id,))
    return cursor.fetchone() is not None

def get_zkill_killmails(entity_type, entity_id, max_pages=3):
    """Get recent killmails from zKillboard."""
    all_killmails = []
    page = 1
    
    headers = {
        'User-Agent': 'EVE Market Trading Tool / contact: your_email@example.com'
    }
    
    while page <= max_pages:
        if entity_type == "corporation":
            url = f'{ZKILLBOARD_BASE_URL}/corporationID/{entity_id}/page/{page}/'
        else:
            url = f'{ZKILLBOARD_BASE_URL}/allianceID/{entity_id}/page/{page}/'
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            killmails = response.json()
            if not killmails:
                break
            all_killmails.extend(killmails)
            page += 1
            time.sleep(DELAY_BETWEEN_PAGES)
        else:
            break
    
    return all_killmails

def get_killmail_details_from_esi(killmail_id, killmail_hash):
    """Get full killmail from ESI."""
    url = f'{ESI_BASE_URL}/killmails/{killmail_id}/{killmail_hash}/'
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def store_complete_killmail(conn, zkb_km, esi_km):
    """Store complete killmail with ALL fields."""
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    killmail_id = zkb_km['killmail_id']
    zkb = zkb_km.get('zkb', {})
    
    # Main killmail
    cursor.execute('''
        INSERT OR REPLACE INTO raw_killmails (
            killmail_id, killmail_time, solar_system_id, moon_id, war_id,
            zkb_location_id, zkb_hash, zkb_fitted_value, zkb_dropped_value,
            zkb_destroyed_value, zkb_total_value, zkb_points, zkb_npc,
            zkb_solo, zkb_awox, zkb_labels, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        killmail_id,
        esi_km['killmail_time'],
        esi_km['solar_system_id'],
        esi_km.get('moon_id'),
        esi_km.get('war_id'),
        zkb.get('locationID'),
        zkb.get('hash'),
        zkb.get('fittedValue'),
        zkb.get('droppedValue'),
        zkb.get('destroyedValue'),
        zkb.get('totalValue'),
        zkb.get('points'),
        1 if zkb.get('npc') else 0,
        1 if zkb.get('solo') else 0,
        1 if zkb.get('awox') else 0,
        json.dumps(zkb.get('labels', [])),
        current_time
    ))
    
    # Victim
    victim = esi_km.get('victim', {})
    position = victim.get('position', {})
    
    cursor.execute('''
        INSERT OR REPLACE INTO raw_killmail_victims (
            killmail_id, character_id, corporation_id, alliance_id, faction_id,
            ship_type_id, damage_taken, position_x, position_y, position_z
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        killmail_id,
        victim.get('character_id'),
        victim.get('corporation_id'),
        victim.get('alliance_id'),
        victim.get('faction_id'),
        victim.get('ship_type_id'),
        victim.get('damage_taken'),
        position.get('x'),
        position.get('y'),
        position.get('z')
    ))
    
    # Attackers
    cursor.execute('DELETE FROM raw_killmail_attackers WHERE killmail_id = ?', (killmail_id,))
    
    for attacker in esi_km.get('attackers', []):
        cursor.execute('''
            INSERT INTO raw_killmail_attackers (
                killmail_id, character_id, corporation_id, alliance_id, faction_id,
                ship_type_id, weapon_type_id, damage_done, final_blow, security_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            killmail_id,
            attacker.get('character_id'),
            attacker.get('corporation_id'),
            attacker.get('alliance_id'),
            attacker.get('faction_id'),
            attacker.get('ship_type_id'),
            attacker.get('weapon_type_id'),
            attacker.get('damage_done', 0),
            1 if attacker.get('final_blow') else 0,
            attacker.get('security_status')
        ))
    
    # Items
    cursor.execute('DELETE FROM raw_killmail_items WHERE killmail_id = ?', (killmail_id,))
    
    for item in victim.get('items', []):
        cursor.execute('''
            INSERT INTO raw_killmail_items (
                killmail_id, item_type_id, flag, quantity_destroyed,
                quantity_dropped, singleton
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            killmail_id,
            item['item_type_id'],
            item['flag'],
            item.get('quantity_destroyed', 0),
            item.get('quantity_dropped', 0),
            item.get('singleton', 0)
        ))

# ============================================
# MAIN
# ============================================

@timed_script
def main():
    """Incremental update - only fetch NEW killmails."""
    
    print("=" * 80)
    print("UPDATE COMPLETE KILLMAIL DATA (INCREMENTAL)")
    print("=" * 80)
    
    if CORPORATION_ID:
        entity_type = "corporation"
        entity_id = CORPORATION_ID
        print(f"\nCorporation ID: {CORPORATION_ID}")
    elif ALLIANCE_ID:
        entity_type = "alliance"
        entity_id = ALLIANCE_ID
        print(f"\nAlliance ID: {ALLIANCE_ID}")
    else:
        print("\n[ERROR] Must set CORPORATION_ID or ALLIANCE_ID")
        return
    
    print(f"Checking last {MAX_PAGES} pages...")
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Check tables exist
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='raw_killmails'
        """)
        
        if not cursor.fetchone():
            print("\n[ERROR] Tables don't exist!")
            print("Run create_complete_killmail_schema.py first")
            conn.close()
            return
        
        # Fetch recent killmails
        print("\nFetching recent killmails from zKillboard...")
        zkill_data = get_zkill_killmails(entity_type, entity_id, MAX_PAGES)
        
        if not zkill_data:
            print("\n[WARNING] No killmails found")
            conn.close()
            return
        
        print(f"Found {len(zkill_data):,} killmails on zKillboard")
        
        # Filter to new only
        print("\nChecking for new killmails...")
        new_killmails = []
        skipped = 0
        
        for zkb_km in zkill_data:
            if killmail_exists(conn, zkb_km['killmail_id']):
                skipped += 1
            else:
                new_killmails.append(zkb_km)
        
        print(f"  New: {len(new_killmails):,}")
        print(f"  Already have: {skipped:,}")
        
        if not new_killmails:
            print("\n[OK] No new killmails - database is up to date!")
            conn.close()
            return
        
        # Fetch and store new killmails
        print(f"\nStoring {len(new_killmails):,} new killmails...")
        
        processed = 0
        for zkb_km in new_killmails:
            killmail_id = zkb_km['killmail_id']
            killmail_hash = zkb_km['zkb']['hash']
            
            esi_km = get_killmail_details_from_esi(killmail_id, killmail_hash)
            
            if esi_km:
                store_complete_killmail(conn, zkb_km, esi_km)
                processed += 1
                
                if processed % 50 == 0:
                    print(f"  {processed}/{len(new_killmails)}...", end='\r')
                    conn.commit()
        
        print(f"\n\n[OK] Added {processed:,} new killmails")
        conn.commit()
        
        # Summary
        cursor.execute('SELECT COUNT(*) FROM raw_killmails')
        total = cursor.fetchone()[0]
        
        print("\n" + "=" * 80)
        print("UPDATE COMPLETE")
        print("=" * 80)
        print(f"New killmails: {processed:,}")
        print(f"Total in database: {total:,}")
        print("=" * 80)
        
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        conn.commit()
        conn.close()
        raise

if __name__ == '__main__':
    main()