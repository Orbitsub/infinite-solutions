"""
SCRIPT TEMPLATE - Use this as a starting point for all new scripts
This template includes the @timed_script decorator for consistent logging.
"""
from script_utils import timed_script
import sqlite3
import os
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

# Add your configuration constants here
# Example:
# MY_CONFIG_VALUE = 12345

# ============================================
# HELPER FUNCTIONS
# ============================================

def my_helper_function():
    """
    Add your helper functions here.
    These run without the decorator.
    """
    pass

# ============================================
# MAIN SCRIPT
# ============================================

@timed_script
def main():
    """
    Main script function with automatic timing and error handling.
    
    The @timed_script decorator automatically provides:
    - Script name header
    - Start time
    - Duration tracking
    - Success/failure status
    - Formatted error messages
    - End time
    
    Your code should focus on:
    - Progress reporting (print statements for key milestones)
    - Error handling (raise exceptions, decorator will catch and format)
    - Final summary (print key results at the end)
    """
    
    # Your script logic here
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Main processing logic
        print("Processing data...")
        
        # Example progress reporting
        total_items = 100
        for i in range(1, total_items + 1):
            # Do work here
            
            # Report progress every 10 items
            if i % 10 == 0:
                print(f"Progress: {i}/{total_items} items ({(i/total_items)*100:.1f}%)")
        
        # Commit changes
        conn.commit()
        
        # Final summary (decorator will wrap this with completion message)
        print(f"\nSuccessfully processed {total_items} items")
        
    except Exception as e:
        # Clean up on error
        conn.rollback()
        print(f"Error during processing: {e}")
        raise  # Re-raise so decorator can handle it
        
    finally:
        # Always close connection
        conn.close()

# ============================================
# SCRIPT ENTRY POINT
# ============================================

if __name__ == '__main__':
    main()

# ============================================
# USAGE NOTES
# ============================================
"""
The @timed_script decorator will automatically output:

====================================================
YOUR_SCRIPT_NAME
Started: 02:30:15 PM
====================================================
[Your script's print statements appear here]
====================================================
COMPLETED SUCCESSFULLY
Duration: 5.2m (312s)
Finished: 02:35:27 PM
====================================================

OR if there's an error:

====================================================
YOUR_SCRIPT_NAME
Started: 02:30:15 PM
====================================================
[Your script's print statements appear here]
====================================================
FAILED
Error: [error message]
Duration: 2.1m (126s)
Finished: 02:32:21 PM
====================================================

BEST PRACTICES:
1. Remove manual headers/footers - let @timed_script handle them
2. Focus print statements on progress and key milestones
3. Raise exceptions for errors - decorator will format them nicely
4. Add a brief summary at the end of your main() function
5. Don't manually track timing - decorator does this automatically
"""
