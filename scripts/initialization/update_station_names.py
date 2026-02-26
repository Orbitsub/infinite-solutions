#!/usr/bin/env python3
"""
Gets station and structure names from ESI and updates the stations table.
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

INIT_DIR    = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(INIT_DIR)
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

from script_utils import timed_script

DB_PATH      = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Maximum simultaneous requests to ESI
MAX_CONCURRENCY = 20

# Minimum remaining ESI error-limit budget before we pause
ESI_ERROR_LIMIT_THRESHOLD = 10

# Maximum retry attempts for transient errors
MAX_RETRIES = 5

# ============================================
# CREATE TABLE
# ============================================

def create_stations_table(conn):
    """Create table for station/structure names if it doesn't exist."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stations (
            location_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            last_updated TEXT
        )
    ''')
    conn.commit()

# ============================================
# ASYNC FETCH FUNCTIONS
# ============================================

async def fetch_station(session, semaphore, location_id):
    """
    Fetch a single station or structure name from ESI with bounded concurrency,
    ESI error-limit monitoring, and exponential back-off + jitter.
    Returns (location_id, name, station_type).
    """
    retryable = {420, 429, 500, 502, 503, 504}

    # NPC stations use a different endpoint to player structures
    if location_id < 70000000:
        urls = [(f'{ESI_BASE_URL}/universe/stations/{location_id}/', 'NPC Station')]
    else:
        urls = [(f'{ESI_BASE_URL}/universe/structures/{location_id}/', 'Player Structure')]

    async with semaphore:
        for url, station_type in urls:
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
                            return location_id, data.get('name'), station_type

                        if response.status == 403:
                            # Structure exists but we lack access to its name
                            return location_id, f'Private Structure {location_id}', 'Private Structure'

                        if response.status in retryable:
                            wait = (2 ** attempt) + random.uniform(0, 1)
                            print(
                                f"  [HTTP {response.status}] location {location_id} "
                                f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                            )
                            await asyncio.sleep(wait)
                            continue

                        # Non-retryable failure
                        return location_id, f'Unknown Location {location_id}', 'Unknown'

                except aiohttp.ClientError as exc:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    print(
                        f"  [ClientError] location {location_id}: {exc} "
                        f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)

    print(f"  [FAILED] location {location_id} \u2013 exceeded max retries")
    return location_id, f'Unknown Location {location_id}', 'Unknown'


async def fetch_all_stations(location_ids):
    """Fetch all station/structure names concurrently, honouring MAX_CONCURRENCY."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    total = len(location_ids)
    results = []
    completed = 0

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.ensure_future(fetch_station(session, semaphore, lid))
            for lid in location_ids
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1
            if completed % 10 == 0 or completed == total:
                print(f"  Progress: {completed}/{total} ({completed/total*100:.1f}%)")
            results.append(result)

    print(f"  Fetched {len(results)}/{total} stations successfully.")
    return results

# ============================================
# DATABASE FUNCTIONS
# ============================================

def bulk_insert_stations(conn, rows):
    """Insert all station rows in a single executemany() call."""
    cursor = conn.cursor()
    cursor.executemany(
        '''
        INSERT OR REPLACE INTO stations (location_id, name, type, last_updated)
        VALUES (?, ?, ?, ?)
        ''',
        rows,
    )
    return len(rows)

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    print("=" * 60)
    print("STATION NAMES UPDATE")
    print("=" * 60)

    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=30)

    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    # Create table if needed
    create_stations_table(conn)

    # Get all unique location IDs from market orders
    print("\nGetting unique station IDs from market orders...")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT location_id
        FROM market_orders
        WHERE region_id = 10000002
        ORDER BY location_id
    ''')
    location_ids = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(location_ids)} unique stations/structures")

    # Check which ones we already have
    cursor.execute('SELECT location_id FROM stations')
    existing = {row[0] for row in cursor.fetchall()}

    to_fetch = [lid for lid in location_ids if lid not in existing]
    print(f"Already have {len(existing)} station names")
    print(f"Need to fetch {len(to_fetch)} new station names")

    if not to_fetch:
        print("\nAll station names are up to date!")
        conn.close()
        return

    # Fetch all names concurrently
    print(f"\nFetching station names from ESI (concurrency={MAX_CONCURRENCY})...")
    current_time = datetime.now(timezone.utc).isoformat()
    fetched = asyncio.run(fetch_all_stations(to_fetch))

    # Build rows for bulk insert
    rows = [(lid, name, stype, current_time) for lid, name, stype in fetched]

    # Bulk-insert into SQLite
    print("\nSaving to database...")
    inserted = bulk_insert_stations(conn, rows)
    conn.commit()
    conn.close()

    success_count = sum(1 for _, _, t in fetched if t not in ('Private Structure', 'Unknown'))
    private_count = sum(1 for _, _, t in fetched if t == 'Private Structure')
    error_count   = sum(1 for _, _, t in fetched if t == 'Unknown')

    print("\n" + "=" * 60)
    print("STATION NAMES UPDATE COMPLETE")
    print("=" * 60)
    print(f"Successfully fetched: {success_count}")
    print(f"Private structures:   {private_count}")
    print(f"Errors/unknown:       {error_count}")
    print(f"Total inserted/replaced: {inserted}")
    print("=" * 60)


if __name__ == '__main__':
    main()
