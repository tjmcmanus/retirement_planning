"""
test_portfolio_analytics.py
============================
Comprehensive tests for portfolio_analytics module.

Tests cover:
- Time-weighted returns (TWR)
- Money-weighted returns (MWR/IRR)
- Risk metrics (Sharpe, Sortino, volatility)
- Drawdown analysis
- Attribution analysis
- Benchmark comparison
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytest

from portfolio_analytics import (
    calculate_time_weighted_return,
    calculate_money_weighted_return,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_drawdowns,
    find_max_drawdown,
    find_all_drawdown_periods,
    calculate_attribution,
    calculate_alpha_beta,
    calculate_portfolio_analytics,
)


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def simple_portfolio_values():
    """Simple portfolio with steady growth."""
    dates = pd.date_range(start='2024-01-01', periods=12, freq='ME')
    values = [100000 * (1.005 ** i) for i in range(12)]  # 0.5% monthly growth
    return pd.Series(values, index=dates)


@pytest.fixture
def volatile_portfolio_values():
    """Portfolio with significant volatility and drawdowns."""
    dates = pd.date_range(start='2024-01-01', periods=24, freq='ME')
    # Simulate market crash and recovery
    values = [
        100000, 102000, 104000, 106000, 108000, 110000,  # Growth
        105000, 100000, 95000, 90000, 85000, 80000,      # Crash (-27%)
        85000, 90000, 95000, 100000, 105000, 110000,     # Recovery
        115000, 120000, 125000, 130000, 135000, 140000,  # New highs
    ]
    return pd.Series(values, index=dates)


@pytest.fixture
def portfolio_with_contributions():
    """Portfolio with regular contributions."""
    dates = pd.date_range(start='2024-01-01', periods=12, freq='ME')
    contributions = pd.Series([5000] * 12, index=dates)
    contributions.iloc[0] = 0  # No contribution in first month
    return contributions


@pytest.fixture
def portfolio_with_withdrawals():
    """Portfolio with regular withdrawals."""
    dates = pd.date_range(start='2024-01-01', periods=12, freq='ME')
    withdrawals = pd.Series([2000] * 12, index=dates)
    withdrawals.iloc[0] = 0  # No withdrawal in first month
    return withdrawals


# =============================================================================
# Time-Weighted Return Tests
# =============================================================================

def test_twr_simple_growth(simple_portfolio_values):
    """Test TWR calculation with simple steady growth."""
    twr = calculate_time_weighted_return(simple_portfolio_values, annualize=False)
    
    # Expected: (final / initial) - 1
    expected = (simple_portfolio_values.iloc[-1] / simple_portfolio_values.iloc[0]) - 1
    assert abs(twr - expected) < 0.0001


def test_twr_annualized(simple_portfolio_values):
    """Test annualized TWR calculation."""
    twr_annual = calculate_time_weighted_return(simple_portfolio_values, annualize=True)
    
    # Should be approximately 6% annual (0.5% monthly * 12)
    assert 0.05 < twr_annual < 0.07


def test_twr_with_contributions(simple_portfolio_values, portfolio_with_contributions):
    """Test TWR with cash flows (should eliminate their effect)."""
    twr = calculate_time_weighted_return(
        simple_portfolio_values,
        cash_flows=portfolio_with_contributions,
        annualize=False
    )
    
    # TWR should be similar to no-contribution case
    twr_no_cf = calculate_time_weighted_return(simple_portfolio_values, annualize=False)
    assert abs(twr - twr_no_cf) < 0.05  # Within 5%


def test_twr_empty_series():
    """Test TWR with empty series."""
    empty = pd.Series(dtype=float)
    twr = calculate_time_weighted_return(empty)
    assert twr == 0.0


def test_twr_single_value():
    """Test TWR with single value."""
    single = pd.Series([100000], index=[datetime(2024, 1, 1)])
    twr = calculate_time_weighted_return(single)
    assert twr == 0.0


# =============================================================================
# Money-Weighted Return Tests
# =============================================================================

def test_mwr_no_cash_flows(simple_portfolio_values):
    """Test MWR without cash flows (should equal TWR)."""
    cash_flows = pd.Series(dtype=float)
    mwr = calculate_money_weighted_return(
        simple_portfolio_values,
        cash_flows,
        annualize=False
    )
    
    twr = calculate_time_weighted_return(simple_portfolio_values, annualize=False)
    assert abs(mwr - twr) < 0.01


def test_mwr_with_contributions(simple_portfolio_values, portfolio_with_contributions):
    """Test MWR with regular contributions."""
    # Build portfolio values that include contributions
    values_with_contrib = simple_portfolio_values.copy()
    for i in range(1, len(values_with_contrib)):
        values_with_contrib.iloc[i] += portfolio_with_contributions.iloc[:i].sum()
    
    mwr = calculate_money_weighted_return(
        values_with_contrib,
        portfolio_with_contributions,
        annualize=True
    )
    
    # MWR should be positive but lower than TWR due to contributions at higher prices
    assert mwr > 0


def test_mwr_empty_series():
    """Test MWR with empty series."""
    empty = pd.Series(dtype=float)
    cash_flows = pd.Series(dtype=float)
    mwr = calculate_money_weighted_return(empty, cash_flows)
    assert mwr == 0.0


# =============================================================================
# Risk Metrics Tests
# =============================================================================

def test_volatility_calculation():
    """Test volatility calculation."""
    # Create returns with known std dev
    returns = pd.Series([0.01, -0.01, 0.02, -0.02, 0.01, -0.01] * 4)
    vol = calculate_volatility(returns, annualize=False)
    
    expected_std = returns.std()
    assert abs(vol - expected_std) < 0.0001


def test_volatility_annualized():
    """Test annualized volatility."""
    returns = pd.Series([0.01] * 12)  # Constant returns
    vol_annual = calculate_volatility(returns, annualize=True)
    
    # Annualized vol = monthly vol * sqrt(12)
    vol_monthly = returns.std()
    expected = vol_monthly * np.sqrt(12)
    assert abs(vol_annual - expected) < 0.0001


def test_sharpe_ratio_positive():
    """Test Sharpe ratio with positive returns."""
    # Returns averaging 1% per month
    returns = pd.Series([0.01, 0.015, 0.008, 0.012, 0.011, 0.009] * 2)
    sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.04, annualize=True)
    
    # Should be positive
    assert sharpe > 0


def test_sharpe_ratio_zero_volatility():
    """Test Sharpe ratio with zero volatility."""
    returns = pd.Series([0.01] * 12)  # Constant returns
    sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.04, annualize=True)
    
    # Should return 0 when std dev is 0
    assert sharpe == 0.0


def test_sortino_ratio_no_downside():
    """Test Sortino ratio with no negative returns."""
    returns = pd.Series([0.01, 0.02, 0.015, 0.012, 0.018, 0.011] * 2)
    sortino = calculate_sortino_ratio(returns, risk_free_rate=0.04, annualize=True)
    
    # Should be very high (capped at 999)
    assert sortino == 999.0


def test_sortino_ratio_with_downside():
    """Test Sortino ratio with negative returns."""
    returns = pd.Series([0.02, -0.01, 0.015, -0.005, 0.01, -0.008] * 2)
    sortino = calculate_sortino_ratio(returns, risk_free_rate=0.04, annualize=True)
    
    # Should be positive but finite
    assert 0 < sortino < 999


# =============================================================================
# Drawdown Analysis Tests
# =============================================================================

def test_drawdown_calculation(volatile_portfolio_values):
    """Test drawdown calculation."""
    dd_df = calculate_drawdowns(volatile_portfolio_values)
    
    assert 'value' in dd_df.columns
    assert 'peak' in dd_df.columns
    assert 'drawdown' in dd_df.columns
    assert 'drawdown_pct' in dd_df.columns
    
    # Drawdown should be negative or zero
    assert (dd_df['drawdown'] <= 0).all()
    assert (dd_df['drawdown_pct'] <= 0).all()


def test_max_drawdown(volatile_portfolio_values):
    """Test maximum drawdown identification."""
    max_dd_pct, start_date, end_date, recovery_days = find_max_drawdown(volatile_portfolio_values)
    
    # Should find the crash period
    assert max_dd_pct < -20  # At least 20% drawdown
    assert start_date is not None
    assert end_date is not None
    
    # Recovery should have occurred
    if recovery_days is not None:
        assert recovery_days > 0


def test_max_drawdown_no_drawdown():
    """Test max drawdown with only increasing values."""
    dates = pd.date_range(start='2024-01-01', periods=12, freq='ME')
    values = pd.Series([100000 * (1.01 ** i) for i in range(12)], index=dates)
    
    max_dd_pct, _, _, _ = find_max_drawdown(values)
    
    # Should be zero or very small
    assert max_dd_pct >= -0.01


def test_find_all_drawdown_periods(volatile_portfolio_values):
    """Test finding all significant drawdown periods."""
    drawdown_periods = find_all_drawdown_periods(
        volatile_portfolio_values,
        min_drawdown_pct=-5.0
    )
    
    # Should find at least one significant drawdown
    assert len(drawdown_periods) > 0
    
    # Check structure of drawdown periods
    for dd in drawdown_periods:
        assert dd.start_date is not None
        assert dd.trough_date is not None
        assert dd.peak_value > 0
        assert dd.trough_value > 0
        assert dd.drawdown_pct < 0
        assert dd.duration_days >= 0


# =============================================================================
# Attribution Analysis Tests
# =============================================================================

def test_attribution_no_cash_flows(simple_portfolio_values):
    """Test attribution with no cash flows."""
    contributions = pd.Series(dtype=float)
    withdrawals = pd.Series(dtype=float)
    
    total_contrib, total_withdr, inv_growth = calculate_attribution(
        simple_portfolio_values,
        contributions,
        withdrawals
    )
    
    assert total_contrib == 0.0
    assert total_withdr == 0.0
    
    # All growth should be from investment returns
    expected_growth = simple_portfolio_values.iloc[-1] - simple_portfolio_values.iloc[0]
    assert abs(inv_growth - expected_growth) < 0.01


def test_attribution_with_contributions(simple_portfolio_values, portfolio_with_contributions):
    """Test attribution with contributions."""
    withdrawals = pd.Series(dtype=float)
    
    # Adjust portfolio values to include contributions
    values_with_contrib = simple_portfolio_values.copy()
    for i in range(1, len(values_with_contrib)):
        values_with_contrib.iloc[i] += portfolio_with_contributions.iloc[:i].sum()
    
    total_contrib, total_withdr, inv_growth = calculate_attribution(
        values_with_contrib,
        portfolio_with_contributions,
        withdrawals
    )
    
    assert total_contrib == portfolio_with_contributions.sum()
    assert total_withdr == 0.0
    assert inv_growth > 0


# =============================================================================
# Benchmark Comparison Tests
# =============================================================================

def test_alpha_beta_calculation():
    """Test alpha and beta calculation."""
    # Create correlated returns
    dates = pd.date_range(start='2024-01-01', periods=12, freq='ME')
    benchmark_returns = pd.Series([0.01, -0.005, 0.015, -0.01, 0.02, 0.005,
                                   0.01, -0.008, 0.012, -0.003, 0.018, 0.007],
                                  index=dates)
    
    # Portfolio returns with beta ~1.2 and positive alpha
    portfolio_returns = benchmark_returns * 1.2 + 0.002
    
    alpha, beta = calculate_alpha_beta(portfolio_returns, benchmark_returns, risk_free_rate=0.04)
    
    # Beta should be close to 1.2
    assert 1.0 < beta < 1.4
    
    # Alpha should be positive
    assert alpha > 0


def test_alpha_beta_empty_series():
    """Test alpha/beta with empty series."""
    empty = pd.Series(dtype=float)
    alpha, beta = calculate_alpha_beta(empty, empty)
    
    assert alpha == 0.0
    assert beta == 1.0


# =============================================================================
# Integration Tests
# =============================================================================

def test_calculate_portfolio_analytics_complete(
    volatile_portfolio_values,
    portfolio_with_contributions,
    portfolio_with_withdrawals
):
    """Test complete analytics calculation."""
    metrics = calculate_portfolio_analytics(
        volatile_portfolio_values,
        contributions=portfolio_with_contributions,
        withdrawals=portfolio_with_withdrawals,
        benchmark_symbol='^GSPC',
        risk_free_rate=0.04
    )
    
    # Check all metrics are present
    assert metrics.time_weighted_return is not None
    assert metrics.money_weighted_return is not None
    assert metrics.total_return_pct is not None
    assert metrics.volatility >= 0
    assert metrics.sharpe_ratio is not None
    assert metrics.sortino_ratio is not None
    assert metrics.max_drawdown_pct <= 0
    assert metrics.total_contributions >= 0
    assert metrics.total_withdrawals >= 0
    assert metrics.start_date is not None
    assert metrics.end_date is not None
    assert metrics.num_periods > 0


def test_calculate_portfolio_analytics_empty():
    """Test analytics with empty portfolio."""
    empty = pd.Series(dtype=float)
    metrics = calculate_portfolio_analytics(empty)
    
    # Should return zero/default values
    assert metrics.time_weighted_return == 0.0
    assert metrics.money_weighted_return == 0.0
    assert metrics.volatility == 0.0


def test_calculate_portfolio_analytics_minimal():
    """Test analytics with minimal data (2 points)."""
    dates = pd.date_range(start='2024-01-01', periods=2, freq='ME')
    values = pd.Series([100000, 105000], index=dates)
    
    metrics = calculate_portfolio_analytics(values)
    
    # Should calculate basic metrics
    assert metrics.time_weighted_return > 0
    assert metrics.total_return_pct == 5.0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

def test_negative_portfolio_values():
    """Test handling of negative portfolio values."""
    dates = pd.date_range(start='2024-01-01', periods=6, freq='ME')
    values = pd.Series([100000, 80000, 60000, 40000, 20000, -10000], index=dates)
    
    # Should handle gracefully
    twr = calculate_time_weighted_return(values)
    assert twr < 0  # Negative return


def test_zero_starting_value():
    """Test handling of zero starting value."""
    dates = pd.date_range(start='2024-01-01', periods=6, freq='ME')
    values = pd.Series([0, 10000, 20000, 30000, 40000, 50000], index=dates)
    
    twr = calculate_time_weighted_return(values)
    assert twr == 0.0  # Can't calculate return from zero


def test_unsorted_dates():
    """Test handling of unsorted date index."""
    dates = [datetime(2024, 3, 1), datetime(2024, 1, 1), datetime(2024, 2, 1)]
    values = pd.Series([105000, 100000, 102000], index=dates)
    
    # Should sort internally
    twr = calculate_time_weighted_return(values)
    assert twr > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
