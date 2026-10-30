"""market_hours (when a fetched price can no longer have changed) and the cache rules built on it."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import market_hours as mh

NY = ZoneInfo("America/New_York")


def ny(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=NY)


# ------------------------------------------------------------------ calendar

def test_holidays_2026_match_the_nyse_schedule():
    assert mh.holidays(2026) == {
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
        date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    }


def test_holidays_2027_weekend_observance():
    h = mh.holidays(2027)
    assert date(2027, 6, 18) in h            # Juneteenth on a Saturday -> Friday
    assert date(2027, 7, 5) in h             # July 4 on a Sunday -> Monday
    assert date(2027, 12, 24) in h           # Christmas on a Saturday -> Friday
    assert date(2027, 1, 1) in h and date(2027, 3, 26) in h     # New Year; Good Friday (Easter Mar 28)


def test_saturday_new_year_is_not_moved_to_the_previous_year():
    assert date(2021, 12, 31) not in mh.holidays(2021)          # NYSE stays open when Jan 1 is a Saturday
    assert date(2022, 1, 1) not in mh.holidays(2022)


def test_trading_days():
    assert mh.is_trading_day(date(2026, 10, 29))                # Thursday
    assert not mh.is_trading_day(date(2026, 10, 31))            # Saturday
    assert not mh.is_trading_day(date(2026, 11, 26))            # Thanksgiving
    assert mh.is_trading_day(date(2026, 11, 27))


def test_next_open_skips_weekends_and_holidays():
    assert mh.next_open_after(ny(2026, 10, 29, 17)) == ny(2026, 10, 30, 9, 30)
    assert mh.next_open_after(ny(2026, 10, 30, 17)) == ny(2026, 11, 2, 9, 30)       # Friday -> Monday
    assert mh.next_open_after(ny(2026, 11, 25, 17)) == ny(2026, 11, 27, 9, 30)      # Thanksgiving
    assert mh.next_open_after(ny(2026, 10, 29, 9, 30)) == ny(2026, 10, 30, 9, 30)   # strictly after
    assert mh.next_open_after(ny(2026, 10, 29, 8)) == ny(2026, 10, 29, 9, 30)


# ------------------------------------------------------------------ were the prices final?

@pytest.mark.parametrize("when,final", [
    (ny(2026, 10, 29, 8, 0), True),          # before the open
    (ny(2026, 10, 29, 9, 29), True),
    (ny(2026, 10, 29, 9, 30), False),        # the open
    (ny(2026, 10, 29, 12, 0), False),
    (ny(2026, 10, 29, 16, 30), False),       # after the close, but fund NAVs are not out yet
    (ny(2026, 10, 29, 20, 0), True),         # settled
    (ny(2026, 10, 31, 12, 0), True),         # Saturday
    (ny(2026, 11, 26, 12, 0), True),         # Thanksgiving, mid-day
])
def test_prices_final_at(when, final):
    assert mh.prices_final_at(when) is final


def test_naive_timestamps_are_treated_as_utc():
    # 02:00 UTC on Oct 30 is 22:00 the evening before in New York: final.
    assert mh.prices_final_at(datetime(2026, 10, 30, 2, 0)) is True
    # 16:00 UTC is noon in New York on a trading day: not final.
    assert mh.prices_final_at(datetime(2026, 10, 29, 16, 0)) is False


# ------------------------------------------------------------------ unchanged since

def test_evening_fetch_stays_valid_overnight_and_goes_stale_at_the_open():
    fetched = ny(2026, 10, 29, 21, 0)
    assert mh.prices_unchanged_since(fetched, ny(2026, 10, 30, 9, 29))
    assert not mh.prices_unchanged_since(fetched, ny(2026, 10, 30, 9, 30))


def test_friday_evening_fetch_is_good_all_weekend():
    fetched = ny(2026, 10, 30, 21, 0)
    assert mh.prices_unchanged_since(fetched, ny(2026, 11, 1, 15, 0))
    assert not mh.prices_unchanged_since(fetched, ny(2026, 11, 2, 9, 31))


def test_midday_fetch_is_never_treated_as_final():
    assert not mh.prices_unchanged_since(ny(2026, 10, 29, 12, 0), ny(2026, 10, 29, 12, 1))
    assert not mh.prices_unchanged_since(ny(2026, 10, 29, 16, 30), ny(2026, 10, 29, 18, 0))


def test_clock_going_backwards_is_not_fresh():
    assert not mh.prices_unchanged_since(ny(2026, 10, 29, 21, 0), ny(2026, 10, 29, 20, 0))


def test_is_fresh_combines_age_and_market_state():
    now = ny(2026, 10, 29, 12, 0)
    assert mh.is_fresh(now - timedelta(seconds=100), 300, now)               # young
    assert not mh.is_fresh(now - timedelta(seconds=400), 300, now)           # old, market open
    late = ny(2026, 10, 29, 21, 0)
    assert mh.is_fresh(late, 300, ny(2026, 10, 30, 8, 0))                    # old but market closed
    assert not mh.is_fresh(late, 300, ny(2026, 10, 30, 10, 0))               # market has opened since


# ------------------------------------------------------------------ the caches

@pytest.fixture
def env(tmp_path, monkeypatch):
    import shutil
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    shutil.copy(Path(__file__).resolve().parent.parent / "retirement_config.json.example", tmp_path / "retirement_config.json")
    import app_cache
    import portfolio_db as pdb
    pdb._tls.conns = {}
    app_cache.clear_all()
    pdb.db_upsert(pd.DataFrame([dict(month=10, year=2026, account_name="A", account_type="Brokerage", owner="Joint",
                                     symbol="AAA", name="AAA", sector="Technology", qty=10, purchase_price=1.0,
                                     purchase_date="2020-01-01")]))
    yield tmp_path
    pdb._tls.conns = {}
    app_cache.clear_all()


def _frame():
    import portfolio
    return pd.DataFrame([{c: 1 for c in portfolio.PORTFOLIO_DISPLAY_COLUMNS}])


def test_portfolio_cache_is_dropped_when_the_database_changes(env):
    import portfolio
    import portfolio_db as pdb
    portfolio.save_portfolio_cache(_frame(), 10, 2026)
    assert not portfolio.load_portfolio_cache(10, 2026).empty
    pdb.db_upsert(pd.DataFrame([dict(month=10, year=2026, account_name="A", account_type="Brokerage", owner="Joint",
                                     symbol="BBB", name="BBB", sector="Technology", qty=1, purchase_price=1.0,
                                     purchase_date="2020-01-01")]))
    assert portfolio.load_portfolio_cache(10, 2026).empty            # a young cache, but of the old holdings


def test_database_change_also_clears_the_in_memory_caches(env, monkeypatch):
    import app_cache
    import portfolio
    import portfolio_db as pdb
    price = {"v": 100.0}
    monkeypatch.setattr(portfolio, "get_current_price", lambda s: price["v"])
    monkeypatch.setattr(portfolio, "get_ticker_name", lambda s, month=None, year=None: "AAA")
    monkeypatch.setattr(portfolio, "get_current_dividend", lambda s, month=None, year=None: ("na", 0.0, 0))
    first = portfolio.build_portfolio_display(10, 2026)
    portfolio.save_portfolio_cache(first, 10, 2026)
    pdb.db_upsert(pd.DataFrame([dict(month=10, year=2026, account_name="A", account_type="Brokerage", owner="Joint",
                                     symbol="AAA", name="AAA", sector="Technology", qty=99, purchase_price=1.0,
                                     purchase_date="2020-01-01")]))
    price["v"] = 150.0
    assert portfolio.load_portfolio_cache(10, 2026).empty
    rebuilt = portfolio.build_portfolio_display(10, 2026)
    body = rebuilt[rebuilt["Account"] != "Portfolio Totals"]
    assert list(body["Current value"]) == [99 * 150.0]               # new quantity AND new price, not replayed


def test_cache_from_before_this_change_has_no_stamp_and_is_rebuilt(env):
    import portfolio
    df = _frame()
    df["_cache_month"] = 10; df["_cache_year"] = 2026; df["_cache_ts"] = datetime.utcnow().isoformat()
    df.to_parquet(portfolio.PORTFOLIO_CACHE_FILE, index=False)
    assert portfolio.load_portfolio_cache(10, 2026).empty


def test_portfolio_cache_outlives_its_ttl_while_the_market_is_closed(env, monkeypatch):
    import portfolio
    portfolio.save_portfolio_cache(_frame(), 10, 2026)
    cached = pd.read_parquet(portfolio.PORTFOLIO_CACHE_FILE)
    evening = ny(2026, 10, 29, 21, 0)
    cached["_cache_ts"] = evening.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    cached.to_parquet(portfolio.PORTFOLIO_CACHE_FILE, index=False)

    monkeypatch.setattr(mh, "_now", lambda: ny(2026, 10, 30, 8, 0).astimezone(timezone.utc))
    assert not portfolio.load_portfolio_cache(10, 2026).empty        # 11 hours old, market closed
    monkeypatch.setattr(mh, "_now", lambda: ny(2026, 10, 30, 10, 0).astimezone(timezone.utc))
    assert portfolio.load_portfolio_cache(10, 2026).empty            # the market has opened since


def test_in_memory_display_table_expires_so_a_rebuild_sees_new_prices(env, monkeypatch):
    """Without a TTL the table was remembered for the whole process and a rebuild replayed old prices."""
    import app_cache
    import portfolio
    price = {"v": 100.0}
    monkeypatch.setattr(portfolio, "get_current_price", lambda s: price["v"])
    monkeypatch.setattr(portfolio, "get_ticker_name", lambda s, month=None, year=None: "AAA")
    monkeypatch.setattr(portfolio, "get_current_dividend", lambda s, month=None, year=None: ("na", 0.0, 0))
    value = lambda: portfolio.build_portfolio_display(10, 2026).iloc[0]["Current value"]
    assert value() == 1000.0
    price["v"] = 150.0
    assert value() == 1000.0                                         # inside the TTL: remembered
    real = app_cache.time.monotonic
    monkeypatch.setattr(app_cache.time, "monotonic", lambda: real() + portfolio.PORTFOLIO_CACHE_TTL_SECONDS + 1)
    assert value() == 1500.0                                         # after the TTL: rebuilt


def test_networth_cache_rules(env, monkeypatch):
    import load_data
    nw = pd.DataFrame({c: [1.0, 2.0] for c in load_data.NETWORTH_COLUMNS},
                      index=pd.DatetimeIndex(["2026-09-01", "2026-10-01"], name="date"))
    load_data.save_networth_cache(nw, 12)
    assert not load_data.load_networth_cache(12).empty
    # a different month: the history must now run one month further
    monkeypatch.setattr(load_data, "_networth_period", lambda: "2026-11")
    assert load_data.load_networth_cache(12).empty
    monkeypatch.undo()
    # holdings changed
    import portfolio_db as pdb
    pdb.db_upsert(pd.DataFrame([dict(month=10, year=2026, account_name="Z", account_type="Roth", owner="Joint",
                                     symbol="ZZZ", name="ZZZ", sector="Technology", qty=1, purchase_price=1.0,
                                     purchase_date="2020-01-01")]))
    assert load_data.load_networth_cache(12).empty


def test_db_stamp_changes_with_every_write_and_survives_a_missing_wal(env):
    import load_data
    import portfolio_db as pdb
    a = load_data.db_stamp()
    pdb.db_upsert(pd.DataFrame([dict(month=10, year=2026, account_name="Q", account_type="Roth", owner="Joint",
                                     symbol="QQQ", name="QQQ", sector="Technology", qty=1, purchase_price=1.0,
                                     purchase_date="2020-01-01")]))
    assert load_data.db_stamp() != a
    assert isinstance(load_data.db_stamp(), str)
