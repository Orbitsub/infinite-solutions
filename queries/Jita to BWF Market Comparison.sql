-- ============================================
-- COMPLETE Jita → BWF Arbitrage Analysis
-- ============================================
-- Shows ALL items in Jita, including those with 0 orders in BWF
-- This lets you find market gaps!
-- ============================================

WITH trading_fees AS (
    SELECT 
        buy_cost_multiplier,
        sell_revenue_multiplier
    FROM v_my_trading_fees
    LIMIT 1
),
jita_prices AS (
    SELECT
        mo.type_id,
        MAX(CASE WHEN mo.is_buy_order = 1 THEN mo.price END) as best_buy_price,
        MIN(CASE WHEN mo.is_buy_order = 0 THEN mo.price END) as lowest_sell_price,
        SUM(mo.volume_remain) as total_volume
    FROM market_orders mo
    GROUP BY mo.type_id
),
bwf_prices AS (
    SELECT 
        bmo.type_id,
        MAX(CASE WHEN bmo.is_buy_order = 1 THEN bmo.price END) as best_buy_price,
        MIN(CASE WHEN bmo.is_buy_order = 0 THEN bmo.price END) as lowest_sell_price,
        SUM(bmo.volume_remain) as total_volume
    FROM bwf_market_orders bmo
    GROUP BY bmo.type_id
),
bwf_order_counts AS (
    SELECT
        type_id,
        COUNT(*) AS total_orders,
        SUM(CASE WHEN is_buy_order = 1 THEN 1 ELSE 0 END) AS buy_orders,
        SUM(CASE WHEN is_buy_order = 0 THEN 1 ELSE 0 END) AS sell_orders,
        SUM(volume_remain) AS total_units_available
    FROM bwf_market_orders
    GROUP BY type_id
),
profit_tiers AS (
    SELECT
        it.type_id,
        it.type_name AS item_name,
        it.volume AS item_volume_m3,
        ig.group_name AS item_group,
        ic.category_name AS item_category,
        mg.market_group_name,
        pmg.market_group_name AS parent_market_group_name,
        
        -- Jita prices
        jp.best_buy_price AS jita_buy_base,
        jp.best_buy_price * tf.buy_cost_multiplier AS jita_buy_with_fees,
        jp.lowest_sell_price AS jita_sell_base,
        jp.lowest_sell_price * tf.sell_revenue_multiplier AS jita_sell_with_fees,
        jp.total_volume AS jita_total_volume,
        
        -- BWF prices (may be NULL if no orders)
        bp.best_buy_price AS bwf_buy_base,
        bp.best_buy_price * tf.buy_cost_multiplier AS bwf_buy_with_fees,
        bp.lowest_sell_price AS bwf_sell_base,
        bp.lowest_sell_price * tf.sell_revenue_multiplier AS bwf_sell_with_fees,
        bp.total_volume AS bwf_total_volume,
        
        -- Freight costs per unit
        it.volume * 4200 AS freight_tier1_per_unit,
        it.volume * 2000 AS freight_tier2_per_unit,
        it.volume * 1400 AS freight_tier3_per_unit,
        
        -- Collateral (1% of Jita buy price)
        jp.best_buy_price * 0.01 AS collateral_fee,
        
        -- ============================================
        -- PROFIT CALCULATIONS
        -- ============================================
        -- Only calculate if BWF has sell orders to compete with
        
        CASE 
            WHEN bp.lowest_sell_price IS NOT NULL THEN
                (bp.lowest_sell_price * tf.sell_revenue_multiplier) - 
                (jp.best_buy_price * tf.buy_cost_multiplier) - 
                (it.volume * 4200) - 
                (jp.best_buy_price * 0.01)
            ELSE NULL
        END AS tier_1_profit,
        
        CASE 
            WHEN bp.lowest_sell_price IS NOT NULL THEN
                (bp.lowest_sell_price * tf.sell_revenue_multiplier) - 
                (jp.best_buy_price * tf.buy_cost_multiplier) - 
                (it.volume * 2000) - 
                (jp.best_buy_price * 0.01)
            ELSE NULL
        END AS tier_2_profit,
        
        CASE 
            WHEN bp.lowest_sell_price IS NOT NULL THEN
                (bp.lowest_sell_price * tf.sell_revenue_multiplier) - 
                (jp.best_buy_price * tf.buy_cost_multiplier) - 
                (it.volume * 1400) - 
                (jp.best_buy_price * 0.01)
            ELSE NULL
        END AS tier_3_profit
        
    FROM inv_types it
    CROSS JOIN trading_fees tf
    JOIN inv_groups ig ON ig.group_id = it.group_id
    JOIN inv_categories ic ON ic.category_id = ig.category_id
    LEFT JOIN inv_market_groups mg ON it.market_group_id = mg.market_group_id
    LEFT JOIN inv_market_groups pmg ON mg.parent_group_id = pmg.market_group_id
    LEFT JOIN jita_prices jp ON jp.type_id = it.type_id
    LEFT JOIN bwf_prices bp ON bp.type_id = it.type_id
    
    WHERE it.published = 1  -- Only published items
      AND jp.best_buy_price IS NOT NULL  -- Must be available in Jita
),
profit_metrics AS (
    SELECT
        type_id,
        tier_1_profit,
        tier_2_profit,
        tier_3_profit,
        jita_buy_with_fees,
        freight_tier1_per_unit,
        freight_tier2_per_unit,
        freight_tier3_per_unit,
        collateral_fee,
        item_volume_m3,
        
        -- Profit margins
        CASE 
            WHEN tier_1_profit IS NOT NULL THEN
                (tier_1_profit / NULLIF((jita_buy_with_fees + freight_tier1_per_unit + collateral_fee), 0)) * 100
            ELSE NULL
        END AS tier_1_margin_percent,
        
        CASE 
            WHEN tier_2_profit IS NOT NULL THEN
                (tier_2_profit / NULLIF((jita_buy_with_fees + freight_tier2_per_unit + collateral_fee), 0)) * 100
            ELSE NULL
        END AS tier_2_margin_percent,
        
        CASE 
            WHEN tier_3_profit IS NOT NULL THEN
                (tier_3_profit / NULLIF((jita_buy_with_fees + freight_tier3_per_unit + collateral_fee), 0)) * 100
            ELSE NULL
        END AS tier_3_margin_percent,
        
        -- ISK density
        CASE 
            WHEN tier_1_profit IS NOT NULL THEN
                tier_1_profit / NULLIF(item_volume_m3, 0)
            ELSE NULL
        END AS tier_1_isk_per_m3,
        
        CASE 
            WHEN tier_2_profit IS NOT NULL THEN
                tier_2_profit / NULLIF(item_volume_m3, 0)
            ELSE NULL
        END AS tier_2_isk_per_m3,
        
        CASE 
            WHEN tier_3_profit IS NOT NULL THEN
                tier_3_profit / NULLIF(item_volume_m3, 0)
            ELSE NULL
        END AS tier_3_isk_per_m3
        
    FROM profit_tiers
)

-- ============================================
-- FINAL OUTPUT
-- ============================================
SELECT
    --pt.parent_market_group_name,
    --pt.market_group_name,
    pt.item_name,
    --pt.item_category,
    --pt.item_group,
    --printf('%.2f m³', pt.item_volume_m3) AS item_volume,
    
    -- Market Info
    printf('%,.2f ISK', pt.jita_buy_base) AS jita_buy_base,
    CASE 
        WHEN pt.bwf_sell_base IS NOT NULL THEN printf('%,.2f ISK', pt.bwf_sell_base)
        ELSE 'No BWF orders'
    END AS bwf_sell_base,
    
    printf('%,d units', CAST(COALESCE(oc.total_units_available, 0) AS INTEGER)) AS bwf_available,
    printf('%,d orders', COALESCE(oc.total_orders, 0)) AS bwf_orders,
    
    -- Market status
    CASE
        WHEN oc.total_orders IS NULL OR oc.total_orders = 0 THEN '🚨 NO BWF MARKET'
        WHEN oc.total_orders = 1 THEN '⚠️ Only 1 order'
        WHEN oc.total_orders <= 3 THEN '📈 Low coverage'
        ELSE '✅ Active market'
    END AS market_status,
    
    -- ============================================
    -- TIER 1: BLOCKADE RUNNER (0-10k m³)
    -- ============================================
    -- CASE 
    --     WHEN pm.tier_1_profit IS NOT NULL THEN printf('%,.0f ISK', pm.tier_1_profit)
    --     ELSE 'N/A'
    -- END AS tier_1_profit,
    CASE 
        WHEN pm.tier_1_margin_percent IS NOT NULL THEN printf('%.1f%%', pm.tier_1_margin_percent)
        ELSE 'N/A'
    END AS tier_1_margin,
    -- CASE 
    --     WHEN pm.tier_1_isk_per_m3 IS NOT NULL THEN printf('%,.0f ISK/m³', pm.tier_1_isk_per_m3)
    --     ELSE 'N/A'
    -- END AS tier_1_density,
    
    -- ============================================
    -- TIER 2: DEEP SPACE TRANSPORT (10k-60k m³)
    -- ============================================
    -- CASE 
    --     WHEN pm.tier_2_profit IS NOT NULL THEN printf('%,.0f ISK', pm.tier_2_profit)
    --     ELSE 'N/A'
    -- END AS tier_2_profit,
    CASE 
        WHEN pm.tier_2_margin_percent IS NOT NULL THEN printf('%.1f%%', pm.tier_2_margin_percent)
        ELSE 'N/A'
    END AS tier_2_margin,
    -- CASE 
    --     WHEN pm.tier_2_isk_per_m3 IS NOT NULL THEN printf('%,.0f ISK/m³', pm.tier_2_isk_per_m3)
    --     ELSE 'N/A'
    -- END AS tier_2_density,
    
    -- ============================================
    -- TIER 3: JUMP FREIGHTER (60k-300k m³)
    -- ============================================
    -- CASE 
    --     WHEN pm.tier_3_profit IS NOT NULL THEN printf('%,.0f ISK', pm.tier_3_profit)
    --     ELSE 'N/A'
    -- END AS tier_3_profit,
    CASE 
        WHEN pm.tier_3_margin_percent IS NOT NULL THEN printf('%.1f%%', pm.tier_3_margin_percent)
        ELSE 'N/A'
    END AS tier_3_margin
    -- CASE 
    --     WHEN pm.tier_3_isk_per_m3 IS NOT NULL THEN printf('%,.0f ISK/m³', pm.tier_3_isk_per_m3)
    --     ELSE 'N/A'
    -- END AS tier_3_density

FROM profit_tiers pt
LEFT JOIN profit_metrics pm ON pm.type_id = pt.type_id
LEFT JOIN bwf_order_counts oc ON oc.type_id = pt.type_id

-- ============================================
-- FILTERS
-- ============================================

WHERE
    pt.type_id IN (SELECT type_id FROM jita_hangar_inventory)
    --(pm.tier_1_profit > 0 OR pm.tier_1_profit = 'N/A') AND
    --(oc.total_orders IS NULL OR oc.total_orders = 0)
ORDER BY parent_market_group_name,market_group_name,item_name