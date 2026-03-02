# Financial Planner — Full Application Review & Dashboard Improvement Plan

**Reviewed:** March 2026  
**Scope:** Full application audit — functionality, end-user experience, Dashboard tab analysis, and a prioritized improvement backlog for users aged 18–100 with $50K–$100M in net savings.

---

## 1. Application Overview

The application is a **Streamlit-based personal financial planning tool** with 7 main tabs:

| Tab | Purpose | Maturity |
|---|---|---|
| 📊 Dashboard | Net worth snapshot, charts, tax efficiency | ✅ Good foundation |
| 💼 Portfolio | Holdings, tax harvesting, rebalancing, DAF | ✅ Feature-rich |
| 📈 Strategy | Accumulation & withdrawal planning, RRI gauge | ✅ Solid |
| 🎯 Advanced Strategies | Tax planner, multi-year tax, backdoor Roth, NUA, QCD, SEPP, harvesting | ✅ Deep |
| 🎲 Monte Carlo | Simulation, stress tests, longevity, heatmap, scenario comparison | ✅ Excellent |
| ⚙️ Settings | Quick parameters, link to Configuration page | ✅ Adequate |

**Separate pages (Streamlit multi-page):**
- `⚖️ Estate Planning` — checklist, document tracker, review schedule
- `⚙️ Configuration` — personal info, financial assumptions, healthcare, SSI, tax strategy, portfolio data, real estate, advanced

---

## 2. Current Dashboard — What It Contains

The Dashboard (`tab1`, lines 872–1169 of [`planning_app.py`](planning_app.py:872)) currently renders:

### Row 1 — Three Charts (side by side)
1. **Total Net Worth** — bar chart, 12-month history, color-scaled
2. **Net Worth by Account** — stacked bar chart (Cash / Broker / Traditional / Roth)
3. **Asset Mix** — pie chart of current month's 4 account types

### Row 2 — Net Worth Statement
- Formal HTML table: Type → Type Total → Account Total → Account Name
- MoM change, YTD gains, rolling 12-month gains
- Real estate from config appended

### Row 3 — Net Worth Trend Line
- 12-month line chart with MoM annotation (▲/▼ $X,XXX)

### Row 4 — Tax Efficiency Section
- 4 metrics: Tax Efficiency Score, Roth Ratio, Tax-Deferred balance, Tax-Free balance

### Row 5 — Two Treemaps (side by side)
- **Account Mix Breakdown** — treemap by account_type → account_name
- **Portfolio Mix** — treemap by Tax Type → Sector

---

## 3. What Is MISSING from the Dashboard

The Dashboard is a good start but falls short of being a true **"financial health at a glance"** landing page. Below is a prioritized list of what should be added.

---

### 🔴 CRITICAL — Must Add (High Impact, Any User)

#### 3.1 — Personal Financial Snapshot Header (KPI Cards)
**Problem:** There are no top-of-page KPI metric cards. The user lands on a bar chart with no immediate dollar summary.  
**Fix:** Add a row of 5–6 `st.metric` cards at the very top of the Dashboard:

| Card | Value | Delta |
|---|---|---|
| Total Net Worth | $X,XXX,XXX | ▲ $X,XXX MoM |
| Cash & Equivalents | $XXX,XXX | ▲/▼ vs last month |
| Investment Portfolio | $X,XXX,XXX | ▲/▼ vs last month |
| Tax-Deferred (Trad) | $XXX,XXX | ▲/▼ vs last month |
| Tax-Free (Roth) | $XXX,XXX | ▲/▼ vs last month |
| Annual Dividend Income | $XX,XXX | from portfolio |

**Why:** Every financial dashboard (Personal Capital, Mint, Fidelity) leads with dollar totals. Users need to see their number in 2 seconds.

---

#### 3.2 — Financial Plan Readiness Indicator (RRI) on Dashboard
**Problem:** The RRI gauge (overall score + 6 sub-indicators) lives in the **Strategy tab**, not the Dashboard. This is the single most important "at a glance" metric for retirement planning.  
**Fix:** Move the RRI gauge + sub-indicator progress bars to the Dashboard. Keep a copy in Strategy for detail.

**Current location:** [`planning_app.py`](planning_app.py:2283) — `tab_accum`, lines 2283–2484  
**Target:** Top section of Dashboard, below KPI cards

---

#### 3.3 — Life Stage Indicator
**Problem:** The app knows what life stage the user is in (Stage 1–6: Accumulation → RMD) but never surfaces this on the Dashboard.  
**Fix:** Add a prominent life stage banner:

```
🏗️ You are in Stage 2: Prep for Retirement
   Retirement target: Person1 2028 | Person2 2030
   Years to retirement: 2 years
```

This is critical for users 18–100 — a 25-year-old accumulator and a 72-year-old RMD recipient need completely different context.

---

#### 3.4 — Goal Progress Bars (Accumulation Stage)
**Problem:** Users in accumulation have no visual progress toward their retirement number.  
**Fix:** Add a "Goal Progress" section for accumulation-stage users:

```
💰 Retirement Goal Progress
   Target: $3,000,000 (25× $120,000 annual expenses)
   Current: $1,247,000
   Progress: ████████░░░░░░░░░░░░  41.6%
   
   At current savings rate: On track for 2031 ✅
```

---

#### 3.5 — Safe Withdrawal Rate / Runway Indicator (Retirement Stage)
**Problem:** Users in retirement have no "how long will my money last" indicator on the Dashboard.  
**Fix:** For users in withdrawal phase, show:

```
💸 Withdrawal Runway
   Annual Withdrawal: $80,000
   Safe Withdrawal Rate: 4.2% (of $1.9M portfolio)
   Monte Carlo Success Rate: 94% to age 90
   Estimated Runway: 35+ years ✅
```

---

#### 3.6 — Income vs. Expenses Summary
**Problem:** The Dashboard shows net worth but has no income/expense context. A user cannot tell if they are cash-flow positive or negative.  
**Fix:** Add a simple income vs. expense card:

```
📊 Annual Cash Flow (Current Year)
   Income (Wages + SS + Dividends): $XXX,XXX
   Expenses (Planned):              $XXX,XXX
   Net Cash Flow:                   ▲ $XX,XXX  ✅
```

---

### 🟡 HIGH PRIORITY — Should Add

#### 3.7 — Social Security Claiming Decision Widget
**Problem:** SSI claiming age is one of the highest-impact decisions in retirement planning. The Dashboard shows nothing about it.  
**Fix:** Add a compact SSI summary card:

```
📋 Social Security
   Person1: Claiming at age 70 (2031) — $3,200/mo
   Person2: Claiming at age 67 (2029) — $1,800/mo
   Combined at full claim: $60,000/year
   Breakeven vs. age 62: Age 78 ✅
```

---

#### 3.8 — Healthcare Cost Tracker
**Problem:** Healthcare is the #1 retirement expense wildcard. The Dashboard shows nothing about it.  
**Fix:** Add a healthcare summary:

```
🏥 Healthcare
   Current: ACA Marketplace — $1,200/mo
   Medicare starts: 2027 (age 65)
   IRMAA risk: None at current income ✅
```

---

#### 3.9 — Tax Bracket Position (Current Year)
**Problem:** The Tax Efficiency section shows Roth ratio but not where the user sits in their current tax bracket — critical for Roth conversion decisions.  
**Fix:** Add a tax bracket position indicator:

```
🧮 Tax Position (2026)
   Estimated AGI: $XXX,XXX
   Current Bracket: 22% (MFJ)
   Headroom to 24% bracket: $XX,XXX
   Roth Conversion Opportunity: Up to $XX,XXX at 22%
```

---

#### 3.10 — Portfolio Rebalancing Alert
**Problem:** The rebalancing analysis lives deep in Portfolio → Rebalancing. Users won't see it unless they navigate there.  
**Fix:** Add a rebalancing status badge on the Dashboard:

```
⚖️ Portfolio Balance
   Status: ✅ Balanced (within 5% drift threshold)
   Cash: 8% (target 10%) | Bonds: 11% | Stocks: 81%
   Last rebalanced: Jan 2026
```

If drift is triggered: show 🔴 with a link to the Rebalancing tab.

---

#### 3.11 — Estate Planning Completion Status
**Problem:** Estate planning completeness is computed in the RRI (Strategy tab) but never shown on the Dashboard.  
**Fix:** Add a compact estate planning status:

```
⚖️ Estate Planning
   Checklist: 12 of 18 items complete (67%)
   ⚠️ Missing: Healthcare Directive, Beneficiary Review
   → Go to Estate Planning page
```

---

#### 3.12 — Emergency Fund Status
**Problem:** Cash buffer adequacy is computed in the RRI but not shown on the Dashboard.  
**Fix:** Add an emergency fund indicator:

```
🏦 Emergency Fund
   Current Cash: $XXX,XXX
   Target (6 months expenses): $XXX,XXX
   Status: ✅ Fully funded (8.2 months)
```

---

#### 3.13 — Year-to-Date Performance Summary
**Problem:** The net worth statement shows YTD gains but there is no YTD performance context (% return, vs. benchmark).  
**Fix:** Add a YTD performance card:

```
📈 Year-to-Date Performance (2026)
   Portfolio Return: +8.3%
   Benchmark (S&P 500): +6.1%
   You are: ▲ +2.2% ahead of benchmark
   Best performer: NVDA (+34%)
   Worst performer: BND (-2%)
```

---

### 🟢 MEDIUM PRIORITY — Nice to Have

#### 3.14 — Upcoming Financial Events Calendar
**Problem:** There is no "what's coming up" awareness on the Dashboard.  
**Fix:** Add a compact upcoming events list:

```
📅 Upcoming Events
   Mar 15: Q1 Estimated Tax Payment Due — $X,XXX
   Apr 15: Tax Filing Deadline
   Jun 2026: Person2 Medicare Enrollment Window
   Dec 31: Roth Conversion Deadline — $XX,XXX headroom remaining
   Jan 2027: RMD Required — est. $XX,XXX
```

---

#### 3.15 — Dividend Income Tracker
**Problem:** Dividend income is computed in the portfolio module but never surfaced on the Dashboard.  
**Fix:** Add a dividend income card:

```
💰 Dividend Income
   Annual Dividend: $XX,XXX ($X,XXX/mo)
   Yield on Cost: 3.2%
   Current Yield: 2.8%
   Next ex-dividend: SCHD — Mar 20
```

---

#### 3.16 — Roth Conversion Opportunity Alert
**Problem:** The best time to do Roth conversions is during low-income years. The Dashboard should flag this opportunity.  
**Fix:** Add a Roth conversion alert when conditions are favorable:

```
🔄 Roth Conversion Opportunity
   You have $XX,XXX of headroom in the 22% bracket
   Converting now saves est. $X,XXX vs. converting at 24%+
   → Go to Advanced Strategies → Tax Planner
```

---

#### 3.17 — Net Worth Milestone Tracker
**Problem:** There is no gamification or milestone awareness to keep users engaged.  
**Fix:** Add milestone progress:

```
🏆 Milestones
   ✅ $500K Net Worth — Achieved Jan 2024
   ✅ $1M Net Worth — Achieved Aug 2025
   🎯 Next: $1.5M — $253,000 to go (est. 2027)
   🎯 FIRE Number ($3M): $1,753,000 to go
```

---

#### 3.18 — Savings Rate Tracker
**Problem:** Savings rate is the #1 driver of wealth accumulation but is not tracked anywhere.  
**Fix:** Add a savings rate card for accumulation-stage users:

```
💪 Savings Rate (2026)
   Gross Income: $XXX,XXX
   Total Savings (401k + Roth + Brokerage): $XX,XXX
   Savings Rate: 28% ✅ (target: 20%+)
```

---

## 4. What Should Be MOVED from Dashboard to Another Tab

### 4.1 — Move: Account Mix Breakdown Treemap → Portfolio Tab
**Current location:** Dashboard, bottom-left treemap  
**Problem:** The Account Mix Breakdown treemap (account_type → account_name) is a portfolio detail view, not a dashboard summary.  
**Move to:** Portfolio tab → Map sub-tab (already has a deeper version)  
**Replace with:** A simpler donut chart showing just the 4 account type totals

### 4.2 — Move: Full Net Worth Statement Table → Strategy Tab or Collapse
**Current location:** Dashboard, middle section  
**Problem:** The detailed HTML net worth statement (with all individual accounts) is too granular for a landing page. It belongs in a "statements" or "details" view.  
**Move to:** Collapse into an expander on the Dashboard, or move to a dedicated "Statements" sub-tab  
**Replace with:** The 5 KPI metric cards (see 3.1 above)

### 4.3 — Move: Tax Efficiency Metrics → Consolidate with Tax Position (3.9)
**Current location:** Dashboard, 4 metrics (Tax Efficiency Score, Roth Ratio, Tax-Deferred, Tax-Free)  
**Problem:** These 4 metrics are scattered and lack context. The Roth Ratio alone is not actionable without knowing the bracket headroom.  
**Move to:** Merge into a single "Tax Health" card that combines efficiency score + bracket position + conversion opportunity

---

## 5. Dashboard Layout Recommendation

The ideal Dashboard layout for users 18–100, $50K–$100M:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📊 Financial Planner Dashboard                    [Refresh] [Settings]  │
├─────────────────────────────────────────────────────────────────────────┤
│  LIFE STAGE BANNER                                                        │
│  🏗️ Stage 2: Prep for Retirement | Person1 retires 2028 | 2 years away   │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────────┤
│ Net Worth│  Cash    │ Invest.  │ Trad IRA │ Roth IRA │ Annual Dividends │
│ $1.25M   │ $120K    │ $680K    │ $350K    │ $100K    │ $18,400          │
│ ▲ $8,200 │ ▲ $1,200 │ ▲ $5,100 │ ▲ $1,500 │ ▲ $400   │ 2.8% yield       │
├──────────┴──────────┴──────────┴──────────┴──────────┴──────────────────┤
│  RETIREMENT READINESS                    │  GOAL PROGRESS / RUNWAY       │
│  ┌─────────────────────────────────┐     │  Target: $3M (25× expenses)   │
│  │  Overall: 68% 🟡 Needs Attention│     │  Current: $1.25M              │
│  │  ████████████████░░░░░░░░  68%  │     │  ████████░░░░░░░░░░░░  41.6%  │
│  │  💰 Portfolio Funding:  72%     │     │  On track for 2031 ✅          │
│  │  ⚖️ Estate Planning:    45% ⚠️  │     │                               │
│  │  🔀 Tax Diversification: 78%    │     │  MC Success Rate: 94% ✅       │
│  │  📋 Social Security:    100%    │     │  Safe Withdrawal: 4.2%        │
│  │  🏥 Healthcare:          60%    │     │                               │
│  │  🏦 Emergency Fund:      85%    │     │                               │
│  └─────────────────────────────────┘     │                               │
├──────────────────────────────────────────┴───────────────────────────────┤
│  ANNUAL CASH FLOW          │  TAX POSITION (2026)    │  ALERTS           │
│  Income:    $180,000       │  AGI: $142,000          │  ⚠️ Estate: 2 items│
│  Expenses:  $120,000       │  Bracket: 22% (MFJ)     │  🔄 Roth: $18K    │
│  Net:  ▲ $60,000 ✅        │  Headroom: $18,000      │     headroom avail │
│                            │  IRMAA Risk: None ✅     │  ⚖️ Rebalance: OK  │
├────────────────────────────┴─────────────────────────┴───────────────────┤
│  NET WORTH TREND (12 months)                                              │
│  [Line chart with MoM annotation]                                         │
├──────────────────────────────────────────────────────────────────────────┤
│  NET WORTH BY ACCOUNT (stacked bar)  │  ASSET MIX (pie/donut)            │
├──────────────────────────────────────┴───────────────────────────────────┤
│  UPCOMING EVENTS                     │  SOCIAL SECURITY SUMMARY          │
│  Mar 15: Q1 Tax Payment $2,100       │  Person1: Age 70 → $3,200/mo      │
│  Apr 15: Tax Filing                  │  Person2: Age 67 → $1,800/mo      │
│  Dec 31: Roth Conversion Deadline    │  Combined: $60,000/yr             │
│                                      │  Breakeven vs 62: Age 78 ✅        │
└──────────────────────────────────────┴───────────────────────────────────┘
```

---

## 6. Tab-by-Tab Functionality Review

### 📊 Dashboard
**Strengths:** Net worth statement, trend line, tax efficiency, treemaps  
**Gaps:** See Section 3 above — missing KPI cards, RRI, life stage, goal progress, cash flow, SSI summary, tax bracket position, alerts

### 💼 Portfolio
**Strengths:** Excellent — treemap drill-down, full holdings table, tax harvesting with wash-sale replacements, rebalancing with action plan, DAF bundling advisor  
**Gaps:**
- No dividend income summary at the top
- No portfolio performance attribution (which holdings drove gains/losses)
- No sector concentration risk alert (e.g., "45% in Technology — consider diversifying")
- Benchmark comparison is in Portfolio → Map tab, not visible on Dashboard
- No cost basis lot selection (HIFO/FIFO/specific lot) for tax optimization

### 📈 Strategy
**Strengths:** RRI gauge is excellent, phase toggle (Accumulation/Withdrawal) works well, life stage descriptions are clear  
**Gaps:**
- RRI should be on Dashboard, not buried in Strategy
- Accumulation strategy table has no "savings rate needed to hit goal" calculation
- Withdrawal strategy has no "what if I retire 2 years earlier/later" sensitivity analysis
- No Roth conversion ladder visualization (year-by-year conversion amounts as a chart)
- No "what if" scenario comparison (e.g., retire at 60 vs 65 vs 70)

### 🎯 Advanced Strategies
**Strengths:** Comprehensive — Tax Planner, Multi-Year Tax, Backdoor Roth, NUA, QCD, SEPP, Capital Loss Harvesting  
**Gaps:**
- Tax Planner state tax is hardcoded at 3% — should be configurable
- No I-Bond / TIPS / inflation-protected asset analysis
- No HSA optimization strategy (triple tax advantage)
- No 529 college savings planning (relevant for users 25–50)
- BETR Roth conversion module exists in code but is not surfaced in the UI

### 🎲 Monte Carlo
**Strengths:** Best-in-class — fan chart, stress tests, longevity, heatmap, scenario comparison  
**Gaps:**
- Inputs are disconnected from actual portfolio data (user must manually enter starting portfolio)
- Should auto-populate from current net worth
- No "what if I add $X/year in savings" scenario
- No inflation sensitivity analysis (what if inflation is 5% vs 3%)

**Gaps:**
- **Very thin** — the diagram is static/generic, not driven by actual account balances
- No dollar amounts on the flow arrows
- No income flow (wages → accounts)
- No tax flow (accounts → IRS)
- Should show actual monthly/annual flow amounts
- Account Details sub-tab shows raw data with no formatting

### ⚙️ Settings
**Strengths:** Quick parameters work, links to Configuration page  
**Gaps:**
- No "first-time setup wizard" for new users
- No data import capability (CSV, Fidelity/Schwab export)
- No backup/restore from the main app (only in Configuration page)

---

## 7. End-User Experience Issues

### 7.1 — New User Onboarding (Critical Gap)
A new user opening the app for the first time sees an error: *"Insufficient historical data. Need at least 2 months of portfolio data."* There is no onboarding wizard, no sample data, no "get started" guide. This is a blocker for any user under 40 who is just starting to track their finances.

**Fix:** Add a first-run detection and onboarding flow:
1. Detect empty portfolio data
2. Show a "Welcome" screen with 3 steps: Configure → Enter Portfolio → View Dashboard
3. Offer sample data to explore the app before entering real data

### 7.2 — Mobile / Narrow Screen Experience
The 3-column chart layout at the top of the Dashboard collapses poorly on narrow screens. The treemaps become unreadable below 800px width.

**Fix:** Use responsive column counts (`st.columns([1])` on mobile, `st.columns(3)` on desktop) or add a viewport width check.

### 7.3 — Data Staleness Warning
The stale data warning (`⚠️ No portfolio data found for March 2026. Showing February 2026 data`) appears in the middle of the Dashboard, not at the top. Users may not notice it.

**Fix:** Move the stale data warning to the very top of the Dashboard as a persistent banner.

### 7.4 — No "What Does This Mean?" Context
Many metrics (Tax Efficiency Score, Roth Ratio, IRMAA) are shown without plain-English context for users who are not financial experts. A 25-year-old or a 75-year-old without financial background will not know what to do with "Tax Efficiency Score: 62%".

**Fix:** Add `help=` tooltips to every metric card, and add a "📚 Learn More" expander below each major section.

### 7.5 — Configuration Discoverability
The Configuration page is a separate Streamlit page (not a tab). New users may not find it. The sidebar has a small link but it is easy to miss.

**Fix:** Add a prominent "⚙️ Complete Your Setup" call-to-action on the Dashboard when configuration is incomplete (e.g., SSI not configured, healthcare not set).

### 7.6 — No Print / Export from Dashboard
Users cannot export a PDF or print a financial summary from the Dashboard.

**Fix:** Add a "📥 Export Dashboard Summary (PDF)" button that generates a one-page financial snapshot.

### 7.7 — Chart Accessibility
All charts use color as the only differentiator (no patterns, no labels on bars). Users with color vision deficiency cannot distinguish Cash (yellow) from Roth (purple) in the stacked bar chart.

**Fix:** Add text labels to bar segments, use patterns in addition to colors, ensure sufficient contrast ratios.

---

## 8. Prioritized Implementation Backlog

### Sprint 1 — Dashboard Quick Wins (1–2 days)
- [ ] **Add KPI metric cards** at top of Dashboard (Total NW, Cash, Investments, Trad, Roth, Dividends)
- [ ] **Move RRI gauge** from Strategy tab to Dashboard (keep copy in Strategy)
- [ ] **Add Life Stage banner** (current stage + retirement target dates + years to retirement)
- [ ] **Move stale data warning** to top of Dashboard
- [ ] **Add `help=` tooltips** to all existing Dashboard metrics

### Sprint 2 — Dashboard Core Features (3–5 days)
- [ ] **Add Goal Progress / Runway section** (accumulation: progress to FIRE number; retirement: MC success rate + runway)
- [ ] **Add Annual Cash Flow card** (income vs. expenses vs. net)
- [ ] **Add Tax Bracket Position card** (AGI, bracket, headroom, conversion opportunity)
- [ ] **Add SSI Summary card** (claiming ages, monthly amounts, breakeven)
- [ ] **Add Rebalancing Status badge** (balanced/needs rebalancing with link)
- [ ] **Add Estate Planning Status badge** (% complete with link)

### Sprint 3 — Dashboard Enhancements (1 week)
- [ ] **Add Upcoming Events calendar** (tax deadlines, Medicare enrollment, RMD dates)
- [ ] **Add Dividend Income tracker** (annual, monthly, yield)
- [ ] **Add Roth Conversion Opportunity alert** (when headroom exists)
- [ ] **Add Savings Rate tracker** (for accumulation-stage users)
- [ ] **Add Net Worth Milestone tracker**
- [ ] **Collapse Net Worth Statement** into expander (replace with KPI cards)
- [ ] **Move Account Mix Breakdown treemap** to Portfolio tab

### Sprint 4 — UX & Onboarding (1 week)
- [ ] **First-run onboarding wizard** (detect empty data, show setup steps)
- [ ] **Sample data mode** (explore app without entering real data)
- [ ] **"Complete Your Setup" CTA** on Dashboard when config is incomplete
- [ ] **Make Monte Carlo auto-populate** from current net worth
- [ ] **Add state tax configuration** to Tax Planner (remove hardcoded 3%)

### Sprint 5 — Advanced Features (2 weeks)
- [ ] **HSA optimization strategy** in Advanced Strategies
- [ ] **529 college savings planning** in Advanced Strategies
- [ ] **BETR Roth conversion UI** (module exists, not surfaced)
- [ ] **Portfolio performance attribution** (which holdings drove gains/losses)
- [ ] **Sector concentration risk alert** in Portfolio
- [ ] **"What if" retirement date sensitivity** in Strategy tab
- [ ] **Roth conversion ladder visualization** (year-by-year chart)
- [ ] **PDF export** of Dashboard summary
- [ ] **Data import** (CSV from Fidelity/Schwab/Vanguard)

---

## 9. Age & Wealth Segment Considerations

The app targets users 18–100 with $50K–$100M. Here is how the Dashboard should adapt:

| Segment | Age | Net Worth | Dashboard Priority |
|---|---|---|---|
| Young Accumulator | 18–35 | $50K–$500K | Savings rate, goal progress, FIRE number, time to retirement |
| Mid-Career | 35–50 | $500K–$2M | Goal progress, tax efficiency, Roth conversion, college savings |
| Pre-Retirement | 50–65 | $1M–$5M | RRI gauge, Roth conversion window, SSI claiming strategy, healthcare |
| Early Retirement | 60–70 | $1M–$10M | Withdrawal runway, ACA optimization, Roth conversion, IRMAA |
| Full Retirement | 70+ | $500K–$100M | RMD planning, SSI optimization, estate planning, DAF, QCD |

**Recommendation:** Add a "Planning Mode" toggle or auto-detect based on configured retirement dates:
- **Accumulation Mode** → emphasize savings rate, goal progress, investment growth
- **Transition Mode** (within 5 years of retirement) → emphasize RRI, Roth conversions, SSI timing
- **Distribution Mode** → emphasize withdrawal runway, RMDs, tax efficiency, estate planning

---

## 10. Technical Debt on the Dashboard

| Issue | Location | Impact | Fix |
|---|---|---|---|
| `y_axis_min` calculation uses `y_range * 1` (100% padding) instead of `y_range * 0.1` | [`planning_app.py`](planning_app.py:898) | Bar chart y-axis starts too low, bars look tiny | Change `* 1` to `* 0.1` |
| Asset Mix pie chart uses hardcoded `["Cash","Broker","Traditional","Roth"]` labels | [`planning_app.py`](planning_app.py:1005) | Labels won't match if account types change | Use `networth.columns[0:4]` |
| `row_to_plot = networth.iloc[-1,0:4]` — positional column selection | [`planning_app.py`](planning_app.py:1000) | Breaks if column order changes | Use named columns |
| Tax Efficiency Score formula: `(Roth + Taxable) / Total` — includes cash in denominator | [`planning_app.py`](planning_app.py:1088) | Cash dilutes the score misleadingly | Exclude cash from denominator or document the formula |
| Net Worth Trend chart and Net Worth bar chart both show 12-month history — redundant | [`planning_app.py`](planning_app.py:886) and [`planning_app.py`](planning_app.py:1041) | Two charts showing same data | Remove the bar chart, keep the trend line |
| Dashboard renders all content even when `networth.empty` — `st.stop()` halts entire page | [`planning_app.py`](planning_app.py:874) | New users see a hard error with no guidance | Replace `st.stop()` with a friendly onboarding prompt |

---

## 11. Summary

The application is **technically impressive** — it has Monte Carlo simulation, tax harvesting, rebalancing, BETR Roth conversion, multi-year tax planning, estate planning, and more. The underlying data infrastructure is solid.

The **Dashboard is the weakest link**. It currently functions as a "net worth history viewer" rather than a true financial health command center. The most critical missing elements are:

1. **KPI metric cards** — users need their numbers in 2 seconds
2. **Financial Plan Readiness Indicator on the Dashboard** — the most important metric is buried in Strategy
3. **Life Stage awareness** — the app knows what stage you're in but doesn't tell you
4. **Goal progress / withdrawal runway** — the "am I on track?" question is unanswered
5. **Cash flow summary** — income vs. expenses is fundamental
6. **Actionable alerts** — Roth conversion headroom, rebalancing needed, estate planning gaps
7. **Onboarding for new users** — the app crashes on empty data with no guidance

Addressing Sprint 1 and Sprint 2 items above would transform the Dashboard from a chart viewer into a genuine financial planning command center suitable for users at any life stage and wealth level.
---

## 12. Navigation Architecture — Tabs vs. Pages, and Faux-Tab Linking

### 12.1 — Should Some Features Be Separate Pages?

**Yes.** The current app has 7 tabs in [`planning_app.py`](planning_app.py) plus 2 Streamlit pages (`pages/`). Several tabs are heavy enough — and used infrequently enough — that they belong as separate pages rather than tabs that load on every visit.

**The core problem with tabs in Streamlit:**
All tab content in a single `planning_app.py` is parsed and partially executed on every page load, even for tabs the user never opens. The Monte Carlo sidebar inputs and Advanced Strategies forms consume memory and execution time on every Dashboard visit. Moving heavy, infrequently-used features to separate pages means they only load when navigated to.

**Recommended split:**

| Feature | Current Location | Recommended | Reason |
|---|---|---|---|
| 📊 Dashboard | `tab1` in `planning_app.py` | **Keep as main page** | Landing page — must be instant |
| 💼 Portfolio | `tab3` in `planning_app.py` | **Keep as tab** | Used frequently alongside Dashboard |
| 📈 Strategy | `tab_accum` in `planning_app.py` | **Keep as tab** | Core planning — used regularly |
| 🎯 Advanced Strategies | `tab_advanced` in `planning_app.py` | **Move to page** | 7 sub-tabs, heavy, used occasionally |
| 🎲 Monte Carlo | `tab_mc` in `planning_app.py` | **✅ Moved to page** | Computationally heavy, used occasionally |
| ⚙️ Settings | `tab5` in `planning_app.py` | **Move to page** | Already links to Configuration page |
| ⚖️ Estate Planning | `pages/1_estate_planning.py` | **Keep as page** ✅ | Already correct |
| ⚙️ Configuration | `pages/2_configuration.py` | **Keep as page** ✅ | Already correct |

**Result:** `planning_app.py` would contain only 3 tabs (Dashboard, Portfolio, Strategy), making it fast and focused. The heavy tools become dedicated pages. Estimated reduction: **5,122 lines → ~500 lines** in the main file.

---

### 12.2 — The Faux-Tab Navigation Pattern in Streamlit

Streamlit's native multi-page navigation renders as a **sidebar list** (not tabs). However, there are two well-supported techniques to make pages feel like tabs — a horizontal navigation bar that looks and behaves like tabs but routes to separate pages.

---

#### Technique A — `st.page_link()` Navigation Bar (Streamlit ≥ 1.31, **No Extra Dependencies**)

Streamlit 1.31+ added [`st.page_link()`](https://docs.streamlit.io/library/api-reference/widgets/st.page_link) which renders a styled link to any page. By placing a row of `st.page_link()` calls inside a shared component, you get a horizontal nav bar that looks like tabs. The app already requires `streamlit>=1.28.0` in [`requirements.txt`](requirements.txt) — bumping to `>=1.31.0` unlocks this.

**Implementation — [`components/navbar.py`](components/navbar.py):**

```python
import streamlit as st

# Ordered list of (page_path, display_label) for the nav bar
NAV_PAGES = [
    ("planning_app.py",                "📊 Dashboard"),
    ("pages/3_portfolio.py",           "💼 Portfolio"),
    ("pages/4_strategy.py",            "📈 Strategy"),
    ("pages/5_advanced_strategies.py", "🎯 Advanced"),
    ("pages/6_monte_carlo.py",         "🎲 Monte Carlo"),
    ("pages/1_estate_planning.py",     "⚖️ Estate Planning"),
    ("pages/2_configuration.py",       "⚙️ Settings"),
]

def navbar():
    """Render a horizontal faux-tab navigation bar using st.page_link()."""
    cols = st.columns(len(NAV_PAGES))
    for col, (page_path, label) in zip(cols, NAV_PAGES):
        with col:
            st.page_link(page_path, label=label, use_container_width=True)
    st.divider()
```

**Usage — add to the top of every page file:**

```python
from components.navbar import navbar
navbar()
# ... rest of page content
```

**Result:** Every page shows the same horizontal row of links at the top. Streamlit automatically bolds/underlines the current page's link. It looks and feels like a tab bar.

**Pros:**
- Native Streamlit — zero extra dependencies
- Works with Streamlit's built-in page routing
- Active page is automatically highlighted
- Each page loads independently (no shared execution overhead)

**Cons:**
- Clicking a nav link causes a full page navigation (not an instant tab switch like `st.tabs()`)
- No custom color/icon styling beyond Streamlit defaults
- Requires adding `navbar()` call to every page file

---

#### Technique B — `streamlit-option-menu` (Third-Party, **Best Visual Result**)

The [`streamlit-option-menu`](https://github.com/victoryhb/streamlit-option-menu) package renders a horizontal or vertical menu that looks exactly like a professional tab bar, with icons, active highlighting, and full CSS control. It is the most popular community solution for this pattern and is actively maintained.

**Install:**
```
pip install streamlit-option-menu
```

Add to [`requirements.txt`](requirements.txt):
```
streamlit-option-menu>=0.3.6
```

**Implementation — [`components/navbar.py`](components/navbar.py):**

```python
import streamlit as st
from streamlit_option_menu import option_menu

# Map display label → Streamlit page path (for st.switch_page routing)
NAV_ROUTES = {
    "📊 Dashboard":       "planning_app.py",
    "💼 Portfolio":       "pages/3_portfolio.py",
    "📈 Strategy":        "pages/4_strategy.py",
    "🎯 Advanced":        "pages/5_advanced_strategies.py",
    "🎲 Monte Carlo":     "pages/6_monte_carlo.py",
    "⚖️ Estate Planning": "pages/1_estate_planning.py",
    "⚙️ Settings":        "pages/2_configuration.py",
}

def navbar(current_page: str = "📊 Dashboard"):
    """Render a horizontal faux-tab navigation bar.
    
    Args:
        current_page: The display label of the currently active page.
                      Used to highlight the active tab.
    """
    labels = list(NAV_ROUTES.keys())
    selected = option_menu(
        menu_title=None,
        options=labels,
        default_index=labels.index(current_page) if current_page in labels else 0,
        orientation="horizontal",
        styles={
            "container": {
                "padding": "0!important",
                "background-color": "#fafafa",
                "border-bottom": "1px solid #dee2e6",
            },
            "nav-link": {
                "font-size": "13px",
                "text-align": "center",
                "padding": "8px 12px",
                "--hover-color": "#f0f0f0",
            },
            # Active tab uses the app's primary color from .streamlit/config.toml
            "nav-link-selected": {
                "background-color": "#F63366",
                "color": "white",
                "font-weight": "600",
            },
        },
    )
    # Navigate to the selected page when user clicks a different tab
    if selected != current_page:
        st.switch_page(NAV_ROUTES[selected])   # Requires Streamlit >= 1.31
```

**Usage — top of each page file:**
```python
from components.navbar import navbar
navbar(current_page="📊 Dashboard")   # pass the label matching this page
```

**Result:** A polished horizontal tab bar with the active tab highlighted in the app's primary pink (`#F63366` from [`.streamlit/config.toml`](.streamlit/config.toml)).

**Pros:**
- Looks exactly like a professional tab bar
- Active tab highlighted with the app's primary color
- Full CSS control over fonts, padding, hover effects
- `st.switch_page()` provides programmatic navigation
- Works with icons, custom colors, vertical orientation option

**Cons:**
- Extra dependency (`streamlit-option-menu`)
- Still causes a full page load on navigation (not instant like `st.tabs()`)
- Requires passing `current_page` correctly on each page

---

#### Technique C — Hybrid Architecture (Recommended for This App)

The best real-world approach combines both patterns:

```
Top-level navigation:  faux-tab navbar (pages, loads independently)
Within a page:         st.tabs() for sub-sections (instant switching)
```

Example for the Portfolio page:

```
[📊 Dashboard] [💼 Portfolio] [📈 Strategy] [🎯 Advanced] [🎲 Monte Carlo] [⚙️ Settings]
                    ↑ faux-tab navbar — clicking navigates to a separate page

Within 💼 Portfolio page:
  [Map of Portfolio] [Details] [🌾 Tax Harvesting] [⚖️ Rebalancing] [🏦 DAF Bundling]
                    ↑ st.tabs() — instant switching, all within one page load
```

This gives you:
- **Fast top-level navigation** — each major section is a lean, independent page
- **Instant sub-tab switching** within a page — no page reload for related features
- **Clean separation of concerns** — each page file has a single responsibility

---

### 12.3 — Recommended Page Structure After Refactor

```
planning_app.py                  ← 📊 Dashboard (main entry, ~500 lines)
pages/
  1_estate_planning.py           ← ⚖️ Estate Planning (already exists ✅)
  2_configuration.py             ← ⚙️ Configuration (already exists ✅)
  3_portfolio.py                 ← 💼 Portfolio (extracted from tab3)
  4_strategy.py                  ← 📈 Strategy (extracted from tab_accum)
  5_advanced_strategies.py       ← 🎯 Advanced Strategies (extracted from tab_advanced)
  6_monte_carlo.py               ← 🎲 Monte Carlo (extracted from tab_mc)
components/
  navbar.py                      ← Shared faux-tab navigation bar (NEW)
  sidebar.py                     ← Existing sidebar (keep, call from every page)
```

**`planning_app.py` after refactor** contains only:
1. The faux-tab navbar call
2. The sidebar call
3. The Dashboard content (KPI cards, RRI, charts, alerts)

Reduction: **5,122 lines → ~500 lines** — a 90% reduction that makes the main file maintainable and the Dashboard load time fast.

---

### 12.4 — Shared State Between Pages

The main challenge with multi-page apps is sharing data (e.g., `networth` DataFrame, portfolio data) across pages. Streamlit handles this via `st.session_state`, which persists across page navigations within the same session.

**Pattern for shared expensive data:**

```python
# In load_data.py or a new shared_state.py
def get_shared_networth(num_months: int = 12):
    """Load networth from cache; store in session_state for cross-page access."""
    if "_shared_networth" not in st.session_state:
        st.session_state["_shared_networth"] = render_networth(
            num_months=num_months,
            done_event=st.session_state.get("_networth_done_event"),
            build_fn=build_historical_networth,
        )
    return st.session_state["_shared_networth"]
```

Each page calls `get_shared_networth()` instead of rebuilding it. The first page to load populates the cache; subsequent pages read from `session_state` instantly.

**Session state keys already in use** (safe to read from any page without re-computation):

| Key | Value | Set by |
|---|---|---|
| `CONV_TAX_RATE`, `EXPENSE`, `EXPENSE_MULTIPLIER`, `RATE` | Strategy parameters | [`components/sidebar.py`](components/sidebar.py) |
| `SSI_AGE` | Social Security claiming age | [`components/sidebar.py`](components/sidebar.py) |
| `_mc_result`, `_mc_inputs` | Monte Carlo results | [`planning_app.py`](planning_app.py:2842) |
| `_portfolio_done_event` | Background rebuild event | [`planning_app.py`](planning_app.py:858) |
| `_networth_done_event` | Background rebuild event | [`planning_app.py`](planning_app.py:820) |
| `sidebar_config_synced` | One-time config sync flag | [`components/sidebar.py`](components/sidebar.py:186) |

---

### 12.5 — Implementation Steps

1. **Bump Streamlit version** in [`requirements.txt`](requirements.txt): `streamlit>=1.31.0`
2. **Add `streamlit-option-menu>=0.3.6`** to [`requirements.txt`](requirements.txt) (if using Technique B)
3. **Create [`components/navbar.py`](components/navbar.py)** with the `navbar()` function
4. **Extract each heavy tab** into its own `pages/N_name.py` file — copy the `with tabN:` block content, wrap in a `st.set_page_config()` + `navbar()` + `sidebar()` header
5. **Add `navbar(current_page="...")` call** at the top of every page file
6. **Add shared state guards** — each extracted page should call `get_shared_networth()` and `get_shared_portfolio()` rather than rebuilding from scratch
7. **Remove extracted tabs** from `planning_app.py` — replace with the 3-tab structure (Dashboard, Portfolio, Strategy)
8. **Test navigation** — verify `st.switch_page()` routing works for all 8 nav items
9. **Verify sidebar** renders on all pages (call `sidebar()` in each page's header)

**Estimated effort:** 2–3 days for a clean extraction with shared state wiring.

---

### 12.6 — Visual Result

**Before (current):** Single page with 7 tabs. All 5,122 lines execute on every load.

**After (faux-tab pages):** A horizontal nav bar at the top of every page. Clicking "🎲 Monte Carlo" navigates to a dedicated page that only loads Monte Carlo code. The Dashboard loads in ~1 second instead of 3–5 seconds.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [📊 Dashboard] [💼 Portfolio] [📈 Strategy] [🎯 Advanced] [🎲 Monte Carlo]  │
│ [⚖️ Estate Planning] [⚙️ Settings]                                          │
│ ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│  📊 Dashboard content here...                                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

The user experience is indistinguishable from a tab bar. The URL changes (e.g., `localhost:8501/monte_carlo`) but the visual presentation is a horizontal nav bar with the active page highlighted in the app's primary color. Users who are accustomed to Fidelity, Schwab, or Personal Capital will immediately recognize the pattern.