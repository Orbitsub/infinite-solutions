"""
Blueprint Copy Service Pricing Calculator
Using Quality-Based Pricing Formula

Pricing Formula:
- Per Run = Jita 7-day Avg Best Sell × 1% × Quality Multiplier
- Quality Multiplier = 0.25 + (ME/10 × 0.60) + (TE/20 × 0.15)
- At 100% quality (ME 10 / TE 20): per run = 1% of Jita best sell

Price Source:
- Primary: 7-day average of best_sell snapshots from market_price_snapshots
- Fallback: MIN(price) from current market_orders (for items without snapshot history)
"""
import sqlite3
import json
from datetime import datetime, timezone, timedelta

# Configuration
DB_PATH = 'mydatabase.db'
JITA_STATION_ID = 60003760  # Jita IV - Moon 4 - Caldari Navy Assembly Plant
BASE_PERCENTAGE = 0.01  # 1% of Jita best sell at 100% quality


def get_jita_sell_prices():
    """
    Get Jita best sell prices for BPC product pricing.
    Uses 7-day average of best_sell snapshots where available,
    falls back to MIN(price) from current market_orders.
    """
    print("Loading Jita best sell prices...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Primary: 7-day avg of best_sell from snapshots
    cursor.execute("""
        SELECT type_id, AVG(best_sell) as avg_best_sell, COUNT(*) as snapshots
        FROM market_price_snapshots
        WHERE timestamp >= ? AND best_sell IS NOT NULL
        GROUP BY type_id
    """, (seven_days_ago,))

    prices = {}
    snapshot_count = 0
    for type_id, avg_best_sell, count in cursor.fetchall():
        prices[type_id] = avg_best_sell
        snapshot_count += 1

    # Fallback: MIN(price) from current market_orders for items not in snapshots
    cursor.execute("""
        SELECT type_id, MIN(price) as best_sell
        FROM market_orders
        WHERE location_id = ? AND is_buy_order = 0
        GROUP BY type_id
    """, (JITA_STATION_ID,))

    fallback_count = 0
    for type_id, best_sell in cursor.fetchall():
        if type_id not in prices:
            prices[type_id] = best_sell
            fallback_count += 1

    conn.close()
    print(f"  {snapshot_count} from snapshots, {fallback_count} from live market fallback")
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


def calculate_quality_multiplier(me, te):
    """
    Calculate quality multiplier based on ME/TE levels.

    Formula: 0.25 + (ME/10 × 0.60) + (TE/20 × 0.15)

    Returns value between 0.25 (unresearched) and 1.0 (perfect 10/20)
    """
    me_factor = me / 10.0
    te_factor = te / 20.0
    return 0.25 + (me_factor * 0.60) + (te_factor * 0.15)


def calculate_bpc_price(blueprint_type_id, product_type_id, me, te, runs, copies,
                       jita_sell_price):
    """
    Calculate BPC service price.

    Formula: per_run = jita_best_sell × 1% × quality
    Total = per_run × runs × copies
    """
    quality = calculate_quality_multiplier(me, te)
    per_run = jita_sell_price * BASE_PERCENTAGE * quality
    final_price = per_run * runs * copies

    return {
        'quality_multiplier': quality,
        'quality_percent': quality * 100,
        'per_run': per_run,
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
    print("BLUEPRINT COPY SERVICE - PRICING (1% of Jita Best Sell)")
    print("=" * 80)
    print()

    # Load all data
    jita_prices = get_jita_sell_prices()
    bp_product_map = get_blueprint_product_mapping()
    character_bps = get_character_blueprints()

    print()
    print("=" * 80)
    print("SAMPLE PRICING (10 runs, 1 copy)")
    print("=" * 80)

    # Sample pricing for first 10 blueprints that have market data
    samples = []
    for bp in character_bps[:50]:
        product_id = bp_product_map.get(bp['type_id'])
        if not product_id:
            continue

        jita_price = jita_prices.get(product_id)
        if not jita_price:
            continue

        pricing = calculate_bpc_price(
            bp['type_id'], product_id,
            bp['me'], bp['te'],
            10, 1,
            jita_price
        )

        if pricing:
            samples.append({
                'name': bp['name'],
                'pricing': pricing
            })

        if len(samples) >= 10:
            break

    print()
    print(f"{'Blueprint':<30} {'ME/TE':<8} {'Quality':<8} {'Jita Best Sell':<15} {'Per Run':<12} {'10-Run BPC':<12}")
    print("-" * 90)

    for sample in samples:
        name = sample['name'].replace(' Blueprint', '')[:28]
        p = sample['pricing']
        print(f"{name:<30} {p['me']}/{p['te']:<6} {p['quality_percent']:>5.1f}% {format_isk(p['jita_sell_price']):>15} {format_isk(p['per_run']):>12} {format_isk(p['final_price']):>12}")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
