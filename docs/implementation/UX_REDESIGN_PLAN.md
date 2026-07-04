# Retirement Planner — UX Redesign Plan

## Executive Summary

The current application has **6 tabs** with significant duplication of account visualizations, redundant data entry surfaces, and a legacy "Retirement planner" tab that overlaps with the newer Withdrawal Strategy tab. This plan consolidates the experience into **4 focused tabs**, adds a Net Worth Statement widget, and eliminates all duplicate chart/table code.

---

## Current State Analysis

### Tab Inventory (`planning_app.py` line 151)

| Variable | Tab Label | Purpose | Issues |
|---|---|---|---|
| `tab1` | **Dashboard** | Net worth metrics, 3 charts (histogram, stacked bar, pie), 2 treemaps | Good anchor — keep as primary landing |
| `tab3` | **Portfolio Planner** | Portfolio treemap, details table, Update Securities data entry | "Update Securities" is a data-management task, not a planning view |
| `tab_strategy` | **Strategy** | Placeholder only — `st.info()` stub | Empty — should be removed or merged |
| `tab_accum` | **Accumulation Strategy** | 3 sub-tabs: Annual Strategy (stub), Account Balances, Visualizations | Mirrors Withdrawal Strategy exactly; both show same stacked-area + income charts |
| `tab4` | **Retirement planner** | Legacy hand-coded: 5 metrics, Inflow/Outflow table, Portfolio Value table | Superseded by Withdrawal Strategy; metrics are stale/hardcoded |
| `tab5` | **Withdrawal Strategy** | Full strategy: parameters, Annual Strategy table, Account Balances, Visualizations | Most complete tab — should be the canonical strategy view |

### Duplication Inventory

1. **Stacked-area balance chart** — identical `go.Figure()` + 4 `add_trace(go.Scatter(..., stackgroup='one'))` blocks appear in **both** `tab_accum` (lines 788–835) and `tab5` (lines 1189–1236).
2. **Income sources bar chart** — identical `go.Figure()` + `go.Bar` blocks for Wages / Social Security / Portfolio Withdrawal appear in **both** `tab_accum` (lines 840–876) and `tab5` (lines 1242–1278).
3. **Account balance column config** — `balance_column_config` dict defined identically in `tab_accum` (lines 768–776) and `tab5` (lines 1173–1181).
4. **`format_currency()` function** — defined inline inside `tab5` at line 1107; also used in `tab_accum` at line 766. Should be a module-level helper.
5. **Portfolio treemap** — appears in Dashboard `tab1` (line 373) AND Portfolio Planner `tab3` (line 412) with only minor path depth difference (`['Tax Type','Sector']` vs `['Tax Type','Sector','Ticker']`).
6. **`build_portfolio_display()` call** — called at line 370 (inside tab1), line 382 (module level), and line 390 (inside tab3) — three separate calls for the same data.
7. **Net worth metrics** — Dashboard shows 5 `st.metric` cards (lines 166–207). Legacy Retirement Planner tab4 shows 5 `st.subheader` + `st.metric` blocks (lines 883–910) for the same data.
8. **`networth` variable shadowing** — `networth` is a DataFrame at line 154, then overwritten to a scalar at line 887 inside `tab4`, which would break any subsequent reference.

---

## Proposed New Structure — 4 Tabs

```
┌─────────────────────────────────────────────────────────────────┐
│  Retirement Planner                              [sidebar]       │
├──────────┬──────────────┬──────────────────┬────────────────────┤
│ Dashboard│  Portfolio   │    Strategy      │   Configuration    │
│  (tab1)  │  (tab2)      │    (tab3)        │   (pages/)         │
└──────────┴──────────────┴──────────────────┴────────────────────┘
```

### Tab 1 — Dashboard *(enhanced, replaces current tab1)*

**Goal:** Single-glance financial health snapshot.

**Sections (top to bottom):**

1. **Net Worth Statement widget** *(new)* — formal balance-sheet style table showing assets by account type with MoM change column. See design below.
2. **KPI metric cards** — existing 5 cards (Cash, Brokerage, Roth, Traditional, Total) — keep as-is, styled with `style_metric_cards`.
3. **Charts row** — existing 3 charts: Total Net Worth histogram, Net Worth by Account stacked bar, Asset Mix pie — keep as-is.
4. **Treemap row** — existing 2 treemaps: Account Mix Breakdown, Portfolio Mix — keep as-is.

**Remove from Dashboard:** Nothing removed — only the Net Worth Statement is added above the existing content.

---

### Tab 2 — Portfolio *(consolidates tab3 "Portfolio Planner")*

**Goal:** Full portfolio view + data management in one place.

**Sub-tabs:**

| Sub-tab | Content | Source |
|---|---|---|
| **Overview** | Treemap `['Tax Type','Sector','Ticker']` (drill-down) | tab3 → map_tab |
| **Holdings** | Styled dataframe with all columns | tab3 → details_tab |
| **Update Data** | Month/year selector, data editor, validate/save buttons | tab3 → update_tab |

**Changes:**
- Remove the shallow `['Tax Type','Sector']` treemap from Dashboard tab (keep only the deeper one here).
- Dashboard keeps the Portfolio Mix treemap as a summary widget only (no duplication of the full drill-down).
- `build_portfolio_display()` called **once** at the top of the tab, result passed to all sub-tabs.

---

### Tab 3 — Strategy *(consolidates tab_strategy + tab_accum + tab5 + tab4)*

**Goal:** Unified accumulation-through-withdrawal planning view.

**Phase toggle (Accumulation / Withdrawal):**

```
[ Accumulation ]  [ Withdrawal (Distribution) ]
```

A single `st.radio` or segmented button switches between the two phases. Both phases share the **same sub-tab structure** and the **same chart-rendering helper functions**.

**Shared sub-tabs (same for both phases):**

| Sub-tab | Content |
|---|---|
| **Parameters** | Strategy parameters metrics bar (from tab5 lines 999–1011) |
| **Annual Plan** | Year-by-year strategy table (from tab5 strategy_tab) |
| **Balances** | Account balances table (shared column config) |
| **Visualizations** | Stacked-area balance chart + income sources bar chart |

**Key consolidation — shared helper functions (new):**

```python
def render_balance_chart(balances_df: pd.DataFrame, title: str = "Projected Account Balances"):
    """Renders stacked-area chart for Cash/Taxable/Traditional/Roth balances."""
    ...

def render_income_chart(strategy_df: pd.DataFrame, title: str = "Income Sources by Year"):
    """Renders stacked bar chart for Wages/SS/Portfolio Withdrawal."""
    ...

def render_balance_table(balances_df: pd.DataFrame):
    """Renders formatted account balances dataframe with shared column config."""
    ...

def format_currency(val) -> str:
    """Module-level currency formatter — whole numbers without decimals."""
    ...
```

These four functions replace the ~200 lines of duplicated chart/table code.

**Accumulation phase** uses `build_accumulation_strategy_display()` (currently stubbed).  
**Withdrawal phase** uses `build_withdrawal_strategy_display()` (fully implemented in tab5).

---

### Tab 4 — Configuration *(existing `pages/configuration.py`)*

The existing multi-tab configuration page is already well-structured. Add a direct tab link in the main nav or keep it as a Streamlit page. No structural changes needed.

**Retire:** The legacy `tab4` ("Retirement planner") is **removed**. Its useful content migrates:
- The 5 KPI metrics → already exist in Dashboard tab1.
- Inflow/Outflow table → already exists in Withdrawal Strategy (tab5 strategy_tab).
- Portfolio Value table → already exists in Withdrawal Strategy (tab5 balances_tab).
- The hardcoded `$12,500` monthly income metric → remove (stale/misleading).

---

## Net Worth Statement Widget — Design

A formal balance-sheet style widget to be placed at the top of the Dashboard tab.

### Visual Design

```
┌─────────────────────────────────────────────────────────────────────┐
│  NET WORTH STATEMENT                              As of Feb 2026     │
├──────────────────────┬──────────────┬──────────────┬────────────────┤
│ Account              │ Current      │ Prior Month  │ Change         │
├──────────────────────┼──────────────┼──────────────┼────────────────┤
│ 🟡 Cash              │ $XX,XXX      │ $XX,XXX      │ ▲ $X,XXX       │
│ 🩷 Brokerage         │ $XXX,XXX     │ $XXX,XXX     │ ▼ ($X,XXX)     │
│ 🟢 Traditional IRA   │ $XXX,XXX     │ $XXX,XXX     │ ▲ $X,XXX       │
│ 🟣 Roth IRA          │ $XXX,XXX     │ $XXX,XXX     │ ▲ $X,XXX       │
├──────────────────────┼──────────────┼──────────────┼────────────────┤
│ TOTAL NET WORTH      │ $X,XXX,XXX   │ $X,XXX,XXX   │ ▲ $XX,XXX      │
└──────────────────────┴──────────────┴──────────────┴────────────────┘
```

### Implementation

```python
def render_net_worth_statement(networth: pd.DataFrame):
    """
    Renders a formal net worth statement table using the historical networth DataFrame.
    
    Args:
        networth: DataFrame with columns [cash, taxable, tax_deferred, tax_free, total]
                  and DatetimeIndex. Must have at least 2 rows.
    """
    current = networth.iloc[-1]
    prior   = networth.iloc[-2]
    
    rows = [
        ("🟡 Cash",           "cash",         current.cash,         prior.cash),
        ("🩷 Brokerage",      "taxable",      current.taxable,      prior.taxable),
        ("🟢 Traditional",    "tax_deferred", current.tax_deferred, prior.tax_deferred),
        ("🟣 Roth",           "tax_free",     current.tax_free,     prior.tax_free),
        ("**TOTAL**",         "total",        current.total,        prior.total),
    ]
    
    data = []
    for label, _, curr_val, prev_val in rows:
        change = curr_val - prev_val
        change_str = f"▲ ${change:,.0f}" if change >= 0 else f"▼ (${abs(change):,.0f})"
        data.append({
            "Account":      label,
            "Current":      f"${curr_val:,.0f}",
            "Prior Month":  f"${prev_val:,.0f}",
            "Change":       change_str,
            "_change_val":  change,   # hidden, used for color styling
        })
    
    df = pd.DataFrame(data)
    
    # Style: bold total row, green/red change column
    def style_change(val):
        return "color: #21c354" if "▲" in str(val) else "color: #ff4b4b"
    
    styled = (
        df.drop(columns=["_change_val"])
          .style
          .map(style_change, subset=["Change"])
          .set_table_styles([
              {"selector": "th", "props": [("text-align", "center"), ("background", "#1a1a2e"), ("color", "white")]},
              {"selector": "td", "props": [("text-align", "right")]},
              {"selector": "td:first-child", "props": [("text-align", "left"), ("font-weight", "500")]},
              {"selector": "tr:last-child td", "props": [("font-weight", "700"), ("background", "#f8f9fa"), ("font-size", "15px")]},
          ])
    )
    
    as_of = networth.index[-1].strftime("%B %Y")
    st.markdown(f'<h4 style="text-align:left;">📊 Net Worth Statement — {as_of}</h4>', unsafe_allow_html=True)
    st.dataframe(styled, hide_index=True, width='stretch')
```

---

## Duplication Elimination — Refactoring Map

| Current Code | Lines | Action | New Location |
|---|---|---|---|
| `format_currency()` inline in tab5 | 1107–1114 | Extract to module level | Line ~60, after imports |
| Stacked-area balance chart (tab_accum) | 788–835 | Delete | Replaced by `render_balance_chart()` |
| Stacked-area balance chart (tab5) | 1189–1236 | Replace with helper call | `render_balance_chart(balances_df)` |
| Income sources bar chart (tab_accum) | 840–876 | Delete | Replaced by `render_income_chart()` |
| Income sources bar chart (tab5) | 1242–1278 | Replace with helper call | `render_income_chart(strategy_df)` |
| `balance_column_config` dict (tab_accum) | 768–776 | Delete | Replaced by `render_balance_table()` |
| `balance_column_config` dict (tab5) | 1173–1181 | Replace with helper call | `render_balance_table(balances_df)` |
| `build_portfolio_display()` call ×3 | 370, 382, 390 | Single call at tab2 entry | `portdf = build_portfolio_display()` |
| Portfolio treemap (tab1 Dashboard) | 373–380 | Keep as summary widget | Shallow path `['Tax Type','Sector']` |
| Portfolio treemap (tab3 Portfolio) | 412–419 | Keep as drill-down | Deep path `['Tax Type','Sector','Ticker']` |
| `tab_strategy` stub | 739–742 | Remove entirely | Merged into tab3 Strategy |
| `tab4` legacy Retirement Planner | 882–973 | Remove entirely | Content already in Dashboard + tab5 |
| `networth` scalar overwrite | 887 | Remove (bug fix) | Use `networth_total = networth["total"].values[-1]` |

---

## New Tab Declaration (line 151 replacement)

```python
# BEFORE (6 tabs, 2 stubs, 1 legacy):
tab1, tab3, tab_strategy, tab_accum, tab4, tab5 = st.tabs([
    "Dashboard", "Portfolio planner", "Strategy",
    "Accumulation Strategy", "Retirement planner", "Withdrawal Strategy"
])

# AFTER (4 tabs, no stubs, no legacy):
tab_dashboard, tab_portfolio, tab_strategy, tab_config_link = st.tabs([
    "📊 Dashboard", "💼 Portfolio", "📈 Strategy", "⚙️ Settings"
])
```

> **Note:** The "Settings" tab can simply render a link/button to the existing `pages/configuration.py` Streamlit page, or embed a condensed version of the most-used settings (SSI age, expenses, rate of return).

---

## Sidebar Improvements

The sidebar currently shows 6 raw text inputs with no grouping. Proposed improvements:

1. **Group inputs** under a collapsible `st.expander("Strategy Parameters")`.
2. **Add inline validation** — show a warning if RATE > 15 or EXPENSE < 1000.
3. **Replace text inputs with `st.number_input`** for numeric fields (prevents invalid string entry).
4. **Add a "Retirement Date" display** (read-only, computed from config) so it's always visible.
5. **Remove SSI_AGE from sidebar** (already noted in sidebar.py comment line 56) — it's configured in the Configuration page.

---

## Implementation Phases

### Phase 1 — Quick Wins ✅ COMPLETE
- [x] Extract `format_currency()` to module level
- [x] Fix `networth` scalar overwrite bug in tab4
- [x] Remove `tab_strategy` stub tab
- [x] Remove `tab4` legacy Retirement Planner tab
- [x] Deduplicate `build_portfolio_display()` calls (single call, pass result)
- [x] Rename tab labels with emoji icons

### Phase 2 — Consolidation ✅ COMPLETE
- [x] Create `render_balance_chart()` helper function (lines 167–204)
- [x] Create `render_income_chart()` helper function (lines 207–248)
- [x] Create `render_balance_table()` helper function (lines 263–277)
- [x] Merge `tab_accum` and `tab5` into single Strategy tab with phase toggle
- [x] Add Net Worth Statement widget to Dashboard (lines 370–372)
- [x] Remove ~300 lines of duplicated withdrawal chart/table code from old tab5

### Phase 3 — Polish 🔄 IN PROGRESS
- [x] Improve sidebar with `st.number_input` and grouping (`components/sidebar.py`)
- [x] Add `render_net_worth_statement()` with styled DataFrame (completed in Phase 2)
- [x] Add "Retirement Date" read-only display to sidebar (both persons, from config)
- [x] Consolidate Portfolio tab sub-tabs (Overview / Holdings / Update Data) — already in place
- [x] Add Settings tab linking to configuration page — already in place

### Phase 4 — Future Enhancements
- [ ] Implement `build_accumulation_strategy_display()` (currently stubbed)
- [ ] Add YoY net worth trend line to Net Worth Statement
- [ ] Add portfolio performance vs benchmark chart
- [ ] Add tax efficiency score widget to Dashboard

---

## File Change Summary

| File | Change Type | Description |
|---|---|---|
| `planning_app.py` | **Major refactor** | Remove 2 tabs, extract helpers, add NW statement, consolidate strategy |
| `components/sidebar.py` | **Minor update** | Replace text inputs with number inputs, add grouping |
| `mockup/index.html` | **Reference only** | Existing mockup already reflects target design |
| `pages/configuration.py` | **No change** | Already well-structured |

---

## Risk & Compatibility Notes

1. **`build_accumulation_strategy_display()`** — currently raises an exception (caught by try/except in tab_accum). The Strategy tab must keep the same try/except guard until this function is implemented.
2. **Session state keys** — `CONV_TAX_RATE`, `EXPENSE`, etc. are read by both `tab5` and `components/sidebar.py`. No changes to key names needed.
3. **`st.cache_data`** — `build_historical_networth()` is cached at module level. Moving `build_portfolio_display()` to a single call inside the Portfolio tab means it will no longer be called at module level (line 382 removed), which is correct — it should only run when the tab is active.
4. **`networth` variable scope** — the DataFrame `networth` built in tab1 is referenced in tab4 (line 887). After tab4 is removed, this cross-tab reference disappears. The Net Worth Statement widget in Dashboard will use the same `networth` DataFrame already in scope within tab1.
5. **`color_palette`** — defined inside tab1 at line 161. Should be moved to module level so Portfolio and Strategy tabs can use the same palette without re-importing.

---

## Appendix — Current vs Proposed Tab Comparison

```
CURRENT                          PROPOSED
─────────────────────────────    ─────────────────────────────────────
📊 Dashboard                     📊 Dashboard
   • 5 KPI metrics                  • Net Worth Statement (NEW)
   • 3 charts                       • 5 KPI metrics
   • 2 treemaps                     • 3 charts
                                    • 2 treemaps

💼 Portfolio Planner             💼 Portfolio
   • Map sub-tab (treemap)          • Overview (treemap, drill-down)
   • Details sub-tab                • Holdings (details table)
   • Update Securities sub-tab      • Update Data (data entry)

📋 Strategy (STUB — REMOVE)
                                 📈 Strategy
📈 Accumulation Strategy            • Phase toggle: [Accum] [Withdrawal]
   • Annual Strategy (stub)         • Parameters
   • Account Balances               • Annual Plan
   • Visualizations                 • Balances
                                    • Visualizations
🗂️ Retirement Planner (REMOVE)      (shared helpers, no duplication)
   • 5 stale metrics
   • Inflow/Outflow table
   • Portfolio Value table

📉 Withdrawal Strategy           ⚙️ Settings
   • Parameters                     • Link to Configuration page
   • Annual Strategy                • Quick-edit most-used params
   • Account Balances
   • Visualizations