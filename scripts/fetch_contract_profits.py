"""
Fetch character contracts from ESI and calculate estimated profit per contract.
Compares contract sale price against item acquisition costs from wallet_transactions.
"""
from script_utils import timed_script
import sys
import os
import json
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import requests
import sqlite3
from datetime import datetime, timezone, timedelta
from token_manager import get_token

# ============================================
# CONFIGURATION
# ============================================
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'
CHARACTER_ID = 2114278577


def create_table(conn):
    """Create contract_profits table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contract_profits (
            contract_id INTEGER PRIMARY KEY,
            date_completed TEXT,
            customer_name TEXT,
            contract_price REAL,
            estimated_cost REAL,
            broker_fee REAL DEFAULT 0,
            estimated_profit REAL,
            item_count INTEGER,
            items_json TEXT,
            notes TEXT,
            last_updated TEXT
        )
    """)
    conn.commit()


def fetch_contracts(character_id, token):
    """Fetch all contracts for a character from ESI (paginated)."""
    all_contracts = []
    page = 1

    while True:
        url = f'{ESI_BASE_URL}/characters/{character_id}/contracts/'
        headers = {'Authorization': f'Bearer {token}'}
        params = {'page': page}

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            contracts = response.json()
            if not contracts:
                break

            all_contracts.extend(contracts)
            print(f"  Page {page}: {len(contracts)} contracts (total: {len(all_contracts)})")

            x_pages = response.headers.get('x-pages', '1')
            if page >= int(x_pages):
                break

            page += 1
            time.sleep(0.3)
        elif response.status_code == 403:
            print(f"  ERROR 403: Missing ESI scope 'esi-contracts.read_character_contracts.v1'")
            print(f"  You may need to re-authorize with this scope.")
            return []
        else:
            print(f"  Error on page {page}: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            break

    return all_contracts


def fetch_contract_items(character_id, contract_id, token):
    """Fetch items in a specific contract from ESI."""
    url = f'{ESI_BASE_URL}/characters/{character_id}/contracts/{contract_id}/items/'
    headers = {'Authorization': f'Bearer {token}'}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []
    else:
        print(f"    Error fetching items for contract {contract_id}: {response.status_code}")
        return []


def resolve_character_name(character_id):
    """Resolve a character ID to a name via ESI (public endpoint)."""
    url = f'{ESI_BASE_URL}/characters/{character_id}/'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('name', f'Unknown ({character_id})')
    return f'Unknown ({character_id})'


def get_item_name(conn, type_id):
    """Get item name from local database."""
    row = conn.execute(
        "SELECT type_name FROM inv_types WHERE type_id = ?", (type_id,)
    ).fetchone()
    return row[0] if row else f'Type {type_id}'


def get_avg_buy_cost(conn, type_id):
    """
    Get weighted average buy price from wallet_transactions (last 90 days).
    Falls back to market_price_snapshots if no buy history.
    """
    # Try wallet buy history first (90-day window)
    row = conn.execute("""
        SELECT AVG(unit_price) as avg_cost, COUNT(*) as txn_count
        FROM wallet_transactions
        WHERE type_id = ? AND is_buy = 1
          AND date >= datetime('now', '-90 days')
    """, (type_id,)).fetchone()

    if row and row[0] is not None and row[1] > 0:
        return row[0], 'buy_history'

    # Fall back to 7-day avg Jita buy from snapshots
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    row = conn.execute("""
        SELECT AVG(best_buy) as avg_buy
        FROM market_price_snapshots
        WHERE type_id = ? AND timestamp >= ? AND best_buy IS NOT NULL
    """, (type_id, seven_days_ago)).fetchone()

    if row and row[0] is not None:
        return row[0], 'jita_avg'

    return 0, 'unknown'


def format_isk(value):
    """Format ISK values for display."""
    if abs(value) >= 1e9:
        return f"{value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.1f}M"
    if abs(value) >= 1e3:
        return f"{value / 1e3:.1f}k"
    return f"{value:.0f}"


def process_contracts(conn, contracts, token):
    """Process contracts: fetch items, estimate costs, calculate profit."""
    # Get already-processed contract IDs
    existing = set(
        r[0] for r in conn.execute("SELECT contract_id FROM contract_profits").fetchall()
    )

    # Filter to finished item_exchange contracts where we are the issuer (selling)
    # Skip price=0 contracts (transfers to alts/corp members, not sales)
    candidates = [
        c for c in contracts
        if c.get('type') == 'item_exchange'
        and c.get('status') == 'finished'
        and c.get('issuer_id') == CHARACTER_ID
        and c.get('price', 0) > 0
        and c.get('contract_id') not in existing
    ]

    # Also track transfers separately for reference
    transfers = [
        c for c in contracts
        if c.get('type') == 'item_exchange'
        and c.get('status') == 'finished'
        and c.get('issuer_id') == CHARACTER_ID
        and c.get('price', 0) == 0
    ]
    if transfers:
        print(f"\n  (Skipping {len(transfers)} price=0 transfers to alts/corp)")

    if not candidates:
        print("\nNo new contracts to process.")
        return 0

    print(f"\nProcessing {len(candidates)} new contracts...")

    # Cache character name lookups
    name_cache = {}
    new_count = 0

    for i, contract in enumerate(candidates):
        contract_id = contract['contract_id']
        price = contract.get('price', 0)
        date_completed = contract.get('date_completed', contract.get('date_issued', ''))

        # Resolve customer name
        acceptor_id = contract.get('acceptor_id', 0)
        if acceptor_id not in name_cache:
            name_cache[acceptor_id] = resolve_character_name(acceptor_id)
            time.sleep(0.1)
        customer = name_cache[acceptor_id]

        # Fetch contract items
        items = fetch_contract_items(CHARACTER_ID, contract_id, token)
        time.sleep(0.3)

        if not items:
            print(f"  [{i+1}/{len(candidates)}] Contract {contract_id}: no items (skipping)")
            continue

        # Calculate costs for included items (items we gave)
        included_items = [item for item in items if item.get('is_included', False)]
        total_cost = 0
        item_details = []
        unknown_cost_items = 0

        for item in included_items:
            type_id = item['type_id']
            qty = item['quantity']
            name = get_item_name(conn, type_id)
            unit_cost, source = get_avg_buy_cost(conn, type_id)

            line_cost = qty * unit_cost
            total_cost += line_cost

            if source == 'unknown':
                unknown_cost_items += 1

            item_details.append({
                'type_id': type_id,
                'name': name,
                'qty': qty,
                'unit_cost': round(unit_cost, 2),
                'source': source,
            })

        profit = price - total_cost
        notes = f"{unknown_cost_items} items with unknown cost" if unknown_cost_items > 0 else None

        # Insert into database
        conn.execute("""
            INSERT OR REPLACE INTO contract_profits
            (contract_id, date_completed, customer_name, contract_price,
             estimated_cost, estimated_profit, item_count, items_json, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            contract_id,
            date_completed,
            customer,
            price,
            round(total_cost, 2),
            round(profit, 2),
            len(included_items),
            json.dumps(item_details),
            notes,
            datetime.now(timezone.utc).isoformat(),
        ))

        print(f"  [{i+1}/{len(candidates)}] {customer}: {len(included_items)} items, "
              f"price {format_isk(price)}, cost {format_isk(total_cost)}, "
              f"profit {format_isk(profit)}")

        new_count += 1

    conn.commit()
    return new_count


def print_monthly_report(conn, year=None, month=None):
    """Print a profit report for the specified month."""
    now = datetime.now(timezone.utc)
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    month_start = f"{year}-{month:02d}-01"
    if month == 12:
        month_end = f"{year + 1}-01-01"
    else:
        month_end = f"{year}-{month + 1:02d}-01"

    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    month_name = months[month]

    rows = conn.execute("""
        SELECT contract_id, date_completed, customer_name, contract_price,
               estimated_cost, estimated_profit, item_count, notes
        FROM contract_profits
        WHERE date_completed >= ? AND date_completed < ?
        ORDER BY date_completed
    """, (month_start, month_end)).fetchall()

    print(f"\n{'=' * 90}")
    print(f"  {month_name.upper()} {year} CONTRACT PROFIT REPORT")
    print(f"{'=' * 90}")

    if not rows:
        print("  No contract data for this period.")
        print(f"{'=' * 90}")
        return

    print(f"{'Date':<14}{'Customer':<22}{'Items':>6}{'Revenue':>14}{'Cost':>14}{'Profit':>14}")
    print(f"{'-' * 90}")

    total_revenue = 0
    total_cost = 0
    total_profit = 0

    for row in rows:
        _, date_str, customer, price, cost, profit, items, notes = row
        # Parse date for display
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            date_display = dt.strftime('%b %d')
        except (ValueError, AttributeError):
            date_display = str(date_str)[:10]

        customer_display = (customer[:20] + '..') if len(customer) > 20 else customer

        total_revenue += price
        total_cost += cost
        total_profit += profit

        notes_flag = ' *' if notes else ''
        print(f"{date_display:<14}{customer_display:<22}{items:>6}{format_isk(price):>14}"
              f"{format_isk(cost):>14}{format_isk(profit):>14}{notes_flag}")

    print(f"{'-' * 90}")
    print(f"{'TOTALS:':<14}{len(rows)} contracts{'':>8}{format_isk(total_revenue):>14}"
          f"{format_isk(total_cost):>14}{format_isk(total_profit):>14}")

    # Also show market trading profit for context
    market_sells = conn.execute("""
        SELECT SUM(quantity * unit_price) FROM wallet_transactions
        WHERE date >= ? AND date < ? AND is_buy = 0
    """, (month_start, month_end)).fetchone()[0] or 0

    market_buys_avg = conn.execute("""
        WITH sell_types AS (
            SELECT DISTINCT type_id FROM wallet_transactions
            WHERE date >= ? AND date < ? AND is_buy = 0
        ),
        buy_costs AS (
            SELECT wt.type_id, AVG(wt.unit_price) as avg_cost
            FROM wallet_transactions wt
            INNER JOIN sell_types st ON wt.type_id = st.type_id
            WHERE wt.is_buy = 1
            GROUP BY wt.type_id
        ),
        sell_profit AS (
            SELECT wt.type_id,
                   SUM(wt.quantity * wt.unit_price) as revenue,
                   SUM(wt.quantity * COALESCE(bc.avg_cost, 0)) as cost
            FROM wallet_transactions wt
            LEFT JOIN buy_costs bc ON wt.type_id = bc.type_id
            WHERE wt.date >= ? AND wt.date < ? AND wt.is_buy = 0
            GROUP BY wt.type_id
        )
        SELECT SUM(revenue), SUM(cost), SUM(revenue - cost)
        FROM sell_profit
    """, (month_start, month_end, month_start, month_end)).fetchone()

    market_profit = (market_buys_avg[2] or 0) if market_buys_avg else 0

    print(f"\n{'=' * 90}")
    print(f"  COMBINED {month_name.upper()} {year} SUMMARY")
    print(f"{'=' * 90}")
    print(f"  Market trading profit (est):    {format_isk(market_profit):>16} ISK")
    print(f"  Contract profit (est):          {format_isk(total_profit):>16} ISK")
    print(f"  {'-' * 50}")
    print(f"  COMBINED NET PROFIT (est):      {format_isk(market_profit + total_profit):>16} ISK")
    print(f"{'=' * 90}")


@timed_script
def main():
    print("Contract Profit Tracker")
    print("=" * 50)

    # Get ESI token
    print("\nAuthenticating with ESI...")
    token = get_token()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    create_table(conn)

    # Fetch contracts
    print(f"\nFetching contracts for character {CHARACTER_ID}...")
    contracts = fetch_contracts(CHARACTER_ID, token)
    print(f"Total contracts from ESI: {len(contracts)}")

    # Show breakdown
    finished = [c for c in contracts if c.get('status') == 'finished']
    item_exchange = [c for c in finished if c.get('type') == 'item_exchange']
    as_issuer = [c for c in item_exchange if c.get('issuer_id') == CHARACTER_ID]
    print(f"  Finished: {len(finished)}")
    print(f"  Item exchange: {len(item_exchange)}")
    print(f"  As issuer (your sales): {len(as_issuer)}")

    # Process new contracts
    new_count = process_contracts(conn, contracts, token)
    print(f"\nProcessed {new_count} new contracts.")

    # Print monthly report
    print_monthly_report(conn)

    conn.close()


if __name__ == '__main__':
    main()
