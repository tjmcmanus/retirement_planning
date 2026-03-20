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
    get_tactical_allocation_adjustment,
    get_market_momentum_phase,
    format_shortterm_market_summary,
    get_tactical_recommendations,
    clear_shortterm_market_condition_cache,
)


def test_shortterm_market_condition_enum():
    """Test that all market condition states are defined."""
    assert ShortTermMarketCondition.BULL.value == "bull"
    assert ShortTermMarketCondition.WARNING_NEGATIVE.value == "warning_negative"
    assert ShortTermMarketCondition.WARNING_POSITIVE.value == "warning_positive"
    assert ShortTermMarketCondition.BEAR.value == "bear"
    assert ShortTermMarketCondition.UNKNOWN.value == "unknown"


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
    assert config.warning_adjustment == -3.0
    assert config.bear_adjustment == -8.0


def test_determine_shortterm_market_condition_bull():
    """Test bull market condition determination."""
    ema_data = ShortTermEMAData(
        short_ema=450.0,
        long_ema=440.0,
        current_price=455.0,
        short_trend=ShortTermTrendDirection.POSITIVE,
        long_trend=ShortTermTrendDirection.POSITIVE,
        short_slope=0.5,
        long_slope=0.3,
        price_vs_short_ema=1.1,
        price_vs_long_ema=3.4,
        ema_crossover_distance=2.3,
        calculation_date=datetime.now(),
        confidence=0.8,
        days_in_trend=10
    )
    
    condition = determine_shortterm_market_condition(ema_data)
    assert condition == ShortTermMarketCondition.BULL


def test_determine_shortterm_market_condition_warning_negative():
    """Test warning negative condition determination."""
    ema_data = ShortTermEMAData(
        short_ema=445.0,
        long_ema=440.0,
        current_price=443.0,
        short_trend=ShortTermTrendDirection.NEGATIVE,
        long_trend=ShortTermTrendDirection.POSITIVE,
        short_slope=-0.3,
        long_slope=0.2,
        price_vs_short_ema=-0.4,
        price_vs_long_ema=0.7,
        ema_crossover_distance=1.1,
        calculation_date=datetime.now(),
        confidence=0.6,
        days_in_trend=3
    )
    
    condition = determine_shortterm_market_condition(ema_data)
    assert condition == ShortTermMarketCondition.WARNING_NEGATIVE


def test_determine_shortterm_market_condition_warning_positive():
    """Test warning positive condition determination."""
    ema_data = ShortTermEMAData(
        short_ema=442.0,
        long_ema=445.0,
        current_price=443.0,
        short_trend=ShortTermTrendDirection.POSITIVE,
        long_trend=ShortTermTrendDirection.NEGATIVE,
        short_slope=0.2,
        long_slope=-0.3,
        price_vs_short_ema=0.2,
        price_vs_long_ema=-0.4,
        ema_crossover_distance=-0.7,
        calculation_date=datetime.now(),
        confidence=0.5,
        days_in_trend=2
    )
    
    condition = determine_shortterm_market_condition(ema_data)
    assert condition == ShortTermMarketCondition.WARNING_POSITIVE


def test_determine_shortterm_market_condition_bear():
    """Test bear market condition determination."""
    ema_data = ShortTermEMAData(
        short_ema=440.0,
        long_ema=445.0,
        current_price=438.0,
        short_trend=ShortTermTrendDirection.NEGATIVE,
        long_trend=ShortTermTrendDirection.NEGATIVE,
        short_slope=-0.5,
        long_slope=-0.3,
        price_vs_short_ema=-0.5,
        price_vs_long_ema=-1.6,
        ema_crossover_distance=-1.1,
        calculation_date=datetime.now(),
        confidence=0.7,
        days_in_trend=8
    )
    
    condition = determine_shortterm_market_condition(ema_data)
    assert condition == ShortTermMarketCondition.BEAR


def test_get_tactical_allocation_adjustment():
    """Test tactical allocation adjustments for each condition."""
    config = ShortTermMarketTrendConfig()
    
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.BULL, config) == 0.0
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.WARNING_NEGATIVE, config) == -3.0
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.WARNING_POSITIVE, config) == -3.0
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.BEAR, config) == -8.0
    assert get_tactical_allocation_adjustment(ShortTermMarketCondition.UNKNOWN, config) == 0.0


def test_get_market_momentum_phase():
    """Test market momentum phase descriptions."""
    # Strong upward momentum (extended)
    ema_data = ShortTermEMAData(
        short_ema=450.0,
        long_ema=440.0,
        current_price=455.0,
        short_trend=ShortTermTrendDirection.POSITIVE,
        long_trend=ShortTermTrendDirection.POSITIVE,
        short_slope=0.5,
        long_slope=0.3,
        price_vs_short_ema=1.1,
        price_vs_long_ema=3.4,
        ema_crossover_distance=2.3,
        calculation_date=datetime.now(),
        confidence=0.8,
        days_in_trend=16
    )
    phase = get_market_momentum_phase(ema_data)
    assert "Extended" in phase
    
    # Sustained upward momentum
    ema_data.days_in_trend = 10
    phase = get_market_momentum_phase(ema_data)
    assert "Sustained" in phase
    
    # Building upward momentum
    ema_data.days_in_trend = 5
    phase = get_market_momentum_phase(ema_data)
    assert "Building" in phase


def test_format_shortterm_market_summary():
    """Test market summary formatting."""
    ema_data = ShortTermEMAData(
        short_ema=450.0,
        long_ema=440.0,
        current_price=455.0,
        short_trend=ShortTermTrendDirection.POSITIVE,
        long_trend=ShortTermTrendDirection.POSITIVE,
        short_slope=0.5,
        long_slope=0.3,
        price_vs_short_ema=1.1,
        price_vs_long_ema=3.4,
        ema_crossover_distance=2.3,
        calculation_date=datetime.now(),
        confidence=0.8,
        days_in_trend=10
    )
    
    summary = format_shortterm_market_summary(ShortTermMarketCondition.BULL, ema_data)
    
    assert "BULL" in summary
    assert "455.00" in summary
    assert "450.00" in summary
    assert "440.00" in summary
    assert "10 days" in summary


def test_format_shortterm_market_summary_no_data():
    """Test market summary formatting with no data."""
    summary = format_shortterm_market_summary(ShortTermMarketCondition.UNKNOWN, None)
    assert "UNKNOWN" in summary
    assert "unavailable" in summary


def test_get_tactical_recommendations():
    """Test tactical recommendations for each condition."""
    ema_data = ShortTermEMAData(
        short_ema=450.0,
        long_ema=440.0,
        current_price=455.0,
        short_trend=ShortTermTrendDirection.POSITIVE,
        long_trend=ShortTermTrendDirection.POSITIVE,
        short_slope=0.5,
        long_slope=0.3,
        price_vs_short_ema=1.1,
        price_vs_long_ema=3.4,
        ema_crossover_distance=2.3,
        calculation_date=datetime.now(),
        confidence=0.8,
        days_in_trend=10
    )
    
    # Bull recommendations
    recommendations = get_tactical_recommendations(ShortTermMarketCondition.BULL, ema_data)
    assert len(recommendations) > 0
    assert any("momentum" in rec.lower() for rec in recommendations)
    
    # Warning negative recommendations
    recommendations = get_tactical_recommendations(ShortTermMarketCondition.WARNING_NEGATIVE, ema_data)
    assert len(recommendations) > 0
    assert any("reduce" in rec.lower() or "stop" in rec.lower() for rec in recommendations)
    
    # Warning positive recommendations
    recommendations = get_tactical_recommendations(ShortTermMarketCondition.WARNING_POSITIVE, ema_data)
    assert len(recommendations) > 0
    assert any("wait" in rec.lower() or "cautious" in rec.lower() for rec in recommendations)
    
    # Bear recommendations
    recommendations = get_tactical_recommendations(ShortTermMarketCondition.BEAR, ema_data)
    assert len(recommendations) > 0
    assert any("defensive" in rec.lower() or "avoid" in rec.lower() for rec in recommendations)


def test_get_tactical_recommendations_no_data():
    """Test tactical recommendations with no data."""
    recommendations = get_tactical_recommendations(ShortTermMarketCondition.UNKNOWN, None)
    assert len(recommendations) == 1
    assert "unavailable" in recommendations[0]


def test_cache_clearing():
    """Test cache clearing functionality."""
    # This should not raise an error
    clear_shortterm_market_condition_cache()


def test_get_shortterm_market_condition_disabled():
    """Test that disabled config returns UNKNOWN."""
    config = ShortTermMarketTrendConfig(enabled=False)
    condition, ema_data = get_shortterm_market_condition(config, use_cache=False)
    
    assert condition == ShortTermMarketCondition.UNKNOWN
    assert ema_data is None


def test_get_shortterm_market_condition_live():
    """Test live market condition fetching (integration test)."""
    # Clear cache to force fresh fetch
    clear_shortterm_market_condition_cache()
    
    config = ShortTermMarketTrendConfig()
    condition, ema_data = get_shortterm_market_condition(config, use_cache=False)
    
    # Should get a valid condition (or UNKNOWN if market data unavailable)
    assert condition in [
        ShortTermMarketCondition.BULL,
        ShortTermMarketCondition.WARNING_NEGATIVE,
        ShortTermMarketCondition.WARNING_POSITIVE,
        ShortTermMarketCondition.BEAR,
        ShortTermMarketCondition.UNKNOWN
    ]
    
    # If condition is not UNKNOWN, should have EMA data
    if condition != ShortTermMarketCondition.UNKNOWN:
        assert ema_data is not None
        assert ema_data.current_price > 0
        assert ema_data.short_ema > 0
        assert ema_data.long_ema > 0
        assert 0.0 <= ema_data.confidence <= 1.0
        assert ema_data.days_in_trend >= 0


def test_get_shortterm_market_condition_caching():
    """Test that caching works correctly."""
    # Clear cache first
    clear_shortterm_market_condition_cache()
    
    config = ShortTermMarketTrendConfig()
    
    # First call - should fetch fresh data
    condition1, ema_data1 = get_shortterm_market_condition(config, use_cache=True)
    
    # Second call - should use cache
    condition2, ema_data2 = get_shortterm_market_condition(config, use_cache=True)
    
    # Should get same results
    assert condition1 == condition2
    if ema_data1 is not None and ema_data2 is not None:
        assert ema_data1.current_price == ema_data2.current_price
        assert ema_data1.calculation_date == ema_data2.calculation_date


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
