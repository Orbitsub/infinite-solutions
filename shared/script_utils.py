import time
from datetime import datetime
from functools import wraps

def timed_script(func):
    """Decorator to add timing and headers to scripts."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        script_name = func.__module__.split('.')[-1]
        
        print("=" * 60)
        print(f"{script_name.upper()}")
        print(f"Started: {datetime.now().strftime('%I:%M:%S %p')}")
        print("=" * 60)
        
        start = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            
            print("\n" + "=" * 60)
            print("COMPLETED SUCCESSFULLY")  # Removed checkmark
            print(f"Duration: {format_duration(elapsed)}")
            print(f"Finished: {datetime.now().strftime('%I:%M:%S %p')}")
            print("=" * 60)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start
            
            print("\n" + "=" * 60)
            print("FAILED")  # Removed X mark
            print(f"Error: {e}")
            print(f"Duration: {format_duration(elapsed)}")
            print(f"Finished: {datetime.now().strftime('%I:%M:%S %p')}")
            print("=" * 60)
            
            raise
    
    return wrapper

def format_duration(seconds):
    """Format seconds into readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m ({seconds:.0f}s)"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h ({seconds:.0f}s)"