"""
Harvest Execution Workflow
===========================
Execute tax loss harvesting trades with manual review and approval.

This module provides functionality to:
- Generate trade instructions for harvest opportunities
- Create replacement purchase orders
- Track execution status
- Handle partial fills and errors
- Maintain audit trail

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
from enum import Enum
import uuid
import json

import pandas as pd

from components.direct_index_harvester import HarvestOpportunity
from components.replacement_selector import find_replacement_stock
from components.cost_basis_tracker import (
    sell_shares,
    add_tax_lot,
    TaxLot,
    LotSelectionMethod,
    LotDisposition
)

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

DB_PATH = Path("data/rsp_holdings.db")


# ==============================================================================
# ENUMS
# ==============================================================================

class TradeStatus(Enum):
    """Trade execution status."""
    PENDING = "pending"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


class TradeType(Enum):
    """Type of trade."""
    SELL = "sell"
    BUY = "buy"


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class TradeInstruction:
    """Trade instruction for execution."""
    trade_id: str
    trade_type: TradeType
    symbol: str
    shares: float
    account_name: str
    account_type: str
    estimated_price: float
    estimated_value: float
    lot_ids: List[str]  # For sells
    notes: str
    created_at: datetime
    status: TradeStatus
    
    # Execution details (filled after execution)
    executed_price: Optional[float] = None
    executed_shares: Optional[float] = None
    executed_at: Optional[datetime] = None
    execution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['trade_type'] = self.trade_type.value
        d['status'] = self.status.value
        d['created_at'] = self.created_at.isoformat()
        if self.executed_at:
            d['executed_at'] = self.executed_at.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, d: Dict) -> TradeInstruction:
        """Create from dictionary."""
        d = d.copy()
        d['trade_type'] = TradeType(d['trade_type'])
        d['status'] = TradeStatus(d['status'])
        d['created_at'] = datetime.fromisoformat(d['created_at'])
        if d.get('executed_at'):
            d['executed_at'] = datetime.fromisoformat(d['executed_at'])
        return cls(**d)


@dataclass
class HarvestExecution:
    """Complete harvest execution plan."""
    execution_id: str
    harvest_opportunity: HarvestOpportunity
    sell_trade: TradeInstruction
    buy_trade: TradeInstruction
    replacement_symbol: str
    created_at: datetime
    status: TradeStatus
    tax_savings_estimate: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'execution_id': self.execution_id,
            'harvest_opportunity': self.harvest_opportunity.to_dict(),
            'sell_trade': self.sell_trade.to_dict(),
            'buy_trade': self.buy_trade.to_dict(),
            'replacement_symbol': self.replacement_symbol,
            'created_at': self.created_at.isoformat(),
            'status': self.status.value,
            'tax_savings_estimate': self.tax_savings_estimate
        }


# ==============================================================================
# DATABASE FUNCTIONS
# ==============================================================================

def _init_execution_tables():
    """Initialize execution tracking tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Trade instructions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_instructions (
            trade_id TEXT PRIMARY KEY,
            execution_id TEXT,
            trade_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            shares REAL NOT NULL,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            estimated_price REAL NOT NULL,
            estimated_value REAL NOT NULL,
            lot_ids TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            executed_price REAL,
            executed_shares REAL,
            executed_at TEXT,
            execution_notes TEXT,
            FOREIGN KEY (execution_id) REFERENCES harvest_executions(execution_id)
        )
    """)
    
    # Harvest executions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS harvest_executions (
            execution_id TEXT PRIMARY KEY,
            harvest_opportunity TEXT NOT NULL,
            sell_trade_id TEXT NOT NULL,
            buy_trade_id TEXT NOT NULL,
            replacement_symbol TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            tax_savings_estimate REAL NOT NULL,
            FOREIGN KEY (sell_trade_id) REFERENCES trade_instructions(trade_id),
            FOREIGN KEY (buy_trade_id) REFERENCES trade_instructions(trade_id)
        )
    """)
    
    # Execution audit log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS execution_audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            user TEXT,
            FOREIGN KEY (execution_id) REFERENCES harvest_executions(execution_id)
        )
    """)
    
    conn.commit()
    conn.close()


def _save_trade_instruction(trade: TradeInstruction):
    """Save trade instruction to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO trade_instructions
        (trade_id, trade_type, symbol, shares, account_name, account_type,
         estimated_price, estimated_value, lot_ids, notes, created_at, status,
         executed_price, executed_shares, executed_at, execution_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trade.trade_id,
        trade.trade_type.value,
        trade.symbol,
        trade.shares,
        trade.account_name,
        trade.account_type,
        trade.estimated_price,
        trade.estimated_value,
        json.dumps(trade.lot_ids),
        trade.notes,
        trade.created_at.isoformat(),
        trade.status.value,
        trade.executed_price,
        trade.executed_shares,
        trade.executed_at.isoformat() if trade.executed_at else None,
        trade.execution_notes
    ))
    
    conn.commit()
    conn.close()


def _save_harvest_execution(execution: HarvestExecution):
    """Save harvest execution to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO harvest_executions
        (execution_id, harvest_opportunity, sell_trade_id, buy_trade_id,
         replacement_symbol, created_at, status, tax_savings_estimate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        execution.execution_id,
        json.dumps(execution.harvest_opportunity.to_dict()),
        execution.sell_trade.trade_id,
        execution.buy_trade.trade_id,
        execution.replacement_symbol,
        execution.created_at.isoformat(),
        execution.status.value,
        execution.tax_savings_estimate
    ))
    
    conn.commit()
    conn.close()


def _log_execution_action(
    execution_id: str,
    action: str,
    details: Optional[str] = None,
    user: Optional[str] = None
):
    """Log execution action to audit trail."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO execution_audit_log
        (execution_id, timestamp, action, details, user)
        VALUES (?, ?, ?, ?, ?)
    """, (
        execution_id,
        datetime.now().isoformat(),
        action,
        details,
        user
    ))
    
    conn.commit()
    conn.close()


# ==============================================================================
# EXECUTION PLANNING
# ==============================================================================

def create_harvest_execution(
    opportunity: HarvestOpportunity,
    replacement_symbol: str,
    lot_selection_method: LotSelectionMethod = LotSelectionMethod.HIFO
) -> HarvestExecution:
    """
    Create harvest execution plan.
    
    Args:
        opportunity: Harvest opportunity
        replacement_symbol: Symbol to buy as replacement
        lot_selection_method: Method for selecting lots to sell
    
    Returns:
        HarvestExecution plan
    """
    _init_execution_tables()
    
    execution_id = str(uuid.uuid4())
    now = datetime.now()
    
    # Create sell trade
    sell_trade = TradeInstruction(
        trade_id=str(uuid.uuid4()),
        trade_type=TradeType.SELL,
        symbol=opportunity.symbol,
        shares=opportunity.shares,
        account_name=opportunity.account_name,
        account_type=opportunity.account_type,
        estimated_price=opportunity.current_price,
        estimated_value=opportunity.shares * opportunity.current_price,
        lot_ids=[],  # Will be filled during execution
        notes=f"Tax loss harvest: {opportunity.loss_percentage:.1f}% loss",
        created_at=now,
        status=TradeStatus.PENDING
    )
    
    # Create buy trade (same dollar amount)
    buy_value = sell_trade.estimated_value
    
    # Get replacement price (use current price from opportunity's data)
    from components.rsp_holdings_fetcher import get_constituent
    replacement = get_constituent(replacement_symbol)
    replacement_price = replacement.current_price if replacement else 0.0
    
    if replacement_price <= 0:
        raise ValueError(f"Invalid price for replacement symbol {replacement_symbol}")
    
    buy_shares = buy_value / replacement_price
    
    buy_trade = TradeInstruction(
        trade_id=str(uuid.uuid4()),
        trade_type=TradeType.BUY,
        symbol=replacement_symbol,
        shares=buy_shares,
        account_name=opportunity.account_name,
        account_type=opportunity.account_type,
        estimated_price=replacement_price,
        estimated_value=buy_value,
        lot_ids=[],
        notes=f"Replacement for {opportunity.symbol}",
        created_at=now,
        status=TradeStatus.PENDING
    )
    
    # Create execution plan
    execution = HarvestExecution(
        execution_id=execution_id,
        harvest_opportunity=opportunity,
        sell_trade=sell_trade,
        buy_trade=buy_trade,
        replacement_symbol=replacement_symbol,
        created_at=now,
        status=TradeStatus.PENDING,
        tax_savings_estimate=opportunity.estimated_tax_savings
    )
    
    # Save to database
    _save_trade_instruction(sell_trade)
    _save_trade_instruction(buy_trade)
    _save_harvest_execution(execution)
    
    _log_execution_action(
        execution_id,
        "created",
        f"Created harvest execution for {opportunity.symbol}"
    )
    
    logger.info(f"Created harvest execution {execution_id}")
    
    return execution


# ==============================================================================
# EXECUTION WORKFLOW
# ==============================================================================

def approve_execution(
    execution_id: str,
    user: Optional[str] = None
) -> bool:
    """
    Approve harvest execution for submission.
    
    Args:
        execution_id: Execution ID
        user: User approving
    
    Returns:
        True if approved successfully
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Update status
    cursor.execute("""
        UPDATE harvest_executions
        SET status = ?
        WHERE execution_id = ?
    """, (TradeStatus.APPROVED.value, execution_id))
    
    cursor.execute("""
        UPDATE trade_instructions
        SET status = ?
        WHERE execution_id = ?
    """, (TradeStatus.APPROVED.value, execution_id))
    
    conn.commit()
    conn.close()
    
    _log_execution_action(
        execution_id,
        "approved",
        "Execution approved for submission",
        user
    )
    
    logger.info(f"Approved execution {execution_id}")
    
    return True


def cancel_execution(
    execution_id: str,
    reason: Optional[str] = None,
    user: Optional[str] = None
) -> bool:
    """
    Cancel harvest execution.
    
    Args:
        execution_id: Execution ID
        reason: Cancellation reason
        user: User cancelling
    
    Returns:
        True if cancelled successfully
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Update status
    cursor.execute("""
        UPDATE harvest_executions
        SET status = ?
        WHERE execution_id = ?
    """, (TradeStatus.CANCELLED.value, execution_id))
    
    cursor.execute("""
        UPDATE trade_instructions
        SET status = ?
        WHERE execution_id = ?
    """, (TradeStatus.CANCELLED.value, execution_id))
    
    conn.commit()
    conn.close()
    
    _log_execution_action(
        execution_id,
        "cancelled",
        reason or "Execution cancelled",
        user
    )
    
    logger.info(f"Cancelled execution {execution_id}")
    
    return True


def execute_sell_trade(
    trade_id: str,
    executed_price: float,
    executed_shares: float,
    lot_selection_method: LotSelectionMethod = LotSelectionMethod.HIFO,
    execution_notes: Optional[str] = None
) -> List[LotDisposition]:
    """
    Execute sell trade and update cost basis.
    
    Args:
        trade_id: Trade ID
        executed_price: Actual execution price
        executed_shares: Actual shares sold
        lot_selection_method: Method for selecting lots
        execution_notes: Notes about execution
    
    Returns:
        List of lot dispositions
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get trade details
    cursor.execute("""
        SELECT symbol, account_name, execution_id
        FROM trade_instructions
        WHERE trade_id = ?
    """, (trade_id,))
    
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Trade {trade_id} not found")
    
    symbol, account_name, execution_id = row
    
    # Execute sell in cost basis tracker
    dispositions = sell_shares(
        symbol=symbol,
        shares=executed_shares,
        sale_price=executed_price,
        sale_date=date.today(),
        account_name=account_name,
        method=lot_selection_method
    )
    
    # Update trade status
    cursor.execute("""
        UPDATE trade_instructions
        SET status = ?,
            executed_price = ?,
            executed_shares = ?,
            executed_at = ?,
            execution_notes = ?,
            lot_ids = ?
        WHERE trade_id = ?
    """, (
        TradeStatus.FILLED.value,
        executed_price,
        executed_shares,
        datetime.now().isoformat(),
        execution_notes,
        json.dumps([d.lot_id for d in dispositions]),
        trade_id
    ))
    
    conn.commit()
    conn.close()
    
    _log_execution_action(
        execution_id,
        "sell_executed",
        f"Sold {executed_shares} shares of {symbol} at ${executed_price:.2f}"
    )
    
    logger.info(f"Executed sell trade {trade_id}")
    
    return dispositions


def execute_buy_trade(
    trade_id: str,
    executed_price: float,
    executed_shares: float,
    execution_notes: Optional[str] = None
) -> TaxLot:
    """
    Execute buy trade and add to cost basis.
    
    Args:
        trade_id: Trade ID
        executed_price: Actual execution price
        executed_shares: Actual shares bought
        execution_notes: Notes about execution
    
    Returns:
        New tax lot
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get trade details
    cursor.execute("""
        SELECT symbol, account_name, account_type, execution_id
        FROM trade_instructions
        WHERE trade_id = ?
    """, (trade_id,))
    
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Trade {trade_id} not found")
    
    symbol, account_name, account_type, execution_id = row
    
    # Create new tax lot
    lot = TaxLot(
        lot_id=str(uuid.uuid4()),
        symbol=symbol,
        account_name=account_name,
        account_type=account_type,
        shares=executed_shares,
        purchase_price=executed_price,
        purchase_date=date.today(),
        cost_basis=executed_shares * executed_price,
        notes=execution_notes or f"Replacement purchase via trade {trade_id}"
    )
    
    add_tax_lot(lot)
    
    # Update trade status
    cursor.execute("""
        UPDATE trade_instructions
        SET status = ?,
            executed_price = ?,
            executed_shares = ?,
            executed_at = ?,
            execution_notes = ?,
            lot_ids = ?
        WHERE trade_id = ?
    """, (
        TradeStatus.FILLED.value,
        executed_price,
        executed_shares,
        datetime.now().isoformat(),
        execution_notes,
        json.dumps([lot.lot_id]),
        trade_id
    ))
    
    conn.commit()
    conn.close()
    
    _log_execution_action(
        execution_id,
        "buy_executed",
        f"Bought {executed_shares} shares of {symbol} at ${executed_price:.2f}"
    )
    
    logger.info(f"Executed buy trade {trade_id}")
    
    return lot


def complete_execution(execution_id: str) -> bool:
    """
    Mark execution as complete.
    
    Args:
        execution_id: Execution ID
    
    Returns:
        True if completed successfully
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE harvest_executions
        SET status = ?
        WHERE execution_id = ?
    """, (TradeStatus.FILLED.value, execution_id))
    
    conn.commit()
    conn.close()
    
    _log_execution_action(
        execution_id,
        "completed",
        "Execution completed successfully"
    )
    
    logger.info(f"Completed execution {execution_id}")
    
    return True


# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

def export_trade_instructions(
    execution_id: str,
    output_path: Optional[str] = None
) -> str:
    """
    Export trade instructions to CSV for manual execution.
    
    Args:
        execution_id: Execution ID
        output_path: Output file path
    
    Returns:
        Path to exported file
    """
    if output_path is None:
        output_path = f"data/trade_instructions_{execution_id}.csv"
    
    conn = sqlite3.connect(DB_PATH)
    
    df = pd.read_sql_query("""
        SELECT trade_type, symbol, shares, estimated_price, estimated_value,
               account_name, notes, status
        FROM trade_instructions
        WHERE execution_id = ?
        ORDER BY trade_type DESC
    """, conn, params=[execution_id])
    
    conn.close()
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    logger.info(f"Exported trade instructions to {output_path}")
    
    return output_path


def get_execution_status(execution_id: str) -> Dict:
    """
    Get execution status and details.
    
    Args:
        execution_id: Execution ID
    
    Returns:
        Dictionary with execution details
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get execution
    cursor.execute("""
        SELECT * FROM harvest_executions
        WHERE execution_id = ?
    """, (execution_id,))
    
    row = cursor.fetchone()
    if not row:
        return {}
    
    columns = [desc[0] for desc in cursor.description]
    execution = dict(zip(columns, row))
    
    # Get trades
    cursor.execute("""
        SELECT * FROM trade_instructions
        WHERE execution_id = ?
    """, (execution_id,))
    
    trades = []
    for row in cursor.fetchall():
        columns = [desc[0] for desc in cursor.description]
        trades.append(dict(zip(columns, row)))
    
    execution['trades'] = trades
    
    # Get audit log
    cursor.execute("""
        SELECT * FROM execution_audit_log
        WHERE execution_id = ?
        ORDER BY timestamp
    """, (execution_id,))
    
    audit_log = []
    for row in cursor.fetchall():
        columns = [desc[0] for desc in cursor.description]
        audit_log.append(dict(zip(columns, row)))
    
    execution['audit_log'] = audit_log
    
    conn.close()
    
    return execution


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Harvest Executor")
    print("=" * 60)
    
    # Initialize tables
    _init_execution_tables()
    print("Initialized execution tables")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

# Made with Bob
