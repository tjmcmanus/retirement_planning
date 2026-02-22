"""
Portfolio Data Entry Module
Handles manual entry, validation, and saving of portfolio data to portfolio_data_truth.csv
"""

import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime
from typing import Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PORTFOLIO_TRUTH_FILE = 'portfolio_data_truth.csv'
VALID_ACCOUNT_TYPES = ['Cash', 'Brokerage', 'Traditional', 'Roth']
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
    required_fields = ['month', 'year', 'account_name', 'account_type', 'symbol', 'qty', 'purchase_price']
    for field in required_fields:
        if field not in row or pd.isna(row[field]) or str(row[field]).strip() == '':
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
        new_data = new_data[required_columns].copy()
        
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
                combined_data = pd.concat([existing_data_filtered, new_data], ignore_index=True)
                
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
                
                return True, f"Successfully {' and '.join(message_parts)} entries in {PORTFOLIO_TRUTH_FILE}"
                
            except FileNotFoundError:
                # File doesn't exist, create new one
                new_data.to_csv(PORTFOLIO_TRUTH_FILE, index=False)
                return True, f"Created new {PORTFOLIO_TRUTH_FILE} with {len(new_data)} entries"
        else:
            # Overwrite mode
            new_data.to_csv(PORTFOLIO_TRUTH_FILE, index=False)
            return True, f"Overwrote {PORTFOLIO_TRUTH_FILE} with {len(new_data)} entries"
            
    except Exception as e:
        logger.error(f"Error saving portfolio data: {e}")
        return False, f"Error saving data: {str(e)}"


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
            return prev_data
        else:
            logger.info(f"No data found for {prev_month}/{prev_year}, creating empty template")
            return create_empty_entry_template(month, year)
            
    except FileNotFoundError:
        logger.info(f"Portfolio file not found, creating empty template")
        return create_empty_entry_template(month, year)
    except Exception as e:
        logger.error(f"Error loading previous month data: {e}")
        return create_empty_entry_template(month, year)

# Made with Bob
