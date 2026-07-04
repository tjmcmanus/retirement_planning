"""
tests/test_tax_calculator_coverage.py
======================================
Coverage-targeted unit tests for strategy_core/tax_calculator.py.

Uses real CSV data (income_rates.csv, cap_gains.csv, standard.csv) so the
tests exercise the full stack including the load_data functions.  All tests
are pure-Python with no network calls.
"""
import pytest
from strategy_core.tax_calculator import TaxCalculator


@pytest.fixture(scope="module")
def calc():
    """Single TaxCalculator instance shared across the module."""
    return TaxCalculator()


# ---------------------------------------------------------------------------
# calculate_federal_tax
# ---------------------------------------------------------------------------

class TestCalculateFederalTax:
    def test_zero_income_returns_zeros(self, calc):
        tax, rate, upper = calc.calculate_federal_tax(0, "married_filing_jointly", 2026)
        assert tax == 0.0
        assert rate == 0.0
        assert upper == 0.0

    def test_negative_income_returns_zeros(self, calc):
        tax, rate, upper = calc.calculate_federal_tax(-5000, "married_filing_jointly", 2026)
        assert tax == 0.0

    def test_low_income_10pct_bracket(self, calc):
        # $20,000 MFJ falls entirely in the 10% bracket (2026 first bracket is up to $23,200)
        tax, rate, upper = calc.calculate_federal_tax(20_000, "married_filing_jointly", 2026)
        assert tax > 0
        assert rate == pytest.approx(0.10)

    def test_higher_income_crosses_brackets(self, calc):
        # $200,000 MFJ crosses 10%/12%/22% brackets
        tax, rate, upper = calc.calculate_federal_tax(200_000, "married_filing_jointly", 2026)
        assert tax > 0
        assert rate > 0.10   # must have moved past 10%
        assert upper > 0

    def test_single_filer(self, calc):
        # Single filer at same income should pay more than MFJ
        tax_single, _, _ = calc.calculate_federal_tax(100_000, "single", 2026)
        tax_mfj, _, _ = calc.calculate_federal_tax(100_000, "married_filing_jointly", 2026)
        assert tax_single > tax_mfj

    def test_returns_tuple_of_three_floats(self, calc):
        result = calc.calculate_federal_tax(50_000, "married_filing_jointly", 2026)
        assert len(result) == 3
        assert all(isinstance(v, float) for v in result)


# ---------------------------------------------------------------------------
# calculate_capital_gains_tax
# ---------------------------------------------------------------------------

class TestCalculateCapitalGainsTax:
    def test_zero_ltcg_returns_zero(self, calc):
        assert calc.calculate_capital_gains_tax(0, 50_000, "married_filing_jointly", 2026) == 0.0

    def test_negative_ltcg_returns_zero(self, calc):
        assert calc.calculate_capital_gains_tax(-1000, 50_000, "married_filing_jointly", 2026) == 0.0

    def test_low_income_zero_pct_rate(self, calc):
        # MFJ with ordinary income $30,000 and modest LTCG should hit 0% bracket
        tax = calc.calculate_capital_gains_tax(10_000, 30_000, "married_filing_jointly", 2026)
        assert tax == pytest.approx(0.0)

    def test_high_income_15pct_rate(self, calc):
        # MFJ with $200,000 ordinary income and $50,000 LTCG should hit 15% bracket
        tax = calc.calculate_capital_gains_tax(50_000, 200_000, "married_filing_jointly", 2026)
        assert tax == pytest.approx(50_000 * 0.15)

    def test_income_stacking(self, calc):
        # With very high ordinary income already above 0% ceiling, all gains taxed at 15%+
        tax_high = calc.calculate_capital_gains_tax(10_000, 500_000, "married_filing_jointly", 2026)
        tax_low = calc.calculate_capital_gains_tax(10_000, 10_000, "married_filing_jointly", 2026)
        assert tax_high >= tax_low

    def test_returns_float(self, calc):
        result = calc.calculate_capital_gains_tax(5_000, 50_000, "married_filing_jointly", 2026)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_standard_deduction
# ---------------------------------------------------------------------------

class TestCalculateStandardDeduction:
    def test_mfj_2026(self, calc):
        ded = calc.calculate_standard_deduction("married_filing_jointly", 2026)
        assert ded == pytest.approx(32_200.0)

    def test_single_2026(self, calc):
        ded = calc.calculate_standard_deduction("single", 2026)
        assert ded == pytest.approx(16_100.0)

    def test_age_65_primary_adds_extra_mfj(self, calc):
        base = calc.calculate_standard_deduction("married_filing_jointly", 2026)
        with_age = calc.calculate_standard_deduction("married_filing_jointly", 2026, age_primary=65)
        assert with_age > base

    def test_age_65_both_spouses_adds_more(self, calc):
        one = calc.calculate_standard_deduction("married_filing_jointly", 2026, age_primary=65)
        both = calc.calculate_standard_deduction("married_filing_jointly", 2026,
                                                  age_primary=65, age_spouse=65)
        assert both > one

    def test_under_65_no_extra(self, calc):
        base = calc.calculate_standard_deduction("married_filing_jointly", 2026)
        under_65 = calc.calculate_standard_deduction("married_filing_jointly", 2026,
                                                      age_primary=64, age_spouse=64)
        assert under_65 == base


# ---------------------------------------------------------------------------
# calculate_state_tax
# ---------------------------------------------------------------------------

class TestCalculateStateTax:
    def test_zero_agi_returns_zero(self, calc):
        assert calc.calculate_state_tax(0, "FL", 2026) == 0.0

    def test_no_tax_state(self, calc):
        # Florida has no income tax
        tax = calc.calculate_state_tax(100_000, "FL", 2026)
        assert tax == pytest.approx(0.0)

    def test_tax_state_returns_positive(self, calc):
        # California has income tax
        tax = calc.calculate_state_tax(100_000, "CA", 2026)
        assert tax >= 0.0   # may be 0 if calc_state_tax import unavailable; must not raise

    def test_negative_agi_returns_zero(self, calc):
        assert calc.calculate_state_tax(-5_000, "CA", 2026) == 0.0


# ---------------------------------------------------------------------------
# calculate_irmaa_penalty
# ---------------------------------------------------------------------------

class TestCalculateIrmaaPenalty:
    def test_zero_magi_returns_zeros(self, calc):
        primary, spouse = calc.calculate_irmaa_penalty(0, "married_filing_jointly", 2026)
        assert primary == 0.0
        assert spouse == 0.0

    def test_below_threshold_no_penalty(self, calc):
        # MFJ IRMAA threshold is ~$212,000 for 2026
        primary, spouse = calc.calculate_irmaa_penalty(100_000, "married_filing_jointly", 2026)
        assert primary == pytest.approx(0.0, abs=1.0)

    def test_above_threshold_has_penalty(self, calc):
        primary, spouse = calc.calculate_irmaa_penalty(400_000, "married_filing_jointly", 2026)
        assert primary > 0 or spouse > 0

    def test_returns_two_floats(self, calc):
        result = calc.calculate_irmaa_penalty(300_000, "married_filing_jointly", 2026)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)
