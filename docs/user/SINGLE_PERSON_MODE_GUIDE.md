# Single Person Mode Implementation Guide

## Overview

A new "single person" checkbox has been added to the configuration page that allows users to explicitly indicate they are planning for a single person rather than a couple. This affects multiple aspects of the retirement planning calculations and strategies.

## Configuration Changes

### 1. New Configuration Field

**Location**: `config.py` - `DEFAULT_CONFIG["personal_info"]`

```python
"is_single_person": False  # True if planning for single person, False for couple
```

### 2. UI Changes

**Location**: `pages/2_configuration.py` - Personal Information Tab

- Added checkbox at the top of the Personal Info tab
- When checked:
  - Person 2 (Spouse/Partner) fields are hidden
  - A message indicates "Single Person Mode" is active
  - Person 2 data is set to default values internally

### 3. Filing Status Logic

**Location**: `config.py` - `ConfigManager.get_filing_status()`

The method now checks the `is_single_person` flag first:
- If `is_single_person = True` → Returns `"single"`
- If `is_single_person = False` → Checks if `person2_name` is provided
  - If person2_name exists → Returns `"married_filing_jointly"`
  - If person2_name is empty → Returns `"single"`

## Impact on Strategy Calculations

The filing status affects numerous calculations throughout the application. Here's how single person mode impacts each area:

### 1. Tax Calculations

**Filing Status Impact**: Single vs. Married Filing Jointly

**Affected Areas**:
- **Income Tax Brackets** (`load_data.py::get_income_tax_brackets`)
  - Single filers have different (generally lower) bracket thresholds
  - Example: 2024 12% bracket ends at $47,150 (single) vs $94,300 (MFJ)

- **Capital Gains Brackets** (`load_data.py::get_cap_gains_brackets`)
  - 0% bracket: $47,025 (single) vs $94,050 (MFJ) in 2024
  - 15% bracket: $518,900 (single) vs $583,750 (MFJ) in 2024

- **Standard Deduction** (`load_data.py::get_std_deduction`)
  - 2024: $14,600 (single) vs $29,200 (MFJ)
  - Affects itemization decisions and taxable income calculations

### 2. Social Security Taxation

**Function**: `strategy.py::calculate_ss_taxable_amount`

**Thresholds differ by filing status**:
- **Combined Income Thresholds**:
  - Single: $25,000 (0% taxable) / $34,000 (up to 85% taxable)
  - MFJ: $32,000 (0% taxable) / $44,000 (up to 85% taxable)

- **Maximum 50% Taxable Amount**:
  - Single: $4,500
  - MFJ: $6,000

**Impact**: Single filers reach higher SS taxation levels at lower income thresholds.

### 3. Medicare & IRMAA

**Function**: `strategy.py::calculate_medicare_costs`

**IRMAA Surcharge Thresholds** (2024):
- Single: $103,000 / $129,000 / $161,000 / $193,000 / $500,000+
- MFJ: $206,000 / $258,000 / $322,000 / $386,000 / $750,000+

**Impact**: Single filers hit IRMAA surcharges at roughly half the income of married couples.

### 4. Alternative Minimum Tax (AMT)

**Function**: `strategy.py::calculate_amt`

**AMT Exemption & Phase-out** (2024):
- Single: $85,700 exemption, phases out starting at $609,350
- MFJ: $133,300 exemption, phases out starting at $1,218,700

**Impact**: Single filers have lower AMT protection and hit phase-outs sooner.

### 5. Net Investment Income Tax (NIIT)

**Function**: `strategy.py::calculate_niit`

**3.8% NIIT Threshold**:
- Single: $200,000
- MFJ: $250,000

**Impact**: Single filers pay NIIT on investment income at lower MAGI levels.

### 6. Roth Conversion Strategy

**Multiple Functions**: Throughout `strategy.py` and `advanced_strategies.py`

**Impact**:
- Lower tax brackets mean smaller "tax-efficient" conversion amounts
- IRMAA thresholds are lower, requiring more careful MAGI management
- Standard deduction is half, reducing tax-free conversion space

**Strategy Adjustment**: Single filers should:
- Convert smaller amounts annually to stay in lower brackets
- Be more conservative with MAGI to avoid IRMAA
- Consider longer conversion timelines

### 7. Qualified Business Income (QBI) Deduction

**Function**: `advanced_strategies.py::calculate_qbi_deduction`

**Phase-out Thresholds**:
- Single: $191,950 - $241,950
- MFJ: $383,900 - $483,900

**Impact**: Single filers lose QBI deduction benefits at lower income levels.

### 8. Backdoor Roth Contributions

**Function**: `advanced_strategies.py::calculate_backdoor_roth_strategy`

**Roth IRA Phase-out**:
- Single: $150,000 - $165,000
- MFJ: $236,000 - $246,000

**Impact**: Single filers need backdoor Roth at lower income levels.

### 9. Qualified Charitable Distributions (QCD)

**Function**: `advanced_strategies.py::calculate_qcd_optimization`

**Standard Deduction Comparison**:
- Single: $14,600 (2024)
- MFJ: $29,200 (2024)

**Impact**: Single filers more likely to benefit from QCD since lower standard deduction makes itemizing harder.

### 10. Healthcare Costs (ACA)

**Function**: `strategy.py::calculate_total_healthcare_costs`

**Impact**:
- ACA subsidies based on household size (1 vs 2+)
- Premium costs typically lower for single person
- MAGI thresholds for subsidies differ

### 11. State Taxes

**Function**: `strategy.py::calculate_state_tax`

**Impact**: Most states have different brackets/rates for single vs. MFJ filers.

### 12. Withdrawal Strategy

**Multiple Functions**: Throughout `withdrawal_strategy.py`

**Key Impacts**:
- Lower tax brackets mean more aggressive Roth conversions may not be optimal
- IRMAA management more critical due to lower thresholds
- Social Security claiming strategy simpler (no spousal benefits)
- RMDs affect single person differently (no spousal rollover options)

## User Experience Changes

### Configuration Page

1. **Checkbox Location**: Top of Personal Information tab
2. **Visual Feedback**: 
   - Info message when checked: "Single Person Mode: The application will assume single filing status..."
   - Person 2 section shows: "Single person mode - spouse/partner information hidden"
3. **Data Handling**: Person 2 fields are hidden but default values are still saved to config

### Throughout Application

All pages that use `config_mgr.get_filing_status()` will automatically use the correct filing status:
- Dashboard calculations
- Strategy recommendations
- Monte Carlo simulations
- Advanced strategy tools
- Tax projections

## Testing Recommendations

1. **Toggle Test**: Switch between single and couple mode, verify filing status changes
2. **Tax Calculation Test**: Compare tax calculations for same income in both modes
3. **Strategy Test**: Verify Roth conversion recommendations differ appropriately
4. **IRMAA Test**: Confirm IRMAA thresholds are correctly applied
5. **Social Security Test**: Verify SS taxation uses correct thresholds

## Migration Notes

- Existing configurations will default to `is_single_person = False`
- If `person2_name` is empty, filing status will be "single" regardless of checkbox
- The checkbox provides explicit control and clarity for users

## Future Enhancements

Potential improvements:
1. Add validation to prevent checking "single" when person2_name is filled
2. Add warning when switching modes about data implications
3. Create single-person-specific strategy recommendations
4. Adjust Monte Carlo assumptions for single vs. couple longevity
5. Add single-person estate planning considerations

## Code References

Key files modified:
- `config.py`: Added `is_single_person` field and updated `get_filing_status()`
- `pages/2_configuration.py`: Added checkbox UI and conditional display logic

Key files that use filing status:
- `strategy.py`: All withdrawal and tax calculation functions
- `advanced_strategies.py`: QBI, backdoor Roth, QCD, tax harvesting
- `load_data.py`: Tax bracket and deduction lookups
- `income_expense.py`: Income and expense projections
- `components/shared.py`: Session state management

## Summary

The single person checkbox provides users with explicit control over their planning assumptions and ensures all calculations use the appropriate tax filing status. This affects:

- **Tax brackets and rates** (lower thresholds for single filers)
- **Standard deduction** (roughly half for single filers)
- **IRMAA thresholds** (roughly half for single filers)
- **Social Security taxation** (lower thresholds for single filers)
- **Various phase-outs and limits** (generally lower for single filers)

**Bottom Line**: Single filers generally face higher effective tax rates at lower income levels and need more conservative strategies to avoid IRMAA and other income-based surcharges.