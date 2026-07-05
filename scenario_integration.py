"""
scenario_integration.py
=======================
Integration layer connecting Scenario Planning with existing modules

This module provides integration between the scenario planning feature and:
- Monte Carlo simulation engine
- Tax calculation modules
- Withdrawal strategy modules
- Portfolio management

Key Features:
- Convert scenarios to Monte Carlo inputs
- Apply tax strategies to scenarios
- Run withdrawal strategies with life events
- Generate comprehensive scenario reports
"""

from __future__ import annotations

import logging
from typing import Any
import pandas as pd
import numpy as np

from scenario_manager import Scenario, LifeEvent
from life_event_modeler import calculate_event_timeline
from monte_carlo import (
    MonteCarloInputs,
    MonteCarloResult,
    run_monte_carlo,
    PORTFOLIO_PRESETS,
)
from calculations import (
    calculate_taxable_income,
    calculate_cap_gains,
    calc_agi,
    calc_daf_value,
    calculate_age_adjusted_expenses,
    calculate_household_age_adjusted_expenses,
)
from load_data import (
    get_income_tax_brackets,
    get_cap_gains_brackets,
    get_std_deduction,
)

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Monte Carlo Integration
# ============================================================================

def scenario_to_monte_carlo_inputs(
    scenario: Scenario,
    n_simulations: int = 10_000,
    random_seed: int = 42,
) -> MonteCarloInputs:
    """
    Convert a Scenario to MonteCarloInputs for simulation.
    
    Args:
        scenario: Scenario to convert
        n_simulations: Number of Monte Carlo simulations
        random_seed: Random seed for reproducibility
    
    Returns:
        MonteCarloInputs configured from scenario
    """
    # Determine portfolio allocation
    allocation = scenario.portfolio_allocation
    
    # Find matching preset or use custom
    allocation_name = "Custom"
    for preset_name, preset_alloc in PORTFOLIO_PRESETS.items():
        if (abs(preset_alloc.get("stocks", 0) - allocation.get("stocks", 0)) < 0.01 and
            abs(preset_alloc.get("bonds", 0) - allocation.get("bonds", 0)) < 0.01):
            allocation_name = preset_name
            break
    
    # Use preset if found, otherwise use scenario allocation
    final_allocation = PORTFOLIO_PRESETS.get(allocation_name, allocation)
    
    # Calculate total social security
    total_ss = scenario.social_security.person1_amount
    if scenario.social_security.person2_amount:
        total_ss += scenario.social_security.person2_amount
    
    # Determine SS start age (use earlier of the two)
    ss_start_age = scenario.social_security.person1_start_age
    if scenario.social_security.person2_start_age:
        ss_start_age = min(ss_start_age, scenario.social_security.person2_start_age)
    
    logger.info(
        f"Converting scenario '{scenario.name}' to Monte Carlo inputs: "
        f"portfolio=${scenario.initial_portfolio:,.0f}, "
        f"expenses=${scenario.annual_expenses:,.0f}, "
        f"allocation={allocation_name}"
    )
    
    return MonteCarloInputs(
        initial_portfolio=scenario.initial_portfolio,
        annual_withdrawal=scenario.annual_expenses,
        start_age=scenario.retirement_age,
        end_age=scenario.plan_to_age,
        portfolio_allocation=final_allocation,
        inflation_rate=scenario.inflation_rate,
        withdrawal_growth_rate=scenario.inflation_rate,
        social_security_annual=total_ss,
        ss_start_age=ss_start_age,
        n_simulations=n_simulations,
        random_seed=random_seed,
    )


def _warn_out_of_range_events(scenario: Scenario) -> list[str]:
    """Return a warning string for each life event whose age range falls
    entirely or partially outside the simulation window
    [retirement_age, plan_to_age].  Each warning is also emitted via the
    module logger so it appears in server logs.

    A life event is considered out-of-range when:
    - ``start_age`` is beyond ``plan_to_age``  (event never reached), or
    - ``end_age`` (if set) is before ``retirement_age``  (event already over).

    Events that merely *start* before ``retirement_age`` but extend into the
    simulation window are not flagged — their in-window portion is applied
    normally by ``calculate_event_timeline``.
    """
    sim_start = scenario.retirement_age
    sim_end = scenario.plan_to_age
    warnings: list[str] = []

    for event in scenario.life_events:
        event_end = event.end_age if event.end_age is not None else event.start_age
        if event.start_age > sim_end:
            msg = (
                f"Life event '{event.name}' starts at age {event.start_age}, "
                f"which is beyond the simulation end age {sim_end} — "
                "it will have no effect on the projection."
            )
            logger.warning(msg)
            warnings.append(msg)
        elif event_end < sim_start:
            msg = (
                f"Life event '{event.name}' ends at age {event_end}, "
                f"which is before the simulation start age {sim_start} — "
                "it will have no effect on the projection."
            )
            logger.warning(msg)
            warnings.append(msg)

    return warnings


def run_scenario_monte_carlo(
    scenario: Scenario,
    n_simulations: int = 10_000,
    include_life_events: bool = True,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for a scenario.
    
    Args:
        scenario: Scenario to simulate
        n_simulations: Number of simulations
        include_life_events: Whether to include life event impacts
    
    Returns:
        MonteCarloResult with simulation outcomes.  Any life events whose age
        range lies entirely outside [retirement_age, plan_to_age] are recorded
        as warning strings in ``MonteCarloResult.notes``.
    """
    logger.info(f"Running Monte Carlo for scenario: {scenario.name}")

    # Validate life-event ages against the simulation window before running,
    # so the user receives explicit warnings rather than silent no-ops.
    out_of_range_warnings: list[str] = []
    if scenario.life_events:
        out_of_range_warnings = _warn_out_of_range_events(scenario)

    # Convert scenario to inputs
    mc_inputs = scenario_to_monte_carlo_inputs(scenario, n_simulations)
    
    # Run simulation
    result = run_monte_carlo(mc_inputs)
    
    # If life events are included, adjust the result
    if include_life_events and scenario.life_events:
        logger.info(f"Adjusting for {len(scenario.life_events)} life events")
        result = adjust_monte_carlo_for_life_events(result, scenario)

    # Attach out-of-range warnings to the result notes so callers (including
    # the UI) can surface them without re-examining every event.
    if out_of_range_warnings:
        result.notes = result.notes + out_of_range_warnings

    return result


def adjust_monte_carlo_for_life_events(
    mc_result: MonteCarloResult,
    scenario: Scenario,
) -> MonteCarloResult:
    """
    Adjust Monte Carlo results to account for life events.
    
    This is a simplified adjustment that modifies the portfolio paths
    based on life event impacts. For more accurate results, life events
    should be integrated directly into the Monte Carlo simulation.
    
    Args:
        mc_result: Original Monte Carlo result
        scenario: Scenario with life events
    
    Returns:
        Adjusted Monte Carlo result
    """
    if not scenario.life_events or mc_result.portfolio_paths is None:
        return mc_result
    
    # Calculate event timeline
    timeline = calculate_event_timeline(
        scenario.life_events,
        scenario.retirement_age,
        scenario.plan_to_age,
    )
    
    # Adjust portfolio paths
    adjusted_paths = mc_result.portfolio_paths.copy()
    
    for age_idx, age in enumerate(range(scenario.retirement_age, scenario.plan_to_age + 1)):
        if age in timeline:
            impact = timeline[age]
            portfolio_change = impact.get("portfolio_change", 0)
            
            # Apply portfolio change to all paths at this age
            if portfolio_change != 0:
                adjusted_paths[:, age_idx] += portfolio_change
                logger.debug(f"Applied ${portfolio_change:,.0f} portfolio change at age {age}")
    
    # Recalculate success metrics
    final_portfolios = adjusted_paths[:, -1]
    success_count = np.sum(final_portfolios > 0)
    success_probability = success_count / len(final_portfolios)
    
    # Create adjusted result
    adjusted_result = MonteCarloResult(
        success_probability=success_probability,
        median_final_portfolio=float(np.median(final_portfolios)),
        p10_final_portfolio=float(np.percentile(final_portfolios, 10)),
        p90_final_portfolio=float(np.percentile(final_portfolios, 90)),
        years_to_depletion_p10=mc_result.years_to_depletion_p10,
        portfolio_paths=adjusted_paths,
        inputs=mc_result.inputs,
        notes=mc_result.notes + [f"Adjusted for {len(scenario.life_events)} life events"],
    )
    
    logger.info(
        f"Adjusted Monte Carlo: success {mc_result.success_probability:.1%} → "
        f"{adjusted_result.success_probability:.1%}"
    )
    
    return adjusted_result


# ============================================================================
# Tax Calculation Integration
# ============================================================================

def calculate_scenario_taxes(
    scenario: Scenario,
    year: int = 2026,
    filing_status: str = "married_filing_jointly",
) -> dict[str, Any]:
    """
    Calculate estimated taxes for a scenario across retirement years.
    
    Args:
        scenario: Scenario to analyze
        year: Tax year for brackets
        filing_status: Tax filing status
    
    Returns:
        Dictionary with tax analysis results
    """
    logger.info(f"Calculating taxes for scenario: {scenario.name}")
    
    # Load tax data
    income_brackets = get_income_tax_brackets(year, filing_status)
    cap_gains_brackets = get_cap_gains_brackets(year, filing_status)
    std_deduction_df = get_std_deduction(year, filing_status)
    
    # Calculate event timeline
    timeline = calculate_event_timeline(
        scenario.life_events,
        scenario.retirement_age,
        min(scenario.plan_to_age, scenario.retirement_age + 30),
    )
    
    # Calculate taxes for each year
    tax_results = []
    total_taxes = 0
    total_income = 0
    
    for age in range(scenario.retirement_age, min(scenario.plan_to_age, scenario.retirement_age + 30) + 1):
        # Base income
        gross_income = 0
        
        # Social Security
        if age >= scenario.social_security.person1_start_age:
            gross_income += scenario.social_security.person1_amount
        if scenario.social_security.person2_start_age and age >= scenario.social_security.person2_start_age:
            gross_income += scenario.social_security.person2_amount
        
        # Pension
        if scenario.pension and age >= scenario.pension.start_age:
            gross_income += scenario.pension.annual_amount
        
        # Part-time income
        if scenario.part_time_income:
            if scenario.part_time_income.start_age <= age <= scenario.part_time_income.end_age:
                gross_income += scenario.part_time_income.annual_amount
        
        # Life event impacts
        if age in timeline:
            impact = timeline[age]
            gross_income += impact.get("income", 0)
        
        # Withdrawals (simplified - assume from tax-deferred)
        withdrawal = scenario.annual_expenses
        if age in timeline:
            withdrawal += timeline[age].get("expense", 0)
        
        gross_income += max(0, withdrawal)
        
        # Calculate AGI
        agi = calc_agi(gross_income, 0, std_deduction_df, 0)
        
        # Calculate federal tax
        # Ensure income_brackets is a DataFrame
        if isinstance(income_brackets, pd.DataFrame):
            tax_calc = calculate_taxable_income(agi, income_brackets)
            federal_tax = tax_calc.total_tax
        else:
            federal_tax = 0
            logger.warning(f"Invalid income_brackets type at age {age}")
        
        total_taxes += federal_tax
        total_income += gross_income
        
        tax_results.append({
            "age": age,
            "gross_income": gross_income,
            "agi": agi,
            "federal_tax": federal_tax,
            "effective_rate": federal_tax / gross_income if gross_income > 0 else 0,
        })
    
    avg_effective_rate = total_taxes / total_income if total_income > 0 else 0
    
    logger.info(
        f"Tax analysis complete: total_taxes=${total_taxes:,.0f}, "
        f"avg_rate={avg_effective_rate:.1%}"
    )
    
    return {
        "total_taxes": total_taxes,
        "total_income": total_income,
        "average_effective_rate": avg_effective_rate,
        "annual_details": tax_results,
        "filing_status": filing_status,
        "tax_year": year,
    }


def compare_scenario_taxes(
    scenarios: list[Scenario],
    year: int = 2026,
    filing_status: str = "married_filing_jointly",
) -> pd.DataFrame:
    """
    Compare tax implications across multiple scenarios.
    
    Args:
        scenarios: List of scenarios to compare
        year: Tax year
        filing_status: Filing status
    
    Returns:
        DataFrame with tax comparison
    """
    comparison_data = []
    
    for scenario in scenarios:
        tax_analysis = calculate_scenario_taxes(scenario, year, filing_status)
        
        comparison_data.append({
            "Scenario": scenario.name,
            "Total Taxes": tax_analysis["total_taxes"],
            "Total Income": tax_analysis["total_income"],
            "Avg Effective Rate": tax_analysis["average_effective_rate"],
            "Annual Avg Tax": tax_analysis["total_taxes"] / 30,  # Assuming 30 years
        })
    
    return pd.DataFrame(comparison_data)


# ============================================================================
# Strategy Integration
# ============================================================================

def apply_withdrawal_strategy_to_scenario(
    scenario: Scenario,
    strategy_name: str = "proportional",
) -> dict[str, Any]:
    """
    Apply a withdrawal strategy to a scenario.
    
    Args:
        scenario: Scenario to apply strategy to
        strategy_name: Name of withdrawal strategy
    
    Returns:
        Dictionary with strategy results
    """
    logger.info(f"Applying {strategy_name} strategy to scenario: {scenario.name}")
    
    # This is a placeholder for integration with existing strategy modules
    # In a full implementation, this would call the actual strategy functions
    
    return {
        "scenario_name": scenario.name,
        "strategy": strategy_name,
        "message": "Strategy integration placeholder - implement with actual strategy module",
    }


def optimize_roth_conversions_for_scenario(
    scenario: Scenario,
    target_bracket: float = 0.24,
) -> dict[str, Any]:
    """
    Optimize Roth conversions for a scenario.
    
    Args:
        scenario: Scenario to optimize
        target_bracket: Target tax bracket for conversions
    
    Returns:
        Dictionary with optimization results
    """
    logger.info(f"Optimizing Roth conversions for scenario: {scenario.name}")
    
    # This is a placeholder for integration with BETR Roth conversion module
    # In a full implementation, this would call betr_roth_conversion.py
    
    return {
        "scenario_name": scenario.name,
        "target_bracket": target_bracket,
        "message": "Roth conversion optimization placeholder - implement with BETR module",
    }


# ============================================================================
# Comprehensive Scenario Report
# ============================================================================

def generate_scenario_report(
    scenario: Scenario,
    include_monte_carlo: bool = True,
    include_taxes: bool = True,
    n_simulations: int = 10_000,
) -> dict[str, Any]:
    """
    Generate a comprehensive report for a scenario.
    
    Args:
        scenario: Scenario to analyze
        include_monte_carlo: Whether to run Monte Carlo simulation
        include_taxes: Whether to calculate taxes
        n_simulations: Number of Monte Carlo simulations
    
    Returns:
        Dictionary with comprehensive scenario analysis
    """
    logger.info(f"Generating comprehensive report for scenario: {scenario.name}")
    
    report = {
        "scenario_name": scenario.name,
        "scenario_description": scenario.description,
        "parameters": {
            "initial_portfolio": scenario.initial_portfolio,
            "annual_expenses": scenario.annual_expenses,
            "retirement_age": scenario.retirement_age,
            "plan_to_age": scenario.plan_to_age,
            "inflation_rate": scenario.inflation_rate,
        },
        "life_events": [
            {
                "name": event.name,
                "type": event.event_type.value,
                "start_age": event.start_age,
                "end_age": event.end_age,
            }
            for event in scenario.life_events
        ],
    }
    
    # Monte Carlo analysis
    if include_monte_carlo:
        try:
            mc_result = run_scenario_monte_carlo(scenario, n_simulations)
            report["monte_carlo"] = {
                "success_probability": mc_result.success_probability,
                "median_final_portfolio": mc_result.median_final_portfolio,
                "p10_final_portfolio": mc_result.p10_final_portfolio,
                "p90_final_portfolio": mc_result.p90_final_portfolio,
                "n_simulations": n_simulations,
            }
        except Exception as e:
            logger.error(f"Monte Carlo analysis failed: {e}")
            report["monte_carlo"] = {"error": str(e)}
    
    # Tax analysis
    if include_taxes:
        try:
            tax_analysis = calculate_scenario_taxes(scenario)
            report["taxes"] = {
                "total_taxes": tax_analysis["total_taxes"],
                "average_effective_rate": tax_analysis["average_effective_rate"],
            }
        except Exception as e:
            logger.error(f"Tax analysis failed: {e}")
            report["taxes"] = {"error": str(e)}
    
    logger.info(f"Report generation complete for scenario: {scenario.name}")
    
    return report


def compare_scenarios_comprehensive(
    scenarios: list[Scenario],
    n_simulations: int = 5_000,
) -> dict[str, Any]:
    """
    Generate comprehensive comparison of multiple scenarios.
    
    Args:
        scenarios: List of scenarios to compare
        n_simulations: Number of Monte Carlo simulations per scenario
    
    Returns:
        Dictionary with comprehensive comparison
    """
    logger.info(f"Generating comprehensive comparison for {len(scenarios)} scenarios")
    
    comparison = {
        "scenarios": [],
        "summary": {},
    }
    
    # Generate report for each scenario
    for scenario in scenarios:
        report = generate_scenario_report(
            scenario,
            include_monte_carlo=True,
            include_taxes=True,
            n_simulations=n_simulations,
        )
        comparison["scenarios"].append(report)
    
    # Generate summary comparison
    if all("monte_carlo" in s and "error" not in s["monte_carlo"] for s in comparison["scenarios"]):
        success_rates = [s["monte_carlo"]["success_probability"] for s in comparison["scenarios"]]
        comparison["summary"]["best_success_rate"] = max(success_rates)
        comparison["summary"]["worst_success_rate"] = min(success_rates)
        comparison["summary"]["avg_success_rate"] = sum(success_rates) / len(success_rates)
    
    logger.info("Comprehensive comparison complete")
    
    return comparison


# Made with Bob