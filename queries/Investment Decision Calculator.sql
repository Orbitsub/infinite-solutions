-- ============================================
-- INVESTMENT DECISION CALCULATOR
-- ============================================
-- INSTRUCTIONS: Change the item name below, then run

WITH target_item AS (
    SELECT 'Small Focused Pulse Laser II' as item_name  -- ← CHANGE THIS
),
item_analysis AS (
    SELECT 
        t.type_id,
        t.type_name,
        -- Current market
        MAX(CASE WHEN mo.is_buy_order = 1 THEN mo.price END) as best_buy,
        MIN(CASE WHEN mo.is_buy_order = 0 THEN mo.price END) as best_sell,
        COUNT(CASE WHEN mo.is_buy_order = 1 THEN 1 END) as buy_order_count,
        COUNT(CASE WHEN mo.is_buy_order = 0 THEN 1 END) as sell_order_count,
        SUM(CASE WHEN mo.is_buy_order = 1 THEN mo.volume_remain END) as total_buy_volume,
        -- Historical data
        COALESCE((SELECT AVG(volume) FROM market_history 
                  WHERE type_id = t.type_id 
                  AND date >= date('now', '-7 days') 
                  AND region_id = 10000002), 0) as avg_daily_volume,
        COALESCE((SELECT AVG(average) FROM market_history 
                  WHERE type_id = t.type_id 
                  AND date >= date('now', '-30 days') 
                  AND region_id = 10000002), 0) as avg_price_30day,
        -- Recent competition activity
        MAX(CASE WHEN mo.is_buy_order = 1 THEN mo.issued END) as last_buy_update,
        MAX(CASE WHEN mo.is_buy_order = 0 THEN mo.issued END) as last_sell_update
    FROM inv_types t
    JOIN target_item ti ON t.type_name = ti.item_name
    LEFT JOIN market_orders mo ON t.type_id = mo.type_id 
        AND mo.location_id = 60003760 
        AND mo.region_id = 10000002
    GROUP BY t.type_id, t.type_name
),
my_fees AS (
    SELECT 
        buy_cost_multiplier,
        sell_revenue_multiplier,
        broker_fee_percent,
        sales_tax_percent
    FROM v_my_trading_fees
),
calculations AS (
    SELECT 
        ia.type_name,
        ia.best_buy,
        ia.best_sell,
        ia.buy_order_count,
        ia.sell_order_count,
        ia.avg_daily_volume,
        ia.last_buy_update,
        ia.last_sell_update,
        f.buy_cost_multiplier,
        f.sell_revenue_multiplier,
        f.broker_fee_percent,
        f.sales_tax_percent,
        -- If you place a buy order at current best buy + 0.01
        ROUND((ia.best_buy + 0.01) * f.buy_cost_multiplier, 2) as your_buy_cost,
        -- If you place a sell order at current best sell - 0.01
        ROUND((ia.best_sell - 0.01) * f.sell_revenue_multiplier, 2) as your_sell_revenue,
        -- Profit per unit
        ROUND(((ia.best_sell - 0.01) * f.sell_revenue_multiplier) - ((ia.best_buy + 0.01) * f.buy_cost_multiplier), 2) as profit_per_unit,
        -- Margin
        ROUND(((((ia.best_sell - 0.01) * f.sell_revenue_multiplier) - ((ia.best_buy + 0.01) * f.buy_cost_multiplier)) / ((ia.best_buy + 0.01) * f.buy_cost_multiplier)) * 100, 2) as margin_percent,
        -- Daily profit potential
        ROUND(((((ia.best_sell - 0.01) * f.sell_revenue_multiplier) - ((ia.best_buy + 0.01) * f.buy_cost_multiplier)) * ia.avg_daily_volume), 0) as daily_profit_potential,
        -- Competition freshness
        ROUND((JULIANDAY('now') - JULIANDAY(ia.last_buy_update)) * 24, 1) as hours_since_buy_competition,
        ROUND((JULIANDAY('now') - JULIANDAY(ia.last_sell_update)) * 24, 1) as hours_since_sell_competition
    FROM item_analysis ia
    CROSS JOIN my_fees f
),
report AS (
    SELECT 
        1 as sort_order,
        '=== ITEM DETAILS ===' as section,
        type_name as detail
    FROM calculations
    
    UNION ALL SELECT 2, 'Current top buy:', printf('%,.2f', best_buy) || ' ISK' FROM calculations
    UNION ALL SELECT 3, 'Current lowest sell:', printf('%,.2f', best_sell) || ' ISK' FROM calculations
    UNION ALL SELECT 4, 'Buy competition:', buy_order_count || ' orders' FROM calculations
    UNION ALL SELECT 5, 'Sell competition:', sell_order_count || ' orders' FROM calculations
    UNION ALL SELECT 6, 'Daily volume:', printf('%,.0f', avg_daily_volume) || ' units/day' FROM calculations
    UNION ALL SELECT 7, '', '' FROM calculations
    
    UNION ALL SELECT 10, '=== YOUR COSTS ===', '' FROM calculations
    UNION ALL SELECT 11, 'If you place buy at:', printf('%,.2f', best_buy + 0.01) || ' ISK' FROM calculations
    UNION ALL SELECT 12, 'Your true cost:', printf('%,.2f', your_buy_cost) || ' ISK' FROM calculations
    UNION ALL SELECT 13, 'Includes broker fee:', printf('%.2f', broker_fee_percent) || '%' FROM calculations
    UNION ALL SELECT 14, '', '' FROM calculations
    
    UNION ALL SELECT 20, '=== YOUR REVENUE ===', '' FROM calculations
    UNION ALL SELECT 21, 'If you place sell at:', printf('%,.2f', best_sell - 0.01) || ' ISK' FROM calculations
    UNION ALL SELECT 22, 'Your true revenue:', printf('%,.2f', your_sell_revenue) || ' ISK' FROM calculations
    UNION ALL SELECT 23, 'After total fees:', printf('%.2f', (100 - (sell_revenue_multiplier * 100))) || '%' FROM calculations
    UNION ALL SELECT 24, '', '' FROM calculations
    
    UNION ALL SELECT 30, '=== PROFITABILITY ===', '' FROM calculations
    UNION ALL SELECT 31, 'Profit per unit:', printf('%,.2f', profit_per_unit) || ' ISK' FROM calculations
    UNION ALL SELECT 32, 'Profit margin:', printf('%.2f', margin_percent) || '%' FROM calculations
    UNION ALL SELECT 33, 'Daily profit potential:', printf('%,.0f', daily_profit_potential) || ' ISK/day' FROM calculations
    UNION ALL SELECT 34, 'Margin rating:', 
        CASE 
            WHEN margin_percent >= 10 THEN 'EXCELLENT'
            WHEN margin_percent >= 5 THEN 'GOOD'
            WHEN margin_percent >= 3 THEN 'ACCEPTABLE'
            ELSE 'LOW - risky'
        END FROM calculations
    UNION ALL SELECT 35, '', '' FROM calculations
    
    UNION ALL SELECT 40, '=== LIQUIDITY ===', '' FROM calculations
    UNION ALL SELECT 41, 'Daily volume:', printf('%,.0f', avg_daily_volume) || ' units' FROM calculations
    UNION ALL SELECT 42, 'Liquidity rating:',
        CASE 
            WHEN avg_daily_volume > 1000 THEN 'EXCELLENT - Very liquid'
            WHEN avg_daily_volume > 500 THEN 'VERY GOOD'
            WHEN avg_daily_volume > 200 THEN 'GOOD'
            WHEN avg_daily_volume > 50 THEN 'FAIR'
            ELSE 'LOW - Slow'
        END FROM calculations
    UNION ALL SELECT 43, '1 week supply:', printf('%,.0f', avg_daily_volume * 7) || ' units' FROM calculations
    UNION ALL SELECT 44, 'Capital for 1 week:', printf('%,.0f', (best_buy + 0.01) * avg_daily_volume * 7) || ' ISK' FROM calculations
    UNION ALL SELECT 45, '', '' FROM calculations
    
    UNION ALL SELECT 50, '=== COMPETITION ===', '' FROM calculations
    UNION ALL SELECT 51, 'Total orders:', (buy_order_count + sell_order_count) || ' orders' FROM calculations
    UNION ALL SELECT 52, 'Last buy update:', printf('%.1f', hours_since_buy_competition) || ' hours ago' FROM calculations
    UNION ALL SELECT 53, 'Last sell update:', printf('%.1f', hours_since_sell_competition) || ' hours ago' FROM calculations
    UNION ALL SELECT 54, 'Competition level:',
        CASE 
            WHEN buy_order_count + sell_order_count < 10 THEN 'LOW - Easy'
            WHEN buy_order_count + sell_order_count < 30 THEN 'MODERATE'
            WHEN buy_order_count + sell_order_count < 60 THEN 'HIGH'
            ELSE 'VERY HIGH'
        END FROM calculations
    UNION ALL SELECT 55, '', '' FROM calculations
    
    UNION ALL SELECT 60, '=== RECOMMENDATION ===', '' FROM calculations
    UNION ALL SELECT 61, 'Decision:',
        CASE 
            -- STRONG BUY: 10%+ margin, good volume, low competition
            WHEN margin_percent >= 10 AND avg_daily_volume >= 100 AND buy_order_count + sell_order_count < 30 
            THEN 'STRONG BUY - Meets your 10% minimum with good conditions'
            
            -- BUY: 10%+ margin, decent volume
            WHEN margin_percent >= 10 AND avg_daily_volume >= 50 
            THEN 'BUY - Meets your 10% margin requirement'
            
            -- MAYBE: 10%+ margin but low volume
            WHEN margin_percent >= 10 AND avg_daily_volume >= 20 
            THEN 'MAYBE - Good margin but low volume (slow sales)'
            
            -- RISKY: Good margin but very high competition
            WHEN margin_percent >= 10 AND buy_order_count + sell_order_count > 60 
            THEN 'RISKY - Good margin but very high competition (constant updates)'
            
            -- BELOW YOUR MINIMUM: 5-10% margin
            WHEN margin_percent >= 5 AND margin_percent < 10
            THEN 'BELOW MINIMUM - Only ' || printf('%.2f', margin_percent) || '% margin (you want 10%+)'
            
            -- BELOW YOUR MINIMUM: 3-5% margin
            WHEN margin_percent >= 3 AND margin_percent < 5
            THEN 'AVOID - Only ' || printf('%.2f', margin_percent) || '% margin (well below your 10% minimum)'
            
            -- Too low margin
            WHEN margin_percent < 3 
            THEN 'AVOID - Margin too low (' || printf('%.2f', margin_percent) || '% vs your 10% minimum)'
            
            -- Good margin but no volume
            WHEN margin_percent >= 10 AND avg_daily_volume < 20 
            THEN 'AVOID - Good margin but extremely low volume (inventory will sit)'
            
            ELSE 'REVIEW - Check details carefully'
        END FROM calculations
    UNION ALL SELECT 62, '', '' FROM calculations
    UNION ALL SELECT 63, 'Margin target:', 'Your minimum is 10%' FROM calculations
    UNION ALL SELECT 64, 'Current margin:', printf('%.2f', margin_percent) || '%' FROM calculations
    UNION ALL SELECT 65, 'Margin status:',
        CASE 
            WHEN margin_percent >= 15 THEN 'EXCELLENT - Well above your 10% minimum'
            WHEN margin_percent >= 10 THEN 'MEETS TARGET - At or above your 10% minimum'
            WHEN margin_percent >= 5 THEN 'BELOW TARGET - ' || printf('%.2f', 10 - margin_percent) || '% short of your minimum'
            ELSE 'WELL BELOW TARGET - ' || printf('%.2f', 10 - margin_percent) || '% short of your minimum'
        END FROM calculations
)
SELECT section, detail
FROM report
ORDER BY sort_order;