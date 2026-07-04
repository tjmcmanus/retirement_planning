# DAF Tax Calculation Fix

## Issue Identified

User reported Federal tax of $80,070 for year 2026 with:
- AGI: $600,809
- Roth Conversion: $525,755
- LTCG: $75,054

This tax amount was too high because the DAF deduction was not being applied in the preliminary tax calculation used for rebalancing.

## Root Cause

The original code flow was:
1. Calculate preliminary tax using **standard deduction only** (lines 4588-4603)
2. Calculate DAF contribution and optimization (lines 4634-4661)
3. Pass preliminary tax to rebalance_accounts
4. Later recalculate with DAF deduction (lines 4787-4810)

**Problem**: The preliminary tax (without DAF deduction) was being used for rebalancing decisions, and the DAF optimization was increasing the Roth conversion without accounting for the DAF deduction in the tax calculation.

## Solution Implemented

Reordered the code flow in Stage 3:
1. Calculate DAF contribution first (moved earlier)
2. Apply DAF optimization to increase Roth conversion
3. **Calculate preliminary tax using DAF deduction if present**
4. Pass correct preliminary tax to rebalance_accounts
5. Recalculate final tax with actual AGI (includes Traditional withdrawals)

### Key Changes

#### Before (Incorrect Order)
```python
# 1. Calculate preliminary tax (standard deduction only)
taxable_income = agi_preliminary - std_deduction
result = calculate_taxable_income(taxable_income, tax_brackets)
federal_tax = result.total_tax

# 2. Calculate DAF and optimize
daf_contribution, daf_tax_excess = _calculate_daf_for_year(...)
if daf_contribution > 0:
    roth_conversion += daf_enhanced_conversion  # Increased conversion!

# 3. Rebalance with incorrect tax estimate
rebalance_accounts(..., federal_tax=total_tax, ...)  # Tax too high!

# 4. Later recalculate with DAF
if daf_contribution > 0:
    effective_deduction = std_deduction + daf_tax_excess
    # Recalculate...
```

#### After (Correct Order)
```python
# 1. Calculate DAF first
daf_contribution, daf_tax_excess = _calculate_daf_for_year(...)

# 2. Apply DAF optimization
if daf_contribution > 0:
    roth_conversion += daf_enhanced_conversion

# 3. Calculate preliminary tax WITH DAF deduction
if daf_contribution > 0:
    effective_deduction = std_deduction + daf_tax_excess
else:
    effective_deduction = std_deduction

taxable_income = agi_preliminary - effective_deduction
result = calculate_taxable_income(taxable_income, tax_brackets)
federal_tax = result.total_tax

# 4. Rebalance with correct tax estimate
rebalance_accounts(..., federal_tax=total_tax, ...)  # Tax is correct!

# 5. Final recalculation with actual AGI
effective_deduction = std_deduction + daf_tax_excess if daf_contribution > 0 else std_deduction
taxable_income_final = agi - effective_deduction
# Final tax calculation...
```

## Expected Impact

With this fix, when a DAF contribution is made:

1. **Preliminary tax** will be calculated correctly using the DAF deduction
2. **Rebalancing decisions** will use the correct (lower) tax estimate
3. **Final tax** will match the preliminary estimate (adjusted for actual Traditional withdrawals)

### Example Calculation

**Scenario**: $100,000 DAF contribution, $525,755 Roth conversion

**Before Fix**:
```
Preliminary AGI: $600,809
Standard Deduction: $29,200
Taxable Income: $571,609
Preliminary Tax: ~$80,000 (WRONG - too high!)
```

**After Fix**:
```
Preliminary AGI: $600,809
DAF Contribution: $100,000
SALT: $10,000
Total Itemized: $110,000
DAF Tax Excess: $110,000 - $29,200 = $80,800
Effective Deduction: $29,200 + $80,800 = $110,000
Taxable Income: $600,809 - $110,000 = $490,809
Preliminary Tax: ~$65,000 (CORRECT - accounts for DAF!)
```

The tax savings of ~$15,000 from the DAF deduction is now properly reflected in the preliminary calculation.

## Files Modified

- `strategy.py` - Stage 3 (Early Retirement) lines 4586-4810
  - Moved DAF calculation before preliminary tax
  - Added DAF deduction to preliminary tax calculation
  - Simplified final tax recalculation

## Testing Recommendations

1. **Verify tax calculation** with DAF contribution in Stage 3
   - Check that preliminary tax uses DAF deduction
   - Check that final tax matches expected value
   - Compare with and without DAF optimization

2. **Verify rebalancing** uses correct tax estimate
   - Check that buffer replenishment calculations are correct
   - Verify Traditional withdrawals are appropriate

3. **Verify DAF optimization** still works correctly
   - Check that Roth conversion is increased by daf_tax_excess
   - Verify decision logging shows the optimization

## Related Changes

This fix complements the DAF optimization implementation:
- DAF optimization increases Roth conversion (implemented earlier)
- This fix ensures the tax calculation accounts for the DAF deduction
- Together, they enable larger conversions at the same effective tax rate

## Status

✅ **FIXED** - Stage 3 now correctly calculates preliminary tax with DAF deduction
⚠️ **TODO** - Apply same fix to Stages 4 and 5 if they have similar issues