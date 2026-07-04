#!/usr/bin/env python3
"""Test Stage 2 healthcare cost calculation"""

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from strategy_core.stages.stage2_prep_retirement import Stage2PrepForRetirement
from strategy_core.models import PortfolioBalances

# Create Stage 2 instance
stage2 = Stage2PrepForRetirement()

# Test data for 2026
year = 2026
age_primary = 60
age_spouse = 59
balances = PortfolioBalances(
    cash=120707.57,
    taxable=1084834.92,
    traditional=6018084.14,
    roth=320578.81,
    daf=0.0
)
expenses = 110350.0
wages = 247000.0

# Calculate strategy
strategy = stage2.calculate_strategy(
    year=year,
    balances=balances,
    expenses=expenses,
    wages=wages,
    age_primary=age_primary,
    age_spouse=age_spouse,
    max_conversion_rate=0.32,
    filing_status='married_filing_jointly',
    state='PA'
)

print(f"\n=== Stage 2 Healthcare Test for {year} ===")
print(f"Healthcare Costs: ${strategy.healthcare_costs:,.2f}")
print(f"Expected: $11,688.00 (2 people × $487/month × 12 months)")
print(f"\nOther key values:")
print(f"  Wages: ${strategy.wages:,.2f}")
print(f"  Payroll Tax: ${strategy.payroll_tax:,.2f}")
print(f"  Roth Conversion: ${strategy.roth_conversion:,.2f}")
print(f"  AGI: ${strategy.agi:,.2f}")
print(f"  Federal Tax: ${strategy.federal_tax:,.2f}")
print(f"  State Tax: ${strategy.state_tax:,.2f}")

if strategy.healthcare_costs > 0:
    print(f"\n✅ SUCCESS: Healthcare costs are being calculated!")
else:
    print(f"\n❌ FAIL: Healthcare costs are $0")

# Made with Bob
