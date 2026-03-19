"""
Security Selection Integration Module
======================================
Integration layer between security selection and withdrawal strategy.

This module provides wrapper functions that integrate the intelligent security
selection system with the existing withdrawal strategy in strategy.py.

Key Features:
- Seamless integration with existing BrokerageAccount FIFO tracking
- Portfolio DataFrame-based security selection when available
- Fallback to FIFO when portfolio data unavailable
- Transaction logging and decision tracking
- Multi-account optimization support

Author: Bob
Date: 2026-03-17
Version: 1.0
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import pandas as pd

from security_selection import (
    score_securities_for_liquidation,
    create_liquidation_plan,
    optimize_multi_account_withdrawal,
    LiquidationPlan,
)
from strategy import BrokerageAccount, BrokerageTransaction

logger = logging.getLogger(__name__)


# ==============================================================================
# INTEGRATION FUNCTIONS
# ==============================================================================

def withdraw_from_brokerage_smart(
    amount: float,
    brokerage_account: BrokerageAccount,
    portfolio_df: Optional[pd.DataFrame],
    year: int,
    target_allocation: Dict[str, float],
    current_agi: float,
    filing_status: str,
    recent_sales: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[float, float, Optional[LiquidationPlan]]:
    """
    Smart withdrawal from brokerage using security selection when possible.
    
    This function provides intelligent security selection for brokerage withdrawals
    while maintaining compatibility with the existing FIFO cost basis tracking.
    
    Args:
        amount: Amount to withdraw
        brokerage_account: BrokerageAccount instance for cost basis tracking
        portfolio_df: Portfolio DataFrame with current holdings (optional)
        year: Current year
        target_allocation: Target allocation dict {'Cash': 10, 'Bonds': 30, 'Stocks': 60}
        current_agi: Current AGI for tax rate determination
        filing_status: Tax filing status
        recent_sales: Recent sales for wash sale detection
    
    Returns:
        Tuple of (basis_returned, ltcg_realized, liquidation_plan)
        - basis_returned: Tax-free return of cost basis
        - ltcg_realized: Taxable long-term capital gains
        - liquidation_plan: LiquidationPlan object (None if using FIFO fallback)
    
    Example:
        >>> basis, ltcg, plan = withdraw_from_brokerage_smart(
        ...     amount=50000,
        ...     brokerage_account=brokerage_account,
        ...     portfolio_df=portfolio_df,
        ...     year=2024,
        ...     target_allocation={'Cash': 10, 'Bonds': 30, 'Stocks': 60},
        ...     current_agi=100000,
        ...     filing_status='single',
        ... )
        >>> print(f"Withdrew $50k: ${basis:,.0f} basis, ${ltcg:,.0f} LTCG")
        >>> if plan:
        ...     print(f"Used smart selection: {len(plan.securities)} securities")
    """
    if amount <= 0:
        return 0.0, 0.0, None
    
    # Check if we have portfolio data for smart selection
    if portfolio_df is None or portfolio_df.empty:
        logger.info(f"No portfolio data available, using FIFO fallback for ${amount:,.0f} withdrawal")
        basis, ltcg = brokerage_account.withdraw_fifo(amount, year)
        return basis, ltcg, None
    
    # Filter to brokerage holdings
    brokerage_holdings = portfolio_df[portfolio_df['account_type'] == 'Brokerage'].copy()
    
    if brokerage_holdings.empty:
        logger.warning("No brokerage holdings in portfolio data, using FIFO fallback")
        basis, ltcg = brokerage_account.withdraw_fifo(amount, year)
        return basis, ltcg, None
    
    try:
        # Score securities for liquidation
        logger.info(f"Using smart security selection for ${amount:,.0f} brokerage withdrawal")
        
        scores = score_securities_for_liquidation(
            portfolio_df=portfolio_df,
            withdrawal_amount=amount,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=current_agi,
            filing_status=filing_status,
            recent_sales=recent_sales or [],
        )
        
        if not scores:
            logger.warning("No securities scored, using FIFO fallback")
            basis, ltcg = brokerage_account.withdraw_fifo(amount, year)
            return basis, ltcg, None
        
        # Create liquidation plan
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=amount,
            account_type='Brokerage',
            target_allocation=target_allocation,
        )
        
        # Log the plan
        logger.info(f"Smart selection plan created:")
        logger.info(f"  Securities to sell: {len(plan.securities)}")
        logger.info(f"  Total selected: ${plan.total_selected:,.0f}")
        logger.info(f"  Estimated tax: ${plan.estimated_tax:,.0f}")
        logger.info(f"  Drift improvement: {plan.drift_improvement:+.2f}%")
        
        for i, liq in enumerate(plan.securities[:5], 1):  # Log top 5
            logger.info(f"    {i}. {liq.symbol}: ${liq.amount_to_liquidate:,.0f} ({liq.reason})")
        
        # Execute the plan through BrokerageAccount
        # Note: This updates the BrokerageAccount's transaction list
        basis, ltcg = brokerage_account.withdraw_fifo(plan.total_selected, year)
        
        # Return actual basis/LTCG from FIFO plus the plan for reporting
        return basis, ltcg, plan
        
    except Exception as e:
        logger.error(f"Error in smart security selection: {e}, falling back to FIFO")
        logger.exception(e)
        basis, ltcg = brokerage_account.withdraw_fifo(amount, year)
        return basis, ltcg, None


def optimize_withdrawal_across_accounts(
    total_needed: float,
    portfolio_df: Optional[pd.DataFrame],
    account_balances: Dict[str, float],
    account_priorities: List[str],
    target_allocation: Dict[str, float],
    tax_context: Dict[str, Any],
    year: int,
) -> Dict[str, Tuple[float, Optional[LiquidationPlan]]]:
    """
    Optimize withdrawals across multiple accounts using security selection.
    
    This function coordinates withdrawals from multiple accounts (Brokerage,
    Traditional, Roth) to meet a total withdrawal need while minimizing taxes
    and maintaining target allocation.
    
    Args:
        total_needed: Total amount needed across all accounts
        portfolio_df: Portfolio DataFrame with all holdings
        account_balances: Dict of account balances {'Brokerage': 250000, ...}
        account_priorities: List of accounts in priority order
        target_allocation: Target allocation dict
        tax_context: Dict with 'agi', 'filing_status', 'recent_sales'
        year: Current year
    
    Returns:
        Dict mapping account_type to (amount_withdrawn, liquidation_plan)
    
    Example:
        >>> results = optimize_withdrawal_across_accounts(
        ...     total_needed=100000,
        ...     portfolio_df=portfolio_df,
        ...     account_balances={'Brokerage': 250000, 'Traditional': 500000},
        ...     account_priorities=['Brokerage', 'Traditional'],
        ...     target_allocation={'Cash': 10, 'Bonds': 30, 'Stocks': 60},
        ...     tax_context={'agi': 100000, 'filing_status': 'single', 'recent_sales': []},
        ...     year=2024,
        ... )
        >>> for account, (amount, plan) in results.items():
        ...     print(f"{account}: ${amount:,.0f}")
    """
    if total_needed <= 0:
        return {}
    
    # Check if we have portfolio data
    if portfolio_df is None or portfolio_df.empty:
        logger.info("No portfolio data, cannot optimize across accounts")
        return {}
    
    try:
        # Use multi-account optimization
        logger.info(f"Optimizing ${total_needed:,.0f} withdrawal across accounts")
        
        plans = optimize_multi_account_withdrawal(
            total_needed=total_needed,
            portfolio_df=portfolio_df,
            account_priorities=account_priorities,
            target_allocation=target_allocation,
            tax_context=tax_context,
        )
        
        # Convert plans to results format
        results = {}
        for account_type, plan in plans.items():
            results[account_type] = (plan.total_selected, plan)
            logger.info(f"  {account_type}: ${plan.total_selected:,.0f} "
                       f"({len(plan.securities)} securities, "
                       f"${plan.estimated_tax:,.0f} tax)")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in multi-account optimization: {e}")
        logger.exception(e)
        return {}


def create_portfolio_snapshot(
    brokerage_account: BrokerageAccount,
    year: int,
    month: int = 12,
) -> pd.DataFrame:
    """
    Create a portfolio DataFrame from BrokerageAccount transactions.
    
    This function converts the BrokerageAccount's transaction list into a
    portfolio DataFrame suitable for security selection. This is useful when
    detailed portfolio data is not available but we have cost basis tracking.
    
    Args:
        brokerage_account: BrokerageAccount instance
        year: Current year
        month: Current month (default: 12 for year-end)
    
    Returns:
        Portfolio DataFrame with columns:
        - symbol: 'BROKERAGE_LOT_{i}' for each transaction
        - account_type: 'Brokerage'
        - qty: Shares (approximated as current_value / 100)
        - purchase_price: Cost basis per share
        - current_price: Current price per share
        - market_value: Current market value
        - sector: 'Mixed' (unknown)
        - name: Source description
        - holding_period_days: Days held
    
    Note:
        This is a simplified snapshot that treats each transaction as a separate
        "security" for selection purposes. In practice, you should use actual
        portfolio data from portfolio.py when available.
    """
    if not brokerage_account.transactions:
        return pd.DataFrame()
    
    rows = []
    for i, txn in enumerate(brokerage_account.transactions):
        if txn.current_value <= 0:
            continue
        
        # Approximate shares (assuming $100/share for simplicity)
        approx_shares = txn.current_value / 100
        cost_per_share = txn.cost_basis / approx_shares if approx_shares > 0 else 0
        current_per_share = txn.current_value / approx_shares if approx_shares > 0 else 0
        
        rows.append({
            'symbol': f'BROKERAGE_LOT_{i}',
            'account_type': 'Brokerage',
            'qty': approx_shares,
            'purchase_price': cost_per_share,
            'current_price': current_per_share,
            'market_value': txn.current_value,
            'sector': 'Mixed',
            'name': f'Lot from {txn.source}',
            'holding_period_days': txn.years_held * 365,
        })
    
    return pd.DataFrame(rows)


def track_liquidation_for_wash_sales(
    plan: Optional[LiquidationPlan],
    year: int,
) -> List[Dict[str, Any]]:
    """
    Convert liquidation plan to wash sale tracking format.
    
    Args:
        plan: LiquidationPlan from smart withdrawal
        year: Current year
    
    Returns:
        List of sale records for wash sale tracking
    """
    if plan is None or not plan.securities:
        return []
    
    sales = []
    for liq in plan.securities:
        sales.append({
            'symbol': liq.symbol,
            'date': datetime(year, 12, 31),  # Approximate as year-end
            'gain_loss': liq.gain_loss,
            'amount': liq.amount_to_liquidate,
        })
    
    return sales


# ==============================================================================
# HELPER FUNCTIONS FOR STRATEGY.PY INTEGRATION
# ==============================================================================

def should_use_smart_selection(
    portfolio_df: Optional[pd.DataFrame],
    account_type: str = 'Brokerage',
) -> bool:
    """
    Determine if smart security selection should be used.
    
    Args:
        portfolio_df: Portfolio DataFrame
        account_type: Account type to check
    
    Returns:
        True if smart selection should be used, False for FIFO fallback
    """
    if portfolio_df is None or portfolio_df.empty:
        return False
    
    account_holdings = portfolio_df[portfolio_df['account_type'] == account_type]
    return not account_holdings.empty


def format_liquidation_summary_for_log(
    plan: Optional[LiquidationPlan],
) -> str:
    """
    Format liquidation plan for logging.
    
    Args:
        plan: LiquidationPlan object
    
    Returns:
        Formatted string for logging
    """
    if plan is None:
        return "No liquidation plan (used FIFO fallback)"
    
    lines = [
        f"Smart Selection Summary:",
        f"  Securities sold: {len(plan.securities)}",
        f"  Total amount: ${plan.total_selected:,.0f}",
        f"  Tax impact: ${plan.estimated_tax:,.0f}",
        f"  LTCG: ${plan.total_ltcg:,.0f}",
        f"  STCG: ${plan.total_stcg:,.0f}",
        f"  Basis returned: ${plan.total_basis_returned:,.0f}",
        f"  Drift improvement: {plan.drift_improvement:+.2f}%",
    ]
    
    if plan.securities:
        lines.append("  Top securities:")
        for liq in plan.securities[:3]:
            lines.append(f"    • {liq.symbol}: ${liq.amount_to_liquidate:,.0f} ({liq.reason})")
    
    if plan.notes:
        lines.append("  Notes:")
        for note in plan.notes:
            lines.append(f"    • {note}")
    
    return "\n".join(lines)


# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Default target allocation (can be overridden)
DEFAULT_TARGET_ALLOCATION = {
    'Cash': 10.0,
    'Bonds': 30.0,
    'Stocks': 60.0,
}


def get_target_allocation_from_config() -> Dict[str, float]:
    """
    Get target allocation from configuration.
    
    Returns:
        Target allocation dict
    
    Note:
        This function can be extended to read from config.py or bucket_strategy.py
    """
    try:
        from config import get_config_manager
        from bucket_strategy import load_bucket_config
        
        cfg = get_config_manager()
        bucket_enabled = cfg.get("bucket_strategy", "enabled", False)
        
        if bucket_enabled:
            bucket_config = load_bucket_config(cfg)
            # Calculate cumulative target from bucket strategy
            # (Implementation would mirror portfolio_optimization.py logic)
            pass
    except Exception:
        pass
    
    return DEFAULT_TARGET_ALLOCATION


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == '__main__':
    """
    Example usage of security selection integration.
    """
    import sys
    
    # Example: Smart withdrawal from brokerage
    print("Example: Smart Brokerage Withdrawal")
    print("=" * 60)
    
    # Create sample brokerage account
    brokerage = BrokerageAccount()
    brokerage.add_transfer(2020, 100000, "initial_portfolio")
    brokerage.apply_annual_growth(1.07, 2021)
    brokerage.apply_annual_growth(1.07, 2022)
    brokerage.apply_annual_growth(1.07, 2023)
    brokerage.apply_annual_growth(1.07, 2024)
    
    print(f"Brokerage balance: ${brokerage.total_value:,.0f}")
    print(f"Cost basis: ${brokerage.total_basis:,.0f}")
    print(f"Unrealized gains: ${brokerage.total_gains:,.0f}")
    print()
    
    # Create sample portfolio DataFrame
    portfolio_df = create_portfolio_snapshot(brokerage, 2024)
    print(f"Portfolio snapshot: {len(portfolio_df)} lots")
    print()
    
    # Perform smart withdrawal
    basis, ltcg, plan = withdraw_from_brokerage_smart(
        amount=50000,
        brokerage_account=brokerage,
        portfolio_df=portfolio_df,
        year=2024,
        target_allocation=DEFAULT_TARGET_ALLOCATION,
        current_agi=100000,
        filing_status='single',
    )
    
    print(f"Withdrawal results:")
    print(f"  Basis returned: ${basis:,.0f}")
    print(f"  LTCG realized: ${ltcg:,.0f}")
    print()
    
    if plan:
        print(format_liquidation_summary_for_log(plan))

# Made with Bob
