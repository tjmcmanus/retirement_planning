"""SnapTrade SDK >= 13 has no get_user_account_positions; positions come from get_user_holdings."""
from types import SimpleNamespace
from unittest.mock import Mock

from components.snaptrade_connector import SnapTradeConnector


def _connector(holdings_body):
    c = SnapTradeConnector.__new__(SnapTradeConnector)
    c.credential_manager = Mock()
    c.credential_manager.get_snaptrade_user.return_value = {"user_secret": "s"}
    api = Mock(spec=["get_user_holdings", "list_user_accounts"])
    api.list_user_accounts.return_value = SimpleNamespace(body=[
        {"id": "a1", "name": "IBM 401(K) PLAN", "raw_type": "401K", "institution_name": "Fidelity", "number": "1"}])
    api.get_user_holdings.return_value = SimpleNamespace(body=holdings_body)
    c.client = SimpleNamespace(account_information=api)
    return c


def test_get_holdings_reads_positions_from_get_user_holdings():
    pos = {"symbol": {"symbol": {"raw_symbol": "FGCKX", "description": "Fidelity Growth Company Fund Class K", "type": {"code": "oef"}}},
           "units": 10.0, "price": 50.0, "average_purchase_price": None}
    out = _connector({"positions": [pos], "balances": []}).get_holdings("u", "s")
    assert len(out) == 1
    assert out[0]["account_name"] == "IBM 401(K) PLAN" and out[0]["account_raw_type"] == "401K"


def test_account_with_no_positions_yields_empty_list():
    assert _connector({"positions": [], "balances": []}).get_holdings("u", "s") == []


def test_connection_status_reports_institution_and_raw_type():
    status = _connector({"positions": []}).get_connection_status("u", "s")
    assert status["accounts"][0]["institution"] == "Fidelity"
    assert status["accounts"][0]["type"] == "401K"


# --------------------------------------------------------------------------- activities / transactions

def _activity(i, typ="DIVIDEND", **kw):
    base = {"id": f"act-{i}", "type": typ, "trade_date": f"2026-10-{i:02d}T04:00:00Z",
            "symbol": {"symbol": "VTI", "raw_symbol": "VTI"}, "units": 2.0, "price": 10.0, "amount": 20.0,
            "fee": 0.5, "description": "d", "currency": {"code": "USD"}}
    base.update(kw)
    return base


def test_get_transactions_reads_data_envelope_and_paginates():
    c = _connector({})
    pages = [SimpleNamespace(body={"data": [_activity(1), _activity(2)], "pagination": {"total": 3}}),
             SimpleNamespace(body={"data": [_activity(3)], "pagination": {"total": 3}})]
    c.client.account_information.get_account_activities = Mock(side_effect=pages)
    out = c.get_transactions("u", "s")
    assert [t["id"] for t in out] == ["act-1", "act-2", "act-3"]
    assert out[0]["symbol"] == "VTI" and out[0]["date"] == "2026-10-01" and out[0]["fees"] == 0.5
    assert out[0]["account_name"] == "IBM 401(K) PLAN" and out[0]["account_type"] == "401K"
    assert c.client.account_information.get_account_activities.call_args_list[1].kwargs["offset"] == 2


def test_import_transactions_is_idempotent_and_maps_types(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.chdir(tmp_path)
    c = _connector({})
    acts = [_activity(1, "DIVIDEND"), _activity(2, "EXCHANGEIN"), _activity(3, "TRANSFER"), _activity(4, "REALIZEDGAINLOSS")]
    c.client.account_information.get_account_activities = Mock(
        return_value=SimpleNamespace(body={"data": acts, "pagination": {"total": 4}}))
    assert c.import_transactions("u", "s") == {"fetched": 4, "stored": 4}
    c.import_transactions("u", "s")                       # second sync must not duplicate
    rows = sqlite3.connect("data/transactions.db").execute(
        "select transaction_type, account_name, account_type, substr(transaction_date,1,10) from transactions order by transaction_id").fetchall()
    assert [r[0] for r in rows] == ["DIVIDEND", "EXCHANGE_IN", "DEPOSIT", "REALIZED_GAIN_LOSS"]
    assert rows[0][1:] == ("IBM 401(K) PLAN", "401K", "2026-10-01")
