"""Streamlit-free data for the Portfolio Hub page: the Overview tab and the Holdings editor.

Mirrors ``components/portfolio_overview.py`` and ``components/portfolio_holdings_editor.py``.
Those import Streamlit, so the logic is reimplemented here on top of the Streamlit-free engine
modules (``portfolio``, ``portfolio_db``, ``portfolio_data_entry``, ``portfolio_market_indicators``).

Deliberate differences from the Streamlit editor (all in the Holdings tab):
  * Save replaces the selected month with exactly the rows sent. Streamlit upserts, so a row
    deleted in its grid stays in the database. A copy of the month is written to ``.backups/``
    first, and an empty list is refused so a bad client cannot wipe a month.
  * month/year are not editable per row; every row belongs to the selected period.
  * Duplicate (account, symbol) rows are an error. The database key would otherwise silently
    keep only one of them.
"""
from __future__ import annotations

import datetime as dt
import io
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

import app_cache
import load_data
import portfolio as pf
import portfolio_data_entry as pde
import portfolio_db as pdb
import portfolio_market_indicators as pmi
from app.services import dashboard
from app.services import networth as nw_service

logger = logging.getLogger(__name__)

COLUMNS = ["account_name", "account_type", "owner", "symbol", "name", "sector",
           "qty", "purchase_price", "purchase_date"]
_CSV_REQUIRED = ["account_name", "account_type", "symbol", "qty", "purchase_price"]
_write_lock = threading.Lock()

BENCHMARK_ANNUAL_RATE = 0.07


class HoldingsValidationError(ValueError):
    """Per-row problems: ``[{"rid", "row", "label", "message"}]``. Nothing was written."""

    def __init__(self, errors: list[dict[str, Any]], message: str = "Invalid holdings"):
        super().__init__(message)
        self.errors = errors
        self.message = message


def _today() -> tuple[int, int]:
    d = dt.date.today()
    return d.month, d.year


def _f(v: Any) -> float:
    return float(v) if v is not None and pd.notna(v) else 0.0


def _pct(change: float, base: float) -> float:
    return (change / base * 100.0) if base else 0.0


# --------------------------------------------------------------------------------------
# Periods and metadata
# --------------------------------------------------------------------------------------

def meta() -> dict[str, Any]:
    cur_m, cur_y = _today()
    eff_m, eff_y = pf.get_effective_portfolio_month_year(cur_m, cur_y)
    rows = pdb.get_db_connection().execute(
        "SELECT year, month, COUNT(*) AS n FROM holdings GROUP BY year, month ORDER BY year DESC, month DESC"
    ).fetchall()
    return {
        "current": {"month": cur_m, "year": cur_y},
        "effective": {"month": eff_m, "year": eff_y},
        "stale": dashboard._stale(cur_m, cur_y, eff_m, eff_y),
        "periods": [{"month": int(r["month"]), "year": int(r["year"]), "rows": int(r["n"])} for r in rows],
        "account_types": list(pde.VALID_ACCOUNT_TYPES),
        "owners": pde.get_valid_account_owners(),
        "sectors": list(pde.VALID_SECTORS),
        "stale_sectors": sorted(pdb._STALE_SECTORS),
    }


# --------------------------------------------------------------------------------------
# Overview tab
# --------------------------------------------------------------------------------------

def _tax_efficiency(nw: pd.DataFrame) -> dict[str, Any]:
    if nw.empty:
        trad = roth = brok = cash = 0.0
    else:
        last = nw.iloc[-1]
        trad, roth = _f(last["tax_deferred"]), _f(last["tax_free"])
        brok, cash = _f(last["taxable"]), _f(last["cash"])
    total = trad + roth + brok + cash
    score = ((roth + brok) / total * 100) if total > 0 else 0.0
    roth_ratio = (roth / (roth + trad) * 100) if (roth + trad) > 0 else 0.0
    label = "Excellent" if score >= 60 else ("Good" if score >= 40 else "Improve")

    recs: list[dict[str, str]] = []
    if score < 60:
        recs.append({"title": f"Tax Efficiency Score is {score:.0f}% (target: 60%+)",
                     "detail": f"Increase tax-flexible assets by {60 - score:.0f} percentage points."})
    if roth_ratio < 30:
        gap = max(0.0, (trad + roth) * 0.30 - roth)
        recs.append({"title": f"Low Roth Ratio ({roth_ratio:.0f}%)",
                     "detail": f"Consider Roth conversions. Target: convert ~${gap:,.0f} to reach a 30% Roth ratio "
                               "(optimal range: 30-50%)."})
    elif roth_ratio > 50:
        recs.append({"title": f"High Roth Ratio ({roth_ratio:.0f}%)",
                     "detail": "You may have too much in Roth accounts. Consider increasing Traditional 401(k)/IRA "
                               "contributions to balance tax diversification."})
    if total > 0 and brok < total * 0.10:
        recs.append({"title": f"Low Taxable Brokerage ({brok / total * 100:.0f}%)",
                     "detail": f"Consider building taxable brokerage to ${total * 0.10:,.0f} (10% of portfolio) "
                               "for tax-loss harvesting and flexible withdrawals."})
    if total > 0 and trad > total * 0.60:
        recs.append({"title": f"High Traditional Balance ({trad / total * 100:.0f}%)",
                     "detail": "Large Traditional balances create RMD risk at age 73. Consider strategic Roth "
                               "conversions during low-income years."})
    return {"score": score, "label": label, "roth_ratio": roth_ratio, "traditional": trad, "roth": roth,
            "taxable": brok, "cash": cash, "total": total, "recommendations": recs}


def overview() -> dict[str, Any]:
    """Everything on the Overview tab except the holdings treemap (that needs live prices)."""
    cur_m, cur_y = _today()
    eff_m, eff_y = pf.get_effective_portfolio_month_year(cur_m, cur_y)
    nw = nw_service.load_networth_history()
    has = not nw.empty

    total = _f(nw["total"].iloc[-1]) if has else 0.0
    mom = mom_pct = ytd = ytd_pct = 0.0
    if len(nw) >= 2:
        prev = _f(nw["total"].iloc[-2])
        mom, mom_pct = total - prev, _pct(total - prev, prev)
    if has:
        in_year = pd.DatetimeIndex(nw.index).year == cur_y
        if in_year.any():
            start = _f(nw["total"][in_year].iloc[0])
            ytd, ytd_pct = total - start, _pct(total - start, start)

    tax = _tax_efficiency(nw)
    out: dict[str, Any] = {
        "stale": dashboard._stale(cur_m, cur_y, eff_m, eff_y),
        "kpis": {
            "total_value": total,
            "month_change": {"amount": mom, "percent": mom_pct},
            "ytd": {"amount": ytd, "percent": ytd_pct},
            "tax_efficiency": {"score": tax["score"], "label": tax["label"]},
        },
        "tax": tax,
        "history": None, "mix": None, "performance": None,
    }
    if not has:
        return out

    idx = [d.strftime("%Y-%m-%d") for d in pd.DatetimeIndex(nw.index)]
    out["history"] = {
        "labels": idx,
        "traditional": [_f(v) for v in nw["tax_deferred"]], "roth": [_f(v) for v in nw["tax_free"]],
        "taxable": [_f(v) for v in nw["taxable"]], "cash": [_f(v) for v in nw["cash"]],
    }
    out["mix"] = {"labels": ["Cash", "Broker", "Traditional", "Roth"],
                  "values": [tax["cash"], tax["taxable"], tax["traditional"], tax["roth"]]}
    if len(nw) >= 2:
        first = _f(nw["total"].iloc[0])
        rate = BENCHMARK_ANNUAL_RATE / 12
        bench = [first * ((1 + rate) ** i) for i in range(len(nw))]
        vs = total - bench[-1]
        out["performance"] = {"labels": idx, "portfolio": [_f(v) for v in nw["total"]], "benchmark": bench,
                              "vs_amount": vs, "vs_percent": _pct(vs, bench[-1]),
                              "benchmark_rate": BENCHMARK_ANNUAL_RATE}
    return out


def treemap() -> dict[str, Any]:
    """Tax Type > Sector > Ticker treemap of current holdings (live prices, so it can be slow)."""
    cur_m, cur_y = _today()
    eff_m, eff_y = pf.get_effective_portfolio_month_year(cur_m, cur_y)
    stale = dashboard._stale(cur_m, cur_y, eff_m, eff_y)
    port = dashboard._portfolio_frame(eff_m, eff_y)
    if port.empty:
        return {"ready": False, "stale": stale, "reason": "No holdings to display."}
    port = port[port["Account"] != "Portfolio Totals"].copy()
    for col in ("Tax Type", "Sector", "Ticker"):
        port[col] = port[col].fillna("Unknown")
    port = port[port["Current value"].notna() & (port["Current value"] != 0)]
    if port.empty:
        return {"ready": False, "stale": stale, "reason": "No holdings to display."}
    positive = port[port["Current value"] > 0]
    if positive.empty:
        return {"ready": False, "stale": stale,
                "reason": "No holdings with positive value to display. Options contracts require manual "
                          "price entry in the purchase_price field."}
    rows = [((str(r["Tax Type"]), str(r["Sector"]), str(r["Ticker"])), float(r["Current value"]))
            for _, r in positive.iterrows()]
    return {"ready": True, "stale": stale, "excluded": len(port) - len(positive), **dashboard.treemap_nodes(rows)}


# --------------------------------------------------------------------------------------
# Holdings: read
# --------------------------------------------------------------------------------------

def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Rows as JSON-safe dicts (NaN -> None, dates -> YYYY-MM-DD strings)."""
    out = []
    for _, r in df.iterrows():
        rec: dict[str, Any] = {}
        for c in COLUMNS:
            v = r.get(c)
            if c in ("qty", "purchase_price"):
                rec[c] = float(v) if v is not None and pd.notna(v) else None
            else:
                rec[c] = "" if v is None or pd.isna(v) else str(v)
        if rec["purchase_date"]:
            rec["purchase_date"] = rec["purchase_date"][:10]
        if not rec["owner"].strip():
            rec["owner"] = "Joint"
        out.append(rec)
    return out


def list_holdings(month: int, year: int) -> dict[str, Any]:
    return {"month": month, "year": year, "rows": _records(pdb.db_get_by_month(month, year))}


def copy_previous(month: int, year: int) -> dict[str, Any]:
    """Previous month's rows, re-dated to ``month``/``year``. Not saved."""
    pm, py = (month - 1, year) if month > 1 else (12, year - 1)
    prev = pdb.db_get_by_month(pm, py)
    if prev.empty:
        raise LookupError(f"No data found for {pm}/{py}")
    return {"month": month, "year": year, "from": {"month": pm, "year": py}, "rows": _records(prev)}


def import_csv(text: str, month: int, year: int) -> dict[str, Any]:
    """Parse an uploaded CSV into grid rows (not saved). Every row is assigned to month/year."""
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as exc:
        raise ValueError(f"Could not read the CSV: {exc}") from exc
    missing = [c for c in _CSV_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    warnings = []
    if {"month", "year"} <= set(df.columns):
        other = int(((df["month"] != month) | (df["year"] != year)).sum())
        if other:
            warnings.append(f"{other} row(s) had a different month/year in the file; "
                            f"all rows were assigned to {month}/{year}.")
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = None
    return {"month": month, "year": year, "rows": _records(df), "warnings": warnings}


# --------------------------------------------------------------------------------------
# Holdings: validate and save
# --------------------------------------------------------------------------------------

def _s(v: Any) -> str:
    return "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v).strip()


def _clean(rows: list[dict[str, Any]], month: int, year: int) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Normalise the submitted rows and validate each one. Returns (frame, errors)."""
    errors: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], int] = {}
    for i, raw in enumerate(rows):
        rec = {
            "month": month, "year": year,
            "account_name": _s(raw.get("account_name")), "account_type": _s(raw.get("account_type")),
            "owner": _s(raw.get("owner")) or "Joint", "symbol": _s(raw.get("symbol")),
            "name": _s(raw.get("name")), "sector": _s(raw.get("sector")),
            "qty": pd.to_numeric(raw.get("qty"), errors="coerce"),
            "purchase_price": pd.to_numeric(raw.get("purchase_price"), errors="coerce"),
            "purchase_date": _s(raw.get("purchase_date")),
        }
        label = f"{rec['account_name'] or '(no account)'} / {rec['symbol'] or '(no symbol)'}"

        def add(msg: str) -> None:
            errors.append({"rid": raw.get("rid"), "row": i + 1, "label": label, "message": msg})

        ok, msg = pde.validate_portfolio_entry(pd.Series(rec))
        if not ok:
            add(msg)
        if rec["purchase_date"]:
            # ISO only: "01/02/2020" is ambiguous and pandas would silently guess a reading.
            parsed = pd.to_datetime(rec["purchase_date"], format="ISO8601", errors="coerce")
            if pd.isna(parsed):
                add(f"Invalid purchase_date: {rec['purchase_date']!r} (use YYYY-MM-DD)")
            else:
                rec["purchase_date"] = parsed.strftime("%Y-%m-%d")
        key = (rec["account_name"], rec["symbol"])
        if rec["account_name"] and rec["symbol"]:
            if key in seen:
                add(f"Duplicate holding: {label} already appears in row {seen[key]}")
            else:
                seen[key] = i + 1
        records.append(rec)
    return pd.DataFrame(records), errors


def _lookup_symbol(symbol: str) -> dict[str, Any]:
    valid, name, sector, error = pde.validate_ticker_symbol(symbol)
    price = None
    if valid:
        try:
            p = float(pf.get_current_price(symbol))
            price = p if p > 0 else None
        except Exception:
            logger.debug("Price lookup failed for %s", symbol, exc_info=True)
    return {"symbol": symbol, "valid": bool(valid), "name": name, "sector": sector, "price": price,
            "error": error or None}


def lookup(symbol: str) -> dict[str, Any]:
    sym = symbol.strip().upper()
    if not sym:
        raise ValueError("Enter a ticker symbol")
    return _lookup_symbol(sym)


def validate(rows: list[dict[str, Any]], month: int, year: int) -> dict[str, Any]:
    """Row errors plus Yahoo Finance ticker warnings (one lookup per distinct symbol)."""
    df, errors = _clean(rows, month, year)
    warnings: list[dict[str, Any]] = []
    # Digit-leading symbols are cash-balance rows (the editor treats them that way); skip Yahoo for them.
    syms = sorted({s.upper() for s in df["symbol"] if s and s.upper() not in pf.CASH_SYMBOLS and not s[0].isdigit()}) \
        if not df.empty else []
    with ThreadPoolExecutor(max_workers=8) as pool:
        found = dict(zip(syms, pool.map(lambda s: pde.validate_ticker_symbol(s), syms)))
    for i, raw in enumerate(rows):
        sym = df["symbol"].iloc[i].upper() if not df.empty else ""
        if sym not in found:
            continue
        valid, name, sector, err = found[sym]
        label = f"{df['account_name'].iloc[i] or '(no account)'} / {df['symbol'].iloc[i]}"
        if not valid:
            msg = err
        elif not df["name"].iloc[i] or not df["sector"].iloc[i]:
            msg = f"Symbol '{sym}' found but name/sector not filled. Suggested: {name} / {sector}"
        else:
            continue
        warnings.append({"rid": raw.get("rid"), "row": i + 1, "label": label, "message": msg})
    return {"errors": errors, "warnings": warnings, "rows": len(rows)}


def invalidate_caches() -> None:
    """Drop every cached view of the holdings so the next read sees the database."""
    app_cache.clear_all()
    for name in (pf.PORTFOLIO_CACHE_FILE, load_data.NETWORTH_CACHE_FILE):
        try:
            os.remove(name)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("Could not remove cache file %s", name, exc_info=True)


def _warm_cache(df: pd.DataFrame) -> None:
    """Rebuild the portfolio display cache in the background (live prices)."""
    pde._trigger_portfolio_cache_rebuild(df)


def _backup_dir() -> Path:
    d = Path(".backups")
    d.mkdir(exist_ok=True)
    return d


def _count_changed(old: pd.DataFrame, new: pd.DataFrame) -> int:
    """Rows present in both frames (same account + symbol) whose editable fields differ."""
    if old.empty or new.empty:
        return 0
    text = ["account_type", "owner", "name", "sector"]
    num = ["qty", "purchase_price"]
    o = old.set_index(["account_name", "symbol"])
    n = new.set_index(["account_name", "symbol"])
    changed = 0
    for key in n.index.intersection(o.index):
        a, b = o.loc[key], n.loc[key]
        if (any(_s(a[c]) != _s(b[c]) for c in text)
                or any(abs(_f(a[c]) - _f(b[c])) > 1e-9 for c in num)
                or _s(a["purchase_date"])[:10] != _s(b["purchase_date"])[:10]):
            changed += 1
    return changed


def save_holdings(rows: list[dict[str, Any]], month: int, year: int) -> dict[str, Any]:
    """Replace ``month``/``year`` with exactly ``rows``. Validates everything first; writes nothing on error."""
    if not rows:
        raise HoldingsValidationError([], "Refusing to save an empty list: that would delete every holding "
                                          f"for {month}/{year}.")
    df, errors = _clean(rows, month, year)
    if errors:
        raise HoldingsValidationError(errors, f"{len(errors)} problem(s) found; nothing was saved.")

    with _write_lock:
        existing = pdb.db_get_by_month(month, year)
        backup_name = None
        if not existing.empty:
            backup_name = f"portfolio_holdings_{year}-{month:02d}_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
            existing.to_csv(_backup_dir() / backup_name, index=False)

        # Keep stored end-of-month prices for holdings that still exist (the overwrite would drop them).
        eom = {(r.account_name, r.symbol): r.end_of_month_price for r in existing.itertuples()}
        df["end_of_month_price"] = pd.Series(
            [eom.get((a, s)) for a, s in zip(df["account_name"], df["symbol"])], dtype="float64")

        old_keys = set(eom)
        new_keys = set(zip(df["account_name"], df["symbol"]))
        updated = _count_changed(existing, df)

        n = pdb.db_overwrite_month(month, year, df)
        invalidate_caches()

    _warm_cache(df)
    return {"month": month, "year": year, "saved": n, "added": len(new_keys - old_keys),
            "removed": len(old_keys - new_keys), "updated": updated, "backup": backup_name,
            "rows": _records(pdb.db_get_by_month(month, year))}


# --------------------------------------------------------------------------------------
# Holdings: tools
# --------------------------------------------------------------------------------------

def backup_all() -> dict[str, Any]:
    df = pdb.db_load_all()
    name = f"portfolio_data_truth_backup_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
    df.to_csv(_backup_dir() / name, index=False)
    return {"file": f".backups/{name}", "rows": len(df)}


def enrich(month: int, year: int) -> dict[str, Any]:
    """Fill blank names and stale sectors from Yahoo Finance (writes to the database)."""
    with _write_lock:
        result = pdb.enrich_holdings(month=month, year=year)
        if result["enriched"]:
            invalidate_caches()
    return result


def _indicator_row(symbol: str) -> dict[str, Any] | None:
    try:
        ind = pmi.calculate_security_indicator(symbol)
    except Exception:
        logger.debug("Indicator failed for %s", symbol, exc_info=True)
        return None
    if ind is None:
        return None
    return {"label": ind.condition.value.replace("_", " ").title(), "condition": ind.condition.value,
            "recommendation": ind.recommendation, "price": float(ind.current_price),
            "short_ma": float(ind.short_ma), "long_ma": float(ind.long_ma),
            "short_trend": ind.short_trend, "long_trend": ind.long_trend, "confidence": float(ind.confidence)}


def indicators(month: int, year: int) -> dict[str, Any]:
    """Market indicator (10/50-week moving averages) per distinct symbol. Slow on a cold cache."""
    df = pdb.db_get_by_month(month, year)
    symbols = sorted({str(s) for s in df["symbol"].dropna() if str(s).strip()})
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(symbols, pool.map(_indicator_row, symbols)))
    return {"month": month, "year": year, "indicators": results}


# --------------------------------------------------------------------------------------
# Rebalancing
# --------------------------------------------------------------------------------------

def rebalancing_defaults() -> dict[str, Any]:
    """Return saved target allocation (if any) and bucket-strategy-derived defaults."""
    from components.rebalancing_cache import get_target_allocation
    saved = get_target_allocation()

    # Derive smart defaults from bucket strategy config when available
    default_cash, default_bonds, default_stocks, default_threshold = 10.0, 10.0, 80.0, 5.0
    try:
        from config import get_config_manager
        from bucket_strategy import load_bucket_config
        from app.services.networth import load_networth_history
        cfg = get_config_manager()
        if cfg.get("bucket_strategy", "enabled", False):
            bc = load_bucket_config(cfg)
            nw = load_networth_history()
            total = float(nw["total"].iloc[-1]) if not nw.empty else 0.0
            if total > 0:
                annual_need = bc.annual_expenses + bc.annual_taxes
                b1 = annual_need * bc.bucket_1_years
                b2 = annual_need * bc.bucket_2_years
                b3 = max(0.0, total - b1 - b2)
                avg_s2 = (bc.bucket_2_start_stock_pct + bc.bucket_2_end_stock_pct) / 2
                avg_b2 = 100 - avg_s2
                default_cash   = max(0, min(100, round(100 * b1 / total)))
                default_bonds  = max(0, min(100, round(avg_b2 * b2 / total)))
                default_stocks = max(0, 100 - default_cash - default_bonds)
    except Exception:
        pass

    return {
        "saved": saved,
        "defaults": {
            "cash_pct": default_cash,
            "bonds_pct": default_bonds,
            "stocks_pct": default_stocks,
            "drift_threshold_pct": default_threshold,
        },
    }


def rebalance(
    target_cash_pct: float,
    target_bonds_pct: float,
    target_stocks_pct: float,
    drift_threshold_pct: float,
    save_targets: bool = False,
) -> dict[str, Any]:
    """Compute a rebalancing plan and optionally persist the target allocation."""
    from portfolio_rebalancing import compute_rebalance_plan

    cur_m, cur_y = _today()
    eff_m, eff_y = pf.get_effective_portfolio_month_year(cur_m, cur_y)

    report = compute_rebalance_plan(
        month=eff_m,
        year=eff_y,
        target_cash_pct=target_cash_pct,
        target_bonds_pct=target_bonds_pct,
        target_stocks_pct=target_stocks_pct,
        drift_threshold_pct=drift_threshold_pct,
    )

    if save_targets:
        from components.rebalancing_cache import set_target_allocation
        set_target_allocation(
            cash_pct=target_cash_pct,
            bonds_pct=target_bonds_pct,
            stocks_pct=target_stocks_pct,
            drift_threshold_pct=drift_threshold_pct,
        )

    # Serialise asset summary
    summary = [
        {
            "asset_class": s.asset_class,
            "current_value": s.current_value,
            "current_pct": round(s.current_pct, 2),
            "target_pct": round(s.target_pct, 2),
            "drift_pct": round(s.drift_pct, 2),
            "is_drifted": s.is_drifted,
            "delta_value": round(s.delta_value, 2),
        }
        for s in report.asset_summary
    ]

    # Serialise action list
    actions = [
        {
            "priority": a.priority,
            "action": a.action,
            "asset_class": a.asset_class,
            "symbol": a.symbol,
            "account": f"{a.account_name} ({a.account_type})",
            "account_name": a.account_name,
            "account_type": a.account_type,
            "amount": round(a.amount, 2),
            "tax_impact": a.tax_impact,
            "rationale": a.rationale,
            "location_note": a.location_note,
        }
        for a in report.actions
    ]

    return {
        "total_portfolio_value": report.total_portfolio_value,
        "drift_triggered": report.drift_triggered,
        "drift_threshold_pct": report.drift_threshold_pct,
        "target_weights": report.target_weights,
        "brokerage_cash_pct": round(report.brokerage_cash_pct, 2),
        "brokerage_cash_ok": report.brokerage_cash_ok,
        "location_issues": report.location_issues,
        "summary": summary,
        "actions": actions,
        "period": {"month": eff_m, "year": eff_y},
    }


# --------------------------------------------------------------------------------------
# Optimize (Tax Harvesting + Direct Indexing)
# --------------------------------------------------------------------------------------

def optimize(
    agi: float,
    marginal_rate_pct: float,
    loss_threshold: float,
    gain_threshold: float,
    drop_trigger_pct: float,
) -> dict[str, Any]:
    """
    Full harvest-opportunity scan for the current effective portfolio period.

    Returns KPIs, per-holding rows with recommendations, wash-sale replacements,
    market-drop trigger status, and estimated tax impact.
    """
    from tax_harvesting import (
        build_harvesting_analysis,
        classify_harvest_opportunities,
        compute_harvest_summary,
        compute_net_tax_impact,
        check_market_drop_trigger,
        get_ltcg_rate_for_income,
        get_ltcg_zero_threshold,
        get_replacement_detail,
    )
    import datetime as _dt

    cur_m, cur_y = _today()
    eff_m, eff_y = pf.get_effective_portfolio_month_year(cur_m, cur_y)
    year = cur_y

    # ── 1. Build base analysis ────────────────────────────────────────────────
    analysis = build_harvesting_analysis(eff_m, eff_y)

    ltcg_rate    = get_ltcg_rate_for_income(float(agi), year)
    zero_thresh  = get_ltcg_zero_threshold(year)
    headroom     = max(0.0, zero_thresh - float(agi))

    ltcg_kpis = {
        "ltcg_rate": ltcg_rate,
        "zero_threshold": zero_thresh,
        "headroom_to_zero": headroom,
        "strategy": (
            "Harvest Gains (0% rate)" if ltcg_rate == 0.0
            else ("Harvest Losses" if ltcg_rate == 0.15 else "Harvest Losses (High Rate)")
        ),
    }

    if analysis.empty:
        return {
            "period": {"month": eff_m, "year": eff_y},
            "has_holdings": False,
            "ltcg": ltcg_kpis,
            "summary": {},
            "tax_impact": {},
            "holdings": [],
            "drop_trigger": {"triggered": False, "message": "No brokerage holdings found."},
        }

    # ── 2. Classify opportunities ─────────────────────────────────────────────
    classified = classify_harvest_opportunities(
        analysis,
        estimated_agi=float(agi),
        year=year,
        loss_threshold=-max(float(loss_threshold), 1.0),
        gain_threshold=float(gain_threshold),
    )
    summary = compute_harvest_summary(classified)
    tax_impact = compute_net_tax_impact(
        classified,
        estimated_agi=float(agi),
        year=year,
        marginal_ordinary_rate=float(marginal_rate_pct) / 100.0,
    )

    # ── 3. Market-drop trigger ────────────────────────────────────────────────
    drop_result = check_market_drop_trigger(analysis, drop_threshold_pct=float(drop_trigger_pct))

    # ── 4. Serialise per-holding rows + replacements ──────────────────────────
    holdings = []
    for _, row in classified.iterrows():
        sym = str(row["Symbol"])
        replacements = get_replacement_detail(sym)
        holdings.append({
            "account":        str(row["Account"]),
            "symbol":         sym,
            "name":           str(row["Name"]),
            "sector":         str(row["Sector"]),
            "qty":            round(float(row["Qty"]), 4),
            "purchase_price": round(float(row["Purchase Price"]), 4),
            "current_price":  round(float(row["Current Price"]), 4),
            "current_value":  round(float(row["Current Value"]), 2),
            "cost_basis":     round(float(row["Cost Basis"]), 2),
            "unrealized_gl":  round(float(row["Unrealized G/L"]), 2),
            "return_pct":     round(float(row["Return %"]), 2),
            "days_held":      int(row["Days Held"]),
            "gain_type":      str(row["Gain Type"]),
            "recommendation": str(row["Recommendation"]),
            "action_detail":  str(row.get("Action Detail", "")),
            "replacements":   replacements,
        })

    return {
        "period": {"month": eff_m, "year": eff_y},
        "has_holdings": True,
        "ltcg": ltcg_kpis,
        "summary": {
            "total_unrealized_gain":     round(summary["total_unrealized_gain"], 2),
            "total_unrealized_loss":     round(summary["total_unrealized_loss"], 2),
            "net_unrealized":            round(summary["net_unrealized"], 2),
            "harvestable_losses":        round(summary["harvestable_losses"], 2),
            "harvestable_gains_at_zero": round(summary["harvestable_gains_at_zero"], 2),
            "num_loss_candidates":       summary["num_loss_candidates"],
            "num_gain_candidates":       summary["num_gain_candidates"],
        },
        "tax_impact": {
            "ordinary_income_savings": round(float(tax_impact.ordinary_income_savings), 2),
            "tax_on_net_gains":        round(float(tax_impact.tax_on_net_gains), 2),
            "net_tax_impact":          round(float(tax_impact.net_tax_impact), 2),
            "ordinary_income_offset":  round(float(tax_impact.ordinary_income_offset), 2),
            "net_position":            round(float(tax_impact.net_position), 2),
        },
        "drop_trigger": {
            "triggered": bool(drop_result["triggered"]),
            "message":   str(drop_result["message"]),
        },
        "holdings": holdings,
    }


# --------------------------------------------------------------------------------------
# Performance & Analytics
# --------------------------------------------------------------------------------------

def performance(
    period: str,          # "1y" | "3y" | "5y" | "all"
    benchmark: str,       # ticker symbol e.g. "^GSPC"
) -> dict[str, Any]:
    """
    Calculate portfolio performance metrics over the requested period.

    Uses the net-worth history (monthly snapshots). Returns KPIs, chart series,
    and attribution data — no Streamlit dependency.
    """
    from portfolio_analytics import calculate_portfolio_analytics
    import datetime as _dt

    nw = nw_service.load_networth_history()

    if nw.empty or len(nw) < 2:
        return {"available": False, "reason": "Need at least 2 months of historical data."}

    if not isinstance(nw.index, pd.DatetimeIndex):
        nw.index = pd.to_datetime(nw.index)

    # Slice to requested period
    end = nw.index[-1]
    offsets = {"1y": 12, "3y": 36, "5y": 60}
    if period in offsets:
        start = end - pd.DateOffset(months=offsets[period])
        data = nw[nw.index >= start].copy()
    else:
        data = nw.copy()

    if data.empty or len(data) < 2:
        return {"available": False, "reason": f"Not enough data for the '{period}' period."}

    portfolio_series = pd.Series(data["total"].values, index=data.index, dtype=float)

    try:
        m = calculate_portfolio_analytics(
            portfolio_values=portfolio_series,
            benchmark_symbol=benchmark.strip() or "^GSPC",
            risk_free_rate=0.04,
        )
    except Exception as exc:
        logger.warning("performance analytics failed: %s", exc)
        return {"available": False, "reason": f"Analytics calculation failed: {exc}"}

    # Chart series — portfolio values & benchmark reconstruction
    labels = [d.strftime("%Y-%m-%d") for d in data.index]
    portfolio_vals = [_f(v) for v in data["total"]]
    benchmark_vals: list[float] = []
    if m.benchmark_returns:
        bv = portfolio_vals[0]
        benchmark_vals = [bv]
        for r in m.benchmark_returns[1:]:
            bv = bv * (1 + r)
            benchmark_vals.append(bv)

    # Attribution (simplified — no transaction history yet)
    start_v = portfolio_vals[0]
    end_v   = portfolio_vals[-1]
    twr_pct = (m.time_weighted_return or 0.0) * 100
    expected_growth = start_v * (twr_pct / 100)
    est_contrib = max(0.0, (end_v - start_v) - expected_growth)
    growth = max(0.0, (end_v - start_v) - est_contrib)

    # Benchmark vol / return for risk-return scatter
    bench_vol = bench_ret = None
    if m.benchmark_returns and len(m.benchmark_returns) > 1:
        import numpy as _np
        bench_vol = float(_np.std(m.benchmark_returns) * _np.sqrt(12) * 100)
        bench_ret = float((_np.prod([1 + r for r in m.benchmark_returns]) - 1) * 100)

    return {
        "available": True,
        "period": period,
        "benchmark": benchmark,
        "data_points": len(data),
        "start_date": labels[0] if labels else None,
        "end_date":   labels[-1] if labels else None,
        "kpis": {
            "twr":            round(twr_pct, 2),
            "mwr":            round((m.money_weighted_return or 0.0) * 100, 2),
            "total_return":   round(m.total_return_pct or 0.0, 2),
            "sharpe":         round(m.sharpe_ratio or 0.0, 2),
            "sortino":        round(m.sortino_ratio or 0.0, 2),
            "max_drawdown":   round((m.max_drawdown_pct or 0.0), 2),
            "current_drawdown": round((m.current_drawdown_pct or 0.0), 2),
            "volatility":     round((m.volatility or 0.0) * 100, 2),
            "alpha":          round((m.alpha or 0.0) * 100, 2),
            "beta":           round(m.beta or 1.0, 3),
            "benchmark_return": round((m.benchmark_return or 0.0) * 100, 2) if m.benchmark_return is not None else None,
        },
        "chart": {
            "labels":         labels,
            "portfolio":      portfolio_vals,
            "benchmark":      benchmark_vals if len(benchmark_vals) == len(labels) else [],
        },
        "attribution": {
            "start_value":           round(start_v, 2),
            "end_value":             round(end_v, 2),
            "estimated_growth":      round(growth, 2),
            "estimated_contrib":     round(est_contrib, 2),
        },
        "risk_return": {
            "portfolio_vol":   round((m.volatility or 0.0) * 100, 2),
            "portfolio_ret":   round(twr_pct, 2),
            "benchmark_vol":   round(bench_vol, 2) if bench_vol is not None else None,
            "benchmark_ret":   round(bench_ret, 2) if bench_ret is not None else None,
        },
        "drawdown_info": {
            "max_drawdown_pct": round((m.max_drawdown_pct or 0.0), 2),
            "recovery_months":  (m.recovery_days // 30) if m.recovery_days else None,
        },
    }


# --------------------------------------------------------------------------------------
# Factor Analysis
# --------------------------------------------------------------------------------------

def factor_analysis() -> dict[str, Any]:
    """
    Calculate portfolio-level factor exposure (Value / Growth / Momentum / Quality).

    Fetches factor data from Yahoo Finance for each distinct equity symbol,
    weights by market value, and returns portfolio-level scores + per-holding detail.
    Slow on a cold cache (~1 s per symbol); results are cached for 24 hours.
    """
    from portfolio_factors import (
        fetch_factor_data,
        calculate_portfolio_factor_exposure,
        DataQuality,
    )

    cur_m, cur_y = _today()
    eff_m, eff_y = pf.get_effective_portfolio_month_year(cur_m, cur_y)

    raw = pdb.db_get_by_month(eff_m, eff_y)
    if raw.empty:
        return {"available": False, "reason": "No portfolio data for this period."}

    # Build a market-value frame: symbol → market_value
    # Use purchase_price × qty as a cost-basis proxy when live prices aren't needed
    # (factor data doesn't depend on current price)
    df = raw.copy()
    df["qty"]            = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce").fillna(0)
    df["market_value"]   = df["qty"] * df["purchase_price"]

    # Filter to equities only — skip cash, bonds, ETFs with no YF factor data
    equity_mask = ~df["symbol"].str.upper().isin(pf.CASH_SYMBOLS) & (df["market_value"] > 0)
    equity_df = df[equity_mask][["symbol", "market_value"]].copy()
    equity_df = equity_df.groupby("symbol", as_index=False)["market_value"].sum()

    if equity_df.empty:
        return {"available": False, "reason": "No equity holdings found for factor analysis."}

    # Fetch factor data per symbol (cached)
    symbols = equity_df["symbol"].tolist()
    factor_data = {}
    for sym in symbols:
        try:
            factor_data[sym] = fetch_factor_data(sym, use_cache=True)
        except Exception:
            logger.debug("factor fetch failed for %s", sym, exc_info=True)

    if not factor_data:
        return {"available": False, "reason": "Could not fetch factor data from Yahoo Finance."}

    exposure = calculate_portfolio_factor_exposure(equity_df, factor_data)

    if exposure.analyzed_holdings == 0:
        return {"available": False, "reason": "Factor data unavailable for all holdings (ETFs/funds may not have individual factor scores)."}

    # Serialise per-holding factor scores
    holdings_out = []
    for sym, fm in factor_data.items():
        if fm.data_quality == DataQuality.UNAVAILABLE:
            continue
        row = equity_df[equity_df["symbol"] == sym]
        mv  = float(row["market_value"].iloc[0]) if not row.empty else 0.0
        total_mv = float(equity_df["market_value"].sum()) or 1.0
        holdings_out.append({
            "symbol":         sym,
            "name":           fm.name,
            "sector":         fm.sector,
            "weight_pct":     round(mv / total_mv * 100, 2),
            "value_score":    round(fm.value_score, 1),
            "growth_score":   round(fm.growth_score, 1),
            "momentum_score": round(fm.momentum_score, 1),
            "quality_score":  round(fm.quality_score, 1),
            "overall_score":  round(fm.get_overall_score(), 1),
            "data_quality":   fm.data_quality.value,
        })
    holdings_out.sort(key=lambda h: h["weight_pct"], reverse=True)

    return {
        "available": True,
        "period": {"month": eff_m, "year": eff_y},
        "coverage_pct": round(exposure.coverage_pct, 1),
        "analyzed": exposure.analyzed_holdings,
        "total": exposure.total_holdings,
        "exposure": {
            "value":    round(exposure.value_exposure, 1),
            "growth":   round(exposure.growth_exposure, 1),
            "momentum": round(exposure.momentum_exposure, 1),
            "quality":  round(exposure.quality_exposure, 1),
        },
        "tilt": {
            "value":    round(exposure.value_tilt, 1),
            "growth":   round(exposure.growth_tilt, 1),
            "momentum": round(exposure.momentum_tilt, 1),
            "quality":  round(exposure.quality_tilt, 1),
        },
        "style": {
            "primary":   exposure.primary_style.value,
            "secondary": exposure.secondary_style.value if exposure.secondary_style else None,
            "purity":    round(exposure.style_purity, 1),
        },
        "holdings": holdings_out,
    }


# --------------------------------------------------------------------------------------
# DAF Bundling
# --------------------------------------------------------------------------------------

def daf_bundling(
    agi: float,
    annual_giving: float,
    years_to_bundle: int,
    marginal_rate_pct: float,
    standard_deduction: float,
) -> dict[str, Any]:
    """
    Identify appreciated holdings suitable for DAF donation and compute
    the bundling tax savings recommendation.
    """
    from tax_harvesting import (
        build_harvesting_analysis,
        get_ltcg_rate_for_income,
        identify_daf_candidates,
        analyze_daf_bundling as _analyze_daf,
    )
    import datetime as _dt

    cur_m, cur_y = _today()
    eff_m, eff_y = pf.get_effective_portfolio_month_year(cur_m, cur_y)
    year = cur_y

    ltcg_rate = get_ltcg_rate_for_income(float(agi), year)
    analysis  = build_harvesting_analysis(eff_m, eff_y)

    if analysis.empty:
        return {
            "available": False,
            "reason": "No taxable (Brokerage) holdings found. DAF donations use appreciated securities from taxable accounts.",
            "ltcg_rate": ltcg_rate,
        }

    candidates = identify_daf_candidates(analysis, ltcg_rate=ltcg_rate)

    result = _analyze_daf(
        estimated_agi       = float(agi),
        annual_giving       = float(annual_giving),
        years_to_bundle     = int(years_to_bundle),
        marginal_rate       = float(marginal_rate_pct) / 100.0,
        standard_deduction  = float(standard_deduction),
        ltcg_rate           = ltcg_rate,
        securities_candidates = candidates,
        year                = year,
    )

    return {
        "available": True,
        "period": {"month": eff_m, "year": eff_y},
        "ltcg_rate": ltcg_rate,
        "recommendation": result.recommendation,
        "notes": result.notes,
        "summary": {
            "bundled_contribution":    round(result.bundled_contribution, 2),
            "deductible_amount":       round(result.deductible_amount, 2),
            "carryforward_amount":     round(result.carryforward_amount, 2),
            "tax_savings_vs_standard": round(result.tax_savings_vs_standard, 2),
            "total_securities_value":  round(result.total_securities_value, 2),
            "total_avoided_cg_tax":    round(result.total_avoided_cg_tax, 2),
            "standard_deduction":      round(result.standard_deduction, 2),
            "years_to_bundle":         result.years_to_bundle,
            "annual_giving":           round(result.annual_giving, 2),
        },
        "securities": [
            {
                "account":         c.account,
                "symbol":          c.symbol,
                "name":            c.name,
                "qty":             round(c.qty, 4),
                "cost_basis":      round(c.cost_basis, 2),
                "current_value":   round(c.current_value, 2),
                "unrealized_gain": round(c.unrealized_gain, 2),
                "gain_pct":        round(c.gain_pct, 2),
                "days_held":       c.days_held,
                "avoided_cg_tax":  round(c.avoided_cg_tax, 2),
            }
            for c in result.securities_candidates
        ],
        "all_candidates": [
            {
                "symbol":          c.symbol,
                "name":            c.name,
                "current_value":   round(c.current_value, 2),
                "unrealized_gain": round(c.unrealized_gain, 2),
                "gain_pct":        round(c.gain_pct, 2),
                "days_held":       c.days_held,
                "avoided_cg_tax":  round(c.avoided_cg_tax, 2),
            }
            for c in candidates
        ],
    }


# ---------------------------------------------------------------------------
# Connections (SnapTrade brokerage sync)
# ---------------------------------------------------------------------------

def _snaptrade_connector():
    """Return a live SnapTradeConnector or raise ImportError / ValueError."""
    try:
        from components.snaptrade_connector import create_snaptrade_connector
        from components.credential_manager import CredentialManager
    except ImportError as exc:
        raise ImportError("snaptrade-python or cryptography not installed") from exc
    return create_snaptrade_connector(), CredentialManager()


def connections_status() -> dict:
    """Return current SnapTrade connection status + account list."""
    import os
    connector, cred = _snaptrade_connector()
    user_id = os.getenv("SNAPTRADE_USER_ID", "default")
    user_secret = os.getenv("SNAPTRADE_USER_SECRET")
    status = connector.get_connection_status(user_id=user_id, user_secret=user_secret)
    # Annotate with last-sync info from local credential store
    local_conns = cred.list_connections(user_id=user_id)
    last_sync = max(
        (c["last_sync"] for c in local_conns if c["last_sync"]),
        default=None,
    )
    return {
        "configured": True,
        "connected": status.get("connected", False),
        "account_count": status.get("account_count", 0),
        "accounts": status.get("accounts", []),
        "last_sync": last_sync.isoformat() if last_sync else None,
        "user_id": user_id,
    }


def connections_auth_link(redirect_uri: str | None = None) -> dict:
    """Generate a SnapTrade OAuth link. Returns ``{"auth_link": url, "user_id": ...}``."""
    import os
    connector, _cred = _snaptrade_connector()
    user_id = os.getenv("SNAPTRADE_USER_ID", "default")
    result = connector.get_auth_link(user_id=user_id, redirect_uri=redirect_uri)
    return {"auth_link": result["auth_link"], "user_id": result["user_id"]}


def _import_snaptrade_transactions(connector, user_id: str) -> dict:
    """Best-effort: a transaction failure must not fail the holdings sync."""
    try:
        return connector.import_transactions(user_id=user_id)
    except Exception as exc:
        logger.exception("SnapTrade transaction import failed")
        return {"fetched": 0, "stored": 0, "error": str(exc)}


def _merge_and_save_synced(connector, df: pd.DataFrame, month: int, year: int) -> dict:
    """Merge synced brokerage holdings into portfolio.db (replacing the synced accounts' rows)."""
    from portfolio_db import db_overwrite_month, enrich_holdings
    if df.empty:
        return {"synced": 0, "merged": 0, "enriched": 0}
    merged = connector.merge_holdings_to_portfolio(df)
    total = 0
    for (m, y), grp in merged.groupby(["month", "year"]):
        total += db_overwrite_month(int(m), int(y), grp)
    try:
        enrich_result = enrich_holdings(month=month, year=year)
        enriched = enrich_result.get("enriched", 0)
    except Exception:
        enriched = 0
    app_cache.clear_all()
    return {"synced": len(df), "merged": total, "enriched": enriched}


def connections_sync(month: int, year: int) -> dict:
    """Sync all brokerage holdings into portfolio.db for the given month/year."""
    import os
    connector, _cred = _snaptrade_connector()
    user_id = os.getenv("SNAPTRADE_USER_ID", "default")
    df = connector.sync_holdings(user_id=user_id, month=month, year=year)
    result = _merge_and_save_synced(connector, df, month, year)
    result["transactions"] = _import_snaptrade_transactions(connector, user_id)
    return result


def connections_disconnect() -> dict:
    """Disconnect SnapTrade (delete user registration). Returns ``{"ok": true}``."""
    import os
    connector, cred = _snaptrade_connector()
    user_id = os.getenv("SNAPTRADE_USER_ID", "default")
    connector.disconnect_authorization(user_id=user_id)
    # Mark all local connections as disconnected too
    for conn in cred.list_connections(user_id=user_id):
        cred.disconnect_account(conn["id"])
    return {"ok": True}


# ---------------------------------------------------------------------------
# Transactions (Tax Records tab) — read from transactions.db
# ---------------------------------------------------------------------------

def transactions_list(account: str | None = None, symbol: str | None = None,
                      types: list[str] | None = None, start: str | None = None,
                      end: str | None = None, limit: int = 2000) -> dict:
    """Stored brokerage transactions, newest first, plus filter choices and totals.

    ``account`` matches the display name. ``choices`` always lists everything stored so the
    UI can offer every account/type regardless of the active filter. Dates are compared as
    YYYY-MM-DD (the stored value may carry a time and offset).
    """
    import sqlite3
    from components.transaction_storage import TransactionStorage
    storage = TransactionStorage()
    try:
        storage.backfill_account_names()
    except Exception:
        logger.exception("transaction account-name backfill failed")

    sel = ("SELECT id, substr(transaction_date, 1, 10) AS date, "
           "COALESCE(NULLIF(TRIM(account_name), ''), 'Unknown') AS account, transaction_type AS type, "
           "COALESCE(symbol, '') AS symbol, COALESCE(description, '') AS description, "
           "COALESCE(quantity, 0) AS quantity, COALESCE(price, 0) AS price, "
           "COALESCE(amount, 0) AS amount, COALESCE(fee, 0) AS fee FROM transactions")
    with sqlite3.connect(storage.db_path) as conn:
        conn.row_factory = sqlite3.Row
        everything = [dict(r) for r in conn.execute(sel)]
    choices = {"accounts": sorted({r["account"] for r in everything}),
               "types": sorted({r["type"] for r in everything})}

    sym = (symbol or "").strip().upper()
    rows = [r for r in everything
            if (not account or r["account"] == account)
            and (not sym or sym in r["symbol"].upper())
            and (not types or r["type"] in types)
            and (not start or r["date"] >= start)
            and (not end or r["date"] <= end)]
    rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)

    totals: dict[str, dict] = {}
    for r in rows:
        t = totals.setdefault(r["type"], {"count": 0, "amount": 0.0})
        t["count"] += 1
        t["amount"] = round(t["amount"] + r["amount"], 2)
    out = [{k: v for k, v in r.items() if k != "id"} for r in rows[:limit]]
    return {"rows": out, "total": len(rows), "truncated": len(rows) > limit, "totals": totals, "choices": choices}


def _txn_storage():
    from components.transaction_storage import TransactionStorage
    return TransactionStorage()


def _account_types() -> dict[str, str]:
    """``account_name -> account_type`` (Brokerage, Roth, Traditional, ...).

    Taken from the saved holdings (the app's source of truth), with the configured
    ``portfolio_accounts`` filling in any account that has no holdings.
    """
    from config import get_config_manager
    types: dict[str, str] = {}
    accounts = get_config_manager().get("portfolio_accounts", "accounts", []) or []
    types.update({a["account_name"]: a.get("account_type", "") for a in accounts if a.get("account_name")})
    df = pdb.db_load_all()
    if not df.empty:
        latest = df.sort_values(["year", "month"]).drop_duplicates("account_name", keep="last")
        types.update({n: t for n, t in zip(latest["account_name"], latest["account_type"]) if n and t})
    return types


def _trade_lots(method: str) -> dict[str, Any]:
    """Run the cost-basis engine over every stored BUY/SELL and tag each result with its account type.

    Only ``Brokerage`` accounts are taxable; Roth/Traditional gains are not reported to the IRS.
    """
    import sqlite3
    from components import cost_basis

    storage = _txn_storage()
    with sqlite3.connect(storage.db_path) as conn:
        conn.row_factory = sqlite3.Row
        trades = [dict(r) for r in conn.execute(
            "SELECT substr(transaction_date, 1, 10) AS date, "
            "COALESCE(NULLIF(TRIM(account_name), ''), 'Unknown') AS account, transaction_type AS type, "
            "COALESCE(symbol, '') AS symbol, COALESCE(quantity, 0) AS quantity, COALESCE(price, 0) AS price, "
            "COALESCE(amount, 0) AS amount, COALESCE(fee, 0) AS fee "
            "FROM transactions WHERE transaction_type IN ('BUY', 'SELL')")]
    result = cost_basis.compute(trades, method)
    types = _account_types()
    for section in result.values():
        for row in section:
            row["account_type"] = types.get(row["account"], "Unknown")
            row["taxable"] = row["account_type"] == "Brokerage"
    return result


def _round_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]


def cost_basis_lots(method: str = "FIFO", account: str | None = None, symbol: str | None = None) -> dict:
    """Open tax lots (what is still held and what it cost), reconstructed from stored trades."""
    data = _trade_lots(method)
    sym = (symbol or "").strip().upper()
    allrows = data["open_lots"]
    rows = [r for r in allrows if (not account or r["account"] == account) and (not sym or sym in r["symbol"].upper())]
    return {
        "method": method.upper(),
        "lots": _round_rows(rows),
        "total_basis": round(sum(r["basis"] for r in rows), 2),
        "choices": {"accounts": sorted({r["account"] for r in allrows})},
    }


def capital_gains(method: str = "FIFO", year: int | None = None, taxable_only: bool = True) -> dict:
    """Realized gains by tax year (short/long split) plus the matched-lot detail."""
    data = _trade_lots(method)
    pick = lambda rows: [r for r in rows if r["taxable"] or not taxable_only]  # noqa: E731
    realized, unmatched = pick(data["realized"]), pick(data["unmatched"])

    by_year: dict[int, dict[str, float]] = {}
    for r in realized:
        y = by_year.setdefault(r["tax_year"], {"short": 0.0, "long": 0.0, "proceeds": 0.0, "basis": 0.0})
        y[r["term"]] += r["gain"]
        y["proceeds"] += r["proceeds"]
        y["basis"] += r["basis"]
    years = [{"year": y, **{k: round(v, 2) for k, v in d.items()}, "total": round(d["short"] + d["long"], 2)}
             for y, d in sorted(by_year.items(), reverse=True)]

    detail = sorted((r for r in realized if year is None or r["tax_year"] == year),
                    key=lambda r: (r["sold"], r["account"], r["symbol"]), reverse=True)
    return {
        "method": method.upper(), "taxable_only": taxable_only, "years": years,
        "rows": _round_rows(detail),
        "unmatched": _round_rows([u for u in unmatched if year is None or u["tax_year"] == year]),
    }


# ---------------------------------------------------------------------------
# Connections (Schwab Direct API)
# ---------------------------------------------------------------------------

_schwab_lock = threading.Lock()
_schwab_singleton = None   # OAuth PKCE verifier lives on the connector, so it must outlive one request


def _schwab_connector():
    """Return the shared SchwabConnector. Raises ValueError (no credentials) or ImportError."""
    global _schwab_singleton
    from components.schwab_connector import SchwabConnector
    from components.credential_manager import CredentialManager
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    key, secret = os.getenv("SCHWAB_APP_KEY"), os.getenv("SCHWAB_APP_SECRET")
    if not key or not secret:
        raise ValueError("SCHWAB_APP_KEY and SCHWAB_APP_SECRET are not set")
    with _schwab_lock:
        if _schwab_singleton is None:
            _schwab_singleton = SchwabConnector(
                app_key=key,
                app_secret=secret,
                callback_url=os.getenv("SCHWAB_CALLBACK_URL", "https://localhost:8080/callback"),
                credential_manager=CredentialManager(),
            )
        return _schwab_singleton


def _schwab_is_connected(connector) -> bool:
    return connector.is_connected() or connector.load_saved_tokens()


def schwab_status() -> dict:
    """Schwab Direct status. ``configured`` is False when credentials/packages are missing."""
    try:
        connector = _schwab_connector()
    except (ValueError, ImportError) as exc:
        return {"configured": False, "connected": False, "accounts": [], "detail": str(exc)}
    if not _schwab_is_connected(connector):
        return {"configured": True, "connected": False, "accounts": []}
    accounts = []
    for acct in connector.get_accounts():
        info = acct.get("securitiesAccount", {})
        number = str(info.get("accountNumber", ""))
        bal = info.get("currentBalances", {})
        accounts.append({
            "id": number,
            "last4": number[-4:],
            "type": info.get("type", "Unknown"),
            "total_value": bal.get("liquidationValue", 0) or 0,
            "cash": bal.get("cashBalance", 0) or 0,
        })
    return {"configured": True, "connected": True, "accounts": accounts}


def schwab_auth_url() -> dict:
    """Start the OAuth flow. Returns ``{"auth_url": url}``."""
    return {"auth_url": _schwab_connector().get_authorization_url()}


def schwab_complete(callback_url: str) -> dict:
    """Finish OAuth with the full redirect URL pasted by the user."""
    if not _schwab_connector().complete_authorization(callback_url.strip()):
        raise ValueError("Authorization failed. Start again and paste the full callback URL.")
    return {"ok": True}


def schwab_sync(month: int, year: int) -> dict:
    """Pull Schwab positions and merge them into portfolio.db for month/year."""
    from components.schwab_data_transformer import SchwabDataTransformer
    connector = _schwab_connector()
    if not _schwab_is_connected(connector):
        raise ValueError("Schwab is not connected")
    # First sync walks back ~10 years (the API serves 1-year windows; trades since 2016 were verified
    # retrievable). Afterwards the last year is enough because rows are upserted and never deleted.
    marker = Path(_txn_storage().db_path).parent / ".schwab_history_backfilled"
    days_back = 365 if marker.exists() else 3650
    positions = connector.get_positions(import_transactions=True, transaction_days_back=days_back)
    marker.touch()
    df = SchwabDataTransformer.transform_positions_to_portfolio(positions, enrich_with_transactions=True)
    if not df.empty:
        df["month"], df["year"] = month, year
    result = _merge_and_save_synced(connector, df, month, year)
    try:    # the Schwab importer stores trades with a blank account name; fill it from the saved hash mapping
        from components.transaction_storage import TransactionStorage
        TransactionStorage().backfill_account_names()
    except Exception:
        logger.exception("Schwab transaction account-name backfill failed")
    return result


def schwab_disconnect() -> dict:
    """Clear in-memory tokens and deactivate the stored Schwab connection."""
    connector = _schwab_connector()
    connector.disconnect()
    cred = connector.credential_manager
    for conn in cred.list_connections():
        if conn.get("brokerage_name") == "Schwab":
            cred.disconnect_account(conn["id"])
    return {"ok": True}


# ---------------------------------------------------------------------------
# Harvest Savings tracker (Direct Indexing)
# ---------------------------------------------------------------------------

def harvest_savings(year: int) -> dict:
    """Return YTD direct-index harvest savings for *year*."""
    try:
        from components.tax_savings_tracker import (
            get_ytd_summary,
            get_harvest_history,
            get_performance_metrics,
        )
    except ImportError as exc:
        raise ImportError("tax_savings_tracker module not available") from exc

    ytd = get_ytd_summary(year, None)
    try:
        history_df = get_harvest_history(year, None)
        history = history_df.to_dict(orient="records") if not history_df.empty else []
        # Convert any Timestamp/date values to strings for JSON serialisation
        import datetime as _dt
        for row in history:
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
    except Exception:
        history = []

    try:
        metrics = get_performance_metrics(year)
    except Exception:
        metrics = {}

    return {
        "year": year,
        "summary": {
            "total_harvests": ytd.total_harvests,
            "total_realized_losses": round(float(ytd.total_realized_losses), 2),
            "total_estimated_savings": round(float(ytd.total_estimated_savings), 2),
            "total_actual_savings": round(float(ytd.total_actual_savings), 2),
            "short_term_losses": round(float(ytd.short_term_losses), 2),
            "long_term_losses": round(float(ytd.long_term_losses), 2),
            "short_term_savings": round(float(ytd.short_term_savings), 2),
            "long_term_savings": round(float(ytd.long_term_savings), 2),
            "by_account": ytd.by_account or {},
        },
        "history": history,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Direct Indexing configuration YAML
# ---------------------------------------------------------------------------

_DI_CONFIG_PATH = "config/direct_indexing_config.yaml"


def di_config_read() -> dict:
    """Read direct_indexing_config.yaml and return its parsed contents."""
    import yaml
    from pathlib import Path
    p = Path(_DI_CONFIG_PATH)
    if not p.exists():
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


def di_config_write(changes: dict) -> dict:
    """Merge *changes* into the YAML and write it back. Returns the updated config."""
    import yaml
    from pathlib import Path

    p = Path(_DI_CONFIG_PATH)
    cfg = di_config_read()

    # Deep-merge: changes is expected to be the full direct_indexing section
    # keyed exactly as in the YAML so we can do a targeted merge.
    di = cfg.setdefault("direct_indexing", {})
    for section, values in changes.items():
        if isinstance(values, dict):
            di.setdefault(section, {}).update(values)
        else:
            di[section] = values

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    return cfg
