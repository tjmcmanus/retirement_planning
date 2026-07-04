# Direct Indexing User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [What is Direct Indexing?](#what-is-direct-indexing)
3. [Setup Instructions](#setup-instructions)
4. [Getting Started](#getting-started)
5. [Using the Dashboard](#using-the-dashboard)
6. [Tax Loss Harvesting Workflow](#tax-loss-harvesting-workflow)
7. [Configuration](#configuration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [FAQ](#faq)

---

## Introduction

Welcome to the Direct Indexing module for your retirement planning application! This guide will help you set up and use the tax loss harvesting features to optimize your after-tax returns.

### What You'll Learn
- How to set up your direct index portfolio
- How to identify tax loss harvesting opportunities
- How to execute harvest trades safely
- How to track your tax savings

---

## What is Direct Indexing?

### Overview
Direct indexing is an investment strategy where you own individual stocks that replicate an index (in this case, the S&P 500 Equal Weight ETF - RSP) instead of owning the ETF itself.

### Benefits
1. **Tax Loss Harvesting**: Sell losing positions to offset capital gains
2. **Customization**: Exclude specific stocks or sectors
3. **Tax Efficiency**: Potentially save thousands in taxes annually
4. **No ETF Fees**: Own stocks directly without ETF expense ratios

### How It Works
```
Traditional ETF Investing:
You → Buy RSP ETF → Own ~500 stocks indirectly

Direct Indexing:
You → Buy 500 individual stocks → Own stocks directly
     ↓
     Can harvest losses on individual positions
     Replace with similar stocks to maintain exposure
```

### The RSP ETF
- **Name**: Invesco S&P 500 Equal Weight ETF
- **Ticker**: RSP
- **Strategy**: Equal weight (~0.2% per stock)
- **Holdings**: ~500 S&P 500 constituents
- **Rebalancing**: Quarterly

---

## Setup Instructions

### Prerequisites
1. Python 3.10 or higher
2. Existing retirement planning application installed
3. Brokerage account (Schwab recommended for API integration)

### Installation

#### Step 1: Install Dependencies
```bash
# Navigate to your retirement planning directory
cd /path/to/retirement_planning

# Install required packages (if not already installed)
pip install -r requirements.txt
```

#### Step 2: Initialize Database
```bash
# Run the migration script
python migrate_add_direct_indexing.py
```

This creates the necessary database tables:
- `rsp_holdings` - S&P 500 constituent data
- `direct_index_positions` - Your tax lots
- `harvest_history` - Completed harvests
- `replacement_mappings` - Stock replacement rules
- `trade_instructions` - Trade execution tracking
- `harvest_executions` - Harvest plans
- `execution_audit_log` - Audit trail
- `tax_savings_records` - Tax impact tracking

#### Step 3: Fetch RSP Holdings
```bash
# Fetch current RSP constituents from Yahoo Finance
python -c "from components.rsp_holdings_fetcher import fetch_rsp_holdings; fetch_rsp_holdings(force_refresh=True)"
```

This downloads:
- All ~500 S&P 500 stocks
- Current prices
- Sector classifications
- Market capitalizations

#### Step 4: Configure Settings
Edit `config/direct_indexing_config.yaml`:

```yaml
thresholds:
  loss_threshold_pct: 10.0        # Minimum loss % to harvest
  min_loss_amount: 500.0          # Minimum dollar loss
  gains_threshold_pct: 15.0       # Gains threshold (future use)

replacement:
  strategy: sector_based          # Replacement strategy
  prefer_larger_cap: true         # Prefer larger companies
  min_market_cap: 1000000000      # $1B minimum
  max_alternatives: 5             # Number of alternatives

wash_sale:
  lookback_days: 30               # Days to look back
  lookforward_days: 30            # Days to look forward
  check_enabled: true             # Enable wash sale checking

execution:
  require_approval: true          # Require manual approval
  default_lot_method: HIFO        # Default lot selection
  allow_fractional_shares: true   # Allow fractional shares

tax:
  default_ltcg_rate: 0.15         # Long-term capital gains rate
  default_marginal_rate: 0.24     # Marginal tax rate
```

#### Step 5: Verify Installation
```bash
# Run tests to verify everything works
pytest test_direct_indexing.py -v
```

---

## Getting Started

### Option A: Automated Initial Setup

If you're starting fresh, use the automated portfolio generator:

```python
from components.initial_portfolio_generator import generate_initial_portfolio, export_to_csv

# Generate purchase list for $500,000 investment
purchases, summary = generate_initial_portfolio(
    total_investment=500000.0,
    min_trade_size=100.0,
    allow_fractional=True
)

# Export to CSV for execution at your broker
csv_path = export_to_csv(purchases, "data/initial_purchases.csv")

print(f"Generated {len(purchases)} purchase orders")
print(f"Total investment: ${summary['total_investment']:,.2f}")
print(f"Exported to: {csv_path}")
```

**Output Example:**
```
Generated 503 purchase orders
Total investment: $500,000.00
Exported to: data/initial_purchases.csv
```

The CSV file contains:
```csv
symbol,shares,price,value,sector
AAPL,6.67,150.00,1000.50,Information Technology
MSFT,2.86,350.00,1001.00,Information Technology
...
```

**Next Steps:**
1. Review the CSV file
2. Execute trades at your broker
3. Import executed positions (see Option B)

### Option B: Import Existing Positions

If you already own stocks, import them:

#### From CSV File

Create a CSV file with your positions:
```csv
symbol,shares,price,date
AAPL,100,180.00,2025-01-15
MSFT,50,300.00,2025-01-15
GOOGL,75,140.00,2025-01-20
```

Import:
```python
from components.direct_index_manager import import_from_csv

imported, errors = import_from_csv(
    csv_path="my_positions.csv",
    account_name="Schwab Brokerage",
    account_type="Brokerage"
)

print(f"Imported {imported} positions")
if errors:
    print(f"Errors: {errors}")
```

#### From Schwab API

```python
from components.direct_index_manager import import_from_schwab
from components.schwab_connector import SchwabConnector

# Initialize Schwab connector
connector = SchwabConnector(
    client_id="your_client_id",
    client_secret="your_client_secret"
)

# Import positions
imported, errors = import_from_schwab(
    account_id="12345678",
    account_name="Schwab Brokerage",
    schwab_connector=connector
)

print(f"Imported {imported} positions from Schwab")
```

---

## Using the Dashboard

### Accessing the Dashboard

1. Start the Streamlit app:
```bash
streamlit run planning_app.py
```

2. Navigate to **Direct Indexing** in the sidebar

### Dashboard Overview

The dashboard has 4 main tabs:

#### Tab 1: Portfolio Overview

**Purpose**: View your current direct index positions

**Features**:
- Total positions, value, cost basis, unrealized G/L
- Breakdown by account and sector
- Sector allocation pie chart
- Detailed position table with filters
- Export to CSV

**Key Metrics**:
- **Total Positions**: Number of individual stocks
- **Total Value**: Current market value
- **Cost Basis**: Total amount invested
- **Unrealized G/L**: Current gains/losses

**Filters**:
- Show losses only
- Minimum loss percentage
- Account selection

**Actions**:
- 🔄 Refresh Prices - Update current prices
- 📥 Export to CSV - Download position data

#### Tab 2: Harvest Opportunities

**Purpose**: Identify and create tax loss harvesting opportunities

**Features**:
- Scan for positions with losses
- Priority scoring (1-5 stars)
- Replacement stock recommendations
- Wash sale warnings
- Create execution plans

**Opportunity Details**:
- Position information (shares, prices, loss %)
- Tax impact (estimated savings, tax rate)
- Replacement recommendations (primary + alternatives)
- Wash sale risk assessment

**Priority Scoring**:
- ⭐⭐⭐⭐⭐ (5 stars): Excellent opportunity
- ⭐⭐⭐⭐ (4 stars): Good opportunity
- ⭐⭐⭐ (3 stars): Moderate opportunity
- ⭐⭐ (2 stars): Low priority
- ⭐ (1 star): Minimal benefit

**Actions**:
- 🔍 Scan for Opportunities - Find harvest candidates
- Create Execution Plan - Generate trade instructions

#### Tab 3: Execution Queue

**Purpose**: Review and approve pending harvest executions

**Features**:
- View pending executions
- Approve or cancel trades
- Export trade instructions
- Track execution status

**Execution Details**:
- Sell trade (symbol, shares, estimated price/value)
- Buy trade (replacement symbol, shares, estimated price/value)
- Tax savings estimate

**Actions**:
- ✅ Approve - Approve for execution
- ❌ Cancel - Cancel execution
- 📥 Export Trade Instructions - Download CSV for broker

#### Tab 4: Tax Savings

**Purpose**: Track tax savings and performance

**Features**:
- Year-to-date summary
- Breakdown by term (short/long)
- Breakdown by account
- Performance metrics
- Harvest history table

**Key Metrics**:
- Total Harvests - Number of completed harvests
- Realized Losses - Total losses harvested
- Est. Tax Savings - Estimated tax savings
- Actual Savings - Actual savings (after filing)

**Performance Metrics**:
- Average loss per harvest
- Average savings per harvest
- Short-term vs long-term percentage
- Estimate accuracy

---

## Tax Loss Harvesting Workflow

### Complete Workflow Example

#### Step 1: Scan for Opportunities

1. Go to **Tab 2: Harvest Opportunities**
2. Set your current AGI in the sidebar
3. Click **🔍 Scan for Opportunities**

The system will:
- Analyze all positions
- Identify losses > 10%
- Calculate tax savings
- Find replacement stocks
- Check for wash sale risks
- Assign priority scores

#### Step 2: Review Opportunities

For each opportunity, review:
- **Loss Details**: How much you're down
- **Tax Impact**: Estimated savings
- **Replacement**: Recommended alternative stock
- **Wash Sale Risk**: Any concerns

**Example Opportunity**:
```
⭐⭐⭐⭐⭐ AAPL - $3,000 loss (16.7%)

Position Details:
- Shares: 100
- Purchase Price: $180.00
- Current Price: $150.00
- Unrealized Loss: $3,000
- Holding Period: 400 days (Long-term)

Tax Impact:
- Estimated Savings: $450.00
- Tax Rate: 15% (LTCG)

Replacement:
- Recommended: MSFT
- Sector: Information Technology
- Price: $350.00
- Alternatives: GOOGL, NVDA, ORCL
```

#### Step 3: Create Execution Plan

1. Click **Create Execution Plan** for your chosen opportunity
2. System generates:
   - Sell order for AAPL (100 shares @ $150)
   - Buy order for MSFT (~42.86 shares @ $350)
   - Execution ID for tracking

#### Step 4: Review and Approve

1. Go to **Tab 3: Execution Queue**
2. Review the execution details
3. Click **✅ Approve** to proceed
4. Click **📥 Export Trade Instructions** to get CSV

**Trade Instructions CSV**:
```csv
trade_type,symbol,shares,estimated_price,estimated_value,account_name,notes,status
SELL,AAPL,100.00,150.00,15000.00,Schwab Brokerage,Tax loss harvest: 16.7% loss,approved
BUY,MSFT,42.86,350.00,15001.00,Schwab Brokerage,Replacement for AAPL,approved
```

#### Step 5: Execute at Broker

**Manual Execution** (Recommended):
1. Log into your brokerage account
2. Place sell order for AAPL (100 shares, market order)
3. Wait for fill
4. Place buy order for MSFT (~42.86 shares, market order)
5. Note actual execution prices

**Why Manual?**:
- Full control over execution
- Better price discovery
- No automated trading risks
- Compliance with broker policies

#### Step 6: Record Execution

After trades execute, record the actual prices:

```python
from components.harvest_executor import execute_sell_trade, execute_buy_trade, complete_execution

# Record sell execution
dispositions = execute_sell_trade(
    trade_id="sell_trade_id",
    executed_price=150.25,  # Actual fill price
    executed_shares=100.0,
    execution_notes="Executed via Schwab"
)

# Record buy execution
new_lot = execute_buy_trade(
    trade_id="buy_trade_id",
    executed_price=349.75,  # Actual fill price
    executed_shares=42.90,  # Actual shares bought
    execution_notes="Executed via Schwab"
)

# Mark as complete
complete_execution("execution_id")
```

#### Step 7: Verify Tax Savings

1. Go to **Tab 4: Tax Savings**
2. View updated YTD summary
3. Check harvest history

**YTD Summary Example**:
```
Tax Year: 2026
Total Harvests: 1
Realized Losses: $3,000
Est. Tax Savings: $450
```

---

## Configuration

### Threshold Settings

Control when harvests are triggered:

```yaml
thresholds:
  loss_threshold_pct: 10.0        # Minimum 10% loss
  min_loss_amount: 500.0          # Minimum $500 loss
  gains_threshold_pct: 15.0       # Future: gains harvesting
```

**Recommendations**:
- **Conservative**: 15% loss threshold
- **Moderate**: 10% loss threshold (default)
- **Aggressive**: 5% loss threshold

### Replacement Strategy

Control how replacement stocks are selected:

```yaml
replacement:
  strategy: sector_based          # Match by sector
  prefer_larger_cap: true         # Prefer larger companies
  min_market_cap: 1000000000      # $1B minimum
  max_alternatives: 5             # Show 5 alternatives
```

**Strategies**:
- **sector_based**: Match stocks in same GICS sector (recommended)
- **correlation_based**: Match by price correlation (future)

### Wash Sale Settings

Control wash sale checking:

```yaml
wash_sale:
  lookback_days: 30               # IRS: 30 days before
  lookforward_days: 30            # IRS: 30 days after
  check_enabled: true             # Always keep enabled
```

**Important**: Never disable wash sale checking unless you have a specific reason and understand the tax implications.

### Execution Settings

Control trade execution:

```yaml
execution:
  require_approval: true          # Require manual approval
  default_lot_method: HIFO        # Maximize losses
  allow_fractional_shares: true   # Allow fractional shares
```

**Lot Selection Methods**:
- **HIFO** (Highest In, First Out): Maximize losses (recommended for harvesting)
- **FIFO** (First In, First Out): IRS default
- **LIFO** (Last In, First Out): Minimize gains
- **LOFO** (Lowest In, First Out): Maximize gains
- **SpecID** (Specific Identification): Choose specific lots

### Tax Settings

Set your tax rates:

```yaml
tax:
  default_ltcg_rate: 0.15         # 15% LTCG rate
  default_marginal_rate: 0.24     # 24% marginal rate
```

**2026 Tax Rates**:

**Long-Term Capital Gains** (held > 365 days):
- 0% if AGI < $44,625 (single) or $89,250 (married)
- 15% if AGI < $492,300 (single) or $553,850 (married)
- 20% if AGI > above thresholds

**Short-Term Capital Gains** (held ≤ 365 days):
- Taxed as ordinary income at your marginal rate

---

## Best Practices

### 1. Harvest Regularly

**Frequency**: Monthly or quarterly
**Why**: Capture losses before they recover
**How**: Set a calendar reminder to scan for opportunities

### 2. Prioritize Long-Term Losses

**Why**: Long-term losses offset long-term gains (taxed at lower rates)
**How**: Use the priority scoring system (5-star opportunities first)

### 3. Maintain Sector Exposure

**Why**: Avoid changing your overall portfolio allocation
**How**: Always use sector-based replacement stocks

### 4. Avoid Wash Sales

**Why**: IRS disallows the loss deduction
**How**: 
- Never buy the same stock within 30 days before/after selling
- Use the system's wash sale checker
- Choose different replacement stocks

### 5. Track Everything

**Why**: Tax reporting and audit trail
**How**:
- Use the execution queue
- Export trade instructions
- Keep broker confirmations
- Review tax savings tab regularly

### 6. Consider Transaction Costs

**Why**: Commissions can eat into tax savings
**How**:
- Use commission-free brokers (Schwab, Fidelity, etc.)
- Ensure tax savings > transaction costs
- Batch smaller positions if needed

### 7. Plan for Year-End

**Why**: Maximize current year deductions
**How**:
- Scan in November/December
- Execute before December 31
- Consider capital gains from other sources

### 8. Document Everything

**Why**: IRS audit protection
**How**:
- Keep all trade confirmations
- Export harvest history annually
- Save tax reports
- Document wash sale avoidance

---

## Troubleshooting

### Common Issues

#### Issue: "No opportunities found"

**Possible Causes**:
1. No positions with losses > threshold
2. All positions have wash sale risks
3. Prices haven't been updated

**Solutions**:
1. Lower loss threshold in config
2. Wait for wash sale period to expire
3. Click "🔄 Refresh Prices"

#### Issue: "Wash sale risk detected"

**Cause**: You bought/sold the same stock within 30 days

**Solution**:
1. Wait for 30-day period to expire
2. Use a different replacement stock
3. Review wash sale reason in opportunity details

#### Issue: "Import failed - symbol not found"

**Cause**: Stock not in RSP constituents

**Solution**:
1. Verify symbol is in S&P 500
2. Refresh RSP holdings: `fetch_rsp_holdings(force_refresh=True)`
3. Check for ticker changes or delistings

#### Issue: "Database error"

**Cause**: Database not initialized or corrupted

**Solution**:
1. Run migration: `python migrate_add_direct_indexing.py`
2. Check database file exists: `data/rsp_holdings.db`
3. Verify permissions on data directory

#### Issue: "Prices are stale"

**Cause**: Prices haven't been updated recently

**Solution**:
1. Click "🔄 Refresh Prices" in dashboard
2. Or run: `update_position_prices()`
3. Check internet connection
4. Verify Yahoo Finance API is accessible

### Getting Help

1. **Check Logs**: Look in console output for error messages
2. **Run Tests**: `pytest test_direct_indexing.py -v`
3. **Review Documentation**: Re-read relevant sections
4. **Check Configuration**: Verify `direct_indexing_config.yaml`

---

## FAQ

### General Questions

**Q: How much can I save with tax loss harvesting?**

A: Typical savings range from 0.5% to 2% of portfolio value annually. For a $500,000 portfolio, that's $2,500 to $10,000 per year.

**Q: Is this legal?**

A: Yes! Tax loss harvesting is a legitimate tax strategy. Just follow IRS wash sale rules.

**Q: Do I need to own all 500 stocks?**

A: No, but more stocks = more harvest opportunities. Start with 100-200 stocks minimum.

**Q: What if I don't have losses?**

A: That's good! It means your portfolio is up. Harvest when opportunities arise.

### Technical Questions

**Q: How often are prices updated?**

A: Prices are cached for 4 hours. Click "Refresh Prices" for latest data.

**Q: Can I customize the stock list?**

A: Yes, you can exclude specific stocks or sectors in the configuration.

**Q: Does this work with fractional shares?**

A: Yes, if your broker supports fractional shares. Enable in config.

**Q: Can I use this with multiple accounts?**

A: Yes, the system supports multiple accounts. Import positions separately for each.

### Tax Questions

**Q: When do I report harvested losses?**

A: On your tax return for the year you sold (Form 8949 and Schedule D).

**Q: Can I carry forward unused losses?**

A: Yes, capital losses can be carried forward indefinitely.

**Q: What about state taxes?**

A: Most states follow federal capital gains treatment. Consult a tax professional.

**Q: Do I need to tell my accountant?**

A: Yes! Provide them with the tax report from Tab 4.

### Strategy Questions

**Q: Should I harvest short-term or long-term losses first?**

A: Long-term losses are generally more valuable (offset lower-taxed gains). The system prioritizes these.

**Q: What if the replacement stock also drops?**

A: You can harvest it later! This creates a "daisy chain" of harvests.

**Q: Can I buy back the original stock?**

A: Yes, after 31 days. Set a calendar reminder.

**Q: What about dividends?**

A: You'll receive dividends from your new replacement stock instead.

---

## Appendix

### Glossary

**Capital Gain/Loss**: Profit or loss from selling an investment  
**Cost Basis**: Original purchase price of an investment  
**Direct Indexing**: Owning individual stocks instead of an ETF  
**GICS Sector**: Global Industry Classification Standard sector  
**HIFO**: Highest In, First Out (lot selection method)  
**Long-Term**: Held > 365 days  
**Lot**: A specific purchase of shares  
**RSP**: Invesco S&P 500 Equal Weight ETF  
**Short-Term**: Held ≤ 365 days  
**Tax Loss Harvesting**: Selling investments at a loss to offset gains  
**Wash Sale**: Buying substantially identical security within 30 days  

### Resources

**IRS Publications**:
- Publication 550: Investment Income and Expenses
- Publication 551: Basis of Assets

**Useful Links**:
- [IRS Wash Sale Rules](https://www.irs.gov/publications/p550#en_US_2023_publink1000222126)
- [RSP ETF Information](https://www.invesco.com/us/financial-products/etfs/product-detail?audienceType=Investor&ticker=RSP)

### Support

For technical support or questions:
1. Review this guide
2. Check troubleshooting section
3. Run test suite: `pytest test_direct_indexing.py -v`
4. Review implementation documentation

---

**Version**: 1.0  
**Last Updated**: April 18, 2026  
**Author**: Bob

**Disclaimer**: This software is for informational purposes only. Consult a tax professional before making investment decisions. Past performance does not guarantee future results.