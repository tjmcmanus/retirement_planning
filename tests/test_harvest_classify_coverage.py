"""
tests/test_harvest_classify_coverage.py
=========================================
Coverage-targeted tests for tax_harvesting.py.

Covers:
  - classify_harvest_opportunities: all six recommendation branches
  - compute_harvest_summary: full DataFrame, empty DataFrame
  - check_market_drop_trigger: triggered / not triggered / empty
  - get_ltcg_zero_threshold: normal and empty-bracket paths
  - _validate_classify_inputs: error paths
  - _classify_row / _classify_gain_row: each decision branch
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

FAKE_BRACKETS_MFJ = pd.DataFrame([
    {"lower":      0, "upper":  96_700, "rate": 0.00, "filing_status": "married_filing_jointly"},
    {"lower": 96_700, "upper": 583_750, "rate": 0.15, "filing_status": "married_filing_jointly"},
    {"lower": 583_750, "upper": 9_999_999, "rate": 0.20, "filing_status": "married_filing_jointly"},
])


def _row(
    symbol: str = "AAPL",
    gl: float = 0.0,
    gain_type: str = "Long-Term",
    days_held: int = 400,
    return_pct: float = 0.0,
) -> dict:
    return {
        "Account": "Schwab",
        "Symbol": symbol,
        "Name": symbol,
        "Sector": "Technology",
        "Qty": 10.0,
        "Purchase Price": 100.0,
        "Current Price": 100.0 + gl / 10.0,
        "Current Value": 1000.0 + gl,
        "Cost Basis": 1000.0,
        "Unrealized G/L": gl,
        "Return %": return_pct,
        "Days Held": days_held,
        "Gain Type": gain_type,
        "Purchase Date": "2022-01-01",
        "Replacements": "SPY",
    }


def _df(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _classify(df: pd.DataFrame, agi: float = 50_000, year: int = 2026) -> pd.DataFrame:
    from tax_harvesting import classify_harvest_opportunities
    with patch("tax_harvesting.get_cap_gains_brackets", return_value=FAKE_BRACKETS_MFJ):
        with patch("tax_harvesting.get_ltcg_rate_for_income",
                   wraps=lambda a, y: 0.0 if a < 96_700 else (0.15 if a < 583_750 else 0.20)):
            with patch("tax_harvesting.get_ltcg_zero_threshold", return_value=96_700.0):
                return classify_harvest_opportunities(df, agi, year)


# ---------------------------------------------------------------------------
# classify_harvest_opportunities — all six recommendation paths
# ---------------------------------------------------------------------------

class TestClassifyHarvestOpportunities:

    def test_empty_df_returns_empty(self):
        from tax_harvesting import classify_harvest_opportunities
        result = classify_harvest_opportunities(pd.DataFrame(), 50_000, 2026)
        assert result.empty

    def test_harvest_loss_branch(self):
        df = _df(_row("AAPL", gl=-2_000, gain_type="Long-Term"))
        result = _classify(df, agi=50_000)
        rec = result["Recommendation"].iloc[0]
        assert "Harvest Loss" in rec

    def test_harvest_gain_zero_pct_branch(self):
        # AGI < 96,700 → 0% LTCG rate; LT gain > threshold → harvest gain
        df = _df(_row("MSFT", gl=1_500, gain_type="Long-Term", days_held=400))
        result = _classify(df, agi=50_000)
        rec = result["Recommendation"].iloc[0]
        assert "Harvest Gain" in rec or "0%" in rec

    def test_monitor_15pct_branch(self):
        # AGI = 200,000 → 15% LTCG; LT gain > threshold
        df = _df(_row("GOOG", gl=1_500, gain_type="Long-Term", days_held=400))
        with patch("tax_harvesting.get_cap_gains_brackets", return_value=FAKE_BRACKETS_MFJ):
            with patch("tax_harvesting.get_ltcg_rate_for_income", return_value=0.15):
                with patch("tax_harvesting.get_ltcg_zero_threshold", return_value=96_700.0):
                    from tax_harvesting import classify_harvest_opportunities
                    result = classify_harvest_opportunities(df, 200_000, 2026)
        rec = result["Recommendation"].iloc[0]
        assert "Monitor" in rec or "15%" in rec

    def test_hold_20pct_branch(self):
        # AGI = 600,000 → 20% LTCG; LT gain > threshold
        df = _df(_row("NVDA", gl=1_500, gain_type="Long-Term", days_held=400))
        with patch("tax_harvesting.get_cap_gains_brackets", return_value=FAKE_BRACKETS_MFJ):
            with patch("tax_harvesting.get_ltcg_rate_for_income", return_value=0.20):
                with patch("tax_harvesting.get_ltcg_zero_threshold", return_value=96_700.0):
                    from tax_harvesting import classify_harvest_opportunities
                    result = classify_harvest_opportunities(df, 600_000, 2026)
        rec = result["Recommendation"].iloc[0]
        assert "20%" in rec or "Hold" in rec

    def test_short_term_gain_branch(self):
        # Short-Term gain > threshold
        df = _df(_row("TSLA", gl=1_500, gain_type="Short-Term", days_held=100))
        result = _classify(df, agi=50_000)
        rec = result["Recommendation"].iloc[0]
        assert "ST" in rec or "Monitor" in rec or "Short" in rec

    def test_small_loss_branch(self):
        # Loss below default threshold of -500 (e.g., -200)
        df = _df(_row("IBM", gl=-200, gain_type="Long-Term", days_held=400))
        result = _classify(df, agi=50_000)
        rec = result["Recommendation"].iloc[0]
        assert "Small" in rec or "Monitor" in rec

    def test_small_gain_hold_branch(self):
        # Gain below threshold (e.g., +200)
        df = _df(_row("KO", gl=200, gain_type="Long-Term", days_held=400))
        result = _classify(df, agi=50_000)
        rec = result["Recommendation"].iloc[0]
        assert "Hold" in rec or "Small" in rec

    def test_result_has_required_columns(self):
        df = _df(_row("AAPL", gl=-1_000))
        result = _classify(df)
        assert "Recommendation" in result.columns
        assert "Action Detail" in result.columns
        assert "LTCG Rate" in result.columns
        assert "0% Headroom" in result.columns

    def test_multiple_rows(self):
        df = _df(
            _row("AAPL", gl=-2_000),
            _row("MSFT", gl=1_500),
            _row("KO", gl=200),
        )
        result = _classify(df, agi=50_000)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# compute_harvest_summary
# ---------------------------------------------------------------------------

class TestComputeHarvestSummary:

    def _summarise(self, agi=50_000):
        from tax_harvesting import compute_harvest_summary
        df = _df(
            _row("AAPL", gl=-2_000),
            _row("MSFT", gl=1_500),
            _row("KO", gl=200),
        )
        classified = _classify(df, agi=agi)
        return compute_harvest_summary(classified)

    def test_empty_df_returns_zero_dict(self):
        from tax_harvesting import compute_harvest_summary
        result = compute_harvest_summary(pd.DataFrame())
        assert result["total_unrealized_gain"] == 0.0
        assert result["total_unrealized_loss"] == 0.0
        assert result["num_loss_candidates"] == 0

    def test_loss_counted(self):
        summary = self._summarise()
        assert summary["total_unrealized_loss"] < 0

    def test_gain_counted(self):
        summary = self._summarise()
        assert summary["total_unrealized_gain"] > 0

    def test_net_unrealized_is_sum(self):
        summary = self._summarise()
        assert summary["net_unrealized"] == pytest.approx(
            summary["total_unrealized_gain"] + summary["total_unrealized_loss"]
        )

    def test_missing_recommendation_raises(self):
        from tax_harvesting import compute_harvest_summary
        df = _df(_row("AAPL", gl=-1_000))
        with pytest.raises(ValueError, match="classify_harvest_opportunities"):
            compute_harvest_summary(df)

    def test_ltcg_rate_key_present(self):
        summary = self._summarise()
        assert "ltcg_rate" in summary
        assert "zero_headroom" in summary


# ---------------------------------------------------------------------------
# check_market_drop_trigger
# ---------------------------------------------------------------------------

class TestCheckMarketDropTrigger:

    def _analysis_df(self, return_pcts: list[float]) -> pd.DataFrame:
        rows = [_row(f"SYM{i}", return_pct=r) for i, r in enumerate(return_pcts)]
        df = pd.DataFrame(rows)
        # check_market_drop_trigger uses "Return %" and "Unrealized G/L" columns
        df["Unrealized G/L"] = [r * 10 for r in return_pcts]
        return df

    def test_empty_df_not_triggered(self):
        from tax_harvesting import check_market_drop_trigger
        result = check_market_drop_trigger(pd.DataFrame())
        assert result["triggered"] is False

    def test_no_positions_below_threshold_not_triggered(self):
        from tax_harvesting import check_market_drop_trigger
        df = self._analysis_df([-5.0, 2.0, 8.0])   # none below -10%
        result = check_market_drop_trigger(df, drop_threshold_pct=10.0)
        assert result["triggered"] is False

    def test_position_below_threshold_triggered(self):
        from tax_harvesting import check_market_drop_trigger
        df = self._analysis_df([-15.0, 2.0])        # -15% is below -10%
        result = check_market_drop_trigger(df, drop_threshold_pct=10.0)
        assert result["triggered"] is True
        assert len(result["candidates"]) >= 1

    def test_result_has_message(self):
        from tax_harvesting import check_market_drop_trigger
        df = self._analysis_df([2.0, 5.0])
        result = check_market_drop_trigger(df)
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0


# ---------------------------------------------------------------------------
# get_ltcg_zero_threshold — edge paths
# ---------------------------------------------------------------------------

class TestGetLtcgZeroThreshold:

    def test_normal_brackets_returns_upper(self):
        from tax_harvesting import get_ltcg_zero_threshold
        with patch("tax_harvesting.get_cap_gains_brackets", return_value=FAKE_BRACKETS_MFJ):
            get_ltcg_zero_threshold.clear()
            threshold = get_ltcg_zero_threshold(2026)
        assert threshold == pytest.approx(96_700.0)

    def test_empty_brackets_returns_fallback(self):
        from tax_harvesting import get_ltcg_zero_threshold
        with patch("tax_harvesting.get_cap_gains_brackets", return_value=pd.DataFrame()):
            get_ltcg_zero_threshold.clear()
            threshold = get_ltcg_zero_threshold(2026)
        assert threshold == pytest.approx(96_700.0)   # hardcoded fallback


# ---------------------------------------------------------------------------
# _validate_classify_inputs — error paths
# ---------------------------------------------------------------------------

class TestValidateClassifyInputs:

    def test_negative_days_held_raises(self):
        from tax_harvesting import _validate_classify_inputs
        with pytest.raises(ValueError, match="days_held"):
            _validate_classify_inputs(-1, "Long-Term", 0.0)

    def test_invalid_gain_type_raises(self):
        from tax_harvesting import _validate_classify_inputs
        with pytest.raises(ValueError, match="gain_type"):
            _validate_classify_inputs(100, "Medium-Term", 0.0)

    def test_invalid_ltcg_rate_raises(self):
        from tax_harvesting import _validate_classify_inputs
        with pytest.raises(ValueError, match="ltcg_rate"):
            _validate_classify_inputs(100, "Long-Term", 0.05)

    def test_valid_inputs_no_raise(self):
        from tax_harvesting import _validate_classify_inputs
        _validate_classify_inputs(365, "Long-Term", 0.15)   # must not raise
        _validate_classify_inputs(100, "Short-Term", 0.0)


# ---------------------------------------------------------------------------
# _classify_row — each branch
# ---------------------------------------------------------------------------

class TestClassifyRow:

    def _call(self, gl, gain_type="Long-Term", days_held=400,
              ltcg_rate=0.0, headroom=50_000.0,
              loss_threshold=-500.0, gain_threshold=500.0):
        from tax_harvesting import _classify_row
        return _classify_row(gl, gain_type, days_held, ltcg_rate,
                              headroom, loss_threshold, gain_threshold)

    def test_harvest_loss(self):
        d = self._call(-1_000)
        assert "Harvest Loss" in d.recommendation

    def test_harvest_gain_0pct(self):
        d = self._call(1_000, ltcg_rate=0.0)
        assert "Harvest Gain" in d.recommendation

    def test_monitor_15pct(self):
        d = self._call(1_000, ltcg_rate=0.15)
        assert "Monitor" in d.recommendation or "15%" in d.recommendation

    def test_hold_20pct(self):
        d = self._call(1_000, ltcg_rate=0.20)
        assert "20%" in d.recommendation or "Hold" in d.recommendation

    def test_short_term_gain(self):
        d = self._call(1_000, gain_type="Short-Term", days_held=100, ltcg_rate=0.0)
        assert "ST" in d.recommendation or "Short" in d.recommendation or "Monitor" in d.recommendation

    def test_small_loss_monitor(self):
        d = self._call(-200)   # between 0 and -500 threshold
        assert "Small" in d.recommendation or "Monitor" in d.recommendation

    def test_small_gain_hold(self):
        d = self._call(200)    # below 500 gain threshold
        assert "Hold" in d.recommendation or "Small" in d.recommendation
