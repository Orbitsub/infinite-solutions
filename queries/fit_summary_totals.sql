-- ============================================
-- FIT SUMMARY WITH ALL COSTS & TOTALS
-- ============================================
-- Complete breakdown with verification totals
-- Matches fit_pricing_detailed columns
-- ============================================

WITH combined_results AS (
    -- First, show all items
    SELECT 
        'ITEM' AS row_type,
        it.type_name AS name,
        dfi.quantity AS qty,
        
        -- Jita prices
        printf('%,.2f', COALESCE(jita.best_buy_price, 0)) AS jita_buy_each,
        printf('%,.2f', COALESCE(jita.best_sell_price, 0)) AS jita_sell_each,
        printf('%,.2f', dfi.quantity * COALESCE(jita.best_buy_price, 0)) AS jita_buy_total,
        printf('%,.2f', dfi.quantity * COALESCE(jita.best_sell_price, 0)) AS jita_sell_total,
        
        -- BWF prices
        printf('%,.2f', COALESCE(bwf.lowest_sell_price, 0)) AS bwf_sell_each,
        printf('%,.2f', dfi.quantity * COALESCE(bwf.lowest_sell_price, 0)) AS bwf_sell_total,
        
        -- Status
        CASE 
            WHEN bwf.lowest_sell_price IS NOT NULL THEN 'In BWF'
            ELSE 'Missing'
        END AS status,
        
        -- For sorting
        dfi.quantity * COALESCE(jita.best_buy_price, 0) AS sort_value

    FROM doctrine_fit_items dfi
    JOIN doctrine_fits df ON df.fit_id = dfi.fit_id
    JOIN inv_types it ON it.type_id = dfi.type_id

    LEFT JOIN (
        SELECT 
            type_id, 
            MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy_price,
            MIN(CASE WHEN is_buy_order = 0 THEN price END) AS best_sell_price
        FROM market_orders
        GROUP BY type_id
    ) jita ON jita.type_id = dfi.type_id

    LEFT JOIN (
        SELECT type_id, MIN(CASE WHEN is_buy_order = 0 THEN price END) AS lowest_sell_price
        FROM bwf_market_orders
        GROUP BY type_id
    ) bwf ON bwf.type_id = dfi.type_id

    WHERE df.fit_name = 'Nightmare - WC-EN - DPS Nightmare v1.3'

    UNION ALL

    -- Then, show totals row with all calculations
    SELECT 
        'TOTAL' AS row_type,
        '═══════════════════════════' AS name,
        SUM(dfi.quantity) AS qty,
        
        -- Jita totals
        '' AS jita_buy_each,
        '' AS jita_sell_each,
        printf('%,.2f', SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0))) AS jita_buy_total,
        printf('%,.2f', SUM(dfi.quantity * COALESCE(jita.best_sell_price, 0))) AS jita_sell_total,
        
        -- BWF totals
        '' AS bwf_sell_each,
        printf('%,.2f', SUM(dfi.quantity * COALESCE(bwf.lowest_sell_price, 0))) AS bwf_sell_total,
        
        printf('%d items, %d missing', 
            COUNT(*), 
            SUM(CASE WHEN bwf.lowest_sell_price IS NULL THEN 1 ELSE 0 END)
        ) AS status,
        
        999999999999 AS sort_value

    FROM doctrine_fit_items dfi
    JOIN doctrine_fits df ON df.fit_id = dfi.fit_id
    JOIN inv_types it ON it.type_id = dfi.type_id

    LEFT JOIN (
        SELECT 
            type_id, 
            MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy_price,
            MIN(CASE WHEN is_buy_order = 0 THEN price END) AS best_sell_price
        FROM market_orders
        GROUP BY type_id
    ) jita ON jita.type_id = dfi.type_id

    LEFT JOIN (
        SELECT type_id, MIN(CASE WHEN is_buy_order = 0 THEN price END) AS lowest_sell_price
        FROM bwf_market_orders
        GROUP BY type_id
    ) bwf ON bwf.type_id = dfi.type_id

    WHERE df.fit_name = 'Nightmare - WC-EN - DPS Nightmare v1.3'
    
    UNION ALL
    
    -- Add calculation rows at the bottom
    SELECT 
        'CALC' AS row_type,
        'Jita Tax (1.5%)' AS name,
        NULL AS qty,
        '' AS jita_buy_each,
        '' AS jita_sell_each,
        printf('%,.2f', SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 0.015) AS jita_buy_total,
        '' AS jita_sell_total,
        '' AS bwf_sell_each,
        '' AS bwf_sell_total,
        '' AS status,
        999999999998 AS sort_value
        
    FROM doctrine_fit_items dfi
    JOIN doctrine_fits df ON df.fit_id = dfi.fit_id
    JOIN inv_types it ON it.type_id = dfi.type_id
    LEFT JOIN (
        SELECT type_id, MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy_price
        FROM market_orders
        GROUP BY type_id
    ) jita ON jita.type_id = dfi.type_id
    WHERE df.fit_name = 'Nightmare - WC-EN - DPS Nightmare v1.3'
    
    UNION ALL
    
    SELECT 
        'CALC' AS row_type,
        'Total Jita Cost (Buy + Tax)' AS name,
        NULL AS qty,
        '' AS jita_buy_each,
        '' AS jita_sell_each,
        printf('%,.2f', SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015) AS jita_buy_total,
        '' AS jita_sell_total,
        '' AS bwf_sell_each,
        '' AS bwf_sell_total,
        '' AS status,
        999999999997 AS sort_value
        
    FROM doctrine_fit_items dfi
    JOIN doctrine_fits df ON df.fit_id = dfi.fit_id
    JOIN inv_types it ON it.type_id = dfi.type_id
    LEFT JOIN (
        SELECT type_id, MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy_price
        FROM market_orders
        GROUP BY type_id
    ) jita ON jita.type_id = dfi.type_id
    WHERE df.fit_name = 'Nightmare - WC-EN - DPS Nightmare v1.3'
    
    UNION ALL
    
    SELECT 
        'CALC' AS row_type,
        'Freight Cost (TEST)' AS name,
        NULL AS qty,
        '' AS jita_buy_each,
        '' AS jita_sell_each,
        printf('%,.2f',
            SUM(dfi.quantity * COALESCE(it.volume, 0) * 300) +
            (SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015 * 0.01)
        ) AS jita_buy_total,
        '' AS jita_sell_total,
        '' AS bwf_sell_each,
        '' AS bwf_sell_total,
        '' AS status,
        999999999996 AS sort_value
        
    FROM doctrine_fit_items dfi
    JOIN doctrine_fits df ON df.fit_id = dfi.fit_id
    JOIN inv_types it ON it.type_id = dfi.type_id
    LEFT JOIN (
        SELECT type_id, MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy_price
        FROM market_orders
        GROUP BY type_id
    ) jita ON jita.type_id = dfi.type_id
    WHERE df.fit_name = 'Nightmare - WC-EN - DPS Nightmare v1.3'
    
    UNION ALL
    
    SELECT 
        'CALC' AS row_type,
        'Total Sourcing Cost' AS name,
        NULL AS qty,
        '' AS jita_buy_each,
        '' AS jita_sell_each,
        printf('%,.2f',
            (SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015) +
            SUM(dfi.quantity * COALESCE(it.volume, 0) * 300) +
            (SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015 * 0.01)
        ) AS jita_buy_total,
        '' AS jita_sell_total,
        '' AS bwf_sell_each,
        '' AS bwf_sell_total,
        '← Your Total Cost' AS status,
        999999999995 AS sort_value
        
    FROM doctrine_fit_items dfi
    JOIN doctrine_fits df ON df.fit_id = dfi.fit_id
    JOIN inv_types it ON it.type_id = dfi.type_id
    LEFT JOIN (
        SELECT type_id, MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy_price
        FROM market_orders
        GROUP BY type_id
    ) jita ON jita.type_id = dfi.type_id
    WHERE df.fit_name = 'Nightmare - WC-EN - DPS Nightmare v1.3'
    
    UNION ALL
    
    SELECT 
        'CALC' AS row_type,
        'Customer Saves (BWF - Jita Sell)' AS name,
        NULL AS qty,
        '' AS jita_buy_each,
        '' AS jita_sell_each,
        '' AS jita_buy_total,
        '' AS jita_sell_total,
        '' AS bwf_sell_each,
        printf('%,.2f',
            SUM(dfi.quantity * COALESCE(bwf.lowest_sell_price, 0)) -
            SUM(dfi.quantity * COALESCE(jita.best_sell_price, 0))
        ) AS bwf_sell_total,
        '← Savings vs Jita' AS status,
        999999999994 AS sort_value
        
    FROM doctrine_fit_items dfi
    JOIN doctrine_fits df ON df.fit_id = dfi.fit_id
    JOIN inv_types it ON it.type_id = dfi.type_id
    LEFT JOIN (
        SELECT type_id, MIN(CASE WHEN is_buy_order = 0 THEN price END) AS best_sell_price
        FROM market_orders
        GROUP BY type_id
    ) jita ON jita.type_id = dfi.type_id
    LEFT JOIN (
        SELECT type_id, MIN(CASE WHEN is_buy_order = 0 THEN price END) AS lowest_sell_price
        FROM bwf_market_orders
        GROUP BY type_id
    ) bwf ON bwf.type_id = dfi.type_id
    WHERE df.fit_name = 'Nightmare - WC-EN - DPS Nightmare v1.3'
)

SELECT 
    row_type AS "Type",
    name AS "Name",
    qty AS "Qty",
    jita_buy_each AS "Jita Buy (Each)",
    jita_sell_each AS "Jita Sell (Each)",
    jita_buy_total AS "Jita Buy (Total)",
    jita_sell_total AS "Jita Sell (Total)",
    bwf_sell_each AS "BWF Sell (Each)",
    bwf_sell_total AS "BWF Sell (Total)",
    status AS "Status"
FROM combined_results
ORDER BY 
    CASE 
        WHEN row_type = 'TOTAL' THEN 2
        WHEN row_type = 'CALC' THEN 3
        ELSE 1 
    END,
    sort_value DESC;