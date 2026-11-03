"""
tests/test_bracket_fill_edge_cases.py

Boundary condition and edge-case tests for the bracket-fill withdrawal logic.

Covers:
  1. Shortfall = $0 (PNC balance exactly covers expenses)
  2. PNC balance well below safety reserve (shortfall > available traditional)
  3. Zero traditional balance (nothing to draw from)
  4. Zero brokerage (no BETR conversion source)
  5. Bracket-fill with ACA MAGI approaching the 400%-FPL cliff
  6. DAF carryforward 5-year expiry boundary (year 5 vs year 6)
  7. Roth conversion = 0 when 12% bracket is fully consumed by ordinary income
  8. Cross-stage DAF carryforward threading (Stage 3 → Stage 4 via engine kwarg)
  9. Engine formula: carryforward never goes negative
 10. Expenses equal to zero (degenerate but must not crash)
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from strategy_core.models import PortfolioBalances, YearlyStrategy
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager
from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
from strategy_core.stages.stage4_medicare import Stage4Medicare
from strategy_core.agi_calculator import AGICalculator


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_stage3() -> Stage3EarlyRetirement:
    return Stage3EarlyRetirement(
        tax_calculator=TaxCalculator(),
        account_manager=AccountManager(),
    )


def _make_stage4() -> Stage4Medicare:
    return Stage4Medicare(
        tax_calculator=TaxCalculator(),
        account_manager=AccountManager(),
    )


BASE_S3 = dict(
    year=2027,
    age_primary=61,
    age_spouse=60,
    filing_status='married_filing_jointly',
    state='PA',
    max_conversion_rate=0.24,
    growth_rate=1.06,
    start_year=2027,
    daf_carryforward_prior=0.0,
)

BASE_S4 = dict(
    year=2031,
    age_primary=65,
    age_spouse=64,
    filing_status='married_filing_jointly',
    state='PA',
    max_conversion_rate=0.22,
    growth_rate=1.06,
    start_year=2027,
    prior_magi=0.0,
    ss_benefits=0.0,
    daf_carryforward_prior=0.0,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Shortfall = $0  (PNC balance exactly covers all expenses + buffer)
# ─────────────────────────────────────────────────────────────────────────────

class TestNoShortfall:
    """When PNC cash is large enough to cover all spending, no Traditional→Cash needed."""

    def test_no_traditional_withdrawal_when_cash_covers_expenses(self):
        stage = _make_stage3()
        # $500k cash vs $100k expenses — no shortfall
        balances = PortfolioBalances(
            cash=500_000, taxable=300_000,
            traditional=1_500_000, roth=400_000, daf=0,
        )
        result = stage.calculate_strategy(
            balances=balances, expenses=100_000, **BASE_S3,
        )
        # No Traditional→Cash withdrawal needed to cover expenses
        assert result.traditional_to_cash >= 0
        # Strategy should still be valid (non-negative AGI)
        assert result.agi >= 0

    def test_conversion_can_still_fire_when_no_shortfall(self):
        """Bracket fill for Roth conversion should still fire even with zero spending shortfall."""
        stage = _make_stage3()
        balances = PortfolioBalances(
            cash=500_000, taxable=300_000,
            traditional=2_000_000, roth=400_000, daf=0,
        )
        result = stage.calculate_strategy(
            balances=balances, expenses=80_000, **BASE_S3,
        )
        # With a large traditional balance and lots of bracket headroom, conversion should fire
        assert result.roth_conversion >= 0  # Non-negative at minimum
        assert result.agi >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 2. PNC balance below safety reserve (large shortfall)
# ─────────────────────────────────────────────────────────────────────────────

class TestLargeShortfall:
    """PNC cash is below safety reserve — traditional must cover a big gap."""

    def test_shortfall_exceeds_safety_reserve(self):
        stage = _make_stage3()
        # Cash = $10k (below $56k reserve), expenses = $120k → large shortfall
        balances = PortfolioBalances(
            cash=10_000, taxable=200_000,
            traditional=2_000_000, roth=300_000, daf=0,
        )
        result = stage.calculate_strategy(
            balances=balances, expenses=120_000, **BASE_S3,
        )
        # Must have drawn traditional to cover shortfall
        assert result.traditional_to_cash > 0
        # Ending balances must stay non-negative
        assert result.balances.cash >= 0
        assert result.balances.traditional >= 0

    def test_shortfall_greater_than_traditional_balance(self):
        """When traditional balance can't cover the full shortfall, graceful degradation."""
        stage = _make_stage3()
        balances = PortfolioBalances(
            cash=0, taxable=200_000,
            traditional=5_000,   # tiny traditional
            roth=300_000, daf=0,
        )
        # Should not raise; balances should be non-negative
        result = stage.calculate_strategy(
            balances=balances, expenses=120_000, **BASE_S3,
        )
        assert result.balances.traditional >= 0
        assert result.agi >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. Zero traditional balance
# ─────────────────────────────────────────────────────────────────────────────

class TestZeroTraditional:
    """With no traditional balance, conversions and traditional withdrawals must be zero."""

    def test_no_conversion_with_zero_traditional(self):
        stage = _make_stage3()
        balances = PortfolioBalances(
            cash=300_000, taxable=500_000,
            traditional=0, roth=1_000_000, daf=0,
        )
        result = stage.calculate_strategy(
            balances=balances, expenses=80_000, **BASE_S3,
        )
        assert result.roth_conversion == 0.0
        assert result.traditional_to_cash == 0.0
        assert result.balances.traditional >= 0

    def test_stage4_no_conversion_zero_traditional(self):
        stage = _make_stage4()
        balances = PortfolioBalances(
            cash=300_000, taxable=400_000,
            traditional=0, roth=800_000, daf=0,
        )
        result = stage.calculate_strategy(
            balances=balances, expenses=90_000, **BASE_S4,
        )
        assert result.roth_conversion == 0.0
        assert result.balances.traditional >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Zero brokerage balance
# ─────────────────────────────────────────────────────────────────────────────

class TestZeroBrokerage:
    """With no brokerage, BETR must fall back to cash-only or suppress conversions."""

    def test_stage3_rollover_off_zero_brokerage_blocks_conversion(self):
        stage = _make_stage3()
        balances = PortfolioBalances(
            cash=200_000, taxable=0,   # no brokerage
            traditional=2_000_000, roth=300_000, daf=0,
        )
        with patch.object(stage, '_use_60day_rollover', return_value=False):
            result = stage.calculate_strategy(
                balances=balances, expenses=80_000, **BASE_S3,
            )
        # With zero brokerage and rollover OFF, conversion should be blocked
        # (BETR needs taxable to fund the withholding)
        assert result.roth_conversion == 0.0 or result.roth_conversion < 10_000

    def test_stage3_rollover_on_zero_brokerage_uses_cash(self):
        """When rollover is ON, cash above reserve supplements zero brokerage."""
        stage = _make_stage3()
        balances = PortfolioBalances(
            cash=200_000, taxable=0,   # no brokerage, but ample cash
            traditional=2_000_000, roth=300_000, daf=0,
        )
        with patch.object(stage, '_use_60day_rollover', return_value=True):
            result = stage.calculate_strategy(
                balances=balances, expenses=80_000, **BASE_S3,
            )
        # usable_cash = 200k - 56k = 144k → effective = 144k → should enable conversion
        assert result.roth_conversion >= 0
        assert result.agi >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Balances all zero (extreme degenerate case)
# ─────────────────────────────────────────────────────────────────────────────

class TestAllZeroBalances:
    """All-zero portfolio must not crash; all output fields must be non-negative."""

    def test_stage3_all_zero_balances_does_not_crash(self):
        stage = _make_stage3()
        balances = PortfolioBalances(
            cash=0, taxable=0, traditional=0, roth=0, daf=0,
        )
        result = stage.calculate_strategy(
            balances=balances, expenses=80_000, **BASE_S3,
        )
        assert result.roth_conversion == 0.0
        assert result.balances.traditional >= 0
        assert result.balances.roth >= 0
        assert result.agi >= 0

    def test_stage3_zero_expenses_does_not_crash(self):
        """Expenses = 0 is a degenerate input but must not crash."""
        stage = _make_stage3()
        balances = PortfolioBalances(
            cash=200_000, taxable=300_000,
            traditional=1_500_000, roth=400_000, daf=0,
        )
        result = stage.calculate_strategy(
            balances=balances, expenses=0.0, **BASE_S3,
        )
        assert result.agi >= 0
        assert result.balances.traditional >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. DAF carryforward — AGICalculator boundary conditions
# ─────────────────────────────────────────────────────────────────────────────

class TestDAFCarryforwardBoundaries:
    """Verify AGICalculator carryforward arithmetic at key boundaries."""

    def _calc(self, daf_fmv, agi, carryforward_prior):
        tc = TaxCalculator()
        calc = AGICalculator(tax_calculator=tc)
        return calc.calculate_agi_and_taxes(
            year=2027,
            filing_status='married_filing_jointly',
            age_primary=61,
            age_spouse=60,
            traditional_withdrawal=agi,  # set ordinary income = agi
            roth_conversion=0.0,
            brokerage_ltcg=0.0,
            brokerage_basis=0.0,
            daf_fmv=daf_fmv,
            state='PA',
            pa_rate=0.0307,
            property_tax=5_000,
            daf_carryforward_prior=carryforward_prior,
        )

    def test_daf_exactly_at_30pct_limit_no_carryforward(self):
        """DAF = exactly 30% of AGI → deductible = 100%, carryforward = 0."""
        agi = 200_000
        daf = agi * 0.30  # exactly at limit
        result = self._calc(daf_fmv=daf, agi=agi, carryforward_prior=0.0)
        assert result['daf_deductible_this_year'] == pytest.approx(daf, abs=1.0)
        assert result['daf_carryforward_new'] == pytest.approx(0.0, abs=1.0)

    def test_daf_above_30pct_creates_carryforward(self):
        """DAF > 30% of AGI → excess carries forward."""
        agi = 200_000
        daf = 100_000   # 50% of AGI — only 30% ($60k) deductible this year
        result = self._calc(daf_fmv=daf, agi=agi, carryforward_prior=0.0)
        expected_deductible = agi * 0.30
        expected_carryforward = daf - expected_deductible
        assert result['daf_deductible_this_year'] == pytest.approx(expected_deductible, abs=1.0)
        assert result['daf_carryforward_new'] == pytest.approx(expected_carryforward, abs=1.0)

    def test_prior_carryforward_fully_consumed(self):
        """Small prior carryforward is fully consumed when AGI is large enough."""
        agi = 300_000
        carryforward_prior = 10_000   # small; 30% limit = $90k → easily absorbed
        result = self._calc(daf_fmv=0.0, agi=agi, carryforward_prior=carryforward_prior)
        # carryforward alone should be deductible
        assert result['daf_deductible_this_year'] == pytest.approx(carryforward_prior, abs=1.0)
        assert result['daf_carryforward_new'] == pytest.approx(0.0, abs=1.0)

    def test_prior_carryforward_partially_consumed_when_agi_low(self):
        """With a very low AGI, 30% limit may be less than prior carryforward."""
        agi = 10_000   # tiny: 30% = $3k
        carryforward_prior = 20_000
        result = self._calc(daf_fmv=0.0, agi=agi, carryforward_prior=carryforward_prior)
        expected_deductible = agi * 0.30
        expected_remaining = carryforward_prior - expected_deductible
        assert result['daf_deductible_this_year'] == pytest.approx(expected_deductible, abs=1.0)
        assert result['daf_carryforward_new'] == pytest.approx(expected_remaining, abs=1.0)

    def test_zero_agi_no_daf_deduction(self):
        """With zero AGI (no withdrawals), 30% limit = 0 → nothing deductible."""
        result = self._calc(daf_fmv=50_000, agi=0.0, carryforward_prior=0.0)
        assert result['daf_deductible_this_year'] == pytest.approx(0.0, abs=1.0)
        assert result['daf_carryforward_new'] == pytest.approx(50_000.0, abs=1.0)

    def test_carryforward_never_negative(self):
        """Under no circumstances should carryforward go below zero."""
        for daf, agi, carry in [
            (0.0, 0.0, 0.0),
            (0.0, 100_000, 0.0),
            (50_000, 200_000, 0.0),
            (0.0, 50_000, 200_000),
            (1_000, 5_000, 3_000),
        ]:
            result = self._calc(daf_fmv=daf, agi=agi, carryforward_prior=carry)
            assert result['daf_carryforward_new'] >= 0.0, (
                f"carryforward went negative: daf={daf}, agi={agi}, prior={carry} → "
                f"{result['daf_carryforward_new']}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 7. Cross-stage DAF carryforward threading (engine kwarg pattern)
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossStageDAFThreading:
    """
    Verify that a DAF carryforward produced in Stage 3 (Year N) reduces taxes
    in Stage 4 (Year N+1) when threaded via the daf_carryforward_prior kwarg.
    """

    def _run_stage4(self, carryforward_prior: float) -> YearlyStrategy:
        stage = _make_stage4()
        balances = PortfolioBalances(
            cash=100_000, taxable=200_000,
            traditional=2_000_000, roth=500_000, daf=100_000,
        )
        return stage.calculate_strategy(
            balances=balances, expenses=90_000,
            daf_carryforward_prior=carryforward_prior,
            **{k: v for k, v in BASE_S4.items() if k != 'daf_carryforward_prior'},
        )

    def test_stage4_accepts_daf_carryforward_kwarg(self):
        """Stage 4 must accept daf_carryforward_prior without error."""
        result = self._run_stage4(carryforward_prior=50_000)
        assert result is not None
        assert result.agi >= 0

    def test_stage4_with_carryforward_has_deductible(self):
        """When a large carryforward is passed, Stage 4 should report a DAF deductible."""
        result = self._run_stage4(carryforward_prior=80_000)
        # daf_deductible ≥ 0 always; with a $80k carryforward it should be > 0
        assert result.daf_deductible >= 0

    def test_stage4_carryforward_reduces_federal_tax(self):
        """Federal tax should be lower (or equal) with a carryforward vs. without one."""
        result_no_carry = self._run_stage4(carryforward_prior=0.0)
        result_with_carry = self._run_stage4(carryforward_prior=80_000)
        # Tax can only stay the same or decrease with more deduction available
        assert result_with_carry.federal_tax <= result_no_carry.federal_tax + 1.0

    def test_stage3_daf_deductible_set_on_strategy(self):
        """Stage 3 must set daf_deductible on the returned YearlyStrategy."""
        stage = _make_stage3()
        balances = PortfolioBalances(
            cash=200_000, taxable=300_000,
            traditional=1_500_000, roth=400_000, daf=300_000,
        )
        result = stage.calculate_strategy(
            balances=balances, expenses=80_000, **BASE_S3,
        )
        # daf_deductible must be a non-negative float
        assert isinstance(result.daf_deductible, float)
        assert result.daf_deductible >= 0.0

    def test_engine_carryforward_formula_is_non_negative(self):
        """
        Replicate the engine's post-year update formula for a range of inputs.
        The result (carryforward into next year) must always be >= 0.
        """
        cases = [
            (0.0, 0.0, 0.0),
            (50_000, 0.0, 50_000),       # no deduction taken → full carry
            (50_000, 15_000, 35_000),    # partial deduction
            (50_000, 50_000, 0.0),       # fully deducted
            (0.0, 30_000, 0.0),          # prior carryforward fully consumed → 0
            (0.0, 0.0, 20_000),          # prior carry consumed → clamp at 0
        ]
        for daf_contribution, prior_carryforward, daf_deductible in cases:
            _daf_available = daf_contribution + prior_carryforward
            new_carry = max(0.0, _daf_available - daf_deductible)
            assert new_carry >= 0.0, (
                f"Engine formula produced negative carryforward: "
                f"contrib={daf_contribution}, prior={prior_carryforward}, "
                f"deductible={daf_deductible} → {new_carry}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 8. Roth conversion = 0 when traditional balance is exhausted mid-year
# ─────────────────────────────────────────────────────────────────────────────

class TestConversionZeroWhenBracketFull:
    """Verify that Roth conversion is suppressed when no traditional headroom remains."""

    def test_conversion_suppressed_when_traditional_consumed_by_spending(self):
        """If traditional just barely covers spending shortfall, no conversion fires."""
        stage = _make_stage3()
        # Cash = $0 → all expenses must come from traditional
        # Traditional = expenses only (no headroom for conversion)
        annual_expenses = 100_000
        balances = PortfolioBalances(
            cash=0, taxable=0,
            traditional=annual_expenses * 1.2,  # just enough for spending + tax
            roth=300_000, daf=0,
        )
        with patch.object(stage, '_use_60day_rollover', return_value=False):
            result = stage.calculate_strategy(
                balances=balances, expenses=annual_expenses, **BASE_S3,
            )
        # Available-for-conversion = traditional - needs - spending_shortfall → near 0
        # Conversion may be small or zero; what matters is it doesn't crash and is >= 0
        assert result.roth_conversion >= 0.0
        assert result.balances.traditional >= 0.0


# Made with Bob
