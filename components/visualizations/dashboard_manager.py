"""
components/visualizations/dashboard_manager.py
===============================================
Dashboard layout and widget management system.

Provides classes for managing customizable dashboard layouts with
widget positioning, sizing, and configuration.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import streamlit as st


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class Position:
    """Widget position in grid."""
    row: int
    col: int
    
    def to_dict(self) -> Dict[str, int]:
        return {"row": self.row, "col": self.col}
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> Position:
        return cls(row=data["row"], col=data["col"])


@dataclass
class Size:
    """Widget size in grid cells."""
    width: int  # Number of columns
    height: int  # Number of rows
    
    def to_dict(self) -> Dict[str, int]:
        return {"width": self.width, "height": self.height}
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> Size:
        return cls(width=data["width"], height=data["height"])


@dataclass
class GridConfig:
    """Grid layout configuration."""
    columns: int = 12
    row_height: int = 100
    gap: int = 16
    breakpoints: Dict[str, int] = field(default_factory=lambda: {
        "mobile": 1,
        "tablet": 2,
        "desktop": 3,
        "wide": 4
    })
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GridConfig:
        return cls(**data)


@dataclass
class Widget:
    """Base widget configuration."""
    widget_id: str
    widget_type: str
    title: str
    position: Position
    size: Size
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type,
            "title": self.title,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "config": self.config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Widget:
        return cls(
            widget_id=data["widget_id"],
            widget_type=data["widget_type"],
            title=data["title"],
            position=Position.from_dict(data["position"]),
            size=Size.from_dict(data["size"]),
            config=data.get("config", {})
        )
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update widget configuration."""
        self.config.update(config)
    
    def move_to(self, position: Position) -> None:
        """Move widget to new position."""
        self.position = position
    
    def resize(self, size: Size) -> None:
        """Resize widget."""
        self.size = size


# ---------------------------------------------------------------------------
# Dashboard Layout Manager
# ---------------------------------------------------------------------------

class DashboardLayout:
    """Manages dashboard layout configuration."""
    
    def __init__(
        self,
        layout_id: str,
        name: str,
        description: str = "",
        grid_config: Optional[GridConfig] = None,
        widgets: Optional[List[Widget]] = None
    ):
        self.layout_id = layout_id
        self.name = name
        self.description = description
        self.grid_config = grid_config or GridConfig()
        self.widgets = widgets or []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def add_widget(self, widget: Widget, position: Optional[Position] = None) -> None:
        """Add a widget to the layout."""
        if position:
            widget.move_to(position)
        
        # Check for position conflicts
        if self._has_position_conflict(widget):
            raise ValueError(
                f"Widget position conflict at row={widget.position.row}, "
                f"col={widget.position.col}"
            )
        
        self.widgets.append(widget)
        self.updated_at = datetime.now()
    
    def remove_widget(self, widget_id: str) -> bool:
        """Remove a widget from the layout."""
        initial_count = len(self.widgets)
        self.widgets = [w for w in self.widgets if w.widget_id != widget_id]
        
        if len(self.widgets) < initial_count:
            self.updated_at = datetime.now()
            return True
        return False
    
    def get_widget(self, widget_id: str) -> Optional[Widget]:
        """Get a widget by ID."""
        for widget in self.widgets:
            if widget.widget_id == widget_id:
                return widget
        return None
    
    def reorder_widgets(self, widget_ids: List[str]) -> None:
        """Reorder widgets based on provided ID list."""
        widget_map = {w.widget_id: w for w in self.widgets}
        self.widgets = [widget_map[wid] for wid in widget_ids if wid in widget_map]
        self.updated_at = datetime.now()
    
    def move_widget_up(self, widget_id: str) -> bool:
        """Move widget up in order."""
        for i, widget in enumerate(self.widgets):
            if widget.widget_id == widget_id and i > 0:
                self.widgets[i], self.widgets[i-1] = self.widgets[i-1], self.widgets[i]
                self.updated_at = datetime.now()
                return True
        return False
    
    def move_widget_down(self, widget_id: str) -> bool:
        """Move widget down in order."""
        for i, widget in enumerate(self.widgets):
            if widget.widget_id == widget_id and i < len(self.widgets) - 1:
                self.widgets[i], self.widgets[i+1] = self.widgets[i+1], self.widgets[i]
                self.updated_at = datetime.now()
                return True
        return False
    
    def _has_position_conflict(self, new_widget: Widget) -> bool:
        """Check if widget position conflicts with existing widgets."""
        for widget in self.widgets:
            if widget.widget_id == new_widget.widget_id:
                continue
            
            # Check for overlap
            if (widget.position.row == new_widget.position.row and
                widget.position.col == new_widget.position.col):
                return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert layout to dictionary."""
        return {
            "layout_id": self.layout_id,
            "name": self.name,
            "description": self.description,
            "grid_config": self.grid_config.to_dict(),
            "widgets": [w.to_dict() for w in self.widgets],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DashboardLayout:
        """Create layout from dictionary."""
        layout = cls(
            layout_id=data["layout_id"],
            name=data["name"],
            description=data.get("description", ""),
            grid_config=GridConfig.from_dict(data["grid_config"]),
            widgets=[Widget.from_dict(w) for w in data["widgets"]]
        )
        
        if "created_at" in data:
            layout.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            layout.updated_at = datetime.fromisoformat(data["updated_at"])
        
        return layout
    
    def save_layout(self, directory: str = "data/dashboard_layouts") -> None:
        """Save layout to JSON file."""
        Path(directory).mkdir(parents=True, exist_ok=True)
        filepath = Path(directory) / f"{self.layout_id}.json"
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_layout(cls, layout_id: str, directory: str = "data/dashboard_layouts") -> Optional[DashboardLayout]:
        """Load layout from JSON file."""
        filepath = Path(directory) / f"{layout_id}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def list_layouts(cls, directory: str = "data/dashboard_layouts") -> List[Dict[str, str]]:
        """List all available layouts."""
        layouts = []
        layout_dir = Path(directory)
        
        if not layout_dir.exists():
            return layouts
        
        for filepath in layout_dir.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                layouts.append({
                    "layout_id": data["layout_id"],
                    "name": data["name"],
                    "description": data.get("description", ""),
                    "widget_count": len(data.get("widgets", []))
                })
            except Exception:
                continue
        
        return layouts
    
    def clone(self, new_layout_id: str, new_name: str) -> DashboardLayout:
        """Create a copy of this layout with new ID and name."""
        return DashboardLayout(
            layout_id=new_layout_id,
            name=new_name,
            description=self.description,
            grid_config=GridConfig.from_dict(self.grid_config.to_dict()),
            widgets=[Widget.from_dict(w.to_dict()) for w in self.widgets]
        )


# ---------------------------------------------------------------------------
# Layout Presets
# ---------------------------------------------------------------------------

def create_default_layout() -> DashboardLayout:
    """Create default dashboard layout."""
    layout = DashboardLayout(
        layout_id="default",
        name="Default Dashboard",
        description="Standard financial overview dashboard"
    )
    
    # Add default widgets
    widgets = [
        Widget(
            widget_id="net_worth_kpi",
            widget_type="kpi_metric",
            title="Net Worth",
            position=Position(0, 0),
            size=Size(3, 1),
            config={"metric": "net_worth", "show_trend": True}
        ),
        Widget(
            widget_id="mom_change_kpi",
            widget_type="kpi_metric",
            title="Month-over-Month",
            position=Position(0, 3),
            size=Size(3, 1),
            config={"metric": "mom_change", "show_trend": True}
        ),
        Widget(
            widget_id="ytd_change_kpi",
            widget_type="kpi_metric",
            title="Year-to-Date",
            position=Position(0, 6),
            size=Size(3, 1),
            config={"metric": "ytd_change", "show_trend": True}
        ),
        Widget(
            widget_id="net_worth_chart",
            widget_type="chart",
            title="Net Worth Trend",
            position=Position(1, 0),
            size=Size(6, 2),
            config={
                "chart_type": "line",
                "data_source": "networth_by_month",
                "x_axis": "date",
                "y_axis": "total"
            }
        ),
        Widget(
            widget_id="account_mix_chart",
            widget_type="chart",
            title="Account Mix",
            position=Position(1, 6),
            size=Size(6, 2),
            config={
                "chart_type": "pie",
                "names": "account_type",
                "values": "balance"
            }
        ),
    ]
    
    for widget in widgets:
        layout.add_widget(widget)
    
    return layout


def create_tax_planning_layout() -> DashboardLayout:
    """Create tax planning focused dashboard layout."""
    layout = DashboardLayout(
        layout_id="tax_planning",
        name="Tax Planning Dashboard",
        description="Focus on tax optimization and strategies"
    )
    
    widgets = [
        Widget(
            widget_id="current_tax_bracket",
            widget_type="kpi_metric",
            title="Current Tax Bracket",
            position=Position(0, 0),
            size=Size(4, 1),
            config={"metric": "tax_bracket"}
        ),
        Widget(
            widget_id="roth_conversion_chart",
            widget_type="chart",
            title="Roth Conversion Analysis",
            position=Position(1, 0),
            size=Size(6, 2),
            config={"chart_type": "waterfall", "data_source": "roth_analysis"}
        ),
        Widget(
            widget_id="tax_projection_chart",
            widget_type="chart",
            title="Multi-Year Tax Projection",
            position=Position(1, 6),
            size=Size(6, 2),
            config={"chart_type": "line", "data_source": "tax_projection"}
        ),
    ]
    
    for widget in widgets:
        layout.add_widget(widget)
    
    return layout


def create_portfolio_focus_layout() -> DashboardLayout:
    """Create portfolio focused dashboard layout."""
    layout = DashboardLayout(
        layout_id="portfolio_focus",
        name="Portfolio Focus Dashboard",
        description="Detailed portfolio analytics and performance"
    )
    
    widgets = [
        Widget(
            widget_id="portfolio_value",
            widget_type="kpi_metric",
            title="Portfolio Value",
            position=Position(0, 0),
            size=Size(3, 1),
            config={"metric": "portfolio_value"}
        ),
        Widget(
            widget_id="portfolio_return",
            widget_type="kpi_metric",
            title="YTD Return",
            position=Position(0, 3),
            size=Size(3, 1),
            config={"metric": "ytd_return"}
        ),
        Widget(
            widget_id="allocation_chart",
            widget_type="chart",
            title="Asset Allocation",
            position=Position(1, 0),
            size=Size(6, 2),
            config={"chart_type": "pie", "data_source": "asset_allocation"}
        ),
        Widget(
            widget_id="performance_chart",
            widget_type="chart",
            title="Performance vs Benchmark",
            position=Position(1, 6),
            size=Size(6, 2),
            config={"chart_type": "line", "data_source": "performance"}
        ),
    ]
    
    for widget in widgets:
        layout.add_widget(widget)
    
    return layout


# ---------------------------------------------------------------------------
# Session State Management
# ---------------------------------------------------------------------------

def get_current_layout() -> DashboardLayout:
    """Get current dashboard layout from session state."""
    if "dashboard_layout" not in st.session_state:
        # Try to load saved layout
        layout_id = st.session_state.get("selected_layout_id", "default")
        layout = DashboardLayout.load_layout(layout_id)
        
        if layout is None:
            # Create and save default layout
            layout = create_default_layout()
            layout.save_layout()
        
        st.session_state.dashboard_layout = layout
    
    return st.session_state.dashboard_layout


def set_current_layout(layout: DashboardLayout) -> None:
    """Set current dashboard layout in session state."""
    st.session_state.dashboard_layout = layout
    st.session_state.selected_layout_id = layout.layout_id


def refresh_layout() -> None:
    """Refresh layout from disk."""
    if "dashboard_layout" in st.session_state:
        layout_id = st.session_state.dashboard_layout.layout_id
        layout = DashboardLayout.load_layout(layout_id)
        if layout:
            st.session_state.dashboard_layout = layout

# Made with Bob
