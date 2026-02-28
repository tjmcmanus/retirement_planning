#!/usr/bin/env python3
"""
Unit tests for calculations.py

Verifies that calculate_taxable_income correctly applies progressive taxation
using non-overlapping cumulative brackets (each bracket's lower == previous upper).
Tax amounts are truncated to whole dollars via floor (IRS standard), not rounded.
"""

import math
import pandas as pd
import pytest
from calculations import calculate_taxable_income, calc_agi, calculate_atm, calc_roth_conversions_tax


# Sample brackets mirroring the structure in income_rates.csv (2025 MFJ values)
BRACKETS_2025 = pd.DataFrame([
    {'lower':      0, 'upper':  23850, 'rate': 0.10},
    {'lower':  23850, 'upper':  96950, 'rate': 0.12},
    {'lower':  96950, 'upper': 206700, 'rate': 0.22},
    {'lower': 206700, 'upper': 394600, 'rate': 0.24},
    {'lower': 394600, 'upper': 501050, 'rate': 0.32},
    {'lower': 501050, 'upper': 751600, 'rate': 0.35},
    {'lower': 751600, 'upper': 4000000, 'rate': 0.37},
])


def test_income_in_first_bracket():
    """Income entirely within the 10% bracket should be taxed at 10% only."""
    income = 10_000
    tax, max_rate, _ = calculate_taxable_income(income, BRACKETS_2025)
    assert tax == math.floor(10_000 * 0.10)
    assert max_rate == 0.10


def test_income_spanning_two_brackets():
    """Income spanning the 10% and 12% brackets — no double-taxation of lower income."""
    income = 50_000
    # 10% on first $23,850 = $2,385
    # 12% on next $26,150 ($50,000 - $23,850) = $3,138
    expected_tax = math.floor(23_850 * 0.10) + math.floor(26_150 * 0.12)
    tax, max_rate, _ = calculate_taxable_income(income, BRACKETS_2025)
    assert tax == expected_tax, f"Expected {expected_tax}, got {tax}"
    assert max_rate == 0.12


def test_income_at_bracket_boundary():
    """Income exactly at a bracket boundary should not spill into the next bracket."""
    income = 23_850  # top of 10% bracket
    tax, max_rate, _ = calculate_taxable_income(income, BRACKETS_2025)
    assert tax == math.floor(23_850 * 0.10)
    assert max_rate == 0.10


def test_income_spanning_all_brackets():
    """High income spanning all brackets — each bracket taxed only on its marginal width."""
    income = 800_000
    expected_tax = (
        math.floor(23_850 * 0.10)                    # 10% bracket
        + math.floor((96_950 - 23_850) * 0.12)       # 12% bracket
        + math.floor((206_700 - 96_950) * 0.22)      # 22% bracket
        + math.floor((394_600 - 206_700) * 0.24)     # 24% bracket
        + math.floor((501_050 - 394_600) * 0.32)     # 32% bracket
        + math.floor((751_600 - 501_050) * 0.35)     # 35% bracket
        + math.floor((800_000 - 751_600) * 0.37)     # 37% bracket
    )
    tax, max_rate, _ = calculate_taxable_income(income, BRACKETS_2025)
    assert tax == expected_tax, f"Expected {expected_tax}, got {tax}"
    assert max_rate == 0.37


def test_zero_income():
    """Zero income should produce zero tax."""
    tax, max_rate, upper_max = calculate_taxable_income(0, BRACKETS_2025)
    assert tax == 0.0


def test_negative_income():
    """Negative income (net loss scenario) should produce zero tax."""
    tax, max_rate, upper_max = calculate_taxable_income(-1000, BRACKETS_2025)
    assert tax == 0.0
    assert max_rate == 0.0
    assert upper_max == 0.0


def test_no_double_taxation_of_lower_bracket_income():
    """
    Regression test: confirms lower-bracket income is NOT double-taxed at higher rates.
    With income=$50,000, the 10% bracket ($0-$23,850) must only be taxed at 10%,
    not also at 12% (which would happen if brackets were overlapping from $0).
    """
    income = 50_000
    tax, _, _ = calculate_taxable_income(income, BRACKETS_2025)
    # If double-taxation occurred, the 12% bracket would add 12% on $23,850 extra
    double_tax_amount = math.floor(23_850 * 0.12)
    correct_tax = math.floor(23_850 * 0.10) + math.floor(26_150 * 0.12)
    # Tax must equal correct progressive amount, not the inflated double-taxed amount
    assert tax == correct_tax
    assert tax != correct_tax + double_tax_amount


# ---------------------------------------------------------------------------
# Standard deduction DataFrame used by calc_agi tests (MFJ 2025: $30,000)
# ---------------------------------------------------------------------------
STD_DED_DF = pd.DataFrame([
    {'lower': 0, 'upper': 4_000_000, 'deduction': 30_000}
])


def test_calc_agi_daf_itemized_route():
    """
    When DAF > standard deduction, AGI = total_income - daf only.
    The standard deduction is NOT also subtracted (DAF replaces it as the
    itemized deduction). This locks in the intended formula after the
    removal of the erroneous double-subtraction of std_deduction_base.
    """
    gross_income = 200_000
    interest = 0
    daf = 50_000          # daf > std_deduction ($30,000) → itemized route
    total_income = gross_income + interest

    agi = calc_agi(gross_income, interest, STD_DED_DF, daf)

    # Expected: only DAF is deducted, NOT daf + std_deduction
    expected_agi = total_income - daf          # 150,000
    wrong_agi    = total_income - daf - 30_000 # 120,000 (old double-deduction bug)

    assert agi == expected_agi, (
        f"DAF itemized route: expected AGI={expected_agi:,.0f}, got {agi:,.0f}"
    )
    assert agi != wrong_agi, "AGI must not double-subtract the standard deduction"


def test_calc_agi_standard_deduction_route():
    """When DAF <= standard deduction, AGI = total_income - std_deduction."""
    gross_income = 200_000
    interest = 0
    daf = 5_000           # daf < std_deduction ($30,000) → standard route

    agi = calc_agi(gross_income, interest, STD_DED_DF, daf)

    expected_agi = gross_income + interest - 30_000  # 170,000
    assert agi == expected_agi, (
        f"Standard deduction route: expected AGI={expected_agi:,.0f}, got {agi:,.0f}"
    )


# ---------------------------------------------------------------------------
# ATM bracket matching tests
# ---------------------------------------------------------------------------
# ATM DataFrame: two brackets mirroring a typical AMT structure.
# Bracket 0: income $0–$99,999  (lower bracket, rate 0%)  — exemption zone
# Bracket 1: income $100,000–$500,000 (upper bracket, rate 26%)
# phase_out=$150,000, exception_rate=0.25 means the $40,000 deduction is
# reduced by $0.25 for every $1 of MAGI above $150,000.
ATM_DF = pd.DataFrame([
    {'year': 2025, 'deduction': 40_000, 'lower':       0, 'upper':  99_999,
     'phase_out': 150_000, 'rate': 0.00, 'exception_rate': 0.25},
    {'year': 2025, 'deduction': 40_000, 'lower': 100_000, 'upper': 500_000,
     'phase_out': 150_000, 'rate': 0.26, 'exception_rate': 0.25},
])


def test_calculate_atm_bracket_matching_below_phase_out():
    """
    With total_income=$120,000 and cap_gains=$0, MAGI=$120,000 which is below
    the phase_out threshold of $150,000, so the full $40,000 deduction applies.
    ATM income = 120,000 - 40,000 = 80,000, which falls in bracket 0 (0–99,999).
    Expected: total_tax=0, lowerby=80,000 - 0 = 80,000.
    std_deduction is correctly excluded; adding it would push income to a
    different bracket and produce wrong results.
    """
    total_income = 120_000
    cap_gains = 0
    total_tax, lowerby = calculate_atm(total_income, cap_gains, ATM_DF)
    assert total_tax == 0.0, f"Expected tax=0, got {total_tax}"
    assert lowerby == 80_000.0, f"Expected lowerby=80000, got {lowerby}"


def test_calculate_atm_bracket_matching_above_phase_out():
    """
    With total_income=$200,000 and cap_gains=$0, MAGI=$200,000 which is above
    the phase_out threshold of $150,000.
    Excess = 200,000 - 150,000 = 50,000; reduction = 0.25 * 50,000 = 12,500.
    Adjusted deduction = 40,000 - 12,500 = 27,500.
    ATM income = round(200,000 - 27,500) = 172,500, which falls in bracket 1.
    Expected: total_tax = round(172,500 * 0.26) = 44,850, lowerby = 72,500.
    """
    total_income = 200_000
    cap_gains = 0
    total_tax, lowerby = calculate_atm(total_income, cap_gains, ATM_DF)
    assert total_tax == 44_850.0, f"Expected tax=44850, got {total_tax}"
    assert lowerby == 72_500.0, f"Expected lowerby=72500, got {lowerby}"


# ---------------------------------------------------------------------------
# calc_roth_conversions_tax tests
# ---------------------------------------------------------------------------
# Bracket setup used across all calc_roth_conversions_tax tests:
#   Current bracket : 22% rate, upper limit $206,700
#   Headroom bracket: 24% rate, upper limit $394,600
#   Bracket space   : $206,700 - $394,600 = $187,900 headroom width
_MAXRATE        = 0.22
_HEADROOM_RATE  = 0.24
_UPPERMAX       = 206_700.0
_HEADROOM_MAX   = 394_600.0


def test_roth_tax_maxrate_exceeds_headroom_rate_returns_zero():
    """When maxrate > headroom_rate there is no conversion benefit; tax must be 0."""
    tax = calc_roth_conversions_tax(
        maxrate=0.24,
        headroom_rate=0.22,
        uppermax=_UPPERMAX,
        agi=150_000.0,
        headroom_max=_HEADROOM_MAX,
        conversion=50_000.0,
    )
    assert tax == 0.0


def test_roth_tax_zero_conversion_returns_zero():
    """A conversion of exactly 0 must return 0 (new guard clause)."""
    tax = calc_roth_conversions_tax(
        maxrate=_MAXRATE,
        headroom_rate=_HEADROOM_RATE,
        uppermax=_UPPERMAX,
        agi=150_000.0,
        headroom_max=_HEADROOM_MAX,
        conversion=0.0,
    )
    assert tax == 0.0


def test_roth_tax_negative_conversion_returns_zero():
    """A negative conversion amount must return 0 (new guard clause)."""
    tax = calc_roth_conversions_tax(
        maxrate=_MAXRATE,
        headroom_rate=_HEADROOM_RATE,
        uppermax=_UPPERMAX,
        agi=150_000.0,
        headroom_max=_HEADROOM_MAX,
        conversion=-10_000.0,
    )
    assert tax == 0.0


def test_roth_tax_conversion_fits_entirely_in_current_bracket():
    """Conversion that fits entirely within the current bracket is taxed at maxrate only."""
    # AGI = $180,000; current bracket space = $206,700 - $180,000 = $26,700
    # Conversion = $20,000 < $26,700 → all taxed at 22%
    agi = 180_000.0
    conversion = 20_000.0
    expected_tax = conversion * _MAXRATE
    tax = calc_roth_conversions_tax(
        maxrate=_MAXRATE,
        headroom_rate=_HEADROOM_RATE,
        uppermax=_UPPERMAX,
        agi=agi,
        headroom_max=_HEADROOM_MAX,
        conversion=conversion,
    )
    assert tax == pytest.approx(expected_tax)


def test_roth_tax_conversion_fits_entirely_in_headroom_bracket():
    """Conversion that starts above the current bracket upper is taxed at headroom_rate only."""
    # AGI = $210,000 > uppermax ($206,700) → current_bracket_space = max(0, 206700-210000) = 0
    # All of conversion goes into headroom bracket at 24%
    agi = 210_000.0
    conversion = 30_000.0
    expected_tax = conversion * _HEADROOM_RATE
    tax = calc_roth_conversions_tax(
        maxrate=_MAXRATE,
        headroom_rate=_HEADROOM_RATE,
        uppermax=_UPPERMAX,
        agi=agi,
        headroom_max=_HEADROOM_MAX,
        conversion=conversion,
    )
    assert tax == pytest.approx(expected_tax)


def test_roth_tax_conversion_spans_both_brackets():
    """Conversion that spans the current and headroom brackets is split and taxed at both rates."""
    # AGI = $180,000; current_bracket_space = $26,700; headroom_bracket_space = $187,900
    # Conversion = $50,000 → $26,700 @ 22% + $23,300 @ 24%
    agi = 180_000.0
    conversion = 50_000.0
    current_space = _UPPERMAX - agi          # 26_700
    headroom_portion = conversion - current_space  # 23_300
    expected_tax = current_space * _MAXRATE + headroom_portion * _HEADROOM_RATE
    tax = calc_roth_conversions_tax(
        maxrate=_MAXRATE,
        headroom_rate=_HEADROOM_RATE,
        uppermax=_UPPERMAX,
        agi=agi,
        headroom_max=_HEADROOM_MAX,
        conversion=conversion,
    )
    assert tax == pytest.approx(expected_tax)


def test_roth_tax_conversion_exceeds_total_bracket_space_raises():
    """Conversion larger than both bracket spaces combined must raise ValueError."""
    # total_bracket_space = (206700-180000) + (394600-206700) = 26700 + 187900 = 214600
    # Conversion = $300,000 > $214,600 → ValueError
    with pytest.raises(ValueError, match="No third-rate bracket"):
        calc_roth_conversions_tax(
            maxrate=_MAXRATE,
            headroom_rate=_HEADROOM_RATE,
            uppermax=_UPPERMAX,
            agi=180_000.0,
            headroom_max=_HEADROOM_MAX,
            conversion=300_000.0,
        )


def test_roth_tax_inverted_headroom_max_is_safe():
    """headroom_max < uppermax (misconfigured brackets) must not produce negative tax.

    The new max(0.0, ...) guard on headroom_bracket_space ensures the function
    treats the headroom width as zero rather than negative, so the entire
    conversion is taxed at maxrate (current bracket only).
    """
    # headroom_max < uppermax → headroom_bracket_space clamped to 0
    # current_bracket_space = 206700 - 180000 = 26700
    # conversion = 10000 < 26700 → all at maxrate
    agi = 180_000.0
    conversion = 10_000.0
    expected_tax = conversion * _MAXRATE
    tax = calc_roth_conversions_tax(
        maxrate=_MAXRATE,
        headroom_rate=_HEADROOM_RATE,
        uppermax=_UPPERMAX,
        agi=agi,
        headroom_max=100_000.0,   # intentionally < uppermax
        conversion=conversion,
    )
    assert tax == pytest.approx(expected_tax)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
