-- ============================================
-- SIMPLE FIT ITEM LIST
-- ============================================
-- Quick list of items per fit for cross-checking
-- ============================================

SELECT 
    df.fit_name AS "Fit",
    it.type_name AS "Item",
    dfi.quantity AS "Qty",
    printf('%,.2f', COALESCE(jita.best_buy_price, 0)) AS "Jita Buy",
    printf('%,.2f', COALESCE(jita.best_sell_price, 0)) AS "Jita Sell",
    printf('%,.2f', dfi.quantity * COALESCE(jita.best_buy_price, 0)) AS "Buy Total",
    printf('%,.2f', dfi.quantity * COALESCE(jita.best_sell_price, 0)) AS "Sell Total",
    
    -- Quick status
    CASE 
        WHEN bwf.lowest_sell_price IS NOT NULL THEN '✓ BWF'
        ELSE '✗ Missing'
    END AS "BWF?"

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

-- ============================================
-- FILTER BY FIT NAME (edit this line)
-- ============================================
WHERE df.fit_name = 'Zealot - WC Zealot'

ORDER BY dfi.quantity * COALESCE(jita.best_buy_price, 0) DESC;