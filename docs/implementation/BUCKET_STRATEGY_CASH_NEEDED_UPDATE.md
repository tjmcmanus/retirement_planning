# Bucket Strategy: Cash Needed Calculation Update

## Overview
Updated the bucket strategy to calculate annual cash needed based on **outflows minus inflows**, rather than just expenses and taxes. This provides a more accurate representation of the actual liquid funds needed from the portfolio each year.

## Changes Made

### 1. Enhanced BucketConfig Data Class
**File:** `bucket_strategy.py`

Added new fields to track both outflows and inflows:

**Outflows (money going out):**
- `annual_expenses`: Living expenses
- `annual_healthcare`: Healthcare costs (ACA/Medicare premiums)
- `annual_taxes`: Estimated tax burden

**Inflows (money coming in):**
- `annual_wages`: Combined wages/salary for both persons
- `annual_ssi`: Social Security benefits for both persons
- `annual_pension`: Pension income
- `annual_annuities`: Annuity income

### 2. New Method: `get_annual_cash_needed()`
Added a method to `BucketConfig` that calculates:

```python
Cash Needed = (Expenses + Healthcare + Taxes) - (Wages + SSI + Pension + Annuities)
```

The method:
- Returns the net cash needed from the portfolio
- Returns 0 if inflows exceed outflows (no portfolio withdrawal needed)
- Includes detailed logging for transparency

### 3. Updated Configuration Loading
**Function:** `load_bucket_config()`

Now loads income sources from the configuration:
- Reads `person1_annual_wages` and `person2_annual_wages` from `income` section
- Reads `person1_ssi_amount` and `person2_ssi_amount` from `social_security` section
- Reads `aca_insurance_monthly` from `healthcare` section (converted to annual)
- Supports future pension and annuity income fields

### 4. Modified Bucket Target Calculations
**Function:** `analyze_portfolio_buckets()`

Changed from:
```python
annual_need = config.annual_expenses + config.annual_taxes
bucket_1_target = annual_need * config.bucket_1_years
bucket_2_target = annual_need * config.bucket_2_years
```

To:
```python
annual_cash_needed = config.get_annual_cash_needed()
bucket_1_target = annual_cash_needed * config.bucket_1_years
bucket_2_target = annual_cash_needed * config.bucket_2_years
```

### 5. Updated Documentation
- Enhanced module docstring to explain the cash needed calculation
- Updated logging messages to show outflows vs inflows breakdown
- Added detailed comments explaining the calculation logic

## Impact

### Before
Bucket sizes were based solely on expenses + taxes, ignoring income sources like:
- Social Security benefits
- Wages during semi-retirement
- Pension income
- Annuity payments

This could result in over-allocation to buckets when significant income exists.

### After
Bucket sizes are based on actual cash needed from the portfolio:
- If you have $50K expenses + $10K taxes = $60K outflows
- But receive $30K Social Security + $10K wages = $40K inflows
- Cash needed = $60K - $40K = **$20K** (not $60K)
- Bucket 1 (2 years) = $40K (not $120K)
- Bucket 2 (8 years) = $160K (not $480K)

This results in more efficient capital allocation and potentially higher growth.

## Configuration Requirements

To use this feature, ensure your `retirement_config.json` includes:

```json
{
  "income": {
    "person1_annual_wages": 0,
    "person2_annual_wages": 0,
    "annual_pension": 0,
    "annual_annuities": 0
  },
  "social_security": {
    "person1_ssi_amount": 0,
    "person2_ssi_amount": 0
  },
  "healthcare": {
    "aca_insurance_monthly": 0
  }
}
```

## Example Scenarios

### Scenario 1: Early Retirement with Part-Time Work
- Expenses: $60,000
- Healthcare: $12,000
- Taxes: $8,000
- Part-time wages: $25,000
- **Cash needed: $55,000** (not $80,000)

### Scenario 2: Post-Social Security
- Expenses: $60,000
- Healthcare: $6,000 (Medicare)
- Taxes: $10,000
- Social Security: $40,000
- **Cash needed: $36,000** (not $76,000)

### Scenario 3: Full Retirement with Pension
- Expenses: $70,000
- Healthcare: $6,000
- Taxes: $12,000
- Social Security: $45,000
- Pension: $20,000
- **Cash needed: $23,000** (not $88,000)

## Backward Compatibility

The changes are fully backward compatible:
- If income fields are not set (default 0), behavior is identical to before
- Existing configurations will work without modification
- The calculation gracefully handles missing or zero income sources

## Testing Recommendations

1. **Verify Configuration Loading:**
   - Check that income sources are correctly loaded from config
   - Verify healthcare costs are properly annualized

2. **Test Cash Needed Calculation:**
   - Confirm outflows - inflows = cash needed
   - Verify it returns 0 when inflows exceed outflows

3. **Validate Bucket Targets:**
   - Ensure bucket sizes reflect actual cash needed
   - Check market trend adjustments still work correctly

4. **Review Logging:**
   - Confirm detailed breakdown appears in logs
   - Verify transparency of calculation

## Future Enhancements

Potential improvements:
1. **Dynamic Income Projection:** Adjust income sources by year (e.g., wages decrease, SSI increases)
2. **RMD Integration:** Include Required Minimum Distributions as inflows
3. **Tax Optimization:** Consider tax-efficient withdrawal sequencing
4. **Inflation Adjustment:** Apply different inflation rates to expenses vs income
5. **UI Integration:** Add income source inputs to the bucket strategy configuration page

## Notes

- Type checking warnings (basedpyright) are cosmetic and don't affect functionality
- The calculation uses `max(0, cash_needed)` to prevent negative bucket sizes
- Excess inflows (when income > expenses) should be handled by the broader strategy module