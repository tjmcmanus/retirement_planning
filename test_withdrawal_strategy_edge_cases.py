#!/usr/bin/env python3
"""
Comprehensive Edge Case Testing for Withdrawal Strategy

Tests edge cases, boundary conditions, and error handling to ensure
production-ready robustness.

Author: Bob
Date: 2026-03-08
Version: 1.0
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any
import sys
import logging

from strategy import (
    PortfolioBalances,
    WithdrawalStrategyEngine,
    build_withdrawal_strategy_display,
    YearlyStrategy
)
from withdrawal_strategy_validation import (
    validate_withdrawal_scenario,
    validate_yearly_strategy,
    ValidationResult,
    ValidationSeverity,
    check_irmaa_cliff_proximity,
    check_aca_subsidy_optimization,
    check_roth_conversion_opportunity,
    analyze_strategy_optimizations
)

# Configure logging for tests
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ==============================================================================
# EDGE CASE TESTS - ZERO BALANCES
# ==============================================================================

def test_zero_cash_balance():
    """Test strategy with zero cash balance"""
    balances = PortfolioBalances(
        cash=0,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2028,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 3
    assert strategy_df['Total Portfolio'].iloc[0] > 0
    print("✅ Zero cash balance test passed")


def test_zero_taxable_balance():
    """Test strategy with zero taxable balance"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=0,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2028,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 3
    print("✅ Zero taxable balance test passed")


def test_zero_traditional_balance():
    """Test strategy with zero traditional balance (Roth-only portfolio)"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=0,
        roth=600000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2028,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 3
    # Should have no Roth conversions with zero traditional balance
    assert strategy_df['Roth Conversion'].sum() == 0
    print("✅ Zero traditional balance test passed")


def test_zero_roth_balance():
    """Test strategy with zero Roth balance"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=0,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2028,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 3
    # May have Roth conversions to build Roth balance
    print("✅ Zero Roth balance test passed")


def test_all_accounts_zero_except_one():
    """Test with only one account having balance"""
    balances = PortfolioBalances(
        cash=0,
        taxable=0,
        traditional=500000,
        roth=0,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2028,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 3
    assert strategy_df['Total Portfolio'].iloc[0] == 500000
    print("✅ Single account balance test passed")


# ==============================================================================
# EDGE CASE TESTS - EXTREME AGES
# ==============================================================================

def test_very_young_retirement():
    """Test early retirement at age 50"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    # Birth year for age 50 in 2026
    from config import get_config_manager
    config = get_config_manager()
    config.set("personal_info", "person1_birth_date", "1976-01-01")
    config.set("personal_info", "person2_birth_date", "1978-01-01")
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2030,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 5
    # Should be in early retirement stage
    assert "Early Retirement" in strategy_df['Stage'].iloc[0] or "Prep" in strategy_df['Stage'].iloc[0]
    print("✅ Very young retirement test passed")


def test_very_old_age():
    """Test strategy extending to age 100+"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    from config import get_config_manager
    config = get_config_manager()
    config.set("personal_info", "person1_birth_date", "1950-01-01")
    config.set("personal_info", "person2_birth_date", "1952-01-01")
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2050,  # Age 100
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2020,
        has_wages=False
    )
    
    assert len(strategy_df) == 25
    # Should be in RMD stage for later years
    assert "RMD" in strategy_df['Stage'].iloc[-1]
    print("✅ Very old age test passed")


# ==============================================================================
# EDGE CASE TESTS - EXTREME RETURNS
# ==============================================================================

def test_negative_returns():
    """Test strategy with negative market returns (bear market)"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2030,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=0.90,  # -10% returns
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 5
    # Portfolio should decline
    assert strategy_df['Total Portfolio'].iloc[-1] < strategy_df['Total Portfolio'].iloc[0]
    print("✅ Negative returns test passed")


def test_zero_growth():
    """Test strategy with zero growth (0% returns)"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2030,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.00,  # 0% returns
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 5
    print("✅ Zero growth test passed")


def test_high_inflation():
    """Test strategy with high inflation (10%)"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2030,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.10,  # 10% inflation
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 5
    # Expenses should increase significantly
    assert strategy_df['Expenses'].iloc[-1] > strategy_df['Expenses'].iloc[0] * 1.4
    print("✅ High inflation test passed")


# ==============================================================================
# EDGE CASE TESTS - BOUNDARY CONDITIONS
# ==============================================================================

def test_ss_claiming_at_62():
    """Test Social Security claiming at minimum age (62)"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2030,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=62,  # Minimum age
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 5
    print("✅ SS claiming at 62 test passed")


def test_ss_claiming_at_70():
    """Test Social Security claiming at maximum age (70)"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2035,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=70,  # Maximum age
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 10
    print("✅ SS claiming at 70 test passed")


def test_rmd_age_boundary():
    """Test RMD calculations at age 73 (current RMD age)"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    from config import get_config_manager
    config = get_config_manager()
    # Set birth year so person is 73 in 2026
    config.set("personal_info", "person1_birth_date", "1953-01-01")
    config.set("personal_info", "person2_birth_date", "1955-01-01")
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2030,
        initial_balances=balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2020,
        has_wages=False
    )
    
    assert len(strategy_df) == 5
    # Should have RMDs
    assert strategy_df['RMD Amount'].sum() > 0
    print("✅ RMD age boundary test passed")


# ==============================================================================
# VALIDATION TESTS
# ==============================================================================

def test_validation_negative_balance():
    """Test validation catches negative balances"""
    result = validate_withdrawal_scenario(
        start_year=2026,
        end_year=2030,
        initial_balances={'cash': -1000, 'taxable': 200000, 'traditional': 600000, 'roth': 150000},
        initial_expenses=50000,
        growth_rate=1.05,
        expense_inflation_rate=0.03,
        ss_claiming_age=67,
        retirement_year=2026
    )
    
    assert not result.is_valid
    assert any("negative" in issue.message.lower() for issue in result.issues)
    print("✅ Validation negative balance test passed")


def test_validation_invalid_ss_age():
    """Test validation catches invalid SS claiming age"""
    result = validate_withdrawal_scenario(
        start_year=2026,
        end_year=2030,
        initial_balances={'cash': 50000, 'taxable': 200000, 'traditional': 600000, 'roth': 150000},
        initial_expenses=50000,
        growth_rate=1.05,
        expense_inflation_rate=0.03,
        ss_claiming_age=55,  # Too young
        retirement_year=2026
    )
    
    assert not result.is_valid
    assert any("social security" in issue.message.lower() for issue in result.issues)
    print("✅ Validation invalid SS age test passed")


def test_validation_extreme_growth_rate():
    """Test validation warns about extreme growth rates"""
    result = validate_withdrawal_scenario(
        start_year=2026,
        end_year=2030,
        initial_balances={'cash': 50000, 'taxable': 200000, 'traditional': 600000, 'roth': 150000},
        initial_expenses=50000,
        growth_rate=1.50,  # 50% - unrealistic
        expense_inflation_rate=0.03,
        ss_claiming_age=67,
        retirement_year=2026
    )
    
    assert result.has_warnings()
    assert any("growth rate" in warning.message.lower() for warning in result.warnings)
    print("✅ Validation extreme growth rate test passed")


def test_validation_insufficient_portfolio():
    """Test validation warns about insufficient portfolio"""
    result = validate_withdrawal_scenario(
        start_year=2026,
        end_year=2030,
        initial_balances={'cash': 10000, 'taxable': 20000, 'traditional': 30000, 'roth': 15000},
        initial_expenses=50000,  # More than portfolio can sustain
        growth_rate=1.05,
        expense_inflation_rate=0.03,
        ss_claiming_age=67,
        retirement_year=2026
    )
    
    assert result.has_warnings()
    assert any("sustainability" in warning.message.lower() for warning in result.warnings)
    print("✅ Validation insufficient portfolio test passed")


# ==============================================================================
# OPTIMIZATION WARNING TESTS
# ==============================================================================

def test_irmaa_cliff_detection():
    """Test IRMAA cliff proximity detection"""
    # Just below threshold
    warning = check_irmaa_cliff_proximity(magi=204000, year=2026)
    assert warning is not None
    assert "IRMAA" in warning.category
    print("✅ IRMAA cliff detection test passed")


def test_aca_subsidy_optimization():
    """Test ACA subsidy optimization detection"""
    # Just above free coverage threshold
    warning = check_aca_subsidy_optimization(magi=32000, household_size=2)
    assert warning is not None
    assert "ACA" in warning.category
    print("✅ ACA subsidy optimization test passed")


def test_roth_conversion_opportunity():
    """Test Roth conversion opportunity detection"""
    warning = check_roth_conversion_opportunity(
        traditional_balance=800000,
        current_tax_rate=0.12,
        age=60,
        years_to_rmd=13
    )
    assert warning is not None
    assert "Roth" in warning.category
    print("✅ Roth conversion opportunity test passed")


# ==============================================================================
# STRESS TESTS
# ==============================================================================

def test_portfolio_depletion():
    """Test strategy when portfolio is depleted"""
    balances = PortfolioBalances(
        cash=10000,
        taxable=20000,
        traditional=30000,
        roth=15000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2035,
        initial_balances=balances,
        initial_expenses=50000,  # Will deplete portfolio
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.00,  # No growth
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 10
    # Portfolio should be depleted or near zero
    assert strategy_df['Total Portfolio'].iloc[-1] < 10000
    print("✅ Portfolio depletion test passed")


def test_very_high_expenses():
    """Test with expenses exceeding portfolio income"""
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy_df, _ = build_withdrawal_strategy_display(
        start_year=2026,
        end_year=2030,
        initial_balances=balances,
        initial_expenses=200000,  # Very high expenses
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.05,
        expense_inflation_rate=0.0,
        ss_claiming_age=67,
        retirement_year=2026,
        has_wages=False
    )
    
    assert len(strategy_df) == 5
    # Portfolio should decline significantly
    assert strategy_df['Total Portfolio'].iloc[-1] < strategy_df['Total Portfolio'].iloc[0] * 0.5
    print("✅ Very high expenses test passed")


# ==============================================================================
# TEST RUNNER
# ==============================================================================

def run_all_edge_case_tests():
    """Run all edge case tests"""
    print("\n" + "="*80)
    print("WITHDRAWAL STRATEGY - EDGE CASE TEST SUITE")
    print("="*80)
    
    tests = [
        # Zero balance tests
        test_zero_cash_balance,
        test_zero_taxable_balance,
        test_zero_traditional_balance,
        test_zero_roth_balance,
        test_all_accounts_zero_except_one,
        
        # Extreme age tests
        test_very_young_retirement,
        test_very_old_age,
        
        # Extreme return tests
        test_negative_returns,
        test_zero_growth,
        test_high_inflation,
        
        # Boundary condition tests
        test_ss_claiming_at_62,
        test_ss_claiming_at_70,
        test_rmd_age_boundary,
        
        # Validation tests
        test_validation_negative_balance,
        test_validation_invalid_ss_age,
        test_validation_extreme_growth_rate,
        test_validation_insufficient_portfolio,
        
        # Optimization tests
        test_irmaa_cliff_detection,
        test_aca_subsidy_optimization,
        test_roth_conversion_opportunity,
        
        # Stress tests
        test_portfolio_depletion,
        test_very_high_expenses,
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
    
    print("\n" + "="*80)
    print(f"EDGE CASE TEST RESULTS: {passed} passed, {failed} failed")
    print("="*80)
    
    if failed == 0:
        print("\n✅ All edge case tests passed successfully!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_edge_case_tests()
    sys.exit(exit_code)

# Made with Bob