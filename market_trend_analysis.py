"""
Market Trend Analysis Module
============================
Analyzes market conditions using SPY (S&P 500 ETF) moving averages to inform
bucket strategy rebalancing decisions.

This module implements a 4-state market condition system based on 10-week and
50-week moving averages:
- Bull Case: Both MAs trending positive
- Warning Negative: 10-week MA negative, 50-week MA positive
- Warning Positive: 10-week MA positive, 50-week MA negative
- Bear Case: Both MAs trending negative

The market condition influences bucket allocation adjustments and rebalancing
triggers to help manage sequence of returns risk.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Tuple

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPY_SYMBOL = "SPY"
DEFAULT_SHORT_MA_WEEKS = 10
DEFAULT_LONG_MA_WEEKS = 50
CACHE_TTL_HOURS = 1  # Cache market conditions for 1 hour
MIN_STATE_DURATION_DAYS = 3  # Minimum days in state before transition


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MarketCondition(Enum):
    """Market condition states based on moving average trends."""
    BULL = "bull"  # Both MAs positive
    WARNING_NEGATIVE = "warning_negative"  # 10-week down, 50-week up
    WARNING_POSITIVE = "warning_positive"  # 10-week up, 50-week down
    BEAR = "bear"  # Both MAs negative
    UNKNOWN = "unknown"  # Unable to determine (data issues)


class TrendDirection(Enum):
    """Direction of moving average trend."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class MovingAverageData:
    """Moving average calculation results."""
    short_ma: float  # 10-week MA value
    long_ma: float  # 50-week MA value
    current_price: float  # Current SPY price
    short_trend: TrendDirection  # 10-week MA trend
    long_trend: TrendDirection  # 50-week MA trend
    short_slope: float  # Rate of change of short MA (% per week)
    long_slope: float  # Rate of change of long MA (% per week)
    calculation_date: datetime  # When this was calculated
    confidence: float  # Confidence score 0.0-1.0 based on slope magnitudes


@dataclass
class MarketTrendConfig:
    """Configuration for market trend analysis."""
    short_ma_weeks: int = DEFAULT_SHORT_MA_WEEKS
    long_ma_weeks: int = DEFAULT_LONG_MA_WEEKS
    cache_ttl_hours: int = CACHE_TTL_HOURS
    min_state_duration_days: int = MIN_STATE_DURATION_DAYS
    enabled: bool = True
    # Allocation adjustment percentages for each market state
    bull_adjustment: float = 0.0  # No adjustment in bull market
    warning_adjustment: float = -10.0  # Reduce stocks by 10% in warning states
    bear_adjustment: float = -20.0  # Reduce stocks by 20% in bear market


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

_market_condition_cache: Optional[Tuple[MarketCondition, MovingAverageData, datetime]] = None


def _get_cached_condition() -> Optional[Tuple[MarketCondition, MovingAverageData]]:
    """
    Get cached market condition if still valid.
    
    Returns:
        Tuple of (MarketCondition, MovingAverageData) if cache valid, None otherwise
    """
    global _market_condition_cache
    if _market_condition_cache is None:
        return None
    
    condition, ma_data, cache_time = _market_condition_cache
    cache_age = datetime.now() - cache_time
    
    if cache_age.total_seconds() / 3600 < CACHE_TTL_HOURS:
        logger.debug(f"Using cached market condition: {condition.value} (age: {cache_age})")
        return condition, ma_data
    
    logger.debug(f"Cache expired (age: {cache_age}), will fetch new data")
    return None


def _cache_condition(condition: MarketCondition, ma_data: MovingAverageData) -> None:
    """
    Cache market condition with timestamp.
    
    Args:
        condition: Market condition to cache
        ma_data: Moving average data to cache
    """
    global _market_condition_cache
    _market_condition_cache = (condition, ma_data, datetime.now())
    logger.debug(f"Cached market condition: {condition.value}")


def clear_market_condition_cache() -> None:
    """Clear the market condition cache. Useful for testing or forcing refresh."""
    global _market_condition_cache
    _market_condition_cache = None
    logger.info("Market condition cache cleared")


# ---------------------------------------------------------------------------
# Data Fetching
# ---------------------------------------------------------------------------

def fetch_spy_data(weeks: int) -> Optional[pd.DataFrame]:
    """
    Fetch SPY historical data for the specified number of weeks.
    
    Args:
        weeks: Number of weeks of historical data to fetch
        
    Returns:
        DataFrame with SPY price data, or None if fetch fails
    """
    try:
        # Add 20% buffer to ensure we have enough data for MA calculation
        days = int(weeks * 7 * 1.2)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.debug(f"Fetching SPY data from {start_date.date()} to {end_date.date()}")
        
        spy = yf.Ticker(SPY_SYMBOL)
        df = spy.history(start=start_date, end=end_date)
        
        if df.empty:
            logger.error("No SPY data returned from yfinance")
            return None
        
        logger.debug(f"Fetched {len(df)} days of SPY data")
        return df
        
    except Exception as e:
        logger.error(f"Error fetching SPY data: {e}")
        return None


# ---------------------------------------------------------------------------
# Moving Average Calculations
# ---------------------------------------------------------------------------

def calculate_moving_averages(
    config: MarketTrendConfig = MarketTrendConfig()
) -> Optional[MovingAverageData]:
    """
    Calculate moving averages and trends for SPY.
    
    Args:
        config: Configuration for MA calculation
        
    Returns:
        MovingAverageData with calculation results, or None if calculation fails
    """
    # Fetch data for the longer MA period
    max_weeks = max(config.short_ma_weeks, config.long_ma_weeks)
    df = fetch_spy_data(max_weeks)
    
    if df is None or df.empty:
        logger.error("Cannot calculate moving averages: no data available")
        return None
    
    try:
        # Calculate weekly data (resample to weekly close prices)
        weekly_df = df['Close'].resample('W').last().dropna()
        
        if len(weekly_df) < config.long_ma_weeks:
            logger.error(f"Insufficient data: need {config.long_ma_weeks} weeks, have {len(weekly_df)}")
            return None
        
        # Calculate moving averages
        short_ma = weekly_df.rolling(window=config.short_ma_weeks).mean().iloc[-1]
        long_ma = weekly_df.rolling(window=config.long_ma_weeks).mean().iloc[-1]
        current_price = weekly_df.iloc[-1]
        
        # Calculate slopes (rate of change as % per week)
        # Compare current MA to MA from 4 weeks ago
        lookback_weeks = 4
        if len(weekly_df) >= config.short_ma_weeks + lookback_weeks:
            short_ma_prev = weekly_df.rolling(window=config.short_ma_weeks).mean().iloc[-(lookback_weeks+1)]
            short_slope = ((short_ma - short_ma_prev) / short_ma_prev) * 100 / lookback_weeks
        else:
            short_slope = 0.0
        
        if len(weekly_df) >= config.long_ma_weeks + lookback_weeks:
            long_ma_prev = weekly_df.rolling(window=config.long_ma_weeks).mean().iloc[-(lookback_weeks+1)]
            long_slope = ((long_ma - long_ma_prev) / long_ma_prev) * 100 / lookback_weeks
        else:
            long_slope = 0.0
        
        # Determine trend directions
        # Use a threshold to avoid noise (0.05% per week)
        slope_threshold = 0.05
        short_trend = (
            TrendDirection.POSITIVE if short_slope > slope_threshold
            else TrendDirection.NEGATIVE if short_slope < -slope_threshold
            else TrendDirection.NEUTRAL
        )
        long_trend = (
            TrendDirection.POSITIVE if long_slope > slope_threshold
            else TrendDirection.NEGATIVE if long_slope < -slope_threshold
            else TrendDirection.NEUTRAL
        )
        
        # Calculate confidence score based on slope magnitudes
        # Higher slopes = higher confidence
        # Scale: 0.0 (flat) to 1.0 (strong trend)
        max_slope = 2.0  # 2% per week is considered very strong
        confidence = min(1.0, (abs(short_slope) + abs(long_slope)) / (2 * max_slope))
        
        ma_data = MovingAverageData(
            short_ma=short_ma,
            long_ma=long_ma,
            current_price=current_price,
            short_trend=short_trend,
            long_trend=long_trend,
            short_slope=short_slope,
            long_slope=long_slope,
            calculation_date=datetime.now(),
            confidence=confidence
        )
        
        logger.info(
            f"MA calculated: Short={short_ma:.2f} ({short_trend.value}, {short_slope:+.3f}%/wk), "
            f"Long={long_ma:.2f} ({long_trend.value}, {long_slope:+.3f}%/wk), "
            f"Price={current_price:.2f}, Confidence={confidence:.2f}"
        )
        
        return ma_data
        
    except Exception as e:
        logger.error(f"Error calculating moving averages: {e}")
        return None


# ---------------------------------------------------------------------------
# Market Condition Determination
# ---------------------------------------------------------------------------

def determine_market_condition(ma_data: MovingAverageData) -> MarketCondition:
    """
    Determine market condition based on moving average trends.
    
    Args:
        ma_data: Moving average data
        
    Returns:
        MarketCondition enum value
    """
    short_positive = ma_data.short_trend == TrendDirection.POSITIVE
    long_positive = ma_data.long_trend == TrendDirection.POSITIVE
    
    if short_positive and long_positive:
        return MarketCondition.BULL
    elif not short_positive and long_positive:
        return MarketCondition.WARNING_NEGATIVE
    elif short_positive and not long_positive:
        return MarketCondition.WARNING_POSITIVE
    elif not short_positive and not long_positive:
        return MarketCondition.BEAR
    else:
        # Both neutral - use price vs MA comparison as tiebreaker
        if ma_data.current_price > ma_data.short_ma and ma_data.current_price > ma_data.long_ma:
            return MarketCondition.BULL
        elif ma_data.current_price < ma_data.short_ma and ma_data.current_price < ma_data.long_ma:
            return MarketCondition.BEAR
        else:
            return MarketCondition.WARNING_NEGATIVE  # Default to caution


def get_market_condition(
    config: MarketTrendConfig = MarketTrendConfig(),
    use_cache: bool = True
) -> Tuple[MarketCondition, Optional[MovingAverageData]]:
    """
    Get current market condition with caching.
    
    Args:
        config: Configuration for market trend analysis
        use_cache: Whether to use cached result if available
        
    Returns:
        Tuple of (MarketCondition, MovingAverageData or None)
    """
    if not config.enabled:
        logger.info("Market trend analysis disabled in config")
        return MarketCondition.UNKNOWN, None
    
    # Check cache first
    if use_cache:
        cached = _get_cached_condition()
        if cached is not None:
            return cached
    
    # Calculate fresh data
    ma_data = calculate_moving_averages(config)
    
    if ma_data is None:
        logger.warning("Unable to calculate market condition, returning UNKNOWN")
        return MarketCondition.UNKNOWN, None
    
    condition = determine_market_condition(ma_data)
    
    # Cache the result
    _cache_condition(condition, ma_data)
    
    logger.info(f"Market condition determined: {condition.value}")
    return condition, ma_data


# ---------------------------------------------------------------------------
# Bucket Allocation Adjustments
# ---------------------------------------------------------------------------

def get_allocation_adjustment(
    condition: MarketCondition,
    config: MarketTrendConfig = MarketTrendConfig()
) -> float:
    """
    Get stock allocation adjustment percentage for the given market condition.
    
    Args:
        condition: Current market condition
        config: Configuration with adjustment percentages
        
    Returns:
        Adjustment percentage (negative = reduce stocks, positive = increase stocks)
    """
    adjustments = {
        MarketCondition.BULL: config.bull_adjustment,
        MarketCondition.WARNING_NEGATIVE: config.warning_adjustment,
        MarketCondition.WARNING_POSITIVE: config.warning_adjustment,
        MarketCondition.BEAR: config.bear_adjustment,
        MarketCondition.UNKNOWN: 0.0,
    }
    
    adjustment = adjustments.get(condition, 0.0)
    logger.debug(f"Allocation adjustment for {condition.value}: {adjustment:+.1f}%")
    return adjustment


def should_trigger_rebalance(
    condition: MarketCondition,
    previous_condition: Optional[MarketCondition],
    config: MarketTrendConfig = MarketTrendConfig()
) -> bool:
    """
    Determine if market condition change should trigger rebalancing.
    
    Args:
        condition: Current market condition
        previous_condition: Previous market condition (None if first check)
        config: Configuration with state duration requirements
        
    Returns:
        True if rebalancing should be triggered
    """
    # Always rebalance on first check
    if previous_condition is None:
        logger.info("First market condition check, triggering rebalance")
        return True
    
    # No rebalance if condition unchanged
    if condition == previous_condition:
        return False
    
    # Rebalance on any state transition
    # In production, you'd want to track state duration and only trigger
    # after min_state_duration_days, but that requires persistent storage
    logger.info(f"Market condition changed: {previous_condition.value} → {condition.value}")
    return True


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def format_market_condition_summary(
    condition: MarketCondition,
    ma_data: Optional[MovingAverageData]
) -> str:
    """
    Format a human-readable summary of market condition.
    
    Args:
        condition: Market condition
        ma_data: Moving average data (None if unavailable)
        
    Returns:
        Formatted summary string
    """
    if ma_data is None:
        return f"Market Condition: {condition.value.upper()} (data unavailable)"
    
    summary = f"""Market Condition: {condition.value.upper()}
Current SPY Price: ${ma_data.current_price:.2f}
10-Week MA: ${ma_data.short_ma:.2f} ({ma_data.short_trend.value}, {ma_data.short_slope:+.2f}%/week)
50-Week MA: ${ma_data.long_ma:.2f} ({ma_data.long_trend.value}, {ma_data.long_slope:+.2f}%/week)
Confidence: {ma_data.confidence:.0%}
Updated: {ma_data.calculation_date.strftime('%Y-%m-%d %H:%M')}"""
    
    return summary


# Made with Bob