# Monte Carlo 0% Success Probability Bug - RESOLVED

## Issue Summary

User reported getting **0% success probability** when running Monte Carlo simulation with these parameters:
- Starting Portfolio: $2,689,454
- Annual Withdrawal: $60,000
- Retirement Age: 62
- Plan To Age: 85

## Root Cause

The bug was caused by **inflation rate being stored as a percentage (2.9) instead of a decimal (0.029)** in the session state.

### Technical Details

In [`pages/6_monte_carlo.py`](pages/6_monte_carlo.py:137-143), the inflation slider was defined as:

```python
_mc_inflation = st.slider(
    "Inflation Rate", min_value=1.0, max_value=10.0,
    value=_default_inflation * 100, step=0.1, format="%.1f%%", key="mc_inflation",
) / 100
```

The slider displays values like "2.9%" and divides by 100 to get 0.029. However, **Streamlit's session state was storing the slider's raw value (2.9) before the division**, not the divided result (0.029).

When [`_build_mc_inputs()`](pages/6_monte_carlo.py:158-172) retrieved the value:

```python
inflation_rate=float(st.session_state.get("mc_inflation", 0.029)),
```

It got **2.9 instead of 0.029**, which the simulation interpreted as **290% inflation** instead of 2.9%.

### Impact

With 290% inflation:
- Year 1 withdrawal: $60,000
- Year 2 withdrawal: $234,000 (grows by 290%)
- Year 3 withdrawal: $912,600
- Portfolio depletes in ~2-3 years in ALL scenarios
- Result: **0% success probability**

## The Fix

Changed the slider to use a separate key for the percentage value and explicitly store the decimal value in session state:

```python
_mc_inflation_pct = st.slider(
    "Inflation Rate", min_value=1.0, max_value=10.0,
    value=_default_inflation * 100, step=0.1, format="%.1f%%", key="mc_inflation_pct",
)
_mc_inflation = _mc_inflation_pct / 100
st.session_state["mc_inflation"] = _mc_inflation  # Explicitly store decimal value
```

## Verification

After the fix, the same parameters now show:
- **Success Probability: 100%**
- Median Final Portfolio: $11,060,644
- 10th Percentile Final: $5,808,345

This is the correct result because:
1. Initial withdrawal rate is only 2.23% ($60k / $2.69M)
2. Portfolio expected return is 8.41% (Moderate 70/30 allocation)
3. Even with 2.9% inflation, the portfolio grows faster than withdrawals
4. Over 23 years, the portfolio has excellent success probability

## Testing

Created diagnostic scripts to verify:
- [`diagnostic_monte_carlo.py`](diagnostic_monte_carlo.py) - Shows year-by-year portfolio progression
- [`debug_mc_inputs.py`](debug_mc_inputs.py) - Tests various input scenarios including the bug

## Recommendations for Users

If you're still seeing 0% success probability after this fix:

1. **Clear your browser cache** and reload the page
2. **Check Social Security settings** - Default is $40k/year at age 70
3. **Verify inflation rate** - Should show as "2.9%" in the slider
4. **Check the simulation results** - Look for notes about inflation rate
5. **Try adjusting parameters**:
   - Reduce withdrawal to $50k/year
   - Add Social Security income
   - Delay retirement to age 65
   - Use a more conservative allocation initially

## Files Modified

- [`pages/6_monte_carlo.py`](pages/6_monte_carlo.py:136-143) - Fixed inflation rate storage

## Files Created

- [`diagnostic_monte_carlo.py`](diagnostic_monte_carlo.py) - Diagnostic tool
- [`debug_mc_inputs.py`](debug_mc_inputs.py) - Input validation tool
- `MONTE_CARLO_BUG_FIX.md` - This documentation

---

**Status**: ✅ RESOLVED

**Date**: 2026-03-03

**Impact**: Critical - Affected all Monte Carlo simulations with custom inflation rates