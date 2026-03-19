#!/usr/bin/env python3
"""
Gets universe entity data from ESI and updates the universe_entities table.
"""
import asyncio
import os
import random
import sqlite3
import sys
from datetime import datetime, timezone

import aiohttp
import requests

# ============================================
# CONFIGURATION
# ============================================

INIT_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR  = os.path.dirname(os.path.dirname(INIT_DIR))
DB_PATH      = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Maximum simultaneous requests to ESI
MAX_CONCURRENCY = 20

# Minimum remaining ESI error-limit budget before we pause
ESI_ERROR_LIMIT_THRESHOLD = 10

# Maximum retry attempts for transient errors
MAX_RETRIES = 5

# Key entities for Jita/High-sec trading
FACTIONS_TO_FETCH = [500001, 500002, 500003, 500004]  # Cal, Min, Amarr, Gal
CORPORATIONS_TO_FETCH = [
    1000035,  # Caldari Navy
    1000125,  # Minmatar Fleet
    1000182,  # Imperial Navy
    1000127,  # Federal Navy
]

# ============================================
# SYNC FETCH FUNCTIONS
# ============================================

def fetch_all_factions():
    """Fetch all factions from ESI (synchronous, single-page endpoint)."""
    url = f'{ESI_BASE_URL}/universe/factions/'
    print("Fetching all factions from ESI...")

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print(f"  Found {len(data)} factions.")
        return data
    else:
        print(f"  Error fetching factions: {response.status_code}")
        return []

# ============================================
# ASYNC FETCH FUNCTIONS
# ============================================

async def fetch_corporation(session, semaphore, corp_id):
    """
    Fetch a single corporation from ESI with bounded concurrency,
    ESI error-limit monitoring, and exponential back-off + jitter.
    Returns (corp_id, parsed JSON dict) or (corp_id, None) on failure.
    """
    url = f'{ESI_BASE_URL}/corporations/{corp_id}/'
    retryable = {420, 429, 500, 502, 503, 504}

    async with semaphore:
        for attempt in range(MAX_RETRIES):
            await asyncio.sleep(random.uniform(0, 0.05))

            try:
                async with session.get(url) as response:
                    # ESI error-limit monitoring
                    remain = int(response.headers.get('X-ESI-Error-Limit-Remain', 100))
                    reset  = int(response.headers.get('X-ESI-Error-Limit-Reset', 60))

                    if remain < ESI_ERROR_LIMIT_THRESHOLD:
                        print(
                            f"  [ESI] Error budget low ({remain} remaining). "
                            f"Pausing {reset}s..."
                        )
                        await asyncio.sleep(reset)

                    if response.status == 200:
                        data = await response.json()
                        return corp_id, data

                    if response.status in retryable:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        print(
                            f"  [HTTP {response.status}] corp {corp_id} "
                            f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Non-retryable (e.g. 404) - silent skip
                    print(f"  [HTTP {response.status}] corp {corp_id} \u2013 skipping")
                    return corp_id, None

            except aiohttp.ClientError as exc:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(
                    f"  [ClientError] corp {corp_id}: {exc} "
                    f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                )
                await asyncio.sleep(wait)

    print(f"  [FAILED] corp {corp_id} \u2013 exceeded max retries")
    return corp_id, None


async def fetch_all_corporations(corp_ids):
    """Fetch all corporations concurrently, honouring MAX_CONCURRENCY."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    results = {}

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.ensure_future(fetch_corporation(session, semaphore, cid))
            for cid in corp_ids
        ]
        for coro in asyncio.as_completed(tasks):
            corp_id, data = await coro
            if data:
                results[corp_id] = data

    print(f"  Fetched {len(results)}/{len(corp_ids)} corporations successfully.")
    return results

# ============================================
# DATABASE FUNCTIONS
# ============================================

def bulk_insert_entities(conn, rows):
    """Insert all entity rows in a single executemany() call."""
    cursor = conn.cursor()
    cursor.executemany(
        '''
        INSERT OR REPLACE INTO universe_entities (
            entity_id, entity_type, entity_name, description, ticker, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''',
        rows,
    )
    return len(rows)

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting universe entities update")
    print("=" * 50)

    current_time = datetime.now(timezone.utc).isoformat()
    rows = []

    # Step 1: Fetch factions (synchronous single-page endpoint)
    factions = fetch_all_factions()
    for faction in factions:
        rows.append((
            faction['faction_id'],
            'faction',
            faction['name'],
            faction.get('description'),
            None,
            current_time,
        ))

    # Step 2: Fetch corporations concurrently
    print(f"\nFetching {len(CORPORATIONS_TO_FETCH)} corporations "
          f"(concurrency={MAX_CONCURRENCY})...")
    corp_data = asyncio.run(fetch_all_corporations(CORPORATIONS_TO_FETCH))
    for corp_id, data in corp_data.items():
        rows.append((
            corp_id,
            'corporation',
            data['name'],
            data.get('description'),
            data.get('ticker'),
            current_time,
        ))
        print(f"  Added corporation: {data['name']} [{data.get('ticker')}]")

    if not rows:
        print("No entity data retrieved. Exiting.")
        return

    # Step 3: Bulk-insert into SQLite
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    print("Inserting entity data...")
    inserted = bulk_insert_entities(conn, rows)

    conn.commit()
    conn.close()

    faction_count = sum(1 for r in rows if r[1] == 'faction')
    corp_count    = sum(1 for r in rows if r[1] == 'corporation')

    print("\n" + "=" * 50)
    print("Universe entities update complete!")
    print(f"Factions inserted: {faction_count}")
    print(f"Corporations inserted: {corp_count}")
    print(f"Total rows inserted/replaced: {inserted}")
    print("=" * 50)


if __name__ == '__main__':
    main()
