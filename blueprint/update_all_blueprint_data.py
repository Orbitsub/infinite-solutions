"""
Master script to update all blueprint-related data.
Runs:
1. Fetch latest blueprints from ESI
2. Update blueprint_data.js (deduplicated BPOs)
3. Update bpc_data.js (BPCs with quantity aggregation)
4. Update research_jobs.js (active research)
5. Update blueprint product mapping table
6. Update BPC pricing data
7. Update index_final.html (embedded data)
8. Copy index_final.html -> index.html, commit & push to GitHub

Run this script daily via Windows Task Scheduler.
"""
import subprocess
import sys
import os
import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
LOG_FILE = os.path.join(SCRIPT_DIR, 'logs', 'blueprint_updates.log')
ENABLE_GITHUB_COMMIT = False

def log(message):
    """Log message to both console and file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    print(log_message)

    # Ensure logs directory exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_message + '\n')

def run_script(script_name, description):
    """Run a Python script and return success status."""
    log(f"Running: {description}...")

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, script_name)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            log(f"  [OK] {description} completed successfully")
            return True
        else:
            log(f"  [ERROR] {description} failed:")
            log(f"  {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        log(f"  [ERROR] {description} timed out")
        return False
    except Exception as e:
        log(f"  [ERROR] {description} failed: {e}")
        return False

def main():
    log("="*70)
    log("AUTOMATED BLUEPRINT DATA UPDATE - STARTING")
    log("="*70)

    success_count = 0
    total_steps = 7

    # Step 1: Fetch blueprints from ESI
    if run_script('fetch_blueprints.py', 'Fetch blueprints from ESI'):
        success_count += 1

    # Step 2: Update blueprint_data.js (deduplicated BPOs)
    if run_script('update_blueprint_data_js.py', 'Update blueprint_data.js'):
        success_count += 1

    # Step 3: Update bpc_data.js (BPCs with quantity aggregation)
    if run_script('update_bpc_data_js.py', 'Update bpc_data.js'):
        success_count += 1

    # Step 4: Update research_jobs.js (active research)
    if run_script('update_research_jobs.py', 'Update research_jobs.js'):
        success_count += 1

    # Step 5: Update blueprint -> product mapping
    if run_script('update_blueprint_product_mapping.py', 'Update blueprint product mapping table'):
        success_count += 1

    # Step 6: Update BPC pricing data (quality-based pricing)
    if run_script('generate_bpc_pricing_data.py', 'Update BPC pricing data'):
        success_count += 1

    # Step 7: Update index_final.html (embedded data)
    if run_script(os.path.join('..', 'update_html_data.py'), 'Update embedded_data.js'):
        success_count += 1

    # Step 7: Copy index_final.html -> index.html and push to GitHub
    if success_count >= 4:  # Only push if most steps succeeded
        try:
            log("Copying index_final.html -> index.html...")
            shutil.copy2(
                os.path.join(PROJECT_DIR, 'index_final.html'),
                os.path.join(PROJECT_DIR, 'index.html')
            )

            if ENABLE_GITHUB_COMMIT:
                log("Committing and pushing to GitHub...")
                files_to_add = [
                    'index.html', 'index_final.html',
                    'assets/blueprint_data.js', 'assets/bpc_data.js',
                    'assets/bpc_pricing_data.js', 'assets/research_jobs.js',
                    'assets/embedded_data.js'
                ]
                subprocess.run(
                    ['git', 'add'] + files_to_add,
                    cwd=PROJECT_DIR, check=True, capture_output=True
                )

                # Check if there are actually changes to commit
                diff_result = subprocess.run(
                    ['git', 'diff', '--cached', '--quiet'],
                    cwd=PROJECT_DIR, capture_output=True
                )
                if diff_result.returncode == 0:
                    log("  [OK] No changes to commit (data unchanged)")
                else:
                    commit_msg = f"Auto-update blueprint data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    subprocess.run(
                        ['git', 'commit', '-m', commit_msg],
                        cwd=PROJECT_DIR, check=True, capture_output=True
                    )
                    subprocess.run(
                        ['git', 'push'],
                        cwd=PROJECT_DIR, check=True, capture_output=True
                    )
                    log(f"  [OK] Pushed to GitHub: {commit_msg}")
                    success_count += 1
                    total_steps += 1
            else:
                log("Skipping GitHub commit/push step (ENABLE_GITHUB_COMMIT=False)")

        except subprocess.CalledProcessError as e:
            log(f"  [ERROR] Git operation failed: {e}")
        except Exception as e:
            log(f"  [ERROR] Deploy step failed: {e}")
    else:
        log("Skipping deploy — too many update steps failed")

    log("="*70)
    if success_count >= total_steps:
        log(f"UPDATE COMPLETED SUCCESSFULLY ({success_count}/{total_steps} steps)")
    else:
        log(f"UPDATE COMPLETED WITH ERRORS ({success_count}/{total_steps} steps succeeded)")
    log("="*70)

    return 0 if success_count >= total_steps else 1

if __name__ == '__main__':
    sys.exit(main())
