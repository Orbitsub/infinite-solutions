WITH my_fees AS (
        SELECT 
            buy_cost_multiplier,
            sell_revenue_multiplier
        FROM v_my_trading_fees
        LIMIT 1
)
,my_sell_orders AS (
    SELECT 
        co.order_id,
        co.type_id,
        co.price as current_sell_price,
        co.volume_remain,
        co.volume_total
    FROM character_orders co
    WHERE co.character_id = 2114278577
    AND co.state = 'active'
    AND co.is_buy_order = 0
)

SELECT 
    bc.type_name,
    it.type_id,
    units_to_sell,
    volume_total,
    volume_total - volume_remain AS 'volume_sold',
    printf('%,.2f', actual_buy_price_paid) || ' ISK' as what_i_actually_paid,
    printf('%,.2f', bc.current_sell_price) || ' ISK' as selling_for,
    printf('%,.2f', margin_percent) || '%' as margin,
    printf('%,.2f', total_profit) || ' ISK' as profit,
    printf('%,.2f', breakeven_price) || ' ISK' AS break_even_price,
    CASE WHEN total_profit < 0
            THEN printf('%,.2f',ROUND((((actual_buy_price_paid * buy_cost_multiplier * units_to_sell) - total_profit) / (units_to_sell * sell_revenue_multiplier) ), 2)) || ' ISK'
        ELSE ''
        END
    AS recoup_price
FROM breakeven_cache bc
JOIN inv_types it ON it.type_name = bc.type_name
JOIN my_sell_orders mso ON mso.type_id = it.type_id
CROSS JOIN my_fees
ORDER BY total_profit DESC