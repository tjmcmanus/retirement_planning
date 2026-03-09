"""
pages/4_portfolio.py
====================
💼 Portfolio — Holdings, performance, tax harvesting, rebalancing, and DAF bundling.

Sub-tabs (st.tabs within the page):
  - Map Of Portfolio  (treemap + benchmark chart)
  - Details           (full holdings table)
  - Tax Harvesting    (loss/gain harvesting with wash-sale replacements)
  - Rebalancing       (drift analysis + action plan)
  - DAF Bundling      (donor advised fund analysis)
"""
from __future__ import annotations

from typing import cast
import calendar as _calendar

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.navbar import navbar
from components.shared import (
    COLOR_SCALE,
    auto_rerun_if_rebuilding,
    init_page,
)
from portfolio import (
    build_portfolio_display,
    color_negative_positive,
    render_portfolio,
)
from portfolio_rebalancing import (
    build_actions_display_df,
    build_holdings_by_class_df,
    build_rebalance_display_df,
    compute_rebalance_plan,
)
from tax_harvesting import (
    analyze_daf_bundling,
    build_harvesting_analysis,
    check_market_drop_trigger,
    classify_harvest_opportunities,
    compute_harvest_summary,
    compute_net_tax_impact,
    get_ltcg_rate_for_income,
    get_ltcg_zero_threshold,
    get_replacement_detail,
    identify_daf_candidates,
)

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
) = init_page("💼 Portfolio — Financial Planner", "💼")

navbar("📊 Portfolio")

st.header("💼 Portfolio")

if _stale_label:
    st.warning(
        f"⚠️ No portfolio data found for {_calendar.month_name[curr_month]} {curr_year}. "
        f"Showing **{_stale_label}** data instead. Please update your portfolio data.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# Ensure portfolio data is available
# ---------------------------------------------------------------------------
import threading as _threading
_portfolio_done_event = st.session_state.get("_portfolio_done_event", _threading.Event())

if _portfolio_df.empty:
    with st.spinner("📈 Building portfolio — fetching live prices…"):
        _portfolio_done_event.wait(timeout=30)
    portdf = render_portfolio(_eff_port_month, _eff_port_year, _portfolio_done_event)
    if portdf.empty:
        portdf = build_portfolio_display(month=_eff_port_month, year=_eff_port_year)
else:
    portdf = _portfolio_df
    if not _portfolio_done_event.is_set():
        st.caption("📡 Serving cached portfolio data — live prices refreshing in background…")

# ---------------------------------------------------------------------------
# Prepare display DataFrames
# ---------------------------------------------------------------------------
portdf_no_totals = portdf[portdf['Account'] != 'Portfolio Totals'].copy()
for _col in ['Tax Type', 'Sector', 'Ticker']:
    if _col in portdf_no_totals.columns:
        portdf_no_totals[_col] = portdf_no_totals[_col].fillna('Unknown')  # type: ignore[union-attr]
portdf_no_totals = portdf_no_totals[
    portdf_no_totals['Current value'].notna() & (portdf_no_totals['Current value'] != 0)  # type: ignore[union-attr]
]

from pandas.io.formats.style import CSSStyles
_styles = cast(CSSStyles, [
    {"selector": "th", "props": [("text-align", "center")]},
    {"selector": "td", "props": [("text-align", "center")]},
])
styled_portdf          = portdf.style.set_table_styles(_styles).map(color_negative_positive)
styled_portdf_no_total = portdf_no_totals.style.set_table_styles(_styles).map(color_negative_positive)  # type: ignore[union-attr]

# ---------------------------------------------------------------------------
# Portfolio Tax Efficiency Score
# ---------------------------------------------------------------------------
try:
    _te_trad  = float(networth['tax_deferred'].iloc[-1]) if not networth.empty else 0.0
    _te_roth  = float(networth['tax_free'].iloc[-1])     if not networth.empty else 0.0
    _te_brok  = float(networth['taxable'].iloc[-1])      if not networth.empty else 0.0
    _te_cash  = float(networth['cash'].iloc[-1])         if not networth.empty else 0.0
    _te_total = _te_trad + _te_roth + _te_brok + _te_cash
    _te_score  = ((_te_roth + _te_brok) / _te_total * 100) if _te_total > 0 else 0.0
    _roth_ratio = (_te_roth / (_te_roth + _te_trad) * 100) if (_te_roth + _te_trad) > 0 else 0.0
except Exception:
    _te_score = _roth_ratio = 0.0
    _te_trad = _te_roth = _te_brok = _te_cash = _te_total = 0.0

st.markdown("### 🧮 Portfolio Tax Efficiency")
st.caption(
    "Measures how much of your portfolio is in tax-flexible accounts (Roth + Taxable Brokerage). "
    "Higher scores provide more flexibility for tax planning and withdrawals."
)

_te_col1, _te_col2, _te_col3, _te_col4 = st.columns(4)
with _te_col1:
    _te_label = "🟢 Excellent" if _te_score >= 60 else ("🟡 Good" if _te_score >= 40 else "🔴 Improve")
    st.metric("Portfolio Tax Efficiency Score", f"{_te_score:.0f}%",
              help="(Roth + Taxable Brokerage) / Total Portfolio. Higher = more tax-flexible assets.")
    st.caption(_te_label)
with _te_col2:
    st.metric("Roth Ratio", f"{_roth_ratio:.0f}%",
              help="Roth / (Roth + Traditional). Higher = more tax-free retirement assets.")
with _te_col3:
    st.metric("Tax-Deferred (Trad)", f"${_te_trad:,.0f}")
with _te_col4:
    st.metric("Tax-Free (Roth)", f"${_te_roth:,.0f}")

# Generate prescriptive recommendations
_te_actions: list[str] = []

if _te_score < 60:
    _tax_flex_gap = 60 - _te_score
    _te_actions.append(
        f"📊 **Tax Efficiency Score is {_te_score:.0f}%** (target: 60%+). "
        f"Increase tax-flexible assets by {_tax_flex_gap:.0f} percentage points."
    )

if _roth_ratio < 30:
    _roth_gap = max(0, (_te_trad + _te_roth) * 0.30 - _te_roth)
    _te_actions.append(
        f"🔄 **Low Roth Ratio ({_roth_ratio:.0f}%)** — Consider Roth conversions. "
        f"Target: Convert ~${_roth_gap:,.0f} to reach 30% Roth ratio (optimal range: 30-50%)."
    )
elif _roth_ratio > 50:
    _te_actions.append(
        f"⚠️ **High Roth Ratio ({_roth_ratio:.0f}%)** — You may have too much in Roth accounts. "
        f"Consider increasing Traditional 401(k)/IRA contributions to balance tax diversification."
    )

if _te_brok < (_te_total * 0.10) and _te_total > 0:
    _brok_target = _te_total * 0.10
    _brok_gap = _brok_target - _te_brok
    _te_actions.append(
        f"💼 **Low Taxable Brokerage ({(_te_brok/_te_total*100):.0f}%)** — "
        f"Consider building taxable brokerage to ${_brok_target:,.0f} (10% of portfolio) "
        f"for tax-loss harvesting and flexible withdrawals."
    )

if _te_trad > (_te_total * 0.60) and _te_total > 0:
    _te_actions.append(
        f"🏦 **High Traditional Balance ({(_te_trad/_te_total*100):.0f}%)** — "
        f"Large Traditional balances create RMD risk at age 73. "
        f"Consider strategic Roth conversions during low-income years."
    )

# Display recommendations
if _te_actions:
    with st.expander(f"💡 {len(_te_actions)} Recommendation(s) to Improve Tax Efficiency", expanded=False):
        st.markdown("**Actionable Steps:**")
        for _te_act in _te_actions:
            st.markdown(f"- {_te_act}")
        st.markdown("---")
        st.markdown("**Why This Matters:**")
        st.markdown(
            "- **Tax Diversification** reduces risk by spreading assets across different tax treatments\n"
            "- **Roth accounts** provide tax-free withdrawals in retirement and no RMDs\n"
            "- **Taxable brokerage** enables tax-loss harvesting and flexible access\n"
            "- **Traditional accounts** offer upfront tax deductions but create RMD obligations at age 73"
        )
else:
    st.success("✅ Your portfolio tax efficiency is well-balanced!")

st.markdown("---")

# ---------------------------------------------------------------------------
# Sub-tabs
# ---------------------------------------------------------------------------
map_tab, details_tab, harvest_tab, rebalance_tab, daf_tab = st.tabs(
    ["Map Of Portfolio", "Details", "🌾 Tax Harvesting", "⚖️ Rebalancing", "🏦 DAF Bundling"]
)

# ============================================================
# MAP OF PORTFOLIO
# ============================================================
with map_tab:
    # Account Breakdown Charts
    st.markdown("### 📊 Account & Asset Allocation")
    _alloc_col1, _alloc_col2 = st.columns(2)
    
    with _alloc_col1:
        st.markdown('<h4 style="text-align:center;">Net Worth by Account Type</h4>', unsafe_allow_html=True)
        _stacked_max = (networth.cash + networth.taxable + networth.tax_deferred + networth.tax_free).max()
        fig_stacked = go.Figure(data=[
            go.Bar(x=networth.index, y=networth.tax_deferred, name='Traditional', marker_color='rgb(139, 224, 164)'),
            go.Bar(x=networth.index, y=networth.tax_free,     name='Roth',        marker_color='rgb(180, 151, 231)'),
            go.Bar(x=networth.index, y=networth.taxable,      name='Broker',      marker_color='rgb(254, 136, 177)'),
            go.Bar(x=networth.index, y=networth.cash,         name='Cash',        marker_color='rgb(246, 207, 113)'),
        ], layout=go.Layout(
            autosize=True, plot_bgcolor='white', paper_bgcolor='white', barmode='stack',
            xaxis=dict(title='Date', tickfont=dict(color='black')),
            yaxis=dict(title='Amount', tickfont=dict(color='black'), range=[0, _stacked_max * 1.1]),
            legend=dict(title='Account Type', orientation='h', yanchor='bottom', y=1.1,
                        groupclick='togglegroup', font=dict(color='black')),
            height=400,
        ))
        st.plotly_chart(fig_stacked, use_container_width=True, key='portfolio_stacked')
    
    with _alloc_col2:
        st.markdown('<h4 style="text-align:center;">Current Asset Mix</h4>', unsafe_allow_html=True)
        _row_last = networth.iloc[-1, 0:4]
        fig_pie = px.pie(
            names=["Cash", "Broker", "Traditional", "Roth"],
            values=_row_last.values,
            color_discrete_sequence=['rgb(246, 207, 113)', 'rgb(254, 136, 177)', 'rgb(139, 224, 164)', 'rgb(180, 151, 231)'],
            title=' ',
        )
        fig_pie.update_traces(
            textinfo='label+percent+value',
            pull=[0, 0, 0, 0],
            hoverinfo='label+percent+value',
            insidetextfont=dict(color='black'),
        )
        fig_pie.update_layout(
            autosize=True, plot_bgcolor='white', paper_bgcolor='white',
            legend=dict(title='Account Type', orientation='h', yanchor='bottom', y=1.1,
                        groupclick='togglegroup', font=dict(color='black')),
            margin=dict(l=1, r=1, b=1, t=1),
            height=400,
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    st.markdown("---")
    
    # Portfolio Treemap
    st.markdown('<h4 style="text-align:center;">Detailed Portfolio Breakdown</h4>', unsafe_allow_html=True)
    _cv      = portdf_no_totals['Current value']
    _midpoint = np.average(_cv, weights=_cv) if _cv.sum() != 0 else 0
    portfolio_by_sector = px.treemap(
        portdf_no_totals, path=['Tax Type', 'Sector', 'Ticker'],
        values='Current value', color='Current value',
        color_continuous_scale=COLOR_SCALE, color_continuous_midpoint=_midpoint, title="",
    )
    portfolio_by_sector.data[0].textinfo = "label+text+value+percent root"
    portfolio_by_sector.update_traces(texttemplate="%{label}<br>$%{value:,.2f}")
    portfolio_by_sector.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    st.plotly_chart(portfolio_by_sector, use_container_width=True)

    st.markdown("---")
    
    # Portfolio Performance vs Benchmark
    st.markdown("### 📈 Portfolio Performance vs Benchmark")
    if not networth.empty and len(networth) >= 2:
        _bench_rate = 0.07 / 12
        _start_val  = float(networth['total'].iloc[0])
        _bench_vals = [_start_val * ((1 + _bench_rate) ** i) for i in range(len(networth))]

        _perf_fig = go.Figure()
        _perf_fig.add_trace(go.Scatter(
            x=networth.index, y=networth['total'],
            mode='lines+markers', name='Your Portfolio',
            line=dict(color='#4c78a8', width=2), marker=dict(size=5),
            hovertemplate='%{x|%b %Y}<br>Portfolio: $%{y:,.0f}<extra></extra>',
        ))
        _perf_fig.add_trace(go.Scatter(
            x=networth.index, y=_bench_vals,
            mode='lines', name='Benchmark (7% p.a.)',
            line=dict(color='#f58518', width=2, dash='dash'),
            hovertemplate='%{x|%b %Y}<br>Benchmark: $%{y:,.0f}<extra></extra>',
        ))
        _perf_fig.add_trace(go.Scatter(
            x=list(networth.index) + list(networth.index[::-1]),
            y=networth['total'].tolist() + _bench_vals[::-1],
            fill='toself', fillcolor='rgba(76,120,168,0.10)',
            line=dict(color='rgba(255,255,255,0)'),
            showlegend=False, hoverinfo='skip',
        ))
        _last_port  = float(networth['total'].iloc[-1])
        _last_bench = _bench_vals[-1]
        _vs_bench   = _last_port - _last_bench
        _vs_pct     = (_vs_bench / _last_bench * 100) if _last_bench else 0.0
        _vs_clr     = '#21c354' if _vs_bench >= 0 else '#ff4b4b'
        _vs_lbl     = f"{'▲' if _vs_bench >= 0 else '▼'} ${abs(_vs_bench):,.0f} ({_vs_pct:+.1f}%) vs benchmark"
        _perf_fig.add_annotation(
            x=networth.index[-1], y=_last_port,
            text=_vs_lbl, showarrow=True, arrowhead=2, arrowcolor=_vs_clr,
            font=dict(color=_vs_clr, size=11),
            bgcolor='white', bordercolor=_vs_clr, borderwidth=1, ax=0, ay=-40,
        )
        _perf_fig.update_layout(
            xaxis_title='Month', yaxis_title='Portfolio Value ($)',
            plot_bgcolor='white', paper_bgcolor='white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            margin=dict(t=40, l=10, r=10, b=10),
            yaxis=dict(tickformat='$,.0f'),
        )
        st.plotly_chart(_perf_fig, use_container_width=True)
    else:
        st.info("📈 Portfolio performance chart requires at least 2 months of historical data.")

# ============================================================
# DETAILS
# ============================================================
with details_tab:
    desired_height = (len(portdf) + 1) * 35 + 3
    st.dataframe(
        styled_portdf,
        height=desired_height,
        column_config={
            "Price":                  st.column_config.NumberColumn("Closing Price", format="dollar"),
            "Current value":          st.column_config.NumberColumn("Current value", format="dollar"),
            "Cost Basis":             st.column_config.NumberColumn("Cost Basis", format="dollar"),
            "Net Return":             st.column_config.NumberColumn("Net Return", format="dollar"),
            "Dividend Amount":        st.column_config.NumberColumn("Dividend", format="dollar"),
            "annual dividend amount": st.column_config.NumberColumn("Annual Div", format="dollar"),
            "dividend yield":         st.column_config.NumberColumn("Yield", format="percent"),
        },
        hide_index=True,
        use_container_width=True,
    )

# Made with Bob

# ============================================================
# TAX HARVESTING
# ============================================================
with harvest_tab:
    st.markdown("## 🌾 Tax Loss & Gain Harvesting (Stock Indexing)")
    st.caption(
        "Analyzes your **Brokerage (taxable) account** holdings to identify opportunities to "
        "harvest losses (offset gains or up to $3,000 of ordinary income) and harvest gains "
        "at the **0% LTCG rate**. Wash-sale-safe replacement securities are suggested."
    )
    st.info(
        "💡 **This tab** identifies *which* positions to harvest today. "
        "To model how harvested losses carry forward, go to "
        "**🎯 Advanced Strategies → 🌾 Capital Loss Harvesting**.",
        icon=None,
    )

    st.markdown("#### ⚙️ Analysis Parameters")
    _h_col1, _h_col2, _h_col3, _h_col4, _h_col5 = st.columns(5)
    with _h_col1:
        _h_agi = st.number_input("Estimated AGI ($)", min_value=0, max_value=2_000_000,
                                  value=80_000, step=1_000, key="harvest_agi")
    with _h_col2:
        _h_marginal = st.number_input("Marginal Tax Rate (%)", min_value=0, max_value=50,
                                       value=22, step=1, key="harvest_marginal")
    with _h_col3:
        _h_loss_thresh = st.number_input("Loss Threshold ($)", min_value=0, max_value=100_000,
                                          value=500, step=100, key="harvest_loss_thresh")
    with _h_col4:
        _h_drop_pct = st.number_input("Market Drop Trigger (%)", min_value=1, max_value=50,
                                       value=10, step=1, key="harvest_drop_pct")
    with _h_col5:
        _h_gain_thresh = st.number_input("Gain Threshold ($)", min_value=0, max_value=100_000,
                                          value=500, step=100, key="harvest_gain_thresh")

    st.markdown("---")
    _h_year        = curr_year
    _h_zero_thresh = get_ltcg_zero_threshold(_h_year)
    _h_ltcg_rate   = get_ltcg_rate_for_income(float(_h_agi), _h_year)
    _h_headroom    = max(0.0, _h_zero_thresh - float(_h_agi))

    _bc1, _bc2, _bc3, _bc4 = st.columns(4)
    with _bc1:
        _rate_color = "🟢" if _h_ltcg_rate == 0.0 else ("🟡" if _h_ltcg_rate == 0.15 else "🔴")
        st.metric("Your LTCG Rate", f"{_rate_color} {_h_ltcg_rate:.0%}")
    with _bc2:
        st.metric("0% LTCG Threshold", f"${_h_zero_thresh:,.0f}")
    with _bc3:
        st.metric("Headroom to 0% Rate", f"${_h_headroom:,.0f}")
    with _bc4:
        _h_strategy_label = (
            "🟢 Harvest Gains (0% rate!)" if _h_ltcg_rate == 0.0
            else ("🟡 Harvest Losses" if _h_ltcg_rate == 0.15 else "🔴 Harvest Losses (High Rate)")
        )
        st.metric("Recommended Strategy", _h_strategy_label)

    st.markdown("---")

    try:
        with st.spinner("Fetching current prices and analyzing brokerage holdings..."):
            _h_analysis = build_harvesting_analysis(curr_month, curr_year)

        if _h_analysis.empty:
            st.info("ℹ️ No taxable (Brokerage) holdings found for the current period.")
        else:
            _h_classified = classify_harvest_opportunities(
                _h_analysis,
                estimated_agi=float(_h_agi),
                year=_h_year,
                loss_threshold=-max(float(_h_loss_thresh), 1.0),
                gain_threshold=float(_h_gain_thresh),
            )
            _h_summary    = compute_harvest_summary(_h_classified)
            _h_tax_impact = compute_net_tax_impact(
                _h_classified,
                estimated_agi=float(_h_agi),
                year=_h_year,
                marginal_ordinary_rate=float(_h_marginal) / 100.0,
            )

            st.markdown("#### 📊 Portfolio Gain/Loss Summary (Brokerage Only)")
            _sm_c1, _sm_c2, _sm_c3, _sm_c4, _sm_c5 = st.columns(5)
            with _sm_c1:
                st.metric("Total Unrealized Gains", f"${_h_summary['total_unrealized_gain']:,.0f}")
            with _sm_c2:
                _loss_val = _h_summary['total_unrealized_loss']
                st.metric("Total Unrealized Losses", f"${abs(_loss_val):,.0f}",
                          delta=f"-${abs(_loss_val):,.0f}" if _loss_val < 0 else None,
                          delta_color="inverse")
            with _sm_c3:
                _net = _h_summary['net_unrealized']
                st.metric("Net Unrealized", f"${_net:,.0f}",
                          delta=f"{'▲' if _net >= 0 else '▼'} ${abs(_net):,.0f}",
                          delta_color="normal" if _net >= 0 else "inverse")
            with _sm_c4:
                st.metric("Harvestable Losses", f"${abs(_h_summary['harvestable_losses']):,.0f}")
            with _sm_c5:
                st.metric("Harvestable Gains @ 0%", f"${_h_summary['harvestable_gains_at_zero']:,.0f}")

            if _h_tax_impact:
                st.markdown("#### 💰 Estimated Tax Impact")
                _ti_c1, _ti_c2, _ti_c3, _ti_c4 = st.columns(4)
                with _ti_c1:
                    st.metric("Net Position", f"${_h_tax_impact.net_position:,.0f}")
                with _ti_c2:
                    st.metric("Tax on Net Gains", f"${_h_tax_impact.tax_on_net_gains:,.0f}")
                with _ti_c3:
                    st.metric("Ordinary Income Offset", f"${_h_tax_impact.ordinary_income_offset:,.0f}")
                with _ti_c4:
                    _net_impact = _h_tax_impact.net_tax_impact
                    st.metric("Net Tax Impact",
                              f"${abs(_net_impact):,.0f} {'Savings' if _net_impact >= 0 else 'Owed'}",
                              delta=f"{'Save' if _net_impact >= 0 else 'Owe'} ${abs(_net_impact):,.0f}",
                              delta_color="normal" if _net_impact >= 0 else "inverse")

            st.markdown("---")
            _h_drop_result = check_market_drop_trigger(_h_analysis, drop_threshold_pct=float(_h_drop_pct))
            if _h_drop_result["triggered"]:
                st.warning(_h_drop_result["message"])
            else:
                st.success(f"✅ {_h_drop_result['message']}")

            st.markdown("---")
            st.markdown("#### 🎯 Harvesting Recommendations")
            _display_cols = [
                "Account", "Symbol", "Name", "Sector",
                "Qty", "Purchase Price", "Current Price",
                "Current Value", "Cost Basis", "Unrealized G/L",
                "Return %", "Days Held", "Gain Type", "Recommendation",
            ]
            _h_display = cast(pd.DataFrame, _h_classified[_display_cols].copy())
            _h_display["Purchase Price"] = cast(pd.Series, _h_display["Purchase Price"]).map(lambda x: f"${x:,.2f}")
            _h_display["Current Price"]  = cast(pd.Series, _h_display["Current Price"]).map(lambda x: f"${x:,.2f}")
            _h_display["Current Value"]  = cast(pd.Series, _h_display["Current Value"]).map(lambda x: f"${x:,.0f}")
            _h_display["Cost Basis"]     = cast(pd.Series, _h_display["Cost Basis"]).map(lambda x: f"${x:,.0f}")
            _h_display["Unrealized G/L"] = cast(pd.Series, _h_display["Unrealized G/L"]).map(lambda x: f"${x:,.0f}")
            _h_display["Return %"]       = cast(pd.Series, _h_display["Return %"]).map(lambda x: f"{x:.1f}%")
            _h_display["Qty"]            = cast(pd.Series, _h_display["Qty"]).map(lambda x: f"{x:,.0f}")
            st.dataframe(_h_display, hide_index=True, height=(len(_h_display) + 1) * 38 + 3, use_container_width=True)

    except Exception as _h_err:
        st.error(f"⚠️ Error running tax harvesting analysis: {_h_err}")

# ============================================================
# REBALANCING
# ============================================================
with rebalance_tab:
    st.markdown("## ⚖️ Portfolio Rebalancing")
    st.caption(
        "Calculates your current Cash / Bonds / Stocks allocation and flags drift from targets. "
        "Rebalancing suggestions prioritise tax-advantaged accounts first."
    )

    # Try to get bucket strategy cumulative target mix as defaults
    _default_cash = 10
    _default_bonds = 10
    _default_stocks = 80
    
    try:
        from config import get_config_manager as _get_rb_bucket_cfg
        from bucket_strategy import load_bucket_config, BucketType
        
        _rb_bucket_cfg = _get_rb_bucket_cfg()
        _rb_bucket_enabled = _rb_bucket_cfg.get("bucket_strategy", "enabled", False)
        
        if _rb_bucket_enabled:
            bucket_config = load_bucket_config(_rb_bucket_cfg)
            
            # Calculate cumulative target mix based on bucket strategy
            # Bucket 1: 100% cash
            # Bucket 2: graduated (average of start and end stock %)
            # Bucket 3: 100% stocks
            
            # Get total portfolio value to calculate weighted averages
            total_value = float(networth["total"].iloc[-1]) if not networth.empty else 0.0
            
            if total_value > 0:
                annual_need = bucket_config.annual_expenses + bucket_config.annual_taxes
                bucket_1_target = annual_need * bucket_config.bucket_1_years
                bucket_2_target = annual_need * bucket_config.bucket_2_years
                bucket_3_target = max(0, total_value - bucket_1_target - bucket_2_target)
                
                # Calculate weighted percentages
                bucket_1_weight = bucket_1_target / total_value
                bucket_2_weight = bucket_2_target / total_value
                bucket_3_weight = bucket_3_target / total_value
                
                # Bucket 1: 100% cash
                cash_from_b1 = 100 * bucket_1_weight
                
                # Bucket 2: graduated allocation (average)
                avg_stocks_b2 = (bucket_config.bucket_2_start_stock_pct + bucket_config.bucket_2_end_stock_pct) / 2
                avg_bonds_b2 = 100 - avg_stocks_b2
                stocks_from_b2 = avg_stocks_b2 * bucket_2_weight
                bonds_from_b2 = avg_bonds_b2 * bucket_2_weight
                
                # Bucket 3: 100% stocks
                stocks_from_b3 = 100 * bucket_3_weight
                
                # Cumulative targets
                _default_cash = round(cash_from_b1)
                _default_bonds = round(bonds_from_b2)
                _default_stocks = round(stocks_from_b2 + stocks_from_b3)
                
                # Ensure they sum to 100
                total = _default_cash + _default_bonds + _default_stocks
                if total != 100:
                    # Adjust stocks to make it exactly 100
                    _default_stocks = 100 - _default_cash - _default_bonds
    except Exception:
        # If bucket strategy not available or any error, use hardcoded defaults
        pass

    st.markdown("#### 🎯 Target Allocation & Drift Threshold")
    _rb_col1, _rb_col2, _rb_col3, _rb_col4 = st.columns(4)
    with _rb_col1:
        _rb_cash_tgt   = st.number_input("Target Cash %",   min_value=0, max_value=100, value=_default_cash, step=1, key="rb_cash_tgt")
    with _rb_col2:
        _rb_bonds_tgt  = st.number_input("Target Bonds %",  min_value=0, max_value=100, value=_default_bonds, step=1, key="rb_bonds_tgt")
    with _rb_col3:
        _rb_stocks_tgt = st.number_input("Target Stocks %", min_value=0, max_value=100, value=_default_stocks, step=1, key="rb_stocks_tgt")
    with _rb_col4:
        _rb_drift      = st.number_input("Drift Threshold %", min_value=1, max_value=20, value=5, step=1, key="rb_drift")

    # Show current total and validation status
    _rb_total = _rb_cash_tgt + _rb_bonds_tgt + _rb_stocks_tgt
    _rb_is_valid = _rb_total == 100
    
    # Display total with color coding
    if _rb_is_valid:
        st.success(f"✅ Target allocation totals: **{_rb_total}%** (Ready to calculate)")
    else:
        st.warning(f"⚠️ Target allocation totals: **{_rb_total}%** (Must equal 100% to calculate rebalancing)")
    
    # Only show the calculate button when targets are valid
    _rb_calculate = st.button(
        "🔄 Calculate Rebalancing Plan",
        disabled=not _rb_is_valid,
        type="primary" if _rb_is_valid else "secondary",
        use_container_width=True,
        key="rb_calculate_btn"
    )
    
    if _rb_calculate and _rb_is_valid:
        st.markdown("---")
        try:
            with st.spinner("Computing rebalancing plan…"):
                _rb_report = compute_rebalance_plan(
                    month=curr_month, year=curr_year,
                    target_cash_pct=float(_rb_cash_tgt),
                    target_bonds_pct=float(_rb_bonds_tgt),
                    target_stocks_pct=float(_rb_stocks_tgt),
                    drift_threshold_pct=float(_rb_drift),
                )

            if _rb_report.drift_triggered:
                st.warning(f"🔴 **Rebalancing Required** — one or more asset classes have drifted more than {_rb_report.drift_threshold_pct:.0f}% from their targets.")
            else:
                st.success(f"✅ **Portfolio is balanced** — all asset classes are within {_rb_report.drift_threshold_pct:.0f}% of their targets.")

            st.markdown(f"#### 📊 Asset Class Allocation  (Total: ${_rb_report.total_portfolio_value:,.0f})")
            _rb_sum_df = build_rebalance_display_df(_rb_report)
            _rb_mc1, _rb_mc2, _rb_mc3 = st.columns(3)
            for _rb_mc, _rb_ac in zip([_rb_mc1, _rb_mc2, _rb_mc3], ["Cash", "Bonds", "Stocks"]):
                _rb_row = _rb_sum_df[_rb_sum_df["Asset Class"] == _rb_ac]
                if not _rb_row.empty:
                    _rb_r = _rb_row.iloc[0]
                    with _rb_mc:
                        _rb_drift_val = float(_rb_r["Drift %"])
                        st.metric(
                            label=_rb_ac,
                            value=f"{_rb_r['Current %']:.1f}%  (${_rb_r['Current Value']:,.0f})",
                            delta=f"{_rb_drift_val:+.1f}% vs {_rb_r['Target %']:.0f}% target",
                            delta_color="normal" if abs(_rb_drift_val) < float(_rb_drift) else "inverse",
                        )

            st.markdown("#### 🔄 Rebalancing Action Plan")
            _rb_act_df = build_actions_display_df(_rb_report)
            if _rb_act_df.empty:
                st.info("No specific actions generated.")
            else:
                for _, _rb_act in _rb_act_df.iterrows():
                    _rb_action_str = str(_rb_act["Action"])
                    _rb_is_sell    = "Sell" in _rb_action_str
                    _rb_is_buy     = "Buy"  in _rb_action_str
                    if _rb_is_sell and "Brokerage" in _rb_action_str:
                        _rb_card_bg, _rb_card_border = "#fff8f0", "#f58518"
                    elif _rb_is_sell:
                        _rb_card_bg, _rb_card_border = "#f0f8ff", "#4c78a8"
                    elif _rb_is_buy:
                        _rb_card_bg, _rb_card_border = "#f0fff4", "#21c354"
                    else:
                        _rb_card_bg, _rb_card_border = "#f8f9fa", "#6c757d"
                    st.markdown(
                        f'<div style="border-left:4px solid {_rb_card_border};background:{_rb_card_bg};'
                        f'padding:12px 16px;border-radius:6px;margin-bottom:10px;">'
                        f'<div style="font-size:14px;font-weight:700;">#{int(_rb_act["Priority"])} — {_rb_action_str} '
                        f'<span style="color:#555;font-weight:400;">[{_rb_act["Asset Class"]}]</span> '
                        f'<span style="font-size:13px;color:#1a73e8;">{_rb_act["Symbol"]}</span></div>'
                        f'<div style="font-size:12px;margin-top:4px;">Account: <b>{_rb_act["Account"]}</b> | '
                        f'Amount: <b>${float(_rb_act["Amount"]):,.0f}</b> | Tax: <b>{_rb_act["Tax Impact"]}</b></div>'
                        f'<div style="font-size:12px;color:#444;margin-top:6px;">{_rb_act["Rationale"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        except Exception as _rb_err:
            st.error(f"⚠️ Error computing rebalancing plan: {_rb_err}")

# ============================================================
# DAF BUNDLING
# ============================================================
with daf_tab:
    st.markdown("## 🏦 Donor Advised Fund (DAF) Bundling")
    st.caption(
        "Identifies long-term appreciated securities in your brokerage account that are ideal "
        "for donating to a Donor Advised Fund — avoiding capital gains tax while maximizing "
        "your charitable deduction."
    )

    st.markdown("#### ⚙️ DAF Analysis Parameters")
    _daf_col1, _daf_col2, _daf_col3 = st.columns(3)
    with _daf_col1:
        _daf_agi = st.number_input("Estimated AGI ($)", min_value=0, max_value=5_000_000,
                                    value=150_000, step=5_000, key="daf_agi")
    with _daf_col2:
        _daf_annual_giving = st.number_input("Annual Charitable Giving ($)", min_value=0,
                                              max_value=500_000, value=5_000, step=500, key="daf_annual_giving")
    with _daf_col3:
        _daf_bundle_years = st.number_input("Bundle Years", min_value=2, max_value=10,
                                             value=3, step=1, key="daf_bundle_years")

    st.markdown("---")

    try:
        # First, get the candidates
        with st.spinner("Analyzing DAF bundling opportunities..."):
            _h_analysis_daf = build_harvesting_analysis(curr_month, curr_year)
            _daf_candidates_list = identify_daf_candidates(
                _h_analysis_daf,
                ltcg_rate=get_ltcg_rate_for_income(float(_daf_agi), curr_year)
            )
            
            # Get required parameters for bundling analysis
            from load_data import get_std_deduction
            from config import get_config_manager
            config_mgr = get_config_manager()
            filing_status = config_mgr.get_filing_status()
            _daf_std_ded_df = get_std_deduction(curr_year, filing_status)
            # Extract standard deduction for the current filing status
            try:
                _daf_std_ded = float(_daf_std_ded_df.iloc[0]['deduction'])
            except (KeyError, IndexError, AttributeError):
                _daf_std_ded = 32200.0  # Default 2026 married filing jointly standard deduction
            _daf_ltcg = get_ltcg_rate_for_income(float(_daf_agi), curr_year)
            
            _daf_analysis = analyze_daf_bundling(
                estimated_agi=float(_daf_agi),
                annual_giving=float(_daf_annual_giving),
                years_to_bundle=int(_daf_bundle_years),
                marginal_rate=0.22,  # Default marginal rate - could be made configurable
                standard_deduction=_daf_std_ded,
                ltcg_rate=_daf_ltcg,
                securities_candidates=_daf_candidates_list,
                year=curr_year,
            )

        if _daf_analysis:
            _daf_c1, _daf_c2, _daf_c3, _daf_c4 = st.columns(4)
            with _daf_c1:
                st.metric("Bundled Contribution", f"${_daf_analysis.bundled_contribution:,.0f}")
            with _daf_c2:
                st.metric("Standard Deduction", f"${_daf_analysis.standard_deduction:,.0f}")
            with _daf_c3:
                st.metric("Deductible Amount", f"${_daf_analysis.deductible_amount:,.0f}")
            with _daf_c4:
                _daf_net = _daf_analysis.tax_savings_vs_standard
                st.metric("Tax Savings", f"${abs(_daf_net):,.0f}",
                          delta=f"{'Save' if _daf_net >= 0 else 'Owe'} ${abs(_daf_net):,.0f}",
                          delta_color="normal" if _daf_net >= 0 else "inverse")

            if _daf_analysis.recommendation:
                if "Strong" in _daf_analysis.recommendation:
                    st.success(f"✅ {_daf_analysis.recommendation}")
                elif "Moderate" in _daf_analysis.recommendation:
                    st.info(f"💡 {_daf_analysis.recommendation}")
                else:
                    st.warning(f"⚠️ {_daf_analysis.recommendation}")

        st.markdown("---")
        st.markdown("#### 🎯 Appreciated Securities — DAF Donation Candidates")
        if _daf_candidates_list:
            _daf_cand_rows = [
                {
                    "Account": c.account, "Symbol": c.symbol, "Name": c.name,
                    "Qty": f"{c.qty:,.2f}", "Cost Basis": f"${c.cost_basis:,.0f}",
                    "Current Value": f"${c.current_value:,.0f}",
                    "Unrealized Gain": f"${c.unrealized_gain:,.0f}",
                    "Gain %": f"{c.gain_pct:.1f}%", "Days Held": c.days_held,
                    "Gain Type": c.gain_type, "CG Tax Avoided": f"${c.avoided_cg_tax:,.0f}",
                }
                for c in _daf_candidates_list
            ]
            st.dataframe(pd.DataFrame(_daf_cand_rows), hide_index=True, use_container_width=True)
        else:
            st.info("ℹ️ No long-term appreciated securities found in your brokerage account.")

    except Exception as _daf_err:
        st.error(f"⚠️ Error running DAF analysis: {_daf_err}")

# ---------------------------------------------------------------------------
# Auto-rerun while background rebuilds are in flight
# ---------------------------------------------------------------------------
auto_rerun_if_rebuilding()
