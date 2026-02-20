--DROP VIEW IF EXISTS v_reinvestment_opportunities;

--CREATE VIEW IF NOT EXISTS v_reinvestment_opportunities AS
WITH my_fees AS (
    SELECT
        buy_cost_multiplier,
        sell_revenue_multiplier
    FROM v_my_trading_fees
    LIMIT 1
),
my_buys AS (
    -- Your most recent purchases (filled buy orders)
    SELECT 
        wt.type_id,
        t.type_name,
        wt.unit_price as my_buy_price,
        wt.quantity as buy_quantity,
        wt.date as buy_date,
        ROW_NUMBER() OVER (PARTITION BY wt.type_id ORDER BY wt.date DESC) as recency_rank
    FROM wallet_transactions wt
    JOIN inv_types t ON wt.type_id = t.type_id
    WHERE wt.is_buy = 1
    AND wt.date >= date('now', '-30 days')
),
my_sells AS (
    -- Your most recent sales (filled sell orders)
    SELECT 
        wt.type_id,
        wt.unit_price as my_sell_price,
        wt.quantity as sell_quantity,
        wt.date as sell_date,
        ROW_NUMBER() OVER (PARTITION BY wt.type_id ORDER BY wt.date DESC) as recency_rank
    FROM wallet_transactions wt
    WHERE wt.is_buy = 0
    AND wt.date >= date('now', '-30 days')
),
my_completed_cycles AS (
    -- Match your completed buy/sell cycles
    SELECT 
        mb.type_id,
        mb.type_name,
        mb.my_buy_price,
        mb.buy_quantity,
        mb.buy_date,
        ms.my_sell_price,
        ms.sell_quantity,
        ms.sell_date,
        f.buy_cost_multiplier,
        f.sell_revenue_multiplier,
        
        -- Your actual profit per unit
        ROUND(
            (ms.my_sell_price * f.sell_revenue_multiplier) - 
            (mb.my_buy_price * f.buy_cost_multiplier),
            2
        ) as my_profit_per_unit,
        
        -- Your ROI %
        ROUND(
            ((ms.my_sell_price * f.sell_revenue_multiplier) - 
             (mb.my_buy_price * f.buy_cost_multiplier)) /
            (mb.my_buy_price * f.buy_cost_multiplier) * 100,
            2
        ) as my_roi_percent
        
    FROM my_buys mb
    JOIN my_sells ms ON mb.type_id = ms.type_id
    CROSS JOIN my_fees f
    WHERE mb.recency_rank = 1
    AND ms.recency_rank = 1
),
current_market AS (
    -- Current best buy and sell orders
    SELECT
        mo.type_id,
        MAX(CASE WHEN mo.is_buy_order = 1 THEN mo.price END) as current_best_buy,
        MIN(CASE WHEN mo.is_buy_order = 0 THEN mo.price END) as current_lowest_sell
    FROM market_orders mo
    WHERE mo.location_id = 60003760
    AND mo.region_id = 10000002
    GROUP BY mo.type_id
)
SELECT 
    cc.type_name,
    
    -- YOUR LAST COMPLETED CYCLE
    -- printf('%,.2f', cc.my_buy_price) || ' ISK' as your_buy_price,
    -- printf('%,.2f', cc.my_sell_price) || ' ISK' as your_sell_price,
    -- printf('%,.2f', cc.my_profit_per_unit) || ' ISK' as your_profit,
    printf('%.1f', cc.my_roi_percent) || '%' as your_roi,
    -- cc.buy_quantity as qty_bought,
    -- cc.sell_quantity as qty_sold,
    -- DATE(cc.buy_date) as last_buy,
    DATE(cc.sell_date) as last_sell,
    
    -- CURRENT MARKET SPREAD
    -- printf('%,.2f', cm.current_best_buy) || ' ISK' as current_best_buy,
    -- printf('%,.2f', cm.current_lowest_sell) || ' ISK' as current_lowest_sell,
    -- printf('%,.2f', cm.current_lowest_sell - cm.current_best_buy) || ' ISK' as current_spread,
    
    --IF YOU POST SAME ORDERS AGAIN
    -- ROUND(
    --     (cc.my_sell_price * cc.sell_revenue_multiplier) - 
    --     (cc.my_buy_price * cc.buy_cost_multiplier),
    --     2
    -- ) as profit_if_repeat,
    
    -- ROUND(
    --     ((cc.my_sell_price * cc.sell_revenue_multiplier) - 
    --      (cc.my_buy_price * cc.buy_cost_multiplier)) /
    --     (cc.my_buy_price * cc.buy_cost_multiplier) * 100,
    --     2
    -- ) as roi_if_repeat,
    
    -- IF YOU POST AT CURRENT BEST PRICES (competitive orders)
    -- ROUND(
    --     (cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
    --     (cm.current_best_buy * cc.buy_cost_multiplier),
    --     2
    -- ) as profit_at_current_best,
    
    -- ROUND(
    --     ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
    --      (cm.current_best_buy * cc.buy_cost_multiplier)) /
    --     (cm.current_best_buy * cc.buy_cost_multiplier) * 100,
    --     2
    -- ) as roi_at_current_best,
    
    -- printf('%,.2f', 
    --     ROUND(
    --         (cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
    --         (cm.current_best_buy * cc.buy_cost_multiplier),
    --         2
    --     )
    -- ) || ' ISK' as profit_display,
    
    printf('%.1f', 
        ROUND(
            ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
             (cm.current_best_buy * cc.buy_cost_multiplier)) /
            (cm.current_best_buy * cc.buy_cost_multiplier) * 100,
            2
        )
    ) || '%' as roi_display,
    
    -- PROFIT CHANGE vs YOUR LAST CYCLE
    -- ROUND(
    --     ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
    --      (cm.current_best_buy * cc.buy_cost_multiplier)) - cc.my_profit_per_unit,
    --     2
    -- ) as profit_change,
    
    -- printf('%.1f', 
    --     ROUND(
    --         (((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
    --           (cm.current_best_buy * cc.buy_cost_multiplier)) - cc.my_profit_per_unit) / 
    --         ABS(cc.my_profit_per_unit) * 100,
    --         1
    --     )
    -- ) || '%' as profit_change_pct,
    
    -- RECOMMENDATION
    CASE 
        -- High value item (>1M ISK): 5% ROI minimum
        WHEN cm.current_best_buy >= 1000000 
        THEN CASE 
            WHEN ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
                  (cm.current_best_buy * cc.buy_cost_multiplier)) /
                 (cm.current_best_buy * cc.buy_cost_multiplier) * 100 >= 5
            THEN '✓ REINVEST (5%+ ROI on high-value)'
            WHEN ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
                  (cm.current_best_buy * cc.buy_cost_multiplier)) > 0
            THEN '⚠ MARGINAL (Profitable but <5% ROI)'
            ELSE '✗ SKIP (Not profitable)'
        END
        
        -- Normal item: 10% ROI minimum
        ELSE CASE 
            WHEN ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
                  (cm.current_best_buy * cc.buy_cost_multiplier)) /
                 (cm.current_best_buy * cc.buy_cost_multiplier) * 100 >= 10
            THEN '✓ REINVEST (10%+ ROI)'
            WHEN ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
                  (cm.current_best_buy * cc.buy_cost_multiplier)) > 0
            THEN '⚠ MARGINAL (Profitable but <10% ROI)'
            ELSE '✗ SKIP (Not profitable)'
        END
    END as recommendation,
    
    -- SUGGESTED ORDERS
    'BUY ORDER: ' || printf('%,.2f', cm.current_best_buy + 0.01) || ' ISK' as suggested_buy_order,
    'SELL ORDER: ' || printf('%,.2f', cm.current_lowest_sell - 0.01) || ' ISK' as suggested_sell_order

FROM my_completed_cycles cc
JOIN current_market cm ON cc.type_id = cm.type_id
WHERE cm.current_best_buy IS NOT NULL
AND cm.current_lowest_sell IS NOT NULL
AND cm.current_lowest_sell > cm.current_best_buy  -- Must have spread
ORDER BY 
    -- CASE 
    --     WHEN cm.current_best_buy >= 1000000 
    --     THEN CASE 
    --         WHEN ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
    --               (cm.current_best_buy * cc.buy_cost_multiplier)) /
    --              (cm.current_best_buy * cc.buy_cost_multiplier) * 100 >= 5
    --         THEN 1 ELSE 2 
    --     END
    --     ELSE CASE 
    --         WHEN ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
    --               (cm.current_best_buy * cc.buy_cost_multiplier)) /
    --              (cm.current_best_buy * cc.buy_cost_multiplier) * 100 >= 10
    --         THEN 1 ELSE 2 
    --     END
    -- END,
            ROUND(
            ((cm.current_lowest_sell * cc.sell_revenue_multiplier) - 
             (cm.current_best_buy * cc.buy_cost_multiplier)) /
            (cm.current_best_buy * cc.buy_cost_multiplier) * 100,
            2
        ) DESC;