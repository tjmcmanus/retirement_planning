# Retirement Portfolio Withdrawal Strategy - 7 Stages of Life

A comprehensive Python module for calculating optimal retirement withdrawal strategies across 7 distinct life stages, with tax optimization, Roth conversions, IRMAA management, ACA subsidy considerations, and surviving spouse planning.

## Overview

This module implements a sophisticated withdrawal strategy that adapts to different life stages:

1. **Stage 1: Accumulation** - Employed, earning wages; routes wages to Traditional 401k, Roth, brokerage, and cash buffer at configurable rates
2. **Stage 2: Prep for Retirement** - Within 10 years of retirement; cash buffer linearly ramps from wages-based target to 75% of full retirement reserve
3. **Stage 3: Early Retirement** - Pre-Medicare, pre-SS, pre-RMD with aggressive Roth conversions
4. **Stage 4: Medicare** - On Medicare, optimizing for IRMAA while continuing conversions
5. **Stage 5: Social Security** - Collecting SS + Medicare, balancing taxation
6. **Stage 6: RMD** - Managing Required Minimum Distributions with full retirement income
7. **Stage 7: Surviving Spouse** - Single filer status with survivor benefits and conservative tax planning

## Key Features

### BETR-Validated Roth Conversions
- **Break-Even Tax Rate (BETR)**: Uses Vanguard's BETR methodology to determine whether a conversion is financially beneficial before executing it
- **Tax Payment Source**: Accounts for whether conversion taxes are paid from taxable account (preferred) or IRA assets
- **Nontaxable Basis**: Adjusts BETR for after-tax contributions in Traditional IRA
- **Backdoor Roth Enablement**: Factors in future backdoor Roth contribution opportunities
- **Bracket Optimization**: Converts up to `max_roth_conversion_tax_rate` (configured in `config.py`) each year

### Tax Optimization
- **Roth Conversions**: Automatically calculates optimal conversion amounts to fill lower tax brackets, validated by BETR analysis
- **LTCG Harvesting**: Harvests long-term capital gains at 0% or 15% rates when beneficial
- **Tax Bracket Management**: Stays within target tax brackets (12%, 22%, 24%)
- **Standard Deduction**: Fully utilizes standard deduction each year

### IRMAA Management
- **2-Year Lookback**: Accounts for IRMAA's 2-year MAGI lookback period
- **Threshold Optimization**: Avoids crossing IRMAA thresholds when possible
- **Multi-Person Support**: Handles 1 or 2 people on Medicare

### ACA Subsidy Optimization (Stage 3)
- **FPL Calculations**: Keeps income below 400% Federal Poverty Level for maximum subsidies
- **Premium Calculations**: Estimates net ACA premiums after subsidies

### Withdrawal Sequencing
- **4% Rule**: Implements sustainable 4% withdrawal strategy
- **Account Prioritization**: Optimal withdrawal order (Taxable → Traditional → Roth)
- **Tax-Efficient Sourcing**: Pays taxes from most cost-effective accounts

### RMD Compliance
- **Automatic Calculation**: Calculates RMDs based on IRS life expectancy tables
- **Age 73+**: Implements SECURE Act 2.0 RMD age requirements
- **Forced Distributions**: Ensures RMD compliance while minimizing tax impact

## Installation

### Prerequisites
```bash
pip install pandas numpy streamlit yfinance
```

### Files Required
- `strategy.py` - Main module
- `load_data.py` - Data loading utilities
- `calculations.py` - Tax calculation functions
- `ssibenefits.py` - Social Security benefit calculations
- CSV data files:
  - `income_rates.csv` - Federal tax brackets
  - `cap_gains.csv` - Capital gains tax brackets
  - `standard.csv` - Standard deduction amounts
  - `irmaa.csv` - Medicare IRMAA brackets
  - `atm.csv` - Alternative Minimum Tax data
  - `ssincome.csv` - Social Security benefit data
  - `rmd.csv` - RMD distribution factors
  - `portfolio_data_truth.csv` - Portfolio holdings

## Quick Start

### Basic Usage

```python
from strategy import (
    PortfolioBalances,
    build_withdrawal_strategy_display,
    generate_strategy_summary,
    print_strategy_report
)

# Define your portfolio
initial_balances = PortfolioBalances(
    cash=55000,
    taxable=225000,
    traditional=670000,
    roth=168000,
    daf=0
)

# Calculate strategy from 2026 to 2051
strategy_df, balances_df = build_withdrawal_strategy_display(
    start_year=2026,
    end_year=2051,
    initial_balances=initial_balances,
    initial_expenses=120000,
    person1_name="Tom",
    person2_name="Sarah",
    growth_rate=1.07,  # 7% annual growth
    expense_inflation=0.993,  # Slight deflation
    ss_claiming_age=67,
    retirement_year=2026,
    has_wages=False
)

# Generate report
summary = generate_strategy_summary(strategy_df)
print_strategy_report(strategy_df, summary)

# Save results
strategy_df.to_csv("my_retirement_strategy.csv", index=False)
```

### Using Pre-Built Scenarios

```python
from strategy import create_example_scenario

# Load a pre-built scenario
scenario = create_example_scenario("early_retire")

# Calculate strategy
strategy_df, balances_df = build_withdrawal_strategy_display(**scenario)
```

Available scenarios:
- `"default"` - Standard retirement with $1.1M portfolio
- `"early_retire"` - Early retirement with $1.5M portfolio, delayed SS
- `"high_income"` - High net worth with $3.7M portfolio

## Module Components

### Core Classes

#### `PortfolioBalances`
Container for portfolio account balances:
```python
balances = PortfolioBalances(
    cash=50000,        # Cash/checking accounts
    taxable=200000,    # Brokerage accounts
    traditional=600000, # 401k, Traditional IRA
    roth=150000,       # Roth IRA, Roth 401k
    daf=0              # Donor Advised Fund
)
```

#### `YearlyStrategy`
Contains a single year's withdrawal strategy with:
- Income sources (wages, SS, RMD)
- Withdrawals by account type
- Roth conversions
- Tax calculations
- IRMAA penalties
- End-of-year balances

#### `LifeStage` Classes
Six stage-specific strategy calculators:
- [`Stage1Accumulation`](strategy.py:1) - Working years with configurable contribution rates
- [`Stage2PrepForRetirement`](strategy.py:1) - Within 10 years of retirement; cash buffer ramp
- [`Stage3EarlyRetirement`](strategy.py:1) - Pre-Medicare retirement with aggressive Roth conversions
- [`Stage4Medicare`](strategy.py:1) - Medicare with IRMAA optimization
- [`Stage5SocialSecurity`](strategy.py:1) - SS + Medicare taxation management
- [`Stage6RMD`](strategy.py:1) - RMD compliance

#### `WithdrawalStrategyEngine`
Main calculation engine that:
- Determines applicable life stage each year
- Calculates optimal withdrawals and conversions
- Tracks MAGI for IRMAA lookback
- Projects portfolio growth
- Returns comprehensive DataFrame

### Key Functions

#### `build_withdrawal_strategy_display()`
Main entry point for strategy calculation.

**Parameters:**
- `start_year` (int): Starting year (default: current year)
- `end_year` (int): Ending year (default: 2051)
- `initial_balances` (PortfolioBalances): Starting portfolio
- `initial_expenses` (float): Annual expenses
- `person1_name` (str): Primary person name
- `person2_name` (str): Spouse name
- `growth_rate` (float): Annual portfolio growth (default: 1.07 = 7%)
- `expense_inflation` (float): Annual expense inflation (default: 0.993)
- `ss_claiming_age` (int): SS claiming age (default: 67)
- `retirement_year` (int): Year of retirement
- `has_wages` (bool): Whether still earning wages

**Returns:**
- `strategy_df`: DataFrame with yearly strategies
- `balances_df`: DataFrame with account balances

#### `generate_strategy_summary()`
Generates summary statistics from strategy DataFrame.

**Returns dictionary with:**
- Total years analyzed
- Years in each life stage
- Total Roth conversions
- Total taxes paid
- Total IRMAA penalties
- Portfolio growth
- Final Roth percentage

#### `print_strategy_report()`
Prints formatted report to console with:
- Overview statistics
- Life stage breakdown
- Roth conversion summary
- Tax efficiency metrics
- Year-by-year details

#### `calculate_aca_subsidy()`
Calculates ACA marketplace subsidies based on MAGI and Federal Poverty Level.

**Parameters:**
- `magi` (float): Modified Adjusted Gross Income
- `year` (int): Tax year
- `household_size` (int): Number in household

**Returns:**
- `subsidy_amount`: Annual subsidy
- `net_premium`: Net premium after subsidy

## Output DataFrame Columns

The `strategy_df` DataFrame contains:

| Column | Description |
|--------|-------------|
| Year | Calendar year |
| Age | Ages of primary/spouse (e.g., "65/63") |
| Stage | Life stage name |
| Wages | W-2 wages |
| SS Benefits | Social Security benefits |
| RMD | Required Minimum Distribution |
| Traditional Withdrawal | Withdrawals from Traditional accounts |
| Taxable Withdrawal | Withdrawals from taxable accounts |
| Roth Withdrawal | Withdrawals from Roth accounts |
| Roth Conversion | Amount converted to Roth |
| LTCG Harvested | Long-term capital gains harvested |
| DAF Contribution | Donor Advised Fund contributions |
| Expenses | Annual living expenses |
| Federal Tax | Federal income tax |
| IRMAA Penalty | Medicare IRMAA surcharge |
| ACA Premium | ACA marketplace premium |
| Cash Balance | End-of-year cash balance |
| Taxable Balance | End-of-year taxable balance |
| Traditional Balance | End-of-year traditional balance |
| Roth Balance | End-of-year Roth balance |
| DAF Balance | End-of-year DAF balance |
| Total Portfolio | Total portfolio value |

## Examples

See [`example_strategy.py`](example_strategy.py) for comprehensive examples:

1. **Basic Strategy** - Standard retirement scenario
2. **Early Retirement** - Aggressive Roth conversions
3. **High Income** - IRMAA optimization
4. **Custom Scenario** - User-defined parameters
5. **Scenario Comparison** - Side-by-side analysis

Run examples:
```bash
python example_strategy.py
```

## Strategy Details by Stage

### Stage 1: Accumulation
**When:** Still employed with wages (more than 10 years before retirement)
**Focus:** Tax-efficient contributions and cash buffer building
**Actions:**
- Route wages to Traditional 401k at `contribution_401k_percent` rate (pre-tax, reduces AGI)
- Route wages to Roth 401k/IRA at `contribution_roth_percent` rate
- Route wages to brokerage at `contribution_brokerage_percent` rate
- Remaining take-home cash fills the cash buffer (target: `accumulation_cash_buffer_months` × monthly wages)
- Any surplus above the cash buffer target also flows to brokerage
- No portfolio withdrawals

**Cash Buffer Target (Stage 1):**
```
target_cash = (person1_wages + person2_wages) / 12 × accumulation_cash_buffer_months
```

### Stage 2: Prep for Retirement
**When:** Still employed with wages, within 10 years of the earlier retirement date

**Key behaviors:**
- All Stage 1 contribution logic applies (Traditional 401k, Roth, brokerage)
- Cash buffer target **linearly ramps** from the wages-based accumulation target (at 10 years out) to 75% of the full retirement cash reserve (at 1 year out)
- BETR-validated Roth conversions continue if in a favorable bracket
- Backdoor Roth IRA executed if income exceeds direct Roth IRA limit

**Cash Buffer Ramp Formula:**
```
years_to_retirement = retirement_year - current_year
ramp_fraction = (10 - years_to_retirement) / 9   # 0.0 at 10 yrs, 1.0 at 1 yr
retirement_cash_target = expected_annual_expenses × years_of_expenses_in_cash
target_cash = wages_target + ramp_fraction × (0.75 × retirement_cash_target - wages_target)
```

### Stage 3: Early Retirement
**When:** Retired, pre-Medicare, pre-SS, pre-RMD
**Focus:** Roth conversion opportunity
**Actions:**
- Aggressive BETR-validated Roth conversions (fill 12% or 22% bracket up to `max_roth_conversion_tax_rate`)
- Harvest LTCG at 0% rate when possible
- Use taxable account for living expenses
- Optimize for ACA subsidies when `aca_marketplace_enrolled = true` (keep MAGI < 400% FPL)
- Maintain 2-year cash buffer + 3-year brokerage buffer

**Cash Buffer Maintenance (Retirement Stages 3–6):**
```
cash_target    = expected_annual_expenses × 2          # 2-year cash cushion
brokerage_min  = expected_annual_expenses × 3          # 3-year brokerage buffer
```
When cash falls below target, the engine draws from brokerage before touching Traditional or Roth accounts.

**Tax Strategy:**
- Convert Traditional → Roth up to `max_roth_conversion_tax_rate` bracket, subject to BETR validation
- Harvest LTCG to fund expenses at 0% rate
- Minimize taxable income for ACA subsidies when enrolled

### Stage 4: Medicare
**When:** On Medicare, pre-SS, pre-RMD
**Focus:** IRMAA optimization
**Actions:**
- Continue BETR-validated Roth conversions but watch IRMAA thresholds
- Balance conversion benefits vs IRMAA penalties
- Stay below next IRMAA bracket using 2-year MAGI lookback
- Maintain 2-year cash + 3-year brokerage buffer

**IRMAA Thresholds (2024):**
- $103,000 – $129,000: +$69.90/month
- $129,000 – $161,000: +$174.70/month
- $161,000 – $193,000: +$279.50/month
- $193,000+: Higher penalties

### Stage 5: Social Security
**When:** Collecting SS, on Medicare, pre-RMD
**Focus:** SS taxation and IRMAA
**Actions:**
- Receive SS benefits (up to 85% taxable); benefits calculated dynamically via [`ssi_calculator.py`](ssi_calculator.py:1)
- Limited Roth conversions (SS increases MAGI)
- Manage IRMAA with SS income
- Supplement with portfolio withdrawals as needed

**Tax Considerations:**
- 85% of SS is taxable at higher incomes
- SS + conversions can trigger IRMAA
- Balance conversion benefits vs higher taxation

### Stage 6: RMD
**When:** Age 73+ (SECURE Act 2.0)
**Focus:** RMD compliance and tax management
**Actions:**
- Take Required Minimum Distributions
- RMDs may fill lower tax brackets
- Limited Roth conversion opportunity
- Focus on tax-efficient withdrawal sequencing

**RMD Calculation:**
- Traditional IRA balance ÷ Life Expectancy Factor (from `rmd.csv`)
- Must withdraw by December 31 each year
- 50% penalty for missed RMDs

## BETR Integration

The withdrawal strategy uses the BETR (Break-Even Tax Rate) algorithm from [`betr_roth_conversion.py`](betr_roth_conversion.py:1) to validate every Roth conversion before executing it.

### How BETR Is Used in the Strategy

```python
from betr_roth_conversion import optimize_conversion_amount, BETRInputs, calculate_betr

# In Stage 2 / Stage 3 — determine optimal conversion amount
optimal_amount, betr_results = optimize_conversion_amount(
    traditional_ira_balance=balances.traditional,
    current_agi=current_agi,
    target_tax_bracket=max_roth_conversion_tax_rate / 100,
    year=current_year,
    pay_from_taxable=True,
    taxable_account_balance=balances.taxable
)

# Only convert if BETR analysis recommends it
if betr_results.conversion_recommended:
    execute_roth_conversion(optimal_amount)
```

### BETR Decision Logic

| Condition | Action |
|-----------|--------|
| Expected future rate > BETR | ✅ Convert — financially beneficial |
| Expected future rate ≤ BETR | ❌ Skip — not beneficial at this time |
| IRMAA threshold would be crossed | ⚠️ Reduce conversion to stay below threshold |
| ACA subsidy cliff would be hit | ⚠️ Reduce conversion to stay below 400% FPL |

### Configuration

The maximum tax rate for conversions is set in [`config.py`](config.py:59):
```json
"tax_strategy": {
    "max_roth_conversion_tax_rate": 12
}
```
Change this to `22` or `24` to allow conversions into higher brackets.

See [`BETR_GUIDE.md`](BETR_GUIDE.md) for full BETR algorithm documentation.

## Tax Optimization Strategies

### Roth Conversion Ladder
Convert Traditional → Roth during low-income years (Stages 2-3):
1. Calculate current taxable income
2. Find room to target tax bracket (12%, 22%, 24%)
3. Convert up to bracket limit
4. Pay conversion tax from taxable account
5. Repeat annually

**Benefits:**
- Tax-free growth in Roth
- No RMDs on Roth
- Lower future tax burden
- Reduced IRMAA in later years

### Capital Gains Harvesting
Harvest LTCG at favorable rates:
- **0% bracket**: Up to ~$94,000 MAGI (married)
- **15% bracket**: Up to ~$583,000 MAGI (married)

**Strategy:**
- Sell appreciated positions
- Immediately rebuy (no wash sale rule for gains)
- Reset cost basis higher
- Fund living expenses tax-efficiently

### Withdrawal Sequencing
Optimal order to minimize lifetime taxes:
1. **Taxable** - Harvest LTCG at low rates
2. **Traditional** - Fill lower tax brackets
3. **Roth** - Preserve for last (tax-free)

**Exception:** Use Roth early if:
- Avoiding IRMAA threshold
- Staying below ACA subsidy cliff
- Preventing higher tax bracket

## Integration with Streamlit App

The module integrates with the existing Streamlit retirement planning app:

```python
# In planning_app.py
from strategy import build_withdrawal_strategy_display

# Add to retirement planner tab
strategy_df, balances_df = build_withdrawal_strategy_display(
    start_year=current_year,
    end_year=2051
)

# Display in Streamlit
st.dataframe(strategy_df)
st.line_chart(balances_df.set_index('Year'))
```

## Customization

### Custom Life Stage
Create your own life stage strategy:

```python
from strategy import LifeStage, YearlyStrategy

class CustomStage(LifeStage):
    def __init__(self):
        super().__init__("Custom Stage", "My custom strategy")
    
    def applies(self, age_primary, age_spouse, year, has_wages, has_ss):
        # Define when this stage applies
        return age_primary >= 60 and age_primary < 65
    
    def calculate_strategy(self, year, balances, expenses, **kwargs):
        # Implement custom withdrawal logic
        # Return YearlyStrategy object
        pass
```

### Custom Tax Calculations
Override tax calculation functions in `calculations.py` for:
- State taxes
- Alternative Minimum Tax (AMT)
- Net Investment Income Tax (NIIT)
- Custom deductions

## Fund Movement Tracking

The engine tracks all fund movements across accounts each year:

| Movement | Source | Destination | Tax Event |
|----------|--------|-------------|-----------|
| Roth conversion | Traditional | Roth | Ordinary income |
| LTCG harvest | Taxable (sell) | Taxable (rebuy) | 0% or 15% LTCG |
| RMD | Traditional | Cash/Brokerage | Ordinary income |
| SS benefits | External | Cash | Up to 85% taxable |
| Living expenses | Cash | Out | None |
| Portfolio withdrawal | Brokerage → Traditional → Roth | Cash | Varies |

### Emergency Distribution Protocol

When cash falls below the 2-year buffer target:
1. Draw from brokerage (taxable account) first — LTCG rates apply
2. If brokerage exhausted, draw from Traditional — ordinary income rates
3. Draw from Roth only as last resort — tax-free but reduces future tax-free growth

## Performance Considerations

- **Caching**: Uses `@st.cache_data` for expensive calculations
- **Batch Processing**: Fetches all stock prices in single API call
- **Vectorization**: Uses pandas vectorized operations
- **Memory**: Efficient DataFrame operations

## Limitations

1. **Assumptions:**
   - Constant growth rate (can be customized)
   - Simplified tax calculations (federal only)
   - No state taxes (can be added)
   - Fixed expense inflation

2. **Not Included:**
   - Estate planning
   - Charitable giving strategies (beyond DAF)
   - Healthcare costs (beyond IRMAA)
   - Long-term care insurance
   - Pension income

3. **Data Requirements:**
   - Requires CSV files with tax brackets
   - Needs Social Security benefit data
   - Portfolio data must be current

## Troubleshooting

### Common Issues

**"No portfolio data found"**
- Ensure `portfolio_data_truth.csv` exists
- Check month/year data availability
- Verify CSV format

**"Could not get SS benefits"**
- Check `ssincome.csv` has data for person names
- Verify year range in SS data
- Ensure claiming age is valid

**"IRMAA calculation error"**
- Verify `irmaa.csv` has data for year
- Check MAGI is within bracket ranges
- Ensure people_on_medicare is 0, 1, or 2

**"RMD calculation failed"**
- Check `rmd.csv` has age data
- Verify age >= 73 for RMD requirement
- Ensure Traditional balance > 0

## Contributing

To extend this module:

1. Add new life stages in `strategy.py`
2. Implement custom tax strategies in `calculations.py`
3. Add new data sources in `load_data.py`
4. Create visualization functions for Streamlit

## References

- [IRS Publication 590-B](https://www.irs.gov/publications/p590b) - RMD rules
- [IRS Publication 915](https://www.irs.gov/publications/p915) - Social Security taxation
- [Medicare IRMAA](https://www.medicare.gov/your-medicare-costs/part-b-costs) - IRMAA brackets
- [ACA Subsidies](https://www.healthcare.gov/lower-costs/) - Premium tax credits
- [SECURE Act 2.0](https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-required-minimum-distributions-rmds) - RMD age changes

## License

This module is part of the retirement planning application.

## Author

Bob — 2026-02-22
Last Updated: 2026-03-01

---

For questions or issues, please refer to the main application documentation or create an issue in the project repository.