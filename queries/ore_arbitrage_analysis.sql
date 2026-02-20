-- ============================================================
-- ORE ARBITRAGE ANALYSIS - 7-DAY AVERAGE MINERAL PRICES
-- ============================================================
-- Uses 7-day average mineral prices for stability
-- Uses spot ore prices for actual purchase decisions
-- Includes reprocessing efficiency and collateral fees
-- Includes volatility indicators and confidence scores
-- ============================================================

-- ============================================================
-- CONFIGURABLE PARAMETERS (EDIT THESE)
-- ============================================================
WITH config AS (
    SELECT
        -- REPROCESSING EFFICIENCY
        0.906 as reprocessing_efficiency,  -- 90.6% for compressed ore at Tatara
        
        -- MINERAL SELLING RATE
        0.97 as mineral_sell_pct_of_jbv,  -- Sell minerals at 97% of Jita Buy Value
        
        -- FREIGHT & COLLATERAL COSTS
        125.0 as freight_cost_per_m3,
        0.01 as collateral_fee_pct,        -- 1% of Jita Split for freighter pilot
        
        -- TRADING FEES
        0.00 as broker_fee_pct,
        0.00 as buy_order_multiplier,
        0.00 as sell_order_multiplier,
        
        -- VOLATILITY THRESHOLDS
        0.05 as low_volatility_pct,      -- <5% = stable
        0.15 as high_volatility_pct      -- >15% = volatile
),

-- ============================================================
-- 7-DAY AVERAGE MINERAL PRICES
-- ============================================================
mineral_prices_7day AS (
    SELECT
        'Tritanium' as mineral_name,
        34 as type_id,
        AVG(average) as avg_price_7d,
        MIN(average) as min_price_7d,
        MAX(average) as max_price_7d,
        COUNT(*) as data_points,
        (MAX(average) - MIN(average)) / AVG(average) as volatility_pct
    FROM market_history
    WHERE type_id = 34  -- Tritanium
    AND region_id = 10000002
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    SELECT
        'Pyerite' as mineral_name,
        35 as type_id,
        AVG(average) as avg_price_7d,
        MIN(average) as min_price_7d,
        MAX(average) as max_price_7d,
        COUNT(*) as data_points,
        (MAX(average) - MIN(average)) / AVG(average) as volatility_pct
    FROM market_history
    WHERE type_id = 35  -- Pyerite
    AND region_id = 10000002
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    SELECT
        'Mexallon' as mineral_name,
        36 as type_id,
        AVG(average) as avg_price_7d,
        MIN(average) as min_price_7d,
        MAX(average) as max_price_7d,
        COUNT(*) as data_points,
        (MAX(average) - MIN(average)) / AVG(average) as volatility_pct
    FROM market_history
    WHERE type_id = 36  -- Mexallon
    AND region_id = 10000002
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    SELECT
        'Isogen' as mineral_name,
        37 as type_id,
        AVG(average) as avg_price_7d,
        MIN(average) as min_price_7d,
        MAX(average) as max_price_7d,
        COUNT(*) as data_points,
        (MAX(average) - MIN(average)) / AVG(average) as volatility_pct
    FROM market_history
    WHERE type_id = 37  -- Isogen
    AND region_id = 10000002
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    SELECT
        'Nocxium' as mineral_name,
        38 as type_id,
        AVG(average) as avg_price_7d,
        MIN(average) as min_price_7d,
        MAX(average) as max_price_7d,
        COUNT(*) as data_points,
        (MAX(average) - MIN(average)) / AVG(average) as volatility_pct
    FROM market_history
    WHERE type_id = 38  -- Nocxium
    AND region_id = 10000002
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    SELECT
        'Zydrine' as mineral_name,
        39 as type_id,
        AVG(average) as avg_price_7d,
        MIN(average) as min_price_7d,
        MAX(average) as max_price_7d,
        COUNT(*) as data_points,
        (MAX(average) - MIN(average)) / AVG(average) as volatility_pct
    FROM market_history
    WHERE type_id = 39  -- Zydrine
    AND region_id = 10000002
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    SELECT
        'Megacyte' as mineral_name,
        40 as type_id,
        AVG(average) as avg_price_7d,
        MIN(average) as min_price_7d,
        MAX(average) as max_price_7d,
        COUNT(*) as data_points,
        (MAX(average) - MIN(average)) / AVG(average) as volatility_pct
    FROM market_history
    WHERE type_id = 40  -- Megacyte
    AND region_id = 10000002
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    SELECT
        'Morphite' as mineral_name,
        11399 as type_id,
        AVG(average) as avg_price_7d,
        MIN(average) as min_price_7d,
        MAX(average) as max_price_7d,
        COUNT(*) as data_points,
        (MAX(average) - MIN(average)) / AVG(average) as volatility_pct
    FROM market_history
    WHERE type_id = 11399  -- Morphite
    AND region_id = 10000002
    AND date >= date('now', '-7 days')
),

-- ============================================================
-- EXTRACT MINERAL PRICES INTO VARIABLES
-- ============================================================
mineral_averages AS (
    SELECT
        MAX(CASE WHEN mineral_name = 'Tritanium' THEN avg_price_7d END) as trit_avg,
        MAX(CASE WHEN mineral_name = 'Pyerite' THEN avg_price_7d END) as pye_avg,
        MAX(CASE WHEN mineral_name = 'Mexallon' THEN avg_price_7d END) as mex_avg,
        MAX(CASE WHEN mineral_name = 'Isogen' THEN avg_price_7d END) as iso_avg,
        MAX(CASE WHEN mineral_name = 'Nocxium' THEN avg_price_7d END) as noc_avg,
        MAX(CASE WHEN mineral_name = 'Zydrine' THEN avg_price_7d END) as zyd_avg,
        MAX(CASE WHEN mineral_name = 'Megacyte' THEN avg_price_7d END) as mega_avg,
        MAX(CASE WHEN mineral_name = 'Morphite' THEN avg_price_7d END) as morph_avg,
        
        -- Volatility scores
        MAX(CASE WHEN mineral_name = 'Tritanium' THEN volatility_pct END) as trit_vol,
        MAX(CASE WHEN mineral_name = 'Pyerite' THEN volatility_pct END) as pye_vol,
        MAX(CASE WHEN mineral_name = 'Mexallon' THEN volatility_pct END) as mex_vol,
        MAX(CASE WHEN mineral_name = 'Isogen' THEN volatility_pct END) as iso_vol,
        MAX(CASE WHEN mineral_name = 'Nocxium' THEN volatility_pct END) as noc_vol,
        MAX(CASE WHEN mineral_name = 'Zydrine' THEN volatility_pct END) as zyd_vol,
        MAX(CASE WHEN mineral_name = 'Megacyte' THEN volatility_pct END) as mega_vol,
        MAX(CASE WHEN mineral_name = 'Morphite' THEN volatility_pct END) as morph_vol
    FROM mineral_prices_7day
),

-- ============================================================
-- ORE DATA WITH LIVE PRICES
-- ============================================================
ore_data AS (
    SELECT
        ore_type_id,
        ore_name,
        ore_category,
        tritanium_yield,
        pyerite_yield,
        mexallon_yield,
        isogen_yield,
        nocxium_yield,
        zydrine_yield,
        megacyte_yield,
        morphite_yield,
        volume_m3,
        best_buy_price,
        best_sell_price,
        updated_at
    FROM v_ore_arbitrage_live
),

-- ============================================================
-- CALCULATIONS USING 7-DAY AVERAGES + REPROCESSING EFFICIENCY
-- ============================================================
calculations AS (
    SELECT
        od.*,
        c.*,
        ma.*,
        
        -- Freight cost per ore unit
        (c.freight_cost_per_m3 * od.volume_m3) as freight_per_unit,
        
        -- Jita Split (average of buy and sell)
        ((od.best_buy_price + od.best_sell_price) / 2.0) as jita_split,
        
        -- Collateral fee (1% of Jita Split)
        ((od.best_buy_price + od.best_sell_price) / 2.0 * c.collateral_fee_pct) as collateral_fee,
        
        -- Theoretical mineral value using 7-DAY AVERAGE prices WITH REPROCESSING EFFICIENCY AND SELL RATE
        (
            (od.tritanium_yield * c.reprocessing_efficiency * ma.trit_avg * c.mineral_sell_pct_of_jbv) +
            (od.pyerite_yield * c.reprocessing_efficiency * ma.pye_avg * c.mineral_sell_pct_of_jbv) +
            (od.mexallon_yield * c.reprocessing_efficiency * ma.mex_avg * c.mineral_sell_pct_of_jbv) +
            (od.isogen_yield * c.reprocessing_efficiency * ma.iso_avg * c.mineral_sell_pct_of_jbv) +
            (od.nocxium_yield * c.reprocessing_efficiency * ma.noc_avg * c.mineral_sell_pct_of_jbv) +
            (od.zydrine_yield * c.reprocessing_efficiency * ma.zyd_avg * c.mineral_sell_pct_of_jbv) +
            (od.megacyte_yield * c.reprocessing_efficiency * ma.mega_avg * c.mineral_sell_pct_of_jbv) +
            (od.morphite_yield * c.reprocessing_efficiency * ma.morph_avg * c.mineral_sell_pct_of_jbv)
        ) as theoretical_mineral_value_7d,
        
        -- TOTAL COSTS = Ore Price + Freight + Collateral
        (od.best_buy_price * (1 + c.buy_order_multiplier)) + 
        (c.freight_cost_per_m3 * od.volume_m3) + 
        ((od.best_buy_price + od.best_sell_price) / 2.0 * c.collateral_fee_pct) as total_cost_buy_order,
        
        (od.best_sell_price * (1 + c.sell_order_multiplier)) + 
        (c.freight_cost_per_m3 * od.volume_m3) + 
        ((od.best_buy_price + od.best_sell_price) / 2.0 * c.collateral_fee_pct) as total_cost_sell_order,
        
        -- Breakeven prices (subtract freight + collateral from mineral value at 97% JBV)
        (
            (
                (od.tritanium_yield * c.reprocessing_efficiency * ma.trit_avg * c.mineral_sell_pct_of_jbv) +
                (od.pyerite_yield * c.reprocessing_efficiency * ma.pye_avg * c.mineral_sell_pct_of_jbv) +
                (od.mexallon_yield * c.reprocessing_efficiency * ma.mex_avg * c.mineral_sell_pct_of_jbv) +
                (od.isogen_yield * c.reprocessing_efficiency * ma.iso_avg * c.mineral_sell_pct_of_jbv) +
                (od.nocxium_yield * c.reprocessing_efficiency * ma.noc_avg * c.mineral_sell_pct_of_jbv) +
                (od.zydrine_yield * c.reprocessing_efficiency * ma.zyd_avg * c.mineral_sell_pct_of_jbv) +
                (od.megacyte_yield * c.reprocessing_efficiency * ma.mega_avg * c.mineral_sell_pct_of_jbv) +
                (od.morphite_yield * c.reprocessing_efficiency * ma.morph_avg * c.mineral_sell_pct_of_jbv)
            ) - (c.freight_cost_per_m3 * od.volume_m3) - ((od.best_buy_price + od.best_sell_price) / 2.0 * c.collateral_fee_pct)
        ) / (1 + c.buy_order_multiplier) as max_buy_order_price,
        
        (
            (
                (od.tritanium_yield * c.reprocessing_efficiency * ma.trit_avg * c.mineral_sell_pct_of_jbv) +
                (od.pyerite_yield * c.reprocessing_efficiency * ma.pye_avg * c.mineral_sell_pct_of_jbv) +
                (od.mexallon_yield * c.reprocessing_efficiency * ma.mex_avg * c.mineral_sell_pct_of_jbv) +
                (od.isogen_yield * c.reprocessing_efficiency * ma.iso_avg * c.mineral_sell_pct_of_jbv) +
                (od.nocxium_yield * c.reprocessing_efficiency * ma.noc_avg * c.mineral_sell_pct_of_jbv) +
                (od.zydrine_yield * c.reprocessing_efficiency * ma.zyd_avg * c.mineral_sell_pct_of_jbv) +
                (od.megacyte_yield * c.reprocessing_efficiency * ma.mega_avg * c.mineral_sell_pct_of_jbv) +
                (od.morphite_yield * c.reprocessing_efficiency * ma.morph_avg * c.mineral_sell_pct_of_jbv)
            ) - (c.freight_cost_per_m3 * od.volume_m3) - ((od.best_buy_price + od.best_sell_price) / 2.0 * c.collateral_fee_pct)
        ) / (1 + c.sell_order_multiplier) as max_sell_order_price,
        
        -- Calculate overall volatility score for this ore
        (
            (od.tritanium_yield * COALESCE(ma.trit_vol, 0)) +
            (od.pyerite_yield * COALESCE(ma.pye_vol, 0)) +
            (od.mexallon_yield * COALESCE(ma.mex_vol, 0)) +
            (od.isogen_yield * COALESCE(ma.iso_vol, 0)) +
            (od.nocxium_yield * COALESCE(ma.noc_vol, 0)) +
            (od.zydrine_yield * COALESCE(ma.zyd_vol, 0)) +
            (od.megacyte_yield * COALESCE(ma.mega_vol, 0)) +
            (od.morphite_yield * COALESCE(ma.morph_vol, 0))
        ) / NULLIF(
            od.tritanium_yield + od.pyerite_yield + od.mexallon_yield + 
            od.isogen_yield + od.nocxium_yield + od.zydrine_yield + 
            od.megacyte_yield + od.morphite_yield, 0
        ) as weighted_volatility
        
    FROM ore_data od
    CROSS JOIN config c
    CROSS JOIN mineral_averages ma
    WHERE od.best_buy_price IS NOT NULL
    OR od.best_sell_price IS NOT NULL
),

-- ============================================================
-- PROFIT ANALYSIS
-- ============================================================
profit_analysis AS (
    SELECT
        ore_name,
        ore_category,
        volume_m3,
        updated_at,
        
        -- Pass through config values
        reprocessing_efficiency,
        mineral_sell_pct_of_jbv,
        
        -- Yields (actual after reprocessing efficiency)
        ROUND(tritanium_yield * reprocessing_efficiency, 2) as actual_trit,
        ROUND(pyerite_yield * reprocessing_efficiency, 2) as actual_pye,
        ROUND(mexallon_yield * reprocessing_efficiency, 2) as actual_mex,
        ROUND(isogen_yield * reprocessing_efficiency, 2) as actual_iso,
        ROUND(nocxium_yield * reprocessing_efficiency, 2) as actual_noc,
        ROUND(zydrine_yield * reprocessing_efficiency, 2) as actual_zyd,
        ROUND(megacyte_yield * reprocessing_efficiency, 2) as actual_mega,
        ROUND(morphite_yield * reprocessing_efficiency, 2) as actual_morph,
        
        -- Efficiency used
        ROUND(reprocessing_efficiency * 100, 1) as efficiency_pct,
        
        -- Current SPOT ore prices
        best_buy_price,
        best_sell_price,
        
        -- Cost breakdown
        freight_per_unit,
        collateral_fee,
        
        -- Theoretical value (7-DAY AVERAGE with efficiency applied)
        theoretical_mineral_value_7d,
        
        -- Actual total costs (ore + freight + collateral)
        total_cost_buy_order,
        total_cost_sell_order,
        
        -- Breakeven thresholds
        max_buy_order_price,
        max_sell_order_price,
        
        -- Profitability vs theoretical value
        ROUND((best_buy_price / theoretical_mineral_value_7d * 100), 1) as buy_price_pct_of_theoretical,
        ROUND((best_sell_price / theoretical_mineral_value_7d * 100), 1) as sell_price_pct_of_theoretical,
        
        -- Profit per unit (mineral value - total costs)
        theoretical_mineral_value_7d - total_cost_buy_order as profit_per_unit_buy,
        theoretical_mineral_value_7d - total_cost_sell_order as profit_per_unit_sell,
        
        -- Savings percentage
        ROUND(((theoretical_mineral_value_7d - total_cost_buy_order) / theoretical_mineral_value_7d * 100), 2) as savings_pct_buy,
        ROUND(((theoretical_mineral_value_7d - total_cost_sell_order) / theoretical_mineral_value_7d * 100), 2) as savings_pct_sell,
        
        -- Volatility indicator
        ROUND(weighted_volatility * 100, 2) as volatility_pct,
        CASE
            WHEN weighted_volatility < low_volatility_pct THEN 'Low'
            WHEN weighted_volatility < high_volatility_pct THEN 'Medium'
            ELSE 'High'
        END as volatility_rating,
        
        -- Confidence score (lower volatility = higher confidence)
        ROUND((1 - MIN(weighted_volatility, 0.25)) * 100, 0) as confidence_score,
        
        -- Profitability flags
        CASE 
            WHEN best_buy_price <= max_buy_order_price THEN '✓ PROFITABLE'
            ELSE '✗ TOO EXPENSIVE'
        END as buy_order_status,
        
        CASE 
            WHEN best_sell_price <= max_sell_order_price THEN '✓ PROFITABLE'
            ELSE '✗ TOO EXPENSIVE'
        END as sell_order_status,
        
        -- Primary mineral
        CASE
            WHEN morphite_yield > 0 THEN 'Morphite'
            WHEN megacyte_yield > 0 THEN 'Megacyte'
            WHEN zydrine_yield > 0.05 THEN 'Zydrine-Rich'
            WHEN nocxium_yield > 0.05 THEN 'Nocxium-Rich'
            WHEN tritanium_yield > 2.0 THEN 'Tritanium-Rich'
            WHEN pyerite_yield > 0.5 THEN 'Pyerite-Rich'
            WHEN mexallon_yield > 0.1 THEN 'Mexallon-Rich'
            WHEN isogen_yield > 0.05 THEN 'Isogen-Rich'
            WHEN tritanium_yield > 0 AND pyerite_yield > 0 THEN 'Mixed'
            ELSE 'Other'
        END as mineral_type,
        
        -- Compressed vs Uncompressed
        CASE
            WHEN ore_name LIKE 'Compressed%' THEN 'Compressed'
            ELSE 'Uncompressed'
        END as compression_status
        
    FROM calculations
)

-- ============================================================
-- FINAL OUTPUT
-- ============================================================
SELECT
    -- ore_category as category,
    ore_name as ore,
    compression_status as type,
    mineral_type,
    efficiency_pct as eff_pct,
    ROUND(mineral_sell_pct_of_jbv * 100, 0) as sell_pct,
    
    -- Data freshness
    -- SUBSTR(updated_at, 12, 5) as time_updated,
    
    -- Volume and costs
    ROUND(volume_m3, 3) as vol_m3,
    ROUND(freight_per_unit, 2) as freight,
    ROUND(collateral_fee, 2) as collat,
    
    -- Yields (AFTER efficiency applied)
    actual_trit as trit,
    actual_pye as pye,
    actual_mex as mex,
    actual_iso as iso,
    actual_noc as noc,
    actual_zyd as zyd,
    actual_mega as mega,
    actual_morph as morph,
    
    -- Current SPOT ore prices
    ROUND(best_buy_price, 2) as spot_buy,
    ROUND(best_sell_price, 2) as spot_sell,
    
    -- Theoretical value (7-DAY AVG minerals × efficiency)
    ROUND(theoretical_mineral_value_7d, 2) as theory_7d,
    
    -- Price as % of theoretical
    buy_price_pct_of_theoretical as buy_pct,
    sell_price_pct_of_theoretical as sell_pct,
    
    -- Breakeven prices
    ROUND(max_buy_order_price, 2) as max_buy,
    ROUND(max_sell_order_price, 2) as max_sell,
    
    -- Profitability
    buy_order_status as buy_status,
    sell_order_status as sell_status,
    
    -- Profit (mineral value - ore cost - freight - collateral)
    ROUND(profit_per_unit_buy, 2) as profit_buy,
    ROUND(profit_per_unit_sell, 2) as profit_sell,
    savings_pct_buy as save_buy,
    savings_pct_sell as save_sell,
    
    -- Volatility & Confidence
    volatility_pct as vol_pct,
    volatility_rating as volatility,
    confidence_score as confidence

FROM profit_analysis

WHERE 
    -- Show all ores (comment out to see everything)
    1=1
    
    -- Filter options (uncomment as needed):
    AND (buy_order_status = '✓ PROFITABLE' OR sell_order_status = '✓ PROFITABLE')
    --AND compression_status = 'Compressed'
    -- AND mineral_type IN ('Tritanium-Rich', 'Pyerite-Rich')
    -- AND volatility_rating IN ('Low', 'Medium')  -- Exclude high volatility
    -- AND confidence_score >= 80  -- Only high-confidence opportunities

ORDER BY
    savings_pct_sell DESC,
    ore_category,
    ore_name

-- ============================================================
-- CHANGES FROM PREVIOUS VERSION:
-- ============================================================
-- ✅ ADDED: reprocessing_efficiency parameter (0.906 = 90.6%)
-- ✅ ADDED: mineral_sell_pct_of_jbv parameter (0.97 = 97% JBV)
-- ✅ ADDED: collateral_fee_pct parameter (0.01 = 1%)
-- ✅ ADDED: collateral_fee calculation (1% of Jita Split)
-- ✅ UPDATED: All mineral value calculations now multiply by efficiency AND sell rate
-- ✅ UPDATED: Total costs now include ore + freight + collateral
-- ✅ UPDATED: Breakeven prices subtract freight + collateral and use 97% JBV
-- ✅ ADDED: Actual yields shown in output (after efficiency applied)
-- ✅ ADDED: Efficiency % shown in output (90.6%)
-- ✅ ADDED: Sell % shown in output (97% of JBV)
-- ✅ ADDED: Collateral fee shown in output
-- 
-- FORMULA NOW:
-- Revenue = yields × efficiency × 7-day_avg_JBV × sell_rate
-- Costs = ore_price + freight + collateral
-- Profit = Revenue - Costs
-- ============================================================