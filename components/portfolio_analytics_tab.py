"""
components/portfolio_analytics_tab.py
========================================
Unified Analytics tab for Portfolio Hub.

Four sub-tabs:
  🎯 Factor Analysis   — value/growth/momentum/quality factor exposure (all accounts)
  📊 Direct Index      — portfolio vs RSP benchmark, sector drift, harvest efficiency
  🏦 DAF Bundling      — donor advised fund charitable giving optimisation
  💰 Withdrawals       — tax-efficient withdrawal planning
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from pandas import DataFrame


# ---------------------------------------------------------------------------
# Factor analysis (existing)
# ---------------------------------------------------------------------------
try:
    from components.portfolio_factor_analysis import render_factor_analysis_tab
    FACTOR_ANALYSIS_AVAILABLE = True
except ImportError:
    FACTOR_ANALYSIS_AVAILABLE = False
    render_factor_analysis_tab = None  # type: ignore

# ---------------------------------------------------------------------------
# Direct-index analytics (from Direct_Indexing.py)
# ---------------------------------------------------------------------------
try:
    from components.direct_index_analytics import (
        compute_performance,
        get_harvest_efficiency_series,
        get_sector_drift_table,
    )
    DI_ANALYTICS_AVAILABLE = True
except ImportError:
    DI_ANALYTICS_AVAILABLE = False
    compute_performance = None           # type: ignore
    get_harvest_efficiency_series = None  # type: ignore
    get_sector_drift_table = None         # type: ignore

# ---------------------------------------------------------------------------
# DAF bundling and withdrawals (refactored from portfolio_optimization.py)
# ---------------------------------------------------------------------------
try:
    from components.portfolio_optimization import render_daf_tab, render_withdrawals_tab
    OPTIMIZATION_AVAILABLE = True
except ImportError:
    OPTIMIZATION_AVAILABLE = False
    render_daf_tab = None         # type: ignore
    render_withdrawals_tab = None  # type: ignore


# ==============================================================================
# PUBLIC ENTRY POINT
# ==============================================================================

def render_analytics_tab(
    portdf: "DataFrame",
    networth: "DataFrame",
    curr_month: int,
    curr_year: int,
) -> None:
    """
    Render the Analytics tab (top-level Portfolio Hub tab).

    Args:
        portdf:     Current portfolio display DataFrame (all accounts).
        networth:   Net worth history DataFrame.
        curr_month: Current month (1-12).
        curr_year:  Current year.
    """
    st.markdown("### 📊 Portfolio Analytics")
    st.caption(
        "Factor exposure, direct-index performance vs RSP benchmark, "
        "DAF bundling optimisation, and withdrawal planning."
    )

    factor_sub, di_sub, daf_sub, withdrawal_sub = st.tabs([
        "🎯 Factor Analysis",
        "📊 Direct Index",
        "🏦 DAF Bundling",
        "💰 Withdrawals",
    ])

    with factor_sub:
        _render_factor(portdf, curr_month, curr_year)

    with di_sub:
        _render_di_analytics()

    with daf_sub:
        if OPTIMIZATION_AVAILABLE and render_daf_tab is not None:
            render_daf_tab(portdf, networth, curr_month, curr_year)
        else:
            st.info("DAF Bundling component unavailable.")

    with withdrawal_sub:
        if OPTIMIZATION_AVAILABLE and render_withdrawals_tab is not None:
            render_withdrawals_tab(portdf, networth, curr_month, curr_year)
        else:
            st.info("Withdrawal Planning component unavailable.")


# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

def _render_factor(portdf: "DataFrame", curr_month: int, curr_year: int) -> None:
    if FACTOR_ANALYSIS_AVAILABLE and render_factor_analysis_tab is not None:
        render_factor_analysis_tab(portdf, curr_month, curr_year)
    else:
        st.markdown("#### 🎯 Factor Analysis")
        st.info("Factor Analysis component unavailable.")
        st.markdown("**This section includes:**")
        st.markdown("- Factor Exposure Radar (Value, Growth, Momentum, Quality)")
        st.markdown("- Style Classification vs benchmark")
        st.markdown("- Holdings detail table with factor scores")


def _render_di_analytics() -> None:
    if not DI_ANALYTICS_AVAILABLE:
        st.info("Direct Index Analytics component unavailable.")
        return

    st.markdown("#### 📊 Direct Index Portfolio Analytics")
    st.caption(
        "Performance of your direct-index portfolio vs the RSP equal-weight "
        "S&P 500 benchmark."
    )

    with st.expander("⚙️ Analytics settings", expanded=False):
        acol1, acol2 = st.columns(2)
        with acol1:
            rsp_annual_assumption = st.number_input(
                "RSP annual return assumption (%)",
                min_value=0.0, max_value=30.0,
                value=10.0, step=0.5,
                key="hub_analytics_rsp_return",
                help="Used to estimate RSP benchmark return when live price history is unavailable.",
            )
        with acol2:
            cost_per_trade_input = st.number_input(
                "Cost per trade ($)",
                min_value=0.0, max_value=50.0,
                value=0.0, step=0.50,
                key="hub_analytics_cost_trade",
                help="Set to 0 for zero-commission brokers.",
            )

    with st.spinner("Computing analytics…"):
        perf = compute_performance(
            cost_per_trade=cost_per_trade_input,
            rsp_annual_return_pct=rsp_annual_assumption,
        )

    if perf is None:
        st.info(
            "No direct-index positions found. Use the **⚙️ Setup & Config** tab "
            "to build your portfolio, then import executed positions via **🔗 Connections**."
        )
        return

    st.caption(
        f"As of {perf.as_of_date.strftime('%B %d, %Y')} · "
        f"{perf.number_of_positions:,} positions"
    )

    # Return comparison KPIs
    st.subheader("Return vs Benchmark")
    k1, k2, k3, k4 = st.columns(4)
    delta_color_active = "normal" if perf.active_return_pct >= 0 else "inverse"
    k1.metric("Portfolio Return", f"{perf.total_return_pct:+.2f}%")
    k2.metric(
        "RSP Benchmark",
        f"{perf.rsp_return_pct:+.2f}%",
        help=f"Estimated using {rsp_annual_assumption:.1f}% annual return assumption since inception.",
    )
    k3.metric(
        "Active Return (Alpha)",
        f"{perf.active_return_pct:+.2f}%",
        delta=f"{perf.active_return_pct:+.2f}%",
        delta_color=delta_color_active,
    )
    k4.metric(
        "Information Ratio",
        f"{perf.information_ratio:+.2f}",
        help="Active return ÷ tracking error. >0.5 is generally considered good.",
    )

    # Risk metrics
    r1, r2, r3, r4 = st.columns(4)
    r1.metric(
        "Tracking Error (ann.)",
        f"{perf.tracking_error_pct:.2f}%",
        help="Annualised std-dev of daily active returns vs RSP.",
    )
    r2.metric(
        "After-Tax Return",
        f"{perf.after_tax_return_pct:+.2f}%",
        delta=f"+{perf.harvest_benefit_pct:.2f}% harvest benefit",
        delta_color="normal",
        help="Portfolio return plus estimated tax savings as % of cost basis.",
    )
    r3.metric(
        "Unrealized G/L",
        f"${perf.total_unrealized_gl:+,.0f}",
        delta=f"{(perf.total_unrealized_gl / perf.total_cost_basis * 100):+.2f}%"
        if perf.total_cost_basis > 0 else "0%",
    )
    r4.metric(
        "Portfolio Value",
        f"${perf.total_current_value:,.0f}",
        help=f"Cost basis: ${perf.total_cost_basis:,.0f}",
    )

    st.divider()

    # Trading costs
    st.subheader("Trading Costs")
    tc1, tc2, tc3 = st.columns(3)
    tc1.metric("Executed Harvests", perf.total_trades // 2)
    tc2.metric("Total Trades (buy + sell)", perf.total_trades)
    tc3.metric(
        "Est. Trading Cost",
        f"${perf.estimated_trading_cost:,.2f}",
        delta=f"{perf.trading_cost_pct:.3f}% of portfolio"
        if perf.total_current_value > 0 else "N/A",
        delta_color="inverse" if perf.estimated_trading_cost > 0 else "off",
    )

    st.divider()

    # Sector drift
    st.subheader("Sector Drift vs RSP")
    st.caption(
        "Positive drift = overweight vs RSP equal-weight benchmark. "
        "Negative drift = underweight."
    )

    drift_df = get_sector_drift_table()
    if not drift_df.empty:
        import plotly.graph_objects as go

        colours = ["#3b82d4" if v >= 0 else "#ef4444" for v in drift_df["Drift (pp)"]]
        fig_drift = go.Figure(
            go.Bar(
                x=drift_df["Sector"],
                y=drift_df["Drift (pp)"],
                marker_color=colours,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Portfolio: %{customdata[0]:.2f}%<br>"
                    "RSP: %{customdata[1]:.2f}%<br>"
                    "Drift: %{y:+.2f} pp<extra></extra>"
                ),
                customdata=drift_df[["Portfolio (%)", "RSP (%)"]].values,
            )
        )
        fig_drift.update_layout(
            title="Sector Weight Drift vs RSP (percentage points)",
            xaxis_title="Sector",
            yaxis_title="Drift (pp)",
            height=350,
            margin=dict(t=40, b=60, l=40, r=20),
            plot_bgcolor="#f7f8fa",
            paper_bgcolor="#ffffff",
            yaxis=dict(zeroline=True, zerolinewidth=1.5, zerolinecolor="#e5e7eb"),
        )
        st.plotly_chart(fig_drift, use_container_width=True)

        with st.expander("Full sector drift table", expanded=False):
            st.dataframe(
                drift_df.style.format({
                    "Portfolio (%)": "{:.2f}%",
                    "RSP (%)": "{:.2f}%",
                    "Drift (pp)": "{:+.2f}",
                    "Value ($)": "${:,.0f}",
                }).background_gradient(
                    subset=["Drift (pp)"],
                    cmap="RdYlGn",
                    vmin=-5,
                    vmax=5,
                ),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("No sector data available yet.")

    st.divider()

    # Harvest efficiency
    st.subheader("Cumulative Harvest Savings")
    efficiency_df = get_harvest_efficiency_series()

    if not efficiency_df.empty:
        import plotly.express as px

        fig_eff = px.area(
            efficiency_df,
            x="harvest_date",
            y="cumulative_savings",
            labels={
                "harvest_date": "Date",
                "cumulative_savings": "Cumulative Tax Savings ($)",
            },
            title="Cumulative Estimated Tax Savings Over Time",
            color_discrete_sequence=["#3b82d4"],
        )
        fig_eff.update_layout(
            height=300,
            margin=dict(t=40, b=40, l=40, r=20),
            plot_bgcolor="#f7f8fa",
            paper_bgcolor="#ffffff",
        )
        st.plotly_chart(fig_eff, use_container_width=True)

        latest = efficiency_df.iloc[-1]
        sm1, sm2, sm3 = st.columns(3)
        sm1.metric("Total Harvests", int(latest["harvests_count"]))
        sm2.metric(
            "Cumulative Losses Harvested",
            f"${abs(float(latest['cumulative_losses'])):,.0f}",
        )
        sm3.metric(
            "Cumulative Tax Savings",
            f"${float(latest['cumulative_savings']):,.0f}",
        )
    else:
        st.info("No harvest history yet. Execute your first harvest to see the savings chart.")

# Made with Bob
