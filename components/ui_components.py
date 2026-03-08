"""
components/ui_components.py
===========================
Reusable UI components with consistent styling, loading states, and error handling.

Provides high-level components that can be used across all pages for a unified UX.
"""
from __future__ import annotations

from typing import Any, Callable, Literal, Optional
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from components.theme import (
    Colors,
    Typography,
    Spacing,
    BorderRadius,
    ComponentStyles,
    get_status_color,
    get_status_label,
    format_percentage,
    format_delta,
)


# ---------------------------------------------------------------------------
# Loading States
# ---------------------------------------------------------------------------
class LoadingState:
    """Context manager for loading states with spinners."""
    
    def __init__(self, message: str = "Loading...", icon: str = "⏳"):
        self.message = message
        self.icon = icon
        self.spinner = None
    
    def __enter__(self):
        self.spinner = st.spinner(f"{self.icon} {self.message}")
        self.spinner.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.spinner:
            self.spinner.__exit__(exc_type, exc_val, exc_tb)


def with_loading_state(
    func: Callable,
    message: str = "Loading...",
    icon: str = "⏳",
    error_message: str = "An error occurred",
) -> Any:
    """
    Execute a function with loading state and error handling.
    
    Args:
        func: Function to execute
        message: Loading message to display
        icon: Icon to show during loading
        error_message: Message to show on error
    
    Returns:
        Result of func() or None on error
    """
    try:
        with LoadingState(message, icon):
            return func()
    except Exception as e:
        st.error(f"{error_message}: {str(e)}")
        return None


# ---------------------------------------------------------------------------
# Alert Components
# ---------------------------------------------------------------------------
def show_alert(
    message: str,
    alert_type: Literal["success", "warning", "error", "info"] = "info",
    icon: Optional[str] = None,
    dismissible: bool = False,
) -> None:
    """
    Display a styled alert box.
    
    Args:
        message: Alert message
        alert_type: Type of alert (success, warning, error, info)
        icon: Optional icon to display
        dismissible: Whether alert can be dismissed
    """
    icon_map = {
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "info": "ℹ️",
    }
    
    display_icon = icon or icon_map.get(alert_type, "")
    full_message = f"{display_icon} {message}" if display_icon else message
    
    style = ComponentStyles.alert(alert_type)
    
    if dismissible:
        with st.expander(full_message, expanded=True):
            st.markdown(
                f'<div style="{style}">{message}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f'<div style="{style}">{full_message}</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Metric Cards
# ---------------------------------------------------------------------------
def metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: Literal["normal", "inverse", "off"] = "normal",
    help_text: Optional[str] = None,
    icon: Optional[str] = None,
) -> None:
    """
    Display a metric card with consistent styling.
    
    Args:
        label: Metric label
        value: Metric value
        delta: Optional delta value
        delta_color: Color scheme for delta
        help_text: Optional help text
        icon: Optional icon
    """
    st.metric(
        label=f"{icon} {label}" if icon else label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help_text,
    )


def metric_card_grid(
    metrics: list[dict[str, Any]],
    columns: int = 4,
) -> None:
    """
    Display a grid of metric cards.
    
    Args:
        metrics: List of metric dictionaries with keys: label, value, delta, help, icon
        columns: Number of columns in the grid
    """
    cols = st.columns(columns)
    for idx, metric in enumerate(metrics):
        with cols[idx % columns]:
            metric_card(
                label=metric.get("label", ""),
                value=metric.get("value", ""),
                delta=metric.get("delta"),
                delta_color=metric.get("delta_color", "normal"),
                help_text=metric.get("help"),
                icon=metric.get("icon"),
            )


# ---------------------------------------------------------------------------
# Progress Indicators
# ---------------------------------------------------------------------------
def progress_indicator(
    label: str,
    value: float,
    max_value: float = 100.0,
    show_percentage: bool = True,
    color: Optional[str] = None,
    height: str = "8px",
) -> None:
    """
    Display a progress bar with label.
    
    Args:
        label: Progress label
        value: Current value
        max_value: Maximum value
        show_percentage: Whether to show percentage
        color: Optional custom color
        height: Bar height
    """
    percentage = (value / max_value * 100) if max_value > 0 else 0
    percentage = min(percentage, 100)
    
    if color is None:
        color = get_status_color(percentage)
    
    styles = ComponentStyles.progress_bar(height=height, fill_color=color)
    
    label_html = f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:{Spacing.XS};">'
    label_html += f'<span style="font-size:{Typography.SIZE_SM};font-weight:{Typography.WEIGHT_SEMIBOLD};">{label}</span>'
    
    if show_percentage:
        label_html += f'<span style="font-size:{Typography.SIZE_SM};color:{color};font-weight:{Typography.WEIGHT_BOLD};">{percentage:.0f}%</span>'
    
    label_html += '</div>'
    
    bar_html = f'<div style="{styles["container"]}">'
    bar_html += f'<div style="{styles["fill"]}width:{percentage}%;"></div>'
    bar_html += '</div>'
    
    st.markdown(label_html + bar_html, unsafe_allow_html=True)


def score_gauge(
    label: str,
    score: float,
    detail: str = "",
    thresholds: tuple[float, float] = (50, 75),
) -> None:
    """
    Display a score with progress bar and status.
    
    Args:
        label: Score label
        score: Score value (0-100)
        detail: Additional detail text
        thresholds: Tuple of (warning_threshold, success_threshold)
    """
    color = get_status_color(score, thresholds)
    
    st.markdown(
        f'<div style="margin-bottom:{Spacing.SM};">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:{Typography.SIZE_SM};font-weight:{Typography.WEIGHT_SEMIBOLD};">{label}</span>'
        f'<span style="font-size:{Typography.SIZE_SM};color:{color};font-weight:{Typography.WEIGHT_BOLD};">{score:.0f}%</span>'
        f'</div>'
        f'<div style="background:#e9ecef;border-radius:{BorderRadius.SM};height:8px;margin:{Spacing.XS} 0;">'
        f'<div style="background:{color};width:{score:.0f}%;height:8px;border-radius:{BorderRadius.SM};"></div>'
        f'</div>'
        f'<div style="font-size:{Typography.SIZE_XS};color:{Colors.TEXT_SECONDARY};">{detail}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Status Badges
# ---------------------------------------------------------------------------
def status_badge(
    text: str,
    status: Literal["success", "warning", "error", "info", "neutral"] = "neutral",
) -> str:
    """
    Generate HTML for a status badge.
    
    Args:
        text: Badge text
        status: Badge status type
    
    Returns:
        HTML string for the badge
    """
    color_map = {
        "success": Colors.SUCCESS,
        "warning": Colors.WARNING,
        "error": Colors.ERROR,
        "info": Colors.INFO,
        "neutral": Colors.TEXT_SECONDARY,
    }
    
    bg_color = color_map.get(status, Colors.TEXT_SECONDARY)
    style = ComponentStyles.badge(background=bg_color)
    
    return f'<span style="{style}">{text}</span>'


# ---------------------------------------------------------------------------
# Info Cards
# ---------------------------------------------------------------------------
def info_card(
    title: str,
    content: str,
    icon: Optional[str] = None,
    color: str = Colors.INFO,
) -> None:
    """
    Display an information card.
    
    Args:
        title: Card title
        content: Card content
        icon: Optional icon
        color: Accent color
    """
    title_html = f"{icon} {title}" if icon else title
    
    st.markdown(
        f'<div style="{ComponentStyles.card()}">'
        f'<div style="border-left:4px solid {color};padding-left:{Spacing.MD};">'
        f'<h4 style="margin:0 0 {Spacing.SM} 0;color:{Colors.TEXT_PRIMARY};">{title_html}</h4>'
        f'<p style="margin:0;color:{Colors.TEXT_SECONDARY};font-size:{Typography.SIZE_SM};">{content}</p>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Section Headers
# ---------------------------------------------------------------------------
def section_header(
    title: str,
    subtitle: Optional[str] = None,
    icon: Optional[str] = None,
    divider: bool = True,
) -> None:
    """
    Display a consistent section header.
    
    Args:
        title: Section title
        subtitle: Optional subtitle
        icon: Optional icon
        divider: Whether to show divider below
    """
    title_html = f"{icon} {title}" if icon else title
    st.markdown(f"### {title_html}")
    
    if subtitle:
        st.caption(subtitle)
    
    if divider:
        st.markdown("---")


# ---------------------------------------------------------------------------
# Data Tables
# ---------------------------------------------------------------------------
def styled_dataframe(
    df: pd.DataFrame,
    column_config: Optional[dict] = None,
    hide_index: bool = True,
    height: Optional[int] = None,
) -> None:
    """
    Display a styled dataframe with consistent formatting.
    
    Args:
        df: DataFrame to display
        column_config: Column configuration
        hide_index: Whether to hide the index
        height: Optional fixed height
    """
    if df.empty:
        show_alert("No data available", "info", "📊")
        return
    
    kwargs = {
        "column_config": column_config,
        "hide_index": hide_index,
        "use_container_width": True,
    }
    if height is not None:
        kwargs["height"] = height
    
    st.dataframe(df, **kwargs)


# ---------------------------------------------------------------------------
# Empty States
# ---------------------------------------------------------------------------
def empty_state(
    message: str,
    icon: str = "📭",
    action_label: Optional[str] = None,
    action_callback: Optional[Callable] = None,
) -> None:
    """
    Display an empty state with optional action.
    
    Args:
        message: Empty state message
        icon: Icon to display
        action_label: Optional action button label
        action_callback: Optional action button callback
    """
    st.markdown(
        f'<div style="text-align:center;padding:{Spacing.XXL} {Spacing.LG};">'
        f'<div style="font-size:48px;margin-bottom:{Spacing.MD};">{icon}</div>'
        f'<p style="color:{Colors.TEXT_SECONDARY};font-size:{Typography.SIZE_LG};">{message}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
    
    if action_label and action_callback:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button(action_label, use_container_width=True):
                action_callback()


# ---------------------------------------------------------------------------
# Collapsible Sections
# ---------------------------------------------------------------------------
def collapsible_section(
    title: str,
    content_func: Callable,
    expanded: bool = False,
    icon: Optional[str] = None,
) -> None:
    """
    Create a collapsible section with consistent styling.
    
    Args:
        title: Section title
        content_func: Function that renders the content
        expanded: Whether section is expanded by default
        icon: Optional icon
    """
    title_html = f"{icon} {title}" if icon else title
    
    with st.expander(title_html, expanded=expanded):
        content_func()


# ---------------------------------------------------------------------------
# Action Lists
# ---------------------------------------------------------------------------
def action_list(
    actions: list[str],
    title: str = "Action Items",
    icon: str = "📋",
    expanded: bool = False,
) -> None:
    """
    Display a list of action items in an expander.
    
    Args:
        actions: List of action item strings
        title: List title
        icon: Icon to display
        expanded: Whether list is expanded by default
    """
    if not actions:
        return
    
    with st.expander(f"{icon} {len(actions)} {title}", expanded=expanded):
        for action in actions:
            st.markdown(f"- {action}")


# ---------------------------------------------------------------------------
# Comparison Cards
# ---------------------------------------------------------------------------
def comparison_card(
    label: str,
    current: float,
    target: float,
    format_func: Callable[[float], str] = lambda x: f"${x:,.0f}",
    show_progress: bool = True,
) -> None:
    """
    Display a comparison between current and target values.
    
    Args:
        label: Comparison label
        current: Current value
        target: Target value
        format_func: Function to format values
        show_progress: Whether to show progress bar
    """
    percentage = (current / target * 100) if target > 0 else 0
    gap = target - current
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label, format_func(current))
    with col2:
        st.metric("Target", format_func(target), delta=format_func(gap))
    
    if show_progress:
        progress_indicator(
            label=f"{label} Progress",
            value=current,
            max_value=target,
            show_percentage=True,
        )


# Made with Bob