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

from strategy import (
    PortfolioBalances,
    build_accumulation_strategy_display,
    generate_strategy_summary,
    print_strategy_report,
)
import pandas as pd


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


# ---------------------------------------------------------------------------
# Example scenarios
# ---------------------------------------------------------------------------

def example_1_mid_career_accumulation() -> tuple:
    """Example 1: Mid-career worker building retirement assets (2026-2036).

    Scenario:
    - Age 45 / 43 couple, both employed
    - $650k combined portfolio
    - $150k annual expenses
    - 7% growth, 3% expense inflation
    - Retirement target: 2036 (age 55 / 53)

    Returns:
        tuple: (strategy_df, balances_df)
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Mid-Career Accumulation (2026-2036)")
    print("="*80)

    initial_balances = PortfolioBalances(
        cash=30_000,
        taxable=120_000,
        traditional=380_000,
        roth=120_000,
        daf=0,
    )

    _print_portfolio_balances(initial_balances, "Starting Portfolio")

    strategy_df, balances_df = build_accumulation_strategy_display(
        start_year=2026,
        end_year=2035,
        initial_balances=initial_balances,
        initial_expenses=150_000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.07,
        expense_inflation_rate=0.03,
        retirement_year=2036,
        has_wages=True,
    )

    if strategy_df.empty:
        print("⚠️  No accumulation data returned — check config retirement dates.")
        return strategy_df, balances_df

    summary = generate_strategy_summary(strategy_df)
    print_strategy_report(strategy_df, summary)

    _print_portfolio_evolution(strategy_df, [2026, 2030, 2035])
    _print_account_mix(strategy_df, strategy_df['Year'].iloc[-1])
    _print_roth_conversion_summary(strategy_df)

    strategy_df.to_csv("example_accum1_mid_career.csv", index=False)
    print("\n✅ Results saved to example_accum1_mid_career.csv")

    return strategy_df, balances_df


def example_2_prep_for_retirement() -> tuple:
    """Example 2: Final 10 years before retirement — Stage 2 Prep phase (2026-2035).

    Scenario:
    - Age 55 / 53 couple, still employed
    - $1.4M combined portfolio (heavy Traditional)
    - $160k annual expenses
    - 6.5% growth, 2.5% expense inflation
    - Retirement target: 2036 (age 65 / 63)
    - Demonstrates Stage 2: Prep for Retirement optimisation

    Returns:
        tuple: (strategy_df, balances_df)
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Prep for Retirement — Final 10 Years (2026-2035)")
    print("="*80)

    initial_balances = PortfolioBalances(
        cash=50_000,
        taxable=200_000,
        traditional=900_000,
        roth=250_000,
        daf=0,
    )

    _print_portfolio_balances(initial_balances, "Starting Portfolio")

    strategy_df, balances_df = build_accumulation_strategy_display(
        start_year=2026,
        end_year=2035,
        initial_balances=initial_balances,
        initial_expenses=160_000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.065,
        expense_inflation_rate=0.025,
        retirement_year=2036,
        has_wages=True,
    )

    if strategy_df.empty:
        print("⚠️  No accumulation data returned — check config retirement dates.")
        return strategy_df, balances_df

    # Show stage transitions
    print("\n🎯 Life Stage Transitions:")
    prev_stage = None
    for _, row in strategy_df.iterrows():
        if row['Stage'] != prev_stage:
            print(f"   {row['Year']}: {row['Stage']} (Age {row['Age']})")
            prev_stage = row['Stage']

    _print_portfolio_evolution(strategy_df, [2026, 2030, 2035])
    _print_account_mix(strategy_df, strategy_df['Year'].iloc[-1])
    _print_roth_conversion_summary(strategy_df)

    strategy_df.to_csv("example_accum2_prep_retirement.csv", index=False)
    print("\n✅ Results saved to example_accum2_prep_retirement.csv")

    return strategy_df, balances_df


def example_3_early_saver() -> tuple:
    """Example 3: Early-career saver with long accumulation horizon (2026-2045).

    Scenario:
    - Age 35 / 33 couple, both employed
    - $200k combined portfolio (mostly Roth — early career)
    - $120k annual expenses
    - 7.5% growth, 3% expense inflation
    - Retirement target: 2046 (age 55 / 53)
    - Demonstrates long compounding runway

    Returns:
        tuple: (strategy_df, balances_df)
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Early Saver — Long Accumulation Horizon (2026-2045)")
    print("="*80)

    initial_balances = PortfolioBalances(
        cash=20_000,
        taxable=30_000,
        traditional=80_000,
        roth=70_000,
        daf=0,
    )

    _print_portfolio_balances(initial_balances, "Starting Portfolio")

    strategy_df, balances_df = build_accumulation_strategy_display(
        start_year=2026,
        end_year=2045,
        initial_balances=initial_balances,
        initial_expenses=120_000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.075,
        expense_inflation_rate=0.03,
        retirement_year=2046,
        has_wages=True,
    )

    if strategy_df.empty:
        print("⚠️  No accumulation data returned — check config retirement dates.")
        return strategy_df, balances_df

    _print_portfolio_evolution(strategy_df, [2026, 2030, 2035, 2040, 2045])
    _print_account_mix(strategy_df, strategy_df['Year'].iloc[-1])
    _print_roth_conversion_summary(strategy_df)

    # Show total portfolio growth
    start_total = strategy_df['Total Portfolio'].iloc[0]
    end_total   = strategy_df['Total Portfolio'].iloc[-1]
    growth_x    = end_total / start_total if start_total > 0 else 0
    print(f"\n📈 20-Year Growth Summary:")
    print(f"   Starting portfolio: ${start_total:>12,.0f}")
    print(f"   Ending portfolio:   ${end_total:>12,.0f}")
    print(f"   Growth multiple:    {growth_x:.1f}x")

    strategy_df.to_csv("example_accum3_early_saver.csv", index=False)
    print("\n✅ Results saved to example_accum3_early_saver.csv")

    return strategy_df, balances_df


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