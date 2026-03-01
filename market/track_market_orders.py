"""
track_market_orders.py

Takes price snapshots from the live market_orders table and logs them
to market_price_snapshots for trend analysis. Designed to run after
update_market_orders.py refreshes the order book.

This is how you build the historical price data ESI doesn't provide:
each run captures the best buy price at that moment, so you can average
over days/weeks to see if current prices are elevated or depressed.

Usage:
    python track_market_orders.py                          # take snapshot now
    python track_market_orders.py --report 30              # 30-day spread analysis
    python track_market_orders.py --timeline 34 --days 7   # item price history
    python track_market_orders.py --export spreads.csv --days 90  # export to CSV

Tracked Items:
    Defined in tracked_items.txt (same directory). One type_id per line.
    Item names are resolved automatically from the inv_types table.

Database:
    Reads from:  market_orders          (populated by update_market_orders.py)
    Writes to:   market_price_snapshots (append-only time series)
    Both tables live in mydatabase.db.
"""

import sqlite3
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / 'scripts'))

from script_utils import timed_script

# ─── CONFIG ───────────────────────────────────────────────────────────────────

DB_PATH = str(PROJECT_DIR / 'mydatabase.db')
ITEMS_FILE = PROJECT_DIR / 'scripts' / 'tracked_items.txt'

# ─── LOAD TRACKED ITEMS ──────────────────────────────────────────────────────

def load_tracked_type_ids() -> list[int]:
    """
    Reads tracked_items.txt and returns list of type_ids.
    Skips comments (#) and blank lines.
    """
    type_ids = []
    with open(ITEMS_FILE, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            type_ids.append(int(line))
    return type_ids


def load_bpc_product_type_ids(conn) -> list[int]:
    """
    Gets product type_ids for all blueprints in character_blueprints.
    These are the items produced by our BPOs/BPCs — we need their sell
    prices for the BPC pricing calculator.
    """
    import json

    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT type_id FROM character_blueprints")
    bp_ids = set(r[0] for r in cursor.fetchall())

    if not bp_ids:
        return []

    sde_path = PROJECT_DIR / 'sde' / 'blueprints.jsonl'
    if not sde_path.exists():
        print("  [WARN] sde/blueprints.jsonl not found — skipping BPC product tracking")
        return []

    product_ids = set()
    with open(sde_path, 'r', encoding='utf-8') as f:
        for line in f:
            bp = json.loads(line)
            if bp['blueprintTypeID'] in bp_ids:
                if 'manufacturing' in bp.get('activities', {}):
                    products = bp['activities']['manufacturing'].get('products', [])
                    if products:
                        product_ids.add(products[0]['typeID'])

    return list(product_ids)


def resolve_item_names(conn, type_ids: list[int]) -> dict[int, str]:
    """
    Looks up type_name from inv_types for the given type_ids.
    Returns {type_id: type_name}. Missing IDs fall back to "Type {id}".
    """
    placeholders = ",".join("?" * len(type_ids))
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT type_id, type_name FROM inv_types WHERE type_id IN ({placeholders})",
        type_ids
    )
    names = dict(cursor.fetchall())
    return {tid: names.get(tid, f"Type {tid}") for tid in type_ids}


# ─── DATABASE ─────────────────────────────────────────────────────────────────

def init_db(conn):
    """Creates market_price_snapshots table and indexes if they don't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_price_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            type_id     INTEGER NOT NULL,
            best_buy    REAL,
            best_sell   REAL,
            spread_pct  REAL,
            buy_volume  INTEGER,
            sell_volume INTEGER
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mps_timestamp ON market_price_snapshots(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mps_type      ON market_price_snapshots(type_id)")
    conn.commit()


# ─── SNAPSHOT ─────────────────────────────────────────────────────────────────

def take_snapshot(conn, items: dict[int, str]):
    """
    Queries market_orders for best buy/sell across all tracked items,
    then inserts one snapshot row per item into market_price_snapshots.
    Items with zero orders in the current book are skipped.
    """
    type_ids     = list(items.keys())
    placeholders = ",".join("?" * len(type_ids))
    cursor       = conn.cursor()

    print(f"\n  Snapshotting {len(type_ids)} tracked items from market_orders...")

    # Single query — derives best buy/sell/volume for every tracked item at once
    cursor.execute(f"""
        SELECT
            type_id,
            MAX(CASE WHEN is_buy_order = 1 THEN price END)                     AS best_buy,
            MIN(CASE WHEN is_buy_order = 0 THEN price END)                     AS best_sell,
            SUM(CASE WHEN is_buy_order = 1 THEN volume_remain ELSE 0 END)      AS buy_volume,
            SUM(CASE WHEN is_buy_order = 0 THEN volume_remain ELSE 0 END)      AS sell_volume
        FROM market_orders
        WHERE type_id IN ({placeholders})
        GROUP BY type_id
    """, type_ids)

    rows      = cursor.fetchall()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build insert batch
    inserts = []
    for type_id, best_buy, best_sell, buy_vol, sell_vol in rows:
        spread_pct = ((best_sell - best_buy) / best_buy * 100) if best_buy and best_sell else None
        inserts.append((timestamp, type_id, best_buy, best_sell, spread_pct, buy_vol, sell_vol))

    cursor.executemany("""
        INSERT INTO market_price_snapshots
            (timestamp, type_id, best_buy, best_sell, spread_pct, buy_volume, sell_volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, inserts)
    conn.commit()

    # ── Print summary ──────────────────────────────────────────────────────────
    max_name_len = max((len(items.get(tid, "")) for tid, *_ in rows), default=12)
    max_name_len = max(max_name_len, 12)
    sep_len      = max_name_len + 62

    print(f"  {'-' * sep_len}")
    print(f"  {'Item':<{max_name_len}} {'Best Buy':>12} {'Best Sell':>12} {'Spread %':>10} {'Buy Vol':>12} {'Sell Vol':>12}")
    print(f"  {'-' * sep_len}")

    printed = set()
    for type_id, best_buy, best_sell, buy_vol, sell_vol in rows:
        name   = items.get(type_id, f"Type {type_id}")
        spread = ((best_sell - best_buy) / best_buy * 100) if best_buy and best_sell else 0
        print(f"  {name:<{max_name_len}} {best_buy or 0:>12,.2f} {best_sell or 0:>12,.2f} {spread:>9.2f}% {buy_vol:>12,} {sell_vol:>12,}")
        printed.add(type_id)

    missing = set(items.keys()) - printed
    if missing:
        print(f"  {'-' * sep_len}")
        print(f"  {len(missing)} tracked item(s) had no orders -- skipped.")

    print(f"  {'-' * sep_len}")
    print(f"  {len(inserts)} snapshots saved to market_price_snapshots")


# ─── ANALYSIS ─────────────────────────────────────────────────────────────────

def analyze_spreads(conn, items: dict[int, str], days: int):
    """
    Pulls the last N days of snapshots and calculates average buy/sell/spread.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = conn.cursor()

    max_name_len = max((len(n) for n in items.values()), default=12)
    max_name_len = max(max_name_len, 12)
    sep_len      = max_name_len + 52

    print(f"\n{'=' * (sep_len + 2)}")
    print(f"  AVERAGE BUY/SELL SPREAD ANALYSIS -- Last {days} days (Jita 4-4)")
    print(f"{'=' * (sep_len + 2)}")
    print(f"  {'Item':<{max_name_len}} {'Avg Buy':>12} {'Avg Sell':>12} {'Avg Spread %':>14} {'Snapshots':>12}")
    print(f"  {'-' * sep_len}")

    for type_id, name in sorted(items.items(), key=lambda x: x[1]):
        cursor.execute("""
            SELECT AVG(best_buy), AVG(best_sell), AVG(spread_pct), COUNT(*)
            FROM market_price_snapshots
            WHERE type_id = ? AND timestamp >= ?
              AND best_buy IS NOT NULL AND best_sell IS NOT NULL
        """, (type_id, cutoff))

        row = cursor.fetchone()
        if row and row[3] > 0:
            avg_buy, avg_sell, avg_spread, count = row
            print(f"  {name:<{max_name_len}} {avg_buy:>12,.2f} {avg_sell:>12,.2f} {avg_spread:>13.2f}% {count:>12}")
        else:
            print(f"  {name:<{max_name_len}} {'-- no data --':>40}")

    print(f"  {'-' * sep_len}\n")


def show_timeline(conn, type_id: int, days: int):
    """
    Shows a timeline of best buy/sell for a specific item.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = conn.cursor()

    # Resolve item name from inv_types
    cursor.execute("SELECT type_name FROM inv_types WHERE type_id = ?", (type_id,))
    row       = cursor.fetchone()
    item_name = row[0] if row else f"Type {type_id}"

    cursor.execute("""
        SELECT timestamp, best_buy, best_sell, spread_pct, buy_volume, sell_volume
        FROM market_price_snapshots
        WHERE type_id = ? AND timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT 50
    """, (type_id, cutoff))

    rows = cursor.fetchall()

    if not rows:
        print(f"\n  No snapshot data for {item_name} in the last {days} days.\n")
        return

    print(f"\n{'=' * 90}")
    print(f"  {item_name.upper()} -- Last {len(rows)} snapshots (Jita 4-4)")
    print(f"{'=' * 90}")
    print(f"  {'Timestamp':<20} {'Best Buy':>12} {'Best Sell':>12} {'Spread %':>10} {'Buy Vol':>12} {'Sell Vol':>12}")
    print(f"  {'-' * 80}")

    for ts, buy, sell, spread, bvol, svol in rows:
        ts_short = ts[:16].replace("T", " ")
        print(f"  {ts_short:<20} {buy or 0:>12,.2f} {sell or 0:>12,.2f} {spread or 0:>9.2f}% {bvol or 0:>12,} {svol or 0:>12,}")

    print(f"  {'-' * 80}\n")


# ─── EXPORT ───────────────────────────────────────────────────────────────────

def export_to_csv(filepath: str, conn, items: dict[int, str], days: int):
    """
    Exports snapshots from the last N days to CSV.
    """
    cutoff       = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    type_ids     = list(items.keys())
    placeholders = ",".join("?" * len(type_ids))
    cursor       = conn.cursor()

    cursor.execute(f"""
        SELECT timestamp, type_id, best_buy, best_sell, spread_pct, buy_volume, sell_volume
        FROM market_price_snapshots
        WHERE type_id IN ({placeholders}) AND timestamp >= ?
        ORDER BY timestamp DESC
    """, (*type_ids, cutoff))

    rows = cursor.fetchall()

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "type_id", "item_name", "best_buy",
                         "best_sell", "spread_pct", "buy_volume", "sell_volume"])
        for ts, tid, buy, sell, spread, bvol, svol in rows:
            writer.writerow([ts, tid, items.get(tid, f"Type {tid}"), buy, sell, spread, bvol, svol])

    print(f"\n  Exported {len(rows)} snapshots to {filepath}\n")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

@timed_script
def main():
    parser = argparse.ArgumentParser(
        description="Snapshot and analyze Jita 4-4 best buy/sell prices over time."
    )
    parser.add_argument("--report",   type=int, default=None,  help="Show average spread analysis for last N days")
    parser.add_argument("--timeline", type=int, default=None,  help="Show price history for a specific type_id")
    parser.add_argument("--days",     type=int, default=30,    help="Days window for report/timeline/export (default: 30)")
    parser.add_argument("--export",   type=str, default=None,  help="Export snapshots to CSV filepath")
    args = parser.parse_args()

    # Load tracked items from config file
    type_ids = load_tracked_type_ids()
    if not type_ids:
        print("\n  [ERROR] No type_ids found in tracked_items.txt\n")
        return

    # Connect to database
    conn = sqlite3.connect(DB_PATH, timeout=30)
    init_db(conn)

    # Also track BPC product items (for BPC pricing calculator)
    bpc_product_ids = load_bpc_product_type_ids(conn)
    if bpc_product_ids:
        existing = set(type_ids)
        new_ids = [tid for tid in bpc_product_ids if tid not in existing]
        if new_ids:
            type_ids.extend(new_ids)
            print(f"  + {len(new_ids)} BPC product items added for price tracking")

    # Resolve names from inv_types
    items = resolve_item_names(conn, type_ids)

    # Execute command
    if args.report:
        analyze_spreads(conn, items, args.report)
    elif args.timeline:
        show_timeline(conn, args.timeline, args.days)
    elif args.export:
        export_to_csv(args.export, conn, items, args.days)
    else:
        take_snapshot(conn, items)

    conn.close()


if __name__ == "__main__":
    main()


# ─── USAGE EXAMPLES ───────────────────────────────────────────────────────────
#
# 1. Take a snapshot (normally runs automatically via run_market_updates.py):
#    python track_market_orders.py
#
# 2. Show average buy/sell over the last 30 days:
#    python track_market_orders.py --report 30
#
# 3. See price history for Tritanium (type_id 34) over last 7 days:
#    python track_market_orders.py --timeline 34 --days 7
#
# 4. Export all tracked items to CSV (last 90 days):
#    python track_market_orders.py --export spreads.csv --days 90
#
# ─── ADDING OR CHANGING TRACKED ITEMS ─────────────────────────────────────────
#
# Edit scripts/tracked_items.txt — one type_id per line.
# Names are resolved automatically from the inv_types table.
#
# ─── HOW IT WORKS ─────────────────────────────────────────────────────────────
#
# This script does NOT call ESI. It reads the market_orders table, which is
# refreshed by update_market_orders.py (Jita 4-4 only, location_id 60003760).
#
# Each run: one GROUP BY query extracts best buy/sell for all tracked items,
# then appends one row per item to market_price_snapshots. Over time this
# builds the historical price series that ESI doesn't provide natively.
#
# ─────────────────────────────────────────────────────────────────────────────
