-- BWF Market Arbitrage Query
WITH freight_costs_per_item AS (
    SELECT 
        di.type_id,
        it.type_name,
        it.volume,
        jita.best_buy_price,
        fs.service_name,
        fs.cost_per_m3,
        fs.collateral_fee_percent,
        fs.minimum_reward,
        (it.volume * fs.cost_per_m3) + (COALESCE(jita.best_buy_price, 0) * fs.collateral_fee_percent) AS total_freight_cost
    FROM doctrine_items di
    JOIN inv_types it ON it.type_id = di.type_id
    CROSS JOIN freighting_services fs
    LEFT JOIN (
        SELECT 
            type_id,
            MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy_price
        FROM market_orders
        WHERE type_id IN (SELECT type_id FROM doctrine_items)
        GROUP BY type_id
    ) jita ON jita.type_id = di.type_id
    WHERE fs.is_active = 1
    AND fs.route_from = 'Jita'
    AND fs.route_to = 'BWF-ZZ'
),
best_freight_per_item AS (
    SELECT 
        type_id,
        type_name,
        volume,
        best_buy_price,
        service_name AS best_service,
        total_freight_cost,
        MIN(total_freight_cost) AS cheapest_freight
    FROM freight_costs_per_item
    GROUP BY type_id, type_name, volume, best_buy_price
)
SELECT 
    bfi.type_name AS item_name,
    printf('%,.2f', bfi.best_buy_price) AS jita_buy,
    printf('%,.2f', bwf.lowest_sell_price) AS bwf_sell,
    printf('%,.2f', bfi.total_freight_cost) AS freight_cost,
    CASE 
        WHEN bfi.best_buy_price IS NOT NULL AND bwf.lowest_sell_price IS NOT NULL
        THEN printf('%,.2f', (bwf.lowest_sell_price * 0.9636) - (bfi.best_buy_price * 1.015) - bfi.total_freight_cost)
        ELSE NULL
    END AS profit,
    CASE 
        WHEN bfi.best_buy_price IS NOT NULL AND bwf.lowest_sell_price IS NOT NULL AND bfi.best_buy_price > 0
        THEN printf('%.2f%%', (((bwf.lowest_sell_price * 0.9636) - (bfi.best_buy_price * 1.015) - bfi.total_freight_cost) / (bfi.best_buy_price * 1.015)) * 100)
        ELSE NULL
    END AS profit_margin,
    CASE 
        WHEN bfi.best_buy_price IS NOT NULL AND bwf.lowest_sell_price IS NOT NULL AND ((bfi.best_buy_price * 1.015) + bfi.total_freight_cost) > 0
        THEN printf('%.2f%%', (((bwf.lowest_sell_price * 0.9636) - (bfi.best_buy_price * 1.015) - bfi.total_freight_cost) / ((bfi.best_buy_price * 1.015) + bfi.total_freight_cost)) * 100)
        ELSE NULL
    END AS roi,
    printf('%,d', COALESCE(bwf.num_sell_orders, 0)) AS bwf_sell_orders,
    printf('%,d', COALESCE(CAST(bwf.total_sell_volume AS INTEGER), 0)) AS bwf_sell_volume
FROM best_freight_per_item bfi
LEFT JOIN (
    SELECT 
        type_id,
        MIN(CASE WHEN is_buy_order = 0 THEN price END) AS lowest_sell_price,
        SUM(CASE WHEN is_buy_order = 0 THEN volume_remain ELSE 0 END) AS total_sell_volume,
        SUM(CASE WHEN is_buy_order = 0 THEN 1 ELSE 0 END) AS num_sell_orders
    FROM bwf_market_orders
    WHERE type_id IN (SELECT type_id FROM doctrine_items)
    GROUP BY type_id
) bwf ON bwf.type_id = bfi.type_id
ORDER BY 
    CASE 
        WHEN bwf.type_id IS NULL THEN 0
        WHEN COALESCE(bwf.num_sell_orders, 0) = 0 THEN 1
        ELSE 2
    END,
    CASE 
        WHEN bfi.best_buy_price IS NOT NULL AND bwf.lowest_sell_price IS NOT NULL
        THEN (bwf.lowest_sell_price * 0.9636) - (bfi.best_buy_price * 1.015) - bfi.total_freight_cost
        ELSE NULL
    END DESC;