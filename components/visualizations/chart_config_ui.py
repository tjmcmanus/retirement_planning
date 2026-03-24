"""
components/visualizations/chart_config_ui.py
=============================================
Chart configuration UI components for customizing chart appearance and behavior.
"""
from __future__ import annotations

from typing import Dict, Any, Optional
import streamlit as st
import plotly.graph_objects as go
from io import BytesIO

from components.theme import Colors


# ---------------------------------------------------------------------------
# Chart Configuration UI
# ---------------------------------------------------------------------------

def render_chart_config_ui(
    widget_id: str,
    current_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Render chart configuration UI and return updated configuration.
    
    Args:
        widget_id: Unique widget identifier
        current_config: Current widget configuration
    
    Returns:
        Updated configuration dictionary
    """
    st.subheader("Chart Configuration")
    
    # Chart type selection
    chart_type = st.selectbox(
        "Chart Type",
        options=["line", "bar", "pie", "treemap", "area", "waterfall", "3d_surface", "animated"],
        index=["line", "bar", "pie", "treemap", "area", "waterfall", "3d_surface", "animated"].index(
            current_config.get("chart_type", "line")
        ),
        key=f"{widget_id}_chart_type"
    )
    
    config = {"chart_type": chart_type}
    
    # Common configuration
    st.subheader("Data Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        x_axis = st.text_input(
            "X-Axis Column",
            value=current_config.get("x_axis", "date"),
            key=f"{widget_id}_x_axis",
            help="Column name for x-axis data"
        )
        config["x_axis"] = x_axis
    
    with col2:
        y_axis = st.text_input(
            "Y-Axis Column",
            value=current_config.get("y_axis", "total"),
            key=f"{widget_id}_y_axis",
            help="Column name for y-axis data"
        )
        config["y_axis"] = y_axis
    
    # Chart-specific configuration
    st.subheader("Chart Styling")
    
    if chart_type in ["line", "area"]:
        config.update(_render_line_area_config(widget_id, current_config))
    elif chart_type == "bar":
        config.update(_render_bar_config(widget_id, current_config))
    elif chart_type in ["pie", "treemap"]:
        config.update(_render_pie_treemap_config(widget_id, current_config))
    elif chart_type == "waterfall":
        config.update(_render_waterfall_config(widget_id, current_config))
    elif chart_type == "3d_surface":
        config.update(_render_3d_surface_config(widget_id, current_config))
    elif chart_type == "animated":
        config.update(_render_animated_config(widget_id, current_config))
    
    # Common styling options
    st.subheader("Display Options")
    
    col1, col2 = st.columns(2)
    with col1:
        show_legend = st.checkbox(
            "Show Legend",
            value=current_config.get("show_legend", True),
            key=f"{widget_id}_show_legend"
        )
        config["show_legend"] = show_legend
    
    with col2:
        show_grid = st.checkbox(
            "Show Grid",
            value=current_config.get("show_grid", True),
            key=f"{widget_id}_show_grid"
        )
        config["show_grid"] = show_grid
    
    return config


def _render_line_area_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for line and area charts."""
    config = {}
    
    col1, col2 = st.columns(2)
    with col1:
        line_color = st.color_picker(
            "Line Color",
            value=current_config.get("line_color", Colors.PRIMARY),
            key=f"{widget_id}_line_color"
        )
        config["line_color"] = line_color
    
    with col2:
        line_width = st.slider(
            "Line Width",
            min_value=1,
            max_value=5,
            value=current_config.get("line_width", 2),
            key=f"{widget_id}_line_width"
        )
        config["line_width"] = line_width
    
    show_markers = st.checkbox(
        "Show Markers",
        value=current_config.get("show_markers", False),
        key=f"{widget_id}_show_markers"
    )
    config["show_markers"] = show_markers
    
    return config


def _render_bar_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for bar charts."""
    config = {}
    
    col1, col2 = st.columns(2)
    with col1:
        bar_color = st.color_picker(
            "Bar Color",
            value=current_config.get("bar_color", Colors.PRIMARY),
            key=f"{widget_id}_bar_color"
        )
        config["bar_color"] = bar_color
    
    with col2:
        orientation = st.selectbox(
            "Orientation",
            options=["vertical", "horizontal"],
            index=0 if current_config.get("orientation", "vertical") == "vertical" else 1,
            key=f"{widget_id}_orientation"
        )
        config["orientation"] = orientation
    
    return config


def _render_pie_treemap_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for pie and treemap charts."""
    config = {}
    
    names_col = st.text_input(
        "Names Column",
        value=current_config.get("names", "category"),
        key=f"{widget_id}_names",
        help="Column containing category names"
    )
    config["names"] = names_col
    
    values_col = st.text_input(
        "Values Column",
        value=current_config.get("values", "value"),
        key=f"{widget_id}_values",
        help="Column containing values"
    )
    config["values"] = values_col
    
    return config


def _render_waterfall_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for waterfall charts."""
    config = {}
    
    st.info("💡 Waterfall charts require a 'measure' column with values: 'absolute', 'relative', or 'total'")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        color_positive = st.color_picker(
            "Positive Color",
            value=current_config.get("color_positive", Colors.SUCCESS),
            key=f"{widget_id}_color_positive"
        )
        config["color_positive"] = color_positive
    
    with col2:
        color_negative = st.color_picker(
            "Negative Color",
            value=current_config.get("color_negative", Colors.ERROR),
            key=f"{widget_id}_color_negative"
        )
        config["color_negative"] = color_negative
    
    with col3:
        color_total = st.color_picker(
            "Total Color",
            value=current_config.get("color_total", Colors.INFO),
            key=f"{widget_id}_color_total"
        )
        config["color_total"] = color_total
    
    show_values = st.checkbox(
        "Show Values on Bars",
        value=current_config.get("show_values", True),
        key=f"{widget_id}_show_values"
    )
    config["show_values"] = show_values
    
    return config


def _render_3d_surface_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for 3D surface plots."""
    config = {}
    
    col1, col2, col3 = st.columns(3)
    with col1:
        x_label = st.text_input(
            "X-Axis Label",
            value=current_config.get("x_label", "X"),
            key=f"{widget_id}_x_label"
        )
        config["x_label"] = x_label
    
    with col2:
        y_label = st.text_input(
            "Y-Axis Label",
            value=current_config.get("y_label", "Y"),
            key=f"{widget_id}_y_label"
        )
        config["y_label"] = y_label
    
    with col3:
        z_label = st.text_input(
            "Z-Axis Label",
            value=current_config.get("z_label", "Z"),
            key=f"{widget_id}_z_label"
        )
        config["z_label"] = z_label
    
    colorscale = st.selectbox(
        "Color Scale",
        options=["Viridis", "RdYlGn", "RdYlGn_r", "Blues", "Reds", "Greens"],
        index=0,
        key=f"{widget_id}_colorscale"
    )
    config["colorscale"] = colorscale
    
    show_contours = st.checkbox(
        "Show Contours",
        value=current_config.get("show_contours", True),
        key=f"{widget_id}_show_contours"
    )
    config["show_contours"] = show_contours
    
    return config


def _render_animated_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for animated charts."""
    config = {}
    
    animation_frame = st.text_input(
        "Animation Frame Column",
        value=current_config.get("animation_frame", "year"),
        key=f"{widget_id}_animation_frame",
        help="Column to animate over (e.g., 'year', 'month')"
    )
    config["animation_frame"] = animation_frame
    
    col1, col2 = st.columns(2)
    with col1:
        color_column = st.text_input(
            "Color Column (optional)",
            value=current_config.get("color_column", ""),
            key=f"{widget_id}_color_column",
            help="Column for color coding"
        )
        if color_column:
            config["color_column"] = color_column
    
    with col2:
        size_column = st.text_input(
            "Size Column (optional)",
            value=current_config.get("size_column", ""),
            key=f"{widget_id}_size_column",
            help="Column for bubble size"
        )
        if size_column:
            config["size_column"] = size_column
    
    return config


# ---------------------------------------------------------------------------
# Chart Export Functions
# ---------------------------------------------------------------------------

def export_chart_as_image(
    fig: go.Figure,
    filename: str = "chart",
    format: str = "png",
    width: int = 1200,
    height: int = 800
) -> BytesIO:
    """
    Export Plotly chart as image.
    
    Args:
        fig: Plotly Figure object
        filename: Base filename (without extension)
        format: Image format ('png', 'jpg', 'svg', 'pdf')
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        BytesIO buffer containing image data
    """
    img_bytes = fig.to_image(format=format, width=width, height=height)
    buffer = BytesIO(img_bytes)
    buffer.seek(0)
    return buffer


def export_chart_as_html(fig: go.Figure, filename: str = "chart") -> BytesIO:
    """
    Export Plotly chart as interactive HTML.
    
    Args:
        fig: Plotly Figure object
        filename: Base filename (without extension)
    
    Returns:
        BytesIO buffer containing HTML data
    """
    html_str = fig.to_html(include_plotlyjs='cdn')
    buffer = BytesIO(html_str.encode('utf-8'))
    buffer.seek(0)
    return buffer


def render_chart_export_ui(fig: go.Figure, chart_title: str = "chart") -> None:
    """
    Render chart export UI with download buttons.
    
    Args:
        fig: Plotly Figure object to export
        chart_title: Title for the exported file
    """
    st.subheader("Export Chart")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Export as PNG
        if st.button("📥 PNG", key=f"export_png_{chart_title}", use_container_width=True):
            img_buffer = export_chart_as_image(fig, chart_title, "png")
            st.download_button(
                label="Download PNG",
                data=img_buffer,
                file_name=f"{chart_title}.png",
                mime="image/png",
                key=f"download_png_{chart_title}"
            )
    
    with col2:
        # Export as SVG
        if st.button("📥 SVG", key=f"export_svg_{chart_title}", use_container_width=True):
            img_buffer = export_chart_as_image(fig, chart_title, "svg")
            st.download_button(
                label="Download SVG",
                data=img_buffer,
                file_name=f"{chart_title}.svg",
                mime="image/svg+xml",
                key=f"download_svg_{chart_title}"
            )
    
    with col3:
        # Export as HTML
        if st.button("📥 HTML", key=f"export_html_{chart_title}", use_container_width=True):
            html_buffer = export_chart_as_html(fig, chart_title)
            st.download_button(
                label="Download HTML",
                data=html_buffer,
                file_name=f"{chart_title}.html",
                mime="text/html",
                key=f"download_html_{chart_title}"
            )
    
    with col4:
        # Export as PDF
        if st.button("📥 PDF", key=f"export_pdf_{chart_title}", use_container_width=True):
            img_buffer = export_chart_as_image(fig, chart_title, "pdf")
            st.download_button(
                label="Download PDF",
                data=img_buffer,
                file_name=f"{chart_title}.pdf",
                mime="application/pdf",
                key=f"download_pdf_{chart_title}"
            )


# ---------------------------------------------------------------------------
# Advanced Chart Configuration
# ---------------------------------------------------------------------------

def render_advanced_chart_options(
    widget_id: str,
    chart_type: str,
    current_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Render advanced configuration options for specific chart types.
    
    Args:
        widget_id: Unique widget identifier
        chart_type: Type of chart
        current_config: Current configuration
    
    Returns:
        Updated configuration dictionary
    """
    config = {}
    
    with st.expander("🎨 Advanced Styling Options"):
        
        # Title and labels
        st.subheader("Titles & Labels")
        col1, col2 = st.columns(2)
        
        with col1:
            x_title = st.text_input(
                "X-Axis Title",
                value=current_config.get("x_title", ""),
                key=f"{widget_id}_x_title"
            )
            if x_title:
                config["x_title"] = x_title
        
        with col2:
            y_title = st.text_input(
                "Y-Axis Title",
                value=current_config.get("y_title", ""),
                key=f"{widget_id}_y_title"
            )
            if y_title:
                config["y_title"] = y_title
        
        # Colors
        st.subheader("Colors")
        
        if chart_type in ["line", "area", "bar"]:
            primary_color = st.color_picker(
                "Primary Color",
                value=current_config.get("primary_color", Colors.PRIMARY),
                key=f"{widget_id}_primary_color"
            )
            config["primary_color"] = primary_color
        
        # Hover template
        st.subheader("Hover Information")
        hover_template = st.text_area(
            "Custom Hover Template",
            value=current_config.get("hover_template", ""),
            key=f"{widget_id}_hover_template",
            help="Plotly hover template string (leave blank for default)"
        )
        if hover_template:
            config["hover_template"] = hover_template
        
        # Axis ranges
        st.subheader("Axis Ranges")
        col1, col2 = st.columns(2)
        
        with col1:
            auto_range_x = st.checkbox(
                "Auto X-Axis Range",
                value=current_config.get("auto_range_x", True),
                key=f"{widget_id}_auto_range_x"
            )
            config["auto_range_x"] = auto_range_x
            
            if not auto_range_x:
                x_min = st.number_input(
                    "X-Axis Min",
                    value=current_config.get("x_min", 0.0),
                    key=f"{widget_id}_x_min"
                )
                x_max = st.number_input(
                    "X-Axis Max",
                    value=current_config.get("x_max", 100.0),
                    key=f"{widget_id}_x_max"
                )
                config["x_min"] = x_min
                config["x_max"] = x_max
        
        with col2:
            auto_range_y = st.checkbox(
                "Auto Y-Axis Range",
                value=current_config.get("auto_range_y", True),
                key=f"{widget_id}_auto_range_y"
            )
            config["auto_range_y"] = auto_range_y
            
            if not auto_range_y:
                y_min = st.number_input(
                    "Y-Axis Min",
                    value=current_config.get("y_min", 0.0),
                    key=f"{widget_id}_y_min"
                )
                y_max = st.number_input(
                    "Y-Axis Max",
                    value=current_config.get("y_max", 100.0),
                    key=f"{widget_id}_y_max"
                )
                config["y_min"] = y_min
                config["y_max"] = y_max
    
    return config


def _render_waterfall_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for waterfall charts."""
    config = {}
    
    col1, col2, col3 = st.columns(3)
    with col1:
        color_positive = st.color_picker(
            "Positive Color",
            value=current_config.get("color_positive", Colors.SUCCESS),
            key=f"{widget_id}_color_positive"
        )
        config["color_positive"] = color_positive
    
    with col2:
        color_negative = st.color_picker(
            "Negative Color",
            value=current_config.get("color_negative", Colors.ERROR),
            key=f"{widget_id}_color_negative"
        )
        config["color_negative"] = color_negative
    
    with col3:
        color_total = st.color_picker(
            "Total Color",
            value=current_config.get("color_total", Colors.INFO),
            key=f"{widget_id}_color_total"
        )
        config["color_total"] = color_total
    
    show_values = st.checkbox(
        "Show Values on Bars",
        value=current_config.get("show_values", True),
        key=f"{widget_id}_show_values"
    )
    config["show_values"] = show_values
    
    return config


def _render_3d_surface_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for 3D surface plots."""
    config = {}
    
    col1, col2, col3 = st.columns(3)
    with col1:
        x_label = st.text_input(
            "X-Axis Label",
            value=current_config.get("x_label", "X"),
            key=f"{widget_id}_x_label"
        )
        config["x_label"] = x_label
    
    with col2:
        y_label = st.text_input(
            "Y-Axis Label",
            value=current_config.get("y_label", "Y"),
            key=f"{widget_id}_y_label"
        )
        config["y_label"] = y_label
    
    with col3:
        z_label = st.text_input(
            "Z-Axis Label",
            value=current_config.get("z_label", "Z"),
            key=f"{widget_id}_z_label"
        )
        config["z_label"] = z_label
    
    colorscale = st.selectbox(
        "Color Scale",
        options=["Viridis", "RdYlGn", "RdYlGn_r", "Blues", "Reds", "Greens", "Plasma", "Inferno"],
        index=0,
        key=f"{widget_id}_colorscale"
    )
    config["colorscale"] = colorscale
    
    show_contours = st.checkbox(
        "Show Contours",
        value=current_config.get("show_contours", True),
        key=f"{widget_id}_show_contours"
    )
    config["show_contours"] = show_contours
    
    return config


def _render_animated_config(widget_id: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render configuration for animated charts."""
    config = {}
    
    animation_frame = st.text_input(
        "Animation Frame Column",
        value=current_config.get("animation_frame", "year"),
        key=f"{widget_id}_animation_frame",
        help="Column to animate over (e.g., 'year', 'month')"
    )
    config["animation_frame"] = animation_frame
    
    col1, col2 = st.columns(2)
    with col1:
        color_column = st.text_input(
            "Color Column (optional)",
            value=current_config.get("color_column", ""),
            key=f"{widget_id}_color_column"
        )
        if color_column:
            config["color_column"] = color_column
    
    with col2:
        size_column = st.text_input(
            "Size Column (optional)",
            value=current_config.get("size_column", ""),
            key=f"{widget_id}_size_column"
        )
        if size_column:
            config["size_column"] = size_column
    
    frame_duration = st.slider(
        "Frame Duration (ms)",
        min_value=100,
        max_value=2000,
        value=current_config.get("frame_duration", 500),
        step=100,
        key=f"{widget_id}_frame_duration"
    )
    config["frame_duration"] = frame_duration
    
    return config

# Made with Bob
