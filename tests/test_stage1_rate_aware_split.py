"""Tests for the Stage 1 rate-aware Roth vs Traditional contribution splitter."""

import pytest

from strategy_core.stages import Stage1Accumulation
from strategy_core.models import PortfolioBalances


class FakeTaxCalculator:
    """Returns a fixed marginal rate so tests don't depend on bracket data."""

    def __init__(self, marginal_rate):
        self.marginal_rate = marginal_rate

    def calculate_standard_deduction(self, *args, **kwargs):
        return 30000.0

    def calculate_federal_tax(self, taxable_income, filing_status, year):
        return taxable_income * 0.1, self.marginal_rate, 1e9

    def calculate_state_tax(self, *args, **kwargs):
        return 0.0


@pytest.fixture
def balances():
    return PortfolioBalances(cash=100000.0, taxable=0.0, traditional=0.0, roth=0.0, daf=0.0)


def make_stage(mocker, marginal_rate, **income):
    settings = {
        "contribution_401k_percent": 10.0,
        "contribution_roth_percent": 5.0,
        "contribution_brokerage_percent": 5.0,
        "contribution_auto_split": True,
        "expected_retirement_tax_rate": 22.0,
        "employer_match_percent": 0.0,
    }
    settings.update(income)
    config = mocker.MagicMock()
    config.get.side_effect = lambda section, key, default=None: (
        settings.get(key, default) if section == "income" else default
    )
    mocker.patch("config.get_config_manager", return_value=config)
    return Stage1Accumulation(FakeTaxCalculator(marginal_rate), mocker.MagicMock())


def run(stage, balances):
    return stage.calculate_strategy(
        year=2024, balances=balances, expenses=50000.0,
        age_primary=40, age_spouse=40, wages=200000.0,
        filing_status="married_filing_jointly", max_conversion_rate=0.0,
    )


def test_high_bracket_goes_traditional(mocker, balances):
    result = run(make_stage(mocker, 0.32), balances)
    assert result.wages_to_trad == pytest.approx(30000.0)
    assert result.wages_to_roth == 0.0


def test_low_bracket_goes_roth(mocker, balances):
    result = run(make_stage(mocker, 0.12), balances)
    assert result.wages_to_trad == 0.0
    assert result.wages_to_roth == pytest.approx(30000.0)


def test_equal_rates_keep_configured_split(mocker, balances):
    result = run(make_stage(mocker, 0.22), balances)
    assert result.wages_to_trad == pytest.approx(20000.0)
    assert result.wages_to_roth == pytest.approx(10000.0)


def test_disabled_keeps_configured_split(mocker, balances):
    result = run(make_stage(mocker, 0.32, contribution_auto_split=False), balances)
    assert result.wages_to_trad == pytest.approx(20000.0)
    assert result.wages_to_roth == pytest.approx(10000.0)


def test_employer_match_goes_pre_tax_to_traditional(mocker, balances):
    # Roth deferral (12% bracket) with a 4% match: match still lands in Traditional.
    result = run(make_stage(mocker, 0.12, employer_match_percent=4.0), balances)
    assert result.wages_to_roth == pytest.approx(30000.0)
    assert result.traditional_balance == pytest.approx(8000.0)


def test_employer_match_capped_by_deferral(mocker, balances):
    # 15% deferral, 20% match limit -> match is only on the 15% actually deferred.
    result = run(make_stage(mocker, 0.32, employer_match_percent=20.0), balances)
    assert result.traditional_balance == pytest.approx(30000.0 + 30000.0)


# ---------------------------------------------------------------- Stage 2

from strategy_core.stages import Stage2PrepForRetirement  # noqa: E402


def make_stage2(mocker, marginal_rate, **income):
    settings = {
        "contribution_401k_percent": 15.0,
        "contribution_roth_percent": 0.0,
        "contribution_auto_split": True,
        "expected_retirement_tax_rate": 22.0,
        "employer_match_percent": 0.0,
    }
    settings.update(income)
    config = mocker.MagicMock()
    config.get.side_effect = lambda section, key, default=None: (
        settings.get(key, default) if section == "income"
        else False if key == "has_daf" else default
    )
    mocker.patch("config.get_config_manager", return_value=config)
    return Stage2PrepForRetirement(FakeTaxCalculator(marginal_rate), mocker.MagicMock())


def run2(stage, balances):
    return stage.calculate_strategy(
        year=2024, balances=balances, expenses=50000.0,
        age_primary=55, age_spouse=55, wages=200000.0,
        filing_status="married_filing_jointly", max_conversion_rate=0.24,
    )


def test_stage2_high_bracket_goes_traditional(mocker, balances):
    result = run2(make_stage2(mocker, 0.32), balances)
    assert result.wages_to_trad == pytest.approx(30000.0)
    assert result.wages_to_roth == 0.0


def test_stage2_low_bracket_goes_roth(mocker, balances):
    result = run2(make_stage2(mocker, 0.12), balances)
    assert result.wages_to_roth == pytest.approx(30000.0)
    assert result.wages_to_trad == 0.0


def test_stage2_employer_match_goes_to_traditional_even_when_roth(mocker, balances):
    result = run2(make_stage2(mocker, 0.12, employer_match_percent=4.0), balances)
    assert result.wages_to_roth == pytest.approx(30000.0)
    assert result.traditional_balance == pytest.approx(8000.0)


def test_stage2_rule_applies_even_when_auto_split_off(mocker, balances):
    result = run2(make_stage2(mocker, 0.32, contribution_auto_split=False), balances)
    assert result.wages_to_trad == pytest.approx(30000.0)
    result = run2(make_stage2(mocker, 0.12, contribution_auto_split=False), balances)
    assert result.wages_to_roth == pytest.approx(30000.0)
