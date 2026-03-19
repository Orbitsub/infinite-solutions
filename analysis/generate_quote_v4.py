"""
==========================================
JITA SOURCING SERVICE QUOTE GENERATOR v4
==========================================
New in v4:
- 2.5% MINIMUM PROFIT GUARANTEE
- Smart shipping coverage based on order margin
- Uses actual broker fees from v_my_trading_fees
- Pulls freight rates from freighting_services table (TEST Freight)
==========================================

SHIPPING LOGIC (2.5% Minimum Profit):

Step 1: Calculate minimum profit requirement
  minimum_profit = order_value × 2.5%

Step 2: Determine available budget for shipping coverage
  available_for_shipping = total_margin - minimum_profit

Step 3: Choose shipping strategy
  IF available >= total_shipping:
    → FULL_COVERAGE: Cover all shipping, keep 2.5%+ profit
  
  ELIF available > 0:
    → PARTIAL_COVERAGE: Cover what you can, keep 2.5% profit
  
  ELSE (margin < 2.5%):
    → CHARGE_ALL: Charge full shipping, keep all margin (below target)

Per-item decisions respect the overall strategy and coverage budget.

This ensures you NEVER work for free and always target 2.5%+ profit!
==========================================

EXAMPLES:
- High margin order (5%+): FREE shipping on most/all items ✅
- Medium margin (2.5-5%): Partial coverage, hit 2.5% target ✅
- Low margin (<2.5%): Charge full shipping, maximize profit ⚠️
==========================================
"""

import sqlite3
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

# Shipping buffer - item margin must cover shipping cost × (1 + buffer)
SHIPPING_BUFFER = 0.10  # 10% safety margin

# Minimum profit threshold - guarantee at least this % of order value as profit
MINIMUM_PROFIT_PERCENT = 0.025  # 2.5% of order value

def get_freight_service(db_path):
    """Get TEST Freight service details from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            service_name,
            cost_per_m3,
            collateral_fee_percent,
            minimum_reward
        FROM freighting_services
        WHERE service_name = 'TEST Freight'
          AND route_from = 'Jita'
          AND route_to = 'BWF-ZZ'
          AND is_active = 1
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise Exception("TEST Freight service not found in database!")
    
    return {
        'name': result[0],
        'cost_per_m3': result[1],
        'collateral_fee_percent': result[2],
        'minimum_reward': result[3]
    }

def calculate_shipping(total_volume_m3, total_value_isk, freight_service):
    """Calculate total shipping cost: (volume × rate) + (value × collateral%), with minimum."""
    volume_cost = total_volume_m3 * freight_service['cost_per_m3']
    collateral_cost = total_value_isk * freight_service['collateral_fee_percent']
    total_shipping = volume_cost + collateral_cost
    
    # Apply minimum reward
    if total_shipping < freight_service['minimum_reward']:
        total_shipping = freight_service['minimum_reward']
    
    return total_shipping, volume_cost, collateral_cost

def generate_quote(items_list, customer_name="Corp Member"):
    """Generate a quote with per-item shipping decisions."""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build the order list for SQL
    order_items = []
    for i, (item_name, qty) in enumerate(items_list):
        safe_name = item_name.replace("'", "''")
        if i == 0:
            order_items.append(f"SELECT '{safe_name}' AS item_name, {qty} AS quantity")
        else:
            order_items.append(f"UNION ALL SELECT '{safe_name}', {qty}")
    
    order_list_sql = '\n    '.join(order_items)

    # The quote query
    query = f"""
WITH order_list AS (
    {order_list_sql}
),

my_fees AS (
    -- Get YOUR actual trading fees
    SELECT 
        broker_fee_percent,
        sales_tax_percent,
        buy_cost_multiplier,
        sell_revenue_multiplier
    FROM v_my_trading_fees
    WHERE character_id = 2114278577
),

jita_prices AS (
    SELECT
        it.type_id,
        it.type_name,
        COALESCE(st.packaged_volume, it.volume) as volume,
        MAX(CASE WHEN mo.is_buy_order = 1 THEN mo.price END) as buy_order_price,
        MIN(CASE WHEN mo.is_buy_order = 0 THEN mo.price END) as sell_order_price,
        (SELECT broker_fee_percent FROM my_fees) as broker_fee_pct
    FROM inv_types it
    LEFT JOIN sde_types st ON st.type_id = it.type_id
    LEFT JOIN market_orders mo ON mo.type_id = it.type_id
        AND mo.location_id = 60003760
        AND mo.region_id = 10000002
    WHERE it.type_name IN (SELECT item_name FROM order_list)
    GROUP BY it.type_id, it.type_name, it.volume, st.packaged_volume
),

bwf_prices AS (
    SELECT
        it.type_id,
        MIN(CASE WHEN bmo.is_buy_order = 0 THEN bmo.price END) as lowest_sell_price
    FROM inv_types it
    LEFT JOIN bwf_market_orders bmo ON bmo.type_id = it.type_id
    WHERE it.type_name IN (SELECT item_name FROM order_list)
    GROUP BY it.type_id
),

item_calculations AS (
    SELECT
        ol.item_name,
        ol.quantity,
        jp.volume,
        jp.buy_order_price,
        jp.sell_order_price,
        jp.broker_fee_pct,
        
        -- Customer pays sell price
        jp.sell_order_price AS customer_price_per_unit,
        jp.sell_order_price * ol.quantity AS line_total,
        
        -- Volume calculations
        jp.volume * ol.quantity AS total_volume_m3,
        
        -- Your gross margin per unit
        CASE
            WHEN jp.buy_order_price IS NOT NULL
            THEN jp.sell_order_price - jp.buy_order_price
            ELSE NULL
        END AS gross_margin_per_unit,
        
        -- Broker fee amount per unit
        CASE
            WHEN jp.buy_order_price IS NOT NULL
            THEN jp.buy_order_price * (jp.broker_fee_pct / 100.0)
            ELSE NULL
        END AS broker_fee_per_unit,
        
        -- Your NET margin per unit (after broker fees)
        CASE
            WHEN jp.buy_order_price IS NOT NULL
            THEN (jp.sell_order_price - jp.buy_order_price) - (jp.buy_order_price * jp.broker_fee_pct / 100.0)
            ELSE NULL
        END AS net_margin_per_unit,
        
        -- Total NET margin for this line
        CASE
            WHEN jp.buy_order_price IS NOT NULL
            THEN ((jp.sell_order_price - jp.buy_order_price) - (jp.buy_order_price * jp.broker_fee_pct / 100.0)) * ol.quantity
            ELSE NULL
        END AS net_margin_total,
        
        -- Collateral per unit
        jp.sell_order_price * 0.01 AS collateral_per_unit,
        (jp.sell_order_price * 0.01) * ol.quantity AS item_collateral,
        
        -- BWF comparison
        bp.lowest_sell_price,
        bp.lowest_sell_price * ol.quantity AS bwf_total_cost
        
    FROM order_list ol
    JOIN jita_prices jp ON jp.type_name = ol.item_name
    LEFT JOIN bwf_prices bp ON bp.type_id = jp.type_id
)

SELECT 
    item_name,
    quantity,
    volume,
    buy_order_price,
    sell_order_price,
    broker_fee_pct,
    customer_price_per_unit,
    line_total,
    total_volume_m3,
    gross_margin_per_unit,
    broker_fee_per_unit,
    net_margin_per_unit,
    net_margin_total,
    collateral_per_unit,
    item_collateral,
    lowest_sell_price,
    bwf_total_cost
FROM item_calculations;
"""
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    if not results:
        print("[ERROR] No items found in database!")
        conn.close()
        return None
    
    # Get TEST Freight service details
    freight_service = get_freight_service(DB_PATH)
    
    # Calculate totals
    total_items_cost = sum(row[7] for row in results)  # line_total
    total_volume_m3 = sum(row[8] for row in results)   # total_volume_m3
    
    # Calculate shipping using TEST Freight rates
    total_shipping, volume_cost, collateral_cost = calculate_shipping(
        total_volume_m3, 
        total_items_cost,
        freight_service
    )
    
    # Calculate total net margin
    total_net_margin = sum(row[12] for row in results if row[12] is not None)  # net_margin_total
    
    # 2.5% MINIMUM PROFIT GUARANTEE
    # Calculate minimum profit required (2.5% of order value)
    minimum_profit_required = total_items_cost * MINIMUM_PROFIT_PERCENT
    
    # Calculate how much you can afford to spend on shipping while keeping 2.5%
    available_for_shipping = total_net_margin - minimum_profit_required
    
    # Determine shipping coverage strategy
    if available_for_shipping >= total_shipping:
        # Can cover ALL shipping and still keep 2.5%+ profit
        shipping_strategy = "FULL_COVERAGE"
        max_coverage_amount = total_shipping
    elif available_for_shipping > 0:
        # Can cover SOME shipping and keep 2.5% profit
        shipping_strategy = "PARTIAL_COVERAGE"
        max_coverage_amount = available_for_shipping
    else:
        # Margin is below 2.5% threshold - charge full shipping to maximize profit
        shipping_strategy = "CHARGE_ALL"
        max_coverage_amount = 0
    
    # Per-item shipping decisions
    shipping_decisions = []
    total_customer_shipping = 0
    total_covered_shipping = 0
    items_with_free_shipping = 0
    items_with_charges = 0
    items_need_quote = 0
    
    for row in results:
        (item_name, qty, volume, buy_price, sell_price, broker_fee_pct,
         customer_price, line_total, item_volume_m3, 
         gross_margin_unit, broker_fee_unit, net_margin_unit, net_margin_total,
         collat_unit, item_collat, bwf_sell, bwf_total) = row
        
        # Calculate this item's proportional share of shipping
        volume_share = item_volume_m3 / total_volume_m3 if total_volume_m3 > 0 else 0
        item_shipping_cost = total_shipping * volume_share
        
        # Decision logic - WITH 2.5% MINIMUM PROFIT GUARANTEE
        if buy_price is None or net_margin_total is None:
            # No buy order available - needs manual quote
            status = "REQUIRES QUOTE"
            customer_charge = None
            you_cover = 0
            items_need_quote += 1
            
        elif shipping_strategy == "CHARGE_ALL":
            # Order margin is below 2.5% - charge full shipping on all items
            status = "CHARGED"
            customer_charge = item_shipping_cost
            you_cover = 0
            total_customer_shipping += customer_charge
            items_with_charges += 1
            
        elif shipping_strategy == "FULL_COVERAGE":
            # Can afford to cover all shipping and keep 2.5%+
            # Apply original per-item logic
            if net_margin_total >= (item_shipping_cost * (1 + SHIPPING_BUFFER)):
                # Item margin covers its shipping + buffer
                status = "INCLUDED"
                customer_charge = 0
                you_cover = item_shipping_cost
                total_covered_shipping += item_shipping_cost
                items_with_free_shipping += 1
            else:
                # Item margin too thin - partial coverage
                status = "PARTIAL"
                you_cover = net_margin_total
                customer_charge = item_shipping_cost - net_margin_total
                total_covered_shipping += you_cover
                total_customer_shipping += customer_charge
                items_with_charges += 1
                
        else:  # PARTIAL_COVERAGE strategy
            # Can afford SOME shipping coverage while keeping 2.5%
            # Distribute available coverage proportionally
            if total_covered_shipping < max_coverage_amount:
                # Still have coverage budget remaining
                remaining_budget = max_coverage_amount - total_covered_shipping
                
                if net_margin_total >= (item_shipping_cost * (1 + SHIPPING_BUFFER)):
                    # Item margin is good - cover what we can from budget
                    coverage = min(item_shipping_cost, remaining_budget)
                    status = "INCLUDED" if coverage == item_shipping_cost else "PARTIAL"
                    you_cover = coverage
                    customer_charge = item_shipping_cost - coverage
                    total_covered_shipping += you_cover
                    total_customer_shipping += customer_charge
                    if coverage == item_shipping_cost:
                        items_with_free_shipping += 1
                    else:
                        items_with_charges += 1
                else:
                    # Item margin is thin - use proportional coverage from budget
                    proportional_coverage = min(net_margin_total, remaining_budget)
                    status = "PARTIAL"
                    you_cover = proportional_coverage
                    customer_charge = item_shipping_cost - proportional_coverage
                    total_covered_shipping += you_cover
                    total_customer_shipping += customer_charge
                    items_with_charges += 1
            else:
                # Budget exhausted - charge customer
                status = "CHARGED"
                customer_charge = item_shipping_cost
                you_cover = 0
                total_customer_shipping += customer_charge
                items_with_charges += 1
        
        shipping_decisions.append({
            'row': row,
            'status': status,
            'customer_charge': customer_charge,
            'you_cover': you_cover,
            'item_shipping_cost': item_shipping_cost,
            'volume_share': volume_share
        })
    
    # Calculate your actual profit
    total_net_margin = sum(row[12] for row in results if row[12] is not None)  # net_margin_total
    your_net_profit = total_net_margin - total_covered_shipping
    
    # Grand total for customer
    grand_total = total_items_cost + total_customer_shipping
    
    # Generate customer quote
    quote_lines = []
    quote_lines.append("═" * 110)
    quote_lines.append("                              JITA SOURCING SERVICE QUOTE")
    quote_lines.append("═" * 110)
    quote_lines.append("")
    quote_lines.append(f"Quote Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    quote_lines.append(f"Customer: {customer_name}")
    quote_lines.append("")
    quote_lines.append("ITEM BREAKDOWN:")
    quote_lines.append("─" * 110)
    quote_lines.append(f"{'Item':<45} {'Qty':>4} {'m³':>10} {'Unit Price':>14} {'Shipping':>14} {'Line Total':>16}")
    quote_lines.append("─" * 110)
    
    for decision in shipping_decisions:
        row = decision['row']
        status = decision['status']
        customer_charge = decision['customer_charge']
        
        item_name, qty, volume, buy_price, sell_price, broker_fee_pct, customer_price, line_total, total_m3 = row[:9]
        
        display_name = item_name[:44] if len(item_name) > 44 else item_name
        
        # Shipping display
        if status == "INCLUDED":
            shipping_display = "INCLUDED"
            final_line_total = line_total
        elif status in ["CHARGED", "PARTIAL"]:
            shipping_display = f"+{customer_charge:,.2f}"
            final_line_total = line_total + customer_charge
        else:  # REQUIRES QUOTE
            shipping_display = "[QUOTE]"
            final_line_total = None
        
        if final_line_total is not None:
            quote_lines.append(
                f"{display_name:<45} "
                f"{qty:>4} "
                f"{total_m3:>10,.2f} "
                f"{customer_price:>14,.2f} "
                f"{shipping_display:>14} "
                f"{final_line_total:>16,.2f}"
            )
        else:
            quote_lines.append(
                f"{display_name:<45} "
                f"{qty:>4} "
                f"{total_m3:>10,.2f} "
                f"{customer_price:>14,.2f} "
                f"{shipping_display:>14} "
                f"{'[QUOTE NEEDED]':>16}"
            )
    
    quote_lines.append("─" * 110)
    quote_lines.append(
        f"{'SUBTOTAL (Items)':<45} "
        f"{'':<4} "
        f"{'':<10} "
        f"{'':<14} "
        f"{'':<14} "
        f"{total_items_cost:>16,.2f}"
    )

    if total_customer_shipping > 0:
        quote_lines.append(
            f"{'Shipping Charges':<45} "
            f"{'':<4} "
            f"{'':<10} "
            f"{'':<14} "
            f"{'':<14} "
            f"{total_customer_shipping:>16,.2f}"
        )
    
    quote_lines.append(
        f"{'':<45} "
        f"{'':<4} "
        f"{'':<10} "
        f"{'':<14} "
        f"{'':<14} "
        f"{'─' * 16}"
    )
    
    quote_lines.append(
        f"{'TOTAL DUE:':<45} "
        f"{'':<4} "
        f"{'':<10} "
        f"{'':<14} "
        f"{'':<14} "
        f"{grand_total:>16,.2f}"
    )
    quote_lines.append("═" * 110)
    
    # Shipping summary
    quote_lines.append("")
    quote_lines.append("SHIPPING DETAILS (Jita → BWF-ZZ):")
    quote_lines.append("─" * 110)
    quote_lines.append(f"Total volume: {total_volume_m3:,.2f} m³")
    quote_lines.append(f"Rate: {freight_service['cost_per_m3']:.0f} ISK/m³ + {freight_service['collateral_fee_percent']*100:.0f}% Service Fee")
    quote_lines.append(f"Minimum: {freight_service['minimum_reward']:,.0f} ISK")
    quote_lines.append("")
    quote_lines.append(f"Volume cost: {volume_cost:,.2f} ISK")
    quote_lines.append(f"Service fee: {collateral_cost:,.2f} ISK")
    quote_lines.append(f"Total shipping: {total_shipping:,.2f} ISK")
    quote_lines.append("")
    
    # Show minimum profit policy
    margin_percent = (total_net_margin / total_items_cost * 100) if total_items_cost > 0 else 0
    quote_lines.append(f"Service Policy: We maintain a minimum {MINIMUM_PROFIT_PERCENT*100:.1f}% profit margin to ensure sustainable service.")
    quote_lines.append("")
    
    if total_covered_shipping > 0:
        coverage_pct = (total_covered_shipping / total_shipping * 100) if total_shipping > 0 else 0
        quote_lines.append(f"We're covering: {total_covered_shipping:,.2f} ISK ({coverage_pct:.0f}% of total shipping)")
        quote_lines.append(f"You pay: {total_customer_shipping:,.2f} ISK ({100-coverage_pct:.0f}% of total shipping)")
        quote_lines.append("")
    
    quote_lines.append(f"Items with FREE shipping:    {items_with_free_shipping} items (margin covers full shipping)")
    if items_with_charges > 0:
        quote_lines.append(f"Items with partial charges:  {items_with_charges} items (we cover what margin allows)")
    if items_need_quote > 0:
        quote_lines.append(f"Items requiring quote:       {items_need_quote} items (no buy orders available)")
    quote_lines.append("─" * 110)
    
    # BWF comparison if applicable
    bwf_items_with_prices = [row[16] for row in results if row[16] is not None]
    if bwf_items_with_prices:
        total_bwf_cost = sum(bwf_items_with_prices)
        items_with_bwf = len(bwf_items_with_prices)
        total_items = len(results)
        
        if total_bwf_cost > grand_total:
            savings = total_bwf_cost - grand_total
            savings_pct = (savings / total_bwf_cost) * 100
            
            quote_lines.append("")
            quote_lines.append("YOUR SAVINGS:")
            quote_lines.append("─" * 110)
            if items_with_bwf < total_items:
                quote_lines.append(f"  * {items_with_bwf}/{total_items} items available in BWF market")
                quote_lines.append("")
            quote_lines.append(f"  BWF Market Price:   {total_bwf_cost:>16,.2f} ISK")
            quote_lines.append(f"  Our Price:          {grand_total:>16,.2f} ISK")
            quote_lines.append("  " + "─" * 80)
            quote_lines.append(f"  YOU SAVE:           {savings:>16,.2f} ISK ({savings_pct:.1f}%)")
            quote_lines.append("═" * 110)
    
    quote_lines.append("")
    quote_lines.append("This price is locked in. Payment due on delivery to BWF.")
    quote_lines.append("")
    quote_lines.append("Service Timeline:")
    quote_lines.append("  - Sourcing: 5-7 days (buy orders in Jita)")
    quote_lines.append("  - Shipping: Coordinated via professional courier services")
    quote_lines.append("")
    quote_lines.append("Items will be contracted to you in BWF once delivered.")
    quote_lines.append("═" * 110)
    
    quote_text = "\n".join(quote_lines)
    
    # Internal profit breakdown
    profit_lines = []
    profit_lines.append("")
    profit_lines.append("═" * 110)
    profit_lines.append("                              YOUR PROFIT BREAKDOWN (INTERNAL)")
    profit_lines.append("═" * 110)
    profit_lines.append("")
    profit_lines.append("NOTES:")
    profit_lines.append("  - Customer pays SELL ORDER price")
    profit_lines.append("  - You pay BUY ORDER price (when orders fill)")
    profit_lines.append("  - Broker fees deducted from margin")
    profit_lines.append("  - Shipping decisions based on per-item margin coverage")
    profit_lines.append("")
    profit_lines.append("ITEM BREAKDOWN:")
    profit_lines.append("─" * 110)
    profit_lines.append(f"{'Item':<40} {'Qty':>4} {'Net Margin/Unit':>16} {'Total Margin':>14} {'Shipping':>14} {'Status':>14}")
    profit_lines.append("─" * 110)
    
    for decision in shipping_decisions:
        row = decision['row']
        status = decision['status']
        item_shipping_cost = decision['item_shipping_cost']
        
        item_name, qty = row[0], row[1]
        net_margin_unit = row[11] if row[11] is not None else 0
        net_margin_total = row[12] if row[12] is not None else 0
        
        display_name = item_name[:39] if len(item_name) > 39 else item_name
        
        if status == "INCLUDED":
            status_display = "✅ FREE"
        elif status == "PARTIAL":
            status_display = "🔸 PARTIAL"
        elif status == "CHARGED":
            status_display = "💰 CHARGED"
        else:
            status_display = "⚠️ QUOTE"
        
        profit_lines.append(
            f"{display_name:<40} "
            f"{qty:>4} "
            f"{net_margin_unit:>16,.0f} "
            f"{net_margin_total:>14,.0f} "
            f"{item_shipping_cost:>14,.0f} "
            f"{status_display:>14}"
        )
    
    profit_lines.append("─" * 110)
    profit_lines.append(
        f"{'TOTALS:':<40} "
        f"{'':<4} "
        f"{'':<16} "
        f"{total_net_margin:>14,.0f} "
        f"{total_shipping:>14,.0f} "
        f"{'':<14}"
    )
    profit_lines.append("═" * 110)
    profit_lines.append("")
    profit_lines.append("SHIPPING BREAKDOWN:")
    profit_lines.append(f"  Service: {freight_service['name']}")
    profit_lines.append(f"  Rate: {freight_service['cost_per_m3']:.0f} ISK/m³ + {freight_service['collateral_fee_percent']*100:.0f}% Service Fee (min {freight_service['minimum_reward']:,.0f} ISK)")
    profit_lines.append("")
    profit_lines.append(f"  Volume cost:                {volume_cost:>16,.0f} ISK  ({total_volume_m3:,.2f} m³)")
    profit_lines.append(f"  Service fee:                {collateral_cost:>16,.0f} ISK  ({total_items_cost:,.0f} ISK × 1%)")
    profit_lines.append(f"  Total shipping:             {total_shipping:>16,.0f} ISK")
    profit_lines.append("")
    profit_lines.append("PROFIT POLICY:")
    profit_lines.append(f"  Minimum profit target:      {minimum_profit_required:>16,.0f} ISK ({MINIMUM_PROFIT_PERCENT*100:.1f}% of order value)")
    profit_lines.append(f"  Strategy used:              {shipping_strategy.replace('_', ' ').title()}")
    profit_lines.append(f"  Order margin %:             {margin_percent:>16.2f}%")
    profit_lines.append("")
    profit_lines.append("COST BREAKDOWN:")
    profit_lines.append(f"  Customer pays:              {grand_total:>16,.0f} ISK")
    profit_lines.append(f"  Total shipping cost:        {total_shipping:>16,.0f} ISK")
    profit_lines.append(f"    - Covered by you:         {total_covered_shipping:>16,.0f} ISK")
    profit_lines.append(f"    - Charged to customer:    {total_customer_shipping:>16,.0f} ISK")
    profit_lines.append("")
    profit_lines.append(f"  Your net margin:            {total_net_margin:>16,.0f} ISK (after broker fees)")
    profit_lines.append(f"  Shipping you cover:        -{total_covered_shipping:>16,.0f} ISK")
    profit_lines.append("  " + "─" * 80)
    profit_lines.append(f"  YOUR NET PROFIT:            {your_net_profit:>16,.0f} ISK")
    profit_margin_pct = (your_net_profit / total_items_cost * 100) if total_items_cost > 0 else 0
    profit_lines.append(f"  Your profit margin:         {profit_margin_pct:>16.2f}%")
    if profit_margin_pct >= MINIMUM_PROFIT_PERCENT * 100:
        profit_lines.append(f"  ✅ Meets {MINIMUM_PROFIT_PERCENT*100:.1f}% minimum target!")
    else:
        profit_lines.append(f"  ⚠️ Below {MINIMUM_PROFIT_PERCENT*100:.1f}% target (margin was insufficient)")
    profit_lines.append("═" * 110)
    
    profit_text = "\n".join(profit_lines)
    
    # Delivery receipt
    receipt_lines = []
    receipt_lines.append("═" * 110)
    receipt_lines.append("                                   DELIVERY RECEIPT")
    receipt_lines.append("═" * 110)
    receipt_lines.append("")
    receipt_num = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M') + "-" + customer_name[:3].upper()
    receipt_lines.append(f"Receipt #: {receipt_num}")
    receipt_lines.append(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    receipt_lines.append(f"Customer: {customer_name}")
    receipt_lines.append("Service: Jita Sourcing & Delivery")
    receipt_lines.append("")
    receipt_lines.append("─" * 110)
    receipt_lines.append("ITEMS DELIVERED:")
    receipt_lines.append("─" * 110)
    receipt_lines.append(f"{'Item':<50} {'Qty':>4} {'Unit Price':>14} {'Line Total':>16}")
    receipt_lines.append("─" * 110)
    
    for decision in shipping_decisions:
        row = decision['row']
        status = decision['status']
        customer_charge = decision['customer_charge']
        
        item_name, qty, volume, buy_price, sell_price, broker_fee_pct, customer_price, line_total = row[:8]
        
        display_name = item_name[:49] if len(item_name) > 49 else item_name
        
        if status == "CHARGED":
            final_total = line_total + customer_charge
        else:
            final_total = line_total
        
        receipt_lines.append(
            f"{display_name:<50} "
            f"{qty:>4} "
            f"{customer_price:>14,.2f} "
            f"{final_total:>16,.2f}"
        )
    
    if total_customer_shipping > 0:
        receipt_lines.append("─" * 110)
        receipt_lines.append(
            f"{'Shipping charges (low-margin items)':<50} "
            f"{'':<4} "
            f"{'':<14} "
            f"{total_customer_shipping:>16,.2f}"
        )

    receipt_lines.append("─" * 110)
    receipt_lines.append(
        f"{'TOTAL PAYMENT:':<50} "
        f"{'':<4} "
        f"{'':<14} "
        f"{grand_total:>16,.2f}"
    )
    receipt_lines.append("═" * 110)
    receipt_lines.append("")
    receipt_lines.append("DELIVERY LOCATION: BWF-ZZ (Item Exchange Contract)")
    receipt_lines.append("")
    receipt_lines.append("Thank you for using our sourcing service!")
    receipt_lines.append("Questions? Contact me in corp chat or Discord.")
    receipt_lines.append("")
    receipt_lines.append("═" * 110)
    
    receipt_text = "\n".join(receipt_lines)

    conn.close()

    return quote_text, profit_text, receipt_text, grand_total, your_net_profit


def main():
    print("=" * 110)
    print("JITA SOURCING SERVICE - QUOTE GENERATOR v4 (Smart Shipping)")
    print("=" * 110)
    print()
    
    # Get customer name
    customer_name = input("Customer name (optional, press Enter to skip): ").strip()
    if not customer_name:
        customer_name = "Corp Member"
    
    # Get items
    print("\nEnter items - TWO OPTIONS:")
    print()
    print("OPTION 1: Multi-line paste (fastest for bulk orders)")
    print("  Paste all items at once, then press Enter twice")
    print("  Format: Item Name, Quantity (one per line)")
    print()
    print("OPTION 2: Enter items one at a time")
    print("  Type 'done' when finished")
    print()
    
    mode = input("Choose mode (paste/manual): ").strip().lower()
    
    items = []
    
    if mode == 'paste':
        print("\nPaste your items (press Enter twice when done):")
        print()
        
        lines = []
        empty_count = 0
        
        while True:
            line = input().strip()
            
            if not line:
                empty_count += 1
                if empty_count >= 2:
                    break
                continue
            
            empty_count = 0
            lines.append(line)
        
        # Parse pasted lines
        for line in lines:
            if ',' not in line:
                print(f"[SKIP] Invalid format: {line}")
                continue
            
            try:
                parts = line.rsplit(',', 1)
                item_name = parts[0].strip()
                quantity = int(parts[1].strip())
                items.append((item_name, quantity))
                print(f"  [OK] Added: {quantity}x {item_name}")
            except (ValueError, IndexError):
                print(f"[SKIP] Invalid format: {line}")
    
    else:  # manual mode
        print("\nEnter items one at a time:")
        while True:
            item_input = input(f"Item {len(items) + 1}: ").strip()
            
            if item_input.lower() == 'done':
                break
            
            if ',' not in item_input:
                print("[ERROR] Format should be: Item Name, Quantity")
                continue
            
            try:
                parts = item_input.rsplit(',', 1)
                item_name = parts[0].strip()
                quantity = int(parts[1].strip())
                items.append((item_name, quantity))
                print(f"  [OK] Added: {quantity}x {item_name}")
            except (ValueError, IndexError):
                print("[ERROR] Invalid format. Try again.")
    
    if not items:
        print("\n[ERROR] No items entered!")
        return
    
    print(f"\n[OK] Generating quote for {len(items)} items with smart shipping logic...")
    print("[INFO] Items with thin margins will have shipping charges applied")
    
    result = generate_quote(items, customer_name)
    
    if result is None:
        return
    
    quote_text, profit_text, receipt_text, grand_total, your_profit = result
    
    # Save to files
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = customer_name.replace(' ', '_').replace('/', '_')
    
    quote_filename = f"quote_{safe_name}_{timestamp}.txt"
    profit_filename = f"profit_{safe_name}_{timestamp}.txt"
    receipt_filename = f"receipt_{safe_name}_{timestamp}.txt"
    
    quote_path = os.path.join(PROJECT_DIR, quote_filename)
    profit_path = os.path.join(PROJECT_DIR, profit_filename)
    receipt_path = os.path.join(PROJECT_DIR, receipt_filename)
    
    with open(quote_path, 'w', encoding='utf-8') as f:
        f.write(quote_text)
    
    with open(profit_path, 'w', encoding='utf-8') as f:
        f.write(quote_text)
        f.write(profit_text)
    
    with open(receipt_path, 'w', encoding='utf-8') as f:
        f.write(receipt_text)
    
    print("\n" + "=" * 110)
    print("[OK] Quote generated successfully!")
    print("=" * 110)
    print(f"\nCustomer Quote:   {quote_filename}")
    print(f"Your Profit:      {profit_filename}")
    print(f"Delivery Receipt: {receipt_filename}")
    print(f"\nCustomer Total: {grand_total:,.2f} ISK")
    print(f"Your Net Profit: {your_profit:,.2f} ISK")
    print("\n" + "=" * 110)
    
    # Display quote
    print("\nCUSTOMER QUOTE PREVIEW:")
    print(quote_text)
    
    print("\n[OK] Files saved to project directory!")
    print("Send the customer quote file, and the receipt when order is complete!")


if __name__ == '__main__':
    main()