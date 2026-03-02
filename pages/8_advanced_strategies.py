"""
pages/8_advanced_strategies.py  — 🎯 Advanced Strategies
7 sub-tabs: Tax Planner | Multi-Year Tax | Backdoor Roth | NUA | QCD | SEPP | Capital Loss
"""
from __future__ import annotations
from typing import cast
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from advanced_strategies import (
    SEPP_METHODS, build_multi_year_loss_harvesting_plan, build_rolling_tax_window,
    calculate_backdoor_roth, calculate_mega_backdoor_roth, calculate_nua_analysis,
    calculate_qbi_deduction_full, calculate_qcd_optimization, calculate_sepp,
)
from betr_roth_conversion import BETRInputs, calculate_betr
from calculations import (
    calc_agi, calc_daf_value, calc_roth_conversions, calc_roth_conversions_tax,
    calculate_atm, calculate_cap_gains, calculate_irmma_penalty, calculate_taxable_income,
    get_std_deduction_by_year, getlower_atm_amount_n_deduction, getUpperIncomeRate,
)
from components.navbar import navbar
from components.shared import auto_rerun_if_rebuilding, init_page
from load_data import get_atm_costs, get_cap_gains_brackets, get_income_tax_brackets, get_medicare_costs, get_std_deduction

(networth, _pdf, _pcr, _sl, curr_month, curr_year, _epm, _epy) = init_page("🎯 Advanced Strategy Tools", "🎯")
navbar("Advanced Strategy Tools")
st.header("🎯 Advanced Strategy Tools")
st.markdown("Multi-year tax planning, backdoor Roth, NUA, QCD, and 72(t) SEPP calculators.")
st.markdown("---")

def _cs() -> None:
    st.session_state["submit"] = False

(adv_tax_planner_tab, adv_tax_tab, adv_backdoor_tab, adv_nua_tab,
 adv_qcd_tab, adv_sepp_tab, adv_harvest_tab) = st.tabs([
    "🧮 Tax Planner", "📅 Multi-Year Tax Planning", "🔄 Backdoor & Mega Backdoor Roth",
    "📈 NUA Analysis", "🎁 QCD Optimizer", "⏱️ 72(t) SEPP Calculator", "🌾 Capital Loss Harvesting",
])

# ── TAX PLANNER ─────────────────────────────────────────────────────────────
with adv_tax_planner_tab:
    st.subheader("🧮 Tax Planner")
    try:
        cash_value    = float(networth["cash"].iloc[-1])         if not networth.empty else 0.0
        trad_value    = float(networth["tax_deferred"].iloc[-1]) if not networth.empty else 0.0
        roth_value    = float(networth["tax_free"].iloc[-1])     if not networth.empty else 0.0
        taxable_value = float(networth["taxable"].iloc[-1])      if not networth.empty else 0.0
    except Exception:
        cash_value = trad_value = roth_value = taxable_value = 0.0

    with st.expander("Create estimated taxes for next year", expanded=True):
        c5, c6, c7, c8, c14 = st.columns(5)
        wages               = c5.number_input("Wages", key="tp_wages", on_change=_cs)
        deferred_dist       = c6.number_input("Trad IRA Distribution", key="tp_trad_dist", on_change=_cs)
        interest            = c14.number_input("Interest", key="tp_interest", on_change=_cs)
        cg_income_lt        = c7.number_input("Long Term Cap Gains", key="tp_ltcg", on_change=_cs)
        cg_income_st        = c8.number_input("Short Term Cap Gains", key="tp_stcg", on_change=_cs)

        c9, c10, c12, c11, c13 = st.columns(5)
        people       = c9.selectbox("Medicare Eligible", [0, 1, 2], key="tp_medicare", on_change=_cs)
        year         = c10.selectbox("Tax Year", [2023, 2024, 2025, 2026, 2027], key="tp_year", on_change=_cs, index=3)
        maxdaf       = c12.selectbox("Max Donor Advisor Fund", ["N", "Y"], key="tp_maxdaf", on_change=_cs)
        with c11:
            daf1 = st.number_input("Charitable Contrib", key="tp_daf1" if maxdaf == "Y" else "tp_daf1b",
                                   disabled=(maxdaf == "Y"), on_change=_cs if maxdaf != "Y" else None)
        headroom_rate = c13.selectbox("Max Conversion Rate", [10, 12, 22, 24, 32, 35, 37],
                                      key="tp_headroom", on_change=_cs, index=3) / 100

        cd1, cd2, _c3, _c4, _c5 = st.columns(5)
        with cd1:
            daf_contribution_type = st.selectbox("DAF Contribution Type", ["securities", "cash"],
                key="tp_daf_type", on_change=_cs,
                help="Securities: 30% AGI limit, avoids cap gains. Cash: 60% AGI limit.")
        with cd2:
            st.info(f"ℹ️ **{'60%' if daf_contribution_type == 'cash' else '30%'}** of AGI limit.", icon=None)

        cb1, cb2, _c6, _c7, _c8 = st.columns(5)
        roth_amount   = cb1.number_input("Roth Conversion Amount", key="tp_roth_amt", on_change=_cs)
        pd_tax_amount = cb2.number_input("Estimated prepaid Fed taxes", key="tp_prepaid", on_change=_cs)
        summarize_button = st.button("Project this years changes!", key="tp_summarize")

    if summarize_button:
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()
            filing_status = config_mgr.get_filing_status()
            taxratedf = cast(pd.DataFrame, get_income_tax_brackets(year))
            cgdf      = cast(pd.DataFrame, get_cap_gains_brackets(year))
            irmaadf   = get_medicare_costs(year)
            stddectdf = get_std_deduction(year, filing_status)
            atmdf     = get_atm_costs(year)
        except Exception as e:
            st.error(f"Error loading tax data: {e}"); st.stop()

        try:
            calc_daf = calc_daf_value(deferred_dist + wages, interest, daf1, maxdaf,
                                      contribution_type=daf_contribution_type,  # type: ignore[arg-type]
                                      stddectdf=cast(pd.DataFrame, stddectdf))
        except Exception:
            calc_daf = 0

        try:
            agi = calc_agi(deferred_dist + wages + cg_income_st, interest, stddectdf, calc_daf)
        except Exception as e:
            st.error(f"AGI error: {e}"); st.stop()

        try:
            irmaa_fees = calculate_irmma_penalty(agi, irmaadf, people)
        except Exception:
            irmaa_fees = 0

        try:
            result = calculate_taxable_income(agi, taxratedf)
            taxable_income, maxrate, uppermax = result.total_tax, result.max_rate, result.upper_max
        except Exception as e:
            st.error(f"Taxable income error: {e}"); st.stop()

        try:
            headroom_max = getUpperIncomeRate(headroom_rate, taxratedf)
        except Exception:
            headroom_max = 0

        if maxrate > headroom_rate:
            st.warning("Current tax rate exceeds target conversion rate")

        try:
            atm_lower, atm_deduction = getlower_atm_amount_n_deduction(None, atmdf)
            get_std_deduction_by_year(year)
            if uppermax >= (atm_lower + atm_deduction):
                uppermax = atm_lower + atm_deduction
        except Exception:
            pass

        try:
            if roth_amount > 0:
                conversions = roth_amount
                conversion_tax = calc_roth_conversions_tax(maxrate, headroom_rate, uppermax, agi, headroom_max, conversions)
            else:
                conversions, conversion_tax = calc_roth_conversions(maxrate, headroom_rate, uppermax, agi, headroom_max, 0)
        except Exception as e:
            st.error(f"Roth conversion error: {e}")
            conversions, conversion_tax = 0, 0

        try:
            if conversions >= 0:
                agi = calc_agi(deferred_dist + wages + cg_income_st + conversions, interest, stddectdf, calc_daf)
                result = calculate_taxable_income(agi, taxratedf)
                taxable_income, maxrate, uppermax = result.total_tax, result.max_rate, result.upper_max
        except Exception:
            pass

        cg_tax = 0
        try:
            if cg_income_lt != 0:
                cg_tax = calculate_cap_gains(agi, cgdf, cg_income_lt)
        except Exception:
            pass

        atm_tax = 0
        try:
            atm_tax, _ = calculate_atm(agi, cg_income_lt, atmdf)
            if taxable_income > atm_tax:
                atm_tax = 0
        except Exception:
            pass

        irmaa_headroom = 0
        try:
            irmaa_headroom = calculate_irmma_penalty(uppermax, irmaadf, people)
        except Exception:
            pass

        r3, r5, r6, r7, r8 = st.columns(5)
        with r3:
            st.markdown("##### Ordinary Income")
            if agi + conversions > 0: st.metric("AGI", f"${agi:,.2f}")
            if interest > 0: st.metric("Interest", f"${interest:,.2f}")
            if cg_income_st > 0: st.metric("ST Cap Gains", f"${cg_income_st:,.2f}")
            if cg_income_lt != 0: st.metric("LT Cap Gains", f"${cg_income_lt:,.2f}")
        with r5:
            st.markdown("##### Taxes Owed")
            state_tax = (wages + cg_income_lt + cg_income_st + interest) * 0.03
            q_fed = (taxable_income + cg_tax - pd_tax_amount) / 4
            q_st  = state_tax / 4
            if taxable_income > 0:
                st.metric("Income Tax", f"${taxable_income + cg_tax - pd_tax_amount:,.2f}")
                st.metric("Quarterly Fed", f"${q_fed:,.2f}")
            if state_tax > 0:
                st.metric("State Tax", f"${state_tax:,.2f}")
                st.metric("Quarterly State", f"${q_st:,.2f}")
            if calc_daf > 0: st.metric("DAF", f"${calc_daf:,.2f}")
            if cg_tax > 0: st.metric("LT Cap Gains Tax", f"${cg_tax:,.2f}")
            if irmaa_fees > 0: st.metric("Medicare Surcharge", f"${irmaa_fees:,.2f}")
            if irmaa_headroom > 0 and conversions > 0: st.metric("Medicare w/ Conversion", f"${irmaa_headroom:,.2f}")
            if atm_tax > taxable_income: st.metric("Additional ATM Taxes", f"${atm_tax - taxable_income:,.2f}")
        with r6:
            st.markdown("##### Traditional")
            if deferred_dist + conversions > 0:
                st.metric("New Trad Balance", f"${trad_value - deferred_dist - conversions:,.2f}",
                          delta=f"{-deferred_dist - conversions:,.2f}")
            else:
                st.metric("Trad Balance", f"${trad_value:,.2f}")
        with r7:
            st.markdown("##### Roth")
            if conversions > 0:
                st.metric("New Roth Balance", f"${roth_value + conversions:,.2f}", delta=f"{conversions:,.2f}")
                st.metric("Conversion", f"${conversions:,.2f}")
                st.metric("Conversion Tax", f"${conversion_tax:,.2f}")
            else:
                st.metric("Roth Balance", f"${roth_value:,.2f}")
        with r8:
            st.markdown("##### Cash & Broker")
            new_cash = cash_value - state_tax - cg_tax - taxable_income + pd_tax_amount
            new_brok = taxable_value - calc_daf + deferred_dist
            if new_cash != cash_value:
                st.metric("New Cash", f"${new_cash:,.2f}", delta=f"{new_cash - cash_value:,.2f}")
            else:
                st.metric("Cash Balance", f"${cash_value:,.2f}")
            if new_brok != taxable_value:
                st.metric("New Broker", f"${new_brok:,.2f}", delta=f"{new_brok - taxable_value:,.2f}")
            else:
                st.metric("Broker Balance", f"${taxable_value:,.2f}")

# Made with Bob

# ── MULTI-YEAR TAX PLANNING ──────────────────────────────────────────────────
with adv_tax_tab:
    st.subheader("📅 5-Year Rolling Tax Optimization Window")
    _myt_col1, _myt_col2, _myt_col3 = st.columns(3)
    with _myt_col1:
        _myt_start_year = st.selectbox("Start Year", list(range(curr_year, curr_year + 6)), key="myt_start_year")
        _myt_filing = st.selectbox("Filing Status", ["married_filing_jointly", "single"], key="myt_filing")
    with _myt_col2:
        _myt_income = st.number_input("Annual Ordinary Income ($)", min_value=0, value=150_000, step=5_000, key="myt_income")
        _myt_cg_lt  = st.number_input("Annual Long-Term Cap Gains ($)", min_value=0, value=0, step=1_000, key="myt_cg_lt")
    with _myt_col3:
        _myt_conversion = st.number_input("Annual Roth Conversion ($)", min_value=0, value=0, step=5_000, key="myt_conversion")
        _myt_qbi        = st.number_input("Annual QBI Income ($)", min_value=0, value=0, step=5_000, key="myt_qbi")
    _myt_col4, _myt_col5, _ = st.columns(3)
    with _myt_col4:
        _myt_loss_cf = st.number_input("Capital Loss Carryforward ($)", min_value=0, value=0, step=1_000, key="myt_loss_cf")
    with _myt_col5:
        _myt_window = st.slider("Window (years)", min_value=3, max_value=10, value=5, key="myt_window")

    if st.button("📊 Run 5-Year Tax Projection", key="myt_run"):
        try:
            _myt_result = build_rolling_tax_window(
                start_year=int(_myt_start_year),
                income_by_year={int(_myt_start_year) + i: float(_myt_income) for i in range(_myt_window)},
                cg_lt_by_year={int(_myt_start_year) + i: float(_myt_cg_lt) for i in range(_myt_window)},
                conversion_by_year={int(_myt_start_year) + i: float(_myt_conversion) for i in range(_myt_window)},
                qbi_by_year={int(_myt_start_year) + i: float(_myt_qbi) for i in range(_myt_window)},
                loss_carryforward=float(_myt_loss_cf),
                filing_status=_myt_filing,
                window=_myt_window,
            )
            _mc1, _mc2, _mc3, _mc4 = st.columns(4)
            _mc1.metric(f"Total Tax ({_myt_window}yr)", f"${_myt_result.total_tax_5yr:,.0f}")
            _mc2.metric("Avg Effective Rate", f"{_myt_result.avg_effective_rate:.1%}")
            _mc3.metric("Total Bracket Headroom", f"${_myt_result.total_bracket_headroom:,.0f}")
            _mc4.metric("Optimization Opportunities", str(len(_myt_result.optimization_opportunities)))

            st.markdown("#### Year-by-Year Projection")
            st.dataframe(pd.DataFrame([{
                "Year": _p.year, "Ordinary Income": f"${_p.ordinary_income:,.0f}",
                "Roth Conversion": f"${_p.roth_conversion:,.0f}", "QBI Deduction": f"${_p.qbi_deduction:,.0f}",
                "AGI": f"${_p.agi:,.0f}", "Federal Tax": f"${_p.federal_tax:,.0f}",
                "Effective Rate": f"{_p.effective_rate:.1%}", "Marginal Rate": f"{_p.marginal_rate:.0%}",
                "Bracket Headroom": f"${_p.bracket_headroom:,.0f}",
            } for _p in _myt_result.years]), use_container_width=True, hide_index=True)

            _myt_fig = go.Figure()
            _myt_fig.add_bar(x=[p.year for p in _myt_result.years], y=[p.federal_tax for p in _myt_result.years],
                             name="Federal Tax", marker_color="rgb(239,85,59)")
            _myt_fig.add_bar(x=[p.year for p in _myt_result.years], y=[p.bracket_headroom for p in _myt_result.years],
                             name="Bracket Headroom", marker_color="rgb(99,110,250)")
            _myt_fig.update_layout(barmode="group", title="Federal Tax vs. Bracket Headroom",
                                   xaxis_title="Year", yaxis_title="Amount ($)",
                                   legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(_myt_fig, use_container_width=True)

            if _myt_result.optimization_opportunities:
                st.markdown("#### 💡 Optimization Opportunities")
                for _opp in _myt_result.optimization_opportunities:
                    st.info(_opp)
            if _myt_result.recommended_conversions:
                st.markdown("#### 📈 Recommended Roth Conversions")
                st.dataframe(pd.DataFrame([{"Year": yr, "Recommended Conversion": f"${amt:,.0f}"}
                                           for yr, amt in _myt_result.recommended_conversions.items()]),
                             use_container_width=True, hide_index=True)
        except Exception as _myt_err:
            st.error(f"Error running tax projection: {_myt_err}")

    st.markdown("---")
    st.subheader("🏢 QBI Deduction Calculator (IRC §199A)")
    with st.expander("Calculate your Qualified Business Income deduction", expanded=True):
        _qbi_c1, _qbi_c2 = st.columns(2)
        with _qbi_c1:
            _qbi_income = st.number_input("QBI Income ($)", min_value=0, value=100_000, step=5_000, key="qbi_income")
            _qbi_total  = st.number_input("Total Taxable Income ($)", min_value=0, value=200_000, step=5_000, key="qbi_total")
            _qbi_filing = st.selectbox("Filing Status", ["married_filing_jointly", "single"], key="qbi_filing")
        with _qbi_c2:
            _qbi_w2   = st.number_input("W-2 Wages Paid by Business ($)", min_value=0, value=0, step=5_000, key="qbi_w2")
            _qbi_ubia = st.number_input("UBIA of Qualified Property ($)", min_value=0, value=0, step=10_000, key="qbi_ubia")
            _qbi_sstb = st.checkbox("Specified Service Trade or Business (SSTB)?", key="qbi_sstb")
        if st.button("Calculate QBI Deduction", key="qbi_calc"):
            _qbi_r = calculate_qbi_deduction_full(qbi_income=float(_qbi_income), total_taxable_income=float(_qbi_total),
                                                   w2_wages=float(_qbi_w2), ubia_qualified_property=float(_qbi_ubia),
                                                   is_sstb=bool(_qbi_sstb), filing_status=_qbi_filing)
            st.session_state["qbi_result"] = _qbi_r
        
        if "qbi_result" in st.session_state:
            _qbi_r = st.session_state["qbi_result"]
            _qc1, _qc2, _qc3 = st.columns(3)
            _qc1.metric("QBI Deduction", f"${_qbi_r['deduction']:,.0f}")
            _qc2.metric("Base Deduction (20%)", f"${_qbi_r['base_deduction']:,.0f}")
            _qc3.metric("Phase-Out %", f"{_qbi_r['phase_out_pct']:.1%}")
            for _note in _qbi_r["notes"]:
                st.caption(_note)

# ── BACKDOOR & MEGA BACKDOOR ROTH ────────────────────────────────────────────
with adv_backdoor_tab:
    st.subheader("🔄 Backdoor Roth IRA")
    
    with st.expander("Backdoor Roth IRA Calculator", expanded=True):
        _bd_c1, _bd_c2, _bd_c3 = st.columns(3)
        with _bd_c1:
            _bd_year     = st.selectbox("Tax Year", list(range(curr_year, curr_year + 3)), key="bd_year")
            _bd_age      = st.number_input("Your Age", min_value=18, max_value=80, value=45, key="bd_age")
        with _bd_c2:
            _bd_magi     = st.number_input("MAGI ($)", min_value=0, value=250_000, step=5_000, key="bd_magi")
            _bd_trad_bal = st.number_input("Pre-Tax IRA Balance ($)", min_value=0, value=0, step=10_000, key="bd_trad_bal")
        with _bd_c3:
            _bd_basis    = st.number_input("After-Tax IRA Basis ($)", min_value=0, value=0, step=1_000, key="bd_basis")
            _bd_filing   = st.selectbox("Filing Status", ["married_filing_jointly", "single"], key="bd_filing")

        if st.button("Analyze Backdoor Roth", key="bd_run"):
            _bd_r = calculate_backdoor_roth(year=int(_bd_year), age=int(_bd_age), magi=float(_bd_magi),
                                            traditional_ira_balance=float(_bd_trad_bal),
                                            after_tax_ira_basis=float(_bd_basis), filing_status=_bd_filing)
            st.session_state["bd_result"] = _bd_r
        
        if "bd_result" in st.session_state:
            _bd_r = st.session_state["bd_result"]
            if not _bd_r.eligible and _bd_r.ineligible_reason:
                st.info(_bd_r.ineligible_reason)
            else:
                _bc1, _bc2, _bc3 = st.columns(3)
                _bc1.metric("Contribution Amount", f"${_bd_r.contribution_amount:,.0f}")
                _bc2.metric("Pro-Rata Tax", f"${_bd_r.pro_rata_tax:,.0f}")
                _bc3.metric("20-Year Net Benefit", f"${_bd_r.net_benefit:,.0f}")
                for _w in (_bd_r.warnings or []):
                    st.warning(_w)
                st.markdown("#### Step-by-Step Instructions")
                for _step in _bd_r.steps:
                    st.markdown(f"- {_step}")

    st.markdown("---")
    st.subheader("📐 BETR — Break-Even Tax Rate Analysis")
    
    with st.expander("BETR Calculator", expanded=True):
        _betr_c1, _betr_c2, _betr_c3 = st.columns(3)
        with _betr_c1:
            _betr_conv_amt  = st.number_input("Conversion Amount ($)", min_value=1_000, value=50_000, step=5_000, key="betr_conv_amt")
            _betr_trad_bal  = st.number_input("Traditional IRA Balance ($)", min_value=1_000, value=500_000, step=10_000, key="betr_trad_bal")
            _betr_basis     = st.number_input("Nontaxable Basis ($)", min_value=0, value=0, step=1_000, key="betr_basis")
        with _betr_c2:
            _betr_curr_rate  = st.slider("Current Marginal Rate (%)", 10, 37, 24, 1, format="%d%%", key="betr_curr_rate") / 100
            _betr_fut_rate   = st.slider("Expected Future Rate (%)", 10, 37, 22, 1, format="%d%%", key="betr_future_rate") / 100
            _betr_return     = st.slider("Expected Annual Return (%)", 2, 12, 7, 1, format="%d%%", key="betr_return") / 100
        with _betr_c3:
            _betr_years      = st.number_input("Years to Withdrawal", min_value=1, max_value=40, value=20, key="betr_years")
            _betr_pay_source = st.radio("Pay Conversion Tax From", ["Taxable Account", "IRA Assets"], key="betr_pay_source")
            _betr_taxable    = st.number_input("Taxable Account Balance ($)", min_value=0, value=200_000, step=10_000, key="betr_taxable_bal")

        if st.button("📐 Calculate BETR", key="betr_run", type="primary"):
            try:
                _betr_inputs = BETRInputs(
                    current_marginal_rate=float(_betr_curr_rate), expected_future_rate=float(_betr_fut_rate),
                    conversion_amount=float(_betr_conv_amt), traditional_ira_balance=float(_betr_trad_bal),
                    nontaxable_basis=float(_betr_basis), pay_from_taxable=(_betr_pay_source == "Taxable Account"),
                    taxable_account_balance=float(_betr_taxable), years_to_withdrawal=int(_betr_years),
                    annual_return=float(_betr_return),
                )
                _betr_r = calculate_betr(_betr_inputs)
                st.session_state["betr_result"] = _betr_r
                st.session_state["betr_fut_rate"] = _betr_fut_rate
                st.session_state["betr_years"] = _betr_years
            except Exception as _betr_err:
                st.error(f"BETR error: {_betr_err}")
        
        if "betr_result" in st.session_state:
            _betr_r = st.session_state["betr_result"]
            _betr_fut_rate = st.session_state.get("betr_fut_rate", 0.22)
            _betr_years = st.session_state.get("betr_years", 20)
            
            if _betr_r.conversion_recommended:
                st.success(f"✅ **Conversion Recommended** — BETR ({_betr_r.betr:.1%}) > Future Rate ({_betr_fut_rate:.0%}).")
            else:
                st.warning(f"⚠️ **Conversion May Not Be Optimal** — BETR ({_betr_r.betr:.1%}) ≤ Future Rate ({_betr_fut_rate:.0%}).")
            _bb1, _bb2, _bb3, _bb4 = st.columns(4)
            _bb1.metric("BETR", f"{_betr_r.betr:.1%}", delta=f"{(_betr_r.betr - _betr_fut_rate):.1%} vs future",
                        delta_color="normal" if _betr_r.conversion_recommended else "inverse")
            _bb2.metric("Conversion Tax", f"${_betr_r.conversion_tax:,.0f}")
            _bb3.metric("Roth Future Value", f"${_betr_r.roth_future_value:,.0f}")
            _bb4.metric("Net Benefit", f"${_betr_r.net_benefit:,.0f}",
                        delta_color="normal" if _betr_r.net_benefit > 0 else "inverse")
            _betr_fig = go.Figure()
            _betr_fig.add_bar(
                x=["Traditional IRA", "Roth IRA"],
                y=[_betr_r.traditional_future_value, _betr_r.roth_future_value],
                marker_color=["rgb(239,85,59)" if _betr_r.roth_future_value > _betr_r.traditional_future_value else "rgb(99,110,250)",
                              "rgb(0,204,150)" if _betr_r.roth_future_value > _betr_r.traditional_future_value else "rgb(239,85,59)"],
                text=[f"${_betr_r.traditional_future_value:,.0f}", f"${_betr_r.roth_future_value:,.0f}"],
                textposition="outside",
            )
            _betr_fig.update_layout(title=f"After-Tax Future Value ({_betr_years}-Year Horizon)",
                                    yaxis_title="After-Tax Future Value ($)", yaxis_tickformat="$,.0f")
            st.plotly_chart(_betr_fig, use_container_width=True)
            if _betr_r.analysis_notes:
                for _note in _betr_r.analysis_notes:
                    st.caption(_note)

    st.markdown("---")
    st.subheader("🚀 Mega Backdoor Roth (401k After-Tax)")
    
    with st.expander("Mega Backdoor Roth Calculator", expanded=True):
        _mbr_c1, _mbr_c2, _mbr_c3 = st.columns(3)
        with _mbr_c1:
            _mbr_year     = st.selectbox("Tax Year", list(range(curr_year, curr_year + 3)), key="mbr_year")
            _mbr_age      = st.number_input("Your Age", min_value=18, max_value=80, value=45, key="mbr_age")
            _mbr_income   = st.number_input("Annual Income ($)", min_value=0, value=200_000, step=10_000, key="mbr_income")
        with _mbr_c2:
            _mbr_employee = st.number_input("Employee 401(k) Contribution ($)", min_value=0, value=23_500, step=500, key="mbr_employee")
            _mbr_employer = st.number_input("Employer Match ($)", min_value=0, value=5_000, step=500, key="mbr_employer")
            _mbr_after_tax = st.number_input("After-Tax Contribution ($)", min_value=0, value=20_000, step=1_000, key="mbr_after_tax")
        with _mbr_c3:
            _mbr_plan_allows = st.checkbox("Plan allows after-tax contributions?", value=True, key="mbr_plan_allows")
            _mbr_in_service  = st.checkbox("Plan allows in-service withdrawals?", value=True, key="mbr_in_service")
            _mbr_filing      = st.selectbox("Filing Status", ["married_filing_jointly", "single"], key="mbr_filing")

        if st.button("Analyze Mega Backdoor Roth", key="mbr_run"):
            try:
                _mbr_r = calculate_mega_backdoor_roth(
                    year=int(_mbr_year), age=int(_mbr_age),
                    employee_elective_deferral=float(_mbr_employee),
                    employer_match=float(_mbr_employer),
                    plan_allows_after_tax=bool(_mbr_plan_allows),
                    plan_allows_in_plan_conversion=bool(_mbr_in_service),
                )
                st.session_state["mbr_result"] = _mbr_r
            except Exception as _mbr_err:
                st.error(f"Mega Backdoor Roth error: {_mbr_err}")
        
        if "mbr_result" in st.session_state:
            _mbr_r = st.session_state["mbr_result"]
            if not _mbr_r.eligible and _mbr_r.ineligible_reason:
                st.info(_mbr_r.ineligible_reason)
            else:
                _mc1, _mc2, _mc3, _mc4 = st.columns(4)
                _mc1.metric("After-Tax Contribution", f"${_mbr_r.after_tax_contribution:,.0f}")
                _mc2.metric("In-Plan Conversion", f"${_mbr_r.in_plan_conversion:,.0f}")
                _mc3.metric("Rollover to Roth IRA", f"${_mbr_r.rollover_to_roth_ira:,.0f}")
                _mc4.metric("Net Benefit", f"${_mbr_r.net_benefit:,.0f}")
                st.markdown("#### Step-by-Step Instructions")
                for _step in _mbr_r.steps:
                    st.markdown(f"- {_step}")

# ── NUA ANALYSIS ─────────────────────────────────────────────────────────────
with adv_nua_tab:
    st.subheader("📈 Net Unrealized Appreciation (NUA) Analysis")
    
    with st.expander("NUA Calculator", expanded=True):
        _nua_c1, _nua_c2, _nua_c3 = st.columns(3)
        with _nua_c1:
            _nua_cost_basis   = st.number_input("Cost Basis of Employer Stock ($)", min_value=0, value=50_000, step=5_000, key="nua_cost_basis")
            _nua_current_val  = st.number_input("Current Market Value ($)", min_value=0, value=200_000, step=10_000, key="nua_current_val")
            _nua_other_assets = st.number_input("Other 401(k) Assets ($)", min_value=0, value=300_000, step=10_000, key="nua_other_assets")
        with _nua_c2:
            _nua_age           = st.number_input("Your Age", min_value=55, max_value=80, value=62, key="nua_age")
            _nua_ordinary_rate = st.slider("Ordinary Income Rate (%)", 10, 37, 24, 1, format="%d%%", key="nua_ordinary_rate") / 100
            _nua_ltcg_rate     = st.slider("LTCG Rate (%)", 0, 20, 15, 1, format="%d%%", key="nua_ltcg_rate") / 100
        with _nua_c3:
            _nua_state_rate  = st.slider("State Tax Rate (%)", 0, 15, 5, 1, format="%d%%", key="nua_state_rate") / 100
            _nua_years       = st.number_input("Years to Hold After Distribution", min_value=0, max_value=30, value=5, key="nua_years")
            _nua_growth_rate = st.slider("Expected Annual Growth (%)", 0, 15, 7, 1, format="%d%%", key="nua_growth_rate") / 100

        if st.button("Analyze NUA Strategy", key="nua_run"):
            try:
                # calculate_nua_analysis(ticker, shares, cost_basis_per_share, current_price_per_share,
                #                        ordinary_income_tax_rate, ltcg_tax_rate, future_tax_rate, years_to_sale)
                _nua_shares = float(_nua_current_val) / max(1.0, float(_nua_current_val) / max(1, int(_nua_current_val / 100)))
                _nua_cost_per = float(_nua_cost_basis) / max(1.0, _nua_shares)
                _nua_price_per = float(_nua_current_val) / max(1.0, _nua_shares)
                _nua_r = calculate_nua_analysis(
                    ticker="EMPLOYER",
                    shares=_nua_shares,
                    cost_basis_per_share=_nua_cost_per,
                    current_price_per_share=_nua_price_per,
                    ordinary_income_tax_rate=float(_nua_ordinary_rate),
                    ltcg_tax_rate=float(_nua_ltcg_rate),
                    future_tax_rate=float(_nua_ordinary_rate),
                    years_to_sale=int(_nua_years),
                )
                st.session_state["nua_result"] = _nua_r
            except Exception as _nua_err:
                st.error(f"NUA analysis error: {_nua_err}")
        
        if "nua_result" in st.session_state:
            _nua_r = st.session_state["nua_result"]
            _na1, _na2, _na3 = st.columns(3)
            _na1.metric("NUA Amount", f"${_nua_r.nua_amount:,.0f}")
            _na2.metric("NUA Tax Savings", f"${_nua_r.tax_savings:,.0f}")
            _na3.metric("Recommendation", "✅ Use NUA" if _nua_r.strategy_recommended else "❌ Roll Over Instead")
            st.markdown("#### NUA vs. Rollover Comparison")
            _nua_fig = go.Figure()
            _nua_fig.add_bar(
                x=["NUA Strategy Tax", "IRA Rollover Tax"],
                y=[_nua_r.total_nua_tax, _nua_r.tax_if_distributed_as_cash],
                marker_color=["rgb(0,204,150)" if _nua_r.strategy_recommended else "rgb(239,85,59)",
                              "rgb(239,85,59)" if _nua_r.strategy_recommended else "rgb(0,204,150)"],
                text=[f"${_nua_r.total_nua_tax:,.0f}", f"${_nua_r.tax_if_distributed_as_cash:,.0f}"],
                textposition="outside",
            )
            _nua_fig.update_layout(title="Tax Cost: NUA Strategy vs. IRA Rollover",
                                   yaxis_title="Tax Cost ($)", yaxis_tickformat="$,.0f")
            st.plotly_chart(_nua_fig, use_container_width=True)
            if _nua_r.notes:
                st.markdown("#### Analysis Notes")
                for _note in _nua_r.notes:
                    st.caption(_note)

# ── QCD OPTIMIZER ─────────────────────────────────────────────────────────────
with adv_qcd_tab:
    st.subheader("🎁 Qualified Charitable Distribution (QCD) Optimizer")
    st.markdown("QCDs allow IRA owners age 70½+ to donate up to $105,000/year directly from an IRA, satisfying RMDs tax-free.")
    
    with st.expander("QCD Calculator", expanded=True):
        _qcd_c1, _qcd_c2, _qcd_c3 = st.columns(3)
        with _qcd_c1:
            _qcd_age         = st.number_input("Your Age", min_value=70, max_value=100, value=73, key="qcd_age")
            _qcd_ira_balance = st.number_input("IRA Balance ($)", min_value=0, value=500_000, step=10_000, key="qcd_ira_balance")
            _qcd_rmd         = st.number_input("Annual RMD ($)", min_value=0, value=20_000, step=1_000, key="qcd_rmd")
        with _qcd_c2:
            _qcd_agi         = st.number_input("AGI Before QCD ($)", min_value=0, value=100_000, step=5_000, key="qcd_agi")
            _qcd_charitable  = st.number_input("Annual Charitable Giving Goal ($)", min_value=0, value=10_000, step=1_000, key="qcd_charitable")
            _qcd_filing      = st.selectbox("Filing Status", ["married_filing_jointly", "single"], key="qcd_filing")
        with _qcd_c3:
            _qcd_ordinary_rate = st.slider("Marginal Tax Rate (%)", 10, 37, 22, 1, format="%d%%", key="qcd_ordinary_rate") / 100
            _qcd_state_rate    = st.slider("State Tax Rate (%)", 0, 15, 5, 1, format="%d%%", key="qcd_state_rate") / 100
            _qcd_year          = st.selectbox("Tax Year", list(range(curr_year, curr_year + 3)), key="qcd_year")

        if st.button("Optimize QCD Strategy", key="qcd_run"):
            try:
                # calculate_qcd_optimization(year, age, rmd_amount, ira_balance,
                #   planned_charitable_giving, agi_before_rmd, marginal_tax_rate, filing_status, ...)
                _qcd_r = calculate_qcd_optimization(
                    year=int(_qcd_year), age=int(_qcd_age),
                    rmd_amount=float(_qcd_rmd), ira_balance=float(_qcd_ira_balance),
                    planned_charitable_giving=float(_qcd_charitable),
                    agi_before_rmd=float(_qcd_agi),
                    marginal_tax_rate=float(_qcd_ordinary_rate),
                    filing_status=_qcd_filing,
                )
                st.session_state["qcd_result"] = _qcd_r
            except Exception as _qcd_err:
                st.error(f"QCD optimization error: {_qcd_err}")
        
        if "qcd_result" in st.session_state:
            _qcd_r = st.session_state["qcd_result"]
            _qa1, _qa2, _qa3, _qa4 = st.columns(4)
            _qa1.metric("QCD Amount", f"${_qcd_r.qcd_amount:,.0f}")
            _qa2.metric("Tax Savings", f"${_qcd_r.tax_savings:,.0f}")
            _qa3.metric("AGI Reduction", f"${_qcd_r.agi_reduction:,.0f}")
            _qa4.metric("QCD Advantage", f"${_qcd_r.qcd_advantage:,.0f}")
            if _qcd_r.notes:
                st.markdown("#### Analysis Notes")
                for _note in _qcd_r.notes:
                    st.caption(_note)

# ── 72(t) SEPP CALCULATOR ─────────────────────────────────────────────────────
with adv_sepp_tab:
    st.subheader("⏱️ 72(t) SEPP Calculator")
    st.markdown("Substantially Equal Periodic Payments allow penalty-free IRA withdrawals before age 59½.")
    
    with st.expander("SEPP Calculator", expanded=True):
        _sepp_c1, _sepp_c2, _sepp_c3 = st.columns(3)
        with _sepp_c1:
            _sepp_balance    = st.number_input("IRA Balance ($)", min_value=1_000, value=500_000, step=10_000, key="sepp_balance")
            _sepp_age        = st.number_input("Current Age", min_value=18, max_value=58, value=50, key="sepp_age")
            _sepp_life_exp   = st.number_input("Life Expectancy (years)", min_value=20, max_value=50, value=35, key="sepp_life_exp")
        with _sepp_c2:
            _sepp_rate       = st.slider("Interest Rate (%)", min_value=0.5, max_value=10.0, value=5.0, step=0.1, format="%.1f%%", key="sepp_rate") / 100
            _sepp_method     = st.selectbox("SEPP Method", SEPP_METHODS, key="sepp_method")
            _sepp_filing     = st.selectbox("Filing Status", ["married_filing_jointly", "single"], key="sepp_filing")
        with _sepp_c3:
            _sepp_ordinary_rate = st.slider("Marginal Tax Rate (%)", 10, 37, 22, 1, format="%d%%", key="sepp_ordinary_rate") / 100
            _sepp_state_rate    = st.slider("State Tax Rate (%)", 0, 15, 5, 1, format="%d%%", key="sepp_state_rate") / 100

        if st.button("Calculate SEPP", key="sepp_run"):
            try:
                # calculate_sepp(account_balance, age, method, afr, marginal_tax_rate)
                _sepp_r = calculate_sepp(
                    account_balance=float(_sepp_balance), age=int(_sepp_age),
                    method=_sepp_method, afr=float(_sepp_rate),
                    marginal_tax_rate=float(_sepp_ordinary_rate),
                )
                st.session_state["sepp_result"] = _sepp_r
            except Exception as _sepp_err:
                st.error(f"SEPP calculation error: {_sepp_err}")
        
        if "sepp_result" in st.session_state:
            _sepp_r = st.session_state["sepp_result"]
            _sa1, _sa2, _sa3, _sa4 = st.columns(4)
            _sa1.metric("Annual SEPP Payment", f"${_sepp_r.annual_payment:,.0f}")
            _sa2.metric("Monthly Payment", f"${_sepp_r.monthly_payment:,.0f}")
            _sa3.metric("Est. Annual Tax", f"${_sepp_r.estimated_annual_tax:,.0f}")
            _sa4.metric("Years Required", str(_sepp_r.years_required))
            if _sepp_r.warnings:
                for _w in _sepp_r.warnings:
                    st.warning(_w)
            if _sepp_r.notes:
                st.markdown("#### Important Notes")
                for _note in _sepp_r.notes:
                    st.caption(_note)

# ── CAPITAL LOSS HARVESTING ───────────────────────────────────────────────────
with adv_harvest_tab:
    st.subheader("🌾 Multi-Year Capital Loss Harvesting Plan")
    st.markdown("Model how harvesting unrealized losses in your brokerage account reduces taxes over multiple years.")
    _hlv_c1, _hlv_c2, _hlv_c3 = st.columns(3)
    with _hlv_c1:
        _hlv_income      = st.number_input("Annual Ordinary Income ($)", min_value=0, value=150_000, step=5_000, key="hlv_income")
        _hlv_cg_lt       = st.number_input("Annual Long-Term Cap Gains ($)", min_value=0, value=20_000, step=1_000, key="hlv_cg_lt")
        _hlv_filing      = st.selectbox("Filing Status", ["married_filing_jointly", "single"], key="hlv_filing")
    with _hlv_c2:
        _hlv_unrealized  = st.number_input("Total Unrealized Losses ($)", min_value=0, value=50_000, step=5_000, key="hlv_unrealized")
        _hlv_loss_cf     = st.number_input("Existing Loss Carryforward ($)", min_value=0, value=0, step=1_000, key="hlv_loss_cf")
        _hlv_start_year  = st.selectbox("Start Year", list(range(curr_year, curr_year + 3)), key="hlv_start_year")
    with _hlv_c3:
        _hlv_window      = st.slider("Planning Window (years)", min_value=1, max_value=10, value=5, key="hlv_window")
        _hlv_harvest_pct = st.slider("% of Losses to Harvest Annually", min_value=10, max_value=100, value=50, step=5, key="hlv_harvest_pct") / 100

    if st.button("📊 Build Loss Harvesting Plan", key="hlv_run"):
        try:
            # build_multi_year_loss_harvesting_plan(start_year, portfolio_positions, income_by_year, filing_status, window)
            # Build synthetic portfolio_positions from the unrealized loss input
            _hlv_positions = [{
                "ticker": "PORTFOLIO", "shares": 1000.0,
                "cost_basis": float(_hlv_unrealized) / 1000.0 + float(_hlv_income) / 1000.0,
                "current_price": float(_hlv_income) / 1000.0,
                "holding_period_days": 400,
            }] if float(_hlv_unrealized) > 0 else []
            _hlv_income_by_year = {int(_hlv_start_year) + i: float(_hlv_income) for i in range(_hlv_window)}
            _hlv_r = build_multi_year_loss_harvesting_plan(
                start_year=int(_hlv_start_year),
                portfolio_positions=_hlv_positions,
                income_by_year=_hlv_income_by_year,
                filing_status=_hlv_filing,
                window=_hlv_window,
            )
            st.session_state["hlv_result"] = _hlv_r
            st.session_state["hlv_positions"] = _hlv_positions
            st.session_state["hlv_window"] = _hlv_window
        except Exception as _hlv_err:
            st.error(f"Loss harvesting error: {_hlv_err}")
    
    if "hlv_result" in st.session_state:
        _hlv_r = st.session_state["hlv_result"]
        _hlv_positions = st.session_state.get("hlv_positions", [])
        _hlv_window = st.session_state.get("hlv_window", 5)
        
        _ha1, _ha2, _ha3 = st.columns(3)
        _ha1.metric(f"Total Tax Savings ({_hlv_window}yr)", f"${_hlv_r.total_tax_savings:,.0f}")
        _ha2.metric("Years Planned", str(len(_hlv_r.years)))
        _ha3.metric("Positions with Losses", str(len(_hlv_positions)))

        st.markdown("#### Year-by-Year Harvesting Plan")
        st.dataframe(pd.DataFrame([{
            "Year": yr,
            "Losses Harvested": f"${_hlv_r.harvest_amounts.get(yr, 0):,.0f}",
            "Tax Savings": f"${_hlv_r.tax_savings_by_year.get(yr, 0):,.0f}",
            "Carryforward": f"${_hlv_r.carryforward_by_year.get(yr, 0):,.0f}",
        } for yr in _hlv_r.years]), use_container_width=True, hide_index=True)

        _hlv_fig = go.Figure()
        _hlv_fig.add_bar(
            x=_hlv_r.years,
            y=[_hlv_r.tax_savings_by_year.get(yr, 0) for yr in _hlv_r.years],
            name="Tax Savings", marker_color="rgb(0,204,150)",
        )
        _hlv_fig.update_layout(title="Annual Tax Savings from Loss Harvesting",
                               xaxis_title="Year", yaxis_title="Tax Savings ($)", yaxis_tickformat="$,.0f")
        st.plotly_chart(_hlv_fig, use_container_width=True)

        if _hlv_r.notes:
            st.markdown("#### 📋 Notes")
            for _note in _hlv_r.notes:
                st.caption(_note)

# ── Footer ────────────────────────────────────────────────────────────────────
auto_rerun_if_rebuilding()
