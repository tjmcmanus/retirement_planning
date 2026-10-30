"""Streamlit-free data for the rest of the Dashboard page.

Mirrors ``pages/3_dashboard.py`` section by section (market forecast tabs, stress indicator,
net worth statement, account / portfolio mix, readiness indicator) so the HTML page shows the
same figures. Where Streamlit has an odd rule it is copied rather than fixed, so the two UIs can
be compared number for number; the odd spots are marked ``PARITY``.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import logging
import os
from typing import Any

import numpy as np
import pandas as pd

from app.services import networth as nw_service
from config import ConfigManager

logger = logging.getLogger(__name__)

GREEN, GREY, RED, AMBER = "#21c354", "#808080", "#ff4b4b", "#ffa500"

# Same three-colour scale as components.theme.Colors.CHART_SCALE (the Streamlit treemaps).
COLOR_SCALE = [[0.0, "rgb(246, 207, 113)"], [0.5, "rgb(180, 151, 231)"], [1.0, "rgb(139, 224, 164)"]]


def _cfg() -> ConfigManager:
    """Fresh read of the config file, so edits made in the other service are seen."""
    return ConfigManager()


# --------------------------------------------------------------------------------------
# Market forecast tabs (Long-term / Intermediate / Short-term)
# --------------------------------------------------------------------------------------

# (condition, subphase) -> (level, text). Anything that is not Accumulation / Consolidating is
# Distribution, as in the Streamlit if/elif chains.
_G = {
    "longterm": {
        ("bull", "Accumulation"): ("success", "18-month trend up, 8-month momentum rising. Favorable for full equity exposure — consider maintaining or adding to allocation."),
        ("bull", "Consolidating"): ("success", "18-month trend up, 8-month momentum flat. Healthy pause in uptrend — hold allocation and wait for momentum to resume."),
        ("bull", "Distribution"): ("warning", "18-month trend up but 8-month momentum fading. Monitor for regime change — avoid increasing equity exposure."),
        ("neutral", "Accumulation"): ("info", "18-month EMA flat, 8-month momentum rising. Possible early bull forming — wait for 18-month confirmation before acting."),
        ("neutral", "Consolidating"): ("info", "Both EMAs flat. Sideways market — maintain current allocation, avoid major strategic shifts."),
        ("neutral", "Distribution"): ("warning", "18-month EMA flat, 8-month momentum falling. Risk of bear transition — consider reducing equity exposure."),
        ("bear", "Accumulation"): ("info", "18-month trend down but 8-month bouncing. Possible relief rally — wait for 18-month EMA to turn before adding exposure."),
        ("bear", "Consolidating"): ("error", "18-month trend down, 8-month flat. Downtrend pausing, not reversing — maintain defensive posture."),
        ("bear", "Distribution"): ("error", "Both EMAs falling. Sustained downtrend — reduce risk exposure; focus on capital preservation."),
    },
    "intermediate": {
        ("bull", "Accumulation"): ("success", "50-week trend up, 10-week momentum rising. Favorable for maintaining or increasing equity exposure."),
        ("bull", "Consolidating"): ("success", "50-week trend up, 10-week momentum flat. Healthy pause — hold allocation; wait for momentum to resume."),
        ("bull", "Distribution"): ("warning", "50-week trend up but 10-week momentum fading. Avoid adding; monitor for transition."),
        ("neutral", "Accumulation"): ("info", "50-week EMA flat, 10-week momentum rising. Possible breakout building — wait for 50-week confirmation."),
        ("neutral", "Consolidating"): ("info", "Both MAs flat. Sideways market — maintain positions; no directional action warranted."),
        ("neutral", "Distribution"): ("warning", "50-week EMA flat, 10-week momentum falling. Risk of breakdown — reduce tactical exposure."),
        ("bear", "Accumulation"): ("info", "50-week trend down but 10-week bouncing. Possible relief rally — wait for 50-week EMA to turn before adding."),
        ("bear", "Consolidating"): ("error", "50-week trend down, 10-week flat. Downtrend pausing — maintain defensive posture."),
        ("bear", "Distribution"): ("error", "Both MAs falling. Reduce tactical risk; focus on capital preservation."),
    },
    "shortterm": {
        ("bull", "Accumulation"): ("success", "50-day trend up, 10-day momentum rising. Favorable for tactical positions — consider maintaining or adding exposure."),
        ("bull", "Consolidating"): ("success", "50-day trend up, 10-day momentum flat. Healthy pause — hold positions; wait for momentum to resume."),
        ("bull", "Distribution"): ("warning", "50-day trend up but 10-day momentum fading. Tighten stop-losses; avoid adding new positions."),
        ("neutral", "Accumulation"): ("info", "50-day EMA flat, 10-day momentum rising. Possible breakout building — wait for 50-day confirmation before committing."),
        ("neutral", "Consolidating"): ("info", "Both EMAs flat. Sideways market — maintain positions; no directional action warranted."),
        ("neutral", "Distribution"): ("warning", "50-day EMA flat, 10-day momentum falling. Risk of breakdown — reduce tactical exposure."),
        ("bear", "Accumulation"): ("info", "50-day trend down but 10-day bouncing. Possible relief rally — not a confirmed reversal; wait for 50-day EMA to turn."),
        ("bear", "Consolidating"): ("error", "50-day trend down, 10-day flat. Downtrend pausing — maintain defensive posture; avoid new long positions."),
        ("bear", "Distribution"): ("error", "Both EMAs falling. Defensive posture; avoid new long positions until trend reverses."),
    },
}

_FORECAST_META = {
    "longterm": dict(
        title="Long-Term",
        blurb=("Strategic market outlook based on 8-month and 18-month exponential moving averages of the S&P 500 (SPY). "
               "This long-term perspective helps inform major portfolio decisions and risk management."),
        short="8-Month", long="18-Month", per="month", decimals=2, count_label="Months in Trend",
        phase_label="Market Cycle Phase", adj_label="Strategic Adjustment",
        detail_title="Detailed Market Analysis", guidance_title="Strategic Guidance", noun="Long-term",
    ),
    "intermediate": dict(
        title="Intermediate-Term",
        blurb=("Tactical market outlook based on 10-week and 50-week moving averages of the S&P 500 (SPY). "
               "This intermediate-term perspective helps inform tactical rebalancing and near-term risk adjustments."),
        short="10-Week", long="50-Week", per="week", decimals=3, count_label="Weeks in Trend",
        phase_label="Momentum Phase", adj_label="Tactical Adjustment",
        detail_title="Detailed Intermediate-Term Analysis", guidance_title="Tactical Guidance", noun="Intermediate-term",
    ),
    "shortterm": dict(
        title="Short-Term",
        blurb=("Tactical market outlook based on 10-day and 50-day exponential moving averages of the S&P 500 (SPY). "
               "This very short-term perspective helps inform day trading, swing trading, and immediate tactical adjustments."),
        short="10-Day", long="50-Day", per="day", decimals=3, count_label="Days in Trend",
        phase_label="Momentum Phase", adj_label="Tactical Adjustment",
        detail_title="Detailed Short-Term Analysis", guidance_title="Tactical Guidance", noun="Short-term",
    ),
}

FORECAST_TIMEFRAMES = tuple(_FORECAST_META)


def _forecast_engine(timeframe: str):
    """Return (condition, ema_data, unknown_enum, error_text, subphase_fn, phase_fn, adjustment) for one tab."""
    if timeframe == "longterm":
        import market_trend_longterm as m

        cfg = m.LongTermMarketTrendConfig()
        cond, data = m.get_longterm_market_condition(cfg, use_cache=True)
        return (cond, data, m.LongTermMarketCondition.UNKNOWN, m.get_last_fetch_error_longterm,
                m.get_market_subphase, m.get_market_cycle_phase,
                lambda: m.get_strategic_allocation_adjustment(cond, cfg))
    if timeframe == "intermediate":
        import market_trend_analysis as m

        cfg = m.MarketTrendConfig()
        cond, data = m.get_market_condition(cfg, use_cache=True)
        return (cond, data, m.MarketCondition.UNKNOWN, m.get_last_fetch_error,
                m.get_market_subphase,
                lambda d: f"{cond.value.title()} ({m.get_market_subphase(d)})",
                lambda: m.get_allocation_adjustment(cond, cfg))
    import market_trend_shortterm as m

    cfg = m.ShortTermMarketTrendConfig()
    cond, data = m.get_shortterm_market_condition(cfg, use_cache=True)
    return (cond, data, m.ShortTermMarketCondition.UNKNOWN, m.get_last_fetch_error_shortterm,
            m.get_market_subphase, m.get_market_momentum_phase,
            lambda: m.get_tactical_allocation_adjustment(cond, cfg))


def market_forecast(timeframe: str) -> dict[str, Any]:
    meta = _FORECAST_META[timeframe]
    base = {"timeframe": timeframe, "title": meta["title"], "blurb": meta["blurb"]}
    try:
        cond, d, unknown, last_error, subphase_fn, phase_fn, adj_fn = _forecast_engine(timeframe)
        if cond == unknown or not d:
            reason = last_error()
            return {**base, "available": False, "message": (
                f"{meta['noun']} market forecast data is currently unavailable. "
                + (f"Reason: {reason}" if reason else
                   "This may be due to market data service issues or network connectivity.")
                + " The forecast will update automatically when data becomes available.")}
        sub = subphase_fn(d)
        colour = {"bull": GREEN, "neutral": GREY, "bear": RED}.get(cond.value, GREY)
        conf = d.confidence * 100
        conf_colour = AMBER if conf <= 5 else colour
        level, text = _G[timeframe][(cond.value, sub if sub in ("Accumulation", "Consolidating") else "Distribution")]
        count = d.months_in_trend if timeframe == "longterm" else (
            d.weeks_in_trend if timeframe == "intermediate" else d.days_in_trend)
        return {
            **base, "available": True,
            "condition": cond.value, "condition_label": f"{cond.value.title()} ({sub})", "colour": colour,
            "phase_label": meta["phase_label"], "phase": phase_fn(d),
            "adjustment_label": meta["adj_label"], "adjustment": adj_fn(),
            "confidence": conf, "confidence_colour": conf_colour,
            "detail_title": meta["detail_title"], "guidance_title": meta["guidance_title"],
            "detail": {
                "short_label": meta["short"], "long_label": meta["long"], "per": meta["per"],
                "slope_decimals": meta["decimals"], "count_label": meta["count_label"],
                "price": d.current_price, "short_ema": d.short_ema, "long_ema": d.long_ema,
                "price_vs_short": d.price_vs_short_ema, "price_vs_long": d.price_vs_long_ema,
                "short_trend": d.short_trend.value.title(), "long_trend": d.long_trend.value.title(),
                "short_slope": d.short_slope, "long_slope": d.long_slope, "count": count,
                "crossover": d.ema_crossover_distance,
                "updated": d.calculation_date.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "guidance": {"level": level, "title": f"{cond.value.title()} ({sub})", "text": text},
        }
    except Exception as exc:
        logger.warning("%s forecast failed", timeframe, exc_info=True)
        return {**base, "available": False,
                "message": f"Could not load {meta['noun'].lower()} market forecast: {exc}"}


# --------------------------------------------------------------------------------------
# Market stress indicator
# --------------------------------------------------------------------------------------

_STRESS_ACTIONS = {
    "CRITICAL": ("error", "CRITICAL STRESS LEVEL", "Immediate Actions",
                 ["Activate portfolio hedges (put options, inverse ETFs)", "Reduce equity exposure to defensive levels",
                  "Increase cash/bond allocation", "Review stop-loss orders on volatile positions",
                  "Consider tax-loss harvesting opportunities"],
                 "Monitor: Check stress indicator daily until it drops below 70"),
    "WARNING": ("warning", "ELEVATED STRESS LEVEL", "Review Actions",
                ["Review portfolio allocation and risk exposure",
                 "Prepare hedge strategies (identify put options, inverse positions)",
                 "Assess cash reserves and liquidity needs", "Review rebalancing opportunities",
                 "Monitor daily for further deterioration"],
                "Threshold: Activate hedges if stress crosses 70"),
    "NORMAL": ("success", "NORMAL MARKET CONDITIONS", "Routine Actions",
               ["Continue normal investment strategy", "Execute planned rebalancing",
                "Consider opportunistic buying", "Review weekly for changes"],
               "Monitoring: Check stress indicator weekly"),
}


def market_stress() -> dict[str, Any]:
    from components.market_stress_indicator import fetch_stress_indicator, get_stress_level_info

    data = fetch_stress_indicator()
    if data is None:
        return {"available": False, "message": "Unable to fetch market stress data. Please try again later."}
    _emoji, colour, status, recommendation = get_stress_level_info(data.stress_index)
    level, title, heading, bullets, footer = _STRESS_ACTIONS[status]
    return {
        "available": True, "stress_index": data.stress_index, "regime": data.regime,
        "sensor_count": data.sensor_count, "status": status, "colour": colour,
        "recommendation": recommendation, "as_of": data.as_of, "methodology": data.methodology,
        "breakdown": {k: int(data.breakdown.get(k, 0)) for k in ("severe", "elevated", "rising", "neutral", "stable")},
        "action": {"level": level, "title": f"{title} ({data.stress_index:.1f}/100)",
                   "heading": heading, "bullets": bullets, "footer": footer},
    }


# --------------------------------------------------------------------------------------
# Net worth statement, account mix, portfolio mix
# --------------------------------------------------------------------------------------

_TYPE_LABELS = {"Savings": "Savings", "Cash": "Cash", "Brokerage": "Investment",
                "Traditional": "Tax Deferred", "Roth": "Tax Free", "Real Estate": "Real Estate"}
_TYPE_ORDER = ["Savings", "Cash", "Brokerage", "Traditional", "Roth", "Real Estate"]
_TYPE_ACCENT = {"Savings": "rgb(135, 206, 250)", "Cash": "rgb(246, 207, 113)", "Brokerage": "rgb(254, 136, 177)",
                "Traditional": "rgb(139, 224, 164)", "Roth": "rgb(180, 151, 231)", "Real Estate": "rgb(255, 190, 122)"}
_TYPE_BG = {"Savings": "rgba(135, 206, 250, 0.35)", "Cash": "rgba(246, 207, 113, 0.35)",
            "Brokerage": "rgba(254, 136, 177, 0.35)", "Traditional": "rgba(139, 224, 164, 0.35)",
            "Roth": "rgba(180, 151, 231, 0.35)", "Real Estate": "rgba(255, 190, 122, 0.35)"}


def _real_estate_rows() -> pd.DataFrame:
    """Same as components.shared._get_real_estate_rows (purchase price is used as the value)."""
    rows = []
    for p in _cfg().get("real_estate", "properties", []) or []:
        rows.append({"account_type": "Real Estate", "account_name": p.get("property_name", "Property"),
                     "market_value": float(p.get("purchase_price", 0) or 0)})
    if not rows:
        return pd.DataFrame({"account_type": pd.Series(dtype=str), "account_name": pd.Series(dtype=str),
                             "market_value": pd.Series(dtype=float)})
    return pd.DataFrame(rows)


def _today_month_year() -> tuple[int, int]:
    today = dt.date.today()
    return today.month, today.year


def net_worth_statement() -> dict[str, Any]:
    from load_data import get_networth_by_month

    networth = nw_service.load_networth_history()
    if len(networth) < 2:
        return {"ready": False, "reason": "Need at least 2 months of data to compute net worth changes."}
    month, year = _today_month_year()
    try:
        detailed, _ = get_networth_by_month(month, year)
    except Exception:
        logger.warning("Failed to load detailed net worth for statement", exc_info=True)
        detailed = pd.DataFrame()
    if detailed.empty:
        return {"ready": False, "reason": "No account detail data available for net worth statement."}

    re_rows = _real_estate_rows()
    combined = pd.concat([detailed, re_rows], ignore_index=True) if not re_rows.empty else detailed
    grouped = combined.groupby(["account_type", "account_name"], as_index=False)["market_value"].sum()

    re_total = float(re_rows["market_value"].sum())
    aug = networth.copy()
    if re_total > 0:
        # PARITY: Streamlit adds real estate to the latest month only, so the statement's change
        # figures include the whole real-estate value. (The KPI cards add it to every month.)
        aug.at[aug.index[-1], "total"] += re_total

    current = float(aug["total"].iloc[-1])
    mom = current - float(aug["total"].iloc[-2])
    idx = pd.DatetimeIndex(aug.index)
    ytd_mask = idx.year == idx[-1].year
    ytd_start = float(aug.loc[ytd_mask, "total"].iloc[0]) if ytd_mask.any() else current
    older = aug.loc[aug.index <= idx[-1] - pd.DateOffset(months=12)]
    roll_start = float(older["total"].iloc[-1]) if not older.empty else float(aug["total"].iloc[0])

    groups = []
    for t in _TYPE_ORDER:
        accts = grouped.loc[grouped["account_type"] == t]
        if accts.empty:
            continue
        groups.append({
            "type": t, "label": _TYPE_LABELS[t], "accent": _TYPE_ACCENT[t], "background": _TYPE_BG[t],
            "total": float(accts["market_value"].sum()),
            "accounts": [{"name": str(r.account_name), "value": float(r.market_value)} for r in accts.itertuples()],
        })
    return {
        "ready": True, "as_of": idx[-1].strftime("%B %Y"), "groups": groups, "total": current,
        "month_change": mom, "ytd_gain": current - ytd_start, "rolling_gain": current - roll_start,
    }


def treemap_nodes(rows: list[tuple[tuple[str, ...], float]]) -> dict[str, Any]:
    """Nodes for a Plotly treemap, matching ``px.treemap(path=..., values=v, color=v)``.

    Values add up the tree. A node's colour is the value-weighted mean of the colour column
    (here the value itself) over its rows, which is what plotly express computes.
    """
    agg: dict[tuple[str, ...], list[float]] = {}
    for path, v in rows:
        for n in range(1, len(path) + 1):
            a = agg.setdefault(path[:n], [0.0, 0.0])
            a[0] += v        # sum of values
            a[1] += v * v    # sum of value * colour
    nodes = [{"id": "/".join(p), "label": p[-1], "parent": "/".join(p[:-1]), "value": a[0],
              "color": (a[1] / a[0]) if a[0] else 0.0} for p, a in agg.items()]
    total = sum(v for _, v in rows)
    mid = (sum(v * v for _, v in rows) / total) if total else 0.0
    return {"nodes": nodes, "midpoint": mid, "colorscale": COLOR_SCALE}


def _stale(month: int, year: int, eff_month: int, eff_year: int) -> dict[str, str] | None:
    if (eff_month, eff_year) == (month, year):
        return None
    return {"requested": f"{calendar.month_name[month]} {year}",
            "showing": f"{calendar.month_name[eff_month]} {eff_year}"}


def account_mix() -> dict[str, Any]:
    from load_data import get_month_account_values
    from portfolio import get_effective_portfolio_month_year

    month, year = _today_month_year()
    eff_m, eff_y = get_effective_portfolio_month_year(month, year)
    df, _, _ = get_month_account_values(eff_m, eff_y)
    stale = _stale(month, year, eff_m, eff_y)
    if df.empty:
        return {"ready": False, "stale": stale, "reason": "No account data available for the current period."}
    df = df.dropna(subset=["market_value"])
    rows = [((str(r.account_type), str(r.account_name)), float(r.market_value)) for r in df.itertuples()]
    return {"ready": True, "stale": stale, "title": "Account Mix Breakdown", **treemap_nodes(rows)}


def _portfolio_frame(month: int, year: int) -> pd.DataFrame:
    """On-disk portfolio display cache if still valid (see portfolio.load_portfolio_cache), else build it (live prices) and save it."""
    from portfolio import build_portfolio_display, load_portfolio_cache, save_portfolio_cache

    cached = load_portfolio_cache(month, year)
    if not cached.empty:
        return cached
    built = build_portfolio_display(month=month, year=year)
    if not built.empty:
        save_portfolio_cache(built, month, year)
    return built


def portfolio_mix() -> dict[str, Any]:
    from portfolio import get_effective_portfolio_month_year

    month, year = _today_month_year()
    eff_m, eff_y = get_effective_portfolio_month_year(month, year)
    stale = _stale(month, year, eff_m, eff_y)
    port = _portfolio_frame(eff_m, eff_y)
    port = port[port["Account"] != "Portfolio Totals"] if not port.empty else port
    if port.empty:
        return {"ready": False, "stale": stale,
                "reason": "No portfolio data available. Please add portfolio data via Portfolio Data Entry."}
    port = port[port["Sector"].notna() & (port["Sector"] != "")]
    if port.empty:
        return {"ready": False, "stale": stale, "reason": "No sector data available for portfolio mix chart."}
    port = port.dropna(subset=["Current value"])
    rows = [((str(r["Tax Type"]), str(r["Sector"])), float(r["Current value"])) for _, r in port.iterrows()]
    return {"ready": True, "stale": stale, "title": "Portfolio Mix", **treemap_nodes(rows)}


# --------------------------------------------------------------------------------------
# Financial Plan Readiness Indicator
# --------------------------------------------------------------------------------------

WEIGHTS = [0.35, 0.20, 0.15, 0.10, 0.10, 0.10]


def _rri_colour(score: float) -> str:
    return GREEN if score >= 75 else (AMBER if score >= 50 else RED)


def _rri_label(score: float) -> str:
    return "On Track" if score >= 75 else ("Needs Attention" if score >= 50 else "Action Required")


def _estate_progress() -> tuple[float, int, int, dict]:
    """(score, done, total, assessment) from estate_planning_data.json (in the working directory)."""
    if not os.path.exists("estate_planning_data.json"):
        return 0.0, 0, 0, {}
    with open("estate_planning_data.json") as f:
        data = json.load(f)

    def count(d: dict) -> tuple[int, int]:
        tot = done = 0
        for v in d.values():
            if isinstance(v, dict):
                if "done" in v:
                    tot += 1
                    done += 1 if v["done"] else 0
                else:
                    s_done, s_tot = count(v)
                    done += s_done
                    tot += s_tot
        return done, tot

    done, tot = count(data)
    assess = data.get("assessment", {})
    core = sum(1 for k in ("has_will", "has_poa", "has_healthcare_directive", "beneficiaries_current") if assess.get(k, False))
    score = min((done / tot * 70 if tot > 0 else 0) + (core / 4 * 30), 100)
    return score, done, tot, assess


def readiness() -> dict[str, Any]:
    networth = nw_service.load_networth_history()
    if networth.empty or len(networth) < 2:
        return {"ready": False, "reason": "Insufficient historical data. Need at least 2 months of portfolio data."}
    try:
        return _readiness(networth)
    except Exception as exc:
        logger.warning("Readiness indicator failed", exc_info=True)
        return {"ready": False, "reason": f"Could not compute retirement readiness indicator: {exc}"}


def _readiness(networth: pd.DataFrame) -> dict[str, Any]:
    cfg = _cfg()
    re_total = float(_real_estate_rows()["market_value"].sum())
    current_nw = float(networth["total"].iloc[-1]) + re_total

    annual_exp = float(cfg.get("financial_assumptions", "expected_annual_expenses", 50_000) or 50_000)
    target_port = annual_exp * 25.0
    try:
        re_purchase = sum(float(p.get("purchase_price", 0) or 0) for p in cfg.get("real_estate", "properties", []) or [])
    except Exception:
        re_purchase = 0.0
    # PARITY: current_nw already includes real estate; Streamlit adds it again here.
    total_assets = current_nw + re_purchase
    funding_pct = min(total_assets / target_port * 100, 100) if target_port > 0 else 0.0
    funding_score = funding_pct

    try:
        estate_score, ep_done, ep_tot, assess = _estate_progress()
    except Exception:
        logger.warning("Failed to compute estate planning score", exc_info=True)
        estate_score, ep_done, ep_tot, assess = 0.0, 0, 0, {}

    trad = float(networth["tax_deferred"].iloc[-1])
    roth = float(networth["tax_free"].iloc[-1])
    roth_r = (roth / (roth + trad) * 100) if (roth + trad) > 0 else 0.0
    tax_div_score = max(0.0, 100.0 - abs(roth_r - 40.0) * 2.5)

    p1_ssi = float(cfg.get("social_security", "person1_ssi_amount", 0) or 0)
    p2_ssi = float(cfg.get("social_security", "person2_ssi_amount", 0) or 0)
    ssi_score = 100.0 if (p1_ssi > 0 and p2_ssi > 0) else (50.0 if (p1_ssi > 0 or p2_ssi > 0) else 0.0)

    h = lambda k, d=None: cfg.get("healthcare", k, d)  # noqa: E731
    p = {}
    for n in ("1", "2"):
        pre_type, pre_amt = h(f"person{n}_preretirement_coverage_type", "None"), float(h(f"person{n}_preretirement_insurance_monthly", 0) or 0)
        ret_type, ret_amt = h(f"person{n}_retirement_coverage_type", "None"), float(h(f"person{n}_aca_insurance_monthly", 0) or 0)
        reviewed, eligible = h(f"person{n}_reviewed_medicare_guide", False), h(f"person{n}_medicare_eligible", False)
        p[n] = dict(pre=(pre_type != "None" and pre_amt > 0), ret=(ret_type != "None" and ret_amt > 0),
                    reviewed=reviewed, eligible=eligible, ret_type=ret_type,
                    medicare=bool(reviewed and eligible))
        p[n]["full"] = p[n]["pre"] and p[n]["ret"] and p[n]["medicare"]
    if p["1"]["full"] and p["2"]["full"]:
        hc_score = 100.0
    elif p["1"]["full"] or p["2"]["full"]:
        hc_score = 80.0
    elif (p["1"]["pre"] or p["1"]["ret"]) and (p["2"]["pre"] or p["2"]["ret"]):
        hc_score = 60.0
    elif p["1"]["pre"] or p["1"]["ret"] or p["2"]["pre"] or p["2"]["ret"]:
        hc_score = 40.0
    else:
        hc_score = 20.0
    using_aca = p["1"]["ret_type"] == "ACA Marketplace" or p["2"]["ret_type"] == "ACA Marketplace"

    target_months = int(cfg.get("financial_assumptions", "accumulation_cash_buffer_months", 6) or 6)
    wages = float(cfg.get("income", "person1_annual_wages", 0) or 0) + float(cfg.get("income", "person2_annual_wages", 0) or 0)
    cash_bal = float(networth["cash"].iloc[-1])
    yrs_cash = float(cfg.get("financial_assumptions", "years_of_expenses_in_cash", 4) or 4)
    cash_target_ret = annual_exp * yrs_cash
    cash_target = wages * target_months / 12 if wages > 0 else cash_target_ret
    cash_score = min(cash_bal / cash_target * 100, 100) if cash_target > 0 else 50.0

    scores = [funding_score, estate_score, tax_div_score, ssi_score, hc_score, cash_score]
    overall = sum(w * s for w, s in zip(WEIGHTS, scores))

    ssi_detail = ("Both persons configured" if ssi_score == 100 else
                  "One person configured" if ssi_score == 50 else "Not configured — add SSI amounts in Settings")
    if hc_score == 100:
        hc_detail = "Both people fully covered (pre-retirement, retirement & Medicare planning complete)"
        if using_aca:
            hc_detail += " (includes ACA)"
    elif hc_score == 80:
        hc_detail = "One person fully covered including Medicare, complete coverage for second person"
    elif hc_score == 60:
        hc_detail = "Both people have partial coverage, complete Medicare planning"
    elif hc_score == 40:
        hc_detail = "One person partially covered, add coverage and Medicare planning"
    else:
        hc_detail = "Configure healthcare coverage and Medicare planning in Settings"

    indicators = [
        ("funding", "Portfolio Funding", funding_score, f"{funding_pct:.0f}% of 25x expenses target  (${total_assets:,.0f} / ${target_port:,.0f})"),
        ("estate", "Estate Planning", estate_score, f"{ep_done if estate_score > 0 else 0} of {ep_tot if estate_score > 0 else '?'} checklist items complete"),
        ("tax", "Tax Diversification", tax_div_score, f"Roth ratio {roth_r:.0f}%  (target 30-50%)"),
        ("ssi", "Social Security", ssi_score, ssi_detail),
        ("health", "Healthcare Coverage", hc_score, hc_detail),
        ("cash", "Cash / Emergency Fund", cash_score, f"${cash_bal:,.0f} vs ${cash_target:,.0f} target"),
    ]

    n1 = cfg.get("personal_info", "person1_name", "Person 1")
    n2 = cfg.get("personal_info", "person2_name", "Person 2")
    actions: list[dict[str, str]] = []
    if funding_score < 75:
        gap = target_port - total_assets
        pct = (total_assets / target_port * 100) if target_port > 0 else 0
        actions.append({"title": f"Portfolio Funding ({pct:.0f}% complete)", "text": (
            f"You need ${gap:,.0f} more to reach your 25x expenses target of ${target_port:,.0f}. "
            f"Current total assets: ${total_assets:,.0f}. Continue saving and investing to close this gap.")})
    if estate_score < 50:
        pct = (ep_done / ep_tot * 100) if ep_tot > 0 else 0
        mark = lambda k: "✓" if assess.get(k) else "✗"  # noqa: E731
        actions.append({"title": f"Estate Planning ({pct:.0f}% complete)", "text": (
            f"You have completed {ep_done} of {ep_tot} checklist items. Visit the Estate Planning page to review and "
            f"complete remaining items. Core documents status: Will ({mark('has_will')}), POA ({mark('has_poa')}), "
            f"Healthcare Directive ({mark('has_healthcare_directive')}), Beneficiaries Current ({mark('beneficiaries_current')}).")})
    if tax_div_score < 50:
        side = ("is below the recommended 30-50% range. Consider Roth conversions to increase tax-free assets."
                if roth_r < 30 else
                "is above the recommended 30-50% range. Ensure you have sufficient Traditional assets for tax-efficient withdrawals.")
        actions.append({"title": f"Tax Diversification (Roth ratio: {roth_r:.0f}%)", "text": (
            f"Your Roth ratio {side} Current: ${roth:,.0f} Roth vs ${trad:,.0f} Traditional.")})
    if ssi_score < 100:
        s1 = f"${p1_ssi:,.0f}/month at age {cfg.get('social_security', 'person1_ssi_age', 70)}" if p1_ssi > 0 else "Not configured"
        s2 = f"${p2_ssi:,.0f}/month at age {cfg.get('social_security', 'person2_ssi_age', 70)}" if p2_ssi > 0 else "Not configured"
        actions.append({"title": f"Social Security ({ssi_score:.0f}% complete)", "text": (
            f"{n1}: {s1}. {n2}: {s2}. Add SSI benefit amounts in Settings → Social Security to complete your retirement income plan.")})
    if hc_score < 100:
        missing = []
        for n, name in (("1", n1), ("2", n2)):
            q = p[n]
            if not q["pre"]:
                missing.append(f"{name}'s pre-retirement coverage (while working)")
            if not q["ret"]:
                missing.append(f"{name}'s retirement coverage (post-retirement, pre-Medicare)")
            if not q["medicare"]:
                if not q["reviewed"]:
                    missing.append(f"{name} needs to review Medicare Enrollment Guide")
                if not q["eligible"]:
                    missing.append(f"{name} needs to indicate Medicare eligibility status")
        if missing:
            actions.append({"title": f"Healthcare Coverage ({hc_score:.0f}% complete)", "text": (
                f"Missing: {'; '.join(missing)}. Go to Settings → Healthcare to select coverage types (Employer, ACA "
                f"Marketplace, or Employer Retiree), enter monthly premium amounts, and complete Medicare planning. "
                f"Review the Medicare Enrollment Guide in Advanced Strategies page for comprehensive Medicare information.")})
    if cash_score < 50:
        monthly = annual_exp / 12
        cash_months = (cash_bal / monthly) if annual_exp > 0 else 0
        tgt_months = (cash_target / monthly) if annual_exp > 0 else 0
        actions.append({"title": f"Cash/Emergency Fund ({cash_score:.0f}% complete)", "text": (
            f"Current balance: ${cash_bal:,.0f} ({cash_months:.1f} months of expenses). "
            f"Target: ${cash_target:,.0f} ({tgt_months:.1f} months). "
            f"Build your emergency fund by ${cash_target - cash_bal:,.0f} to provide adequate liquidity buffer.")})

    return {
        "ready": True, "overall": overall, "label": _rri_label(overall), "colour": _rri_colour(overall),
        "indicators": [{"key": k, "name": n, "score": s, "colour": _rri_colour(s), "detail": d}
                       for k, n, s, d in indicators],
        "actions": actions,
    }
