"""
RSP Holdings Fetcher
====================
Fetch and maintain RSP (Equal-Weighted S&P 500) constituent holdings from Yahoo Finance.

This module provides functionality to:
- Fetch current RSP ETF holdings
- Get sector/industry classification for each stock
- Retrieve current prices and market caps
- Cache data locally for performance
- Handle API rate limits and errors

Author: Bob
Date: April 16, 2026
Version: 1.0
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import time

import pandas as pd
import numpy as np

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logging.warning("yfinance not available. Install with: pip install yfinance")

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

RSP_TICKER = "RSP"  # Invesco S&P 500 Equal Weight ETF
DB_PATH = Path("data/rsp_holdings.db")
CACHE_DURATION_DAYS = 7  # Refresh holdings weekly
PRICE_CACHE_HOURS = 4  # Refresh prices every 4 hours

# GICS Sectors (Level 1)
GICS_SECTORS = [
    "Information Technology",
    "Health Care",
    "Financials",
    "Consumer Discretionary",
    "Communication Services",
    "Industrials",
    "Consumer Staples",
    "Energy",
    "Utilities",
    "Real Estate",
    "Materials"
]

# Sector mapping for common variations
SECTOR_MAPPING = {
    "Technology": "Information Technology",
    "Healthcare": "Health Care",
    "Financial Services": "Financials",
    "Consumer Cyclical": "Consumer Discretionary",
    "Communication": "Communication Services",
    "Industrial": "Industrials",
    "Consumer Defensive": "Consumer Staples",
    "Basic Materials": "Materials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Energy": "Energy",
}


# ==============================================================================
# DATA CLASSES
# ==============================================================================

# Market indicator priority order for sorting (lower = more preferred)
INDICATOR_PRIORITY: Dict[str, int] = {
    "strong_buy": 1,
    "buy":        2,
    "hold":       3,
    "caution":    4,
    "sell":       5,
    "unknown":    6,
}


@dataclass
class RSPConstituent:
    """
    Represents a single constituent of the RSP ETF.
    
    Attributes:
        symbol: Stock ticker symbol
        name: Company name
        sector: GICS Sector (Level 1)
        industry: GICS Industry (Level 2)
        market_cap: Market capitalization in dollars
        weight_in_rsp: Weight in RSP ETF (approximately equal ~0.2%)
        current_price: Current stock price
        last_updated: Timestamp of last data update
        market_indicator: Market condition string — one of strong_buy, buy,
            hold, caution, sell, unknown (populated by update_market_indicators)
        indicator_updated: Timestamp of last indicator calculation
    """
    symbol: str
    name: str
    sector: str
    industry: str
    market_cap: float
    weight_in_rsp: float
    current_price: float
    last_updated: datetime
    market_indicator: str = "unknown"
    indicator_updated: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        d = asdict(self)
        d['last_updated'] = self.last_updated.isoformat()
        if d.get('indicator_updated') and isinstance(d['indicator_updated'], datetime):
            d['indicator_updated'] = d['indicator_updated'].isoformat()
        return d

    @property
    def indicator_priority(self) -> int:
        """Numeric priority for sorting: 1 (strong_buy) … 6 (unknown)."""
        return INDICATOR_PRIORITY.get(self.market_indicator, 6)

    @classmethod
    def from_dict(cls, d: Dict) -> 'RSPConstituent':
        """Create from dictionary."""
        d = d.copy()
        if isinstance(d['last_updated'], str):
            d['last_updated'] = datetime.fromisoformat(d['last_updated'])
        if isinstance(d.get('indicator_updated'), str):
            d['indicator_updated'] = datetime.fromisoformat(d['indicator_updated'])
        return cls(**d)


# ==============================================================================
# DATABASE FUNCTIONS
# ==============================================================================

def init_database() -> None:
    """Initialize the RSP holdings database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create holdings table (canonical schema)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rsp_holdings (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            industry TEXT,
            market_cap REAL,
            weight_in_rsp REAL,
            current_price REAL,
            last_updated TIMESTAMP,
            market_indicator TEXT DEFAULT 'unknown',
            indicator_updated TIMESTAMP
        )
    """)

    # Add new columns to existing databases (migration — safe to call repeatedly)
    for col, definition in [
        ("market_indicator", "TEXT DEFAULT 'unknown'"),
        ("indicator_updated", "TIMESTAMP"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE rsp_holdings ADD COLUMN {col} {definition}")
            logger.info(f"Migrated rsp_holdings: added column {col}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Create metadata table for tracking updates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS update_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    logger.info(f"Initialized RSP holdings database at {DB_PATH}")


def save_constituents(constituents: List[RSPConstituent]) -> None:
    """
    Save RSP constituents to database.
    
    Args:
        constituents: List of RSP constituents to save
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for constituent in constituents:
        cursor.execute("""
            INSERT OR REPLACE INTO rsp_holdings
            (symbol, name, sector, industry, market_cap, weight_in_rsp,
             current_price, last_updated, market_indicator, indicator_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            constituent.symbol,
            constituent.name,
            constituent.sector,
            constituent.industry,
            constituent.market_cap,
            constituent.weight_in_rsp,
            constituent.current_price,
            constituent.last_updated.isoformat(),
            constituent.market_indicator or "unknown",
            constituent.indicator_updated.isoformat() if constituent.indicator_updated else None,
        ))
    
    # Update metadata
    cursor.execute("""
        INSERT OR REPLACE INTO update_metadata (key, value, updated_at)
        VALUES ('last_full_update', ?, ?)
    """, (datetime.now().isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Saved {len(constituents)} RSP constituents to database")


def load_constituents() -> List[RSPConstituent]:
    """
    Load RSP constituents from database.
    
    Returns:
        List of RSP constituents
    """
    if not DB_PATH.exists():
        logger.warning("RSP holdings database does not exist")
        return []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM rsp_holdings ORDER BY symbol")
    rows = cursor.fetchall()
    
    conn.close()
    
    constituents = []
    for row in rows:
        constituent = RSPConstituent(
            symbol=row[0],
            name=row[1],
            sector=row[2],
            industry=row[3] or "",
            market_cap=row[4] or 0.0,
            weight_in_rsp=row[5] or 0.0,
            current_price=row[6] or 0.0,
            last_updated=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
            market_indicator=row[8] if len(row) > 8 and row[8] else "unknown",
            indicator_updated=(
                datetime.fromisoformat(row[9]) if len(row) > 9 and row[9] else None
            ),
        )
        constituents.append(constituent)
    
    logger.info(f"Loaded {len(constituents)} RSP constituents from database")
    return constituents


def get_last_update_time() -> Optional[datetime]:
    """Get timestamp of last full update."""
    if not DB_PATH.exists():
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT value FROM update_metadata WHERE key = 'last_full_update'
    """)
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return datetime.fromisoformat(row[0])
    return None


def needs_update() -> bool:
    """Check if holdings data needs to be refreshed."""
    last_update = get_last_update_time()
    if last_update is None:
        return True
    
    age = datetime.now() - last_update
    return age > timedelta(days=CACHE_DURATION_DAYS)


# ==============================================================================
# YAHOO FINANCE FETCHING
# ==============================================================================

def normalize_sector(sector: str) -> str:
    """
    Normalize sector name to GICS standard.
    
    Args:
        sector: Raw sector name from Yahoo Finance
    
    Returns:
        Normalized GICS sector name
    """
    if not sector:
        return "Unknown"
    
    # Check direct match
    if sector in GICS_SECTORS:
        return sector
    
    # Check mapping
    if sector in SECTOR_MAPPING:
        return SECTOR_MAPPING[sector]
    
    # Return as-is if no match
    return sector


def fetch_sp500_constituents() -> List[str]:
    """
    Fetch S&P 500 constituent symbols.
    
    Since RSP tracks S&P 500 with equal weights, we can use S&P 500 constituents.
    
    Returns:
        List of stock symbols
    """
    if not YFINANCE_AVAILABLE:
        logger.error("yfinance not available")
        return []
    
    try:
        # Fetch S&P 500 constituents from Wikipedia
        # Use a requests session with a browser User-Agent to avoid 403/SSL issues
        import io
        import requests
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        sp500_table = tables[0]

        symbols = sp500_table['Symbol'].tolist()

        # Clean symbols (remove dots, etc.)
        symbols = [s.replace('.', '-') for s in symbols]

        logger.info(f"Fetched {len(symbols)} S&P 500 constituent symbols")
        return symbols

    except Exception as e:
        logger.error(f"Error fetching S&P 500 constituents: {e}")
        return []


def fetch_stock_info(symbol: str) -> Optional[Dict]:
    """
    Fetch stock information from Yahoo Finance.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Dictionary with stock info, or None if error
    """
    if not YFINANCE_AVAILABLE or 'yf' not in globals():
        return None
    
    try:
        ticker = yf.Ticker(symbol)  # type: ignore
        info = ticker.info
        
        # Get current price
        current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0.0)
        
        return {
            'symbol': symbol,
            'name': info.get('longName') or info.get('shortName', symbol),
            'sector': normalize_sector(info.get('sector', 'Unknown')),
            'industry': info.get('industry', ''),
            'market_cap': info.get('marketCap', 0.0),
            'current_price': current_price
        }
        
    except Exception as e:
        logger.warning(f"Error fetching info for {symbol}: {e}")
        return None


def fetch_rsp_holdings(
    force_refresh: bool = False,
    max_stocks: Optional[int] = None
) -> List[RSPConstituent]:
    """
    Fetch RSP holdings from Yahoo Finance.
    
    Args:
        force_refresh: Force refresh even if cache is valid
        max_stocks: Limit number of stocks (for testing)
    
    Returns:
        List of RSP constituents
    """
    # Check if we need to update
    if not force_refresh and not needs_update():
        logger.info("Using cached RSP holdings (still fresh)")
        return load_constituents()
    
    if not YFINANCE_AVAILABLE:
        logger.error("yfinance not available, using cached data")
        return load_constituents()
    
    logger.info("Fetching RSP holdings from Yahoo Finance...")
    
    # Initialize database
    init_database()
    
    # Fetch S&P 500 constituents (RSP tracks these with equal weights)
    symbols = fetch_sp500_constituents()
    
    if not symbols:
        logger.error("Failed to fetch S&P 500 constituents")
        return load_constituents()
    
    # Limit for testing
    if max_stocks:
        symbols = symbols[:max_stocks]
        logger.info(f"Limited to {max_stocks} stocks for testing")
    
    # Calculate equal weight
    num_stocks = len(symbols)
    equal_weight = 100.0 / num_stocks if num_stocks > 0 else 0.0
    
    # Fetch info for each stock
    constituents = []
    failed_symbols = []
    
    for i, symbol in enumerate(symbols):
        if i > 0 and i % 50 == 0:
            logger.info(f"Fetched {i}/{len(symbols)} stocks...")
            time.sleep(1)  # Rate limiting
        
        info = fetch_stock_info(symbol)
        
        if info:
            constituent = RSPConstituent(
                symbol=info['symbol'],
                name=info['name'],
                sector=info['sector'],
                industry=info['industry'],
                market_cap=info['market_cap'],
                weight_in_rsp=equal_weight,
                current_price=info['current_price'],
                last_updated=datetime.now()
            )
            constituents.append(constituent)
        else:
            failed_symbols.append(symbol)
    
    logger.info(f"Successfully fetched {len(constituents)} stocks")
    if failed_symbols:
        logger.warning(f"Failed to fetch {len(failed_symbols)} stocks: {failed_symbols[:10]}")
    
    # Save to database
    if constituents:
        save_constituents(constituents)
    
    return constituents


def update_prices(symbols: Optional[List[str]] = None) -> Dict[str, float]:
    """
    Update current prices for RSP constituents.
    
    Args:
        symbols: Specific symbols to update (None = all)
    
    Returns:
        Dictionary mapping symbol to current price
    """
    if not YFINANCE_AVAILABLE:
        logger.error("yfinance not available")
        return {}
    
    # Load constituents
    constituents = load_constituents()
    
    if not constituents:
        logger.warning("No constituents to update")
        return {}
    
    # Filter to specific symbols if provided
    if symbols:
        constituents = [c for c in constituents if c.symbol in symbols]
    
    logger.info(f"Updating prices for {len(constituents)} stocks...")
    
    prices = {}
    updated_constituents = []
    
    for i, constituent in enumerate(constituents):
        if i > 0 and i % 50 == 0:
            logger.info(f"Updated {i}/{len(constituents)} prices...")
            time.sleep(1)  # Rate limiting
        
        try:
            ticker = yf.Ticker(constituent.symbol)  # type: ignore
            info = ticker.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0.0)
            
            if current_price > 0:
                prices[constituent.symbol] = current_price
                
                # Update constituent
                constituent.current_price = current_price
                constituent.last_updated = datetime.now()
                updated_constituents.append(constituent)
        
        except Exception as e:
            logger.warning(f"Error updating price for {constituent.symbol}: {e}")
    
    # Save updated prices
    if updated_constituents:
        save_constituents(updated_constituents)
        logger.info(f"Updated {len(updated_constituents)} prices")
    
    return prices


def update_market_indicators(
    symbols: Optional[List[str]] = None,
    force: bool = False,
    max_age_hours: float = 24.0,
) -> Dict[str, str]:
    """
    Calculate and persist market indicators for RSP constituents.

    Calls ``calculate_security_indicator`` from ``portfolio_market_indicators``
    for each symbol and writes the result back to the DB.

    Args:
        symbols: Specific symbols to update (None = all constituents).
        force: Recalculate even if indicator was updated recently.
        max_age_hours: Skip symbols whose indicator was updated within this
            many hours (unless *force* is True). Default 24 h.

    Returns:
        Dict mapping symbol → indicator string (e.g. "strong_buy").
    """
    try:
        from portfolio_market_indicators import calculate_security_indicator
    except ImportError:
        logger.error("portfolio_market_indicators not available — cannot update indicators")
        return {}

    constituents = load_constituents()
    if not constituents:
        logger.warning("No constituents to update indicators for")
        return {}

    if symbols:
        symbol_set = set(symbols)
        constituents = [c for c in constituents if c.symbol in symbol_set]

    now = datetime.now()
    cutoff = now.replace(microsecond=0)
    results: Dict[str, str] = {}
    updated: List[RSPConstituent] = []

    logger.info(f"Updating market indicators for {len(constituents)} constituents…")

    for i, constituent in enumerate(constituents):
        # Skip recently updated unless forced
        if not force and constituent.indicator_updated:
            age_hours = (now - constituent.indicator_updated).total_seconds() / 3600
            if age_hours < max_age_hours:
                results[constituent.symbol] = constituent.market_indicator
                continue

        if i > 0 and i % 50 == 0:
            logger.info(f"  … processed {i}/{len(constituents)} indicators")
            time.sleep(0.5)  # be polite to Yahoo Finance

        try:
            indicator = calculate_security_indicator(constituent.symbol)
            if indicator is not None:
                constituent.market_indicator = indicator.condition.value
                constituent.indicator_updated = cutoff
            else:
                constituent.market_indicator = "unknown"
                constituent.indicator_updated = cutoff
        except Exception as exc:
            logger.warning(f"Indicator error for {constituent.symbol}: {exc}")
            constituent.market_indicator = "unknown"
            constituent.indicator_updated = cutoff

        results[constituent.symbol] = constituent.market_indicator
        updated.append(constituent)

    if updated:
        save_constituents(updated)
        logger.info(f"Saved market indicators for {len(updated)} constituents")

    return results


# ==============================================================================
# QUERY FUNCTIONS
# ==============================================================================

def get_constituents_by_sector(sector: str) -> List[RSPConstituent]:
    """
    Get all constituents in a specific sector.
    
    Args:
        sector: GICS sector name
    
    Returns:
        List of constituents in that sector
    """
    constituents = load_constituents()
    return [c for c in constituents if c.sector == sector]


def get_constituent(symbol: str) -> Optional[RSPConstituent]:
    """
    Get a specific constituent by symbol.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        RSPConstituent or None if not found
    """
    constituents = load_constituents()
    for c in constituents:
        if c.symbol == symbol:
            return c
    return None


def get_sector_summary() -> Dict[str, Dict]:
    """
    Get summary statistics by sector.
    
    Returns:
        Dictionary mapping sector to summary stats
    """
    constituents = load_constituents()
    
    summary = {}
    for sector in GICS_SECTORS:
        sector_stocks = [c for c in constituents if c.sector == sector]
        
        if sector_stocks:
            total_market_cap = sum(c.market_cap for c in sector_stocks)
            avg_price = np.mean([c.current_price for c in sector_stocks])
            
            summary[sector] = {
                'num_stocks': len(sector_stocks),
                'total_market_cap': total_market_cap,
                'avg_price': avg_price,
                'weight': len(sector_stocks) / len(constituents) * 100 if constituents else 0
            }
    
    return summary


def export_to_csv(output_path: str = "data/rsp_constituents.csv") -> None:
    """
    Export RSP constituents to CSV file.
    
    Args:
        output_path: Path to output CSV file
    """
    constituents = load_constituents()
    
    if not constituents:
        logger.warning("No constituents to export")
        return
    
    # Convert to DataFrame
    data = [c.to_dict() for c in constituents]
    df = pd.DataFrame(data)
    
    # Save to CSV
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    
    logger.info(f"Exported {len(constituents)} constituents to {output_file}")


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """Main function for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("RSP Holdings Fetcher")
    print("=" * 60)
    
    # Check if yfinance is available
    if not YFINANCE_AVAILABLE:
        print("ERROR: yfinance not installed")
        print("Install with: pip install yfinance")
        return
    
    # Fetch holdings (limit to 10 for testing)
    print("\nFetching RSP holdings (limited to 10 for testing)...")
    constituents = fetch_rsp_holdings(force_refresh=True, max_stocks=10)
    
    print(f"\nFetched {len(constituents)} constituents")
    
    # Display sample
    if constituents:
        print("\nSample constituents:")
        for c in constituents[:5]:
            print(f"  {c.symbol:6s} - {c.name:40s} | {c.sector:25s} | ${c.current_price:8.2f}")
    
    # Get sector summary
    print("\nSector Summary:")
    summary = get_sector_summary()
    for sector, stats in sorted(summary.items(), key=lambda x: x[1]['num_stocks'], reverse=True):
        print(f"  {sector:30s}: {stats['num_stocks']:3d} stocks")
    
    # Export to CSV
    print("\nExporting to CSV...")
    export_to_csv()
    print("Done!")


if __name__ == "__main__":
    main()

# Made with Bob
