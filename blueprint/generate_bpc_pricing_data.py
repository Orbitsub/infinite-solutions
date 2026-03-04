"""
Generate BPC pricing data for HTML display.
Creates a JavaScript file with pricing information for all blueprints.

Formula: per_run = Jita 7-day avg best sell × 1% × quality multiplier
"""
import sqlite3
import json
import os
from calculate_bpc_pricing import (
    get_jita_sell_prices,
    get_blueprint_product_mapping_from_db,
    calculate_bpc_price,
    calculate_quality_multiplier,
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mydatabase.db')

def get_all_blueprints_with_pricing():
    """Get all blueprints with pricing data."""
    print("Generating BPC pricing data...")
    print("-" * 60)

    # Load all required data
    jita_prices = get_jita_sell_prices()
    bp_product_map = get_blueprint_product_mapping_from_db()

    # Get character blueprints
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all unique blueprints (both BPOs and BPCs)
    cursor.execute("""
        SELECT DISTINCT type_id, type_name, material_efficiency, time_efficiency
        FROM character_blueprints
        ORDER BY type_name
    """)

    blueprints_with_pricing = []
    blueprints_without_pricing = []

    for row in cursor.fetchall():
        bp_type_id, bp_name, me, te = row

        # Get product type
        product_id = bp_product_map.get(bp_type_id)
        if not product_id:
            blueprints_without_pricing.append(bp_name)
            continue

        # Get Jita price
        jita_price = jita_prices.get(product_id)
        if not jita_price:
            blueprints_without_pricing.append(bp_name)
            continue

        # Calculate quality multiplier
        quality = calculate_quality_multiplier(me, te)

        # Calculate sample pricing (10 runs, 1 copy)
        pricing_10 = calculate_bpc_price(
            bp_type_id, product_id, me, te,
            10, 1,
            jita_price
        )

        if pricing_10:
            blueprints_with_pricing.append({
                'blueprintTypeId': bp_type_id,
                'blueprintName': bp_name,
                'productTypeId': product_id,
                'me': me,
                'te': te,
                'quality': round(quality, 3),
                'qualityPercent': round(quality * 100, 1),
                'jitaSellPrice': round(jita_price, 2),
                'price10Runs': round(pricing_10['final_price'], 2),
                'pricePerRun': round(pricing_10['per_run'], 2)
            })

    conn.close()

    print(f"  Blueprints with pricing: {len(blueprints_with_pricing)}")
    print(f"  Blueprints without market data: {len(blueprints_without_pricing)}")

    return blueprints_with_pricing

def write_pricing_js(blueprints_data):
    """Write pricing data to JavaScript file."""
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'bpc_pricing_data.js')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('// Auto-generated BPC pricing data\n')
        f.write('// Updated automatically - do not manually edit\n')
        f.write('\n')
        f.write('// Pricing configuration\n')
        f.write('const BPC_PRICING_CONFIG = {\n')
        f.write('    formula: "per_run = Jita 7-day avg best sell × 1% × quality",\n')
        f.write('    priceSource: "7-day avg best sell from market snapshots",\n')
        f.write('    basePercentage: 0.01,  // 1% of Jita best sell at 100% quality\n')
        f.write('    qualityFormula: "0.25 + (ME/10 × 0.60) + (TE/20 × 0.15)"\n')
        f.write('};\n')
        f.write('\n')
        f.write('// Blueprint pricing data\n')
        f.write('const BPC_PRICING_DATA = ')
        f.write(json.dumps(blueprints_data, indent=4))
        f.write(';\n')
        f.write('\n')
        f.write('// Helper function to calculate custom pricing\n')
        f.write('function calculateBPCPrice(blueprintTypeId, runs, copies) {\n')
        f.write('    const bp = BPC_PRICING_DATA.find(b => b.blueprintTypeId === blueprintTypeId);\n')
        f.write('    if (!bp) return null;\n')
        f.write('\n')
        f.write('    // Price scales linearly with runs and copies\n')
        f.write('    const pricePerRun = bp.pricePerRun;\n')
        f.write('    const totalPrice = pricePerRun * runs * copies;\n')
        f.write('\n')
        f.write('    return {\n')
        f.write('        blueprintName: bp.blueprintName,\n')
        f.write('        me: bp.me,\n')
        f.write('        te: bp.te,\n')
        f.write('        quality: bp.quality,\n')
        f.write('        qualityPercent: bp.qualityPercent,\n')
        f.write('        jitaSellPrice: bp.jitaSellPrice,\n')
        f.write('        runs: runs,\n')
        f.write('        copies: copies,\n')
        f.write('        totalRuns: runs * copies,\n')
        f.write('        pricePerRun: pricePerRun,\n')
        f.write('        totalPrice: totalPrice\n')
        f.write('    };\n')
        f.write('}\n')

    print(f"\n[OK] Pricing data written to {output_path}")
    return output_path

def main():
    print("=" * 60)
    print("BPC PRICING DATA GENERATOR")
    print("=" * 60)
    print()

    blueprints = get_all_blueprints_with_pricing()
    output_file = write_pricing_js(blueprints)

    print()
    print("=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"Generated pricing for {len(blueprints)} blueprints")
    print(f"Output file: {output_file}")
    print()

if __name__ == '__main__':
    main()
