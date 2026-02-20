-- ============================================
-- IMPROVED TRADING ANALYSIS QUERIES
-- ============================================
-- Uses both character_orders_history (snapshots)
-- and wallet_transactions (actual fills)
-- ============================================

-- ============================================
-- QUERY 1: ORDER FILL TIME ANALYSIS
-- ============================================
-- How long do buy orders take to fill?
-- Uses snapshot history to track order lifecycle

WITH order_lifecycle AS (
    SELECT
        order_id,
        type_id,
        MIN(snapshot_date) as first_seen,
        MAX(snapshot_date) as last_seen,
        MIN(CASE WHEN state = 'active' THEN snapshot_date END) as became_active,
        MAX(CASE WHEN volume_remain > 0 THEN snapshot_date END) as last_active,
        MAX(CASE WHEN volume_remain = 0 THEN snapshot_date END) as filled_date,
        MAX(volume_total) as total_volume,
        MIN(volume_remain) as min_remain,
        MAX(price) as price
    FROM character_orders_history
    WHERE character_id = 2114278577
    AND is_buy_order = 1
    AND issued >= date('now', '-60 days')
    GROUP BY order_id, type_id
    HAVING filled_date IS NOT NULL  -- Only filled orders
),
fill_times AS (
    SELECT
        ol.type_id,
        it.type_name,
        ol.order_id,
        ol.price,
        ol.total_volume,
        ol.first_seen,
        ol.filled_date,
        -- Time to fill
        ROUND((JULIANDAY(ol.filled_date) - JULIANDAY(ol.first_seen)) * 24, 1) as hours_to_fill,
        ROUND((JULIANDAY(ol.filled_date) - JULIANDAY(ol.first_seen)), 1) as days_to_fill
    FROM order_lifecycle ol
    JOIN inv_types it ON it.type_id = ol.type_id
    WHERE ol.filled_date IS NOT NULL
)
SELECT
    type_name,
    COUNT(DISTINCT order_id) as orders_filled,
    ROUND(AVG(hours_to_fill), 1) as avg_hours_to_fill,
    ROUND(MIN(hours_to_fill), 1) as fastest_fill,
    ROUND(MAX(hours_to_fill), 1) as slowest_fill,
    ROUND(AVG(days_to_fill), 2) as avg_days_to_fill,
    -- Percentage that fill quickly
    ROUND(SUM(CASE WHEN hours_to_fill <= 24 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pct_fill_under_24h,
    ROUND(SUM(CASE WHEN hours_to_fill <= 72 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pct_fill_under_3days,
    ROUND(AVG(price), 0) as avg_buy_price,
    SUM(total_volume) as total_units_bought,
    MAX(filled_date) as last_order_filled
FROM fill_times
GROUP BY type_name
HAVING orders_filled >= 3  -- At least 3 orders
ORDER BY avg_hours_to_fill ASC
LIMIT 30;


-- ============================================
-- QUERY 2: ACTUAL TRADE COUNT (FIXED)
-- ============================================
-- Count distinct ORDERS, not individual transactions
-- Fixes the "times traded" overcounting issue

WITH sell_orders AS (
    SELECT
        order_id,
        type_id,
        MIN(snapshot_date) as order_placed,
        MAX(CASE WHEN volume_remain = 0 THEN snapshot_date END) as order_completed,
        MAX(volume_total) as total_volume,
        MAX(price) as sell_price
    FROM character_orders_history
    WHERE character_id = 2114278577
    AND is_buy_order = 0
    AND issued >= date('now', '-30 days')
    GROUP BY order_id, type_id
    HAVING order_completed IS NOT NULL  -- Only completed orders
),
buy_orders AS (
    SELECT
        order_id,
        type_id,
        MIN(snapshot_date) as order_placed,
        MAX(CASE WHEN volume_remain = 0 THEN snapshot_date END) as order_completed,
        MAX(volume_total) as total_volume,
        MAX(price) as buy_price
    FROM character_orders_history
    WHERE character_id = 2114278577
    AND is_buy_order = 1
    AND issued >= date('now', '-30 days')
    GROUP BY order_id, type_id
    HAVING order_completed IS NOT NULL
)
SELECT
    it.type_name,
    COUNT(DISTINCT so.order_id) as sell_orders_completed,
    COUNT(DISTINCT bo.order_id) as buy_orders_completed,
    SUM(so.total_volume) as total_units_sold,
    SUM(bo.total_volume) as total_units_bought,
    ROUND(AVG(so.sell_price), 0) as avg_sell_price,
    ROUND(AVG(bo.buy_price), 0) as avg_buy_price,
    ROUND(AVG(so.sell_price) - AVG(bo.buy_price), 0) as avg_spread,
    ROUND((AVG(so.sell_price) - AVG(bo.buy_price)) / AVG(bo.buy_price) * 100, 2) as avg_margin_pct
FROM sell_orders so
JOIN buy_orders bo ON bo.type_id = so.type_id
JOIN inv_types it ON it.type_id = so.type_id
GROUP BY it.type_name
ORDER BY sell_orders_completed DESC;


-- ============================================
-- QUERY 3: ORDER SUCCESS RATE
-- ============================================
-- What % of your orders actually fill?

WITH all_orders AS (
    SELECT
        order_id,
        type_id,
        is_buy_order,
        MAX(volume_total) as volume_total,
        MIN(volume_remain) as final_volume_remain,
        MAX(CASE WHEN volume_remain = 0 THEN 1 ELSE 0 END) as filled_completely,
        MAX(CASE WHEN state = 'cancelled' THEN 1 ELSE 0 END) as was_cancelled,
        MIN(snapshot_date) as first_seen,
        MAX(snapshot_date) as last_seen
    FROM character_orders_history
    WHERE character_id = 2114278577
    AND issued >= date('now', '-30 days')
    GROUP BY order_id, type_id, is_buy_order
)
SELECT
    it.type_name,
    CASE WHEN ao.is_buy_order = 1 THEN 'Buy' ELSE 'Sell' END as order_type,
    COUNT(*) as total_orders,
    SUM(filled_completely) as filled_completely,
    SUM(was_cancelled) as cancelled,
    COUNT(*) - SUM(filled_completely) - SUM(was_cancelled) as still_active,
    ROUND(SUM(filled_completely) * 100.0 / COUNT(*), 1) as fill_rate_pct,
    ROUND(SUM(was_cancelled) * 100.0 / COUNT(*), 1) as cancel_rate_pct
FROM all_orders ao
JOIN inv_types it ON it.type_id = ao.type_id
GROUP BY it.type_name, ao.is_buy_order
HAVING total_orders >= 3
ORDER BY fill_rate_pct DESC;


-- ============================================
-- QUERY 4: INVENTORY HOLDING TIME
-- ============================================
-- Time between buy completing and sell starting

WITH buy_completed AS (
    SELECT
        type_id,
        order_id,
        MAX(CASE WHEN volume_remain = 0 THEN snapshot_date END) as buy_filled_date,
        MAX(volume_total) as units_bought
    FROM character_orders_history
    WHERE character_id = 2114278577
    AND is_buy_order = 1
    GROUP BY order_id, type_id
    HAVING buy_filled_date IS NOT NULL
),
sell_started AS (
    SELECT
        type_id,
        order_id,
        MIN(snapshot_date) as sell_placed_date,
        MAX(volume_total) as units_selling
    FROM character_orders_history
    WHERE character_id = 2114278577
    AND is_buy_order = 0
    GROUP BY order_id, type_id
),
holding_times AS (
    SELECT
        bc.type_id,
        bc.buy_filled_date,
        ss.sell_placed_date,
        ROUND((JULIANDAY(ss.sell_placed_date) - JULIANDAY(bc.buy_filled_date)) * 24, 1) as hours_holding
    FROM buy_completed bc
    JOIN sell_started ss ON ss.type_id = bc.type_id
        AND ss.sell_placed_date >= bc.buy_filled_date
        -- Match sell to most recent buy before it
        AND ss.sell_placed_date = (
            SELECT MIN(ss2.sell_placed_date)
            FROM sell_started ss2
            WHERE ss2.type_id = bc.type_id
            AND ss2.sell_placed_date >= bc.buy_filled_date
        )
)
SELECT
    it.type_name,
    COUNT(*) as cycles,
    ROUND(AVG(hours_holding), 1) as avg_hours_holding,
    ROUND(MIN(hours_holding), 1) as fastest_relist,
    ROUND(MAX(hours_holding), 1) as slowest_relist,
    ROUND(AVG(hours_holding) / 24, 2) as avg_days_holding
FROM holding_times ht
JOIN inv_types it ON it.type_id = ht.type_id
WHERE hours_holding >= 0  -- Sanity check
GROUP BY it.type_name
HAVING cycles >= 2
ORDER BY avg_hours_holding ASC;


-- ============================================
-- QUERY 5: ACTIVE ORDER SNAPSHOT
-- ============================================
-- What's currently active right now?

WITH latest_snapshot AS (
    SELECT MAX(snapshot_date) as latest_date
    FROM character_orders_history
    WHERE character_id = 2114278577
),
current_orders AS (
    SELECT
        coh.order_id,
        coh.type_id,
        coh.is_buy_order,
        coh.price,
        coh.volume_remain,
        coh.volume_total,
        coh.issued,
        coh.state,
        ROUND((JULIANDAY(ls.latest_date) - JULIANDAY(coh.issued)) * 24, 1) as hours_active
    FROM character_orders_history coh
    CROSS JOIN latest_snapshot ls
    WHERE coh.character_id = 2114278577
    AND coh.snapshot_date = ls.latest_date
    AND coh.volume_remain > 0
    AND coh.state = 'active'
)
SELECT
    it.type_name,
    CASE WHEN co.is_buy_order = 1 THEN 'BUY' ELSE 'SELL' END as order_type,
    co.price,
    co.volume_remain,
    co.volume_total,
    ROUND((co.volume_total - co.volume_remain) * 100.0 / co.volume_total, 1) as pct_filled,
    co.hours_active,
    ROUND(co.hours_active / 24, 1) as days_active,
    co.issued,
    co.order_id
FROM current_orders co
JOIN inv_types it ON it.type_id = co.type_id
ORDER BY co.hours_active DESC;


-- ============================================
-- QUERY 6: BEST ITEMS FOR CORP SOURCING
-- ============================================
-- Items that fill quickly + have good margins
-- Perfect for your sourcing service!

WITH buy_fill_times AS (
    SELECT
        order_id,
        type_id,
        MIN(snapshot_date) as order_placed,
        MAX(CASE WHEN volume_remain = 0 THEN snapshot_date END) as order_filled,
        MAX(price) as buy_price,
        MAX(volume_total) as units
    FROM character_orders_history
    WHERE character_id = 2114278577
    AND is_buy_order = 1
    AND issued >= date('now', '-60 days')
    GROUP BY order_id, type_id
    HAVING order_filled IS NOT NULL
),
fill_stats AS (
    SELECT
        type_id,
        COUNT(*) as orders_filled,
        AVG((JULIANDAY(order_filled) - JULIANDAY(order_placed)) * 24) as avg_hours_to_fill,
        AVG(buy_price) as avg_buy_price,
        SUM(units) as total_units_bought
    FROM buy_fill_times
    GROUP BY type_id
    HAVING orders_filled >= 3
),
current_prices AS (
    SELECT
        type_id,
        MIN(CASE WHEN is_buy_order = 0 THEN price END) as current_sell_price
    FROM market_orders
    WHERE location_id = 60003760  -- Jita
    AND region_id = 10000002
    GROUP BY type_id
)
SELECT
    it.type_name,
    fs.orders_filled,
    ROUND(fs.avg_hours_to_fill, 1) as avg_hours_to_fill,
    ROUND(fs.avg_hours_to_fill / 24, 1) as avg_days_to_fill,
    ROUND(fs.avg_buy_price, 0) as avg_buy_price,
    ROUND(cp.current_sell_price, 0) as current_jita_sell,
    ROUND(cp.current_sell_price - fs.avg_buy_price, 0) as potential_profit_per_unit,
    ROUND((cp.current_sell_price - fs.avg_buy_price) / fs.avg_buy_price * 100, 2) as margin_pct,
    fs.total_units_bought,
    -- Sourcing service estimate
    CASE
        WHEN fs.avg_hours_to_fill <= 48 THEN '2-3 days'
        WHEN fs.avg_hours_to_fill <= 120 THEN '5-7 days'
        ELSE '7+ days'
    END as sourcing_estimate
FROM fill_stats fs
JOIN inv_types it ON it.type_id = fs.type_id
LEFT JOIN current_prices cp ON cp.type_id = fs.type_id
WHERE fs.avg_hours_to_fill <= 168  -- Fills within 7 days
AND cp.current_sell_price IS NOT NULL
ORDER BY margin_pct DESC, avg_hours_to_fill ASC
LIMIT 30;


-- ============================================
-- QUERY 7: ORDER MODIFICATION TRACKING
-- ============================================
-- How often do you change prices?

WITH order_price_changes AS (
    SELECT
        order_id,
        type_id,
        is_buy_order,
        COUNT(DISTINCT price) as price_changes,
        MIN(price) as lowest_price,
        MAX(price) as highest_price,
        MIN(snapshot_date) as first_seen,
        MAX(snapshot_date) as last_seen
    FROM character_orders_history
    WHERE character_id = 2114278577
    AND issued >= date('now', '-30 days')
    GROUP BY order_id, type_id, is_buy_order
)
SELECT
    it.type_name,
    CASE WHEN opc.is_buy_order = 1 THEN 'Buy' ELSE 'Sell' END as order_type,
    COUNT(*) as total_orders,
    ROUND(AVG(opc.price_changes), 1) as avg_price_changes_per_order,
    SUM(CASE WHEN opc.price_changes > 1 THEN 1 ELSE 0 END) as orders_with_changes,
    ROUND(SUM(CASE WHEN opc.price_changes > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pct_modified,
    ROUND(AVG(opc.highest_price - opc.lowest_price), 0) as avg_price_range
FROM order_price_changes opc
JOIN inv_types it ON it.type_id = opc.type_id
GROUP BY it.type_name, opc.is_buy_order
HAVING total_orders >= 3
ORDER BY avg_price_changes_per_order DESC;