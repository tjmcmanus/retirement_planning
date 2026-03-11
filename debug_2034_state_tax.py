#!/usr/bin/env python3
"""
Debug script to trace exactly what's happening with 2034 state tax calculation.
"""

from strategy import calculate_state_tax

# From your screenshot for 2034:
agi = 218410.86
ss_benefits_full = 50676
taxable_ss = ss_benefits_full * 0.85  # Approximately $43,075
trad_to_brok = 92960.41
roth_conversion = 61601.30
brok_to_cash = 100015.91
ltcg_harvested = brok_to_cash * 0.40  # Approximately $40,006

retirement_income = trad_to_brok + roth_conversion  # $154,561

print("=" * 80)
print("Debugging 2034 State Tax Calculation")
print("=" * 80)
print(f"\nFrom Screenshot:")
print(f"  AGI: ${agi:,.2f}")
print(f"  SS Benefits (full): ${ss_benefits_full:,.2f}")
print(f"  Taxable SS (85%): ${taxable_ss:,.2f}")
print(f"  Trad→Brok: ${trad_to_brok:,.2f}")
print(f"  Roth Conversion: ${roth_conversion:,.2f}")
print(f"  Brok→Cash: ${brok_to_cash:,.2f}")
print(f"  LTCG (40% of Brok→Cash): ${ltcg_harvested:,.2f}")
print(f"  Retirement Income: ${retirement_income:,.2f}")

# Call state tax function
state_tax, details = calculate_state_tax(
    state_agi=agi,
    state='PA',
    year=2034,
    filing_status='married_filing_jointly',
    retirement_income=retirement_income,
    ss_benefits=taxable_ss
)

print(f"\nState Tax Calculation:")
print(f"  State AGI: ${details['state_agi']:,.2f}")
print(f"  Retirement exemption: ${details['retirement_exemption']:,.2f}")
print(f"  Standard deduction: ${details['standard_deduction']:,.2f}")
print(f"  Taxable income: ${details['taxable_income']:,.2f}")
print(f"  State tax: ${details['state_tax']:,.2f}")

print(f"\nBreakdown:")
print(f"  AGI: ${agi:,.2f}")
print(f"  - Retirement income exempt: ${retirement_income:,.2f}")
print(f"  - SS benefits exempt: ${taxable_ss:,.2f}")
print(f"  - Standard deduction: ${details['standard_deduction']:,.2f}")
print(f"  = Taxable: ${details['taxable_income']:,.2f}")

expected_remaining = agi - retirement_income - taxable_ss
print(f"\nExpected remaining after exemptions: ${expected_remaining:,.2f}")
print(f"Expected tax at 3.07%: ${expected_remaining * 0.0307:,.2f}")

if state_tax == 0:
    print(f"\n❌ STATE TAX IS $0!")
    print(f"   This means taxable income is: ${details['taxable_income']:,.2f}")
    if details['taxable_income'] == 0:
        print(f"   Total exemptions: ${details['retirement_exemption']:,.2f}")
        print(f"   This is MORE than the non-retirement income in AGI!")
        print(f"\n   ISSUE: PA is exempting ALL income, including LTCG from brokerage")
        print(f"   LTCG should NOT be exempt - only IRA/401k distributions")
else:
    print(f"\n✓ State tax calculated: ${state_tax:,.2f}")

print("=" * 80)

# Made with Bob
