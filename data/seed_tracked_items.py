"""
seed_tracked_items.py

Reads tracked_items.txt and seeds the tracked_market_items table.
Cross-references inv_types to get the correct type_name.
"""

import sqlite3
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

DB_PATH = PROJECT_DIR / 'mydatabase.db'
ITEMS_FILE = SCRIPT_DIR / 'tracked_items.txt'

def main():
    if not ITEMS_FILE.exists():
        print(f"Error: {ITEMS_FILE} not found.")
        return

    # 1. Parse tracked items
    type_ids = []
    with open(ITEMS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                type_ids.append(int(line))
            except ValueError:
                continue

    if not type_ids:
        print("No valid type_ids found in tracked_items.txt")
        return

    print(f"Found {len(type_ids)} type_ids in tracked_items.txt")

    # 2. Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 3. Get item names from inv_types
    # SQLite has a limit on parameters (usually 999 or 32766), so chunking might be safer 
    # but for a few hundred items it's fine. We'll chunk just to be safe.
    id_to_name = {}
    chunk_size = 500
    for i in range(0, len(type_ids), chunk_size):
        chunk = type_ids[i:i+chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        cursor.execute(f"SELECT type_id, type_name FROM inv_types WHERE type_id IN ({placeholders})", chunk)
        for row in cursor.fetchall():
            id_to_name[row[0]] = row[1]

    # 4. Insert into tracked_market_items
    inserted = 0
    ignored = 0
    missing_names = 0

    for type_id in set(type_ids):  # Use set to avoid formatting duplicates from the txt file
        type_name = id_to_name.get(type_id)
        if not type_name:
            print(f"Warning: type_id {type_id} not found in inv_types. Using fallback name.")
            type_name = f"Unknown Type {type_id}"
            missing_names += 1

        try:
            # category is set to 'other' by default via schema, or we can explicit pass it
            cursor.execute("""
                INSERT INTO tracked_market_items (type_id, type_name, category)
                VALUES (?, ?, 'other')
            """, (type_id, type_name))
            inserted += 1
        except sqlite3.IntegrityError:
            # UNIQUE constraint failed (already exists)
            ignored += 1

    conn.commit()
    conn.close()

    print(f"Done! Inserted {inserted} items, {ignored} items already existed in the table.")
    if missing_names > 0:
        print(f"Note: {missing_names} items had no matching name in inv_types.")

if __name__ == '__main__':
    main()
