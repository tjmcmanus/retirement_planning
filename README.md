# Tax & Retirement Planning Application -tom

A comprehensive Streamlit-based financial planning application for retirement tax optimization, portfolio management, and long-term financial projections.

## Overview

This application helps users plan their retirement by:
- Calculating optimal Roth IRA conversions
- Projecting tax liabilities across multiple years
- Managing investment portfolios with real-time data
- Modeling Social Security benefits
- Tracking net worth across different account types
- Planning charitable contributions (Donor Advised Funds)
- Calculating Medicare IRMAA penalties
- Analyzing Alternative Minimum Tax (AMT) scenarios

## Features

### 1. Dashboard Tab
- **Net Worth Tracking**: Monitor cash, brokerage, traditional IRA, and Roth IRA accounts
- **Visual Analytics**: Interactive charts showing account balances over time
- **Asset Allocation**: Pie charts and treemaps for portfolio visualization
- **Monthly Change Tracking**: Delta metrics for all account types

### 2. Tax Planner Tab
- **Roth Conversion Calculator**: Optimize conversions to stay within desired tax brackets
- **Tax Projection**: Calculate federal and state taxes based on income sources
- **Medicare IRMAA Calculator**: Project Medicare surcharges based on MAGI
- **AMT Analysis**: Identify and avoid Alternative Minimum Tax scenarios
- **Donor Advised Fund Planning**: Optimize charitable contributions for tax benefits
- **Quarterly Tax Estimates**: Calculate estimated tax payments

### 3. Portfolio Planner Tab
- **Real-time Portfolio Tracking**: Live stock prices via Yahoo Finance API
- **Dividend Analysis**: Track dividend income and yields
- **Cost Basis Tracking**: Monitor gains/losses across holdings
- **Sector Allocation**: Visualize portfolio diversification
- **Tax-Advantaged Account Management**: Separate tracking for taxable, traditional, and Roth accounts
- **Editable Portfolio**: Add, remove, or modify holdings

### 4. Retirement Planner Tab
- **Long-term Projections**: Model retirement through 2050
- **Social Security Integration**: Calculate benefits based on claiming age
- **Required Minimum Distributions (RMD)**: Automatic RMD calculations
- **Expense Modeling**: Project expenses with inflation adjustments
- **Portfolio Withdrawal Strategy**: Optimize withdrawal sequencing
- **Multi-year Tax Planning**: Project taxes across retirement years

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. Clone or download this repository:
```bash
cd taxapp
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Required Data Files

The application requires the following CSV files in the root directory:

### Financial Data Files
- **`financial_data.csv`**: Historical net worth data
  - Columns: `date`, `cash`, `taxable`, `tax_deferred`, `tax_free`, `total`, `expenses`, `daf`

- **`financial_account.csv`** (or `financial_account_sample.csv`): Account-level details
  - Columns: `year`, `month`, `type`, `account`, `amount`

- **`portfolio.csv`** (or `portfolio_sample.csv`): Investment holdings
  - Columns: `account_type`, `symbol`, `name`, `sector`, `qty`, `purchase_price`

### Tax Reference Files
- **`income_rates.csv`**: Federal income tax brackets by year
  - Columns: `year`, `lower`, `upper`, `rate`

- **`cap_gains.csv`**: Capital gains tax brackets
  - Columns: `year`, `lower`, `upper`, `rate`

- **`standard.csv`**: Standard deduction amounts
  - Columns: `year`, `deduction`

- **`irmaa.csv`**: Medicare IRMAA surcharge brackets
  - Columns: `year`, `lower`, `upper`, `rate`

- **`atm.csv`**: Alternative Minimum Tax parameters
  - Columns: `year`, `deduction`, `lower`, `upper`, `phase_out`, `rate`, `execption_rate`

- **`rmd.csv`**: Required Minimum Distribution factors
  - Columns: `Age`, `Distribution`

### Social Security Files
- **`ssincome.csv`**: Social Security benefit projections
  - Columns: `year`, `person`, `claiming_age`, `monthly_benefit`

## Running the Application

1. Ensure all required CSV files are in place (use sample files if needed)

2. Start the Streamlit application:
```bash
streamlit run planning_app.py
```

3. The application will open in your default web browser at `http://localhost:8501`

## Configuration

### Sidebar Settings
Configure retirement parameters in the sidebar:
- **Social Security Age**: Age to begin claiming benefits (default: 70)
- **Roth Conversion at SSI Age**: Annual conversion amount after SS starts
- **Max Tax Rate for Roth Conversion**: Target marginal tax rate (default: 24%)
- **Expected Annual Expenses**: Projected yearly spending
- **Expense Multiplier**: Safety margin for brokerage account (default: 4x)
- **Expected Annual Rate of Return**: Investment growth rate (default: 6%)
- **DAF Disbursement Rate**: Annual charitable giving rate (default: 25%)

## Command-Line Tax Calculator

For standalone tax calculations, use [`calculate_taxable_income.py`](calculate_taxable_income.py:1):

```bash
python calculate_taxable_income.py \
  --deferred_distribution 50000 \
  --wages 0 \
  --cap_gains_lt 20000 \
  --cap_gains_st 0 \
  --medicare_persons 2 \
  --year 2026 \
  --int_div 5000 \
  --headroom_rate 24 \
  --max_daf N \
  --daf 0
```

### Parameters:
- `--deferred_distribution`: Traditional IRA/401k distributions
- `--wages`: W-2 wages
- `--cap_gains_lt`: Long-term capital gains
- `--cap_gains_st`: Short-term capital gains
- `--medicare_persons`: Number of people on Medicare (0-2)
- `--year`: Tax year (2023-2027)
- `--int_div`: Interest and dividend income
- `--headroom_rate`: Maximum desired tax rate for conversions
- `--max_daf`: Maximize charitable contribution (Y/N)
- `--daf`: Specific charitable contribution amount

## Project Structure

```
taxapp/
├── planning_app.py              # Main Streamlit application
├── calculate_taxable_income.py  # CLI tax calculator
├── calculations.py              # Tax calculation functions
├── income_expense.py            # Income/expense projections
├── load_data.py                 # Data loading utilities
├── portfolio.py                 # Portfolio management functions
├── ssibenefits.py              # Social Security calculations
├── editable_table.py           # Standalone table editor
├── components/
│   └── sidebar.py              # Sidebar configuration
├── .streamlit/
│   └── requirements.txt        # Streamlit Cloud config
├── requirements.txt            # Python dependencies
├── *.csv                       # Data files
└── README.md                   # This file
```

## Key Functions

### Tax Calculations ([`calculations.py`](calculations.py:1))
- [`calc_roth_conversions()`](calculations.py:36): Calculate optimal Roth conversion amounts
- [`calc_agi()`](calculations.py:63): Compute Adjusted Gross Income
- [`calculate_taxable_income()`](calculations.py:233): Calculate federal income tax
- [`calculate_cap_gains()`](calculations.py:211): Calculate capital gains tax
- [`calculate_irmma_penalty()`](calculations.py:193): Calculate Medicare IRMAA surcharges
- [`calculate_atm()`](calculations.py:126): Calculate Alternative Minimum Tax

### Portfolio Management ([`portfolio.py`](portfolio.py:1))
- [`build_portfolio_display()`](portfolio.py:158): Generate portfolio summary with live prices
- [`get_current_price()`](portfolio.py:21): Fetch real-time stock prices
- [`get_current_dividend()`](portfolio.py:83): Calculate dividend income
- [`calculate_current_value()`](portfolio.py:72): Compute current portfolio value

### Data Loading ([`load_data.py`](load_data.py:1))
- [`get_income_tax_brackets()`](load_data.py:6): Load tax brackets for specified year
- [`get_cap_gains_brackets()`](load_data.py:14): Load capital gains rates
- [`load_net_worth()`](load_data.py:59): Load historical net worth data

## Known Issues & Limitations

### Python Syntax Issues Found:
1. **[`portfolio.py:30`](portfolio.py:30)**: Print statement has incorrect f-string syntax
   ```python
   # Current (incorrect):
   print("quanity price is: {quanity}")
   # Should be:
   print(f"quanity price is: {quanity}")
   ```

2. **Missing Dependencies**: The application requires additional packages not in `.streamlit/requirements.txt`

### Data Requirements:
- Sample CSV files are provided but need to be renamed (remove `_sample` suffix)
- Real portfolio data requires valid stock tickers
- Historical net worth data must be manually maintained

### API Limitations:
- Yahoo Finance API may rate-limit requests for large portfolios
- Stock data requires internet connection
- Some mutual funds may not have complete data

## Troubleshooting

### "ModuleNotFoundError"
Install missing dependencies:
```bash
pip install -r requirements.txt
```

### "FileNotFoundError" for CSV files
Ensure all required CSV files exist. Copy sample files:
```bash
cp financial_data_sample.csv financial_data.csv
cp portfolio_sample.csv portfolio.csv
cp financial_account_sample.csv financial_account.csv
```

### Portfolio data not loading
- Verify stock tickers are valid
- Check internet connection for Yahoo Finance API
- Review [`portfolio.csv`](portfolio.csv:1) format

### Tax calculations seem incorrect
- Verify tax bracket CSV files match current IRS rates
- Check that all income sources are properly categorized
- Review standard deduction amounts for the tax year

## Contributing

This is a personal financial planning tool. Modifications should be tested thoroughly with sample data before using with real financial information.

## Disclaimer

**This application is for educational and planning purposes only. It is not financial, tax, or investment advice. Always consult with qualified professionals before making financial decisions.**

- Tax laws change frequently; verify calculations with current IRS publications
- Investment returns are not guaranteed
- Social Security projections are estimates based on current law
- Medicare IRMAA brackets are subject to change

## License

This project uses code from Stack Overflow (CC BY-SA 4.0) as noted in [`portfolio.py`](portfolio.py:1-3).

## Version History

- **Current**: Initial documentation and analysis
- Tax year support: 2023-2027
- Retirement projections through 2050

## Support

For issues or questions:
1. Review this README thoroughly
2. Check CSV file formats match requirements
3. Verify all dependencies are installed
4. Test with sample data files first