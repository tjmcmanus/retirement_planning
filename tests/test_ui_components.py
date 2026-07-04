"""
test_ui_components.py
=====================
Standalone test application demonstrating the UI component system.

Run this file directly to see all available UI components and design options:
    streamlit run test_ui_components.py

This file showcases all the reusable components, loading states,
error handling, and styling features available in the application.
"""
from __future__ import annotations

import time
import streamlit as st
import pandas as pd
import numpy as np

from components.theme import (
    Colors,
    Typography,
    Spacing,
    ComponentStyles,
    get_status_color,
    get_status_label,
)
from components.ui_components import (
    LoadingState,
    with_loading_state,
    show_alert,
    metric_card,
    metric_card_grid,
    progress_indicator,
    score_gauge,
    status_badge,
    info_card,
    section_header,
    styled_dataframe,
    empty_state,
    collapsible_section,
    action_list,
    comparison_card,
)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="UI Component Test Suite",
    page_icon="🎨",
    layout="wide"
)

st.title("🎨 UI Component Test Suite")
st.caption("Comprehensive showcase of reusable components and design options")

st.info("""
**👋 Welcome to the UI Component Test Suite!**

This standalone app demonstrates all available UI components for the retirement planning application.
Use this as a reference when building new features or pages.

**To run this test app:**
```bash
streamlit run test_ui_components.py
```
""")

# ---------------------------------------------------------------------------
# Section 1: Alerts
# ---------------------------------------------------------------------------
section_header(
    title="Alert Components",
    subtitle="Different types of alerts for various scenarios",
    icon="🔔"
)

col1, col2 = st.columns(2)
with col1:
    show_alert("Operation completed successfully!", "success")
    show_alert("Please review your configuration", "warning", icon="⚠️")
with col2:
    show_alert("Failed to load data", "error")
    show_alert("Background refresh in progress", "info", dismissible=True)

# ---------------------------------------------------------------------------
# Section 2: Metric Cards
# ---------------------------------------------------------------------------
section_header(
    title="Metric Cards",
    subtitle="Display key performance indicators",
    icon="📊"
)

st.markdown("#### Single Metrics")
col1, col2, col3, col4 = st.columns(4)
with col1:
    metric_card("Net Worth", "$1,234,567", delta="+5.2%", icon="💰")
with col2:
    metric_card("Monthly Change", "$50,000", delta="+2.1%", icon="📈")
with col3:
    metric_card("YTD Gain", "$125,000", delta="+11.3%", icon="📆")
with col4:
    metric_card("Portfolio Return", "8.5%", delta="+1.5%", icon="🎯")

st.markdown("#### Metric Grid")
metrics = [
    {"label": "Cash", "value": "$100K", "icon": "💵", "help": "Cash balance"},
    {"label": "Taxable", "value": "$300K", "icon": "📊", "help": "Taxable accounts"},
    {"label": "Traditional", "value": "$500K", "icon": "🏦", "help": "Tax-deferred"},
    {"label": "Roth", "value": "$334K", "icon": "🌟", "help": "Tax-free"},
]
metric_card_grid(metrics, columns=4)

# ---------------------------------------------------------------------------
# Section 3: Progress Indicators
# ---------------------------------------------------------------------------
section_header(
    title="Progress Indicators",
    subtitle="Visual representation of progress and scores",
    icon="📈"
)

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Simple Progress Bar**")
    progress_indicator(
        label="Portfolio Funding",
        value=750000,
        max_value=1000000,
        show_percentage=True
    )
    
    progress_indicator(
        label="Emergency Fund",
        value=45000,
        max_value=50000,
        show_percentage=True,
        color=Colors.SUCCESS
    )

with col2:
    st.markdown("**Score Gauges**")
    score_gauge(
        label="💰 Portfolio Funding",
        score=75,
        detail="75% of 25x expenses target ($750K / $1M)",
        thresholds=(50, 75)
    )
    
    score_gauge(
        label="🔀 Tax Diversification",
        score=85,
        detail="Roth ratio 40% (target 30-50%)",
        thresholds=(50, 75)
    )

# ---------------------------------------------------------------------------
# Section 4: Status Badges
# ---------------------------------------------------------------------------
section_header(
    title="Status Badges",
    subtitle="Compact status indicators",
    icon="🏷️"
)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(status_badge("Success", "success"), unsafe_allow_html=True)
with col2:
    st.markdown(status_badge("Warning", "warning"), unsafe_allow_html=True)
with col3:
    st.markdown(status_badge("Error", "error"), unsafe_allow_html=True)
with col4:
    st.markdown(status_badge("Info", "info"), unsafe_allow_html=True)
with col5:
    st.markdown(status_badge("Neutral", "neutral"), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Section 5: Info Cards
# ---------------------------------------------------------------------------
section_header(
    title="Info Cards",
    subtitle="Highlighted information boxes",
    icon="💡"
)

col1, col2 = st.columns(2)
with col1:
    info_card(
        title="Portfolio Update",
        content="Your portfolio data is being refreshed in the background. This may take a few moments.",
        icon="📊",
        color=Colors.INFO
    )
with col2:
    info_card(
        title="Tax Season Reminder",
        content="Don't forget to review your tax-loss harvesting opportunities before year-end.",
        icon="📅",
        color=Colors.WARNING
    )

# ---------------------------------------------------------------------------
# Section 6: Data Tables
# ---------------------------------------------------------------------------
section_header(
    title="Data Tables",
    subtitle="Styled dataframes with consistent formatting",
    icon="📋"
)

# Sample data
sample_df = pd.DataFrame({
    "Account": ["Cash", "Brokerage", "Traditional 401k", "Roth IRA"],
    "Balance": [100000, 300000, 500000, 334000],
    "Change": [2.1, 5.3, 8.2, 9.1],
    "Status": ["✅ Good", "✅ Good", "⚠️ Review", "✅ Good"]
})

styled_dataframe(
    df=sample_df,
    column_config={
        "Balance": st.column_config.NumberColumn(format="$%d"),
        "Change": st.column_config.NumberColumn(format="%.1f%%"),
    }
)

# ---------------------------------------------------------------------------
# Section 7: Loading States
# ---------------------------------------------------------------------------
section_header(
    title="Loading States",
    subtitle="Demonstrate loading indicators and error handling",
    icon="⏳"
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Context Manager**")
    if st.button("Simulate Loading (Success)", key="load1"):
        with LoadingState("Loading data...", icon="📊"):
            time.sleep(2)
        show_alert("Data loaded successfully!", "success")

with col2:
    st.markdown("**Function Wrapper**")
    if st.button("Simulate Loading (Error)", key="load2"):
        def failing_operation():
            time.sleep(1)
            raise ValueError("Simulated error")
        
        result = with_loading_state(
            func=failing_operation,
            message="Processing...",
            icon="⚙️",
            error_message="Operation failed"
        )

# ---------------------------------------------------------------------------
# Section 8: Empty States
# ---------------------------------------------------------------------------
section_header(
    title="Empty States",
    subtitle="Graceful handling of missing data",
    icon="📭"
)

def mock_action():
    show_alert("Action button clicked!", "info")

empty_state(
    message="No portfolio data available for this period",
    icon="📭",
    action_label="Add Portfolio Data",
    action_callback=mock_action
)

# ---------------------------------------------------------------------------
# Section 9: Collapsible Sections
# ---------------------------------------------------------------------------
section_header(
    title="Collapsible Sections",
    subtitle="Organize content with expandable sections",
    icon="📂"
)

def render_advanced_details():
    st.write("This is advanced content that can be hidden by default.")
    st.code("""
    # Example code
    def calculate_returns(portfolio):
        return portfolio.sum() * 1.08
    """)

collapsible_section(
    title="Advanced Configuration",
    content_func=render_advanced_details,
    expanded=False,
    icon="🔧"
)

# ---------------------------------------------------------------------------
# Section 10: Action Lists
# ---------------------------------------------------------------------------
section_header(
    title="Action Lists",
    subtitle="Prioritized action items",
    icon="✅"
)

actions = [
    "💰 **Portfolio gap:** $250,000 below the 25x expenses target",
    "🔀 **Low Roth ratio:** Consider Roth conversions to reach 30-50% target",
    "🏥 **Healthcare not configured:** Add ACA premiums in Configuration",
    "📋 **Social Security incomplete:** Add SSI amounts for both persons"
]

action_list(
    actions=actions,
    title="Recommended Actions",
    icon="📋",
    expanded=True
)

# ---------------------------------------------------------------------------
# Section 11: Comparison Cards
# ---------------------------------------------------------------------------
section_header(
    title="Comparison Cards",
    subtitle="Compare current vs target values",
    icon="⚖️"
)

col1, col2 = st.columns(2)
with col1:
    comparison_card(
        label="Portfolio Value",
        current=750000,
        target=1000000,
        format_func=lambda x: f"${x:,.0f}",
        show_progress=True
    )

with col2:
    comparison_card(
        label="Emergency Fund",
        current=45000,
        target=50000,
        format_func=lambda x: f"${x:,.0f}",
        show_progress=True
    )

# ---------------------------------------------------------------------------
# Section 12: Theme Colors
# ---------------------------------------------------------------------------
section_header(
    title="Theme Colors",
    subtitle="Color palette reference",
    icon="🎨"
)

st.markdown("#### Primary Colors")
color_cols = st.columns(5)
colors = [
    ("Primary", Colors.PRIMARY),
    ("Success", Colors.SUCCESS),
    ("Warning", Colors.WARNING),
    ("Error", Colors.ERROR),
    ("Info", Colors.INFO),
]

for col, (name, color) in zip(color_cols, colors):
    with col:
        st.markdown(
            f'<div style="background:{color};color:white;padding:20px;'
            f'border-radius:8px;text-align:center;font-weight:600;">{name}</div>',
            unsafe_allow_html=True
        )
        st.caption(color)

st.markdown("#### Account Type Colors")
account_cols = st.columns(4)
account_colors = [
    ("Cash", Colors.CASH_ACCENT),
    ("Brokerage", Colors.BROKERAGE_ACCENT),
    ("Traditional", Colors.TRADITIONAL_ACCENT),
    ("Roth", Colors.ROTH_ACCENT),
]

for col, (name, color) in zip(account_cols, account_colors):
    with col:
        st.markdown(
            f'<div style="background:{color};color:white;padding:20px;'
            f'border-radius:8px;text-align:center;font-weight:600;">{name}</div>',
            unsafe_allow_html=True
        )
        st.caption(color)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    f'<div style="text-align:center;color:{Colors.TEXT_MUTED};'
    f'font-size:{Typography.SIZE_SM};">'
    f'UI Integration System v1.0.0 • See UI_INTEGRATION_GUIDE.md for documentation'
    f'</div>',
    unsafe_allow_html=True
)

# Made with Bob