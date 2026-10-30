"""Scenario Planning service for retirement planning.

Provides scenario CRUD, life event modeling, timeline calculations,
conflict detection, parameter comparison, and Monte Carlo integration.
"""
from __future__ import annotations

import logging
from typing import Any
import numpy as np

import settings
from config import get_config_manager
from scenario_manager import (
    Scenario,
    ScenarioManager,
    LifeEvent,
    LifeEventType,
    create_baseline_from_config,
)
from life_event_modeler import (
    detect_event_conflicts,
    calculate_event_timeline,
    get_template_list,
)
from scenario_integration import run_scenario_monte_carlo

logger = logging.getLogger(__name__)


def _get_manager() -> ScenarioManager:
    storage_dir = settings.data_path("data", "scenarios")
    mgr = ScenarioManager(storage_dir=storage_dir)
    # Ensure baseline exists
    scenarios = mgr.list_scenarios()
    if not scenarios:
        try:
            cfg = get_config_manager()
            baseline = create_baseline_from_config(cfg)
            mgr.create_scenario(baseline)
        except Exception as e:
            logger.warning("Could not auto-generate baseline scenario: %s", e)
    return mgr


def list_scenarios() -> list[dict[str, Any]]:
    """List all scenarios (metadata summaries)."""
    mgr = _get_manager()
    return mgr.list_scenarios()


def get_scenario(scenario_id: str) -> dict[str, Any] | None:
    """Get full scenario details by ID."""
    mgr = _get_manager()
    sc = mgr.get_scenario(scenario_id)
    if not sc:
        return None
    return sc.to_dict()


def create_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new scenario from dictionary data."""
    mgr = _get_manager()
    scenario = Scenario.from_dict(payload)
    created = mgr.create_scenario(scenario)
    return created.to_dict()


def update_scenario(scenario_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing scenario."""
    mgr = _get_manager()
    sc = mgr.get_scenario(scenario_id)
    if not sc:
        return None

    # Update basic fields if provided
    if "name" in payload:
        sc.name = str(payload["name"])
    if "description" in payload:
        sc.description = str(payload["description"])

    # Financial
    if "financial" in payload and isinstance(payload["financial"], dict):
        fin = payload["financial"]
        if "initial_portfolio" in fin and fin["initial_portfolio"] is not None:
            sc.initial_portfolio = float(fin["initial_portfolio"])
        if "annual_expenses" in fin and fin["annual_expenses"] is not None:
            sc.annual_expenses = float(fin["annual_expenses"])
        if "inflation_rate" in fin and fin["inflation_rate"] is not None:
            sc.inflation_rate = float(fin["inflation_rate"])
        if "portfolio_allocation" in fin and fin["portfolio_allocation"] is not None:
            sc.portfolio_allocation = fin["portfolio_allocation"]
    
    if "initial_portfolio" in payload and payload["initial_portfolio"] is not None:
        sc.initial_portfolio = float(payload["initial_portfolio"])
    if "annual_expenses" in payload and payload["annual_expenses"] is not None:
        sc.annual_expenses = float(payload["annual_expenses"])
    if "inflation_rate" in payload and payload["inflation_rate"] is not None:
        sc.inflation_rate = float(payload["inflation_rate"])

    # Personal
    if "personal" in payload and isinstance(payload["personal"], dict):
        pers = payload["personal"]
        if "retirement_age" in pers and pers["retirement_age"] is not None:
            sc.retirement_age = int(pers["retirement_age"])
        if "plan_to_age" in pers and pers["plan_to_age"] is not None:
            sc.plan_to_age = int(pers["plan_to_age"])
        if "person1_age" in pers and pers["person1_age"] is not None:
            sc.person1_age = int(pers["person1_age"])
        if "person2_age" in pers:
            sc.person2_age = int(pers["person2_age"]) if pers["person2_age"] is not None else None
    
    if "retirement_age" in payload and payload["retirement_age"] is not None:
        sc.retirement_age = int(payload["retirement_age"])
    if "plan_to_age" in payload and payload["plan_to_age"] is not None:
        sc.plan_to_age = int(payload["plan_to_age"])

    # Social Security
    if "income_sources" in payload and "social_security" in payload["income_sources"]:
        ss = payload["income_sources"]["social_security"]
        if "person1_amount" in ss:
            sc.social_security.person1_amount = float(ss["person1_amount"])
        if "person1_start_age" in ss:
            sc.social_security.person1_start_age = int(ss["person1_start_age"])
        if "person2_amount" in ss:
            sc.social_security.person2_amount = float(ss["person2_amount"])
        if "person2_start_age" in ss:
            sc.social_security.person2_start_age = int(ss["person2_start_age"]) if ss["person2_start_age"] is not None else None
    elif "social_security" in payload:
        ss = payload["social_security"]
        if "person1_amount" in ss:
            sc.social_security.person1_amount = float(ss["person1_amount"])
        if "person1_start_age" in ss:
            sc.social_security.person1_start_age = int(ss["person1_start_age"])

    # Life events list direct update
    if "life_events" in payload:
        sc.life_events = [LifeEvent.from_dict(ev) for ev in payload["life_events"]]

    updated = mgr.update_scenario(sc)
    return updated.to_dict()


def clone_scenario(scenario_id: str, new_name: str | None = None) -> dict[str, Any] | None:
    """Clone an existing scenario."""
    mgr = _get_manager()
    sc = mgr.get_scenario(scenario_id)
    if not sc:
        return None
    cloned = sc.clone(new_name=new_name)
    saved = mgr.create_scenario(cloned)
    return saved.to_dict()


def delete_scenario(scenario_id: str) -> bool:
    """Delete a scenario."""
    mgr = _get_manager()
    return mgr.delete_scenario(scenario_id)


def get_templates() -> list[dict[str, Any]]:
    """Get all pre-defined life event templates."""
    raw = get_template_list()
    out = []
    for t in raw:
        out.append({
            "name": t["name"],
            "type": t["type"].value,
            "description": t.get("description", ""),
            "color": t.get("color", "#3B82F6"),
            "default_income_change": t.get("default_income_change", 0.0),
            "default_expense_change": t.get("default_expense_change", 0.0),
            "default_one_time": t.get("default_one_time", 0.0),
        })
    return out


def add_life_event(scenario_id: str, event_data: dict[str, Any]) -> dict[str, Any] | None:
    """Add a life event to a scenario."""
    mgr = _get_manager()
    sc = mgr.get_scenario(scenario_id)
    if not sc:
        return None

    raw_type = event_data.get("event_type", "custom")
    try:
        ev_type = LifeEventType(raw_type)
    except ValueError:
        ev_type = LifeEventType.CUSTOM

    start_age = int(event_data.get("start_age", sc.retirement_age))
    end_age_raw = event_data.get("end_age")
    end_age = int(end_age_raw) if end_age_raw and int(end_age_raw) > 0 else None

    ev_id = event_data.get("id") or f"event_{len(sc.life_events)}_{start_age}"
    new_event = LifeEvent(
        id=ev_id,
        event_type=ev_type,
        name=str(event_data.get("name", "Custom Event")),
        start_age=start_age,
        end_age=end_age,
        income_change=float(event_data.get("income_change", 0.0)),
        expense_change=float(event_data.get("expense_change", 0.0)),
        one_time_amount=float(event_data.get("one_time_amount", 0.0)),
        notes=str(event_data.get("notes", "")),
        color=str(event_data.get("color", "#3B82F6")),
    )

    sc.life_events.append(new_event)
    mgr.update_scenario(sc)
    return sc.to_dict()


def delete_life_event(scenario_id: str, event_id: str) -> dict[str, Any] | None:
    """Remove a life event from a scenario."""
    mgr = _get_manager()
    sc = mgr.get_scenario(scenario_id)
    if not sc:
        return None

    sc.life_events = [e for e in sc.life_events if e.id != event_id]
    mgr.update_scenario(sc)
    return sc.to_dict()


def analyze_scenario(scenario_id: str, n_simulations: int = 5000) -> dict[str, Any]:
    """Run Monte Carlo simulation and timeline calculations for a scenario."""
    mgr = _get_manager()
    sc = mgr.get_scenario(scenario_id)
    if not sc:
        return {"success": False, "error": f"Scenario {scenario_id} not found"}

    try:
        mc_result = run_scenario_monte_carlo(
            sc,
            n_simulations=n_simulations,
            include_life_events=True,
        )

        # Median trajectory
        median_path = []
        ages = list(range(sc.retirement_age, sc.plan_to_age + 1))
        if hasattr(mc_result, "portfolio_paths") and mc_result.portfolio_paths is not None:
            raw_median = np.median(mc_result.portfolio_paths, axis=0)
            median_path = [float(v) for v in raw_median[:len(ages)]]

        # Cash flow timeline
        timeline_map = calculate_event_timeline(
            sc.life_events,
            sc.retirement_age,
            min(sc.plan_to_age, sc.retirement_age + 30),
        )

        cash_flows = []
        for age in range(sc.retirement_age, min(sc.plan_to_age, sc.retirement_age + 30) + 1):
            impact = timeline_map.get(age, {})
            base_income = 0.0
            if age >= sc.social_security.person1_start_age:
                base_income += sc.social_security.person1_amount
            if sc.social_security.person2_start_age and age >= sc.social_security.person2_start_age:
                base_income += sc.social_security.person2_amount

            tot_inc = base_income + impact.get("income", 0.0)
            tot_exp = sc.annual_expenses + impact.get("expense", 0.0)
            net_cf = tot_inc - tot_exp

            cash_flows.append({
                "age": age,
                "income": tot_inc,
                "expenses": tot_exp,
                "net_cash_flow": net_cf,
            })

        # Conflict detection
        conflicts = detect_event_conflicts(sc.life_events)

        return {
            "success": True,
            "scenario_id": sc.id,
            "scenario_name": sc.name,
            "success_probability": float(mc_result.success_probability),
            "median_final": float(mc_result.median_final_portfolio),
            "p10_final": float(mc_result.p10_final_portfolio),
            "p90_final": float(mc_result.p90_final_portfolio),
            "depletion_age": mc_result.years_to_depletion_p10,
            "median_path": median_path,
            "ages": ages[:len(median_path)],
            "cash_flows": cash_flows,
            "conflicts": conflicts,
            "notes": mc_result.notes or [],
        }
    except Exception as e:
        logger.exception("Scenario analysis failed: %s", e)
        return {
            "success": False,
            "scenario_id": sc.id,
            "scenario_name": sc.name,
            "error": str(e),
        }
