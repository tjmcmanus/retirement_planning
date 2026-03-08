"""
Migration script to add 'owner' column to existing portfolio_data_truth.csv

This script:
1. Backs up the existing portfolio_data_truth.csv
2. Adds an 'owner' column with default value 'Joint'
3. Saves the updated file

Usage:
    python migrate_portfolio_add_owner.py
"""

import pandas as pd
import os
import shutil
from datetime import datetime

def migrate_portfolio_data():
    """Add 'owner' column to existing portfolio data."""
    
    portfolio_file = 'portfolio_data_truth.csv'
    
    # Check if file exists
    if not os.path.exists(portfolio_file):
        print(f"❌ {portfolio_file} not found. No migration needed.")
        return False
    
    try:
        # Load existing data
        print(f"📂 Loading {portfolio_file}...")
        df = pd.read_csv(portfolio_file)
        
        # Check if 'owner' column already exists
        if 'owner' in df.columns:
            print("✅ 'owner' column already exists. No migration needed.")
            return True
        
        # Create backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f'portfolio_data_truth_pre_owner_migration_{timestamp}.csv'
        shutil.copy2(portfolio_file, backup_file)
        print(f"💾 Backup created: {backup_file}")
        
        # Add 'owner' column after 'account_type'
        # Default to 'Joint' for all existing accounts
        if 'account_type' in df.columns:
            # Find the position of account_type
            cols = df.columns.tolist()
            account_type_idx = cols.index('account_type')
            
            # Insert 'owner' column after 'account_type'
            df.insert(account_type_idx + 1, 'owner', 'Joint')
        else:
            # If account_type doesn't exist, just append
            df['owner'] = 'Joint'
        
        # Save updated data
        df.to_csv(portfolio_file, index=False)
        print(f"✅ Successfully added 'owner' column to {portfolio_file}")
        print(f"   Total rows: {len(df)}")
        print(f"   All accounts set to 'Joint' ownership by default")
        print(f"\n⚠️  IMPORTANT: Review your portfolio data and update the 'owner' field")
        print(f"   for accounts that belong to Primary or Spouse individually.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("Portfolio Data Migration: Add 'owner' Column")
    print("=" * 70)
    print()
    
    success = migrate_portfolio_data()
    
    print()
    print("=" * 70)
    if success:
        print("Migration completed successfully!")
        print("\nNext steps:")
        print("1. Review portfolio_data_truth.csv in the Configuration page")
        print("2. Update 'owner' field for accounts owned by Primary or Spouse")
        print("3. Joint accounts (default) are owned by both spouses")
    else:
        print("Migration failed or not needed.")
    print("=" * 70)

# Made with Bob
