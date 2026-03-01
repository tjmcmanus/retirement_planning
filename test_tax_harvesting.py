#!/usr/bin/env python3
"""
Unit tests for tax_harvesting.py

Covers:
  - get_ltcg_rate_for_income: 0%/15%/20% bracket boundaries
  - classify_harvest_opportunities: each recommendation category
  - compute_net_tax_impact: net gain vs net loss scenarios
"""

import pandas as pd
import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# Synthetic 2025 MFJ LTCG brackets (mirrors cap_gains.csv structure)
FAKE_BRACKETS = pd.DataFrame([
    {"lower":      0, "upper":  96700, "rate": 0.00},
    {"lower":  96700, "upper": 583750, "rate": 0.15},
    {"lower": 583750, "upper": 9999999, "rate": 0.20},
])


def _make_analysis_row(
    symbol: str = "AAPL",
    unrealized_gl: float = 0.0,
    gain_type: str = "Long-Term",
    days_held: int = 400,
    return_pct: float = 0.0,
    purchase_date: str = "2023-01-01",
) -> dict:
    """Build a minimal analysis DataFrame row for testing."""
    return {
        "Account": "Brokerage",
        "Symbol": symbol,
        "Name": symbol,
        "Sector": "Technology",
        "Qty": 10.0,
        "Purchase Price": 100.0,
        "Current Price": 100.0 + unrealized_gl / 10.0,
        "Current Value": 1000.0 + unrealized_gl,
        "Cost Basis": 1000.0,
        "Unrealized G/L": unrealized_gl,
        "Return %": return_pct,
        "Days Held": days_held,
        "Gain Type": gain_type,
        "Purchase Date": purchase_date,
        "Replacements": "SPY (Broad market exposure)",
    }


def _make_df(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# get_ltcg_rate_for_income — bracket boundary tests
# ---------------------------------------------------------------------------

class TestGetLtcgRateForIncome:
    """Tests for get_ltcg_rate_for_income bracket selection."""

    def _call(self, agi: float, brackets: pd.DataFrame = FAKE_BRACKETS) -> float:
        from tax_harvesting import get_ltcg_rate_for_income
        # Patch get_cap_gains_brackets AND clear the st.cache_data cache so each
        # call exercises the real branching logic with our synthetic brackets.
        with patch("tax_harvesting.get_cap_gains_brackets", return_value=brackets):
            get_ltcg_rate_for_income.clear()
            return get_ltcg_rate_for_income(agi, 2025)

    def test_zero_percent_bracket_low_income(self):
        """AGI well below 0% upper limit → 0% rate."""
        assert self._call(50_000) == 0.0

    def test_zero_percent_bracket_at_upper_boundary(self):
        """AGI exactly at 0% upper limit ($96,700) → 0% rate."""
        assert self._call(96_700) == 0.0

    def test_fifteen_percent_bracket_just_above_zero(self):
        """AGI just above 0% threshold → 15% rate."""
        assert self._call(96_701) == 0.15

    def test_fifteen_percent_bracket_mid_range(self):
        """AGI in the middle of the 15% bracket → 15% rate."""
        assert self._call(300_000) == 0.15

    def test_fifteen_percent_bracket_at_upper_boundary(self):
        """AGI exactly at 15% upper limit ($583,750) → 15% rate."""
        assert self._call(583_750) == 0.15

    def test_twenty_percent_bracket(self):
        """AGI above 15% upper limit → 20% rate."""
        assert self._call(600_000) == 0.20

    def test_empty_brackets_returns_fallback(self):
        """Empty brackets DataFrame → fallback rate of 15%."""
        assert self._call(50_000, brackets=pd.DataFrame()) == 0.15


# ---------------------------------------------------------------------------
# classify_harvest_opportunities — recommendation category tests
# ---------------------------------------------------------------------------

class TestClassifyHarvestOpportunities:
    """Tests for classify_harvest_opportunities recommendation logic."""

    def _classify(self, rows, agi: float = 50_000, year: int = 2025):
        from tax_harvesting import classify_harvest_opportunities
        df = _make_df(*rows)
        with patch("tax_harvesting.get_ltcg_rate_for_income") as mock_rate, \
             patch("tax_harvesting.get_ltcg_zero_threshold") as mock_thresh:
            mock_rate.return_value = 0.0 if agi <= 96_700 else 0.15
            mock_thresh.return_value = 96_700.0
            return classify_harvest_opportunities(df, agi, year)

    def test_harvest_loss_recommendation(self):
        """Large unrealized loss → 🔴 Harvest Loss."""
        row = _make_analysis_row(unrealized_gl=-2000.0, gain_type="Long-Term")
        result = self._classify([row])
        assert result["Recommendation"].iloc[0].startswith("🔴 Harvest Loss")

    def test_harvest_gain_at_zero_ltcg(self):
        """LT gain + 0% LTCG rate → 🟢 Harvest Gain (0% LTCG)."""
        row = _make_analysis_row(unrealized_gl=1500.0, gain_type="Long-Term")
        result = self._classify([row], agi=50_000)
        assert result["Recommendation"].iloc[0].startswith("🟢 Harvest Gain")

    def test_monitor_fifteen_percent_lt_gain(self):
        """LT gain + 15% LTCG rate → 🟡 Monitor (15% LTCG)."""
        row = _make_analysis_row(unrealized_gl=1500.0, gain_type="Long-Term")
        result = self._classify([row], agi=200_000)
        assert "15%" in result["Recommendation"].iloc[0]

    def test_monitor_short_term_gain(self):
        """ST gain above threshold → 🟡 Monitor (ST — Ordinary Rate)."""
        row = _make_analysis_row(unrealized_gl=1500.0, gain_type="Short-Term", days_held=100)
        result = self._classify([row], agi=50_000)
        assert "ST" in result["Recommendation"].iloc[0]

    def test_small_loss_monitor(self):
        """Small loss below threshold → ⚪ Small Loss — Monitor."""
        row = _make_analysis_row(unrealized_gl=-200.0, gain_type="Long-Term")
        result = self._classify([row])
        assert "Small Loss" in result["Recommendation"].iloc[0]

    def test_small_gain_hold(self):
        """Small gain below threshold → ⚪ Small Gain — Hold."""
        row = _make_analysis_row(unrealized_gl=200.0, gain_type="Long-Term")
        result = self._classify([row])
        assert "Small Gain" in result["Recommendation"].iloc[0]

    def test_empty_dataframe_returns_empty(self):
        """Empty input DataFrame → empty output DataFrame."""
        from tax_harvesting import classify_harvest_opportunities
        result = classify_harvest_opportunities(pd.DataFrame(), 50_000, 2025)
        assert result.empty

    def test_ltcg_rate_column_added(self):
        """Output DataFrame must contain 'LTCG Rate' column."""
        row = _make_analysis_row(unrealized_gl=0.0)
        result = self._classify([row])
        assert "LTCG Rate" in result.columns


# ---------------------------------------------------------------------------
# compute_net_tax_impact — net gain vs net loss scenarios
# ---------------------------------------------------------------------------

class TestComputeNetTaxImpact:
    """Tests for compute_net_tax_impact tax estimation logic."""

    def _make_classified(self, loss_gl: float = 0.0, gain_gl: float = 0.0) -> pd.DataFrame:
        """Build a minimal classified DataFrame with one loss and/or one gain row."""
        rows = []
        if loss_gl != 0.0:
            rows.append({
                **_make_analysis_row(unrealized_gl=loss_gl),
                "Recommendation": "🔴 Harvest Loss",
                "LTCG Rate": "0%",
                "0% Headroom": 46700.0,
                "Action Detail": "",
            })
        if gain_gl != 0.0:
            rows.append({
                **_make_analysis_row(unrealized_gl=gain_gl),
                "Recommendation": "🟢 Harvest Gain (0% LTCG)",
                "LTCG Rate": "0%",
                "0% Headroom": 46700.0,
                "Action Detail": "",
            })
        return pd.DataFrame(rows)

    def _call(self, df: pd.DataFrame, agi: float = 50_000, marginal: float = 0.22):
        from tax_harvesting import compute_net_tax_impact
        with patch("tax_harvesting.get_ltcg_rate_for_income", return_value=0.0 if agi <= 96_700 else 0.15):
            return compute_net_tax_impact(df, agi, 2025, marginal_ordinary_rate=marginal)

    def test_net_gain_scenario_tax_owed(self):
        """Net gain → tax_on_net_gains > 0, net_tax_impact negative (tax owed)."""
        df = self._make_classified(gain_gl=5000.0)
        result = self._call(df, agi=200_000)  # 15% bracket
        assert result.net_position > 0
        assert result.tax_on_net_gains > 0
        assert result.net_tax_impact < 0

    def test_net_gain_at_zero_rate_no_tax(self):
        """Net gain at 0% LTCG rate → no tax owed."""
        df = self._make_classified(gain_gl=5000.0)
        result = self._call(df, agi=50_000)  # 0% bracket
        assert result.tax_on_net_gains == 0.0
        assert result.net_tax_impact == 0.0

    def test_net_loss_scenario_ordinary_offset(self):
        """Net loss → ordinary income offset applied, tax savings positive."""
        df = self._make_classified(loss_gl=-4000.0)
        result = self._call(df, marginal=0.22)
        assert result.net_position < 0
        assert result.ordinary_income_offset == 3000.0  # capped at $3,000
        assert result.ordinary_income_savings == pytest.approx(3000.0 * 0.22)
        assert result.net_tax_impact > 0

    def test_loss_cap_at_3000(self):
        """Net loss > $3,000 → ordinary offset capped at $3,000."""
        df = self._make_classified(loss_gl=-10_000.0)
        result = self._call(df)
        assert result.ordinary_income_offset == 3000.0

    def test_small_net_loss_below_3000(self):
        """Net loss < $3,000 → full loss used as ordinary offset."""
        df = self._make_classified(loss_gl=-1500.0)
        result = self._call(df)
        assert result.ordinary_income_offset == 1500.0

    def test_gains_offset_losses_netting(self):
        """Gains and losses net against each other before tax calculation."""
        df = self._make_classified(loss_gl=-3000.0, gain_gl=1000.0)
        result = self._call(df)
        # net = 1000 - 3000 = -2000 (net loss)
        assert result.net_position == pytest.approx(-2000.0)
        assert result.ordinary_income_offset == 2000.0

    def test_empty_dataframe_returns_zero_filled_dict(self):
        """Empty classified DataFrame → zero-filled NetTaxImpact with all 9 fields."""
        import dataclasses
        from tax_harvesting import compute_net_tax_impact, NetTaxImpact
        with patch("tax_harvesting.get_ltcg_rate_for_income", return_value=0.15):
            result = compute_net_tax_impact(pd.DataFrame(), 50_000, 2025)
        assert isinstance(result, NetTaxImpact)
        assert {f.name for f in dataclasses.fields(result)} == {
            "total_harvestable_losses", "total_harvestable_gains", "net_position",
            "ltcg_rate", "tax_on_net_gains", "ordinary_income_offset",
            "ordinary_income_savings", "net_tax_impact", "marginal_ordinary_rate",
        }
        assert result.total_harvestable_losses == 0.0
        assert result.total_harvestable_gains == 0.0
        assert result.net_position == 0.0
        assert result.tax_on_net_gains == 0.0
        assert result.ordinary_income_offset == 0.0
        assert result.ordinary_income_savings == 0.0
        assert result.net_tax_impact == 0.0

# ---------------------------------------------------------------------------
# calc_daf_value — contribution type, maxdaf modes, AGI limit enforcement
# ---------------------------------------------------------------------------

class TestCalcDafValue:
    """Tests for calc_daf_value in calculations.py."""

    def _call(self, gross: float, interest: float, daf1: float, maxdaf: str,
              contribution_type: str = "cash",
              std_deduction: float = 0.0) -> float:
        import pandas as pd
        from calculations import calc_daf_value
        stddectdf = pd.DataFrame([{"deduction": std_deduction}]) if std_deduction > 0 else pd.DataFrame()
        return calc_daf_value(gross, interest, daf1, maxdaf, contribution_type, stddectdf)  # type: ignore[arg-type]

    # maxdaf = "N" — always zero regardless of type
    def test_maxdaf_n_returns_zero(self):
        """maxdaf='N' → 0 regardless of income or contribution type."""
        assert self._call(200_000, 10_000, 5_000, "N") == 0.0

    def test_maxdaf_n_securities_returns_zero(self):
        """maxdaf='N' with securities type → 0."""
        assert self._call(200_000, 10_000, 5_000, "N", "securities") == 0.0

    # maxdaf = "Y" — returns AGI-based ceiling
    def test_maxdaf_y_cash_returns_60pct(self):
        """maxdaf='Y', cash → 60% of total income."""
        result = self._call(100_000, 0, 0, "Y", "cash")
        assert result == pytest.approx(60_000.0)

    def test_maxdaf_y_securities_returns_30pct(self):
        """maxdaf='Y', securities → 30% of total income."""
        result = self._call(100_000, 0, 0, "Y", "securities")
        assert result == pytest.approx(30_000.0)

    def test_maxdaf_y_includes_interest(self):
        """maxdaf='Y' — interest is included in the income base."""
        result = self._call(80_000, 20_000, 0, "Y", "cash")
        assert result == pytest.approx(60_000.0)  # 60% of 100_000

    # Custom amount (daf1) — within and exceeding limit
    def test_custom_amount_within_cash_limit(self):
        """Custom daf1 within 60% cash limit → returns daf1."""
        result = self._call(100_000, 0, 40_000, "custom", "cash")
        assert result == pytest.approx(40_000.0)

    def test_custom_amount_within_securities_limit(self):
        """Custom daf1 within 30% securities limit → returns daf1."""
        result = self._call(100_000, 0, 20_000, "custom", "securities")
        assert result == pytest.approx(20_000.0)

    def test_custom_amount_exceeds_cash_limit_returns_zero(self):
        """Custom daf1 exceeding 60% cash limit → returns 0 (not capped)."""
        result = self._call(100_000, 0, 70_000, "custom", "cash")
        assert result == 0.0

    def test_custom_amount_exceeds_securities_limit_returns_zero(self):
        """Custom daf1 exceeding 30% securities limit → returns 0."""
        result = self._call(100_000, 0, 35_000, "custom", "securities")
        assert result == 0.0

    def test_invalid_contribution_type_raises(self):
        """Unknown contribution_type → ValueError."""
        from calculations import calc_daf_value
        with pytest.raises(ValueError, match="Unsupported contribution_type"):
            calc_daf_value(100_000, 0, 5_000, "Y", "crypto", None)  # type: ignore[arg-type]

    def test_agi_limit_uses_std_deduction(self):
        """AGI limit is based on gross - std_deduction, not gross income (IRC §170)."""
        # gross=200_000, interest=0, std_deduction=30_000 → AGI=170_000
        # 60% cash limit = 102_000, NOT 120_000
        result = self._call(200_000, 0, 0, "Y", "cash", std_deduction=30_000)
        assert result == pytest.approx(102_000.0)

    def test_agi_limit_no_std_deduction_uses_gross(self):
        """When no stddectdf is provided (empty), gross income is used as fallback."""
        result = self._call(100_000, 0, 0, "Y", "cash", std_deduction=0.0)
        assert result == pytest.approx(60_000.0)


# ---------------------------------------------------------------------------
# identify_daf_candidates — long-term vs short-term, gain threshold
# ---------------------------------------------------------------------------

class TestIdentifyDafCandidates:
    """Tests for identify_daf_candidates in tax_harvesting.py."""

    def _make_holding(self, symbol: str, unrealized_gl: float,
                      days_held: int, gain_type: str) -> dict:
        return {
            "Account": "Brokerage",
            "Symbol": symbol,
            "Name": symbol,
            "Qty": 10.0,
            "Cost Basis": 1_000.0,
            "Current Value": 1_000.0 + unrealized_gl,
            "Unrealized G/L": unrealized_gl,
            "Days Held": days_held,
            "Gain Type": gain_type,
        }

    def _call(self, rows, min_gain: float = 500.0, min_days: int = 366):
        from tax_harvesting import identify_daf_candidates
        df = pd.DataFrame(rows)
        return identify_daf_candidates(df, min_gain=min_gain, min_days=min_days)

    def test_long_term_large_gain_is_candidate(self):
        """Long-term holding with gain ≥ min_gain → included."""
        row = self._make_holding("AAPL", 2_000.0, 400, "Long-Term")
        result = self._call([row])
        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    def test_short_term_holding_excluded(self):
        """Short-term holding (< 366 days) → excluded even with large gain."""
        row = self._make_holding("TSLA", 5_000.0, 200, "Short-Term")
        result = self._call([row])
        assert result == []

    def test_long_term_small_gain_excluded(self):
        """Long-term holding with gain < min_gain → excluded."""
        row = self._make_holding("MSFT", 100.0, 400, "Long-Term")
        result = self._call([row])
        assert result == []

    def test_sorted_by_gain_descending(self):
        """Multiple candidates → sorted by unrealized_gain descending."""
        rows = [
            self._make_holding("LOW", 600.0, 400, "Long-Term"),
            self._make_holding("HIGH", 3_000.0, 400, "Long-Term"),
            self._make_holding("MID", 1_500.0, 400, "Long-Term"),
        ]
        result = self._call(rows)
        gains = [c.unrealized_gain for c in result]
        assert gains == sorted(gains, reverse=True)

    def test_empty_dataframe_returns_empty_list(self):
        """Empty input → empty list."""
        from tax_harvesting import identify_daf_candidates
        result = identify_daf_candidates(pd.DataFrame())
        assert result == []

    def test_avoided_cg_tax_computed_at_15pct(self):
        """avoided_cg_tax = unrealized_gain × 0.15 (conservative estimate)."""
        row = self._make_holding("VTI", 2_000.0, 400, "Long-Term")
        result = self._call([row])
        assert result[0].avoided_cg_tax == pytest.approx(2_000.0 * 0.15)

    def test_missing_columns_returns_empty_list(self):
        """DataFrame missing required columns → empty list (graceful)."""
        from tax_harvesting import identify_daf_candidates
        df = pd.DataFrame([{"Symbol": "X", "Qty": 5}])
        result = identify_daf_candidates(df)
        assert result == []


# ---------------------------------------------------------------------------
# analyze_daf_bundling — below/above std deduction, securities, carryforward
# ---------------------------------------------------------------------------

class TestAnalyzeDafBundling:
    """Tests for analyze_daf_bundling in tax_harvesting.py."""

    def _make_candidate(self, symbol: str = "VTI", value: float = 10_000.0,
                        gain: float = 5_000.0, avoided: float = 750.0):
        from tax_harvesting import DAFDonationCandidate
        return DAFDonationCandidate(
            account="Brokerage", symbol=symbol, name=symbol,
            qty=10.0, cost_basis=value - gain, current_value=value,
            unrealized_gain=gain, gain_pct=gain / (value - gain) * 100,
            days_held=400, gain_type="Long-Term", avoided_cg_tax=avoided,
        )

    def _call(self, agi: float = 200_000, annual_giving: float = 10_000,
              years_to_bundle: int = 3, marginal_rate: float = 0.22,
              standard_deduction: float = 29_200, ltcg_rate: float = 0.15,
              securities_candidates=None):
        from tax_harvesting import analyze_daf_bundling
        if securities_candidates is None:
            securities_candidates = []
        return analyze_daf_bundling(
            estimated_agi=agi,
            annual_giving=annual_giving,
            years_to_bundle=years_to_bundle,
            marginal_rate=marginal_rate,
            standard_deduction=standard_deduction,
            ltcg_rate=ltcg_rate,
            securities_candidates=securities_candidates,
        )

    def test_bundled_target_below_std_deduction_not_beneficial(self):
        """Bundled target ≤ standard deduction → ⚪ not beneficial recommendation."""
        # annual_giving=5_000, years=3 → bundled=15_000 < std_ded=29_200
        result = self._call(annual_giving=5_000, years_to_bundle=3)
        assert result.recommendation.startswith("⚪")

    def test_bundled_target_above_std_deduction_recommended(self):
        """Bundled target well above standard deduction → 🟢 recommended."""
        # annual_giving=15_000, years=3 → bundled=45_000 > std_ded=29_200
        result = self._call(annual_giving=15_000, years_to_bundle=3)
        assert result.recommendation.startswith("🟢")

    def test_no_securities_candidates_cash_only_note(self):
        """No securities candidates → note mentions cash contribution."""
        result = self._call(annual_giving=15_000, years_to_bundle=3)
        assert any("cash" in n.lower() for n in result.notes)

    def test_with_securities_candidates_reduces_cash_needed(self):
        """Securities candidates are used first; cash tops up the remainder."""
        cand = self._make_candidate(value=20_000, gain=10_000, avoided=1_500)
        result = self._call(annual_giving=15_000, years_to_bundle=3,
                            securities_candidates=[cand])
        # Securities should appear in used candidates
        assert len(result.securities_candidates) >= 1
        assert result.total_securities_value > 0

    def test_carryforward_when_contribution_exceeds_agi_limit(self):
        """Contribution exceeding 60% AGI cap → carryforward_amount > 0."""
        # AGI=50_000 → 60% limit = 30_000; bundled = 15_000*3 = 45_000 > 30_000
        result = self._call(agi=50_000, annual_giving=15_000, years_to_bundle=3,
                            standard_deduction=29_200)
        assert result.carryforward_amount > 0

    def test_no_carryforward_within_agi_limit(self):
        """Contribution within 60% AGI cap → carryforward_amount == 0."""
        # AGI=200_000 → 60% limit = 120_000; bundled = 10_000*3 = 30_000
        result = self._call(agi=200_000, annual_giving=10_000, years_to_bundle=3)
        assert result.carryforward_amount == 0.0

    def test_years_to_bundle_clamped_to_5(self):
        """years_to_bundle > 5 → clamped to 5."""
        result = self._call(years_to_bundle=10)
        assert result.years_to_bundle == 5

    def test_years_to_bundle_clamped_to_1(self):
        """years_to_bundle < 1 → clamped to 1."""
        result = self._call(years_to_bundle=0)
        assert result.years_to_bundle == 1

    def test_tax_savings_vs_standard_positive_when_beneficial(self):
        """tax_savings_vs_standard > 0 when bundled exceeds standard deduction."""
        result = self._call(annual_giving=15_000, years_to_bundle=3)
        assert result.tax_savings_vs_standard > 0

    def test_partial_securities_donation_fills_room(self):
        """Candidate larger than remaining room → partial donation used."""
        # bundled_target = 10_000*2 = 20_000; securities_limit = 200_000*0.30 = 60_000
        # candidate value = 50_000 > bundled_target → partial donation of 20_000 used.
        # standard_deduction set below bundled_target so the early-return path is not taken.
        cand = self._make_candidate(value=50_000, gain=25_000, avoided=3_750)
        result = self._call(annual_giving=10_000, years_to_bundle=2,
                            standard_deduction=10_000,
                            securities_candidates=[cand])
        assert result.total_securities_value == pytest.approx(20_000.0)


# ---------------------------------------------------------------------------
# _calculate_daf_for_year — bundle years, non-bundle years, age boundaries
# ---------------------------------------------------------------------------

class TestCalculateDafForYear:
    """Tests for _calculate_daf_for_year in strategy.py."""

    def _call(self, age_primary: int, year: int = 2030,
              std_deduction: float = 29_200,
              has_daf: bool = True, annual_giving: float = 10_000,
              giving_start_age: int = 65, giving_end_age: int = 95,
              daf_start_age: int = 60, daf_end_age: int = 75,
              daf_initial: float = 0):
        from strategy import _calculate_daf_for_year
        config_data = {
            "charitable_giving": {
                "has_daf": has_daf,
                "annual_charitable_giving": annual_giving,
                "charitable_giving_start_age": giving_start_age,
                "charitable_giving_end_age": giving_end_age,
                "daf_contribution_start_age": daf_start_age,
                "daf_contribution_end_age": daf_end_age,
                "daf_initial_contribution": daf_initial,
            }
        }
        with patch("strategy.get_config_manager") as mock_cfg:
            mock_cfg.return_value.get.side_effect = (
                lambda section, key, default=None:
                config_data.get(section, {}).get(key, default)
            )
            return _calculate_daf_for_year(age_primary, year, std_deduction)

    def test_bundle_year_returns_nonzero_contribution(self):
        """First year of DAF window (age == daf_start_age) → bundle year."""
        contribution, excess = self._call(age_primary=60)
        assert contribution > 0

    def test_non_bundle_year_returns_zero(self):
        """Non-bundle year → (0.0, 0.0)."""
        # bundle_interval = floor(29200/10000)+1 = 3; age=61 → years_into=1 → not bundle
        contribution, excess = self._call(age_primary=61)
        assert contribution == 0.0
        assert excess == 0.0

    def test_age_before_daf_start_returns_zero(self):
        """Age below daf_start_age → (0.0, 0.0)."""
        contribution, excess = self._call(age_primary=55, daf_start_age=60)
        assert contribution == 0.0
        assert excess == 0.0

    def test_age_after_daf_end_returns_zero(self):
        """Age above daf_end_age → (0.0, 0.0)."""
        contribution, excess = self._call(age_primary=80, daf_end_age=75)
        assert contribution == 0.0
        assert excess == 0.0

    def test_has_daf_false_returns_zero(self):
        """has_daf=False → (0.0, 0.0)."""
        contribution, excess = self._call(age_primary=60, has_daf=False)
        assert contribution == 0.0
        assert excess == 0.0

    def test_zero_annual_giving_returns_zero(self):
        """annual_giving=0 → (0.0, 0.0)."""
        contribution, excess = self._call(age_primary=60, annual_giving=0)
        assert contribution == 0.0
        assert excess == 0.0

    def test_initial_contribution_added_in_first_bundle_year(self):
        """daf_initial > 0 → added to bundle amount in first year only."""
        contrib_first, _ = self._call(age_primary=60, daf_initial=5_000)
        contrib_later, _ = self._call(age_primary=63, daf_initial=5_000)
        # First year includes initial; later bundle year does not
        assert contrib_first > contrib_later

    def test_tax_excess_is_contribution_minus_std_deduction(self):
        """daf_tax_excess = max(0, contribution - std_deduction)."""
        contribution, excess = self._call(age_primary=60, std_deduction=29_200)
        expected_excess = max(0.0, contribution - 29_200)
        assert excess == pytest.approx(expected_excess)

    def test_bundle_interval_clamped_to_5(self):
        """Very small annual_giving → bundle_interval clamped to 5."""
        # std_ded=29200, annual_giving=100 → floor(292)+1=293 → clamped to 5
        contribution, _ = self._call(age_primary=60, annual_giving=100,
                                     std_deduction=29_200)
        # bundle_amount = 100 * 5 = 500
        assert contribution == pytest.approx(500.0)

    def test_bundle_interval_minimum_2(self):
        """Large annual_giving → bundle_interval minimum is 2."""
        # std_ded=29200, annual_giving=50000 → floor(0)+1=1 → clamped to 2
        contribution, _ = self._call(age_primary=60, annual_giving=50_000,
                                     std_deduction=29_200)
        # bundle_amount = 50_000 * 2 = 100_000
        assert contribution == pytest.approx(100_000.0)

# Made with Bob
