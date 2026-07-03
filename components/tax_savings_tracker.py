"""
Tax Savings Tracker
===================
Track and report tax savings from direct index harvesting.

This module provides functionality to:
- Track realized tax savings from harvests
- Calculate year-to-date savings
- Generate tax reports
- Compare actual vs estimated savings
- Track harvest history and performance

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
from dataclasses import dataclass, asdict
import json

import pandas as pd
import numpy as np

from components.cost_basis_tracker import LotDisposition, GainType

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

DB_PATH = Path("data/rsp_holdings.db")


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class TaxSavingsRecord:
    """Record of tax savings from a harvest."""
    record_id: str
    execution_id: str
    harvest_date: date
    tax_year: int
    
    # Position details
    symbol_sold: str
    symbol_bought: str
    shares: float
    
    # Financial details
    sale_price: float
    purchase_price: float
    realized_loss: float
    
    # Tax impact
    estimated_tax_savings: float
    actual_tax_savings: Optional[float]
    ltcg_rate: float
    marginal_rate: float
    is_long_term: bool
    
    # Account
    account_name: str
    account_type: str
    
    # Metadata
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['harvest_date'] = self.harvest_date.isoformat()
        return d


@dataclass
class YearToDateSummary:
    """Year-to-date tax savings summary."""
    tax_year: int
    total_harvests: int
    total_realized_losses: float
    total_estimated_savings: float
    total_actual_savings: float
    
    # By term
    short_term_losses: float
    long_term_losses: float
    short_term_savings: float
    long_term_savings: float
    
    # By account
    by_account: Dict[str, Dict]
    
    # By sector
    by_sector: Dict[str, Dict]


# ==============================================================================
# DATABASE FUNCTIONS
# ==============================================================================

def _init_savings_tables():
    """Initialize tax savings tracking tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tax savings records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_savings_records (
            record_id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL,
            harvest_date TEXT NOT NULL,
            tax_year INTEGER NOT NULL,
            symbol_sold TEXT NOT NULL,
            symbol_bought TEXT NOT NULL,
            shares REAL NOT NULL,
            sale_price REAL NOT NULL,
            purchase_price REAL NOT NULL,
            realized_loss REAL NOT NULL,
            estimated_tax_savings REAL NOT NULL,
            actual_tax_savings REAL,
            ltcg_rate REAL NOT NULL,
            marginal_rate REAL NOT NULL,
            is_long_term INTEGER NOT NULL,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tax_savings_year 
        ON tax_savings_records(tax_year)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tax_savings_account 
        ON tax_savings_records(account_name)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tax_savings_date 
        ON tax_savings_records(harvest_date)
    """)
    
    conn.commit()
    conn.close()


def _save_savings_record(record: TaxSavingsRecord):
    """Save tax savings record to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO tax_savings_records
        (record_id, execution_id, harvest_date, tax_year, symbol_sold, symbol_bought,
         shares, sale_price, purchase_price, realized_loss, estimated_tax_savings,
         actual_tax_savings, ltcg_rate, marginal_rate, is_long_term, account_name,
         account_type, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.record_id,
        record.execution_id,
        record.harvest_date.isoformat(),
        record.tax_year,
        record.symbol_sold,
        record.symbol_bought,
        record.shares,
        record.sale_price,
        record.purchase_price,
        record.realized_loss,
        record.estimated_tax_savings,
        record.actual_tax_savings,
        record.ltcg_rate,
        record.marginal_rate,
        1 if record.is_long_term else 0,
        record.account_name,
        record.account_type,
        record.notes,
        now,
        now
    ))
    
    conn.commit()
    conn.close()


# ==============================================================================
# TRACKING FUNCTIONS
# ==============================================================================

def record_harvest_savings(
    execution_id: str,
    dispositions: List[LotDisposition],
    symbol_bought: str,
    shares_bought: float,
    estimated_tax_savings: float,
    ltcg_rate: float,
    marginal_rate: float,
    account_name: str,
    account_type: str,
    notes: str = ""
) -> List[TaxSavingsRecord]:
    """
    Record tax savings from a harvest execution.
    
    Args:
        execution_id: Execution ID
        dispositions: List of lot dispositions from sale
        symbol_bought: Replacement symbol purchased
        shares_bought: Shares of replacement purchased
        estimated_tax_savings: Estimated tax savings
        ltcg_rate: Long-term capital gains rate
        marginal_rate: Marginal tax rate
        account_name: Account name
        account_type: Account type
        notes: Additional notes
    
    Returns:
        List of tax savings records created
    """
    _init_savings_tables()
    
    records = []
    harvest_date = date.today()
    tax_year = harvest_date.year
    
    for disposition in dispositions:
        # Calculate realized loss (should be negative)
        realized_loss = disposition.gain_loss
        
        # Calculate tax savings based on gain type
        if disposition.gain_type == GainType.LONG_TERM:
            tax_savings = abs(realized_loss) * ltcg_rate
            is_long_term = True
        else:
            tax_savings = abs(realized_loss) * marginal_rate
            is_long_term = False
        
        # Calculate average purchase price from cost basis
        avg_purchase_price = disposition.cost_basis / disposition.shares_sold if disposition.shares_sold > 0 else 0.0
        
        record = TaxSavingsRecord(
            record_id=f"{execution_id}_{disposition.lot_id}",
            execution_id=execution_id,
            harvest_date=harvest_date,
            tax_year=tax_year,
            symbol_sold=disposition.symbol,
            symbol_bought=symbol_bought,
            shares=disposition.shares_sold,
            sale_price=disposition.sale_price,
            purchase_price=avg_purchase_price,
            realized_loss=realized_loss,
            estimated_tax_savings=tax_savings,
            actual_tax_savings=None,  # Updated at tax time
            ltcg_rate=ltcg_rate,
            marginal_rate=marginal_rate,
            is_long_term=is_long_term,
            account_name=account_name,
            account_type=account_type,
            notes=notes
        )
        
        _save_savings_record(record)
        records.append(record)
    
    logger.info(f"Recorded {len(records)} tax savings records for execution {execution_id}")
    
    return records


def update_actual_savings(
    record_id: str,
    actual_savings: float
) -> bool:
    """
    Update actual tax savings after filing taxes.
    
    Args:
        record_id: Record ID
        actual_savings: Actual tax savings realized
    
    Returns:
        True if updated successfully
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE tax_savings_records
        SET actual_tax_savings = ?,
            updated_at = ?
        WHERE record_id = ?
    """, (actual_savings, datetime.now().isoformat(), record_id))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Updated actual savings for record {record_id}")
    
    return True


# ==============================================================================
# REPORTING FUNCTIONS
# ==============================================================================

def get_ytd_summary(
    tax_year: Optional[int] = None,
    account_name: Optional[str] = None
) -> YearToDateSummary:
    """
    Get year-to-date tax savings summary.
    
    Args:
        tax_year: Tax year (default: current year)
        account_name: Filter by account (optional)
    
    Returns:
        YearToDateSummary
    """
    if tax_year is None:
        tax_year = date.today().year
    
    conn = sqlite3.connect(DB_PATH)
    
    # Build query
    query = """
        SELECT *
        FROM tax_savings_records
        WHERE tax_year = ?
    """
    params: List = [tax_year]
    
    if account_name:
        query += " AND account_name = ?"
        params.append(account_name)
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df.empty:
        return YearToDateSummary(
            tax_year=tax_year,
            total_harvests=0,
            total_realized_losses=0.0,
            total_estimated_savings=0.0,
            total_actual_savings=0.0,
            short_term_losses=0.0,
            long_term_losses=0.0,
            short_term_savings=0.0,
            long_term_savings=0.0,
            by_account={},
            by_sector={}
        )
    
    # Calculate totals
    total_harvests = len(df)
    total_realized_losses = float(df['realized_loss'].sum())
    total_estimated_savings = float(df['estimated_tax_savings'].sum())
    
    # Check if actual_tax_savings has any non-null values
    has_actual = df['actual_tax_savings'].notna().sum() > 0
    total_actual_savings = float(df['actual_tax_savings'].sum()) if has_actual else 0.0
    
    # By term
    short_term_df = df[df['is_long_term'] == 0]
    long_term_df = df[df['is_long_term'] == 1]
    
    short_term_losses = short_term_df['realized_loss'].sum() if not short_term_df.empty else 0.0
    long_term_losses = long_term_df['realized_loss'].sum() if not long_term_df.empty else 0.0
    short_term_savings = short_term_df['estimated_tax_savings'].sum() if not short_term_df.empty else 0.0
    long_term_savings = long_term_df['estimated_tax_savings'].sum() if not long_term_df.empty else 0.0
    
    # By account
    by_account = {}
    for account in df['account_name'].unique():
        account_df = df[df['account_name'] == account]
        actual_col = account_df['actual_tax_savings']
        has_actual_account = pd.notna(actual_col).sum() > 0
        by_account[str(account)] = {
            'harvests': len(account_df),
            'realized_losses': float(account_df['realized_loss'].sum()),
            'estimated_savings': float(account_df['estimated_tax_savings'].sum()),
            'actual_savings': float(actual_col.sum()) if has_actual_account else 0.0
        }
    
    # By sector (would need sector mapping)
    by_sector = {}
    
    return YearToDateSummary(
        tax_year=tax_year,
        total_harvests=total_harvests,
        total_realized_losses=total_realized_losses,
        total_estimated_savings=total_estimated_savings,
        total_actual_savings=total_actual_savings,
        short_term_losses=short_term_losses,
        long_term_losses=long_term_losses,
        short_term_savings=short_term_savings,
        long_term_savings=long_term_savings,
        by_account=by_account,
        by_sector=by_sector
    )


def get_harvest_history(
    tax_year: Optional[int] = None,
    account_name: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> pd.DataFrame:
    """
    Get harvest history as DataFrame.
    
    Args:
        tax_year: Filter by tax year (optional)
        account_name: Filter by account (optional)
        start_date: Start date filter (optional)
        end_date: End date filter (optional)
    
    Returns:
        DataFrame with harvest history
    """
    conn = sqlite3.connect(DB_PATH)
    
    # Build query
    query = "SELECT * FROM tax_savings_records WHERE 1=1"
    params = []
    
    if tax_year:
        query += " AND tax_year = ?"
        params.append(tax_year)
    
    if account_name:
        query += " AND account_name = ?"
        params.append(account_name)
    
    if start_date:
        query += " AND harvest_date >= ?"
        params.append(start_date.isoformat())
    
    if end_date:
        query += " AND harvest_date <= ?"
        params.append(end_date.isoformat())
    
    query += " ORDER BY harvest_date DESC"
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    conn.close()
    
    if not df.empty:
        df['harvest_date'] = pd.to_datetime(df['harvest_date'])
    
    return df


def export_tax_report(
    tax_year: int,
    output_path: Optional[str] = None
) -> str:
    """
    Export tax report for the year.
    
    Args:
        tax_year: Tax year
        output_path: Output file path
    
    Returns:
        Path to exported file
    """
    if output_path is None:
        output_path = f"data/tax_report_{tax_year}.csv"
    
    df = get_harvest_history(tax_year=tax_year)
    
    if df.empty:
        logger.warning(f"No harvest data for tax year {tax_year}")
        return output_path
    
    # Format for tax reporting
    tax_report = df[[
        'harvest_date',
        'symbol_sold',
        'shares',
        'purchase_price',
        'sale_price',
        'realized_loss',
        'is_long_term',
        'account_name'
    ]].copy()
    
    tax_report.columns = [
        'Date Sold',
        'Symbol',
        'Shares',
        'Cost Basis',
        'Sale Price',
        'Gain/Loss',
        'Long Term',
        'Account'
    ]
    
    # Calculate totals
    tax_report['Proceeds'] = tax_report['Shares'] * tax_report['Sale Price']
    tax_report['Cost'] = tax_report['Shares'] * tax_report['Cost Basis']
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    tax_report.to_csv(output_path, index=False)
    
    logger.info(f"Exported tax report to {output_path}")
    
    return output_path


def get_performance_metrics(
    tax_year: Optional[int] = None
) -> Dict:
    """
    Get performance metrics for harvesting strategy.
    
    Args:
        tax_year: Tax year (default: current year)
    
    Returns:
        Dictionary with performance metrics
    """
    if tax_year is None:
        tax_year = date.today().year
    
    summary = get_ytd_summary(tax_year)
    
    # Calculate metrics
    avg_loss_per_harvest = (
        summary.total_realized_losses / summary.total_harvests
        if summary.total_harvests > 0 else 0.0
    )
    
    avg_savings_per_harvest = (
        summary.total_estimated_savings / summary.total_harvests
        if summary.total_harvests > 0 else 0.0
    )
    
    # Accuracy (if actual savings available)
    accuracy = 0.0
    if summary.total_actual_savings > 0:
        accuracy = (summary.total_actual_savings / summary.total_estimated_savings) * 100
    
    return {
        'tax_year': tax_year,
        'total_harvests': summary.total_harvests,
        'total_losses_realized': summary.total_realized_losses,
        'total_tax_savings': summary.total_estimated_savings,
        'avg_loss_per_harvest': avg_loss_per_harvest,
        'avg_savings_per_harvest': avg_savings_per_harvest,
        'short_term_pct': (
            (abs(summary.short_term_losses) / abs(summary.total_realized_losses)) * 100
            if summary.total_realized_losses != 0 else 0.0
        ),
        'long_term_pct': (
            (abs(summary.long_term_losses) / abs(summary.total_realized_losses)) * 100
            if summary.total_realized_losses != 0 else 0.0
        ),
        'estimate_accuracy_pct': accuracy
    }


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Tax Savings Tracker")
    print("=" * 60)
    
    # Initialize tables
    _init_savings_tables()
    print("Initialized tax savings tables")
    
    # Get YTD summary
    print("\nGetting YTD summary...")
    summary = get_ytd_summary()
    
    print(f"\nTax Year: {summary.tax_year}")
    print(f"Total Harvests: {summary.total_harvests}")
    print(f"Total Realized Losses: ${summary.total_realized_losses:,.2f}")
    print(f"Total Estimated Savings: ${summary.total_estimated_savings:,.2f}")
    print(f"Short-Term Losses: ${summary.short_term_losses:,.2f}")
    print(f"Long-Term Losses: ${summary.long_term_losses:,.2f}")
    
    if summary.by_account:
        print("\nBy Account:")
        for account, stats in summary.by_account.items():
            print(f"  {account}:")
            print(f"    Harvests: {stats['harvests']}")
            print(f"    Savings: ${stats['estimated_savings']:,.2f}")
    
    # Get performance metrics
    print("\nGetting performance metrics...")
    metrics = get_performance_metrics()
    
    print(f"\nAverage Loss per Harvest: ${metrics['avg_loss_per_harvest']:,.2f}")
    print(f"Average Savings per Harvest: ${metrics['avg_savings_per_harvest']:,.2f}")
    print(f"Short-Term %: {metrics['short_term_pct']:.1f}%")
    print(f"Long-Term %: {metrics['long_term_pct']:.1f}%")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

# Made with Bob
