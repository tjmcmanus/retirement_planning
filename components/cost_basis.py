"""
components/cost_basis.py
========================
Tax-lot cost basis and realized capital gains, computed from stored BUY/SELL transactions.

Pure functions: no database or network access. Lots are rebuilt from the full transaction
history on every call, so results always reflect everything stored.

Rules
-----
- Lots are tracked per (account, symbol). BUY basis = gross amount + fee; SELL proceeds = gross - fee.
- A SELL consumes lots in the order given by ``method`` (FIFO, LIFO, HIFO, LOFO).
- Holding period is long-term when held more than 365 days.
- Options (OCC-style symbols) may be opened short (sell-to-open); closing a short is always
  short-term. Equities cannot go short: a SELL larger than the lots on record is reported as
  ``unmatched`` (basis unknown, e.g. the shares were acquired before the imported history).
- Same-day trades are processed BUYs first.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Callable

METHODS = ("FIFO", "LIFO", "HIFO", "LOFO")
_EPS = 1e-9
OPTION_MULTIPLIER = 100


def is_option(symbol: str) -> bool:
    """Option symbols look like ``"SOFI  260123P00027000"`` (underlying, two spaces, OCC code)."""
    return bool(symbol) and "  " in symbol and len(symbol) > 15


@dataclass
class _Lot:
    date: dt.date
    qty: float
    cost: float          # total remaining basis (long) or net proceeds (short)
    side: str            # "long" | "short"
    seq: int

    @property
    def unit(self) -> float:
        return self.cost / self.qty if self.qty else 0.0


def _picker(method: str) -> Callable[[_Lot], Any]:
    if method == "LIFO":
        return lambda l: (-l.date.toordinal(), -l.seq)
    if method == "HIFO":
        return lambda l: (-l.unit, l.date.toordinal(), l.seq)
    if method == "LOFO":
        return lambda l: (l.unit, l.date.toordinal(), l.seq)
    return lambda l: (l.date.toordinal(), l.seq)


def _date(v: Any) -> dt.date:
    return dt.date.fromisoformat(str(v)[:10])


def compute(trades: list[dict[str, Any]], method: str = "FIFO", today: dt.date | None = None) -> dict[str, list[dict[str, Any]]]:
    """Match ``trades`` into lots.

    Each trade needs: ``date`` (YYYY-MM-DD), ``account``, ``symbol``, ``type`` (BUY/SELL),
    ``quantity``, ``amount`` (gross cash value, positive), ``fee`` and optionally ``price``.

    Returns ``{"open_lots": [...], "realized": [...], "unmatched": [...]}``.
    """
    method = method.upper()
    if method not in METHODS:
        raise ValueError(f"Unknown method {method!r}; choose one of {', '.join(METHODS)}")
    today = today or dt.date.today()
    pick = _picker(method)

    ordered = sorted(
        (t for t in trades if t.get("type") in ("BUY", "SELL") and (t.get("quantity") or 0) > 0 and t.get("symbol")),
        key=lambda t: (str(t["date"])[:10], 0 if t["type"] == "BUY" else 1),
    )

    books: dict[tuple[str, str], list[_Lot]] = {}
    realized: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for seq, t in enumerate(ordered):
        account, symbol = t["account"], t["symbol"]
        qty = float(t["quantity"])
        fee = float(t.get("fee") or 0)
        gross = float(t.get("amount") or 0)
        if not gross:
            gross = qty * float(t.get("price") or 0) * (OPTION_MULTIPLIER if is_option(symbol) else 1)
        is_buy = t["type"] == "BUY"
        total = gross + fee if is_buy else gross - fee
        per_unit = total / qty
        when = _date(t["date"])

        lots = books.setdefault((account, symbol), [])
        closing_side = "short" if is_buy else "long"
        remaining = qty
        for lot in sorted((l for l in lots if l.side == closing_side), key=pick):
            if remaining <= _EPS:
                break
            take = min(lot.qty, remaining)
            lot_value = lot.cost * take / lot.qty
            trade_value = per_unit * take
            if closing_side == "long":
                proceeds, basis = trade_value, lot_value
                term = "long" if (when - lot.date).days > 365 else "short"
            else:
                proceeds, basis = lot_value, trade_value
                term = "short"
            realized.append({
                "account": account, "symbol": symbol, "side": closing_side,
                "acquired": lot.date.isoformat(), "sold": when.isoformat(), "tax_year": when.year,
                "quantity": take, "proceeds": proceeds, "basis": basis, "gain": proceeds - basis,
                "days_held": (when - lot.date).days, "term": term,
            })
            lot.qty -= take
            lot.cost -= lot_value
            remaining -= take
        lots[:] = [l for l in lots if l.qty > _EPS]

        if remaining > _EPS:
            if is_buy or is_option(symbol):
                lots.append(_Lot(when, remaining, per_unit * remaining, "long" if is_buy else "short", seq))
            else:
                unmatched.append({
                    "account": account, "symbol": symbol, "sold": when.isoformat(), "tax_year": when.year,
                    "quantity": remaining, "proceeds": per_unit * remaining,
                })

    open_lots = [
        {"account": account, "symbol": symbol, "side": l.side, "acquired": l.date.isoformat(),
         "quantity": l.qty, "basis": l.cost, "unit_cost": l.unit,
         "days_held": (today - l.date).days, "term": "long" if (today - l.date).days > 365 else "short"}
        for (account, symbol), lots in books.items() for l in lots
    ]
    open_lots.sort(key=lambda r: (r["account"], r["symbol"], r["acquired"]))
    return {"open_lots": open_lots, "realized": realized, "unmatched": unmatched}
