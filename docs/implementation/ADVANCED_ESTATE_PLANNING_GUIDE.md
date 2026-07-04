# Advanced Estate Planning Integration Guide

## Overview

This guide covers the complete advanced estate planning features integrated into the retirement planning application, including estate tax calculations, beneficiary optimization, and charitable giving strategies.

## Table of Contents

1. [Estate Tax Calculations](#estate-tax-calculations)
2. [Beneficiary Optimization](#beneficiary-optimization)
3. [Charitable Giving Strategies](#charitable-giving-strategies)
4. [Integration Architecture](#integration-architecture)
5. [Usage Examples](#usage-examples)
6. [API Reference](#api-reference)
7. [Best Practices](#best-practices)

---

## Estate Tax Calculations

### Overview

The estate tax calculation module provides comprehensive federal and state estate tax analysis with TCJA sunset modeling.

### Key Features

#### 1. Federal Estate Tax
- **Current Exemption:** $13.61M (2024)
- **TCJA Sunset:** Drops to ~$7.1M in 2026
- **Tax Rate:** Flat 40% above exemption
- **Portability:** Surviving spouse can use deceased spouse's unused exemption

#### 2. State Estate Taxes (13 States)
| State | Exemption | Top Rate | Special Rules |
|-------|-----------|----------|---------------|
| Massachusetts | $2.0M | 16% | **Cliff tax** - entire estate taxable if over threshold |
| Oregon | $1.0M | 16% | Lowest exemption in nation |
| New York | $6.94M | 16% | **Cliff tax** if estate > 105% of exemption |
| Connecticut | $13.61M | 12% | Matches federal exemption |
| Washington | $2.19M | 20% | Progressive rates 10%-20% |

#### 3. Inheritance Taxes (6 States)
Paid by beneficiaries based on relationship:
- **Pennsylvania:** 4.5% (children), 12% (siblings), 15% (other)
- **New Jersey:** 11-16% (siblings), 15-16% (other)
- **Maryland:** 10% (non-lineal heirs) - also has estate tax

#### 4. Generation-Skipping Transfer Tax (GSTT)
- **Exemption:** Same as estate tax ($13.61M in 2024)
- **Rate:** Flat 40%
- **Applies to:** Transfers to grandchildren or skip persons

### TCJA Sunset Impact

**Example Scenario:**
```
Estate Value: $15,000,000
State: New York

2025 (TCJA in effect):
- Federal Exemption: $13,990,000
- Federal Tax: $404,000
- State Tax: $1,280,000
- Total Tax: $1,684,000 (11.2%)

2026 (TCJA sunset):
- Federal Exemption: $7,110,000
- Federal Tax: $3,156,000
- State Tax: $1,280,000
- Total Tax: $4,436,000 (29.6%)

Impact: +$2,752,000 tax increase
```

### Using the Estate Tax Calculator

**Access:** Estate Planning → Estate Tax Calculator tab

**Steps:**
1. Enter gross estate value
2. Select year of death (for projections)
3. Enter prior lifetime gifts
4. Select state of residence
5. Add portability from spouse (if applicable)
6. Enter skip person transfers (for GSTT)
7. Add beneficiaries (for inheritance tax)
8. Click "Calculate Estate Taxes"

**Results Display:**
- Summary metrics (gross estate, total tax, net to heirs, effective rate)
- Federal estate tax breakdown
- State estate tax (if applicable)
- Inheritance tax by beneficiary
- GSTT (if applicable)

**TCJA Sunset Analysis:**
- Click "Analyze TCJA Sunset Impact"
- See side-by-side comparison of 2025 vs 2026
- View exemption reduction and tax increase
- Get planning recommendations

---

## Beneficiary Optimization

### Overview

The beneficiary optimization module provides SECURE Act 2.0 compliant analysis of inherited IRA strategies.

### SECURE Act 2.0 Changes

#### RMD Age Changes
- **2023-2032:** Age 73
- **2033+:** Age 75

#### 10-Year Rule (Non-Spouse Beneficiaries)
- Must withdraw entire IRA balance within 10 years
- No annual RMD requirements
- Applies to deaths after December 31, 2019

#### Eligible Designated Beneficiaries (EDBs)
Can still use stretch IRA:
1. **Surviving spouse** (always EDB)
2. **Minor children** (until age 21)
3. **Disabled individuals**
4. **Chronically ill individuals**
5. **Individuals not more than 10 years younger than owner**

### Beneficiary Strategies

#### 1. 10-Year Rule Analysis

**When to Use:**
- Non-spouse beneficiary
- Not an EDB
- Want to optimize tax impact

**Strategy Options:**
- **Equal annual distributions:** Minimize bracket creep
- **Defer to year 10:** Maximize tax-deferred growth
- **Front-load distributions:** If expecting higher future tax rates

**Example:**
```python
from beneficiary_optimization import calculate_inherited_ira_10_year_rule

result = calculate_inherited_ira_10_year_rule(
    initial_balance=500_000,
    beneficiary_age=45,
    beneficiary_tax_rate=0.24,
    annual_growth_rate=0.07,
)

print(f"Total Distributions: ${result.total_distributions:,.0f}")
print(f"Total Taxes: ${result.total_taxes_paid:,.0f}")
print(f"Net to Beneficiary: ${result.net_to_beneficiary:,.0f}")
```

#### 2. Stretch IRA (EDBs Only)

**Benefits:**
- Distributions based on life expectancy
- Decades of tax-deferred growth
- Lower annual distributions = lower taxes

**Example:**
```python
from beneficiary_optimization import calculate_stretch_ira

result = calculate_stretch_ira(
    initial_balance=500_000,
    beneficiary_age=45,
    beneficiary_tax_rate=0.24,
)

print(f"Years of Distributions: {result.years_of_distributions}")
print(f"Total Distributions: ${result.total_distributions:,.0f}")
print(f"Total Growth: ${result.total_growth:,.0f}")
```

#### 3. Spousal Options Comparison

**Option 1: Rollover to Own IRA**
- Treat as own IRA
- RMDs start at age 73/75
- Can name own beneficiaries
- Best if: Spouse under RMD age

**Option 2: Remain as Beneficiary**
- Take distributions based on life expectancy
- Can access before 59.5 without penalty
- Best if: Spouse under 59.5 and needs income

**Example:**
```python
from beneficiary_optimization import compare_spousal_options

result = compare_spousal_options(
    initial_balance=800_000,
    spouse_age=62,
    spouse_tax_rate=0.24,
)

print(f"Recommended: {result.recommended_option}")
print(f"Savings: ${result.savings_amount:,.0f}")
for factor in result.key_factors:
    print(f"  • {factor}")
```

#### 4. Trust as Beneficiary

**Trust Types:**

**Conduit Trust:**
- Passes all RMDs directly to beneficiaries
- Beneficiaries pay tax at their rates
- Qualifies as designated beneficiary
- Can use stretch (if EDB)

**Accumulation Trust:**
- Can accumulate income
- Trust pays tax at trust rates (37% quickly)
- Does NOT qualify as designated beneficiary
- Must use 10-year or 5-year rule

**See-Through Trust:**
- Hybrid approach
- Some pass-through, some accumulation
- May qualify as designated beneficiary
- Complex administration

**When to Use Trusts:**
- Minor beneficiaries
- Spendthrift concerns
- Special needs beneficiaries
- Asset protection needs
- Multiple beneficiaries with different needs

**Example:**
```python
from beneficiary_optimization import calculate_trust_beneficiary

result = calculate_trust_beneficiary(
    initial_balance=1_000_000,
    trust_type='conduit',
    oldest_beneficiary_age=40,
    annual_admin_cost=5_000,
)

print(f"Net to Beneficiaries: ${result.net_to_beneficiaries:,.0f}")
print(f"Total Taxes: ${result.total_taxes_paid:,.0f}")
print(f"Admin Costs: ${result.trust_administration_costs:,.0f}")
```

### Using the Beneficiary Planning Tool

**Access:** Estate Planning → Beneficiary Planning tab

**Analysis Types:**
1. **Inherited IRA (10-Year Rule)**
   - Enter IRA balance and beneficiary age
   - Set tax rate and growth assumptions
   - View year-by-year distributions

2. **Stretch IRA (EDB)**
   - Calculate lifetime distributions
   - See tax-deferred growth benefits
   - Compare to 10-year rule

3. **Spousal Options Comparison**
   - Compare rollover vs. inherited IRA
   - Get personalized recommendation
   - See savings amount

4. **Trust as Beneficiary**
   - Model different trust types
   - Calculate tax implications
   - Include administration costs

5. **Compare Multiple Strategies**
   - Side-by-side comparison
   - Net to beneficiary rankings
   - Effective tax rate analysis

---

## Charitable Giving Strategies

### Overview

The charitable giving module provides sophisticated modeling of charitable remainder trusts, charitable lead trusts, and foundation vs. DAF comparisons.

### Charitable Remainder Trusts (CRT)

#### CRUT (Charitable Remainder Unitrust)

**How It Works:**
1. Transfer assets to irrevocable trust
2. Receive annual payments (% of trust value, revalued annually)
3. Payments for life or term of years
4. Remainder goes to charity

**Benefits:**
- Immediate income tax deduction (present value of remainder)
- Avoid capital gains tax on appreciated assets
- Income stream for life
- Estate tax reduction
- Inflation protection (payments grow with trust value)

**Requirements:**
- Minimum payout: 5%
- Maximum payout: 50%
- Minimum remainder to charity: 10% of initial value

**Example:**
```python
from charitable_giving_advanced import calculate_crt_crut

result = calculate_crt_crut(
    initial_funding=1_000_000,
    payout_rate=0.05,  # 5%
    term_years=20,
    donor_age=65,
    donor_tax_rate=0.24,
)

print(f"Total Income: ${result.total_income_received:,.0f}")
print(f"Net Income: ${result.net_income_to_donor:,.0f}")
print(f"To Charity: ${result.charitable_remainder:,.0f}")
print(f"Tax Savings: ${result.effective_tax_savings:,.0f}")
```

#### CRAT (Charitable Remainder Annuity Trust)

**How It Works:**
- Same as CRUT but fixed dollar payment
- No revaluation
- Predictable income but no inflation protection

**Best For:**
- Donors wanting predictable income
- Conservative planning
- Shorter terms

### Charitable Lead Trusts (CLT)

#### CLUT (Charitable Lead Unitrust)

**How It Works:**
1. Transfer assets to trust
2. Charity receives annual payments (% of trust value)
3. After term, remainder goes to heirs
4. Reduces gift/estate tax

**Benefits:**
- Transfer wealth to heirs at reduced tax cost
- Support charity during term
- Estate tax reduction
- Potential for "zeroed-out" CLAT

**Example:**
```python
from charitable_giving_advanced import calculate_clt_clut

result = calculate_clt_clut(
    initial_funding=2_000_000,
    payout_rate=0.05,
    term_years=15,
    estate_tax_rate=0.40,
)

print(f"To Charity: ${result.total_to_charity:,.0f}")
print(f"To Heirs: ${result.remainder_to_heirs:,.0f}")
print(f"Estate Tax Savings: ${result.estate_tax_savings:,.0f}")
```

#### CLAT (Charitable Lead Annuity Trust)

**How It Works:**
- Fixed dollar payment to charity
- Remainder to heirs
- Can be "zeroed-out" (no gift tax)

**Zeroed-Out CLAT:**
- Payment amount set so present value of remainder = $0
- No gift tax on transfer to heirs
- Heirs receive all growth above AFR

### Private Foundation vs. Donor Advised Fund

#### Private Foundation

**Advantages:**
- Maximum control over investments and grants
- Can employ family members
- Perpetual existence
- Family legacy

**Disadvantages:**
- High setup costs ($10,000-$50,000)
- Annual admin costs ($25,000-$100,000+)
- Excise tax on investment income (1.39%)
- Minimum distribution requirement (5%)
- Complex compliance (Form 990-PF)
- Public disclosure

**Best For:**
- Assets > $5M
- Desire for maximum control
- Multi-generational planning
- Employing family members

#### Donor Advised Fund (DAF)

**Advantages:**
- Low setup costs ($0)
- Low annual fees (0.6% typical)
- No excise taxes
- Simple administration
- Immediate tax deduction
- Privacy

**Disadvantages:**
- Less control (sponsor has legal control)
- Cannot employ family
- Cannot make grants to individuals
- May have investment restrictions

**Best For:**
- Assets < $5M
- Simplicity priority
- Lower costs
- Flexibility

**Comparison Example:**
```python
from charitable_giving_advanced import compare_foundation_vs_daf

result = compare_foundation_vs_daf(
    contribution_amount=5_000_000,
    years=20,
)

print(f"Recommended: {result.recommended_strategy}")
print("\nKey Factors:")
for factor in result.key_factors:
    print(f"  • {factor}")

print("\nTax Efficiency Ranking:")
for i, (strategy, efficiency) in enumerate(result.tax_efficiency_ranking, 1):
    print(f"  {i}. {strategy}: {efficiency:.2%}")
```

### Qualified Charitable Distributions (QCD)

**How It Works:**
- Direct transfer from IRA to charity
- Up to $105,000/year (2024)
- Must be age 70.5+
- Satisfies RMD
- Not included in taxable income

**Benefits:**
- Reduce taxable income
- Avoid IRMAA surcharges
- Satisfy RMD without tax
- Simple process

**Example:**
```python
from charitable_giving_advanced import calculate_qcd_benefit

result = calculate_qcd_benefit(
    ira_balance=500_000,
    donor_age=72,
    qcd_amount=50_000,
    marginal_tax_rate=0.24,
)

if result['eligible']:
    print(f"Tax Savings: ${result['tax_savings']:,.0f}")
    print(f"IRMAA Savings: ${result['irmaa_savings']:,.0f}")
    print(f"Total Benefit: ${result['total_benefit']:,.0f}")
```

### Using the Charitable Giving Tool

**Access:** Estate Planning → Charitable Giving tab

**Strategy Options:**
1. **CRUT Analysis**
   - Model income stream
   - Calculate tax benefits
   - Project charitable remainder

2. **CRAT Analysis**
   - Fixed payment modeling
   - Depletion analysis
   - Tax deduction calculation

3. **CLUT/CLAT Analysis**
   - Estate tax savings
   - Remainder to heirs
   - Gift tax implications

4. **Foundation vs. DAF**
   - Cost comparison
   - Grant efficiency
   - Control vs. simplicity

5. **QCD Benefit Analysis**
   - Tax savings calculation
   - IRMAA impact
   - RMD satisfaction

---

## Integration Architecture

### Module Structure

```
estate_tax_calculations.py (1,089 lines)
├── Federal estate tax
├── State estate taxes (13 states)
├── Inheritance taxes (6 states)
├── GSTT calculations
└── Comprehensive analysis

beneficiary_optimization.py (847 lines)
├── 10-year rule
├── Stretch IRA
├── Spousal options
├── Trust beneficiaries
└── Strategy comparison

charitable_giving_advanced.py (752 lines)
├── CRT (CRUT/CRAT)
├── CLT (CLUT/CLAT)
├── Private Foundation
├── DAF
└── QCD analysis
```

### Data Flow

```
User Input (Estate Planning Page)
    ↓
Calculation Modules
    ↓
Result Objects (NamedTuples)
    ↓
UI Display (Streamlit)
    ↓
Session State (Persistence)
```

### Integration Points

1. **Estate Planning Page** (`pages/1_estate_planning.py`)
   - Imports all three modules
   - Provides interactive UI
   - Manages session state
   - Displays results

2. **Configuration System** (`config.py`)
   - Personal information
   - Account data
   - Property information

3. **Portfolio Data** (`portfolio.py`)
   - Account balances
   - Asset allocation
   - Cost basis tracking

---

## Usage Examples

### Complete Estate Analysis

```python
from estate_tax_calculations import calculate_comprehensive_estate_tax
from beneficiary_optimization import compare_spousal_options
from charitable_giving_advanced import calculate_crt_crut

# 1. Calculate estate taxes
estate_result = calculate_comprehensive_estate_tax(
    gross_estate=20_000_000,
    year=2026,
    state_code='NY',
    beneficiaries=[
        {'name': 'Child 1', 'relationship': 'child', 'amount': 5_000_000},
        {'name': 'Child 2', 'relationship': 'child', 'amount': 5_000_000},
    ],
    skip_person_transfers=3_000_000,  # To grandchildren
)

print(f"Total Tax Burden: ${estate_result.total_tax_burden:,.0f}")
print(f"Net to Heirs: ${estate_result.net_to_heirs:,.0f}")

# 2. Analyze spousal IRA options
spousal_result = compare_spousal_options(
    initial_balance=2_000_000,
    spouse_age=62,
    spouse_tax_rate=0.24,
)

print(f"\nRecommended: {spousal_result.recommended_option}")
print(f"Savings: ${spousal_result.savings_amount:,.0f}")

# 3. Model charitable remainder trust
crt_result = calculate_crt_crut(
    initial_funding=3_000_000,
    payout_rate=0.05,
    term_years=20,
    donor_age=65,
)

print(f"\nCRT Income: ${crt_result.total_income_received:,.0f}")
print(f"To Charity: ${crt_result.charitable_remainder:,.0f}")
print(f"Tax Savings: ${crt_result.effective_tax_savings:,.0f}")
```

---

## Best Practices

### Estate Tax Planning

1. **Review Annually**
   - Estate values change
   - Tax laws change
   - Family situations change

2. **Use TCJA Window**
   - Make large gifts before 2026
   - Lock in higher exemption
   - No clawback confirmed by IRS

3. **Consider State Taxes**
   - Some states have low exemptions
   - Cliff taxes can be brutal
   - Domicile planning may help

4. **Portability Election**
   - File Form 706 even if no tax owed
   - Preserve spouse's exemption
   - Must file within 9 months

### Beneficiary Planning

1. **Review Beneficiary Designations**
   - Check all retirement accounts
   - Update after life events
   - Consider contingent beneficiaries

2. **Understand SECURE Act**
   - 10-year rule is default
   - EDB status is valuable
   - Plan distributions strategically

3. **Consider Trusts Carefully**
   - High administration costs
   - Complex tax rules
   - May lose stretch benefits

4. **Spousal Planning**
   - Rollover usually best if under RMD age
   - Inherited IRA if under 59.5 and need income
   - Run the numbers for your situation

### Charitable Giving

1. **Start with Goals**
   - Income needs?
   - Estate tax reduction?
   - Charitable intent?

2. **Consider Timing**
   - High-income years for deductions
   - Appreciated assets for CRTs
   - QCDs after age 70.5

3. **Compare Strategies**
   - CRT for income + charity
   - CLT for wealth transfer
   - DAF for simplicity
   - Foundation for control

4. **Professional Advice**
   - Complex tax rules
   - Irrevocable decisions
   - Consult attorney and CPA

---

## Disclaimer

This tool is for educational and planning purposes only. It is not legal or tax advice. Consult with qualified professionals (estate planning attorney, CPA, CFP) for your specific situation.

---

## Support

For questions or issues:
1. Review this documentation
2. Check the test suites for examples
3. Consult with qualified professionals

---

**Last Updated:** March 20, 2026
**Version:** 1.0