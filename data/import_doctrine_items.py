"""
==========================================
IMPORT DOCTRINE ITEMS TO DATABASE
==========================================
Imports doctrine items into a simple table.
Table contains only type_id and last_updated.
==========================================
"""

import sqlite3
import csv
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

# Use the cleaned CSV
CSV_PATH = os.path.join(PROJECT_DIR, 'TEST_doctrine_items.csv')

def create_doctrine_items_table(conn):
    """Create simple doctrine items table."""
    cursor = conn.cursor()
    
    print("Creating doctrine_items table...")
    
    cursor.execute('DROP TABLE IF EXISTS doctrine_items')
    
    cursor.execute('''
        CREATE TABLE doctrine_items (
            type_id INTEGER PRIMARY KEY,
            last_updated TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    print("[OK] Table created")

def import_csv(conn, csv_path):
    """Import items from CSV."""
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    print(f"\nReading CSV from: {csv_path}")
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        return 0, 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        
        imported = 0
        not_found = []
        duplicates = 0
        
        for row in reader:
            if not row:
                continue
                
            item_name = row[0].strip().strip('"')
            
            # Look up type_id from inv_types
            cursor.execute('SELECT type_id FROM inv_types WHERE type_name = ?', (item_name,))
            result = cursor.fetchone()
            
            if result:
                type_id = result[0]
                
                try:
                    cursor.execute('''
                        INSERT INTO doctrine_items (type_id, last_updated)
                        VALUES (?, ?)
                    ''', (type_id, current_time))
                    imported += 1
                except sqlite3.IntegrityError:
                    # Duplicate type_id
                    duplicates += 1
            else:
                not_found.append(item_name)
        
        conn.commit()
    
    print(f"\n[OK] Imported {imported} unique items")
    
    if duplicates > 0:
        print(f"[INFO] Skipped {duplicates} duplicate entries")
    
    if not_found:
        print(f"\n[WARNING] {len(not_found)} items not found in inv_types:")
        for item in not_found[:10]:  # Show first 10
            print(f"  - {item}")
        if len(not_found) > 10:
            print(f"  ... and {len(not_found) - 10} more")
    
    return imported, len(not_found)

def show_summary(conn):
    """Show summary of imported items."""
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("DOCTRINE ITEMS SUMMARY")
    print("=" * 80)
    
    cursor.execute('SELECT COUNT(*) FROM doctrine_items')
    total = cursor.fetchone()[0]
    print(f"\nTotal Doctrine Items: {total}")
    
    # Check which items are in BWF market
    cursor.execute('''
        SELECT COUNT(DISTINCT di.type_id)
        FROM doctrine_items di
        JOIN bwf_market_orders bmo ON bmo.type_id = di.type_id
    ''')
    in_market = cursor.fetchone()[0]
    
    print(f"Items in BWF Market: {in_market}")
    print(f"Items NOT in BWF Market: {total - in_market}")
    
    # Show some items
    print("\n" + "-" * 80)
    print("SAMPLE DOCTRINE ITEMS:")
    print("-" * 80)
    
    cursor.execute('''
        SELECT it.type_name
        FROM doctrine_items di
        JOIN inv_types it ON it.type_id = di.type_id
        ORDER BY it.type_name
        LIMIT 10
    ''')
    
    for (item_name,) in cursor.fetchall():
        print(f"  {item_name}")
    
    print(f"  ... and {total - 10} more")
    print("=" * 80)

def main():
    print("=" * 80)
    print("IMPORT DOCTRINE ITEMS TO DATABASE")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        create_doctrine_items_table(conn)
        imported, not_found = import_csv(conn, CSV_PATH)
        
        if imported > 0:
            show_summary(conn)
            
            print("\n[OK] Doctrine items imported!")
            print("\nTable structure:")
            print("  - type_id (PRIMARY KEY)")
            print("  - last_updated")
            print("\nNow you can run doctrine_market_analysis.sql")
        else:
            print("\n[ERROR] No items imported")
        
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        conn.close()

if __name__ == '__main__':
    main()