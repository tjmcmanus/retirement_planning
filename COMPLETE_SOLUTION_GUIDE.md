# Retirement Planning Application — Complete Solution Guide

**Version:** 2.0 (February 2026)  
**Last Updated:** March 2, 2026

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Core Features](#core-features)
4. [Getting Started](#getting-started)
5. [User Interface Guide](#user-interface-guide)
6. [Configuration System](#configuration-system)
7. [Portfolio Management](#portfolio-management)
8. [Tax Optimization](#tax-optimization)
9. [Withdrawal Strategy](#withdrawal-strategy)
10. [Advanced Features](#advanced-features)
11. [Data Management](#data-management)
12. [API Reference](#api-reference)
13. [Best Practices](#best-practices)
14. [Troubleshooting](#troubleshooting)
15. [Technical Details](#technical-details)

---

## Executive Summary

### What is This Application?

A comprehensive retirement planning tool that helps individuals and couples:
- **Plan** retirement income strategies across multiple life stages
- **Optimize** tax efficiency through Roth conversions, tax harvesting, and strategic withdrawals
- **Manage** investment portfolios with rebalancing and asset location guidance
- **Project** cash flows, healthcare costs, and Social Security benefits
- **Analyze** scenarios using Monte Carlo simulations

### Who Is It For?

- **Pre-retirees** (ages 50-65) planning their retirement transition
- **Early retirees** (ages 60-65) managing ACA healthcare and tax optimization
- **Retirees** (ages 65+) optimizing Medicare, Social Security, and RMDs
- **Financial planners** seeking sophisticated analysis tools
- **DIY investors** with $50K-$100M in retirement savings

### Key Differentiators

✅ **6-Stage Life-Cycle Strategy** — Automatically adapts to your life stage  
✅ **BETR Roth Conversion Algorithm** — Vanguard research-based optimization  
✅ **Tax-Efficient Rebalancing** — Minimizes tax impact while maintaining allocation  
✅ **Integrated Tax Harvesting** — Identifies loss/gain opportunities with wash-sale protection  
✅ **Healthcare Cost Modeling** — ACA subsidies, IRMAA, Medicare Part B/D  
✅ **Multi-Account Coordination** — Cash, Brokerage, Traditional IRA, Roth IRA, DAF  

---

## System Architecture

### Technology Stack

```
Frontend:  Streamlit (Python web framework)
Backend:   Python 3.9+
Data:      CSV files + JSON configuration
Pricing:   Yahoo Finance API (yfinance)
Charts:    Plotly
UI:        streamlit-option-menu (horizontal navigation)
```

### Application Structure

```
retirement_planning/
├── planning_app.py              # Main entry point (redirects to dashboard)
├── config.py                    # Configuration management
├── strategy.py                  # 6-stage withdrawal strategy engine
├── calculations.py              # Tax calculations
├── portfolio.py                 # Portfolio display and management
├── portfolio_rebalancing.py     # Rebalancing analysis
├── tax_harvesting.py            # Tax loss/gain harvesting
├── betr_roth_conversion.py      # BETR algorithm
├── load_data.py                 # Data loading utilities
├── ssibenefits.py               # Social Security calculations
├── monte_carlo.py               # Monte Carlo simulations
├── income_expense.py            # Income/expense projections
├── pages/                       # Multi-page application
│   ├── 1_estate_planning.py
│   ├── 2_configuration.py       # Configuration UI
│   ├── 3_dashboard.py           # Main dashboard
│   ├── 4_portfolio.py           # Portfolio management
│   ├── 5_strategy.py            # Strategy planning
│   ├── 6_monte_carlo.py         # Monte Carlo simulations
│   └── 8_advanced_strategies.py # Advanced tax strategies
├── components/                  # Shared UI components
│   ├── navbar.py                # Horizontal navigation
│   ├── sidebar.py               # Sidebar configuration
│   └── shared.py                # Shared utilities
└── data files/                  # CSV reference data
    ├── portfolio_data_truth.csv # Portfolio holdings (REQUIRED)
    ├── income_rates.csv         # Federal tax brackets
    ├── cap_gains.csv            # Capital gains brackets
    ├── irmaa.csv                # Medicare IRMAA brackets
    ├── atm.csv                  # Alternative Minimum Tax
    ├── rmd.csv                  # Required Minimum Distributions
    ├── standard.csv             # Standard deduction
    └── ssincome.csv             # Social Security income data
```

### Hybrid Architecture

The application uses a **hybrid multi-page architecture**:
- **Streamlit native pages** under `pages/` directory
- **Horizontal navigation** via `streamlit-option-menu` for better UX
- **Shared state** via `st.session_state` across pages
- **Background processing** for portfolio price fetching

---

## Core Features

### 1. Dashboard (📊)

**Purpose:** Financial at-a-glance landing page

**Key Metrics:**
- Net Worth with MoM, YTD, 12-month, and benchmark comparison
- Financial Plan Readiness Indicator (gauge + sub-indicators)
- Portfolio Tax Efficiency metrics
- Account mix and asset allocation visualizations

**Charts:**
- Net Worth bar chart
- Stacked account balance chart
- Asset mix pie chart
- Net Worth trend line chart
- Account mix treemap
- Portfolio mix treemap

**Data Requirements:**
- Minimum 2 months of portfolio data
- Historical net worth data

### 2. Portfolio Management (💼)

**Purpose:** Holdings, performance, tax harvesting, rebalancing, DAF bundling

**Sub-tabs:**
- **Map of Portfolio** — Treemap visualization + benchmark comparison
- **Details** — Full holdings table with gains/losses
- **Tax Harvesting** — Loss/gain opportunities with wash-sale replacements
- **Rebalancing** — Drift analysis + tax-efficient action plan
- **DAF Bundling** — Donor Advised Fund contribution analysis

**Features:**
- Live price fetching via Yahoo Finance
- Unrealized gain/loss tracking
- Cost basis management
- Tax lot identification
- Wash-sale rule compliance

### 3. Strategy Planning (📋)

**Purpose:** Multi-year withdrawal and accumulation strategy

**6 Life Stages:**
1. **Stage 1: Accumulation** (Pre-retirement, earning wages)
2. **Stage 2: Prep for Retirement** (2 years before retirement)
3. **Stage 3: Early Retirement** (Retired, before Medicare)
4. **Stage 4: Medicare** (Age 65-69, before Social Security)
5. **Stage 5: Social Security** (Age 70-72, before RMDs)
6. **Stage 6: RMD** (Age 73+, Required Minimum Distributions)

**Strategy Features:**
- Automatic stage detection based on age and retirement status
- Tax-optimized withdrawal sequencing
- Roth conversion recommendations
- ACA subsidy optimization (Stage 3)
- IRMAA avoidance (Medicare stages)
- RMD planning and QCD opportunities

### 4. Tax Optimization

**BETR Roth Conversion Algorithm:**
- Break-Even Tax Rate calculation
- Optimal conversion amount finder
- Multi-year conversion planning
- Nontaxable basis handling
- Backdoor Roth enablement

**Tax Harvesting:**
- Loss harvesting opportunities
- Gain harvesting in 0% LTCG bracket
- Wash-sale rule compliance
- Replacement ticker suggestions
- Net tax impact calculations

**Tax-Efficient Rebalancing:**
- Prioritizes tax-advantaged account trades
- Uses tax-loss harvesting for brokerage rebalancing
- Redirects contributions to under-weight assets
- Maintains brokerage cash cushion

### 5. Healthcare Cost Modeling

**ACA (Pre-Medicare):**
- Premium calculations
- Subsidy optimization (400% FPL threshold)
- MAGI management strategies

**Medicare (Age 65+):**
- Part B and Part D premiums
- IRMAA surcharge calculations (2-year lookback)
- Medigap policy costs
- Total healthcare cost projections

### 6. Social Security Optimization

**Features:**
- Benefit calculations at different claiming ages (62-70)
- Spousal benefit coordination
- Delayed claiming credits (8% per year)
- Survivor benefit planning
- Tax implications of benefits

### 7. Monte Carlo Simulations

**Purpose:** Probability-based retirement success analysis

**Features:**
- 10,000+ simulation runs
- Variable return scenarios
- Inflation modeling
- Longevity risk analysis
- Success probability calculations
- Percentile-based projections

### 8. Configuration System

**Purpose:** Centralized settings management

**Sections:**
- Personal Information (names, birth dates, retirement ages)
- Financial Assumptions (expenses, returns, inflation)
- Income (wages, contribution rates)
- Healthcare (ACA, Medicare)
- Social Security (claiming ages, benefit amounts)
- Tax Strategy (Roth conversion limits)
- Charitable Giving (DAF configuration)
- Portfolio Accounts (account definitions)

**Features:**
- JSON file persistence (`retirement_config.json`)
- Import/export functionality
- Backup and restore
- Validation and error checking

---

## Getting Started

### Prerequisites

```bash
# Python 3.9 or higher
python3 --version

# pip package manager
pip3 --version
```

### Installation

#### Option 1: Quick Start (Recommended)

```bash
# 1. Clone or download the repository
cd retirement_planning

# 2. Create virtual environment
python3 -m venv .venv

# 3. Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the application
streamlit run planning_app.py
```

#### Option 2: Using Run Scripts

**macOS/Linux:**
```bash
chmod +x run.sh
./run.sh
```

**Windows:**
```cmd
run.bat
```

### Initial Setup

1. **Launch Application** — Navigate to `http://localhost:8501`

2. **Configure Settings** — Go to ⚙️ Configuration page:
   - Enter personal information (names, birth dates, retirement ages)
   - Set financial assumptions (expenses, returns)
   - Configure healthcare settings
   - Enter Social Security estimates
   - Save configuration

3. **Add Portfolio Data** — Go to ⚙️ Configuration → Portfolio Data tab:
   - Define your accounts (e.g., "Schwab Roth", "Fidelity Traditional")
   - Enter holdings (minimum 2 months of data required)
   - Save portfolio data

4. **Review Dashboard** — Go to 📊 Dashboard:
   - Verify net worth calculations
   - Check portfolio allocation
   - Review financial readiness indicators

5. **Run Strategy Analysis** — Go to 📋 Strategy:
   - Review current life stage
   - Examine withdrawal/accumulation strategy
   - Check Roth conversion recommendations

---

## User Interface Guide

### Navigation

**Horizontal Menu Bar:**
```
🏠 Home | 📊 Dashboard | 💼 Portfolio | 📋 Strategy | 🎲 Monte Carlo |
🎯 Advanced | ⚙️ Configuration
```

**Sidebar:**
- Quick settings (temporary session overrides)
- Financial assumptions
- Healthcare settings
- Social Security inputs

### Page Descriptions

#### 🏠 Home (Estate Planning)
- Estate planning overview
- Beneficiary management
- Document checklist

#### 📊 Dashboard
- **Purpose:** Financial snapshot
- **Key Metrics:** Net worth, MoM/YTD/12-month changes
- **Charts:** Net worth trend, account mix, asset allocation
- **Refresh:** Automatic on page load

#### 💼 Portfolio
- **Map of Portfolio:** Treemap visualization
- **Details:** Full holdings table with gains/losses
- **Tax Harvesting:** Loss/gain opportunities
- **Rebalancing:** Drift analysis and action plan
- **DAF Bundling:** Charitable giving optimization

#### 📋 Strategy
- **Life Stage:** Current stage identification
- **Withdrawal Strategy:** Multi-year projection
- **Roth Conversions:** BETR-based recommendations
- **Tax Analysis:** Federal, state, IRMAA, NIIT
- **Cash Flow:** Income sources and expenses

#### 🎲 Monte Carlo
- **Simulations:** 10,000+ runs
- **Success Probability:** Retirement success rate
- **Percentile Analysis:** 10th, 50th, 90th percentiles
- **Sensitivity:** Variable return scenarios

#### 🎯 Advanced Strategies
- **BETR Analysis:** Detailed Roth conversion analysis
- **Tax Harvesting:** Advanced harvesting strategies
- **QCD Planning:** Qualified Charitable Distributions
- **Estate Planning:** Legacy optimization

#### ⚙️ Configuration
- **Personal Info:** Names, birth dates, retirement ages
- **Financial:** Expenses, returns, inflation
- **Income:** Wages, contribution rates
- **Healthcare:** ACA, Medicare settings
- **Social Security:** Claiming ages, benefit amounts
- **Tax Strategy:** Roth conversion limits
- **Charitable:** DAF configuration
- **Portfolio Data:** Account and holdings management
- **Advanced:** Save, reset, import/export

---

## Configuration System

### Configuration File Structure

**Location:** `retirement_config.json`

**Sections:**
1. `personal_info` — Names, birth dates, retirement ages, state
2. `income` — Wages, contribution rates, inflation
3. `financial_assumptions` — Expenses, returns, cash buffer
4. `healthcare` — ACA, Medicare settings
5. `social_security` — Claiming ages, benefit amounts
6. `tax_strategy` — Roth conversion limits
7. `charitable_giving` — DAF configuration
8. `metadata` — Last updated, version

### Key Configuration Fields

#### Personal Information
```json
{
  "person1_name": "Tom",
  "person1_birth_date": "1965-01-01",
  "person1_retirement_age": 62,
  "person1_retirement_year": 2026,
  "person2_name": "Sarah",
  "person2_birth_date": "1967-01-01",
  "person2_retirement_age": 62,
  "person2_retirement_year": 2028,
  "retirement_state": "FL"
}
```

#### Income (Accumulation Phase)
```json
{
  "person1_annual_wages": 120000,
  "person2_annual_wages": 80000,
  "wage_inflation_rate": 3.0,
  "contribution_401k_percent": 10.0,
  "contribution_roth_percent": 5.0,
  "contribution_brokerage_percent": 5.0
}
```

#### Financial Assumptions
```json
{
  "expected_annual_expenses": 50000,
  "expense_inflation_rate": 3.0,
  "expected_rate_of_return": 6.0,
  "years_of_expenses_in_cash": 4,
  "accumulation_cash_buffer_months": 6
}
```

#### Healthcare
```json
{
  "aca_insurance_monthly": 850,
  "aca_start_age": 62,
  "aca_end_age": 65,
  "medicare_start_age": 65,
  "aca_marketplace_enrolled": true
}
```

### Configuration API

```python
from config import get_config_manager

# Get configuration manager
config = get_config_manager()

# Get value
value = config.get("section", "key", default)

# Set value
config.set("section", "key", value)

# Save to file
config.save_config()

# Get person's age
age = config.get_person_age(1)  # Person 1 or 2

# Get annual wages for a year
wages = config.get_annual_wages(2028)

# Check if working in a year
working = config.has_wages_in_year(2028)
```

---

## Portfolio Management

### Portfolio Data File

**Location:** `portfolio_data_truth.csv`

**Required Columns:**
- `month` — Month number (1-12)
- `year` — Year (e.g., 2026)
- `account_name` — Account name (e.g., "Schwab")
- `account_type` — Cash, Brokerage, Traditional, Roth
- `symbol` — Ticker symbol or "MF:CASH"
- `name` — Security name
- `sector` — Sector classification
- `qty` — Quantity of shares
- `purchase_price` — Cost basis per share

**Example:**
```csv
month,year,account_name,account_type,symbol,name,sector,qty,purchase_price
2,2026,Schwab,Roth,VFIAX,Vanguard 500 Index,MF:Large-Cap Blend,1000,350.00
2,2026,Schwab,Roth,MF:CASH,Money Market,MF:Cash,25000,1.00
2,2026,Fidelity,Traditional,VBTLX,Vanguard Total Bond,Bond,2000,10.50
```

### Asset Classification

**Cash:**
- Symbol: `MF:CASH`
- Sector: Contains "cash" or "money market"

**Bonds:**
- Sector: Contains "bond", "fixed income", "treasury", "municipal", "muni"

**Stocks:**
- Everything else (equities, ETFs, mutual funds)

### Portfolio Features

#### Live Price Fetching
- Automatic price updates via Yahoo Finance
- Fallback to purchase price if fetch fails
- `MF:CASH` always priced at $1.00

#### Gain/Loss Tracking
- Unrealized gains/losses per holding
- Total portfolio gain/loss
- Percentage returns
- Cost basis management

#### Tax Lot Management
- Purchase price tracking
- Holding period calculation
- Long-term vs short-term classification

---

## Tax Optimization

### BETR Roth Conversion Algorithm

**Based on:** Vanguard Research "A 'BETR' approach to Roth conversions" (July 2025)

**Break-Even Tax Rate (BETR):** The future tax rate at which you would be indifferent between converting now or keeping funds in Traditional IRA.

**Decision Rule:**
- If **expected future rate > BETR** → Convert (beneficial)
- If **expected future rate ≤ BETR** → Don't convert

**Factors Considered:**
1. Tax payment source (taxable account vs IRA)
2. Nontaxable basis (after-tax contributions)
3. Future backdoor Roth opportunities
4. Time until withdrawal
5. Expected investment returns

**Usage:**
```python
from betr_roth_conversion import calculate_betr, BETRInputs

inputs = BETRInputs(
    current_marginal_rate=0.24,
    expected_future_rate=0.22,
    conversion_amount=50000,
    traditional_ira_balance=500000,
    pay_from_taxable=True,
    taxable_account_balance=200000,
    years_to_withdrawal=20,
    annual_return=0.07
)

results = calculate_betr(inputs)
print(f"BETR: {results.betr:.2%}")
print(f"Recommended: {results.conversion_recommended}")
```

### Tax Harvesting

**Loss Harvesting:**
- Identify positions with unrealized losses
- Harvest losses to offset gains or $3,000 ordinary income
- Suggest wash-sale-safe replacements
- Track 30-day wash-sale window

**Gain Harvesting:**
- Identify opportunities in 0% LTCG bracket
- Harvest gains tax-free
- Reset cost basis higher
- Reduce future tax liability

**Wash-Sale Rule Compliance:**
- Tracks 30-day before/after window
- Suggests substantially different replacements
- Maintains similar market exposure

**Example Replacements:**
```
VTI (Total Market) → ITOT (iShares Total Market)
VOO (S&P 500) → IVV (iShares S&P 500)
VEA (Developed Markets) → IEFA (iShares Developed Markets)
```

### Tax-Efficient Rebalancing

**Priority Order:**
1. **Rebalance inside tax-advantaged accounts** (no tax event)
2. **Tax-loss harvest in Brokerage** (book losses)
3. **Redirect contributions** (no selling required)
4. **Top up Brokerage cash cushion** (maintain liquidity)

**Account-Location Rules:**
- **Bonds** → Traditional IRA (ordinary income on withdrawal)
- **Stocks** → Roth IRA (tax-free growth) or Brokerage (LTCG rates)
- **Cash** → Brokerage (≥10% for liquidity)

**Drift Threshold:** 5% (configurable)

---

## Withdrawal Strategy

### 6-Stage Life-Cycle Strategy

#### Stage 1: Accumulation (Pre-Retirement)

**Applies:** Either person still working (earning wages)

**Strategy:**
- Contribute to 401k/IRA based on configuration percentages
- Build cash buffer (6 months of wages by default)
- Excess cash flows to brokerage
- No withdrawals or Roth conversions

**Cash Buffer Target:**
```
target = monthly_wages × accumulation_cash_buffer_months
```

**Contribution Flow:**
```
Gross Wages
  ├─ Traditional 401k (contribution_401k_percent)
  ├─ Roth 401k/IRA (contribution_roth_percent)
  ├─ Brokerage (contribution_brokerage_percent)
  └─ Take-home → Cash buffer → Excess to brokerage
```

#### Stage 2: Prep for Retirement (2 Years Before)

**Applies:** Within 2 years of earliest retirement year

**Strategy:**
- Ramp up cash buffer to 4 years of expenses
- Begin strategic Roth conversions
- Optimize tax position before retirement
- Prepare for ACA enrollment if applicable

**Cash Buffer Ramp-Up:**
```
Year -2: 2 years of expenses
Year -1: 3 years of expenses
Year 0:  4 years of expenses
```

#### Stage 3: Early Retirement (Pre-Medicare)

**Applies:** Retired, age < 65 (Medicare start age)

**Strategy:**
- Live on cash buffer (4 years of expenses)
- Replenish cash from taxable account
- Aggressive Roth conversions (low tax bracket)
- **ACA Subsidy Optimization:** Keep MAGI < 400% FPL if enrolled
- Avoid Traditional IRA withdrawals (preserve for later)

**ACA Subsidy Threshold (2026):**
```
400% FPL (couple) ≈ $75,000 MAGI
Strategy: Keep income below threshold to maximize premium tax credits
```

**Withdrawal Sequence:**
1. Cash buffer (no tax)
2. Taxable account (LTCG rates)
3. Roth conversions (fill low brackets)

#### Stage 4: Medicare (Age 65-69)

**Applies:** Age ≥ 65, before Social Security claiming

**Strategy:**
- Continue living on cash buffer
- Replenish from taxable account
- Moderate Roth conversions
- **IRMAA Avoidance:** Keep MAGI below IRMAA thresholds
- Medicare Part B/D premiums begin

**IRMAA Thresholds (2026):**
```
Single: $106,000 MAGI
Couple: $212,000 MAGI
Strategy: Stay below first IRMAA bracket to avoid surcharges
```

**Medicare Costs:**
- Part B: $174.70/month base (2026)
- Part D: ~$50/month average
- IRMAA: $0-$419.30/month per person (income-based)

#### Stage 5: Social Security (Age 70-72)

**Applies:** Social Security claimed, before RMD age

**Strategy:**
- Social Security income begins
- Reduce taxable account withdrawals
- Continue Roth conversions (moderate)
- Prepare for upcoming RMDs
- QCD planning if charitable

**Income Sources:**
1. Social Security (primary)
2. Cash buffer (supplement)
3. Taxable account (as needed)
4. Roth conversions (fill brackets)

#### Stage 6: RMD (Age 73+)

**Applies:** Age ≥ 73 (RMD age)

**Strategy:**
- Required Minimum Distributions from Traditional IRA
- Social Security income
- **QCD Opportunity:** Direct RMD to charity (up to $105,000/year)
- Minimize additional withdrawals
- Roth conversions (limited, if beneficial)

**RMD Calculation:**
```
RMD = Traditional_IRA_Balance / Distribution_Period
Distribution_Period = IRS Uniform Lifetime Table value for age
```

**QCD Benefits:**
- Satisfies RMD requirement
- Excluded from AGI (lowers MAGI)
- Avoids IRMAA surcharges
- Reduces future RMDs

### Withdrawal Sequencing

**General Priority:**
1. **Cash** — No tax impact
2. **Taxable (Brokerage)** — LTCG rates (0%, 15%, 20%)
3. **Traditional IRA** — Ordinary income rates
4. **Roth IRA** — Last resort (tax-free, preserve for heirs)

**Exception:** Roth conversions may pull from Traditional IRA strategically to fill low tax brackets.

---

## Advanced Features

### Monte Carlo Simulations

**Purpose:** Probability-based retirement success analysis

**Methodology:**
- 10,000+ simulation runs
- Variable annual returns (normal distribution)
- Inflation modeling
- Longevity risk (age 95 default)
- Withdrawal strategy execution

**Outputs:**
- Success probability (% of runs with positive balance at end)
- Percentile projections (10th, 50th, 90th)
- Year-by-year balance distributions
- Failure year analysis

### Donor Advised Fund (DAF) Planning

**Purpose:** Optimize charitable giving for tax efficiency

**Strategy:**
- Bunch contributions in high-income years
- Take itemized deduction in contribution year
- Distribute over multiple years
- Donate appreciated securities (avoid capital gains)

**DAF Contribution Limits:**
- **Cash:** 60% of AGI
- **Appreciated Securities:** 30% of AGI
- Excess carries forward 5 years

### Qualified Charitable Distributions (QCD)

**Purpose:** Tax-efficient charitable giving from IRA (age 70½+)

**Benefits:**
- Satisfies RMD requirement
- Excluded from AGI (lowers MAGI)
- Avoids IRMAA surcharges
- No itemization required

**Limits:**
- $105,000 per person per year (2026)
- Must be direct transfer to charity
- Only from Traditional IRA (not 401k)

**Strategy:**
```
Age 73: RMD = $40,000
Charitable goal = $15,000

Option 1 (Standard):
  - Take $40,000 RMD → AGI
  - Donate $15,000 → Itemized deduction (maybe)
  - Net AGI impact: $40,000 (or $25,000 if itemizing)

Option 2 (QCD):
  - QCD $15,000 directly to charity
  - Take remaining $25,000 RMD → AGI
  - Net AGI impact: $25,000 (guaranteed)
```

### Healthcare Cost Projections

**ACA (Pre-Medicare):**
```python
from strategy import calculate_aca_premium_for_year

premium = calculate_aca_premium_for_year(
    year=2026,
    age=62,
    monthly_premium=850,
    aca_start_age=62,
    aca_end_age=65
)
```

**Medicare + IRMAA:**
```python
from strategy import calculate_medicare_costs

costs = calculate_medicare_costs(
    year=2026,
    person1_age=67,
    person2_age=65,
    magi=180000,
    irmaa_df=irmaa_data
)

print(f"Part B: ${costs.part_b_annual:,.0f}")
print(f"Part D: ${costs.part_d_annual:,.0f}")
print(f"IRMAA: ${costs.irmaa_annual:,.0f}")
print(f"Total: ${costs.total_annual:,.0f}")
```

---

## Data Management

### Required Data Files

#### Portfolio Data (REQUIRED)
**File:** `portfolio_data_truth.csv`
**Minimum:** 2 months of data
**Backup:** Automatic timestamped backups on save

#### Tax Reference Files
- `income_rates.csv` — Federal income tax brackets
- `cap_gains.csv` — Capital gains tax brackets
- `irmaa.csv` — Medicare IRMAA brackets
- `atm.csv` — Alternative Minimum Tax
- `rmd.csv` — Required Minimum Distribution rates
- `standard.csv` — Standard deduction amounts

#### Social Security Files
- `ssincome.csv` — Social Security benefit calculations

### Data Validation

**Portfolio Data:**
- Required fields: month, year, account_name, account_type, symbol, name, sector, qty, purchase_price
- Valid account types: Cash, Brokerage, Traditional, Roth
- Valid sectors: See sector list in portfolio data entry
- Quantity > 0
- Purchase price > 0

**Configuration:**
- Birth dates in YYYY-MM-DD format
- Percentages sum to 100 where required
- Positive values for amounts
- Valid age ranges (18-100)

### Backup and Restore

**Automatic Backups:**
- Portfolio data: `portfolio_data_truth_YYYYMMDD_HHMMSS.csv`
- Configuration: Manual export to JSON

**Manual Backup:**
1. Go to ⚙️ Configuration → Advanced tab
2. Click "Export Configuration"
3. Save JSON file to safe location

**Restore:**
1. Go to ⚙️ Configuration → Advanced tab
2. Upload JSON file
3. Click "Import Configuration"
4. Refresh page

---

## API Reference

### Configuration API

```python
from config import get_config_manager, ConfigManager

# Get global instance
config = get_config_manager()

# Get value
value = config.get("section", "key", default)

# Set value
config.set("section", "key", value)

# Get section
section = config.get_section("section_name")

# Update section
config.update_section("section_name", {"key1": val1, "key2": val2})

# Save to file
success = config.save_config()

# Calculate age
age = config.calculate_age("1965-01-01")

# Get person age
age = config.get_person_age(1)  # 1 or 2

# Get annual wages
wages = config.get_annual_wages(2028)

# Check if working
working = config.has_wages_in_year(2028)
```

### Strategy API

```python
from strategy import WithdrawalStrategyEngine, PortfolioBalances

# Create engine
engine = WithdrawalStrategyEngine()

# Define balances
balances = PortfolioBalances(
    cash=55000,
    taxable=225000,
    traditional=670000,
    roth=168000,
    daf=0
)

# Calculate strategy
strategies = engine.calculate_multi_year_strategy(
    start_year=2026,
    num_years=30,
    initial_balances=balances,
    annual_expenses=50000
)

# Convert to DataFrame
df = engine._strategies_to_dataframe(strategies)
```

### BETR API

```python
from betr_roth_conversion import (
    calculate_betr,
    optimize_conversion_amount,
    BETRInputs
)

# Calculate BETR
inputs = BETRInputs(
    current_marginal_rate=0.24,
    expected_future_rate=0.22,
    conversion_amount=50000,
    traditional_ira_balance=500000
)
results = calculate_betr(inputs)

# Optimize conversion
optimal, results = optimize_conversion_amount(
    traditional_ira_balance=500000,
    current_agi=150000,
    target_tax_bracket=0.24,
    year=2026
)
```

### Tax Harvesting API

```python
from tax_harvesting import (
    build_harvesting_analysis,
    classify_harvest_opportunities,
    get_replacement_detail
)

# Analyze harvesting opportunities
analysis = build_harvesting_analysis(
    portfolio_df=portfolio,
    current_income=100000,
    year=2026
)

# Get replacement suggestions
replacement = get_replacement_detail("VTI")
print(f"Replace {replacement.original_ticker} with {replacement.replacement_ticker}")
```

### Rebalancing API

```python
from portfolio_rebalancing import (
    compute_rebalance_plan,
    build_rebalance_display_df,
    build_actions_display_df
)

# Compute rebalance plan
report = compute_rebalance_plan(
    month=2,
    year=2026,
    target_cash_pct=10.0,
    target_bonds_pct=10.0,
    target_stocks_pct=80.0,
    drift_threshold_pct=5.0
)

# Get display DataFrames
summary_df = build_rebalance_display_df(report)
actions_df = build_actions_display_df(report)
```

---

## Best Practices

### Portfolio Management

1. **Maintain 2+ months of data** — Required for application functionality
2. **Update monthly** — Add new month's data at month-end
3. **Verify prices** — Check live prices vs purchase prices
4. **Track cost basis** — Accurate purchase prices for tax calculations
5. **Classify sectors correctly** — Affects asset allocation and rebalancing

### Tax Optimization

1. **Annual Roth conversions** — Fill low tax brackets each year
2. **Harvest losses regularly** — Offset gains and reduce taxes
3. **Avoid wash sales** — Wait 31 days or use replacement tickers
4. **Pay conversion tax from taxable** — Maximizes tax-advantaged space
5. **Monitor IRMAA thresholds** — 2-year lookback for Medicare surcharges

### Withdrawal Strategy

1. **Build cash buffer early** — 4 years of expenses before retirement
2. **Optimize ACA subsidies** — Keep MAGI < 400% FPL if enrolled
3. **Delay Social Security** — 8% annual increase until age 70
4. **Plan for RMDs** — Start Roth conversions early to reduce future RMDs
5. **Use QCDs** — Tax-efficient charitable giving after age 70½

### Configuration

1. **Backup regularly** — Export configuration monthly
2. **Version control** — Keep dated backups
3. **Validate inputs** — Check calculated values make sense
4. **Update annually** — Review and adjust assumptions
5. **Document changes** — Note why values were changed

### Data Management

1. **Consistent naming** — Use same account names across months
2. **Accurate sectors** — Critical for asset classification
3. **Complete data** — Fill all required fields
4. **Verify totals** — Cross-check with brokerage statements
5. **Archive old data** — Keep historical data for trend analysis

---

## Troubleshooting

### Common Issues

#### "Insufficient historical data"
**Cause:** Less than 2 months of portfolio data  
**Solution:** Add at least 2 months of data in Configuration → Portfolio Data

#### "No portfolio data found for current month"
**Cause:** Missing current month's data  
**Solution:** Add current month's data or application will use most recent available

#### "Target weights must sum to 100"
**Cause:** Rebalancing targets don't sum to 100%  
**Solution:** Adjust Cash/Bonds/Stocks percentages to sum to exactly 100

#### "Configuration not loading"
**Cause:** Corrupted or missing `retirement_config.json`  
**Solution:** Go to Configuration → Advanced → Reset to Defaults

#### "Live prices not loading"
**Cause:** Network issue or market closed  
**Solution:** Application uses purchase price as fallback; prices update when market opens

#### "Wash sale warning"
**Cause:** Selling and buying same/similar security within 30 days  
**Solution:** Use replacement ticker suggestions from Tax Harvesting tab

### Performance Issues

#### Slow portfolio loading
**Cause:** Fetching live prices for many securities  
**Solution:** Application caches prices; subsequent loads are faster

#### Dashboard not updating
**Cause:** Stale session state  
**Solution:** Refresh browser page (F5)

#### Charts not rendering
**Cause:** Browser compatibility or data issue  
**Solution:** Try different browser (Chrome recommended); check console for errors

### Data Issues

#### Holdings classified incorrectly
**Cause:** Sector field doesn't match classification rules  
**Solution:** Update sector in portfolio data:
- Bonds: Include "bond", "fixed income", "treasury", or "municipal"
- Cash: Use "MF:Cash" or include "cash"/"money market"
- Stocks: Any other sector

#### Net worth doesn't match brokerage
**Cause:** Missing holdings or incorrect quantities  
**Solution:** Verify all accounts and holdings are entered; check quantities

#### Tax calculations seem wrong
**Cause:** Incorrect AGI or missing deductions  
**Solution:** Verify income inputs; check standard deduction is applied

---

## Technical Details

### Dependencies

```
streamlit>=1.31.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
yfinance>=0.2.36
streamlit-option-menu>=0.3.6
streamlit-extras>=0.3.6
```

### Performance Characteristics

**Portfolio Loading:**
- Initial load: 5-15 seconds (live price fetching)
- Cached load: <1 second
- Background refresh: Automatic

**Strategy Calculation:**
- 30-year projection: <1 second
- 50-year projection: 1-2 seconds

**Monte Carlo:**
- 10,000 simulations: 5-10 seconds
- 100,000 simulations: 30-60 seconds

### Data Storage

**Configuration:** JSON file (`retirement_config.json`)  
**Portfolio:** CSV file (`portfolio_data_truth.csv`)  
**Session State:** In-memory (lost on page refresh)  
**Cache:** Streamlit cache (cleared on app restart)

### Security Considerations

⚠️ **Important:** This application stores financial data in plain text files on your local machine. For production use:
- Encrypt sensitive data files
- Use secure file permissions
- Don't commit data files to version control
- Consider database storage for multi-user scenarios

### Browser Compatibility

**Recommended:** Chrome, Firefox, Safari (latest versions)  
**Not Supported:** Internet Explorer

---

## Additional Resources

### Documentation Files

- [`README.md`](README.md) — Main application documentation
- [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) — Configuration system guide
- [`BETR_GUIDE.md`](BETR_GUIDE.md) — BETR algorithm guide
- [`PORTFOLIO_REBALANCING_GUIDE.md`](PORTFOLIO_REBALANCING_GUIDE.md) — Rebalancing guide
- [`SSI_CALCULATOR_GUIDE.md`](SSI_CALCULATOR_GUIDE.md) — Social Security calculator
- [`INCOME_EXPENSE_GUIDE.md`](INCOME_EXPENSE_GUIDE.md) — Income/expense projections
- [`STRATEGY_README.md`](STRATEGY_README.md) — Withdrawal strategy details
- [`TEST_VALIDATION_GUIDE.md`](TEST_VALIDATION_GUIDE.md) — Testing guide

### Government Resources

**IRS:**
- [Retirement Plans](https://www.irs.gov/retirement-plans)
- [Roth IRA Conversions](https://www.irs.gov/retirement-plans/roth-iras)
- [Required Minimum Distributions](https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-required-minimum-distributions-rmds)

**Social Security:**
- [Benefit Calculators](https://www.ssa.gov/benefits/retirement/estimator.html)
- [Retirement Age](https://www.ssa.gov/benefits/retirement/planner/agereduction.html)

**Medicare:**
- [Medicare.gov](https://www.medicare.gov)
- [IRMAA Information](https://www.medicare.gov/your-medicare-costs/part-b-costs)

### Research Papers

- Vanguard: "A 'BETR' approach to Roth conversions" (July 2025)
- Fidelity: "Tax-Loss Harvesting Strategies"
- Morningstar: "Asset Location Strategies"

---

## Support and Contributing

### Getting Help

1. **Check this guide** — Most questions answered here
2. **Review specific guides** — See Additional Resources section
3. **Enable debug logging** — `export LOG_LEVEL=DEBUG`
4. **Check console** — Browser developer console for errors

### Contributing

Contributions welcome! Areas of interest:
- Additional tax optimization strategies
- Enhanced visualizations
- Performance improvements
- Bug fixes
- Documentation improvements

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd retirement_planning

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run application
streamlit run planning_app.py
```

---

## Disclaimer

⚠️ **IMPORTANT LEGAL DISCLAIMER**

This application is provided for **educational and informational purposes only**. It is **NOT**:
- Financial advice
- Tax advice
- Investment advice
- Legal advice

**You should:**
- Consult with qualified financial, tax, and legal professionals before making any financial decisions
- Verify all calculations independently
- Understand the assumptions and limitations of the models
- Not rely solely on this tool for retirement planning decisions

**The developers:**
- Make no warranties about accuracy or completeness
- Are not liable for any financial losses or damages
- Do not guarantee fitness for any particular purpose
- Recommend professional financial planning services

**Tax laws and regulations:**
- Change frequently
- Vary by jurisdiction
- May not be reflected in this application
- Require professional interpretation

**Use at your own risk.**

---

## Version History

### Version 2.0 (February 2026)
- ✅ 6-stage life-cycle strategy
- ✅ BETR Roth conversion algorithm
- ✅ Tax-efficient rebalancing
- ✅ Portfolio tax harvesting
- ✅ Configuration system
- ✅ Multi-page architecture
- ✅ Healthcare cost modeling
- ✅ Monte Carlo simulations

### Version 1.0 (Initial Release)
- Basic withdrawal strategy
- Portfolio tracking
- Tax calculations
- Social Security integration

---

## License

MIT License — See LICENSE file for details

---

## Acknowledgments

**Built with:**
- Streamlit — Web framework
- Plotly — Visualizations
- yfinance — Market data
- pandas — Data analysis

**Research:**
- Vanguard BETR methodology
- IRS tax regulations
- Social Security Administration data
- Medicare cost structures

**Made with Bob** — AI-assisted development

---

**Last Updated:** March 2, 2026  
**Version:** 2.0  
**Maintainer:** Retirement Planning Team

---

*For questions, issues, or contributions, please refer to the repository documentation.*