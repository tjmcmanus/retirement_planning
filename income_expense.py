from matplotlib.pylab import f
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
    
    Note: Roth conversions are now handled by the BETR algorithm in withdrawal_strategy.py
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
                                    rate: float) -> tuple[float, float, float, float, float]:
    """
    Calculate RMD and update traditional account value.
    
    Args:
        trad_value: Current traditional account value
        t_age: Tom's age for the year
        planned_dist: Planned distribution amount
        conversions: Roth conversion amount
        rate: Growth rate multiplier (1 + rate/100)
        
    Returns:
        tuple: (rmd, planned_dist, conversions, daf, new_trad_value)
               Returns zeros for distributions if account becomes negative
    """
    rmd = 0
    daf = 0
    
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
        return (0, 0, 0, 0, trad_value * rate)
    
    # Apply growth rate to remaining balance
    return (rmd, planned_dist, conversions, daf, trad_value_new * rate)



def build_income_expenses_display():
    """
    Build income and expense projections with portfolio tracking.
    
    Returns:
        tuple: (i_e_df, port_draw_df) - DataFrames containing income/expense and portfolio projections
    """
    # Initialize state variables
    cash = 0
    tax_free = 0
    today = datetime.date.today()
    current_year = today.year
    current_month = today.month
    
    # Load configuration to get person names dynamically
    config = get_config_manager()
    person1_name = config.get("personal_info", "person1_name", "Person1")
    person2_name = config.get("personal_info", "person2_name", "Person2")
    person1_claiming_age = config.get("social_security", "person1_ssi_age", 70)
    person1_birth_date = config.get("personal_info", "person1_birth_date", "1965-01-01")
    person1_birth_year = int(person1_birth_date.split('-')[0])
    person2_birth_date = config.get("personal_info", "person2_birth_date", "1967-01-01")
    person2_birth_year = int(person2_birth_date.split('-')[0])
    
    logger.info(f"Using person names from config: {person1_name}, {person2_name}")
    
    # Load current net worth data using helper function
    portfolio = _load_portfolio_data(current_month, current_year)
    cash_in = portfolio['cash_in']
    brokerage = portfolio['brokerage']
    trad_value = portfolio['trad_value']
    tax_free_in = portfolio['tax_free_in']
    
    # Cache session state values to avoid repeated lookups
    expenses = float(st.session_state["EXPENSE"])
    rate = 1 + float(st.session_state["RATE"]) / 100
    daf_rate = float(st.session_state["DAF_RATE"]) / 100
    expense_multiplier = int(st.session_state["EXPENSE_MULTIPLIER"])
    planned_dist_2027 = float(st.session_state.get("PLANNED_DIST_2027", "575000") or "575000")
    
    # Calculate SSI year and claiming age once using config values
    claiming_age = person1_claiming_age
    ssi_year = person1_birth_year + claiming_age
    
    # Initialize tracking variables
    end_year = 2051
    daf_in = 0
    
    # Generate SSI schedule from config (replaces CSV-based lookups)
    ssi_schedule = generate_ssi_schedule_from_config(config, current_year, end_year)
    logger.debug(f"Generated SSI schedule with {len(ssi_schedule)} rows")
    
    # Pre-compute age and benefit lookups for performance
    person1_data = ssi_schedule[ssi_schedule['person'] == person1_name].set_index('year')
    person2_data = ssi_schedule[ssi_schedule['person'] == person2_name].set_index('year')
    
    # Accumulate rows in lists for efficient DataFrame construction
    i_e_rows = []
    port_draw_rows = []
    
    # Iterate through years and accumulate results
    for year in range(current_year, end_year):
        # Get ages and benefits from pre-computed SSI schedule
        person1_age = year - person1_birth_year
        person2_age = year - person2_birth_year
        age = str(person2_age) + "/" + str(person1_age)
        
        # Get monthly benefits from SSI schedule
        person1_monthly_benefit = person1_data.loc[year, 'monthly_benefit'] if year in person1_data.index else 0.0
        person2_monthly_benefit = person2_data.loc[year, 'monthly_benefit'] if year in person2_data.index else 0.0
        monthly_benefit = (person2_monthly_benefit + person1_monthly_benefit) * 12
        
        # Calculate year-specific distributions using helper function
        planned_dist, daf, conversions = _calculate_year_distributions(
            year=year,
            ssi_year=ssi_year,
            planned_dist_2027=planned_dist_2027
        )
       
        # Calculate RMD and update traditional account using helper function
        rmd, planned_dist, conversions, daf, trad_value = _calculate_rmd_and_update_trad(
            trad_value, person1_age, planned_dist, conversions, rate
        )
        
        # Calculate taxes
        taxable_inflows = (monthly_benefit * 0.85) + planned_dist + conversions + rmd - daf
        taxes = calculate_taxes(taxable_inflows, 0, year)
        
        # Update expenses with deflator
        expenses = expenses * 0.993
        
        # Calculate portfolio withdrawal
        tot_inflows = monthly_benefit
        portfolio_withdrawal = (expenses + taxes) - tot_inflows
        if portfolio_withdrawal < 0:
            portfolio_withdrawal = 0
        tot_inflows = portfolio_withdrawal + tot_inflows
        
        # Update cash balance
        if cash > 0:
            cash = cash + monthly_benefit + portfolio_withdrawal - expenses - taxes
            cash_rate = ((rate - 1) / 3)
            cash = cash + cash * cash_rate
        else:
            cash = cash_in + monthly_benefit + portfolio_withdrawal - expenses - taxes
            cash_rate = ((rate - 1) / 3)
            cash = cash + cash * cash_rate
        
        # Check brokerage threshold and adjust if needed
        brokerage_threshold = (expenses + taxes) * expense_multiplier
        
        if brokerage < brokerage_threshold:
            planned_dist = planned_dist + conversions / 2
            conversions = conversions / 2
        
        # Update brokerage account (simplified - same formula for all cases)
        brokerage = (brokerage + planned_dist + rmd - daf - portfolio_withdrawal) * rate
        
        # Update tax-free account
        if tax_free > 0:
            tax_free = (tax_free + conversions) * rate
        else:
            tax_free = (tax_free_in + tax_free + conversions) * rate
        
        # Update DAF
        if daf_in == 0:
            daf_in = daf
        elif daf_in >= (daf_in * daf_rate):
            daf_in = daf_in - (daf_in * daf_rate) + daf
        else:
            daf_in = daf
        
        # Accumulate row data (efficient approach)
        i_e_rows.append({
            'Year': year,
            'Age': age,
            'SSI Flows': monthly_benefit,
            'Planned Distribution': planned_dist,
            'Roth Conversions': conversions,
            'RMD': rmd,
            'Total Inflows': tot_inflows,
            'Taxes Owed': taxes,
            'Expenses': expenses,
            'Portfolio Withdrawal': portfolio_withdrawal
        })
        
        port_draw_rows.append({
            'Year': year,
            'Cash': cash,
            'Taxable': brokerage,
            'Tax Deferred': trad_value,
            'Tax Free': tax_free,
            'Donor Advised Fund': daf_in
        })
    
    # Construct DataFrames once at the end (efficient approach)
    i_e_df = pd.DataFrame(i_e_rows)
    port_draw_df = pd.DataFrame(port_draw_rows)
    
    return i_e_df, port_draw_df


