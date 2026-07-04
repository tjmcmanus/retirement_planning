# Life Stage Precedence Update for Age-Gapped Marriages

## Date: 2026-03-08

## Summary
Updated the retirement planning strategy to ensure the **OLDER spouse's life stage takes precedence** for tax strategy decisions in age-gapped marriages. This provides a more conservative and tax-efficient approach.

## Changes Made

### 1. Stage 4: Medicare Stage (Lines 3664-3674)
**Before:**
```python
def applies(self, age_primary: int, age_spouse: int, year: int,
            has_wages: bool, has_ss: bool) -> bool:
    """Applies when on Medicare but before SS and RMDs"""
    return (not has_wages and not has_ss and
            (age_primary >= MEDICARE_AGE or age_spouse >= MEDICARE_AGE) and
            age_primary < RMD_AGE)
```

**After:**
```python
def applies(self, age_primary: int, age_spouse: int, year: int,
            has_wages: bool, has_ss: bool) -> bool:
    """Applies when on Medicare but before SS and RMDs.
    
    Uses the OLDER spouse's age for RMD threshold to ensure tax strategy
    is driven by the person closest to RMD age (more conservative approach).
    """
    older_age = max(age_primary, age_spouse)
    return (not has_wages and not has_ss and
            (age_primary >= MEDICARE_AGE or age_spouse >= MEDICARE_AGE) and
            older_age < RMD_AGE)
```

**Impact:** Stage 4 now transitions to Stage 5 when the OLDER spouse reaches RMD age, not just Person 1.

### 2. Stage 5: Social Security Stage (Lines 3997-4006)
**Before:**
```python
def applies(self, age_primary: int, age_spouse: int, year: int,
            has_wages: bool, has_ss: bool) -> bool:
    """Applies when collecting SS but before RMDs"""
    return (not has_wages and has_ss and age_primary < RMD_AGE)
```

**After:**
```python
def applies(self, age_primary: int, age_spouse: int, year: int,
            has_wages: bool, has_ss: bool) -> bool:
    """Applies when collecting SS but before RMDs.
    
    Uses the OLDER spouse's age for RMD threshold to ensure tax strategy
    is driven by the person closest to RMD age (more conservative approach).
    """
    older_age = max(age_primary, age_spouse)
    return (not has_wages and has_ss and older_age < RMD_AGE)
```

**Impact:** Stage 5 now transitions to Stage 6 when the OLDER spouse reaches RMD age, ensuring RMD planning begins at the appropriate time.

### 3. Stage 3: Early Retirement (Lines 3391-3401)
**No Change - Intentional:**
Stage 3 continues to require BOTH spouses to be under Medicare age. This is correct because:
- Stage 3 is the optimal window for aggressive Roth conversions
- Once either spouse reaches Medicare age, IRMAA considerations begin
- The transition to Stage 4 when the OLDER spouse reaches Medicare is already handled by Stage 4's OR logic

## Rationale

### Why the Older Spouse Should Take Precedence:

1. **Medicare/IRMAA Considerations:**
   - IRMAA surcharges are based on household MAGI from 2 years prior
   - When the older spouse reaches Medicare age, the household must start managing IRMAA
   - This affects Roth conversion strategy for the entire household

2. **RMD Planning:**
   - RMDs force taxable income that affects the entire household's tax situation
   - Planning must begin before the older spouse reaches RMD age (73)
   - Waiting until Person 1 reaches RMD age could miss critical planning years

3. **Social Security Taxation:**
   - SS benefits are taxed at the household level
   - Combined income from both spouses determines taxation
   - RMDs from the older spouse increase household income and SS taxation

4. **Tax Bracket Management:**
   - The household files jointly (married filing jointly)
   - Income from either spouse affects the household tax bracket
   - Conservative approach: plan for the older spouse's milestones

## Stage Precedence Summary

| Stage | Precedence Rule | Rationale |
|-------|----------------|-----------|
| Stage 1: Accumulation | Latest (younger) retirement | Keep accumulating until last person retires |
| Stage 2: Prep for Retirement | Latest (younger) retirement | Prep window based on last retirement date |
| Stage 3: Early Retirement | BOTH under Medicare age | Maximize Roth conversion window |
| Stage 4: Medicare | Either reaches Medicare, older for RMD | IRMAA planning, conservative RMD transition |
| Stage 5: Social Security | Has SS, older for RMD | Conservative RMD transition |
| Stage 6: RMD | Either reaches RMD age | RMDs affect entire household |

## Testing Recommendations

1. Test with age gap scenarios:
   - Person 1 older (e.g., 65 and 60)
   - Person 2 older (e.g., 60 and 65)
   - Large age gap (e.g., 70 and 55)

2. Verify stage transitions occur at correct ages

3. Confirm Roth conversion strategy adjusts appropriately

4. Check IRMAA calculations use correct lookback periods

## Files Modified

- `strategy.py` (Lines 3664-3674, 3997-4006, 3391-3401)

## Backward Compatibility

This change may affect existing retirement plans where:
- Person 1 is younger than Person 2
- The plan was previously transitioning stages based on Person 1's age

**Action Required:** Users with age-gapped marriages should review their strategy projections to ensure the new logic produces expected results.