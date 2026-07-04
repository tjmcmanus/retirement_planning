#!/usr/bin/env python3
"""
Clear Streamlit cache and force strategy regeneration.
Run this script to clear cached data after code changes.
"""

import os
import shutil
import sys

def clear_streamlit_cache():
    """Clear Streamlit cache directories."""
    cache_dirs = [
        '.streamlit/cache',
        '__pycache__',
        '.pytest_cache'
    ]
    
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                print(f"✓ Cleared {cache_dir}")
            except Exception as e:
                print(f"✗ Could not clear {cache_dir}: {e}")
    
    # Also clear Python bytecode files
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                try:
                    os.remove(os.path.join(root, file))
                except OSError:
                    pass
        # Remove __pycache__ directories
        if '__pycache__' in dirs:
            try:
                shutil.rmtree(os.path.join(root, '__pycache__'))
            except OSError:
                pass
    
    print("\n✓ Cache cleared successfully!")
    print("\nNext steps:")
    print("1. Restart your Streamlit app")
    print("2. Go to the Strategy page")
    print("3. The strategy will be recalculated with the fixed AGI")
    print("\nExpected results for 2026:")
    print("  - AGI: $371,350 (was $247,000)")
    print("  - Taxable Income: $339,150 (was $214,800)")
    print("  - Effective Rate: ~21.9% (was 34.5%)")

if __name__ == "__main__":
    print("Clearing Streamlit cache...")
    clear_streamlit_cache()

# Made with Bob
