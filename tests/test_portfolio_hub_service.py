"""Portfolio Hub service tests (app/services/portfolio_hub.py) and the CASH pricing fix.

These do not need FastAPI, so they run on the host as well as in the container image.
Network calls (Yahoo Finance) are replaced; each test works in its own directory with its own
portfolio.db, because the engine modules resolve ``portfolio.db`` relative to the working directory.
"""
import shutil
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
M, Y = 10, 2026


def _row(account, symbol, qty, price, **kw):
    base = dict(month=M, year=Y, account_name=account, account_type="Brokerage", owner="Joint",
                symbol=symbol, name=symbol, sector="Technology", qty=qty, purchase_price=price,
                purchase_date="2020-01-15")
    base.update(kw)
    return base


@pytest.fixture
def hub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copy(REPO / "retirement_config.json.example", tmp_path / "retirement_config.json")
    import app_cache
    import config
    import portfolio_data_entry as pde
    import portfolio_db as pdb
    from app.services import portfolio_hub

    pdb._tls.conns = {}                      # connections are cached under the relative path "portfolio.db"
    monkeypatch.setattr(pdb, "CSV_BACKUP_PATH", Path("portfolio_data_truth.csv"))   # tests/conftest.py redirects it for the session
    app_cache.clear_all()
    config.reload_config()
    monkeypatch.setattr(pde, "_trigger_portfolio_cache_rebuild", lambda df: None)
    monkeypatch.setattr(pde, "validate_ticker_symbol",
                        lambda s: (True, f"{s} Inc", "Technology", "") if s != "BADSYM"
                        else (False, "", "", "Symbol 'BADSYM' not found in Yahoo Finance"))
    pdb.db_upsert(pd.DataFrame([
        _row("Schwab-1", "AAPL", 10, 100.0),
        _row("Schwab-1", "CASH", 500, 1.0, sector="MF:Cash"),
        _row("IRA", "VTI", 5, 200.0, account_type="Traditional"),
    ]))
    yield portfolio_hub
    pdb._tls.conns = {}
    app_cache.clear_all()
    monkeypatch.undo()                       # back to the real working directory, then drop the example config we loaded
    config.reload_config()


def _grid(rows):
    return [{**{k: v for k, v in r.items() if k not in ("month", "year")}, "rid": i + 1} for i, r in enumerate(rows)]


def _stored():
    import portfolio_db as pdb
    return pdb.db_get_by_month(M, Y)


# --------------------------------------------------------------------------- CASH pricing

@pytest.mark.parametrize("symbol", ["CASH", "MF:CASH", "cash", " Cash "])
def test_cash_symbols_priced_at_one_without_yahoo(symbol, monkeypatch):
    import portfolio

    def boom(*a, **k):
        raise AssertionError("Yahoo Finance must not be called for cash")
    monkeypatch.setattr(portfolio.yf, "Ticker", boom)
    portfolio.get_current_price.clear()
    assert portfolio.is_cash_symbol(symbol)
    assert portfolio.get_current_price(symbol.strip()) == 1.0
    assert portfolio.get_ticker_name(symbol) == "Cash"
    assert portfolio.get_sector(symbol) == "MF:Cash"
    assert portfolio.get_current_dividend(symbol) == ("na", 0.0, 0)
    assert portfolio.get_dividend_frequency(symbol) == 0


def test_non_cash_symbols_are_not_cash():
    import portfolio
    for s in ("AAPL", "CASHX", "MF:CASHX", "", "VMFXX"):
        assert not portfolio.is_cash_symbol(s)


def test_portfolio_display_prices_cash_at_face_value(hub, monkeypatch):
    import portfolio
    monkeypatch.setattr(portfolio, "get_ticker_name", lambda s, **k: "Cash" if portfolio.is_cash_symbol(s) else s)
    monkeypatch.setattr(portfolio, "get_sector", lambda s, **k: "MF:Cash" if portfolio.is_cash_symbol(s) else "Technology")
    monkeypatch.setattr(portfolio, "get_current_dividend", lambda s, **k: ("na", 0.0, 0))
    real = portfolio.get_current_price
    monkeypatch.setattr(portfolio, "get_current_price", lambda s: 150.0 if s == "AAPL" else (200.0 if s == "VTI" else real(s)))
    portfolio.build_portfolio_display.clear()
    df = portfolio.build_portfolio_display(month=M, year=Y)
    cash = df[df["Ticker"] == "Cash"].iloc[0]
    assert cash["Price"] == 1.0 and cash["Current value"] == 500.0   # was 500 x ~$76 before the fix


# --------------------------------------------------------------------------- read paths

def test_meta_lists_periods_and_choices(hub):
    m = hub.meta()
    assert {"month": M, "year": Y, "rows": 3} in m["periods"]
    assert "Brokerage" in m["account_types"] and "Joint" in m["owners"]
    assert "MF:Cash" in m["sectors"] and "Unknown" in m["stale_sectors"]
    assert m["effective"] == {"month": M, "year": Y}


def test_list_holdings_shape(hub):
    rows = hub.list_holdings(M, Y)["rows"]
    assert len(rows) == 3
    assert set(rows[0]) == set(hub.COLUMNS)
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["qty"] == 10 and aapl["purchase_price"] == 100.0 and aapl["purchase_date"] == "2020-01-15"


def test_copy_previous_redates_nothing_and_requires_data(hub):
    with pytest.raises(LookupError):
        hub.copy_previous(M, Y)              # September is empty
    import portfolio_db as pdb
    pdb.db_upsert(pd.DataFrame([_row("Schwab-1", "AAPL", 1, 1.0, month=9)]))
    out = hub.copy_previous(M, Y)
    assert out["from"] == {"month": 9, "year": Y} and len(out["rows"]) == 1
    assert len(_stored()) == 3               # nothing was written


# --------------------------------------------------------------------------- validation

def test_validate_reports_row_errors_with_rid(hub):
    rows = _grid([_row("A", "AAPL", 10, 100.0), _row("A", "MSFT", 0, 100.0), _row("A", "IBM", 1, -5)])
    rep = hub.validate(rows, M, Y)
    assert {e["rid"] for e in rep["errors"]} == {2, 3}
    assert "zero" in next(e for e in rep["errors"] if e["rid"] == 2)["message"].lower()


def test_validate_flags_duplicates_and_bad_dates(hub):
    rows = _grid([_row("A", "AAPL", 1, 1.0), _row("A", "AAPL", 2, 1.0), _row("A", "IBM", 1, 1.0, purchase_date="31/12/2020")])
    msgs = [e["message"] for e in hub.validate(rows, M, Y)["errors"]]
    assert any("Duplicate holding" in m for m in msgs)
    assert any("Invalid purchase_date" in m for m in msgs)


def test_validate_ticker_warnings_skip_cash_and_options(hub):
    rows = _grid([_row("A", "CASH", 1, 1.0, sector="MF:Cash"), _row("A", "BADSYM", 1, 1.0),
                  _row("A", "XYZ", 1, 1.0, name="", sector="")])
    w = hub.validate(rows, M, Y)["warnings"]
    assert [x["rid"] for x in w] == [2, 3]
    assert "not found" in w[0]["message"] and "Suggested" in w[1]["message"]


def test_negative_qty_allowed_only_for_options(hub):
    opt = "SOFI  260402C00020000"
    ok = hub.validate(_grid([_row("A", opt, -2, 1.5, sector="Options:Call")]), M, Y)
    assert ok["errors"] == []
    bad = hub.validate(_grid([_row("A", "AAPL", -2, 1.5)]), M, Y)
    assert len(bad["errors"]) == 1


# --------------------------------------------------------------------------- save

def test_save_replaces_month_adds_updates_and_removes(hub):
    rows = _grid([_row("Schwab-1", "AAPL", 12, 100.0),                      # changed qty
                  _row("IRA", "VTI", 5, 200.0, account_type="Traditional"),  # unchanged
                  _row("IRA", "BND", 3, 80.0, account_type="Traditional")])  # new; Schwab-1/CASH removed
    out = hub.save_holdings(rows, M, Y)
    assert (out["added"], out["updated"], out["removed"], out["saved"]) == (1, 1, 1, 3)
    stored = _stored()
    assert set(stored["symbol"]) == {"AAPL", "VTI", "BND"}
    assert float(stored.loc[stored.symbol == "AAPL", "qty"].iloc[0]) == 12


def test_save_writes_backup_of_previous_month_first(hub):
    out = hub.save_holdings(_grid([_row("A", "AAPL", 1, 1.0)]), M, Y)
    path = Path(".backups") / out["backup"]
    assert path.exists()
    old = pd.read_csv(path)
    assert set(old["symbol"]) == {"AAPL", "CASH", "VTI"} and len(old) == 3


def test_save_with_errors_writes_nothing(hub):
    from app.services.portfolio_hub import HoldingsValidationError
    rows = _grid([_row("A", "AAPL", 1, 1.0), _row("A", "IBM", 0, 1.0)])
    with pytest.raises(HoldingsValidationError) as ei:
        hub.save_holdings(rows, M, Y)
    assert ei.value.errors[0]["rid"] == 2
    assert len(_stored()) == 3 and not Path(".backups").exists()


def test_save_refuses_empty_list(hub):
    from app.services.portfolio_hub import HoldingsValidationError
    with pytest.raises(HoldingsValidationError):
        hub.save_holdings([], M, Y)
    assert len(_stored()) == 3


def test_save_does_not_touch_other_months(hub):
    import portfolio_db as pdb
    pdb.db_upsert(pd.DataFrame([_row("Schwab-1", "AAPL", 7, 1.0, month=9)]))
    hub.save_holdings(_grid([_row("A", "AAPL", 1, 1.0)]), M, Y)
    sept = pdb.db_get_by_month(9, Y)
    assert len(sept) == 1 and float(sept["qty"].iloc[0]) == 7


def test_save_keeps_end_of_month_price(hub):
    import portfolio_db as pdb
    conn = pdb.get_db_connection()
    conn.execute("UPDATE holdings SET end_of_month_price=123.45 WHERE symbol='AAPL'")
    conn.commit()
    hub.save_holdings(_grid([_row("Schwab-1", "AAPL", 11, 100.0)]), M, Y)
    row = conn.execute("SELECT end_of_month_price FROM holdings WHERE symbol='AAPL'").fetchone()
    assert row[0] == 123.45


def test_save_normalises_dates_and_blank_owner(hub):
    hub.save_holdings(_grid([_row("A", "AAPL", 1, 1.0, owner="", purchase_date="2021-03-05T00:00:00")]), M, Y)
    r = hub.list_holdings(M, Y)["rows"][0]
    assert r["owner"] == "Joint" and r["purchase_date"] == "2021-03-05"


def test_save_writes_csv_backup_and_drops_caches(hub):
    import load_data
    import portfolio
    Path(portfolio.PORTFOLIO_CACHE_FILE).write_text("x")
    Path(load_data.NETWORTH_CACHE_FILE).write_text("x")
    hub.save_holdings(_grid([_row("A", "AAPL", 1, 1.0)]), M, Y)
    assert not Path(portfolio.PORTFOLIO_CACHE_FILE).exists() and not Path(load_data.NETWORTH_CACHE_FILE).exists()
    assert "AAPL" in Path("portfolio_data_truth.csv").read_text()


# --------------------------------------------------------------------------- CSV import, tools

def test_import_csv_assigns_period_and_reports_other_months(hub):
    csv = ("month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price,purchase_date\n"
           "1,2020,Acct,Roth,Joint,VTI,Vanguard,MF:US,2,50,2019-05-01\n")
    out = hub.import_csv(csv, M, Y)
    assert out["rows"][0]["symbol"] == "VTI" and out["warnings"]
    assert len(_stored()) == 3               # import never writes


def test_import_csv_missing_columns_and_garbage(hub):
    with pytest.raises(ValueError, match="missing required columns"):
        hub.import_csv("a,b\n1,2\n", M, Y)
    with pytest.raises(ValueError):
        hub.import_csv("", M, Y)


def test_import_without_optional_columns_still_validates(hub):
    out = hub.import_csv("account_name,account_type,symbol,qty,purchase_price\nAcct,Roth,VTI,2,50\n", M, Y)
    assert out["rows"][0]["owner"] == "Joint" and out["rows"][0]["name"] == ""


def test_backup_all_writes_csv(hub):
    out = hub.backup_all()
    assert out["rows"] == 3 and (Path(".backups") / Path(out["file"]).name).exists()


def test_lookup_returns_name_sector_and_price(hub, monkeypatch):
    import portfolio
    monkeypatch.setattr(portfolio, "get_current_price", lambda s: 12.5)
    r = hub.lookup(" aapl ")
    assert r["valid"] and r["symbol"] == "AAPL" and r["price"] == 12.5 and r["sector"] == "Technology"
    assert hub.lookup("BADSYM")["valid"] is False
    with pytest.raises(ValueError):
        hub.lookup("  ")


def test_indicators_skip_failures_per_symbol(hub, monkeypatch):
    import portfolio_market_indicators as pmi
    pmi.clear_indicator_cache()
    monkeypatch.setattr(pmi, "fetch_security_data", lambda s, w: None)
    out = hub.indicators(M, Y)["indicators"]
    assert out["CASH"]["label"] == "Hold" and out["CASH"]["price"] == 1.0   # cash needs no data
    assert out["AAPL"] is None and out["VTI"] is None


# --------------------------------------------------------------------------- overview

def _networth(rows):
    idx = pd.DatetimeIndex([r[0] for r in rows], name="date")
    df = pd.DataFrame([r[1:] for r in rows], index=idx, columns=["cash", "taxable", "tax_deferred", "tax_free", "total"])
    return df


def test_overview_kpis_tax_efficiency_and_benchmark(hub, monkeypatch):
    from app.services import networth as nw_service
    import datetime as dt
    year = dt.date.today().year
    nw = _networth([(f"{year}-01-01", 10, 20, 60, 10, 100.0), (f"{year}-02-01", 10, 30, 60, 20, 120.0)])
    monkeypatch.setattr(nw_service, "load_networth_history", lambda *a, **k: nw)
    o = hub.overview()
    k = o["kpis"]
    assert k["total_value"] == 120.0
    assert k["month_change"]["amount"] == 20.0 and round(k["month_change"]["percent"], 1) == 20.0
    assert k["ytd"]["amount"] == 20.0
    t = o["tax"]
    assert round(t["score"]) == round((20 + 30) / 120 * 100) and round(t["roth_ratio"]) == round(20 / 80 * 100)
    assert any("Low Roth Ratio" in r["title"] for r in t["recommendations"])
    assert len(o["history"]["labels"]) == 2 and o["mix"]["values"] == [10.0, 30.0, 60.0, 20.0]
    perf = o["performance"]
    assert perf["benchmark"][0] == 100.0 and perf["benchmark"][1] == pytest.approx(100 * (1 + 0.07 / 12))


def test_overview_with_no_history(hub, monkeypatch):
    from app.services import networth as nw_service
    monkeypatch.setattr(nw_service, "load_networth_history", lambda *a, **k: _networth([]))
    o = hub.overview()
    assert o["history"] is None and o["performance"] is None and o["kpis"]["total_value"] == 0.0


def test_treemap_excludes_zero_value_and_groups_tax_type_sector_ticker(hub, monkeypatch):
    from app.services import dashboard
    frame = pd.DataFrame([
        {"Account": "A", "Tax Type": "Brokerage", "Ticker": "AAPL", "Sector": "Technology", "Current value": 1500.0},
        {"Account": "A", "Tax Type": "Brokerage", "Ticker": "Cash", "Sector": "MF:Cash", "Current value": 500.0},
        {"Account": "A", "Tax Type": "Brokerage", "Ticker": "OPT", "Sector": "Options:Call", "Current value": 0.0},
        {"Account": "Portfolio Totals", "Tax Type": None, "Ticker": None, "Sector": None, "Current value": 2000.0},
    ])
    monkeypatch.setattr(dashboard, "_portfolio_frame", lambda m, y: frame)
    t = hub.treemap()
    assert t["ready"] and t["excluded"] == 0                    # the zero-value row is dropped before counting
    ids = {n["id"] for n in t["nodes"]}
    assert "Brokerage/Technology/AAPL" in ids and "Brokerage/MF:Cash/Cash" in ids
    assert next(n for n in t["nodes"] if n["id"] == "Brokerage")["value"] == 2000.0


# --------------------------------------------------------------------------- shared DB connection

def test_last_known_price_does_not_close_the_shared_connection(hub):
    """A failed Yahoo price used to close the thread's shared connection, so every later read on
    that thread returned an empty frame ("Cannot operate on a closed database")."""
    import portfolio
    import portfolio_db as pdb
    assert portfolio._last_known_price("AAPL") == 100.0
    assert portfolio._last_known_price("NOPE") == 0.0
    assert len(pdb.db_get_by_month(M, Y)) == 3          # still readable afterwards
    assert len(hub.list_holdings(M, Y)["rows"]) == 3
    assert hub.meta()["periods"]                        # meta() queries the connection directly


# --------------------------------------------------------------------------- Schwab Direct

def test_schwab_status_not_configured_without_credentials(hub, monkeypatch):
    monkeypatch.delenv("SCHWAB_APP_KEY", raising=False)
    monkeypatch.delenv("SCHWAB_APP_SECRET", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    out = hub.schwab_status()
    assert out["configured"] is False and out["connected"] is False and out["accounts"] == []


def test_schwab_sync_replaces_schwab_account_rows_for_chosen_month(hub, monkeypatch):
    import portfolio_db as pdb

    class FakeConnector:
        def is_connected(self):
            return True

        def get_positions(self, **kw):
            return [{"account_number": "12345678", "position": {
                "instrument": {"symbol": "MSFT", "description": "Microsoft", "assetType": "EQUITY"},
                "longQuantity": 3, "shortQuantity": 0, "averagePrice": 300.0, "marketValue": 900.0}}]

        def merge_holdings_to_portfolio(self, df):
            keep = pdb.db_load_all()
            keep = keep[~((keep["month"] == M) & (keep["year"] == Y) & (keep["account_name"] == "Schwab-1"))]
            return pd.concat([keep, df.drop(columns=["current_value", "account_number"])], ignore_index=True)

    monkeypatch.setattr(hub, "_schwab_connector", lambda: FakeConnector())
    monkeypatch.setattr("components.schwab_data_transformer.get_schwab_account_name", lambda n: "Schwab-1")
    monkeypatch.setattr(pdb, "enrich_holdings", lambda **kw: {"enriched": 0})

    out = hub.schwab_sync(M, Y)

    assert out["synced"] == 1
    stored = _stored()
    schwab = stored[stored["account_name"] == "Schwab-1"]
    assert list(schwab["symbol"]) == ["MSFT"]            # AAPL/CASH replaced
    assert "VTI" in set(stored["symbol"])                # other accounts untouched


# --------------------------------------------------------------------------- Transactions list

def _store_txns(rows):
    from components.transaction_storage import TransactionStorage
    TransactionStorage().store_transactions(pd.DataFrame(rows))


def _t(i, date, account, typ, symbol, amount, name_blank=False):
    return dict(transaction_id=f"t{i}", date=date, account_id=f"acct-{account}", account_name="" if name_blank else account,
                account_type="401K", transaction_type=typ, symbol=symbol, description=f"{typ} {symbol}",
                quantity=1, price=amount, amount=amount, fee=0)


def test_transactions_list_filters_totals_and_choices(hub):
    _store_txns([_t(1, "2026-10-01", "IBM", "BUY", "VTI", 100.0), _t(2, "2026-10-05", "IBM", "DIVIDEND", "VTI", 5.0),
                 _t(3, "2026-09-01", "Capgemini", "SELL", "VXUS", -40.0)])
    out = hub.transactions_list()
    assert out["total"] == 3 and [r["date"] for r in out["rows"]] == ["2026-10-05", "2026-10-01", "2026-09-01"]
    assert out["choices"] == {"accounts": ["Capgemini", "IBM"], "types": ["BUY", "DIVIDEND", "SELL"]}
    assert hub.transactions_list(account="IBM")["total"] == 2
    assert hub.transactions_list(symbol="vx")["rows"][0]["symbol"] == "VXUS"
    assert hub.transactions_list(types=["BUY"])["totals"] == {"BUY": {"count": 1, "amount": 100.0}}
    assert hub.transactions_list(start="2026-10-01", end="2026-10-03")["total"] == 1
    assert hub.transactions_list(account="IBM")["choices"]["accounts"] == ["Capgemini", "IBM"]   # choices ignore filters


def test_transactions_list_labels_blank_account_and_truncates(hub):
    _store_txns([_t(i, f"2026-10-{i:02d}", "X", "BUY", "VTI", 1.0, name_blank=True) for i in range(1, 6)])
    out = hub.transactions_list(limit=2)
    assert out["total"] == 5 and out["truncated"] is True and len(out["rows"]) == 2
    # blank names are backfilled from the account id (Schwab-<last4>) before listing
    assert {r["account"] for r in out["rows"]} == {"Schwab-ct-X"}


def test_transactions_list_empty(hub):
    out = hub.transactions_list()
    assert out["total"] == 0 and out["rows"] == [] and out["choices"] == {"accounts": [], "types": []}
