#!/usr/bin/env python3
"""
================================================================================
ITEM REPROCESSING ARBITRAGE ANALYZER
================================================================================
Finds items on Jita market where reprocessing value exceeds purchase cost.
Similar to ore arbitrage, but for ANY reprocessable item (modules, ammo, etc.)

Author: Hamektok Hakaari
Created: January 26, 2026
================================================================================
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ============================================================================
# CONFIGURABLE PARAMETERS - ADJUST THESE AS NEEDED
# ============================================================================
CONFIG = {
    # DATABASE
    'database_path': r'E:\Python Project\mydatabase.db',
    
    # REPROCESSING EFFICIENCY - UPDATE THESE BASED ON YOUR SKILLS!
    'base_reprocess_yield': 0.50,      # Base 50% yield (always this)
    'reprocessing_skill_bonus': 0.15,  # 3% per level (15% = Level V)
    'reprocessing_efficiency_bonus': 0.10,  # 2% per level (10% = Level V)
    'ore_processing_bonus': 0.00,      # Ore-specific skills don't apply to items!
    'implant_bonus': 0.00,             # 4% if you have RX-804 implant
    'structure_bonus': 0.06,           # ASK YOUR CORPMATE FOR TATARA BONUS!
    
    # TRADING FEES
    'broker_fee_pct': 0.015,           # 1.5% broker fee
    'sales_tax_pct': 0.01,             # 1% sales tax
    'reprocessing_tax_pct': 0.00,      # 0% in player structures
    
    # FREIGHT COSTS
    'freight_cost_per_m3': 400.0,      # ISK per m³ to null-sec
    
    # FILTERS - Adjust these to show more/fewer results
    'min_profit_margin_pct': 5.0,      # Minimum profit margin to show
    'min_profit_per_unit': 10000.0,    # Minimum ISK profit per unit
    'max_item_volume_m3': 10000.0,     # Skip huge items (e.g., assembled ships)
    
    # REGIONS
    'jita_region_id': 10000002,        # The Forge
    'jita_station_id': 60003760,       # Jita 4-4
    
    # MINERAL TYPE IDs
    'mineral_type_ids': {
        'Tritanium': 34,
        'Pyerite': 35,
        'Mexallon': 36,
        'Isogen': 37,
        'Nocxium': 38,
        'Zydrine': 39,
        'Megacyte': 40,
        'Morphite': 11399,
    },
    
    # OUTPUT OPTIONS
    'show_mineral_breakdown': True,    # Show mineral yields per item
    'show_only_profitable': True,      # Filter out unprofitable items
    'output_csv': True,                # Export results to CSV
    'csv_filename': 'reprocessing_arbitrage_results.csv',
}

# ============================================================================
# CALCULATE TOTAL REPROCESSING EFFICIENCY
# ============================================================================
def calculate_reprocessing_efficiency(config):
    """
    Calculate total reprocessing efficiency from skills and bonuses.
    
    Formula:
    Total = Base × (1 + Reprocessing + Efficiency + Implant + Structure)
    
    Example with max skills at T2 Tatara:
    50% × (1 + 15% + 10% + 0% + 6%) = 50% × 1.31 = 65.5%
    """
    efficiency = config['base_reprocess_yield']
    efficiency *= (1 + 
                   config['reprocessing_skill_bonus'] + 
                   config['reprocessing_efficiency_bonus'] +
                   config['ore_processing_bonus'] +
                   config['implant_bonus'] +
                   config['structure_bonus'])
    
    return efficiency

# ============================================================================
# GET 7-DAY AVERAGE MINERAL PRICES
# ============================================================================
def get_mineral_prices_7day(conn, config):
    """
    Fetch 7-day average mineral prices from market_history.
    Returns dict: {mineral_name: avg_price_7d}
    """
    mineral_prices = {}
    
    query = """
        SELECT 
            type_id,
            AVG(average) as avg_price_7d,
            MIN(average) as min_price_7d,
            MAX(average) as max_price_7d,
            COUNT(*) as data_points
        FROM market_history
        WHERE type_id = ?
        AND region_id = ?
        AND date >= date('now', '-7 days')
    """
    
    cursor = conn.cursor()
    
    for mineral_name, type_id in config['mineral_type_ids'].items():
        cursor.execute(query, (type_id, config['jita_region_id']))
        result = cursor.fetchone()
        
        if result and result[1] is not None:
            mineral_prices[mineral_name] = {
                'avg_price_7d': result[1],
                'min_price_7d': result[2],
                'max_price_7d': result[3],
                'data_points': result[4],
                'volatility_pct': ((result[3] - result[2]) / result[1] * 100) if result[1] > 0 else 0
            }
            print(f"  {mineral_name:12s}: {result[1]:10.2f} ISK (7d avg, {result[4]} data points)")
        else:
            print(f"  WARNING: No price data for {mineral_name}")
            mineral_prices[mineral_name] = {'avg_price_7d': 0}
    
    return mineral_prices

# ============================================================================
# GET REPROCESSABLE ITEMS FROM JITA MARKET
# ============================================================================
def get_reprocessable_items(conn, config):
    """
    Get all items currently on Jita market that have reprocessing yields.
    """
    query = """
        SELECT DISTINCT
            it.type_id,
            it.type_name,
            it.volume,
            it.group_id,
            ig.group_name
        FROM market_orders mo
        JOIN inv_types it ON it.type_id = mo.type_id
        JOIN inv_groups ig ON ig.group_id = it.group_id
        WHERE mo.region_id = ?
        AND mo.location_id = ?
        AND it.volume > 0
        AND it.volume <= ?
        ORDER BY it.type_name
    """
    
    cursor = conn.cursor()
    cursor.execute(query, (
        config['jita_region_id'],
        config['jita_station_id'],
        config['max_item_volume_m3']
    ))
    
    items = []
    for row in cursor.fetchall():
        items.append({
            'type_id': row[0],
            'type_name': row[1],
            'volume': row[2],
            'group_id': row[3],
            'group_name': row[4]
        })
    
    return items

# ============================================================================
# GET ITEM REPROCESSING YIELDS
# ============================================================================
def get_reprocessing_yields(conn, type_id):
    """
    Get reprocessing yields for a specific item.
    
    Returns dict: {mineral_name: quantity}
    """
    query = """
        SELECT
            tritanium_yield,
            pyerite_yield,
            mexallon_yield,
            isogen_yield,
            nocxium_yield,
            zydrine_yield,
            megacyte_yield,
            morphite_yield
        FROM item_reprocessing_yields
        WHERE type_id = ?
    """
    
    cursor = conn.cursor()
    cursor.execute(query, (type_id,))
    result = cursor.fetchone()
    
    if not result:
        return None
    
    return {
        'Tritanium': result[0] or 0,
        'Pyerite': result[1] or 0,
        'Mexallon': result[2] or 0,
        'Isogen': result[3] or 0,
        'Nocxium': result[4] or 0,
        'Zydrine': result[5] or 0,
        'Megacyte': result[6] or 0,
        'Morphite': result[7] or 0,
    }

# ============================================================================
# GET CURRENT JITA PRICES
# ============================================================================
def get_jita_prices(conn, type_id, config):
    """
    Get current best buy and sell prices for an item in Jita.
    """
    query = """
        SELECT
            MIN(CASE WHEN is_buy_order = 0 THEN price END) as best_sell_price,
            MAX(CASE WHEN is_buy_order = 1 THEN price END) as best_buy_price
        FROM market_orders
        WHERE type_id = ?
        AND region_id = ?
        AND location_id = ?
    """
    
    cursor = conn.cursor()
    cursor.execute(query, (type_id, config['jita_region_id'], config['jita_station_id']))
    result = cursor.fetchone()
    
    if result:
        return {
            'best_sell_price': result[0],
            'best_buy_price': result[1]
        }
    
    return {'best_sell_price': None, 'best_buy_price': None}

# ============================================================================
# CALCULATE REPROCESSING PROFIT
# ============================================================================
def calculate_reprocessing_profit(item, yields, mineral_prices, item_prices, config, efficiency):
    """
    Calculate profit from buying item, reprocessing, and selling minerals.
    """
    if not yields or not item_prices['best_sell_price']:
        return None
    
    # Calculate mineral value (7-day average prices)
    mineral_value = 0
    mineral_breakdown = {}
    
    for mineral_name, base_yield in yields.items():
        if base_yield > 0:
            # Apply reprocessing efficiency
            actual_yield = base_yield * efficiency
            mineral_price = mineral_prices.get(mineral_name, {}).get('avg_price_7d', 0)
            value = actual_yield * mineral_price
            mineral_value += value
            mineral_breakdown[mineral_name] = {
                'base_yield': base_yield,
                'actual_yield': actual_yield,
                'price': mineral_price,
                'value': value
            }
    
    # Calculate costs
    item_cost = item_prices['best_sell_price']  # Buy from sell orders (instant)
    freight_cost = item['volume'] * config['freight_cost_per_m3']
    broker_fee = item_cost * config['broker_fee_pct']  # If placing buy orders
    reprocess_tax = mineral_value * config['reprocessing_tax_pct']
    
    # Total cost (instant buy from sell orders)
    total_cost = item_cost + freight_cost + reprocess_tax
    
    # Revenue from selling minerals (need to pay sales tax)
    mineral_revenue_after_tax = mineral_value * (1 - config['sales_tax_pct'])
    
    # Profit calculation
    profit_per_unit = mineral_revenue_after_tax - total_cost
    profit_margin_pct = (profit_per_unit / total_cost * 100) if total_cost > 0 else 0
    
    return {
        'item_cost': item_cost,
        'freight_cost': freight_cost,
        'reprocess_tax': reprocess_tax,
        'total_cost': total_cost,
        'mineral_value_gross': mineral_value,
        'mineral_revenue_after_tax': mineral_revenue_after_tax,
        'profit_per_unit': profit_per_unit,
        'profit_margin_pct': profit_margin_pct,
        'mineral_breakdown': mineral_breakdown,
        'efficiency_used': efficiency
    }

# ============================================================================
# MAIN ANALYSIS
# ============================================================================
def analyze_reprocessing_arbitrage(config):
    """
    Main analysis function - finds profitable reprocessing opportunities.
    """
    print("=" * 80)
    print("ITEM REPROCESSING ARBITRAGE ANALYSIS")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Calculate reprocessing efficiency
    efficiency = calculate_reprocessing_efficiency(config)
    print(f"Reprocessing Efficiency: {efficiency * 100:.2f}%")
    print(f"  Base: {config['base_reprocess_yield'] * 100:.0f}%")
    print(f"  Reprocessing skill: +{config['reprocessing_skill_bonus'] * 100:.0f}%")
    print(f"  Efficiency skill: +{config['reprocessing_efficiency_bonus'] * 100:.0f}%")
    print(f"  Structure bonus: +{config['structure_bonus'] * 100:.0f}%")
    print(f"  Total multiplier: {(efficiency / config['base_reprocess_yield']):.2f}x\n")
    
    # Connect to database
    print(f"Connecting to database: {config['database_path']}")
    try:
        conn = sqlite3.connect(config['database_path'])
        print("✓ Connected successfully\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return
    
    # Check if reprocessing yields table exists
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='item_reprocessing_yields'
    """)
    
    if not cursor.fetchone():
        print("=" * 80)
        print("ERROR: item_reprocessing_yields table does not exist!")
        print("=" * 80)
        print("\nYou need to run the setup script first:")
        print("  python create_item_reprocessing_table_from_JSONL.py")
        conn.close()
        return
    
    # Get 7-day average mineral prices
    print("Fetching 7-day average mineral prices...")
    mineral_prices = get_mineral_prices_7day(conn, config)
    print()
    
    # Get items on Jita market
    print("Fetching items from Jita market...")
    items = get_reprocessable_items(conn, config)
    print(f"Found {len(items)} items on Jita market\n")
    
    # Analyze each item
    print("Analyzing reprocessing opportunities...")
    print("-" * 80)
    
    results = []
    items_analyzed = 0
    items_with_yields = 0
    profitable_items = 0
    
    for i, item in enumerate(items):
        items_analyzed += 1
        
        # Progress indicator
        if items_analyzed % 100 == 0:
            print(f"  Analyzed {items_analyzed}/{len(items)} items... ({items_with_yields} with yields, {profitable_items} profitable)")
        
        # Get reprocessing yields
        yields = get_reprocessing_yields(conn, item['type_id'])
        if not yields or sum(yields.values()) == 0:
            continue
        
        items_with_yields += 1
        
        # Get current Jita prices
        item_prices = get_jita_prices(conn, item['type_id'], config)
        if not item_prices['best_sell_price']:
            continue
        
        # Calculate profit
        profit_data = calculate_reprocessing_profit(
            item, yields, mineral_prices, item_prices, config, efficiency
        )
        
        if not profit_data:
            continue
        
        # Apply filters
        if config['show_only_profitable']:
            if profit_data['profit_margin_pct'] < config['min_profit_margin_pct']:
                continue
            if profit_data['profit_per_unit'] < config['min_profit_per_unit']:
                continue
        
        profitable_items += 1
        
        # Store result
        results.append({
            'item': item,
            'prices': item_prices,
            'yields': yields,
            'profit': profit_data
        })
    
    print(f"\n✓ Analysis complete!")
    print(f"  Items analyzed: {items_analyzed}")
    print(f"  Items with reprocessing yields: {items_with_yields}")
    print(f"  Profitable opportunities: {profitable_items}\n")
    
    # Sort by profit margin
    results.sort(key=lambda x: x['profit']['profit_margin_pct'], reverse=True)
    
    # Display results
    display_results(results, config)
    
    # Export to CSV
    if config['output_csv'] and results:
        export_to_csv(results, config)
    
    conn.close()
    print("\n" + "=" * 80)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

# ============================================================================
# DISPLAY RESULTS
# ============================================================================
def display_results(results, config):
    """
    Display results in a formatted table.
    """
    if not results:
        print("\nNo profitable opportunities found with current filters.")
        print("\nTry adjusting these CONFIG values:")
        print("  - Lower 'min_profit_margin_pct' (currently {})".format(config['min_profit_margin_pct']))
        print("  - Lower 'min_profit_per_unit' (currently {})".format(config['min_profit_per_unit']))
        return
    
    print("\n" + "=" * 80)
    print("PROFITABLE REPROCESSING OPPORTUNITIES")
    print("=" * 80)
    print(f"Showing top {min(50, len(results))} results (sorted by profit margin)\n")
    
    # Header
    print(f"{'Item Name':<40} {'Volume':>8} {'Buy':>12} {'Min Val':>12} {'Profit':>12} {'Margin':>8}")
    print(f"{'Group':<40} {'(m³)':>8} {'Price':>12} {'(ISK)':>12} {'per unit':>12} {'(%)':>8}")
    print("-" * 80)
    
    # Display top results
    for i, result in enumerate(results[:50], 1):
        item = result['item']
        profit = result['profit']
        
        print(f"{item['type_name'][:40]:<40} "
              f"{item['volume']:>8.2f} "
              f"{result['prices']['best_sell_price']:>12,.2f} "
              f"{profit['mineral_value_gross']:>12,.2f} "
              f"{profit['profit_per_unit']:>12,.2f} "
              f"{profit['profit_margin_pct']:>8.1f}%")
        
        print(f"{item['group_name'][:40]:<40} "
              f"{'':>8} "
              f"{'':>12} "
              f"{'':>12} "
              f"{'':>12} "
              f"{'':>8}")
        
        # Show mineral breakdown if enabled
        if config['show_mineral_breakdown'] and i <= 10:  # Only top 10
            print(f"  Mineral breakdown:")
            for mineral, data in profit['mineral_breakdown'].items():
                if data['actual_yield'] > 0:
                    print(f"    {mineral:12s}: {data['actual_yield']:>10,.2f} units × "
                          f"{data['price']:>10,.2f} ISK = {data['value']:>12,.2f} ISK")
            print()
        
        if i < len(results):
            print()
    
    # Summary statistics
    print("-" * 80)
    print("\nSUMMARY STATISTICS:")
    total_items = len(results)
    avg_margin = sum(r['profit']['profit_margin_pct'] for r in results) / total_items
    avg_profit = sum(r['profit']['profit_per_unit'] for r in results) / total_items
    max_profit = max(r['profit']['profit_per_unit'] for r in results)
    
    print(f"  Total opportunities: {total_items}")
    print(f"  Average profit margin: {avg_margin:.2f}%")
    print(f"  Average profit per unit: {avg_profit:,.2f} ISK")
    print(f"  Maximum profit per unit: {max_profit:,.2f} ISK")

# ============================================================================
# EXPORT TO CSV
# ============================================================================
def export_to_csv(results, config):
    """
    Export results to CSV file.
    """
    import csv
    
    filename = config['csv_filename']
    print(f"\nExporting results to {filename}...")
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'type_id', 'type_name', 'group_name', 'volume_m3',
                'buy_price', 'mineral_value', 'total_cost', 'revenue_after_tax',
                'profit_per_unit', 'profit_margin_pct',
                'tritanium', 'pyerite', 'mexallon', 'isogen',
                'nocxium', 'zydrine', 'megacyte', 'morphite'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                item = result['item']
                profit = result['profit']
                yields = result['yields']
                
                writer.writerow({
                    'type_id': item['type_id'],
                    'type_name': item['type_name'],
                    'group_name': item['group_name'],
                    'volume_m3': item['volume'],
                    'buy_price': result['prices']['best_sell_price'],
                    'mineral_value': profit['mineral_value_gross'],
                    'total_cost': profit['total_cost'],
                    'revenue_after_tax': profit['mineral_revenue_after_tax'],
                    'profit_per_unit': profit['profit_per_unit'],
                    'profit_margin_pct': profit['profit_margin_pct'],
                    'tritanium': yields['Tritanium'],
                    'pyerite': yields['Pyerite'],
                    'mexallon': yields['Mexallon'],
                    'isogen': yields['Isogen'],
                    'nocxium': yields['Nocxium'],
                    'zydrine': yields['Zydrine'],
                    'megacyte': yields['Megacyte'],
                    'morphite': yields['Morphite'],
                })
        
        print(f"✓ Exported {len(results)} results to {filename}")
    
    except Exception as e:
        print(f"✗ Failed to export CSV: {e}")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    try:
        analyze_reprocessing_arbitrage(CONFIG)
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)