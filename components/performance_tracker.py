"""
components/performance_tracker.py
==================================
Performance tracking module for accurate historical portfolio performance analysis.

This module provides:
1. Database storage for daily/monthly portfolio snapshots
2. Time-Weighted Return (TWR) calculations
3. Cash flow handling
4. Performance attribution
5. Historical data backfill capabilities
"""
from __future__ import annotations

import sqlite3
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "performance_history.db"


@dataclass
class PerformanceSnapshot:
    """Represents a portfolio snapshot at a point in time."""
    snapshot_date: date
    total_value: Decimal
    account_breakdown: Dict[str, Decimal]  # account_type -> value
    cash_flow: Decimal  # Net cash flow (deposits positive, withdrawals negative)
    notes: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """Performance metrics for a time period."""
    start_date: date
    end_date: date
    twr: float  # Time-Weighted Return
    mwr: float  # Money-Weighted Return (IRR)
    total_return: float  # Simple return
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    total_deposits: Decimal
    total_withdrawals: Decimal
    starting_value: Decimal
    ending_value: Decimal


class PerformanceTracker:
    """
    Track and analyze portfolio performance over time.
    
    Features:
    - Store daily/monthly portfolio snapshots
    - Calculate Time-Weighted Returns (TWR)
    - Handle cash flows properly
    - Generate performance reports
    - Backfill historical data
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize performance tracker.
        
        Args:
            db_path: Path to SQLite database (default: data/performance_history.db)
        """
        self.db_path = db_path or DB_PATH
        self._ensure_database()
        logger.info(f"PerformanceTracker initialized with database: {self.db_path}")
    
    def _ensure_database(self):
        """Create database and tables if they don't exist."""
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Portfolio snapshots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date DATE NOT NULL UNIQUE,
                    total_value REAL NOT NULL,
                    cash_flow REAL DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Account breakdown table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    account_type TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    market_value REAL NOT NULL,
                    FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(id),
                    UNIQUE(snapshot_id, account_type, account_name)
                )
            """)
            
            # Cash flows table (for detailed tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cash_flows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_date DATE NOT NULL,
                    account_type TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    flow_type TEXT NOT NULL,  -- 'deposit', 'withdrawal', 'dividend', 'fee'
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Performance metrics cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    period_type TEXT NOT NULL,  -- '1M', '3M', '6M', '1Y', 'YTD', 'ITD'
                    twr REAL,
                    mwr REAL,
                    total_return REAL,
                    annualized_return REAL,
                    volatility REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(start_date, end_date, period_type)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_date 
                ON portfolio_snapshots(snapshot_date)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cash_flows_date 
                ON cash_flows(flow_date)
            """)
            
            conn.commit()
            logger.info("Database schema initialized successfully")
    
    def record_snapshot(self, snapshot: PerformanceSnapshot) -> int:
        """
        Record a portfolio snapshot.
        
        Args:
            snapshot: PerformanceSnapshot object
            
        Returns:
            Snapshot ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert or update portfolio snapshot
            cursor.execute("""
                INSERT INTO portfolio_snapshots (snapshot_date, total_value, cash_flow, notes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(snapshot_date) DO UPDATE SET
                    total_value = excluded.total_value,
                    cash_flow = excluded.cash_flow,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                snapshot.snapshot_date.isoformat(),
                float(snapshot.total_value),
                float(snapshot.cash_flow),
                snapshot.notes
            ))
            
            snapshot_id = cursor.lastrowid
            
            # Delete existing account snapshots for this date
            cursor.execute("""
                DELETE FROM account_snapshots 
                WHERE snapshot_id = (
                    SELECT id FROM portfolio_snapshots 
                    WHERE snapshot_date = ?
                )
            """, (snapshot.snapshot_date.isoformat(),))
            
            # Insert account breakdown
            for account_key, value in snapshot.account_breakdown.items():
                # Parse account_key (format: "account_type:account_name")
                if ':' in account_key:
                    account_type, account_name = account_key.split(':', 1)
                else:
                    account_type = account_key
                    account_name = account_key
                
                cursor.execute("""
                    INSERT INTO account_snapshots (snapshot_id, account_type, account_name, market_value)
                    VALUES (?, ?, ?, ?)
                """, (snapshot_id, account_type, account_name, float(value)))
            
            conn.commit()
            logger.info(f"Recorded snapshot for {snapshot.snapshot_date}: ${snapshot.total_value:,.2f}")
            return snapshot_id
    
    def get_snapshots(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Retrieve portfolio snapshots for a date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            DataFrame with columns: snapshot_date, total_value, cash_flow
        """
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT snapshot_date, total_value, cash_flow FROM portfolio_snapshots"
            conditions = []
            params = []
            
            if start_date:
                conditions.append("snapshot_date >= ?")
                params.append(start_date.isoformat())
            
            if end_date:
                conditions.append("snapshot_date <= ?")
                params.append(end_date.isoformat())
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY snapshot_date"
            
            df = pd.read_sql_query(query, conn, params=params)
            
            if not df.empty:
                df['snapshot_date'] = pd.to_datetime(df['snapshot_date']).dt.date
            
            return df
    
    def calculate_twr(
        self,
        start_date: date,
        end_date: date
    ) -> Optional[float]:
        """
        Calculate Time-Weighted Return (TWR) for a period.
        
        TWR eliminates the impact of cash flows, showing the true investment performance.
        
        Formula:
        TWR = [(1 + R1) × (1 + R2) × ... × (1 + Rn)] - 1
        
        Where Ri is the return for each sub-period between cash flows.
        
        Args:
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            TWR as decimal (e.g., 0.075 for 7.5% return) or None if insufficient data
        """
        try:
            # Get all snapshots in the period
            snapshots = self.get_snapshots(start_date, end_date)
            
            if snapshots.empty or len(snapshots) < 2:
                logger.warning(f"Insufficient data for TWR calculation: {len(snapshots)} snapshots")
                return None
            
            # Calculate sub-period returns
            sub_period_returns = []
            
            for i in range(len(snapshots) - 1):
                start_value = snapshots.iloc[i]['total_value']
                end_value = snapshots.iloc[i + 1]['total_value']
                cash_flow = snapshots.iloc[i + 1]['cash_flow']
                
                # Adjust for cash flow
                # If cash flow occurred, calculate return before cash flow
                adjusted_end_value = end_value - cash_flow
                
                if start_value > 0:
                    sub_return = (adjusted_end_value - start_value) / start_value
                    sub_period_returns.append(sub_return)
            
            if not sub_period_returns:
                return None
            
            # Calculate compound return
            twr = 1.0
            for r in sub_period_returns:
                twr *= (1 + r)
            twr -= 1
            
            logger.info(f"TWR for {start_date} to {end_date}: {twr*100:.2f}%")
            return twr
            
        except Exception as e:
            logger.error(f"Error calculating TWR: {e}")
            return None
    
    def calculate_performance_metrics(
        self,
        start_date: date,
        end_date: date,
        risk_free_rate: float = 0.04
    ) -> Optional[PerformanceMetrics]:
        """
        Calculate comprehensive performance metrics for a period.
        
        Args:
            start_date: Period start date
            end_date: Period end date
            risk_free_rate: Annual risk-free rate for Sharpe ratio (default: 4%)
            
        Returns:
            PerformanceMetrics object or None if insufficient data
        """
        try:
            snapshots = self.get_snapshots(start_date, end_date)
            
            if snapshots.empty or len(snapshots) < 2:
                return None
            
            # Basic values
            starting_value = Decimal(str(snapshots.iloc[0]['total_value']))
            ending_value = Decimal(str(snapshots.iloc[-1]['total_value']))
            total_deposits = Decimal(str(snapshots[snapshots['cash_flow'] > 0]['cash_flow'].sum()))
            total_withdrawals = Decimal(str(abs(snapshots[snapshots['cash_flow'] < 0]['cash_flow'].sum())))
            
            # Calculate TWR
            twr = self.calculate_twr(start_date, end_date)
            if twr is None:
                twr = 0.0
            
            # Calculate simple return
            total_return = float((ending_value - starting_value - total_deposits + total_withdrawals) / starting_value)
            
            # Annualize return
            days = (end_date - start_date).days
            years = days / 365.25
            if years > 0:
                annualized_return = (1 + twr) ** (1 / years) - 1
            else:
                annualized_return = twr
            
            # Calculate volatility (standard deviation of returns)
            returns = snapshots['total_value'].pct_change().dropna()
            volatility = float(returns.std() * np.sqrt(252))  # Annualized
            
            # Calculate Sharpe ratio
            if volatility > 0:
                sharpe_ratio = (annualized_return - risk_free_rate) / volatility
            else:
                sharpe_ratio = 0.0
            
            # Calculate maximum drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = float(drawdown.min())
            
            # Calculate MWR (IRR) - simplified version
            mwr = total_return  # Placeholder - full IRR calculation is complex
            
            return PerformanceMetrics(
                start_date=start_date,
                end_date=end_date,
                twr=twr,
                mwr=mwr,
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                total_deposits=total_deposits,
                total_withdrawals=total_withdrawals,
                starting_value=starting_value,
                ending_value=ending_value
            )
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return None
    
    def backfill_from_networth_data(
        self,
        start_month: int,
        start_year: int,
        end_month: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> int:
        """
        Backfill performance history from existing net worth data.
        
        Args:
            start_month: Starting month (1-12)
            start_year: Starting year
            end_month: Ending month (default: current month)
            end_year: Ending year (default: current year)
            
        Returns:
            Number of snapshots created
        """
        from load_data import get_networth_by_month
        
        if end_month is None or end_year is None:
            today = date.today()
            end_month = today.month
            end_year = today.year
        
        count = 0
        current_date = date(start_year, start_month, 1)
        end_date = date(end_year, end_month, 1)
        
        logger.info(f"Backfilling performance data from {current_date} to {end_date}")
        
        while current_date <= end_date:
            try:
                # Get net worth data for this month
                detailed_df, summary_df = get_networth_by_month(current_date.month, current_date.year)
                
                if not summary_df.empty:
                    # Calculate total value (excluding Total row)
                    total_value = summary_df[summary_df['account_type'] != 'Total']['market_value'].sum()
                    
                    # Build account breakdown
                    account_breakdown = {}
                    for _, row in detailed_df.iterrows():
                        key = f"{row['account_type']}:{row['account_name']}"
                        if key in account_breakdown:
                            account_breakdown[key] += Decimal(str(row['market_value']))
                        else:
                            account_breakdown[key] = Decimal(str(row['market_value']))
                    
                    # Create snapshot (assume no cash flow for backfill)
                    snapshot = PerformanceSnapshot(
                        snapshot_date=current_date,
                        total_value=Decimal(str(total_value)),
                        account_breakdown=account_breakdown,
                        cash_flow=Decimal('0'),
                        notes="Backfilled from historical data"
                    )
                    
                    self.record_snapshot(snapshot)
                    count += 1
                
            except Exception as e:
                logger.warning(f"Could not backfill data for {current_date}: {e}")
            
            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
        
        logger.info(f"Backfilled {count} snapshots")
        return count
    
    def get_period_performance(
        self,
        period: str,
        end_date: Optional[date] = None
    ) -> Optional[PerformanceMetrics]:
        """
        Get performance metrics for a standard period.
        
        Args:
            period: Period type ('1M', '3M', '6M', '1Y', 'YTD', 'ITD')
            end_date: End date (default: today)
            
        Returns:
            PerformanceMetrics or None
        """
        if end_date is None:
            end_date = date.today()
        
        # Calculate start date based on period
        if period == '1M':
            start_date = end_date - timedelta(days=30)
        elif period == '3M':
            start_date = end_date - timedelta(days=90)
        elif period == '6M':
            start_date = end_date - timedelta(days=180)
        elif period == '1Y':
            start_date = end_date - timedelta(days=365)
        elif period == 'YTD':
            start_date = date(end_date.year, 1, 1)
        elif period == 'ITD':
            # Inception to date - get earliest snapshot
            snapshots = self.get_snapshots()
            if snapshots.empty:
                return None
            start_date = snapshots.iloc[0]['snapshot_date']
        else:
            raise ValueError(f"Unknown period: {period}")
        
        return self.calculate_performance_metrics(start_date, end_date)


# Convenience functions
def get_tracker() -> PerformanceTracker:
    """Get a PerformanceTracker instance."""
    return PerformanceTracker()


def record_current_portfolio() -> Optional[int]:
    """
    Record current portfolio as a snapshot.
    
    Returns:
        Snapshot ID or None if failed
    """
    try:
        from load_data import get_networth_by_month
        import datetime
        
        today = datetime.date.today()
        detailed_df, summary_df = get_networth_by_month(today.month, today.year)
        
        if summary_df.empty:
            logger.warning("No portfolio data available")
            return None
        
        # Calculate total value
        total_value = summary_df[summary_df['account_type'] != 'Total']['market_value'].sum()
        
        # Build account breakdown
        account_breakdown = {}
        for _, row in detailed_df.iterrows():
            key = f"{row['account_type']}:{row['account_name']}"
            if key in account_breakdown:
                account_breakdown[key] += Decimal(str(row['market_value']))
            else:
                account_breakdown[key] = Decimal(str(row['market_value']))
        
        # Create snapshot
        snapshot = PerformanceSnapshot(
            snapshot_date=today,
            total_value=Decimal(str(total_value)),
            account_breakdown=account_breakdown,
            cash_flow=Decimal('0'),  # Would need to be tracked separately
            notes="Automated snapshot"
        )
        
        tracker = get_tracker()
        return tracker.record_snapshot(snapshot)
        
    except Exception as e:
        logger.error(f"Error recording current portfolio: {e}")
        return None

# Made with Bob
