"""
components/visualizations/__init__.py
=====================================
Visualization components for enhanced dashboards and charts.
"""

from .dashboard_manager import DashboardLayout, Widget, GridConfig
from .widget_library import (
    KPIMetricWidget,
    ChartWidget,
    TableWidget,
    TextWidget,
    GoalProgressWidget,
    AlertWidget,
)
from .advanced_charts import (
    create_waterfall_chart,
    create_3d_surface_plot,
    create_animated_timeline,
    create_bar_chart_race,
)

__all__ = [
    # Dashboard Management
    "DashboardLayout",
    "Widget",
    "GridConfig",
    # Widgets
    "KPIMetricWidget",
    "ChartWidget",
    "TableWidget",
    "TextWidget",
    "GoalProgressWidget",
    "AlertWidget",
    # Advanced Charts
    "create_waterfall_chart",
    "create_3d_surface_plot",
    "create_animated_timeline",
    "create_bar_chart_race",
]

# Made with Bob
