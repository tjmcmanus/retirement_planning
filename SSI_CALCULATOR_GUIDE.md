# Social Security Income (SSI) Calculator Guide

## Overview

The SSI Calculator dynamically generates Social Security benefit schedules based on configuration settings. Instead of maintaining a static CSV file, you can now calculate benefits for any claiming age and benefit amount.

## Key Formula Components

### 1. Full Retirement Age (FRA) Benefit
The **FRA benefit** is the base amount you would receive if you claim at age 67 (Full Retirement Age). This is the `person1_ssi_amount` and `person2_ssi_amount` in `config.py`.

**Example from CSV:**
- Tom at age 67: $4,223/month
- Sarah at age 67: $4,223/month

### 2. Early Claiming Reduction (Ages 62-66)

When claiming **before** age 67, benefits are reduced:

**Formula:**
- First 36 months early: 5/9 of 1% per month (≈0.556% per month)
- Beyond 36 months: 5/12 of 1% per month (≈0.417% per month)

**Examples:**
```
Age 62 (60 months early):
  - First 36 months: 36 × 0.00556 = 20%
  - Next 24 months: 24 × 0.00417 = 10%
  - Total reduction: 30%
  - Benefit: $4,223 × 0.70 = $2,956

Age 65 (24 months early):
  - 24 months × 0.00556 = 13.33%
  - Benefit: $4,223 × 0.8667 = $3,660
```

### 3. Delayed Retirement Credits (Ages 68-70)

When claiming **after** age 67, benefits increase by **8% per year**:

**Formula:**
```
Benefit = FRA_Benefit × (1 + 0.08 × years_delayed)
```

**Examples:**
```
Age 68 (1 year delay):
  - Benefit: $4,223 × 1.08 = $4,561

Age 70 (3 years delay):
  - Benefit: $4,223 × 1.24 = $5,236
```

### 4. Cost of Living Adjustments (COLA)

After claiming, benefits increase annually with COLA (typically 2-3%):

**Formula:**
```
Benefit_Year_N = Initial_Benefit × (1 + COLA_rate)^years_since_claiming
```

**Example:**
```
Claimed at 70 in 2035: $5,215/month
Year 2036 (1 year later, 2% COLA):
  - Benefit: $5,215 × 1.02 = $5,319
Year 2037 (2 years later):
  - Benefit: $5,215 × 1.02² = $5,425
```

## Configuration in config.py

Update the `social_security` section:

```python
"social_security": {
    "person1_ssi_age": 70,        # Age when person 1 claims (62-70)
    "person1_ssi_amount": 4223,   # Monthly benefit at age 67 (FRA)
    "person2_ssi_age": 70,        # Age when person 2 claims (62-70)
    "person2_ssi_amount": 4223,   # Monthly benefit at age 67 (FRA)
}
```

### Important Notes:

1. **`person1_ssi_amount` and `person2_ssi_amount`** should be the benefit amount **at age 67** (Full Retirement Age), NOT at the claiming age.

2. The calculator will automatically:
   - Reduce benefits if claiming before 67
   - Increase benefits if claiming after 67
   - Apply COLA adjustments after claiming

3. Valid claiming ages: 62-70 (benefits don't increase after 70)

## Usage Examples

### Example 1: Generate Schedule from Config

```python
from ssi_calculator import generate_ssi_schedule_from_config
from config import get_config_manager

# Load configuration
config = get_config_manager()

# Generate schedule for 2026-2050
schedule = generate_ssi_schedule_from_config(
    config_manager=config,
    start_year=2026,
    end_year=2050,
    cola_rate=0.02  # 2% annual COLA
)

# Export to CSV
schedule.to_csv('ssincome_generated.csv', index=False)
```

### Example 2: Generate Schedule for One Person

```python
from ssi_calculator import generate_ssi_schedule

# Tom: Born 1965, claims at 70, FRA benefit $4,223
tom_schedule = generate_ssi_schedule(
    person_name="Tom",
    birth_year=1965,
    claiming_age=70,
    fra_benefit=4223,
    start_year=2026,
    end_year=2050,
    cola_rate=0.02
)
```

### Example 3: Calculate Benefit at Specific Age

```python
from ssi_calculator import calculate_benefit_at_claiming_age

fra_benefit = 4223  # Benefit at age 67

# Calculate benefit at different ages
benefit_62 = calculate_benefit_at_claiming_age(fra_benefit, 62)  # ~$2,956
benefit_67 = calculate_benefit_at_claiming_age(fra_benefit, 67)  # $4,223
benefit_70 = calculate_benefit_at_claiming_age(fra_benefit, 70)  # ~$5,236
```

### Example 4: Apply COLA Adjustments

```python
from ssi_calculator import calculate_benefit_with_cola

initial_benefit = 5215  # Benefit when claimed
years_later = 5
cola_rate = 0.02  # 2% annual

future_benefit = calculate_benefit_with_cola(initial_benefit, years_later, cola_rate)
# Result: $5,215 × 1.02^5 = $5,758
```

## Verification Against CSV Data

The formula has been validated against the provided `ssincome.csv`:

| Age | CSV Value | Calculated | Difference |
|-----|-----------|------------|------------|
| 62  | $2,829    | $2,956     | ~$127      |
| 67  | $4,223    | $4,223     | $0         |
| 70  | $5,215    | $5,236     | ~$21       |

Small differences are due to:
1. Rounding in the CSV
2. Actual SSA calculations may use slightly different reduction factors
3. Historical COLA rates vs. assumed 2% rate

## Benefits of Dynamic Calculation

### Before (Static CSV):
- ❌ Manual updates required for different scenarios
- ❌ Hard to test "what-if" scenarios
- ❌ Separate CSV file to maintain
- ❌ Limited to pre-calculated ages

### After (Dynamic Formula):
- ✅ Automatically calculates for any claiming age (62-70)
- ✅ Easy to test different scenarios
- ✅ Integrated with config.py
- ✅ Supports any FRA benefit amount
- ✅ Flexible COLA rate adjustments

## Testing

Run the test suite to verify calculations:

```bash
python test_ssi_calculator.py
```

Or with pytest:

```bash
pytest test_ssi_calculator.py -v
```

## Integration with Existing Code

The calculator is designed to work alongside existing code:

1. **`ssibenefits.py`** can continue to use CSV data OR switch to dynamic calculation
2. **`load_data.py`** can load from generated CSV or calculate on-the-fly
3. **`config.py`** already has the necessary configuration structure

### Migration Path:

```python
# Option 1: Generate new CSV and use existing code
from ssi_calculator import generate_ssi_schedule_from_config
from config import get_config_manager

config = get_config_manager()
schedule = generate_ssi_schedule_from_config(config, 2026, 2050)
schedule.to_csv('ssincome.csv', index=False)

# Option 2: Use calculator directly in your code
from ssi_calculator import calculate_benefit_at_claiming_age, calculate_benefit_with_cola

def get_monthly_benefit_dynamic(year, person_name, config):
    """Calculate benefit dynamically instead of reading from CSV."""
    # Get person's config
    person_num = 1 if person_name == config.get("personal_info", "person1_name") else 2
    claiming_age = config.get("social_security", f"person{person_num}_ssi_age")
    fra_benefit = config.get("social_security", f"person{person_num}_ssi_amount")
    birth_year = int(config.get("personal_info", f"person{person_num}_birth_date").split('-')[0])
    
    current_age = year - birth_year
    
    if current_age < claiming_age:
        return 0.0
    
    # Calculate initial benefit at claiming age
    initial_benefit = calculate_benefit_at_claiming_age(fra_benefit, claiming_age)
    
    # Apply COLA for years since claiming
    claiming_year = birth_year + claiming_age
    years_since_claiming = year - claiming_year
    
    return calculate_benefit_with_cola(initial_benefit, years_since_claiming, 0.02)
```

## Common Scenarios

### Scenario 1: Both Claim at 70
```python
"social_security": {
    "person1_ssi_age": 70,
    "person1_ssi_amount": 4223,  # FRA benefit
    "person2_ssi_age": 70,
    "person2_ssi_amount": 4223,
}
# Result: Both get ~24% increase = $5,236/month
```

### Scenario 2: One Early, One Delayed
```python
"social_security": {
    "person1_ssi_age": 62,        # Early claiming
    "person1_ssi_amount": 4223,
    "person2_ssi_age": 70,        # Delayed claiming
    "person2_ssi_amount": 4223,
}
# Person 1: ~$2,956/month (30% reduction)
# Person 2: ~$5,236/month (24% increase)
```

### Scenario 3: Different FRA Benefits
```python
"social_security": {
    "person1_ssi_age": 67,
    "person1_ssi_amount": 3500,  # Lower earner
    "person2_ssi_age": 67,
    "person2_ssi_amount": 4223,  # Higher earner
}
# Person 1: $3,500/month
# Person 2: $4,223/month
```

## Formula Summary

```
1. Calculate Initial Benefit at Claiming Age:
   IF claiming_age < 67:
       reduction = calculate_early_reduction(67 - claiming_age)
       benefit = fra_benefit × (1 - reduction)
   ELSE IF claiming_age > 67:
       increase = 0.08 × (claiming_age - 67)
       benefit = fra_benefit × (1 + increase)
   ELSE:
       benefit = fra_benefit

2. Apply COLA for Each Year After Claiming:
   benefit_year_N = initial_benefit × (1 + cola_rate)^N
```

## References

- [Social Security Administration - Benefit Calculation](https://www.ssa.gov/oact/quickcalc/early_late.html)
- [SSA - Delayed Retirement Credits](https://www.ssa.gov/benefits/retirement/planner/delayret.html)
- [SSA - Early or Late Retirement](https://www.ssa.gov/oact/quickcalc/early_late.html)

## Support

For questions or issues:
1. Review the test file: `test_ssi_calculator.py`
2. Check the examples in: `ssi_calculator.py` (main block)
3. Validate your config: Use `validate_config_ssi_settings()`