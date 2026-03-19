# Schwab Orders API Solution for Purchase Dates

## Problem Discovery

The Schwab API **does not have a "transactions" endpoint** - it only provides an **"orders" endpoint**. This was discovered by analyzing the [cschwab.py](https://github.com/rcholic/cschwab.py) library, which successfully integrates with Schwab's API.

### Original Issue
- Attempting to call `/trader/v1/accounts/{hash}/transactions` resulted in **400 Bad Request** errors
- The endpoint does not exist in Schwab's API specification
- Purchase dates were not available in the positions/holdings data

## Solution: Using the Orders Endpoint

### API Endpoint
```
GET /trader/v1/accounts/{accountHash}/orders
```

### Parameters
- `fromEnteredTime`: Start datetime in ISO 8601 format (e.g., `2024-01-15T00:00:00.000Z`)
- `toEnteredTime`: End datetime in ISO 8601 format (e.g., `2024-12-31T23:59:59.999Z`)
- `maxResults`: Maximum number of results (default: 1000)
- `status`: Optional filter (e.g., `FILLED` for executed orders only)

### Key Differences from Transactions

| Feature | Orders Endpoint | Transactions Endpoint |
|---------|----------------|----------------------|
| **Availability** | ✅ Available | ❌ Does not exist |
| **Buy/Sell Trades** | ✅ Yes | N/A |
| **Purchase Dates** | ✅ Yes (from execution time) | N/A |
| **Dividends** | ❌ No | N/A |
| **Transfers** | ❌ No | N/A |
| **Interest** | ❌ No | N/A |

## Implementation Changes

### 1. SchwabAPI Class (`components/schwab_connector.py`)

Added new `get_orders()` method:

```python
def get_orders(
    self,
    account_hash: str,
    from_entered_time: str,
    to_entered_time: str,
    max_results: int = 1000,
    status: Optional[str] = None
) -> List[Dict]:
    """
    Get order history for an account
    
    Returns filled orders with execution details including:
    - Order ID and status
    - Execution time (used as purchase date)
    - Symbol and quantity
    - Execution price
    - Buy/Sell instruction
    """
```

Modified `get_transactions()` to be a wrapper that calls `get_orders()` internally for backward compatibility.

### 2. TransactionImporter Class (`components/transaction_importer.py`)

Updated `get_schwab_transactions()` to:
- Call `get_orders()` instead of `get_transactions()`
- Filter for `FILLED` orders only
- Convert dates to ISO 8601 format

Added new `_transform_schwab_orders()` method to:
- Extract execution time as purchase date
- Parse order legs for symbol, quantity, and price
- Map BUY/SELL instructions to transaction types
- Handle execution details from `orderActivityCollection`

### 3. Order Data Structure

Example order response:
```json
{
  "orderId": 123456789,
  "status": "FILLED",
  "enteredTime": "2024-01-15T10:30:00+0000",
  "closeTime": "2024-01-15T10:30:15+0000",
  "orderLegCollection": [
    {
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
      "activityType": "EXECUTION",
      "executionLegs": [
        {
          "price": 150.00,
          "quantity": 100.0,
          "time": "2024-01-15T10:30:15+0000"
        }
      ]
    }
  ]
}
```

### 4. Purchase Date Extraction

Purchase dates are derived from:
1. **Primary**: `closeTime` - when the order was executed
2. **Fallback**: `enteredTime` - when the order was placed
3. **Format**: ISO 8601 timestamp converted to `YYYY-MM-DD`

## Usage

### Automatic Import (Default)
When fetching positions, orders are automatically imported:

```python
connector = SchwabConnector(app_key, app_secret, callback_url)
positions = connector.get_positions(
    import_transactions=True,  # Default
    transaction_days_back=365   # Default
)
```

### Manual Import
```python
from components.transaction_importer import TransactionImporter

importer = TransactionImporter(schwab_connector=connector)
orders_df = importer.get_schwab_transactions(
    account_hash=None,  # All accounts
    days_back=365
)
```

### Purchase Date Enrichment
```python
from components.schwab_data_transformer import SchwabDataTransformer

transformer = SchwabDataTransformer()
portfolio_df = transformer.transform_positions_to_portfolio(
    positions,
    enrich_with_transactions=True  # Adds purchase dates from orders
)
```

## Limitations

### What Orders Provide
✅ Buy and sell trades with execution dates  
✅ Purchase dates for cost basis tracking  
✅ Trade prices and quantities  
✅ Order status and execution details  

### What Orders Don't Provide
❌ Dividend payments  
❌ Interest income  
❌ Account transfers  
❌ Corporate actions (mergers, spinoffs)  
❌ Fee transactions  

### Workarounds for Missing Data

1. **Dividends & Interest**: Must be tracked separately or imported via CSV
2. **Transfers**: Manual entry required
3. **Corporate Actions**: May need to be entered manually with effective dates

## Testing

To test the orders endpoint integration:

```python
# Run the live test
python test_transaction_import_live.py
```

This will:
1. Connect to Schwab API
2. Fetch filled orders for the past year
3. Transform to transaction format
4. Store in database
5. Verify purchase dates appear in holdings

## API Reference

### Schwab Orders Endpoint Documentation
- **Base URL**: `https://api.schwabapi.com`
- **Endpoint**: `/trader/v1/accounts/{accountHash}/orders`
- **Method**: GET
- **Authentication**: OAuth 2.0 Bearer token
- **Rate Limits**: Subject to Schwab API rate limits

### Order Status Values
- `FILLED` - Order executed (use this for transactions)
- `CANCELED` - Order canceled
- `REJECTED` - Order rejected
- `WORKING` - Order pending
- `PENDING_ACTIVATION` - Order scheduled
- `EXPIRED` - Order expired

## Migration Notes

### From Previous Implementation
The previous implementation attempted to use a non-existent `/transactions` endpoint. All code has been updated to use `/orders` instead.

### Backward Compatibility
- `get_transactions()` method still exists but calls `get_orders()` internally
- `_transform_schwab_transactions()` method deprecated but calls `_transform_schwab_orders()`
- Existing code continues to work without changes

## Conclusion

**Answer to Original Question**: 
> "Looking at the Schwab holdings, I am not seeing 'purchase date' in the dataframe. Is this something we can get from the API?"

**Yes**, purchase dates can be obtained from the Schwab API using the **orders endpoint**. The implementation:
1. Fetches filled orders from the past year (configurable)
2. Extracts execution dates as purchase dates
3. Stores orders in the transaction database
4. Enriches position data with purchase dates from the database

The solution is now implemented and ready for testing with a live Schwab account.