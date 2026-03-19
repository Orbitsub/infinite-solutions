#!/usr/bin/env python3
"""
Gets a new list of inventory categories from ESI and updates
the inv_categories table.
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

def get_all_category_ids():
    """
    Get a list of all category IDs from ESI (synchronous – single call).
    No authentication required.
    """
    url = f'{ESI_BASE_URL}/universe/categories/'

    print("Fetching list of all category IDs from ESI...")
    response = requests.get(url)

    if response.status_code == 200:
        category_ids = response.json()
        print(f"Found {len(category_ids)} category IDs")
        return category_ids
    else:
        print(f"Error fetching category IDs: {response.status_code}")
        return []


async def fetch_category(session, semaphore, category_id):
    """
    Fetch a single category from ESI with bounded concurrency,
    ESI error-limit monitoring, and exponential back-off + jitter.
    Returns the parsed JSON dict, or None on persistent failure.
    """
    url = f'{ESI_BASE_URL}/universe/categories/{category_id}/'
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
                            f"  [HTTP {response.status}] category {category_id} "
                            f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                        )
                        await asyncio.sleep(wait)
                        continue

                    print(
                        f"  [HTTP {response.status}] category {category_id} "
                        f"\u2013 skipping (non-retryable)"
                    )
                    return None

            except aiohttp.ClientError as exc:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(
                    f"  [ClientError] category {category_id}: {exc} "
                    f"\u2013 retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s"
                )
                await asyncio.sleep(wait)

    print(f"  [FAILED] category {category_id} \u2013 exceeded max retries")
    return None


async def fetch_all_categories(category_ids):
    """
    Fetch all categories concurrently, honouring MAX_CONCURRENCY.
    Returns a list of data dicts for successful fetches.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    total = len(category_ids)
    results = []
    completed = 0

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.ensure_future(fetch_category(session, semaphore, cid))
            for cid in category_ids
        ]

        for coro in asyncio.as_completed(tasks):
            data = await coro
            completed += 1

            if completed % 50 == 0:
                print(f"  Progress: {completed}/{total} categories fetched...")

            if data:
                results.append(data)

    print(f"  Fetched {len(results)}/{total} categories successfully.")
    return results

# ============================================
# DATABASE FUNCTIONS
# ============================================

def bulk_insert_categories(conn, categories):
    """
    Insert all categories in a single executemany() call.
    """
    rows = [
        (
            cat['category_id'],
            cat['name'],
            cat.get('icon_id'),
            cat.get('published', 0),
        )
        for cat in categories
    ]

    cursor = conn.cursor()
    cursor.executemany(
        '''
        INSERT OR REPLACE INTO inv_categories (
            category_id, category_name, icon_id, published
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
    print("Starting inv_categories update from ESI")
    print("=" * 50)

    # Fetch the list of IDs
    category_ids = get_all_category_ids()

    if not category_ids:
        print("No category IDs found. Exiting.")
        return

    # Fetch all category details in parallel
    print(f"\nFetching category details (concurrency={MAX_CONCURRENCY})...")
    categories = asyncio.run(fetch_all_categories(category_ids))

    if not categories:
        print("No category data retrieved. Exiting.")
        return

    # Bulk-insert into SQLite
    print(f"\nConnecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    print("Inserting category data...")
    inserted = bulk_insert_categories(conn, categories)

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("inv_categories update complete!")
    print(f"Total categories inserted/replaced: {inserted}")
    print("=" * 50)


if __name__ == '__main__':
    main()