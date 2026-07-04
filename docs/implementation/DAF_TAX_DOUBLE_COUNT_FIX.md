# DAF Tax Calculation Double-Count Bug Fix

## Issue Discovered

When implementing DAF optimization, a critical bug was found in the tax calculation logic across all stages. The bug caused LTCG (Long-Term Capital Gains) to be double-taxed:

1. **Ordinary income tax** was calculated on the FULL taxable income (including LTCG)
2. **Capital gains tax** was then added on top, effectively taxing LTCG twice

### Example from 2026 with DAF:
- AGI: $600,809 (Roth conversion $525,755 + LTCG $75,054)
- Effective Deduction: $205,500 (std $32,200 + DAF excess $173,300)
- Taxable Income: $395,309
- **INCORRECT**: Tax on $395,309 ordinary rates = $80,070, plus LTCG tax $11,258 = **$91,328**
- **CORRECT**: Tax on $320,255 ordinary rates = $62,946, plus LTCG tax $11,258 = **$74,204**
- **Overcharge**: $17,124 (23% too high!)

## Root Cause

The tax calculation was using this pattern:
```python
taxable_income = agi - deduction
result = calculate_taxable_income(taxable_income, tax_brackets)  # WRONG: includes LTCG
federal_tax = result.total_tax
cg_tax = calculate_cap_gains(taxable_income - ltcg, cg_brackets, ltcg)
total_tax = federal_tax + cg_tax  # Double-counts LTCG!
```

## Fix Applied

Changed to correctly separate ordinary income from LTCG:
```python
taxable_income = agi - deduction
ordinary_income = taxable_income - ltcg  # NEW: Exclude LTCG
result = calculate_taxable_income(ordinary_income, tax_brackets)  # CORRECT: ordinary only
federal_tax = result.total_tax
cg_tax = calculate_cap_gains(ordinary_income, cg_brackets, ltcg)  # Use ordinary as base
total_tax = federal_tax + cg_tax  # No double-counting
```

## Locations Fixed

### Stage 3 (Early Retirement)
1. **Lines 4659-4667**: Preliminary tax calculation (before rebalancing)
2. **Lines 4800-4810**: Final tax recalculation (after rebalancing with brokerage LTCG)

### Stage 4 (Medicare)
1. **Lines 5123-5129**: Preliminary tax calculation

### Stage 5 (Social Security)
1. **Lines 5723-5731**: Preliminary tax calculation with conversion

## Impact

This fix significantly reduces the calculated tax burden in years with:
- Brokerage withdrawals (buffer replenishment)
- LTCG tax harvesting
- Any scenario where LTCG is included in AGI

The bug was particularly impactful in DAF years because:
1. DAF optimization increases Roth conversions
2. Larger conversions require more brokerage withdrawals for tax payment
3. Brokerage withdrawals generate LTCG
4. The double-counting made the tax appear much higher than it actually is

## Expected Results After Fix

For 2026 with DAF:
- **Before fix**: Total tax $91,328
- **After fix**: Total tax ~$74,204
- **Savings**: ~$17,124

This makes the DAF optimization even more attractive, as the true tax cost is significantly lower than previously calculated.

## Testing

The fix should be tested by:
1. Running the strategy with DAF enabled
2. Verifying federal tax matches manual calculations
3. Checking that ordinary income and LTCG are taxed at correct rates
4. Confirming total tax = ordinary tax + LTCG tax (no overlap)

## Related Files

- `strategy.py`: Main implementation (Stages 3, 4, 5)
- `DAF_OPTIMIZATION_IMPLEMENTATION.md`: Original DAF optimization documentation
- `DAF_TAX_CALCULATION_FIX.md`: Initial investigation of tax discrepancy