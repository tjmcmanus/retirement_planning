"""
Replacement Stock Selector
==========================
Select replacement stocks for tax loss harvesting to avoid wash sales.

This module provides functionality to:
- Find suitable replacement stocks in the same sector
- Sort by market cap (prefer larger or smaller)
- Avoid wash sale violations
- Provide multiple alternative suggestions
- Support cross-sector replacements when needed

Strategy: Sector-based with market cap sorting

Author: Bob
Date: April 17, 2026
Version: 1.0
"""

from __future__ import annotations

import logging
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from components.rsp_holdings_fetcher import (
    RSPConstituent,
    load_constituents,
    get_constituent
)
from components.sector_classifier import (
    get_sector_constituents,
    get_adjacent_sectors
)

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

WASH_SALE_WINDOW_DAYS = 30  # IRS wash sale rule: 30 days before/after


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ReplacementCandidate:
    """
    Represents a candidate replacement stock.
    
    Attributes:
        symbol: Stock ticker symbol
        name: Company name
        sector: GICS sector
        market_cap: Market capitalization
        current_price: Current stock price
        reason: Why this stock was selected
        priority: Priority ranking (1 = highest)
        is_same_sector: True if same sector as original
        similarity_score: Similarity score (0-100)
    """
    symbol: str
    name: str
    sector: str
    market_cap: float
    current_price: float
    reason: str
    priority: int
    is_same_sector: bool
    similarity_score: float
    
    def __repr__(self) -> str:
        return (
            f"ReplacementCandidate({self.symbol}, "
            f"sector={self.sector}, "
            f"priority={self.priority}, "
            f"score={self.similarity_score:.1f})"
        )


# ==============================================================================
# WASH SALE CHECKING
# ==============================================================================

def check_wash_sale_risk(
    symbol: str,
    recent_sales: List[Dict],
    check_date: Optional[datetime] = None
) -> Tuple[bool, str]:
    """
    Check if a symbol has wash sale risk.
    
    Args:
        symbol: Stock symbol to check
        recent_sales: List of recent sales with 'symbol', 'date', 'gain_loss'
        check_date: Date to check from (default: today)
    
    Returns:
        Tuple of (has_risk, reason)
    """
    if check_date is None:
        check_date = datetime.now()
    
    if not recent_sales:
        return False, "No recent sales"
    
    # Check for sales of this symbol in the last 30 days
    for sale in recent_sales:
        if sale.get('symbol') != symbol:
            continue
        
        sale_date = sale.get('date')
        if isinstance(sale_date, str):
            sale_date = datetime.fromisoformat(sale_date)
        
        if not sale_date:
            continue
        
        days_ago = (check_date - sale_date).days
        
        # Only care about loss sales
        gain_loss = sale.get('gain_loss', 0)
        if gain_loss >= 0:
            continue
        
        # Check if within wash sale window
        if 0 <= days_ago <= WASH_SALE_WINDOW_DAYS:
            return True, f"Sold at loss {days_ago} days ago (within 30-day window)"
    
    return False, "No wash sale risk"


def get_owned_symbols(
    portfolio_positions: List[Dict],
    account_name: Optional[str] = None
) -> Set[str]:
    """
    Get set of currently owned symbols.
    
    Args:
        portfolio_positions: List of current positions
        account_name: Filter by account (optional)
    
    Returns:
        Set of owned symbols
    """
    owned = set()
    
    for position in portfolio_positions:
        if account_name and position.get('account_name') != account_name:
            continue
        
        symbol = position.get('symbol')
        shares = position.get('shares', 0)
        
        if symbol and shares > 0:
            owned.add(symbol)
    
    return owned


# ==============================================================================
# REPLACEMENT SELECTION
# ==============================================================================

def find_replacement_stock(
    harvested_symbol: str,
    owned_symbols: Set[str],
    recent_sales: Optional[List[Dict]] = None,
    prefer_larger_cap: bool = True,
    allow_cross_sector: bool = False,
    min_market_cap: float = 1e9,
    num_alternatives: int = 3
) -> List[ReplacementCandidate]:
    """
    Find suitable replacement stocks for a harvested position.
    
    Args:
        harvested_symbol: Stock being sold at a loss
        owned_symbols: Set of currently owned symbols (to avoid)
        recent_sales: Recent sales for wash sale checking
        prefer_larger_cap: Prefer larger market cap stocks
        allow_cross_sector: Allow replacements from adjacent sectors
        min_market_cap: Minimum market cap for replacements (default: $1B)
        num_alternatives: Number of alternatives to return
    
    Returns:
        List of ReplacementCandidate objects, sorted by priority
    """
    if recent_sales is None:
        recent_sales = []
    
    # Get the harvested stock info
    harvested = get_constituent(harvested_symbol)
    if not harvested:
        logger.error(f"Stock {harvested_symbol} not found in RSP constituents")
        return []
    
    logger.info(f"Finding replacement for {harvested_symbol} ({harvested.sector})")
    
    candidates = []
    
    # 1. Try same sector first
    same_sector_candidates = _find_in_sector(
        sector=harvested.sector,
        exclude_symbols=owned_symbols | {harvested_symbol},
        recent_sales=recent_sales,
        prefer_larger_cap=prefer_larger_cap,
        min_market_cap=min_market_cap,
        num_candidates=num_alternatives
    )
    
    for i, candidate in enumerate(same_sector_candidates):
        candidates.append(ReplacementCandidate(
            symbol=candidate.symbol,
            name=candidate.name,
            sector=candidate.sector,
            market_cap=candidate.market_cap,
            current_price=candidate.current_price,
            reason=f"Same sector ({candidate.sector}), next largest by market cap",
            priority=i + 1,
            is_same_sector=True,
            similarity_score=100.0 - (i * 5)  # Decrease score for lower priority
        ))
    
    # 2. If not enough same-sector candidates and cross-sector allowed
    if len(candidates) < num_alternatives and allow_cross_sector:
        logger.info(f"Only found {len(candidates)} same-sector candidates, looking in adjacent sectors")
        
        adjacent_sectors = get_adjacent_sectors(harvested.sector)
        
        for adj_sector in adjacent_sectors:
            if len(candidates) >= num_alternatives:
                break
            
            adj_candidates = _find_in_sector(
                sector=adj_sector,
                exclude_symbols=owned_symbols | {harvested_symbol} | {c.symbol for c in candidates},
                recent_sales=recent_sales,
                prefer_larger_cap=prefer_larger_cap,
                min_market_cap=min_market_cap,
                num_candidates=num_alternatives - len(candidates)
            )
            
            for candidate in adj_candidates:
                candidates.append(ReplacementCandidate(
                    symbol=candidate.symbol,
                    name=candidate.name,
                    sector=candidate.sector,
                    market_cap=candidate.market_cap,
                    current_price=candidate.current_price,
                    reason=f"Adjacent sector ({candidate.sector})",
                    priority=len(candidates) + 1,
                    is_same_sector=False,
                    similarity_score=70.0 - (len(candidates) * 5)
                ))
    
    logger.info(f"Found {len(candidates)} replacement candidates for {harvested_symbol}")
    
    return candidates[:num_alternatives]


def _find_in_sector(
    sector: str,
    exclude_symbols: Set[str],
    recent_sales: List[Dict],
    prefer_larger_cap: bool,
    min_market_cap: float,
    num_candidates: int
) -> List[RSPConstituent]:
    """
    Find replacement candidates within a specific sector.

    Candidates are sorted by market indicator preference first
    (strong_buy → buy → hold → caution → sell → unknown), then by
    market cap within each indicator tier.

    Args:
        sector: GICS sector to search
        exclude_symbols: Symbols to exclude
        recent_sales: Recent sales for wash sale checking
        prefer_larger_cap: Prefer larger market cap
        min_market_cap: Minimum market cap
        num_candidates: Number of candidates to return

    Returns:
        List of RSPConstituent objects
    """
    # Get all stocks in sector, sorted by market cap
    sector_stocks = get_sector_constituents(sector, sort_by='market_cap')

    # Reverse if prefer smaller cap
    if not prefer_larger_cap:
        sector_stocks = list(reversed(sector_stocks))

    # Re-sort by indicator priority (primary) then market cap (secondary).
    # indicator_priority: 1 = strong_buy … 6 = unknown, so ascending = best first.
    # Market cap direction is preserved by negating for descending within each tier.
    cap_sign = -1 if prefer_larger_cap else 1
    sector_stocks = sorted(
        sector_stocks,
        key=lambda s: (s.indicator_priority, cap_sign * s.market_cap)
    )
    
    candidates = []
    
    for stock in sector_stocks:
        # Skip if already have enough
        if len(candidates) >= num_candidates:
            break
        
        # Skip if excluded
        if stock.symbol in exclude_symbols:
            continue
        
        # Skip if below minimum market cap
        if stock.market_cap < min_market_cap:
            continue
        
        # Skip if invalid price
        if stock.current_price <= 0:
            continue
        
        # Check wash sale risk
        has_risk, reason = check_wash_sale_risk(stock.symbol, recent_sales)
        if has_risk:
            logger.debug(f"Skipping {stock.symbol}: {reason}")
            continue
        
        candidates.append(stock)
    
    return candidates


# ==============================================================================
# BATCH REPLACEMENT FINDING
# ==============================================================================

def find_replacements_batch(
    harvest_symbols: List[str],
    owned_symbols: Set[str],
    recent_sales: Optional[List[Dict]] = None,
    prefer_larger_cap: bool = True,
    allow_cross_sector: bool = False,
    min_market_cap: float = 1e9,
    num_alternatives: int = 3
) -> Dict[str, List[ReplacementCandidate]]:
    """
    Find replacements for multiple stocks at once.
    
    Args:
        harvest_symbols: List of symbols being harvested
        owned_symbols: Set of currently owned symbols
        recent_sales: Recent sales for wash sale checking
        prefer_larger_cap: Prefer larger market cap stocks
        allow_cross_sector: Allow replacements from adjacent sectors
        min_market_cap: Minimum market cap for replacements
        num_alternatives: Number of alternatives per stock
    
    Returns:
        Dictionary mapping symbol to list of replacement candidates
    """
    replacements = {}
    
    # Track symbols we're using as replacements to avoid duplicates
    used_replacements = set()
    
    for symbol in harvest_symbols:
        # Exclude symbols we're harvesting and already used replacements
        exclude = owned_symbols | set(harvest_symbols) | used_replacements
        
        candidates = find_replacement_stock(
            harvested_symbol=symbol,
            owned_symbols=exclude,
            recent_sales=recent_sales,
            prefer_larger_cap=prefer_larger_cap,
            allow_cross_sector=allow_cross_sector,
            min_market_cap=min_market_cap,
            num_alternatives=num_alternatives
        )
        
        replacements[symbol] = candidates
        
        # Mark top candidate as used
        if candidates:
            used_replacements.add(candidates[0].symbol)
    
    return replacements


# ==============================================================================
# REPLACEMENT VALIDATION
# ==============================================================================

def validate_replacement(
    original_symbol: str,
    replacement_symbol: str,
    owned_symbols: Set[str],
    recent_sales: Optional[List[Dict]] = None
) -> Tuple[bool, str]:
    """
    Validate that a replacement is suitable.
    
    Args:
        original_symbol: Original stock being sold
        replacement_symbol: Proposed replacement
        owned_symbols: Currently owned symbols
        recent_sales: Recent sales for wash sale checking
    
    Returns:
        Tuple of (is_valid, reason)
    """
    # Check if replacement is the same as original
    if replacement_symbol == original_symbol:
        return False, "Replacement cannot be the same as original (wash sale)"
    
    # Check if already owned
    if replacement_symbol in owned_symbols:
        return False, f"Already own {replacement_symbol} (wash sale risk)"
    
    # Check if replacement exists in RSP
    replacement = get_constituent(replacement_symbol)
    if not replacement:
        return False, f"{replacement_symbol} not found in RSP constituents"
    
    # Check wash sale risk
    if recent_sales:
        has_risk, reason = check_wash_sale_risk(replacement_symbol, recent_sales)
        if has_risk:
            return False, f"Wash sale risk: {reason}"
    
    # Check if replacement has valid price
    if replacement.current_price <= 0:
        return False, f"Invalid price for {replacement_symbol}"
    
    return True, "Valid replacement"


# ==============================================================================
# REPLACEMENT MAPPING MANAGEMENT
# ==============================================================================

def build_replacement_mappings(
    prefer_larger_cap: bool = True,
    min_market_cap: float = 1e9
) -> Dict[str, List[str]]:
    """
    Pre-build replacement mappings for all RSP constituents.
    
    This creates a lookup table of primary -> [secondary1, secondary2, ...]
    for faster replacement selection.
    
    Args:
        prefer_larger_cap: Prefer larger market cap stocks
        min_market_cap: Minimum market cap for replacements
    
    Returns:
        Dictionary mapping symbol to list of replacement symbols
    """
    logger.info("Building replacement mappings for all RSP constituents...")
    
    constituents = load_constituents()
    mappings = {}
    
    for i, constituent in enumerate(constituents):
        if i > 0 and i % 100 == 0:
            logger.info(f"Processed {i}/{len(constituents)} stocks...")
        
        # Find replacements (excluding the stock itself)
        candidates = find_replacement_stock(
            harvested_symbol=constituent.symbol,
            owned_symbols=set(),  # Empty set for pre-building
            recent_sales=[],
            prefer_larger_cap=prefer_larger_cap,
            allow_cross_sector=False,  # Only same sector for pre-built mappings
            min_market_cap=min_market_cap,
            num_alternatives=5  # Store top 5
        )
        
        mappings[constituent.symbol] = [c.symbol for c in candidates]
    
    logger.info(f"Built replacement mappings for {len(mappings)} stocks")
    
    return mappings


def save_replacement_mappings_to_db(
    mappings: Dict[str, List[str]],
    db_path: str = "data/rsp_holdings.db"
) -> None:
    """
    Save replacement mappings to database.
    
    Args:
        mappings: Dictionary of symbol -> replacement list
        db_path: Path to database
    """
    import sqlite3
    from pathlib import Path
    
    conn = sqlite3.connect(Path(db_path))
    cursor = conn.cursor()
    
    # Clear existing mappings
    cursor.execute("DELETE FROM replacement_mappings")
    
    # Insert new mappings
    for primary_symbol, replacement_list in mappings.items():
        # Get sector
        constituent = get_constituent(primary_symbol)
        sector = constituent.sector if constituent else "Unknown"
        
        for priority, secondary_symbol in enumerate(replacement_list, 1):
            cursor.execute("""
                INSERT INTO replacement_mappings 
                (primary_symbol, secondary_symbol, sector, priority, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (primary_symbol, secondary_symbol, sector, priority))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Saved {len(mappings)} replacement mappings to database")


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Replacement Stock Selector")
    print("=" * 60)
    
    # Test finding replacement for a specific stock
    test_symbol = "AAPL"
    print(f"\nFinding replacement for {test_symbol}...")
    
    # Simulate owned stocks
    owned = {"MSFT", "GOOGL", "AMZN"}
    
    candidates = find_replacement_stock(
        harvested_symbol=test_symbol,
        owned_symbols=owned,
        recent_sales=[],
        prefer_larger_cap=True,
        allow_cross_sector=False,
        num_alternatives=3
    )
    
    print(f"\nFound {len(candidates)} replacement candidates:")
    for candidate in candidates:
        print(f"\n  Priority {candidate.priority}: {candidate.symbol}")
        print(f"    Name: {candidate.name}")
        print(f"    Sector: {candidate.sector}")
        print(f"    Market Cap: ${candidate.market_cap/1e9:.2f}B")
        print(f"    Price: ${candidate.current_price:.2f}")
        print(f"    Reason: {candidate.reason}")
        print(f"    Similarity Score: {candidate.similarity_score:.1f}")
    
    # Test batch replacement
    print("\n" + "=" * 60)
    print("Testing batch replacement...")
    
    harvest_list = ["AAPL", "MSFT", "GOOGL"]
    batch_replacements = find_replacements_batch(
        harvest_symbols=harvest_list,
        owned_symbols=owned,
        num_alternatives=2
    )
    
    print(f"\nBatch replacements for {len(harvest_list)} stocks:")
    for symbol, candidates in batch_replacements.items():
        print(f"\n  {symbol}:")
        for candidate in candidates:
            print(f"    → {candidate.symbol} ({candidate.sector})")
    
    # Test validation
    print("\n" + "=" * 60)
    print("Testing replacement validation...")
    
    is_valid, reason = validate_replacement(
        original_symbol="AAPL",
        replacement_symbol="NVDA",
        owned_symbols=owned
    )
    
    print(f"\nValidation: AAPL → NVDA")
    print(f"  Valid: {is_valid}")
    print(f"  Reason: {reason}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

# Made with Bob
