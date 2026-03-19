import subprocess
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Only static/reference data
SCRIPTS = [
    'update_inv_types.py',
    'update_inv_categories.py',
    'update_inv_groups.py',
    'update_inv_market_groups.py',
    'update_inv_meta_groups.py'
]

def main():
    print("=" * 60)
    print(f"Starting static data update - {datetime.now()}")
    print("=" * 60)
    
    for script in SCRIPTS:
        script_path = os.path.join(SCRIPT_DIR, script)
        print(f"\nRunning: {script}")
        
        try:
            result = subprocess.run(['python', script_path], capture_output=True, text=True)
            print(result.stdout)
            if result.returncode != 0:
                print(f"ERROR: {result.stderr}")
        except Exception as e:
            print(f"ERROR: {e}")
    
    print(f"\n✓ Static updates complete - {datetime.now()}")

if __name__ == '__main__':
    main()