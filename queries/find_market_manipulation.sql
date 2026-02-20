--Need to add in tax stuff

SELECT 
    type_name,
    MIN(price) AS lowest_sell,
    AVG(price) AS avg_sell,
    ((AVG(price) - MIN(price)) / AVG(price)) * 100 AS gap_percent,
    SUM(volume_remain)
FROM market_orders mo
JOIN inv_types it ON mo.type_id = it.type_id
WHERE is_buy_order = false
GROUP BY type_name
HAVING ((AVG(price) - MIN(price)) / AVG(price)) * 100 BETWEEN 10 AND 20
ORDER BY gap_percent DESC;