"""
portfolio_analytics.py
======================
Portfolio performance analytics module providing:
- Time-weighted returns (TWR)
- Money-weighted returns (MWR/IRR)
- Risk-adjusted metrics (Sharpe, Sortino ratios)
- Drawdown analysis
- Contribution vs. growth attribution
- Benchmark comparison

Author: Financial Planner Team
Date: March 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes for Analytics Results
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Container for portfolio performance metrics."""
    
    # Returns
    time_weighted_return: float  # Annualized TWR
    money_weighted_return: float  # Annualized MWR (IRR)
    total_return_pct: float  # Total return percentage
    
    # Risk metrics
    volatility: float  # Annualized standard deviation
    sharpe_ratio: float  # Risk-adjusted return
    sortino_ratio: float  # Downside risk-adjusted return
    
    # Drawdown metrics
    max_drawdown_pct: float  # Maximum peak-to-trough decline
    max_drawdown_start: Optional[datetime]
    max_drawdown_end: Optional[datetime]
    current_drawdown_pct: float
    recovery_days: Optional[int]  # Days to recover from max drawdown
    
    # Attribution
    total_contributions: float
    total_withdrawals: float
    investment_growth: float  # Growth from market returns
    net_cash_flow: float
    
    # Benchmark comparison
    benchmark_return: Optional[float] = None
    alpha: Optional[float] = None  # Excess return vs benchmark
    beta: Optional[float] = None  # Sensitivity to benchmark
    
    # Period info
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    num_periods: int = 0


@dataclass
class DrawdownPeriod:
    """Information about a specific drawdown period."""
    
    start_date: datetime
    trough_date: datetime
    end_date: Optional[datetime]  # None if not recovered
    peak_value: float
    trough_value: float
    drawdown_pct: float
    recovery_days: Optional[int]
    duration_days: int


# =============================================================================
# Time-Weighted Return (TWR) Calculation
# =============================================================================

def calculate_time_weighted_return(
    portfolio_values: pd.Series,
    cash_flows: Optional[pd.Series] = None,
    annualize: bool = True,
) -> float:
    """
    Calculate time-weighted return (TWR).
    
    TWR measures the compound rate of growth in a portfolio, eliminating the
    distorting effects of cash flows (contributions/withdrawals).
    
    Args:
        portfolio_values: Series of portfolio values indexed by date
        cash_flows: Series of cash flows (positive=contribution, negative=withdrawal)
                   If None, assumes no cash flows
        annualize: If True, return annualized rate; otherwise return total return
    
    Returns:
        Annualized or total time-weighted return as a decimal (e.g., 0.07 = 7%)
    """
    if portfolio_values.empty or len(portfolio_values) < 2:
        return 0.0
    
    # Sort by date
    portfolio_values = portfolio_values.sort_index()
    
    if cash_flows is None or cash_flows.empty:
        # Simple case: no cash flows
        start_value = float(portfolio_values.iloc[0])
        end_value = float(portfolio_values.iloc[-1])
        
        if start_value <= 0:
            return 0.0
        
        total_return = (end_value / start_value) - 1.0
        
        if not annualize:
            return total_return
        
        # Annualize based on time period
        start_dt = pd.Timestamp(portfolio_values.index[0])
        end_dt = pd.Timestamp(portfolio_values.index[-1])
        days = (end_dt - start_dt).days
        if days <= 0:
            return 0.0
        
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1 / years) - 1
        return annualized_return
    
    # Complex case: with cash flows
    # Calculate sub-period returns between cash flows
    cash_flows = cash_flows.sort_index()
    
    # Combine dates and ensure we have start and end
    all_dates = sorted(set(portfolio_values.index) | set(cash_flows.index))
    
    sub_returns = []
    for i in range(len(all_dates) - 1):
        date1 = all_dates[i]
        date2 = all_dates[i + 1]
        
        # Get values at boundaries
        val1 = portfolio_values.loc[date1] if date1 in portfolio_values.index else portfolio_values.asof(date1)
        val2 = portfolio_values.loc[date2] if date2 in portfolio_values.index else portfolio_values.asof(date2)
        
        # Adjust for cash flow at start of period
        if date1 in cash_flows.index:
            val1 += cash_flows.loc[date1]
        
        if val1 > 0:
            period_return = (val2 / val1) - 1.0
            sub_returns.append(1 + period_return)
    
    if not sub_returns:
        return 0.0
    
    # Chain the sub-period returns
    total_return = np.prod(sub_returns) - 1.0
    
    if not annualize:
        return total_return
    
    # Annualize
    start_dt = pd.Timestamp(all_dates[0])
    end_dt = pd.Timestamp(all_dates[-1])
    days = (end_dt - start_dt).days
    if days <= 0:
        return 0.0
    
    years = days / 365.25
    annualized_return = (1 + total_return) ** (1 / years) - 1
    return annualized_return


# =============================================================================
# Money-Weighted Return (MWR/IRR) Calculation
# =============================================================================

def calculate_money_weighted_return(
    portfolio_values: pd.Series,
    cash_flows: pd.Series,
    annualize: bool = True,
) -> float:
    """
    Calculate money-weighted return (MWR), also known as Internal Rate of Return (IRR).
    
    MWR accounts for the timing and size of cash flows, showing the actual return
    experienced by the investor.
    
    Args:
        portfolio_values: Series of portfolio values indexed by date
        cash_flows: Series of cash flows (positive=contribution, negative=withdrawal)
        annualize: If True, return annualized rate
    
    Returns:
        Annualized or total money-weighted return as a decimal
    """
    if portfolio_values.empty or cash_flows.empty:
        return 0.0
    
    portfolio_values = portfolio_values.sort_index()
    cash_flows = cash_flows.sort_index()
    
    # Build cash flow array for IRR calculation
    # Start with initial investment (negative cash flow)
    start_date = pd.Timestamp(portfolio_values.index[0])
    end_date = pd.Timestamp(portfolio_values.index[-1])
    
    # Create array of cash flows with dates
    cf_dates = [start_date]
    cf_amounts = [-float(portfolio_values.iloc[0])]  # Initial investment
    
    # Add intermediate cash flows
    for date, amount in cash_flows.items():
        date_ts = pd.Timestamp(date)
        if start_date < date_ts <= end_date:
            cf_dates.append(date_ts)
            cf_amounts.append(-float(amount))  # Negative because contributions are outflows
    
    # Add final value (positive cash flow)
    cf_dates.append(end_date)
    cf_amounts.append(float(portfolio_values.iloc[-1]))
    
    # Calculate IRR using numpy
    try:
        # Convert dates to days from start
        days_from_start = [(pd.Timestamp(d) - start_date).days for d in cf_dates]
        
        # Use Newton's method to find IRR
        irr = _calculate_xirr(cf_amounts, days_from_start)
        
        if not annualize:
            # Convert to total return
            total_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
            total_return = (1 + irr) ** (total_days / 365.25) - 1
            return total_return
        
        return irr
    
    except Exception as e:
        logger.warning(f"Failed to calculate MWR: {e}")
        return 0.0


def _calculate_xirr(cash_flows: list[float], days: list[int], guess: float = 0.1) -> float:
    """
    Calculate XIRR (extended internal rate of return) using Newton's method.
    
    Args:
        cash_flows: List of cash flow amounts
        days: List of days from start date
        guess: Initial guess for IRR
    
    Returns:
        Annualized IRR
    """
    max_iterations = 100
    tolerance = 1e-6
    
    rate = guess
    
    for _ in range(max_iterations):
        # Calculate NPV and derivative
        npv = 0.0
        dnpv = 0.0
        
        for cf, day in zip(cash_flows, days):
            years = day / 365.25
            discount_factor = (1 + rate) ** years
            npv += cf / discount_factor
            dnpv -= cf * years / (discount_factor * (1 + rate))
        
        # Newton's method update
        if abs(dnpv) < 1e-10:
            break
        
        new_rate = rate - npv / dnpv
        
        if abs(new_rate - rate) < tolerance:
            return new_rate
        
        rate = new_rate
    
    return rate


# =============================================================================
# Risk Metrics
# =============================================================================

def calculate_volatility(returns: pd.Series, annualize: bool = True) -> float:
    """
    Calculate portfolio volatility (standard deviation of returns).
    
    Args:
        returns: Series of periodic returns
        annualize: If True, annualize the volatility
    
    Returns:
        Annualized or periodic volatility
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    
    std_dev = float(returns.std())
    
    if annualize:
        # Assume monthly returns, annualize by sqrt(12)
        std_dev *= np.sqrt(12)
    
    return std_dev


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.04,
    annualize: bool = True,
) -> float:
    """
    Calculate Sharpe ratio (risk-adjusted return).
    
    Sharpe Ratio = (Portfolio Return - Risk-Free Rate) / Portfolio Volatility
    
    Args:
        returns: Series of periodic returns
        risk_free_rate: Annual risk-free rate (default 4%)
        annualize: If True, calculate annualized Sharpe ratio
    
    Returns:
        Sharpe ratio
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    
    mean_return = float(returns.mean())
    std_dev = float(returns.std())
    
    if std_dev == 0:
        return 0.0
    
    if annualize:
        # Annualize mean and std dev
        mean_return *= 12
        std_dev *= np.sqrt(12)
        rf_rate = risk_free_rate
    else:
        # Convert annual risk-free rate to monthly
        rf_rate = (1 + risk_free_rate) ** (1/12) - 1
    
    sharpe = (mean_return - rf_rate) / std_dev
    return sharpe


def calculate_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.04,
    annualize: bool = True,
) -> float:
    """
    Calculate Sortino ratio (downside risk-adjusted return).
    
    Similar to Sharpe ratio but only considers downside volatility.
    
    Args:
        returns: Series of periodic returns
        risk_free_rate: Annual risk-free rate (default 4%)
        annualize: If True, calculate annualized Sortino ratio
    
    Returns:
        Sortino ratio
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    
    mean_return = float(returns.mean())
    
    # Calculate downside deviation (only negative returns)
    downside_returns = returns[returns < 0]
    
    if len(downside_returns) == 0:
        # No downside, return infinite (capped at 999)
        return 999.0
    
    downside_std = float(downside_returns.std())
    
    if downside_std == 0:
        return 999.0
    
    if annualize:
        mean_return *= 12
        downside_std *= np.sqrt(12)
        rf_rate = risk_free_rate
    else:
        rf_rate = (1 + risk_free_rate) ** (1/12) - 1
    
    sortino = (mean_return - rf_rate) / downside_std
    return sortino


# =============================================================================
# Drawdown Analysis
# =============================================================================

def calculate_drawdowns(portfolio_values: pd.Series) -> pd.DataFrame:
    """
    Calculate drawdown series for portfolio values.
    
    Args:
        portfolio_values: Series of portfolio values indexed by date
    
    Returns:
        DataFrame with columns: value, peak, drawdown, drawdown_pct
    """
    if portfolio_values.empty:
        return pd.DataFrame()
    
    df = pd.DataFrame({
        'value': portfolio_values,
        'peak': portfolio_values.expanding().max(),
    })
    
    df['drawdown'] = df['value'] - df['peak']
    df['drawdown_pct'] = (df['drawdown'] / df['peak']) * 100
    
    return df


def find_max_drawdown(portfolio_values: pd.Series) -> tuple[float, Optional[datetime], Optional[datetime], Optional[int]]:
    """
    Find maximum drawdown and recovery information.
    
    Args:
        portfolio_values: Series of portfolio values indexed by date
    
    Returns:
        Tuple of (max_drawdown_pct, start_date, end_date, recovery_days)
    """
    if portfolio_values.empty or len(portfolio_values) < 2:
        return 0.0, None, None, None
    
    dd_df = calculate_drawdowns(portfolio_values)
    
    # Find maximum drawdown
    max_dd_idx = dd_df['drawdown_pct'].idxmin()
    max_dd_pct = float(dd_df.loc[max_dd_idx, 'drawdown_pct'])
    
    # Find start of drawdown (last peak before max drawdown)
    peak_value = dd_df.loc[max_dd_idx, 'peak']
    start_candidates = dd_df[dd_df.index <= max_dd_idx]
    start_mask = start_candidates['value'] == peak_value
    start_idx = start_candidates[start_mask].index[-1]
    
    # Find recovery date (when value exceeds peak again)
    recovery_candidates = dd_df[dd_df.index > max_dd_idx]
    recovery_mask = recovery_candidates['value'] >= peak_value
    
    if recovery_mask.any():
        recovery_idx = recovery_candidates[recovery_mask].index[0]
        recovery_days = (pd.Timestamp(recovery_idx) - pd.Timestamp(max_dd_idx)).days
    else:
        recovery_idx = None
        recovery_days = None
    
    return max_dd_pct, start_idx, max_dd_idx, recovery_days  # type: ignore[return-value]


def find_all_drawdown_periods(
    portfolio_values: pd.Series,
    min_drawdown_pct: float = -5.0,
) -> list[DrawdownPeriod]:
    """
    Identify all significant drawdown periods.
    
    Args:
        portfolio_values: Series of portfolio values indexed by date
        min_drawdown_pct: Minimum drawdown percentage to include (e.g., -5.0 for 5% drops)
    
    Returns:
        List of DrawdownPeriod objects
    """
    if portfolio_values.empty:
        return []
    
    dd_df = calculate_drawdowns(portfolio_values)
    
    drawdown_periods = []
    in_drawdown = False
    current_peak = None
    current_peak_date = None
    
    for date, row in dd_df.iterrows():
        if not in_drawdown and row['drawdown_pct'] < 0:
            # Start of new drawdown
            in_drawdown = True
            current_peak = row['peak']
            current_peak_date = date
        
        elif in_drawdown and row['value'] >= current_peak:
            # Recovery - end of drawdown
            trough_idx = dd_df.loc[current_peak_date:date, 'drawdown_pct'].idxmin()
            trough_value = dd_df.loc[trough_idx, 'value']
            drawdown_pct = dd_df.loc[trough_idx, 'drawdown_pct']
            
            if drawdown_pct <= min_drawdown_pct:
                recovery_days = (pd.Timestamp(date) - pd.Timestamp(trough_idx)).days
                duration_days = (pd.Timestamp(date) - pd.Timestamp(current_peak_date)).days
                
                drawdown_periods.append(DrawdownPeriod(
                    start_date=pd.Timestamp(current_peak_date),  # type: ignore[arg-type]
                    trough_date=pd.Timestamp(trough_idx),  # type: ignore[arg-type]
                    end_date=pd.Timestamp(date),  # type: ignore[arg-type]
                    peak_value=float(current_peak),
                    trough_value=trough_value,
                    drawdown_pct=drawdown_pct,
                    recovery_days=recovery_days,
                    duration_days=duration_days,
                ))
            
            in_drawdown = False
            current_peak = None
            current_peak_date = None
    
    # Handle ongoing drawdown
    if in_drawdown:
        trough_idx = dd_df.loc[current_peak_date:, 'drawdown_pct'].idxmin()
        trough_value = dd_df.loc[trough_idx, 'value']
        drawdown_pct = dd_df.loc[trough_idx, 'drawdown_pct']
        
        if drawdown_pct <= min_drawdown_pct:
            duration_days = (pd.Timestamp(dd_df.index[-1]) - pd.Timestamp(current_peak_date)).days
            
            drawdown_periods.append(DrawdownPeriod(
                start_date=pd.Timestamp(current_peak_date),  # type: ignore[arg-type]
                trough_date=pd.Timestamp(trough_idx),  # type: ignore[arg-type]
                end_date=None,  # Not recovered yet
                peak_value=float(current_peak),
                trough_value=trough_value,
                drawdown_pct=drawdown_pct,
                recovery_days=None,
                duration_days=duration_days,
            ))
    
    return drawdown_periods


# =============================================================================
# Attribution Analysis
# =============================================================================

def calculate_attribution(
    portfolio_values: pd.Series,
    contributions: pd.Series,
    withdrawals: pd.Series,
) -> tuple[float, float, float]:
    """
    Calculate contribution vs. growth attribution.
    
    Args:
        portfolio_values: Series of portfolio values indexed by date
        contributions: Series of contribution amounts
        withdrawals: Series of withdrawal amounts
    
    Returns:
        Tuple of (total_contributions, total_withdrawals, investment_growth)
    """
    if portfolio_values.empty:
        return 0.0, 0.0, 0.0
    
    total_contributions = float(contributions.sum()) if not contributions.empty else 0.0
    total_withdrawals = float(withdrawals.sum()) if not withdrawals.empty else 0.0
    
    start_value = float(portfolio_values.iloc[0])
    end_value = float(portfolio_values.iloc[-1])
    
    # Investment growth = End Value - Start Value - Net Contributions
    net_contributions = total_contributions - total_withdrawals
    investment_growth = end_value - start_value - net_contributions
    
    return total_contributions, total_withdrawals, investment_growth


# =============================================================================
# Benchmark Comparison
# =============================================================================

@st.cache_data(ttl=3600)
def fetch_benchmark_data(
    benchmark_symbol: str,
    start_date: datetime,
    end_date: datetime,
) -> pd.Series:
    """
    Fetch benchmark price data from Yahoo Finance.
    
    Args:
        benchmark_symbol: Ticker symbol (e.g., '^GSPC' for S&P 500)
        start_date: Start date for data
        end_date: End date for data
    
    Returns:
        Series of adjusted close prices indexed by date
    """
    try:
        ticker = yf.Ticker(benchmark_symbol)
        hist = ticker.history(start=start_date, end=end_date)
        
        if hist.empty:
            logger.warning(f"No benchmark data found for {benchmark_symbol}")
            return pd.Series(dtype=float)
        
        return pd.Series(hist['Close'])
    
    except Exception as e:
        logger.error(f"Failed to fetch benchmark data for {benchmark_symbol}: {e}")
        return pd.Series(dtype=float)


def calculate_alpha_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.04,
) -> tuple[float, float]:
    """
    Calculate alpha and beta relative to a benchmark.
    
    Alpha: Excess return above what would be predicted by beta
    Beta: Sensitivity to benchmark movements
    
    Args:
        portfolio_returns: Series of portfolio returns
        benchmark_returns: Series of benchmark returns
        risk_free_rate: Annual risk-free rate
    
    Returns:
        Tuple of (alpha, beta)
    """
    if portfolio_returns.empty or benchmark_returns.empty:
        return 0.0, 1.0
    
    # Align the series
    aligned = pd.DataFrame({
        'portfolio': portfolio_returns,
        'benchmark': benchmark_returns,
    }).dropna()
    
    if len(aligned) < 2:
        return 0.0, 1.0
    
    # Calculate beta using covariance
    port_series = pd.Series(aligned['portfolio'])
    bench_series = pd.Series(aligned['benchmark'])
    covariance = port_series.cov(bench_series)
    benchmark_variance = bench_series.var()
    
    if benchmark_variance == 0:
        beta = 1.0
    else:
        beta = covariance / benchmark_variance
    
    # Calculate alpha
    portfolio_mean = aligned['portfolio'].mean() * 12  # Annualize
    benchmark_mean = aligned['benchmark'].mean() * 12  # Annualize
    
    alpha = portfolio_mean - (risk_free_rate + beta * (benchmark_mean - risk_free_rate))
    
    return alpha, beta


# =============================================================================
# Main Analytics Function
# =============================================================================

def calculate_portfolio_analytics(
    portfolio_values: pd.Series,
    contributions: Optional[pd.Series] = None,
    withdrawals: Optional[pd.Series] = None,
    benchmark_symbol: str = '^GSPC',
    risk_free_rate: float = 0.04,
) -> PerformanceMetrics:
    """
    Calculate comprehensive portfolio performance analytics.
    
    Args:
        portfolio_values: Series of portfolio values indexed by date
        contributions: Series of contribution amounts (optional)
        withdrawals: Series of withdrawal amounts (optional)
        benchmark_symbol: Benchmark ticker symbol (default: S&P 500)
        risk_free_rate: Annual risk-free rate (default: 4%)
    
    Returns:
        PerformanceMetrics object with all calculated metrics
    """
    if portfolio_values.empty or len(portfolio_values) < 2:
        return PerformanceMetrics(
            time_weighted_return=0.0,
            money_weighted_return=0.0,
            total_return_pct=0.0,
            volatility=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown_pct=0.0,
            max_drawdown_start=None,
            max_drawdown_end=None,
            current_drawdown_pct=0.0,
            recovery_days=None,
            total_contributions=0.0,
            total_withdrawals=0.0,
            investment_growth=0.0,
            net_cash_flow=0.0,
        )
    
    # Sort and prepare data
    portfolio_values = portfolio_values.sort_index()
    start_date = portfolio_values.index[0]
    end_date = portfolio_values.index[-1]
    
    # Calculate returns
    portfolio_returns = portfolio_values.pct_change().dropna()
    
    # Prepare cash flows
    if contributions is None:
        contributions = pd.Series(dtype=float)
    if withdrawals is None:
        withdrawals = pd.Series(dtype=float)
    
    cash_flows = contributions.subtract(withdrawals, fill_value=0.0)
    
    # Calculate TWR
    twr = calculate_time_weighted_return(portfolio_values, cash_flows, annualize=True)
    
    # Calculate MWR
    mwr = calculate_money_weighted_return(portfolio_values, cash_flows, annualize=True)
    
    # Total return
    total_return_pct = ((portfolio_values.iloc[-1] / portfolio_values.iloc[0]) - 1) * 100
    
    # Risk metrics
    volatility = calculate_volatility(portfolio_returns, annualize=True)
    sharpe = calculate_sharpe_ratio(portfolio_returns, risk_free_rate, annualize=True)
    sortino = calculate_sortino_ratio(portfolio_returns, risk_free_rate, annualize=True)
    
    # Drawdown analysis
    max_dd_pct, dd_start, dd_end, recovery_days = find_max_drawdown(portfolio_values)
    dd_df = calculate_drawdowns(portfolio_values)
    current_dd_pct = float(dd_df['drawdown_pct'].iloc[-1])
    
    # Attribution
    total_contrib, total_withdr, inv_growth = calculate_attribution(
        portfolio_values, contributions, withdrawals
    )
    net_cash_flow = total_contrib - total_withdr
    
    # Benchmark comparison
    benchmark_return = None
    alpha = None
    beta = None
    
    try:
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        benchmark_data = fetch_benchmark_data(benchmark_symbol, start_dt, end_dt)
        if not benchmark_data.empty:
            benchmark_returns = benchmark_data.pct_change().dropna()
            
            # Calculate benchmark return
            benchmark_return = calculate_time_weighted_return(
                benchmark_data, annualize=True
            )
            
            # Calculate alpha and beta
            alpha, beta = calculate_alpha_beta(
                portfolio_returns, benchmark_returns, risk_free_rate
            )
    except Exception as e:
        logger.warning(f"Failed to calculate benchmark metrics: {e}")
    
    return PerformanceMetrics(
        time_weighted_return=twr,
        money_weighted_return=mwr,
        total_return_pct=total_return_pct,
        volatility=volatility,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_start=dd_start,
        max_drawdown_end=dd_end,
        current_drawdown_pct=current_dd_pct,
        recovery_days=recovery_days,
        total_contributions=total_contrib,
        total_withdrawals=total_withdr,
        investment_growth=inv_growth,
        net_cash_flow=net_cash_flow,
        benchmark_return=benchmark_return,
        alpha=alpha,
        beta=beta,
        start_date=pd.Timestamp(start_date),
        end_date=pd.Timestamp(end_date),
        num_periods=len(portfolio_values),
    )

# Made with Bob
