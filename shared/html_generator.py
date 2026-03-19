"""
Generate corrected HTML with:
- ONLY the 35 tracked items (8 minerals, 7 ice, 20 moon)
- Full-width layout for large monitors
- Dynamic filters
- UTC timezone
- No "Research Time Remaining" column
"""
import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), 'mydatabase.db')
ORIGINAL_HTML = os.path.join(os.path.dirname(__file__), 'index.html')

# The exact 35 items from original index.html
MINERALS = [
    'Tritanium', 'Pyerite', 'Isogen', 'Mexallon',
    'Nocxium', 'Zydrine', 'Megacyte', 'Morphite'
]

ICE_PRODUCTS = [
    'Heavy Water', 'Liquid Ozone', 'Strontium Clathrates',
    'Oxygen Isotopes', 'Hydrogen Isotopes', 'Helium Isotopes', 'Nitrogen Isotopes'
]

MOON_MATERIALS = {
    'R4 - Ubiquitous': ['Atmospheric Gases', 'Evaporite Deposits', 'Hydrocarbons', 'Silicates'],
    'R8 - Common': ['Cobalt', 'Scandium', 'Tungsten', 'Titanium'],
    'R16 - Uncommon': ['Chromium', 'Cadmium', 'Platinum', 'Vanadium'],
    'R32 - Rare': ['Technetium', 'Mercury', 'Caesium', 'Hafnium'],
    'R64 - Exceptional': ['Promethium', 'Neodymium', 'Dysprosium', 'Thulium']
}

def get_inventory_data():
    """Get current inventory for all tracked items."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT type_name, quantity FROM lx_zoj_current_inventory")

    inventory = {}
    for type_name, quantity in cursor.fetchall():
        inventory[type_name] = quantity

    conn.close()
    return inventory

def get_market_group_path(cursor, market_group_id):
    """Get full market group hierarchy path as a list."""
    if not market_group_id:
        return []

    path = []
    current_id = market_group_id

    # Prevent infinite loops (max 10 levels)
    for _ in range(10):
        cursor.execute(
            'SELECT market_group_name, parent_group_id FROM inv_market_groups WHERE market_group_id = ?',
            (current_id,)
        )
        result = cursor.fetchone()

        if not result:
            break

        market_group_name, parent_id = result
        path.insert(0, market_group_name)

        if not parent_id:
            break

        current_id = parent_id

    return path

def get_blueprint_category_by_market_group(cursor, market_group_id):
    """
    Get blueprint category using market group hierarchy.
    Returns category based on top-level market group under 'Blueprints & Reactions'.
    This is more reliable than string matching.
    """
    if not market_group_id:
        return None

    # Market group ID mappings for top-level blueprint categories
    # (Direct children of market_group_id 2: 'Blueprints & Reactions')
    MARKET_GROUP_CATEGORIES = {
        204: 'Ships',                    # Ships
        209: 'Modules',                  # Ship Equipment
        943: 'Rigs',                     # Ship Modifications
        211: 'Ammunition',               # Ammunition & Charges
        357: 'Drones',                   # Drones
        1338: 'Structures',              # Structures
        2158: 'Modules',                 # Structure Equipment (structure modules)
        2157: 'Rigs',                    # Structure Modifications (structure rigs)
        1849: 'Reactions',               # Reaction Formulas
        1041: 'Components',              # Manufacture & Research (components)
        # Special cases (sub-categories that need different classification)
        339: 'Modules',                  # Cap Booster Charges (are capacitor modules, not ammo)
    }

    # Walk up the market group hierarchy to find the top-level category
    current_id = market_group_id
    for _ in range(10):  # Prevent infinite loops
        # Check if this is a known top-level category
        if current_id in MARKET_GROUP_CATEGORIES:
            return MARKET_GROUP_CATEGORIES[current_id]

        # Get parent
        cursor.execute(
            'SELECT parent_group_id FROM inv_market_groups WHERE market_group_id = ?',
            (current_id,)
        )
        result = cursor.fetchone()

        if not result or not result[0]:
            break

        current_id = result[0]

    return None

def get_blueprints_with_metadata():
    """Get all BPOs with proper categorization using market groups.
    Deduplicates: keeps best ME/TE version (prefer 10/20, else highest ME)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
        SELECT
            b.type_id,
            b.type_name,
            b.material_efficiency as ME,
            b.time_efficiency as TE,
            COALESCE(g.group_name, 'Unknown') as group_name,
            t.market_group_id
        FROM character_blueprints b
        LEFT JOIN inv_types t ON b.type_id = t.type_id
        LEFT JOIN inv_groups g ON t.group_id = g.group_id
        WHERE b.runs = -1
        ORDER BY b.type_name, b.material_efficiency DESC, b.time_efficiency DESC
    """

    cursor.execute(query)
    results = cursor.fetchall()

    # Deduplicate: keep only best version of each blueprint
    bp_dict = {}
    for row in results:
        type_id = row[0]
        bp_name = row[1]
        me = row[2]
        te = row[3]
        group_name = row[4]
        market_group_id = row[5]

        # Get market group hierarchy
        market_path = get_market_group_path(cursor, market_group_id)

        # Categorize using market group ID (most reliable), with override support
        category = categorize_blueprint(group_name, bp_name, market_path, type_id, market_group_id, cursor)
        subcategory = get_subcategory(group_name, bp_name, market_path, type_id)

        # Check if we already have this blueprint
        if bp_name in bp_dict:
            existing = bp_dict[bp_name]
            # Keep perfect (10/20) if it exists
            if me == 10 and te == 20:
                bp_dict[bp_name] = {'name': bp_name, 'me': me, 'te': te, 'category': category, 'subcategory': subcategory}
            elif existing['me'] == 10 and existing['te'] == 20:
                # Already have perfect, skip this one
                continue
            elif me > existing['me']:
                # Higher ME, replace
                bp_dict[bp_name] = {'name': bp_name, 'me': me, 'te': te, 'category': category, 'subcategory': subcategory}
        else:
            bp_dict[bp_name] = {'name': bp_name, 'me': me, 'te': te, 'category': category, 'subcategory': subcategory}

    conn.close()
    return list(bp_dict.values())

def get_category_override(type_id):
    """Check if there's a manual category override for this blueprint."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, subcategory
        FROM blueprint_category_overrides
        WHERE type_id = ?
    """, (type_id,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0], result[1]  # (category, subcategory)
    return None

def categorize_blueprint(group_name, bp_name, market_path=None, type_id=None, market_group_id=None, cursor=None):
    """
    Categorize blueprint using market group hierarchy, group name, and market path.
    Checks manual overrides first if type_id provided.
    Uses market group ID for most accurate categorization.
    """
    # Check for manual override first
    if type_id:
        override = get_category_override(type_id)
        if override:
            return override[0]  # Just return category, subcategory handled separately

    # Try market group ID based categorization first (most reliable)
    if market_group_id and cursor:
        category = get_blueprint_category_by_market_group(cursor, market_group_id)
        if category:
            return category

    # Fallback to string matching if market group didn't work
    group_lower = group_name.lower()
    name_lower = bp_name.lower()
    market_str = ' '.join(market_path).lower() if market_path else ''

    # Use market groups for better categorization
    if market_path:
        # Ships (but exclude "ship equipment" which is modules)
        if 'ship equipment' not in market_str and any(x in market_str for x in ['ship', 'frigate', 'destroyer', 'cruiser', 'battleship', 'carrier', 'dreadnought', 'titan', 'supercarrier', 'industrial']):
            return 'Ships'

        # Cap Boosters are modules, not ammunition
        if 'cap booster' in market_str:
            return 'Modules'

        # Ammunition (check market path first)
        if 'ammunition' in market_str or 'charges' in market_str:
            return 'Ammunition'

        # Drones
        if 'drone' in market_str:
            return 'Drones'

        # Rigs
        if 'rig' in market_str:
            return 'Rigs'

        # Modules (from market groups)
        if any(x in market_str for x in ['module', 'electronic systems', 'engineering equipment', 'hull & armor', 'propulsion', 'shield', 'targeting', 'turrets & bays', 'weapon upgrades']):
            return 'Modules'

        # Components
        if 'component' in market_str or 'composite' in market_str:
            return 'Components'

        # Structures
        if 'structure' in market_str or 'deployable' in market_str:
            return 'Structures'

        # Reactions
        if 'reaction' in market_str:
            return 'Reactions'

    # Fallback to group name based categorization
    # Ship categories
    if any(x in group_lower for x in ['frigate', 'destroyer', 'cruiser', 'battlecruiser', 'battleship', 'titan', 'dreadnought', 'carrier', 'supercarrier', 'industrial']):
        return 'Ships'

    # Rigs
    if 'rig' in group_lower or 'rig' in name_lower:
        return 'Rigs'

    # Ammunition
    if any(x in group_lower for x in ['charge', 'missile', 'bomb', 'ammunition', 'ammo']):
        return 'Ammunition'

    # Drones
    if 'drone' in group_lower:
        return 'Drones'

    # Components
    if any(x in group_lower for x in ['component', 'composite']):
        return 'Components'

    # Modules
    if any(x in group_lower for x in ['module', 'weapon', 'armor', 'shield', 'propulsion', 'capacitor']):
        return 'Modules'

    # Structures
    if any(x in group_lower for x in ['citadel', 'engineering complex', 'structure']):
        return 'Structures'

    # Reactions
    if 'reaction' in group_lower or 'formula' in name_lower:
        return 'Reactions'

    return 'Other'

def get_subcategory(group_name, bp_name, market_path=None, type_id=None):
    """Get detailed sub-category using group name and market path.
    Checks manual overrides first if type_id provided."""
    # Check for manual override first
    if type_id:
        override = get_category_override(type_id)
        if override:
            return override[1]  # Return subcategory from override

    group_lower = group_name.lower()
    name_lower = bp_name.lower()
    market_str = ' '.join(market_path).lower() if market_path else ''

    # Use market path for better subcategorization
    if market_path and len(market_path) >= 2:
        # For ammunition, use the parent market group (e.g., "Hybrid Charges", "Projectile Ammo")
        if 'ammunition' in market_str or 'charges' in market_str:
            for segment in market_path:
                if 'hybrid' in segment.lower():
                    return 'Hybrid Charges'
                elif 'projectile' in segment.lower():
                    return 'Projectile Charges'
                elif 'missile' in segment.lower():
                    if 'rocket' in name_lower:
                        return 'Rockets'
                    elif 'torpedo' in name_lower or 'bomb' in name_lower:
                        return 'Torpedoes & Bombs'
                    return 'Missiles'
                elif 'frequency' in segment.lower() or 'crystal' in segment.lower():
                    return 'Frequency Crystals'
                elif 'bomb' in segment.lower():
                    return 'Bombs'

        # For ships, use market group
        if 'ship' in market_str:
            for segment in market_path:
                seg_lower = segment.lower()
                if 'frigate' in seg_lower:
                    return 'Frigate'
                elif 'destroyer' in seg_lower:
                    return 'Destroyer'
                elif 'cruiser' in seg_lower and 'battle' not in seg_lower:
                    return 'Cruiser'
                elif 'battlecruiser' in seg_lower:
                    return 'Battlecruiser'
                elif 'battleship' in seg_lower:
                    return 'Battleship'
                elif 'industrial' in seg_lower:
                    if 'command' in seg_lower:
                        return 'Industrial Command Ship'
                    return 'Industrial'
                elif any(x in seg_lower for x in ['capital', 'carrier', 'dreadnought', 'titan', 'supercarrier']):
                    return 'Capital Ship'

    # Fallback to group-based logic
    # Ships - by size class
    if 'frigate' in group_lower:
        return 'Frigate'
    elif 'destroyer' in group_lower:
        return 'Destroyer'
    elif 'cruiser' in group_lower and 'battle' not in group_lower:
        return 'Cruiser'
    elif 'battlecruiser' in group_lower:
        return 'Battlecruiser'
    elif 'battleship' in group_lower:
        return 'Battleship'
    elif 'industrial' in group_lower:
        if 'command' in group_lower:
            return 'Industrial Command Ship'
        return 'Industrial'
    elif any(x in group_lower for x in ['dreadnought', 'titan', 'carrier', 'supercarrier', 'force auxiliary']):
        return 'Capital Ship'

    # Ammunition types
    elif 'hybrid' in group_lower and ('charge' in group_lower or 'ammo' in group_lower):
        return 'Hybrid Charges'
    elif 'projectile' in group_lower and ('charge' in group_lower or 'ammo' in group_lower):
        return 'Projectile Charges'
    elif 'frequency' in group_lower or ('advanced' in group_lower and ('laser' in name_lower or 'beam' in name_lower or 'pulse' in name_lower)):
        return 'Frequency Crystals'
    elif 'missile' in group_lower:
        if 'rocket' in name_lower:
            return 'Rockets'
        elif 'torpedo' in name_lower or 'bomb' in name_lower:
            return 'Torpedoes & Bombs'
        return 'Missiles'
    elif 'bomb' in group_lower:
        return 'Bombs'

    # Drones by size
    elif 'drone' in group_lower:
        if 'light' in group_lower or 'light' in name_lower:
            return 'Light Drones'
        elif 'medium' in group_lower or 'medium' in name_lower:
            return 'Medium Drones'
        elif 'heavy' in group_lower or 'heavy' in name_lower:
            return 'Heavy Drones'
        elif 'fighter' in group_lower:
            return 'Fighters'
        return 'Drones'

    # Modules by type
    elif any(x in group_lower for x in ['armor', 'shield', 'hull']):
        if 'armor' in group_lower:
            return 'Armor Modules'
        elif 'shield' in group_lower:
            return 'Shield Modules'
        return 'Defense Modules'
    elif any(x in group_lower for x in ['weapon', 'turret', 'launcher']):
        return 'Weapon Modules'
    elif 'propulsion' in group_lower or 'afterburner' in name_lower or 'microwarpdrive' in name_lower:
        return 'Propulsion Modules'
    elif 'capacitor' in group_lower or 'cap booster' in name_lower:
        return 'Capacitor Modules'
    elif 'electronic' in group_lower or 'ewar' in name_lower:
        return 'Electronic Warfare'

    # Rigs by type
    elif 'rig' in group_lower:
        if 'armor' in group_lower or 'armor' in name_lower:
            return 'Armor Rigs'
        elif 'shield' in group_lower or 'shield' in name_lower:
            return 'Shield Rigs'
        elif 'astronautic' in group_lower or 'speed' in name_lower or 'warp' in name_lower:
            return 'Astronautic Rigs'
        elif 'weapon' in name_lower or 'gunnery' in name_lower or 'launcher' in name_lower:
            return 'Weapon Rigs'
        return 'Rigs'

    # Components
    elif 'component' in group_lower or 'composite' in group_lower:
        if 'capital' in group_lower or 'capital' in name_lower:
            return 'Capital Components'
        elif 'station' in group_lower or 'structure' in name_lower:
            return 'Structure Components'
        return 'Ship Components'

    # Structures
    elif any(x in group_lower for x in ['citadel', 'engineering complex', 'structure']):
        if 'citadel' in group_lower:
            return 'Citadels'
        elif 'engineering' in group_lower:
            return 'Engineering Complexes'
        return 'Structures'

    # Reactions
    elif 'reaction' in group_lower or 'formula' in name_lower:
        return 'Reactions'

    # Default: use the group name or "Uncategorized"
    return group_name if group_name and group_name != 'Unknown' else 'Uncategorized'

def get_last_updated():
    """Get last updated timestamp for blueprints in UTC (EVE Time)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(last_updated) FROM character_blueprints")
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        # Parse ISO format timestamp from database
        timestamp_str = result[0]

        # Handle different ISO format variations
        if 'Z' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        elif '+' in timestamp_str or timestamp_str.endswith('00:00'):
            dt = datetime.fromisoformat(timestamp_str)
        else:
            # No timezone info, assume UTC
            dt = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)

        # Convert to UTC if it's not already
        if dt.tzinfo is not None and dt.tzinfo != timezone.utc:
            dt = dt.astimezone(timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Format as EVE Time (UTC) - 24-hour format
        return dt.strftime('%b %d, %Y %H:%M') + ' EVE'

    return datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M') + ' EVE'

def get_inventory_last_updated():
    """Get last updated timestamp for inventory in UTC (EVE Time)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory")
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        # Parse ISO format timestamp from database
        timestamp_str = result[0]

        # Handle different ISO format variations
        if 'Z' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        elif '+' in timestamp_str or timestamp_str.endswith('00:00'):
            dt = datetime.fromisoformat(timestamp_str)
        else:
            # No timezone info, assume UTC
            dt = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)

        # Convert to UTC if it's not already
        if dt.tzinfo is not None and dt.tzinfo != timezone.utc:
            dt = dt.astimezone(timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Format as EVE Time (UTC) - 24-hour format
        return dt.strftime('%b %d, %Y %H:%M') + ' EVE'

    return datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M') + ' EVE'

print("Generating corrected HTML...")
print(f"Last updated: {get_last_updated()}")

# Continue with HTML generation...
print("\n[OK] Script ready - will generate full HTML")
