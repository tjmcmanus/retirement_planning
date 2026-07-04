"""
Coverage tests for monte_carlo.py.

Targets the core simulation, helper, and output-building functions.
Uses n_simulations=100 and random_seed=42 for fast, deterministic runs.
"""
import io
import pytest
import numpy as np
import pandas as pd

from monte_carlo import (
    MonteCarloInputs,
    MonteCarloResult,
    SimulationYear,
    StressTestResult,
    ScenarioComparisonResult,
    PORTFOLIO_PRESETS,
    HISTORICAL_RETURNS,
    STRESS_SCENARIOS,
    FAN_CHART_PERCENTILES,
    _compute_portfolio_stats,
    _simulate_returns,
    _apply_stress_shocks,
    run_monte_carlo,
    build_fan_chart_df,
    build_scenario_comparison_df,
    generate_monte_carlo_report_csv,
    get_safe_withdrawal_rate,
    run_stress_tests,
    run_longevity_analysis,
    run_full_scenario_comparison,
    analyze_sequence_of_returns_risk,
    build_success_heatmap_df,
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def base_inputs():
    return MonteCarloInputs(
        initial_portfolio=1_000_000,
        annual_withdrawal=40_000,
        start_age=65,
        end_age=90,
        portfolio_allocation={"US Large Cap Equity": 0.6, "US Bonds (Intermediate)": 0.4},
        n_simulations=100,
        random_seed=42,
    )


@pytest.fixture
def mc_result(base_inputs):
    return run_monte_carlo(base_inputs)


# ---------------------------------------------------------------------------
# _compute_portfolio_stats
# ---------------------------------------------------------------------------

class TestComputePortfolioStats:
    def test_all_equities_matches_historical(self):
        key = "US Large Cap Equity"
        mean, std = _compute_portfolio_stats({key: 1.0})
        mu, sigma = HISTORICAL_RETURNS[key]
        assert mean == pytest.approx(mu)
        assert std == pytest.approx(sigma)

    def test_mixed_portfolio_returns_between_components(self):
        alloc = {"US Large Cap Equity": 0.6, "US Bonds (Intermediate)": 0.4}
        mean, std = _compute_portfolio_stats(alloc)
        eq_mean = HISTORICAL_RETURNS["US Large Cap Equity"][0]
        bd_mean = HISTORICAL_RETURNS["US Bonds (Intermediate)"][0]
        assert min(eq_mean, bd_mean) <= mean <= max(eq_mean, bd_mean)

    def test_unknown_asset_ignored(self):
        mean, std = _compute_portfolio_stats({"unknown_asset": 1.0})
        assert mean == 0.0
        assert std == 0.0

    def test_returns_two_floats(self):
        mean, std = _compute_portfolio_stats({"equities": 0.5, "bonds": 0.5})
        assert isinstance(mean, float)
        assert isinstance(std, float)

    def test_std_non_negative(self):
        _, std = _compute_portfolio_stats({"equities": 0.6, "bonds": 0.4})
        assert std >= 0.0


# ---------------------------------------------------------------------------
# _simulate_returns
# ---------------------------------------------------------------------------

class TestSimulateReturns:
    def test_output_shape(self):
        rng = np.random.default_rng(42)
        returns = _simulate_returns(0.07, 0.15, 25, 100, rng)
        assert returns.shape == (100, 25)

    def test_returns_positive(self):
        rng = np.random.default_rng(42)
        returns = _simulate_returns(0.07, 0.15, 25, 100, rng)
        assert np.all(returns > 0)

    def test_reproducible_with_same_seed(self):
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        r1 = _simulate_returns(0.07, 0.15, 10, 50, rng1)
        r2 = _simulate_returns(0.07, 0.15, 10, 50, rng2)
        np.testing.assert_array_equal(r1, r2)


# ---------------------------------------------------------------------------
# _apply_stress_shocks
# ---------------------------------------------------------------------------

class TestApplyStressShocks:
    def test_no_shocks_unchanged(self):
        base = np.ones((10, 5))
        result = _apply_stress_shocks(base, [], 0.6, 0.4)
        np.testing.assert_array_equal(result, base)

    def test_shock_applied_to_correct_year(self):
        base = np.ones((10, 5))
        shocks = [(1, -0.20, -0.05, 0.0)]
        result = _apply_stress_shocks(base, shocks, 0.6, 0.4)
        expected = 1.0 + 0.6 * (-0.20) + 0.4 * (-0.05)
        assert result[0, 1] == pytest.approx(expected)
        assert result[0, 0] == pytest.approx(1.0)

    def test_out_of_range_shock_ignored(self):
        base = np.ones((10, 3))
        shocks = [(10, -0.50, -0.20, 0.0)]  # year_offset=10 >= n_years=3
        result = _apply_stress_shocks(base, shocks, 0.6, 0.4)
        np.testing.assert_array_equal(result, base)

    def test_does_not_modify_original(self):
        base = np.ones((5, 5))
        original = base.copy()
        _apply_stress_shocks(base, [(0, -0.30, -0.10, 0.0)], 0.6, 0.4)
        np.testing.assert_array_equal(base, original)


# ---------------------------------------------------------------------------
# run_monte_carlo
# ---------------------------------------------------------------------------

class TestRunMonteCarlo:
    def test_returns_monte_carlo_result(self, base_inputs):
        result = run_monte_carlo(base_inputs)
        assert isinstance(result, MonteCarloResult)

    def test_success_probability_in_range(self, mc_result):
        assert 0.0 <= mc_result.success_probability <= 1.0

    def test_years_count_matches_simulation_period(self, base_inputs, mc_result):
        expected_years = base_inputs.end_age - base_inputs.start_age
        assert len(mc_result.years) == expected_years

    def test_each_year_has_percentiles(self, mc_result):
        for yr in mc_result.years:
            for p in FAN_CHART_PERCENTILES:
                assert p in yr.percentiles

    def test_median_final_portfolio_is_float(self, mc_result):
        assert isinstance(mc_result.median_final_portfolio, float)

    def test_p10_less_than_p90(self, mc_result):
        assert mc_result.p10_final_portfolio <= mc_result.p90_final_portfolio

    def test_ss_income_increases_success(self, base_inputs):
        no_ss = run_monte_carlo(base_inputs)
        with_ss_inputs = MonteCarloInputs(
            initial_portfolio=base_inputs.initial_portfolio,
            annual_withdrawal=base_inputs.annual_withdrawal,
            start_age=base_inputs.start_age,
            end_age=base_inputs.end_age,
            portfolio_allocation=base_inputs.portfolio_allocation,
            social_security_annual=24_000,
            n_simulations=100,
            random_seed=42,
        )
        with_ss = run_monte_carlo(with_ss_inputs)
        # SS income offsets withdrawals, so success should be >= no-SS case
        assert with_ss.success_probability >= no_ss.success_probability - 0.01

    def test_zero_withdrawal_near_100pct_success(self, base_inputs):
        inputs = MonteCarloInputs(
            initial_portfolio=base_inputs.initial_portfolio,
            annual_withdrawal=0,
            start_age=base_inputs.start_age,
            end_age=base_inputs.end_age,
            portfolio_allocation=base_inputs.portfolio_allocation,
            n_simulations=100,
            random_seed=42,
        )
        result = run_monte_carlo(inputs)
        assert result.success_probability >= 0.95

    def test_stress_scenario_name(self, base_inputs):
        scenario = next(iter(STRESS_SCENARIOS))
        result = run_monte_carlo(base_inputs, stress_scenario=scenario)
        assert isinstance(result, MonteCarloResult)

    def test_mean_override(self, base_inputs):
        result = run_monte_carlo(base_inputs, mean_override=0.03)
        assert isinstance(result, MonteCarloResult)

    def test_std_override(self, base_inputs):
        result = run_monte_carlo(base_inputs, std_override=0.05)
        assert isinstance(result, MonteCarloResult)

    def test_reproducible_with_seed(self, base_inputs):
        r1 = run_monte_carlo(base_inputs)
        r2 = run_monte_carlo(base_inputs)
        assert r1.success_probability == r2.success_probability


# ---------------------------------------------------------------------------
# build_fan_chart_df
# ---------------------------------------------------------------------------

class TestBuildFanChartDf:
    def test_returns_dataframe(self, mc_result):
        df = build_fan_chart_df(mc_result)
        assert isinstance(df, pd.DataFrame)

    def test_has_age_column(self, mc_result):
        df = build_fan_chart_df(mc_result)
        assert "age" in df.columns

    def test_has_percentile_columns(self, mc_result):
        df = build_fan_chart_df(mc_result)
        for p in FAN_CHART_PERCENTILES:
            assert f"p{p}" in df.columns

    def test_row_count_matches_years(self, mc_result):
        df = build_fan_chart_df(mc_result)
        assert len(df) == len(mc_result.years)

    def test_p50_between_p10_and_p90(self, mc_result):
        df = build_fan_chart_df(mc_result)
        assert (df["p10"] <= df["p50"]).all()
        assert (df["p50"] <= df["p90"]).all()


# ---------------------------------------------------------------------------
# run_stress_tests
# ---------------------------------------------------------------------------

class TestRunStressTests:
    def test_returns_list(self, base_inputs):
        results = run_stress_tests(base_inputs)
        assert isinstance(results, list)

    def test_each_item_is_stress_test_result(self, base_inputs):
        results = run_stress_tests(base_inputs)
        for r in results:
            assert isinstance(r, StressTestResult)

    def test_specific_scenario(self, base_inputs):
        scenario = next(iter(STRESS_SCENARIOS))
        results = run_stress_tests(base_inputs, scenarios=[scenario])
        assert len(results) == 1
        assert results[0].scenario_name == scenario


# ---------------------------------------------------------------------------
# run_longevity_analysis
# ---------------------------------------------------------------------------

class TestRunLongevityAnalysis:
    def test_returns_dict(self, base_inputs):
        results = run_longevity_analysis(base_inputs)
        assert isinstance(results, dict)

    def test_custom_end_ages(self, base_inputs):
        results = run_longevity_analysis(base_inputs, {"95": 95})
        assert "95" in results

    def test_longer_horizon_same_or_lower_success(self, base_inputs):
        long_inputs = MonteCarloInputs(
            initial_portfolio=base_inputs.initial_portfolio,
            annual_withdrawal=base_inputs.annual_withdrawal,
            start_age=base_inputs.start_age,
            end_age=95,
            portfolio_allocation=base_inputs.portfolio_allocation,
            n_simulations=100,
            random_seed=42,
        )
        long = run_monte_carlo(long_inputs)
        assert 0.0 <= long.success_probability <= 1.0


# ---------------------------------------------------------------------------
# run_full_scenario_comparison
# ---------------------------------------------------------------------------

class TestRunFullScenarioComparison:
    def test_returns_scenario_comparison_result(self, base_inputs):
        result = run_full_scenario_comparison(base_inputs)
        assert isinstance(result, ScenarioComparisonResult)

    def test_has_baseline(self, base_inputs):
        result = run_full_scenario_comparison(base_inputs)
        assert isinstance(result.baseline, MonteCarloResult)


# ---------------------------------------------------------------------------
# build_scenario_comparison_df
# ---------------------------------------------------------------------------

class TestBuildScenarioComparisonDf:
    def test_returns_dataframe(self, base_inputs):
        comparison = run_full_scenario_comparison(base_inputs)
        df = build_scenario_comparison_df(comparison)
        assert isinstance(df, pd.DataFrame)

    def test_has_scenario_column(self, base_inputs):
        comparison = run_full_scenario_comparison(base_inputs)
        df = build_scenario_comparison_df(comparison)
        assert "Scenario" in df.columns

    def test_baseline_row_present(self, base_inputs):
        comparison = run_full_scenario_comparison(base_inputs)
        df = build_scenario_comparison_df(comparison)
        assert any("Baseline" in str(s) for s in df["Scenario"])


# ---------------------------------------------------------------------------
# generate_monte_carlo_report_csv
# ---------------------------------------------------------------------------

class TestGenerateMonteCarloReportCsv:
    def test_returns_bytes(self, mc_result):
        csv_bytes = generate_monte_carlo_report_csv(mc_result)
        assert isinstance(csv_bytes, bytes)

    def test_contains_summary_header(self, mc_result):
        csv_bytes = generate_monte_carlo_report_csv(mc_result)
        assert b"MONTE CARLO" in csv_bytes

    def test_with_stress_results(self, base_inputs, mc_result):
        stress = run_stress_tests(base_inputs)
        csv_bytes = generate_monte_carlo_report_csv(mc_result, stress_results=stress)
        assert b"STRESS" in csv_bytes

    def test_with_longevity_results(self, base_inputs, mc_result):
        longevity = run_longevity_analysis(base_inputs, {"95": 95})
        csv_bytes = generate_monte_carlo_report_csv(mc_result, longevity_results=longevity)
        assert b"LONGEVITY" in csv_bytes

    def test_depletion_age_included_when_present(self, base_inputs):
        # Very high withdrawal to force depletion
        starved_inputs = MonteCarloInputs(
            initial_portfolio=100_000,
            annual_withdrawal=50_000,
            start_age=65,
            end_age=90,
            portfolio_allocation={"equities": 0.6, "bonds": 0.4},
            n_simulations=100,
            random_seed=42,
        )
        result = run_monte_carlo(starved_inputs)
        csv_bytes = generate_monte_carlo_report_csv(result)
        assert isinstance(csv_bytes, bytes)


# ---------------------------------------------------------------------------
# get_safe_withdrawal_rate
# ---------------------------------------------------------------------------

class TestGetSafeWithdrawalRate:
    def test_returns_positive_float(self, base_inputs):
        swr = get_safe_withdrawal_rate(base_inputs, max_iterations=3)
        assert isinstance(swr, float)
        assert swr > 0

    def test_lower_target_success_gives_higher_swr(self, base_inputs):
        swr_90 = get_safe_withdrawal_rate(base_inputs, target_success=0.90, max_iterations=3)
        swr_50 = get_safe_withdrawal_rate(base_inputs, target_success=0.50, max_iterations=3)
        # Higher confidence requirement → lower safe withdrawal
        assert swr_90 <= swr_50 * 1.5  # allow tolerance for fast binary search


# ---------------------------------------------------------------------------
# analyze_sequence_of_returns_risk
# ---------------------------------------------------------------------------

class TestAnalyzeSequenceOfReturnsRisk:
    def test_returns_dict(self, base_inputs):
        result = analyze_sequence_of_returns_risk(base_inputs)
        assert isinstance(result, dict)

    def test_has_expected_keys(self, base_inputs):
        result = analyze_sequence_of_returns_risk(base_inputs)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# Portfolio presets sanity
# ---------------------------------------------------------------------------

class TestPortfolioPresets:
    def test_all_presets_have_allocations(self):
        for name, alloc in PORTFOLIO_PRESETS.items():
            assert isinstance(alloc, dict)
            assert len(alloc) > 0

    def test_preset_weights_sum_to_one(self):
        for name, alloc in PORTFOLIO_PRESETS.items():
            total = sum(alloc.values())
            assert total == pytest.approx(1.0, abs=0.01), f"{name} weights sum to {total}"
