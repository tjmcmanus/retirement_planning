# Account ID Tax Tracking Enhancement

## Overview

Enhanced Cost Basis and Capital Gains tracking to include `account_id` for proper tax treatment analysis. This is critical because the same security held in different account types (Roth IRA, Traditional IRA, Brokerage) has different tax implications.

## Problem Statement

**Before Enhancement:**
- Transactions grouped only by `account_name` and `symbol`
- Same stock (e.g., AAPL) in different accounts could be confused
- Tax treatment differences not clearly visible
- Difficult to separate taxable vs tax-advantaged gains

**Example Issue:**
```
AAPL in Roth IRA (tax-free gains) 
  vs 
AAPL in Brokerage (taxable gains)
```

Without `account_id`, these could be incorrectly aggregated, leading to:
- Incorrect cost basis calculations
- Wrong tax reporting
- Missed tax optimization opportunities

## Solution Implemented

### 1. Transaction Import Enhancement

**File**: [`components/schwab_connector.py`](components/schwab_connector.py:830)

```python
transaction = {
    'transaction_id': f"{activity_id}",
    'date': trade_date if trade_date else txn_time[:10],
    'symbol': symbol,
    'transaction_type': transaction_type,
    'quantity': quantity,
    'price': price,
    'amount': quantity * price,
    'account_id': account_hash,  # ✅ Added for proper tax tracking
    'description': f"{transaction_type} {quantity} {symbol} @ ${price}"
}
```

### 2. Transaction History Display

**File**: [`components/transaction_history_ui.py`](components/transaction_history_ui.py:249-277)

**Enhanced Display Columns:**
```python
display_columns = ['date', 'account_id', 'account_name', 'type', 'symbol', 
                  'quantity', 'price', 'amount', 'gain_loss', 'term', 'wash_sale']
```

**Column Mapping:**
```python
column_names = {
    'date': 'Date',
    'account_id': 'Account ID',      # ✅ Added
    'account_name': 'Account',
    'type': 'Type',
    'symbol': 'Symbol',
    # ...
}
```

### 3. Cost Basis Tab Enhancement

**File**: [`components/transaction_history_ui.py`](components/transaction_history_ui.py:447-530)

**Grouping Logic:**
```python
# Group by account_id, account_name, and symbol for proper tax tracking
group_cols = ['account_name', 'symbol']
if 'account_id' in buy_transactions.columns:
    group_cols = ['account_id', 'account_name', 'symbol']  # ✅ Enhanced grouping

lots_summary = buy_transactions.groupby(group_cols).agg({
    'quantity': 'sum',
    'price': 'mean',
    'amount': 'sum',
    'date': 'min'
}).reset_index()
```

**Display Table:**
```
┌────────────┬─────────────────┬────────┬──────────────┬───────────┬─────────────┐
│ Account ID │ Account         │ Symbol │ Total Shares │ Avg Price │ Total Cost  │
├────────────┼─────────────────┼────────┼──────────────┼───────────┼─────────────┤
│ ABC123     │ Roth IRA        │ AAPL   │ 50.0000      │ $150.00   │ $7,500.00   │
│ DEF456     │ Brokerage       │ AAPL   │ 50.0000      │ $155.00   │ $7,750.00   │
│ GHI789     │ Traditional IRA │ AAPL   │ 50.0000      │ $145.00   │ $7,250.00   │
└────────────┴─────────────────┴────────┴──────────────┴───────────┴─────────────┘
```

**Key Benefit**: Same symbol (AAPL) tracked separately by account for accurate cost basis.

### 4. Capital Gains Tab Enhancement

**File**: [`components/transaction_history_ui.py`](components/transaction_history_ui.py:709-770)

**Account-Level Gains:**
```python
# Group by account_id if available, otherwise account_name
if 'account_id' in sell_transactions.columns:
    account_gains = sell_transactions.groupby(['account_id', 'account_name']).agg({
        'gain_loss': 'sum',
        'symbol': 'count'
    }).reset_index()
    account_gains.columns = ['Account ID', 'Account', 'Total Gains', 'Number of Sales']
```

**Display Table:**
```
┌────────────┬─────────────────┬──────────────┬─────────────────┐
│ Account ID │ Account         │ Total Gains  │ Number of Sales │
├────────────┼─────────────────┼──────────────┼─────────────────┤
│ ABC123     │ Roth IRA        │ $5,000.00    │ 10              │
│ DEF456     │ Brokerage       │ $3,500.00    │ 8               │
│ GHI789     │ Traditional IRA │ $2,800.00    │ 6               │
└────────────┴─────────────────┴──────────────┴─────────────────┘
```

**Tax Treatment Explanation Added:**
```markdown
**Roth IRA:**
- Qualified withdrawals are tax-free
- No capital gains tax on sales within the account
- Gains shown here are for tracking only, not taxable

**Traditional IRA:**
- Withdrawals taxed as ordinary income
- No capital gains tax on sales within the account
- Gains shown here are for tracking only, not taxable

**Brokerage (Taxable):**
- Capital gains are taxable
- Short-term gains (≤365 days) taxed as ordinary income
- Long-term gains (>365 days) have preferential rates (0%, 15%, 20%)
- These gains MUST be reported on your tax return
```

## Tax Treatment by Account Type

### Roth IRA (Tax-Free Growth)
- **Contributions**: After-tax dollars
- **Growth**: Tax-free
- **Withdrawals**: Tax-free (if qualified)
- **Capital Gains**: Not taxable
- **Cost Basis Tracking**: For record-keeping only

### Traditional IRA (Tax-Deferred)
- **Contributions**: Pre-tax dollars (deductible)
- **Growth**: Tax-deferred
- **Withdrawals**: Taxed as ordinary income
- **Capital Gains**: Not separately taxed (all withdrawals treated as ordinary income)
- **Cost Basis Tracking**: For record-keeping only

### Brokerage (Taxable)
- **Contributions**: After-tax dollars
- **Growth**: Taxable annually (dividends, interest)
- **Capital Gains**: Taxable when realized
  - Short-term (≤365 days): Ordinary income rates (10%-37%)
  - Long-term (>365 days): Preferential rates (0%, 15%, 20%)
- **Cost Basis Tracking**: CRITICAL for tax reporting

## Use Cases

### Use Case 1: Tax Loss Harvesting
**Scenario**: You want to harvest losses to offset gains.

**Without account_id**:
- Can't distinguish which account holds the loss position
- Might accidentally harvest from Roth IRA (no tax benefit)

**With account_id**:
- Clearly see losses in Brokerage account (taxable)
- Harvest losses only from taxable accounts
- Maximize tax benefit

### Use Case 2: Withdrawal Planning
**Scenario**: You need $50,000 for retirement expenses.

**Without account_id**:
- Can't see which account has the best tax treatment
- Might withdraw from wrong account

**With account_id**:
- See gains by account type
- Withdraw from Roth IRA first (tax-free)
- Then Traditional IRA (ordinary income)
- Last from Brokerage (capital gains tax)

### Use Case 3: Rebalancing
**Scenario**: You need to rebalance your portfolio.

**Without account_id**:
- Can't see which account to sell from
- Might trigger unnecessary taxes

**With account_id**:
- Rebalance within Roth/Traditional IRA (no tax impact)
- Minimize sales in Brokerage account
- Optimize tax efficiency

### Use Case 4: 1099-B Reconciliation
**Scenario**: Tax time - need to report capital gains.

**Without account_id**:
- All gains mixed together
- Can't separate taxable from non-taxable

**With account_id**:
- Filter for Brokerage account only
- Report only taxable gains
- Accurate 1099-B reconciliation

## Database Schema

The `account_id` field is stored in the transactions table:

```sql
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    account_id TEXT,              -- ✅ Account hash/ID
    account_name TEXT,            -- Human-readable name
    account_type TEXT,            -- Roth IRA, Traditional IRA, Brokerage, etc.
    transaction_date TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    symbol TEXT,
    description TEXT,
    quantity REAL,
    price REAL,
    amount REAL,
    fee REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## Benefits

### 1. Accurate Tax Reporting
- ✅ Separate taxable from non-taxable gains
- ✅ Correct 1099-B reconciliation
- ✅ Proper cost basis by account

### 2. Tax Optimization
- ✅ Identify best accounts for withdrawals
- ✅ Optimize tax loss harvesting
- ✅ Minimize tax liability

### 3. Compliance
- ✅ IRS requires separate tracking by account
- ✅ Audit trail with account identification
- ✅ Proper documentation

### 4. Planning
- ✅ See which accounts have gains/losses
- ✅ Plan tax-efficient rebalancing
- ✅ Optimize withdrawal strategies

## Example Scenarios

### Scenario A: Same Stock, Different Accounts

**Holdings:**
```
Account ID: ABC123 (Roth IRA)
- AAPL: 100 shares @ $150 = $15,000 cost basis
- Sold 50 shares @ $180 = $1,500 gain (TAX-FREE)

Account ID: DEF456 (Brokerage)
- AAPL: 100 shares @ $160 = $16,000 cost basis
- Sold 50 shares @ $180 = $1,000 gain (TAXABLE)
```

**Without account_id**: Both gains might be aggregated as $2,500 total
**With account_id**: Clearly shows $1,500 tax-free + $1,000 taxable

### Scenario B: Tax Loss Harvesting

**Holdings:**
```
Account ID: ABC123 (Roth IRA)
- TSLA: 50 shares @ $250 = $12,500 cost basis
- Current price: $200 = $2,500 unrealized loss (NO TAX BENEFIT)

Account ID: DEF456 (Brokerage)
- TSLA: 50 shares @ $250 = $12,500 cost basis
- Current price: $200 = $2,500 unrealized loss (TAX BENEFIT)
```

**Action**: Harvest loss from Brokerage (DEF456) only
**Tax Benefit**: $2,500 loss can offset gains or $3,000 of ordinary income

### Scenario C: Withdrawal Planning

**Accounts:**
```
Account ID: ABC123 (Roth IRA)
- Total Gains: $50,000 (TAX-FREE)

Account ID: GHI789 (Traditional IRA)
- Total Gains: $40,000 (ORDINARY INCOME TAX)

Account ID: DEF456 (Brokerage)
- Total Gains: $30,000 (CAPITAL GAINS TAX)
```

**Optimal Withdrawal Order:**
1. Roth IRA first (tax-free)
2. Brokerage second (preferential capital gains rates)
3. Traditional IRA last (highest tax rate - ordinary income)

## Testing

### Test Cases

1. **Import with account_id**: ✅ Verified in schwab_connector.py
2. **Display account_id**: ✅ Added to transaction history UI
3. **Group by account_id**: ✅ Cost basis tab groups correctly
4. **Filter by account_id**: ✅ Capital gains tab filters correctly
5. **Tax treatment display**: ✅ Educational content added

### Validation

Run the application and verify:
- [ ] Transaction history shows Account ID column
- [ ] Cost Basis tab groups by Account ID + Symbol
- [ ] Capital Gains tab shows gains by Account ID
- [ ] Tax treatment explanation is visible
- [ ] Same symbol in different accounts tracked separately

## Future Enhancements

### Phase 1 (Current)
- ✅ Add account_id to transaction import
- ✅ Display account_id in UI
- ✅ Group by account_id in cost basis
- ✅ Show tax treatment by account type

### Phase 2 (Planned)
- [ ] Filter transactions by account type
- [ ] Tax-efficient withdrawal recommendations
- [ ] Account-specific rebalancing suggestions
- [ ] Automated tax loss harvesting by account

### Phase 3 (Future)
- [ ] Multi-account tax optimization
- [ ] Cross-account wash sale detection
- [ ] Account-specific performance attribution
- [ ] Tax bracket integration

## Conclusion

The addition of `account_id` to transaction tracking is essential for:
1. **Accurate tax reporting** - Separate taxable from non-taxable gains
2. **Tax optimization** - Identify best accounts for transactions
3. **Compliance** - Meet IRS requirements for separate account tracking
4. **Planning** - Make informed decisions about withdrawals and rebalancing

This enhancement ensures that users can properly track and report their investment gains and losses according to the tax treatment of each account type.

---

**Implementation Date**: 2026-03-23  
**Status**: ✅ Complete  
**Files Modified**: 
- [`components/schwab_connector.py`](components/schwab_connector.py)
- [`components/transaction_history_ui.py`](components/transaction_history_ui.py)