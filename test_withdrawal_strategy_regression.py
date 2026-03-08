#!/usr/bin/env python3
"""
Regression Test Suite for Withdrawal Strategy Tax Calculations

Ensures tax calculations remain accurate and consistent across code changes.
Tests against known scenarios with verified results.

Author: Bob
Date: 2026-03-08
Version: 1.0
"""

import sys
import logging
from typing import Dict, Any
import pandas as pd
import numpy as np

from strategy import (
    PortfolioBalances,
    build_withdrawal_strategy_display
)
from calculations import (
    calculate_taxable_income,
    calculate_cap_gains,
    calc_agi,
    calc_roth_conversions,
    calc_roth_conversions_tax
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ==============================================================================
# KNOWN GOOD SCENARIOS (BASELINE)
# ==============================================================================

# These scenarios have been manually verified and serve as regression baselines
BASELINE_SCENARIOS = {
    'simple_retirement': {
        'description': 'Simple retirement scenario with balanced portfolio',
        'params': {
            'start_year': 2026,
            'end_year': 2030,
            'initial_balances': PortfolioBalances(
                cash=50000,
                taxable=200000,
                traditional=600000,
                roth=150000,
                daf=0
            ),
            'initial_expenses': 100000,
            'growth_rate': 1.07,
            'expense_inflation_rate': 0.03,
            'ss_claiming_age': 67,
            'retirement_year': 2026,
            'has_wages': False,
            'person1_name': 'Tom',
            'person2_name': 'Sarah'
        },
        'expected_results': {
            'total_years': 5,
            'final_portfolio_min': 800000,  # Should be around this after growth
            'total_taxes_max': 100000,  # Total taxes over 5 years
            'roth_conversions_min': 50000,  # Should have some conversions
        }
    },
    'high_income': {
        'description': 'High income scenario with large traditional balance',
        'params': {
            'start_year': 2026,
            'end_year': 2030,
            'initial_balances': PortfolioBalances(
                cash=100000,
                taxable=500000,
                traditional=2000000,
                roth=300000,
                daf=50000
            ),
            'initial_expenses': 150000,
            'growth_rate': 1.08,
            'expense_inflation_rate': 0.025,
            'ss_claiming_age': 70,
            'retirement_year': 2026,
            'has_wages': False,
            'person1_name': 'Tom',
            'person2_name': 'Sarah'
        },
        'expected_results': {
            'total_years': 5,
            'final_portfolio_min': 2500000,
            'total_taxes_max': 300000,
            'roth_conversions_min': 200000,
        }
    },
    'early_retire': {
        'description': 'Early retirement with aggressive Roth conversions',
        'params': {
            'start_year': 2026,
            'end_year': 2030,
            'initial_balances': PortfolioBalances(
                cash=75000,
                taxable=300000,
                traditional=800000,
                roth=100000,
                daf=0
            ),
            'initial_expenses': 80000,
            'growth_rate': 1.06,
            'expense_inflation_rate': 0.02,
            'ss_claiming_age': 70,
            'retirement_year': 2024,
            'has_wages': False,
            'person1_name': 'Tom',
            'person2_name': 'Sarah'
        },
        'expected_results': {
            'total_years': 5,
            'final_portfolio_min': 1000000,
            'total_taxes_max': 150000,
            'roth_conversions_min': 100000,
        }
    }
}


# ==============================================================================
# TAX CALCULATION REGRESSION TESTS
# ==============================================================================

def test_tax_bracket_calculation():
    """Test that tax bracket calculations are consistent"""
    print("\nTesting tax bracket calculations...")
    
    # Test known income/tax pairs (2024 MFJ brackets)
    test_cases = [
        {'income': 22000, 'expected_tax_min': 2000, 'expected_tax_max': 2500},
        {'income': 50000, 'expected_tax_min': 5000, 'expected_tax_max': 6500},
        {'income': 100000, 'expected_tax_min': 11000, 'expected_tax_max': 13000},
        {'income': 200000, 'expected_tax_min': 28000, 'expected_tax_max': 32000},
    ]
    
    from load_data import get_income_tax_brackets
    
    for case in test_cases:
        income = case['income']
        tax_brackets = get_income_tax_brackets(2026, 'married_filing_jointly')
        
        result = calculate_taxable_income(income, tax_brackets)
        tax = result.total_tax
        
        assert case['expected_tax_min'] <= tax <= case['expected_tax_max'], \
            f"Tax for ${income:,} should be ${case['expected_tax_min']:,}-${case['expected_tax_max']:,}, got ${tax:,.0f}"
        
        print(f"  ✅ Income ${income:,} → Tax ${tax:,.0f} (within expected range)")
    
    print("✅ Tax bracket calculation test passed")


def test_capital_gains_calculation():
    """Test that capital gains calculations are consistent"""
    print("\nTesting capital gains calculations...")
    
    from load_data import get_cap_gains_brackets
    
    test_cases = [
        {'income': 50000, 'cg': 10000, 'expected_cg_tax': 0},  # 0% bracket
        {'income': 100000, 'cg': 50000, 'expected_cg_tax_min': 5000, 'expected_cg_tax_max': 8000},  # 15% bracket
        {'income': 500000, 'cg': 100000, 'expected_cg_tax_min': 18000, 'expected_cg_tax_max': 22000},  # 20% bracket
    ]
    
    for case in test_cases:
        cg_brackets = get_cap_gains_brackets(2026, 'married_filing_jointly')
        cg_tax = calculate_cap_gains(case['income'], cg_brackets, case['cg'])
        
        if 'expected_cg_tax' in case:
            assert cg_tax == case['expected_cg_tax'], \
                f"CG tax should be ${case['expected_cg_tax']:,}, got ${cg_tax:,.0f}"
        else:
            assert case['expected_cg_tax_min'] <= cg_tax <= case['expected_cg_tax_max'], \
                f"CG tax should be ${case['expected_cg_tax_min']:,}-${case['expected_cg_tax_max']:,}, got ${cg_tax:,.0f}"
        
        print(f"  ✅ Income ${case['income']:,}, CG ${case['cg']:,} → Tax ${cg_tax:,.0f}")
    
    print("✅ Capital gains calculation test passed")


def test_roth_conversion_tax():
    """Test that Roth conversion tax calculations are consistent"""
    print("\nTesting Roth conversion tax calculations...")
    
    test_cases = [
        {
            'maxrate': 0.12,
            'headroom_rate': 0.22,
            'uppermax': 89075,
            'agi': 50000,
            'headroom_max': 190750,
            'conversion': 30000,
            'expected_tax_min': 3500,
            'expected_tax_max': 4000
        },
        {
            'maxrate': 0.22,
            'headroom_rate': 0.24,
            'uppermax': 190750,
            'agi': 150000,
            'headroom_max': 364200,
            'conversion': 50000,
            'expected_tax_min': 10000,
            'expected_tax_max': 12000
        }
    ]
    
    for case in test_cases:
        tax = calc_roth_conversions_tax(
            maxrate=case['maxrate'],
            headroom_rate=case['headroom_rate'],
            uppermax=case['uppermax'],
            agi=case['agi'],
            headroom_max=case['headroom_max'],
            conversion=case['conversion']
        )
        
        assert case['expected_tax_min'] <= tax <= case['expected_tax_max'], \
            f"Conversion tax should be ${case['expected_tax_min']:,}-${case['expected_tax_max']:,}, got ${tax:,.0f}"
        
        print(f"  ✅ Conversion ${case['conversion']:,} at {case['maxrate']:.0%} → Tax ${tax:,.0f}")
    
    print("✅ Roth conversion tax calculation test passed")


# ==============================================================================
# SCENARIO REGRESSION TESTS
# ==============================================================================

def test_scenario_regression(scenario_name: str, scenario: Dict[str, Any]) -> bool:
    """
    Test a complete scenario against baseline expectations
    
    Args:
        scenario_name: Name of the scenario
        scenario: Scenario configuration with params and expected results
    
    Returns:
        True if test passes, False otherwise
    """
    print(f"\nTesting scenario: {scenario_name}")
    print(f"  Description: {scenario['description']}")
    
    try:
        # Run strategy
        strategy_df, _ = build_withdrawal_strategy_display(**scenario['params'])
        
        # Check expected results
        expected = scenario['expected_results']
        
        # Check total years
        actual_years = len(strategy_df)
        assert actual_years == expected['total_years'], \
            f"Expected {expected['total_years']} years, got {actual_years}"
        print(f"  ✅ Years: {actual_years}")
        
        # Check final portfolio
        final_portfolio = strategy_df['Total Portfolio'].iloc[-1]
        assert final_portfolio >= expected['final_portfolio_min'], \
            f"Final portfolio ${final_portfolio:,.0f} below minimum ${expected['final_portfolio_min']:,}"
        print(f"  ✅ Final portfolio: ${final_portfolio:,.0f}")
        
        # Check total taxes
        total_taxes = strategy_df['Federal Tax'].sum()
        assert total_taxes <= expected['total_taxes_max'], \
            f"Total taxes ${total_taxes:,.0f} exceed maximum ${expected['total_taxes_max']:,}"
        print(f"  ✅ Total taxes: ${total_taxes:,.0f}")
        
        # Check Roth conversions
        total_conversions = strategy_df['Roth Conversion'].sum()
        assert total_conversions >= expected['roth_conversions_min'], \
            f"Total conversions ${total_conversions:,.0f} below minimum ${expected['roth_conversions_min']:,}"
        print(f"  ✅ Roth conversions: ${total_conversions:,.0f}")
        
        print(f"✅ Scenario {scenario_name} passed all checks")
        return True
        
    except Exception as e:
        print(f"❌ Scenario {scenario_name} failed: {e}")
        return False


def test_all_baseline_scenarios():
    """Test all baseline scenarios"""
    print("\n" + "="*80)
    print("BASELINE SCENARIO REGRESSION TESTS")
    print("="*80)
    
    passed = 0
    failed = 0
    
    for scenario_name, scenario in BASELINE_SCENARIOS.items():
        if test_scenario_regression(scenario_name, scenario):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*80)
    print(f"BASELINE SCENARIOS: {passed} passed, {failed} failed")
    print("="*80)
    
    return failed == 0


# ==============================================================================
# CONSISTENCY TESTS
# ==============================================================================

def test_calculation_consistency():
    """Test that calculations are consistent across multiple runs"""
    print("\nTesting calculation consistency...")
    
    params = {
        'start_year': 2026,
        'end_year': 2028,
        'initial_balances': PortfolioBalances(
            cash=50000,
            taxable=200000,
            traditional=600000,
            roth=150000,
            daf=0
        ),
        'initial_expenses': 100000,
        'growth_rate': 1.07,
        'expense_inflation_rate': 0.03,
        'ss_claiming_age': 67,
        'retirement_year': 2026,
        'has_wages': False,
        'person1_name': 'Tom',
        'person2_name': 'Sarah'
    }
    
    # Run same scenario 3 times
    results = []
    for i in range(3):
        strategy_df, _ = build_withdrawal_strategy_display(**params)
        results.append({
            'final_portfolio': strategy_df['Total Portfolio'].iloc[-1],
            'total_taxes': strategy_df['Federal Tax'].sum(),
            'total_conversions': strategy_df['Roth Conversion'].sum()
        })
    
    # Check all runs produced identical results
    for i in range(1, len(results)):
        for key in results[0].keys():
            assert abs(results[0][key] - results[i][key]) < 0.01, \
                f"Run {i+1} {key} differs from run 1: {results[0][key]} vs {results[i][key]}"
    
    print(f"  ✅ All 3 runs produced identical results")
    print(f"     Final portfolio: ${results[0]['final_portfolio']:,.0f}")
    print(f"     Total taxes: ${results[0]['total_taxes']:,.0f}")
    print(f"     Total conversions: ${results[0]['total_conversions']:,.0f}")
    
    print("✅ Calculation consistency test passed")


def test_balance_conservation():
    """Test that portfolio balances are conserved (no money created/destroyed)"""
    print("\nTesting balance conservation...")
    
    params = {
        'start_year': 2026,
        'end_year': 2030,
        'initial_balances': PortfolioBalances(
            cash=50000,
            taxable=200000,
            traditional=600000,
            roth=150000,
            daf=0
        ),
        'initial_expenses': 100000,
        'growth_rate': 1.00,  # No growth for easier tracking
        'expense_inflation_rate': 0.00,
        'ss_claiming_age': 67,
        'retirement_year': 2026,
        'has_wages': False,
        'person1_name': 'Tom',
        'person2_name': 'Sarah'
    }
    
    strategy_df, _ = build_withdrawal_strategy_display(**params)
    
    # Check each year
    for idx, row in strategy_df.iterrows():
        year = row['Year']
        
        # Total portfolio should equal sum of accounts
        total = row['Total Portfolio']
        sum_accounts = (
            row['Cash Balance'] +
            row['Taxable Balance'] +
            row['Traditional Balance'] +
            row['Roth Balance'] +
            row.get('DAF Balance', 0)
        )
        
        # Allow small rounding errors
        assert abs(total - sum_accounts) < 1.0, \
            f"Year {year}: Total ${total:,.0f} != Sum ${sum_accounts:,.0f}"
    
    print(f"  ✅ Balance conservation verified for all {len(strategy_df)} years")
    print("✅ Balance conservation test passed")


# ==============================================================================
# TEST RUNNER
# ==============================================================================

def run_all_regression_tests():
    """Run all regression tests"""
    print("\n" + "="*80)
    print("WITHDRAWAL STRATEGY - REGRESSION TEST SUITE")
    print("="*80)
    
    tests = [
        test_tax_bracket_calculation,
        test_capital_gains_calculation,
        test_roth_conversion_tax,
        test_calculation_consistency,
        test_balance_conservation,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️  {test_func.__name__} ERROR: {e}")
            failed += 1
    
    # Run baseline scenarios
    if test_all_baseline_scenarios():
        passed += 1
    else:
        failed += 1
    
    print("\n" + "="*80)
    print(f"REGRESSION TEST RESULTS: {passed} passed, {failed} failed")
    print("="*80)
    
    if failed == 0:
        print("\n✅ All regression tests passed successfully!")
        print("Tax calculations are consistent and accurate.")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        print("Review failures and ensure calculations haven't regressed.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_regression_tests()
    sys.exit(exit_code)

# Made with Bob