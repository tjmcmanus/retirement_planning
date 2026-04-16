# IRMAA Calculation Fix for Stage 6 and Stage 7

## Issue
The Healthcare Cost column was showing $0 in Stage 6 (RMD years) and Stage 7 (Surviving Spouse) despite MAGI being in the $400K-$500K range, which should trigger significant IRMAA penalties.

## Root Causes

### 1. Incorrect Field Assignment (Primary Bug)
In both `strategy_core/stages/stage6_rmd.py` and `strategy_core/stages/stage7_surviving_spouse.py`, the code was incorrectly assigning the wrong healthcare cost component to `strategy.irmaa_penalty`:

**Incorrect code:**
```python
strategy.irmaa_penalty = healthcare_costs['medical_costs']
```

**Correct code:**
```python
strategy.irmaa_penalty = healthcare_costs['irmaa_penalty']
```

### 2. Incorrect Import Statement (Secondary Bug)
Both stages were trying to import `calculate_total_healthcare_costs` from the wrong module:

**Incorrect import:**
```python
from calculations import calculate_total_healthcare_costs
```

**Correct import:**
```python
from strategy import calculate_total_healthcare_costs
```

This caused the healthcare calculation to fail silently and return default values of 0.0 for all fields.

## Healthcare Costs Dictionary Structure
The `_calculate_healthcare_costs()` method returns a dictionary with three components:
- `medical_costs`: Total Medicare costs including IRMAA
- `aca_premium`: ACA premium costs (for pre-Medicare ages)
- `irmaa_penalty`: Just the IRMAA penalty portion

## How Healthcare Cost is Displayed
In `strategy.py` line 4108, the Healthcare Cost column is calculated as:
```python
'Healthcare Cost': s.irmaa_penalty + s.aca_premium
```

By incorrectly assigning `medical_costs` to `irmaa_penalty`, the field was being set to the total Medicare costs (which includes base Medicare premiums + IRMAA), but then the display logic was adding `aca_premium` to it, which would be incorrect.

## Files Fixed

### strategy_core/stages/stage6_rmd.py
- Line 351: Changed field assignment from `medical_costs` to `irmaa_penalty`
- Line 443: Changed import from `calculations` to `strategy`

### strategy_core/stages/stage7_surviving_spouse.py
- Line 349: Changed field assignment from `medical_costs` to `irmaa_penalty`
- Line 416: Changed import from `calculations` to `strategy`

## Impact
- Stage 6 (RMD years 2039-2044) will now correctly show IRMAA penalties in the Healthcare Cost column
- Stage 7 (Surviving Spouse) will now correctly show IRMAA penalties
- With MAGI around $400K-$500K, IRMAA penalties should be substantial (likely in the range of $5,000-$10,000+ per year for married filing jointly)
- The healthcare cost calculation will no longer fail silently due to import errors

## Testing
To verify the fix:
1. Run a strategy with RMD years (Stage 6)
2. Check that MAGI is in the $400K-$500K range
3. Verify that the Healthcare Cost column shows non-zero values
4. The IRMAA penalty should be calculated based on MAGI from 2 years prior (2-year lookback rule)
5. Check the logs to ensure no "Could not calculate healthcare costs" warnings appear

## Related Code
- IRMAA calculation: `strategy_core/tax_calculator.py` - `calculate_irmaa_penalty()` method
- Healthcare cost calculation: `strategy.py` - `calculate_total_healthcare_costs()` function
- Healthcare breakdown model: `strategy_core/models.py` - `HealthcareCostBreakdown` class
- Display logic: `strategy.py` line 4108