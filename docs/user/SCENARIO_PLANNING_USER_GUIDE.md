# Scenario Planning & What-If Analysis - User Guide

## Overview

The Scenario Planning feature allows you to explore multiple retirement scenarios side-by-side, model significant life events, and make data-driven decisions about your retirement strategy. Compare up to 4 scenarios simultaneously with comprehensive analysis including Monte Carlo simulations, tax implications, and cash flow projections.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Creating Your First Scenario](#creating-your-first-scenario)
3. [Understanding Life Events](#understanding-life-events)
4. [Comparing Scenarios](#comparing-scenarios)
5. [Analyzing Results](#analyzing-results)
6. [Advanced Features](#advanced-features)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Getting Started

### Accessing Scenario Planning

1. Launch the retirement planning application
2. Navigate to **🎯 Scenario Planning** from the main menu
3. The application will automatically create a baseline scenario from your current configuration

### Understanding the Interface

The Scenario Planning page consists of:

- **Scenario Management Bar**: Select, create, clone, and delete scenarios
- **Quick Comparison**: View key metrics for all selected scenarios
- **Analysis Tabs**: Five comprehensive tabs for detailed analysis
  - 📈 Portfolio Trajectories
  - 💰 Cash Flow Analysis
  - 📅 Life Events Timeline
  - ⚙️ Parameter Comparison
  - ✏️ Edit Scenarios

## Creating Your First Scenario

### Method 1: Start with Baseline

The easiest way to start is with the automatically created baseline scenario:

1. The baseline scenario uses your current configuration
2. Clone it to create variations: Click **📋 Clone Selected**
3. Edit the cloned scenario to explore "what-if" questions

### Method 2: Create from Scratch

To create a completely new scenario:

1. Click **➕ New Scenario**
2. Fill in the basic information:
   - **Name**: Descriptive name (e.g., "Early Retirement at 60")
   - **Description**: Brief explanation of the scenario
3. Set financial parameters:
   - Starting Portfolio
   - Annual Expenses
   - Inflation Rate
4. Set personal parameters:
   - Retirement Age
   - Plan To Age
5. Configure Social Security:
   - Annual Amount
   - Start Age
6. Click **💾 Save Changes**

### Example: Creating an Early Retirement Scenario

```
Scenario Name: Early Retirement at 60
Description: Retire 5 years early with reduced expenses

Financial Parameters:
- Starting Portfolio: $1,500,000
- Annual Expenses: $65,000 (reduced from $80,000)
- Inflation Rate: 2.9%

Personal Parameters:
- Retirement Age: 60 (changed from 65)
- Plan To Age: 95

Social Security:
- Annual Amount: $36,000
- Start Age: 70
```

## Understanding Life Events

Life events are significant financial occurrences that impact your retirement plan. The system provides 14 pre-defined templates plus custom event creation.

### Available Life Event Templates

#### 1. **Early Retirement**
Retire earlier than originally planned with adjusted expenses.

**Example Use Case**: You want to retire at 60 instead of 65.

**Parameters**:
- Retirement Age: 60
- Expense Reduction: $15,000/year (no commute, work clothes)

**Impact**:
- Reduces annual expenses
- Starts portfolio withdrawals earlier

#### 2. **Part-Time Work**
Work part-time during retirement for additional income.

**Example Use Case**: Consulting work 2 days/week from ages 62-67.

**Parameters**:
- Start Age: 62
- End Age: 67
- Annual Income: $30,000

**Impact**:
- Adds taxable income
- Reduces portfolio withdrawals needed

#### 3. **Inheritance**
Receive an inheritance windfall.

**Example Use Case**: Expected inheritance at age 70.

**Parameters**:
- Age: 70
- Amount: $500,000
- Taxable Portion: $0 (typically tax-free)

**Impact**:
- One-time portfolio boost
- Improves success probability

#### 4. **Home Purchase**
Purchase a home with down payment and ongoing costs.

**Example Use Case**: Buy vacation home at age 65.

**Parameters**:
- Age: 65
- Purchase Price: $500,000
- Down Payment: 20% ($100,000)
- Annual Costs: $15,000 (taxes, insurance, maintenance)

**Impact**:
- One-time portfolio withdrawal for down payment
- Increased annual expenses

#### 5. **College Funding**
Fund college education for children or grandchildren.

**Example Use Case**: Help grandchildren with college costs.

**Parameters**:
- Start Age: 65
- Duration: 4 years
- Annual Cost: $50,000

**Impact**:
- Increased annual expenses for duration
- Significant portfolio impact

#### 6. **Downsizing**
Sell current home and move to smaller/less expensive home.

**Example Use Case**: Downsize at age 75 to reduce expenses.

**Parameters**:
- Age: 75
- Home Sale Proceeds: $400,000
- New Home Cost: $250,000
- Expense Reduction: $10,000/year

**Impact**:
- Net proceeds added to portfolio ($150,000)
- Reduced annual expenses

#### 7. **Relocation**
Move to lower cost of living area.

**Example Use Case**: Move to Florida at age 70.

**Parameters**:
- Age: 70
- Moving Cost: $20,000
- Expense Change: -$15,000/year (lower taxes, cost of living)

**Impact**:
- One-time moving expense
- Reduced annual expenses

#### 8. **Major Medical**
Significant medical event with costs.

**Example Use Case**: Major surgery at age 75.

**Parameters**:
- Age: 75
- One-Time Cost: $100,000
- Ongoing Annual Cost: $10,000
- Duration: 5 years

**Impact**:
- One-time portfolio withdrawal
- Increased annual expenses for duration

#### 9. **Business Sale**
Sell a business for proceeds.

**Example Use Case**: Sell small business at age 65.

**Parameters**:
- Age: 65
- Sale Proceeds: $2,000,000
- Capital Gains Portion: 80%

**Impact**:
- Large portfolio boost
- Taxable income (capital gains)

#### 10. **Rental Income**
Receive rental income from property.

**Example Use Case**: Rental property income starting at age 62.

**Parameters**:
- Start Age: 62
- End Age: None (ongoing)
- Annual Income: $24,000
- Annual Expenses: $8,000
- Net Income: $16,000

**Impact**:
- Additional taxable income
- Reduces portfolio withdrawals needed

### Adding Life Events to a Scenario

1. Select the scenario you want to edit (must select exactly one)
2. Go to the **✏️ Edit Scenarios** tab
3. Scroll to **📅 Manage Life Events**
4. Click **➕ Add Life Event**
5. Select a template from the dropdown
6. Customize the parameters:
   - Event Name
   - Start Age
   - End Age (if applicable)
   - Financial impacts
   - Notes
7. Click **➕ Add Event**

### Life Event Conflict Detection

The system automatically detects potential conflicts:

- **Overlapping incompatible events**: Early retirement + part-time work at same age
- **Unrealistic timing**: Events starting before age 40 or after 100
- **Portfolio depletion risk**: Events that would drain portfolio

Conflicts are shown with ⚠️ warnings in the Life Events Timeline tab.

## Comparing Scenarios

### Selecting Scenarios to Compare

1. Use the multi-select dropdown at the top of the page
2. Select 2-4 scenarios for comparison
3. The page updates automatically with comparison data

### Quick Comparison Metrics

For each selected scenario, you'll see:

- **Success Rate**: Probability portfolio survives to plan end age
  - 🟢 Green: ≥ 90% (high confidence)
  - 🟡 Yellow: 75-90% (moderate confidence)
  - 🔴 Red: < 75% (at risk)
- **Final Portfolio (Median)**: Expected portfolio value at end age
- **Retirement Age**: Age at retirement
- **Annual Expenses**: Expected annual expenses

### Portfolio Trajectories Tab

Compare how portfolio values evolve over time:

- **Median Path Chart**: Shows median portfolio value by age for each scenario
- **Success Probability Chart**: Bar chart comparing success rates
- **Color-coded lines**: Each scenario has a unique color

**Interpretation**:
- Higher lines = more wealth preserved
- Steeper declines = faster portfolio depletion
- Crossing lines = scenarios diverge at that age

### Cash Flow Analysis Tab

Analyze income, expenses, and net cash flow:

- **Income vs. Expenses Chart**: Stacked area chart showing cash flow
- **Life Event Integration**: Shows impact of events on cash flow
- **Summary Metrics**: Average annual income, expenses, and net cash flow

**Key Insights**:
- Positive net cash flow = portfolio grows
- Negative net cash flow = portfolio withdrawals needed
- Spikes indicate life events (inheritance, major expenses)

### Life Events Timeline Tab

Visual timeline of all life events:

- **Event Table**: Detailed list of all events with impacts
- **Timeline Chart**: Visual representation of event timing
- **Conflict Warnings**: Alerts for potential issues

### Parameter Comparison Tab

Side-by-side comparison of all parameters:

- Starting Portfolio
- Annual Expenses
- Retirement Age
- Plan To Age
- Inflation Rate
- Social Security details
- Number of Life Events
- Success Rate
- Final Portfolio

**Export**: Click **📥 Download Comparison (CSV)** to export the table

## Analyzing Results

### Understanding Success Probability

Success probability is the percentage of Monte Carlo simulations where the portfolio survives to the plan end age.

**Guidelines**:
- **≥ 90%**: High confidence - portfolio very likely to last
- **75-90%**: Moderate confidence - acceptable risk for many
- **< 75%**: At risk - consider adjustments

**Factors that improve success**:
- Higher starting portfolio
- Lower annual expenses
- Later retirement age
- Additional income sources (Social Security, part-time work)
- Positive life events (inheritance, business sale)

**Factors that reduce success**:
- Early retirement
- Higher expenses
- Major expense events (home purchase, college funding)
- Longer planning horizon

### Interpreting Portfolio Trajectories

The portfolio trajectory chart shows the median path across all simulations:

**Healthy Trajectory**:
- Gradual decline or stable
- Remains well above zero
- Increases when Social Security starts

**Concerning Trajectory**:
- Steep decline
- Approaches zero before end age
- Sharp drops from life events

### Tax Impact Analysis

While not shown in the main UI, scenarios are analyzed for tax implications:

- Total taxes paid across retirement
- Average effective tax rate
- Impact of life events on taxable income

**Tax-Efficient Strategies**:
- Delay Social Security to reduce taxable income early
- Roth conversions in low-income years
- Strategic timing of taxable events (business sale, inheritance)

## Advanced Features

### Scenario Sharing

Share scenarios with others via URL:

1. Select the scenarios you want to share
2. Click **🔗 Generate Share Link**
3. Copy the URL parameter
4. Append to your app URL: `?scenarios=<encoded_parameter>`
5. Share the full URL

**Note**: The URL contains encoded scenario IDs, not full scenario data. Recipients must have access to the same scenario files.

### Exporting Scenarios

Export scenarios for backup or analysis:

1. Select scenarios to export
2. Click **📥 Export Scenarios**
3. Download JSON file
4. File contains complete scenario data including life events

**Use Cases**:
- Backup scenarios before major changes
- Share with financial advisor
- Import into other tools for analysis

### Re-running Analysis

If you modify a scenario, re-run the analysis:

1. Make changes in the **✏️ Edit Scenarios** tab
2. Click **💾 Save & Re-run Analysis**
3. Or click **🔄 Re-run All Analyses** to update all scenarios

**When to re-run**:
- After adding/removing life events
- After changing financial parameters
- After updating retirement age or plan horizon

### Baseline Scenario

The baseline scenario represents your current plan:

- Automatically created from your configuration
- Marked with a special indicator
- Cannot be deleted (but can be edited)
- Use as reference point for comparisons

## Best Practices

### 1. Start Simple

- Begin with baseline scenario
- Clone and make one change at a time
- Compare to see impact of each change

### 2. Use Realistic Assumptions

- Don't be overly optimistic about returns
- Include realistic expense estimates
- Account for inflation
- Plan for longer life expectancy than expected

### 3. Model Key Life Events

Focus on events most likely to occur:
- Social Security timing
- Part-time work in early retirement
- Downsizing home
- Major known expenses

### 4. Compare Apples to Apples

When comparing scenarios:
- Keep most parameters the same
- Change only what you're testing
- Use consistent assumptions

### 5. Consider Multiple Scenarios

Create scenarios for:
- **Best Case**: Everything goes well
- **Base Case**: Expected outcome
- **Worst Case**: Conservative assumptions

### 6. Review Regularly

- Update scenarios as circumstances change
- Re-run analysis with new market data
- Adjust for life changes

### 7. Focus on Success Probability

- Aim for ≥ 90% success rate
- If below 75%, consider adjustments:
  - Reduce expenses
  - Delay retirement
  - Increase savings
  - Add income sources

## Troubleshooting

### Scenario Won't Save

**Problem**: Error when saving scenario

**Solutions**:
- Check all required fields are filled
- Ensure retirement age < plan to age
- Verify portfolio allocation sums to 100%
- Check for negative values where not allowed

### Analysis Takes Too Long

**Problem**: Monte Carlo simulation is slow

**Solutions**:
- Reduce number of simulations (default: 5,000 for UI)
- Close other applications
- Simplify life events
- Consider running overnight for detailed analysis

### Life Event Not Showing Impact

**Problem**: Added life event but no visible impact

**Solutions**:
- Verify event age is within retirement period
- Check event is active (not in past)
- Re-run analysis after adding event
- Review event parameters (amounts may be too small)

### Scenarios Not Comparing

**Problem**: Can't see comparison charts

**Solutions**:
- Select at least 2 scenarios
- Ensure scenarios have been analyzed (run Monte Carlo)
- Check for errors in scenario configuration
- Try re-running analysis

### Success Rate Seems Wrong

**Problem**: Success probability doesn't match expectations

**Solutions**:
- Verify all parameters are correct
- Check life events are configured properly
- Review portfolio allocation
- Ensure Social Security amounts are annual (not monthly)
- Check inflation rate is reasonable (2-4%)

### Can't Delete Scenario

**Problem**: Delete button is disabled

**Solutions**:
- Can only delete one scenario at a time
- Cannot delete baseline scenario
- Select exactly one non-baseline scenario

## Tips for Effective Scenario Planning

### 1. Early Retirement Analysis

To model early retirement:
1. Clone baseline scenario
2. Reduce retirement age
3. Add "Early Retirement" life event with expense reduction
4. Consider adding part-time work event
5. Compare success rates

### 2. Social Security Optimization

Test different Social Security claiming ages:
1. Create scenarios for ages 62, 67, and 70
2. Keep all other parameters the same
3. Compare total lifetime benefits
4. Consider tax implications

### 3. Major Purchase Planning

To plan for a major purchase:
1. Add "Home Purchase" or custom event
2. Model down payment and ongoing costs
3. Compare with scenario without purchase
4. Assess impact on success probability

### 4. Inheritance Planning

Model expected inheritance:
1. Add "Inheritance" event at expected age
2. Set realistic amount
3. Compare with and without inheritance
4. Don't rely solely on uncertain events

### 5. Healthcare Cost Planning

Model increased healthcare costs:
1. Add "Major Medical" event
2. Or increase base expenses in later years
3. Consider long-term care costs
4. Plan for Medicare premiums (IRMAA)

## Conclusion

Scenario Planning is a powerful tool for exploring retirement possibilities and making informed decisions. By comparing multiple scenarios with different assumptions and life events, you can:

- Understand the impact of key decisions
- Identify risks and opportunities
- Build confidence in your retirement plan
- Make data-driven adjustments

Remember: No scenario is perfect, but comparing multiple scenarios helps you understand the range of possible outcomes and plan accordingly.

For technical details, see the [API Documentation](../implementation/SCENARIO_PLANNING_API.md).

For implementation details, see the [Implementation Plan](../implementation/SCENARIO_PLANNING_IMPLEMENTATION.md).

---

**Need Help?**

- Review the [Troubleshooting](#troubleshooting) section
- Check the [Best Practices](#best-practices)
- Consult with a financial advisor for personalized guidance

**Version**: 1.0 (April 2026)