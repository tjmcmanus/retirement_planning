---
layout: default
title: BETR Roth Conversion Guide
---

# BETR Roth Conversion Algorithm

**B**racket-**E**fficient **T**ax-Aware **R**oth conversion optimization algorithm.

## Overview

The BETR algorithm optimizes Roth IRA conversions by:
- Filling lower tax brackets efficiently
- Avoiding IRMAA threshold crossings
- Minimizing lifetime tax burden
- Maximizing tax-free growth potential

## How BETR Works

### Core Principles

1. **Bracket Filling**: Convert just enough to fill current tax bracket
2. **IRMAA Avoidance**: Stay below Medicare surcharge thresholds
3. **Multi-Year Planning**: Optimize conversions across multiple years
4. **Tax Arbitrage**: Pay taxes now at lower rates vs. higher RMD rates later

### Algorithm Steps

```
For each year in planning horizon:
  1. Calculate current taxable income
  2. Identify available bracket capacity
  3. Check IRMAA threshold proximity
  4. Calculate optimal conversion amount
  5. Project future tax savings
  6. Execute conversion if beneficial
```

## When to Use BETR

### Ideal Scenarios

✅ **Pre-Retirement (Ages 55-65)**
- Lower income years before RMDs
- Can fill 12%, 22%, or 24% brackets
- Time for tax-free growth

✅ **Early Retirement**
- Gap years before Social Security
- Minimal other income
- Maximum conversion capacity

✅ **Market Downturns**
- Lower account values = lower conversion taxes
- Convert more shares for same tax cost
- Recovery happens tax-free in Roth

### Less Ideal Scenarios

❌ **High Income Years**
- Already in high tax brackets
- Limited conversion capacity
- Better to wait for lower income years

❌ **Near IRMAA Thresholds**
- Risk triggering Medicare surcharges
- Surcharges can exceed conversion benefits
- Need careful threshold management

❌ **Short Time Horizon**
- Need 5+ years for tax-free growth
- Conversion taxes may not be recovered
- Better to leave in Traditional IRA

## Using BETR in the Application

### Step 1: Navigate to Advanced Strategies

1. Launch the application
2. Click on **Advanced Strategies** tab (🎯)
3. Select **BETR Roth Conversion**

### Step 2: Review Current Situation

The tool displays:
- Current Traditional IRA balance
- Current Roth IRA balance
- Projected income for conversion years
- Current tax bracket
- IRMAA threshold proximity

### Step 3: Configure Parameters

**Conversion Period:**
- Start year (typically current year)
- End year (typically age 70 when RMDs begin)
- Number of years to optimize

**Tax Preferences:**
- Target tax bracket (12%, 22%, 24%)
- IRMAA avoidance priority (High/Medium/Low)
- State tax considerations

**Constraints:**
- Maximum annual conversion amount
- Minimum cash reserves
- Other income sources

### Step 4: Run BETR Analysis

Click **Calculate Optimal Conversions**

The algorithm generates:
- Year-by-year conversion schedule
- Tax cost for each conversion
- Projected long-term savings
- IRMAA impact analysis

### Step 5: Review Recommendations

**Conversion Schedule Table:**
```
Year | Age | Income | Conversion | Tax Cost | Bracket | IRMAA
2024 | 60  | $50K   | $45K      | $9.9K   | 22%     | Safe
2025 | 61  | $52K   | $43K      | $9.5K   | 22%     | Safe
2026 | 62  | $75K   | $20K      | $4.4K   | 22%     | Safe
```

**Summary Metrics:**
- Total conversions: $108,000
- Total tax cost: $23,800
- Effective conversion rate: 22%
- Estimated lifetime savings: $85,000

### Step 6: Implement Strategy

**Execution Steps:**
1. Verify conversion amounts fit budget
2. Ensure sufficient cash for taxes
3. Execute conversions before year-end
4. Document for tax filing
5. Update portfolio data

## Advanced BETR Strategies

### Strategy 1: Bracket Surfing

**Concept:** Ride the edge of tax brackets for maximum efficiency

**Implementation:**
```python
# Fill 22% bracket completely
target_income = 89075  # Top of 22% bracket (MFJ)
current_income = 50000
conversion_capacity = target_income - current_income
# Convert $39,075
```

**Benefits:**
- Maximize conversions at lower rates
- Avoid jumping to 24% bracket
- Efficient use of bracket space

### Strategy 2: IRMAA Threshold Management

**IRMAA Thresholds (2024, MFJ):**
- $206,000: +$69.90/month Part B
- $258,000: +$174.70/month Part B
- $322,000: +$279.50/month Part B
- $394,000: +$384.30/month Part B
- $750,000+: +$419.30/month Part B

**Strategy:**
- Stay $10K below thresholds for safety
- Plan 2-year lookback period
- Coordinate with other income sources

**Example:**
```
Current MAGI: $195,000
IRMAA threshold: $206,000
Safe conversion: $11,000 (with $10K buffer)
```

### Strategy 3: Multi-Year Optimization

**Concept:** Optimize across multiple years, not just current year

**Factors to Consider:**
- Income variability
- Tax law changes
- RMD projections
- Life stage transitions

**Example Scenario:**
```
Year 1 (Age 60): High income → Small conversion
Year 2 (Age 61): Retired → Large conversion
Year 3 (Age 62): SS starts → Medium conversion
Year 4-9: Optimize around SS income
Year 10+: RMDs begin → Conversions complete
```

### Strategy 4: Roth Conversion Ladder

**For Early Retirees:**

**5-Year Rule:** Converted amounts can be withdrawn penalty-free after 5 years

**Ladder Strategy:**
```
Year 1: Convert $50K (available Year 6)
Year 2: Convert $50K (available Year 7)
Year 3: Convert $50K (available Year 8)
Year 4: Convert $50K (available Year 9)
Year 5: Convert $50K (available Year 10)
```

**Benefits:**
- Access to funds before 59½
- No 10% early withdrawal penalty
- Tax-free growth on conversions

## Tax Considerations

### Federal Tax Impact

**Conversion Tax Calculation:**
```
Conversion Amount: $50,000
Current Income: $60,000
Total Income: $110,000

Tax on $60K: $6,617 (22% bracket)
Tax on $110K: $17,617
Conversion Tax: $11,000
Effective Rate: 22%
```

### State Tax Impact

**States with No Income Tax:**
- Alaska, Florida, Nevada, South Dakota
- Tennessee, Texas, Washington, Wyoming
- New Hampshire (limited)

**High Tax States:**
- California: Up to 13.3%
- New York: Up to 10.9%
- New Jersey: Up to 10.75%

**Strategy:** Consider moving to low/no tax state before conversions

### IRMAA Impact

**2-Year Lookback:**
- 2024 IRMAA based on 2022 income
- Plan conversions 2+ years before Medicare
- Life-changing events can appeal

**Surcharge Costs:**
```
Threshold exceeded by $1: +$839/year (Part B)
Threshold exceeded by $10K: +$839/year
Threshold exceeded by $52K: +$1,258/year
```

**Lesson:** Stay well below thresholds or jump to next tier

## Common Mistakes to Avoid

### ❌ Mistake 1: Converting Too Much

**Problem:** Jumping to higher tax bracket

**Example:**
```
Income: $80,000
22% bracket ends: $89,075
Convert: $20,000 → Good (stays in 22%)
Convert: $50,000 → Bad (pushes to 24%)
```

**Solution:** Use BETR to calculate exact capacity

### ❌ Mistake 2: Ignoring IRMAA

**Problem:** Triggering Medicare surcharges

**Example:**
```
MAGI: $200,000
Conversion: $10,000
New MAGI: $210,000 → Exceeds $206K threshold
IRMAA cost: $839/year for 2 years = $1,678
Conversion tax: $2,400
Total cost: $4,078 (40.8% effective rate!)
```

**Solution:** Check IRMAA thresholds before converting

### ❌ Mistake 3: No Cash for Taxes

**Problem:** Using IRA funds to pay conversion taxes

**Example:**
```
Convert: $50,000
Tax: $11,000
Pay from IRA: $11,000 (counts as distribution)
Additional tax: $2,420
Total cost: $13,420 vs. $11,000
```

**Solution:** Pay taxes from taxable accounts

### ❌ Mistake 4: Converting Too Late

**Problem:** Waiting until RMDs begin

**Example:**
```
Age 72: RMD = $40,000
Other income: $50,000
Total income: $90,000
Conversion capacity: Minimal
```

**Solution:** Start conversions in 50s or early 60s

## Real-World Examples

### Example 1: Standard Retirement

**Profile:**
- Ages: 60 and 58
- Traditional IRA: $800,000
- Roth IRA: $100,000
- Current income: $50,000
- Retirement: Age 65

**BETR Recommendation:**
```
Years 60-64: Convert $40K/year
Total conversions: $200,000
Total tax cost: $44,000
Effective rate: 22%

Result at age 72:
- Traditional IRA: $750,000 (RMD: $27,000)
- Roth IRA: $450,000 (no RMD)
- Lifetime tax savings: $95,000
```

### Example 2: Early Retirement

**Profile:**
- Age: 55
- Traditional IRA: $1,200,000
- Retired early
- No income until SS at 67

**BETR Recommendation:**
```
Years 55-66: Convert $60K/year
Total conversions: $720,000
Total tax cost: $79,200
Effective rate: 11%

Result:
- Massive tax savings vs. RMDs
- Most assets in Roth
- Tax-free retirement income
```

### Example 3: High Net Worth

**Profile:**
- Ages: 62 and 60
- Traditional IRA: $2,000,000
- Taxable: $1,500,000
- Income: $150,000

**BETR Recommendation:**
```
Limited conversion capacity due to income
Focus on:
- QCDs after age 70½
- Strategic small conversions
- Tax-loss harvesting in taxable
- Consider mega backdoor Roth
```

## Monitoring and Adjusting

### Annual Review Checklist

- [ ] Update income projections
- [ ] Recalculate conversion capacity
- [ ] Check IRMAA thresholds
- [ ] Review tax law changes
- [ ] Adjust conversion schedule
- [ ] Verify cash for taxes

### Triggers for Adjustment

**Increase Conversions:**
- Income lower than expected
- Market downturn (lower values)
- Tax rates increasing
- Moving to low-tax state

**Decrease Conversions:**
- Income higher than expected
- Near IRMAA threshold
- Insufficient cash for taxes
- Tax rates decreasing

## Resources

### IRS Publications
- [Publication 590-A](https://www.irs.gov/publications/p590a) - IRA Contributions
- [Publication 590-B](https://www.irs.gov/publications/p590b) - IRA Distributions

### Medicare Resources
- [IRMAA Information](https://www.medicare.gov/your-medicare-costs/part-b-costs)
- [Medicare.gov](https://www.medicare.gov)

### Related Guides
- [Mega Backdoor Roth Strategy](mega-backdoor-roth.md)
- [Tax Optimization Guide](../guides/tax-optimization.md)
- [Withdrawal Strategies](../guides/withdrawal-strategies.md)

---

[← Back to Guides](../guides.md) | [Home](../../index.md)