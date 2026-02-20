#!/usr/bin/env python3
"""
Pulls the corporation mining ledger from ESI and stores it.

ESI endpoints used:
  GET /corporation/{corporation_id}/mining/observers/
      -> list of refineries (observer_id + last_updated)
  GET /corporation/{corporation_id}/mining/observers/{observer_id}/
      -> paginated mining events per refinery

Required scope: esi-industry.read_corporation_mining.v1
Required role:  Accountant (or Director/CEO)
Cache:          1 hour (no point running more often than that)
History:        ESI returns ~30 days of events per observer
"""

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
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Corporation ID that owns the refineries
CORPORATION_ID = 98814441  # <-- UPDATE THIS to your corp ID

# ============================================
# ESI HELPERS
# ============================================

def get_observers(corporation_id, token):
    """
    GET /corporation/{corporation_id}/mining/observers/
    Returns list of dicts: { observer_id, last_updated }
    These are the refineries that have mining ledger entries.
    """
    url = f'{ESI_BASE_URL}/corporation/{corporation_id}/mining/observers/'
    headers = {'Authorization': f'Bearer {token}'}

    print(f"  Fetching observers for corp {corporation_id}...")
    resp = requests.get(url, headers=headers)

    if resp.status_code == 200:
        observers = resp.json()
        print(f"  Found {len(observers)} observer(s)")
        return observers
    else:
        print(f"  ERROR {resp.status_code}: {resp.text}")
        return []


def get_mining_ledger(corporation_id, observer_id, token):
    """
    GET /corporation/{corporation_id}/mining/observers/{observer_id}/
    Paginated.  Pulls every page until ESI stops returning results.
    Returns flat list of raw event dicts from ESI.
    """
    url     = f'{ESI_BASE_URL}/corporation/{corporation_id}/mining/observers/{observer_id}/'
    headers = {'Authorization': f'Bearer {token}'}
    all_events = []
    page = 1

    while True:
        resp = requests.get(url, headers=headers, params={'page': page})

        if resp.status_code == 200:
            events = resp.json()
            if not events:
                break                       # empty page = end of data
            all_events.extend(events)
            print(f"    page {page}: {len(events)} events")

            # ESI paginates in chunks of 1000; if we got a full page keep going
            if len(events) < 1000:
                break
            page += 1
        elif resp.status_code == 304:
            print(f"    304 Not Modified — no new data")
            break
        else:
            print(f"    ERROR {resp.status_code} on page {page}: {resp.text}")
            break

    return all_events


# ============================================
# DATABASE
# ============================================

def upsert_events(conn, observer_id, events, fetched_at):
    """
    Insert mining events.  Uses INSERT OR IGNORE against the UNIQUE constraint
    so that re-running the script is safe — existing rows are untouched,
    genuinely new events are appended.
    """
    cursor = conn.cursor()

    cursor.executemany('''
        INSERT OR IGNORE INTO corp_mining_ledger (
            observer_id,
            character_id,
            recorded_corporation_id,
            type_id,
            quantity,
            last_updated,
            fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [
        (
            observer_id,
            ev['character_id'],
            ev['recorded_corporation_id'],
            ev['type_id'],
            ev['quantity'],
            ev['last_updated'],          # raw date string from ESI
            fetched_at
        )
        for ev in events
    ])

    return cursor.rowcount          # number actually inserted (skips duplicates)


# ============================================
# MAIN
# ============================================

@timed_script
def main():
    print("=" * 60)
    print("CORPORATION MINING LEDGER UPDATE")
    print("=" * 60)

    # ---- token ----
    print("\nGetting access token...")
    token = get_token()

    # ---- observers ----
    print("\nStep 1: Get list of refineries (observers)...")
    observers = get_observers(CORPORATION_ID, token)
    if not observers:
        print("No observers returned — nothing to do.")
        return

    # ---- connect DB ----
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=30)

    fetched_at = datetime.now(timezone.utc).isoformat()
    total_new  = 0

    # ---- per-observer pull ----
    print("\nStep 2: Pull mining ledger for each refinery...")
    for obs in observers:
        observer_id  = obs['observer_id']
        last_updated = obs.get('last_updated', 'unknown')
        print(f"\n  Observer {observer_id}  (last_updated: {last_updated})")

        events = get_mining_ledger(CORPORATION_ID, observer_id, token)

        if events:
            inserted = upsert_events(conn, observer_id, events, fetched_at)
            print(f"    -> {inserted} new row(s) inserted  ({len(events)} total from ESI)")
            total_new += inserted
        else:
            print(f"    -> no events")

    # ---- commit ----
    conn.commit()

    # ---- summary ----
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM corp_mining_ledger")
    total_rows = cursor.fetchone()[0]
    conn.close()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  New rows inserted : {total_new}")
    print(f"  Total rows in table: {total_rows}")
    print(f"  Fetched at         : {fetched_at}")
    print("=" * 60)


if __name__ == '__main__':
    main()