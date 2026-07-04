"""
set_target_allocation.py
========================
CLI helper to set the target portfolio allocation for rebalancing.

This is a thin command-line wrapper around the functions in
components/rebalancing_cache.py.  Run it from the project root so that
the components package is on the Python path.

Usage:
    python scripts/set_target_allocation.py 10 30 60
    python scripts/set_target_allocation.py          # interactive
"""
import sys
import logging
from pathlib import Path

# Ensure project root is on the path when script is run directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.rebalancing_cache import set_target_allocation, get_target_allocation  # noqa: E402

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    if len(sys.argv) == 4:
        cash = float(sys.argv[1])
        bonds = float(sys.argv[2])
        stocks = float(sys.argv[3])

        print(f"Setting target allocation: {cash}% cash, {bonds}% bonds, {stocks}% stocks")
        success = set_target_allocation(cash, bonds, stocks)

        if success:
            print("✅ Target allocation set successfully")
            sys.exit(0)
        else:
            print("❌ Failed to set target allocation")
            sys.exit(1)
    else:
        print("Set Target Portfolio Allocation")
        print("=" * 40)

        try:
            cash = float(input("Cash percentage (0-100): "))
            bonds = float(input("Bonds percentage (0-100): "))
            stocks = float(input("Stocks percentage (0-100): "))
            threshold = float(input("Drift threshold percentage (default 5.0): ") or "5.0")

            print(f"\nSetting target allocation:")
            print(f"  Cash:   {cash}%")
            print(f"  Bonds:  {bonds}%")
            print(f"  Stocks: {stocks}%")
            print(f"  Drift threshold: {threshold}%")

            success = set_target_allocation(cash, bonds, stocks, threshold)

            if success:
                print("\n✅ Target allocation set successfully")
                print("   Rebalancing cache updated")
            else:
                print("\n❌ Failed to set target allocation")

        except KeyboardInterrupt:
            print("\n\nCancelled")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)

# Made with Bob
