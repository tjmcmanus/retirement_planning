# IRA and 401(k) Contribution Limits - Administrative Guide

## Overview

The Backdoor Roth IRA and Mega Backdoor Roth calculators now use a dynamic lookup table (`ira_limits.csv`) for contribution limits and phase-out thresholds. This allows administrators to easily update values annually without modifying code.

## File Location

**`ira_limits.csv`** - Located in the project root directory

## File Structure

The CSV file contains the following columns:

| Column | Description |
|--------|-------------|
| `year` | Tax year (e.g., 2023, 2024, 2025) |
| `ira_contribution_base` | Base IRA contribution limit |
| `ira_catchup_50plus` | IRA catch-up contribution for age 50+ |
| `roth_phaseout_start_mfj` | Roth IRA phase-out start threshold (Married Filing Jointly) |
| `roth_phaseout_end_mfj` | Roth IRA phase-out end threshold (Married Filing Jointly) |
| `roth_phaseout_start_single` | Roth IRA phase-out start threshold (Single) |
| `roth_phaseout_end_single` | Roth IRA phase-out end threshold (Single) |
| `k401_employee_limit` | 401(k) employee elective deferral limit |
| `k401_total_limit` | 401(k) total contribution limit (IRC §415(c)) |
| `k401_catchup_50` | 401(k) catch-up contribution for age 50-59 |
| `k401_catchup_60_63` | 401(k) catch-up contribution for age 60-63 (SECURE 2.0) |

## Annual Update Process

### Step 1: Obtain Current IRS Limits

Each year (typically announced in October/November), obtain the updated limits from:
- IRS Notice of Cost-of-Living Adjustments
- IRS Publication 590-A (IRA contributions)
- IRS Publication 560 (401(k) limits)

### Step 2: Update the CSV File

1. Open `ira_limits.csv` in a text editor or spreadsheet application
2. Add a new row for the upcoming tax year
3. Fill in all column values with the IRS-published limits
4. Save the file

**Example:**
```csv
year,ira_contribution_base,ira_catchup_50plus,roth_phaseout_start_mfj,roth_phaseout_end_mfj,roth_phaseout_start_single,roth_phaseout_end_single,k401_employee_limit,k401_total_limit,k401_catchup_50,k401_catchup_60_63
2028,7500,1000,245000,255000,155000,170000,24000,72000,7500,11250
```

### Step 3: Verify the Update

1. Restart the Streamlit application
2. Navigate to **Advanced Strategy Tools** → **Backdoor & Mega Backdoor Roth** tab
3. Select the new tax year from the dropdown
4. Verify that the contribution amounts and phase-out thresholds are correct

## Fallback Behavior

If a year is not found in the lookup table, the system will:
1. Log a warning message
2. Fall back to hardcoded constants in `advanced_strategies.py`
3. Continue functioning with default values

This ensures the application remains operational even if the CSV is missing or incomplete.

## Technical Details

### Code Integration

The lookup table is loaded via the `get_ira_limits(year)` function in `load_data.py`:

```python
@st.cache_data()
def get_ira_limits(year):
    ira_limits_year = pd.read_csv('ira_limits.csv')
    ira_limits_df = ira_limits_year[ira_limits_year['year'] == year]
    return ira_limits_df
```

### Functions Using the Lookup Table

1. **`calculate_backdoor_roth()`** - Uses IRA contribution limits and Roth phase-out thresholds
2. **`calculate_mega_backdoor_roth()`** - Uses 401(k) contribution limits and catch-up amounts

### Caching

The lookup table is cached by Streamlit (`@st.cache_data()`), so updates require:
- Restarting the application, OR
- Clearing the Streamlit cache via the UI (☰ → Clear cache)

## Historical Reference

### 2023-2027 Limits (Current in File)

| Year | IRA Base | IRA Catch-up | Roth Phase-out (MFJ) | 401(k) Employee | 401(k) Total |
|------|----------|--------------|---------------------|-----------------|--------------|
| 2023 | $6,500 | $1,000 | $218,000-$228,000 | $22,500 | $66,000 |
| 2024 | $7,000 | $1,000 | $230,000-$240,000 | $23,000 | $69,000 |
| 2025 | $7,000 | $1,000 | $236,000-$246,000 | $23,500 | $70,000 |
| 2026 | $7,000 | $1,000 | $236,000-$246,000 | $23,500 | $70,000 |
| 2027 | $7,000 | $1,000 | $236,000-$246,000 | $23,500 | $70,000 |

## Troubleshooting

### Issue: Calculator shows incorrect limits

**Solution:**
1. Verify the CSV file contains the correct year
2. Check that all columns are properly formatted (no extra spaces, correct data types)
3. Clear Streamlit cache and restart

### Issue: Year not found error

**Solution:**
1. Add the missing year to `ira_limits.csv`
2. Ensure the year column matches exactly (no extra characters)
3. Restart the application

### Issue: Changes not reflected in UI

**Solution:**
1. Clear Streamlit cache: ☰ → Clear cache
2. Restart the Streamlit application
3. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)

## Maintenance Schedule

**Recommended:** Update the CSV file annually in November/December when IRS announces cost-of-living adjustments for the following tax year.

## Contact

For questions about updating the limits or technical issues, contact the system administrator.