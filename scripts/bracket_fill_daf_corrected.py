"""
2027 Bracket-Fill Breakdown — Corrected DAF Treatment

KEY CORRECTIONS:
1. DAF is funded from BROKERAGE (appreciated stock transfer) — NOT Traditional
2. DAF deduction = 30% of AGI limit (appreciated securities)
3. When DAF > standard deduction → ITEMIZE (DAF + SALT replaces std deduction)
4. No Traditional withdrawal needed for DAF — brokerage transfer is tax-free

References:
- IRC §170: 30% AGI limit for appreciated securities donated to DAF
- calculations.py _DAF_SECURITIES_LIMIT_PCT = 0.30
- strategy.py line 1390: itemized = SALT + DAF
"""

import sys
sys.path.insert(0, '.')

from strategy_core.tax_calculator import TaxCalculator

print("=" * 80)
print("2027 BRACKET-FILL BREAKDOWN — CORRECTED DAF TREATMENT")
print("=" * 80)
print()

# ============================================================================
# CORRECTED UNDERSTANDING OF DAF
# ============================================================================

print("DAF MECHANICS (CORRECTED):")
print("-" * 80)
print("""
  1. FUNDING:   DAF funded from BROKERAGE (appreciated stock transfer)
                → NOT from Traditional IRA
                → NO ordinary income tax on the transfer
                → Capital gain on donated stock is COMPLETELY ELIMINATED

  2. DEDUCTION: Appreciated securities → 30% of AGI limit (IRC §170)
                → REPLACES standard deduction (itemized route)
                → Combined with SALT deduction (capped at $10,000)
                → Only beneficial if (DAF + SALT) > standard deduction

  3. TAX FLOW:  AGI = gross income - itemized deductions (when DAF > std ded)
                Gross income = only the Traditional withdrawal (for spending)
""")

# ============================================================================
# STEP 1: DETERMINE 2027 INCOME (DAF IS NOT ORDINARY INCOME)
# ============================================================================

print("STEP 1: INCOME SOURCES (2027)")
print("-" * 80)

# Traditional withdrawal — spending ONLY (no DAF component)
traditional_for_spending = 73083   # Covers spending shortfall
traditional_for_daf = 0            # CORRECTED: DAF comes from Brokerage, not Traditional!

# Brokerage — two components
brokerage_delta = 5583             # Delta over 12% bracket
brokerage_daf = 60000              # Appreciated stock to DAF (NO capital gain recognized)

print(f"  Traditional (spending shortfall only): ${traditional_for_spending:>10,.0f}")
print(f"  Traditional (DAF):                     ${traditional_for_daf:>10,.0f}  ← was $60,000 INCORRECTLY")
print()
print(f"  Brokerage → spending delta (sold):     ${brokerage_delta:>10,.0f}  → LTCG applies")
print(f"  Brokerage → DAF transfer (stock):      ${brokerage_daf:>10,.0f}  → NO tax (donated appreciated stock)")
print()

# ============================================================================
# STEP 2: GROSS INCOME CALCULATION
# ============================================================================

print("STEP 2: GROSS INCOME")
print("-" * 80)

# Brokerage delta breakdown
brokerage_delta_basis = 3349.80
brokerage_delta_gain  = 2233.20

# Gross income = Traditional (spending) + brokerage basis (not gain — that's LTCG)
gross_ordinary = traditional_for_spending + brokerage_delta_basis
ltcg_income = brokerage_delta_gain

print(f"  Traditional ordinary income:           ${traditional_for_spending:>10,.0f}")
print(f"  Brokerage basis (ordinary):            ${brokerage_delta_basis:>10,.0f}")
print(f"  ────────────────────────────────────────────────")
print(f"  Total Gross Ordinary Income:           ${gross_ordinary:>10,.0f}")
print()
print(f"  Long-Term Capital Gain (LTCG):         ${ltcg_income:>10,.0f}")
print()

# ============================================================================
# STEP 3: DAF DEDUCTION CALCULATION
# ============================================================================

print("STEP 3: DAF DEDUCTION")
print("-" * 80)

daf_contribution = 60000
property_tax = 5000  # From config
pa_state_tax_estimate = gross_ordinary * 0.0573
salt_cap = 10000
salt_deduction = min(pa_state_tax_estimate + property_tax, salt_cap)

# AGI limit for appreciated securities: 30% of AGI (IRC §170)
# IMPORTANT: The 30% limit is based on AGI *before* the DAF deduction
# AGI = gross ordinary income (Traditional + brokerage basis) + LTCG
agi_before_deduction = gross_ordinary + ltcg_income
agi_limit_30pct = agi_before_deduction * 0.30  # 30% of pre-deduction AGI

# Is $60,000 DAF within the 30% limit?
daf_within_limit = daf_contribution <= agi_limit_30pct

# Total itemized deductions
itemized_total = daf_contribution + salt_deduction

# Standard deduction
std_deduction = 35500

# Should we itemize?
should_itemize = itemized_total > std_deduction
effective_deduction = itemized_total if should_itemize else std_deduction
deduction_label = "ITEMIZED" if should_itemize else "STANDARD"

print(f"  DAF contribution (appreciated stock):  ${daf_contribution:>10,.0f}")
print(f"  30% AGI limit:                         ${agi_limit_30pct:>10,.0f}")
print(f"  DAF within limit?                      {'YES ✓' if daf_within_limit else 'NO — CAPPED'}")
print()
print(f"  SALT deduction:")
print(f"    PA State Tax estimate:               ${pa_state_tax_estimate:>10,.0f}")
print(f"    Property Tax:                        ${property_tax:>10,.0f}")
print(f"    SALT (capped at $10,000):            ${salt_deduction:>10,.0f}")
print()
print(f"  Itemized deduction = DAF + SALT:       ${itemized_total:>10,.0f}")
print(f"  Standard deduction:                    ${std_deduction:>10,.0f}")
print(f"  Use {deduction_label}: ${effective_deduction:,.0f}")
print()
print(f"  Taxable ordinary income:")
print(f"    Gross ordinary:                      ${gross_ordinary:>10,.0f}")
print(f"    Less {deduction_label}:  ${effective_deduction:>10,.0f}")
taxable_ordinary = max(0, gross_ordinary - effective_deduction)
print(f"    = Taxable Ordinary Income:           ${taxable_ordinary:>10,.0f}")
print()

# ============================================================================
# STEP 4: BRACKET-FILL ALLOCATION
# ============================================================================

print("STEP 4: BRACKET-FILL ALLOCATION")
print("-" * 80)
print()

brackets_2027 = [
    {"name": "10%", "lower": 0,       "upper": 24800,  "rate": 0.10},
    {"name": "12%", "lower": 24800,   "upper": 100800, "rate": 0.12},
    {"name": "22%", "lower": 100800,  "upper": 191950, "rate": 0.22},
]

ltcg_brackets_2027 = [
    {"name": "0%",  "lower": 0,      "upper": 95375,  "rate": 0.00},
    {"name": "15%", "lower": 95375,  "upper": 593750, "rate": 0.15},
]

print(f"  {'Bracket':<32} {'Amount':>10} {'Rate':>6} {'Tax':>10}")
print(f"  {'─'*60}")

total_fed_ordinary_tax = 0
remaining = taxable_ordinary
cumulative = 0

print(f"  {'Deduction (' + deduction_label + ')':30} ${effective_deduction:>9,.0f} {'—':>6} {'$0':>10}")

for br in brackets_2027:
    if remaining <= 0:
        break
    space = br['upper'] - br['lower']
    fill  = min(remaining, space)
    if fill <= 0:
        continue
    tax = fill * br['rate']
    total_fed_ordinary_tax += tax
    remaining -= fill
    cumulative += fill
    label = f"{br['name']} Bracket (${br['lower']:,} - ${br['upper']:,})"
    print(f"  {label:30} ${fill:>9,.0f} {br['name']:>6} ${tax:>9,.0f}")

print(f"  {'─'*60}")
print(f"  {'Ordinary Income Tax':30} {'':>10} {'':>6} ${total_fed_ordinary_tax:>9,.0f}")
print()

# LTCG — stacked on top of taxable ordinary income
print(f"  {'LTCG (stacked on ordinary income)':32}")
total_ltcg_tax = 0
ltcg_remaining = ltcg_income
ltcg_stack_start = taxable_ordinary

for ltcg_br in ltcg_brackets_2027:
    if ltcg_remaining <= 0:
        break
    effective_start = max(ltcg_stack_start, ltcg_br['lower'])
    effective_end   = ltcg_br['upper']
    if effective_start >= effective_end:
        continue
    space = effective_end - effective_start
    fill  = min(ltcg_remaining, space)
    if fill <= 0:
        continue
    tax = fill * ltcg_br['rate']
    total_ltcg_tax += tax
    ltcg_remaining -= fill
    ltcg_stack_start += fill
    label = f"{ltcg_br['name']} LTCG (${ltcg_br['lower']:,} - ${ltcg_br['upper']:,})"
    print(f"  {label:30} ${fill:>9,.0f} {ltcg_br['name']:>6} ${tax:>9,.0f}")

print(f"  {'─'*60}")
print(f"  {'LTCG Tax':30} {'':>10} {'':>6} ${total_ltcg_tax:>9,.0f}")
print()

# ============================================================================
# STEP 5: STATE TAX
# ============================================================================

print("STEP 5: PA STATE TAX")
print("-" * 80)

pa_rate = 0.0573
actual_pa_tax = taxable_ordinary * pa_rate
pa_ltcg_tax   = 0  # PA does not tax LTCG

print(f"  Ordinary income (${taxable_ordinary:,.0f}) × 5.73%: ${actual_pa_tax:>9,.0f}")
print(f"  LTCG (${ltcg_income:,.0f}) × 0.00% (PA exempt):  ${'0':>9}")
print(f"  {'─'*50}")
print(f"  Total PA State Tax:                    ${actual_pa_tax:>9,.0f}")
print()

# ============================================================================
# FINAL SUMMARY
# ============================================================================

total_federal = total_fed_ordinary_tax + total_ltcg_tax
total_state   = actual_pa_tax
grand_total   = total_federal + total_state

print("=" * 80)
print("FINAL 2027 TAX & WITHDRAWAL SUMMARY")
print("=" * 80)
print()
print(f"  WITHDRAWALS:")
print(f"    Traditional (spending):              ${traditional_for_spending:>10,.0f}")
print(f"    Traditional (DAF):                   ${0:>10,.0f}  ← CORRECTED (was $60,000)")
print(f"    Brokerage (delta, sold):             ${brokerage_delta:>10,.0f}")
print(f"    Brokerage (DAF, stock transfer):     ${brokerage_daf:>10,.0f}  ← no income event")
print(f"  {'─'*50}")
print(f"    Total Traditional:                   ${traditional_for_spending:>10,.0f}")
print(f"    Total Brokerage:                     ${brokerage_delta + brokerage_daf:>10,.0f}")
print()
print(f"  DEDUCTION: {deduction_label}")
print(f"    DAF contribution:                    ${daf_contribution:>10,.0f}")
print(f"    SALT:                                ${salt_deduction:>10,.0f}")
print(f"    Total Itemized:                      ${itemized_total:>10,.0f}")
print()
print(f"  TAXES:")
print(f"    Federal ordinary income:             ${total_fed_ordinary_tax:>10,.0f}")
print(f"    Federal LTCG:                        ${total_ltcg_tax:>10,.0f}")
print(f"    PA state:                            ${actual_pa_tax:>10,.0f}")
print(f"  {'─'*50}")
print(f"    TOTAL TAX OWED:                      ${grand_total:>10,.0f}")
print()
print(f"  COMPARISON (vs. old incorrect calculation):")
old_tax = 17748
saved   = old_tax - grand_total
print(f"    Old total tax (Traditional for DAF): $  17,748")
print(f"    New total tax (Brokerage for DAF):   ${grand_total:>10,.0f}")
print(f"    TAX SAVINGS FROM CORRECTION:         ${saved:>10,.0f}")
print()

if __name__ == '__main__':
    pass
