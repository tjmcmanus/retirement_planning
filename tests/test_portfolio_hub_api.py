"""API tests for the Portfolio Hub endpoints. Skipped where FastAPI is unusable (see test_api.py).

Run inside the container image:
    podman run --rm --entrypoint sh -v "$PWD/tests:/app/tests:ro" localhost/retirement-planning:local \
        -c "pip install -q --user pytest httpx && cd /tmp && python -m pytest -q -p no:cacheprovider -o addopts= /app/tests/test_portfolio_hub_api.py"
"""
import shutil
from pathlib import Path

import pandas as pd
import pytest

try:
    from fastapi.testclient import TestClient
    import app.main as main_module
except Exception as exc:
    pytest.skip(f"FastAPI not usable here: {exc}", allow_module_level=True)

REPO = Path(__file__).resolve().parent.parent
M, Y = 10, 2026


def _row(account, symbol, qty, price, **kw):
    base = dict(month=M, year=Y, account_name=account, account_type="Brokerage", owner="Joint",
                symbol=symbol, name=symbol, sector="Technology", qty=qty, purchase_price=price,
                purchase_date="2020-01-15")
    base.update(kw)
    return base


def _body(rows, month=M, year=Y):
    return {"month": month, "year": year,
            "rows": [{**{k: v for k, v in r.items() if k not in ("month", "year")}, "rid": i + 1} for i, r in enumerate(rows)]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copy(REPO / "retirement_config.json.example", tmp_path / "retirement_config.json")
    import app_cache
    import config
    import portfolio_data_entry as pde
    import portfolio_db as pdb

    pdb._tls.conns = {}
    app_cache.clear_all()
    config.reload_config()
    monkeypatch.setattr(pde, "_trigger_portfolio_cache_rebuild", lambda df: None)
    monkeypatch.setattr(pde, "validate_ticker_symbol", lambda s: (True, f"{s} Inc", "Technology", ""))
    pdb.db_upsert(pd.DataFrame([_row("Schwab-1", "AAPL", 10, 100.0), _row("IRA", "VTI", 5, 200.0, account_type="Traditional")]))
    with TestClient(main_module.app, base_url="http://localhost") as c:
        yield c
    pdb._tls.conns = {}


def test_portfolio_page_served_and_nav_links_to_it(client):
    html = client.get("/portfolio").text
    assert 'id="main-nav"' in html and "grid-holdings" in html
    assert "http://" not in html and "https://" not in html
    assert client.get("/static/portfolio.js").status_code == 200
    assert 'label: "Portfolio", href: "/portfolio"' in client.get("/static/nav.js").text


def test_meta_and_holdings_get(client):
    meta = client.get("/api/portfolio/meta").json()
    assert {"month": M, "year": Y, "rows": 2} in meta["periods"]
    rows = client.get("/api/portfolio/holdings", params={"month": M, "year": Y}).json()["rows"]
    assert {r["symbol"] for r in rows} == {"AAPL", "VTI"}


@pytest.mark.parametrize("params", [{"month": 13, "year": 2026}, {"month": 0, "year": 2026}, {"month": 1, "year": 1999}, {}])
def test_holdings_get_rejects_bad_period(client, params):
    assert client.get("/api/portfolio/holdings", params=params).status_code == 422


def test_put_holdings_roundtrip(client):
    body = _body([_row("Schwab-1", "AAPL", 12, 100.0), _row("IRA", "BND", 3, 80.0, account_type="Traditional")])
    r = client.put("/api/portfolio/holdings", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["added"], out["updated"], out["removed"]) == (1, 1, 1)
    assert {x["symbol"] for x in out["rows"]} == {"AAPL", "BND"}
    again = client.get("/api/portfolio/holdings", params={"month": M, "year": Y}).json()["rows"]
    assert {x["symbol"]: x["qty"] for x in again} == {"AAPL": 12, "BND": 3}


def test_put_holdings_422_lists_row_errors_and_writes_nothing(client):
    body = _body([_row("A", "AAPL", 1, 1.0), _row("A", "IBM", 0, 1.0)])
    r = client.put("/api/portfolio/holdings", json=body)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["errors"][0]["rid"] == 2 and "zero" in detail["errors"][0]["message"].lower()
    assert len(client.get("/api/portfolio/holdings", params={"month": M, "year": Y}).json()["rows"]) == 2


def test_put_holdings_refuses_empty_list(client):
    r = client.put("/api/portfolio/holdings", json={"month": M, "year": Y, "rows": []})
    assert r.status_code == 422 and "empty" in r.json()["detail"]["message"].lower()
    assert len(client.get("/api/portfolio/holdings", params={"month": M, "year": Y}).json()["rows"]) == 2


def test_put_holdings_rejects_bad_body(client):
    assert client.put("/api/portfolio/holdings", json={"month": 99, "year": Y, "rows": []}).status_code == 422
    assert client.put("/api/portfolio/holdings", json={"rows": []}).status_code == 422


def test_validate_endpoint(client):
    r = client.post("/api/portfolio/holdings/validate", json=_body([_row("A", "AAPL", 1, 1.0), _row("A", "IBM", -1, 1.0)]))
    assert r.status_code == 200
    assert [e["rid"] for e in r.json()["errors"]] == [2]


def test_copy_previous_404_then_ok(client):
    assert client.post("/api/portfolio/holdings/copy-previous", json={"month": M, "year": Y}).status_code == 404
    client.put("/api/portfolio/holdings", json=_body([_row("A", "AAPL", 1, 1.0, month=9)], month=9))
    r = client.post("/api/portfolio/holdings/copy-previous", json={"month": M, "year": Y})
    assert r.status_code == 200 and r.json()["from"] == {"month": 9, "year": Y}


def test_import_csv_and_errors(client):
    ok = client.post("/api/portfolio/holdings/import", json={
        "month": M, "year": Y,
        "csv": "account_name,account_type,symbol,qty,purchase_price\nAcct,Roth,VTI,2,50\n"})
    assert ok.status_code == 200 and ok.json()["rows"][0]["symbol"] == "VTI"
    bad = client.post("/api/portfolio/holdings/import", json={"month": M, "year": Y, "csv": "a,b\n1,2\n"})
    assert bad.status_code == 422 and "missing required columns" in bad.json()["detail"]
    too_big = client.post("/api/portfolio/holdings/import", json={"month": M, "year": Y, "csv": "x" * 2_000_001})
    assert too_big.status_code == 422


def test_backup_endpoint_writes_file(client):
    r = client.post("/api/portfolio/holdings/backup")
    assert r.status_code == 200 and r.json()["rows"] == 2 and list(Path(".backups").glob("portfolio_data_truth_backup_*.csv"))


def test_lookup_endpoint(client):
    assert client.get("/api/portfolio/lookup", params={"symbol": "aapl"}).json()["symbol"] == "AAPL"
    assert client.get("/api/portfolio/lookup", params={"symbol": "  "}).status_code == 422
    assert client.get("/api/portfolio/lookup").status_code == 422


def test_cross_origin_write_rejected(client):
    r = client.put("/api/portfolio/holdings", json=_body([_row("A", "AAPL", 1, 1.0)]), headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert len(client.get("/api/portfolio/holdings", params={"month": M, "year": Y}).json()["rows"]) == 2
