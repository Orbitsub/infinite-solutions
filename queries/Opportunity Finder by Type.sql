SELECT
    vto.item_category
    ,img.market_group_name
    ,vto.type_name
    ,current_buy_price
    ,current_sell_price
    ,your_buy_cost
    ,your_sell_revenue
    ,profit_per_unit
    ,net_margin_percent
    ,estimated_profit_per_trade
    ,avg_daily_volume
    ,total_7day_volume
    ,immediate_buy_demand
    ,daily_profit_potential
    ,buy_order_count
    ,sell_order_count
    ,hours_since_buy_update
    ,hours_since_sell_update
    ,already_trading
    ,liquidity_rating
    ,competition_rating
    --,opportunity_score
FROM v_trading_opportunities vto
JOIN inv_types it ON it.type_id = vto.type_id
JOIN inv_market_groups img ON it.market_group_id = img.market_group_id
WHERE market_group_name LIKE '%planetary%'
-- (item_category LIKE '%Hybrid%'
-- OR item_category LIKE '%Projectile%'
-- OR item_category LIKE '%Frequency%'
-- OR item_category LIKE '%Torpedo%'
-- OR item_category LIKE '%Missile%'
-- OR item_category LIKE '%rocket%')
--AND liquidity_rating = 'EXCELLENT'
--AND competition_rating = 'HIGH'
--AND net_margin_percent BETWEEN 10 AND 100

ORDER BY net_margin_percent DESC