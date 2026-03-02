#!/usr/bin/env python3
"""
Migration script to convert old standard.csv format to new format.

Old format (2 columns): year,deduction
New format (3 columns): year,filing_status,deduction

This script:
1. Detects if standard.csv is in old format
2. Backs up the old file
3. Converts to new format by duplicating each row for both filing statuses
4. Validates the new format

Usage:
    python migrate_standard_csv.py
"""

import pandas as pd
import os
import sys
from datetime import datetime

OLD_FORMAT_COLUMNS = ['year', 'deduction']
NEW_FORMAT_COLUMNS = ['year', 'filing_status', 'deduction']
CSV_FILE = 'standard.csv'
BACKUP_SUFFIX = '.backup'

def detect_format(df):
    """Detect if CSV is in old or new format."""
    columns = list(df.columns)
    
    if columns == OLD_FORMAT_COLUMNS:
        return 'old'
    elif columns == NEW_FORMAT_COLUMNS:
        return 'new'
    else:
        return 'unknown'

def migrate_old_to_new(old_df):
    """
    Convert old format to new format.
    
    Old format has one row per year with a single deduction value.
    New format needs two rows per year (one for each filing status).
    
    The old format assumed married_filing_jointly values, so we:
    - Keep original rows as married_filing_jointly
    - Create single rows with approximately 50% of the married value
    """
    new_rows = []
    
    for _, row in old_df.iterrows():
        year = row['year']
        married_deduction = row['deduction']
        
        # Add married_filing_jointly row (original value)
        new_rows.append({
            'year': year,
            'filing_status': 'married_filing_jointly',
            'deduction': married_deduction
        })
        
        # Add single row (approximately 50% of married value, rounded to nearest 50)
        single_deduction = round(married_deduction / 2 / 50) * 50
        new_rows.append({
            'year': year,
            'filing_status': 'single',
            'deduction': single_deduction
        })
    
    new_df = pd.DataFrame(new_rows)
    # Sort by year, then filing_status for consistency
    new_df = new_df.sort_values(['year', 'filing_status']).reset_index(drop=True)
    
    return new_df

def main():
    """Main migration function."""
    print(f"Standard Deduction CSV Migration Tool")
    print(f"=" * 50)
    
    # Check if file exists
    if not os.path.exists(CSV_FILE):
        print(f"ERROR: {CSV_FILE} not found in current directory")
        return 1
    
    # Read current file
    try:
        df = pd.read_csv(CSV_FILE)
        print(f"✓ Loaded {CSV_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to read {CSV_FILE}: {e}")
        return 1
    
    # Detect format
    format_type = detect_format(df)
    print(f"✓ Detected format: {format_type}")
    
    if format_type == 'new':
        print(f"✓ File is already in new format (3 columns)")
        print(f"  Columns: {list(df.columns)}")
        print(f"  No migration needed.")
        return 0
    
    if format_type == 'unknown':
        print(f"ERROR: Unknown format detected")
        print(f"  Expected columns: {OLD_FORMAT_COLUMNS} or {NEW_FORMAT_COLUMNS}")
        print(f"  Found columns: {list(df.columns)}")
        return 1
    
    # Format is 'old' - proceed with migration
    print(f"\n⚠ Migration required: Converting from old format to new format")
    
    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"{CSV_FILE}{BACKUP_SUFFIX}.{timestamp}"
    try:
        df.to_csv(backup_file, index=False)
        print(f"✓ Created backup: {backup_file}")
    except Exception as e:
        print(f"ERROR: Failed to create backup: {e}")
        return 1
    
    # Perform migration
    try:
        new_df = migrate_old_to_new(df)
        print(f"✓ Converted {len(df)} rows to {len(new_df)} rows")
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        return 1
    
    # Validate new format
    if list(new_df.columns) != NEW_FORMAT_COLUMNS:
        print(f"ERROR: Migration produced incorrect columns")
        print(f"  Expected: {NEW_FORMAT_COLUMNS}")
        print(f"  Got: {list(new_df.columns)}")
        return 1
    
    # Write new file
    try:
        new_df.to_csv(CSV_FILE, index=False)
        print(f"✓ Wrote new format to {CSV_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to write new file: {e}")
        print(f"  Your backup is safe at: {backup_file}")
        return 1
    
    # Show summary
    print(f"\n✓ Migration completed successfully!")
    print(f"\nSummary:")
    print(f"  - Old format: {len(df)} rows with columns {OLD_FORMAT_COLUMNS}")
    print(f"  - New format: {len(new_df)} rows with columns {NEW_FORMAT_COLUMNS}")
    print(f"  - Backup saved: {backup_file}")
    print(f"\nFirst few rows of new format:")
    print(new_df.head(6).to_string(index=False))
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

# Made with Bob
