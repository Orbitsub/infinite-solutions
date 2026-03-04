#!/usr/bin/env python3
"""
Gets a new list of meta groups from ESI and updates
the inv_meta_groups table.
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

def get_all_meta_group_ids():
    """
    ESI has no direct meta groups endpoint; use the known static IDs.
    Meta groups correspond to T1, T2, Faction, Deadspace, Officer, etc.
    and are rarely updated by CCP.
    """
    meta_group_ids = [1, 2, 3, 4, 5, 6, 14, 15, 17, 19, 52, 53]
    print(f"Using {len(meta_group_ids)} known meta group IDs")
    return meta_group_ids


async def fetch_meta_group(session, semaphore, meta_group_id):
    """
    Fetch a single meta group from the dogma attributes endpoint with
    bounded concurrency, ESI error-limit monitoring, and back-off + jitter.
    Returns a transformed dict suitable for the inv_meta_groups table,
    or None on persistent failure.
    """
    url = f'{ESI_BASE_URL}/dogma/attributes/{meta_group_id}/'
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
                        return {
                            'meta_group_id':   data['attribute_id'],
                            'meta_group_name': data.get(
                                'display_name',
                                data.get('name', f'Meta Group {meta_group_id}')
                            ),
                            'description': data.get('description'),
                            'icon_id':     data.get('icon_id'),
                        }

                    if response.status in retryable:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        print(
                            f"  [HTTP {response.status}] meta_group {meta_group_id} "
                            f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                        )
                        await asyncio.sleep(wait)
                        continue

                    print(
                        f"  [HTTP {response.status}] meta_group {meta_group_id} "
                        f"\u2013 skipping (non-retryable)"
                    )
                    return None

            except aiohttp.ClientError as exc:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(
                    f"  [ClientError] meta_group {meta_group_id}: {exc} "
                    f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                )
                await asyncio.sleep(wait)

    print(f"  [FAILED] meta_group {meta_group_id} \u2013 exceeded max retries")
    return None


async def fetch_all_meta_groups(meta_group_ids):
    """
    Fetch all meta groups concurrently, honouring MAX_CONCURRENCY.
    Returns a list of data dicts for successful fetches.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    total = len(meta_group_ids)
    results = []
    completed = 0

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.ensure_future(fetch_meta_group(session, semaphore, mgid))
            for mgid in meta_group_ids
        ]

        for coro in asyncio.as_completed(tasks):
            data = await coro
            completed += 1

            if data:
                results.append(data)

    print(f"  Fetched {len(results)}/{total} meta groups successfully.")
    return results

# ============================================
# DATABASE FUNCTIONS
# ============================================

def bulk_insert_meta_groups(conn, meta_groups):
    """
    Insert all meta groups in a single executemany() call.
    """
    rows = [
        (
            mg['meta_group_id'],
            mg['meta_group_name'],
            mg.get('description'),
            mg.get('icon_id'),
        )
        for mg in meta_groups
    ]

    cursor = conn.cursor()
    cursor.executemany(
        '''
        INSERT OR REPLACE INTO inv_meta_groups (
            meta_group_id, meta_group_name, description, icon_id
        ) VALUES (?, ?, ?, ?)
        ''',
        rows,
    )
    return len(rows)

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting inv_meta_groups update from ESI")
    print("=" * 50)

    meta_group_ids = get_all_meta_group_ids()

    if not meta_group_ids:
        print("No meta group IDs found. Exiting.")
        return

    # Fetch all meta group details in parallel
    print(f"\nFetching meta group details (concurrency={MAX_CONCURRENCY})...")
    meta_groups = asyncio.run(fetch_all_meta_groups(meta_group_ids))

    if not meta_groups:
        print("No meta group data retrieved. Exiting.")
        return

    # Bulk-insert into SQLite
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    print("Inserting meta group data...")
    inserted = bulk_insert_meta_groups(conn, meta_groups)

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("inv_meta_groups update complete!")
    print(f"Total meta groups inserted/replaced: {inserted}")
    print("=" * 50)


if __name__ == '__main__':
    main()