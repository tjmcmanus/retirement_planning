# Cash Balance Calculation Issue - Analysis and Fix

## Issue Summary

The refactored stage implementations are not properly deducting expenses, healthcare costs, and taxes from the cash balance, resulting in incorrect ending cash balances that are higher than they should be.

## Root Cause Analysis

### How Original `strategy.py` Handles Cash

In the original `strategy.py`, the `rebalance_accounts()` function (lines 3173-3700) follows this sequence:

1. **Step 1: Deduct ALL costs from cash FIRST** (lines 3249-3274)
   ```python
   total_cash_outflow = expenses + federal_tax + irmaa_penalty + aca_premium + medical_costs
   
   balances = PortfolioBalances(
       cash=balances.cash - total_cash_outflow,
       taxable=balances.taxable,
       traditional=balances.traditional,
       roth=balances.roth,
       daf=balances.daf
   )
   ```

2. **Step 2: Replenish cash buffer if needed** (lines 3276-3500)
   - Calculate cash deficit after deductions
   - Transfer funds from Brokerage → Cash
   - If Brokerage insufficient, transfer Traditional → Cash

3. **Step 3: Maintain brokerage buffer** (lines 3500+)
   - Transfer Traditional → Brokerage if needed

4. **Step 4: Execute Roth conversions** (if applicable)

5. **Return updated balances** with all deductions applied

### How Refactored Stages Handle Cash

The refactored stages (e.g., `stage6_rmd.py`, `stage5_social_security.py`) follow a different pattern:

1. **Add income to cash** (e.g., SS benefits)
   ```python
   balances_with_ss = PortfolioBalances(
       cash=balances.cash + ss_benefits,
       ...
   )
   ```

2. **Call `rebalance_accounts()` from `strategy.py`**
   ```python
   new_balances, transactions = self._execute_rebalancing(
       balances_for_rebalance, expenses, roth_conversion, year, age_primary,
       total_tax, healthcare_costs, brokerage_account
   )
   ```

3. **Apply growth to all accounts**
   ```python
   new_balances = PortfolioBalances(
       cash=new_balances.cash,
       taxable=new_balances.taxable * growth_rate,
       ...
   )
   ```

4. **Return strategy with new_balances**

## The Problem

The refactored stages ARE calling `rebalance_accounts()` which DOES deduct expenses/taxes/healthcare from cash. However, there may be an issue with:

1. **Timing of deductions**: The stages add income (SS benefits) to cash, then call rebalancing, which should deduct costs. This should work correctly.

2. **Missing state tax deduction**: State taxes are calculated AFTER rebalancing but may not be deducted from cash balance.

3. **Growth application**: Growth is applied to cash after rebalancing, which could inflate the balance if costs weren't properly deducted first.

## Investigation Findings

Looking at Stage 6 RMD (`stage6_rmd.py` lines 211-274):

```python
# Add SS benefits to cash before rebalancing
balances_with_ss = PortfolioBalances(
    cash=balances.cash + ss_benefits,
    ...
)

# Execute account rebalancing (THIS SHOULD DEDUCT COSTS)
new_balances, transactions = self._execute_rebalancing(
    balances_for_rebalance, expenses, roth_conversion, year, age_primary,
    total_tax, healthcare_costs, brokerage_account
)

# Apply growth
new_balances = PortfolioBalances(
    cash=new_balances.cash,  # <-- Cash is NOT grown
    taxable=new_balances.taxable * growth_rate,
    ...
)
```

**Key observation**: Cash is NOT grown (line 265), which is correct. The `rebalance_accounts()` function IS being called with the correct parameters including `federal_tax`, `irmaa_penalty`, `aca_premium`, and `medical_costs`.

## Likely Issues

### Issue 1: State Tax Not Deducted

State tax is calculated AFTER rebalancing (line 313-316 in stage6_rmd.py):

```python
# Calculate state tax
state_tax = self._calculate_state_tax(
    agi, year, filing_status, trad_withdrawal, roth_conversion, taxable_ss
)
```

But state tax is never deducted from the cash balance! It's only stored in `strategy.state_tax` for reporting.

### Issue 2: Healthcare Costs Structure

The stages pass healthcare costs to `rebalance_accounts()` but the structure may not match:

```python
# Stage 6 passes:
healthcare_costs = {
    'medical_costs': medical_costs,
    'aca_premium': aca_premium,
    'irmaa_penalty': irmaa_penalty
}

# But rebalance_accounts expects separate parameters:
def rebalance_accounts(..., irmaa_penalty: float, aca_premium: float, medical_costs: float, ...)
```

Looking at line 743 in stage6_rmd.py:
```python
new_balances, transactions, rebal_dl = rebalance_accounts(
    balances=balances,
    expenses=expenses,
    roth_conversion=roth_conversion,
    year=year,
    age_primary=age_primary,
    stage=self.name,
    federal_tax=total_tax,
    irmaa_penalty=healthcare_costs['irmaa_penalty'],  # ✓ Correct
    aca_premium=healthcare_costs['aca_premium'],      # ✓ Correct
    medical_costs=healthcare_costs['medical_costs'],  # ✓ Correct
    brokerage_account=brokerage_account,
)
```

This looks correct! The healthcare costs ARE being passed properly.

## Actual Root Cause

After thorough analysis, the issue is likely:

1. **State tax is calculated but never deducted from cash**
2. **The comparison test may be using different assumptions** (e.g., different growth rates, different timing of income additions)

## Recommended Fix

### Fix 1: Deduct State Tax from Cash

Add state tax deduction after it's calculated in each stage:

```python
# Calculate state tax
state_tax = self._calculate_state_tax(...)

# Deduct state tax from cash
new_balances = PortfolioBalances(
    cash=new_balances.cash - state_tax,
    taxable=new_balances.taxable,
    traditional=new_balances.traditional,
    roth=new_balances.roth,
    daf=new_balances.daf
)
```

### Fix 2: Verify Rebalancing is Called Correctly

Ensure all stages call `_execute_rebalancing()` with the correct parameters, especially:
- `federal_tax` (total federal tax including capital gains)
- `irmaa_penalty` (IRMAA surcharge)
- `aca_premium` (ACA premium if applicable)
- `medical_costs` (Medicare/other medical costs)

### Fix 3: Add Validation

Add assertion or logging to verify cash balance decreases after costs:

```python
cash_before = balances.cash
# ... deduct costs ...
cash_after = new_balances.cash
logger.info(f"Cash change: ${cash_before:,.0f} → ${cash_after:,.0f} (Δ ${cash_after - cash_before:,.0f})")
```

## Testing Strategy

1. Create a test that compares cash balances between original and refactored implementations
2. Log all cash movements (income additions, cost deductions)
3. Verify that ending cash = starting cash + income - expenses - taxes - healthcare
4. Check that state tax is properly deducted

## Files to Update

1. `strategy_core/stages/stage6_rmd.py` - Add state tax deduction
2. `strategy_core/stages/stage5_social_security.py` - Add state tax deduction
3. `strategy_core/stages/stage4_medicare.py` - Add state tax deduction (if exists)
4. `strategy_core/stages/stage3_early_retirement.py` - Add state tax deduction
5. All other stage files - Add state tax deduction

## Priority

**HIGH** - This affects the accuracy of all financial projections and could lead to incorrect retirement planning decisions.