# Brokerage Buffer Replenishment Fix

## Issue Summary

The brokerage buffer was not being replenished when it fell below target in years 2032-2038, causing it to remain at $138K (2032-2033) and then $38K (2034-2038) instead of the target $205K.

## Root Cause

In `strategy.py`, the `rebalance_accounts()` function has two routing paths:

1. **Normal routing** (lines 3182-3203): 
   - Replenishes cash buffer via `replenish_cash_buffer()`
   - Then replenishes brokerage buffer via `replenish_brokerage_buffer()`

2. **Optimized routing** (lines 3097-3180):
   - Used when brokerage cannot cover both cash needs AND maintain its buffer
   - Routes Traditional directly to Cash to avoid double taxation
   - **BUG**: Set `brokerage_replenishment = 0.0` at line 3180, completely skipping brokerage replenishment

### The Problem

The optimized routing logic at line 3107 calculates:
```python
brokerage_can_provide = max(0, balances.taxable - brokerage_target)
```

When brokerage is already below target (e.g., $138K vs $205K target):
- `brokerage_can_provide = 0` (can't provide anything while maintaining buffer)
- Optimized routing handles immediate cash needs
- But then sets `brokerage_replenishment = 0.0` without checking if brokerage needs replenishment
- **Result**: Brokerage never gets replenished back to target once it falls below

### Example from Screenshot Data

**Year 2032:**
- Brokerage starts at: $138,245 (already $67K below target)
- Cash needs: $64,139 (after expenses)
- Optimized routing triggers because brokerage can't cover both
- Traditional → Cash: $64,139 (handles cash need)
- Traditional → Brokerage: **$0** (BUG - should be $67,315)
- Brokerage ends at: $138,245 (still below target)

This pattern repeated for years 2032-2038, preventing brokerage from ever recovering.

## The Fix

Modified `rebalance_accounts()` at lines 3174-3191 to add a check after optimized routing:

```python
# After handling cash needs with optimized routing, check if brokerage still needs replenishment
# This handles the case where brokerage was already below target before this year
current_brokerage_deficit = max(0, brokerage_target - balances.taxable)
if current_brokerage_deficit > _BUFFER_REPLENISHMENT_MIN_DEFICIT:
    logger.info(f"Year {year}: Brokerage still below target after optimized routing, replenishing...")
    balances, brokerage_txns, brok_dl = replenish_brokerage_buffer(
        balances, expenses, age_primary, year, brokerage_account
    )
    transactions['traditional_to_brokerage'] = brokerage_txns['traditional_to_brokerage']
    transactions['brokerage_replenishment'] = brokerage_txns['brokerage_replenishment']
    dl.brokerage_replenishment.extend(brok_dl.brokerage_replenishment)
else:
    # Brokerage maintained its buffer through optimized routing
    transactions['traditional_to_brokerage'] = 0.0
    transactions['brokerage_replenishment'] = 0.0
```

### How It Works

1. **Optimized routing handles immediate cash needs** (lines 3097-3173)
   - Routes Traditional directly to Cash to avoid double taxation
   - Prevents brokerage from falling further below target

2. **New check replenishes brokerage if still below target** (lines 3174-3191)
   - After cash needs are met, checks if brokerage is still below target
   - If yes, calls `replenish_brokerage_buffer()` to restore it
   - Uses Traditional → Brokerage transfers (capped at 30% per year)

3. **Result**: Both tax optimization AND buffer maintenance
   - Optimized routing still avoids double taxation on new transfers
   - Brokerage buffer gets replenished back to target over time

## Test Results

### Before Fix
```
Year 2032:
  Starting Brokerage: $138,245 (below target)
  Traditional → Cash: $64,139 (optimized routing)
  Traditional → Brokerage: $0 (BUG)
  Ending Brokerage: $138,245 (still below target)
```

### After Fix
```
Year 2032:
  Starting Brokerage: $138,245 (below target)
  Traditional → Cash: $64,139 (optimized routing)
  Traditional → Brokerage: $67,315 (FIX - replenishment)
  Ending Brokerage: $205,560 (at target ✓)
```

## Impact

### Positive
- ✓ Brokerage buffer properly maintained at target levels
- ✓ Tax optimization still works (avoids double taxation)
- ✓ Both buffers (cash and brokerage) reach their targets
- ✓ Transparent decision logging explains all transfers

### Considerations
- Traditional withdrawals increase in years where brokerage needs replenishment
- Capped at 30% of Traditional balance per year to limit tax impact
- May take multiple years to fully replenish if deficit is large

## Files Modified

- `strategy.py` (lines 3174-3191): Added brokerage replenishment check after optimized routing

## Test Files

- `test_fix_brokerage_replenishment.py`: Validates the fix with scenario matching screenshot data
- `analyze_screenshot_data.py`: Analyzes the original issue from screenshot data
- `test_full_rebalance.py`: Tests full rebalance flow

## Related Documentation

- `BUFFER_REPLENISHMENT_OPTIMIZATION.md`: Documents the optimized routing strategy
- `COST_BASIS_TRACKING_GUIDE.md`: Explains cost basis tracking for brokerage transfers

## Verification

Run the test to verify the fix:
```bash
python3 test_fix_brokerage_replenishment.py
```

Expected output:
```
✓✓✓ SUCCESS! Both buffers replenished to target
  Cash: $205,560 (at target)
  Brokerage: $205,560 (at target - replenished from $138,245)
```

---

**Fix implemented by:** Bob  
**Date:** 2026-03-16  
**Issue:** Buffer replenishment not working as designed