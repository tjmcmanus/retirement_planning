#!/usr/bin/env python3
"""
Example script demonstrating the 5-stage retirement withdrawal strategy

This script shows how to use the withdrawal_strategy module to:
1. Calculate optimal withdrawal strategies across 5 life stages
2. Optimize Roth conversions
3. Minimize taxes and IRMAA penalties
4. Generate comprehensive reports

Usage:
    python example_withdrawal_strategy.py
"""

from withdrawal_strategy import (
    PortfolioBalances,
    WithdrawalStrategyEngine,
    build_withdrawal_strategy_display,
    create_example_scenario,
    generate_strategy_summary,
    print_strategy_report
)
import pandas as pd


def _print_portfolio_balances(balances: PortfolioBalances, title: str = "Portfolio") -> None:
    """Print formatted portfolio balance details.
    
    Args:
        balances: PortfolioBalances object containing account balances
        title: Title to display above the balance details
    """
    print(f"\n{title}:")
    print(f"  Cash: ${balances.cash:,.0f}")
    print(f"  Taxable: ${balances.taxable:,.0f}")
    print(f"  Traditional: ${balances.traditional:,.0f}")
    print(f"  Roth: ${balances.roth:,.0f}")
    print(f"  DAF: ${balances.daf:,.0f}")
    print(f"  Total: ${balances.total():,.0f}")


def _print_portfolio_evolution(strategy_df: pd.DataFrame, years: list[int]) -> None:
    """Print portfolio values at specific milestone years.
    
    Args:
        strategy_df: DataFrame containing withdrawal strategy data
        years: List of years to display portfolio values for
    """
    print(f"\n📊 Portfolio Evolution:")
    for year in years:
        year_data = strategy_df.loc[strategy_df['Year'] == year]
        if not year_data.empty:
            total = year_data['Total Portfolio'].iloc[0]
            print(f"   Year {year}: ${total:,.0f}")


def _calculate_roth_percentage(strategy_df: pd.DataFrame, year: int) -> float:
    """Calculate Roth balance as percentage of total portfolio for a given year.
    
    Args:
        strategy_df: DataFrame containing withdrawal strategy data
        year: Year to calculate Roth percentage for
        
    Returns:
        Roth balance as percentage of total portfolio (0.0 if year not found)
    """
    year_data = strategy_df.loc[strategy_df['Year'] == year]
    if year_data.empty:
        return 0.0
    roth = year_data['Roth Balance'].iloc[0]
    total = year_data['Total Portfolio'].iloc[0]
    return (roth / total * 100) if total > 0 else 0.0


def _print_roth_conversion_impact(
    strategy_df: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> None:
    """Print Roth conversion impact between two milestone years.

    Args:
        strategy_df: DataFrame containing withdrawal strategy data
        start_year: First year to measure Roth percentage
        end_year: Final year to measure Roth percentage
    """
    roth_pct_start = _calculate_roth_percentage(strategy_df, start_year)
    roth_pct_end = _calculate_roth_percentage(strategy_df, end_year)
    print(f"\n💰 Roth Conversion Impact:")
    print(f"   Starting Roth %: {roth_pct_start:.1f}%")
    print(f"   Ending Roth %: {roth_pct_end:.1f}%")
    print(f"   Change: {roth_pct_end - roth_pct_start:+.1f} percentage points")


def example_1_basic_strategy():
    """Example 1: Basic withdrawal strategy from 2026-2051"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic Withdrawal Strategy")
    print("="*80)
    
    # Define initial portfolio balances
    initial_balances = PortfolioBalances(
        cash=55000,
        taxable=225000,
        traditional=670000,
        roth=168000,
        daf=0
    )
    
    # Calculate strategy
    strategy_df, balances_df = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2050,
        initial_balances=initial_balances,
        initial_expenses=150000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.06,
        expense_inflation_rate=0.03,  # 3% inflation rate
        ss_claiming_age=67,
        retirement_year=2027,
        has_wages=True
    )
    
    # Generate and print report
    summary = generate_strategy_summary(strategy_df)
    print_strategy_report(strategy_df, summary)
    
    # Save results
    strategy_df.to_csv("example1_strategy.csv", index=False)
    print("✅ Results saved to example1_strategy.csv")
    
    return strategy_df, balances_df


def example_2_early_retirement():
    """Example 2: Early retirement with aggressive Roth conversions"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Early Retirement Strategy")
    print("="*80)
    
    # Use pre-defined scenario
    scenario = create_example_scenario("early_retire")
    
    print(f"\nScenario Details:")
    print(f"  Initial Portfolio: ${scenario.initial_balances.total():,.0f}")
    print(f"  Annual Expenses: ${scenario.initial_expenses:,.0f}")
    print(f"  SS Claiming Age: {scenario.ss_claiming_age}")
    print(f"  Growth Rate: {(scenario.growth_rate-1)*100:.1f}%")
    
    # Calculate strategy
    strategy_df, balances_df = build_withdrawal_strategy_display(**scenario.to_dict())
    
    # Analyze Roth conversion opportunities
    conversion_years = strategy_df[strategy_df['Roth Conversion'] > 0]
    print(f"\n💰 Roth Conversion Analysis:")
    print(f"   Years with conversions: {len(conversion_years)}")
    print(f"   Total converted: ${conversion_years['Roth Conversion'].sum():,.0f}")
    print(f"   Average conversion: ${conversion_years['Roth Conversion'].mean():,.0f}")
    
    # Show stage transitions
    print(f"\n🎯 Life Stage Transitions:")
    prev_stage = None
    for _, row in strategy_df.iterrows():
        if row['Stage'] != prev_stage:
            print(f"   {row['Year']}: {row['Stage']} (Age {row['Age']})")
            prev_stage = row['Stage']
    
    strategy_df.to_csv("example2_early_retire.csv", index=False)
    print("\n✅ Results saved to example2_early_retire.csv")
    
    return strategy_df, balances_df


def example_3_high_income():
    """Example 3: High income portfolio with IRMAA optimization"""
    print("\n" + "="*80)
    print("EXAMPLE 3: High Income Portfolio Strategy")
    print("="*80)
    
    scenario = create_example_scenario("high_income")
    
    print(f"\nScenario Details:")
    print(f"  Initial Portfolio: ${scenario.initial_balances.total():,.0f}")
    print(f"  Traditional IRA: ${scenario.initial_balances.traditional:,.0f}")
    print(f"  Annual Expenses: ${scenario.initial_expenses:,.0f}")
    
    strategy_df, balances_df = build_withdrawal_strategy_display(**scenario.to_dict())
    
    # Analyze IRMAA impact
    irmaa_years = strategy_df[strategy_df['IRMAA Penalty'] > 0]
    print(f"\n🏥 IRMAA Analysis:")
    print(f"   Years with IRMAA: {len(irmaa_years)}")
    print(f"   Total IRMAA paid: ${irmaa_years['IRMAA Penalty'].sum():,.0f}")
    print(f"   Average IRMAA: ${irmaa_years['IRMAA Penalty'].mean():,.0f}/year")
    
    # Tax efficiency analysis
    total_income = (strategy_df['SS Benefits'].sum() + 
                   strategy_df['Traditional Withdrawal'].sum() + 
                   strategy_df['Roth Conversion'].sum())
    total_taxes = strategy_df['Federal Tax'].sum()
    effective_rate = (total_taxes / total_income * 100) if total_income > 0 else 0
    
    print(f"\n💵 Tax Efficiency:")
    print(f"   Total Income: ${total_income:,.0f}")
    print(f"   Total Taxes: ${total_taxes:,.0f}")
    print(f"   Effective Rate: {effective_rate:.2f}%")
    
    strategy_df.to_csv("example3_high_income.csv", index=False)
    print("\n✅ Results saved to example3_high_income.csv")
    
    return strategy_df, balances_df


EXAMPLE4_CSV_OUTPUT = "example4_custom.csv"


def _display_custom_scenario_results(
    strategy_df: pd.DataFrame,
    start_year: int,
    end_year: int,
    csv_output: str,
) -> None:
    """Display results and save CSV for the custom scenario.

    Args:
        strategy_df: DataFrame containing withdrawal strategy data
        start_year: First year of the planning horizon
        end_year: Final year of the planning horizon
        csv_output: File path to write the CSV output
    """
    mid_year = (start_year + end_year) // 2
    _print_portfolio_evolution(strategy_df, [start_year, mid_year, end_year])
    _print_roth_conversion_impact(strategy_df, start_year=start_year, end_year=end_year)
    with open(csv_output, "w", encoding="utf-8", newline="") as f:
        strategy_df.to_csv(f, index=False)
    print(f"\n✅ Results saved to {csv_output}")


def example_4_custom_scenario() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Example 4: Custom scenario with specific parameters
    
    Demonstrates a custom retirement scenario with:
    - Large traditional IRA ($5.5M) requiring strategic Roth conversions
    - Substantial taxable account ($1.25M) for tax-efficient withdrawals
    - Delayed Social Security claiming (age 70) for maximum benefits
    - Conservative growth assumptions (6% annual return)
    - 20-year planning horizon (2026-2045)
    
    Returns:
        tuple: (strategy_df, balances_df) containing withdrawal strategy and balance evolution
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Custom Scenario")
    print("="*80)
    
    # Create custom balances
    custom_balances = PortfolioBalances(
        cash=200000,
        taxable=1250000,
        traditional=5500000,
        roth=800000,
        daf=25000
    )
    
    _print_portfolio_balances(custom_balances, "Custom Portfolio")
    
    # Calculate with custom parameters
    strategy_df, balances_df = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2045,  # 20 years
        initial_balances=custom_balances,
        initial_expenses=150000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.06,  # Conservative 6% growth
        expense_inflation_rate=0.02,  # 2% inflation rate
        ss_claiming_age=70,  # Delay SS for maximum benefit
        retirement_year=2026,
        has_wages=False
    )
    
    # Show portfolio evolution at key milestones and save results
    _display_custom_scenario_results(strategy_df, 2026, 2045, EXAMPLE4_CSV_OUTPUT)

    return strategy_df, balances_df


# Comparison metric configuration: (display_name, summary_key, formatter_function)
COMPARISON_METRICS = [
    ('Initial Portfolio', 'initial_portfolio_value', lambda v: f"${v:,.0f}"),
    ('Final Portfolio', 'final_portfolio_value', lambda v: f"${v:,.0f}"),
    ('Portfolio Growth', 'portfolio_growth', lambda v: f"${v:,.0f}"),
    ('Total Roth Conversions', 'total_roth_conversions', lambda v: f"${v:,.0f}"),
    ('Total Taxes Paid', 'total_taxes_paid', lambda v: f"${v:,.0f}"),
    ('Total IRMAA', 'total_irmaa_penalties', lambda v: f"${v:,.0f}"),
    ('Final Roth %', 'roth_percentage_final', lambda v: f"{v:.1f}%")
]

# Scenario display name mapping
SCENARIO_DISPLAY_NAMES = {
    'default': 'Default',
    'early_retire': 'Early Retire',
    'high_income': 'High Income'
}


def _collect_scenario_results(scenarios: list) -> dict:
    """Collect summary results for all scenarios.
    
    Args:
        scenarios: List of scenario names to process
        
    Returns:
        Dictionary mapping scenario names to their summary results
    """
    results = {}
    for scenario_name in scenarios:
        scenario = create_example_scenario(scenario_name)
        strategy_df, _ = build_withdrawal_strategy_display(**scenario.to_dict())
        summary = generate_strategy_summary(strategy_df)
        results[scenario_name] = summary
    return results


def _build_comparison_dataframe(results: dict, scenarios: list) -> pd.DataFrame:
    """Build comparison DataFrame from scenario results.
    
    Args:
        results: Dictionary of scenario summaries
        scenarios: List of scenario names in desired order
        
    Returns:
        DataFrame with formatted comparison data
    """
    data = {'Metric': [metric[0] for metric in COMPARISON_METRICS]}
    
    for scenario_name in scenarios:
        display_name = SCENARIO_DISPLAY_NAMES.get(scenario_name) or scenario_name.title()
        data[display_name] = [
            formatter(results[scenario_name][key])
            for _, key, formatter in COMPARISON_METRICS
        ]
    
    return pd.DataFrame(data)


def _print_comparison_header():
    """Print comparison section header."""
    print("\n" + "="*80)
    print("SCENARIO COMPARISON")
    print("="*80)


def _print_comparison_table(comparison_df: pd.DataFrame):
    """Print formatted comparison table.
    
    Args:
        comparison_df: DataFrame containing comparison data
    """
    print("\n")
    print(comparison_df.to_string(index=False))
    print("\n")


def compare_scenarios():
    """Compare different scenarios side-by-side.
    
    Generates a comparison table showing key metrics across multiple
    retirement scenarios including portfolio values, conversions, taxes,
    and IRMAA penalties.
    """
    _print_comparison_header()
    
    scenarios = ["default", "early_retire", "high_income"]
    results = _collect_scenario_results(scenarios)
    comparison_df = _build_comparison_dataframe(results, scenarios)
    
    _print_comparison_table(comparison_df)


def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("RETIREMENT WITHDRAWAL STRATEGY - EXAMPLES")
    print("5 Stages of Life: Accumulation → Early Retirement → Medicare → SS → RMD")
    print("="*80)
    
    # Run examples
    example_1_basic_strategy()
    example_2_early_retirement()
    example_3_high_income()
    example_4_custom_scenario()
    compare_scenarios()
    
    print("\n" + "="*80)
    print("✅ All examples completed successfully!")
    print("="*80)
    print("\nGenerated files:")
    print("  - example1_strategy.csv")
    print("  - example2_early_retire.csv")
    print("  - example3_high_income.csv")
    print(f"  - {EXAMPLE4_CSV_OUTPUT}")
    print("\nUse these CSV files for further analysis in Excel or other tools.")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

# Made with Bob
