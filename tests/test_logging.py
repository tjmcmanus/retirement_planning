#!/usr/bin/env python3
"""
Test script to verify logging configuration displays file names and line numbers.
"""
import logging
import os

# Configure logging with the same format as the application
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def test_function():
    """Test function to generate log messages."""
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message - should show file and line number")
    logger.error("This is an error message - should show file and line number")
    
    try:
        # Simulate an exception
        result = 1 / 0
    except ZeroDivisionError as e:
        logger.error(f"Exception occurred: {e}", exc_info=True)

if __name__ == "__main__":
    print("Testing logging configuration...")
    print("=" * 70)
    print("Running with default WARNING level (set LOG_LEVEL=DEBUG to see all)")
    print("=" * 70)
    test_function()
    print("\nLogging test complete!")
    print("\nExpected output format:")
    print("YYYY-MM-DD HH:MM:SS - LEVEL - function_name:line_number - message")

# Made with Bob
