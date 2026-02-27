"""
Update blueprint_data.js with deduplicated blueprint data.
"""
import sys
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from generate_corrected_html import get_blueprints_with_metadata
import json

print("Fetching deduplicated blueprint data from database...")
blueprints = get_blueprints_with_metadata()

print(f"Blueprints after deduplication: {len(blueprints)}")
print()

# Check for any remaining duplicates
names = [bp['name'] for bp in blueprints]
duplicates = [name for name in names if names.count(name) > 1]
if duplicates:
    print("WARNING: Still found duplicates:")
    for dup in set(duplicates):
        print(f"  - {dup}")
        matching = [bp for bp in blueprints if bp['name'] == dup]
        for bp in matching:
            print(f"    ME: {bp['me']}, TE: {bp['te']}")
    print()
else:
    print("No duplicates found!")
    print()

# Write to assets/blueprint_data.js
output_path = os.path.join(PROJECT_DIR, 'assets', 'blueprint_data.js')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('// Auto-generated blueprint data with deduplication\n')
    f.write('// Only best ME/TE version of each blueprint is included\n')
    f.write('BLUEPRINT_DATA = ')
    f.write(json.dumps(blueprints, indent=2))
    f.write(';')

print(f"{output_path} updated successfully with {len(blueprints)} unique blueprints!")
