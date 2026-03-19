"""
Market Opportunity Scanner
--------------------------
Scans Jita buy/sell spreads and ranks station trading opportunities.

Manipulation filters applied:
  - Minimum order count on each side (depth filter)
  - Minimum avg daily trading volume from historical data
  - Price stability check via 14-day market snapshots (if available)
  - Flags suspiciously high margins that may indicate fake/bait orders
  - Flags current price deviating significantly from recent snapshot average

Usage:
    python scripts/market_opportunity_scanner.py [--min-margin N] [--min-vol N] [--limit N]
"""

import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH   = os.path.join(os.path.dirname(__file__), '..', 'mydatabase.db')
JITA      = 60003760
THE_FORGE = 10000002

# Your actual trading fees (from v_my_trading_fees — Broker Relations 5, Accounting 5)
BUY_COST_MULT  = 1.015     # cost = price × 1.015
SELL_REV_MULT  = 0.95125   # revenue = price × 0.95125

# ── Filters (adjustable via CLI) ──────────────────────────────────────────────
MIN_NET_MARGIN_PCT  = 10.0      # Minimum net margin % after your fees
MIN_PROFIT_PER_UNIT = 100_000_000  # ISK — skip penny items even at high margin
MIN_BUY_ORDERS      = 5        # Minimum buy orders in book (depth)
MIN_SELL_ORDERS     = 5        # Minimum sell orders in book (depth)
MIN_AVG_DAILY_VOL   = 20       # Units/day from historical data (skip illiquid)
SNAPSHOT_LOOKBACK_DAYS = 14    # Days of snapshot data to use for stability check
MIN_SNAPSHOTS       = 3        # Need at least this many snapshots for stability check

# Manipulation warning thresholds
WARN_MARGIN_PCT     = 100.0    # Flag margins above this (likely manipulated/bait)
WARN_VOLATILITY_PCT = 40.0     # Flag if price swings >40% in snapshot window
WARN_DRIFT_PCT      = 35.0     # Flag if current price drifted >35% from snapshot avg
# ─────────────────────────────────────────────────────────────────────────────


def isk(value):
    """Format ISK value to readable string."""
    if value >= 1_000_000_000:
        return f"{value/1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value/1_000:.0f}K"
    return f"{value:.0f}"


def run(min_margin=MIN_NET_MARGIN_PCT, min_vol=MIN_AVG_DAILY_VOL, limit=50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    snap_cutoff = (datetime.now(timezone.utc) - timedelta(days=SNAPSHOT_LOOKBACK_DAYS)).isoformat()

    params = {
        "sell_rev":        SELL_REV_MULT,
        "buy_cost":        BUY_COST_MULT,
        "min_buy_orders":  MIN_BUY_ORDERS,
        "min_sell_orders": MIN_SELL_ORDERS,
        "min_vol":         min_vol,
        "min_profit":      MIN_PROFIT_PER_UNIT,
        "min_margin":      min_margin,
        "max_vol_pct":     WARN_VOLATILITY_PCT,
        "max_drop_pct":    -WARN_DRIFT_PCT,
        "limit":           limit,
        "jita":            JITA,
        "forge":           THE_FORGE,
        "snap_cutoff":     snap_cutoff,
        "min_snaps":       MIN_SNAPSHOTS,
    }

    c.execute("""
        WITH
        -- ── Live spread from current market orders ──────────────────────────
        spread AS (
            SELECT
                type_id,
                MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_buy,
                MIN(CASE WHEN is_buy_order = 0 THEN price END) AS best_sell,
                COUNT(CASE WHEN is_buy_order = 1 THEN 1 END)   AS buy_orders,
                COUNT(CASE WHEN is_buy_order = 0 THEN 1 END)   AS sell_orders,
                SUM(CASE WHEN is_buy_order = 1 THEN volume_remain END) AS buy_vol_available,
                SUM(CASE WHEN is_buy_order = 0 THEN volume_remain END) AS sell_vol_available
            FROM market_orders
            WHERE location_id = :jita AND region_id = :forge
            GROUP BY type_id
            HAVING best_buy IS NOT NULL
               AND best_sell IS NOT NULL
               AND best_sell > best_buy
        ),

        -- ── Historical volume (from market_history — may be a few weeks old) ─
        hist AS (
            SELECT
                type_id,
                ROUND(AVG(volume), 0)   AS avg_daily_vol,
                AVG(average)            AS hist_avg_price,
                MAX(highest)            AS hist_max_price,
                MIN(lowest)             AS hist_min_price,
                MAX(date)               AS last_history_date,
                COUNT(*)                AS history_days
            FROM market_history
            WHERE region_id = :forge
            GROUP BY type_id
        ),

        -- ── Price stability from recent market snapshots ─────────────────────
        snaps AS (
            SELECT
                type_id,
                AVG(best_sell)                                    AS snap_avg_sell,
                AVG(best_buy)                                     AS snap_avg_buy,
                MAX(best_sell)                                    AS snap_max_sell,
                MIN(best_sell)                                    AS snap_min_sell,
                COUNT(*)                                          AS snap_count,
                -- Volatility: how much has best_sell ranged in the window?
                CASE WHEN AVG(best_sell) > 0
                     THEN (MAX(best_sell) - MIN(best_sell)) / AVG(best_sell) * 100
                     ELSE NULL END                                AS sell_volatility_pct
            FROM market_price_snapshots
            WHERE timestamp >= :snap_cutoff
            GROUP BY type_id
            HAVING COUNT(*) >= :min_snaps
        )

        -- ── Main result ──────────────────────────────────────────────────────
        SELECT
            t.type_name,
            t.type_id,
            s.best_buy,
            s.best_sell,
            s.buy_orders,
            s.sell_orders,
            s.buy_vol_available,
            s.sell_vol_available,

            -- Profitability (after your actual fees)
            ROUND((s.best_sell * :sell_rev - s.best_buy * :buy_cost) /
                  (s.best_buy * :buy_cost) * 100, 1)              AS net_margin_pct,
            ROUND(s.best_sell * :sell_rev - s.best_buy * :buy_cost, 0)
                                                                   AS profit_per_unit,

            -- Volume & liquidity
            CAST(COALESCE(h.avg_daily_vol, 0) AS INTEGER)         AS avg_daily_vol,
            h.last_history_date,
            h.history_days,

            -- Daily ISK potential (profit per unit × units that trade per day)
            ROUND((s.best_sell * :sell_rev - s.best_buy * :buy_cost) *
                  COALESCE(h.avg_daily_vol, 0), 0)                AS daily_isk_potential,

            -- Snapshot-based quality data
            ROUND(sn.snap_avg_sell, 0)                            AS snap_avg_sell,
            ROUND(sn.sell_volatility_pct, 1)                      AS sell_volatility_pct,
            -- How much has the current price drifted from the snapshot average?
            CASE WHEN sn.snap_avg_sell IS NOT NULL AND sn.snap_avg_sell > 0
                 THEN ROUND((s.best_sell - sn.snap_avg_sell) / sn.snap_avg_sell * 100, 1)
                 ELSE NULL END                                     AS drift_from_snap_pct,
            sn.snap_count,

            -- Item group for context
            ig.group_name                                          AS item_group
        FROM spread s
        JOIN inv_types t  ON s.type_id = t.type_id
        JOIN inv_groups ig ON t.group_id = ig.group_id
        LEFT JOIN hist  h  ON s.type_id = h.type_id
        LEFT JOIN snaps sn ON s.type_id = sn.type_id
        WHERE t.published = 1
          AND t.market_group_id IS NOT NULL
          -- ── Hard filters ──────────────────────────────────────────────────
          AND s.buy_orders  >= :min_buy_orders
          AND s.sell_orders >= :min_sell_orders
          AND COALESCE(h.avg_daily_vol, 0) >= :min_vol
          AND (s.best_sell * :sell_rev - s.best_buy * :buy_cost) >= :min_profit
          AND (s.best_sell * :sell_rev - s.best_buy * :buy_cost) /
              (s.best_buy * :buy_cost) * 100 >= :min_margin
          -- ── Snapshot manipulation filter (applied only when data exists) ──
          -- Reject if sell price is wildly volatile (instability = manipulation)
          AND (sn.sell_volatility_pct IS NULL OR sn.sell_volatility_pct <= :max_vol_pct)
          -- Reject if current best_sell is >X% BELOW snapshot avg
          -- (big drop = likely bait order sitting at fake low price)
          AND (sn.snap_avg_sell IS NULL
               OR (s.best_sell - sn.snap_avg_sell) / sn.snap_avg_sell * 100 >= :max_drop_pct)
        ORDER BY daily_isk_potential DESC
        LIMIT :limit
    """, params)

    rows = c.fetchall()
    conn.close()
    return rows


def flag(row):
    """Return warning flags for a result row."""
    flags = []
    margin = row["net_margin_pct"]
    vol    = row["sell_volatility_pct"]
    drift  = row["drift_from_snap_pct"]
    buy_ct = row["buy_orders"]
    sell_ct= row["sell_orders"]

    if margin > WARN_MARGIN_PCT:
        flags.append(f"HIGH-MARGIN({margin:.0f}%)")   # suspiciously large spread
    if buy_ct < 10:
        flags.append(f"LOW-BUY-DEPTH({buy_ct})")      # easy to fake
    if sell_ct < 10:
        flags.append(f"LOW-SELL-DEPTH({sell_ct})")
    if vol is not None and vol > 20:
        flags.append(f"VOLATILE({vol:.0f}%)")          # price swings a lot
    if drift is not None and drift > WARN_DRIFT_PCT:
        flags.append(f"PRICE-SPIKE(+{drift:.0f}%)")   # price spiked vs recent avg
    return flags


def print_report(rows, min_margin, min_vol):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print()
    print("=" * 100)
    print(f"  JITA STATION TRADING OPPORTUNITIES   |   Generated {now}")
    print(f"  Filters: Net margin >= {min_margin}%  |  Min avg volume >= {min_vol}/day  |  Min profit >= {isk(MIN_PROFIT_PER_UNIT)}/unit")
    print(f"  Fees: Buy x{BUY_COST_MULT} ({(BUY_COST_MULT-1)*100:.1f}% broker)  |  Sell x{SELL_REV_MULT} ({(1-SELL_REV_MULT)*100:.3f}% broker+tax)")
    print("=" * 100)
    print()

    if not rows:
        print("  No opportunities found with current filters.")
        print("  Try lowering --min-margin or --min-vol.")
        return

    line_w = 100
    header = (f"{'#':>3}  {'Item':<40} {'Buy':>10} {'Sell':>10} {'Net%':>6} "
              f"{'Profit/u':>10} {'Vol/day':>8} {'Depth B/S':>10}  {'Daily ISK':>12}")
    print(header)
    print("-" * line_w)

    for i, row in enumerate(rows, 1):
        flags = flag(row)
        snap_note = ""
        if row["snap_count"]:
            snap_note = f" [snap avg {isk(row['snap_avg_sell'])}, {row['snap_count']} pts"
            if row["drift_from_snap_pct"] is not None:
                snap_note += f", drift {row['drift_from_snap_pct']:+.0f}%"
            snap_note += "]"

        name = row["type_name"]
        if len(name) > 39:
            name = name[:36] + "..."

        print(
            f"{i:>3}. {name:<40} "
            f"{isk(row['best_buy']):>10} {isk(row['best_sell']):>10} "
            f"{row['net_margin_pct']:>5.1f}% "
            f"{isk(row['profit_per_unit']):>10} "
            f"{row['avg_daily_vol']:>8,} "
            f"{row['buy_orders']:>4}/{row['sell_orders']:<4}  "
            f"{isk(row['daily_isk_potential']):>12}"
        )

        if snap_note:
            print(f"       {' ' * 40}{snap_note}")
        if flags:
            print(f"       {' ' * 40}[!] {' | '.join(flags)}")
        if snap_note or flags:
            print()

    print()
    print("-" * line_w)
    print(f"  Showing top {len(rows)} results sorted by daily ISK potential.")
    print()
    print("  Column guide:")
    print("    Buy/Sell   = current best Jita order prices")
    print("    Net%       = margin after your broker fee + sales tax")
    print("    Profit/u   = ISK profit per unit after fees")
    print("    Vol/day    = avg daily units traded (from market history — may be 1-4 weeks old)")
    print("    Depth B/S  = number of buy/sell orders (higher = harder to manipulate)")
    print("    Daily ISK  = Profit/unit × Vol/day (theoretical max, you won't capture all)")
    print()
    print("  Snapshot data (shown in brackets where available):")
    print("    snap avg   = 14-day average best sell price from intraday snapshots")
    print("    drift      = how much current sell deviates from that average")
    print()
    print("  [!] Flags:")
    print("    HIGH-MARGIN   — net margin >100%; verify the item isn't being manipulated")
    print("    LOW-DEPTH     — fewer than 10 orders; easier for one person to fake the spread")
    print("    VOLATILE      — sell price ranged >40% in snapshot window; unstable")
    print("    PRICE-SPIKE   — current sell is >35% above recent average; may correct down")
    print()
    print("  Tip: Items WITHOUT snapshot data have less manipulation protection.")
    print("       Prefer items with [snap avg] lines and low/no flags for lower risk.")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Jita market opportunity scanner")
    parser.add_argument("--min-margin", type=float, default=MIN_NET_MARGIN_PCT,
                        help=f"Minimum net margin %% (default {MIN_NET_MARGIN_PCT})")
    parser.add_argument("--min-vol",    type=float, default=MIN_AVG_DAILY_VOL,
                        help=f"Minimum avg daily volume (default {MIN_AVG_DAILY_VOL})")
    parser.add_argument("--limit",      type=int,   default=50,
                        help="Max results to show (default 50)")
    args = parser.parse_args()

    rows = run(min_margin=args.min_margin, min_vol=args.min_vol, limit=args.limit)
    print_report(rows, args.min_margin, args.min_vol)
