SELECT 
    trade_date,
    day_of_week,
    printf('%,.0f', gross_revenue) || ' ISK' as revenue,
    printf('%,.0f', cost_of_goods) || ' ISK' as costs,
    printf('%,.0f', total_fees) || ' ISK' as fees,
    printf('%,.0f', gross_profit) || ' ISK' as gross_profit,
    printf('%,.0f', net_profit) || ' ISK' as net_profit,
    printf('%.2f', gross_margin_percent) || '%' as gross_margin,
    printf('%.2f', net_margin_percent) || '%' as net_margin,
    units_bought || ' bought' as buying,
    units_sold || ' sold' as selling
FROM v_daily_trading_performance
WHERE trade_date >= date('now', '-30 days')
ORDER BY trade_date DESC;