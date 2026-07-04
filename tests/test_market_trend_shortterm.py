"""
Test suite for short-term market trend analysis module.
"""
import pytest
from datetime import datetime
from market_trend_shortterm import (
    ShortTermMarketCondition,
    ShortTermTrendDirection,
    ShortTermEMAData,
    ShortTermMarketTrendConfig,
    get_shortterm_market_condition,
    determine_shortterm_market_condition,
    get_market_subphase,
    get_tactical_allocation_adjustment,
    get_market_momentum_phase,
    format_shortterm_market_summary,
    get_tactical_recommendations,
    clear_shortterm_market_condition_cache,
)


def _make_ema_data(short_trend, long_trend, days_in_trend=5):
    """Helper: build a ShortTermEMAData with the given trend directions."""
    return ShortTermEMAData(
        short_ema=450.0,
        long_ema=440.0,
        current_price=455.0,
        short_trend=short_trend,
        long_trend=long_trend,
        short_slope=0.5 if short_trend == ShortTermTrendDirection.POSITIVE else (
            -0.5 if short_trend == ShortTermTrendDirection.NEGATIVE else 0.0),
        long_slope=0.3 if long_trend == ShortTermTrendDirection.POSITIVE else (
            -0.3 if long_trend == ShortTermTrendDirection.NEGATIVE else 0.0),
        price_vs_short_ema=1.1,
        price_vs_long_ema=3.4,
        ema_crossover_distance=2.3,
        calculation_date=datetime.now(),
        confidence=0.8,
        days_in_trend=days_in_trend,
    )


def test_shortterm_market_condition_enum():
    """Test that all market condition states are defined."""
    assert ShortTermMarketCondition.BULL.value == "bull"
    assert ShortTermMarketCondition.NEUTRAL.value == "neutral"
    assert ShortTermMarketCondition.BEAR.value == "bear"
    assert ShortTermMarketCondition.UNKNOWN.value == "unknown"
    # WARNING states removed — ensure they no longer exist
    assert not hasattr(ShortTermMarketCondition, "WARNING_NEGATIVE")
    assert not hasattr(ShortTermMarketCondition, "WARNING_POSITIVE")


def test_shortterm_trend_direction_enum():
    """Test that all trend directions are defined."""
    assert ShortTermTrendDirection.POSITIVE.value == "positive"
    assert ShortTermTrendDirection.NEGATIVE.value == "negative"
    assert ShortTermTrendDirection.NEUTRAL.value == "neutral"


def test_shortterm_config_defaults():
    """Test default configuration values."""
    config = ShortTermMarketTrendConfig()
    assert config.short_ema_days == 10
    assert config.long_ema_days == 50
    assert config.cache_ttl_minutes == 30
    assert config.enabled is True
    assert config.bull_adjustment == 0.0
    assert config.neutral_adjustment == 0.0
    assert config.bear_adjustment == -8.0
    # warning_adjustment removed
    assert not hasattr(config, "warning_adjustment")


# ---------------------------------------------------------------------------
# determine_shortterm_market_condition — long EMA drives regime
# ---------------------------------------------------------------------------

def test_condition_long_positive_is_bull():
    """Long EMA positive → BULL regardless of short EMA."""
    P = ShortTermTrendDirection.POSITIVE
    N = ShortTermTrendDirection.NEGATIVE
    U = ShortTermTrendDirection.NEUTRAL
    for short in (P, N, U):
        ema = _make_ema_data(short, P)
        assert determine_shortterm_market_condition(ema) == ShortTermMarketCondition.BULL, \
            f"Expected BULL when long=POSITIVE, short={short.value}"


def test_condition_long_negative_is_bear():
    """Long EMA negative → BEAR regardless of short EMA."""
    P = ShortTermTrendDirection.POSITIVE
    N = ShortTermTrendDirection.NEGATIVE
    U = ShortTermTrendDirection.NEUTRAL
    for short in (P, N, U):
        ema = _make_ema_data(short, N)
        assert determine_shortterm_market_condition(ema) == ShortTermMarketCondition.BEAR, \
            f"Expected BEAR when long=NEGATIVE, short={short.value}"


def test_condition_long_neutral_is_neutral():
    """Long EMA neutral → NEUTRAL regardless of short EMA."""
    P = ShortTermTrendDirection.POSITIVE
    N = ShortTermTrendDirection.NEGATIVE
    U = ShortTermTrendDirection.NEUTRAL
    for short in (P, N, U):
        ema = _make_ema_data(short, U)
        assert determine_shortterm_market_condition(ema) == ShortTermMarketCondition.NEUTRAL, \
            f"Expected NEUTRAL when long=NEUTRAL, short={short.value}"


# ---------------------------------------------------------------------------
# get_market_subphase — short EMA drives sub-phase
# ---------------------------------------------------------------------------

def test_subphase_short_positive_is_accumulation():
    ema = _make_ema_data(ShortTermTrendDirection.POSITIVE, ShortTermTrendDirection.POSITIVE)
    assert get_market_subphase(ema) == "Accumulation"


def test_subphase_short_neutral_is_consolidating():
    ema = _make_ema_data(ShortTermTrendDirection.NEUTRAL, ShortTermTrendDirection.POSITIVE)
    assert get_market_subphase(ema) == "Consolidating"


def test_subphase_short_negative_is_distribution():
    ema = _make_ema_data(ShortTermTrendDirection.NEGATIVE, ShortTermTrendDirection.POSITIVE)
    assert get_market_subphase(ema) == "Distribution"


# ---------------------------------------------------------------------------
# get_market_momentum_phase — combined label
# ---------------------------------------------------------------------------

def test_momentum_phase_label():
    """get_market_momentum_phase returns 'Condition (Subphase)' format."""
    ema = _make_ema_data(ShortTermTrendDirection.POSITIVE, ShortTermTrendDirection.POSITIVE)
    phase = get_market_momentum_phase(ema)
    assert phase == "Bull (Accumulation)"

    ema2 = _make_ema_data(ShortTermTrendDirection.NEUTRAL, ShortTermTrendDirection.NEUTRAL)
    phase2 = get_market_momentum_phase(ema2)
    assert phase2 == "Neutral (Consolidating)"

    ema3 = _make_ema_data(ShortTermTrendDirection.NEGATIVE, ShortTermTrendDirection.NEGATIVE)
    phase3 = get_market_momentum_phase(ema3)
    assert phase3 == "Bear (Distribution)"


# ---------------------------------------------------------------------------
# get_tactical_allocation_adjustment
# ---------------------------------------------------------------------------

def test_get_tactical_allocation_adjustment():
    """Test tactical allocation adjustments for each condition."""
    config = ShortTermMarketTrendConfig()
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.BULL, config) == 0.0
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.NEUTRAL, config) == 0.0
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.BEAR, config) == -8.0
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.UNKNOWN, config) == 0.0


# ---------------------------------------------------------------------------
# format_shortterm_market_summary
# ---------------------------------------------------------------------------

def test_format_shortterm_market_summary():
    """Test market summary formatting includes condition + subphase."""
    ema_data = _make_ema_data(ShortTermTrendDirection.POSITIVE, ShortTermTrendDirection.POSITIVE)
    summary = format_shortterm_market_summary(ShortTermMarketCondition.BULL, ema_data)
    assert "BULL" in summary
    assert "Accumulation" in summary
    assert "455.00" in summary
    assert "450.00" in summary
    assert "440.00" in summary


def test_format_shortterm_market_summary_no_data():
    """Test market summary formatting with no data."""
    summary = format_shortterm_market_summary(ShortTermMarketCondition.UNKNOWN, None)
    assert "UNKNOWN" in summary
    assert "unavailable" in summary


# ---------------------------------------------------------------------------
# get_tactical_recommendations
# ---------------------------------------------------------------------------

def test_get_tactical_recommendations_bull_accumulation():
    ema = _make_ema_data(ShortTermTrendDirection.POSITIVE, ShortTermTrendDirection.POSITIVE)
    recs = get_tactical_recommendations(ShortTermMarketCondition.BULL, ema)
    assert len(recs) > 0
    combined = " ".join(recs).lower()
    assert "accumulation" in combined

def test_get_tactical_recommendations_bull_consolidating():
    ema = _make_ema_data(ShortTermTrendDirection.NEUTRAL, ShortTermTrendDirection.POSITIVE)
    recs = get_tactical_recommendations(ShortTermMarketCondition.BULL, ema)
    combined = " ".join(recs).lower()
    assert "consolidating" in combined

def test_get_tactical_recommendations_bull_distribution():
    ema = _make_ema_data(ShortTermTrendDirection.NEGATIVE, ShortTermTrendDirection.POSITIVE)
    recs = get_tactical_recommendations(ShortTermMarketCondition.BULL, ema)
    combined = " ".join(recs).lower()
    assert "distribution" in combined

def test_get_tactical_recommendations_neutral():
    ema = _make_ema_data(ShortTermTrendDirection.NEUTRAL, ShortTermTrendDirection.NEUTRAL)
    recs = get_tactical_recommendations(ShortTermMarketCondition.NEUTRAL, ema)
    assert len(recs) > 0
    combined = " ".join(recs).lower()
    assert "consolidating" in combined

def test_get_tactical_recommendations_bear_distribution():
    ema = _make_ema_data(ShortTermTrendDirection.NEGATIVE, ShortTermTrendDirection.NEGATIVE)
    recs = get_tactical_recommendations(ShortTermMarketCondition.BEAR, ema)
    assert len(recs) > 0
    combined = " ".join(recs).lower()
    assert "distribution" in combined

def test_get_tactical_recommendations_bear_accumulation():
    ema = _make_ema_data(ShortTermTrendDirection.POSITIVE, ShortTermTrendDirection.NEGATIVE)
    recs = get_tactical_recommendations(ShortTermMarketCondition.BEAR, ema)
    combined = " ".join(recs).lower()
    assert "accumulation" in combined

def test_get_tactical_recommendations_no_data():
    """Test tactical recommendations with no data."""
    recommendations = get_tactical_recommendations(ShortTermMarketCondition.UNKNOWN, None)
    assert len(recommendations) == 1
    assert "unavailable" in recommendations[0]


# ---------------------------------------------------------------------------
# Cache and integration
# ---------------------------------------------------------------------------

def test_cache_clearing():
    """Test cache clearing functionality."""
    clear_shortterm_market_condition_cache()


def test_get_shortterm_market_condition_disabled():
    """Test that disabled config returns UNKNOWN."""
    config = ShortTermMarketTrendConfig(enabled=False)
    condition, ema_data = get_shortterm_market_condition(config, use_cache=False)
    assert condition == ShortTermMarketCondition.UNKNOWN
    assert ema_data is None


def test_get_shortterm_market_condition_live():
    """Test live market condition fetching (integration test)."""
    clear_shortterm_market_condition_cache()
    config = ShortTermMarketTrendConfig()
    condition, ema_data = get_shortterm_market_condition(config, use_cache=False)

    assert condition in [
        ShortTermMarketCondition.BULL,
        ShortTermMarketCondition.NEUTRAL,
        ShortTermMarketCondition.BEAR,
        ShortTermMarketCondition.UNKNOWN,
    ]

    if condition != ShortTermMarketCondition.UNKNOWN:
        assert ema_data is not None
        assert ema_data.current_price > 0
        assert ema_data.short_ema > 0
        assert ema_data.long_ema > 0
        assert 0.0 <= ema_data.confidence <= 1.0
        assert ema_data.days_in_trend >= 0
        # Subphase should be one of the three valid values
        assert get_market_subphase(ema_data) in ("Accumulation", "Consolidating", "Distribution")


def test_get_shortterm_market_condition_caching():
    """Test that caching works correctly."""
    clear_shortterm_market_condition_cache()
    config = ShortTermMarketTrendConfig()

    condition1, ema_data1 = get_shortterm_market_condition(config, use_cache=True)
    condition2, ema_data2 = get_shortterm_market_condition(config, use_cache=True)

    assert condition1 == condition2
    if ema_data1 is not None and ema_data2 is not None:
        assert ema_data1.current_price == ema_data2.current_price
        assert ema_data1.calculation_date == ema_data2.calculation_date


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
