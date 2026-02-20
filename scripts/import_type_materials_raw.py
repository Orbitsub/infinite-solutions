#!/usr/bin/env python3
"""
Import typeMaterials.jsonl as raw data into database.
Simple table: type_id -> JSON materials data
"""

import sqlite3
import json
import os

# Configuration
DB_PATH = r'E:\Python Project\mydatabase.db'
JSONL_PATH = r'E:\Python Project\sde\typeMaterials.jsonl'  # Adjust path if needed


def create_raw_table(conn):
    """
    Create raw table for typeMaterials data.
    Just stores the type_id and JSON materials array as-is.
    """
    cursor = conn.cursor()
    
    print("\nCreating type_materials table...")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS type_materials (
            type_id INTEGER PRIMARY KEY,
            materials_json TEXT NOT NULL
        )
    ''')
    conn.commit()
    print("[OK] Created type_materials table")


def import_raw_data(conn, jsonl_path):
    """
    Import typeMaterials.jsonl directly into database.
    No processing - just store the JSON as-is.
    """
    cursor = conn.cursor()
    
    print(f"\nImporting data from: {jsonl_path}")
    
    if not os.path.exists(jsonl_path):
        print(f"[ERROR] File not found: {jsonl_path}")
        return 0
    
    added = 0
    skipped = 0
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                entry = json.loads(line.strip())
                type_id = entry['_key']
                materials = entry.get('materials', [])
                
                # Store materials as JSON string
                materials_json = json.dumps(materials)
                
                try:
                    cursor.execute('''
                        INSERT INTO type_materials (type_id, materials_json)
                        VALUES (?, ?)
                    ''', (type_id, materials_json))
                    added += 1
                    
                    # Progress indicator
                    if added % 1000 == 0:
                        print(f"  Imported {added} rows...")
                        
                except sqlite3.IntegrityError:
                    skipped += 1
                    
            except json.JSONDecodeError as e:
                print(f"[WARNING] Line {line_num} - Invalid JSON: {e}")
    
    conn.commit()
    print(f"\n[OK] Imported {added} rows")
    if skipped > 0:
        print(f"[INFO] Skipped {skipped} duplicates")
    
    return added


def show_summary(conn):
    """Display summary of imported data"""
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("RAW TYPE_MATERIALS TABLE - SUMMARY")
    print("=" * 70)
    
    cursor.execute('SELECT COUNT(*) FROM type_materials')
    total = cursor.fetchone()[0]
    print(f"\nTotal rows: {total}")
    
    print("\n" + "=" * 70)
    print("SAMPLE DATA")
    print("=" * 70)
    
    cursor.execute('''
        SELECT type_id, materials_json
        FROM type_materials
        LIMIT 5
    ''')
    
    for type_id, materials_json in cursor.fetchall():
        materials = json.loads(materials_json)
        print(f"\nType ID: {type_id}")
        print(f"Materials: {len(materials)} items")
        for mat in materials[:3]:  # Show first 3
            print(f"  - Material {mat['materialTypeID']}: {mat['quantity']} units")
        if len(materials) > 3:
            print(f"  ... and {len(materials) - 3} more")
    
    print("\n" + "=" * 70)
    print("USAGE EXAMPLES")
    print("=" * 70)
    print("""
1. Get materials for a specific item (e.g., type_id = 18):
   
   SELECT type_id, materials_json
   FROM type_materials
   WHERE type_id = 18;

2. Parse JSON in Python:
   
   import json
   cursor.execute('SELECT materials_json FROM type_materials WHERE type_id = ?', (18,))
   materials = json.loads(cursor.fetchone()[0])
   for mat in materials:
       print(f"Material {mat['materialTypeID']}: {mat['quantity']}")

3. Count items by number of materials:
   
   SELECT 
       LENGTH(materials_json) - LENGTH(REPLACE(materials_json, 'materialTypeID', '')) 
       as material_count,
       COUNT(*) as items
   FROM type_materials
   GROUP BY material_count
   ORDER BY material_count;

4. Join with inv_types to get item names:
   
   SELECT 
       it.type_name,
       tm.materials_json
   FROM type_materials tm
   JOIN inv_types it ON it.type_id = tm.type_id
   WHERE it.type_name LIKE '%Muninn%';
""")


def main():
    print("=" * 70)
    print("EVE ONLINE - RAW IMPORT OF typeMaterials.jsonl")
    print("=" * 70)
    print("\nThis script imports typeMaterials.jsonl as raw data.")
    print("No processing - just stores type_id and JSON materials.")
    print("=" * 70 + "\n")
    
    # Check files exist
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        return
    
    if not os.path.exists(JSONL_PATH):
        print(f"[ERROR] typeMaterials.jsonl not found: {JSONL_PATH}")
        print("\nExpected location:")
        print(f"  {JSONL_PATH}")
        print("\nPlease:")
        print("  1. Place typeMaterials.jsonl in sde/ directory, OR")
        print("  2. Update JSONL_PATH variable in this script")
        return
    
    print(f"[OK] Database: {DB_PATH}")
    print(f"[OK] Data file: {JSONL_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Create table
        create_raw_table(conn)
        
        # Import data
        count = import_raw_data(conn, JSONL_PATH)
        
        if count > 0:
            # Show summary
            show_summary(conn)
            
            print("\n✅ Raw import complete!")
            print(f"📊 Table: type_materials")
            print(f"📁 Rows: {count}")
            print(f"📁 Database: {DB_PATH}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    main()