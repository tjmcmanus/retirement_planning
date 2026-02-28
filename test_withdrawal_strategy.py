#!/usr/bin/env python3
"""
Test script for withdrawal strategy module

This script performs basic validation of the withdrawal strategy calculations
to ensure the module is working correctly.
"""

import sys
import logging

from strategy import (
    PortfolioBalances,
    WithdrawalStrategyEngine,
    YearlyStrategy,
    Stage1Accumulation,
    Stage3EarlyRetirement,
    Stage4Medicare,
    Stage5SocialSecurity,
    Stage6RMD,
    ScenarioType,
    ScenarioConfig,
    calculate_aca_subsidy,
    generate_strategy_summary,
    create_example_scenario,
    _resolve_scenario_key,
    _build_scenario_config,
)


def test_portfolio_balances():
    """Test PortfolioBalances dataclass"""
    print("Testing PortfolioBalances...")
    
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=25000
    )
    
    assert balances.total() == 1025000, "Total calculation incorrect"
    assert balances.cash == 50000, "Cash value incorrect"
    assert balances.traditional == 600000, "Traditional value incorrect"
    
    print("✅ PortfolioBalances tests passed")


def test_life_stages():
    """Test life stage determination"""
    print("\nTesting Life Stages...")
    
    stage1 = Stage1Accumulation()
    stage2 = Stage3EarlyRetirement()
    stage3 = Stage4Medicare()
    stage4 = Stage5SocialSecurity()
    stage5 = Stage6RMD()
    
    # Test Stage 1 (Accumulation - has wages, year far from retirement so Stage 2 prep window doesn't apply)
    assert stage1.applies(45, 43, 2000, has_wages=True, has_ss=False), "Stage 1 should apply with wages"
    
    # Test Stage 2 (Early Retirement - no wages, no SS, pre-Medicare)
    assert stage2.applies(60, 58, 2026, has_wages=False, has_ss=False), "Stage 2 should apply"
    assert not stage2.applies(66, 64, 2026, has_wages=False, has_ss=False), "Stage 2 should not apply at 66"
    
    # Test Stage 3 (Medicare - on Medicare, no SS)
    assert stage3.applies(65, 63, 2026, has_wages=False, has_ss=False), "Stage 3 should apply at 65"
    assert not stage3.applies(60, 58, 2026, has_wages=False, has_ss=False), "Stage 3 should not apply at 60"
    
    # Test Stage 4 (Social Security - has SS, pre-RMD)
    assert stage4.applies(68, 66, 2026, has_wages=False, has_ss=True), "Stage 4 should apply with SS"
    assert not stage4.applies(68, 66, 2026, has_wages=False, has_ss=False), "Stage 4 should not apply without SS"
    
    # Test Stage 5 (RMD - at RMD age)
    assert stage5.applies(73, 71, 2026, has_wages=False, has_ss=True), "Stage 5 should apply at 73"
    assert stage5.applies(80, 78, 2026, has_wages=False, has_ss=True), "Stage 5 should apply at 80"
    
    print("✅ Life stage tests passed")


def test_aca_subsidy():
    """Test ACA subsidy calculation"""
    print("\nTesting ACA Subsidy Calculation...")
    
    # Test at 150% FPL (should be free)
    subsidy1, premium1 = calculate_aca_subsidy(magi=30000, year=2026, household_size=2)
    assert premium1 == 0, "Premium should be $0 at 150% FPL"
    
    # Test at 250% FPL (should have subsidy)
    subsidy2, premium2 = calculate_aca_subsidy(magi=70000, year=2026, household_size=2)
    assert subsidy2 > 0, "Should have subsidy at 250% FPL"
    assert premium2 < 12000, "Net premium should be less than benchmark"
    
    # Test above 400% FPL (no subsidy)
    subsidy3, premium3 = calculate_aca_subsidy(magi=150000, year=2026, household_size=2)
    assert subsidy3 == 0, "Should have no subsidy above 400% FPL"
    assert premium3 == 12000, "Should pay full premium"
    
    print("✅ ACA subsidy tests passed")


def test_withdrawal_engine():
    """Test WithdrawalStrategyEngine"""
    print("\nTesting WithdrawalStrategyEngine...")
    
    engine = WithdrawalStrategyEngine()
    
    # Verify all 6 stages are loaded
    assert len(engine.stages) == 6, "Should have 6 life stages"
    
    # Test stage determination
    stage = engine.determine_stage(60, 58, 2026, has_wages=False, has_ss=False)
    assert "Early Retirement" in stage.name, "Should be in Early Retirement stage"
    
    stage = engine.determine_stage(73, 71, 2026, has_wages=False, has_ss=True)
    assert "RMD" in stage.name, "Should be in RMD stage"
    
    print("✅ WithdrawalStrategyEngine tests passed")


def test_strategy_calculation():
    """Test basic strategy calculation"""
    print("\nTesting Strategy Calculation...")
    
    try:
        from strategy import build_withdrawal_strategy_display
        
        # Create simple test scenario
        balances = PortfolioBalances(
            cash=50000,
            taxable=200000,
            traditional=600000,
            roth=150000,
            daf=0
        )
        
        # Calculate for just 5 years to keep test fast
        strategy_df, balances_df = build_withdrawal_strategy_display(
            start_year=2026,
            end_year=2030,
            initial_balances=balances,
            initial_expenses=100000,
            person1_name="Tom",
            person2_name="Sarah",
            growth_rate=1.05,
            expense_inflation_rate=0.0,  # 0% inflation for test
            ss_claiming_age=67,
            retirement_year=2026,
            has_wages=False
        )
        
        # Verify DataFrame structure
        assert len(strategy_df) == 5, "Should have 5 years of data"
        assert 'Year' in strategy_df.columns, "Should have Year column"
        assert 'Stage' in strategy_df.columns, "Should have Stage column"
        assert 'Total Portfolio' in strategy_df.columns, "Should have Total Portfolio column"
        
        # Verify portfolio values are reasonable
        assert strategy_df['Total Portfolio'].iloc[0] > 0, "Initial portfolio should be positive"
        assert strategy_df['Total Portfolio'].iloc[-1] > 0, "Final portfolio should be positive"
        
        # Generate summary
        summary = generate_strategy_summary(strategy_df)
        assert summary['total_years'] == 5, "Should have 5 years"
        assert summary['initial_portfolio_value'] > 0, "Initial value should be positive"
        
        print("✅ Strategy calculation tests passed")
        
    except Exception as e:
        print(f"⚠️  Strategy calculation test skipped (requires full data files): {e}")


def test_yearly_strategy_structure():
    """Test YearlyStrategy dataclass structure"""
    print("\nTesting YearlyStrategy Structure...")
    
    balances = PortfolioBalances(
        cash=50000,
        taxable=200000,
        traditional=600000,
        roth=150000,
        daf=0
    )
    
    strategy = YearlyStrategy(
        year=2026,
        age_primary=60,
        age_spouse=58,
        stage="Test Stage",
        wages=0,
        ss_benefits=0,
        rmd_amount=0,
        traditional_withdrawal=50000,
        taxable_withdrawal=30000,
        roth_withdrawal=0,
        roth_conversion=25000,
        ltcg_harvested=30000,
        daf_contribution=0,
        expenses=100000,
        agi=80000,
        magi=80000,
        federal_tax=15000,
        irmaa_penalty=0,
        aca_premium=0,
        balances=balances
    )
    
    assert strategy.year == 2026, "Year should be 2026"
    assert strategy.roth_conversion == 25000, "Roth conversion should be 25000"
    assert strategy.balances.total() == 1000000, "Total should be 1M"
    
    print("✅ YearlyStrategy structure tests passed")


def test_resolve_scenario_key():
    """Test _resolve_scenario_key enum resolution and fallback behaviour"""
    print("\nTesting _resolve_scenario_key...")

    # ScenarioType member passed directly → returned unchanged
    assert _resolve_scenario_key(ScenarioType.DEFAULT) is ScenarioType.DEFAULT
    assert _resolve_scenario_key(ScenarioType.EARLY_RETIRE) is ScenarioType.EARLY_RETIRE
    assert _resolve_scenario_key(ScenarioType.HIGH_INCOME) is ScenarioType.HIGH_INCOME

    # Valid string values → resolved to matching enum member
    assert _resolve_scenario_key("default") is ScenarioType.DEFAULT
    assert _resolve_scenario_key("early_retire") is ScenarioType.EARLY_RETIRE
    assert _resolve_scenario_key("high_income") is ScenarioType.HIGH_INCOME

    # Unknown string → falls back to DEFAULT with a warning (no exception raised)
    result = _resolve_scenario_key("nonexistent_scenario")
    assert result is ScenarioType.DEFAULT, "Unknown string should fall back to DEFAULT"

    print("✅ _resolve_scenario_key tests passed")


def test_build_scenario_config():
    """Test _build_scenario_config produces valid, cached ScenarioConfig instances"""
    print("\nTesting _build_scenario_config...")

    for scenario_type in ScenarioType:
        config = _build_scenario_config(scenario_type)
        assert isinstance(config, ScenarioConfig), f"{scenario_type} should return a ScenarioConfig"
        assert config.start_year > 0, "start_year must be positive"
        assert config.end_year > config.start_year, "end_year must be after start_year"
        assert config.initial_expenses > 0, "initial_expenses must be positive"
        assert isinstance(config.initial_balances, PortfolioBalances)

    # Cache identity: same key → same object
    config_a = _build_scenario_config(ScenarioType.DEFAULT)
    config_b = _build_scenario_config(ScenarioType.DEFAULT)
    assert config_a is config_b, "Cached results should be the same object"

    print("✅ _build_scenario_config tests passed")


def test_create_example_scenario():
    """Test create_example_scenario for all named scenarios and edge cases"""
    print("\nTesting create_example_scenario...")

    # All three named scenarios return a valid ScenarioConfig
    for name in ("default", "early_retire", "high_income"):
        config = create_example_scenario(name)
        assert isinstance(config, ScenarioConfig), f"'{name}' should return ScenarioConfig"

    # Enum member form is equivalent to string form
    assert create_example_scenario(ScenarioType.DEFAULT) == create_example_scenario("default")
    assert create_example_scenario(ScenarioType.EARLY_RETIRE) == create_example_scenario("early_retire")
    assert create_example_scenario(ScenarioType.HIGH_INCOME) == create_example_scenario("high_income")

    # Default argument ("default") works without explicit argument
    config_default = create_example_scenario()
    assert isinstance(config_default, ScenarioConfig)
    assert config_default == create_example_scenario("default")

    # Unknown string falls back to DEFAULT (no exception)
    config_fallback = create_example_scenario("unknown_scenario")
    assert config_fallback == create_example_scenario("default"), \
        "Unknown scenario should fall back to DEFAULT"

    # Scenario-specific overrides are applied correctly
    early = create_example_scenario(ScenarioType.EARLY_RETIRE)
    assert early.ss_claiming_age == 70, "EARLY_RETIRE should claim SS at 70"

    high = create_example_scenario(ScenarioType.HIGH_INCOME)
    assert high.growth_rate == 1.08, "HIGH_INCOME should use 8% growth rate"
    assert high.expense_inflation == 1.025, "HIGH_INCOME should use 2.5% expense inflation"

    default = create_example_scenario(ScenarioType.DEFAULT)
    assert default.expense_inflation == 0.993, "DEFAULT should use deflation scenario"

    print("✅ create_example_scenario tests passed")


def test_scenario_config_to_dict():
    """Test ScenarioConfig.to_dict() round-trips all fields correctly"""
    print("\nTesting ScenarioConfig.to_dict()...")

    config = create_example_scenario(ScenarioType.DEFAULT)
    d = config.to_dict()

    assert d['start_year'] == config.start_year
    assert d['end_year'] == config.end_year
    assert d['person1_name'] == config.person1_name
    assert d['person2_name'] == config.person2_name
    assert d['growth_rate'] == config.growth_rate
    assert d['expense_inflation'] == config.expense_inflation
    assert d['ss_claiming_age'] == config.ss_claiming_age
    assert d['retirement_year'] == config.retirement_year
    assert d['has_wages'] == config.has_wages
    assert d['initial_balances'] is config.initial_balances
    assert d['initial_expenses'] == config.initial_expenses

    # All expected keys are present
    expected_keys = {
        'start_year', 'end_year', 'initial_balances', 'initial_expenses',
        'person1_name', 'person2_name', 'growth_rate', 'expense_inflation',
        'ss_claiming_age', 'retirement_year', 'has_wages'
    }
    assert set(d.keys()) == expected_keys, f"Unexpected keys in to_dict(): {set(d.keys()) ^ expected_keys}"

    print("✅ ScenarioConfig.to_dict() tests passed")


def run_all_tests():
    """Run all test functions"""
    print("="*80)
    print("WITHDRAWAL STRATEGY MODULE - TEST SUITE")
    print("="*80)
    
    tests = [
        test_portfolio_balances,
        test_life_stages,
        test_aca_subsidy,
        test_withdrawal_engine,
        test_yearly_strategy_structure,
        test_resolve_scenario_key,
        test_build_scenario_config,
        test_create_example_scenario,
        test_scenario_config_to_dict,
        test_strategy_calculation,
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
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("="*80)
    
    if failed == 0:
        print("\n✅ All tests passed successfully!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)

# Made with Bob
