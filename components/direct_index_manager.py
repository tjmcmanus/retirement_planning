"""
Direct Index Manager
====================
Manage direct index positions and integrate with existing portfolio system.

This module provides functionality to:
- Import positions from various sources (CSV, Schwab API, manual entry)
- Export to standard portfolio format
- Sync with existing portfolio data
- Handle bulk updates
- Maintain data consistency

Author: Bob
Date: April 17, 2026
Version: 1.0
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import uuid

import pandas as pd
import numpy as np

from components.cost_basis_tracker import (
    TaxLot,
    add_tax_lot,
    get_tax_lots
)
from components.rsp_holdings_fetcher import (
    load_constituents,
    get_constituent
)

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

DB_PATH = Path("data/rsp_holdings.db")
PORTFOLIO_CSV_PATH = Path("data/direct_index_positions.csv")


# ==============================================================================
# IMPORT FUNCTIONS
# ==============================================================================

def import_from_csv(
    csv_path: str,
    account_name: str,
    account_type: str = "Brokerage",
    execution_date: Optional[date] = None
) -> Tuple[int, List[str]]:
    """
    Import direct index positions from CSV file.
    
    Expected CSV format:
    symbol,shares,price,date (optional)
    
    Args:
        csv_path: Path to CSV file
        account_name: Account name
        account_type: Account type
        execution_date: Date positions were purchased (default: today)
    
    Returns:
        Tuple of (number_imported, list_of_errors)
    """
    logger.info(f"Importing positions from {csv_path}")
    
    if execution_date is None:
        execution_date = date.today()
    
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.error(f"Error reading CSV: {e}")
        return 0, [f"Error reading CSV: {e}"]
    
    # Validate required columns
    required_cols = ['symbol', 'shares', 'price']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        error = f"Missing required columns: {missing_cols}"
        logger.error(error)
        return 0, [error]
    
    # Optional date column - convert to date objects
    if 'date' in df.columns:
        df['purchase_date'] = pd.to_datetime(df['date']).apply(lambda x: x.date() if pd.notna(x) else execution_date)
    else:
        df['purchase_date'] = execution_date
    
    imported = 0
    errors = []
    
    for idx, row in df.iterrows():
        try:
            symbol = str(row['symbol']).strip().upper()
            shares = float(row['shares'])
            price = float(row['price'])
            purchase_date_val = row['purchase_date']
            if isinstance(purchase_date_val, date):
                purchase_date = purchase_date_val
            else:
                purchase_date = execution_date
            
            # Validate symbol exists in RSP
            constituent = get_constituent(symbol)
            if not constituent:
                errors.append(f"Row {idx}: {symbol} not found in RSP constituents")
                continue
            
            # Create tax lot
            lot = TaxLot(
                lot_id=str(uuid.uuid4()),
                symbol=symbol,
                account_name=account_name,
                account_type=account_type,
                shares=shares,
                purchase_price=price,
                purchase_date=purchase_date,
                cost_basis=shares * price,
                notes=f"Imported from {Path(csv_path).name}"
            )
            
            add_tax_lot(lot)
            imported += 1
            
        except Exception as e:
            errors.append(f"Row {idx}: {e}")
            logger.warning(f"Error importing row {idx}: {e}")
    
    logger.info(f"Imported {imported} positions, {len(errors)} errors")
    
    return imported, errors


def import_from_schwab(
    account_id: str,
    account_name: str,
    schwab_connector
) -> Tuple[int, List[str]]:
    """
    Import positions from Schwab API.
    
    Args:
        account_id: Schwab account ID
        account_name: Account name for tracking
        schwab_connector: Schwab API connector instance
    
    Returns:
        Tuple of (number_imported, list_of_errors)
    """
    logger.info(f"Importing positions from Schwab account {account_id}")
    
    try:
        # Get positions from Schwab
        positions = schwab_connector.get_account_positions(account_id)
        
        if not positions:
            return 0, ["No positions found in Schwab account"]
        
        imported = 0
        errors = []
        
        for position in positions:
            symbol = ''
            try:
                symbol = position.get('symbol', '').strip().upper()
                shares = float(position.get('quantity', 0))
                
                # Skip if no shares
                if shares <= 0:
                    continue
                
                # Check if this is an RSP constituent
                constituent = get_constituent(symbol)
                if not constituent:
                    # Not a direct index position, skip
                    continue
                
                # Get cost basis info
                avg_price = float(position.get('averagePrice', 0))
                
                # Try to get purchase date (may not be available)
                purchase_date_str = position.get('purchaseDate')
                if purchase_date_str:
                    purchase_date = datetime.fromisoformat(purchase_date_str).date()
                else:
                    purchase_date = date.today()
                
                # Create tax lot
                lot = TaxLot(
                    lot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    account_name=account_name,
                    account_type="Brokerage",
                    shares=shares,
                    purchase_price=avg_price,
                    purchase_date=purchase_date,
                    cost_basis=shares * avg_price,
                    notes=f"Imported from Schwab account {account_id}"
                )
                
                add_tax_lot(lot)
                imported += 1
                
            except Exception as e:
                errors.append(f"Error importing {symbol}: {e}")
                logger.warning(f"Error importing {symbol}: {e}")
        
        logger.info(f"Imported {imported} positions from Schwab")
        
        return imported, errors
        
    except Exception as e:
        error = f"Error connecting to Schwab: {e}"
        logger.error(error)
        return 0, [error]


# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

def export_to_portfolio_csv(
    account_name: Optional[str] = None,
    output_path: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None
) -> str:
    """
    Export direct index positions to standard portfolio CSV format.
    
    Output format matches existing portfolio structure:
    month,year,account_name,account_type,owner,symbol,name,sector,qty,
    purchase_price,end_of_month_price,purchase_date
    
    Args:
        account_name: Filter by account (optional)
        output_path: Output file path (default: data/direct_index_positions.csv)
        month: Month for end_of_month_price (default: current)
        year: Year for end_of_month_price (default: current)
    
    Returns:
        Path to exported file
    """
    if output_path is None:
        output_path = str(PORTFOLIO_CSV_PATH)
    
    if month is None:
        month = datetime.now().month
    
    if year is None:
        year = datetime.now().year
    
    logger.info(f"Exporting direct index positions to {output_path}")
    
    # Get all tax lots
    lots = get_tax_lots(account_name=account_name)
    
    if not lots:
        logger.warning("No positions to export")
        return output_path
    
    # Get current prices
    constituents = load_constituents()
    price_map = {c.symbol: c.current_price for c in constituents}
    
    # Build export data
    data = []
    for lot in lots:
        constituent = get_constituent(lot.symbol)
        
        data.append({
            'month': month,
            'year': year,
            'account_name': lot.account_name,
            'account_type': lot.account_type,
            'owner': 'Joint',  # Default, could be configurable
            'symbol': lot.symbol,
            'name': constituent.name if constituent else lot.symbol,
            'sector': constituent.sector if constituent else 'Unknown',
            'qty': lot.shares,
            'purchase_price': lot.purchase_price,
            'end_of_month_price': price_map.get(lot.symbol, lot.purchase_price),
            'purchase_date': lot.purchase_date.isoformat()
        })
    
    # Create DataFrame and export
    df = pd.DataFrame(data)
    
    # Ensure directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_path, index=False)
    
    logger.info(f"Exported {len(data)} positions to {output_path}")
    
    return output_path


def export_to_dataframe(
    account_name: Optional[str] = None
) -> pd.DataFrame:
    """
    Export direct index positions to DataFrame.
    
    Args:
        account_name: Filter by account (optional)
    
    Returns:
        DataFrame with position details
    """
    lots = get_tax_lots(account_name=account_name)
    
    if not lots:
        return pd.DataFrame()
    
    # Get current prices
    constituents = load_constituents()
    price_map = {c.symbol: c.current_price for c in constituents}
    
    data = []
    for lot in lots:
        current_price = price_map.get(lot.symbol, 0)
        current_value = lot.shares * current_price
        unrealized_gl = current_value - lot.cost_basis
        
        data.append({
            'lot_id': lot.lot_id,
            'symbol': lot.symbol,
            'account_name': lot.account_name,
            'account_type': lot.account_type,
            'shares': lot.shares,
            'purchase_price': lot.purchase_price,
            'purchase_date': lot.purchase_date,
            'cost_basis': lot.cost_basis,
            'current_price': current_price,
            'current_value': current_value,
            'unrealized_gl': unrealized_gl,
            'holding_days': lot.holding_period_days(),
            'is_long_term': lot.is_long_term()
        })
    
    return pd.DataFrame(data)


# ==============================================================================
# SYNC FUNCTIONS
# ==============================================================================

def sync_with_portfolio_system(
    portfolio_df: pd.DataFrame,
    account_name: str
) -> pd.DataFrame:
    """
    Merge direct index positions with existing portfolio DataFrame.
    
    Args:
        portfolio_df: Existing portfolio DataFrame
        account_name: Account to sync
    
    Returns:
        Merged DataFrame
    """
    logger.info(f"Syncing direct index positions with portfolio for {account_name}")
    
    # Export direct index positions to DataFrame
    direct_index_df = export_to_dataframe(account_name=account_name)
    
    if direct_index_df.empty:
        logger.info("No direct index positions to sync")
        return portfolio_df
    
    # Convert to portfolio format
    month = datetime.now().month
    year = datetime.now().year
    
    constituents = load_constituents()
    constituent_map = {c.symbol: c for c in constituents}
    
    portfolio_format = []
    for _, row in direct_index_df.iterrows():
        symbol = str(row['symbol'])
        constituent = constituent_map.get(symbol)
        
        purchase_date_val = row['purchase_date']
        if isinstance(purchase_date_val, date):
            purchase_date_str = purchase_date_val.isoformat()
        else:
            purchase_date_str = str(purchase_date_val)
        
        portfolio_format.append({
            'month': month,
            'year': year,
            'account_name': str(row['account_name']),
            'account_type': str(row['account_type']),
            'owner': 'Joint',
            'symbol': symbol,
            'name': constituent.name if constituent else symbol,
            'sector': constituent.sector if constituent else 'Unknown',
            'qty': float(row['shares']),
            'purchase_price': float(row['purchase_price']),
            'end_of_month_price': float(row['current_price']),
            'purchase_date': purchase_date_str
        })
    
    direct_index_portfolio = pd.DataFrame(portfolio_format)
    
    # Remove existing direct index positions from portfolio_df
    # (to avoid duplicates)
    if not portfolio_df.empty:
        direct_index_symbols = list(direct_index_df['symbol'].unique())
        mask = ~((portfolio_df['account_name'] == account_name) &
                 (portfolio_df['symbol'].isin(direct_index_symbols)))
        filtered = portfolio_df[mask]
        if isinstance(filtered, pd.DataFrame):
            portfolio_df = filtered.copy()
    
    # Merge
    merged_df = pd.concat([portfolio_df, direct_index_portfolio], ignore_index=True)
    
    logger.info(f"Merged {len(direct_index_portfolio)} direct index positions")
    
    return merged_df


# ==============================================================================
# POSITION MANAGEMENT
# ==============================================================================

def get_position_summary(
    account_name: Optional[str] = None
) -> Dict:
    """
    Get summary of direct index positions.
    
    Args:
        account_name: Filter by account (optional)
    
    Returns:
        Dictionary with summary statistics
    """
    df = export_to_dataframe(account_name=account_name)
    
    if df.empty:
        return {
            'total_positions': 0,
            'total_value': 0.0,
            'total_cost_basis': 0.0,
            'total_unrealized_gl': 0.0,
            'by_account': {},
            'by_sector': {}
        }
    
    # Get sector info
    constituents = load_constituents()
    sector_map = {c.symbol: c.sector for c in constituents}
    df['sector'] = df['symbol'].apply(lambda x: sector_map.get(x, 'Unknown'))
    
    # Calculate summaries
    summary = {
        'total_positions': len(df),
        'total_value': df['current_value'].sum(),
        'total_cost_basis': df['cost_basis'].sum(),
        'total_unrealized_gl': df['unrealized_gl'].sum(),
        'by_account': {},
        'by_sector': {}
    }
    
    # By account
    if 'account_name' in df.columns:
        for account in df['account_name'].unique():
            account_df = df[df['account_name'] == account]
            summary['by_account'][account] = {
                'positions': len(account_df),
                'value': account_df['current_value'].sum(),
                'cost_basis': account_df['cost_basis'].sum(),
                'unrealized_gl': account_df['unrealized_gl'].sum()
            }
    
    # By sector
    if 'sector' in df.columns:
        for sector in df['sector'].dropna().unique():
            sector_df = df[df['sector'] == sector]
            summary['by_sector'][sector] = {
                'positions': len(sector_df),
                'value': sector_df['current_value'].sum(),
                'cost_basis': sector_df['cost_basis'].sum(),
                'unrealized_gl': sector_df['unrealized_gl'].sum()
            }
    
    return summary


def update_position_prices(
    account_name: Optional[str] = None
) -> int:
    """
    Update current prices for all positions.
    
    This doesn't modify the database, just returns updated data.
    Prices are fetched from RSP holdings cache.
    
    Args:
        account_name: Filter by account (optional)
    
    Returns:
        Number of positions updated
    """
    from components.rsp_holdings_fetcher import update_prices
    
    lots = get_tax_lots(account_name=account_name)
    
    if not lots:
        return 0
    
    # Get unique symbols
    symbols = list(set(lot.symbol for lot in lots))
    
    # Update prices in RSP holdings cache
    updated_prices = update_prices(symbols)
    
    logger.info(f"Updated prices for {len(updated_prices)} symbols")
    
    return len(updated_prices)


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Direct Index Manager")
    print("=" * 60)
    
    # Test getting position summary
    print("\nGetting position summary...")
    summary = get_position_summary()
    
    print(f"\nTotal Positions: {summary['total_positions']}")
    print(f"Total Value: ${summary['total_value']:,.2f}")
    print(f"Total Cost Basis: ${summary['total_cost_basis']:,.2f}")
    print(f"Unrealized G/L: ${summary['total_unrealized_gl']:+,.2f}")
    
    if summary['by_account']:
        print("\nBy Account:")
        for account, stats in summary['by_account'].items():
            print(f"  {account}:")
            print(f"    Positions: {stats['positions']}")
            print(f"    Value: ${stats['value']:,.2f}")
            print(f"    Unrealized G/L: ${stats['unrealized_gl']:+,.2f}")
    
    if summary['by_sector']:
        print("\nBy Sector:")
        for sector, stats in sorted(
            summary['by_sector'].items(),
            key=lambda x: x[1]['value'],
            reverse=True
        )[:5]:
            print(f"  {sector}:")
            print(f"    Positions: {stats['positions']}")
            print(f"    Value: ${stats['value']:,.2f}")
    
    # Test export
    print("\nExporting to CSV...")
    try:
        output_path = export_to_portfolio_csv()
        print(f"  Exported to: {output_path}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

# Made with Bob
