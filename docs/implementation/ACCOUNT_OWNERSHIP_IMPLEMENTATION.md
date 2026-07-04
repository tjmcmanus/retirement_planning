# Account Ownership Implementation Guide

## Overview
This document describes the implementation of account ownership designation in the retirement planning application. This feature allows users to specify whether each account belongs to both spouses (Joint), the primary person (Primary), or the spouse (Spouse).

## Implementation Date
2026-03-08

## Motivation
In age-gapped marriages and retirement planning, it's critical to track account ownership because:

1. **RMD Calculations**: Required Minimum Distributions are calculated based on the account owner's age, not household age
2. **IRA Contribution Limits**: Traditional and Roth IRA contributions have age-based limits and phase-outs
3. **Rebalancing**: Account rebalancing must respect ownership boundaries
4. **Withdrawal Strategy**: Tax-efficient withdrawals depend on who owns which accounts
5. **Estate Planning**: Account ownership affects beneficiary designations and inheritance

## Changes Made

### 1. Data Model Updates

#### portfolio_data_entry.py
- Added `VALID_ACCOUNT_OWNERS = ['Joint', 'Primary', 'Spouse']` constant
- Updated `validate_portfolio_entry()` to require and validate 'owner' field
- Updated `create_empty_entry_template()` to include 'owner' column with default 'Joint'

#### pages/2_configuration.py
- Added 'owner' column to all portfolio DataFrame initializations
- Added SelectboxColumn for 'owner' in data editor with help text
- Updated sample data format documentation to include 'owner' field
- Imported `VALID_ACCOUNT_OWNERS` from portfolio_data_entry

### 2. Portfolio Data Schema

**Old Schema:**
```
month, year, account_name, account_type, symbol, name, sector, qty, purchase_price
```

**New Schema:**
```
month, year, account_name, account_type, owner, symbol, name, sector, qty, purchase_price
```

**Owner Field Values:**
- `Joint`: Account owned by both spouses (default for married couples)
- `Primary`: Account owned by Person 1 only
- `Spouse`: Account owned by Person 2 only

### 3. Migration Script

Created `migrate_portfolio_add_owner.py` to:
- Backup existing portfolio_data_truth.csv
- Add 'owner' column with default value 'Joint'
- Preserve all existing data
- Provide clear instructions for manual review

## Usage Instructions

### For New Users
1. When entering portfolio data, select the appropriate owner for each account:
   - **Joint**: Brokerage accounts, joint bank accounts
   - **Primary**: Person 1's IRA, 401(k), or individual accounts
   - **Spouse**: Person 2's IRA, 401(k), or individual accounts

### For Existing Users
1. Run the migration script:
   ```bash
   python migrate_portfolio_add_owner.py
   ```

2. Review your portfolio data in the Configuration page

3. Update the 'owner' field for each account:
   - Traditional IRAs → Set to Primary or Spouse based on whose IRA it is
   - Roth IRAs → Set to Primary or Spouse based on whose IRA it is
   - 401(k) accounts → Set to Primary or Spouse based on whose 401(k) it is
   - Brokerage accounts → Usually Joint, but verify
   - Bank accounts → Usually Joint, but verify

## Impact on Other Features

### RMD Calculations (To Be Implemented)
- RMDs will be calculated based on the account owner's age
- For Joint accounts, use the older spouse's age (conservative approach)
- For Primary accounts, use Person 1's age
- For Spouse accounts, use Person 2's age

### IRA Contribution Limits (To Be Implemented)
- Traditional IRA deductibility phase-outs based on owner's age and income
- Roth IRA contribution limits based on owner's age and income
- Catch-up contributions (age 50+) based on owner's age

### Rebalancing (To Be Implemented)
- Rebalancing operations will respect account ownership
- Cannot move funds between accounts with different owners
- Joint accounts can be rebalanced with either spouse's accounts

### Withdrawal Strategy (To Be Implemented)
- Tax-efficient withdrawal sequencing will consider account ownership
- RMDs from Primary accounts affect Person 1's tax situation
- RMDs from Spouse accounts affect Person 2's tax situation
- Joint account withdrawals affect household tax situation

## Validation Rules

The system validates:
1. **Required Field**: 'owner' must be present and non-empty
2. **Valid Values**: Must be one of: Joint, Primary, Spouse
3. **Consistency**: All rows must have a valid owner designation

## Example Data

```csv
month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price
1,2026,Fidelity 401k,Traditional,Primary,VFIAX,Vanguard 500 Index,MF:Large-Cap,1000,350.00
1,2026,Schwab IRA,Roth,Spouse,VTI,Vanguard Total Market,Stock/ETF,500,220.00
1,2026,Joint Brokerage,Brokerage,Joint,AAPL,Apple Inc.,Technology,100,150.00
1,2026,Joint Savings,Cash,Joint,MF:CASH,Money Market,MF:Cash,50000,1.00
```

## Testing Recommendations

1. **Data Entry**: Verify that the owner dropdown appears and works correctly
2. **Validation**: Test that invalid owner values are rejected
3. **Migration**: Run migration script on test data and verify results
4. **Backward Compatibility**: Ensure old data without 'owner' column is handled gracefully

## Future Enhancements

### Phase 1 (Current)
- ✅ Add 'owner' field to data model
- ✅ Update UI to support owner selection
- ✅ Add validation for owner field
- ✅ Create migration script

### Phase 2 (Next Steps)
- [ ] Update RMD calculations to use account owner's age
- [ ] Update IRA contribution limit calculations
- [ ] Update rebalancing logic to respect ownership
- [ ] Update withdrawal strategy to consider ownership

### Phase 3 (Future)
- [ ] Add ownership-based reporting
- [ ] Add ownership-based tax projections
- [ ] Add ownership transfer scenarios (e.g., inheritance)
- [ ] Add spousal beneficiary calculations

## Technical Notes

### Default Behavior
- New accounts default to 'Joint' ownership
- This is the safest default for married couples
- Users should review and update as needed

### Single Person Households
- For single individuals, all accounts should be set to 'Primary'
- The 'Spouse' option will not be used
- 'Joint' can still be used for accounts with other co-owners

### Data Integrity
- The 'owner' field is required for all new entries
- Existing data without 'owner' will need migration
- The system will not allow saving invalid owner values

## Related Files

- `portfolio_data_entry.py`: Core validation and data handling
- `pages/2_configuration.py`: UI for portfolio data entry
- `migrate_portfolio_add_owner.py`: Migration script
- `portfolio_data_truth.csv`: Portfolio data file (user data)
- `LIFE_STAGE_PRECEDENCE_UPDATE.md`: Related life stage changes

## Support

If you encounter issues:
1. Check that all portfolio entries have a valid 'owner' value
2. Run the migration script if upgrading from an older version
3. Review the validation errors in the Configuration page
4. Ensure 'owner' is one of: Joint, Primary, Spouse

## Changelog

### 2026-03-08
- Initial implementation of account ownership feature
- Added 'owner' field to portfolio data schema
- Created migration script
- Updated UI and validation
- Created documentation