---
layout: default
title: API Reference
---

# API Reference

Technical documentation for the Financial Planner application modules and functions.

## Core Modules

### [`strategy.py`](../strategy.py) - Withdrawal Strategy Engine

The main withdrawal strategy module implementing the 6-stage life-cycle approach.

#### Key Functions

##### `run_withdrawal_strategy()`

Executes the complete withdrawal strategy simulation.

**Parameters:**
- `config` (dict): Configuration dictionary with personal and financial settings
- `portfolio_data` (DataFrame): Portfolio account information
- `start_year` (int): Starting year for simulation
- `end_year` (int): Ending year for simulation
- `annual_expenses` (float): Annual expense requirement
- `filing_status` (str): Tax filing status
- `state` (str): State of residence

**Returns:**
- `results` (dict): Comprehensive results including:
  - Year-by-year projections
  - Tax calculations
  - Account balances
  - Withdrawal sequences
  - Success metrics

**Example:**
```python
from strategy import run_withdrawal_strategy
import pandas as pd

config = {
    'person1_age': 60,
    'person2_age': 58,
    'retirement_age': 65,
    'life_expectancy': 95
}

portfolio = pd.read_csv('portfolio_data_truth.csv')

results = run_withdrawal_strategy(
    config=config,
    portfolio_data=portfolio,
    start_year=2024,
    end_year=2060,
    annual_expenses=80000,
    filing_status='Married Filing Jointly',
    state='CA'
)
```

##### `calculate_withdrawal_sequence()`

Determines optimal withdrawal order from accounts.

**Parameters:**
- `accounts` (dict): Dictionary of account balances by type
- `amount_needed` (float): Total withdrawal amount required
- `age` (int): Current age for penalty calculations
- `tax_rates` (dict): Current tax rate information

**Returns:**
- `sequence` (list): Ordered list of withdrawals by account
- `tax_impact` (float): Estimated tax liability

##### `optimize_roth_conversion()`

Calculates optimal Roth conversion amount for the year.

**Parameters:**
- `traditional_ira_balance` (float): Current Traditional IRA balance
- `current_income` (float): Taxable income before conversion
- `tax_brackets` (DataFrame): Tax bracket information
- `target_bracket` (str): Target tax bracket to fill

**Returns:**
- `conversion_amount` (float): Recommended conversion amount
- `tax_cost` (float): Tax cost of conversion
- `long_term_benefit` (float): Estimated long-term tax savings

### [`betr_roth_conversion.py`](../betr_roth_conversion.py) - BETR Algorithm

Bracket-Efficient Tax-Aware Roth conversion optimization.

#### Key Functions

##### `calculate_betr_conversions()`

Implements the BETR algorithm for multi-year Roth conversion planning.

**Parameters:**
- `portfolio` (dict): Portfolio account balances
- `income_projection` (DataFrame): Projected income by year
- `tax_brackets` (DataFrame): Tax bracket data
- `years` (int): Planning horizon in years
- `irmaa_thresholds` (DataFrame): Medicare IRMAA thresholds

**Returns:**
- `conversion_schedule` (DataFrame): Year-by-year conversion recommendations
- `tax_savings` (float): Total estimated tax savings
- `irmaa_impact` (dict): IRMAA surcharge analysis

**Algorithm:**
1. Project income and tax brackets for each year
2. Identify conversion capacity within target brackets
3. Optimize conversion timing to minimize lifetime taxes
4. Avoid IRMAA threshold crossings
5. Balance current tax cost vs. future RMD savings

**Example:**
```python
from betr_roth_conversion import calculate_betr_conversions

conversions = calculate_betr_conversions(
    portfolio={'Traditional IRA': 500000, 'Roth IRA': 100000},
    income_projection=income_df,
    tax_brackets=brackets_df,
    years=10,
    irmaa_thresholds=irmaa_df
)

print(conversions['conversion_schedule'])
```

### [`calculations.py`](../calculations.py) - Tax Calculations

Comprehensive tax calculation engine.

#### Key Functions

##### `calculate_federal_tax()`

Calculates federal income tax liability.

**Parameters:**
- `taxable_income` (float): Taxable income amount
- `filing_status` (str): Filing status
- `year` (int): Tax year
- `standard_deduction` (float, optional): Standard deduction amount

**Returns:**
- `tax_liability` (float): Total federal tax
- `effective_rate` (float): Effective tax rate
- `marginal_rate` (float): Marginal tax rate

##### `calculate_capital_gains_tax()`

Calculates long-term capital gains tax.

**Parameters:**
- `gains` (float): Capital gains amount
- `ordinary_income` (float): Ordinary income
- `filing_status` (str): Filing status

**Returns:**
- `tax` (float): Capital gains tax liability
- `rate` (float): Applicable capital gains rate

##### `calculate_irmaa_surcharge()`

Calculates Medicare IRMAA surcharges.

**Parameters:**
- `magi` (float): Modified Adjusted Gross Income
- `filing_status` (str): Filing status
- `year` (int): Year for IRMAA calculation

**Returns:**
- `part_b_surcharge` (float): Part B monthly surcharge
- `part_d_surcharge` (float): Part D monthly surcharge
- `annual_cost` (float): Total annual IRMAA cost

##### `calculate_rmd()`

Calculates Required Minimum Distribution.

**Parameters:**
- `account_balance` (float): Account balance as of 12/31 prior year
- `age` (int): Account owner's age
- `rmd_table` (DataFrame): IRS RMD life expectancy table

**Returns:**
- `rmd_amount` (float): Required minimum distribution
- `penalty_if_missed` (float): 50% penalty if not taken

### [`portfolio.py`](../portfolio.py) - Portfolio Management

Portfolio tracking and analysis functions.

#### Key Functions

##### `load_portfolio_data()`

Loads and validates portfolio data from CSV.

**Parameters:**
- `filepath` (str): Path to portfolio CSV file
- `validate` (bool): Whether to validate data format

**Returns:**
- `portfolio_df` (DataFrame): Validated portfolio data

##### `calculate_asset_allocation()`

Calculates current asset allocation.

**Parameters:**
- `portfolio_df` (DataFrame): Portfolio holdings data

**Returns:**
- `allocation` (dict): Asset allocation percentages by category
- `total_value` (float): Total portfolio value

##### `rebalance_portfolio()`

Generates tax-efficient rebalancing recommendations.

**Parameters:**
- `current_allocation` (dict): Current allocation percentages
- `target_allocation` (dict): Target allocation percentages
- `tax_lots` (DataFrame): Tax lot information
- `minimize_taxes` (bool): Whether to optimize for taxes

**Returns:**
- `trades` (list): Recommended trades
- `tax_impact` (float): Estimated tax impact
- `new_allocation` (dict): Projected allocation after trades

### [`portfolio_analytics.py`](../portfolio_analytics.py) - Performance Analytics

Portfolio performance and risk analysis.

#### Key Functions

##### `calculate_returns()`

Calculates time-weighted returns.

**Parameters:**
- `portfolio_history` (DataFrame): Historical portfolio values
- `cash_flows` (DataFrame): Contributions and withdrawals
- `period` (str): 'YTD', '1Y', '3Y', '5Y', or 'ITD'

**Returns:**
- `total_return` (float): Total return percentage
- `annualized_return` (float): Annualized return
- `time_weighted_return` (float): Time-weighted return

##### `calculate_risk_metrics()`

Calculates portfolio risk metrics.

**Parameters:**
- `returns` (Series): Historical returns
- `risk_free_rate` (float): Risk-free rate for Sharpe calculation

**Returns:**
- `sharpe_ratio` (float): Risk-adjusted return metric
- `volatility` (float): Standard deviation of returns
- `max_drawdown` (float): Maximum peak-to-trough decline
- `var_95` (float): Value at Risk (95% confidence)

##### `calculate_correlation_matrix()`

Calculates correlation between holdings.

**Parameters:**
- `holdings` (DataFrame): Holdings with historical prices
- `period` (int): Number of periods for calculation

**Returns:**
- `correlation_matrix` (DataFrame): Correlation coefficients

### [`monte_carlo.py`](../monte_carlo.py) - Monte Carlo Simulation

Probabilistic retirement planning simulation.

#### Key Functions

##### `run_monte_carlo_simulation()`

Runs Monte Carlo retirement simulation.

**Parameters:**
- `initial_portfolio` (float): Starting portfolio value
- `annual_withdrawal` (float): Annual withdrawal amount
- `years` (int): Simulation time horizon
- `num_simulations` (int): Number of scenarios (default: 10000)
- `return_params` (dict): Return and volatility assumptions
- `inflation_rate` (float): Expected inflation rate

**Returns:**
- `results` (dict): Simulation results including:
  - `success_rate` (float): Percentage of successful scenarios
  - `median_outcome` (float): Median ending balance
  - `percentiles` (dict): 10th, 25th, 75th, 90th percentiles
  - `scenarios` (DataFrame): All scenario outcomes

**Example:**
```python
from monte_carlo import run_monte_carlo_simulation

results = run_monte_carlo_simulation(
    initial_portfolio=1000000,
    annual_withdrawal=40000,
    years=30,
    num_simulations=10000,
    return_params={'mean': 0.07, 'std': 0.15},
    inflation_rate=0.03
)

print(f"Success Rate: {results['success_rate']:.1%}")
print(f"Median Outcome: ${results['median_outcome']:,.0f}")
```

### [`ssi_calculator.py`](../ssi_calculator.py) - Social Security Calculator

Social Security benefit calculations and optimization.

#### Key Functions

##### `calculate_pia()`

Calculates Primary Insurance Amount.

**Parameters:**
- `earnings_history` (list): Historical earnings record
- `birth_year` (int): Year of birth
- `bend_points` (dict): Current year bend points

**Returns:**
- `pia` (float): Primary Insurance Amount
- `aime` (float): Average Indexed Monthly Earnings

##### `calculate_benefit_at_age()`

Calculates benefit amount at specific claiming age.

**Parameters:**
- `pia` (float): Primary Insurance Amount
- `claiming_age` (int): Age when claiming benefits
- `fra` (int): Full Retirement Age

**Returns:**
- `monthly_benefit` (float): Monthly benefit amount
- `adjustment_factor` (float): Early/delayed claiming adjustment

##### `optimize_claiming_strategy()`

Optimizes Social Security claiming for couples.

**Parameters:**
- `person1_pia` (float): Person 1's PIA
- `person2_pia` (float): Person 2's PIA
- `life_expectancies` (tuple): Life expectancies for both
- `discount_rate` (float): Discount rate for NPV calculation

**Returns:**
- `optimal_ages` (tuple): Optimal claiming ages
- `lifetime_benefit` (float): Total lifetime benefits
- `breakeven_age` (int): Breakeven age for delayed claiming

### [`tax_harvesting.py`](../tax_harvesting.py) - Tax-Loss Harvesting

Tax-loss harvesting identification and execution.

#### Key Functions

##### `identify_harvesting_opportunities()`

Identifies tax-loss harvesting opportunities.

**Parameters:**
- `portfolio` (DataFrame): Current portfolio holdings
- `tax_lots` (DataFrame): Tax lot information with cost basis
- `min_loss` (float): Minimum loss threshold (default: 1000)

**Returns:**
- `opportunities` (DataFrame): Harvesting opportunities with:
  - Security name
  - Current value
  - Cost basis
  - Unrealized loss
  - Recommended action

##### `check_wash_sale()`

Checks for wash sale rule violations.

**Parameters:**
- `sale_date` (date): Date of sale
- `security` (str): Security identifier
- `purchase_history` (DataFrame): Recent purchase history

**Returns:**
- `is_wash_sale` (bool): Whether wash sale rule applies
- `disallowed_loss` (float): Amount of disallowed loss

### [`hsa_integration.py`](../hsa_integration.py) - HSA Planning

Health Savings Account optimization.

#### Key Functions

##### `calculate_hsa_contribution_limit()`

Calculates HSA contribution limits.

**Parameters:**
- `age` (int): Account holder age
- `coverage_type` (str): 'Individual' or 'Family'
- `year` (int): Tax year

**Returns:**
- `contribution_limit` (float): Maximum contribution allowed
- `catch_up` (float): Catch-up contribution if applicable

##### `optimize_hsa_strategy()`

Optimizes HSA contribution and withdrawal strategy.

**Parameters:**
- `current_balance` (float): Current HSA balance
- `years_to_medicare` (int): Years until Medicare eligibility
- `expected_medical_expenses` (float): Annual medical expenses
- `investment_return` (float): Expected return on HSA investments

**Returns:**
- `contribution_schedule` (DataFrame): Recommended contributions
- `withdrawal_strategy` (dict): Optimal withdrawal timing
- `tax_savings` (float): Estimated lifetime tax savings

## Data Structures

### Portfolio Data Format

```python
{
    'Account': str,           # Account name
    'Type': str,             # Account type (401k, IRA, Roth, Taxable, HSA)
    'Owner': str,            # Person1, Person2, or Joint
    'Balance': float,        # Current balance
    'Basis': float,          # Cost basis (for taxable/Roth)
    'Contribution': float,   # Annual contribution
    'Annual_Return': float   # Expected annual return (decimal)
}
```

### Configuration Format

```python
{
    'person1_name': str,
    'person2_name': str,
    'person1_birth_date': str,  # 'YYYY-MM-DD'
    'person2_birth_date': str,
    'person1_current_age': int,
    'person2_current_age': int,
    'person1_retirement_age': int,
    'person2_retirement_age': int,
    'person1_life_expectancy': int,
    'person2_life_expectancy': int,
    'filing_status': str,
    'state': str,
    'annual_expenses': float,
    'expense_growth_rate': float
}
```

## Constants and Enumerations

### Account Types

```python
ACCOUNT_TYPES = [
    '401k',
    '403b',
    'Traditional IRA',
    'Roth IRA',
    'Taxable',
    'HSA',
    '529',
    'Cash'
]
```

### Filing Status Options

```python
FILING_STATUS = [
    'Single',
    'Married Filing Jointly',
    'Married Filing Separately',
    'Head of Household',
    'Qualifying Widow(er)'
]
```

### Life Stages

```python
LIFE_STAGES = {
    1: 'Pre-Retirement Accumulation',
    2: 'Early Retirement (Pre-59½)',
    3: 'Pre-Social Security (59½-62)',
    4: 'Social Security Bridge (62-70)',
    5: 'RMD Management (70+)',
    6: 'Estate Planning'
}
```

## Error Handling

### Common Exceptions

```python
class PortfolioDataError(Exception):
    """Raised when portfolio data is invalid or missing"""
    pass

class TaxCalculationError(Exception):
    """Raised when tax calculation fails"""
    pass

class ConfigurationError(Exception):
    """Raised when configuration is invalid"""
    pass

class InsufficientFundsError(Exception):
    """Raised when withdrawal exceeds available funds"""
    pass
```

## Utility Functions

### Date and Age Calculations

```python
def calculate_age(birth_date: str, as_of_date: str = None) -> int:
    """Calculate age from birth date"""
    
def get_tax_year(date: str) -> int:
    """Get tax year for a given date"""
    
def calculate_years_to_retirement(current_age: int, retirement_age: int) -> int:
    """Calculate years remaining until retirement"""
```

### Financial Calculations

```python
def future_value(pv: float, rate: float, periods: int) -> float:
    """Calculate future value"""
    
def present_value(fv: float, rate: float, periods: int) -> float:
    """Calculate present value"""
    
def annuity_payment(pv: float, rate: float, periods: int) -> float:
    """Calculate annuity payment"""
```

## Testing

See [Testing Guide](technical/testing.md) for information on:
- Unit tests
- Integration tests
- Test data fixtures
- Running test suites

## Performance Considerations

See [Performance Guide](technical/performance.md) for:
- Optimization strategies
- Caching mechanisms
- Large portfolio handling
- Simulation performance

## Version History

- **v2.0** (March 2026): Portfolio Hub redesign, single person mode
- **v1.5** (February 2026): BETR algorithm, tax optimization
- **v1.0** (January 2026): Initial release

---

[← Back to Guides](guides.md) | [Home](../index.md)