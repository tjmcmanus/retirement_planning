"""
Portfolio Rebalancing Module
============================
Calculates the full portfolio allocation across Cash / Bonds / Stocks and
generates rebalancing recommendations when any asset class drifts more than
a configurable threshold (default 5%) from its target weight.

Key design decisions
--------------------
* **Asset classification** is driven by the ``sector`` and ``name`` fields stored
  in the portfolio CSV.  Sectors that start with ``MF:Cash`` or the symbol
  ``MF:CASH`` are treated as *Cash*.  Sectors **or names** that contain bond-related
  keywords (Bond, Fixed Income, Treasury, Municipal, Muni) are treated as *Bonds*.
  Everything else is *Stocks*.  Checking the name is necessary because Yahoo Finance
  classifies many bond closed-end funds and ETFs under ``Financial Services``.

* **Account-location rules** (where to hold each asset class):
  - Bonds → prefer Traditional IRA (ordinary income on withdrawal anyway).
    Exception: Municipal bonds and Treasuries may live in Brokerage.
  - Cash → keep ≥ 10 % of the Brokerage account in MF:Cash.
  - Stocks → Roth (tax-free growth) or Brokerage.

* **Rebalancing strategy** (in priority order):
  1. Rebalance *inside* Traditional or Roth accounts first (no tax event).
  2. Use Tax-Loss Harvesting in Brokerage to fund rebalancing trades.
  3. Redirect new contributions / dividends to under-weight asset classes.

Only the *current* portfolio snapshot (latest month/year) is analysed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from typing import cast

from load_data import _fetch_current_prices
from portfolio import getPortfolioData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASH_SYMBOL = "MF:CASH"

# Regex patterns that identify bond-like sectors (case-insensitive whole-word match).
# IMPORTANT: Use word-boundary anchors (\b) to avoid false substring matches.
# Example failure without \b: "muni" matches inside "communication" → false positive.
BOND_SECTOR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'\bbond\b',        re.IGNORECASE),
    re.compile(r'\bfixed income\b', re.IGNORECASE),
    re.compile(r'\btreasur(?:y|ies)\b', re.IGNORECASE),
    re.compile(r'\bmunicipal\b',   re.IGNORECASE),
    re.compile(r'\bmuni\b',        re.IGNORECASE),
]

# Sectors / symbols that are always cash
CASH_SECTOR_KEYWORDS = ["cash", "money market"]

# Account types
BROKERAGE   = "Brokerage"
TRADITIONAL = "Traditional"
ROTH        = "Roth"
CASH_ACCT   = "Cash"   # plain savings / checking

# Minimum Brokerage cash cushion (10 % of brokerage market value)
BROKERAGE_CASH_MIN_PCT = 0.10

# Default rebalance drift threshold
DEFAULT_DRIFT_THRESHOLD_PCT = 5.0


# ---------------------------------------------------------------------------
# Asset-class classification helpers
# ---------------------------------------------------------------------------

def _classify_asset(symbol: str, sector: str, name: str = "") -> str:
    """
    Return 'Cash', 'Bonds', or 'Stocks' for a single holding.

    Classification logic (in priority order):
    1. Symbol == MF:CASH  → Cash
    2. Sector contains a cash keyword → Cash
    3. Sector OR name matches a bond pattern (whole-word regex) → Bonds
    4. Everything else → Stocks

    Note: Bond patterns use word-boundary anchors (\b) to prevent false positives
    such as "muni" matching inside "communication".

    The ``name`` field is checked in addition to ``sector`` because Yahoo Finance
    classifies many bond closed-end funds and ETFs (e.g. VPV — "Invesco Pennsylvania
    Value Muni") under the generic ``Financial Services`` sector, making sector-only
    classification unreliable for these instruments.
    """
    sym_upper    = symbol.upper()
    sector_lower = (sector or "").lower()
    name_lower   = (name or "").lower()

    if sym_upper == CASH_SYMBOL:
        return "Cash"

    for kw in CASH_SECTOR_KEYWORDS:
        if kw in sector_lower:
            return "Cash"

    for pattern in BOND_SECTOR_PATTERNS:
        if pattern.search(sector_lower) or pattern.search(name_lower):
            return "Bonds"

    return "Stocks"


# Pre-compiled patterns for muni/treasury detection (word-boundary safe)
_MUNI_TSY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'\bmunicipal\b',        re.IGNORECASE),
    re.compile(r'\bmuni\b',             re.IGNORECASE),
    re.compile(r'\btreasur(?:y|ies)\b', re.IGNORECASE),
]

def _is_municipal_or_treasury(sector: str, name: str = "") -> bool:
    """Return True if the sector or name indicates a muni or treasury bond.

    Checks both ``sector`` and ``name`` because Yahoo Finance often returns
    ``Financial Services`` as the sector for muni/treasury bond funds, while
    the fund name (e.g. "Invesco Pennsylvania Value Muni") correctly identifies
    the instrument type.

    Uses whole-word regex matching to avoid false positives such as
    'muni' matching inside 'communication'.
    """
    return any(p.search(sector or "") or p.search(name or "") for p in _MUNI_TSY_PATTERNS)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AssetClassSummary:
    """Aggregated values for one asset class across the whole portfolio."""
    asset_class:    str
    current_value:  float
    current_pct:    float   # 0–100
    target_pct:     float   # 0–100
    drift_pct:      float   # current_pct − target_pct  (signed)
    is_drifted:     bool    # abs(drift_pct) >= threshold
    delta_value:    float   # dollar amount to buy(+) or sell(−) to reach target


@dataclass
class HoldingDetail:
    """One row of the enriched portfolio used for rebalancing analysis."""
    account_name:   str
    account_type:   str
    symbol:         str
    name:           str
    sector:         str
    qty:            float
    purchase_price: float
    current_price:  float
    current_value:  float
    cost_basis:     float
    unrealized_gl:  float
    asset_class:    str   # Cash / Bonds / Stocks
    is_muni_or_tsy: bool  # True for muni/treasury bonds


@dataclass
class RebalanceAction:
    """A single recommended rebalancing trade."""
    priority:       int     # 1 = highest
    action:         str     # "Buy" | "Sell" | "Transfer" | "Redirect"
    asset_class:    str
    symbol:         str
    account_name:   str
    account_type:   str
    amount:         float   # positive dollar amount
    rationale:      str
    tax_impact:     str     # "None (tax-deferred/free)" | "Taxable event" | "Tax-loss harvest"
    location_note:  str     # guidance on where this asset *should* live


@dataclass
class RebalanceReport:
    """Full output of compute_rebalance_plan()."""
    total_portfolio_value:  float
    asset_summary:          list[AssetClassSummary]
    holdings:               list[HoldingDetail]
    actions:                list[RebalanceAction]
    drift_triggered:        bool
    drift_threshold_pct:    float
    target_weights:         dict[str, float]   # {"Cash": 10, "Bonds": 10, "Stocks": 80}
    brokerage_cash_pct:     float              # current cash % of brokerage account
    brokerage_cash_ok:      bool               # >= BROKERAGE_CASH_MIN_PCT
    location_issues:        list[str]          # plain-English location warnings


# ---------------------------------------------------------------------------
# Price resolution
# ---------------------------------------------------------------------------

def _resolve_prices(symbols: list[str], fallback_px: pd.Series) -> dict[str, float]:
    """
    Fetch live prices; fall back to purchase price for any that fail.

    Args:
        symbols:     Unique ticker symbols to fetch.
        fallback_px: Series indexed by symbol with purchase prices.

    Returns:
        Mapping symbol → float price.
    """
    raw = _fetch_current_prices(symbols)
    failed = [s for s, p in raw.items() if p is None]
    if failed:
        logger.warning("Could not fetch live prices for: %s — using purchase price as fallback", failed)
    result: dict[str, float] = {}
    for s, p in raw.items():
        if p is not None:
            result[s] = float(p)
        else:
            fb = fallback_px.get(s)
            result[s] = float(fb) if fb is not None else 1.0
    return result


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_rebalance_plan(
    month: int,
    year:  int,
    target_cash_pct:   float = 10.0,
    target_bonds_pct:  float = 10.0,
    target_stocks_pct: float = 80.0,
    drift_threshold_pct: float = DEFAULT_DRIFT_THRESHOLD_PCT,
) -> RebalanceReport:
    """
    Compute a full portfolio rebalancing plan.

    Args:
        month:               Portfolio snapshot month (1–12).
        year:                Portfolio snapshot year.
        target_cash_pct:     Target allocation to Cash (0–100).
        target_bonds_pct:    Target allocation to Bonds (0–100).
        target_stocks_pct:   Target allocation to Stocks (0–100).
        drift_threshold_pct: Trigger rebalancing when any class drifts this
                             many percentage points from its target.

    Returns:
        RebalanceReport with full analysis and action list.

    Raises:
        ValueError: if target weights do not sum to 100.
    """
    total_target = target_cash_pct + target_bonds_pct + target_stocks_pct
    if abs(total_target - 100.0) > 0.01:
        raise ValueError(
            f"Target weights must sum to 100; got {total_target:.2f} "
            f"(Cash={target_cash_pct}, Bonds={target_bonds_pct}, Stocks={target_stocks_pct})"
        )

    target_weights = {
        "Cash":   target_cash_pct,
        "Bonds":  target_bonds_pct,
        "Stocks": target_stocks_pct,
    }

    # ── 1. Load portfolio ────────────────────────────────────────────────────
    raw = getPortfolioData(month=month, year=year)
    if raw.empty:
        return RebalanceReport(
            total_portfolio_value=0.0,
            asset_summary=[],
            holdings=[],
            actions=[],
            drift_triggered=False,
            drift_threshold_pct=drift_threshold_pct,
            target_weights=target_weights,
            brokerage_cash_pct=0.0,
            brokerage_cash_ok=True,
            location_issues=[],
        )

    raw = raw.copy()
    raw[["qty", "purchase_price"]] = raw[["qty", "purchase_price"]].astype(float)

    # ── 2. Fetch live prices ─────────────────────────────────────────────────
    unique_symbols = raw["symbol"].unique().tolist()
    fallback_px    = cast(pd.Series, raw.groupby("symbol")["purchase_price"].first())
    price_map      = _resolve_prices(unique_symbols, fallback_px)

    # ── 3. Build enriched holdings list ─────────────────────────────────────
    holdings: list[HoldingDetail] = []
    for _, row in raw.iterrows():
        sym    = str(row["symbol"])
        sector = str(row.get("sector", "") or "")
        name   = str(row.get("name", sym) or sym)
        qty    = float(row["qty"])
        pp     = float(row["purchase_price"])
        cp     = price_map.get(sym, pp)
        cv     = qty * cp
        cb     = qty * pp
        ac     = _classify_asset(sym, sector, name)
        holdings.append(HoldingDetail(
            account_name   = str(row["account_name"]),
            account_type   = str(row["account_type"]),
            symbol         = sym,
            name           = name,
            sector         = sector,
            qty            = qty,
            purchase_price = pp,
            current_price  = cp,
            current_value  = cv,
            cost_basis     = cb,
            unrealized_gl  = cv - cb,
            asset_class    = ac,
            is_muni_or_tsy = _is_municipal_or_treasury(sector, name),
        ))

    total_value = sum(h.current_value for h in holdings)
    if total_value <= 0:
        total_value = 1.0  # guard against division by zero

    # ── 4. Asset-class aggregation ───────────────────────────────────────────
    class_totals: dict[str, float] = {"Cash": 0.0, "Bonds": 0.0, "Stocks": 0.0}
    for h in holdings:
        class_totals[h.asset_class] = class_totals.get(h.asset_class, 0.0) + h.current_value

    asset_summary: list[AssetClassSummary] = []
    drift_triggered = False
    for ac, tgt in target_weights.items():
        cv_ac   = class_totals.get(ac, 0.0)
        cur_pct = cv_ac / total_value * 100.0
        drift   = cur_pct - tgt
        drifted = abs(drift) >= drift_threshold_pct
        if drifted:
            drift_triggered = True
        delta_val = (tgt / 100.0 * total_value) - cv_ac  # + = need to buy, − = need to sell
        asset_summary.append(AssetClassSummary(
            asset_class   = ac,
            current_value = cv_ac,
            current_pct   = cur_pct,
            target_pct    = tgt,
            drift_pct     = drift,
            is_drifted    = drifted,
            delta_value   = delta_val,
        ))

    # ── 5. Brokerage cash cushion check ─────────────────────────────────────
    brok_total = sum(h.current_value for h in holdings if h.account_type == BROKERAGE)
    brok_cash  = sum(
        h.current_value for h in holdings
        if h.account_type == BROKERAGE and h.asset_class == "Cash"
    )
    brok_cash_pct = (brok_cash / brok_total) if brok_total > 0 else 0.0
    brok_cash_ok  = brok_cash_pct >= BROKERAGE_CASH_MIN_PCT

    # ── 6. Account-location issues ───────────────────────────────────────────
    location_issues: list[str] = []
    for h in holdings:
        if h.asset_class == "Bonds":
            if h.account_type == BROKERAGE and not h.is_muni_or_tsy:
                location_issues.append(
                    f"⚠️ {h.symbol} ({h.name}) is a bond in a Brokerage account. "
                    "Consider moving to Traditional IRA to defer ordinary income tax. "
                    "Exception: Municipal bonds and Treasuries may stay in Brokerage."
                )
            if h.account_type == ROTH:
                location_issues.append(
                    f"💡 {h.symbol} ({h.name}) is a bond in a Roth account. "
                    "Bonds generate ordinary income — Roth space is better used for "
                    "high-growth equities. Consider swapping with a stock holding in Traditional."
                )
        if h.asset_class == "Stocks" and h.account_type == TRADITIONAL:
            location_issues.append(
                f"💡 {h.symbol} ({h.name}) is a stock in a Traditional IRA. "
                "Growth will be taxed as ordinary income on withdrawal. "
                "Consider holding in Roth (tax-free growth) or Brokerage (LTCG rates)."
            )

    if not brok_cash_ok:
        needed = BROKERAGE_CASH_MIN_PCT * brok_total - brok_cash
        location_issues.append(
            f"⚠️ Brokerage cash cushion is {brok_cash_pct:.1%} "
            f"(target ≥ {BROKERAGE_CASH_MIN_PCT:.0%}). "
            f"Consider adding ${needed:,.0f} to MF:CASH in the Brokerage account."
        )

    # ── 7. Build rebalancing action list ────────────────────────────────────
    actions: list[RebalanceAction] = []
    priority = 1

    # Sort asset classes: over-weight first (sell), then under-weight (buy)
    over_weight  = [s for s in asset_summary if s.drift_pct >  drift_threshold_pct]
    under_weight = [s for s in asset_summary if s.drift_pct < -drift_threshold_pct]

    # ── 7a. Rebalance inside tax-advantaged accounts first (no tax event) ───
    for ow in over_weight:
        # Find tax-advantaged holdings in the over-weight class
        trad_roth_holdings = [
            h for h in holdings
            if h.asset_class == ow.asset_class
            and h.account_type in (TRADITIONAL, ROTH)
        ]
        sell_needed = abs(ow.delta_value)
        for h in sorted(trad_roth_holdings, key=lambda x: x.current_value, reverse=True):
            if sell_needed <= 0:
                break
            sell_amt = min(h.current_value, sell_needed)
            actions.append(RebalanceAction(
                priority     = priority,
                action       = "Sell / Reallocate",
                asset_class  = ow.asset_class,
                symbol       = h.symbol,
                account_name = h.account_name,
                account_type = h.account_type,
                amount       = sell_amt,
                rationale    = (
                    f"{ow.asset_class} is over-weight by {ow.drift_pct:+.1f}% "
                    f"(current {ow.current_pct:.1f}% vs target {ow.target_pct:.1f}%). "
                    f"Sell ${sell_amt:,.0f} of {h.symbol} inside {h.account_type} "
                    f"({h.account_name}) — no tax event."
                ),
                tax_impact    = "None (tax-deferred/free account)",
                location_note = _location_guidance(ow.asset_class, h.account_type),
            ))
            sell_needed -= sell_amt
            priority += 1

    for uw in under_weight:
        buy_needed = abs(uw.delta_value)
        # Prefer buying inside tax-advantaged accounts
        trad_roth_cash = [
            h for h in holdings
            if h.asset_class == "Cash"
            and h.account_type in (TRADITIONAL, ROTH)
        ]
        for h in sorted(trad_roth_cash, key=lambda x: x.current_value, reverse=True):
            if buy_needed <= 0:
                break
            buy_amt = min(h.current_value * 0.9, buy_needed)  # keep 10% cash buffer
            if buy_amt <= 0:
                continue
            actions.append(RebalanceAction(
                priority     = priority,
                action       = "Buy",
                asset_class  = uw.asset_class,
                symbol       = _suggest_symbol(uw.asset_class, h.account_type),
                account_name = h.account_name,
                account_type = h.account_type,
                amount       = buy_amt,
                rationale    = (
                    f"{uw.asset_class} is under-weight by {abs(uw.drift_pct):.1f}% "
                    f"(current {uw.current_pct:.1f}% vs target {uw.target_pct:.1f}%). "
                    f"Use ${buy_amt:,.0f} of cash in {h.account_type} ({h.account_name}) "
                    f"to buy {uw.asset_class} — no tax event."
                ),
                tax_impact    = "None (tax-deferred/free account)",
                location_note = _location_guidance(uw.asset_class, h.account_type),
            ))
            buy_needed -= buy_amt
            priority += 1

    # ── 7b. Tax-loss harvest in Brokerage to fund remaining rebalancing ──────
    brok_losers = [
        h for h in holdings
        if h.account_type == BROKERAGE
        and h.unrealized_gl < -500.0   # meaningful loss threshold
        and h.asset_class != "Cash"
    ]
    for ow in over_weight:
        brok_ow = [h for h in holdings if h.asset_class == ow.asset_class and h.account_type == BROKERAGE]
        sell_needed = abs(ow.delta_value)
        for h in sorted(brok_ow, key=lambda x: x.unrealized_gl):  # losses first
            if sell_needed <= 0:
                break
            sell_amt = min(h.current_value, sell_needed)
            is_loss  = h.unrealized_gl < 0
            actions.append(RebalanceAction(
                priority     = priority,
                action       = "Sell (Brokerage)",
                asset_class  = ow.asset_class,
                symbol       = h.symbol,
                account_name = h.account_name,
                account_type = h.account_type,
                amount       = sell_amt,
                rationale    = (
                    f"{ow.asset_class} is over-weight. Sell ${sell_amt:,.0f} of {h.symbol} "
                    f"in Brokerage ({h.account_name}). "
                    + (f"Unrealized loss of ${abs(h.unrealized_gl):,.0f} — "
                       "consider tax-loss harvesting with a wash-sale-safe replacement."
                       if is_loss else
                       f"Unrealized gain of ${h.unrealized_gl:,.0f} — "
                       "check LTCG rate before selling.")
                ),
                tax_impact    = "Tax-loss harvest opportunity" if is_loss else "Taxable event — check LTCG rate",
                location_note = _location_guidance(ow.asset_class, BROKERAGE),
            ))
            sell_needed -= sell_amt
            priority += 1

    # ── 7c. Redirect contributions / dividends ───────────────────────────────
    # For contributions, use the optimal account type per asset class:
    #   Bonds  → Traditional (mutual fund; ordinary income taxed on withdrawal anyway)
    #   Stocks → Roth (ETF; tax-free growth on highest-return assets)
    #   Cash   → Brokerage (liquidity cushion)
    _CONTRIBUTION_ACCOUNT: dict[str, str] = {
        "Bonds":  TRADITIONAL,
        "Stocks": ROTH,
        "Cash":   BROKERAGE,
    }
    for uw in under_weight:
        contrib_acct = _CONTRIBUTION_ACCOUNT.get(uw.asset_class, TRADITIONAL)
        actions.append(RebalanceAction(
            priority     = priority,
            action       = "Redirect Contributions",
            asset_class  = uw.asset_class,
            symbol       = _suggest_symbol(uw.asset_class, contrib_acct),
            account_name = f"{contrib_acct} account (preferred)",
            account_type = contrib_acct,
            amount       = abs(uw.delta_value),
            rationale    = (
                f"{uw.asset_class} is under-weight by {abs(uw.drift_pct):.1f}%. "
                f"Direct new contributions, dividends, and RMDs toward {uw.asset_class} "
                f"in your {contrib_acct} account "
                f"until the target of {uw.target_pct:.1f}% is restored."
            ),
            tax_impact    = "None (new money)",
            location_note = _location_guidance(uw.asset_class, contrib_acct),
        ))
        priority += 1

    # ── 7d. Brokerage cash cushion top-up ────────────────────────────────────
    if not brok_cash_ok:
        needed = BROKERAGE_CASH_MIN_PCT * brok_total - brok_cash
        actions.append(RebalanceAction(
            priority     = priority,
            action       = "Buy MF:CASH",
            asset_class  = "Cash",
            symbol       = CASH_SYMBOL,
            account_name = "Brokerage account",
            account_type = BROKERAGE,
            amount       = needed,
            rationale    = (
                f"Brokerage cash cushion is {brok_cash_pct:.1%} "
                f"(target ≥ {BROKERAGE_CASH_MIN_PCT:.0%}). "
                f"Add ${needed:,.0f} to MF:CASH in the Brokerage account to maintain liquidity."
            ),
            tax_impact    = "None (buying cash equivalent)",
            location_note = "Keep ≥ 10% of Brokerage account in MF:CASH for liquidity.",
        ))
        priority += 1

    return RebalanceReport(
        total_portfolio_value = total_value,
        asset_summary         = asset_summary,
        holdings              = holdings,
        actions               = actions,
        drift_triggered       = drift_triggered,
        drift_threshold_pct   = drift_threshold_pct,
        target_weights        = target_weights,
        brokerage_cash_pct    = brok_cash_pct,
        brokerage_cash_ok     = brok_cash_ok,
        location_issues       = location_issues,
    )


# ---------------------------------------------------------------------------
# Helper: location guidance text
# ---------------------------------------------------------------------------

def _location_guidance(asset_class: str, account_type: str) -> str:
    """Return a plain-English note about the ideal account location for an asset class."""
    if asset_class == "Bonds":
        if account_type == TRADITIONAL:
            return "✅ Bonds in Traditional IRA — interest taxed as ordinary income on withdrawal (correct location)."
        if account_type == BROKERAGE:
            return (
                "⚠️ Bonds in Brokerage — interest is taxable each year. "
                "Exception: Municipal bonds (tax-exempt) and Treasuries (state-tax-exempt) are acceptable here."
            )
        if account_type == ROTH:
            return (
                "💡 Bonds in Roth — Roth space is better used for high-growth equities. "
                "Consider swapping bonds to Traditional and equities to Roth."
            )
    if asset_class == "Stocks":
        if account_type == ROTH:
            return "✅ Stocks in Roth — tax-free growth on highest-return assets (ideal location)."
        if account_type == BROKERAGE:
            return "✅ Stocks in Brokerage — long-term capital gains rates apply (acceptable)."
        if account_type == TRADITIONAL:
            return (
                "⚠️ Stocks in Traditional — growth will be taxed as ordinary income on withdrawal. "
                "Consider holding bonds here and moving stocks to Roth or Brokerage."
            )
    if asset_class == "Cash":
        if account_type == BROKERAGE:
            return "✅ Cash (MF:CASH) in Brokerage — maintain ≥ 10% of brokerage value for liquidity."
        return "ℹ️ Cash in tax-advantaged account — acceptable for short-term needs or pending reallocation."
    return ""


# ---------------------------------------------------------------------------
# Helper: suggest a representative symbol for an asset class / account type
# ---------------------------------------------------------------------------

def _suggest_symbol(asset_class: str, account_type: str) -> str:
    """Return a representative ticker to buy for a given asset class and account type.

    Account-type conventions:
    - Traditional IRA  → Mutual funds (lower-cost, no bid/ask spread, ideal for
                         tax-deferred accounts where intra-day liquidity is irrelevant)
    - Roth IRA         → ETFs or individual stocks (tax-free growth; ETFs offer
                         flexibility and tax efficiency)
    - Brokerage        → ETFs or individual stocks (intra-day trading, tax-loss
                         harvesting, LTCG rates)
    """
    if asset_class == "Cash":
        return "MF:CASH"

    if asset_class == "Bonds":
        if account_type == TRADITIONAL:
            # Mutual fund — ideal for tax-deferred bond income
            return "VBTLX (Vanguard Total Bond Market Admiral)"
        if account_type == ROTH:
            # ETF — acceptable if bonds are held in Roth (though not ideal location)
            return "BND (Vanguard Total Bond Market ETF)"
        # Brokerage — ETF; prefer Treasuries/munis for tax efficiency
        return "VGIT (Vanguard Intermediate-Term Treasury ETF)"

    # Stocks
    if account_type == TRADITIONAL:
        # Mutual fund — tax-deferred growth, no intra-day trading needed
        return "VFIAX (Vanguard 500 Index Admiral)"
    if account_type == ROTH:
        # ETF — tax-free growth, flexibility
        return "VTI (Vanguard Total Market ETF)"
    # Brokerage — ETF for LTCG rates and tax-loss harvesting
    return "VTI (Vanguard Total Market ETF)"


# ---------------------------------------------------------------------------
# Convenience: build a display DataFrame from the report
# ---------------------------------------------------------------------------

def build_rebalance_display_df(report: RebalanceReport) -> pd.DataFrame:
    """
    Convert the asset_summary list into a display-ready DataFrame.

    Columns: Asset Class | Current Value | Current % | Target % | Drift % | Delta $ | Status
    """
    rows = []
    for s in report.asset_summary:
        if s.drift_pct > report.drift_threshold_pct:
            status = "🔴 Over-weight"
        elif s.drift_pct < -report.drift_threshold_pct:
            status = "🔴 Under-weight"
        else:
            status = "🟢 On Target"
        rows.append({
            "Asset Class":   s.asset_class,
            "Current Value": s.current_value,
            "Current %":     s.current_pct,
            "Target %":      s.target_pct,
            "Drift %":       s.drift_pct,
            "Delta $":       s.delta_value,
            "Status":        status,
        })
    return pd.DataFrame(rows)


def build_actions_display_df(report: RebalanceReport) -> pd.DataFrame:
    """
    Convert the actions list into a display-ready DataFrame.

    Columns: Priority | Action | Asset Class | Symbol | Account | Amount | Tax Impact | Rationale
    """
    rows = []
    for a in report.actions:
        rows.append({
            "Priority":    a.priority,
            "Action":      a.action,
            "Asset Class": a.asset_class,
            "Symbol":      a.symbol,
            "Account":     f"{a.account_name} ({a.account_type})",
            "Amount":      a.amount,
            "Tax Impact":  a.tax_impact,
            "Rationale":   a.rationale,
        })
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(
        {c: pd.Series(dtype="object") for c in
         ["Priority","Action","Asset Class","Symbol","Account","Amount","Tax Impact","Rationale"]}
    )


def build_holdings_by_class_df(report: RebalanceReport) -> pd.DataFrame:
    """
    Return a DataFrame of all holdings annotated with their asset class.
    """
    rows = []
    for h in report.holdings:
        rows.append({
            "Account":       h.account_name,
            "Account Type":  h.account_type,
            "Symbol":        h.symbol,
            "Name":          h.name,
            "Sector":        h.sector,
            "Asset Class":   h.asset_class,
            "Qty":           h.qty,
            "Current Price": h.current_price,
            "Current Value": h.current_value,
            "Cost Basis":    h.cost_basis,
            "Unrealized G/L":h.unrealized_gl,
        })
    return pd.DataFrame(rows)

# Made with Bob