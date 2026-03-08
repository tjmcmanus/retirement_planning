"""
components/theme.py
===================
Unified theme configuration and styling system for the Financial Planner application.

Provides consistent colors, typography, spacing, and component styles across all pages.
"""
from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Color Palette
# ---------------------------------------------------------------------------
class Colors:
    """Application color palette with semantic naming."""
    
    # Primary brand colors
    PRIMARY = "#F63366"
    PRIMARY_DARK = "#D12A56"
    PRIMARY_LIGHT = "#FF5C8A"
    
    # Semantic colors
    SUCCESS = "#21c354"
    WARNING = "#ffa500"
    ERROR = "#ff4b4b"
    INFO = "#4c78a8"
    
    # Neutral colors
    BACKGROUND = "#ffffff"
    SURFACE = "#f8f9fa"
    BORDER = "#dee2e6"
    TEXT_PRIMARY = "#1a1a2e"
    TEXT_SECONDARY = "#666666"
    TEXT_MUTED = "#999999"
    
    # Account type colors (with transparency)
    CASH = "rgba(246, 207, 113, 0.35)"
    CASH_ACCENT = "rgb(246, 207, 113)"
    BROKERAGE = "rgba(254, 136, 177, 0.35)"
    BROKERAGE_ACCENT = "rgb(254, 136, 177)"
    TRADITIONAL = "rgba(139, 224, 164, 0.35)"
    TRADITIONAL_ACCENT = "rgb(139, 224, 164)"
    ROTH = "rgba(180, 151, 231, 0.35)"
    ROTH_ACCENT = "rgb(180, 151, 231)"
    REAL_ESTATE = "rgba(255, 190, 122, 0.35)"
    REAL_ESTATE_ACCENT = "rgb(255, 190, 122)"
    
    # Chart colors
    CHART_PALETTE = [
        "rgb(246, 207, 113)",  # Yellow
        "rgb(254, 136, 177)",  # Pink
        "rgb(139, 224, 164)",  # Green
        "rgb(180, 151, 231)",  # Purple
        "rgb(255, 190, 122)",  # Orange
        "rgb(99, 110, 250)",   # Blue
        "rgb(239, 85, 59)",    # Red
        "rgb(0, 204, 150)",    # Teal
    ]
    
    CHART_SCALE = [
        [0.0, "rgb(246, 207, 113)"],   # Low
        [0.5, "rgb(180, 151, 231)"],   # Mid
        [1.0, "rgb(139, 224, 164)"],   # High
    ]


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
class Typography:
    """Typography scale and font families."""
    
    FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    FONT_FAMILY_MONO = "'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace"
    
    # Font sizes (in pixels)
    SIZE_XS = "11px"
    SIZE_SM = "13px"
    SIZE_BASE = "14px"
    SIZE_LG = "16px"
    SIZE_XL = "18px"
    SIZE_2XL = "24px"
    SIZE_3XL = "32px"
    
    # Font weights
    WEIGHT_NORMAL = "400"
    WEIGHT_MEDIUM = "500"
    WEIGHT_SEMIBOLD = "600"
    WEIGHT_BOLD = "700"


# ---------------------------------------------------------------------------
# Spacing
# ---------------------------------------------------------------------------
class Spacing:
    """Consistent spacing scale."""
    
    XS = "4px"
    SM = "8px"
    MD = "12px"
    LG = "16px"
    XL = "24px"
    XXL = "32px"
    XXXL = "48px"


# ---------------------------------------------------------------------------
# Border Radius
# ---------------------------------------------------------------------------
class BorderRadius:
    """Border radius scale."""
    
    SM = "4px"
    MD = "6px"
    LG = "8px"
    XL = "12px"
    FULL = "9999px"


# ---------------------------------------------------------------------------
# Shadows
# ---------------------------------------------------------------------------
class Shadows:
    """Box shadow definitions."""
    
    SM = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
    MD = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)"
    LG = "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)"
    XL = "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)"


# ---------------------------------------------------------------------------
# Component Styles
# ---------------------------------------------------------------------------
class ComponentStyles:
    """Pre-built component style definitions."""
    
    @staticmethod
    def card(
        background: str = Colors.SURFACE,
        border: str = Colors.BORDER,
        padding: str = Spacing.LG,
        radius: str = BorderRadius.MD,
        shadow: str = Shadows.SM,
    ) -> str:
        """Generate card container styles."""
        return (
            f"background: {background}; "
            f"border: 1px solid {border}; "
            f"border-radius: {radius}; "
            f"padding: {padding}; "
            f"box-shadow: {shadow};"
        )
    
    @staticmethod
    def metric_card(
        value_color: str = Colors.TEXT_PRIMARY,
        label_color: str = Colors.TEXT_SECONDARY,
    ) -> str:
        """Generate metric card styles."""
        return ComponentStyles.card() + (
            f"text-align: center; "
            f"--value-color: {value_color}; "
            f"--label-color: {label_color};"
        )
    
    @staticmethod
    def alert(
        alert_type: Literal["success", "warning", "error", "info"] = "info",
    ) -> str:
        """Generate alert box styles."""
        color_map = {
            "success": Colors.SUCCESS,
            "warning": Colors.WARNING,
            "error": Colors.ERROR,
            "info": Colors.INFO,
        }
        color = color_map[alert_type]
        return (
            f"background: {color}15; "
            f"border-left: 4px solid {color}; "
            f"border-radius: {BorderRadius.MD}; "
            f"padding: {Spacing.MD} {Spacing.LG}; "
            f"margin: {Spacing.MD} 0; "
            f"color: {Colors.TEXT_PRIMARY};"
        )
    
    @staticmethod
    def badge(
        background: str = Colors.PRIMARY,
        text_color: str = "#ffffff",
    ) -> str:
        """Generate badge styles."""
        return (
            f"display: inline-block; "
            f"background: {background}; "
            f"color: {text_color}; "
            f"padding: {Spacing.XS} {Spacing.SM}; "
            f"border-radius: {BorderRadius.FULL}; "
            f"font-size: {Typography.SIZE_XS}; "
            f"font-weight: {Typography.WEIGHT_SEMIBOLD}; "
            f"text-transform: uppercase; "
            f"letter-spacing: 0.05em;"
        )
    
    @staticmethod
    def progress_bar(
        height: str = "8px",
        background: str = "#e9ecef",
        fill_color: str = Colors.PRIMARY,
    ) -> dict[str, str]:
        """Generate progress bar styles (returns dict with container and fill)."""
        return {
            "container": (
                f"background: {background}; "
                f"border-radius: {BorderRadius.SM}; "
                f"height: {height}; "
                f"overflow: hidden;"
            ),
            "fill": (
                f"background: {fill_color}; "
                f"height: {height}; "
                f"border-radius: {BorderRadius.SM}; "
                f"transition: width 0.3s ease;"
            ),
        }
    
    @staticmethod
    def table_header() -> str:
        """Generate table header styles."""
        return (
            f"background: {Colors.TEXT_PRIMARY}; "
            f"color: white; "
            f"font-size: {Typography.SIZE_SM}; "
            f"text-transform: uppercase; "
            f"letter-spacing: 0.05em; "
            f"padding: {Spacing.SM} {Spacing.MD}; "
            f"font-weight: {Typography.WEIGHT_SEMIBOLD};"
        )
    
    @staticmethod
    def button(
        variant: Literal["primary", "secondary", "outline"] = "primary",
    ) -> str:
        """Generate button styles."""
        if variant == "primary":
            return (
                f"background: {Colors.PRIMARY}; "
                f"color: white; "
                f"border: none; "
                f"padding: {Spacing.SM} {Spacing.LG}; "
                f"border-radius: {BorderRadius.MD}; "
                f"font-weight: {Typography.WEIGHT_SEMIBOLD}; "
                f"cursor: pointer; "
                f"transition: background 0.2s ease;"
            )
        elif variant == "secondary":
            return (
                f"background: {Colors.SURFACE}; "
                f"color: {Colors.TEXT_PRIMARY}; "
                f"border: 1px solid {Colors.BORDER}; "
                f"padding: {Spacing.SM} {Spacing.LG}; "
                f"border-radius: {BorderRadius.MD}; "
                f"font-weight: {Typography.WEIGHT_SEMIBOLD}; "
                f"cursor: pointer; "
                f"transition: background 0.2s ease;"
            )
        else:  # outline
            return (
                f"background: transparent; "
                f"color: {Colors.PRIMARY}; "
                f"border: 2px solid {Colors.PRIMARY}; "
                f"padding: {Spacing.SM} {Spacing.LG}; "
                f"border-radius: {BorderRadius.MD}; "
                f"font-weight: {Typography.WEIGHT_SEMIBOLD}; "
                f"cursor: pointer; "
                f"transition: all 0.2s ease;"
            )


# ---------------------------------------------------------------------------
# Chart Configuration
# ---------------------------------------------------------------------------
class ChartConfig:
    """Consistent chart configuration."""
    
    @staticmethod
    def get_layout(
        title: str = "",
        height: int = 400,
        show_legend: bool = True,
    ) -> dict:
        """Get standard chart layout configuration."""
        return {
            "title": title,
            "height": height,
            "plot_bgcolor": "white",
            "paper_bgcolor": "white",
            "font": {
                "family": Typography.FONT_FAMILY,
                "size": 12,
                "color": Colors.TEXT_PRIMARY,
            },
            "showlegend": show_legend,
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
            "margin": {"t": 60, "l": 10, "r": 10, "b": 10},
            "xaxis": {
                "tickfont": {"color": Colors.TEXT_PRIMARY},
                "gridcolor": Colors.BORDER,
            },
            "yaxis": {
                "tickfont": {"color": Colors.TEXT_PRIMARY},
                "gridcolor": Colors.BORDER,
            },
        }
    
    @staticmethod
    def get_color_scale() -> list:
        """Get standard color scale for heatmaps."""
        return Colors.CHART_SCALE
    
    @staticmethod
    def get_palette() -> list[str]:
        """Get standard color palette for charts."""
        return Colors.CHART_PALETTE


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def get_status_color(score: float, thresholds: tuple[float, float] = (50, 75)) -> str:
    """
    Get color based on score and thresholds.
    
    Args:
        score: Numeric score (0-100)
        thresholds: Tuple of (warning_threshold, success_threshold)
    
    Returns:
        Color string (hex or rgb)
    """
    warning_threshold, success_threshold = thresholds
    if score >= success_threshold:
        return Colors.SUCCESS
    elif score >= warning_threshold:
        return Colors.WARNING
    else:
        return Colors.ERROR


def get_status_label(score: float, thresholds: tuple[float, float] = (50, 75)) -> str:
    """
    Get status label based on score and thresholds.
    
    Args:
        score: Numeric score (0-100)
        thresholds: Tuple of (warning_threshold, success_threshold)
    
    Returns:
        Status label with emoji
    """
    warning_threshold, success_threshold = thresholds
    if score >= success_threshold:
        return "🟢 On Track"
    elif score >= warning_threshold:
        return "🟡 Needs Attention"
    else:
        return "🔴 Action Required"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a value as a percentage."""
    return f"{value:.{decimals}f}%"


def format_delta(value: float, show_sign: bool = True) -> str:
    """Format a delta value with appropriate sign."""
    sign = "+" if value >= 0 and show_sign else ""
    return f"{sign}{value:,.0f}"


# Made with Bob