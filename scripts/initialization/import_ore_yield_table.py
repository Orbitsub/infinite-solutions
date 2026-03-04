#!/usr/bin/env python3
"""
Import Ore Yields from CSV
Handles both regular minerals and moon materials.
"""

import sqlite3
import csv
import os

# Configuration

INIT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(INIT_DIR))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
CSV_PATH = os.path.join(PROJECT_DIR, 'dataImported', 'moon_ore_yields.csv')

def import_csv_to_moon_ore_yields(conn, csv_path):
    """
    Import moon ore yields from CSV file.
    """
    cursor = conn.cursor()
    
    print(f"\nImporting from: {csv_path}")
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        return False
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Get column names
        fieldnames = reader.fieldnames
        print(f"Found {len(fieldnames)} columns")
        
        updated = 0
        not_found = []
        
        for row in reader:
            ore_name = row.get('Moon Ore', '').strip()
            
            if not ore_name:
                continue
            
            # Ore names in CSV already have "Compressed" prefix
            # Match exactly to database names
            search_names = [ore_name]
            
            # Build UPDATE query
            updates = []
            values = []
            
            # Column mapping - CSV column name → database column name
            column_mapping = {
                # Regular minerals
                'Pyerite': 'pyerite_yield',
                'Mexallon': 'mexallon_yield',
                'Tritanium': 'tritanium_yield',
                'Isogen': 'isogen_yield',
                'Nocxium': 'nocxium_yield',
                'Zydrine': 'zydrine_yield',
                'Megacyte': 'megacyte_yield',
                'Morphite': 'morphite_yield',
                
                # R16 Moon materials
                'Hydrocarbons': 'hydrocarbons_yield',
                'Silicates': 'silicates_yield',
                'Evaporite Deposits': 'evaporite_deposits_yield',
                'Atmospheric Gases': 'atmospheric_gases_yield',
                
                # R32 Moon materials
                'Cadmium': 'cadmium_yield',
                'Vanadium': 'vanadium_yield',
                
                # R64 Moon materials
                'Cobalt': 'cobalt_yield',
                'Scandium': 'scandium_yield',
                'Tungsten': 'tungsten_yield',
                'Titanium': 'titanium_yield',
                'Chromium': 'chromium_yield',
                'Platinum': 'platinum_yield',
                'Technetium': 'technetium_yield',
                'Mercury': 'mercury_yield',
                'Caesium': 'caesium_yield',
                'Hafnium': 'hafnium_yield',
                'Promethium': 'promethium_yield',
                'Neodymium': 'neodymium_yield',
                'Dysprosium': 'dysprosium_yield',
                'Thulium': 'thulium_yield',
            }
            
            for csv_col, db_col in column_mapping.items():
                if csv_col in row:
                    try:
                        value = float(row[csv_col]) if row[csv_col].strip() and row[csv_col].strip() != '0' else 0.0
                        if value > 0:  # Only update non-zero values
                            updates.append(f"{db_col} = ?")
                            values.append(value)
                    except ValueError:
                        pass
            
            if not updates:
                continue
            
            # Try to update with each possible name
            updated_row = False
            for search_name in search_names:
                values_with_name = values + [search_name]
                sql = f"UPDATE moon_ore_yields SET {', '.join(updates)} WHERE ore_name = ?"
                
                cursor.execute(sql, values_with_name)
                
                if cursor.rowcount > 0:
                    updated += 1
                    updated_row = True
                    break
            
            if not updated_row:
                not_found.append(ore_name)
        
        conn.commit()
    
    print(f"\n[OK] Updated {updated} moon ore types")
    
    if not_found:
        print(f"\n[WARNING] {len(not_found)} ores not found in database:")
        for ore in not_found[:10]:
            print(f"  • {ore}")
        if len(not_found) > 10:
            print(f"  ... and {len(not_found) - 10} more")
    
    return True


def verify_import(conn):
    """Verify data was imported correctly"""
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    # Count ores with yields
    cursor.execute('''
        SELECT COUNT(*) 
        FROM moon_ore_yields 
        WHERE pyerite_yield > 0 
           OR mexallon_yield > 0
           OR cobalt_yield > 0 
           OR chromium_yield > 0 
           OR titanium_yield > 0
    ''')
    with_yields = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM moon_ore_yields')
    total = cursor.fetchone()[0]
    
    print(f"\nTotal moon ore types: {total}")
    print(f"Ores with yields populated: {with_yields}")
    
    # Show sample data - regular minerals
    print("\nSample Data (Regular Minerals):")
    cursor.execute('''
        SELECT ore_name, pyerite_yield, mexallon_yield
        FROM moon_ore_yields
        WHERE pyerite_yield > 0 OR mexallon_yield > 0
        ORDER BY ore_name
        LIMIT 5
    ''')
    
    print(f"{'Ore Name':<40} {'Pyerite':>10} {'Mexallon':>10}")
    print("-" * 60)
    for ore_name, pyerite, mexallon in cursor.fetchall():
        print(f"{ore_name:<40} {pyerite:>10.0f} {mexallon:>10.0f}")
    
    # Show sample data - moon materials
    print("\nSample Data (Moon Materials):")
    cursor.execute('''
        SELECT ore_name, cobalt_yield, chromium_yield, titanium_yield
        FROM moon_ore_yields
        WHERE cobalt_yield > 0 OR chromium_yield > 0 OR titanium_yield > 0
        ORDER BY ore_name
        LIMIT 5
    ''')
    
    print(f"{'Ore Name':<40} {'Cobalt':>10} {'Chromium':>10} {'Titanium':>10}")
    print("-" * 70)
    for ore_name, cobalt, chromium, titanium in cursor.fetchall():
        print(f"{ore_name:<40} {cobalt:>10.0f} {chromium:>10.0f} {titanium:>10.0f}")


def main():
    print("=" * 70)
    print("IMPORT MOON ORE YIELDS FROM CSV")
    print("=" * 70)
    
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        return
    
    if not os.path.exists(CSV_PATH):
        print(f"[ERROR] CSV file not found: {CSV_PATH}")
        print("\nRun parse_moon_ore_data.py first to create the CSV.")
        return
    
    print(f"[OK] Database: {DB_PATH}")
    print(f"[OK] CSV File: {CSV_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Import CSV
        success = import_csv_to_moon_ore_yields(conn, CSV_PATH)
        
        if success:
            # Verify import
            verify_import(conn)
            
            print("\n" + "=" * 70)
            print("✅ Import complete!")
            print("\n📋 NEXT STEP:")
            print("  Copy moon_ore_arbitrage_query.sql to queries folder")
            print("  Open in DB Browser and run analysis")
            print("=" * 70)
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    main()