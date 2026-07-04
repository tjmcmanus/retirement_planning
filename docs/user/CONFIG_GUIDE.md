# Configuration System Guide

## Overview

The retirement planning application now includes a comprehensive configuration system that allows you to store and manage all your planning constants in one place. This guide explains how to use the configuration features.

## Features

### 1. Configuration Storage (`config.py`)

The configuration system stores all settings in a JSON file (`retirement_config.json`) with the following sections:

- **Personal Information**: Names, birth dates, retirement ages
- **Financial Assumptions**: Expected expenses, inflation rates, investment returns
- **Healthcare**: ACA insurance costs, Medicare start age
- **Social Security**: Benefit start ages and amounts
- **Tax Strategy**: Roth conversion parameters, DAF disbursement rates
- **Portfolio Accounts**: Investment account names and types
- **Portfolio Data**: Detailed holdings stored in `portfolio_data_truth.csv`

### 2. Configuration Page (`pages/configuration.py`)

Access the configuration page through the Streamlit sidebar or by navigating to the "Configuration" page. The page provides:

#### Personal Info Tab
- Enter names and birth dates for both spouses/partners
- Set planned retirement ages
- View current ages automatically calculated

#### Financial Assumptions Tab
- Set expected annual expenses
- Configure expense inflation rate
- Set expected investment return rate
- Define years of expenses to keep in cash (retirement phase)
- **Accumulation Phase: Cash Buffer** — set how many months of wages to keep in cash during working years (3–24 months, default 6)
- **Accumulation Phase: Contribution Rates** — set what percentage of gross wages flows to each account type:
  - **Traditional 401k (%)** — pre-tax contribution; reduces AGI (default 10%)
  - **Roth 401k / IRA (%)** — after-tax Roth contribution (default 5%)
  - **Brokerage (%)** — after-tax taxable brokerage contribution (default 5%)
  - Remaining take-home cash fills the cash buffer first; any surplus above the target also flows to brokerage
- View calculated cash reserve recommendations

#### Healthcare Tab
- Configure ACA insurance monthly premiums
- Set ACA coverage period (start/end ages)
- Set Medicare start age
- View calculated annual and total ACA costs

#### Social Security Tab
- Set benefit start ages for both people
- Enter estimated annual benefit amounts
- View monthly benefits and combined totals

#### Tax Strategy Tab
- Configure Roth conversion amounts and tax rates
- Set Donor Advised Fund disbursement rate
- Set planned distributions for specific years

#### Portfolio Data Tab
- **Account Configuration**: Define your investment accounts with names and types
  - Add accounts (e.g., "Schwab" - "Roth", "Fidelity" - "Traditional")
  - Edit or remove existing accounts
  - Save account configurations to use when entering portfolio holdings
- **Portfolio Holdings**: Enter detailed portfolio data
  - Add holdings with month, year, account, symbol, sector, quantity, and purchase price
  - Edit existing holdings in an interactive data editor
  - Validate data before saving
  - **Important**: Requires at least 2 months of data for the application to work properly
- **Data Management**:
  - Load existing portfolio data from `portfolio_data_truth.csv`
  - Add empty rows for new entries
  - Clear all data to start fresh
  - Save with automatic timestamped backups (e.g., `portfolio_data_truth_20260222_181305.csv`)
- **Validation**: Automatic validation of account types, sectors, and data completeness

#### Advanced Tab
- **Save All Changes**: Persist all configuration changes to file
- **Reset to Defaults**: Restore default configuration values
- **Reload from File**: Reload configuration from disk
- **Export Configuration**: Download configuration as JSON file
- **Import Configuration**: Upload and restore configuration from JSON file
- **View Raw Configuration**: Inspect the complete configuration structure

## Usage

### Initial Setup

1. Navigate to the Configuration page (⚙️ icon in sidebar)
2. Fill in all relevant information in each tab
3. Click "Save All Changes" in the Advanced tab
4. Configuration is now saved to `retirement_config.json`

### Updating Configuration

1. Open the Configuration page
2. Modify any values in the tabs
3. Click "Save All Changes" to persist changes
4. The application will automatically use the new values

### Backup and Restore

#### Export Configuration
1. Go to Advanced tab
2. Click "Export Configuration"
3. Download the JSON file
4. Store it safely for backup

#### Import Configuration
1. Go to Advanced tab
2. Use the file uploader to select your JSON backup
3. Configuration will be imported and saved automatically
4. Refresh the page to see updated values

### Integration with Sidebar

The sidebar now automatically loads values from the configuration file:
- On first run, sidebar inputs are populated from `retirement_config.json`
- Changes in sidebar are stored in session state (temporary)
- To make sidebar changes permanent, update them in the Configuration page

## Configuration File Structure

```json
{
  "personal_info": {
    "person1_name": "Tom",
    "person1_birth_date": "1965-01-01",
    "person1_retirement_age": 62,
    "person1_retirement_year": 2026,
    "person2_name": "Sarah",
    "person2_birth_date": "1967-01-01",
    "person2_retirement_age": 62,
    "person2_retirement_year": 2028,
    "retirement_state": "FL",
    "children": []
  },
  "income": {
    "person1_annual_wages": 120000,
    "person2_annual_wages": 80000,
    "wage_inflation_rate": 3.0,
    "contribution_401k_percent": 10.0,
    "contribution_roth_percent": 5.0,
    "contribution_brokerage_percent": 5.0
  },
  "financial_assumptions": {
    "expected_annual_expenses": 50000,
    "expense_inflation_rate": 3.0,
    "expected_rate_of_return": 6.0,
    "years_of_expenses_in_cash": 4,
    "accumulation_cash_buffer_months": 6
  },
  "healthcare": {
    "aca_insurance_monthly": 0,
    "aca_start_age": 62,
    "aca_end_age": 65,
    "medicare_start_age": 65,
    "aca_marketplace_enrolled": false
  },
  "social_security": {
    "person1_ssi_age": 70,
    "person1_ssi_amount": 0,
    "person2_ssi_age": 70,
    "person2_ssi_amount": 0
  },
  "tax_strategy": {
    "max_roth_conversion_tax_rate": 12
  },
  "charitable_giving": {
    "annual_charitable_giving": 0,
    "charitable_giving_start_age": 65,
    "charitable_giving_end_age": 95,
    "charitable_giving_inflation_rate": 2.0,
    "has_daf": false,
    "daf_provider": "",
    "daf_initial_contribution": 0,
    "daf_annual_contribution": 0,
    "daf_contribution_start_age": 60,
    "daf_contribution_end_age": 75
  },
  "portfolio_accounts": {
    "accounts": [
      {
        "account_name": "Schwab",
        "account_type": "Roth"
      },
      {
        "account_name": "Fidelity",
        "account_type": "Traditional"
      },
      {
        "account_name": "Vanguard",
        "account_type": "Brokerage"
      }
    ]
  },
  "metadata": {
    "last_updated": "2026-02-22T16:30:00",
    "version": "1.0"
  }
}
```

## Configuration Field Reference

### `personal_info` Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `person1_name` | string | `"Tom"` | Display name for person 1 |
| `person1_birth_date` | string | `"1965-01-01"` | Birth date in `YYYY-MM-DD` format |
| `person1_retirement_age` | int | `62` | Planned retirement age for person 1 |
| `person1_retirement_year` | int | current year | Calendar year person 1 retires; wages stop after this year |
| `person2_name` | string | `"Sarah"` | Display name for person 2 |
| `person2_birth_date` | string | `"1967-01-01"` | Birth date in `YYYY-MM-DD` format |
| `person2_retirement_age` | int | `62` | Planned retirement age for person 2 |
| `person2_retirement_year` | int | current year | Calendar year person 2 retires; wages stop after this year |
| `retirement_state` | string | `"FL"` | Two-letter state abbreviation for retirement location (used for future state-tax calculations) |
| `children` | list | `[]` | Optional list of `{"name": str, "birth_date": "YYYY-MM-DD"}` entries |

### `income` Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `person1_annual_wages` | float | `0` | Current annual gross wages/salary for person 1 |
| `person2_annual_wages` | float | `0` | Current annual gross wages/salary for person 2 |
| `wage_inflation_rate` | float | `3.0` | Annual wage growth percentage applied to project future wages |
| `contribution_401k_percent` | float | `10.0` | Percentage of gross wages contributed to a pre-tax Traditional 401k; reduces AGI |
| `contribution_roth_percent` | float | `5.0` | Percentage of gross wages contributed to a Roth 401k or Roth IRA |
| `contribution_brokerage_percent` | float | `5.0` | Percentage of gross wages contributed to an after-tax taxable brokerage account |

**Notes:**
- Wages are projected forward using `wage_inflation_rate` from the current calendar year.
- Wages for each person stop in the year equal to their `person1_retirement_year` / `person2_retirement_year`.
- The three contribution percentages are applied to gross wages. Remaining take-home cash fills the cash buffer first; any surplus above the target also flows to brokerage.
- Use [`ConfigManager.get_annual_wages(year)`](config.py:266) to retrieve inflation-adjusted wages for any future year.
- Use [`ConfigManager.has_wages_in_year(year)`](config.py:302) to check whether either person is still working.

### `financial_assumptions` Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `expected_annual_expenses` | float | `50000` | Annual living expenses in today's dollars |
| `expense_inflation_rate` | float | `3.0` | Annual expense growth percentage |
| `expected_rate_of_return` | float | `6.0` | Expected annual portfolio return percentage |
| `years_of_expenses_in_cash` | int | `4` | Number of years of expenses to hold in cash during retirement |
| `accumulation_cash_buffer_months` | int | `6` | Months of wages to keep in cash during working years (3–24) |

### `healthcare` Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `aca_insurance_monthly` | float | `0` | Monthly ACA marketplace premium (before subsidies) |
| `aca_start_age` | int | `62` | Age at which ACA coverage begins |
| `aca_end_age` | int | `65` | Age at which ACA coverage ends (Medicare begins) |
| `medicare_start_age` | int | `65` | Age at which Medicare coverage begins |
| `aca_marketplace_enrolled` | bool | `false` | Set to `true` when actively enrolled in an ACA marketplace plan; enables ACA subsidy optimization in the withdrawal strategy (Stage 3 keeps MAGI below 400% FPL to maximize premium tax credits) |

### `social_security` Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `person1_ssi_age` | int | `70` | Age at which person 1 claims Social Security (62–70) |
| `person1_ssi_amount` | float | `0` | Person 1's estimated monthly benefit **at age 67** (Full Retirement Age); the SSI calculator adjusts for early/delayed claiming automatically |
| `person2_ssi_age` | int | `70` | Age at which person 2 claims Social Security (62–70) |
| `person2_ssi_amount` | float | `0` | Person 2's estimated monthly benefit at age 67 (FRA) |

### `tax_strategy` Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_roth_conversion_tax_rate` | int | `12` | Maximum marginal tax rate (%) at which Roth conversions are performed; the BETR algorithm uses this as the upper bracket limit |

### `charitable_giving` Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `annual_charitable_giving` | float | `0` | Annual direct charitable giving amount |
| `charitable_giving_start_age` | int | `65` | Age at which charitable giving begins |
| `charitable_giving_end_age` | int | `95` | Age at which charitable giving ends |
| `charitable_giving_inflation_rate` | float | `2.0` | Annual inflation rate applied to charitable giving amounts |
| `has_daf` | bool | `false` | Whether a Donor Advised Fund (DAF) is in use |
| `daf_provider` | string | `""` | Name of the DAF provider (e.g., "Fidelity Charitable") |
| `daf_initial_contribution` | float | `0` | One-time initial contribution to the DAF |
| `daf_annual_contribution` | float | `0` | Annual contribution to the DAF |
| `daf_contribution_start_age` | int | `60` | Age at which annual DAF contributions begin |
| `daf_contribution_end_age` | int | `75` | Age at which annual DAF contributions end |

**Notes:**
- DAF contributions are deductible in the year contributed, providing an immediate tax benefit.
- The `income_expense.py` simulation applies a 25% annual spend-down rate to the DAF balance.
- DAF disbursements reduce taxable income in the year of the contribution (not the disbursement).

### `portfolio_accounts` Section

Defines the investment accounts used when entering portfolio holdings. Each entry in the `accounts` list has:

| Field | Type | Description |
|-------|------|-------------|
| `account_name` | string | Display name (e.g., `"Schwab"`, `"Fidelity"`) |
| `account_type` | string | One of: `"Cash"`, `"Brokerage"`, `"Traditional"`, `"Roth"` |

## API Reference

### ConfigManager Class

```python
from config import get_config_manager

# Get the global configuration manager
config_mgr = get_config_manager()

# Get a value
value = config_mgr.get("section_name", "key_name", default_value)

# Set a value
config_mgr.set("section_name", "key_name", new_value)

# Get entire section
section = config_mgr.get_section("section_name")

# Update section
config_mgr.update_section("section_name", {"key1": value1, "key2": value2})

# Save to file
config_mgr.save_config()

# Calculate age from birth date
age = config_mgr.calculate_age("1965-01-01")

# Get person's current age
age = config_mgr.get_person_age(1)  # Person 1 or 2

# Get inflation-adjusted wages for a future year
wages = config_mgr.get_annual_wages(2028)

# Check whether either person has wages in a given year
working = config_mgr.has_wages_in_year(2028)
```

## Configuration Scenarios

### Scenario 1: Single Person, Already Retired

```json
{
  "personal_info": {
    "person1_name": "Alex",
    "person1_birth_date": "1960-06-15",
    "person1_retirement_age": 65,
    "person1_retirement_year": 2025,
    "person2_name": "",
    "person2_birth_date": "1960-01-01",
    "person2_retirement_year": 2025
  },
  "income": {
    "person1_annual_wages": 0,
    "person2_annual_wages": 0,
    "wage_inflation_rate": 3.0,
    "contribution_401k_percent": 0,
    "contribution_roth_percent": 0,
    "contribution_brokerage_percent": 0
  }
}
```

### Scenario 2: Couple with Different Retirement Ages

```json
{
  "personal_info": {
    "person1_name": "Tom",
    "person1_birth_date": "1965-01-01",
    "person1_retirement_age": 62,
    "person1_retirement_year": 2027,
    "person2_name": "Sarah",
    "person2_birth_date": "1967-06-01",
    "person2_retirement_age": 60,
    "person2_retirement_year": 2027
  },
  "income": {
    "person1_annual_wages": 120000,
    "person2_annual_wages": 80000,
    "wage_inflation_rate": 3.0,
    "contribution_401k_percent": 10.0,
    "contribution_roth_percent": 5.0,
    "contribution_brokerage_percent": 5.0
  }
}
```

### Scenario 3: Early Retirement with ACA Coverage

```json
{
  "personal_info": {
    "person1_retirement_year": 2026
  },
  "income": {
    "person1_annual_wages": 0,
    "person2_annual_wages": 0
  },
  "healthcare": {
    "aca_insurance_monthly": 850,
    "aca_start_age": 60,
    "aca_end_age": 65,
    "medicare_start_age": 65,
    "aca_marketplace_enrolled": true
  }
}
```
> When `aca_marketplace_enrolled` is `true`, the withdrawal strategy (Stage 3) optimizes income to stay below 400% of the Federal Poverty Level to maximize ACA premium tax credits.

### Scenario 4: High-Income with DAF Strategy

```json
{
  "tax_strategy": {
    "max_roth_conversion_tax_rate": 24
  },
  "charitable_giving": {
    "annual_charitable_giving": 20000,
    "charitable_giving_start_age": 60,
    "has_daf": true,
    "daf_provider": "Fidelity Charitable",
    "daf_initial_contribution": 100000,
    "daf_annual_contribution": 25000,
    "daf_contribution_start_age": 58,
    "daf_contribution_end_age": 72
  }
}
```

## Best Practices

1. **Regular Backups**: Export your configuration regularly, especially before making major changes
2. **Version Control**: Keep exported configurations in version control or cloud storage
3. **Validation**: Always review calculated values (like cash reserves) after changing assumptions
4. **Documentation**: Use the notes feature (if added) to document why certain values were chosen
5. **Testing**: After importing a configuration, verify all values are correct before running analyses
6. **Portfolio Data**: Always maintain at least 2 months of portfolio data for proper application functionality
7. **Timestamped Backups**: Portfolio data is automatically backed up with timestamps before each save - review these backups periodically

## Troubleshooting

### Configuration Not Loading
- Check that `retirement_config.json` exists in the application directory
- Try clicking "Reload from File" in the Advanced tab
- If file is corrupted, click "Reset to Defaults" to recreate it

### Changes Not Persisting
- Ensure you click "Save All Changes" after making modifications
- Check file permissions on `retirement_config.json` and `portfolio_data_truth.csv`
- Verify the files are not read-only

### Portfolio Data Issues
- Ensure you have at least 2 months of data entered
- Check that all required fields are filled (month, year, account_name, account_type, symbol, name, sector, qty, purchase_price)
- Verify account types match valid options: Cash, Brokerage, Traditional, Roth
- Check that sectors are valid (use the dropdown in the data editor)
- Review timestamped backup files if data was accidentally overwritten

### Import Fails
- Ensure the JSON file is properly formatted
- Verify the file contains all required sections
- Check that numeric values are not strings (except where appropriate)

## Future Enhancements

Potential future additions to the configuration system:
- Multiple configuration profiles (conservative, moderate, aggressive)
- Scenario comparison tools
- Configuration validation and warnings
- Historical configuration tracking
- Shared configurations across multiple users
- Cloud backup integration

## Support

For issues or questions about the configuration system:
1. Check this guide first
2. Review the raw configuration in the Advanced tab
3. Try resetting to defaults and reconfiguring
4. Export your configuration before troubleshooting