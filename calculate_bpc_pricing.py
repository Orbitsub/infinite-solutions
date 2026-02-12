"""
Blueprint Copy Service Pricing Calculator
Using Quality-Based Pricing Formula

Pricing Formula:
- Base Price = Job Cost + (Runs × Jita Daily Avg Sell × 2%)
- Quality Multiplier = 0.25 + (ME/10 × 0.60) + (TE/20 × 0.15)
- Final Price = Base Price × Quality Multiplier

Features:
- Uses daily average Jita sell prices (resistant to manipulation)
- Scales pricing by ME/TE quality
- Accounts for facility bonuses (Azbel in LX-ZOJ)
"""
import sqlite3
import requests
import json
from datetime import datetime

# Configuration
DB_PATH = 'mydatabase.db'
JITA_STATION_ID = 60003760  # Jita IV - Moon 4 - Caldari Navy Assembly Plant
LX_ZOJ_SYSTEM_ID = 30002458
FACILITY_COST_REDUCTION = 0.21  # 21% cost reduction from rig
FACILITY_TAX = 0.05  # 5% facility tax
BASE_PERCENTAGE = 0.02  # 2% of Jita sell value

# ESI endpoints
ADJUSTED_PRICES_URL = "https://esi.evetech.net/latest/markets/prices/"
COST_INDICES_URL = "https://esi.evetech.net/latest/industry/systems/"

def get_jita_sell_prices():
    """Get daily average Jita sell prices from market_orders table."""
    print("Loading Jita sell prices from database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get average sell price per type_id (sell orders only, not buy orders)
    cursor.execute("""
        SELECT type_id, AVG(price) as avg_price
        FROM market_orders
        WHERE location_id = ?
          AND is_buy_order = 0
        GROUP BY type_id
    """, (JITA_STATION_ID,))

    prices = {}
    for row in cursor.fetchall():
        type_id, avg_price = row
        prices[type_id] = avg_price

    conn.close()
    print(f"  Loaded {len(prices)} Jita sell prices")
    return prices

def get_blueprint_product_mapping():
    """Get mapping of blueprint_type_id -> product_type_id from SDE."""
    print("Loading blueprint product mappings...")
    mapping = {}

    with open('sde/blueprints.jsonl', 'r') as f:
        for line in f:
            bp = json.loads(line)
            bp_type_id = bp['blueprintTypeID']

            if 'manufacturing' in bp.get('activities', {}):
                products = bp['activities']['manufacturing'].get('products', [])
                if products:
                    product_type_id = products[0]['typeID']
                    mapping[bp_type_id] = product_type_id

    print(f"  Loaded {len(mapping)} blueprint mappings")
    return mapping

def get_adjusted_prices():
    """Fetch adjusted prices (EIV) from ESI for job cost calculation."""
    print("Fetching adjusted prices from ESI...")
    response = requests.get(ADJUSTED_PRICES_URL)
    response.raise_for_status()

    prices = {}
    for item in response.json():
        if 'adjusted_price' in item:
            prices[item['type_id']] = item['adjusted_price']

    print(f"  Loaded {len(prices)} adjusted prices")
    return prices

def get_system_cost_index(system_id):
    """Fetch copying cost index for LX-ZOJ."""
    print(f"Fetching cost index for system {system_id}...")
    response = requests.get(COST_INDICES_URL)
    response.raise_for_status()

    for system in response.json():
        if system['solar_system_id'] == system_id:
            for activity in system.get('cost_indices', []):
                if activity['activity'] == 'copying':
                    cost_index = activity['cost_index']
                    print(f"  LX-ZOJ copying cost index: {cost_index:.4f}")
                    return cost_index

    print(f"  Warning: No cost index found, using 1.0")
    return 1.0

def calculate_quality_multiplier(me, te):
    """
    Calculate quality multiplier based on ME/TE levels.

    Formula: 0.25 + (ME/10 × 0.60) + (TE/20 × 0.15)

    Returns value between 0.25 (unresearched) and 1.0 (perfect 10/20)
    """
    me_factor = me / 10.0
    te_factor = te / 20.0
    return 0.25 + (me_factor * 0.60) + (te_factor * 0.15)

def calculate_job_cost(product_type_id, runs, copies, adjusted_prices, system_cost_index):
    """Calculate the actual EVE job cost with facility bonuses."""
    eiv = adjusted_prices.get(product_type_id, 0)
    if eiv == 0:
        return None

    # Base EVE cost
    base_cost = eiv * 0.02 * runs * copies * system_cost_index

    # Apply rig bonus
    cost_after_rig = base_cost * (1 - FACILITY_COST_REDUCTION)

    # Apply facility tax
    cost_after_tax = cost_after_rig * (1 + FACILITY_TAX)

    return cost_after_tax

def calculate_bpc_price(blueprint_type_id, product_type_id, me, te, runs, copies,
                       jita_sell_price, adjusted_prices, system_cost_index):
    """
    Calculate BPC service price using quality-based formula.

    Returns dict with pricing breakdown.
    """
    # Calculate job cost
    job_cost = calculate_job_cost(product_type_id, runs, copies, adjusted_prices, system_cost_index)
    if job_cost is None:
        return None

    # Calculate quality multiplier
    quality = calculate_quality_multiplier(me, te)

    # Calculate base price (before quality adjustment)
    # Base = Job Cost + (Runs × Copies × Jita Sell × 2%)
    value_component = runs * copies * jita_sell_price * BASE_PERCENTAGE
    base_price = job_cost + value_component

    # Apply quality multiplier
    final_price = base_price * quality

    return {
        'job_cost': job_cost,
        'value_component': value_component,
        'base_price': base_price,
        'quality_multiplier': quality,
        'quality_percent': quality * 100,
        'final_price': final_price,
        'jita_sell_price': jita_sell_price,
        'me': me,
        'te': te
    }

def get_character_blueprints():
    """Get all blueprints from character with ME/TE levels."""
    print("Loading character blueprints...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT type_id, type_name, material_efficiency, time_efficiency
        FROM character_blueprints
        WHERE runs = -1
        ORDER BY type_name
    """)

    blueprints = []
    for row in cursor.fetchall():
        blueprints.append({
            'type_id': row[0],
            'name': row[1],
            'me': row[2],
            'te': row[3]
        })

    conn.close()
    print(f"  Loaded {len(blueprints)} blueprints")
    return blueprints

def format_isk(amount):
    """Format ISK amount."""
    if amount is None:
        return "N/A"
    if amount >= 1_000_000:
        return f"{amount/1_000_000:.2f}M ISK"
    elif amount >= 1_000:
        return f"{amount/1_000:.1f}k ISK"
    else:
        return f"{amount:.0f} ISK"

def main():
    print("=" * 80)
    print("BLUEPRINT COPY SERVICE - QUALITY-BASED PRICING")
    print("=" * 80)
    print()

    # Load all data
    jita_prices = get_jita_sell_prices()
    bp_product_map = get_blueprint_product_mapping()
    adjusted_prices = get_adjusted_prices()
    system_cost_index = get_system_cost_index(LX_ZOJ_SYSTEM_ID)
    character_bps = get_character_blueprints()

    print()
    print("=" * 80)
    print("SAMPLE PRICING (10 runs, 1 copy)")
    print("=" * 80)

    # Sample pricing for first 10 blueprints that have market data
    samples = []
    for bp in character_bps[:50]:  # Check first 50
        product_id = bp_product_map.get(bp['type_id'])
        if not product_id:
            continue

        jita_price = jita_prices.get(product_id)
        if not jita_price:
            continue

        pricing = calculate_bpc_price(
            bp['type_id'], product_id,
            bp['me'], bp['te'],
            10, 1,  # 10 runs, 1 copy
            jita_price, adjusted_prices, system_cost_index
        )

        if pricing:
            samples.append({
                'name': bp['name'],
                'pricing': pricing
            })

        if len(samples) >= 10:
            break

    print()
    print(f"{'Blueprint':<30} {'ME/TE':<8} {'Quality':<8} {'Jita Sell':<12} {'Price (10 runs)':<15}")
    print("-" * 80)

    for sample in samples:
        name = sample['name'].replace(' Blueprint', '')[:28]
        p = sample['pricing']
        print(f"{name:<30} {p['me']}/{p['te']:<6} {p['quality_percent']:>5.1f}% {format_isk(p['jita_sell_price']):>12} {format_isk(p['final_price']):>15}")

    print()
    print("=" * 80)
    print("DETAILED EXAMPLE: First Blueprint")
    print("=" * 80)
    if samples:
        sample = samples[0]
        p = sample['pricing']
        print(f"\nBlueprint: {sample['name']}")
        print(f"Quality: ME {p['me']} / TE {p['te']} = {p['quality_percent']:.1f}%")
        print(f"Jita Sell (daily avg): {format_isk(p['jita_sell_price'])}")
        print()
        print("Cost Breakdown:")
        print(f"  1. Job Cost (EVE + facility):      {format_isk(p['job_cost'])}")
        print(f"  2. Value Component (10 × 2%):      {format_isk(p['value_component'])}")
        print(f"  3. Base Price (1 + 2):             {format_isk(p['base_price'])}")
        print(f"  4. Quality Multiplier:             ×{p['quality_multiplier']:.3f}")
        print(f"  5. FINAL CUSTOMER PRICE:           {format_isk(p['final_price'])}")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
