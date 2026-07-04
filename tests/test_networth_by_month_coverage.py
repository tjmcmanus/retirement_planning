"""
tests/test_networth_by_month_coverage.py
=========================================
Coverage-targeted tests for load_data.get_networth_by_month().

Uses pytest-mock to patch the DB call (get_portfolio_truth_by_month) and the
price-fetch (_fetch_current_prices) so no SQLite or network I/O occurs.
"""
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _portfolio_rows(month: int = 1, year: int = 2026) -> pd.DataFrame:
    """Minimal portfolio DataFrame matching the required columns."""
    return pd.DataFrame([
        {
            "month": month, "year": year,
            "account_name": "Schwab", "account_type": "Brokerage",
            "symbol": "AAPL", "qty": 10.0, "purchase_price": 150.0,
        },
        {
            "month": month, "year": year,
            "account_name": "Fidelity", "account_type": "Traditional",
            "symbol": "VFIAX", "qty": 5.0, "purchase_price": 400.0,
        },
        {
            "month": month, "year": year,
            "account_name": "Chase", "account_type": "Savings",
            "symbol": "CASH", "qty": 50_000.0, "purchase_price": 1.0,
        },
    ])


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestGetNetworthByMonthValidation:
    def test_invalid_month_raises(self):
        from load_data import get_networth_by_month
        with pytest.raises(ValueError, match="Month"):
            get_networth_by_month(13, 2026)

    def test_month_zero_raises(self):
        from load_data import get_networth_by_month
        with pytest.raises(ValueError, match="Month"):
            get_networth_by_month(0, 2026)

    def test_invalid_year_raises(self):
        from load_data import get_networth_by_month
        with pytest.raises(ValueError, match="Year"):
            get_networth_by_month(1, 1800)

    def test_year_too_high_raises(self):
        from load_data import get_networth_by_month
        with pytest.raises(ValueError, match="Year"):
            get_networth_by_month(1, 2200)

    def test_non_int_month_raises(self):
        from load_data import get_networth_by_month
        with pytest.raises((ValueError, TypeError)):
            get_networth_by_month("January", 2026)


# ---------------------------------------------------------------------------
# Happy path — data present, prices patched
# ---------------------------------------------------------------------------

class TestGetNetworthByMonthHappyPath:
    def test_returns_two_dataframes(self, mocker):
        from load_data import get_networth_by_month
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=_portfolio_rows())
        mocker.patch("load_data._fetch_current_prices",
                     return_value={"AAPL": 160.0, "VFIAX": 420.0})
        # Clear Streamlit cache so the patched function is actually called
        get_networth_by_month.clear()

        detailed, summary = get_networth_by_month(1, 2026)

        assert isinstance(detailed, pd.DataFrame)
        assert isinstance(summary, pd.DataFrame)

    def test_detailed_has_market_value_column(self, mocker):
        from load_data import get_networth_by_month
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=_portfolio_rows())
        mocker.patch("load_data._fetch_current_prices",
                     return_value={"AAPL": 160.0, "VFIAX": 420.0})
        get_networth_by_month.clear()

        detailed, _ = get_networth_by_month(1, 2026)

        assert "market_value" in detailed.columns
        assert "current_price" in detailed.columns

    def test_cash_symbol_price_is_one(self, mocker):
        from load_data import get_networth_by_month
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=_portfolio_rows())
        mocker.patch("load_data._fetch_current_prices",
                     return_value={"AAPL": 160.0, "VFIAX": 420.0})
        get_networth_by_month.clear()

        detailed, _ = get_networth_by_month(1, 2026)

        cash_rows = detailed[detailed["symbol"] == "CASH"]
        assert not cash_rows.empty
        assert (cash_rows["current_price"] == 1.0).all()

    def test_market_value_equals_price_times_qty(self, mocker):
        from load_data import get_networth_by_month
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=_portfolio_rows())
        mocker.patch("load_data._fetch_current_prices",
                     return_value={"AAPL": 160.0, "VFIAX": 420.0})
        get_networth_by_month.clear()

        detailed, _ = get_networth_by_month(1, 2026)

        aapl = detailed[detailed["symbol"] == "AAPL"].iloc[0]
        assert aapl["market_value"] == pytest.approx(aapl["current_price"] * aapl["qty"])

    def test_summary_has_total_row(self, mocker):
        from load_data import get_networth_by_month
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=_portfolio_rows())
        mocker.patch("load_data._fetch_current_prices",
                     return_value={"AAPL": 160.0, "VFIAX": 420.0})
        get_networth_by_month.clear()

        _, summary = get_networth_by_month(1, 2026)

        assert "Total" in summary["account_type"].values

    def test_summary_account_types_present(self, mocker):
        from load_data import get_networth_by_month
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=_portfolio_rows())
        mocker.patch("load_data._fetch_current_prices",
                     return_value={"AAPL": 160.0, "VFIAX": 420.0})
        get_networth_by_month.clear()

        _, summary = get_networth_by_month(1, 2026)

        types = set(summary["account_type"].values)
        assert "Brokerage" in types
        assert "Traditional" in types


# ---------------------------------------------------------------------------
# Empty data path
# ---------------------------------------------------------------------------

class TestGetNetworthByMonthEmptyData:
    def test_empty_portfolio_returns_empty_dataframes(self, mocker):
        from load_data import get_networth_by_month
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=pd.DataFrame())
        get_networth_by_month.clear()

        detailed, summary = get_networth_by_month(6, 2026)

        assert detailed.empty
        assert summary.empty


# ---------------------------------------------------------------------------
# Price-fetch fallback path
# ---------------------------------------------------------------------------

class TestGetNetworthByMonthPriceFallback:
    def test_price_fetch_failure_uses_purchase_price(self, mocker):
        """When _fetch_current_prices raises, purchase_price is used as fallback."""
        from load_data import get_networth_by_month
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=_portfolio_rows())
        mocker.patch("load_data._fetch_current_prices",
                     side_effect=RuntimeError("network error"))
        get_networth_by_month.clear()

        detailed, _ = get_networth_by_month(1, 2026)

        # Should not raise; AAPL current_price falls back to purchase_price 150.0
        aapl = detailed[detailed["symbol"] == "AAPL"].iloc[0]
        assert aapl["current_price"] == pytest.approx(150.0)

    def test_stored_end_of_month_prices_used_for_past_months(self, mocker):
        """Historical rows with end_of_month_price use stored prices, not live fetch."""
        from load_data import get_networth_by_month
        rows = _portfolio_rows(month=1, year=2025)
        rows["end_of_month_price"] = [175.0, 430.0, 1.0]
        fetch_mock = mocker.patch("load_data._fetch_current_prices",
                                  return_value={})
        mocker.patch("load_data.get_portfolio_truth_by_month",
                     return_value=rows)
        get_networth_by_month.clear()

        detailed, _ = get_networth_by_month(1, 2025)

        aapl = detailed[detailed["symbol"] == "AAPL"].iloc[0]
        assert aapl["current_price"] == pytest.approx(175.0)
        # Live price fetch should NOT have been called for this past month
        fetch_mock.assert_not_called()
