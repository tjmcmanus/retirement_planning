import pandas as pd
import numpy as np
import streamlit as st
import sys
import os
import argparse
import logging
import warnings
from datetime import date
from datetime import datetime
from typing import Literal, NamedTuple
from load_data import get_cap_gains_brackets, get_income_tax_brackets, get_net_worth, get_medicare_costs, get_atm_costs, get_std_deduction, load_rmd_data

# Configure logging
# Set default level to WARNING to suppress debug messages unless explicitly enabled
# To enable debug logging, set level to logging.DEBUG:
#   logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(funcName)s: %(message)s')
# Or use environment variable: export LOG_LEVEL=DEBUG
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
# Constants
MIN_TAXABLE_AMOUNT = 0.0

class TaxCalculation(NamedTuple):
    """Result of progressive tax calculation.
    
    Attributes:
        total_tax: Total tax owed (truncated to whole dollars via floor)
        max_rate: Highest tax rate that applies to this income
        upper_max: Upper limit of the highest bracket that applies
    """
    total_tax: float
    max_rate: float
    upper_max: float


def calc_roth_conversions_tax(
    maxrate: float,
    headroom_rate: float,
    uppermax: float,
    agi: float,
    headroom_max: float,
    conversion: float,
) -> float:
    """
    Calculate tax on Roth conversions considering tax brackets and headroom.

    Args:
        maxrate: Current tax bracket rate
        headroom_rate: Next higher tax bracket rate
        uppermax: Upper limit of current tax bracket
        agi: Adjusted Gross Income
        headroom_max: Upper limit of headroom bracket
        conversion: Conversion amount

    Returns:
        float: Calculated conversion tax
    """
    # Early return if maxrate exceeds headroom_rate (no conversion benefit)
    if maxrate > headroom_rate:
        logger.debug(f"No conversion: maxrate ({maxrate}) > headroom_rate ({headroom_rate})")
        return 0.0

    # Early return for non-positive conversion amounts (no tax owed)
    if conversion <= 0:
        return 0.0

    current_space  = max(0.0, uppermax - agi)           # room left in current bracket
    headroom_space = max(0.0, headroom_max - uppermax)  # width of next bracket

    if conversion > current_space + headroom_space:
        raise ValueError(
            f"Conversion exceeds both current bracket and headroom bracket by "
            f"{conversion - current_space - headroom_space:,.2f}. "
            "No third-rate bracket is defined to handle this overflow."
        )

    logger.debug(
        f"Bracket spaces: current={current_space:,.2f}, headroom={headroom_space:,.2f}"
    )

    current_portion  = min(conversion, current_space)
    headroom_portion = max(0.0, conversion - current_space)
    conversion_tax   = (current_portion * maxrate) + (headroom_portion * headroom_rate)

    logger.debug(
        f"Conversion tax: current_portion={current_portion:,.2f} @ {maxrate:.0%}, "
        f"headroom_portion={headroom_portion:,.2f} @ {headroom_rate:.0%} → tax={conversion_tax:,.2f}"
    )
    return conversion_tax

def calc_roth_conversions(maxrate, headroom_rate, uppermax, agi, headroom_max, lowerby):
    """
    Calculate Roth conversion amounts and associated tax with headroom adjustment.
    
    Args:
        maxrate: Current tax bracket rate
        headroom_rate: Next higher tax bracket rate
        uppermax: Upper limit of current tax bracket
        agi: Adjusted Gross Income
        headroom_max: Upper limit of headroom bracket
        lowerby: Amount to reduce headroom conversion by
        
    Returns:
        tuple: (total_conversions, conversion_tax)
    """
    # Early return if maxrate exceeds headroom_rate (no conversion benefit)
    if maxrate > headroom_rate:
        logger.debug(f"No conversion: maxrate ({maxrate}) > headroom_rate ({headroom_rate})")
        return 0.0, 0.0
    
    # Calculate conversion amounts
    conversion = uppermax - agi
    headroom_conv = headroom_max - uppermax
    
    logger.debug(f"Initial: conversion={conversion:,.2f}, headroom_conv={headroom_conv:,.2f}, lowerby={lowerby:,.2f}")
    
    # Adjust headroom conversion if lowerby is specified
    if lowerby > 0:
        headroom_conv = max(0, headroom_conv - lowerby)
        logger.debug(f"Reduced headroom_conv to {headroom_conv:,.2f} (lowerby={lowerby:,.2f})")
    
    # Calculate tax on both conversion portions
    conversion_tax = (conversion * maxrate) + (headroom_conv * headroom_rate)
    total_conversions = conversion + headroom_conv
    
    logger.debug(f"Results: total_conversions=${total_conversions:,.2f}, conversion_tax=${conversion_tax:,.2f}")
    
    return total_conversions, conversion_tax
    
def calc_agi(joint_gross_income, interest, stddectdf, daf):
    """
    Calculate Adjusted Gross Income (AGI) considering standard deduction and DAF contributions.
    
    Args:
        joint_gross_income: Joint gross income amount
        interest: Interest and dividend income
        stddectdf: Standard deduction DataFrame
        daf: Donor Advised Fund contribution amount
        
    Returns:
        float: Calculated AGI
    """
    total_income = joint_gross_income + interest
    std_deduction = calculate_std_deduction(total_income, stddectdf)
    
    logger.debug(f"calc_agi: gross_income={joint_gross_income:,.2f}, interest={interest:,.2f}, daf={daf:,.2f}")
    
    # Check if standard deduction is zero (no income scenario)
    if std_deduction == 0:
        logger.debug("AGI: Zero income route (std_deduction=0)")
        return 0.0
    
    # Check if DAF exceeds standard deduction (itemized deduction route).
    # When itemizing via DAF, the DAF amount IS the deduction — the standard
    # deduction is NOT also subtracted. AGI = total_income - daf only.
    if std_deduction < daf:
        agi = total_income - daf
        logger.debug(f"AGI: DAF route (daf > std_deduction) = {agi:,.2f}")
    else:
        # Standard deduction route
        agi = total_income - std_deduction
        logger.debug(f"AGI: Standard deduction route = {agi:,.2f}")
    
    return agi
        
# IRS AGI deduction limits for DAF contributions (IRC §170)
# Cash contributions to a public charity / DAF: 60% of AGI (post-TCJA)
# Appreciated long-term capital property donated to a DAF: 30% of AGI
_DAF_CASH_LIMIT_PCT: float = 0.60
_DAF_SECURITIES_LIMIT_PCT: float = 0.30

# Lookup table: contribution_type → (AGI limit fraction, human-readable label)
# Add new contribution types here without touching calc_daf_value.
_CONTRIBUTION_LIMITS: dict[str, tuple[float, str]] = {
    "cash":       (_DAF_CASH_LIMIT_PCT,       "60% (cash)"),
    "securities": (_DAF_SECURITIES_LIMIT_PCT, "30% (appreciated securities)"),
}


def calc_daf_value(
    joint_gross_income: float,
    interest: float,
    daf1: float,
    maxdaf: Literal["Y", "N"] | str,
    contribution_type: Literal["cash", "securities"] = "cash",
    stddectdf: pd.DataFrame | None = None,
) -> float:
    """
    Calculate the deductible Donor Advised Fund (DAF) contribution amount.

    IRS deduction limits (IRC §170):
    - **Cash** contributions to a DAF: up to **60% of AGI**.
    - **Appreciated securities** (long-term capital property) donated to a DAF:
      up to **30% of AGI**.  The donor avoids capital gains tax on the embedded
      gain AND deducts the full fair-market value.
    - Excess contributions carry forward for up to 5 years (IRC §170(d)).

    Args:
        joint_gross_income: Joint gross income (wages + distributions, etc.)
        interest:           Interest and dividend income
        daf1:               Proposed DAF contribution amount (used when maxdaf
                            is neither "Y" nor "N")
        maxdaf:             "Y" → use the maximum allowable amount for the
                            contribution type; "N" → no DAF contribution;
                            anything else → use daf1 if within the limit.
        contribution_type:  "cash" (default) or "securities".  Determines
                            which AGI limit applies (60% vs 30%).
        stddectdf:          Standard deduction DataFrame (from get_std_deduction).
                            Used to compute AGI = gross_income - std_deduction
                            per IRC §170.  If None or empty, gross income is used
                            as a conservative fallback.

    Returns:
        float: Deductible DAF contribution amount (AGI-limited).

    Raises:
        ValueError: If contribution_type is not a recognised key in
                    _CONTRIBUTION_LIMITS.
    """
    # Validate contribution type early — raises ValueError for unsupported values
    # so misconfiguration is caught immediately rather than silently using the
    # wrong AGI limit.
    if contribution_type not in _CONTRIBUTION_LIMITS:
        raise ValueError(
            f"Unsupported contribution_type {contribution_type!r}. "
            f"Expected one of: {list(_CONTRIBUTION_LIMITS)}"
        )
    limit_pct, limit_label = _CONTRIBUTION_LIMITS[contribution_type]

    # Guard clause: no DAF requested — short-circuit before any arithmetic.
    if maxdaf == "N":
        logger.debug("DAF: None (maxdaf='N')")
        return 0.0

    # Compute the AGI-based ceiling per IRC §170: the deduction limit is a
    # percentage of AGI, not gross income.  AGI = gross_income - std_deduction.
    total_income  = joint_gross_income + interest
    std_deduction = calculate_std_deduction(total_income, stddectdf) if stddectdf is not None else 0.0
    agi           = total_income - std_deduction
    max_daf_limit = agi * limit_pct

    logger.debug(
        f"calc_daf_value: gross_income={joint_gross_income:,.2f}, "
        f"interest={interest:,.2f}, std_deduction={std_deduction:,.2f}, "
        f"agi={agi:,.2f}, maxdaf={maxdaf}, "
        f"type={contribution_type}, limit={limit_label}, "
        f"max_limit=${max_daf_limit:,.2f}"
    )

    # Maximum allowable contribution.
    if maxdaf == "Y":
        logger.debug(f"DAF: Maximum ({limit_label}) = ${max_daf_limit:,.2f}")
        return max_daf_limit

    # Custom amount: use daf1 when it is non-negative and within the AGI limit.
    if 0 <= daf1 <= max_daf_limit:
        logger.debug(f"DAF: Custom amount = ${daf1:,.2f}")
        return daf1

    # daf1 is negative or exceeds the AGI limit — default to 0.
    logger.warning(
        f"DAF: Requested amount (daf1={daf1:,.2f}) exceeds {limit_label} "
        f"limit ${max_daf_limit:,.2f} or is negative — defaulting to 0"
    )
    return 0.0
    
def getUpperIncomeRate(taxrate, year_tax_brackets_df):
    """
    Get the upper income limit for a given tax rate from tax brackets.
    
    Args:
        taxrate: Tax rate to query (can be string or numeric)
        year_tax_brackets_df: DataFrame containing tax bracket information with 'rate' and 'upper' columns
        
    Returns:
        float: Upper income limit for the specified tax rate
        
    Raises:
        ValueError: If the tax rate is not found in the brackets
    """
    rate_to_query = float(taxrate)
    
    logger.debug(f"Querying upper limit for tax rate: {rate_to_query:.2%}")
    
    # Use numpy isclose for floating-point comparison to handle precision issues
    # This handles cases like 0.24 vs 0.24000000000000002
    mask = np.isclose(year_tax_brackets_df['rate'], rate_to_query, rtol=1e-9, atol=1e-9)
    result = year_tax_brackets_df[mask]
    
    if result.empty:
        logger.warning(f"Tax rate {rate_to_query:.2%} not found in brackets")
        raise ValueError(f"Tax rate {rate_to_query} not found in tax brackets")
    
    if len(result) > 1:
        raise ValueError(f"Tax rate {rate_to_query} matches multiple rows in tax brackets; expected exactly one")
    
    uppervalue = float(result['upper'].item())
    logger.debug(f"Upper limit for rate {rate_to_query:.2%}: ${uppervalue:,.2f}")
    
    return uppervalue
       
def calc_atm_phase_out(total_income, cap_gains, deduction, phase_out, exception_rate):
    """
    Calculate Alternative Minimum Tax (ATM) income with phase-out adjustments.
    
    The deduction is reduced when total income exceeds the phase-out threshold.
    
    Args:
        total_income: Total income amount
        cap_gains: Capital gains amount
        deduction: Base deduction amount
        phase_out: Phase-out threshold
        exception_rate: Rate at which deduction is reduced above phase-out
        
    Returns:
        float: Calculated income after deduction adjustments
    """
    magi = total_income + cap_gains
    
    logger.debug(f"ATM phase-out calc: MAGI=${magi:,.2f}, phase_out=${phase_out:,.2f}")
    
    if magi <= phase_out:
        # Below phase-out: full deduction applies
        adjusted_deduction = deduction
        logger.debug(f"Below phase-out: full deduction=${deduction:,.2f}")
    else:
        # Above phase-out: reduce deduction
        excess = magi - phase_out
        deduction_reduction = exception_rate * excess
        adjusted_deduction = max(0, deduction - deduction_reduction)
        logger.debug(f"Above phase-out: excess=${excess:,.2f}, reduction=${deduction_reduction:,.2f}, adjusted_deduction=${adjusted_deduction:,.2f}")
    
    income = round(total_income - adjusted_deduction, 0)
    logger.debug(f"Final ATM income: ${income:,.2f}")
    
    return income
           
def calculate_atm(total_income, cap_gains, atmdf):
    """
    Calculate Alternative Minimum Tax (ATM) based on income and tax brackets.
    
    Args:
        total_income: Total income amount
        cap_gains: Capital gains amount
        atmdf: DataFrame containing ATM brackets with columns:
               year, deduction, lower, upper, phase_out, rate, exception_rate
        
    Returns:
        tuple: (total_tax, lowerby_amount)
            - total_tax: Total ATM tax owed
            - lowerby_amount: Amount by which income exceeds lower bracket threshold
    """
    magi = total_income + cap_gains
    logger.debug(f"calculate_atm: MAGI=${magi:,.2f}")
    
    total_tax = 0.0
    lowerby = 0.0
    
    # Iterate through ATM brackets
    for year, deduction, lower, upper, phase_out, rate, exception_rate in atmdf[['year', 'deduction', 'lower', 'upper', 'phase_out', 'rate', 'exception_rate']].values:
        logger.debug(f"Processing year {year:.0f}: rate={rate:.2%}, bracket=[${lower:,.0f}-${upper:,.0f}]")
        
        # Calculate income with phase-out adjustments.
        # NOTE: std_deduction is intentionally excluded from ATM income. The AMT
        # system uses its own separate exemption (the 'deduction' column in atmdf)
        # rather than the regular standard deduction, so adding std_deduction here
        # would incorrectly inflate MAGI and misplace the taxpayer in ATM brackets.
        income = calc_atm_phase_out(total_income, cap_gains, deduction, phase_out, exception_rate)
        
        # Check if income falls within this bracket
        if lower <= income <= upper:
            bracket_tax = round(income * rate, 0)
            lowerby = income - lower
            total_tax += bracket_tax
            logger.debug(f"Income ${income:,.2f} in bracket: tax=${bracket_tax:,.2f}, lowerby=${lowerby:,.2f}")
        else:
            logger.debug(f"Income ${income:,.2f} outside bracket")
    
    logger.debug(f"Total ATM tax: ${total_tax:,.2f}, lowerby: ${lowerby:,.2f}")
    return total_tax, lowerby

# TODO: remove `year` parameter in a future version once all callers are updated
def getlower_atm_amount_n_deduction(year, atmdf):
    """
    Get the lower ATM amount and deduction for the second bracket (index 1).
    
    Note: The 'year' parameter is currently unused but kept for API compatibility.
    It is deprecated and will be removed in a future version.
    
    Args:
        year: Deprecated. Year parameter (unused, kept for compatibility).
              Pass ``None`` (or omit via a wrapper) to suppress the warning.
        atmdf: DataFrame containing ATM brackets with 'lower' and 'deduction' columns
        
    Returns:
        tuple: (lower_amount, deduction_amount) from the second bracket (index 1)
        
    Raises:
        IndexError: If atmdf has fewer than 2 rows
    """
    if year is not None:
        warnings.warn(
            "The 'year' parameter of getlower_atm_amount_n_deduction() is deprecated "
            "and will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
    if len(atmdf) < 2:
        logger.error(f"ATM DataFrame has insufficient rows: {len(atmdf)} (need at least 2)")
        raise IndexError("ATM DataFrame must have at least 2 rows")
    
    # Extract values directly from the second row (index 1)
    lower_amount = atmdf.iloc[1]['lower']
    deduction_amount = atmdf.iloc[1]['deduction']
    
    logger.debug(f"ATM bracket[1]: lower=${lower_amount:,.2f}, deduction=${deduction_amount:,.2f}")
    
    return lower_amount, deduction_amount
   
def calculate_atm1(total_income, cap_gains, atmdf):
    """
    .. deprecated::
        Use :func:`calculate_atm` instead. ``calculate_atm1`` is a legacy
        implementation that lacks ``exception_rate`` support and will be
        removed in a future version.
    """
    warnings.warn(
        "calculate_atm1() is deprecated and will be removed in a future version. "
        "Use calculate_atm() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return calculate_atm(total_income, cap_gains, atmdf)
    
def get_std_deduction_by_year(year_in):
    """
    Get the standard deduction amount for a specific year.
    
    Args:
        year_in: The year to get the standard deduction for
        
    Returns:
        float: Standard deduction amount for the specified year
        
    Raises:
        ValueError: If no deduction data is found for the year
    """
    stddectdf = get_std_deduction(year_in)
    
    if stddectdf.empty:
        logger.error(f"No standard deduction data found for year {year_in}")
        raise ValueError(f"No standard deduction data found for year {year_in}")
    
    # Get the first row's deduction value directly
    deduction = float(stddectdf.iloc[0]['deduction'])
    logger.debug(f"Standard deduction for year {year_in}: ${deduction:,.2f}")
    
    return deduction
    
def calculate_std_deduction(joint_gross_income, stddectdf):
    """
    Calculate the applicable standard deduction based on income.
    
    Returns the standard deduction if income is sufficient, otherwise returns 0.
    Note: This function only processes the first row of the DataFrame.
    
    Args:
        joint_gross_income: Joint gross income amount
        stddectdf: DataFrame containing standard deduction data with 'deduction' column
        
    Returns:
        float: Standard deduction amount (or 0 if income is below deduction threshold)
    """
    logger.debug(f"calculate_std_deduction: joint_gross_income=${joint_gross_income:,.2f}")
    
    if stddectdf.empty:
        logger.warning("Standard deduction DataFrame is empty, returning 0")
        return 0.0
    
    # Get deduction from first row
    deduction = float(stddectdf.iloc[0]['deduction'])
    
    # Return deduction if income is sufficient, otherwise 0
    if joint_gross_income >= deduction:
        logger.debug(f"Income sufficient: returning deduction ${deduction:,.2f}")
        return deduction
    else:
        logger.debug(f"Income insufficient: returning 0 (income ${joint_gross_income:,.2f} < deduction ${deduction:,.2f})")
        return 0.0
    
def calculate_irmma_penalty(income, irmaa_range, people):
    """
    Calculate IRMAA (Income-Related Monthly Adjustment Amount) penalty for Medicare.
    
    IRMAA is an additional premium charged to higher-income Medicare beneficiaries.
    
    Args:
        income: Annual income amount
        irmaa_range: DataFrame with IRMAA brackets.  Supports both the legacy
            schema (``lower``, ``upper``, ``rate``) and the current schema
            (``lower``, ``upper``, ``part_b_monthly``).  ``part_b_monthly`` takes
            precedence when both columns are present.
        people: Number of people subject to IRMAA
        
    Returns:
        float: Annual IRMAA penalty (monthly penalty * 12 * number of people)
    """
    logger.debug(f"calculate_irmma_penalty: income=${income:,.2f}, people={people}")

    # Support both the legacy 'rate' column and the current 'part_b_monthly' column.
    rate_col = 'part_b_monthly' if 'part_b_monthly' in irmaa_range.columns else 'rate'
    
    monthly_penalty = 0.0
    
    # Find the applicable IRMAA bracket
    for lower, upper, rate in irmaa_range[['lower', 'upper', rate_col]].values:
        if lower <= income <= upper:
            monthly_penalty = rate
            logger.debug(f"IRMAA bracket found: income ${income:,.2f} in [${lower:,.2f}-${upper:,.2f}], rate=${rate:,.2f}/month")
            break
        else:
            logger.debug(f"Income ${income:,.2f} not in bracket [${lower:,.2f}-${upper:,.2f}]")
    
    annual_penalty = monthly_penalty * 12 * people
    logger.debug(f"Annual IRMAA penalty: ${monthly_penalty:,.2f}/month * 12 * {people} = ${annual_penalty:,.2f}")
    
    return annual_penalty

def calculate_cap_gains(income: float, cg_range: pd.DataFrame, cg_income: float) -> float:
    """
    Calculate capital gains tax using progressive tax brackets.

    Ordinary income fills the lower brackets first; capital gains are taxed on the
    remainder. Uses interval-overlap vectorization across brackets.

    Args:
        income:    Ordinary income amount (fills brackets from the bottom).
        cg_range:  DataFrame with capital gains brackets ('lower', 'upper', 'rate' columns).
        cg_income: Capital gains income amount.

    Returns:
        float: Total capital gains tax owed.
    """
    if cg_income <= 0:
        logger.debug(f"No capital gains to tax (cg_income={cg_income})")
        return 0.0

    agi = income + cg_income

    lower = cg_range['lower'].to_numpy()
    upper = cg_range['upper'].to_numpy()
    rate  = cg_range['rate'].to_numpy()

    # Tax the CG falling in the overlap of [income, agi] and each bracket [lower, upper]
    taxed_cg    = np.maximum(0.0, np.minimum(agi, upper) - np.maximum(income, lower))
    bracket_tax = np.floor(taxed_cg * rate)
    total_tax   = float(bracket_tax.sum())

    logger.debug(
        f"calculate_cap_gains: income=${income:,.2f}, cg_income=${cg_income:,.2f}, "
        f"AGI=${agi:,.2f} → total_tax=${total_tax:,.2f}"
    )
    return total_tax

    
def calculate_taxable_income(income: float, tax_brackets_df: pd.DataFrame) -> TaxCalculation:
    """
    Calculate income tax using progressive tax brackets.
    
    Applies progressive taxation where income is taxed at different rates across brackets.
    Also returns the highest tax rate applied and its upper limit.
    
    Args:
        income: Total taxable income
        tax_brackets_df: DataFrame with tax brackets containing 'lower', 'upper', 'rate' columns
        
    Returns:
        TaxCalculation: Named tuple containing:
            - total_tax: Total tax owed (truncated to whole dollars via floor)
            - max_rate: Highest tax rate that applies to this income
            - upper_max: Upper limit of the highest bracket that applies
    """
    if income < 0:
        logger.warning(f"Negative income ${income:,.2f} received; returning zero tax")
        return TaxCalculation(0.0, 0.0, 0.0)
    if income == 0:
        return TaxCalculation(0.0, 0.0, 0.0)

    logger.debug(f"calculate_taxable_income: income=${income:,.2f}")

    # Vectorized bracket calculation: clip income above each bracket's floor to the
    # bracket width. Brackets are non-overlapping and cumulative (each bracket's
    # lower == previous bracket's upper), so this gives the correct marginal amount
    # without double-counting lower-bracket income.
    taxable_in_bracket = (income - tax_brackets_df['lower']).clip(
        MIN_TAXABLE_AMOUNT,
        tax_brackets_df['upper'] - tax_brackets_df['lower']
    )
    bracket_tax = np.floor(taxable_in_bracket * tax_brackets_df['rate'])
    total_tax = float(bracket_tax.sum())

    # Highest bracket that income reaches (taxable_in_bracket > 0)
    active = taxable_in_bracket > 0
    if active.any():
        max_rate = float(tax_brackets_df.loc[active, 'rate'].max())
        upper_max = float(tax_brackets_df.loc[active, 'upper'].max())
    else:
        max_rate = 0.0
        upper_max = 0.0

    logger.debug(
        f"Total tax: ${total_tax:,.2f}, max_rate={max_rate:.2%}, "
        f"upper_max=${upper_max:,.2f}"
    )
    return TaxCalculation(total_tax, max_rate, upper_max)

def get_rmd_value(age):
    """
    Get the Required Minimum Distribution (RMD) rate for a given age.
    
    RMD rates determine the minimum percentage that must be withdrawn from
    retirement accounts annually based on the account holder's age.
    
    Args:
        age: Age of the account holder
        
    Returns:
        float: RMD distribution rate for the age (0 if age not found)
    """
    rmddf = load_rmd_data()
    
    # Filter for the specific age
    age_data = pd.DataFrame(rmddf[rmddf['Age'] == age])
    
    if age_data.empty:
        logger.warning(f"Age {age} not found in RMD data, returning 0")
        return 0.0
    
    # Get distribution rate directly
    distribution_rate = float(age_data['Distribution'].iloc[0])
    logger.debug(f"RMD rate for age {age}: {distribution_rate}")
    
    return distribution_rate

