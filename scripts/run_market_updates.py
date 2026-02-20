"""
Market Updates Orchestrator
Runs market data updates in optimal order with error handling.
All updates use temporary tables for ZERO DOWNTIME.
"""
import subprocess
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Market data scripts in optimal execution order
SCRIPTS = [
    {
        'name': 'Market Orders Update',
        'file': 'update_market_orders.py',
        'description': 'Updates Jita 4-4 market orders (30-45 min)',
        'critical': True  # If this fails, skip others
    },
    {
        'name': 'Market Price Snapshot',
        'file': 'track_market_orders.py',
        'description': 'Snapshots best buy/sell for tracked items (<1 min)',
        'critical': False
    },
    {
        'name': 'Breakeven Cache Refresh',
        'file': 'refresh_breakeven_cache.py',
        'description': 'Recalculates profit margins (<1 min)',
        'critical': False
    },
    {
        'name': 'BWF-ZZ Market Orders Update',
        'file': 'update_bwf_market_orders.py',
        'description': 'Updates BWF-ZZ Market Orders (25-30 min)',
        'critical': False
    }
]

def log_message(message):
    """Print message with timestamp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def log_separator(char='=', length=70):
    """Print a separator line."""
    print(char * length)

def run_script(script_info):
    """
    Run a script and return success status.
    Captures output and displays it in real-time.
    """
    script_name = script_info['name']
    script_file = script_info['file']
    script_path = os.path.join(SCRIPT_DIR, script_file)
    
    log_separator()
    log_message(f"STARTING: {script_name}")
    log_separator()
    log_message(f"Description: {script_info['description']}")
    log_message(f"Script: {script_file}")
    log_separator()
    
    start_time = datetime.now()
    
    try:
        # Run the script with real-time output
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # Print the script's output
        if result.stdout:
            print(result.stdout)
        
        # Check for errors
        if result.returncode != 0:
            log_message(f"[ERROR] ERROR in {script_name}:")
            if result.stderr:
                print(result.stderr)
            return False
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        log_separator()
        log_message(f"[OK] SUCCESS: {script_name} (Duration: {duration})")
        log_separator()
        return True
        
    except Exception as e:
        log_message(f"[ERROR] FAILED to run {script_name}: {e}")
        return False

def main():
    """
    Main orchestrator function.
    Runs all market update scripts in sequence.
    """
    overall_start = datetime.now()
    
    log_separator('=', 70)
    log_message("MARKET UPDATES - ORCHESTRATOR (ZERO DOWNTIME MODE)")
    log_separator('=', 70)
    log_message("All scripts use temporary tables - production stays live!")
    log_separator('=', 70)
    
    results = {}
    
    for script_info in SCRIPTS:
        script_name = script_info['name']
        
        # Run the script
        success = run_script(script_info)
        results[script_name] = success
        
        # If a critical script fails, stop execution
        if not success and script_info.get('critical', False):
            log_message(f"[WARNING] CRITICAL FAILURE in {script_name}")
            log_message("[WARNING] Skipping remaining scripts")
            break
        
        # Add spacing between scripts
        print("\n")
    
    # Print summary
    overall_end = datetime.now()
    overall_duration = overall_end - overall_start
    
    log_separator('=', 70)
    log_message("MARKET UPDATES - SUMMARY")
    log_separator('=', 70)
    log_message(f"Total Duration: {overall_duration}")
    log_message(f"Start Time: {overall_start.strftime('%Y-%m-%d %H:%M:%S')}")
    log_message(f"End Time: {overall_end.strftime('%Y-%m-%d %H:%M:%S')}")
    log_separator('-', 70)
    
    # Results table
    log_message("Results:")
    for script_name, success in results.items():
        status = "[OK] SUCCESS" if success else "[ERROR] FAILED"
        log_message(f"  {script_name}: {status}")
    
    log_separator('=', 70)
    
    # Calculate success rate
    total_scripts = len(results)
    successful_scripts = sum(1 for success in results.values() if success)
    
    log_message(f"Success Rate: {successful_scripts}/{total_scripts} scripts completed")
    
    if all(results.values()):
        log_message("[OK] ALL UPDATES COMPLETED SUCCESSFULLY!")
    elif any(results.values()):
        log_message("[WARNING] PARTIAL SUCCESS - Some updates completed")
    else:
        log_message("[ERROR] ALL UPDATES FAILED")
    
    log_separator('=', 70)
    
    # Exit with appropriate code
    if not all(results.values()):
        sys.exit(1)

if __name__ == '__main__':
    main()