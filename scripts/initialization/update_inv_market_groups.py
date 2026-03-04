#!/usr/bin/env python3
"""
Gets a new list of market groups from ESI and updates
the inv_market_groups table.
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

def get_all_market_group_ids():
    """
    Get a list of all market group IDs from ESI (synchronous – single call).
    No authentication required.
    """
    url = f'{ESI_BASE_URL}/markets/groups/'

    print("Fetching list of all market group IDs from ESI...")
    response = requests.get(url)

    if response.status_code == 200:
        market_group_ids = response.json()
        print(f"Found {len(market_group_ids)} market group IDs")
        return market_group_ids
    else:
        print(f"Error fetching market group IDs: {response.status_code}")
        return []


async def fetch_market_group(session, semaphore, market_group_id):
    """
    Fetch a single market group from ESI with:
    Returns the parsed JSON dict, or None on persistent failure.
    """
    url = f'{ESI_BASE_URL}/markets/groups/{market_group_id}/'
    retryable = {420, 429, 500, 502, 503, 504}

    async with semaphore:
        for attempt in range(MAX_RETRIES):
            # Small jitter to smooth request distribution
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

                    # Success
                    if response.status == 200:
                        return await response.json()

                    # Retryable error 
                    if response.status in retryable:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        print(
                            f"  [HTTP {response.status}] market_group {market_group_id} "
                            f"– retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Non-retryable error
                    print(
                        f"  [HTTP {response.status}] market_group {market_group_id} "
                        f"– skipping (non-retryable)"
                    )
                    return None

            except aiohttp.ClientError as exc:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(
                    f"  [ClientError] market_group {market_group_id}: {exc} "
                    f"– retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                )
                await asyncio.sleep(wait)

    print(f"  [FAILED] market_group {market_group_id} – exceeded max retries")
    return None


async def fetch_all_market_groups(market_group_ids):
    """
    Fetch all market groups concurrently, honouring MAX_CONCURRENCY.
    Returns a list of (market_group_id, data_dict) tuples for successful fetches.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    total = len(market_group_ids)
    results = []
    completed = 0

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.ensure_future(
                fetch_market_group(session, semaphore, mgid)
            )
            for mgid in market_group_ids
        ]

        for coro in asyncio.as_completed(tasks):
            data = await coro
            completed += 1

            if completed % 50 == 0:
                print(f"  Progress: {completed}/{total} market groups fetched...")

            if data:
                results.append(data)

    print(f"  Fetched {len(results)}/{total} market groups successfully.")
    return results

# ============================================
# DATABASE FUNCTIONS
# ============================================

def bulk_insert_market_groups(conn, market_groups):
    """
    Insert all market groups in a single executemany() call.
    """
    rows = [
        (
            mg['market_group_id'],
            mg.get('parent_group_id'),
            mg['name'],
            mg.get('description'),
            mg.get('icon_id'),
            mg.get('has_types', 0),
        )
        for mg in market_groups
    ]

    cursor = conn.cursor()
    cursor.executemany(
        '''
        INSERT OR REPLACE INTO inv_market_groups (
            market_group_id, parent_group_id, market_group_name,
            description, icon_id, has_types
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
    print("Starting inv_market_groups update from ESI")
    print("=" * 50)

    # Fetch the list of IDs
    market_group_ids = get_all_market_group_ids()

    if not market_group_ids:
        print("No market group IDs found. Exiting.")
        return

    # Fetch all group details in parallel
    print(f"\nFetching market group details (concurrency={MAX_CONCURRENCY})...")
    market_groups = asyncio.run(fetch_all_market_groups(market_group_ids))

    if not market_groups:
        print("No market group data retrieved. Exiting.")
        return

    # Bulk-insert into SQLite
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    # Enable WAL mode and relaxed sync for faster bulk writes
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    print("Inserting market group data...")
    inserted = bulk_insert_market_groups(conn, market_groups)

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("inv_market_groups update complete!")
    print(f"Total market groups inserted/replaced: {inserted}")
    print("=" * 50)


if __name__ == '__main__':
    main()