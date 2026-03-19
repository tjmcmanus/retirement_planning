"""
Fix Missing Owner Values in Portfolio Data
===========================================
This script identifies and optionally fixes rows in portfolio_data_truth.csv
that are missing the 'owner' field.
"""

import pandas as pd
import sys

PORTFOLIO_FILE = 'portfolio_data_truth.csv'

def analyze_missing_owners():
    """Analyze which rows are missing owner values."""
    try:
        df = pd.read_csv(PORTFOLIO_FILE)
    except FileNotFoundError:
        print(f"❌ Error: {PORTFOLIO_FILE} not found")
        return
    
    # Check if owner column exists
    if 'owner' not in df.columns:
        print(f"❌ Error: 'owner' column not found in {PORTFOLIO_FILE}")
        print(f"Available columns: {', '.join(df.columns)}")
        return
    
    # Find rows with missing owner
    missing_owner = df['owner'].isna() | (df['owner'].astype(str).str.strip() == '')
    missing_count = missing_owner.sum()
    
    print(f"\n📊 Analysis of {PORTFOLIO_FILE}")
    print(f"=" * 60)
    print(f"Total rows: {len(df)}")
    print(f"Rows with owner: {(~missing_owner).sum()}")
    print(f"Rows missing owner: {missing_count}")
    
    if missing_count > 0:
        print(f"\n⚠️  Found {missing_count} rows with missing owner:")
        print("-" * 60)
        
        # Show details of missing rows
        missing_df = df[missing_owner][['month', 'year', 'account_name', 'account_type', 'symbol', 'owner']]
        print(missing_df.to_string(index=False))
        
        # Group by account to show patterns
        print(f"\n📋 Missing owners by account:")
        account_counts = df[missing_owner].groupby('account_name').size()
        for account, count in account_counts.items():
            print(f"  - {account}: {count} rows")
        
        return df, missing_owner
    else:
        print("\n✅ All rows have owner values!")
        return df, missing_owner

def fix_missing_owners(df, missing_owner, default_owner='Joint'):
    """Fix missing owner values with a default."""
    if missing_owner.sum() == 0:
        print("\n✅ No missing owners to fix!")
        return
    
    print(f"\n🔧 Fixing missing owners...")
    print(f"Setting {missing_owner.sum()} rows to owner='{default_owner}'")
    
    # Create backup
    backup_file = PORTFOLIO_FILE.replace('.csv', '_backup_before_owner_fix.csv')
    df.to_csv(backup_file, index=False)
    print(f"✅ Backup created: {backup_file}")
    
    # Fix missing owners
    df.loc[missing_owner, 'owner'] = default_owner
    
    # Save fixed data
    df.to_csv(PORTFOLIO_FILE, index=False)
    print(f"✅ Fixed data saved to: {PORTFOLIO_FILE}")
    print(f"\n💡 If you need to use a different owner value:")
    print(f"   1. Open {PORTFOLIO_FILE} in a spreadsheet")
    print(f"   2. Filter for owner='{default_owner}'")
    print(f"   3. Update to the correct owner (e.g., 'Morticia', 'Primary', etc.)")

if __name__ == "__main__":
    print("🔍 Portfolio Owner Field Analyzer")
    print("=" * 60)
    
    result = analyze_missing_owners()
    
    if result is None:
        sys.exit(1)
    
    df, missing_owner = result
    
    if missing_owner.sum() > 0:
        print("\n" + "=" * 60)
        response = input("\n❓ Do you want to fix missing owners by setting them to 'Joint'? (y/n): ")
        
        if response.lower() == 'y':
            fix_missing_owners(df, missing_owner, default_owner='Joint')
        else:
            print("\n💡 To fix manually:")
            print(f"   1. Open {PORTFOLIO_FILE} in a spreadsheet")
            print(f"   2. Find rows with empty 'owner' column")
            print(f"   3. Fill in the correct owner value")
            print(f"   4. Save the file")
    
    print("\n✅ Done!")

# Made with Bob
