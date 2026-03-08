"""
Portfolio Data Entry Module
Handles manual entry, validation, and saving of portfolio data to portfolio_data_truth.csv
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
VALID_ACCOUNT_TYPES = ['Cash', 'Brokerage', 'Traditional', 'Roth']
VALID_ACCOUNT_OWNERS = ['Joint', 'Primary', 'Spouse']
VALID_SECTORS = [
    'MF:Cash',
    'Stock/ETF',
    'MF:Large-Cap',
    'MF:Mid-Cap',
    'MF:Small-Cap',
    'MF:Reit',
    'MF:Global',
    'MF:Asia',
    'MF:Europe',
    'MF:Latin America',
    'Automotive',
    'Technology',
    'Communication Services',
    'Healthcare',
    'Consumer Defensive',
    'Financial Services',
    'Energy',
    'Industrials',
    'Real Estate',
    'Utilities',
    'Basic Materials',
    'Consumer Cyclical'
]

def validate_ticker_symbol(symbol: str) -> Tuple[bool, str, str, str]:
    """
    Validate a ticker symbol by looking it up in Yahoo Finance.
    
    Args:
        symbol: Ticker symbol to validate (e.g., 'AAPL', 'GOOGL')
    
    Returns:
        Tuple of (is_valid, name, sector, error_message)
        - is_valid: True if symbol exists and can be validated
        - name: Company/security name from Yahoo Finance
        - sector: Sector from Yahoo Finance (or empty string)
        - error_message: Error description if validation fails
    """
    # Special handling for cash
    if symbol.upper() in ['MF:CASH', 'CASH']:
        return True, 'Money Market', 'MF:Cash', ''
    
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Check if we got valid data
        if not info or 'symbol' not in info:
            return False, '', '', f"Symbol '{symbol}' not found in Yahoo Finance"
        
        # Extract name and sector
        name = info.get('shortName', info.get('longName', symbol))
        sector = info.get('sector', '')
        
        # If no sector, try to get it from other fields
        if not sector:
            sector = info.get('category', info.get('quoteType', ''))
        
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
    required_fields = ['month', 'year', 'account_name', 'account_type', 'owner', 'symbol', 'qty', 'purchase_price']
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
    
    # Validate owner
    if row['owner'] not in VALID_ACCOUNT_OWNERS:
        errors.append(f"Invalid owner: {row['owner']}. Must be one of {VALID_ACCOUNT_OWNERS}")
    
    # Validate qty (must be positive number)
    try:
        qty = float(row['qty'])
        if qty <= 0:
            errors.append(f"Quantity must be positive, got {qty}")
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
    Save portfolio data to portfolio_data_truth.csv.
    Updates/overwrites existing entries with matching month, year, account_name, and symbol.
    
    Args:
        new_data: DataFrame with new portfolio entries
        append: If True, merge with existing file (update duplicates); if False, overwrite entire file
    
    Returns:
        Tuple of (success, message)
    """
    try:
        # Ensure required columns are present
        required_columns = ['month', 'year', 'account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price']
        
        # Check for missing columns
        missing_cols = [col for col in required_columns if col not in new_data.columns]
        if missing_cols:
            return False, f"Missing required columns: {missing_cols}"
        
        # Select only required columns in correct order
        new_data = cast(pd.DataFrame, new_data[required_columns].copy())
        
        # Convert numeric columns to appropriate types
        new_data['month'] = new_data['month'].astype(int)
        new_data['year'] = new_data['year'].astype(int)
        new_data['qty'] = new_data['qty'].astype(float)
        new_data['purchase_price'] = new_data['purchase_price'].astype(float)
        
        if append:
            # Load existing data
            try:
                existing_data = pd.read_csv(PORTFOLIO_TRUTH_FILE)
                
                # Define merge columns (unique identifier for each entry)
                merge_cols = ['month', 'year', 'account_name', 'symbol']
                
                # Remove existing entries that match the new data (will be replaced)
                # Create a mask for rows that DON'T match any new entries
                mask = ~existing_data.set_index(merge_cols).index.isin(
                    new_data.set_index(merge_cols).index
                )
                
                # Keep only non-matching existing entries
                existing_data_filtered = existing_data[mask].copy()
                
                # Combine filtered existing data with new data
                combined_data: pd.DataFrame = cast(pd.DataFrame, pd.concat([existing_data_filtered, new_data], ignore_index=True))
                
                # Sort by year, month, account_name, symbol
                combined_data = combined_data.sort_values(['year', 'month', 'account_name', 'symbol'])
                
                # Save to file
                combined_data.to_csv(PORTFOLIO_TRUTH_FILE, index=False)
                
                # Count updates vs new entries
                updated_count = len(new_data) - len(new_data[~new_data.set_index(merge_cols).index.isin(
                    existing_data.set_index(merge_cols).index
                )])
                new_count = len(new_data) - updated_count
                
                message_parts = []
                if updated_count > 0:
                    message_parts.append(f"updated {updated_count} existing")
                if new_count > 0:
                    message_parts.append(f"added {new_count} new")
                
                msg = f"Successfully {' and '.join(message_parts)} entries in {PORTFOLIO_TRUTH_FILE}"
                _trigger_portfolio_cache_rebuild(new_data)
                return True, msg

            except FileNotFoundError:
                # File doesn't exist, create new one
                new_data.to_csv(PORTFOLIO_TRUTH_FILE, index=False)
                _trigger_portfolio_cache_rebuild(new_data)
                return True, f"Created new {PORTFOLIO_TRUTH_FILE} with {len(new_data)} entries"
        else:
            # Overwrite mode
            new_data.to_csv(PORTFOLIO_TRUTH_FILE, index=False)
            _trigger_portfolio_cache_rebuild(new_data)
            return True, f"Overwrote {PORTFOLIO_TRUTH_FILE} with {len(new_data)} entries"

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
        'purchase_price': [0.0]
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
        # Try to load previous month's data
        existing_data = pd.read_csv(PORTFOLIO_TRUTH_FILE)
        
        # Filter for previous month
        prev_data = existing_data[
            (existing_data['month'] == prev_month) &
            (existing_data['year'] == prev_year)
        ].copy()
        
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
    Create a timestamped backup of the current portfolio_data_truth.csv file.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        if not os.path.exists(PORTFOLIO_TRUTH_FILE):
            return False, f"{PORTFOLIO_TRUTH_FILE} does not exist - nothing to backup"
        
        # Create timestamp suffix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"portfolio_data_truth_{timestamp}.csv"
        
        # Copy the file
        shutil.copy2(PORTFOLIO_TRUTH_FILE, backup_filename)
        
        logger.info(f"Created backup: {backup_filename}")
        return True, f"Backup created: {backup_filename}"
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return False, f"Error creating backup: {str(e)}"


def create_blank_portfolio_file() -> Tuple[bool, str]:
    """
    Create a blank portfolio_data_truth.csv file with only column headers.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        # Create DataFrame with just headers
        blank_df = pd.DataFrame(columns=pd.Index([
            'month', 'year', 'account_name', 'account_type',
            'symbol', 'name', 'sector', 'qty', 'purchase_price'
        ]))
        
        # Save to file
        blank_df.to_csv(PORTFOLIO_TRUTH_FILE, index=False)
        
        logger.info(f"Created blank {PORTFOLIO_TRUTH_FILE}")
        return True, f"Created blank {PORTFOLIO_TRUTH_FILE} with column headers only"
        
    except Exception as e:
        logger.error(f"Error creating blank file: {e}")
        return False, f"Error creating blank file: {str(e)}"


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
    Restore the portfolio_data_truth.csv from the most recent backup.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        latest_backup = get_latest_backup()
        
        if not latest_backup:
            return False, "No backup files found to revert to"
        
        # Backup current file before reverting (just in case)
        if os.path.exists(PORTFOLIO_TRUTH_FILE):
            temp_backup = f"portfolio_data_truth_before_revert_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            shutil.copy2(PORTFOLIO_TRUTH_FILE, temp_backup)
            logger.info(f"Created safety backup before revert: {temp_backup}")
        
        # Copy backup to main file
        shutil.copy2(latest_backup, PORTFOLIO_TRUTH_FILE)
        
        logger.info(f"Reverted to backup: {latest_backup}")
        return True, f"Successfully reverted to backup: {latest_backup}"
        
    except Exception as e:
        logger.error(f"Error reverting to backup: {e}")
        return False, f"Error reverting to backup: {str(e)}"

# Made with Bob
