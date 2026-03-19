"""
==========================================
IMPORT PACKAGED VOLUMES FROM CSV
==========================================
Imports packaged volumes from CSV file into
sde_types table. Fast and simple!
==========================================
"""

import sqlite3
import csv
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
CSV_PATH = os.path.join(PROJECT_DIR, 'packaged_volumes.csv')

def create_sde_table(conn):
    """Create the sde_types table."""
    cursor = conn.cursor()
    
    print("=" * 80)
    print("CREATING SDE_TYPES TABLE")
    print("=" * 80)
    
    cursor.execute('DROP TABLE IF EXISTS sde_types')
    
    cursor.execute('''
        CREATE TABLE sde_types (
            type_id INTEGER PRIMARY KEY,
            packaged_volume REAL NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')
    
    cursor.execute('CREATE INDEX idx_sde_types_packaged_volume ON sde_types(packaged_volume)')
    
    conn.commit()
    print("\n[OK] Table created")

def import_csv(conn, csv_path):
    """Import packaged volumes from CSV."""
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("IMPORTING PACKAGED VOLUMES")
    print("=" * 80)
    
    if not os.path.exists(csv_path):
        print(f"\n[ERROR] CSV file not found: {csv_path}")
        print("\nMake sure 'packaged_volumes.csv' is in your project directory!")
        return 0
    
    current_time = datetime.now(timezone.utc).isoformat()
    imported = 0
    
    print(f"\n[INFO] Reading CSV: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        batch = []
        batch_size = 100
        
        for row in reader:
            type_id = int(row['typeID'])
            volume = float(row['volume'])
            
            batch.append((type_id, volume, current_time))
            
            if len(batch) >= batch_size:
                cursor.executemany('''
                    INSERT INTO sde_types (type_id, packaged_volume, last_updated)
                    VALUES (?, ?, ?)
                ''', batch)
                imported += len(batch)
                print(f"\r[INFO] Imported: {imported} items", end='', flush=True)
                batch = []
        
        # Insert remaining
        if batch:
            cursor.executemany('''
                INSERT INTO sde_types (type_id, packaged_volume, last_updated)
                VALUES (?, ?, ?)
            ''', batch)
            imported += len(batch)
    
    conn.commit()
    print(f"\n\n[OK] Imported {imported} packaged volumes")
    return imported

def verify_import(conn):
    """Verify the import worked."""
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    # Count total
    cursor.execute("SELECT COUNT(*) FROM sde_types")
    count = cursor.fetchone()[0]
    print(f"\n[INFO] Total items with packaged volumes: {count}")
    
    # Show ship examples
    print("\n[INFO] Sample ships:")
    cursor.execute("""
        SELECT 
            it.type_name,
            it.volume as assembled,
            st.packaged_volume as packaged,
            it.volume / st.packaged_volume as ratio
        FROM sde_types st
        JOIN inv_types it ON it.type_id = st.type_id
        WHERE it.type_name IN ('Mackinaw', 'Hulk', 'Retriever', 'Venture', 'Procurer')
        ORDER BY it.type_name
    """)
    
    print(f"\n{'Ship':<20} {'Assembled':>15} {'Packaged':>15} {'Ratio':>10}")
    print("-" * 62)
    
    for row in cursor.fetchall():
        name, assembled, packaged, ratio = row
        print(f"{name:<20} {assembled:>15,.1f} {packaged:>15,.1f} {ratio:>10.1f}x")
    
    # Show freight cost for Mackinaw
    print("\n[INFO] Mackinaw freight cost (Tier 2: 2,000 ISK/m³):")
    cursor.execute("""
        SELECT 
            it.type_name,
            it.volume * 2000 as old_freight,
            st.packaged_volume * 2000 as new_freight,
            (it.volume * 2000) - (st.packaged_volume * 2000) as savings
        FROM sde_types st
        JOIN inv_types it ON it.type_id = st.type_id
        WHERE it.type_name = 'Mackinaw'
    """)
    
    row = cursor.fetchone()
    if row:
        name, old_freight, new_freight, savings = row
        print(f"\n  Old (assembled):  {old_freight:>15,.0f} ISK")
        print(f"  New (packaged):   {new_freight:>15,.0f} ISK")
        print(f"  SAVINGS:          {savings:>15,.0f} ISK ✓")

def main():
    print("=" * 80)
    print("IMPORT PACKAGED VOLUMES FROM CSV")
    print("=" * 80)
    print(f"\nThis will import packaged volumes from: {CSV_PATH}")
    print("Creates sde_types table (doesn't touch inv_types)")
    print()
    
    response = input("Continue? (y/n): ").strip().lower()
    if response != 'y':
        print("\n[CANCELLED]")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        create_sde_table(conn)
        imported = import_csv(conn, CSV_PATH)
        
        if imported > 0:
            verify_import(conn)
            
            print("\n" + "=" * 80)
            print("[OK] IMPORT COMPLETE!")
            print("=" * 80)
            print("\nYour quote generator will now use correct packaged volumes!")
            print("Ship freight costs will be accurate! ✓\n")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()