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
import operator
import re
from collections import defaultdict
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
CASH_ACCT   = "Savings"   # plain savings / checking

# Minimum Brokerage cash cushion (10 % of brokerage market value)
BROKERAGE_CASH_MIN_PCT = 0.10

# Fraction of each tax-advantaged cash position kept as a liquidity buffer
# when deploying cash to buy under-weight assets (Step 7b).
TA_CASH_BUFFER_PCT = 0.10

# Default rebalance drift threshold
DEFAULT_DRIFT_THRESHOLD_PCT = 5.0

# RebalanceAction string literals shared across action-generation helpers
ACTION_SELL_REALLOCATE = "Sell / Reallocate"
TAX_IMPACT_NONE_TA     = "None (tax-deferred/free account)"
TAX_IMPACT_TLH         = "Tax-loss harvest opportunity"
TAX_IMPACT_LTCG_CHECK  = "Taxable event — check LTCG rate"

# Preferred account type for new contributions per asset class
_CONTRIBUTION_ACCOUNT: dict[str, str] = {
    "Bonds":  TRADITIONAL,
    "Stocks": ROTH,
    "Cash":   BROKERAGE,
}


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
    # Ensure sector and name are strings
    sector_str = str(sector) if sector is not None else ""
    name_str = str(name) if name is not None else ""
    sector_lower = sector_str.lower()
    name_lower   = name_str.lower()

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
# Holdings builder (Proposal 1)
# ---------------------------------------------------------------------------

def _build_holdings(raw: pd.DataFrame, price_map: dict[str, float]) -> list[HoldingDetail]:
    """
    Build the enriched holdings list from the raw portfolio DataFrame.

    Arithmetic columns are computed with sequential in-place assignments on a
    single copy of the input frame, avoiding intermediate DataFrame allocations.
    current_price is resolved via vectorized Series.map; classification helpers
    are applied row-wise via apply (regex logic prevents full vectorization).
    The final dataclass construction iterates over to_dict("records") for clean,
    statically-typed attribute access.

    Args:
        raw:       Portfolio DataFrame with columns: account_name, account_type,
                   symbol, name, sector, qty, purchase_price.
        price_map: Mapping symbol → current price (from _resolve_prices).

    Returns:
        List of HoldingDetail dataclass instances.
    """
    df = raw.copy()
    df["name"]   = df["name"].fillna(df["symbol"])
    df["sector"] = df["sector"].fillna("")
    # Vectorized price lookup; type: ignore suppresses basedpyright's strict
    # dict overload rejection — runtime behavior is correct.
    df["current_price"]  = df["symbol"].map(price_map).fillna(  # type: ignore[arg-type]
        df["purchase_price"]
    )
    df["current_value"]  = df["qty"] * df["current_price"]
    df["cost_basis"]     = df["qty"] * df["purchase_price"]
    df["unrealized_gl"]  = df["current_value"] - df["cost_basis"]
    df["asset_class"]    = df.apply(
        lambda r: _classify_asset(r["symbol"], r["sector"], r["name"]), axis=1
    )
    df["is_muni_or_tsy"] = df.apply(
        lambda r: _is_municipal_or_treasury(r["sector"], r["name"]), axis=1
    )
    # to_dict("records") gives plain dicts with statically-known keys,
    # avoiding the unresolvable named-tuple attribute errors from itertuples().
    return [
        HoldingDetail(
            account_name   = r["account_name"],
            account_type   = r["account_type"],
            symbol         = r["symbol"],
            name           = r["name"],
            sector         = r["sector"],
            qty            = float(r["qty"]),
            purchase_price = float(r["purchase_price"]),
            current_price  = float(r["current_price"]),
            current_value  = float(r["current_value"]),
            cost_basis     = float(r["cost_basis"]),
            unrealized_gl  = float(r["unrealized_gl"]),
            asset_class    = r["asset_class"],
            is_muni_or_tsy = bool(r["is_muni_or_tsy"]),
        )
        for r in df.to_dict("records")
    ]


# ---------------------------------------------------------------------------
# Holdings aggregation (Proposal 2)
# ---------------------------------------------------------------------------

def _aggregate_holdings(
    holdings: list[HoldingDetail],
) -> tuple[dict[str, float], float, float, list[str]]:
    """
    Single-pass aggregation over all holdings.

    Computes asset-class totals, brokerage account totals, and location
    warnings in one O(n) loop instead of four separate passes.

    Args:
        holdings: Enriched list produced by _build_holdings().

    Returns:
        class_totals:    Mapping asset_class → total current value.
        brok_total:      Total market value of all Brokerage holdings.
        brok_cash:       Cash portion of the Brokerage account.
        location_issues: Plain-English account-location warnings.
    """
    class_totals: dict[str, float] = {"Cash": 0.0, "Bonds": 0.0, "Stocks": 0.0}
    brok_total = 0.0
    brok_cash  = 0.0
    location_issues: list[str] = []

    for h in holdings:
        class_totals[h.asset_class] = class_totals.get(h.asset_class, 0.0) + h.current_value

        if h.account_type == BROKERAGE:
            brok_total += h.current_value
            if h.asset_class == "Cash":
                brok_cash += h.current_value

        # ── Account-location checks ──────────────────────────────────────────
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

    return class_totals, brok_total, brok_cash, location_issues


# ---------------------------------------------------------------------------
# Action-generation helpers (Proposal 3)
# ---------------------------------------------------------------------------

def _sell_rationale_tax_advantaged(
    ow: AssetClassSummary,
    h: HoldingDetail,
    sell_amt: float,
) -> str:
    """Build the rationale string for a tax-advantaged sell / reallocate action.

    Extracted from the loop body of _actions_tax_advantaged_sell() to keep
    control-flow and string-formatting concerns separate, and to mirror the
    pattern established by _brokerage_sell_rationale().

    Args:
        ow:       The over-weight asset-class summary driving the sell.
        h:        The specific holding being sold.
        sell_amt: Dollar amount being sold from this holding.

    Returns:
        Plain-English rationale string for RebalanceAction.rationale.
    """
    return (
        f"{ow.asset_class} is over-weight by {ow.drift_pct:+.1f}% "
        f"(current {ow.current_pct:.1f}% vs target {ow.target_pct:.1f}%). "
        f"Sell ${sell_amt:,.0f} of {h.symbol} inside {h.account_type} "
        f"({h.account_name}) — no tax event."
    )


def _sell_ta_action(
    ow: AssetClassSummary,
    h: HoldingDetail,
    sell_amt: float,
    priority: int,
) -> RebalanceAction:
    """Build one tax-advantaged sell RebalanceAction.

    Extracted from the inner loop of _actions_tax_advantaged_sell() to keep
    control-flow and object-construction concerns separate, and to make the
    action construction independently unit-testable.

    Args:
        ow:       The over-weight asset-class summary driving the sell.
        h:        The specific holding being sold.
        sell_amt: Dollar amount being sold from this holding.
        priority: Priority rank to assign to this action.

    Returns:
        A fully populated RebalanceAction instance.
    """
    return RebalanceAction(
        priority      = priority,
        action        = ACTION_SELL_REALLOCATE,
        asset_class   = ow.asset_class,
        symbol        = h.symbol,
        account_name  = h.account_name,
        account_type  = h.account_type,
        amount        = sell_amt,
        rationale     = _sell_rationale_tax_advantaged(ow, h, sell_amt),
        tax_impact    = TAX_IMPACT_NONE_TA,
        location_note = _location_guidance(ow.asset_class, h.account_type),
    )


def _actions_tax_advantaged_sell(
    over_weight: list[AssetClassSummary],
    under_weight: list[AssetClassSummary],
    holdings: list[HoldingDetail],
    start_priority: int,
) -> tuple[list[RebalanceAction], int, list[AssetClassSummary], set[tuple[str, str]]]:
    """
    Step 7a — Sell / reallocate inside Traditional or Roth accounts.

    No tax event occurs inside tax-advantaged accounts, so these trades are
    always recommended first.  Holdings are sorted largest-first to minimise
    the number of individual sell orders.
    
    This function now generates PAIRED sell/buy actions within the same account
    to ensure proceeds are immediately reinvested.

    Holdings are pre-grouped into a dict keyed by asset_class (single O(n)
    pass) before the outer loop, so the full holdings list is never re-scanned
    for each over-weight entry.  This mirrors the pattern used in
    _actions_brokerage_rebalance().  Rationale string construction is
    delegated to _sell_rationale_tax_advantaged() to keep the loop body
    focused on control flow.

    Args:
        over_weight:     Asset classes whose current weight exceeds the target.
        under_weight:    Asset classes whose current weight is below the target.
        holdings:        Full enriched holdings list.
        start_priority:  Priority counter to continue from.

    Returns:
        (actions, next_priority, remaining_under_weight, used_holdings)
    """
    actions: list[RebalanceAction] = []
    priority = start_priority
    
    # Track which holdings were used in sell actions (account_name, symbol)
    used_holdings: set[tuple[str, str]] = set()

    # Single O(n) pass: group Traditional/Roth holdings by asset_class,
    # sorted largest-first to minimise the number of sell orders.
    _ta: defaultdict[str, list[HoldingDetail]] = defaultdict(list)
    for h in holdings:
        if h.account_type in (TRADITIONAL, ROTH):
            _ta[h.asset_class].append(h)
    sorted_ta: dict[str, list[HoldingDetail]] = {
        ac: sorted(hs, key=operator.attrgetter("current_value"), reverse=True)
        for ac, hs in _ta.items()
    }

    # Track how much each under-weight class still needs
    uw_needs: dict[str, float] = {uw.asset_class: abs(uw.delta_value) for uw in under_weight}
    
    for ow in over_weight:
        sell_needed = abs(ow.delta_value)
        for h in sorted_ta.get(ow.asset_class, []):
            if sell_needed <= 0:
                break
            sell_amt = min(h.current_value, sell_needed)
            
            # Generate sell action and track this holding as used
            actions.append(_sell_ta_action(ow, h, sell_amt, priority))
            used_holdings.add((h.account_name, h.symbol))
            priority += 1
            
            # Try to pair with a buy action in the SAME account for under-weight assets
            remaining_proceeds = sell_amt
            for uw in under_weight:
                if uw_needs.get(uw.asset_class, 0) <= 0:
                    continue
                if remaining_proceeds <= 0:
                    break
                    
                # Only buy in the same account where we sold
                buy_amt = min(remaining_proceeds, uw_needs[uw.asset_class])
                
                # Create a pseudo-holding for the buy action
                buy_action = RebalanceAction(
                    priority      = priority,
                    action        = "Buy",
                    asset_class   = uw.asset_class,
                    symbol        = _suggest_symbol(uw.asset_class, h.account_type),
                    account_name  = h.account_name,
                    account_type  = h.account_type,
                    amount        = buy_amt,
                    rationale     = (
                        f"{uw.asset_class} is under-weight by {abs(uw.drift_pct):.1f}% "
                        f"(current {uw.current_pct:.1f}% vs target {uw.target_pct:.1f}%). "
                        f"Use ${buy_amt:,.0f} from {ow.asset_class} sale proceeds in "
                        f"{h.account_type} ({h.account_name}) to buy {uw.asset_class} — no tax event."
                    ),
                    tax_impact    = TAX_IMPACT_NONE_TA,
                    location_note = _location_guidance(uw.asset_class, h.account_type),
                )
                actions.append(buy_action)
                priority += 1
                
                uw_needs[uw.asset_class] -= buy_amt
                remaining_proceeds -= buy_amt
            
            # If there are remaining proceeds after satisfying all under-weight needs,
            # generate an explicit "Hold as Cash" action to clarify the full disposition
            if remaining_proceeds > 100:  # Only show if significant (> $100)
                cash_action = RebalanceAction(
                    priority      = priority,
                    action        = "Hold as Cash",
                    asset_class   = "Cash",
                    symbol        = CASH_SYMBOL,
                    account_name  = h.account_name,
                    account_type  = h.account_type,
                    amount        = remaining_proceeds,
                    rationale     = (
                        f"After rebalancing, ${remaining_proceeds:,.0f} from {ow.asset_class} sale "
                        f"remains in {h.account_type} ({h.account_name}) as cash. "
                        f"This provides liquidity and can be deployed when additional rebalancing opportunities arise."
                    ),
                    tax_impact    = TAX_IMPACT_NONE_TA,
                    location_note = "Cash in tax-advantaged accounts provides flexibility for future rebalancing without tax consequences.",
                )
                actions.append(cash_action)
                priority += 1
            
            sell_needed -= sell_amt

    # Update under_weight list with remaining needs
    # Only include needs > $100 to avoid tiny residual amounts from floating point arithmetic
    MIN_REMAINING_NEED = 100.0
    remaining_uw = [
        AssetClassSummary(
            asset_class=uw.asset_class,
            current_value=uw.current_value,
            current_pct=uw.current_pct,
            target_pct=uw.target_pct,
            drift_pct=uw.drift_pct,
            is_drifted=uw.is_drifted,
            delta_value=-uw_needs.get(uw.asset_class, 0),  # Negative because it's still needed
        )
        for uw in under_weight
        if uw_needs.get(uw.asset_class, 0) > MIN_REMAINING_NEED
    ]

    return actions, priority, remaining_uw, used_holdings


def _buy_rationale_tax_advantaged(
    uw: AssetClassSummary,
    h: HoldingDetail,
    buy_amt: float,
) -> str:
    """Build the rationale string for a tax-advantaged buy action.

    Extracted from the loop body of _actions_tax_advantaged_buy() to keep
    control-flow and string-formatting concerns separate, and to mirror the
    pattern established by _sell_rationale_tax_advantaged().

    Args:
        uw:      The under-weight asset-class summary driving the buy.
        h:       The cash holding being drawn from.
        buy_amt: Dollar amount being deployed from this cash position.

    Returns:
        Plain-English rationale string for RebalanceAction.rationale.
    """
    return (
        f"{uw.asset_class} is under-weight by {abs(uw.drift_pct):.1f}% "
        f"(current {uw.current_pct:.1f}% vs target {uw.target_pct:.1f}%). "
        f"Use ${buy_amt:,.0f} of cash in {h.account_type} ({h.account_name}) "
        f"to buy {uw.asset_class} — no tax event."
    )


def _buy_ta_action(
    uw: AssetClassSummary,
    h: HoldingDetail,
    buy_amt: float,
    priority: int,
) -> RebalanceAction:
    """Build one tax-advantaged buy RebalanceAction.

    Extracted from the inner loop of _actions_tax_advantaged_buy() to keep
    control-flow and object-construction concerns separate, and to make the
    action construction independently unit-testable.  Mirrors the pattern
    established by _sell_ta_action().

    Args:
        uw:       The under-weight asset-class summary driving the buy.
        h:        The cash holding being drawn from.
        buy_amt:  Dollar amount being deployed from this cash position.
        priority: Priority rank to assign to this action.

    Returns:
        A fully populated RebalanceAction instance.
    """
    return RebalanceAction(
        priority      = priority,
        action        = "Buy",
        asset_class   = uw.asset_class,
        symbol        = _suggest_symbol(uw.asset_class, h.account_type),
        account_name  = h.account_name,
        account_type  = h.account_type,
        amount        = buy_amt,
        rationale     = _buy_rationale_tax_advantaged(uw, h, buy_amt),
        tax_impact    = TAX_IMPACT_NONE_TA,
        location_note = _location_guidance(uw.asset_class, h.account_type),
    )


def _actions_tax_advantaged_buy(
    under_weight: list[AssetClassSummary],
    holdings: list[HoldingDetail],
    used_holdings: set[tuple[str, str]],
    start_priority: int,
) -> tuple[list[RebalanceAction], int]:
    """
    Step 7b — Buy inside Traditional or Roth using available cash.

    Draws from cash holdings inside tax-advantaged accounts, keeping a
    ``TA_CASH_BUFFER_PCT`` reserve in each cash position to avoid fully
    depleting liquidity.  Cash is treated as a shared, depletable resource:
    the sorted cash list is consumed in priority order across all under-weight
    classes so that the largest cash positions are never re-visited once
    exhausted.
    
    Skips cash holdings that were already sold in step 7a (paired sell/buy actions).

    Cash holdings are filtered (positive balances only) and sorted once before
    the outer loop (single O(n) pass + one sort), so the full holdings list is
    never re-scanned or re-sorted for each under-weight entry.  This mirrors
    the pattern used in _actions_tax_advantaged_sell() and
    _actions_brokerage_rebalance().  A shared iterator advances through the
    sorted list; the inner for-loop breaks as soon as the under-weight need is
    met, and resumes from the same position on the next outer iteration so
    exhausted positions are never re-visited.  Action construction is delegated
    to _buy_ta_action() to keep the loop body focused on control flow.

    Args:
        under_weight:    Asset classes whose current weight is below the target.
        holdings:        Full enriched holdings list.
        used_holdings:   Set of (account_name, symbol) tuples that were already sold.
        start_priority:  Priority counter to continue from.

    Returns:
        (actions, next_priority)
    """
    actions: list[RebalanceAction] = []
    priority = start_priority

    # Single O(n) pass: collect positive-balance Traditional/Roth cash holdings,
    # largest-first.  Zero/negative positions are excluded so the inner loop
    # never needs to guard against a non-positive available_cash.
    # ALSO skip holdings that were already sold in step 7a.
    trad_roth_cash: list[HoldingDetail] = sorted(
        (
            h for h in holdings
            if h.asset_class == "Cash"
            and h.account_type in (TRADITIONAL, ROTH)
            and h.current_value > 0
            and (h.account_name, h.symbol) not in used_holdings
        ),
        key=operator.attrgetter("current_value"),
        reverse=True,
    )

    # Shared iterator: position is preserved across outer iterations so each
    # cash position is visited at most once across all under-weight entries.
    cash_iter = iter(trad_roth_cash)
    for uw in under_weight:
        buy_needed = abs(uw.delta_value)
        if buy_needed <= 0:
            continue
        for h in cash_iter:
            available_cash = h.current_value * (1 - TA_CASH_BUFFER_PCT)
            buy_amt = min(available_cash, buy_needed)
            actions.append(_buy_ta_action(uw, h, buy_amt, priority))
            buy_needed -= buy_amt
            priority += 1
            if buy_needed <= 0:
                break

    return actions, priority


def _brokerage_sell_rationale(
    ow: AssetClassSummary,
    h: HoldingDetail,
    sell_amt: float,
) -> str:
    """Build the rationale string for a Brokerage sell / tax-loss harvest action.

    Args:
        ow:       The over-weight asset-class summary driving the sell.
        h:        The specific holding being sold.
        sell_amt: Dollar amount being sold from this holding.

    Returns:
        Plain-English rationale string for RebalanceAction.rationale.
    """
    header = (
        f"{ow.asset_class} is over-weight. Sell ${sell_amt:,.0f} of {h.symbol} "
        f"in Brokerage ({h.account_name}). "
    )
    if h.unrealized_gl < 0:
        return header + (
            f"Unrealized loss of ${abs(h.unrealized_gl):,.0f} — "
            "consider tax-loss harvesting with a wash-sale-safe replacement."
        )
    return header + (
        f"Unrealized gain of ${h.unrealized_gl:,.0f} — "
        "check LTCG rate before selling."
    )


def _brokerage_sell_action(
    ow: AssetClassSummary,
    h: HoldingDetail,
    sell_amt: float,
    priority: int,
) -> RebalanceAction:
    """Build one Brokerage sell RebalanceAction.

    Extracted from the inner loop of _actions_brokerage_rebalance() to keep
    control-flow and object-construction concerns separate, and to mirror the
    pattern established by _sell_ta_action().

    Args:
        ow:       The over-weight asset-class summary driving the sell.
        h:        The specific holding being sold.
        sell_amt: Dollar amount being sold from this holding.
        priority: Priority rank to assign to this action.

    Returns:
        A fully populated RebalanceAction instance.
    """
    return RebalanceAction(
        priority      = priority,
        action        = "Sell (Brokerage)",
        asset_class   = ow.asset_class,
        symbol        = h.symbol,
        account_name  = h.account_name,
        account_type  = h.account_type,
        amount        = sell_amt,
        rationale     = _brokerage_sell_rationale(ow, h, sell_amt),
        tax_impact    = TAX_IMPACT_TLH if h.unrealized_gl < 0 else TAX_IMPACT_LTCG_CHECK,
        location_note = _location_guidance(ow.asset_class, BROKERAGE),
    )


def _actions_brokerage_rebalance(
    over_weight: list[AssetClassSummary],
    under_weight: list[AssetClassSummary],
    holdings: list[HoldingDetail],
    start_priority: int,
) -> tuple[list[RebalanceAction], int, list[AssetClassSummary]]:
    """
    Step 7c — Sell over-weight positions in Brokerage and pair with buy actions.

    Holdings are sorted by unrealized gain/loss (losses first) to surface
    tax-loss harvesting opportunities.  Each action is flagged with the
    appropriate tax impact string.
    
    This function now generates PAIRED sell/buy actions within Brokerage to ensure
    proceeds are immediately reinvested.

    Brokerage holdings are pre-grouped into a defaultdict keyed by asset_class
    (each bucket sorted losses-first in-place) before the outer loop, so the
    full holdings list is scanned only once regardless of how many asset classes
    are over-weight.  Action construction is delegated to _brokerage_sell_action()
    to keep the loop body focused on control flow.

    Args:
        over_weight:     Asset classes whose current weight exceeds the target.
        under_weight:    Asset classes whose current weight is below the target.
        holdings:        Full enriched holdings list.
        start_priority:  Priority counter to continue from.

    Returns:
        (actions, next_priority, remaining_under_weight)
    """
    if not over_weight:
        return [], start_priority, under_weight

    actions: list[RebalanceAction] = []
    priority = start_priority
    sell_action = _brokerage_sell_action  # cache global lookup; avoids LOAD_GLOBAL in hot loop

    # Single O(n) pass: group Brokerage holdings by asset_class, losses first.
    # This avoids re-scanning and re-sorting `holdings` for every over-weight entry.
    # Lists are sorted in-place (no per-class allocation) after grouping is complete.
    brokerage_holdings: defaultdict[str, list[HoldingDetail]] = defaultdict(list)
    for h in holdings:
        if h.account_type == BROKERAGE:
            brokerage_holdings[h.asset_class].append(h)
    for hs in brokerage_holdings.values():
        hs.sort(key=operator.attrgetter("unrealized_gl"))

    # Track how much each under-weight class still needs
    uw_needs: dict[str, float] = {uw.asset_class: abs(uw.delta_value) for uw in under_weight}

    for ow in over_weight:
        sell_needed = abs(ow.delta_value)
        for h in brokerage_holdings.get(ow.asset_class, []):
            if sell_needed <= 0:
                break
            sell_amt = min(h.current_value, sell_needed)
            
            # Generate sell action
            actions.append(sell_action(ow, h, sell_amt, priority))
            priority += 1
            
            # Try to pair with a buy action in Brokerage for under-weight assets
            remaining_proceeds = sell_amt
            for uw in under_weight:
                if uw_needs.get(uw.asset_class, 0) <= 0:
                    continue
                if remaining_proceeds <= 0:
                    break
                    
                buy_amt = min(remaining_proceeds, uw_needs[uw.asset_class])
                
                # Create buy action in Brokerage
                buy_action = RebalanceAction(
                    priority      = priority,
                    action        = "Buy (Brokerage)",
                    asset_class   = uw.asset_class,
                    symbol        = _suggest_symbol(uw.asset_class, BROKERAGE),
                    account_name  = h.account_name,
                    account_type  = BROKERAGE,
                    amount        = buy_amt,
                    rationale     = (
                        f"{uw.asset_class} is under-weight by {abs(uw.drift_pct):.1f}% "
                        f"(current {uw.current_pct:.1f}% vs target {uw.target_pct:.1f}%). "
                        f"Use ${buy_amt:,.0f} from {ow.asset_class} sale proceeds in "
                        f"Brokerage ({h.account_name}) to buy {uw.asset_class}."
                    ),
                    tax_impact    = "Taxable event on sale; new purchase establishes basis",
                    location_note = _location_guidance(uw.asset_class, BROKERAGE),
                )
                actions.append(buy_action)
                priority += 1
                
                uw_needs[uw.asset_class] -= buy_amt
                remaining_proceeds -= buy_amt
            
            # If there are remaining proceeds (no under-weight assets to buy),
            # add action to hold as cash in brokerage
            if remaining_proceeds > 100:  # Only if significant amount remains
                cash_action = RebalanceAction(
                    priority      = priority,
                    action        = "Hold as Cash (Brokerage)",
                    asset_class   = "Cash",
                    symbol        = CASH_SYMBOL,
                    account_name  = h.account_name,
                    account_type  = BROKERAGE,
                    amount        = remaining_proceeds,
                    rationale     = (
                        f"Hold ${remaining_proceeds:,.0f} from {ow.asset_class} sale proceeds as cash in "
                        f"Brokerage ({h.account_name}). All under-weight asset classes have been satisfied "
                        f"in tax-advantaged accounts. This maintains the brokerage cash cushion."
                    ),
                    tax_impact    = "None (cash position)",
                    location_note = _location_guidance("Cash", BROKERAGE),
                )
                actions.append(cash_action)
                priority += 1
            
            sell_needed -= sell_amt

    # Update under_weight list with remaining needs
    # Only include needs > $100 to avoid tiny residual amounts from floating point arithmetic
    MIN_REMAINING_NEED = 100.0
    remaining_uw = [
        AssetClassSummary(
            asset_class=uw.asset_class,
            current_value=uw.current_value,
            current_pct=uw.current_pct,
            target_pct=uw.target_pct,
            drift_pct=uw.drift_pct,
            is_drifted=uw.is_drifted,
            delta_value=-uw_needs.get(uw.asset_class, 0),  # Negative because it's still needed
        )
        for uw in under_weight
        if uw_needs.get(uw.asset_class, 0) > MIN_REMAINING_NEED
    ]

    return actions, priority, remaining_uw


def _actions_redirect_contributions(
    under_weight: list[AssetClassSummary],
    start_priority: int,
) -> tuple[list[RebalanceAction], int]:
    """
    Step 7d — Redirect new contributions / dividends to under-weight classes.

    Uses the optimal account type per asset class:
      Bonds  → Traditional (ordinary income taxed on withdrawal anyway)
      Stocks → Roth (tax-free growth on highest-return assets)
      Cash   → Brokerage (liquidity cushion)
    
    Shows realistic annual contribution amounts (e.g., $7,000 for IRA, $23,000 for 401k)
    rather than the full rebalancing need, which may take multiple years to achieve.

    Args:
        under_weight:    Asset classes whose current weight is below the target.
        start_priority:  Priority counter to continue from.

    Returns:
        (actions, next_priority)
    """
    actions: list[RebalanceAction] = []
    priority = start_priority

    # Realistic annual contribution limits (2026)
    ANNUAL_LIMITS = {
        ROTH: 7000,          # Roth IRA limit
        TRADITIONAL: 7000,   # Traditional IRA limit
        BROKERAGE: float('inf'),  # No limit for taxable accounts
    }

    for uw in under_weight:
        contrib_acct = _CONTRIBUTION_ACCOUNT.get(uw.asset_class, TRADITIONAL)
        needed = abs(uw.delta_value)
        annual_limit = ANNUAL_LIMITS.get(contrib_acct, 7000)
        
        # Show realistic annual contribution amount
        realistic_amount = min(needed, annual_limit)
        
        # Calculate how many years it would take at this rate
        years_needed = needed / realistic_amount if realistic_amount > 0 else 0
        
        rationale_parts = [
            f"{uw.asset_class} is under-weight by {abs(uw.drift_pct):.1f}%. "
        ]
        
        if needed <= annual_limit:
            rationale_parts.append(
                f"Direct new contributions, dividends, and RMDs toward {uw.asset_class} "
                f"in your {contrib_acct} account until the target of {uw.target_pct:.1f}% is restored."
            )
        else:
            rationale_parts.append(
                f"Direct annual contributions of ~${realistic_amount:,.0f} toward {uw.asset_class} "
                f"in your {contrib_acct} account. "
                f"At this rate, it will take approximately {years_needed:.1f} years to reach "
                f"the target of {uw.target_pct:.1f}%."
            )
        
        actions.append(RebalanceAction(
            priority     = priority,
            action       = "Redirect Contributions",
            asset_class  = uw.asset_class,
            symbol       = _suggest_symbol(uw.asset_class, contrib_acct),
            account_name = f"{contrib_acct} account (preferred)",
            account_type = contrib_acct,
            amount       = realistic_amount,  # Show realistic annual amount
            rationale    = "".join(rationale_parts),
            tax_impact    = "None (new money)",
            location_note = _location_guidance(uw.asset_class, contrib_acct),
        ))
        priority += 1

    return actions, priority


def _actions_brokerage_cash_topup(
    brok_cash_ok: bool,
    brok_total: float,
    brok_cash: float,
    brok_cash_pct: float,
    start_priority: int,
    holdings: Optional[list[HoldingDetail]] = None,
) -> tuple[list[RebalanceAction], int]:
    """
    Step 7e — Top up the Brokerage cash cushion if it falls below 10 %.

    Args:
        brok_cash_ok:    True when the cushion already meets the minimum.
        brok_total:      Total Brokerage account market value.
        brok_cash:       Current cash portion of the Brokerage account.
        brok_cash_pct:   brok_cash / brok_total (pre-computed ratio).
        start_priority:  Priority counter to continue from.
        holdings:        Optional holdings list to identify specific brokerage accounts.

    Returns:
        (actions, next_priority)
    """
    actions: list[RebalanceAction] = []
    priority = start_priority

    if not brok_cash_ok:
        needed = BROKERAGE_CASH_MIN_PCT * brok_total - brok_cash
        
        # Try to identify the largest brokerage account to add cash to
        account_name = "Brokerage account"
        if holdings:
            brok_accounts: dict[str, float] = {}
            for h in holdings:
                if h.account_type == BROKERAGE:
                    brok_accounts[h.account_name] = brok_accounts.get(h.account_name, 0) + h.current_value
            if brok_accounts:
                # Use the largest brokerage account
                account_name = max(brok_accounts.items(), key=lambda x: x[1])[0]
        
        actions.append(RebalanceAction(
            priority     = priority,
            action       = "Buy MF:CASH",
            asset_class  = "Cash",
            symbol       = CASH_SYMBOL,
            account_name = account_name,
            account_type = BROKERAGE,
            amount       = needed,
            rationale    = (
                f"Brokerage cash cushion is {brok_cash_pct:.1%} "
                f"(target ≥ {BROKERAGE_CASH_MIN_PCT:.0%}). "
                f"Add ${needed:,.0f} to MF:CASH in {account_name} to maintain liquidity. "
                f"This can come from new contributions, dividends, or by holding some of the "
                f"stock sale proceeds as cash rather than reinvesting immediately."
            ),
            tax_impact    = "None (buying cash equivalent)",
            location_note = "Keep ≥ 10% of Brokerage account in MF:CASH for liquidity.",
        ))
        priority += 1

    return actions, priority


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
    holdings = _build_holdings(raw, price_map)

    total_value = sum(h.current_value for h in holdings)
    if total_value <= 0:
        total_value = 1.0  # guard against division by zero

    # ── 4. Asset-class aggregation + location checks (single pass) ───────────
    class_totals, brok_total, brok_cash, location_issues = _aggregate_holdings(holdings)

    # ── 5. Brokerage cash cushion check ─────────────────────────────────────
    brok_cash_pct = (brok_cash / brok_total) if brok_total > 0 else 0.0
    brok_cash_ok  = brok_cash_pct >= BROKERAGE_CASH_MIN_PCT

    if not brok_cash_ok:
        needed = BROKERAGE_CASH_MIN_PCT * brok_total - brok_cash
        location_issues.append(
            f"⚠️ Brokerage cash cushion is {brok_cash_pct:.1%} "
            f"(target ≥ {BROKERAGE_CASH_MIN_PCT:.0%}). "
            f"Consider adding ${needed:,.0f} to MF:CASH in the Brokerage account."
        )

    # ── 6. Asset-class summary ───────────────────────────────────────────────
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

    # ── 7. Build rebalancing action list ────────────────────────────────────
    over_weight  = [s for s in asset_summary if s.drift_pct >  drift_threshold_pct]
    under_weight = [s for s in asset_summary if s.drift_pct < -drift_threshold_pct]

    actions: list[RebalanceAction] = []
    priority = 1

    # 7a. Rebalance inside tax-advantaged accounts first (no tax event)
    # This now generates paired sell/buy actions and returns remaining under-weight needs
    new_actions, priority, remaining_under_weight, used_ta_holdings = _actions_tax_advantaged_sell(
        over_weight, under_weight, holdings, priority
    )
    actions.extend(new_actions)

    # 7b. Buy inside tax-advantaged accounts using available cash (for remaining needs)
    # Skip cash holdings that were already sold in step 7a
    new_actions, priority = _actions_tax_advantaged_buy(
        remaining_under_weight, holdings, used_ta_holdings, priority
    )
    actions.extend(new_actions)

    # 7c. Tax-loss harvest / sell in Brokerage to fund remaining rebalancing
    # This now generates paired sell/buy actions and returns remaining under-weight needs
    new_actions, priority, final_under_weight = _actions_brokerage_rebalance(
        over_weight, remaining_under_weight, holdings, priority
    )
    actions.extend(new_actions)

    # 7d. Redirect contributions / dividends to under-weight classes (for any remaining needs)
    new_actions, priority = _actions_redirect_contributions(final_under_weight, priority)
    actions.extend(new_actions)

    # 7e. Brokerage cash cushion top-up
    new_actions, priority = _actions_brokerage_cash_topup(
        brok_cash_ok, brok_total, brok_cash, brok_cash_pct, priority, holdings
    )
    actions.extend(new_actions)

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
    
    Reads preferences from configuration file if available, otherwise uses defaults.

    Account-type conventions:
    - Traditional IRA  → Mutual funds (lower-cost, no bid/ask spread, ideal for
                         tax-deferred accounts where intra-day liquidity is irrelevant)
    - Roth IRA         → ETFs or individual stocks (tax-free growth; ETFs offer
                         flexibility and tax efficiency)
    - Brokerage        → ETFs or individual stocks (intra-day trading, tax-loss
                         harvesting, LTCG rates)
    """
    # Try to load preferences from config, fall back to defaults
    try:
        from config import get_config_manager
        config_mgr = get_config_manager()
        
        if asset_class == "Cash":
            return config_mgr.get("rebalancing_preferences", "cash_symbol", "MF:CASH")

        if asset_class == "Bonds":
            if account_type == TRADITIONAL:
                return config_mgr.get("rebalancing_preferences", "bonds_traditional",
                                     "VBTLX (Vanguard Total Bond Market Admiral)")
            if account_type == ROTH:
                return config_mgr.get("rebalancing_preferences", "bonds_roth",
                                     "BND (Vanguard Total Bond Market ETF)")
            # Brokerage
            return config_mgr.get("rebalancing_preferences", "bonds_brokerage",
                                 "VGIT (Vanguard Intermediate-Term Treasury ETF)")

        # Stocks
        if account_type == TRADITIONAL:
            return config_mgr.get("rebalancing_preferences", "stocks_traditional",
                                 "VFIAX (Vanguard 500 Index Admiral)")
        if account_type == ROTH:
            return config_mgr.get("rebalancing_preferences", "stocks_roth",
                                 "VTI (Vanguard Total Market ETF)")
        # Brokerage
        return config_mgr.get("rebalancing_preferences", "stocks_brokerage",
                             "VTI (Vanguard Total Market ETF)")
    
    except Exception:
        # Fall back to hardcoded defaults if config is unavailable
        if asset_class == "Cash":
            return "MF:CASH"

        if asset_class == "Bonds":
            if account_type == TRADITIONAL:
                return "VBTLX (Vanguard Total Bond Market Admiral)"
            if account_type == ROTH:
                return "BND (Vanguard Total Bond Market ETF)"
            return "VGIT (Vanguard Intermediate-Term Treasury ETF)"

        # Stocks
        if account_type == TRADITIONAL:
            return "VFIAX (Vanguard 500 Index Admiral)"
        if account_type == ROTH:
            return "VTI (Vanguard Total Market ETF)"
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