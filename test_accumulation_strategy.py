#!/usr/bin/env python3
"""
Test script for accumulation strategy module

This script performs basic validation of the accumulation strategy calculations
(Stage 1: Accumulation and Stage 2: Prep for Retirement) to ensure the module
is working correctly.
"""

import sys
import pytest  # type: ignore[import-untyped]
import pandas as pd
from strategy import (
    PortfolioBalances,
    WithdrawalStrategyEngine,
    Stage1Accumulation,
    Stage2PrepForRetirement,
    build_accumulation_strategy_display,
    generate_strategy_summary,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_STRATEGY_COLS = (
    'Year', 'Stage', 'Total Portfolio',
    'Cash Balance', 'Taxable Balance',
    'Traditional Balance', 'Roth Balance',
)

ACCUMULATION_STAGES = (
    "Stage 1: Accumulation",
    "Stage 2: Prep for Retirement",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def accumulation_balances() -> PortfolioBalances:
    """Standard accumulation-phase portfolio used across multiple tests."""
    return PortfolioBalances(
        cash=30_000,
        taxable=120_000,
        traditional=380_000,
        roth=120_000,
        daf=0,
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_portfolio_balances_accumulation(accumulation_balances):
    """Test PortfolioBalances with typical accumulation-phase values."""
    assert accumulation_balances.total() == 650_000, \
        f"Expected 650000, got {accumulation_balances.total()}"
    assert accumulation_balances.cash == 30_000, "Cash value incorrect"
    assert accumulation_balances.roth == 120_000, "Roth value incorrect"


def test_stage1_accumulation_applies():
    """Test Stage1Accumulation.applies() logic.

    Stage 1 applies when has_wages=True AND the current year is outside the
    Stage 2 prep window (i.e. more than PREP_WINDOW_YEARS before the earliest
    configured retirement year).  Years within the prep window correctly yield
    to Stage 2, so we use a year well outside that window (2015) to test the
    pure Stage-1 path.
    """
    stage = Stage1Accumulation()

    # Year well outside the prep window → Stage 1 should apply with wages
    assert stage.applies(35, 33, 2015, has_wages=True,  has_ss=False), \
        "Stage 1 should apply at age 35 with wages (outside prep window)"
    assert stage.applies(45, 43, 2015, has_wages=True,  has_ss=False), \
        "Stage 1 should apply at age 45 with wages (outside prep window)"

    # Should NOT apply without wages regardless of year
    assert not stage.applies(45, 43, 2015, has_wages=False, has_ss=False), \
        "Stage 1 should not apply without wages"
    assert not stage.applies(60, 58, 2015, has_wages=False, has_ss=True), \
        "Stage 1 should not apply without wages even with SS"

    # Within the prep window → Stage 1 yields to Stage 2 (returns False)
    assert not stage.applies(45, 43, 2026, has_wages=True, has_ss=False), \
        "Stage 1 should yield to Stage 2 when within the prep window"


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


def test_accumulation_strategy_calculation(accumulation_balances):
    """Test build_accumulation_strategy_display() with explicit parameters."""
    strategy_df, balances_df = build_accumulation_strategy_display(
        start_year=2026,
        end_year=2030,
        initial_balances=accumulation_balances,
        initial_expenses=150_000,
        person1_name="Tom",
        person2_name="Sarah",
        growth_rate=1.07,
        expense_inflation_rate=0.03,
        retirement_year=2036,
        has_wages=True,
    )

    # DataFrames must be returned even if empty (config may limit years)
    assert strategy_df is not None, "strategy_df should not be None"
    assert balances_df is not None, "balances_df should not be None"

    if not strategy_df.empty:
        # Verify all required columns exist — report every missing column at once
        missing = [c for c in REQUIRED_STRATEGY_COLS if c not in strategy_df.columns]
        assert not missing, f"Missing columns: {missing}"

        # All returned rows must be accumulation stages
        non_accum = strategy_df[~strategy_df['Stage'].isin(ACCUMULATION_STAGES)]
        assert non_accum.empty, \
            f"Non-accumulation stages found: {set(non_accum['Stage'].tolist())}"

        # Portfolio values must be positive (vectorized)
        assert bool((strategy_df['Total Portfolio'] > 0).all()), \
            "All portfolio values should be positive"

        # balances_df must have the same years as strategy_df
        pd.testing.assert_series_equal(
            balances_df['Year'].reset_index(drop=True),
            strategy_df['Year'].reset_index(drop=True),
            check_names=False,
            obj="Year alignment between balances_df and strategy_df",
        )


def test_accumulation_summary(accumulation_balances):
    """Test generate_strategy_summary() with accumulation data."""
    strategy_df, _ = build_accumulation_strategy_display(
        start_year=2026,
        end_year=2028,
        initial_balances=accumulation_balances,
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


def test_accumulation_portfolio_growth(accumulation_balances):
    """Test that portfolio grows over the accumulation period."""
    strategy_df, _ = build_accumulation_strategy_display(
        start_year=2026,
        end_year=2035,
        initial_balances=accumulation_balances,
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
        assert end_val > start_val, (
            f"Portfolio should grow during accumulation: "
            f"{start_val:,.0f} → {end_val:,.0f}"
        )


# ---------------------------------------------------------------------------
# Test runner (fixture-independent tests only)
# ---------------------------------------------------------------------------

def run_all_tests() -> int:
    """Run fixture-independent accumulation strategy tests directly.

    Tests that use the ``accumulation_balances`` pytest fixture are excluded
    here because fixtures are only injected when pytest invokes the function.
    Run ``pytest test_accumulation_strategy.py`` for the full suite.

    Returns:
        int: 0 if all tests passed, 1 if any failed
    """
    print("="*80)
    print("ACCUMULATION STRATEGY MODULE - TEST SUITE")
    print("Stage 1: Accumulation  |  Stage 2: Prep for Retirement")
    print("="*80)

    tests = [
        test_stage1_accumulation_applies,
        test_stage2_prep_applies,
        test_accumulation_engine_stages,
        test_accumulation_stage_determination,
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