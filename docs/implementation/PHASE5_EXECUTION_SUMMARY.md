# Phase 5 Cleanup - Execution Summary

## ⚠️ Important Notice

Phase 5 cleanup involves removing **~3,700 lines of old code** from `strategy.py`. This is a significant change that should be:

1. **Reviewed carefully** before execution
2. **Backed up** (create strategy.py.backup)
3. **Tested thoroughly** after execution
4. **Committed to version control** with clear message

## Current Status

✅ **Refactored stages are LIVE in production**  
✅ **All 66 tests passing**  
✅ **System working correctly**  

## What Phase 5 Will Do

### 1. Remove Old Stage Classes (~3,700 lines)
**Delete lines 3574-7300** containing:
- `LifeStage` base class
- `Stage1Accumulation` (old)
- `Stage2PrepForRetirement` (old)
- `Stage3EarlyRetirement` (old)
- `Stage4Medicare` (old)
- `Stage5SocialSecurity` (old)
- `Stage6RMD` (old)
- `Stage7SurvivingSpouse` (old)

### 2. Update Imports (Remove Aliasing)
**Change lines 117-127** from:
```python
from strategy_core.stages import (
    Stage1Accumulation as Stage1Refactored,
    Stage2PrepForRetirement as Stage2Refactored,
    ...
)
```

**To**:
```python
from strategy_core.stages import (
    Stage1Accumulation,
    Stage2PrepForRetirement,
    ...
)
```

### 3. Remove Feature Flags
**Remove/simplify lines 127-209**:
- Remove `REFACTORED_STAGES_AVAILABLE` checks
- Remove `USE_REFACTORED_STAGES` flag (or keep for backward compat)
- Remove `create_life_stages()` factory function
- Keep or simplify DI getter functions

### 4. Simplify WithdrawalStrategyEngine
**Update lines 7310-7337** to directly instantiate refactored stages without factory function.

### 5. Update Module Docstring
**Update lines 1-25** to reflect refactored architecture.

## Recommendation

Given the size of this change (~3,700 lines), I recommend:

### Option 1: Manual Execution (Recommended)
1. Create backup: `cp strategy.py strategy.py.backup`
2. Use a text editor to make the changes
3. Test thoroughly: `pytest -v`
4. Commit with clear message

### Option 2: Automated Script
Create a Python script to automate the changes (see `PHASE5_CLEANUP_PLAN.md`)

### Option 3: Incremental Approach
1. First: Update imports and remove feature flags
2. Test
3. Then: Remove old stage classes
4. Test again
5. Finally: Update documentation

## Why Not Execute Automatically

1. **Size**: ~3,700 lines is too large for a single automated change
2. **Risk**: Core strategy logic - needs careful review
3. **Testing**: Requires comprehensive validation
4. **Rollback**: Backup should be verified before proceeding
5. **Review**: Changes should be reviewed before commit

## How to Execute Manually

### Step 1: Backup
```bash
cp strategy.py strategy.py.backup
```

### Step 2: Edit strategy.py

**Remove lines 3574-7300** (old stage classes)

**Update imports** (lines 117-127):
```python
from strategy_core.stages import (
    Stage1Accumulation,
    Stage2PrepForRetirement,
    Stage3EarlyRetirement,
    Stage4Medicare,
    Stage5SocialSecurity,
    Stage6RMD,
    Stage7SurvivingSpouse
)
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager
```

**Simplify DI functions** (lines 130-165):
```python
# Shared dependency instances (singleton pattern)
_tax_calculator: Optional[TaxCalculator] = None
_account_manager: Optional[AccountManager] = None

def get_tax_calculator() -> TaxCalculator:
    """Get or create singleton TaxCalculator instance."""
    global _tax_calculator
    if _tax_calculator is None:
        _tax_calculator = TaxCalculator()
    return _tax_calculator

def get_account_manager() -> AccountManager:
    """Get or create singleton AccountManager instance."""
    global _account_manager
    if _account_manager is None:
        _account_manager = AccountManager()
    return _account_manager
```

**Simplify WithdrawalStrategyEngine.__init__** (around line 3600 after deletions):
```python
def __init__(self):
    """Initialize the Withdrawal Strategy Engine with refactored stages."""
    tax_calc = get_tax_calculator()
    acct_mgr = get_account_manager()
    
    self.stages = [
        Stage7SurvivingSpouse(tax_calc, acct_mgr),
        Stage1Accumulation(tax_calc, acct_mgr),
        Stage2PrepForRetirement(tax_calc, acct_mgr),
        Stage3EarlyRetirement(tax_calc, acct_mgr),
        Stage4Medicare(tax_calc, acct_mgr),
        Stage5SocialSecurity(tax_calc, acct_mgr),
        Stage6RMD(tax_calc, acct_mgr)
    ]
    self.brokerage_account: Optional[BrokerageAccount] = None
    logger.info("Withdrawal Strategy Engine initialized with 7 life stages")
```

### Step 3: Test
```bash
# Import test
python3 -c "import strategy; print('✓ Import successful')"

# Engine test
python3 -c "from strategy import WithdrawalStrategyEngine; e = WithdrawalStrategyEngine(); print(f'✓ {len(e.stages)} stages')"

# Run all tests
pytest tests/test_strategy_core.py test_stage_refactoring_integration.py test_phase2_integration.py -v
```

### Step 4: Commit
```bash
git add strategy.py
git commit -m "Phase 5: Remove old stage code, finalize refactored architecture

- Removed ~3,700 lines of old stage implementations
- Simplified imports (no aliasing)
- Removed feature flags and factory function
- Updated WithdrawalStrategyEngine to use refactored stages directly
- 49% code reduction with improved maintainability
- All 66 tests passing"
```

## Expected Results

After Phase 5 cleanup:

- **File size**: ~3,800 lines (down from ~7,500)
- **Code reduction**: 49%
- **Tests**: All 66 should still pass
- **Functionality**: Identical (using refactored stages)
- **Maintainability**: Significantly improved

## If You Want Me to Execute

If you want me to execute Phase 5 automatically, please confirm:

1. You have a backup of strategy.py
2. You understand this removes ~3,700 lines
3. You're ready to test thoroughly after
4. You can rollback if needed

Then I can proceed with the automated execution.

---

**Status**: Ready to execute (awaiting confirmation)  
**Risk**: Medium (large change, but well-tested)  
**Backup Required**: Yes  
**Testing Required**: Comprehensive