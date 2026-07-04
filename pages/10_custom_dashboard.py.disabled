"""
pages/10_custom_dashboard.py
=============================
🎨 Custom Dashboard — Customizable dashboard with drag-and-drop widgets.

Allows users to create personalized dashboards with various widget types
and save/load custom layouts.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime

from components.navbar import navbar
from components.shared import init_page, format_currency
from components.visualizations.dashboard_manager import (
    DashboardLayout,
    Widget,
    Position,
    Size,
    get_current_layout,
    set_current_layout,
    create_default_layout,
    create_tax_planning_layout,
    create_portfolio_focus_layout,
)
from components.visualizations.widget_library import create_widget
from components.visualizations.chart_config_ui import render_chart_export_ui
from load_data import get_networth_by_month

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
(
    networth,
    _portfolio_df,
    _portfolio_cache_ready,
    _stale_label,
    curr_month,
    curr_year,
    _eff_port_month,
    _eff_port_year,
) = init_page("🎨 Custom Dashboard — Financial Planner", "🎨")

navbar("🎨 Custom Dashboard")

st.title("🎨 Custom Dashboard")
st.caption("Create and customize your personal financial dashboard")

# ---------------------------------------------------------------------------
# Sidebar: Dashboard Management
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Dashboard Management")
    
    # Layout selection
    available_layouts = DashboardLayout.list_layouts()
    layout_options = {f"{l['name']} ({l['widget_count']} widgets)": l['layout_id'] 
                     for l in available_layouts}
    
    if layout_options:
        selected_layout_name = st.selectbox(
            "Select Layout",
            options=list(layout_options.keys()),
            key="layout_selector"
        )
        selected_layout_id = layout_options[selected_layout_name]
    else:
        st.info("No saved layouts found. Creating default layout...")
        default_layout = create_default_layout()
        default_layout.save_layout()
        selected_layout_id = "default"
    
    # Load selected layout
    if st.button("Load Layout", use_container_width=True):
        layout = DashboardLayout.load_layout(selected_layout_id)
        if layout:
            set_current_layout(layout)
            st.success(f"Loaded: {layout.name}")
            st.rerun()
        else:
            st.error("Failed to load layout")
    
    st.divider()
    
    # Create new layout
    with st.expander("➕ Create New Layout"):
        new_layout_id = st.text_input("Layout ID", key="new_layout_id")
        new_layout_name = st.text_input("Layout Name", key="new_layout_name")
        
        preset_options = {
            "Blank": None,
            "Default Dashboard": create_default_layout,
            "Tax Planning": create_tax_planning_layout,
            "Portfolio Focus": create_portfolio_focus_layout,
        }
        
        preset = st.selectbox("Start from preset", options=list(preset_options.keys()))
        
        if st.button("Create Layout", use_container_width=True):
            if new_layout_id and new_layout_name:
                if preset_options[preset]:
                    new_layout = preset_options[preset]()
                    new_layout.layout_id = new_layout_id
                    new_layout.name = new_layout_name
                else:
                    new_layout = DashboardLayout(new_layout_id, new_layout_name)
                
                new_layout.save_layout()
                set_current_layout(new_layout)
                st.success(f"Created: {new_layout_name}")
                st.rerun()
            else:
                st.error("Please provide both ID and name")
    
    st.divider()
    
    # Save current layout
    if st.button("💾 Save Current Layout", use_container_width=True):
        current_layout = get_current_layout()
        current_layout.save_layout()
        st.success(f"Saved: {current_layout.name}")

# ---------------------------------------------------------------------------
# Main Content: Dashboard Display
# ---------------------------------------------------------------------------

# Get current layout
current_layout = get_current_layout()

# Display layout info
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.subheader(current_layout.name)
    if current_layout.description:
        st.caption(current_layout.description)
with col2:
    st.metric("Widgets", len(current_layout.widgets))
with col3:
    if st.button("🔄 Refresh Data"):
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Widget Management
# ---------------------------------------------------------------------------
with st.expander("⚙️ Manage Widgets"):
    tab1, tab2, tab3 = st.tabs(["Add Widget", "Edit Widgets", "Configure Widget"])
    
    with tab1:
        st.subheader("Add New Widget")
        
        col1, col2 = st.columns(2)
        with col1:
            widget_type = st.selectbox(
                "Widget Type",
                options=["kpi_metric", "chart", "table", "text", "goal_progress", "alert"]
            )
            widget_id = st.text_input("Widget ID", value=f"widget_{len(current_layout.widgets) + 1}")
            widget_title = st.text_input("Widget Title", value="New Widget")
        
        with col2:
            row = st.number_input("Row", min_value=0, value=len(current_layout.widgets))
            col_pos = st.number_input("Column", min_value=0, max_value=11, value=0)
            width = st.number_input("Width (columns)", min_value=1, max_value=12, value=6)
            height = st.number_input("Height (rows)", min_value=1, max_value=4, value=2)
        
        if st.button("Add Widget"):
            try:
                new_widget = Widget(
                    widget_id=widget_id,
                    widget_type=widget_type,
                    title=widget_title,
                    position=Position(row, col_pos),
                    size=Size(width, height),
                    config={}
                )
                current_layout.add_widget(new_widget)
                current_layout.save_layout()
                st.success(f"Added widget: {widget_title}")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    
    with tab2:
        st.subheader("Edit Widgets")
        
        if not current_layout.widgets:
            st.info("No widgets to edit")
        else:
            for i, widget in enumerate(current_layout.widgets):
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        st.write(f"**{widget.title}** ({widget.widget_type})")
                        st.caption(f"Position: ({widget.position.row}, {widget.position.col}) | Size: {widget.size.width}x{widget.size.height}")
                    
                    with col2:
                        if st.button("⬆️", key=f"up_{widget.widget_id}"):
                            if current_layout.move_widget_up(widget.widget_id):
                                current_layout.save_layout()
                                st.rerun()
                    
                    with col3:
                        if st.button("⬇️", key=f"down_{widget.widget_id}"):
                            if current_layout.move_widget_down(widget.widget_id):
                                current_layout.save_layout()
                                st.rerun()
                    
                    with col4:
                        if st.button("🗑️", key=f"delete_{widget.widget_id}"):
                            if current_layout.remove_widget(widget.widget_id):
                                current_layout.save_layout()
                                st.success(f"Removed: {widget.title}")
                                st.rerun()
                    
                    st.divider()
    
    with tab3:
        st.subheader("Configure Widget")
        
        if not current_layout.widgets:
            st.info("No widgets to configure")
        else:
            # Widget selector
            widget_options = {f"{w.title} ({w.widget_type})": w.widget_id
                            for w in current_layout.widgets}
            
            selected_widget_name = st.selectbox(
                "Select Widget to Configure",
                options=list(widget_options.keys()),
                key="config_widget_selector"
            )
            
            selected_widget_id = widget_options[selected_widget_name]
            selected_widget = current_layout.get_widget(selected_widget_id)
            
            if selected_widget and selected_widget.widget_type == "chart":
                st.divider()
                
                # Import chart configuration UI
                from components.visualizations.chart_config_ui import (
                    render_chart_config_ui,
                    render_advanced_chart_options
                )
                
                # Render configuration UI
                updated_config = render_chart_config_ui(
                    selected_widget.widget_id,
                    selected_widget.config
                )
                
                # Render advanced options
                advanced_config = render_advanced_chart_options(
                    selected_widget.widget_id,
                    updated_config.get("chart_type", "line"),
                    selected_widget.config
                )
                
                # Merge configurations
                updated_config.update(advanced_config)
                
                # Save button
                if st.button("💾 Save Configuration", key=f"save_config_{selected_widget_id}"):
                    selected_widget.update_config(updated_config)
                    current_layout.save_layout()
                    st.success(f"Configuration saved for: {selected_widget.title}")
                    st.rerun()
            
            elif selected_widget:
                st.info(f"Configuration UI not yet available for {selected_widget.widget_type} widgets")
            else:
                st.error("Widget not found")

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def prepare_widget_data(networth: pd.DataFrame) -> dict:
    """Prepare data for all widgets."""
    if networth.empty:
        return {}
    
    # Calculate metrics
    current_nw = float(networth["total"].iloc[-1])
    prior_nw = float(networth["total"].iloc[-2]) if len(networth) > 1 else current_nw
    mom_change = current_nw - prior_nw
    mom_pct = (mom_change / prior_nw * 100) if prior_nw else 0.0
    
    # YTD calculation
    dti = pd.DatetimeIndex(networth.index)
    curr_year_mask = dti.year == dti[-1].year  # type: ignore
    ytd_start = float(networth.loc[curr_year_mask, "total"].iloc[0]) if curr_year_mask.any() else current_nw
    ytd_change = current_nw - ytd_start
    ytd_pct = (ytd_change / ytd_start * 100) if ytd_start else 0.0
    
    # Prepare account mix data for pie/treemap charts
    latest_row = networth.iloc[-1]
    account_mix_data = pd.DataFrame({
        "account_type": ["Cash", "Taxable", "Tax Deferred", "Tax Free"],
        "balance": [
            float(latest_row.get("cash", 0)),
            float(latest_row.get("taxable", 0)),
            float(latest_row.get("tax_deferred", 0)),
            float(latest_row.get("tax_free", 0))
        ]
    })
    # Remove zero balances
    account_mix_data = account_mix_data[account_mix_data["balance"] > 0]
    
    return {
        "net_worth": current_nw,
        "net_worth_delta": mom_change,
        "mom_change": mom_change,
        "mom_change_delta": mom_pct,
        "mom_pct": mom_pct,
        "ytd_change": ytd_change,
        "ytd_change_delta": ytd_pct,
        "ytd_return": ytd_pct,
        "portfolio_value": current_nw,
        "chart_data": networth.reset_index(),
        "table_data": networth.tail(12).reset_index(),
        "account_mix": account_mix_data,  # For pie/treemap charts
    }


def render_widget(widget: Widget, data: dict) -> None:
    """Render a single widget with export options for charts."""
    try:
        widget_instance = create_widget(
            widget.widget_type,
            widget.widget_id,
            widget.title,
            widget.config
        )
        
        # Render the widget
        widget_instance.render(data)
        
        # Add export options for chart widgets
        if widget.widget_type == "chart" and "chart_data" in data:
            with st.expander(f"📥 Export {widget.title}", expanded=False):
                # Re-create the chart for export
                from components.visualizations.widget_library import ChartWidget
                
                # Type check and cast
                if isinstance(widget_instance, ChartWidget):
                    chart_type = widget.config.get("chart_type", "line")
                    
                    # Re-create figure for export
                    try:
                        if chart_type == "line":
                            fig = widget_instance._create_line_chart(data["chart_data"])
                        elif chart_type == "bar":
                            fig = widget_instance._create_bar_chart(data["chart_data"])
                        elif chart_type == "pie":
                            fig = widget_instance._create_pie_chart(data["chart_data"])
                        elif chart_type == "treemap":
                            fig = widget_instance._create_treemap_chart(data["chart_data"])
                        elif chart_type == "area":
                            fig = widget_instance._create_area_chart(data["chart_data"])
                        elif chart_type == "waterfall":
                            fig = widget_instance._create_waterfall_chart(data["chart_data"])
                        else:
                            fig = None
                        
                        if fig:
                            render_chart_export_ui(fig, widget.widget_id)
                    except Exception as e:
                        st.warning(f"Export not available: {str(e)}")
                
    except Exception as e:
        st.error(f"Error rendering widget '{widget.title}': {str(e)}")


# ---------------------------------------------------------------------------
# Render Dashboard Widgets
# ---------------------------------------------------------------------------

st.subheader("Dashboard")

if not current_layout.widgets:
    st.info("No widgets in this dashboard. Add widgets using the 'Manage Widgets' section above.")
else:
    # Prepare data for widgets
    widget_data = prepare_widget_data(networth)
    
    # Render widgets in grid layout
    # Group widgets by row
    widgets_by_row = {}
    for widget in current_layout.widgets:
        row = widget.position.row
        if row not in widgets_by_row:
            widgets_by_row[row] = []
        widgets_by_row[row].append(widget)
    
    # Render each row
    for row in sorted(widgets_by_row.keys()):
        row_widgets = sorted(widgets_by_row[row], key=lambda w: w.position.col)
        
        # Calculate column widths
        total_width = sum(w.size.width for w in row_widgets)
        if total_width > 12:
            st.warning(f"Row {row} exceeds 12 columns. Widgets may not display correctly.")
        
        # Create columns
        cols = st.columns([w.size.width for w in row_widgets])
        
        # Render widgets in columns
        for col, widget in zip(cols, row_widgets):
            with col:
                render_widget(widget, widget_data)

# Made with Bob
