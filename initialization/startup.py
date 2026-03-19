#!/usr/bin/env python3
"""
Runs the full database initialisation sequence:
  1. init_database.py   – creates all tables and views
  2. update_inv_groups.py – populates inv_groups from ESI
  3. update_inv_categories.py – populates inv_categories from ESI
  4. update_inv_meta_groups.py – populates inv_meta_groups from ESI
  5. update_inv_types.py – populates inv_types from jsonl file
  6. update_inv_market_groups.py – populates inv_market_groups from ESI
"""
import subprocess
import sys
import os
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================

INIT_DIR = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ('Initialize database',  'init_database.py'),
    ('Update inv_groups',    'update_inv_groups.py'),
    ('Update inv_categories', 'update_inv_categories.py'),
    ('Update meta_groups',    'update_inv_meta_groups.py'),
    ('Update inv_types',    'update_inv_types.py'),
    ('Update inv_market_groups',    'update_inv_market_groups.py'),
]

# ============================================
# MAIN
# ============================================

def run_step(label, script_name):
    script_path = os.path.join(INIT_DIR, script_name)
    print(f"\n{'=' * 50}")
    print(f"STEP: {label}")
    print(f"Script: {script_name}")
    print(f"{'=' * 50}")

    result = subprocess.run(
        [sys.executable, script_path],
        check=False,
    )

    if result.returncode != 0:
        print(f"\n[ERROR] '{script_name}' exited with code {result.returncode}. Aborting.")
        sys.exit(result.returncode)

    print(f"\n[OK] {label} completed successfully.")


def main():
    start = datetime.now()
    print("=" * 50)
    print("STARTUP SEQUENCE BEGINNING")
    print(f"Started at: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    for label, script in STEPS:
        run_step(label, script)

    elapsed = datetime.now() - start
    print(f"\n{'=' * 50}")
    print("STARTUP SEQUENCE COMPLETE")
    print(f"Total time: {elapsed}")
    print("=" * 50)


if __name__ == '__main__':
    main()
