"""Batched price fetching in load_data._fetch_prices (one Yahoo request, not one per symbol per month)."""
from datetime import datetime

import pandas as pd
import pytest

import load_data


def _frame(closes: dict) -> pd.DataFrame:
    """What yf.download(..., group_by='ticker') returns: (ticker, field) columns."""
    cols = {}
    for sym, series in closes.items():
        cols[(sym, "Close")] = series
    df = pd.DataFrame(cols)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


def _days(*pairs):
    return pd.Series([v for _, v in pairs], index=pd.DatetimeIndex([d for d, _ in pairs]))


@pytest.fixture(autouse=True)
def fresh_history(monkeypatch):
    monkeypatch.setattr(load_data, "_history_cache", {})


@pytest.fixture
def downloads(monkeypatch):
    """Replace yf.download; records each call and serves the configured closes."""
    calls = []
    data = {}

    def fake(symbols, **kw):
        calls.append((list(symbols), kw))
        return _frame({s: data[s] for s in symbols if s in data})

    monkeypatch.setattr(load_data.yf, "download", fake)
    return calls, data


def test_current_prices_use_one_request_for_all_symbols(downloads):
    calls, data = downloads
    data["AAPL"] = _days(("2026-10-27", 200.0), ("2026-10-28", 201.5))
    data["VTI"] = _days(("2026-10-27", 300.0), ("2026-10-28", 305.0))
    prices = load_data._fetch_current_prices(["AAPL", "VTI"])
    assert prices == {"AAPL": 201.5, "VTI": 305.0}
    assert len(calls) == 1 and calls[0][1]["period"] == "4d"


def test_cash_symbols_never_reach_yahoo(downloads):
    calls, data = downloads
    data["AAPL"] = _days(("2026-10-28", 10.0))
    prices = load_data._fetch_current_prices(["CASH", "MF:CASH", "AAPL"])
    assert prices == {"CASH": 1.0, "MF:CASH": 1.0, "AAPL": 10.0}
    assert calls[0][0] == ["AAPL"]
    assert load_data._fetch_current_prices(["CASH"]) == {"CASH": 1.0}
    assert len(calls) == 1                       # an all-cash list makes no request


def test_unknown_symbol_and_option_contract_come_back_as_none(downloads):
    calls, data = downloads
    data["AAPL"] = _days(("2026-10-28", 10.0))
    option = "SOFI  280121C00018000"
    prices = load_data._fetch_current_prices(["AAPL", "NOPE", option])
    assert prices == {"AAPL": 10.0, "NOPE": None, option: None}
    assert "NOPE" in calls[0][0] and option not in calls[0][0]


def test_single_symbol_download_with_flat_columns(monkeypatch):
    """yfinance returns plain columns when only one ticker is requested."""
    monkeypatch.setattr(load_data.yf, "download",
                        lambda symbols, **kw: pd.DataFrame({"Close": [1.0, 2.5]}, index=pd.DatetimeIndex(["2026-10-27", "2026-10-28"])))
    assert load_data._fetch_current_prices(["VTI"]) == {"VTI": 2.5}


def test_download_failure_returns_none_for_every_symbol(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(load_data.yf, "download", boom)
    assert load_data._fetch_current_prices(["AAPL", "CASH"]) == {"CASH": 1.0, "AAPL": None}


def test_month_end_prices_share_one_cached_download(downloads):
    calls, data = downloads
    today = pd.Timestamp.now().normalize()
    data["AAPL"] = _days((today - pd.Timedelta(days=95), 90.0), (today - pd.Timedelta(days=65), 100.0),
                         (today - pd.Timedelta(days=64), 101.0), (today - pd.Timedelta(days=5), 120.0))
    target1 = (today - pd.Timedelta(days=64)).to_pydatetime()
    target2 = (today - pd.Timedelta(days=94)).to_pydatetime()
    assert load_data._fetch_prices(["AAPL"], target_date=target1) == {"AAPL": 101.0}
    assert load_data._fetch_prices(["AAPL"], target_date=target2) == {"AAPL": 90.0}
    assert len(calls) == 1                       # the second month reused the cached history


def test_month_end_window_matches_ticker_history_semantics(downloads):
    """A close from the week before the target counts; one after the target day does not."""
    calls, data = downloads
    today = pd.Timestamp.now().normalize()
    target = today - pd.Timedelta(days=60)
    data["AAPL"] = _days((target - pd.Timedelta(days=6), 50.0), (target + pd.Timedelta(days=3), 99.0))
    assert load_data._fetch_prices(["AAPL"], target_date=target.to_pydatetime()) == {"AAPL": 50.0}
    data["TOOEARLY"] = _days((target - pd.Timedelta(days=9), 7.0))
    assert load_data._fetch_prices(["TOOEARLY"], target_date=target.to_pydatetime()) == {"TOOEARLY": None}


def test_timezone_aware_index_is_handled(downloads):
    calls, data = downloads
    today = pd.Timestamp.now().normalize()
    target = today - pd.Timedelta(days=40)
    s = _days((target - pd.Timedelta(days=1), 42.0))
    s.index = s.index.tz_localize("America/New_York")
    data["AAPL"] = s
    assert load_data._fetch_prices(["AAPL"], target_date=target.to_pydatetime()) == {"AAPL": 42.0}


def test_old_target_dates_use_a_direct_narrow_download(downloads):
    calls, data = downloads
    data["AAPL"] = _days(("2020-03-30", 70.0), ("2020-03-31", 71.0))
    assert load_data._fetch_prices(["AAPL"], target_date=datetime(2020, 3, 31)) == {"AAPL": 71.0}
    assert "start" in calls[0][1] and calls[0][1]["start"] == pd.Timestamp("2020-03-24")
    assert load_data._history_cache == {}        # not cached: it is outside the shared window


def test_failed_lookup_is_not_cached(downloads):
    calls, data = downloads
    today = pd.Timestamp.now().normalize()
    target = (today - pd.Timedelta(days=30)).to_pydatetime()
    assert load_data._fetch_prices(["LATE"], target_date=target) == {"LATE": None}
    data["LATE"] = _days((today - pd.Timedelta(days=31), 5.0))
    assert load_data._fetch_prices(["LATE"], target_date=target) == {"LATE": 5.0}
    assert len(calls) == 2                       # the miss was retried, not remembered


def test_cache_entries_expire(downloads, monkeypatch):
    calls, data = downloads
    today = pd.Timestamp.now().normalize()
    data["AAPL"] = _days((today - pd.Timedelta(days=31), 5.0))
    target = (today - pd.Timedelta(days=30)).to_pydatetime()
    load_data._fetch_prices(["AAPL"], target_date=target)
    monkeypatch.setattr(load_data.time, "time", lambda: 1e12)
    load_data._fetch_prices(["AAPL"], target_date=target)
    assert len(calls) == 2


def test_only_missing_symbols_are_downloaded(downloads):
    calls, data = downloads
    today = pd.Timestamp.now().normalize()
    target = (today - pd.Timedelta(days=30)).to_pydatetime()
    data["AAPL"] = _days((today - pd.Timedelta(days=31), 5.0))
    data["VTI"] = _days((today - pd.Timedelta(days=31), 6.0))
    load_data._fetch_prices(["AAPL"], target_date=target)
    out = load_data._fetch_prices(["AAPL", "VTI"], target_date=target)
    assert out == {"AAPL": 5.0, "VTI": 6.0}
    assert calls[1][0] == ["VTI"]


def test_empty_and_invalid_input():
    assert load_data._fetch_prices([]) == {}
    with pytest.raises(ValueError):
        load_data._fetch_prices("AAPL")


def test_display_table_lookups_run_concurrently_and_match_sequential_results(monkeypatch):
    """build_portfolio_display runs the per-symbol Yahoo lookups on a thread pool; results must be identical."""
    import threading
    import portfolio

    portfolio.build_portfolio_display.clear()
    df = pd.DataFrame({
        "account_name": ["A", "A", "B"], "account_type": ["Brokerage", "Roth", "Roth"], "symbol": ["AAA", "BBB", "AAA"],
        "name": ["", "", ""], "sector": ["", "", ""], "qty": [10.0, 2.0, 5.0], "purchase_price": [1.0, 10.0, 1.0],
        "purchase_date": ["2020-01-01"] * 3,
    })
    threads = set()
    price = {"AAA": 3.0, "BBB": 7.0}

    def lookup(value):
        def f(*a, **k):
            threads.add(threading.get_ident())
            return value(a[0])
        return f

    monkeypatch.setattr(portfolio, "getPortfolioData", lambda month=None, year=None: df)
    monkeypatch.setattr(portfolio, "get_current_price", lookup(lambda s: price[s]))
    monkeypatch.setattr(portfolio, "get_ticker_name", lookup(lambda s: f"{s} Inc"))
    monkeypatch.setattr(portfolio, "get_current_dividend", lookup(lambda s: ("01/01/2026", 1.0, 4.0)))
    monkeypatch.setattr(portfolio, "get_sector", lambda s, month=None, year=None: "Technology")

    out = portfolio.build_portfolio_display(10, 2026)
    body = out[out["Account"] != "Portfolio Totals"]
    assert list(body["Ticker"]) == ["AAA", "BBB", "AAA"]
    assert list(body["Current value"]) == [30.0, 14.0, 15.0]
    assert set(body["Name"]) == {"AAA Inc", "BBB Inc"} and set(body["Sector"]) == {"Technology"}
    assert threading.get_ident() not in threads          # lookups ran on pool threads, not the caller
    portfolio.build_portfolio_display.clear()
