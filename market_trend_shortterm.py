"""
Short-Term Market Trend Analysis Module
========================================
Analyzes short-term market conditions using SPY (S&P 500 ETF) exponential moving
averages to inform tactical trading and near-term portfolio decisions.

This module implements a 4-state market condition system based on 10-day and
50-day exponential moving averages (EMAs):
- Bull Case: Both EMAs trending positive
- Warning Negative: 10-day EMA negative, 50-day EMA positive
- Warning Positive: 10-day EMA positive, 50-day EMA negative
- Bear Case: Both EMAs trending negative

The short-term market condition provides tactical guidance for:
- Day trading and swing trading decisions
- Near-term risk adjustments
- Quick rebalancing opportunities
- Short-term hedging strategies

This complements the intermediate-term (10/50-week) and long-term (8/18-month)
analysis by providing the most granular perspective on market momentum.
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
DEFAULT_SHORT_EMA_DAYS = 10
DEFAULT_LONG_EMA_DAYS = 50
CACHE_TTL_MINUTES = 30  # Cache for 30 minutes (shorter for short-term)
MIN_STATE_DURATION_HOURS = 4  # Minimum hours in state before transition

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ShortTermMarketCondition(Enum):
    """Short-term market condition states based on EMA trends."""
    BULL = "bull"  # Both EMAs positive - strong uptrend
    WARNING_NEGATIVE = "warning_negative"  # 10-day down, 50-day up - early warning
    WARNING_POSITIVE = "warning_positive"  # 10-day up, 50-day down - recovery attempt
    BEAR = "bear"  # Both EMAs negative - sustained downtrend
    UNKNOWN = "unknown"  # Unable to determine (data issues)


class ShortTermTrendDirection(Enum):
    """Direction of EMA trend."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ShortTermEMAData:
    """Exponential moving average calculation results."""
    short_ema: float  # 10-day EMA value
    long_ema: float  # 50-day EMA value
    current_price: float  # Current SPY price
    short_trend: ShortTermTrendDirection  # 10-day EMA trend
    long_trend: ShortTermTrendDirection  # 50-day EMA trend
    short_slope: float  # Rate of change of short EMA (% per day)
    long_slope: float  # Rate of change of long EMA (% per day)
    price_vs_short_ema: float  # Price relative to short EMA (%)
    price_vs_long_ema: float  # Price relative to long EMA (%)
    ema_crossover_distance: float  # Distance between EMAs (%)
    calculation_date: datetime  # When this was calculated
    confidence: float  # Confidence score 0.0-1.0 based on slope magnitudes
    days_in_trend: int  # Estimated days in current trend


@dataclass
class ShortTermMarketTrendConfig:
    """Configuration for short-term market trend analysis."""
    short_ema_days: int = DEFAULT_SHORT_EMA_DAYS
    long_ema_days: int = DEFAULT_LONG_EMA_DAYS
    cache_ttl_minutes: int = CACHE_TTL_MINUTES
    min_state_duration_hours: int = MIN_STATE_DURATION_HOURS
    enabled: bool = True
    # Tactical allocation adjustment percentages for each market state
    bull_adjustment: float = 0.0  # No adjustment in bull market
    warning_adjustment: float = -3.0  # Reduce stocks by 3% in warning states
    bear_adjustment: float = -8.0  # Reduce stocks by 8% in bear market


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

_shortterm_condition_cache: Optional[Tuple[ShortTermMarketCondition, ShortTermEMAData, datetime]] = None


def _get_cached_shortterm_condition() -> Optional[Tuple[ShortTermMarketCondition, ShortTermEMAData]]:
    """
    Get cached short-term market condition if still valid.
    
    Returns:
        Tuple of (ShortTermMarketCondition, ShortTermEMAData) if cache valid, None otherwise
    """
    global _shortterm_condition_cache
    if _shortterm_condition_cache is None:
        return None
    
    condition, ema_data, cache_time = _shortterm_condition_cache
    cache_age = datetime.now() - cache_time
    
    if cache_age.total_seconds() / 60 < CACHE_TTL_MINUTES:
        logger.debug(f"Using cached short-term market condition: {condition.value} (age: {cache_age})")
        return condition, ema_data
    
    logger.debug(f"Short-term cache expired (age: {cache_age}), will fetch new data")
    return None


def _cache_shortterm_condition(condition: ShortTermMarketCondition, ema_data: ShortTermEMAData) -> None:
    """
    Cache short-term market condition with timestamp.
    
    Args:
        condition: Market condition to cache
        ema_data: EMA data to cache
    """
    global _shortterm_condition_cache
    _shortterm_condition_cache = (condition, ema_data, datetime.now())
    logger.debug(f"Cached short-term market condition: {condition.value}")


def clear_shortterm_market_condition_cache() -> None:
    """Clear the short-term market condition cache."""
    global _shortterm_condition_cache
    _shortterm_condition_cache = None
    logger.info("Short-term market condition cache cleared")


# ---------------------------------------------------------------------------
# Data Fetching
# ---------------------------------------------------------------------------

def fetch_spy_shortterm_data(days: int) -> Optional[pd.DataFrame]:
    """
    Fetch SPY historical data for the specified number of days.
    
    Args:
        days: Number of days of historical data to fetch
        
    Returns:
        DataFrame with SPY price data, or None if fetch fails
    """
    try:
        # Add 50% buffer to ensure we have enough data for EMA calculation
        fetch_days = int(days * 1.5)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=fetch_days)
        
        logger.debug(f"Fetching SPY short-term data from {start_date.date()} to {end_date.date()}")
        
        spy = yf.Ticker(SPY_SYMBOL)
        df = spy.history(start=start_date, end=end_date, interval="1d")
        
        if df.empty:
            logger.error("No SPY data returned from yfinance for short-term analysis")
            return None
        
        logger.debug(f"Fetched {len(df)} days of SPY data for short-term analysis")
        return df
        
    except Exception as e:
        logger.error(f"Error fetching SPY short-term data: {e}")
        return None


# ---------------------------------------------------------------------------
# EMA Calculations
# ---------------------------------------------------------------------------

def calculate_shortterm_emas(
    config: ShortTermMarketTrendConfig = ShortTermMarketTrendConfig()
) -> Optional[ShortTermEMAData]:
    """
    Calculate exponential moving averages and trends for SPY.
    
    Args:
        config: Configuration for EMA calculation
        
    Returns:
        ShortTermEMAData with calculation results, or None if calculation fails
    """
    # Fetch data for the longer EMA period
    max_days = max(config.short_ema_days, config.long_ema_days)
    df = fetch_spy_shortterm_data(max_days)
    
    if df is None or df.empty:
        logger.error("Cannot calculate short-term EMAs: no data available")
        return None
    
    try:
        # Use daily close prices for EMA calculation
        prices = df['Close'].dropna()
        
        if len(prices) < config.long_ema_days:
            logger.error(f"Insufficient data: need {config.long_ema_days} days, have {len(prices)}")
            return None
        
        # Calculate EMAs using pandas ewm (exponential weighted moving average)
        short_ema_series = prices.ewm(span=config.short_ema_days, adjust=False).mean()
        long_ema_series = prices.ewm(span=config.long_ema_days, adjust=False).mean()
        
        short_ema = short_ema_series.iloc[-1]
        long_ema = long_ema_series.iloc[-1]
        current_price = prices.iloc[-1]
        
        # Calculate slopes (rate of change as % per day)
        # Compare current EMA to EMA from 5 days ago
        lookback_days = 5
        if len(prices) >= lookback_days + 1:
            short_ema_prev = short_ema_series.iloc[-(lookback_days+1)]
            short_slope = ((short_ema - short_ema_prev) / short_ema_prev) * 100 / lookback_days  # per day
            
            long_ema_prev = long_ema_series.iloc[-(lookback_days+1)]
            long_slope = ((long_ema - long_ema_prev) / long_ema_prev) * 100 / lookback_days  # per day
        else:
            short_slope = 0.0
            long_slope = 0.0
        
        # Determine trend directions
        # Use a threshold to avoid noise (0.1% per day for short-term trends)
        slope_threshold = 0.1
        short_trend = (
            ShortTermTrendDirection.POSITIVE if short_slope > slope_threshold
            else ShortTermTrendDirection.NEGATIVE if short_slope < -slope_threshold
            else ShortTermTrendDirection.NEUTRAL
        )
        long_trend = (
            ShortTermTrendDirection.POSITIVE if long_slope > slope_threshold
            else ShortTermTrendDirection.NEGATIVE if long_slope < -slope_threshold
            else ShortTermTrendDirection.NEUTRAL
        )
        
        # Calculate price relative to EMAs
        price_vs_short_ema = ((current_price - short_ema) / short_ema) * 100
        price_vs_long_ema = ((current_price - long_ema) / long_ema) * 100
        
        # Calculate EMA crossover distance
        ema_crossover_distance = ((short_ema - long_ema) / long_ema) * 100
        
        # Calculate confidence score based on slope magnitudes
        # Higher slopes = higher confidence
        # Scale: 0.0 (flat) to 1.0 (strong trend)
        max_slope = 1.0  # 1% per day is considered very strong for short-term
        confidence = min(1.0, (abs(short_slope) + abs(long_slope)) / (2 * max_slope))
        
        # Estimate days in current trend (simplified)
        # Count consecutive periods where trend direction matches current
        days_in_trend = 1
        for i in range(2, min(21, len(short_ema_series))):  # Look back up to 20 days
            prev_ema = short_ema_series.iloc[-i]
            prev_prev_ema = short_ema_series.iloc[-(i+1)]
            prev_slope = ((prev_ema - prev_prev_ema) / prev_prev_ema) * 100
            
            if short_trend == ShortTermTrendDirection.POSITIVE and prev_slope > slope_threshold:
                days_in_trend += 1
            elif short_trend == ShortTermTrendDirection.NEGATIVE and prev_slope < -slope_threshold:
                days_in_trend += 1
            else:
                break
        
        ema_data = ShortTermEMAData(
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
            calculation_date=datetime.now(),
            confidence=confidence,
            days_in_trend=days_in_trend
        )
        
        logger.info(
            f"Short-term EMA calculated: Short={short_ema:.2f} ({short_trend.value}, {short_slope:+.3f}%/day), "
            f"Long={long_ema:.2f} ({long_trend.value}, {long_slope:+.3f}%/day), "
            f"Price={current_price:.2f}, Confidence={confidence:.2f}, "
            f"Days in trend={days_in_trend}"
        )
        
        return ema_data
        
    except Exception as e:
        logger.error(f"Error calculating short-term EMAs: {e}")
        return None


# ---------------------------------------------------------------------------
# Market Condition Determination
# ---------------------------------------------------------------------------

def determine_shortterm_market_condition(ema_data: ShortTermEMAData) -> ShortTermMarketCondition:
    """
    Determine short-term market condition based on EMA trends.

    Uses three explicit states per EMA (POSITIVE / NEUTRAL / NEGATIVE) so that
    flat/consolidating markets are not misclassified as BEAR.  When either EMA
    is NEUTRAL the price position relative to the EMAs acts as the tiebreaker.

    Decision matrix:
      Short       Long        Result
      POSITIVE    POSITIVE    BULL
      POSITIVE    NEUTRAL     BULL  (price above both; short trend healthy)
      NEUTRAL     POSITIVE    BULL  (long trend driving; price above)
      NEUTRAL     NEUTRAL     BULL if price > both EMAs, else WARNING_NEGATIVE
      NEGATIVE    POSITIVE    WARNING_NEGATIVE
      POSITIVE    NEGATIVE    WARNING_POSITIVE
      NEGATIVE    NEUTRAL     WARNING_NEGATIVE
      NEUTRAL     NEGATIVE    WARNING_NEGATIVE
      NEGATIVE    NEGATIVE    BEAR

    Args:
        ema_data: EMA data

    Returns:
        ShortTermMarketCondition enum value
    """
    short = ema_data.short_trend
    long  = ema_data.long_trend

    P = ShortTermTrendDirection.POSITIVE
    N = ShortTermTrendDirection.NEGATIVE
    U = ShortTermTrendDirection.NEUTRAL

    # --- Unambiguous cases ---
    if short == P and long == P:
        return ShortTermMarketCondition.BULL

    if short == N and long == N:
        return ShortTermMarketCondition.BEAR

    if short == N and long == P:
        return ShortTermMarketCondition.WARNING_NEGATIVE

    if short == P and long == N:
        return ShortTermMarketCondition.WARNING_POSITIVE

    # --- Cases involving NEUTRAL ---
    # Both neutral: use price position vs EMAs as tiebreaker
    if short == U and long == U:
        if ema_data.price_vs_short_ema > 0 and ema_data.price_vs_long_ema > 0:
            return ShortTermMarketCondition.BULL
        else:
            return ShortTermMarketCondition.WARNING_NEGATIVE

    # Short neutral, long positive → leaning bullish
    if short == U and long == P:
        return ShortTermMarketCondition.BULL

    # Short positive, long neutral → leaning bullish
    if short == P and long == U:
        return ShortTermMarketCondition.BULL

    # Short neutral, long negative → caution
    if short == U and long == N:
        return ShortTermMarketCondition.WARNING_NEGATIVE

    # Short negative, long neutral → caution
    if short == N and long == U:
        return ShortTermMarketCondition.WARNING_NEGATIVE

    # Fallback (should never reach here given the enum only has 3 values)
    return ShortTermMarketCondition.WARNING_NEGATIVE


def get_shortterm_market_condition(
    config: ShortTermMarketTrendConfig = ShortTermMarketTrendConfig(),
    use_cache: bool = True
) -> Tuple[ShortTermMarketCondition, Optional[ShortTermEMAData]]:
    """
    Get current short-term market condition with caching.
    
    Args:
        config: Configuration for short-term market trend analysis
        use_cache: Whether to use cached result if available
        
    Returns:
        Tuple of (ShortTermMarketCondition, ShortTermEMAData or None)
    """
    if not config.enabled:
        logger.info("Short-term market trend analysis disabled in config")
        return ShortTermMarketCondition.UNKNOWN, None
    
    # Check cache first
    if use_cache:
        cached = _get_cached_shortterm_condition()
        if cached is not None:
            return cached
    
    # Calculate fresh data
    ema_data = calculate_shortterm_emas(config)
    
    if ema_data is None:
        logger.warning("Unable to calculate short-term market condition, returning UNKNOWN")
        return ShortTermMarketCondition.UNKNOWN, None
    
    condition = determine_shortterm_market_condition(ema_data)
    
    # Cache the result
    _cache_shortterm_condition(condition, ema_data)
    
    logger.info(f"Short-term market condition determined: {condition.value}")
    return condition, ema_data


# ---------------------------------------------------------------------------
# Tactical Guidance
# ---------------------------------------------------------------------------

def get_tactical_allocation_adjustment(
    condition: ShortTermMarketCondition,
    config: ShortTermMarketTrendConfig = ShortTermMarketTrendConfig()
) -> float:
    """
    Get tactical stock allocation adjustment percentage for the given market condition.
    
    Args:
        condition: Current short-term market condition
        config: Configuration with adjustment percentages
        
    Returns:
        Adjustment percentage (negative = reduce stocks, positive = increase stocks)
    """
    adjustments = {
        ShortTermMarketCondition.BULL: config.bull_adjustment,
        ShortTermMarketCondition.WARNING_NEGATIVE: config.warning_adjustment,
        ShortTermMarketCondition.WARNING_POSITIVE: config.warning_adjustment,
        ShortTermMarketCondition.BEAR: config.bear_adjustment,
        ShortTermMarketCondition.UNKNOWN: 0.0,
    }
    
    adjustment = adjustments.get(condition, 0.0)
    logger.debug(f"Tactical allocation adjustment for {condition.value}: {adjustment:+.1f}%")
    return adjustment


def get_market_momentum_phase(ema_data: ShortTermEMAData) -> str:
    """
    Determine the current market momentum phase based on EMA data.
    
    Args:
        ema_data: EMA data
        
    Returns:
        Market momentum phase description
    """
    if ema_data.short_trend == ShortTermTrendDirection.POSITIVE and ema_data.long_trend == ShortTermTrendDirection.POSITIVE:
        if ema_data.days_in_trend >= 15:
            return "Strong Upward Momentum (Extended)"
        elif ema_data.days_in_trend >= 7:
            return "Sustained Upward Momentum"
        else:
            return "Building Upward Momentum"
    
    elif ema_data.short_trend == ShortTermTrendDirection.NEGATIVE and ema_data.long_trend == ShortTermTrendDirection.POSITIVE:
        return "Weakening Momentum (Caution)"
    
    elif ema_data.short_trend == ShortTermTrendDirection.POSITIVE and ema_data.long_trend == ShortTermTrendDirection.NEGATIVE:
        return "Momentum Reversal Attempt"
    
    elif ema_data.short_trend == ShortTermTrendDirection.NEGATIVE and ema_data.long_trend == ShortTermTrendDirection.NEGATIVE:
        if ema_data.days_in_trend >= 15:
            return "Strong Downward Momentum (Extended)"
        elif ema_data.days_in_trend >= 7:
            return "Sustained Downward Momentum"
        else:
            return "Building Downward Momentum"
    
    else:
        return "Neutral Momentum (Consolidating)"


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def format_shortterm_market_summary(
    condition: ShortTermMarketCondition,
    ema_data: Optional[ShortTermEMAData]
) -> str:
    """
    Format a human-readable summary of short-term market condition.
    
    Args:
        condition: Short-term market condition
        ema_data: EMA data (None if unavailable)
        
    Returns:
        Formatted summary string
    """
    if ema_data is None:
        return f"Short-Term Market Condition: {condition.value.upper()} (data unavailable)"
    
    momentum_phase = get_market_momentum_phase(ema_data)
    
    summary = f"""Short-Term Market Condition: {condition.value.upper()}
Market Momentum Phase: {momentum_phase}

Current SPY Price: ${ema_data.current_price:.2f}
10-Day EMA: ${ema_data.short_ema:.2f} ({ema_data.short_trend.value}, {ema_data.short_slope:+.3f}%/day)
50-Day EMA: ${ema_data.long_ema:.2f} ({ema_data.long_trend.value}, {ema_data.long_slope:+.3f}%/day)

Price vs 10-Day EMA: {ema_data.price_vs_short_ema:+.1f}%
Price vs 50-Day EMA: {ema_data.price_vs_long_ema:+.1f}%
EMA Crossover Distance: {ema_data.ema_crossover_distance:+.1f}%

Trend Duration: {ema_data.days_in_trend} days
Confidence: {ema_data.confidence:.0%}
Updated: {ema_data.calculation_date.strftime('%Y-%m-%d %H:%M')}"""
    
    return summary


def get_tactical_recommendations(
    condition: ShortTermMarketCondition,
    ema_data: Optional[ShortTermEMAData]
) -> list[str]:
    """
    Get tactical recommendations based on short-term market condition.
    
    Args:
        condition: Short-term market condition
        ema_data: EMA data
        
    Returns:
        List of recommendation strings
    """
    if ema_data is None:
        return ["Unable to provide recommendations: market data unavailable"]
    
    recommendations = []
    
    if condition == ShortTermMarketCondition.BULL:
        recommendations.append("✅ Strong short-term momentum - favorable for tactical positions")
        recommendations.append("📊 Consider maintaining or slightly increasing exposure")
        if ema_data.days_in_trend >= 15:
            recommendations.append("⚠️ Extended run - watch for reversal signals")
            recommendations.append("💰 Consider taking profits on short-term trades")
    
    elif condition == ShortTermMarketCondition.WARNING_NEGATIVE:
        recommendations.append("⚠️ Short-term momentum weakening - reduce tactical exposure")
        recommendations.append("🛡️ Consider tightening stop-losses on active positions")
        recommendations.append("💵 Build cash for potential buying opportunities")
        recommendations.append("📋 Review and trim overextended positions")
    
    elif condition == ShortTermMarketCondition.WARNING_POSITIVE:
        recommendations.append("🔄 Short-term bounce attempt - remain cautious")
        recommendations.append("⏳ Wait for 50-day EMA confirmation before adding exposure")
        recommendations.append("📊 Monitor for sustained momentum (3-5 days)")
    
    elif condition == ShortTermMarketCondition.BEAR:
        recommendations.append("🛡️ Defensive posture for short-term positions")
        recommendations.append("💵 Maintain higher cash allocation")
        recommendations.append("📉 Avoid new long positions until trend reverses")
        if ema_data.days_in_trend >= 10:
            recommendations.append("💎 Watch for oversold conditions and reversal signals")
    
    else:
        recommendations.append("❓ Short-term direction unclear - maintain current positions")
    
    return recommendations


# Made with Bob