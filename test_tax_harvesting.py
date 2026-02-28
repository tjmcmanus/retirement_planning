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

# Made with Bob
