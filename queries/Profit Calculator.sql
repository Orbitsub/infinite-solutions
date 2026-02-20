-- @block Bookmarked query
-- @group EVE Saved Queries
-- @name Profit Calculator

-- ============================================
-- PROFIT CALCULATOR
-- ============================================
-- INSTRUCTIONS: Change the 4 VALUES below, then run the query
-- 
-- Example: Radar ECM II
-- - Buy at: 1,837,000 ISK
-- - Sell at: 2,072,000 ISK  
-- - Quantity: 11 units
--

WITH inputs AS (
    SELECT 
        341.8 as buy_price,      -- ← CHANGE THIS: Price you'll pay
        446.5 as sell_price,      -- ← CHANGE THIS: Price you'll sell at
        8772743 as quantity,               -- ← CHANGE THIS: Number of units
        'Radar ECM II' as item_name   -- ← CHANGE THIS: Item name (optional)
),
my_fees AS (
    SELECT 
        buy_cost_multiplier,
        sell_revenue_multiplier,
        broker_fee_percent,
        sales_tax_percent
    FROM v_my_trading_fees
)
SELECT 
    i.item_name,
    i.quantity as units,
    printf('%,d', CAST(i.buy_price AS INTEGER)) || ' ISK' as buy_price,
    printf('%,d', CAST(i.sell_price AS INTEGER)) || ' ISK' as sell_price,
    -- Your actual costs/revenue after fees
    printf('%,d', CAST(i.buy_price * f.buy_cost_multiplier AS INTEGER)) || ' ISK' as actual_buy_cost,
    printf('%,d', CAST(i.sell_price * f.sell_revenue_multiplier AS INTEGER)) || ' ISK' as actual_sell_revenue,
    -- Per unit profit
    printf('%,d', CAST((i.sell_price * f.sell_revenue_multiplier) - (i.buy_price * f.buy_cost_multiplier) AS INTEGER)) || ' ISK' as profit_per_unit,
    -- Total profit
    printf('%,d', CAST(((i.sell_price * f.sell_revenue_multiplier) - (i.buy_price * f.buy_cost_multiplier)) * i.quantity AS INTEGER)) || ' ISK' as TOTAL_PROFIT,
    -- Margin
    printf('%,.2f', (((i.sell_price * f.sell_revenue_multiplier) - (i.buy_price * f.buy_cost_multiplier)) / (i.buy_price * f.buy_cost_multiplier)) * 100) || '%' as margin_percent,
    -- Capital required
    printf('%,d', CAST(i.buy_price * i.quantity AS INTEGER)) || ' ISK' as capital_required,
    -- ROI
    printf('%,.2f', (((i.sell_price * f.sell_revenue_multiplier) - (i.buy_price * f.buy_cost_multiplier)) / (i.buy_price * f.buy_cost_multiplier)) * 100) || '%' as roi,
    -- Simple verdict
    CASE 
        WHEN (i.sell_price * f.sell_revenue_multiplier) > (i.buy_price * f.buy_cost_multiplier) THEN '✓ PROFITABLE'
        ELSE '✗ WOULD LOSE MONEY'
    END as verdict
FROM inputs i
CROSS JOIN my_fees f;