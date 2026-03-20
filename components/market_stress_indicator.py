"""
components/market_stress_indicator.py
======================================
EventHorizonIQ Stress Indicator Component

Displays real-time market stress levels and provides actionable recommendations
based on the EventHorizonIQ Stress Index API.

Stress Levels:
- 0-50: Normal conditions
- 50-70: Review portfolio (flag for review)
- 70+: Activate hedges (defensive action required)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
import streamlit as st

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STRESS_API_URL = "https://eventhorizoniq.com/api/stress-index"
STRESS_REVIEW_THRESHOLD = 50
STRESS_HEDGE_THRESHOLD = 70
CACHE_TTL_MINUTES = 15

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class StressIndicatorData:
    """Market stress indicator data from EventHorizonIQ."""
    stress_index: float
    regime: str
    sensor_count: int
    breakdown: dict[str, int]
    as_of: str
    methodology: str
    fetch_time: datetime


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

_stress_cache: Optional[tuple[StressIndicatorData, datetime]] = None


def _get_cached_stress() -> Optional[StressIndicatorData]:
    """Get cached stress data if still valid."""
    global _stress_cache
    if _stress_cache is None:
        return None
    
    data, cache_time = _stress_cache
    cache_age = datetime.now() - cache_time
    
    if cache_age.total_seconds() / 60 < CACHE_TTL_MINUTES:
        logger.debug(f"Using cached stress data (age: {cache_age})")
        return data
    
    return None


def _cache_stress(data: StressIndicatorData) -> None:
    """Cache stress data with timestamp."""
    global _stress_cache
    _stress_cache = (data, datetime.now())


# ---------------------------------------------------------------------------
# API Fetching
# ---------------------------------------------------------------------------

def fetch_stress_indicator() -> Optional[StressIndicatorData]:
    """
    Fetch current market stress indicator from EventHorizonIQ API.
    
    Returns:
        StressIndicatorData if successful, None if fetch fails
    """
    # Check cache first
    cached = _get_cached_stress()
    if cached is not None:
        return cached
    
    try:
        response = requests.get(STRESS_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        stress_data = StressIndicatorData(
            stress_index=float(data['stress_index']),
            regime=data['regime'],
            sensor_count=int(data['sensor_count']),
            breakdown=data['breakdown'],
            as_of=data['as_of'],
            methodology=data['methodology'],
            fetch_time=datetime.now()
        )
        
        # Cache the result
        _cache_stress(stress_data)
        
        logger.info(f"Stress indicator fetched: {stress_data.stress_index}/100 ({stress_data.regime})")
        return stress_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching stress indicator: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing stress indicator response: {e}")
        return None


# ---------------------------------------------------------------------------
# UI Rendering
# ---------------------------------------------------------------------------

def get_stress_level_info(stress_index: float) -> tuple[str, str, str, str]:
    """
    Get display information based on stress level.
    
    Args:
        stress_index: Stress index value (0-100)
        
    Returns:
        Tuple of (emoji, color, status, recommendation)
    """
    if stress_index >= STRESS_HEDGE_THRESHOLD:
        return "🔴", "#ff4b4b", "CRITICAL", "Activate hedges immediately"
    elif stress_index >= STRESS_REVIEW_THRESHOLD:
        return "🟡", "#ffa500", "WARNING", "Flag portfolio for review"
    else:
        return "🟢", "#21c354", "NORMAL", "Continue normal operations"


def render_stress_indicator_card() -> None:
    """
    Render the EventHorizonIQ Stress Indicator card.
    
    Displays current market stress level with actionable recommendations.
    """
    st.caption("Real-time market stress monitoring powered by EventHorizonIQ")
    
    # Fetch stress data
    stress_data = fetch_stress_indicator()
    
    if stress_data is None:
        st.error("⚠️ Unable to fetch market stress data. Please try again later.")
        return
    
    # Get display info
    emoji, color, status, recommendation = get_stress_level_info(stress_data.stress_index)
    
    # Main metrics display
    col1, col2, col3 = st.columns([2, 2, 3])
    
    with col1:
        st.markdown(
            f'<div style="text-align: center; padding: 20px; background-color: {color}20; '
            f'border-radius: 10px; border: 2px solid {color};">'
            f'<div style="font-size: 36px;font-weight: bold; color: {color}">{emoji}  {stress_data.stress_index:.1f}</div>'
            f'<div style="font-size: 14px; color: #666;">Stress Index</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            f'<div style="padding: 20px; background-color: #f0f2f6; border-radius: 10px;">'
            f'<div style="font-size: 18px; font-weight: bold; color: {color};">{status}</div>'
            f'<div style="font-size: 14px; color: #666; margin-top: 5px;">Regime: {stress_data.regime}</div>'
            f'<div style="font-size: 12px; color: #999; margin-top: 10px;">'
            f'{stress_data.sensor_count} sensors active</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            f'<div style="padding: 20px; background-color: #f0f2f6; border-radius: 10px;">'
            f'<div style="font-size: 18px; font-weight: bold; margin-bottom: 10px;">📋 Action Required:</div>'
            f'<div style="font-size: 14px; color: {color}; font-weight: bold;">{recommendation}</div>'
            f'<div style="font-size: 12px; color: #999; margin-top: 10px;">'
            f'See Recommended action below</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    if stress_data.stress_index >= STRESS_HEDGE_THRESHOLD:
           st.error(
               f"🔴 **CRITICAL STRESS LEVEL ({stress_data.stress_index:.1f}/100)**\n\n"
               "**Immediate Actions:**\n"
               "- ✅ Activate portfolio hedges (put options, inverse ETFs)\n"
               "- ✅ Reduce equity exposure to defensive levels\n"
               "- ✅ Increase cash/bond allocation\n"
               "- ✅ Review stop-loss orders on volatile positions\n"
               "- ✅ Consider tax-loss harvesting opportunities\n\n"
               "**Monitor:** Check stress indicator daily until it drops below 70"
           )
    elif stress_data.stress_index >= STRESS_REVIEW_THRESHOLD:
            st.warning(
               f"🟡 **ELEVATED STRESS LEVEL ({stress_data.stress_index:.1f}/100)**\n\n"
               "**Review Actions:**\n"
               "- 📋 Review portfolio allocation and risk exposure\n"
               "- 📋 Prepare hedge strategies (identify put options, inverse positions)\n"
               "- 📋 Assess cash reserves and liquidity needs\n"
               "- 📋 Review rebalancing opportunities\n"
               "- 📋 Monitor daily for further deterioration\n\n"
               "**Threshold:** Activate hedges if stress crosses 70"
        )
    else:
            st.success(
                f"🟢 **NORMAL MARKET CONDITIONS ({stress_data.stress_index:.1f}/100)**\n\n"
                "**Routine Actions:**\n"
                "- ✅ Continue normal investment strategy\n"
                "- ✅ Execute planned rebalancing\n"
                "- ✅ Consider opportunistic buying\n"
                "- ✅ Review weekly for changes\n\n"
                "**Monitoring:** Check stress indicator weekly"
           )    
    
    # Detailed breakdown
    with st.expander("📊 Detailed Sensor Breakdown", expanded=False):
        breakdown = stress_data.breakdown
        
        st.markdown("**Sensor Status Distribution:**")
        
        # Create columns for breakdown
        bd_col1, bd_col2, bd_col3, bd_col4, bd_col5 = st.columns(5)
        
        with bd_col1:
            st.metric("🔴 Severe", breakdown.get('severe', 0))
        with bd_col2:
            st.metric("🟠 Elevated", breakdown.get('elevated', 0))
        with bd_col3:
            st.metric("🟡 Rising", breakdown.get('rising', 0))
        with bd_col4:
            st.metric("⚪ Neutral", breakdown.get('neutral', 0))
        with bd_col5:
            st.metric("🟢 Stable", breakdown.get('stable', 0))
        
        st.markdown("---")
        st.markdown(f"**Methodology:** {stress_data.methodology}")
        st.caption(f"Data as of: {stress_data.as_of}")
    
    # Actionable recommendations based on stress level


    
    # Stress level thresholds reference
    with st.expander("ℹ️ Understanding Stress Levels", expanded=False):
        st.markdown(
            "**Stress Index Interpretation:**\n\n"
            "- **0-50 (Normal):** 🟢 Market conditions are stable. Continue normal operations.\n"
            "- **50-70 (Warning):** 🟡 Elevated stress detected. Flag portfolio for review and prepare defensive strategies.\n"
            "- **70-100 (Critical):** 🔴 High stress conditions. Activate hedges and reduce risk exposure.\n\n"
            "**About EventHorizonIQ:**\n\n"
            "The Stress Index aggregates signals from 55+ market sensors monitoring volatility, "
            "credit spreads, liquidity, sentiment, and technical indicators. It provides early warning "
            "of market stress before major corrections occur."
        )


# Made with Bob