"""
Blueprint Copy Service Cost Calculator
Calculates actual copy costs with facility bonuses and customer pricing.

Facility: Azbel in LX-ZOJ (Geminate)
- Rig: -21% cost, -42% time
- Tax: 5%
- System Cost Index: Dynamic (from ESI)
- Markup: 2x for Standard BPOs
"""
import requests
import json

# Configuration
LX_ZOJ_SYSTEM_ID = 30002458
FACILITY_COST_REDUCTION = 0.21  # 21% cost reduction from rig
FACILITY_TAX = 0.05  # 5% facility tax
STANDARD_MARKUP = 2.0  # 2x markup for standard BPOs

# ESI endpoints
ADJUSTED_PRICES_URL = "https://esi.evetech.net/latest/markets/prices/"
COST_INDICES_URL = "https://esi.evetech.net/latest/industry/systems/"

def get_adjusted_prices():
    """Fetch adjusted prices (EIV) from ESI."""
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
    """Fetch copying cost index for specific system."""
    print(f"Fetching cost indices for system {system_id}...")
    response = requests.get(COST_INDICES_URL)
    response.raise_for_status()

    for system in response.json():
        if system['solar_system_id'] == system_id:
            for activity in system.get('cost_indices', []):
                if activity['activity'] == 'copying':
                    cost_index = activity['cost_index']
                    print(f"  LX-ZOJ copying cost index: {cost_index:.4f} ({cost_index*100:.2f}%)")
                    return cost_index

    print(f"  Warning: No cost index found for system {system_id}, using 1.0")
    return 1.0

def get_blueprint_product(blueprint_type_id):
    """Get what a blueprint produces from SDE."""
    with open('sde/blueprints.jsonl', 'r') as f:
        for line in f:
            bp = json.loads(line)
            if bp['blueprintTypeID'] == blueprint_type_id:
                if 'manufacturing' in bp.get('activities', {}):
                    products = bp['activities']['manufacturing'].get('products', [])
                    if products:
                        return products[0]['typeID']
    return None

def calculate_copy_service_cost(blueprint_type_id, blueprint_name, product_type_id,
                                runs_per_copy, num_copies, adjusted_prices,
                                system_cost_index):
    """
    Calculate copy service costs with facility bonuses and customer pricing.

    Returns dict with breakdown of costs.
    """
    # Get the adjusted price (EIV) of the product
    eiv = adjusted_prices.get(product_type_id, 0)

    if eiv == 0:
        return None

    # Step 1: Base EVE copy cost
    # Formula: EIV × 0.02 × Runs × Copies × System Cost Index
    base_eve_cost = eiv * 0.02 * runs_per_copy * num_copies * system_cost_index

    # Step 2: Apply facility rig bonus (21% cost reduction)
    cost_after_rig = base_eve_cost * (1 - FACILITY_COST_REDUCTION)

    # Step 3: Apply facility tax (5%)
    cost_after_tax = cost_after_rig * (1 + FACILITY_TAX)

    # Step 4: Your actual cost (what you pay)
    your_cost = cost_after_tax

    # Step 5: Customer price (2x markup)
    customer_price = your_cost * STANDARD_MARKUP

    return {
        'eiv': eiv,
        'base_eve_cost': base_eve_cost,
        'cost_after_rig': cost_after_rig,
        'cost_after_tax': cost_after_tax,
        'your_cost': your_cost,
        'customer_price': customer_price,
        'rig_savings': base_eve_cost - cost_after_rig,
        'tax_amount': cost_after_tax - cost_after_rig,
        'your_profit': customer_price - your_cost
    }

def format_isk(amount):
    """Format ISK amount with commas."""
    if amount is None:
        return "Unknown"
    return f"{amount:,.2f} ISK"

def print_cost_breakdown(blueprint_name, runs, copies, costs):
    """Print detailed cost breakdown."""
    print()
    print("=" * 80)
    print(f"COST BREAKDOWN: {blueprint_name}")
    print("=" * 80)
    print(f"Configuration: {copies} {'copy' if copies == 1 else 'copies'} × {runs} runs each = {runs * copies} total runs")
    print()
    print(f"Product EIV (Estimated Item Value):     {format_isk(costs['eiv'])}")
    print()
    print("COST CALCULATION:")
    print("-" * 80)
    print(f"1. Base EVE Copy Cost:                   {format_isk(costs['base_eve_cost'])}")
    print(f"   (EIV × 0.02 × Runs × Copies × System Index)")
    print()
    print(f"2. After Rig Bonus (-21%):               {format_isk(costs['cost_after_rig'])}")
    print(f"   Savings from rig:                     -{format_isk(costs['rig_savings'])}")
    print()
    print(f"3. After Facility Tax (+5%):             {format_isk(costs['cost_after_tax'])}")
    print(f"   Tax amount:                           +{format_isk(costs['tax_amount'])}")
    print()
    print(f"4. YOUR ACTUAL COST:                     {format_isk(costs['your_cost'])}")
    print()
    print(f"5. CUSTOMER PRICE (2x markup):           {format_isk(costs['customer_price'])}")
    print(f"   Your profit:                          {format_isk(costs['your_profit'])}")
    print("=" * 80)

def main():
    print("=" * 80)
    print("BLUEPRINT COPY SERVICE - COST CALCULATOR")
    print("=" * 80)
    print()
    print("Facility: Azbel in LX-ZOJ (Geminate)")
    print("  - Rig Bonus: -21% cost, -42% time")
    print("  - Facility Tax: 5%")
    print("  - Markup: 2x (Standard BPOs)")
    print()

    # Fetch data
    adjusted_prices = get_adjusted_prices()
    system_cost_index = get_system_cost_index(LX_ZOJ_SYSTEM_ID)

    # Example calculations
    examples = [
        (16243, "Thrasher Blueprint", [(1, 10), (5, 10), (1, 100)]),
        (17476, "Vexor Blueprint", [(1, 10), (5, 10)]),
        (684, "Catalyst Blueprint", [(1, 10), (10, 10)]),
    ]

    for bp_id, bp_name, scenarios in examples:
        product_id = get_blueprint_product(bp_id)

        if not product_id:
            print(f"\nSkipping {bp_name} - no product found")
            continue

        for copies, runs in scenarios:
            costs = calculate_copy_service_cost(
                bp_id, bp_name, product_id,
                runs, copies,
                adjusted_prices, system_cost_index
            )

            if costs:
                print_cost_breakdown(bp_name, runs, copies, costs)

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("Customer sees: Transparent pricing based on EVE costs + facility bonuses")
    print("Customer pays: 2x your actual cost (includes your profit)")
    print("You earn:      100% markup on your actual expenses")
    print()
    print("Note: Prices update automatically as system cost index changes!")
    print("=" * 80)

if __name__ == '__main__':
    main()
