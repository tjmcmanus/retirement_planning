# Estate Tax Calculations Guide

## Overview

The Estate Tax Calculations module provides comprehensive estate tax planning and analysis, including:

- **Federal Estate Tax** calculations with current exemptions
- **TCJA Sunset Modeling** showing the impact of exemption reductions in 2026
- **State Estate Taxes** for 13 states with estate taxes
- **Inheritance Taxes** for 6 states with inheritance taxes
- **Generation-Skipping Transfer Tax (GSTT)** analysis
- **Portability** calculations for married couples
- **Lifetime Gift** tracking and impact analysis

## Features

### 1. Federal Estate Tax Calculations

The module calculates federal estate tax based on:

- **Gross Estate Value**: Total value of all assets
- **Federal Exemption**: $13.61M (2024), reducing to ~$7.1M in 2026
- **Tax Rate**: Flat 40% on amounts above exemption
- **Prior Gifts**: Tracks lifetime gifts that used exemption
- **Portability**: Unused exemption from deceased spouse

#### TCJA Sunset Impact

The Tax Cuts and Jobs Act (TCJA) doubled the estate tax exemption from 2018-2025. Starting in 2026, the exemption will revert to approximately half the current level:

| Year | Exemption | TCJA Status |
|------|-----------|-------------|
| 2024 | $13,610,000 | In Effect |
| 2025 | $13,990,000 | In Effect |
| 2026 | $7,110,000 | **Sunset** |
| 2027 | $7,320,000 | Post-Sunset |

**Example Impact:**
- Estate Value: $15,000,000
- 2025 Tax: $404,000 (2.7% effective rate)
- 2026 Tax: $3,156,000 (21.0% effective rate)
- **Tax Increase: $2,752,000**

### 2. State Estate Taxes

The module supports 13 states with estate taxes:

#### States with Estate Taxes (2024)

| State | Exemption | Top Rate | Notes |
|-------|-----------|----------|-------|
| Connecticut | $13,610,000 | 12% | Matches federal |
| District of Columbia | $4,528,800 | 16% | Progressive rates |
| Hawaii | $5,490,000 | 20% | Progressive rates |
| Illinois | $4,000,000 | 16% | Flat rate |
| Maine | $6,410,000 | 12% | Progressive rates |
| Maryland | $5,000,000 | 16% | Also has inheritance tax |
| Massachusetts | $2,000,000 | 16% | **Cliff tax** - lowest exemption |
| Minnesota | $3,000,000 | 16% | Progressive rates |
| New York | $6,940,000 | 16% | **Cliff tax** at 105% |
| Oregon | $1,000,000 | 16% | **Lowest exemption** |
| Rhode Island | $1,733,264 | 16% | Flat rate |
| Vermont | $5,000,000 | 16% | Flat rate |
| Washington | $2,193,000 | 20% | Progressive rates |

#### Special State Rules

**Massachusetts Cliff Tax:**
- If estate exceeds $2M, the **entire estate** is taxable (no exemption)
- Example: $2.1M estate pays tax on full $2.1M, not just $100K

**New York Cliff Tax:**
- If estate exceeds 105% of exemption ($7.287M), maximum rate applies to entire estate
- Example: $7.5M estate pays 16% on full $7.5M = $1.2M tax

### 3. Inheritance Taxes

Six states impose inheritance taxes (paid by beneficiaries, not the estate):

| State | Spouse | Children | Siblings | Other |
|-------|--------|----------|----------|-------|
| Iowa | Exempt | Exempt | 5% | 10% |
| Kentucky | Exempt | Exempt | 4-16% | 6-16% |
| Maryland | Exempt | Exempt | 10% | 10% |
| Nebraska | Exempt | 1% | 13% | 18% |
| New Jersey | Exempt | Exempt | 11-16% | 15-16% |
| Pennsylvania | Exempt | 4.5% | 12% | 15% |

**Key Points:**
- Spouses are always exempt
- Children are exempt in most states
- Rates increase for more distant relationships
- Some states have exemption amounts per beneficiary

### 4. Generation-Skipping Transfer Tax (GSTT)

GSTT applies to transfers to beneficiaries two or more generations below the transferor (e.g., grandchildren):

- **Exemption**: Same as estate tax exemption ($13.61M in 2024)
- **Tax Rate**: Flat 40%
- **Purpose**: Prevents avoiding estate tax by skipping a generation
- **Sunset Impact**: GSTT exemption also reduces in 2026

**Example:**
- Transfer to grandchildren: $20M
- GSTT Exemption (2024): $13.61M
- Taxable Amount: $6.39M
- GSTT Tax: $2.556M (40%)

### 5. Portability

Portability allows a surviving spouse to use the deceased spouse's unused estate tax exemption:

**How It Works:**
1. First spouse dies with $5M estate
2. Unused exemption: $13.61M - $5M = $8.61M
3. Surviving spouse's total exemption: $13.61M + $8.61M = $22.22M

**Requirements:**
- Must file Form 706 (estate tax return) within 9 months of death
- Election must be made even if no tax is owed
- Only applies to most recent deceased spouse

## Using the Estate Tax Calculator

### Access

Navigate to: **Estate Planning → Estate Tax Calculator** tab

### Basic Calculation

1. **Enter Estate Information:**
   - Gross Estate Value
   - Year of Death (for projections)
   - Prior Lifetime Gifts
   - State of Residence
   - Portability from Spouse
   - Skip Person Transfers

2. **Add Beneficiaries** (if in inheritance tax state):
   - Name
   - Relationship
   - Inheritance Amount

3. **Click "Calculate Estate Taxes"**

### Results Display

The calculator shows:

- **Summary Metrics:**
  - Gross Estate
  - Total Tax Burden
  - Net to Heirs
  - Effective Tax Rate

- **Detailed Breakdown:**
  - Federal estate tax
  - State estate tax (if applicable)
  - Inheritance tax by beneficiary
  - GSTT (if applicable)

### TCJA Sunset Analysis

Click **"Analyze TCJA Sunset Impact"** to see:

- Side-by-side comparison of 2025 vs 2026
- Exemption reduction amount
- Tax increase amount
- Net reduction to heirs

## Planning Strategies

### 1. Lifetime Gifting

**Annual Exclusion Gifts:**
- $18,000 per recipient per year (2024)
- No gift tax or exemption use
- Unlimited recipients

**Example:**
- 3 children, 6 grandchildren = 9 recipients
- Annual gifts: $18,000 × 9 = $162,000/year
- 10 years: $1,620,000 removed from estate tax-free

### 2. Use Exemption Before 2026

If estate exceeds $7.1M, consider making large gifts before 2026:

**Strategy:**
- Make gifts up to current exemption ($13.61M)
- Locks in higher exemption before sunset
- IRS has confirmed no "clawback" of gifts made before 2026

**Example:**
- Estate: $20M
- Gift $10M in 2025 (uses exemption)
- Remaining estate in 2026: $10M
- 2026 exemption: $7.1M
- Taxable: $2.9M
- Tax: $1.16M

**Without gifting:**
- Estate in 2026: $20M
- Exemption: $7.1M
- Taxable: $12.9M
- Tax: $5.16M
- **Savings: $4M**

### 3. Irrevocable Life Insurance Trust (ILIT)

Remove life insurance proceeds from taxable estate:

- Transfer policy to ILIT
- ILIT owns policy and is beneficiary
- Proceeds not included in estate
- Can provide liquidity for estate taxes

### 4. Grantor Retained Annuity Trust (GRAT)

Transfer appreciating assets with minimal gift tax:

- Transfer assets to GRAT
- Receive annuity payments for term
- Remaining value passes to beneficiaries
- Effective for high-growth assets

### 5. Charitable Giving

Reduce estate tax while supporting causes:

- **Charitable Remainder Trust (CRT)**: Income for life, remainder to charity
- **Charitable Lead Trust (CLT)**: Income to charity, remainder to heirs
- **Donor Advised Fund (DAF)**: Immediate deduction, flexible giving

### 6. State Planning

For high-tax states, consider:

- **Domicile Change**: Move to no-estate-tax state
- **Asset Situs**: Hold real estate in LLC in low-tax state
- **Trust Situs**: Establish trusts in favorable jurisdictions

## API Reference

### Main Functions

#### `calculate_federal_estate_tax()`

```python
from estate_tax_calculations import calculate_federal_estate_tax

result = calculate_federal_estate_tax(
    gross_estate=15_000_000,
    year=2024,
    prior_exemption_used=2_000_000,
    portability_from_spouse=5_000_000,
)

print(f"Estate Tax: ${result.estate_tax:,.0f}")
print(f"Effective Rate: {result.effective_rate:.2%}")
```

#### `calculate_state_estate_tax()`

```python
from estate_tax_calculations import calculate_state_estate_tax

result = calculate_state_estate_tax(
    gross_estate=10_000_000,
    state_code='NY',
    year=2024,
)

if result:
    print(f"State Tax: ${result.estate_tax:,.0f}")
```

#### `calculate_comprehensive_estate_tax()`

```python
from estate_tax_calculations import calculate_comprehensive_estate_tax

beneficiaries = [
    {'name': 'Child 1', 'relationship': 'child', 'amount': 3_000_000},
    {'name': 'Child 2', 'relationship': 'child', 'amount': 3_000_000},
]

result = calculate_comprehensive_estate_tax(
    gross_estate=20_000_000,
    year=2024,
    state_code='PA',
    beneficiaries=beneficiaries,
    skip_person_transfers=5_000_000,
    prior_exemption_used=2_000_000,
)

print(f"Total Tax Burden: ${result.total_tax_burden:,.0f}")
print(f"Net to Heirs: ${result.net_to_heirs:,.0f}")
```

#### `compare_tcja_sunset_impact()`

```python
from estate_tax_calculations import compare_tcja_sunset_impact

comparison = compare_tcja_sunset_impact(
    gross_estate=15_000_000,
    state_code='NY',
)

print(f"2025 Tax: ${comparison['year_2025']['total_tax']:,.0f}")
print(f"2026 Tax: ${comparison['year_2026']['total_tax']:,.0f}")
print(f"Increase: ${comparison['impact']['tax_increase']:,.0f}")
```

## Testing

Run the comprehensive test suite:

```bash
pytest test_estate_tax_calculations.py -v
```

Test coverage includes:
- Federal estate tax calculations
- TCJA sunset modeling
- State estate taxes (all 13 states)
- Inheritance taxes (all 6 states)
- GSTT calculations
- Portability scenarios
- Edge cases and boundary conditions

## Important Disclaimers

⚠️ **This tool is for educational and planning purposes only.**

- **Not Legal Advice**: Consult with a qualified estate planning attorney
- **Not Tax Advice**: Consult with a tax professional or CPA
- **Projections**: Future exemptions and rates are estimates
- **State Laws**: State tax laws change frequently
- **Individual Circumstances**: Every situation is unique

## Resources

### IRS Resources

- [Estate Tax](https://www.irs.gov/businesses/small-businesses-self-employed/estate-tax)
- [Form 706 Instructions](https://www.irs.gov/forms-pubs/about-form-706)
- [Generation-Skipping Transfer Tax](https://www.irs.gov/businesses/small-businesses-self-employed/generation-skipping-transfer-tax)
- [Portability Election](https://www.irs.gov/instructions/i706#idm140506478848768)

### State Resources

- [State Estate Tax Chart](https://www.tax-rates.org/taxtables/estate-tax-by-state)
- [State Inheritance Tax Information](https://www.thebalancemoney.com/state-inheritance-taxes-3505635)

### Professional Organizations

- [American College of Trust and Estate Counsel (ACTEC)](https://www.actec.org/)
- [National Association of Estate Planners & Councils (NAEPC)](https://www.naepc.org/)

## Frequently Asked Questions

### Q: When does the TCJA sunset take effect?

**A:** January 1, 2026. Deaths occurring on or after this date will use the reduced exemption (~$7.1M).

### Q: Can I make large gifts now and avoid the 2026 reduction?

**A:** Yes. The IRS has confirmed that gifts made before 2026 using the higher exemption will not be "clawed back" after the sunset.

### Q: What is portability and how do I claim it?

**A:** Portability allows a surviving spouse to use the deceased spouse's unused exemption. You must file Form 706 within 9 months of death to elect portability, even if no tax is owed.

### Q: Do I need to file an estate tax return?

**A:** You must file Form 706 if:
- Gross estate exceeds the exemption amount
- You want to elect portability for surviving spouse
- You made certain lifetime gifts

### Q: How do state estate taxes interact with federal taxes?

**A:** State estate taxes are separate from federal taxes. You may owe both. However, state estate taxes paid are deductible on the federal return.

### Q: What is the difference between estate tax and inheritance tax?

**A:**
- **Estate Tax**: Paid by the estate before distribution (federal + 13 states)
- **Inheritance Tax**: Paid by beneficiaries after receiving inheritance (6 states)

### Q: Can I avoid estate tax by giving everything away before death?

**A:** Large gifts use your lifetime exemption (same as estate tax exemption). However, annual exclusion gifts ($18,000/recipient/year) don't use exemption.

### Q: What happens if I move to a different state?

**A:** Estate tax is based on domicile at death. Changing domicile can affect state estate tax, but requires establishing new domicile (residence, voter registration, driver's license, etc.).

## Version History

- **v1.0** (2026-03-20): Initial release
  - Federal estate tax calculations
  - TCJA sunset modeling
  - State estate and inheritance taxes
  - GSTT analysis
  - Comprehensive estate tax calculator UI

## Support

For questions or issues:
1. Review this documentation
2. Check the test suite for examples
3. Consult with qualified professionals for your specific situation

---

**Last Updated:** March 20, 2026