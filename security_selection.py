"""
Security Selection Module
=========================
Intelligent decision-making for which specific holdings to liquidate during withdrawals.

This module provides sophisticated security selection logic that optimizes for:
- Tax efficiency (minimize tax burden through strategic loss/gain harvesting)
- Rebalancing needs (sell overweight positions to maintain target allocation)
- Cost basis optimization (FIFO with strategic selection)
- Wash sale rule compliance (avoid triggering wash sales)
- Transaction cost minimization (batch trades efficiently)

Key Features:
- Multi-factor scoring system for liquidation suitability
- Tax-aware liquidation planning across multiple accounts
- Integration with existing cost basis tracking
- Wash sale detection and avoidance
- Rebalancing-aware security selection

Author: Bob
Date: 2026-03-17
Version: 1.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np

from load_data import get_cap_gains_brackets
from portfolio_rebalancing import _classify_asset
from tax_harvesting import WASH_SALE_REPLACEMENTS

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Scoring weights for liquidation suitability (must sum to 1.0)
WEIGHT_TAX_EFFICIENCY = 0.30
WEIGHT_REBALANCING = 0.30
WEIGHT_LIQUIDITY = 0.20
WEIGHT_COST_BASIS = 0.20

# Tax efficiency scoring thresholds
TAX_SCORE_LOSS = 100.0  # Harvest losses first
TAX_SCORE_GAIN_0PCT = 90.0  # Gains at 0% LTCG rate
TAX_SCORE_GAIN_15PCT = 60.0  # Gains at 15% LTCG rate
TAX_SCORE_GAIN_20PCT = 40.0  # Gains at 20% LTCG rate
TAX_SCORE_STCG = 20.0  # Short-term gains (ordinary income)

# Rebalancing scoring thresholds
REBAL_SCORE_OVERWEIGHT_10PCT = 100.0
REBAL_SCORE_OVERWEIGHT_5PCT = 80.0
REBAL_SCORE_OVERWEIGHT_0PCT = 60.0
REBAL_SCORE_AT_TARGET = 40.0
REBAL_SCORE_UNDERWEIGHT = 20.0

# Liquidity scoring
LIQUIDITY_SCORE_HIGH = 100.0  # High volume stocks/ETFs
LIQUIDITY_SCORE_MEDIUM = 80.0  # Mutual funds
LIQUIDITY_SCORE_LOW = 60.0  # Low volume stocks
LIQUIDITY_SCORE_ILLIQUID = 40.0  # Very illiquid positions

# Cost basis scoring
BASIS_SCORE_HIGH = 100.0  # High basis (low gain)
BASIS_SCORE_MEDIUM = 70.0  # Medium basis
BASIS_SCORE_LOW = 40.0  # Low basis (high gain)
BASIS_SCORE_LOSS = 100.0  # Loss positions

# Wash sale window (30 days before and after)
WASH_SALE_DAYS = 30

# Long-term capital gains holding period
LTCG_HOLDING_DAYS = 365


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class SecurityScore:
    """
    Score for a security's suitability for liquidation.
    
    Attributes:
        symbol: Ticker symbol
        account_type: Account type (Brokerage, Traditional, Roth)
        current_value: Current market value
        shares: Number of shares held
        
        # Scoring factors (0-100 each)
        tax_efficiency_score: Higher = better tax outcome
        rebalancing_score: Higher = more overweight
        liquidity_score: Higher = easier to sell
        cost_basis_score: Higher = better basis situation
        
        # Composite score
        total_score: Weighted average of all factors
        
        # Supporting data
        unrealized_gain_loss: Unrealized gain (positive) or loss (negative)
        holding_period_days: Days held
        is_wash_sale_risk: True if recent sale could trigger wash sale
        asset_class: Cash, Bonds, or Stocks
        current_allocation_pct: Current % of portfolio
        target_allocation_pct: Target % of portfolio
        cost_basis: Tax basis per share
        current_price: Current price per share
        
        # Tax details
        ltcg_rate: Long-term capital gains rate (0.0, 0.15, 0.20)
        is_long_term: True if held > 365 days
        estimated_tax: Estimated tax on full liquidation
    """
    symbol: str
    account_type: str
    current_value: float
    shares: float
    
    # Scoring factors
    tax_efficiency_score: float
    rebalancing_score: float
    liquidity_score: float
    cost_basis_score: float
    
    # Composite
    total_score: float
    
    # Supporting data
    unrealized_gain_loss: float
    holding_period_days: int
    is_wash_sale_risk: bool
    asset_class: str
    current_allocation_pct: float
    target_allocation_pct: float
    cost_basis: float
    current_price: float
    
    # Tax details
    ltcg_rate: float
    is_long_term: bool
    estimated_tax: float
    
    def __repr__(self) -> str:
        return (
            f"SecurityScore({self.symbol}, score={self.total_score:.1f}, "
            f"value=${self.current_value:,.0f}, gain=${self.unrealized_gain_loss:,.0f})"
        )


@dataclass
class SecurityLiquidation:
    """
    Details for liquidating a specific security.
    
    Attributes:
        symbol: Ticker symbol
        account_type: Account type
        shares_to_sell: Number of shares to liquidate
        amount_to_liquidate: Dollar amount to receive
        cost_basis: Total cost basis of shares being sold
        gain_loss: Realized gain (positive) or loss (negative)
        tax_impact: Estimated tax on this liquidation
        reason: Why this security was selected
        is_partial: True if selling partial position
        remaining_shares: Shares remaining after sale
        remaining_value: Value remaining after sale
    """
    symbol: str
    account_type: str
    shares_to_sell: float
    amount_to_liquidate: float
    cost_basis: float
    gain_loss: float
    tax_impact: float
    reason: str
    is_partial: bool
    remaining_shares: float
    remaining_value: float
    
    def __repr__(self) -> str:
        return (
            f"SecurityLiquidation({self.symbol}, "
            f"${self.amount_to_liquidate:,.0f}, "
            f"tax=${self.tax_impact:,.0f})"
        )


@dataclass
class LiquidationPlan:
    """
    Complete plan for liquidating securities to meet withdrawal need.
    
    Attributes:
        total_needed: Total withdrawal amount requested
        total_selected: Total amount from selected securities
        securities: List of securities to liquidate
        
        # Tax impact summary
        total_ltcg: Total long-term capital gains
        total_stcg: Total short-term capital gains
        total_basis_returned: Total cost basis returned (tax-free)
        estimated_tax: Total estimated tax
        
        # Rebalancing impact
        pre_allocation: Asset allocation before liquidation
        post_allocation: Asset allocation after liquidation
        drift_improvement: Improvement in drift from target (positive = better)
        
        # Metadata
        account_type: Account where liquidation occurs
        created_at: Timestamp when plan was created
        notes: Additional notes or warnings
    """
    total_needed: float
    total_selected: float
    securities: List[SecurityLiquidation]
    
    # Tax impact
    total_ltcg: float
    total_stcg: float
    total_basis_returned: float
    estimated_tax: float
    
    # Rebalancing impact
    pre_allocation: Dict[str, float]
    post_allocation: Dict[str, float]
    drift_improvement: float
    
    # Metadata
    account_type: str
    created_at: datetime = field(default_factory=datetime.now)
    notes: List[str] = field(default_factory=list)
    
    def __repr__(self) -> str:
        return (
            f"LiquidationPlan(needed=${self.total_needed:,.0f}, "
            f"selected=${self.total_selected:,.0f}, "
            f"securities={len(self.securities)}, "
            f"tax=${self.estimated_tax:,.0f})"
        )
    
    def summary(self) -> str:
        """Generate human-readable summary of the plan."""
        lines = [
            f"Liquidation Plan for {self.account_type} Account",
            f"=" * 60,
            f"Total Needed: ${self.total_needed:,.2f}",
            f"Total Selected: ${self.total_selected:,.2f}",
            f"Securities to Sell: {len(self.securities)}",
            "",
            "Tax Impact:",
            f"  Long-term Capital Gains: ${self.total_ltcg:,.2f}",
            f"  Short-term Capital Gains: ${self.total_stcg:,.2f}",
            f"  Cost Basis Returned: ${self.total_basis_returned:,.2f}",
            f"  Estimated Tax: ${self.estimated_tax:,.2f}",
            "",
            "Rebalancing Impact:",
        ]
        
        for asset_class in ['Cash', 'Bonds', 'Stocks']:
            pre = self.pre_allocation.get(asset_class, 0.0)
            post = self.post_allocation.get(asset_class, 0.0)
            change = post - pre
            lines.append(f"  {asset_class}: {pre:.1f}% → {post:.1f}% ({change:+.1f}%)")
        
        lines.append(f"  Drift Improvement: {self.drift_improvement:+.2f}%")
        
        if self.notes:
            lines.append("")
            lines.append("Notes:")
            for note in self.notes:
                lines.append(f"  • {note}")
        
        return "\n".join(lines)


# ==============================================================================
# SCORING FUNCTIONS
# ==============================================================================

def calculate_tax_efficiency_score(
    unrealized_gain_loss: float,
    holding_period_days: int,
    ltcg_rate: float,
    account_type: str,
) -> float:
    """
    Calculate tax efficiency score (0-100).
    
    Higher score = better tax outcome from selling this security.
    
    Args:
        unrealized_gain_loss: Unrealized gain (positive) or loss (negative)
        holding_period_days: Days held
        ltcg_rate: Long-term capital gains rate (0.0, 0.15, 0.20)
        account_type: Account type (Brokerage, Traditional, Roth)
    
    Returns:
        Score from 0-100
    """
    # Tax-advantaged accounts have no current tax impact
    if account_type in ['Traditional', 'Roth']:
        return TAX_SCORE_GAIN_0PCT
    
    # Loss positions are most tax-efficient (harvest losses)
    if unrealized_gain_loss < 0:
        return TAX_SCORE_LOSS
    
    # Short-term gains (ordinary income rates) are least efficient
    if holding_period_days <= LTCG_HOLDING_DAYS:
        return TAX_SCORE_STCG
    
    # Long-term gains scored by rate
    if ltcg_rate == 0.0:
        return TAX_SCORE_GAIN_0PCT
    elif ltcg_rate <= 0.15:
        return TAX_SCORE_GAIN_15PCT
    else:
        return TAX_SCORE_GAIN_20PCT


def calculate_rebalancing_score(
    current_allocation_pct: float,
    target_allocation_pct: float,
) -> float:
    """
    Calculate rebalancing score (0-100).
    
    Higher score = more overweight, should sell to rebalance.
    
    Args:
        current_allocation_pct: Current % of portfolio in this asset class
        target_allocation_pct: Target % of portfolio in this asset class
    
    Returns:
        Score from 0-100
    """
    drift = current_allocation_pct - target_allocation_pct
    
    if drift >= 10.0:
        return REBAL_SCORE_OVERWEIGHT_10PCT
    elif drift >= 5.0:
        return REBAL_SCORE_OVERWEIGHT_5PCT
    elif drift > 0.0:
        return REBAL_SCORE_OVERWEIGHT_0PCT
    elif drift == 0.0:
        return REBAL_SCORE_AT_TARGET
    else:
        return REBAL_SCORE_UNDERWEIGHT


def calculate_liquidity_score(
    symbol: str,
    asset_class: str,
) -> float:
    """
    Calculate liquidity score (0-100).
    
    Higher score = easier to sell without market impact.
    
    Args:
        symbol: Ticker symbol
        asset_class: Cash, Bonds, or Stocks
    
    Returns:
        Score from 0-100
    """
    # Cash is perfectly liquid
    if symbol == "MF:CASH" or asset_class == "Cash":
        return LIQUIDITY_SCORE_HIGH
    
    # Mutual funds (5-letter tickers) are generally liquid
    if len(symbol) == 5 and symbol.isalpha():
        return LIQUIDITY_SCORE_MEDIUM
    
    # ETFs and large-cap stocks are highly liquid
    # (In production, would check actual volume data)
    if symbol.isupper() and len(symbol) <= 4:
        return LIQUIDITY_SCORE_HIGH
    
    # Default to medium liquidity
    return LIQUIDITY_SCORE_MEDIUM


def calculate_cost_basis_score(
    unrealized_gain_loss: float,
    current_value: float,
) -> float:
    """
    Calculate cost basis score (0-100).
    
    Higher score = better basis situation (high basis/low gain or loss).
    
    Args:
        unrealized_gain_loss: Unrealized gain (positive) or loss (negative)
        current_value: Current market value
    
    Returns:
        Score from 0-100
    """
    # Loss positions get highest score
    if unrealized_gain_loss < 0:
        return BASIS_SCORE_LOSS
    
    # Calculate gain as percentage of current value
    if current_value <= 0:
        return BASIS_SCORE_MEDIUM
    
    gain_pct = (unrealized_gain_loss / current_value) * 100
    
    # High basis (low gain %) is better
    if gain_pct < 10:
        return BASIS_SCORE_HIGH
    elif gain_pct < 50:
        return BASIS_SCORE_MEDIUM
    else:
        return BASIS_SCORE_LOW


def calculate_composite_score(
    tax_score: float,
    rebal_score: float,
    liquidity_score: float,
    basis_score: float,
) -> float:
    """
    Calculate weighted composite score.
    
    Args:
        tax_score: Tax efficiency score (0-100)
        rebal_score: Rebalancing score (0-100)
        liquidity_score: Liquidity score (0-100)
        basis_score: Cost basis score (0-100)
    
    Returns:
        Weighted composite score (0-100)
    """
    return (
        tax_score * WEIGHT_TAX_EFFICIENCY +
        rebal_score * WEIGHT_REBALANCING +
        liquidity_score * WEIGHT_LIQUIDITY +
        basis_score * WEIGHT_COST_BASIS
    )


# ==============================================================================
# WASH SALE DETECTION
# ==============================================================================

def check_wash_sale_risk(
    symbol: str,
    recent_sales: List[Dict[str, Any]],
    sale_date: datetime,
) -> bool:
    """
    Check if selling this security would trigger a wash sale.
    
    A wash sale occurs when you sell a security at a loss and buy the same
    or substantially identical security within 30 days before or after the sale.
    
    Args:
        symbol: Ticker symbol to check
        recent_sales: List of recent sales with 'symbol', 'date', 'gain_loss'
        sale_date: Proposed sale date
    
    Returns:
        True if there's a wash sale risk
    """
    for sale in recent_sales:
        if sale['symbol'] != symbol:
            continue
        
        # Only care about loss sales
        if sale.get('gain_loss', 0) >= 0:
            continue
        
        # Check if within 30-day window
        days_diff = abs((sale_date - sale['date']).days)
        if days_diff <= WASH_SALE_DAYS:
            return True
    
    return False


# ==============================================================================
# MAIN SCORING FUNCTION
# ==============================================================================

def score_securities_for_liquidation(
    portfolio_df: pd.DataFrame,
    withdrawal_amount: float,
    account_type: str,
    target_allocation: Dict[str, float],
    current_agi: float,
    filing_status: str,
    recent_sales: Optional[List[Dict[str, Any]]] = None,
    year: Optional[int] = None,
) -> List[SecurityScore]:
    """
    Score all securities in an account for liquidation suitability.

    Args:
        portfolio_df: Portfolio DataFrame with holdings
        withdrawal_amount: Amount needed to withdraw
        account_type: Account type (Brokerage, Traditional, Roth)
        target_allocation: Target allocation dict {'Cash': 10, 'Bonds': 30, 'Stocks': 60}
        current_agi: Current AGI for LTCG rate determination
        filing_status: Tax filing status
        recent_sales: Recent sales for wash sale detection
        year: Tax year for bracket lookup (defaults to current calendar year)

    Returns:
        List of SecurityScore objects, sorted by total_score (descending)
    """
    if recent_sales is None:
        recent_sales = []
    if year is None:
        year = datetime.now().year

    # Filter to specified account
    account_holdings = portfolio_df[portfolio_df['account_type'] == account_type].copy()

    if account_holdings.empty:
        logger.warning(f"No holdings found in {account_type} account")
        return []

    # Get LTCG rate brackets
    try:
        ltcg_brackets = get_cap_gains_brackets(year, filing_status)
    except Exception as e:
        logger.error(f"Error getting LTCG brackets: {e}")
        ltcg_brackets = pd.DataFrame()
    
    # Calculate current allocation
    total_value = account_holdings['market_value'].sum()
    current_allocation = {}
    for asset_class in ['Cash', 'Bonds', 'Stocks']:
        class_value = account_holdings[
            account_holdings['asset_class'] == asset_class
        ]['market_value'].sum()
        current_allocation[asset_class] = (class_value / total_value * 100) if total_value > 0 else 0
    
    scores = []
    sale_date = datetime.now()
    
    for _, holding in account_holdings.iterrows():
        symbol = str(holding['symbol'])
        shares = float(holding.get('qty') or 0)
        current_price = float(holding.get('current_price') or 0)
        purchase_price = float(holding.get('purchase_price') or current_price)
        current_value = float(holding.get('market_value') or (shares * current_price))
        
        # Calculate cost basis and gain/loss
        cost_basis_per_share = purchase_price
        cost_basis_total = cost_basis_per_share * shares
        unrealized_gain_loss = current_value - cost_basis_total
        
        # Determine holding period (simplified - would use actual purchase date)
        holding_period_days = int(holding.get('holding_period_days') or 400)  # Default to long-term
        is_long_term = holding_period_days > LTCG_HOLDING_DAYS
        
        # Determine LTCG rate
        ltcg_rate = 0.0
        if account_type == 'Brokerage' and unrealized_gain_loss > 0 and is_long_term:
            # Simplified LTCG rate determination
            if current_agi < 44_625:  # Single 0% threshold (2024)
                ltcg_rate = 0.0
            elif current_agi < 492_300:  # Single 15% threshold (2024)
                ltcg_rate = 0.15
            else:
                ltcg_rate = 0.20
        
        # Calculate estimated tax
        if account_type == 'Brokerage' and unrealized_gain_loss > 0:
            if is_long_term:
                estimated_tax = unrealized_gain_loss * ltcg_rate
            else:
                # Short-term gains taxed as ordinary income (simplified to 24%)
                estimated_tax = unrealized_gain_loss * 0.24
        else:
            estimated_tax = 0.0
        
        # Classify asset
        sector = str(holding.get('sector') or '')
        name = str(holding.get('name') or '')
        asset_class = _classify_asset(symbol, sector, name)
        
        # Get allocation percentages
        current_alloc_pct = current_allocation.get(asset_class, 0.0)
        target_alloc_pct = target_allocation.get(asset_class, 0.0)
        
        # Check wash sale risk
        is_wash_sale_risk = check_wash_sale_risk(symbol, recent_sales, sale_date)
        
        # Calculate individual scores
        tax_score = calculate_tax_efficiency_score(
            unrealized_gain_loss, holding_period_days, ltcg_rate, account_type
        )
        rebal_score = calculate_rebalancing_score(current_alloc_pct, target_alloc_pct)
        liquidity_score = calculate_liquidity_score(symbol, asset_class)
        basis_score = calculate_cost_basis_score(unrealized_gain_loss, current_value)
        
        # Penalize wash sale risks
        if is_wash_sale_risk:
            tax_score *= 0.5  # Cut tax score in half
        
        # Calculate composite score
        total_score = calculate_composite_score(
            tax_score, rebal_score, liquidity_score, basis_score
        )
        
        # Create SecurityScore object
        score = SecurityScore(
            symbol=symbol,
            account_type=account_type,
            current_value=current_value,
            shares=shares,
            tax_efficiency_score=tax_score,
            rebalancing_score=rebal_score,
            liquidity_score=liquidity_score,
            cost_basis_score=basis_score,
            total_score=total_score,
            unrealized_gain_loss=unrealized_gain_loss,
            holding_period_days=holding_period_days,
            is_wash_sale_risk=is_wash_sale_risk,
            asset_class=asset_class,
            current_allocation_pct=current_alloc_pct,
            target_allocation_pct=target_alloc_pct,
            cost_basis=cost_basis_per_share,
            current_price=current_price,
            ltcg_rate=ltcg_rate,
            is_long_term=is_long_term,
            estimated_tax=estimated_tax,
        )
        
        scores.append(score)
    
    # Sort by total score (descending)
    scores.sort(key=lambda x: x.total_score, reverse=True)
    
    logger.info(f"Scored {len(scores)} securities in {account_type} account")
    
    return scores


# ==============================================================================
# LIQUIDATION PLAN CREATION
# ==============================================================================

def create_liquidation_plan(
    scored_securities: List[SecurityScore],
    withdrawal_amount: float,
    account_type: str,
    target_allocation: Dict[str, float],
    allow_partial_shares: bool = True,
) -> LiquidationPlan:
    """
    Create optimal liquidation plan to meet withdrawal need.
    
    Algorithm:
    1. Sort securities by total_score (descending) - already done
    2. Select securities until withdrawal amount is met
    3. Handle partial share sales if needed
    4. Calculate tax impact and rebalancing effect
    5. Validate plan meets all constraints
    
    Args:
        scored_securities: List of scored securities (sorted by score)
        withdrawal_amount: Amount needed to withdraw
        account_type: Account type
        target_allocation: Target allocation dict
        allow_partial_shares: Whether to allow partial share sales
    
    Returns:
        LiquidationPlan object
    """
    if not scored_securities:
        raise ValueError("No securities available for liquidation")
    
    # Calculate pre-liquidation allocation
    total_value = sum(s.current_value for s in scored_securities)
    pre_allocation = {}
    for asset_class in ['Cash', 'Bonds', 'Stocks']:
        class_value = sum(
            s.current_value for s in scored_securities 
            if s.asset_class == asset_class
        )
        pre_allocation[asset_class] = (class_value / total_value * 100) if total_value > 0 else 0
    
    # Select securities to liquidate
    liquidations = []
    total_selected = 0.0
    total_ltcg = 0.0
    total_stcg = 0.0
    total_basis = 0.0
    total_tax = 0.0
    
    for security in scored_securities:
        if total_selected >= withdrawal_amount:
            break
        
        remaining_need = withdrawal_amount - total_selected
        
        # Determine how much to sell from this security
        if security.current_value <= remaining_need:
            # Sell entire position
            shares_to_sell = security.shares
            amount_to_liquidate = security.current_value
            is_partial = False
        else:
            # Sell partial position
            if not allow_partial_shares:
                # Skip if we can't do partial shares and this would overshoot
                continue
            
            shares_to_sell = remaining_need / security.current_price
            amount_to_liquidate = remaining_need
            is_partial = True
        
        # Calculate cost basis and gain/loss for this liquidation
        cost_basis = shares_to_sell * security.cost_basis
        gain_loss = amount_to_liquidate - cost_basis
        
        # Calculate tax impact
        if account_type == 'Brokerage' and gain_loss > 0:
            if security.is_long_term:
                tax_impact = gain_loss * security.ltcg_rate
                total_ltcg += gain_loss
            else:
                tax_impact = gain_loss * 0.24  # Simplified STCG rate
                total_stcg += gain_loss
        else:
            tax_impact = 0.0
        
        total_basis += cost_basis
        total_tax += tax_impact
        
        # Determine reason for selection
        reasons = []
        if security.tax_efficiency_score >= 90:
            reasons.append("Tax-efficient")
        if security.rebalancing_score >= 80:
            reasons.append("Overweight")
        if security.unrealized_gain_loss < 0:
            reasons.append("Loss harvest")
        reason = ", ".join(reasons) if reasons else "Best available"
        
        # Create liquidation record
        liquidation = SecurityLiquidation(
            symbol=security.symbol,
            account_type=account_type,
            shares_to_sell=shares_to_sell,
            amount_to_liquidate=amount_to_liquidate,
            cost_basis=cost_basis,
            gain_loss=gain_loss,
            tax_impact=tax_impact,
            reason=reason,
            is_partial=is_partial,
            remaining_shares=security.shares - shares_to_sell,
            remaining_value=security.current_value - amount_to_liquidate,
        )
        
        liquidations.append(liquidation)
        total_selected += amount_to_liquidate
    
    # Calculate post-liquidation allocation
    remaining_value = total_value - total_selected
    post_allocation = {}
    
    for asset_class in ['Cash', 'Bonds', 'Stocks']:
        # Calculate remaining value in this asset class
        class_remaining = 0.0
        for security in scored_securities:
            if security.asset_class != asset_class:
                continue
            
            # Find if this security was liquidated
            liquidated = next(
                (liq for liq in liquidations if liq.symbol == security.symbol),
                None
            )
            
            if liquidated:
                class_remaining += liquidated.remaining_value
            else:
                class_remaining += security.current_value
        
        post_allocation[asset_class] = (
            (class_remaining / remaining_value * 100) if remaining_value > 0 else 0
        )
    
    # Calculate drift improvement
    pre_drift = sum(
        abs(pre_allocation.get(ac, 0) - target_allocation.get(ac, 0))
        for ac in ['Cash', 'Bonds', 'Stocks']
    )
    post_drift = sum(
        abs(post_allocation.get(ac, 0) - target_allocation.get(ac, 0))
        for ac in ['Cash', 'Bonds', 'Stocks']
    )
    drift_improvement = pre_drift - post_drift
    
    # Generate notes
    notes = []
    if total_selected < withdrawal_amount:
        shortfall = withdrawal_amount - total_selected
        notes.append(f"Warning: Shortfall of ${shortfall:,.2f} - insufficient securities")
    
    if total_tax > withdrawal_amount * 0.20:
        notes.append(f"Warning: High tax impact ({total_tax/withdrawal_amount*100:.1f}% of withdrawal)")
    
    if any(liq.is_wash_sale_risk for liq in liquidations if hasattr(liq, 'is_wash_sale_risk')):
        notes.append("Warning: Some securities have wash sale risk")
    
    # Create plan
    plan = LiquidationPlan(
        total_needed=withdrawal_amount,
        total_selected=total_selected,
        securities=liquidations,
        total_ltcg=total_ltcg,
        total_stcg=total_stcg,
        total_basis_returned=total_basis,
        estimated_tax=total_tax,
        pre_allocation=pre_allocation,
        post_allocation=post_allocation,
        drift_improvement=drift_improvement,
        account_type=account_type,
        notes=notes,
    )
    
    logger.info(
        f"Created liquidation plan: {len(liquidations)} securities, "
        f"${total_selected:,.0f} selected, ${total_tax:,.0f} tax"
    )
    
    return plan


# ==============================================================================
# MULTI-ACCOUNT OPTIMIZATION
# ==============================================================================

def optimize_multi_account_withdrawal(
    total_needed: float,
    portfolio_df: pd.DataFrame,
    account_priorities: List[str],
    target_allocation: Dict[str, float],
    tax_context: Dict[str, Any],
) -> Dict[str, LiquidationPlan]:
    """
    Optimize withdrawals across multiple accounts.
    
    Strategy:
    1. Determine optimal account sequence (tax-efficient withdrawal order)
    2. For each account, create liquidation plan
    3. Ensure total meets withdrawal need
    4. Minimize total tax impact across all accounts
    
    Args:
        total_needed: Total amount needed across all accounts
        portfolio_df: Complete portfolio DataFrame
        account_priorities: List of account types in priority order
        target_allocation: Target allocation dict
        tax_context: Dict with 'agi', 'filing_status', 'recent_sales'
    
    Returns:
        Dict mapping account_type to LiquidationPlan
    """
    plans = {}
    remaining_need = total_needed
    
    for account_type in account_priorities:
        if remaining_need <= 0:
            break
        
        # Get holdings in this account
        account_holdings = portfolio_df[portfolio_df['account_type'] == account_type]
        
        if account_holdings.empty:
            logger.info(f"No holdings in {account_type} account, skipping")
            continue
        
        # Calculate available amount in this account
        available = account_holdings['market_value'].sum()
        
        if available <= 0:
            logger.info(f"No value in {account_type} account, skipping")
            continue
        
        # Determine how much to withdraw from this account
        withdrawal_from_account = min(remaining_need, available)
        
        # Score securities
        scored = score_securities_for_liquidation(
            portfolio_df,
            withdrawal_from_account,
            account_type,
            target_allocation,
            tax_context.get('agi', 0),
            tax_context.get('filing_status', 'single'),
            tax_context.get('recent_sales', []),
        )
        
        if not scored:
            logger.warning(f"No securities scored in {account_type} account")
            continue
        
        # Create liquidation plan
        plan = create_liquidation_plan(
            scored,
            withdrawal_from_account,
            account_type,
            target_allocation,
        )
        
        plans[account_type] = plan
        remaining_need -= plan.total_selected
        
        logger.info(
            f"Planned ${plan.total_selected:,.0f} withdrawal from {account_type}, "
            f"${remaining_need:,.0f} remaining"
        )
    
    if remaining_need > 0:
        logger.warning(
            f"Unable to meet full withdrawal need: ${remaining_need:,.0f} shortfall"
        )
    
    return plans


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def format_liquidation_summary(plans: Dict[str, LiquidationPlan]) -> str:
    """
    Format a human-readable summary of liquidation plans.
    
    Args:
        plans: Dict mapping account_type to LiquidationPlan
    
    Returns:
        Formatted string summary
    """
    lines = [
        "Multi-Account Liquidation Summary",
        "=" * 60,
        ""
    ]
    
    total_withdrawn = sum(p.total_selected for p in plans.values())
    total_tax = sum(p.estimated_tax for p in plans.values())
    total_securities = sum(len(p.securities) for p in plans.values())
    
    lines.append(f"Total Withdrawn: ${total_withdrawn:,.2f}")
    lines.append(f"Total Tax: ${total_tax:,.2f}")
    lines.append(f"Total Securities: {total_securities}")
    lines.append("")
    
    for account_type, plan in plans.items():
        lines.append(f"\n{account_type} Account:")
        lines.append("-" * 40)
        lines.append(f"  Amount: ${plan.total_selected:,.2f}")
        lines.append(f"  Securities: {len(plan.securities)}")
        lines.append(f"  Tax: ${plan.estimated_tax:,.2f}")
        
        if plan.securities:
            lines.append("  Top Securities:")
            for liq in plan.securities[:3]:
                lines.append(
                    f"    • {liq.symbol}: ${liq.amount_to_liquidate:,.0f} "
                    f"({liq.reason})"
                )
    
    return "\n".join(lines)

# Made with Bob
