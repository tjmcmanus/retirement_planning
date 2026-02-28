# Financial Planner

A comprehensive Streamlit-based financial planning application for tax optimization, portfolio management, and long-term financial projections with a sophisticated 6-stage life-cycle withdrawal strategy engine.

## Overview

This application helps users plan their retirement by:
- **6-Stage Life-Cycle Strategy**: Comprehensive planning from accumulation through RMD phase, including a dedicated pre-retirement prep stage
- **Roth Conversion Optimization**: Intelligent conversions to minimize lifetime tax burden
- **Tax Projection**: Multi-year federal and state tax calculations
- **Portfolio Management**: Real-time tracking with Yahoo Finance integration
- **Social Security Modeling**: Benefits optimization based on claiming age
- **IRMAA Management**: Medicare surcharge optimization with 2-year lookback
- **ACA Subsidy Optimization**: Healthcare cost management for early retirees
- **Net Worth Tracking**: Comprehensive account monitoring across all types
- **Charitable Planning**: Donor Advised Fund (DAF) contribution strategies
- **RMD Compliance**: Automatic Required Minimum Distribution calculations

### 🆕 NEW: BETR Roth Conversion Algorithm
Advanced Roth conversion analysis based on Vanguard research:
- **Break-Even Tax Rate (BETR)**: Calculate the future tax rate that makes conversion indifferent
- **Smart Optimization**: Find optimal conversion amounts to stay within target tax brackets
- **Multi-Factor Analysis**: Accounts for tax payment source, nontaxable basis, and future opportunities
- **Scenario Comparison**: Analyze multiple conversion strategies side-by-side
- **Integration Ready**: Works seamlessly with existing tax calculations and withdrawal strategies

See [`BETR_GUIDE.md`](BETR_GUIDE.md) for complete documentation and [`betr_roth_conversion.py`](betr_roth_conversion.py) for implementation.

## Recent Updates (February 2026)

### 🎯 New: Configuration System & Portfolio Data Management
Complete configuration management system with portfolio data entry:
- **Centralized Configuration**: Store all planning parameters in `retirement_config.json`
- **Portfolio Data Entry**: Interactive data editor for investment holdings
- **Account Management**: Define and organize investment accounts by type
- **Automatic Backups**: Timestamped backups of portfolio data before each save
- **Data Validation**: Built-in validation for account types, sectors, and completeness
- **Import/Export**: Backup and restore configurations as JSON files
- **Minimum Data Requirement**: At least 2 months of portfolio data required

See [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) for complete configuration documentation.

### ✨ New: 6-Stage Life-Cycle Strategy Module
Complete retirement life-cycle strategy implementation covering all phases:
- **Stage 1: Accumulation** - Tax-efficient asset building; wages routed to Traditional 401k, Roth, brokerage, and cash buffer (configurable contribution rates)
- **Stage 2: Prep for Retirement** - Within 10 years of retirement; cash buffer ramps from wages-based target up to 75% of full retirement reserve
- **Stage 3: Early Retirement** - Aggressive Roth conversions, ACA optimization
- **Stage 4: Medicare** - IRMAA-aware conversion strategies
- **Stage 5: Social Security** - SS taxation and benefit optimization
- **Stage 6: RMD** - Required distribution compliance and management

See [`STRATEGY_README.md`](STRATEGY_README.md) for complete documentation.

### 🆕 NEW: Advanced Tax Planning & Healthcare Features
Comprehensive tax optimization and healthcare cost modeling in [`strategy.py`](strategy.py):
- **State Tax Planning**: Multi-state calculations with retirement-friendly state handling
  - No-tax states (FL, TX, WA, NV, SD, WY, AK, TN, NH)
  - Retirement-friendly states with full exemptions (PA, IL, MS)
  - Progressive brackets for high-tax states (CA, NY, NJ, MA, CO, NC)
  - Automatic integration with `retirement_state` from config.py
- **AMT Calculation**: Full Alternative Minimum Tax with exemption phase-out
  - 26%/28% AMT rate structure
  - State tax add-back and ISO spread handling
  - Exemption phase-out at high income levels
- **NIIT Planning**: Net Investment Income Tax (3.8% surtax) calculation
  - Applies to investment income above MAGI thresholds
  - MFJ: $250,000 | Single: $200,000 | MFS: $125,000
  - Strategic planning to minimize surtax exposure
- **Healthcare Cost Projections**: Comprehensive medical expense modeling
  - Medicare Part B/D with IRMAA surcharges (2-year lookback)
  - Medigap supplemental coverage
  - Pre-Medicare ACA marketplace costs (ages 62-65)
  - Out-of-pocket expenses by health status
  - Long-term care insurance premiums
  - Multi-year projections with age transitions

See [`strategy_plan.yaml`](strategy_plan.yaml) for detailed specifications.

### 🔧 Enhanced Logging System
Configurable debug logging throughout [`calculations.py`](calculations.py):
- Environment variable control (`LOG_LEVEL=DEBUG`)
- Detailed calculation tracing
- Tax computation debugging
- See [`LOGGING_GUIDE.md`](LOGGING_GUIDE.md) for usage

### 📊 Example Scenarios
Four pre-built withdrawal strategy scenarios in [`example_strategy.py`](example_strategy.py):
1. Basic retirement strategy ($1.1M portfolio)
2. Early retirement with aggressive conversions ($1.5M portfolio)
3. High-income IRMAA optimization ($3.7M portfolio)
4. Custom scenario builder

### 🧪 Test Suite
Comprehensive validation in [`test_strategy.py`](test_strategy.py):
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

### 0. Configuration Page (⚙️)
**NEW: Centralized configuration management**
- **Personal Information**: Names, birth dates, retirement ages with automatic age calculation
- **Financial Assumptions**: Expenses, inflation, returns, cash reserves
- **Healthcare Settings**: ACA insurance premiums, Medicare start age
- **Social Security**: Benefit amounts and claiming ages for both spouses
- **Tax Strategy**: Roth conversion parameters, DAF disbursement rates
- **Portfolio Accounts**: Define investment accounts with names and types (e.g., "Schwab" - "Roth")
- **Portfolio Data Entry**: Interactive editor for detailed holdings with validation
  - Requires at least 2 months of data for proper application functionality
  - Automatic timestamped backups before each save
  - Real-time validation of account types and sectors
- **Configuration Management**: Export/import, backup/restore, reset to defaults

See [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) for detailed configuration instructions.

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

### 4. Strategy Tab
- **Accumulation Phase**: Year-by-year projection during working years (Stage 1 & 2)
- **Withdrawal Phase**: Distribution planning from retirement through RMD stage
- **Long-term Projections**: Model retirement through 2051
- **Social Security Integration**: Calculate benefits based on claiming age
- **Required Minimum Distributions (RMD)**: Automatic RMD calculations
- **Expense Modeling**: Project expenses with inflation adjustments
- **Portfolio Withdrawal Strategy**: 6-stage life-cycle optimization
- **Cash Flow Analysis**: Year-by-year inflows and outflows through 2051
- **Withdrawal Sequencing**: Tax-efficient account prioritization

## Getting Started

### Quick Start Guide

1. **Install and Run** (see Installation section below)
2. **Configure Your Settings** - Navigate to the Configuration page (⚙️ icon)
   - Fill in personal information, financial assumptions, and tax strategy
   - See [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) for detailed setup instructions
3. **Enter Portfolio Data** - Use the Portfolio Data tab in Configuration
   - Define your investment accounts (names and types)
   - Enter at least 2 months of portfolio holdings
   - Save with automatic backup protection
4. **Explore the Application** - Use the main tabs to analyze your retirement plan

### Installation

#### Prerequisites
- Python 3.8 or higher
- pip package manager

#### Setup

**Linux/Mac:**

1. Clone or download this repository:
```bash
cd retirement_planning
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install required dependencies:
```bash
pip install -r requirements.txt
```

**Windows:**

⚠️ **Note:** Windows support is provided via `run.bat` but has not been tested. Please report any issues.

1. Clone or download this repository:
```cmd
cd retirement_planning
```

2. Create a virtual environment (recommended):
```cmd
python -m venv .venv
.venv\Scripts\activate
```

3. Install required dependencies:
```cmd
pip install -r requirements.txt
```

**Windows-Specific Notes:**
- Ensure Python is added to your PATH during installation
- You may need to run Command Prompt or PowerShell as Administrator
- If you encounter execution policy errors in PowerShell, run:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```
- The `run.bat` script handles most setup automatically

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

### Portfolio Data Files

#### Primary Data File (REQUIRED)
- **`portfolio_data_truth.csv`**: Portfolio holdings with monthly snapshots
  - **Columns**: `month`, `year`, `account_name`, `account_type`, `symbol`, `name`, `sector`, `qty`, `purchase_price`
  - **Minimum Requirement**: At least 2 months of data required for proper application functionality
  - **Account Types**: Cash, Brokerage, Traditional, Roth
  - **Data Entry**: Use the Configuration page (⚙️) → Portfolio Data tab for interactive data entry
  - **Automatic Backups**: Timestamped backups created before each save (`portfolio_data_truth_YYYYMMDD_HHMMSS.csv`)
  - **Dynamic Valuation**: Application calculates current market values using Yahoo Finance API
  - **Net Worth Calculation**: Automatically computed from portfolio holdings with real-time prices
  - See [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) for detailed data entry instructions

#### Legacy Files (DEPRECATED - Not Used by Application)
The following files are **no longer used** by the application but sample files remain for reference:
- ~~`financial_data.csv`~~ - Replaced by dynamic calculation from `portfolio_data_truth.csv`
- ~~`financial_account.csv`~~ - Replaced by account aggregation from `portfolio_data_truth.csv`
- ~~`portfolio.csv`~~ - Replaced by `portfolio_data_truth.csv`

**Migration Note**: The application has transitioned from static CSV files to a dynamic portfolio tracking system. All net worth and account data is now calculated in real-time from `portfolio_data_truth.csv` using current market prices.

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

**Linux/Mac:**
```bash
./run.sh
```

**Windows:**
```cmd
run.bat
```

⚠️ **Windows Note:** The `run.bat` script has not been tested on Windows. If you encounter issues, please use Method 2 (Manual Start) below and report any problems.

The run script will:
- Check for Python installation
- Create/activate virtual environment
- Install dependencies
- Verify required files
- Start the Streamlit application

### Method 2: Manual Start (Recommended for Windows)
1. Ensure all required CSV files are in place (use sample files if needed)

2. Activate virtual environment:

**Linux/Mac:**
```bash
source .venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

3. Start the Streamlit application:
```bash
streamlit run planning_app.py
```

4. The application will open in your default web browser at `http://localhost:8501`

**Windows Troubleshooting:**
- If `streamlit` command is not found, try: `python -m streamlit run planning_app.py`
- If you get permission errors, run Command Prompt as Administrator
- If PowerShell blocks script execution, see installation notes above for execution policy

## Configuration

### Configuration System
The application now uses a centralized configuration system. See [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) for complete documentation.

**Key Configuration Files:**
- `retirement_config.json` - Main configuration file (auto-created)
- `portfolio_data_truth.csv` - Portfolio holdings data (requires at least 2 months)
- `portfolio_data_truth_YYYYMMDD_HHMMSS.csv` - Automatic timestamped backups

**Configuration Page (⚙️):**
Access through the sidebar to manage:
- Personal information and retirement ages
- Financial assumptions and expense projections
- Healthcare costs (ACA and Medicare)
- Social Security benefit planning
- Tax strategy and Roth conversions
- Portfolio accounts and holdings data
- Import/export and backup/restore

### Sidebar Settings (Legacy)
The sidebar still provides quick access to key parameters (see [`components/sidebar.py`](components/sidebar.py)):
- **Social Security Age**: Age to begin claiming benefits (default: 70)
- **Roth Conversion at SSI Age**: Annual conversion amount after SS starts
- **Max Tax Rate for Roth Conversion**: Target marginal tax rate (default: 24%)
- **Expected Annual Expenses**: Projected yearly spending
- **Expense Multiplier**: Safety margin for brokerage account (default: 4x)
- **Expected Annual Rate of Return**: Investment growth rate (default: 6%)
- **DAF Disbursement Rate**: Annual charitable giving rate (default: 25%)

**Note:** For permanent changes, use the Configuration page. Sidebar changes are temporary (session-only).

## Project Structure

```
retirement_planning/
├── planning_app.py                    # Main Streamlit application
├── config.py                          # Configuration management system
├── portfolio_data_entry.py            # Portfolio data entry and validation
├── strategy.py             # 6-stage life-cycle strategy engine
├── betr_roth_conversion.py            # BETR Roth conversion algorithm
├── ssi_calculator.py                  # Dynamic SSI benefit calculator
├── generate_ssi_schedule.py           # SSI schedule generation script
├── example_withdrawal_strategy.py  # Withdrawal strategy example scenarios
├── example_accumulation_strategy.py  # Accumulation phase example scenarios
├── income_expense.py                  # Income/expense projections with RMD
├── calculations.py                    # Tax calculation functions (with logging)
├── load_data.py                       # Data loading utilities
├── portfolio.py                       # Portfolio management functions
├── ssibenefits.py                     # Social Security benefit lookups
├── editable_table.py                  # Standalone table editor demo
├── components/
│   └── sidebar.py                     # Sidebar configuration
├── pages/
│   ├── configuration.py               # Configuration page
│   ├── calculators.py                 # Additional calculator pages
│   └── flow_of_funds.py               # Cash flow analysis
├── .streamlit/
│   └── config.toml                    # Streamlit configuration
├── requirements.txt                   # Python dependencies
├── run.sh                             # Main app setup and run script
├── run_strategy.sh                    # Withdrawal strategy runner
├── README.md                          # This file (main documentation)
├── CONFIG_GUIDE.md                    # Configuration system guide
├── BETR_GUIDE.md                      # BETR Roth conversion guide
├── SSI_CALCULATOR_GUIDE.md            # SSI calculator documentation
├── SSI_INTEGRATION_GUIDE.md           # SSI integration with withdrawal strategy
├── STRATEGY_README.md      # Withdrawal strategy documentation
├── IMPLEMENTATION_SUMMARY.md          # Implementation details
├── ACCOUNT_REBALANCING_IMPLEMENTATION.md  # Account rebalancing feature
├── BETR_CORRECTION_NOTES.md           # BETR algorithm corrections
├── ERRORS_FOUND.md                    # Bug fixes and code analysis
├── LOGGING_GUIDE.md                   # Debug logging guide
├── DOCUMENTATION_REVIEW_SUMMARY.md    # Documentation review and gaps
├── retirement_config.json             # Configuration file (auto-created)
├── portfolio_data_truth.csv           # Portfolio holdings data
├── portfolio_data_truth_*.csv         # Timestamped backups
├── *.csv                              # Tax reference data files
├── example*.csv                       # Generated strategy outputs
└── test_*.py                          # Test suites for various modules
```

### Income & Expense Projections ([`income_expense.py`](income_expense.py))
**Purpose:** Multi-year income and expense projections with portfolio tracking

**Key Functions:**
- `build_income_expenses_display()` - Generate 25-year income/expense projections
- `calculate_taxes()` - Calculate federal taxes for a given year
- `_calculate_year_distributions()` - Determine planned distributions and conversions
- `_calculate_rmd_and_update_trad()` - Calculate RMDs and update Traditional IRA balance
- `_load_portfolio_data()` - Load current portfolio data with error handling

**Features:**
- Integrates with SSI calculator for dynamic benefit calculations
- Tracks portfolio balances across all account types
- Calculates RMDs based on age and IRS tables
- Projects expenses with inflation adjustments
- Generates comprehensive income/expense DataFrames

**Integration:**
- Uses [`config.py`](config.py) for personal and financial settings
- Calls `ssi_calculator.generate_ssi_schedule_from_config()` for SSI benefits
- Uses [`calculations.py`](calculations.py) for tax calculations
- Loads portfolio data via `load_data.get_networth_by_month()`

### Portfolio Data Entry ([`portfolio_data_entry.py`](portfolio_data_entry.py))
**Purpose:** Manual entry, validation, and management of portfolio holdings

**Key Functions:**
- `validate_ticker_symbol()` - Validate ticker symbols via Yahoo Finance
- `validate_portfolio_entry()` - Validate single portfolio entry
- `validate_portfolio_dataframe()` - Validate entire portfolio DataFrame
- `save_portfolio_data()` - Save/update portfolio data with merge logic
- `load_previous_month_data()` - Load previous month as template
- `backup_portfolio_data()` - Create timestamped backups
- `create_blank_portfolio_file()` - Initialize new portfolio file

**Features:**
- Real-time ticker validation using yfinance
- Automatic sector and name lookup
- Update/overwrite logic for existing entries
- Timestamped automatic backups
- Comprehensive validation rules
- Support for multiple account types (Cash, Brokerage, Traditional, Roth)

**Data Format:**
- Columns: month, year, account_name, account_type, symbol, name, sector, qty, purchase_price
- Stored in `portfolio_data_truth.csv`
- Backups: `portfolio_data_truth_YYYYMMDD_HHMMSS.csv`

### SSI Calculator ([`ssi_calculator.py`](ssi_calculator.py))
**Purpose:** Dynamic Social Security benefit calculations based on claiming age

**Key Functions:**
- `calculate_benefit_at_claiming_age()` - Calculate benefit for specific claiming age
- `calculate_benefit_with_cola()` - Apply COLA adjustments over time
- `generate_ssi_schedule()` - Generate complete benefit schedule for one person
- `generate_ssi_schedule_from_config()` - Generate schedule from config.py settings
- `validate_config_ssi_settings()` - Validate SSI configuration

**Features:**
- Implements SSA early claiming reduction rules (ages 62-66)
- Implements delayed retirement credits (ages 68-70, 8% per year)
- Applies annual COLA adjustments (default 2%)
- Integrates with [`config.py`](config.py) for automatic schedule generation
- Replaces static CSV with dynamic calculations

**Formula:**
- Early claiming: 5/9 of 1% per month (first 36 months), 5/12 of 1% per month (beyond 36)
- Delayed claiming: 8% per year increase
- COLA: Compound annual adjustment after claiming

**See Also:** [`SSI_CALCULATOR_GUIDE.md`](SSI_CALCULATOR_GUIDE.md), [`SSI_INTEGRATION_GUIDE.md`](SSI_INTEGRATION_GUIDE.md)

## Key Modules & Functions

### Withdrawal Strategy ([`strategy.py`](strategy.py))
**Complete 6-stage life-cycle strategy engine with advanced tax planning**

**Core Strategy Engine:**
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

**🆕 State Tax Planning:**
- `calculate_state_tax()` - Multi-state income tax calculation
  - Handles no-tax states (FL, TX, WA, NV, SD, WY, AK, TN, NH)
  - Retirement-friendly states with exemptions (PA, IL, MS)
  - Progressive brackets for high-tax states (CA, NY, NJ, MA, CO, NC)
  - Automatic config integration with `retirement_state` parameter
  - Returns (state_tax, calculation_details)

**🆕 AMT Planning:**
- `calculate_amt()` - Alternative Minimum Tax calculation
  - Full AMT calculation with exemption phase-out
  - 26%/28% AMT rate structure
  - State tax add-back, ISO spread, private activity bonds
  - Returns (amt_owed, tentative_amt, regular_tax, details)

**🆕 NIIT Planning:**
- `calculate_net_investment_income()` - Net Investment Income calculation
  - Aggregates interest, dividends, capital gains, rental income, royalties
  - Excludes retirement account distributions
- `calculate_niit()` - Net Investment Income Tax (3.8% surtax)
  - Applies to lesser of NII or excess MAGI over thresholds
  - MFJ: $250,000 | Single: $200,000 | MFS: $125,000
  - Returns (niit_amount, calculation_details)

**🆕 Healthcare Cost Projections:**
- `calculate_medicare_costs()` - Medicare Part B/D with IRMAA
  - Integrates with existing `calculate_irmma_penalty()` function
  - 2-year MAGI lookback for IRMAA surcharges
  - Optional Medigap supplemental coverage
- `calculate_total_healthcare_costs()` - Comprehensive medical expenses
  - Medicare or pre-Medicare ACA costs
  - Out-of-pocket expenses by health status (healthy/average/chronic)
  - Long-term care insurance premiums
- `project_healthcare_costs()` - Multi-year healthcare projections
  - Handles age transitions (pre-Medicare → Medicare)
  - IRMAA lookback with MAGI projections
  - Returns DataFrame with year-by-year breakdown
### BETR Roth Conversion ([`betr_roth_conversion.py`](betr_roth_conversion.py))
**NEW: Advanced Roth conversion analysis based on Vanguard research**
- `BETRInputs` - Input parameters dataclass
- `BETRResults` - Results dataclass with detailed analysis
- `calculate_betr()` - Calculate Break-Even Tax Rate
- `optimize_conversion_amount()` - Find optimal conversion to stay in target bracket
- `analyze_conversion_scenarios()` - Compare multiple conversion amounts
- `print_betr_report()` - Generate formatted analysis report


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
- **[`CONFIG_GUIDE.md`](CONFIG_GUIDE.md)** - Configuration system guide (NEW - 256 lines)
  - Configuration page walkthrough
  - Portfolio data entry instructions
  - Account management
  - Backup and restore procedures
  - API reference
  - Troubleshooting
- **[`STRATEGY_README.md`](STRATEGY_README.md)** - Complete withdrawal strategy guide (625 lines)
  - Installation and setup
  - API documentation
  - Strategy explanations for each life stage
  - Tax optimization techniques
  - Integration examples
- **[`BETR_GUIDE.md`](BETR_GUIDE.md)** - BETR Roth conversion guide (NEW - 600 lines)
  - BETR methodology explanation
  - Quick start examples
  - API reference
  - Integration with existing modules
  - Use cases and scenarios
  - Decision framework
  - Best practices
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
- **Portfolio Data**: Use `portfolio_data_truth.csv` with at least 2 months of holdings data
- **Data Entry**: Use the Configuration page (⚙️) for interactive portfolio data management
- **Real-time Valuation**: Portfolio values calculated dynamically using Yahoo Finance API
- **Valid Tickers**: Ensure stock symbols are valid on Yahoo Finance
- **Tax Reference Files**: Update annually to reflect current IRS rates (income_rates.csv, standard.csv, etc.)
- **Legacy Sample Files**: Provided for reference only; not used by the application

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
- **Windows support**: `run.bat` script provided but not tested on Windows systems

### Windows-Specific Issues
⚠️ **The application has not been tested on Windows.** Known potential issues:

1. **Path Separators**: Windows uses backslashes (`\`) vs forward slashes (`/`)
   - Most Python code should handle this automatically
   - File paths in CSV files may need adjustment

2. **Virtual Environment Activation**:
   - Command Prompt: `.venv\Scripts\activate`
   - PowerShell: `.venv\Scripts\Activate.ps1`
   - May require execution policy changes in PowerShell

3. **Line Endings**: CSV files may have different line endings (CRLF vs LF)
   - Python's CSV module should handle this automatically
   - If issues occur, convert files to Windows line endings

4. **Color Output**: The `run.bat` script uses ANSI color codes
   - May not display correctly in older Command Prompt versions
   - Works best in Windows Terminal or PowerShell

5. **File Permissions**: Some operations may require Administrator privileges

**If you encounter Windows-specific issues:**
- Use Method 2 (Manual Start) instead of `run.bat`
- Report issues with detailed error messages
- Consider using WSL (Windows Subsystem for Linux) as an alternative

## Usage Examples

### Running Withdrawal Strategy Analysis

```bash
# Run all example scenarios
./run_strategy.sh

# Or run directly with Python
python3 example_strategy.py
```

### Using in Python Code

```python
from strategy import (
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
python3 example_strategy.py
```

See [`LOGGING_GUIDE.md`](LOGGING_GUIDE.md) for complete logging documentation.

## Testing

### Run Withdrawal Strategy Tests

```bash
python3 test_strategy.py
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
Ensure all required CSV files exist. The primary data file needed is:
```bash
# The application requires portfolio_data_truth.csv
# Use the Configuration page (⚙️) to create and manage this file interactively
# Or create it manually with the required columns:
# month, year, account_name, account_type, symbol, name, sector, qty, purchase_price
```

**Note**: Legacy sample files (`financial_data_sample.csv`, `portfolio_sample.csv`, `financial_account_sample.csv`) are no longer used by the application. Use the Configuration page for data entry instead.

### Portfolio data not loading
- Verify stock tickers are valid (check on Yahoo Finance)
- Check internet connection for Yahoo Finance API
- Review [`portfolio_data_truth.csv`](portfolio_data_truth.csv) format matches expected columns
- Ensure required columns exist: `month`, `year`, `account_name`, `account_type`, `symbol`, `name`, `sector`, `qty`, `purchase_price`
- Verify at least 2 months of data are present
- Use the Configuration page (⚙️) → Portfolio Data tab to validate and edit data

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
1. **Use Configuration System**: Leverage the Configuration page for centralized settings management
2. **Backup regularly**: Export configuration JSON and keep copies of CSV files
3. **Portfolio Data**: Maintain at least 2 months of data; automatic backups are created on save
4. **Update annually**: Refresh tax bracket files with current IRS rates
5. **Verify calculations**: Cross-check results with tax software or professionals
6. **Use sample data first**: Test with sample files before using real financial data

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
- ✅ **Configuration System**: Centralized settings management with JSON storage
- ✅ **Portfolio Data Entry**: Interactive editor with validation and automatic backups
- ✅ **Account Management**: Define and organize investment accounts by type
- ✅ **6-Stage Life-Cycle Strategy**: Complete planning engine from accumulation through RMD
- ✅ **State Tax Planning**: Multi-state calculations with config integration
- ✅ **AMT Calculation**: Full Alternative Minimum Tax with exemption phase-out
- ✅ **NIIT Planning**: Net Investment Income Tax (3.8% surtax) calculation
- ✅ **Healthcare Cost Projections**: Medicare, IRMAA, pre-Medicare ACA, out-of-pocket expenses
- ✅ **Enhanced Logging**: Configurable debug output throughout
- ✅ **Example Scenarios**: 4 pre-built retirement strategies
- ✅ **Test Suite**: Comprehensive validation (all tests passing)
- ✅ **Bug Fixes**: Resolved f-string syntax error
- ✅ **Documentation**: 6 comprehensive guides (3,800+ lines total)
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
2. **Start with Configuration**: See [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) for setup instructions
3. Check CSV file formats match requirements
4. Verify all dependencies are installed
5. Test with sample data files first
6. Ensure at least 2 months of portfolio data are entered
7. Consult official IRS and SSA resources for tax/benefit questions
8. Review documentation files for detailed guidance:
   - [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) - Configuration system (NEW)
   - [`STRATEGY_README.md`](STRATEGY_README.md) - Withdrawal strategies
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

### High Priority Enhancements

#### 1. Withdrawal Strategy Refinements (Alpha → Production)
**Status: Alpha code - needs production hardening**
- **Validation & Testing**
  - Add comprehensive edge case testing (zero balances, negative returns, extreme ages)
  - Implement boundary condition validation (e.g., RMD age changes, SS claiming limits)
  - Add integration tests with real historical market data
  - Create regression test suite for tax calculations
- **Strategy Optimization**
  - Implement dynamic Roth conversion optimization based on future tax bracket projections
  - Add intelligent IRMAA cliff avoidance (stay just below thresholds)
  - Optimize ACA subsidy maximization with income targeting
  - Add multi-year tax planning (look-ahead optimization)
- **Error Handling**
  - Add graceful degradation when data is missing
  - Implement validation for impossible scenarios (e.g., negative balances)
  - Add warning system for suboptimal strategies
  - Create detailed error messages with remediation suggestions

#### 2. Monte Carlo Simulation Engine
**Priority: High - Critical for realistic retirement planning**
- **Core Simulation**
  - Implement 10,000+ iteration Monte Carlo analysis
  - Model market volatility using historical return distributions
  - Add sequence-of-returns risk analysis
  - Calculate probability of success metrics (e.g., 90% confidence intervals)
- **Scenario Analysis**
  - Best case / worst case / median outcome projections
  - Stress testing (2008 crash, stagflation, etc.)
  - Longevity risk modeling (living to 95, 100, 105)
  - Inflation shock scenarios
- **Visualization**
  - Fan charts showing outcome distributions
  - Success probability heatmaps
  - Interactive scenario comparison tools
  - Downloadable Monte Carlo reports

#### 3. Advanced Tax Optimization
**Status: ✅ PARTIALLY IMPLEMENTED - Core features complete, advanced strategies pending**

**✅ Implemented (February 2026):**
- **State Tax Integration** - `calculate_state_tax()` function
  - Multi-state tax calculations (no-tax, retirement-friendly, high-tax states)
  - Retirement income exemptions and SS benefit exclusions
  - Progressive brackets for CA, NY, NJ, MA, CO, NC
  - Automatic config integration with `retirement_state` parameter
- **AMT Calculation** - `calculate_amt()` function
  - Full Alternative Minimum Tax with exemption phase-out
  - 26%/28% AMT rate structure
  - State tax add-back, ISO spread, private activity bonds
- **NIIT Planning** - `calculate_niit()` function
  - Net Investment Income Tax (3.8% surtax) calculation
  - Strategic planning to minimize surtax exposure
  - Integration with MAGI thresholds by filing status

**🔄 Still Pending:**
- **Multi-Year Tax Planning**
  - 5-year rolling tax optimization window
  - Bracket management across multiple years
  - Capital loss harvesting strategies
  - Qualified Business Income (QBI) deduction planning
- **Advanced Strategies**
  - Backdoor Roth IRA contribution tracking
  - Mega backdoor Roth strategies
  - Net Unrealized Appreciation (NUA) for company stock
  - Qualified Charitable Distributions (QCD) optimization
  - 72(t) SEPP (Substantially Equal Periodic Payments) calculations

### Medium Priority Enhancements

#### 4. Healthcare Cost Modeling
**Status: ✅ IMPLEMENTED (February 2026)**

**✅ Implemented:**
- **Comprehensive Medical Expenses** - `calculate_medicare_costs()`, `calculate_total_healthcare_costs()`
  - Medicare Part B/D premium projections with IRMAA integration
  - Medigap policy cost modeling ($2,400/year per person)
  - Out-of-pocket expense estimates by health status (healthy/average/chronic)
  - Long-term care insurance integration ($3,500/year per person)
  - Pre-Medicare ACA marketplace costs (ages 62-65)
- **Multi-Year Projections** - `project_healthcare_costs()`
  - Year-by-year healthcare cost projections
  - Age transition handling (pre-Medicare → Medicare)
  - IRMAA 2-year lookback with MAGI projections
  - Returns detailed DataFrame with cost breakdowns

**🔄 Still Pending:**
- **Long-Term Care Planning**
  - Nursing home cost projections by state
  - Home health care expense modeling
  - Medicaid spend-down strategies
  - Self-insurance vs. LTC insurance analysis
- **HSA Integration**
  - Health Savings Account contribution tracking
  - HSA investment growth projections
  - HSA withdrawal strategies in retirement
  - Triple tax advantage optimization

#### 5. Estate Planning Module
**Priority: Medium - Important for wealth transfer**
- **Estate Tax Calculations**
  - Federal estate tax projections
  - State estate/inheritance tax calculations
  - Lifetime gift tax tracking
  - Generation-skipping transfer tax (GSTT)
- **Beneficiary Optimization**
  - IRA beneficiary designation strategies
  - Stretch IRA calculations (SECURE Act 2.0 compliant)
  - Trust beneficiary modeling
  - Spousal rollover vs. inherited IRA analysis
- **Charitable Giving**
  - Charitable Remainder Trust (CRT) modeling
  - Charitable Lead Trust (CLT) calculations
  - Private foundation vs. DAF comparison
  - Legacy giving impact analysis

#### 6. Portfolio Management Enhancements
**Priority: Medium - Improve investment tracking**
- **Advanced Portfolio Features**
  - Real-time portfolio editing (currently roadmap feature)
  - Automatic rebalancing recommendations
  - Dynamic tax-loss/gain harvesting with intelligent security selection
  - Optimized security selection for withdrawals (which specific holdings to liquidate)
  - Asset location optimization (tax-efficient placement)
  - Factor-based portfolio analysis
- **Performance Analytics**
  - Time-weighted vs. money-weighted returns
  - Benchmark comparison (S&P 500, custom indices)
  - Risk-adjusted return metrics (Sharpe, Sortino ratios)
  - Drawdown analysis and recovery periods
  - Contribution vs. growth attribution
- **Integration Enhancements**
  - Direct brokerage account integration (Schwab, Fidelity, Vanguard APIs)
  - Automatic transaction import
  - Real-time balance synchronization
  - Multi-currency support for international holdings

### Lower Priority / Nice-to-Have

#### 7. Enhanced Visualizations & Reporting
**Priority: Low - Improves user experience**
- **Interactive Dashboards**
  - Customizable dashboard layouts
  - Drag-and-drop widget arrangement
  - Real-time data refresh controls
  - Mobile-responsive design
- **Advanced Charts**
  - Waterfall charts for cash flow analysis
  - Sankey diagrams for money flow visualization
  - 3D surface plots for multi-variable optimization
  - Animated timeline visualizations
- **Report Generation**
  - PDF comprehensive retirement plan exports
  - Executive summary one-pagers
  - Detailed appendix with assumptions
  - Customizable report templates
  - Email scheduling for periodic reports

#### 8. Scenario Planning & What-If Analysis
**Priority: Low - Enhances planning flexibility**
- **Interactive Scenarios**
  - Side-by-side scenario comparison (up to 4 scenarios)
  - Real-time parameter adjustment with instant recalculation
  - Scenario saving and loading
  - Scenario sharing via URL parameters
- **Life Event Modeling**
  - Early retirement scenarios
  - Part-time work in retirement
  - Inheritance windfalls
  - Major expense events (home purchase, college funding)
  - Divorce/remarriage financial impact
  - Disability income scenarios

#### 9. Social Security Optimization
**Priority: Low - Refinement of existing feature**
- **Advanced SS Strategies**
  - File and suspend strategies (if applicable)
  - Spousal benefit optimization
  - Divorced spouse benefit calculations
  - Survivor benefit planning
  - Earnings test impact modeling (working while collecting)
- **Break-Even Analysis**
  - Claiming age break-even calculations
  - Net present value comparisons
  - Longevity-adjusted recommendations
  - Spousal coordination strategies

#### 10. Data Management & Security
**Priority: Low - Operational improvements**
- **Enhanced Data Management**
  - Cloud backup integration (encrypted)
  - Version control for configurations
  - Data import from financial software (Quicken, Mint, Personal Capital)
  - Bulk data entry tools
  - Data validation and cleanup utilities
- **Security Enhancements**
  - End-to-end encryption for sensitive data
  - Password protection for configuration files
  - Audit logging for data changes
  - Two-factor authentication option
  - GDPR/privacy compliance features

### Technical Debt & Code Quality

#### 11. Code Improvements
- **Refactoring**
  - Modularize withdrawal strategy into smaller, testable components
  - Implement dependency injection for better testability
  - Add type hints throughout codebase (currently partial)
  - Create abstract base classes for strategy patterns
- **Testing**
  - Increase test coverage to >80% (currently ~60% estimated)
  - Add property-based testing for tax calculations
  - Implement continuous integration (CI) pipeline
  - Add performance benchmarking tests
- **Documentation**
  - Add inline code documentation (docstrings) for all functions
  - Create API documentation with Sphinx
  - Add architecture decision records (ADRs)
  - Create video tutorials for common workflows

#### 12. Performance Optimization
- **Caching Improvements**
  - Implement Redis for distributed caching
  - Add intelligent cache invalidation
  - Optimize database queries (if DB added)
  - Lazy loading for large datasets
- **Computation Optimization**
  - Parallelize Monte Carlo simulations
  - Use NumPy vectorization for tax calculations
  - Implement incremental computation for large projections
  - Add progress indicators for long-running operations

### Integration & Ecosystem

#### 13. Third-Party Integrations
- **Financial Data Providers**
  - Alpha Vantage API for market data
  - IEX Cloud for real-time quotes
  - Morningstar API for fund analysis
  - Federal Reserve Economic Data (FRED) for economic indicators
- **Tax Software Integration**
  - TurboTax data export
  - H&R Block integration
  - TaxAct compatibility
  - IRS e-file format generation
- **Financial Planning Tools**
  - Export to Excel/Google Sheets with formulas
  - Import from other retirement calculators
  - Integration with financial advisor platforms
  - API for third-party tool integration

#### 14. Collaboration Features
- **Multi-User Support**
  - Shared planning sessions for couples
  - Financial advisor collaboration mode
  - Role-based access control
  - Comment and annotation system
- **Communication**
  - In-app messaging for advisor/client
  - Scheduled review reminders
  - Change notification system
  - Shared decision tracking

### Contributions Welcome
See development guidelines in the Contributing section above. Priority areas for community contributions:
1. **Withdrawal Strategy Testing** - Help move from alpha to production
2. **State Tax Calculations** - Contribute state-specific tax logic
3. **Monte Carlo Engine** - Implement simulation framework
4. **Documentation** - Improve guides and add examples
5. **Test Coverage** - Add unit and integration tests

---

**Made with IBM Bob** | Last Updated: 2026-02-23

## Quick Links

- ⚙️ [Configuration Guide](CONFIG_GUIDE.md) - **START HERE**
- 💰 [BETR Roth Conversion Guide](BETR_GUIDE.md) - **NEW**
- 📖 [Withdrawal Strategy Guide](STRATEGY_README.md)
- 🔧 [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- 🐛 [Bug Fixes & Analysis](ERRORS_FOUND.md)
- 📝 [Logging Guide](LOGGING_GUIDE.md)
- 🚀 [Run Main App](run.sh)
- 📊 [Run Strategy Examples](run_strategy.sh)