# Social Security Early Filing Tax Strategy Analysis

## Date: 2026-03-08

## Executive Summary

When taking Social Security (SSI) early (before age 70), there are **critical tax implications** that affect the life stage priority and overall retirement tax strategy. The current implementation has Stage 5 (Social Security) taking precedence correctly, but there are important considerations around ACA subsidies, IRMAA, Traditional IRA distributions, and Roth conversions that need careful review.

## Key Question: Should Stage 5 Take Priority Over Stage 4 or 3?

**Answer: YES - Stage 5 should take priority, and it currently does in the implementation.**

However, the **tax strategy within Stage 5 needs enhancement** to better handle the complex interactions between:
1. Social Security income (up to 85% taxable)
2. ACA subsidies (if under 65)
3. IRMAA surcharges (2-year lookback)
4. Traditional IRA distributions
5. Roth conversions
6. Pending RMDs (planning ahead)

---

## Current Life Stage Precedence (Correct)

| Stage | Trigger | Priority Logic |
|-------|---------|----------------|
| **Stage 3: Early Retirement** | Retired, no SS, both under Medicare age | Aggressive Roth conversions in low-tax window |
| **Stage 4: Medicare** | On Medicare, no SS yet | IRMAA-aware conversions, moderate strategy |
| **Stage 5: Social Security** | Collecting SS, on Medicare | **SS income constrains conversions** |
| **Stage 6: RMD** | Either spouse reaches RMD age (73) | RMDs force income, limited conversion room |

### Why Stage 5 Takes Priority (Correctly)

Once Social Security begins, it **fundamentally changes the tax landscape**:

1. **SS Income is Taxable**: Up to 85% of SS benefits are included in taxable income
2. **Reduces Conversion Room**: SS income fills up lower tax brackets
3. **Affects ACA Subsidies**: If under 65, SS income counts toward MAGI for subsidy calculations
4. **Impacts IRMAA**: SS income in year Y affects IRMAA surcharges in year Y+2
5. **Limits Traditional Distributions**: Less room for tax-efficient Traditional IRA withdrawals

---

## Tax Implications Analysis

### 1. Social Security Taxation

**Current Implementation (Lines 4050-4051):**
```python
# 85% of SS is taxable at higher incomes
taxable_ss = ss_benefits * TAXABLE_SS_RATE  # TAXABLE_SS_RATE = 0.85
```

**Tax Treatment:**
- 0% taxable if combined income < $32,000 (MFJ)
- 50% taxable if combined income $32,000-$44,000 (MFJ)
- 85% taxable if combined income > $44,000 (MFJ)

**Current Issue:** The code assumes 85% is always taxable. This is conservative but may overstate taxes for lower-income retirees.

**Combined Income Formula:**
```
Combined Income = AGI + Nontaxable Interest + 50% of SS Benefits
```

### 2. ACA Subsidy Impact (Critical for Early SS Filers)

**Scenario:** Person takes SS at 62, not yet on Medicare (age 62-64)

**Current Implementation:**
- ACA premium calculation: `calculate_aca_premium_for_year()` (lines 220-256)
- ACA subsidy calculation: `calculate_aca_subsidy()` (lines 5279-5322)

**Problem:** The current code calculates ACA **premiums** but doesn't fully integrate ACA **subsidies** into the Stage 5 strategy.

**ACA Subsidy Cliff:**
- Subsidies available if MAGI < 400% FPL (~$75,000 for couple in 2026)
- **SS income counts toward MAGI** for subsidy calculation
- Taking SS early can **eliminate ACA subsidies**, costing $10,000-$15,000/year

**Example:**
```
Scenario A (No SS): MAGI = $50,000 → ACA subsidy = $12,000/yr
Scenario B (With SS): MAGI = $80,000 → ACA subsidy = $0/yr
Net Cost of Early SS: $12,000/yr in lost subsidies (ages 62-64)
```

### 3. IRMAA Impact (2-Year Lookback)

**Current Implementation (Lines 4046-4048, 4091-4099):**
```python
# Calculate IRMAA based on prior_magi (2 years ago)
irmaa_penalty = calculate_irmma_penalty(prior_magi, irmaa_brackets, people_on_medicare)

# Find next IRMAA threshold
next_irmaa_threshold = ...
irmaa_headroom = next_irmaa_threshold - current_income - std_deduction
```

**IRMAA Brackets (2026, MFJ):**
| MAGI Range | Part B Monthly | Part D Monthly | Annual Surcharge |
|------------|----------------|----------------|------------------|
| ≤ $206,000 | $174.70 | $0 | $0 |
| $206,001-$258,000 | $244.60 | $12.90 | $1,528/person |
| $258,001-$322,000 | $349.40 | $33.30 | $2,792/person |
| $322,001-$386,000 | $454.20 | $53.80 | $4,056/person |
| $386,001-$750,000 | $559.00 | $74.20 | $5,320/person |
| > $750,000 | $594.00 | $81.00 | $5,740/person |

**Critical Insight:**
- **Year Y SS income** affects **Year Y+2 IRMAA**
- Taking SS at 62 means IRMAA impact starts at age 64 (if on Medicare at 65)
- Must plan Roth conversions in Year Y considering Year Y+2 IRMAA

**Current Code Handles This:** Lines 4126-4151 limit conversions to avoid crossing IRMAA thresholds.

### 4. Traditional IRA Distribution Strategy

**Current Implementation (Lines 4065-4086):**
```python
# Calculate withdrawal need (SS covers part of expenses)
withdrawal_need = max(0, expenses + irmaa_penalty - ss_benefits)

# Harvest LTCG if needed
ltcg_harvested = 0
if withdrawal_need > 0 and balances.taxable > 0:
    # Calculate 0% LTCG room after accounting for SS income
    ltcg_room = max(0, cg_0_percent_limit - taxable_ss - std_deduction)
```

**Strategy:**
1. SS income reduces need for Traditional IRA distributions
2. Prioritize LTCG harvesting in 0% bracket (after SS income)
3. Only withdraw from Traditional if needed for expenses

**Issue:** Code doesn't explicitly consider **strategic Traditional distributions** to fill up lower brackets before RMDs begin.

### 5. Roth Conversion Strategy with SS Income

**Current Implementation (Lines 4102-4174):**
Uses BETR (Break-Even Tax Rate) algorithm to optimize conversions:

```python
optimal_amount, betr_results = optimize_conversion_amount(
    traditional_ira_balance=balances.traditional,
    current_agi=current_income,  # Includes taxable SS
    target_tax_bracket=max_conversion_rate,
    ...
)
```

**Key Considerations:**
1. **SS income fills lower brackets** → Less room for conversions
2. **IRMAA headroom** limits conversions (lines 4126-4151)
3. **Must balance** current tax cost vs. future RMD tax savings

**Current Code Strength:** Lines 4126-4151 properly limit conversions to avoid IRMAA cliffs.

**Potential Enhancement:** Consider multi-year optimization that accounts for:
- Years until RMDs (currently done: line 4117)
- Expected SS income growth (COLA adjustments)
- Spouse's SS timing (if different ages)

### 6. RMD Planning (Forward-Looking)

**Current Implementation:**
- Stage 5 applies when `older_age < RMD_AGE` (line 4015)
- Transitions to Stage 6 when older spouse reaches 73

**RMD Calculation:**
```
RMD = Traditional IRA Balance / Life Expectancy Factor
Age 73: Factor = 26.5 → RMD = Balance / 26.5 ≈ 3.77% of balance
Age 80: Factor = 20.2 → RMD = Balance / 20.2 ≈ 4.95% of balance
```

**Critical Planning Window:**
- **Ages 62-72** (if taking SS at 62): 10 years to reduce Traditional IRA
- **Goal:** Minimize Traditional IRA balance before RMDs begin
- **Constraint:** SS income limits annual conversion capacity

**Example:**
```
Traditional IRA at 62: $1,000,000
Annual SS income: $60,000 (taxable: $51,000)
Target bracket: 24%
Available conversion room: ~$30,000-$50,000/year (after SS income)
10-year conversion capacity: $300,000-$500,000
Remaining balance at 73: $500,000-$700,000
RMD at 73: $18,868-$26,415/year (forced income)
```

---

## Recommended Enhancements

### 1. **ACA Subsidy Integration** (High Priority)

**Problem:** Stage 5 doesn't explicitly calculate and optimize for ACA subsidies when person is 62-64.

**Solution:**
```python
# In Stage 5, calculate_strategy():
if age_primary < MEDICARE_AGE or age_spouse < MEDICARE_AGE:
    # Calculate ACA subsidy based on projected MAGI
    subsidy, net_premium = calculate_aca_subsidy(
        magi=projected_magi,
        year=year,
        household_size=2
    )
    
    # Consider subsidy cliff in conversion decisions
    aca_subsidy_threshold = fpl_400_percent  # ~$75,000 for couple
    if projected_magi + roth_conversion > aca_subsidy_threshold:
        # Reduce conversion to preserve subsidy
        max_conversion_with_subsidy = aca_subsidy_threshold - projected_magi
        roth_conversion = min(roth_conversion, max_conversion_with_subsidy)
```

**Impact:** Could save $10,000-$15,000/year in ACA subsidies for ages 62-64.

### 2. **SS Taxation Accuracy** (Medium Priority)

**Problem:** Code assumes 85% of SS is always taxable (conservative but inaccurate).

**Solution:**
```python
def calculate_ss_taxable_amount(ss_benefits: float, agi_without_ss: float) -> float:
    """Calculate actual taxable portion of SS benefits"""
    combined_income = agi_without_ss + (ss_benefits * 0.5)
    
    if combined_income <= 32000:  # MFJ thresholds
        return 0
    elif combined_income <= 44000:
        return min(ss_benefits * 0.5, (combined_income - 32000) * 0.5)
    else:
        return min(
            ss_benefits * 0.85,
            0.85 * (combined_income - 44000) + 0.5 * min(12000, combined_income - 32000)
        )
```

**Impact:** More accurate tax calculations, especially for lower-income retirees.

### 3. **Multi-Year RMD Planning** (Medium Priority)

**Problem:** Stage 5 optimizes year-by-year but doesn't explicitly plan for RMD impact.

**Solution:**
```python
# Add to Stage 5 decision log:
years_to_rmd = RMD_AGE - older_age
projected_rmd = balances.traditional / get_life_expectancy_factor(RMD_AGE)

dl.add(
    "rmd_planning",
    "RMD Planning",
    f"{years_to_rmd} years until RMDs, projected RMD: ${projected_rmd:,.0f}",
    f"With {years_to_rmd} years remaining, we can convert approximately "
    f"${roth_conversion * years_to_rmd:,.0f} total before RMDs begin. "
    f"This will reduce the projected RMD from ${projected_rmd:,.0f} to "
    f"${projected_rmd * 0.7:,.0f} (assuming 30% reduction).",
    years_to_rmd=years_to_rmd,
    current_traditional=f"${balances.traditional:,.0f}",
    projected_rmd=f"${projected_rmd:,.0f}",
)
```

**Impact:** Better visibility into long-term RMD impact and conversion strategy.

### 4. **Stage Transition Warning** (Low Priority)

**Problem:** Users may not realize when taking SS early affects their tax strategy.

**Solution:**
Add a warning in the UI when SS begins before age 70:
```python
if ss_benefits > 0 and age_primary < 70:
    st.warning(
        f"⚠️ **Early Social Security Impact**: Taking SS at age {age_primary} "
        f"adds ${ss_benefits * 0.85:,.0f} of taxable income annually, which "
        f"reduces Roth conversion capacity and may affect ACA subsidies (if under 65) "
        f"and IRMAA surcharges (2-year lookback)."
    )
```

---

## Decision Matrix: When to Take SS Early

| Factor | Take SS at 62 | Wait Until 70 |
|--------|---------------|---------------|
| **ACA Subsidy** (62-64) | ❌ Lose $10k-15k/yr | ✅ Keep subsidy |
| **Roth Conversion Room** | ❌ Reduced by ~$50k/yr | ✅ Full room available |
| **IRMAA Impact** | ⚠️ Higher MAGI → IRMAA | ✅ Lower MAGI pre-70 |
| **Longevity Risk** | ❌ Lower lifetime benefit | ✅ Higher lifetime benefit |
| **Cash Flow Need** | ✅ Immediate income | ❌ Must draw from portfolio |
| **Portfolio Preservation** | ✅ Less portfolio draw | ❌ More portfolio draw |
| **Tax Bracket** | ⚠️ Fills lower brackets | ✅ More conversion room |

**Optimal Strategy (Generally):**
1. **Wait until 70** if you have sufficient portfolio assets and want to maximize:
   - Roth conversion capacity (ages 62-69)
   - ACA subsidies (ages 62-64)
   - Lifetime SS benefits
   
2. **Take at 62-67** if you:
   - Need cash flow and portfolio is insufficient
   - Have health concerns (shorter life expectancy)
   - Want to preserve portfolio for heirs
   - Are in high tax bracket now, expect lower bracket later (rare)

---

## Current Implementation Assessment

### ✅ **Strengths:**
1. **Correct stage precedence**: Stage 5 properly takes priority when SS begins
2. **IRMAA awareness**: Lines 4126-4151 limit conversions to avoid IRMAA cliffs
3. **BETR optimization**: Uses sophisticated algorithm for conversion decisions
4. **2-year lookback**: Properly uses `prior_magi` for IRMAA calculations
5. **SS taxation**: Includes taxable SS in income calculations

### ⚠️ **Areas for Enhancement:**
1. **ACA subsidy integration**: Not explicitly optimized in Stage 5
2. **SS taxation accuracy**: Assumes 85% always taxable (conservative)
3. **Multi-year RMD planning**: Year-by-year optimization only
4. **User warnings**: No explicit warnings about early SS tax impact

### 🔧 **Recommended Priority:**
1. **High**: Add ACA subsidy optimization to Stage 5 (ages 62-64)
2. **Medium**: Improve SS taxation calculation accuracy
3. **Medium**: Add multi-year RMD planning visibility
4. **Low**: Add UI warnings for early SS tax implications

---

## Conclusion

**The current life stage precedence is CORRECT**: Stage 5 (Social Security) should and does take priority over Stages 3 and 4 once SS benefits begin. The tax strategy within Stage 5 is sophisticated and handles most scenarios well.

**Key Insight**: Taking Social Security early (before 70) has significant tax implications:
- Reduces Roth conversion capacity by $30,000-$50,000/year
- May eliminate ACA subsidies ($10,000-$15,000/year loss for ages 62-64)
- Increases IRMAA risk (2-year lookback)
- Limits Traditional IRA distribution flexibility

**Recommendation**: The code is solid, but consider the **ACA subsidy integration** enhancement for users taking SS before Medicare eligibility. This is the most significant gap in the current implementation.

The other enhancements (SS taxation accuracy, multi-year RMD planning) are nice-to-have improvements but not critical for correct tax strategy execution.