"""Strategy service for the API.

Exposes withdrawal strategy data, plus the six views that were previously
only available in the Streamlit version of pages/5_strategy.py:
  - Key Events Timeline
  - Money Flow (per-year Sankey data)
  - Month-by-Month Plan
  - Bucket Strategy Analysis
  - Tax Analytics
  - Income & Expense breakdown
"""
from __future__ import annotations

import calendar
import datetime as dt
import math
import threading
from typing import Any

import numpy as np
import pandas as pd

from config import get_config_manager, reload_config
from strategy import build_withdrawal_strategy_display

# The engine and the shared headless config manager are process-wide state.
_lock = threading.Lock()

END_YEAR_DEFAULT = 2050


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(v, (pd.Timestamp, dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, np.bool_):
        return bool(v)
    if v is pd.NaT:
        return None
    return v


def df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): _jsonable(v) for k, v in row.items()} for row in df.to_dict("records")]


# ---------------------------------------------------------------------------
# Internal: build strategy DataFrame (cached per process run with _lock)
# ---------------------------------------------------------------------------

def _build_strategy(start_year: int | None, end_year: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (strategy_df, balances_df, cfg_snapshot). Caller holds _lock."""
    reload_config()
    cfg = get_config_manager()
    start_year = start_year or dt.date.today().year
    rate = float(cfg.get("financial_assumptions", "expected_rate_of_return", 6) or 6) / 100
    strategy_df, balances_df = build_withdrawal_strategy_display(
        start_year=start_year,
        end_year=end_year,
        growth_rate=1 + rate,
        expense_inflation_rate=float(
            cfg.get("financial_assumptions", "expense_inflation_rate", 3.0) or 3.0
        ) / 100,
        person1_name=cfg.get("personal_info", "person1_name", "Person1"),
        person2_name=cfg.get("personal_info", "person2_name", "Person2"),
        max_conversion_rate=float(
            cfg.get("tax_strategy", "max_roth_conversion_tax_rate", 24) or 24
        ) / 100,
        aca_optimize=bool(cfg.get("healthcare", "aca_marketplace_enrolled", False)),
        ss_claiming_age=int(cfg.get("social_security", "person1_ssi_age", 70) or 70),
    )
    cfg_snap = {
        "start_year": start_year,
        "end_year": end_year,
        "rate": rate,
        "person1_name": cfg.get("personal_info", "person1_name", "Person1"),
        "person2_name": cfg.get("personal_info", "person2_name", "Person2"),
        "person1_ss_age": int(cfg.get("social_security", "person1_ssi_age", 70) or 70),
        "person2_ss_age": int(cfg.get("social_security", "person2_ssi_age", 70) or 70),
        "person1_retirement_age": int(cfg.get("personal_info", "person1_retirement_age", 67) or 67),
        "person2_retirement_age": int(cfg.get("personal_info", "person2_retirement_age", 62) or 62),
        "annual_expenses": float(cfg.get("financial_assumptions", "expected_annual_expenses", 120_000) or 120_000),
    }
    return strategy_df, balances_df, cfg_snap


# ---------------------------------------------------------------------------
# Public: main strategy endpoint (existing)
# ---------------------------------------------------------------------------

DECISION_LOG_COL = "Decision Log"


def _plain(v: Any) -> Any:
    """Make a decision's supporting values JSON-safe (numpy, dates, nested containers, odd objects)."""
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_plain(x) for x in v]
    if isinstance(v, (str, bool)) or v is None:
        return v
    if isinstance(v, (int, float, np.number, np.bool_, pd.Timestamp, dt.datetime, dt.date)):
        return _jsonable(v)
    return str(v)


def withdrawal_strategy(
    start_year: int | None = None,
    end_year: int = END_YEAR_DEFAULT,
) -> dict[str, Any]:
    with _lock:
        strategy_df, balances_df, cfg = _build_strategy(start_year, end_year)
    # The decision log holds objects, not table data; it is served by decision_log() instead.
    strategy_df = strategy_df.drop(columns=[DECISION_LOG_COL], errors="ignore")
    return {
        "start_year": cfg["start_year"],
        "end_year": end_year,
        "assumptions": {"expected_rate_of_return": cfg["rate"]},
        "columns": [str(c) for c in strategy_df.columns],
        "strategy": df_to_records(strategy_df),
        "balances": df_to_records(balances_df),
    }


def decision_log(
    year: int,
    start_year: int | None = None,
    end_year: int = END_YEAR_DEFAULT,
) -> dict[str, Any]:
    """The reasons the engine recorded for one year, grouped by category."""
    with _lock:
        strategy_df, _, _ = _build_strategy(start_year, end_year)
    rows = strategy_df[strategy_df["Year"] == year]
    if rows.empty:
        raise ValueError(f"Year {year} is outside the strategy range")
    row = rows.iloc[0]
    log = row.get(DECISION_LOG_COL) if DECISION_LOG_COL in strategy_df.columns else None

    groups: list[dict[str, Any]] = []
    if log is not None and hasattr(log, "__dataclass_fields__"):
        for name in log.__dataclass_fields__:
            entries = [
                {"decision": d.decision, "action": d.action, "reason": d.reason, "values": _plain(d.values)}
                for d in getattr(log, name)
            ]
            if entries:
                groups.append({"category": name, "decisions": entries})

    def amount(col: str) -> float:
        return _val(row, col)

    return {
        "year": int(year),
        "stage": str(row.get("Stage", "")),
        "summary": {
            "trad_to_cash": amount("Trad→\nCash"),
            "trad_to_roth": amount("Trad→\nRoth"),
            "brok_to_cash": amount("Brok→\nCash"),
            "daf_contribution": amount("DAF Contribution"),
            "agi": amount("AGI"),
            "federal_tax": amount("Federal Tax"),
        },
        "groups": groups,
    }


# ---------------------------------------------------------------------------
# Key Events Timeline
# ---------------------------------------------------------------------------

def _val(row: "pd.Series", col: str) -> float:
    v = row.get(col, 0)
    try:
        return float(v) if v is not None and v == v else 0.0
    except (TypeError, ValueError):
        return 0.0


def timeline_events(
    start_year: int | None = None,
    end_year: int = END_YEAR_DEFAULT,
) -> dict[str, Any]:
    with _lock:
        strategy_df, _, cfg = _build_strategy(start_year, end_year)

    p1_name = cfg["person1_name"]
    p2_name = cfg["person2_name"]
    p1_ss_age = cfg["person1_ss_age"]
    p2_ss_age = cfg["person2_ss_age"]
    p1_ret_age = cfg["person1_retirement_age"]
    p2_ret_age = cfg["person2_retirement_age"]

    events: list[dict] = []
    start = int(strategy_df.iloc[0]["Year"])
    limit = start + 15
    p1_ss_done = p2_ss_done = p1_med_done = p2_med_done = False

    for _, row in strategy_df.iterrows():
        year = int(row["Year"])
        if year > limit:
            break
        age_str = str(row.get("Age", ""))
        age1 = age2 = 0
        if "/" in age_str:
            parts = age_str.split("/")
            try:
                age1 = int(parts[0].strip())
                age2 = int(parts[1].strip()) if len(parts) > 1 else 0
            except (ValueError, IndexError):
                pass

        # Social Security
        ss = _val(row, "SS Benefits")
        if ss > 0:
            if age1 >= p1_ss_age and not p1_ss_done:
                events.append({"year": year, "event": f"{p1_name} SS Begins",
                                "details": f"Age {age1}", "category": "ss"})
                p1_ss_done = True
            if age2 >= p2_ss_age and age2 > 0 and not p2_ss_done:
                events.append({"year": year, "event": f"{p2_name} SS Begins",
                                "details": f"Age {age2}", "category": "ss"})
                p2_ss_done = True

        # Medicare
        if age1 == 65 and not p1_med_done:
            events.append({"year": year, "event": f"{p1_name} Medicare",
                           "details": "Age 65", "category": "medicare"})
            p1_med_done = True
        if age2 == 65 and age2 > 0 and not p2_med_done:
            events.append({"year": year, "event": f"{p2_name} Medicare",
                           "details": "Age 65", "category": "medicare"})
            p2_med_done = True

        # RMDs first year
        rmd = _val(row, "RMD")
        prev_rmd = 0.0
        idx = list(strategy_df.index).index(row.name) if row.name in strategy_df.index else -1
        if idx > 0:
            prev_rmd = _val(strategy_df.iloc[idx - 1], "RMD")
        if rmd > 0 and prev_rmd == 0:
            events.append({"year": year, "event": "RMDs Begin",
                           "details": f"${rmd:,.0f} required", "category": "rmd"})

        # Large Roth conversions
        conv = _val(row, "Trad→\nRoth")
        if conv > 50_000:
            events.append({"year": year, "event": "Major Roth Conversion",
                           "details": f"${conv:,.0f}", "category": "roth"})

    return {"events": events}


# ---------------------------------------------------------------------------
# Money Flow (Sankey data for a single year)
# ---------------------------------------------------------------------------

def money_flow(
    year: int,
    start_year: int | None = None,
    end_year: int = END_YEAR_DEFAULT,
) -> dict[str, Any]:
    with _lock:
        strategy_df, _, _ = _build_strategy(start_year, end_year)

    rows = strategy_df[strategy_df["Year"] == year]
    if rows.empty:
        return {"sources": [], "targets": [], "values": [], "labels": []}

    row = rows.iloc[0]

    def v(col: str) -> float:
        return _val(row, col)

    sources, targets, values = [], [], []

    wages = v("Wages")
    payroll = v("Wages→\nPayroll")
    if wages > 1000:
        if payroll > 1000:
            sources.append("Wages/Salary"); targets.append("Payroll Taxes"); values.append(payroll)
        after = wages - payroll
        sources.append("Wages/Salary"); targets.append("Cash/Spending"); values.append(after)

    trad_cash = v("Trad→\nCash")
    if trad_cash > 1000:
        sources.append("Traditional IRA/401(k)"); targets.append("Cash/Spending"); values.append(trad_cash)

    brok_cash = v("Brok→\nCash")
    if brok_cash > 1000:
        sources.append("Brokerage"); targets.append("Cash/Spending"); values.append(brok_cash)

    roth_cash = v("Roth→\nCash")
    if roth_cash > 1000:
        sources.append("Roth IRA/401(k)"); targets.append("Cash/Spending"); values.append(roth_cash)

    ss = v("SS Benefits")
    if ss > 1000:
        sources.append("Social Security"); targets.append("Cash/Spending"); values.append(ss)

    expenses = v("Expenses")
    if expenses > 1000:
        sources.append("Cash/Spending"); targets.append("Living Expenses"); values.append(expenses)

    hc = v("Healthcare Cost")
    if hc > 1000:
        sources.append("Cash/Spending"); targets.append("Healthcare"); values.append(hc)

    fed = v("Federal Tax")
    if fed > 1000:
        sources.append("Cash/Spending"); targets.append("Federal Tax"); values.append(fed)

    state = v("State Tax")
    if state > 1000:
        sources.append("Cash/Spending"); targets.append("State Tax"); values.append(state)

    trad_roth = v("Trad→\nRoth")
    if trad_roth > 1000:
        sources.append("Traditional IRA/401(k)"); targets.append("Roth Conversion"); values.append(trad_roth)

    trad_brok = v("Trad→\nBrok")
    if trad_brok > 1000:
        sources.append("Traditional IRA/401(k)"); targets.append("Brokerage"); values.append(trad_brok)

    daf = v("DAF Contribution")
    if daf > 1000:
        sources.append("Brokerage"); targets.append("DAF (Charitable)"); values.append(daf)

    labels = list(dict.fromkeys(sources + targets))
    src_idx = [labels.index(s) for s in sources]
    tgt_idx = [labels.index(t) for t in targets]

    return {
        "year": year,
        "labels": labels,
        "sources": src_idx,
        "targets": tgt_idx,
        "values": values,
        "available_years": [int(y) for y in strategy_df["Year"].tolist()],
    }


# ---------------------------------------------------------------------------
# Month-by-Month Plan
# ---------------------------------------------------------------------------

_MONTH_NAMES = list(calendar.month_name)[1:]

def monthly_plan(
    year: int,
    start_year: int | None = None,
    end_year: int = END_YEAR_DEFAULT,
) -> dict[str, Any]:
    with _lock:
        strategy_df, _, cfg = _build_strategy(start_year, end_year)

    rows = strategy_df[strategy_df["Year"] == year]
    if rows.empty:
        return {"year": year, "months": [], "available_years": []}

    row = rows.iloc[0]
    p1 = cfg["person1_name"]
    p2 = cfg["person2_name"]

    def v(col: str) -> float:
        return _val(row, col)

    trad_roth = v("Trad→\nRoth")
    trad_cash = v("Trad→\nCash")
    trad_brok = v("Trad→\nBrok")
    rmd_total = v("RMD")
    rmd_p1 = v("RMD Person1") or rmd_total * 0.70
    rmd_p2 = v("RMD Person2") or rmd_total * 0.30

    months = []
    for m in range(1, 13):
        actions = []

        # Q estimated taxes (Apr=Q1, Jun=Q2, Sep=Q3, Jan=Q4-prior)
        fed = v("Federal Tax")
        if fed > 0 and m in (1, 4, 6, 9):
            q_fed = fed / 4
            q_state = v("State Tax") / 4
            q_total = q_fed + q_state
            label = {1: "Q4 Prior Year", 4: "Q1", 6: "Q2", 9: "Q3"}[m]
            if q_state > 0:
                actions.append({"label": f"{label} Estimated Tax", "amount": q_total,
                                 "detail": f"Fed ${q_fed:,.0f} + State ${q_state:,.0f}"})
            else:
                actions.append({"label": f"{label} Estimated Tax (Federal)", "amount": q_fed, "detail": ""})

        # Roth conversions quarterly
        if trad_roth > 0 and m in (1, 4, 7, 10):
            q = trad_roth / 4
            actions.append({"label": f"Roth Conversion — {p1}", "amount": q * 0.70,
                             "detail": "IBM 401k→Schwab Roth"})
            actions.append({"label": f"Roth Conversion — {p2}", "amount": q * 0.30,
                             "detail": "Highmark 401k→Schwab Roth"})

        # Trad→Cash monthly
        if trad_cash > 0:
            mc = trad_cash / 12
            if mc >= 500:
                actions.append({"label": f"Trad→Cash — {p1}", "amount": mc,
                                 "detail": "IBM 401k → PNC for expenses"})

        # RMDs quarterly
        if rmd_total > 0 and m in (3, 6, 9, 12):
            actions.append({"label": f"RMD — {p1}", "amount": rmd_p1 / 4,
                             "detail": "IBM 401k → Brokerage, mandatory"})
            actions.append({"label": f"RMD — {p2}", "amount": rmd_p2 / 4,
                             "detail": "Highmark 401k → Brokerage, mandatory"})

        # Trad→Brok quarterly
        if trad_brok > 0 and m in (1, 4, 7, 10):
            q = trad_brok / 4
            actions.append({"label": f"Trad→Brokerage — {p1}", "amount": q * 0.70, "detail": ""})
            p2b = q * 0.30
            if p2b >= 500:
                actions.append({"label": f"Trad→Brokerage — {p2}", "amount": p2b, "detail": ""})

        # Rebalance review quarterly
        if m in (3, 6, 9, 12):
            actions.append({"label": "Portfolio Rebalance Review", "amount": 0, "detail": ""})

        # Strategy review
        if m in (1, 7):
            actions.append({"label": "Strategy Review & Adjustment", "amount": 0, "detail": ""})

        # Healthcare premiums summary
        if m == 1:
            hc = v("Healthcare Cost")
            if hc > 0:
                actions.append({"label": "Healthcare Premiums", "amount": hc / 12,
                                 "detail": "monthly cost"})

        # DAF year-end
        if m == 12:
            daf = v("DAF Contribution")
            if daf > 0:
                actions.append({"label": "DAF Contribution", "amount": daf,
                                 "detail": "Year-end charitable giving"})

        months.append({"month": _MONTH_NAMES[m - 1], "month_num": m, "actions": actions})

    return {
        "year": year,
        "months": months,
        "available_years": [int(y) for y in strategy_df["Year"].tolist()],
    }


# ---------------------------------------------------------------------------
# Bucket Strategy
# ---------------------------------------------------------------------------

def bucket_analysis() -> dict[str, Any]:
    try:
        from bucket_strategy import analyze_portfolio_buckets, load_bucket_config, BucketType
        cfg_b = load_bucket_config()
        if not cfg_b.enabled:
            return {"enabled": False}
        summary = analyze_portfolio_buckets()
        holdings = [
            {
                "symbol": h.symbol,
                "name": h.name,
                "value": _jsonable(h.current_value),
                "bucket": h.bucket_assignment.value,
                "asset_class": h.asset_class.value,
            }
            for h in summary.holdings
        ]
        return {
            "enabled": True,
            "bucket1": {"value": _jsonable(summary.bucket_1_value),
                        "target": _jsonable(summary.bucket_1_target),
                        "pct": _jsonable(summary.bucket_1_pct),
                        "drift": _jsonable(summary.get_bucket_drift(BucketType.BUCKET_1_SAFETY))},
            "bucket2": {"value": _jsonable(summary.bucket_2_value),
                        "target": _jsonable(summary.bucket_2_target),
                        "pct": _jsonable(summary.bucket_2_pct),
                        "drift": _jsonable(summary.get_bucket_drift(BucketType.BUCKET_2_TRANSITION))},
            "bucket3": {"value": _jsonable(summary.bucket_3_value),
                        "target": _jsonable(summary.bucket_3_target),
                        "pct": _jsonable(summary.bucket_3_pct),
                        "drift": _jsonable(summary.get_bucket_drift(BucketType.BUCKET_3_GROWTH))},
            "total": _jsonable(summary.total_portfolio_value),
            "needs_rebalancing": bool(summary.needs_rebalancing),
            "holdings": holdings,
        }
    except Exception as exc:
        return {"enabled": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tax Analytics
# ---------------------------------------------------------------------------

def tax_analytics(
    start_year: int | None = None,
    end_year: int = END_YEAR_DEFAULT,
) -> dict[str, Any]:
    with _lock:
        strategy_df, balances_df, cfg = _build_strategy(start_year, end_year)

    def col(name: str) -> "pd.Series":
        return strategy_df[name] if name in strategy_df.columns else pd.Series(0.0, index=strategy_df.index)

    def bcol(name: str) -> "pd.Series":
        return balances_df[name] if name in balances_df.columns else pd.Series(0.0, index=balances_df.index)

    fed = col("Federal Tax").sum()
    state = col("State Tax").sum()
    irmaa = col("IRMAA Penalty").sum()
    payroll = col("Wages→\nPayroll").sum()
    total_income = (col("Wages") + col("SS Benefits") + col("Trad→\nCash") +
                    col("Roth→\nCash") + col("Brok→\nCash")).sum()
    total_taxes = fed + state + irmaa + payroll
    avg_eff_rate = (total_taxes / total_income * 100) if total_income > 0 else 0.0

    # Per-year breakdown for charts
    years_data = []
    for _, row in strategy_df.iterrows():
        agi = _val(row, "AGI")
        year_taxes = _val(row, "Federal Tax") + _val(row, "State Tax") + _val(row, "IRMAA Penalty")
        years_data.append({
            "year":            int(row["Year"]),
            "federal_tax":     _val(row, "Federal Tax"),
            "state_tax":       _val(row, "State Tax"),
            "irmaa":           _val(row, "IRMAA Penalty"),
            "payroll":         _val(row, "Wages→\nPayroll"),
            "agi":             agi,
            "roth_conversion": _val(row, "Trad→\nRoth"),
            "effective_rate":  (year_taxes / agi * 100) if agi > 0 else 0.0,
            # Per-year income series (for stacked bar)
            "wages":           _val(row, "Wages"),
            "ss_benefits":     _val(row, "SS Benefits"),
            "trad_cash":       _val(row, "Trad→\nCash"),
            "roth_cash":       _val(row, "Roth→\nCash"),
            "brok_cash":       _val(row, "Brok→\nCash"),
            "rmd":             _val(row, "RMD"),
        })

    # Income sources totals (for donut)
    income_sources = {
        "Wages":                   float(col("Wages").sum()),
        "Social Security":         float(col("SS Benefits").sum()),
        "Traditional Withdrawals": float(col("Trad→\nCash").sum()),
        "Roth Conversions":        float(col("Trad→\nRoth").sum()),
        "Roth Withdrawals":        float(col("Roth→\nCash").sum()),
        "Brokerage Withdrawals":   float(col("Brok→\nCash").sum()),
        "RMDs":                    float(col("RMD").sum()),
    }

    # Projected balances series (moved here from Long-Term Plan)
    bal_years = [int(y) for y in balances_df["Year"].tolist()]
    balances = {
        "years":       bal_years,
        "cash":        [_jsonable(v) for v in bcol("Cash").tolist()],
        "taxable":     [_jsonable(v) for v in bcol("Taxable").tolist()],
        "traditional": [_jsonable(v) for v in bcol("Traditional").tolist()],
        "roth":        [_jsonable(v) for v in bcol("Roth").tolist()],
        "daf":         [_jsonable(v) for v in bcol("DAF").tolist()],
    }

    return {
        "summary": {
            "total_federal":      _jsonable(fed),
            "total_state":        _jsonable(state),
            "total_irmaa":        _jsonable(irmaa),
            "total_payroll":      _jsonable(payroll),
            "total_taxes":        _jsonable(total_taxes),
            "total_income":       _jsonable(total_income),
            "avg_effective_rate": _jsonable(avg_eff_rate),
            "ss_age":             cfg.get("person1_ss_age", 70),
            "max_roth_rate":      cfg.get("rate", 0.06) * 100,
            "rate_of_return":     cfg.get("rate", 0.06) * 100,
        },
        "income_sources": {k: _jsonable(v) for k, v in income_sources.items() if v and v > 0},
        "years":    years_data,
        "balances": balances,
    }


# ---------------------------------------------------------------------------
# Income & Expense breakdown
# ---------------------------------------------------------------------------

def income_expense(
    start_year: int | None = None,
    end_year: int = END_YEAR_DEFAULT,
) -> dict[str, Any]:
    with _lock:
        strategy_df, _, _ = _build_strategy(start_year, end_year)

    def col(name: str) -> "pd.Series":
        return strategy_df[name] if name in strategy_df.columns else pd.Series(0.0, index=strategy_df.index)

    years = [int(y) for y in strategy_df["Year"].tolist()]
    income = {
        "years": years,
        "wages":        [_jsonable(v) for v in col("Wages").tolist()],
        "ss_benefits":  [_jsonable(v) for v in col("SS Benefits").tolist()],
        "trad_cash":    [_jsonable(v) for v in col("Trad→\nCash").tolist()],
        "roth_cash":    [_jsonable(v) for v in col("Roth→\nCash").tolist()],
        "brok_cash":    [_jsonable(v) for v in col("Brok→\nCash").tolist()],
        "rmd":          [_jsonable(v) for v in col("RMD").tolist()],
        "interest":     [_jsonable(v) for v in col("Interest Income").tolist()],
        "dividends":    [_jsonable(v) for v in col("Dividends").tolist()],
    }
    expenses = {
        "years": years,
        "living":       [_jsonable(v) for v in col("Expenses").tolist()],
        "healthcare":   [_jsonable(v) for v in col("Healthcare Cost").tolist()],
        "federal_tax":  [_jsonable(v) for v in col("Federal Tax").tolist()],
        "state_tax":    [_jsonable(v) for v in col("State Tax").tolist()],
        "irmaa":        [_jsonable(v) for v in col("IRMAA Penalty").tolist()],
        "daf":          [_jsonable(v) for v in col("DAF Contribution").tolist()],
    }
    return {"income": income, "expenses": expenses}
