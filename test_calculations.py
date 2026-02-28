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
from calculations import calculate_taxable_income


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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
