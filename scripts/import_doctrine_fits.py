#!/usr/bin/env python3
"""
==========================================
IMPORT DOCTRINE FITS TO DATABASE
==========================================
Imports doctrine fits and items into database tables:
- doctrine_fits: fit metadata
- doctrine_fit_items: items in each fit
==========================================
"""

import sqlite3
import csv
import os
from datetime import datetime, timezone

def create_tables(conn):
    """Create doctrine fits tables."""
    cursor = conn.cursor()
    
    print("Creating tables...")
    
    # Drop existing tables
    cursor.execute('DROP TABLE IF EXISTS doctrine_fit_items')
    cursor.execute('DROP TABLE IF EXISTS doctrine_fits')
    
    # Create doctrine_fits table
    cursor.execute('''
        CREATE TABLE doctrine_fits (
            fit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fit_name TEXT NOT NULL UNIQUE,
            ship_type TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Create doctrine_fit_items table
    cursor.execute('''
        CREATE TABLE doctrine_fit_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fit_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (fit_id) REFERENCES doctrine_fits(fit_id),
            FOREIGN KEY (type_id) REFERENCES inv_types(type_id)
        )
    ''')
    
    # Create index for faster lookups
    cursor.execute('''
        CREATE INDEX idx_fit_items_fit_id ON doctrine_fit_items(fit_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX idx_fit_items_type_id ON doctrine_fit_items(type_id)
    ''')
    
    conn.commit()
    print("[OK] Tables created")


def import_fits(conn, csv_path):
    """Import fits from CSV."""
    cursor = conn.cursor()
    current_time = datetime.now(timezone.utc).isoformat()
    
    print(f"\nReading CSV from: {csv_path}")
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        return 0, 0
    
    fits_created = 0
    items_imported = 0
    items_not_found = []
    hulls_added = 0
    
    fit_id_map = {}  # fit_name -> fit_id
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            fit_name = row['fit_name'].strip()
            item_name = row['item_name'].strip()
            quantity = int(row['quantity'])
            
            # Create fit if we haven't seen it yet
            if fit_name not in fit_id_map:
                # Extract ship type (everything before first dash)
                ship_type = fit_name.split(' - ')[0].strip() if ' - ' in fit_name else fit_name
                
                cursor.execute('''
                    INSERT INTO doctrine_fits (fit_name, ship_type, created_at)
                    VALUES (?, ?, ?)
                ''', (fit_name, ship_type, current_time))
                
                fit_id = cursor.lastrowid
                fit_id_map[fit_name] = fit_id
                fits_created += 1
                
                # ADD THE SHIP HULL ITSELF (1x ship hull)
                cursor.execute('SELECT type_id FROM inv_types WHERE type_name = ?', (ship_type,))
                hull_result = cursor.fetchone()
                
                if hull_result:
                    hull_type_id = hull_result[0]
                    cursor.execute('''
                        INSERT INTO doctrine_fit_items (fit_id, type_id, quantity)
                        VALUES (?, ?, 1)
                    ''', (fit_id, hull_type_id))
                    items_imported += 1
                    hulls_added += 1
                else:
                    items_not_found.append((fit_name, f"{ship_type} (HULL)"))
            else:
                fit_id = fit_id_map[fit_name]
            
            # Look up type_id from inv_types
            cursor.execute('SELECT type_id FROM inv_types WHERE type_name = ?', (item_name,))
            result = cursor.fetchone()
            
            if result:
                type_id = result[0]
                
                cursor.execute('''
                    INSERT INTO doctrine_fit_items (fit_id, type_id, quantity)
                    VALUES (?, ?, ?)
                ''', (fit_id, type_id, quantity))
                
                items_imported += 1
            else:
                items_not_found.append((fit_name, item_name))
    
    conn.commit()
    
    print(f"\n[OK] Created {fits_created} fits")
    print(f"[OK] Added {hulls_added} ship hulls")
    print(f"[OK] Imported {items_imported} items")
    
    if items_not_found:
        print(f"\n[WARNING] {len(items_not_found)} items not found in inv_types:")
        # Group by item name
        missing_items = {}
        for fit_name, item_name in items_not_found:
            if item_name not in missing_items:
                missing_items[item_name] = []
            missing_items[item_name].append(fit_name)
        
        for item_name in list(missing_items.keys())[:10]:
            fits = missing_items[item_name]
            print(f"  - {item_name} (in {len(fits)} fits)")
        
        if len(missing_items) > 10:
            print(f"  ... and {len(missing_items) - 10} more unique items")
    
    return fits_created, len(items_not_found)


def show_summary(conn):
    """Show summary of imported data."""
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("DOCTRINE FITS SUMMARY")
    print("=" * 80)
    
    cursor.execute('SELECT COUNT(*) FROM doctrine_fits')
    total_fits = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM doctrine_fit_items')
    total_items = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT type_id) FROM doctrine_fit_items')
    unique_items = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(quantity) FROM doctrine_fit_items')
    total_quantity = cursor.fetchone()[0]
    
    print(f"\nTotal Fits: {total_fits}")
    print(f"Total Item Entries: {total_items}")
    print(f"Unique Items: {unique_items}")
    print(f"Total Quantity: {total_quantity:,}")
    
    # Show sample fits
    print("\n" + "-" * 80)
    print("SAMPLE FITS:")
    print("-" * 80)
    
    cursor.execute('''
        SELECT 
            df.fit_name,
            df.ship_type,
            COUNT(dfi.id) as item_count,
            SUM(dfi.quantity) as total_qty
        FROM doctrine_fits df
        LEFT JOIN doctrine_fit_items dfi ON dfi.fit_id = df.fit_id
        GROUP BY df.fit_id
        ORDER BY df.fit_name
        LIMIT 5
    ''')
    
    for fit_name, ship_type, item_count, total_qty in cursor.fetchall():
        print(f"  • {fit_name}")
        print(f"    Ship: {ship_type} | {item_count} unique items | {total_qty:,} total")
    
    print("=" * 80)


def main():
    print("=" * 80)
    print("IMPORT DOCTRINE FITS TO DATABASE")
    print("=" * 80)
    
    # Use paths - database is in parent directory of scripts
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)  # Go up one level
    db_path = os.path.join(project_dir, 'mydatabase.db')
    csv_path = os.path.join(project_dir, 'doctrine_fits.csv')
    
    print(f"\nLooking for database: {db_path}")
    print(f"Looking for CSV: {csv_path}\n")
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        return
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        print("Run parse_doctrine_fits.py first!")
        return
    
    conn = sqlite3.connect(db_path)
    
    try:
        create_tables(conn)
        fits_created, items_not_found = import_fits(conn, csv_path)
        
        if fits_created > 0:
            show_summary(conn)
            
            print("\n[OK] Doctrine fits imported!")
            print("\nNext step: Run fit_pricing_query.sql to see Jita prices")
        else:
            print("\n[ERROR] No fits imported")
        
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        conn.close()


if __name__ == '__main__':
    main()