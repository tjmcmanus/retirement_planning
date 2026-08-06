"""
Option 4 Analysis: Brokerage (LTCG) vs Traditional (13%) for the Delta

Compare the tax costs of:
- Withdrawing $5,583 from Brokerage (with LTCG tax)
- vs. Withdrawing $5,583 from Traditional (at 13% rate, over bracket)
"""

import sys
sys.path.insert(0, '.')

from strategy_core.tax_calculator import TaxCalculator

# ============================================================================
# SCENARIO SETUP
# ============================================================================

print("=" * 70)
print("OPTION 4: BROKERAGE (LTCG) vs TRADITIONAL (13%) ANALYSIS")
print("=" * 70)
print()

print("SITUATION:")
print("-" * 70)
print("  2027 Spending Shortfall: $73,083")
print("  12% Bracket Available: $67,500")
print("  DELTA: $5,583 (amount over bracket)")
print()
print("QUESTION: How to fund the $5,583 delta?")
print("  Option A: Traditional (will be taxed at 13% instead of 12%)")
print("  Option B: Brokerage (will incur LTCG tax)")
print()

# ============================================================================
# OPTION A: TRADITIONAL AT 13% (OVER BRACKET)
# ============================================================================

print("OPTION A: Pull $5,583 from Traditional (Over Bracket)")
print("-" * 70)

delta_amount = 5583
traditional_rate = 0.13  # Over the 12% bracket into 22% bracket

# Marginal rate is 22% (next bracket up), but we're only going into it slightly
# Conservative estimate: average between 12% and 22% = ~17%
# But the next bracket starts at $100,800, so technically it's 22%
# Let's calculate both scenarios

print(f"  Withdrawal amount: ${delta_amount:,.2f}")
print(f"  Marginal rate (next bracket): 22%")
print()

# Federal tax on the overage
federal_tax_over_bracket = delta_amount * 0.22
print(f"  Federal tax @ 22%: ${federal_tax_over_bracket:,.2f}")

# State tax (PA): ~5%
state_rate = 0.0573  # PA income tax rate
state_tax_traditional = delta_amount * state_rate
print(f"  PA State tax @ 5.73%: ${state_tax_traditional:,.2f}")

total_tax_traditional = federal_tax_over_bracket + state_tax_traditional
effective_rate_traditional = (total_tax_traditional / delta_amount) * 100

print(f"  Total tax: ${total_tax_traditional:,.2f}")
print(f"  Effective rate: {effective_rate_traditional:.2f}%")
print()

net_traditional = delta_amount - total_tax_traditional
print(f"  Net received: ${net_traditional:,.2f}")
print()

# ============================================================================
# OPTION B: BROKERAGE WITH LTCG
# ============================================================================

print("OPTION B: Pull $5,583 from Brokerage (LTCG Tax)")
print("-" * 70)
print()

# Need to estimate LTCG ratio on brokerage account
# Brokerage balance: ~$1,150,000
# Let's estimate the gain ratio (you've been investing for years)
# Conservative estimate: 40% gain ratio = 60% basis, 40% gain

brokerage_balance = 1150000
estimated_gain_ratio = 0.40  # 40% of value is unrealized gain

print(f"  Brokerage balance: ${brokerage_balance:,.0f}")
print(f"  Estimated gain ratio: {estimated_gain_ratio*100:.0f}%")
print()

# When withdrawing $5,583, allocate proportionally
withdrawal_amount = delta_amount
gain_in_withdrawal = withdrawal_amount * estimated_gain_ratio
basis_in_withdrawal = withdrawal_amount * (1 - estimated_gain_ratio)

print(f"  Withdrawal amount: ${withdrawal_amount:,.2f}")
print(f"    - Basis: ${basis_in_withdrawal:,.2f}")
print(f"    - Unrealized gain: ${gain_in_withdrawal:,.2f}")
print()

# LTCG tax rates for 2027 (married filing jointly, ages 61/60)
# You'll have some ordinary income from the Traditional withdrawal
# Let's calculate your LTCG bracket

tax_calc = TaxCalculator()

# Your 2027 ordinary income: $73,083 (spending-based Traditional withdrawal)
# Plus: $60,000 DAF distribution (not taxable but counts for phaseout)
# Standard deduction: $35,500
# Taxable ordinary income: $73,083 - $35,500 = $37,583

ordinary_income_for_ltcg = 73083 - 35500  # = $37,583
print(f"  Your taxable ordinary income: ${ordinary_income_for_ltcg:,.2f}")
print()

# 2027 LTCG brackets (MFJ):
# 0%: $0 - $95,375
# 15%: $95,375 - $593,750
# 20%: $593,750+

ltcg_0_percent_threshold = 95375
ltcg_15_percent_threshold = 593750

# How much 0% bracket space do you have?
space_in_0_percent = ltcg_0_percent_threshold - ordinary_income_for_ltcg
space_in_0_percent = max(0, space_in_0_percent)

print(f"  0% LTCG bracket available: ${space_in_0_percent:,.2f}")
print(f"  (between ${ordinary_income_for_ltcg:,.2f} and ${ltcg_0_percent_threshold:,.0f})")
print()

# Your $5,583 gain: how much fits in 0% bracket?
gain_at_0_percent = min(gain_in_withdrawal, space_in_0_percent)
gain_at_15_percent = max(0, gain_in_withdrawal - gain_at_0_percent)

ltcg_tax = (gain_at_0_percent * 0.00) + (gain_at_15_percent * 0.15)

print(f"  LTCG tax breakdown:")
print(f"    - ${gain_at_0_percent:,.2f} @ 0%: ${gain_at_0_percent * 0.00:,.2f}")
print(f"    - ${gain_at_15_percent:,.2f} @ 15%: ${gain_at_15_percent * 0.15:,.2f}")
print(f"  Total LTCG tax (federal): ${ltcg_tax:,.2f}")
print()

# State tax on LTCG (PA doesn't tax capital gains separately for individuals)
# PA doesn't have capital gains tax for individuals
state_tax_ltcg = 0
print(f"  PA State tax on LTCG: ${state_tax_ltcg:,.2f} (PA does not tax LTCG)")
print()

total_tax_brokerage = ltcg_tax + state_tax_ltcg
effective_rate_brokerage = (total_tax_brokerage / delta_amount) * 100

print(f"  Total tax on $5,583 withdrawal: ${total_tax_brokerage:,.2f}")
print(f"  Effective rate: {effective_rate_brokerage:.2f}%")
print()

net_brokerage = withdrawal_amount - total_tax_brokerage
print(f"  Net received: ${net_brokerage:,.2f}")
print()

# ============================================================================
# COMPARISON
# ============================================================================

print("=" * 70)
print("COMPARISON SUMMARY")
print("=" * 70)
print()

comparison_data = [
    ("", "Traditional (Over)", "Brokerage (LTCG)"),
    ("Withdrawal Amount", f"${delta_amount:,.2f}", f"${withdrawal_amount:,.2f}"),
    ("Federal Tax", f"${federal_tax_over_bracket:,.2f}", f"${ltcg_tax:,.2f}"),
    ("State Tax", f"${state_tax_traditional:,.2f}", f"${state_tax_ltcg:,.2f}"),
    ("Total Tax", f"${total_tax_traditional:,.2f}", f"${total_tax_brokerage:,.2f}"),
    ("Effective Rate", f"{effective_rate_traditional:.2f}%", f"{effective_rate_brokerage:.2f}%"),
    ("Net Received", f"${net_traditional:,.2f}", f"${net_brokerage:,.2f}"),
]

# Print table
for row in comparison_data:
    if row[0] == "":
        print(f"{row[0]:<20} {row[1]:>20} {row[2]:>20}")
        print("-" * 60)
    else:
        print(f"{row[0]:<20} {row[1]:>20} {row[2]:>20}")

print()
print("RECOMMENDATION:")
print("-" * 70)

tax_savings = total_tax_traditional - total_tax_brokerage
savings_pct = (tax_savings / total_tax_traditional) * 100

if total_tax_brokerage < total_tax_traditional:
    print(f"✓ BROKERAGE is MORE TAX-EFFICIENT")
    print(f"  Tax savings: ${tax_savings:,.2f} ({savings_pct:.1f}% savings)")
    print(f"  Effective rate: {effective_rate_brokerage:.2f}% vs {effective_rate_traditional:.2f}%")
else:
    print(f"✓ TRADITIONAL is MORE TAX-EFFICIENT")
    print(f"  Tax savings: ${tax_savings:,.2f} ({savings_pct:.1f}% savings)")
    print(f"  Effective rate: {effective_rate_traditional:.2f}% vs {effective_rate_brokerage:.2f}%")

print()
print("STRATEGY:")
print("-" * 70)
print(f"  Pull ${withdrawal_amount:,.2f} from BROKERAGE (LTCG)")
print(f"  + Pull ${73083:,.2f} from TRADITIONAL (spending shortfall within bracket)")
print(f"  + Fund ${60000:,.2f} DAF from TRADITIONAL")
print()
print(f"  TOTAL TRADITIONAL: ${73083 + 60000:,.2f}")
print(f"  TOTAL BROKERAGE: ${withdrawal_amount:,.2f}")
print(f"  TOTAL TAX: ${total_tax_traditional + total_tax_brokerage:,.2f}")
print()
print("ACCOUNT IMPACTS:")
print("-" * 70)
print(f"  Traditional: reduced by ${73083 + 60000:,.2f} = GOOD (reduce RMD burden)")
print(f"  Brokerage: reduced by ${withdrawal_amount:,.2f} (LTCG loss is minor)")
print(f"  PNC: increased by ${73083 - 73083:,.2f} = exact need met")
print()
print("KEY INSIGHT:")
print("-" * 70)
print(f"  By pulling the $5,583 delta from Brokerage instead of Traditional,")
print(f"  you save ${tax_savings:,.2f} in taxes while also reducing your Traditional")
print(f"  balance (which helps with future RMD burden).")
print()

