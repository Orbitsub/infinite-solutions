#!/usr/bin/env python3
"""
Import edited blueprint categories from CSV and create database overrides.
Run this after uploading blueprint_categories.csv.
"""
import sqlite3
import csv

DB_PATH = 'mydatabase.db'
INPUT_CSV = 'blueprint_categories.csv'

def create_override_table():
    """Create the override table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blueprint_category_overrides (
            type_id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            subcategory TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (type_id) REFERENCES inv_types(type_id)
        )
    """)

    conn.commit()
    conn.close()

def import_categories():
    print("=" * 70)
    print("IMPORTING BLUEPRINT CATEGORY OVERRIDES")
    print("=" * 70)
    print()

    # Create table if needed
    create_override_table()

    # Read CSV
    print(f"Reading {INPUT_CSV}...")
    overrides = []
    skipped = 0

    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            type_id = int(row['type_id'])
            new_category = row['new_category'].strip()
            new_subcategory = row['new_subcategory'].strip()
            current_category = row['current_category'].strip()
            current_subcategory = row['current_subcategory'].strip()

            # Only create override if new differs from current (and new is not blank)
            if new_category and (new_category != current_category or new_subcategory != current_subcategory):
                overrides.append({
                    'type_id': type_id,
                    'category': new_category,
                    'subcategory': new_subcategory
                })
            else:
                skipped += 1

    print(f"  Found {len(overrides)} changed categories")
    print(f"  Skipped {skipped} unchanged blueprints")
    print()

    if not overrides:
        print("No changes detected. Nothing to import.")
        return

    # Import to database
    print("Importing overrides to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing overrides (fresh import)
    cursor.execute("DELETE FROM blueprint_category_overrides")
    conn.commit()  # Commit the delete first

    # Insert new overrides using INSERT OR REPLACE to handle any conflicts
    for override in overrides:
        cursor.execute("""
            INSERT OR REPLACE INTO blueprint_category_overrides (type_id, category, subcategory)
            VALUES (?, ?, ?)
        """, (override['type_id'], override['category'], override['subcategory']))

    conn.commit()
    conn.close()

    print()
    print("=" * 70)
    print("IMPORT COMPLETE!")
    print("=" * 70)
    print()
    print(f"[OK] Imported {len(overrides)} category overrides")
    print()
    print("NEXT STEPS:")
    print("1. Run: python update_all_blueprint_data.py")
    print("   (This will regenerate index.html with new categories)")
    print()
    print("Or just run the HTML update:")
    print("2. Run: python update_html_data.py")
    print()

if __name__ == '__main__':
    import_categories()
