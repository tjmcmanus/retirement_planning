# Tax & Retirement Planning Application

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
- **Account Mix Breakdown**: Detailed treemap visualization of account distribution

### 2. Tax Planner Tab
- **Roth Conversion Calculator**: Optimize conversions to stay within desired tax brackets
- **Tax Projection**: Calculate federal and state taxes based on income sources
- **Medicare IRMAA Calculator**: Project Medicare surcharges based on MAGI
- **AMT Analysis**: Identify and avoid Alternative Minimum Tax scenarios
- **Donor Advised Fund Planning**: Optimize charitable contributions for tax benefits
- **Quarterly Tax Estimates**: Calculate estimated tax payments
- **Multi-year Tax Planning**: Project taxes across retirement years

### 3. Portfolio Planner Tab
- **Real-time Portfolio Tracking**: Live stock prices via Yahoo Finance API
- **Dividend Analysis**: Track dividend income and yields
- **Cost Basis Tracking**: Monitor gains/losses across holdings
- **Sector Allocation**: Visualize portfolio diversification
- **Tax-Advantaged Account Management**: Separate tracking for taxable, traditional, and Roth accounts
- **Editable Portfolio**: Add, remove, or modify holdings (roadmap feature)

### 4. Retirement Planner Tab
- **Long-term Projections**: Model retirement through 2050
- **Social Security Integration**: Calculate benefits based on claiming age
- **Required Minimum Distributions (RMD)**: Automatic RMD calculations
- **Expense Modeling**: Project expenses with inflation adjustments
- **Portfolio Withdrawal Strategy**: Optimize withdrawal sequencing
- **Cash Flow Analysis**: Track inflows and outflows across retirement years

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. Clone or download this repository:
```bash
cd retirement_planning
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

### Quick Start with Run Script

For convenience, use the provided [`run.sh`](run.sh:1) script:
```bash
chmod +x run.sh
./run.sh
```

This script will:
- Check for Python 3 installation
- Create and activate a virtual environment
- Install all dependencies
- Verify required CSV files exist
- Launch the Streamlit application

## Required Data Files

The application requires the following CSV files in the root directory:

### Financial Data Files
- **`financial_data.csv`**: Historical net worth data
  - Columns: `date`, `cash`, `taxable`, `tax_deferred`, `tax_free`, `total`, `expenses`, `daf`
  - Sample file: [`financial_data_sample.csv`](financial_data_sample.csv:1)

- **`financial_account.csv`**: Account-level details
  - Columns: `year`, `month`, `type`, `account`, `amount`
  - Sample file: [`financial_account_sample.csv`](financial_account_sample.csv:1)

- **`portfolio.csv`**: Investment holdings
  - Columns: `account_type`, `symbol`, `name`, `sector`, `qty`, `purchase_price`
  - Sample file: [`portfolio_sample.csv`](portfolio_sample.csv:1)

### Tax Reference Files

#### Federal Income Tax
- **`income_rates.csv`**: Federal income tax brackets by year
  - Columns: `year`, `lower`, `upper`, `rate`
  - Reference: [IRS Tax Brackets](https://www.irs.gov/newsroom/irs-provides-tax-inflation-adjustments-for-tax-year-2024)

- **`standard.csv`**: Standard deduction amounts
  - Columns: `year`, `deduction`
  - Reference: [IRS Standard Deduction](https://www.irs.gov/newsroom/irs-provides-tax-inflation-adjustments-for-tax-year-2024)

#### Capital Gains Tax
- **`cap_gains.csv`**: Capital gains tax brackets
  - Columns: `year`, `lower`, `upper`, `rate`
  - Reference: [IRS Capital Gains Tax Rates](https://www.irs.gov/taxtopics/tc409)

#### Medicare IRMAA (Income-Related Monthly Adjustment Amount)
- **`irmaa.csv`**: Medicare IRMAA surcharge brackets
  - Columns: `year`, `lower`, `upper`, `rate`
  - **Official Resources:**
    - [Medicare.gov IRMAA Information](https://www.medicare.gov/your-medicare-costs/part-b-costs)
    - [Social Security IRMAA Details](https://www.ssa.gov/benefits/medicare/medicare-premiums.html)
    - [CMS IRMAA Tables](https://www.cms.gov/medicare/health-plans/medigapolicies/downloads/irmaa.pdf)

#### Alternative Minimum Tax (AMT)
- **`atm.csv`**: Alternative Minimum Tax parameters
  - Columns: `year`, `deduction`, `lower`, `upper`, `phase_out`, `rate`, `exception_rate`
  - **Official Resources:**
    - [IRS AMT Overview](https://www.irs.gov/taxtopics/tc556)
    - [IRS Form 6251 Instructions](https://www.irs.gov/forms-pubs/about-form-6251)
    - [IRS AMT Assistant](https://www.irs.gov/businesses/small-businesses-self-employed/alternative-minimum-tax-amt-assistant-for-individuals)

#### Required Minimum Distributions (RMD)
- **`rmd.csv`**: Required Minimum Distribution factors
  - Columns: `Age`, `Distribution`
  - **Official Resources:**
    - [IRS RMD Overview](https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-required-minimum-distributions-rmds)
    - [IRS Uniform Lifetime Table](https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-required-minimum-distributions-rmds)
    - [IRS Publication 590-B](https://www.irs.gov/publications/p590b)

### Social Security Files

#### Social Security Income (SSI)
- **`ssincome.csv`**: Social Security benefit projections
  - Columns: `year`, `person`, `claiming_age`, `monthly_benefit`
  - **Official Resources:**
    - [Social Security Administration](https://www.ssa.gov/)
    - [SSA Retirement Benefits](https://www.ssa.gov/benefits/retirement/)
    - [SSA Benefit Calculators](https://www.ssa.gov/benefits/retirement/estimator.html)
    - [SSA my Social Security Account](https://www.ssa.gov/myaccount/)
    - [SSA Full Retirement Age](https://www.ssa.gov/benefits/retirement/planner/agereduction.html)

## Running the Application

### Method 1: Using the Run Script (Recommended)
```bash
./run.sh
```

### Method 2: Manual Start
1. Ensure all required CSV files are in place (use sample files if needed)

2. Activate virtual environment:
```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Start the Streamlit application:
```bash
streamlit run planning_app.py
```

4. The application will open in your default web browser at `http://localhost:8501`

## Configuration

### Sidebar Settings
Configure retirement parameters in the sidebar (see [`components/sidebar.py`](components/sidebar.py:1)):
- **Social Security Age**: Age to begin claiming benefits (default: 70)
- **Roth Conversion at SSI Age**: Annual conversion amount after SS starts
- **Max Tax Rate for Roth Conversion**: Target marginal tax rate (default: 24%)
- **Expected Annual Expenses**: Projected yearly spending
- **Expense Multiplier**: Safety margin for brokerage account (default: 4x)
- **Expected Annual Rate of Return**: Investment growth rate (default: 6%)
- **DAF Disbursement Rate**: Annual charitable giving rate (default: 25%)

## Project Structure

```
retirement_planning/
├── planning_app.py              # Main Streamlit application
├── calculations.py              # Tax calculation functions
├── income_expense.py            # Income/expense projections
├── load_data.py                 # Data loading utilities
├── portfolio.py                 # Portfolio management functions
├── ssibenefits.py              # Social Security calculations
├── editable_table.py           # Standalone table editor
├── components/
│   └── sidebar.py              # Sidebar configuration
├── pages/
│   ├── calculators.py          # Additional calculator pages
│   └── flow_of_funds.py        # Cash flow analysis
├── .streamlit/
│   └── config.toml             # Streamlit configuration
├── requirements.txt            # Python dependencies
├── run.sh                      # Automated setup and run script
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
- [`calc_daf_value()`](calculations.py:1): Calculate optimal charitable contributions

### Portfolio Management ([`portfolio.py`](portfolio.py:1))
- [`build_portfolio_display()`](portfolio.py:158): Generate portfolio summary with live prices
- [`get_current_price()`](portfolio.py:21): Fetch real-time stock prices via Yahoo Finance
- [`get_current_dividend()`](portfolio.py:83): Calculate dividend income
- [`calculate_current_value()`](portfolio.py:72): Compute current portfolio value
- [`calculate_cost_basis()`](portfolio.py:1): Track investment cost basis

### Data Loading ([`load_data.py`](load_data.py:1))
- [`get_income_tax_brackets()`](load_data.py:6): Load tax brackets for specified year
- [`get_cap_gains_brackets()`](load_data.py:14): Load capital gains rates
- [`load_net_worth()`](load_data.py:59): Load historical net worth data
- [`get_medicare_costs()`](load_data.py:1): Load IRMAA brackets
- [`get_atm_costs()`](load_data.py:1): Load AMT parameters

### Social Security ([`ssibenefits.py`](ssibenefits.py:1))
- Social Security benefit calculations based on claiming age
- Integration with retirement planning projections

## Government Resources & References

### IRS Resources
- [IRS Homepage](https://www.irs.gov/)
- [IRS Tax Forms and Publications](https://www.irs.gov/forms-instructions)
- [IRS Retirement Plans](https://www.irs.gov/retirement-plans)
- [IRS Publication 590-A (IRA Contributions)](https://www.irs.gov/publications/p590a)
- [IRS Publication 590-B (IRA Distributions)](https://www.irs.gov/publications/p590b)

### Social Security Administration
- [SSA Homepage](https://www.ssa.gov/)
- [Retirement Planner](https://www.ssa.gov/benefits/retirement/planner/)
- [Online Benefit Calculators](https://www.ssa.gov/benefits/retirement/estimator.html)
- [Medicare Information](https://www.ssa.gov/benefits/medicare/)

### Medicare Resources
- [Medicare.gov](https://www.medicare.gov/)
- [Medicare Costs](https://www.medicare.gov/your-medicare-costs)
- [Medicare Part B Premiums](https://www.medicare.gov/your-medicare-costs/part-b-costs)

### Tax Planning Resources
- [Tax Policy Center](https://www.taxpolicycenter.org/)
- [Congressional Research Service Tax Reports](https://crsreports.congress.gov/)

## Known Issues & Limitations

### Code Issues
See [`ERRORS_FOUND.md`](ERRORS_FOUND.md:1) for detailed code analysis.

1. **[`portfolio.py:30`](portfolio.py:30)**: Print statement has incorrect f-string syntax
   ```python
   # Current (incorrect):
   print("quanity price is: {quanity}")
   # Should be:
   print(f"quanity price is: {quanity}")
   ```

### Data Requirements
- Sample CSV files are provided but need to be renamed (remove `_sample` suffix) or create your own
- Real portfolio data requires valid stock tickers
- Historical net worth data must be manually maintained
- Tax bracket files should be updated annually to reflect current IRS rates

### API Limitations
- Yahoo Finance API may rate-limit requests for large portfolios
- Stock data requires internet connection
- Some mutual funds may not have complete data available
- Real-time prices may have slight delays

### Feature Limitations
- Portfolio editing interface is marked as "roadmap" feature (not yet functional)
- State tax calculations use a simplified 3% flat rate
- AMT calculations may need verification for complex scenarios

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
- Verify stock tickers are valid (check on Yahoo Finance)
- Check internet connection for Yahoo Finance API
- Review [`portfolio.csv`](portfolio.csv:1) format matches expected columns
- Ensure `account_type`, `symbol`, `name`, `sector`, `qty`, and `purchase_price` columns exist

### Tax calculations seem incorrect
- Verify tax bracket CSV files match current IRS rates
- Check that all income sources are properly categorized
- Review standard deduction amounts for the tax year
- Consult official IRS publications for verification

### Application won't start
- Ensure Python 3.8+ is installed: `python3 --version`
- Verify virtual environment is activated
- Check that all dependencies installed successfully
- Review terminal output for specific error messages

## Best Practices

### Data Management
1. **Backup regularly**: Keep copies of your CSV files
2. **Update annually**: Refresh tax bracket files with current IRS rates
3. **Verify calculations**: Cross-check results with tax software or professionals
4. **Use sample data first**: Test with sample files before using real financial data

### Tax Planning
1. **Consult professionals**: This tool is for planning, not tax advice
2. **Verify with IRS**: Always check calculations against official IRS publications
3. **Consider state taxes**: State tax calculations are simplified
4. **Review annually**: Tax laws change; update your data files accordingly

### Portfolio Management
1. **Regular updates**: Update portfolio holdings as you make changes
2. **Verify tickers**: Ensure stock symbols are correct
3. **Monitor API limits**: Yahoo Finance may rate-limit excessive requests
4. **Check data quality**: Review fetched prices for accuracy

## Contributing

This is a personal financial planning tool. Modifications should be tested thoroughly with sample data before using with real financial information.

### Development Guidelines
- Test all changes with sample data first
- Verify tax calculations against IRS publications
- Document any new features or calculations
- Follow existing code structure and naming conventions

## Disclaimer

**⚠️ IMPORTANT: This application is for educational and planning purposes only. It is NOT financial, tax, or investment advice. Always consult with qualified professionals before making financial decisions.**

- Tax laws change frequently; verify calculations with current IRS publications
- Investment returns are not guaranteed and past performance doesn't predict future results
- Social Security projections are estimates based on current law and may change
- Medicare IRMAA brackets are subject to annual adjustment
- State tax calculations are simplified and may not reflect your actual liability
- This tool does not replace professional financial, tax, or legal advice

## License

This project uses code from Stack Overflow (CC BY-SA 4.0) as noted in [`portfolio.py`](portfolio.py:1-3).

## Version History

- **Current**: Enhanced documentation with government resource links
- Tax year support: 2023-2027
- Retirement projections through 2050
- Real-time portfolio tracking via Yahoo Finance

## Support

For issues or questions:
1. Review this README thoroughly
2. Check CSV file formats match requirements
3. Verify all dependencies are installed
4. Test with sample data files first
5. Consult official IRS and SSA resources for tax/benefit questions
6. Review [`ERRORS_FOUND.md`](ERRORS_FOUND.md:1) for known code issues

## Additional Resources

### Financial Planning
- [FINRA Investor Education](https://www.finra.org/investors)
- [SEC Investor Information](https://www.investor.gov/)
- [Consumer Financial Protection Bureau](https://www.consumerfinance.gov/)

### Retirement Planning Tools
- [SSA Retirement Estimator](https://www.ssa.gov/benefits/retirement/estimator.html)
- [IRS Retirement Plans Overview](https://www.irs.gov/retirement-plans)
- [DOL Retirement Toolkit](https://www.dol.gov/general/topic/retirement)

---

**Made with IBM Bob** | Last Updated: 2026-02-20