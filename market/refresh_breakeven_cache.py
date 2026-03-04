import sqlite3
from datetime import datetime
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / 'scripts'))

from script_utils import timed_script

DB_PATH = str(PROJECT_DIR / 'mydatabase.db')
DEFAULT_BUY_COST_MULTIPLIER = 1.015
DEFAULT_SELL_REVENUE_MULTIPLIER = 0.95125


def build_fee_cte(cursor):
    """Return SQL for my_fees CTE using view data when available, else defaults."""
    cursor.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'view'
          AND name = 'v_my_trading_fees'
        LIMIT 1
        """
    )
    has_fee_view = cursor.fetchone() is not None

    if has_fee_view:
        print("[OK] Using trading fees from v_my_trading_fees")
        return """
        my_fees AS (
            SELECT
                buy_cost_multiplier,
                sell_revenue_multiplier
            FROM v_my_trading_fees
            LIMIT 1
        )
        """

    print(
        "[WARN] v_my_trading_fees not found; using defaults "
        f"(buy x{DEFAULT_BUY_COST_MULTIPLIER}, sell x{DEFAULT_SELL_REVENUE_MULTIPLIER})"
    )
    return f"""
    my_fees AS (
        SELECT
            {DEFAULT_BUY_COST_MULTIPLIER} AS buy_cost_multiplier,
            {DEFAULT_SELL_REVENUE_MULTIPLIER} AS sell_revenue_multiplier
    )
    """

@timed_script
def refresh_breakeven_cache():
    """
    Pre-calculate break-even prices and store in a table.
    Uses temporary table approach for zero downtime.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(">>> Creating temporary cache table...")
    
    # Drop temp table if exists
    cursor.execute("DROP TABLE IF EXISTS breakeven_cache_temp")

    fee_cte_sql = build_fee_cte(cursor)
    
    # Create TEMPORARY table with the calculation
    cursor.execute(f"""
        CREATE TABLE breakeven_cache_temp AS
        WITH my_sell_orders AS (
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
        ),
        most_recent_purchase AS (
            SELECT 
                wt.type_id,
                wt.unit_price as buy_price,
                wt.date,
                ROW_NUMBER() OVER (PARTITION BY wt.type_id ORDER BY wt.date DESC) as rn
            FROM wallet_transactions wt
            WHERE wt.character_id = 2114278577
            AND wt.is_buy = 1
            AND wt.is_personal = 1
        ),
        recent_buy_price AS (
            SELECT *
            FROM (
                SELECT
                    wt.type_id,
                    wt.price AS 'most_recent_buy_price',
                    wt.issued AS 'date',
                    ROW_NUMBER() OVER (PARTITION BY type_id ORDER BY issued DESC) as rn
                FROM character_orders wt
                WHERE duration <> 0
                AND is_buy_order = 1
            ) sub
            WHERE rn = 1
            ORDER BY date DESC
        ),
        {fee_cte_sql}
        SELECT 
            t.type_name,
            so.volume_remain as units_to_sell,
            ROUND(rbp.most_recent_buy_price, 2) as actual_buy_price_paid,
            ROUND(rbp.most_recent_buy_price * f.buy_cost_multiplier, 2) as actual_cost_with_fees,
            ROUND(so.current_sell_price, 2) as current_sell_price,
            ROUND(so.current_sell_price * f.sell_revenue_multiplier, 2) as actual_revenue_after_fees,
            ROUND((rbp.most_recent_buy_price * f.buy_cost_multiplier) / f.sell_revenue_multiplier, 2) as breakeven_price,
            ROUND((so.current_sell_price * f.sell_revenue_multiplier) - (rbp.most_recent_buy_price * f.buy_cost_multiplier), 2) as profit_per_unit,
            ROUND(((so.current_sell_price * f.sell_revenue_multiplier) - (rbp.most_recent_buy_price * f.buy_cost_multiplier)) * so.volume_remain, 2) as total_profit,
            ROUND(so.current_sell_price - ((rbp.most_recent_buy_price * f.buy_cost_multiplier) / f.sell_revenue_multiplier), 2) as safety_margin,
            ROUND((((so.current_sell_price * f.sell_revenue_multiplier) - (rbp.most_recent_buy_price * f.buy_cost_multiplier)) / (rbp.most_recent_buy_price * f.buy_cost_multiplier)) * 100, 2) as margin_percent,
            CASE 
                WHEN (so.current_sell_price * f.sell_revenue_multiplier) > (rbp.most_recent_buy_price * f.buy_cost_multiplier) THEN 'PROFITABLE'
                WHEN (so.current_sell_price * f.sell_revenue_multiplier) = (rbp.most_recent_buy_price * f.buy_cost_multiplier) THEN 'BREAK-EVEN'
                ELSE 'LOSING MONEY'
            END as status
        FROM my_sell_orders so
        JOIN inv_types t ON so.type_id = t.type_id
        LEFT JOIN recent_buy_price rbp ON so.type_id = rbp.type_id
        CROSS JOIN my_fees f
        WHERE rbp.most_recent_buy_price IS NOT NULL
        ORDER BY type_name
    """)
    
    # Count results in temp table
    cursor.execute("SELECT COUNT(*) FROM breakeven_cache_temp")
    count = cursor.fetchone()[0]
    
    print(f"[OK] Temporary cache calculated: {count} sell orders")
    
    # For cache tables, use DROP and RENAME instead of ALTER TABLE RENAME
    # This avoids issues with views that reference the table
    print("\n>>> Replacing cache table (INSTANTANEOUS)...")
    
    cursor.execute('BEGIN IMMEDIATE')
    
    try:
        # Drop the old cache (this is safe - it's just a cache)
        cursor.execute('DROP TABLE IF EXISTS breakeven_cache')
        
        # Rename temp to production (instant)
        cursor.execute('ALTER TABLE breakeven_cache_temp RENAME TO breakeven_cache')
        
        conn.commit()
        print("[OK] Cache replaced successfully - NEW DATA NOW LIVE!")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] ERROR during replacement: {e}")
        print("[ERROR] Temporary table remains - will retry on next run")
        raise
    
    conn.close()
    
    # Summary - will be wrapped by @timed_script decorator
    print(f"\nCached {count} sell orders with ZERO DOWNTIME")

if __name__ == '__main__':
    refresh_breakeven_cache()