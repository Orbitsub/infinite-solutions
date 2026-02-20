SELECT
    it.type_name,
    mh.date,
    printf('%,.2f',average) || ' ISK' AS 'daily_average',
    printf('%,.2f',(
        SELECT AVG(mh2.average)
        FROM market_history mh2
        WHERE mh2.type_id = mh.type_id
        AND mh2.date >= DATE(mh.date,'-1 year')
        AND mh2.date <= mh.date
    )) || ' ISK' AS 'avg_1year',
    printf('%,.2f',(
        SELECT AVG(mh2.average)
        FROM market_history mh2
        WHERE mh2.type_id = mh.type_id
        AND mh2.date >= DATE(mh.date,'-1 month')
        AND mh2.date <= mh.date
    )) || ' ISK' AS 'avg_1month',
        printf('%,.2f',(
    SELECT AVG(mh2.average)
    FROM market_history mh2
    WHERE mh2.type_id = mh.type_id
    AND mh2.date >= DATE(mh.date,'-7 days')
    AND mh2.date <= mh.date
)) || ' ISK' AS 'avg_1week',
    printf('%d',mh.order_count) || ' orders' AS 'order_count',
    printf('%,.2f',mh.volume) || ' m3' AS 'volume',
    ROW_NUMBER() OVER(PARTITION BY type_name ORDER BY date DESC) AS 'rn'
FROM market_history AS mh
JOIN inv_types AS it 
    ON mh.type_id = it.type_id
WHERE mh.date >= DATE('now','-30 day')
AND type_name = 'Small Focused Pulse Laser II'
LIMIT 100