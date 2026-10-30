"""Unit tests for jobs manager and monte_carlo_service."""
from __future__ import annotations

import time
import pytest

from app.services import jobs, monte_carlo_service


@pytest.fixture(autouse=True)
def clean_jobs():
    jobs.clear_all_jobs()
    yield
    jobs.clear_all_jobs()


# ---------------------------------------------------------------------------
# Jobs Manager Tests
# ---------------------------------------------------------------------------

def test_job_lifecycle_success():
    def dummy_worker(progress_cb):
        progress_cb(25, "Quarter way")
        time.sleep(0.05)
        progress_cb(75, "Almost done")
        return {"data": 123}

    job_id = jobs.submit_job("test_task", dummy_worker)
    assert job_id is not None

    # Wait for completion
    for _ in range(20):
        info = jobs.get_job(job_id)
        assert info is not None
        if info["status"] == "completed":
            break
        time.sleep(0.02)

    info = jobs.get_job(job_id)
    assert info is not None
    assert info["status"] == "completed"
    assert info["progress"] == 100
    assert info["result"] == {"data": 123}
    assert info["error"] is None


def test_job_lifecycle_failure():
    def failing_worker(progress_cb):
        progress_cb(10, "Starting")
        raise RuntimeError("Something exploded")

    job_id = jobs.submit_job("failing_task", failing_worker)

    for _ in range(20):
        info = jobs.get_job(job_id)
        if info and info["status"] == "failed":
            break
        time.sleep(0.02)

    info = jobs.get_job(job_id)
    assert info is not None
    assert info["status"] == "failed"
    assert "Something exploded" in (info["error"] or "")


def test_get_nonexistent_job():
    assert jobs.get_job("non-existent-uuid") is None


# ---------------------------------------------------------------------------
# Monte Carlo Service Tests
# ---------------------------------------------------------------------------

def test_monte_carlo_meta():
    meta = monte_carlo_service.get_monte_carlo_meta()
    assert "portfolio_presets" in meta
    assert "Moderate (70/30)" in meta["portfolio_presets"]
    assert "stress_scenarios" in meta
    assert "2008 Financial Crisis" in meta["stress_scenarios"]
    assert "longevity_scenarios" in meta


def test_monte_carlo_defaults():
    defs = monte_carlo_service.get_monte_carlo_defaults()
    assert defs["portfolio"] >= 10_000
    assert defs["withdrawal"] >= 1_000
    assert defs["start_age"] < defs["end_age"]
    assert defs["allocation"] in monte_carlo_service.PORTFOLIO_PRESETS


def test_parse_mc_inputs_validation():
    # Valid
    valid_data = {
        "portfolio": 1_000_000,
        "withdrawal": 50_000,
        "start_age": 60,
        "end_age": 90,
        "ss_annual": 30_000,
        "ss_start_age": 67,
        "inflation_pct": 2.5,
        "allocation": "Moderate (70/30)",
        "n_simulations": 500,
    }
    inputs = monte_carlo_service.parse_mc_inputs(valid_data)
    assert inputs.initial_portfolio == 1_000_000
    assert inputs.annual_withdrawal == 50_000
    assert inputs.start_age == 60
    assert inputs.end_age == 90
    assert inputs.inflation_rate == 0.025

    # Invalid portfolio
    with pytest.raises(ValueError, match="at least \\$10,000"):
        monte_carlo_service.parse_mc_inputs({**valid_data, "portfolio": 5000})

    # Invalid withdrawal
    with pytest.raises(ValueError, match="at least \\$1,000"):
        monte_carlo_service.parse_mc_inputs({**valid_data, "withdrawal": 100})

    # End age <= start age
    with pytest.raises(ValueError, match="greater than retirement age"):
        monte_carlo_service.parse_mc_inputs({**valid_data, "start_age": 75, "end_age": 72})

    # Unknown allocation
    with pytest.raises(ValueError, match="Unknown allocation preset"):
        monte_carlo_service.parse_mc_inputs({**valid_data, "allocation": "Crypto Only"})

    # Bad inflation
    with pytest.raises(ValueError, match="Inflation rate must be between"):
        monte_carlo_service.parse_mc_inputs({**valid_data, "inflation_pct": 25.0})


def test_run_simulation_job():
    progress_updates = []

    def mock_cb(pct, msg=""):
        progress_updates.append((pct, msg))

    inputs_dict = {
        "portfolio": 1_200_000,
        "withdrawal": 60_000,
        "start_age": 62,
        "end_age": 85,
        "ss_annual": 25_000,
        "ss_start_age": 70,
        "inflation_pct": 2.5,
        "allocation": "Moderate (70/30)",
        "n_simulations": 300,
    }

    res = monte_carlo_service.run_simulation_job(inputs_dict, mock_cb)
    assert "success_probability" in res
    assert 0.0 <= res["success_probability"] <= 1.0
    assert "median_final_portfolio" in res
    assert "p10_final_portfolio" in res
    assert "fan_chart" in res
    assert len(res["fan_chart"]) > 0
    assert "safe_withdrawal_rates" in res
    assert "sequence_risk" in res
    assert len(progress_updates) >= 4
    assert progress_updates[-1][0] == 100


def test_run_stress_tests_job():
    progress_updates = []

    def mock_cb(pct, msg=""):
        progress_updates.append((pct, msg))

    inputs_dict = {
        "portfolio": 1_000_000,
        "withdrawal": 50_000,
        "start_age": 62,
        "end_age": 85,
        "ss_annual": 20_000,
        "ss_start_age": 70,
        "inflation_pct": 2.5,
        "allocation": "Moderate (70/30)",
        "n_simulations": 200,
    }

    res = monte_carlo_service.run_stress_tests_job(
        inputs_dict,
        ["2008 Financial Crisis", "1970s Stagflation"],
        mock_cb,
    )
    assert "results" in res
    assert len(res["results"]) == 2
    assert res["results"][0]["scenario_name"] == "2008 Financial Crisis"
    assert "ages" in res
    assert len(res["ages"]) == (85 - 62 + 1)


def test_run_longevity_job():
    progress_updates = []

    def mock_cb(pct, msg=""):
        progress_updates.append((pct, msg))

    inputs_dict = {
        "portfolio": 1_000_000,
        "withdrawal": 50_000,
        "start_age": 62,
        "end_age": 85,
        "ss_annual": 20_000,
        "ss_start_age": 70,
        "inflation_pct": 2.5,
        "allocation": "Moderate (70/30)",
        "n_simulations": 200,
    }

    res = monte_carlo_service.run_longevity_job(
        inputs_dict,
        ["Average (age 85)", "Long-Lived (age 95)"],
        mock_cb,
    )
    assert "summary" in res
    assert len(res["summary"]) == 2
    assert "paths" in res
    assert "Average (age 85)" in res["paths"]


def test_run_heatmap_job():
    progress_updates = []

    def mock_cb(pct, msg=""):
        progress_updates.append((pct, msg))

    inputs_dict = {
        "portfolio": 1_000_000,
        "withdrawal": 50_000,
        "start_age": 62,
        "end_age": 80,
        "ss_annual": 20_000,
        "ss_start_age": 70,
        "inflation_pct": 2.5,
        "allocation": "Moderate (70/30)",
        "n_simulations": 100,
    }

    res = monte_carlo_service.run_heatmap_job(
        inputs_dict,
        base_withdrawal=50_000,
        n_sims_cell=100,
        progress_cb=mock_cb,
    )
    assert "columns" in res
    assert "index" in res
    assert "values" in res
    assert len(res["values"]) > 0


def test_run_comparison_job():
    progress_updates = []

    def mock_cb(pct, msg=""):
        progress_updates.append((pct, msg))

    inputs_dict = {
        "portfolio": 1_000_000,
        "withdrawal": 50_000,
        "start_age": 62,
        "end_age": 85,
        "ss_annual": 20_000,
        "ss_start_age": 70,
        "inflation_pct": 2.5,
        "allocation": "Moderate (70/30)",
        "n_simulations": 100,
    }

    res = monte_carlo_service.run_comparison_job(
        inputs_dict,
        stress_scenarios=["2008 Financial Crisis"],
        longevity_scenarios=["Average (age 85)"],
        progress_cb=mock_cb,
    )
    assert "table" in res
    assert len(res["table"]) >= 2
    assert "bar_data" in res


def test_export_report_csv():
    inputs_dict = {
        "portfolio": 1_000_000,
        "withdrawal": 50_000,
        "start_age": 62,
        "end_age": 85,
        "ss_annual": 20_000,
        "ss_start_age": 70,
        "inflation_pct": 2.5,
        "allocation": "Moderate (70/30)",
        "n_simulations": 100,
    }

    csv_bytes = monte_carlo_service.export_report_csv(inputs_dict, include_stress=True, include_longevity=True)
    assert isinstance(csv_bytes, bytes)
    text = csv_bytes.decode("utf-8")
    assert "MONTE CARLO SIMULATION REPORT" in text
    assert "BASELINE SUMMARY" in text
    assert "Initial Portfolio,$1,000,000" in text
