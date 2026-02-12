"""
Update index_final.html with:
1. Correct UTC/EVE Time timestamp
2. Deduplicated blueprints (keep best ME/TE)
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from generate_corrected_html import get_last_updated, get_inventory_last_updated, get_blueprints_with_metadata, get_inventory_data
import json
import re

HTML_FILE = 'index_final.html'

print("Fetching data from database...")
print("-" * 60)

# Get data
inventory = get_inventory_data()
blueprints = get_blueprints_with_metadata()
blueprints_last_updated = get_last_updated()
inventory_last_updated = get_inventory_last_updated()

print(f"Inventory items: {len(inventory)}")
print(f"Blueprints (after deduplication): {len(blueprints)}")
print(f"Blueprints last updated: {blueprints_last_updated}")
print(f"Inventory last updated: {inventory_last_updated}")
print()

# Read HTML file
print(f"Reading {HTML_FILE}...")
with open(HTML_FILE, 'r', encoding='utf-8') as f:
    html_content = f.read()

# Update EMBEDDED_DATA section
print("Updating embedded data...")

# Create new EMBEDDED_DATA
new_embedded_data = {
    "inventory": inventory,
    "blueprintsLastUpdated": blueprints_last_updated,
    "inventoryLastUpdated": inventory_last_updated
}

# Find and replace EMBEDDED_DATA (using a more robust pattern that handles nested objects)
pattern = r'const EMBEDDED_DATA = \{.*?\n\s*\};'
replacement = f'const EMBEDDED_DATA = {json.dumps(new_embedded_data, indent=12)};'

html_content = re.sub(pattern, replacement, html_content, flags=re.DOTALL)

# Create blueprint data JavaScript
blueprint_js = "BLUEPRINT_DATA = " + json.dumps(blueprints, indent=12) + ";"

# Find and replace existing BLUEPRINT_DATA (including any existing content)
pattern_bp = r'let BLUEPRINT_DATA = \[[\s\S]*?\];'
html_content = re.sub(pattern_bp, f'let {blueprint_js}', html_content, flags=re.DOTALL)

# Write updated HTML
print(f"Writing updated {HTML_FILE}...")
with open(HTML_FILE, 'w', encoding='utf-8') as f:
    f.write(html_content)

print()
print("=" * 60)
print("SUCCESS!")
print("=" * 60)
print(f"[OK] Blueprint timestamp: {blueprints_last_updated}")
print(f"[OK] Inventory timestamp: {inventory_last_updated}")
print(f"[OK] Blueprints deduplicated: {len(blueprints)} unique BPOs")
print(f"[OK] {HTML_FILE} updated successfully")
print()
print("Refresh your browser to see the changes!")
