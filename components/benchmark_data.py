"""
components/benchmark_data.py
=============================
Real benchmark data integration for accurate performance comparison.

This module provides:
1. Integration with market data APIs (yfinance)
2. Multiple benchmark options (S&P 500, Total Market, 60/40, etc.)
3. Benchmark data caching
4. Advanced metrics (Beta, Information Ratio, Tracking Error)
5. Historical benchmark returns
"""
from __future__ import annotations

import sqlite3
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Database path for benchmark cache
CACHE_DB_PATH = Path(__file__).parent.parent / "data" / "benchmark_cache.db"


class BenchmarkType(Enum):
    """Available benchmark types."""
    SP500 = "^GSPC"  # S&P 500
    TOTAL_MARKET = "VTI"  # Vanguard Total Stock Market
    NASDAQ = "^IXIC"  # NASDAQ Composite
    DOW = "^DJI"  # Dow Jones Industrial Average
    RUSSELL_2000 = "^RUT"  # Russell 2000
    BALANCED_60_40 = "60/40"  # 60% stocks / 40% bonds
    BALANCED_40_60 = "40/60"  # 40% stocks / 60% bonds
    ALL_WEATHER = "ALL_WEATHER"  # Ray Dalio All Weather
    TREASURY_10Y = "^TNX"  # 10-Year Treasury
    AGGREGATE_BOND = "AGG"  # iShares Core U.S. Aggregate Bond


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark."""
    name: str
    ticker: str
    description: str
    asset_class: str
    is_composite: bool = False  # True for multi-asset benchmarks like 60/40


# Predefined benchmark configurations
BENCHMARK_CONFIGS = {
    BenchmarkType.SP500: BenchmarkConfig(
        name="S&P 500",
        ticker="^GSPC",
        description="Large-cap U.S. stocks",
        asset_class="Equity"
    ),
    BenchmarkType.TOTAL_MARKET: BenchmarkConfig(
        name="Total Stock Market",
        ticker="VTI",
        description="Entire U.S. stock market",
        asset_class="Equity"
    ),
    BenchmarkType.NASDAQ: BenchmarkConfig(
        name="NASDAQ Composite",
        ticker="^IXIC",
        description="Technology-heavy index",
        asset_class="Equity"
    ),
    BenchmarkType.DOW: BenchmarkConfig(
        name="Dow Jones",
        ticker="^DJI",
        description="30 large U.S. companies",
        asset_class="Equity"
    ),
    BenchmarkType.RUSSELL_2000: BenchmarkConfig(
        name="Russell 2000",
        ticker="^RUT",
        description="Small-cap U.S. stocks",
        asset_class="Equity"
    ),
    BenchmarkType.BALANCED_60_40: BenchmarkConfig(
        name="60/40 Portfolio",
        ticker="60/40",
        description="60% stocks, 40% bonds",
        asset_class="Balanced",
        is_composite=True
    ),
    BenchmarkType.BALANCED_40_60: BenchmarkConfig(
        name="40/60 Portfolio",
        ticker="40/60",
        description="40% stocks, 60% bonds",
        asset_class="Balanced",
        is_composite=True
    ),
    BenchmarkType.ALL_WEATHER: BenchmarkConfig(
        name="All Weather",
        ticker="ALL_WEATHER",
        description="Ray Dalio's All Weather Portfolio",
        asset_class="Balanced",
        is_composite=True
    ),
    BenchmarkType.TREASURY_10Y: BenchmarkConfig(
        name="10-Year Treasury",
        ticker="^TNX",
        description="U.S. 10-year government bonds",
        asset_class="Fixed Income"
    ),
    BenchmarkType.AGGREGATE_BOND: BenchmarkConfig(
        name="Aggregate Bond",
        ticker="AGG",
        description="U.S. investment-grade bonds",
        asset_class="Fixed Income"
    ),
}


@dataclass
class BenchmarkReturns:
    """Benchmark return data for a period."""
    benchmark_type: BenchmarkType
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    volatility: float
    daily_returns: pd.Series
    prices: pd.Series


@dataclass
class AdvancedMetrics:
    """Advanced performance metrics vs benchmark."""
    beta: float  # Portfolio volatility relative to benchmark
    alpha: float  # Excess return vs benchmark (risk-adjusted)
    information_ratio: float  # Excess return / tracking error
    tracking_error: float  # Standard deviation of excess returns
    correlation: float  # Correlation with benchmark
    r_squared: float  # Proportion of variance explained by benchmark
    sharpe_ratio: float  # Risk-adjusted return
    sortino_ratio: float  # Downside risk-adjusted return
    max_drawdown: float  # Maximum peak-to-trough decline
    up_capture: float  # Capture ratio in up markets
    down_capture: float  # Capture ratio in down markets


class BenchmarkDataProvider:
    """
    Provide real benchmark data with caching.
    
    Features:
    - Fetch data from yfinance
    - Cache data locally
    - Calculate benchmark returns
    - Support composite benchmarks
    - Advanced metrics calculation
    """
    
    def __init__(self, cache_db_path: Optional[Path] = None):
        """
        Initialize benchmark data provider.
        
        Args:
            cache_db_path: Path to cache database (default: data/benchmark_cache.db)
        """
        self.cache_db_path = cache_db_path or CACHE_DB_PATH
        self._ensure_cache_database()
        logger.info(f"BenchmarkDataProvider initialized with cache: {self.cache_db_path}")
    
    def _ensure_cache_database(self):
        """Create cache database and tables if they don't exist."""
        self.cache_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.cache_db_path) as conn:
            cursor = conn.cursor()
            
            # Benchmark prices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    price_date DATE NOT NULL,
                    close_price REAL NOT NULL,
                    adjusted_close REAL NOT NULL,
                    volume INTEGER,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, price_date)
                )
            """)
            
            # Create index for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_ticker_date 
                ON benchmark_prices(ticker, price_date)
            """)
            
            conn.commit()
            logger.info("Benchmark cache database initialized")
    
    def get_benchmark_returns(
        self,
        benchmark_type: BenchmarkType,
        start_date: date,
        end_date: date,
        force_refresh: bool = False
    ) -> Optional[BenchmarkReturns]:
        """
        Get benchmark returns for a period.
        
        Args:
            benchmark_type: Type of benchmark
            start_date: Period start date
            end_date: Period end date
            force_refresh: If True, fetch fresh data from API
            
        Returns:
            BenchmarkReturns object or None if data unavailable
        """
        try:
            config = BENCHMARK_CONFIGS[benchmark_type]
            
            # Handle composite benchmarks
            if config.is_composite:
                return self._get_composite_benchmark_returns(
                    benchmark_type, start_date, end_date, force_refresh
                )
            
            # Get prices from cache or API
            prices = self._get_prices(config.ticker, start_date, end_date, force_refresh)
            
            if prices is None or prices.empty:
                logger.warning(f"No price data available for {config.name}")
                return None
            
            # Calculate returns
            daily_returns = prices.pct_change().dropna()
            
            if daily_returns.empty:
                return None
            
            # Calculate metrics
            total_return = (prices.iloc[-1] / prices.iloc[0]) - 1
            days = (end_date - start_date).days
            years = days / 365.25
            
            if years > 0:
                annualized_return = (1 + total_return) ** (1 / years) - 1
            else:
                annualized_return = total_return
            
            volatility = daily_returns.std() * np.sqrt(252)  # Annualized
            
            return BenchmarkReturns(
                benchmark_type=benchmark_type,
                start_date=start_date,
                end_date=end_date,
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                daily_returns=daily_returns,
                prices=prices
            )
            
        except Exception as e:
            logger.error(f"Error getting benchmark returns: {e}")
            return None
    
    def _get_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        force_refresh: bool = False
    ) -> Optional[pd.Series]:
        """
        Get price data from cache or API.
        
        Args:
            ticker: Ticker symbol
            start_date: Start date
            end_date: End date
            force_refresh: Force API fetch
            
        Returns:
            Series of adjusted close prices or None
        """
        # Check cache first
        if not force_refresh:
            cached_prices = self._get_cached_prices(ticker, start_date, end_date)
            if cached_prices is not None and not cached_prices.empty:
                logger.debug(f"Using cached prices for {ticker}")
                return cached_prices
        
        # Fetch from API
        logger.info(f"Fetching {ticker} data from yfinance")
        prices = self._fetch_from_yfinance(ticker, start_date, end_date)
        
        if prices is not None and not prices.empty:
            # Cache the data
            self._cache_prices(ticker, prices)
        
        return prices
    
    def _get_cached_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.Series]:
        """Get prices from cache."""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                query = """
                    SELECT price_date, adjusted_close
                    FROM benchmark_prices
                    WHERE ticker = ? AND price_date >= ? AND price_date <= ?
                    ORDER BY price_date
                """
                df = pd.read_sql_query(
                    query,
                    conn,
                    params=(ticker, start_date.isoformat(), end_date.isoformat())
                )
                
                if df.empty:
                    return None
                
                df['price_date'] = pd.to_datetime(df['price_date']).dt.date
                df = df.set_index('price_date')
                
                return df['adjusted_close']
                
        except Exception as e:
            logger.warning(f"Error reading cache: {e}")
            return None
    
    def _fetch_from_yfinance(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.Series]:
        """Fetch price data from yfinance."""
        try:
            import yfinance as yf
            
            # Add buffer to ensure we get all data
            buffer_start = start_date - timedelta(days=7)
            buffer_end = end_date + timedelta(days=1)
            
            # Download data
            data = yf.download(
                ticker,
                start=buffer_start,
                end=buffer_end,
                progress=False
            )
            
            if data.empty:
                logger.warning(f"No data returned from yfinance for {ticker}")
                return None
            
            # Extract adjusted close
            if 'Adj Close' in data.columns:
                prices = data['Adj Close']
            elif 'Close' in data.columns:
                prices = data['Close']
            else:
                logger.error(f"No price column found for {ticker}")
                return None
            
            # Filter to requested date range
            prices = prices[
                (prices.index.date >= start_date) &
                (prices.index.date <= end_date)
            ]
            
            # Convert index to date
            prices.index = prices.index.date
            
            logger.info(f"Fetched {len(prices)} prices for {ticker}")
            return prices
            
        except ImportError:
            logger.error("yfinance not installed. Install with: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"Error fetching from yfinance: {e}")
            return None
    
    def _cache_prices(self, ticker: str, prices: pd.Series):
        """Cache price data."""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.cursor()
                
                for price_date, price in prices.items():
                    # Convert price_date to string format
                    if hasattr(price_date, 'isoformat'):
                        date_str = price_date.isoformat()
                    elif hasattr(price_date, 'strftime'):
                        date_str = price_date.strftime('%Y-%m-%d')
                    else:
                        date_str = str(price_date)
                    
                    # Convert price to float (handle Series)
                    if isinstance(price, pd.Series):
                        price_val = float(price.iloc[0])
                    else:
                        price_val = float(price)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO benchmark_prices
                        (ticker, price_date, close_price, adjusted_close)
                        VALUES (?, ?, ?, ?)
                    """, (ticker, date_str, price_val, price_val))
                
                conn.commit()
                logger.debug(f"Cached {len(prices)} prices for {ticker}")
                
        except Exception as e:
            logger.warning(f"Error caching prices: {e}")
    
    def _get_composite_benchmark_returns(
        self,
        benchmark_type: BenchmarkType,
        start_date: date,
        end_date: date,
        force_refresh: bool = False
    ) -> Optional[BenchmarkReturns]:
        """Get returns for composite benchmarks (60/40, All Weather, etc.)."""
        try:
            if benchmark_type == BenchmarkType.BALANCED_60_40:
                # 60% stocks (VTI), 40% bonds (AGG)
                stock_returns = self.get_benchmark_returns(
                    BenchmarkType.TOTAL_MARKET, start_date, end_date, force_refresh
                )
                bond_returns = self.get_benchmark_returns(
                    BenchmarkType.AGGREGATE_BOND, start_date, end_date, force_refresh
                )
                
                if stock_returns and bond_returns:
                    # Combine returns
                    total_return = 0.6 * stock_returns.total_return + 0.4 * bond_returns.total_return
                    annualized_return = 0.6 * stock_returns.annualized_return + 0.4 * bond_returns.annualized_return
                    volatility = np.sqrt(
                        (0.6 ** 2) * (stock_returns.volatility ** 2) +
                        (0.4 ** 2) * (bond_returns.volatility ** 2) +
                        2 * 0.6 * 0.4 * stock_returns.volatility * bond_returns.volatility * 0.2  # Assume 0.2 correlation
                    )
                    
                    # Combine daily returns
                    daily_returns = 0.6 * stock_returns.daily_returns + 0.4 * bond_returns.daily_returns
                    
                    # Combine prices (weighted)
                    prices = 0.6 * stock_returns.prices + 0.4 * bond_returns.prices
                    
                    return BenchmarkReturns(
                        benchmark_type=benchmark_type,
                        start_date=start_date,
                        end_date=end_date,
                        total_return=total_return,
                        annualized_return=annualized_return,
                        volatility=volatility,
                        daily_returns=daily_returns,
                        prices=prices
                    )
            
            elif benchmark_type == BenchmarkType.BALANCED_40_60:
                # 40% stocks, 60% bonds
                stock_returns = self.get_benchmark_returns(
                    BenchmarkType.TOTAL_MARKET, start_date, end_date, force_refresh
                )
                bond_returns = self.get_benchmark_returns(
                    BenchmarkType.AGGREGATE_BOND, start_date, end_date, force_refresh
                )
                
                if stock_returns and bond_returns:
                    total_return = 0.4 * stock_returns.total_return + 0.6 * bond_returns.total_return
                    annualized_return = 0.4 * stock_returns.annualized_return + 0.6 * bond_returns.annualized_return
                    volatility = np.sqrt(
                        (0.4 ** 2) * (stock_returns.volatility ** 2) +
                        (0.6 ** 2) * (bond_returns.volatility ** 2) +
                        2 * 0.4 * 0.6 * stock_returns.volatility * bond_returns.volatility * 0.2
                    )
                    
                    daily_returns = 0.4 * stock_returns.daily_returns + 0.6 * bond_returns.daily_returns
                    prices = 0.4 * stock_returns.prices + 0.6 * bond_returns.prices
                    
                    return BenchmarkReturns(
                        benchmark_type=benchmark_type,
                        start_date=start_date,
                        end_date=end_date,
                        total_return=total_return,
                        annualized_return=annualized_return,
                        volatility=volatility,
                        daily_returns=daily_returns,
                        prices=prices
                    )
            
            # Add more composite benchmarks as needed
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating composite benchmark: {e}")
            return None
    
    def calculate_advanced_metrics(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: BenchmarkReturns,
        risk_free_rate: float = 0.04
    ) -> Optional[AdvancedMetrics]:
        """
        Calculate advanced performance metrics.
        
        Args:
            portfolio_returns: Series of portfolio daily returns
            benchmark_returns: Benchmark return data
            risk_free_rate: Annual risk-free rate (default: 4%)
            
        Returns:
            AdvancedMetrics object or None
        """
        try:
            # Align returns
            aligned_portfolio, aligned_benchmark = portfolio_returns.align(
                benchmark_returns.daily_returns,
                join='inner'
            )
            
            if len(aligned_portfolio) < 30:  # Need sufficient data
                logger.warning("Insufficient data for advanced metrics")
                return None
            
            # Calculate excess returns
            excess_returns = aligned_portfolio - aligned_benchmark
            
            # Beta: Covariance(portfolio, benchmark) / Variance(benchmark)
            covariance = aligned_portfolio.cov(aligned_benchmark)
            benchmark_variance = aligned_benchmark.var()
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
            
            # Alpha: Portfolio return - (Risk-free rate + Beta * (Benchmark return - Risk-free rate))
            portfolio_return = (1 + aligned_portfolio).prod() - 1
            benchmark_return = (1 + aligned_benchmark).prod() - 1
            alpha = portfolio_return - (risk_free_rate + beta * (benchmark_return - risk_free_rate))
            
            # Tracking Error: Standard deviation of excess returns
            tracking_error = excess_returns.std() * np.sqrt(252)  # Annualized
            
            # Information Ratio: Excess return / Tracking error
            annualized_excess = excess_returns.mean() * 252
            information_ratio = annualized_excess / tracking_error if tracking_error > 0 else 0
            
            # Correlation and R-squared
            correlation = aligned_portfolio.corr(aligned_benchmark)
            r_squared = correlation ** 2
            
            # Sharpe Ratio
            portfolio_volatility = aligned_portfolio.std() * np.sqrt(252)
            sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_volatility if portfolio_volatility > 0 else 0
            
            # Sortino Ratio (downside deviation)
            downside_returns = aligned_portfolio[aligned_portfolio < 0]
            downside_deviation = downside_returns.std() * np.sqrt(252)
            sortino_ratio = (portfolio_return - risk_free_rate) / downside_deviation if downside_deviation > 0 else 0
            
            # Maximum Drawdown
            cumulative = (1 + aligned_portfolio).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()
            
            # Capture Ratios
            up_months = aligned_benchmark > 0
            down_months = aligned_benchmark < 0
            
            if up_months.sum() > 0:
                up_capture = aligned_portfolio[up_months].mean() / aligned_benchmark[up_months].mean()
            else:
                up_capture = 0
            
            if down_months.sum() > 0:
                down_capture = aligned_portfolio[down_months].mean() / aligned_benchmark[down_months].mean()
            else:
                down_capture = 0
            
            return AdvancedMetrics(
                beta=beta,
                alpha=alpha,
                information_ratio=information_ratio,
                tracking_error=tracking_error,
                correlation=correlation,
                r_squared=r_squared,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=max_drawdown,
                up_capture=up_capture,
                down_capture=down_capture
            )
            
        except Exception as e:
            logger.error(f"Error calculating advanced metrics: {e}")
            return None


# Convenience functions
def get_benchmark_provider() -> BenchmarkDataProvider:
    """Get a BenchmarkDataProvider instance."""
    return BenchmarkDataProvider()


def get_available_benchmarks() -> Dict[BenchmarkType, BenchmarkConfig]:
    """Get all available benchmark configurations."""
    return BENCHMARK_CONFIGS.copy()

# Made with Bob
