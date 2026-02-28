#!/usr/bin/env python3
"""
Example script demonstrating the accumulation (pre-retirement) strategy

This script shows how to use the strategy module to:
1. Project portfolio growth during working years (Stage 1: Accumulation)
2. Optimize contributions in the final years before retirement (Stage 2: Prep for Retirement)
3. Analyze Roth vs Traditional contribution decisions
4. Model the impact of different savings rates and growth assumptions

Usage:
    python example_accumulation_strategy.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from strategy import (
    PortfolioBalances,
    build_accumulation_strategy_display,
    generate_strategy_summary,
    print_strategy_report,
)
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario configuration
# ---------------------------------------------------------------------------

@dataclass
class AccumulationScenarioConfig:
    """Configuration for an accumulation-phase scenario.

    All hard-coded values that previously lived inside each example function
    are promoted to named, typed fields with defaults matching Example 1
    (mid-career accumulation).  Override individual fields when constructing
    configs for other scenarios.
    """

    # --- Portfolio starting balances ---
    cash:         int   = 30_000
    taxable:      int   = 120_000
    traditional:  int   = 380_000
    roth:         int   = 120_000
    daf:          int   = 0

    # --- Simulation parameters ---
    start_year:             int   = 2026
    end_year:               int   = 2035
    retirement_year:        int   = 2036
    initial_expenses:       int   = 150_000
    growth_rate:            float = 1.07
    expense_inflation_rate: float = 0.03
    has_wages:              bool  = True

    # --- People ---
    person1_name: str = "Tom"
    person2_name: str = "Sarah"

    # --- Output ---
    output_csv:      Path  = field(default_factory=lambda: Path("example_accum1_mid_career.csv"))
    milestone_years: tuple = (2026, 2030, 2035)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _print_portfolio_balances(balances: PortfolioBalances, title: str = "Portfolio") -> None:
    """Print formatted portfolio balance details.

    Args:
        balances: PortfolioBalances object containing account balances
        title: Title to display above the balance details
    """
    print(f"\n{title}:")
    print(f"  Cash:        ${balances.cash:>12,.0f}")
    print(f"  Taxable:     ${balances.taxable:>12,.0f}")
    print(f"  Traditional: ${balances.traditional:>12,.0f}")
    print(f"  Roth:        ${balances.roth:>12,.0f}")
    print(f"  DAF:         ${balances.daf:>12,.0f}")
    print(f"  Total:       ${balances.total():>12,.0f}")


def _print_portfolio_evolution(strategy_df: pd.DataFrame, years: list) -> None:
    """Print portfolio values at specific milestone years.

    Args:
        strategy_df: DataFrame containing accumulation strategy data
        years: List of years to display portfolio values for
    """
    print("\n📊 Portfolio Evolution:")
    for year in years:
        row = strategy_df.loc[strategy_df['Year'] == year]
        if not row.empty:
            total = row['Total Portfolio'].iloc[0]
            stage = row['Stage'].iloc[0]
            print(f"   {year}: ${total:>12,.0f}  [{stage}]")


def _print_account_mix(strategy_df: pd.DataFrame, year: int) -> None:
    """Print account-type breakdown as percentages for a given year.

    Args:
        strategy_df: DataFrame containing accumulation strategy data
        year: Year to display the account mix for
    """
    row = strategy_df.loc[strategy_df['Year'] == year]
    if row.empty:
        return
    total = row['Total Portfolio'].iloc[0]
    if total <= 0:
        return
    trad_pct  = row['Traditional Balance'].iloc[0] / total * 100
    roth_pct  = row['Roth Balance'].iloc[0]        / total * 100
    tax_pct   = row['Taxable Balance'].iloc[0]     / total * 100
    cash_pct  = row['Cash Balance'].iloc[0]        / total * 100
    print(f"\n📂 Account Mix in {year}:")
    print(f"   Traditional: {trad_pct:5.1f}%  (${row['Traditional Balance'].iloc[0]:>10,.0f})")
    print(f"   Roth:        {roth_pct:5.1f}%  (${row['Roth Balance'].iloc[0]:>10,.0f})")
    print(f"   Taxable:     {tax_pct:5.1f}%  (${row['Taxable Balance'].iloc[0]:>10,.0f})")
    print(f"   Cash:        {cash_pct:5.1f}%  (${row['Cash Balance'].iloc[0]:>10,.0f})")


def _print_roth_conversion_summary(strategy_df: pd.DataFrame) -> None:
    """Print a summary of any Roth conversions made during accumulation.

    Args:
        strategy_df: DataFrame containing accumulation strategy data
    """
    if 'Roth Conversion' not in strategy_df.columns:
        return
    conversion_years = strategy_df[strategy_df['Roth Conversion'] > 0]
    if conversion_years.empty:
        print("\n💰 Roth Conversions: none during accumulation phase")
        return
    print(f"\n💰 Roth Conversions during accumulation:")
    print(f"   Years with conversions: {len(conversion_years)}")
    print(f"   Total converted:        ${conversion_years['Roth Conversion'].sum():>12,.0f}")
    print(f"   Average per year:       ${conversion_years['Roth Conversion'].mean():>12,.0f}")


def _display_stage_transitions(strategy_df: pd.DataFrame) -> None:
    """Log each life-stage transition found in *strategy_df*.

    Iterates the DataFrame once and emits one log line per stage boundary,
    showing the year and age at which the transition occurs.

    Args:
        strategy_df: DataFrame containing accumulation strategy data with
            ``'Stage'``, ``'Year'``, and ``'Age'`` columns.
    """
    if strategy_df.empty:
        return
    logger.info("🎯 Life Stage Transitions:")
    prev_stage = None
    for _, row in strategy_df.iterrows():
        if row['Stage'] != prev_stage:
            logger.info("   %s: %s (Age %s)", row['Year'], row['Stage'], row['Age'])
            prev_stage = row['Stage']


def _save_scenario_csv(df: pd.DataFrame, path: Path) -> Path:
    """Write *df* to *path* as CSV and return the resolved path.

    Creates any missing parent directories so callers can safely pass
    sub-directory paths (e.g. ``Path("output/example1.csv")``).

    Args:
        df:   DataFrame to persist.
        path: Destination file path (``str`` or :class:`~pathlib.Path`).

    Returns:
        The resolved absolute path of the written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("Results saved to %s", path.resolve())
    return path


def _log_scenario_header(title: str) -> None:
    """Emit a bordered INFO banner for a scenario.

    Args:
        title: The scenario title line to display between the two separator
            bars, e.g. ``"EXAMPLE 1: Mid-Career Accumulation (2026-2036)"``.
    """
    logger.info("=" * 80)
    logger.info(title)
    logger.info("=" * 80)


def _log_growth_summary(strategy_df: pd.DataFrame, label: str = "Growth Summary") -> None:
    """Log start/end portfolio values and the growth multiple.

    Args:
        strategy_df: DataFrame containing accumulation strategy data with a
            ``'Total Portfolio'`` column.
        label: Heading text emitted before the three summary lines.
    """
    start_total = strategy_df['Total Portfolio'].iloc[0]
    end_total   = strategy_df['Total Portfolio'].iloc[-1]
    growth_x    = round(end_total / start_total, 1) if start_total else 0
    logger.info(
        "📈 %s:\n   Starting portfolio: $%s\n   Ending portfolio:   $%s\n   Growth multiple:    %.1fx",
        label,
        f"{start_total:>12,.0f}",
        f"{end_total:>12,.0f}",
        growth_x,
    )


def _balances_from_config(config: AccumulationScenarioConfig) -> PortfolioBalances:
    """Construct a :class:`~strategy.PortfolioBalances` from a scenario config.

    Centralises the five-field construction that is otherwise duplicated in
    every scenario function.

    Args:
        config: Scenario configuration supplying the starting account balances.

    Returns:
        A new :class:`~strategy.PortfolioBalances` populated from *config*.
    """
    return PortfolioBalances(
        cash=config.cash,
        taxable=config.taxable,
        traditional=config.traditional,
        roth=config.roth,
        daf=config.daf,
    )


def _run_accumulation_report(
    strategy_df: pd.DataFrame,
    balances_df: pd.DataFrame,
    config: AccumulationScenarioConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the standard reporting block for any accumulation scenario.

    Centralises the repeated pattern shared by all three example functions:
    summary generation, strategy report, portfolio evolution, account mix,
    and Roth conversion summary.

    Args:
        strategy_df: DataFrame returned by
            :func:`~strategy.build_accumulation_strategy_display`.
        balances_df: Companion balances DataFrame from the same call.
        config:      Scenario configuration supplying ``milestone_years``
                     and ``output_csv``.

    Returns:
        The unchanged ``(strategy_df, balances_df)`` tuple so callers can
        return it directly.
    """
    if strategy_df.empty:
        logger.warning("No accumulation data returned — check config retirement dates.")
        return strategy_df, balances_df

    summary = generate_strategy_summary(strategy_df)
    print_strategy_report(strategy_df, summary)
    _log_growth_summary(
        strategy_df,
        f"{strategy_df['Year'].iloc[-1] - strategy_df['Year'].iloc[0]}-Year Growth Summary",
    )

    _print_portfolio_evolution(strategy_df, list(config.milestone_years))
    _print_account_mix(strategy_df, strategy_df['Year'].iloc[-1])
    _print_roth_conversion_summary(strategy_df)

    _save_scenario_csv(strategy_df, config.output_csv)
    return strategy_df, balances_df


# ---------------------------------------------------------------------------
# Example scenarios
# ---------------------------------------------------------------------------

def example_1_mid_career_accumulation(
    config: AccumulationScenarioConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Example 1: Mid-career worker building retirement assets (2026-2036).

    Scenario:
    - Age 45 / 43 couple, both employed
    - $650k combined portfolio
    - $150k annual expenses
    - 7% growth, 3% expense inflation
    - Retirement target: 2036 (age 55 / 53)

    Args:
        config: Scenario configuration.  Defaults to
            :class:`AccumulationScenarioConfig` with all Example-1 values.
            Pass a customised instance to override individual parameters
            without touching the function body.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: ``(strategy_df, balances_df)``
    """
    if config is None:
        config = AccumulationScenarioConfig()

    _log_scenario_header(
        f"EXAMPLE 1: Mid-Career Accumulation ({config.start_year}-{config.retirement_year})"
    )

    initial_balances = _balances_from_config(config)

    _print_portfolio_balances(initial_balances, "Starting Portfolio")

    strategy_df, balances_df = build_accumulation_strategy_display(
        start_year=config.start_year,
        end_year=config.end_year,
        initial_balances=initial_balances,
        initial_expenses=config.initial_expenses,
        person1_name=config.person1_name,
        person2_name=config.person2_name,
        growth_rate=config.growth_rate,
        expense_inflation_rate=config.expense_inflation_rate,
        retirement_year=config.retirement_year,
        has_wages=config.has_wages,
    )

    _display_stage_transitions(strategy_df)
    return _run_accumulation_report(strategy_df, balances_df, config)


def _example_2_config() -> AccumulationScenarioConfig:
    """Return the default :class:`AccumulationScenarioConfig` for Example 2.

    Centralises all hard-coded values for the *Prep for Retirement* scenario
    so that :func:`example_2_prep_for_retirement` can accept an injectable
    ``config`` parameter without duplicating defaults in the function body.

    Returns:
        AccumulationScenarioConfig: Fully populated config for Example 2.
    """
    return AccumulationScenarioConfig(
        cash=50_000,
        taxable=200_000,
        traditional=900_000,
        roth=250_000,
        daf=0,
        start_year=2026,
        end_year=2035,
        retirement_year=2036,
        initial_expenses=160_000,
        growth_rate=1.065,
        expense_inflation_rate=0.025,
        has_wages=True,
        person1_name="Tom",
        person2_name="Sarah",
        output_csv=Path("example_accum2_prep_retirement.csv"),
        milestone_years=(2026, 2030, 2035),
    )


def _example_3_config() -> AccumulationScenarioConfig:
    """Return the default :class:`AccumulationScenarioConfig` for Example 3.

    Centralises all hard-coded values for the *Early Saver* scenario so that
    :func:`example_3_early_saver` can accept an injectable ``config`` parameter
    without duplicating defaults in the function body.

    Returns:
        AccumulationScenarioConfig: Fully populated config for Example 3.
    """
    return AccumulationScenarioConfig(
        cash=20_000,
        taxable=30_000,
        traditional=80_000,
        roth=70_000,
        daf=0,
        start_year=2026,
        end_year=2045,
        retirement_year=2046,
        initial_expenses=120_000,
        growth_rate=1.075,
        expense_inflation_rate=0.03,
        has_wages=True,
        person1_name="Tom",
        person2_name="Sarah",
        output_csv=Path("example_accum3_early_saver.csv"),
        milestone_years=(2026, 2030, 2035, 2040, 2045),
    )


def example_2_prep_for_retirement(
    config: AccumulationScenarioConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Example 2: Final 10 years before retirement — Stage 2 Prep phase (2026-2035).

    Scenario:
    - Age 55 / 53 couple, still employed
    - $1.4M combined portfolio (heavy Traditional)
    - $160k annual expenses
    - 6.5% growth, 2.5% expense inflation
    - Retirement target: 2036 (age 65 / 63)
    - Demonstrates Stage 2: Prep for Retirement optimisation

    Args:
        config: Scenario configuration.  Defaults to
            :func:`_example_2_config` with all Example-2 values.
            Pass a customised instance to override individual parameters
            without touching the function body.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: ``(strategy_df, balances_df)``
    """
    if config is None:
        config = _example_2_config()

    _log_scenario_header(
        f"EXAMPLE 2: Prep for Retirement — Final 10 Years ({config.start_year}-{config.end_year})"
    )

    initial_balances = _balances_from_config(config)

    _print_portfolio_balances(initial_balances, "Starting Portfolio")

    strategy_df, balances_df = build_accumulation_strategy_display(
        start_year=config.start_year,
        end_year=config.end_year,
        initial_balances=initial_balances,
        initial_expenses=config.initial_expenses,
        person1_name=config.person1_name,
        person2_name=config.person2_name,
        growth_rate=config.growth_rate,
        expense_inflation_rate=config.expense_inflation_rate,
        retirement_year=config.retirement_year,
        has_wages=config.has_wages,
    )

    _display_stage_transitions(strategy_df)
    return _run_accumulation_report(strategy_df, balances_df, config)


def example_3_early_saver(
    config: AccumulationScenarioConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Example 3: Early-career saver with long accumulation horizon (2026-2045).

    Scenario:
    - Age 35 / 33 couple, both employed
    - $200k combined portfolio (mostly Roth — early career)
    - $120k annual expenses
    - 7.5% growth, 3% expense inflation
    - Retirement target: 2046 (age 55 / 53)
    - Demonstrates long compounding runway

    Args:
        config: Scenario configuration.  Defaults to
            :func:`_example_3_config` with all Example-3 values.
            Pass a customised instance to override individual parameters
            without touching the function body.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: ``(strategy_df, balances_df)``
    """
    if config is None:
        config = _example_3_config()

    _log_scenario_header(
        f"EXAMPLE 3: Early Saver — Long Accumulation Horizon "
        f"({config.start_year}-{config.end_year})"
    )

    initial_balances = _balances_from_config(config)
    _print_portfolio_balances(initial_balances, "Starting Portfolio")

    strategy_df, balances_df = build_accumulation_strategy_display(
        start_year=config.start_year,
        end_year=config.end_year,
        initial_balances=initial_balances,
        initial_expenses=config.initial_expenses,
        person1_name=config.person1_name,
        person2_name=config.person2_name,
        growth_rate=config.growth_rate,
        expense_inflation_rate=config.expense_inflation_rate,
        retirement_year=config.retirement_year,
        has_wages=config.has_wages,
    )

    _display_stage_transitions(strategy_df)
    return _run_accumulation_report(strategy_df, balances_df, config)


def compare_accumulation_scenarios() -> None:
    """Compare key metrics across all three accumulation scenarios."""
    print("\n" + "="*80)
    print("ACCUMULATION SCENARIO COMPARISON")
    print("="*80)

    scenarios = [
        ("Mid-Career",       "example_accum1_mid_career.csv"),
        ("Prep Retirement",  "example_accum2_prep_retirement.csv"),
        ("Early Saver",      "example_accum3_early_saver.csv"),
    ]

    rows = []
    for label, csv_file in scenarios:
        try:
            df = pd.read_csv(csv_file)
            start_val = df['Total Portfolio'].iloc[0]
            end_val   = df['Total Portfolio'].iloc[-1]
            years     = len(df)
            roth_end  = df['Roth Balance'].iloc[-1]
            roth_pct  = roth_end / end_val * 100 if end_val > 0 else 0
            rows.append({
                'Scenario':          label,
                'Years':             years,
                'Start Portfolio':   f"${start_val:>10,.0f}",
                'End Portfolio':     f"${end_val:>10,.0f}",
                'Growth':            f"${end_val - start_val:>10,.0f}",
                'Final Roth %':      f"{roth_pct:.1f}%",
            })
        except FileNotFoundError:
            rows.append({'Scenario': label, 'Years': 'N/A',
                         'Start Portfolio': 'N/A', 'End Portfolio': 'N/A',
                         'Growth': 'N/A', 'Final Roth %': 'N/A'})

    comparison_df = pd.DataFrame(rows)
    print("\n")
    print(comparison_df.to_string(index=False))
    print("\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run all accumulation strategy examples."""
    print("\n" + "="*80)
    print("RETIREMENT ACCUMULATION STRATEGY - EXAMPLES")
    print("Stage 1: Accumulation  →  Stage 2: Prep for Retirement")
    print("="*80)

    example_1_mid_career_accumulation()
    example_2_prep_for_retirement()
    example_3_early_saver()
    compare_accumulation_scenarios()

    print("\n" + "="*80)
    print("✅ All accumulation examples completed successfully!")
    print("="*80)
    print("\nGenerated files:")
    print("  - example_accum1_mid_career.csv")
    print("  - example_accum2_prep_retirement.csv")
    print("  - example_accum3_early_saver.csv")
    print("\nUse these CSV files for further analysis in Excel or other tools.")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

# Made with Bob