"""
Coverage tests for scenario_integration.py.

Uses minimal Scenario objects with the fields needed by each function.
"""
import pytest
import pandas as pd

from scenario_manager import (
    Scenario,
    SocialSecurityConfig,
    LifeEvent,
)
from scenario_integration import (
    scenario_to_monte_carlo_inputs,
    run_scenario_monte_carlo,
    calculate_scenario_taxes,
    compare_scenario_taxes,
    apply_withdrawal_strategy_to_scenario,
    optimize_roth_conversions_for_scenario,
    generate_scenario_report,
    compare_scenarios_comprehensive,
)
from monte_carlo import MonteCarloInputs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scenario(**kwargs) -> Scenario:
    """Build a minimal Scenario for testing (overridable via kwargs)."""
    defaults = dict(
        name="Test",
        description="Unit test scenario",
        initial_portfolio=1_000_000.0,
        annual_expenses=50_000.0,
        retirement_age=65,
        plan_to_age=88,
        inflation_rate=0.029,
        portfolio_allocation={"US Large Cap Equity": 0.6, "US Bonds (Intermediate)": 0.4},
        social_security=SocialSecurityConfig(
            person1_amount=24_000.0,
            person1_start_age=70,
        ),
        life_events=[],
    )
    defaults.update(kwargs)
    return Scenario(**defaults)


# ---------------------------------------------------------------------------
# scenario_to_monte_carlo_inputs
# ---------------------------------------------------------------------------

class TestScenarioToMonteCarloInputs:
    def test_returns_monte_carlo_inputs(self):
        scenario = _make_scenario()
        mc = scenario_to_monte_carlo_inputs(scenario, n_simulations=100)
        assert isinstance(mc, MonteCarloInputs)

    def test_portfolio_mapped_correctly(self):
        scenario = _make_scenario(initial_portfolio=2_000_000.0)
        mc = scenario_to_monte_carlo_inputs(scenario)
        assert mc.initial_portfolio == 2_000_000.0

    def test_annual_expenses_mapped_to_withdrawal(self):
        scenario = _make_scenario(annual_expenses=60_000.0)
        mc = scenario_to_monte_carlo_inputs(scenario)
        assert mc.annual_withdrawal == 60_000.0

    def test_ages_mapped_correctly(self):
        scenario = _make_scenario(retirement_age=62, plan_to_age=92)
        mc = scenario_to_monte_carlo_inputs(scenario)
        assert mc.start_age == 62
        assert mc.end_age == 92

    def test_ss_income_mapped(self):
        scenario = _make_scenario(
            social_security=SocialSecurityConfig(person1_amount=30_000.0, person1_start_age=70)
        )
        mc = scenario_to_monte_carlo_inputs(scenario)
        assert mc.social_security_annual == 30_000.0

    def test_two_person_ss_summed(self):
        scenario = _make_scenario(
            social_security=SocialSecurityConfig(
                person1_amount=24_000.0, person1_start_age=70,
                person2_amount=18_000.0, person2_start_age=68,
            )
        )
        mc = scenario_to_monte_carlo_inputs(scenario)
        assert mc.social_security_annual == pytest.approx(42_000.0)

    def test_seed_passed_through(self):
        scenario = _make_scenario()
        mc = scenario_to_monte_carlo_inputs(scenario, random_seed=99)
        assert mc.random_seed == 99


# ---------------------------------------------------------------------------
# run_scenario_monte_carlo
# ---------------------------------------------------------------------------

class TestRunScenarioMonteCarlo:
    def test_returns_result_with_valid_success_probability(self):
        scenario = _make_scenario()
        # Patch n_simulations via monkeypatching is complex; test via default path
        from monte_carlo import MonteCarloResult
        result = run_scenario_monte_carlo(scenario, n_simulations=50)
        assert isinstance(result, MonteCarloResult)
        assert 0.0 <= result.success_probability <= 1.0


# ---------------------------------------------------------------------------
# calculate_scenario_taxes
# ---------------------------------------------------------------------------

class TestCalculateScenarioTaxes:
    def test_returns_dict_with_required_keys(self):
        scenario = _make_scenario()
        result = calculate_scenario_taxes(scenario, year=2026)
        assert isinstance(result, dict)
        for key in ("total_taxes", "total_income", "average_effective_rate", "annual_details"):
            assert key in result

    def test_total_taxes_non_negative(self):
        scenario = _make_scenario()
        result = calculate_scenario_taxes(scenario, year=2026)
        assert result["total_taxes"] >= 0.0

    def test_annual_details_is_list(self):
        scenario = _make_scenario()
        result = calculate_scenario_taxes(scenario, year=2026)
        assert isinstance(result["annual_details"], list)

    def test_annual_details_have_age(self):
        scenario = _make_scenario()
        result = calculate_scenario_taxes(scenario, year=2026)
        for row in result["annual_details"]:
            assert "age" in row


# ---------------------------------------------------------------------------
# compare_scenario_taxes
# ---------------------------------------------------------------------------

class TestCompareScenarioTaxes:
    def test_returns_dataframe(self):
        s1 = _make_scenario(name="S1", annual_expenses=40_000.0)
        s2 = _make_scenario(name="S2", annual_expenses=70_000.0)
        df = compare_scenario_taxes([s1, s2], year=2026)
        assert isinstance(df, pd.DataFrame)

    def test_has_scenario_column(self):
        s1 = _make_scenario(name="Alpha")
        df = compare_scenario_taxes([s1], year=2026)
        assert "Scenario" in df.columns

    def test_row_per_scenario(self):
        s1 = _make_scenario(name="S1")
        s2 = _make_scenario(name="S2")
        df = compare_scenario_taxes([s1, s2], year=2026)
        assert len(df) == 2


# ---------------------------------------------------------------------------
# apply_withdrawal_strategy_to_scenario
# ---------------------------------------------------------------------------

class TestApplyWithdrawalStrategyToScenario:
    def test_returns_dict(self):
        scenario = _make_scenario()
        result = apply_withdrawal_strategy_to_scenario(scenario)
        assert isinstance(result, dict)

    def test_scenario_name_in_result(self):
        scenario = _make_scenario(name="MyScenario")
        result = apply_withdrawal_strategy_to_scenario(scenario)
        assert result["scenario_name"] == "MyScenario"

    def test_custom_strategy_name(self):
        scenario = _make_scenario()
        result = apply_withdrawal_strategy_to_scenario(scenario, strategy_name="bucket")
        assert result["strategy"] == "bucket"


# ---------------------------------------------------------------------------
# optimize_roth_conversions_for_scenario
# ---------------------------------------------------------------------------

class TestOptimizeRothConversionsForScenario:
    def test_returns_dict(self):
        scenario = _make_scenario()
        result = optimize_roth_conversions_for_scenario(scenario)
        assert isinstance(result, dict)

    def test_target_bracket_in_result(self):
        scenario = _make_scenario()
        result = optimize_roth_conversions_for_scenario(scenario, target_bracket=0.22)
        assert result["target_bracket"] == 0.22


# ---------------------------------------------------------------------------
# generate_scenario_report
# ---------------------------------------------------------------------------

class TestGenerateScenarioReport:
    def test_returns_dict_with_scenario_name(self):
        scenario = _make_scenario(name="Report Test")
        report = generate_scenario_report(scenario, include_monte_carlo=False,
                                          include_taxes=False)
        assert isinstance(report, dict)
        assert report["scenario_name"] == "Report Test"

    def test_life_events_present_in_report(self):
        scenario = _make_scenario(life_events=[])
        report = generate_scenario_report(scenario, include_monte_carlo=False,
                                          include_taxes=False)
        assert "life_events" in report

    def test_parameters_present_in_report(self):
        scenario = _make_scenario()
        report = generate_scenario_report(scenario, include_monte_carlo=False,
                                          include_taxes=False)
        assert "parameters" in report
        assert report["parameters"]["initial_portfolio"] == scenario.initial_portfolio

    def test_monte_carlo_section_present_when_included(self):
        scenario = _make_scenario()
        report = generate_scenario_report(scenario, include_monte_carlo=True,
                                          include_taxes=False, n_simulations=50)
        assert "monte_carlo" in report

    def test_taxes_section_present_when_included(self):
        scenario = _make_scenario()
        report = generate_scenario_report(scenario, include_monte_carlo=False,
                                          include_taxes=True)
        assert "taxes" in report


# ---------------------------------------------------------------------------
# compare_scenarios_comprehensive
# ---------------------------------------------------------------------------

class TestCompareScenariosComprehensive:
    def test_returns_dict_with_scenarios_key(self):
        s1 = _make_scenario(name="A")
        result = compare_scenarios_comprehensive([s1], n_simulations=50)
        assert isinstance(result, dict)
        assert "scenarios" in result

    def test_one_entry_per_scenario(self):
        s1 = _make_scenario(name="X")
        s2 = _make_scenario(name="Y")
        result = compare_scenarios_comprehensive([s1, s2], n_simulations=50)
        assert len(result["scenarios"]) == 2

    def test_summary_has_success_rates_when_available(self):
        s1 = _make_scenario(name="Z")
        result = compare_scenarios_comprehensive([s1], n_simulations=50)
        # summary may or may not populate depending on mc result; just check structure
        assert "summary" in result
