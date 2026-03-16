# Stage 5 AGI and Roth Conversion Fix

## Issue Identified

In **Stage 5: Social Security**, the BETR-based Roth conversion optimization is not including Traditional IRA withdrawals (Trad→Cash and Trad→Brok) in the `current_agi` calculation when determining conversion amounts. This causes the system to recommend conversions that push income into higher tax brackets than intended.

### Problem Description

Looking at your 2036 data:
- **Year 2036**: Converting $100,000 to Roth at 24% bracket
- **Trad→Cash**: $62,838.24 (ordinary income)
- **Trad→Brok**: $171,715.33 (ordinary income for buffer replenishment)
- **Total Traditional withdrawals**: $234,553.57
- **Roth Conversion**: $100,000
- **AGI**: $731,089.03
- **Federal Tax**: $155,089
- **Marginal Rate**: Likely 32% or higher (not the target 24%!)

The conversion optimizer is calculating bracket room **without** considering the Traditional withdrawals that will happen during `rebalance_accounts()`. This leads to over-conversions.

## Root Cause Analysis

### Location: Stage 5 (Social Security Stage)
**File:** `strategy.py`  
**Lines:** 5440-5496

### The Problem Code

```python
# Line 5440-5441: Only includes taxable SS in current_income
current_income = taxable_ss

# Lines 5486-5496: BETR optimization uses incomplete current_agi
optimal_amount, betr_results = optimize_conversion_amount(
    traditional_ira_balance=available_traditional,
    current_agi=current_income,  # ❌ Missing Trad→Cash and Trad→Brok!
    target_tax_bracket=max_conversion_rate,
    year=year,
    pay_from_taxable=True,
    taxable_account_balance=balances.taxable,
    years_to_withdrawal=(73 - age_primary) if age_primary > 0 else 10,
    annual_return=kwargs.get('growth_rate', 1.07) - 1.0
)
```

### Why This Happens

1. **Stage 5 Flow**:
   - Calculate preliminary conversion based on SS income only (line 5441)
   - Call `optimize_conversion_amount()` with incomplete AGI (line 5487-5496)
   - Later call `rebalance_accounts()` which withdraws from Traditional for buffer needs (line 5632)
   - **Problem**: The conversion was calculated BEFORE knowing about Traditional withdrawals

2. **Missing Components**:
   - `current_income` only includes `taxable_ss`
   - Does NOT include anticipated Traditional withdrawals for buffer replenishment
   - Does NOT include any LTCG that might be harvested

3. **Timing Issue**:
   - Conversion amount is calculated BEFORE `rebalance_accounts()`
   - But `rebalance_accounts()` determines actual Traditional withdrawals
   - This creates a chicken-and-egg problem

## Solution Strategy

### Approach 1: Pre-calculate Buffer Needs (Recommended)

Similar to Stage 3's fix, we need to calculate anticipated Traditional withdrawals BEFORE the conversion optimization:

```python
# NEW CODE (CORRECT):
# Calculate anticipated buffer needs BEFORE conversion optimization
anticipated_needs = calculate_anticipated_buffer_needs(
    balances=balances_with_ss,  # After adding SS benefits
    expenses=expenses,
    year=year,
    start_year=kwargs.get('start_year', year),
    stage=self.name
)

# Include ALL anticipated ordinary income in current_income
current_income = (taxable_ss + 
                 anticipated_needs['traditional_to_cash'] + 
                 anticipated_needs['traditional_to_brokerage'])

# Now BETR optimization sees the complete picture
optimal_amount, betr_results = optimize_conversion_amount(
    traditional_ira_balance=available_traditional,
    current_agi=current_income,  # ✅ Now includes all Traditional withdrawals!
    target_tax_bracket=max_conversion_rate,
    ...
)
```

### Approach 2: Post-rebalance Conversion (Alternative)

Move the conversion calculation AFTER `rebalance_accounts()` so we know the actual withdrawals:

```python
# Execute rebalancing first (without conversion)
new_balances, transactions, rebal_dl = rebalance_accounts(
    balances=balances_for_rebalance,
    expenses=expenses,
    roth_conversion=0,  # No conversion yet
    ...
)

# Now calculate conversion with known Traditional withdrawals
actual_trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage']
current_income = taxable_ss + actual_trad_withdrawal

# Calculate optimal conversion
optimal_amount, betr_results = optimize_conversion_amount(
    current_agi=current_income,  # ✅ Now includes actual withdrawals
    ...
)

# Execute conversion separately if beneficial
```

## Recommended Fix: Approach 1

**Approach 1** is recommended because:
1. **Consistent with Stage 3**: Uses the same `calculate_anticipated_buffer_needs()` pattern
2. **Single rebalancing pass**: Avoids the complexity of multiple rebalancing calls
3. **Predictable**: Buffer needs are deterministic based on targets and current balances

## Implementation Details

### Step 1: Add Buffer Needs Calculation

Insert after line 5419 (after buffer target calculation):

```python
# Calculate anticipated buffer needs BEFORE conversion optimization
anticipated_needs = calculate_anticipated_buffer_needs(
    balances=balances_with_ss,  # After adding SS benefits
    expenses=expenses,
    year=year,
    start_year=kwargs.get('start_year', year),
    stage=self.name
)

logger.debug(f"Anticipated buffer needs: Trad→Cash=${anticipated_needs['traditional_to_cash']:,.0f}, "
            f"Trad→Brok=${anticipated_needs['traditional_to_brokerage']:,.0f}")
```

### Step 2: Update Current Income Calculation

Replace line 5441:

```python
# OLD:
current_income = taxable_ss

# NEW:
# Include ALL anticipated ordinary income for accurate bracket calculation
current_income = (taxable_ss + 
                 anticipated_needs['traditional_to_cash'] + 
                 anticipated_needs['traditional_to_brokerage'])

logger.debug(f"Current income for conversion calc: SS=${taxable_ss:,.0f} + "
            f"Trad→Cash=${anticipated_needs['traditional_to_cash']:,.0f} + "
            f"Trad→Brok=${anticipated_needs['traditional_to_brokerage']:,.0f} = "
            f"${current_income:,.0f}")
```

### Step 3: Update Available Traditional Balance

Replace line 5483:

```python
# OLD:
available_traditional = balances.traditional

# NEW:
# Subtract anticipated Traditional withdrawals from available balance
available_for_conversion = (balances.traditional - 
                           anticipated_needs['traditional_to_cash'] - 
                           anticipated_needs['traditional_to_brokerage'])

logger.debug(f"Available for conversion: ${balances.traditional:,.0f} - "
            f"${anticipated_needs['traditional_to_cash'] + anticipated_needs['traditional_to_brokerage']:,.0f} = "
            f"${available_for_conversion:,.0f}")
```

### Step 4: Update BETR Call

Update line 5488:

```python
# OLD:
traditional_ira_balance=available_traditional,

# NEW:
traditional_ira_balance=available_for_conversion,
```

## Expected Impact

### Your 2036 Example

**Before Fix**:
- `current_income` = $62,838 (taxable SS only)
- Conversion optimizer thinks there's ~$137k room in 24% bracket
- Recommends $100k conversion
- **Actual AGI**: $731k (way over 24% bracket!)
- **Actual rate**: 32%+ marginal

**After Fix**:
- `current_income` = $62,838 + $171,715 = $234,553
- Conversion optimizer sees much less room in 24% bracket
- Recommends much smaller conversion (maybe $20-30k)
- **Actual AGI**: ~$300-350k (stays in 24% bracket)
- **Actual rate**: 24% marginal ✅

### Verification Steps

1. **Check AGI components**: AGI should equal SS + Trad withdrawals + Roth conversion + LTCG
2. **Verify marginal rate**: Should stay at target (24%) not exceed it
3. **Compare conversion amounts**: Should be smaller when Traditional withdrawals are large
4. **Review decision log**: Should show proper bracket room calculation

## Files to Modify

1. **strategy.py** - Stage 5 class (`Stage5SocialSecurity.calculate_strategy()`)
   - Add buffer needs calculation
   - Update current income calculation
   - Update available Traditional balance
   - Add debug logging

## Testing

Create test case that verifies:
1. Traditional withdrawals are included in AGI calculation
2. Conversion amounts respect the target bracket
3. Final marginal rate matches target rate
4. AGI components sum correctly

## Date

**Identified**: 2026-03-16  
**Status**: Ready for implementation

---

**Made with IBM Bob**