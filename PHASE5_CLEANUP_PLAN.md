# Phase 5: Cleanup Plan

## Overview

This document outlines the plan to remove old stage code and finalize the migration to refactored stages.

## Scope of Changes

### Code to Remove

**File**: `strategy.py`
**Lines**: 3574-7300 (approximately 3,726 lines)

This includes:
- `LifeStage` base class (line 3574)
- `Stage1Accumulation` (line 3778)
- `Stage2PrepForRetirement` (line 4204)
- `Stage3EarlyRetirement` (line 4711)
- `Stage4Medicare` (line 5214)
- `Stage5SocialSecurity` (line 5770)
- `Stage6RMD` (line 6515)
- `Stage7SurvivingSpouse` (line 6977)

### Imports to Update

**Current** (with aliasing):
```python
from strategy_core.stages import (
    Stage1Accumulation as Stage1Refactored,
    Stage2PrepForRetirement as Stage2Refactored,
    ...
)
```

**After cleanup** (no aliasing):
```python
from strategy_core.stages import (
    Stage1Accumulation,
    Stage2PrepForRetirement,
    ...
)
```

### Feature Flags to Remove/Update

1. **Remove**: `USE_REFACTORED_STAGES` environment variable check
2. **Remove**: `REFACTORED_STAGES_AVAILABLE` flag
3. **Remove**: `COMPARE_IMPLEMENTATIONS` flag
4. **Remove**: `create_life_stages()` factory function
5. **Remove**: Dependency injection getter functions (or keep if useful)

### Code to Update

**WithdrawalStrategyEngine.__init__():**
- Remove `use_refactored_stages` parameter
- Directly instantiate refactored stages
- Remove factory function call

## Step-by-Step Execution Plan

### Step 1: Update Imports (Remove Aliasing)

Change imports from aliased to direct:
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
```

### Step 2: Simplify Dependency Injection

Keep the DI functions but simplify:
```python
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

### Step 3: Remove Feature Flags and Factory

Remove:
- `USE_REFACTORED_STAGES`
- `REFACTORED_STAGES_AVAILABLE`
- `COMPARE_IMPLEMENTATIONS`
- `create_life_stages()` function

### Step 4: Remove Old Stage Classes

Delete lines 3574-7300 containing:
- LifeStage base class
- All 7 old stage implementations

### Step 5: Simplify WithdrawalStrategyEngine

Update `__init__` to directly use refactored stages:
```python
def __init__(self):
    """Initialize the Withdrawal Strategy Engine."""
    tax_calc = get_tax_calculator()
    acct_mgr = get_account_manager()
    
    self.stages = [
        Stage7SurvivingSpouse(tax_calc, acct_mgr),  # Check first
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

### Step 6: Update Documentation

Update module docstring to reflect refactored architecture:
```python
"""
Portfolio Withdrawal Strategy Module - Refactored Architecture

This module implements a comprehensive withdrawal strategy across 7 life stages
using a modern, dependency-injected architecture.

Life Stages:
1. Accumulation: Employed, earning wages, tax-efficient asset accumulation
2. Prep for Retirement: Within 10 years of retirement, balance account types
3. Early Retirement: Pre-Medicare, pre-SS, pre-RMD with BETR-optimized conversions
4. Medicare Stage: IRMAA optimization with continued Roth conversions
5. Social Security Stage: SS benefits + Medicare, pre-RMD optimization
6. RMD Stage: Required Minimum Distributions with full retirement income
7. Surviving Spouse: Optimized strategy for surviving spouse

Architecture:
- Dependency injection for testability
- Type-safe interfaces
- Centralized tax calculations
- Modular account management
- Comprehensive decision logging

Based on Vanguard Research: "A 'BETR' approach to Roth conversions" (July 2025)
"""
```

## Testing After Cleanup

### 1. Import Test
```bash
python3 -c "import strategy; print('✓ Module imports successfully')"
```

### 2. Engine Creation Test
```bash
python3 -c "
from strategy import WithdrawalStrategyEngine
engine = WithdrawalStrategyEngine()
print(f'✓ Engine created with {len(engine.stages)} stages')
"
```

### 3. Run All Tests
```bash
pytest tests/test_strategy_core.py test_stage_refactoring_integration.py test_phase2_integration.py -v
```

### 4. Run Application
```bash
python3 planning_app.py
```

## Rollback Plan

If issues arise after cleanup:

### Option 1: Git Revert
```bash
git revert <commit-hash>
```

### Option 2: Restore from Backup
Keep a backup of `strategy.py` before cleanup:
```bash
cp strategy.py strategy.py.backup
```

## Success Criteria

Cleanup is successful when:

- [x] Old stage classes removed
- [x] Imports updated (no aliasing)
- [x] Feature flags removed
- [x] Factory function removed
- [x] Engine simplified
- [x] Documentation updated
- [x] All tests passing
- [x] Application runs correctly
- [x] No references to old code

## File Size Impact

**Before cleanup:**
- strategy.py: ~7,500 lines

**After cleanup:**
- strategy.py: ~3,800 lines (50% reduction!)

**Benefits:**
- Cleaner codebase
- Easier to maintain
- Faster to understand
- Better organized
- Modern architecture

## Timeline

**Estimated Time**: 2-4 hours

- Step 1-3 (Imports & flags): 30 minutes
- Step 4 (Remove old code): 30 minutes
- Step 5 (Simplify engine): 30 minutes
- Step 6 (Documentation): 30 minutes
- Testing & validation: 1-2 hours

## Notes

- Keep backup of original file
- Test thoroughly after each step
- Update any external documentation
- Notify team of changes
- Celebrate completion! 🎉

---

**Status**: Ready to Execute  
**Risk**: Low (all tests passing, well-tested)  
**Impact**: High (50% code reduction, cleaner architecture)