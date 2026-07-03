"""
Cost Basis Tracker
==================
Track lot-level cost basis for direct index positions.

This module provides functionality to:
- Track multiple tax lots per symbol
- Calculate realized gains/losses on sales
- Support FIFO, LIFO, and SpecID methods
- Handle wash sale adjustments
- Generate tax reports (Form 8949 data)

Author: Bob
Date: April 17, 2026
Version: 1.0
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from enum import Enum
import uuid

import pandas as pd

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

DB_PATH = Path("data/rsp_holdings.db")
LONG_TERM_HOLDING_DAYS = 365  # IRS long-term capital gains threshold


# ==============================================================================
# ENUMS
# ==============================================================================

class LotSelectionMethod(Enum):
    """Methods for selecting which lots to sell."""
    FIFO = "FIFO"  # First In, First Out
    LIFO = "LIFO"  # Last In, First Out
    HIFO = "HIFO"  # Highest In, First Out (highest cost basis)
    LOFO = "LOFO"  # Lowest In, First Out (lowest cost basis)
    SPEC_ID = "SPEC_ID"  # Specific Identification


class GainType(Enum):
    """Type of capital gain."""
    SHORT_TERM = "SHORT_TERM"  # Held <= 365 days
    LONG_TERM = "LONG_TERM"    # Held > 365 days


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class TaxLot:
    """
    Represents a single tax lot (purchase) of a security.
    
    Attributes:
        lot_id: Unique identifier for this lot
        symbol: Stock ticker symbol
        account_name: Account holding this lot
        account_type: Account type (Brokerage, Traditional, Roth)
        shares: Number of shares in this lot
        purchase_price: Price per share at purchase
        purchase_date: Date of purchase
        cost_basis: Total cost basis (shares * purchase_price)
        is_replacement: True if this was a wash sale replacement
        replaced_symbol: Symbol this replaced (if wash sale)
        notes: Additional notes
        created_at: Timestamp when lot was created
    """
    lot_id: str
    symbol: str
    account_name: str
    account_type: str
    shares: float
    purchase_price: float
    purchase_date: date
    cost_basis: float
    is_replacement: bool = False
    replaced_symbol: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        
        # Ensure cost_basis is calculated
        if self.cost_basis == 0:
            self.cost_basis = self.shares * self.purchase_price
    
    def holding_period_days(self, as_of_date: Optional[date] = None) -> int:
        """Calculate holding period in days."""
        if as_of_date is None:
            as_of_date = date.today()
        return (as_of_date - self.purchase_date).days
    
    def is_long_term(self, as_of_date: Optional[date] = None) -> bool:
        """Check if this lot qualifies for long-term capital gains."""
        return self.holding_period_days(as_of_date) > LONG_TERM_HOLDING_DAYS
    
    def gain_type(self, as_of_date: Optional[date] = None) -> GainType:
        """Determine gain type (short-term or long-term)."""
        if self.is_long_term(as_of_date):
            return GainType.LONG_TERM
        return GainType.SHORT_TERM


@dataclass
class LotDisposition:
    """
    Represents the sale/disposition of a tax lot.
    
    Attributes:
        lot_id: ID of the lot being sold
        symbol: Stock ticker symbol
        account_name: Account name
        shares_sold: Number of shares sold from this lot
        sale_price: Price per share at sale
        sale_date: Date of sale
        cost_basis: Cost basis of shares sold
        proceeds: Total proceeds from sale
        gain_loss: Realized gain (positive) or loss (negative)
        gain_type: SHORT_TERM or LONG_TERM
        holding_period_days: Days held
        wash_sale_loss_disallowed: Amount of loss disallowed due to wash sale
    """
    lot_id: str
    symbol: str
    account_name: str
    shares_sold: float
    sale_price: float
    sale_date: date
    cost_basis: float
    proceeds: float
    gain_loss: float
    gain_type: GainType
    holding_period_days: int
    wash_sale_loss_disallowed: float = 0.0
    
    def adjusted_gain_loss(self) -> float:
        """Get gain/loss after wash sale adjustment."""
        return self.gain_loss + self.wash_sale_loss_disallowed


# ==============================================================================
# DATABASE FUNCTIONS
# ==============================================================================

def add_tax_lot(lot: TaxLot) -> None:
    """
    Add a new tax lot to the database.
    
    Args:
        lot: TaxLot object to add
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO direct_index_positions 
        (account_name, account_type, symbol, shares, purchase_price, 
         purchase_date, cost_basis, is_replacement, replaced_symbol, 
         lot_id, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lot.account_name,
        lot.account_type,
        lot.symbol,
        lot.shares,
        lot.purchase_price,
        lot.purchase_date.isoformat(),
        lot.cost_basis,
        1 if lot.is_replacement else 0,
        lot.replaced_symbol,
        lot.lot_id,
        lot.notes,
        lot.created_at.isoformat() if lot.created_at else datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Added tax lot: {lot.symbol} - {lot.shares} shares @ ${lot.purchase_price:.2f}")


def get_tax_lots(
    symbol: Optional[str] = None,
    account_name: Optional[str] = None,
    account_type: Optional[str] = None
) -> List[TaxLot]:
    """
    Get tax lots from database.
    
    Args:
        symbol: Filter by symbol (optional)
        account_name: Filter by account name (optional)
        account_type: Filter by account type (optional)
    
    Returns:
        List of TaxLot objects
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT * FROM direct_index_positions WHERE shares > 0"
    params = []
    
    if symbol:
        query += " AND symbol = ?"
        params.append(symbol)
    
    if account_name:
        query += " AND account_name = ?"
        params.append(account_name)
    
    if account_type:
        query += " AND account_type = ?"
        params.append(account_type)
    
    query += " ORDER BY purchase_date"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    lots = []
    for row in rows:
        lot = TaxLot(
            lot_id=row[10] or str(uuid.uuid4()),  # lot_id column
            symbol=row[3],
            account_name=row[1],
            account_type=row[2],
            shares=row[4],
            purchase_price=row[5],
            purchase_date=date.fromisoformat(row[6]),
            cost_basis=row[7],
            is_replacement=bool(row[8]),
            replaced_symbol=row[9],
            notes=row[11],
            created_at=datetime.fromisoformat(row[12]) if row[12] else datetime.now()
        )
        lots.append(lot)
    
    return lots


def update_lot_shares(lot_id: str, new_shares: float) -> None:
    """
    Update the number of shares in a lot (after partial sale).
    
    Args:
        lot_id: Lot ID to update
        new_shares: New share count
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE direct_index_positions 
        SET shares = ?, updated_at = ?
        WHERE lot_id = ?
    """, (new_shares, datetime.now().isoformat(), lot_id))
    
    conn.commit()
    conn.close()


# ==============================================================================
# LOT SELECTION
# ==============================================================================

def select_lots_to_sell(
    symbol: str,
    shares_to_sell: float,
    account_name: str,
    method: LotSelectionMethod = LotSelectionMethod.FIFO,
    specific_lot_ids: Optional[List[str]] = None
) -> List[Tuple[TaxLot, float]]:
    """
    Select which lots to sell based on the specified method.
    
    Args:
        symbol: Stock symbol
        shares_to_sell: Number of shares to sell
        account_name: Account name
        method: Lot selection method
        specific_lot_ids: Specific lot IDs (for SPEC_ID method)
    
    Returns:
        List of (TaxLot, shares_from_lot) tuples
    """
    # Get all lots for this symbol
    lots = get_tax_lots(symbol=symbol, account_name=account_name)
    
    if not lots:
        raise ValueError(f"No lots found for {symbol} in {account_name}")
    
    # Check if we have enough shares
    total_shares = sum(lot.shares for lot in lots)
    if total_shares < shares_to_sell:
        raise ValueError(
            f"Insufficient shares: have {total_shares}, need {shares_to_sell}"
        )
    
    # Sort lots based on method
    if method == LotSelectionMethod.FIFO:
        # First In, First Out - oldest first
        lots.sort(key=lambda x: x.purchase_date)
    
    elif method == LotSelectionMethod.LIFO:
        # Last In, First Out - newest first
        lots.sort(key=lambda x: x.purchase_date, reverse=True)
    
    elif method == LotSelectionMethod.HIFO:
        # Highest In, First Out - highest cost basis first
        lots.sort(key=lambda x: x.purchase_price, reverse=True)
    
    elif method == LotSelectionMethod.LOFO:
        # Lowest In, First Out - lowest cost basis first
        lots.sort(key=lambda x: x.purchase_price)
    
    elif method == LotSelectionMethod.SPEC_ID:
        # Specific Identification - use specified lots
        if not specific_lot_ids:
            raise ValueError("SPEC_ID method requires specific_lot_ids")
        
        # Filter to specified lots
        lot_dict = {lot.lot_id: lot for lot in lots}
        lots = [lot_dict[lot_id] for lot_id in specific_lot_ids if lot_id in lot_dict]
    
    # Select lots until we have enough shares
    selected = []
    remaining = shares_to_sell
    
    for lot in lots:
        if remaining <= 0:
            break
        
        if lot.shares <= remaining:
            # Use entire lot
            selected.append((lot, lot.shares))
            remaining -= lot.shares
        else:
            # Use partial lot
            selected.append((lot, remaining))
            remaining = 0
    
    if remaining > 0:
        raise ValueError(f"Could not select enough shares: {remaining} short")
    
    return selected


# ==============================================================================
# SALE PROCESSING
# ==============================================================================

def sell_shares(
    symbol: str,
    shares: float,
    sale_price: float,
    sale_date: date,
    account_name: str,
    method: LotSelectionMethod = LotSelectionMethod.FIFO,
    specific_lot_ids: Optional[List[str]] = None
) -> List[LotDisposition]:
    """
    Sell shares and calculate realized gains/losses.
    
    Args:
        symbol: Stock symbol
        shares: Number of shares to sell
        sale_price: Sale price per share
        sale_date: Date of sale
        account_name: Account name
        method: Lot selection method
        specific_lot_ids: Specific lot IDs (for SPEC_ID method)
    
    Returns:
        List of LotDisposition objects (one per lot sold)
    """
    logger.info(f"Selling {shares} shares of {symbol} @ ${sale_price:.2f}")
    
    # Select lots to sell
    selected_lots = select_lots_to_sell(
        symbol=symbol,
        shares_to_sell=shares,
        account_name=account_name,
        method=method,
        specific_lot_ids=specific_lot_ids
    )
    
    dispositions = []
    
    for lot, shares_from_lot in selected_lots:
        # Calculate cost basis for shares being sold
        cost_basis_per_share = lot.purchase_price
        cost_basis = shares_from_lot * cost_basis_per_share
        
        # Calculate proceeds
        proceeds = shares_from_lot * sale_price
        
        # Calculate gain/loss
        gain_loss = proceeds - cost_basis
        
        # Determine gain type
        holding_days = lot.holding_period_days(sale_date)
        gain_type = lot.gain_type(sale_date)
        
        # Create disposition
        disposition = LotDisposition(
            lot_id=lot.lot_id,
            symbol=symbol,
            account_name=account_name,
            shares_sold=shares_from_lot,
            sale_price=sale_price,
            sale_date=sale_date,
            cost_basis=cost_basis,
            proceeds=proceeds,
            gain_loss=gain_loss,
            gain_type=gain_type,
            holding_period_days=holding_days
        )
        
        dispositions.append(disposition)
        
        # Update lot in database
        remaining_shares = lot.shares - shares_from_lot
        if remaining_shares > 0.001:  # Keep lot with remaining shares
            update_lot_shares(lot.lot_id, remaining_shares)
        else:  # Lot fully sold
            update_lot_shares(lot.lot_id, 0)
        
        logger.info(
            f"  Sold {shares_from_lot:.4f} shares from lot {lot.lot_id[:8]}... "
            f"(purchased {lot.purchase_date}): "
            f"${gain_loss:+,.2f} {gain_type.value}"
        )
    
    return dispositions


# ==============================================================================
# UNREALIZED GAINS/LOSSES
# ==============================================================================

def get_unrealized_gains_losses(
    symbol: Optional[str] = None,
    account_name: Optional[str] = None,
    current_prices: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Calculate unrealized gains/losses for all lots.
    
    Args:
        symbol: Filter by symbol (optional)
        account_name: Filter by account (optional)
        current_prices: Dict of symbol -> current price (optional)
    
    Returns:
        DataFrame with unrealized gain/loss details
    """
    lots = get_tax_lots(symbol=symbol, account_name=account_name)
    
    if not lots:
        return pd.DataFrame()
    
    # Get current prices if not provided
    if current_prices is None:
        from components.rsp_holdings_fetcher import load_constituents
        constituents = load_constituents()
        current_prices = {c.symbol: c.current_price for c in constituents}
    
    data = []
    for lot in lots:
        current_price = current_prices.get(lot.symbol, 0)
        current_value = lot.shares * current_price
        unrealized_gl = current_value - lot.cost_basis
        unrealized_gl_pct = (unrealized_gl / lot.cost_basis * 100) if lot.cost_basis > 0 else 0
        
        data.append({
            'lot_id': lot.lot_id,
            'symbol': lot.symbol,
            'account_name': lot.account_name,
            'shares': lot.shares,
            'purchase_price': lot.purchase_price,
            'purchase_date': lot.purchase_date,
            'cost_basis': lot.cost_basis,
            'current_price': current_price,
            'current_value': current_value,
            'unrealized_gl': unrealized_gl,
            'unrealized_gl_pct': unrealized_gl_pct,
            'holding_days': lot.holding_period_days(),
            'is_long_term': lot.is_long_term(),
            'gain_type': lot.gain_type().value
        })
    
    df = pd.DataFrame(data)
    return df


# ==============================================================================
# TAX REPORTING
# ==============================================================================

def generate_form_8949_data(
    year: int,
    account_name: Optional[str] = None
) -> pd.DataFrame:
    """
    Generate data for IRS Form 8949 (Sales and Dispositions).
    
    Args:
        year: Tax year
        account_name: Filter by account (optional)
    
    Returns:
        DataFrame with Form 8949 data
    """
    # This would query harvest_history table for completed sales
    # For now, return empty DataFrame as placeholder
    
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT 
            sold_symbol as symbol,
            sold_shares as shares,
            cost_basis,
            sold_price as sale_price,
            harvest_date as sale_date,
            realized_loss as gain_loss,
            holding_period_days
        FROM harvest_history
        WHERE strftime('%Y', harvest_date) = ?
        AND status = 'executed'
    """
    
    params = [str(year)]
    
    if account_name:
        query += " AND account_name = ?"
        params.append(account_name)
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df.empty:
        return df
    
    # Add Form 8949 columns
    df['description'] = df['symbol'] + ' - ' + df['shares'].astype(str) + ' shares'
    df['date_acquired'] = 'VARIOUS'  # Would need to track from lots
    df['proceeds'] = df['shares'] * df['sale_price']
    df['adjustment_code'] = ''
    df['adjustment_amount'] = 0.0
    
    return df


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Cost Basis Tracker")
    print("=" * 60)
    
    # Test adding a tax lot
    print("\nAdding test tax lot...")
    
    test_lot = TaxLot(
        lot_id=str(uuid.uuid4()),
        symbol="AAPL",
        account_name="Schwab Brokerage",
        account_type="Brokerage",
        shares=100.0,
        purchase_price=150.00,
        purchase_date=date(2024, 1, 15),
        cost_basis=15000.00,
        notes="Test lot"
    )
    
    try:
        add_tax_lot(test_lot)
        print(f"  Added: {test_lot.symbol} - {test_lot.shares} shares")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Test retrieving lots
    print("\nRetrieving tax lots for AAPL...")
    lots = get_tax_lots(symbol="AAPL")
    print(f"  Found {len(lots)} lots")
    
    for lot in lots:
        print(f"    {lot.lot_id[:8]}... - {lot.shares} shares @ ${lot.purchase_price:.2f}")
        print(f"      Purchased: {lot.purchase_date}")
        print(f"      Holding period: {lot.holding_period_days()} days")
        print(f"      Gain type: {lot.gain_type().value}")
    
    # Test unrealized gains/losses
    print("\nCalculating unrealized gains/losses...")
    current_prices = {"AAPL": 175.00}  # Simulated current price
    
    df = get_unrealized_gains_losses(symbol="AAPL", current_prices=current_prices)
    
    if not df.empty:
        print(f"\n{df.to_string(index=False)}")
    else:
        print("  No positions found")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

# Made with Bob
