"""
components/portfolio_overview.py
=================================
Portfolio Overview Component - Key metrics, visualizations, and quick actions.

Displays:
- Key metrics cards (Total Value, Today's Change, YTD Return, Tax Efficiency)
- Account allocation charts (stacked bar + pie)
- Portfolio treemap by sector/ticker
- Performance vs benchmark chart
- Tax efficiency analysis with recommendations
- Quick action buttons
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

if TYPE_CHECKING:
    from pandas import DataFrame

from components.shared import COLOR_SCALE


def render_portfolio_overview(
    portdf: DataFrame,
    networth: DataFrame,
    curr_month: int,
    curr_year: int,
) -> None:
    """
    Render the Portfolio Overview tab.
    
    Args:
        portdf: Portfolio holdings DataFrame with totals row
        networth: Net worth history DataFrame
        curr_month: Current month (1-12)
        curr_year: Current year
    """
    # Remove totals row for visualizations
    portdf_no_totals = portdf[portdf['Account'] != 'Portfolio Totals'].copy()
    for _col in ['Tax Type', 'Sector', 'Ticker']:
        if _col in portdf_no_totals.columns:
            portdf_no_totals[_col] = portdf_no_totals[_col].fillna('Unknown')  # type: ignore[union-attr]
    portdf_no_totals = portdf_no_totals[
        portdf_no_totals['Current value'].notna() & (portdf_no_totals['Current value'] != 0)  # type: ignore[union-attr]
    ]
    
    # Calculate key metrics
    total_value = float(networth['total'].iloc[-1]) if not networth.empty else 0.0
    
    # Today's change (compare to previous month if available)
    if len(networth) >= 2:
        prev_value = float(networth['total'].iloc[-2])
        today_change = total_value - prev_value
        today_change_pct = (today_change / prev_value * 100) if prev_value else 0.0
    else:
        today_change = 0.0
        today_change_pct = 0.0
    
    # YTD return (compare to start of year)
    ytd_return = 0.0
    ytd_return_pct = 0.0
    if not networth.empty:
        # Find first value of current year
        year_start_idx = networth.index[networth.index.year == curr_year]  # type: ignore[attr-defined]
        if len(year_start_idx) > 0:
            year_start_value = float(networth.loc[year_start_idx[0], 'total'])
            ytd_return = total_value - year_start_value
            ytd_return_pct = (ytd_return / year_start_value * 100) if year_start_value else 0.0
    
    # Tax efficiency score
    try:
        _te_trad = float(networth['tax_deferred'].iloc[-1]) if not networth.empty else 0.0
        _te_roth = float(networth['tax_free'].iloc[-1]) if not networth.empty else 0.0
        _te_brok = float(networth['taxable'].iloc[-1]) if not networth.empty else 0.0
        _te_cash = float(networth['cash'].iloc[-1]) if not networth.empty else 0.0
        _te_total = _te_trad + _te_roth + _te_brok + _te_cash
        _te_score = ((_te_roth + _te_brok) / _te_total * 100) if _te_total > 0 else 0.0
        _roth_ratio = (_te_roth / (_te_roth + _te_trad) * 100) if (_te_roth + _te_trad) > 0 else 0.0
    except Exception:
        _te_score = _roth_ratio = 0.0
        _te_trad = _te_roth = _te_brok = _te_cash = _te_total = 0.0
    
    # ========================================================================
    # KEY METRICS CARDS
    # ========================================================================
    st.markdown("### 📊 Portfolio Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Portfolio Value",
            f"${total_value:,.0f}",
            help="Total value of all holdings across all accounts"
        )
    
    with col2:
        delta_color = "normal" if today_change >= 0 else "inverse"
        st.metric(
            "Month Change",
            f"${abs(today_change):,.0f}",
            f"{today_change_pct:+.1f}%",
            delta_color=delta_color,
            help="Change from previous month"
        )
    
    with col3:
        ytd_delta_color = "normal" if ytd_return >= 0 else "inverse"
        st.metric(
            "YTD Return",
            f"${abs(ytd_return):,.0f}",
            f"{ytd_return_pct:+.1f}%",
            delta_color=ytd_delta_color,
            help="Year-to-date return"
        )
    
    with col4:
        _te_label = "🟢 Excellent" if _te_score >= 60 else ("🟡 Good" if _te_score >= 40 else "🔴 Improve")
        st.metric(
            "Tax Efficiency",
            f"{_te_score:.0f}%",
            _te_label,
            help="(Roth + Taxable Brokerage) / Total Portfolio"
        )
    
    st.markdown("---")
    
    # ========================================================================
    # TAX EFFICIENCY ANALYSIS
    # ========================================================================
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
    
    # ========================================================================
    # ACCOUNT & ASSET ALLOCATION CHARTS
    # ========================================================================
    st.markdown("### 📊 Account & Asset Allocation")
    _alloc_col1, _alloc_col2 = st.columns(2)
    
    with _alloc_col1:
        st.markdown('<h4 style="text-align:center;">Net Worth by Account Type</h4>', unsafe_allow_html=True)
        if not networth.empty:
            _stacked_max = (networth.cash + networth.taxable + networth.tax_deferred + networth.tax_free).max()
            fig_stacked = go.Figure(data=[
                go.Bar(x=networth.index, y=networth.tax_deferred, name='Traditional', marker_color='rgb(139, 224, 164)'),
                go.Bar(x=networth.index, y=networth.tax_free, name='Roth', marker_color='rgb(180, 151, 231)'),
                go.Bar(x=networth.index, y=networth.taxable, name='Broker', marker_color='rgb(254, 136, 177)'),
                go.Bar(x=networth.index, y=networth.cash, name='Cash', marker_color='rgb(246, 207, 113)'),
            ], layout=go.Layout(
                autosize=True, plot_bgcolor='white', paper_bgcolor='white', barmode='stack',
                xaxis=dict(title='Date', tickfont=dict(color='black')),
                yaxis=dict(title='Amount', tickfont=dict(color='black'), range=[0, _stacked_max * 1.1]),
                legend=dict(title='Account Type', orientation='h', yanchor='bottom', y=1.1,
                            groupclick='togglegroup', font=dict(color='black')),
                height=400,
            ))
            st.plotly_chart(fig_stacked, use_container_width=True, key='portfolio_stacked')
        else:
            st.info("📊 Historical data not available")
    
    with _alloc_col2:
        st.markdown('<h4 style="text-align:center;">Current Asset Mix</h4>', unsafe_allow_html=True)
        if not networth.empty:
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
        else:
            st.info("📊 Historical data not available")
    
    st.markdown("---")
    
    # ========================================================================
    # PORTFOLIO TREEMAP
    # ========================================================================
    st.markdown('<h4 style="text-align:center;">Detailed Portfolio Breakdown</h4>', unsafe_allow_html=True)
    if len(portdf_no_totals) > 0:
        _cv = portdf_no_totals['Current value']
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
    else:
        st.info("📊 No holdings to display")
    
    st.markdown("---")
    
    # ========================================================================
    # PORTFOLIO PERFORMANCE VS BENCHMARK
    # ========================================================================
    st.markdown("### 📈 Portfolio Performance vs Benchmark")
    if not networth.empty and len(networth) >= 2:
        _bench_rate = 0.07 / 12
        _start_val = float(networth['total'].iloc[0])
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
        _last_port = float(networth['total'].iloc[-1])
        _last_bench = _bench_vals[-1]
        _vs_bench = _last_port - _last_bench
        _vs_pct = (_vs_bench / _last_bench * 100) if _last_bench else 0.0
        _vs_clr = '#21c354' if _vs_bench >= 0 else '#ff4b4b'
        _vs_lbl = f"{'▲' if _vs_bench >= 0 else '▼'} ${abs(_vs_bench):,.0f} ({_vs_pct:+.1f}%) vs benchmark"
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
    
    st.markdown("---")
    
    # ========================================================================
    # QUICK ACTIONS
    # ========================================================================
    st.markdown("### ⚡ Quick Actions")
    
    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
    
    with action_col1:
        if st.button("📝 Update Holdings", use_container_width=True, help="Edit your portfolio holdings"):
            st.info("Switch to the 'Holdings' tab to edit your portfolio")
    
    with action_col2:
        if st.button("⚖️ Rebalance", use_container_width=True, help="Analyze portfolio drift and rebalancing needs"):
            st.info("Switch to the 'Optimization' tab to run rebalancing analysis")
    
    with action_col3:
        if st.button("🌾 Harvest Losses", use_container_width=True, help="Identify tax-loss harvesting opportunities"):
            st.info("Switch to the 'Optimization' tab to find tax-loss harvesting opportunities")
    
    with action_col4:
        if st.button("📊 View Analytics", use_container_width=True, help="See detailed performance metrics"):
            st.info("Switch to the 'Performance & Analytics' tab for detailed metrics")

# Made with Bob
