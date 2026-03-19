# Source - https://stackoverflow.com/a
# Posted by Trenton McKinney, modified by community. See post 'Timeline' for change history
# Retrieved 2025-12-29, License - CC BY-SA 4.0

import yfinance as yf
import pandas as pd
import streamlit as st
import os
import threading as _threading
import logging
from datetime import datetime
from load_data import get_portfolio_truth_by_month, get_latest_portfolio_month_year

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Portfolio disk-cache constants
# ---------------------------------------------------------------------------
# The cache file stores the last successfully built portfolio display DataFrame
# as a Parquet file so the app can render instantly on startup without waiting
# for live yfinance price fetches.  The cache is keyed by month/year so stale
# data from a different period is never shown as current.
PORTFOLIO_CACHE_FILE = "portfolio_display_cache.parquet"
PORTFOLIO_CACHE_TTL_SECONDS = 300  # 5 minutes — matches @st.cache_data(ttl=300)

def color_negative_positive(value):
    """
    Colors the text red if the value is negative, and green if positive or zero.
    """
    if isinstance(value, (int, float)):
        return 'color: red' if value < 0 else 'color: green'
    return ''

@st.cache_data(ttl=300)  # refresh every 5 minutes
def get_current_price(symbol):
    # For cash holdings, return 1.0 (no price lookup needed)
    if symbol == "MF:CASH":
        return 1.0
    
    # Check if this is an options contract
    from portfolio_data_entry import is_option_symbol
    is_option, underlying, option_type = is_option_symbol(symbol)
    
    if is_option:
        # Options contracts don't have reliable price data in yfinance
        # Return 0.0 to indicate manual price entry is needed
        logger.info(f"Options contract detected: {symbol}. Manual price entry required.")
        return 0.0
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Mutual funds (5-letter tickers) need longer period for price data
        # They update less frequently than stocks
        if len(symbol) == 5 and symbol.isalpha():
            period = '5d'  # Use 5 days for mutual funds
        else:
            period = '4d'  # Use 4 days for stocks/ETFs
        
        todays_data = ticker.history(period=period).tail(1)
        if todays_data.empty:
            logger.warning(f"No price data available for {symbol}, treating as cash (MF:CASH)")
            return 1.0  # Treat as cash if no price data available
        return todays_data['Close'].iloc[0]
    except Exception as e:
        # Catch HTTP 404 errors and other exceptions for invalid symbols
        logger.warning(f"Error fetching price for {symbol}: {e}. Treating as cash (MF:CASH)")
        return 1.0  # Treat invalid symbols as cash

#@st.cache_data()
def get_qty(symbol, month=None, year=None):
    df = getPortfolioData(month=month, year=year)
    quantity = df.loc[df['symbol'] == symbol, 'qty'].iloc[0]
    return quantity

#@st.cache_data()
def get_purchase_price(symbol, month=None, year=None):
    df = getPortfolioData(month=month, year=year)
    purchase_price = df.loc[df['symbol'] == symbol, 'purchase_price'].iloc[0]
    #print("Purchase price is: {purchase_price}")
    return purchase_price

#@st.cache_data()
def get_tax_type(symbol, month=None, year=None):
    df = getPortfolioData(month=month, year=year)
    tax_type = df.loc[df['symbol'] == symbol, 'account_type'].iloc[0]
    #print("tax_type price is: {tax_type}")
    return tax_type

#@st.cache_data()
def get_ticker_name(symbol, month=None, year=None):
    # For cash holdings, return "Cash"
    if symbol == "MF:CASH":
        return "Cash"
    
    ticker = yf.Ticker(symbol)
    try:
        short_name = ticker.info.get('shortName', symbol)
        
        # For mutual funds (typically 5-letter tickers), append category
        # Note: yfinance uses 'category' not 'categoryName'
        if len(symbol) == 5 and symbol.isalpha():
            category = ticker.info.get('category')
            if category:
                return f"{short_name} ({category})"
        
        return short_name
    except Exception:
        # Fallback to symbol if info fetch fails
        return symbol


def get_sector(symbol, month=None, year=None):
    #print(f"get sector {symbol}")
    # For cash holdings, return "MF:Cash"
    if symbol == "MF:CASH":
        return "MF:Cash"
    
    # Check if sector is specified in CSV first
    df = getPortfolioData(month=month, year=year)
    csv_sector = df.loc[df['symbol'] == symbol, 'sector'].iloc[0]
    
    # If CSV has a valid sector value (including MF: prefixed), use it
    # This preserves user overrides and MF: categories like MF:Bonds, MF:Global
    # Skip "MUTUALFUND" and "nan" as these need to be looked up
    if isinstance(csv_sector, str) and csv_sector and csv_sector not in ['MUTUALFUND', 'nan', 'Cash']:
        return csv_sector
    
    # Special handling for "Cash" in CSV - convert to MF:Cash for consistency
    if isinstance(csv_sector, str) and csv_sector == 'Cash':
        return 'MF:Cash'
    
    # For mutual funds (5-letter tickers), try to get category from yfinance
    # and prefix it with MF: for consistency
    if len(symbol) == 5 and symbol.isalpha():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            category = info.get('category', '')
            
            # Try category first (for mutual funds)
            if category and category not in ['MUTUALFUND', '']:
                return f"MF:{category}"
            
            # Fallback to categoryName if available
            category_name = info.get('categoryName', '')
            if category_name:
                return f"MF:{category_name}"
                
        except Exception as e:
            pass  # Fall through to check stocks/ETFs
    
    # For stocks/ETFs, get sector from yfinance
    try:
        ticker = yf.Ticker(symbol)
        sector = ticker.info.get('sector')
        if sector:
            return sector
    except Exception:
        pass
    
    # Final fallback - if CSV had MUTUALFUND but we couldn't get better data, return it
    if isinstance(csv_sector, str) and csv_sector == 'MUTUALFUND':
        return 'MF:Unknown'
    
    # Fallback - return "Unknown" for missing data
    return "Unknown"

def calculate_current_value(symbol, month=None, year=None):
    current_value = get_qty(symbol, month=month, year=year) * get_current_price(symbol)
    #print(stock_value_port)
    return current_value

def calculate_cost_basis(symbol, month=None, year=None):
    cost_basis = get_qty(symbol, month=month, year=year) * get_purchase_price(symbol, month=month, year=year)
    #print(stock_value_port)
    return cost_basis

#@st.cache_data()
def get_current_dividend(symbol, month=None, year=None):
    # Cash holdings don't have dividends
    if symbol == "MF:CASH":
        return "na", 0.00, 0
    
    ticker = yf.Ticker(symbol)
    dividends_data = ticker.dividends
    # Find the latest dividend payment date (ex-date) and amount
    if not dividends_data.empty:
       latest_dividend_date = pd.DatetimeIndex(dividends_data.index)[-1].strftime('%m/%d/%Y')
       latest_dividend_amount = dividends_data.iloc[-1]* get_qty(symbol, month=month, year=year)
       annual_dividend_count = get_dividend_frequency(symbol)
       annual_dividend_amount = latest_dividend_amount * annual_dividend_count
    else:
       latest_dividend_date = "na"
       latest_dividend_amount = 0.00
       annual_dividend_amount = 0
       annual_dividend_count = 0
    #print( latest_dividend_date, latest_dividend_amount )
    return latest_dividend_date,latest_dividend_amount, annual_dividend_amount

def get_dividend_frequency(symbol):
    # Cash holdings don't have dividends
    if symbol == "MF:CASH":
        return 0
    
    ticker = yf.Ticker(symbol)
    dividends_history = ticker.dividends
    if not dividends_history.empty:
        # Filter dividends for the year 2025 (from start of year to end of year)
        start_date = '2025-01-01'
        end_date = '2025-12-31'
        dividends_2025 = dividends_history.loc[start_date:end_date]
        count = len(dividends_2025)
    else:
     count =0
    
    return count
    
  
def get_effective_portfolio_month_year(month=None, year=None):
    """
    Return the effective (month, year) for portfolio data.
    If the requested month/year has no data, returns the most recent available.

    Args:
        month (int, optional): Requested month. Defaults to current month.
        year (int, optional): Requested year. Defaults to current year.

    Returns:
        tuple[int, int]: (effective_month, effective_year)
    """
    if month is None or year is None:
        now = datetime.now()
        month = month or now.month
        year = year or now.year

    portdf = get_portfolio_truth_by_month(month, year)
    if portdf.empty:
        return get_latest_portfolio_month_year()
    return month, year


@st.cache_data()
def getPortfolioData(month=None, year=None):
    """
    Get portfolio data for a specific month and year.
    If month/year not provided, defaults to current month/year.
    Falls back to the most recent available month/year when no data exists for
    the requested period.

    Args:
        month (int, optional): Month number (1-12). Defaults to current month.
        year (int, optional): Year (e.g., 2025, 2026). Defaults to current year.

    Returns:
        pd.DataFrame: Portfolio data with columns: account_name, account_type,
                      symbol, name, sector, qty, purchase_price, purchase_date
    """
    # Use current month/year if not provided
    if month is None or year is None:
        now = datetime.now()
        month = month or now.month
        year = year or now.year

    # Get portfolio data from the truth dataset
    portdf = get_portfolio_truth_by_month(month, year)

    # Fall back to the most recent available month when current month has no data
    if portdf.empty:
        effective_month, effective_year = get_latest_portfolio_month_year()
        if (effective_month, effective_year) != (month, year):
            portdf = get_portfolio_truth_by_month(effective_month, effective_year)

    if portdf.empty:
        return pd.DataFrame(columns=pd.Index(['account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date']))

    # Select the required columns, now including account_name for unique identification
    selected_columns = ['account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date']
    df_selected = pd.DataFrame(portdf[selected_columns])

    # Remove duplicates based on account_name and symbol combination
    df_selected = df_selected.drop_duplicates(subset=['account_name', 'symbol'], keep='first')

    return df_selected

def get_entry_in_portfolio(symbol, month=None, year=None):
    try:
        cols_to_extract = ['symbol', 'name','sector', 'qty', 'purchase_price']
        df = getPortfolioData(month=month, year=year)
        filtered_rows = df.loc[df['symbol'] == symbol]
        extracted_data = filtered_rows[cols_to_extract]
        return extracted_data
    except KeyError as e:
        print(f"Error: One of the specified columns was not found: {e}")
        return None



def get_list_of_tickers(month=None, year=None):
    """
    Get list of unique account_name + symbol combinations for a given month/year.
    
    Returns:
        list: List of tuples (account_name, symbol)
    """
    portdf = getPortfolioData(month=month, year=year)
    # Return list of tuples with (account_name, symbol) for unique identification
    ticker_list = list(zip(portdf['account_name'], portdf['symbol']))
    return ticker_list
    
def format_quantity(qty):
    """
    Format quantity: whole number if decimal is 0, otherwise 2 decimal places.
    
    Args:
        qty: The quantity value to format
    
    Returns:
        str: Formatted quantity string
    """
    if qty == int(qty):
        return f"{int(qty)}"
    else:
        return f"{qty:.2f}"

# Canonical column list for the portfolio display DataFrame.
# Used both when building rows and when returning an empty result so that
# downstream code can always rely on these columns being present.
PORTFOLIO_DISPLAY_COLUMNS = [
    'Account', 'Tax Type', 'Ticker', 'Name', 'Sector',
    'Quantity', 'Price', 'Current value', 'Cost Basis', 'Net Return',
    'Dividend date', 'Dividend Amount', 'annual dividend amount', 'dividend yield',
]

def _build_totals_row(portdf: pd.DataFrame) -> pd.DataFrame:
    """
    Compute portfolio-wide totals and return them as a single-row DataFrame
    aligned to the same columns as *portdf*.

    Numeric columns are summed; all other columns are left as NaN so that
    pandas can correctly infer dtypes during the subsequent concat (avoids
    FutureWarning about empty/all-NA entries).
    """
    numeric_cols = ['Current value', 'Cost Basis', 'Net Return', 'annual dividend amount']
    sums = portdf[numeric_cols].sum()
    total_yield = (
        sums['annual dividend amount'] / sums['Cost Basis']
        if sums['Cost Basis'] > 0 else 0
    )
    totals = pd.Series({
        'Account':                'Portfolio Totals',
        'Current value':          sums['Current value'],
        'Cost Basis':             sums['Cost Basis'],
        'Net Return':             sums['Net Return'],
        'annual dividend amount': sums['annual dividend amount'],
        'dividend yield':         total_yield,
    })
    # Align to the full column set; missing columns become NaN automatically.
    return totals.reindex(portdf.columns).to_frame().T


@st.cache_data()
def build_portfolio_display(month=None, year=None):
    """
    Build portfolio display with unique account_name + symbol combinations.
    Each row represents a unique holding in a specific account.
    Includes a totals row at the bottom.
    """
    portfolio_data = getPortfolioData(month=month, year=year)

    # If there is no portfolio data for the requested month/year, return an
    # empty DataFrame that still carries the expected column schema so that
    # callers can safely reference columns like 'Account' without a KeyError.
    if portfolio_data.empty:
        return pd.DataFrame(columns=pd.Index(PORTFOLIO_DISPLAY_COLUMNS))

    # Pre-fetch per-symbol data once to avoid redundant external calls for
    # symbols that appear across multiple accounts.
    unique_symbols = portfolio_data['symbol'].unique()
    price_cache  = {s: get_current_price(s)                            for s in unique_symbols}
    sector_cache = {s: get_sector(s, month=month, year=year)           for s in unique_symbols}
    name_cache   = {s: get_ticker_name(s, month=month, year=year)      for s in unique_symbols}
    div_cache    = {s: get_current_dividend(s, month=month, year=year) for s in unique_symbols}

    # Build a flat per-symbol lookup DataFrame (Suggestion 3).
    # Unpacking the dividend tuple here keeps the downstream merge + assign clean.
    lookup = pd.DataFrame({
        'symbol':                 unique_symbols,
        'Price':                  [price_cache[s]     for s in unique_symbols],
        'Sector':                 [sector_cache[s]    for s in unique_symbols],
        'Name':                   [name_cache[s]      for s in unique_symbols],
        'Dividend date':          [div_cache[s][0]    for s in unique_symbols],
        'Dividend Amount':        [div_cache[s][1]    for s in unique_symbols],
        'annual dividend amount': [div_cache[s][2]    for s in unique_symbols],
    })

    # Merge lookup data with portfolio rows, then derive all computed columns
    # in a single vectorized pass — no per-row Python loop (Suggestion 1).
    # Direct bracket assignment is used for column names that contain spaces,
    # since .assign() only accepts valid Python identifiers as keyword args.
    merged = portfolio_data.merge(lookup, on='symbol', how='left')

    merged['Account']                = merged['account_name']
    merged['Tax Type']               = merged['account_type']
    merged['Ticker']                 = merged['symbol'].where(merged['symbol'] != 'MF:CASH', 'Cash')
    merged['Quantity']               = merged['qty'].map(format_quantity)
    merged['Current value']          = merged['qty'] * merged['Price']
    merged['Cost Basis']             = merged['qty'] * merged['purchase_price']
    merged['Net Return']             = merged['Current value'] - merged['Cost Basis']
    merged['dividend yield']         = (
        merged['annual dividend amount']
        .div(merged['Cost Basis'])
        .where(merged['Cost Basis'] > 0, other=0)
    )

    portdf: pd.DataFrame = pd.DataFrame(merged[PORTFOLIO_DISPLAY_COLUMNS])

    # Append totals row at the bottom (Suggestion 2 + 4).
    if not portdf.empty:
        portdf = pd.DataFrame(pd.concat([portdf, _build_totals_row(portdf)], ignore_index=True))

    return portdf


def get_portfolio_dividend_total():
    portdf = build_portfolio_display()
    divy_total = portdf[['annual dividend amount']].sum()
    #print(divy_total)
    return  divy_total


# ---------------------------------------------------------------------------
# Disk-cache helpers
# ---------------------------------------------------------------------------

def save_portfolio_cache(portdf: pd.DataFrame, month: int, year: int) -> None:
    """Persist *portdf* (the full display DataFrame including totals row) to disk.

    The file is a Parquet document that also stores the month/year key and the
    UTC timestamp of the save so that :func:`load_portfolio_cache` can validate
    freshness on the next startup.

    Args:
        portdf:  The DataFrame returned by :func:`build_portfolio_display`.
        month:   Portfolio month (1-12).
        year:    Portfolio year (e.g. 2025).
    """
    try:
        # Attach metadata as extra columns that survive the round-trip.
        # We use a single-row metadata frame and concat so the main data is
        # untouched; callers strip these columns on load.
        meta = pd.DataFrame({
            "_cache_month": [int(month)],
            "_cache_year":  [int(year)],
            "_cache_ts":    [datetime.utcnow().isoformat()],
        })
        # Pad meta to match portdf row count (fill with NaN) so concat works.
        meta_padded = meta.reindex(portdf.index)
        meta_padded.iloc[0] = meta.iloc[0]

        out = portdf.copy()
        out["_cache_month"] = meta_padded["_cache_month"]
        out["_cache_year"]  = meta_padded["_cache_year"]
        out["_cache_ts"]    = meta_padded["_cache_ts"]

        out.to_parquet(PORTFOLIO_CACHE_FILE, index=False)
    except Exception as exc:
        # Cache write failures are non-fatal — the app continues without cache.
        print(f"[portfolio cache] save failed: {exc}")


def load_portfolio_cache(month: int, year: int) -> pd.DataFrame:
    """Load the cached portfolio display DataFrame from disk.

    Returns the cached DataFrame (without the internal ``_cache_*`` columns)
    when the cache exists, matches the requested *month*/*year*, and is no
    older than :data:`PORTFOLIO_CACHE_TTL_SECONDS`.

    Returns an empty DataFrame (with the canonical :data:`PORTFOLIO_DISPLAY_COLUMNS`
    schema) when the cache is absent, stale, or belongs to a different period.

    Args:
        month:  Requested portfolio month (1-12).
        year:   Requested portfolio year (e.g. 2025).

    Returns:
        pd.DataFrame: Cached portfolio display data, or empty DataFrame.
    """
    try:
        if not os.path.exists(PORTFOLIO_CACHE_FILE):
            return pd.DataFrame(columns=pd.Index(PORTFOLIO_DISPLAY_COLUMNS))

        cached = pd.read_parquet(PORTFOLIO_CACHE_FILE)

        # Validate month/year key
        cached_month = int(cached["_cache_month"].iloc[0]) if "_cache_month" in cached.columns else -1
        cached_year  = int(cached["_cache_year"].iloc[0])  if "_cache_year"  in cached.columns else -1
        if cached_month != month or cached_year != year:
            return pd.DataFrame(columns=pd.Index(PORTFOLIO_DISPLAY_COLUMNS))

        # Validate TTL
        cached_ts_str = cached["_cache_ts"].iloc[0] if "_cache_ts" in cached.columns else None
        if cached_ts_str:
            cached_ts = datetime.fromisoformat(str(cached_ts_str))
            age_seconds = (datetime.utcnow() - cached_ts).total_seconds()
            if age_seconds > PORTFOLIO_CACHE_TTL_SECONDS:
                return pd.DataFrame(columns=pd.Index(PORTFOLIO_DISPLAY_COLUMNS))

        # Strip internal metadata columns before returning
        display_cols = [c for c in cached.columns if not c.startswith("_cache_")]
        return pd.DataFrame(cached[display_cols]).reset_index(drop=True)

    except Exception as exc:
        print(f"[portfolio cache] load failed: {exc}")
        return pd.DataFrame(columns=pd.Index(PORTFOLIO_DISPLAY_COLUMNS))


def _rebuild_and_cache(month: int, year: int, done_event: "_threading.Event") -> None:
    """Background worker: call :func:`build_portfolio_display`, then persist to disk.

    Designed to be run in a :class:`threading.Thread`.  Sets *done_event* when
    finished (whether successful or not) so callers can detect completion.

    Args:
        month:       Portfolio month (1-12).
        year:        Portfolio year (e.g. 2025).
        done_event:  :class:`threading.Event` to set on completion.
    """
    try:
        portdf = build_portfolio_display(month=month, year=year)
        if not portdf.empty:
            save_portfolio_cache(portdf, month, year)
    except Exception as exc:
        print(f"[portfolio cache] background rebuild failed: {exc}")
    finally:
        done_event.set()


def render_portfolio(month: int, year: int, done_event: "_threading.Event") -> pd.DataFrame:
    """Return the best available portfolio display DataFrame for *month*/*year*.

    **Startup / fast-path behaviour**
    On first call (or after the cache has expired / been invalidated) this
    function immediately returns the last-known-good data from the on-disk
    Parquet cache so the UI renders without delay.  Simultaneously it launches
    (or re-uses) a background thread that calls :func:`build_portfolio_display`
    with live yfinance prices and writes the result back to disk.

    **Cache-hit behaviour**
    When the cache is fresh (< :data:`PORTFOLIO_CACHE_TTL_SECONDS` old) and
    matches the requested period, the cached DataFrame is returned directly and
    *no* background thread is started.

    **Background rebuild**
    The background thread sets *done_event* when it finishes.  Callers that
    want to trigger a Streamlit rerun once live data is ready should check
    ``done_event.is_set()`` and call ``st.rerun()`` accordingly.

    Args:
        month:       Portfolio month (1-12).
        year:        Portfolio year (e.g. 2025).
        done_event:  A :class:`threading.Event` stored in ``st.session_state``
                     so it survives Streamlit reruns.  Pass the same object on
                     every call within a session.

    Returns:
        pd.DataFrame: Portfolio display data (may be from cache or live build).
    """
    cached = load_portfolio_cache(month, year)

    if not cached.empty:
        # Cache is fresh — kick off a background refresh only if the event has
        # already been set (meaning a previous rebuild finished) so we don't
        # pile up threads on every rerun.
        if done_event.is_set():
            done_event.clear()
            _t = _threading.Thread(
                target=_rebuild_and_cache,
                args=(month, year, done_event),
                daemon=True,
            )
            _t.start()
        return cached

    # Cache is empty / stale / wrong period — start background rebuild if not
    # already running (event not yet set means a thread is in flight).
    if not done_event.is_set():
        # Thread already running — return empty frame; caller shows spinner
        return pd.DataFrame(columns=pd.Index(PORTFOLIO_DISPLAY_COLUMNS))

    # Launch a fresh background rebuild
    done_event.clear()
    _t = _threading.Thread(
        target=_rebuild_and_cache,
        args=(month, year, done_event),
        daemon=True,
    )
    _t.start()
    return pd.DataFrame(columns=pd.Index(PORTFOLIO_DISPLAY_COLUMNS))

def backup_file(current_file_name, backup_filename):   
    try:
        os.rename(current_file_name, backup_filename)
      #  print(f"File successfully renamed to: {backup_filename}")
    except FileNotFoundError:
        print(f"Error: The file '{current_file_name}' was not found.")
    except FileExistsError:
        print(f"Error: A file named '{backup_filename}' already exists.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
def add_rows_to_portfolio(original_df,new_rows_df):
      df_merged = pd.concat([original_df, new_rows_df], ignore_index=True) 
      return df_merged 
  
#def update_portfolio(df):
    
     
    
      
