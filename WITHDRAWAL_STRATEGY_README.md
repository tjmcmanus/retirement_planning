# Retirement Portfolio Withdrawal Strategy - 5 Stages of Life

A comprehensive Python module for calculating optimal retirement withdrawal strategies across 5 distinct life stages, with tax optimization, Roth conversions, IRMAA management, and ACA subsidy considerations.

## Overview

This module implements a sophisticated withdrawal strategy that adapts to different life stages:

1. **Stage 1: Accumulation** - Employed, earning wages, building assets tax-efficiently
2. **Stage 2: Early Retirement** - Pre-Medicare, pre-SS, pre-RMD with aggressive Roth conversions
3. **Stage 3: Medicare** - On Medicare, optimizing for IRMAA while continuing conversions
4. **Stage 4: Social Security** - Collecting SS + Medicare, balancing taxation
5. **Stage 5: RMD** - Managing Required Minimum Distributions with full retirement income

## Key Features

### Tax Optimization
- **Roth Conversions**: Automatically calculates optimal conversion amounts to fill lower tax brackets
- **LTCG Harvesting**: Harvests long-term capital gains at 0% or 15% rates when beneficial
- **Tax Bracket Management**: Stays within target tax brackets (12%, 22%, 24%)
- **Standard Deduction**: Fully utilizes standard deduction each year

### IRMAA Management
- **2-Year Lookback**: Accounts for IRMAA's 2-year MAGI lookback period
- **Threshold Optimization**: Avoids crossing IRMAA thresholds when possible
- **Multi-Person Support**: Handles 1 or 2 people on Medicare

### ACA Subsidy Optimization (Stage 2)
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
- `withdrawal_strategy.py` - Main module
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
from withdrawal_strategy import (
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
from withdrawal_strategy import create_example_scenario

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
Five stage-specific strategy calculators:
- `Stage1Accumulation` - Working years
- `Stage2EarlyRetirement` - Pre-Medicare retirement
- `Stage3Medicare` - Medicare with IRMAA optimization
- `Stage4SocialSecurity` - SS + Medicare
- `Stage5RMD` - RMD compliance

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

See [`example_withdrawal_strategy.py`](example_withdrawal_strategy.py) for comprehensive examples:

1. **Basic Strategy** - Standard retirement scenario
2. **Early Retirement** - Aggressive Roth conversions
3. **High Income** - IRMAA optimization
4. **Custom Scenario** - User-defined parameters
5. **Scenario Comparison** - Side-by-side analysis

Run examples:
```bash
python example_withdrawal_strategy.py
```

## Strategy Details by Stage

### Stage 1: Accumulation
**When:** Still employed with wages  
**Focus:** Tax-efficient contributions  
**Actions:**
- Maximize 401k/IRA contributions
- Choose Roth vs Traditional based on tax bracket
- Build emergency fund
- No withdrawals

### Stage 2: Early Retirement
**When:** Retired, pre-Medicare, pre-SS, pre-RMD  
**Focus:** Roth conversion opportunity  
**Actions:**
- Aggressive Roth conversions (fill 12% or 22% bracket)
- Harvest LTCG at 0% rate when possible
- Use taxable account for living expenses
- Optimize for ACA subsidies (keep MAGI < 400% FPL)
- 4% withdrawal rate

**Tax Strategy:**
- Convert Traditional → Roth up to target bracket
- Harvest LTCG to fund expenses at 0% rate
- Minimize taxable income for ACA subsidies

### Stage 3: Medicare
**When:** On Medicare, pre-SS, pre-RMD  
**Focus:** IRMAA optimization  
**Actions:**
- Continue Roth conversions but watch IRMAA thresholds
- Balance conversion benefits vs IRMAA penalties
- Stay below next IRMAA bracket
- Use 2-year MAGI lookback for planning

**IRMAA Thresholds (2024):**
- $103,000 - $129,000: +$69.90/month
- $129,000 - $161,000: +$174.70/month
- $161,000 - $193,000: +$279.50/month
- $193,000+: Higher penalties

### Stage 4: Social Security
**When:** Collecting SS, on Medicare, pre-RMD  
**Focus:** SS taxation and IRMAA  
**Actions:**
- Receive SS benefits (up to 85% taxable)
- Limited Roth conversions (SS increases MAGI)
- Manage IRMAA with SS income
- Supplement with portfolio withdrawals

**Tax Considerations:**
- 85% of SS is taxable at higher incomes
- SS + conversions can trigger IRMAA
- Balance conversion benefits vs higher taxation

### Stage 5: RMD
**When:** Age 73+ (SECURE Act 2.0)  
**Focus:** RMD compliance and tax management  
**Actions:**
- Take Required Minimum Distributions
- RMDs may fill lower tax brackets
- Limited Roth conversion opportunity
- Focus on tax-efficient withdrawal sequencing

**RMD Calculation:**
- Traditional IRA balance ÷ Life Expectancy Factor
- Must withdraw by December 31 each year
- 50% penalty for missed RMDs

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
from withdrawal_strategy import build_withdrawal_strategy_display

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
from withdrawal_strategy import LifeStage, YearlyStrategy

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

1. Add new life stages in `withdrawal_strategy.py`
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

IBM Bob - 2026-02-22

---

For questions or issues, please refer to the main application documentation or create an issue in the project repository.