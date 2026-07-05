"""
Long-Term Market Trend Analysis Module
=======================================
Analyzes long-term market conditions using SPY (S&P 500 ETF) exponential moving
averages to inform strategic portfolio decisions.

This module implements a 4-state market condition system based on 8-month and
18-month exponential moving averages (EMAs):
- Bull Case: Both EMAs trending positive
- Warning Negative: 8-month EMA negative, 18-month EMA positive
- Warning Positive: 8-month EMA positive, 18-month EMA negative
- Bear Case: Both EMAs trending negative

The long-term market condition provides strategic guidance for:
- Major portfolio rebalancing decisions
- Risk tolerance adjustments
- Long-term allocation shifts
- Retirement timing considerations

This complements the short-term 10/50-week analysis by providing a broader
perspective on market cycles and secular trends.
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
DEFAULT_SHORT_EMA_MONTHS = 8
DEFAULT_LONG_EMA_MONTHS = 18
CACHE_TTL_HOURS = 4  # Cache for 4 hours (longer than short-term)
MIN_STATE_DURATION_WEEKS = 2  # Minimum weeks in state before transition

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LongTermMarketCondition(Enum):
    """Long-term market condition states. Driven solely by the long (18-month) EMA."""
    BULL = "bull"       # 18-month EMA positive — long trend intact
    NEUTRAL = "neutral" # 18-month EMA flat — no clear direction
    BEAR = "bear"       # 18-month EMA negative — sustained downtrend
    UNKNOWN = "unknown" # Unable to determine (data issues)


class LongTermTrendDirection(Enum):
    """Direction of EMA trend."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class LongTermEMAData:
    """Exponential moving average calculation results."""
    short_ema: float  # 8-month EMA value
    long_ema: float  # 18-month EMA value
    current_price: float  # Current SPY price
    short_trend: LongTermTrendDirection  # 8-month EMA trend
    long_trend: LongTermTrendDirection  # 18-month EMA trend
    short_slope: float  # Rate of change of short EMA (% per month)
    long_slope: float  # Rate of change of long EMA (% per month)
    price_vs_short_ema: float  # Price relative to short EMA (%)
    price_vs_long_ema: float  # Price relative to long EMA (%)
    ema_crossover_distance: float  # Distance between EMAs (%)
    calculation_date: datetime  # When this was calculated
    confidence: float  # Confidence score 0.0-1.0 based on slope magnitudes
    months_in_trend: int  # Estimated months in current trend


@dataclass
class LongTermMarketTrendConfig:
    """Configuration for long-term market trend analysis."""
    short_ema_months: int = DEFAULT_SHORT_EMA_MONTHS
    long_ema_months: int = DEFAULT_LONG_EMA_MONTHS
    cache_ttl_hours: int = CACHE_TTL_HOURS
    min_state_duration_weeks: int = MIN_STATE_DURATION_WEEKS
    enabled: bool = True
    # Strategic allocation adjustment percentages for each market state
    bull_adjustment: float = 0.0    # No adjustment in bull market
    neutral_adjustment: float = 0.0  # No adjustment when consolidating
    bear_adjustment: float = -15.0  # Reduce stocks by 15% in bear market


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

_longterm_condition_cache: Optional[Tuple[LongTermMarketCondition, LongTermEMAData, datetime]] = None
_last_fetch_error_longterm: Optional[str] = None


def get_last_fetch_error_longterm() -> Optional[str]:
    """Return the most recent long-term market-data failure reason, or None on success."""
    return _last_fetch_error_longterm


def _get_cached_longterm_condition() -> Optional[Tuple[LongTermMarketCondition, LongTermEMAData]]:
    """
    Get cached long-term market condition if still valid.
    
    Returns:
        Tuple of (LongTermMarketCondition, LongTermEMAData) if cache valid, None otherwise
    """
    global _longterm_condition_cache
    if _longterm_condition_cache is None:
        return None
    
    condition, ema_data, cache_time = _longterm_condition_cache
    cache_age = datetime.now() - cache_time
    
    if cache_age.total_seconds() / 3600 < CACHE_TTL_HOURS:
        logger.debug(f"Using cached long-term market condition: {condition.value} (age: {cache_age})")
        return condition, ema_data
    
    logger.debug(f"Long-term cache expired (age: {cache_age}), will fetch new data")
    return None


def _cache_longterm_condition(condition: LongTermMarketCondition, ema_data: LongTermEMAData) -> None:
    """
    Cache long-term market condition with timestamp.
    
    Args:
        condition: Market condition to cache
        ema_data: EMA data to cache
    """
    global _longterm_condition_cache
    _longterm_condition_cache = (condition, ema_data, datetime.now())
    logger.debug(f"Cached long-term market condition: {condition.value}")


def clear_longterm_market_condition_cache() -> None:
    """Clear the long-term market condition cache."""
    global _longterm_condition_cache
    _longterm_condition_cache = None
    logger.info("Long-term market condition cache cleared")


# ---------------------------------------------------------------------------
# Data Fetching
# ---------------------------------------------------------------------------

def fetch_spy_longterm_data(months: int) -> Optional[pd.DataFrame]:
    """
    Fetch SPY historical data for the specified number of months.
    
    Args:
        months: Number of months of historical data to fetch
        
    Returns:
        DataFrame with SPY price data, or None if fetch fails
    """
    global _last_fetch_error_longterm
    try:
        # Add 25% buffer to ensure we have enough data for EMA calculation
        days = int(months * 30 * 1.25)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.debug(f"Fetching SPY long-term data from {start_date.date()} to {end_date.date()}")
        
        spy = yf.Ticker(SPY_SYMBOL)
        df = spy.history(start=start_date, end=end_date)
        
        if df.empty:
            _last_fetch_error_longterm = "No SPY price data returned from market data provider"
            logger.error(_last_fetch_error_longterm)
            return None
        
        logger.debug(f"Fetched {len(df)} days of SPY data for long-term analysis")
        return df
        
    except Exception as e:
        _last_fetch_error_longterm = f"Long-term market data fetch failed: {e}"
        logger.error(_last_fetch_error_longterm, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# EMA Calculations
# ---------------------------------------------------------------------------

def calculate_longterm_emas(
    config: LongTermMarketTrendConfig = LongTermMarketTrendConfig()
) -> Optional[LongTermEMAData]:
    """
    Calculate exponential moving averages and trends for SPY.
    
    Args:
        config: Configuration for EMA calculation
        
    Returns:
        LongTermEMAData with calculation results, or None if calculation fails
    """
    # Fetch data for the longer EMA period
    max_months = max(config.short_ema_months, config.long_ema_months)
    df = fetch_spy_longterm_data(max_months)
    
    if df is None or df.empty:
        logger.error("Cannot calculate long-term EMAs: no data available")
        return None
    
    try:
        # Use daily close prices for more accurate EMA calculation
        prices = df['Close'].dropna()
        
        if len(prices) < config.long_ema_months * 20:  # ~20 trading days per month
            logger.error(f"Insufficient data: need ~{config.long_ema_months * 20} days, have {len(prices)}")
            return None
        
        # Calculate EMAs using pandas ewm (exponential weighted moving average)
        # span parameter: for N-month EMA, use span = N * 21 (approximate trading days)
        short_span = config.short_ema_months * 21
        long_span = config.long_ema_months * 21
        
        short_ema_series = prices.ewm(span=short_span, adjust=False).mean()
        long_ema_series = prices.ewm(span=long_span, adjust=False).mean()
        
        short_ema = short_ema_series.iloc[-1]
        long_ema = long_ema_series.iloc[-1]
        current_price = prices.iloc[-1]
        
        # Calculate slopes (rate of change as % per month)
        # Compare current EMA to EMA from 2 months ago (~42 trading days)
        lookback_days = 42
        if len(prices) >= lookback_days + 1:
            short_ema_prev = short_ema_series.iloc[-(lookback_days+1)]
            short_slope = (((short_ema - short_ema_prev) / short_ema_prev) * 100 / 2
                           if short_ema_prev != 0 else 0.0)  # per month

            long_ema_prev = long_ema_series.iloc[-(lookback_days+1)]
            long_slope = (((long_ema - long_ema_prev) / long_ema_prev) * 100 / 2
                          if long_ema_prev != 0 else 0.0)  # per month
        else:
            short_slope = 0.0
            long_slope = 0.0
        
        # Determine trend directions
        # Use a threshold to avoid noise (0.25% per month for long-term trends)
        slope_threshold = 0.25
        short_trend = (
            LongTermTrendDirection.POSITIVE if short_slope > slope_threshold
            else LongTermTrendDirection.NEGATIVE if short_slope < -slope_threshold
            else LongTermTrendDirection.NEUTRAL
        )
        long_trend = (
            LongTermTrendDirection.POSITIVE if long_slope > slope_threshold
            else LongTermTrendDirection.NEGATIVE if long_slope < -slope_threshold
            else LongTermTrendDirection.NEUTRAL
        )
        
        # Calculate price relative to EMAs
        price_vs_short_ema = ((current_price - short_ema) / short_ema) * 100 if short_ema != 0 else 0.0
        price_vs_long_ema  = ((current_price - long_ema)  / long_ema)  * 100 if long_ema  != 0 else 0.0
        
        # Calculate EMA crossover distance
        ema_crossover_distance = ((short_ema - long_ema) / long_ema) * 100 if long_ema != 0 else 0.0
        
        # Calculate confidence score based on slope magnitudes
        # Higher slopes = higher confidence
        # Scale: 0.0 (flat) to 1.0 (strong trend)
        max_slope = 3.0  # 3% per month is considered very strong for long-term
        confidence = min(1.0, (abs(short_slope) + abs(long_slope)) / (2 * max_slope))
        
        # Estimate months in current trend (simplified)
        # Count consecutive periods where trend direction matches current
        months_in_trend = 1
        for i in range(2, min(13, len(short_ema_series))):  # Look back up to 12 months
            prev_ema = short_ema_series.iloc[-(i * 21)]  # ~1 month back
            prev_prev_ema = short_ema_series.iloc[-((i+1) * 21)]
            if prev_prev_ema == 0:
                break
            prev_slope = ((prev_ema - prev_prev_ema) / prev_prev_ema) * 100
            
            if short_trend == LongTermTrendDirection.POSITIVE and prev_slope > slope_threshold:
                months_in_trend += 1
            elif short_trend == LongTermTrendDirection.NEGATIVE and prev_slope < -slope_threshold:
                months_in_trend += 1
            else:
                break
        
        ema_data = LongTermEMAData(
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
            months_in_trend=months_in_trend
        )
        
        logger.info(
            f"Long-term EMA calculated: Short={short_ema:.2f} ({short_trend.value}, {short_slope:+.3f}%/mo), "
            f"Long={long_ema:.2f} ({long_trend.value}, {long_slope:+.3f}%/mo), "
            f"Price={current_price:.2f}, Confidence={confidence:.2f}, "
            f"Months in trend={months_in_trend}"
        )
        
        return ema_data
        
    except Exception as e:
        _last_fetch_error_longterm = f"Long-term EMA calculation failed: {e}"
        logger.error(_last_fetch_error_longterm, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Market Condition Determination
# ---------------------------------------------------------------------------

def get_market_subphase(ema_data: LongTermEMAData) -> str:
    """
    Return the market sub-phase label driven by the short (8-month) EMA direction.

    Accumulation  — short EMA rising  (buyers stepping in)
    Consolidating — short EMA flat    (no directional pressure)
    Distribution  — short EMA falling (sellers taking over)
    """
    if ema_data.short_trend == LongTermTrendDirection.POSITIVE:
        return "Accumulation"
    elif ema_data.short_trend == LongTermTrendDirection.NEGATIVE:
        return "Distribution"
    else:
        return "Consolidating"


def determine_longterm_market_condition(ema_data: LongTermEMAData) -> LongTermMarketCondition:
    """
    Determine long-term market condition based on EMA trends.

    The long (18-month) EMA sets the regime; the short (8-month) EMA determines
    the sub-phase (see get_market_subphase).

    Decision matrix:
      Long EMA    Result
      POSITIVE    BULL
      NEUTRAL     NEUTRAL
      NEGATIVE    BEAR

    Args:
        ema_data: EMA data

    Returns:
        LongTermMarketCondition enum value
    """
    if ema_data.long_trend == LongTermTrendDirection.POSITIVE:
        return LongTermMarketCondition.BULL
    elif ema_data.long_trend == LongTermTrendDirection.NEGATIVE:
        return LongTermMarketCondition.BEAR
    else:
        return LongTermMarketCondition.NEUTRAL


def get_longterm_market_condition(
    config: LongTermMarketTrendConfig = LongTermMarketTrendConfig(),
    use_cache: bool = True
) -> Tuple[LongTermMarketCondition, Optional[LongTermEMAData]]:
    """
    Get current long-term market condition with caching.
    
    Args:
        config: Configuration for long-term market trend analysis
        use_cache: Whether to use cached result if available
        
    Returns:
        Tuple of (LongTermMarketCondition, LongTermEMAData or None)
    """
    global _last_fetch_error_longterm

    if not config.enabled:
        logger.info("Long-term market trend analysis disabled in config")
        return LongTermMarketCondition.UNKNOWN, None
    
    # Check cache first
    if use_cache:
        cached = _get_cached_longterm_condition()
        if cached is not None:
            return cached
    
    # Calculate fresh data
    ema_data = calculate_longterm_emas(config)
    
    if ema_data is None:
        reason = _last_fetch_error_longterm or "Unknown error fetching long-term market data"
        logger.warning("Unable to calculate long-term market condition, returning UNKNOWN. Reason: %s", reason)
        return LongTermMarketCondition.UNKNOWN, None

    _last_fetch_error_longterm = None

    condition = determine_longterm_market_condition(ema_data)
    
    # Cache the result
    _cache_longterm_condition(condition, ema_data)
    
    logger.info(f"Long-term market condition determined: {condition.value}")
    return condition, ema_data


# ---------------------------------------------------------------------------
# Strategic Guidance
# ---------------------------------------------------------------------------

def get_strategic_allocation_adjustment(
    condition: LongTermMarketCondition,
    config: LongTermMarketTrendConfig = LongTermMarketTrendConfig()
) -> float:
    """
    Get strategic stock allocation adjustment percentage for the given market condition.
    
    Args:
        condition: Current long-term market condition
        config: Configuration with adjustment percentages
        
    Returns:
        Adjustment percentage (negative = reduce stocks, positive = increase stocks)
    """
    adjustments = {
        LongTermMarketCondition.BULL: config.bull_adjustment,
        LongTermMarketCondition.NEUTRAL: config.neutral_adjustment,
        LongTermMarketCondition.BEAR: config.bear_adjustment,
        LongTermMarketCondition.UNKNOWN: 0.0,
    }
    
    adjustment = adjustments.get(condition, 0.0)
    logger.debug(f"Strategic allocation adjustment for {condition.value}: {adjustment:+.1f}%")
    return adjustment


def get_market_cycle_phase(ema_data: LongTermEMAData) -> str:
    """
    Return a combined condition + sub-phase label, e.g. 'Bull (Accumulation)'.

    This is a convenience wrapper used by the dashboard Market Cycle Phase metric.
    """
    condition = determine_longterm_market_condition(ema_data)
    subphase  = get_market_subphase(ema_data)
    return f"{condition.value.title()} ({subphase})"


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def format_longterm_market_summary(
    condition: LongTermMarketCondition,
    ema_data: Optional[LongTermEMAData]
) -> str:
    """
    Format a human-readable summary of long-term market condition.
    
    Args:
        condition: Long-term market condition
        ema_data: EMA data (None if unavailable)
        
    Returns:
        Formatted summary string
    """
    if ema_data is None:
        return f"Long-Term Market Condition: {condition.value.upper()} (data unavailable)"

    subphase = get_market_subphase(ema_data)

    summary = f"""Long-Term Market Condition: {condition.value.upper()} ({subphase})

Current SPY Price: ${ema_data.current_price:.2f}
8-Month EMA: ${ema_data.short_ema:.2f} ({ema_data.short_trend.value}, {ema_data.short_slope:+.2f}%/month)
18-Month EMA: ${ema_data.long_ema:.2f} ({ema_data.long_trend.value}, {ema_data.long_slope:+.2f}%/month)

Price vs 8-Month EMA: {ema_data.price_vs_short_ema:+.1f}%
Price vs 18-Month EMA: {ema_data.price_vs_long_ema:+.1f}%
EMA Crossover Distance: {ema_data.ema_crossover_distance:+.1f}%

Trend Duration: {ema_data.months_in_trend} months
Confidence: {ema_data.confidence:.0%}
Updated: {ema_data.calculation_date.strftime('%Y-%m-%d %H:%M')}"""
    
    return summary


def get_strategic_recommendations(
    condition: LongTermMarketCondition,
    ema_data: Optional[LongTermEMAData]
) -> list[str]:
    """
    Get strategic recommendations based on long-term market condition.
    
    Args:
        condition: Long-term market condition
        ema_data: EMA data
        
    Returns:
        List of recommendation strings
    """
    if ema_data is None:
        return ["Unable to provide recommendations: market data unavailable"]
    
    recommendations = []
    
    subphase = get_market_subphase(ema_data)

    if condition == LongTermMarketCondition.BULL:
        if subphase == "Accumulation":
            recommendations.append("✅ Bull (Accumulation): 18-month trend up, 8-month momentum rising — favorable environment for full equity exposure")
            recommendations.append("📈 Consider maintaining or adding to target stock allocation")
        elif subphase == "Consolidating":
            recommendations.append("✅ Bull (Consolidating): 18-month trend up, 8-month momentum flat — healthy pause in long-term uptrend")
            recommendations.append("📊 Hold current allocation; avoid major changes until momentum resumes")
        else:  # Distribution
            recommendations.append("⚠️ Bull (Distribution): 18-month trend up but 8-month momentum fading — monitor for regime change")
            recommendations.append("🛡️ Review overweight positions; avoid increasing equity exposure until momentum stabilises")

    elif condition == LongTermMarketCondition.NEUTRAL:
        if subphase == "Accumulation":
            recommendations.append("⚪ Neutral (Accumulation): 18-month EMA flat, 8-month momentum rising — possible early new bull forming")
            recommendations.append("⏳ Monitor closely; wait for 18-month EMA to turn positive before increasing allocation")
        elif subphase == "Consolidating":
            recommendations.append("⚪ Neutral (Consolidating): Both EMAs flat — long-term market in sideways consolidation")
            recommendations.append("📊 Maintain current allocation; avoid major strategic shifts until a trend establishes")
        else:  # Distribution
            recommendations.append("⚪ Neutral (Distribution): 18-month EMA flat, 8-month momentum falling — risk of bear transition")
            recommendations.append("🛡️ Consider reducing equity exposure; build cash reserves as a precaution")

    elif condition == LongTermMarketCondition.BEAR:
        if subphase == "Accumulation":
            recommendations.append("🔄 Bear (Accumulation): 18-month trend down but 8-month bouncing — possible recovery attempt, not confirmed")
            recommendations.append("⏳ Wait for 18-month EMA to turn positive before increasing exposure")
        elif subphase == "Consolidating":
            recommendations.append("🛡️ Bear (Consolidating): 18-month trend down, 8-month flat — downtrend pausing, not reversing")
            recommendations.append("💵 Maintain defensive posture and higher cash allocation")
        else:  # Distribution
            recommendations.append("🛡️ Bear (Distribution): Both EMAs falling — sustained long-term downtrend in force")
            recommendations.append("📉 Defensive posture; consider reducing equity exposure by 10-20%")
            if ema_data.months_in_trend >= 6:
                recommendations.append("💎 Prepare for potential long-term buying opportunities at value prices")

    else:
        recommendations.append("❓ Market direction unclear - maintain current allocation")
    
    return recommendations


# Made with Bob