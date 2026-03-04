#!/usr/bin/env python3
"""
Gets a new list of inventory types from ESI and updates
the inv_types table.
"""
import asyncio
import random
import sqlite3
import os
import aiohttp
import requests

# ============================================
# CONFIGURATION
# ============================================

INIT_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(INIT_DIR))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Maximum simultaneous requests to ESI
MAX_CONCURRENCY = 20

# Minimum remaining ESI error-limit budget before we pause
ESI_ERROR_LIMIT_THRESHOLD = 10

# Maximum retry attempts for transient errors
MAX_RETRIES = 5

# ============================================
# ASYNC FETCH FUNCTIONS
# ============================================

def get_all_type_ids():
    """
    Get a list of all type IDs from ESI (synchronous, handles pagination).
    No authentication required.
    """
    all_type_ids = []
    page = 1

    print("Fetching list of all type IDs from ESI...")

    while True:
        response = requests.get(
            f'{ESI_BASE_URL}/universe/types/',
            params={'page': page},
        )

        if response.status_code == 200:
            page_ids = response.json()
            if not page_ids:
                break
            all_type_ids.extend(page_ids)

            total_pages = int(response.headers.get('X-Pages', 1))
            print(f"  Page {page}/{total_pages}: {len(page_ids)} IDs (total: {len(all_type_ids)})")
            if page >= total_pages:
                break
            page += 1
        else:
            print(f"Error fetching type IDs page {page}: {response.status_code}")
            break

    print(f"\nTotal type IDs found: {len(all_type_ids)}")
    return all_type_ids


async def fetch_type(session, semaphore, type_id):
    """
    Fetch a single type from ESI with bounded concurrency,
    ESI error-limit monitoring, and exponential back-off + jitter.
    Returns the parsed JSON dict, or None on persistent failure.
    """
    url = f'{ESI_BASE_URL}/universe/types/{type_id}/'
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
                        return await response.json()

                    if response.status in retryable:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        print(
                            f"  [HTTP {response.status}] type {type_id} "
                            f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Non-retryable (e.g. 404 for unpublished/invalid types) – silent skip
                    return None

            except aiohttp.ClientError as exc:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(
                    f"  [ClientError] type {type_id}: {exc} "
                    f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                )
                await asyncio.sleep(wait)

    print(f"  [FAILED] type {type_id} \u2013 exceeded max retries")
    return None


async def fetch_all_types(type_ids):
    """
    Fetch all types concurrently, honouring MAX_CONCURRENCY.
    Returns a list of data dicts for successful fetches.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    total = len(type_ids)
    results = []
    completed = 0

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.ensure_future(fetch_type(session, semaphore, tid))
            for tid in type_ids
        ]

        for coro in asyncio.as_completed(tasks):
            data = await coro
            completed += 1

            if completed % 500 == 0:
                print(f"  Progress: {completed}/{total} types fetched...")

            if data:
                results.append(data)

    print(f"  Fetched {len(results)}/{total} types successfully.")
    return results

# ============================================
# DATABASE FUNCTIONS
# ============================================

def bulk_insert_types(conn, types):
    """
    Insert all types in a single executemany() call.
    """
    rows = [
        (
            t['type_id'],
            t.get('group_id'),
            t['name'],
            t.get('description'),
            t.get('mass'),
            t.get('volume'),
            t.get('capacity'),
            t.get('portion_size'),
            t.get('race_id'),
            t.get('base_price'),
            t.get('published', 0),
            t.get('market_group_id'),
            t.get('icon_id'),
            t.get('sound_id'),
            t.get('graphic_id'),
        )
        for t in types
    ]

    cursor = conn.cursor()
    cursor.executemany(
        '''
        INSERT OR REPLACE INTO inv_types (
            type_id, group_id, type_name, description, mass, volume,
            capacity, portion_size, race_id, base_price, published,
            market_group_id, icon_id, sound_id, graphic_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        rows,
    )
    return len(rows)

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting inv_types update from ESI")
    print("=" * 50)

    # Step 1: Fetch all type IDs (paginated, synchronous)
    type_ids = get_all_type_ids()

    if not type_ids:
        print("No type IDs found. Exiting.")
        return

    # Step 2: Fetch all type details in parallel
    print(f"\nFetching type details (concurrency={MAX_CONCURRENCY})...")
    types = asyncio.run(fetch_all_types(type_ids))

    if not types:
        print("No type data retrieved. Exiting.")
        return

    # Step 3: Bulk-insert into SQLite
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    print("Inserting type data...")
    inserted = bulk_insert_types(conn, types)

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("inv_types update complete!")
    print(f"Total type IDs checked: {len(type_ids)}")
    print(f"Successfully inserted/replaced: {inserted}")
    print("=" * 50)


if __name__ == '__main__':
    main()