#!/usr/bin/env python3
"""
==========================================
PARSE DOCTRINE FITS TO CSV
==========================================
Extracts all fits from TEST_Doctrine_Fits.txt
Creates a CSV with: fit_name, item_name, quantity
==========================================
"""

import re
import csv

def parse_fits_file(filename):
    """
    Parse the fits file and extract all items with quantities.
    Returns: list of (fit_name, item_name, quantity)
    """
    
    fits_data = []
    current_fit = None
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check if this is a fit header: [ShipType, FitName]
            fit_match = re.match(r'\[(.*?),\s*(.*?)\]', line)
            if fit_match:
                ship_type = fit_match.group(1).strip()
                fit_name = fit_match.group(2).strip()
                current_fit = f"{ship_type} - {fit_name}"
                continue
            
            # Skip empty high slots
            if '[Empty' in line:
                continue
            
            # Parse item line
            # Format can be:
            # - "Item Name x5" (with quantity)
            # - "Item Name" (quantity = 1)
            
            if current_fit:
                # Check for quantity notation (x###)
                qty_match = re.match(r'(.*?)\s+x(\d+)$', line)
                
                if qty_match:
                    item_name = qty_match.group(1).strip()
                    quantity = int(qty_match.group(2))
                else:
                    item_name = line.strip()
                    quantity = 1
                
                # Add to data
                fits_data.append((current_fit, item_name, quantity))
    
    return fits_data


def write_to_csv(fits_data, output_filename):
    """Write fits data to CSV file."""
    
    with open(output_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['fit_name', 'item_name', 'quantity'])
        
        for fit_name, item_name, quantity in fits_data:
            writer.writerow([fit_name, item_name, quantity])
    
    print(f"[OK] Wrote {len(fits_data)} items to {output_filename}")


def show_summary(fits_data):
    """Show summary statistics."""
    
    # Count unique fits
    unique_fits = set(fit_name for fit_name, _, _ in fits_data)
    
    # Count unique items
    unique_items = set(item_name for _, item_name, _ in fits_data)
    
    # Total quantity
    total_quantity = sum(qty for _, _, qty in fits_data)
    
    print("\n" + "=" * 80)
    print("FITS PARSING SUMMARY")
    print("=" * 80)
    print(f"Total Fit Lines: {len(fits_data)}")
    print(f"Unique Fits: {len(unique_fits)}")
    print(f"Unique Items: {len(unique_items)}")
    print(f"Total Item Quantity: {total_quantity:,}")
    
    print("\n" + "-" * 80)
    print("SAMPLE FITS:")
    print("-" * 80)
    for fit_name in list(unique_fits)[:5]:
        print(f"  • {fit_name}")
    
    print("\n" + "-" * 80)
    print("SAMPLE ITEMS:")
    print("-" * 80)
    for item_name in list(unique_items)[:10]:
        print(f"  • {item_name}")
    
    print("=" * 80)


def main():
    input_file = 'TEST_Doctrine_Fits.txt'
    output_file = 'doctrine_fits.csv'
    
    print("=" * 80)
    print("PARSE DOCTRINE FITS")
    print("=" * 80)
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print()
    
    # Parse the fits file
    print("Parsing fits file...")
    fits_data = parse_fits_file(input_file)
    
    # Write to CSV
    write_to_csv(fits_data, output_file)
    
    # Show summary
    show_summary(fits_data)
    
    print("\n[OK] Done! Next steps:")
    print("  1. Review doctrine_fits.csv")
    print("  2. Run import script to load into database")
    print("  3. Query for fit pricing")


if __name__ == '__main__':
    main()