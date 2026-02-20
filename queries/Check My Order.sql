-- @block Bookmarked query
-- @group EVE Saved Queries
-- @name Check Orders

--Check Orders
SELECT
    type_name
    ,order_type
    ,status
    ,market_temperature
    ,trading_intensity
    ,action_recommendation
FROM v_my_order_status
WHERE action_recommendation NOT LIKE '%WINNING%'