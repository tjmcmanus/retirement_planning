# Stage 5 and Stage 6 LTCG Calculation Fix

## Problem Statement

Stage 5 (Social Security) and Stage 6 (RMD) were calculating Long-Term Capital Gains (LTCG) from brokerage buffer replenishment incorrectly, leading to inflated tax calculations.

### Issues Identified

1. **Stage 5 (Social Security)**:
   - Used **estimated** LTCG based on cost basis ratio instead of **actual** LTCG
   - Line 5700-5710: Calculated `brokerage_withdrawal_ltcg` using ratio estimation
   - This ignored the actual LTCG already calculated in `rebalance_accounts()`

2. **Stage 6 (RMD)**:
   - Performed a **second withdrawal** from brokerage account to calculate LTCG
   - Line 6249-6260: Called `brokerage_account.withdraw_fifo()` again
   - This double-counted the withdrawal and calculated incorrect LTCG
   - The actual LTCG was already calculated in `rebalance_accounts()`

### Root Cause

Both stages were not using the `brokerage_ltcg` value that was already calculated and stored in the `transactions` dictionary by `rebalance_accounts()`. This led to:

- **Inaccurate LTCG calculations**: Using estimates or double-withdrawals instead of actual FIFO-based LTCG
- **Inflated AGI**: Higher LTCG values led to higher Adjusted Gross Income
- **Higher taxes**: Inflated AGI resulted in "awfully high" tax calculations
- **Incorrect tax bracket positioning**: Over-estimated income pushed into higher brackets

## Solution

### Changes Made

#### Stage 5 (Social Security) - Lines 5700-5703

**Before:**
```python
# Use the LTCG ratio to estimate LTCG from the buffer replenishment
# The actual withdrawal already happened in rebalance_accounts
brokerage_withdrawal_ltcg = transactions['brokerage_to_cash'] * brokerage_account.ltcg_ratio
# ... or fallback
brokerage_withdrawal_ltcg = transactions['brokerage_to_cash'] * BROKERAGE_LTCG_RATIO

total_ltcg = ltcg_harvested + brokerage_withdrawal_ltcg
```

**After:**
```python
# Get actual LTCG from brokerage buffer replenishment (already calculated in rebalance_accounts)
brokerage_ltcg = transactions.get('brokerage_ltcg', 0.0)
total_ltcg = ltcg_harvested + brokerage_ltcg
```

#### Stage 6 (RMD) - Lines 6245-6251

**Before:**
```python
# Execute withdrawal and get actual LTCG (replaces 60/40 assumption)
brokerage_account = kwargs.get('brokerage_account')
if brokerage_account and transactions['brokerage_to_cash'] > 0:
    basis_from_buffer, brokerage_withdrawal_ltcg = brokerage_account.withdraw_fifo(
        transactions['brokerage_to_cash'], year
    )
else:
    # Fallback to old calculation if brokerage_account not available
    brokerage_withdrawal_ltcg = transactions['brokerage_to_cash'] * BROKERAGE_LTCG_RATIO

total_ltcg = ltcg_harvested + brokerage_withdrawal_ltcg
```

**After:**
```python
# Get actual LTCG from brokerage buffer replenishment (already calculated in rebalance_accounts)
brokerage_ltcg = transactions.get('brokerage_ltcg', 0.0)
total_ltcg = ltcg_harvested + brokerage_ltcg
```

#### Log Message Update - Stage 5 Line 5733

**Before:**
```python
logger.debug(f"Tax calculation: ... LTCG=${total_ltcg:,.0f} (harvested=${ltcg_harvested:,.0f}, buffer=${brokerage_withdrawal_ltcg:,.0f}), ...")
```

**After:**
```python
logger.debug(f"Tax calculation: ... LTCG=${total_ltcg:,.0f} (harvested=${ltcg_harvested:,.0f}, buffer=${brokerage_ltcg:,.0f}), ...")
```

## Technical Details

### How LTCG is Calculated

1. **In `rebalance_accounts()` (lines 3014-3270)**:
   - Calls `replenish_cash_buffer()` which performs actual brokerage withdrawals
   - `replenish_cash_buffer()` uses `BrokerageAccount.withdraw_fifo()` to calculate actual LTCG
   - Stores the result in `transactions['brokerage_ltcg']`

2. **In Stage 3 and Stage 4** (already fixed):
   - Retrieve `brokerage_ltcg` from transactions dictionary
   - Include in AGI calculation: `agi = total_ltcg + roth_conversion + trad_withdrawal`
   - Include in YearlyStrategy return: `ltcg_harvested=total_ltcg`

3. **In Stage 5 and Stage 6** (now fixed):
   - Retrieve `brokerage_ltcg` from transactions dictionary (same as Stages 3 & 4)
   - Include in AGI calculation
   - Include in YearlyStrategy return

### FIFO Cost Basis Tracking

The `BrokerageAccount.withdraw_fifo()` method:
- Tracks individual transaction lots with purchase date and cost basis
- Uses First-In-First-Out (FIFO) method for withdrawals
- Calculates actual LTCG based on the difference between sale price and cost basis
- Returns both basis returned and LTCG realized

This is more accurate than using a fixed ratio because:
- It accounts for actual purchase prices of individual lots
- It properly handles market fluctuations over time
- It reflects the true tax liability from the withdrawal

## Impact

### Before Fix
- **Stage 5**: Used estimated LTCG based on current cost basis ratio
- **Stage 6**: Performed double withdrawal, calculating incorrect LTCG
- **Result**: Inflated AGI and "awfully high" taxes

### After Fix
- **Stage 5**: Uses actual LTCG from FIFO-based withdrawal
- **Stage 6**: Uses actual LTCG from FIFO-based withdrawal (no double withdrawal)
- **Result**: Accurate AGI and correct tax calculations

### Tax Calculation Improvements

1. **More Accurate AGI**: Uses actual LTCG instead of estimates
2. **Correct Tax Brackets**: Proper income positioning in tax brackets
3. **Better Roth Conversion Optimization**: BETR algorithm works with accurate income data
4. **Improved IRMAA Calculations**: Correct MAGI for Medicare premium surcharges
5. **Accurate ACA Subsidy Calculations**: Proper MAGI for subsidy eligibility

## Testing

The existing test suite (`test_ltcg_estimation.py`) validates:
- Actual LTCG tracking from brokerage withdrawals
- Default ratio fallback when brokerage_account not available
- Zero LTCG when no withdrawals occur
- High and low gain scenarios

Additional testing should verify:
- Stage 5 tax calculations are reasonable
- Stage 6 tax calculations are reasonable
- No double-counting of brokerage withdrawals
- AGI matches expected values based on actual LTCG

## Related Files

- `strategy.py`: Stage 5 and Stage 6 implementations
- `calculations.py`: `replenish_cash_buffer()` and `rebalance_accounts()`
- `test_ltcg_estimation.py`: Test suite for LTCG calculations
- `LTCG_ESTIMATION_ENHANCEMENT.md`: Original LTCG estimation documentation
- `BETR_FIX_SUMMARY.md`: BETR algorithm fixes

## Conclusion

This fix ensures that Stage 5 and Stage 6 use the same accurate LTCG calculation method as Stages 3 and 4, eliminating the "awfully high" tax calculations and providing consistent, accurate tax planning across all life stages.