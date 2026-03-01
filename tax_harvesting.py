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
import logging
from dataclasses import dataclass
from typing import Optional, cast

import numpy as np
import pandas as pd
import streamlit as st

from load_data import get_cap_gains_brackets, _fetch_current_prices  # noqa: F401
from portfolio import getPortfolioData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type for compute_net_tax_impact
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HarvestDecision:
    """Typed, immutable result of _classify_row / _classify_gain_row."""
    recommendation: str
    action_detail:  str


@dataclass(frozen=True)
class NetTaxImpact:
    """Typed, immutable result of compute_net_tax_impact."""
    total_harvestable_losses: float
    total_harvestable_gains:  float
    net_position:             float
    ltcg_rate:                float
    tax_on_net_gains:         float
    ordinary_income_offset:   float
    ordinary_income_savings:  float
    net_tax_impact:           float
    marginal_ordinary_rate:   float


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASH_SYMBOL = "MF:CASH"
BROKERAGE_ACCOUNT_TYPE = "Brokerage"

# Holding-period threshold in days (IRS: > 1 year = long-term)
LONG_TERM_DAYS = 365

# IRS annual cap on net capital loss deductible against ordinary income (IRC §1211(b))
MAX_ORDINARY_LOSS_OFFSET = 3_000.0

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


def _format_replacements(symbol: str) -> str:
    """Return a display string of up to 2 wash-sale replacement suggestions."""
    replacements = WASH_SALE_REPLACEMENTS.get(symbol, DEFAULT_REPLACEMENT)
    return ", ".join(f"{r['symbol']} ({r['reason']})" for r in replacements[:2])


def _fmt_money(value: float) -> str:
    """Format a dollar amount as '$1,234' (no cents, comma-separated)."""
    return f"${value:,.0f}"


def _resolve_prices(
    symbols: list[str],
    fallback: pd.Series,
) -> dict[str, float]:
    """
    Fetch live prices for *symbols*; fall back to *fallback* for any that fail.

    Args:
        symbols:  List of ticker symbols to fetch.
        fallback: Series indexed by symbol containing purchase prices used
                  when a live price cannot be retrieved.

    Returns:
        Mapping of symbol → resolved price (float).
    """
    raw = _fetch_current_prices(symbols)
    failed = [s for s, p in raw.items() if p is None]
    if failed:
        logger.warning("Could not fetch prices for: %s", failed)
        st.warning(f"Could not fetch prices for: {failed}")
    return {
        s: float(p) if p is not None else float(fallback.at[s])
        for s, p in raw.items()
    }


# ---------------------------------------------------------------------------
# Holding-period estimation
# ---------------------------------------------------------------------------

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
            return float(str(row["rate"]).strip())
    return 0.20


@st.cache_data(ttl=3600)
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

def _enrich_with_prices(
    df: pd.DataFrame,
    qty: pd.Series,
    px: pd.Series,
) -> pd.DataFrame:
    """
    Fetch live prices and add derived valuation columns to *df* in-place.

    Adds: ``Current Price``, ``Current Value``, ``Cost Basis``,
    ``Unrealized G/L``, ``Return %``.

    Args:
        df:  Brokerage holdings frame (modified in-place and returned).
        qty: Float Series of share quantities, index-aligned with *df*.
        px:  Float Series of purchase prices, index-aligned with *df*.

    Returns:
        The same *df* with the five new columns populated.
    """
    price_map = _resolve_prices(
        df["symbol"].tolist(),
        cast(pd.Series, px.set_axis(df["symbol"])),
    )
    df["Current Price"]  = df["symbol"].map(price_map)  # type: ignore[arg-type]
    df["Current Value"]  = qty * df["Current Price"]
    df["Cost Basis"]     = qty * px
    df["Unrealized G/L"] = df["Current Value"] - df["Cost Basis"]
    df["Return %"] = np.where(
        df["Cost Basis"] != 0,
        df["Unrealized G/L"] / df["Cost Basis"] * 100,
        0.0,
    )
    return df


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

    # Filter to Brokerage accounts only, excluding cash — single-pass combined mask
    mask = (
        (portfolio["account_type"] == BROKERAGE_ACCOUNT_TYPE)
        & (portfolio["symbol"] != CASH_SYMBOL)
    )
    df = cast(pd.DataFrame, portfolio[mask].copy())

    if df.empty:
        return pd.DataFrame()

    today = datetime.date.today()

    # ── Cast numeric columns once; bind locals for reuse below ─────────────
    df[["qty", "purchase_price"]] = df[["qty", "purchase_price"]].astype(float)
    qty = cast(pd.Series, df["qty"])
    px  = cast(pd.Series, df["purchase_price"])

    # ── Batch price fetch + derived valuation columns ───────────────────────
    _enrich_with_prices(df, qty, px)

    # ── Vectorized date arithmetic ──────────────────────────────────────────
    fallback_date = datetime.date(year, month, 1)
    purchase_ts = pd.to_datetime(df["purchase_date"], errors="coerce").fillna(
        pd.Timestamp(fallback_date)
    )
    df["Days Held"] = (pd.Timestamp(today) - purchase_ts).dt.days
    df["Gain Type"] = np.where(df["Days Held"] > LONG_TERM_DAYS, "Long-Term", "Short-Term")

    # ── Build output DataFrame with canonical column names ──────────────────
    df = df.assign(
        Account            = df["account_name"].astype(str),
        Symbol             = df["symbol"].astype(str),
        Name               = df["name"].fillna(df["symbol"]).astype(str),
        Sector             = df["sector"].fillna("").astype(str),
        Qty                = qty,
        Replacements       = df["symbol"].map(_format_replacements),  # type: ignore[arg-type]
        **{"Purchase Price": px},
    )

    output_columns = [
        "Account", "Symbol", "Name", "Sector", "Qty",
        "Purchase Price", "Current Price", "Current Value",
        "Cost Basis", "Unrealized G/L", "Return %",
        "Days Held", "Gain Type", "Replacements",
    ]
    # Sort: losses first (most negative), then gains (most positive)
    return df[output_columns].sort_values("Unrealized G/L", ascending=True).reset_index(drop=True)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Harvest opportunity classifier — row-level helpers
# ---------------------------------------------------------------------------

_VALID_GAIN_TYPES = {"Long-Term", "Short-Term"}
_VALID_LTCG_RATES = {0.0, 0.15, 0.20}

# ---------------------------------------------------------------------------
# Action-detail message templates
# Centralised here so _classify_row and the vectorised path in
# classify_harvest_opportunities share identical wording.
# ---------------------------------------------------------------------------
_DETAIL_HARVEST_LOSS    = (
    "Sell to realize {loss} loss. "
    "Replace with wash-sale-safe alternative within same day. "
    "Loss offsets gains or up to {max_offset} of ordinary income."
)
_DETAIL_HARVEST_GAIN_0  = (
    "Sell to realize {gl} LT gain at 0% rate. "
    "Repurchase same security to reset cost basis higher. "
    "Remaining 0% headroom: {headroom}."
)
_DETAIL_MONITOR_15      = (
    "LT gain of {gl} would be taxed at 15%. "
    "Consider deferring or offsetting with harvested losses. "
    "Need {headroom} income reduction for 0% rate."
)
_DETAIL_HOLD_20         = (
    "LT gain of {gl} would be taxed at 20%. "
    "Defer realization or offset with harvested losses."
)
_DETAIL_MONITOR_ST      = (
    "ST gain of {gl} taxed as ordinary income. "
    "Wait for long-term treatment (hold {days_to_lt} more days)."
)
_DETAIL_SMALL_LOSS      = (
    "Loss of {loss} is below harvest threshold. Monitor for larger decline."
)
_DETAIL_SMALL_GAIN      = (
    "Gain of {gl} is below harvest threshold. Hold position."
)


def _validate_classify_inputs(
    days_held: int,
    gain_type: str,
    ltcg_rate: float,
) -> None:
    """
    Raise ValueError for any out-of-contract input to _classify_row.

    Extracted so that the validation logic can be tested independently and
    reused without duplicating the error messages.

    Raises:
        ValueError: if days_held < 0, gain_type is unrecognised, or
                    ltcg_rate is not one of 0.0 / 0.15 / 0.20.
    """
    if days_held < 0:
        raise ValueError(f"days_held must be >= 0, got {days_held}")
    if gain_type not in _VALID_GAIN_TYPES:
        raise ValueError(
            f"Unknown gain_type {gain_type!r}; expected one of {sorted(_VALID_GAIN_TYPES)}"
        )
    if ltcg_rate not in _VALID_LTCG_RATES:
        raise ValueError(
            f"Unexpected ltcg_rate {ltcg_rate}; expected one of {sorted(_VALID_LTCG_RATES)}"
        )


def _classify_gain_row(
    gl: float,
    gain_type: str,
    ltcg_rate: float,
    headroom_to_zero: float,
    days_held: int,
) -> HarvestDecision:
    """
    Return a HarvestDecision for a position where gl >= gain_threshold.

    Extracted from _classify_row so the gain-path logic can be tested and
    extended independently (e.g. adding a new LTCG rate requires only a new
    case here, not a change to _classify_row).
    """
    match (gain_type, ltcg_rate):
        case ("Long-Term", 0.0):
            return HarvestDecision(
                "🟢 Harvest Gain (0% LTCG)",
                _DETAIL_HARVEST_GAIN_0.format(
                    gl=_fmt_money(gl), headroom=_fmt_money(headroom_to_zero)
                ),
            )
        case ("Long-Term", 0.15):
            return HarvestDecision(
                "🟡 Monitor (15% LTCG)",
                _DETAIL_MONITOR_15.format(
                    gl=_fmt_money(gl), headroom=_fmt_money(headroom_to_zero)
                ),
            )
        case ("Long-Term", _):
            # ltcg_rate == 0.20 (validated upstream; any other positive rate falls here)
            return HarvestDecision(
                "🔴 Hold (20% LTCG)",
                _DETAIL_HOLD_20.format(gl=_fmt_money(gl)),
            )
        case _:
            # Short-Term — always taxed as ordinary income regardless of LTCG rate
            days_to_lt = max(0, LONG_TERM_DAYS - days_held)
            return HarvestDecision(
                "🟡 Monitor (ST — Ordinary Rate)",
                _DETAIL_MONITOR_ST.format(
                    gl=_fmt_money(gl), days_to_lt=days_to_lt
                ),
            )


def _classify_row(
    gl: float,
    gain_type: str,
    days_held: int,
    ltcg_rate: float,
    headroom_to_zero: float,
    loss_threshold: float,
    gain_threshold: float,
) -> HarvestDecision:
    """
    Return a HarvestDecision for a single holding.

    All threshold comparisons and string formatting are centralised here so
    that classify_harvest_opportunities() is a thin orchestrator and this
    helper can be tested independently without constructing a DataFrame.

    Raises:
        ValueError: if days_held < 0, gain_type is unrecognised, or
                    ltcg_rate is not one of 0.0 / 0.15 / 0.20.
    """
    _validate_classify_inputs(days_held, gain_type, ltcg_rate)

    if gl <= loss_threshold:
        return HarvestDecision(
            "🔴 Harvest Loss",
            _DETAIL_HARVEST_LOSS.format(
                loss=_fmt_money(abs(gl)),
                max_offset=_fmt_money(MAX_ORDINARY_LOSS_OFFSET),
            ),
        )

    if gl >= gain_threshold:
        return _classify_gain_row(gl, gain_type, ltcg_rate, headroom_to_zero, days_held)

    if gl < 0:  # abs(gl) < abs(loss_threshold) — small loss, below harvest threshold
        return HarvestDecision(
            "⚪ Small Loss — Monitor",
            _DETAIL_SMALL_LOSS.format(loss=_fmt_money(abs(gl))),
        )

    # Invariant: 0 <= gl < gain_threshold (small gain, below harvest threshold)
    return HarvestDecision(
        "⚪ Small Gain — Hold",
        _DETAIL_SMALL_GAIN.format(gl=_fmt_money(gl)),
    )


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

    ltcg_rate        = get_ltcg_rate_for_income(estimated_agi, year)
    zero_threshold   = get_ltcg_zero_threshold(year)
    headroom_to_zero = max(0.0, zero_threshold - estimated_agi)

    # ── Up-front column-level validation (replaces per-row guards in _classify_row) ──
    gl        = analysis_df["Unrealized G/L"].astype(float)
    gain_type = analysis_df["Gain Type"].astype(str)
    days_held = analysis_df["Days Held"].astype(int)

    if (days_held < 0).any():
        bad = days_held[days_held < 0].tolist()
        raise ValueError(f"days_held must be >= 0; got negative values: {bad}")
    unknown_types = set(gain_type.unique()) - _VALID_GAIN_TYPES
    if unknown_types:
        raise ValueError(
            f"Unknown gain_type values {sorted(unknown_types)}; "
            f"expected one of {sorted(_VALID_GAIN_TYPES)}"
        )
    if ltcg_rate not in _VALID_LTCG_RATES:
        raise ValueError(
            f"Unexpected ltcg_rate {ltcg_rate}; expected one of {sorted(_VALID_LTCG_RATES)}"
        )

    # ── Vectorized Recommendation column via np.select ───────────────────────
    is_harvest_loss = gl <= loss_threshold
    is_large_gain   = gl >= gain_threshold
    is_lt           = gain_type == "Long-Term"
    is_small_loss   = (gl < 0) & ~is_harvest_loss

    rec = np.select(
        [
            is_harvest_loss,
            is_large_gain & is_lt & (ltcg_rate == 0.0),
            is_large_gain & is_lt & (ltcg_rate == 0.15),
            is_large_gain & is_lt,          # ltcg_rate == 0.20 fallthrough
            is_large_gain & ~is_lt,         # Short-Term gain
            is_small_loss,
        ],
        [
            "🔴 Harvest Loss",
            "🟢 Harvest Gain (0% LTCG)",
            "🟡 Monitor (15% LTCG)",
            "🔴 Hold (20% LTCG)",
            "🟡 Monitor (ST — Ordinary Rate)",
            "⚪ Small Loss — Monitor",
        ],
        default="⚪ Small Gain — Hold",
    )

    # ── Action Detail: vectorized string construction via np.select ──────────
    # Reuses the boolean masks already computed for `rec`; scalar values
    # (ltcg_rate, headroom_to_zero) are broadcast automatically by numpy.
    days_to_lt = (LONG_TERM_DAYS - days_held).clip(lower=0)

    detail = np.select(
        [
            is_harvest_loss,
            is_large_gain & is_lt & (ltcg_rate == 0.0),
            is_large_gain & is_lt & (ltcg_rate == 0.15),
            is_large_gain & is_lt,          # ltcg_rate == 0.20 fallthrough
            is_large_gain & ~is_lt,         # Short-Term gain
            is_small_loss,
        ],
        [
            "Sell to realize " + gl.abs().map(_fmt_money) + " loss. "
            "Replace with wash-sale-safe alternative within same day. "
            f"Loss offsets gains or up to {_fmt_money(MAX_ORDINARY_LOSS_OFFSET)} of ordinary income.",

            "Sell to realize " + gl.map(_fmt_money) + " LT gain at 0% rate. "
            "Repurchase same security to reset cost basis higher. "
            f"Remaining 0% headroom: {_fmt_money(headroom_to_zero)}.",

            "LT gain of " + gl.map(_fmt_money) + " would be taxed at 15%. "
            "Consider deferring or offsetting with harvested losses. "
            f"Need {_fmt_money(headroom_to_zero)} income reduction for 0% rate.",

            "LT gain of " + gl.map(_fmt_money) + " would be taxed at 20%. "
            "Defer realization or offset with harvested losses.",

            "ST gain of " + gl.map(_fmt_money) + " taxed as ordinary income. "
            "Wait for long-term treatment (hold "
            + days_to_lt.astype(str) + " more days).",

            "Loss of " + gl.abs().map(_fmt_money) + " is below harvest threshold. "
            "Monitor for larger decline.",
        ],
        default="Gain of " + gl.map(_fmt_money) + " is below harvest threshold. Hold position.",
    )

    return analysis_df.assign(**{
        "Recommendation": rec,
        "Action Detail":  detail,
        "LTCG Rate":      f"{ltcg_rate:.0%}",
        "0% Headroom":    headroom_to_zero,
    })


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

    if 'Recommendation' not in classified_df.columns:
        raise ValueError('classified_df must be the output of classify_harvest_opportunities()')

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
) -> NetTaxImpact:
    """
    Estimate the tax impact of executing all recommended harvesting actions.

    Assumptions:
      - Harvested losses first offset harvested gains (netting)
      - Remaining net loss offsets up to MAX_ORDINARY_LOSS_OFFSET of ordinary income
      - Remaining net gain taxed at applicable LTCG rate

    Returns a NetTaxImpact dataclass with estimated tax savings / liability.
    """
    ltcg_rate = get_ltcg_rate_for_income(estimated_agi, year)

    if classified_df.empty:
        return NetTaxImpact(
            total_harvestable_losses = 0.0,
            total_harvestable_gains  = 0.0,
            net_position             = 0.0,
            ltcg_rate                = ltcg_rate,
            tax_on_net_gains         = 0.0,
            ordinary_income_offset   = 0.0,
            ordinary_income_savings  = 0.0,
            net_tax_impact           = 0.0,
            marginal_ordinary_rate   = marginal_ordinary_rate,
        )

    is_loss          = classified_df["Recommendation"].str.startswith("🔴")
    total_losses_abs = classified_df.loc[is_loss,  "Unrealized G/L"].abs().sum()
    total_gains      = classified_df.loc[~is_loss, "Unrealized G/L"].sum()  # naturally positive
    net              = total_gains - total_losses_abs  # positive = net gain, negative = net loss

    tax_on_gains     = max(0.0, net) * ltcg_rate
    ordinary_offset  = max(0.0, min(-net, MAX_ORDINARY_LOSS_OFFSET))
    ordinary_savings = ordinary_offset * marginal_ordinary_rate
    net_tax_impact   = ordinary_savings - tax_on_gains

    return NetTaxImpact(
        total_harvestable_losses = total_losses_abs,
        total_harvestable_gains  = total_gains,
        net_position             = net,
        ltcg_rate                = ltcg_rate,
        tax_on_net_gains         = tax_on_gains,
        ordinary_income_offset   = ordinary_offset,
        ordinary_income_savings  = ordinary_savings,
        net_tax_impact           = net_tax_impact,
        marginal_ordinary_rate   = marginal_ordinary_rate,
    )

# Made with Bob


# ---------------------------------------------------------------------------
# Donor Advised Fund (DAF) bundling analysis
# ---------------------------------------------------------------------------

# IRS deduction limits for DAF contributions (IRC §170)
# Cash contributions to a DAF: 60% of AGI (post-TCJA)
# Appreciated securities donated to a DAF: 30% of AGI
DAF_CASH_DEDUCTION_LIMIT_PCT: float = 0.60
DAF_SECURITIES_DEDUCTION_LIMIT_PCT: float = 0.30

# Minimum unrealized gain to flag a security as a DAF donation candidate.
# Donating low-cost-basis securities avoids capital gains tax entirely.
DAF_MIN_GAIN_FOR_DONATION: float = 500.0

# Minimum holding period (days) for a security to qualify as long-term
# appreciated property for DAF donation (IRS requires > 1 year).
DAF_MIN_HOLDING_DAYS: int = 366


@dataclass(frozen=True)
class DAFDonationCandidate:
    """A brokerage security flagged as a strong DAF donation candidate."""
    account:        str
    symbol:         str
    name:           str
    qty:            float
    cost_basis:     float
    current_value:  float
    unrealized_gain: float
    gain_pct:       float
    days_held:      int
    gain_type:      str   # 'Long-Term' or 'Short-Term'
    avoided_cg_tax: float  # estimated capital gains tax avoided by donating vs. selling


@dataclass(frozen=True)
class DAFBundlingAnalysis:
    """
    Full DAF bundling recommendation for a tax year.

    Bundling means concentrating multiple years of charitable giving into a
    single high-deduction year (using the DAF as a pass-through), then
    distributing grants to charities over subsequent years.
    """
    estimated_agi:          float
    standard_deduction:     float
    years_to_bundle:        int       # how many years of giving to front-load
    annual_giving:          float     # normal annual charitable giving amount
    bundled_contribution:   float     # total DAF contribution in the bundle year
    deductible_amount:      float     # actual deductible amount (AGI-limited)
    carryforward_amount:    float     # excess carried forward (5-year carryforward)
    tax_savings_vs_standard: float    # incremental tax savings vs. taking std deduction
    marginal_rate:          float
    securities_candidates:  list      # list of DAFDonationCandidate
    total_securities_value: float     # total FMV of flagged securities
    total_avoided_cg_tax:   float     # total CG tax avoided by donating securities
    recommendation:         str
    notes:                  list      # list of str


def identify_daf_candidates(
    analysis_df: pd.DataFrame,
    min_gain: float = DAF_MIN_GAIN_FOR_DONATION,
    min_days: int = DAF_MIN_HOLDING_DAYS,
) -> list[DAFDonationCandidate]:
    """
    Identify brokerage securities that are strong candidates for DAF donation.

    The ideal DAF donation candidate is a long-term appreciated security:
    - Held > 1 year (qualifies for FMV deduction, not just cost basis)
    - Has a significant unrealized gain (avoids capital gains tax on donation)
    - Donating FMV to DAF = full FMV deduction + zero capital gains tax

    Args:
        analysis_df: Output of build_harvesting_analysis() — brokerage holdings
                     with Current Value, Cost Basis, Unrealized G/L, Days Held,
                     Gain Type columns.
        min_gain:    Minimum unrealized gain ($) to flag as a candidate.
        min_days:    Minimum holding period (days) to qualify as long-term.

    Returns:
        List of DAFDonationCandidate sorted by unrealized_gain descending.
    """
    if analysis_df.empty:
        return []

    required = {"Symbol", "Account", "Name", "Qty", "Cost Basis",
                "Current Value", "Unrealized G/L", "Days Held", "Gain Type"}
    missing = required - set(analysis_df.columns)
    if missing:
        logger.warning("identify_daf_candidates: missing columns %s", missing)
        return []

    # Filter: long-term, meaningful gain
    mask = (
        (analysis_df["Unrealized G/L"] >= min_gain)
        & (analysis_df["Days Held"] >= min_days)
        & (analysis_df["Gain Type"] == "Long-Term")
    )
    candidates_df = analysis_df[mask].copy()

    if candidates_df.empty:
        return []

    results: list[DAFDonationCandidate] = []
    for _, row in candidates_df.iterrows():
        gain      = float(row["Unrealized G/L"])
        cv        = float(row["Current Value"])
        cb        = float(row["Cost Basis"])
        gain_pct  = (gain / cb * 100) if cb > 0 else 0.0
        # Estimated CG tax avoided: long-term gain × 15% (conservative mid-bracket estimate)
        avoided   = gain * 0.15

        results.append(DAFDonationCandidate(
            account        = str(row["Account"]),
            symbol         = str(row["Symbol"]),
            name           = str(row["Name"]),
            qty            = float(row["Qty"]),
            cost_basis     = cb,
            current_value  = cv,
            unrealized_gain= gain,
            gain_pct       = gain_pct,
            days_held      = int(row["Days Held"]),
            gain_type      = str(row["Gain Type"]),
            avoided_cg_tax = avoided,
        ))

    return sorted(results, key=lambda c: c.unrealized_gain, reverse=True)


def analyze_daf_bundling(
    estimated_agi:      float,
    annual_giving:      float,
    years_to_bundle:    int,
    marginal_rate:      float,
    standard_deduction: float,
    ltcg_rate:          float,
    securities_candidates: list[DAFDonationCandidate],
    year:               int = 2024,
) -> DAFBundlingAnalysis:
    """
    Compute a full DAF bundling recommendation.

    Bundling strategy:
    1. Front-load N years of charitable giving into one DAF contribution.
    2. Donate appreciated securities (FMV deductible, zero CG tax) first.
    3. Top up with cash to reach the bundled target.
    4. Deduct the bundled amount (up to AGI limits) in the bundle year.
    5. Distribute grants from the DAF to charities over subsequent years.

    IRS limits (IRC §170):
    - Appreciated securities donated to DAF: deductible up to 30% of AGI.
    - Cash donated to DAF: deductible up to 60% of AGI.
    - Excess carries forward up to 5 years.

    Args:
        estimated_agi:          Estimated AGI for the bundle year.
        annual_giving:          Normal annual charitable giving amount.
        years_to_bundle:        Number of years of giving to front-load (2–5).
        marginal_rate:          Marginal federal income tax rate (e.g. 0.22).
        standard_deduction:     Standard deduction for the filing status/year.
        ltcg_rate:              Applicable LTCG rate (0.0, 0.15, or 0.20).
        securities_candidates:  Output of identify_daf_candidates().
        year:                   Tax year (for reference).

    Returns:
        DAFBundlingAnalysis dataclass with full recommendation details.
    """
    years_to_bundle = max(1, min(years_to_bundle, 5))
    bundled_target  = annual_giving * years_to_bundle

    # ── Step 1: Allocate securities donations first (up to 30% AGI limit) ──
    securities_limit = estimated_agi * DAF_SECURITIES_DEDUCTION_LIMIT_PCT
    securities_value = 0.0
    avoided_cg_total = 0.0
    used_candidates: list[DAFDonationCandidate] = []

    for cand in securities_candidates:
        if securities_value >= min(bundled_target, securities_limit):
            break
        remaining_room = min(bundled_target, securities_limit) - securities_value
        if cand.current_value <= remaining_room:
            used_candidates.append(cand)
            securities_value  += cand.current_value
            avoided_cg_total  += cand.avoided_cg_tax
        else:
            # Partial donation (donate enough shares to fill the room)
            partial_ratio = remaining_room / cand.current_value if cand.current_value > 0 else 0
            partial_gain  = cand.unrealized_gain * partial_ratio
            partial_avoid = partial_gain * ltcg_rate
            used_candidates.append(DAFDonationCandidate(
                account         = cand.account,
                symbol          = cand.symbol,
                name            = cand.name,
                qty             = cand.qty * partial_ratio,
                cost_basis      = cand.cost_basis * partial_ratio,
                current_value   = remaining_room,
                unrealized_gain = partial_gain,
                gain_pct        = cand.gain_pct,
                days_held       = cand.days_held,
                gain_type       = cand.gain_type,
                avoided_cg_tax  = partial_avoid,
            ))
            securities_value  += remaining_room
            avoided_cg_total  += partial_avoid
            break

    # ── Step 2: Top up with cash to reach bundled target ───────────────────
    cash_needed = max(0.0, bundled_target - securities_value)
    cash_limit  = estimated_agi * DAF_CASH_DEDUCTION_LIMIT_PCT

    # Total deductible = securities (30% limit) + cash (60% limit, but combined
    # cannot exceed 60% of AGI per IRC §170(b)(1)(G))
    total_contribution = securities_value + cash_needed
    combined_limit     = estimated_agi * DAF_CASH_DEDUCTION_LIMIT_PCT  # 60% overall cap
    deductible_amount  = min(total_contribution, combined_limit)
    carryforward       = max(0.0, total_contribution - deductible_amount)

    # ── Step 3: Incremental tax savings vs. taking standard deduction ───────
    # Only the amount ABOVE the standard deduction generates incremental savings
    itemized_deduction = deductible_amount
    incremental_deduction = max(0.0, itemized_deduction - standard_deduction)
    tax_savings = incremental_deduction * marginal_rate

    # ── Step 4: Build recommendation and notes ──────────────────────────────
    notes: list[str] = []

    if bundled_target <= standard_deduction:
        recommendation = "⚪ Bundling not beneficial — contribution below standard deduction"
        notes.append(
            f"Your {years_to_bundle}-year bundled contribution of "
            f"${bundled_target:,.0f} does not exceed the standard deduction "
            f"(${standard_deduction:,.0f}). Consider bundling more years or "
            f"increasing annual giving to make itemizing worthwhile."
        )
    elif incremental_deduction < 1_000:
        recommendation = "🟡 Marginal benefit — small incremental deduction over standard"
        notes.append(
            f"Bundled contribution of ${bundled_target:,.0f} exceeds the standard "
            f"deduction by only ${incremental_deduction:,.0f}. Tax savings are modest."
        )
    else:
        recommendation = "🟢 Bundle recommended — significant tax savings identified"
        notes.append(
            f"Front-loading {years_to_bundle} years of giving (${bundled_target:,.0f}) "
            f"into a single DAF contribution generates ~${tax_savings:,.0f} in incremental "
            f"federal tax savings vs. taking the standard deduction each year."
        )

    if used_candidates:
        notes.append(
            f"Donate {len(used_candidates)} appreciated security position(s) "
            f"(FMV ${securities_value:,.0f}) to avoid ~${avoided_cg_total:,.0f} "
            f"in capital gains tax. Donate securities BEFORE selling."
        )
    else:
        notes.append(
            "No long-term appreciated securities identified for donation. "
            "Consider a cash contribution to the DAF."
        )

    if carryforward > 0:
        notes.append(
            f"${carryforward:,.0f} of your contribution exceeds the AGI deduction limit "
            f"and carries forward for up to 5 years (IRC §170(d))."
        )

    if cash_needed > 0:
        notes.append(
            f"After securities donations, contribute an additional "
            f"${cash_needed:,.0f} cash to reach your {years_to_bundle}-year bundled target."
        )

    return DAFBundlingAnalysis(
        estimated_agi          = estimated_agi,
        standard_deduction     = standard_deduction,
        years_to_bundle        = years_to_bundle,
        annual_giving          = annual_giving,
        bundled_contribution   = total_contribution,
        deductible_amount      = deductible_amount,
        carryforward_amount    = carryforward,
        tax_savings_vs_standard= tax_savings,
        marginal_rate          = marginal_rate,
        securities_candidates  = used_candidates,
        total_securities_value = securities_value,
        total_avoided_cg_tax   = avoided_cg_total,
        recommendation         = recommendation,
        notes                  = notes,
    )
