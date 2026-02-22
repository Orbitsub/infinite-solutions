"""
Update assets/embedded_data.js with:
1. Current inventory quantities
2. Correct UTC/EVE Time timestamps
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from generate_corrected_html import get_last_updated, get_inventory_last_updated, get_inventory_data
import json
import re

EMBEDDED_DATA_FILE = os.path.join('assets', 'embedded_data.js')

print("Fetching data from database...")
print("-" * 60)

# Get data
inventory = get_inventory_data()
blueprints_last_updated = get_last_updated()
inventory_last_updated = get_inventory_last_updated()

print(f"Inventory items: {len(inventory)}")
print(f"Blueprints last updated: {blueprints_last_updated}")
print(f"Inventory last updated: {inventory_last_updated}")
print()

# Read embedded_data.js
print(f"Reading {EMBEDDED_DATA_FILE}...")
with open(EMBEDDED_DATA_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Build new EMBEDDED_DATA block
print("Updating EMBEDDED_DATA...")
new_embedded_data = {
    "inventory": inventory,
    "blueprintsLastUpdated": blueprints_last_updated,
    "inventoryLastUpdated": inventory_last_updated
}

replacement = f'const EMBEDDED_DATA = {json.dumps(new_embedded_data, indent=4)};'

# Find and replace the entire EMBEDDED_DATA object
pattern = r'const EMBEDDED_DATA = \{.*?\n\};'
content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

if count == 0:
    print("WARNING: Could not find EMBEDDED_DATA pattern in embedded_data.js")
    sys.exit(1)

# Write updated file
print(f"Writing updated {EMBEDDED_DATA_FILE}...")
with open(EMBEDDED_DATA_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print()
print("=" * 60)
print("SUCCESS!")
print("=" * 60)
print(f"[OK] Blueprint timestamp: {blueprints_last_updated}")
print(f"[OK] Inventory timestamp: {inventory_last_updated}")
print(f"[OK] Inventory items written: {len(inventory)}")
print(f"[OK] {EMBEDDED_DATA_FILE} updated successfully")
print()
print("Refresh your browser to see the changes!")
