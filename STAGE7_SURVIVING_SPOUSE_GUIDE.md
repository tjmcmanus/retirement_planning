# Stage 7: Surviving Spouse Planning Guide

## Overview

Stage 7 is a specialized life stage designed for planning after the loss of a spouse. This stage automatically handles the transition from married couple planning to single person planning, with appropriate tax treatment, benefit optimization, and conservative financial strategies.

## When Stage 7 Applies

Stage 7 activates when:
- **Surviving Spouse Mode** is enabled in Configuration
- A **decedent** (deceased spouse) is selected
- A **date of death** is specified
- The planning year is **after** the year of death

### Important Tax Timing

- **Year of Death**: Uses Married Filing Jointly (MFJ) status
- **Year After Death Onward**: Uses Single filer status

This follows IRS rules that allow surviving spouses to file jointly in the year of death.

## Key Features

### 1. Tax Filing Status Change

**Automatic Single Filer Status:**
- Less favorable tax brackets than MFJ
- Lower standard deduction
- Higher IRMAA thresholds (Medicare surcharges)
- More conservative Roth conversion strategy

**Example Tax Impact:**
```
MFJ 12% Bracket: Up to $89,075 (2024)
Single 12% Bracket: Up to $44,725 (2024)
```

### 2. Social Security Survivor Benefits

**Benefit Optimization:**
- Survivor receives the **higher** of:
  - Their own Social Security benefit
  - 100% of deceased spouse's benefit
- Only **one** benefit is paid (not both)
- Automatically calculated in Stage 7

**Example:**
```
Person 1 Benefit: $3,000/month
Person 2 Benefit: $2,200/month
Survivor Benefit: $3,000/month (higher of two)
```

### 3. Medicare Coverage

**Single Person Coverage:**
- Survivor maintains their own Medicare enrollment
- IRMAA calculated based on survivor's income only
- Part B premium based on single filer MAGI thresholds
- No spouse Medicare costs

### 4. Conservative Roth Conversion Strategy

**Stage 7 Conversion Approach:**
- Default maximum rate: 15% (configurable)
- Uses only **50% of available conversion room**
- Accounts for less favorable single filer brackets
- Prevents over-conversion in higher tax brackets

**Why Conservative?**
Single filer brackets fill up faster, making conversions more expensive. Stage 7 protects against converting too much at unfavorable rates.

### 5. Required Minimum Distributions (RMDs)

**Survivor RMD Rules:**
- Based on survivor's age
- Inherited IRA follows beneficiary RMD rules
- Properly included in AGI and taxable income
- Coordinated with Social Security income

## Configuration Setup

### Step 1: Enable Stage 7 Mode

1. Navigate to **Configuration → Personal Info** tab
2. Scroll to **"Stage 7: Surviving Spouse Planning"** section
3. Check **"Planning for surviving spouse scenario (Stage 7)"**

### Step 2: Select Decedent

1. Choose which person is deceased:
   - Primary Person (Person 1)
   - Spouse/Partner (Person 2)
2. The system automatically identifies the survivor

### Step 3: Enter Date of Death

1. Select the date when the spouse passed away
2. This determines:
   - When Stage 7 activates (year after death)
   - Tax filing status transition
   - Benefit calculations

### Step 4: Review To-Do Checklist

The configuration page displays a comprehensive checklist with 30+ action items organized by timeframe:

**Immediate Actions (First 30 Days):**
- Obtain death certificates
- Contact Social Security Administration
- Notify Medicare
- Contact life insurance companies

**Financial Account Updates (30-90 Days):**
- Update beneficiary designations
- Retitle joint accounts
- Roll over inherited retirement accounts
- Review RMD requirements

**Tax and Legal (Within 1 Year):**
- File final joint tax return
- Update estate planning documents
- Consult with professionals

**Benefits Optimization:**
- Apply for survivor Social Security benefits
- Update Medicare coverage
- Review pension benefits

**Long-Term Planning:**
- Adjust investment strategy
- Review IRMAA thresholds
- Optimize Roth conversions

### Step 5: Configure Conversion Rate (Optional)

1. Navigate to **Configuration → Tax Strategy** tab
2. Scroll to **"Stage-Specific Conversion Rate Limits"**
3. Adjust **"Stage 7: Surviving Spouse (%)"** if desired
   - Default: 15%
   - Range: 0-37%
   - Recommendation: Keep conservative (12-15%)

### Step 6: Save Configuration

Click **"💾 Save All Changes"** at the bottom of the Configuration page.

## How Stage 7 Works

### Stage Priority

Stage 7 is checked **first** in the stage determination process. When active, it takes precedence over all other stages, including:
- Stage 6 (RMD)
- Stage 5 (Social Security)
- Stage 4 (Medicare)

### Calculation Flow

1. **Determine Survivor**: Identifies which person is still alive
2. **Apply Single Status**: Uses Single filer tax brackets
3. **Calculate Survivor Benefits**: Uses higher Social Security benefit
4. **Assess Healthcare**: Single person Medicare costs
5. **Calculate RMD**: Based on survivor's age
6. **Conservative Conversions**: 50% of available room
7. **LTCG Harvesting**: Up to 15% bracket (conservative)
8. **Rebalance Accounts**: Maintain cash buffer targets

### Decision Logging

Stage 7 provides detailed decision logs explaining:
- Why Single filer status is used
- How survivor benefits are calculated
- Why conversions are conservative
- All tax calculations and assumptions

## Financial Impact Examples

### Example 1: Tax Bracket Impact

**Scenario:** Survivor with $100,000 income

**As MFJ (Year of Death):**
- Standard Deduction: $29,200
- Taxable Income: $70,800
- Tax Bracket: 12%
- Federal Tax: ~$8,096

**As Single (Year After):**
- Standard Deduction: $14,600
- Taxable Income: $85,400
- Tax Bracket: 22%
- Federal Tax: ~$14,382

**Impact:** $6,286 more in federal taxes

### Example 2: IRMAA Thresholds

**2024 IRMAA Thresholds:**

| Filing Status | Tier 1 | Tier 2 | Tier 3 |
|---------------|--------|--------|--------|
| MFJ | $206,000 | $258,000 | $322,000 |
| Single | $103,000 | $129,000 | $161,000 |

**Impact:** Single filer hits IRMAA surcharges at half the income level of MFJ.

### Example 3: Roth Conversion Capacity

**Scenario:** Converting to 12% bracket top

**As MFJ:**
- 12% Bracket Top: $89,075
- Current Income: $50,000
- Conversion Room: $39,075

**As Single:**
- 12% Bracket Top: $44,725
- Current Income: $50,000
- Conversion Room: $0 (already in 22% bracket)

**Impact:** Significantly reduced conversion capacity as single filer.

## Best Practices

### 1. Timing Considerations

**Year of Death:**
- File joint return (MFJ status)
- Take advantage of favorable brackets one last time
- Consider larger Roth conversion if appropriate

**Year After Death:**
- Expect higher tax burden
- Adjust withholding and estimated payments
- Review all tax strategies

### 2. Social Security Optimization

**Before Claiming:**
- Understand both spouses' benefit amounts
- Consider longevity and health factors
- Plan for survivor benefit scenario

**After Loss:**
- Apply for survivor benefits promptly
- Understand the 100% survivor benefit rule
- Coordinate with other income sources

### 3. Roth Conversion Strategy

**Conservative Approach:**
- Stage 7 default: 15% max rate
- Uses only 50% of available room
- Prevents over-conversion in higher brackets

**When to Convert More:**
- Low income years (before RMDs start)
- Large traditional IRA balances
- Desire to reduce future RMDs

**When to Convert Less:**
- Already in high tax brackets
- Limited traditional IRA balance
- Other large income sources

### 4. Healthcare Planning

**Medicare Considerations:**
- IRMAA based on single filer thresholds
- Plan income to avoid surcharges
- Consider 2-year lookback period

**Coverage Continuity:**
- Maintain survivor's Medicare enrollment
- Update Part D prescription coverage if needed
- Review Medigap policies

### 5. Estate Planning Updates

**Critical Updates:**
- Revise will and trust documents
- Update beneficiary designations
- Review power of attorney
- Update healthcare directives
- Consider special needs trusts for children

## Common Questions

### Q: Can I switch back to MFJ status?

**A:** No. Once you file as Single (year after death), you cannot return to MFJ status unless you remarry.

### Q: What if I remarry?

**A:** If you remarry, you would:
1. Disable Stage 7 mode
2. Update personal information with new spouse
3. Return to couple planning (Stages 1-6)
4. File as MFJ with new spouse

### Q: How does Stage 7 handle inherited IRAs?

**A:** Stage 7 calculates RMDs based on:
- Survivor's age (if spouse beneficiary)
- Beneficiary RMD rules
- Properly includes in AGI
- Coordinates with other income

### Q: Can I adjust the Stage 7 conversion rate?

**A:** Yes. Navigate to Configuration → Tax Strategy and adjust "Stage 7: Surviving Spouse (%)" to your preferred rate (0-37%). However, we recommend keeping it conservative (12-15%) due to single filer brackets.

### Q: What happens to joint accounts?

**A:** Stage 7 assumes accounts have been retitled to survivor's name. The checklist includes steps for:
- Retitling joint accounts
- Updating beneficiaries
- Consolidating accounts
- Proper documentation

### Q: How does Stage 7 affect Monte Carlo simulations?

**A:** Monte Carlo simulations will:
- Use Stage 7 for years after death
- Apply Single filer tax rates
- Use survivor benefits
- Show more conservative outcomes due to higher taxes

## Technical Details

### Stage Detection Logic

```python
def applies(self, age_primary, age_spouse, year, has_wages, has_ss):
    # Check if surviving spouse mode enabled
    if not surviving_spouse_mode:
        return False
    
    # Check if past year of death
    year_of_death = extract_year(date_of_death)
    return year > year_of_death
```

### Survivor Identification

```python
decedent_person = config.get("decedent_person")
if decedent_person == "person1":
    survivor_age = age_spouse
else:
    survivor_age = age_primary
```

### Conservative Conversion

```python
# Calculate available room to target bracket
conversion_room = target_bracket_max - current_agi

# Use only 50% of room (conservative)
roth_conversion = conversion_room * 0.5
```

## Integration with Other Features

### Portfolio Management
- Works with all account types
- Maintains cost basis tracking
- Supports rebalancing strategies
- Compatible with bucket strategy

### Tax Optimization
- Coordinates with DAF contributions
- Manages LTCG harvesting
- Optimizes standard deduction
- Handles state taxes

### Healthcare Costs
- Calculates single person Medicare
- Manages IRMAA surcharges
- Tracks premium costs
- Includes in expense planning

### Reporting
- Shows Stage 7 in strategy tables
- Displays Single filing status
- Explains survivor benefits
- Documents all decisions

## Support and Resources

### Within the Application
- Configuration checklist (30+ items)
- Decision logs (detailed explanations)
- Strategy tables (year-by-year breakdown)
- Tax calculations (transparent methodology)

### External Resources
- Social Security Administration: www.ssa.gov
- Medicare: www.medicare.gov
- IRS Publication 559: Survivors, Executors, and Administrators
- Estate planning attorney
- Financial advisor
- Tax professional

## Summary

Stage 7 provides comprehensive support for surviving spouse planning by:

✅ Automatically applying Single filer tax status
✅ Optimizing Social Security survivor benefits
✅ Using conservative Roth conversion strategies
✅ Managing single person Medicare costs
✅ Providing detailed transition checklist
✅ Integrating with all existing features
✅ Documenting all decisions clearly

The goal is to help surviving spouses navigate the financial transition with confidence, proper tax treatment, and optimized benefit strategies.

---

**Last Updated:** March 2026
**Version:** 1.0
**Feature:** Stage 7 - Surviving Spouse Planning