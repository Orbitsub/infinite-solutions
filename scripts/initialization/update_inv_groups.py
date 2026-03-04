#!/usr/bin/env python3
"""
Gets a new list of inventory groups from ESI and updates
the inv_groups table.
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

def get_all_group_ids():
    """
    Get a list of all group IDs from ESI (synchronous, handles pagination).
    No authentication required.
    """
    url = f'{ESI_BASE_URL}/universe/groups/'

    print("Fetching list of all group IDs from ESI...")
    group_ids = []
    page = 1

    while True:
        response = requests.get(url, params={'page': page})

        if response.status_code == 200:
            page_ids = response.json()
            if not page_ids:
                break
            group_ids.extend(page_ids)

            # Check if there are more pages
            total_pages = int(response.headers.get('X-Pages', 1))
            if page >= total_pages:
                break
            page += 1
        else:
            print(f"Error fetching group IDs (page {page}): {response.status_code}")
            break

    print(f"Found {len(group_ids)} group IDs")
    return group_ids


async def fetch_group(session, semaphore, group_id):
    """
    Fetch a single group from ESI with bounded concurrency,
    ESI error-limit monitoring, and exponential back-off + jitter.
    Returns the parsed JSON dict, or None on persistent failure.
    """
    url = f'{ESI_BASE_URL}/universe/groups/{group_id}/'
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
                            f"  [HTTP {response.status}] group {group_id} "
                            f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                        )
                        await asyncio.sleep(wait)
                        continue

                    print(
                        f"  [HTTP {response.status}] group {group_id} "
                        f"\u2013 skipping (non-retryable)"
                    )
                    return None

            except aiohttp.ClientError as exc:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(
                    f"  [ClientError] group {group_id}: {exc} "
                    f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                )
                await asyncio.sleep(wait)

    print(f"  [FAILED] group {group_id} \u2013 exceeded max retries")
    return None


async def fetch_all_groups(group_ids):
    """
    Fetch all groups concurrently, honouring MAX_CONCURRENCY.
    Returns a list of data dicts for successful fetches.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    total = len(group_ids)
    results = []
    completed = 0

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.ensure_future(fetch_group(session, semaphore, gid))
            for gid in group_ids
        ]

        for coro in asyncio.as_completed(tasks):
            data = await coro
            completed += 1

            if completed % 50 == 0:
                print(f"  Progress: {completed}/{total} groups fetched...")

            if data:
                results.append(data)

    print(f"  Fetched {len(results)}/{total} groups successfully.")
    return results

# ============================================
# DATABASE FUNCTIONS
# ============================================

def bulk_insert_groups(conn, groups):
    """
    Insert all groups in a single executemany() call.
    """
    rows = [
        (
            g['group_id'],
            g['category_id'],
            g['name'],
            g.get('icon_id'),
            g.get('use_base_price', 0),
            g.get('anchored', 0),
            g.get('anchorable', 0),
            g.get('fittable_non_singleton', 0),
            g.get('published', 0),
        )
        for g in groups
    ]

    cursor = conn.cursor()
    cursor.executemany(
        '''
        INSERT OR REPLACE INTO inv_groups (
            group_id, category_id, group_name, icon_id, use_base_price,
            anchored, anchorable, fittable_non_singleton, published
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        rows,
    )
    return len(rows)

# ============================================
# MAIN SCRIPT
# ============================================

def main():
    print("=" * 50)
    print("Starting inv_groups update from ESI")
    print("=" * 50)

    # Fetch the list of IDs (handles pagination)
    group_ids = get_all_group_ids()

    if not group_ids:
        print("No group IDs found. Exiting.")
        return

    # Fetch all group details in parallel
    print(f"\nFetching group details (concurrency={MAX_CONCURRENCY})...")
    groups = asyncio.run(fetch_all_groups(group_ids))

    if not groups:
        print("No group data retrieved. Exiting.")
        return

    # Bulk-insert into SQLite
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    print("Inserting group data...")
    inserted = bulk_insert_groups(conn, groups)

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("inv_groups update complete!")
    print(f"Total groups inserted/replaced: {inserted}")
    print("=" * 50)


if __name__ == '__main__':
    main()