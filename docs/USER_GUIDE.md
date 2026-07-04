# User Guide — Retirement Planning Application

This guide covers every page and major feature of the application.  
New to the app? Start with the **[Quick Start Guide](user/QUICKSTART.md)** first.

---

## Table of Contents

1. [Application Layout](#1-application-layout)
2. [Configuration Page](#2-configuration-page)
3. [Dashboard](#3-dashboard)
4. [Portfolio Hub](#4-portfolio-hub)
5. [Strategy Page](#5-strategy-page)
6. [Monte Carlo Simulation](#6-monte-carlo-simulation)
7. [Advanced Strategies](#7-advanced-strategies)
8. [Estate Planning](#8-estate-planning)
9. [Scenario Planning](#9-scenario-planning)
10. [Reports](#10-reports)
11. [Market Indicators — Reference Tables](#11-market-indicators--reference-tables)
    - [Dashboard: Three-Timeframe EMA Regime System](#11a-dashboard-three-timeframe-ema-regime-system)
    - [Portfolio Market Stress Indicator](#11b-portfolio-market-stress-indicator)
    - [Portfolio Holdings: Per-Security Indicators](#11c-portfolio-holdings-per-security-indicators)
12. [Key Data Files](#12-key-data-files)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Application Layout

The app is a multi-page Streamlit application. Pages are listed in the left sidebar:

| Sidebar entry | Page |
|---|---|
| 📊 Dashboard | Overview of net worth, market conditions, retirement readiness |
| ⚙️ Configuration | All personal, financial, and account settings |
| 💼 Portfolio Hub | Holdings, performance analytics, rebalancing, brokerage sync |
| 🗺️ Strategy | Year-by-year 7-stage withdrawal plan |
| 🎲 Monte Carlo | Probabilistic simulation |
| 🎯 Advanced Strategies | BETR Roth conversion, bucket strategy, SS optimisation |
| 🏛️ Estate Planning | Beneficiary plans, estate tax, charitable giving |
| 📋 Scenario Planning | Side-by-side what-if comparisons |
| 📄 Reports | Exportable summaries |
| 🔧 Admin / Tax Data | Update tax brackets, IRMAA tables, RMD factors |

---

## 2. Configuration Page

All planning assumptions live here. Changes are written to `retirement_config.json`.

### Personal Info tab

| Field | Description |
|---|---|
| Person 1 / Person 2 name | Display names used throughout the app |
| Birth dates | Used to compute current age automatically |
| Retirement ages | When each person plans to retire |
| Life expectancy | Planning horizon (typically 90–100) |
| Filing status | Single, Married Filing Jointly, etc. |
| State | Two-letter code; used for state income tax calculations |

### Financial Assumptions tab

| Field | Description |
|---|---|
| Annual expenses | Base living expenses in today's dollars |
| Expense growth rate | Inflation rate applied to expenses (e.g. 0.03 = 3%) |
| Expected return rate | Blended portfolio return assumption |
| Cash buffer (retirement) | Years of expenses to keep liquid in retirement |
| Cash buffer (accumulation) | Months of wages to keep in cash during working years (3–24) |
| Traditional 401k % | Pre-tax contribution rate; reduces AGI |
| Roth 401k / IRA % | After-tax Roth contribution rate |
| Brokerage % | After-tax taxable contribution rate |

### Healthcare tab

| Field | Description |
|---|---|
| ACA monthly premium | Health insurance cost before retirement / Medicare |
| ACA coverage ages | Start and end ages for ACA coverage |
| Medicare start age | Default 65; adjust if using COBRA or other coverage |

### Social Security tab

| Field | Description |
|---|---|
| Person 1 / 2 benefit start age | Claiming age (62–70) |
| Annual benefit amount | Estimated benefit at the chosen claiming age |

> **Tip:** Pull your benefit estimates from the SSA *my Social Security* portal at ssa.gov, or use the `generate_ssi_schedule.py` utility.

### Tax Strategy tab

| Field | Description |
|---|---|
| Roth conversion amount | Annual conversion target (overridden by BETR in the strategy engine) |
| Roth conversion max tax rate | Cap the marginal rate used when BETR evaluates conversions |
| DAF disbursement rate | Annual percentage of Donor Advised Fund to distribute |

### Portfolio Data tab

- Define account names and types (401k, Roth IRA, Traditional IRA, Taxable, HSA, etc.)
- Enter holdings by month/year, account, symbol, sector, quantity, and purchase price
- Load from or save to `portfolio_data_truth.csv` (auto-timestamped backups are created)
- Requires at least two months of data for the strategy engine to function

### Advanced tab

- **Save All Changes** — persist the current form state to `retirement_config.json`
- **Reset to Defaults** — restore the shipped defaults
- **Reload from File** — discard in-memory changes and reload from disk
- **Export Configuration** — download a JSON file

---

## 3. Dashboard

The Dashboard is the home page. It shows a summary of your financial picture and the current market regime.

### Summary Cards

| Card | What it shows |
|---|---|
| Total Net Worth | Sum of all account balances |
| Retirement Readiness | Score (0–100) based on projected coverage of expenses |
| Years to Retirement | Calculated from the earlier of Person 1 / Person 2 retirement age |
| Projected Retirement Income | Estimated annual income at retirement |

### Net Worth Chart

A year-by-year projection of total net worth through life expectancy.  
The shaded band shows 25th–75th percentile outcomes from the Monte Carlo engine.

### Market Forecast Tabs

Three independent tabs — **Short-Term**, **Intermediate**, and **Long-Term** — each showing EMA-based market condition analysis for the S&P 500 (SPY).

Each tab displays four metrics:

| Metric | Meaning |
|---|---|
| Market Condition | Headline label e.g. `🟢 Bull (Consolidating)` |
| Momentum Phase | Same combined label used by the recommendations engine |
| Tactical Adjustment | Suggested change to equity allocation (percentage points) |
| Confidence Score | Strength of the EMA slopes (0–100%) |

Expand **Detailed Analysis** to see raw EMA values, slopes (% per period), and a plain-language guidance statement.

→ See **[Section 11a](#11a-dashboard-three-timeframe-ema-regime-system)** for the complete indicator reference tables.

---

## 4. Portfolio Hub

Five tabs covering every aspect of portfolio management.

### Tab 1: Overview

- Total portfolio value, asset allocation breakdown, account-by-account listing
- Owner attribution (Person 1, Person 2, Joint)
- **Short-Term Market Forecast** card showing the EventHorizonIQ stress index
- Asset allocation donut chart

→ See **[Section 11b](#11b-portfolio-market-stress-indicator)** for the stress indicator threshold table.

### Tab 2: Holdings Management

An interactive table of all your accounts and securities.

**Account types supported:**

| Type | Tax treatment |
|---|---|
| 401k / 403b | Pre-tax; RMDs at 73 |
| Traditional IRA | Pre-tax; RMDs at 73 |
| Roth IRA | After-tax; no RMDs |
| Roth 401k | After-tax; RMDs at 73 (roll to Roth IRA to avoid) |
| Taxable Brokerage | After-tax; capital gains on sale |
| HSA | Triple-tax-advantaged; healthcare withdrawals tax-free |
| 529 | Education savings; tax-free for qualified expenses |
| Cash / Savings | No investment return assumption |

**Market Indicator column** — each security displays a condition badge calculated from its 10-week and 50-week moving averages.

→ See **[Section 11c](#11c-portfolio-holdings-per-security-indicators)** for the indicator table.

**Import / Export:**
- Import holdings from CSV (drag-and-drop or file picker)
- Export current holdings to CSV
- Backup is created automatically before every save

### Tab 3: Performance & Analytics

| Metric | Description |
|---|---|
| Total Return (TWR) | Time-weighted return removes contribution/withdrawal distortion |
| Annualized Return | Geometric annualization of TWR |
| Sharpe Ratio | Risk-adjusted return (excess return / standard deviation) |
| Max Drawdown | Largest peak-to-trough decline |
| Volatility | Annualized standard deviation of returns |
| Beta | Sensitivity to S&P 500 movements |
| Value at Risk (VaR) | Estimated worst-case loss at 95% confidence |

Available time periods: YTD, 1-year, 3-year, 5-year, since inception, custom range.

### Tab 4: Optimization (Rebalancing)

Shows the gap between current allocation and your target allocation, then recommends specific buy/sell actions.

| Column | Meaning |
|---|---|
| Current % | Actual weight in portfolio |
| Target % | Your stated target (set in Configuration) |
| Drift | Difference (positive = overweight) |
| Action | Buy / Sell recommendation with dollar amount |
| Est. Tax Impact | Estimated capital gains triggered if sold from taxable account |

Options to **minimise tax impact** (harvest losses first, sell highest-basis lots) or **minimise deviation** from target regardless of tax cost.

### Tab 5: Connections (SnapTrade Brokerage Sync)

Securely connect your brokerage accounts for automatic portfolio synchronisation.

**Supported institutions:** Charles Schwab, Fidelity, Vanguard, TD Ameritrade, E*TRADE, Merrill Edge, Interactive Brokers, Robinhood, 401k providers, and 12,000+ others.

**Setup steps:**
1. Create a free account at [snaptrade.com](https://snaptrade.com)
2. Obtain your Client ID and Consumer Key from the SnapTrade dashboard
3. Generate an encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
4. Add all three to `.env`:
   ```
   SNAPTRADE_CLIENT_ID=...
   SNAPTRADE_CONSUMER_KEY=...
   ENCRYPTION_KEY=...
   ```
5. Click **Connect Brokerage** in the Connections tab and complete OAuth
6. Click **Sync Now** to pull current balances and holdings

**Security model:**
- Read-only API access — no trades can be placed
- Credentials are stored locally in AES-256 encrypted form
- No data is uploaded to any external server

---

## 5. Strategy Page

The Strategy engine produces a year-by-year plan from today through life expectancy.

### 7-Stage Life-Cycle Model

| Stage | Typical ages | Primary focus |
|---|---|---|
| 1 — Accumulation | Working years | Maximise contributions, Roth conversions when bracket is low |
| 2 — Pre-Retirement Prep | Last 2–5 working years | Begin repositioning; reduce equity risk; finalise SS timing |
| 3 — Early Retirement | Retire → age 59½ | Draw taxable accounts; execute Roth conversion ladder; manage ACA subsidies |
| 4 — Medicare Bridge | 59½ → Medicare start | Penalty-free IRA access; continued conversions; IRMAA awareness |
| 5 — Social Security Bridge | Medicare → SS start | Coordinate SS claiming; spousal benefit; tax-efficient withdrawals |
| 6 — RMD Management | 73+ | Required Minimum Distributions; QCDs; IRMAA management |
| 7 — Surviving Spouse | After first death | Re-optimise single-filer brackets; survivor SS benefit; estate planning |

### Output Columns (one row per year)

| Column | Description |
|---|---|
| Year / Age | Calendar year and Person 1 age |
| Stage | Life stage number and name |
| Gross Income | All taxable income before deductions |
| Federal Tax | Computed federal income tax |
| State Tax | Computed state income tax |
| Net Expenses | After-tax living expenses |
| Roth Conversion | Amount converted to Roth |
| Withdrawals | Total drawn from investment accounts |
| SS Income | Social Security benefit received |
| Portfolio End | Total portfolio value at year end |

### Withdrawal Sequencing

The default sequence minimises lifetime taxes:

1. **Taxable brokerage** — draw first to control capital gains; cost basis step-up on death
2. **Traditional / pre-tax accounts** — draw next; fills lower brackets before RMDs force withdrawals
3. **Roth accounts** — draw last; tax-free; no RMDs; ideal legacy assets

BETR Roth conversions run opportunistically throughout to fill the current bracket without crossing IRMAA or ACA cliffs.

---

## 6. Monte Carlo Simulation

Probabilistic analysis using 10,000 independent scenarios.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| Scenarios | 10,000 | Number of independent simulations |
| Equity return (mean) | 7% | Annual real equity return |
| Equity return (std dev) | 15% | Volatility of annual equity returns |
| Bond return (mean) | 3% | Annual real bond return |
| Inflation rate | 3% | Expense growth |
| Sequence risk | On | Randomly sample historical return sequences |

### Output

| Metric | Description |
|---|---|
| Success probability | % of scenarios where portfolio survives to life expectancy |
| Median ending value | 50th percentile portfolio value at death |
| 10th / 25th / 75th / 90th percentile | Fan chart band values by year |
| Failure year distribution | Histogram of when plans run out of money |

### Interpreting Results

- **≥ 90% success** — plan is robust; small changes have little impact
- **75–90% success** — solid plan; modest spending flexibility recommended
- **60–75% success** — review spending or asset allocation; some risk
- **< 60% success** — significant changes needed; consult a financial planner

A success rate of 100% may indicate you are under-spending and leaving unnecessary legacy.

---

## 7. Advanced Strategies

### BETR Roth Conversion

**BETR** (Bracket-Efficient Tax-Aware Roth conversion) evaluates whether a Roth conversion dollar is worth doing *today* versus paying tax on it later.

The algorithm considers:
- Your current marginal federal tax rate
- Expected future marginal rate (driven by RMDs, Social Security, investment income)
- The tax cost of the conversion today (including state tax)
- The tax cost of leaving it in the traditional account and withdrawing later
- IRMAA premium surcharges triggered at AGI thresholds
- ACA premium tax credit phase-outs

**When BETR recommends a conversion:**
- Current marginal rate is below expected future rate
- IRMAA cliff is not crossed by the conversion amount
- ACA subsidy is not clawed back by the conversion amount
- Multi-year RMDs project to push AGI into a higher bracket

**When BETR does not recommend a conversion:**
- Current rate is higher than expected future rate
- Conversion would cross a sharp IRMAA bracket boundary
- ACA premium tax credit would be lost

→ Full details in the [BETR Guide](user/BETR_GUIDE.md).

### Bucket Strategy

The three-bucket framework insulates current spending from short-term market volatility.

| Bucket | Time horizon | Typical allocation | Purpose |
|---|---|---|---|
| Bucket 1 — Safety | Years 1–2 | 100% cash / money market | Immediate liquidity; never needs to be sold in a downturn |
| Bucket 2 — Bridge | Years 3–10 | Graduated 10%→80% stocks | Moderate growth; replenishes Bucket 1 each year |
| Bucket 3 — Growth | Years 11+ | 100% equities | Long-term wealth preservation; feeds Bucket 2 over time |

**Replenishment rules:**
1. At each year-end, top up Bucket 1 to 2 years of expenses from Bucket 2
2. If market is up, replenish Bucket 2 from Bucket 3
3. If market is down, delay Bucket 3 drawdown; draw from Bucket 2 buffer instead

→ Full details in the [Bucket Strategy Guide](user/BUCKET_STRATEGY_GUIDE.md).

### Tax-Loss Harvesting

Identifies securities in the taxable brokerage that have unrealised losses, then:
1. Recommends selling the loss position to realise the tax deduction
2. Suggests a *substantially different* replacement security to maintain market exposure (wash-sale compliance)
3. Estimates the net tax alpha (tax saved minus any bid/ask and transaction costs)

### Social Security Optimisation

| Strategy | Description |
|---|---|
| Delay to 70 | Each year of delay past FRA adds ~8% to the base benefit |
| Claim early at 62 | Reduced benefit but more total years of payments |
| Spousal coordination | Lower-earner claims early; higher-earner delays to maximise survivor benefit |
| Breakeven analysis | Age at which cumulative delayed benefit exceeds cumulative early benefit |

→ Full details in the [Social Security Optimisation Guide](user/SS_OPTIMIZATION_GUIDE.md).

---

## 8. Estate Planning

| Feature | Description |
|---|---|
| Beneficiary designations | Track primary and contingent beneficiaries per account |
| Inherited IRA rules | 10-year rule for non-spouse beneficiaries; stretch IRA for eligible |
| Estate tax projection | Federal and state estate tax estimates by year |
| Step-up in basis | Models the tax reset at death for taxable accounts |
| Charitable giving | DAF contributions, QCDs, charitable remainder trust modelling |
| Generation-skipping | Model direct transfers to grandchildren |

---

## 9. Scenario Planning

Create and compare up to five independent planning scenarios simultaneously.

**Common use cases:**
- Retire at 60 vs 65 vs 67
- Spend $80k/year vs $100k/year
- Claim Social Security at 62 vs 67 vs 70
- Move to a no-income-tax state vs staying put

Each scenario runs the full strategy engine and Monte Carlo independently. A side-by-side comparison table shows success probability, ending wealth, lifetime taxes paid, and peak IRMAA exposure.

---

## 10. Reports

The Reports page generates exportable summaries:

| Report | Content |
|---|---|
| Net Worth Statement | Snapshot of all accounts at a selected date |
| Income Projection | Year-by-year income by source through life expectancy |
| Tax Liability Forecast | Federal + state tax by year with effective rate |
| Withdrawal Schedule | Account drawdown order and amounts by year |
| Roth Conversion Summary | Recommended conversions by year with BETR rationale |
| Social Security Analysis | Benefit estimates and claiming strategy comparison |

---

## 11. Market Indicators — Reference Tables

### 11a. Dashboard: Three-Timeframe EMA Regime System

The Dashboard shows three independent assessments of the S&P 500 (SPY) using exponential moving averages (EMAs). Each timeframe uses two EMAs: a long one to define the **regime** and a short one to define the **sub-phase**.

#### EMA Periods by Timeframe

| Timeframe | Long EMA (regime) | Short EMA (sub-phase) |
|---|---|---|
| Short-Term | 50-day | 10-day |
| Intermediate | 50-week | 10-week |
| Long-Term | 18-month | 8-month |

#### Slope Thresholds

| Classification | Slope per period |
|---|---|
| Positive ↑ | > +0.1% |
| Neutral → | −0.1% to +0.1% |
| Negative ↓ | < −0.1% |

*(Long-Term uses ±0.25% per month)*

#### The 9 Market States — What They Mean and What to Do

**Short-Term (10-day / 50-day EMA)**

| Long (50d) | Short (10d) | Label | When it switches | Action |
|---|---|---|---|---|
| Positive ↑ | Positive ↑ | 🟢 Bull (Accumulation) | Long EMA turns up AND short EMA turns up | Maintain or add exposure — most favourable state |
| Positive ↑ | Neutral → | 🟢 Bull (Consolidating) | Short EMA slope drops below +0.1% | Hold; healthy pause; wait for momentum to resume |
| Positive ↑ | Negative ↓ | 🟢 Bull (Distribution) | Short EMA slope drops below −0.1% | Tighten stop-losses; avoid adding new positions |
| Neutral → | Positive ↑ | ⚪ Neutral (Accumulation) | Long EMA stalls; short EMA still rising | Watch for breakout; wait for long EMA confirmation |
| Neutral → | Neutral → | ⚪ Neutral (Consolidating) | Both EMAs flatten to ±0.1% | Hold; no directional edge |
| Neutral → | Negative ↓ | ⚪ Neutral (Distribution) | Long EMA flat; short EMA turns down | Reduce exposure; risk of transition to Bear |
| Negative ↓ | Positive ↑ | 🔴 Bear (Accumulation) | Long EMA still negative; short EMA bounces up | Relief rally only — do NOT add; wait for long EMA |
| Negative ↓ | Neutral → | 🔴 Bear (Consolidating) | Long EMA negative; short EMA flattens | Downtrend pausing; maintain defensive posture |
| Negative ↓ | Negative ↓ | 🔴 Bear (Distribution) | Both EMAs falling | Full defensive; higher cash; avoid new longs |

**Intermediate (10-week / 50-week EMA)**

| Long (50w) | Short (10w) | Label | When it switches | Action |
|---|---|---|---|---|
| Positive ↑ | Positive ↑ | 🟢 Bull (Accumulation) | Both weekly EMAs positively sloped | Maintain or increase allocation |
| Positive ↑ | Neutral → | 🟢 Bull (Consolidating) | 10-week slope flattens | Hold; healthy pause |
| Positive ↑ | Negative ↓ | 🟢 Bull (Distribution) | 10-week EMA turns down | Avoid adding; monitor for regime transition |
| Neutral → | Positive ↑ | ⚪ Neutral (Accumulation) | 50-week stalls; 10-week recovers | Hold; wait for 50-week confirmation |
| Neutral → | Neutral → | ⚪ Neutral (Consolidating) | Both weekly EMAs flat | Maintain; no tactical edge |
| Neutral → | Negative ↓ | ⚪ Neutral (Distribution) | 50-week flat; 10-week falls | Reduce ~10%; risk of bear transition |
| Negative ↓ | Positive ↑ | 🔴 Bear (Accumulation) | 50-week negative; 10-week bounces | Relief rally; wait for confirmation |
| Negative ↓ | Neutral → | 🔴 Bear (Consolidating) | 50-week negative; 10-week flattens | Defensive; no new longs |
| Negative ↓ | Negative ↓ | 🔴 Bear (Distribution) | Both weekly EMAs falling | Reduce ~20%; capital preservation |

**Long-Term (8-month / 18-month EMA)**

| Long (18m) | Short (8m) | Label | When it switches | Action |
|---|---|---|---|---|
| Positive ↑ | Positive ↑ | 🟢 Bull (Accumulation) | Both monthly EMAs rising > +0.25%/mo | Full equity exposure; add to allocation |
| Positive ↑ | Neutral → | 🟢 Bull (Consolidating) | 8-month slope drops to ±0.25% | Hold; avoid major changes |
| Positive ↑ | Negative ↓ | 🟢 Bull (Distribution) | 8-month slope turns negative | Review overweights; monitor for regime change |
| Neutral → | Positive ↑ | ⚪ Neutral (Accumulation) | 18-month stalls; 8-month recovers | Early bull possible; wait for 18-month confirmation |
| Neutral → | Neutral → | ⚪ Neutral (Consolidating) | Both monthly EMAs flat | Maintain allocation; avoid strategic shifts |
| Neutral → | Negative ↓ | ⚪ Neutral (Distribution) | 18-month flat; 8-month falls | Consider reducing exposure; build cash |
| Negative ↓ | Positive ↑ | 🔴 Bear (Accumulation) | 18-month negative; 8-month bounces | Recovery attempt; wait for 18-month confirmation |
| Negative ↓ | Neutral → | 🔴 Bear (Consolidating) | 18-month negative; 8-month flattens | Defensive posture; higher cash |
| Negative ↓ | Negative ↓ | 🔴 Bear (Distribution) | Both monthly EMAs falling | Reduce 10–20%; watch for value after 6+ months |

#### Suggested Tactical Allocation Adjustments

| Timeframe | Regime | Default equity adjustment |
|---|---|---|
| Any | Bull | 0% (maintain target allocation) |
| Any | Neutral | 0% (no directional edge) |
| Short-Term | Bear | −8% |
| Intermediate | Bear | −20% |
| Long-Term | Bear | −15% |

The sub-phase provides nuance: Bear (Distribution) that has persisted multiple periods strengthens the case for the full reduction; Bear (Accumulation) in early stages may warrant waiting.

#### Key Rules

1. **Long EMA is the regime anchor.** Never override the regime based on the short EMA alone. A short-term bounce inside a Bear is still a Bear.
2. **Distribution ≠ exit.** Bull (Distribution) means momentum is fading, not that the uptrend has ended. Tighten controls and watch the long EMA slope.
3. **Accumulation in Bear ≠ buy.** Wait for the long EMA slope to turn positive before adding exposure.
4. **Neutral means wait.** Neutral (Consolidating) has no directional edge.
5. **Use all three timeframes.** Short-Term signals are noisy. Intermediate and Long-Term carry more weight for strategic decisions.
6. **Confidence score matters.** A score below 20% means the slopes are barely outside the neutral band — treat the signal cautiously.

---

### 11b. Portfolio Market Stress Indicator

Located in **Portfolio Hub → Overview → Short-Term Market Forecast**.  
Data from the EventHorizonIQ Stress Index, aggregating 55+ market sensors. Cached for 15 minutes.

#### Threshold Table

| Score | Status | Regime label | When it switches | Actions |
|---|---|---|---|---|
| 0–49 | 🟢 Normal | NEUTRAL | Stress index rises above 0 from a quiet market | Continue normal strategy; execute planned rebalancing; check weekly |
| 50–69 | 🟡 Warning | ELEVATED | Stress index crosses 50 | Review allocation and risk; prepare hedge strategies; identify put options / inverse positions; check daily |
| 70–100 | 🔴 Critical | CRITICAL | Stress index crosses 70 | Activate hedges (puts, inverse ETFs); reduce equity to defensive levels; raise cash to 15–20%; set stop-losses; check daily until < 70 |

#### Sensor Breakdown (expandable detail)

| Sensor state | Colour | Meaning |
|---|---|---|
| Severe | 🔴 | Extreme stress signal from this sensor |
| Elevated | 🟠 | Above-average stress from this sensor |
| Rising | 🟡 | Stress trending upward from this sensor |
| Neutral | ⚪ | No significant signal |
| Stable | 🟢 | Market condition normal for this sensor |

#### Monitoring Frequency

| Stress level | Recommended check frequency |
|---|---|
| < 50 (Normal) | Weekly |
| 50–70 (Warning) | Daily |
| > 70 (Critical) | Multiple times per day until resolved |

---

### 11c. Portfolio Holdings: Per-Security Indicators

Displayed in the **Market Indicator** column of the Holdings tab.  
Calculated from 10-week and 50-week moving averages using weekly closing prices from yfinance. Cached for 1 hour per symbol.

#### Condition Table

| Condition | Badge | Short MA (10w) | Long MA (50w) | Price position | When it switches | Recommended action |
|---|---|---|---|---|---|---|
| Strong Buy | 🚀 | Trending up | Trending up | Above both MAs | Both MAs positive and price breaks above | Consider adding to position |
| Buy | 📈 | Trending up | Trending up | Near or above MAs | Both MAs slope turn positive | Favourable; hold or accumulate |
| Hold | ➖ | Mixed / neutral | Mixed / neutral | Around MAs | Either MA goes flat or signals conflict | Maintain current position; wait for clarity |
| Caution | ⚠️ | Trending down | Trending up | Below short MA | Short MA slope turns negative while long MA still positive | Monitor closely; consider tightening stops or taking partial profits |
| Sell | 📉 | Trending down | Trending down | Below both MAs | Long MA slope also turns negative | Consider reducing or exiting position |
| Unknown | ❓ | N/A | N/A | N/A | Fewer than 50 weeks of data, or data fetch failed | Verify ticker symbol; check internet connection |

#### Special Cases

| Symbol pattern | Condition always shown | Reason |
|---|---|---|
| `MF:CASH`, `CASH` | 💵 Hold | Cash has no trend data |
| Any ETF / mutual fund with < 50 weeks of history | ❓ Unknown | Insufficient data for 50-week MA |

#### Slope Threshold

The 10-week and 50-week MAs are evaluated over a 4-week lookback period.  
A slope is classified as up/down/neutral using a **0.05% per week** threshold.

---

## 12. Key Data Files

| File | Required | Description |
|---|---|---|
| `retirement_config.json` | Yes | All personal and financial settings; edited via Configuration page |
| `portfolio_data_truth.csv` | Yes | Your actual holdings; the source of truth for all account data |
| `standard.csv` | Yes | Federal income tax brackets by year |
| `cap_gains.csv` | Yes | Long-term and short-term capital gains rates |
| `irmaa.csv` | Yes | Medicare Part B and D IRMAA surcharge thresholds |
| `atm.csv` | Yes | Alternative Minimum Tax parameters |
| `rmd.csv` | Yes | IRS Uniform Lifetime Table (RMD divisors) |
| `ssincome.csv` | Yes | Your Social Security benefit estimates by claiming age |
| `income_rates.csv` | Yes | State income tax rates |
| `ira_limits.csv` | Reference | Annual IRA contribution limits |
| `.env` | Optional | API keys for SnapTrade brokerage sync |

---

## 13. Troubleshooting

### App won't start

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` with the virtual environment active |
| Port 8501 already in use | `streamlit run planning_app.py --server.port 8502` |
| `python3: command not found` | Install Python 3.9+ from python.org |

### Data not loading

| Symptom | Fix |
|---|---|
| "FileNotFoundError: portfolio_data_truth.csv" | `cp portfolio_data_truth.sample.csv portfolio_data_truth.csv` |
| CSV format error | Check that headers match `Account,Type,Owner,Balance,Basis,Contribution,Annual_Return`; remove currency symbols from numeric columns; save as UTF-8 |
| Configuration not saving | Ensure the app has write permission to the project directory |

### Market indicators not showing

| Symptom | Fix |
|---|---|
| Market forecast tab shows nothing | Check internet connection; yfinance requires network access |
| Holdings indicator column shows all Unknown | Same as above; or ticker symbols are not valid US exchange tickers |
| Stress indicator shows "Unable to fetch" | EventHorizonIQ API is unreachable; wait and reload; data is cached 15 minutes |

### SnapTrade / brokerage sync issues

| Symptom | Fix |
|---|---|
| "Encryption key not found" | Generate key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and add to `.env` as `ENCRYPTION_KEY=` |
| "SnapTrade credentials not found" | Verify `SNAPTRADE_CLIENT_ID` and `SNAPTRADE_CONSUMER_KEY` are in `.env` |
| "Failed to generate auth link" | Confirm API credentials are correct in the SnapTrade dashboard; try Reset & Reconnect |
| "No holdings found to sync" | Complete the full OAuth flow in the browser popup; verify the brokerage account has holdings |

### Strategy / Monte Carlo results look wrong

| Symptom | Fix |
|---|---|
| Net worth drops to zero immediately | Check that `portfolio_data_truth.csv` has positive balances |
| Retirement readiness = 0 | Verify birth dates and retirement ages are set correctly in Configuration |
| Monte Carlo always fails | Annual expenses may exceed sustainable withdrawal from portfolio; review spending assumptions |

---

*For detailed feature-specific troubleshooting, see the individual guide for each feature in the [User Guides index](user/README.md).*

---

*Made with Bob*
