# BETR Tax Bracket Fix - Documentation

## Issue Identified

The BETR (Break-Even Tax Rate) calculation in `strategy.py` was using a **fixed 8% increment** to estimate the expected future tax rate, rather than looking up the actual next tax bracket. This caused incorrect future tax rate assumptions for most tax brackets.

### Location
- **File**: `strategy.py`
- **Line**: 4911 (original)
- **Function**: Stage 3 Early Retirement Roth conversion optimization

### The Problem

```python
# OLD CODE (INCORRECT):
expected_future_rate = min(0.32, max_conversion_rate + 0.08)  # One bracket higher, capped at 32%
```

This approach had several issues:

1. **Incorrect for most brackets**: Tax brackets don't have uniform 8% spacing
   - 12% + 8% = 20% ❌ (should be 22%)
   - 22% + 8% = 30% ❌ (should be 24%)
   - 24% + 8% = 32% ✓ (correct by coincidence)

2. **Misleading comment**: The comment said "one bracket higher" but the calculation didn't actually look up the next bracket

3. **Hardcoded cap**: The `min(0.32, ...)` cap was arbitrary and could prevent using the correct next bracket for higher income scenarios

## Solution Implemented

### 1. New Helper Function in `calculations.py`

Added `getNextHigherTaxRate()` function that properly looks up the next tax bracket:

```python
def getNextHigherTaxRate(current_rate, year_tax_brackets_df):
    """
    Get the next higher tax rate from the current rate.
    
    Args:
        current_rate: Current tax rate (can be string or numeric)
        year_tax_brackets_df: DataFrame containing tax bracket information with 'rate' column
        
    Returns:
        float: Next higher tax rate, or current rate if already at highest bracket
        
    Raises:
        ValueError: If the current tax rate is not found in the brackets
    """
```

**Key features:**
- Uses actual tax bracket data from the year's tax tables
- Handles floating-point comparison correctly with `np.isclose()`
- Returns current rate if already at the highest bracket
- Raises clear error if bracket not found

### 2. Updated `strategy.py`

Modified the BETR calculation to use the new function:

```python
# NEW CODE (CORRECT):
try:
    tax_brackets_df = get_income_tax_brackets(year)
    expected_future_rate = getNextHigherTaxRate(max_conversion_rate, tax_brackets_df)
except (ValueError, Exception) as e:
    logger.warning(f"Could not determine next tax bracket, using current rate: {e}")
    expected_future_rate = max_conversion_rate
```

**Improvements:**
- Looks up actual next bracket from tax tables
- Handles errors gracefully with fallback to current rate
- No arbitrary caps - uses actual tax bracket structure
- Works correctly for all tax brackets

### 3. Added Import

Updated imports in `strategy.py`:

```python
from calculations import (
    # ... existing imports ...
    getNextHigherTaxRate  # NEW
)
```

## Verification

Created comprehensive test suite in `test_betr_bracket_fix.py`:

### Test Results
```
✓ PASS: 10% -> 12%
✓ PASS: 12% -> 22%
✓ PASS: 22% -> 24%
✓ PASS: 24% -> 32%
✓ PASS: 32% -> 35%
✓ PASS: 35% -> 37%
✓ PASS: 37% -> 37% (already at top)
```

### Bug Demonstration
The test also demonstrates how the old calculation was wrong:
- 12% + 0.08 = 20% ❌ (should be 22%)
- 22% + 0.08 = 30% ❌ (should be 24%)
- 24% + 0.08 = 32% ✓ (correct by coincidence)

## Impact

### Before Fix
- **12% bracket**: Expected future rate of 20% (incorrect, should be 22%)
  - Impact: Underestimated future tax burden by 2%
  - Result: May have recommended conversions that weren't optimal
  
- **22% bracket**: Expected future rate of 30% (incorrect, should be 24%)
  - Impact: Overestimated future tax burden by 6%
  - Result: May have over-recommended conversions

- **24% bracket**: Expected future rate of 32% (correct by coincidence)
  - Impact: None - happened to be correct

### After Fix
- **All brackets**: Correctly uses the actual next tax bracket
- **More accurate BETR calculations**: Better conversion recommendations
- **Proper tax planning**: Accounts for actual tax bracket structure

## Federal Tax Brackets (2026)

For reference, the actual federal tax bracket structure:
- 10% → 12% (2% increase)
- 12% → 22% (10% increase)
- 22% → 24% (2% increase)
- 24% → 32% (8% increase) ← Old code only worked here
- 32% → 35% (3% increase)
- 35% → 37% (2% increase)
- 37% → 37% (top bracket)

## Files Modified

1. **calculations.py**
   - Added `getNextHigherTaxRate()` function (lines 308-344)

2. **strategy.py**
   - Updated import statement to include `getNextHigherTaxRate`
   - Modified BETR expected future rate calculation (lines 4906-4918)

3. **test_betr_bracket_fix.py** (NEW)
   - Comprehensive test suite for the fix
   - Demonstrates the bug and validates the solution

## Testing

To run the test:
```bash
python3 test_betr_bracket_fix.py
```

Expected output: All tests should pass with ✓ marks.

## Recommendations

1. **Review past conversions**: If you've made Roth conversions based on BETR calculations in the 12% or 22% brackets, review those decisions with the corrected calculations.

2. **Re-run scenarios**: Re-run any saved scenarios to get updated recommendations with the correct bracket lookups.

3. **Monitor future changes**: Tax brackets can change with legislation. The new implementation will automatically use the correct brackets for any year.

## Related Documentation

- [BETR_GUIDE.md](BETR_GUIDE.md) - Complete BETR algorithm guide
- [BETR_CORRECTION_NOTES.md](BETR_CORRECTION_NOTES.md) - Previous BETR fix (recommendation logic)

## Date

**Fixed**: 2026-03-16

---

**Made with IBM Bob**