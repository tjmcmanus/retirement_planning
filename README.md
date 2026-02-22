# Tax & Retirement Planning Application

A comprehensive Streamlit-based financial planning application for retirement tax optimization, portfolio management, and long-term financial projections with a sophisticated 5-stage withdrawal strategy engine.

## Overview

This application helps users plan their retirement by:
- **5-Stage Withdrawal Strategy**: Comprehensive life-cycle planning from accumulation through RMD phase
- **Roth Conversion Optimization**: Intelligent conversions to minimize lifetime tax burden
- **Tax Projection**: Multi-year federal and state tax calculations
- **Portfolio Management**: Real-time tracking with Yahoo Finance integration
- **Social Security Modeling**: Benefits optimization based on claiming age
- **IRMAA Management**: Medicare surcharge optimization with 2-year lookback
- **ACA Subsidy Optimization**: Healthcare cost management for early retirees
- **Net Worth Tracking**: Comprehensive account monitoring across all types
- **Charitable Planning**: Donor Advised Fund (DAF) contribution strategies
- **RMD Compliance**: Automatic Required Minimum Distribution calculations

## Recent Updates (February 2026)

### ✨ New: 5-Stage Withdrawal Strategy Module
Complete retirement withdrawal strategy implementation covering all life phases:
- **Stage 1: Accumulation** - Tax-efficient asset building while employed
- **Stage 2: Early Retirement** - Aggressive Roth conversions, ACA optimization
- **Stage 3: Medicare** - IRMAA-aware conversion strategies
- **Stage 4: Social Security** - SS taxation and benefit optimization
- **Stage 5: RMD** - Required distribution compliance and management

See [`WITHDRAWAL_STRATEGY_README.md`](WITHDRAWAL_STRATEGY_README.md) for complete documentation.

### 🔧 Enhanced Logging System
Configurable debug logging throughout [`calculations.py`](calculations.py):
- Environment variable control (`LOG_LEVEL=DEBUG`)
- Detailed calculation tracing
- Tax computation debugging
- See [`LOGGING_GUIDE.md`](LOGGING_GUIDE.md) for usage

### 📊 Example Scenarios
Four pre-built withdrawal strategy scenarios in [`example_withdrawal_strategy.py`](example_withdrawal_strategy.py):
1. Basic retirement strategy ($1.1M portfolio)
2. Early retirement with aggressive conversions ($1.5M portfolio)
3. High-income IRMAA optimization ($3.7M portfolio)
4. Custom scenario builder

### 🧪 Test Suite
Comprehensive validation in [`test_withdrawal_strategy.py`](test_withdrawal_strategy.py):
- Portfolio balance calculations
- Life stage determination
- ACA subsidy calculations
- Strategy engine validation
- All tests passing ✅

### 🐛 Bug Fixes
- Fixed f-string syntax error in [`portfolio.py:30`](portfolio.py)
- Corrected variable name typo (quanity → quantity)
- See [`ERRORS_FOUND.md`](ERRORS_FOUND.md) for details

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
- **Long-term Projections**: Model retirement through 2051
- **Social Security Integration**: Calculate benefits based on claiming age
- **Required Minimum Distributions (RMD)**: Automatic RMD calculations
- **Expense Modeling**: Project expenses with inflation adjustments
- **Portfolio Withdrawal Strategy**: 5-stage life-cycle optimization
- **Cash Flow Analysis**: Year-by-year inflows and outflows through 2051
- **Withdrawal Sequencing**: Tax-efficient account prioritization

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

### Quick Start with Run Scripts

#### Main Application
Use the provided [`run.sh`](run.sh) script:
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

#### Withdrawal Strategy Examples
Run pre-built withdrawal strategy scenarios with [`run_strategy.sh`](run_strategy.sh):
```bash
chmod +x run_strategy.sh
./run_strategy.sh
```

This generates:
- `example1_strategy.csv` - Basic retirement scenario
- `example2_early_retire.csv` - Early retirement with conversions
- `example3_high_income.csv` - High net worth optimization
- `example4_custom.csv` - Custom parameters

## Required Data Files

The application requires the following CSV files in the root directory:

### Financial Data Files
- **`financial_data.csv`**: Historical net worth data
  - Columns: `date`, `cash`, `taxable`, `tax_deferred`, `tax_free`, `total`, `expenses`, `daf`
  - Sample file: [`financial_data_sample.csv`](financial_data_sample.csv)

- **`financial_account.csv`**: Account-level details
  - Columns: `year`, `month`, `type`, `account`, `amount`
  - Sample file: [`financial_account_sample.csv`](financial_account_sample.csv)

- **`portfolio.csv`**: Investment holdings
  - Columns: `account_type`, `symbol`, `name`, `sector`, `qty`, `purchase_price`
  - Sample file: [`portfolio_sample.csv`](portfolio_sample.csv)

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
Configure retirement parameters in the sidebar (see [`components/sidebar.py`](components/sidebar.py)):
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
├── planning_app.py                    # Main Streamlit application
├── withdrawal_strategy.py             # 5-stage withdrawal strategy engine
├── example_withdrawal_strategy.py     # Example scenarios and runner
├── test_withdrawal_strategy.py        # Test suite for withdrawal module
├── calculations.py                    # Tax calculation functions (with logging)
├── income_expense.py                  # Income/expense projections
├── load_data.py                       # Data loading utilities
├── portfolio.py                       # Portfolio management functions
├── ssibenefits.py                     # Social Security calculations
├── editable_table.py                  # Standalone table editor
├── components/
│   └── sidebar.py                     # Sidebar configuration
├── pages/
│   ├── calculators.py                 # Additional calculator pages
│   └── flow_of_funds.py               # Cash flow analysis
├── .streamlit/
│   └── config.toml                    # Streamlit configuration
├── requirements.txt                   # Python dependencies
├── run.sh                             # Main app setup and run script
├── run_strategy.sh                    # Withdrawal strategy runner
├── README.md                          # This file (main documentation)
├── WITHDRAWAL_STRATEGY_README.md      # Withdrawal strategy documentation
├── IMPLEMENTATION_SUMMARY.md          # Implementation details
├── ERRORS_FOUND.md                    # Bug fixes and code analysis
├── LOGGING_GUIDE.md                   # Debug logging guide
├── *.csv                              # Data files
└── example*.csv                       # Generated strategy outputs
```

## Key Modules & Functions

### Withdrawal Strategy ([`withdrawal_strategy.py`](withdrawal_strategy.py))
**NEW: Complete 5-stage retirement withdrawal engine**
- `PortfolioBalances` - Portfolio account container
- `WithdrawalStrategyEngine` - Main calculation engine
- `Stage1Accumulation` - Working years strategy
- `Stage2EarlyRetirement` - Pre-Medicare optimization
- `Stage3Medicare` - IRMAA-aware conversions
- `Stage4SocialSecurity` - SS + Medicare management
- `Stage5RMD` - RMD compliance
- `build_withdrawal_strategy_display()` - Main entry point
- `calculate_aca_subsidy()` - ACA marketplace subsidies
- `generate_strategy_summary()` - Summary statistics
- `print_strategy_report()` - Formatted reporting

### Tax Calculations ([`calculations.py`](calculations.py))
**Enhanced with configurable debug logging**
- `calc_roth_conversions()` - Calculate optimal Roth conversion amounts
- `calc_agi()` - Compute Adjusted Gross Income
- `calculate_taxable_income()` - Calculate federal income tax
- `calculate_cap_gains()` - Calculate capital gains tax
- `calculate_irmma_penalty()` - Calculate Medicare IRMAA surcharges
- `calculate_atm()` - Calculate Alternative Minimum Tax
- `calc_daf_value()` - Calculate optimal charitable contributions

### Portfolio Management ([`portfolio.py`](portfolio.py))
- `build_portfolio_display()` - Generate portfolio summary with live prices
- `get_current_price()` - Fetch real-time stock prices via Yahoo Finance
- `get_current_dividend()` - Calculate dividend income
- `calculate_current_value()` - Compute current portfolio value
- `calculate_cost_basis()` - Track investment cost basis

### Data Loading ([`load_data.py`](load_data.py))
- `get_income_tax_brackets()` - Load tax brackets for specified year
- `get_cap_gains_brackets()` - Load capital gains rates
- `get_networth_by_month()` - Calculate net worth with current market values
- `get_medicare_costs()` - Load IRMAA brackets
- `get_atm_costs()` - Load AMT parameters

### Social Security ([`ssibenefits.py`](ssibenefits.py))
- Social Security benefit calculations based on claiming age
- Integration with retirement planning projections

## Documentation

### Core Documentation
- **[`README.md`](README.md)** (this file) - Main application documentation
- **[`WITHDRAWAL_STRATEGY_README.md`](WITHDRAWAL_STRATEGY_README.md)** - Complete withdrawal strategy guide (625 lines)
  - Installation and setup
  - API documentation
  - Strategy explanations for each life stage
  - Tax optimization techniques
  - Integration examples
  - Troubleshooting guide

### Implementation Details
- **[`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md)** - Development summary (307 lines)
  - What was built
  - Key capabilities
  - Technical architecture
  - Test results
  - Integration points

### Technical Guides
- **[`LOGGING_GUIDE.md`](LOGGING_GUIDE.md)** - Debug logging configuration (129 lines)
  - Enabling debug output
  - Log levels and format
  - Functions with logging
  - Usage examples

- **[`ERRORS_FOUND.md`](ERRORS_FOUND.md)** - Bug fixes and code analysis (193 lines)
  - Fixed syntax errors
  - Code quality observations
  - Testing recommendations
  - Security considerations

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

### Fixed Issues ✅
All critical bugs have been resolved:
1. ✅ **[`portfolio.py:30`](portfolio.py)**: Fixed f-string syntax error
2. ✅ **Missing dependencies**: Complete [`requirements.txt`](requirements.txt) created
3. ✅ **Debug statements**: Converted to configurable logging system

See [`ERRORS_FOUND.md`](ERRORS_FOUND.md) for complete analysis.

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

### Current Limitations
- **Portfolio editing**: Interface marked as "roadmap" feature (not yet functional)
- **State taxes**: Simplified 3% flat rate (can be customized)
- **AMT calculations**: May need verification for complex scenarios
- **Market volatility**: Uses constant growth rate (no Monte Carlo simulation)
- **Healthcare costs**: IRMAA only; no long-term care modeling

## Usage Examples

### Running Withdrawal Strategy Analysis

```bash
# Run all example scenarios
./run_strategy.sh

# Or run directly with Python
python3 example_withdrawal_strategy.py
```

### Using in Python Code

```python
from withdrawal_strategy import (
    PortfolioBalances,
    build_withdrawal_strategy_display,
    generate_strategy_summary
)

# Define portfolio
balances = PortfolioBalances(
    cash=55000,
    taxable=225000,
    traditional=670000,
    roth=168000,
    daf=0
)

# Calculate 26-year strategy
strategy_df, balances_df = build_withdrawal_strategy_display(
    start_year=2026,
    end_year=2051,
    initial_balances=balances,
    initial_expenses=120000,
    growth_rate=1.07,  # 7% annual growth
    ss_claiming_age=67
)

# Generate summary
summary = generate_strategy_summary(strategy_df)
print(f"Total Roth Conversions: ${summary['total_roth_conversions']:,.0f}")
print(f"Total Taxes Paid: ${summary['total_taxes']:,.0f}")
print(f"Final Portfolio: ${summary['final_portfolio']:,.0f}")

# Save results
strategy_df.to_csv("my_strategy.csv", index=False)
```

### Enabling Debug Logging

```bash
# Enable detailed calculation logging
export LOG_LEVEL=DEBUG
streamlit run planning_app.py

# Or for withdrawal strategy
export LOG_LEVEL=DEBUG
python3 example_withdrawal_strategy.py
```

See [`LOGGING_GUIDE.md`](LOGGING_GUIDE.md) for complete logging documentation.

## Testing

### Run Withdrawal Strategy Tests

```bash
python3 test_withdrawal_strategy.py
```

**Test Coverage:**
- ✅ Portfolio balance calculations
- ✅ Life stage determination logic
- ✅ ACA subsidy calculations
- ✅ Withdrawal engine functionality
- ✅ Strategy calculation pipeline
- ✅ YearlyStrategy structure validation

All tests passing with 6 test categories.

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
- Review [`portfolio.csv`](portfolio.csv) format matches expected columns
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

## Performance

- **Calculation Speed**: ~2 seconds for 26-year projection
- **Memory Usage**: Minimal (DataFrame-based operations)
- **Caching**: Leverages Streamlit `@st.cache_data` for efficiency
- **Scalability**: Handles portfolios from $100K to $10M+
- **API Efficiency**: Batch stock price fetching

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

This project uses code from Stack Overflow (CC BY-SA 4.0) as noted in [`portfolio.py`](portfolio.py).

## Version History

### Current Version (February 2026)
- ✅ **5-Stage Withdrawal Strategy**: Complete life-cycle planning engine
- ✅ **Enhanced Logging**: Configurable debug output throughout
- ✅ **Example Scenarios**: 4 pre-built retirement strategies
- ✅ **Test Suite**: Comprehensive validation (all tests passing)
- ✅ **Bug Fixes**: Resolved f-string syntax error
- ✅ **Documentation**: 4 comprehensive guides (1,500+ lines)
- ✅ **Run Scripts**: Automated setup for app and strategies

### Previous Features
- Tax year support: 2023-2027
- Retirement projections through 2051
- Real-time portfolio tracking via Yahoo Finance
- Multi-year tax planning
- IRMAA and AMT calculations

## Support

For issues or questions:
1. Review this README thoroughly
2. Check CSV file formats match requirements
3. Verify all dependencies are installed
4. Test with sample data files first
5. Consult official IRS and SSA resources for tax/benefit questions
6. Review documentation files for detailed guidance:
   - [`WITHDRAWAL_STRATEGY_README.md`](WITHDRAWAL_STRATEGY_README.md) - Withdrawal strategies
   - [`LOGGING_GUIDE.md`](LOGGING_GUIDE.md) - Debug logging
   - [`ERRORS_FOUND.md`](ERRORS_FOUND.md) - Bug fixes
   - [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md) - Technical details

## Additional Resources

### Financial Planning
- [FINRA Investor Education](https://www.finra.org/investors)
- [SEC Investor Information](https://www.investor.gov/)
- [Consumer Financial Protection Bureau](https://www.consumerfinance.gov/)

### Retirement Planning Tools
- [SSA Retirement Estimator](https://www.ssa.gov/benefits/retirement/estimator.html)
- [IRS Retirement Plans Overview](https://www.irs.gov/retirement-plans)
- [DOL Retirement Toolkit](https://www.dol.gov/general/topic/retirement)

## Future Enhancements (Roadmap)

### Planned Features
1. **Monte Carlo Simulation** - Market volatility modeling with success probabilities
2. **State Tax Integration** - State-specific tax calculations
3. **Healthcare Cost Modeling** - Detailed medical expense projections
4. **Estate Planning** - Beneficiary optimization and estate tax considerations
5. **Interactive Visualizations** - Enhanced Streamlit charts and graphs
6. **Portfolio Rebalancing** - Automated rebalancing recommendations
7. **What-If Scenarios** - Interactive parameter adjustment
8. **PDF Report Generation** - Comprehensive retirement plan exports

### Contributions Welcome
See development guidelines in the Contributing section above.

---

**Made with IBM Bob** | Last Updated: 2026-02-22

## Quick Links

- 📖 [Withdrawal Strategy Guide](WITHDRAWAL_STRATEGY_README.md)
- 🔧 [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- 🐛 [Bug Fixes & Analysis](ERRORS_FOUND.md)
- 📝 [Logging Guide](LOGGING_GUIDE.md)
- 🚀 [Run Main App](run.sh)
- 📊 [Run Strategy Examples](run_strategy.sh)