# Life Event Modeling Examples

## Overview

This document provides practical examples of modeling various life events in retirement planning scenarios. Each example includes the scenario setup, life event configuration, expected impacts, and analysis tips.

## Table of Contents

1. [Early Retirement Scenarios](#early-retirement-scenarios)
2. [Part-Time Work Strategies](#part-time-work-strategies)
3. [Windfall Events](#windfall-events)
4. [Major Expenses](#major-expenses)
5. [Family Changes](#family-changes)
6. [Healthcare Events](#healthcare-events)
7. [Real Estate Transactions](#real-estate-transactions)
8. [Combined Scenarios](#combined-scenarios)

## Early Retirement Scenarios

### Example 1: Retire 5 Years Early

**Scenario**: You want to retire at 60 instead of 65, with reduced expenses due to no commute and work-related costs.

**Setup**:
```python
from scenario_manager import Scenario, SocialSecurityConfig
from life_event_modeler import LifeEventTemplates

scenario = Scenario(
    name="Early Retirement at 60",
    description="Retire 5 years early with reduced expenses",
    initial_portfolio=1_500_000,
    annual_expenses=80_000,  # Will be reduced by event
    retirement_age=60,
    plan_to_age=95,
    social_security=SocialSecurityConfig(
        person1_amount=36_000,
        person1_start_age=70  # Delay SS to maximize benefits
    )
)

# Add early retirement event
scenario.life_events.append(
    LifeEventTemplates.early_retirement(
        retirement_age=60,
        expense_reduction=15_000,  # Save on commute, work clothes, etc.
        notes="No commute, reduced dining out, no work wardrobe"
    )
)
```

**Expected Impact**:
- Annual expenses: $80,000 → $65,000
- Portfolio withdrawals start 5 years earlier
- More years of portfolio depletion risk
- Success probability typically drops 5-10%

**Analysis Tips**:
- Compare with baseline retirement at 65
- Consider part-time work to bridge the gap
- Model different expense reduction amounts
- Test various Social Security claiming ages

### Example 2: Phased Retirement

**Scenario**: Gradually transition to retirement by working part-time from 62-67, then fully retire.

**Setup**:
```python
scenario = Scenario(
    name="Phased Retirement",
    description="Part-time work 62-67, then full retirement",
    initial_portfolio=1_200_000,
    annual_expenses=70_000,
    retirement_age=62,
    plan_to_age=95
)

# Reduce to part-time at 62
scenario.life_events.append(
    LifeEventTemplates.part_time_work(
        start_age=62,
        end_age=67,
        annual_income=40_000,  # 2-3 days/week
        notes="Consulting 2-3 days per week"
    )
)

# Reduce expenses during part-time phase
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="Reduced Expenses During Part-Time",
        start_age=62,
        end_age=67,
        expense_change=-10_000,
        notes="Still have some work expenses"
    )
)
```

**Expected Impact**:
- Income: +$40,000/year ages 62-67
- Expenses: -$10,000/year ages 62-67
- Net: $30,000/year less portfolio withdrawal
- Significantly improves success probability

## Part-Time Work Strategies

### Example 3: Consulting Income

**Scenario**: Leverage your expertise for consulting income in early retirement.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.part_time_work(
        start_age=62,
        end_age=70,
        annual_income=50_000,  # Higher rate, fewer hours
        notes="High-value consulting 1-2 days/week"
    )
)
```

**Variations**:

**Declining Income Model**:
```python
# Year 1-3: Full consulting
scenario.life_events.append(
    LifeEventTemplates.part_time_work(62, 64, annual_income=50_000)
)

# Year 4-6: Reduced consulting
scenario.life_events.append(
    LifeEventTemplates.part_time_work(65, 67, annual_income=30_000)
)

# Year 7-8: Minimal consulting
scenario.life_events.append(
    LifeEventTemplates.part_time_work(68, 69, annual_income=15_000)
)
```

### Example 4: Seasonal Work

**Scenario**: Work seasonally (e.g., tax season, holiday retail).

**Setup**:
```python
# Model as annual income averaged over the year
scenario.life_events.append(
    LifeEventTemplates.part_time_work(
        start_age=62,
        end_age=70,
        annual_income=20_000,  # 3-4 months of work
        notes="Seasonal tax preparation work"
    )
)
```

## Windfall Events

### Example 5: Expected Inheritance

**Scenario**: You expect to receive an inheritance at age 70.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.inheritance(
        age=70,
        amount=500_000,
        taxable_portion=0,  # Most inheritances are tax-free
        notes="Expected inheritance from parents"
    )
)
```

**Analysis Tips**:
- Create two scenarios: with and without inheritance
- Don't rely solely on uncertain events
- Consider earlier/later timing scenarios
- Model partial amounts (conservative estimate)

### Example 6: Business Sale

**Scenario**: Sell your business at retirement.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.business_sale(
        age=65,
        sale_proceeds=2_000_000,
        capital_gains_pct=0.80,  # 80% is capital gains
        notes="Sell consulting business at retirement"
    )
)
```

**Tax Considerations**:
```python
# Model the tax impact
taxable_gain = 2_000_000 * 0.80  # $1,600,000
# Long-term capital gains rates apply
# Consider spreading sale over multiple years
```

### Example 7: Stock Options Vesting

**Scenario**: Large stock option vest at specific age.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="Stock Options Vest",
        start_age=62,
        one_time_amount=300_000,
        taxable_income_change=300_000,  # Ordinary income
        notes="Final stock option vest at retirement"
    )
)
```

## Major Expenses

### Example 8: Home Purchase

**Scenario**: Buy a vacation home at age 65.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.home_purchase(
        age=65,
        purchase_price=500_000,
        down_payment_pct=0.30,  # 30% down
        annual_costs=18_000,  # Property tax, insurance, maintenance
        notes="Vacation home in Florida"
    )
)
```

**Expected Impact**:
- One-time: -$150,000 (down payment)
- Annual: +$18,000 expenses
- Consider rental income if applicable

### Example 9: College Funding for Grandchildren

**Scenario**: Help fund college for two grandchildren.

**Setup**:
```python
# First grandchild
scenario.life_events.append(
    LifeEventTemplates.college_funding(
        start_age=68,
        years=4,
        annual_cost=40_000,
        notes="Grandchild 1 college funding"
    )
)

# Second grandchild (starts 2 years later)
scenario.life_events.append(
    LifeEventTemplates.college_funding(
        start_age=70,
        years=4,
        annual_cost=40_000,
        notes="Grandchild 2 college funding"
    )
)
```

**Expected Impact**:
- Ages 68-69: +$40,000/year
- Ages 70-71: +$80,000/year (both in college)
- Ages 72-73: +$40,000/year
- Total: $320,000 over 6 years

### Example 10: RV Purchase and Travel

**Scenario**: Buy an RV and travel extensively in early retirement.

**Setup**:
```python
# RV purchase
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="RV Purchase",
        start_age=62,
        portfolio_withdrawal=150_000,
        notes="Purchase RV for travel"
    )
)

# Increased travel expenses
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="Extensive Travel",
        start_age=62,
        end_age=72,
        expense_change=20_000,  # Fuel, campgrounds, maintenance
        notes="Active travel phase"
    )
)

# Sell RV and reduce travel
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="Sell RV",
        start_age=72,
        portfolio_contribution=50_000,  # Depreciated value
        expense_change=-20_000,  # End travel expenses
        notes="Sell RV, reduce travel"
    )
)
```

## Family Changes

### Example 11: Divorce Impact

**Scenario**: Model financial impact of divorce at age 65.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.divorce(
        age=65,
        asset_split_pct=0.50,  # 50/50 split
        portfolio_value=1_500_000,
        expense_change=-25_000,  # Single person expenses
        notes="Divorce settlement - 50/50 split"
    )
)
```

**Expected Impact**:
- Portfolio: $1,500,000 → $750,000
- Expenses: $80,000 → $55,000 (single person)
- Social Security: May need to adjust
- Tax filing status: Single

### Example 12: Remarriage

**Scenario**: Remarry at age 70 with combined finances.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.remarriage(
        age=70,
        combined_income_increase=20_000,  # Spouse's pension
        expense_increase=15_000,  # Household expenses increase
        notes="Remarriage with combined finances"
    )
)
```

## Healthcare Events

### Example 13: Major Medical Event

**Scenario**: Significant medical event requiring surgery and ongoing care.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.major_medical(
        age=75,
        one_time_cost=150_000,  # Surgery, hospital stay
        ongoing_annual_cost=20_000,  # Ongoing treatment
        duration_years=5,
        notes="Major surgery with 5-year recovery"
    )
)
```

**Expected Impact**:
- Age 75: -$150,000 one-time
- Ages 75-79: +$20,000/year
- Total: $250,000 over 5 years

### Example 14: Long-Term Care

**Scenario**: Need for assisted living starting at age 85.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="Assisted Living",
        start_age=85,
        end_age=None,  # Until end of plan
        expense_change=60_000,  # Annual cost
        notes="Assisted living facility"
    )
)
```

### Example 15: Disability Income

**Scenario**: Become disabled at 60, receive disability income until 65.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.disability(
        age=60,
        disability_income=45_000,  # Annual disability payment
        medical_expenses=15_000,  # Additional medical costs
        duration_years=5,  # Until Medicare at 65
        notes="Disability income until Medicare eligible"
    )
)
```

## Real Estate Transactions

### Example 16: Downsizing Home

**Scenario**: Sell large family home and buy smaller condo at age 75.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.downsizing(
        age=75,
        home_sale_proceeds=600_000,
        new_home_cost=350_000,
        expense_reduction=15_000,  # Lower maintenance, taxes
        notes="Downsize to condo"
    )
)
```

**Expected Impact**:
- One-time: +$250,000 to portfolio
- Annual: -$15,000 expenses
- Significant improvement in success probability

### Example 17: Rental Property Income

**Scenario**: Own rental property providing income throughout retirement.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.rental_income(
        start_age=62,
        end_age=None,  # Keep until end
        annual_income=30_000,  # Gross rent
        annual_expenses=12_000,  # Maintenance, taxes, insurance
        notes="Rental property - net $18k/year"
    )
)

# Sell rental property at age 80
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="Sell Rental Property",
        start_age=80,
        portfolio_contribution=400_000,
        income_change=-18_000,  # End rental income
        notes="Sell rental property"
    )
)
```

### Example 18: Relocation to Lower Cost Area

**Scenario**: Move to lower cost of living state at age 70.

**Setup**:
```python
scenario.life_events.append(
    LifeEventTemplates.relocation(
        age=70,
        moving_cost=25_000,
        expense_change=-20_000,  # Lower taxes, cost of living
        notes="Move to Florida - lower taxes and expenses"
    )
)
```

**Expected Impact**:
- One-time: -$25,000 (moving costs)
- Annual: -$20,000 expenses
- Payback period: ~1.25 years
- Significant long-term benefit

## Combined Scenarios

### Example 19: Comprehensive Early Retirement Plan

**Scenario**: Early retirement with multiple life events.

**Setup**:
```python
scenario = Scenario(
    name="Comprehensive Early Retirement",
    description="Early retirement with part-time work, downsizing, and inheritance",
    initial_portfolio=1_800_000,
    annual_expenses=85_000,
    retirement_age=60,
    plan_to_age=95
)

# Early retirement with reduced expenses
scenario.life_events.append(
    LifeEventTemplates.early_retirement(60, expense_reduction=15_000)
)

# Part-time consulting for 5 years
scenario.life_events.append(
    LifeEventTemplates.part_time_work(60, 65, annual_income=40_000)
)

# Expected inheritance at 70
scenario.life_events.append(
    LifeEventTemplates.inheritance(70, amount=400_000)
)

# Downsize home at 75
scenario.life_events.append(
    LifeEventTemplates.downsizing(
        75,
        home_sale_proceeds=500_000,
        new_home_cost=300_000,
        expense_reduction=12_000
    )
)

# Help grandchildren with college
scenario.life_events.append(
    LifeEventTemplates.college_funding(72, years=4, annual_cost=30_000)
)
```

**Timeline**:
- Age 60: Retire early, start part-time work
- Ages 60-65: Part-time income $40k/year
- Age 70: Receive $400k inheritance
- Ages 72-75: College funding $30k/year
- Age 75: Downsize home, net $200k

### Example 20: Conservative Planning with Contingencies

**Scenario**: Plan for potential adverse events.

**Setup**:
```python
scenario = Scenario(
    name="Conservative with Contingencies",
    description="Plan for potential medical and family needs",
    initial_portfolio=2_000_000,
    annual_expenses=80_000,
    retirement_age=65,
    plan_to_age=95
)

# Potential major medical at 75
scenario.life_events.append(
    LifeEventTemplates.major_medical(
        75,
        one_time_cost=100_000,
        ongoing_annual_cost=15_000,
        duration_years=5
    )
)

# Assisted living starting at 85
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="Assisted Living",
        start_age=85,
        expense_change=50_000,
        notes="Conservative assisted living estimate"
    )
)

# Emergency fund for family
scenario.life_events.append(
    LifeEventTemplates.custom(
        name="Family Emergency Fund",
        start_age=70,
        portfolio_withdrawal=50_000,
        notes="One-time family emergency assistance"
    )
)
```

## Best Practices

### 1. Start Simple
- Begin with one or two key events
- Add complexity gradually
- Compare with baseline frequently

### 2. Use Realistic Estimates
- Research actual costs (college, healthcare, etc.)
- Include inflation in long-term events
- Be conservative with income estimates

### 3. Model Uncertainty
- Create optimistic, expected, and pessimistic scenarios
- Test sensitivity to timing changes
- Consider probability of events occurring

### 4. Consider Tax Implications
- Large windfalls may push into higher brackets
- Time taxable events strategically
- Consider Roth conversions in low-income years

### 5. Review and Update
- Update as circumstances change
- Adjust for actual vs. planned events
- Re-run analysis periodically

## Common Pitfalls to Avoid

1. **Over-optimistic income estimates**: Part-time work may be harder to find than expected
2. **Under-estimating expenses**: Healthcare and long-term care costs often exceed estimates
3. **Ignoring inflation**: Long-term events need inflation adjustment
4. **Forgetting taxes**: Large windfalls and income have tax consequences
5. **Too many events**: Keep scenarios focused and realistic
6. **Ignoring conflicts**: Check for overlapping or incompatible events

## Conclusion

Life event modeling is a powerful tool for retirement planning. By modeling realistic events and their financial impacts, you can:

- Make more informed decisions
- Identify potential risks
- Optimize timing of major events
- Build confidence in your retirement plan

Remember: These are models, not predictions. Use them to explore possibilities and understand trade-offs, but remain flexible as life unfolds.

---

For more information:
- [User Guide](SCENARIO_PLANNING_USER_GUIDE.md)
- [API Documentation](SCENARIO_PLANNING_API.md)
- [Implementation Plan](SCENARIO_PLANNING_IMPLEMENTATION.md)

**Version**: 1.0 (April 2026)