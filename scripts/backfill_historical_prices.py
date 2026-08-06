"""
Backfill Historical Prices Utility
===================================
This script populates the end_of_month_price column in portfolio_data_truth.csv
with actual historical prices from Yahoo Finance.

Purpose:
- Fixes net worth trend issues by using accurate historical prices
- Fetches end-of-month prices for all past months
- Preserves existing stored prices (only fills missing values)
- Enables accurate historical net worth analysis

Usage:
    python backfill_historical_prices.py [--dry-run] [--months N]

Options:
    --dry-run: Preview changes without modifying the file
    --months N: Only backfill last N months (default: all months)
    --force: Overwrite existing prices (default: only fill missing)
"""

import pandas as pd
import calendar
from datetime import datetime
import os
import sys
import argparse
import shutil
from typing import Optional
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import from load_data
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from load_data import _fetch_prices, CASH_SYMBOLS, CASH_PRICE
from portfolio_db import DB_PATH, db_load_all, db_overwrite_month

PORTFOLIO_FILE = 'portfolio_data_truth.csv'
COLUMN_NAME = 'end_of_month_price'


def create_backup(filename: str) -> str:
    """Create a timestamped backup of the portfolio file."""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"{filename} not found")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f'portfolio_data_truth_pre_backfill_{timestamp}.csv'
    shutil.copy2(filename, backup_file)
    logger.info(f"Created backup: {backup_file}")
    return backup_file


def get_end_of_month_date(year: int, month: int) -> datetime:
    """Get the last day of the specified month."""
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day)


def backfill_historical_prices(
    dry_run: bool = False,
    max_months: Optional[int] = None,
    force_overwrite: bool = False
) -> None:
    """
    Backfill historical prices for all months in portfolio_data_truth.csv.
    
    Args:
        dry_run: If True, preview changes without modifying the file
        max_months: If provided, only backfill last N months
        force_overwrite: If True, overwrite existing prices
    """
    print(f"\n{'='*70}")
    print("Backfill Historical Prices Utility")
    print(f"{'='*70}\n")
    
    # Check if DB exists
    if not DB_PATH.exists():
        print(f"❌ Error: {DB_PATH} not found")
        sys.exit(1)
    
    # Load the data
    logger.info(f"Loading {DB_PATH}...")
    df = db_load_all()
    logger.info(f"Found {len(df)} rows")
    
    # Check if column exists
    if COLUMN_NAME not in df.columns:
        print(f"\n❌ Error: Column '{COLUMN_NAME}' not found!")
        print(f"   Please run migrate_add_historical_prices.py first")
        sys.exit(1)
    
    # Get unique month/year combinations
    months_years_df = df[['month', 'year']].drop_duplicates().sort_values(by=['year', 'month']).reset_index(drop=True)
    
    # Filter to current month and earlier
    today = datetime.now()
    months_years_df = months_years_df[
        (months_years_df['year'] < today.year) |
        ((months_years_df['year'] == today.year) & (months_years_df['month'] <= today.month))
    ].reset_index(drop=True)
    
    # Exclude current month (always use live prices)
    months_years_df = months_years_df[
        ~((months_years_df['year'] == today.year) & (months_years_df['month'] == today.month))
    ].reset_index(drop=True)
    
    if max_months:
        months_years_df = months_years_df.tail(max_months).reset_index(drop=True)
    
    total_months = len(months_years_df)
    logger.info(f"Found {total_months} historical months to process")
    
    if total_months == 0:
        print("\n✅ No historical months to backfill")
        return
    
    # Statistics
    total_rows_to_update = 0
    total_rows_updated = 0
    months_processed = 0
    
    # Create a copy for modifications
    df_updated = df.copy()
    
    print(f"\n📊 Processing {total_months} months...\n")
    
    for idx, (_, row) in enumerate(months_years_df.iterrows(), 1):
        month = int(row['month'])
        year = int(row['year'])
        
        print(f"[{idx}/{total_months}] Processing {calendar.month_name[month]} {year}...")
        
        # Get rows for this month/year
        month_mask = (df_updated['month'] == month) & (df_updated['year'] == year)
        month_df = df_updated[month_mask].copy()
        
        # Determine which rows need prices
        if force_overwrite:
            needs_price_mask = ~month_df['symbol'].isin(CASH_SYMBOLS)
        else:
            needs_price_mask = (
                month_df[COLUMN_NAME].isna() & 
                ~month_df['symbol'].isin(CASH_SYMBOLS)
            )
        
        symbols_to_fetch = month_df.loc[needs_price_mask, 'symbol'].unique().tolist()
        
        if not symbols_to_fetch:
            print(f"   ✓ All prices already stored ({len(month_df)} rows)")
            continue
        
        # Get end of month date
        target_date = get_end_of_month_date(year, month)
        
        # Fetch historical prices
        print(f"   Fetching prices for {len(symbols_to_fetch)} symbols...")
        try:
            price_map = _fetch_prices(symbols_to_fetch, target_date=target_date)
            
            # Count successful fetches
            successful = sum(1 for p in price_map.values() if p is not None)
            print(f"   ✓ Fetched {successful}/{len(symbols_to_fetch)} prices")
            
            # Update the dataframe
            rows_updated_this_month = 0
            for symbol, price in price_map.items():
                if price is not None:
                    update_mask = month_mask & (df_updated['symbol'] == symbol)
                    if force_overwrite or df_updated.loc[update_mask, COLUMN_NAME].isna().all():
                        df_updated.loc[update_mask, COLUMN_NAME] = price
                        rows_updated_this_month += update_mask.sum()
            
            # Set CASH symbols to 1.0
            cash_mask = month_mask & df_updated['symbol'].isin(CASH_SYMBOLS)
            if force_overwrite or df_updated.loc[cash_mask, COLUMN_NAME].isna().any():
                df_updated.loc[cash_mask, COLUMN_NAME] = CASH_PRICE
                rows_updated_this_month += cash_mask.sum()
            
            total_rows_updated += rows_updated_this_month
            total_rows_to_update += len(month_df)
            months_processed += 1
            
            print(f"   ✓ Updated {rows_updated_this_month} rows")
            
        except Exception as e:
            logger.error(f"   ✗ Error fetching prices: {e}")
            continue
    
    print(f"\n{'='*70}")
    print("Backfill Summary")
    print(f"{'='*70}\n")
    print(f"Months processed: {months_processed}/{total_months}")
    print(f"Rows updated: {total_rows_updated}")
    print(f"Total historical rows: {total_rows_to_update}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN MODE - No changes saved")
        print(f"\n   Sample of updated data:")
        sample = df_updated[df_updated[COLUMN_NAME].notna()].head(5)
        print(sample[['month', 'year', 'symbol', 'purchase_price', COLUMN_NAME]].to_string(index=False))
        print(f"\n   To apply changes, run without --dry-run flag")
        return
    
    if total_rows_updated == 0:
        print(f"\n✅ No updates needed - all historical prices already stored")
        return
    
    # Create backup
    print(f"\n💾 Creating backup...")
    backup_file = create_backup(PORTFOLIO_FILE)
    
    # Save updated data back to portfolio.db (which also regenerates portfolio_data_truth.csv)
    print(f"💾 Saving updated holdings to {DB_PATH}...")
    for (month, year), month_rows in df_updated.groupby(['month', 'year'], sort=False):
        db_overwrite_month(int(month), int(year), month_rows)
    
    print(f"\n{'='*70}")
    print("✅ Backfill completed successfully!")
    print(f"{'='*70}\n")
    
    print("📝 Next Steps:")
    print("   1. Refresh your dashboard to see accurate historical trends")
    print("   2. Net worth charts will now show true historical values")
    print("   3. Run this script monthly to keep historical data up to date")
    
    print(f"\n💡 Tip: Add this to a monthly cron job or scheduled task")


def main():
    """Main entry point for the backfill script."""
    parser = argparse.ArgumentParser(
        description='Backfill historical prices in portfolio_data_truth.csv'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying the file'
    )
    parser.add_argument(
        '--months',
        type=int,
        help='Only backfill last N months (default: all months)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing prices (default: only fill missing)'
    )
    
    args = parser.parse_args()
    
    try:
        backfill_historical_prices(
            dry_run=args.dry_run,
            max_months=args.months,
            force_overwrite=args.force
        )
    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

# Made with Bob
