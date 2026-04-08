#!/usr/bin/env python3
"""
backfill_performance_history.py
================================
Utility script to backfill performance tracking database with historical data.

This script:
1. Reads existing portfolio data from the database
2. Creates performance snapshots for each historical month
3. Populates the performance_history.db database
4. Enables accurate Time-Weighted Return (TWR) calculations

Usage:
    python3 backfill_performance_history.py [--start-year YEAR] [--start-month MONTH]
    
Examples:
    # Backfill from January 2020 to present
    python3 backfill_performance_history.py --start-year 2020 --start-month 1
    
    # Backfill from June 2023 to present
    python3 backfill_performance_history.py --start-year 2023 --start-month 6
    
    # Backfill all available data
    python3 backfill_performance_history.py
"""

import argparse
import sys
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from components.performance_tracker import get_tracker
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_earliest_data() -> tuple[int, int]:
    """
    Find the earliest month/year with portfolio data.
    
    Returns:
        Tuple of (month, year)
    """
    from load_data import get_portfolio_truth_by_month
    
    # Start from 2015 and search forward
    for year in range(2015, date.today().year + 1):
        for month in range(1, 13):
            try:
                df = get_portfolio_truth_by_month(month, year)
                if not df.empty:
                    logger.info(f"Found earliest data: {month}/{year}")
                    return (month, year)
            except:
                continue
    
    # Default to current year if nothing found
    today = date.today()
    return (1, today.year)


def backfill_performance_data(
    start_month: int,
    start_year: int,
    end_month: int = None,
    end_year: int = None,
    force: bool = False
) -> int:
    """
    Backfill performance tracking database.
    
    Args:
        start_month: Starting month (1-12)
        start_year: Starting year
        end_month: Ending month (default: current month)
        end_year: Ending year (default: current year)
        force: If True, overwrite existing snapshots
        
    Returns:
        Number of snapshots created
    """
    tracker = get_tracker()
    
    # Check if data already exists
    if not force:
        existing = tracker.get_snapshots()
        if not existing.empty:
            print(f"\n⚠️  Warning: Performance database already contains {len(existing)} snapshots")
            print(f"   Earliest: {existing.iloc[0]['snapshot_date']}")
            print(f"   Latest: {existing.iloc[-1]['snapshot_date']}")
            print("\n   Use --force to overwrite existing data")
            
            response = input("\n   Continue and add new snapshots? (y/N): ")
            if response.lower() != 'y':
                print("   Cancelled.")
                return 0
    
    print(f"\n📊 Backfilling performance data...")
    print(f"   Start: {start_month}/{start_year}")
    
    if end_month and end_year:
        print(f"   End: {end_month}/{end_year}")
    else:
        print(f"   End: Present")
    
    print()
    
    count = tracker.backfill_from_networth_data(
        start_month=start_month,
        start_year=start_year,
        end_month=end_month,
        end_year=end_year
    )
    
    return count


def verify_backfill():
    """Verify the backfilled data and show summary."""
    tracker = get_tracker()
    snapshots = tracker.get_snapshots()
    
    if snapshots.empty:
        print("\n❌ No snapshots found in database")
        return False
    
    print(f"\n✅ Successfully backfilled {len(snapshots)} snapshots")
    print(f"\n📈 Performance Data Summary:")
    print(f"   Total Snapshots: {len(snapshots)}")
    print(f"   Date Range: {snapshots.iloc[0]['snapshot_date']} to {snapshots.iloc[-1]['snapshot_date']}")
    print(f"   Starting Value: ${snapshots.iloc[0]['total_value']:,.2f}")
    print(f"   Current Value: ${snapshots.iloc[-1]['total_value']:,.2f}")
    
    # Calculate overall return
    start_value = snapshots.iloc[0]['total_value']
    end_value = snapshots.iloc[-1]['total_value']
    total_return = ((end_value - start_value) / start_value) * 100
    print(f"   Total Return: {total_return:+.2f}%")
    
    # Test TWR calculation
    print(f"\n🧮 Testing TWR Calculations:")
    periods = ['1M', '3M', '6M', '1Y']
    
    for period in periods:
        try:
            metrics = tracker.get_period_performance(period)
            if metrics:
                print(f"   {period:3s}: {metrics.twr*100:+6.2f}% (TWR)")
            else:
                print(f"   {period:3s}: Insufficient data")
        except Exception as e:
            print(f"   {period:3s}: Error - {e}")
    
    print(f"\n✅ Performance tracking is now enabled!")
    print(f"   Reports will now use accurate Time-Weighted Returns (TWR)")
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Backfill performance tracking database with historical data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill from January 2020
  %(prog)s --start-year 2020 --start-month 1
  
  # Backfill all available data
  %(prog)s --auto
  
  # Force overwrite existing data
  %(prog)s --force --start-year 2020 --start-month 1
        """
    )
    
    parser.add_argument(
        '--start-year',
        type=int,
        help='Starting year (e.g., 2020)'
    )
    
    parser.add_argument(
        '--start-month',
        type=int,
        choices=range(1, 13),
        help='Starting month (1-12)'
    )
    
    parser.add_argument(
        '--end-year',
        type=int,
        help='Ending year (default: current year)'
    )
    
    parser.add_argument(
        '--end-month',
        type=int,
        choices=range(1, 13),
        help='Ending month (default: current month)'
    )
    
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Automatically find earliest data and backfill'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing snapshots'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Performance History Backfill Utility")
    print("=" * 70)
    
    try:
        # Determine start date
        if args.auto:
            print("\n🔍 Searching for earliest portfolio data...")
            start_month, start_year = find_earliest_data()
        elif args.start_year and args.start_month:
            start_month = args.start_month
            start_year = args.start_year
        else:
            # Interactive mode
            print("\n📅 Enter backfill start date:")
            start_year = int(input("   Year (e.g., 2020): "))
            start_month = int(input("   Month (1-12): "))
        
        # Perform backfill
        count = backfill_performance_data(
            start_month=start_month,
            start_year=start_year,
            end_month=args.end_month,
            end_year=args.end_year,
            force=args.force
        )
        
        if count > 0:
            # Verify and show summary
            verify_backfill()
            
            print("\n" + "=" * 70)
            print("✅ Backfill Complete!")
            print("=" * 70)
            print("\nNext Steps:")
            print("  1. Generate a Portfolio Review Report")
            print("  2. Check the Performance Analysis section")
            print("  3. Verify Benchmark Comparison chart appears")
            print("  4. Review TWR-based performance metrics")
            print("\nNote: Run this script monthly to keep performance data current")
            print("=" * 70)
            
            return 0
        else:
            print("\n⚠️  No snapshots were created")
            return 1
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
        return 1
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Backfill failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())

# Made with Bob
