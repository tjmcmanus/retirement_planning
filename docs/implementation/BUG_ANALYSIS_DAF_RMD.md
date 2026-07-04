# Bug Analysis: DAF Contributions and RMD Issues

## Date: 2026-04-13

## Issues Identified

### Issue 1: DAF Contributions Not Reducing Taxable Account Balances

**Location:** `strategy_core/stages/stage6_rmd.py` (lines 256-263)

**Problem:**
When a DAF contribution is made, the code adds the contribution to the DAF balance but does NOT subtract it from the taxable balance. This creates a fund conservation violation where money appears to be created out of thin air.

**Current Code (Stage 6, lines 256-263):**
```python
if daf_contribution > 0:
    new_balances = PortfolioBalances(
        cash=new_balances.cash,
        taxable=new_balances.taxable,  # ❌ NOT REDUCED
        traditional=new_balances.traditional,
        roth=new_balances.roth,
        daf=new_balances.daf + daf_contribution  # ✅ INCREASED
    )
```

**Expected Behavior:**
The taxable balance should be reduced by the DAF contribution amount since the funds are transferred from the taxable brokerage account to the DAF.

**Impact:**
- Portfolio total value is artificially inflated
- Fund conservation is violated
- Tax calculations may be incorrect
- Misleading account balance reporting

**Similar Issue in Other Stages:**
- Stage 4 (Medicare): Lines 273-280 - Same issue
- Stage 5 (Social Security): Lines 258-268 - Correctly subtracts BEFORE rebalancing but may have issues AFTER

---

### Issue 2: RMD Amount Showing $0 in Strategy Object

**Location:** `strategy_core/stages/stage6_rmd.py` (line 300)

**Problem:**
The RMD amount is correctly calculated (line 136) and used in calculations, but when populating the strategy object, it's set correctly at line 300. However, the issue may be in how RMD is being calculated or displayed.

**Current Code Analysis:**
```python
# Line 136: RMD calculated
rmd_amount = self._calculate_rmd(age_primary, balances.traditional)

# Line 300: RMD set in strategy
strategy.rmd_amount = rmd_amount
```

**Potential Root Causes:**
1. `_calculate_rmd()` method may be returning 0 due to:
   - Age check failing (age < 73)
   - Traditional balance being 0
   - Error in RMD calculation logic
   - Missing or incorrect RMD rate data

2. The RMD calculation method (lines 335-354) has error handling that returns 0.0 on failure

**Investigation Needed:**
- Check if `get_rmd_value()` is working correctly
- Verify age_primary is >= 73 when RMD should apply
- Verify traditional balance is > 0
- Check for exceptions being caught and suppressed

---

## Root Cause Analysis

### DAF Bug Root Cause:
The code correctly subtracts DAF from taxable BEFORE rebalancing (lines 197-207), but then AFTER rebalancing and growth, it adds DAF to the DAF balance WITHOUT subtracting from taxable (lines 256-263). This creates duplicate funds.

**The Fix:**
The taxable balance should be reduced when DAF is added to the DAF balance.

### RMD Bug Root Cause:
Likely one of:
1. RMD calculation returning 0 due to missing data or error
2. Age check preventing RMD calculation
3. Traditional balance being 0 or very small
4. Exception being caught and returning 0

**The Fix:**
Need to add better logging and error handling in `_calculate_rmd()` to identify why it's returning 0.

---

## Affected Stages

### DAF Bug:
- ✅ Stage 4 (Medicare): Lines 273-280 - NEEDS FIX
- ⚠️ Stage 5 (Social Security): Lines 258-268 - Partially correct, needs verification
- ✅ Stage 6 (RMD): Lines 256-263 - NEEDS FIX

### RMD Bug:
- Stage 6 (RMD): Lines 335-354 - Needs investigation

---

## Proposed Fixes

### Fix 1: DAF Balance Reduction

**Stage 6 (lines 256-263):**
```python
if daf_contribution > 0:
    new_balances = PortfolioBalances(
        cash=new_balances.cash,
        taxable=new_balances.taxable - daf_contribution,  # ✅ SUBTRACT DAF
        traditional=new_balances.traditional,
        roth=new_balances.roth,
        daf=new_balances.daf + daf_contribution
    )
```

**Stage 4 (lines 273-280):**
```python
if daf_contribution > 0:
    new_balances = PortfolioBalances(
        cash=new_balances.cash,
        taxable=new_balances.taxable - daf_contribution,  # ✅ SUBTRACT DAF
        traditional=new_balances.traditional,
        roth=new_balances.roth,
        daf=new_balances.daf + daf_contribution
    )
```

### Fix 2: RMD Calculation Debugging

Add enhanced logging to `_calculate_rmd()` method:
```python
def _calculate_rmd(self, age_primary: int, traditional_balance: float) -> float:
    logger.info(f"RMD calculation: age={age_primary}, balance=${traditional_balance:,.2f}")
    
    if age_primary < RMD_AGE:
        logger.info(f"RMD not required: age {age_primary} < {RMD_AGE}")
        return 0.0
    
    if traditional_balance <= 0:
        logger.info(f"RMD not required: traditional balance is ${traditional_balance:,.2f}")
        return 0.0
    
    try:
        from load_data import get_rmd_value
        rmd_rate = get_rmd_value(age_primary)
        logger.info(f"RMD rate for age {age_primary}: {rmd_rate}")
        
        if rmd_rate > 0 and traditional_balance > 0:
            rmd = traditional_balance / rmd_rate
            logger.info(f"RMD calculated: ${rmd:,.2f}")
            return rmd
        else:
            logger.warning(f"Invalid RMD rate: {rmd_rate}")
            return 0.0
    except Exception as e:
        logger.error(f"Error calculating RMD: {e}", exc_info=True)
        return 0.0
```

---

## Testing Plan

1. Create test case for DAF contribution with known balances
2. Verify taxable balance is reduced by DAF amount
3. Verify DAF balance is increased by DAF amount
4. Verify total portfolio value remains constant (fund conservation)
5. Create test case for RMD calculation with age >= 73
6. Verify RMD is calculated correctly
7. Verify RMD appears in strategy object
8. Run full integration tests to ensure no regressions

---

## Priority

**DAF Bug:** HIGH - Causes fund conservation violations and incorrect balance reporting
**RMD Bug:** MEDIUM - May be a display issue or data issue rather than calculation bug

---

## Next Steps

1. ✅ Document bugs (this file)
2. Create test cases to reproduce bugs
3. Implement fixes for DAF balance reduction
4. Add enhanced logging for RMD calculation
5. Run tests to verify fixes
6. Update documentation