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
Row 2 : Net Worth Overview (Combined Bar + Trend)
Row 3 : Net Worth Statement (formal balance-sheet HTML table)
Row 4 : Account Mix treemap + Portfolio Mix treemap
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
from components.ui_components import (
    show_alert,
    info_card,
    section_header,
    with_loading_state,
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

navbar("🏠 Dashboard")

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
    _assess = {}  # Initialize outside try block for action items
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

    # Check pre-retirement coverage (while working)
    _p1_preretire_type = _cfg.get("healthcare", "person1_preretirement_coverage_type", "None")
    _p2_preretire_type = _cfg.get("healthcare", "person2_preretirement_coverage_type", "None")
    _p1_preretire_amt  = float(_cfg.get("healthcare", "person1_preretirement_insurance_monthly", 0) or 0)
    _p2_preretire_amt  = float(_cfg.get("healthcare", "person2_preretirement_insurance_monthly", 0) or 0)
    
    # Check retirement coverage (post-retirement, pre-Medicare)
    _p1_retire_type = _cfg.get("healthcare", "person1_retirement_coverage_type", "None")
    _p2_retire_type = _cfg.get("healthcare", "person2_retirement_coverage_type", "None")
    _p1_retire_amt  = float(_cfg.get("healthcare", "person1_aca_insurance_monthly", 0) or 0)
    _p2_retire_amt  = float(_cfg.get("healthcare", "person2_aca_insurance_monthly", 0) or 0)
    
    # Check if each person has both phases covered
    _p1_has_preretire = (_p1_preretire_type != "None" and _p1_preretire_amt > 0)
    _p1_has_retire = (_p1_retire_type != "None" and _p1_retire_amt > 0)
    _p2_has_preretire = (_p2_preretire_type != "None" and _p2_preretire_amt > 0)
    _p2_has_retire = (_p2_retire_type != "None" and _p2_retire_amt > 0)
    
    _p1_fully_covered = _p1_has_preretire and _p1_has_retire
    _p2_fully_covered = _p2_has_preretire and _p2_has_retire
    
    # Calculate healthcare score based on coverage status
    # 100%: BOTH people have BOTH pre-retirement AND retirement coverage configured
    # 80%: At least one person has both phases covered, OR both people have at least one phase
    # 60%: One person has both phases OR multiple partial coverages
    # 40%: Only one phase covered for one person
    # 20%: No coverage configured
    
    if _p1_fully_covered and _p2_fully_covered:
        _healthcare_score = 100.0  # Both people fully covered
    elif _p1_fully_covered or _p2_fully_covered:
        _healthcare_score = 80.0  # One person fully covered
    elif (_p1_has_preretire or _p1_has_retire) and (_p2_has_preretire or _p2_has_retire):
        _healthcare_score = 60.0  # Both people have partial coverage
    elif _p1_has_preretire or _p1_has_retire or _p2_has_preretire or _p2_has_retire:
        _healthcare_score = 40.0  # One person has partial coverage
    else:
        _healthcare_score = 20.0  # No coverage
    
    # Check if ACA marketplace is being used (for detail message)
    _using_aca = (_p1_retire_type == "ACA Marketplace" or _p2_retire_type == "ACA Marketplace")

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
        # Build healthcare detail message based on coverage
        if _healthcare_score == 100:
            _hc_detail = "Both people fully covered (pre-retirement & retirement)"
            if _using_aca:
                _hc_detail += " (includes ACA)"
        elif _healthcare_score == 80:
            _hc_detail = "One person fully covered, complete coverage for second person"
        elif _healthcare_score == 60:
            _hc_detail = "Both people have partial coverage, complete both phases"
        elif _healthcare_score == 40:
            _hc_detail = "One person partially covered, add coverage for second person"
        else:
            _hc_detail = "Configure healthcare coverage in Configuration"
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
        _pct_complete = (_total_assets / _target_port * 100) if _target_port > 0 else 0
        _actions.append(
            f"💰 **Portfolio Funding ({_pct_complete:.0f}% complete):** "
            f"You need ${_gap:,.0f} more to reach your 25x expenses target of ${_target_port:,.0f}. "
            f"Current total assets: ${_total_assets:,.0f}. "
            f"Continue saving and investing to close this gap."
        )
    
    if _estate_score < 50:
        _ep_pct = (_ep_done / _ep_tot * 100) if _ep_tot > 0 else 0
        _actions.append(
            f"⚖️ **Estate Planning ({_ep_pct:.0f}% complete):** "
            f"You have completed {_ep_done} of {_ep_tot} checklist items. "
            f"Visit the Estate Planning page to review and complete remaining items. "
            f"Core documents status: Will ({'✓' if _assess.get('has_will') else '✗'}), "
            f"POA ({'✓' if _assess.get('has_poa') else '✗'}), "
            f"Healthcare Directive ({'✓' if _assess.get('has_healthcare_directive') else '✗'}), "
            f"Beneficiaries Current ({'✓' if _assess.get('beneficiaries_current') else '✗'})."
        )
    
    if _tax_div_score < 50:
        if _roth_r < 30:
            _actions.append(
                f"🔀 **Tax Diversification (Roth ratio: {_roth_r:.0f}%):** "
                f"Your Roth ratio is below the recommended 30-50% range. "
                f"Consider Roth conversions to increase tax-free assets. "
                f"Current: ${_roth_bal:,.0f} Roth vs ${_trad_bal:,.0f} Traditional."
            )
        else:
            _actions.append(
                f"🔀 **Tax Diversification (Roth ratio: {_roth_r:.0f}%):** "
                f"Your Roth ratio is above the recommended 30-50% range. "
                f"Ensure you have sufficient Traditional assets for tax-efficient withdrawals. "
                f"Current: ${_roth_bal:,.0f} Roth vs ${_trad_bal:,.0f} Traditional."
            )
    
    if _ssi_score < 100:
        _p1_ssi_status = f"${_p1_ssi:,.0f}/month at age {_cfg.get('social_security', 'person1_ssi_age', 70)}" if _p1_ssi > 0 else "Not configured"
        _p2_ssi_status = f"${_p2_ssi:,.0f}/month at age {_cfg.get('social_security', 'person2_ssi_age', 70)}" if _p2_ssi > 0 else "Not configured"
        _actions.append(
            f"📋 **Social Security ({_ssi_score:.0f}% complete):** "
            f"{_cfg.get('personal_info', 'person1_name', 'Person 1')}: {_p1_ssi_status}. "
            f"{_cfg.get('personal_info', 'person2_name', 'Person 2')}: {_p2_ssi_status}. "
            f"Add SSI benefit amounts in Configuration → Social Security to complete your retirement income plan."
        )
    
    if _healthcare_score < 100:
        # Build specific action items based on what's missing
        _p1_name = _cfg.get('personal_info', 'person1_name', 'Person 1')
        _p2_name = _cfg.get('personal_info', 'person2_name', 'Person 2')
        _missing_details = []
        
        if not _p1_has_preretire:
            _missing_details.append(f"{_p1_name}'s pre-retirement coverage (while working)")
        if not _p1_has_retire:
            _missing_details.append(f"{_p1_name}'s retirement coverage (post-retirement, pre-Medicare)")
        if not _p2_has_preretire:
            _missing_details.append(f"{_p2_name}'s pre-retirement coverage (while working)")
        if not _p2_has_retire:
            _missing_details.append(f"{_p2_name}'s retirement coverage (post-retirement, pre-Medicare)")
        
        if _missing_details:
            _actions.append(
                f"🏥 **Healthcare Coverage ({_healthcare_score:.0f}% complete):** "
                f"Missing coverage for: {'; '.join(_missing_details)}. "
                f"Go to Configuration → Healthcare to select coverage types (Employer, ACA Marketplace, or Employer Retiree) "
                f"and enter monthly premium amounts for complete protection."
            )
    
    if _cash_score < 50:
        _cash_months = (_cash_bal / (_annual_exp / 12)) if _annual_exp > 0 else 0
        _target_months = (_cash_target / (_annual_exp / 12)) if _annual_exp > 0 else 0
        _actions.append(
            f"🏦 **Cash/Emergency Fund ({_cash_score:.0f}% complete):** "
            f"Current balance: ${_cash_bal:,.0f} ({_cash_months:.1f} months of expenses). "
            f"Target: ${_cash_target:,.0f} ({_target_months:.1f} months). "
            f"Build your emergency fund by ${_cash_target - _cash_bal:,.0f} to provide adequate liquidity buffer."
        )

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
