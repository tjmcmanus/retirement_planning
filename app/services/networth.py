"""Streamlit-free net worth history and dashboard KPIs.

Mirrors ``components/shared.py`` (``build_historical_networth``,
``_get_real_estate_rows``) and the KPI arithmetic in ``pages/3_dashboard.py``.
Those modules import Streamlit, so they cannot be used here. Once the Streamlit
pages are retired (or split in M4), this becomes the single implementation.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

import app_cache
from config import get_config_manager
from load_data import (
    get_networth_by_month,
    load_networth_cache,
    save_networth_cache,
)

logger = logging.getLogger(__name__)

NUM_MONTHS = 12
BENCHMARK_ANNUAL_RATE = 0.07

# Same mapping as components/shared.ACCOUNT_TYPE_MAP
ACCOUNT_TYPE_MAP: dict[str, str] = {
    "Cash": "cash",
    "Savings": "cash",
    "Brokerage": "taxable",
    "Traditional": "tax_deferred",
    "Roth": "tax_free",
}
_COLUMNS = ["cash", "taxable", "tax_deferred", "tax_free", "total"]


def _build_row(date: pd.Timestamp, summary_df: pd.DataFrame) -> dict:
    totals = (
        summary_df[summary_df["account_type"].isin(list(ACCOUNT_TYPE_MAP))]
        .groupby("account_type")["market_value"]
        .sum()
        .reindex(list(ACCOUNT_TYPE_MAP), fill_value=0.0)
    )
    row = {ACCOUNT_TYPE_MAP[str(k)]: v for k, v in totals.items()}
    row["total"] = totals.sum()
    row["date"] = date
    return row


@app_cache.cache_data(ttl=300)
def build_historical_networth(num_months: int = NUM_MONTHS) -> pd.DataFrame:
    """Month-start net worth by account bucket for the last ``num_months`` months."""
    end = pd.Timestamp.today().normalize().replace(day=1)
    start = end - pd.DateOffset(months=num_months - 1)
    rows = []
    for date in pd.date_range(start=start, end=end, freq="MS"):
        try:
            _, summary_df = get_networth_by_month(date.month, date.year)
            if summary_df.empty:
                continue
            rows.append(_build_row(date, summary_df))
        except (ValueError, RuntimeError) as exc:
            logger.warning("Could not fetch net worth for %s: %s", date.strftime("%m/%Y"), exc)
    if not rows:
        return pd.DataFrame(
            {c: pd.Series(dtype=float) for c in _COLUMNS}
        ).set_index(pd.DatetimeIndex([], name="date"))
    return (
        pd.DataFrame.from_records(rows, index="date", columns=["date", *_COLUMNS]).sort_index()
    )


def load_networth_history(num_months: int = NUM_MONTHS) -> pd.DataFrame:
    """Fresh on-disk cache if present (shared with the Streamlit UI), else build and save."""
    cached = load_networth_cache(num_months)
    if not cached.empty:
        return cached
    built = build_historical_networth(num_months=num_months)
    if not built.empty:
        save_networth_cache(built, num_months)
    return built


def real_estate_total() -> float:
    """Sum of configured real-estate purchase prices (same rule as the Streamlit dashboard)."""
    try:
        props = get_config_manager().get("real_estate", "properties", []) or []
        return float(sum(float(p.get("purchase_price", 0) or 0) for p in props))
    except Exception:
        logger.warning("Could not load real estate config", exc_info=True)
        return 0.0


def _pct(change: float, base: float) -> float:
    return (change / base * 100.0) if base else 0.0


def dashboard_networth() -> dict[str, Any]:
    """Net worth trend series and KPI cards, matching pages/3_dashboard.py."""
    networth = load_networth_history()
    if networth.empty or len(networth) < 2:
        return {"ready": False, "reason": "Need at least 2 months of portfolio data."}

    re_total = real_estate_total()
    nw = networth.copy()
    if re_total:
        nw["total"] = nw["total"] + re_total

    current = float(nw["total"].iloc[-1])
    prior = float(nw["total"].iloc[-2])
    mom = current - prior

    idx = pd.DatetimeIndex(nw.index)
    year_mask = idx.year == idx[-1].year
    ytd_start = float(nw.loc[year_mask, "total"].iloc[0]) if year_mask.any() else current
    ytd = current - ytd_start

    older = nw.loc[nw.index <= idx[-1] - pd.DateOffset(months=12)]
    roll_start = float(older["total"].iloc[-1]) if not older.empty else float(nw["total"].iloc[0])
    rolling = current - roll_start

    first = float(nw["total"].iloc[0])
    last_bench = first * ((1 + BENCHMARK_ANNUAL_RATE / 12) ** (len(nw) - 1))
    vs_bench = current - last_bench

    monthly = nw[["total"]].sort_index().resample("ME").last().dropna(subset=["total"])

    return {
        "ready": True,
        "as_of": idx[-1].strftime("%Y-%m-%d"),
        "real_estate_total": re_total,
        "kpis": {
            "net_worth": current,
            "month_over_month": {"amount": mom, "percent": _pct(mom, prior)},
            "year_to_date": {"amount": ytd, "percent": _pct(ytd, ytd_start)},
            "rolling_12_month": {"amount": rolling, "percent": _pct(rolling, roll_start)},
            "vs_benchmark": {
                "amount": vs_bench,
                "percent": _pct(vs_bench, last_bench),
                "benchmark_rate": BENCHMARK_ANNUAL_RATE,
            },
        },
        "trend": {
            "labels": [d.strftime("%b %Y") for d in monthly.index],
            "values": [float(v) for v in monthly["total"]],
        },
    }
