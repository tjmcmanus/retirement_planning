"""
Harvest Approval Workflow
==========================
Persistent, structured approval workflow for direct-index harvest trades.

Lifecycle
---------
  scan → [HarvestOpportunity]
      → create_pending_trade()        # stores in DB with status PENDING
      → approve_pending_trade()       # PENDING → APPROVED
      → reject_pending_trade()        # PENDING → REJECTED
      → confirm_trade_executed()      # APPROVED → EXECUTED
                                        (writes realized loss to tax tracker)
      → revert_confirmation()         # EXECUTED → APPROVED  (undo mis-click)

All state lives in the ``pending_trades`` SQLite table so it survives page
reloads.  The harvest_executor module handles the *execution plan* objects
(HarvestExecution); this module handles the simpler, auditable *approval
record* that wraps around it.

Author: Bob
Date: April 2026
Version: 1.0
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/rsp_holdings.db")


# ==============================================================================
# ENUMS & DATACLASSES
# ==============================================================================

class ApprovalStatus(str, Enum):
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    EXECUTED  = "executed"    # user confirmed they did the trades
    CANCELLED = "cancelled"


@dataclass
class PendingTrade:
    """
    A harvest trade pair (sell + buy) awaiting manual approval.

    Fields
    ------
    trade_id:       UUID primary key.
    sell_symbol:    Ticker to sell.
    buy_symbol:     Ticker to buy as replacement.
    account_name:   Brokerage account name.
    shares:         Shares to sell.
    sell_price:     Estimated sell price per share.
    buy_price:      Estimated buy price per share.
    buy_shares:     Estimated shares to buy (sell_value / buy_price).
    estimated_loss: Realised loss amount (negative number).
    estimated_savings: Estimated tax savings.
    lot_method:     Cost-basis method requested (HIFO, FIFO, …).
    status:         Current approval status.
    created_at:     Creation timestamp.
    reviewed_at:    Timestamp of last status change.
    review_notes:   Free-text notes from approver / rejecter.
    execution_id:   Link to a harvest_executor HarvestExecution (optional).
    """
    trade_id: str
    sell_symbol: str
    buy_symbol: str
    account_name: str
    shares: float
    sell_price: float
    buy_price: float
    buy_shares: float
    estimated_loss: float
    estimated_savings: float
    lot_method: str
    status: ApprovalStatus
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    review_notes: str = ""
    execution_id: Optional[str] = None

    def sell_value(self) -> float:
        return self.shares * self.sell_price

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["created_at"] = self.created_at.isoformat()
        d["reviewed_at"] = self.reviewed_at.isoformat() if self.reviewed_at else None
        return d


# ==============================================================================
# DATABASE SETUP
# ==============================================================================

def _init_table() -> None:
    """Create the pending_trades table if it does not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_trades (
            trade_id         TEXT PRIMARY KEY,
            sell_symbol      TEXT NOT NULL,
            buy_symbol       TEXT NOT NULL,
            account_name     TEXT NOT NULL,
            shares           REAL NOT NULL,
            sell_price       REAL NOT NULL,
            buy_price        REAL NOT NULL,
            buy_shares       REAL NOT NULL,
            estimated_loss   REAL NOT NULL,
            estimated_savings REAL NOT NULL,
            lot_method       TEXT NOT NULL DEFAULT 'HIFO',
            status           TEXT NOT NULL DEFAULT 'pending',
            created_at       TEXT NOT NULL,
            reviewed_at      TEXT,
            review_notes     TEXT DEFAULT '',
            execution_id     TEXT
        )
    """)
    conn.commit()
    conn.close()


def _row_to_pending_trade(row: dict) -> PendingTrade:
    return PendingTrade(
        trade_id=row["trade_id"],
        sell_symbol=row["sell_symbol"],
        buy_symbol=row["buy_symbol"],
        account_name=row["account_name"],
        shares=float(row["shares"]),
        sell_price=float(row["sell_price"]),
        buy_price=float(row["buy_price"]),
        buy_shares=float(row["buy_shares"]),
        estimated_loss=float(row["estimated_loss"]),
        estimated_savings=float(row["estimated_savings"]),
        lot_method=row["lot_method"],
        status=ApprovalStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        reviewed_at=(
            datetime.fromisoformat(row["reviewed_at"])
            if row.get("reviewed_at")
            else None
        ),
        review_notes=row.get("review_notes") or "",
        execution_id=row.get("execution_id"),
    )


def _save(trade: PendingTrade) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT OR REPLACE INTO pending_trades
        (trade_id, sell_symbol, buy_symbol, account_name, shares,
         sell_price, buy_price, buy_shares, estimated_loss,
         estimated_savings, lot_method, status, created_at,
         reviewed_at, review_notes, execution_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            trade.trade_id,
            trade.sell_symbol,
            trade.buy_symbol,
            trade.account_name,
            trade.shares,
            trade.sell_price,
            trade.buy_price,
            trade.buy_shares,
            trade.estimated_loss,
            trade.estimated_savings,
            trade.lot_method,
            trade.status.value,
            trade.created_at.isoformat(),
            trade.reviewed_at.isoformat() if trade.reviewed_at else None,
            trade.review_notes,
            trade.execution_id,
        ),
    )
    conn.commit()
    conn.close()


# ==============================================================================
# PUBLIC API
# ==============================================================================

def create_pending_trade(
    sell_symbol: str,
    buy_symbol: str,
    account_name: str,
    shares: float,
    sell_price: float,
    buy_price: float,
    estimated_loss: float,
    estimated_savings: float,
    lot_method: str = "HIFO",
    execution_id: Optional[str] = None,
) -> PendingTrade:
    """
    Create and persist a new pending harvest trade record.

    Returns the saved ``PendingTrade``.
    """
    _init_table()

    buy_shares = (shares * sell_price / buy_price) if buy_price > 0 else 0.0

    trade = PendingTrade(
        trade_id=str(uuid.uuid4()),
        sell_symbol=sell_symbol,
        buy_symbol=buy_symbol,
        account_name=account_name,
        shares=shares,
        sell_price=sell_price,
        buy_price=buy_price,
        buy_shares=buy_shares,
        estimated_loss=estimated_loss,
        estimated_savings=estimated_savings,
        lot_method=lot_method,
        status=ApprovalStatus.PENDING,
        created_at=datetime.now(),
        execution_id=execution_id,
    )
    _save(trade)
    logger.info(f"Created pending trade {trade.trade_id[:8]} ({sell_symbol} → {buy_symbol})")
    return trade


def get_pending_trades(
    status: Optional[ApprovalStatus] = None,
    account_name: Optional[str] = None,
) -> List[PendingTrade]:
    """
    Retrieve pending trade records from the DB.

    Parameters
    ----------
    status:
        Filter to a specific status.  ``None`` returns all statuses.
    account_name:
        Filter to a specific account.  ``None`` returns all accounts.
    """
    _init_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    clauses: List[str] = []
    params: List = []

    if status is not None:
        clauses.append("status = ?")
        params.append(status.value)
    if account_name is not None:
        clauses.append("account_name = ?")
        params.append(account_name)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM pending_trades {where} ORDER BY created_at DESC",
        params,
    ).fetchall()
    conn.close()

    return [_row_to_pending_trade(dict(r)) for r in rows]


def get_pending_trade(trade_id: str) -> Optional[PendingTrade]:
    """Fetch a single pending trade by ID, or None if not found."""
    _init_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM pending_trades WHERE trade_id = ?", (trade_id,)
    ).fetchone()
    conn.close()
    return _row_to_pending_trade(dict(row)) if row else None


def approve_pending_trade(
    trade_id: str,
    notes: str = "",
) -> PendingTrade:
    """
    Approve a PENDING trade.  Moves status to APPROVED.

    Raises
    ------
    ValueError
        If the trade does not exist or is not in PENDING status.
    """
    trade = get_pending_trade(trade_id)
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found")
    if trade.status != ApprovalStatus.PENDING:
        raise ValueError(
            f"Cannot approve trade in status {trade.status.value!r}. "
            "Only PENDING trades can be approved."
        )

    trade.status = ApprovalStatus.APPROVED
    trade.reviewed_at = datetime.now()
    trade.review_notes = notes
    _save(trade)
    logger.info(f"Approved trade {trade_id[:8]} ({trade.sell_symbol} → {trade.buy_symbol})")
    return trade


def reject_pending_trade(
    trade_id: str,
    reason: str = "",
) -> PendingTrade:
    """
    Reject a PENDING trade.  Moves status to REJECTED.

    Raises
    ------
    ValueError
        If the trade is not in PENDING status.
    """
    trade = get_pending_trade(trade_id)
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found")
    if trade.status != ApprovalStatus.PENDING:
        raise ValueError(
            f"Cannot reject trade in status {trade.status.value!r}. "
            "Only PENDING trades can be rejected."
        )

    trade.status = ApprovalStatus.REJECTED
    trade.reviewed_at = datetime.now()
    trade.review_notes = reason
    _save(trade)
    logger.info(f"Rejected trade {trade_id[:8]}: {reason}")
    return trade


def confirm_trade_executed(
    trade_id: str,
    actual_sell_price: Optional[float] = None,
    actual_buy_price: Optional[float] = None,
    notes: str = "",
) -> PendingTrade:
    """
    Confirm that an APPROVED trade was manually executed in Schwab.

    This moves the status to EXECUTED and, if possible, records the
    realized loss in the tax_savings_tracker.

    Parameters
    ----------
    trade_id:
        The pending trade to confirm.
    actual_sell_price / actual_buy_price:
        Actual fill prices.  When provided, they replace the estimates for
        tax-savings recording.
    notes:
        Optional confirmation notes (e.g. order ID).
    """
    trade = get_pending_trade(trade_id)
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found")
    if trade.status != ApprovalStatus.APPROVED:
        raise ValueError(
            f"Cannot confirm trade in status {trade.status.value!r}. "
            "Only APPROVED trades can be confirmed."
        )

    sell_price = actual_sell_price or trade.sell_price
    buy_price  = actual_buy_price  or trade.buy_price

    # Record realized loss directly in the tax_savings table.
    # record_harvest_savings() requires LotDisposition objects (created by the
    # automated sell path) which we don't have for manually executed trades, so
    # we insert a minimal record via a direct DB write instead.
    try:
        _record_manual_savings(trade, sell_price)
        logger.info(
            f"Recorded tax savings for trade {trade_id[:8]}: "
            f"${trade.estimated_savings:,.2f}"
        )
    except Exception as exc:
        # Non-fatal — confirmation still succeeds even if savings tracking fails
        logger.warning(f"Could not record tax savings for {trade_id[:8]}: {exc}")

    trade.status = ApprovalStatus.EXECUTED
    trade.reviewed_at = datetime.now()
    trade.review_notes = (
        f"Executed — sell @ ${sell_price:.2f}, buy @ ${buy_price:.2f}. {notes}"
    ).strip()
    _save(trade)

    # Keep the linked HarvestExecution in sync — mark it as filled too.
    if trade.execution_id:
        try:
            from components.harvest_executor import complete_execution
            complete_execution(trade.execution_id)
        except Exception as exc:
            logger.warning(
                f"Could not mark HarvestExecution {trade.execution_id[:8]} as filled: {exc}"
            )

    logger.info(f"Confirmed execution of trade {trade_id[:8]}")
    return trade


def revert_confirmation(trade_id: str, reason: str = "") -> PendingTrade:
    """
    Revert an EXECUTED trade back to APPROVED (undo a mis-click).

    Does NOT undo any tax_savings_tracker entries.
    """
    trade = get_pending_trade(trade_id)
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found")
    if trade.status != ApprovalStatus.EXECUTED:
        raise ValueError(
            f"Cannot revert trade in status {trade.status.value!r}. "
            "Only EXECUTED trades can be reverted."
        )

    trade.status = ApprovalStatus.APPROVED
    trade.reviewed_at = datetime.now()
    trade.review_notes = f"Reverted: {reason}"
    _save(trade)
    logger.info(f"Reverted trade {trade_id[:8]} back to APPROVED")
    return trade


def cancel_pending_trade(trade_id: str, reason: str = "") -> PendingTrade:
    """Cancel a trade that is in PENDING or APPROVED status."""
    trade = get_pending_trade(trade_id)
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found")
    if trade.status not in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED):
        raise ValueError(
            f"Cannot cancel trade in status {trade.status.value!r}."
        )

    trade.status = ApprovalStatus.CANCELLED
    trade.reviewed_at = datetime.now()
    trade.review_notes = reason or "Cancelled by user"
    _save(trade)
    logger.info(f"Cancelled trade {trade_id[:8]}: {reason}")
    return trade


def _record_manual_savings(trade: PendingTrade, sell_price: float) -> None:
    """
    Insert a minimal tax-savings row for a manually confirmed trade.

    This bypasses ``record_harvest_savings()`` which requires ``LotDisposition``
    objects only available in the automated execution path.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        # Ensure the savings table exists (init is idempotent)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tax_savings (
                record_id          TEXT PRIMARY KEY,
                execution_id       TEXT,
                harvest_date       TEXT NOT NULL,
                tax_year           INTEGER NOT NULL,
                symbol_sold        TEXT NOT NULL,
                symbol_bought      TEXT NOT NULL,
                shares             REAL NOT NULL,
                purchase_price     REAL NOT NULL,
                sell_price         REAL NOT NULL,
                realized_loss      REAL NOT NULL,
                estimated_tax_savings REAL NOT NULL,
                actual_tax_savings REAL DEFAULT 0,
                is_long_term       INTEGER NOT NULL DEFAULT 0,
                account_name       TEXT NOT NULL,
                account_type       TEXT NOT NULL DEFAULT 'Brokerage',
                lot_method         TEXT NOT NULL DEFAULT 'HIFO',
                notes              TEXT DEFAULT ''
            )
        """)
        now = date.today()
        conn.execute(
            """
            INSERT OR IGNORE INTO tax_savings
            (record_id, execution_id, harvest_date, tax_year, symbol_sold,
             symbol_bought, shares, purchase_price, sell_price, realized_loss,
             estimated_tax_savings, actual_tax_savings, is_long_term,
             account_name, account_type, lot_method, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f"manual_{trade.trade_id}",
                trade.execution_id,
                now.isoformat(),
                now.year,
                trade.sell_symbol,
                trade.buy_symbol,
                trade.shares,
                trade.sell_price,
                sell_price,
                trade.estimated_loss,
                trade.estimated_savings,
                0.0,
                0,                          # unknown term for manual trades
                trade.account_name,
                "Brokerage",
                trade.lot_method,
                f"Manual confirmation — pending trade {trade.trade_id[:8]}",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_approval_summary(account_name: Optional[str] = None) -> Dict:
    """
    Return a summary dict of pending-trade counts and estimated savings.

    Useful for a dashboard KPI tile.
    """
    all_trades = get_pending_trades(account_name=account_name)

    summary: Dict = {
        "total": len(all_trades),
        "pending": 0,
        "approved": 0,
        "executed": 0,
        "rejected": 0,
        "cancelled": 0,
        "pending_savings": 0.0,
        "executed_savings": 0.0,
    }
    for t in all_trades:
        key = t.status.value
        if key in summary:
            summary[key] += 1
        if t.status == ApprovalStatus.PENDING:
            summary["pending_savings"] += t.estimated_savings
        elif t.status == ApprovalStatus.EXECUTED:
            summary["executed_savings"] += t.estimated_savings

    return summary
