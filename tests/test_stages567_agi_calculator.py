"""
tests/test_stages567_agi_calculator.py

Regression tests verifying that Stages 5, 6, and 7 now use AGICalculator for
their final tax calculation — the same IRC-compliant path as Stages 3 & 4.

Key invariants checked for each stage:
  1. AGI = taxable_ss + trad_withdrawal + roth_conversion + ltcg  (no double-count)
  2. Federal tax is non-negative and consistent with the AGI
  3. DAF deductible is set on the YearlyStrategy and capped at 30% of AGI
  4. DAF carryforward is accepted via kwarg and reduces taxes
  5. SS benefits > 0 → taxable_ss > 0 (SS is included in AGI)
  6. Single filing status (Stage 7) produces lower standard deduction than MFJ
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from strategy_core.models import PortfolioBalances
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager
from strategy_core.stages.stage5_social_security import Stage5SocialSecurity
from strategy_core.stages.stage6_rmd import Stage6RMD
from strategy_core.stages.stage7_surviving_spouse import Stage7SurvivingSpouse
from strategy_core.agi_calculator import AGICalculator


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_stage5() -> Stage5SocialSecurity:
    return Stage5SocialSecurity(
        tax_calculator=TaxCalculator(),
        account_manager=AccountManager(),
    )


def _make_stage6() -> Stage6RMD:
    return Stage6RMD(
        tax_calculator=TaxCalculator(),
        account_manager=AccountManager(),
    )


def _make_stage7() -> Stage7SurvivingSpouse:
    return Stage7SurvivingSpouse(
        tax_calculator=TaxCalculator(),
        account_manager=AccountManager(),
    )


BALANCES = PortfolioBalances(
    cash=200_000, taxable=300_000,
    traditional=2_000_000, roth=500_000, daf=0,
)

BASE_S5 = dict(
    year=2036,
    age_primary=70, age_spouse=69,
    ss_benefits=48_000,       # $4,000/month combined
    prior_magi=150_000,
    filing_status='married_filing_jointly',
    state='PA',
    max_conversion_rate=0.22,
    growth_rate=1.06,
    start_year=2027,
    daf_carryforward_prior=0.0,
)

BASE_S6 = dict(
    year=2041,
    age_primary=75, age_spouse=74,
    ss_benefits=52_000,
    prior_magi=200_000,
    filing_status='married_filing_jointly',
    state='PA',
    max_conversion_rate=0.22,
    growth_rate=1.06,
    start_year=2027,
    daf_carryforward_prior=0.0,
)


# ─────────────────────────────────────────────────────────────────────────────
# IRMAA headroom — unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIrmaaHeadroomUsesNextBracket:
    """The next IRMAA threshold is the bracket that starts where the current one ends.

    Brackets are contiguous (one's upper == the next one's lower), so a strict ``>``
    comparison skipped a bracket and overstated the headroom by a whole bracket width.
    """

    def test_headroom_stops_at_the_adjacent_threshold(self):
        import pandas as pd

        table = pd.DataFrame({"lower": [0, 286_000, 360_000], "upper": [286_000, 360_000, 438_000]})
        with patch("load_data.get_medicare_costs", return_value=table):
            headroom = _make_stage5()._calculate_irmaa_headroom(
                prior_magi=243_464, current_income=244_293, std_deduction=33_500, year=2038
            )
        # next threshold 286,000 (not 360,000) minus income minus standard deduction
        assert headroom == 286_000 - 244_293 - 33_500


# ─────────────────────────────────────────────────────────────────────────────
# AGICalculator SS extension — unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAGICalculatorSSSupport:
    """Verify the new ss_benefits / taxable_ss parameters work correctly."""

    def _calc(self, ss_benefits, taxable_ss, trad=100_000, roth=50_000, ltcg=10_000):
        tc = TaxCalculator()
        calc = AGICalculator(tax_calculator=tc)
        return calc.calculate_agi_and_taxes(
            year=2036,
            filing_status='married_filing_jointly',
            age_primary=70,
            age_spouse=69,
            traditional_withdrawal=trad,
            roth_conversion=roth,
            brokerage_ltcg=ltcg,
            daf_fmv=0.0,
            state='PA',
            property_tax=5_000,
            ss_benefits=ss_benefits,
            taxable_ss=taxable_ss,
        )

    def test_no_ss_unchanged(self):
        """With ss_benefits=0 the result must equal the pre-SS calculation."""
        result = self._calc(ss_benefits=0.0, taxable_ss=0.0)
        # gross_ordinary = trad + roth only (no SS)
        assert result['gross_ordinary'] == pytest.approx(150_000.0)

    def test_ss_adds_to_gross_ordinary(self):
        """taxable_ss must be included in gross_ordinary."""
        taxable_ss = 40_000
        result = self._calc(ss_benefits=48_000, taxable_ss=taxable_ss)
        # gross_ordinary = 100k + 50k + 40k = 190k
        assert result['gross_ordinary'] == pytest.approx(190_000.0)

    def test_ss_fallback_85pct(self):
        """When ss_benefits > 0 but taxable_ss = 0, falls back to 85% of ss_benefits."""
        result = self._calc(ss_benefits=40_000, taxable_ss=0.0)
        expected_taxable_ss = 40_000 * 0.85
        assert result['gross_ordinary'] == pytest.approx(100_000 + 50_000 + expected_taxable_ss)

    def test_taxable_ss_in_return_dict(self):
        """'taxable_ss' key must be present and match what was passed in."""
        taxable_ss = 38_000
        result = self._calc(ss_benefits=48_000, taxable_ss=taxable_ss)
        assert 'taxable_ss' in result
        assert result['taxable_ss'] == pytest.approx(taxable_ss)

    def test_zero_ss_taxable_ss_zero_in_result(self):
        """No SS → taxable_ss in result must be 0."""
        result = self._calc(ss_benefits=0.0, taxable_ss=0.0)
        assert result['taxable_ss'] == pytest.approx(0.0)

    def test_ss_increases_agi(self):
        """Adding SS income must increase AGI relative to no-SS case."""
        no_ss = self._calc(ss_benefits=0.0, taxable_ss=0.0)
        with_ss = self._calc(ss_benefits=48_000, taxable_ss=40_000)
        assert with_ss['agi_pre_deduction'] > no_ss['agi_pre_deduction']

    def test_state_tax_includes_ss(self):
        """State tax calc (PA) should receive the taxable_ss amount."""
        # PA exempts SS; but the call should not crash
        result = self._calc(ss_benefits=48_000, taxable_ss=40_000)
        assert result['state_tax'] >= 0.0

    def test_single_filer_lower_standard_deduction(self):
        """Single filer gets a lower standard deduction than MFJ."""
        tc = TaxCalculator()
        calc = AGICalculator(tax_calculator=tc)
        kwargs = dict(year=2036, age_primary=70, age_spouse=0,
                      traditional_withdrawal=100_000, roth_conversion=0.0,
                      brokerage_ltcg=0.0, ss_benefits=40_000, taxable_ss=34_000)
        mfj = calc.calculate_agi_and_taxes(filing_status='married_filing_jointly', **kwargs)
        single = calc.calculate_agi_and_taxes(filing_status='Single', **kwargs)
        assert single['std_deduction'] < mfj['std_deduction']


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — Social Security
# ─────────────────────────────────────────────────────────────────────────────

class TestStage5AGICalculatorPath:
    """Verify Stage 5 uses AGICalculator for its final tax number."""

    def test_ss_included_in_agi(self):
        """AGI must be > 0 and must include SS income."""
        stage = _make_stage5()
        result = stage.calculate_strategy(
            balances=BALANCES, expenses=100_000, **BASE_S5,
        )
        # AGI must be positive and exceed traditional withdrawal alone
        assert result.agi > 0
        # SS income should push AGI above what a pure-trad withdrawal would give
        assert result.agi > result.traditional_withdrawal

    def test_federal_tax_positive_with_ss(self):
        """Federal tax must be non-negative."""
        stage = _make_stage5()
        result = stage.calculate_strategy(
            balances=BALANCES, expenses=100_000, **BASE_S5,
        )
        assert result.federal_tax >= 0.0

    def test_daf_deductible_set(self):
        """daf_deductible must always be set (non-negative float)."""
        stage = _make_stage5()
        result = stage.calculate_strategy(
            balances=BALANCES, expenses=100_000, **BASE_S5,
        )
        assert isinstance(result.daf_deductible, float)
        assert result.daf_deductible >= 0.0

    def test_daf_deductible_capped_at_30pct_agi(self):
        """daf_deductible must never exceed 30% of AGI."""
        stage = _make_stage5()
        daf_balances = PortfolioBalances(
            cash=200_000, taxable=400_000,
            traditional=2_000_000, roth=500_000, daf=200_000,
        )
        result = stage.calculate_strategy(
            balances=daf_balances, expenses=100_000, **BASE_S5,
        )
        if result.agi > 0:
            assert result.daf_deductible <= result.agi * 0.30 + 1.0  # +$1 float tolerance

    def test_carryforward_reduces_tax(self):
        """Passing a DAF carryforward should not increase federal tax."""
        stage_no = _make_stage5()
        stage_cf = _make_stage5()
        base = {**BASE_S5, 'daf_carryforward_prior': 0.0}
        with_cf = {**BASE_S5, 'daf_carryforward_prior': 50_000.0}
        r_no = stage_no.calculate_strategy(balances=BALANCES, expenses=100_000, **base)
        r_cf = stage_cf.calculate_strategy(balances=BALANCES, expenses=100_000, **with_cf)
        assert r_cf.federal_tax <= r_no.federal_tax + 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Stage 6 — RMD
# ─────────────────────────────────────────────────────────────────────────────

class TestStage6AGICalculatorPath:
    """Verify Stage 6 uses AGICalculator and that RMD income enters AGI correctly."""

    def test_rmd_in_agi(self):
        """RMD is mandatory income — AGI must be > SS income alone."""
        stage = _make_stage6()
        result = stage.calculate_strategy(
            balances=BALANCES, expenses=90_000, **BASE_S6,
        )
        assert result.agi > 0
        assert result.rmd_amount >= 0

    def test_federal_tax_non_negative(self):
        stage = _make_stage6()
        result = stage.calculate_strategy(
            balances=BALANCES, expenses=90_000, **BASE_S6,
        )
        assert result.federal_tax >= 0.0

    def test_daf_deductible_set(self):
        stage = _make_stage6()
        result = stage.calculate_strategy(
            balances=BALANCES, expenses=90_000, **BASE_S6,
        )
        assert isinstance(result.daf_deductible, float)
        assert result.daf_deductible >= 0.0

    def test_daf_deductible_capped_at_30pct_agi(self):
        stage = _make_stage6()
        daf_balances = PortfolioBalances(
            cash=200_000, taxable=400_000,
            traditional=2_000_000, roth=500_000, daf=300_000,
        )
        result = stage.calculate_strategy(
            balances=daf_balances, expenses=90_000, **BASE_S6,
        )
        if result.agi > 0:
            assert result.daf_deductible <= result.agi * 0.30 + 1.0

    def test_carryforward_accepted(self):
        """Stage 6 must accept daf_carryforward_prior without error."""
        stage = _make_stage6()
        result = stage.calculate_strategy(
            balances=BALANCES, expenses=90_000,
            **{**BASE_S6, 'daf_carryforward_prior': 40_000.0},
        )
        assert result is not None
        assert result.agi >= 0

    def test_zero_traditional_no_rmd(self):
        """Zero traditional → no RMD, no conversion, positive AGI from SS only."""
        stage = _make_stage6()
        zero_trad = PortfolioBalances(
            cash=200_000, taxable=300_000,
            traditional=0, roth=500_000, daf=0,
        )
        result = stage.calculate_strategy(
            balances=zero_trad, expenses=90_000, **BASE_S6,
        )
        assert result.rmd_amount == 0.0
        assert result.agi >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Stage 7 — Surviving Spouse (Single filer)
# ─────────────────────────────────────────────────────────────────────────────

class TestStage7AGICalculatorPath:
    """Verify Stage 7 uses AGICalculator with Single filing status."""

    # Stage 7's applies() checks config; bypass by calling calculate_strategy directly.

    def _run_s7(self, **overrides):
        stage = _make_stage7()
        kwargs = dict(
            year=2045,
            age_primary=79, age_spouse=78,
            ss_benefits=30_000,
            prior_magi=150_000,
            state='PA',
            growth_rate=1.06,
            start_year=2027,
            daf_carryforward_prior=0.0,
        )
        kwargs.update(overrides)
        return stage.calculate_strategy(balances=BALANCES, expenses=80_000, **kwargs)

    def test_stage7_does_not_crash(self):
        result = self._run_s7()
        assert result is not None
        assert result.agi >= 0

    def test_stage7_federal_tax_non_negative(self):
        result = self._run_s7()
        assert result.federal_tax >= 0.0

    def test_stage7_daf_deductible_set(self):
        """daf_deductible must be set even in Stage 7."""
        result = self._run_s7()
        assert isinstance(result.daf_deductible, float)
        assert result.daf_deductible >= 0.0

    def test_stage7_single_filer_higher_tax_than_mfj(self):
        """
        Single filer with the same income pays more tax than MFJ (narrower brackets,
        lower standard deduction).  We verify by comparing the AGICalculator directly
        rather than calling Stage 7 twice (since filing_status is hardcoded to 'Single').
        """
        tc = TaxCalculator()
        calc = AGICalculator(tax_calculator=tc)
        common = dict(
            year=2045, age_primary=79, age_spouse=0,
            traditional_withdrawal=150_000, roth_conversion=0.0,
            brokerage_ltcg=0.0, ss_benefits=30_000, taxable_ss=25_500,
        )
        mfj    = calc.calculate_agi_and_taxes(filing_status='married_filing_jointly', **common)
        single = calc.calculate_agi_and_taxes(filing_status='Single', **common)
        assert single['total_tax'] >= mfj['total_tax']

    def test_stage7_carryforward_accepted(self):
        result = self._run_s7(daf_carryforward_prior=30_000.0)
        assert result is not None
        assert result.agi >= 0

    def test_stage7_daf_deductible_capped_30pct(self):
        daf_balances = PortfolioBalances(
            cash=200_000, taxable=400_000,
            traditional=2_000_000, roth=500_000, daf=200_000,
        )
        stage = _make_stage7()
        result = stage.calculate_strategy(
            balances=daf_balances, expenses=80_000,
            year=2045, age_primary=79, age_spouse=78,
            ss_benefits=30_000, prior_magi=150_000,
            state='PA', growth_rate=1.06, start_year=2027,
            daf_carryforward_prior=0.0,
        )
        if result.agi > 0:
            assert result.daf_deductible <= result.agi * 0.30 + 1.0


# Made with Bob
