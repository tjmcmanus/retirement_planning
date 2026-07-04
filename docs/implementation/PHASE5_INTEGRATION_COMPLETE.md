# Phase 5: Cleanup - Ready to Execute ✅

## Summary

Phase 5 (Cleanup) plan is complete and ready for execution. This phase will remove ~3,700 lines of old code and finalize the migration to the refactored architecture.

## What Needs to Be Done

### 1. Update Imports (Remove Aliasing)

**Current** (lines 117-127):
```python
from strategy_core.stages import (
    Stage1Accumulation as Stage1Refactored,
    Stage2PrepForRetirement as Stage2Refactored,
    Stage3EarlyRetirement as Stage3Refactored,
    Stage4Medicare as Stage4Refactored,
    Stage5SocialSecurity as Stage5Refactored,
    Stage6RMD as Stage6Refactored,
    Stage7SurvivingSpouse as Stage7Refactored
)
```

**Change to**:
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

### 2. Remove Feature Flags and Factory Function

**Remove** (lines 127-209):
- `REFACTORED_STAGES_AVAILABLE` flag
- `USE_REFACTORED_STAGES` environment variable
- `_tax_calculator` and `_account_manager` globals (or keep if useful)
- `get_tax_calculator()` function (or simplify)
- `get_account_manager()` function (or simplify)
- `create_life_stages()` factory function
- `COMPARE_IMPLEMENTATIONS` flag

**Keep** (simplified):
```python
# Shared dependency instances for stages (singleton pattern)
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

### 3. Remove Old Stage Classes

**Delete** lines 3574-7300 (~3,726 lines):
- `LifeStage` base class (line 3574)
- `Stage1Accumulation` old implementation (line 3778)
- `Stage2PrepForRetirement` old implementation (line 4204)
- `Stage3EarlyRetirement` old implementation (line 4711)
- `Stage4Medicare` old implementation (line 5214)
- `Stage5SocialSecurity` old implementation (line 5770)
- `Stage6RMD` old implementation (line 6515)
- `Stage7SurvivingSpouse` old implementation (line 6977)

### 4. Simplify WithdrawalStrategyEngine

**Current** (lines 7310-7337):
```python
def __init__(self, use_refactored_stages: Optional[bool] = None):
    """
    Initialize the Withdrawal Strategy Engine.
    
    Args:
        use_refactored_stages: If True, use refactored stages. If False, use original.
                              If None (default), uses USE_REFACTORED_STAGES flag.
    """
    # Determine which implementation to use
    if use_refactored_stages is None:
        use_refactored_stages = USE_REFACTORED_STAGES
    
    # Create stages using factory function
    self.stages = create_life_stages(use_refactored=use_refactored_stages)
    self.brokerage_account: Optional[BrokerageAccount] = None
    
    impl_type = "refactored" if use_refactored_stages else "original"
    logger.info(f"Withdrawal Strategy Engine initialized with 7 life stages ({impl_type} implementation)")
```

**Change to**:
```python
def __init__(self):
    """Initialize the Withdrawal Strategy Engine with refactored stages."""
    tax_calc = get_tax_calculator()
    acct_mgr = get_account_manager()
    
    self.stages = [
        Stage7SurvivingSpouse(tax_calc, acct_mgr),  # Check first - takes precedence
        Stage1Accumulation(tax_calc, acct_mgr),
        Stage2PrepForRetirement(tax_calc, acct_mgr),
        Stage3EarlyRetirement(tax_calc, acct_mgr),
        Stage4Medicare(tax_calc, acct_mgr),
        Stage5SocialSecurity(tax_calc, acct_mgr),
        Stage6RMD(tax_calc, acct_mgr)
    ]
    self.brokerage_account: Optional[BrokerageAccount] = None
    logger.info("Withdrawal Strategy Engine initialized with 7 life stages (refactored architecture)")
```

### 5. Update Module Docstring

**Update** (lines 1-25) to reflect refactored architecture:
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

Architecture Features:
- Dependency injection for testability and modularity
- Type-safe interfaces throughout
- Centralized tax calculations via TaxCalculator
- Modular account management via AccountManager
- Comprehensive decision logging
- Clean separation of concerns

Key Features:
- BETR (Break-Even Tax Rate) algorithm for optimal Roth conversion decisions
- RMD lookback optimization to reduce future tax burden
- Tax-efficient withdrawal sequencing across all life stages
- IRMAA threshold management with 2-year lookback
- ACA subsidy optimization for early retirees
- Dynamic Security Selection for intelligent withdrawal decisions

Based on Vanguard Research: "A 'BETR' approach to Roth conversions" (July 2025)

Author: IBM Bob
Date: 2026-04-13
Version: 3.0 - Refactored Architecture with Dependency Injection
"""
```

## Impact Analysis

### Code Reduction
- **Before**: ~7,500 lines
- **After**: ~3,800 lines
- **Reduction**: ~3,700 lines (49% smaller!)

### Benefits
✅ **Cleaner codebase** - 50% less code to maintain
✅ **Better organization** - Clear separation of concerns
✅ **Improved testability** - Dependency injection throughout
✅ **Type safety** - Full type hints
✅ **Bug fix included** - Better stage selection logic
✅ **Easier to understand** - Modern architecture patterns
✅ **Future-proof** - Easy to extend and modify

### Risks
⚠️ **Breaking changes** - Old code references will break
⚠️ **Testing required** - Must validate all functionality
⚠️ **Documentation updates** - External docs may need updates

## Testing Checklist

After cleanup, verify:

- [ ] Module imports successfully
- [ ] Engine creates with 7 stages
- [ ] All 66 tests pass
- [ ] Application runs correctly
- [ ] No import errors
- [ ] No references to old classes
- [ ] Performance is acceptable
- [ ] Logs show refactored architecture

## Execution Steps

### Step 1: Create Backup
```bash
cp strategy.py strategy.py.backup
```

### Step 2: Execute Changes
Make the 5 changes listed above in order:
1. Update imports (remove aliasing)
2. Remove feature flags and factory
3. Delete old stage classes (lines 3574-7300)
4. Simplify WithdrawalStrategyEngine.__init__
5. Update module docstring

### Step 3: Test
```bash
# Import test
python3 -c "import strategy; print('✓ Import successful')"

# Engine test
python3 -c "from strategy import WithdrawalStrategyEngine; e = WithdrawalStrategyEngine(); print(f'✓ Engine created: {len(e.stages)} stages')"

# Run all tests
pytest tests/test_strategy_core.py test_stage_refactoring_integration.py test_phase2_integration.py -v

# Run application
python3 planning_app.py
```

### Step 4: Update Tests
Some tests may need updates:
- `test_phase2_integration.py` - Remove tests for old implementation
- Update any tests that reference `use_refactored_stages` parameter

### Step 5: Commit
```bash
git add strategy.py
git commit -m "Phase 5: Remove old stage code, finalize refactored architecture

- Removed ~3,700 lines of old stage implementations
- Simplified imports (no aliasing)
- Removed feature flags and factory function
- Updated WithdrawalStrategyEngine to use refactored stages directly
- Updated documentation to reflect new architecture
- 49% code reduction with improved maintainability"
```

## Why This Approach

**Manual execution recommended** because:
1. **Large change**: ~3,700 lines removed
2. **Critical code**: Core strategy logic
3. **Review needed**: Should be carefully reviewed
4. **Testing required**: Comprehensive validation needed
5. **Rollback plan**: Backup should be verified

## Alternative: Automated Script

If you prefer automation, here's a script outline:

```python
#!/usr/bin/env python3
"""
Automated cleanup script for Phase 5.
Use with caution - creates backup first.
"""

import shutil
import re

# Backup
shutil.copy('strategy.py', 'strategy.py.backup')

# Read file
with open('strategy.py', 'r') as f:
    lines = f.readlines()

# Remove lines 3574-7300 (old stage classes)
new_lines = lines[:3573] + lines[7300:]

# Update imports (remove aliasing)
# ... regex replacements ...

# Remove feature flags
# ... more replacements ...

# Write back
with open('strategy.py', 'w') as f:
    f.writelines(new_lines)

print("✓ Cleanup complete - please test thoroughly!")
```

## Success Criteria

Cleanup is successful when:

✅ All old stage code removed
✅ Imports simplified (no aliasing)
✅ Feature flags removed
✅ Engine simplified
✅ Documentation updated
✅ All tests passing (66/66)
✅ Application runs correctly
✅ No errors in logs
✅ Performance maintained

## Next Steps After Cleanup

1. **Test thoroughly** - Run all tests and application
2. **Update external docs** - README, guides, etc.
3. **Notify team** - Inform about architecture change
4. **Monitor** - Watch for any issues
5. **Celebrate!** 🎉 - Migration complete!

## Integration Complete!

Once Phase 5 is executed:

| Phase | Status | Time | Impact |
|-------|--------|------|--------|
| Phase 1: Preparation | ✅ Complete | 15 min | Infrastructure |
| Phase 2: Parallel Implementation | ✅ Complete | 20 min | Factory pattern |
| Phase 3: Testing & Validation | ✅ Complete | 30 min | 66 tests |
| Phase 4: Gradual Rollout | ✅ Complete | 30 min | Tools & docs |
| Phase 5: Cleanup | ⏳ Ready | 2-4 hrs | 49% code reduction |

**Total Estimated Time**: ~4 hours
**Total Code Reduction**: ~3,700 lines (49%)
**Total Tests**: 66 passing
**Bug Fixes**: 1 (stage selection logic)

---

**Phase 5 Status**: ✅ **READY TO EXECUTE**  
**Date Prepared**: 2026-04-13  
**Backup Required**: Yes (strategy.py.backup)  
**Testing Required**: Comprehensive  
**Risk Level**: Low (well-tested, easy rollback)  
**Recommendation**: Execute with careful testing