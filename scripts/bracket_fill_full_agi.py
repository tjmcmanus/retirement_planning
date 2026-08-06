"""
2027 Bracket-Fill Breakdown — Full AGI with Correct Calculation Order

CORRECT AGI BUILD ORDER:
  1. Gross Ordinary Income = Traditional (spending) + Roth Conversion
  2. AGI = Gross Ordinary + LTCG (before deductions)
  3. DAF 30% limit = 30% × AGI
  4. Deduction = max(Itemized, Standard) where Itemized = DAF (capped) + SALT
  5. Taxable Ordinary = Gross Ordinary − Deduction
  6. LTCG brackets stack on top of Taxable Ordinary
  7. State tax on Taxable Ordinary

DAF mechanics:
  - Funded from Brokerage appreciated stock (no income event, gain eliminated)
  - Deductible up to 30% of AGI for appreciated securities (IRC §170)
  - Excess carries forward up to 5 years
"""

import sys
sys.path.insert(0, '.')

from strategy_core.tax_calculator import TaxCalculator
import csv

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_bracket_upper(filing_status, year, rate, csv_path='income_rates.csv'):
    """Return upper limit of a given bracket from income_rates.csv."""
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if int(row['year']) == year and row['filing_status'] == filing_status and abs(float(row['rate']) - rate) < 0.001:
                return float(row['upper'])
    return None

def fill_brackets(taxable_income, brackets):
    """Return list of (name, fill, rate, tax) for each bracket that receives income."""
    remaining = taxable_income
    result = []
    for br in brackets:
        if remaining <= 0:
            break
        space = br['upper'] - br['lower']
        fill  = min(remaining, space)
        if fill <= 0:
            continue
        result.append({'name': br['name'], 'fill': fill, 'rate': br['rate'], 'tax': fill * br['rate']})
        remaining -= fill
    return result

def fill_ltcg_brackets(ltcg_income, ordinary_taxable, ltcg_brackets):
    """LTCG brackets stack on top of ordinary taxable income."""
    stack_position = ordinary_taxable
    remaining = ltcg_income
    result = []
    for br in ltcg_brackets:
        if remaining <= 0:
            break
        effective_start = max(stack_position, br['lower'])
        if effective_start >= br['upper']:
            continue
        space = br['upper'] - effective_start
        fill  = min(remaining, space)
        if fill <= 0:
            continue
        result.append({'name': br['name'], 'fill': fill, 'rate': br['rate'], 'tax': fill * br['rate']})
        remaining -= fill
        stack_position += fill
    return result

def hdr(label, amount, note=''):
    note_str = f'  ← {note}' if note else ''
    print(f"  {label:<44} ${amount:>10,.0f}{note_str}")

def sep():
    print(f"  {'─'*60}")

# ─────────────────────────────────────────────────────────────────────────────
# INPUTS — 2027 SCENARIO
# ─────────────────────────────────────────────────────────────────────────────

year            = 2027
filing_status   = 'married_filing_jointly'
age_primary     = 61
age_spouse      = 60

# Spending-based Traditional withdrawal (covers PNC shortfall, within 12% bracket)
trad_spending       = 73083

# Roth conversion — uses REMAINING 12% bracket space after spending (if any)
# For this scenario with Option 4 (Brokerage covers delta), spending fits in 12%
# so we use remaining space for a Roth conversion
roth_conversion     = 0      # Set to actual conversion amount to model that scenario

# Brokerage sale to cover the spending delta (amount over bracket)
brokerage_sold_basis = 3350
brokerage_sold_gain  = 2233

# DAF: appreciated Brokerage stock transfer — NOT ordinary income
daf_fmv             = 60000   # Fair Market Value transferred to DAF
daf_gain_eliminated = 24000   # Embedded gain eliminated (estimated 40% gain ratio)

# Tax constants
std_deduction = TaxCalculator().calculate_standard_deduction(
    filing_status, year, age_primary, age_spouse)
property_tax  = 5000
pa_rate       = 0.0573

# Bracket tables for 2027 (from income_rates.csv)
brackets_2027 = [
    {'name': '10%', 'lower':      0, 'upper':  24800, 'rate': 0.10},
    {'name': '12%', 'lower':  24800, 'upper': 100800, 'rate': 0.12},
    {'name': '22%', 'lower': 100800, 'upper': 191950, 'rate': 0.22},
    {'name': '24%', 'lower': 191950, 'upper': 243725, 'rate': 0.24},
]

ltcg_brackets_2027 = [
    {'name':  '0%', 'lower':      0, 'upper':  95375, 'rate': 0.00},
    {'name': '15%', 'lower':  95375, 'upper': 593750, 'rate': 0.15},
]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — GROSS ORDINARY INCOME
#   Traditional (spending) + Roth Conversion
#   Brokerage sold basis (return of capital, ordinary)
#   NOTE: Roth conversion is ordinary income and must come before DAF limit calc
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("2027 BRACKET-FILL — FULL AGI CALCULATION")
print("=" * 70)
print()
print("STEP 1 — GROSS ORDINARY INCOME")
print("-" * 70)
hdr("Traditional (spending shortfall)", trad_spending)
hdr("Roth Conversion", roth_conversion, "0 — no bracket space left after spending")
hdr("Brokerage sold — basis (return of capital)", brokerage_sold_basis)
sep()
gross_ordinary = trad_spending + roth_conversion + brokerage_sold_basis
hdr("GROSS ORDINARY INCOME", gross_ordinary)
print()
hdr("Brokerage sold — LTCG gain", brokerage_sold_gain, "taxed separately at LTCG rates")
hdr("DAF stock transfer (FMV)", daf_fmv, "no income event — gain eliminated")
print()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — AGI (before deductions)
#   AGI = Gross Ordinary + LTCG
#   This is the base for the 30% DAF limit calculation
# ─────────────────────────────────────────────────────────────────────────────

print("STEP 2 — AGI (before deductions, used for 30% DAF limit)")
print("-" * 70)
agi_gross = gross_ordinary + brokerage_sold_gain
hdr("Gross Ordinary Income", gross_ordinary)
hdr("+ Long-Term Capital Gain", brokerage_sold_gain)
sep()
hdr("= AGI (pre-deduction)", agi_gross)
print()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — DAF DEDUCTION
#   30% AGI limit applies to appreciated securities donated to DAF
#   Excess carries forward up to 5 years
#   SALT (state tax + property tax, capped at $10,000)
#   Itemize only if (DAF deductible + SALT) > standard deduction
# ─────────────────────────────────────────────────────────────────────────────

print("STEP 3 — DAF DEDUCTION (IRC §170)")
print("-" * 70)

daf_limit_30pct     = agi_gross * 0.30
daf_deductible      = min(daf_fmv, daf_limit_30pct)
daf_carryforward    = daf_fmv - daf_deductible

pa_state_est        = gross_ordinary * pa_rate
salt                = min(pa_state_est + property_tax, 10000)
itemized            = daf_deductible + salt
use_itemized        = itemized > std_deduction
deduction           = itemized if use_itemized else std_deduction
deduction_type      = "ITEMIZED" if use_itemized else "STANDARD"

hdr("DAF FMV transferred (appreciated stock)", daf_fmv)
hdr("30% AGI limit (30% × $" + f"{agi_gross:,.0f})", daf_limit_30pct)
hdr("DAF deductible this year", daf_deductible)
hdr("DAF carryforward (2028–2032)", daf_carryforward, "not lost — 5-year carryforward")
print()
hdr("SALT: PA est. tax", pa_state_est)
hdr("SALT: Property tax", property_tax)
hdr("SALT (capped at $10,000)", salt)
print()
hdr("Itemized total (DAF + SALT)", itemized)
hdr("Standard deduction (MFJ ages 61/60)", std_deduction)
print(f"  → Use {deduction_type}: ${deduction:,.0f}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — TAXABLE ORDINARY INCOME
# ─────────────────────────────────────────────────────────────────────────────

print("STEP 4 — TAXABLE ORDINARY INCOME")
print("-" * 70)
taxable_ordinary = max(0, gross_ordinary - deduction)
hdr("Gross Ordinary Income", gross_ordinary)
hdr(f"Less {deduction_type} deduction", deduction)
sep()
hdr("= TAXABLE ORDINARY INCOME", taxable_ordinary)
print()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — BRACKET FILL (ORDINARY)
# ─────────────────────────────────────────────────────────────────────────────

print("STEP 5 — ORDINARY INCOME BRACKET FILL")
print("-" * 70)
print(f"  {'Bracket':<35} {'Fill':>10} {'Rate':>6} {'Tax':>10}")
print(f"  {'─'*63}")
print(f"  {deduction_type+' Deduction':<35} ${deduction:>9,.0f} {'—':>6} {'$0':>10}")

alloc = fill_brackets(taxable_ordinary, brackets_2027)
fed_ordinary_tax = 0
for a in alloc:
    print(f"  {a['name']+' Bracket':<35} ${a['fill']:>9,.0f} {a['rate']*100:>5.0f}% ${a['tax']:>9,.0f}")
    fed_ordinary_tax += a['tax']
sep()
print(f"  {'Federal Ordinary Tax':<35} {'':>10} {'':>6} ${fed_ordinary_tax:>9,.0f}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — LTCG BRACKET (stacked on top of taxable ordinary)
# ─────────────────────────────────────────────────────────────────────────────

print("STEP 6 — LTCG BRACKET (stacked on taxable ordinary income)")
print("-" * 70)
print(f"  Taxable ordinary = ${taxable_ordinary:,.0f}  |  "
      f"0% LTCG threshold = $95,375  |  "
      f"0% space remaining = ${max(0, 95375 - taxable_ordinary):,.0f}")
print()
print(f"  {'Bracket':<35} {'LTCG':>10} {'Rate':>6} {'Tax':>10}")
print(f"  {'─'*63}")

ltcg_alloc = fill_ltcg_brackets(brokerage_sold_gain, taxable_ordinary, ltcg_brackets_2027)
fed_ltcg_tax = 0
for a in ltcg_alloc:
    print(f"  {a['name']+' LTCG Bracket':<35} ${a['fill']:>9,.0f} {a['rate']*100:>5.0f}% ${a['tax']:>9,.0f}")
    fed_ltcg_tax += a['tax']
sep()
print(f"  {'Federal LTCG Tax':<35} {'':>10} {'':>6} ${fed_ltcg_tax:>9,.0f}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — PA STATE TAX
# ─────────────────────────────────────────────────────────────────────────────

print("STEP 7 — PENNSYLVANIA STATE TAX")
print("-" * 70)
pa_tax = taxable_ordinary * pa_rate
print(f"  Ordinary income ${taxable_ordinary:,.0f} × {pa_rate*100:.2f}%:  ${pa_tax:,.0f}")
print(f"  LTCG (PA does not tax LTCG):       $0")
print()

# ─────────────────────────────────────────────────────────────────────────────
# TOTALS & SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

total_fed  = fed_ordinary_tax + fed_ltcg_tax
total_tax  = total_fed + pa_tax

print("=" * 70)
print("FINAL SUMMARY")
print("=" * 70)
print()
print(f"  WITHDRAWALS:")
print(f"  {'Traditional (spending)':<44} ${trad_spending:>10,.0f}")
if roth_conversion > 0:
    print(f"  {'Roth Conversion':<44} ${roth_conversion:>10,.0f}")
print(f"  {'Brokerage sold (delta)':<44} ${brokerage_sold_basis + brokerage_sold_gain:>10,.0f}")
print(f"  {'Brokerage → DAF (stock transfer)':<44} ${daf_fmv:>10,.0f}  (no tax)")
sep()
total_withdrawals = trad_spending + roth_conversion + brokerage_sold_basis + brokerage_sold_gain + daf_fmv
print(f"  {'Total Withdrawals (incl. DAF)':<44} ${total_withdrawals:>10,.0f}")
print()
print(f"  AGI COMPONENTS:")
print(f"  {'Gross ordinary income':<44} ${gross_ordinary:>10,.0f}")
print(f"  {'LTCG':<44} ${brokerage_sold_gain:>10,.0f}")
print(f"  {'Pre-deduction AGI':<44} ${agi_gross:>10,.0f}")
print(f"  {'Deduction (' + deduction_type + ')':<44} ${deduction:>10,.0f}")
print(f"  {'Taxable ordinary income':<44} ${taxable_ordinary:>10,.0f}")
print()
print(f"  TAXES:")
print(f"  {'Federal ordinary income tax':<44} ${fed_ordinary_tax:>10,.0f}")
print(f"  {'Federal LTCG tax':<44} ${fed_ltcg_tax:>10,.0f}")
print(f"  {'PA state income tax':<44} ${pa_tax:>10,.0f}")
sep()
print(f"  {'TOTAL TAX OWED 2027':<44} ${total_tax:>10,.0f}")
print()

# Bracket utilization
bracket_12_used = next((a['fill'] for a in alloc if a['name'] == '12%'), 0)
bracket_12_total = 100800 - 24800
bracket_12_remain = bracket_12_total - bracket_12_used

print(f"  BRACKET UTILIZATION:")
print(f"  {'Standard/Itemized Deduction':<44} ${deduction:>10,.0f}")
for a in alloc:
    width = brackets_2027[[b['name'] for b in brackets_2027].index(a['name'])]['upper'] - \
            brackets_2027[[b['name'] for b in brackets_2027].index(a['name'])]['lower']
    print(f"  {a['name']+' Bracket used':<44} ${a['fill']:>10,.0f} / ${width:,.0f}")
print(f"  {'12% Bracket remaining (Roth opportunity)':<44} ${bracket_12_remain:>10,.0f}")
ltcg_0pct_space = max(0, 95375 - taxable_ordinary)
print(f"  {'0% LTCG space remaining':<44} ${ltcg_0pct_space:>10,.0f}")
print()

if bracket_12_remain > 0:
    roth_tax_at_12 = bracket_12_remain * 0.12
    print(f"  → Converting ${bracket_12_remain:,.0f} to Roth would cost ${roth_tax_at_12:,.0f} (12% federal)")
    print(f"    and an additional ${bracket_12_remain * pa_rate:,.0f} PA state tax")
    print(f"    Total conversion tax: ${roth_tax_at_12 + bracket_12_remain * pa_rate:,.0f}")
    print(f"    Effective rate on conversion: {(roth_tax_at_12 + bracket_12_remain * pa_rate) / bracket_12_remain * 100:.1f}%")
print()
print(f"  DAF CARRYFORWARD TO 2028–2032: ${daf_carryforward:,.0f}")
