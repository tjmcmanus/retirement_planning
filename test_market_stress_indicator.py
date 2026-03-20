"""
test_market_stress_indicator.py
================================
Tests for the EventHorizonIQ Market Stress Indicator component.
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from components.market_stress_indicator import (
    StressIndicatorData,
    fetch_stress_indicator,
    get_stress_level_info,
    STRESS_REVIEW_THRESHOLD,
    STRESS_HEDGE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

MOCK_API_RESPONSE = {
    "stress_index": 22.4,
    "regime": "NEUTRAL",
    "sensor_count": 55,
    "breakdown": {
        "severe": 0,
        "elevated": 2,
        "rising": 8,
        "neutral": 12,
        "stable": 33
    },
    "as_of": "2026-03-16T15:30:00Z",
    "methodology": "Weighted average of all active sensor states..."
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_stress_level_info_normal():
    """Test stress level info for normal conditions."""
    emoji, color, status, recommendation = get_stress_level_info(30.0)
    assert emoji == "🟢"
    assert color == "#21c354"
    assert status == "NORMAL"
    assert "Continue normal operations" in recommendation


def test_stress_level_info_warning():
    """Test stress level info for warning conditions."""
    emoji, color, status, recommendation = get_stress_level_info(60.0)
    assert emoji == "🟡"
    assert color == "#ffa500"
    assert status == "WARNING"
    assert "Flag portfolio for review" in recommendation


def test_stress_level_info_critical():
    """Test stress level info for critical conditions."""
    emoji, color, status, recommendation = get_stress_level_info(75.0)
    assert emoji == "🔴"
    assert color == "#ff4b4b"
    assert status == "CRITICAL"
    assert "Activate hedges" in recommendation


def test_stress_level_thresholds():
    """Test exact threshold boundaries."""
    # Just below review threshold
    emoji, _, status, _ = get_stress_level_info(STRESS_REVIEW_THRESHOLD - 0.1)
    assert status == "NORMAL"
    
    # At review threshold
    emoji, _, status, _ = get_stress_level_info(STRESS_REVIEW_THRESHOLD)
    assert status == "WARNING"
    
    # Just below hedge threshold
    emoji, _, status, _ = get_stress_level_info(STRESS_HEDGE_THRESHOLD - 0.1)
    assert status == "WARNING"
    
    # At hedge threshold
    emoji, _, status, _ = get_stress_level_info(STRESS_HEDGE_THRESHOLD)
    assert status == "CRITICAL"


@patch('components.market_stress_indicator.requests.get')
def test_fetch_stress_indicator_success(mock_get):
    """Test successful API fetch."""
    # Mock successful API response
    mock_response = Mock()
    mock_response.json.return_value = MOCK_API_RESPONSE
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    # Clear cache
    import components.market_stress_indicator as msi
    msi._stress_cache = None
    
    # Fetch data
    result = fetch_stress_indicator()
    
    # Verify result
    assert result is not None
    assert result.stress_index == 22.4
    assert result.regime == "NEUTRAL"
    assert result.sensor_count == 55
    assert result.breakdown["severe"] == 0
    assert result.breakdown["stable"] == 33
    assert result.as_of == "2026-03-16T15:30:00Z"
    
    # Verify API was called
    mock_get.assert_called_once()


@patch('components.market_stress_indicator.requests.get')
def test_fetch_stress_indicator_network_error(mock_get):
    """Test API fetch with network error."""
    # Mock network error
    mock_get.side_effect = Exception("Network error")
    
    # Clear cache
    import components.market_stress_indicator as msi
    msi._stress_cache = None
    
    # Fetch data
    result = fetch_stress_indicator()
    
    # Verify result is None
    assert result is None


@patch('components.market_stress_indicator.requests.get')
def test_fetch_stress_indicator_caching(mock_get):
    """Test that stress indicator data is cached."""
    # Mock successful API response
    mock_response = Mock()
    mock_response.json.return_value = MOCK_API_RESPONSE
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    # Clear cache
    import components.market_stress_indicator as msi
    msi._stress_cache = None
    
    # First fetch
    result1 = fetch_stress_indicator()
    assert result1 is not None
    assert mock_get.call_count == 1
    
    # Second fetch (should use cache)
    result2 = fetch_stress_indicator()
    assert result2 is not None
    assert result2.stress_index == result1.stress_index
    assert mock_get.call_count == 1  # Still only called once


@patch('components.market_stress_indicator.requests.get')
def test_fetch_stress_indicator_invalid_json(mock_get):
    """Test API fetch with invalid JSON response."""
    # Mock invalid JSON response
    mock_response = Mock()
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    # Clear cache
    import components.market_stress_indicator as msi
    msi._stress_cache = None
    
    # Fetch data
    result = fetch_stress_indicator()
    
    # Verify result is None
    assert result is None


def test_stress_indicator_data_creation():
    """Test StressIndicatorData dataclass creation."""
    data = StressIndicatorData(
        stress_index=45.5,
        regime="NEUTRAL",
        sensor_count=55,
        breakdown={"severe": 1, "elevated": 3, "rising": 10, "neutral": 15, "stable": 26},
        as_of="2026-03-19T12:00:00Z",
        methodology="Test methodology",
        fetch_time=datetime.now()
    )
    
    assert data.stress_index == 45.5
    assert data.regime == "NEUTRAL"
    assert data.sensor_count == 55
    assert data.breakdown["severe"] == 1
    assert isinstance(data.fetch_time, datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# Made with Bob