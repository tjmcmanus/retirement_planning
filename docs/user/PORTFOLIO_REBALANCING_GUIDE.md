# Portfolio Rebalancing Guide

> **Module:** [`portfolio_rebalancing.py`](portfolio_rebalancing.py)
> **UI Location:** 💼 Portfolio → ⚖️ Rebalancing tab
> **Added:** 2026-02-28

---

## Table of Contents

1. [Overview](#overview)
2. [Why Rebalance?](#why-rebalance)
3. [The 5% Drift Rule](#the-5-drift-rule)
4. [Asset Classification](#asset-classification)
5. [Default Target Allocation](#default-target-allocation)
6. [Account-Location Rules](#account-location-rules)
7. [Brokerage Cash Cushion](#brokerage-cash-cushion)
8. [Tax-Efficient Rebalancing Priority](#tax-efficient-rebalancing-priority)
9. [Integration with Tax Harvesting](#integration-with-tax-harvesting)
10. [Using the UI](#using-the-ui)
11. [API Reference](#api-reference)
12. [Data Classes](#data-classes)
13. [Examples](#examples)
14. [Troubleshooting](#troubleshooting)

---

## Overview

The Portfolio Rebalancing module analyses your **entire portfolio** across all accounts
(Cash, Brokerage, Traditional IRA, Roth IRA) and:

1. **Classifies** every holding as Cash, Bonds, or Stocks.
2. **Calculates** the current allocation percentage for each asset class.
3. **Detects drift** — flags any class that has moved more than the threshold from its target.
4. **Generates a prioritised action plan** that minimises taxes while restoring balance.
5. **Enforces account-location rules** — warns when assets are in sub-optimal accounts.

---

## Why Rebalance?

Over time, asset classes grow at different rates. A portfolio that started at
**10% Cash / 10% Bonds / 80% Stocks** might drift to **5% / 12% / 83%** after a strong
equity run — increasing risk beyond your intended level.

Regular rebalancing:
- Maintains your target risk profile
- Forces a systematic "buy low, sell high" discipline
- Prevents any single asset class from dominating the portfolio

---

## The 5% Drift Rule

Rebalance when any asset class deviates more than **5 percentage points** from its target.

| Scenario | Cash | Bonds | Stocks | Action |
|---|---|---|---|---|
| Initial target | 10% | 10% | 80% | — |
| After equity run | 5% | 12% | 83% | 🔴 Rebalance — Cash under-weight by 5%, Stocks over-weight by 3% |
| Within tolerance | 9% | 11% | 80% | 🟢 No action needed |

The threshold is configurable in the UI (default 5%).

---

## Asset Classification

Every holding is classified using the `sector` field from `portfolio_data_truth.csv`:

| Classification | Criteria |
|---|---|
| **Cash** | Symbol == `MF:CASH`, or sector contains "cash" / "money market" |
| **Bonds** | Sector contains "bond", "fixed income", "treasury", "treasuries", "municipal", "muni", "income", "fixed" |
| **Stocks** | Everything else (equities, ETFs, mutual funds not matching above) |

### Examples

| Symbol | Sector | Classification |
|---|---|---|
| `MF:CASH` | MF:Cash | Cash |
| `VBTLX` | Bond | Bonds |
| `VGIT` | Treasury | Bonds |
| `VFIAX` | MF:Large-Cap Blend | Stocks |
| `GOOGL` | Technology | Stocks |
| `JNJ` | Healthcare | Stocks |

---

## Default Target Allocation

| Asset Class | Default Target | Rationale |
|---|---|---|
| **Cash** | 10% | Liquidity for expenses, rebalancing trades, and opportunities |
| **Bonds** | 10% | Stability and income; held in Traditional IRA for tax efficiency |
| **Stocks** | 80% | Long-term growth; held in Roth (tax-free) or Brokerage (LTCG rates) |

All three targets are configurable in the UI and must sum to 100%.

---

## Account-Location Rules

Optimal asset location reduces taxes over the long term.

### Bonds → Traditional IRA (preferred)

Bond interest is taxed as **ordinary income**. Holding bonds in a Traditional IRA
defers that tax until withdrawal — when you may be in a lower bracket.

**Exception:** Municipal bonds (federally tax-exempt) and Treasuries (state-tax-exempt)
may be held in a Brokerage account without significant tax drag.

```
✅ VBTLX (Total Bond Market) in Traditional IRA
✅ VGIT (Intermediate Treasury) in Brokerage
✅ Muni bond fund in Brokerage
⚠️ VBTLX in Brokerage — interest taxable each year
💡 VBTLX in Roth — wastes Roth space on low-return asset
```

### Stocks → Roth IRA (preferred) or Brokerage

Stock growth in a Roth IRA is **completely tax-free**. Placing your highest-growth
assets here maximises the benefit of tax-free compounding.

Brokerage is acceptable for stocks — long-term capital gains rates (0%, 15%, 20%)
are much lower than ordinary income rates.

```
✅ VFIAX (S&P 500) in Roth IRA — tax-free growth
✅ GOOGL in Brokerage — LTCG rates on gains
⚠️ VFIAX in Traditional IRA — growth taxed as ordinary income on withdrawal
```

### Cash → Brokerage (≥ 10%)

Keep at least **10% of your Brokerage account** in `MF:CASH` (money market) for:
- Liquidity to fund rebalancing trades without forced sales
- Tax payments (estimated quarterly taxes)
- Opportunistic purchases during market dips

---

## Brokerage Cash Cushion

The module checks whether the Brokerage account holds at least **10%** of its total
value in `MF:CASH`.

| Status | Indicator |
|---|---|
| ≥ 10% cash | ✅ Adequate liquidity |
| < 10% cash | ⚠️ Warning + action to top up |

The required top-up amount is calculated as:
```
needed = 10% × brokerage_total_value − current_brokerage_cash
```

---

## Tax-Efficient Rebalancing Priority

Actions are generated in this order to minimise tax impact:

### Priority 1 — Rebalance Inside Tax-Advantaged Accounts
Sell over-weight assets and buy under-weight assets **within the same Traditional or
Roth account**. No tax event occurs — gains and losses inside these accounts are
not taxable until withdrawal (Traditional) or never (Roth).

### Priority 2 — Tax-Loss Harvest in Brokerage
If rebalancing requires selling in a Brokerage account, prioritise positions with
**unrealized losses** first. Booking the loss offsets other gains or up to $3,000
of ordinary income. See [`tax_harvesting.py`](tax_harvesting.py) for wash-sale-safe
replacement suggestions.

### Priority 3 — Redirect Contributions and Dividends
Direct new money (401k contributions, IRA contributions, dividends, RMDs) toward
**under-weight asset classes** until balance is restored — without selling anything.

### Priority 4 — Brokerage Cash Cushion Top-Up
If the Brokerage cash cushion is below 10%, add `MF:CASH` to restore liquidity.

---

## Integration with Tax Harvesting

The rebalancing module and [`tax_harvesting.py`](tax_harvesting.py) are complementary:

| Feature | Module | When to Use |
|---|---|---|
| Identify loss/gain harvest opportunities | `tax_harvesting.py` | Ongoing — any time |
| Rebalance asset classes across accounts | `portfolio_rebalancing.py` | When drift > threshold |
| Combined: sell losers in Brokerage to fund rebalancing | Both | When Brokerage is over-weight AND has unrealized losses |

**Workflow:**
1. Check the **⚖️ Rebalancing** tab — is rebalancing needed?
2. If Brokerage sells are required, switch to the **🌾 Tax Harvesting** tab.
3. Identify positions with unrealized losses in the over-weight asset class.
4. Sell the losers (harvest the loss), buy a wash-sale-safe replacement in the
   under-weight asset class.

---

## Using the UI

### Location
**💼 Portfolio** tab → **⚖️ Rebalancing** sub-tab

### Inputs

| Field | Default | Description |
|---|---|---|
| Target Cash % | 10 | Target allocation to Cash / money market |
| Target Bonds % | 10 | Target allocation to Bonds / fixed income |
| Target Stocks % | 80 | Target allocation to Equities |
| Drift Threshold % | 5 | Trigger rebalancing when any class drifts this many points |

> ⚠️ The three target percentages must sum to exactly 100%.

### Output Sections

1. **Status Banner** — 🔴 Rebalancing Required / ✅ Portfolio is balanced
2. **Asset Class Metrics** — Current %, Target %, Drift delta for Cash / Bonds / Stocks
3. **Charts** — Stacked bar (Current vs Target) + donut pie (current mix)
4. **Brokerage Cash Cushion** — Status and top-up amount if needed
5. **Account-Location Recommendations** — ⚠️ warnings and 💡 suggestions
6. **Holdings by Asset Class** — Expandable table of all holdings with classification
7. **Rebalancing Action Plan** — Colour-coded action cards ordered by priority
8. **📚 Rebalancing Strategy Guide** — In-app educational reference

### Action Card Colours

| Colour | Meaning |
|---|---|
| 🟢 Green border | Buy inside tax-advantaged account (no tax event) |
| 🔵 Blue border | Sell inside tax-advantaged account (no tax event) |
| 🟠 Orange border | Sell in Brokerage (potential tax event) |
| ⚫ Grey border | Redirect contributions / dividends |

---

## API Reference

### `compute_rebalance_plan()`

```python
from portfolio_rebalancing import compute_rebalance_plan

report = compute_rebalance_plan(
    month=2,
    year=2026,
    target_cash_pct=10.0,    # default
    target_bonds_pct=10.0,   # default
    target_stocks_pct=80.0,  # default
    drift_threshold_pct=5.0, # default
)
```

**Returns:** [`RebalanceReport`](#rebalancereport) dataclass

**Raises:** `ValueError` if target weights do not sum to 100.

---

### `build_rebalance_display_df(report)`

```python
from portfolio_rebalancing import build_rebalance_display_df

df = build_rebalance_display_df(report)
# Columns: Asset Class | Current Value | Current % | Target % | Drift % | Delta $ | Status
```

---

### `build_actions_display_df(report)`

```python
from portfolio_rebalancing import build_actions_display_df

df = build_actions_display_df(report)
# Columns: Priority | Action | Asset Class | Symbol | Account | Amount | Tax Impact | Rationale
```

---

### `build_holdings_by_class_df(report)`

```python
from portfolio_rebalancing import build_holdings_by_class_df

df = build_holdings_by_class_df(report)
# Columns: Account | Account Type | Symbol | Name | Sector | Asset Class |
#          Qty | Current Price | Current Value | Cost Basis | Unrealized G/L
```

---

## Data Classes

### `RebalanceReport`

| Field | Type | Description |
|---|---|---|
| `total_portfolio_value` | float | Total market value of all holdings |
| `asset_summary` | list[AssetClassSummary] | Per-class allocation summary |
| `holdings` | list[HoldingDetail] | All holdings with classification |
| `actions` | list[RebalanceAction] | Prioritised action list |
| `drift_triggered` | bool | True if any class exceeds drift threshold |
| `drift_threshold_pct` | float | Configured threshold |
| `target_weights` | dict | {"Cash": 10, "Bonds": 10, "Stocks": 80} |
| `brokerage_cash_pct` | float | Current cash % of brokerage account (0–1) |
| `brokerage_cash_ok` | bool | True if brokerage cash ≥ 10% |
| `location_issues` | list[str] | Plain-English location warnings |

### `AssetClassSummary`

| Field | Type | Description |
|---|---|---|
| `asset_class` | str | "Cash", "Bonds", or "Stocks" |
| `current_value` | float | Total market value in this class |
| `current_pct` | float | Current allocation % (0–100) |
| `target_pct` | float | Target allocation % (0–100) |
| `drift_pct` | float | current_pct − target_pct (signed) |
| `is_drifted` | bool | abs(drift_pct) ≥ threshold |
| `delta_value` | float | Dollar amount to buy (+) or sell (−) |

### `RebalanceAction`

| Field | Type | Description |
|---|---|---|
| `priority` | int | 1 = highest priority |
| `action` | str | "Buy", "Sell / Reallocate", "Sell (Brokerage)", "Redirect Contributions", "Buy MF:CASH" |
| `asset_class` | str | "Cash", "Bonds", or "Stocks" |
| `symbol` | str | Ticker or suggested ticker |
| `account_name` | str | Account name |
| `account_type` | str | "Traditional", "Roth", "Brokerage", etc. |
| `amount` | float | Dollar amount of the trade |
| `rationale` | str | Plain-English explanation |
| `tax_impact` | str | "None (tax-deferred/free account)", "Taxable event — check LTCG rate", "Tax-loss harvest opportunity" |
| `location_note` | str | Account-location guidance |

---

## Examples

### Example 1 — Check if rebalancing is needed

```python
from portfolio_rebalancing import compute_rebalance_plan, build_rebalance_display_df

report = compute_rebalance_plan(month=2, year=2026)

if report.drift_triggered:
    print("⚠️ Rebalancing required!")
    df = build_rebalance_display_df(report)
    print(df[["Asset Class", "Current %", "Target %", "Drift %", "Status"]])
else:
    print("✅ Portfolio is balanced.")
```

### Example 2 — Print the action plan

```python
from portfolio_rebalancing import compute_rebalance_plan, build_actions_display_df

report = compute_rebalance_plan(month=2, year=2026)
actions = build_actions_display_df(report)

for _, row in actions.iterrows():
    print(f"#{row['Priority']} {row['Action']} [{row['Asset Class']}] "
          f"{row['Symbol']} — ${row['Amount']:,.0f} — {row['Tax Impact']}")
```

### Example 3 — Custom target allocation (conservative)

```python
report = compute_rebalance_plan(
    month=2, year=2026,
    target_cash_pct=15.0,
    target_bonds_pct=25.0,
    target_stocks_pct=60.0,
    drift_threshold_pct=3.0,  # tighter tolerance
)
```

### Example 4 — Check account-location issues

```python
report = compute_rebalance_plan(month=2, year=2026)

for issue in report.location_issues:
    print(issue)
```

---

## Troubleshooting

### "Target weights must sum to 100"
The three target percentages (Cash + Bonds + Stocks) must equal exactly 100.
The UI shows an error banner if they don't — adjust the inputs until they sum to 100.

### "No rebalancing actions required" but drift is shown
Actions are only generated when `drift_triggered` is True **or** the brokerage cash
cushion is below 10% **or** there are account-location issues. If the portfolio is
within tolerance and the cash cushion is adequate, no actions are needed.

### Live prices not loading
The module uses `_fetch_current_prices()` from [`load_data.py`](load_data.py) to fetch
live prices via Yahoo Finance. If prices cannot be fetched (network issue, market closed,
delisted symbol), the purchase price is used as a fallback. A warning is logged.

`MF:CASH` always uses a price of $1.00 (no lookup needed).

### Holdings classified incorrectly
Classification is based on the `sector` field in `portfolio_data_truth.csv`. If a
holding is misclassified, update its sector to include the appropriate keyword:
- For bonds: add "Bond", "Fixed Income", "Treasury", or "Municipal" to the sector
- For cash: add "Cash" or "Money Market" to the sector
- For stocks: use any other sector value (e.g., "Technology", "Healthcare")

---

## See Also

- [`tax_harvesting.py`](tax_harvesting.py) — Tax loss/gain harvesting analysis
- [`portfolio.py`](portfolio.py) — Portfolio display and price fetching
- [`load_data.py`](load_data.py) — Data loading and price fetching utilities
- [`../implementation/IMPLEMENTATION_SUMMARY.md`](../implementation/IMPLEMENTATION_SUMMARY.md) — Full implementation history
- [`README.md`](README.md) — Main application documentation

---

*Made with Bob — 2026-02-28*