"""
Portfolio Factor Analysis Module
=================================
Institutional-grade factor analysis for portfolio holdings.

This module provides comprehensive factor-based analysis across four key investment factors:
- Value: Low P/E, P/B ratios (undervalued stocks)
- Growth: High earnings/revenue growth
- Momentum: Recent price trends and relative strength
- Quality: High ROE, low debt, stable earnings

Key Features:
- Factor data fetching from Yahoo Finance
- Multi-factor scoring (0-100 scale)
- Portfolio-level factor exposure analysis
- Style classification (Value/Growth/Blend/Quality/Momentum)
- Factor drift tracking over time
- Performance attribution by factor

Author: Bob
Date: 2026-03-17
Version: 1.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from enum import Enum
import yfinance as yf
import sqlite3
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# ==============================================================================
# CACHE MANAGEMENT
# ==============================================================================

# Cache database path
CACHE_DB_PATH = Path(__file__).parent / "data" / "factor_cache.db"

def _init_cache_db():
    """Initialize cache database if it doesn't exist."""
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS factor_cache (
            symbol TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

def _get_cached_data(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached factor data if still valid."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT data, timestamp FROM factor_cache WHERE symbol = ?",
            (symbol,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            data_json, timestamp = result
            cache_age_hours = (datetime.now().timestamp() - timestamp) / 3600
            
            if cache_age_hours < CACHE_DURATION_HOURS:
                return json.loads(data_json)
        
        return None
    except Exception as e:
        logger.warning(f"Error reading cache for {symbol}: {e}")
        return None

def _save_to_cache(symbol: str, data: Dict[str, Any]):
    """Save factor data to cache."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO factor_cache (symbol, data, timestamp) VALUES (?, ?, ?)",
            (symbol, json.dumps(data), datetime.now().timestamp())
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Error saving cache for {symbol}: {e}")

def _clear_old_cache():
    """Remove cache entries older than MAX_CACHE_SIZE."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        
        # Keep only the most recent MAX_CACHE_SIZE entries
        cursor.execute("""
            DELETE FROM factor_cache
            WHERE symbol NOT IN (
                SELECT symbol FROM factor_cache
                ORDER BY timestamp DESC
                LIMIT ?
            )
        """, (MAX_CACHE_SIZE,))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Error clearing old cache: {e}")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Factor weights for composite scoring
FACTOR_WEIGHTS = {
    'value': 0.25,
    'growth': 0.25,
    'momentum': 0.25,
    'quality': 0.25,
}

# Momentum period weights (must sum to 1.0)
MOMENTUM_WEIGHTS = {
    '1m': 0.10,
    '3m': 0.20,
    '6m': 0.30,
    '12m': 0.40,
}

# Style classification thresholds
STYLE_THRESHOLD_HIGH = 70.0  # Score above this = strong factor exposure
STYLE_THRESHOLD_LOW = 50.0   # Score below this = weak factor exposure
STYLE_PURITY_THRESHOLD = 20.0  # Difference needed for pure style

# Data quality thresholds
DATA_QUALITY_COMPLETE = 0.90  # 90%+ metrics available
DATA_QUALITY_PARTIAL = 0.50   # 50-90% metrics available
# Below 50% = limited

# Cache settings
CACHE_DURATION_HOURS = 24
MAX_CACHE_SIZE = 1000

# Benchmark assumptions (S&P 500 typical values)
BENCHMARK_FACTORS = {
    'value': 50.0,
    'growth': 50.0,
    'momentum': 50.0,
    'quality': 50.0,
}


# ==============================================================================
# ENUMS
# ==============================================================================

class DataQuality(Enum):
    """Data quality indicator."""
    COMPLETE = "complete"  # 90%+ metrics available
    PARTIAL = "partial"    # 50-90% metrics available
    LIMITED = "limited"    # <50% metrics available
    UNAVAILABLE = "unavailable"  # No data


class PortfolioStyle(Enum):
    """Portfolio style classification."""
    VALUE = "Value"
    GROWTH = "Growth"
    BLEND = "Blend"
    QUALITY = "Quality"
    MOMENTUM = "Momentum"
    BALANCED = "Balanced"


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class FactorMetrics:
    """
    Factor metrics for a single security.
    
    All factor scores are on a 0-100 scale where:
    - 0 = Worst (bottom percentile)
    - 50 = Average (market benchmark)
    - 100 = Best (top percentile)
    """
    symbol: str
    name: str
    
    # Value factors (lower ratios = higher scores)
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    value_score: float = 50.0  # 0-100 composite
    
    # Growth factors (higher growth = higher scores)
    earnings_growth: Optional[float] = None
    revenue_growth: Optional[float] = None
    eps_growth: Optional[float] = None
    growth_score: float = 50.0  # 0-100 composite
    
    # Momentum factors (higher returns = higher scores)
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_12m: Optional[float] = None
    relative_strength: Optional[float] = None
    momentum_score: float = 50.0  # 0-100 composite
    
    # Quality factors (better metrics = higher scores)
    roe: Optional[float] = None  # Return on Equity
    roa: Optional[float] = None  # Return on Assets
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    profit_margin: Optional[float] = None
    quality_score: float = 50.0  # 0-100 composite
    
    # Metadata
    market_cap: Optional[float] = None
    sector: str = "Unknown"
    asset_class: str = "Stocks"
    data_quality: DataQuality = DataQuality.UNAVAILABLE
    last_updated: Optional[datetime] = None
    
    # Metrics availability tracking
    value_metrics_available: int = 0
    value_metrics_total: int = 4
    growth_metrics_available: int = 0
    growth_metrics_total: int = 3
    momentum_metrics_available: int = 0
    momentum_metrics_total: int = 5
    quality_metrics_available: int = 0
    quality_metrics_total: int = 5
    
    def get_overall_score(self) -> float:
        """Calculate overall factor score (weighted average)."""
        return (
            self.value_score * FACTOR_WEIGHTS['value'] +
            self.growth_score * FACTOR_WEIGHTS['growth'] +
            self.momentum_score * FACTOR_WEIGHTS['momentum'] +
            self.quality_score * FACTOR_WEIGHTS['quality']
        )
    
    def get_data_completeness(self) -> float:
        """Calculate percentage of available metrics."""
        total_metrics = (
            self.value_metrics_total +
            self.growth_metrics_total +
            self.momentum_metrics_total +
            self.quality_metrics_total
        )
        available_metrics = (
            self.value_metrics_available +
            self.growth_metrics_available +
            self.momentum_metrics_available +
            self.quality_metrics_available
        )
        return available_metrics / total_metrics if total_metrics > 0 else 0.0
    
    def update_data_quality(self):
        """Update data quality indicator based on completeness."""
        completeness = self.get_data_completeness()
        if completeness >= DATA_QUALITY_COMPLETE:
            self.data_quality = DataQuality.COMPLETE
        elif completeness >= DATA_QUALITY_PARTIAL:
            self.data_quality = DataQuality.PARTIAL
        elif completeness > 0:
            self.data_quality = DataQuality.LIMITED
        else:
            self.data_quality = DataQuality.UNAVAILABLE


@dataclass
class PortfolioFactorExposure:
    """
    Portfolio-level factor exposure analysis.
    
    Provides comprehensive view of portfolio's factor characteristics
    including weighted scores, tilts vs benchmark, and style classification.
    """
    
    # Weighted average factor scores (0-100)
    value_exposure: float = 50.0
    growth_exposure: float = 50.0
    momentum_exposure: float = 50.0
    quality_exposure: float = 50.0
    
    # Factor tilts relative to benchmark (-50 to +50)
    value_tilt: float = 0.0
    growth_tilt: float = 0.0
    momentum_tilt: float = 0.0
    quality_tilt: float = 0.0
    
    # Style classification
    primary_style: PortfolioStyle = PortfolioStyle.BALANCED
    secondary_style: Optional[PortfolioStyle] = None
    style_purity: float = 0.0  # 0-100, how pure the style is
    
    # Holdings breakdown by factor (symbol, weight, score)
    value_holdings: List[Tuple[str, float, float]] = field(default_factory=list)
    growth_holdings: List[Tuple[str, float, float]] = field(default_factory=list)
    momentum_holdings: List[Tuple[str, float, float]] = field(default_factory=list)
    quality_holdings: List[Tuple[str, float, float]] = field(default_factory=list)
    
    # Factor diversification metrics
    factor_concentration: float = 0.0  # 0-100, lower = more diversified
    factor_correlation: Optional[pd.DataFrame] = None
    
    # Portfolio composition
    total_holdings: int = 0
    analyzed_holdings: int = 0
    total_market_value: float = 0.0
    coverage_pct: float = 0.0  # % of portfolio analyzed
    
    # Metadata
    analysis_date: Optional[datetime] = None
    benchmark_name: str = "S&P 500"
    
    def get_dominant_factors(self, threshold: float = 60.0) -> List[str]:
        """Get list of factors with exposure above threshold."""
        dominant = []
        if self.value_exposure >= threshold:
            dominant.append('value')
        if self.growth_exposure >= threshold:
            dominant.append('growth')
        if self.momentum_exposure >= threshold:
            dominant.append('momentum')
        if self.quality_exposure >= threshold:
            dominant.append('quality')
        return dominant
    
    def get_factor_balance(self) -> Dict[str, float]:
        """Get factor balance as percentages."""
        total = (
            self.value_exposure +
            self.growth_exposure +
            self.momentum_exposure +
            self.quality_exposure
        )
        if total == 0:
            return {'value': 25.0, 'growth': 25.0, 'momentum': 25.0, 'quality': 25.0}
        
        return {
            'value': (self.value_exposure / total) * 100,
            'growth': (self.growth_exposure / total) * 100,
            'momentum': (self.momentum_exposure / total) * 100,
            'quality': (self.quality_exposure / total) * 100,
        }


@dataclass
class FactorAttribution:
    """
    Factor-based performance attribution.
    
    Decomposes portfolio returns into factor contributions and alpha.
    """
    
    # Total return breakdown
    total_return: float = 0.0
    factor_return: float = 0.0  # Return explained by factors
    alpha: float = 0.0  # Return not explained by factors
    
    # Factor contributions to return
    value_contribution: float = 0.0
    growth_contribution: float = 0.0
    momentum_contribution: float = 0.0
    quality_contribution: float = 0.0
    
    # Time period
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    period_days: int = 0
    
    # Time series data
    factor_returns_ts: Optional[pd.DataFrame] = None
    cumulative_returns: Optional[pd.DataFrame] = None
    
    # Statistical measures
    r_squared: float = 0.0  # How much variance explained by factors
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    
    def get_factor_contributions_pct(self) -> Dict[str, float]:
        """Get factor contributions as percentages of total return."""
        if self.total_return == 0:
            return {'value': 0.0, 'growth': 0.0, 'momentum': 0.0, 'quality': 0.0, 'alpha': 0.0}
        
        return {
            'value': (self.value_contribution / self.total_return) * 100,
            'growth': (self.growth_contribution / self.total_return) * 100,
            'momentum': (self.momentum_contribution / self.total_return) * 100,
            'quality': (self.quality_contribution / self.total_return) * 100,
            'alpha': (self.alpha / self.total_return) * 100,
        }


@dataclass
class FactorDrift:
    """
    Factor drift analysis over time.
    
    Tracks how portfolio factor exposures change relative to targets.
    """
    
    # Current vs target exposures
    current_exposure: PortfolioFactorExposure
    target_exposure: Optional[PortfolioFactorExposure] = None
    
    # Drift metrics (current - target)
    value_drift: float = 0.0
    growth_drift: float = 0.0
    momentum_drift: float = 0.0
    quality_drift: float = 0.0
    
    # Historical tracking
    historical_exposures: List[PortfolioFactorExposure] = field(default_factory=list)
    exposure_dates: List[datetime] = field(default_factory=list)
    
    # Drift statistics
    max_drift: float = 0.0
    avg_drift: float = 0.0
    drift_volatility: float = 0.0
    
    # Trend analysis
    value_trend: str = "stable"  # "increasing", "decreasing", "stable"
    growth_trend: str = "stable"
    momentum_trend: str = "stable"
    quality_trend: str = "stable"
    
    # Recommendations
    rebalancing_needed: bool = False
    drift_threshold: float = 10.0  # Threshold for rebalancing alert
    recommendations: List[str] = field(default_factory=list)
    
    def calculate_total_drift(self) -> float:
        """Calculate total drift magnitude."""
        return abs(self.value_drift) + abs(self.growth_drift) + \
               abs(self.momentum_drift) + abs(self.quality_drift)
    
    def needs_rebalancing(self) -> bool:
        """Check if any factor drift exceeds threshold."""
        return (
            abs(self.value_drift) > self.drift_threshold or
            abs(self.growth_drift) > self.drift_threshold or
            abs(self.momentum_drift) > self.drift_threshold or
            abs(self.quality_drift) > self.drift_threshold
        )


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def classify_portfolio_style(
    value_score: float,
    growth_score: float,
    momentum_score: float,
    quality_score: float,
) -> Tuple[PortfolioStyle, Optional[PortfolioStyle], float]:
    """
    Classify portfolio style based on factor scores.
    
    Args:
        value_score: Value factor score (0-100)
        growth_score: Growth factor score (0-100)
        momentum_score: Momentum factor score (0-100)
        quality_score: Quality factor score (0-100)
    
    Returns:
        Tuple of (primary_style, secondary_style, purity)
    """
    scores = {
        'value': value_score,
        'growth': growth_score,
        'momentum': momentum_score,
        'quality': quality_score,
    }
    
    # Sort by score
    sorted_factors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    highest_factor, highest_score = sorted_factors[0]
    second_factor, second_score = sorted_factors[1]
    
    # Calculate purity (difference between highest and average of others)
    other_scores = [s for f, s in sorted_factors[1:]]
    avg_others = sum(other_scores) / len(other_scores)
    purity = min(100.0, max(0.0, highest_score - avg_others))
    
    # Determine primary style
    if highest_score >= STYLE_THRESHOLD_HIGH:
        if highest_factor == 'value':
            primary = PortfolioStyle.VALUE
        elif highest_factor == 'growth':
            primary = PortfolioStyle.GROWTH
        elif highest_factor == 'momentum':
            primary = PortfolioStyle.MOMENTUM
        elif highest_factor == 'quality':
            primary = PortfolioStyle.QUALITY
        else:
            primary = PortfolioStyle.BALANCED
    elif value_score >= STYLE_THRESHOLD_LOW and growth_score >= STYLE_THRESHOLD_LOW:
        primary = PortfolioStyle.BLEND
    else:
        primary = PortfolioStyle.BALANCED
    
    # Determine secondary style
    secondary = None
    if second_score >= STYLE_THRESHOLD_LOW and purity < STYLE_PURITY_THRESHOLD:
        if second_factor == 'value':
            secondary = PortfolioStyle.VALUE
        elif second_factor == 'growth':
            secondary = PortfolioStyle.GROWTH
        elif second_factor == 'momentum':
            secondary = PortfolioStyle.MOMENTUM
        elif second_factor == 'quality':
            secondary = PortfolioStyle.QUALITY
    
    return primary, secondary, purity


def calculate_factor_concentration(
    holdings: List[Tuple[str, float, float]]
) -> float:
    """
    Calculate factor concentration (Herfindahl index).
    
    Args:
        holdings: List of (symbol, weight, score) tuples
    
    Returns:
        Concentration score (0-100, lower = more diversified)
    """
    if not holdings:
        return 0.0
    
    # Calculate Herfindahl index
    weights = [w for _, w, _ in holdings]
    total_weight = sum(weights)
    
    if total_weight == 0:
        return 0.0
    
    # Normalize weights
    normalized_weights = [w / total_weight for w in weights]
    
    # Calculate HHI
    hhi = sum(w ** 2 for w in normalized_weights)
    
    # Convert to 0-100 scale (1/n = perfectly diversified, 1 = concentrated)
    n = len(holdings)
    min_hhi = 1.0 / n if n > 0 else 1.0
    concentration = ((hhi - min_hhi) / (1.0 - min_hhi)) * 100 if n > 1 else 100.0
    
    return min(100.0, max(0.0, concentration))


# ==============================================================================
# ==============================================================================
# FACTOR SCORING FUNCTIONS
# ==============================================================================

def _calculate_value_score(metrics: FactorMetrics) -> float:
    """
    Calculate value factor score (0-100).
    Lower ratios = higher scores (better value).
    """
    if metrics.value_metrics_available == 0:
        return 50.0  # Default to market average
    
    scores = []
    
    # P/E ratio scoring (lower is better)
    if metrics.pe_ratio is not None:
        if metrics.pe_ratio < 0:
            scores.append(20.0)  # Negative earnings
        elif metrics.pe_ratio < 10:
            scores.append(100.0)
        elif metrics.pe_ratio < 15:
            scores.append(80.0)
        elif metrics.pe_ratio < 20:
            scores.append(60.0)
        elif metrics.pe_ratio < 30:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # P/B ratio scoring (lower is better)
    if metrics.pb_ratio is not None:
        if metrics.pb_ratio < 0:
            scores.append(20.0)
        elif metrics.pb_ratio < 1.0:
            scores.append(100.0)
        elif metrics.pb_ratio < 2.0:
            scores.append(80.0)
        elif metrics.pb_ratio < 3.0:
            scores.append(60.0)
        elif metrics.pb_ratio < 5.0:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # P/S ratio scoring (lower is better)
    if metrics.ps_ratio is not None:
        if metrics.ps_ratio < 0:
            scores.append(20.0)
        elif metrics.ps_ratio < 1.0:
            scores.append(100.0)
        elif metrics.ps_ratio < 2.0:
            scores.append(80.0)
        elif metrics.ps_ratio < 3.0:
            scores.append(60.0)
        elif metrics.ps_ratio < 5.0:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # Dividend yield scoring (higher is better)
    if metrics.dividend_yield is not None:
        yield_pct = metrics.dividend_yield * 100
        if yield_pct > 4.0:
            scores.append(100.0)
        elif yield_pct > 3.0:
            scores.append(80.0)
        elif yield_pct > 2.0:
            scores.append(60.0)
        elif yield_pct > 1.0:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    return sum(scores) / len(scores) if scores else 50.0


def _calculate_growth_score(metrics: FactorMetrics) -> float:
    """
    Calculate growth factor score (0-100).
    Higher growth = higher scores.
    """
    if metrics.growth_metrics_available == 0:
        return 50.0
    
    scores = []
    
    # Earnings growth scoring
    if metrics.earnings_growth is not None:
        growth_pct = metrics.earnings_growth * 100
        if growth_pct > 20:
            scores.append(100.0)
        elif growth_pct > 15:
            scores.append(80.0)
        elif growth_pct > 10:
            scores.append(60.0)
        elif growth_pct > 5:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # Revenue growth scoring
    if metrics.revenue_growth is not None:
        growth_pct = metrics.revenue_growth * 100
        if growth_pct > 20:
            scores.append(100.0)
        elif growth_pct > 15:
            scores.append(80.0)
        elif growth_pct > 10:
            scores.append(60.0)
        elif growth_pct > 5:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # EPS growth scoring
    if metrics.eps_growth is not None:
        growth_pct = metrics.eps_growth * 100
        if growth_pct > 20:
            scores.append(100.0)
        elif growth_pct > 15:
            scores.append(80.0)
        elif growth_pct > 10:
            scores.append(60.0)
        elif growth_pct > 5:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    return sum(scores) / len(scores) if scores else 50.0


def _calculate_momentum_score(metrics: FactorMetrics) -> float:
    """
    Calculate momentum factor score (0-100).
    Higher returns = higher scores.
    Uses weighted average of different periods.
    """
    if metrics.momentum_metrics_available == 0:
        return 50.0
    
    scores = []
    weights = []
    
    # 1-month return
    if metrics.return_1m is not None:
        if metrics.return_1m > 10:
            scores.append(100.0)
        elif metrics.return_1m > 5:
            scores.append(80.0)
        elif metrics.return_1m > 0:
            scores.append(60.0)
        elif metrics.return_1m > -5:
            scores.append(40.0)
        else:
            scores.append(20.0)
        weights.append(MOMENTUM_WEIGHTS['1m'])
    
    # 3-month return
    if metrics.return_3m is not None:
        if metrics.return_3m > 15:
            scores.append(100.0)
        elif metrics.return_3m > 10:
            scores.append(80.0)
        elif metrics.return_3m > 0:
            scores.append(60.0)
        elif metrics.return_3m > -10:
            scores.append(40.0)
        else:
            scores.append(20.0)
        weights.append(MOMENTUM_WEIGHTS['3m'])
    
    # 6-month return
    if metrics.return_6m is not None:
        if metrics.return_6m > 20:
            scores.append(100.0)
        elif metrics.return_6m > 15:
            scores.append(80.0)
        elif metrics.return_6m > 0:
            scores.append(60.0)
        elif metrics.return_6m > -15:
            scores.append(40.0)
        else:
            scores.append(20.0)
        weights.append(MOMENTUM_WEIGHTS['6m'])
    
    # 12-month return
    if metrics.return_12m is not None:
        if metrics.return_12m > 30:
            scores.append(100.0)
        elif metrics.return_12m > 20:
            scores.append(80.0)
        elif metrics.return_12m > 0:
            scores.append(60.0)
        elif metrics.return_12m > -20:
            scores.append(40.0)
        else:
            scores.append(20.0)
        weights.append(MOMENTUM_WEIGHTS['12m'])
    
    if not scores:
        return 50.0
    
    # Weighted average
    total_weight = sum(weights)
    if total_weight == 0:
        return sum(scores) / len(scores)
    
    return sum(s * w for s, w in zip(scores, weights)) / total_weight


def _calculate_quality_score(metrics: FactorMetrics) -> float:
    """
    Calculate quality factor score (0-100).
    Better metrics = higher scores.
    """
    if metrics.quality_metrics_available == 0:
        return 50.0
    
    scores = []
    
    # ROE scoring (higher is better)
    if metrics.roe is not None:
        roe_pct = metrics.roe * 100
        if roe_pct > 20:
            scores.append(100.0)
        elif roe_pct > 15:
            scores.append(80.0)
        elif roe_pct > 10:
            scores.append(60.0)
        elif roe_pct > 5:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # ROA scoring (higher is better)
    if metrics.roa is not None:
        roa_pct = metrics.roa * 100
        if roa_pct > 10:
            scores.append(100.0)
        elif roa_pct > 7:
            scores.append(80.0)
        elif roa_pct > 5:
            scores.append(60.0)
        elif roa_pct > 3:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # Debt to equity scoring (lower is better)
    if metrics.debt_to_equity is not None:
        if metrics.debt_to_equity < 0.5:
            scores.append(100.0)
        elif metrics.debt_to_equity < 1.0:
            scores.append(80.0)
        elif metrics.debt_to_equity < 1.5:
            scores.append(60.0)
        elif metrics.debt_to_equity < 2.0:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # Current ratio scoring (higher is better, but not too high)
    if metrics.current_ratio is not None:
        if 1.5 <= metrics.current_ratio <= 3.0:
            scores.append(100.0)
        elif 1.0 <= metrics.current_ratio < 1.5:
            scores.append(80.0)
        elif metrics.current_ratio >= 3.0:
            scores.append(70.0)
        elif 0.5 <= metrics.current_ratio < 1.0:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    # Profit margin scoring (higher is better)
    if metrics.profit_margin is not None:
        margin_pct = metrics.profit_margin * 100
        if margin_pct > 20:
            scores.append(100.0)
        elif margin_pct > 15:
            scores.append(80.0)
        elif margin_pct > 10:
            scores.append(60.0)
        elif margin_pct > 5:
            scores.append(40.0)
        else:
            scores.append(20.0)
    
    return sum(scores) / len(scores) if scores else 50.0


# ==============================================================================
# PLACEHOLDER FUNCTIONS (To be implemented in Phase 2-5)
# ==============================================================================

def fetch_factor_data(
    symbol: str,
    use_cache: bool = True,
) -> FactorMetrics:
    """
    Fetch factor data for a security from Yahoo Finance.
    
    Args:
        symbol: Ticker symbol (e.g., 'AAPL', 'VTI')
        use_cache: Whether to use cached data if available
    
    Returns:
        FactorMetrics object with all available factor data
    
    Data Sources:
    - Value: P/E, P/B, P/S, dividend yield from ticker.info
    - Growth: Earnings/revenue growth from ticker.info
    - Momentum: Calculated from historical prices
    - Quality: ROE, ROA, debt ratios from ticker.info
    """
    # Initialize cache
    _init_cache_db()
    
    # Check cache first
    if use_cache:
        cached = _get_cached_data(symbol)
        if cached:
            logger.debug(f"Using cached data for {symbol}")
            return _dict_to_factor_metrics(cached)
    
    logger.info(f"Fetching factor data for {symbol}")
    
    try:
        # Fetch data from Yahoo Finance
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Get historical prices for momentum
        hist = ticker.history(period="1y")
        
        # Helper function to safely convert to float
        def safe_float(value):
            """Convert value to float, return None if not possible."""
            if value is None:
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        
        # Create FactorMetrics object
        metrics = FactorMetrics(
            symbol=symbol,
            name=info.get('longName', symbol),
            sector=info.get('sector', 'Unknown'),
            market_cap=safe_float(info.get('marketCap')),
            last_updated=datetime.now(),
        )
        
        # Extract value factors with type conversion
        metrics.pe_ratio = safe_float(info.get('trailingPE'))
        metrics.pb_ratio = safe_float(info.get('priceToBook'))
        metrics.ps_ratio = safe_float(info.get('priceToSalesTrailing12Months'))
        metrics.dividend_yield = safe_float(info.get('dividendYield'))
        
        # Extract growth factors with type conversion
        metrics.earnings_growth = safe_float(info.get('earningsGrowth'))
        metrics.revenue_growth = safe_float(info.get('revenueGrowth'))
        metrics.eps_growth = safe_float(info.get('earningsQuarterlyGrowth'))
        
        # Calculate momentum factors
        if not hist.empty and len(hist) > 0:
            current_price = hist['Close'].iloc[-1]
            
            if len(hist) >= 21:  # 1 month
                metrics.return_1m = (current_price / hist['Close'].iloc[-21] - 1) * 100
            
            if len(hist) >= 63:  # 3 months
                metrics.return_3m = (current_price / hist['Close'].iloc[-63] - 1) * 100
            
            if len(hist) >= 126:  # 6 months
                metrics.return_6m = (current_price / hist['Close'].iloc[-126] - 1) * 100
            
            if len(hist) >= 252:  # 12 months
                metrics.return_12m = (current_price / hist['Close'].iloc[-252] - 1) * 100
        
        # Extract quality factors with type conversion
        metrics.roe = safe_float(info.get('returnOnEquity'))
        metrics.roa = safe_float(info.get('returnOnAssets'))
        metrics.debt_to_equity = safe_float(info.get('debtToEquity'))
        metrics.current_ratio = safe_float(info.get('currentRatio'))
        metrics.profit_margin = safe_float(info.get('profitMargins'))
        
        # Count available metrics
        metrics.value_metrics_available = sum([
            metrics.pe_ratio is not None,
            metrics.pb_ratio is not None,
            metrics.ps_ratio is not None,
            metrics.dividend_yield is not None,
        ])
        
        metrics.growth_metrics_available = sum([
            metrics.earnings_growth is not None,
            metrics.revenue_growth is not None,
            metrics.eps_growth is not None,
        ])
        
        metrics.momentum_metrics_available = sum([
            metrics.return_1m is not None,
            metrics.return_3m is not None,
            metrics.return_6m is not None,
            metrics.return_12m is not None,
        ])
        
        metrics.quality_metrics_available = sum([
            metrics.roe is not None,
            metrics.roa is not None,
            metrics.debt_to_equity is not None,
            metrics.current_ratio is not None,
            metrics.profit_margin is not None,
        ])
        
        # Calculate factor scores
        metrics.value_score = _calculate_value_score(metrics)
        metrics.growth_score = _calculate_growth_score(metrics)
        metrics.momentum_score = _calculate_momentum_score(metrics)
        metrics.quality_score = _calculate_quality_score(metrics)
        
        # Update data quality
        metrics.update_data_quality()
        
        # Cache the results
        if use_cache:
            _save_to_cache(symbol, _factor_metrics_to_dict(metrics))
            _clear_old_cache()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error fetching factor data for {symbol}: {e}")
        # Return empty metrics with error indicator
        metrics = FactorMetrics(
            symbol=symbol,
            name=symbol,
            data_quality=DataQuality.UNAVAILABLE,
        )
        return metrics


def _factor_metrics_to_dict(metrics: FactorMetrics) -> Dict[str, Any]:
    """Convert FactorMetrics to dictionary for caching."""
    return {
        'symbol': metrics.symbol,
        'name': metrics.name,
        'pe_ratio': metrics.pe_ratio,
        'pb_ratio': metrics.pb_ratio,
        'ps_ratio': metrics.ps_ratio,
        'dividend_yield': metrics.dividend_yield,
        'value_score': metrics.value_score,
        'earnings_growth': metrics.earnings_growth,
        'revenue_growth': metrics.revenue_growth,
        'eps_growth': metrics.eps_growth,
        'growth_score': metrics.growth_score,
        'return_1m': metrics.return_1m,
        'return_3m': metrics.return_3m,
        'return_6m': metrics.return_6m,
        'return_12m': metrics.return_12m,
        'momentum_score': metrics.momentum_score,
        'roe': metrics.roe,
        'roa': metrics.roa,
        'debt_to_equity': metrics.debt_to_equity,
        'current_ratio': metrics.current_ratio,
        'profit_margin': metrics.profit_margin,
        'quality_score': metrics.quality_score,
        'market_cap': metrics.market_cap,
        'sector': metrics.sector,
        'asset_class': metrics.asset_class,
        'data_quality': metrics.data_quality.value,
        'last_updated': metrics.last_updated.isoformat() if metrics.last_updated else None,
        'value_metrics_available': metrics.value_metrics_available,
        'growth_metrics_available': metrics.growth_metrics_available,
        'momentum_metrics_available': metrics.momentum_metrics_available,
        'quality_metrics_available': metrics.quality_metrics_available,
    }


def _dict_to_factor_metrics(data: Dict[str, Any]) -> FactorMetrics:
    """Convert dictionary to FactorMetrics object."""
    return FactorMetrics(
        symbol=data['symbol'],
        name=data['name'],
        pe_ratio=data.get('pe_ratio'),
        pb_ratio=data.get('pb_ratio'),
        ps_ratio=data.get('ps_ratio'),
        dividend_yield=data.get('dividend_yield'),
        value_score=data.get('value_score', 50.0),
        earnings_growth=data.get('earnings_growth'),
        revenue_growth=data.get('revenue_growth'),
        eps_growth=data.get('eps_growth'),
        growth_score=data.get('growth_score', 50.0),
        return_1m=data.get('return_1m'),
        return_3m=data.get('return_3m'),
        return_6m=data.get('return_6m'),
        return_12m=data.get('return_12m'),
        momentum_score=data.get('momentum_score', 50.0),
        roe=data.get('roe'),
        roa=data.get('roa'),
        debt_to_equity=data.get('debt_to_equity'),
        current_ratio=data.get('current_ratio'),
        profit_margin=data.get('profit_margin'),
        quality_score=data.get('quality_score', 50.0),
        market_cap=data.get('market_cap'),
        sector=data.get('sector', 'Unknown'),
        asset_class=data.get('asset_class', 'Stocks'),
        data_quality=DataQuality(data.get('data_quality', 'unavailable')),
        last_updated=datetime.fromisoformat(data['last_updated']) if data.get('last_updated') else None,
        value_metrics_available=data.get('value_metrics_available', 0),
        growth_metrics_available=data.get('growth_metrics_available', 0),
        momentum_metrics_available=data.get('momentum_metrics_available', 0),
        quality_metrics_available=data.get('quality_metrics_available', 0),
    )


def calculate_portfolio_factor_exposure(
    portfolio_df: pd.DataFrame,
    factor_data: Dict[str, FactorMetrics],
    benchmark_name: str = "S&P 500",
) -> PortfolioFactorExposure:
    """
    Calculate portfolio-level factor exposure.
    
    Args:
        portfolio_df: DataFrame with portfolio holdings (must have 'symbol' and 'market_value' columns)
        factor_data: Dictionary mapping symbols to FactorMetrics
        benchmark_name: Name of benchmark for comparison
    
    Returns:
        PortfolioFactorExposure with weighted factor scores and analysis
    
    Algorithm:
    1. Calculate portfolio weights for each holding
    2. Weight each security's factor scores by portfolio weight
    3. Calculate weighted average for each factor
    4. Compare to benchmark to determine tilts
    5. Classify portfolio style
    6. Identify top holdings in each factor category
    7. Calculate factor concentration
    """
    if portfolio_df.empty:
        logger.warning("Empty portfolio DataFrame provided")
        return PortfolioFactorExposure()
    
    # Validate required columns
    required_cols = ['symbol', 'market_value']
    missing_cols = [col for col in required_cols if col not in portfolio_df.columns]
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}")
        return PortfolioFactorExposure()
    
    # Calculate total portfolio value
    total_value = portfolio_df['market_value'].sum()
    if total_value == 0:
        logger.warning("Portfolio has zero total value")
        return PortfolioFactorExposure()
    
    # Calculate weights
    portfolio_df = portfolio_df.copy()
    portfolio_df['weight'] = portfolio_df['market_value'] / total_value
    
    # Initialize weighted scores
    weighted_value = 0.0
    weighted_growth = 0.0
    weighted_momentum = 0.0
    weighted_quality = 0.0
    
    analyzed_value = 0.0
    analyzed_count = 0
    
    # Lists for top holdings by factor
    value_holdings = []
    growth_holdings = []
    momentum_holdings = []
    quality_holdings = []
    
    # Calculate weighted factor scores
    for _, row in portfolio_df.iterrows():
        symbol = row['symbol']
        weight = row['weight']
        
        # Get factor data for this security
        if symbol not in factor_data:
            logger.debug(f"No factor data for {symbol}, skipping")
            continue
        
        metrics = factor_data[symbol]
        
        # Skip if data quality is unavailable
        if metrics.data_quality == DataQuality.UNAVAILABLE:
            continue
        
        # Add to weighted scores
        weighted_value += metrics.value_score * weight
        weighted_growth += metrics.growth_score * weight
        weighted_momentum += metrics.momentum_score * weight
        weighted_quality += metrics.quality_score * weight
        
        analyzed_value += row['market_value']
        analyzed_count += 1
        
        # Add to factor holdings lists
        value_holdings.append((symbol, weight, metrics.value_score))
        growth_holdings.append((symbol, weight, metrics.growth_score))
        momentum_holdings.append((symbol, weight, metrics.momentum_score))
        quality_holdings.append((symbol, weight, metrics.quality_score))
    
    if analyzed_count == 0:
        logger.warning("No securities with factor data found")
        return PortfolioFactorExposure()
    
    # Sort holdings by score (descending) and take top 10
    value_holdings.sort(key=lambda x: x[2], reverse=True)
    growth_holdings.sort(key=lambda x: x[2], reverse=True)
    momentum_holdings.sort(key=lambda x: x[2], reverse=True)
    quality_holdings.sort(key=lambda x: x[2], reverse=True)
    
    value_holdings = value_holdings[:10]
    growth_holdings = growth_holdings[:10]
    momentum_holdings = momentum_holdings[:10]
    quality_holdings = quality_holdings[:10]
    
    # Calculate factor tilts vs benchmark
    value_tilt = weighted_value - BENCHMARK_FACTORS['value']
    growth_tilt = weighted_growth - BENCHMARK_FACTORS['growth']
    momentum_tilt = weighted_momentum - BENCHMARK_FACTORS['momentum']
    quality_tilt = weighted_quality - BENCHMARK_FACTORS['quality']
    
    # Classify portfolio style
    primary_style, secondary_style, style_purity = classify_portfolio_style(
        weighted_value,
        weighted_growth,
        weighted_momentum,
        weighted_quality,
    )
    
    # Calculate factor concentration for each factor
    value_concentration = calculate_factor_concentration(value_holdings)
    growth_concentration = calculate_factor_concentration(growth_holdings)
    momentum_concentration = calculate_factor_concentration(momentum_holdings)
    quality_concentration = calculate_factor_concentration(quality_holdings)
    
    # Average concentration across factors
    avg_concentration = (
        value_concentration + growth_concentration +
        momentum_concentration + quality_concentration
    ) / 4.0
    
    # Calculate factor correlation matrix
    factor_scores_df = pd.DataFrame({
        'value': [m.value_score for m in factor_data.values() if m.data_quality != DataQuality.UNAVAILABLE],
        'growth': [m.growth_score for m in factor_data.values() if m.data_quality != DataQuality.UNAVAILABLE],
        'momentum': [m.momentum_score for m in factor_data.values() if m.data_quality != DataQuality.UNAVAILABLE],
        'quality': [m.quality_score for m in factor_data.values() if m.data_quality != DataQuality.UNAVAILABLE],
    })
    
    factor_correlation = factor_scores_df.corr() if len(factor_scores_df) > 1 else None
    
    # Create exposure object
    exposure = PortfolioFactorExposure(
        value_exposure=weighted_value,
        growth_exposure=weighted_growth,
        momentum_exposure=weighted_momentum,
        quality_exposure=weighted_quality,
        value_tilt=value_tilt,
        growth_tilt=growth_tilt,
        momentum_tilt=momentum_tilt,
        quality_tilt=quality_tilt,
        primary_style=primary_style,
        secondary_style=secondary_style,
        style_purity=style_purity,
        value_holdings=value_holdings,
        growth_holdings=growth_holdings,
        momentum_holdings=momentum_holdings,
        quality_holdings=quality_holdings,
        factor_concentration=avg_concentration,
        factor_correlation=factor_correlation,
        total_holdings=len(portfolio_df),
        analyzed_holdings=analyzed_count,
        total_market_value=total_value,
        coverage_pct=(analyzed_value / total_value) * 100,
        analysis_date=datetime.now(),
        benchmark_name=benchmark_name,
    )
    
    logger.info(f"Portfolio factor analysis complete: {analyzed_count}/{len(portfolio_df)} holdings analyzed")
    logger.info(f"Style: {primary_style.value}, Purity: {style_purity:.1f}%")
    logger.info(f"Factor exposures - V:{weighted_value:.1f} G:{weighted_growth:.1f} M:{weighted_momentum:.1f} Q:{weighted_quality:.1f}")
    
    return exposure


def analyze_factor_drift(
    current_exposure: PortfolioFactorExposure,
    target_exposure: Optional[PortfolioFactorExposure] = None,
    historical_exposures: Optional[List[PortfolioFactorExposure]] = None,
) -> FactorDrift:
    """
    Analyze factor drift over time.
    
    TODO: Implement in Phase 5
    """
    logger.warning("analyze_factor_drift not yet implemented")
    return FactorDrift(current_exposure=current_exposure)


def perform_factor_attribution(
    portfolio_returns: pd.Series,
    factor_exposures: pd.DataFrame,
    benchmark_returns: pd.Series,
) -> FactorAttribution:
    """
    Perform factor-based performance attribution.
    
    TODO: Implement in Phase 5
    """
    logger.warning("perform_factor_attribution not yet implemented")
    return FactorAttribution()


# Made with Bob