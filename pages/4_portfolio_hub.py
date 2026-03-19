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
    from components.portfolio_optimization import render_optimization_tab
except ImportError:
    render_optimization_tab = None

try:
    from components.portfolio_connections import render_connections_tab
except ImportError:
    render_connections_tab = None

try:
    from components.portfolio_factor_analysis import render_factor_analysis_tab
except ImportError:
    render_factor_analysis_tab = None

try:
    from components.transaction_history_ui import (
        render_transaction_history_tab,
        render_cost_basis_tab,
        render_capital_gains_tab
    )
    from components.transaction_importer import create_transaction_importer
    from components.transaction_storage import create_transaction_storage
    TRANSACTION_FEATURES_AVAILABLE = True
except ImportError:
    render_transaction_history_tab = None
    render_cost_basis_tab = None
    render_capital_gains_tab = None
    create_transaction_importer = None
    create_transaction_storage = None
    TRANSACTION_FEATURES_AVAILABLE = False

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
overview_tab, holdings_tab, performance_tab, optimization_tab, factor_tab, connections_tab, transactions_tab, cost_basis_tab, cap_gains_tab = st.tabs([
    "📊 Overview",
    "📝 Holdings",
    "📈 Performance & Analytics",
    "⚖️ Optimization",
    "🎯 Factor Analysis",
    "🔗 Connections",
    "💳 Transactions",
    "💰 Cost Basis",
    "📈 Capital Gains"
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
# TAB 4: OPTIMIZATION
# ---------------------------------------------------------------------------
with optimization_tab:
    if render_optimization_tab is not None:
        render_optimization_tab(portdf, networth, curr_month, curr_year)
    else:
        # Temporary fallback until component is created
        st.info("⚖️ Optimization component is being consolidated. Coming soon!")
        st.markdown("**This tab will consolidate:**")
        st.markdown("- **Rebalancing:** Drift analysis and tax-efficient action plans")
        st.markdown("- **Tax Loss Harvesting:** Identify loss/gain harvesting opportunities")
        st.markdown("- **DAF Bundling:** Donor advised fund charitable giving optimization")
        st.markdown("- **Withdrawal Planning:** Tax-efficient security liquidation")
        
        st.markdown("---")
        st.markdown("### Temporary Access")
        st.markdown("Until consolidation is complete, these features are available in:")
        st.markdown("- **Current Portfolio Page:** Rebalancing, Tax Harvesting, DAF Bundling tabs")
        st.markdown("- **Advanced Strategies Page:** Capital Loss Harvesting (multi-year modeling)")

# ---------------------------------------------------------------------------
# TAB 5: FACTOR ANALYSIS
# ---------------------------------------------------------------------------
with factor_tab:
    if render_factor_analysis_tab is not None:
        render_factor_analysis_tab(portdf, curr_month, curr_year)
    else:
        # Temporary fallback
        st.info("🎯 Factor Analysis component is being integrated. Coming soon!")
        st.markdown("**This tab will include:**")
        st.markdown("- **Factor Exposure Radar:** Visual representation of Value, Growth, Momentum, Quality")
        st.markdown("- **Style Classification:** Determine portfolio style (Value/Growth/Blend/Quality/Momentum)")
        st.markdown("- **Factor Tilts:** Compare portfolio vs benchmark (S&P 500)")
        st.markdown("- **Top Holdings by Factor:** See which holdings drive each factor exposure")
        st.markdown("- **Holdings Detail Table:** Factor scores for each security")
        
        st.markdown("---")
        st.markdown("### Factor Analysis Module Status")
        st.success("✅ portfolio_factors.py module is complete and ready for integration!")
        st.markdown("**Available Analysis:**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("**💰 Value:**")
            st.markdown("- P/E Ratio")
            st.markdown("- P/B Ratio")
            st.markdown("- P/S Ratio")
            st.markdown("- Dividend Yield")
        with col2:
            st.markdown("**🚀 Growth:**")
            st.markdown("- Earnings Growth")
            st.markdown("- Revenue Growth")
            st.markdown("- EPS Growth")
        with col3:
            st.markdown("**📈 Momentum:**")
            st.markdown("- 1M Return")
            st.markdown("- 3M Return")
            st.markdown("- 6M Return")
            st.markdown("- 12M Return")
        with col4:
            st.markdown("**⭐ Quality:**")
            st.markdown("- ROE")
            st.markdown("- ROA")
            st.markdown("- Debt/Equity")
            st.markdown("- Current Ratio")
            st.markdown("- Profit Margin")

# ---------------------------------------------------------------------------
# TAB 6: CONNECTIONS
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
# Auto-rerun while background rebuilds are in flight
# ---------------------------------------------------------------------------
auto_rerun_if_rebuilding()

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption("💼 Portfolio Hub — Unified portfolio management for retirement planning")
st.caption("Phase 1: UX Consolidation + Performance Analytics | Phase 2: Brokerage Integration | Phase 3: Advanced Features")

# Made with Bob

# ---------------------------------------------------------------------------
# TAB 7: TRANSACTIONS
# ---------------------------------------------------------------------------
with transactions_tab:
    if TRANSACTION_FEATURES_AVAILABLE and render_transaction_history_tab is not None:
        # Initialize transaction components
        if 'transaction_importer' not in st.session_state:
            try:
                if 'snaptrade_connector' in st.session_state:
                    st.session_state.transaction_importer = create_transaction_importer(
                        st.session_state.snaptrade_connector
                    )
                    st.session_state.transaction_storage = create_transaction_storage()
                else:
                    st.warning("⚠️ SnapTrade connector not initialized. Please connect your brokerage account in the Connections tab first.")
                    st.stop()
            except Exception as e:
                st.error(f"Failed to initialize transaction components: {e}")
                st.stop()
        
        # Render transaction history tab
        # Get user_id from environment if available, otherwise use "default"
        import os
        env_user_id = os.getenv("SNAPTRADE_USER_ID", "default")
        
        render_transaction_history_tab(
            connector=st.session_state.get('snaptrade_connector'),
            transaction_importer=st.session_state.get('transaction_importer'),
            transaction_storage=st.session_state.get('transaction_storage'),
            user_id=env_user_id
        )
    else:
        st.markdown("## 💳 Transaction History")
        st.caption("Import and analyze your investment transactions")
        
        st.info("🚀 **Transaction Import Feature Available** — Connect your brokerage account to get started")
        
        st.markdown("### Features")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Transaction Import:**")
            st.markdown("- ✅ Automatic import from SnapTrade")
            st.markdown("- ✅ All transaction types (buy, sell, dividend, etc.)")
            st.markdown("- ✅ Customizable date ranges")
            st.markdown("- ✅ Multi-account support")
        
        with col2:
            st.markdown("**Analysis & Reporting:**")
            st.markdown("- ✅ Transaction history viewing")
            st.markdown("- ✅ Filtering and search")
            st.markdown("- ✅ Interactive visualizations")
            st.markdown("- ✅ Export to CSV/Excel")
        
        st.markdown("---")
        st.markdown("### Getting Started")
        st.markdown("1. Go to the **🔗 Connections** tab")
        st.markdown("2. Connect your brokerage account via SnapTrade")
        st.markdown("3. Return here to import your transaction history")

# ---------------------------------------------------------------------------
# TAB 8: COST BASIS
# ---------------------------------------------------------------------------
with cost_basis_tab:
    if TRANSACTION_FEATURES_AVAILABLE and render_cost_basis_tab is not None:
        # Ensure transaction storage is initialized
        if 'transaction_storage' not in st.session_state:
            st.session_state.transaction_storage = create_transaction_storage()
        
        # Render cost basis tab
        render_cost_basis_tab(
            transaction_storage=st.session_state.transaction_storage,
            user_id="default"
        )
    else:
        st.markdown("## 💰 Cost Basis Tracking")
        st.caption("Track cost basis and tax lots for accurate tax reporting")
        
        st.info("🚀 **Cost Basis Tracking Available** — Import transactions to get started")
        
        st.markdown("### Features")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Cost Basis Calculation:**")
            st.markdown("- ✅ FIFO (First In, First Out)")
            st.markdown("- ✅ LIFO (Last In, First Out)")
            st.markdown("- ✅ Average Cost method")
            st.markdown("- ✅ Tax lot tracking")
        
        with col2:
            st.markdown("**Reporting:**")
            st.markdown("- ✅ Cost basis by symbol")
            st.markdown("- ✅ Detailed tax lot view")
            st.markdown("- ✅ Remaining quantity tracking")
            st.markdown("- ✅ Average cost calculation")
        
        st.markdown("---")
        st.markdown("### Getting Started")
        st.markdown("1. Import your transaction history in the **💳 Transactions** tab")
        st.markdown("2. Cost basis will be automatically calculated")
        st.markdown("3. View detailed tax lots and cost basis here")

# ---------------------------------------------------------------------------
# TAB 9: CAPITAL GAINS
# ---------------------------------------------------------------------------
with cap_gains_tab:
    if TRANSACTION_FEATURES_AVAILABLE and render_capital_gains_tab is not None:
        # Ensure transaction storage is initialized
        if 'transaction_storage' not in st.session_state:
            st.session_state.transaction_storage = create_transaction_storage()
        
        # Render capital gains tab
        render_capital_gains_tab(
            transaction_storage=st.session_state.transaction_storage,
            user_id="default"
        )
    else:
        st.markdown("## 📈 Capital Gains & Losses")
        st.caption("Track realized capital gains and losses for tax reporting")
        
        st.info("🚀 **Capital Gains Reporting Available** — Import transactions to get started")
        
        st.markdown("### Features")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Tax Reporting:**")
            st.markdown("- ✅ Capital gains by tax year")
            st.markdown("- ✅ Short-term vs long-term")
            st.markdown("- ✅ Account-level breakdown")
            st.markdown("- ✅ Symbol-level detail")
        
        with col2:
            st.markdown("**Export:**")
            st.markdown("- ✅ CSV export for tax software")
            st.markdown("- ✅ Detailed transaction records")
            st.markdown("- ✅ Cost basis documentation")
            st.markdown("- ✅ Holding period tracking")
        
        st.markdown("---")
        st.markdown("### Getting Started")
        st.markdown("1. Import your transaction history in the **💳 Transactions** tab")
        st.markdown("2. Capital gains will be automatically calculated")
        st.markdown("3. Select tax year and export for filing")

# ---------------------------------------------------------------------------
# Auto-rerun if portfolio is still building
# ---------------------------------------------------------------------------
auto_rerun_if_rebuilding()

# Made with Bob
