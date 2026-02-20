-- ============================================================
-- FIXED: FAT FINGER QUERY - NO CORRELATED SUBQUERIES
-- ============================================================
WITH my_fees AS (
    SELECT
        buy_cost_multiplier,
        sell_revenue_multiplier
    FROM v_my_trading_fees
    LIMIT 1
),

-- Historical averages
historical_averages AS (
    SELECT 
        type_id,
        AVG(CASE WHEN date >= date('now', '-1 days') THEN average END) as daily_avg,
        AVG(CASE WHEN date >= date('now', '-7 days') THEN average END) as weekly_avg,
        AVG(CASE WHEN date >= date('now', '-30 days') THEN average END) as monthly_avg,
        AVG(average) as yearly_avg
    FROM market_history
    WHERE region_id = 10000002
    AND date >= date('now', '-365 days')
    GROUP BY type_id
),

-- Get all sell orders ranked by price
ranked_sells AS (
    SELECT
        type_id,
        price,
        volume_remain,
        ROW_NUMBER() OVER (PARTITION BY type_id ORDER BY price ASC) as price_rank
    FROM market_orders
    WHERE location_id = 60003760
    AND region_id = 10000002
    AND is_buy_order = 0
),

-- Current market summary
current_orders AS (
    SELECT
        mo.type_id,
        t.type_name,
        
        -- Highest buy order
        MAX(CASE WHEN mo.is_buy_order = 1 THEN mo.price END) as best_buy_price,
        
        -- Lowest sell order
        MIN(CASE WHEN mo.is_buy_order = 0 THEN mo.price END) as best_sell_price
        
    FROM market_orders mo
    JOIN inv_types t ON mo.type_id = t.type_id
    WHERE mo.location_id = 60003760
    AND mo.region_id = 10000002
    GROUP BY mo.type_id, t.type_name
),

-- Get volume at lowest sell price
fat_finger_volumes AS (
    SELECT
        mo.type_id,
        SUM(mo.volume_remain) as fat_finger_volume
    FROM market_orders mo
    JOIN current_orders co ON mo.type_id = co.type_id 
        AND mo.price = co.best_sell_price
        AND mo.is_buy_order = 0
    WHERE mo.location_id = 60003760
    AND mo.region_id = 10000002
    GROUP BY mo.type_id
),

-- Join with second lowest sell and volumes
orders_with_second AS (
    SELECT
        co.*,
        ffv.fat_finger_volume,
        rs.price as second_lowest_sell
    FROM current_orders co
    LEFT JOIN fat_finger_volumes ffv ON ffv.type_id = co.type_id
    LEFT JOIN ranked_sells rs ON rs.type_id = co.type_id AND rs.price_rank = 2
),

-- Calculate everything
calculations AS (
    SELECT 
        co.type_name,
        co.fat_finger_volume as units,
        co.best_buy_price,
        co.best_sell_price,
        co.second_lowest_sell,
        f.buy_cost_multiplier,
        f.sell_revenue_multiplier,
        
        -- Historical prices
        ha.daily_avg,
        ha.weekly_avg,
        ha.monthly_avg,
        ha.yearly_avg,
        
        -- Spread
        co.best_sell_price - co.best_buy_price as buy_sell_spread,
        
        -- Buy cost with fees
        co.best_sell_price * f.buy_cost_multiplier as buy_cost_per_unit,
        
        -- Capital needed
        co.best_sell_price * f.buy_cost_multiplier * co.fat_finger_volume as capital_required,
        
        -- Profit at second lowest
        ((co.second_lowest_sell * f.sell_revenue_multiplier) - 
         (co.best_sell_price * f.buy_cost_multiplier)) * co.fat_finger_volume as profit_at_second,
        
        -- ROI at second lowest
        ((co.second_lowest_sell * f.sell_revenue_multiplier) - 
         (co.best_sell_price * f.buy_cost_multiplier)) /
        (co.best_sell_price * f.buy_cost_multiplier) * 100 as roi_at_second,
        
        -- Profit at averages
        ((ha.daily_avg * f.sell_revenue_multiplier) - 
         (co.best_sell_price * f.buy_cost_multiplier)) * co.fat_finger_volume as profit_at_daily_avg,
        
        ((ha.weekly_avg * f.sell_revenue_multiplier) - 
         (co.best_sell_price * f.buy_cost_multiplier)) * co.fat_finger_volume as profit_at_weekly_avg,
        
        ((ha.monthly_avg * f.sell_revenue_multiplier) - 
         (co.best_sell_price * f.buy_cost_multiplier)) * co.fat_finger_volume as profit_at_monthly_avg,
        
        ((ha.yearly_avg * f.sell_revenue_multiplier) - 
         (co.best_sell_price * f.buy_cost_multiplier)) * co.fat_finger_volume as profit_at_yearly_avg
        
    FROM orders_with_second co
    CROSS JOIN my_fees f
    LEFT JOIN historical_averages ha ON co.type_id = ha.type_id
    
    WHERE co.second_lowest_sell IS NOT NULL
    AND co.best_sell_price IS NOT NULL
    AND co.best_buy_price IS NOT NULL
    AND co.second_lowest_sell > co.best_sell_price
    AND co.fat_finger_volume > 0
    
    -- Fat finger detection: tiny spread
    AND (co.best_sell_price - co.best_buy_price) IN 
        (0.01,0.1,1,10,100,1000,10000,100000,1000000,10000000,100000000,1000000000)
)

SELECT 
    type_name,
    units,
    printf('%,d', CAST(best_sell_price AS INTEGER)) || ' ISK' as fat_finger_price,
    printf('%,d', CAST(best_buy_price AS INTEGER)) || ' ISK' as buy_price,
    printf('%,.2f', buy_sell_spread) || ' ISK' as spread,
    printf('%,d', CAST(profit_at_second AS INTEGER)) || ' ISK' as profit_at_2nd,
    printf('%,d', CAST(capital_required AS INTEGER)) || ' ISK' as capital,
    printf('%.1f', roi_at_second) || '%' as roi,
    COALESCE(printf('%,d', CAST(daily_avg AS INTEGER)), 'N/A') || ' ISK' as daily_avg,
    COALESCE(printf('%,d', CAST(weekly_avg AS INTEGER)), 'N/A') || ' ISK' as weekly_avg,
    COALESCE(printf('%,d', CAST(monthly_avg AS INTEGER)), 'N/A') || ' ISK' as monthly_avg,
    COALESCE(printf('%,d', CAST(yearly_avg AS INTEGER)), 'N/A') || ' ISK' as yearly_avg,
    COALESCE(printf('%,d', CAST(profit_at_daily_avg AS INTEGER)), 'N/A') || ' ISK' as profit_at_daily,
    COALESCE(printf('%,d', CAST(profit_at_weekly_avg AS INTEGER)), 'N/A') || ' ISK' as profit_at_weekly,
    COALESCE(printf('%,d', CAST(profit_at_monthly_avg AS INTEGER)), 'N/A') || ' ISK' as profit_at_monthly,
    COALESCE(printf('%,d', CAST(profit_at_yearly_avg AS INTEGER)), 'N/A') || ' ISK' as profit_at_yearly

FROM calculations
WHERE 
    -- profit_at_second >= 1000000
    -- profit_at_daily >= 1000000
    profit_at_weekly >= 1000000
    -- profit_at_monthly_avg >= 1000000
    -- profit_at_yearly >= 1000000

ORDER BY profit_at_weekly_avg DESC;