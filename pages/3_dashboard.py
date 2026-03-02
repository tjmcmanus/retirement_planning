"""
pages/3_dashboard.py
====================
📊 Dashboard — Financial at-a-glance landing page.

Designed to answer "Where am I financially?" in under 10 seconds
for users aged 18–100 with $50K–$100M in net savings, whether in
accumulation or retirement stage.

Layout
------
Row 0 : KPI metric cards (Net Worth, MoM, YTD, 12-month, vs Benchmark)
Row 1 : Financial Plan Readiness Indicator gauge + sub-indicators
Row 2 : Portfolio Tax Efficiency metrics
Row 3 : 3 charts (NW bar, stacked account bar, asset mix pie)
Row 4 : Net Worth Statement (formal balance-sheet HTML table)
Row 5 : Net Worth Trend line chart
Row 6 : Account Mix treemap + Portfolio Mix treemap
"""
from __future__ import annotations

import calendar as _calendar
import json as _json
import os as _os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from streamlit_extras.add_vertical_space import add_vertical_space

from components.navbar import navbar
from components.shared import (
    COLOR_PALETTE,
    COLOR_SCALE,
    auto_rerun_if_rebuilding,
    format_currency,
    init_page,
    render_net_worth_statement,
)
from load_data import get_month_account_values, get_networth_by_month

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
) = init_page("📊 Dashboard — Financial Planner", "📊")

navbar("📊 Dashboard")

st.title("📊 Financial Dashboard")
st.caption("Your complete financial picture at a glance.")

# ---------------------------------------------------------------------------
# Guard: need at least 2 months of data
# ---------------------------------------------------------------------------
if networth.empty or len(networth) < 2:
    st.error(
        "⚠️ Insufficient historical data. Need at least 2 months of portfolio data. "
        "Please add data via **Portfolio Data Entry** and return here."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Pre-compute summary figures used across multiple sections
# ---------------------------------------------------------------------------
_current_nw = float(networth["total"].iloc[-1])
_prior_nw   = float(networth["total"].iloc[-2])
_mom_change = _current_nw - _prior_nw
_mom_pct    = (_mom_change / _prior_nw * 100) if _prior_nw else 0.0

_dti = pd.DatetimeIndex(networth.index)
_curr_year_mask = _dti.year == _dti[-1].year  # type: ignore[union-attr]
_ytd_start = (
    float(networth.loc[_curr_year_mask, "total"].iloc[0])
    if _curr_year_mask.any() else _current_nw
)
_ytd_gain = _current_nw - _ytd_start

_twelve_ago    = _dti[-1] - pd.DateOffset(months=12)
_older         = networth.loc[networth.index <= _twelve_ago]
_rolling_start = float(_older["total"].iloc[-1]) if not _older.empty else float(networth["total"].iloc[0])
_rolling_gain  = _current_nw - _rolling_start

# Benchmark comparison (7% annual → monthly compound)
_bench_rate   = 0.07 / 12
_start_val    = float(networth["total"].iloc[0])
_bench_vals   = [_start_val * ((1 + _bench_rate) ** i) for i in range(len(networth))]
_last_bench   = _bench_vals[-1]
_vs_bench     = _current_nw - _last_bench
_vs_bench_pct = (_vs_bench / _last_bench * 100) if _last_bench else 0.0

# ---------------------------------------------------------------------------
# ROW 0 — KPI Metric Cards
# ---------------------------------------------------------------------------
st.markdown("### 💡 Key Metrics")
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

with kpi1:
    st.metric(
        "💰 Total Net Worth",
        f"${_current_nw:,.0f}",
        help="Current total net worth across all accounts.",
    )
with kpi2:
    st.metric(
        "📅 Month-over-Month",
        f"${abs(_mom_change):,.0f}",
        delta=f"{_mom_pct:+.1f}%",
        delta_color="normal" if _mom_change >= 0 else "inverse",
        help="Change in net worth vs. last month.",
    )
with kpi3:
    _ytd_pct = abs(_ytd_gain / _ytd_start * 100) if _ytd_start else 0.0
    st.metric(
        "📆 Year-to-Date Gain",
        f"${abs(_ytd_gain):,.0f}",
        delta=f"{'▲' if _ytd_gain >= 0 else '▼'} {_ytd_pct:.1f}%",
        delta_color="normal" if _ytd_gain >= 0 else "inverse",
        help="Net worth change since January 1st of the current year.",
    )
with kpi4:
    _roll_pct = abs(_rolling_gain / _rolling_start * 100) if _rolling_start else 0.0
    st.metric(
        "📈 12-Month Rolling",
        f"${abs(_rolling_gain):,.0f}",
        delta=f"{'▲' if _rolling_gain >= 0 else '▼'} {_roll_pct:.1f}%",
        delta_color="normal" if _rolling_gain >= 0 else "inverse",
        help="Net worth change over the last 12 months.",
    )
with kpi5:
    st.metric(
        "🏆 vs 7% Benchmark",
        f"${abs(_vs_bench):,.0f}",
        delta=f"{'▲' if _vs_bench >= 0 else '▼'} {abs(_vs_bench_pct):.1f}%",
        delta_color="normal" if _vs_bench >= 0 else "inverse",
        help="How your portfolio compares to a 7% annual benchmark since the first recorded month.",
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# ROW 1 — Financial Plan Readiness Indicator (RRI)
# ---------------------------------------------------------------------------
st.markdown("### 🎯 Financial Plan Readiness Indicator")
st.caption(
    "A composite snapshot of how prepared you are across key retirement planning dimensions. "
    "Each indicator is scored 0–100."
)

try:
    from config import get_config_manager as _get_cfg
    _cfg = _get_cfg()

    _annual_exp  = float(_cfg.get("financial_assumptions", "expected_annual_expenses", 50_000) or 50_000)
    _target_port = _annual_exp * 25.0
    try:
        _re_props     = _cfg.get("real_estate", "properties", []) or []
        _re_total_rri = sum(float(p.get("purchase_price", 0) or 0) for p in _re_props)
    except Exception:
        _re_total_rri = 0.0
    _total_assets  = _current_nw + _re_total_rri
    _funding_pct   = min(_total_assets / _target_port * 100, 100) if _target_port > 0 else 0.0
    _funding_score = _funding_pct

    _estate_score = 0.0
    _ep_done, _ep_tot = 0, 0
    try:
        if _os.path.exists("estate_planning_data.json"):
            with open("estate_planning_data.json") as _ef:
                _ed = _json.load(_ef)
            def _count_done(d: dict) -> tuple[int, int]:
                tot, done = 0, 0
                for v in d.values():
                    if isinstance(v, dict):
                        if "done" in v:
                            tot += 1
                            if v["done"]: done += 1
                        else:
                            s_done, s_tot = _count_done(v)
                            done += s_done; tot += s_tot
                return done, tot
            _ep_done, _ep_tot = _count_done(_ed)
            _assess = _ed.get("assessment", {})
            _core_checks = ["has_will", "has_poa", "has_healthcare_directive", "beneficiaries_current"]
            _core_done = sum(1 for k in _core_checks if _assess.get(k, False))
            _estate_score = min((_ep_done / _ep_tot * 70 if _ep_tot > 0 else 0) + (_core_done / len(_core_checks) * 30), 100)
    except Exception:
        _estate_score = 0.0

    _trad_bal      = float(networth["tax_deferred"].iloc[-1]) if not networth.empty else 0.0
    _roth_bal      = float(networth["tax_free"].iloc[-1])     if not networth.empty else 0.0
    _roth_r        = (_roth_bal / (_roth_bal + _trad_bal) * 100) if (_roth_bal + _trad_bal) > 0 else 0.0
    _tax_div_score = max(0.0, 100.0 - abs(_roth_r - 40.0) * 2.5)

    _p1_ssi    = float(_cfg.get("social_security", "person1_ssi_amount", 0) or 0)
    _p2_ssi    = float(_cfg.get("social_security", "person2_ssi_amount", 0) or 0)
    _ssi_score = 100.0 if (_p1_ssi > 0 and _p2_ssi > 0) else (50.0 if (_p1_ssi > 0 or _p2_ssi > 0) else 0.0)

    _aca_enrolled     = bool(_cfg.get("healthcare", "aca_marketplace_enrolled", False))
    _p1_aca_amt       = float(_cfg.get("healthcare", "person1_aca_insurance_monthly", 0) or 0)
    _p2_aca_amt       = float(_cfg.get("healthcare", "person2_aca_insurance_monthly", 0) or 0)
    _healthcare_score = 100.0 if (_aca_enrolled and (_p1_aca_amt > 0 or _p2_aca_amt > 0)) else (
        60.0 if (_p1_aca_amt > 0 or _p2_aca_amt > 0) else 20.0
    )

    _target_months   = int(_cfg.get("financial_assumptions", "accumulation_cash_buffer_months", 6) or 6)
    _wages_total     = (
        float(_cfg.get("income", "person1_annual_wages", 0) or 0) +
        float(_cfg.get("income", "person2_annual_wages", 0) or 0)
    )
    _cash_bal        = float(networth["cash"].iloc[-1]) if not networth.empty else 0.0
    _yrs_cash        = float(_cfg.get("financial_assumptions", "years_of_expenses_in_cash", 4) or 4)
    _cash_target_ret = _annual_exp * _yrs_cash
    _cash_target     = _wages_total * _target_months / 12 if _wages_total > 0 else _cash_target_ret
    _cash_score      = min(_cash_bal / _cash_target * 100, 100) if _cash_target > 0 else 50.0

    _weights = [0.35, 0.20, 0.15, 0.10, 0.10, 0.10]
    _scores  = [_funding_score, _estate_score, _tax_div_score, _ssi_score, _healthcare_score, _cash_score]
    _overall = sum(w * s for w, s in zip(_weights, _scores))

    def _rri_color(score: float) -> str:
        if score >= 75: return "#21c354"
        if score >= 50: return "#ffa500"
        return "#ff4b4b"

    def _rri_label(score: float) -> str:
        if score >= 75: return "🟢 On Track"
        if score >= 50: return "🟡 Needs Attention"
        return "🔴 Action Required"

    _gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=_overall,
        delta={"reference": 75, "valueformat": ".0f"},
        title={"text": "Overall Retirement Readiness", "font": {"size": 16}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": _rri_color(_overall)},
            "steps": [
                {"range": [0,  50], "color": "rgba(255,75,75,0.15)"},
                {"range": [50, 75], "color": "rgba(255,165,0,0.15)"},
                {"range": [75,100], "color": "rgba(33,195,84,0.15)"},
            ],
            "threshold": {"line": {"color": "#333", "width": 3}, "thickness": 0.75, "value": 75},
        },
        number={"suffix": "%", "valueformat": ".0f"},
    ))
    _gauge_fig.update_layout(height=260, margin=dict(t=40, b=10, l=20, r=20), paper_bgcolor="white")

    _rri_col_gauge, _rri_col_metrics = st.columns([2, 3])
    with _rri_col_gauge:
        st.plotly_chart(_gauge_fig, use_container_width=True)
        st.markdown(
            f'<p style="text-align:center;font-size:18px;font-weight:700;'
            f'color:{_rri_color(_overall)}">{_rri_label(_overall)}</p>',
            unsafe_allow_html=True,
        )

    with _rri_col_metrics:
        _ssi_detail = (
            "Both persons configured" if _ssi_score == 100
            else ("One person configured" if _ssi_score == 50
                  else "Not configured — add SSI amounts in Configuration")
        )
        _hc_detail = (
            "ACA enrolled & premiums set" if _healthcare_score == 100
            else ("Premiums set" if _healthcare_score == 60
                  else "Configure ACA/Medicare in Configuration")
        )
        _ind_labels = [
            ("💰 Portfolio Funding",    _funding_score,    f"{_funding_pct:.0f}% of 25x expenses target  (${_total_assets:,.0f} / ${_target_port:,.0f})"),
            ("⚖️ Estate Planning",      _estate_score,     f"{_ep_done if _estate_score > 0 else 0} of {_ep_tot if _estate_score > 0 else '?'} checklist items complete"),
            ("🔀 Tax Diversification",  _tax_div_score,    f"Roth ratio {_roth_r:.0f}%  (target 30-50%)"),
            ("📋 Social Security",      _ssi_score,        _ssi_detail),
            ("🏥 Healthcare Coverage",  _healthcare_score, _hc_detail),
            ("🏦 Cash / Emergency Fund",_cash_score,       f"${_cash_bal:,.0f} vs ${_cash_target:,.0f} target"),
        ]
        for _ind_name, _ind_score, _ind_detail in _ind_labels:
            _bar_color = _rri_color(_ind_score)
            _bar_pct   = int(_ind_score)
            st.markdown(
                f'<div style="margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-size:13px;font-weight:600;">{_ind_name}</span>'
                f'<span style="font-size:13px;color:{_bar_color};font-weight:700;">{_bar_pct}%</span>'
                f'</div>'
                f'<div style="background:#e9ecef;border-radius:4px;height:8px;margin:3px 0;">'
                f'<div style="background:{_bar_color};width:{_bar_pct}%;height:8px;border-radius:4px;"></div>'
                f'</div>'
                f'<div style="font-size:11px;color:#666;">{_ind_detail}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    _actions: list[str] = []
    if _funding_score < 75:
        _gap = _target_port - _total_assets
        _actions.append(f"💰 **Portfolio gap:** ${_gap:,.0f} below the 25x expenses target.")
    if _estate_score < 50:
        _actions.append("⚖️ **Estate planning incomplete.** Visit the Estate Planning page.")
    if _tax_div_score < 50:
        if _roth_r < 30:
            _actions.append("🔀 **Low Roth ratio.** Consider Roth conversions.")
        else:
            _actions.append("🔀 **High Roth ratio.** Ensure sufficient Traditional assets.")
    if _ssi_score < 100:
        _actions.append("📋 **Social Security not fully configured.** Add SSI amounts in Configuration.")
    if _healthcare_score < 60:
        _actions.append("🏥 **Healthcare coverage not configured.** Add ACA premiums in Configuration.")
    if _cash_score < 50:
        _actions.append(f"🏦 **Cash buffer below target.** Current: ${_cash_bal:,.0f}. Build toward ${_cash_target:,.0f}.")

    if _actions:
        with st.expander(f"📋 {len(_actions)} Action Item(s) to Improve Your Score", expanded=False):
            for _act in _actions:
                st.markdown(f"- {_act}")
    else:
        st.success("✅ All retirement readiness indicators are on track!")

except Exception as _rri_err:
    st.warning(f"⚠️ Could not compute retirement readiness indicator: {_rri_err}")

st.markdown("---")

# ---------------------------------------------------------------------------
# ROW 2 — Portfolio Tax Efficiency Score
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

add_vertical_space(1)

st.markdown("---")

# ---------------------------------------------------------------------------
# ROW 3 — Net Worth Overview (Combined Bar + Trend)
# ---------------------------------------------------------------------------
st.markdown("### 📊 Net Worth Overview")
st.caption("For detailed account breakdowns and asset allocation, visit the **💼 Portfolio** page.")

# Combined bar chart with trend line overlay
_nw_labels = pd.DatetimeIndex(networth.index).strftime("%b %Y")
fig_nw_combined = go.Figure()

# Add bars
fig_nw_combined.add_trace(go.Bar(
    x=networth.index,
    y=networth['total'],
    name='Net Worth',
    marker=dict(
        color=networth['total'],
        colorscale=COLOR_SCALE,
        showscale=False,
    ),
    hovertemplate='%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>',
))

# Add trend line
fig_nw_combined.add_trace(go.Scatter(
    x=networth.index,
    y=networth['total'],
    mode='lines+markers',
    name='Trend',
    line=dict(color='#4c78a8', width=3),
    marker=dict(size=8, color='#4c78a8', line=dict(color='white', width=2)),
    hovertemplate='%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>',
))

# Add month-over-month annotation
_last_val  = float(networth['total'].iloc[-1])
_prev_val  = float(networth['total'].iloc[-2])
_mom_delta = _last_val - _prev_val
_mom_pct_t = (_mom_delta / _prev_val * 100) if _prev_val else 0.0
_arrow_clr = '#21c354' if _mom_delta >= 0 else '#ff4b4b'
fig_nw_combined.add_annotation(
    x=networth.index[-1], y=_last_val,
    text=f"{'▲' if _mom_delta >= 0 else '▼'} ${abs(_mom_delta):,.0f} ({_mom_pct_t:+.1f}%)",
    showarrow=True, arrowhead=2, arrowcolor=_arrow_clr,
    font=dict(color=_arrow_clr, size=12, weight='bold'),
    bgcolor='white', bordercolor=_arrow_clr, borderwidth=2,
    ax=0, ay=-40,
)

_y_min = networth['total'].min()
_y_max = networth['total'].max()
_y_rng = _y_max - _y_min
fig_nw_combined.update_layout(
    title='Net Worth Trend (All Time)',
    xaxis_title='Month',
    yaxis_title='Net Worth ($)',
    plot_bgcolor='white',
    paper_bgcolor='white',
    showlegend=True,
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    xaxis=dict(tickfont=dict(color='black'), tickangle=-45),
    yaxis=dict(
        tickfont=dict(color='black'),
        tickformat='$,.0f',
        range=[_y_min - _y_rng * 0.1, _y_max + _y_rng * 0.15]
    ),
    height=450,
    margin=dict(t=60, l=10, r=10, b=10),
)

st.plotly_chart(fig_nw_combined, use_container_width=True)

add_vertical_space(1)

# ---------------------------------------------------------------------------
# ROW 4 — Net Worth Statement (formal balance-sheet)
# ---------------------------------------------------------------------------
try:
    _nw_detailed_df, _ = get_networth_by_month(curr_month, curr_year)
except Exception:
    _nw_detailed_df = pd.DataFrame()
render_net_worth_statement(networth, _nw_detailed_df)

# ---------------------------------------------------------------------------
# ROW 6 — Treemaps: Account Mix + Portfolio Mix
# ---------------------------------------------------------------------------
if _stale_label:
    st.warning(
        f"⚠️ No portfolio data found for {_calendar.month_name[curr_month]} {curr_year}. "
        f"Showing **{_stale_label}** data instead. Please update your portfolio data.",
        icon="⚠️",
    )

tab1_row2_col1, tab1_row2_col2 = st.columns(2)

with tab1_row2_col1:
    st.markdown('<h4 style="text-align:center;">Account Mix Breakdown</h4>', unsafe_allow_html=True)
    mtd_spend, _, _ = get_month_account_values(_eff_port_month, _eff_port_year)
    if not mtd_spend.empty:
        _mid = (
            np.average(mtd_spend['market_value'], weights=mtd_spend['market_value'])
            if mtd_spend['market_value'].sum() != 0 else 0
        )
        fig_acct_mix = px.treemap(
            mtd_spend, path=['account_type', 'account_name'],
            values='market_value', color='market_value',
            color_continuous_scale=COLOR_SCALE, color_continuous_midpoint=_mid, title="",
        )
        fig_acct_mix.data[0].textinfo = "label+text+value+percent root"
        fig_acct_mix.update_layout(margin=dict(t=50, l=25, r=25, b=25))
        st.plotly_chart(fig_acct_mix, use_container_width=True)
    else:
        st.info("No account data available for the current period.")

with tab1_row2_col2:
    st.markdown('<h4 style="text-align:center;">Portfolio Mix</h4>', unsafe_allow_html=True)
    if not _portfolio_cache_ready:
        st.info(
            "⏳ Portfolio data is loading in the background… "
            "The chart will appear automatically once prices are fetched.",
            icon="📊",
        )
    else:
        portdf_no_totals = _portfolio_df[_portfolio_df['Account'] != 'Portfolio Totals'].copy()
        if portdf_no_totals.empty:
            st.info("No portfolio data available. Please add portfolio data via Portfolio Data Entry.")
        else:
            portdf_treemap = portdf_no_totals[
                portdf_no_totals['Sector'].notna() & (portdf_no_totals['Sector'] != '')  # type: ignore[union-attr]
            ].copy()
            if not portdf_treemap.empty:  # type: ignore[union-attr]
                _pmid = (
                    np.average(portdf_treemap['Current value'], weights=portdf_treemap['Current value'])
                    if portdf_treemap['Current value'].sum() != 0 else 0
                )
                fig_port_mix = px.treemap(
                    portdf_treemap, path=['Tax Type', 'Sector'],
                    values='Current value', color='Current value',
                    color_continuous_scale=COLOR_SCALE, color_continuous_midpoint=_pmid, title="",
                )
                fig_port_mix.data[0].textinfo = "label+text+value+percent root"
                fig_port_mix.update_traces(texttemplate="%{label}<br>$%{value:,.2f}")
                fig_port_mix.update_layout(margin=dict(t=50, l=25, r=25, b=25))
                st.plotly_chart(fig_port_mix, use_container_width=True)
            else:
                st.info("No sector data available for portfolio mix chart.")

# ---------------------------------------------------------------------------
# Auto-rerun while background rebuilds are in flight
# ---------------------------------------------------------------------------
auto_rerun_if_rebuilding()
