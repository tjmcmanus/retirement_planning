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
navbar("🧠 Advanced Strategy Tools")
st.header("🎯 Advanced Strategy Tools")
st.markdown("Multi-year tax planning, backdoor Roth, NUA, QCD, and 72(t) SEPP calculators.")
st.markdown("---")

def _cs() -> None:
    st.session_state["submit"] = False

(adv_tax_planner_tab, adv_tax_tab, adv_backdoor_tab, adv_nua_tab,
 adv_qcd_tab, adv_sepp_tab, adv_harvest_tab, adv_medicare_tab, adv_ssa_tab) = st.tabs([
    "🧮 Tax Planner", "📅 Multi-Year Tax Planning", "🔄 Backdoor & Mega Backdoor Roth",
    "📈 NUA Analysis", "🎁 QCD Optimizer", "⏱️ 72(t) SEPP Calculator", "🌾 Capital Loss Harvesting",
    "🏥 Medicare Enrollment Guide", "💰 Social Security Enrollment Guide",
])

# ── TAX PLANNER ─────────────────────────────────────────────────────────────
with adv_tax_planner_tab:
    st.subheader("🧮 Tax Planner")
    
    with st.expander("📘 Strategy: Why Use the Tax Planner?", expanded=False):
        st.markdown("""
        The **Tax Planner** is a single-year tax projection tool that helps you estimate your tax liability and optimize key decisions before year-end.
        
        **Why This Matters:**
        - **Avoid Surprises**: Project your total tax bill before filing, including federal, state, and Medicare surcharges
        - **Optimize Conversions**: Determine the optimal Roth conversion amount to stay within your target tax bracket
        - **Plan Withdrawals**: Calculate how much you can safely withdraw from tax-deferred accounts
        - **Charitable Giving**: Model Donor Advised Fund (DAF) contributions to maximize deductions
        - **Medicare Planning**: See how conversions affect IRMAA surcharges (2-year lookback)
        
        **Best Used For:**
        - Year-end tax planning and adjustments
        - Estimating quarterly tax payments
        - Evaluating Roth conversion opportunities
        - Optimizing charitable contribution timing
        - Projecting the impact of capital gains on your tax situation
        
        **Key Features:**
        - Real-time tax calculations using current IRS brackets
        - Roth conversion headroom analysis
        - IRMAA surcharge projections
        - DAF contribution optimization (30% or 60% AGI limits)
        - State tax estimates
        - Account balance projections after transactions
        """)
    
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
    
    with st.expander("📘 Strategy: Why Use Multi-Year Tax Planning?", expanded=False):
        st.markdown("""
        **Multi-Year Tax Planning** helps you optimize Roth conversions and tax strategies across a 5-10 year window, not just a single year.
        
        **Why This Matters:**
        - **Bracket Management**: Identify years with lower income to maximize conversions
        - **RMD Preparation**: Convert before Required Minimum Distributions push you into higher brackets
        - **Tax Rate Arbitrage**: Take advantage of temporary low-income years (early retirement, sabbatical)
        - **IRMAA Avoidance**: Plan conversions to avoid Medicare surcharges in future years
        - **Smooth Tax Burden**: Spread conversions to avoid bracket spikes
        
        **Best Used For:**
        - Early retirees (age 60-72) before RMDs begin
        - Planning systematic Roth conversions over multiple years
        - Optimizing QBI (Qualified Business Income) deductions
        - Coordinating capital gains with conversion strategies
        - Long-term tax bracket optimization
        
        **Key Features:**
        - 5-10 year tax projection window
        - Year-by-year effective and marginal rate analysis
        - Bracket headroom identification (unused space in current bracket)
        - QBI deduction calculator (IRC §199A for business owners)
        - Optimization opportunity recommendations
        - Visual comparison of tax burden across years
        """)
    
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
    
    with st.expander("📘 Strategy: Why Use the QBI Deduction Calculator?", expanded=False):
        st.markdown("""
        The **Qualified Business Income (QBI) Deduction** under IRC §199A allows eligible business owners and self-employed individuals to deduct up to **20% of qualified business income** from pass-through entities.
        
        **Why This Matters:**
        - **Significant Tax Savings**: Deduct up to 20% of business income, potentially saving thousands in taxes
        - **Pass-Through Benefit**: Available for sole proprietors, partnerships, S-corps, and LLCs
        - **No Additional Cost**: Unlike retirement contributions, this deduction doesn't require setting aside funds
        - **Stacks with Other Deductions**: Works alongside standard/itemized deductions and retirement contributions
        
        **Who Qualifies:**
        - Self-employed individuals (Schedule C)
        - Partners in partnerships
        - S-corporation shareholders
        - LLC members (taxed as pass-through)
        - Real estate investors with rental income
        - Trust and estate beneficiaries with QBI
        
        **Income Thresholds (2026):**
        - **Below Threshold**: Full 20% deduction, no limitations
          - Married Filing Jointly: $394,600
          - Single: $197,300
        - **Phase-Out Range**: Deduction gradually limited by W-2 wages and property basis
          - MFJ: $394,600 - $494,600
          - Single: $197,300 - $247,300
        - **Above Threshold**: W-2 wage and UBIA limitations fully apply
        
        **Specified Service Trade or Business (SSTB) Rules:**
        SSTBs face stricter limitations and complete phase-out at higher incomes:
        - **SSTB Examples**: Doctors, lawyers, accountants, consultants, financial advisors, athletes, performers
        - **Non-SSTB Examples**: Manufacturing, retail, restaurants, construction, engineering, architecture
        - **SSTB Impact**: Deduction phases out completely above income thresholds
        
        **W-2 Wage Limitation:**
        Above income thresholds, deduction is limited to the greater of:
        1. **50% of W-2 wages** paid by the business, OR
        2. **25% of W-2 wages** + 2.5% of UBIA (unadjusted basis of qualified property)
        
        **Best Used For:**
        - Annual tax planning for business owners
        - Evaluating whether to take additional income in current year
        - Deciding between W-2 compensation vs. distributions (S-corps)
        - Planning major equipment purchases (UBIA impact)
        - Assessing impact of Roth conversions on QBI deduction
        - Comparing tax efficiency of different business structures
        
        **Strategic Considerations:**
        - **Roth Conversions**: Large conversions can push you into phase-out range
        - **Income Timing**: Consider deferring income if near threshold
        - **W-2 Wages**: S-corp owners may benefit from higher W-2 compensation
        - **Equipment Purchases**: Qualified property increases UBIA, expanding deduction
        - **Business Structure**: QBI deduction may favor pass-through over C-corp
        
        **Common Scenarios:**
        1. **Solo Consultant (SSTB)**: $180K income → Full 20% deduction ($36K)
        2. **High-Income Doctor (SSTB)**: $550K income → No deduction (phased out)
        3. **Manufacturing Business**: $450K income, $200K W-2 wages → Limited by W-2 wages
        4. **Real Estate Investor**: $300K rental income → Full 20% deduction ($60K)
        """)
    
    with st.expander("Calculate your Qualified Business Income deduction", expanded=True):
        _qbi_c1, _qbi_c2 = st.columns(2)
        with _qbi_c1:
            _qbi_income = st.number_input("QBI Income ($)", min_value=0, value=100_000, step=5_000, key="qbi_income",
                help="Qualified business income from pass-through entities (Schedule C, K-1, etc.)")
            _qbi_total  = st.number_input("Total Taxable Income ($)", min_value=0, value=200_000, step=5_000, key="qbi_total",
                help="Total taxable income (determines phase-out and limitations)")
            _qbi_filing = st.selectbox("Filing Status", ["married_filing_jointly", "single"], key="qbi_filing")
        with _qbi_c2:
            _qbi_w2   = st.number_input("W-2 Wages Paid by Business ($)", min_value=0, value=0, step=5_000, key="qbi_w2",
                help="Total W-2 wages paid by the business (for wage limitation)")
            _qbi_ubia = st.number_input("UBIA of Qualified Property ($)", min_value=0, value=0, step=10_000, key="qbi_ubia",
                help="Unadjusted basis immediately after acquisition of qualified property")
            _qbi_sstb = st.checkbox("Specified Service Trade or Business (SSTB)?", key="qbi_sstb",
                help="Check if business is health, law, accounting, consulting, financial services, etc.")
        
        if st.button("Calculate QBI Deduction", key="qbi_calc"):
            _qbi_r = calculate_qbi_deduction_full(qbi_income=float(_qbi_income), total_taxable_income=float(_qbi_total),
                                                   w2_wages=float(_qbi_w2), ubia_qualified_property=float(_qbi_ubia),
                                                   is_sstb=bool(_qbi_sstb), filing_status=_qbi_filing)
            st.session_state["qbi_result"] = _qbi_r
        
        if "qbi_result" in st.session_state:
            _qbi_r = st.session_state["qbi_result"]
            _qc1, _qc2, _qc3 = st.columns(3)
            _qc1.metric("QBI Deduction", f"${_qbi_r['deduction']:,.0f}",
                help="Final qualified business income deduction")
            _qc2.metric("Base Deduction (20%)", f"${_qbi_r['base_deduction']:,.0f}",
                help="20% of QBI before limitations")
            _qc3.metric("Phase-Out %", f"{_qbi_r['phase_out_pct']:.1%}",
                help="Percentage through phase-out range")
            
            st.markdown("#### Calculation Details")
            for _note in _qbi_r["notes"]:
                st.caption(_note)
            
            # Add tax savings estimate
            if _qbi_r['deduction'] > 0:
                _est_tax_rate = 0.24  # Estimate
                _est_savings = _qbi_r['deduction'] * _est_tax_rate
                st.success(f"💰 **Estimated Tax Savings**: ${_est_savings:,.0f} (assuming 24% marginal rate)")

# ── BACKDOOR & MEGA BACKDOOR ROTH ────────────────────────────────────────────
with adv_backdoor_tab:
    st.subheader("🔄 Backdoor Roth IRA")
    
    with st.expander("📘 Strategy: Why Use Backdoor & Mega Backdoor Roth?", expanded=False):
        st.markdown("""
        **Backdoor Roth** strategies allow high-income earners to contribute to Roth accounts despite income limits.
        
        ### Regular Backdoor Roth IRA
        **Why This Matters:**
        - **Income Limit Workaround**: Contribute to Roth IRA even when MAGI exceeds $240,000 (married) or $161,000 (single)
        - **Tax-Free Growth**: All future growth and withdrawals are tax-free
        - **No RMDs**: Unlike Traditional IRAs, Roth IRAs have no Required Minimum Distributions
        - **Estate Planning**: Pass tax-free wealth to heirs
        
        **Annual Contribution:** $7,000 ($8,000 if age 50+)
        
        **Critical Consideration:** The **Pro-Rata Rule** - if you have existing pre-tax IRA balances, conversions are partially taxable. Solution: Roll pre-tax IRAs into your 401(k) first.
        
        ### Mega Backdoor Roth (401k After-Tax)
        **Why This Matters:**
        - **Massive Contributions**: Up to $46,000 additional annually (2026 limits)
        - **No Income Limits**: Available regardless of income level
        - **No Pro-Rata Issues**: 401(k) conversions don't trigger IRA pro-rata rules
        - **Accelerated Wealth Building**: Dramatically increase tax-free retirement savings
        
        **Requirements:**
        - Employer 401(k) must allow after-tax contributions
        - Plan must allow in-plan Roth conversions OR in-service distributions
        - Check with your HR department or plan administrator
        
        ### BETR (Break-Even Tax Rate) Analysis
        **Why This Matters:**
        - **Scientific Decision Framework**: Determine if conversion makes financial sense
        - **Beyond Simple Comparison**: Accounts for tax payment source, time horizon, and future opportunities
        - **Personalized Analysis**: Calculate your specific break-even tax rate
        
        **Decision Rule:** If your expected future tax rate > BETR, conversion is recommended.
        
        **Best Used For:**
        - High-income earners maximizing Roth contributions
        - Those with employer 401(k) plans supporting mega backdoor
        - Anyone wanting to enable future backdoor Roth contributions
        - Evaluating whether Roth conversions make financial sense
        """)
    
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
    
    with st.expander("📘 Strategy: Why Use NUA?", expanded=False):
        st.markdown("""
        **Net Unrealized Appreciation (NUA)** is a specialized tax strategy for company stock held in your 401(k).
        
        **Why This Matters:**
        - **Tax Savings**: Pay capital gains rates (0-20%) instead of ordinary income rates (10-37%) on stock appreciation
        - **Immediate Access**: Distribute stock to taxable account without 10% early withdrawal penalty
        - **Estate Planning**: Heirs get step-up in basis on NUA amount
        - **One-Time Opportunity**: Must be done as lump-sum distribution upon separation from service
        
        **How It Works:**
        1. Distribute employer stock from 401(k) to taxable brokerage account
        2. Pay ordinary income tax on original cost basis only
        3. Pay capital gains tax on appreciation (NUA) when you sell
        4. Appreciation is taxed at favorable long-term capital gains rates
        
        **Example:**
        - Cost basis: $50,000 (taxed as ordinary income at distribution)
        - Current value: $200,000
        - NUA: $150,000 (taxed as capital gains when sold)
        - Tax savings: Up to $25,500 vs. rolling to IRA
        
        **Best Used For:**
        - Employees with highly appreciated company stock in 401(k)
        - Those age 55+ separating from service (no early withdrawal penalty)
        - Stock with low cost basis relative to current value
        - When you expect to be in high tax bracket in retirement
        
        **Requirements:**
        - Must take lump-sum distribution (entire 401(k) balance)
        - Must occur after triggering event (separation, age 59½, death, disability)
        - Stock must be distributed in-kind (not sold first)
        
        **Caution:** This is a complex, irrevocable decision. Consult a tax professional before proceeding.
        """)
    
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
    
    with st.expander("📘 Strategy: Why Use QCD?", expanded=False):
        st.markdown("""
        **Qualified Charitable Distributions (QCD)** allow IRA owners age 70½+ to donate directly from an IRA to charity, tax-free.
        
        **Why This Matters:**
        - **Tax-Free Giving**: Donations don't count as taxable income (better than itemized deduction)
        - **Satisfy RMDs**: QCDs count toward Required Minimum Distributions
        - **Lower AGI**: Reduces AGI, which can help with IRMAA, ACA subsidies, and other income-based thresholds
        - **No Itemization Needed**: Benefit even if you take the standard deduction
        - **Efficient Philanthropy**: More tax-efficient than taking distribution and donating separately
        
        **Annual Limit:** $105,000 per person (2026)
        
        **How It Works:**
        1. Direct your IRA custodian to send funds directly to qualified charity
        2. Distribution is excluded from taxable income
        3. Counts toward your RMD requirement
        4. Charity receives full amount (no taxes withheld)
        
        **Example:**
        - RMD: $20,000
        - Charitable giving goal: $10,000
        - Strategy: Use $10,000 QCD + $10,000 regular distribution
        - Tax savings: $2,200 (at 22% bracket) vs. taking full distribution and donating
        
        **Best Used For:**
        - Retirees age 70½+ with charitable giving goals
        - Those who don't itemize deductions
        - Managing AGI to avoid IRMAA surcharges
        - Satisfying RMDs while supporting charities
        - Reducing taxable estate
        
        **Requirements:**
        - Must be age 70½ or older
        - Distribution must go directly from IRA to qualified 501(c)(3) charity
        - Cannot receive any benefit in return (no tickets, meals, etc.)
        - Must receive written acknowledgment from charity
        
        **Advantages Over Regular Donations:**
        - Reduces AGI (not just taxable income)
        - Works with standard deduction
        - Avoids IRMAA and other AGI-based penalties
        - More tax-efficient than distribute-then-donate
        """)
    
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
    
    with st.expander("📘 Strategy: Why Use 72(t) SEPP?", expanded=False):
        st.markdown("""
        **72(t) SEPP (Substantially Equal Periodic Payments)** allows penalty-free IRA withdrawals before age 59½.
        
        **Why This Matters:**
        - **Early Retirement**: Access IRA funds before 59½ without 10% early withdrawal penalty
        - **Bridge to 59½**: Create income stream until penalty-free withdrawals begin
        - **Flexible Methods**: Choose from three IRS-approved calculation methods
        - **Legal and Safe**: IRS-sanctioned exception to early withdrawal penalty
        
        **How It Works:**
        1. Calculate annual payment using IRS-approved method
        2. Take substantially equal payments for at least 5 years AND until age 59½
        3. Payments must continue without modification (with limited exceptions)
        4. Failure to comply triggers retroactive penalties plus interest
        
        **Three IRS-Approved Methods:**
        
        1. **Required Minimum Distribution (RMD)**
           - Recalculated annually based on account balance
           - Most flexible (payments adjust with balance)
           - Typically lowest payment amount
        
        2. **Fixed Amortization**
           - Fixed payment based on life expectancy and interest rate
           - Moderate payment amount
           - Can switch to RMD method once
        
        3. **Fixed Annuitization**
           - Fixed payment using annuity factors
           - Typically highest payment amount
           - Can switch to RMD method once
        
        **Example:**
        - IRA Balance: $500,000
        - Age: 50
        - Interest Rate: 5%
        - Annual Payment: ~$20,000-$25,000 (method dependent)
        - Must continue until age 59½ (9 years minimum)
        
        **Best Used For:**
        - Early retirees (age 50-58) needing IRA income
        - Those with sufficient IRA balance to support payments
        - People committed to long-term payment schedule
        - Bridging gap to age 59½ or Social Security
        
        **Critical Warnings:**
        - **Irrevocable**: Once started, must continue for required period
        - **Modification Penalty**: Changing payments triggers retroactive 10% penalty + interest
        - **All or Nothing**: Applies to entire IRA (consider splitting IRAs first)
        - **Still Taxable**: Payments are taxed as ordinary income (just no penalty)
        
        **Requirements:**
        - Must continue for longer of: 5 years OR until age 59½
        - Cannot modify payment amount (with limited exceptions)
        - Must take payments at least annually
        - Applies to entire IRA account
        
        **Planning Tips:**
        - Consider splitting IRA before starting SEPP (only apply to portion needed)
        - Choose conservative interest rate (lower payments = more flexibility)
        - Ensure sufficient balance to sustain payments
        - Have backup income sources in case of emergency
        - Consult tax professional before implementing
        """)
    
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
    
    with st.expander("📘 Strategy: Why Use Capital Loss Harvesting?", expanded=False):
        st.markdown("""
        **Capital Loss Harvesting** (also called Tax-Loss Harvesting) involves strategically selling investments at a loss to offset capital gains and reduce taxes.
        
        **Why This Matters:**
        - **Offset Gains**: Losses offset capital gains dollar-for-dollar
        - **Reduce Ordinary Income**: Excess losses offset up to $3,000 of ordinary income annually
        - **Carry Forward**: Unused losses carry forward indefinitely to future years
        - **Lower AGI**: Reduces AGI, helping with IRMAA, ACA subsidies, and other thresholds
        - **Free Tax Benefit**: Harvest losses without changing investment exposure (via wash sale planning)
        
        **How It Works:**
        1. Identify positions with unrealized losses in taxable accounts
        2. Sell losing positions to realize losses
        3. Immediately buy similar (but not "substantially identical") investments
        4. Use losses to offset gains or reduce ordinary income
        5. Carry forward unused losses to future years
        
        **Tax Benefits:**
        - **Offset Short-Term Gains**: Save up to 37% (ordinary income rates)
        - **Offset Long-Term Gains**: Save up to 23.8% (20% + 3.8% NIIT)
        - **Offset Ordinary Income**: Save up to $3,000 × your tax rate annually
        - **Indefinite Carryforward**: Losses never expire
        
        **Example:**
        - Realized capital gains: $50,000
        - Harvest losses: $30,000
        - Net taxable gains: $20,000
        - Tax savings: $7,140 (at 23.8% LTCG rate)
        
        **Multi-Year Strategy:**
        - Year 1: Harvest $50,000 losses, offset $20,000 gains + $3,000 income
        - Year 2: Carry forward $27,000, offset $20,000 gains + $3,000 income
        - Year 3: Carry forward $4,000, offset $4,000 gains
        - Total tax savings: $11,900+ over 3 years
        
        **Best Used For:**
        - Market downturns (harvest losses when available)
        - Years with large capital gains (from sales, rebalancing, etc.)
        - High-income years (maximize value of ordinary income offset)
        - Retirees managing AGI for IRMAA and ACA subsidies
        - Building loss carryforward "bank" for future use
        
        **Wash Sale Rule (Critical):**
        - Cannot buy "substantially identical" security 30 days before or after sale
        - 61-day window total (30 days before + day of sale + 30 days after)
        - Violation defers loss (doesn't eliminate it, but delays benefit)
        - Applies across all accounts (including spouse's and IRAs)
        
        **Strategies to Avoid Wash Sales:**
        - Buy similar but not identical fund (e.g., different S&P 500 fund)
        - Wait 31 days before repurchasing
        - Double up (buy more shares, wait 31 days, sell original)
        - Use different asset class with similar exposure
        
        **What You Can Harvest:**
        - Individual stocks
        - Mutual funds
        - ETFs
        - Bonds
        - Any security in taxable accounts
        
        **What You CANNOT Harvest:**
        - Losses in IRAs, 401(k)s, or other tax-advantaged accounts
        - Losses on personal property (home, car, etc.)
        
        **Planning Tips:**
        - Harvest losses throughout the year (not just December)
        - Track cost basis carefully (use specific identification)
        - Consider harvesting even without current gains (build carryforward)
        - Coordinate with Roth conversion planning (losses reduce AGI)
        - Review portfolio quarterly for harvesting opportunities
        - Use this tool to model multi-year harvesting strategy
        """)
    
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

# ── MEDICARE ENROLLMENT GUIDE ─────────────────────────────────────────────────
with adv_medicare_tab:
    st.markdown("### 🏥 Medicare Enrollment Guide")
    st.markdown("""
    This comprehensive guide helps you navigate Medicare enrollment, understand your options,
    and avoid costly mistakes. Medicare decisions are complex and often irreversible, so it's
    crucial to understand your choices before enrolling.
    
    ⚠️ **Important Recommendation**: For most retirees, **Original Medicare + Medigap (Supplement)**
    is the safer choice despite higher premiums. While Medicare Advantage may seem attractive with
    lower costs, switching back to Medigap later is extremely difficult or impossible due to medical
    underwriting. The freedom and comprehensive coverage of Medigap is worth the extra cost.
    """)
    
    # Overview Section
    with st.expander("📋 Medicare Basics: Parts A, B, C, D", expanded=False):
        st.markdown("""
        #### Understanding Medicare Parts
        
        **Part A (Hospital Insurance)**
        - Covers inpatient hospital stays, skilled nursing facility care, hospice, and some home health care
        - Most people get Part A premium-free if they or their spouse paid Medicare taxes for 10+ years
        - 2026 deductible: $1,632 per benefit period
        
        **Part B (Medical Insurance)**
        - Covers doctor visits, outpatient care, preventive services, medical equipment
        - Standard monthly premium in 2026: $174.70
        - **⚠️ IRMAA Surcharges Apply**: Premium increases based on your MAGI from **2 years prior**
        - Annual deductible: $240, then typically 20% coinsurance
        
        **🚨 CRITICAL: IRMAA (Income-Related Monthly Adjustment Amount)**
        - Part B and Part D premiums increase based on your Modified Adjusted Gross Income (MAGI)
        - **Uses income from 2 years ago** (2026 premiums based on 2024 tax return)
        - Applies to individuals with MAGI > $103,000 or couples > $206,000 (2024 thresholds)
        - Surcharges range from $69.90 to $419.30/month added to Part B premium
        - Part D also has IRMAA surcharges ($12.90 to $81.00/month)
        - **Tax Planning Opportunity**: Manage Roth conversions and withdrawals to minimize IRMAA
        - Life-changing events (marriage, divorce, death of spouse, work stoppage) may allow appeals
        
        **Part C (Medicare Advantage) - ⚠️ Proceed with Caution**
        - Alternative to Original Medicare (Parts A & B)
        - Offered by private insurance companies approved by Medicare
        - Often includes prescription drug coverage (Part D)
        - May offer additional benefits like dental, vision, hearing
        - **Major Drawbacks**:
          - Network restrictions limit doctor and hospital choices
          - Prior authorization required for many services (delays care)
          - **Frequent denials** that can take months to resolve
          - **Very difficult to switch back to Medigap** due to medical underwriting
          - Networks change annually - you may lose your doctors
        - **⚠️ Warning**: This is often a one-way door - choose carefully
        
        **Part D (Prescription Drug Coverage)**
        - Covers prescription medications
        - Offered by private insurance companies
        - Required if you want drug coverage with Original Medicare
        - Late enrollment penalty applies if you delay without creditable coverage
        - Also subject to IRMAA surcharges based on 2-year-prior income
        """)
    
    # Enrollment Timing
    with st.expander("⏰ Critical Enrollment Periods & Penalties", expanded=False):
        st.markdown("""
        #### Initial Enrollment Period (IEP)
        
        **When to Enroll:**
        - 7-month window: 3 months before your 65th birthday month, your birthday month, and 3 months after
        - If still working with employer coverage (20+ employees), you may delay Part B without penalty
        
        **⚠️ Late Enrollment Penalties:**
        
        **Part A Penalty:**
        - If you don't have 40 work credits and miss your IEP
        - 10% premium increase for twice the number of years you were eligible but didn't enroll
        - **This penalty is permanent**
        
        **Part B Penalty:**
        - 10% premium increase for each 12-month period you were eligible but didn't enroll
        - **This penalty is permanent and compounds annually**
        - Example: 2 years late = 20% higher premiums for life
        
        **Part D Penalty:**
        - 1% of the national base beneficiary premium × number of months without coverage
        - **This penalty is permanent**
        - 2026 base premium: ~$34.70, so 1% = $0.35/month per month delayed
        
        #### Special Enrollment Periods (SEP)
        - When you lose employer coverage (8-month window)
        - When you move out of your plan's service area
        - If you qualify for Extra Help with costs
        - Other qualifying life events
        """)
    
    # Decision Tree
    with st.expander("🔀 Decision Guide: Original Medicare vs Medicare Advantage", expanded=False):
        st.markdown("""
        #### Key Decision Factors
        
        **Choose Original Medicare + Medigap if you:**
        - Want freedom to see any doctor/specialist nationwide who accepts Medicare
        - Travel frequently or spend time in multiple states
        - Have complex medical needs requiring specialist care
        - Value predictable out-of-pocket costs
        - Can afford higher monthly premiums for comprehensive coverage
        
        **Choose Medicare Advantage if you:**
        - Prefer lower monthly premiums (often $0)
        - Are comfortable with network restrictions (HMO/PPO)
        - Stay in one geographic area
        - Want extra benefits (dental, vision, hearing, gym membership)
        - Have relatively simple medical needs
        - Can handle potentially higher out-of-pocket costs when sick
        
        #### Cost Comparison Example
        
        **Original Medicare + Medigap Plan G:**
        - Part B Premium: $174.70/month
        - Medigap Plan G: $150-250/month (varies by age, location, company)
        - Part D: $30-80/month
        - **Total: ~$355-505/month**
        - Predictable costs, minimal out-of-pocket when you need care
        
        **Medicare Advantage:**
        - Combined premium: $0-100/month (often $0)
        - Out-of-pocket maximum: $3,000-8,000/year
        - Copays for services: $10-50 per visit
        - **Total: Variable based on usage**
        - Lower monthly cost, but higher costs when you need care
        """)
    
    # The 20% Gap
    with st.expander("💰 Covering the 20% Gap: Medigap vs Advantage", expanded=False):
        st.markdown("""
        #### Understanding the 20% Coinsurance
        
        Original Medicare Part B covers 80% of approved costs after you meet the deductible.
        You're responsible for the remaining 20%, which has **no annual limit**. This can be
        financially devastating for expensive treatments.
        
        **Example of 20% Risk Without Supplemental Coverage:**
        - $100,000 hospital bill = $20,000 out-of-pocket
        - $500,000 cancer treatment = $100,000 out-of-pocket
        - **This unlimited exposure is why supplemental coverage is essential**
        
        #### ✅ Option 1: Medigap (Medicare Supplement Insurance) - STRONGLY RECOMMENDED
        
        **What it covers:**
        - Fills the gaps in Original Medicare
        - Covers the 20% coinsurance with **no limit**
        - May cover Part A deductible, Part B deductible, foreign travel emergency care
        - **No claim denials** - if Medicare approves it, Medigap pays
        - **No prior authorization** - get care when you need it
        
        **Popular Plans:**
        - **Plan G** (most popular): Covers everything except Part B deductible ($240)
        - **Plan N**: Lower premiums, small copays ($20 office, $50 ER)
        - **High Deductible Plan G**: Lower premiums, $2,800 deductible (2026)
        
        **Key Features:**
        - Guaranteed renewable for life
        - Works with any doctor who accepts Medicare (no networks)
        - Premiums increase with age but coverage remains comprehensive
        - No network restrictions - travel freely
        - **No fighting with insurance when you're sick**
        
        **When to Buy:**
        - **CRITICAL**: Buy during 6-month Medigap Open Enrollment (starts when you turn 65 and enroll in Part B)
        - Guaranteed issue regardless of health conditions during this window
        - After this window, you may face medical underwriting and denial
        - **This is your one chance to get Medigap without health questions**
        
        **Why Medigap is Worth the Extra Cost:**
        - Peace of mind when you're sick
        - No surprise bills
        - No claim denials to fight
        - Freedom to see any doctor
        - Comprehensive protection against catastrophic costs
        
        #### ⚠️ Option 2: Medicare Advantage - Understand the Risks
        
        **What it covers:**
        - Replaces Original Medicare
        - Includes the 20% coverage
        - Has an annual out-of-pocket maximum
        
        **Major Drawbacks:**
        - **Frequent claim denials** that can take months to resolve
        - **Prior authorization required** for many services (delays care)
        - Network restrictions (HMO/PPO) limit doctor choices
        - Networks change annually - you may lose your doctors
        - **Very difficult to switch back to Medigap** later
        - May include extra benefits, but at the cost of freedom and comprehensive coverage
        
        **⚠️ Warning**: While Medicare Advantage has an out-of-pocket maximum, getting to that
        point often involves fighting denials, waiting for authorizations, and dealing with
        network restrictions when you're sick and need care most.
        
        #### ❌ Option 3: No Supplemental Coverage (NEVER RECOMMENDED)
        
        **Risks:**
        - Unlimited exposure to 20% coinsurance
        - Financial catastrophe from serious illness
        - **This is the biggest mistake retirees make**
        - Don't risk your retirement savings on medical bills
        """)
    
    # Switching Rules
    with st.expander("🔄 What You Can and Cannot Switch", expanded=False):
        st.markdown("""
        #### 🚨 CRITICAL: The One-Way Door Problem
        
        **Switching FROM Original Medicare + Medigap TO Medicare Advantage**
        
        **When you can switch:**
        - During Annual Enrollment Period (October 15 - December 7)
        - During Medicare Advantage Open Enrollment (January 1 - March 31)
        - Special Enrollment Periods (if you qualify)
        
        **What happens:**
        - You can easily drop your Medigap policy
        - ⚠️ **CRITICAL WARNING**: If you later want to return to Medigap, you'll face medical underwriting
        - You may be **permanently denied** Medigap coverage due to health conditions
        - **This is almost always a one-way door - you can't go back**
        
        **Why This is Dangerous:**
        - Most people who switch to Advantage do so for the lower premium
        - When they get sick and face denials/restrictions, they want to switch back
        - By then, they have health conditions that make them uninsurable for Medigap
        - They're stuck in Medicare Advantage forever
        - **Don't make this mistake - start with Medigap and stay there**
        
        ---
        
        #### ⚠️ Switching FROM Medicare Advantage TO Original Medicare + Medigap
        
        **When you can switch:**
        - During Annual Enrollment Period (October 15 - December 7)
        - During Medicare Advantage Open Enrollment (January 1 - March 31)
        
        **The Major Challenge:**
        - You'll need to apply for Medigap coverage
        - **Medical underwriting applies** (except in rare guaranteed issue situations)
        - Insurance companies will review your health history
        - **They can deny you or charge much higher premiums based on health**
        - Pre-existing conditions (diabetes, heart disease, cancer, etc.) often result in denial
        - Even minor health issues can make you uninsurable
        - **Most people who try to switch back are denied**
        
        **Guaranteed Issue Rights (No Medical Underwriting) - RARE:**
        - Your Medicare Advantage plan leaves your area or stops providing care
        - You move out of the plan's service area
        - Your plan violated contract or misled you
        - You're in a Medicare SELECT policy and move out of area
        - You have Original Medicare and employer coverage ends
        
        **Reality Check:**
        - These guaranteed issue situations are rare
        - Most people don't qualify
        - Don't count on being able to switch back
        - **Assume Medicare Advantage is permanent once you choose it**
        
        #### Switching Between Medicare Advantage Plans
        
        **When you can switch:**
        - Annual Enrollment Period (October 15 - December 7)
        - Medicare Advantage Open Enrollment (January 1 - March 31, one change allowed)
        
        **What to consider:**
        - Check if your doctors are in the new plan's network
        - Compare out-of-pocket maximums
        - Review prescription drug coverage
        - Verify hospital and specialist access
        
        #### Switching Between Medigap Plans
        
        **When you can switch:**
        - Anytime, but subject to medical underwriting
        - Some states have additional protections (birthday rule, annual open enrollment)
        
        **States with Special Rules:**
        - **California**: Birthday Rule (30 days after birthday to switch to equal/lesser plan)
        - **Oregon**: Birthday Rule (similar to California)
        - **Missouri**: Annual open enrollment for Medigap
        - Check your state's specific rules
        """)
    
    # State Considerations
    with st.expander("🗺️ State-Specific Considerations", expanded=False):
        st.markdown("""
        #### Medicare Advantage Availability Varies by State
        
        **High Availability States:**
        - Florida, California, Texas, Arizona, Pennsylvania
        - Many plan options, competitive pricing
        - Extensive provider networks
        
        **Limited Availability States:**
        - Rural areas in Montana, Wyoming, Alaska
        - Fewer plan choices
        - Smaller provider networks
        
        #### State Medigap Protections
        
        **States with Birthday Rule:**
        - California, Oregon, Idaho, Illinois, Nevada
        - Allows annual switching to equal or lesser Medigap plans without underwriting
        
        **States with Continuous Open Enrollment:**
        - Connecticut, Maine, Massachusetts, New York
        - Can switch Medigap plans year-round with some protections
        
        **Community Rating States:**
        - Some states require community rating (same price regardless of age)
        - Others allow attained-age rating (premiums increase with age)
        - Issue-age rating (premium based on age when you first buy)
        
        #### State-Specific Programs
        
        **State Pharmaceutical Assistance Programs (SPAPs):**
        - Help with prescription drug costs
        - Eligibility varies by state
        - Can work alongside Medicare Part D
        
        **State Health Insurance Assistance Programs (SHIP):**
        - Free, unbiased Medicare counseling
        - Available in every state
        - Can help you compare plans and understand options
        """)
    
    # Doctor Access
    with st.expander("👨‍⚕️ Doctor Access and Network Concerns", expanded=False):
        st.markdown("""
        #### Original Medicare + Medigap
        
        **Advantages:**
        - See any doctor who accepts Medicare (about 93% of doctors)
        - No referrals needed for specialists
        - No network restrictions
        - Freedom to travel and get care anywhere in the US
        
        **Considerations:**
        - Some doctors don't accept new Medicare patients
        - A small percentage opt out of Medicare entirely
        - Always verify a new doctor accepts Medicare assignment
        
        #### Medicare Advantage
        
        **Network Types:**
        
        **HMO (Health Maintenance Organization):**
        - Must use network doctors (except emergencies)
        - Need referrals for specialists
        - Lower premiums, more restrictions
        - No coverage outside network (except emergencies)
        
        **PPO (Preferred Provider Organization):**
        - Can see out-of-network doctors (higher cost)
        - No referrals needed
        - Higher premiums, more flexibility
        - Some coverage outside network
        
        **PFFS (Private Fee-for-Service):**
        - Can see any doctor who accepts plan's terms
        - No network, but doctors can refuse
        - Less common
        
        **SNP (Special Needs Plan):**
        - For specific conditions or circumstances
        - Tailored networks and benefits
        
        **Critical Questions to Ask:**
        1. Are my current doctors in the network?
        2. Are my specialists in the network?
        3. Is my preferred hospital in the network?
        4. What happens if I need care while traveling?
        5. How do I get referrals to specialists?
        6. What if my doctor leaves the network?
        
        #### Losing Access to Your Doctor
        
        **With Medicare Advantage:**
        - Networks change annually
        - Doctors can leave networks
        - You may need to switch doctors or plans
        - Review network changes during Annual Enrollment Period
        
        **With Original Medicare + Medigap:**
        - Rare to lose access (only if doctor stops accepting Medicare)
        - More stability in doctor relationships
        - Easier to maintain continuity of care
        """)
    
    # Common Mistakes
    with st.expander("⚠️ Common Mistakes to Avoid", expanded=False):
        st.markdown("""
        #### Top 12 Medicare Enrollment Mistakes
        
        1. **Missing the Initial Enrollment Period**
           - Results in permanent late enrollment penalties
           - Can cost thousands over your lifetime
           - Set reminders 3 months before turning 65
        
        2. **Not Understanding Employer Coverage Coordination**
           - If you have employer coverage (20+ employees), you can delay Part B
           - If fewer than 20 employees, you MUST enroll in Medicare at 65
           - Get written confirmation from HR about your coverage
        
        3. **🚨 Choosing Medicare Advantage Over Medigap (BIGGEST MISTAKE)**
           - **This is the #1 regret among Medicare beneficiaries**
           - You may never be able to get Medigap later due to health conditions
           - Denials and prior authorization delays when you're sick
           - Network restrictions limit your doctor choices
           - **Start with Medigap - it's worth the extra cost**
        
        4. **Switching from Medigap to Medicare Advantage**
           - You may never be able to get Medigap again
           - Health conditions could make you permanently uninsurable
           - This is almost always irreversible
           - **Don't do it - even for a $0 premium**
        
        5. **Choosing Medicare Advantage Based Only on Premium**
           - $0 premium plans can have high out-of-pocket costs
           - Frequent denials can delay or prevent care
           - Check the out-of-pocket maximum and denial rates
           - Review copays, coinsurance, and prior authorization requirements
        
        6. **Not Checking if Your Doctors Are In-Network (Advantage Plans)**
           - Verify every doctor, specialist, and hospital
           - Networks change annually - you may lose your doctors
           - Out-of-network care can be very expensive or not covered
           - **With Medigap, this isn't a concern**
        
        7. **Ignoring Prescription Drug Coverage**
           - Part D late enrollment penalty is permanent
           - Check if your medications are covered
           - Review formulary tiers and restrictions
        
        8. **🚨 Not Understanding IRMAA Surcharges**
           - **IRMAA is based on your MAGI from 2 years prior**
           - 2026 premiums based on 2024 tax return
           - Can add $69.90 to $419.30/month to Part B premium
           - Plus $12.90 to $81.00/month to Part D premium
           - **Plan Roth conversions carefully to avoid IRMAA brackets**
           - Life-changing events may allow appeals
        
        9. **Not Buying Medigap During Open Enrollment**
           - 6-month window starting when you turn 65 and enroll in Part B
           - Guaranteed issue regardless of health
           - After this window, you may be denied or pay much more
           - **This is your one chance - don't miss it**
        
        10. **Assuming All Medigap Plans Are the Same**
            - Plans are standardized, but prices vary significantly
            - Shop around - same coverage, different prices
            - Consider financial strength of insurance company
        
        11. **Not Reviewing Coverage Annually**
            - Plans change benefits, costs, and networks every year
            - Annual Enrollment Period: October 15 - December 7
            - Review your coverage even if you're happy with it
        
        12. **Relying on Biased Advice**
            - Insurance agents may push Medicare Advantage for higher commissions
            - Use SHIP (State Health Insurance Assistance Program) for unbiased help
            - Get multiple quotes and opinions
            - **Be skeptical of agents pushing $0 premium plans**
        """)
    
    # HSA and Medicare Section
    with st.expander("💰 Health Savings Accounts (HSA) and Medicare", expanded=False):
        st.markdown("""
        #### Using Your HSA with Medicare
        
        If you're age 60+, you probably have figured out how to use your health savings account (HSA)
        to help pay for qualified medical expenses—and even save something extra for unanticipated
        health care expenses you may soon be facing in retirement.
        
        But watch out: There are a few important rules to follow if you want to avoid being subject
        to stern financial penalties when you enroll in Medicare in a few short years.
        
        #### 🚨 CRITICAL: Stop Contributing Before Medicare Enrollment
        
        **You must stop contributing to your HSA at least 6 months before you enroll in Medicare**,
        as Part A coverage is often backdated. This is one of the most important rules to avoid
        tax penalties.
        
        **Why 6 months?**
        - When you receive Social Security retirement benefits, your Part A coverage is back-dated
          6 months (but no earlier than the first month you're eligible for Medicare)
        - If you contribute to your HSA during those 6 months, you may face a **6% excise tax**
          and an **income tax** for those contributions
        - This "6-month lookback" starts when you enroll in Medicare or begin your Social Security
          retirement benefits
        
        **If you're currently contributing to your HSA and plan to start Medicare at age 65:**
        - Make sure all HSA contributions end **before your 65th birthday month**
        - If your birthday is on the first of the month, stop contributions by the beginning of
          the month before your birthday month
        
        **If you continue to work after age 65:**
        - Stop making contributions to your HSA up to 6 months before applying for Medicare Part A
          only or Part A and Part B or starting your Social Security retirement benefits
        - This HSA restriction leads some working past age 65 to defer Medicare and maintain their
          current employer-based health insurance coverage so they can keep contributing to their
          HSA until they retire
        
        **How to fix excess contributions:**
        - Withdraw your excess contributions by your tax filing deadline, including extensions,
          for the year you made them
        - Withdraw any earnings attributed to the withdrawn excess contributions and include the
          earnings in "other income" on your tax return for the year you withdrew them
        - Learn more about excess contributions on the IRS website
        
        #### ✅ What You CAN Use HSA Funds For with Medicare
        
        **Allowed Medicare Premiums (Tax-Free):**
        - ✅ Medicare Part A premiums (if you have to pay for Part A)
        - ✅ Medicare Part B premiums
        - ✅ Medicare Part C (Medicare Advantage) premiums
        - ✅ Medicare Part D (prescription drug) premiums
        - ✅ Employer-sponsored health premiums (if you're over 65 and still working)
        
        **Other Qualified Medical Expenses:**
        - ✅ Deductibles, copayments, and coinsurance
        - ✅ Vision and dental care
        - ✅ Hearing aids
        - ✅ Nursing services
        - ✅ Long-term care services
        - ✅ Medical equipment and supplies
        
        #### ❌ What You CANNOT Use HSA Funds For
        
        **🚨 Medigap/Medicare Supplement Premiums Are NOT Allowed**
        
        **No, you cannot use Health Savings Account (HSA) funds to pay for Medicare Supplement
        (Medigap) policy premiums.** IRS regulations do not consider Medigap premiums a qualified
        medical expense, making them ineligible for tax-free HSA reimbursement.
        
        This is an important distinction because:
        - Medigap premiums can be $150-250/month or more
        - You'll need to pay these from other sources (not your HSA)
        - This is a key cost to factor into your Medicare budget
        
        #### 💡 HSA Advantage: Medicare Advantage vs Medigap
        
        **For Cost-Conscious Retirees with HSA Funds:**
        
        If you have a substantial HSA balance, there's a financial advantage to choosing Medicare
        Advantage over Original Medicare + Medigap:
        
        **Medicare Advantage + HSA = Tax-Free Premium Payments**
        - ✅ Medicare Advantage premiums CAN be paid with HSA funds (tax-free)
        - ✅ Often $0-100/month premiums (many plans are $0)
        - ✅ Use your HSA tax-free for premiums, copays, and out-of-pocket costs
        - ✅ Maximize the value of your HSA savings
        - ✅ Lower monthly costs leave more room in your budget
        
        **Original Medicare + Medigap = Higher Out-of-Pocket Costs**
        - ❌ Medigap premiums CANNOT be paid with HSA funds
        - ❌ Medigap premiums: $150-250+/month (must pay with after-tax dollars)
        - ✅ Part B premiums CAN be paid with HSA funds
        - Higher total monthly costs ($355-505/month typical)
        
        **Cost Comparison Example with HSA:**
        
        **Medicare Advantage Path:**
        - Part B: $174.70/month (HSA eligible ✅)
        - Medicare Advantage: $0-50/month (HSA eligible ✅)
        - **Total: $174.70-224.70/month - ALL can be paid tax-free from HSA**
        - Out-of-pocket max: $3,000-8,000/year (HSA eligible ✅)
        
        **Original Medicare + Medigap Path:**
        - Part B: $174.70/month (HSA eligible ✅)
        - Medigap Plan G: $150-250/month (NOT HSA eligible ❌)
        - Part D: $30-80/month (HSA eligible ✅)
        - **Total: $355-505/month - Only $205-255 can be paid from HSA**
        - **$150-250/month must come from other sources**
        
        **Financial Benefit for HSA Holders:**
        - With Medicare Advantage, you can use your HSA for 100% of premiums
        - With Medigap, you lose the tax advantage on $1,800-3,000/year in premiums
        - Over 20 years of retirement, that's $36,000-60,000 in premiums that can't use HSA funds
        - If you have a large HSA balance, Medicare Advantage lets you maximize its tax-free benefit
        
        **⚠️ Important Considerations:**
        
        While the HSA advantage favors Medicare Advantage financially, remember:
        - Medicare Advantage has network restrictions and prior authorization requirements
        - Switching back to Medigap later is very difficult due to medical underwriting
        - The tax savings may not outweigh the loss of freedom and comprehensive coverage
        - Consider your health status, travel plans, and doctor preferences
        - **This is a personal decision** - the HSA benefit is just one factor
        
        **Best for HSA + Medicare Advantage:**
        - You have a substantial HSA balance ($50,000+)
        - You want to maximize tax-free healthcare spending
        - You're comfortable with network restrictions
        - You stay in one geographic area
        - You have relatively simple medical needs
        - Lower monthly costs are a priority
        
        **Best for HSA + Medigap (Despite No HSA Benefit):**
        - You value freedom to see any doctor
        - You travel frequently or have complex medical needs
        - You can afford the higher premiums from other sources
        - Peace of mind is worth more than tax savings
        - You want comprehensive coverage without claim denials
        
        #### 💡 HSA Triple Tax Advantage
        
        HSAs offer triple tax savings:
        1. **Contribute pre-tax dollars** - Reduces your taxable income
        2. **Earnings grow tax-deferred** - No taxes on investment gains
        3. **Withdraw tax-free for qualified medical expenses** - Including Medicare premiums
        
        #### 🏥 Bridging the Gap to Medicare (Before Age 65)
        
        If you retired before age 65, you still need health care coverage before enrolling in Medicare.
        You may be able to use your HSA to pay for insurance premiums, but the situations in which
        you can do so are limited:
        
        **Allowed Premium Payments Before Age 65:**
        - ✅ COBRA continuation coverage
        - ✅ Health insurance while receiving unemployment compensation
        - ❌ Other health insurance premiums (not allowed before age 65)
        
        #### 📊 After Age 65: Expanded HSA Flexibility
        
        Once you turn age 65, you can use your HSA to pay for any nonqualified medical expenses
        (like buying a boat or new patio furniture), but you don't get to take full advantage of
        the tax savings:
        - You're required to pay federal and potentially state taxes for such expenditures
        - No 20% penalty (unlike withdrawals before age 65)
        - However, it's still better to use HSA funds for qualified medical expenses to maximize
          tax benefits
        
        **Note:** If you're not age 65 or older, you will pay a 20% penalty and taxes on withdrawals
        for anything other than qualified medical expenses.
        
        #### 🎯 Strategic HSA Planning for Medicare
        
        **Best Practices:**
        1. **Build your HSA balance before Medicare** - Maximize contributions while you can
        2. **Stop contributions 6 months before Medicare** - Avoid tax penalties
        3. **Use HSA for Medicare premiums** - Parts A, B, C, D (but not Medigap)
        4. **Save HSA for medical expenses** - Let it grow tax-free for healthcare costs
        5. **Consider delaying Medicare if still working** - Keep contributing to HSA
        
        **Tax Planning Opportunity:**
        - HSA withdrawals for Medicare premiums are tax-free
        - This can help manage your taxable income in retirement
        - Coordinate with Roth conversions and other income strategies
        - Remember: IRMAA surcharges are based on income from 2 years prior
        
        #### ⚠️ Common HSA and Medicare Mistakes
        
        1. **Contributing to HSA after enrolling in Medicare** - Results in tax penalties
        2. **Not stopping contributions 6 months before Medicare** - Backdated Part A causes issues
        3. **Trying to use HSA for Medigap premiums** - Not allowed by IRS
        4. **Not maximizing HSA before Medicare** - Missing opportunity to build tax-free healthcare fund
        5. **Withdrawing HSA for non-medical expenses before 65** - 20% penalty plus taxes
        
        #### 📋 HSA and Medicare Checklist
        
        **12 Months Before Medicare:**
        - [ ] Review your HSA balance and contribution strategy
        - [ ] Maximize contributions if possible
        - [ ] Plan when to stop contributions (6 months before Medicare)
        
        **6 Months Before Medicare:**
        - [ ] Stop all HSA contributions (yours and employer's)
        - [ ] Notify your employer to stop HSA contributions
        - [ ] Verify no contributions are being made
        
        **At Medicare Enrollment:**
        - [ ] Confirm HSA contributions have stopped
        - [ ] Plan to use HSA for Medicare Part B, C, D premiums
        - [ ] Budget for Medigap premiums from other sources (not HSA)
        - [ ] Keep HSA funds invested for future medical expenses
        
        **After Medicare Enrollment:**
        - [ ] Use HSA for qualified Medicare expenses
        - [ ] Track HSA withdrawals for tax purposes
        - [ ] Continue to let unused HSA funds grow tax-free
        - [ ] Remember: You can still use HSA funds, just can't contribute
        """)
    
    # Action Checklist
    with st.expander("✅ Medicare Enrollment Checklist", expanded=False):
        st.markdown("""
        #### 6 Months Before Turning 65
        - [ ] Determine if you need to enroll or can delay (employer coverage?)
        - [ ] Research Original Medicare vs Medicare Advantage
        - [ ] List your current doctors and medications
        - [ ] Contact SHIP for free counseling
        - [ ] Review your state's specific Medicare rules
        
        #### 3 Months Before Turning 65
        - [ ] Enroll in Part A (if not automatic)
        - [ ] Decide on Part B enrollment timing
        - [ ] If choosing Original Medicare, research Medigap plans
        - [ ] If choosing Medicare Advantage, compare plans in your area
        - [ ] Research Part D prescription drug plans
        - [ ] Verify doctor and hospital networks
        
        #### During Your Birthday Month
        - [ ] Complete all enrollment applications
        - [ ] Confirm coverage start dates
        - [ ] Set up premium payments
        - [ ] Request Medicare card if not received
        
        #### After Enrollment
        - [ ] Receive Medicare card and supplemental insurance cards
        - [ ] Inform doctors of your new coverage
        - [ ] Update pharmacy with Part D information
        - [ ] Keep all enrollment documents
        - [ ] Set calendar reminder for Annual Enrollment Period
        
        #### Annual Review (Every October)
        - [ ] Review Annual Notice of Change from your plans
        - [ ] Check if doctors are still in network
        - [ ] Verify medications are still covered
        - [ ] Compare plans during Annual Enrollment Period
        - [ ] Make changes if needed (effective January 1)
        """)
    
    # Resources
    with st.expander("📚 Additional Resources", expanded=False):
        st.markdown("""
        #### Official Medicare Resources
        
        **Medicare.gov**
        - Official Medicare website
        - Plan comparison tool
        - Coverage information
        - Find doctors and facilities
        
        **1-800-MEDICARE (1-800-633-4227)**
        - 24/7 customer service
        - TTY: 1-877-486-2048
        - Help with enrollment and questions
        
        **State Health Insurance Assistance Program (SHIP)**
        - Free, unbiased Medicare counseling
        - Find your local SHIP: www.shiphelp.org
        - One-on-one help with plan selection
        
        #### Plan Comparison Tools
        
        **Medicare Plan Finder**
        - Compare all plans in your area
        - Enter your medications for accurate cost estimates
        - Check doctor and pharmacy networks
        - Available at www.medicare.gov/plan-compare
        
        **Medigap Plan Comparison**
        - Compare standardized Medigap plans
        - Get quotes from multiple companies
        - Review financial ratings of insurers
        
        #### Educational Resources
        
        **Medicare & You Handbook**
        - Comprehensive annual guide
        - Mailed to all Medicare beneficiaries
        - Available online at Medicare.gov
        
        **State Insurance Department**
        - State-specific Medicare rules
        - Consumer protection
        - Complaint resolution
        
        #### Important Phone Numbers
        
        - **Social Security**: 1-800-772-1213
        - **Medicare**: 1-800-633-4227
        - **Medicare Rights Center**: 1-800-333-4114
        - **SHIP**: Find local number at shiphelp.org
        - **State Insurance Department**: Varies by state
        """)

# ── SOCIAL SECURITY ENROLLMENT GUIDE ──────────────────────────────────────────
with adv_ssa_tab:
    st.markdown("### 💰 Social Security Enrollment Guide")
    st.markdown("""
    This comprehensive guide helps you navigate Social Security enrollment, understand your options,
    optimize your claiming strategy, and avoid costly mistakes. Social Security decisions are often
    irreversible, so it's crucial to understand your choices before enrolling.
    
    ⚠️ **Critical Connection with Medicare**: Enrolling in Social Security retirement benefits
    automatically enrolls you in Medicare Part A (and Part B unless you opt out). This has important
    implications for HSA contributions and healthcare planning.
    """)
    
    # Overview Section
    with st.expander("📋 Social Security Basics: What You Need to Know", expanded=False):
        st.markdown("""
        #### Understanding Social Security Retirement Benefits
        
        **What is Social Security?**
        - Monthly retirement income based on your lifetime earnings
        - Funded by payroll taxes (FICA) you paid during your working years
        - Provides inflation-adjusted income for life
        - Spousal and survivor benefits available
        
        **Key Ages:**
        - **Age 62**: Earliest you can claim (reduced benefits)
        - **Full Retirement Age (FRA)**: 66-67 depending on birth year
          - Born 1943-1954: FRA is 66
          - Born 1955: FRA is 66 and 2 months
          - Born 1956: FRA is 66 and 4 months
          - Born 1957: FRA is 66 and 6 months
          - Born 1958: FRA is 66 and 8 months
          - Born 1959: FRA is 66 and 10 months
          - Born 1960 or later: FRA is 67
        - **Age 70**: Maximum benefit (8% increase per year after FRA)
        
        **Benefit Calculation:**
        - Based on your highest 35 years of earnings
        - Indexed for inflation
        - If you worked fewer than 35 years, zeros are averaged in
        - Claiming early reduces benefits permanently
        - Delaying past FRA increases benefits permanently
        
        **Reduction for Early Claiming:**
        - Claim at 62 (FRA 67): ~30% reduction (70% of FRA benefit)
        - Claim at 63 (FRA 67): ~25% reduction
        - Claim at 64 (FRA 67): ~20% reduction
        - Claim at 65 (FRA 67): ~13.3% reduction
        - Claim at 66 (FRA 67): ~6.7% reduction
        
        **Increase for Delayed Claiming:**
        - Delay to 68 (FRA 67): +8% (108% of FRA benefit)
        - Delay to 69 (FRA 67): +16% (116% of FRA benefit)
        - Delay to 70 (FRA 67): +24% (124% of FRA benefit)
        - **No benefit to delaying past age 70**
        """)
    
    # Medicare Connection
    with st.expander("🏥 Critical: Social Security and Medicare Connection", expanded=False):
        st.markdown("""
        #### 🚨 Automatic Medicare Enrollment When You Claim Social Security
        
        **The Connection:**
        - When you apply for Social Security retirement benefits, you are **automatically enrolled
          in Medicare Part A and Part B**
        - Part A enrollment is backdated 6 months (or to age 65, whichever is later)
        - You can opt out of Part B, but Part A enrollment is automatic
        
        **Critical HSA Implications:**
        - Once enrolled in Medicare Part A, you **cannot contribute to an HSA**
        - Part A is backdated 6 months, so you may owe penalties for HSA contributions during that period
        - If you're still working and contributing to an HSA, **do not claim Social Security** until
          you're ready to stop HSA contributions
        
        **Strategies to Preserve HSA Contributions:**
        
        **Option 1: Delay Social Security Past 65**
        - Continue working and contributing to HSA
        - Delay Social Security until you're ready to stop HSA contributions
        - Enroll in Medicare separately when you stop working
        - Maximize both HSA contributions and Social Security delayed credits
        
        **Option 2: Claim Social Security, Stop HSA Contributions**
        - Stop HSA contributions 6 months before claiming Social Security
        - Accept automatic Medicare enrollment
        - Use existing HSA funds for Medicare premiums and expenses
        
        **Option 3: Opt Out of Part B (But Not Part A)**
        - You can decline Part B if you have employer coverage
        - Part A is still automatic (and free for most people)
        - HSA contributions still prohibited once Part A starts
        - Must enroll in Part B within 8 months of losing employer coverage to avoid penalties
        
        #### When to Enroll in Medicare vs Social Security
        
        **Scenario 1: Still Working at 65 with Employer Coverage (20+ employees)**
        - Delay Medicare Part B (keep employer coverage)
        - Part A is free, so usually accept it
        - Can delay Social Security to age 70 for maximum benefit
        - **Problem**: Part A enrollment stops HSA contributions
        
        **Scenario 2: Still Working at 65 with HSA**
        - Delay both Social Security and Medicare
        - Continue HSA contributions
        - Enroll in Medicare when you stop working
        - Claim Social Security when optimal (up to age 70)
        
        **Scenario 3: Retired Before 65**
        - Decide Social Security claiming age independently (62-70)
        - Must enroll in Medicare at 65 to avoid penalties
        - If claiming Social Security before 65, Medicare enrollment is separate
        - If claiming Social Security at/after 65, Medicare enrollment is automatic
        
        **Scenario 4: Need Income at 62, Want to Maximize Benefits**
        - Claim Social Security at 62 for income
        - Enroll in Medicare separately at 65
        - Accept reduced Social Security benefit
        - Consider if other income sources could delay claiming
        """)
    
    # When to Enroll
    with st.expander("⏰ When to Enroll: Timing Your Application", expanded=False):
        st.markdown("""
        #### Application Timeline
        
        **When Can You Apply?**
        - You can apply up to **4 months before** you want benefits to start
        - Earliest benefit start: Age 62
        - Latest benefit increase: Age 70
        
        **Recommended Application Timeline:**
        
        **If Claiming at 62:**
        - Apply 3-4 months before your 62nd birthday
        - Benefits can start as early as the month you turn 62
        - Allows time for processing
        
        **If Claiming at Full Retirement Age:**
        - Apply 3 months before your FRA birthday month
        - Ensures benefits start on time
        - Avoids processing delays
        
        **If Claiming at 70:**
        - Apply 3-4 months before turning 70
        - Don't wait past 70 - no additional benefit
        - Ensures you don't miss any payments
        
        #### Processing Timeline
        
        **Application to First Payment:**
        - **Application processing**: 2-4 weeks typically
        - **First payment**: Usually 2-3 months after application
        - **Direct deposit setup**: 1-2 weeks after approval
        - **Retroactive payments**: If applicable, paid in lump sum
        
        **Example Timeline (Claiming at FRA):**
        - 3 months before birthday: Submit application
        - 2-3 weeks later: Application approved
        - Birthday month: Benefits begin
        - 1 month after birthday: First payment received (for birthday month)
        - Ongoing: Payments on 2nd, 3rd, or 4th Wednesday based on birth date
        
        #### Payment Schedule
        
        **When You Get Paid:**
        - Benefits are paid the month after they're earned
        - Payment date based on your birth date:
          - Born 1st-10th: 2nd Wednesday of month
          - Born 11th-20th: 3rd Wednesday of month
          - Born 21st-31st: 4th Wednesday of month
        - If you claimed before May 1997: Payment on 3rd of month
        
        **Direct Deposit:**
        - Required for all new beneficiaries (since 2013)
        - Set up during application process
        - Funds typically available on payment date
        - Can take 1-2 business days to appear in account
        - More secure than paper checks
        """)
    
    # How to Enroll
    with st.expander("📝 How to Enroll: Application Process", expanded=False):
        st.markdown("""
        #### Three Ways to Apply
        
        **1. Online (Recommended) ✅**
        - **Website**: www.ssa.gov/benefits/retirement/apply.html
        - **Advantages**:
          - Apply anytime, 24/7
          - Save and return to application
          - Faster processing
          - Immediate confirmation
          - No appointment needed
        - **Time required**: 15-30 minutes
        - **Best for**: Most applicants, especially straightforward cases
        
        **2. By Phone**
        - **Number**: 1-800-772-1213 (TTY 1-800-325-0778)
        - **Hours**: Monday-Friday, 8:00 AM - 7:00 PM local time
        - **Advantages**:
          - Can ask questions during application
          - Help with complex situations
          - Assistance for those uncomfortable with online
        - **Disadvantages**:
          - Long wait times (especially Monday mornings)
          - Limited hours
        - **Best for**: Complex cases, need assistance
        
        **3. In Person**
        - **Location**: Local Social Security office
        - **Appointment**: Required - call 1-800-772-1213 or schedule online
        - **Advantages**:
          - Face-to-face assistance
          - Can bring documents for review
          - Help with complex situations
        - **Disadvantages**:
          - Must schedule appointment
          - Travel required
          - Limited office hours
        - **Best for**: Very complex cases, prefer in-person help
        
        #### Required Information for Application
        
        **Personal Information:**
        - [ ] Social Security number
        - [ ] Birth certificate or proof of birth
        - [ ] U.S. citizenship or lawful alien status documents
        - [ ] Military service papers (if applicable - DD-214)
        - [ ] W-2 forms or self-employment tax returns for last year
        
        **Banking Information for Direct Deposit:**
        - [ ] Bank name
        - [ ] Routing number (9 digits)
        - [ ] Account number
        - [ ] Account type (checking or savings)
        - [ ] Voided check or bank letter (helpful but not required)
        
        **Spouse Information (if applicable):**
        - [ ] Spouse's Social Security number
        - [ ] Spouse's date of birth
        - [ ] Marriage certificate
        - [ ] Divorce decree (if claiming on ex-spouse's record)
        
        **Children Information (if applicable):**
        - [ ] Children's Social Security numbers
        - [ ] Children's birth certificates
        - [ ] Proof of adoption (if applicable)
        
        **Work History:**
        - [ ] Employer names and addresses for last 2 years
        - [ ] Dates of employment
        - [ ] Self-employment information (if applicable)
        
        #### Documents to Have Ready
        
        **Essential Documents:**
        1. **Birth Certificate** - Original or certified copy
        2. **Social Security Card** - Or know your number
        3. **W-2 Forms** - Most recent year
        4. **Tax Returns** - If self-employed
        5. **Bank Information** - For direct deposit
        
        **Additional Documents (if applicable):**
        6. **Marriage Certificate** - For spousal benefits
        7. **Divorce Decree** - If claiming on ex-spouse
        8. **Death Certificate** - For survivor benefits
        9. **Military Discharge Papers** - DD-214
        10. **Proof of Citizenship** - If not born in U.S.
        
        **Tips for Document Preparation:**
        - Make copies of all documents before submitting
        - SSA will return original documents
        - If you don't have a document, SSA can help you get it
        - Some documents can be uploaded online
        - Keep confirmation numbers from online applications
        """)
    
    # Spousal Benefits
    with st.expander("👫 Spousal and Survivor Benefits", expanded=False):
        st.markdown("""
        #### Spousal Benefits
        
        **Eligibility:**
        - Married for at least 1 year
        - Spouse must have filed for their own benefit
        - You must be at least 62 years old
        - Or caring for child under 16 (or disabled)
        
        **Benefit Amount:**
        - Up to 50% of spouse's FRA benefit
        - Reduced if claimed before your FRA
        - Not increased by delaying past your FRA
        - You receive the higher of: your own benefit or spousal benefit
        
        **Claiming Strategy:**
        - If your own benefit is higher, claim your own
        - If spousal benefit is higher, you'll automatically receive it
        - Can't claim spousal benefit until spouse files
        - Deemed filing rules: If you claim before FRA, you must claim all benefits
        
        **Divorced Spouse Benefits:**
        - Marriage lasted at least 10 years
        - You're unmarried
        - You're at least 62
        - Ex-spouse is entitled to benefits (doesn't have to be claiming)
        - Your benefit doesn't affect ex-spouse's benefit
        - Ex-spouse doesn't need to know you're claiming
        
        #### Survivor Benefits
        
        **Eligibility:**
        - Widow/widower of deceased worker
        - At least 60 years old (50 if disabled)
        - Or caring for child under 16 (or disabled)
        - Marriage lasted at least 9 months (exceptions for accidents)
        
        **Benefit Amount:**
        - Up to 100% of deceased spouse's benefit
        - Amount depends on when deceased spouse claimed
        - Reduced if you claim before your FRA
        - Can switch from survivor to your own benefit later
        
        **Strategic Claiming:**
        - Claim survivor benefit at 60, switch to your own at 70
        - Claim your own benefit early, switch to survivor at FRA
        - Choose strategy that maximizes lifetime benefits
        - Survivor benefits have different FRA than retirement benefits
        
        **Divorced Survivor Benefits:**
        - Marriage lasted at least 10 years
        - You're unmarried (or remarried after age 60)
        - Same benefit as if still married
        - Ex-spouse's remarriage doesn't affect your benefit
        """)
    
    # Working While Receiving Benefits
    with st.expander("💼 Working While Receiving Social Security", expanded=False):
        st.markdown("""
        #### Earnings Test (Before Full Retirement Age)
        
        **If You're Under FRA for the Entire Year:**
        - **2026 Limit**: $22,320 per year
        - **Penalty**: $1 in benefits withheld for every $2 earned above limit
        - **Example**: Earn $32,320 = $10,000 over limit = $5,000 withheld
        
        **In the Year You Reach FRA:**
        - **2026 Limit**: $59,520 per year (only months before FRA count)
        - **Penalty**: $1 withheld for every $3 earned above limit
        - **After FRA month**: No earnings limit
        
        **After Full Retirement Age:**
        - **No earnings limit** - Earn as much as you want
        - No benefit reduction
        - Benefits may increase due to additional earnings
        
        #### What Counts as Earnings?
        
        **Counts Toward Limit:**
        - ✅ Wages from employment
        - ✅ Net self-employment income
        - ✅ Bonuses and commissions
        
        **Does NOT Count:**
        - ❌ Pensions
        - ❌ Annuities
        - ❌ Investment income
        - ❌ Interest and dividends
        - ❌ Capital gains
        - ❌ Rental income (if not real estate business)
        - ❌ IRA/401(k) withdrawals
        
        #### Benefits Are Not Lost Forever
        
        **Important**: Withheld benefits are not lost!
        - At FRA, SSA recalculates your benefit
        - Increases your benefit to account for months withheld
        - Essentially converts early claiming to later claiming
        - You'll eventually receive the money
        
        **Example:**
        - Claim at 62, work and have benefits withheld for 3 years
        - At FRA, benefit is recalculated as if you claimed at 65
        - Higher monthly benefit for rest of life
        """)
    
    # Taxation
    with st.expander("💰 Taxation of Social Security Benefits", expanded=False):
        st.markdown("""
        #### How Social Security is Taxed
        
        **Combined Income Formula:**
        - Adjusted Gross Income (AGI)
        - Plus: Tax-exempt interest
        - Plus: 50% of Social Security benefits
        - = Combined Income
        
        **Taxation Thresholds (2026):**
        
        **Single Filers:**
        - Combined income < $25,000: 0% taxable
        - Combined income $25,000-$34,000: Up to 50% taxable
        - Combined income > $34,000: Up to 85% taxable
        
        **Married Filing Jointly:**
        - Combined income < $32,000: 0% taxable
        - Combined income $32,000-$44,000: Up to 50% taxable
        - Combined income > $44,000: Up to 85% taxable
        
        **Married Filing Separately:**
        - Usually 85% of benefits are taxable
        - Very limited exceptions
        
        #### Tax Planning Strategies
        
        **Minimize Taxable Social Security:**
        1. **Roth conversions before claiming** - Reduce future RMDs
        2. **Qualified Charitable Distributions (QCDs)** - Reduce AGI
        3. **Tax-loss harvesting** - Offset capital gains
        4. **Manage retirement account withdrawals** - Control AGI
        5. **Consider Roth accounts** - Withdrawals don't count as income
        
        **State Taxation:**
        - 38 states don't tax Social Security benefits
        - 12 states do tax benefits (some with exemptions):
          - Colorado, Connecticut, Kansas, Minnesota, Missouri
          - Montana, Nebraska, New Mexico, Rhode Island
          - Utah, Vermont, West Virginia
        - Check your state's specific rules
        
        #### Withholding Options
        
        **Voluntary Withholding:**
        - You can request federal tax withholding
        - Choose 7%, 10%, 12%, or 22%
        - Use Form W-4V
        - Can change anytime
        - Helps avoid underpayment penalties
        
        **Estimated Tax Payments:**
        - If not withholding, may need quarterly estimated payments
        - Use Form 1040-ES
        - Due dates: April 15, June 15, September 15, January 15
        - Avoid underpayment penalties
        """)
    
    # Opting Out and Suspending
    with st.expander("🔄 Can You Opt Out, Suspend, or Change Your Mind?", expanded=False):
        st.markdown("""
        #### Withdrawing Your Application (Within 12 Months)
        
        **The Do-Over Option:**
        - Available only once in your lifetime
        - Must be within 12 months of claiming
        - Must repay all benefits received (including spousal/dependent benefits)
        - No interest charged on repayment
        - Resets your record as if you never claimed
        
        **How to Withdraw:**
        1. Complete Form SSA-521 (Request for Withdrawal)
        2. Submit to Social Security
        3. Repay all benefits within 60 days of approval
        4. Can reapply later for higher benefit
        
        **When This Makes Sense:**
        - Claimed early and regret it
        - Financial situation improved
        - Want to maximize lifetime benefits
        - Can afford to repay benefits
        
        **Example:**
        - Claimed at 62, received $20,000 in benefits
        - Within 12 months, repay $20,000
        - Wait until 70 to claim for 76% higher benefit
        - Lifetime benefit increase can be substantial
        
        #### Suspending Benefits (After Full Retirement Age)
        
        **Voluntary Suspension:**
        - Available only after reaching FRA
        - Can suspend for any reason
        - Benefits grow 8% per year while suspended
        - Can suspend up to age 70
        - No repayment required
        - Can restart anytime
        
        **How to Suspend:**
        1. Call Social Security: 1-800-772-1213
        2. Or visit local office
        3. Request voluntary suspension
        4. Effective the month after request
        
        **When This Makes Sense:**
        - Returned to work after claiming
        - Don't need the income currently
        - Want to increase future benefits
        - Maximize survivor benefit for spouse
        
        **Important Notes:**
        - Spousal benefits also suspended
        - Medicare premiums still deducted (if applicable)
        - Can restart benefits anytime
        - Automatic restart at age 70
        
        #### Changing Your Mind After FRA
        
        **After 12-Month Window:**
        - Can't withdraw application
        - Can suspend benefits (if at FRA)
        - Can't undo claiming decision
        - Stuck with reduced benefit if claimed early
        
        **This is Why Timing Matters:**
        - Early claiming decision is mostly permanent
        - Only one 12-month do-over opportunity
        - Suspension only available after FRA
        - Plan carefully before claiming
        """)
    
    # Common Mistakes
    with st.expander("⚠️ Common Social Security Mistakes to Avoid", expanded=False):
        st.markdown("""
        #### Top 15 Social Security Mistakes
        
        1. **Claiming Too Early Without Considering Longevity**
           - Claiming at 62 reduces benefits by ~30%
           - Break-even age is typically around 78-80
           - If you live past break-even, you lose money
           - Consider family longevity and health
        
        2. **Not Coordinating with Medicare and HSA**
           - Claiming Social Security auto-enrolls you in Medicare
           - Medicare Part A stops HSA contributions
           - Part A is backdated 6 months
           - Can owe penalties for HSA contributions during backdated period
        
        3. **Ignoring Spousal Benefits**
           - Spousal benefit can be up to 50% of spouse's FRA benefit
           - May be higher than your own benefit
           - Divorced spouses (10+ year marriage) also eligible
           - Doesn't reduce spouse's benefit
        
        4. **Not Understanding Survivor Benefits**
           - Survivor gets up to 100% of deceased spouse's benefit
           - Can claim survivor benefit and switch to own later
           - Strategic claiming can maximize lifetime benefits
           - Divorced spouses (10+ year marriage) eligible
        
        5. **Claiming Early While Still Working**
           - Earnings test reduces benefits before FRA
           - $1 withheld for every $2 over limit (under FRA)
           - Benefits are recalculated later, but creates cash flow issues
           - Better to delay claiming if still earning
        
        6. **Not Checking Your Earnings Record**
           - Benefits based on highest 35 years of earnings
           - Errors in earnings record reduce benefits
           - Check annually at www.ssa.gov/myaccount
           - Report errors immediately
        
        7. **Forgetting About Taxes**
           - Up to 85% of benefits may be taxable
           - Depends on combined income
           - Can push you into higher tax bracket
           - Plan for tax withholding or estimated payments
        
        8. **Not Maximizing Delayed Retirement Credits**
           - Benefits increase 8% per year from FRA to 70
           - That's a guaranteed 8% return
           - No benefit to delaying past 70
           - Consider if you can afford to wait
        
        9. **Claiming Before Reviewing All Options**
           - Many claiming strategies available
           - Spousal, survivor, divorced spouse benefits
           - File and suspend (if at FRA)
           - Consult with financial advisor
        
        10. **Not Setting Up Direct Deposit**
            - Required for new beneficiaries
            - More secure than paper checks
            - Faster access to funds
            - Set up during application
        
        11. **Ignoring State Taxation**
            - 12 states tax Social Security benefits
            - May affect where you retire
            - Some states have income exemptions
            - Factor into retirement planning
        
        12. **Not Understanding the Earnings Test**
            - Only applies before FRA
            - Many types of income don't count
            - Withheld benefits aren't lost forever
            - Benefits recalculated at FRA
        
        13. **Claiming Without Considering Inflation**
            - Benefits are adjusted for inflation (COLA)
            - Higher initial benefit = higher COLA increases
            - Compounds over lifetime
            - Delaying increases inflation-adjusted income
        
        14. **Not Coordinating with Overall Retirement Plan**
            - Social Security is one piece of retirement income
            - Coordinate with pensions, 401(k), IRA withdrawals
            - Consider tax implications of all income sources
            - Optimize total retirement income strategy
        
        15. **Relying on Social Security Alone**
            - Average benefit: ~$1,900/month (2026)
            - Replaces only ~40% of pre-retirement income
            - Need additional retirement savings
            - Plan for healthcare costs not covered by Medicare
        """)
    
    # Enrollment Checklist
    with st.expander("✅ Social Security Enrollment Checklist", expanded=False):
        st.markdown("""
        #### 12 Months Before Claiming
        - [ ] Review your earnings record at www.ssa.gov/myaccount
        - [ ] Correct any errors in your earnings history
        - [ ] Estimate your benefit at different claiming ages
        - [ ] Consider longevity, health, and family history
        - [ ] Review spousal and survivor benefit options
        - [ ] Coordinate with Medicare enrollment plans
        - [ ] Check HSA contribution implications
        - [ ] Consult with financial advisor on claiming strategy
        
        #### 6 Months Before Claiming
        - [ ] Decide on claiming age (62-70)
        - [ ] If claiming before 65, plan separate Medicare enrollment
        - [ ] If claiming at/after 65, understand automatic Medicare enrollment
        - [ ] Stop HSA contributions if claiming at/after 65
        - [ ] Gather required documents (birth certificate, W-2s, etc.)
        - [ ] Set up direct deposit information
        - [ ] Review tax withholding options
        - [ ] Plan for taxation of benefits
        
        #### 4 Months Before Claiming
        - [ ] Submit online application at www.ssa.gov
        - [ ] Or schedule phone/in-person appointment
        - [ ] Upload or mail required documents
        - [ ] Confirm direct deposit setup
        - [ ] Request tax withholding if desired (Form W-4V)
        - [ ] Save application confirmation number
        
        #### After Application Submitted
        - [ ] Wait for approval notification (2-4 weeks)
        - [ ] Confirm benefit start date
        - [ ] Confirm payment schedule (based on birth date)
        - [ ] Set up online account at www.ssa.gov/myaccount
        - [ ] Verify direct deposit is working
        - [ ] Keep all correspondence from SSA
        
        #### First Payment Received
        - [ ] Verify payment amount is correct
        - [ ] Confirm direct deposit is working properly
        - [ ] Set up tax withholding if not done already
        - [ ] Plan for quarterly estimated tax payments if needed
        - [ ] Update budget with actual benefit amount
        - [ ] Coordinate with other retirement income sources
        
        #### Annual Review
        - [ ] Review annual COLA adjustment notice
        - [ ] Check for any changes in benefit amount
        - [ ] Verify earnings record is still accurate
        - [ ] Review tax withholding adequacy
        - [ ] Adjust estimated tax payments if needed
        - [ ] Update retirement income plan
        """)
    
    # Resources
    with st.expander("📚 Additional Resources", expanded=False):
        st.markdown("""
        #### Official Social Security Resources
        
        **Social Security Administration Website**
        - www.ssa.gov
        - Create account: www.ssa.gov/myaccount
        - Benefit calculators and estimators
        - Online application portal
        - Check earnings record
        
        **Social Security Phone Numbers**
        - **Main number**: 1-800-772-1213
        - **TTY**: 1-800-325-0778
        - **Hours**: Monday-Friday, 8:00 AM - 7:00 PM local time
        - **Best times to call**: Mid-week, mid-month, mid-morning
        
        **Local Social Security Office**
        - Find office: www.ssa.gov/locator
        - Appointments required
        - Schedule online or by phone
        - Bring all required documents
        
        #### Planning Tools
        
        **Benefit Calculators**
        - **Quick Calculator**: www.ssa.gov/benefits/retirement/planner/AnypiaApplet.html
        - **Retirement Estimator**: www.ssa.gov/benefits/retirement/estimator.html
        - **Detailed Calculator**: www.ssa.gov/benefits/retirement/planner/anyPiaWepjs04.html
        
        **Publications**
        - **Retirement Benefits** (Publication No. 05-10035)
        - **Understanding the Benefits** (Publication No. 05-10024)
        - **Your Retirement Checklist** (Publication No. 05-10377)
        - **When to Start Receiving Benefits** (Publication No. 05-10147)
        - All available at www.ssa.gov/pubs
        
        #### Educational Resources
        
        **AARP Social Security Resource Center**
        - www.aarp.org/retirement/social-security
        - Claiming strategies
        - Benefit calculators
        - Educational articles
        
        **Financial Planning Association**
        - Find a CFP® professional
        - Social Security claiming strategies
        - Retirement income planning
        
        **Medicare.gov**
        - Coordinate Medicare enrollment
        - Understand Part A/B enrollment with Social Security
        - Plan for healthcare costs
        
        #### Important Forms
        
        - **SSA-1 (Application for Retirement Benefits)** - Online or paper
        - **SSA-521 (Request for Withdrawal)** - Within 12 months of claiming
        - **SSA-795 (Statement of Claimant)** - Correct earnings record
        - **W-4V (Voluntary Withholding Request)** - Tax withholding
        - **SSA-44 (Medicare Income-Related Monthly Adjustment Amount)** - IRMAA appeal
        
        #### State-Specific Information
        
        **State Taxation of Benefits**
        - Check your state's Department of Revenue website
        - Some states offer exemptions based on income
        - May affect retirement location decision
        
        **State Disability Programs**
        - Some states have additional disability benefits
        - May coordinate with Social Security Disability
        - Check your state's social services department
        """)

# ── Footer ────────────────────────────────────────────────────────────────────
auto_rerun_if_rebuilding()
