# Strategy Page UX Redesign

## Overview
The Strategy page has been completely redesigned to provide better visualization and execution planning for long-term financial strategies. The redesign addresses the need for granular flow-of-funds tracking and practical month-by-month execution guidance.

## Key Improvements

### 1. **Enhanced Tab Structure**
The page now features four main tabs:
- **📋 Long-Term Plan**: Multi-year strategy overview with state taxes
- **📅 Monthly Calendar**: NEW - Month-by-month execution plan
- **💰 Account Balances**: Projected account balances over time
- **📊 Visualizations**: Charts and graphs for visual analysis

### 2. **State Tax Integration**
- Added **State Tax** column to all strategy tables
- Automatically calculates state income tax based on configured state
- Supports major states (CA, NY, TX, FL, etc.)
- Shows combined federal + state tax burden for accurate planning

### 3. **Summary Insight Cards**
Four key metrics displayed at the top of the Long-Term Plan:
- **Planning Horizon**: Total years in the plan
- **Total Contributions/Withdrawals**: Aggregate retirement account activity
- **Total Taxes**: Combined federal and state taxes over planning period
- **Portfolio Growth**: Net portfolio change with percentage

### 4. **Timeline View for Key Events**
Visual timeline showing major financial milestones:
- 🎯 Retirement begins
- 🏥 Medicare eligibility (age 65)
- 💰 Social Security benefits start
- 📊 Required Minimum Distributions (RMDs) begin
- 🔄 Major Roth conversions (>$50K)

### 5. **Interactive Sankey Diagrams**
- **Year Selector**: Choose any year to see detailed money flows
- **Dynamic Updates**: Sankey diagram updates based on actual year data
- **Accumulation Phase**: Shows income → accounts flow
- **Withdrawal Phase**: Shows accounts → expenses & conversions flow
- **Real Data**: Uses actual transaction amounts from strategy calculations

### 6. **Month-by-Month Execution Calendar** (NEW)
The most significant addition - a practical execution guide showing:

#### Quarterly Tax Payments
- Q1 (April 15): Estimated tax payment
- Q2 (June 15): Estimated tax payment
- Q3 (September 15): Estimated tax payment
- Q4 (January 15): Prior year estimated tax payment

#### Roth Conversions
- Spread across Jan, Apr, Jul, Oct
- Shows quarterly conversion amounts
- Helps avoid large tax spikes in single month

#### RMD Distributions
- Quarterly distributions (March, June, September, December)
- Ensures compliance with year-end deadline
- Spreads tax impact throughout the year

#### Traditional IRA Withdrawals
- Monthly withdrawals for living expenses
- Only shown if amount is significant (>$1,000/month)
- Helps plan cash flow

#### Portfolio Rebalancing
- Quarterly reviews (March, June, September, December)
- Reminder to check asset allocation
- Maintain target portfolio mix

#### Strategy Reviews
- Semi-annual reviews (January and July)
- Time to reassess and adjust plan
- Incorporate life changes or market conditions

#### Healthcare Premiums
- Monthly premium amounts shown
- Helps budget for healthcare costs
- Includes Medicare, ACA, or private insurance

### 7. **Improved Visual Hierarchy**
- Clear section headers with emoji icons
- Expandable monthly cards for easy scanning
- Color-coded Sankey flows for intuitive understanding
- Responsive layout that works on all screen sizes

## Usage Guide

### Viewing the Long-Term Plan
1. Select your planning phase (Accumulation or Withdrawal)
2. Review the summary cards for quick insights
3. Check the timeline for upcoming milestones
4. Use the year selector on the Sankey diagram to explore specific years
5. Scroll through the detailed year-by-year table

### Using the Monthly Calendar
1. Navigate to the **📅 Monthly Calendar** tab
2. Select the year you want to plan for
3. Expand each month to see action items
4. Note the amounts and timing for each action
5. Use this as your execution checklist throughout the year

### Understanding the Sankey Diagrams
- **Node Size**: Proportional to dollar amount
- **Flow Color**: Matches source account type
- **Hover**: Shows exact amounts and descriptions
- **Interactive**: Select different years to see how flows change over time

## Technical Implementation

### State Tax Calculation
Use def calculate_state_tax(state_agi: float, state: Optional[str] = None, year: int = 2024,
                       filing_status: str = "married_filing_jointly",
                       retirement_income: float = 0,
                       ss_benefits: float = 0) -> Tuple[float, Dict]: Found in @strategy.py
                       

### Monthly Plan Generation
The `create_monthly_execution_plan()` function:
- Analyzes annual strategy data
- Distributes actions across appropriate months
- Follows IRS deadlines for tax payments
- Optimizes timing for conversions and withdrawals
- Provides actionable guidance with specific amounts

### Data Flow
```
Strategy Engine → Annual DataFrame → Monthly Plan Generator → UI Display
                                  ↓
                            Sankey Visualizer
                                  ↓
                            Timeline Builder
```

## Benefits

### For Users
1. **Clarity**: See exactly what to do each month
2. **Confidence**: Know when taxes are due and how much
3. **Optimization**: Spread conversions and withdrawals for tax efficiency
4. **Compliance**: Never miss RMD deadlines or estimated tax payments
5. **Planning**: Visualize long-term strategy with state taxes included

### For Financial Planning
1. **Granular Tracking**: See every dollar's movement
2. **Tax Optimization**: State + federal tax visibility
3. **Execution Ready**: Turn strategy into actionable steps
4. **Flexible**: Adjust plan year by year as circumstances change
5. **Comprehensive**: Covers all aspects of retirement planning

## Future Enhancements

### Potential Additions
1. **Export to Calendar**: Add actions to Google Calendar or iCal
2. **Email Reminders**: Automated reminders for upcoming actions
3. **Mobile View**: Optimized mobile interface for on-the-go access
4. **Actual vs. Planned**: Track execution against plan
5. **What-If Scenarios**: Compare different strategy variations
6. **State Tax Brackets**: Full state tax calculation with brackets
7. **AMT Integration**: Show Alternative Minimum Tax impact
8. **NIIT Tracking**: Net Investment Income Tax visibility
9. **Charitable Giving**: Integrate QCD and DAF strategies
10. **Healthcare Optimization**: IRMAA threshold management

## Comparison: Before vs. After

### Before
- Single flat table with all years
- No state tax visibility
- Static Sankey diagram
- No execution guidance
- Difficult to understand flow of funds

### After
- Organized tabs with clear purpose
- State tax column integrated
- Interactive year-by-year Sankey
- Month-by-month execution calendar
- Timeline view of key events
- Summary cards for quick insights
- Better visual hierarchy

## Feedback Welcome

This redesign represents a significant UX improvement based on user feedback. We welcome additional suggestions for:
- Additional monthly actions to track
- Different visualization preferences
- Export formats needed
- Integration with other tools
- Mobile experience improvements

---

**Version**: 1.0  
**Date**: 2026-03-03  
**Author**: Bob (Senior UX Designer & Developer)