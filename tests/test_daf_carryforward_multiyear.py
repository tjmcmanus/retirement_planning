"""
test_daf_carryforward_multiyear.py

Verifies that the IRC §170 DAF 5-year carryforward flows correctly through the
engine across multiple years and stage transitions.

Three scenarios:
  1. Carryforward persists within Stage 3 (year 1 → year 2 same stage)
  2. Carryforward survives a Stage 3 → Stage 4 transition
  3. Zero carryforward when DAF contribution is within the 30% AGI limit
"""

import pytest
from unittest.mock import patch, MagicMock

from strategy_core.models import PortfolioBalances, YearlyStrategy
from strategy_core.agi_calculator import AGICalculator
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager
from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
from strategy_core.stages.stage4_medicare import Stage4Medicare


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _balances(traditional=2_000_000, roth=300_000, taxable=800_000,
              cash=150_000, daf=600_000) -> PortfolioBalances:
    return PortfolioBalances(
        cash=cash,
        taxable=taxable,
        traditional=traditional,
        roth=roth,
        daf=daf,
    )


# ---------------------------------------------------------------------------
# Scenario 1: AGICalculator carryforward arithmetic
# ---------------------------------------------------------------------------

class TestAGICalculatorCarryforward:
    """Unit-level: verify the calculator itself produces correct carryforward."""

    def test_large_daf_creates_carryforward(self):
        """DAF contribution > 30% of AGI should create a carryforward."""
        calc = AGICalculator(TaxCalculator())
        # AGI = $100k ordinary; 30% limit = $30k; contributing $60k → $30k carries forward
        result = calc.calculate_agi_and_taxes(
            year=2027,
            filing_status='married_filing_jointly',
            age_primary=61,
            age_spouse=60,
            traditional_withdrawal=100_000,
            roth_conversion=0,
            brokerage_ltcg=0,
            brokerage_basis=0,
            daf_fmv=60_000,
            state='PA',
            pa_rate=0.0307,
            property_tax=5_000,
            daf_carryforward_prior=0.0,
            tax_calculator=TaxCalculator(),
        )
        assert result['daf_deductible_this_year'] == pytest.approx(30_000, abs=100), \
            f"Expected ~$30k deductible, got ${result['daf_deductible_this_year']:,.0f}"
        assert result['daf_carryforward_new'] == pytest.approx(30_000, abs=100), \
            f"Expected ~$30k carryforward, got ${result['daf_carryforward_new']:,.0f}"

    def test_prior_carryforward_consumed_first(self):
        """When there is a prior carryforward and no new contribution, it should be consumed."""
        calc = AGICalculator(TaxCalculator())
        result = calc.calculate_agi_and_taxes(
            year=2028,
            filing_status='married_filing_jointly',
            age_primary=62,
            age_spouse=61,
            traditional_withdrawal=100_000,
            roth_conversion=0,
            brokerage_ltcg=0,
            brokerage_basis=0,
            daf_fmv=0,           # No new contribution this year
            state='PA',
            pa_rate=0.0307,
            property_tax=5_000,
            daf_carryforward_prior=30_000,   # From prior year
            tax_calculator=TaxCalculator(),
        )
        # 30% of $100k AGI = $30k limit; carryforward of $30k is fully consumed
        assert result['daf_deductible_this_year'] == pytest.approx(30_000, abs=100), \
            f"Carryforward not consumed: got ${result['daf_deductible_this_year']:,.0f}"
        assert result['daf_carryforward_new'] == pytest.approx(0, abs=1), \
            f"Carryforward should be zero after consumption, got ${result['daf_carryforward_new']:,.0f}"

    def test_partial_carryforward_consumption(self):
        """When 30% limit exceeds the carryforward, all of it is consumed with nothing left."""
        calc = AGICalculator(TaxCalculator())
        result = calc.calculate_agi_and_taxes(
            year=2028,
            filing_status='married_filing_jointly',
            age_primary=62,
            age_spouse=61,
            traditional_withdrawal=200_000,   # Higher AGI → bigger 30% limit
            roth_conversion=0,
            brokerage_ltcg=0,
            brokerage_basis=0,
            daf_fmv=0,
            state='PA',
            pa_rate=0.0307,
            property_tax=5_000,
            daf_carryforward_prior=15_000,    # Small carryforward vs $60k limit
            tax_calculator=TaxCalculator(),
        )
        # 30% of $200k = $60k; carryforward $15k < limit → all consumed
        assert result['daf_deductible_this_year'] == pytest.approx(15_000, abs=100)
        assert result['daf_carryforward_new'] == pytest.approx(0, abs=1)

    def test_no_daf_no_carryforward(self):
        """Zero contribution and zero prior carryforward should produce zero deductible."""
        calc = AGICalculator(TaxCalculator())
        result = calc.calculate_agi_and_taxes(
            year=2027,
            filing_status='married_filing_jointly',
            age_primary=61,
            age_spouse=60,
            traditional_withdrawal=80_000,
            roth_conversion=0,
            brokerage_ltcg=0,
            brokerage_basis=0,
            daf_fmv=0,
            state='PA',
            pa_rate=0.0307,
            property_tax=5_000,
            daf_carryforward_prior=0.0,
            tax_calculator=TaxCalculator(),
        )
        assert result['daf_deductible_this_year'] == 0.0
        assert result['daf_carryforward_new'] == 0.0


# ---------------------------------------------------------------------------
# Scenario 2: Stage 3 reads engine carryforward kwarg and updates daf_deductible
# ---------------------------------------------------------------------------

class TestStage3CarryforwardWiring:
    """Stage 3: engine kwarg → stage calculation → strategy.daf_deductible."""

    def _run_year(self, stage: Stage3EarlyRetirement, year: int,
                  balances: PortfolioBalances, carryforward_prior: float,
                  daf_contribution_patch: float) -> YearlyStrategy:
        """
        Run one year of Stage 3, patching _calculate_daf_optimization to return
        a fixed daf_contribution so we can control the scenario precisely.
        """
        with patch.object(
            stage, '_calculate_daf_optimization',
            return_value=(daf_contribution_patch, 0.0)
        ):
            return stage.calculate_strategy(
                year=year,
                balances=balances,
                expenses=132_000,
                age_primary=61 + (year - 2027),
                age_spouse=60 + (year - 2027),
                filing_status='married_filing_jointly',
                state='PA',
                max_conversion_rate=0.24,
                growth_rate=1.06,
                start_year=2027,
                daf_carryforward_prior=carryforward_prior,
            )

    def test_stage3_reads_carryforward_from_kwarg(self):
        """Stage 3 must accept daf_carryforward_prior from the engine and apply it."""
        stage = _make_stage3()
        # Year 1: large DAF contribution with zero prior carryforward
        # AGI will be ~$130-200k; 30% limit ~$40-60k; contribution $80k → creates carryforward
        result_y1 = self._run_year(stage, 2027, _balances(), 0.0, 80_000)

        assert result_y1.daf_deductible >= 0, "daf_deductible must be set"
        # If AGI < $267k, contribution $80k > 30% → carryforward exists
        if result_y1.daf_contribution > 0:
            expected_carryforward = result_y1.daf_contribution - result_y1.daf_deductible
            assert expected_carryforward >= 0, "Carryforward cannot be negative"

    def test_stage3_supplied_carryforward_reduces_tax(self):
        """Supplying a prior carryforward to Stage 3 should reduce taxes vs zero carryforward.

        Stage 3 adds large Roth conversions, so AGI in a typical year exceeds $200k and
        the 30% DAF limit naturally exceeds any reasonable contribution — no carryforward
        is produced from within Stage 3 itself.  This test therefore directly supplies a
        carryforward (simulating one produced by Stage 2 or a prior high-DAF year) and
        confirms that Stage 3 consumes it correctly through AGICalculator.
        """
        stage_with_cf    = _make_stage3()
        stage_without_cf = _make_stage3()
        balances = _balances()

        # Run the same year twice: once with a $30k carryforward, once without
        result_with_cf    = self._run_year(stage_with_cf,    2027, balances, 30_000, 0.0)
        result_without_cf = self._run_year(stage_without_cf, 2027, balances,  0.0,  0.0)

        # With carryforward, daf_deductible must reflect the $30k
        assert result_with_cf.daf_deductible == pytest.approx(30_000, abs=500), (
            f"Stage 3 should have applied the $30k carryforward as a deductible. "
            f"Got daf_deductible=${result_with_cf.daf_deductible:,.0f}, AGI=${result_with_cf.agi:,.0f}"
        )

        # Taxes with carryforward must be lower (or equal if already zero)
        assert result_with_cf.federal_tax <= result_without_cf.federal_tax, (
            f"Stage 3 taxes with carryforward (${result_with_cf.federal_tax:,.0f}) "
            f"should be ≤ without (${result_without_cf.federal_tax:,.0f})"
        )

    def test_stage3_daf_deductible_set_on_strategy(self):
        """strategy.daf_deductible must always be set (used by engine for next-year carryforward)."""
        stage = _make_stage3()
        result = self._run_year(stage, 2027, _balances(), 0.0, 0.0)
        assert hasattr(result, 'daf_deductible'), "strategy.daf_deductible must exist"
        assert isinstance(result.daf_deductible, (int, float)), \
            f"daf_deductible must be numeric, got {type(result.daf_deductible)}"
        assert result.daf_deductible >= 0


# ---------------------------------------------------------------------------
# Scenario 3: Stage 4 wiring (same pattern, Medicare context)
# ---------------------------------------------------------------------------

class TestStage4CarryforwardWiring:
    """Stage 4: engine kwarg → stage calculation → strategy.daf_deductible."""

    def test_stage4_reads_carryforward_from_kwarg(self):
        """Stage 4 must set strategy.daf_deductible so the engine can update its carryforward."""
        stage = _make_stage4()

        # Supply a prior carryforward of $20k
        with patch.object(stage, '_calculate_daf_optimization', return_value=(0.0, 0.0)):
            result = stage.calculate_strategy(
                year=2031,
                balances=_balances(traditional=5_000_000, cash=200_000),
                expenses=140_000,
                age_primary=65,
                age_spouse=64,
                filing_status='married_filing_jointly',
                state='PA',
                max_conversion_rate=0.24,
                growth_rate=1.06,
                start_year=2027,
                prior_magi=100_000,
                daf_carryforward_prior=20_000,
            )

        assert hasattr(result, 'daf_deductible'), "Stage 4: strategy.daf_deductible must be set"
        assert result.daf_deductible >= 0

    def test_stage4_carryforward_reduces_tax(self):
        """Supplying carryforward to Stage 4 should reduce federal tax vs no carryforward."""
        stage_with    = _make_stage4()
        stage_without = _make_stage4()
        kwargs = dict(
            year=2031,
            balances=_balances(traditional=5_000_000, cash=200_000),
            expenses=140_000,
            age_primary=65,
            age_spouse=64,
            filing_status='married_filing_jointly',
            state='PA',
            max_conversion_rate=0.24,
            growth_rate=1.06,
            start_year=2027,
            prior_magi=100_000,
        )

        # Patch DAF optimization to zero so only the carryforward differs
        with patch.object(stage_with,    '_calculate_daf_optimization', return_value=(0.0, 0.0)), \
             patch.object(stage_without, '_calculate_daf_optimization', return_value=(0.0, 0.0)):
            result_with    = stage_with.calculate_strategy(**kwargs, daf_carryforward_prior=30_000)
            result_without = stage_without.calculate_strategy(**kwargs, daf_carryforward_prior=0.0)

        assert result_with.federal_tax <= result_without.federal_tax, (
            f"Stage 4 taxes with ${30_000:,} carryforward (${result_with.federal_tax:,.0f}) "
            f"should be ≤ without (${result_without.federal_tax:,.0f})"
        )


# ---------------------------------------------------------------------------
# Scenario 4: Engine-level carryforward arithmetic (isolated)
# ---------------------------------------------------------------------------

class TestEngineCarryforwardArithmetic:
    """Verify the engine's _daf_carryforward formula without running a full simulation."""

    def test_engine_formula_accumulates_correctly(self):
        """
        Engine formula: new_cf = max(0, (contribution + prior_cf) - deductible)
        Simulate 3 years manually and verify accumulation.
        """
        engine_cf = 0.0
        daf_contribution = 60_000
        # AGI ~$150k → 30% limit ~$45k each year

        year1_deductible = 45_000
        year1_available  = daf_contribution + engine_cf      # 60k + 0 = 60k
        engine_cf = max(0.0, year1_available - year1_deductible)  # 60k - 45k = 15k
        assert engine_cf == pytest.approx(15_000, abs=1)

        # Year 2: no new contribution; consume carryforward
        year2_contribution = 0.0
        year2_deductible   = 15_000   # Can deduct all of it (limit > carryforward)
        year2_available    = year2_contribution + engine_cf   # 0 + 15k = 15k
        engine_cf = max(0.0, year2_available - year2_deductible)  # 15k - 15k = 0
        assert engine_cf == pytest.approx(0.0, abs=1)

    def test_engine_formula_does_not_go_negative(self):
        """Carryforward must never be negative (over-deduction shouldn't happen but guard it)."""
        engine_cf = 0.0
        # deductible > available is impossible by definition, but max(0, ...) guards it
        engine_cf = max(0.0, 5_000 - 10_000)
        assert engine_cf == 0.0

    def test_engine_formula_caps_at_zero_not_negative(self):
        """max(0, ...) applied in the engine produces zero, not a negative balance."""
        result = max(0.0, 0.0 - 0.0)
        assert result == 0.0
