"""
components/visualizations/advanced_charts.py
=============================================
Advanced chart types for enhanced visualizations.

Provides waterfall charts, 3D surface plots, and animated timeline visualizations.
"""
from __future__ import annotations

from typing import Optional, List, Union, Dict
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from components.theme import Colors


# ---------------------------------------------------------------------------
# Waterfall Charts
# ---------------------------------------------------------------------------

def create_waterfall_chart(
    data: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str = "Cash Flow Analysis",
    color_positive: str = Colors.SUCCESS,
    color_negative: str = Colors.ERROR,
    color_total: str = Colors.INFO,
    show_values: bool = True
) -> go.Figure:
    """
    Create a waterfall chart for cash flow analysis.
    
    Args:
        data: DataFrame with categories and values
              Must include a 'measure' column with values: 'relative', 'total', or 'absolute'
        x_column: Column name for categories (x-axis)
        y_column: Column name for values (y-axis)
        title: Chart title
        color_positive: Color for positive values
        color_negative: Color for negative values
        color_total: Color for total/subtotal bars
        show_values: Whether to show value labels on bars
    
    Returns:
        Plotly Figure object
    
    Example:
        >>> data = pd.DataFrame({
        ...     "category": ["Starting Balance", "Income", "Expenses", "Ending Balance"],
        ...     "value": [1000000, 50000, -80000, 970000],
        ...     "measure": ["absolute", "relative", "relative", "total"]
        ... })
        >>> fig = create_waterfall_chart(data, "category", "value")
    """
    # Validate data
    if "measure" not in data.columns:
        raise ValueError("Data must include a 'measure' column")
    
    # Create waterfall chart
    fig = go.Figure(go.Waterfall(
        name="Cash Flow",
        orientation="v",
        measure=data["measure"].tolist(),
        x=data[x_column].tolist(),
        y=data[y_column].tolist(),
        text=data[y_column].apply(lambda x: f"${x:,.0f}") if show_values else None,
        textposition="outside",
        connector={"line": {"color": Colors.BORDER, "width": 2}},
        increasing={"marker": {"color": color_positive}},
        decreasing={"marker": {"color": color_negative}},
        totals={"marker": {"color": color_total}}
    ))
    
    fig.update_layout(
        title=title,
        showlegend=False,
        xaxis_title="Category",
        yaxis_title="Amount ($)",
        template="plotly_white",
        hovermode="x unified"
    )
    
    return fig


def create_income_expense_waterfall(
    income_sources: Dict[str, float],
    expense_categories: Dict[str, float],
    starting_balance: float = 0,
    title: str = "Annual Cash Flow"
) -> go.Figure:
    """
    Create a waterfall chart showing income sources and expense categories.
    
    Args:
        income_sources: Dictionary of income source names and amounts
        expense_categories: Dictionary of expense category names and amounts (positive values)
        starting_balance: Starting balance (optional)
        title: Chart title
    
    Returns:
        Plotly Figure object
    """
    categories = []
    values = []
    measures = []
    
    # Starting balance
    if starting_balance > 0:
        categories.append("Starting Balance")
        values.append(starting_balance)
        measures.append("absolute")
    
    # Income sources
    for source, amount in income_sources.items():
        categories.append(source)
        values.append(amount)
        measures.append("relative")
    
    # Expense categories (make negative)
    for category, amount in expense_categories.items():
        categories.append(category)
        values.append(-abs(amount))
        measures.append("relative")
    
    # Ending balance
    categories.append("Ending Balance")
    values.append(0)  # Will be calculated by waterfall
    measures.append("total")
    
    data = pd.DataFrame({
        "category": categories,
        "value": values,
        "measure": measures
    })
    
    return create_waterfall_chart(data, "category", "value", title)


# ---------------------------------------------------------------------------
# 3D Surface Plots
# ---------------------------------------------------------------------------

def create_3d_surface_plot(
    x_data: Union[np.ndarray, List],
    y_data: Union[np.ndarray, List],
    z_data: np.ndarray,
    x_label: str,
    y_label: str,
    z_label: str,
    title: str = "Optimization Surface",
    colorscale: str = "Viridis",
    show_contours: bool = True
) -> go.Figure:
    """
    Create a 3D surface plot for multi-variable analysis.
    
    Args:
        x_data: X-axis values (e.g., ages)
        y_data: Y-axis values (e.g., conversion amounts)
        z_data: Z-axis values (e.g., tax impact) - 2D array
        x_label: X-axis label
        y_label: Y-axis label
        z_label: Z-axis label
        title: Chart title
        colorscale: Plotly colorscale name
        show_contours: Whether to show contour lines
    
    Returns:
        Plotly Figure object
    
    Example:
        >>> ages = np.arange(60, 75)
        >>> amounts = np.arange(0, 100000, 5000)
        >>> X, Y = np.meshgrid(ages, amounts)
        >>> Z = X * 1000 + Y * 0.2  # Example calculation
        >>> fig = create_3d_surface_plot(ages, amounts, Z, "Age", "Amount", "Tax Impact")
    """
    # Convert to numpy arrays if needed
    x_data = np.array(x_data)
    y_data = np.array(y_data)
    
    # Create surface plot
    fig = go.Figure(data=[go.Surface(
        x=x_data,
        y=y_data,
        z=z_data,
        colorscale=colorscale,
        colorbar=dict(title=z_label),
        contours={
            "z": {"show": show_contours, "usecolormap": True, "highlightcolor": "limegreen", "project": {"z": True}}
        } if show_contours else {}
    )])
    
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title=x_label,
            yaxis_title=y_label,
            zaxis_title=z_label,
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.3)
            )
        ),
        template="plotly_white"
    )
    
    return fig


def create_roth_conversion_surface(
    ages: np.ndarray,
    conversion_amounts: np.ndarray,
    tax_impact_matrix: np.ndarray,
    title: str = "Roth Conversion Optimization"
) -> go.Figure:
    """
    Create a 3D surface plot for Roth conversion optimization.
    
    Args:
        ages: Array of ages to analyze
        conversion_amounts: Array of conversion amounts
        tax_impact_matrix: 2D array of tax impacts for each age/amount combination
        title: Chart title
    
    Returns:
        Plotly Figure object
    """
    return create_3d_surface_plot(
        ages,
        conversion_amounts,
        tax_impact_matrix,
        "Age",
        "Conversion Amount ($)",
        "Total Tax Impact ($)",
        title,
        colorscale="RdYlGn_r"  # Red (high tax) to Green (low tax)
    )


# ---------------------------------------------------------------------------
# Animated Timeline Visualizations
# ---------------------------------------------------------------------------

def create_animated_timeline(
    data: pd.DataFrame,
    x_column: str,
    y_column: str,
    animation_frame: str,
    title: str = "Timeline Animation",
    color_column: Optional[str] = None,
    size_column: Optional[str] = None
) -> go.Figure:
    """
    Create an animated timeline visualization.
    
    Args:
        data: DataFrame with time-series data
        x_column: Column for x-axis
        y_column: Column for y-axis
        animation_frame: Column to animate over (e.g., "year")
        title: Chart title
        color_column: Optional column for color coding
        size_column: Optional column for bubble size
    
    Returns:
        Plotly Figure object with animation
    
    Example:
        >>> data = pd.DataFrame({
        ...     "year": [2025, 2025, 2026, 2026],
        ...     "account": ["Roth", "Traditional", "Roth", "Traditional"],
        ...     "balance": [100000, 200000, 110000, 210000]
        ... })
        >>> fig = create_animated_timeline(data, "account", "balance", "year")
    """
    fig = px.scatter(
        data,
        x=x_column,
        y=y_column,
        animation_frame=animation_frame,
        color=color_column,
        size=size_column if size_column else y_column,
        hover_name=x_column,
        title=title,
        template="plotly_white"
    )
    
    fig.update_layout(
        xaxis_title=x_column,
        yaxis_title=y_column,
        showlegend=True
    )
    
    # Customize animation settings
    try:
        # Type ignore for dynamic plotly attributes
        fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 500  # type: ignore
        fig.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 300  # type: ignore
    except (AttributeError, IndexError, KeyError):
        pass  # Animation controls not available
    
    return fig


def create_bar_chart_race(
    data: pd.DataFrame,
    category_column: str,
    value_column: str,
    time_column: str,
    title: str = "Portfolio Evolution",
    n_bars: int = 10
) -> go.Figure:
    """
    Create an animated bar chart race showing changes over time.
    
    Args:
        data: DataFrame with time-series data
        category_column: Column for categories (y-axis)
        value_column: Column for values (x-axis)
        time_column: Column for time periods (animation frames)
        title: Chart title
        n_bars: Number of top bars to show
    
    Returns:
        Plotly Figure object with animation
    
    Example:
        >>> data = pd.DataFrame({
        ...     "year": [2025, 2025, 2026, 2026],
        ...     "account": ["Roth IRA", "401k", "Roth IRA", "401k"],
        ...     "balance": [100000, 200000, 150000, 250000]
        ... })
        >>> fig = create_bar_chart_race(data, "account", "balance", "year")
    """
    # Sort data and keep top N categories per time period
    sorted_data = []
    for time_val in data[time_column].unique():
        time_slice = data[data[time_column] == time_val].copy()
        # Type ignore for pandas sort_values overload complexity
        time_data = time_slice.sort_values(by=value_column, ascending=False).head(n_bars)  # type: ignore
        sorted_data.append(time_data)
    
    plot_data = pd.concat(sorted_data)
    
    fig = px.bar(
        plot_data,
        x=value_column,
        y=category_column,
        animation_frame=time_column,
        orientation='h',
        title=title,
        template="plotly_white",
        color=category_column,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig.update_layout(
        xaxis_title="Value ($)",
        yaxis_title="Category",
        showlegend=False,
        yaxis={'categoryorder': 'total ascending'}
    )
    
    # Customize animation
    try:
        # Type ignore for dynamic plotly attributes
        fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 800  # type: ignore
        fig.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 400  # type: ignore
    except (AttributeError, IndexError, KeyError):
        pass  # Animation controls not available
    
    return fig


def create_portfolio_evolution_animation(
    portfolio_data: pd.DataFrame,
    title: str = "Portfolio Balance Evolution"
) -> go.Figure:
    """
    Create an animated visualization of portfolio balance evolution over time.
    
    Args:
        portfolio_data: DataFrame with columns: date, account_type, balance
        title: Chart title
    
    Returns:
        Plotly Figure object with animation
    """
    # Ensure date column is datetime
    if 'date' in portfolio_data.columns:
        portfolio_data['date'] = pd.to_datetime(portfolio_data['date'])
        portfolio_data['year'] = portfolio_data['date'].dt.year
    
    return create_bar_chart_race(
        portfolio_data,
        "account_type",
        "balance",
        "year",
        title
    )


# ---------------------------------------------------------------------------
# Combination Charts
# ---------------------------------------------------------------------------

def create_waterfall_with_projection(
    historical_data: pd.DataFrame,
    projection_data: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str = "Cash Flow with Projection"
) -> go.Figure:
    """
    Create a waterfall chart with historical data and future projections.
    
    Args:
        historical_data: DataFrame with historical cash flow data
        projection_data: DataFrame with projected cash flow data
        x_column: Column name for categories
        y_column: Column name for values
        title: Chart title
    
    Returns:
        Plotly Figure object
    """
    # Create base waterfall for historical data
    fig = create_waterfall_chart(historical_data, x_column, y_column, title)
    
    # Add projection as a separate trace with different styling
    if not projection_data.empty:
        fig.add_trace(go.Waterfall(
            name="Projection",
            orientation="v",
            measure=projection_data["measure"].tolist(),
            x=projection_data[x_column].tolist(),
            y=projection_data[y_column].tolist(),
            text=projection_data[y_column].apply(lambda x: f"${x:,.0f}"),
            textposition="outside",
            connector={"line": {"color": Colors.BORDER, "width": 2, "dash": "dash"}},
            increasing={"marker": {"color": Colors.SUCCESS, "opacity": 0.6}},
            decreasing={"marker": {"color": Colors.ERROR, "opacity": 0.6}},
            totals={"marker": {"color": Colors.INFO, "opacity": 0.6}}
        ))
        
        fig.update_layout(showlegend=True)
    
    return fig


def create_heatmap_timeline(
    data: pd.DataFrame,
    x_column: str,
    y_column: str,
    z_column: str,
    title: str = "Timeline Heatmap",
    colorscale: str = "RdYlGn"
) -> go.Figure:
    """
    Create a heatmap showing values over time.
    
    Args:
        data: DataFrame with time-series data
        x_column: Column for x-axis (e.g., year)
        y_column: Column for y-axis (e.g., category)
        z_column: Column for values (color intensity)
        title: Chart title
        colorscale: Plotly colorscale name
    
    Returns:
        Plotly Figure object
    """
    # Pivot data for heatmap
    pivot_data = data.pivot(index=y_column, columns=x_column, values=z_column)
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_data.values,
        x=pivot_data.columns,
        y=pivot_data.index,
        colorscale=colorscale,
        hovertemplate='%{y}<br>%{x}: $%{z:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title=x_column,
        yaxis_title=y_column,
        template="plotly_white"
    )
    
    return fig

# Made with Bob
