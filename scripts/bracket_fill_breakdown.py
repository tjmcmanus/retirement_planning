"""
2027 Bracket-Fill Breakdown by Tax Bracket

Detailed allocation of Traditional withdrawals across each tax bracket,
showing how much income goes into each bracket and the corresponding tax.
"""

import sys
sys.path.insert(0, '.')

from strategy_core.tax_calculator import TaxCalculator

print("=" * 80)
print("2027 TAX BRACKET FILL ANALYSIS - DETAILED BREAKDOWN")
print("=" * 80)
print()

# ============================================================================
# YOUR 2027 INCOME COMPONENTS
# ============================================================================

print("INCOME SOURCES FOR 2027:")
print("-" * 80)

# Start with what you're withdrawing
traditional_for_spending = 73083
traditional_for_daf = 60000
brokerage_for_delta = 5583

# Brokerage withdrawal has both basis and gain
brokerage_basis = 3349.80
brokerage_gain = 2233.20

print(f"  Traditional withdrawal (spending): ${traditional_for_spending:,.2f}")
print(f"  Traditional withdrawal (DAF): ${traditional_for_daf:,.2f}")
print(f"  Brokerage withdrawal (basis): ${brokerage_basis:,.2f}")
print(f"  Brokerage withdrawal (LTCG gain): ${brokerage_gain:,.2f}")
print()

# Calculate AGI/taxable income
total_traditional = traditional_for_spending + traditional_for_daf
total_ordinary_income = total_traditional + brokerage_basis

print(f"  Total ordinary income (Trad + Brokerage basis): ${total_ordinary_income:,.2f}")
print()

# Standard deduction (MFJ ages 61/60)
std_deduction = 35500

print(f"  Standard deduction (MFJ, ages 61/60): ${std_deduction:,.2f}")
print()

# Taxable ordinary income
taxable_ordinary_income = max(0, total_ordinary_income - std_deduction)
print(f"  Taxable ordinary income: ${taxable_ordinary_income:,.2f}")
print()

# LTCG - goes to 0% bracket first
ltcg_gain = brokerage_gain
print(f"  Long-Term Capital Gains: ${ltcg_gain:,.2f}")
print()

# ============================================================================
# 2027 TAX BRACKETS (MARRIED FILING JOINTLY)
# ============================================================================

print("2027 TAX BRACKETS (Married Filing Jointly):")
print("-" * 80)

brackets_2027 = [
    {"rate": 0.10, "name": "10%", "lower": 0, "upper": 24800},
    {"rate": 0.12, "name": "12%", "lower": 24800, "upper": 100800},
    {"rate": 0.22, "name": "22%", "lower": 100800, "upper": 191950},
    {"rate": 0.24, "name": "24%", "lower": 191950, "upper": 243725},
]

ltcg_brackets_2027 = [
    {"rate": 0.00, "name": "0%", "lower": 0, "upper": 95375},
    {"rate": 0.15, "name": "15%", "lower": 95375, "upper": 593750},
    {"rate": 0.20, "name": "20%", "lower": 593750, "upper": float('inf')},
]

for bracket in brackets_2027:
    print(f"  {bracket['name']:>3}: ${bracket['lower']:>7,} - ${bracket['upper']:>7,}")
print()

# ============================================================================
# ORDINARY INCOME BRACKET ALLOCATION
# ============================================================================

print("ORDINARY INCOME BRACKET ALLOCATION:")
print("-" * 80)
print()

# How much do we have to allocate?
income_to_allocate = total_ordinary_income
remaining_std_ded = std_deduction
bracket_allocation = []
total_tax = 0

print(f"{'Bracket':<15} {'Income':<15} {'Tax Rate':<12} {'Taxable':<15} {'Tax':<15}")
print("-" * 80)

# Standard deduction first (no tax)
std_ded_from_ordinary = min(remaining_std_ded, income_to_allocate)
income_to_allocate -= std_ded_from_ordinary
remaining_std_ded -= std_ded_from_ordinary

print(f"{'Std Deduction':<15} ${std_ded_from_ordinary:>13,.2f} {'0%':<12} ${0:>13,.2f} ${0:>13,.2f}")

# Now allocate to tax brackets
for bracket in brackets_2027:
    if income_to_allocate <= 0:
        break
    
    bracket_name = f"{bracket['name']} Bracket"
    bracket_width = bracket['upper'] - bracket['lower']
    
    # How much of this bracket is available?
    used_in_bracket = bracket['lower']
    available_in_bracket = bracket_width - used_in_bracket
    
    # Actually, we need to think about this differently
    # We need to know how much is ALREADY used from previous allocations
    pass

# Let me recalculate properly
income_to_allocate = total_ordinary_income
bracket_allocation = []
cumulative_income = 0
total_tax = 0

# First apply standard deduction
taxable_start = std_deduction
remaining_income = taxable_ordinary_income

print(f"{'Std Deduction':<15} ${std_deduction:>13,.2f} {'—':<12} ${0:>13,.2f} ${0:>13,.2f}")

# Now fill brackets
for bracket in brackets_2027:
    if remaining_income <= 0:
        break
    
    bracket_space = bracket['upper'] - bracket['lower']
    # How much we already used in this bracket from standard deduction offset
    if cumulative_income < bracket['upper']:
        amount_in_bracket = min(remaining_income, bracket['upper'] - max(cumulative_income, bracket['lower']))
        if amount_in_bracket > 0:
            tax_for_bracket = amount_in_bracket * bracket['rate']
            total_tax += tax_for_bracket
            bracket_allocation.append({
                'bracket': bracket['name'],
                'amount': amount_in_bracket,
                'rate': bracket['rate'],
                'tax': tax_for_bracket
            })
            
            print(f"{bracket['name']:>3} Bracket     ${amount_in_bracket:>13,.2f} {bracket['name']:<12} ${amount_in_bracket:>13,.2f} ${tax_for_bracket:>13,.2f}")
            
            remaining_income -= amount_in_bracket
            cumulative_income += amount_in_bracket

print()
print(f"{'ORDINARY INCOME TAX:':<40} ${total_tax:>13,.2f}")
print()

# ============================================================================
# LTCG BRACKET ALLOCATION
# ============================================================================

print("LONG-TERM CAPITAL GAINS (LTCG) BRACKET ALLOCATION:")
print("-" * 80)
print()

# LTCG brackets are stacked on top of ordinary income
ltcg_income_start = taxable_ordinary_income  # LTCG starts after ordinary income
remaining_ltcg = ltcg_gain
total_ltcg_tax = 0

print(f"{'Bracket':<15} {'LTCG Amount':<15} {'Tax Rate':<12} {'Taxable':<15} {'Tax':<15}")
print("-" * 80)

for ltcg_bracket in ltcg_brackets_2027:
    if remaining_ltcg <= 0:
        break
    
    # Calculate how much LTCG fits in this bracket
    bracket_start = max(ltcg_income_start, ltcg_bracket['lower'])
    bracket_end = ltcg_bracket['upper']
    
    if bracket_start >= bracket_end:
        continue  # This bracket is already full
    
    available_space = bracket_end - bracket_start
    amount_in_bracket = min(remaining_ltcg, available_space)
    
    if amount_in_bracket > 0:
        ltcg_tax = amount_in_bracket * ltcg_bracket['rate']
        total_ltcg_tax += ltcg_tax
        
        print(f"{ltcg_bracket['name']:>3} LTCG Br.    ${amount_in_bracket:>13,.2f} {ltcg_bracket['name']:<12} ${amount_in_bracket:>13,.2f} ${ltcg_tax:>13,.2f}")
        
        remaining_ltcg -= amount_in_bracket
        ltcg_income_start += amount_in_bracket

print()
print(f"{'LTCG TAX:':<40} ${total_ltcg_tax:>13,.2f}")
print()

# ============================================================================
# STATE TAX (PA)
# ============================================================================

print("PENNSYLVANIA STATE INCOME TAX:")
print("-" * 80)
print()

pa_rate = 0.0573
ordinary_income_state_tax = taxable_ordinary_income * pa_rate
ltcg_state_tax = 0.0  # PA doesn't tax LTCG for individuals

print(f"  Ordinary income (${taxable_ordinary_income:,.2f}) @ 5.73%: ${ordinary_income_state_tax:,.2f}")
print(f"  LTCG (${ltcg_gain:,.2f}) @ 0.00%: ${ltcg_state_tax:,.2f}")
print()
print(f"  Total PA State Tax: ${ordinary_income_state_tax:,.2f}")
print()

# ============================================================================
# TOTAL TAX SUMMARY
# ============================================================================

print("=" * 80)
print("TOTAL TAX SUMMARY FOR 2027")
print("=" * 80)
print()

total_federal_tax = total_tax + total_ltcg_tax
total_state_tax = ordinary_income_state_tax
grand_total_tax = total_federal_tax + total_state_tax

print(f"  Federal tax (ordinary income):     ${total_tax:>13,.2f}")
print(f"  Federal tax (LTCG):                ${total_ltcg_tax:>13,.2f}")
print(f"  Total Federal Tax:                 ${total_federal_tax:>13,.2f}")
print()
print(f"  PA State Income Tax:               ${total_state_tax:>13,.2f}")
print()
print(f"  TOTAL TAX OWED FOR 2027:           ${grand_total_tax:>13,.2f}")
print()

# ============================================================================
# WITHDRAWAL SUMMARY
# ============================================================================

print("=" * 80)
print("2027 WITHDRAWAL SUMMARY")
print("=" * 80)
print()

print(f"  Traditional (spending):            ${traditional_for_spending:>13,.2f}")
print(f"  Traditional (DAF):                 ${traditional_for_daf:>13,.2f}")
print(f"  Total Traditional:                 ${traditional_for_spending + traditional_for_daf:>13,.2f}")
print()
print(f"  Brokerage (basis):                 ${brokerage_basis:>13,.2f}")
print(f"  Brokerage (LTCG gain):             ${brokerage_gain:>13,.2f}")
print(f"  Total Brokerage:                   ${brokerage_basis + brokerage_gain:>13,.2f}")
print()
print(f"  Total Withdrawals:                 ${total_traditional + brokerage_basis + brokerage_gain:>13,.2f}")
print(f"  Total Taxes:                       ${grand_total_tax:>13,.2f}")
print()

# ============================================================================
# BRACKET UTILIZATION SUMMARY
# ============================================================================

print("=" * 80)
print("BRACKET UTILIZATION SUMMARY")
print("=" * 80)
print()

print(f"  Standard Deduction:                ${std_deduction:>13,.2f}")
print(f"  10% Bracket (${24800:,.0f}-${24800:,.0f}):      ${0:>13,.2f}")
print(f"  12% Bracket (${24800:,.0f}-${100800:,.0f}):    ${min(remaining_income + taxable_ordinary_income, 76000):>13,.2f}")
print()
print(f"  0% LTCG Bracket available:         ${95375 - taxable_ordinary_income:>13,.2f}")
print(f"  0% LTCG used:                      ${ltcg_gain:>13,.2f}")
print()
print(f"  Effective Federal Tax Rate:        {(total_federal_tax / (total_ordinary_income + ltcg_gain) * 100):>13.2f}%")
print()

