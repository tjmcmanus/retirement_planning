# Options Trading Support

## Overview
The retirement planning application now supports options trading with proper cost basis calculation and capital gains tracking. Options are automatically detected and handled with the correct multiplier (100 shares per contract).

## Options Symbol Format

### Standard Format
Options symbols follow the OCC (Options Clearing Corporation) format:
```
TICKER  YYMMDDCPSTRIKE
```

**Example**: `SOFI  260123P00027000`
- **SOFI** = Underlying ticker
- **260123** = Expiration date (January 23, 2026)
- **P** = Put option (C = Call)
- **00027000** = Strike price ($27.00)

### Detection Logic
The system automatically detects options by:
1. Presence of double spaces (`  `) in the symbol
2. Symbol length > 15 characters
3. Valid date and strike price format

## Options Multiplier

### Standard Multiplier
- **1 option contract = 100 shares**
- All proceeds and cost basis calculations are multiplied by 100
- This applies to both calls and puts

### Example Calculation
```python
# Option transaction
Symbol: "SOFI  260123P00027000"
Quantity: 1 contract
Price per contract: $2.50

# Actual proceeds/cost
Actual amount = 1 × $2.50 × 100 = $250.00
```

## Transaction Types for Options

### Opening Positions
- **Sell to Open** (SELL): Selling options to open a position (credit received)
  - Creates a short position
  - Receives premium
  - Example: Selling a covered call

- **Buy to Open** (BUY): Buying options to open a position (debit paid)
  - Creates a long position
  - Pays premium
  - Example: Buying a protective put

### Closing Positions
- **Buy to Close** (BUY): Buying options to close a short position (debit paid)
  - Closes a short position
  - Pays to close
  - Matched with "Sell to Open" for gain/loss calculation

- **Sell to Close** (SELL): Selling options to close a long position (credit received)
  - Closes a long position
  - Receives proceeds
  - Matched with "Buy to Open" for gain/loss calculation

## Cost Basis Calculation

### FIFO Matching
The system uses First In, First Out (FIFO) to match opening and closing transactions:

1. **Opening Transaction** (Sell to Open or Buy to Open)
   - Added to lot queue
   - Cost basis = quantity × price × 100

2. **Closing Transaction** (Buy to Close or Sell to Close)
   - Matched with oldest opening transaction
   - Gain/Loss = (closing proceeds - opening cost) × 100

### Example: Covered Call
```
1. Sell to Open: SOFI 260123C00030000
   - Date: 2025-11-15
   - Quantity: 1 contract
   - Price: $3.50
   - Premium received: $350.00

2. Buy to Close: SOFI 260123C00030000
   - Date: 2026-01-20
   - Quantity: 1 contract
   - Price: $0.50
   - Cost to close: $50.00

Gain/Loss Calculation:
- Opening credit: $350.00
- Closing debit: $50.00
- Net gain: $300.00
- Holding period: 66 days (SHORT-term)
```

### Example: Protective Put
```
1. Buy to Open: SOFI 260123P00027000
   - Date: 2025-12-01
   - Quantity: 1 contract
   - Price: $2.50
   - Premium paid: $250.00

2. Sell to Close: SOFI 260123P00027000
   - Date: 2026-01-15
   - Quantity: 1 contract
   - Price: $4.00
   - Proceeds: $400.00

Gain/Loss Calculation:
- Opening debit: $250.00
- Closing credit: $400.00
- Net gain: $150.00
- Holding period: 45 days (SHORT-term)
```

## Tax Treatment

### Holding Period
- **SHORT-term**: ≤ 365 days (taxed as ordinary income)
- **LONG-term**: > 365 days (preferential capital gains rates)

### Account Type Considerations

#### Brokerage (Taxable) Accounts
- All options gains/losses are taxable
- Reported on Form 1099-B
- Must be reported on Schedule D

#### IRA Accounts (Roth and Traditional)
- Options trading allowed (if approved by broker)
- Gains/losses not taxable within the account
- Roth: Tax-free on qualified withdrawals
- Traditional: Taxed as ordinary income on withdrawal

### Special Tax Rules

#### Wash Sale Rule
- Applies to options on the same underlying security
- 30-day window before and after the sale
- Loss disallowed if substantially identical option purchased

#### Straddles
- Special rules for offsetting positions
- May require mark-to-market accounting
- Consult tax professional for complex strategies

## Capital Gains Display

### Options in UI
Options are displayed with their full symbol in all tabs:

**Transaction History Tab**:
```
Symbol: SOFI  260123P00027000
Type: SELL TO OPEN
Quantity: 1
Price: $2.50
Amount: $250.00
```

**Capital Gains Tab**:
```
Symbol: SOFI  260123P00027000
Gain/Loss: $150.00
Term: SHORT
Holding Period: 45 days
```

### Grouping
- Options are grouped separately from underlying stock
- Each unique option (strike + expiration) tracked independently
- Account-specific tracking maintained

## Implementation Details

### Code Location
[`components/transaction_history_ui.py`](components/transaction_history_ui.py:16-90)

### Key Functions

#### `is_option(symbol)`
Detects if a symbol represents an option contract.

```python
def is_option(symbol):
    """
    Detect if a symbol is an option.
    Options format: "TICKER  YYMMDDCPSTRIKE"
    """
    if not symbol or not isinstance(symbol, str):
        return False
    return '  ' in symbol and len(symbol) > 15
```

#### `get_option_multiplier(symbol)`
Returns the multiplier for options (100) or stocks (1).

```python
def get_option_multiplier(symbol):
    """
    Get the multiplier for options (typically 100 shares per contract).
    """
    return 100 if is_option(symbol) else 1
```

#### `parse_option_symbol(symbol)`
Parses option symbol to extract components.

```python
def parse_option_symbol(symbol):
    """
    Parse option symbol to extract underlying, expiration, type, and strike.
    Returns: {
        'underlying': 'SOFI',
        'expiration': '260123',
        'type': 'PUT',
        'strike': 27.0,
        'full_symbol': 'SOFI  260123P00027000'
    }
    """
```

### FIFO Calculation Enhancement
The FIFO calculation automatically applies the multiplier:

```python
# Opening position
lot = {
    'date': row['date'],
    'quantity': abs(row['quantity']),
    'price': abs(row['price']) * multiplier,  # 100x for options
    'remaining': abs(row['quantity'])
}

# Closing position
sell_price = abs(row['price']) * multiplier  # 100x for options
proceeds = sell_quantity * sell_price
```

## Supported Strategies

### Covered Calls
✅ Fully supported
- Sell to Open → Buy to Close
- Premium received tracked correctly
- Gain/loss calculated with 100x multiplier

### Protective Puts
✅ Fully supported
- Buy to Open → Sell to Close
- Premium paid tracked correctly
- Gain/loss calculated with 100x multiplier

### Cash-Secured Puts
✅ Fully supported
- Sell to Open → Buy to Close or Assignment
- Premium received tracked correctly

### Long Calls/Puts
✅ Fully supported
- Buy to Open → Sell to Close or Expiration
- Premium paid tracked correctly

### Spreads (Bull, Bear, Calendar)
⚠️ Partially supported
- Each leg tracked independently
- Manual reconciliation may be needed for complex strategies

### Iron Condors / Butterflies
⚠️ Partially supported
- Each leg tracked independently
- Consider using trade notes for strategy tracking

## Limitations

### Current Limitations
1. **Assignment/Exercise**: Not automatically detected
   - Manual entry required for assigned options
   - Stock acquisition cost should include option premium

2. **Expiration**: Expired options show as open positions
   - Manual marking as expired needed
   - Future enhancement planned

3. **Complex Spreads**: Each leg tracked separately
   - No automatic spread recognition
   - P&L calculated per leg, not per strategy

4. **Adjustments**: Rolling positions requires manual tracking
   - Close old position, open new position
   - No automatic roll detection

### Workarounds

#### For Assignments
1. Manually enter stock transaction at strike price
2. Adjust cost basis to include option premium
3. Mark option as closed

#### For Expirations
1. Filter out expired options from active positions
2. Mark as "EXPIRED" in notes
3. Zero gain/loss if expired worthless

#### For Rolls
1. Enter as two separate transactions:
   - Close original position
   - Open new position
2. Track relationship in notes field

## Testing

### Test Cases

#### Test 1: Simple Covered Call
```python
# Sell to Open
Symbol: "AAPL  260115C00150000"
Quantity: 1
Price: $5.00
Expected: $500.00 credit

# Buy to Close
Symbol: "AAPL  260115C00150000"
Quantity: 1
Price: $2.00
Expected: $200.00 debit

# Result
Gain: $300.00 (SHORT-term)
```

#### Test 2: Protective Put
```python
# Buy to Open
Symbol: "TSLA  260220P00200000"
Quantity: 2
Price: $8.50
Expected: $1,700.00 debit

# Sell to Close
Symbol: "TSLA  260220P00200000"
Quantity: 2
Price: $12.00
Expected: $2,400.00 credit

# Result
Gain: $700.00 (SHORT-term)
```

### Validation
Run the Capital Gains Analysis tab to verify:
- ✅ Options show correct proceeds (price × 100)
- ✅ Cost basis calculated correctly (price × 100)
- ✅ Gain/loss matches expected (proceeds - cost)
- ✅ Holding period calculated from open to close
- ✅ Term classification (SHORT/LONG) correct

## Future Enhancements

### Planned Features
1. **Assignment Detection**: Automatic detection of option assignments
2. **Expiration Handling**: Auto-mark expired options
3. **Spread Recognition**: Identify and group spread strategies
4. **Roll Detection**: Automatic detection of rolled positions
5. **Greeks Tracking**: Delta, gamma, theta, vega for open positions
6. **Strategy P&L**: Combined P&L for multi-leg strategies

### Timeline
- Phase 1 (Current): Basic options support ✅
- Phase 2 (Q2 2026): Assignment and expiration handling
- Phase 3 (Q3 2026): Spread recognition and strategy P&L
- Phase 4 (Q4 2026): Greeks and advanced analytics

## Support

### Getting Help
- Review transaction history for correct multiplier application
- Check Capital Gains tab for accurate gain/loss calculations
- Verify holding periods match your records
- Contact support for complex strategy questions

### Reporting Issues
If you notice incorrect calculations:
1. Note the option symbol
2. Record opening and closing transactions
3. Compare expected vs actual gain/loss
4. Submit issue with transaction details

---

*Last Updated: 2026-03-23*
*Version: 1.0*
*Status: Production*