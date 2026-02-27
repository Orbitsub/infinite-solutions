#!/usr/bin/env python3
"""
Load blueprint -> manufactured product mappings from SDE into SQLite.
Source: dataImported/blueprints.jsonl
Target table: blueprint_product_mapping
"""
import json
import os
import sqlite3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
SDE_BLUEPRINTS_PATH = os.path.join(PROJECT_DIR, 'dataImported', 'blueprints.jsonl')


def ensure_table(conn):
    """Create mapping table if it does not already exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blueprint_product_mapping (
            blueprint_type_id INTEGER PRIMARY KEY,
            product_type_id INTEGER NOT NULL,
            last_updated TEXT NOT NULL
        )
        """
    )


def load_mappings_from_sde():
    """Parse SDE blueprints.jsonl and return rows for DB insert."""
    if not os.path.exists(SDE_BLUEPRINTS_PATH):
        raise FileNotFoundError(
            f"SDE file not found: {SDE_BLUEPRINTS_PATH}\n"
            "Download/restore sde/blueprints.jsonl before running this script."
        )

    mappings = []

    with open(SDE_BLUEPRINTS_PATH, 'r', encoding='utf-8') as sde_file:
        for line in sde_file:
            blueprint = json.loads(line)
            bp_type_id = blueprint.get('blueprintTypeID')
            activities = blueprint.get('activities', {})

            manufacturing = activities.get('manufacturing')
            if not manufacturing:
                continue

            products = manufacturing.get('products', [])
            if not products:
                continue

            product_type_id = products[0].get('typeID')
            if bp_type_id and product_type_id:
                mappings.append((bp_type_id, product_type_id))

    return mappings


def bulk_replace_mappings(conn, mappings):
    """Replace all rows in mapping table in one transaction."""
    cursor = conn.cursor()

    cursor.execute("DELETE FROM blueprint_product_mapping")
    cursor.executemany(
        """
        INSERT OR REPLACE INTO blueprint_product_mapping
        (blueprint_type_id, product_type_id, last_updated)
        VALUES (?, ?, datetime('now'))
        """,
        mappings,
    )

    return len(mappings)


def main():
    print("=" * 60)
    print("UPDATING BLUEPRINT PRODUCT MAPPING")
    print("=" * 60)
    print(f"SDE source: {SDE_BLUEPRINTS_PATH}")
    print(f"Database:   {DB_PATH}")
    print()

    mappings = load_mappings_from_sde()
    print(f"Parsed {len(mappings)} blueprint/product mappings from SDE")

    if not mappings:
        print("No mappings found. Exiting.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_table(conn)
        inserted = bulk_replace_mappings(conn, mappings)
        conn.commit()
    finally:
        conn.close()

    print()
    print("=" * 60)
    print(f"[OK] blueprint_product_mapping updated with {inserted} rows")
    print("=" * 60)


if __name__ == '__main__':
    main()
