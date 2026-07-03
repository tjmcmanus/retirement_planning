"""
pages/4_portfolio_hub.py
========================
💼 Portfolio Hub — Unified portfolio management interface

Consolidates all portfolio features into a single, intuitive interface:
- Overview: Quick snapshot with key metrics and visualizations
- Holdings: Inline editing and data management
- Performance & Analytics: Professional-grade performance metrics
- Optimization: Rebalancing, tax harvesting, DAF bundling, withdrawals
- Connections: Brokerage integration (Phase 2)

This replaces the previous scattered portfolio features across multiple pages.
"""

from __future__ import annotations

import calendar as _calendar
import streamlit as st

from components.navbar import navbar
from components.shared import init_page, auto_rerun_if_rebuilding

# Import tab components (to be created)
try:
    from components.portfolio_overview import render_portfolio_overview
    render_overview_tab = render_portfolio_overview
except ImportError:
    render_overview_tab = None

try:
    from components.portfolio_holdings_editor import render_holdings_tab
except ImportError:
    render_holdings_tab = None

try:
    from components.portfolio_performance import render_performance_tab
except ImportError:
    render_performance_tab = None

try:
    from components.portfolio_optimization import render_rebalancing_tab
except ImportError:
    render_rebalancing_tab = None

try:
    from components.portfolio_harvest_tab import render_harvest_tab
except ImportError:
    render_harvest_tab = None

try:
    from components.portfolio_connections import render_connections_tab
except ImportError:
    render_connections_tab = None

try:
    from components.portfolio_analytics_tab import render_analytics_tab
except ImportError:
    render_analytics_tab = None

try:
    from components.portfolio_tax_records_tab import render_tax_records_tab
except ImportError:
    render_tax_records_tab = None

try:
    from components.portfolio_setup_config_tab import render_setup_config_tab
except ImportError:
    render_setup_config_tab = None

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Portfolio Hub — Financial Planner",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Initialize Page Data
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
) = init_page("💼 Portfolio Hub — Financial Planner", "💼")

navbar("📊 Portfolio")

# ---------------------------------------------------------------------------
# Page Header
# ---------------------------------------------------------------------------
st.title("💼 Portfolio Hub")
st.caption("Unified portfolio management — Overview, Holdings, Performance, Optimization & Connections")

# Show data staleness warning if applicable
if _stale_label:
    st.warning(
        f"⚠️ No portfolio data found for {_calendar.month_name[curr_month]} {curr_year}. "
        f"Showing **{_stale_label}** data instead. Please update your portfolio data.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# Portfolio Data Availability Check
# ---------------------------------------------------------------------------
import threading as _threading
_portfolio_done_event = st.session_state.get("_portfolio_done_event", _threading.Event())

if _portfolio_df.empty:
    with st.spinner("📈 Building portfolio — fetching live prices…"):
        from portfolio import render_portfolio, build_portfolio_display
        _portfolio_done_event.wait(timeout=30)
        portdf = render_portfolio(_eff_port_month, _eff_port_year, _portfolio_done_event)
        if portdf.empty:
            portdf = build_portfolio_display(month=_eff_port_month, year=_eff_port_year)
else:
    portdf = _portfolio_df
    if not _portfolio_done_event.is_set():
        st.caption("📡 Serving cached portfolio data — live prices refreshing in background…")

# ---------------------------------------------------------------------------
# Create Tab Structure
# ---------------------------------------------------------------------------
overview_tab, holdings_tab, performance_tab, rebalancing_tab, harvest_tab, analytics_tab, connections_tab, tax_records_tab, setup_config_tab = st.tabs([
    "📊 Overview",
    "📝 Holdings",
    "📈 Performance & Analytics",
    "⚖️ Rebalancing",
    "🌾 Tax Harvesting",
    "📊 Analytics",
    "🔗 Connections",
    "💰 Tax Records",
    "⚙️ Setup & Config",
])

# ---------------------------------------------------------------------------
# TAB 1: OVERVIEW
# ---------------------------------------------------------------------------
with overview_tab:
    if render_overview_tab is not None:
        render_overview_tab(portdf, networth, curr_month, curr_year)
    else:
        # Temporary fallback until component is created
        st.info("📊 Overview tab component is being migrated. Coming soon!")
        st.markdown("**This tab will include:**")
        st.markdown("- Key metrics cards (Total Value, Today's Change, YTD Return, Tax Efficiency)")
        st.markdown("- Asset allocation treemap")
        st.markdown("- Performance chart vs benchmark")
        st.markdown("- Quick action buttons (Rebalance, Harvest Losses, Update Holdings)")

# ---------------------------------------------------------------------------
# TAB 2: HOLDINGS
# ---------------------------------------------------------------------------
with holdings_tab:
    if render_holdings_tab is not None:
        render_holdings_tab(portdf, curr_month, curr_year, _eff_port_month, _eff_port_year)
    else:
        # Temporary fallback until component is created
        st.info("📝 Holdings editor component is being built. Coming soon!")
        st.markdown("**This tab will include:**")
        st.markdown("- Inline editable data table")
        st.markdown("- Add/delete row functionality")
        st.markdown("- Real-time validation (ticker symbols, dates, numbers)")
        st.markdown("- Automatic price fetching")
        st.markdown("- Save to portfolio_data_truth.csv")
        st.markdown("- Import from CSV / Copy from previous month")
        
        # Show current holdings table as placeholder
        st.markdown("---")
        st.markdown("### Current Holdings (Read-Only)")
        if not portdf.empty:
            st.dataframe(portdf, use_container_width=True, hide_index=True)
        else:
            st.warning("No portfolio data available.")

# ---------------------------------------------------------------------------
# TAB 3: PERFORMANCE & ANALYTICS
# ---------------------------------------------------------------------------
with performance_tab:
    if render_performance_tab is not None:
        render_performance_tab(portdf, networth, curr_month, curr_year)
    else:
        # Temporary fallback until component is created
        st.info("📈 Performance Analytics component is being integrated. Coming soon!")
        st.markdown("**This tab will include:**")
        st.markdown("- Performance summary cards (TWR, MWR, Sharpe, Sortino, Max Drawdown)")
        st.markdown("- Time period selector (1Y, 3Y, 5Y, All)")
        st.markdown("- Benchmark selector (S&P 500, custom ticker)")
        st.markdown("- Visualizations:")
        st.markdown("  - Performance chart with drawdown shading")
        st.markdown("  - Attribution breakdown (contributions vs growth)")
        st.markdown("  - Risk-return scatter plot")
        st.markdown("  - Drawdown recovery timeline")
        st.markdown("- PDF export for financial advisor")
        
        st.markdown("---")
        st.markdown("### Analytics Module Status")
        st.success("✅ portfolio_analytics.py module is complete and ready for integration!")
        st.markdown("**Available Metrics:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Returns:**")
            st.markdown("- Time-Weighted Return (TWR)")
            st.markdown("- Money-Weighted Return (MWR)")
            st.markdown("- Total Return %")
        with col2:
            st.markdown("**Risk Metrics:**")
            st.markdown("- Volatility")
            st.markdown("- Sharpe Ratio")
            st.markdown("- Sortino Ratio")
        with col3:
            st.markdown("**Analysis:**")
            st.markdown("- Maximum Drawdown")
            st.markdown("- Alpha & Beta")
            st.markdown("- Attribution Analysis")

# ---------------------------------------------------------------------------
# TAB 4: REBALANCING
# ---------------------------------------------------------------------------
with rebalancing_tab:
    if render_rebalancing_tab is not None:
        render_rebalancing_tab(portdf, networth, curr_month, curr_year)
    else:
        st.info("⚖️ Rebalancing component unavailable.")

# ---------------------------------------------------------------------------
# TAB 5: TAX HARVESTING
# ---------------------------------------------------------------------------
with harvest_tab:
    if render_harvest_tab is not None:
        render_harvest_tab(portdf, curr_month, curr_year)
    else:
        st.info("🌾 Tax Harvesting component unavailable.")

# ---------------------------------------------------------------------------
# TAB 6: ANALYTICS (Factor Analysis + Direct Index + DAF + Withdrawals)
# ---------------------------------------------------------------------------
with analytics_tab:
    if render_analytics_tab is not None:
        render_analytics_tab(portdf, networth, curr_month, curr_year)
    else:
        st.info("📊 Analytics component unavailable.")

# ---------------------------------------------------------------------------
# TAB 7: CONNECTIONS
# ---------------------------------------------------------------------------
with connections_tab:
    if render_connections_tab is not None:
        render_connections_tab(portdf, curr_month, curr_year)
    else:
        # Fallback to Phase 2 placeholder
        st.markdown("## 🔗 Brokerage Connections")
        st.caption("Automatic portfolio synchronization with your brokerage accounts")
        
        st.info("🚀 **SnapTrade Integration Available** — See setup instructions below")
        
        st.markdown("### Supported Brokerages")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Via SnapTrade:**")
            st.markdown("- ✅ Vanguard")
            st.markdown("- ✅ Fidelity")
            st.markdown("- ✅ Schwab")
            st.markdown("- ✅ TD Ameritrade")
            st.markdown("- ✅ E*TRADE")
            st.markdown("- ✅ 12,000+ other institutions")
        
        with col2:
            st.markdown("**Features:**")
            st.markdown("- 🔄 Automatic sync")
            st.markdown("- 🔄 Real-time balances")
            st.markdown("- 🔄 Secure OAuth 2.0")
            st.markdown("- 🔄 Encrypted storage")
        
        st.markdown("---")
        st.markdown("### Setup Required")
        st.markdown("To enable brokerage connections:")
        st.markdown("1. Install dependencies: `pip install snaptrade-python cryptography python-dotenv`")
        st.markdown("2. Get SnapTrade API credentials from [snaptrade.com](https://snaptrade.com)")
        st.markdown("3. Configure `.env` file with credentials")
        st.markdown("4. Restart application")
        st.markdown("")
        st.markdown("See `SNAPTRADE_INTEGRATION_PLAN.md` for detailed setup instructions.")

# ---------------------------------------------------------------------------
# TAB 8: TAX RECORDS (Transactions + Cost Basis + Capital Gains + Harvest Savings)
# ---------------------------------------------------------------------------
with tax_records_tab:
    if render_tax_records_tab is not None:
        render_tax_records_tab(curr_year)
    else:
        st.info("💰 Tax Records component unavailable.")

# ---------------------------------------------------------------------------
# TAB 9: SETUP & CONFIG
# ---------------------------------------------------------------------------
with setup_config_tab:
    if render_setup_config_tab is not None:
        render_setup_config_tab()
    else:
        st.info("⚙️ Setup & Config component unavailable.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption("💼 Portfolio Hub — Unified portfolio management for retirement planning")

# ---------------------------------------------------------------------------
# Auto-rerun if portfolio is still building
# ---------------------------------------------------------------------------
auto_rerun_if_rebuilding()

# Made with Bob
