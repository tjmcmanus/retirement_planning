"""
Direct Index Harvester
======================
Scan for tax loss harvesting opportunities in direct index positions.

This module provides functionality to:
- Identify positions with losses exceeding threshold
- Calculate estimated tax savings
- Apply configurable thresholds
- Check wash sale rules
- Find replacement stocks
- Priority scoring for harvest opportunities

Author: Bob
Date: April 17, 2026
Version: 1.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import pandas as pd
import numpy as np

from components.cost_basis_tracker import (
    get_tax_lots,
    TaxLot,
    GainType
)
from components.replacement_selector import (
    find_replacement_stock,
    get_owned_symbols,
    ReplacementCandidate
)
from components.rsp_holdings_fetcher import load_constituents

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

CONFIG_PATH = Path("config/direct_indexing_config.yaml")

# Default thresholds (overridden by config)
DEFAULT_LOSS_THRESHOLD_PCT = 10.0
DEFAULT_MIN_LOSS_AMOUNT = 500.0
DEFAULT_GAINS_THRESHOLD_PCT = 15.0


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class HarvestOpportunity:
    """
    Represents a tax loss harvesting opportunity.
    
    Attributes:
        symbol: Stock ticker symbol
        account_name: Account holding this position
        account_type: Account type
        shares: Number of shares
        purchase_price: Average purchase price
        current_price: Current market price
        purchase_date: Purchase date (or average for multiple lots)
        
        # Loss details
        unrealized_loss: Unrealized loss amount (negative)
        loss_percentage: Loss as percentage
        holding_period_days: Days held
        is_long_term: True if held > 365 days
        
        # Tax impact
        estimated_tax_savings: Estimated tax savings from harvest
        ltcg_rate: Long-term capital gains rate
        marginal_rate: Marginal ordinary income rate
        
        # Replacement
        recommended_replacement: Primary replacement symbol
        replacement_sector: Sector of replacement
        replacement_price: Current price of replacement
        alternative_replacements: List of alternative replacements
        
        # Validation
        is_wash_sale_risk: True if wash sale risk exists
        wash_sale_reason: Reason for wash sale risk
        can_harvest: True if safe to harvest
        harvest_priority: Priority score (1-5, higher = better)
        
        # Metadata
        lot_ids: List of lot IDs involved
        notes: Additional notes
    """
    symbol: str
    account_name: str
    account_type: str
    shares: float
    purchase_price: float
    current_price: float
    purchase_date: date
    
    # Loss details
    unrealized_loss: float
    loss_percentage: float
    holding_period_days: int
    is_long_term: bool
    
    # Tax impact
    estimated_tax_savings: float
    ltcg_rate: float
    marginal_rate: float
    
    # Replacement
    recommended_replacement: Optional[str]
    replacement_sector: str
    replacement_price: float
    alternative_replacements: List[str]
    
    # Validation
    is_wash_sale_risk: bool
    wash_sale_reason: str
    can_harvest: bool
    harvest_priority: int
    
    # Metadata
    lot_ids: List[str]
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['purchase_date'] = self.purchase_date.isoformat()
        return d


# ==============================================================================
# CONFIGURATION
# ==============================================================================

def load_config() -> Dict:
    """Load configuration from YAML file."""
    if not CONFIG_PATH.exists():
        logger.warning(f"Config file not found: {CONFIG_PATH}, using defaults")
        return {
            'direct_indexing': {
                'thresholds': {
                    'loss_threshold_pct': DEFAULT_LOSS_THRESHOLD_PCT,
                    'min_loss_amount': DEFAULT_MIN_LOSS_AMOUNT,
                    'enable_gains_harvesting': True,
                    'gains_threshold_pct': DEFAULT_GAINS_THRESHOLD_PCT
                }
            }
        }

    try:
        import yaml
    except ModuleNotFoundError:
        logger.warning("PyYAML not installed, using default direct indexing config")
        return {
            'direct_indexing': {
                'thresholds': {
                    'loss_threshold_pct': DEFAULT_LOSS_THRESHOLD_PCT,
                    'min_loss_amount': DEFAULT_MIN_LOSS_AMOUNT,
                    'enable_gains_harvesting': True,
                    'gains_threshold_pct': DEFAULT_GAINS_THRESHOLD_PCT
                }
            }
        }

    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


# ==============================================================================
# TAX CALCULATIONS
# ==============================================================================

def get_ltcg_rate(agi: float, filing_status: str = 'single') -> float:
    """
    Get long-term capital gains rate based on AGI.
    
    Args:
        agi: Adjusted Gross Income
        filing_status: Tax filing status
    
    Returns:
        LTCG rate (0.0, 0.15, or 0.20)
    """
    # 2024 thresholds (simplified)
    if filing_status == 'single':
        if agi <= 44_625:
            return 0.0
        elif agi <= 492_300:
            return 0.15
        else:
            return 0.20
    elif filing_status == 'married':
        if agi <= 89_250:
            return 0.0
        elif agi <= 553_850:
            return 0.15
        else:
            return 0.20
    else:
        # Default to 15%
        return 0.15


def calculate_tax_savings(
    loss_amount: float,
    is_long_term: bool,
    ltcg_rate: float,
    marginal_rate: float
) -> float:
    """
    Calculate estimated tax savings from harvesting a loss.
    
    Args:
        loss_amount: Amount of loss (positive number)
        is_long_term: True if long-term holding
        ltcg_rate: Long-term capital gains rate
        marginal_rate: Marginal ordinary income rate
    
    Returns:
        Estimated tax savings
    """
    # Losses offset gains first, then up to $3,000 of ordinary income
    # For simplicity, assume losses offset capital gains at LTCG rate
    # In reality, would need to know if user has other gains
    
    if is_long_term:
        # Long-term losses offset long-term gains
        tax_savings = abs(loss_amount) * ltcg_rate
    else:
        # Short-term losses offset ordinary income (up to $3,000)
        # Use marginal rate for short-term
        tax_savings = min(abs(loss_amount), 3000) * marginal_rate
    
    return tax_savings


# ==============================================================================
# HARVEST SCANNING
# ==============================================================================

def scan_harvest_opportunities(
    account_name: str,
    account_type: str = 'Brokerage',
    current_agi: float = 0,
    filing_status: str = 'single',
    marginal_rate: float = 0.24,
    recent_sales: Optional[List[Dict]] = None,
    loss_threshold_pct: Optional[float] = None,
    min_loss_amount: Optional[float] = None,
    enable_gains_harvesting: bool = False,
    gains_threshold_pct: Optional[float] = None
) -> List[HarvestOpportunity]:
    """
    Scan for tax loss harvesting opportunities.
    
    Args:
        account_name: Account to scan
        account_type: Account type (usually Brokerage)
        current_agi: Current AGI for tax calculations
        filing_status: Tax filing status
        marginal_rate: Marginal ordinary income tax rate
        recent_sales: Recent sales for wash sale checking
        loss_threshold_pct: Minimum loss % (overrides config)
        min_loss_amount: Minimum loss $ (overrides config)
        enable_gains_harvesting: Consider gains in 0% bracket
        gains_threshold_pct: Minimum gain % for harvesting
    
    Returns:
        List of HarvestOpportunity objects, sorted by priority
    """
    logger.info(f"Scanning for harvest opportunities in {account_name}")
    
    # Load config
    config = load_config()
    thresholds = config.get('direct_indexing', {}).get('thresholds', {})
    
    # Use provided values or config defaults
    loss_threshold_pct = loss_threshold_pct if loss_threshold_pct is not None else thresholds.get('loss_threshold_pct', DEFAULT_LOSS_THRESHOLD_PCT)
    min_loss_amount = min_loss_amount if min_loss_amount is not None else thresholds.get('min_loss_amount', DEFAULT_MIN_LOSS_AMOUNT)
    gains_threshold_pct = gains_threshold_pct if gains_threshold_pct is not None else thresholds.get('gains_threshold_pct', DEFAULT_GAINS_THRESHOLD_PCT)
    
    if recent_sales is None:
        recent_sales = []
    
    # Get LTCG rate
    ltcg_rate = get_ltcg_rate(current_agi, filing_status)
    
    # Get all tax lots for this account
    lots = get_tax_lots(account_name=account_name, account_type=account_type)
    
    if not lots:
        logger.warning(f"No tax lots found in {account_name}")
        return []
    
    # Get current prices
    constituents = load_constituents()
    current_prices = {c.symbol: c.current_price for c in constituents}
    
    # Get owned symbols for replacement selection
    owned_symbols = {lot.symbol for lot in lots}
    
    # Group lots by symbol
    lots_by_symbol = {}
    for lot in lots:
        if lot.symbol not in lots_by_symbol:
            lots_by_symbol[lot.symbol] = []
        lots_by_symbol[lot.symbol].append(lot)
    
    opportunities = []
    
    for symbol, symbol_lots in lots_by_symbol.items():
        current_price = current_prices.get(symbol, 0)
        
        if current_price <= 0:
            logger.debug(f"Skipping {symbol}: no current price")
            continue
        
        # Calculate aggregate position
        total_shares = sum(lot.shares for lot in symbol_lots)
        total_cost_basis = sum(lot.cost_basis for lot in symbol_lots)
        avg_purchase_price = total_cost_basis / total_shares if total_shares > 0 else 0
        
        current_value = total_shares * current_price
        unrealized_gl = current_value - total_cost_basis
        unrealized_gl_pct = (unrealized_gl / total_cost_basis * 100) if total_cost_basis > 0 else 0
        
        # Calculate average holding period
        total_days = sum(lot.holding_period_days() * lot.shares for lot in symbol_lots)
        avg_holding_days = int(total_days / total_shares) if total_shares > 0 else 0
        is_long_term = avg_holding_days > 365
        
        # Average purchase date (weighted by shares)
        total_date_weight = sum(
            (lot.purchase_date.toordinal() * lot.shares) 
            for lot in symbol_lots
        )
        avg_date_ordinal = int(total_date_weight / total_shares) if total_shares > 0 else date.today().toordinal()
        avg_purchase_date = date.fromordinal(avg_date_ordinal)
        
        # Check if this is a harvest opportunity
        is_loss = unrealized_gl < 0
        is_gain = unrealized_gl > 0
        
        # Loss harvesting
        if is_loss:
            loss_amount = abs(unrealized_gl)
            loss_pct = abs(unrealized_gl_pct)
            
            # Check thresholds
            if loss_pct < loss_threshold_pct:
                logger.debug(f"Skipping {symbol}: loss {loss_pct:.1f}% below threshold {loss_threshold_pct}%")
                continue
            
            if loss_amount < min_loss_amount:
                logger.debug(f"Skipping {symbol}: loss ${loss_amount:.2f} below minimum ${min_loss_amount}")
                continue
            
            # Calculate tax savings
            tax_savings = calculate_tax_savings(
                loss_amount=loss_amount,
                is_long_term=is_long_term,
                ltcg_rate=ltcg_rate,
                marginal_rate=marginal_rate
            )
            
            # Find replacement
            replacements = find_replacement_stock(
                harvested_symbol=symbol,
                owned_symbols=owned_symbols,
                recent_sales=recent_sales,
                num_alternatives=3
            )
            
            recommended = replacements[0] if replacements else None
            alternatives = [r.symbol for r in replacements[1:]] if len(replacements) > 1 else []
            
            # Check wash sale risk
            from components.replacement_selector import check_wash_sale_risk
            is_wash_risk, wash_reason = check_wash_sale_risk(symbol, recent_sales)
            
            # Create opportunity
            opportunity = HarvestOpportunity(
                symbol=symbol,
                account_name=account_name,
                account_type=account_type,
                shares=total_shares,
                purchase_price=avg_purchase_price,
                current_price=current_price,
                purchase_date=avg_purchase_date,
                unrealized_loss=unrealized_gl,
                loss_percentage=unrealized_gl_pct,
                holding_period_days=avg_holding_days,
                is_long_term=is_long_term,
                estimated_tax_savings=tax_savings,
                ltcg_rate=ltcg_rate,
                marginal_rate=marginal_rate,
                recommended_replacement=recommended.symbol if recommended else None,
                replacement_sector=recommended.sector if recommended else "",
                replacement_price=recommended.current_price if recommended else 0,
                alternative_replacements=alternatives,
                is_wash_sale_risk=is_wash_risk,
                wash_sale_reason=wash_reason,
                can_harvest=not is_wash_risk and recommended is not None,
                harvest_priority=0,  # Will calculate below
                lot_ids=[lot.lot_id for lot in symbol_lots]
            )
            
            # Calculate priority
            opportunity.harvest_priority = calculate_harvest_priority(opportunity)
            
            opportunities.append(opportunity)
        
        # Gains harvesting (if in 0% LTCG bracket)
        elif is_gain and enable_gains_harvesting and ltcg_rate == 0.0:
            gain_amount = unrealized_gl
            gain_pct = unrealized_gl_pct
            
            # Check threshold
            if gain_pct < gains_threshold_pct:
                continue
            
            # Only harvest long-term gains in 0% bracket
            if not is_long_term:
                continue
            
            # For gains harvesting, we don't need a replacement
            # Just sell and immediately rebuy at same price
            opportunity = HarvestOpportunity(
                symbol=symbol,
                account_name=account_name,
                account_type=account_type,
                shares=total_shares,
                purchase_price=avg_purchase_price,
                current_price=current_price,
                purchase_date=avg_purchase_date,
                unrealized_loss=unrealized_gl,  # Actually a gain
                loss_percentage=unrealized_gl_pct,
                holding_period_days=avg_holding_days,
                is_long_term=is_long_term,
                estimated_tax_savings=0.0,  # No tax on 0% bracket
                ltcg_rate=ltcg_rate,
                marginal_rate=marginal_rate,
                recommended_replacement=symbol,  # Rebuy same stock
                replacement_sector="",
                replacement_price=current_price,
                alternative_replacements=[],
                is_wash_sale_risk=False,
                wash_sale_reason="",
                can_harvest=True,
                harvest_priority=2,  # Lower priority than loss harvesting
                lot_ids=[lot.lot_id for lot in symbol_lots],
                notes="Gains harvesting in 0% LTCG bracket - step up cost basis"
            )
            
            opportunities.append(opportunity)
    
    # Sort by priority (descending)
    opportunities.sort(key=lambda x: x.harvest_priority, reverse=True)
    
    logger.info(f"Found {len(opportunities)} harvest opportunities")
    
    return opportunities


def calculate_harvest_priority(opp: HarvestOpportunity) -> int:
    """
    Calculate priority score (1-5) for harvest opportunity.
    
    Factors:
    - Loss magnitude (larger = higher priority)
    - Tax savings potential
    - Holding period (long-term preferred)
    - Replacement availability
    - Wash sale risk (none = higher priority)
    
    Args:
        opp: HarvestOpportunity object
    
    Returns:
        Priority score: 5 (highest) to 1 (lowest)
    """
    score = 0
    
    # Loss magnitude (0-2 points)
    loss_pct = abs(opp.loss_percentage)
    if loss_pct >= 20:
        score += 2
    elif loss_pct >= 15:
        score += 1
    
    # Tax savings (0-1 point)
    if opp.estimated_tax_savings >= 1000:
        score += 1
    
    # Long-term holding (0-1 point)
    if opp.is_long_term:
        score += 1
    
    # Good replacement available (0-1 point)
    if opp.recommended_replacement and not opp.is_wash_sale_risk:
        score += 1
    
    # Ensure score is 1-5
    return max(1, min(score, 5))


# ==============================================================================
# REPORTING
# ==============================================================================

def generate_harvest_report(
    opportunities: List[HarvestOpportunity]
) -> pd.DataFrame:
    """
    Generate a DataFrame report of harvest opportunities.
    
    Args:
        opportunities: List of HarvestOpportunity objects
    
    Returns:
        DataFrame with harvest details
    """
    if not opportunities:
        return pd.DataFrame()
    
    data = [opp.to_dict() for opp in opportunities]
    df = pd.DataFrame(data)
    
    # Select and order columns
    columns = [
        'symbol', 'harvest_priority', 'loss_percentage', 'unrealized_loss',
        'estimated_tax_savings', 'holding_period_days', 'is_long_term',
        'recommended_replacement', 'can_harvest', 'is_wash_sale_risk'
    ]
    
    # Only include columns that exist
    columns = [c for c in columns if c in df.columns]
    
    result = df[columns]
    return result if isinstance(result, pd.DataFrame) else pd.DataFrame()


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Direct Index Harvester")
    print("=" * 60)
    
    # Test scanning (will be empty unless database has positions)
    print("\nScanning for harvest opportunities...")
    
    opportunities = scan_harvest_opportunities(
        account_name="Schwab Brokerage",
        account_type="Brokerage",
        current_agi=100000,
        filing_status="single",
        marginal_rate=0.24,
        loss_threshold_pct=10.0,
        min_loss_amount=500.0
    )
    
    print(f"\nFound {len(opportunities)} opportunities")
    
    if opportunities:
        print("\nTop opportunities:")
        for i, opp in enumerate(opportunities[:5], 1):
            print(f"\n{i}. {opp.symbol} - Priority {opp.harvest_priority}")
            print(f"   Loss: ${opp.unrealized_loss:,.2f} ({opp.loss_percentage:.1f}%)")
            print(f"   Tax Savings: ${opp.estimated_tax_savings:,.2f}")
            print(f"   Replacement: {opp.recommended_replacement or 'None'}")
            print(f"   Can Harvest: {opp.can_harvest}")
    else:
        print("\nNo harvest opportunities found")
        print("(This is expected if no positions are in the database)")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

# Made with Bob
