-- ============================================
-- DOCTRINE FIT PRICING - DETAILED BREAKDOWN
-- ============================================
-- Compares Jita sourcing vs BWF direct purchase
-- Shows customer savings and all costs
-- ============================================

SELECT 
    df.fit_name AS "Fit Name",
    df.ship_type AS "Ship",
    
    -- ============================================
    -- JITA SOURCING COSTS
    -- ============================================
    
    -- Base Jita buy price (hitting buy orders)
    printf('%,.2f', SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0))) AS "Jita Buy",
    
    -- Jita sell price (what customer would pay if buying from Jita sell orders)
    printf('%,.2f', SUM(dfi.quantity * COALESCE(jita.best_sell_price, 0))) AS "Jita Sell",
    
    -- 1.5% broker fee on Jita purchases
    printf('%,.2f', SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 0.015) AS "Jita Tax",
    
    -- Total cost at Jita (buy price + broker fee)
    printf('%,.2f', SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015) AS "Total Jita Cost",
    
    -- ============================================
    -- FREIGHT COSTS (TEST Freight)
    -- ============================================
    
    -- Freight: (volume × 300 ISK/m³) + (Jita cost × 1% collateral)
    printf('%,.2f',
        -- Volume cost: sum of (quantity × volume × 300)
        SUM(dfi.quantity * COALESCE(it.volume, 0) * 300) +
        -- Collateral: 1% of total Jita cost
        (SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015 * 0.01)
    ) AS "Freight Cost",
    
    -- ============================================
    -- TOTAL SOURCING COST
    -- ============================================
    
    -- Total cost with Jita sourcing service (Jita + tax + freight)
    printf('%,.2f',
        (SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015) +  -- Jita with tax
        (SUM(dfi.quantity * COALESCE(it.volume, 0) * 300) +                -- Freight volume
         (SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015 * 0.01))  -- Collateral
    ) AS "Total Sourcing Cost",
    
    -- ============================================
    -- BWF DIRECT PURCHASE
    -- ============================================
    
    -- BWF sell price (customer buying from market, no tax)
    -- If item not in BWF, use Jita sell price + freight as fallback
    printf('%,.2f', 
        SUM(
            dfi.quantity * 
            COALESCE(
                bwf.lowest_sell_price,  -- Prefer BWF if available
                -- Fallback: Jita sell + individual item freight
                jita.best_sell_price + (it.volume * 300) + (jita.best_sell_price * 0.01)
            )
        )
    ) AS "BWF Sell Price",
    
    -- ============================================
    -- SAVINGS ANALYSIS
    -- ============================================
    
    -- Customer savings (BWF sell price vs Jita sell price - no taxes/freight)
    -- This shows how much they save by using your service vs buying from Jita themselves
    printf('%,.2f',
        SUM(
            dfi.quantity * 
            COALESCE(
                bwf.lowest_sell_price,  -- BWF price if available
                -- Fallback: Jita sell + freight for unavailable items
                jita.best_sell_price + (it.volume * 300) + (jita.best_sell_price * 0.01)
            )
        ) -  -- What they'd pay in BWF
        SUM(dfi.quantity * COALESCE(jita.best_sell_price, 0))  -- What they'd pay in Jita (no tax/freight)
    ) AS "Customer Saves",
    
    -- Savings percentage (vs Jita sell price)
    CASE 
        WHEN SUM(dfi.quantity * COALESCE(jita.best_sell_price, 0)) > 0
        THEN printf('%.2f%%',
            ((SUM(dfi.quantity * COALESCE(bwf.lowest_sell_price, jita.best_sell_price + (it.volume * 300) + (jita.best_sell_price * 0.01))) -
              SUM(dfi.quantity * COALESCE(jita.best_sell_price, 0))) /
             SUM(dfi.quantity * COALESCE(bwf.lowest_sell_price, jita.best_sell_price + (it.volume * 300) + (jita.best_sell_price * 0.01)))) * 100
        )
        ELSE NULL
    END AS "Savings %",
    
    -- ============================================
    -- AVAILABILITY INFO
    -- ============================================
    
    -- Count items not available in BWF
    SUM(CASE WHEN bwf.lowest_sell_price IS NULL THEN 1 ELSE 0 END) AS "Items Missing in BWF",
    
    -- Total unique items
    COUNT(DISTINCT dfi.type_id) AS "Total Items"

FROM doctrine_fits df
JOIN doctrine_fit_items dfi ON dfi.fit_id = df.fit_id
JOIN inv_types it ON it.type_id = dfi.type_id

-- Jita buy prices
LEFT JOIN (
    SELECT 
        type_id,
        MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy_price,
        MIN(CASE WHEN is_buy_order = 0 THEN price END) AS best_sell_price
    FROM market_orders
    GROUP BY type_id
) jita ON jita.type_id = dfi.type_id

-- BWF sell prices (what customer would pay to buy directly)
-- If not available, fallback to Jita sell price + freight
LEFT JOIN (
    SELECT 
        type_id,
        MIN(CASE WHEN is_buy_order = 0 THEN price END) AS lowest_sell_price
    FROM bwf_market_orders
    GROUP BY type_id
) bwf ON bwf.type_id = dfi.type_id

GROUP BY df.fit_id, df.fit_name, df.ship_type
-- ORDER BY SUM(dfi.quantity * COALESCE(jita.best_buy_price, 0)) * 1.015 DESC;
ORDER BY (SUM(dfi.quantity * COALESCE(bwf.lowest_sell_price, jita.best_sell_price + (it.volume * 300) + (jita.best_sell_price * 0.01))) -
              SUM(dfi.quantity * COALESCE(jita.best_sell_price, 0))) /
             SUM(dfi.quantity * COALESCE(bwf.lowest_sell_price, jita.best_sell_price + (it.volume * 300) + (jita.best_sell_price * 0.01))) * 100 DESC;