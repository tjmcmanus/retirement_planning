# Age-Based Expense Adjustment Implementation Guide

## Overview

The retirement planning application now includes age-based adjustments for both discretionary expenses and healthcare costs that reflect real-world spending patterns throughout retirement. Research shows that retirees' spending follows predictable patterns:

- **Discretionary spending** (travel, dining, hobbies) decreases with age
- **Healthcare costs** (out-of-pocket medical expenses) increase with age

These inverse patterns are now automatically applied to create more realistic retirement projections.

## Spending Patterns by Age

### Discretionary Expenses (Inverse Pattern)

Based on retirement spending research, the application applies the following adjustments:

| Age Range | Discretionary Expenses | Healthcare Costs (OOP) | Net Effect |
|-----------|----------------------|----------------------|------------|
| **60-69** | **+5%** | **-5%** | Higher discretionary, lower medical |
| **70-79** | **Baseline (0%)** | **Baseline (0%)** | Stable phase |
| **80-89** | **-15%** | **+15%** | Lower discretionary, higher medical |
| **90+** | **-30%** | **+30%** | Much lower discretionary, much higher medical |

### Discretionary Expenses Rationale

| Age Range | Adjustment | Rationale |
|-----------|-----------|-----------|
| **60-69** | **+5%** | Higher spending: travel, activities, home improvements, helping adult children |
| **70-79** | **Baseline** | Expenses as declared - stable spending phase |
| **80-89** | **-15%** | Reduced spending: less travel, fewer activities, downsizing lifestyle |
| **90+** | **-30%** | Significantly reduced: limited mobility, simpler lifestyle |

### Healthcare Costs Rationale (Inverse Pattern)

| Age Range | Adjustment | Rationale |
|-----------|-----------|-----------|
| **60-69** | **-5%** | Generally healthier, fewer medical needs |
| **70-79** | **Baseline** | Expected healthcare costs as planned |
| **80-89** | **+15%** | Increased medical needs, more frequent care |
| **90+** | **+30%** | Significantly higher: chronic conditions, intensive care needs |

### Example Calculations

**Discretionary Expenses** (if you declare $50,000):
- **Age 65**: $52,500 (50,000 × 1.05)
- **Age 75**: $50,000 (50,000 × 1.00)
- **Age 85**: $42,500 (50,000 × 0.85)
- **Age 95**: $35,000 (50,000 × 0.70)

**Healthcare Out-of-Pocket Costs** (if baseline is $10,000):
- **Age 65**: $9,500 (10,000 × 0.95)
- **Age 75**: $10,000 (10,000 × 1.00)
- **Age 85**: $11,500 (10,000 × 1.15)
- **Age 95**: $13,000 (10,000 × 1.30)

**Combined Effect** (Total annual costs):
- **Age 65**: $62,000 ($52,500 + $9,500)
- **Age 75**: $60,000 ($50,000 + $10,000)
- **Age 85**: $54,000 ($42,500 + $11,500)
- **Age 95**: $48,000 ($35,000 + $13,000)

Note: Despite healthcare increasing, total costs still decline due to larger decrease in discretionary spending.

## Implementation Details

### 1. Core Functions (calculations.py)

#### Discretionary Expenses

##### `calculate_age_adjusted_expenses(base_expenses, age)`

Calculates age-adjusted expenses for a single person based on their age.

```python
def calculate_age_adjusted_expenses(base_expenses: float, age: int) -> float:
    """
    Calculate age-adjusted annual expenses based on spending patterns by age.
    
    Args:
        base_expenses: Base annual expenses as declared in configuration
        age: Current age of the person
        
    Returns:
        float: Age-adjusted annual expenses
    """
```

**Age Brackets:**
- Under 60: Baseline (1.0x)
- 60-69: +5% (1.05x)
- 70-79: Baseline (1.0x)
- 80-89: -15% (0.85x)
- 90+: -30% (0.70x)

#### `calculate_household_age_adjusted_expenses(base_expenses, person1_age, person2_age, is_single)`

Calculates age-adjusted expenses for a household (single or couple).

```python
def calculate_household_age_adjusted_expenses(
    base_expenses: float,
    person1_age: int,
    person2_age: int | None = None,
    is_single: bool = False
) -> float:
    """
    Calculate age-adjusted expenses for a household (single or couple).
    
    For couples, uses the younger person's age as the primary driver of spending,
    since household expenses tend to remain higher as long as one person is active.
    """
```

**Couple Logic:**
- Uses the **younger person's age** to determine the adjustment factor
- Rationale: Household spending remains elevated as long as one person is active
- Example: If ages are 75 and 85, uses age 75 (baseline spending)

### 2. Integration with Withdrawal Strategy (strategy.py)

The age-based adjustments are integrated into the main withdrawal strategy engine at line ~5130:

```python
# Calculate age-adjusted expenses for next year
from calculations import calculate_household_age_adjusted_expenses
from config import get_value_with_session_override

# Get base expenses from config (without inflation)

#### Healthcare Costs (Inverse Pattern)

##### `calculate_age_adjusted_healthcare_costs(base_healthcare_cost, age)`

Calculates age-adjusted out-of-pocket healthcare costs for a single person based on their age.

```python
def calculate_age_adjusted_healthcare_costs(base_healthcare_cost: float, age: int) -> float:
    """
    Calculate age-adjusted healthcare out-of-pocket costs based on age.
    
    Healthcare costs increase with age (inverse of discretionary spending):
    - 60s: -5% (generally healthier)
    - 70s: Baseline (expected costs)
    - 80s: +15% (increased medical needs)
    - 90s: +30% (significantly higher needs)
    
    Args:
        base_healthcare_cost: Base annual out-of-pocket healthcare costs
        age: Current age of the person
        
    Returns:
        float: Age-adjusted annual healthcare costs
    """
```

**Age Brackets:**
- Under 60: Baseline (1.0x)
- 60-69: -5% (0.95x) - Generally healthier
- 70-79: Baseline (1.0x) - Expected costs
- 80-89: +15% (1.15x) - Increased needs
- 90+: +30% (1.30x) - Significantly higher needs

##### `calculate_household_age_adjusted_healthcare_costs(base_healthcare_cost, person1_age, person2_age, is_single)`

Calculates age-adjusted healthcare costs for a household (single or couple).

```python
def calculate_household_age_adjusted_healthcare_costs(
    base_healthcare_cost: float,
    person1_age: int,
    person2_age: int | None = None,
    is_single: bool = False
) -> float:
    """
    Calculate age-adjusted healthcare costs for a household.
    
    For couples, uses the OLDER person's age as the primary driver,
    since healthcare expenses are typically driven by the person with
    greater medical needs (usually the older person).
    """
```

**Couple Logic:**
- Uses the **older person's age** to determine the adjustment factor
- Rationale: Healthcare costs are driven by the person with greater medical needs
- Example: If ages are 75 and 85, uses age 85 (+15% adjustment)

**Key Difference from Discretionary Expenses:**
- Discretionary expenses use **younger** person's age (household stays active longer)
- Healthcare costs use **older** person's age (medical needs drive costs)

base_expenses = float(get_value_with_session_override(
    'financial_assumptions', 'expected_annual_expenses', 'EXPENSE',
    kwargs.get('initial_expenses', 120000)
))

# Check if single person mode
is_single = config_mgr.get("personal_info", "is_single_person", False)

# Calculate next year's ages
next_year_age_primary = age_primary + 1
next_year_age_spouse = age_spouse + 1

# Apply age-based adjustment to base expenses
age_adjusted_base = calculate_household_age_adjusted_expenses(
    base_expenses,
    next_year_age_primary,
    next_year_age_spouse if not is_single else None,
    is_single
)

# Apply inflation to the age-adjusted base
years_from_start = (year + 1) - start_year
inflation_multiplier = (1 + expense_inflation_rate) ** years_from_start
expenses = age_adjusted_base * inflation_multiplier
```

### 3. Calculation Flow

For each year in the retirement projection:

1. **Get Base Expenses**: Read declared annual expenses from configuration
2. **Calculate Ages**: Determine current ages of person1 and person2
3. **Apply Age Adjustment**: Use appropriate multiplier based on age(s)
4. **Apply Inflation**: Compound inflation from start year to current year
5. **Use in Strategy**: Pass adjusted expenses to withdrawal strategy calculation

**Formula:**

### 3. Healthcare Cost Integration (strategy.py)

The age-based healthcare adjustments are integrated into the `calculate_total_healthcare_costs()` function at line ~1474:

```python
# --- Out-of-pocket expenses -------------------------------------------
# Falls back to OOP_COST_DEFAULT ("average") for unrecognised health_status values.
base_oop_cost: int = OOP_COSTS_BY_HEALTH_STATUS.get(health_status, OOP_COST_DEFAULT)

# Apply age-based adjustment to out-of-pocket costs
# Healthcare costs increase with age (inverse of discretionary spending)
from calculations import calculate_household_age_adjusted_healthcare_costs
from config import get_config_manager

config_mgr = get_config_manager()
is_single = config_mgr.get("personal_info", "is_single_person", False)

oop_cost = calculate_household_age_adjusted_healthcare_costs(
    float(base_oop_cost),
    age_primary,
    age_spouse if age_spouse > 0 else None,
    is_single
)
```

**What Gets Adjusted:**
- Out-of-pocket healthcare costs (OOP) based on health_status
- Does NOT adjust Medicare premiums, IRMAA surcharges, or insurance premiums
- Only adjusts the variable out-of-pocket medical expenses

**Health Status Base Costs:**
- Healthy: Lower baseline OOP costs
- Average: Standard OOP costs  
- Chronic: Higher baseline OOP costs

Then age adjustment is applied on top of the health status baseline.

```
Final Expenses = Base Expenses × Age Adjustment Factor × (1 + Inflation Rate)^Years
```

## Impact on Retirement Strategy

### 1. Cash Reserve Requirements

The age-based adjustments affect cash reserve calculations:

- **Early Retirement (60s)**: Higher expenses mean larger cash reserves needed
- **Mid Retirement (70s)**: Baseline expenses, standard cash reserves
- **Late Retirement (80s+)**: Lower expenses mean smaller cash reserves needed

### 2. Withdrawal Amounts

Withdrawal strategies adjust automatically:

- **60s**: Larger withdrawals to cover higher spending
- **70s**: Baseline withdrawals
- **80s+**: Reduced withdrawals as spending decreases

### 3. Portfolio Longevity

Age-based adjustments improve portfolio sustainability:

- **Reduced late-life spending** extends portfolio longevity
- **More realistic projections** vs. constant inflation-adjusted expenses
- **Better alignment** with actual retirement spending patterns

### 4. Roth Conversion Strategy

Lower expenses in later years affect conversion decisions:

- **More conversion headroom** in 80s+ when expenses are lower
- **Tax bracket management** easier with reduced spending needs
- **IRMAA optimization** more achievable with lower required withdrawals

### 5. Social Security Claiming

Age-based expenses influence optimal claiming age:

- **Delaying SS** more feasible when 80s+ expenses are lower
- **Bridge years** (60s) require more portfolio support due to higher expenses
- **Breakeven analysis** improved with realistic spending curve

## Single vs. Couple Considerations

### Single Person

- Uses individual's age directly
- Simpler calculation
- Spending adjustments apply immediately at each age threshold

### Couple

- Uses **younger person's age** for household expenses
- Rationale: Household remains more active with younger spouse
- Example scenarios:

| Person 1 Age | Person 2 Age | Age Used | Adjustment | Rationale |
|--------------|--------------|----------|------------|-----------|
| 65 | 67 | 65 | +5% | Both in 60s, use younger |
| 75 | 68 | 68 | +5% | Younger still in 60s |
| 75 | 77 | 75 | 0% | Both in 70s, use younger |
| 85 | 75 | 75 | 0% | Younger in 70s keeps spending higher |
| 85 | 87 | 85 | -15% | Both in 80s, use younger |

## Configuration

### User-Declared Expenses

Users declare their expected annual expenses in the Configuration page under "Financial Assumptions":

- **Expected Annual Expenses**: Base amount (e.g., $50,000)
- **Expense Inflation Rate**: Annual increase rate (e.g., 3%)

The application then:
1. Applies age-based adjustments automatically
2. Compounds inflation from start year
3. Uses adjusted amounts in all calculations

### No Additional Settings Required

Age-based adjustments are applied automatically based on:
- Person ages (calculated from birth dates)
- Single person checkbox status
- Declared base expenses

## Research Basis

The age-based spending pattern is supported by multiple retirement studies:

1. **"The Retirement Spending Smile"** - Research shows spending decreases in real terms throughout retirement, with the steepest declines after age 75.

2. **"Go-Go, Slow-Go, No-Go Years"** - Common framework describing retirement phases:
   - **Go-Go (60s)**: Active travel and activities (+5%)
   - **Slow-Go (70s)**: Moderate activity (baseline)
   - **No-Go (80s+)**: Limited activity (-15% to -30%)

3. **Healthcare Offset**: While healthcare costs increase with age, they don't fully offset the decline in discretionary spending (travel, dining, entertainment, hobbies).

## Logging and Debugging

The implementation includes detailed logging:

```python
logger.debug(
    f"Year {year+1} expense calculation: "
    f"base=${base_expenses:,.2f}, "
    f"age_adjusted=${age_adjusted_base:,.2f} "
    f"(ages {next_year_age_primary}/{next_year_age_spouse}), "
    f"inflation_mult={inflation_multiplier:.4f}, "
    f"final=${expenses:,.2f}"
)
```

Enable debug logging to see expense calculations:
```bash
export LOG_LEVEL=DEBUG
python planning_app.py
```

## Examples

### Example 1: Single Person

**Configuration:**
- Base expenses: $60,000
- Birth year: 1960
- Inflation: 3%
- Start year: 2025

**Expense Progression:**

| Year | Age | Base | Age Adj | Inflation | Final Expenses |
|------|-----|------|---------|-----------|----------------|
| 2025 | 65 | $60,000 | $63,000 | 1.000 | $63,000 |
| 2030 | 70 | $60,000 | $60,000 | 1.159 | $69,540 |
| 2035 | 75 | $60,000 | $60,000 | 1.344 | $80,640 |
| 2040 | 80 | $60,000 | $51,000 | 1.558 | $79,458 |
| 2045 | 85 | $60,000 | $51,000 | 1.806 | $92,106 |
| 2050 | 90 | $60,000 | $42,000 | 2.094 | $87,948 |

**Note**: Expenses peak in mid-70s, then decline despite inflation.

### Example 2: Couple with Age Gap

**Configuration:**
- Base expenses: $80,000
- Person 1 birth: 1960 (older)
- Person 2 birth: 1965 (younger)
- Inflation: 2.5%
- Start year: 2025

**Expense Progression:**

| Year | P1 Age | P2 Age | Age Used | Age Adj | Inflation | Final Expenses |
|------|--------|--------|----------|---------|-----------|----------------|
| 2025 | 65 | 60 | 60 | $80,000 | 1.000 | $80,000 |
| 2030 | 70 | 65 | 65 | $84,000 | 1.131 | $95,004 |
| 2035 | 75 | 70 | 70 | $80,000 | 1.280 | $102,400 |
| 2040 | 80 | 75 | 75 | $80,000 | 1.448 | $115,840 |
| 2045 | 85 | 80 | 80 | $68,000 | 1.639 | $111,452 |
| 2050 | 90 | 85 | 85 | $68,000 | 1.853 | $126,004 |

**Note**: Younger spouse keeps household expenses elevated longer.

## Testing

Test the age-based expense calculations:

```python
from calculations import calculate_age_adjusted_expenses, calculate_household_age_adjusted_expenses

# Test single person
assert calculate_age_adjusted_expenses(50000, 65) == 52500  # 60s: +5%
assert calculate_age_adjusted_expenses(50000, 75) == 50000  # 70s: baseline
assert calculate_age_adjusted_expenses(50000, 85) == 42500  # 80s: -15%
assert calculate_age_adjusted_expenses(50000, 95) == 35000  # 90s: -30%

# Test couple (uses younger age)
assert calculate_household_age_adjusted_expenses(50000, 85, 75, False) == 50000  # Younger in 70s
assert calculate_household_age_adjusted_expenses(50000, 85, 82, False) == 42500  # Both in 80s
```

## Future Enhancements

Potential improvements:

1. **Customizable Age Brackets**: Allow users to adjust the age thresholds
2. **Customizable Adjustment Factors**: Let users modify the +5%/-15%/-30% values
3. **Healthcare Expense Separation**: Track healthcare separately from discretionary spending
4. **Lifestyle Profiles**: Offer preset profiles (active, moderate, conservative)
5. **Regional Adjustments**: Account for geographic cost-of-living changes
6. **Longevity Planning**: Adjust for expected lifespan variations

## Summary

The age-based expense adjustment feature provides:

✅ **More realistic projections** aligned with actual retirement spending patterns  
✅ **Automatic adjustments** based on age without user intervention  
✅ **Couple-aware logic** using younger spouse's age for household expenses  
✅ **Integration with all strategies** including Roth conversions, RMDs, and withdrawals  
✅ **Improved portfolio longevity** through reduced late-life spending assumptions  
✅ **Better tax planning** with more accurate expense forecasts  

This creates more accurate and achievable retirement plans that reflect how retirees actually spend money throughout their retirement years.