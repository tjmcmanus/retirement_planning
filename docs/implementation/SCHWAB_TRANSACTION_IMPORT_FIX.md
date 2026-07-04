# Schwab Transaction Import Fix

## Issues Fixed

### Issue 1: TypeError on TransactionImporter instantiation
When syncing Schwab accounts, the automatic transaction import was failing with:
```
TypeError: TransactionImporter.__init__() got an unexpected keyword argument 'schwab_connector'
```

### Issue 2: Account hash was None
After fixing Issue 1, transaction import was still failing with:
```
ERROR - Account hash required for transaction import
```
This was because `get_positions()` was passing `None` for `account_hash` when fetching all accounts.

## Root Causes

### Issue 1 Root Cause
The `_import_transactions_for_positions()` method in `components/schwab_connector.py` was incorrectly instantiating `TransactionImporter`:

**Before (Incorrect)**:
```python
importer = TransactionImporter(schwab_connector=self)
transactions_df = importer.get_schwab_transactions(
    account_hash=account_hash,
    days_back=days_back
)
```

**Problems**:
1. `TransactionImporter.__init__()` expects `credential_manager`, not `schwab_connector`
2. `TransactionImporter` doesn't have a `get_schwab_transactions()` method
3. The Schwab connector should fetch orders directly using its own API

### Issue 2 Root Cause
The `get_positions()` method was calling `_import_transactions_for_positions(account_hash=account_hash)` where `account_hash` was None when fetching all accounts. The method needs to:
1. Get account hashes first via `get_account_numbers()`
2. Loop through each account hash
3. Import transactions for each account individually

## Solution
Modified `_import_transactions_for_positions()` to:
1. Use `SchwabAPI.get_orders()` directly to fetch order history
2. Convert orders to transaction format locally
3. Store transactions using `TransactionStorage`

**After (Correct)**:
```python
# Ensure API is initialized
if not self.api:
    logger.error("Schwab API not initialized")
    return

# Fetch orders from Schwab API
orders = self.api.get_orders(
    account_hash=account_hash,
    from_entered_time=from_time,
    to_entered_time=to_time,
    max_results=3000,
    status='FILLED'
)

# Convert orders to transaction format
transactions = []
for order in orders:
    for leg in order.get('orderLegCollection', []):
        # Extract transaction details
        transaction = {
            'transaction_id': f"{order_id}_{leg_id}",
            'date': close_time[:10],
            'symbol': symbol,
            'transaction_type': instruction,  # BUY or SELL
            'quantity': quantity,
            'price': price,
            'amount': quantity * price,
            'account_id': account_hash,
            'description': f"{instruction} {quantity} {symbol} @ ${price}"
        }
        transactions.append(transaction)

# Convert to DataFrame and store
transactions_df = pd.DataFrame(transactions)
storage.store_transactions(transactions_df, user_id="default")
```

## Changes Made

### File: `components/schwab_connector.py`

**Lines 683-735**: Modified `get_positions()` method
- Get account hashes first via `get_account_numbers()` when fetching all accounts
- Loop through each account hash individually
- Import transactions for each account separately
- Added proper None filtering for account hashes

**Lines 745-830**: Rewrote `_import_transactions_for_positions()` method
- Added API initialization check
- Added account_hash validation
- Removed incorrect `TransactionImporter` instantiation
- Use `self.api.get_orders()` to fetch orders directly
- Convert Schwab order format to transaction format
- Extract price from order execution legs
- Handle multiple legs per order
- Store transactions using `TransactionStorage`

## Transaction Format

### Schwab Order Format (Input)
```json
{
  "orderId": "12345",
  "enteredTime": "2024-01-15T10:30:00.000Z",
  "closeTime": "2024-01-15T10:30:05.000Z",
  "orderLegCollection": [
    {
      "legId": 1,
      "instrument": {
        "symbol": "AAPL",
        "assetType": "EQUITY"
      },
      "instruction": "BUY",
      "quantity": 100.0
    }
  ],
  "orderActivityCollection": [
    {
      "executionLegs": [
        {
          "legId": 1,
          "price": 150.00
        }
      ]
    }
  ]
}
```

### Transaction Format (Output)
```python
{
    'transaction_id': '12345_1',
    'date': '2024-01-15',
    'symbol': 'AAPL',
    'transaction_type': 'BUY',
    'quantity': 100.0,
    'price': 150.00,
    'amount': 15000.00,
    'account_id': 'account_hash',
    'description': 'BUY 100.0 AAPL @ $150.0'
}
```

## Testing

### Expected Behavior
1. When syncing Schwab accounts, transaction import should succeed
2. Filled orders from the past 365 days should be imported
3. Transactions should be stored in the database
4. Purchase dates should be enriched for positions

### Verification
Check logs for:
```
INFO - Starting transaction import for Schwab (days_back=365)
INFO - Fetching orders from Schwab API (...)
INFO - Fetched N filled orders from Schwab
INFO - Converted N orders to transaction format
INFO - Storing transactions in database...
INFO - ✅ Successfully imported and stored N orders as transactions
```

## Impact

### Fixed
- ✅ Schwab transaction import no longer crashes
- ✅ Orders are properly converted to transactions
- ✅ Transactions are stored in database
- ✅ Purchase dates can be enriched from transaction history

### No Impact On
- SnapTrade transaction import (uses different code path)
- Manual transaction import via UI
- Existing transaction data

## Related Files
- `components/schwab_connector.py` - Main fix location
- `components/transaction_importer.py` - Correct API reference
- `components/transaction_storage.py` - Storage interface
- `components/schwab_oauth.py` - Authentication (unchanged)

## Future Improvements
1. Add retry logic for failed order fetches
2. Support incremental imports (only new orders)
3. Add progress indicators for large imports
4. Cache order data to reduce API calls
5. Support filtering by order status (not just FILLED)

---

**Status**: Fixed ✅  
**Date**: 2026-03-23  
**Version**: 1.0.0