"""
Coverage tests for income_expense.py pure helper functions.

Tests only the standalone, non-Streamlit-dependent helpers.
"""
import pytest

from income_expense import (
    _calculate_year_distributions,
    _validate_tax_inputs,
    _apply_seed_once,
    _update_daf,
    YEAR_2026_CONVERSION,
    PRE_SSI_CONVERSION,
    YEAR_2027_DAF_RATIO,
)


# ---------------------------------------------------------------------------
# _calculate_year_distributions
# ---------------------------------------------------------------------------

class TestCalculateYearDistributions:
    def test_year_before_2026_returns_zeros(self):
        result = _calculate_year_distributions(2025, 2032, 100_000)
        assert result == (0.0, 0.0, 0.0)

    def test_invalid_ssi_year_raises(self):
        with pytest.raises(ValueError, match="ssi_year"):
            _calculate_year_distributions(2027, 2026, 100_000)

    def test_ssi_year_equal_2027_raises(self):
        with pytest.raises(ValueError):
            _calculate_year_distributions(2027, 2027, 100_000)

    def test_year_2026_returns_conversion(self):
        planned_dist, daf, conversions = _calculate_year_distributions(2026, 2032, 100_000)
        assert planned_dist == 0.0
        assert daf == 0.0
        assert conversions == float(YEAR_2026_CONVERSION)

    def test_year_2027_uses_planned_dist(self):
        planned = 200_000.0
        planned_dist, daf, conversions = _calculate_year_distributions(2027, 2032, planned)
        assert planned_dist == planned
        assert daf == pytest.approx(planned * YEAR_2027_DAF_RATIO)
        assert conversions == 0.0

    def test_pre_ssi_year_returns_pre_ssi_conversion(self):
        # year between 2027 and ssi_year (e.g. 2028, ssi_year=2032)
        planned_dist, daf, conversions = _calculate_year_distributions(2028, 2032, 100_000)
        assert planned_dist == 0.0
        assert daf == 0.0
        assert conversions == float(PRE_SSI_CONVERSION)

    def test_year_at_ssi_year_returns_zeros(self):
        planned_dist, daf, conversions = _calculate_year_distributions(2032, 2032, 100_000)
        assert planned_dist == 0.0
        assert daf == 0.0
        assert conversions == 0.0

    def test_year_after_ssi_year_returns_zeros(self):
        planned_dist, daf, conversions = _calculate_year_distributions(2035, 2032, 100_000)
        assert planned_dist == 0.0
        assert daf == 0.0
        assert conversions == 0.0


# ---------------------------------------------------------------------------
# _validate_tax_inputs
# ---------------------------------------------------------------------------

class TestValidateTaxInputs:
    def test_valid_inputs_pass_through(self):
        income, daf, year = _validate_tax_inputs(100_000.0, 10_000.0, 2026)
        assert income == 100_000.0
        assert daf == 10_000.0
        assert year == 2026

    def test_negative_income_clamped_to_zero(self):
        income, daf, year = _validate_tax_inputs(-5_000.0, 0.0, 2026)
        assert income == 0.0

    def test_negative_daf_clamped_to_zero(self):
        income, daf, year = _validate_tax_inputs(50_000.0, -1_000.0, 2026)
        assert daf == 0.0

    def test_non_int_year_raises(self):
        with pytest.raises((TypeError, ValueError)):
            _validate_tax_inputs(50_000.0, 0.0, 2026.5)

    def test_year_too_low_raises(self):
        with pytest.raises(ValueError):
            _validate_tax_inputs(50_000.0, 0.0, 1800)

    def test_year_too_high_raises(self):
        with pytest.raises(ValueError):
            _validate_tax_inputs(50_000.0, 0.0, 2200)


# ---------------------------------------------------------------------------
# _apply_seed_once
# ---------------------------------------------------------------------------

class TestApplySeedOnce:
    def test_zero_current_returns_seed(self):
        # current == 0 means first iteration: return seed
        result = _apply_seed_once(0.0, 500_000.0)
        assert result == 500_000.0

    def test_nonzero_current_returns_zero(self):
        # current != 0: seed was already applied, return 0
        result = _apply_seed_once(1_000_000.0, 500_000.0)
        assert result == 0.0

    def test_zero_current_zero_seed_returns_zero(self):
        result = _apply_seed_once(0.0, 0.0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# _update_daf
# ---------------------------------------------------------------------------

class TestUpdateDaf:
    def test_zero_balances_returns_zero(self):
        result = _update_daf(0.0, 0.0, 0.05)
        assert result == 0.0

    def test_formula_daf_in_times_rate_plus_contribution(self):
        # _update_daf(daf_in, daf, daf_rate) = daf_in * (1 - daf_rate) + daf
        result = _update_daf(100_000.0, 50_000.0, 0.05)
        expected = 100_000.0 * 0.95 + 50_000.0
        assert result == pytest.approx(expected)

    def test_100pct_daf_rate_spends_all_existing(self):
        # Existing balance fully spent, only new contribution remains
        result = _update_daf(100_000.0, 20_000.0, 1.0)
        assert result == pytest.approx(20_000.0)

    def test_zero_daf_rate_no_spend_down(self):
        result = _update_daf(100_000.0, 10_000.0, 0.0)
        assert result == pytest.approx(110_000.0)
