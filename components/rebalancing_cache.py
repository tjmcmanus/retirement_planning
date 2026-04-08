"""
components/rebalancing_cache.py
================================
Cache rebalancing analysis results for use in reports.

Stores:
- User's target allocations from Portfolio Hub
- Latest rebalancing analysis results
- Timestamp of last calculation
"""
from __future__ import annotations

import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Database path
CACHE_DB_PATH = Path(__file__).parent.parent / "data" / "rebalancing_cache.db"


@dataclass
class TargetAllocation:
    """User's target portfolio allocation."""
    cash_pct: float
    bonds_pct: float
    stocks_pct: float
    drift_threshold_pct: float
    last_updated: str  # ISO format datetime


@dataclass
class RebalancingCache:
    """Cached rebalancing analysis results."""
    calculation_date: str  # ISO format date
    drift_triggered: bool
    total_value: float
    summary_json: str  # JSON string of summary DataFrame
    actions_count: int
    target_allocation: TargetAllocation


class RebalancingCacheManager:
    """Manage rebalancing analysis cache."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize cache manager.
        
        Args:
            db_path: Path to SQLite database (default: data/rebalancing_cache.db)
        """
        self.db_path = db_path or CACHE_DB_PATH
        self._init_database()
        logger.info(f"RebalancingCacheManager initialized with db: {self.db_path}")
    
    def _init_database(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Target allocations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS target_allocations (
                    id INTEGER PRIMARY KEY,
                    cash_pct REAL NOT NULL,
                    bonds_pct REAL NOT NULL,
                    stocks_pct REAL NOT NULL,
                    drift_threshold_pct REAL NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Rebalancing cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rebalancing_cache (
                    id INTEGER PRIMARY KEY,
                    calculation_date TEXT NOT NULL UNIQUE,
                    drift_triggered INTEGER NOT NULL,
                    total_value REAL NOT NULL,
                    summary_json TEXT NOT NULL,
                    actions_count INTEGER NOT NULL,
                    actions_json TEXT,
                    cash_pct REAL NOT NULL,
                    bonds_pct REAL NOT NULL,
                    stocks_pct REAL NOT NULL,
                    drift_threshold_pct REAL NOT NULL
                )
            """)
            
            conn.commit()
            logger.info("Database schema initialized")
    
    def save_target_allocation(
        self,
        cash_pct: float,
        bonds_pct: float,
        stocks_pct: float,
        drift_threshold_pct: float = 5.0
    ):
        """
        Save user's target allocation.
        
        Args:
            cash_pct: Target cash percentage
            bonds_pct: Target bonds percentage
            stocks_pct: Target stocks percentage
            drift_threshold_pct: Drift threshold percentage
        """
        # Validate percentages sum to 100
        total = cash_pct + bonds_pct + stocks_pct
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Target allocations must sum to 100%, got {total}%")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Delete old allocation
            cursor.execute("DELETE FROM target_allocations")
            
            # Insert new allocation
            cursor.execute("""
                INSERT INTO target_allocations 
                (cash_pct, bonds_pct, stocks_pct, drift_threshold_pct, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """, (cash_pct, bonds_pct, stocks_pct, drift_threshold_pct, 
                  datetime.now().isoformat()))
            
            conn.commit()
            logger.info(f"Saved target allocation: {cash_pct}% cash, {bonds_pct}% bonds, {stocks_pct}% stocks")
    
    def get_target_allocation(self) -> Optional[TargetAllocation]:
        """
        Get user's target allocation.
        
        Returns:
            TargetAllocation or None if not set
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cash_pct, bonds_pct, stocks_pct, drift_threshold_pct, last_updated
                FROM target_allocations
                ORDER BY id DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                return TargetAllocation(
                    cash_pct=row[0],
                    bonds_pct=row[1],
                    stocks_pct=row[2],
                    drift_threshold_pct=row[3],
                    last_updated=row[4]
                )
            
            return None
    
    def save_rebalancing_analysis(
        self,
        drift_triggered: bool,
        total_value: float,
        summary_df: Any,  # pandas DataFrame
        actions_count: int,
        target_allocation: TargetAllocation,
        actions: Optional[list] = None
    ):
        """
        Save rebalancing analysis results.
        
        Args:
            drift_triggered: Whether rebalancing is needed
            total_value: Total portfolio value
            summary_df: Summary DataFrame with asset class details
            actions_count: Number of rebalancing actions
            target_allocation: Target allocation used
            actions: List of rebalancing action objects
        """
        import pandas as pd
        
        calculation_date = date.today().isoformat()
        
        # Convert DataFrame to JSON
        if isinstance(summary_df, pd.DataFrame):
            summary_json = summary_df.to_json(orient='records')
        else:
            summary_json = json.dumps([])
        
        # Convert actions to JSON (extract relevant fields from RebalanceAction objects)
        if actions:
            actions_data = []
            for action in actions:
                # Extract fields from RebalanceAction object
                action_dict = {
                    'priority': getattr(action, 'priority', 0),
                    'action': getattr(action, 'action', ''),
                    'asset_class': getattr(action, 'asset_class', ''),
                    'symbol': getattr(action, 'symbol', ''),
                    'account_name': getattr(action, 'account_name', ''),
                    'account_type': getattr(action, 'account_type', ''),
                    'amount': getattr(action, 'amount', 0),
                    'rationale': getattr(action, 'rationale', ''),
                    'tax_impact': getattr(action, 'tax_impact', ''),
                    'location_note': getattr(action, 'location_note', '')
                }
                actions_data.append(action_dict)
            actions_json = json.dumps(actions_data)
        else:
            actions_json = json.dumps([])
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Delete old cache for today (if exists)
            cursor.execute("DELETE FROM rebalancing_cache WHERE calculation_date = ?",
                          (calculation_date,))
            
            # Insert new cache
            cursor.execute("""
                INSERT INTO rebalancing_cache
                (calculation_date, drift_triggered, total_value, summary_json,
                 actions_count, actions_json, cash_pct, bonds_pct, stocks_pct, drift_threshold_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                calculation_date,
                1 if drift_triggered else 0,
                total_value,
                summary_json,
                actions_count,
                actions_json,
                target_allocation.cash_pct,
                target_allocation.bonds_pct,
                target_allocation.stocks_pct,
                target_allocation.drift_threshold_pct
            ))
            
            conn.commit()
            logger.info(f"Saved rebalancing analysis for {calculation_date}")
    
    def get_latest_analysis(self) -> Optional[Dict[str, Any]]:
        """
        Get latest rebalancing analysis.
        
        Returns:
            Dictionary with analysis results or None if not available
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT calculation_date, drift_triggered, total_value, summary_json,
                       actions_count, actions_json, cash_pct, bonds_pct, stocks_pct, drift_threshold_pct
                FROM rebalancing_cache
                ORDER BY calculation_date DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                import pandas as pd
                
                # Parse summary JSON back to DataFrame
                summary_json = row[3]
                try:
                    summary_data = json.loads(summary_json)
                    summary_df = pd.DataFrame(summary_data) if summary_data else None
                except:
                    summary_df = None
                
                # Parse actions JSON
                actions_json = row[5]
                try:
                    actions = json.loads(actions_json) if actions_json else []
                except:
                    actions = []
                
                return {
                    'calculation_date': row[0],
                    'drift_triggered': bool(row[1]),
                    'total_value': row[2],
                    'summary': summary_df,
                    'actions_count': row[4],
                    'actions': actions,
                    'target_allocation': TargetAllocation(
                        cash_pct=row[6],
                        bonds_pct=row[7],
                        stocks_pct=row[8],
                        drift_threshold_pct=row[9],
                        last_updated=row[0]
                    )
                }
            
            return None
    
    def needs_update(self) -> bool:
        """
        Check if cache needs updating (older than 1 day).
        
        Returns:
            True if cache should be updated
        """
        latest = self.get_latest_analysis()
        if not latest:
            return True
        
        try:
            cache_date = datetime.fromisoformat(latest['calculation_date']).date()
            today = date.today()
            return cache_date < today
        except:
            return True
    
    def update_cache(self):
        """
        Update cache with fresh rebalancing analysis.
        
        This should be called:
        - Once per day automatically
        - When user changes target allocations
        - When generating a report if cache is stale
        """
        try:
            from portfolio_rebalancing import compute_rebalance_plan
            import datetime
            
            # Get target allocation
            target = self.get_target_allocation()
            if not target:
                logger.warning("No target allocation set, using defaults")
                target = TargetAllocation(
                    cash_pct=10.0,
                    bonds_pct=10.0,
                    stocks_pct=80.0,
                    drift_threshold_pct=5.0,
                    last_updated=datetime.datetime.now().isoformat()
                )
            
            # Compute rebalancing plan
            current_date = datetime.date.today()
            report = compute_rebalance_plan(
                month=current_date.month,
                year=current_date.year,
                target_cash_pct=target.cash_pct,
                target_bonds_pct=target.bonds_pct,
                target_stocks_pct=target.stocks_pct,
                drift_threshold_pct=target.drift_threshold_pct
            )
            
            # Build summary DataFrame
            import pandas as pd
            summary_data = []
            for asset_summary in report.asset_summary:
                summary_data.append({
                    'Asset Class': asset_summary.asset_class,
                    'Current Value': asset_summary.current_value,
                    'Current %': asset_summary.current_pct,
                    'Target %': asset_summary.target_pct,
                    'Difference': asset_summary.drift_pct,
                    'Trade Amount': asset_summary.delta_value
                })
            
            summary_df = pd.DataFrame(summary_data) if summary_data else None
            
            # Save to cache
            self.save_rebalancing_analysis(
                drift_triggered=report.drift_triggered,
                total_value=report.total_portfolio_value,
                summary_df=summary_df,
                actions_count=len(report.actions),
                target_allocation=target,
                actions=report.actions
            )
            
            logger.info("Rebalancing cache updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update rebalancing cache: {e}", exc_info=True)
            return False


# Singleton instance
_cache_manager_instance: Optional[RebalancingCacheManager] = None


def get_cache_manager() -> RebalancingCacheManager:
    """Get singleton cache manager instance."""
    global _cache_manager_instance
    if _cache_manager_instance is None:
        _cache_manager_instance = RebalancingCacheManager()
    return _cache_manager_instance

# Made with Bob
