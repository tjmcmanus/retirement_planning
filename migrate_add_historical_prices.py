"""
Migration Script: Add Historical Price Storage
==============================================
This script adds 'end_of_month_price' column to portfolio_data_truth.csv
to enable accurate historical net worth tracking.

Purpose:
- Fixes the issue where Feb/March/April show nearly identical net worth values
- Stores actual end-of-month prices instead of always using current prices
- Enables accurate historical trend analysis

Usage:
    python migrate_add_historical_prices.py [--dry-run]

Options:
    --dry-run: Preview changes without modifying the file
"""

import pandas as pd
import shutil
from datetime import datetime
import os
import sys
import argparse

PORTFOLIO_FILE = 'portfolio_data_truth.csv'
NEW_COLUMN = 'end_of_month_price'


def create_backup(filename: str) -> str:
    """Create a timestamped backup of the portfolio file."""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"{filename} not found")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f'portfolio_data_truth_pre_historical_prices_{timestamp}.csv'
    shutil.copy2(filename, backup_file)
    print(f"✅ Created backup: {backup_file}")
    return backup_file


def add_historical_price_column(dry_run: bool = False) -> None:
    """
    Add end_of_month_price column to portfolio_data_truth.csv.
    
    Args:
        dry_run: If True, preview changes without modifying the file
    """
    print(f"\n{'='*70}")
    print("Migration: Add Historical Price Storage")
    print(f"{'='*70}\n")
    
    # Check if file exists
    if not os.path.exists(PORTFOLIO_FILE):
        print(f"❌ Error: {PORTFOLIO_FILE} not found")
        print("   Please ensure the file exists in the current directory.")
        sys.exit(1)
    
    # Load the data
    print(f"📂 Loading {PORTFOLIO_FILE}...")
    df = pd.read_csv(PORTFOLIO_FILE)
    print(f"   Found {len(df)} rows")
    
    # Check if column already exists
    if NEW_COLUMN in df.columns:
        print(f"\n⚠️  Column '{NEW_COLUMN}' already exists!")
        print("   Migration may have already been run.")
        
        # Show statistics
        null_count = df[NEW_COLUMN].isna().sum()
        filled_count = len(df) - null_count
        print(f"\n   Statistics:")
        print(f"   - Rows with prices: {filled_count}")
        print(f"   - Rows without prices: {null_count}")
        
        if null_count > 0:
            print(f"\n   💡 Tip: Run backfill_historical_prices.py to populate missing prices")
        
        sys.exit(0)
    
    # Preview the change
    print(f"\n📋 Migration Plan:")
    print(f"   - Add column: '{NEW_COLUMN}'")
    print(f"   - Default value: None (will be populated by backfill script)")
    print(f"   - Rows affected: {len(df)}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN MODE - No changes will be made")
        print(f"\n   Sample of what the data will look like:")
        sample_df = df.head(3).copy()
        sample_df[NEW_COLUMN] = None
        print(sample_df[['month', 'year', 'symbol', 'purchase_price', NEW_COLUMN]].to_string(index=False))
        print(f"\n   To apply changes, run without --dry-run flag")
        return
    
    # Create backup
    print(f"\n💾 Creating backup...")
    backup_file = create_backup(PORTFOLIO_FILE)
    
    # Add the new column with None as default
    print(f"\n✏️  Adding '{NEW_COLUMN}' column...")
    df[NEW_COLUMN] = None
    
    # Reorder columns to put end_of_month_price after purchase_price
    cols = df.columns.tolist()
    if 'purchase_price' in cols:
        purchase_price_idx = cols.index('purchase_price')
        cols.remove(NEW_COLUMN)
        cols.insert(purchase_price_idx + 1, NEW_COLUMN)
        df = df[cols]
    
    # Save the updated file
    print(f"💾 Saving updated {PORTFOLIO_FILE}...")
    df.to_csv(PORTFOLIO_FILE, index=False)
    
    print(f"\n{'='*70}")
    print("✅ Migration completed successfully!")
    print(f"{'='*70}\n")
    
    print("📊 Summary:")
    print(f"   - Backup created: {backup_file}")
    print(f"   - Column added: {NEW_COLUMN}")
    print(f"   - Total rows: {len(df)}")
    
    print("\n📝 Next Steps:")
    print("   1. Run: python backfill_historical_prices.py")
    print("      This will populate historical prices for past months")
    print("   2. Current month prices will be fetched automatically")
    print("   3. Net worth trends will now show accurate historical values")
    
    print(f"\n💡 Note: The new column is currently empty (None values).")
    print(f"   Historical prices will be populated by the backfill script.")


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description='Add historical price storage to portfolio_data_truth.csv'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying the file'
    )
    
    args = parser.parse_args()
    
    try:
        add_historical_price_column(dry_run=args.dry_run)
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

# Made with Bob
