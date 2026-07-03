# Portfolio Hub + Direct Indexing Consolidation Plan

## Overview

The application currently has two overlapping pages:

- **`pages/4_portfolio_hub.py`** — 9-tab whole-portfolio manager (all account types)
- **`pages/Direct_Indexing.py`** — 7-tab direct indexing dashboard (taxable accounts only)

The goal is to merge these into a single **Portfolio Hub** where Direct Indexing is not a
separate tool but rather the mechanism used to **build, hold, and tax-harvest taxable
brokerage positions** — integrated naturally alongside the whole-portfolio views for
Traditional, Roth, and Savings accounts.

### Core Design Principle

- **Portfolio Hub owns ALL accounts** — Holdings, Performance, Rebalancing, and Connections
  continue to operate across Brokerage, Traditional, Roth, and Savings.
- **Direct Indexing capabilities live inside Portfolio Hub** — the Harvest workflow,
  Execution Queue, Tax Records, and Analytics that previously lived in `Direct_Indexing.py`
  are absorbed into dedicated tabs within Portfolio Hub.
- **`pages/Direct_Indexing.py` is retired** — it is replaced by the expanded Portfolio Hub.
- **Tax harvesting is consolidated** — the legacy `tax_harvesting.py` analysis
  (used by `portfolio_optimization.py`) and the `direct_index_harvester.py` scanner are
  unified under a single Harvest tab that is the one place to identify, review, and
  execute loss-harvesting trades.
- **Tax Records replaces three tabs** — Transactions, Cost Basis, and Capital Gains are
  merged into one "Tax Records" tab to eliminate redundancy.

### Final Tab Structure (Portfolio Hub — 9 tabs, same count, different content)

| # | Tab | Replaces / Source |
|---|-----|--------------------|
| 1 | 📊 Overview | Portfolio Hub: Overview (unchanged) |
| 2 | 📝 Holdings | Portfolio Hub: Holdings (unchanged) |
| 3 | 📈 Performance | Portfolio Hub: Performance (add DI after-tax metrics) |
| 4 | ⚖️ Rebalancing | Portfolio Hub: Optimization → Rebalancing sub-tab (promoted) |
| 5 | 🌾 Tax Harvesting | Merged: Optimization→Tax Harvesting + DI Harvest + DI Execution Queue |
| 6 | 💰 Tax Records | Merged: Transactions + Cost Basis + Capital Gains + DI Tax Savings |
| 7 | 📊 Analytics | Merged: DI Analytics + Portfolio Factor Analysis (DAF/Withdrawals move here) |
| 8 | 🔗 Connections | Portfolio Hub: Connections (add Schwab DI sync) |
| 9 | ⚙️ Setup & Config | Merged: DI Setup Wizard + DI Config YAML editor |

---

## Sub-Tasks

---

### Sub-Task 1 — Promote Rebalancing to its Own Tab

**Status:** `[x] done`

**Intent**

The Rebalancing sub-tab inside `portfolio_optimization.py` is a full-featured tool
(drift analysis, bucket strategy integration, rebalancing action plan) that is buried
one level too deep. Promoting it to a top-level tab makes room for the Harvest tab
to take over the Optimization slot without losing rebalancing functionality. This is
purely a structural lift — no logic changes.

**Expected Outcomes**

- Portfolio Hub has a dedicated `⚖️ Rebalancing` tab at position 4.
- The rebalancing content (`compute_rebalance_plan`, `build_rebalance_display_df`,
  `build_actions_display_df`) renders identically to today.
- `portfolio_optimization.py` keeps the Rebalancing rendering function but it is now
  called directly from the top-level tab, not from inside a sub-tab switcher.

**Todo List**

1. Extract the rebalancing rendering block from `components/portfolio_optimization.py`
   into a new exportable function `render_rebalancing_tab()` in that same file.
2. In `pages/4_portfolio_hub.py`, replace `optimization_tab` with two new tabs:
   `rebalancing_tab` and `harvest_tab` (keeping the remaining 7 tabs unchanged for now).
3. Wire `rebalancing_tab` to call `render_rebalancing_tab()`.
4. Leave `harvest_tab` as a placeholder stub (`st.info("Coming in Sub-Task 2")`).
5. Remove the `⚖️ Rebalancing` sub-tab from inside `portfolio_optimization.py`.

**Relevant Context**

- `pages/4_portfolio_hub.py` line 134 — tab tuple definition
- `components/portfolio_optimization.py` lines 58-65 — sub-tab definitions
- `components/portfolio_optimization.py` lines 68-220 — rebalancing rendering block
- `portfolio_rebalancing.py` — `compute_rebalance_plan()`, `build_rebalance_display_df()`

---

### Sub-Task 2 — Build the Unified Tax Harvesting Tab

**Status:** `[x] done`

**Intent**

Create a single `🌾 Tax Harvesting` tab in Portfolio Hub that is the **one place** to
scan for opportunities, review them, queue them for execution, and manage the trade
queue. It replaces:

- `portfolio_optimization.py` → `🌾 Tax Harvesting` sub-tab (uses `tax_harvesting.py`)
- `pages/Direct_Indexing.py` → `🎯 Harvest` tab (`direct_index_harvester.py`)
- `pages/Direct_Indexing.py` → `📋 Execution Queue` tab (`harvest_approval.py`)

**Data Source Architecture (SELL side vs BUY side)**

The two existing scanners read from different data sources and serve different roles
that must both be preserved:

| Scanner | Data Source | Role |
|---------|-------------|------|
| `tax_harvesting.py :: build_harvesting_analysis()` | `portfolio_data_truth.csv` (via `getPortfolioData()`) | **SELL scanner** — scans actual Brokerage holdings for loss/gain opportunities |
| `direct_index_harvester.py :: scan_harvest_opportunities()` | `rsp_holdings.db :: direct_index_positions` | **DI SELL scanner** — scans direct-index tax lots already in the DI portfolio |
| `replacement_selector.py :: find_replacement_stock()` | `rsp_holdings.db :: rsp_constituents / rsp_holdings` | **BUY universe** — RSP constituent pool for wash-sale-safe sector-matched replacements |

The unified Harvest tab runs **both scanners** and merges results:

1. **Primary scan** — `build_harvesting_analysis()` reads `portfolio_data_truth.csv`,
   filters to Brokerage accounts, identifies all loss/gain positions. For each
   opportunity, it calls `find_replacement_stock()` (backed by `rsp_holdings.db`) to
   surface RSP-constituent buy candidates. This is the scan for positions the user
   already holds outside the direct index.

2. **DI scan** — `scan_harvest_opportunities()` reads `rsp_holdings.db :: direct_index_positions`,
   identifying losses in positions already tracked as direct-index tax lots. Results
   are deduplicated against the primary scan (same symbol should not appear twice).

This architecture is correct because `portfolio_data_truth.csv` is the source of truth
for what you *own*, and `rsp_holdings.db` is the universe of what you can *buy* as a
wash-sale-safe replacement from the RSP S&P 500 constituent pool.

The `build_harvesting_analysis()` replacement lookup currently uses a static
`WASH_SALE_REPLACEMENTS` dict in `tax_harvesting.py`. This should be **enhanced** to
also call `find_replacement_stock()` from `replacement_selector.py` so that RSP
constituents (from `rsp_holdings.db`) are surfaced as buy candidates alongside the
static list.

The tab should have **two internal sub-tabs**:

- **🔍 Opportunities** — merged scan results, filters, review modal, approve to queue
- **📋 Execution Queue** — pending/approved/executed trades, approve/reject/confirm

**Expected Outcomes**

- `harvest_tab` in Portfolio Hub renders both Opportunities and Execution Queue.
- The tax settings (AGI, LTCG rate, marginal rate) from `Direct_Indexing.py` are
  moved to the Harvest tab's own `⚙️ Settings` expander (no sidebar dependency).
- The account filter for harvesting is scoped to Brokerage accounts only — matching
  `tax_harvesting.py`'s `BROKERAGE_ACCOUNT_TYPE` constant.
- Opportunities show a merged, deduplicated list from both scanners. Each opportunity
  card identifies its source ("Portfolio Holdings" vs "Direct Index Portfolio").
- Buy candidates for each opportunity come from `find_replacement_stock()` querying
  the RSP constituent universe in `rsp_holdings.db`.
- All existing `harvest_approval.py` approval/reject/confirm logic is preserved intact.

**Todo List**

1. Create `components/portfolio_harvest_tab.py` with a single entry point:
   `render_harvest_tab(portdf, curr_month, curr_year) -> None`.
2. Inside `render_harvest_tab`, create two sub-tabs: Opportunities and Execution Queue.
3. **Opportunities sub-tab:**
   a. Add a `⚙️ Harvest Settings` expander: AGI input, LTCG rate select, marginal rate
      select, loss threshold %, min loss $, account filter (Brokerage accounts only,
      sourced from distinct `account_name` values where `account_type == "Brokerage"`
      in `portdf`).
   b. Run the **primary scan**: call `build_harvesting_analysis(curr_month, curr_year)`
      from `tax_harvesting.py`, then `classify_harvest_opportunities()` with user-provided
      AGI and thresholds.
   c. For each opportunity from the primary scan, call `find_replacement_stock()` from
      `replacement_selector.py` to get RSP-constituent buy candidates (in addition to
      the static `WASH_SALE_REPLACEMENTS` already in the result).
   d. Run the **DI scan**: call `scan_harvest_opportunities()` from
      `direct_index_harvester.py`. Deduplicate against primary scan results by symbol.
   e. Merge and sort all opportunities by estimated tax savings descending.
   f. Render each opportunity as an expandable card showing: symbol, loss amount,
      loss %, holding period (ST/LT), estimated tax savings, and a ranked list of
      RSP buy candidates with sector and wash-sale status. Include a
      "Add to Queue" button that calls `harvest_approval.py :: create_pending_trade()`.
4. **Execution Queue sub-tab:**
   - Port the entire Execution Queue rendering block from
     `pages/Direct_Indexing.py` lines 523-731 into this component.
   - Keep all `harvest_approval.py` calls (`get_pending_trades`, `approve_pending_trade`,
     `reject_pending_trade`, `confirm_trade_executed`, `revert_confirmation`,
     `cancel_pending_trade`, `get_approval_summary`) unchanged.
5. Wire `harvest_tab` in `pages/4_portfolio_hub.py` to call `render_harvest_tab()`.
6. Remove the `🌾 Tax Harvesting` sub-tab from `components/portfolio_optimization.py`
   (keep DAF Bundling and Withdrawals in place for Sub-Task 4).

**Relevant Context**

- `tax_harvesting.py` — `build_harvesting_analysis()` (L302), `classify_harvest_opportunities()`
  (L684), `BROKERAGE_ACCOUNT_TYPE` constant (L73), `WASH_SALE_REPLACEMENTS` dict (L86)
- `portfolio.py` — `getPortfolioData()` (L244) — CSV read path used by tax_harvesting.py
- `components/replacement_selector.py` — `find_replacement_stock()` — RSP constituent BUY lookup
- `components/direct_index_harvester.py` — `scan_harvest_opportunities()` — DI tax lot SELL scan
- `components/harvest_approval.py` — `PendingTrade`, `ApprovalStatus`, `create_pending_trade()`,
  approval functions
- `components/harvest_review_modal.py` — `render_harvest_review()`
- `pages/Direct_Indexing.py` lines 328-731 — Harvest + Execution Queue blocks to port
- `components/portfolio_optimization.py` lines 352-560 — legacy harvest sub-tab to remove

---

### Sub-Task 3 — Merge Tax Records Tab

**Status:** `[x] done`

**Intent**

The current Portfolio Hub has three separate tabs — Transactions, Cost Basis, and Capital
Gains — that all draw from `transaction_history_ui.py` and `cost_basis_tracker.py`. The
Direct Indexing page has a `💰 Tax Savings` tab that shows YTD harvest records. These
four things answer the same question: *"What happened with my taxes this year?"* Merging
them into one `💰 Tax Records` tab with internal sub-tabs reduces navigation friction and
makes the harvest savings appear alongside realized gains from all accounts.

**Expected Outcomes**

- A single `💰 Tax Records` tab replaces the three current tabs (Transactions, Cost Basis,
  Capital Gains) and absorbs the DI Tax Savings content.
- Four internal sub-tabs: **Transactions | Cost Basis | Capital Gains | Harvest Savings**.
- All existing functionality of each component is preserved; no logic is removed.
- The `Harvest Savings` sub-tab displays the same content as the current DI Tax Savings tab
  (`get_ytd_summary`, `get_performance_metrics`, `get_harvest_history` from
  `tax_savings_tracker.py`).

**Todo List**

1. Create `components/portfolio_tax_records_tab.py` with entry point:
   `render_tax_records_tab(transaction_storage, user_id, curr_year) -> None`.
2. Inside, define four sub-tabs: Transactions, Cost Basis, Capital Gains, Harvest Savings.
3. Wire Transactions, Cost Basis, and Capital Gains sub-tabs to call the existing functions
   from `transaction_history_ui.py` (`render_transaction_history_tab`,
   `render_cost_basis_tab`, `render_capital_gains_tab`) unchanged.
4. Wire Harvest Savings sub-tab to call `get_ytd_summary`, `get_performance_metrics`,
   and `get_harvest_history` from `tax_savings_tracker.py`, using the same layout as the
   current DI Tax Savings tab (4 metric cards, term breakdown, account detail, history table).
5. In `pages/4_portfolio_hub.py`:
   - Replace the three tabs `transactions_tab`, `cost_basis_tab`, `cap_gains_tab` with a
     single `tax_records_tab`.
   - Wire it to call `render_tax_records_tab()`.
6. Update the tab tuple in `pages/4_portfolio_hub.py` line 134 to reflect the new 9-tab
   structure.

**Relevant Context**

- `components/transaction_history_ui.py` — `render_transaction_history_tab()` (L248),
  `render_cost_basis_tab()` (L578), `render_capital_gains_tab()` (L751)
- `components/tax_savings_tracker.py` — `get_ytd_summary()`, `get_performance_metrics()`,
  `get_harvest_history()`
- `pages/4_portfolio_hub.py` lines 350-487 — current three-tab rendering blocks
- `pages/Direct_Indexing.py` lines 732-835 — DI Tax Savings tab to port

---

### Sub-Task 4 — Merge Analytics Tab (+ DAF/Withdrawals)

**Status:** `[x] done`

**Intent**

The Portfolio Hub has `🎯 Factor Analysis` and the Direct Indexing page has `📊 Analytics`.
Both show performance data but from different angles — Factor Analysis examines value/growth/
momentum factor tilts across all accounts, while DI Analytics shows return vs RSP benchmark,
sector drift, and harvest efficiency for the taxable direct-index portfolio. Combining them
into a single `📊 Analytics` tab with sub-tabs gives users a unified analytics center.

The DAF Bundling and Withdrawals sub-tabs (currently inside `portfolio_optimization.py`)
also belong here — they are planning/analytics tools, not execution tools, so they fit
naturally alongside the performance analytics.

**Expected Outcomes**

- A single `📊 Analytics` tab replaces both `🎯 Factor Analysis` and the old `⚖️ Optimization` slot.
- Four internal sub-tabs: **Factor Analysis | Direct Index | DAF Bundling | Withdrawals**.
- Factor Analysis renders identically to today (`render_factor_analysis_tab()`).
- Direct Index sub-tab renders identically to the current DI Analytics tab
  (`compute_performance`, `get_sector_drift_table`, `get_harvest_efficiency_series`).
- DAF Bundling and Withdrawals render identically to their current sub-tabs in
  `portfolio_optimization.py`.

**Todo List**

1. Create `components/portfolio_analytics_tab.py` with entry point:
   `render_analytics_tab(portdf, networth, curr_month, curr_year) -> None`.
2. Define four sub-tabs: Factor Analysis, Direct Index, DAF Bundling, Withdrawals.
3. Wire Factor Analysis to call `render_factor_analysis_tab()` from
   `components/portfolio_factor_analysis.py` (unchanged).
4. Wire Direct Index to port the analytics rendering block from
   `pages/Direct_Indexing.py` lines 836-1290 (`compute_performance`,
   `get_sector_drift_table`, `get_harvest_efficiency_series`, all chart code).
5. Wire DAF Bundling and Withdrawals to call the existing rendering functions from
   `components/portfolio_optimization.py` (extract them into exportable functions
   `render_daf_tab()` and `render_withdrawals_tab()` in that file first).
6. In `pages/4_portfolio_hub.py`, replace `factor_tab` with `analytics_tab` and wire
   to `render_analytics_tab()`.
7. Remove the DAF Bundling and Withdrawals sub-tabs from `portfolio_optimization.py`
   now that they live in the Analytics tab.

**Relevant Context**

- `components/portfolio_factor_analysis.py` — `render_factor_analysis_tab()`
- `components/direct_index_analytics.py` — `compute_performance()`,
  `get_sector_drift_table()`, `get_harvest_efficiency_series()`, `PortfolioPerformance`
- `components/portfolio_optimization.py` lines 560-end — DAF Bundling + Withdrawals
- `pages/Direct_Indexing.py` lines 836-1290 — DI Analytics tab block
- `tax_harvesting.py` — `identify_daf_candidates()`, `analyze_daf_bundling()`

---

### Sub-Task 5 — Expand Connections Tab with Schwab DI Sync

**Status:** `[x] done`

**Intent**

The current Connections tab handles SnapTrade OAuth for brokerage data sync. The Direct
Indexing page has a Schwab sync expander inside its Portfolio tab (lines 247-289) that
pulls positions into `rsp_holdings.db`. Once `Direct_Indexing.py` is retired, that sync
entry point needs a permanent home. The Connections tab is the right place — it is already
the page for brokerage integration.

**Expected Outcomes**

- The Connections tab gains a new `🔄 Schwab Direct Index Sync` section beneath the
  existing SnapTrade content.
- Sync logic (`create_schwab_di_connector()`, `sync_positions_to_db()`,
  `update_db_prices()`) is moved there unchanged.
- The Portfolio tab in Portfolio Hub (Holdings) no longer needs a sync expander.

**Todo List**

1. In `components/portfolio_connections.py`, add a new section to `render_connections_tab()`
   below the SnapTrade block: `🔄 Schwab Direct Index Sync`.
2. Port the Schwab sync expander block from `pages/Direct_Indexing.py` lines 247-289
   into this section (account name input, overwrite checkbox, update prices checkbox,
   Sync button, result display).
3. Verify that the OAuth flow note (*"Complete the OAuth flow in Portfolio Hub → Brokerage
   Connections"*) is now accurate — it points to itself, so update the note to say
   *"Authenticate Schwab above before syncing"*.
4. No changes needed to `components/schwab_direct_indexing.py` — it is called as-is.

**Relevant Context**

- `components/portfolio_connections.py` — `render_connections_tab()` (L41)
- `pages/Direct_Indexing.py` lines 247-289 — Schwab sync expander
- `components/schwab_direct_indexing.py` — `create_schwab_di_connector()`,
  `sync_positions_to_db()`, `update_db_prices()`

---

### Sub-Task 6 — Add Setup & Config Tab

**Status:** `[x] done`

**Intent**

The Direct Indexing setup wizard (`initial_setup_wizard.py`) and YAML config editor
(currently tab 7 in `Direct_Indexing.py`) need a home in Portfolio Hub. A new
`⚙️ Setup & Config` tab at the end of the tab bar provides first-time setup for the
direct-indexing portfolio alongside the threshold/replacement/wash-sale configuration
that governs the Harvest tab.

**Expected Outcomes**

- Portfolio Hub gains a `⚙️ Setup & Config` tab with two sub-tabs: **Setup Wizard** and
  **Harvest Config**.
- Setup Wizard renders identically to the current DI Setup tab
  (`render_setup_wizard()` from `initial_setup_wizard.py`).
- Harvest Config renders identically to the current DI Config tab (all YAML editor
  sections: thresholds, replacement, wash sale, weighting, data, initial setup defaults).

**Todo List**

1. Create `components/portfolio_setup_config_tab.py` with entry point:
   `render_setup_config_tab() -> None`.
2. Define two sub-tabs: Setup Wizard and Harvest Config.
3. Wire Setup Wizard to call `render_setup_wizard()` from
   `components/initial_setup_wizard.py` unchanged.
4. Port the Config tab rendering block from `pages/Direct_Indexing.py` lines 839-1080
   into the Harvest Config sub-tab (all YAML read/write/save logic unchanged).
5. In `pages/4_portfolio_hub.py`, add `setup_config_tab` to the tab tuple and wire to
   `render_setup_config_tab()`.

**Relevant Context**

- `components/initial_setup_wizard.py` — `render_setup_wizard()` (L484)
- `pages/Direct_Indexing.py` lines 839-1080 — Config tab block
- `config/direct_indexing_config.yaml` — YAML config file read/written by the config tab

---

### Sub-Task 7 — Retire Direct_Indexing.py and Final Cleanup

**Status:** `[x] done`

**Intent**

With all functionality absorbed into Portfolio Hub, `pages/Direct_Indexing.py` should be
retired and any leftover loose ends cleaned up: duplicate import aliases, dead
`try/except ImportError` stubs in the Portfolio Hub page, and the tab tuple finalized.

**Expected Outcomes**

- `pages/Direct_Indexing.py` is renamed to `pages/Direct_Indexing.py.disabled` (same
  pattern used for `7_flow_of_funds.py.disabled`) — preserving it without it appearing
  in the Streamlit sidebar.
- `pages/4_portfolio_hub.py` has a clean, final 9-tab structure with no placeholder stubs.
- The `try/except ImportError` guards in `pages/4_portfolio_hub.py` for components that
  now always exist are simplified to direct imports.
- The Portfolio Hub sidebar (currently just the Streamlit navbar) gains an account filter
  widget scoped to Brokerage accounts, used by the Harvest and Tax Records tabs.

**Todo List**

1. Rename `pages/Direct_Indexing.py` → `pages/Direct_Indexing.py.disabled`.
2. In `pages/4_portfolio_hub.py`, replace all `try/except ImportError` import blocks
   with direct imports for components confirmed to exist:
   `portfolio_harvest_tab`, `portfolio_tax_records_tab`, `portfolio_analytics_tab`,
   `portfolio_setup_config_tab`.
3. Add a sidebar account filter (`st.selectbox` scoped to Brokerage accounts) that is
   passed into `render_harvest_tab()` and `render_tax_records_tab()`.
4. Update the page footer caption to remove the "Phase 1/2/3" placeholder text.
5. Verify all 9 tabs render without errors by reviewing each import chain.

**Relevant Context**

- `pages/4_portfolio_hub.py` lines 24-70 — current `try/except ImportError` blocks
- `pages/4_portfolio_hub.py` line 134 — tab tuple to finalize
- `pages/Direct_Indexing.py` — file to disable
- Pattern reference: `pages/7_flow_of_funds.py.disabled`

---

## Component Map: Before → After

```
BEFORE                                  AFTER
──────────────────────────────────────────────────────────────────
pages/4_portfolio_hub.py (9 tabs)       pages/4_portfolio_hub.py (9 tabs)
  Tab 1: Overview                  →      Tab 1: Overview (unchanged)
  Tab 2: Holdings                  →      Tab 2: Holdings (unchanged)
  Tab 3: Performance               →      Tab 3: Performance (+ DI after-tax metric)
  Tab 4: Optimization              →      Tab 4: Rebalancing (promoted, Sub-Task 1)
    sub: Rebalancing                        (no sub-tabs)
    sub: Tax Harvesting [RETIRED]
    sub: DAF Bundling              →      Tab 7: Analytics > DAF sub-tab
    sub: Withdrawals               →      Tab 7: Analytics > Withdrawals sub-tab
  Tab 5: Factor Analysis           →      Tab 7: Analytics > Factor sub-tab (Sub-Task 4)
  Tab 6: Connections               →      Tab 6: Connections + Schwab DI (Sub-Task 5)
  Tab 7: Transactions              →      Tab 6 [merged into Tax Records] (Sub-Task 3)
  Tab 8: Cost Basis                →      Tab 6 [merged into Tax Records] (Sub-Task 3)
  Tab 9: Capital Gains             →      Tab 6 [merged into Tax Records] (Sub-Task 3)

pages/Direct_Indexing.py (7 tabs)       [DISABLED → .disabled]
  Tab 1: Setup                     →      Tab 9: Setup & Config > Setup Wizard (Sub-Task 6)
  Tab 2: Portfolio                 →      [absorbed into Holdings + Connections]
  Tab 3: Harvest                   →      Tab 5: Tax Harvesting > Opportunities (Sub-Task 2)
  Tab 4: Execution Queue           →      Tab 5: Tax Harvesting > Queue (Sub-Task 2)
  Tab 5: Tax Savings               →      Tab 6: Tax Records > Harvest Savings (Sub-Task 3)
  Tab 6: Analytics                 →      Tab 7: Analytics > Direct Index sub-tab (Sub-Task 4)
  Tab 7: Config                    →      Tab 9: Setup & Config > Harvest Config (Sub-Task 6)
```

## New Component Files Created

| New File | Entry Point | Sub-Task |
|---|---|---|
| `components/portfolio_harvest_tab.py` | `render_harvest_tab()` | 2 |
| `components/portfolio_tax_records_tab.py` | `render_tax_records_tab()` | 3 |
| `components/portfolio_analytics_tab.py` | `render_analytics_tab()` | 4 |
| `components/portfolio_setup_config_tab.py` | `render_setup_config_tab()` | 6 |

## Existing Files Modified (Summary)

| File | Change |
|---|---|
| `pages/4_portfolio_hub.py` | Tab structure, imports, sidebar filter |
| `components/portfolio_optimization.py` | Extract `render_rebalancing_tab()`, remove Tax Harvest / DAF / Withdrawals sub-tabs |
| `components/portfolio_connections.py` | Add Schwab DI sync section |
| `pages/Direct_Indexing.py` | Renamed to `.disabled` |

## Files Left Unchanged

All backend logic files remain untouched — no business logic is rewritten, only
UI assembly changes:

- `tax_harvesting.py`
- `components/direct_index_harvester.py`
- `components/harvest_approval.py`
- `components/harvest_executor.py`
- `components/harvest_review_modal.py`
- `components/tax_savings_tracker.py`
- `components/cost_basis_tracker.py`
- `components/direct_index_analytics.py`
- `components/initial_setup_wizard.py`
- `components/initial_portfolio_generator.py`
- `components/replacement_selector.py`
- `components/sector_classifier.py`
- `components/transaction_history_ui.py`
- `components/portfolio_factor_analysis.py`
- `components/portfolio_performance.py`
- `components/portfolio_holdings_editor.py`
- `components/portfolio_overview.py`
- `components/schwab_direct_indexing.py`
- `portfolio_rebalancing.py`
