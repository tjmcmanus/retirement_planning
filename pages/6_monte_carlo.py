"""
pages/6_monte_carlo.py
======================
🎲 Monte Carlo Simulation — 5 sub-tabs:
  - 🎯 Run Simulation
  - ⚠️ Stress Tests
  - 🕐 Longevity Risk
  - 🗺️ Success Heatmap
  - 📊 Scenario Comparison
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.navbar import navbar
from components.shared import auto_rerun_if_rebuilding, init_page
from monte_carlo import (
    LONGEVITY_SCENARIOS,
    PORTFOLIO_PRESETS,
    STRESS_SCENARIOS,
    MonteCarloInputs,
    analyze_sequence_of_returns_risk,
    build_fan_chart_df,
    build_scenario_comparison_df,
    build_success_heatmap_df,
    generate_monte_carlo_report_csv,
    get_safe_withdrawal_rate,
    run_full_scenario_comparison,
    run_longevity_analysis,
    run_monte_carlo,
    run_stress_tests,
)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
(
    _networth,
    _portfolio_df,
    _portfolio_cache_ready,
    _stale_label,
    _curr_month,
    _curr_year,
    _eff_port_month,
    _eff_port_year,
) = init_page("🎲 Monte Carlo — Financial Planner", "🎲")

navbar("🎲 Monte Carlo")

# Load configuration for default values
from config import get_config_manager
_config_mgr = get_config_manager()

# Calculate default portfolio value from networth
try:
    _default_portfolio = 0
    if not _networth.empty:
        _latest_row = _networth.iloc[-1]
        _default_portfolio = int(
            float(_latest_row.get("cash", 0)) +
            float(_latest_row.get("taxable", 0)) +
            float(_latest_row.get("tax_deferred", 0)) +
            float(_latest_row.get("tax_free", 0))
        )
    # Fallback to a reasonable default if no data
    if _default_portfolio < 10_000:
        _default_portfolio = 1_500_000
except Exception:
    _default_portfolio = 1_500_000

# Get configuration defaults
_default_expenses = _config_mgr.get("financial_assumptions", "expected_annual_expenses", 50_000)
_default_person1_age = _config_mgr.calculate_age(
    _config_mgr.get("personal_info", "person1_birth_date", "1965-01-01")
)
_default_person1_retire_age = _config_mgr.get("personal_info", "person1_retirement_age", 62)
_default_person2_age = _config_mgr.calculate_age(
    _config_mgr.get("personal_info", "person2_birth_date", "1967-01-01")
)
_default_ss_age = _config_mgr.get("social_security", "person1_ssi_age", 70)
_default_ss_amount = _config_mgr.get("social_security", "person1_ssi_amount", 0)
_default_inflation = _config_mgr.get("financial_assumptions", "expense_inflation_rate", 3.0) / 100

# Use the younger person's retirement age if both are defined
_default_start_age = min(_default_person1_retire_age,
                         _config_mgr.get("personal_info", "person2_retirement_age", 62))

# Calculate a reasonable end age (use the older person's age + 30 years, capped at 95)
_default_end_age = min(95, max(_default_person1_age, _default_person2_age) + 30)

st.header("🎲 Monte Carlo Simulation")
st.markdown(
    "Run 10,000+ retirement simulations to estimate the probability your portfolio "
    "survives your lifetime under realistic market volatility."
)
st.markdown("---")

# ---------------------------------------------------------------------------
# Shared settings panel (inline, not sidebar — sidebar is for config)
# ---------------------------------------------------------------------------
with st.expander("⚙️ Simulation Settings", expanded=False):
    _s1, _s2, _s3, _s4 = st.columns(4)
    with _s1:
        _mc_portfolio = st.number_input(
            "Starting Portfolio ($)", min_value=10_000, value=_default_portfolio,
            step=50_000, key="mc_portfolio",
            help="Current total portfolio value from your latest data"
        )
        _mc_withdrawal = st.number_input(
            "Annual Withdrawal ($)", min_value=1_000, value=_default_expenses,
            step=5_000, key="mc_withdrawal",
            help="Expected annual expenses from configuration"
        )
    with _s2:
        _mc_start_age = st.number_input(
            "Retirement Age", min_value=40, max_value=80, value=_default_start_age, key="mc_start_age",
            help="Planned retirement age from configuration"
        )
        _mc_end_age = st.number_input(
            "Plan To Age", min_value=70, max_value=110, value=_default_end_age, key="mc_end_age",
            help="Planning horizon (typically 90-95)"
        )
    with _s3:
        _mc_ss = st.number_input(
            "Annual Social Security ($)", min_value=0, value=_default_ss_amount,
            step=1_000, key="mc_ss",
            help="Expected annual Social Security benefits from configuration"
        )
        _mc_ss_age = st.number_input(
            "SS Start Age", min_value=62, max_value=70, value=_default_ss_age, key="mc_ss_age",
            help="Age to start Social Security from configuration"
        )
    with _s4:
        _mc_inflation_pct = st.slider(
            "Inflation Rate", min_value=1.0, max_value=10.0,
            value=_default_inflation * 100, step=0.1, format="%.1f%%", key="mc_inflation_pct",
            help="Expected inflation rate from configuration"
        )
        _mc_inflation = _mc_inflation_pct / 100
        st.session_state["mc_inflation"] = _mc_inflation
        _mc_allocation = st.selectbox(
            "Portfolio Allocation", list(PORTFOLIO_PRESETS.keys()),
            index=1, key="mc_allocation",
            help="Asset allocation mix (stocks/bonds)"
        )
        _mc_n_sims = st.select_slider(
            "Simulations", options=[1_000, 2_000, 5_000, 10_000, 20_000],
            value=10_000, key="mc_n_sims",
            help="Number of Monte Carlo simulations to run"
        )

st.markdown("---")


def _build_mc_inputs() -> MonteCarloInputs:
    return MonteCarloInputs(
        initial_portfolio=float(st.session_state.get("mc_portfolio", 1_500_000)),
        annual_withdrawal=float(st.session_state.get("mc_withdrawal", 80_000)),
        start_age=int(st.session_state.get("mc_start_age", 62)),
        end_age=int(st.session_state.get("mc_end_age", 90)),
        portfolio_allocation=PORTFOLIO_PRESETS[
            st.session_state.get("mc_allocation", "Moderate (70/30)")
        ],
        inflation_rate=float(st.session_state.get("mc_inflation", 0.029)),
        withdrawal_growth_rate=float(st.session_state.get("mc_inflation", 0.029)),
        social_security_annual=float(st.session_state.get("mc_ss", 40_000)),
        ss_start_age=int(st.session_state.get("mc_ss_age", 70)),
        n_simulations=int(st.session_state.get("mc_n_sims", 10_000)),
        random_seed=42,
    )


# ---------------------------------------------------------------------------
# Sub-tabs
# ---------------------------------------------------------------------------
mc_sim_tab, mc_stress_tab, mc_longevity_tab, mc_heatmap_tab, mc_compare_tab = st.tabs([
    "🎯 Run Simulation",
    "⚠️ Stress Tests",
    "🕐 Longevity Risk",
    "🗺️ Success Heatmap",
    "📊 Scenario Comparison",
])

# -----------------------------------------------------------------------
# SUB-TAB 1: Run Simulation
# -----------------------------------------------------------------------
with mc_sim_tab:
    st.subheader("🎯 Monte Carlo Simulation")
    st.markdown("Configure inputs above, then click **Run**.")

    _mc_c1, _mc_c2, _mc_c3, _mc_c4 = st.columns(4)
    _mc_c1.metric("Starting Portfolio", f"${st.session_state.get('mc_portfolio', 1_500_000):,.0f}")
    _mc_c2.metric("Annual Withdrawal", f"${st.session_state.get('mc_withdrawal', 80_000):,.0f}")
    _mc_c3.metric("Retirement Age", str(st.session_state.get("mc_start_age", 62)))
    _mc_c4.metric("Plan To Age", str(st.session_state.get("mc_end_age", 90)))

    if st.button("▶️ Run Monte Carlo Simulation", key="mc_run", type="primary"):
        with st.spinner(f"Running {st.session_state.get('mc_n_sims', 10_000):,} simulations…"):
            try:
                _mc_inputs = _build_mc_inputs()
                _mc_result = run_monte_carlo(_mc_inputs)
                st.session_state["_mc_result"] = _mc_result
                st.session_state["_mc_inputs"] = _mc_inputs
                
                # Save Monte Carlo results to file for report generation
                import json
                from pathlib import Path
                from datetime import datetime
                import numpy as np
                
                mc_data = {
                    'success_rate': _mc_result.success_probability,
                    'median_final_portfolio': _mc_result.median_final_portfolio,
                    'p10_final_portfolio': _mc_result.p10_final_portfolio,
                    'p90_final_portfolio': _mc_result.p90_final_portfolio,
                    'years_to_depletion_p10': _mc_result.years_to_depletion_p10,
                    'timestamp': datetime.now().isoformat(),
                    'n_simulations': st.session_state.get('mc_n_sims', 10_000),
                    'available': True,
                    'annual_withdrawal': float(_mc_inputs.annual_withdrawal),
                    'initial_portfolio': float(_mc_inputs.initial_portfolio),
                    'start_age': int(_mc_inputs.start_age),
                    'end_age': int(_mc_inputs.end_age),
                    'social_security_annual': float(_mc_inputs.social_security_annual),
                    'ss_start_age': int(_mc_inputs.ss_start_age) if _mc_inputs.ss_start_age else None,
                    'filing_status': st.session_state.get('mc_filing_status', 'Married Filing Jointly')
                }
                
                # Calculate safe withdrawal rates at multiple confidence levels
                portfolio_value = float(st.session_state.get("mc_portfolio", 1_500_000))
                try:
                    swr_90 = get_safe_withdrawal_rate(_mc_inputs, target_success=0.90)
                    swr_75 = get_safe_withdrawal_rate(_mc_inputs, target_success=0.75)
                    swr_65 = get_safe_withdrawal_rate(_mc_inputs, target_success=0.65)
                    
                    mc_data['safe_withdrawal_rates'] = {
                        '90_percent_confidence': {
                            'annual_amount': float(swr_90),
                            'percentage': float(swr_90 / portfolio_value * 100),
                            'description': 'Conservative - 90% confidence of success'
                        },
                        '75_percent_confidence': {
                            'annual_amount': float(swr_75),
                            'percentage': float(swr_75 / portfolio_value * 100),
                            'description': 'Moderate - 75% confidence of success'
                        },
                        '65_percent_confidence': {
                            'annual_amount': float(swr_65),
                            'percentage': float(swr_65 / portfolio_value * 100),
                            'description': 'Aggressive - 65% confidence of success'
                        },
                        'portfolio_value': float(portfolio_value),
                        'inflation_rate': float(_mc_inputs.inflation_rate)
                    }
                except Exception as swr_err:
                    # Safe withdrawal rate calculation failed, continue without it
                    pass
                
                # Add scenario paths if available
                if _mc_result.portfolio_paths is not None:
                    paths = _mc_result.portfolio_paths
                    # Calculate percentile paths across all simulations
                    p10_path = np.percentile(paths, 10, axis=0).tolist()
                    p25_path = np.percentile(paths, 25, axis=0).tolist()
                    p50_path = np.percentile(paths, 50, axis=0).tolist()
                    p75_path = np.percentile(paths, 75, axis=0).tolist()
                    p90_path = np.percentile(paths, 90, axis=0).tolist()
                    
                    mc_data['scenario_paths'] = {
                        'p10': p10_path,
                        'p25': p25_path,
                        'p50': p50_path,
                        'p75': p75_path,
                        'p90': p90_path,
                        'ages': list(range(_mc_inputs.start_age, _mc_inputs.end_age + 1))
                    }
                
                Path("data").mkdir(exist_ok=True)
                with open("data/monte_carlo_results.json", 'w') as f:
                    json.dump(mc_data, f, indent=2)
                
            except Exception as _mc_err:
                st.error(f"Simulation error: {_mc_err}")
                st.session_state.pop("_mc_result", None)

    if "_mc_result" in st.session_state:
        _r = st.session_state["_mc_result"]

        _sp = _r.success_probability
        _sp_color = "🟢" if _sp >= 0.90 else ("🟡" if _sp >= 0.75 else "🔴")
        st.markdown(f"## {_sp_color} Success Probability: **{_sp:.1%}**")
        st.caption(
            "Probability the portfolio survives to the plan end age across all simulations. "
            "Target: ≥ 90% for high confidence."
        )

        _rm1, _rm2, _rm3, _rm4 = st.columns(4)
        _rm1.metric("Median Final Portfolio", f"${_r.median_final_portfolio:,.0f}")
        _rm2.metric("10th Pct Final Portfolio", f"${_r.p10_final_portfolio:,.0f}")
        _rm3.metric("90th Pct Final Portfolio", f"${_r.p90_final_portfolio:,.0f}")
        _rm4.metric(
            "P10 Depletion Age",
            str(_r.years_to_depletion_p10) if _r.years_to_depletion_p10 else "Never ✅",
        )

        with st.spinner("Calculating safe withdrawal rate…"):
            try:
                _swr = get_safe_withdrawal_rate(st.session_state["_mc_inputs"])
                _swr_pct = _swr / float(st.session_state.get("mc_portfolio", 1_500_000)) * 100
                st.info(
                    f"💡 **Safe Withdrawal Rate at 90% confidence:** "
                    f"${_swr:,.0f}/year ({_swr_pct:.2f}% of portfolio)"
                )
            except Exception:
                pass

        st.markdown("#### 📈 Portfolio Outcome Fan Chart")
        st.caption(
            "Shaded bands show the range of outcomes across all simulations. "
            "The dark line is the median (50th percentile)."
        )
        _fan_df = build_fan_chart_df(_r)
        if not _fan_df.empty:
            _fan_fig = go.Figure()
            for _lo, _hi, _color in [
                (5, 95, "rgba(99,110,250,0.08)"),
                (10, 90, "rgba(99,110,250,0.12)"),
                (25, 75, "rgba(99,110,250,0.20)"),
            ]:
                _fan_fig.add_trace(go.Scatter(
                    x=list(_fan_df["age"]) + list(_fan_df["age"])[::-1],
                    y=list(_fan_df[f"p{_hi}"]) + list(_fan_df[f"p{_lo}"])[::-1],
                    fill="toself", fillcolor=_color,
                    line=dict(color="rgba(0,0,0,0)"),
                    name=f"P{_lo}–P{_hi}", showlegend=True,
                ))
            _fan_fig.add_trace(go.Scatter(
                x=_fan_df["age"], y=_fan_df["p50"],
                mode="lines", name="Median (P50)",
                line=dict(color="rgb(99,110,250)", width=2.5),
            ))
            _fan_fig.add_trace(go.Scatter(
                x=_fan_df["age"], y=_fan_df["p10"],
                mode="lines", name="P10 (Pessimistic)",
                line=dict(color="rgb(239,85,59)", width=1.5, dash="dash"),
            ))
            _fan_fig.update_layout(
                title="Portfolio Value Distribution by Age",
                xaxis_title="Age", yaxis_title="Portfolio Value ($)",
                yaxis_tickformat="$,.0f",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                hovermode="x unified",
            )
            st.plotly_chart(_fan_fig, use_container_width=True)

        st.markdown("#### ✅ Probability of Success by Age")
        _sr_fig = go.Figure()
        _sr_fig.add_trace(go.Scatter(
            x=_fan_df["age"], y=_fan_df["success_rate"] * 100,
            mode="lines+markers", name="Success Rate",
            line=dict(color="rgb(0,204,150)", width=2),
            fill="tozeroy", fillcolor="rgba(0,204,150,0.15)",
        ))
        _sr_fig.add_hline(y=90, line_dash="dash", line_color="orange", annotation_text="90% Target")
        _sr_fig.update_layout(
            title="Probability of Portfolio Survival by Age",
            xaxis_title="Age", yaxis_title="Success Rate (%)", yaxis_range=[0, 105],
        )
        st.plotly_chart(_sr_fig, use_container_width=True)

        st.markdown("#### 🔀 Sequence-of-Returns Risk Analysis")
        with st.spinner("Analyzing sequence risk…"):
            try:
                _sor = analyze_sequence_of_returns_risk(st.session_state["_mc_inputs"])
                _sor_c1, _sor_c2, _sor_c3 = st.columns(3)
                _sor_c1.metric(
                    "Worst-Sequence Success Rate",
                    f"{_sor.get('worst_paths_success_rate', 0):.1%}",
                    delta=f"{(_sor.get('worst_paths_success_rate', 0) - _sor.get('overall_success_probability', 0)):.1%}",
                    delta_color="inverse",
                )
                _sor_c2.metric("Avg First-5yr Return (Worst)", f"{_sor.get('avg_first5yr_return_worst', 0):.1%}")
                _sor_c3.metric("Depletion Age (Worst Median)", str(_sor.get("depletion_age_worst_median", "N/A")))
                st.caption(
                    "Sequence risk: retiring into a bear market dramatically reduces success. "
                    "The worst 1% of sequences are shown above."
                )
            except Exception as _sor_err:
                st.caption(f"Sequence analysis unavailable: {_sor_err}")

        with st.expander("ℹ️ Simulation Notes", expanded=False):
            for _note in _r.notes:
                st.caption(_note)

        st.markdown("---")
        _csv_bytes = generate_monte_carlo_report_csv(_r)
        st.download_button(
            label="📥 Download Monte Carlo Report (CSV)",
            data=_csv_bytes,
            file_name=f"monte_carlo_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key="mc_download",
        )

# -----------------------------------------------------------------------
# SUB-TAB 2: Stress Tests
# -----------------------------------------------------------------------
with mc_stress_tab:
    st.subheader("⚠️ Stress Test Scenarios")
    st.markdown("Test your portfolio against historical market crises and adverse scenarios.")

    _st_scenarios = st.multiselect(
        "Select Stress Scenarios",
        list(STRESS_SCENARIOS.keys()),
        default=list(STRESS_SCENARIOS.keys()),
        key="mc_stress_scenarios",
    )

    if st.button("▶️ Run Stress Tests", key="mc_stress_run", type="primary"):
        with st.spinner("Running stress scenarios…"):
            try:
                _st_inputs = _build_mc_inputs()
                _st_results = run_stress_tests(_st_inputs, _st_scenarios)
                st.session_state["_mc_stress_results"] = _st_results
                st.session_state["_mc_stress_inputs"] = _st_inputs
                
                # Save stress test results to JSON for reporting
                import json
                from pathlib import Path
                
                _stress_data = []
                for _s in _st_results:
                    _stress_data.append({
                        "scenario_name": _s.scenario_name,
                        "description": _s.description,
                        "success_probability": float(_s.success_probability),
                        "median_final_portfolio": float(_s.median_final_portfolio),
                        "p10_final_portfolio": float(_s.p10_final_portfolio),
                        "years_to_depletion_median": _s.years_to_depletion_median,
                        "portfolio_path_median": [float(v) for v in _s.portfolio_path_median] if _s.portfolio_path_median else [],
                        "notes": _s.notes,
                    })
                
                # Load existing Monte Carlo results if they exist
                _mc_file = Path("data/monte_carlo_results.json")
                if _mc_file.exists():
                    with open(_mc_file, "r") as f:
                        _existing_data = json.load(f)
                else:
                    _existing_data = {}
                
                # Add stress test results
                _existing_data["stress_tests"] = _stress_data
                _existing_data["stress_test_timestamp"] = pd.Timestamp.now().isoformat()
                
                # Save back to file
                _mc_file.parent.mkdir(parents=True, exist_ok=True)
                with open(_mc_file, "w") as f:
                    json.dump(_existing_data, f, indent=2)
                
            except Exception as _st_err:
                st.error(f"Stress test error: {_st_err}")

    if "_mc_stress_results" in st.session_state:
        _st_res = st.session_state["_mc_stress_results"]

        st.markdown("#### Stress Test Summary")
        _st_rows = []
        for _s in _st_res:
            _sp_icon = "🟢" if _s.success_probability >= 0.90 else ("🟡" if _s.success_probability >= 0.75 else "🔴")
            _st_rows.append({
                "Scenario": _s.scenario_name,
                "Description": _s.description,
                "Success": f"{_sp_icon} {_s.success_probability:.1%}",
                "Median Final": f"${_s.median_final_portfolio:,.0f}",
                "P10 Final": f"${_s.p10_final_portfolio:,.0f}",
                "Depletion Age": str(_s.years_to_depletion_median) if _s.years_to_depletion_median else "Never",
            })
        st.dataframe(pd.DataFrame(_st_rows), use_container_width=True, hide_index=True)

        st.markdown("#### Median Portfolio Path by Scenario")
        _path_fig = go.Figure()
        _ages = list(range(
            int(st.session_state.get("mc_start_age", 62)),
            int(st.session_state.get("mc_end_age", 90)),
        ))
        _colors = px.colors.qualitative.Plotly
        for _i, _s in enumerate(_st_res):
            if _s.portfolio_path_median:
                _path_fig.add_trace(go.Scatter(
                    x=_ages[:len(_s.portfolio_path_median)],
                    y=_s.portfolio_path_median,
                    mode="lines", name=_s.scenario_name,
                    line=dict(color=_colors[_i % len(_colors)], width=2),
                ))
        _path_fig.update_layout(
            title="Median Portfolio Path — Stress Scenarios",
            xaxis_title="Age", yaxis_title="Portfolio Value ($)",
            yaxis_tickformat="$,.0f",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(_path_fig, use_container_width=True)

        _st_csv = generate_monte_carlo_report_csv(
            st.session_state.get("_mc_result", run_monte_carlo(_build_mc_inputs())),
            stress_results=_st_res,
        )
        st.download_button(
            label="📥 Download Stress Test Report (CSV)",
            data=_st_csv,
            file_name=f"stress_test_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key="mc_stress_download",
        )

# -----------------------------------------------------------------------
# SUB-TAB 3: Longevity Risk
# -----------------------------------------------------------------------
with mc_longevity_tab:
    st.subheader("🕐 Longevity Risk Analysis")
    st.markdown(
        "How does your portfolio hold up if you live longer than expected? "
        "Model outcomes to age 85, 90, 95, 100, and 105."
    )

    _lon_ages_selected = st.multiselect(
        "Longevity Scenarios",
        list(LONGEVITY_SCENARIOS.keys()),
        default=list(LONGEVITY_SCENARIOS.keys()),
        key="mc_longevity_scenarios",
    )

    if st.button("▶️ Run Longevity Analysis", key="mc_lon_run", type="primary"):
        with st.spinner("Running longevity scenarios…"):
            try:
                _lon_inputs = _build_mc_inputs()
                _lon_ages = {k: v for k, v in LONGEVITY_SCENARIOS.items() if k in _lon_ages_selected}
                _lon_results = run_longevity_analysis(_lon_inputs, _lon_ages)
                st.session_state["_mc_lon_results"] = _lon_results
            except Exception as _lon_err:
                st.error(f"Longevity analysis error: {_lon_err}")

    if "_mc_lon_results" in st.session_state:
        _lon_res = st.session_state["_mc_lon_results"]

        st.markdown("#### Longevity Scenario Summary")
        _lon_rows = []
        for _label, _mc in _lon_res.items():
            _sp_icon = "🟢" if _mc.success_probability >= 0.90 else ("🟡" if _mc.success_probability >= 0.75 else "🔴")
            _lon_rows.append({
                "Scenario": _label,
                "Plan To Age": _mc.inputs.end_age,
                "Success": f"{_sp_icon} {_mc.success_probability:.1%}",
                "Median Final": f"${_mc.median_final_portfolio:,.0f}",
                "P10 Final": f"${_mc.p10_final_portfolio:,.0f}",
                "P10 Depletion Age": str(_mc.years_to_depletion_p10) if _mc.years_to_depletion_p10 else "Never ✅",
            })
        st.dataframe(pd.DataFrame(_lon_rows), use_container_width=True, hide_index=True)

        _lon_fig = go.Figure()
        _lon_labels = list(_lon_res.keys())
        _lon_success = [_lon_res[k].success_probability * 100 for k in _lon_labels]
        _lon_colors = [
            "rgb(0,204,150)" if s >= 90 else ("rgb(255,165,0)" if s >= 75 else "rgb(239,85,59)")
            for s in _lon_success
        ]
        _lon_fig.add_trace(go.Bar(
            x=_lon_labels, y=_lon_success,
            marker_color=_lon_colors,
            text=[f"{s:.1f}%" for s in _lon_success],
            textposition="outside",
        ))
        _lon_fig.add_hline(y=90, line_dash="dash", line_color="orange", annotation_text="90% Target")
        _lon_fig.update_layout(
            title="Success Probability by Longevity Scenario",
            xaxis_title="Longevity Scenario",
            yaxis_title="Success Probability (%)",
            yaxis_range=[0, 110],
        )
        st.plotly_chart(_lon_fig, use_container_width=True)

        st.markdown("#### Median Portfolio Path by Longevity")
        _lon_path_fig = go.Figure()
        _lon_colors_list = px.colors.qualitative.Plotly
        for _i, (_label, _mc) in enumerate(_lon_res.items()):
            _fan = build_fan_chart_df(_mc)
            if not _fan.empty:
                _lon_path_fig.add_trace(go.Scatter(
                    x=_fan["age"], y=_fan["p50"],
                    mode="lines", name=_label,
                    line=dict(color=_lon_colors_list[_i % len(_lon_colors_list)], width=2),
                ))
        _lon_path_fig.update_layout(
            title="Median Portfolio Path — Longevity Scenarios",
            xaxis_title="Age", yaxis_title="Portfolio Value ($)",
            yaxis_tickformat="$,.0f",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(_lon_path_fig, use_container_width=True)

        _lon_csv = generate_monte_carlo_report_csv(
            st.session_state.get("_mc_result", run_monte_carlo(_build_mc_inputs())),
            longevity_results=_lon_res,
        )
        st.download_button(
            label="📥 Download Longevity Report (CSV)",
            data=_lon_csv,
            file_name=f"longevity_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key="mc_lon_download",
        )

# -----------------------------------------------------------------------
# SUB-TAB 4: Success Heatmap
# -----------------------------------------------------------------------
with mc_heatmap_tab:
    st.subheader("🗺️ Success Probability Heatmap")
    st.markdown(
        "See how success probability changes across different withdrawal amounts "
        "and portfolio allocations. Green = high confidence, Red = at risk."
    )

    _hm_col1, _hm_col2 = st.columns(2)
    with _hm_col1:
        _hm_base_withdrawal = st.number_input(
            "Base Annual Withdrawal ($)", min_value=10_000, value=80_000,
            step=5_000, key="hm_withdrawal",
        )
    with _hm_col2:
        _hm_n_sims = st.select_slider(
            "Simulations per Cell", options=[500, 1_000, 2_000],
            value=1_000, key="hm_n_sims",
            help="More simulations = more accurate but slower.",
        )

    if st.button("▶️ Build Heatmap", key="mc_heatmap_run", type="primary"):
        with st.spinner("Building heatmap (this may take 30–60 seconds)…"):
            try:
                _hm_inputs = MonteCarloInputs(
                    initial_portfolio=float(st.session_state.get("mc_portfolio", 1_500_000)),
                    annual_withdrawal=float(_hm_base_withdrawal),
                    start_age=int(st.session_state.get("mc_start_age", 62)),
                    end_age=int(st.session_state.get("mc_end_age", 90)),
                    portfolio_allocation=PORTFOLIO_PRESETS["Moderate (70/30)"],
                    inflation_rate=float(st.session_state.get("mc_inflation", 0.029)),
                    withdrawal_growth_rate=float(st.session_state.get("mc_inflation", 0.029)),
                    social_security_annual=float(st.session_state.get("mc_ss", 40_000)),
                    ss_start_age=int(st.session_state.get("mc_ss_age", 70)),
                    n_simulations=int(_hm_n_sims),
                    random_seed=42,
                )
                _hm_df = build_success_heatmap_df(_hm_inputs)
                st.session_state["_mc_heatmap_df"] = _hm_df
            except Exception as _hm_err:
                st.error(f"Heatmap error: {_hm_err}")

    if "_mc_heatmap_df" in st.session_state:
        _hm_df = st.session_state["_mc_heatmap_df"]
        st.markdown("#### Success Probability (%) by Withdrawal × Allocation")
        st.caption("Values are success probability %. Green ≥ 90%, Yellow 75–90%, Red < 75%.")

        _hm_display = _hm_df.set_index("Annual Withdrawal")

        def _color_success(val: object) -> str:
            try:
                v = float(val)  # type: ignore[arg-type]
                if v >= 90:
                    return "background-color: rgba(0,204,150,0.4)"
                elif v >= 75:
                    return "background-color: rgba(255,165,0,0.4)"
                else:
                    return "background-color: rgba(239,85,59,0.4)"
            except (ValueError, TypeError):
                return ""

        st.dataframe(
            _hm_display.style.applymap(_color_success),
            use_container_width=True,
        )

        _hm_fig = go.Figure(data=go.Heatmap(
            z=_hm_display.values,
            x=list(_hm_display.columns),
            y=list(_hm_display.index),
            colorscale=[
                [0.0, "rgb(239,85,59)"],
                [0.75, "rgb(255,165,0)"],
                [0.90, "rgb(0,204,150)"],
                [1.0, "rgb(0,150,100)"],
            ],
            zmin=0, zmax=100,
            text=_hm_display.values,
            texttemplate="%{text:.0f}%",
            colorbar=dict(title="Success %"),
        ))
        _hm_fig.update_layout(
            title="Success Probability Heatmap",
            xaxis_title="Portfolio Allocation",
            yaxis_title="Annual Withdrawal",
        )
        st.plotly_chart(_hm_fig, use_container_width=True)

# -----------------------------------------------------------------------
# SUB-TAB 5: Scenario Comparison
# -----------------------------------------------------------------------
with mc_compare_tab:
    st.subheader("📊 Full Scenario Comparison")
    st.markdown(
        "Run baseline + all stress tests + all longevity scenarios in one shot "
        "and compare results side-by-side."
    )

    _cmp_stress = st.multiselect(
        "Stress Scenarios to Include",
        list(STRESS_SCENARIOS.keys()),
        default=list(STRESS_SCENARIOS.keys())[:3],
        key="mc_cmp_stress",
    )
    _cmp_longevity = st.multiselect(
        "Longevity Scenarios to Include",
        list(LONGEVITY_SCENARIOS.keys()),
        default=["Average (age 85)", "Long-Lived (age 95)", "Exceptional (age 105)"],
        key="mc_cmp_longevity",
    )

    if st.button("▶️ Run Full Comparison", key="mc_compare_run", type="primary"):
        with st.spinner("Running full scenario comparison…"):
            try:
                _cmp_inputs = _build_mc_inputs()
                _cmp_lon_ages = {k: v for k, v in LONGEVITY_SCENARIOS.items() if k in _cmp_longevity}
                _cmp_result = run_full_scenario_comparison(
                    _cmp_inputs,
                    stress_scenarios=_cmp_stress,
                    longevity_ages=_cmp_lon_ages,
                )
                st.session_state["_mc_cmp_result"] = _cmp_result
            except Exception as _cmp_err:
                st.error(f"Comparison error: {_cmp_err}")

    if "_mc_cmp_result" in st.session_state:
        _cmp = st.session_state["_mc_cmp_result"]
        _cmp_df = build_scenario_comparison_df(_cmp)

        st.markdown("#### All Scenarios — Side-by-Side")
        st.dataframe(_cmp_df, use_container_width=True, hide_index=True)

        _cmp_fig = go.Figure()
        _cmp_labels = _cmp_df["Scenario"].tolist()
        _cmp_success_vals = []
        for _row in _cmp_df["Success Probability"]:
            try:
                _cmp_success_vals.append(float(str(_row).replace("%", "").strip()))
            except (ValueError, AttributeError):
                _cmp_success_vals.append(0.0)

        _cmp_bar_colors = [
            "rgb(0,204,150)" if v >= 90 else ("rgb(255,165,0)" if v >= 75 else "rgb(239,85,59)")
            for v in _cmp_success_vals
        ]
        _cmp_fig.add_trace(go.Bar(
            x=_cmp_labels, y=_cmp_success_vals,
            marker_color=_cmp_bar_colors,
            text=[f"{v:.1f}%" for v in _cmp_success_vals],
            textposition="outside",
        ))
        _cmp_fig.add_hline(y=90, line_dash="dash", line_color="orange", annotation_text="90% Target")
        _cmp_fig.update_layout(
            title="Success Probability — All Scenarios",
            xaxis_title="Scenario", yaxis_title="Success Probability (%)",
            yaxis_range=[0, 115], xaxis_tickangle=-30,
        )
        st.plotly_chart(_cmp_fig, use_container_width=True)

        _cmp_csv = generate_monte_carlo_report_csv(
            _cmp.baseline,
            stress_results=_cmp.stress_tests,
            longevity_results=_cmp.longevity_results,
        )
        st.download_button(
            label="📥 Download Full Comparison Report (CSV)",
            data=_cmp_csv,
            file_name=f"mc_full_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key="mc_cmp_download",
        )

# ---------------------------------------------------------------------------
auto_rerun_if_rebuilding()

# Made with Bob
