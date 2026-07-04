# Custom Dashboard User Guide

## Overview

The Custom Dashboard allows you to create personalized financial dashboards with various widget types and layouts.

---

## Getting Started

### Accessing the Dashboard

1. Navigate to **🎨 Custom Dashboard** in the top navigation bar
2. You'll see the default dashboard layout with sample widgets

### Understanding Layouts

A **layout** is a saved configuration of widgets, their positions, and settings. You can:
- Create multiple layouts for different purposes
- Switch between layouts
- Save and load layouts
- Clone existing layouts

---

## Creating Your First Dashboard

### Step 1: Create a New Layout

1. In the sidebar, expand **"➕ Create New Layout"**
2. Enter a unique **Layout ID** (e.g., `my_dashboard`)
3. Enter a **Layout Name** (e.g., `My Financial Dashboard`)
4. Choose a preset:
   - **Blank** - Start from scratch
   - **Default Dashboard** - Standard financial overview
   - **Tax Planning** - Tax-focused widgets
   - **Portfolio Focus** - Portfolio analytics
5. Click **"Create Layout"**

### Step 2: Add Widgets

1. Expand **"⚙️ Manage Widgets"**
2. Go to the **"Add Widget"** tab
3. Configure your widget:
   - **Widget Type**: Choose from 6 types (see below)
   - **Widget ID**: Unique identifier (e.g., `net_worth_kpi`)
   - **Widget Title**: Display name (e.g., `Net Worth`)
   - **Row**: Vertical position (0 = top)
   - **Column**: Horizontal position (0-11)
   - **Width**: Number of columns (1-12)
   - **Height**: Number of rows (1-4)
4. Click **"Add Widget"**

### Step 3: Arrange Widgets

1. Go to the **"Edit Widgets"** tab
2. Use **⬆️** and **⬇️** buttons to reorder widgets
3. Use **🗑️** button to delete unwanted widgets

### Step 4: Save Your Layout

1. Click **"💾 Save Current Layout"** in the sidebar
2. Your layout is now saved and will persist across sessions

---

## Widget Types

### 1. KPI Metric Widget

**Purpose**: Display a single key metric with trend indicator

**Best For**:
- Net worth
- Month-over-month changes
- Year-to-date performance
- Portfolio value

**Data Requirements**:
- Metric value (automatically pulled from networth data)
- Optional: Delta value for trend

**Configuration**:
```json
{
  "metric": "net_worth",
  "show_trend": true,
  "comparison_period": "month"
}
```

**Available Metrics**:
- `net_worth` - Total net worth
- `mom_change` - Month-over-month change
- `ytd_change` - Year-to-date change
- `portfolio_value` - Total portfolio value
- `ytd_return` - Year-to-date return percentage

---

### 2. Chart Widget

**Purpose**: Display various chart types

**Best For**:
- Trends over time
- Comparisons
- Distributions
- Cash flow analysis

**Chart Types**:
- `line` - Line chart for trends
- `bar` - Bar chart for comparisons
- `pie` - Pie chart for distributions
- `treemap` - Hierarchical treemap
- `area` - Area chart for cumulative data
- `waterfall` - Cash flow analysis
- `3d_surface` - Multi-variable optimization
- `animated` - Timeline animations

**Configuration**:
```json
{
  "chart_type": "line",
  "x_axis": "date",
  "y_axis": "total"
}
```

**Data Source**: Automatically uses networth data with columns:
- `date` - Time series index
- `total` - Total net worth
- `cash` - Cash balance
- `taxable` - Taxable account balance
- `tax_deferred` - Traditional IRA/401k balance
- `tax_free` - Roth IRA/401k balance

---

### 3. Table Widget

**Purpose**: Display tabular data

**Best For**:
- Account balances
- Transaction history
- Detailed breakdowns

**Configuration**:
```json
{
  "editable": false,
  "hide_index": true
}
```

**Data Source**: Last 12 months of networth data

---

### 4. Text Widget

**Purpose**: Display custom text or notes

**Best For**:
- Dashboard instructions
- Important reminders
- Planning notes
- Goals and objectives

**Configuration**:
```json
{
  "content": "## My Financial Goals\n\n- Save $50k this year\n- Max out 401k\n- Build 6-month emergency fund"
}
```

**Supports**: Full Markdown formatting

---

### 5. Goal Progress Widget

**Purpose**: Track progress toward financial goals

**Best For**:
- Savings goals
- Debt payoff
- Investment targets
- Emergency fund building

**Configuration**:
```json
{
  "goal_name": "Emergency Fund",
  "target_value": 50000,
  "current_value": 35000
}
```

**Note**: Currently requires manual data entry. Future versions will support automatic tracking.

---

### 6. Alert Widget

**Purpose**: Display important notifications

**Best For**:
- Action items
- Warnings
- Reminders
- Status updates

**Configuration**:
```json
{
  "alerts": [
    {
      "type": "warning",
      "title": "RMD Due",
      "message": "Required Minimum Distribution due by Dec 31"
    }
  ]
}
```

**Alert Types**:
- `info` - Informational (blue)
- `warning` - Warning (yellow)
- `error` - Error (red)
- `success` - Success (green)

---

## Data Sources

### Current Implementation

**Automatic Data**: The dashboard currently pulls data automatically from:
- **Networth Data**: Monthly portfolio balances from `portfolio_data_truth.csv`
- **Calculated Metrics**: Derived metrics like MoM change, YTD change, etc.

**Data Preparation**: The `prepare_widget_data()` function in `pages/10_custom_dashboard.py` prepares all data:

```python
{
    "net_worth": current_nw,
    "net_worth_delta": mom_change,
    "mom_change": mom_change,
    "mom_pct": mom_pct,
    "ytd_change": ytd_change,
    "ytd_return": ytd_pct,
    "portfolio_value": current_nw,
    "chart_data": networth.reset_index(),
    "table_data": networth.tail(12).reset_index(),
}
```

### Future Enhancement: Custom Data Sources

**Planned for Phase 2**: Widget-level data source configuration

**Proposed Configuration**:
```json
{
  "widget_id": "custom_chart",
  "widget_type": "chart",
  "data_source": {
    "type": "networth",  // or "portfolio", "strategy", "custom"
    "filters": {
      "date_range": "last_12_months",
      "accounts": ["Roth", "Traditional"]
    }
  }
}
```

---

## Layout Management

### Preset Layouts

**Default Dashboard**:
- Net Worth KPI
- Month-over-Month KPI
- Year-to-Date KPI
- Net Worth Trend Chart
- Account Mix Treemap

**Tax Planning**:
- Current Tax Bracket KPI
- Roth Conversion Analysis (Waterfall)
- Multi-Year Tax Projection (Line)

**Portfolio Focus**:
- Portfolio Value KPI
- YTD Return KPI
- Asset Allocation (Pie)
- Performance vs Benchmark (Line)

### Cloning Layouts

1. Load the layout you want to clone
2. In sidebar, create a new layout
3. Choose the preset that matches your current layout
4. Modify as needed
5. Save with a new name

### Sharing Layouts

**Export** (Manual):
1. Layouts are saved in `data/dashboard_layouts/`
2. Copy the JSON file (e.g., `my_dashboard.json`)
3. Share the file

**Import** (Manual):
1. Place JSON file in `data/dashboard_layouts/`
2. Refresh the dashboard page
3. Select the layout from the dropdown

---

## Grid System

### Understanding the Grid

- **12 Columns**: Dashboard uses a 12-column grid
- **Rows**: Unlimited rows, each 100px high
- **Positioning**: Widgets positioned by (row, column)
- **Sizing**: Widgets sized by (width, height)

### Layout Examples

**Full Width Widget**:
- Row: 0, Column: 0
- Width: 12, Height: 2

**Half Width Widgets**:
- Widget 1: Row: 0, Column: 0, Width: 6, Height: 2
- Widget 2: Row: 0, Column: 6, Width: 6, Height: 2

**Three Column Layout**:
- Widget 1: Row: 0, Column: 0, Width: 4, Height: 1
- Widget 2: Row: 0, Column: 4, Width: 4, Height: 1
- Widget 3: Row: 0, Column: 8, Width: 4, Height: 1

**Stacked Widgets**:
- Widget 1: Row: 0, Column: 0, Width: 12, Height: 1
- Widget 2: Row: 1, Column: 0, Width: 12, Height: 2
- Widget 3: Row: 3, Column: 0, Width: 12, Height: 1

---

## Tips & Best Practices

### Dashboard Design

1. **Start Simple**: Begin with 3-5 key widgets
2. **Group Related Info**: Keep related metrics together
3. **Use Visual Hierarchy**: Important metrics at top
4. **Balance Layout**: Avoid overcrowding
5. **Test Responsiveness**: Check on different screen sizes

### Widget Selection

1. **KPIs for Key Metrics**: Use for most important numbers
2. **Charts for Trends**: Show changes over time
3. **Tables for Details**: Provide detailed breakdowns
4. **Text for Context**: Add explanations and notes
5. **Alerts for Actions**: Highlight what needs attention

### Performance

1. **Limit Widgets**: 10-15 widgets per dashboard
2. **Optimize Charts**: Use appropriate date ranges
3. **Cache Data**: Data is prepared once per page load
4. **Refresh Wisely**: Use refresh button only when needed

---

## Troubleshooting

### Widget Not Displaying

**Problem**: Widget shows "No data available"

**Solutions**:
1. Ensure portfolio data exists in `portfolio_data_truth.csv`
2. Check that you have at least 2 months of data
3. Verify widget configuration is correct
4. Try refreshing the page

### Layout Not Saving

**Problem**: Changes don't persist

**Solutions**:
1. Click "💾 Save Current Layout" after changes
2. Check file permissions on `data/dashboard_layouts/`
3. Verify layout ID is unique
4. Check browser console for errors

### Widgets Overlapping

**Problem**: Widgets appear on top of each other

**Solutions**:
1. Check widget positions don't conflict
2. Ensure total width doesn't exceed 12 columns
3. Use "Edit Widgets" to reorder
4. Delete and re-add widgets with correct positions

### Chart Type Not Supported

**Problem**: "Unsupported chart type" error

**Solutions**:
1. Use supported chart types: line, bar, pie, treemap, area, waterfall, 3d_surface, animated
2. Check spelling of chart_type in configuration
3. Ensure data format matches chart requirements

---

## Advanced Usage

### Custom Widget Configuration

While the UI provides basic configuration, you can manually edit layout JSON files for advanced options:

**Location**: `data/dashboard_layouts/your_layout.json`

**Example**:
```json
{
  "widget_id": "advanced_chart",
  "widget_type": "chart",
  "title": "Custom Analysis",
  "position": {"row": 0, "col": 0},
  "size": {"width": 12, "height": 3},
  "config": {
    "chart_type": "waterfall",
    "x_axis": "category",
    "y_axis": "value",
    "color_positive": "#21c354",
    "color_negative": "#ff4b4b",
    "show_values": true
  }
}
```

### Programmatic Widget Creation

For developers, widgets can be created programmatically:

```python
from components.visualizations.dashboard_manager import (
    DashboardLayout, Widget, Position, Size
)

# Create layout
layout = DashboardLayout("custom", "My Custom Dashboard")

# Add widget
widget = Widget(
    widget_id="my_widget",
    widget_type="kpi_metric",
    title="Custom Metric",
    position=Position(0, 0),
    size=Size(3, 1),
    config={"metric": "net_worth", "show_trend": True}
)

layout.add_widget(widget)
layout.save_layout()
```

---

## Future Enhancements

### Planned Features

**Phase 2** (Advanced Charts Integration):
- Chart configuration UI
- More chart customization options
- Chart export functionality

**Phase 3** (PDF Reports):
- Export dashboards as PDF
- Scheduled report generation
- Email delivery

**Phase 4** (Data Sources):
- Custom data source configuration
- Multiple data source support
- Real-time data updates
- API integrations

**Phase 5** (Polish):
- Mobile-responsive layouts
- Drag-and-drop widget positioning
- Widget templates library
- Dashboard sharing

---

## Support

### Getting Help

1. Check this guide first
2. Review the implementation plan: `../implementation/ENHANCED_VISUALIZATIONS_REPORTING_PLAN.md`
3. Check the main README: `README.md`
4. Review widget library code: `components/visualizations/widget_library.py`

### Reporting Issues

When reporting issues, include:
- Dashboard layout ID
- Widget configuration
- Error messages
- Steps to reproduce
- Browser and OS information

---

## Quick Reference

### Widget Types
- `kpi_metric` - Single metric with trend
- `chart` - Various chart types
- `table` - Tabular data
- `text` - Markdown content
- `goal_progress` - Goal tracking
- `alert` - Notifications

### Chart Types
- `line`, `bar`, `pie`, `treemap`, `area` (standard)
- `waterfall`, `3d_surface`, `animated` (advanced)

### Grid System
- 12 columns wide
- Unlimited rows
- Position: (row, col)
- Size: (width, height)

### File Locations
- Layouts: `data/dashboard_layouts/*.json`
- Portfolio Data: `portfolio_data_truth.csv`
- Page Code: `pages/10_custom_dashboard.py`

---

**Version**: 1.0  
**Last Updated**: 2026-03-23  
**Phase**: 1 (Foundation)