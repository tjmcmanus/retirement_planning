# SSI Calculator Integration with Withdrawal Strategy

## Overview

The SSI calculator has been successfully integrated into the withdrawal strategy module, specifically in **Stage 4 (Social Security)** and **Stage 5 (RMD)**. The system now dynamically calculates Social Security benefits based on [`config.py`](config.py:38) settings instead of relying on a static CSV file.

## What Changed

### 1. New Imports in [`withdrawal_strategy.py`](withdrawal_strategy.py:54)

```python
from ssi_calculator import (
    calculate_benefit_at_claiming_age,
    calculate_benefit_with_cola,
    DEFAULT_COLA_RATE
)
```

### 2. New Helper Function: [`calculate_ssi_benefits_dynamic()`](withdrawal_strategy.py:73)

This function calculates SSI benefits for a person in any given year:

```python
def calculate_ssi_benefits_dynamic(year: int, person_name: str, birth_year: int, 
                                   claiming_age: int, fra_benefit: float,
                                   cola_rate: float = DEFAULT_COLA_RATE) -> float:
    """
    Calculate SSI benefits for a person in a given year using dynamic formula.
    
    Returns:
        Monthly SSI benefit amount for the year (0 if not yet claiming)
    """
```

**Key Features:**
- Returns 0 if person hasn't reached claiming age
- Calculates initial benefit based on claiming age (62-70)
- Applies COLA adjustments for years since claiming
- Fully integrated with config.py settings

### 3. Updated [`calculate_multi_year_strategy()`](withdrawal_strategy.py:2691)

The main calculation method now:
1. Reads SSI settings from [`config.py`](config.py:38)
2. Calculates benefits dynamically using the formula
3. Falls back to CSV method if dynamic calculation fails
4. Logs detailed SSI information for each year

## How It Works

### Stage 4: Social Security (Pre-RMD)

In [`Stage4SocialSecurity.calculate_strategy()`](withdrawal_strategy.py:2128), SSI benefits are:
1. Added to cash at the beginning of the year
2. Included in taxable income calculations (85% taxable)
3. Used to reduce withdrawal needs from other accounts
4. Considered in IRMAA threshold calculations

**Code Flow:**
```python
# SSI benefits calculated in calculate_multi_year_strategy()
ss_benefits = (ss_primary + ss_spouse) * 12  # Annual amount

# Added to cash in Stage 4
balances_with_ss = PortfolioBalances(
    cash=balances.cash + ss_benefits,
    taxable=balances.taxable,
    traditional=balances.traditional,
    roth=balances.roth,
    daf=balances.daf
)

# Used in tax calculations
taxable_ss = ss_benefits * TAXABLE_SS_RATE  # 85% taxable
```

### Stage 5: RMD (Post-RMD Age)

In [`Stage5RMD.calculate_strategy()`](withdrawal_strategy.py:2380), SSI benefits are:
1. Combined with RMD amounts for total income
2. Used to determine additional withdrawal needs
3. Factored into limited Roth conversion opportunities
4. Included in IRMAA calculations

**Code Flow:**
```python
# Total income includes both SSI and RMD
taxable_ss = ss_benefits * TAXABLE_SS_RATE
total_income = taxable_ss + rmd_amount

# Determine if additional withdrawals needed
withdrawal_need = max(0, expenses + irmaa_penalty - ss_benefits - rmd_amount)
```

## Configuration

### Required Settings in [`config.py`](config.py:38)

```python
"social_security": {
    "person1_ssi_age": 70,        # Age when person 1 claims (62-70)
    "person1_ssi_amount": 4223,   # Monthly benefit at age 67 (FRA)
    "person2_ssi_age": 70,        # Age when person 2 claims (62-70)
    "person2_ssi_amount": 4223,   # Monthly benefit at age 67 (FRA)
}
```

**Important:** 
- `ssi_amount` should be the benefit **at age 67** (Full Retirement Age)
- The calculator automatically adjusts for early/delayed claiming
- Set to 0 if person doesn't have SSI benefits

### Optional Parameters

When calling `calculate_multi_year_strategy()`, you can override:

```python
strategy_df = engine.calculate_multi_year_strategy(
    start_year=2026,
    end_year=2050,
    initial_balances=balances,
    initial_expenses=50000,
    cola_rate=0.025,  # Override default 2% COLA
    # ... other parameters
)
```

## Formula Details

### 1. Initial Benefit Calculation

Based on claiming age relative to Full Retirement Age (67):

**Early Claiming (62-66):**
- First 36 months: 5/9 of 1% per month reduction
- Beyond 36 months: 5/12 of 1% per month reduction
- Example: Age 62 = ~30% reduction

**At FRA (67):**
- Full benefit amount (no adjustment)

**Delayed Claiming (68-70):**
- 8% increase per year
- Example: Age 70 = 24% increase

### 2. COLA Adjustments

After claiming, benefits increase annually:

```
Benefit_Year_N = Initial_Benefit × (1 + COLA_rate)^years_since_claiming
```

Default COLA rate: 2% (configurable)

## Example Calculation

**Scenario:**
- Person: Tom
- Birth Year: 1965
- Claiming Age: 70
- FRA Benefit: $4,223/month
- COLA Rate: 2%

**Results:**

| Year | Age | Calculation | Monthly Benefit |
|------|-----|-------------|-----------------|
| 2033 | 68  | Not claiming yet | $0 |
| 2035 | 70  | Initial at 70: $4,223 × 1.24 | $5,236 |
| 2036 | 71  | Year 1 COLA: $5,236 × 1.02 | $5,341 |
| 2040 | 75  | Year 5 COLA: $5,236 × 1.02^5 | $5,781 |

## Benefits of Dynamic Calculation

### Before (Static CSV):
- ❌ Manual updates required for different scenarios
- ❌ Hard to test "what-if" scenarios
- ❌ Separate CSV file to maintain
- ❌ Limited to pre-calculated ages

### After (Dynamic Formula):
- ✅ Automatically calculates for any claiming age (62-70)
- ✅ Easy to test different scenarios via config.py
- ✅ Integrated with withdrawal strategy
- ✅ Supports any FRA benefit amount
- ✅ Flexible COLA rate adjustments
- ✅ Falls back to CSV if needed

## Testing

### Run Integration Tests

```bash
python test_ssi_integration.py
```

This will:
1. Test dynamic SSI calculation
2. Verify config.py integration
3. Confirm withdrawal strategy integration

### Run Full Test Suite

```bash
python test_ssi_calculator.py
```

This validates the calculation formulas against CSV data.

## Logging

The integration includes detailed logging:

```
INFO - Year 2036 SSI Benefits: Person1=$5,341.00/mo, Person2=$5,341.00/mo, Annual=$128,184.00
INFO - Year 2036: Added SS benefits $128,184.00 to cash
DEBUG - SSI for Tom in 2036: Age 71, Claiming age 70, Monthly benefit $5,341.00
```

Set log level to see details:
```python
import logging
logging.basicConfig(level=logging.INFO)  # or DEBUG for more detail
```

## Fallback Mechanism

If dynamic calculation fails, the system automatically falls back to CSV-based method:

```python
try:
    # Try dynamic calculation
    ss_benefits = calculate_ssi_benefits_dynamic(...)
except Exception as e:
    logger.warning(f"Could not calculate dynamic SS benefits: {e}")
    # Fallback to CSV
    ss_benefits = get_monthly_benefit(year, person_name) * 12
```

This ensures the withdrawal strategy continues to work even if there are issues with the dynamic calculator.

## Migration Path

### Option 1: Use Dynamic Calculator Only
1. Update [`config.py`](config.py:38) with SSI settings
2. Run withdrawal strategy - benefits calculated automatically
3. No CSV file needed

### Option 2: Generate CSV from Config
1. Update [`config.py`](config.py:38) with SSI settings
2. Generate CSV: `python generate_ssi_schedule.py`
3. Use CSV as backup/reference

### Option 3: Hybrid Approach
1. Keep existing CSV for historical data
2. Use dynamic calculator for projections
3. System automatically uses whichever is available

## Troubleshooting

### Issue: SSI benefits are $0

**Check:**
1. Is `person1_ssi_amount` or `person2_ssi_amount` set in config.py?
2. Has the person reached their claiming age?
3. Check logs for calculation details

### Issue: Benefits don't match CSV

**Possible causes:**
1. Different COLA rate (CSV may use historical rates)
2. Rounding differences
3. CSV may have manual adjustments

**Solution:** Small differences (<$50/month) are normal due to rounding and COLA assumptions.

### Issue: Dynamic calculation fails

**The system will:**
1. Log a warning
2. Automatically fall back to CSV method
3. Continue processing

**Check logs for details:**
```
WARNING - Could not calculate dynamic SS benefits for 2036: [error details]
INFO - Using CSV fallback for SSI: $128,184.00
```

## Code References

- **SSI Calculator Module:** [`ssi_calculator.py`](ssi_calculator.py:1)
- **Helper Function:** [`calculate_ssi_benefits_dynamic()`](withdrawal_strategy.py:73)
- **Stage 4 Integration:** [`Stage4SocialSecurity.calculate_strategy()`](withdrawal_strategy.py:2128)
- **Stage 5 Integration:** [`Stage5RMD.calculate_strategy()`](withdrawal_strategy.py:2380)
- **Main Calculation:** [`calculate_multi_year_strategy()`](withdrawal_strategy.py:2639)
- **Configuration:** [`config.py`](config.py:38)

## Summary

The SSI calculator is now fully integrated into the withdrawal strategy, providing:
- ✅ Dynamic benefit calculations based on config.py
- ✅ Automatic COLA adjustments
- ✅ Support for any claiming age (62-70)
- ✅ Seamless integration with Stage 4 and Stage 5
- ✅ Detailed logging and error handling
- ✅ Fallback to CSV if needed

Simply update your config.py settings and run the withdrawal strategy - SSI benefits will be calculated automatically!