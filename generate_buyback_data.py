"""
Generate buyback_data.js from the database.
Reads tracked_market_items and market_price_snapshots to produce
a JavaScript data file with item rates, quotas, and 7-day avg Jita buy prices.
"""
import sqlite3
import os
import json
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'mydatabase.db')

# Map DB category names to display names
CATEGORY_DISPLAY = {
    'minerals': 'Minerals',
    'ice_products': 'Ice Products',
    'moon_materials': 'Reaction Materials',
}


def get_buyback_data():
    """Query the database and build the buyback data structure."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all tracked items with buyback info
    cursor.execute("""
        SELECT type_id, type_name, category, display_order,
               price_percentage, buyback_accepted, buyback_rate, buyback_quota
        FROM tracked_market_items
        ORDER BY category, display_order
    """)
    items = cursor.fetchall()

    # Get 7-day average Jita buy prices from snapshots
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    cursor.execute("""
        SELECT type_id, AVG(best_buy) as avg_buy
        FROM market_price_snapshots
        WHERE timestamp >= ?
        GROUP BY type_id
    """, (seven_days_ago,))
    avg_prices = {row[0]: round(row[1], 2) for row in cursor.fetchall() if row[1] is not None}

    # Get category visibility from site_config
    cursor.execute("""
        SELECT key, value FROM site_config
        WHERE key LIKE 'buyback_category_%_visible'
    """)
    category_visibility = {}
    for key, value in cursor.fetchall():
        # Extract category name from key like 'buyback_category_minerals_visible'
        cat = key.replace('buyback_category_', '').replace('_visible', '')
        category_visibility[cat] = value == '1'

    conn.close()

    # Build output data
    buyback_items = []
    for type_id, type_name, category, display_order, price_pct, accepted, rate, quota in items:
        # Use buyback_rate if set, otherwise fall back to price_percentage
        effective_rate = rate if rate is not None else price_pct

        buyback_items.append({
            'typeId': type_id,
            'name': type_name,
            'category': category,
            'displayCategory': CATEGORY_DISPLAY.get(category, category),
            'rate': effective_rate,
            'accepted': bool(accepted),
            'quota': quota or 0,
            'avgJitaBuy': avg_prices.get(type_id, 0),
        })

    # Build category config
    categories = {}
    for cat_key, display_name in CATEGORY_DISPLAY.items():
        visible = category_visibility.get(cat_key, True)
        categories[cat_key] = {
            'displayName': display_name,
            'visible': visible,
        }

    return {
        'items': buyback_items,
        'categories': categories,
        'generated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    }


def main():
    print("Generating buyback data from database...")
    data = get_buyback_data()

    # Count stats
    total = len(data['items'])
    accepted = sum(1 for i in data['items'] if i['accepted'])
    with_prices = sum(1 for i in data['items'] if i['avgJitaBuy'] > 0)

    print(f"  Items: {total} total, {accepted} accepting, {with_prices} with price data")

    # Write to buyback_data.js
    output_path = os.path.join(os.path.dirname(__file__), 'buyback_data.js')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('// Auto-generated buyback program data\n')
        f.write(f'// Generated: {data["generated"]}\n')
        f.write('const BUYBACK_DATA = ')
        f.write(json.dumps(data, indent=2))
        f.write(';\n')

    print(f"  Written to: buyback_data.js")
    print("Done!")


if __name__ == '__main__':
    main()
