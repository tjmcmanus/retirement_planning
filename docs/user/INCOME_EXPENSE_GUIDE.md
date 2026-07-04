# Income & Expense Projection Module Guide

## Overview

[`income_expense.py`](income_expense.py:1) is the core simulation engine for the **Dashboard** tab of the retirement planning application. It projects annual income, expenses, taxes, and portfolio balances from the current year through 2051, using actual portfolio holdings loaded from [`portfolio_data_truth.csv`](portfolio_data_truth.csv) and Social Security schedules generated dynamically from [`config.py`](config.py:1).

The module is distinct from [`strategy.py`](strategy.py:1):

| Module | Purpose |
|--------|---------|
| [`income_expense.py`](income_expense.py:1) | Dashboard tab — simplified year-by-year projection using current portfolio data and SSI schedule |
| [`strategy.py`](strategy.py:1) | Strategy tab — full 6-stage life-cycle optimizer with BETR Roth conversions, IRMAA management, and ACA subsidy optimization |

---

## Architecture

```
build_income_expenses_display()          ← main entry point
│
├── _initialize_simulation_config()      ← reads config + session state + portfolio
│   ├── _read_personal_config()          ← reads names, birth years, SSI claiming age
│   └── _load_portfolio_data()           ← loads current market values from CSV
│
├── generate_ssi_schedule_from_config()  ← builds SSI schedule (ssi_calculator.py)
│
└── simulation loop (year by year)
    └── _simulate_year()                 ← per-year orchestration
        ├── _get_ssi_annual_benefit()    ← combined SSI inflow for the year
        ├── _calculate_year_distributions() ← planned dist, DAF, conversions
        ├── _calculate_rmd_and_update_trad() ← RMD + traditional account update
        ├── calculate_taxes()            ← federal tax on taxable inflows
        └── _update_accounts()           ← cash, brokerage, tax-free, DAF update
            ├── _apply_seed_once()       ← seeds opening balances exactly once
            ├── _split_conversions()     ← splits conversion between brokerage/tax-free
            └── _update_daf()            ← DAF spend-down + new contribution
```

---

## Public API

### `build_income_expenses_display()`

```python
def build_income_expenses_display() -> tuple[pd.DataFrame, pd.DataFrame]
```

Main entry point called by [`planning_app.py`](planning_app.py:1) to render the Dashboard tab.

**Returns:**
- `i_e_df` — Income/Expense DataFrame (one row per year, columns below)
- `port_draw_df` — Portfolio balance DataFrame (one row per year, columns below)

**Income/Expense DataFrame columns:**

| Column | Description |
|--------|-------------|
| `Year` | Calendar year |
| `Age` | `"person2_age/person1_age"` string (e.g., `"59/61"`) |
| `SSI Flows` | Combined annual SSI benefit (both persons × 12 months) |
| `Planned Distribution` | Planned Traditional account distribution |
| `Roth Conversions` | Roth conversion amount |
| `RMD` | Required Minimum Distribution |
| `Total Inflows` | SSI + portfolio withdrawal |
| `Taxes Owed` | Federal income tax |
| `Expenses` | Deflated annual living expenses |
| `Portfolio Withdrawal` | Amount drawn from portfolio to cover expenses + taxes |

**Portfolio DataFrame columns:**

| Column | Description |
|--------|-------------|
| `Year` | Calendar year |
| `Cash` | End-of-year cash balance |
| `Taxable` | End-of-year brokerage balance |
| `Tax Deferred` | End-of-year Traditional IRA/401k balance |
| `Tax Free` | End-of-year Roth balance |
| `Donor Advised Fund` | End-of-year DAF balance |

**Example:**
```python
from income_expense import build_income_expenses_display

i_e_df, port_df = build_income_expenses_display()
print(i_e_df[['Year', 'SSI Flows', 'Taxes Owed', 'Expenses']].head(10))
print(port_df[['Year', 'Cash', 'Taxable', 'Tax Deferred', 'Tax Free']].head(10))
```

---

## Configuration & Session State

[`_initialize_simulation_config()`](income_expense.py:370) reads all inputs once and packages them into an immutable [`SimulationConfig`](income_expense.py:323) dataclass. Inputs come from two sources:

### From `config.py` (persistent)
- Person names and birth dates
- SSI claiming age
- Portfolio account data (via `portfolio_data_truth.csv`)

### From Streamlit session state (temporary, overrides config)

| Session Key | Type | Default | Description |
|-------------|------|---------|-------------|
| `EXPENSE` | float | `50000` | Annual living expenses |
| `RATE` | float | `6.0` | Annual portfolio growth rate (%) |
| `EXPENSE_MULTIPLIER` | int | `4` | Years of expenses to hold in cash |

> **Note:** `daf_rate` (25% annual DAF spend-down) and `planned_dist_2027` ($75,000) are currently hardcoded constants in [`_initialize_simulation_config()`](income_expense.py:370). They are not user-configurable via the UI.

---

## Data Classes

### `SimulationConfig`

```python
@dataclasses.dataclass
class SimulationConfig:
    expenses: float              # Annual living expenses
    rate: float                  # Growth multiplier (e.g., 1.07 for 7%)
    daf_rate: float              # Annual DAF spend-down fraction (0.25)
    expense_multiplier: int      # Years of expenses to hold in cash
    planned_dist_2027: float     # Planned 2027 Traditional distribution
    ssi_year: int                # Year person 1 begins claiming SSI
    person1_birth_year: int
    person2_birth_year: int
    person1_name: str
    person2_name: str
    cash_in: float               # Opening cash balance from portfolio data
    brokerage: float             # Opening brokerage balance
    trad_value: float            # Opening Traditional balance
    tax_free_in: float           # Opening Roth balance
    current_year: int
    current_month: int
    end_year: int                # Simulation end year (default: 2051)
```

### `SimulationState`

Mutable per-year account balances threaded through the simulation loop:

```python
@dataclasses.dataclass
class SimulationState:
    cash: float = 0.0
    tax_free: float = 0.0
    brokerage: float = 0.0
    trad_value: float = 0.0
    daf_in: float = 0.0
```

### `YearResult`

Typed return value from [`_simulate_year()`](income_expense.py:635):

```python
class YearResult(typing.NamedTuple):
    new_state: SimulationState   # Updated account balances
    new_expenses: float          # Deflated expenses for next year
    ie_row: dict                 # Row for income/expense DataFrame
    port_row: dict               # Row for portfolio DataFrame
```

---

## Helper Functions

### `_read_personal_config(config)`

```python
def _read_personal_config(config) -> dict
```

Reads person names, birth years, and SSI claiming age from a [`ConfigManager`](config.py:80) instance. Separated from session-state reads to allow independent unit testing.

**Returns dict with keys:** `person1_name`, `person2_name`, `person1_claiming_age`, `person1_birth_year`, `person2_birth_year`

---

### `_load_portfolio_data(current_month, current_year)`

```python
def _load_portfolio_data(current_month: int, current_year: int) -> dict[str, float]
```

Loads current portfolio market values from [`portfolio_data_truth.csv`](portfolio_data_truth.csv) via [`get_networth_by_month()`](load_data.py:1). Groups holdings by account type using [`ACCOUNT_TYPE_MAPPING`](income_expense.py:31).

**Account type mapping:**

| CSV `account_type` | Dict key | Description |
|--------------------|----------|-------------|
| `Cash` | `cash_in` | Cash / money market |
| `Brokerage` | `brokerage` | Taxable brokerage |
| `Traditional` | `trad_value` | Traditional IRA / 401k |
| `Roth` | `tax_free_in` | Roth IRA / Roth 401k |

**Returns:** `{'cash_in': float, 'brokerage': float, 'trad_value': float, 'tax_free_in': float}`  
**On error:** Returns all zeros and logs the error — the simulation continues with zero opening balances.

---

### `_calculate_year_distributions(year, ssi_year, planned_dist_2027)`

```python
def _calculate_year_distributions(year: int, ssi_year: int,
                                   planned_dist_2027: float) -> tuple[float, float, float]
```

Returns `(planned_dist, daf, conversions)` for a given year using hardcoded year-specific logic:

| Year | planned_dist | daf | conversions |
|------|-------------|-----|-------------|
| 2026 | 0 | 0 | `YEAR_2026_CONVERSION` (100,000) |
| 2027 | `planned_dist_2027` | `planned_dist_2027 × 0.33` | 0 |
| 2028 – (ssi_year − 1) | 0 | 0 | `PRE_SSI_CONVERSION` (375,000) |
| ssi_year+ | 0 | 0 | 0 (BETR algorithm in strategy.py handles conversions) |

> **Note:** Roth conversions in this module are legacy/simplified values. The full BETR-validated conversion logic lives in [`strategy.py`](strategy.py:1).

**Raises:** `ValueError` if `ssi_year <= 2027`

---

### `_validate_tax_inputs(income, daf, year)`

```python
def _validate_tax_inputs(income: float, daf: float, year: int) -> tuple[float, float, int]
```

Normalizes negative income/DAF to 0 and validates the year is an integer between 1900–2100.

**Raises:** `ValueError` if year is invalid.

---

### `calculate_taxes(income, daf, year)`

```python
def calculate_taxes(income: float, daf: float, year: int) -> float
```

Calculates federal income tax on taxable inflows.

**Tax calculation pipeline:**
1. Validate inputs via [`_validate_tax_inputs()`](income_expense.py:83)
2. Load standard deduction data via [`get_std_deduction(year)`](load_data.py:1)
3. Load tax bracket data via [`get_income_tax_brackets(year)`](load_data.py:1)
4. Calculate standard deduction via [`calculate_std_deduction()`](calculations.py:1)
5. Compute AGI: `income − standard_deduction − daf`
6. Calculate tax via [`calculate_taxable_income()`](calculations.py:1)

**Returns:** Tax amount as float. Returns `0.0` on any error (errors are logged).

**Taxable inflows include:**
- 85% of SSI benefits (`SSI_TAXABLE_FRACTION = 0.85`)
- Planned Traditional distributions
- Roth conversions
- RMDs

---

### `_calculate_rmd_and_update_trad(trad_value, t_age, planned_dist, conversions, rate)`

```python
def _calculate_rmd_and_update_trad(
    trad_value: float, t_age: float,
    planned_dist: float, conversions: float,
    rate: float
) -> tuple[float, float, float, float]
```

Calculates the RMD for person 1 and updates the Traditional account balance.

**Returns:** `(rmd, planned_dist, conversions, new_trad_value)`

**RMD logic:**
- Calls [`get_rmd_value(age)`](calculations.py:1) to get the IRS life expectancy factor
- `rmd = trad_value / life_expectancy_factor`
- RMD is reduced by any planned distributions or conversions already taken
- If the account would go negative, all distributions are zeroed and the account grows at `rate`

---

### `_apply_seed_once(current, seed)`

```python
def _apply_seed_once(current: float, seed: float) -> float
```

Returns `seed` only when `current == 0.0` (first iteration), ensuring opening balances are added exactly once. Returns `0.0` on all subsequent iterations.

---

### `_update_daf(daf_in, daf, daf_rate)`

```python
def _update_daf(daf_in: float, daf: float, daf_rate: float) -> float
```

Applies the annual DAF spend-down and adds the current year's new contribution:

```
new_daf = daf_in × (1 − daf_rate) + daf
```

Default `daf_rate` is `0.25` (25% annual spend-down).

---

### `_split_conversions(conversions, brokerage, annual_expenses, taxes, expense_multiplier)`

```python
def _split_conversions(
    conversions: float, brokerage: float,
    annual_expenses: float, taxes: float,
    expense_multiplier: int
) -> tuple[float, float]
```

Splits Roth conversion proceeds between brokerage and tax-free accounts:

- **Below threshold** (`brokerage < (expenses + taxes) × expense_multiplier`): 50% to brokerage, 50% to tax-free — rebuilds the taxable buffer
- **Above threshold**: 100% to tax-free

**Returns:** `(conversions_to_brokerage, conversions_to_tax_free)`  
**Invariant:** `conversions_to_brokerage + conversions_to_tax_free == conversions`

---

### `_update_accounts(state, cfg, ...)`

```python
def _update_accounts(
    state: SimulationState, cfg: SimulationConfig,
    monthly_benefit: float, portfolio_withdrawal: float,
    planned_dist: float, conversions: float,
    rmd: float, daf: float,
    annual_expenses: float, taxes: float
) -> SimulationState
```

Computes updated cash, brokerage, and tax-free balances for one year.

**Cash update:**
```
cash_growth_rate = (rate − 1) / 3    # Cash earns ~1/3 of equity growth rate
new_cash = (cash + seed + ssi + portfolio_withdrawal − expenses − taxes) × (1 + cash_growth_rate)
```

**Brokerage update:**
```
new_brokerage = (brokerage + planned_dist + conversions_to_brokerage + rmd − daf − portfolio_withdrawal) × rate
```

**Tax-free (Roth) update:**
```
new_tax_free = (tax_free + seed + conversions_to_tax_free) × rate
```

---

### `_get_ssi_annual_benefit(year, person1_data, person2_data)`

```python
def _get_ssi_annual_benefit(
    year: int,
    person1_data: pd.DataFrame,
    person2_data: pd.DataFrame
) -> float
```

Returns the combined annual SSI benefit for both persons in `year` by looking up the pre-computed SSI schedule DataFrames (indexed by year).

**Returns:** `(person1_monthly + person2_monthly) × 12`, or `0.0` if year not in schedule.

---

### `_simulate_year(year, state, cfg, person1_data, person2_data, annual_expenses)`

```python
def _simulate_year(
    year: int, state: SimulationState, cfg: SimulationConfig,
    person1_data: pd.DataFrame, person2_data: pd.DataFrame,
    annual_expenses: float
) -> YearResult
```

Orchestrates all per-year calculations and returns a [`YearResult`](income_expense.py:619).

**Processing order:**
1. Calculate ages for both persons
2. Look up SSI annual benefit
3. Calculate planned distributions, DAF, and conversions
4. Calculate RMD and update Traditional balance
5. Calculate taxes on taxable inflows
6. Apply expense deflator (`EXPENSE_DEFLATOR = 0.993`)
7. Calculate portfolio withdrawal needed: `max(0, expenses + taxes − ssi_inflows)`
8. Update all account balances
9. Build output row dicts

---

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `YEAR_2026_CONVERSION` | `100_000` | Roth conversion amount for 2026 |
| `YEAR_2027_DAF_RATIO` | `0.33` | Fraction of 2027 distribution going to DAF |
| `PRE_SSI_CONVERSION` | `375_000` | Annual Roth conversion amount before SSI begins |
| `EXPENSE_DEFLATOR` | `0.993` | Annual real-spending reduction factor (0.7% real deflation) |
| `SSI_TAXABLE_FRACTION` | `0.85` | IRS maximum taxable fraction of SSI benefits |

---

## Integration with Other Modules

### [`ssi_calculator.py`](ssi_calculator.py:1)

The module calls [`generate_ssi_schedule_from_config(config, start_year, end_year)`](ssi_calculator.py:1) to build a complete SSI benefit schedule for both persons. This replaces the legacy CSV-based lookup.

```python
ssi_schedule = generate_ssi_schedule_from_config(config, cfg.current_year, cfg.end_year)
person1_data = ssi_schedule[ssi_schedule['person'] == cfg.person1_name].set_index('year')
person2_data = ssi_schedule[ssi_schedule['person'] == cfg.person2_name].set_index('year')
```

See [`../implementation/SSI_INTEGRATION_GUIDE.md`](../implementation/SSI_INTEGRATION_GUIDE.md) for full SSI integration details.

### [`load_data.py`](load_data.py:1)

Used for:
- [`get_networth_by_month(month, year)`](load_data.py:1) — loads portfolio market values
- [`get_std_deduction(year)`](load_data.py:1) — standard deduction data
- [`get_income_tax_brackets(year)`](load_data.py:1) — federal tax bracket data

### [`calculations.py`](calculations.py:1)

Used for:
- [`calculate_std_deduction(income, df)`](calculations.py:1) — standard deduction amount
- [`calculate_taxable_income(agi, df)`](calculations.py:1) — federal tax calculation
- [`get_rmd_value(age)`](calculations.py:1) — IRS RMD life expectancy factor

### [`config.py`](config.py:1)

Used via [`get_config_manager()`](config.py:319) to read person names, birth dates, and SSI claiming ages.

---

## Logging

The module uses Python's standard `logging` library. Log level is controlled by the `LOG_LEVEL` environment variable:

```bash
# Show all debug output
export LOG_LEVEL=DEBUG
streamlit run planning_app.py

# Show only warnings and errors (default)
export LOG_LEVEL=WARNING
```

**Key log messages:**

| Level | Message | When |
|-------|---------|------|
| `INFO` | `"Using person names from config: Tom, Sarah"` | Startup |
| `DEBUG` | `"Loaded net worth for 2/2026 — Cash: $55,000..."` | Portfolio load |
| `DEBUG` | `"Generated SSI schedule with N rows"` | SSI schedule build |
| `WARNING` | `"Negative income provided: -1000, setting to 0"` | Tax input normalization |
| `ERROR` | `"Net worth data is empty for 2/2026, using default values of 0"` | Missing portfolio data |
| `ERROR` | `"Failed to retrieve standard deduction data for year 2026"` | Missing tax data |

---

## Error Handling

| Scenario | Behavior |
|----------|---------|
| Portfolio CSV missing or empty | Returns zero balances; simulation continues |
| Tax data files missing | `calculate_taxes()` returns `0.0`; error logged |
| Negative income/DAF | Normalized to `0.0`; warning logged |
| Invalid year (< 1900 or > 2100) | `ValueError` raised by `_validate_tax_inputs()` |
| `ssi_year <= 2027` | `ValueError` raised by `_calculate_year_distributions()` |
| Traditional account goes negative | All distributions zeroed; account grows at `rate` |
| SSI year not in schedule | Returns `0.0` for that person's benefit |

---

## Troubleshooting

### All portfolio values show as $0

**Cause:** `portfolio_data_truth.csv` is missing or has no data for the current month/year.

**Fix:**
1. Open the Configuration page → Portfolio Data tab
2. Ensure at least 2 months of data are entered
3. Verify the current month and year are present in the data
4. Check logs: `export LOG_LEVEL=DEBUG`

### SSI benefits are $0 for all years

**Cause:** `person1_ssi_amount` or `person2_ssi_amount` is `0` in config, or the persons haven't reached their claiming age in the simulation range.

**Fix:**
1. Open Configuration → Social Security tab
2. Enter the estimated monthly benefit at age 67 (FRA)
3. Verify the claiming age is within 62–70

### Taxes seem too high or too low

**Cause:** Tax data CSV files may be missing or the income calculation is incorrect.

**Fix:**
1. Verify `income_rates.csv` and `standard.csv` exist
2. Enable debug logging to see the tax calculation breakdown
3. Check that `SSI_TAXABLE_FRACTION` (85%) is expected for your income level

### Expenses don't match expectations

**Cause:** The `EXPENSE_DEFLATOR` (0.993) applies a 0.7% annual real spending reduction. Over 25 years this compounds to roughly an 16% reduction.

**Note:** This is intentional — it models the empirical observation that retirees tend to spend less in real terms as they age ("retirement spending smile"). Adjust `EXPENSE_DEFLATOR` in the source if a different assumption is preferred.

---

## See Also

- [`../implementation/SSI_INTEGRATION_GUIDE.md`](../implementation/SSI_INTEGRATION_GUIDE.md) — SSI dynamic calculation details
- [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) — Configuration reference
- [`STRATEGY_README.md`](STRATEGY_README.md) — Full 6-stage withdrawal strategy
- [`PORTFOLIO_REBALANCING_GUIDE.md`](PORTFOLIO_REBALANCING_GUIDE.md) — Portfolio rebalancing
- [`LOGGING_GUIDE.md`](LOGGING_GUIDE.md) — Logging configuration across all modules

---

**Module:** [`income_expense.py`](income_expense.py:1)  
**Last Updated:** 2026-03-01  
**Author:** Bob