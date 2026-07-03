"""
Sector Classifier
=================
Classify stocks by GICS sectors and create sector groups for Direct Indexing.

This module provides functionality to:
- Classify stocks by GICS sectors
- Get sector constituents
- Calculate sector weights
- Support sector-based replacement stock selection

Author: Bob
Date: April 16, 2026
Version: 1.0
"""

from __future__ import annotations

import logging
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

import pandas as pd
import numpy as np

from components.rsp_holdings_fetcher import (
    RSPConstituent,
    load_constituents,
    get_constituent,
    GICS_SECTORS
)

logger = logging.getLogger(__name__)

# ==============================================================================
# SECTOR CLASSIFICATION
# ==============================================================================

def get_sector_constituents(
    sector: str,
    sort_by: str = 'market_cap'
) -> List[RSPConstituent]:
    """
    Get all RSP constituents in a specific sector.
    
    Args:
        sector: GICS sector name
        sort_by: Sort key ('market_cap', 'symbol', 'price')
    
    Returns:
        List of constituents in that sector, sorted
    """
    constituents = load_constituents()
    sector_stocks = [c for c in constituents if c.sector == sector]
    
    # Sort
    if sort_by == 'market_cap':
        sector_stocks.sort(key=lambda x: x.market_cap, reverse=True)
    elif sort_by == 'symbol':
        sector_stocks.sort(key=lambda x: x.symbol)
    elif sort_by == 'price':
        sector_stocks.sort(key=lambda x: x.current_price, reverse=True)
    
    return sector_stocks


def get_stock_sector(symbol: str) -> Optional[str]:
    """
    Get the GICS sector for a specific stock.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        GICS sector name, or None if not found
    """
    constituent = get_constituent(symbol)
    return constituent.sector if constituent else None


def get_all_sectors() -> List[str]:
    """
    Get list of all GICS sectors represented in RSP.
    
    Returns:
        List of sector names
    """
    constituents = load_constituents()
    sectors = set(c.sector for c in constituents)
    
    # Return in standard GICS order
    return [s for s in GICS_SECTORS if s in sectors]


def get_sector_weights(
    portfolio_df: Optional[pd.DataFrame] = None
) -> Dict[str, float]:
    """
    Calculate sector weights in portfolio or RSP.
    
    Args:
        portfolio_df: Portfolio DataFrame (if None, uses RSP equal weights)
    
    Returns:
        Dictionary mapping sector to weight percentage
    """
    if portfolio_df is None:
        # Use RSP equal weights
        constituents = load_constituents()
        total_stocks = len(constituents)
        
        sector_counts = defaultdict(int)
        for c in constituents:
            sector_counts[c.sector] += 1
        
        return {
            sector: (count / total_stocks * 100) if total_stocks > 0 else 0
            for sector, count in sector_counts.items()
        }
    
    else:
        # Calculate from portfolio
        if 'sector' not in portfolio_df.columns or 'market_value' not in portfolio_df.columns:
            logger.warning("Portfolio DataFrame missing required columns")
            return {}
        
        total_value = portfolio_df['market_value'].sum()
        
        if total_value == 0:
            return {}
        
        sector_values = portfolio_df.groupby('sector')['market_value'].sum()
        
        return {
            sector: (value / total_value * 100)
            for sector, value in sector_values.items()
        }


def compare_sector_allocations(
    portfolio_df: pd.DataFrame,
    target_weights: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Compare portfolio sector allocation to target (RSP or custom).
    
    Args:
        portfolio_df: Portfolio DataFrame
        target_weights: Target sector weights (if None, uses RSP)
    
    Returns:
        DataFrame with current, target, and drift columns
    """
    # Get current weights
    current_weights = get_sector_weights(portfolio_df)
    
    # Get target weights (RSP if not provided)
    if target_weights is None:
        target_weights = get_sector_weights()
    
    # Build comparison DataFrame
    sectors = set(list(current_weights.keys()) + list(target_weights.keys()))
    
    data = []
    for sector in sorted(sectors):
        current = current_weights.get(sector, 0.0)
        target = target_weights.get(sector, 0.0)
        drift = current - target
        
        data.append({
            'sector': sector,
            'current_weight': current,
            'target_weight': target,
            'drift': drift,
            'abs_drift': abs(drift)
        })
    
    df = pd.DataFrame(data)
    df = df.sort_values('abs_drift', ascending=False)
    
    return df


# ==============================================================================
# SECTOR GROUPING
# ==============================================================================

def group_by_sector(
    constituents: Optional[List[RSPConstituent]] = None
) -> Dict[str, List[RSPConstituent]]:
    """
    Group constituents by sector.
    
    Args:
        constituents: List of constituents (if None, loads all RSP)
    
    Returns:
        Dictionary mapping sector to list of constituents
    """
    if constituents is None:
        constituents = load_constituents()
    
    groups = defaultdict(list)
    for c in constituents:
        groups[c.sector].append(c)
    
    # Sort each group by market cap
    for sector in groups:
        groups[sector].sort(key=lambda x: x.market_cap, reverse=True)
    
    return dict(groups)


def get_sector_statistics(sector: str) -> Dict[str, Any]:
    """
    Get statistics for a specific sector.
    
    Args:
        sector: GICS sector name
    
    Returns:
        Dictionary with sector statistics
    """
    constituents = get_sector_constituents(sector, sort_by='market_cap')
    
    if not constituents:
        return {
            'sector': sector,
            'num_stocks': 0,
            'total_market_cap': 0.0,
            'avg_market_cap': 0.0,
            'median_market_cap': 0.0,
            'avg_price': 0.0,
            'median_price': 0.0,
            'largest_stock': None,
            'smallest_stock': None
        }
    
    market_caps = [c.market_cap for c in constituents]
    prices = [c.current_price for c in constituents]
    
    return {
        'sector': sector,
        'num_stocks': len(constituents),
        'total_market_cap': sum(market_caps),
        'avg_market_cap': np.mean(market_caps),
        'median_market_cap': np.median(market_caps),
        'avg_price': np.mean(prices),
        'median_price': np.median(prices),
        'largest_stock': constituents[0].symbol if constituents else None,
        'smallest_stock': constituents[-1].symbol if constituents else None
    }


def get_all_sector_statistics() -> pd.DataFrame:
    """
    Get statistics for all sectors.
    
    Returns:
        DataFrame with sector statistics
    """
    sectors = get_all_sectors()
    stats = [get_sector_statistics(sector) for sector in sectors]
    
    df = pd.DataFrame(stats)
    df = df.sort_values('num_stocks', ascending=False)
    
    return df


# ==============================================================================
# SECTOR SIMILARITY
# ==============================================================================

def get_adjacent_sectors(sector: str) -> List[str]:
    """
    Get sectors that are similar/adjacent to the given sector.
    
    This is useful for finding replacement stocks when same-sector
    options are exhausted.
    
    Args:
        sector: GICS sector name
    
    Returns:
        List of similar sectors in order of similarity
    """
    # Define sector similarity groups
    similarity_map = {
        'Information Technology': [
            'Communication Services',
            'Consumer Discretionary',
            'Industrials'
        ],
        'Health Care': [
            'Consumer Staples',
            'Materials',
            'Industrials'
        ],
        'Financials': [
            'Real Estate',
            'Industrials',
            'Consumer Discretionary'
        ],
        'Consumer Discretionary': [
            'Consumer Staples',
            'Information Technology',
            'Communication Services'
        ],
        'Communication Services': [
            'Information Technology',
            'Consumer Discretionary',
            'Industrials'
        ],
        'Industrials': [
            'Materials',
            'Information Technology',
            'Financials'
        ],
        'Consumer Staples': [
            'Consumer Discretionary',
            'Health Care',
            'Materials'
        ],
        'Energy': [
            'Materials',
            'Utilities',
            'Industrials'
        ],
        'Utilities': [
            'Energy',
            'Real Estate',
            'Materials'
        ],
        'Real Estate': [
            'Financials',
            'Utilities',
            'Consumer Discretionary'
        ],
        'Materials': [
            'Industrials',
            'Energy',
            'Consumer Staples'
        ]
    }
    
    return similarity_map.get(sector, [])


# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

def export_sector_summary(output_path: str = "data/sector_summary.csv") -> None:
    """
    Export sector summary to CSV.
    
    Args:
        output_path: Path to output CSV file
    """
    df = get_all_sector_statistics()
    df.to_csv(output_path, index=False)
    logger.info(f"Exported sector summary to {output_path}")


def export_sector_constituents(
    sector: str,
    output_path: Optional[str] = None
) -> None:
    """
    Export constituents of a specific sector to CSV.
    
    Args:
        sector: GICS sector name
        output_path: Path to output CSV file (auto-generated if None)
    """
    constituents = get_sector_constituents(sector)
    
    if not constituents:
        logger.warning(f"No constituents found for sector: {sector}")
        return
    
    # Convert to DataFrame
    data = [c.to_dict() for c in constituents]
    df = pd.DataFrame(data)
    
    # Generate output path if not provided
    if output_path is None:
        sector_slug = sector.lower().replace(' ', '_')
        output_path = f"data/sector_{sector_slug}.csv"
    
    df.to_csv(output_path, index=False)
    logger.info(f"Exported {len(constituents)} {sector} stocks to {output_path}")


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Sector Classifier")
    print("=" * 60)
    
    # Get all sectors
    sectors = get_all_sectors()
    print(f"\nFound {len(sectors)} sectors in RSP")
    
    # Get sector statistics
    print("\nSector Statistics:")
    stats_df = get_all_sector_statistics()
    print(stats_df.to_string(index=False))
    
    # Get sector weights
    print("\nSector Weights (Equal-Weighted RSP):")
    weights = get_sector_weights()
    for sector, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        print(f"  {sector:30s}: {weight:5.2f}%")
    
    # Test sector constituents
    test_sector = "Information Technology"
    print(f"\nTop 5 {test_sector} stocks by market cap:")
    tech_stocks = get_sector_constituents(test_sector, sort_by='market_cap')
    for stock in tech_stocks[:5]:
        print(f"  {stock.symbol:6s} - {stock.name:40s} | ${stock.market_cap/1e9:8.2f}B")
    
    # Test adjacent sectors
    print(f"\nAdjacent sectors to {test_sector}:")
    adjacent = get_adjacent_sectors(test_sector)
    for adj_sector in adjacent:
        print(f"  - {adj_sector}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

# Made with Bob
