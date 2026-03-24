"""
components/visualizations/widget_library.py
============================================
Reusable dashboard widget implementations.

Provides concrete widget classes that can be added to dashboards.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from components.shared import format_currency, COLOR_PALETTE
from components.theme import Colors, get_status_color, format_percentage, format_delta


# ---------------------------------------------------------------------------
# Base Widget Class
# ---------------------------------------------------------------------------

class BaseWidget(ABC):
    """Abstract base class for all widgets."""
    
    def __init__(self, widget_id: str, title: str, config: Dict[str, Any]):
        self.widget_id = widget_id
        self.title = title
        self.config = config
    
    @abstractmethod
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render the widget. Must be implemented by subclasses."""
        pass
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default."""
        return self.config.get(key, default)


# ---------------------------------------------------------------------------
# KPI Metric Widget
# ---------------------------------------------------------------------------

class KPIMetricWidget(BaseWidget):
    """Display a single KPI metric with optional trend."""
    
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render KPI metric widget."""
        metric_name = self.get_config_value("metric", "value")
        show_trend = self.get_config_value("show_trend", True)
        comparison_period = self.get_config_value("comparison_period", "month")
        
        if data is None:
            st.metric(
                label=self.title,
                value="No data",
                delta=None
            )
            return
        
        # Get metric value
        value = data.get(metric_name, 0)
        
        # Format value based on type
        if isinstance(value, (int, float)):
            if metric_name in ["net_worth", "portfolio_value", "mom_change", "ytd_change"]:
                formatted_value = format_currency(value)
            elif metric_name in ["ytd_return", "mom_pct"]:
                formatted_value = format_percentage(value)
            else:
                formatted_value = f"{value:,.0f}"
        else:
            formatted_value = str(value)
        
        # Get delta if showing trend
        delta = None
        delta_color = "normal"
        if show_trend and f"{metric_name}_delta" in data:
            delta_value = data[f"{metric_name}_delta"]
            if isinstance(delta_value, (int, float)):
                if metric_name in ["net_worth", "portfolio_value", "mom_change", "ytd_change"]:
                    delta = format_currency(delta_value)
                elif metric_name in ["ytd_return", "mom_pct"]:
                    delta = format_percentage(delta_value)
                else:
                    delta = f"{delta_value:+,.0f}"
                
                # Determine delta color
                delta_color = "normal" if delta_value >= 0 else "inverse"
        
        st.metric(
            label=self.title,
            value=formatted_value,
            delta=delta,
            delta_color=delta_color
        )


# ---------------------------------------------------------------------------
# Chart Widget
# ---------------------------------------------------------------------------

class ChartWidget(BaseWidget):
    """Display various chart types."""
    
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render chart widget."""
        chart_type = self.get_config_value("chart_type", "line")
        
        if data is None:
            st.info(f"📊 {self.title}: No data available")
            return
        
        # For pie/treemap charts, try to use account_mix data if available
        if chart_type in ["pie", "treemap"] and "account_mix" in data:
            chart_data = data["account_mix"]
        elif "chart_data" in data:
            chart_data = data["chart_data"]
        else:
            st.info(f"📊 {self.title}: No data available")
            return
        
        # Create chart based on type
        if chart_type == "line":
            fig = self._create_line_chart(chart_data)
        elif chart_type == "bar":
            fig = self._create_bar_chart(chart_data)
        elif chart_type == "pie":
            fig = self._create_pie_chart(chart_data)
        elif chart_type == "treemap":
            fig = self._create_treemap_chart(chart_data)
        elif chart_type == "area":
            fig = self._create_area_chart(chart_data)
        elif chart_type == "waterfall":
            fig = self._create_waterfall_chart(chart_data)
        elif chart_type == "3d_surface":
            fig = self._create_3d_surface_chart(chart_data)
        elif chart_type == "animated":
            fig = self._create_animated_chart(chart_data)
        else:
            st.error(f"Unsupported chart type: {chart_type}")
            return
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _create_line_chart(self, data: pd.DataFrame) -> go.Figure:
        """Create line chart."""
        x_axis = self.get_config_value("x_axis", data.columns[0])
        y_axis = self.get_config_value("y_axis", data.columns[1])
        
        fig = px.line(
            data,
            x=x_axis,
            y=y_axis,
            title=self.title,
            template="plotly_white"
        )
        
        fig.update_traces(line_color=Colors.PRIMARY)
        return fig
    
    def _create_bar_chart(self, data: pd.DataFrame) -> go.Figure:
        """Create bar chart."""
        x_axis = self.get_config_value("x_axis", data.columns[0])
        y_axis = self.get_config_value("y_axis", data.columns[1])
        
        fig = px.bar(
            data,
            x=x_axis,
            y=y_axis,
            title=self.title,
            template="plotly_white"
        )
        
        fig.update_traces(marker_color=Colors.PRIMARY)
        return fig
    
    def _create_pie_chart(self, data: pd.DataFrame) -> go.Figure:
        """Create pie chart."""
        names_col = self.get_config_value("names", data.columns[0] if len(data.columns) > 0 else "category")
        values_col = self.get_config_value("values", data.columns[1] if len(data.columns) > 1 else "value")
        
        # Validate columns exist
        if names_col not in data.columns or values_col not in data.columns:
            # Try to use first two columns as fallback
            if len(data.columns) >= 2:
                names_col = data.columns[0]
                values_col = data.columns[1]
            else:
                raise ValueError(f"Columns '{names_col}' or '{values_col}' not found in data")
        
        fig = px.pie(
            data,
            names=names_col,
            values=values_col,
            title=self.title,
            template="plotly_white",
            color_discrete_sequence=COLOR_PALETTE
        )
        
        return fig
    
    def _create_treemap_chart(self, data: pd.DataFrame) -> go.Figure:
        """Create treemap chart."""
        path_col = self.get_config_value("path", [data.columns[0]] if len(data.columns) > 0 else ["category"])
        values_col = self.get_config_value("values", data.columns[1] if len(data.columns) > 1 else "value")
        
        # Validate columns exist
        path_list = path_col if isinstance(path_col, list) else [path_col]
        for col in path_list:
            if col not in data.columns:
                # Use first column as fallback
                path_list = [data.columns[0]] if len(data.columns) > 0 else ["category"]
                break
        
        if values_col not in data.columns:
            values_col = data.columns[1] if len(data.columns) > 1 else data.columns[0]
        
        fig = px.treemap(
            data,
            path=path_list,
            values=values_col,
            title=self.title,
            template="plotly_white",
            color_discrete_sequence=COLOR_PALETTE
        )
        
        return fig
    
    def _create_area_chart(self, data: pd.DataFrame) -> go.Figure:
        """Create area chart."""
        x_axis = self.get_config_value("x_axis", data.columns[0])
        y_axis = self.get_config_value("y_axis", data.columns[1])
        
        fig = px.area(
            data,
            x=x_axis,
            y=y_axis,
            title=self.title,
            template="plotly_white"
        )
        
        fig.update_traces(fillcolor=Colors.PRIMARY_LIGHT, line_color=Colors.PRIMARY)
        return fig


# ---------------------------------------------------------------------------
# Table Widget
# ---------------------------------------------------------------------------

class TableWidget(BaseWidget):
    """Display tabular data."""
    
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render table widget."""
        if data is None or "table_data" not in data:
            st.info(f"📋 {self.title}: No data available")
            return
        
        table_data = data["table_data"]
        
        if not isinstance(table_data, pd.DataFrame):
            st.error("Table data must be a pandas DataFrame")
            return
        
        # Apply formatting if specified
        format_config = self.get_config_value("format", {})
        
        # Display table
        st.subheader(self.title)
        
        # Check if interactive editing is enabled
        if self.get_config_value("editable", False):
            edited_df = st.data_editor(
                table_data,
                use_container_width=True,
                hide_index=self.get_config_value("hide_index", True)
            )
            # Store edited data back
            if "edited_data" not in st.session_state:
                st.session_state.edited_data = {}
            st.session_state.edited_data[self.widget_id] = edited_df
        else:
            st.dataframe(
                table_data,
                use_container_width=True,
                hide_index=self.get_config_value("hide_index", True)
            )


# ---------------------------------------------------------------------------
# Text/Notes Widget
# ---------------------------------------------------------------------------

class TextWidget(BaseWidget):
    """Display custom text or markdown content."""
    
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render text widget."""
        content = self.get_config_value("content", "")
        
        if data and "content" in data:
            content = data["content"]
        
        if not content:
            content = "*No content provided*"
        
        # Display with optional title
        if self.title:
            st.subheader(self.title)
        
        st.markdown(content)


# ---------------------------------------------------------------------------
# Goal Progress Widget
# ---------------------------------------------------------------------------

class GoalProgressWidget(BaseWidget):
    """Display progress toward a financial goal."""
    
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render goal progress widget."""
        if data is None:
            st.info(f"🎯 {self.title}: No data available")
            return
        
        current_value = data.get("current_value", 0)
        target_value = data.get("target_value", 100)
        goal_name = data.get("goal_name", self.title)
        
        # Calculate progress
        progress = min(current_value / target_value, 1.0) if target_value > 0 else 0
        progress_pct = progress * 100
        
        # Display goal info
        st.subheader(goal_name)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current", format_currency(current_value))
        with col2:
            st.metric("Target", format_currency(target_value))
        
        # Progress bar
        st.progress(progress)
        
        # Progress percentage
        status_color = get_status_color(progress_pct)
        st.markdown(
            f"<p style='text-align: center; color: {status_color}; font-size: 1.2em; font-weight: bold;'>"
            f"{progress_pct:.1f}% Complete</p>",
            unsafe_allow_html=True
        )
        
        # Remaining amount
        remaining = target_value - current_value
        if remaining > 0:
            st.caption(f"Remaining: {format_currency(remaining)}")
        else:
            st.success("🎉 Goal achieved!")


# ---------------------------------------------------------------------------
# Alert Widget
# ---------------------------------------------------------------------------

class AlertWidget(BaseWidget):
    """Display important alerts or notifications."""
    
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render alert widget."""
        if data is None:
            return
        
        alerts = data.get("alerts", [])
        
        if not alerts:
            st.info("✅ No alerts at this time")
            return
        
        st.subheader(self.title)
        
        for alert in alerts:
            alert_type = alert.get("type", "info")
            message = alert.get("message", "")
            title = alert.get("title", "")
            
            # Display alert based on type
            if alert_type == "error":
                st.error(f"**{title}**: {message}" if title else message)
            elif alert_type == "warning":
                st.warning(f"**{title}**: {message}" if title else message)
            elif alert_type == "success":
                st.success(f"**{title}**: {message}" if title else message)
            else:
                st.info(f"**{title}**: {message}" if title else message)


# ---------------------------------------------------------------------------
# Widget Factory
# ---------------------------------------------------------------------------

def create_widget(widget_type: str, widget_id: str, title: str, config: Dict[str, Any]) -> BaseWidget:
    """Factory function to create widgets by type."""
    widget_classes = {
        "kpi_metric": KPIMetricWidget,
        "chart": ChartWidget,
        "table": TableWidget,
        "text": TextWidget,
        "goal_progress": GoalProgressWidget,
        "alert": AlertWidget,
    }
    
    widget_class = widget_classes.get(widget_type)
    if widget_class is None:
        raise ValueError(f"Unknown widget type: {widget_type}")
    
    return widget_class(widget_id, title, config)

# Made with Bob

    
    def _create_waterfall_chart(self, data: pd.DataFrame) -> go.Figure:
        """Create waterfall chart."""
        from components.visualizations.advanced_charts import create_waterfall_chart
        
        x_axis = self.get_config_value("x_axis", data.columns[0])
        y_axis = self.get_config_value("y_axis", data.columns[1])
        
        # Ensure measure column exists
        if "measure" not in data.columns:
            # Auto-generate measure column if not provided
            data = data.copy()
            data["measure"] = "relative"
            data.loc[0, "measure"] = "absolute"  # First row is starting value
            data.loc[len(data)-1, "measure"] = "total"  # Last row is total
        
        return create_waterfall_chart(data, x_axis, y_axis, self.title)
    
    def _create_3d_surface_chart(self, data: Dict[str, Any]) -> go.Figure:
        """Create 3D surface chart."""
        from components.visualizations.advanced_charts import create_3d_surface_plot
        import numpy as np
        
        # Expect data to contain x_data, y_data, z_data
        x_data = data.get("x_data", np.arange(10))
        y_data = data.get("y_data", np.arange(10))
        z_data = data.get("z_data", np.zeros((10, 10)))
        
        x_label = self.get_config_value("x_label", "X")
        y_label = self.get_config_value("y_label", "Y")
        z_label = self.get_config_value("z_label", "Z")
        
        return create_3d_surface_plot(x_data, y_data, z_data, x_label, y_label, z_label, self.title)
    
    def _create_animated_chart(self, data: pd.DataFrame) -> go.Figure:
        """Create animated timeline chart."""
        from components.visualizations.advanced_charts import create_animated_timeline
        
        x_column = self.get_config_value("x_axis", data.columns[0])
        y_column = self.get_config_value("y_axis", data.columns[1])
        animation_frame = self.get_config_value("animation_frame", "year")
        color_column = self.get_config_value("color_column", None)
        
        return create_animated_timeline(data, x_column, y_column, animation_frame, self.title, color_column)
