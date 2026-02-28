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
    "person2_name": "Sarah",
    "person2_birth_date": "1967-01-01",
    "person2_retirement_age": 62
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
    "medicare_start_age": 65
  },
  "social_security": {
    "person1_ssi_age": 70,
    "person1_ssi_amount": 0,
    "person2_ssi_age": 70,
    "person2_ssi_amount": 0
  },
  "tax_strategy": {
    "roth_conversion_at_ssi_age": 5000,
    "max_roth_conversion_tax_rate": 12,
    "daf_disbursement_rate": 25,
    "planned_distribution_2027": 75000
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