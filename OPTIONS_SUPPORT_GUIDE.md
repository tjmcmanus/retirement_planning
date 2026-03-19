# Stock Options Support Guide

## Overview

The retirement planning system now supports stock options contracts, including the ability to track short positions (covered calls and cash-secured puts) using negative quantities.

## Features

### 1. Options Symbol Detection

The system automatically detects options contracts in OCC (Options Clearing Corporation) format:

**Format:** `TICKER[spaces]YYMMDDCSTRIKE` or `TICKER[spaces]YYMMDDPSTRIKE`

**Examples:**
- `SOFI  260402C00020000` - SOFI Call expiring 2026-04-02 at strike $20.00
- `AAPL  260115P00150000` - AAPL Put expiring 2026-01-15 at strike $150.00

**Components:**
- **TICKER**: Underlying stock symbol (e.g., SOFI, AAPL)
- **YYMMDD**: Expiration date (6 digits)
- **C/P**: Option type (C=Call, P=Put)
- **STRIKE**: Strike price (8 digits, last 3 are decimals)

### 2. Negative Quantities for Short Positions

Options support both long and short positions:

| Quantity | Position Type | Common Use Cases |
|----------|---------------|------------------|
| **Positive** | Long position | Buying calls/puts for speculation or hedging |
| **Negative** | Short position | Covered calls, cash-secured puts, income generation |

**Examples:**

#### Covered Call (Negative Quantity)
```csv
month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price,purchase_date
3,2026,Schwab,Brokerage,Joint,SOFI  260402C00020000,SoFi Technologies Call Option,Options:Call,-1,0.50,2026-03-18
```
- **Qty: -1** = Short 1 call contract (sold/wrote the call)
- You own 100 shares of SOFI and sold a call against them
- Premium received: $50 ($0.50 × 100 shares)

#### Cash-Secured Put (Negative Quantity)
```csv
month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price,purchase_date
3,2026,Schwab,Brokerage,Joint,AAPL  260115P00150000,Apple Inc. Put Option,Options:Put,-2,1.25,2026-03-18
```
- **Qty: -2** = Short 2 put contracts (sold/wrote the puts)
- You have cash secured to buy 200 shares at $150
- Premium received: $250 ($1.25 × 100 shares × 2 contracts)

#### Long Call (Positive Quantity)
```csv
month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price,purchase_date
3,2026,Schwab,Brokerage,Joint,TSLA  260320C00200000,Tesla Inc. Call Option,Options:Call,3,5.00,2026-03-18
```
- **Qty: 3** = Long 3 call contracts (bought the calls)
- Premium paid: $1,500 ($5.00 × 100 shares × 3 contracts)

### 3. Sector Classification

Options are automatically classified into dedicated sectors:

- **Options:Call** - Call options (both long and short)
- **Options:Put** - Put options (both long and short)

These sectors appear in:
- Portfolio holdings editor dropdown
- Portfolio analytics and reports
- Sector allocation charts

### 4. Price Handling

**Important:** Options contracts return `0.0` for current price because:
- Options pricing is complex (time decay, volatility, Greeks)
- Yahoo Finance doesn't provide reliable real-time options prices
- Manual price entry is required

**How to enter prices:**
1. Add the options contract with symbol in OCC format
2. Enter the **premium per share** in the `purchase_price` field
3. For sold options (negative qty), enter the premium you received
4. For bought options (positive qty), enter the premium you paid

**Example:**
- Sold 1 call for $0.50 premium → Enter `-1` qty and `0.50` price
- Bought 2 puts for $1.25 premium → Enter `2` qty and `1.25` price

### 5. Validation Rules

The system enforces these validation rules:

✅ **Allowed:**
- Positive quantities for all securities (long positions)
- Negative quantities for options only (short positions)
- Any non-zero quantity for options

❌ **Not Allowed:**
- Negative quantities for stocks, ETFs, or mutual funds
- Zero quantity for any security
- Invalid OCC format for options symbols

## Usage Examples

### Example 1: Covered Call Strategy

You own 100 shares of SOFI at $18.50 and sell a $20 call expiring April 2, 2026 for $0.50:

```csv
month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price,purchase_date
3,2026,Schwab,Brokerage,Joint,SOFI,SoFi Technologies Inc.,Technology,100,18.50,2026-01-15
3,2026,Schwab,Brokerage,Joint,SOFI  260402C00020000,SoFi Technologies Call Option,Options:Call,-1,0.50,2026-03-18
```

**Portfolio Value:**
- Stock: 100 × $18.50 = $1,850
- Call premium: -1 × $0.50 × 100 = $50 (income)
- Total: $1,900

### Example 2: Cash-Secured Put Strategy

You want to buy AAPL at $150 and sell a put expiring January 15, 2026 for $1.25:

```csv
month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price,purchase_date
3,2026,Schwab,Brokerage,Joint,MF:CASH,Money Market,MF:Cash,15000,1.00,2026-03-18
3,2026,Schwab,Brokerage,Joint,AAPL  260115P00150000,Apple Inc. Put Option,Options:Put,-1,1.25,2026-03-18
```

**Portfolio Value:**
- Cash secured: $15,000 (for potential assignment)
- Put premium: -1 × $1.25 × 100 = $125 (income)
- Total: $15,125

### Example 3: Long Call for Speculation

You buy 5 TSLA $200 calls expiring March 20, 2026 for $5.00:

```csv
month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price,purchase_date
3,2026,Schwab,Brokerage,Joint,TSLA  260320C00200000,Tesla Inc. Call Option,Options:Call,5,5.00,2026-03-18
```

**Portfolio Value:**
- Call premium paid: 5 × $5.00 × 100 = $2,500 (cost)

## Technical Implementation

### Files Modified

1. **portfolio_data_entry.py**
   - Added `is_option_symbol()` function to detect OCC format
   - Updated `VALID_SECTORS` to include `Options:Call` and `Options:Put`
   - Modified `validate_ticker_symbol()` to handle options
   - Updated `validate_portfolio_entry()` to allow negative quantities for options

2. **portfolio.py**
   - Modified `get_current_price()` to return 0.0 for options (manual entry required)

3. **components/portfolio_holdings_editor.py**
   - Updated `get_current_price()` to handle options
   - Updated `get_sector_from_yfinance()` to return options sectors
   - Modified quantity column config to allow negative values

4. **portfolio_market_indicators.py**
   - Updated `fetch_security_data()` to skip options (no meaningful MA analysis)

### Key Functions

#### `is_option_symbol(symbol: str) -> Tuple[bool, str, str]`

Detects if a symbol is an options contract and parses its components.

**Returns:**
- `is_option`: True if this is an options contract
- `underlying_ticker`: The underlying stock symbol
- `option_type`: 'Call' or 'Put' or empty string

**Example:**
```python
is_opt, underlying, opt_type = is_option_symbol("SOFI  260402C00020000")
# Returns: (True, "SOFI", "Call")
```

## Best Practices

### 1. Recording Options Trades

**When selling (writing) options:**
- Use negative quantity
- Enter the premium you **received**
- This represents income/credit to your account

**When buying options:**
- Use positive quantity
- Enter the premium you **paid**
- This represents cost/debit from your account

### 2. Tracking Assignments

If an option is assigned:

**For covered calls (assigned):**
1. Remove the option entry (qty = 0 or delete row)
2. Remove the underlying stock (sold at strike)
3. Add cash received (strike × 100 × contracts)

**For cash-secured puts (assigned):**
1. Remove the option entry
2. Add the underlying stock (bought at strike)
3. Reduce cash by (strike × 100 × contracts)

### 3. Expiration Handling

When options expire worthless:

**For sold options (negative qty):**
- Remove the option entry
- Keep the premium as realized gain

**For bought options (positive qty):**
- Remove the option entry
- Premium paid is realized loss

### 4. Rolling Options

When rolling an option to a new expiration/strike:
1. Close the old option (remove entry)
2. Add the new option with net premium
3. Net premium = new premium - old premium

## Limitations

1. **No automatic price updates**: Options prices must be entered manually
2. **No Greeks calculation**: Delta, gamma, theta, vega not calculated
3. **No market indicators**: Moving average analysis not applicable to options
4. **No expiration tracking**: System doesn't alert on approaching expirations
5. **No assignment tracking**: Manual updates required when assigned

## Future Enhancements

Potential improvements for options support:

- [ ] Automatic expiration date parsing and alerts
- [ ] Options Greeks calculation
- [ ] Assignment probability estimation
- [ ] Options strategy templates (iron condor, butterfly, etc.)
- [ ] Integration with options pricing APIs
- [ ] P&L tracking for closed positions
- [ ] Options chain visualization

## Troubleshooting

### Issue: "No data returned for [options symbol]"

**Cause:** The system tried to fetch market data for an options contract.

**Solution:** This is expected behavior. Options symbols are automatically detected and skipped for price fetching. Enter the premium manually in the `purchase_price` field.

### Issue: "Quantity must be positive"

**Cause:** Trying to use negative quantity for a non-options security.

**Solution:** Negative quantities are only allowed for options contracts. Verify the symbol is in correct OCC format.

### Issue: Symbol not recognized as option

**Cause:** Symbol doesn't match OCC format pattern.

**Solution:** Ensure symbol follows format: `TICKER[spaces]YYMMDDCSTRIKE`
- Example: `SOFI  260402C00020000` (note the spaces after SOFI)
- Ticker must be uppercase letters only
- Date must be 6 digits (YYMMDD)
- Must have C or P after date
- Strike must be 8 digits

## Testing

Run the test suite to verify options support:

```bash
python3 test_options_support.py
```

Expected output:
```
✅ All tests passed!
```

## Support

For questions or issues with options support, refer to:
- This guide (OPTIONS_SUPPORT_GUIDE.md)
- Test file (test_options_support.py)
- Portfolio data entry guide (PORTFOLIO_DATA_ENTRY_GUIDE.md)

---

**Last Updated:** 2026-03-18  
**Version:** 1.0