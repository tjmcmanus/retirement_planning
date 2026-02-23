# BETR Roth Conversion Algorithm Guide

## Overview

The BETR (Break-Even Tax Rate) Roth Conversion Algorithm is based on Vanguard's research paper "A 'BETR' approach to Roth conversions" (July 2025). This module provides a sophisticated framework for analyzing Roth conversion decisions that goes beyond simple current vs. future tax rate comparisons.

## What is BETR?

The **Break-Even Tax Rate (BETR)** is the future tax rate at which an investor would be indifferent between:
1. Converting to a Roth IRA now, or
2. Keeping funds in a Traditional IRA

### Key Insight

If your **expected future tax rate is ABOVE the BETR**, a Roth conversion is beneficial. The BETR is the break-even point - if you expect your future tax rate to exceed this threshold, conversion makes financial sense. The BETR accounts for factors that traditional analysis misses:

- **Tax payment source**: Paying from a taxable account vs. from IRA assets
- **Nontaxable basis**: After-tax contributions in Traditional IRA
- **Future opportunities**: Enabling backdoor Roth contributions
- **Time value**: Years until withdrawal and investment growth

## Installation

The module is already integrated into your retirement planning application. No additional installation is required.

## Quick Start

### Basic Usage

```python
from betr_roth_conversion import BETRInputs, calculate_betr, print_betr_report

# Define your conversion scenario
inputs = BETRInputs(
    current_marginal_rate=0.24,        # 24% current tax bracket
    expected_future_rate=0.22,         # Expect 22% in retirement
    conversion_amount=50000,           # Convert $50,000
    traditional_ira_balance=500000,    # Total IRA balance
    pay_from_taxable=True,             # Pay tax from taxable account
    taxable_account_balance=200000,    # Taxable account balance
    years_to_withdrawal=20,            # 20 years until withdrawal
    annual_return=0.07                 # 7% expected return
)

# Calculate BETR
results = calculate_betr(inputs)

# Print detailed report
print_betr_report(results, inputs)
```

### Optimize Conversion Amount

```python
from betr_roth_conversion import optimize_conversion_amount

# Find optimal conversion to stay in 24% bracket
optimal_amount, betr_results = optimize_conversion_amount(
    traditional_ira_balance=500000,
    current_agi=150000,
    target_tax_bracket=0.24,
    year=2026,
    pay_from_taxable=True,
    taxable_account_balance=200000
)

print(f"Optimal conversion: ${optimal_amount:,.0f}")
print(f"BETR: {betr_results.betr:.2%}")
print(f"Recommended: {betr_results.conversion_recommended}")
```

### Analyze Multiple Scenarios

```python
from betr_roth_conversion import analyze_conversion_scenarios

# Compare different conversion amounts
scenarios_df = analyze_conversion_scenarios(
    traditional_ira_balance=500000,
    conversion_amounts=[25000, 50000, 75000, 100000],
    current_marginal_rate=0.24,
    expected_future_rate=0.22,
    pay_from_taxable=True,
    taxable_account_balance=200000
)

print(scenarios_df)
```

## Core Concepts

### 1. Tax Payment Source Matters

**Paying from Taxable Account (Recommended)**
- Moves tax-inefficient dollars to tax-advantaged space
- Full conversion amount grows tax-free in Roth
- Higher BETR (more favorable for conversion)

**Paying from IRA**
- Reduces amount that can be converted
- Less favorable but still may be beneficial
- Lower BETR

### 2. Nontaxable Basis

If you have after-tax contributions in your Traditional IRA:
- Only the taxable portion is subject to conversion tax
- Increases BETR (makes conversion more attractive)
- Important for those who made non-deductible IRA contributions

### 3. Future Backdoor Roth Contributions

Converting now can enable future backdoor Roth contributions by:
- Eliminating pro-rata rule complications
- Allowing clean backdoor conversions going forward
- This benefit increases BETR

## API Reference

### BETRInputs

Dataclass containing all input parameters for BETR calculation.

**Required Parameters:**
- `current_marginal_rate` (float): Current marginal tax rate (e.g., 0.24 for 24%)
- `expected_future_rate` (float): Expected future marginal tax rate
- `conversion_amount` (float): Amount to convert from Traditional to Roth
- `traditional_ira_balance` (float): Total Traditional IRA balance

**Optional Parameters:**
- `nontaxable_basis` (float): Nontaxable basis in Traditional IRA (default: 0.0)
- `pay_from_taxable` (bool): Pay conversion tax from taxable account (default: True)
- `taxable_account_balance` (float): Balance in taxable account (default: 0.0)
- `years_to_withdrawal` (int): Years until withdrawal from Roth (default: 20)
- `annual_return` (float): Expected annual return (default: 0.07)
- `future_backdoor_roth` (bool): Planning future backdoor Roth (default: False)
- `backdoor_contribution_years` (int): Years of future backdoor contributions (default: 0)

### BETRResults

Dataclass containing calculation results.

**Attributes:**
- `betr` (float): Break-Even Tax Rate
- `conversion_recommended` (bool): Whether conversion is recommended
- `conversion_tax` (float): Tax owed on conversion
- `net_benefit` (float): Net benefit of conversion (present value)
- `traditional_future_value` (float): Future value if staying in Traditional IRA
- `roth_future_value` (float): Future value after Roth conversion
- `taxable_account_impact` (float): Impact on taxable account
- `analysis_notes` (List[str]): Detailed analysis notes

### calculate_betr()

Calculate the Break-Even Tax Rate for a Roth conversion.

```python
def calculate_betr(inputs: BETRInputs) -> BETRResults
```

**Parameters:**
- `inputs`: BETRInputs dataclass with all required parameters

**Returns:**
- BETRResults dataclass with BETR and detailed analysis

**Example:**
```python
inputs = BETRInputs(
    current_marginal_rate=0.24,
    expected_future_rate=0.22,
    conversion_amount=50000,
    traditional_ira_balance=500000
)
results = calculate_betr(inputs)
print(f"BETR: {results.betr:.2%}")
```

### optimize_conversion_amount()

Optimize Roth conversion amount to stay within a target tax bracket.

```python
def optimize_conversion_amount(
    traditional_ira_balance: float,
    current_agi: float,
    target_tax_bracket: float,
    year: int,
    pay_from_taxable: bool = True,
    taxable_account_balance: float = 0.0,
    nontaxable_basis: float = 0.0,
    years_to_withdrawal: int = 20,
    annual_return: float = 0.07,
    future_backdoor_roth: bool = False
) -> Tuple[float, BETRResults]
```

**Parameters:**
- `traditional_ira_balance`: Total Traditional IRA balance
- `current_agi`: Current Adjusted Gross Income
- `target_tax_bracket`: Target marginal tax rate (e.g., 0.24)
- `year`: Tax year for bracket lookup
- Additional optional parameters (see BETRInputs)

**Returns:**
- Tuple of (optimal_conversion_amount, BETRResults)

**Example:**
```python
amount, results = optimize_conversion_amount(
    traditional_ira_balance=500000,
    current_agi=150000,
    target_tax_bracket=0.24,
    year=2026
)
```

### analyze_conversion_scenarios()

Analyze multiple conversion scenarios and compare BETR values.

```python
def analyze_conversion_scenarios(
    traditional_ira_balance: float,
    conversion_amounts: List[float],
    current_marginal_rate: float,
    expected_future_rate: float,
    pay_from_taxable: bool = True,
    taxable_account_balance: float = 0.0,
    nontaxable_basis: float = 0.0,
    years_to_withdrawal: int = 20,
    annual_return: float = 0.07
) -> pd.DataFrame
```

**Parameters:**
- `traditional_ira_balance`: Total Traditional IRA balance
- `conversion_amounts`: List of conversion amounts to analyze
- `current_marginal_rate`: Current marginal tax rate
- `expected_future_rate`: Expected future marginal tax rate
- Additional optional parameters (see BETRInputs)

**Returns:**
- DataFrame with scenario analysis results

**Example:**
```python
df = analyze_conversion_scenarios(
    traditional_ira_balance=500000,
    conversion_amounts=[25000, 50000, 75000, 100000],
    current_marginal_rate=0.24,
    expected_future_rate=0.22
)
print(df[['conversion_amount', 'betr', 'recommended', 'net_benefit']])
```

### print_betr_report()

Print a formatted report of BETR analysis results.

```python
def print_betr_report(results: BETRResults, inputs: BETRInputs)
```

**Parameters:**
- `results`: BETRResults from calculate_betr()
- `inputs`: BETRInputs used for calculation

**Example:**
```python
print_betr_report(results, inputs)
```

## Integration with Existing Application

### Using with Withdrawal Strategy

```python
from betr_roth_conversion import optimize_conversion_amount
from withdrawal_strategy import PortfolioBalances

# Get current portfolio balances
balances = PortfolioBalances(
    cash=55000,
    taxable=225000,
    traditional=670000,
    roth=168000,
    daf=0
)

# Calculate optimal conversion for current year
current_agi = 120000  # From income calculations
optimal_conversion, betr_results = optimize_conversion_amount(
    traditional_ira_balance=balances.traditional,
    current_agi=current_agi,
    target_tax_bracket=0.24,
    year=2026,
    pay_from_taxable=True,
    taxable_account_balance=balances.taxable
)

if betr_results.conversion_recommended:
    print(f"Recommended conversion: ${optimal_conversion:,.0f}")
    print(f"BETR: {betr_results.betr:.2%}")
```

### Using with Tax Calculations

```python
from betr_roth_conversion import calculate_betr, BETRInputs
from calculations import calc_agi, calculate_taxable_income

# Calculate current AGI
agi = calc_agi(
    joint_gross_income=100000,
    interest=5000,
    stddectdf=std_deduction_df,
    daf=0
)

# Analyze conversion
inputs = BETRInputs(
    current_marginal_rate=0.24,
    expected_future_rate=0.22,
    conversion_amount=50000,
    traditional_ira_balance=500000,
    pay_from_taxable=True,
    taxable_account_balance=200000
)

results = calculate_betr(inputs)
```

## Use Cases

### 1. Early Retirement (Pre-Medicare)

**Scenario:** Retired at 60, living on taxable account, low current income

```python
inputs = BETRInputs(
    current_marginal_rate=0.12,  # Low bracket due to no wages
    expected_future_rate=0.24,   # Higher when RMDs start
    conversion_amount=100000,
    traditional_ira_balance=800000,
    pay_from_taxable=True,
    taxable_account_balance=300000,
    years_to_withdrawal=13,      # Until RMD age (73)
    annual_return=0.07
)

results = calculate_betr(inputs)
# Likely shows high BETR, strong recommendation to convert
```

### 2. IRMAA Optimization

**Scenario:** Approaching Medicare, want to avoid IRMAA surcharges

```python
# Convert up to IRMAA threshold
from load_data import get_medicare_costs

irmaa_df = get_medicare_costs(2026)
irmaa_threshold = 206000  # First IRMAA bracket

optimal_conversion, results = optimize_conversion_amount(
    traditional_ira_balance=1000000,
    current_agi=180000,
    target_tax_bracket=0.24,
    year=2026,
    pay_from_taxable=True
)

# Ensure conversion doesn't push into IRMAA
if current_agi + optimal_conversion > irmaa_threshold:
    safe_conversion = irmaa_threshold - current_agi
    print(f"Adjusted for IRMAA: ${safe_conversion:,.0f}")
```

### 3. Backdoor Roth Planning

**Scenario:** High earner wanting to enable future backdoor Roth contributions

```python
inputs = BETRInputs(
    current_marginal_rate=0.35,
    expected_future_rate=0.32,
    conversion_amount=200000,  # Convert entire balance
    traditional_ira_balance=200000,
    nontaxable_basis=50000,    # After-tax contributions
    pay_from_taxable=True,
    taxable_account_balance=500000,
    years_to_withdrawal=25,
    annual_return=0.07,
    future_backdoor_roth=True,
    backdoor_contribution_years=15
)

results = calculate_betr(inputs)
# BETR adjusted upward for backdoor benefit
```

### 4. Multi-Year Conversion Strategy

**Scenario:** Systematic conversions over several years

```python
# Analyze 5-year conversion strategy
years = range(2026, 2031)
annual_conversion = 50000

for year in years:
    current_agi = 100000  # Adjust based on year
    
    optimal, results = optimize_conversion_amount(
        traditional_ira_balance=500000 - (annual_conversion * (year - 2026)),
        current_agi=current_agi,
        target_tax_bracket=0.24,
        year=year,
        pay_from_taxable=True
    )
    
    print(f"{year}: Convert ${optimal:,.0f}, BETR: {results.betr:.2%}")
```

## Decision Framework

### When BETR Analysis Recommends Conversion

✓ **Expected Future Tax Rate > BETR**
- Your expected future tax rate exceeds the break-even threshold
- Conversion is financially beneficial
- The higher your expected future rate above BETR, the more beneficial the conversion
- Strong recommendation to proceed

### When BETR Analysis Does Not Recommend Conversion

✗ **Expected Future Tax Rate ≤ BETR**
- Your expected future tax rate is at or below the break-even threshold
- Conversion may not be financially beneficial from a pure tax perspective
- Consider waiting, converting smaller amount, or reassessing future tax rate expectations
- May still convert for non-tax reasons (estate planning, RMD avoidance, etc.)

### Additional Considerations

1. **State Taxes**: BETR analysis uses federal rates; consider state tax implications
2. **Estate Planning**: Roth IRAs have no RMDs, beneficial for heirs
3. **ACA Subsidies**: Conversions increase MAGI, may affect healthcare subsidies
4. **Medicare IRMAA**: Conversions can trigger IRMAA surcharges (2-year lookback)
5. **Market Timing**: Consider converting after market declines (lower tax cost)

## Best Practices

### 1. Annual Review
- Recalculate BETR each year as circumstances change
- Adjust conversion amounts based on income fluctuations
- Monitor tax law changes

### 2. Multi-Year Planning
- Spread conversions over multiple years
- Stay within target tax bracket each year
- Avoid pushing into higher brackets or IRMAA

### 3. Pay from Taxable Account
- Maximizes tax-advantaged space
- Higher BETR (more favorable)
- Requires sufficient taxable account balance

### 4. Document Nontaxable Basis
- Track after-tax IRA contributions carefully
- File Form 8606 annually
- Reduces conversion tax burden

### 5. Consider Future Opportunities
- Enable backdoor Roth contributions
- Plan for future tax rate changes
- Account for RMD requirements

## Troubleshooting

### Issue: BETR seems too high/low

**Check:**
- Tax payment source (taxable vs. IRA)
- Nontaxable basis amount
- Years to withdrawal
- Expected return rate

### Issue: Optimization returns $0 conversion

**Possible causes:**
- Current AGI already at/above target bracket
- Traditional IRA balance insufficient
- Target tax bracket not found in tax tables

**Solution:**
- Verify current AGI calculation
- Check target_tax_bracket parameter
- Ensure tax bracket data files are current

### Issue: Results don't match expectations

**Verify:**
- All input parameters are correct
- Tax rates are in decimal form (0.24, not 24)
- Traditional IRA balance is accurate
- Years to withdrawal is reasonable

## Examples

See the bottom of [`betr_roth_conversion.py`](betr_roth_conversion.py) for complete working examples that demonstrate:

1. Basic conversion analysis
2. Conversion with nontaxable basis
3. Optimizing conversion amount

Run examples:
```bash
python3 betr_roth_conversion.py
```

## References

- **Vanguard Research**: "A 'BETR' approach to Roth conversions" (July 2025)
  - https://corporate.vanguard.com/content/dam/corp/research/pdf/a_betr_approach_to_roth_conversions_072025.pdf

- **IRS Resources**:
  - [Roth IRA Conversions](https://www.irs.gov/retirement-plans/roth-iras)
  - [Form 8606 Instructions](https://www.irs.gov/forms-pubs/about-form-8606)

- **Related Modules**:
  - [`calculations.py`](calculations.py) - Tax calculations
  - [`withdrawal_strategy.py`](withdrawal_strategy.py) - Withdrawal strategies
  - [`load_data.py`](load_data.py) - Tax bracket data

## Support

For questions or issues:
1. Review this guide thoroughly
2. Check example code in [`betr_roth_conversion.py`](betr_roth_conversion.py)
3. Verify input parameters are correct
4. Enable debug logging: `export LOG_LEVEL=DEBUG`
5. Consult with a tax professional for personalized advice

## Disclaimer

⚠️ **IMPORTANT**: This tool is for educational and planning purposes only. It is NOT financial, tax, or investment advice. The BETR methodology provides a framework for analysis but should not be the sole basis for financial decisions. Always consult with qualified tax and financial professionals before making Roth conversion decisions.

---

**Made with IBM Bob** | Last Updated: 2026-02-23