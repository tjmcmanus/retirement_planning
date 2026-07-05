"""
BETR (Break-Even Tax Rate) Roth Conversion Algorithm

Based on Vanguard Research: "A 'BETR' approach to Roth conversions" (July 2025)
https://corporate.vanguard.com/content/dam/corp/research/pdf/a_betr_approach_to_roth_conversions_072025.pdf

The BETR methodology calculates a break-even tax rate that accounts for:
1. Current marginal tax rate vs. expected future tax rate
2. Tax payment source (taxable account vs. IRA assets)
3. Impact of nontaxable basis in traditional IRA
4. Future backdoor Roth contribution opportunities

Key Insight: The BETR shows how far the investor's future tax rate would have to fall
to make a Roth conversion undesirable. If the BETR is above the current marginal rate,
conversion is beneficial even if future tax rates decline.

Author: IBM Bob
Date: 2026-02-23
"""

import pandas as pd
import numpy as np
import numbers
import logging
import os
from datetime import datetime
from typing import Dict, Tuple, Optional, List, NamedTuple, Sequence, TypedDict
from dataclasses import dataclass
from functools import lru_cache

from load_data import (
    get_income_tax_brackets,
    get_cap_gains_brackets,
    get_std_deduction,
    get_medicare_costs,
)
from config import get_config_manager as _betr_get_config_manager
from calculations import (
    calculate_taxable_income,
    calc_agi,
    getUpperIncomeRate,
    calculate_irmma_penalty,
)

# Configure logging
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# BETR adjustment factors (empirical values based on Vanguard research)
# These factors adjust the break-even tax rate to account for additional benefits
NONTAXABLE_BASIS_ADJUSTMENT_FACTOR = 0.05  # 5% adjustment per 100% nontaxable basis
BACKDOOR_ROTH_BENEFIT_FACTOR = 0.02  # 2% benefit per 10 years of backdoor contributions
DEFAULT_BACKDOOR_CONTRIBUTION_YEARS = 10  # Default years for backdoor Roth planning


class ConversionAfterTaxResult(NamedTuple):
    """Result of after-tax future value calculation for Roth conversion.
    
    Attributes:
        conversion_fv: Future value of conversion amount (grows tax-free in Roth)
        tax_fv: Future value of tax payment (opportunity cost in taxable account)
        after_tax_fv: Net after-tax future value (conversion_fv - tax_fv)
    """
    conversion_fv: float
    tax_fv: float
    after_tax_fv: float


@dataclass
class BETRInputs:
    """
    Input parameters for BETR calculation
    """
    # Current tax situation
    current_marginal_rate: float  # Current marginal tax rate (e.g., 0.24 for 24%)
    expected_future_rate: float   # Expected future marginal tax rate
    
    # Conversion details
    conversion_amount: float      # Amount to convert from Traditional to Roth
    traditional_ira_balance: float  # Total Traditional IRA balance
    nontaxable_basis: float = 0.0  # Nontaxable basis in Traditional IRA (after-tax contributions)
    
    # Tax payment source
    pay_from_taxable: bool = True  # True if paying conversion tax from taxable account
    taxable_account_balance: float = 0.0  # Balance in taxable account
    
    # Investment assumptions
    years_to_withdrawal: int = 20  # Years until withdrawal from Roth
    annual_return: float = 0.07    # Expected annual return (e.g., 0.07 for 7%)
    
    # Future planning
    future_backdoor_roth: bool = False  # Planning future backdoor Roth contributions
    backdoor_contribution_years: int = 0  # Years of future backdoor contributions
    wages: float = 0.0  # Annual wages (required for backdoor Roth contributions)
    
    # Tax year for bracket lookups (optional, defaults to current year)
    tax_year: Optional[int] = None  # Year for tax bracket data lookup

    # IRMAA cliff inputs (optional — leave at defaults if not yet on Medicare)
    magi_before_conversion: float = 0.0  # MAGI in tax_year *before* the conversion
    people_on_medicare: int = 0          # 0 = skip IRMAA check; 1 or 2 = apply surcharge


@dataclass
class BETRResults:
    """
    Results from BETR calculation
    """
    betr: float                    # Break-Even Tax Rate
    conversion_recommended: bool   # Whether conversion is recommended
    conversion_tax: float          # Tax owed on conversion
    net_benefit: float            # Net benefit of conversion (present value)
    
    # Detailed breakdown
    traditional_future_value: float  # Future value if staying in Traditional IRA
    roth_future_value: float        # Future value after Roth conversion
    taxable_account_impact: float   # Impact on taxable account if paying from there
    
    # Analysis details
    analysis_notes: List[str]      # Detailed notes about the analysis

    # IRMAA cost (present value of incremental Medicare surcharge triggered by the conversion)
    irmaa_surcharge_pv: float = 0.0   # $0 when IRMAA is not applicable

def _validate_numeric_input(
    value,
    name: str,
    allow_negative: bool = False,
    integer_only: bool = False,
    min_value: Optional[float] = None
) -> None:
    """
    Validate numeric input parameters.
    
    Args:
        value: The value to validate
        name: Parameter name for error messages
        allow_negative: Whether negative values are allowed
        integer_only: Whether only integers are accepted
        min_value: Optional minimum value constraint
        
    Raises:
        TypeError: If value is not of the correct numeric type
        ValueError: If value violates constraints
    """
    expected_type = numbers.Integral if integer_only else numbers.Real
    if not isinstance(value, expected_type):
        type_name = "integer" if integer_only else "numeric"
        raise TypeError(f"{name} must be {type_name}, got {type(value).__name__}")
    
    if not allow_negative and value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")
    
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")




def calculate_conversion_future_value(
    conversion_amount: float,
    annual_return: float,
    years: int
) -> float:
    """
    Calculate the future value of a conversion amount with compound growth.
    
    Formula: FV = PV × (1 + r)^n
    Where:
        FV = Future Value
        PV = Present Value (conversion amount)
        r = Annual rate of return
        n = Number of years
    
    Examples:
        Positive return:
            conversion_amount = 10000
            annual_return = 0.06 (6%)
            years = 20
            Result: 10000 × (1.06)^20 = 32,071.35
        
        Negative return:
            conversion_amount = 10000
            annual_return = -0.10 (-10% annual loss)
            years = 5
            Result: 10000 × (0.90)^5 = 5,904.90
    
    Args:
        conversion_amount: Initial conversion amount (Present Value)
        annual_return: Annual rate of return as decimal (e.g., 0.06 for 6%)
        years: Number of years to compound
        
    Returns:
        Future value after compound growth
        
    Raises:
        TypeError: If inputs are not of the correct type
        ValueError: If inputs are invalid
    """
    # Validate all inputs via shared helper (neutral tax rate — not applicable here)
    _validate_conversion_inputs(conversion_amount, years, annual_return, 0.0)
    
    # Short-circuit for zero years or zero growth
    if years <= 0 or annual_return == 0:
        logger.debug(
            f"No growth period or zero rate: returning conversion amount ${conversion_amount:,.2f}"
        )
        return conversion_amount
    
    # Calculate compound growth: FV = PV × (1 + r)^n
    growth_factor = (1 + annual_return) ** years
    
    logger.debug(
        f"Conversion FV calculation: ${conversion_amount:,.2f} × {growth_factor:.6f} "
        f"({annual_return * 100:.2f}% over {years} years) = ${conversion_amount * growth_factor:,.2f}"
    )
    
    return conversion_amount * growth_factor


def calculate_conversion_tax(
    conversion_amount: float,
    ordinary_income_tax_rate: float
) -> float:
    """
    Calculate the tax owed on a Roth conversion.
    
    Formula: Conversion Tax = Conversion Amount × Ordinary Income Tax Rate
    
    The conversion is treated as ordinary income and taxed at the current
    marginal tax rate in the year of conversion.
    
    Example:
        conversion_amount = 50000
        ordinary_income_tax_rate = 0.24 (24%)
        Result: 50000 × 0.24 = $12,000
    
    Args:
        conversion_amount: Amount being converted from Traditional to Roth IRA
        ordinary_income_tax_rate: Current marginal ordinary income tax rate as decimal
                                  (e.g., 0.24 for 24%)
        
    Returns:
        Tax owed on the conversion
        
    Raises:
        ValueError: If inputs are invalid
    """
    if conversion_amount < 0:
        raise ValueError(f"Conversion amount must be non-negative, got ${conversion_amount:,.2f}")
    
    if not 0 <= ordinary_income_tax_rate <= 1:
        raise ValueError(
            f"Ordinary income tax rate must be between 0 and 1, got {ordinary_income_tax_rate}"
        )
    
    # Calculate conversion tax: Tax = Amount × Rate
    conversion_tax = conversion_amount * ordinary_income_tax_rate
    
    logger.debug(
        f"Conversion tax calculation: ${conversion_amount:,.2f} × {ordinary_income_tax_rate:.2%} "
        f"= ${conversion_tax:,.2f}"
    )
    
    return conversion_tax


def _validate_conversion_inputs(
    conversion_amount: float,
    years: int,
    annual_return: float,
    ordinary_income_tax_rate: float
) -> None:
    """
    Validate inputs for conversion calculations.
    
    Args:
        conversion_amount: Amount being converted
        years: Number of years (must be a whole-number integer)
        annual_return: Annual rate of return
        ordinary_income_tax_rate: Tax rate as decimal
        
    Raises:
        TypeError: If years is not an integer type
        ValueError: If any input is invalid
    """
    if conversion_amount < 0:
        raise ValueError(f"Conversion amount must be non-negative, got ${conversion_amount:,.2f}")
    
    if not isinstance(years, numbers.Integral):
        raise TypeError(f"years must be integer, got {type(years).__name__}")
    
    if years < 0:
        raise ValueError(f"Years must be non-negative, got {years}")
    
    if annual_return < -1:
        raise ValueError(f"Annual return must be >= -1 (cannot lose more than 100%), got {annual_return}")
    
    if not 0 <= ordinary_income_tax_rate <= 1:
        raise ValueError(
            f"Ordinary income tax rate must be between 0 and 1, got {ordinary_income_tax_rate}"
        )


def _calculate_after_tax_growth_factor(
    annual_return: float,
    tax_rate: float,
    years: int
) -> float:
    """
    Calculate growth factor for taxable account with after-tax returns.
    
    In a taxable account, investment gains are subject to ongoing taxation,
    so the effective growth rate is reduced by the tax rate.
    
    Formula: (1 + r × (1 - tax_rate))^years
    
    Args:
        annual_return: Annual rate of return as decimal (e.g., 0.06 for 6%)
        tax_rate: Tax rate as decimal (e.g., 0.35 for 35%)
        years: Number of years of growth
        
    Returns:
        Growth factor for after-tax returns
    """
    after_tax_return = annual_return * (1 - tax_rate)
    return (1 + after_tax_return) ** years


def calculate_conversion_after_tax_future_value(
    conversion_amount: float,
    annual_return: float,
    years: int,
    ordinary_income_tax_rate: float
) -> ConversionAfterTaxResult:
    """
    Calculate the future after-tax value of a Roth conversion.
    
    This function projects the net benefit of a Roth conversion by calculating:
    1. Future value of the conversion amount (grows tax-free in Roth)
    2. Future value of the conversion tax (opportunity cost in taxable account)
    3. Net after-tax future value (conversion FV - tax FV)
    
    The key insight is that the tax payment would grow at an AFTER-TAX rate in a
    taxable account, not the full pre-tax rate, because investment gains in taxable
    accounts are subject to ongoing taxation.
    
    Formula:
        Conversion FV = Conversion Amount × (1 + r)^n
        Tax Amount = Conversion Amount × Tax Rate
        After-Tax Return = r × (1 - Tax Rate)
        Tax FV = Tax Amount × [1 + (r × (1 - Tax Rate))]^n
        After-Tax FV = Conversion FV - Tax FV
    
    Example:
        conversion_amount = 10000
        annual_return = 0.06 (6%)
        years = 20
        ordinary_income_tax_rate = 0.35 (35%)
        
        Conversion FV: 10000 × (1.06)^20 = $32,071
        Tax Amount: 10000 × 0.35 = $3,500
        After-Tax Return: 0.06 × (1 - 0.35) = 0.039 (3.9%)
        Tax FV: 3500 × [1 + 0.039]^20 = 3500 × 2.1495 = $7,523
        After-Tax FV: 32071 - 7523 = $24,549
    
    Args:
        conversion_amount: Amount being converted from Traditional to Roth IRA
        annual_return: Annual rate of return as decimal (e.g., 0.06 for 6%)
        years: Number of years until withdrawal
        ordinary_income_tax_rate: Current marginal tax rate as decimal (e.g., 0.35 for 35%)
        
    Returns:
        ConversionAfterTaxResult with conversion_fv, tax_fv, and after_tax_fv
        
    Raises:
        ValueError: If inputs are invalid
    """
    # Validate inputs using helper function
    _validate_conversion_inputs(conversion_amount, years, annual_return, ordinary_income_tax_rate)
    
    # Early return for zero cases (optimization)
    if conversion_amount == 0 or years == 0:
        return ConversionAfterTaxResult(
            conversion_fv=conversion_amount,
            tax_fv=0.0,
            after_tax_fv=conversion_amount
        )
    
    # Calculate future value of conversion (grows tax-free in Roth)
    # Inlined: FV = PV × (1 + r)^n
    growth_factor: float = (1 + annual_return) ** years
    conversion_fv: float = conversion_amount * growth_factor
    
    # Calculate conversion tax amount
    # Inlined: Tax = Amount × Rate
    tax_amount: float = conversion_amount * ordinary_income_tax_rate
    
    # Calculate future value of tax using AFTER-TAX return
    # The tax payment would be in a taxable account, so it grows at an after-tax rate
    after_tax_growth_factor: float = _calculate_after_tax_growth_factor(
        annual_return, ordinary_income_tax_rate, years
    )
    tax_fv: float = tax_amount * after_tax_growth_factor
    
    # Calculate net after-tax future value
    after_tax_fv: float = conversion_fv - tax_fv
    
    # Validate numerical stability
    if not np.isfinite(after_tax_fv):
        raise ValueError(
            f"Invalid calculation result: after_tax_fv={after_tax_fv}, "
            f"conversion_fv={conversion_fv}, tax_fv={tax_fv}"
        )
    
    logger.debug(
        f"After-tax FV calculation: ${after_tax_fv:,.2f} "
        f"(Conversion FV: ${conversion_fv:,.2f} - Tax FV: ${tax_fv:,.2f}) | "
        f"Input: ${conversion_amount:,.2f} over {years} years at {annual_return * 100:.2f}%, "
        f"tax rate: {ordinary_income_tax_rate * 100:.2f}%"
    )
    
    return ConversionAfterTaxResult(
        conversion_fv=conversion_fv,
        tax_fv=tax_fv,
        after_tax_fv=after_tax_fv
    )


def calculate_betr_rate(
    conversion_amount: float,
    annual_return: float,
    years: int,
    ordinary_income_tax_rate: float
) -> float:
    """
    Calculate the Break-Even Tax Rate (BETR) for a Roth conversion.
    
    The BETR represents the future tax rate at which an investor would be indifferent
    between converting to a Roth IRA now versus keeping funds in a Traditional IRA.
    
    Formula:
        BETR = 1 - (After-Tax FV / Conversion FV)
    
    Where:
        - After-Tax FV = Net future value after accounting for tax opportunity cost
        - Conversion FV = Future value of conversion amount (tax-free growth in Roth)
    
    The BETR shows the threshold future tax rate. If your expected future tax rate
    exceeds the BETR, the Roth conversion is beneficial.
    
    Example:
        conversion_amount = 10000
        annual_return = 0.06 (6%)
        years = 20
        ordinary_income_tax_rate = 0.35 (35%)
        
        Conversion FV: $32,071
        After-Tax FV: $24,549
        BETR: 1 - (24549 / 32071) = 1 - 0.7654 = 0.2346 or 23.46%
        
        Interpretation: If your future tax rate is above 23.46%, the conversion
        is beneficial. If below, you're better off staying in Traditional IRA.
    
    Args:
        conversion_amount: Amount being converted from Traditional to Roth IRA
        annual_return: Annual rate of return as decimal (e.g., 0.06 for 6%)
        years: Number of years until withdrawal
        ordinary_income_tax_rate: Current marginal tax rate as decimal (e.g., 0.35 for 35%)
        
    Returns:
        BETR as a decimal (e.g., 0.2346 for 23.46%)
        
    Raises:
        ValueError: If inputs are invalid
    """
    # Validate inputs explicitly for defense-in-depth
    _validate_conversion_inputs(conversion_amount, years, annual_return, ordinary_income_tax_rate)

    # Guard against zero-denominator: conversion_fv = 0 when conversion_amount = 0,
    # which would cause ZeroDivisionError in the BETR formula below.
    if conversion_amount == 0:
        raise ValueError("conversion_amount must be positive for BETR calculation")
    # Semantic guard: years = 0 means no growth period, making BETR = 0% — economically
    # meaningless and not a valid input for a conversion decision.
    if years == 0:
        raise ValueError("years must be positive for BETR calculation")

    # Calculate the after-tax future value components
    result = calculate_conversion_after_tax_future_value(
        conversion_amount, annual_return, years, ordinary_income_tax_rate
    )

    # Guard against zero/negative conversion_fv before dividing.
    # conversion_fv = conversion_amount * (1 + annual_return)^years reaches zero
    # when annual_return == -1.0 (total loss), which passes _validate_conversion_inputs.
    if result.conversion_fv <= 0:
        raise ValueError(
            f"conversion_fv={result.conversion_fv:,.6f} is non-positive "
            f"(annual_return={annual_return}, years={years}); "
            "BETR is undefined for a total-loss return assumption."
        )

    # Calculate BETR: 1 - (After-Tax FV / Conversion FV)
    betr = 1 - (result.after_tax_fv / result.conversion_fv)

    # Log consolidated calculation details at DEBUG — this is a mid-level helper;
    # top-level callers (calculate_betr) log at INFO.
    logger.debug(
        f"BETR calculation: After-Tax FV=${result.after_tax_fv:,.2f}, "
        f"Conversion FV=${result.conversion_fv:,.2f}, "
        f"BETR=1-({result.after_tax_fv:,.2f}/{result.conversion_fv:,.2f})={betr:.4%} "
        f"(Convert if future tax rate > {betr:.2%})"
    )

    return betr


def _get_ltcg_rate(income: float, year: int) -> float:
    """
    Get the long-term capital gains tax rate based on income level.
    
    Args:
        income: Income level (AGI or taxable income)
        year: Tax year for bracket lookup
        
    Returns:
        LTCG rate (0.0, 0.15, or 0.20)
    """
    try:
        _filing_status = _betr_get_config_manager().get_filing_status()
        cap_gains_df = get_cap_gains_brackets(year, _filing_status)
        
        # Find the applicable bracket
        for _, row in cap_gains_df.iterrows():
            if row['lower'] <= income < row['upper']:
                return float(row['rate'])
        
        # If income exceeds all brackets, return highest rate
        return 0.20
    except (OSError, KeyError, ValueError) as e:
        logger.warning(f"Could not lookup LTCG rate for year {year}, using 15% default: {e}", exc_info=True)
        return 0.15  # Conservative default


def _calculate_irmaa_conversion_cost(
    magi_before: float,
    conversion_amount: float,
    people: int,
    tax_year: int,
    annual_return: float,
) -> Tuple[float, str]:
    """Return the present-value cost of the incremental IRMAA surcharge triggered
    by adding *conversion_amount* to MAGI.

    Background
    ----------
    IRMAA is assessed two years in arrears: a conversion in *tax_year* affects
    Medicare premiums in *tax_year + 2*.  The surcharge applies for exactly one
    calendar year (the premium year), so the PV is simply the incremental annual
    surcharge discounted back two years at *annual_return*.

    The function tries to look up IRMAA brackets for *tax_year + 2* from the
    data file; if that year is absent it falls back to the most recent available
    year (IRMAA brackets are projected forward in irmaa.csv several years).

    Args:
        magi_before:       MAGI *before* the Roth conversion (in tax_year).
        conversion_amount: Size of the conversion (added to MAGI for IRMAA).
        people:            Number of people on Medicare (1 or 2).
        tax_year:          The year the conversion is made.
        annual_return:     Discount rate (same as the portfolio return assumption).

    Returns:
        Tuple of (present_value_cost, human_readable_note).
        Returns (0.0, '') when no incremental IRMAA is triggered.
    """
    if people <= 0 or magi_before < 0 or conversion_amount <= 0:
        return 0.0, ''

    magi_after = magi_before + conversion_amount
    irmaa_year = tax_year + 2  # Two-year look-back rule

    # Load IRMAA brackets for the premium year; fall back to the latest available year.
    try:
        brackets = get_medicare_costs(irmaa_year)
        if brackets.empty:
            # Year not in CSV — use the highest year present
            import pandas as _pd
            all_brackets = _pd.read_csv('irmaa.csv')
            latest_year = int(all_brackets['year'].max())
            brackets = get_medicare_costs(latest_year)
            if brackets.empty:
                logger.warning("IRMAA data unavailable — skipping IRMAA cost in BETR")
                return 0.0, ''
            logger.debug(
                f"IRMAA brackets for {irmaa_year} not found; using {latest_year} as proxy"
            )
    except (OSError, KeyError, ValueError) as exc:
        logger.warning(f"Could not load IRMAA data: {exc} — skipping IRMAA cost in BETR", exc_info=True)
        return 0.0, ''

    # Build a slim lookup DataFrame containing only the three columns that
    # calculate_irmma_penalty expects: lower, upper, part_b_monthly.
    # We combine Part B + Part D surcharges so the full Medicare cost increase
    # is captured (Part D IRMAA is a meaningful additional cost at higher brackets).
    brackets = brackets.copy()
    if 'part_d_irmaa_monthly' in brackets.columns:
        brackets['part_b_monthly'] = (
            brackets['part_b_monthly'] + brackets['part_d_irmaa_monthly']
        )
    lookup = brackets[['lower', 'upper', 'part_b_monthly']].copy()

    annual_before = calculate_irmma_penalty(magi_before, lookup, people)
    annual_after  = calculate_irmma_penalty(magi_after,  lookup, people)
    annual_delta  = annual_after - annual_before

    if annual_delta <= 0:
        return 0.0, ''

    # Discount the one-year surcharge back two years (it hits in tax_year + 2)
    discount_factor = (1 + annual_return) ** 2
    pv_cost = annual_delta / discount_factor

    note = (
        f"IRMAA cliff: conversion raises MAGI from ${magi_before:,.0f} to "
        f"${magi_after:,.0f}, triggering an incremental Medicare surcharge of "
        f"${annual_delta:,.0f}/yr in {irmaa_year} "
        f"(PV cost = ${pv_cost:,.0f} discounted at {annual_return:.1%})"
    )
    logger.info(f"IRMAA conversion cost: annual_delta=${annual_delta:,.2f}, PV=${pv_cost:,.2f}")
    return pv_cost, note


def calculate_betr(inputs: BETRInputs) -> BETRResults:
    """
    Calculate the Break-Even Tax Rate (BETR) for a Roth conversion.
    
    The BETR represents the future tax rate at which an investor would be indifferent
    between converting to a Roth IRA now versus keeping funds in a Traditional IRA.
    
    Key Formula Components:
    - If paying from taxable account: BETR accounts for moving tax-free dollars to Roth
    - If paying from IRA: BETR is lower since conversion reduces IRA assets
    - Nontaxable basis: Increases BETR since less of conversion is taxable
    - Backdoor Roth: Increases BETR by enabling future tax-free contributions
    
    Args:
        inputs: BETRInputs dataclass with all required parameters
        
    Returns:
        BETRResults dataclass with BETR and detailed analysis
        
    Raises:
        ValueError: If input parameters are invalid
    """
    # Input validation
    if inputs.conversion_amount <= 0:
        raise ValueError(f"Conversion amount must be positive, got ${inputs.conversion_amount:,.2f}")
    
    if inputs.traditional_ira_balance <= 0:
        raise ValueError(f"Traditional IRA balance must be positive, got ${inputs.traditional_ira_balance:,.2f}")
    
    if inputs.conversion_amount > inputs.traditional_ira_balance:
        raise ValueError(
            f"Conversion amount (${inputs.conversion_amount:,.2f}) cannot exceed "
            f"Traditional IRA balance (${inputs.traditional_ira_balance:,.2f})"
        )
    
    if not 0 <= inputs.current_marginal_rate <= 1:
        raise ValueError(f"Current marginal rate must be between 0 and 1, got {inputs.current_marginal_rate}")
    
    if not 0 <= inputs.expected_future_rate <= 1:
        raise ValueError(f"Expected future rate must be between 0 and 1, got {inputs.expected_future_rate}")
    
    if inputs.nontaxable_basis < 0:
        raise ValueError(f"Nontaxable basis cannot be negative, got ${inputs.nontaxable_basis:,.2f}")
    
    if inputs.nontaxable_basis > inputs.traditional_ira_balance:
        raise ValueError(
            f"Nontaxable basis (${inputs.nontaxable_basis:,.2f}) cannot exceed "
            f"Traditional IRA balance (${inputs.traditional_ira_balance:,.2f})"
        )
    
    if inputs.pay_from_taxable and inputs.taxable_account_balance < 0:
        raise ValueError(f"Taxable account balance cannot be negative, got ${inputs.taxable_account_balance:,.2f}")
    
    if inputs.years_to_withdrawal <= 0:
        raise ValueError(f"Years to withdrawal must be positive, got {inputs.years_to_withdrawal}")
    
    if not -1 <= inputs.annual_return <= 1:
        raise ValueError(f"Annual return must be between -1 and 1, got {inputs.annual_return}")
    
    if inputs.backdoor_contribution_years < 0:
        raise ValueError(f"Backdoor contribution years cannot be negative, got {inputs.backdoor_contribution_years}")
    
    logger.info(f"=== Starting BETR Calculation for ${inputs.conversion_amount:,.0f} conversion ===")
    logger.info(f"Tax payment source: {'Taxable Account' if inputs.pay_from_taxable else 'IRA Assets'}")
    
    analysis_notes = []
    
    # Determine tax year for lookups
    tax_year = inputs.tax_year if inputs.tax_year is not None else datetime.now().year
    
    # Step 1: Calculate conversion tax using helper function
    logger.info("--- Step 1: Calculate Conversion Tax ---")
    
    # Adjust for nontaxable basis (reduces taxable portion)
    if inputs.nontaxable_basis > 0:
        nontaxable_percentage = inputs.nontaxable_basis / inputs.traditional_ira_balance
        taxable_portion = inputs.conversion_amount * (1 - nontaxable_percentage)
        conversion_tax = calculate_conversion_tax(taxable_portion, inputs.current_marginal_rate)
        logger.info(f"Nontaxable basis adjustment: {nontaxable_percentage:.2%} of IRA is nontaxable")
        logger.info(f"Taxable portion: ${taxable_portion:,.2f}")
        logger.info(f"Conversion tax: ${conversion_tax:,.2f} (${taxable_portion:,.0f} × {inputs.current_marginal_rate:.2%})")
        analysis_notes.append(
            f"Nontaxable basis of ${inputs.nontaxable_basis:,.0f} reduces taxable conversion to ${taxable_portion:,.0f}"
        )
    else:
        conversion_tax = calculate_conversion_tax(inputs.conversion_amount, inputs.current_marginal_rate)
        logger.info(f"Conversion tax: ${conversion_tax:,.2f} (${inputs.conversion_amount:,.0f} × {inputs.current_marginal_rate:.2%})")
    
    logger.info(f"Step 1 Result - Conversion tax: ${conversion_tax:,.2f}")
    
    # Step 2: Calculate future value in Traditional IRA (no conversion scenario) using helper function
    logger.info("--- Step 2: Calculate Traditional IRA Future Value (No Conversion) ---")
    traditional_future_gross = calculate_conversion_future_value(
        inputs.conversion_amount,
        inputs.annual_return,
        inputs.years_to_withdrawal
    )
    logger.info(f"Traditional future gross: ${traditional_future_gross:,.2f}")
    logger.info(f"  (${inputs.conversion_amount:,.0f} × (1 + {inputs.annual_return:.2%})^{inputs.years_to_withdrawal})")
    
    # Future withdrawal from Traditional IRA will be taxed at future rate
    traditional_future_net = traditional_future_gross * (1 - inputs.expected_future_rate)
    logger.info(f"Traditional future net (after {inputs.expected_future_rate:.2%} tax): ${traditional_future_net:,.2f}")
    logger.info(f"Step 2 Result - Traditional future gross: ${traditional_future_gross:,.2f}, net: ${traditional_future_net:,.2f}")
    
    # Step 3: Calculate future value in Roth IRA (conversion scenario) using helper function
    logger.info("--- Step 3: Calculate Roth IRA Future Value (With Conversion) ---")
    if inputs.pay_from_taxable:
        logger.info("Tax payment from TAXABLE account")
        
        # Use the after-tax future value calculation which accounts for opportunity cost
        roth_future_value, tax_fv, roth_future_net = calculate_conversion_after_tax_future_value(
            inputs.conversion_amount,
            inputs.annual_return,
            inputs.years_to_withdrawal,
            inputs.current_marginal_rate
        )
        
        logger.info(f"Roth future value (full conversion grows tax-free): ${roth_future_value:,.2f}")
        logger.info(f"Tax FV (opportunity cost in taxable account): ${tax_fv:,.2f}")
        logger.info(f"Roth future net (after opportunity cost): ${roth_future_net:,.2f}")
        
        analysis_notes.append(
            f"Paying ${conversion_tax:,.0f} tax from taxable account. "
            f"Opportunity cost: ${tax_fv:,.0f}"
        )
    else:
        logger.info("Tax payment from IRA assets")
        # Paying from IRA - reduces amount that can be converted
        net_conversion = inputs.conversion_amount - conversion_tax
        roth_future_value = calculate_conversion_future_value(
            net_conversion,
            inputs.annual_return,
            inputs.years_to_withdrawal
        )
        roth_future_net = roth_future_value  # Already tax-free, no opportunity cost
        logger.info(f"Net conversion after tax: ${net_conversion:,.2f}")
        logger.info(f"Roth future value: ${roth_future_value:,.2f}")
        
        analysis_notes.append(
            f"Paying ${conversion_tax:,.0f} tax from IRA. "
            f"Net conversion: ${net_conversion:,.0f}"
        )
    
    logger.info(f"Step 3 Result - Roth future net: ${roth_future_net:,.2f}")
    
    # Step 4: Calculate Base BETR
    logger.info("--- Step 4: Calculate Base BETR ---")
    # BETR calculation depends on payment source
    if inputs.pay_from_taxable:
        # When paying from taxable account, use the standard BETR formula
        # This accounts for the opportunity cost of the tax payment
        betr = calculate_betr_rate(
            inputs.conversion_amount,
            inputs.annual_return,
            inputs.years_to_withdrawal,
            inputs.current_marginal_rate
        )
        logger.info(f"Base BETR (paying from taxable): {betr:.4%}")
        logger.info(f"Formula: BETR = 1 - (After-Tax FV / Conversion FV)")
    else:
        # When paying from IRA, the effective BETR is higher because
        # you're giving up IRA dollars that would have grown tax-deferred
        # The comparison is: Roth FV vs Traditional FV (both net of taxes)
        # BETR = 1 - (Roth Net FV / Traditional Gross FV)
        if traditional_future_gross > 0:
            betr = 1 - (roth_future_net / traditional_future_gross)
            logger.info(f"Base BETR (paying from IRA): {betr:.4%}")
            logger.info(f"Formula: BETR = 1 - (Roth Net FV / Traditional Gross FV)")
            logger.info(f"  = 1 - (${roth_future_net:,.2f} / ${traditional_future_gross:,.2f})")
        else:
            betr = calculate_betr_rate(
                inputs.conversion_amount,
                inputs.annual_return,
                inputs.years_to_withdrawal,
                inputs.current_marginal_rate
            )
            logger.info(f"Base BETR (no growth): {betr:.4%}")
    
    logger.info(f"Step 4 Result - Base BETR: {betr:.4%}")

    # Step 4b: Adjust BETR for IRMAA cliff cost
    # A Roth conversion raises MAGI in tax_year; under the two-year look-back rule
    # IRMAA premiums increase in tax_year+2.  We compute the PV of that one-year
    # surcharge (Part B + Part D) and reduce the effective Roth future value by it,
    # which raises the BETR threshold to properly account for this hidden cost.
    logger.info("--- Step 4b: Adjust BETR for IRMAA Cliff Cost ---")
    irmaa_pv = 0.0
    if inputs.people_on_medicare > 0 and inputs.magi_before_conversion > 0:
        irmaa_pv, irmaa_note = _calculate_irmaa_conversion_cost(
            magi_before=inputs.magi_before_conversion,
            conversion_amount=inputs.conversion_amount,
            people=inputs.people_on_medicare,
            tax_year=tax_year,
            annual_return=inputs.annual_return,
        )
        if irmaa_pv > 0:
            # Reduce the effective after-tax Roth future value so the BETR formula
            # absorbs the Medicare cost.  The adjustment mirrors how conversion_tax
            # is already embedded in roth_future_net via the opportunity-cost path.
            if inputs.pay_from_taxable:
                _atfv = calculate_conversion_after_tax_future_value(
                    inputs.conversion_amount,
                    inputs.annual_return,
                    inputs.years_to_withdrawal,
                    inputs.current_marginal_rate,
                )
                if _atfv.conversion_fv > 0:
                    betr = 1 - (
                        (_atfv.after_tax_fv - irmaa_pv) / _atfv.conversion_fv
                    )
            else:
                # Paying from IRA path: deduct IRMAA PV from roth_future_net
                roth_future_net_adj = roth_future_net - irmaa_pv
                if traditional_future_gross > 0:
                    betr = 1 - (roth_future_net_adj / traditional_future_gross)
            analysis_notes.append(irmaa_note)
            logger.info(f"IRMAA adjustment applied: PV=${irmaa_pv:,.2f}, BETR → {betr:.4%}")
        else:
            logger.info("No IRMAA bracket change triggered by this conversion")
    else:
        logger.info("IRMAA check skipped (people_on_medicare=0 or no magi_before_conversion)")

    logger.info(f"Step 4b Result - BETR after IRMAA adjustment: {betr:.4%}")

    # Step 5: Adjust BETR for nontaxable basis
    logger.info("--- Step 5: Adjust BETR for Nontaxable Basis ---")
    if inputs.nontaxable_basis > 0:
        # Higher nontaxable basis increases BETR (makes conversion more attractive)
        # The adjustment is proportional to the percentage of nontaxable basis
        basis_percentage = inputs.nontaxable_basis / inputs.traditional_ira_balance
        basis_adjustment = basis_percentage * NONTAXABLE_BASIS_ADJUSTMENT_FACTOR
        betr_before = betr
        betr += basis_adjustment
        logger.info(f"Nontaxable basis: {basis_percentage:.2%} of IRA balance")
        logger.info(f"Basis adjustment: +{basis_adjustment:.4%} (BETR: {betr_before:.4%} → {betr:.4%})")
        analysis_notes.append(
            f"BETR increased by {basis_adjustment:.2%} due to {basis_percentage:.1%} nontaxable basis"
        )
    else:
        logger.info("No nontaxable basis adjustment (basis = $0)")
    
    logger.info(f"Step 5 Result - BETR after basis adjustment: {betr:.4%}")
    
    # Step 6: Adjust BETR for future backdoor Roth contributions
    logger.info("--- Step 6: Adjust BETR for Future Backdoor Roth Contributions ---")
    # Consider backdoor Roth if planning future contributions
    # Note: Backdoor Roth typically requires wages, but we apply the adjustment if planned
    # even without explicit wage information (assumes user has or will have wages)
    if inputs.future_backdoor_roth and inputs.backdoor_contribution_years > 0:
        # Converting now enables future backdoor Roth contributions by eliminating pro-rata rule
        # This increases the BETR (makes conversion more attractive)
        # Benefit scales with number of years of future contributions
        backdoor_benefit = BACKDOOR_ROTH_BENEFIT_FACTOR * (inputs.backdoor_contribution_years / 10)
        betr_before = betr
        betr += backdoor_benefit
        if inputs.wages > 0:
            logger.info(f"Wages: ${inputs.wages:,.0f} (backdoor Roth eligible)")
        else:
            logger.info("Backdoor Roth planned (assuming future wage income)")
        logger.info(f"Backdoor Roth benefit: +{backdoor_benefit:.4%} for {inputs.backdoor_contribution_years} years")
        logger.info(f"Backdoor adjustment (BETR: {betr_before:.4%} → {betr:.4%})")
        analysis_notes.append(
            f"BETR increased by {backdoor_benefit:.2%} due to {inputs.backdoor_contribution_years} "
            f"years of future backdoor Roth contributions"
        )
    else:
        logger.info("No backdoor Roth adjustment (not planning future backdoor contributions)")
    
    logger.info(f"Step 6 Result - BETR after backdoor adjustment: {betr:.4%}")
    
    # Step 7: Calculate net benefit
    logger.info("--- Step 7: Calculate Net Benefit ---")
    net_benefit = roth_future_net - traditional_future_net
    logger.info(f"Net benefit: ${net_benefit:,.2f} (Roth: ${roth_future_net:,.2f} - Traditional: ${traditional_future_net:,.2f})")
    logger.info(f"Step 7 Result - Net benefit: ${net_benefit:,.2f}")
    
    # Step 8: Determine recommendation
    logger.info("--- Step 8: Determine Recommendation ---")
    # Conversion is recommended if expected future tax rate > BETR
    # BETR is the break-even point - if future rate exceeds it, conversion is beneficial
    conversion_recommended = inputs.expected_future_rate > betr
    logger.info(f"Expected future rate: {inputs.expected_future_rate:.4%}")
    logger.info(f"Final BETR: {betr:.4%}")
    logger.info(f"Comparison: {inputs.expected_future_rate:.4%} {'>' if conversion_recommended else '≤'} {betr:.4%}")
    
    if conversion_recommended:
        logger.info("✓ CONVERSION RECOMMENDED")
        analysis_notes.append(
            f"✓ CONVERSION RECOMMENDED: Expected Future Rate ({inputs.expected_future_rate:.2%}) > BETR ({betr:.2%})"
        )
        analysis_notes.append(
            f"Conversion is beneficial because your expected future tax rate exceeds the break-even rate"
        )
    else:
        logger.info("✗ CONVERSION NOT RECOMMENDED")
        analysis_notes.append(
            f"✗ CONVERSION NOT RECOMMENDED: Expected Future Rate ({inputs.expected_future_rate:.2%}) ≤ BETR ({betr:.2%})"
        )
        analysis_notes.append(
            f"Conversion not beneficial unless future tax rate exceeds {betr:.2%}"
        )
    
    logger.info(f"Step 8 Result - Recommendation: {'CONVERT' if conversion_recommended else 'DO NOT CONVERT'}")
    logger.info(f"=== BETR Calculation Complete: {betr:.4%} ===")
    
    return BETRResults(
        betr=betr,
        conversion_recommended=conversion_recommended,
        conversion_tax=conversion_tax,
        net_benefit=net_benefit,
        traditional_future_value=traditional_future_net,
        roth_future_value=roth_future_net,
        taxable_account_impact=conversion_tax if inputs.pay_from_taxable else 0,
        irmaa_surcharge_pv=irmaa_pv,
        analysis_notes=analysis_notes
    )


@lru_cache(maxsize=10)
def _get_cached_tax_brackets(year: int) -> pd.DataFrame:
    """
    Cache tax brackets by year to avoid repeated lookups.
    
    Args:
        year: Tax year for bracket lookup
        
    Returns:
        DataFrame containing tax brackets for the specified year
    """
    # Bracket upper-limit lookups are filing-status-agnostic for optimization
    # purposes (the bracket structure is the same across MFJ); use a stable
    # default so @lru_cache behaves correctly across test contexts.
    return get_income_tax_brackets(year, 'married_filing_jointly')


@lru_cache(maxsize=128)
def _get_bracket_upper_limit(target_rate: float, year: int) -> Optional[float]:
    """
    Get upper income limit for target tax bracket.
    
    This function is cached since tax brackets are deterministic for a given year.
    
    Args:
        target_rate: Target marginal tax rate (e.g., 0.24 for 24%)
        year: Tax year for bracket lookup
        
    Returns:
        Upper income limit for the bracket, or None if bracket not found
    """
    try:
        tax_brackets_df = _get_cached_tax_brackets(year)
        return getUpperIncomeRate(target_rate, tax_brackets_df)
    except ValueError:
        logger.error(f"Target tax bracket {target_rate:.2%} not found")
        return None


def _create_empty_betr_result(error_message: str) -> BETRResults:
    """
    Create an empty BETR result for error cases.
    
    Args:
        error_message: Error message to include in analysis notes
        
    Returns:
        BETRResults with zero values and error message
    """
    return BETRResults(
        betr=0.0,
        conversion_recommended=False,
        conversion_tax=0.0,
        net_benefit=0.0,
        traditional_future_value=0.0,
        roth_future_value=0.0,
        taxable_account_impact=0.0,
        analysis_notes=[error_message]
    )


def _calculate_max_conversion_amount(
    bracket_upper_limit: float,
    current_agi: float,
    traditional_ira_balance: float
) -> float:
    """
    Calculate maximum conversion amount to stay within target bracket.
    
    Returns the lesser of:
    - Available room in tax bracket (bracket limit - current AGI)
    - Traditional IRA balance
    
    Args:
        bracket_upper_limit: Upper income limit of target tax bracket
        current_agi: Current Adjusted Gross Income
        traditional_ira_balance: Total Traditional IRA balance
        
    Returns:
        Maximum conversion amount that stays within bracket
    """
    available_room = max(0.0, bracket_upper_limit - current_agi)
    return min(available_room, traditional_ira_balance)


def _build_betr_inputs(
    target_tax_bracket: float,
    optimal_conversion: float,
    traditional_ira_balance: float,
    nontaxable_basis: float,
    pay_from_taxable: bool,
    taxable_account_balance: float,
    years_to_withdrawal: int,
    annual_return: float,
    future_backdoor_roth: bool,
    expected_future_rate: Optional[float] = None
) -> BETRInputs:
    """
    Build BETRInputs for BETR validation.
    
    Args:
        target_tax_bracket: Target marginal tax rate
        optimal_conversion: Calculated optimal conversion amount
        traditional_ira_balance: Total Traditional IRA balance
        nontaxable_basis: Nontaxable basis in Traditional IRA
        pay_from_taxable: Whether to pay conversion tax from taxable account
        taxable_account_balance: Balance in taxable account
        years_to_withdrawal: Years until withdrawal
        annual_return: Expected annual return
        future_backdoor_roth: Planning future backdoor Roth contributions
        expected_future_rate: Expected future marginal tax rate for BETR comparison.
            Defaults to ``target_tax_bracket`` when not provided (neutral assumption).
        
    Returns:
        BETRInputs configured for BETR analysis
    """
    if expected_future_rate is None:
        expected_future_rate = target_tax_bracket
    return BETRInputs(
        current_marginal_rate=target_tax_bracket,
        expected_future_rate=expected_future_rate,
        conversion_amount=optimal_conversion,
        traditional_ira_balance=traditional_ira_balance,
        nontaxable_basis=nontaxable_basis,
        pay_from_taxable=pay_from_taxable,
        taxable_account_balance=taxable_account_balance,
        years_to_withdrawal=years_to_withdrawal,
        annual_return=annual_return,
        future_backdoor_roth=future_backdoor_roth,
        backdoor_contribution_years=DEFAULT_BACKDOOR_CONTRIBUTION_YEARS if future_backdoor_roth else 0
    )


def _validate_taxable_account_sufficiency(
    optimal_conversion: float,
    target_tax_bracket: float,
    taxable_account_balance: float
) -> Optional[str]:
    """
    Validate that taxable account has sufficient balance to pay conversion tax.
    
    Args:
        optimal_conversion: Calculated optimal conversion amount
        target_tax_bracket: Target marginal tax rate for tax estimation
        taxable_account_balance: Balance in taxable account
        
    Returns:
        Error message if validation fails, None if sufficient balance
    """
    if optimal_conversion <= 0:
        return None
    
    estimated_tax = optimal_conversion * target_tax_bracket
    if estimated_tax > taxable_account_balance:
        logger.warning(
            f"Insufficient taxable account balance: ${taxable_account_balance:,.0f} "
            f"< estimated tax ${estimated_tax:,.0f}"
        )
        return "Error: Insufficient taxable account balance to pay conversion tax"
    
    return None


def _validate_optimization_inputs(
    traditional_ira_balance: float,
    current_agi: float,
    target_tax_bracket: float,
    nontaxable_basis: float,
    pay_from_taxable: bool,
    taxable_account_balance: float,
    years_to_withdrawal: int,
    annual_return: float,
    year: Optional[int] = None
) -> Optional[str]:
    """
    Validate inputs for optimize_conversion_amount using declarative validation rules.
    
    Args:
        traditional_ira_balance: Total Traditional IRA balance
        current_agi: Current Adjusted Gross Income
        target_tax_bracket: Target marginal tax rate
        nontaxable_basis: Nontaxable basis in Traditional IRA
        pay_from_taxable: Whether to pay conversion tax from taxable account
        taxable_account_balance: Balance in taxable account
        years_to_withdrawal: Years until withdrawal
        annual_return: Expected annual return
        year: Tax year for bracket lookup (must be an integer >= 2020)
        
    Returns:
        Error message if validation fails, None if all inputs are valid
    """
    # Define validation rules declaratively as (condition, message) pairs.
    # message may be a plain str or a zero-argument callable (lambda) for
    # formatted strings — lambdas are only evaluated on failure (lazy).
    # Rules are evaluated in order; the first failure returns immediately.
    #
    # Ordering rationale:
    #   1. Type checks (prevent misleading downstream TypeErrors)
    #   2. Single-field non-negative / positive checks (field-level, cheapest)
    #   3. Cross-field consistency check (requires valid individual fields)
    #   4. Percentage range checks (0 <= x <= 1, inclusive — consistent with
    #      _validate_conversion_inputs and calculate_conversion_tax)
    validations = [
        # --- Type checks ---
        (not isinstance(years_to_withdrawal, numbers.Integral),
         lambda: f"Years to withdrawal must be an integer, got {type(years_to_withdrawal).__name__}"),

        (year is not None and not isinstance(year, numbers.Integral),
         lambda: f"year must be an integer, got {type(year).__name__}"),

        (year is not None and year < 2020,
         lambda: f"year must be >= 2020, got {year}"),

        # --- Single-field positive / non-negative checks ---
        (years_to_withdrawal <= 0,
         "Years to withdrawal must be positive"),

        (traditional_ira_balance <= 0,
         "Traditional IRA balance must be positive"),

        (current_agi < 0,
         "Current AGI cannot be negative"),

        (nontaxable_basis < 0,
         "Nontaxable basis cannot be negative"),

        # Validated unconditionally: a negative balance is invalid regardless of
        # whether the caller intends to pay conversion tax from it.
        (taxable_account_balance < 0,
         "Taxable account balance cannot be negative"),

        # --- Cross-field consistency check (safe now that fields are valid) ---
        (nontaxable_basis > traditional_ira_balance,
         "Nontaxable basis cannot exceed Traditional IRA balance"),

        # --- Percentage range checks (inclusive boundaries, 0 and 1 are valid) ---
        (not (0 <= target_tax_bracket <= 1),
         lambda: f"Invalid tax bracket {target_tax_bracket:.2%} (must be between 0 and 1)"),

        (not (0 <= annual_return <= 1),
         lambda: f"Invalid annual return {annual_return:.2%} (must be between 0 and 1)"),
    ]

    # Return first validation error found; resolve lazy messages only on failure
    for condition, message in validations:
        if condition:
            return f"Error: {message() if callable(message) else message}"
    
    return None


def _optimization_error(message: str) -> Tuple[float, BETRResults]:
    """
    Return standard error response for optimization failures.
    
    Args:
        message: Error message to include in result
        
    Returns:
        Tuple of (0.0, empty BETRResults with error message)
    """
    return 0.0, _create_empty_betr_result(message)


def optimize_conversion_amount(
    traditional_ira_balance: float,
    current_agi: float,
    target_tax_bracket: float,
    year: int,
    pay_from_taxable: bool = True,
    taxable_account_balance: float = 0.0,
    nontaxable_basis: float = 0.0,
    years_to_withdrawal: int = 20,
    annual_return: float = 0.07,
    future_backdoor_roth: bool = False,
    expected_future_rate: Optional[float] = None
) -> Tuple[float, BETRResults]:
    """
    Optimize Roth conversion amount to stay within a target tax bracket using BETR analysis.
    
    This function determines the maximum conversion amount that keeps you within your
    target tax bracket, then validates it using BETR methodology.
    
    Args:
        traditional_ira_balance: Total Traditional IRA balance
        current_agi: Current Adjusted Gross Income
        target_tax_bracket: Target marginal tax rate to stay within (e.g., 0.24 for 24%)
        year: Tax year for bracket lookup
        pay_from_taxable: Whether to pay conversion tax from taxable account
        taxable_account_balance: Balance in taxable account
        nontaxable_basis: Nontaxable basis in Traditional IRA
        years_to_withdrawal: Years until withdrawal
        annual_return: Expected annual return
        future_backdoor_roth: Planning future backdoor Roth contributions
        expected_future_rate: Expected future marginal tax rate for BETR comparison.
            Defaults to ``target_tax_bracket`` when not provided (neutral assumption).
        
    Returns:
        Tuple of (optimal_conversion_amount, BETRResults)
    """
    # Validate all inputs
    if validation_error := _validate_optimization_inputs(
        traditional_ira_balance, current_agi, target_tax_bracket,
        nontaxable_basis, pay_from_taxable, taxable_account_balance,
        years_to_withdrawal, annual_return, year
    ):
        return _optimization_error(validation_error)
    
    logger.info(f"Optimizing conversion for target bracket: {target_tax_bracket:.2%}")
    
    # Get bracket upper limit (cached for performance)
    bracket_upper_limit = _get_bracket_upper_limit(target_tax_bracket, year)
    if bracket_upper_limit is None:
        return _optimization_error("Error: Target tax bracket not found")
    
    # Calculate optimal conversion amount
    optimal_conversion = _calculate_max_conversion_amount(
        bracket_upper_limit, current_agi, traditional_ira_balance
    )
    
    if optimal_conversion <= 0:
        logger.info('No conversion room available in target tax bracket')
        return 0.0, _create_empty_betr_result('No conversion room in target bracket')
    
    # Verify taxable account sufficiency if paying from taxable (guard clause)
    if pay_from_taxable and (error := _validate_taxable_account_sufficiency(
        optimal_conversion, target_tax_bracket, taxable_account_balance
    )):
        return _optimization_error(error)
    
    logger.info(f"Optimal conversion amount: ${optimal_conversion:,.0f}")
    
    # Build inputs and validate with BETR analysis
    betr_inputs = _build_betr_inputs(
        target_tax_bracket, optimal_conversion, traditional_ira_balance,
        nontaxable_basis, pay_from_taxable, taxable_account_balance,
        years_to_withdrawal, annual_return, future_backdoor_roth,
        expected_future_rate=expected_future_rate if expected_future_rate is not None else target_tax_bracket
    )
    
    betr_results = calculate_betr(betr_inputs)
    
    return optimal_conversion, betr_results

class ConversionScenarioResult(TypedDict):
    """Type definition for conversion scenario analysis results."""
    conversion_amount: float
    conversion_tax: float
    betr: float
    recommended: bool
    net_benefit: float
    roth_future_value: float
    traditional_future_value: float


def _validate_conversion_amounts(
    conversion_amounts: Sequence[float],
    traditional_ira_balance: float
) -> List[float]:
    """
    Validate and filter conversion amounts.
    
    Args:
        conversion_amounts: Sequence of conversion amounts to validate
        traditional_ira_balance: Total Traditional IRA balance for validation
        
    Returns:
        List of valid conversion amounts (filtered and validated)
        
    Raises:
        TypeError: If conversion_amounts is not a sequence
        ValueError: If conversion_amounts contains invalid values
    """
    # Type validation
    if not isinstance(conversion_amounts, (list, tuple)):
        raise TypeError(
            f"conversion_amounts must be a list or tuple, got {type(conversion_amounts).__name__}"
        )

    # Early return for empty sequence
    if not conversion_amounts:
        logger.warning("No conversion amounts provided")
        return []

    # Value validation
    if any(not isinstance(amt, numbers.Real) or amt <= 0
           for amt in conversion_amounts):
        raise ValueError("All conversion amounts must be positive numbers")
    
    # Filter amounts exceeding IRA balance
    valid_amounts = [amt for amt in conversion_amounts if amt <= traditional_ira_balance]
    invalid_count = len(conversion_amounts) - len(valid_amounts)
    
    if invalid_count > 0:
        logger.warning(
            f"Skipping {invalid_count} amount(s) exceeding IRA balance of ${traditional_ira_balance:,.0f}"
        )
    
    if not valid_amounts:
        logger.warning("No valid conversion amounts to analyze")
        return []
    
    return valid_amounts


def _build_scenario_result(amount: float, betr_result: BETRResults) -> ConversionScenarioResult:
    """
    Build result dictionary for a single conversion scenario.
    
    Args:
        amount: Conversion amount for this scenario
        betr_result: BETR calculation results
        
    Returns:
        Dictionary containing scenario analysis results
    """
    return {
        'conversion_amount': amount,
        'conversion_tax': betr_result.conversion_tax,
        'betr': betr_result.betr,
        'recommended': betr_result.conversion_recommended,
        'net_benefit': betr_result.net_benefit,
        'roth_future_value': betr_result.roth_future_value,
        'traditional_future_value': betr_result.traditional_future_value
    }



def analyze_conversion_scenarios(
    traditional_ira_balance: float,
    conversion_amounts: Sequence[float],
    current_marginal_rate: float,
    expected_future_rate: float,
    pay_from_taxable: bool = True,
    taxable_account_balance: float = 0.0,
    nontaxable_basis: float = 0.0,
    years_to_withdrawal: int = 20,
    annual_return: float = 0.07
) -> pd.DataFrame:
    """
    Analyze multiple conversion scenarios and compare their BETR values.
    
    This function helps visualize the impact of different conversion amounts
    on the break-even tax rate and net benefit.
    
    Args:
        traditional_ira_balance: Total Traditional IRA balance
        conversion_amounts: Sequence of conversion amounts to analyze
        current_marginal_rate: Current marginal tax rate
        expected_future_rate: Expected future marginal tax rate
        pay_from_taxable: Whether to pay conversion tax from taxable account
        taxable_account_balance: Balance in taxable account
        nontaxable_basis: Nontaxable basis in Traditional IRA
        years_to_withdrawal: Years until withdrawal
        annual_return: Expected annual return
        
    Returns:
        DataFrame with scenario analysis results
        
    Raises:
        TypeError: If conversion_amounts is not a sequence
        ValueError: If conversion_amounts contains invalid values
    """
    # Validate and filter conversion amounts
    valid_amounts = _validate_conversion_amounts(conversion_amounts, traditional_ira_balance)
    
    # Early return if no valid amounts
    if not valid_amounts:
        return pd.DataFrame()
    
    logger.info(f"Analyzing {len(valid_amounts)} conversion scenarios")

    # Build results using list comprehension
    results = [
        _build_scenario_result(
            amount,
            calculate_betr(
                BETRInputs(
                    current_marginal_rate=current_marginal_rate,
                    expected_future_rate=expected_future_rate,
                    conversion_amount=amount,
                    traditional_ira_balance=traditional_ira_balance,
                    nontaxable_basis=nontaxable_basis,
                    pay_from_taxable=pay_from_taxable,
                    taxable_account_balance=taxable_account_balance,
                    years_to_withdrawal=years_to_withdrawal,
                    annual_return=annual_return
                )
            )
        )
        for amount in valid_amounts
    ]
    
    df = pd.DataFrame(results)
    
    logger.info(f"Scenario analysis complete: {len(df)} scenarios analyzed")
    
    return df


def print_betr_report(results: BETRResults, inputs: BETRInputs):
    """
    Print a formatted report of BETR analysis results.
    
    Args:
        results: BETRResults from calculate_betr()
        inputs: BETRInputs used for calculation
    """
    print("\n" + "="*70)
    print("BETR (Break-Even Tax Rate) Analysis Report")
    print("="*70)
    
    print(f"\nConversion Details:")
    print(f"  Amount to Convert:        ${inputs.conversion_amount:>15,.0f}")
    print(f"  Traditional IRA Balance:  ${inputs.traditional_ira_balance:>15,.0f}")
    print(f"  Nontaxable Basis:         ${inputs.nontaxable_basis:>15,.0f}")
    print(f"  Conversion Tax:           ${results.conversion_tax:>15,.0f}")
    
    print(f"\nTax Rates:")
    print(f"  Current Marginal Rate:    {inputs.current_marginal_rate:>15.2%}")
    print(f"  Expected Future Rate:     {inputs.expected_future_rate:>15.2%}")
    print(f"  Break-Even Tax Rate:      {results.betr:>15.2%}")
    
    print(f"\nFuture Values (in {inputs.years_to_withdrawal} years):")
    print(f"  Traditional IRA (after tax): ${results.traditional_future_value:>12,.0f}")
    print(f"  Roth IRA (tax-free):         ${results.roth_future_value:>12,.0f}")
    print(f"  Net Benefit:                 ${results.net_benefit:>12,.0f}")
    
    print(f"\nRecommendation: {'✓ CONVERT' if results.conversion_recommended else '✗ DO NOT CONVERT'}")
    
    print(f"\nAnalysis Notes:")
    for note in results.analysis_notes:
        print(f"  • {note}")
    
    print("="*70 + "\n")


# Example usage and testing
if __name__ == "__main__":
    print("BETR Roth Conversion Algorithm - Example Usage\n")
    
    # Example 0a: Conversion Tax Calculation
    print("Example 0a: Conversion Tax Calculation")
    print("-" * 50)
    print("Formula: Conversion Tax = Conversion Amount × Ordinary Income Tax Rate\n")
    
    # Test case: $50,000 conversion at 24% tax rate
    test_conversion_amt = 50000
    test_tax_rate = 0.24
    test_tax = calculate_conversion_tax(test_conversion_amt, test_tax_rate)
    
    print(f"Test Case:")
    print(f"  Conversion Amount: ${test_conversion_amt:,.2f}")
    print(f"  Tax Rate: {test_tax_rate:.2%}")
    print(f"  Conversion Tax: ${test_tax:,.2f}")
    print(f"  Expected: $12,000.00")
    print(f"  Match: {'✓ PASS' if abs(test_tax - 12000.00) < 0.01 else '✗ FAIL'}\n")
    
    # Example 0b: Conversion After-Tax Future Value
    print("\nExample 0b: Conversion After-Tax Future Value")
    print("-" * 50)
    print("Formula: After-Tax FV = Conversion FV - Tax FV")
    print("Where: Conversion FV = Amount × (1+r)^n, Tax FV = Tax × (1+r)^n\n")
    
    # Test case from user: $10,000 at 6% for 20 years with 35% tax
    test_amt = 10000
    test_rate = 0.06
    test_years = 20
    test_tax_rate = 0.35
    
    conv_fv, tax_fv, after_tax_fv = calculate_conversion_after_tax_future_value(
        test_amt, test_rate, test_years, test_tax_rate
    )
    
    print(f"Test Case:")
    print(f"  Conversion Amount: ${test_amt:,.2f}")
    print(f"  Annual Return: {test_rate:.2%}")
    print(f"  Years: {test_years}")
    print(f"  Tax Rate: {test_tax_rate:.2%}")
    print(f"\nResults:")
    print(f"  Conversion FV: ${conv_fv:,.0f} (Expected: $32,071)")
    print(f"  Tax FV: ${tax_fv:,.0f} (Expected: $7,523)")
    print(f"  After-Tax FV: ${after_tax_fv:,.0f} (Expected: $24,549)")
    
    # Verify results
    conv_match = abs(conv_fv - 32071) < 1
    tax_match = abs(tax_fv - 7523) < 1
    after_tax_match = abs(after_tax_fv - 24549) < 1
    
    print(f"\nValidation:")
    print(f"  Conversion FV: {'✓ PASS' if conv_match else '✗ FAIL'}")
    print(f"  Tax FV: {'✓ PASS' if tax_match else '✗ FAIL'}")
    print(f"  After-Tax FV: {'✓ PASS' if after_tax_match else '✗ FAIL'}")
    
    # Calculate and display BETR
    betr = calculate_betr_rate(test_amt, test_rate, test_years, test_tax_rate)
    expected_betr = 1 - (24549 / 32071)
    betr_match = abs(betr - expected_betr) < 0.0001
    
    print(f"\nBETR Calculation:")
    print(f"  BETR = 1 - (After-Tax FV / Conversion FV)")
    print(f"  BETR = 1 - (${after_tax_fv:,.0f} / ${conv_fv:,.0f})")
    print(f"  BETR = {betr:.4%} (Expected: {expected_betr:.4%})")
    print(f"  Match: {'✓ PASS' if betr_match else '✗ FAIL'}")
    print(f"\n  Interpretation: Convert if future tax rate > {betr:.2%}\n")
    
    # Example 0c: Future Value Calculation Formula
    print("\nExample 0c: Conversion Future Value Calculation")
    print("-" * 50)
    print("Formula: FV = PV × (1 + r)^n")
    print("Where: FV = Future Value, PV = Present Value, r = annual return, n = years\n")
    
    # Test case: $10,000 at 6% for 20 years should equal $32,071.35
    test_conversion = 10000
    test_rate = 0.06
    test_years = 20
    test_result = calculate_conversion_future_value(test_conversion, test_rate, test_years)
    
    print(f"Test Case:")
    print(f"  Conversion Amount: ${test_conversion:,.2f}")
    print(f"  Annual Return: {test_rate:.2%}")
    print(f"  Years: {test_years}")
    print(f"  Future Value: ${test_result:,.2f}")
    print(f"  Expected: $32,071.35")
    print(f"  Match: {'✓ PASS' if abs(test_result - 32071.35) < 0.01 else '✗ FAIL'}\n")
    
    # Example 1: Basic conversion analysis
    print("\nExample 1: Basic Conversion Analysis")
    print("-" * 50)
    
    inputs1 = BETRInputs(
        current_marginal_rate=0.24,
        expected_future_rate=0.22,
        conversion_amount=50000,
        traditional_ira_balance=500000,
        nontaxable_basis=0,
        pay_from_taxable=True,
        taxable_account_balance=200000,
        years_to_withdrawal=20,
        annual_return=0.07
    )
    
    results1 = calculate_betr(inputs1)
    print_betr_report(results1, inputs1)
    
    # Example 2: Conversion with nontaxable basis
    print("\nExample 2: Conversion with Nontaxable Basis")
    print("-" * 50)
    
    inputs2 = BETRInputs(
        current_marginal_rate=0.24,
        expected_future_rate=0.24,
        conversion_amount=50000,
        traditional_ira_balance=500000,
        nontaxable_basis=50000,  # $50k of after-tax contributions
        pay_from_taxable=True,
        taxable_account_balance=200000,
        years_to_withdrawal=15,
        annual_return=0.07
    )
    
    results2 = calculate_betr(inputs2)
    print_betr_report(results2, inputs2)
    
    # Example 3: Optimize conversion amount
    print("\nExample 3: Optimize Conversion Amount")
    print("-" * 50)
    
    optimal_amount, optimal_results = optimize_conversion_amount(
        traditional_ira_balance=500000,
        current_agi=150000,
        target_tax_bracket=0.24,
        year=2026,
        pay_from_taxable=True,
        taxable_account_balance=200000,
        years_to_withdrawal=20,
        annual_return=0.07
    )
    
    print(f"Optimal conversion amount: ${optimal_amount:,.0f}")
    if optimal_results:
        print_betr_report(optimal_results, BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.24,
            conversion_amount=optimal_amount,
            traditional_ira_balance=500000,
            pay_from_taxable=True,
            taxable_account_balance=200000,
            years_to_withdrawal=20,
            annual_return=0.07
        ))

# Made with Bob
