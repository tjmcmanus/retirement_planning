"""Streamlit-free service for Monte Carlo simulation and analysis.

Wraps ``monte_carlo.py`` and provides job-friendly worker functions, default values,
validation, and JSON-safe data formatting for the API and frontend.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from config import get_config_manager
from app.services import networth as nw_service
from monte_carlo import (
    LONGEVITY_SCENARIOS,
    PORTFOLIO_PRESETS,
    STRESS_SCENARIOS,
    MonteCarloInputs,
    MonteCarloResult,
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
import settings

logger = logging.getLogger(__name__)


def get_monte_carlo_meta() -> dict[str, Any]:
    """Return presets, scenario options, and field bounds."""
    return {
        "portfolio_presets": list(PORTFOLIO_PRESETS.keys()),
        "stress_scenarios": list(STRESS_SCENARIOS.keys()),
        "longevity_scenarios": list(LONGEVITY_SCENARIOS.keys()),
    }


def get_monte_carlo_defaults() -> dict[str, Any]:
    """Derive starting default values from saved config and net worth."""
    config_mgr = get_config_manager()

    default_portfolio = 1_500_000
    try:
        networth = nw_service.load_networth_history()
        if not networth.empty:
            latest = networth.iloc[-1]
            tot = (
                float(latest.get("cash", 0))
                + float(latest.get("taxable", 0))
                + float(latest.get("tax_deferred", 0))
                + float(latest.get("tax_free", 0))
            )
            if tot >= 10_000:
                default_portfolio = int(tot)
    except Exception as exc:
        logger.warning("Could not read net worth for Monte Carlo default portfolio: %s", exc)

    expenses = float(config_mgr.get("financial_assumptions", "expected_annual_expenses", 80_000))
    p1_birth = config_mgr.get("personal_info", "person1_birth_date", "1965-01-01")
    p2_birth = config_mgr.get("personal_info", "person2_birth_date", "1967-01-01")
    p1_age = config_mgr.calculate_age(p1_birth)
    p2_age = config_mgr.calculate_age(p2_birth)
    p1_retire = int(config_mgr.get("personal_info", "person1_retirement_age", 62))
    p2_retire = int(config_mgr.get("personal_info", "person2_retirement_age", 62))

    start_age = min(p1_retire, p2_retire)
    end_age = min(95, max(p1_age, p2_age) + 30)
    if end_age <= start_age:
        end_age = max(90, start_age + 25)

    p1_ss = float(config_mgr.get("social_security", "person1_ssi_amount", 0))
    p2_ss = float(config_mgr.get("social_security", "person2_ssi_amount", 0))
    default_ss_annual = (p1_ss + p2_ss) * 12
    default_ss_age = int(config_mgr.get("social_security", "person1_ssi_age", 70))
    inflation_pct = float(config_mgr.get("financial_assumptions", "expense_inflation_rate", 2.9))

    return {
        "portfolio": default_portfolio,
        "withdrawal": int(expenses),
        "start_age": start_age,
        "end_age": end_age,
        "ss_annual": int(default_ss_annual),
        "ss_start_age": default_ss_age,
        "inflation_pct": round(inflation_pct, 2),
        "allocation": "Moderate (70/30)",
        "n_simulations": 10_000,
    }


def parse_mc_inputs(data: dict[str, Any]) -> MonteCarloInputs:
    """Validate and construct MonteCarloInputs from API payload."""
    portfolio = float(data.get("portfolio", 1_500_000))
    if portfolio < 10_000:
        raise ValueError("Starting portfolio must be at least $10,000")

    withdrawal = float(data.get("withdrawal", 80_000))
    if withdrawal < 1_000:
        raise ValueError("Annual withdrawal must be at least $1,000")

    start_age = int(data.get("start_age", 62))
    if not (40 <= start_age <= 80):
        raise ValueError("Retirement age must be between 40 and 80")

    end_age = int(data.get("end_age", 90))
    if not (70 <= end_age <= 110):
        raise ValueError("Plan to age must be between 70 and 110")
    if end_age <= start_age:
        raise ValueError("Plan to age must be greater than retirement age")

    ss_annual = float(data.get("ss_annual", 0))
    if ss_annual < 0:
        raise ValueError("Social security amount cannot be negative")

    ss_start_age = int(data.get("ss_start_age", 70))
    if not (62 <= ss_start_age <= 70):
        raise ValueError("Social security start age must be between 62 and 70")

    inflation_pct = float(data.get("inflation_pct", 2.9))
    if not (0.5 <= inflation_pct <= 20.0):
        raise ValueError("Inflation rate must be between 0.5% and 20%")
    inflation_rate = inflation_pct / 100.0

    allocation_name = str(data.get("allocation", "Moderate (70/30)"))
    if allocation_name not in PORTFOLIO_PRESETS:
        raise ValueError(f"Unknown allocation preset: '{allocation_name}'")
    allocation = PORTFOLIO_PRESETS[allocation_name]

    n_sims = int(data.get("n_simulations", 10_000))
    if not (100 <= n_sims <= 50_000):
        raise ValueError("Simulations count must be between 100 and 50,000")

    seed = int(data.get("random_seed", 42))

    return MonteCarloInputs(
        initial_portfolio=portfolio,
        annual_withdrawal=withdrawal,
        start_age=start_age,
        end_age=end_age,
        portfolio_allocation=allocation,
        inflation_rate=inflation_rate,
        withdrawal_growth_rate=inflation_rate,
        social_security_annual=ss_annual,
        ss_start_age=ss_start_age,
        n_simulations=n_sims,
        random_seed=seed,
    )


def save_monte_carlo_results_json(mc_data: dict[str, Any]) -> None:
    """Save Monte Carlo summary results to data/monte_carlo_results.json for reports."""
    try:
        target = settings.data_path("data", "monte_carlo_results.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(mc_data, f, indent=2)
    except Exception as exc:
        logger.warning("Failed to save monte_carlo_results.json: %s", exc)


def update_stress_test_json(stress_data: list[dict[str, Any]]) -> None:
    """Append or update stress test results in data/monte_carlo_results.json."""
    try:
        target = settings.data_path("data", "monte_carlo_results.json")
        existing_data: dict[str, Any] = {}
        if target.exists():
            with open(target, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

        existing_data["stress_tests"] = stress_data
        existing_data["stress_test_timestamp"] = datetime.now().isoformat()
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2)
    except Exception as exc:
        logger.warning("Failed to update stress test in monte_carlo_results.json: %s", exc)


# ---------------------------------------------------------------------------
# Worker Functions for Background Jobs
# ---------------------------------------------------------------------------

def run_simulation_job(
    inputs_dict: dict[str, Any],
    progress_cb: Callable[[int, str], None],
) -> dict[str, Any]:
    """Execute main Monte Carlo simulation with progress reporting."""
    progress_cb(10, "Validating simulation inputs...")
    inputs = parse_mc_inputs(inputs_dict)

    progress_cb(25, f"Running {inputs.n_simulations:,} Monte Carlo simulation paths...")
    result = run_monte_carlo(inputs)

    progress_cb(60, "Building percentile distributions & fan chart...")
    fan_df = build_fan_chart_df(result)
    fan_chart_data = fan_df.to_dict(orient="records") if not fan_df.empty else []

    progress_cb(75, "Calculating safe withdrawal rates...")
    swr_data = {}
    try:
        swr_90 = get_safe_withdrawal_rate(inputs, target_success=0.90)
        swr_75 = get_safe_withdrawal_rate(inputs, target_success=0.75)
        swr_65 = get_safe_withdrawal_rate(inputs, target_success=0.65)
        port_val = inputs.initial_portfolio
        swr_data = {
            "swr_90": {"amount": float(swr_90), "pct": float(swr_90 / port_val * 100)},
            "swr_75": {"amount": float(swr_75), "pct": float(swr_75 / port_val * 100)},
            "swr_65": {"amount": float(swr_65), "pct": float(swr_65 / port_val * 100)},
        }
    except Exception as exc:
        logger.warning("SWR calculation error: %s", exc)

    progress_cb(85, "Analyzing sequence-of-returns risk...")
    sor_data = {}
    try:
        sor_data = analyze_sequence_of_returns_risk(inputs)
    except Exception as exc:
        logger.warning("Sequence of returns error: %s", exc)

    progress_cb(95, "Saving results and preparing output...")
    # Persist JSON for reports
    mc_report_data: dict[str, Any] = {
        "success_rate": result.success_probability,
        "median_final_portfolio": result.median_final_portfolio,
        "p10_final_portfolio": result.p10_final_portfolio,
        "p90_final_portfolio": result.p90_final_portfolio,
        "years_to_depletion_p10": result.years_to_depletion_p10,
        "timestamp": datetime.now().isoformat(),
        "n_simulations": inputs.n_simulations,
        "available": True,
        "annual_withdrawal": float(inputs.annual_withdrawal),
        "initial_portfolio": float(inputs.initial_portfolio),
        "start_age": int(inputs.start_age),
        "end_age": int(inputs.end_age),
        "social_security_annual": float(inputs.social_security_annual),
        "ss_start_age": int(inputs.ss_start_age) if inputs.ss_start_age else None,
    }
    if result.portfolio_paths is not None:
        paths = result.portfolio_paths
        mc_report_data["scenario_paths"] = {
            "p10": np.percentile(paths, 10, axis=0).tolist(),
            "p25": np.percentile(paths, 25, axis=0).tolist(),
            "p50": np.percentile(paths, 50, axis=0).tolist(),
            "p75": np.percentile(paths, 75, axis=0).tolist(),
            "p90": np.percentile(paths, 90, axis=0).tolist(),
            "ages": list(range(inputs.start_age, inputs.end_age + 1)),
        }
    save_monte_carlo_results_json(mc_report_data)

    progress_cb(100, "Simulation complete")

    return {
        "success_probability": float(result.success_probability),
        "median_final_portfolio": float(result.median_final_portfolio),
        "p10_final_portfolio": float(result.p10_final_portfolio),
        "p90_final_portfolio": float(result.p90_final_portfolio),
        "years_to_depletion_p10": result.years_to_depletion_p10,
        "fan_chart": fan_chart_data,
        "safe_withdrawal_rates": swr_data,
        "sequence_risk": sor_data,
        "notes": result.notes,
        "inputs": inputs_dict,
    }


def run_stress_tests_job(
    inputs_dict: dict[str, Any],
    selected_scenarios: list[str],
    progress_cb: Callable[[int, str], None],
) -> dict[str, Any]:
    """Execute stress test scenarios."""
    progress_cb(10, "Validating inputs...")
    inputs = parse_mc_inputs(inputs_dict)
    scenarios = [s for s in selected_scenarios if s in STRESS_SCENARIOS]
    if not scenarios:
        scenarios = list(STRESS_SCENARIOS.keys())

    progress_cb(30, f"Running {len(scenarios)} stress test scenarios...")
    results = run_stress_tests(inputs, scenarios)

    progress_cb(80, "Formatting stress test results...")
    rows = []
    stress_json_data = []
    for s in results:
        rows.append({
            "scenario_name": s.scenario_name,
            "description": s.description,
            "success_probability": float(s.success_probability),
            "median_final_portfolio": float(s.median_final_portfolio),
            "p10_final_portfolio": float(s.p10_final_portfolio),
            "years_to_depletion_median": s.years_to_depletion_median,
            "portfolio_path_median": [float(v) for v in s.portfolio_path_median] if s.portfolio_path_median else [],
            "notes": s.notes,
        })
        stress_json_data.append({
            "scenario_name": s.scenario_name,
            "description": s.description,
            "success_probability": float(s.success_probability),
            "median_final_portfolio": float(s.median_final_portfolio),
            "p10_final_portfolio": float(s.p10_final_portfolio),
            "years_to_depletion_median": s.years_to_depletion_median,
            "portfolio_path_median": [float(v) for v in s.portfolio_path_median] if s.portfolio_path_median else [],
            "notes": s.notes,
        })

    update_stress_test_json(stress_json_data)
    ages = list(range(inputs.start_age, inputs.end_age + 1))

    progress_cb(100, "Stress tests complete")
    return {
        "results": rows,
        "ages": ages,
    }


def run_longevity_job(
    inputs_dict: dict[str, Any],
    selected_scenarios: list[str],
    progress_cb: Callable[[int, str], None],
) -> dict[str, Any]:
    """Execute longevity risk analysis."""
    progress_cb(10, "Validating inputs...")
    inputs = parse_mc_inputs(inputs_dict)

    chosen_ages = {
        k: v for k, v in LONGEVITY_SCENARIOS.items()
        if not selected_scenarios or k in selected_scenarios
    }
    if not chosen_ages:
        chosen_ages = LONGEVITY_SCENARIOS

    progress_cb(30, f"Evaluating {len(chosen_ages)} longevity horizons...")
    lon_results = run_longevity_analysis(inputs, chosen_ages)

    progress_cb(80, "Building longevity comparison summary and paths...")
    rows = []
    paths = {}
    for label, mc in lon_results.items():
        fan = build_fan_chart_df(mc)
        path = fan[["age", "p50"]].to_dict(orient="records") if not fan.empty else []
        paths[label] = path

        rows.append({
            "scenario": label,
            "plan_to_age": mc.inputs.end_age,
            "success_probability": float(mc.success_probability),
            "median_final_portfolio": float(mc.median_final_portfolio),
            "p10_final_portfolio": float(mc.p10_final_portfolio),
            "p10_depletion_age": mc.years_to_depletion_p10,
        })

    progress_cb(100, "Longevity analysis complete")
    return {
        "summary": rows,
        "paths": paths,
    }


def run_heatmap_job(
    inputs_dict: dict[str, Any],
    base_withdrawal: float,
    n_sims_cell: int,
    progress_cb: Callable[[int, str], None],
) -> dict[str, Any]:
    """Build withdrawal vs allocation success heatmap."""
    progress_cb(10, "Validating inputs...")
    base_inputs = parse_mc_inputs(inputs_dict)

    hm_inputs = MonteCarloInputs(
        initial_portfolio=base_inputs.initial_portfolio,
        annual_withdrawal=float(base_withdrawal),
        start_age=base_inputs.start_age,
        end_age=base_inputs.end_age,
        portfolio_allocation=base_inputs.portfolio_allocation,
        inflation_rate=base_inputs.inflation_rate,
        withdrawal_growth_rate=base_inputs.withdrawal_growth_rate,
        social_security_annual=base_inputs.social_security_annual,
        ss_start_age=base_inputs.ss_start_age,
        n_simulations=int(n_sims_cell),
        random_seed=base_inputs.random_seed,
    )

    progress_cb(25, "Simulating parameter matrix (this may take 15-30s)...")
    df = build_success_heatmap_df(hm_inputs)

    progress_cb(90, "Formatting heatmap data...")
    if df.empty:
        return {"columns": [], "index": [], "values": []}

    df_display = df.set_index("Annual Withdrawal")
    columns = list(df_display.columns)
    index = [str(idx) for idx in df_display.index]
    values = df_display.values.tolist()

    progress_cb(100, "Heatmap complete")
    return {
        "columns": columns,
        "index": index,
        "values": values,
    }


def run_comparison_job(
    inputs_dict: dict[str, Any],
    stress_scenarios: list[str],
    longevity_scenarios: list[str],
    progress_cb: Callable[[int, str], None],
) -> dict[str, Any]:
    """Run full baseline + stress + longevity comparison."""
    progress_cb(10, "Validating inputs...")
    inputs = parse_mc_inputs(inputs_dict)

    stress_selected = [s for s in stress_scenarios if s in STRESS_SCENARIOS]
    if not stress_selected:
        stress_selected = list(STRESS_SCENARIOS.keys())[:3]

    lon_selected = {
        k: v for k, v in LONGEVITY_SCENARIOS.items()
        if not longevity_scenarios or k in longevity_scenarios
    }
    if not lon_selected:
        lon_selected = {
            "Average (age 85)": 85,
            "Long-Lived (age 95)": 95,
            "Exceptional (age 105)": 105,
        }

    progress_cb(25, "Running full multi-scenario simulation suite...")
    comp_res = run_full_scenario_comparison(
        inputs,
        stress_scenarios=stress_selected,
        longevity_ages=lon_selected,
    )

    progress_cb(80, "Building comparison tables and charts...")
    comp_df = build_scenario_comparison_df(comp_res)
    records = comp_df.to_dict(orient="records") if not comp_df.empty else []

    # Chart data
    bar_data = []
    for row in records:
        scen = row.get("Scenario", "")
        sp_str = str(row.get("Success Probability", "0%")).replace("%", "").strip()
        try:
            sp_val = float(sp_str)
        except ValueError:
            sp_val = 0.0
        bar_data.append({"scenario": scen, "success_rate": sp_val})

    progress_cb(100, "Scenario comparison complete")
    return {
        "table": records,
        "bar_data": bar_data,
    }


def export_report_csv(
    inputs_dict: dict[str, Any],
    include_stress: bool = True,
    include_longevity: bool = True,
) -> bytes:
    """Generate CSV report for Monte Carlo simulation."""
    inputs = parse_mc_inputs(inputs_dict)
    baseline = run_monte_carlo(inputs)

    stress_res = None
    if include_stress:
        stress_res = run_stress_tests(inputs, list(STRESS_SCENARIOS.keys()))

    lon_res = None
    if include_longevity:
        lon_res = run_longevity_analysis(inputs, LONGEVITY_SCENARIOS)

    return generate_monte_carlo_report_csv(
        baseline,
        stress_results=stress_res,
        longevity_results=lon_res,
    )
