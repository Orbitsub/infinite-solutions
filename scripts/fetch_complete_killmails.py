"""
==========================================
FETCH COMPLETE KILLMAIL DATA (RAW)
==========================================
Fetches ALL killmails for your corporation and stores
EVERY field from zKillboard and ESI with NO transformations.

This is the complete data fetch - no filtering, no transformations.
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# ============================================
# CONFIGURATION
# ============================================

sys.path.insert(0, os.path.join(PROJECT_DIR, 'config'))
from setup import CORPORATION_ID, ALLIANCE_ID

# How many pages to fetch (None = all available)
MAX_PAGES = None

# Database location
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

# API endpoints
ESI_BASE_URL = 'https://esi.evetech.net/latest'
ZKILLBOARD_BASE_URL = 'https://zkillboard.com/api'

# Rate limiting
DELAY_BETWEEN_PAGES = 1.0

# ============================================
# FUNCTIONS
# ============================================

def get_zkill_killmails(entity_type, entity_id, max_pages=None):
    """Get killmails from zKillboard."""
    
    all_killmails = []
    page = 1
    
    print(f"\nFetching killmails from zKillboard...")
    
    headers = {
        'User-Agent': 'EVE Market Trading Tool / contact: your_email@example.com'
    }
    
    while True:
        if entity_type == "corporation":
            url = f'{ZKILLBOARD_BASE_URL}/corporationID/{entity_id}/page/{page}/'
        else:
            url = f'{ZKILLBOARD_BASE_URL}/allianceID/{entity_id}/page/{page}/'
        
        print(f"  Fetching page {page}...", end='\r')
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            killmails = response.json()
            
            if not killmails:
                break
            
            all_killmails.extend(killmails)
            print(f"  Page {page}: {len(killmails)} killmails (total: {len(all_killmails):,})")
            
            page += 1
            
            if max_pages and page > max_pages:
                break
            
            time.sleep(DELAY_BETWEEN_PAGES)
            
        else:
            print(f"\n  Error: {response.status_code}")
            break
    
    print(f"\nTotal killmails fetched: {len(all_killmails):,}")
    return all_killmails

def get_killmail_details_from_esi(killmail_id, killmail_hash):
    """Get full killmail details from ESI."""
    url = f'{ESI_BASE_URL}/killmails/{killmail_id}/{killmail_hash}/'
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def store_complete_killmail(conn, zkb_km, esi_km):
    """
    Store complete killmail with ALL fields.
    
    Parameters:
    - conn: Database connection
    - zkb_km: Raw zKillboard response
    - esi_km: Raw ESI killmail response
    """
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    killmail_id = zkb_km['killmail_id']
    zkb = zkb_km.get('zkb', {})
    
    # ============================================
    # TABLE 1: MAIN KILLMAIL
    # ============================================
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
    
    # ============================================
    # TABLE 2: VICTIM
    # ============================================
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
    
    # ============================================
    # TABLE 3: ATTACKERS
    # ============================================
    # Delete existing attackers first
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
    
    # ============================================
    # TABLE 4: ITEMS
    # ============================================
    # Delete existing items first
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

def show_summary(conn):
    """Show summary of stored killmails."""
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("KILLMAIL SUMMARY")
    print("=" * 80)
    
    cursor.execute('SELECT COUNT(*) FROM raw_killmails')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM raw_killmail_attackers')
    total_attackers = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM raw_killmail_items')
    total_items = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(zkb_total_value) FROM raw_killmails')
    total_value = cursor.fetchone()[0] or 0
    
    cursor.execute('''
        SELECT COUNT(*) 
        FROM raw_killmails km
        JOIN raw_killmail_victims v ON v.killmail_id = km.killmail_id
        WHERE v.corporation_id = ?
    ''', (CORPORATION_ID if CORPORATION_ID else ALLIANCE_ID,))
    losses = cursor.fetchone()[0]
    
    print(f"\nTotal Killmails: {total:,}")
    print(f"  Losses: {losses:,}")
    print(f"  Kills: {total - losses:,}")
    print(f"\nTotal Attackers Stored: {total_attackers:,}")
    print(f"Total Items Stored: {total_items:,}")
    print(f"Total ISK Value: {total_value:,.0f}")
    
    # Solo vs fleet
    cursor.execute('SELECT COUNT(*) FROM raw_killmails WHERE zkb_solo = 1')
    solo = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM raw_killmails WHERE zkb_npc = 1')
    npc = cursor.fetchone()[0]
    
    print(f"\nSolo Kills: {solo:,}")
    print(f"NPC Kills: {npc:,}")
    
    print("=" * 80)

# ============================================
# MAIN
# ============================================

@timed_script
def main():
    """
    Fetch complete killmail data with ALL fields.
    """
    
    print("=" * 80)
    print("FETCH COMPLETE KILLMAIL DATA (RAW)")
    print("=" * 80)
    
    # Determine entity
    if CORPORATION_ID:
        entity_type = "corporation"
        entity_id = CORPORATION_ID
        print(f"\nCorporation ID: {CORPORATION_ID}")
    elif ALLIANCE_ID:
        entity_type = "alliance"
        entity_id = ALLIANCE_ID
        print(f"\nAlliance ID: {ALLIANCE_ID}")
    else:
        print("\n[ERROR] Must set either CORPORATION_ID or ALLIANCE_ID")
        return
    
    if MAX_PAGES:
        print(f"Page limit: {MAX_PAGES}")
    else:
        print(f"Page limit: None (fetching ALL)")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Check if tables exist
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
        
        # Fetch killmails from zKillboard
        zkill_data = get_zkill_killmails(entity_type, entity_id, MAX_PAGES)
        
        if not zkill_data:
            print("\n[WARNING] No killmails found")
            conn.close()
            return
        
        # Process each killmail
        print(f"\nFetching details and storing {len(zkill_data):,} killmails...")
        
        processed = 0
        failed = 0
        
        for i, zkb_km in enumerate(zkill_data, 1):
            killmail_id = zkb_km['killmail_id']
            killmail_hash = zkb_km['zkb']['hash']
            
            # Get full details from ESI
            esi_km = get_killmail_details_from_esi(killmail_id, killmail_hash)
            
            if esi_km:
                store_complete_killmail(conn, zkb_km, esi_km)
                processed += 1
                
                if processed % 100 == 0:
                    print(f"  Processed {processed:,}/{len(zkill_data):,} killmails...", end='\r')
                    conn.commit()
            else:
                failed += 1
        
        print(f"\n\n[OK] Processed {processed:,} killmails")
        if failed > 0:
            print(f"[WARNING] Failed to fetch {failed:,} killmails")
        
        conn.commit()
        
        # Show summary
        show_summary(conn)
        
        print("\n✅ Complete killmail data stored!")
        print("\n💡 All fields from zKillboard and ESI are now in your database")
        print("💡 Use SQL queries to analyze the raw data as needed")
        
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