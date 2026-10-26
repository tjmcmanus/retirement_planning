"""
Tests for Stage 2 DAF 30% AGI limit and carryforward (IRC §170).

Key rules being tested:
  - Appreciated-securities DAF donations are deductible up to 30% of AGI in year 1
  - Excess carries forward up to 5 years
  - The _daf_carryforward instance variable persists across calculate_strategy calls
"""

import pytest
from unittest.mock import patch, MagicMock

from strategy_core.stages.stage2_prep_retirement import Stage2PrepForRetirement
from strategy_core.models import PortfolioBalances
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage2():
    """Return a Stage2 instance with real (lightweight) dependencies."""
    tc = TaxCalculator()
    am = AccountManager()
    return Stage2PrepForRetirement(tax_calculator=tc, account_manager=am)


def _make_cfg_mock(has_daf: bool = True, daf_fmv: float = 530_000.0,
                   start_year: int = 2026):
    """Return a mock config manager for DAF tests."""
    cfg_data = {
        "personal_info": {
            "person1_birth_date": "1965-01-01",
            "person2_birth_date": "1966-01-01",
        },
        "charitable_giving": {
            "has_daf": has_daf,
            "annual_charitable_giving": 50_000,
            "daf_initial_contribution": daf_fmv,
            "daf_annual_contribution": daf_fmv,
            "daf_contribution_start_year": start_year,
            "daf_contribution_end_year": 2040,
        },
        "income": {
            "contribution_401k_percent": 0.0,
            "contribution_roth_percent": 0.0,
        },
        "tax_strategy": {
            "property_tax_annual": 5_000,
        },
    }
    cfg = MagicMock()
    cfg.get.side_effect = lambda section, key, default=None: (
        cfg_data.get(section, {}).get(key, default)
    )
    return cfg


def _run_stage2_year(stage: Stage2PrepForRetirement,
                     year: int, wages: float,
                     daf_fmv: float = 530_000.0,
                     brokerage: float = 2_000_000.0,
                     has_daf: bool = True,
                     start_year: int = 2026):
    """
    Run calculate_strategy for one year with heavy dependencies patched out.

    Patches:
      - config → controlled DAF settings
      - _calculate_daf_for_year → returns (daf_fmv, 0) to isolate the 30% cap
      - _calculate_prep_roth_conversion → 0 (no conversion, simplifies math)
      - _calculate_backdoor_roth → 0
      - healthcare → 0
      - BETR → not needed (conversion is 0)
    """
    balances = PortfolioBalances(
        cash=200_000.0,
        taxable=brokerage,
        traditional=1_000_000.0,
        roth=200_000.0,
        daf=0.0,
    )
    cfg_mock = _make_cfg_mock(has_daf=has_daf, daf_fmv=daf_fmv, start_year=start_year)

    with (
        patch("config.get_config_manager", return_value=cfg_mock),
        # _calculate_daf_for_year determines whether/how much to contribute;
        # we return (daf_fmv, 0) so the Stage 2 30%-cap block is what sets
        # daf_tax_excess (the old uncapped excess return is intentionally discarded).
        patch("strategy._calculate_daf_for_year", return_value=(daf_fmv, 0.0)),
        patch.object(stage, "_calculate_prep_roth_conversion", return_value=0.0),
        patch.object(stage, "_calculate_backdoor_roth", return_value=0.0),
        patch.object(stage, "_calculate_preretirement_healthcare", return_value=0.0),
        patch("strategy.calculate_total_healthcare_costs", return_value=(0.0, {})),
        patch("strategy.get_health_status_from_config", return_value="good"),
    ):
        return stage.calculate_strategy(
            year=year,
            balances=balances,
            expenses=60_000.0,
            wages=wages,
            age_primary=61,
            age_spouse=60,
            max_conversion_rate=0.32,
            filing_status="married_filing_jointly",
            state="PA",
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStage2DAF30PctLimit:
    """Stage 2 applies 30% of post-conversion AGI as the deductible ceiling."""

    def test_initial_carryforward_is_zero(self):
        """A fresh Stage2 instance always starts with zero carryforward."""
        stage = _make_stage2()
        assert stage._daf_carryforward == 0.0

    def test_30pct_cap_sets_carryforward(self):
        """DAF $530k on $200k AGI → deductible=$60k, carryforward=$470k."""
        stage = _make_stage2()
        _run_stage2_year(stage, year=2026, wages=200_000.0, daf_fmv=530_000.0)

        # 30% of $200k = $60k; available = $530k; carryforward = $530k - $60k = $470k
        assert stage._daf_carryforward == pytest.approx(470_000.0, rel=0.01)

    def test_no_carryforward_when_within_limit(self):
        """DAF within 30% AGI limit → carryforward stays zero."""
        stage = _make_stage2()
        _run_stage2_year(stage, year=2026, wages=200_000.0, daf_fmv=50_000.0)
        # 30% of 200k = 60k; 50k < 60k → fully deductible
        assert stage._daf_carryforward == 0.0

    def test_30pct_cap_reduces_federal_tax(self):
        """
        With $530k DAF and $200k wages, federal tax should be on ~$130k taxable
        income (wages $200k − std_ded $30k − daf_excess $40k), NOT near-zero.

        std_deduction for MFJ 2026 ≈ $30k (no age bump under 65).
        30% limit = $60k; SALT = min($10k, state_tax+prop_tax).
        total_itemised = $60k + SALT.
        daf_tax_excess = total_itemised - std_ded.
        taxable_income = $200k - std_ded - daf_tax_excess.
        """
        stage = _make_stage2()
        strategy = _run_stage2_year(stage, year=2026, wages=200_000.0, daf_fmv=530_000.0)

        # Under the old (broken) code: taxable_income ≈ $6k → federal_tax ≈ $1k
        # Under the fix: taxable_income ≈ wages - std_ded - daf_excess > $100k
        # Just assert it's meaningfully above $1k as a smoke-test.
        assert strategy.federal_tax > 10_000, (
            f"Expected federal_tax > $10k with 30% cap; got ${strategy.federal_tax:,.0f}"
        )

    def test_daf_deductible_populated_on_bundle_year(self):
        """strategy.daf_deductible == min($530k, 30% × AGI) in the bundle year."""
        stage = _make_stage2()
        strategy = _run_stage2_year(stage, year=2026, wages=200_000.0, daf_fmv=530_000.0)

        # 30% of $200k = $60k; $530k > $60k → deductible = $60k
        assert strategy.daf_deductible == pytest.approx(60_000.0, rel=0.01)

    def test_daf_deductible_populated_on_carryforward_year(self):
        """In year 2 (no new bundle), daf_deductible reflects the carryforward consumed."""
        stage = _make_stage2()
        _run_stage2_year(stage, year=2026, wages=200_000.0, daf_fmv=530_000.0)
        # carryforward after 2026 ≈ $470k

        strategy2 = _run_stage2_year(stage, year=2027, wages=200_000.0,
                                     daf_fmv=0.0, start_year=2026)
        # available in 2027 = $470k; 30% of $200k = $60k → deductible = $60k
        assert strategy2.daf_deductible == pytest.approx(60_000.0, rel=0.01)

    def test_daf_deductible_zero_when_no_daf(self):
        """daf_deductible is 0 when has_daf=False."""
        stage = _make_stage2()
        strategy = _run_stage2_year(stage, year=2026, wages=200_000.0,
                                    daf_fmv=0.0, has_daf=False)
        assert strategy.daf_deductible == 0.0

    def test_carryforward_consumed_next_year(self):
        """Carryforward from year 1 reduces what carries out of year 2."""
        stage = _make_stage2()

        # Year 1: $530k donation on $200k wages → $470k carryforward
        _run_stage2_year(stage, year=2026, wages=200_000.0, daf_fmv=530_000.0)
        cf_after_y1 = stage._daf_carryforward
        assert cf_after_y1 == pytest.approx(470_000.0, rel=0.01)

        # Year 2: no new bundle (daf_fmv=0), but carryforward of $470k is available
        # 30% of $200k = $60k → deductible $60k, carryforward_new = $410k
        _run_stage2_year(stage, year=2027, wages=200_000.0,
                         daf_fmv=0.0, start_year=2026)
        assert stage._daf_carryforward == pytest.approx(410_000.0, rel=0.01)

    def test_no_daf_leaves_carryforward_zero(self):
        """has_daf=False → carryforward stays zero."""
        stage = _make_stage2()
        _run_stage2_year(stage, year=2026, wages=200_000.0,
                         daf_fmv=0.0, has_daf=False)
        assert stage._daf_carryforward == 0.0

    def test_carryforward_resets_on_new_instance(self):
        """Each new Stage2 instance starts with zero carryforward."""
        stage1 = _make_stage2()
        _run_stage2_year(stage1, year=2026, wages=200_000.0, daf_fmv=530_000.0)
        assert stage1._daf_carryforward > 0

        stage2 = _make_stage2()
        assert stage2._daf_carryforward == 0.0

# Made with Bob
