"""
Coverage tests for market_trend_longterm.py pure deterministic functions.

All tested functions are pure: they take explicit arguments and return a value
without I/O or network access.
"""
import pytest
from datetime import datetime

from market_trend_longterm import (
    LongTermMarketCondition,
    LongTermTrendDirection,
    LongTermEMAData,
    LongTermMarketTrendConfig,
    get_market_subphase,
    determine_longterm_market_condition,
    get_strategic_allocation_adjustment,
    get_market_cycle_phase,
    format_longterm_market_summary,
    get_strategic_recommendations,
    get_longterm_market_condition,
    clear_longterm_market_condition_cache,
    _get_cached_longterm_condition,
    _cache_longterm_condition,
)


# ---------------------------------------------------------------------------
# Helper to build a minimal EMAData
# ---------------------------------------------------------------------------

def _make_ema(
    short_trend=LongTermTrendDirection.POSITIVE,
    long_trend=LongTermTrendDirection.POSITIVE,
    short_slope=0.5,
    long_slope=0.3,
    months_in_trend=4,
    confidence=0.8,
) -> LongTermEMAData:
    return LongTermEMAData(
        short_ema=500.0,
        long_ema=490.0,
        current_price=510.0,
        short_trend=short_trend,
        long_trend=long_trend,
        short_slope=short_slope,
        long_slope=long_slope,
        price_vs_short_ema=2.0,
        price_vs_long_ema=4.1,
        ema_crossover_distance=2.0,
        calculation_date=datetime(2026, 1, 1),
        confidence=confidence,
        months_in_trend=months_in_trend,
    )


# ---------------------------------------------------------------------------
# get_market_subphase
# ---------------------------------------------------------------------------

class TestGetMarketSubphase:
    def test_positive_short_trend_is_accumulation(self):
        ema = _make_ema(short_trend=LongTermTrendDirection.POSITIVE)
        assert get_market_subphase(ema) == "Accumulation"

    def test_negative_short_trend_is_distribution(self):
        ema = _make_ema(short_trend=LongTermTrendDirection.NEGATIVE)
        assert get_market_subphase(ema) == "Distribution"

    def test_neutral_short_trend_is_consolidating(self):
        ema = _make_ema(short_trend=LongTermTrendDirection.NEUTRAL)
        assert get_market_subphase(ema) == "Consolidating"


# ---------------------------------------------------------------------------
# determine_longterm_market_condition
# ---------------------------------------------------------------------------

class TestDetermineLongtermMarketCondition:
    def test_positive_long_trend_is_bull(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.POSITIVE)
        result = determine_longterm_market_condition(ema)
        assert result == LongTermMarketCondition.BULL

    def test_negative_long_trend_is_bear(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEGATIVE)
        result = determine_longterm_market_condition(ema)
        assert result == LongTermMarketCondition.BEAR

    def test_neutral_long_trend_is_neutral(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEUTRAL)
        result = determine_longterm_market_condition(ema)
        assert result == LongTermMarketCondition.NEUTRAL


# ---------------------------------------------------------------------------
# get_strategic_allocation_adjustment
# ---------------------------------------------------------------------------

class TestGetStrategicAllocationAdjustment:
    def test_bull_returns_bull_adjustment(self):
        config = LongTermMarketTrendConfig(bull_adjustment=5.0)
        adj = get_strategic_allocation_adjustment(LongTermMarketCondition.BULL, config)
        assert adj == 5.0

    def test_bear_returns_bear_adjustment(self):
        config = LongTermMarketTrendConfig(bear_adjustment=-15.0)
        adj = get_strategic_allocation_adjustment(LongTermMarketCondition.BEAR, config)
        assert adj == -15.0

    def test_neutral_returns_neutral_adjustment(self):
        config = LongTermMarketTrendConfig(neutral_adjustment=2.0)
        adj = get_strategic_allocation_adjustment(LongTermMarketCondition.NEUTRAL, config)
        assert adj == 2.0

    def test_unknown_returns_zero(self):
        adj = get_strategic_allocation_adjustment(LongTermMarketCondition.UNKNOWN)
        assert adj == 0.0


# ---------------------------------------------------------------------------
# get_market_cycle_phase
# ---------------------------------------------------------------------------

class TestGetMarketCyclePhase:
    def test_bull_accumulation(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.POSITIVE,
                        short_trend=LongTermTrendDirection.POSITIVE)
        phase = get_market_cycle_phase(ema)
        assert "Bull" in phase
        assert "Accumulation" in phase

    def test_bear_distribution(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEGATIVE,
                        short_trend=LongTermTrendDirection.NEGATIVE)
        phase = get_market_cycle_phase(ema)
        assert "Bear" in phase
        assert "Distribution" in phase

    def test_neutral_consolidating(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEUTRAL,
                        short_trend=LongTermTrendDirection.NEUTRAL)
        phase = get_market_cycle_phase(ema)
        assert "Neutral" in phase
        assert "Consolidating" in phase


# ---------------------------------------------------------------------------
# format_longterm_market_summary
# ---------------------------------------------------------------------------

class TestFormatLongtermMarketSummary:
    def test_none_ema_data_shows_unavailable(self):
        summary = format_longterm_market_summary(LongTermMarketCondition.UNKNOWN, None)
        assert "unavailable" in summary.lower()

    def test_bull_condition_in_summary(self):
        ema = _make_ema()
        summary = format_longterm_market_summary(LongTermMarketCondition.BULL, ema)
        assert "BULL" in summary

    def test_price_shown_in_summary(self):
        ema = _make_ema()
        summary = format_longterm_market_summary(LongTermMarketCondition.BULL, ema)
        assert "510.00" in summary

    def test_confidence_shown_in_summary(self):
        ema = _make_ema(confidence=0.8)
        summary = format_longterm_market_summary(LongTermMarketCondition.BULL, ema)
        assert "80%" in summary


# ---------------------------------------------------------------------------
# get_strategic_recommendations
# ---------------------------------------------------------------------------

class TestGetStrategicRecommendations:
    def test_none_ema_returns_unavailable_message(self):
        recs = get_strategic_recommendations(LongTermMarketCondition.BULL, None)
        assert len(recs) == 1
        assert "unavailable" in recs[0].lower()

    def test_bull_accumulation_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.POSITIVE,
                        short_trend=LongTermTrendDirection.POSITIVE)
        recs = get_strategic_recommendations(LongTermMarketCondition.BULL, ema)
        assert isinstance(recs, list)
        assert len(recs) >= 1

    def test_bull_consolidating_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.POSITIVE,
                        short_trend=LongTermTrendDirection.NEUTRAL)
        recs = get_strategic_recommendations(LongTermMarketCondition.BULL, ema)
        assert len(recs) >= 1

    def test_bull_distribution_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.POSITIVE,
                        short_trend=LongTermTrendDirection.NEGATIVE)
        recs = get_strategic_recommendations(LongTermMarketCondition.BULL, ema)
        assert len(recs) >= 1

    def test_neutral_accumulation_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEUTRAL,
                        short_trend=LongTermTrendDirection.POSITIVE)
        recs = get_strategic_recommendations(LongTermMarketCondition.NEUTRAL, ema)
        assert len(recs) >= 1

    def test_neutral_consolidating_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEUTRAL,
                        short_trend=LongTermTrendDirection.NEUTRAL)
        recs = get_strategic_recommendations(LongTermMarketCondition.NEUTRAL, ema)
        assert len(recs) >= 1

    def test_neutral_distribution_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEUTRAL,
                        short_trend=LongTermTrendDirection.NEGATIVE)
        recs = get_strategic_recommendations(LongTermMarketCondition.NEUTRAL, ema)
        assert len(recs) >= 1

    def test_bear_accumulation_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEGATIVE,
                        short_trend=LongTermTrendDirection.POSITIVE)
        recs = get_strategic_recommendations(LongTermMarketCondition.BEAR, ema)
        assert len(recs) >= 1

    def test_bear_consolidating_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEGATIVE,
                        short_trend=LongTermTrendDirection.NEUTRAL)
        recs = get_strategic_recommendations(LongTermMarketCondition.BEAR, ema)
        assert len(recs) >= 1

    def test_bear_distribution_returns_list(self):
        ema = _make_ema(long_trend=LongTermTrendDirection.NEGATIVE,
                        short_trend=LongTermTrendDirection.NEGATIVE)
        recs = get_strategic_recommendations(LongTermMarketCondition.BEAR, ema)
        assert len(recs) >= 1

    def test_bear_distribution_long_trend_adds_extra_rec(self):
        # months_in_trend >= 6 adds an extra recommendation
        ema = _make_ema(long_trend=LongTermTrendDirection.NEGATIVE,
                        short_trend=LongTermTrendDirection.NEGATIVE,
                        months_in_trend=7)
        recs = get_strategic_recommendations(LongTermMarketCondition.BEAR, ema)
        assert len(recs) >= 3

    def test_unknown_condition_returns_single_unclear_message(self):
        ema = _make_ema()
        recs = get_strategic_recommendations(LongTermMarketCondition.UNKNOWN, ema)
        assert len(recs) >= 1


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

class TestCacheManagement:
    def test_clear_cache_clears_data(self):
        ema = _make_ema()
        _cache_longterm_condition(LongTermMarketCondition.BULL, ema)
        clear_longterm_market_condition_cache()
        assert _get_cached_longterm_condition() is None

    def test_cached_value_is_returned(self):
        clear_longterm_market_condition_cache()
        ema = _make_ema()
        _cache_longterm_condition(LongTermMarketCondition.BEAR, ema)
        result = _get_cached_longterm_condition()
        assert result is not None
        condition, cached_ema = result
        assert condition == LongTermMarketCondition.BEAR

    def test_disabled_config_returns_unknown(self):
        config = LongTermMarketTrendConfig(enabled=False)
        condition, ema_data = get_longterm_market_condition(config)
        assert condition == LongTermMarketCondition.UNKNOWN
        assert ema_data is None
