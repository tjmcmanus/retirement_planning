#!/usr/bin/env python3
"""Test that the AGI fix is working correctly."""

import sys
sys.path.insert(0, '/Users/tjm/Downloads/retirement_planning')

from strategy import PortfolioBalances, build_withdrawal_strategy_display

# Test with 2026 data
initial_balances = PortfolioBalances(
    cash=55000,
    taxable=225000,
    traditional=670000,
    roth=168000,
    daf=200000
)

print("Testing AGI calculation for 2026...")
print("=" * 60)

strategy_df, balances_df = build_withdrawal_strategy_display(
    start_year=2026,
    end_year=2026,
    initial_balances=initial_balances,
    initial_expenses=102780,
    person1_name="Gomez",
    person2_name="Morticia",
    growth_rate=1.05,
    expense_inflation_rate=0.025,
    ss_claiming_age=70,
    retirement_year=2026,
    has_wages=True
)

if not strategy_df.empty:
    row = strategy_df[strategy_df['Year'] == 2026].iloc[0]
    
    wages = row.get("Wages", 0)
    roth_conv = row.get("Roth Conversion", 0)
    agi = row.get("AGI", 0)
    magi = row.get("MAGI", 0)
    
    print(f"Wages: ${wages:,.0f}")
    print(f"Roth Conversion: ${roth_conv:,.0f}")
    print(f"AGI: ${agi:,.0f}")
    print(f"MAGI: ${magi:,.0f}")
    print()
    
    expected_agi = wages + roth_conv
    print(f"Expected AGI: ${expected_agi:,.0f}")
    
    if abs(agi - expected_agi) < 1:
        print("✅ AGI FIX IS WORKING!")
    else:
        print(f"❌ AGI FIX NOT WORKING - AGI should be ${expected_agi:,.0f} but is ${agi:,.0f}")
        print(f"   Difference: ${expected_agi - agi:,.0f}")
else:
    print("❌ No data generated")

print("=" * 60)

# Made with Bob
