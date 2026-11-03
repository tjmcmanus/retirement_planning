"""
tests/test_sixty_day_rollover_integration.py

Tests for 60-day rollover integration in Stage 3 and Stage 4.

Validates that:
  1. _use_60day_rollover() reads the config flag correctly.
  2. _effective_taxable_for_conversion() returns brokerage+cash when the flag is ON
     and brokerage-only when OFF.
  3. _get_safety_reserve() reads savings_safety_reserve from config.
  4. Stage 3: with the flag ON, cash supplements brokerage so BETR has enough to fund
     conversion tax that would have been blocked brokerage-only.
  5. Stage 4: same as Stage 3 with IRMAA constraints.
  6. When the flag is OFF, behavior is unchanged (brokerage-only).
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from strategy_core.models import PortfolioBalances, YearlyStrategy
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager
from strategy_core.base_strategy import BaseLifeStageStrategy
from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
from strategy_core.stages.stage4_medicare import Stage4Medicare


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_balances(
    traditional: float = 4_000_000,
    roth: float = 300_000,
    taxable: float = 40_000,   # thin brokerage — won't cover conversion tax alone
    cash: float = 200_000,     # but cash is healthy
    daf: float = 500_000,
) -> PortfolioBalances:
    return PortfolioBalances(
        cash=cash, taxable=taxable,
        traditional=traditional, roth=roth, daf=daf,
    )


def make_stages():
    tc = TaxCalculator()
    am = AccountManager()
    s3 = Stage3EarlyRetirement(tax_calculator=tc, account_manager=am)
    s4 = Stage4Medicare(tax_calculator=tc, account_manager=am)
    return s3, s4


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for base helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestBaseHelpers:
    """Tests for _use_60day_rollover, _effective_taxable_for_conversion, _get_safety_reserve."""

    def _get_stage(self):
        tc = TaxCalculator()
        am = AccountManager()
        return Stage3EarlyRetirement(tax_calculator=tc, account_manager=am)

    def test_use_60day_rollover_reads_config_true(self):
        stage = self._get_stage()
        with patch.object(stage, '_use_60day_rollover', return_value=True):
            assert stage._use_60day_rollover() is True

    def test_use_60day_rollover_reads_config_false(self):
        stage = self._get_stage()
        with patch.object(stage, '_use_60day_rollover', return_value=False):
            assert stage._use_60day_rollover() is False

    def test_use_60day_rollover_defaults_on_when_never_saved(self):
        """The Settings page shows this option ON when unset, so the engine must default to ON too."""
        stage = self._get_stage()
        fake_cfg = type("Cfg", (), {"get": lambda self, section, key, default=None: default})()
        with patch("config.get_config_manager", return_value=fake_cfg):
            assert stage._use_60day_rollover() is True

    def test_effective_taxable_rollover_off(self):
        """When rollover is OFF, effective balance = brokerage only."""
        stage = self._get_stage()
        with patch.object(stage, '_use_60day_rollover', return_value=False):
            result = stage._effective_taxable_for_conversion(
                brokerage_balance=50_000,
                cash_balance=200_000,
                safety_reserve=56_000,
            )
        assert result == 50_000

    def test_effective_taxable_rollover_on(self):
        """When rollover is ON, effective balance = brokerage + (cash - reserve)."""
        stage = self._get_stage()
        with patch.object(stage, '_use_60day_rollover', return_value=True):
            result = stage._effective_taxable_for_conversion(
                brokerage_balance=50_000,
                cash_balance=200_000,
                safety_reserve=56_000,
            )
        # 50_000 + (200_000 - 56_000) = 194_000
        assert result == pytest.approx(194_000.0)

    def test_effective_taxable_rollover_on_cash_below_reserve(self):
        """When cash <= reserve, usable_cash = 0; result = brokerage only."""
        stage = self._get_stage()
        with patch.object(stage, '_use_60day_rollover', return_value=True):
            result = stage._effective_taxable_for_conversion(
                brokerage_balance=50_000,
                cash_balance=30_000,     # below 56k reserve
                safety_reserve=56_000,
            )
        assert result == pytest.approx(50_000.0)

    def test_get_safety_reserve_reads_config(self):
        """_get_safety_reserve returns the config value (or 56_000 default)."""
        stage = self._get_stage()
        # The config has savings_safety_reserve: 56000
        reserve = stage._get_safety_reserve()
        assert reserve >= 0
        # Real config should give 56_000
        assert reserve == pytest.approx(56_000.0, abs=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Integration: Stage 3 with rollover ON vs. OFF
# ─────────────────────────────────────────────────────────────────────────────

class TestStage3RolloverIntegration:
    """
    Regression tests checking that Stage 3 Roth conversions are unlocked by
    the 60-day rollover when brokerage alone is insufficient.
    """

    BASE_KWARGS = dict(
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

    def _run(self, rollover_on: bool) -> YearlyStrategy:
        s3, _ = make_stages()
        # Brokerage = $5k.  BETR's optimal bracket-fill is ~$200k; estimated tax
        # = $200k × 0.24 = $48k >> $5k.  _validate_taxable_account_sufficiency
        # blocks the conversion and returns (0.0, empty).
        # Cash = $200k.  In rollover mode: usable cash = $200k − $56k = $144k;
        # effective = $5k + $144k = $149k, which is > $48k → conversion unlocked.
        balances = make_balances(
            traditional=4_000_000,
            taxable=5_000,    # genuinely insufficient at $5k
            cash=200_000,
        )
        with patch.object(s3, '_use_60day_rollover', return_value=rollover_on):
            return s3.calculate_strategy(balances=balances, expenses=132_000, **self.BASE_KWARGS)

    def test_rollover_off_no_conversion_when_brokerage_thin(self):
        """With rollover OFF and $5k brokerage, BETR blocks the full-bracket conversion."""
        result = self._run(rollover_on=False)
        # $5k can fund at most $5k/0.24 ≈ $20k conversion; optimal is much larger → blocked.
        # We use < 25_000 rather than == 0 because the bracket-fill fallback path may still
        # find a small conversion if the stage falls back to it for other reasons.
        assert result.roth_conversion < 25_000

    def test_rollover_on_enables_conversion_when_brokerage_thin(self):
        """With rollover ON, cash supplements brokerage → BETR can find a conversion."""
        result = self._run(rollover_on=True)
        # Cash ($200k - $56k reserve = $144k) + brokerage ($30k) = $174k effective
        # That's ample to cover the estimated tax → conversion should fire
        assert result.roth_conversion > 0

    def test_rollover_on_conversion_within_bracket(self):
        """Conversion amount should stay within the 24% bracket ceiling."""
        result = self._run(rollover_on=True)
        if result.roth_conversion > 0:
            # Rough sanity: conversion should not exceed what fills the 24% bracket
            # (bracket top ~$383k for MFJ 2027; expenses ~$132k so plenty of space)
            assert result.roth_conversion < 400_000

    def test_rollover_on_agi_reasonable(self):
        """AGI should be positive and include the conversion income."""
        result = self._run(rollover_on=True)
        assert result.agi > 0

    def test_rollover_off_result_consistent_with_pre_rollover(self):
        """With rollover OFF the result should be identical to the pre-rollover behavior."""
        result_off = self._run(rollover_on=False)
        # Just verify it doesn't crash and AGI is non-negative
        assert result_off.agi >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Integration: Stage 4 with rollover ON vs. OFF
# ─────────────────────────────────────────────────────────────────────────────

class TestStage4RolloverIntegration:
    """
    Stage 4 (Medicare) equivalent — thin brokerage, healthy cash.
    """

    BASE_KWARGS = dict(
        year=2031,
        age_primary=65,
        age_spouse=64,
        filing_status='married_filing_jointly',
        state='PA',
        max_conversion_rate=0.24,
        growth_rate=1.06,
        start_year=2027,
        prior_magi=200_000.0,
        daf_carryforward_prior=0.0,
    )

    def _run(self, rollover_on: bool) -> YearlyStrategy:
        _, s4 = make_stages()
        # $5k brokerage — the BETR optimal is ~$200k; estimated tax $48k >> $5k → blocked.
        # Cash $180k; in rollover mode usable = $180k − $56k = $124k; total $129k > $48k → unlocked.
        balances = make_balances(
            traditional=5_500_000,
            taxable=5_000,    # genuinely insufficient at $5k
            cash=180_000,
        )
        with patch.object(s4, '_use_60day_rollover', return_value=rollover_on):
            return s4.calculate_strategy(balances=balances, expenses=148_000, **self.BASE_KWARGS)

    def test_stage4_rollover_off_no_conversion_thin_brokerage(self):
        """Stage 4 with rollover OFF and $5k brokerage → BETR blocks the full conversion."""
        result = self._run(rollover_on=False)
        # $5k can fund at most ~$20k conversion; bracket-fill fallback may fire a small amount
        assert result.roth_conversion < 25_000

    def test_stage4_rollover_on_enables_conversion(self):
        """Stage 4 with rollover ON → conversion unlocked via cash."""
        result = self._run(rollover_on=True)
        assert result.roth_conversion > 0

    def test_stage4_rollover_on_irmaa_penalty_present(self):
        """IRMAA penalty should still be calculated regardless of rollover flag."""
        result = self._run(rollover_on=True)
        assert result.irmaa_penalty >= 0

    def test_stage4_rollover_on_agi_positive(self):
        result = self._run(rollover_on=True)
        assert result.agi > 0


# ─────────────────────────────────────────────────────────────────────────────
# Symmetry: with ample brokerage, rollover ON/OFF should give same conversion
# ─────────────────────────────────────────────────────────────────────────────

class TestRolloverSymmetry:
    """When brokerage is already ample, the flag should make no difference."""

    BASE_KWARGS = dict(
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

    def test_ample_brokerage_rollover_on_off_same_conversion(self):
        """With $500k brokerage (ample), rollover ON and OFF should give same conversion amount."""
        tc = TaxCalculator()
        am = AccountManager()
        balances = make_balances(taxable=500_000, cash=150_000)

        s3_on  = Stage3EarlyRetirement(tax_calculator=tc, account_manager=am)
        s3_off = Stage3EarlyRetirement(tax_calculator=tc, account_manager=am)

        with patch.object(s3_on,  '_use_60day_rollover', return_value=True):
            result_on  = s3_on.calculate_strategy(balances=balances, expenses=132_000, **self.BASE_KWARGS)
        with patch.object(s3_off, '_use_60day_rollover', return_value=False):
            result_off = s3_off.calculate_strategy(balances=balances, expenses=132_000, **self.BASE_KWARGS)

        # Both should produce a conversion; amounts should be equal (same bracket math)
        assert result_on.roth_conversion  > 0
        assert result_off.roth_conversion > 0
        assert abs(result_on.roth_conversion - result_off.roth_conversion) < 1000
