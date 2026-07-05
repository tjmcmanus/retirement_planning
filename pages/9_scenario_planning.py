"""
pages/9_scenario_planning.py
=============================
🎯 Scenario Planning & What-If Analysis

Interactive scenario comparison and life event modeling for retirement planning.
Compare up to 4 scenarios side-by-side with real-time parameter adjustments.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json
from pathlib import Path

from components.navbar import navbar
from components.shared import init_page_minimal
from scenario_manager import (
    Scenario,
    ScenarioManager,
    LifeEvent,
    create_baseline_from_config,
)
from life_event_modeler import (
    LifeEventTemplates,
    detect_event_conflicts,
    calculate_event_timeline,
    get_template_list,
)
from scenario_integration import (
    run_scenario_monte_carlo,
    calculate_scenario_taxes,
    compare_scenario_taxes,
    generate_scenario_report,
)
from config import get_config_manager
from monte_carlo import PORTFOLIO_PRESETS

# ============================================================================
# Page Setup
# ============================================================================

init_page_minimal("🎯 Scenario Planning — Financial Planner", "🎯")

navbar("🎯 Scenario Planning")

# Initialize managers
_scenario_mgr = ScenarioManager()
_config_mgr = get_config_manager()

# ============================================================================
# Session State Initialization
# ============================================================================

if "selected_scenarios" not in st.session_state:
    st.session_state.selected_scenarios = []

if "scenario_results" not in st.session_state:
    st.session_state.scenario_results = {}

if "editing_scenario" not in st.session_state:
    st.session_state.editing_scenario = None

if "show_event_editor" not in st.session_state:
    st.session_state.show_event_editor = False

# ============================================================================
# Helper Functions
# ============================================================================

def load_scenario_list() -> list[dict]:
    """Load list of available scenarios."""
    scenarios = _scenario_mgr.list_scenarios()
    if not scenarios:
        # Create baseline if no scenarios exist
        baseline = create_baseline_from_config(_config_mgr)
        _scenario_mgr.create_scenario(baseline)
        scenarios = _scenario_mgr.list_scenarios()
    return scenarios


def run_scenario_analysis(scenario: Scenario) -> dict:
    """Run Monte Carlo analysis for a scenario."""
    try:
        # Use integration module to run Monte Carlo with life events
        result = run_scenario_monte_carlo(
            scenario,
            n_simulations=5_000,  # Faster for UI
            include_life_events=True,
        )
        
        return {
            "success": True,
            "success_probability": result.success_probability,
            "median_final": result.median_final_portfolio,
            "p10_final": result.p10_final_portfolio,
            "p90_final": result.p90_final_portfolio,
            "depletion_age": result.years_to_depletion_p10,
            "result": result,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def format_currency(value: float) -> str:
    """Format value as currency."""
    return f"${value:,.0f}"


def format_percentage(value: float) -> str:
    """Format value as percentage."""
    return f"{value:.1%}"


# ============================================================================
# Header
# ============================================================================

st.header("🎯 Scenario Planning & What-If Analysis")
st.markdown(
    "Compare multiple retirement scenarios side-by-side. Model life events, "
    "adjust parameters, and see how different choices affect your retirement success."
)
st.markdown("---")

# ============================================================================
# Scenario Management Bar
# ============================================================================

st.subheader("📋 Scenario Management")

_mgmt_col1, _mgmt_col2, _mgmt_col3, _mgmt_col4 = st.columns([3, 1, 1, 1])

with _mgmt_col1:
    # Load available scenarios
    _available_scenarios = load_scenario_list()
    _scenario_options = {s["name"]: s["id"] for s in _available_scenarios}
    
    # Multi-select for scenarios (max 4)
    _selected_names = st.multiselect(
        "Select Scenarios to Compare (max 4)",
        options=list(_scenario_options.keys()),
        default=list(_scenario_options.keys())[:min(2, len(_scenario_options))],
        max_selections=4,
        help="Choose up to 4 scenarios to compare side-by-side"
    )
    
    # Update session state
    st.session_state.selected_scenarios = [
        _scenario_options[name] for name in _selected_names
    ]

with _mgmt_col2:
    if st.button("➕ New Scenario", use_container_width=True):
        st.session_state.editing_scenario = "new"
        st.rerun()

with _mgmt_col3:
    if st.button("📋 Clone Selected", use_container_width=True, 
                 disabled=len(st.session_state.selected_scenarios) != 1):
        if len(st.session_state.selected_scenarios) == 1:
            scenario = _scenario_mgr.get_scenario(st.session_state.selected_scenarios[0])
            if scenario:
                cloned = scenario.clone()
                _scenario_mgr.create_scenario(cloned)
                st.success(f"Cloned: {cloned.name}")
                st.rerun()

with _mgmt_col4:
    if st.button("🗑️ Delete", use_container_width=True,
                 disabled=len(st.session_state.selected_scenarios) != 1):
        if len(st.session_state.selected_scenarios) == 1:
            scenario_id = st.session_state.selected_scenarios[0]
            scenario = _scenario_mgr.get_scenario(scenario_id)
            if scenario and not scenario.is_baseline:
                _scenario_mgr.delete_scenario(scenario_id)
                st.session_state.selected_scenarios = []
                st.success("Scenario deleted")
                st.rerun()
            elif scenario and scenario.is_baseline:
                st.error("Cannot delete baseline scenario")

st.markdown("---")

# ============================================================================
# Scenario Comparison View
# ============================================================================

if not st.session_state.selected_scenarios:
    st.info("👆 Select at least one scenario above to begin comparison")
    st.stop()

# Load selected scenarios
_scenarios = []
for scenario_id in st.session_state.selected_scenarios:
    scenario = _scenario_mgr.get_scenario(scenario_id)
    if scenario:
        _scenarios.append(scenario)

if not _scenarios:
    st.error("No valid scenarios selected")
    st.stop()

# ============================================================================
# Quick Metrics Comparison
# ============================================================================

st.subheader("📊 Quick Comparison")

_metric_cols = st.columns(len(_scenarios))

for idx, scenario in enumerate(_scenarios):
    with _metric_cols[idx]:
        st.markdown(f"**{scenario.name}**")
        
        # Run analysis if not cached
        if scenario.id not in st.session_state.scenario_results:
            with st.spinner(f"Analyzing {scenario.name}..."):
                st.session_state.scenario_results[scenario.id] = run_scenario_analysis(scenario)
        
        result = st.session_state.scenario_results[scenario.id]
        
        if result.get("success"):
            success_rate = result["success_probability"]
            color = "🟢" if success_rate >= 0.90 else ("🟡" if success_rate >= 0.75 else "🔴")
            
            st.metric(
                "Success Rate",
                f"{color} {success_rate:.1%}",
                help="Probability portfolio survives to plan end age"
            )
            st.metric(
                "Final Portfolio (Median)",
                format_currency(result["median_final"]),
                help="Median portfolio value at end age"
            )
            st.metric(
                "Retirement Age",
                scenario.retirement_age,
                help="Age at retirement"
            )
            st.metric(
                "Annual Expenses",
                format_currency(scenario.annual_expenses),
                help="Expected annual expenses"
            )
        else:
            st.error(f"Analysis failed: {result.get('error', 'Unknown error')}")

st.markdown("---")

# ============================================================================
# Detailed Comparison Tabs
# ============================================================================

_tab1, _tab2, _tab3, _tab4, _tab5 = st.tabs([
    "📈 Portfolio Trajectories",
    "💰 Cash Flow Analysis",
    "📅 Life Events Timeline",
    "⚙️ Parameter Comparison",
    "✏️ Edit Scenarios"
])

# ----------------------------------------------------------------------------
# TAB 1: Portfolio Trajectories
# ----------------------------------------------------------------------------

with _tab1:
    st.subheader("📈 Portfolio Value Projections")
    st.caption("Compare how portfolio values evolve over time across scenarios")
    
    # Create portfolio trajectory chart
    _traj_fig = go.Figure()
    _colors = px.colors.qualitative.Plotly
    
    for idx, scenario in enumerate(_scenarios):
        result = st.session_state.scenario_results.get(scenario.id, {})
        
        if result.get("success") and result.get("result"):
            mc_result = result["result"]
            
            # Get median path
            if hasattr(mc_result, 'portfolio_paths') and mc_result.portfolio_paths is not None:
                import numpy as np
                median_path = np.median(mc_result.portfolio_paths, axis=0)
                ages = list(range(scenario.retirement_age, scenario.plan_to_age + 1))
                
                _traj_fig.add_trace(go.Scatter(
                    x=ages[:len(median_path)],
                    y=median_path,
                    mode='lines',
                    name=scenario.name,
                    line=dict(color=_colors[idx % len(_colors)], width=3),
                    hovertemplate='<b>%{fullData.name}</b><br>Age: %{x}<br>Portfolio: $%{y:,.0f}<extra></extra>'
                ))
    
    _traj_fig.update_layout(
        title="Portfolio Value Over Time (Median Projection)",
        xaxis_title="Age",
        yaxis_title="Portfolio Value ($)",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=500,
    )
    
    st.plotly_chart(_traj_fig, use_container_width=True)
    
    # Success probability comparison
    st.markdown("#### ✅ Success Probability Comparison")
    
    _success_data = []
    for scenario in _scenarios:
        result = st.session_state.scenario_results.get(scenario.id, {})
        if result.get("success"):
            _success_data.append({
                "Scenario": scenario.name,
                "Success Rate": result["success_probability"] * 100,
            })
    
    if _success_data:
        _success_df = pd.DataFrame(_success_data)
        
        _success_fig = go.Figure()
        _success_colors = [
            "rgb(0,204,150)" if v >= 90 else ("rgb(255,165,0)" if v >= 75 else "rgb(239,85,59)")
            for v in _success_df["Success Rate"]
        ]
        
        _success_fig.add_trace(go.Bar(
            x=_success_df["Scenario"],
            y=_success_df["Success Rate"],
            marker_color=_success_colors,
            text=[f"{v:.1f}%" for v in _success_df["Success Rate"]],
            textposition="outside",
        ))
        
        _success_fig.add_hline(
            y=90, line_dash="dash", line_color="orange",
            annotation_text="90% Target", annotation_position="right"
        )
        
        _success_fig.update_layout(
            title="Success Probability by Scenario",
            xaxis_title="Scenario",
            yaxis_title="Success Probability (%)",
            yaxis_range=[0, 110],
            height=400,
        )
        
        st.plotly_chart(_success_fig, use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 2: Cash Flow Analysis
# ----------------------------------------------------------------------------

with _tab2:
    st.subheader("💰 Cash Flow Analysis")
    st.caption("Compare income, expenses, and net cash flow across scenarios")
    
    # Create cash flow comparison
    for scenario in _scenarios:
        with st.expander(f"📊 {scenario.name} - Cash Flow Details", expanded=len(_scenarios) == 1):
            # Calculate timeline with life events
            timeline = calculate_event_timeline(
                scenario.life_events,
                scenario.retirement_age,
                min(scenario.plan_to_age, scenario.retirement_age + 30)
            )
            
            # Build cash flow data
            _cf_data = []
            for age in range(scenario.retirement_age, min(scenario.plan_to_age, scenario.retirement_age + 30) + 1):
                event_impact = timeline.get(age, {})
                
                # Base income and expenses
                base_income = 0
                if age >= scenario.social_security.person1_start_age:
                    base_income += scenario.social_security.person1_amount
                if scenario.social_security.person2_start_age and age >= scenario.social_security.person2_start_age:
                    base_income += scenario.social_security.person2_amount
                
                total_income = base_income + event_impact.get("income", 0)
                total_expenses = scenario.annual_expenses + event_impact.get("expense", 0)
                net_cash_flow = total_income - total_expenses
                
                _cf_data.append({
                    "Age": age,
                    "Income": total_income,
                    "Expenses": total_expenses,
                    "Net Cash Flow": net_cash_flow,
                })
            
            _cf_df = pd.DataFrame(_cf_data)
            
            # Create stacked area chart
            _cf_fig = go.Figure()
            
            _cf_fig.add_trace(go.Scatter(
                x=_cf_df["Age"],
                y=_cf_df["Income"],
                mode='lines',
                name='Income',
                line=dict(color='rgb(0,204,150)', width=2),
                fill='tozeroy',
                fillcolor='rgba(0,204,150,0.3)',
            ))
            
            _cf_fig.add_trace(go.Scatter(
                x=_cf_df["Age"],
                y=_cf_df["Expenses"],
                mode='lines',
                name='Expenses',
                line=dict(color='rgb(239,85,59)', width=2),
                fill='tozeroy',
                fillcolor='rgba(239,85,59,0.3)',
            ))
            
            _cf_fig.add_trace(go.Scatter(
                x=_cf_df["Age"],
                y=_cf_df["Net Cash Flow"],
                mode='lines',
                name='Net Cash Flow',
                line=dict(color='rgb(99,110,250)', width=3, dash='dash'),
            ))
            
            _cf_fig.update_layout(
                title=f"Cash Flow Timeline - {scenario.name}",
                xaxis_title="Age",
                yaxis_title="Annual Amount ($)",
                yaxis_tickformat="$,.0f",
                hovermode="x unified",
                height=400,
            )
            
            st.plotly_chart(_cf_fig, use_container_width=True)
            
            # Summary metrics
            _cf_col1, _cf_col2, _cf_col3 = st.columns(3)
            _cf_col1.metric("Avg Annual Income", format_currency(float(_cf_df["Income"].mean())))
            _cf_col2.metric("Avg Annual Expenses", format_currency(float(_cf_df["Expenses"].mean())))
            _cf_col3.metric("Avg Net Cash Flow", format_currency(float(_cf_df["Net Cash Flow"].mean())))

# ----------------------------------------------------------------------------
# TAB 3: Life Events Timeline
# ----------------------------------------------------------------------------

with _tab3:
    st.subheader("📅 Life Events Timeline")
    st.caption("View and manage life events for each scenario")
    
    for scenario in _scenarios:
        with st.expander(f"📅 {scenario.name} - Life Events", expanded=len(_scenarios) == 1):
            if not scenario.life_events:
                st.info("No life events defined for this scenario")
                if st.button(f"➕ Add Life Event to {scenario.name}", key=f"add_event_{scenario.id}"):
                    st.session_state.editing_scenario = scenario.id
                    st.session_state.show_event_editor = True
                    st.rerun()
            else:
                # Display events in timeline
                _events_df = pd.DataFrame([
                    {
                        "Event": event.name,
                        "Type": event.event_type.value.replace("_", " ").title(),
                        "Start Age": event.start_age,
                        "End Age": event.end_age if event.end_age else "One-time",
                        "Income Change": format_currency(event.income_change) if event.income_change else "-",
                        "Expense Change": format_currency(event.expense_change) if event.expense_change else "-",
                        "One-Time Amount": format_currency(event.one_time_amount) if event.one_time_amount else "-",
                    }
                    for event in scenario.life_events
                ])
                
                st.dataframe(_events_df, use_container_width=True, hide_index=True)
                
                # Check for conflicts
                conflicts = detect_event_conflicts(scenario.life_events)
                if conflicts:
                    st.warning(f"⚠️ {len(conflicts)} potential conflict(s) detected")
                    for conflict in conflicts:
                        severity_icon = "⚠️" if conflict["severity"] == "warning" else "ℹ️"
                        st.caption(f"{severity_icon} {conflict['message']}")

                # Check for life events outside the simulation age range.
                # Warnings are generated by run_scenario_monte_carlo and stored
                # in MonteCarloResult.notes; retrieve them from the cached result.
                _cached = st.session_state.scenario_results.get(scenario.id, {})
                if _cached.get("success") and _cached.get("result"):
                    _oor_warnings = [
                        n for n in (_cached["result"].notes or [])
                        if n.startswith("Life event '")
                    ]
                    if _oor_warnings:
                        st.warning(
                            f"⚠️ {len(_oor_warnings)} life event(s) fall outside the "
                            f"simulation range (ages {scenario.retirement_age}–"
                            f"{scenario.plan_to_age}) and will have no effect:"
                        )
                        for _w in _oor_warnings:
                            st.caption(f"⚠️ {_w}")

                # Timeline visualization
                st.markdown("#### Event Timeline")
                _timeline_fig = go.Figure()
                
                for idx, event in enumerate(scenario.life_events):
                    end_age = event.end_age if event.end_age else event.start_age
                    
                    _timeline_fig.add_trace(go.Scatter(
                        x=[event.start_age, end_age],
                        y=[idx, idx],
                        mode='lines+markers',
                        name=event.name,
                        line=dict(color=event.color, width=8),
                        marker=dict(size=12, color=event.color),
                        hovertemplate=f'<b>{event.name}</b><br>Ages: {event.start_age}-{end_age}<extra></extra>',
                    ))
                
                _timeline_fig.update_layout(
                    title="Life Events Timeline",
                    xaxis_title="Age",
                    yaxis_title="",
                    yaxis=dict(showticklabels=False),
                    height=max(200, len(scenario.life_events) * 50),
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.05),
                )
                
                st.plotly_chart(_timeline_fig, use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 4: Parameter Comparison
# ----------------------------------------------------------------------------

with _tab4:
    st.subheader("⚙️ Parameter Comparison")
    st.caption("Compare key parameters across all selected scenarios")
    
    # Build comparison table
    _param_data = []
    for scenario in _scenarios:
        result = st.session_state.scenario_results.get(scenario.id, {})
        
        _param_data.append({
            "Scenario": scenario.name,
            "Starting Portfolio": format_currency(scenario.initial_portfolio),
            "Annual Expenses": format_currency(scenario.annual_expenses),
            "Retirement Age": scenario.retirement_age,
            "Plan To Age": scenario.plan_to_age,
            "Inflation Rate": format_percentage(scenario.inflation_rate),
            "SS Person 1": format_currency(scenario.social_security.person1_amount),
            "SS Start Age": scenario.social_security.person1_start_age,
            "Life Events": len(scenario.life_events),
            "Success Rate": format_percentage(result.get("success_probability", 0)) if result.get("success") else "N/A",
            "Final Portfolio (Median)": format_currency(result.get("median_final", 0)) if result.get("success") else "N/A",
        })
    
    _param_df = pd.DataFrame(_param_data)
    st.dataframe(_param_df, use_container_width=True, hide_index=True)
    
    # Download comparison
    _csv = _param_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Comparison (CSV)",
        data=_csv,
        file_name=f"scenario_comparison_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

# ----------------------------------------------------------------------------
# TAB 5: Edit Scenarios
# ----------------------------------------------------------------------------

with _tab5:
    st.subheader("✏️ Edit Scenarios")
    st.caption("Modify scenario parameters and life events")
    
    if len(_scenarios) == 1:
        scenario = _scenarios[0]
        
        st.markdown(f"### Editing: {scenario.name}")
        
        with st.form(f"edit_scenario_{scenario.id}"):
            _edit_col1, _edit_col2 = st.columns(2)
            
            with _edit_col1:
                st.markdown("#### Basic Information")
                new_name = st.text_input("Scenario Name", value=scenario.name)
                new_description = st.text_area("Description", value=scenario.description)
                
                st.markdown("#### Financial Parameters")
                new_portfolio = st.number_input(
                    "Starting Portfolio ($)",
                    min_value=0,
                    value=int(scenario.initial_portfolio),
                    step=50_000
                )
                new_expenses = st.number_input(
                    "Annual Expenses ($)",
                    min_value=0,
                    value=int(scenario.annual_expenses),
                    step=5_000
                )
                new_inflation = st.slider(
                    "Inflation Rate (%)",
                    min_value=0.0,
                    max_value=10.0,
                    value=scenario.inflation_rate * 100,
                    step=0.1
                ) / 100
            
            with _edit_col2:
                st.markdown("#### Personal Parameters")
                new_retirement_age = st.number_input(
                    "Retirement Age",
                    min_value=40,
                    max_value=80,
                    value=scenario.retirement_age
                )
                new_plan_age = st.number_input(
                    "Plan To Age",
                    min_value=70,
                    max_value=120,
                    value=scenario.plan_to_age
                )
                
                st.markdown("#### Social Security")
                new_ss_amount = st.number_input(
                    "Annual SS Amount ($)",
                    min_value=0,
                    value=int(scenario.social_security.person1_amount),
                    step=1_000
                )
                new_ss_age = st.number_input(
                    "SS Start Age",
                    min_value=62,
                    max_value=70,
                    value=scenario.social_security.person1_start_age
                )
            
            _submit_col1, _submit_col2 = st.columns(2)
            with _submit_col1:
                submitted = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
            with _submit_col2:
                rerun_analysis = st.form_submit_button("💾 Save & Re-run Analysis", use_container_width=True)
            
            if submitted or rerun_analysis:
                # Update scenario
                scenario.name = new_name
                scenario.description = new_description
                scenario.initial_portfolio = float(new_portfolio)
                scenario.annual_expenses = float(new_expenses)
                scenario.inflation_rate = float(new_inflation)
                scenario.retirement_age = int(new_retirement_age)
                scenario.plan_to_age = int(new_plan_age)
                scenario.social_security.person1_amount = float(new_ss_amount)
                scenario.social_security.person1_start_age = int(new_ss_age)
                
                _scenario_mgr.update_scenario(scenario)
                
                if rerun_analysis:
                    # Clear cached results
                    if scenario.id in st.session_state.scenario_results:
                        del st.session_state.scenario_results[scenario.id]
                
                st.success("✅ Scenario updated successfully!")
                st.rerun()
        
        # Life event management
        st.markdown("---")
        st.markdown("### 📅 Manage Life Events")
        
        if st.button("➕ Add Life Event", key="add_event_btn"):
            st.session_state.show_event_editor = True
        
        if st.session_state.show_event_editor:
            with st.form("add_life_event"):
                st.markdown("#### Add New Life Event")
                
                templates = get_template_list()
                template_names = [t["name"] for t in templates]
                
                selected_template = st.selectbox("Event Template", template_names)
                
                # Get template details
                template = next(t for t in templates if t["name"] == selected_template)
                
                event_name = st.text_input("Event Name", value=selected_template) or selected_template
                start_age = st.number_input("Start Age", min_value=40, max_value=120, value=scenario.retirement_age)
                
                if template["type"].value != "custom":
                    end_age_input = st.number_input(
                        "End Age (leave 0 for one-time event)",
                        min_value=0,
                        max_value=120,
                        value=0
                    )
                    end_age = end_age_input if end_age_input > 0 else None
                else:
                    end_age = None
                
                income_change = st.number_input("Annual Income Change ($)", value=0, step=1_000)
                expense_change = st.number_input("Annual Expense Change ($)", value=0, step=1_000)
                one_time_amount = st.number_input("One-Time Amount ($)", value=0, step=10_000)
                
                notes = st.text_area("Notes") or ""
                
                _event_col1, _event_col2 = st.columns(2)
                with _event_col1:
                    add_event = st.form_submit_button("➕ Add Event", type="primary", use_container_width=True)
                with _event_col2:
                    cancel_event = st.form_submit_button("❌ Cancel", use_container_width=True)
                
                if add_event:
                    # Create new event
                    from scenario_manager import LifeEventType
                    new_event = LifeEvent(
                        id=f"event_{len(scenario.life_events)}_{start_age}",
                        event_type=template["type"],
                        name=event_name,
                        start_age=start_age,
                        end_age=end_age,
                        income_change=float(income_change),
                        expense_change=float(expense_change),
                        one_time_amount=float(one_time_amount),
                        notes=notes,
                        color=template["color"],
                    )
                    
                    scenario.life_events.append(new_event)
                    _scenario_mgr.update_scenario(scenario)
                    
                    # Clear cached results
                    if scenario.id in st.session_state.scenario_results:
                        del st.session_state.scenario_results[scenario.id]
                    
                    st.session_state.show_event_editor = False
                    st.success("✅ Life event added!")
                    st.rerun()
                
                if cancel_event:
                    st.session_state.show_event_editor = False
                    st.rerun()
    
    else:
        st.info("👆 Select exactly one scenario above to edit its parameters")

# ============================================================================
# Footer Actions
# ============================================================================

st.markdown("---")

_footer_col1, _footer_col2, _footer_col3, _footer_col4 = st.columns(4)

with _footer_col1:
    if st.button("🔄 Re-run All Analyses", use_container_width=True):
        st.session_state.scenario_results = {}
        st.rerun()

with _footer_col2:
    if st.button("🔗 Generate Share Link", use_container_width=True,
                 disabled=not st.session_state.selected_scenarios):
        url_param = _scenario_mgr.encode_scenario_url(st.session_state.selected_scenarios)
        share_url = f"?scenarios={url_param}"
        st.code(share_url, language=None)
        st.info("💡 Copy this parameter and append to your app URL to share these scenarios")

with _footer_col3:
    if st.button("📥 Export Scenarios", use_container_width=True,
                 disabled=not st.session_state.selected_scenarios):
        export_data = []
        for scenario_id in st.session_state.selected_scenarios:
            scenario = _scenario_mgr.get_scenario(scenario_id)
            if scenario:
                export_data.append(scenario.to_dict())
        
        export_json = json.dumps(export_data, indent=2)
        st.download_button(
            label="📥 Download JSON",
            data=export_json,
            file_name=f"scenarios_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            key="export_json_btn"
        )

with _footer_col4:
    if st.button("ℹ️ Help", use_container_width=True):
        st.info("""
        **Scenario Planning Tips:**
        
        1. **Start with Baseline**: Create a baseline scenario from your current plan
        2. **Clone & Modify**: Clone the baseline and adjust one parameter at a time
        3. **Add Life Events**: Model major financial events like inheritance, part-time work
        4. **Compare Results**: Look at success rates and portfolio trajectories
        5. **Iterate**: Refine scenarios based on insights
        
        **Life Event Examples:**
        - Early retirement at 60 with reduced expenses
        - Part-time consulting work ages 62-67
        - Inheritance windfall at age 70
        - Downsizing home at age 75
        """)

# Made with Bob