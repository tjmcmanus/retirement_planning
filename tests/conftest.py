"""
conftest.py — pytest configuration for the tests/ directory.

Adds the project root to sys.path so that all test files can import
application modules (strategy, calculations, config, etc.) by name,
regardless of whether pytest is invoked from the project root or
the tests/ subdirectory.
"""
import sys
from pathlib import Path

# Project root is one level up from this file (tests/)
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
