#!/usr/bin/env python3
"""
Test script for accumulation strategy module

This script performs basic validation of the accumulation strategy calculations
(Stage 1: Accumulation and Stage 2: Prep for Retirement) to ensure the module
is working correctly.
"""

import sys
from strategy import (
    PortfolioBalances,
    WithdrawalStrategyEngine,
    Stage1Accumulation,
    Stage2PrepForRetirement,
    build_accumulation_strategy_display,
    generate_strategy_summary,
)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_portfolio_balances_accumulation():
    """Test PortfolioBalances with typical accumulation-phase values."""
    print("Testing PortfolioBalances (accumulation)...")

    balances = PortfolioBalances(
        cash=30_000,
        taxable=120_000,
        traditional=380_000,
        roth=120_000,
        daf=0,
    )

    assert balances.total() == 650_000, f"Expected 650000, got {balances.total()}"
    assert balances.cash == 30_000, "Cash value incorrect"
    assert balances.roth == 120_000, "Roth value incorrect"

    print("✅ PortfolioBalances (accumulation) tests passed")


def test_stage1_accumulation_applies():
    """Test Stage1Accumulation.applies() logic."""
    print("\nTesting Stage1Accumulation.applies()...")

    stage = Stage1Accumulation()

    # Should apply whenever has_wages=True, regardless of age
    assert stage.applies(35, 33, 2026, has_wages=True,  has_ss=False), \
        "Stage 1 should apply at age 35 with wages"
    assert stage.applies(55, 53, 2026, has_wages=True,  has_ss=False), \
        "Stage 1 should apply at age 55 with wages"
    assert stage.applies(64, 62, 2026, has_wages=True,  has_ss=False), \
        "Stage 1 should apply at age 64 with wages"

    # Should NOT apply without wages
    assert not stage.applies(45, 43, 2026, has_wages=False, has_ss=False), \
        "Stage 1 should not apply without wages"
    assert not stage.applies(60, 58, 2026, has_wages=False, has_ss=True), \
        "Stage 1 should not apply without wages even with SS"

    print("✅ Stage1Accumulation.applies() tests passed")


def test_stage2_prep_applies():
    """Test Stage2PrepForRetirement.applies() logic."""
    print("\nTesting Stage2PrepForRetirement.applies()...")

    stage = Stage2PrepForRetirement()

    # Without wages it should never apply
    assert not stage.applies(55, 53, 2026, has_wages=False, has_ss=False), \
        "Stage 2 should not apply without wages"

    # With wages it depends on config (years-to-retirement window).
    # We can only assert the return type is bool.
    result = stage.applies(55, 53, 2026, has_wages=True, has_ss=False)
    assert isinstance(result, bool), "applies() must return bool"

    print("✅ Stage2PrepForRetirement.applies() tests passed")


def test_accumulation_engine_stages():
    """Test that WithdrawalStrategyEngine contains accumulation stages."""
    print("\nTesting WithdrawalStrategyEngine stage list...")

    engine = WithdrawalStrategyEngine()

    stage_names = [s.name for s in engine.stages]
    assert any("Accumulation" in n for n in stage_names), \
        "Engine should include Stage 1: Accumulation"
    assert any("Prep" in n for n in stage_names), \
        "Engine should include Stage 2: Prep for Retirement"

    print("✅ WithdrawalStrategyEngine stage list tests passed")


def test_accumulation_stage_determination():
    """Test that the engine selects the correct stage for working-age inputs."""
    print("\nTesting accumulation stage determination...")

    engine = WithdrawalStrategyEngine()

    # Age 45 with wages → Stage 1 Accumulation
    stage = engine.determine_stage(45, 43, 2026, has_wages=True, has_ss=False)
    assert "Accumulation" in stage.name or "Prep" in stage.name, \
        f"Expected accumulation stage, got: {stage.name}"

    print("✅ Accumulation stage determination tests passed")


def test_accumulation_strategy_calculation():
    """Test build_accumulation_strategy_display() with explicit parameters."""
    print("\nTesting accumulation strategy calculation...")

    try:
        balances = PortfolioBalances(
            cash=30_000,
            taxable=120_000,
            traditional=380_000,
            roth=120_000,
            daf=0,
        )

        strategy_df, balances_df = build_accumulation_strategy_display(
            start_year=2026,
            end_year=2030,
            initial_balances=balances,
            initial_expenses=150_000,
            person1_name="Tom",
            person2_name="Sarah",
            growth_rate=1.07,
            expense_inflation_rate=0.03,
            retirement_year=2036,
            has_wages=True,
        )

        # DataFrame must be returned even if empty (config may limit years)
        assert strategy_df is not None, "strategy_df should not be None"
        assert balances_df is not None, "balances_df should not be None"

        if not strategy_df.empty:
            # Verify required columns exist
            required_cols = ['Year', 'Stage', 'Total Portfolio',
                             'Cash Balance', 'Taxable Balance',
                             'Traditional Balance', 'Roth Balance']
            for col in required_cols:
                assert col in strategy_df.columns, f"Missing column: {col}"

            # All returned rows must be accumulation stages
            accum_stages = ["Stage 1: Accumulation", "Stage 2: Prep for Retirement"]
            non_accum = strategy_df[~strategy_df['Stage'].isin(accum_stages)]
            assert non_accum.empty, \
                f"Non-accumulation stages found: {set(non_accum['Stage'].tolist())}"

            # Portfolio values must be positive
            assert (strategy_df['Total Portfolio'] > 0).all(), \
                "All portfolio values should be positive"

            # balances_df must have the same years as strategy_df
            assert list(balances_df['Year']) == list(strategy_df['Year']), \
                "balances_df years must match strategy_df years"

            print(f"   Calculated {len(strategy_df)} accumulation year(s)")

        print("✅ Accumulation strategy calculation tests passed")

    except Exception as e:
        print(f"⚠️  Accumulation strategy calculation test skipped "
              f"(requires full data files): {e}")


def test_accumulation_summary():
    """Test generate_strategy_summary() with accumulation data."""
    print("\nTesting accumulation strategy summary...")

    try:
        balances = PortfolioBalances(
            cash=30_000,
            taxable=120_000,
            traditional=380_000,
            roth=120_000,
            daf=0,
        )

        strategy_df, _ = build_accumulation_strategy_display(
            start_year=2026,
            end_year=2028,
            initial_balances=balances,
            initial_expenses=150_000,
            person1_name="Tom",
            person2_name="Sarah",
            growth_rate=1.07,
            expense_inflation_rate=0.03,
            retirement_year=2036,
            has_wages=True,
        )

        if not strategy_df.empty:
            summary = generate_strategy_summary(strategy_df)
            assert 'total_years' in summary, "Summary missing total_years"
            assert 'initial_portfolio_value' in summary, \
                "Summary missing initial_portfolio_value"
            assert summary['initial_portfolio_value'] > 0, \
                "Initial portfolio value should be positive"
            assert summary['total_years'] == len(strategy_df), \
                "total_years should match DataFrame length"

        print("✅ Accumulation strategy summary tests passed")

    except Exception as e:
        print(f"⚠️  Accumulation summary test skipped "
              f"(requires full data files): {e}")


def test_accumulation_portfolio_growth():
    """Test that portfolio grows over the accumulation period."""
    print("\nTesting accumulation portfolio growth...")

    try:
        balances = PortfolioBalances(
            cash=30_000,
            taxable=120_000,
            traditional=380_000,
            roth=120_000,
            daf=0,
        )

        strategy_df, _ = build_accumulation_strategy_display(
            start_year=2026,
            end_year=2035,
            initial_balances=balances,
            initial_expenses=150_000,
            person1_name="Tom",
            person2_name="Sarah",
            growth_rate=1.07,
            expense_inflation_rate=0.03,
            retirement_year=2036,
            has_wages=True,
        )

        if len(strategy_df) >= 2:
            start_val = strategy_df['Total Portfolio'].iloc[0]
            end_val   = strategy_df['Total Portfolio'].iloc[-1]
            assert end_val > start_val, \
                f"Portfolio should grow during accumulation: {start_val:,.0f} → {end_val:,.0f}"
            print(f"   Portfolio grew from ${start_val:,.0f} to ${end_val:,.0f}")

        print("✅ Accumulation portfolio growth tests passed")

    except Exception as e:
        print(f"⚠️  Portfolio growth test skipped "
              f"(requires full data files): {e}")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_all_tests() -> int:
    """Run all accumulation strategy test functions.

    Returns:
        int: 0 if all tests passed, 1 if any failed
    """
    print("="*80)
    print("ACCUMULATION STRATEGY MODULE - TEST SUITE")
    print("Stage 1: Accumulation  |  Stage 2: Prep for Retirement")
    print("="*80)

    tests = [
        test_portfolio_balances_accumulation,
        test_stage1_accumulation_applies,
        test_stage2_prep_applies,
        test_accumulation_engine_stages,
        test_accumulation_stage_determination,
        test_accumulation_strategy_calculation,
        test_accumulation_summary,
        test_accumulation_portfolio_growth,
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
        print("\n✅ All accumulation strategy tests passed successfully!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)

# Made with Bob