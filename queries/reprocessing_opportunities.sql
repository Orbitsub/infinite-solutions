-- ============================================================================
-- ITEM REPROCESSING ARBITRAGE ANALYSIS
-- ============================================================================
-- 
-- PURPOSE:
--   Find profitable opportunities to buy items in Jita, ship to null-sec,
--   reprocess at corp Tatara, and sell minerals at 97% JBV to corp members.
--
-- BUSINESS MODEL:
--   1. Buy items from Jita sell orders (instant purchase)
--   2. Ship to null-sec (400 ISK/m³)
--   3. Pay freighter pilot (1% of Jita Split value)
--   4. Reprocess at Tatara (65.5% efficiency)
--   5. Sell minerals at 97% of Jita Buy Value (JBV)
--
-- INTEGRATIONS:
--   - Complements existing Ore Arbitrage system
--   - Feeds into Mineral Market service (97% JBV pricing)
--   - Uses same freight infrastructure
--
-- AUTHOR: Hamektok Hakaari
-- CREATED: January 27, 2026
-- ============================================================================


-- ============================================================================
-- CONFIGURATION SECTION
-- ============================================================================
-- Edit these values to match your situation and preferences
-- ============================================================================

WITH config AS (
    SELECT
        -- ----------------------------------------------------------------
        -- REPROCESSING EFFICIENCY SETTINGS
        -- ----------------------------------------------------------------
        -- Your total efficiency = base × (1 + all bonuses)
        -- Example: 50% × (1 + 0.15 + 0.10 + 0.00 + 0.06) = 65.5%
        -- ----------------------------------------------------------------
        0.50 as base_yield,                    -- Always 50% (game mechanics)
        0.15 as reprocessing_skill_bonus,      -- Reprocessing V = 15% (3% per level)
        0.10 as efficiency_skill_bonus,        -- Reprocessing Efficiency V = 10% (2% per level)
        0.04 as implant_bonus,                 -- RX-804 implant = 4% (if you have it)
        0.06 as structure_bonus,               -- Corp Tatara bonus (VERIFY WITH CORPMATE!)
        
        -- ----------------------------------------------------------------
        -- COST SETTINGS
        -- ----------------------------------------------------------------
        125.0 as freight_per_m3,               -- ISK per m³ to ship from Jita to null-sec
        0.01 as freighter_collateral_pct,     -- 1% of Jita Split value for freighter pilot reward
        0.0 as broker_fee_pct,               -- 1.5% broker fee (not used for instant buys)
        0.0 as sales_tax_pct,                 -- 1% sales tax (not used when selling to corp)
        
        -- ----------------------------------------------------------------
        -- MINERAL PRICING STRATEGY
        -- ----------------------------------------------------------------
        0.97 as mineral_sell_pct_of_jbv,      -- Sell minerals at 97% of Jita Buy Value
                                               -- (Your Mineral Market service pricing)
        
        -- ----------------------------------------------------------------
        -- FILTERS - ADJUST TO SHOW MORE/FEWER RESULTS
        -- ----------------------------------------------------------------
        0.05 as min_spread_pct,                -- Exclude fat-finger orders (spread < 5%)
        5.0 as min_profit_margin_pct,          -- Minimum 5% profit margin to show
        10000.0 as min_profit_per_unit,        -- Minimum 10,000 ISK profit per unit
        10000.0 as max_volume_m3,              -- Skip items larger than 10,000 m³
        
        -- ----------------------------------------------------------------
        -- REGION/STATION IDS
        -- ----------------------------------------------------------------
        10000002 as jita_region_id,            -- The Forge (Jita region)
        60003760 as jita_station_id            -- Jita IV - Moon 4 - Caldari Navy Assembly Plant
),


-- ============================================================================
-- REPROCESSING EFFICIENCY CALCULATION
-- ============================================================================
-- Calculate your total reprocessing efficiency based on skills and bonuses
-- ============================================================================

efficiency AS (
    SELECT 
        base_yield * (1 + 
                      reprocessing_skill_bonus + 
                      efficiency_skill_bonus +
                      implant_bonus +
                      structure_bonus) as total_efficiency
    FROM config
),


-- ============================================================================
-- MINERAL PRICING - 7-DAY AVERAGES (FOR REFERENCE)
-- ============================================================================
-- These are used for context/comparison, not actual profit calculations
-- ============================================================================

mineral_prices_7day AS (
    -- Tritanium (34)
    SELECT 34 as type_id, 'Tritanium' as mineral_name, AVG(average) as avg_price_7d
    FROM market_history 
    WHERE type_id = 34 
    AND region_id = 10000002 
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    -- Pyerite (35)
    SELECT 35, 'Pyerite', AVG(average)
    FROM market_history 
    WHERE type_id = 35 
    AND region_id = 10000002 
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    -- Mexallon (36)
    SELECT 36, 'Mexallon', AVG(average)
    FROM market_history 
    WHERE type_id = 36 
    AND region_id = 10000002 
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    -- Isogen (37)
    SELECT 37, 'Isogen', AVG(average)
    FROM market_history 
    WHERE type_id = 37 
    AND region_id = 10000002 
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    -- Nocxium (38)
    SELECT 38, 'Nocxium', AVG(average)
    FROM market_history 
    WHERE type_id = 38 
    AND region_id = 10000002 
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    -- Zydrine (39)
    SELECT 39, 'Zydrine', AVG(average)
    FROM market_history 
    WHERE type_id = 39 
    AND region_id = 10000002 
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    -- Megacyte (40)
    SELECT 40, 'Megacyte', AVG(average)
    FROM market_history 
    WHERE type_id = 40 
    AND region_id = 10000002 
    AND date >= date('now', '-7 days')
    
    UNION ALL
    
    -- Morphite (11399)
    SELECT 11399, 'Morphite', AVG(average)
    FROM market_history 
    WHERE type_id = 11399 
    AND region_id = 10000002 
    AND date >= date('now', '-7 days')
),


-- ============================================================================
-- MINERAL PRICING - CURRENT JITA BUY VALUES
-- ============================================================================
-- These are the ACTUAL prices you'll sell minerals at (97% of these values)
-- ============================================================================

mineral_jita_buy_values AS (
    SELECT
        type_id,
        MAX(CASE WHEN is_buy_order = 1 THEN price END) as jita_buy_value
    FROM market_orders
    WHERE type_id IN (34, 35, 36, 37, 38, 39, 40, 11399)  -- All 8 minerals
    AND region_id = 10000002                               -- Jita
    AND location_id = 60003760                             -- Jita 4-4
    GROUP BY type_id
),


-- ============================================================================
-- MINERAL PRICING - CONSOLIDATED
-- ============================================================================
-- Combine 7-day averages and current buy values into single row for easy access
-- ============================================================================

mineral_prices AS (
    SELECT
        -- 7-day averages (for reference)
        MAX(CASE WHEN mp7.type_id = 34 THEN mp7.avg_price_7d END) as trit_avg_7d,
        MAX(CASE WHEN mp7.type_id = 35 THEN mp7.avg_price_7d END) as pye_avg_7d,
        MAX(CASE WHEN mp7.type_id = 36 THEN mp7.avg_price_7d END) as mex_avg_7d,
        MAX(CASE WHEN mp7.type_id = 37 THEN mp7.avg_price_7d END) as iso_avg_7d,
        MAX(CASE WHEN mp7.type_id = 38 THEN mp7.avg_price_7d END) as noc_avg_7d,
        MAX(CASE WHEN mp7.type_id = 39 THEN mp7.avg_price_7d END) as zyd_avg_7d,
        MAX(CASE WHEN mp7.type_id = 40 THEN mp7.avg_price_7d END) as mega_avg_7d,
        MAX(CASE WHEN mp7.type_id = 11399 THEN mp7.avg_price_7d END) as morph_avg_7d,
        
        -- ACTUAL SELL PRICES: 97% of current Jita Buy Value (configurable)
        -- This is what you'll actually receive when selling to corp members
        MAX(CASE WHEN mjbv.type_id = 34 THEN mjbv.jita_buy_value END) * 
            (SELECT mineral_sell_pct_of_jbv FROM config) as trit_sell,
        MAX(CASE WHEN mjbv.type_id = 35 THEN mjbv.jita_buy_value END) * 
            (SELECT mineral_sell_pct_of_jbv FROM config) as pye_sell,
        MAX(CASE WHEN mjbv.type_id = 36 THEN mjbv.jita_buy_value END) * 
            (SELECT mineral_sell_pct_of_jbv FROM config) as mex_sell,
        MAX(CASE WHEN mjbv.type_id = 37 THEN mjbv.jita_buy_value END) * 
            (SELECT mineral_sell_pct_of_jbv FROM config) as iso_sell,
        MAX(CASE WHEN mjbv.type_id = 38 THEN mjbv.jita_buy_value END) * 
            (SELECT mineral_sell_pct_of_jbv FROM config) as noc_sell,
        MAX(CASE WHEN mjbv.type_id = 39 THEN mjbv.jita_buy_value END) * 
            (SELECT mineral_sell_pct_of_jbv FROM config) as zyd_sell,
        MAX(CASE WHEN mjbv.type_id = 40 THEN mjbv.jita_buy_value END) * 
            (SELECT mineral_sell_pct_of_jbv FROM config) as mega_sell,
        MAX(CASE WHEN mjbv.type_id = 11399 THEN mjbv.jita_buy_value END) * 
            (SELECT mineral_sell_pct_of_jbv FROM config) as morph_sell
    FROM mineral_prices_7day mp7
    CROSS JOIN mineral_jita_buy_values mjbv
),


-- ============================================================================
-- JITA ITEM PRICES
-- ============================================================================
-- Current best buy and sell prices for items on Jita market
-- ============================================================================

jita_prices AS (
    SELECT
        type_id,
        -- Best sell price = lowest sell order (what you pay to buy instantly)
        MIN(CASE WHEN is_buy_order = 0 THEN price END) as best_sell_price,
        
        -- Best buy price = highest buy order (what you'd get if selling)
        MAX(CASE WHEN is_buy_order = 1 THEN price END) as best_buy_price
    FROM market_orders
    WHERE region_id = (SELECT jita_region_id FROM config)
    AND location_id = (SELECT jita_station_id FROM config)
    GROUP BY type_id
),


-- ============================================================================
-- REPROCESSABLE ITEMS
-- ============================================================================
-- Get all items that can be reprocessed and have valid mineral yields
-- ============================================================================

reprocessable_items AS (
    SELECT
        it.type_id,
        it.type_name,
        it.volume,
        ig.group_name,
        ic.category_name,
        -- Mineral yields (per-unit, already adjusted for portion_size)
        iry.tritanium_yield,
        iry.pyerite_yield,
        iry.mexallon_yield,
        iry.isogen_yield,
        iry.nocxium_yield,
        iry.zydrine_yield,
        iry.megacyte_yield,
        iry.morphite_yield
    FROM inv_types it
    JOIN inv_groups ig ON ig.group_id = it.group_id
    JOIN inv_categories ic ON ic.category_id = ig.category_id
    JOIN item_reprocessing_yields iry ON iry.type_id = it.type_id
    WHERE iry.can_reprocess = 1                        -- Item can be reprocessed
    AND it.volume > 0                                  -- Has volume (for freight calc)
    AND it.volume <= (SELECT max_volume_m3 FROM config) -- Not too big
),


-- ============================================================================
-- MAIN CALCULATIONS
-- ============================================================================
-- Calculate costs, revenue, and profit for each reprocessable item
-- ============================================================================

calculations AS (
    SELECT
        -- Item information
        ri.type_id,
        ri.type_name,
        ri.volume,
        ri.group_name,
        ri.category_name,
        
        -- Market prices
        jp.best_sell_price,
        jp.best_buy_price,
        
        -- Efficiency
        e.total_efficiency,
        
        -- Mineral prices (for reference and calculations)
        mp.trit_avg_7d, mp.pye_avg_7d, mp.mex_avg_7d, mp.iso_avg_7d,
        mp.noc_avg_7d, mp.zyd_avg_7d, mp.mega_avg_7d, mp.morph_avg_7d,
        mp.trit_sell, mp.pye_sell, mp.mex_sell, mp.iso_sell,
        mp.noc_sell, mp.zyd_sell, mp.mega_sell, mp.morph_sell,
        
        -- ----------------------------------------------------------------
        -- MINERAL YIELDS AFTER REPROCESSING
        -- ----------------------------------------------------------------
        -- Multiply base yields by efficiency to get actual amounts
        -- ----------------------------------------------------------------
        (ri.tritanium_yield * e.total_efficiency) as actual_trit,
        (ri.pyerite_yield * e.total_efficiency) as actual_pye,
        (ri.mexallon_yield * e.total_efficiency) as actual_mex,
        (ri.isogen_yield * e.total_efficiency) as actual_iso,
        (ri.nocxium_yield * e.total_efficiency) as actual_noc,
        (ri.zydrine_yield * e.total_efficiency) as actual_zyd,
        (ri.megacyte_yield * e.total_efficiency) as actual_mega,
        (ri.morphite_yield * e.total_efficiency) as actual_morph,
        
        -- ----------------------------------------------------------------
        -- TOTAL MINERAL VALUE AT YOUR SELL PRICE (97% JBV)
        -- ----------------------------------------------------------------
        -- This is your actual revenue when selling to corp members
        -- ----------------------------------------------------------------
        (
            (ri.tritanium_yield * e.total_efficiency * mp.trit_sell) +
            (ri.pyerite_yield * e.total_efficiency * mp.pye_sell) +
            (ri.mexallon_yield * e.total_efficiency * mp.mex_sell) +
            (ri.isogen_yield * e.total_efficiency * mp.iso_sell) +
            (ri.nocxium_yield * e.total_efficiency * mp.noc_sell) +
            (ri.zydrine_yield * e.total_efficiency * mp.zyd_sell) +
            (ri.megacyte_yield * e.total_efficiency * mp.mega_sell) +
            (ri.morphite_yield * e.total_efficiency * mp.morph_sell)
        ) as mineral_revenue,
        
        -- ----------------------------------------------------------------
        -- COSTS
        -- ----------------------------------------------------------------
        -- Freight: Volume-based shipping cost
        (ri.volume * (SELECT freight_per_m3 FROM config)) as freight_cost,
        
        -- Collateral: 1% of Jita Split (avg of buy/sell) for freighter pilot
        ((jp.best_sell_price + jp.best_buy_price) / 2 * (SELECT freighter_collateral_pct FROM config)) as collateral_fee,
        
        -- Total cost: Item + Freight + Collateral
        jp.best_sell_price + 
        (ri.volume * (SELECT freight_per_m3 FROM config)) + 
        ((jp.best_sell_price + jp.best_buy_price) / 2 * (SELECT freighter_collateral_pct FROM config)) as total_cost,
        
        -- ----------------------------------------------------------------
        -- MARKET SPREAD (FAT-FINGER DETECTION)
        -- ----------------------------------------------------------------
        -- Calculate spread percentage to filter out suspicious orders
        -- ----------------------------------------------------------------
        CASE 
            WHEN jp.best_buy_price > 0 THEN 
                ((jp.best_sell_price - jp.best_buy_price) / jp.best_buy_price * 100)
            ELSE 999.0
        END as price_spread_pct
        
    FROM reprocessable_items ri
    JOIN jita_prices jp ON jp.type_id = ri.type_id
    CROSS JOIN efficiency e
    CROSS JOIN mineral_prices mp
    WHERE jp.best_sell_price IS NOT NULL
    AND jp.best_buy_price IS NOT NULL
    
    -- ----------------------------------------------------------------
    -- FAT-FINGER FILTER
    -- ----------------------------------------------------------------
    -- Exclude orders where sell price is too close to buy price
    -- This usually indicates a pricing mistake (fat-finger)
    -- ----------------------------------------------------------------
    AND CASE 
        WHEN jp.best_buy_price > 0 THEN 
            ((jp.best_sell_price - jp.best_buy_price) / jp.best_buy_price * 100)
        ELSE 999.0
    END >= (SELECT min_spread_pct FROM config)
),


-- ============================================================================
-- PROFIT ANALYSIS
-- ============================================================================
-- Calculate final profit metrics and prepare for output
-- ============================================================================

profit_analysis AS (
    SELECT
        type_name,
        group_name,
        category_name,
        volume,
        best_sell_price,
        best_buy_price,
        price_spread_pct,
        
        -- Costs breakdown
        freight_cost,
        collateral_fee,
        total_cost,
        
        -- Revenue
        mineral_revenue,
        
        -- ----------------------------------------------------------------
        -- PROFIT CALCULATIONS
        -- ----------------------------------------------------------------
        (mineral_revenue - total_cost) as profit_per_unit,
        ROUND(((mineral_revenue - total_cost) / total_cost * 100), 2) as profit_margin_pct,
        
        -- ----------------------------------------------------------------
        -- ISK DENSITY METRICS (FREIGHT EFFICIENCY)
        -- ----------------------------------------------------------------
        -- These help identify items worth the freight cost
        -- ----------------------------------------------------------------
        
        -- Mineral value per m³ (how much ISK of minerals per cubic meter)
        ROUND(mineral_revenue / NULLIF(volume, 0), 2) as isk_per_m3,
        
        -- Profit per m³ (net profit density)
        ROUND((mineral_revenue - total_cost) / NULLIF(volume, 0), 2) as profit_per_m3,
        
        -- Freight efficiency: What % of revenue is eaten by freight?
        ROUND((freight_cost / NULLIF(mineral_revenue, 0) * 100), 2) as freight_pct_of_revenue,
        
        -- Value density rating (item price per m³ - shows compact value)
        ROUND(best_sell_price / NULLIF(volume, 0), 2) as item_value_density,
        
        -- ----------------------------------------------------------------
        -- MINERAL YIELDS (for display)
        -- ----------------------------------------------------------------
        ROUND(actual_trit, 2) as trit,
        ROUND(actual_pye, 2) as pye,
        ROUND(actual_mex, 2) as mex,
        ROUND(actual_iso, 2) as iso,
        ROUND(actual_noc, 2) as noc,
        ROUND(actual_zyd, 2) as zyd,
        ROUND(actual_mega, 2) as mega,
        ROUND(actual_morph, 2) as morph,
        
        -- Efficiency used
        ROUND(total_efficiency * 100, 2) as efficiency_pct
        
    FROM calculations
)


-- ============================================================================
-- FINAL OUTPUT
-- ============================================================================
-- Show top profitable opportunities, sorted by profit margin
-- ============================================================================

SELECT
    -- Item identification
    type_name as item,
    --group_name as item_group,
    --ROUND(volume, 2) as vol_m3,
    
    -- Market prices
    ROUND(best_sell_price, 2) as jita_sell_price,
    ROUND(best_buy_price, 2) as jita_buy_price,
    ROUND(price_spread_pct, 2) as spread_pct,
    
    -- Cost breakdown
    -- ROUND(freight_cost, 2) as freight_cost,
    -- ROUND(collateral_fee, 2) as collateral_fee,
    -- ROUND(total_cost, 2) as total_cost,
    
    -- Revenue and profit
    ROUND(mineral_revenue, 2) as mineral_revenue_97pct_jbv,
    --ROUND(profit_per_unit, 2) as profit_per_unit,
    profit_margin_pct as margin_pct,
    
    -- Mineral yields (for reference)
    --trit, pye, mex, iso, noc, zyd, mega, morph,
    
    -- ----------------------------------------------------------------
    -- ISK DENSITY METRICS (Freight efficiency!)
    -- ----------------------------------------------------------------
    isk_per_m3,                    -- Mineral value per m³
    profit_per_m3,                 -- Net profit per m³
    freight_pct_of_revenue,        -- Freight % of revenue
    item_value_density,            -- Item price per m³
    
    -- Efficiency used
    efficiency_pct

FROM profit_analysis

-- ----------------------------------------------------------------
-- APPLY PROFIT FILTERS
-- ----------------------------------------------------------------
WHERE profit_per_unit >= (SELECT min_profit_per_unit FROM config)
AND profit_margin_pct >= (SELECT min_profit_margin_pct FROM config)

-- ----------------------------------------------------------------
-- SORT BY ISK DENSITY (Best freight efficiency first!)
-- ----------------------------------------------------------------
ORDER BY 
    profit_per_m3 DESC,            -- Highest profit density first
    profit_margin_pct DESC         -- Then by margin

LIMIT 50  -- Top 50 opportunities


-- ============================================================================
-- HOW TO USE THIS QUERY
-- ============================================================================
--
-- 1. PREREQUISITES:
--    - Run update_market_orders.py to get fresh Jita prices
--    - Ensure item_reprocessing_yields table is populated with correct data
--      (Run create_item_reprocessing_table_from_JSONL_FIXED.py if needed)
--
-- 2. CONFIGURE:
--    - Edit the CONFIG section at the top
--    - Verify structure_bonus with your corpmate
--    - Adjust filters to show more/fewer results
--
-- 3. RUN:
--    - Execute this query in your SQLite database browser
--    - Results show items sorted by profit margin
--
-- 4. INTERPRET RESULTS:
--    - Look for 10-30% margins (realistic)
--    - Check spread_pct (should be >5% to avoid fat-fingers)
--    - Consider volume (lower volume = lower freight cost)
--    - Large weapons and T2 modules typically best
--
-- 5. WORKFLOW:
--    a. Buy items from Jita sell orders (instant purchase)
--    b. Contract to freighter (pay collateral fee)
--    c. Ship to null-sec
--    d. Reprocess at corp Tatara
--    e. Sell minerals at 97% JBV to corp members
--
-- ============================================================================
-- EXPECTED RESULTS
-- ============================================================================
--
-- Good opportunities:
--   - T2 Large weapons: 15-25% margin
--   - T2 Medium weapons: 12-20% margin
--   - Large armor/shield modules: 10-18% margin
--   - Capital components: 8-15% margin
--
-- Avoid:
--   - Ammunition (low per-unit value even after portion_size fix)
--   - Very small modules (<5m³, high freight % of value)
--   - Huge items (>5000m³, freight cost too high)
--   - Fat-finger orders (spread <5%)
--
-- ============================================================================