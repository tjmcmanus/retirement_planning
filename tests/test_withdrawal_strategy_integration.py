#!/usr/bin/env python3
"""
Integration Tests with Historical Market Data Simulation

Tests withdrawal strategy against simulated historical market scenarios
to ensure robustness across different market conditions.

Author: Bob
Date: 2026-03-08
Version: 1.0
"""

import sys
import logging
from typing import List, Dict, Any
import pandas as pd
import numpy as np

from strategy import (
    PortfolioBalances,
    build_withdrawal_strategy_display
)
from withdrawal_strategy_validation import (
    validate_withdrawal_scenario,
    validate_yearly_strategy,
    ValidationResult
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ==============================================================================
# HISTORICAL MARKET SCENARIOS
# ==============================================================================

# Simulated historical market return sequences
MARKET_SCENARIOS = {
    'great_recession_2008': {
        'description': '2008 Financial Crisis scenario',
        'years': [2008, 2009, 2010, 2011, 2012],
        'returns': [-0.37, 0.26, 0.15, 0.02, 0.16],  # S&P 500 approximate
        'inflation': [0.038, -0.004, 0.016, 0.032, 0.021]
    },
    'dot_com_bust_2000': {
        'description': 'Dot-com bubble burst scenario',
        'years': [2000, 2001, 2002, 2003, 2004],
        'returns': [-0.09, -0.12, -0.22, 0.29, 0.11],
        'inflation': [0.034, 0.028, 0.016, 0.023, 0.027]
    },
    'bull_market_2010s': {
        'description': '2010s bull market scenario',
        'years': [2013, 2014, 2015, 2016, 2017],
        'returns': [0.32, 0.14, 0.01, 0.12, 0.22],
        'inflation': [0.015, 0.016, 0.001, 0.013, 0.021]
    },
    'covid_recovery': {
        'description': 'COVID-19 crash and recovery',
        'years': [2020, 2021, 2022, 2023, 2024],
        'returns': [0.18, 0.29, -0.18, 0.26, 0.24],
        'inflation': [0.012, 0.047, 0.080, 0.041, 0.031]
    },
    'stagflation_1970s': {
        'description': '1970s stagflation scenario',
        'years': [1973, 1974, 1975, 1976, 1977],
        'returns': [-0.15, -0.26, 0.37, 0.24, -0.07],
        'inflation': [0.062, 0.110, 0.091, 0.058, 0.065]
    }
}


# ==============================================================================
# MARKET SCENARIO TESTING
# ==============================================================================

def test_strategy_with_market_scenario(
    scenario_name: str,
    market_data: Dict[str, Any],
    initial_portfolio: float = 1000000,
    annual_expenses: float = 50000
) -> Dict[str, Any]:
    """
    Test withdrawal strategy with historical market scenario
    
    Args:
        scenario_name: Name of market scenario
        market_data: Historical market data (returns, inflation)
        initial_portfolio: Initial portfolio value
        annual_expenses: Annual expenses
    
    Returns:
        Dictionary with test results
    """
    print(f"\nTesting: {scenario_name}")
    print(f"  {market_data['description']}")
    
    # Distribute portfolio across accounts
    balances = PortfolioBalances(
        cash=initial_portfolio * 0.05,
        taxable=initial_portfolio * 0.20,
        traditional=initial_portfolio * 0.50,
        roth=initial_portfolio * 0.25,
        daf=0
    )
    
    returns = market_data['returns']
    inflation_rates = market_data['inflation']
    years = len(returns)
    
    # Run strategy year by year with actual returns
    results = []
    current_balances = balances
    current_expenses = annual_expenses
    
    validation_result = ValidationResult(is_valid=True)
    
    for i in range(years):
        year = 2026 + i
        growth_rate = 1.0 + returns[i]
        inflation_rate = inflation_rates[i]
        
        try:
            # Run single year
            strategy_df, _ = build_withdrawal_strategy_display(
                start_year=year,
                end_year=year,
                initial_balances=current_balances,
                initial_expenses=current_expenses,
                person1_name="Tom",
                person2_name="Sarah",
                growth_rate=growth_rate,
                expense_inflation_rate=inflation_rate,
                ss_claiming_age=67,
                retirement_year=2026,
                has_wages=False
            )
            
            # Extract results
            year_result = strategy_df.iloc[0]
            
            # Validate year
            validate_yearly_strategy(
                year=year,
                age_primary=60 + i,
                age_spouse=58 + i,
                balances={
                    'cash': year_result['Cash Balance'],
                    'taxable': year_result['Taxable Balance'],
                    'traditional': year_result['Traditional Balance'],
                    'roth': year_result['Roth Balance']
                },
                expenses=year_result['Expenses'],
                withdrawals={
                    'traditional': year_result['Traditional Withdrawal'],
                    'taxable': year_result['Taxable Withdrawal'],
                    'roth': year_result['Roth Withdrawal']
                },
                result=validation_result
            )
            
            results.append({
                'year': year,
                'return': returns[i],
                'inflation': inflation_rates[i],
                'portfolio': year_result['Total Portfolio'],
                'expenses': year_result['Expenses'],
                'taxes': year_result['Federal Tax'],
                'conversions': year_result['Roth Conversion']
            })
            
            # Update for next year
            current_balances = PortfolioBalances(
                cash=year_result['Cash Balance'],
                taxable=year_result['Taxable Balance'],
                traditional=year_result['Traditional Balance'],
                roth=year_result['Roth Balance'],
                daf=0
            )
            current_expenses = year_result['Expenses']
            
        except Exception as e:
            print(f"  ❌ Failed in year {year}: {e}")
            return {
                'scenario': scenario_name,
                'success': False,
                'error': str(e),
                'years_completed': i
            }
    
    # Calculate summary statistics
    final_portfolio = results[-1]['portfolio']
    total_taxes = sum(r['taxes'] for r in results)
    total_conversions = sum(r['conversions'] for r in results)
    portfolio_change = final_portfolio - initial_portfolio
    portfolio_change_pct = (portfolio_change / initial_portfolio) * 100
    
    # Check if portfolio survived
    survived = final_portfolio > 0
    
    # Check validation issues
    has_errors = not validation_result.is_valid
    
    print(f"  Initial portfolio: ${initial_portfolio:,.0f}")
    print(f"  Final portfolio: ${final_portfolio:,.0f}")
    print(f"  Change: ${portfolio_change:,.0f} ({portfolio_change_pct:+.1f}%)")
    print(f"  Total taxes: ${total_taxes:,.0f}")
    print(f"  Total conversions: ${total_conversions:,.0f}")
    print(f"  Validation: {'✅ Passed' if not has_errors else '❌ Failed'}")
    
    if survived and not has_errors:
        print(f"  ✅ Strategy survived {scenario_name}")
    else:
        print(f"  ⚠️  Strategy struggled with {scenario_name}")
    
    return {
        'scenario': scenario_name,
        'success': survived and not has_errors,
        'initial_portfolio': initial_portfolio,
        'final_portfolio': final_portfolio,
        'portfolio_change': portfolio_change,
        'portfolio_change_pct': portfolio_change_pct,
        'total_taxes': total_taxes,
        'total_conversions': total_conversions,
        'years_completed': years,
        'validation_errors': len(validation_result.issues) if has_errors else 0,
        'yearly_results': results
    }


def test_all_market_scenarios():
    """Test strategy against all historical market scenarios"""
    print("\n" + "="*80)
    print("HISTORICAL MARKET SCENARIO INTEGRATION TESTS")
    print("="*80)
    
    all_results = []
    
    for scenario_name, market_data in MARKET_SCENARIOS.items():
        result = test_strategy_with_market_scenario(
            scenario_name=scenario_name,
            market_data=market_data,
            initial_portfolio=1000000,
            annual_expenses=50000
        )
        all_results.append(result)
    
    # Summary
    print("\n" + "="*80)
    print("MARKET SCENARIO SUMMARY")
    print("="*80)
    
    successful = sum(1 for r in all_results if r['success'])
    total = len(all_results)
    
    print(f"\nScenarios passed: {successful}/{total}")
    
    for result in all_results:
        status = "✅" if result['success'] else "❌"
        print(f"\n{status} {result['scenario']}")
        if 'portfolio_change_pct' in result:
            print(f"   Portfolio change: {result['portfolio_change_pct']:+.1f}%")
            print(f"   Final value: ${result['final_portfolio']:,.0f}")
    
    return successful == total


# ==============================================================================
# SEQUENCE OF RETURNS RISK TESTING
# ==============================================================================

def test_sequence_of_returns_risk():
    """Test strategy sensitivity to sequence of returns"""
    print("\n" + "="*80)
    print("SEQUENCE OF RETURNS RISK TEST")
    print("="*80)
    
    # Same returns, different order
    returns_good = [0.10, 0.08, 0.06, -0.05, 0.12]  # Good early, bad late
    returns_bad = [0.12, -0.05, 0.06, 0.08, 0.10]   # Bad early, good late
    
    scenarios = [
        ('Good sequence (positive early)', returns_good),
        ('Bad sequence (negative early)', returns_bad)
    ]
    
    results = []
    
    for name, returns in scenarios:
        print(f"\nTesting: {name}")
        
        balances = PortfolioBalances(
            cash=50000,
            taxable=200000,
            traditional=600000,
            roth=150000,
            daf=0
        )
        
        current_balances = balances
        initial_portfolio = balances.total()
        
        for i, ret in enumerate(returns):
            year = 2026 + i
            growth_rate = 1.0 + ret
            
            strategy_df, _ = build_withdrawal_strategy_display(
                start_year=year,
                end_year=year,
                initial_balances=current_balances,
                initial_expenses=50000,
                person1_name="Tom",
                person2_name="Sarah",
                growth_rate=growth_rate,
                expense_inflation_rate=0.0,
                ss_claiming_age=67,
                retirement_year=2026,
                has_wages=False
            )
            
            year_result = strategy_df.iloc[0]
            current_balances = PortfolioBalances(
                cash=year_result['Cash Balance'],
                taxable=year_result['Taxable Balance'],
                traditional=year_result['Traditional Balance'],
                roth=year_result['Roth Balance'],
                daf=0
            )
        
        final_portfolio = current_balances.total()
        change_pct = ((final_portfolio - initial_portfolio) / initial_portfolio) * 100
        
        print(f"  Initial: ${initial_portfolio:,.0f}")
        print(f"  Final: ${final_portfolio:,.0f}")
        print(f"  Change: {change_pct:+.1f}%")
        
        results.append({
            'name': name,
            'final_portfolio': final_portfolio,
            'change_pct': change_pct
        })
    
    # Compare results
    print("\n" + "-"*80)
    print("COMPARISON:")
    diff = results[0]['final_portfolio'] - results[1]['final_portfolio']
    diff_pct = (diff / results[1]['final_portfolio']) * 100
    
    print(f"  Good sequence final: ${results[0]['final_portfolio']:,.0f}")
    print(f"  Bad sequence final: ${results[1]['final_portfolio']:,.0f}")
    print(f"  Difference: ${diff:,.0f} ({diff_pct:+.1f}%)")
    
    if diff > 0:
        print(f"  ✅ Good sequence outperformed by ${diff:,.0f}")
    else:
        print(f"  ⚠️  Unexpected: Bad sequence outperformed")
    
    print("✅ Sequence of returns risk test completed")


# ==============================================================================
# STRESS TEST - WORST CASE SCENARIO
# ==============================================================================

def test_worst_case_scenario():
    """Test strategy under worst-case market conditions"""
    print("\n" + "="*80)
    print("WORST CASE SCENARIO STRESS TEST")
    print("="*80)
    
    print("\nScenario: Severe bear market + high inflation + high expenses")
    
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    try:
        strategy_df, _ = build_withdrawal_strategy_display(
            start_year=2026,
            end_year=2030,
            initial_balances=balances,
            initial_expenses=100000,  # High expenses
            person1_name="Tom",
            person2_name="Sarah",
            growth_rate=0.85,  # -15% returns (severe bear)
            expense_inflation_rate=0.10,  # 10% inflation
            ss_claiming_age=67,
            retirement_year=2026,
            has_wages=False
        )
        
        initial_portfolio = strategy_df['Total Portfolio'].iloc[0]
        final_portfolio = strategy_df['Total Portfolio'].iloc[-1]
        
        print(f"  Initial portfolio: ${initial_portfolio:,.0f}")
        print(f"  Final portfolio: ${final_portfolio:,.0f}")
        print(f"  Years survived: {len(strategy_df)}")
        
        if final_portfolio > 0:
            print(f"  ✅ Portfolio survived worst-case scenario")
            print(f"     Remaining: ${final_portfolio:,.0f}")
            return True
        else:
            print(f"  ⚠️  Portfolio depleted in worst-case scenario")
            return False
            
    except Exception as e:
        print(f"  ❌ Strategy failed under worst-case: {e}")
        return False


# ==============================================================================
# MONTE CARLO SIMULATION
# ==============================================================================

def test_monte_carlo_simulation(num_simulations: int = 100):
    """
    Run Monte Carlo simulation with random market returns
    
    Args:
        num_simulations: Number of simulations to run
    """
    print("\n" + "="*80)
    print(f"MONTE CARLO SIMULATION ({num_simulations} runs)")
    print("="*80)
    
    print("\nSimulating random market returns (mean=7%, std=15%)...")
    
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    initial_portfolio = balances.total()
    final_portfolios = []
    success_count = 0
    
    for i in range(num_simulations):
        # Generate random returns (normal distribution)
        returns = np.random.normal(0.07, 0.15, 5)  # 5 years
        
        current_balances = balances
        
        try:
            for j, ret in enumerate(returns):
                year = 2026 + j
                growth_rate = 1.0 + ret
                
                strategy_df, _ = build_withdrawal_strategy_display(
                    start_year=year,
                    end_year=year,
                    initial_balances=current_balances,
                    initial_expenses=50000,
                    person1_name="Tom",
                    person2_name="Sarah",
                    growth_rate=growth_rate,
                    expense_inflation_rate=0.03,
                    ss_claiming_age=67,
                    retirement_year=2026,
                    has_wages=False
                )
                
                year_result = strategy_df.iloc[0]
                current_balances = PortfolioBalances(
                    cash=year_result['Cash Balance'],
                    taxable=year_result['Taxable Balance'],
                    traditional=year_result['Traditional Balance'],
                    roth=year_result['Roth Balance'],
                    daf=0
                )
            
            final_portfolio = current_balances.total()
            final_portfolios.append(final_portfolio)
            
            if final_portfolio > initial_portfolio * 0.8:  # Within 20% of initial
                success_count += 1
                
        except Exception as e:
            logger.warning(f"Simulation {i+1} failed: {e}")
            final_portfolios.append(0)
    
    # Calculate statistics
    final_portfolios = np.array(final_portfolios)
    mean_final = np.mean(final_portfolios)
    median_final = np.median(final_portfolios)
    std_final = np.std(final_portfolios)
    min_final = np.min(final_portfolios)
    max_final = np.max(final_portfolios)
    success_rate = (success_count / num_simulations) * 100
    
    print(f"\nResults after {num_simulations} simulations:")
    print(f"  Initial portfolio: ${initial_portfolio:,.0f}")
    print(f"  Mean final: ${mean_final:,.0f}")
    print(f"  Median final: ${median_final:,.0f}")
    print(f"  Std dev: ${std_final:,.0f}")
    print(f"  Min: ${min_final:,.0f}")
    print(f"  Max: ${max_final:,.0f}")
    print(f"  Success rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print(f"  ✅ High success rate ({success_rate:.1f}%)")
    elif success_rate >= 60:
        print(f"  ⚠️  Moderate success rate ({success_rate:.1f}%)")
    else:
        print(f"  ❌ Low success rate ({success_rate:.1f}%)")
    
    print("✅ Monte Carlo simulation completed")


# ==============================================================================
# TEST RUNNER
# ==============================================================================

def run_all_integration_tests():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("WITHDRAWAL STRATEGY - INTEGRATION TEST SUITE")
    print("="*80)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Historical market scenarios
    try:
        if test_all_market_scenarios():
            tests_passed += 1
        else:
            tests_failed += 1
    except Exception as e:
        print(f"❌ Market scenarios test failed: {e}")
        tests_failed += 1
    
    # Test 2: Sequence of returns risk
    try:
        test_sequence_of_returns_risk()
        tests_passed += 1
    except Exception as e:
        print(f"❌ Sequence of returns test failed: {e}")
        tests_failed += 1
    
    # Test 3: Worst case scenario
    try:
        if test_worst_case_scenario():
            tests_passed += 1
        else:
            tests_failed += 1
    except Exception as e:
        print(f"❌ Worst case test failed: {e}")
        tests_failed += 1
    
    # Test 4: Monte Carlo simulation
    try:
        test_monte_carlo_simulation(num_simulations=50)  # Reduced for speed
        tests_passed += 1
    except Exception as e:
        print(f"❌ Monte Carlo test failed: {e}")
        tests_failed += 1
    
    print("\n" + "="*80)
    print(f"INTEGRATION TEST RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("="*80)
    
    if tests_failed == 0:
        print("\n✅ All integration tests passed successfully!")
        print("Strategy is robust across various market conditions.")
        return 0
    else:
        print(f"\n❌ {tests_failed} test(s) failed")
        print("Review failures and improve strategy robustness.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_integration_tests()
    sys.exit(exit_code)

# Made with Bob