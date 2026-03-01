"""
monte_carlo.py

Monte Carlo Simulation Engine for Retirement Planning

Implements:
  Core Simulation:
    - 10,000+ iteration Monte Carlo analysis
    - Market volatility modeled from historical return distributions
    - Sequence-of-returns risk analysis
    - Probability of success metrics (90% confidence intervals)

  Scenario Analysis:
    - Best case / worst case / median outcome projections
    - Stress testing (2008 crash, stagflation, dot-com bust, etc.)
    - Longevity risk modeling (living to 95, 100, 105)
    - Inflation shock scenarios

  Visualization Support:
    - Fan chart data (percentile bands)
    - Success probability by year
    - Scenario comparison DataFrames
    - Downloadable CSV report generation

Reuses:
    - PortfolioBalances from strategy.py
    - Historical return distributions calibrated to US equity/bond data

Author: IBM Bob
Date: 2026-03-01
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_level = logging.getLevelName(os.getenv("LOG_LEVEL", "WARNING"))
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ===========================================================================
# HISTORICAL RETURN PARAMETERS
# Calibrated to US market data 1926-2024 (Ibbotson/Morningstar SBBI)
# ===========================================================================

# Asset class: (mean annual return, annual std dev)
HISTORICAL_RETURNS: Dict[str, Tuple[float, float]] = {
    "US Large Cap Equity":      (0.1012, 0.1962),   # S&P 500 long-run
    "US Small Cap Equity":      (0.1162, 0.2380),   # Small cap premium
    "International Equity":     (0.0850, 0.1750),   # MSCI EAFE
    "US Bonds (Intermediate)":  (0.0520, 0.0680),   # 10-yr Treasury
    "US Bonds (Short)":         (0.0380, 0.0310),   # 3-yr Treasury
    "Cash / Money Market":      (0.0330, 0.0090),   # T-bills
    "Real Estate (REITs)":      (0.0920, 0.1850),   # NAREIT
    "Inflation (CPI)":          (0.0290, 0.0150),   # CPI long-run
}

# Typical balanced portfolio allocations
PORTFOLIO_PRESETS: Dict[str, Dict[str, float]] = {
    "Aggressive (90/10)": {
        "US Large Cap Equity": 0.60,
        "US Small Cap Equity": 0.15,
        "International Equity": 0.15,
        "US Bonds (Intermediate)": 0.10,
    },
    "Moderate (70/30)": {
        "US Large Cap Equity": 0.45,
        "US Small Cap Equity": 0.10,
        "International Equity": 0.15,
        "US Bonds (Intermediate)": 0.20,
        "US Bonds (Short)": 0.10,
    },
    "Conservative (50/50)": {
        "US Large Cap Equity": 0.30,
        "US Small Cap Equity": 0.05,
        "International Equity": 0.15,
        "US Bonds (Intermediate)": 0.30,
        "US Bonds (Short)": 0.15,
        "Cash / Money Market": 0.05,
    },
    "Income (30/70)": {
        "US Large Cap Equity": 0.20,
        "US Small Cap Equity": 0.05,
        "International Equity": 0.05,
        "US Bonds (Intermediate)": 0.40,
        "US Bonds (Short)": 0.20,
        "Cash / Money Market": 0.10,
    },
}

# Stress scenario: list of (year_offset, equity_shock, bond_shock, inflation_shock)
# year_offset=0 means the shock hits in the first year of retirement
STRESS_SCENARIOS: Dict[str, Dict] = {
    "2008 Financial Crisis": {
        "description": "Global financial crisis. S&P 500 fell 37% in 2008.",
        "shocks": [(0, -0.37, 0.05, 0.04), (1, 0.26, 0.06, 0.02)],
        "mean_override": None,
        "std_override": None,
    },
    "Dot-Com Bust (2000-2002)": {
        "description": "Tech bubble burst. S&P 500 fell ~49% over 3 years.",
        "shocks": [(0, -0.09, 0.08, 0.03), (1, -0.12, 0.10, 0.03), (2, -0.22, 0.12, 0.02)],
        "mean_override": None,
        "std_override": None,
    },
    "1970s Stagflation": {
        "description": "High inflation + low growth. CPI peaked at 14.8% in 1980.",
        "shocks": [],
        "mean_override": 0.04,    # Low real returns
        "std_override": 0.18,
        "inflation_override": 0.09,
    },
    "Lost Decade (Japan-style)": {
        "description": "Prolonged low-return environment. Nikkei lost 80% 1990-2003.",
        "shocks": [],
        "mean_override": 0.02,
        "std_override": 0.15,
        "inflation_override": 0.01,
    },
    "Inflation Shock": {
        "description": "Sudden inflation spike (2022-style). CPI hit 9.1% in June 2022.",
        "shocks": [(0, -0.19, -0.13, 0.09), (1, -0.05, -0.02, 0.06)],
        "mean_override": None,
        "std_override": None,
    },
    "Early Retirement Bear Market": {
        "description": "Severe bear market in the first 3 years of retirement (worst sequence risk).",
        "shocks": [(0, -0.30, 0.02, 0.04), (1, -0.20, 0.03, 0.04), (2, -0.10, 0.04, 0.03)],
        "mean_override": None,
        "std_override": None,
    },
}

# Longevity scenarios
LONGEVITY_SCENARIOS: Dict[str, int] = {
    "Average (age 85)": 85,
    "Above Average (age 90)": 90,
    "Long-Lived (age 95)": 95,
    "Very Long-Lived (age 100)": 100,
    "Exceptional (age 105)": 105,
}

# Percentile bands for fan charts
FAN_CHART_PERCENTILES: List[int] = [5, 10, 25, 50, 75, 90, 95]


# ===========================================================================
# DATA CLASSES
# ===========================================================================

@dataclass
class MonteCarloInputs:
    """Inputs for the Monte Carlo simulation."""
    initial_portfolio: float
    annual_withdrawal: float
    start_age: int
    end_age: int
    portfolio_allocation: Dict[str, float]
    inflation_rate: float = 0.029
    withdrawal_growth_rate: float = 0.029   # Withdrawals grow with inflation
    social_security_annual: float = 0.0
    ss_start_age: int = 70
    additional_income: float = 0.0          # Pension, part-time work, etc.
    n_simulations: int = 10_000
    random_seed: Optional[int] = None


@dataclass
class SimulationYear:
    """Single year result across all simulations."""
    year: int
    age: int
    percentiles: Dict[int, float] = field(default_factory=dict)   # {5: val, 25: val, ...}
    success_rate: float = 0.0    # Fraction of simulations still solvent
    median_portfolio: float = 0.0
    mean_portfolio: float = 0.0


@dataclass
class MonteCarloResult:
    """Full Monte Carlo simulation result."""
    inputs: MonteCarloInputs
    years: List[SimulationYear] = field(default_factory=list)
    success_probability: float = 0.0        # Overall probability of not running out
    median_final_portfolio: float = 0.0
    p10_final_portfolio: float = 0.0        # 10th percentile final value
    p90_final_portfolio: float = 0.0        # 90th percentile final value
    years_to_depletion_p10: Optional[int] = None   # 10th percentile depletion year
    portfolio_paths: Optional[np.ndarray] = None   # Shape: (n_sims, n_years)
    annual_returns_used: Optional[np.ndarray] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class StressTestResult:
    """Result of a single stress scenario."""
    scenario_name: str
    description: str
    success_probability: float
    median_final_portfolio: float
    p10_final_portfolio: float
    years_to_depletion_median: Optional[int]
    portfolio_path_median: List[float] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class ScenarioComparisonResult:
    """Comparison of multiple scenarios."""
    baseline: MonteCarloResult
    stress_tests: List[StressTestResult] = field(default_factory=list)
    longevity_results: Dict[str, MonteCarloResult] = field(default_factory=dict)


# ===========================================================================
# PORTFOLIO RETURN SIMULATION
# ===========================================================================

def _compute_portfolio_stats(
    allocation: Dict[str, float],
) -> Tuple[float, float]:
    """
    Compute blended mean return and standard deviation for a portfolio allocation.

    Uses a simplified diagonal covariance (no cross-asset correlation) for speed.
    For a more accurate model, a full covariance matrix would be used.

    Args:
        allocation: Dict mapping asset class name to weight (weights must sum to ~1.0)

    Returns:
        (mean_return, std_dev) for the blended portfolio
    """
    mean = 0.0
    variance = 0.0
    for asset, weight in allocation.items():
        if asset in HISTORICAL_RETURNS:
            mu, sigma = HISTORICAL_RETURNS[asset]
            mean += weight * mu
            variance += (weight * sigma) ** 2
    return mean, float(np.sqrt(variance))


def _simulate_returns(
    mean: float,
    std: float,
    n_years: int,
    n_sims: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Simulate annual portfolio returns using log-normal distribution.

    Log-normal is used because returns compound multiplicatively and cannot
    go below -100%. The log-normal parameters are derived from the arithmetic
    mean and standard deviation.

    Args:
        mean: Arithmetic mean annual return
        std: Annual standard deviation
        n_years: Number of years to simulate
        n_sims: Number of simulation paths
        rng: NumPy random generator (for reproducibility)

    Returns:
        Array of shape (n_sims, n_years) with annual return multipliers (e.g., 1.07)
    """
    # Convert arithmetic mean/std to log-normal parameters
    sigma2 = np.log(1 + (std / (1 + mean)) ** 2)
    mu_ln = np.log(1 + mean) - 0.5 * sigma2
    sigma_ln = np.sqrt(sigma2)

    # Generate log-normal returns: shape (n_sims, n_years)
    log_returns = rng.normal(mu_ln, sigma_ln, size=(n_sims, n_years))
    return np.exp(log_returns)


def _apply_stress_shocks(
    returns: np.ndarray,
    shocks: List[Tuple[int, float, float, float]],
    equity_weight: float,
    bond_weight: float,
) -> np.ndarray:
    """
    Apply stress scenario shocks to the return matrix.

    Args:
        returns: Shape (n_sims, n_years) return multipliers
        shocks: List of (year_offset, equity_shock, bond_shock, inflation_shock)
        equity_weight: Portfolio equity weight
        bond_weight: Portfolio bond weight

    Returns:
        Modified returns array
    """
    result = returns.copy()
    for year_offset, eq_shock, bd_shock, _inf_shock in shocks:
        if year_offset < result.shape[1]:
            blended_shock = equity_weight * eq_shock + bond_weight * bd_shock
            # Apply shock to ALL simulations for this year (deterministic shock)
            result[:, year_offset] = 1.0 + blended_shock
    return result


# ===========================================================================
# CORE MONTE CARLO ENGINE
# ===========================================================================

def run_monte_carlo(
    inputs: MonteCarloInputs,
    stress_scenario: Optional[str] = None,
    mean_override: Optional[float] = None,
    std_override: Optional[float] = None,
    inflation_override: Optional[float] = None,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for retirement portfolio sustainability.

    Each simulation path:
    1. Starts with initial_portfolio
    2. Each year: portfolio grows by random return, then withdrawal is subtracted
    3. Social Security income reduces the withdrawal need after ss_start_age
    4. Simulation ends when portfolio hits 0 (depleted) or end_age is reached

    Args:
        inputs: MonteCarloInputs with all simulation parameters
        stress_scenario: Optional stress scenario name from STRESS_SCENARIOS
        mean_override: Override portfolio mean return (for stress scenarios)
        std_override: Override portfolio std dev (for stress scenarios)
        inflation_override: Override inflation rate (for stress scenarios)

    Returns:
        MonteCarloResult with full simulation output
    """
    rng = np.random.default_rng(inputs.random_seed)
    n_years = inputs.end_age - inputs.start_age
    n_sims = inputs.n_simulations

    if n_years <= 0:
        return MonteCarloResult(
            inputs=inputs,
            success_probability=1.0,
            notes=["End age must be greater than start age."],
        )

    # Compute portfolio statistics
    port_mean, port_std = _compute_portfolio_stats(inputs.portfolio_allocation)

    # Apply overrides
    if mean_override is not None:
        port_mean = mean_override
    if std_override is not None:
        port_std = std_override
    inflation = inflation_override if inflation_override is not None else inputs.inflation_rate

    logger.debug(
        f"Monte Carlo: {n_sims} sims × {n_years} years, "
        f"mean={port_mean:.2%}, std={port_std:.2%}, inflation={inflation:.2%}"
    )

    # Generate return matrix: shape (n_sims, n_years)
    returns = _simulate_returns(port_mean, port_std, n_years, n_sims, rng)

    # Apply stress scenario shocks
    if stress_scenario and stress_scenario in STRESS_SCENARIOS:
        scenario = STRESS_SCENARIOS[stress_scenario]
        equity_weight = sum(
            w for k, w in inputs.portfolio_allocation.items()
            if "Equity" in k or "REIT" in k
        )
        bond_weight = sum(
            w for k, w in inputs.portfolio_allocation.items()
            if "Bond" in k
        )
        if scenario["shocks"]:
            returns = _apply_stress_shocks(
                returns, scenario["shocks"], equity_weight, bond_weight
            )
        if scenario.get("mean_override") is not None:
            port_mean = scenario["mean_override"]
            port_std = scenario.get("std_override", port_std)
            returns = _simulate_returns(port_mean, port_std, n_years, n_sims, rng)
        if scenario.get("inflation_override") is not None:
            inflation = scenario["inflation_override"]

    # Simulate portfolio paths
    # portfolio_paths[sim, year] = portfolio value at end of year
    portfolio_paths = np.zeros((n_sims, n_years))
    portfolio = np.full(n_sims, float(inputs.initial_portfolio))

    annual_withdrawal = float(inputs.annual_withdrawal)

    for yr in range(n_years):
        age = inputs.start_age + yr

        # Grow portfolio
        portfolio = portfolio * returns[:, yr]

        # Social Security income reduces withdrawal need
        ss_income = float(inputs.social_security_annual) if age >= inputs.ss_start_age else 0.0
        additional = float(inputs.additional_income)

        # Net withdrawal (withdrawal - income sources, floored at 0)
        net_withdrawal = max(0.0, annual_withdrawal - ss_income - additional)

        # Subtract withdrawal (portfolio cannot go below 0)
        portfolio = np.maximum(0.0, portfolio - net_withdrawal)
        portfolio_paths[:, yr] = portfolio

        # Grow withdrawal with inflation
        annual_withdrawal *= (1.0 + inflation)

    # Compute success: simulations where portfolio > 0 at end
    final_portfolios = portfolio_paths[:, -1]
    success_mask = final_portfolios > 0
    success_probability = float(success_mask.mean())

    # Build per-year statistics
    years_list: List[SimulationYear] = []
    for yr in range(n_years):
        age = inputs.start_age + yr
        col = portfolio_paths[:, yr]
        solvent = col > 0
        pcts = {p: float(np.percentile(col, p)) for p in FAN_CHART_PERCENTILES}
        years_list.append(SimulationYear(
            year=inputs.start_age + yr,   # store as age for x-axis
            age=age,
            percentiles=pcts,
            success_rate=float(solvent.mean()),
            median_portfolio=float(np.median(col)),
            mean_portfolio=float(col.mean()),
        ))

    # Years to depletion at 10th percentile
    p10_path = np.percentile(portfolio_paths, 10, axis=0)
    depletion_years = np.where(p10_path <= 0)[0]
    years_to_depletion_p10 = (
        int(depletion_years[0]) + inputs.start_age if len(depletion_years) > 0 else None
    )

    result = MonteCarloResult(
        inputs=inputs,
        years=years_list,
        success_probability=success_probability,
        median_final_portfolio=float(np.median(final_portfolios)),
        p10_final_portfolio=float(np.percentile(final_portfolios, 10)),
        p90_final_portfolio=float(np.percentile(final_portfolios, 90)),
        years_to_depletion_p10=years_to_depletion_p10,
        portfolio_paths=portfolio_paths,
        notes=[
            f"Portfolio mean return: {port_mean:.2%}, std dev: {port_std:.2%}",
            f"Inflation rate: {inflation:.2%}",
            f"Simulations: {n_sims:,}",
            f"Horizon: {n_years} years (age {inputs.start_age}–{inputs.end_age})",
        ],
    )

    if stress_scenario:
        result.notes.insert(0, f"Stress scenario: {stress_scenario}")

    return result


# ===========================================================================
# SEQUENCE-OF-RETURNS RISK ANALYSIS
# ===========================================================================

def analyze_sequence_of_returns_risk(
    inputs: MonteCarloInputs,
    n_worst: int = 100,
) -> Dict:
    """
    Analyze sequence-of-returns risk by comparing early-retirement bear markets.

    Identifies the worst n_worst simulation paths (by first-5-year return) and
    compares their outcomes to the median path.

    Args:
        inputs: MonteCarloInputs
        n_worst: Number of worst-sequence paths to analyze

    Returns:
        Dict with keys: worst_paths_success_rate, median_success_rate,
                        avg_first5yr_return_worst, avg_first5yr_return_median,
                        depletion_age_worst_median, depletion_age_overall_median
    """
    result = run_monte_carlo(inputs)
    if result.portfolio_paths is None:
        return {}

    paths = result.portfolio_paths
    n_sims = paths.shape[0]
    n_years = paths.shape[1]

    # Rank by first-5-year cumulative return (proxy for sequence risk)
    first5 = min(5, n_years)
    # Reconstruct first-5-year returns from portfolio paths
    initial = float(inputs.initial_portfolio)
    first5_returns = paths[:, first5 - 1] / initial if initial > 0 else np.ones(n_sims)

    worst_idx = np.argsort(first5_returns)[:n_worst]
    median_idx = np.argsort(first5_returns)[n_sims // 2 - n_worst // 2: n_sims // 2 + n_worst // 2]

    worst_final = paths[worst_idx, -1]
    median_final = paths[median_idx, -1]

    worst_success = float((worst_final > 0).mean())
    median_success = float((median_final > 0).mean())

    # Depletion age for worst paths
    worst_depletion = []
    for idx in worst_idx:
        dep = np.where(paths[idx, :] <= 0)[0]
        worst_depletion.append(int(dep[0]) + inputs.start_age if len(dep) > 0 else inputs.end_age)

    return {
        "worst_paths_success_rate": worst_success,
        "median_success_rate": median_success,
        "avg_first5yr_return_worst": float(first5_returns[worst_idx].mean()),
        "avg_first5yr_return_median": float(first5_returns[median_idx].mean()),
        "depletion_age_worst_median": int(np.median(worst_depletion)),
        "depletion_age_overall_median": result.years_to_depletion_p10 or inputs.end_age,
        "overall_success_probability": result.success_probability,
    }


# ===========================================================================
# STRESS TESTING
# ===========================================================================

def run_stress_tests(
    inputs: MonteCarloInputs,
    scenarios: Optional[List[str]] = None,
) -> List[StressTestResult]:
    """
    Run all (or selected) stress scenarios against the base inputs.

    Args:
        inputs: MonteCarloInputs (baseline)
        scenarios: List of scenario names to run (None = all)

    Returns:
        List of StressTestResult, one per scenario
    """
    if scenarios is None:
        scenarios = list(STRESS_SCENARIOS.keys())

    results: List[StressTestResult] = []

    for name in scenarios:
        if name not in STRESS_SCENARIOS:
            logger.warning(f"Unknown stress scenario: {name}")
            continue

        scenario_def = STRESS_SCENARIOS[name]
        mc = run_monte_carlo(
            inputs,
            stress_scenario=name,
            mean_override=scenario_def.get("mean_override"),
            std_override=scenario_def.get("std_override"),
            inflation_override=scenario_def.get("inflation_override"),
        )

        # Median portfolio path
        median_path: List[float] = []
        if mc.portfolio_paths is not None:
            median_path = [
                float(np.median(mc.portfolio_paths[:, yr]))
                for yr in range(mc.portfolio_paths.shape[1])
            ]

        # Median depletion year
        depletion_median: Optional[int] = None
        if mc.portfolio_paths is not None:
            median_sim_idx = int(np.argsort(mc.portfolio_paths[:, -1])[mc.inputs.n_simulations // 2])
            dep = np.where(mc.portfolio_paths[median_sim_idx, :] <= 0)[0]
            if len(dep) > 0:
                depletion_median = int(dep[0]) + inputs.start_age

        results.append(StressTestResult(
            scenario_name=name,
            description=scenario_def["description"],
            success_probability=mc.success_probability,
            median_final_portfolio=mc.median_final_portfolio,
            p10_final_portfolio=mc.p10_final_portfolio,
            years_to_depletion_median=depletion_median,
            portfolio_path_median=median_path,
            notes=mc.notes,
        ))

    return results


# ===========================================================================
# LONGEVITY RISK ANALYSIS
# ===========================================================================

def run_longevity_analysis(
    inputs: MonteCarloInputs,
    longevity_ages: Optional[Dict[str, int]] = None,
) -> Dict[str, MonteCarloResult]:
    """
    Run Monte Carlo for multiple longevity scenarios.

    Args:
        inputs: MonteCarloInputs (baseline)
        longevity_ages: Dict mapping label to end_age (None = use LONGEVITY_SCENARIOS)

    Returns:
        Dict mapping scenario label to MonteCarloResult
    """
    if longevity_ages is None:
        longevity_ages = LONGEVITY_SCENARIOS

    results: Dict[str, MonteCarloResult] = {}
    for label, end_age in longevity_ages.items():
        if end_age <= inputs.start_age:
            continue
        modified = MonteCarloInputs(
            initial_portfolio=inputs.initial_portfolio,
            annual_withdrawal=inputs.annual_withdrawal,
            start_age=inputs.start_age,
            end_age=end_age,
            portfolio_allocation=inputs.portfolio_allocation,
            inflation_rate=inputs.inflation_rate,
            withdrawal_growth_rate=inputs.withdrawal_growth_rate,
            social_security_annual=inputs.social_security_annual,
            ss_start_age=inputs.ss_start_age,
            additional_income=inputs.additional_income,
            n_simulations=inputs.n_simulations,
            random_seed=inputs.random_seed,
        )
        results[label] = run_monte_carlo(modified)

    return results


# ===========================================================================
# FAN CHART DATA
# ===========================================================================

def build_fan_chart_df(result: MonteCarloResult) -> pd.DataFrame:
    """
    Build a DataFrame suitable for rendering a fan chart.

    Columns: age, p5, p10, p25, p50, p75, p90, p95, success_rate

    Args:
        result: MonteCarloResult from run_monte_carlo()

    Returns:
        DataFrame with one row per year
    """
    rows = []
    for yr in result.years:
        row: Dict = {"age": yr.age, "success_rate": yr.success_rate}
        for p in FAN_CHART_PERCENTILES:
            row[f"p{p}"] = yr.percentiles.get(p, 0.0)
        rows.append(row)
    return pd.DataFrame(rows)


def build_success_heatmap_df(
    inputs: MonteCarloInputs,
    withdrawal_range: Optional[List[float]] = None,
    allocation_presets: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Build a success probability heatmap DataFrame.

    Rows = withdrawal amounts, Columns = portfolio allocations.
    Each cell = success probability (0–1).

    Args:
        inputs: Base MonteCarloInputs
        withdrawal_range: List of annual withdrawal amounts to test
        allocation_presets: List of preset names from PORTFOLIO_PRESETS

    Returns:
        DataFrame with withdrawal amounts as index, allocations as columns
    """
    if withdrawal_range is None:
        base = inputs.annual_withdrawal
        withdrawal_range = [base * m for m in [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]]

    if allocation_presets is None:
        allocation_presets = list(PORTFOLIO_PRESETS.keys())

    rows = []
    for withdrawal in withdrawal_range:
        row: Dict = {"Annual Withdrawal": f"${withdrawal:,.0f}"}
        for preset in allocation_presets:
            if preset not in PORTFOLIO_PRESETS:
                continue
            modified = MonteCarloInputs(
                initial_portfolio=inputs.initial_portfolio,
                annual_withdrawal=withdrawal,
                start_age=inputs.start_age,
                end_age=inputs.end_age,
                portfolio_allocation=PORTFOLIO_PRESETS[preset],
                inflation_rate=inputs.inflation_rate,
                withdrawal_growth_rate=inputs.withdrawal_growth_rate,
                social_security_annual=inputs.social_security_annual,
                ss_start_age=inputs.ss_start_age,
                additional_income=inputs.additional_income,
                n_simulations=min(inputs.n_simulations, 2_000),  # Faster for heatmap
                random_seed=inputs.random_seed,
            )
            mc = run_monte_carlo(modified)
            row[preset] = round(mc.success_probability * 100, 1)
        rows.append(row)

    return pd.DataFrame(rows)


# ===========================================================================
# SCENARIO COMPARISON
# ===========================================================================

def run_full_scenario_comparison(
    inputs: MonteCarloInputs,
    stress_scenarios: Optional[List[str]] = None,
    longevity_ages: Optional[Dict[str, int]] = None,
) -> ScenarioComparisonResult:
    """
    Run baseline + all stress tests + longevity analysis in one call.

    Args:
        inputs: MonteCarloInputs (baseline)
        stress_scenarios: Stress scenario names (None = all)
        longevity_ages: Longevity scenario dict (None = defaults)

    Returns:
        ScenarioComparisonResult with all results
    """
    baseline = run_monte_carlo(inputs)
    stress = run_stress_tests(inputs, stress_scenarios)
    longevity = run_longevity_analysis(inputs, longevity_ages)

    return ScenarioComparisonResult(
        baseline=baseline,
        stress_tests=stress,
        longevity_results=longevity,
    )


def build_scenario_comparison_df(comparison: ScenarioComparisonResult) -> pd.DataFrame:
    """
    Build a summary DataFrame comparing all scenarios.

    Args:
        comparison: ScenarioComparisonResult

    Returns:
        DataFrame with one row per scenario
    """
    rows = []

    # Baseline
    b = comparison.baseline
    rows.append({
        "Scenario": "📊 Baseline",
        "Success Probability": f"{b.success_probability:.1%}",
        "Median Final Portfolio": f"${b.median_final_portfolio:,.0f}",
        "10th Pct Final Portfolio": f"${b.p10_final_portfolio:,.0f}",
        "90th Pct Final Portfolio": f"${b.p90_final_portfolio:,.0f}",
        "P10 Depletion Age": str(b.years_to_depletion_p10) if b.years_to_depletion_p10 else "Never",
    })

    # Stress tests
    for st in comparison.stress_tests:
        rows.append({
            "Scenario": f"⚠️ {st.scenario_name}",
            "Success Probability": f"{st.success_probability:.1%}",
            "Median Final Portfolio": f"${st.median_final_portfolio:,.0f}",
            "10th Pct Final Portfolio": f"${st.p10_final_portfolio:,.0f}",
            "90th Pct Final Portfolio": "N/A",
            "P10 Depletion Age": str(st.years_to_depletion_median) if st.years_to_depletion_median else "Never",
        })

    # Longevity
    for label, mc in comparison.longevity_results.items():
        rows.append({
            "Scenario": f"🕐 {label}",
            "Success Probability": f"{mc.success_probability:.1%}",
            "Median Final Portfolio": f"${mc.median_final_portfolio:,.0f}",
            "10th Pct Final Portfolio": f"${mc.p10_final_portfolio:,.0f}",
            "90th Pct Final Portfolio": f"${mc.p90_final_portfolio:,.0f}",
            "P10 Depletion Age": str(mc.years_to_depletion_p10) if mc.years_to_depletion_p10 else "Never",
        })

    return pd.DataFrame(rows)


# ===========================================================================
# REPORT GENERATION
# ===========================================================================

def generate_monte_carlo_report_csv(
    result: MonteCarloResult,
    stress_results: Optional[List[StressTestResult]] = None,
    longevity_results: Optional[Dict[str, MonteCarloResult]] = None,
) -> bytes:
    """
    Generate a downloadable CSV report from Monte Carlo results.

    Args:
        result: Baseline MonteCarloResult
        stress_results: Optional stress test results
        longevity_results: Optional longevity scenario results

    Returns:
        CSV bytes suitable for st.download_button()
    """
    buf = io.StringIO()

    # Section 1: Summary
    buf.write("MONTE CARLO SIMULATION REPORT\n")
    buf.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    buf.write("BASELINE SUMMARY\n")
    buf.write(f"Initial Portfolio,${result.inputs.initial_portfolio:,.0f}\n")
    buf.write(f"Annual Withdrawal,${result.inputs.annual_withdrawal:,.0f}\n")
    buf.write(f"Start Age,{result.inputs.start_age}\n")
    buf.write(f"End Age,{result.inputs.end_age}\n")
    buf.write(f"Simulations,{result.inputs.n_simulations:,}\n")
    buf.write(f"Success Probability,{result.success_probability:.1%}\n")
    buf.write(f"Median Final Portfolio,${result.median_final_portfolio:,.0f}\n")
    buf.write(f"10th Pct Final Portfolio,${result.p10_final_portfolio:,.0f}\n")
    buf.write(f"90th Pct Final Portfolio,${result.p90_final_portfolio:,.0f}\n")
    if result.years_to_depletion_p10:
        buf.write(f"P10 Depletion Age,{result.years_to_depletion_p10}\n")
    buf.write("\n")

    # Section 2: Year-by-year fan chart
    buf.write("YEAR-BY-YEAR PERCENTILE BANDS\n")
    fan_df = build_fan_chart_df(result)
    fan_df.to_csv(buf, index=False)
    buf.write("\n")

    # Section 3: Stress tests
    if stress_results:
        buf.write("STRESS TEST RESULTS\n")
        stress_rows = []
        for st in stress_results:
            stress_rows.append({
                "Scenario": st.scenario_name,
                "Description": st.description,
                "Success Probability": f"{st.success_probability:.1%}",
                "Median Final Portfolio": f"${st.median_final_portfolio:,.0f}",
                "P10 Final Portfolio": f"${st.p10_final_portfolio:,.0f}",
                "Depletion Age (Median)": st.years_to_depletion_median or "Never",
            })
        pd.DataFrame(stress_rows).to_csv(buf, index=False)
        buf.write("\n")

    # Section 4: Longevity
    if longevity_results:
        buf.write("LONGEVITY SCENARIO RESULTS\n")
        lon_rows = []
        for label, mc in longevity_results.items():
            lon_rows.append({
                "Scenario": label,
                "End Age": mc.inputs.end_age,
                "Success Probability": f"{mc.success_probability:.1%}",
                "Median Final Portfolio": f"${mc.median_final_portfolio:,.0f}",
                "P10 Final Portfolio": f"${mc.p10_final_portfolio:,.0f}",
                "P10 Depletion Age": mc.years_to_depletion_p10 or "Never",
            })
        pd.DataFrame(lon_rows).to_csv(buf, index=False)

    return buf.getvalue().encode("utf-8")


def get_safe_withdrawal_rate(
    inputs: MonteCarloInputs,
    target_success: float = 0.90,
    tolerance: float = 0.01,
    max_iterations: int = 20,
) -> float:
    """
    Binary search for the maximum safe withdrawal rate at a target success probability.

    Args:
        inputs: MonteCarloInputs (annual_withdrawal is the starting point)
        target_success: Target success probability (default 90%)
        tolerance: Convergence tolerance
        max_iterations: Maximum binary search iterations

    Returns:
        Safe annual withdrawal amount at the target success probability
    """
    low = inputs.annual_withdrawal * 0.1
    high = inputs.annual_withdrawal * 2.0

    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        test_inputs = MonteCarloInputs(
            initial_portfolio=inputs.initial_portfolio,
            annual_withdrawal=mid,
            start_age=inputs.start_age,
            end_age=inputs.end_age,
            portfolio_allocation=inputs.portfolio_allocation,
            inflation_rate=inputs.inflation_rate,
            withdrawal_growth_rate=inputs.withdrawal_growth_rate,
            social_security_annual=inputs.social_security_annual,
            ss_start_age=inputs.ss_start_age,
            additional_income=inputs.additional_income,
            n_simulations=min(inputs.n_simulations, 2_000),
            random_seed=inputs.random_seed,
        )
        mc = run_monte_carlo(test_inputs)
        if abs(mc.success_probability - target_success) < tolerance:
            return mid
        if mc.success_probability > target_success:
            low = mid
        else:
            high = mid

    return (low + high) / 2.0

# Made with Bob
