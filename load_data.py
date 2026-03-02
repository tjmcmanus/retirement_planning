import pandas as pd
import streamlit as st
import yfinance as yf
from datetime import datetime
import logging
import os
import threading as _threading
from typing import Callable, Optional

# Configure logging
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants
CASH_SYMBOL = 'CASH'
CASH_PRICE = 1.0
# Symbols that represent cash/money-market positions and should never be sent to Yahoo Finance
CASH_SYMBOLS = [CASH_SYMBOL, 'MF:CASH']
MIN_MONTH = 1
MAX_MONTH = 12
MIN_YEAR = 1900
MAX_YEAR = 2100

#@st.cache(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_income_tax_brackets(year, filing_status='married_filing_jointly'):
   dfyear = pd.read_csv('income_rates.csv')
   df = dfyear[(dfyear['year'] == year) & (dfyear['filing_status'] == filing_status)]
   #print(df.head())
   return df

#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_cap_gains_brackets(year, filing_status='married_filing_jointly'):
   cgdfyear= pd.read_csv('cap_gains.csv')
   cgdf = cgdfyear[(cgdfyear['year'] == year) & (cgdfyear['filing_status'] == filing_status)]
   #print(cgdf.head())
   return cgdf
 
#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_std_deduction(year, filing_status='married_filing_jointly'):
    stddectdfyear =pd.read_csv('standard.csv')
    
    # Schema validation: Check for required columns
    required_columns = ['year', 'filing_status', 'deduction']
    missing_columns = [col for col in required_columns if col not in stddectdfyear.columns]
    
    if missing_columns:
        logger.error(f"standard.csv schema mismatch. Missing columns: {missing_columns}")
        logger.error(f"Expected columns: {required_columns}")
        logger.error(f"Found columns: {list(stddectdfyear.columns)}")
        raise ValueError(
            f"standard.csv schema error: Missing columns {missing_columns}. "
            f"Expected format: year,filing_status,deduction. "
            f"Please run migrate_standard_csv.py to update the file format."
        )
    
    stddectdf = stddectdfyear[(stddectdfyear['year'] == year) & (stddectdfyear['filing_status'] == filing_status)]
    
    if stddectdf.empty:
        logger.error(f"No standard deduction data found for year {year}, filing_status {filing_status}")
        raise ValueError(f"Missing standard deduction data for {year}/{filing_status}")
    
    return stddectdf
    
    
#@st.cache_data(allow_output_mutation=True, show_spinner=True)    
@st.cache_data()
def get_medicare_costs(year):
   irmaadfyear =pd.read_csv('irmaa.csv')
   irmaadf= irmaadfyear[irmaadfyear['year'] == year]
   #print(irmaadf.head())
   return irmaadf

#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_atm_costs(year):
   atmdfyear =pd.read_csv('atm.csv')
   atmdf = atmdfyear[atmdfyear['year'] == year]
   #print(atmdf.head())
   return atmdf
#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_ira_limits(year):
   """
   Get IRA contribution limits and Roth phase-out thresholds for a given year.
   
   Returns DataFrame with columns:
   - ira_contribution_base: Base IRA contribution limit
   - ira_catchup_50plus: Catch-up contribution for age 50+
   - roth_phaseout_start_mfj: Roth phase-out start (married filing jointly)
   - roth_phaseout_end_mfj: Roth phase-out end (married filing jointly)
   - roth_phaseout_start_single: Roth phase-out start (single)
   - roth_phaseout_end_single: Roth phase-out end (single)
   - k401_employee_limit: 401(k) employee contribution limit
   - k401_total_limit: 401(k) total contribution limit (IRC 415(c))
   - k401_catchup_50: 401(k) catch-up for age 50-59
   - k401_catchup_60_63: 401(k) catch-up for age 60-63
   """
   ira_limits_year = pd.read_csv('ira_limits.csv')
   ira_limits_df = ira_limits_year[ira_limits_year['year'] == year]
   return ira_limits_df


#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_net_worth(ret_date):
   """
   Get net worth values for a specific date using portfolio truth data.
   
   Args:
       ret_date (str): Date string in format 'M/D/YYYY' or 'MM/DD/YYYY'
   
   Returns:
       tuple: (cash, taxable, tax_deferred, tax_free, total, expenses, daf)
   
   Note: This function now uses get_networth_by_month() which calculates values
         from portfolio_data_truth.csv with current market prices.
         The 'expenses' and 'daf' values are set to 0 as they are not tracked
         in the portfolio truth data.
   """
   try:
       # Parse the date string to extract month and year
       date_obj = datetime.strptime(ret_date, '%m/%d/%Y')
   except ValueError:
       try:
           date_obj = datetime.strptime(ret_date, '%m/%d/%Y')
       except ValueError:
           logger.error(f"Invalid date format: {ret_date}. Expected M/D/YYYY or MM/DD/YYYY")
           return 0, 0, 0, 0, 0, 0, 0
   
   month = date_obj.month
   year = date_obj.year
   
   # Get net worth data from portfolio truth
   detailed_df, summary_df = get_networth_by_month(month, year)
   
   if summary_df.empty:
       logger.warning(f"No portfolio data found for {month}/{year}")
       return 0, 0, 0, 0, 0, 0, 0
   
   # Extract values by account_type
   cash = summary_df[summary_df['account_type'] == 'Cash']['market_value'].sum()
   taxable = summary_df[summary_df['account_type'] == 'Brokerage']['market_value'].sum()
   tax_deferred = summary_df[summary_df['account_type'] == 'Traditional']['market_value'].sum()
   tax_free = summary_df[summary_df['account_type'] == 'Roth']['market_value'].sum()
   
   # Calculate total (excluding the 'Total' row to avoid double counting)
   total = cash + taxable + tax_deferred + tax_free
   
   # expenses and daf are not tracked in portfolio truth data
   expenses = 0
   daf = 0
   
   return cash, taxable, tax_deferred, tax_free, total, expenses, daf



def get_month_account_values(month, year) -> tuple[pd.DataFrame, int, int]:
   """
   Get account values for a specific month and year using portfolio truth data.
   Falls back to the most recent available month/year when no data exists for
   the requested period.

   Args:
       month (int): Month number (1-12)
       year (int): Year (e.g., 2025, 2026)

   Returns:
       tuple: (account_values_df, effective_month, effective_year)
           - account_values_df: DataFrame with columns:
               month, year, account_type, account_name, market_value
           - effective_month: the month whose data is actually returned
           - effective_year:  the year  whose data is actually returned
   """
   # Get detailed portfolio data for the requested month
   detailed_df, summary_df = get_networth_by_month(month, year)

   effective_month, effective_year = month, year

   if detailed_df.empty:
       logger.warning(f"No portfolio data found for {month}/{year}")
       # Fall back to the most recent available month
       effective_month, effective_year = get_latest_portfolio_month_year()
       if (effective_month, effective_year) != (month, year):
           logger.info(f"Falling back to portfolio data for {effective_month}/{effective_year}")
           detailed_df, summary_df = get_networth_by_month(effective_month, effective_year)

   if detailed_df.empty:
       return (
           pd.DataFrame(columns=pd.Index(['month', 'year', 'account_type', 'account_name', 'market_value'])),
           effective_month,
           effective_year,
       )

   # Aggregate by account_type and account_name
   account_values: pd.DataFrame = pd.DataFrame(
       detailed_df.groupby(['account_type', 'account_name'], as_index=False).agg({
           'market_value': 'sum'
       })
   )

   # Add month and year columns for consistency with old format
   account_values['month'] = effective_month
   account_values['year'] = effective_year

   # Reorder columns to match expected format
   account_values = pd.DataFrame(account_values[['month', 'year', 'account_type', 'account_name', 'market_value']])

   return account_values, effective_month, effective_year

def load_ssi_data():
   ssi_data =pd.read_csv('ssincome.csv')
   return  ssi_data

def load_rmd_data():
    """
    Load Required Minimum Distribution (RMD) data from CSV file.
    
    Returns:
        DataFrame: RMD data with 'Age' and 'Distribution' columns
    """
    rmd_data = pd.read_csv('rmd.csv')
    return rmd_data
def get_annual_ssi_data(year):
   ssi_data = load_ssi_data()
   year_df = ssi_data[ssi_data['year']==year]
   return year_df

@st.cache_data()
def load_portfolio_truth():
   """
   Load the complete portfolio data truth dataset.
   
   Returns:
       pd.DataFrame: Complete dataset with columns:
           month, year, account_name, account_type, symbol, name, sector, qty, purchase_price, purchase_date
   """
   portfolio_truth = pd.read_csv('portfolio_data_truth.csv')
   return portfolio_truth

def get_latest_portfolio_month_year() -> tuple[int, int]:
    """
    Return the most recent (month, year) available in portfolio_data_truth.csv.

    Returns:
        tuple[int, int]: (month, year) of the latest entry, e.g. (2, 2026)
    """
    portfolio_truth = load_portfolio_truth()
    if portfolio_truth.empty:
        now = datetime.now()
        return now.month, now.year
    # Build a sortable period key and find the max
    latest = portfolio_truth.assign(
        _period=portfolio_truth['year'] * 100 + portfolio_truth['month']
    ).loc[lambda df: df['_period'].idxmax()]
    return int(latest['month']), int(latest['year'])


def get_portfolio_truth_by_month(month, year):
   """
   Get portfolio data for a specific month and year.
   
   Args:
       month (int): Month number (1-12)
       year (int): Year (e.g., 2025, 2026)
   
   Returns:
       pd.DataFrame: Filtered dataset for the specified month and year
   
   Example:
       # Get December 2025 data
       dec_2025_data = get_portfolio_truth_by_month(12, 2025)
       
       # Get January 2026 data
       jan_2026_data = get_portfolio_truth_by_month(1, 2026)
   """
   portfolio_truth = load_portfolio_truth()
   filtered_data = portfolio_truth[(portfolio_truth['month'] == month) & (portfolio_truth['year'] == year)]
   return filtered_data

def _fetch_current_prices(symbols: list[str]) -> dict[str, Optional[float]]:
    """
    Fetch current prices for multiple symbols from Yahoo Finance in a single batch.
    
    This function uses yfinance.Tickers to fetch all prices at once, which is
    significantly faster than individual requests (10-60x improvement).
    
    Args:
        symbols: List of ticker symbols to fetch prices for
        
    Returns:
        dict: Mapping of symbol -> current_price (or None if unavailable)
        
    Raises:
        ValueError: If symbols list is invalid
        
    Example:
        >>> prices = _fetch_current_prices(['AAPL', 'GOOGL', 'MSFT'])
        >>> print(prices)
        {'AAPL': 150.25, 'GOOGL': 2800.50, 'MSFT': 380.75}
    """
    if not symbols:
        return {}
    
    if not isinstance(symbols, list):
        raise ValueError(f"symbols must be a list, got {type(symbols)}")
    
    # Filter out cash/money-market pseudo-symbols that are not valid Yahoo Finance tickers.
    # These are handled separately (price = 1.0) and must never be sent to the API.
    cash_symbols_in_list = [s for s in symbols if s in CASH_SYMBOLS]
    tradeable_symbols = [s for s in symbols if s not in CASH_SYMBOLS]
    
    if cash_symbols_in_list:
        logger.debug(f"Skipping cash symbols (not sent to Yahoo Finance): {cash_symbols_in_list}")
    
    # Pre-populate cash symbols with CASH_PRICE so callers always get a value back
    price_map: dict[str, float | None] = {s: CASH_PRICE for s in cash_symbols_in_list}
    
    if not tradeable_symbols:
        return price_map
    
    # Batch fetch all tradeable symbols at once (MAJOR PERFORMANCE IMPROVEMENT)
    try:
        tickers = yf.Tickers(' '.join(tradeable_symbols))
    except Exception as e:
        logger.error(f"Failed to initialize yfinance Tickers: {e}")
        return {symbol: None for symbol in symbols}
    
    for symbol in tradeable_symbols:
        try:
            hist = tickers.tickers[symbol].history(period='4d')
            if not hist.empty and 'Close' in hist.columns:
                price_map[symbol] = float(hist['Close'].iloc[-1])
            else:
                logger.warning(f"No price data available for {symbol}")
                price_map[symbol] = None
        except Exception as e:
            logger.warning(f"Could not fetch price for {symbol}: {e}")
            price_map[symbol] = None
    
    return price_map

@st.cache_data(ttl=300)  # Cache for 5 minutes to balance freshness and performance
def get_networth_by_month(month: int, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate net worth for a specific month with current market values from Yahoo Finance.
    
    This method:
    1. Validates input parameters
    2. Fetches portfolio data for the specified month/year
    3. Gets current prices from Yahoo Finance in a single batch request (OPTIMIZED)
    4. Calculates market_value = current_price * qty
    5. Aggregates by account_type (Cash, Brokerage, Traditional, Roth)
    
    Args:
        month: Month number (1-12)
        year: Year (e.g., 2025, 2026)
    
    Returns:
        tuple: (detailed_df, summary_df)
            - detailed_df: DataFrame with all holdings including current_price and market_value
            - summary_df: DataFrame with totals by account_type
    
    Raises:
        ValueError: If month or year parameters are invalid
        RuntimeError: If portfolio data cannot be loaded
    
    Example:
        detailed, summary = get_networth_by_month(12, 2025)
        print(summary)
        # Output:
        #   account_type  market_value
        #   Cash          55000.00
        #   Brokerage     225000.00
        #   Traditional   670000.00
        #   Roth          168000.00
    """
    # Input validation
    if not isinstance(month, int) or not (MIN_MONTH <= month <= MAX_MONTH):
        raise ValueError(f"Month must be an integer between {MIN_MONTH} and {MAX_MONTH}, got {month}")
    
    if not isinstance(year, int) or not (MIN_YEAR <= year <= MAX_YEAR):
        raise ValueError(f"Year must be an integer between {MIN_YEAR} and {MAX_YEAR}, got {year}")
    
    # Get portfolio data for the month
    try:
        portfolio_data = get_portfolio_truth_by_month(month, year)
    except Exception as e:
        logger.error(f"Failed to load portfolio data for {month}/{year}: {e}")
        raise RuntimeError(f"Could not load portfolio data: {e}") from e
    
    # Early return if no data
    if portfolio_data.empty:
        logger.info(f"No portfolio data found for {month}/{year}")
        return pd.DataFrame(), pd.DataFrame()
    
    # Create a copy to avoid modifying original
    detailed_df = pd.DataFrame(portfolio_data.copy())
    
    # Validate required columns
    required_columns = ['symbol', 'purchase_price', 'qty', 'account_type']
    missing_columns = [col for col in required_columns if col not in detailed_df.columns]
    if missing_columns:
        raise ValueError(f"Portfolio data missing required columns: {missing_columns}")
    
    # Initialize current_price with purchase_price as fallback
    detailed_df['current_price'] = detailed_df['purchase_price']
    
    # Get unique non-CASH symbols (handle both 'CASH' and 'MF:CASH')
    non_cash_mask = ~detailed_df['symbol'].isin(CASH_SYMBOLS)
    unique_symbols = detailed_df.loc[non_cash_mask, 'symbol'].unique().tolist()
    
    # Fetch all prices in one batch (MAJOR PERFORMANCE IMPROVEMENT)
    if unique_symbols:
        try:
            price_map = _fetch_current_prices(unique_symbols)
            
            # Apply fetched prices using vectorized operations
            # Only update where we successfully fetched a price
            for symbol, price in price_map.items():
                if price is not None:
                    detailed_df.loc[detailed_df['symbol'] == symbol, 'current_price'] = price
                # If price is None, purchase_price fallback is already set
            
            # Log statistics
            successful_fetches = sum(1 for p in price_map.values() if p is not None)
            logger.info(f"Fetched {successful_fetches}/{len(unique_symbols)} current prices")
        except Exception as e:
            logger.warning(f"Error fetching current prices, using purchase prices as fallback: {e}")
    
    # Set CASH to 1.0 (handle both 'CASH' and 'MF:CASH')
    detailed_df.loc[detailed_df['symbol'].isin(CASH_SYMBOLS), 'current_price'] = CASH_PRICE
    
    # Calculate market_value = current_price * qty (vectorized operation)
    detailed_df['market_value'] = detailed_df['current_price'] * detailed_df['qty']
    
    # Calculate cost_basis for reference (vectorized operation)
    detailed_df['cost_basis'] = detailed_df['purchase_price'] * detailed_df['qty']
    
    # Calculate unrealized gain/loss (vectorized operation)
    detailed_df['unrealized_gl'] = detailed_df['market_value'] - detailed_df['cost_basis']
    
    # Create summary by account_type
    summary_df = detailed_df.groupby('account_type', as_index=False).agg({
        'market_value': 'sum',
        'cost_basis': 'sum',
        'unrealized_gl': 'sum'
    })
    
    # Add total row
    total_row = pd.DataFrame({
        'account_type': ['Total'],
        'market_value': [summary_df['market_value'].sum()],
        'cost_basis': [summary_df['cost_basis'].sum()],
        'unrealized_gl': [summary_df['unrealized_gl'].sum()]
    })
    summary_df = pd.concat([pd.DataFrame(summary_df), total_row], ignore_index=True)
    
    logger.info(f"Net worth calculation complete for {month}/{year}: Total = ${summary_df.iloc[-1]['market_value']:,.2f}")
    
    return pd.DataFrame(detailed_df), summary_df



# ---------------------------------------------------------------------------
# Net Worth disk-cache constants
# ---------------------------------------------------------------------------
# The cache file stores the last successfully built historical net worth
# DataFrame as a Parquet file so the Dashboard can render instantly on startup
# without waiting for live yfinance price fetches across 12 months of data.
# The cache is keyed by num_months and has a 5-minute TTL that matches the
# @st.cache_data(ttl=300) on get_networth_by_month().
NETWORTH_CACHE_FILE = "networth_cache.parquet"
NETWORTH_CACHE_TTL_SECONDS = 300  # 5 minutes

# Canonical column list for the net worth history DataFrame.
NETWORTH_COLUMNS = ["cash", "taxable", "tax_deferred", "tax_free", "total"]


def save_networth_cache(networth_df: pd.DataFrame, num_months: int) -> None:
    """Persist *networth_df* (the historical net worth DataFrame) to disk.

    The Parquet file embeds the ``num_months`` key and a UTC timestamp so that
    :func:`load_networth_cache` can validate freshness on the next startup.

    Args:
        networth_df:  DataFrame with DatetimeIndex and columns
                      cash, taxable, tax_deferred, tax_free, total.
        num_months:   Number of months of history stored (used as cache key).
    """
    try:
        out = networth_df.copy().reset_index()  # move DatetimeIndex → 'date' column
        out["_cache_num_months"] = int(num_months)
        out["_cache_ts"] = datetime.utcnow().isoformat()
        out.to_parquet(NETWORTH_CACHE_FILE, index=False)
    except Exception as exc:
        print(f"[networth cache] save failed: {exc}")


def load_networth_cache(num_months: int) -> pd.DataFrame:
    """Load the cached net worth history DataFrame from disk.

    Returns the cached DataFrame (DatetimeIndex restored, ``_cache_*`` columns
    stripped) when the cache exists, matches *num_months*, and is no older than
    :data:`NETWORTH_CACHE_TTL_SECONDS`.

    Returns an empty DataFrame (with the canonical :data:`NETWORTH_COLUMNS`
    schema) when the cache is absent, stale, or belongs to a different period.

    Args:
        num_months:  Requested number of months of history.

    Returns:
        pd.DataFrame: Cached net worth history, or empty DataFrame.
    """
    try:
        if not os.path.exists(NETWORTH_CACHE_FILE):
            return pd.DataFrame(columns=pd.Index(NETWORTH_COLUMNS))

        cached = pd.read_parquet(NETWORTH_CACHE_FILE)

        # Validate num_months key
        cached_nm = int(cached["_cache_num_months"].iloc[0]) if "_cache_num_months" in cached.columns else -1
        if cached_nm != num_months:
            return pd.DataFrame(columns=pd.Index(NETWORTH_COLUMNS))

        # Validate TTL
        cached_ts_str = cached["_cache_ts"].iloc[0] if "_cache_ts" in cached.columns else None
        if cached_ts_str:
            cached_ts = datetime.fromisoformat(str(cached_ts_str))
            age_seconds = (datetime.utcnow() - cached_ts).total_seconds()
            if age_seconds > NETWORTH_CACHE_TTL_SECONDS:
                return pd.DataFrame(columns=pd.Index(NETWORTH_COLUMNS))

        # Strip metadata columns and restore DatetimeIndex
        data_cols = [c for c in cached.columns if not c.startswith("_cache_")]
        result = pd.DataFrame(cached[data_cols])
        if "date" in result.columns:
            result["date"] = pd.to_datetime(result["date"])
            result = result.set_index("date")
            result.index.name = "date"
        return result

    except Exception as exc:
        print(f"[networth cache] load failed: {exc}")
        return pd.DataFrame(columns=pd.Index(NETWORTH_COLUMNS))


def _rebuild_networth_and_cache(
    num_months: int,
    done_event: "_threading.Event",
    build_fn: Callable[..., pd.DataFrame],
) -> None:
    """Background worker: call *build_fn* to rebuild net worth history, then persist to disk.

    Designed to be run in a :class:`threading.Thread`.  Sets *done_event* when
    finished (whether successful or not) so callers can detect completion.

    Args:
        num_months:   Number of months of history to build.
        done_event:   :class:`threading.Event` to set on completion.
        build_fn:     Callable that accepts ``num_months`` and returns the net
                      worth DataFrame (i.e. ``build_historical_networth``).
                      Passed as a parameter to avoid a circular import.
    """
    try:
        nw_df: pd.DataFrame = build_fn(num_months=num_months)
        if not nw_df.empty:
            save_networth_cache(nw_df, num_months)
    except Exception as exc:
        print(f"[networth cache] background rebuild failed: {exc}")
    finally:
        done_event.set()


def render_networth(
    num_months: int,
    done_event: "_threading.Event",
    build_fn: Callable[..., pd.DataFrame],
) -> pd.DataFrame:
    """Return the best available net worth history DataFrame.

    **Startup / fast-path behaviour**
    On first call (or after the cache has expired) this function immediately
    returns the last-known-good data from the on-disk Parquet cache so the
    Dashboard renders without delay.  Simultaneously it launches (or re-uses)
    a background thread that calls *build_fn* with live yfinance prices and
    writes the result back to disk.

    **Cache-hit behaviour**
    When the cache is fresh (< :data:`NETWORTH_CACHE_TTL_SECONDS` old) and
    matches *num_months*, the cached DataFrame is returned directly and *no*
    background thread is started.

    **Background rebuild**
    The background thread sets *done_event* when it finishes.  Callers that
    want to trigger a Streamlit rerun once live data is ready should check
    ``done_event.is_set()`` and call ``st.rerun()`` accordingly.

    Args:
        num_months:   Number of months of history to fetch.
        done_event:   A :class:`threading.Event` stored in ``st.session_state``
                      so it survives Streamlit reruns.
        build_fn:     Callable that accepts ``num_months`` and returns the net
                      worth DataFrame (i.e. ``build_historical_networth``).

    Returns:
        pd.DataFrame: Net worth history (may be from cache or live build).
    """
    cached = load_networth_cache(num_months)

    if not cached.empty:
        # Cache is fresh — kick off a background refresh only if the previous
        # rebuild has already finished (event is set) so we don't pile up threads.
        if done_event.is_set():
            done_event.clear()
            _t = _threading.Thread(
                target=_rebuild_networth_and_cache,
                args=(num_months, done_event, build_fn),
                daemon=True,
            )
            _t.start()
        return cached

    # Cache is empty / stale — start background rebuild if not already running.
    if not done_event.is_set():
        # Thread already running — return empty frame; caller shows spinner
        return pd.DataFrame(columns=pd.Index(NETWORTH_COLUMNS))

    # Launch a fresh background rebuild
    done_event.clear()
    _t = _threading.Thread(
        target=_rebuild_networth_and_cache,
        args=(num_months, done_event, build_fn),
        daemon=True,
    )
    _t.start()
    return pd.DataFrame(columns=pd.Index(NETWORTH_COLUMNS))
