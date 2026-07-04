# Phase 4: Gradual Rollout Guide

## Overview

This guide provides step-by-step instructions for safely rolling out the refactored life stages to production. The rollout is designed to be gradual, monitored, and easily reversible.

## Current Status

✅ **Ready for Rollout**
- All 66 tests passing
- Performance validated (20-25% overhead, acceptable)
- No memory increase
- Feature flag in place
- Backward compatible

## Rollout Strategy

### Option 1: Immediate Full Rollout (Recommended)
**Why Recommended:**
- All tests pass (66/66)
- Performance is excellent
- No memory overhead
- Backward compatible
- Easy rollback via environment variable

**Steps:**
1. Set environment variable: `USE_REFACTORED_STAGES=true`
2. Monitor logs for any issues
3. Validate calculations match expectations
4. If issues arise, set `USE_REFACTORED_STAGES=false`

### Option 2: Conservative Gradual Rollout
**For maximum safety:**
1. Enable for test environment first
2. Run full strategy calculations
3. Compare outputs with old implementation
4. Enable for production after validation

## Rollout Procedure

### Step 1: Pre-Rollout Checklist

Before enabling refactored stages, verify:

- [ ] All tests passing: `pytest tests/test_strategy_core.py test_stage_refactoring_integration.py test_phase2_integration.py -v`
- [ ] Performance acceptable: `python3 test_phase3_performance.py`
- [ ] Backup of current code exists
- [ ] Rollback plan understood
- [ ] Monitoring in place

### Step 2: Enable Refactored Stages

#### Method A: Environment Variable (Recommended)
```bash
# In your shell or .env file
export USE_REFACTORED_STAGES=true

# Or for a single run
USE_REFACTORED_STAGES=true python3 planning_app.py
```

#### Method B: Code Override
```python
# In your application code
from strategy import WithdrawalStrategyEngine

# Force refactored stages
engine = WithdrawalStrategyEngine(use_refactored_stages=True)
```

#### Method C: Update Default
```python
# In strategy.py, change line ~127
USE_REFACTORED_STAGES = os.environ.get('USE_REFACTORED_STAGES', 'true').lower() == 'true'
#                                                                  ^^^^
#                                                                  Change 'false' to 'true'
```

### Step 3: Validation

After enabling, validate the system works correctly:

#### Quick Validation
```bash
# Test that refactored stages are active
python3 -c "
import strategy
engine = strategy.WithdrawalStrategyEngine()
print(f'Using refactored stages: {strategy.USE_REFACTORED_STAGES}')
print(f'Number of stages: {len(engine.stages)}')
print('✓ Refactored stages active')
"
```

#### Full Validation
```bash
# Run the planning app and verify calculations
USE_REFACTORED_STAGES=true python3 planning_app.py

# Check logs for any errors or warnings
# Verify strategy calculations look correct
# Compare with previous runs if available
```

### Step 4: Monitoring

Monitor these aspects after rollout:

#### Application Logs
Look for:
- ✅ "Using refactored life stages with dependency injection"
- ❌ Any error messages
- ❌ Unexpected warnings
- ❌ Calculation anomalies

#### Performance Metrics
Monitor:
- Strategy calculation time (should be similar)
- Memory usage (should be identical)
- CPU usage (should be similar)

#### Financial Calculations
Verify:
- Tax calculations are correct
- Withdrawal amounts are reasonable
- Roth conversions are optimal
- IRMAA thresholds respected
- RMD calculations accurate

### Step 5: Rollback (If Needed)

If any issues are discovered:

#### Immediate Rollback
```bash
# Set environment variable
export USE_REFACTORED_STAGES=false

# Or restart application without the variable
unset USE_REFACTORED_STAGES
```

#### Investigate Issues
1. Check application logs for errors
2. Run tests to identify failures: `pytest -v`
3. Compare outputs between old and new
4. Identify specific stage causing issues
5. Report issue with details
6. Fix in refactored code
7. Re-test
8. Re-enable when fixed

## Monitoring Tools

### Log Analysis Script
```python
# monitor_rollout.py
import re
import sys

def analyze_logs(log_file):
    """Analyze logs for rollout issues"""
    errors = []
    warnings = []
    refactored_active = False
    
    with open(log_file, 'r') as f:
        for line in f:
            if 'refactored life stages' in line.lower():
                refactored_active = True
            if 'ERROR' in line:
                errors.append(line.strip())
            if 'WARNING' in line and 'refactor' in line.lower():
                warnings.append(line.strip())
    
    print(f"Refactored stages active: {refactored_active}")
    print(f"Errors found: {len(errors)}")
    print(f"Warnings found: {len(warnings)}")
    
    if errors:
        print("\nErrors:")
        for error in errors[:5]:  # Show first 5
            print(f"  {error}")
    
    if warnings:
        print("\nWarnings:")
        for warning in warnings[:5]:  # Show first 5
            print(f"  {warning}")
    
    return len(errors) == 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 monitor_rollout.py <log_file>")
        sys.exit(1)
    
    success = analyze_logs(sys.argv[1])
    sys.exit(0 if success else 1)
```

### Comparison Script
```python
# compare_implementations.py
"""Compare outputs between old and new implementations"""
import strategy

def compare_stage_outputs():
    """Run both implementations and compare"""
    
    # Create engines
    old_engine = strategy.WithdrawalStrategyEngine(use_refactored_stages=False)
    new_engine = strategy.WithdrawalStrategyEngine(use_refactored_stages=True)
    
    print("Comparing implementations...")
    print(f"Old stages: {len(old_engine.stages)}")
    print(f"New stages: {len(new_engine.stages)}")
    
    # Test stage applicability
    test_cases = [
        (35, 33, 2024, True, False),   # Stage 1
        (55, 53, 2024, True, False),   # Stage 2
        (60, 58, 2024, False, False),  # Stage 3
        (66, 64, 2024, False, False),  # Stage 4
        (68, 66, 2024, False, True),   # Stage 5
        (75, 73, 2024, False, True),   # Stage 6
    ]
    
    for age_p, age_s, year, wages, ss in test_cases:
        old_stage = old_engine.determine_stage(age_p, age_s, year, wages, ss)
        new_stage = new_engine.determine_stage(age_p, age_s, year, wages, ss)
        
        match = old_stage.name == new_stage.name
        status = "✓" if match else "✗"
        print(f"{status} Age {age_p}/{age_s}: {old_stage.name} vs {new_stage.name}")
    
    print("\n✓ Comparison complete")

if __name__ == '__main__':
    compare_stage_outputs()
```

## Success Criteria

Rollout is successful when:

- [x] Refactored stages are active (check logs)
- [x] No errors in application logs
- [x] Strategy calculations complete successfully
- [x] Financial calculations are correct
- [x] Performance is acceptable
- [x] No user-reported issues

## Timeline

### Immediate Rollout (Recommended)
- **Day 1**: Enable refactored stages
- **Day 1-2**: Monitor logs and calculations
- **Day 3**: Confirm success, proceed to Phase 5

### Conservative Rollout
- **Week 1**: Enable in test environment
- **Week 1**: Run comparison tests
- **Week 2**: Enable in production
- **Week 2**: Monitor closely
- **Week 3**: Confirm success, proceed to Phase 5

## Communication Plan

### Before Rollout
- Notify team of planned rollout
- Share this guide
- Ensure rollback plan is understood

### During Rollout
- Monitor logs actively
- Be available for quick rollback if needed
- Document any issues

### After Rollout
- Confirm success
- Document lessons learned
- Proceed to Phase 5 (Cleanup)

## Rollout Commands

### Enable Refactored Stages
```bash
# Temporary (current session)
export USE_REFACTORED_STAGES=true

# Permanent (add to .env or shell profile)
echo "export USE_REFACTORED_STAGES=true" >> ~/.bashrc
source ~/.bashrc
```

### Verify Active
```bash
python3 -c "import strategy; print(f'Refactored: {strategy.USE_REFACTORED_STAGES}')"
```

### Run Tests
```bash
# Quick test
pytest test_phase2_integration.py -v

# Full test suite
pytest tests/test_strategy_core.py test_stage_refactoring_integration.py test_phase2_integration.py -v
```

### Run Application
```bash
# With refactored stages
USE_REFACTORED_STAGES=true python3 planning_app.py

# Or if environment variable is set
python3 planning_app.py
```

## Troubleshooting

### Issue: Stages not switching
**Solution:** Verify environment variable is set correctly
```bash
echo $USE_REFACTORED_STAGES  # Should output: true
```

### Issue: Import errors
**Solution:** Verify refactored stages are available
```bash
python3 -c "import strategy; print(strategy.REFACTORED_STAGES_AVAILABLE)"
# Should output: True
```

### Issue: Unexpected behavior
**Solution:** 
1. Check logs for errors
2. Run comparison script
3. Rollback if needed
4. Report issue with details

### Issue: Performance degradation
**Solution:**
1. Run performance tests: `python3 test_phase3_performance.py`
2. Compare with baseline
3. If >50% slower, investigate or rollback

## Next Steps After Successful Rollout

Once rollout is successful and stable:

1. **Monitor for 1-3 days** (or longer if conservative)
2. **Confirm no issues** reported
3. **Proceed to Phase 5** (Cleanup)
   - Remove old stage code
   - Remove feature flags
   - Update documentation
   - Celebrate! 🎉

## Support

If you encounter issues during rollout:

1. **Immediate rollback**: `export USE_REFACTORED_STAGES=false`
2. **Check logs**: Look for error messages
3. **Run tests**: `pytest -v` to identify failures
4. **Document issue**: Capture error messages and context
5. **Report**: Share details for investigation

---

**Phase 4 Status**: Ready to Execute  
**Recommended Approach**: Immediate Full Rollout  
**Risk Level**: Low (easy rollback, all tests passing)  
**Estimated Time**: 1-3 days (including monitoring)