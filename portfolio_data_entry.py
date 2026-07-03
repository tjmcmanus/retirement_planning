"""
Portfolio Data Entry Module
Handles manual entry, validation, and saving of portfolio data to portfolio.db
(portfolio_data_truth.csv is kept as a human-readable backup, written automatically
after every DB write by portfolio_db._write_csv_backup).
"""

import pandas as pd
import yfinance as yf
#import streamlit as st
from datetime import datetime
from typing import Tuple, Optional, cast
import logging
import os
import shutil
import glob
import threading as _threading

from portfolio_db import db_upsert, db_overwrite_month, db_load_all, DB_PATH

# Configure logging
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants
PORTFOLIO_TRUTH_FILE = 'portfolio_data_truth.csv'
VALID_ACCOUNT_TYPES = ['Checking','Savings', 'Brokerage', 'Traditional', 'Roth']

def get_valid_account_owners():
    """
    Get valid account owners from Personal Info configuration.
    Returns list of valid owner names: ['Joint', 'Person1Name', 'Person2Name']
    Falls back to ['Joint', 'Primary', 'Spouse'] if config not available.
    """
    try:
        from config import get_config_manager
        config_mgr = get_config_manager()
        
        person1_name = config_mgr.get("personal_info", "person1_name", "")
        person2_name = config_mgr.get("personal_info", "person2_name", "")
        is_single = config_mgr.get("personal_info", "is_single_person", False)
        
        owners = ['Joint']
        if person1_name and person1_name.strip():
            owners.append(person1_name.strip())
        else:
            owners.append('Primary')
        
        if not is_single:
            if person2_name and person2_name.strip():
                owners.append(person2_name.strip())
            else:
                owners.append('Spouse')
        
        return owners
    except Exception:
        # Fallback to defaults if config not available
        return ['Joint', 'Primary', 'Spouse']

# Keep for backward compatibility, but use get_valid_account_owners() for validation
VALID_ACCOUNT_OWNERS = ['Joint', 'Primary', 'Spouse']

# Full sector list used in SelectboxColumn dropdowns.
# Sections:
#   MF:Cash / options  — special asset types
#   MF:*               — mutual fund / ETF categories (from yfinance & fund_type_inference)
#   GICS sectors       — standard equity sectors from yfinance info['sector']
VALID_SECTORS = [
    # ── Special types ────────────────────────────────────────────────────────
    'MF:Cash',
    'Options:Call',
    'Options:Put',
    'MF:OTHER',
    # ── Mutual fund / ETF broad categories ──────────────────────────────────
    'MF:US',
    'MF:Bond',
    'MF:Bonds',
    'MF:Global',
    'MF:Balanced',
    'MF:Commodity',
    'MF:Asia',
    'MF:Europe',
    'MF:Latin America',
    # ── Mutual fund style-box categories (from yfinance info['category']) ───
    'MF:Large Blend',
    'MF:Large Growth',
    'MF:Large Value',
    'MF:Large-Cap',
    'MF:Mid Blend',
    'MF:Mid Growth',
    'MF:Mid Value',
    'MF:Mid-Cap',
    'MF:Small Blend',
    'MF:Small Growth',
    'MF:Small Value',
    'MF:Small-Cap',
    'MF:Total-Stock-Market',
    'MF:Reit',
    'MF:Unknown',
    # ── GICS equity sectors (from yfinance info['sector']) ──────────────────
    'Technology',
    'Healthcare',
    'Financial Services',
    'Consumer Cyclical',
    'Consumer Defensive',
    'Communication Services',
    'Industrials',
    'Energy',
    'Basic Materials',
    'Real Estate',
    'Utilities',
    'Automotive',
]

def is_option_symbol(symbol: str) -> Tuple[bool, str, str]:
    """
    Detect if a symbol is an options contract and parse its components.
    
    Options symbols follow OCC format: TICKER[spaces]YYMMDD[C/P]STRIKE
    Example: SOFI  260402C00020000 = SOFI Call expiring 2026-04-02 at strike $20.00
    
    Args:
        symbol: Ticker symbol to check
        
    Returns:
        Tuple of (is_option, underlying_ticker, option_type)
        - is_option: True if this is an options contract
        - underlying_ticker: The underlying stock symbol (e.g., 'SOFI')
        - option_type: 'Call' or 'Put' or empty string
    """
    if not symbol or len(symbol) < 15:
        return False, '', ''
    
    # Options symbols typically have spaces and end with C or P followed by strike price
    # Format: TICKER[spaces]YYMMDDCSTRIKE or TICKER[spaces]YYMMDDPSTRIKE
    # The 'C' or 'P' appears after the 6-digit date
    
    # Look for the pattern: 6 digits followed by C or P
    import re
    # Match: any chars, then 6 digits, then C or P, then 8 digits (strike price)
    pattern = r'^([A-Z]+)\s+(\d{6})([CP])(\d{8})$'
    match = re.match(pattern, symbol.strip())
    
    if match:
        underlying = match.group(1)
        option_type = 'Call' if match.group(3) == 'C' else 'Put'
        return True, underlying, option_type
    
    return False, '', ''

def validate_ticker_symbol(symbol: str) -> Tuple[bool, str, str, str]:
    """
    Validate a ticker symbol by looking it up in Yahoo Finance.
    For mutual funds (5-letter tickers), uses 'category' field as sector.
    For options contracts, parses OCC format and validates underlying.
    
    Args:
        symbol: Ticker symbol to validate (e.g., 'AAPL', 'GOOGL', 'SOFI  260402C00020000')
    
    Returns:
        Tuple of (is_valid, name, sector, error_message)
        - is_valid: True if symbol exists and can be validated
        - name: Company/security name from Yahoo Finance
        - sector: Sector from Yahoo Finance (or category for mutual funds, or Options:Call/Put)
        - error_message: Error description if validation fails
    """
    # Special handling for cash
    if symbol.upper() in ['MF:CASH', 'CASH']:
        logger.info(f"Validating cash symbol: {symbol}")
        return True, 'Money Market', 'MF:Cash', ''
    
    # Check if this is an options contract
    is_option, underlying, option_type = is_option_symbol(symbol)
    if is_option:
        logger.info(f"Detected options contract: {symbol} -> {underlying} {option_type}")
        # Validate the underlying ticker
        try:
            ticker = yf.Ticker(underlying)
            info = ticker.info
            if not info or 'symbol' not in info:
                return False, '', '', f"Underlying symbol '{underlying}' not found for option"
            
            underlying_name = info.get('shortName', info.get('longName', underlying))
            option_name = f"{underlying_name} {option_type} Option"
            option_sector = f"Options:{option_type}"
            logger.info(f"Validated option: {option_name} -> {option_sector}")
            return True, option_name, option_sector, ''
        except Exception as e:
            logger.error(f"Error validating option underlying {underlying}: {e}")
            return False, '', '', f"Error validating option underlying: {str(e)}"
    
    try:
        logger.info(f"Validating ticker symbol: {symbol}")
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Check if we got valid data
        if not info or 'symbol' not in info:
            logger.warning(f"Symbol '{symbol}' not found in Yahoo Finance")
            return False, '', '', f"Symbol '{symbol}' not found in Yahoo Finance"
        
        # Extract name
        name = info.get('shortName', info.get('longName', symbol))
        logger.info(f"Found ticker {symbol}: {name}")
        
        # Determine sector based on ticker type
        sector = ''
        
        # For mutual funds (5-letter alphabetic tickers), use 'category' field
        # Note: yfinance uses 'category' not 'categoryName'
        if len(symbol) == 5 and symbol.isalpha():
            category = info.get('category', '')
            if category:
                sector = category
                logger.info(f"Mutual fund {symbol} - using category: {sector}")
            else:
                logger.info(f"Mutual fund {symbol} - no category found, trying fallbacks")
        
        # For stocks/ETFs or if category not found, use sector
        if not sector:
            sector = info.get('sector', '')
            if sector:
                logger.info(f"Stock/ETF {symbol} - using sector: {sector}")
        
        # Fallback to category if not already used
        if not sector:
            sector = info.get('category', '')
            if sector:
                logger.info(f"{symbol} - using category fallback: {sector}")
        
        # Last resort: quoteType
        if not sector:
            sector = info.get('quoteType', '')
            if sector:
                logger.info(f"{symbol} - using quoteType fallback: {sector}")
        
        if not sector:
            logger.warning(f"{symbol} - no sector/category information found")
        
        return True, name, sector, ''
        
    except Exception as e:
        logger.error(f"Error validating symbol {symbol}: {e}")
        return False, '', '', f"Error validating symbol: {str(e)}"


def validate_portfolio_entry(row: pd.Series) -> Tuple[bool, str]:
    """
    Validate a single portfolio entry row.
    
    Args:
        row: pandas Series containing portfolio entry data
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    errors = []
    
    # Check required fields
    required_fields = ['month', 'year', 'account_name', 'account_type', 'symbol', 'qty', 'purchase_price']
    for field in required_fields:
        if field not in row or bool(pd.isna(row[field])) or str(row[field]).strip() == '':
            errors.append(f"Missing required field: {field}")
    
    if errors:
        return False, '; '.join(errors)
    
    # Validate month (1-12)
    try:
        month = int(row['month'])
        if month < 1 or month > 12:
            errors.append(f"Month must be between 1 and 12, got {month}")
    except (ValueError, TypeError):
        errors.append(f"Invalid month value: {row['month']}")
    
    # Validate year (reasonable range)
    try:
        year = int(row['year'])
        if year < 2000 or year > 2100:
            errors.append(f"Year must be between 2000 and 2100, got {year}")
    except (ValueError, TypeError):
        errors.append(f"Invalid year value: {row['year']}")
    
    # Validate account_type
    if row['account_type'] not in VALID_ACCOUNT_TYPES:
        errors.append(f"Invalid account_type: {row['account_type']}. Must be one of {VALID_ACCOUNT_TYPES}")
    
    # Validate owner (if provided)
    owner_value = row.get('owner')
    if owner_value is not None and not pd.isna(owner_value) and str(owner_value).strip() != '':
        valid_owners = get_valid_account_owners()
        if owner_value not in valid_owners:
            errors.append(f"Invalid owner: {owner_value}. Must be one of {valid_owners}")
    
    # Validate qty (must be non-zero number, can be negative for options)
    try:
        qty = float(row['qty'])
        if qty == 0:
            errors.append(f"Quantity cannot be zero")
        
        # Check if this is an options contract
        symbol = str(row.get('symbol', '')).strip()
        is_option, _, _ = is_option_symbol(symbol)
        
        # For non-options, quantity must be positive
        if not is_option and qty < 0:
            errors.append(f"Quantity must be positive for non-option securities, got {qty}")
        
        # For options, negative quantity is allowed (covered calls, cash-secured puts)
        # Positive = long position, Negative = short position
        
    except (ValueError, TypeError):
        errors.append(f"Invalid quantity value: {row['qty']}")
    
    # Validate purchase_price (must be positive number)
    try:
        price = float(row['purchase_price'])
        if price <= 0:
            errors.append(f"Purchase price must be positive, got {price}")
    except (ValueError, TypeError):
        errors.append(f"Invalid purchase_price value: {row['purchase_price']}")
    
    if errors:
        return False, '; '.join(errors)
    
    return True, ''


def validate_portfolio_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validate entire portfolio dataframe and separate valid/invalid rows.
    
    Args:
        df: DataFrame containing portfolio entries
    
    Returns:
        Tuple of (valid_df, invalid_df_with_errors)
        - valid_df: DataFrame with valid entries
        - invalid_df_with_errors: DataFrame with invalid entries and error column
    """
    valid_rows = []
    invalid_rows = []
    
    for idx, row in df.iterrows():
        is_valid, error_msg = validate_portfolio_entry(row)
        
        if is_valid:
            valid_rows.append(row)
        else:
            row_with_error = row.copy()
            row_with_error['validation_error'] = error_msg
            invalid_rows.append(row_with_error)
    
    valid_df = pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame()
    invalid_df = pd.DataFrame(invalid_rows) if invalid_rows else pd.DataFrame()
    
    return valid_df, invalid_df


def save_portfolio_data(new_data: pd.DataFrame, append: bool = True) -> Tuple[bool, str]:
    """
    Save portfolio data to portfolio.db (and auto-backup to portfolio_data_truth.csv).

    append=True  → INSERT OR REPLACE (upsert) individual rows via db_upsert().
    append=False → Delete + replace ALL rows for every (month, year) present in
                   new_data via db_overwrite_month(), then upsert the rest.

    Args:
        new_data: DataFrame with new portfolio entries.
        append:   If True, merge/upsert; if False, overwrite by month.

    Returns:
        Tuple of (success, message).
    """
    try:
        required_columns = [
            'month', 'year', 'account_name', 'account_type', 'owner',
            'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date',
        ]

        missing_cols = [col for col in required_columns if col not in new_data.columns]
        if missing_cols:
            return False, f"Missing required columns: {missing_cols}"

        new_data = cast(pd.DataFrame, new_data[required_columns].copy())

        if append:
            n = db_upsert(new_data)
            _trigger_portfolio_cache_rebuild(new_data)
            return True, f"Saved {n} entries to portfolio.db"
        else:
            # Overwrite each (month, year) present in new_data
            total = 0
            for (month, year), grp in new_data.groupby(['month', 'year']):
                total += db_overwrite_month(int(month), int(year), grp)
            _trigger_portfolio_cache_rebuild(new_data)
            return True, f"Overwrote {total} entries in portfolio.db"

    except Exception as e:
        logger.error(f"Error saving portfolio data: {e}")
        return False, f"Error saving data: {str(e)}"


def _trigger_portfolio_cache_rebuild(saved_data: pd.DataFrame) -> None:
    """Kick off a background thread to rebuild and persist the portfolio display cache.

    Called immediately after a successful :func:`save_portfolio_data` so that
    the next app load can serve the freshly-built portfolio from disk without
    waiting for live yfinance calls.

    The rebuild runs in a daemon thread so it never blocks the caller.  Any
    errors are logged but not re-raised.

    Args:
        saved_data: The DataFrame that was just persisted to
                    ``portfolio_data_truth.csv``.  Used to determine the
                    month/year key for the cache entry.
    """
    try:
        # Determine the month/year from the saved data (use the most recent entry)
        month = int(saved_data["month"].iloc[-1])
        year  = int(saved_data["year"].iloc[-1])

        def _rebuild() -> None:
            try:
                # Import here to avoid circular imports at module load time
                from portfolio import build_portfolio_display, save_portfolio_cache
                portdf = build_portfolio_display(month=month, year=year)
                if not portdf.empty:
                    save_portfolio_cache(portdf, month, year)
                    logger.info(
                        f"[portfolio cache] rebuilt and saved for {month}/{year}"
                    )
            except Exception as exc:
                logger.warning(f"[portfolio cache] background rebuild failed: {exc}")

        _t = _threading.Thread(target=_rebuild, daemon=True)
        _t.start()
    except Exception as exc:
        logger.warning(f"[portfolio cache] could not start rebuild thread: {exc}")

    # Also invalidate the networth cache so the Dashboard picks up fresh data
    # on the next load.  We delete the file rather than rebuilding here because
    # the networth build requires build_historical_networth() which lives in
    # planning_app.py (would be a circular import).  Deleting forces a fresh
    # rebuild on the next app startup.
    try:
        from load_data import NETWORTH_CACHE_FILE
        if os.path.exists(NETWORTH_CACHE_FILE):
            os.remove(NETWORTH_CACHE_FILE)
            logger.info("[networth cache] invalidated after portfolio data save")
    except Exception as exc:
        logger.warning(f"[networth cache] could not invalidate cache: {exc}")


def create_empty_entry_template(month: Optional[int] = None, year: Optional[int] = None) -> pd.DataFrame:
    """
    Create an empty template DataFrame for manual entry.
    
    Args:
        month: Default month value (uses current month if None)
        year: Default year value (uses current year if None)
    
    Returns:
        DataFrame with one empty row and proper column structure
    """
    if month is None or year is None:
        now = datetime.now()
        month = month or now.month
        year = year or now.year
    
    template = pd.DataFrame({
        'month': [month],
        'year': [year],
        'account_name': [''],
        'account_type': ['Brokerage'],
        'owner': ['Joint'],
        'symbol': [''],
        'name': [''],
        'sector': [''],
        'qty': [0.0],
        'purchase_price': [0.0],
        'purchase_date': [''],
        'end_of_month_price': [None]
    })
    
    return template


def load_previous_month_data(month: int, year: int) -> pd.DataFrame:
    """
    Load portfolio data from the previous month to use as a template.
    
    Args:
        month: Current month (1-12)
        year: Current year
    
    Returns:
        DataFrame with previous month's data, or empty template if no data exists
    """
    # Calculate previous month
    prev_month = month - 1
    prev_year = year
    
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    
    try:
        # Try to load previous month's data from the DB
        from portfolio_db import db_get_by_month
        prev_data = db_get_by_month(prev_month, prev_year).copy()
        
        if not prev_data.empty:
            # Update month and year to current
            prev_data['month'] = month
            prev_data['year'] = year
            
            logger.info(f"Loaded {len(prev_data)} entries from {prev_month}/{prev_year}")
            return cast(pd.DataFrame, prev_data)
        else:
            logger.info(f"No data found for {prev_month}/{prev_year}, creating empty template")
            return create_empty_entry_template(month, year)
            
    except FileNotFoundError:
        logger.info(f"Portfolio file not found, creating empty template")
        return create_empty_entry_template(month, year)
    except Exception as e:
        logger.error(f"Error loading previous month data: {e}")
        return create_empty_entry_template(month, year)


def backup_portfolio_data() -> Tuple[bool, str]:
    """
    Create a timestamped backup of portfolio.db (exported as CSV).

    Returns:
        Tuple of (success, message)
    """
    try:
        if not DB_PATH.exists():
            return False, f"portfolio.db does not exist — nothing to backup"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"portfolio_data_truth_{timestamp}.csv"

        df = db_load_all()
        df.to_csv(backup_filename, index=False)

        logger.info(f"Created backup: {backup_filename}")
        return True, f"Backup created: {backup_filename} ({len(df)} rows)"

    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return False, f"Error creating backup: {str(e)}"


def create_blank_portfolio_file() -> Tuple[bool, str]:
    """
    Clear all holdings from portfolio.db and write an empty CSV backup.

    Returns:
        Tuple of (success, message)
    """
    try:
        import sqlite3
        conn = __import__('portfolio_db').get_db_connection()
        conn.execute("DELETE FROM holdings")
        conn.commit()
        conn.close()
        # Write empty CSV backup to preserve the file for tools that expect it
        blank_df = pd.DataFrame(columns=[
            'month', 'year', 'account_name', 'account_type', 'owner',
            'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date',
        ])
        blank_df.to_csv(PORTFOLIO_TRUTH_FILE, index=False)
        logger.info("Cleared portfolio.db and wrote empty CSV backup")
        return True, "Cleared portfolio.db (all holdings removed)"

    except Exception as e:
        logger.error(f"Error clearing portfolio: {e}")
        return False, f"Error clearing portfolio: {str(e)}"


def start_from_scratch() -> Tuple[bool, str]:
    """
    Backup the current portfolio file and create a blank one.
    
    Returns:
        Tuple of (success, message)
    """
    # First, backup the existing file
    backup_success, backup_msg = backup_portfolio_data()
    
    if not backup_success:
        return False, backup_msg
    
    # Then create a blank file
    blank_success, blank_msg = create_blank_portfolio_file()
    
    if not blank_success:
        return False, f"{backup_msg}, but failed to create blank file: {blank_msg}"
    
    return True, f"{backup_msg}. {blank_msg}"


def get_latest_backup() -> Optional[str]:
    """
    Find the most recent backup file.
    
    Returns:
        Filename of the latest backup, or None if no backups exist
    """
    try:
        # Find all backup files
        backup_files = glob.glob("portfolio_data_truth_*.csv")
        
        if not backup_files:
            return None
        
        # Sort by modification time (most recent first)
        backup_files.sort(key=os.path.getmtime, reverse=True)
        
        return backup_files[0]
        
    except Exception as e:
        logger.error(f"Error finding latest backup: {e}")
        return None


def revert_to_last_backup() -> Tuple[bool, str]:
    """
    Restore portfolio.db from the most recent CSV backup file.

    Returns:
        Tuple of (success, message)
    """
    try:
        latest_backup = get_latest_backup()

        if not latest_backup:
            return False, "No backup files found to revert to"

        # Safety-snapshot current DB state before overwriting
        backup_before = backup_portfolio_data()
        logger.info(f"Safety snapshot before revert: {backup_before[1]}")

        # Re-import the backup CSV into the DB (overwrite all months present in CSV)
        backup_df = pd.read_csv(latest_backup)
        if backup_df.empty:
            return False, f"Backup file {latest_backup} is empty"

        total = 0
        for (month, year), grp in backup_df.groupby(['month', 'year']):
            total += db_overwrite_month(int(month), int(year), grp)

        logger.info(f"Reverted to backup {latest_backup}: {total} rows restored")
        return True, f"Successfully reverted to backup: {latest_backup} ({total} rows restored)"

    except Exception as e:
        logger.error(f"Error reverting to backup: {e}")
        return False, f"Error reverting to backup: {str(e)}"

# Made with Bob
