# Portfolio Data Entry Guide

## Overview

[`portfolio_data_entry.py`](portfolio_data_entry.py:1) provides the backend for the **Portfolio Holdings** section of the Configuration page. It handles manual entry, validation, saving, backup, and restoration of portfolio data stored in [`portfolio_data_truth.csv`](portfolio_data_truth.csv).

The portfolio data file is the single source of truth for all account balances used throughout the application — the Dashboard tab, Strategy tab, and Portfolio Rebalancing tab all read from this file.

> **Important:** The application requires at least **2 months** of portfolio data to function correctly. The most recent month is used for current balances; the prior month is used for comparison and growth calculations.

---

## CSV File Format

### File: `portfolio_data_truth.csv`

Each row represents one holding in one account for one month.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `month` | int (1–12) | ✅ | Month of the snapshot |
| `year` | int (2000–2100) | ✅ | Year of the snapshot |
| `account_name` | string | ✅ | Account name (e.g., `"Schwab"`, `"Fidelity"`) |
| `account_type` | string | ✅ | One of: `Cash`, `Brokerage`, `Traditional`, `Roth` |
| `symbol` | string | ✅ | Ticker symbol (e.g., `"AAPL"`, `"FXAIX"`, `"MF:CASH"`) |
| `name` | string | ✅ | Security name (e.g., `"Apple Inc."`, `"Fidelity 500 Index"`) |
| `sector` | string | ✅ | Sector classification (see valid sectors below) |
| `qty` | float | ✅ | Number of shares or units held (must be > 0) |
| `purchase_price` | float | ✅ | Average cost basis per share (must be > 0) |

### Example Rows

```csv
month,year,account_name,account_type,symbol,name,sector,qty,purchase_price
2,2026,Schwab,Roth,AAPL,Apple Inc.,Technology,50.0,150.00
2,2026,Schwab,Roth,FXAIX,Fidelity 500 Index Fund,MF:Large-Cap,100.0,185.50
2,2026,Fidelity,Traditional,FSKAX,Fidelity Total Market Index,MF:Large-Cap,200.0,120.00
2,2026,Vanguard,Brokerage,MF:CASH,Money Market,MF:Cash,1.0,55000.00
2,2026,Chase,Cash,MF:CASH,Money Market,MF:Cash,1.0,25000.00
```

### Valid Account Types

| Value | Description | Tax Treatment |
|-------|-------------|---------------|
| `Cash` | Checking / savings / money market | After-tax; interest taxable |
| `Brokerage` | Taxable brokerage account | After-tax; LTCG/STCG on gains |
| `Traditional` | Traditional IRA / 401k | Pre-tax; ordinary income on withdrawal |
| `Roth` | Roth IRA / Roth 401k | After-tax; tax-free growth and withdrawal |

### Valid Sectors

```
MF:Cash           MF:Large-Cap      MF:Mid-Cap        MF:Small-Cap
MF:Reit           MF:Global         MF:Asia           MF:Europe
MF:Latin America  Stock/ETF         Technology        Healthcare
Financial Services Energy            Industrials       Real Estate
Utilities         Basic Materials   Consumer Cyclical Consumer Defensive
Communication Services Automotive
```

### Special Symbol: `MF:CASH`

Use `MF:CASH` as the symbol for cash positions (money market funds, checking accounts, savings accounts). The application treats this symbol specially:
- Skips Yahoo Finance price lookup (always valued at `qty × purchase_price`)
- Classified as the `Cash` asset class in portfolio rebalancing
- Set `qty = 1.0` and `purchase_price = <dollar amount>` for cash positions

---

## Workflow: First-Time Setup

### Step 1: Define Your Accounts

1. Navigate to **Configuration** → **Portfolio Data** tab
2. Under **Account Configuration**, click **Add Account**
3. Enter account name (e.g., `"Schwab"`) and select account type (`"Roth"`)
4. Repeat for each account
5. Click **Save Account Configuration**

### Step 2: Enter First Month of Data

1. Under **Portfolio Holdings**, click **Add Empty Row** (or **Copy Previous Month**)
2. For each holding, fill in:
   - **Month** and **Year** (current month)
   - **Account Name** (must match an account defined in Step 1)
   - **Account Type** (must match the account's type)
   - **Symbol** (ticker symbol or `MF:CASH`)
   - **Name** (security name)
   - **Sector** (select from dropdown)
   - **Qty** (number of shares)
   - **Purchase Price** (average cost basis per share)
3. Click **Validate Data** to check for errors
4. Fix any validation errors shown in red
5. Click **Save Portfolio Data**

### Step 3: Enter Second Month of Data

The application needs at least 2 months of data. After saving the first month:

1. Click **Copy Previous Month** — this loads last month's data with the month/year updated to the current month
2. Update quantities and prices that have changed
3. Add any new holdings; remove any sold positions (delete the row)
4. Validate and save

---

## Workflow: Monthly Update

Each month, update your portfolio data to reflect current holdings:

1. Open **Configuration** → **Portfolio Data** tab
2. Click **Copy Previous Month** to pre-populate with last month's data
3. Update changed values:
   - Adjust `qty` for any buys/sells
   - Update `purchase_price` for new lots (use average cost basis)
   - Add new holdings as new rows
   - Delete rows for fully sold positions
4. For cash accounts: update `purchase_price` to the current balance (keep `qty = 1.0`)
5. Click **Validate Data**
6. Review and fix any errors
7. Click **Save Portfolio Data** — a timestamped backup is created automatically before saving

---

## Workflow: Handling Account Changes

### Adding a New Account

1. Go to **Account Configuration** and add the new account
2. Save account configuration
3. In **Portfolio Holdings**, add rows for the new account's holdings
4. Save portfolio data

### Closing an Account

1. In the current month's data, delete all rows for the closed account
2. Save — the account's holdings will no longer appear in future months
3. Historical data for the account is preserved in the CSV

### Transferring Between Accounts

When transferring assets between accounts (e.g., in-kind transfer from Traditional to Roth):
1. Remove the holding from the source account (delete or zero out qty)
2. Add the holding to the destination account with the same cost basis
3. Update account types accordingly

---

## API Reference

### `validate_ticker_symbol(symbol)`

```python
def validate_ticker_symbol(symbol: str) -> Tuple[bool, str, str, str]
```

Validates a ticker symbol via Yahoo Finance. Returns `(is_valid, name, sector, error_message)`.

- `MF:CASH` and `CASH` are handled as special cases (always valid, returns `"Money Market"` / `"MF:Cash"`)
- For all other symbols, queries Yahoo Finance for name and sector
- Network errors return `(False, '', '', error_message)`

**Example:**
```python
from portfolio_data_entry import validate_ticker_symbol

is_valid, name, sector, error = validate_ticker_symbol("AAPL")
# is_valid=True, name="Apple Inc.", sector="Technology", error=""

is_valid, name, sector, error = validate_ticker_symbol("MF:CASH")
# is_valid=True, name="Money Market", sector="MF:Cash", error=""
```

---

### `validate_portfolio_entry(row)`

```python
def validate_portfolio_entry(row: pd.Series) -> Tuple[bool, str]
```

Validates a single portfolio entry row. Returns `(is_valid, error_message)`.

**Validation rules:**

| Field | Rule |
|-------|------|
| `month` | Required; integer 1–12 |
| `year` | Required; integer 2000–2100 |
| `account_name` | Required; non-empty string |
| `account_type` | Required; must be one of `Cash`, `Brokerage`, `Traditional`, `Roth` |
| `symbol` | Required; non-empty string |
| `qty` | Required; positive float |
| `purchase_price` | Required; positive float |

---

### `validate_portfolio_dataframe(df)`

```python
def validate_portfolio_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]
```

Validates an entire DataFrame. Returns `(valid_df, invalid_df)` where `invalid_df` has an additional `validation_error` column.

**Example:**
```python
from portfolio_data_entry import validate_portfolio_dataframe
import pandas as pd

df = pd.read_csv("portfolio_data_truth.csv")
valid_df, invalid_df = validate_portfolio_dataframe(df)

if not invalid_df.empty:
    print("Validation errors:")
    print(invalid_df[['symbol', 'account_name', 'validation_error']])
```

---

### `save_portfolio_data(new_data, append=True)`

```python
def save_portfolio_data(new_data: pd.DataFrame, append: bool = True) -> Tuple[bool, str]
```

Saves portfolio data to [`portfolio_data_truth.csv`](portfolio_data_truth.csv).

**Parameters:**
- `new_data`: DataFrame with portfolio entries (must have all required columns)
- `append`: If `True` (default), merges with existing file — existing rows matching `(month, year, account_name, symbol)` are replaced; non-matching rows are preserved. If `False`, overwrites the entire file.

**Merge key:** `(month, year, account_name, symbol)` — this uniquely identifies each holding in each month.

**Returns:** `(success: bool, message: str)`

**Example:**
```python
from portfolio_data_entry import save_portfolio_data
import pandas as pd

new_entries = pd.DataFrame([{
    'month': 3, 'year': 2026,
    'account_name': 'Schwab', 'account_type': 'Roth',
    'symbol': 'AAPL', 'name': 'Apple Inc.',
    'sector': 'Technology', 'qty': 55.0, 'purchase_price': 155.00
}])

success, message = save_portfolio_data(new_entries, append=True)
print(message)  # "Successfully updated 1 existing entries in portfolio_data_truth.csv"
```

---

### `load_previous_month_data(month, year)`

```python
def load_previous_month_data(month: int, year: int) -> pd.DataFrame
```

Loads the previous month's portfolio data as a template for the current month. Updates `month` and `year` fields to the current values.

- If no previous month data exists, returns an empty template via [`create_empty_entry_template()`](portfolio_data_entry.py:272)
- Handles year rollover (January → December of prior year)

---

### `create_empty_entry_template(month=None, year=None)`

```python
def create_empty_entry_template(month: Optional[int] = None,
                                 year: Optional[int] = None) -> pd.DataFrame
```

Creates a single-row empty template DataFrame with all required columns. Defaults to the current month and year.

---

### `backup_portfolio_data()`

```python
def backup_portfolio_data() -> Tuple[bool, str]
```

Creates a timestamped backup of [`portfolio_data_truth.csv`](portfolio_data_truth.csv).

**Backup filename format:** `portfolio_data_truth_YYYYMMDD_HHMMSS.csv`

**Example:**
```python
from portfolio_data_entry import backup_portfolio_data

success, message = backup_portfolio_data()
# message: "Backup created: portfolio_data_truth_20260301_143022.csv"
```

---

### `revert_to_last_backup()`

```python
def revert_to_last_backup() -> Tuple[bool, str]
```

Restores [`portfolio_data_truth.csv`](portfolio_data_truth.csv) from the most recent backup file. Before reverting, creates a safety backup of the current file named `portfolio_data_truth_before_revert_YYYYMMDD_HHMMSS.csv`.

---

### `start_from_scratch()`

```python
def start_from_scratch() -> Tuple[bool, str]
```

Backs up the current portfolio file and creates a blank file with only column headers. Use this when you want to re-enter all data from scratch.

---

### `get_latest_backup()`

```python
def get_latest_backup() -> Optional[str]
```

Returns the filename of the most recent backup file, or `None` if no backups exist. Backups are sorted by file modification time.

---

## Backup & Restore Procedures

### Automatic Backups

The application creates a timestamped backup automatically before each save operation in the Configuration UI. Backups are stored in the same directory as the main file:

```
portfolio_data_truth.csv                    ← current data
portfolio_data_truth_20260301_143022.csv    ← backup from March 1
portfolio_data_truth_20260228_091500.csv    ← backup from Feb 28
```

### Manual Backup

```python
from portfolio_data_entry import backup_portfolio_data
success, msg = backup_portfolio_data()
```

Or via the Configuration UI: **Portfolio Data** tab → **Data Management** → **Create Backup**.

### Restoring from Backup

**Via Python:**
```python
from portfolio_data_entry import revert_to_last_backup
success, msg = revert_to_last_backup()
print(msg)
```

**Manually:**
1. Identify the backup file you want to restore (check timestamps)
2. Copy it over the main file:
   ```bash
   cp portfolio_data_truth_20260228_091500.csv portfolio_data_truth.csv
   ```

### Cleaning Up Old Backups

Backups are not automatically deleted. Periodically clean up old backups:

```bash
# List all backups sorted by date
ls -lt portfolio_data_truth_*.csv

# Remove backups older than 30 days (macOS/Linux)
find . -name "portfolio_data_truth_*.csv" -mtime +30 -delete
```

---

## Troubleshooting

### "Missing required field" validation error

**Cause:** One or more required columns are empty.

**Fix:** Ensure all fields are filled in. The `name` field (security name) is required but can be set to the symbol if the full name is unknown.

### "Invalid account_type" error

**Cause:** The `account_type` value doesn't match one of the four valid types.

**Fix:** Use exactly: `Cash`, `Brokerage`, `Traditional`, or `Roth` (case-sensitive).

### "Quantity must be positive" error

**Cause:** `qty` is 0 or negative.

**Fix:** For cash positions, set `qty = 1.0` and `purchase_price = <dollar balance>`. For securities, enter the actual share count.

### Portfolio data not loading in Dashboard

**Cause:** No data exists for the current month/year, or the file is missing.

**Fix:**
1. Verify [`portfolio_data_truth.csv`](portfolio_data_truth.csv) exists in the application directory
2. Check that data exists for the current month and year
3. If only one month of data exists, add a second month (the application requires ≥ 2 months)

### Ticker symbol not found

**Cause:** Yahoo Finance cannot find the symbol, or there is a network issue.

**Fix:**
- Verify the symbol is correct (check on finance.yahoo.com)
- For mutual funds, use the fund's ticker (e.g., `FXAIX`, not `"Fidelity 500"`)
- For cash positions, use `MF:CASH`
- If Yahoo Finance is unavailable, enter the name and sector manually

### Accidentally overwrote data

**Fix:** Use [`revert_to_last_backup()`](portfolio_data_entry.py:448) or manually copy the most recent timestamped backup file over [`portfolio_data_truth.csv`](portfolio_data_truth.csv).

### File permissions error on save

**Cause:** The CSV file is open in another application (e.g., Excel) or is read-only.

**Fix:**
- Close any other applications that have the file open
- Check file permissions: `ls -la portfolio_data_truth.csv`
- On Windows, ensure the file is not marked read-only

---

## Integration with the Application

### How Portfolio Data Flows Through the App

```
portfolio_data_truth.csv
        │
        ▼
load_data.py → get_networth_by_month(month, year)
        │
        ├──▶ income_expense.py → Dashboard tab (current balances)
        ├──▶ strategy.py → Strategy tab (initial portfolio balances)
        ├──▶ portfolio_rebalancing.py → Rebalancing tab (holdings + asset classes)
        └──▶ portfolio.py → Portfolio tab (holdings display)
```

### Market Value Calculation

The application fetches current market prices from Yahoo Finance at runtime:

```
market_value = current_price × qty
```

For `MF:CASH` positions: `market_value = purchase_price × qty` (no price lookup).

The `purchase_price` column stores the **cost basis** (average purchase price), not the current price. The difference between `market_value` and `purchase_price × qty` represents unrealized gain/loss.

---

## See Also

- [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) — Configuration system including portfolio account setup
- [`PORTFOLIO_REBALANCING_GUIDE.md`](PORTFOLIO_REBALANCING_GUIDE.md) — How portfolio data is used for rebalancing analysis
- [`INCOME_EXPENSE_GUIDE.md`](INCOME_EXPENSE_GUIDE.md) — How portfolio data feeds the income/expense simulation
- [`LOGGING_GUIDE.md`](LOGGING_GUIDE.md) — Enable debug logging for data loading

---

**Module:** [`portfolio_data_entry.py`](portfolio_data_entry.py:1)  
**Data File:** [`portfolio_data_truth.csv`](portfolio_data_truth.csv)  
**Last Updated:** 2026-03-01  
**Author:** Bob