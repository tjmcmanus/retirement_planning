"""
Tax Loss/Gain Harvesting (Stock Indexing) Strategy Module  # noqa: E501
=========================================================
Analyzes the taxable (Brokerage) account holdings to identify:
  - Long-term capital gains/losses (held > 1 year)
  - Short-term capital gains/losses (held <= 1 year)
  - Opportunities to harvest gains at 0% LTCG rate
  - Opportunities to harvest losses to offset gains or ordinary income
  - Wash-sale-safe replacement security recommendations

Key concepts:
  - Stock Indexing / Tax-Loss Harvesting: Sell a losing position, immediately
    buy a similar (but not "substantially identical") security to maintain
    market exposure while booking the loss.
  - Gain Harvesting: When LTCG rate is 0%, realize gains tax-free and reset
    cost basis higher.
  - Wash Sale Rule: You cannot repurchase the same (or substantially identical)
    security within 30 days before or after the sale.

Only TAXABLE (Brokerage) accounts are analyzed — gains/losses in Traditional
and Roth accounts have no current-year tax consequence.

MF:CASH is treated as cash/money-market (no gain/loss analysis needed).
"""

from __future__ import annotations

import datetime
from typing import Optional, cast

import pandas as pd
import streamlit as st

from load_data import get_cap_gains_brackets  # noqa: F401
from portfolio import getPortfolioData, get_current_price

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASH_SYMBOL = "MF:CASH"
BROKERAGE_ACCOUNT_TYPE = "Brokerage"

# Holding-period threshold in days (IRS: > 1 year = long-term)
LONG_TERM_DAYS = 365

# ---------------------------------------------------------------------------
# Wash-sale replacement map
# Similar-but-not-identical substitutes keyed by symbol.
# These are curated to maintain sector/factor exposure while avoiding the
# wash-sale rule.  The list is intentionally conservative — always verify
# with a tax professional.
# ---------------------------------------------------------------------------
WASH_SALE_REPLACEMENTS: dict[str, list[dict]] = {
    # ── Technology ──────────────────────────────────────────────────────────
    "GOOGL": [
        {"symbol": "META",  "name": "Meta Platforms",        "reason": "Large-cap internet/ad tech"},
        {"symbol": "MSFT",  "name": "Microsoft",             "reason": "Large-cap technology"},
        {"symbol": "AMZN",  "name": "Amazon",                "reason": "Large-cap tech/e-commerce"},
    ],
    "META": [
        {"symbol": "GOOGL", "name": "Alphabet Class A",      "reason": "Large-cap internet/ad tech"},
        {"symbol": "SNAP",  "name": "Snap Inc.",             "reason": "Social media"},
        {"symbol": "PINS",  "name": "Pinterest",             "reason": "Social media / visual search"},
    ],
    "NVDA": [
        {"symbol": "AMD",   "name": "Advanced Micro Devices","reason": "Semiconductor / GPU competitor"},
        {"symbol": "INTC",  "name": "Intel",                 "reason": "Semiconductor"},
        {"symbol": "SOXX",  "name": "iShares Semiconductor ETF", "reason": "Broad semiconductor exposure"},
    ],
    "TSLA": [
        {"symbol": "RIVN",  "name": "Rivian Automotive",     "reason": "EV manufacturer"},
        {"symbol": "NIO",   "name": "NIO Inc.",              "reason": "EV manufacturer (China)"},
        {"symbol": "LCID",  "name": "Lucid Group",           "reason": "EV manufacturer"},
    ],
    "NFLX": [
        {"symbol": "DIS",   "name": "Walt Disney",           "reason": "Streaming / entertainment"},
        {"symbol": "PARA",  "name": "Paramount Global",      "reason": "Streaming / media"},
        {"symbol": "WBD",   "name": "Warner Bros. Discovery","reason": "Streaming / media"},
    ],
    "IBM": [
        {"symbol": "ORCL",  "name": "Oracle",                "reason": "Enterprise software / cloud"},
        {"symbol": "HPE",   "name": "Hewlett Packard Enterprise", "reason": "Enterprise IT"},
        {"symbol": "CSCO",  "name": "Cisco Systems",         "reason": "Enterprise networking / IT"},
    ],
    # ── Healthcare ──────────────────────────────────────────────────────────
    "JNJ": [
        {"symbol": "ABT",   "name": "Abbott Laboratories",   "reason": "Diversified healthcare"},
        {"symbol": "MDT",   "name": "Medtronic",             "reason": "Medical devices"},
        {"symbol": "PFE",   "name": "Pfizer",                "reason": "Large-cap pharma"},
    ],
    # ── Consumer Defensive ──────────────────────────────────────────────────
    "KO": [
        {"symbol": "PEP",   "name": "PepsiCo",               "reason": "Beverage / consumer staples"},
        {"symbol": "MDLZ",  "name": "Mondelez International","reason": "Consumer staples / snacks"},
        {"symbol": "KHC",   "name": "Kraft Heinz",           "reason": "Consumer staples"},
    ],
    "PG": [
        {"symbol": "CL",    "name": "Colgate-Palmolive",     "reason": "Consumer staples / personal care"},
        {"symbol": "KMB",   "name": "Kimberly-Clark",        "reason": "Consumer staples"},
        {"symbol": "CHD",   "name": "Church & Dwight",       "reason": "Consumer staples"},
    ],
    # ── Communication Services ──────────────────────────────────────────────
    "T": [
        {"symbol": "VZ",    "name": "Verizon",               "reason": "Telecom competitor"},
        {"symbol": "TMUS",  "name": "T-Mobile US",           "reason": "Telecom competitor"},
        {"symbol": "LUMN",  "name": "Lumen Technologies",    "reason": "Telecom"},
    ],
    "VZ": [
        {"symbol": "T",     "name": "AT&T",                  "reason": "Telecom competitor"},
        {"symbol": "TMUS",  "name": "T-Mobile US",           "reason": "Telecom competitor"},
        {"symbol": "LUMN",  "name": "Lumen Technologies",    "reason": "Telecom"},
    ],
    # ── Real Estate ─────────────────────────────────────────────────────────
    "OPEN": [
        {"symbol": "Z",     "name": "Zillow Group",          "reason": "Real estate tech / marketplace"},
        {"symbol": "RDFN",  "name": "Redfin",                "reason": "Real estate tech / brokerage"},
        {"symbol": "VNQ",   "name": "Vanguard Real Estate ETF", "reason": "Broad REIT exposure"},
    ],
    # ── Mutual Fund / Index fallbacks ────────────────────────────────────────
    "VFIAX": [
        {"symbol": "FXAIX", "name": "Fidelity 500 Index Fund","reason": "S&P 500 index (different fund family)"},
        {"symbol": "IVV",   "name": "iShares Core S&P 500 ETF","reason": "S&P 500 ETF"},
        {"symbol": "VOO",   "name": "Vanguard S&P 500 ETF",  "reason": "S&P 500 ETF"},
    ],
    "VEXAX": [
        {"symbol": "FSMAX", "name": "Fidelity Extended Market Index","reason": "Extended market (different fund family)"},
        {"symbol": "VXF",   "name": "Vanguard Extended Market ETF","reason": "Extended market ETF"},
    ],
    "VSMAX": [
        {"symbol": "FSSNX", "name": "Fidelity Small Cap Index","reason": "Small-cap index (different fund family)"},
        {"symbol": "VB",    "name": "Vanguard Small-Cap ETF", "reason": "Small-cap ETF"},
        {"symbol": "IJR",   "name": "iShares Core S&P Small-Cap ETF","reason": "Small-cap ETF"},
    ],
}

# Default replacement for symbols not in the map
DEFAULT_REPLACEMENT = [
    {"symbol": "SPY",  "name": "SPDR S&P 500 ETF",          "reason": "Broad market exposure"},
    {"symbol": "VTI",  "name": "Vanguard Total Stock Market","reason": "Total market exposure"},
]

# ---------------------------------------------------------------------------
# Holding-period estimation
# ---------------------------------------------------------------------------

def _estimate_purchase_date(month: int, year: int) -> datetime.date:
    """
    Estimate the purchase date from the portfolio snapshot month/year.
    We use the 1st of the month as a conservative estimate.
    """
    return datetime.date(year, month, 1)


def _holding_period_days(purchase_date: datetime.date, as_of: Optional[datetime.date] = None) -> int:
    """Return the number of days a position has been held."""
    if as_of is None:
        as_of = datetime.date.today()
    return (as_of - purchase_date).days


def _gain_type(days_held: int) -> str:
    """Return 'Long-Term' or 'Short-Term' based on holding period."""
    return "Long-Term" if days_held > LONG_TERM_DAYS else "Short-Term"


# ---------------------------------------------------------------------------
# LTCG bracket helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_ltcg_rate_for_income(agi: float, year: int) -> float:
    """
    Return the applicable LTCG rate (0.0, 0.15, or 0.20) for a given AGI and year.
    Uses the cap_gains.csv brackets (MFJ thresholds).
    """
    brackets = cast(pd.DataFrame, get_cap_gains_brackets(year))
    if brackets.empty:
        return 0.15  # fallback
    for _, row in brackets.sort_values(by="lower").iterrows():
        if agi <= float(row["upper"]):
            return float(row["rate"])
    return 0.20


def get_ltcg_zero_threshold(year: int) -> float:
    """Return the upper income limit for the 0% LTCG bracket."""
    brackets = cast(pd.DataFrame, get_cap_gains_brackets(year))
    if brackets.empty:
        return 96700.0
    zero_rows = cast(pd.DataFrame, brackets[brackets["rate"] == 0])
    if zero_rows.empty:
        return 0.0
    return float(zero_rows["upper"].max())


# ---------------------------------------------------------------------------
# Core analysis: build the brokerage gain/loss table
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def build_harvesting_analysis(month: int, year: int) -> pd.DataFrame:
    """
    Build a DataFrame of all TAXABLE (Brokerage) holdings with:
      - Current price, current value, cost basis
      - Unrealized gain/loss (dollar and %)
      - Holding period (days) and gain type (LT / ST)
      - Harvest recommendation (Harvest Gain / Harvest Loss / Hold)
      - Wash-sale replacement suggestions

    Args:
        month: Portfolio snapshot month
        year:  Portfolio snapshot year

    Returns:
        pd.DataFrame with one row per brokerage holding (excluding MF:CASH)
    """
    portfolio = getPortfolioData(month=month, year=year)

    # Filter to Brokerage accounts only
    brokerage = cast(pd.DataFrame, portfolio[portfolio["account_type"] == BROKERAGE_ACCOUNT_TYPE].copy())

    # Exclude cash
    brokerage = cast(pd.DataFrame, brokerage[brokerage["symbol"] != CASH_SYMBOL].copy())

    if brokerage.empty:
        return pd.DataFrame()

    rows = []
    today = datetime.date.today()

    for _, row in brokerage.iterrows():
        symbol       = str(row["symbol"])
        account_name = str(row["account_name"])
        qty          = float(row["qty"])
        purchase_px  = float(row["purchase_price"])

        # Current market price
        try:
            current_px = get_current_price(symbol)
        except Exception:
            current_px = purchase_px  # fallback to cost if price unavailable

        current_value = qty * current_px
        cost_basis    = qty * purchase_px
        unrealized_gl = current_value - cost_basis
        pct_return    = (unrealized_gl / cost_basis * 100) if cost_basis != 0 else 0.0

        # Holding period — use snapshot month/year as proxy for purchase date
        purchase_date = _estimate_purchase_date(month, year)
        days_held     = _holding_period_days(purchase_date, as_of=today)
        gain_type     = _gain_type(days_held)

        # Replacement suggestions
        replacements: list[dict] = WASH_SALE_REPLACEMENTS.get(symbol, DEFAULT_REPLACEMENT)  # type: ignore[assignment]
        replacement_str = ", ".join(
            f"{r['symbol']} ({r['reason']})" for r in replacements[:2]
        )

        rows.append({
            "Account":          account_name,
            "Symbol":           symbol,
            "Name":             row.get("name", symbol),
            "Sector":           row.get("sector", ""),
            "Qty":              qty,
            "Purchase Price":   purchase_px,
            "Current Price":    current_px,
            "Current Value":    current_value,
            "Cost Basis":       cost_basis,
            "Unrealized G/L":   unrealized_gl,
            "Return %":         pct_return,
            "Days Held":        days_held,
            "Gain Type":        gain_type,
            "Replacements":     replacement_str,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Sort: losses first (most negative), then gains (most positive)
    df = df.sort_values("Unrealized G/L", ascending=True).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Harvest opportunity classifier
# ---------------------------------------------------------------------------

def classify_harvest_opportunities(
    analysis_df: pd.DataFrame,
    estimated_agi: float,
    year: int,
    loss_threshold: float = -500.0,
    gain_threshold: float = 500.0,
) -> pd.DataFrame:
    """
    Add a 'Recommendation' column to the analysis DataFrame.

    Rules:
      - HARVEST GAIN  → position has LT gain AND current LTCG rate is 0%
      - HARVEST LOSS  → position has unrealized loss > |loss_threshold|
                        (useful to offset gains or up to $3,000 of ordinary income)
      - MONITOR       → position is close to a threshold but not actionable yet
      - HOLD          → no immediate action recommended

    Args:
        analysis_df:    Output of build_harvesting_analysis()
        estimated_agi:  User's estimated AGI for the current year (before harvesting)
        year:           Tax year
        loss_threshold: Dollar loss below which harvesting is recommended (negative number)
        gain_threshold: Dollar gain above which gain harvesting is considered

    Returns:
        DataFrame with added 'Recommendation', 'LTCG Rate', 'Action Detail' columns
    """
    if analysis_df.empty:
        return analysis_df

    df = analysis_df.copy()
    ltcg_rate = get_ltcg_rate_for_income(estimated_agi, year)
    zero_threshold = get_ltcg_zero_threshold(year)
    headroom_to_zero = max(0.0, zero_threshold - estimated_agi)

    recommendations = []
    action_details  = []

    for _, row in df.iterrows():
        gl        = float(row["Unrealized G/L"])
        gain_type = row["Gain Type"]

        if gl <= loss_threshold:
            # Loss harvesting opportunity
            rec    = "🔴 Harvest Loss"
            detail = (
                f"Sell to realize ${abs(gl):,.0f} loss. "
                f"Replace with wash-sale-safe alternative within same day. "
                f"Loss offsets gains or up to $3,000 of ordinary income."
            )
        elif gl >= gain_threshold and gain_type == "Long-Term" and ltcg_rate == 0.0:
            # Gain harvesting at 0% — reset cost basis tax-free
            rec    = "🟢 Harvest Gain (0% LTCG)"
            detail = (
                f"Sell to realize ${gl:,.0f} LT gain at 0% rate. "
                f"Repurchase same security to reset cost basis higher. "
                f"Remaining 0% headroom: ${headroom_to_zero:,.0f}."
            )
        elif gl >= gain_threshold and gain_type == "Long-Term" and ltcg_rate == 0.15:
            rec    = "🟡 Monitor (15% LTCG)"
            detail = (
                f"LT gain of ${gl:,.0f} would be taxed at 15%. "
                f"Consider deferring or offsetting with harvested losses. "
                f"Need ${headroom_to_zero:,.0f} income reduction for 0% rate."
            )
        elif gl >= gain_threshold and gain_type == "Short-Term":
            rec    = "🟡 Monitor (ST — Ordinary Rate)"
            detail = (
                f"ST gain of ${gl:,.0f} taxed as ordinary income. "
                f"Wait for long-term treatment (hold {max(0, LONG_TERM_DAYS - int(row['Days Held']))} more days)."
            )
        elif abs(gl) < abs(loss_threshold) and gl < 0:
            rec    = "⚪ Small Loss — Monitor"
            detail = f"Loss of ${abs(gl):,.0f} is below harvest threshold. Monitor for larger decline."
        elif 0 <= gl < gain_threshold:
            rec    = "⚪ Small Gain — Hold"
            detail = f"Gain of ${gl:,.0f} is below harvest threshold. Hold position."
        else:
            rec    = "⚪ Hold"
            detail = "No immediate harvesting action recommended."

        recommendations.append(rec)
        action_details.append(detail)

    df["Recommendation"] = recommendations
    df["Action Detail"]  = action_details
    df["LTCG Rate"]      = f"{ltcg_rate:.0%}"
    df["0% Headroom"]    = headroom_to_zero

    return df


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def compute_harvest_summary(classified_df: pd.DataFrame) -> dict:
    """
    Compute summary statistics for the harvesting analysis.

    Returns a dict with:
      total_unrealized_gain, total_unrealized_loss, net_unrealized,
      harvestable_losses, harvestable_gains_at_zero,
      num_loss_candidates, num_gain_candidates
    """
    if classified_df.empty:
        return {
            "total_unrealized_gain":      0.0,
            "total_unrealized_loss":      0.0,
            "net_unrealized":             0.0,
            "harvestable_losses":         0.0,
            "harvestable_gains_at_zero":  0.0,
            "num_loss_candidates":        0,
            "num_gain_candidates":        0,
            "ltcg_rate":                  "N/A",
            "zero_headroom":              0.0,
        }

    gains  = classified_df[classified_df["Unrealized G/L"] > 0]["Unrealized G/L"].sum()
    losses = classified_df[classified_df["Unrealized G/L"] < 0]["Unrealized G/L"].sum()

    loss_mask = classified_df["Recommendation"].str.startswith("🔴")
    gain_mask = classified_df["Recommendation"].str.startswith("🟢")

    harvestable_losses        = classified_df.loc[loss_mask, "Unrealized G/L"].sum()
    harvestable_gains_at_zero = classified_df.loc[gain_mask, "Unrealized G/L"].sum()

    ltcg_rate    = classified_df["LTCG Rate"].iloc[0]   if not classified_df.empty else "N/A"
    zero_headroom = float(classified_df["0% Headroom"].iloc[0]) if not classified_df.empty else 0.0

    return {
        "total_unrealized_gain":      float(gains),
        "total_unrealized_loss":      float(losses),
        "net_unrealized":             float(gains + losses),
        "harvestable_losses":         float(harvestable_losses),
        "harvestable_gains_at_zero":  float(harvestable_gains_at_zero),
        "num_loss_candidates":        int(loss_mask.sum()),
        "num_gain_candidates":        int(gain_mask.sum()),
        "ltcg_rate":                  ltcg_rate,
        "zero_headroom":              zero_headroom,
    }


# ---------------------------------------------------------------------------
# Market-drop trigger analysis
# ---------------------------------------------------------------------------

def check_market_drop_trigger(
    analysis_df: pd.DataFrame,
    drop_threshold_pct: float = 10.0,
) -> dict:
    """
    Identify positions that have dropped >= drop_threshold_pct from cost basis.
    This simulates the "SP500 drops 10%" trigger for loss harvesting.

    Returns a dict with:
      triggered: bool
      candidates: DataFrame of positions meeting the threshold
      message: str
    """
    if analysis_df.empty:
        return {"triggered": False, "candidates": pd.DataFrame(), "message": "No brokerage holdings found."}

    threshold = -abs(drop_threshold_pct)
    candidates = analysis_df[analysis_df["Return %"] <= threshold].copy()

    if candidates.empty:
        return {
            "triggered": False,
            "candidates": candidates,
            "message": f"No positions have declined ≥ {drop_threshold_pct:.0f}% from cost basis.",
        }

    total_loss = candidates["Unrealized G/L"].sum()
    return {
        "triggered": True,
        "candidates": candidates,
        "message": (
            f"⚠️ {len(candidates)} position(s) have declined ≥ {drop_threshold_pct:.0f}% from cost basis. "
            f"Total harvestable loss: ${abs(total_loss):,.0f}."
        ),
    }


# ---------------------------------------------------------------------------
# Wash-sale replacement detail
# ---------------------------------------------------------------------------

def get_replacement_detail(symbol: str) -> list[dict]:
    """Return the full list of wash-sale-safe replacement suggestions for a symbol."""
    return WASH_SALE_REPLACEMENTS.get(symbol, DEFAULT_REPLACEMENT)


# ---------------------------------------------------------------------------
# Tax-year gain/loss netting
# ---------------------------------------------------------------------------

def compute_net_tax_impact(
    classified_df: pd.DataFrame,
    estimated_agi: float,
    year: int,
    marginal_ordinary_rate: float = 0.22,
) -> dict:
    """
    Estimate the tax impact of executing all recommended harvesting actions.

    Assumptions:
      - Harvested losses first offset harvested gains (netting)
      - Remaining net loss offsets up to $3,000 of ordinary income
      - Remaining net gain taxed at applicable LTCG rate

    Returns a dict with estimated tax savings / liability.
    """
    if classified_df.empty:
        return {}

    ltcg_rate = get_ltcg_rate_for_income(estimated_agi, year)

    loss_mask = classified_df["Recommendation"].str.startswith("🔴")
    gain_mask = classified_df["Recommendation"].str.startswith("🟢")

    total_losses = abs(classified_df.loc[loss_mask, "Unrealized G/L"].sum())
    total_gains  = classified_df.loc[gain_mask, "Unrealized G/L"].sum()

    net = total_gains - total_losses  # positive = net gain, negative = net loss

    if net >= 0:
        # Net gain — taxed at LTCG rate
        tax_on_gains = net * ltcg_rate
        ordinary_offset = 0.0
        ordinary_savings = 0.0
        net_tax_impact = -tax_on_gains  # negative = tax owed
    else:
        # Net loss — offset up to $3,000 of ordinary income
        tax_on_gains = 0.0
        ordinary_offset = min(abs(net), 3000.0)
        ordinary_savings = ordinary_offset * marginal_ordinary_rate
        net_tax_impact = ordinary_savings  # positive = tax savings

    return {
        "total_harvestable_losses":  total_losses,
        "total_harvestable_gains":   total_gains,
        "net_position":              net,
        "ltcg_rate":                 ltcg_rate,
        "tax_on_net_gains":          tax_on_gains,
        "ordinary_income_offset":    ordinary_offset,
        "ordinary_income_savings":   ordinary_savings,
        "net_tax_impact":            net_tax_impact,
        "marginal_ordinary_rate":    marginal_ordinary_rate,
    }

# Made with Bob
