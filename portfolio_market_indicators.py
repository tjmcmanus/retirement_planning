"""
Portfolio Market Indicators Module
===================================
Provides market condition indicators for individual securities in the portfolio.

This module analyzes each security using the short-term market forecast algorithm
(10-week and 50-week moving averages) to provide actionable market indicators.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SHORT_MA_WEEKS = 10
DEFAULT_LONG_MA_WEEKS = 50
CACHE_TTL_HOURS = 1  # Cache indicators for 1 hour

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SecurityMarketCondition(Enum):
    """Market condition for individual securities."""
    STRONG_BUY = "strong_buy"      # Both MAs positive, price above both
    BUY = "buy"                     # Both MAs positive
    HOLD = "hold"                   # Mixed signals
    CAUTION = "caution"             # Warning signals
    SELL = "sell"                   # Both MAs negative
    UNKNOWN = "unknown"             # Unable to determine

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class SecurityIndicator:
    """Market indicator for a security."""
    symbol: str
    condition: SecurityMarketCondition
    short_ma: float
    long_ma: float
    current_price: float
    short_trend: str  # "up", "down", "neutral"
    long_trend: str   # "up", "down", "neutral"
    confidence: float  # 0.0-1.0
    recommendation: str  # Human-readable recommendation
    emoji: str  # Visual indicator
    calculation_date: datetime

# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

_indicator_cache: Dict[str, tuple[SecurityIndicator, datetime]] = {}


def _get_cached_indicator(symbol: str) -> Optional[SecurityIndicator]:
    """Get cached indicator if still valid."""
    if symbol not in _indicator_cache:
        return None
    
    indicator, cache_time = _indicator_cache[symbol]
    cache_age = datetime.now() - cache_time
    
    if cache_age.total_seconds() / 3600 < CACHE_TTL_HOURS:
        logger.debug(f"Using cached indicator for {symbol} (age: {cache_age})")
        return indicator
    
    return None


def _cache_indicator(indicator: SecurityIndicator) -> None:
    """Cache indicator with timestamp."""
    _indicator_cache[indicator.symbol] = (indicator, datetime.now())


def clear_indicator_cache() -> None:
    """Clear all cached indicators."""
    global _indicator_cache
    _indicator_cache = {}
    logger.info("Security indicator cache cleared")

# ---------------------------------------------------------------------------
# Data Fetching
# ---------------------------------------------------------------------------

def fetch_security_data(symbol: str, weeks: int) -> Optional[pd.DataFrame]:
    """
    Fetch historical data for a security.
    
    Args:
        symbol: Ticker symbol
        weeks: Number of weeks of historical data
        
    Returns:
        DataFrame with price data, or None if fetch fails
    """
    # Skip cash holdings
    if symbol.upper() in ['MF:CASH', 'CASH']:
        return None
    
    try:
        days = int(weeks * 7 * 1.2)  # 20% buffer
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        
        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return None
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None

# ---------------------------------------------------------------------------
# Indicator Calculation
# ---------------------------------------------------------------------------

def calculate_security_indicator(
    symbol: str,
    short_ma_weeks: int = DEFAULT_SHORT_MA_WEEKS,
    long_ma_weeks: int = DEFAULT_LONG_MA_WEEKS
) -> Optional[SecurityIndicator]:
    """
    Calculate market indicator for a security.
    
    Args:
        symbol: Ticker symbol
        short_ma_weeks: Short moving average period (default: 10)
        long_ma_weeks: Long moving average period (default: 50)
        
    Returns:
        SecurityIndicator with analysis results, or None if calculation fails
    """
    # Check cache first
    cached = _get_cached_indicator(symbol)
    if cached is not None:
        return cached
    
    # Skip cash holdings
    if symbol.upper() in ['MF:CASH', 'CASH']:
        indicator = SecurityIndicator(
            symbol=symbol,
            condition=SecurityMarketCondition.HOLD,
            short_ma=1.0,
            long_ma=1.0,
            current_price=1.0,
            short_trend="neutral",
            long_trend="neutral",
            confidence=1.0,
            recommendation="Cash holding",
            emoji="💵",
            calculation_date=datetime.now()
        )
        _cache_indicator(indicator)
        return indicator
    
    # Fetch data
    df = fetch_security_data(symbol, long_ma_weeks)
    if df is None or df.empty:
        return None
    
    try:
        # Calculate weekly data
        weekly_df = df['Close'].resample('W').last().dropna()
        
        if len(weekly_df) < long_ma_weeks:
            logger.warning(f"Insufficient data for {symbol}: need {long_ma_weeks} weeks, have {len(weekly_df)}")
            return None
        
        # Calculate moving averages
        short_ma = weekly_df.rolling(window=short_ma_weeks).mean().iloc[-1]
        long_ma = weekly_df.rolling(window=long_ma_weeks).mean().iloc[-1]
        current_price = weekly_df.iloc[-1]
        
        # Calculate slopes (rate of change)
        lookback_weeks = 4
        if len(weekly_df) >= short_ma_weeks + lookback_weeks:
            short_ma_prev = weekly_df.rolling(window=short_ma_weeks).mean().iloc[-(lookback_weeks+1)]
            short_slope = ((short_ma - short_ma_prev) / short_ma_prev) * 100 / lookback_weeks
        else:
            short_slope = 0.0
        
        if len(weekly_df) >= long_ma_weeks + lookback_weeks:
            long_ma_prev = weekly_df.rolling(window=long_ma_weeks).mean().iloc[-(lookback_weeks+1)]
            long_slope = ((long_ma - long_ma_prev) / long_ma_prev) * 100 / lookback_weeks
        else:
            long_slope = 0.0
        
        # Determine trends
        slope_threshold = 0.05
        short_trend = "up" if short_slope > slope_threshold else "down" if short_slope < -slope_threshold else "neutral"
        long_trend = "up" if long_slope > slope_threshold else "down" if long_slope < -slope_threshold else "neutral"
        
        # Calculate confidence
        max_slope = 2.0
        confidence = min(1.0, (abs(short_slope) + abs(long_slope)) / (2 * max_slope))
        
        # Determine condition
        short_positive = short_trend == "up"
        long_positive = long_trend == "up"
        price_above_short = current_price > short_ma
        price_above_long = current_price > long_ma
        
        if short_positive and long_positive and price_above_short and price_above_long:
            condition = SecurityMarketCondition.STRONG_BUY
            recommendation = "Strong uptrend - consider buying"
            emoji = "🚀"
        elif short_positive and long_positive:
            condition = SecurityMarketCondition.BUY
            recommendation = "Uptrend - favorable"
            emoji = "📈"
        elif not short_positive and not long_positive:
            condition = SecurityMarketCondition.SELL
            recommendation = "Downtrend - consider reducing"
            emoji = "📉"
        elif not short_positive and long_positive:
            condition = SecurityMarketCondition.CAUTION
            recommendation = "Early warning - monitor closely"
            emoji = "⚠️"
        elif short_positive and not long_positive:
            condition = SecurityMarketCondition.HOLD
            recommendation = "Recovery attempt - wait for confirmation"
            emoji = "🔄"
        else:
            condition = SecurityMarketCondition.HOLD
            recommendation = "Mixed signals - hold position"
            emoji = "➖"
        
        indicator = SecurityIndicator(
            symbol=symbol,
            condition=condition,
            short_ma=short_ma,
            long_ma=long_ma,
            current_price=current_price,
            short_trend=short_trend,
            long_trend=long_trend,
            confidence=confidence,
            recommendation=recommendation,
            emoji=emoji,
            calculation_date=datetime.now()
        )
        
        # Cache the result
        _cache_indicator(indicator)
        
        logger.info(f"Indicator calculated for {symbol}: {condition.value} ({emoji})")
        return indicator
        
    except Exception as e:
        logger.error(f"Error calculating indicator for {symbol}: {e}")
        return None


def get_indicator_summary(indicator: SecurityIndicator) -> str:
    """
    Get a formatted summary of the indicator.
    
    Args:
        indicator: Security indicator
        
    Returns:
        Formatted summary string
    """
    return f"""{indicator.emoji} {indicator.condition.value.upper().replace('_', ' ')}
Price: ${indicator.current_price:.2f}
10-Week MA: ${indicator.short_ma:.2f} ({indicator.short_trend})
50-Week MA: ${indicator.long_ma:.2f} ({indicator.long_trend})
Confidence: {indicator.confidence:.0%}
{indicator.recommendation}"""


def get_portfolio_indicators(symbols: list[str]) -> Dict[str, Optional[SecurityIndicator]]:
    """
    Get market indicators for multiple securities.
    
    Args:
        symbols: List of ticker symbols
        
    Returns:
        Dictionary mapping symbols to their indicators
    """
    indicators = {}
    for symbol in symbols:
        indicators[symbol] = calculate_security_indicator(symbol)
    return indicators


# Made with Bob