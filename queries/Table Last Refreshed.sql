WITH table_updates AS (
    SELECT 
        'market_orders' AS table_name,
        'Market Data' AS category,
        MAX(julianday(last_updated)) AS last_update,
        COUNT(*) AS row_count
    FROM market_orders
    
    UNION ALL
    
    SELECT 
        'market_history',
        'Market Data',
        MAX(julianday(date)),
        COUNT(*)
    FROM market_history
    
    UNION ALL

    SELECT
        'market_price_snapshots',
        'Market Data',
        MAX(julianday(timestamp)),
        COUNT(*)
    FROM market_price_snapshots

    UNION ALL

    SELECT
        'wallet_transactions',
        'Wallet Data',
        MAX(julianday(last_updated)),
        COUNT(*)
    FROM wallet_transactions
    
    UNION ALL
    
    SELECT 
        'wallet_journal',
        'Wallet Data',
        MAX(julianday(date)),
        COUNT(*)
    FROM wallet_journal
    
    UNION ALL
    
    SELECT 
        'character_orders',
        'Character Data',
        MAX(julianday(last_updated)),
        COUNT(*)
    FROM character_orders
    
    UNION ALL
    
    SELECT 
        'character_orders_history',
        'Character Data',
        MAX(julianday(DATETIME(snapshot_date,'-5'))),
        COUNT(*)
    FROM character_orders_history
    
    UNION ALL
    
    SELECT 
        'inv_types',
        'Static Data (SDE)',
        NULL,
        COUNT(*)
    FROM inv_types
    
    UNION ALL
    
    SELECT 
        'inv_groups',
        'Static Data (SDE)',
        NULL,
        COUNT(*)
    FROM inv_groups
    
    UNION ALL
    
    SELECT 
        'inv_categories',
        'Static Data (SDE)',
        NULL,
        COUNT(*)
    FROM inv_categories
    
    UNION ALL
    
    SELECT 
        'inv_market_groups',
        'Static Data (SDE)',
        NULL,
        COUNT(*)
    FROM inv_market_groups
)
SELECT 
    category,
    table_name,
    
    CASE 
        WHEN last_update IS NULL THEN 'N/A (Static Data)'
        ELSE datetime(last_update, '-5 hours')
    END AS last_updated_est,
    
    CASE 
        WHEN last_update IS NULL THEN 'Static'
        WHEN last_update >= julianday('now') - (1.0/24.0) THEN '🟢 Fresh (< 1 hour)'
        WHEN last_update >= julianday('now') - 1 THEN '🟡 Recent (< 1 day)'
        WHEN last_update >= julianday('now') - 7 THEN '🟠 Old (< 1 week)'
        ELSE '🔴 Very Old (> 1 week)'
    END AS status,
    
    printf('%,d', row_count) AS rows,
    
    CASE 
        WHEN last_update IS NULL THEN 'Static'
        -- under 60 minutes
        WHEN (julianday('now') - last_update) * 1440 < 60 THEN ROUND((julianday('now') - last_update) * 1440, 0) || ' minute(s) ago'
        -- under 24 hours
        WHEN (julianday('now') - last_update) * 24 < 24 THEN ROUND((julianday('now') - last_update) * 24, 2) || ' hour(s) ago'
        -- otherwise show days
        ELSE ROUND(julianday('now') - last_update, 1) || ' day(s) ago'
    END AS age
    
FROM table_updates
ORDER BY 
    CASE category
        WHEN 'Market Data' THEN 1
        WHEN 'Wallet Data' THEN 2
        WHEN 'Character Data' THEN 3
        WHEN 'Static Data (SDE)' THEN 4
        ELSE 5
    END,
    table_name
