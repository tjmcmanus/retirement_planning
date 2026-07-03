"""
Initial Portfolio Generator
============================
Generate complete initial purchase list for Direct Indexing based on RSP.

This module provides functionality to:
- Calculate equal-weight allocation for target investment amount
- Determine share quantities for each stock
- Handle fractional shares and rounding
- Optimize for minimum trade sizes
- Generate formatted purchase instructions
- Export to multiple formats (CSV, Markdown, Schwab-compatible)

Author: Bob
Date: April 16, 2026
Version: 1.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

import pandas as pd
import numpy as np

from components.rsp_holdings_fetcher import (
    RSPConstituent,
    load_constituents,
    fetch_rsp_holdings,
    update_prices
)
from components.sector_classifier import group_by_sector

logger = logging.getLogger(__name__)

PORTFOLIO_TRUTH_FILE = Path("portfolio_data_truth.csv")
TAXABLE_ACCOUNT_TYPES = {"Brokerage"}

# ==============================================================================
# CONSTANTS
# ==============================================================================

DEFAULT_MIN_TRADE_SIZE = 100.0  # Minimum $100 per trade
DEFAULT_ALLOW_FRACTIONAL = True


# ==============================================================================
# TAXABLE HOLDINGS HELPER
# ==============================================================================

def load_taxable_symbols(
    portfolio_file: Path = PORTFOLIO_TRUTH_FILE,
) -> List[str]:
    """
    Load stock symbols currently held in taxable (Brokerage) accounts for the
    most recent month/year present in portfolio_data_truth.csv.

    These symbols are excluded from direct index portfolio generation to avoid
    wash-sale risk and duplicate tax-lot complexity.

    Returns:
        List of ticker symbols (upper-cased, deduplicated).
    """
    if not portfolio_file.exists():
        logger.warning(f"Portfolio file not found: {portfolio_file} — no taxable exclusions applied")
        return []

    try:
        df = pd.read_csv(portfolio_file)
        required = {"month", "year", "account_type", "symbol"}
        if not required.issubset(df.columns):
            logger.warning(f"Portfolio file missing columns {required - set(df.columns)} — skipping taxable exclusions")
            return []

        # Use the most recent (month, year) in the file
        latest = df[["month", "year"]].drop_duplicates().sort_values(
            ["year", "month"], ascending=False
        ).iloc[0]
        latest_month, latest_year = int(latest["month"]), int(latest["year"])

        taxable = df[
            (df["account_type"].isin(TAXABLE_ACCOUNT_TYPES))
            & (df["month"] == latest_month)
            & (df["year"] == latest_year)
        ]

        symbols = sorted(set(taxable["symbol"].dropna().str.strip().str.upper().tolist()))
        logger.info(
            f"Loaded {len(symbols)} taxable symbols from {portfolio_file.name} "
            f"({latest_month}/{latest_year}): {symbols}"
        )
        return symbols

    except Exception as e:
        logger.error(f"Error loading taxable holdings: {e}")
        return []


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class InitialPurchase:
    """
    Represents a single stock purchase in the initial portfolio.
    
    Attributes:
        symbol: Stock ticker symbol
        name: Company name
        sector: GICS sector
        current_price: Current stock price
        target_weight: Target weight in portfolio (%)
        target_amount: Target dollar amount to invest
        shares_to_buy: Number of whole shares to buy
        actual_amount: Actual dollar amount (shares * price)
        fractional_shares: Fractional shares (if allowed)
        order_type: Order type (MARKET, LIMIT, etc.)
    """
    symbol: str
    name: str
    sector: str
    current_price: float
    target_weight: float
    target_amount: float
    shares_to_buy: int
    actual_amount: float
    fractional_shares: float
    order_type: str = "MARKET"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class PortfolioSummary:
    """
    Summary statistics for the initial portfolio.
    
    Attributes:
        total_stocks: Number of stocks in portfolio
        target_investment: Target investment amount
        actual_investment: Actual investment amount
        unallocated_cash: Cash not allocated to stocks
        by_sector: Sector breakdown
        average_position_size: Average position size
        largest_position: Largest position details
        smallest_position: Smallest position details
        stocks_below_min: Number of stocks below minimum trade size
    """
    total_stocks: int
    target_investment: float
    actual_investment: float
    unallocated_cash: float
    by_sector: Dict[str, Dict[str, Any]]
    average_position_size: float
    largest_position: Dict[str, Any]
    smallest_position: Dict[str, Any]
    stocks_below_min: int
    taxable_excluded: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.taxable_excluded is None:
            self.taxable_excluded = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# ==============================================================================
# PORTFOLIO GENERATION
# ==============================================================================

def generate_initial_portfolio(
    total_investment: float,
    rsp_constituents: Optional[List[RSPConstituent]] = None,
    min_trade_size: float = DEFAULT_MIN_TRADE_SIZE,
    allow_fractional: bool = DEFAULT_ALLOW_FRACTIONAL,
    exclude_symbols: Optional[List[str]] = None,
    refresh_prices: bool = False,
    index_coverage_pct: float = 100.0,
    weighting_mode: str = "stock",
    exclude_taxable: bool = True,
) -> Tuple[List[InitialPurchase], PortfolioSummary]:
    """
    Generate initial purchase list for direct indexing.

    Args:
        total_investment: Total amount to invest
        rsp_constituents: List of RSP stocks (if None, loads from database)
        min_trade_size: Minimum dollar amount per trade
        allow_fractional: Whether to allow fractional shares
        exclude_symbols: Stocks to exclude (if any)
        refresh_prices: Whether to refresh prices before generating
        index_coverage_pct: Percentage (1–100) of RSP constituents to include
            in the direct index. Stocks are selected proportionally across
            sectors so sector balance is maintained. The remainder form your
            replacement pool for tax-loss harvesting.
        weighting_mode: 'stock' — every stock gets the same dollar amount
            (true RSP equal-weight). 'sector' — each GICS sector gets an
            equal share of the portfolio, then stocks within each sector are
            equal-weighted.
        exclude_taxable: If True (default), automatically exclude symbols
            already held in taxable (Brokerage) accounts in the most recent
            month/year of portfolio_data_truth.csv.

    Returns:
        Tuple of (List of purchases, Summary statistics)
        Note: The summary includes a ``taxable_excluded`` key listing symbols
        that were dropped due to existing taxable holdings.
    """
    logger.info(f"Generating initial portfolio for ${total_investment:,.2f}")
    
    # Load constituents if not provided
    if rsp_constituents is None:
        rsp_constituents = load_constituents()
        
        if not rsp_constituents:
            logger.warning("No RSP constituents found, fetching from Yahoo Finance...")
            rsp_constituents = fetch_rsp_holdings(force_refresh=True)
    
    if not rsp_constituents:
        raise ValueError("No RSP constituents available")
    
    # Refresh prices if requested
    if refresh_prices:
        logger.info("Refreshing current prices...")
        symbols = [c.symbol for c in rsp_constituents]
        updated_prices = update_prices(symbols)
        
        # Update constituent prices
        for constituent in rsp_constituents:
            if constituent.symbol in updated_prices:
                constituent.current_price = updated_prices[constituent.symbol]
    
    # Auto-exclude symbols already held in taxable accounts
    taxable_excluded: List[str] = []
    if exclude_taxable:
        taxable_symbols = set(load_taxable_symbols())
        if taxable_symbols:
            before = len(rsp_constituents)
            taxable_excluded = sorted(
                c.symbol for c in rsp_constituents if c.symbol in taxable_symbols
            )
            rsp_constituents = [
                c for c in rsp_constituents if c.symbol not in taxable_symbols
            ]
            logger.info(
                f"Auto-excluded {before - len(rsp_constituents)} taxable holdings: "
                f"{taxable_excluded}"
            )

    # Filter user-specified excluded symbols
    if exclude_symbols:
        rsp_constituents = [
            c for c in rsp_constituents
            if c.symbol not in exclude_symbols
        ]
        logger.info(f"Excluded {len(exclude_symbols)} user-specified symbols")

    # Filter out stocks with invalid prices
    valid_constituents = [
        c for c in rsp_constituents
        if c.current_price > 0
    ]

    if len(valid_constituents) != len(rsp_constituents):
        invalid_count = len(rsp_constituents) - len(valid_constituents)
        logger.warning(f"Excluded {invalid_count} stocks with no price data")

    # Apply index coverage: pick a proportional subset per sector so that
    # every sector is represented at the same ratio.
    coverage = max(1.0, min(100.0, float(index_coverage_pct)))
    if coverage < 100.0:
        from collections import defaultdict
        import math
        by_sector: dict = defaultdict(list)
        for c in valid_constituents:
            by_sector[c.sector].append(c)

        selected = []
        for sector_stocks in by_sector.values():
            # Sort by indicator preference first (strong_buy best), then market_cap desc.
            # This means when index_coverage_pct < 100 the highest-conviction stocks
            # are kept in the index while weaker ones form the replacement pool.
            sector_stocks.sort(
                key=lambda x: (x.indicator_priority, -x.market_cap)
            )
            n_keep = max(1, math.ceil(len(sector_stocks) * coverage / 100.0))
            selected.extend(sector_stocks[:n_keep])

        logger.info(
            f"index_coverage_pct={coverage:.0f}%: selected {len(selected)} "
            f"of {len(valid_constituents)} stocks (replacement pool = "
            f"{len(valid_constituents) - len(selected)})"
        )
        valid_constituents = selected
    
    # Build a per-stock target amount map depending on weighting mode
    num_stocks = len(valid_constituents)
    if num_stocks == 0:
        raise ValueError("No valid stocks available for portfolio generation")

    if weighting_mode == "sector":
        # Each sector gets an equal slice of the total; stocks within a sector
        # are equal-weighted within that sector's slice.
        from collections import defaultdict as _dd
        sector_buckets: dict = _dd(list)
        for c in valid_constituents:
            sector_buckets[c.sector].append(c)
        num_sectors = len(sector_buckets)
        sector_budget = total_investment / num_sectors
        target_map: dict = {}
        for sector_stocks in sector_buckets.values():
            per_stock = sector_budget / len(sector_stocks)
            for c in sector_stocks:
                target_map[c.symbol] = per_stock
        logger.info(
            f"sector weighting: {num_sectors} sectors × "
            f"${sector_budget:,.2f} = ${total_investment:,.2f} total"
        )
    else:
        # stock equal-weight: every stock gets the same dollar amount
        target_per_stock = total_investment / num_stocks
        target_map = {c.symbol: target_per_stock for c in valid_constituents}
        logger.info(f"stock weighting: {num_stocks} stocks × ${target_per_stock:.2f}")

    equal_weight = 100.0 / num_stocks  # used for display only

    # Generate purchases
    purchases = []
    total_allocated = 0.0
    stocks_below_min = 0

    for constituent in valid_constituents:
        target_amount = target_map[constituent.symbol]

        # Calculate shares
        if allow_fractional:
            total_shares = target_amount / constituent.current_price
            whole_shares = int(total_shares)
            fractional = total_shares - whole_shares
            actual_amount = total_shares * constituent.current_price  # == target_amount
        else:
            whole_shares = int(target_amount / constituent.current_price)
            fractional = 0.0
            actual_amount = whole_shares * constituent.current_price

        # Check minimum trade size
        if actual_amount < min_trade_size:
            stocks_below_min += 1
            logger.debug(f"{constituent.symbol}: ${actual_amount:.2f} below minimum ${min_trade_size}")

        purchase = InitialPurchase(
            symbol=constituent.symbol,
            name=constituent.name,
            sector=constituent.sector,
            current_price=constituent.current_price,
            target_weight=equal_weight,
            target_amount=target_amount,
            shares_to_buy=whole_shares,
            actual_amount=actual_amount,
            fractional_shares=fractional,
            order_type="MARKET"
        )

        purchases.append(purchase)
        total_allocated += actual_amount
    
    # Sort by sector, then symbol for organized execution
    purchases.sort(key=lambda x: (x.sector, x.symbol))
    
    # Generate summary
    summary = generate_purchase_summary(
        purchases, total_investment, total_allocated, stocks_below_min
    )
    summary.taxable_excluded = taxable_excluded

    logger.info(f"Generated {len(purchases)} purchases, ${total_allocated:,.2f} allocated")

    return purchases, summary


def generate_purchase_summary(
    purchases: List[InitialPurchase],
    target_investment: float,
    actual_investment: float,
    stocks_below_min: int
) -> PortfolioSummary:
    """
    Generate summary statistics for initial portfolio.
    
    Args:
        purchases: List of purchase instructions
        target_investment: Target investment amount
        actual_investment: Actual investment amount
        stocks_below_min: Number of stocks below minimum trade size
    
    Returns:
        PortfolioSummary object
    """
    if not purchases:
        return PortfolioSummary(
            total_stocks=0,
            target_investment=target_investment,
            actual_investment=0.0,
            unallocated_cash=target_investment,
            by_sector={},
            average_position_size=0.0,
            largest_position={},
            smallest_position={},
            stocks_below_min=0
        )
    
    # Calculate by-sector breakdown
    sector_stats = defaultdict(lambda: {
        'num_stocks': 0,
        'total_amount': 0.0,
        'avg_amount': 0.0,
        'weight': 0.0
    })
    
    for purchase in purchases:
        sector_stats[purchase.sector]['num_stocks'] += 1
        sector_stats[purchase.sector]['total_amount'] += purchase.actual_amount
    
    # Calculate averages and weights
    for sector in sector_stats:
        stats = sector_stats[sector]
        stats['avg_amount'] = stats['total_amount'] / stats['num_stocks']
        stats['weight'] = (stats['total_amount'] / actual_investment * 100) if actual_investment > 0 else 0
    
    # Find largest and smallest positions
    amounts = [p.actual_amount for p in purchases]
    largest_amount = max(amounts)
    smallest_amount = min(amounts)
    
    largest_purchase = next(p for p in purchases if p.actual_amount == largest_amount)
    smallest_purchase = next(p for p in purchases if p.actual_amount == smallest_amount)
    
    largest_position = {
        'symbol': largest_purchase.symbol,
        'name': largest_purchase.name,
        'amount': largest_amount,
        'shares': largest_purchase.shares_to_buy
    }
    
    smallest_position = {
        'symbol': smallest_purchase.symbol,
        'name': smallest_purchase.name,
        'amount': smallest_amount,
        'shares': smallest_purchase.shares_to_buy
    }
    
    return PortfolioSummary(
        total_stocks=len(purchases),
        target_investment=target_investment,
        actual_investment=actual_investment,
        unallocated_cash=target_investment - actual_investment,
        by_sector=dict(sector_stats),
        average_position_size=actual_investment / len(purchases) if purchases else 0,
        largest_position=largest_position,
        smallest_position=smallest_position,
        stocks_below_min=stocks_below_min
    )


# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

def export_purchase_instructions(
    purchases: List[InitialPurchase],
    summary: PortfolioSummary,
    output_format: str = 'csv',
    output_path: Optional[str] = None
) -> str:
    """
    Export purchase instructions in various formats.
    
    Args:
        purchases: List of purchase instructions
        summary: Portfolio summary
        output_format: Format ('csv', 'markdown', 'schwab', 'excel')
        output_path: Output file path (auto-generated if None)
    
    Returns:
        Path to exported file or formatted string
    """
    if output_format == 'csv':
        return export_to_csv(purchases, output_path)
    elif output_format == 'markdown':
        return export_to_markdown(purchases, summary, output_path)
    elif output_format == 'schwab':
        return export_to_schwab_format(purchases, output_path)
    elif output_format == 'excel':
        return export_to_excel(purchases, summary, output_path)
    else:
        raise ValueError(f"Unsupported format: {output_format}")


def export_to_csv(
    purchases: List[InitialPurchase],
    output_path: Optional[str] = None
) -> str:
    """
    Export purchase instructions to CSV format.
    
    Args:
        purchases: List of purchase instructions
        output_path: Output file path
    
    Returns:
        Path to exported file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/initial_portfolio_{timestamp}.csv"
    
    # Convert to DataFrame
    df = pd.DataFrame([p.to_dict() for p in purchases])
    
    # Reorder columns for clarity
    columns = [
        'symbol', 'name', 'sector', 'shares_to_buy', 'current_price', 
        'actual_amount', 'target_amount', 'fractional_shares', 'order_type'
    ]
    df = df[columns]
    
    # Ensure directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Save to CSV
    df.to_csv(output_path, index=False)
    
    logger.info(f"Exported {len(purchases)} purchases to CSV: {output_path}")
    return output_path


def export_to_markdown(
    purchases: List[InitialPurchase],
    summary: PortfolioSummary,
    output_path: Optional[str] = None
) -> str:
    """
    Export purchase instructions to Markdown format.
    
    Args:
        purchases: List of purchase instructions
        summary: Portfolio summary
        output_path: Output file path
    
    Returns:
        Path to exported file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/initial_portfolio_{timestamp}.md"
    
    lines = [
        "# Initial Direct Index Portfolio",
        f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        "",
        "## Summary",
        f"- **Total Investment**: ${summary.target_investment:,.2f}",
        f"- **Actual Investment**: ${summary.actual_investment:,.2f}",
        f"- **Unallocated Cash**: ${summary.unallocated_cash:,.2f}",
        f"- **Number of Stocks**: {summary.total_stocks}",
        f"- **Average Position**: ${summary.average_position_size:,.2f}",
        f"- **Stocks Below Minimum**: {summary.stocks_below_min}",
        "",
        "## By Sector",
        ""
    ]
    
    # Add sector breakdown
    sorted_sectors = sorted(
        summary.by_sector.items(),
        key=lambda x: x[1]['total_amount'],
        reverse=True
    )
    
    for sector, stats in sorted_sectors:
        lines.extend([
            f"### {sector} ({stats['num_stocks']} stocks, ${stats['total_amount']:,.0f})",
            ""
        ])
        
        # Get purchases for this sector
        sector_purchases = [p for p in purchases if p.sector == sector]
        sector_purchases.sort(key=lambda x: x.actual_amount, reverse=True)
        
        lines.append("| Symbol | Name | Shares | Price | Amount |")
        lines.append("|--------|------|--------|-------|--------|")
        
        for purchase in sector_purchases:
            lines.append(
                f"| {purchase.symbol} | {purchase.name[:30]} | {purchase.shares_to_buy} | "
                f"${purchase.current_price:.2f} | ${purchase.actual_amount:,.0f} |"
            )
        
        lines.append("")
    
    # Add execution instructions
    lines.extend([
        "## Execution Instructions",
        "",
        "1. **Review all positions and prices** - Verify current market prices before executing",
        "2. **Execute trades in batches by sector** - This helps with organization and tracking",
        "3. **Use MARKET orders for liquidity** - Most RSP stocks are highly liquid",
        "4. **Complete all trades within same day** - Minimize price movement impact",
        "5. **Import executed positions into system** - Update the direct indexing tracker",
        "",
        "## Important Notes",
        "",
        "- All prices are as of generation time - verify current prices before trading",
        "- Fractional shares may not be available for all stocks",
        "- Consider transaction costs when executing small positions",
        "- Keep trade confirmations for tax record keeping",
        "",
        "---",
        "*Generated by Direct Indexing System*"
    ])
    
    # Write to file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    
    logger.info(f"Exported portfolio instructions to Markdown: {output_path}")
    return output_path


def export_to_schwab_format(
    purchases: List[InitialPurchase],
    output_path: Optional[str] = None
) -> str:
    """
    Export purchase instructions in Schwab-compatible format.
    
    Args:
        purchases: List of purchase instructions
        output_path: Output file path
    
    Returns:
        Path to exported file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/schwab_orders_{timestamp}.csv"
    
    # Create Schwab-compatible format
    schwab_data = []
    for purchase in purchases:
        schwab_data.append({
            'Action': 'BUY',
            'Symbol': purchase.symbol,
            'Quantity': purchase.shares_to_buy,
            'OrderType': purchase.order_type,
            'TimeInForce': 'DAY',
            'Amount': purchase.actual_amount
        })
    
    df = pd.DataFrame(schwab_data)
    
    # Ensure directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Save to CSV
    df.to_csv(output_path, index=False)
    
    logger.info(f"Exported {len(purchases)} orders to Schwab format: {output_path}")
    return output_path


def export_to_excel(
    purchases: List[InitialPurchase],
    summary: PortfolioSummary,
    output_path: Optional[str] = None
) -> str:
    """
    Export purchase instructions to Excel with multiple sheets.
    
    Args:
        purchases: List of purchase instructions
        summary: Portfolio summary
        output_path: Output file path
    
    Returns:
        Path to exported file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/initial_portfolio_{timestamp}.xlsx"
    
    # Ensure directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Main purchases sheet
        df_purchases = pd.DataFrame([p.to_dict() for p in purchases])
        df_purchases.to_excel(writer, sheet_name='Purchases', index=False)
        
        # Summary sheet
        summary_data = [
            ['Metric', 'Value'],
            ['Total Stocks', summary.total_stocks],
            ['Target Investment', f"${summary.target_investment:,.2f}"],
            ['Actual Investment', f"${summary.actual_investment:,.2f}"],
            ['Unallocated Cash', f"${summary.unallocated_cash:,.2f}"],
            ['Average Position Size', f"${summary.average_position_size:,.2f}"],
            ['Stocks Below Minimum', summary.stocks_below_min]
        ]
        df_summary = pd.DataFrame(summary_data[1:], columns=summary_data[0])
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        
        # Sector breakdown sheet
        sector_data = []
        for sector, stats in summary.by_sector.items():
            sector_data.append([
                sector,
                stats['num_stocks'],
                f"${stats['total_amount']:,.2f}",
                f"${stats['avg_amount']:,.2f}",
                f"{stats['weight']:.2f}%"
            ])
        
        df_sectors = pd.DataFrame(
            sector_data,
            columns=['Sector', 'Stocks', 'Total Amount', 'Avg Amount', 'Weight']
        )
        df_sectors.to_excel(writer, sheet_name='By Sector', index=False)
    
    logger.info(f"Exported portfolio to Excel: {output_path}")
    return output_path


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Initial Portfolio Generator")
    print("=" * 60)
    
    # Test with small investment
    test_investment = 50000.0  # $50K for testing
    
    print(f"\nGenerating initial portfolio for ${test_investment:,.2f}")
    
    try:
        purchases, summary = generate_initial_portfolio(
            total_investment=test_investment,
            min_trade_size=50.0,  # Lower minimum for testing
            refresh_prices=False  # Don't refresh for testing
        )
        
        print(f"\nGenerated {len(purchases)} purchases")
        print(f"Total allocated: ${summary.actual_investment:,.2f}")
        print(f"Unallocated: ${summary.unallocated_cash:,.2f}")
        
        # Show top 10 purchases
        print("\nTop 10 purchases by amount:")
        sorted_purchases = sorted(purchases, key=lambda x: x.actual_amount, reverse=True)
        for i, purchase in enumerate(sorted_purchases[:10]):
            print(f"  {i+1:2d}. {purchase.symbol:6s} - {purchase.name[:30]:30s} | "
                  f"{purchase.shares_to_buy:3d} shares @ ${purchase.current_price:8.2f} = "
                  f"${purchase.actual_amount:8.2f}")
        
        # Show sector breakdown
        print("\nSector breakdown:")
        sorted_sectors = sorted(
            summary.by_sector.items(),
            key=lambda x: x[1]['total_amount'],
            reverse=True
        )
        for sector, stats in sorted_sectors:
            print(f"  {sector:30s}: {stats['num_stocks']:3d} stocks, "
                  f"${stats['total_amount']:8,.0f} ({stats['weight']:5.2f}%)")
        
        # Export to CSV for testing
        csv_path = export_to_csv(purchases)
        print(f"\nExported to CSV: {csv_path}")
        
        # Export to Markdown
        md_path = export_to_markdown(purchases, summary)
        print(f"Exported to Markdown: {md_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Error generating portfolio")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

# Made with Bob
