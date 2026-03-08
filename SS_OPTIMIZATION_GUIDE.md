# Social Security Optimization Guide

## Overview

The Social Security Optimization module (`ss_optimization.py`) provides advanced claiming strategies and analysis tools to help maximize lifetime Social Security benefits for individuals and couples.

## Features

### 1. Spousal Benefit Optimization
Analyzes optimal claiming strategies when one spouse can receive benefits based on the other's earnings record.

**Key Rules:**
- Spouse can receive up to 50% of worker's Full Retirement Age (FRA) benefit
- Spousal benefit is reduced if claimed before FRA
- Worker must have claimed benefits for spouse to receive spousal benefits
- Spouse receives the greater of their own benefit or spousal benefit

**Example:**
```python
from ss_optimization import calculate_spousal_benefit

# Worker has $3,000/month at FRA, spouse has $1,200/month at FRA
spousal_benefit = calculate_spousal_benefit(
    worker_fra_benefit=3000,
    spouse_fra_benefit=1200,
    spouse_claiming_age=67,  # Claiming at FRA
    worker_claiming_age=67
)
# Result: $1,500/month (50% of worker's FRA benefit)
```

### 2. Break-Even Analysis
Compares different claiming ages to determine when delayed claiming "breaks even" with early claiming.

**Key Insights:**
- Shows the age at which total benefits from delayed claiming exceed early claiming
- Accounts for COLA adjustments
- Helps make informed decisions based on life expectancy

**Example:**
```python
from ss_optimization import calculate_break_even_age

analysis = calculate_break_even_age(
    fra_benefit=2500,
    early_age=62,
    late_age=70,
    cola_rate=0.02
)

print(f"Break-even age: {analysis.break_even_age}")
print(f"Monthly difference: ${analysis.monthly_difference:,.0f}")
print(f"Years to break even: {analysis.years_to_break_even}")
```

**Typical Break-Even Ages:**
- Age 62 vs 67 (FRA): Break-even around age 78-80
- Age 62 vs 70: Break-even around age 80-82
- Age 67 vs 70: Break-even around age 82-84

### 3. Survivor Benefit Planning
Calculates survivor benefits for widows/widowers.

**Key Rules:**
- Survivor can receive 100% of deceased's benefit
- Survivor receives the greater of their own benefit or survivor benefit
- Survivor benefits can be claimed as early as age 60 (age 50 if disabled)
- Different reduction schedule than retirement benefits

**Example:**
```python
from ss_optimization import calculate_survivor_benefit

survivor_benefit = calculate_survivor_benefit(
    deceased_benefit=3200,  # What deceased was receiving
    survivor_fra_benefit=1800,  # Survivor's own FRA benefit
    survivor_claiming_age=67,
    deceased_claiming_age=70
)
# Result: $3,200/month (100% of deceased's benefit)
```

**Strategy Considerations:**
- Higher-earning spouse should consider delaying to age 70 to maximize survivor benefit
- Survivor can switch from own benefit to survivor benefit (or vice versa)
- Coordinate claiming ages to optimize both current and survivor benefits

### 4. Earnings Test Impact
Models the impact of working while collecting Social Security before FRA.

**Key Rules:**
- **Under FRA**: $1 benefit reduction for every $2 earned over $22,320 (2024 limit)
- **Year reaching FRA**: $1 reduction for every $3 earned over $59,520 (2024 limit)
- **At/After FRA**: No earnings test applies

**Example:**
```python
from ss_optimization import calculate_earnings_test_impact

impact = calculate_earnings_test_impact(
    annual_earnings=50000,
    age=64,  # Under FRA
    monthly_benefit=2000
)

print(f"Benefit before: ${impact.monthly_benefit_before:,.0f}")
print(f"Annual reduction: ${impact.annual_reduction:,.0f}")
print(f"Benefit after: ${impact.monthly_benefit_after:,.0f}")
print(f"Months withheld: {impact.months_withheld}")
```

**Important Notes:**
- Benefits withheld due to earnings test are not lost forever
- At FRA, benefits are recalculated to give credit for months withheld
- Only earned income counts (wages, self-employment); investment income doesn't count

### 5. Net Present Value (NPV) Analysis
Calculates the present value of lifetime benefits using a discount rate.

**Purpose:**
- Accounts for time value of money
- Helps compare strategies on equal footing
- Useful for financial planning decisions

**Example:**
```python
from ss_optimization import calculate_net_present_value

npv = calculate_net_present_value(
    fra_benefit=2500,
    claiming_age=70,
    life_expectancy=87,
    discount_rate=0.03,  # 3% real discount rate
    cola_rate=0.02
)

print(f"NPV of lifetime benefits: ${npv:,.0f}")
```

### 6. Couple Optimization
Analyzes all claiming age combinations for married couples to find optimal strategy.

**Considerations:**
- Individual benefits for each spouse
- Spousal benefits
- Survivor benefits
- Longevity differences
- Net present value

**Example:**
```python
from ss_optimization import PersonProfile, optimize_couple_claiming_strategy

person1 = PersonProfile(
    name="John",
    birth_year=1960,
    fra_benefit=3000,
    gender='M',
    life_expectancy=84
)

person2 = PersonProfile(
    name="Jane",
    birth_year=1962,
    fra_benefit=2000,
    gender='F',
    life_expectancy=87
)

strategies = optimize_couple_claiming_strategy(person1, person2)

# Print top 3 strategies
for i, strategy in enumerate(strategies[:3], 1):
    print(f"\n{i}. {strategy.strategy_name}")
    print(f"   NPV: ${strategy.net_present_value:,.0f}")
    print(f"   Lifetime Total: ${strategy.total_lifetime_benefits:,.0f}")
    for note in strategy.notes:
        print(f"   - {note}")
```

## Common Claiming Strategies

### 1. Both Claim at 70 (Maximum Benefit)
**Best for:**
- Couples with longevity in family
- Higher earners wanting to maximize survivor benefit
- Those who can afford to delay

**Pros:**
- Maximum monthly benefit (32% higher than FRA)
- Highest survivor benefit
- Inflation-protected growth

**Cons:**
- Requires 8 years of other income sources
- May not break even if life expectancy is shorter

### 2. Lower Earner at 62, Higher Earner at 70
**Best for:**
- Couples needing some income now
- Maximizing survivor benefit for higher earner
- Age gap between spouses

**Pros:**
- Immediate income from lower earner
- Maximizes survivor benefit
- Balances current needs with future security

**Cons:**
- Lower earner's benefit permanently reduced
- May trigger earnings test if still working

### 3. Both Claim at FRA (67)
**Best for:**
- Average life expectancy
- Balanced approach
- Those retiring at FRA

**Pros:**
- No reduction in benefits
- Reasonable break-even age
- No earnings test

**Cons:**
- Misses delayed retirement credits
- Lower survivor benefit than waiting to 70

### 4. File and Suspend (Restricted - Check Current Rules)
**Note:** This strategy was largely eliminated by the Bipartisan Budget Act of 2015. Check current SSA rules.

## Claiming Age Decision Factors

### Consider Claiming Early (62-66) If:
- ✓ Poor health or shorter life expectancy
- ✓ Need income immediately
- ✓ No other retirement income sources
- ✓ Not working (to avoid earnings test)
- ✓ Lower earner in couple (to provide current income)

### Consider Delaying (68-70) If:
- ✓ Good health and longevity in family
- ✓ Still working and would face earnings test
- ✓ Have other income sources
- ✓ Higher earner wanting to maximize survivor benefit
- ✓ Want maximum inflation-protected income

### Consider FRA (67) If:
- ✓ Average life expectancy
- ✓ Retiring at FRA
- ✓ Want balanced approach
- ✓ Uncertain about longevity

## Integration with Retirement Planning

### Tax Considerations
- Up to 85% of Social Security benefits may be taxable
- Provisional income = AGI + Tax-exempt interest + 50% of SS benefits
- Coordinate with Roth conversions to manage tax brackets

### Medicare and IRMAA
- Social Security claiming age is independent of Medicare enrollment (age 65)
- Higher benefits may trigger IRMAA surcharges
- Consider IRMAA thresholds when planning claiming age

### Withdrawal Strategy
- Social Security provides inflation-protected base income
- Reduces need to withdraw from portfolio
- Allows more aggressive Roth conversions before claiming
- Coordinate with RMD planning

## API Reference

### Core Functions

#### `calculate_spousal_benefit()`
Calculate spousal benefit amount.

**Parameters:**
- `worker_fra_benefit` (float): Worker's monthly benefit at FRA
- `spouse_fra_benefit` (float): Spouse's own monthly benefit at FRA
- `spouse_claiming_age` (int): Age when spouse claims
- `worker_claiming_age` (int): Age when worker claims
- `fra` (int): Full Retirement Age (default: 67)

**Returns:** float - Monthly spousal benefit amount

#### `calculate_survivor_benefit()`
Calculate survivor benefit amount.

**Parameters:**
- `deceased_benefit` (float): Deceased's monthly benefit
- `survivor_fra_benefit` (float): Survivor's own FRA benefit
- `survivor_claiming_age` (int): Age when survivor claims
- `deceased_claiming_age` (int): Age when deceased claimed
- `fra` (int): Full Retirement Age (default: 67)

**Returns:** float - Monthly survivor benefit amount

#### `calculate_earnings_test_impact()`
Calculate impact of earnings test on benefits.

**Parameters:**
- `annual_earnings` (float): Annual earnings from work
- `age` (int): Current age
- `monthly_benefit` (float): Monthly SS benefit before test
- `fra` (int): Full Retirement Age (default: 67)

**Returns:** EarningsTestImpact - Detailed impact analysis

#### `calculate_break_even_age()`
Calculate break-even age between two claiming strategies.

**Parameters:**
- `fra_benefit` (float): Monthly benefit at FRA
- `early_age` (int): Earlier claiming age
- `late_age` (int): Later claiming age
- `cola_rate` (float): Annual COLA rate (default: 0.02)
- `fra` (int): Full Retirement Age (default: 67)

**Returns:** BreakEvenAnalysis - Detailed comparison

#### `calculate_lifetime_benefits()`
Calculate total lifetime benefits.

**Parameters:**
- `fra_benefit` (float): Monthly benefit at FRA
- `claiming_age` (int): Age when benefits are claimed
- `life_expectancy` (int): Expected age at death
- `cola_rate` (float): Annual COLA rate (default: 0.02)
- `fra` (int): Full Retirement Age (default: 67)

**Returns:** float - Total lifetime benefits

#### `calculate_net_present_value()`
Calculate NPV of lifetime benefits.

**Parameters:**
- `fra_benefit` (float): Monthly benefit at FRA
- `claiming_age` (int): Age when benefits are claimed
- `life_expectancy` (int): Expected age at death
- `discount_rate` (float): Real discount rate (default: 0.03)
- `cola_rate` (float): Annual COLA rate (default: 0.02)
- `fra` (int): Full Retirement Age (default: 67)

**Returns:** float - Net present value

#### `optimize_couple_claiming_strategy()`
Analyze optimal claiming strategies for a couple.

**Parameters:**
- `person1` (PersonProfile): First person's profile
- `person2` (PersonProfile): Second person's profile
- `cola_rate` (float): Annual COLA rate (default: 0.02)
- `discount_rate` (float): Discount rate (default: 0.03)
- `fra` (int): Full Retirement Age (default: 67)

**Returns:** List[ClaimingStrategy] - Strategies ranked by NPV

#### `generate_claiming_age_comparison()`
Generate comparison table of all claiming ages.

**Parameters:**
- `fra_benefit` (float): Monthly benefit at FRA
- `life_expectancy` (int): Expected age at death
- `cola_rate` (float): Annual COLA rate (default: 0.02)
- `discount_rate` (float): Discount rate (default: 0.03)
- `fra` (int): Full Retirement Age (default: 67)

**Returns:** pd.DataFrame - Comparison table

### Data Classes

#### `PersonProfile`
Profile for a person's Social Security benefits.

**Attributes:**
- `name` (str): Person's name
- `birth_year` (int): Year of birth
- `fra_benefit` (float): Monthly benefit at FRA
- `gender` (str): 'M' or 'F' for life expectancy defaults
- `life_expectancy` (int): Expected age at death
- `current_earnings` (float): Annual earnings if working

#### `ClaimingStrategy`
Represents a Social Security claiming strategy.

**Attributes:**
- `person1_claiming_age` (int): First person's claiming age
- `person2_claiming_age` (int): Second person's claiming age
- `strategy_name` (str): Description of strategy
- `total_lifetime_benefits` (float): Total lifetime benefits
- `net_present_value` (float): NPV of benefits
- `break_even_age` (Optional[int]): Break-even age if applicable
- `notes` (List[str]): Strategy notes and considerations

#### `BreakEvenAnalysis`
Break-even analysis results.

**Attributes:**
- `early_age` (int): Earlier claiming age
- `late_age` (int): Later claiming age
- `break_even_age` (int): Age when strategies break even
- `early_total` (float): Total benefits from early claiming
- `late_total` (float): Total benefits from late claiming
- `years_to_break_even` (int): Years after late claiming to break even
- `monthly_difference` (float): Monthly benefit difference

#### `EarningsTestImpact`
Impact of earnings test on benefits.

**Attributes:**
- `annual_earnings` (float): Annual earnings
- `age` (int): Current age
- `monthly_benefit_before` (float): Benefit before test
- `annual_reduction` (float): Annual reduction amount
- `monthly_benefit_after` (float): Benefit after test
- `months_withheld` (int): Number of months withheld
- `notes` (str): Detailed explanation

## Testing

See `test_ss_optimization.py` for comprehensive test cases covering:
- Spousal benefit calculations
- Survivor benefit calculations
- Break-even analysis
- Earnings test scenarios
- Couple optimization
- Edge cases and boundary conditions

## References

- [Social Security Administration - Retirement Benefits](https://www.ssa.gov/benefits/retirement/)
- [SSA - When to Start Receiving Benefits](https://www.ssa.gov/benefits/retirement/planner/agereduction.html)
- [SSA - Spousal Benefits](https://www.ssa.gov/benefits/retirement/planner/applying7.html)
- [SSA - Survivors Benefits](https://www.ssa.gov/benefits/survivors/)
- [SSA - Earnings Test](https://www.ssa.gov/benefits/retirement/planner/whileworking.html)

## Version History

- **v1.0** (2026-03-08): Initial implementation with core optimization features
  - Spousal benefit optimization
  - Break-even analysis
  - Survivor benefit planning
  - Earnings test modeling
  - NPV calculations
  - Couple optimization

## Future Enhancements

- Divorced spouse benefit calculations
- Disability benefit transitions
- Government Pension Offset (GPO) calculations
- Windfall Elimination Provision (WEP) adjustments
- Monte Carlo simulation for longevity uncertainty
- Tax-optimized claiming strategies
- Integration with healthcare cost planning