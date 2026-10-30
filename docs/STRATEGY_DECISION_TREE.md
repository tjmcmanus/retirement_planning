# Strategy Model Decision Tree

How the withdrawal strategy engine decides what to do each year. Source of truth:
[`strategy.py`](../strategy.py) (`WithdrawalStrategyEngine`) and
[`strategy_core/stages/`](../strategy_core/stages).

Stages 3 and 4 were read in detail. For Stages 1, 2, 5 and 7 only the main decisions and log
labels were reviewed, so treat their rows in section 6 as a summary.

## 1. Which stage applies in a given year

Stages are tested in the order 7, 1, 2, 3, 4, 5, 6. The first whose `applies()` returns True wins;
Stage 6 is the default.

```mermaid
flowchart TD
    Y["Year N"] --> S7{"Surviving-spouse mode on,<br/>date of death set,<br/>and N > death year?"}
    S7 -- yes --> ST7["Stage 7: Surviving Spouse"]
    S7 -- no --> W{"Household has wages?"}
    W -- yes --> PREP{"0 <= latest retirement year - N <= 10?"}
    PREP -- no --> ST1["Stage 1: Accumulation"]
    PREP -- yes --> ST2["Stage 2: Prep for Retirement"]
    W -- no --> RMD{"Either spouse at or past RMD age?<br/>73 if born 1951-59, 75 if 1960+"}
    RMD -- yes --> ST6["Stage 6: RMD"]
    RMD -- no --> SS{"Social Security started?"}
    SS -- yes --> ST5["Stage 5: Social Security"]
    SS -- no --> AGE{"Either spouse 65+?"}
    AGE -- yes --> ST4["Stage 4: Medicare"]
    AGE -- no --> ST3["Stage 3: Early Retirement"]
```

Stage 1 also applies when no retirement year is configured.

## 2. What the engine does each year

Loop: `calculate_multi_year_strategy` in [`strategy.py`](../strategy.py).

```mermaid
flowchart TD
    A["Inflate wages, pension, rental, interest, dividends<br/>(retirement-year wages are prorated)"] --> B["Compute SS per person from claiming age"]
    B --> C["Derive has_wages and has_ss"]
    C --> D["Look up MAGI from 2 years ago for IRMAA"]
    D --> E["Pick the stage and its max conversion rate"]
    E --> F["stage.calculate_strategy"]
    F --> G["Update DAF carryforward<br/>IRC 170: 30% of AGI limit"]
    G --> H["Carry balances forward and grow them"]
    H --> I["Next year expenses = age-adjusted base x inflation"]
    I --> J{"More years?"}
    J -- yes --> A
    J -- no --> K["optimize_rmd_lookback"]
    K --> L["_strategies_to_dataframe"]
```

`optimize_rmd_lookback` runs once after all years. If Stage 6 RMDs would exceed expenses it adds
extra Roth conversions in the earlier pre-RMD years.

## 3. Inside Stage 3

`Stage3EarlyRetirement.calculate_strategy` in
[`stage3_early_retirement.py`](../strategy_core/stages/stage3_early_retirement.py). Stages 4 and 5
follow the same shape.

The **pre-fund amount** is the sum of two sources, capped at Traditional minus reserved buffer needs:

1. **DAF window** — `charitable_giving.daf_trad_prefund_enabled/amount/start_year/end_year`.
2. **Year schedule** — `tax_strategy.trad_prefund_schedule`, a list of `{year, amount}` rows. It needs
   no DAF and is the place to seed a Direct Indexing portfolio.

```mermaid
flowchart TD
    A["Compute ACA premium and total healthcare cost"] --> B["Estimate Traditional needed for<br/>future buffers (lookahead)"]
    B --> C{"Pre-fund amount > 0?<br/>(DAF window + year schedule)"}

    C -- yes --> P1["PRE-FUND PATH<br/>January plan covers the spending shortfall"]
    P1 --> P2["Move Traditional to Brokerage<br/>as a zero-gain lot"]
    P2 --> P3["Fill cash deficit:<br/>Brokerage (lowest-gain lots) first,<br/>then Traditional as fallback"]
    P3 --> P4["Make the DAF contribution, if one is due"]
    P4 --> P5["Roth conversion is suppressed"]

    C -- no --> N1["PHASE 1: January bracket-fill<br/>Shortfall = expenses + ACA - cash on Jan 1<br/>Withdraw from Traditional"]
    N1 --> N2["PHASE 2: Roth conversion<br/>available = Traditional - future needs - spending withdrawal"]
    N2 --> N3{"BETR optimizer succeeds?"}
    N3 -- yes --> N4["Convert up to the stage cap"]
    N3 -- no --> N5["Fall back to bracket-fill conversion"]
    N4 --> N6
    N5 --> N6{"DAF gift this year<br/>with tax_excess > 0?"}
    N6 -- yes --> N7["Raise conversion by<br/>min(tax_excess, available - conversion)"]
    N6 -- no --> N8
    N7 --> N8["Apply Traditional to Cash withdrawal,<br/>then DAF (highest-gain lots donated first)"]

    P5 --> R
    N8 --> R["Preliminary tax estimate, then rebalance_accounts"]
    R --> S["Raise ordinary income to at least<br/>90% of the standard deduction"]
    S --> T["Final taxes: AGI, federal, state,<br/>DAF deduction with 30% limit and carryforward"]
    T --> U["Apply growth, deduct the annual DAF grant,<br/>record transactions"]
```

The pre-fund path is only taken in **Stage 3** years. In a Stage 4+ year the pre-fund settings are ignored.

## 4. When a DAF gift happens

`_calculate_daf_for_year` in [`strategy.py`](../strategy.py).

```mermaid
flowchart TD
    A{"has_daf and annual giving > 0?"} -- no --> X["No gift"]
    A -- yes --> B{"Year in contribution window?<br/>start to min(end, eldest birth year + 70)"}
    B -- no --> X
    B -- yes --> C{"(year - start) % bundle interval == 0?"}
    C -- no --> X
    C -- yes --> D{"First window year and<br/>initial contribution > 0?"}
    D -- yes --> E["Amount = initial contribution"]
    D -- no --> F["Amount = annual contribution<br/>(or the bundle override if set)"]
    E --> G{"Amount <= brokerage balance?"}
    F --> G
    G -- no --> X
    G -- yes --> H["Gift made.<br/>tax_excess = amount + min(10k, state + property tax) - std deduction"]
```

Default bundle interval: `max(2, min(floor(std_ded / annual_giving) + 1, 5))` years.
`tax_strategy.daf_bundle_interval_years` overrides it.

## 5. How cash gets refilled

`rebalance_accounts` in [`strategy.py`](../strategy.py).

```mermaid
flowchart TD
    A["Deduct expenses, tax, IRMAA, ACA<br/>and medical costs from cash"] --> B["cash target = expenses x years in cash (default 4)<br/>brokerage target = expenses x trigger multiplier (default 1)"]
    B --> C{"Cash short AND brokerage can't cover<br/>the deficit and keep its own buffer?"}
    C -- no --> D["NORMAL routing"]
    D --> D1["Brokerage to Cash"]
    D1 --> D2["Traditional to Brokerage<br/>to rebuild the brokerage buffer"]
    C -- yes --> E["OPTIMISED routing"]
    E --> E1["Brokerage to Cash (partial)"]
    E1 --> E2["Traditional to Cash<br/>(capped at 15% of Traditional if 59.5+)"]
    E2 --> E3["Roth to Cash<br/>(capped at 10% of Roth if 59.5+)"]
    E3 --> E4["Rebuild brokerage buffer if still below target"]
    D2 --> F["Execute the Roth conversion"]
    E4 --> F
```

## 6. How the other stages differ

| Stage | What drives it |
|---|---|
| 1 Accumulation | Contribution routing and an accumulation Roth conversion. |
| 2 Prep | Roth 401k vs Traditional 401k, Cash→Roth contributions, backdoor vs direct Roth IRA, a BETR conversion, and DAF under the §170 30% limit. |
| 3 Early Retirement | Section 3: the pre-fund path or the normal January plan, then a BETR conversion with a DAF boost. |
| 4 Medicare | Same shape as Stage 3, but the conversion is IRMAA-aware (`irmaa_headroom`) and the DAF boost is capped by that headroom. |
| 5 Social Security | January spending, SS income, an IRMAA assessment, a Roth conversion with an RMD outlook, and the DAF boost. |
| 6 RMD | RMDs computed per person and sent to Brokerage first. Withdrawal need = expenses + healthcare − SS − RMD. LTCG harvesting up to the 15% bracket, and an RMD-limited conversion of `min(conversion_room, irmaa_headroom, traditional − rmd)`. IRMAA uses MAGI from two years earlier. |
| 7 Surviving Spouse | Single-filer brackets and survivor benefits, conservative LTCG harvesting up to the 15% bracket, and the same RMD, DAF, IRMAA and Roth pieces. |

## 7. Configuration that controls the tree

| Setting | Where (web app) | Effect |
|---|---|---|
| `tax_strategy.stage_N_max_conversion_rate` | Settings → Tax Strategy | Bracket ceiling for the Roth conversion in stage N. |
| `tax_strategy.use_january_bracket_fill_strategy`, `savings_safety_reserve` | Settings → Tax Strategy | January plan and the cash floor for mid-year top-ups. |
| `tax_strategy.trad_prefund_schedule` | Settings → Tax Strategy → "Traditional → Brokerage pre-fund by year" | `{year, amount}` rows. Moves $amount Traditional → Brokerage in that Stage 3 year (e.g. to seed Direct Indexing). Suppresses that year's Roth conversion. |
| `charitable_giving.daf_trad_prefund_*` | Settings → Charitable Giving | Same pre-fund path, over a start–end window, to fund DAF gifts. Adds to the schedule. |
| `charitable_giving.daf_*` | Settings → Charitable Giving | DAF gift window, initial/bundled amounts. |
| `financial_assumptions.years_of_expenses_in_cash`, `brokerage_rebalance_trigger_multiplier` | Settings → Financial Assumptions | Cash and brokerage buffer targets used by `rebalance_accounts`. |

### Troubleshooting: "pre-fund never fires"

1. **Check which config file the app reads.** The containers read `/data/retirement_config.json`
   (the `retirement_data` volume), *not* the copy in the project folder. Editing the project-folder
   file has no effect on the running app. Use Settings in the web app, or the Streamlit
   Configuration page.
2. The year must be a **Stage 3** year (no wages, no SS, both spouses under 65).
3. The amount is capped at `Traditional − anticipated buffer needs`; a log line "DAF pre-fund
   skipped — insufficient Traditional balance" means that cap hit zero.
4. Open Strategy → Why these numbers? for the year: a "Traditional → Brokerage Pre-Fund" reason
   appears when it fires, and "Roth Conversion Suppressed" follows it.
