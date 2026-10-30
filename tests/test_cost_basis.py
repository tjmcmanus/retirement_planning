"""Cost-basis engine and Schwab trade conversion."""
import datetime as dt

import pytest

from components import cost_basis
from components.schwab_connector import schwab_trades_to_rows


def T(date, typ, qty, amount, fee=0.0, symbol="VTI", account="Acct"):
    return {"date": date, "account": account, "symbol": symbol, "type": typ,
            "quantity": qty, "amount": amount, "fee": fee, "price": amount / qty}


def test_fifo_splits_lots_and_term():
    trades = [T("2020-01-01", "BUY", 10, 1000), T("2021-06-01", "BUY", 10, 2000), T("2021-07-01", "SELL", 15, 4500)]
    r = cost_basis.compute(trades, "FIFO")
    first, second = r["realized"]
    assert (first["quantity"], first["basis"], first["term"]) == (10, 1000, "long")   # >365 days
    assert (second["quantity"], second["basis"], second["term"]) == (5, 1000, "short")
    assert sum(x["gain"] for x in r["realized"]) == pytest.approx(4500 - 2000)
    assert r["open_lots"][0]["quantity"] == 5 and r["open_lots"][0]["basis"] == pytest.approx(1000)


def test_methods_pick_different_lots():
    trades = [T("2020-01-01", "BUY", 1, 100), T("2020-02-01", "BUY", 1, 300), T("2020-03-01", "BUY", 1, 200),
              T("2020-04-01", "SELL", 1, 250)]
    basis = {m: cost_basis.compute(trades, m)["realized"][0]["basis"] for m in cost_basis.METHODS}
    assert basis == {"FIFO": 100, "LIFO": 200, "HIFO": 300, "LOFO": 100}


def test_fees_adjust_basis_and_proceeds():
    r = cost_basis.compute([T("2022-01-03", "BUY", 10, 1000, fee=1), T("2022-02-01", "SELL", 10, 1200, fee=2)])
    row = r["realized"][0]
    assert row["basis"] == 1001 and row["proceeds"] == 1198 and row["gain"] == 197


def test_sell_without_history_is_unmatched():
    r = cost_basis.compute([T("2022-01-03", "SELL", 5, 500)])
    assert r["realized"] == [] and r["unmatched"][0]["quantity"] == 5


def test_accounts_are_separate():
    r = cost_basis.compute([T("2022-01-01", "BUY", 5, 500, account="A"), T("2022-02-01", "SELL", 5, 600, account="B")])
    assert r["unmatched"] and not r["realized"]


def test_short_option_closed_is_short_term():
    sym = "SOFI  260123P00027000"
    r = cost_basis.compute([T("2025-01-02", "SELL", 1, 100, symbol=sym), T("2026-06-01", "BUY", 1, 30, symbol=sym)])
    row = r["realized"][0]
    assert row["side"] == "short" and row["gain"] == 70 and row["term"] == "short"
    assert r["open_lots"] == [] and r["unmatched"] == []


def test_unknown_method_rejected():
    with pytest.raises(ValueError):
        cost_basis.compute([], "BOGUS")


def _activity(items, **kw):
    return {"activityId": 99, "tradeDate": "2025-05-01", "accountNumber": "12345678", "netAmount": -1001.0,
            "transferItems": items, **kw}


def test_schwab_rows_fold_fees_and_use_unique_ids():
    items = [
        {"instrument": {"symbol": "VTI", "assetType": "ETF"}, "amount": 10, "price": 100.0, "cost": -1000.0, "positionEffect": "OPENING"},
        {"instrument": {"symbol": "CURRENCY_USD", "assetType": "CURRENCY"}, "amount": 0, "cost": -0.63, "feeType": "SEC_FEE"},
        {"instrument": {"symbol": "CURRENCY_USD", "assetType": "CURRENCY"}, "amount": 0, "cost": -0.37, "feeType": "TAF_FEE"},
        {"instrument": {"symbol": "CURRENCY_USD", "assetType": "CURRENCY"}, "amount": 0, "cost": 0},
    ]
    rows = schwab_trades_to_rows([_activity(items)], "hash")
    assert len(rows) == 1
    r = rows[0]
    assert r["transaction_id"] == "99:VTI" and r["transaction_type"] == "BUY"
    assert r["quantity"] == 10 and r["amount"] == 1000.0 and r["fee"] == pytest.approx(1.0)
    assert r["account_name"].endswith("5678")


def test_schwab_sell_and_multi_item_ids_do_not_collide():
    items = [
        {"instrument": {"symbol": "AAA", "assetType": "EQUITY"}, "amount": -2, "price": 10.0, "cost": 20.0},
        {"instrument": {"symbol": "BBB", "assetType": "EQUITY"}, "amount": 3, "price": 5.0, "cost": -15.0},
    ]
    rows = schwab_trades_to_rows([_activity(items)], "hash")
    assert {(r["transaction_id"], r["transaction_type"]) for r in rows} == {("99:AAA", "SELL"), ("99:BBB", "BUY")}


def test_schwab_currency_only_activity_is_skipped():
    items = [{"instrument": {"symbol": "CURRENCY_USD", "assetType": "CURRENCY"}, "amount": 0, "cost": 0}]
    assert schwab_trades_to_rows([_activity(items)], "hash") == []
