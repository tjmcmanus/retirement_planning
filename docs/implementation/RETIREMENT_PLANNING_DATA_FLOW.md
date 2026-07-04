# 🔄 Retirement Planning Application - Data Flow Architecture

## Executive Summary

This document provides a comprehensive view of how data flows through the retirement planning application, from user input through calculations to final visualizations.

---

## 📊 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE LAYER                         │
│                         (Streamlit Pages)                            │
├─────────────────────────────────────────────────────────────────────┤
│  Estate    Config   Dashboard  Portfolio  Strategy  Monte   Advanced │
│ Planning                Hub                        Carlo   Strategies│
└────┬────────┬──────────┬─────────┬────────┬────────┬────────┬──────┘
     │        │          │         │        │        │        │
     └────────┴──────────┴─────────┴────────┴────────┴────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │   CONFIGURATION LAYER       │
                    │   (config.py)               │
                    └──────────────┬──────────────┘
                                   │
     ┌─────────────────────────────┼─────────────────────────────┐
     │                             │                             │
┌────▼─────┐              ┌───────▼────────┐           ┌───────▼────────┐
│   DATA   │              │  CALCULATION   │           │   PORTFOLIO    │
│  LOADER  │              │     ENGINE     │           │    MANAGER     │
│(load_data)│             │  (strategy.py) │           │ (portfolio.py) │
└────┬─────┘              └───────┬────────┘           └───────┬────────┘
     │                            │                            │
     │                            │                            │
┌────▼─────────────────────┐     │     ┌─────────────────────▼────────┐
│   EXTERNAL DATA FILES    │     │     │   PORTFOLIO DATA FILES       │
│  • income_rates.csv      │     │     │  • portfolio_YYYYMM.csv      │
│  • cap_gains.csv         │     │     │  • financial_account.csv     │
│  • standard.csv          │     │     │  • transactions.db           │
│  • irmaa.csv             │     │     └──────────────────────────────┘
│  • atm.csv               │     │
│  • rmd.csv               │     │
│  • ssi_schedule.csv      │     │
└──────────────────────────┘     │
                                 │
                    ┌────────────▼────────────┐
                    │   SPECIALIZED MODULES   │
                    ├─────────────────────────┤
                    │ • betr_roth_conversion  │
                    │ • calculations          │
                    │ • tax_harvesting        │
                    │ • portfolio_rebalancing │
                    │ • advanced_strategies   │
                    │ • beneficiary_optimization│
                    └─────────────────────────┘
```

---

## 🔄 Detailed Data Flow by Component

### 1. Configuration Flow

```
User Input (UI)
    │
    ├─→ Personal Info
    │   ├─ Names, birth dates
    │   ├─ Retirement ages/years
    │   └─ State of residence
    │
    ├─→ Financial Assumptions
    │   ├─ Expected expenses
    │   ├─ Rate of return
    │   └─ Cash buffer settings
    │
    ├─→ Income Settings
    │   ├─ Annual wages
    │   ├─ Contribution rates
    │   └─ Wage inflation
    │
    ├─→ Healthcare Settings
    │   ├─ ACA coverage
    │   ├─ Medicare timing
    │   └─ Premium costs
    │
    └─→ Social Security
        ├─ Claiming ages
        └─ Benefit amounts
            │
            ▼
    retirement_config.json
            │
            ▼
    ConfigManager (config.py)
            │
            ├─→ Validation
            ├─→ Default values
            └─→ API access methods
                │
                ▼
    Available to all modules
```

### 2. Portfolio Data Flow

```
Portfolio Data Sources
    │
    ├─→ Manual Entry (portfolio_data_entry.py)
    │   └─ CSV files: portfolio_YYYYMM.csv
    │
    ├─→ Brokerage Integration (SnapTrade)
    │   ├─ Real-time balances
    │   ├─ Transaction history
    │   └─ Cost basis tracking
    │
    └─→ Historical Data (financial_account.csv)
        │
        ▼
Portfolio Manager (portfolio.py)
        │
        ├─→ Data Loading
        │   ├─ Read CSV files
        │   ├─ Parse account types
        │   └─ Classify holdings
        │
        ├─→ Price Fetching (yfinance)
        │   ├─ Live market prices
        │   ├─ Historical data
        │   └─ Cache management
        │
        ├─→ Portfolio Analysis
        │   ├─ Asset allocation
        │   ├─ Account balances
        │   ├─ Gain/loss tracking
        │   └─ Performance metrics
        │
        └─→ Output: PortfolioBalances
            │
            ├─ Traditional IRA
            ├─ Roth IRA
            ├─ Brokerage (taxable)
            ├─ Cash
            └─ 401k accounts
                │
                ▼
    Used by Strategy Engine
```

### 3. Tax Data Flow

```
Tax Reference Files
    │
    ├─→ income_rates.csv
    │   └─ Federal tax brackets by year
    │
    ├─→ cap_gains.csv
    │   └─ Capital gains rates by year
    │
    ├─→ standard.csv
    │   └─ Standard deductions by year
    │
    ├─→ irmaa.csv
    │   └─ Medicare IRMAA thresholds
    │
    ├─→ atm.csv
    │   └─ Alternative Minimum Tax data
    │
    └─→ rmd.csv
        └─ Required Minimum Distribution tables
            │
            ▼
    Data Loader (load_data.py)
            │
            ├─→ Caching (@st.cache_data)
            ├─→ Year-based filtering
            └─→ Filing status filtering
                │
                ▼
    Tax Calculation Engine (calculations.py)
            │
            ├─→ Federal tax calculation
            ├─→ Capital gains calculation
            ├─→ IRMAA penalty calculation
            ├─→ AMT calculation
            └─→ RMD calculation
                │
                ▼
    Tax Results (TaxCalculation)
            │
            ├─ Total tax
            ├─ Effective rate
            ├─ Marginal rate
            └─ Tax breakdown
                │
                ▼
    Used by Strategy Engine
```

### 4. Strategy Calculation Flow

```
User Inputs + Portfolio Data + Tax Data
            │
            ▼
Strategy Engine (strategy.py)
            │
            ├─→ Stage Detection
            │   ├─ Stage 1: Accumulation
            │   ├─ Stage 2: Prep for Retirement
            │   ├─ Stage 3: Early Retirement
            │   ├─ Stage 4: Medicare
            │   ├─ Stage 5: Social Security
            │   ├─ Stage 6: RMD
            │   └─ Stage 7: Surviving Spouse
            │
            ├─→ Annual Calculations (per year)
            │   │
            │   ├─→ Income Calculation
            │   │   ├─ Wages (if working)
            │   │   ├─ Social Security
            │   │   ├─ RMDs
            │   │   └─ Investment income
            │   │
            │   ├─→ Expense Calculation
            │   │   ├─ Base expenses
            │   │   ├─ Healthcare costs
            │   │   ├─ Age adjustments
            │   │   └─ Inflation adjustments
            │   │
            │   ├─→ Cash Need Calculation
            │   │   └─ Expenses - Income
            │   │
            │   ├─→ Withdrawal Strategy
            │   │   ├─ Cash buffer check
            │   │   ├─ Brokerage buffer check
            │   │   ├─ Account sequencing
            │   │   └─ Tax optimization
            │   │
            │   ├─→ Roth Conversion Optimization
            │   │   ├─ BETR calculation
            │   │   ├─ Tax bracket analysis
            │   │   ├─ Conversion amount
            │   │   └─ Tax payment source
            │   │
            │   ├─→ Tax Calculation
            │   │   ├─ AGI calculation
            │   │   ├─ Federal tax
            │   │   ├─ State tax
            │   │   ├─ IRMAA penalties
            │   │   └─ Capital gains
            │   │
            │   ├─→ Portfolio Growth
            │   │   ├─ Apply returns
            │   │   ├─ Rebalancing
            │   │   └─ Cost basis tracking
            │   │
            │   └─→ Decision Logging
            │       ├─ Withdrawal decisions
            │       ├─ Conversion decisions
            │       ├─ Tax decisions
            │       └─ Rebalancing decisions
            │
            └─→ Output: YearlyStrategy DataFrame
                │
                ├─ Year-by-year projections
                ├─ Account balances
                ├─ Tax calculations
                ├─ Cash flows
                └─ Decision logs
                    │
                    ▼
    Visualization & Analysis
```

### 5. Advanced Strategy Flow

```
Strategy Results
    │
    ├─→ BETR Roth Conversion (betr_roth_conversion.py)
    │   ├─ Input: Current tax rate, future rate, years
    │   ├─ Calculate: Break-even tax rate
    │   ├─ Optimize: Conversion amount
    │   └─ Output: Conversion recommendations
    │
    ├─→ Tax Harvesting (tax_harvesting.py)
    │   ├─ Input: Portfolio holdings, tax situation
    │   ├─ Analyze: Gain/loss opportunities
    │   ├─ Check: Wash sale rules
    │   └─ Output: Harvesting recommendations
    │
    ├─→ Portfolio Rebalancing (portfolio_rebalancing.py)
    │   ├─ Input: Current allocation, target allocation
    │   ├─ Calculate: Drift from targets
    │   ├─ Optimize: Tax-efficient trades
    │   └─ Output: Rebalancing plan
    │
    ├─→ Beneficiary Optimization (beneficiary_optimization.py)
    │   ├─ Input: Estate size, beneficiaries
    │   ├─ Calculate: Inherited IRA strategies
    │   ├─ Compare: Spousal vs non-spousal options
    │   └─ Output: Beneficiary recommendations
    │
    └─→ Charitable Giving (advanced_strategies.py)
        ├─ Input: Income, charitable goals
        ├─ Calculate: QCD benefits, DAF strategies
        ├─ Optimize: Timing and amounts
        └─ Output: Giving recommendations
            │
            ▼
    Dashboard Visualizations
```

### 6. Monte Carlo Simulation Flow

```
Strategy Configuration
    │
    ├─→ Base Case Scenario
    ├─→ Market Assumptions
    │   ├─ Expected return
    │   ├─ Standard deviation
    │   └─ Correlation matrix
    │
    └─→ Simulation Parameters
        ├─ Number of runs (1000+)
        ├─ Years to simulate
        └─ Random seed
            │
            ▼
Monte Carlo Engine (monte_carlo.py)
            │
            ├─→ For each simulation run:
            │   │
            │   ├─→ Generate random returns
            │   │   └─ Based on normal distribution
            │   │
            │   ├─→ Run strategy calculation
            │   │   └─ With randomized returns
            │   │
            │   └─→ Record outcomes
            │       ├─ Final portfolio value
            │       ├─ Success/failure
            │       └─ Year of depletion (if any)
            │
            └─→ Aggregate Results
                │
                ├─ Success rate
                ├─ Percentile outcomes (10th, 50th, 90th)
                ├─ Distribution charts
                └─ Risk metrics
                    │
                    ▼
    Monte Carlo Dashboard
```

---

## 📁 Key Data Files

### Input Files (User Provides)

| File | Purpose | Format |
|------|---------|--------|
| `retirement_config.json` | User configuration | JSON |
| `portfolio_YYYYMM.csv` | Monthly portfolio snapshots | CSV |
| `financial_account.csv` | Account definitions | CSV |

### Reference Files (System Provides)

| File | Purpose | Updates |
|------|---------|---------|
| `income_rates.csv` | Federal tax brackets | Annually |
| `cap_gains.csv` | Capital gains rates | Annually |
| `standard.csv` | Standard deductions | Annually |
| `irmaa.csv` | Medicare IRMAA thresholds | Annually |
| `atm.csv` | AMT calculations | Annually |
| `rmd.csv` | RMD life expectancy tables | Rarely |
| `ssi_schedule.csv` | Social Security schedules | As needed |

### Generated Files (System Creates)

| File | Purpose | Location |
|------|---------|----------|
| `transactions.db` | Transaction history | `data/` |
| `credentials.db` | Encrypted credentials | `data/` |
| `factor_cache.db` | Portfolio factor data | `data/` |
| `sync_state.json` | Brokerage sync state | `data/` |

---

## 🔄 Page-Specific Data Flows

### Estate Planning Page (1_estate_planning.py)

```
User Input
    │
    ├─→ Estate Size
    ├─→ Beneficiaries
    ├─→ Charitable Goals
    │
    ▼
Estate Tax Calculator
    │
    ├─→ Federal estate tax
    ├─→ State estate tax
    ├─→ TCJA sunset analysis
    │
    ▼
Beneficiary Optimizer
    │
    ├─→ Inherited IRA strategies
    ├─→ Spousal options
    ├─→ Trust strategies
    │
    ▼
Charitable Optimizer
    │
    ├─→ QCD strategies
    ├─→ DAF strategies
    ├─→ Tax benefits
    │
    ▼
Estate Plan Recommendations
```

### Configuration Page (2_configuration.py)

```
User Interface Tabs
    │
    ├─→ Personal Info Tab
    │   └─→ Save to config.json
    │
    ├─→ Financial Assumptions Tab
    │   └─→ Save to config.json
    │
    ├─→ Healthcare Tab
    │   └─→ Save to config.json
    │
    ├─→ Social Security Tab
    │   └─→ Save to config.json
    │
    ├─→ Tax Strategy Tab
    │   └─→ Save to config.json
    │
    └─→ Portfolio Data Tab
        └─→ Upload/Edit portfolio files
            │
            ▼
    Configuration Validation
            │
            ▼
    Reload Application State
```

### Dashboard Page (3_dashboard.py)

```
Load Configuration + Portfolio Data
    │
    ├─→ Net Worth Summary
    │   ├─ Total assets
    │   ├─ Account breakdown
    │   └─ Historical trends
    │
    ├─→ Retirement Readiness
    │   ├─ Years to retirement
    │   ├─ Savings rate
    │   └─ Projected income
    │
    ├─→ Tax Situation
    │   ├─ Current year projection
    │   ├─ Marginal rate
    │   └─ Optimization opportunities
    │
    ├─→ Market Stress Indicator
    │   ├─ Current market conditions
    │   ├─ Bucket strategy status
    │   └─ Rebalancing recommendations
    │
    └─→ Quick Actions
        ├─ Run strategy
        ├─ Update portfolio
        └─ View reports
            │
            ▼
    Interactive Visualizations
```

### Portfolio Hub Page (4_portfolio_hub.py)

```
Portfolio Data + Market Data
    │
    ├─→ Overview Tab
    │   ├─ Asset allocation
    │   ├─ Account balances
    │   └─ Performance summary
    │
    ├─→ Holdings Tab
    │   ├─ Security list
    │   ├─ Cost basis
    │   └─ Gain/loss
    │
    ├─→ Performance Tab
    │   ├─ Time-weighted returns
    │   ├─ Benchmark comparison
    │   └─ Factor analysis
    │
    ├─→ Optimization Tab
    │   ├─ Rebalancing needs
    │   ├─ Tax harvesting
    │   └─ Trade recommendations
    │
    └─→ Connections Tab
        ├─ Brokerage sync
        ├─ Transaction import
        └─ Real-time updates
            │
            ▼
    Portfolio Management Actions
```

### Strategy Page (5_strategy.py)

```
Configuration + Portfolio + Tax Data
    │
    ▼
Strategy Engine Execution
    │
    ├─→ Year-by-year calculations
    ├─→ Stage transitions
    ├─→ Tax optimizations
    └─→ Decision logging
        │
        ▼
Results DataFrame
    │
    ├─→ Summary Metrics
    │   ├─ Total taxes paid
    │   ├─ Roth conversions
    │   ├─ Final balances
    │   └─ Success indicators
    │
    ├─→ Detailed Tables
    │   ├─ Annual projections
    │   ├─ Account balances
    │   ├─ Tax breakdown
    │   └─ Cash flows
    │
    ├─→ Visualizations
    │   ├─ Balance charts
    │   ├─ Tax charts
    │   ├─ Withdrawal charts
    │   └─ Conversion charts
    │
    └─→ Decision Logs
        ├─ Withdrawal decisions
        ├─ Conversion decisions
        └─ Rebalancing decisions
            │
            ▼
    Export Options (CSV, PDF)
```

### Monte Carlo Page (6_monte_carlo.py)

```
Strategy Configuration
    │
    ├─→ Simulation Parameters
    │   ├─ Number of runs
    │   ├─ Return assumptions
    │   └─ Volatility assumptions
    │
    ▼
Run Simulations (parallel)
    │
    ├─→ Progress tracking
    ├─→ Result aggregation
    └─→ Statistical analysis
        │
        ▼
Results Visualization
    │
    ├─→ Success Rate
    ├─→ Percentile Charts
    ├─→ Distribution Plots
    └─→ Risk Metrics
        │
        ▼
    Scenario Comparison
```

---

## 🔐 Security & Data Protection

### Sensitive Data Handling

```
User Credentials
    │
    ├─→ Encryption (credential_manager.py)
    │   ├─ Fernet symmetric encryption
    │   ├─ Key derivation from password
    │   └─ Secure storage in credentials.db
    │
    └─→ Access Control
        ├─ Session-based authentication
        ├─ Automatic timeout
        └─ No plaintext storage
```

### Data Privacy

```
Personal Financial Data
    │
    ├─→ Local Storage Only
    │   ├─ No cloud uploads
    │   ├─ User-controlled backups
    │   └─ .gitignore protection
    │
    └─→ API Integrations
        ├─ OAuth 2.0 for brokerages
        ├─ Encrypted credentials
        └─ Minimal data retention
```

---

## 🔄 Real-Time Data Synchronization

### Brokerage Integration Flow

```
User Initiates Sync
    │
    ├─→ Credential Manager
    │   └─→ Retrieve encrypted credentials
    │
    ├─→ SnapTrade Connector
    │   ├─→ OAuth authentication
    │   ├─→ Fetch account data
    │   ├─→ Fetch transactions
    │   └─→ Fetch holdings
    │
    ├─→ Data Transformer
    │   ├─→ Normalize account types
    │   ├─→ Parse transactions
    │   ├─→ Calculate cost basis
    │   └─→ Update portfolio data
    │
    ├─→ Sync State Manager
    │   ├─→ Track last sync time
    │   ├─→ Detect changes
    │   └─→ Update sync_state.json
    │
    └─→ Portfolio Manager
        └─→ Merge with existing data
            │
            ▼
    Updated Portfolio Display
```

---

## 📊 Performance Optimization

### Caching Strategy

```
Data Loading
    │
    ├─→ Streamlit Cache (@st.cache_data)
    │   ├─ Tax reference files
    │   ├─ Portfolio data
    │   └─ Market prices
    │
    ├─→ Database Cache
    │   ├─ Factor data (factor_cache.db)
    │   ├─ Transaction history
    │   └─ Sync state
    │
    └─→ Memory Cache
        ├─ Configuration
        ├─ Session state
        └─ Calculation results
```

---

## 🎯 Key Takeaways

1. **Modular Architecture**: Clear separation between data, calculation, and presentation layers
2. **Configuration-Driven**: All user preferences stored in JSON for easy backup/restore
3. **Tax-Optimized**: Multiple tax calculation engines working together
4. **Real-Time Integration**: Optional brokerage connections for live data
5. **Security-First**: Encrypted credentials, local storage, no cloud dependencies
6. **Performance-Optimized**: Multi-level caching for fast response times
7. **Extensible**: Easy to add new strategies, pages, or data sources

---

## 📚 Related Documentation

- [README.md](README.md) - Main application documentation
- [../user/CONFIG_GUIDE.md](../user/CONFIG_GUIDE.md) - Configuration system details
- [../user/STRATEGY_README.md](../user/STRATEGY_README.md) - Strategy engine documentation
- [BROKERAGE_INTEGRATION_ROADMAP.md](BROKERAGE_INTEGRATION_ROADMAP.md) - Integration details
- [../user/BUCKET_STRATEGY_GUIDE.md](../user/BUCKET_STRATEGY_GUIDE.md) - Bucket strategy documentation

---

*Generated by Bob - Your AI Software Engineer Assistant*