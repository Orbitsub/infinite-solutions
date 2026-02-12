-- Migration: Adjust Tritanium buyback price from 98% to 97% JBV
-- Date: 2026-02-12
-- Author: Hamektok
-- Reason: Market pricing adjustment

-- Update Tritanium (Type ID: 34) from 98% to 97% of Jita Buy Value
UPDATE tracked_market_items
SET price_percentage = 97
WHERE type_id = 34
  AND type_name = 'Tritanium';

-- Verify the change
SELECT type_id, type_name, price_percentage
FROM tracked_market_items
WHERE type_id = 34;
