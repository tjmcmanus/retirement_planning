import dataclasses
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import logging
import os
from load_data import load_ssi_data,get_annual_ssi_data,get_std_deduction, get_income_tax_brackets,get_networth_by_month
from calculations import calculate_taxable_income, calculate_std_deduction,get_rmd_value
from config import get_config_manager
from ssi_calculator import generate_ssi_schedule_from_config

# Configure logging to match calculations.py pattern
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Distribution configuration constants
YEAR_2026_CONVERSION = 100000
YEAR_2027_DAF_RATIO = 0.33
PRE_SSI_CONVERSION = 375000
EXPENSE_DEFLATOR = 0.993  # Annual real-spending reduction factor

# Account type mapping for portfolio data
ACCOUNT_TYPE_MAPPING = {
    'Cash': 'cash_in',
    'Brokerage': 'brokerage',
    'Traditional': 'trad_value',
    'Roth': 'tax_free_in'
}


def _calculate_year_distributions(year: int, ssi_year: int,
                                  planned_dist_2027: float) -> tuple:
    """
    Calculate planned distributions, DAF contributions, and conversions for a given year.
    
    Note: Roth conversions are now handled by the BETR algorithm in strategy.py
    This function only returns legacy conversion amounts for historical compatibility.
    
    Args:
        year: The year to calculate distributions for
        ssi_year: The year SSI benefits begin
        planned_dist_2027: Planned distribution amount for 2027
        
    Returns:
        tuple: (planned_dist, daf, conversions) as floats
        
    Raises:
        ValueError: If ssi_year <= 2027
    """
    # Input validation
    if year < 2026:
        logger.warning(f"Year {year} is before 2026, returning zero distributions")
        return (0.0, 0.0, 0.0)
    
    if ssi_year <= 2027:
        logger.error(f"Invalid ssi_year {ssi_year}, must be > 2027")
        raise ValueError(f"ssi_year must be greater than 2027, got {ssi_year}")
    
    # Year-specific distribution logic
    if year == 2026:
        return (0.0, 0.0, float(YEAR_2026_CONVERSION))
    
    if year == 2027:
        daf = planned_dist_2027 * YEAR_2027_DAF_RATIO
        return (planned_dist_2027, daf, 0.0)
    
    if 2027 < year < ssi_year:
        return (0.0, 0.0, float(PRE_SSI_CONVERSION))
    
    # Default case: year >= ssi_year
    # Note: Roth conversions now handled by BETR algorithm, returning 0 here
    return (0.0, 0.0, 0.0)


def _validate_tax_inputs(income: float, daf: float, year: int) -> tuple[float, float, int]:
    """
    Validate and normalize tax calculation inputs.
    
    Args:
        income: Total taxable income (will be normalized to >= 0)
        daf: Donor Advised Fund contribution (will be normalized to >= 0)
        year: Tax year for calculation (must be integer between 1900-2100)
        
    Returns:
        tuple: (normalized_income, normalized_daf, year)
        
    Raises:
        ValueError: If year is invalid
    """
    # Normalize negative income to 0
    if income < 0:
        logger.warning(f"Negative income provided: {income:,.2f}, setting to 0")
        income = 0
    
    # Normalize negative DAF to 0
    if daf < 0:
        logger.warning(f"Negative DAF provided: {daf:,.2f}, setting to 0")
        daf = 0
    
    # Validate year
    if not isinstance(year, int) or year < 1900 or year > 2100:
        logger.error(f"Invalid year provided: {year}, must be integer between 1900-2100")
        raise ValueError(f"Invalid year: {year}, must be integer between 1900-2100")
    
    return income, daf, year


def _get_tax_data(year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Retrieve and validate standard deduction and tax bracket data.
    
    Args:
        year: Tax year for data retrieval
        
    Returns:
        tuple: (standard_deduction_df, tax_brackets_df)
        
    Raises:
        RuntimeError: If data retrieval fails or returns empty DataFrames
    """
    # Get standard deduction data
    stddectdf = get_std_deduction(year)
    if stddectdf is None or stddectdf.empty:
        logger.error(f"Failed to retrieve standard deduction data for year {year}")
        raise RuntimeError(f"Failed to retrieve standard deduction data for year {year}")
    logger.debug(f"Retrieved standard deduction data for year {year}")
    
    # Get tax bracket data
    taxratedf = get_income_tax_brackets(year)
    if taxratedf is None or taxratedf.empty:
        logger.error(f"Failed to retrieve tax brackets for year {year}")
        raise RuntimeError(f"Failed to retrieve tax brackets for year {year}")
    logger.debug(f"Retrieved tax bracket data for year {year}")
    
    return stddectdf, taxratedf


def calculate_taxes(income: float, daf: float, year: int) -> float:
    """
    Calculate taxes based on income, donor advised fund contributions, and year.
    
    Args:
        income: Total taxable income
        daf: Donor Advised Fund contribution amount
        year: Tax year for calculation
        
    Returns:
        float: Calculated tax amount (returns 0.0 on error)
        
    Raises:
        No exceptions raised - errors are logged and 0.0 is returned
    """
    try:
        logger.debug(f"calculate_taxes inputs: income={income:,.2f}, daf={daf:,.2f}, year={year}")
        
        # Validate and normalize inputs
        income, daf, year = _validate_tax_inputs(income, daf, year)
        
        # Retrieve tax data
        stddectdf, taxratedf = _get_tax_data(year)
        
        # Calculate standard deduction
        std_dect = calculate_std_deduction(income, stddectdf)
        logger.debug(f"Standard deduction calculated: {std_dect:,.2f}")
        
        # Calculate taxable income after standard deduction
        taxable_income = income - std_dect
        
        # Calculate AGI (Adjusted Gross Income) after DAF contribution
        agi = taxable_income - daf
        logger.debug(f"AGI calculated: {agi:,.2f} (income={income:,.2f} - std_dect={std_dect:,.2f} - daf={daf:,.2f})")
        
        # Calculate taxes based on AGI
        taxes, maxrate, uppermax = calculate_taxable_income(agi, taxratedf)
        logger.debug(f"Taxes calculated: {taxes:,.2f}, maxrate={maxrate}, uppermax={uppermax:,.2f}")
        
        return taxes
        
    except Exception as e:
        logger.error(f"Error in calculate_taxes ({type(e).__name__}): {e}. "
                     f"Inputs - income: {income}, daf: {daf}, year: {year}")
        return 0.0

def _load_portfolio_data(current_month: int, current_year: int) -> dict[str, float]:
    """
    Load portfolio data with error handling.
    
    Args:
        current_month: Month to load data for (1-12)
        current_year: Year to load data for
        
    Returns:
        dict[str, float]: Portfolio values with keys 'cash_in', 'brokerage',
                          'trad_value', 'tax_free_in'. Returns zeros on any error.
    """
    default_values = {
        'cash_in': 0.0,
        'brokerage': 0.0,
        'trad_value': 0.0,
        'tax_free_in': 0.0
    }
    
    try:
        # Get net worth with current market prices
        detailed_df, summary_df = get_networth_by_month(current_month, current_year)
        
        # Validate summary DataFrame is not empty
        if summary_df.empty:
            logger.error(f"Net worth data is empty for {current_month}/{current_year}, using default values of 0")
            return default_values
        
        # Extract values by account_type - single groupby operation
        account_values = summary_df.groupby('account_type')['market_value'].sum()
        portfolio = {
            dict_key: float(account_values.get(account_type, 0.0))
            for account_type, dict_key in ACCOUNT_TYPE_MAPPING.items()
        }
        
        logger.debug(f"Loaded net worth for {current_month}/{current_year} - "
                   f"Cash: ${portfolio['cash_in']:,.2f}, Brokerage: ${portfolio['brokerage']:,.2f}, "
                   f"Traditional: ${portfolio['trad_value']:,.2f}, Tax-Free: ${portfolio['tax_free_in']:,.2f}")
        
        return portfolio
    
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Error loading portfolio data ({error_type}): {e}. Using default values of 0")
        return default_values

def _calculate_rmd_and_update_trad(trad_value: float, t_age: float,
                                    planned_dist: float, conversions: float,
                                    rate: float) -> tuple[float, float, float, float]:
    """
    Calculate RMD and update traditional account value.

    Args:
        trad_value: Current traditional account value
        t_age: Tom's age for the year
        planned_dist: Planned distribution amount
        conversions: Roth conversion amount
        rate: Growth rate multiplier (1 + rate/100)

    Returns:
        tuple: (rmd, planned_dist, conversions, new_trad_value)
               Returns zeros for distributions if account becomes negative.
               DAF is intentionally excluded — callers should preserve the DAF
               value returned by _calculate_year_distributions directly.
    """
    rmd = 0

    # Calculate RMD based on age
    rmd_distribution = get_rmd_value(t_age)
    if rmd_distribution > 0:
        rmd = int(trad_value / rmd_distribution)

        # Adjust RMD based on other distributions
        if rmd > conversions + planned_dist:
            rmd = rmd - conversions - planned_dist
        elif rmd < (planned_dist + conversions):
            rmd = 0
        else:
            rmd = 0

    # Calculate new traditional account value
    trad_value_new = trad_value - planned_dist - conversions - rmd

    # Validate account doesn't go negative
    if trad_value < trad_value_new or trad_value < 0 or trad_value_new < 0:
        # Reset all distributions if validation fails
        return (0, 0, 0, trad_value * rate)

    # Apply growth rate to remaining balance
    return (rmd, planned_dist, conversions, trad_value_new * rate)



# ---------------------------------------------------------------------------
# Proposal 1 — SimulationConfig dataclass + _initialize_simulation_config()
# ---------------------------------------------------------------------------

def _read_personal_config(config) -> dict:
    """
    Read personal-info and social-security values from ConfigManager.

    Separating ConfigManager reads from session-state reads allows each
    source to be tested independently without mocking the other.

    Args:
        config: A ConfigManager instance (or any object with a .get() method
                matching the (section, key, default) signature).

    Returns:
        dict with keys: person1_name, person2_name, person1_claiming_age,
        person1_birth_year, person2_birth_year.

    Raises:
        ValueError: If a birth-date string does not match the "%Y-%m-%d" format.
    """
    person1_name = config.get("personal_info", "person1_name", "Person1")
    person2_name = config.get("personal_info", "person2_name", "Person2")
    logger.info("Using person names from config: %s, %s", person1_name, person2_name)
    return {
        "person1_name": person1_name,
        "person2_name": person2_name,
        "person1_claiming_age": config.get("social_security", "person1_ssi_age", 70),
        "person1_birth_year": datetime.datetime.strptime(
            config.get("personal_info", "person1_birth_date", "1965-01-01"), "%Y-%m-%d"
        ).year,
        "person2_birth_year": datetime.datetime.strptime(
            config.get("personal_info", "person2_birth_date", "1967-01-01"), "%Y-%m-%d"
        ).year,
    }


@dataclasses.dataclass
class SimulationConfig:
    """
    Immutable snapshot of all configuration and session-state values needed
    by the simulation loop.  Separating config-reading from simulation logic
    makes each unit independently testable without mocking st.session_state.
    """
    expenses: float
    rate: float           # growth multiplier, e.g. 1.07 for 7 %
    daf_rate: float       # annual DAF spend-down fraction, e.g. 0.05
    expense_multiplier: int
    planned_dist_2027: float
    ssi_year: int
    person1_birth_year: int
    person2_birth_year: int
    person1_name: str
    person2_name: str
    cash_in: float
    brokerage: float
    trad_value: float
    tax_free_in: float
    current_year: int
    current_month: int
    end_year: int = 2051


# ---------------------------------------------------------------------------
# Proposal A — SimulationState dataclass: groups the five mutable account
# variables so they can be passed as a single unit to per-year helpers.
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class SimulationState:
    """
    Mutable per-year account balances that evolve across the simulation loop.

    Grouping them here makes the state boundary explicit, enables the
    per-year helper (_simulate_year) to accept and return a single object,
    and removes the need for boolean seed flags in the main loop.
    """
    cash: float = 0.0
    tax_free: float = 0.0
    brokerage: float = 0.0
    trad_value: float = 0.0
    daf_in: float = 0.0


def _initialize_simulation_config() -> SimulationConfig:
    """
    Read all configuration and session-state values once and return them as
    an immutable SimulationConfig.

    Returns:
        SimulationConfig: Fully populated configuration snapshot.
    """
    today = datetime.date.today()
    current_year = today.year
    current_month = today.month

    personal  = _read_personal_config(get_config_manager())
    portfolio = _load_portfolio_data(current_month, current_year)

    expenses           = float(st.session_state.get("EXPENSE", "50000") or "50000")
    rate               = 1 + float(st.session_state.get("RATE", "6.0") or "6.0") / 100
    daf_rate           = float(st.session_state.get("DAF_RATE", "25") or "25") / 100
    expense_multiplier = int(float(st.session_state.get("EXPENSE_MULTIPLIER", "4") or "4"))
    planned_dist_2027  = float(
        st.session_state.get("PLANNED_DIST_2027", "575000") or "575000"
    )

    return SimulationConfig(
        expenses=expenses,
        rate=rate,
        daf_rate=daf_rate,
        expense_multiplier=expense_multiplier,
        planned_dist_2027=planned_dist_2027,
        ssi_year=personal["person1_birth_year"] + personal["person1_claiming_age"],
        person1_birth_year=personal["person1_birth_year"],
        person2_birth_year=personal["person2_birth_year"],
        person1_name=personal["person1_name"],
        person2_name=personal["person2_name"],
        cash_in=portfolio['cash_in'],
        brokerage=portfolio['brokerage'],
        trad_value=portfolio['trad_value'],
        tax_free_in=portfolio['tax_free_in'],
        current_year=current_year,
        current_month=current_month,
    )


# ---------------------------------------------------------------------------
# Proposal 2 — _apply_seed_once(): removes the magic-zero pattern
# ---------------------------------------------------------------------------

def _apply_seed_once(current: float, seed: float) -> float:
    """
    Return *seed* only when *current* is still at its zero initial value,
    ensuring the seed amount is added exactly once across the simulation loop.

    Args:
        current: Running account balance (0.0 on the very first iteration).
        seed:    Opening balance loaded from portfolio data.

    Returns:
        float: seed if current == 0, else 0.0.
    """
    return seed if current == 0 else 0.0


# ---------------------------------------------------------------------------
# Proposal 5 — _update_daf(): named financial operation, independently testable
# ---------------------------------------------------------------------------

def _update_daf(daf_in: float, daf: float, daf_rate: float) -> float:
    """
    Apply the annual DAF spend-down and add the current year's new contribution.

    The three-branch if/elif/else in the original code reduces to a single
    expression: the elif condition (daf_in >= daf_in * daf_rate) simplifies to
    (1 >= daf_rate), which is always True for a valid rate in [0, 1].  The else
    branch was therefore dead code and has been removed.

    Args:
        daf_in:   Running DAF balance before this year's activity.
        daf:      New contribution for the current year.
        daf_rate: Annual spend-down fraction (0.0–1.0).

    Returns:
        float: Updated DAF balance after spend-down and new contribution.
    """
    return daf_in * (1 - daf_rate) + daf


# ---------------------------------------------------------------------------
# Proposal B — _update_accounts(): isolates the three-account update block
# (cash, brokerage, tax-free) so it can be unit-tested independently.
# ---------------------------------------------------------------------------

def _update_accounts(
    state: SimulationState,
    cfg: "SimulationConfig",
    monthly_benefit: float,
    portfolio_withdrawal: float,
    planned_dist: float,
    conversions: float,
    rmd: float,
    daf: float,
    annual_expenses: float,
    taxes: float,
) -> SimulationState:
    """
    Compute updated cash, brokerage, and tax-free balances for one year.

    The seed amounts (cfg.cash_in, cfg.tax_free_in) are applied exactly once
    via _apply_seed_once(), which returns the seed only when the running
    balance is still at its zero initial value.  This invariant holds as long
    as neither account can return to exactly 0.0 after the first iteration —
    a safe assumption for these account types.

    Args:
        state:               Current account balances (read-only; a new
                             SimulationState is returned).
        cfg:                 Immutable simulation configuration.
        monthly_benefit:     Annual SSI inflow (12 × monthly).
        portfolio_withdrawal: Amount drawn from portfolio this year.
        planned_dist:        Planned traditional-account distribution.
        conversions:         Roth conversion amount.
        rmd:                 Required minimum distribution.
        daf:                 New DAF contribution for this year.
        annual_expenses:     Deflated living expenses for this year.
        taxes:               Tax liability for this year.

    Returns:
        SimulationState: New state with updated cash, brokerage, tax_free,
                         and daf_in.  trad_value is carried forward unchanged
                         (it is updated by _calculate_rmd_and_update_trad).
    """
    # ── Cash ─────────────────────────────────────────────────────────────────
    # Cash earns ~1/3 of the equity growth rate (conservative assumption for
    # money-market / short-term instruments).
    cash_rate = (cfg.rate - 1) / 3
    cash_seed = _apply_seed_once(state.cash, cfg.cash_in)
    new_cash = (
        state.cash
        + cash_seed
        + monthly_benefit
        + portfolio_withdrawal
        - annual_expenses
        - taxes
    ) * (1 + cash_rate)

    # ── Brokerage ─────────────────────────────────────────────────────────────
    # When brokerage is below the expense-multiple threshold, split conversions
    # evenly between brokerage and tax-free to rebuild the taxable buffer.
    brokerage_threshold = (annual_expenses + taxes) * cfg.expense_multiplier
    below_threshold = state.brokerage < brokerage_threshold
    conversions_to_brokerage = conversions / 2 if below_threshold else 0.0
    conversions_to_tax_free  = conversions / 2 if below_threshold else conversions
    new_brokerage = (
        state.brokerage
        + planned_dist
        + conversions_to_brokerage
        + rmd
        - daf
        - portfolio_withdrawal
    ) * cfg.rate

    # ── Tax-free ──────────────────────────────────────────────────────────────
    tax_free_seed = _apply_seed_once(state.tax_free, cfg.tax_free_in)
    new_tax_free = (state.tax_free + tax_free_seed + conversions_to_tax_free) * cfg.rate

    # ── DAF ───────────────────────────────────────────────────────────────────
    new_daf_in = _update_daf(state.daf_in, daf, cfg.daf_rate)

    return SimulationState(
        cash=new_cash,
        tax_free=new_tax_free,
        brokerage=new_brokerage,
        trad_value=state.trad_value,   # unchanged here; updated by RMD helper
        daf_in=new_daf_in,
    )


# ---------------------------------------------------------------------------
# Proposal 1 — _simulate_year(): extracts the per-year orchestration so the
# main loop becomes a thin driver and each year is independently testable.
# ---------------------------------------------------------------------------

def _simulate_year(
    year: int,
    state: SimulationState,
    cfg: "SimulationConfig",
    person1_data: pd.DataFrame,
    person2_data: pd.DataFrame,
    annual_expenses: float,
) -> tuple[SimulationState, float, dict, dict]:
    """
    Run one year of the retirement simulation and return updated state plus
    the two row dicts consumed by the caller to build the output DataFrames.

    Args:
        year:           Calendar year being simulated.
        state:          Account balances at the *start* of this year.
        cfg:            Immutable simulation configuration.
        person1_data:   SSI schedule for person 1, indexed by year.
        person2_data:   SSI schedule for person 2, indexed by year.
        annual_expenses: Deflated living expenses entering this year
                         (the caller applies EXPENSE_DEFLATOR before passing).

    Returns:
        tuple:
            new_state       – SimulationState after this year's activity.
            new_expenses    – annual_expenses after EXPENSE_DEFLATOR applied
                             (passed back so the caller can thread it forward).
            ie_row          – dict for the income/expense DataFrame.
            port_row        – dict for the portfolio DataFrame.
    """
    # ── Ages ──────────────────────────────────────────────────────────────────
    person1_age = year - cfg.person1_birth_year
    person2_age = year - cfg.person2_birth_year
    # person2 is listed first in the display string (intentional — matches the
    # UI convention established when the column was originally named).
    age = f"{person2_age}/{person1_age}"

    # ── SSI benefits ──────────────────────────────────────────────────────────
    person1_monthly = (
        person1_data.loc[year, 'monthly_benefit'] if year in person1_data.index else 0.0
    )
    person2_monthly = (
        person2_data.loc[year, 'monthly_benefit'] if year in person2_data.index else 0.0
    )
    monthly_benefit = (person1_monthly + person2_monthly) * 12

    # ── Distributions (two-stage pipeline) ────────────────────────────────────
    # raw_* values are preserved because _calculate_rmd_and_update_trad may
    # zero them out on a negative-balance guard.  daf is kept here; the helper
    # never modifies it.
    raw_dist, daf, raw_conversions = _calculate_year_distributions(
        year=year,
        ssi_year=cfg.ssi_year,
        planned_dist_2027=cfg.planned_dist_2027,
    )
    rmd, planned_dist, conversions, new_trad_value = _calculate_rmd_and_update_trad(
        state.trad_value, person1_age, raw_dist, raw_conversions, cfg.rate
    )

    # ── Taxes ─────────────────────────────────────────────────────────────────
    taxable_inflows = (monthly_benefit * 0.85) + planned_dist + conversions + rmd
    taxes = calculate_taxes(taxable_inflows, daf, year)

    # ── Expenses & portfolio withdrawal ───────────────────────────────────────
    new_expenses = annual_expenses * EXPENSE_DEFLATOR
    ssi_inflows = monthly_benefit
    portfolio_withdrawal = max(0.0, (new_expenses + taxes) - ssi_inflows)
    tot_inflows = ssi_inflows + portfolio_withdrawal

    # ── Update accounts (Proposal B) ──────────────────────────────────────────
    mid_state = SimulationState(
        cash=state.cash,
        tax_free=state.tax_free,
        brokerage=state.brokerage,
        trad_value=new_trad_value,
        daf_in=state.daf_in,
    )
    new_state = _update_accounts(
        state=mid_state,
        cfg=cfg,
        monthly_benefit=monthly_benefit,
        portfolio_withdrawal=portfolio_withdrawal,
        planned_dist=planned_dist,
        conversions=conversions,
        rmd=rmd,
        daf=daf,
        annual_expenses=new_expenses,
        taxes=taxes,
    )

    # ── Build output rows (Proposal 6 — row builders) ─────────────────────────
    ie_row = _build_ie_row(
        year=year,
        age=age,
        monthly_benefit=monthly_benefit,
        planned_dist=planned_dist,
        conversions=conversions,
        rmd=rmd,
        tot_inflows=tot_inflows,
        taxes=taxes,
        expenses=new_expenses,
        portfolio_withdrawal=portfolio_withdrawal,
    )
    port_row = _build_port_row(
        year=year,
        cash=new_state.cash,
        brokerage=new_state.brokerage,
        trad_value=new_state.trad_value,
        tax_free=new_state.tax_free,
        daf_in=new_state.daf_in,
    )

    return new_state, new_expenses, ie_row, port_row


# ---------------------------------------------------------------------------
# Proposal 6 — row-builder helpers: separate compute from format
# ---------------------------------------------------------------------------

def _build_ie_row(
    year: int,
    age: str,
    monthly_benefit: float,
    planned_dist: float,
    conversions: float,
    rmd: float,
    tot_inflows: float,
    taxes: float,
    expenses: float,
    portfolio_withdrawal: float,
) -> dict:
    """
    Build a single income/expense row dict for the i_e DataFrame.

    Keeping column construction here means the simulation loop stays focused
    on computing values; column names and structure are changed in one place.
    """
    return {
        'Year': year,
        'Age': age,
        'SSI Flows': monthly_benefit,
        'Planned Distribution': planned_dist,
        'Roth Conversions': conversions,
        'RMD': rmd,
        'Total Inflows': tot_inflows,
        'Taxes Owed': taxes,
        'Expenses': expenses,
        'Portfolio Withdrawal': portfolio_withdrawal,
    }


def _build_port_row(
    year: int,
    cash: float,
    brokerage: float,
    trad_value: float,
    tax_free: float,
    daf_in: float,
) -> dict:
    """
    Build a single portfolio-draw row dict for the port_draw DataFrame.
    """
    return {
        'Year': year,
        'Cash': cash,
        'Taxable': brokerage,
        'Tax Deferred': trad_value,
        'Tax Free': tax_free,
        'Donor Advised Fund': daf_in,
    }


# ---------------------------------------------------------------------------
# Main entry point — refactored to use all helpers above
# ---------------------------------------------------------------------------

def build_income_expenses_display():
    """
    Build income and expense projections with portfolio tracking.

    The simulation loop is now a thin driver: it threads SimulationState and
    annual_expenses forward each year and delegates all per-year computation
    to _simulate_year().

    Returns:
        tuple: (i_e_df, port_draw_df) - DataFrames containing income/expense
               and portfolio projections.
    """
    # Proposal 1 — load all config/session-state in one place
    cfg = _initialize_simulation_config()

    # Proposal A — initial mutable state grouped in SimulationState
    state = SimulationState(
        brokerage=cfg.brokerage,
        trad_value=cfg.trad_value,
    )

    # Proposal C — renamed to avoid shadowing cfg.expenses across iterations
    annual_expenses = cfg.expenses

    # Generate SSI schedule from config (replaces CSV-based lookups)
    config = get_config_manager()
    ssi_schedule = generate_ssi_schedule_from_config(config, cfg.current_year, cfg.end_year)
    logger.debug(f"Generated SSI schedule with {len(ssi_schedule)} rows")

    # Pre-compute per-person benefit lookups indexed by year
    person1_data = ssi_schedule[ssi_schedule['person'] == cfg.person1_name].set_index('year')
    person2_data = ssi_schedule[ssi_schedule['person'] == cfg.person2_name].set_index('year')

    # Accumulate rows in lists for efficient DataFrame construction
    i_e_rows: list[dict] = []
    port_draw_rows: list[dict] = []

    for year in range(cfg.current_year, cfg.end_year):
        # Proposal 1 — delegate all per-year logic to _simulate_year()
        state, annual_expenses, ie_row, port_row = _simulate_year(
            year=year,
            state=state,
            cfg=cfg,
            person1_data=person1_data,
            person2_data=person2_data,
            annual_expenses=annual_expenses,
        )
        i_e_rows.append(ie_row)
        port_draw_rows.append(port_row)

    # Construct DataFrames once at the end
    i_e_df = pd.DataFrame(i_e_rows)
    port_draw_df = pd.DataFrame(port_draw_rows)

    return i_e_df, port_draw_df


