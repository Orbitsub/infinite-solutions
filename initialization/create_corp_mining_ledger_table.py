#!/usr/bin/env python3
"""
Creates the corp_mining_ledger table.
Schema is the raw ESI response from:
  GET /corporation/{corporation_id}/mining/observers/{observer_id}/

One row per mining event exactly as ESI returns it.
observer_id is added since we pull from multiple refineries.
"""

import sqlite3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')


def main():
    print("=" * 60)
    print("CREATE CORP MINING LEDGER TABLE")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Raw ESI fields:
    #   character_id            - who mined
    #   last_updated            - date string from ESI (YYYY-MM-DD)
    #   quantity                - how much
    #   recorded_corporation_id - corp the miner belonged to at time of mining
    #   type_id                 - what was mined
    #
    # We add:
    #   observer_id             - which refinery reported this event
    #   fetched_at              - when WE pulled it from ESI
    #
    # Primary key is the natural composite that uniquely identifies
    # a mining event as ESI sees it.  last_updated is only a date (no time)
    # so multiple events on the same day for the same character/type/observer
    # CAN occur — quantity will differ.  We use ROWID as the true PK and
    # keep a UNIQUE constraint on the full tuple so we don't double-insert
    # the same event on repeated pulls.

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS corp_mining_ledger (
            observer_id             INTEGER NOT NULL,
            character_id            INTEGER NOT NULL,
            recorded_corporation_id INTEGER NOT NULL,
            type_id                 INTEGER NOT NULL,
            quantity                INTEGER NOT NULL,
            last_updated            TEXT    NOT NULL,
            fetched_at              TEXT    NOT NULL,

            UNIQUE (
                observer_id,
                character_id,
                recorded_corporation_id,
                type_id,
                quantity,
                last_updated
            )
        )
    ''')

    # Index on character for "what did player X mine?" queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cml_character
        ON corp_mining_ledger (character_id)
    ''')

    # Index on last_updated for date-range queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cml_date
        ON corp_mining_ledger (last_updated)
    ''')

    # Index on observer for per-refinery queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cml_observer
        ON corp_mining_ledger (observer_id)
    ''')

    # Index on type_id for "how much of X was mined?" queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cml_type
        ON corp_mining_ledger (type_id)
    ''')

    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM corp_mining_ledger")
    row_count = cursor.fetchone()[0]

    cursor.execute('''
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name='corp_mining_ledger'
    ''')
    schema = cursor.fetchone()[0]

    conn.close()

    print(f"\nTable: corp_mining_ledger")
    print(f"Rows:  {row_count}")
    print(f"\nSchema:\n{schema}\n")
    print("=" * 60)
    print("Done. Run update_corp_mining_ledger.py to pull data.")
    print("=" * 60)


if __name__ == '__main__':
    main()