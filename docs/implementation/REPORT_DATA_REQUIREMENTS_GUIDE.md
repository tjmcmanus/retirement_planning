# Report Data Requirements Guide

This guide explains how to populate data for each report section so you get full content instead of placeholder messages.

## 📊 Portfolio Review Report

### Performance Analysis Section
**Required Data:** Historical portfolio values and returns

**How to Enable:**
1. **Option A: Connect Live Accounts**
   - Go to **Portfolio Hub** page
   - Click "Connect Account" 
   - Use Schwab or SnapTrade integration
   - Historical performance will be automatically tracked

2. **Option B: Manual Data Entry**
   - Go to **Portfolio Hub** > **Portfolio Data Entry**
   - Enter historical portfolio values for multiple dates
   - System will calculate returns automatically

3. **Option C: Import Transaction History**
   - Go to **Portfolio Hub** > **Transaction History**
   - Import CSV with historical transactions
   - System will reconstruct historical performance

**Data Collection Method:** `_get_performance_data()` in `report_builder.py`
- Currently returns `None` (not implemented)
- Needs to calculate returns from historical portfolio values
- Should return DataFrame with columns: Period, Return, Benchmark, Alpha

### Factor Analysis Section
**Required Data:** Portfolio holdings with factor exposures

**How to Enable:**
1. **Load Portfolio Holdings**
   - Go to **Portfolio Hub** page
   - Ensure holdings are loaded (via connection or manual entry)

2. **Run Factor Analysis**
   - Go to **Portfolio Hub** > **Factor Analysis** tab
   - System will analyze holdings and calculate factor exposures
   - Results are cached for report generation

**Data Collection Method:** `_get_factor_analysis()` in `report_builder.py`
- Currently not implemented
- Needs to retrieve factor analysis results from Portfolio Hub
- Should return dict with 'factor_chart' (Plotly figure) and 'sector_breakdown' (DataFrame)

### Rebalancing Recommendations Section
**Required Data:** Target allocation and current holdings

**How to Enable:**
1. **Set Target Allocation**
   - Go to **Portfolio Hub** > **Optimization** tab
   - Define your target asset allocation (e.g., 60% stocks, 40% bonds)
   - Save target allocation

2. **Load Current Holdings**
   - Ensure portfolio holdings are loaded
   - System will compare current vs target

**Data Collection Method:** `_get_rebalancing_analysis()` in `report_builder.py`
- Currently not implemented
- Needs to compare current allocation vs target
- Should return DataFrame with columns: Asset Class, Current %, Target %, Difference, Trade Amount

### Risk Assessment Section
**Required Data:** Historical portfolio values for volatility calculations

**How to Enable:**
1. **Historical Data Required**
   - Same as Performance Analysis section
   - Need at least 12 months of historical values for meaningful metrics

2. **Automatic Calculation**
   - Once historical data is available, risk metrics are calculated automatically
   - Includes: Standard Deviation, Sharpe Ratio, Max Drawdown, Beta

**Data Collection Method:** `_get_risk_metrics()` in `report_builder.py`
- Currently not implemented
- Needs to calculate volatility, drawdowns from historical returns
- Should return dict with metrics and 'drawdown_chart' (Plotly figure)

---

## 💰 Tax Planning Report

### Current Tax Situation Section
**Required Data:** Current year income and tax calculations

**How to Enable:**
1. **Run Tax Calculations**
   - Go to **Admin Tax Data** page (in sidebar)
   - Enter current year income sources
   - System calculates federal and state taxes
   - Results are stored in database

2. **Required Inputs:**
   - Wages/salary
   - Investment income
   - Social Security benefits
   - RMDs (if applicable)
   - Deductions

**Data Collection Method:** `_get_current_tax_data()` in `report_builder.py`
- Currently returns `None`
- Needs to query tax calculation results from Admin Tax Data
- Should return dict with: federal_tax, state_tax, effective_rate, marginal_rate, irmaa_status

### Roth Conversion Analysis Section
**Required Data:** Tax projections and retirement strategy

**How to Enable:**
1. **Configure Retirement Strategy**
   - Go to **Strategy** page
   - Set up retirement income plan
   - Define withdrawal strategy

2. **Run Tax Projections**
   - System will project taxes for future years
   - Roth conversion opportunities are identified automatically

**Data Collection Method:** `_get_roth_conversion_data()` in `report_builder.py`
- Currently returns `None`
- Needs to analyze optimal Roth conversion amounts
- Should return dict with: optimal_amount, multi_year_plan (DataFrame), tax_impact

### Tax Loss Harvesting Section
**Required Data:** Portfolio holdings with cost basis

**How to Enable:**
1. **Import Holdings with Cost Basis**
   - Go to **Portfolio Hub** > **Portfolio Data Entry**
   - Ensure each holding has cost basis information
   - Or connect brokerage account (cost basis imported automatically)

2. **Automatic Analysis**
   - System identifies positions with unrealized losses
   - Checks wash sale rules
   - Suggests harvesting opportunities

**Data Collection Method:** `_get_tax_harvesting_data()` in `report_builder.py`
- Currently returns `None`
- Needs to identify positions with losses
- Should return DataFrame with: Symbol, Cost Basis, Market Value, Loss, Recommendation

### Charitable Giving Strategies Section
**Required Data:** Charitable giving goals and configuration

**How to Enable:**
1. **Configure Charitable Goals**
   - Go to **Strategy** page > **Advanced Strategies**
   - Set annual charitable giving amount
   - Enable DAF or QCD strategies

2. **System Calculates Benefits**
   - Tax savings from charitable deductions
   - DAF bunching opportunities
   - QCD benefits (if age 70½+)

**Data Collection Method:** `_get_charitable_giving_data()` in `report_builder.py`
- Currently not implemented
- Needs to retrieve charitable strategy configuration
- Should return dict with: daf_benefit, qcd_benefit, total_savings

### Multi-Year Tax Projections Section
**Required Data:** Retirement strategy with income projections

**How to Enable:**
1. **Complete Retirement Strategy**
   - Go to **Strategy** page
   - Configure all income sources (Social Security, pensions, withdrawals)
   - Set withdrawal strategy

2. **Run Projections**
   - System projects income and taxes for 10+ years
   - Identifies tax bracket changes
   - Suggests optimization opportunities

**Data Collection Method:** `_get_tax_projections()` in `report_builder.py`
- Currently not implemented
- Needs to retrieve multi-year tax projections from strategy module
- Should return DataFrame with: Year, Income, Federal Tax, State Tax, Effective Rate

---

## 🔧 Implementation Checklist

To fully populate all report sections, implement these data collection methods in `components/reporting/report_builder.py`:

### High Priority (Portfolio Review)
- [ ] `_get_performance_data()` - Calculate returns from historical portfolio values
- [ ] `_get_factor_analysis()` - Retrieve factor analysis from Portfolio Hub
- [ ] `_get_rebalancing_analysis()` - Compare current vs target allocation
- [ ] `_get_risk_metrics()` - Calculate volatility and drawdown metrics

### High Priority (Tax Planning)
- [ ] `_get_current_tax_data()` - Query Admin Tax Data results
- [ ] `_get_roth_conversion_data()` - Analyze Roth conversion opportunities
- [ ] `_get_tax_harvesting_data()` - Identify tax loss harvesting opportunities
- [ ] `_get_charitable_giving_data()` - Retrieve charitable strategy configuration
- [ ] `_get_tax_projections()` - Get multi-year tax projections

### Data Sources to Connect
- [ ] Admin Tax Data page → Current tax calculations
- [ ] Portfolio Hub → Holdings, performance, factor analysis
- [ ] Strategy page → Retirement projections, charitable goals
- [ ] Transaction History → Historical performance reconstruction

---

## 📝 Quick Start Guide

### For Portfolio Review Report:
1. Connect a brokerage account OR manually enter portfolio holdings
2. Wait for historical data to accumulate (or import transaction history)
3. Run factor analysis in Portfolio Hub
4. Set target allocation in Portfolio Hub > Optimization
5. Generate report - all sections will have content!

### For Tax Planning Report:
1. Go to Admin Tax Data page and enter current year income
2. Go to Strategy page and configure retirement plan
3. Enable charitable giving strategies if applicable
4. Generate report - all sections will have content!

### For Immediate Testing:
The **Net Worth & Market Outlook Report** works immediately with just portfolio data loaded, as it doesn't require historical performance or tax calculations.

---

## 🎯 Current Status

**Working Now (No Additional Data Needed):**
- Comprehensive Retirement Plan
- Executive Summary
- Net Worth & Market Outlook Report
- Estate Planning Report

**Needs Data (Shows Helpful Messages):**
- Portfolio Review Report (needs historical performance, factor analysis, target allocation)
- Tax Planning Report (needs tax calculations, strategy configuration)
- Monte Carlo Analysis (needs retirement strategy configuration)

**Next Steps:**
Implement the data collection methods listed above to fully populate all report sections with actual data instead of placeholder messages.