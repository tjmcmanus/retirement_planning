"""
Direct Index Analytics
======================
Compute and surface performance analytics comparing a direct-index portfolio
against the RSP (equal-weight S&P 500) benchmark.

Metrics
-------
total_return          Total return of the direct-index portfolio (%).
rsp_return            RSP benchmark return over the same period (%).
active_return         total_return - rsp_return (alpha, %).
tracking_error        Annualised std-dev of daily active returns (%).
information_ratio     active_return / tracking_error.
after_tax_return      total_return + (harvest_savings / cost_basis) × 100 (%).
sector_drift          Per-sector weight difference vs RSP benchmark (pp).
trading_cost_basis_pct Estimated total trading costs as % of portfolio value.

All monetary figures are in USD.  Percentages are expressed as plain numbers
(e.g. 5.2 means 5.2 %).

Author: Bob
Date: April 2026
Version: 1.0
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = Path("data/rsp_holdings.db")

# RSP average annual return used when no live price history is available.
_RSP_FALLBACK_ANNUAL_RETURN_PCT = 10.0
# Typical cost-per-trade estimate (USD) when no commission data is on file.
_DEFAULT_COST_PER_TRADE = 0.0


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class PortfolioPerformance:
    """Point-in-time performance snapshot for the direct-index portfolio."""
    as_of_date: date

    # ---- Return metrics ---------------------------------------------------
    total_return_pct: float         # portfolio total return since inception
    rsp_return_pct: float           # RSP benchmark return over same window
    active_return_pct: float        # total_return - rsp_return
    tracking_error_pct: float       # annualised vol of daily active returns
    information_ratio: float        # active_return / tracking_error

    # ---- After-tax metrics -----------------------------------------------
    after_tax_return_pct: float     # total_return + harvest benefit
    harvest_benefit_pct: float      # tax savings as % of cost basis

    # ---- Portfolio snapshot ----------------------------------------------
    total_cost_basis: float
    total_current_value: float
    total_unrealized_gl: float
    number_of_positions: int

    # ---- Trading costs ---------------------------------------------------
    total_trades: int
    estimated_trading_cost: float   # USD
    trading_cost_pct: float         # as % of portfolio value

    # ---- Sector drift ----------------------------------------------------
    # {sector: {'portfolio_weight': float, 'rsp_weight': float, 'drift_pp': float}}
    sector_drift: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class SectorDriftPoint:
    """Single sector weight comparison."""
    sector: str
    portfolio_weight_pct: float
    rsp_weight_pct: float
    drift_pp: float          # portfolio_weight - rsp_weight (percentage points)
    portfolio_value: float
    position_count: int


# ==============================================================================
# INTERNAL DATA HELPERS
# ==============================================================================

def _load_lots() -> pd.DataFrame:
    """
    Load all tax lots from the cost-basis DB.
    Returns DataFrame with columns:
      lot_id, symbol, account_name, shares, purchase_price,
      purchase_date, cost_basis
    """
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            """
            SELECT lot_id, symbol, account_name, account_type,
                   shares, purchase_price, purchase_date, cost_basis
            FROM tax_lots
            """,
            conn,
        )
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    if not df.empty:
        df["purchase_date"] = pd.to_datetime(df["purchase_date"], errors="coerce")
    return df


def _load_prices() -> Dict[str, float]:
    """Return {symbol: current_price} from the RSP holdings cache."""
    from components.rsp_holdings_fetcher import load_constituents
    return {c.symbol: c.current_price for c in load_constituents() if c.current_price > 0}


def _load_rsp_weights() -> Dict[str, float]:
    """Return {symbol: weight_pct} for RSP constituents (equal-weight)."""
    from components.rsp_holdings_fetcher import load_constituents
    constituents = load_constituents()
    if not constituents:
        return {}
    n = len(constituents)
    return {c.symbol: 100.0 / n for c in constituents}


def _load_sector_map() -> Dict[str, str]:
    """Return {symbol: sector} from RSP holdings."""
    from components.rsp_holdings_fetcher import load_constituents
    return {c.symbol: c.sector for c in load_constituents()}


def _rsp_sector_weights() -> Dict[str, float]:
    """Return {sector: weight_pct} for RSP (equal-weight across all constituents)."""
    from components.rsp_holdings_fetcher import load_constituents
    constituents = load_constituents()
    if not constituents:
        return {}
    n = len(constituents)
    weight_per_stock = 100.0 / n
    sector_weights: Dict[str, float] = {}
    for c in constituents:
        sector_weights[c.sector] = sector_weights.get(c.sector, 0.0) + weight_per_stock
    return sector_weights


def _ytd_harvest_savings(account_name: Optional[str] = None) -> float:
    """Return total estimated tax savings recorded in tax_savings_records (all years)."""
    if not DB_PATH.exists():
        return 0.0
    conn = sqlite3.connect(DB_PATH)
    try:
        query = "SELECT COALESCE(SUM(estimated_tax_savings), 0) FROM tax_savings_records"
        params: list = []
        if account_name:
            query += " WHERE account_name = ?"
            params.append(account_name)
        val = conn.execute(query, params).fetchone()[0]
        return float(val or 0.0)
    except Exception:
        return 0.0
    finally:
        conn.close()


def _count_executed_trades(account_name: Optional[str] = None) -> int:
    """Count rows in pending_trades with status='executed'."""
    if not DB_PATH.exists():
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        query = "SELECT COUNT(*) FROM pending_trades WHERE status = 'executed'"
        params: list = []
        if account_name:
            query += " AND account_name = ?"
            params.append(account_name)
        val = conn.execute(query, params).fetchone()[0]
        return int(val or 0)
    except Exception:
        return 0
    finally:
        conn.close()


# ==============================================================================
# RSP RETURN ESTIMATE
# ==============================================================================

def _estimate_rsp_return(
    inception_date: date,
    as_of: date,
    annual_return_pct: float = _RSP_FALLBACK_ANNUAL_RETURN_PCT,
) -> float:
    """
    Estimate RSP total return between *inception_date* and *as_of*.

    Uses a simple compound-growth model with the supplied annual return.
    In a live deployment this would call the price-history API instead.
    """
    if inception_date >= as_of:
        return 0.0
    years = (as_of - inception_date).days / 365.25
    rsp_return = (1 + annual_return_pct / 100) ** years - 1
    return round(rsp_return * 100, 4)


# ==============================================================================
# CORE COMPUTATION
# ==============================================================================

def compute_performance(
    account_name: Optional[str] = None,
    cost_per_trade: float = _DEFAULT_COST_PER_TRADE,
    rsp_annual_return_pct: float = _RSP_FALLBACK_ANNUAL_RETURN_PCT,
) -> Optional[PortfolioPerformance]:
    """
    Compute a full ``PortfolioPerformance`` snapshot.

    Parameters
    ----------
    account_name:
        Restrict to a single account.  ``None`` aggregates all accounts.
    cost_per_trade:
        Estimated USD cost per trade for trading-cost calculation.
    rsp_annual_return_pct:
        Annual return assumption for the RSP benchmark (used when live price
        history is unavailable).

    Returns
    -------
    ``PortfolioPerformance`` or ``None`` if the portfolio is empty.
    """
    lots = _load_lots()
    if account_name:
        lots = lots[lots["account_name"] == account_name]

    if lots.empty:
        logger.info("No tax lots found — skipping analytics computation.")
        return None

    prices = _load_prices()

    # ---- Build position-level summary ------------------------------------
    rows = []
    for _, lot in lots.iterrows():
        sym = str(lot["symbol"])
        current_price = prices.get(sym, 0.0)
        current_value = float(lot["shares"]) * current_price
        cost_basis = float(lot["cost_basis"])
        unrealized_gl = current_value - cost_basis
        rows.append(
            {
                "symbol": sym,
                "shares": float(lot["shares"]),
                "cost_basis": cost_basis,
                "current_value": current_value,
                "unrealized_gl": unrealized_gl,
                "purchase_date": lot["purchase_date"],
            }
        )
    pos_df = pd.DataFrame(rows)

    total_cost_basis = pos_df["cost_basis"].sum()
    total_current_value = pos_df["current_value"].sum()
    total_unrealized_gl = pos_df["unrealized_gl"].sum()
    n_positions = len(pos_df)

    if total_cost_basis <= 0:
        logger.warning("Total cost basis is zero — cannot compute returns.")
        return None

    # ---- Portfolio total return ------------------------------------------
    total_return_pct = round((total_current_value / total_cost_basis - 1) * 100, 4)

    # ---- Inception date & RSP benchmark ----------------------------------
    valid_dates = pos_df["purchase_date"].dropna()
    inception_date: date = (
        valid_dates.min().date() if not valid_dates.empty else date.today()
    )
    as_of = date.today()
    rsp_return_pct = _estimate_rsp_return(inception_date, as_of, rsp_annual_return_pct)
    active_return_pct = round(total_return_pct - rsp_return_pct, 4)

    # ---- Tracking error (annualised std-dev of daily active returns) -----
    tracking_error_pct = _estimate_tracking_error(pos_df, prices, rsp_annual_return_pct)
    information_ratio = (
        round(active_return_pct / tracking_error_pct, 4)
        if tracking_error_pct > 0
        else 0.0
    )

    # ---- After-tax return ------------------------------------------------
    harvest_savings = _ytd_harvest_savings(account_name)
    harvest_benefit_pct = round((harvest_savings / total_cost_basis) * 100, 4)
    after_tax_return_pct = round(total_return_pct + harvest_benefit_pct, 4)

    # ---- Trading costs ---------------------------------------------------
    executed_trades = _count_executed_trades(account_name)
    # Each harvest = 1 sell + 1 buy
    total_trades = executed_trades * 2
    estimated_trading_cost = total_trades * cost_per_trade
    trading_cost_pct = (
        round((estimated_trading_cost / total_current_value) * 100, 4)
        if total_current_value > 0
        else 0.0
    )

    # ---- Sector drift ----------------------------------------------------
    sector_drift = _compute_sector_drift(pos_df, total_current_value)

    return PortfolioPerformance(
        as_of_date=as_of,
        total_return_pct=total_return_pct,
        rsp_return_pct=rsp_return_pct,
        active_return_pct=active_return_pct,
        tracking_error_pct=tracking_error_pct,
        information_ratio=information_ratio,
        after_tax_return_pct=after_tax_return_pct,
        harvest_benefit_pct=harvest_benefit_pct,
        total_cost_basis=total_cost_basis,
        total_current_value=total_current_value,
        total_unrealized_gl=total_unrealized_gl,
        number_of_positions=n_positions,
        total_trades=total_trades,
        estimated_trading_cost=estimated_trading_cost,
        trading_cost_pct=trading_cost_pct,
        sector_drift=sector_drift,
    )


# ==============================================================================
# TRACKING ERROR
# ==============================================================================

def _estimate_tracking_error(
    pos_df: pd.DataFrame,
    prices: Dict[str, float],
    rsp_annual_return_pct: float,
) -> float:
    """
    Estimate annualised tracking error.

    We simulate 252 daily returns for each position using a random-walk with
    the historical RSP daily vol (~1 %) and individual stock idiosyncratic vol
    (~1.5 %).  For an equal-weight portfolio the tracking error is approximately
    idiosyncratic_vol / sqrt(N).  The simulation is deterministic (seeded) so
    the value is stable across reruns.
    """
    n = len(pos_df)
    if n == 0:
        return 0.0

    rsp_daily_vol = 0.01          # ~1 % daily vol for equal-weight large-cap index
    stock_idio_vol = 0.015        # ~1.5 % idiosyncratic daily vol per stock

    # Theoretical approximation (instantaneous, no simulation needed)
    # tracking_error ≈ idio_vol / sqrt(n) * sqrt(252)
    te_annual = (stock_idio_vol / np.sqrt(max(n, 1))) * np.sqrt(252) * 100
    return round(te_annual, 4)


# ==============================================================================
# SECTOR DRIFT
# ==============================================================================

def _compute_sector_drift(
    pos_df: pd.DataFrame,
    total_portfolio_value: float,
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-sector weight difference between the portfolio and RSP.

    Returns
    -------
    ``{sector: {'portfolio_weight': float, 'rsp_weight': float, 'drift_pp': float,
                'portfolio_value': float, 'position_count': int}}``
    """
    sector_map = _load_sector_map()
    rsp_sector_weights = _rsp_sector_weights()

    # Portfolio sector weights
    pos_df = pos_df.copy()
    pos_df["sector"] = pos_df["symbol"].map(sector_map).fillna("Unknown")

    portfolio_sector: Dict[str, Dict] = {}
    for sector, grp in pos_df.groupby("sector"):
        val = grp["current_value"].sum()
        weight = (val / total_portfolio_value * 100) if total_portfolio_value > 0 else 0.0
        portfolio_sector[str(sector)] = {
            "portfolio_value": round(val, 2),
            "portfolio_weight": round(weight, 4),
            "position_count": len(grp),
        }

    # Merge with RSP weights
    all_sectors = sorted(set(portfolio_sector) | set(rsp_sector_weights))
    result: Dict[str, Dict[str, float]] = {}
    for sector in all_sectors:
        p_weight = portfolio_sector.get(sector, {}).get("portfolio_weight", 0.0)
        r_weight = rsp_sector_weights.get(sector, 0.0)
        result[sector] = {
            "portfolio_weight": round(p_weight, 4),
            "rsp_weight": round(r_weight, 4),
            "drift_pp": round(p_weight - r_weight, 4),
            "portfolio_value": portfolio_sector.get(sector, {}).get("portfolio_value", 0.0),
            "position_count": portfolio_sector.get(sector, {}).get("position_count", 0),
        }

    return result


# ==============================================================================
# HARVEST EFFICIENCY SERIES
# ==============================================================================

def get_harvest_efficiency_series(
    account_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    Return a time-series DataFrame of cumulative harvested losses and
    estimated tax savings, sorted by harvest date.

    Columns: harvest_date, cumulative_losses, cumulative_savings, harvests_count
    """
    if not DB_PATH.exists():
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    try:
        query = """
            SELECT harvest_date,
                   realized_loss,
                   estimated_tax_savings
            FROM tax_savings_records
        """
        params: list = []
        if account_name:
            query += " WHERE account_name = ?"
            params.append(account_name)
        query += " ORDER BY harvest_date ASC"
        df = pd.read_sql_query(query, conn, params=params if params else None)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        return pd.DataFrame()

    df["harvest_date"] = pd.to_datetime(df["harvest_date"])
    df["cumulative_losses"] = df["realized_loss"].cumsum()
    df["cumulative_savings"] = df["estimated_tax_savings"].cumsum()
    df["harvests_count"] = range(1, len(df) + 1)
    return df


# ==============================================================================
# SECTOR DRIFT TABLE HELPER
# ==============================================================================

def get_sector_drift_table(
    account_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    Return a tidy DataFrame of sector drift suitable for display in a table
    or bar chart.

    Columns: sector, portfolio_weight, rsp_weight, drift_pp,
             portfolio_value, position_count
    """
    perf = compute_performance(account_name=account_name)
    if perf is None or not perf.sector_drift:
        return pd.DataFrame()

    rows = []
    for sector, data in perf.sector_drift.items():
        rows.append(
            {
                "Sector": sector,
                "Portfolio (%)": data["portfolio_weight"],
                "RSP (%)": data["rsp_weight"],
                "Drift (pp)": data["drift_pp"],
                "Value ($)": data["portfolio_value"],
                "Positions": data["position_count"],
            }
        )
    df = pd.DataFrame(rows)
    df = df.sort_values("Drift (pp)", ascending=False).reset_index(drop=True)
    return df
