# UI Integration Guide

## Overview

This guide documents the comprehensive UI integration system for the Retirement Planning Application. The system provides consistent styling, reusable components, loading states, error handling, and accessibility features across all pages.

## Architecture

### Component Structure

```
components/
├── theme.py           # Unified theme configuration
├── ui_components.py   # Reusable UI components
├── navbar.py          # Navigation bar
├── sidebar.py         # Sidebar navigation
└── shared.py          # Shared utilities and helpers
```

## Theme System (`components/theme.py`)

### Color Palette

The application uses a consistent color palette with semantic naming:

```python
from components.theme import Colors

# Primary brand colors
Colors.PRIMARY          # #F63366
Colors.PRIMARY_DARK     # #D12A56
Colors.PRIMARY_LIGHT    # #FF5C8A

# Semantic colors
Colors.SUCCESS          # #21c354 (green)
Colors.WARNING          # #ffa500 (orange)
Colors.ERROR            # #ff4b4b (red)
Colors.INFO             # #4c78a8 (blue)

# Account type colors
Colors.CASH             # Yellow with transparency
Colors.BROKERAGE        # Pink with transparency
Colors.TRADITIONAL      # Green with transparency
Colors.ROTH             # Purple with transparency
```

### Typography

```python
from components.theme import Typography

# Font families
Typography.FONT_FAMILY      # System font stack
Typography.FONT_FAMILY_MONO # Monospace font stack

# Font sizes
Typography.SIZE_XS    # 11px
Typography.SIZE_SM    # 13px
Typography.SIZE_BASE  # 14px
Typography.SIZE_LG    # 16px
Typography.SIZE_XL    # 18px
Typography.SIZE_2XL   # 24px
Typography.SIZE_3XL   # 32px

# Font weights
Typography.WEIGHT_NORMAL    # 400
Typography.WEIGHT_MEDIUM    # 500
Typography.WEIGHT_SEMIBOLD  # 600
Typography.WEIGHT_BOLD      # 700
```

### Spacing

```python
from components.theme import Spacing

Spacing.XS    # 4px
Spacing.SM    # 8px
Spacing.MD    # 12px
Spacing.LG    # 16px
Spacing.XL    # 24px
Spacing.XXL   # 32px
Spacing.XXXL  # 48px
```

### Component Styles

Pre-built style generators for common components:

```python
from components.theme import ComponentStyles

# Card container
card_style = ComponentStyles.card()

# Metric card
metric_style = ComponentStyles.metric_card()

# Alert boxes
alert_style = ComponentStyles.alert("success")  # or "warning", "error", "info"

# Badges
badge_style = ComponentStyles.badge()

# Progress bars
progress_styles = ComponentStyles.progress_bar()

# Buttons
button_style = ComponentStyles.button("primary")  # or "secondary", "outline"
```

### Chart Configuration

```python
from components.theme import ChartConfig

# Get standard chart layout
layout = ChartConfig.get_layout(
    title="My Chart",
    height=400,
    show_legend=True
)

# Get color scale for heatmaps
color_scale = ChartConfig.get_color_scale()

# Get color palette for charts
palette = ChartConfig.get_palette()
```

### Utility Functions

```python
from components.theme import (
    get_status_color,
    get_status_label,
    format_percentage,
    format_delta
)

# Get color based on score
color = get_status_color(75)  # Returns Colors.SUCCESS

# Get status label
label = get_status_label(75)  # Returns "🟢 On Track"

# Format percentage
pct = format_percentage(75.5, decimals=1)  # Returns "75.5%"

# Format delta
delta = format_delta(1500)  # Returns "+1,500"
```

## UI Components (`components/ui_components.py`)

### Loading States

#### Context Manager

```python
from components.ui_components import LoadingState

with LoadingState("Loading data...", icon="📊"):
    # Your code here
    data = fetch_data()
```

#### Function Wrapper

```python
from components.ui_components import with_loading_state

result = with_loading_state(
    func=lambda: expensive_operation(),
    message="Processing...",
    icon="⚙️",
    error_message="Failed to process data"
)
```

### Alert Components

```python
from components.ui_components import show_alert

# Success alert
show_alert("Operation completed successfully!", "success")

# Warning alert
show_alert("Please review your settings", "warning", icon="⚠️")

# Error alert
show_alert("Failed to save data", "error")

# Info alert
show_alert("Data is loading in background", "info", dismissible=True)
```

### Metric Cards

#### Single Metric

```python
from components.ui_components import metric_card

metric_card(
    label="Total Net Worth",
    value="$1,234,567",
    delta="+$50,000",
    delta_color="normal",
    help_text="Your total assets minus liabilities",
    icon="💰"
)
```

#### Metric Grid

```python
from components.ui_components import metric_card_grid

metrics = [
    {
        "label": "Net Worth",
        "value": "$1,234,567",
        "delta": "+5.2%",
        "icon": "💰",
        "help": "Total net worth"
    },
    {
        "label": "Monthly Change",
        "value": "$50,000",
        "delta": "+2.1%",
        "icon": "📈",
    },
    # ... more metrics
]

metric_card_grid(metrics, columns=4)
```

### Progress Indicators

#### Simple Progress Bar

```python
from components.ui_components import progress_indicator

progress_indicator(
    label="Portfolio Funding",
    value=750000,
    max_value=1000000,
    show_percentage=True
)
```

#### Score Gauge

```python
from components.ui_components import score_gauge

score_gauge(
    label="Tax Efficiency Score",
    score=75,
    detail="Roth ratio 40% (target 30-50%)",
    thresholds=(50, 75)  # warning at 50, success at 75
)
```

### Status Badges

```python
from components.ui_components import status_badge

# Generate badge HTML
badge_html = status_badge("On Track", "success")
st.markdown(badge_html, unsafe_allow_html=True)
```

### Info Cards

```python
from components.ui_components import info_card

info_card(
    title="Important Notice",
    content="Your portfolio data is being refreshed in the background.",
    icon="ℹ️",
    color=Colors.INFO
)
```

### Section Headers

```python
from components.ui_components import section_header

section_header(
    title="Financial Overview",
    subtitle="Your complete financial picture at a glance",
    icon="📊",
    divider=True
)
```

### Data Tables

```python
from components.ui_components import styled_dataframe

styled_dataframe(
    df=my_dataframe,
    column_config={
        "Amount": st.column_config.NumberColumn(format="$%d"),
    },
    hide_index=True,
    height=400
)
```

### Empty States

```python
from components.ui_components import empty_state

def add_data():
    st.switch_page("pages/4_portfolio.py")

empty_state(
    message="No portfolio data available",
    icon="📭",
    action_label="Add Portfolio Data",
    action_callback=add_data
)
```

### Collapsible Sections

```python
from components.ui_components import collapsible_section

def render_details():
    st.write("Detailed information here...")
    st.dataframe(df)

collapsible_section(
    title="Advanced Details",
    content_func=render_details,
    expanded=False,
    icon="🔍"
)
```

### Action Lists

```python
from components.ui_components import action_list

actions = [
    "💰 Portfolio gap: $250,000 below target",
    "🔀 Low Roth ratio: Consider conversions",
    "🏥 Healthcare not configured"
]

action_list(
    actions=actions,
    title="Action Items",
    icon="📋",
    expanded=True
)
```

### Comparison Cards

```python
from components.ui_components import comparison_card

comparison_card(
    label="Portfolio Value",
    current=750000,
    target=1000000,
    format_func=lambda x: f"${x:,.0f}",
    show_progress=True
)
```

## Integration Examples

### Example 1: Dashboard Page with Metrics

```python
import streamlit as st
from components.navbar import navbar
from components.shared import init_page
from components.ui_components import (
    section_header,
    metric_card_grid,
    progress_indicator,
    action_list
)

# Initialize page
networth, portfolio_df, _, _, _, _, _, _ = init_page("Dashboard", "📊")

# Navigation
navbar("🏠 Dashboard")

# Header
section_header(
    title="Financial Dashboard",
    subtitle="Your complete financial picture at a glance",
    icon="📊"
)

# Metrics
metrics = [
    {"label": "Net Worth", "value": "$1.2M", "delta": "+5%", "icon": "💰"},
    {"label": "Monthly Change", "value": "$50K", "delta": "+2%", "icon": "📈"},
]
metric_card_grid(metrics, columns=4)

# Progress
st.markdown("### Portfolio Funding")
progress_indicator(
    label="Progress to Retirement Goal",
    value=750000,
    max_value=1000000
)

# Actions
actions = ["Action 1", "Action 2"]
action_list(actions, title="Recommended Actions")
```

### Example 2: Loading Data with Error Handling

```python
from components.ui_components import with_loading_state, show_alert

def load_portfolio_data():
    # Expensive operation
    return fetch_data_from_api()

# Load with loading state
data = with_loading_state(
    func=load_portfolio_data,
    message="Fetching portfolio data...",
    icon="📊",
    error_message="Failed to load portfolio"
)

if data is not None:
    show_alert("Portfolio data loaded successfully!", "success")
    # Process data
else:
    show_alert("Please try again or contact support", "error")
```

### Example 3: Styled Data Display

```python
from components.ui_components import (
    section_header,
    styled_dataframe,
    empty_state
)

section_header("Portfolio Holdings", icon="💼")

if df.empty:
    empty_state(
        message="No holdings found",
        icon="📭",
        action_label="Add Holdings",
        action_callback=lambda: st.switch_page("pages/4_portfolio.py")
    )
else:
    styled_dataframe(
        df=df,
        column_config={
            "Value": st.column_config.NumberColumn(format="$%.2f"),
            "Change": st.column_config.NumberColumn(format="%.2f%%"),
        }
    )
```

## Best Practices

### 1. Consistent Styling

Always use theme constants instead of hardcoded values:

```python
# ❌ Bad
st.markdown('<div style="color: #666;">Text</div>', unsafe_allow_html=True)

# ✅ Good
from components.theme import Colors
st.markdown(f'<div style="color: {Colors.TEXT_SECONDARY};">Text</div>', unsafe_allow_html=True)
```

### 2. Loading States

Always wrap expensive operations with loading states:

```python
# ❌ Bad
data = expensive_operation()

# ✅ Good
from components.ui_components import LoadingState
with LoadingState("Loading...", "⏳"):
    data = expensive_operation()
```

### 3. Error Handling

Provide user-friendly error messages:

```python
# ❌ Bad
try:
    result = risky_operation()
except Exception as e:
    st.error(str(e))

# ✅ Good
from components.ui_components import with_loading_state
result = with_loading_state(
    func=risky_operation,
    message="Processing...",
    error_message="Operation failed. Please check your inputs and try again."
)
```

### 4. Empty States

Always handle empty data gracefully:

```python
# ❌ Bad
st.dataframe(df)  # Crashes if df is empty

# ✅ Good
from components.ui_components import styled_dataframe
styled_dataframe(df)  # Shows friendly empty state
```

### 5. Accessibility

Use semantic HTML and ARIA labels:

```python
# ✅ Good
st.markdown(
    f'<button aria-label="Close dialog" style="{button_style}">×</button>',
    unsafe_allow_html=True
)
```

## Migration Guide

### Updating Existing Pages

1. **Import theme components:**
   ```python
   from components.theme import Colors, Typography, ComponentStyles
   from components.ui_components import section_header, metric_card_grid
   ```

2. **Replace hardcoded colors:**
   ```python
   # Before
   color = "#F63366"
   
   # After
   color = Colors.PRIMARY
   ```

3. **Use component functions:**
   ```python
   # Before
   st.markdown("### My Section")
   st.caption("Description")
   st.markdown("---")
   
   # After
   section_header("My Section", subtitle="Description")
   ```

4. **Add loading states:**
   ```python
   # Before
   data = load_data()
   
   # After
   with LoadingState("Loading data...", "📊"):
       data = load_data()
   ```

## Testing

### Visual Regression Testing

Test components across different screen sizes and themes:

```python
# Test in different contexts
def test_metric_card():
    metric_card("Test", "$1,000", delta="+5%")
    # Verify rendering
```

### Accessibility Testing

Ensure components meet WCAG 2.1 AA standards:

- Color contrast ratios ≥ 4.5:1
- Keyboard navigation support
- Screen reader compatibility
- Focus indicators

## Performance Considerations

1. **Lazy Loading**: Load heavy components only when needed
2. **Caching**: Use `@st.cache_data` for expensive operations
3. **Debouncing**: Debounce user inputs to reduce re-renders
4. **Virtualization**: Use pagination for large datasets

## Support

For questions or issues:
1. Check this guide first
2. Review component source code in `components/`
3. Check existing page implementations for examples
4. Create an issue with reproduction steps

## Changelog

### Version 1.0.0 (2026-03-07)
- Initial UI integration system
- Theme configuration
- Reusable components
- Loading states and error handling
- Comprehensive documentation

---

**Made with Bob** 🤖