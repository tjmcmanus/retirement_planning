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
    print(f"  Initial Portfolio: ${scenario['initial_balances'].total():,.0f}")
    print(f"  Annual Expenses: ${scenario['initial_expenses']:,.0f}")
    print(f"  SS Claiming Age: {scenario['ss_claiming_age']}")
    print(f"  Growth Rate: {(scenario['growth_rate']-1)*100:.1f}%")
    
    # Calculate strategy
    strategy_df, balances_df = build_withdrawal_strategy_display(**scenario)
    
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
    print(f"  Initial Portfolio: ${scenario['initial_balances'].total():,.0f}")
    print(f"  Traditional IRA: ${scenario['initial_balances'].traditional:,.0f}")
    print(f"  Annual Expenses: ${scenario['initial_expenses']:,.0f}")
    
    strategy_df, balances_df = build_withdrawal_strategy_display(**scenario)
    
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


def example_4_custom_scenario():
    """Example 4: Custom scenario with specific parameters"""
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
    
    print(f"\nCustom Portfolio:")
    print(f"  Cash: ${custom_balances.cash:,.0f}")
    print(f"  Taxable: ${custom_balances.taxable:,.0f}")
    print(f"  Traditional: ${custom_balances.traditional:,.0f}")
    print(f"  Roth: ${custom_balances.roth:,.0f}")
    print(f"  DAF: ${custom_balances.daf:,.0f}")
    print(f"  Total: ${custom_balances.total():,.0f}")
    
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
    
    # Show portfolio evolution
    print(f"\n📊 Portfolio Evolution:")
    print(f"   Year 2026: ${strategy_df.iloc[0]['Total Portfolio']:,.0f}")
    print(f"   Year 2035: ${strategy_df.iloc[9]['Total Portfolio']:,.0f}")
    print(f"   Year 2045: ${strategy_df.iloc[-1]['Total Portfolio']:,.0f}")
    
    # Roth percentage over time
    roth_pct_start = (strategy_df.iloc[0]['Roth Balance'] / strategy_df.iloc[0]['Total Portfolio'] * 100)
    roth_pct_end = (strategy_df.iloc[-1]['Roth Balance'] / strategy_df.iloc[-1]['Total Portfolio'] * 100)
    
    print(f"\n💰 Roth Conversion Impact:")
    print(f"   Starting Roth %: {roth_pct_start:.1f}%")
    print(f"   Ending Roth %: {roth_pct_end:.1f}%")
    print(f"   Change: {roth_pct_end - roth_pct_start:+.1f} percentage points")
    
    strategy_df.to_csv("example4_custom.csv", index=False)
    print("\n✅ Results saved to example4_custom.csv")
    
    return strategy_df, balances_df


def compare_scenarios():
    """Compare different scenarios side-by-side"""
    print("\n" + "="*80)
    print("SCENARIO COMPARISON")
    print("="*80)
    
    scenarios = ["default", "early_retire", "high_income"]
    results = {}
    
    for scenario_name in scenarios:
        scenario = create_example_scenario(scenario_name)
        strategy_df, _ = build_withdrawal_strategy_display(**scenario)
        summary = generate_strategy_summary(strategy_df)
        results[scenario_name] = summary
    
    # Create comparison table
    comparison = pd.DataFrame({
        'Metric': [
            'Initial Portfolio',
            'Final Portfolio',
            'Portfolio Growth',
            'Total Roth Conversions',
            'Total Taxes Paid',
            'Total IRMAA',
            'Final Roth %'
        ],
        'Default': [
            f"${results['default']['initial_portfolio_value']:,.0f}",
            f"${results['default']['final_portfolio_value']:,.0f}",
            f"${results['default']['portfolio_growth']:,.0f}",
            f"${results['default']['total_roth_conversions']:,.0f}",
            f"${results['default']['total_taxes_paid']:,.0f}",
            f"${results['default']['total_irmaa_penalties']:,.0f}",
            f"{results['default']['roth_percentage_final']:.1f}%"
        ],
        'Early Retire': [
            f"${results['early_retire']['initial_portfolio_value']:,.0f}",
            f"${results['early_retire']['final_portfolio_value']:,.0f}",
            f"${results['early_retire']['portfolio_growth']:,.0f}",
            f"${results['early_retire']['total_roth_conversions']:,.0f}",
            f"${results['early_retire']['total_taxes_paid']:,.0f}",
            f"${results['early_retire']['total_irmaa_penalties']:,.0f}",
            f"{results['early_retire']['roth_percentage_final']:.1f}%"
        ],
        'High Income': [
            f"${results['high_income']['initial_portfolio_value']:,.0f}",
            f"${results['high_income']['final_portfolio_value']:,.0f}",
            f"${results['high_income']['portfolio_growth']:,.0f}",
            f"${results['high_income']['total_roth_conversions']:,.0f}",
            f"${results['high_income']['total_taxes_paid']:,.0f}",
            f"${results['high_income']['total_irmaa_penalties']:,.0f}",
            f"{results['high_income']['roth_percentage_final']:.1f}%"
        ]
    })
    
    print("\n")
    print(comparison.to_string(index=False))
    print("\n")


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
    print("  - example4_custom.csv")
    print("\nUse these CSV files for further analysis in Excel or other tools.")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

# Made with Bob
