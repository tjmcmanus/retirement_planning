"""
Market Trend Analysis Module
============================
Analyzes market conditions using SPY (S&P 500 ETF) exponential moving averages
to inform bucket strategy rebalancing decisions.

This module implements a 4-state market condition system based on 10-week and
50-week exponential moving averages (EMAs):
- Bull Case: Both EMAs trending positive
- Warning Negative: 10-week EMA negative, 50-week EMA positive
- Warning Positive: 10-week EMA positive, 50-week EMA negative
- Bear Case: Both EMAs trending negative

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
DEFAULT_SHORT_EMA_WEEKS = 10
DEFAULT_LONG_EMA_WEEKS = 50
CACHE_TTL_HOURS = 1  # Cache market conditions for 1 hour
MIN_STATE_DURATION_DAYS = 3  # Minimum days in state before transition


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MarketCondition(Enum):
    """Market condition states. Driven solely by the long (50-week) EMA."""
    BULL = "bull"       # 50-week EMA positive — long trend intact
    NEUTRAL = "neutral" # 50-week EMA flat — no clear direction
    BEAR = "bear"       # 50-week EMA negative — sustained downtrend
    UNKNOWN = "unknown" # Unable to determine (data issues)


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
    """Exponential moving average calculation results."""
    short_ema: float              # 10-week EMA value
    long_ema: float               # 50-week EMA value
    current_price: float          # Current SPY price
    short_trend: TrendDirection   # 10-week EMA trend
    long_trend: TrendDirection    # 50-week EMA trend
    short_slope: float            # Rate of change of short EMA (% per week)
    long_slope: float             # Rate of change of long EMA (% per week)
    price_vs_short_ema: float     # Price relative to short EMA (%)
    price_vs_long_ema: float      # Price relative to long EMA (%)
    ema_crossover_distance: float # Distance between EMAs: (short-long)/long * 100 (%)
    weeks_in_trend: int           # Estimated weeks in current trend
    calculation_date: datetime    # When this was calculated
    confidence: float             # Confidence score 0.0-1.0 based on slope magnitudes


@dataclass
class MarketTrendConfig:
    """Configuration for market trend analysis."""
    short_ema_weeks: int = DEFAULT_SHORT_EMA_WEEKS
    long_ema_weeks: int = DEFAULT_LONG_EMA_WEEKS
    cache_ttl_hours: int = CACHE_TTL_HOURS
    min_state_duration_days: int = MIN_STATE_DURATION_DAYS
    enabled: bool = True
    # Allocation adjustment percentages for each market state
    bull_adjustment: float = 0.0    # No adjustment in bull market
    neutral_adjustment: float = 0.0  # No adjustment when consolidating
    bear_adjustment: float = -20.0  # Reduce stocks by 20% in bear market


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

_market_condition_cache: Optional[Tuple[MarketCondition, MovingAverageData, datetime]] = None
# Last error message from a failed fetch/calculation, cleared on success.
_last_fetch_error: Optional[str] = None


def get_last_fetch_error() -> Optional[str]:
    """Return the most recent market-data failure reason, or None if last fetch succeeded.

    Callers (UI pages, bucket strategy) can surface this string to inform the
    user *why* market condition shows as UNKNOWN rather than showing a generic
    "data unavailable" message.
    """
    return _last_fetch_error


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
    global _last_fetch_error
    try:
        # Add 20% buffer to ensure we have enough data for MA calculation
        days = int(weeks * 7 * 1.2)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.debug(f"Fetching SPY data from {start_date.date()} to {end_date.date()}")
        
        spy = yf.Ticker(SPY_SYMBOL)
        df = spy.history(start=start_date, end=end_date)
        
        if df.empty:
            _last_fetch_error = "No SPY price data returned from market data provider"
            logger.error(_last_fetch_error)
            return None
        
        logger.debug(f"Fetched {len(df)} days of SPY data")
        return df
        
    except Exception as e:
        _last_fetch_error = f"Market data fetch failed: {e}"
        logger.error(_last_fetch_error, exc_info=True)
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
    # Fetch data for the longer EMA period
    max_weeks = max(config.short_ema_weeks, config.long_ema_weeks)
    df = fetch_spy_data(max_weeks)

    if df is None or df.empty:
        logger.error("Cannot calculate EMAs: no data available")
        return None

    try:
        # Resample daily closes to weekly closes for EMA calculation
        weekly_df = df['Close'].resample('W').last().dropna()

        if len(weekly_df) < config.long_ema_weeks:
            logger.error(f"Insufficient data: need {config.long_ema_weeks} weeks, have {len(weekly_df)}")
            return None

        # Calculate EMAs using pandas ewm (exponential weighted moving average)
        short_ema_series = weekly_df.ewm(span=config.short_ema_weeks, adjust=False).mean()
        long_ema_series  = weekly_df.ewm(span=config.long_ema_weeks,  adjust=False).mean()

        short_ema     = short_ema_series.iloc[-1]
        long_ema      = long_ema_series.iloc[-1]
        current_price = weekly_df.iloc[-1]

        # Calculate slopes (rate of change as % per week)
        # Compare current EMA to EMA from 4 weeks ago
        lookback_weeks = 4
        if len(weekly_df) >= lookback_weeks + 1:
            short_ema_prev = short_ema_series.iloc[-(lookback_weeks + 1)]
            long_ema_prev  = long_ema_series.iloc[-(lookback_weeks + 1)]
            short_slope = (((short_ema - short_ema_prev) / short_ema_prev) * 100 / lookback_weeks
                           if short_ema_prev != 0 else 0.0)
            long_slope  = (((long_ema  - long_ema_prev)  / long_ema_prev)  * 100 / lookback_weeks
                           if long_ema_prev  != 0 else 0.0)
        else:
            short_slope = 0.0
            long_slope  = 0.0

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

        # Calculate price relative to EMAs
        price_vs_short_ema = ((current_price - short_ema) / short_ema) * 100 if short_ema != 0 else 0.0
        price_vs_long_ema  = ((current_price - long_ema)  / long_ema)  * 100 if long_ema  != 0 else 0.0

        # Calculate EMA crossover distance
        ema_crossover_distance = ((short_ema - long_ema) / long_ema) * 100 if long_ema != 0 else 0.0

        # Calculate confidence score based on slope magnitudes
        # Scale: 0.0 (flat) to 1.0 (strong trend); 2% per week = very strong
        max_slope  = 2.0
        confidence = min(1.0, (abs(short_slope) + abs(long_slope)) / (2 * max_slope))

        # Estimate weeks in current trend
        weeks_in_trend = 1
        for i in range(2, min(21, len(short_ema_series))):
            prev_ema      = short_ema_series.iloc[-i]
            prev_prev_ema = short_ema_series.iloc[-(i + 1)]
            if prev_prev_ema == 0:
                break
            prev_slope = ((prev_ema - prev_prev_ema) / prev_prev_ema) * 100
            if short_trend == TrendDirection.POSITIVE and prev_slope > slope_threshold:
                weeks_in_trend += 1
            elif short_trend == TrendDirection.NEGATIVE and prev_slope < -slope_threshold:
                weeks_in_trend += 1
            else:
                break

        ma_data = MovingAverageData(
            short_ema=short_ema,
            long_ema=long_ema,
            current_price=current_price,
            short_trend=short_trend,
            long_trend=long_trend,
            short_slope=short_slope,
            long_slope=long_slope,
            price_vs_short_ema=price_vs_short_ema,
            price_vs_long_ema=price_vs_long_ema,
            ema_crossover_distance=ema_crossover_distance,
            weeks_in_trend=weeks_in_trend,
            calculation_date=datetime.now(),
            confidence=confidence,
        )

        logger.info(
            f"EMA calculated: Short={short_ema:.2f} ({short_trend.value}, {short_slope:+.3f}%/wk), "
            f"Long={long_ema:.2f} ({long_trend.value}, {long_slope:+.3f}%/wk), "
            f"Price={current_price:.2f}, Confidence={confidence:.2f}, "
            f"Weeks in trend={weeks_in_trend}"
        )
        
        return ma_data
        
    except Exception as e:
        _last_fetch_error = f"EMA calculation failed: {e}"
        logger.error(_last_fetch_error, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Market Condition Determination
# ---------------------------------------------------------------------------

def get_market_subphase(ma_data: MovingAverageData) -> str:
    """
    Return the market sub-phase label driven by the short (10-week) EMA direction.

    Accumulation  — short EMA rising  (buyers stepping in)
    Consolidating — short EMA flat    (no directional pressure)
    Distribution  — short EMA falling (sellers taking over)
    """
    if ma_data.short_trend == TrendDirection.POSITIVE:
        return "Accumulation"
    elif ma_data.short_trend == TrendDirection.NEGATIVE:
        return "Distribution"
    else:
        return "Consolidating"


def determine_market_condition(ma_data: MovingAverageData) -> MarketCondition:
    """
    Determine intermediate-term market condition based on EMA trends.

    The long (50-week) EMA sets the regime; the short (10-week) EMA determines
    the sub-phase (see get_market_subphase).

    Decision matrix:
      Long EMA    Result
      POSITIVE    BULL
      NEUTRAL     NEUTRAL
      NEGATIVE    BEAR

    Args:
        ma_data: EMA data

    Returns:
        MarketCondition enum value
    """
    if ma_data.long_trend == TrendDirection.POSITIVE:
        return MarketCondition.BULL
    elif ma_data.long_trend == TrendDirection.NEGATIVE:
        return MarketCondition.BEAR
    else:
        return MarketCondition.NEUTRAL


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
        reason = _last_fetch_error or "Unknown error fetching market data"
        logger.warning("Unable to calculate market condition, returning UNKNOWN. Reason: %s", reason)
        return MarketCondition.UNKNOWN, None
    
    # Successful fetch — clear the stale error
    global _last_fetch_error
    _last_fetch_error = None

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
        MarketCondition.NEUTRAL: config.neutral_adjustment,
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

    subphase = get_market_subphase(ma_data)

    summary = f"""Market Condition: {condition.value.upper()} ({subphase})
Current SPY Price: ${ma_data.current_price:.2f}
10-Week EMA: ${ma_data.short_ema:.2f} ({ma_data.short_trend.value}, {ma_data.short_slope:+.2f}%/week)
50-Week EMA: ${ma_data.long_ema:.2f} ({ma_data.long_trend.value}, {ma_data.long_slope:+.2f}%/week)
Confidence: {ma_data.confidence:.0%}
Updated: {ma_data.calculation_date.strftime('%Y-%m-%d %H:%M')}"""
    
    return summary


# Made with Bob