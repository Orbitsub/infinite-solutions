"""
init_database.py
Creates all tables and views in mydatabase.db from scratch.
"""

import sqlite3
import os
import sys
from datetime import datetime

# ============================================
# PATHS
# ============================================

INIT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(INIT_DIR))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')

# ============================================
# TABLE DEFINITIONS
# ============================================

# Each entry: (table_name, DDL_string)
# Grouped by category for readability.

TABLES = []

# ------------------------------------------------------------------
# SDE / Static Reference Data
# (populated by scripts/run_static_updates.py via ESI)
# ------------------------------------------------------------------

TABLES += [
    ("inv_types", """
        CREATE TABLE IF NOT EXISTS inv_types (
            type_id         INTEGER PRIMARY KEY,
            group_id        INTEGER,
            type_name       TEXT,
            description     TEXT,
            mass            REAL,
            volume          REAL,
            capacity        REAL,
            portion_size    INTEGER,
            race_id         INTEGER,
            base_price      REAL,
            published       INTEGER,
            market_group_id INTEGER,
            icon_id         INTEGER,
            sound_id        INTEGER,
            graphic_id      INTEGER
        )
    """),

    ("inv_groups", """
        CREATE TABLE IF NOT EXISTS inv_groups (
            group_id                INTEGER PRIMARY KEY,
            category_id             INTEGER,
            group_name              TEXT,
            icon_id                 INTEGER,
            use_base_price          INTEGER,
            anchored                INTEGER,
            anchorable              INTEGER,
            fittable_non_singleton  INTEGER,
            published               INTEGER
        )
    """),

    ("inv_categories", """
        CREATE TABLE IF NOT EXISTS inv_categories (
            category_id     INTEGER PRIMARY KEY,
            category_name   TEXT,
            icon_id         INTEGER,
            published       INTEGER
        )
    """),

    ("inv_market_groups", """
        CREATE TABLE IF NOT EXISTS inv_market_groups (
            market_group_id  INTEGER PRIMARY KEY,
            parent_group_id  INTEGER,
            market_group_name TEXT,
            description      TEXT,
            icon_id          INTEGER,
            has_types        INTEGER
        )
    """),

    ("inv_meta_groups", """
        CREATE TABLE IF NOT EXISTS inv_meta_groups (
            meta_group_id   INTEGER PRIMARY KEY,
            meta_group_name TEXT,
            description     TEXT,
            icon_id         INTEGER
        )
    """),

    # Packaged volumes – populated by import_packaged_volumes_csv.py
    ("sde_types", """
        CREATE TABLE IF NOT EXISTS sde_types (
            type_id          INTEGER PRIMARY KEY,
            packaged_volume  REAL,
            last_updated     TEXT
        )
    """),

    # Universe entity cache (characters, corps, alliances, factions)
    ("universe_entities", """
        CREATE TABLE IF NOT EXISTS universe_entities (
            entity_id    INTEGER PRIMARY KEY,
            entity_type  TEXT NOT NULL,
            entity_name  TEXT,
            description  TEXT,
            ticker       TEXT,
            last_updated TEXT
        )
    """),

    # Station / structure name cache
    ("stations", """
        CREATE TABLE IF NOT EXISTS stations (
            location_id  INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            type         TEXT,
            last_updated TEXT
        )
    """),
]

# ------------------------------------------------------------------
# Character / Wallet data
# ------------------------------------------------------------------

TABLES += [
    ("wallet_journal", """
        CREATE TABLE IF NOT EXISTS wallet_journal (
            id                INTEGER PRIMARY KEY,
            character_id      INTEGER NOT NULL,
            date              TEXT NOT NULL,
            ref_type          TEXT,
            amount            REAL,
            balance           REAL,
            description       TEXT,
            first_party_id    INTEGER,
            second_party_id   INTEGER,
            reason            TEXT,
            tax               REAL,
            tax_receiver_id   INTEGER,
            context_id        INTEGER,
            context_id_type   TEXT
        )
    """),

    ("wallet_transactions", """
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            transaction_id  INTEGER PRIMARY KEY,
            character_id    INTEGER NOT NULL,
            date            TEXT NOT NULL,
            type_id         INTEGER NOT NULL,
            location_id     INTEGER NOT NULL,
            quantity        INTEGER NOT NULL,
            unit_price      REAL NOT NULL,
            client_id       INTEGER,
            is_buy          INTEGER NOT NULL,
            is_personal     INTEGER NOT NULL,
            journal_ref_id  INTEGER,
            last_updated    TEXT
        )
    """),

    ("character_orders", """
        CREATE TABLE IF NOT EXISTS character_orders (
            order_id        INTEGER PRIMARY KEY,
            character_id    INTEGER NOT NULL,
            type_id         INTEGER NOT NULL,
            region_id       INTEGER,
            location_id     INTEGER NOT NULL,
            is_buy_order    INTEGER NOT NULL,
            is_corporation  INTEGER NOT NULL DEFAULT 0,
            price           REAL NOT NULL,
            volume_total    INTEGER NOT NULL,
            volume_remain   INTEGER NOT NULL,
            issued          TEXT NOT NULL,
            duration        INTEGER NOT NULL,
            escrow          REAL,
            min_volume      INTEGER DEFAULT 1,
            range           TEXT,
            state           TEXT,
            last_updated    TEXT
        )
    """),

    ("character_orders_history", """
        CREATE TABLE IF NOT EXISTS character_orders_history (
            snapshot_date   TEXT NOT NULL,
            order_id        INTEGER NOT NULL,
            character_id    INTEGER NOT NULL,
            type_id         INTEGER NOT NULL,
            location_id     INTEGER NOT NULL,
            region_id       INTEGER NOT NULL,
            is_buy_order    INTEGER NOT NULL,
            price           REAL NOT NULL,
            volume_remain   INTEGER NOT NULL,
            volume_total    INTEGER NOT NULL,
            issued          TEXT NOT NULL,
            duration        INTEGER NOT NULL,
            state           TEXT NOT NULL,
            PRIMARY KEY (snapshot_date, order_id)
        )
    """),

    ("character_skills", """
        CREATE TABLE IF NOT EXISTS character_skills (
            character_id        INTEGER NOT NULL,
            skill_id            INTEGER NOT NULL,
            active_skill_level  INTEGER NOT NULL,
            trained_skill_level INTEGER NOT NULL,
            last_updated        TEXT NOT NULL,
            PRIMARY KEY (character_id, skill_id)
        )
    """),

    ("character_standings", """
        CREATE TABLE IF NOT EXISTS character_standings (
            character_id  INTEGER NOT NULL,
            from_type     TEXT NOT NULL,
            from_id       INTEGER NOT NULL,
            standing      REAL NOT NULL,
            last_updated  TEXT NOT NULL,
            PRIMARY KEY (character_id, from_type, from_id)
        )
    """),

    ("character_blueprints", """
        CREATE TABLE IF NOT EXISTS character_blueprints (
            item_id           INTEGER PRIMARY KEY,
            type_id           INTEGER NOT NULL,
            type_name         TEXT,
            location_id       INTEGER,
            location_flag     TEXT,
            quantity          INTEGER NOT NULL DEFAULT 1,
            time_efficiency   INTEGER NOT NULL DEFAULT 0,
            material_efficiency INTEGER NOT NULL DEFAULT 0,
            runs              INTEGER NOT NULL DEFAULT -1,
            last_updated      TEXT NOT NULL
        )
    """),
]

# ------------------------------------------------------------------
# Market data
# ------------------------------------------------------------------

TABLES += [
    # Long-term history — populated by update_market_history*.py
    # (market_orders table is created/replaced by update_market_orders.py)
    ("market_history", """
        CREATE TABLE IF NOT EXISTS market_history (
            type_id      INTEGER NOT NULL,
            region_id    INTEGER NOT NULL,
            date         TEXT NOT NULL,
            average      REAL,
            highest      REAL,
            lowest       REAL,
            order_count  INTEGER,
            volume       INTEGER,
            PRIMARY KEY (type_id, region_id, date)
        )
    """),

    ("market_history_tracking", """
        CREATE TABLE IF NOT EXISTS market_history_tracking (
            type_id            INTEGER PRIMARY KEY,
            first_loaded_date  TEXT,
            last_updated_date  TEXT,
            is_priority        INTEGER DEFAULT 1,
            needs_backfill     INTEGER DEFAULT 0
        )
    """),

    ("market_price_snapshots", """
        CREATE TABLE IF NOT EXISTS market_price_snapshots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            type_id      INTEGER NOT NULL,
            best_buy     REAL,
            best_sell    REAL,
            spread_pct   REAL,
            buy_volume   INTEGER,
            sell_volume  INTEGER
        )
    """),

    # Items to watch / trade (core config table for the site)
    ("tracked_market_items", """
        CREATE TABLE IF NOT EXISTS tracked_market_items (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            type_id           INTEGER NOT NULL UNIQUE,
            type_name         TEXT NOT NULL,
            category          TEXT NOT NULL DEFAULT 'other',
            display_order     INTEGER NOT NULL DEFAULT 0,
            price_percentage  INTEGER NOT NULL DEFAULT 100,
            alliance_discount INTEGER NOT NULL DEFAULT 0,
            buyback_accepted  INTEGER NOT NULL DEFAULT 1,
            buyback_rate      INTEGER,
            buyback_quota     INTEGER NOT NULL DEFAULT 0
        )
    """),
]

# ------------------------------------------------------------------
# Inventory / Assets
# ------------------------------------------------------------------

TABLES += [
    ("lx_zoj_inventory", """
        CREATE TABLE IF NOT EXISTS lx_zoj_inventory (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_timestamp TEXT NOT NULL,
            type_id            INTEGER NOT NULL,
            type_name          TEXT,
            quantity           INTEGER NOT NULL DEFAULT 0,
            location_id        INTEGER,
            location_name      TEXT
        )
    """),

    ("jita_hangar_inventory", """
        CREATE TABLE IF NOT EXISTS jita_hangar_inventory (
            item_id       INTEGER PRIMARY KEY,
            type_id       INTEGER NOT NULL,
            location_id   INTEGER NOT NULL,
            location_flag TEXT NOT NULL,
            quantity      INTEGER NOT NULL,
            is_singleton  INTEGER NOT NULL,
            last_updated  TEXT NOT NULL
        )
    """),
]

# ------------------------------------------------------------------
# Blueprints / Industry
# ------------------------------------------------------------------

TABLES += [
    ("blueprint_category_overrides", """
        CREATE TABLE IF NOT EXISTS blueprint_category_overrides (
            type_id     INTEGER PRIMARY KEY,
            category    TEXT NOT NULL,
            subcategory TEXT,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """),

    ("hidden_blueprints", """
        CREATE TABLE IF NOT EXISTS hidden_blueprints (
            type_id INTEGER NOT NULL,
            me      INTEGER NOT NULL DEFAULT 0,
            te      INTEGER NOT NULL DEFAULT 0,
            runs    INTEGER NOT NULL DEFAULT -1,
            PRIMARY KEY (type_id, me, te, runs)
        )
    """),

    ("type_materials", """
        CREATE TABLE IF NOT EXISTS type_materials (
            type_id        INTEGER PRIMARY KEY,
            materials_json TEXT NOT NULL
        )
    """),
]

# ------------------------------------------------------------------
# Doctrine fits
# ------------------------------------------------------------------

TABLES += [
    ("doctrine_fits", """
        CREATE TABLE IF NOT EXISTS doctrine_fits (
            fit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            fit_name  TEXT NOT NULL UNIQUE,
            ship_type TEXT,
            created_at TEXT NOT NULL
        )
    """),

    ("doctrine_fit_items", """
        CREATE TABLE IF NOT EXISTS doctrine_fit_items (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            fit_id   INTEGER NOT NULL,
            type_id  INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (fit_id) REFERENCES doctrine_fits (fit_id)
        )
    """),

    ("doctrine_items", """
        CREATE TABLE IF NOT EXISTS doctrine_items (
            type_id      INTEGER PRIMARY KEY,
            last_updated TEXT NOT NULL
        )
    """),
]

# ------------------------------------------------------------------
# Contracts
# ------------------------------------------------------------------

TABLES += [
    ("contract_profits", """
        CREATE TABLE IF NOT EXISTS contract_profits (
            contract_id     INTEGER PRIMARY KEY,
            date_completed  TEXT,
            customer_name   TEXT,
            contract_price  REAL,
            estimated_cost  REAL,
            broker_fee      REAL DEFAULT 0,
            estimated_profit REAL,
            item_count      INTEGER,
            items_json      TEXT,
            notes           TEXT,
            last_updated    TEXT
        )
    """),
]

# ------------------------------------------------------------------
# Corporation data
# ------------------------------------------------------------------

TABLES += [
    ("corp_members", """
        CREATE TABLE IF NOT EXISTS corp_members (
            character_id    INTEGER PRIMARY KEY,
            character_name  TEXT NOT NULL,
            corporation_id  INTEGER NOT NULL,
            alliance_id     INTEGER,
            faction_id      INTEGER,
            birthday        TEXT,
            gender          TEXT,
            race_id         INTEGER,
            bloodline_id    INTEGER,
            ancestry_id     INTEGER,
            security_status REAL,
            title           TEXT,
            last_updated    TEXT
        )
    """),

    ("corp_mining_ledger", """
        CREATE TABLE IF NOT EXISTS corp_mining_ledger (
            observer_id             INTEGER NOT NULL,
            character_id            INTEGER NOT NULL,
            recorded_corporation_id INTEGER NOT NULL,
            type_id                 INTEGER NOT NULL,
            quantity                INTEGER NOT NULL,
            last_updated            TEXT NOT NULL,
            fetched_at              TEXT NOT NULL,
            UNIQUE (
                observer_id, character_id, recorded_corporation_id,
                type_id, quantity, last_updated
            )
        )
    """),

    ("corp_killmails", """
        CREATE TABLE IF NOT EXISTS corp_killmails (
            killmail_id     INTEGER PRIMARY KEY,
            killmail_time   TEXT NOT NULL,
            character_id    INTEGER,
            corporation_id  INTEGER NOT NULL,
            alliance_id     INTEGER,
            ship_type_id    INTEGER NOT NULL,
            solar_system_id INTEGER NOT NULL,
            is_corp_loss    INTEGER NOT NULL,
            damage_taken    INTEGER,
            num_attackers   INTEGER,
            total_value     REAL,
            last_updated    TEXT
        )
    """),

    ("corp_killmail_items", """
        CREATE TABLE IF NOT EXISTS corp_killmail_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            killmail_id  INTEGER NOT NULL,
            type_id      INTEGER NOT NULL,
            quantity     INTEGER NOT NULL,
            flag         TEXT,
            destroyed    INTEGER NOT NULL,
            FOREIGN KEY (killmail_id) REFERENCES corp_killmails (killmail_id)
        )
    """),
]

# ------------------------------------------------------------------
# Raw killmail data (zKillboard / ESI)
# ------------------------------------------------------------------

TABLES += [
    ("raw_killmails", """
        CREATE TABLE IF NOT EXISTS raw_killmails (
            killmail_id         INTEGER PRIMARY KEY,
            killmail_time       TEXT NOT NULL,
            solar_system_id     INTEGER,
            moon_id             INTEGER,
            war_id              INTEGER,
            zkb_location_id     INTEGER,
            zkb_hash            TEXT,
            zkb_fitted_value    REAL,
            zkb_dropped_value   REAL,
            zkb_destroyed_value REAL,
            zkb_total_value     REAL,
            zkb_points          INTEGER,
            zkb_npc             INTEGER,
            zkb_solo            INTEGER,
            zkb_awox            INTEGER,
            zkb_labels          TEXT,
            last_updated        TEXT
        )
    """),

    ("raw_killmail_victims", """
        CREATE TABLE IF NOT EXISTS raw_killmail_victims (
            killmail_id     INTEGER PRIMARY KEY,
            character_id    INTEGER,
            corporation_id  INTEGER,
            alliance_id     INTEGER,
            faction_id      INTEGER,
            ship_type_id    INTEGER,
            damage_taken    INTEGER,
            position_x      REAL,
            position_y      REAL,
            position_z      REAL,
            FOREIGN KEY (killmail_id) REFERENCES raw_killmails (killmail_id)
        )
    """),

    ("raw_killmail_attackers", """
        CREATE TABLE IF NOT EXISTS raw_killmail_attackers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            killmail_id     INTEGER NOT NULL,
            character_id    INTEGER,
            corporation_id  INTEGER,
            alliance_id     INTEGER,
            faction_id      INTEGER,
            ship_type_id    INTEGER,
            weapon_type_id  INTEGER,
            damage_done     INTEGER,
            final_blow      INTEGER,
            security_status REAL,
            FOREIGN KEY (killmail_id) REFERENCES raw_killmails (killmail_id)
        )
    """),

    ("raw_killmail_items", """
        CREATE TABLE IF NOT EXISTS raw_killmail_items (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            killmail_id         INTEGER NOT NULL,
            item_type_id        INTEGER,
            flag                INTEGER,
            quantity_destroyed  INTEGER,
            quantity_dropped    INTEGER,
            singleton           INTEGER,
            FOREIGN KEY (killmail_id) REFERENCES raw_killmails (killmail_id)
        )
    """),
]

# ------------------------------------------------------------------
# Site config
# ------------------------------------------------------------------

TABLES += [
    ("site_config", """
        CREATE TABLE IF NOT EXISTS site_config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """),
]


# ============================================
# VIEW DEFINITIONS
# ============================================

VIEWS = [
    # Latest snapshot of LX-ZOJ inventory per type
    ("lx_zoj_current_inventory", """
        CREATE VIEW IF NOT EXISTS lx_zoj_current_inventory AS
        SELECT type_id, type_name, quantity, location_id, location_name,
               snapshot_timestamp
        FROM lx_zoj_inventory
        WHERE snapshot_timestamp = (
            SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory
        )
    """),
]


# ============================================
# INDEX DEFINITIONS
# ============================================

INDEXES = [
    # corp_mining_ledger
    "CREATE INDEX IF NOT EXISTS idx_cml_character    ON corp_mining_ledger (character_id)",
    "CREATE INDEX IF NOT EXISTS idx_cml_date         ON corp_mining_ledger (last_updated)",

    # market_history
    "CREATE INDEX IF NOT EXISTS idx_mh_type_region   ON market_history (type_id, region_id)",
    "CREATE INDEX IF NOT EXISTS idx_mh_date          ON market_history (date)",

    # wallet_journal
    "CREATE INDEX IF NOT EXISTS idx_wj_character     ON wallet_journal (character_id)",
    "CREATE INDEX IF NOT EXISTS idx_wj_date          ON wallet_journal (date)",
    "CREATE INDEX IF NOT EXISTS idx_wj_ref_type      ON wallet_journal (ref_type)",

    # wallet_transactions
    "CREATE INDEX IF NOT EXISTS idx_wt_character     ON wallet_transactions (character_id)",
    "CREATE INDEX IF NOT EXISTS idx_wt_date          ON wallet_transactions (date)",
    "CREATE INDEX IF NOT EXISTS idx_wt_type          ON wallet_transactions (type_id)",

    # character_orders
    "CREATE INDEX IF NOT EXISTS idx_co_character     ON character_orders (character_id)",
    "CREATE INDEX IF NOT EXISTS idx_co_type          ON character_orders (type_id)",

    # lx_zoj_inventory
    "CREATE INDEX IF NOT EXISTS idx_lz_snapshot      ON lx_zoj_inventory (snapshot_timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_lz_type          ON lx_zoj_inventory (type_id)",

    # raw killmails
    "CREATE INDEX IF NOT EXISTS idx_rkm_time         ON raw_killmails (killmail_time)",
    "CREATE INDEX IF NOT EXISTS idx_rka_killmail     ON raw_killmail_attackers (killmail_id)",
    "CREATE INDEX IF NOT EXISTS idx_rki_killmail     ON raw_killmail_items (killmail_id)",

    # doctrine
    "CREATE INDEX IF NOT EXISTS idx_dfi_fit          ON doctrine_fit_items (fit_id)",
    "CREATE INDEX IF NOT EXISTS idx_dfi_type         ON doctrine_fit_items (type_id)",

    # tracked items lookup
    "CREATE INDEX IF NOT EXISTS idx_tmi_type         ON tracked_market_items (type_id)",
    "CREATE INDEX IF NOT EXISTS idx_tmi_category     ON tracked_market_items (category)",

    # market_price_snapshots
    "CREATE INDEX IF NOT EXISTS idx_mps_type_ts      ON market_price_snapshots (type_id, timestamp)",
]


# ============================================
# MAIN
# ============================================

def init_database(db_path=DB_PATH):
    is_new = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cursor = conn.cursor()

    created_tables  = []
    existing_tables = []
    created_views   = []
    created_indexes = []

    # --- Tables ---
    for name, ddl in TABLES:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
        exists = cursor.fetchone() is not None
        cursor.execute(ddl)
        if exists:
            existing_tables.append(name)
        else:
            created_tables.append(name)

    # --- Views ---
    for name, ddl in VIEWS:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='view' AND name=?", (name,))
        exists = cursor.fetchone() is not None
        cursor.execute(ddl)
        if not exists:
            created_views.append(name)

    # --- Indexes ---
    for ddl in INDEXES:
        cursor.execute(ddl)
        # Extract index name for reporting
        name = ddl.split("idx_")[1].split(" ")[0] if "idx_" in ddl else "?"
        created_indexes.append("idx_" + name)

    conn.commit()
    conn.close()

    # --- Summary ---
    print("=" * 60)
    print("DATABASE INITIALIZATION COMPLETE")
    print("=" * 60)
    print(f"Database : {db_path}")
    print(f"Status   : {'Created new' if is_new else 'Updated existing'}")
    print()

    if created_tables:
        print(f"[+] Created {len(created_tables)} new table(s):")
        for t in created_tables:
            print(f"      {t}")
    if existing_tables:
        print(f"[=] Skipped {len(existing_tables)} existing table(s) (data preserved):")
        for t in existing_tables:
            print(f"      {t}")
    if created_views:
        print(f"[+] Created {len(created_views)} view(s):")
        for v in created_views:
            print(f"      {v}")
    print(f"[+] Ensured {len(created_indexes)} index(es)")

if __name__ == '__main__':
    init_database()
