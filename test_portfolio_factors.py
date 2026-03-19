"""
Tests for Portfolio Factor Analysis Module
==========================================

Author: Bob
Date: 2026-03-17
"""

import pytest
import pandas as pd
from datetime import datetime

from portfolio_factors import (
    FactorMetrics,
    PortfolioFactorExposure,
    DataQuality,
    PortfolioStyle,
    fetch_factor_data,
    classify_portfolio_style,
    calculate_factor_concentration,
    _calculate_value_score,
    _calculate_growth_score,
    _calculate_momentum_score,
    _calculate_quality_score,
)


# ==============================================================================
# UNIT TESTS - Factor Scoring
# ==============================================================================

class TestFactorScoring:
    """Test factor scoring algorithms."""
    
    def test_value_score_low_pe(self):
        """Test value scoring with low P/E ratio."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            pe_ratio=8.0,
            value_metrics_available=1,
        )
        score = _calculate_value_score(metrics)
        assert score == 100.0  # P/E < 10 = 100 points
    
    def test_value_score_high_pe(self):
        """Test value scoring with high P/E ratio."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            pe_ratio=35.0,
            value_metrics_available=1,
        )
        score = _calculate_value_score(metrics)
        assert score == 20.0  # P/E > 30 = 20 points
    
    def test_growth_score_high_growth(self):
        """Test growth scoring with high growth."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            earnings_growth=0.25,  # 25%
            growth_metrics_available=1,
        )
        score = _calculate_growth_score(metrics)
        assert score == 100.0  # Growth > 20% = 100 points
    
    def test_momentum_score_positive_returns(self):
        """Test momentum scoring with positive returns."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            return_12m=35.0,  # 35% return
            momentum_metrics_available=1,
        )
        score = _calculate_momentum_score(metrics)
        assert score == 100.0  # 12M return > 30% = 100 points
    
    def test_quality_score_high_roe(self):
        """Test quality scoring with high ROE."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            roe=0.25,  # 25%
            quality_metrics_available=1,
        )
        score = _calculate_quality_score(metrics)
        assert score == 100.0  # ROE > 20% = 100 points
    
    def test_no_data_returns_default(self):
        """Test that missing data returns default score of 50."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            value_metrics_available=0,
        )
        score = _calculate_value_score(metrics)
        assert score == 50.0


# ==============================================================================
# UNIT TESTS - Style Classification
# ==============================================================================

class TestStyleClassification:
    """Test portfolio style classification."""
    
    def test_value_style(self):
        """Test classification as Value style."""
        primary, secondary, purity = classify_portfolio_style(
            value_score=80.0,
            growth_score=40.0,
            momentum_score=45.0,
            quality_score=50.0,
        )
        assert primary == PortfolioStyle.VALUE
        assert purity > 0
    
    def test_growth_style(self):
        """Test classification as Growth style."""
        primary, secondary, purity = classify_portfolio_style(
            value_score=40.0,
            growth_score=85.0,
            momentum_score=45.0,
            quality_score=50.0,
        )
        assert primary == PortfolioStyle.GROWTH
        assert purity > 0
    
    def test_blend_style(self):
        """Test classification as Blend style."""
        primary, secondary, purity = classify_portfolio_style(
            value_score=60.0,
            growth_score=60.0,
            momentum_score=45.0,
            quality_score=50.0,
        )
        assert primary == PortfolioStyle.BLEND
    
    def test_balanced_style(self):
        """Test classification as Balanced style."""
        primary, secondary, purity = classify_portfolio_style(
            value_score=50.0,
            growth_score=50.0,
            momentum_score=50.0,
            quality_score=50.0,
        )
        # When all scores are equal at 50, it's classified as BLEND
        assert primary == PortfolioStyle.BLEND


# ==============================================================================
# UNIT TESTS - Factor Concentration
# ==============================================================================

class TestFactorConcentration:
    """Test factor concentration calculations."""
    
    def test_single_holding_concentrated(self):
        """Test that single holding is 100% concentrated."""
        holdings = [("AAPL", 1.0, 80.0)]
        concentration = calculate_factor_concentration(holdings)
        assert concentration == 100.0
    
    def test_equal_weights_diversified(self):
        """Test that equal weights are well diversified."""
        holdings = [
            ("AAPL", 0.25, 80.0),
            ("GOOGL", 0.25, 75.0),
            ("MSFT", 0.25, 70.0),
            ("AMZN", 0.25, 85.0),
        ]
        concentration = calculate_factor_concentration(holdings)
        assert concentration == 0.0  # Perfectly diversified
    
    def test_empty_holdings(self):
        """Test empty holdings list."""
        concentration = calculate_factor_concentration([])
        assert concentration == 0.0


# ==============================================================================
# UNIT TESTS - Data Classes
# ==============================================================================

class TestFactorMetrics:
    """Test FactorMetrics data class."""
    
    def test_overall_score_calculation(self):
        """Test overall score calculation."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            value_score=80.0,
            growth_score=60.0,
            momentum_score=70.0,
            quality_score=90.0,
        )
        overall = metrics.get_overall_score()
        expected = (80.0 * 0.25 + 60.0 * 0.25 + 70.0 * 0.25 + 90.0 * 0.25)
        assert overall == expected
    
    def test_data_completeness(self):
        """Test data completeness calculation."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            value_metrics_available=2,
            value_metrics_total=4,
            growth_metrics_available=1,
            growth_metrics_total=3,
            momentum_metrics_available=3,
            momentum_metrics_total=5,
            quality_metrics_available=4,
            quality_metrics_total=5,
        )
        completeness = metrics.get_data_completeness()
        expected = (2 + 1 + 3 + 4) / (4 + 3 + 5 + 5)
        assert completeness == expected
    
    def test_data_quality_update(self):
        """Test data quality indicator update."""
        metrics = FactorMetrics(
            symbol="TEST",
            name="Test Stock",
            value_metrics_available=4,
            value_metrics_total=4,
            growth_metrics_available=3,
            growth_metrics_total=3,
            momentum_metrics_available=5,
            momentum_metrics_total=5,
            quality_metrics_available=5,
            quality_metrics_total=5,
        )
        metrics.update_data_quality()
        assert metrics.data_quality == DataQuality.COMPLETE


class TestPortfolioFactorExposure:
    """Test PortfolioFactorExposure data class."""
    
    def test_dominant_factors(self):
        """Test dominant factors identification."""
        exposure = PortfolioFactorExposure(
            value_exposure=75.0,
            growth_exposure=45.0,
            momentum_exposure=65.0,
            quality_exposure=80.0,
        )
        dominant = exposure.get_dominant_factors(threshold=60.0)
        assert 'value' in dominant
        assert 'momentum' in dominant
        assert 'quality' in dominant
        assert 'growth' not in dominant
    
    def test_factor_balance(self):
        """Test factor balance calculation."""
        exposure = PortfolioFactorExposure(
            value_exposure=50.0,
            growth_exposure=50.0,
            momentum_exposure=50.0,
            quality_exposure=50.0,
        )
        balance = exposure.get_factor_balance()
        assert balance['value'] == 25.0
        assert balance['growth'] == 25.0
        assert balance['momentum'] == 25.0
        assert balance['quality'] == 25.0


# ==============================================================================
# INTEGRATION TESTS - Data Fetching
# ==============================================================================

class TestDataFetching:
    """Test data fetching from Yahoo Finance."""
    
    @pytest.mark.slow
    def test_fetch_real_stock_data(self):
        """Test fetching real data for AAPL."""
        metrics = fetch_factor_data("AAPL", use_cache=False)
        
        assert metrics.symbol == "AAPL"
        assert metrics.name is not None
        assert metrics.data_quality != DataQuality.UNAVAILABLE
        assert metrics.last_updated is not None
    
    @pytest.mark.slow
    def test_fetch_with_caching(self):
        """Test that caching works."""
        # First fetch (no cache)
        metrics1 = fetch_factor_data("MSFT", use_cache=True)
        
        # Second fetch (should use cache)
        metrics2 = fetch_factor_data("MSFT", use_cache=True)
        
        assert metrics1.symbol == metrics2.symbol
        assert metrics1.value_score == metrics2.value_score
    
    def test_fetch_invalid_symbol(self):
        """Test fetching invalid symbol returns unavailable."""
        metrics = fetch_factor_data("INVALID_SYMBOL_XYZ", use_cache=False)
        
        assert metrics.symbol == "INVALID_SYMBOL_XYZ"
        assert metrics.data_quality == DataQuality.UNAVAILABLE


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob



# ==============================================================================
# INTEGRATION TESTS - Portfolio Analysis
# ==============================================================================

class TestPortfolioAnalysis:
    """Test portfolio-level factor analysis."""
    
    def test_calculate_portfolio_exposure(self):
        """Test portfolio factor exposure calculation."""
        # Create sample portfolio
        portfolio_df = pd.DataFrame([
            {'symbol': 'AAPL', 'market_value': 10000},
            {'symbol': 'GOOGL', 'market_value': 15000},
            {'symbol': 'MSFT', 'market_value': 20000},
        ])
        
        # Create factor data
        factor_data = {
            'AAPL': FactorMetrics(
                symbol='AAPL',
                name='Apple Inc.',
                value_score=60.0,
                growth_score=80.0,
                momentum_score=70.0,
                quality_score=90.0,
                data_quality=DataQuality.COMPLETE,
            ),
            'GOOGL': FactorMetrics(
                symbol='GOOGL',
                name='Alphabet Inc.',
                value_score=70.0,
                growth_score=85.0,
                momentum_score=65.0,
                quality_score=85.0,
                data_quality=DataQuality.COMPLETE,
            ),
            'MSFT': FactorMetrics(
                symbol='MSFT',
                name='Microsoft Corp.',
                value_score=65.0,
                growth_score=75.0,
                momentum_score=75.0,
                quality_score=95.0,
                data_quality=DataQuality.COMPLETE,
            ),
        }
        
        # Calculate exposure
        from portfolio_factors import calculate_portfolio_factor_exposure
        exposure = calculate_portfolio_factor_exposure(portfolio_df, factor_data)
        
        # Verify results
        assert exposure.total_holdings == 3
        assert exposure.analyzed_holdings == 3
        assert exposure.coverage_pct == 100.0
        assert exposure.total_market_value == 45000
        
        # Check weighted scores (should be weighted by market value)
        # AAPL: 10k/45k = 22.2%, GOOGL: 15k/45k = 33.3%, MSFT: 20k/45k = 44.4%
        expected_value = 60*0.222 + 70*0.333 + 65*0.444
        assert abs(exposure.value_exposure - expected_value) < 1.0
        
        # Check style classification
        assert exposure.primary_style in [PortfolioStyle.GROWTH, PortfolioStyle.QUALITY, PortfolioStyle.BLEND]
        
        # Check holdings lists
        assert len(exposure.value_holdings) == 3
        assert len(exposure.growth_holdings) == 3
        assert len(exposure.momentum_holdings) == 3
        assert len(exposure.quality_holdings) == 3
    
    def test_empty_portfolio(self):
        """Test with empty portfolio."""
        from portfolio_factors import calculate_portfolio_factor_exposure
        exposure = calculate_portfolio_factor_exposure(pd.DataFrame(), {})
        
        assert exposure.total_holdings == 0
        assert exposure.analyzed_holdings == 0
    
    def test_missing_factor_data(self):
        """Test with missing factor data for some holdings."""
        portfolio_df = pd.DataFrame([
            {'symbol': 'AAPL', 'market_value': 10000},
            {'symbol': 'UNKNOWN', 'market_value': 5000},
        ])
        
        factor_data = {
            'AAPL': FactorMetrics(
                symbol='AAPL',
                name='Apple Inc.',
                value_score=60.0,
                growth_score=80.0,
                momentum_score=70.0,
                quality_score=90.0,
                data_quality=DataQuality.COMPLETE,
            ),
        }
        
        from portfolio_factors import calculate_portfolio_factor_exposure
        exposure = calculate_portfolio_factor_exposure(portfolio_df, factor_data)
        
        # Should only analyze AAPL
        assert exposure.total_holdings == 2
        assert exposure.analyzed_holdings == 1
        assert exposure.coverage_pct < 100.0

