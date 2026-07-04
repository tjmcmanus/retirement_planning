#!/usr/bin/env python3
"""Test script to verify federal tax calculation fix for years 2027-2029"""

import sys
import logging
from strategy import build_withdrawal_strategy_display

# Set up logging to see the detailed calculations
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
)

print("=" * 80)
print("Testing Federal Tax Calculation Fix")
print("=" * 80)

# Build strategy for years 2026-2029
strategy_df, balances_df = build_withdrawal_strategy_display(start_year=2026, end_year=2029)

# Print column names to debug
print("\nAvailable columns:", list(strategy_df.columns))

# Extract and display federal tax for years 2027-2029
print("\n" + "=" * 80)
print("FEDERAL TAX VERIFICATION")
print("=" * 80)

for year in [2027, 2028, 2029]:
    year_data = strategy_df[strategy_df['Year'] == year]
    if not year_data.empty:
        row = year_data.iloc[0]
        print(f"\nYear {year}:")
        print(f"  AGI:              ${row['AGI']:>15,.2f}")
        print(f"  LTCG Harvested:   ${row['LTCG Harvested']:>15,.2f}")
        print(f"  Roth Conversion:  ${row['Roth Conversion']:>15,.2f}")
        print(f"  DAF Contribution: ${row['DAF Contribution']:>15,.2f}")
        print(f"  Federal Tax:      ${row['Federal Tax']:>15,.2f}")
        
        # Compare with expected values from logs
        if year == 2027:
            expected = 100670.00
            print(f"  Expected:         ${expected:>15,.2f}")
            diff = row['Federal Tax'] - expected
            print(f"  Difference:       ${diff:>15,.2f} {'✓ FIXED' if abs(diff) < 500 else '✗ ISSUE'}")
        elif year == 2028:
            expected = 101043.00
            print(f"  Expected:         ${expected:>15,.2f}")
            diff = row['Federal Tax'] - expected
            print(f"  Difference:       ${diff:>15,.2f} {'✓ FIXED' if abs(diff) < 500 else '✗ ISSUE'}")
        elif year == 2029:
            expected = 103259.00
            print(f"  Expected:         ${expected:>15,.2f}")
            diff = row['Federal Tax'] - expected
            print(f"  Difference:       ${diff:>15,.2f} {'✓ FIXED' if abs(diff) < 500 else '✗ ISSUE'}")

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)

# Made with Bob
