"""
Portfolio Withdrawal Strategy Module - 6 Stages of Life

This module implements a comprehensive withdrawal strategy across 6 life stages:
1. Accumulation: Employed, earning wages, tax-efficient asset accumulation
2. Prep for Retirement: Employed, within 10 years of retirement, balance Roth/Traditional/Taxable
3. Early Retirement: Pre-Medicare, pre-SS, pre-RMD with BETR-optimized Roth conversions
4. Medicare Stage: IRMAA optimization with BETR-based continued Roth conversions
5. Social Security Stage: SS benefits + Medicare, pre-RMD optimization with BETR
6. RMD Stage: Required Minimum Distributions with full retirement income

Key Features:
- BETR (Break-Even Tax Rate) algorithm for optimal Roth conversion decisions
- RMD lookback optimization to reduce future tax burden
- Tax-efficient withdrawal sequencing across all life stages
- IRMAA threshold management with 2-year lookback
- ACA subsidy optimization for early retirees

Based on Vanguard Research: "A 'BETR' approach to Roth conversions" (July 2025)

Author: IBM Bob
Date: 2026-02-24
Version: 2.0 - BETR Integration
"""

import functools
import itertools
import pandas as pd
import numpy as np
import logging
import os
import types
from datetime import datetime
from typing import Dict, Tuple, Optional, List, Any, Union, Iterator, Sequence, cast, TypedDict
from dataclasses import dataclass, field, asdict, replace
from enum import Enum

from load_data import (
    get_income_tax_brackets,
    get_cap_gains_brackets,
    get_std_deduction,
    get_medicare_costs,
    get_atm_costs,
    get_networth_by_month
)
from config import get_config_manager
from calculations import (
    calculate_taxable_income,
    calculate_cap_gains,
    calculate_irmma_penalty,
    calc_roth_conversions,
    calc_roth_conversions_tax,
    calc_agi,
    get_rmd_value,
    getUpperIncomeRate
)
from ssibenefits import get_monthly_benefit
from ssi_calculator import (
    calculate_benefit_at_claiming_age,
    calculate_benefit_with_cola,
    DEFAULT_COLA_RATE
)
from betr_roth_conversion import (
    optimize_conversion_amount,
    calculate_betr,
    BETRInputs,
    BETRResults
)

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Cost basis assumption for Brokerage account withdrawals
# Until intelligent portfolio management is implemented, assume:
# - 60% of withdrawal is return of cost basis (tax-free)
# - 40% of withdrawal is long-term capital gains (taxable)
BROKERAGE_COST_BASIS_RATIO = 0.60
BROKERAGE_LTCG_RATIO = 0.40

# Default columns shown in the year-by-year section of the strategy report.
# Stored as an immutable tuple so callers can reference it without risk of
# mutation and to avoid re-constructing the sequence on every call.
_REPORT_DEFAULT_DISPLAY_COLS: tuple = (
    'Year', 'Age', 'Stage', 'Roth Conversion',
    'Federal Tax', 'IRMAA Penalty', 'Total Portfolio',
)

# Net Investment Income Tax rate (IRC §1411, fixed since 2013)
NIIT_RATE: float = 0.038

# NIIT thresholds (not indexed for inflation since 2013, per IRC §1411)
NIIT_THRESHOLDS: Dict[str, int] = {
    'married_filing_jointly':    250_000,
    'single':                    200_000,
    'married_filing_separately': 125_000,
    'head_of_household':         200_000,
}

# Minimum age for Medicare eligibility (fixed by statute)
MEDICARE_ELIGIBILITY_AGE: int = 65

# Medicare Part D base premium (annual; updated each year by CMS)
PART_D_ANNUAL_BASE_PREMIUM: int = 480   # ~$40/month average

# Medigap supplemental insurance premium (annual estimate)
MEDIGAP_ANNUAL_PREMIUM: int = 2_400     # ~$200/month average

# Medicare Part B standard monthly premium (2024; updated annually by CMS).
# Used as the fallback when IRMAA bracket data is unavailable.
PART_B_MONTHLY_STANDARD_PREMIUM: float = 174.70

# Minimum age for penalty-free withdrawals from Traditional IRA / 401k (IRC §72(t))
EARLY_WITHDRAWAL_PENALTY_AGE: float = 59.5

# ACA marketplace premium estimate per person per month (pre-Medicare)
# Annualised: ACA_MONTHLY_PREMIUM_PER_PERSON * 12 = $12,000/year
ACA_MONTHLY_PREMIUM_PER_PERSON: int = 1_000

# Annual out-of-pocket healthcare costs by health status
OOP_COSTS_BY_HEALTH_STATUS: Dict[str, int] = {
    'healthy': 4_000,
    'average': 6_500,
    'chronic': 12_000,
}
OOP_COST_DEFAULT: int = OOP_COSTS_BY_HEALTH_STATUS['average']

# Long-term care insurance annual premium per person (average estimate)
LTC_ANNUAL_PREMIUM_PER_PERSON: int = 3_500

# IRMAA uses a 2-year lookback: the surcharge applied in year N is based on
# MAGI reported in year N-2.  This constant makes that window explicit and
# provides a single point of change should the IRS ever alter the period.
_IRMAA_LOOKBACK_YEARS: int = 2

# Minimum deficit below which buffer replenishment is skipped (de-minimis threshold).
# Avoids triggering taxable distributions for trivially small shortfalls.
# Used by both replenish_cash_buffer() and replenish_brokerage_buffer().
_BUFFER_REPLENISHMENT_MIN_DEFICIT: float = 100.0

# Maximum fraction of the Traditional balance that may be distributed to the
# brokerage buffer in a single year.  Caps the ordinary-income tax hit.
_MAX_TRADITIONAL_TO_BROKERAGE_RATE: float = 0.15


def calculate_ssi_benefits_dynamic(year: int, person_name: str, birth_year: int,
                                   claiming_age: int, fra_benefit: float,
                                   cola_rate: float = DEFAULT_COLA_RATE) -> float:
    """
    Calculate SSI benefits for a person in a given year using dynamic formula.
    
    Args:
        year: Current year
        person_name: Name of the person
        birth_year: Year of birth
        claiming_age: Age when benefits are claimed
        fra_benefit: Monthly benefit at Full Retirement Age (67)
        cola_rate: Annual COLA rate (default: 2%)
        
    Returns:
        Monthly SSI benefit amount for the year (0 if not yet claiming)
    """
    current_age = year - birth_year
    
    # Not yet claiming
    if current_age < claiming_age:
        return 0.0
    
    # Calculate initial benefit at claiming age
    initial_benefit = calculate_benefit_at_claiming_age(fra_benefit, claiming_age)
    
    # Apply COLA for years since claiming
    claiming_year = birth_year + claiming_age
    years_since_claiming = year - claiming_year
    
    monthly_benefit = calculate_benefit_with_cola(initial_benefit, years_since_claiming, cola_rate)
    
    logger.debug(f"SSI for {person_name} in {year}: Age {current_age}, "
                f"Claiming age {claiming_age}, Monthly benefit ${monthly_benefit:,.2f}")
    
    return monthly_benefit

def calculate_aca_premium_for_year(year: int, age_primary: int, age_spouse: int) -> float:
    """
    Calculate total ACA premium for a given year based on both people's ages and configuration.
    
    Args:
        year: Current year
        age_primary: Primary person's age
        age_spouse: Spouse's age
    
    Returns:
        Annual ACA premium cost (sum of both people if applicable)
    """
    config_mgr = get_config_manager()
    
    # Get person 1 ACA configuration
    person1_monthly_premium = config_mgr.get("healthcare", "person1_aca_insurance_monthly", 0)
    person1_aca_start_age = config_mgr.get("healthcare", "person1_aca_start_age", 62)
    person1_aca_end_age = config_mgr.get("healthcare", "person1_aca_end_age", 65)
    
    # Get person 2 ACA configuration
    person2_monthly_premium = config_mgr.get("healthcare", "person2_aca_insurance_monthly", 0)
    person2_aca_start_age = config_mgr.get("healthcare", "person2_aca_start_age", 62)
    person2_aca_end_age = config_mgr.get("healthcare", "person2_aca_end_age", 65)
    
    total_annual_premium = 0.0
    
    # Check if person 1 is in ACA coverage period
    if person1_aca_start_age <= age_primary < person1_aca_end_age and person1_monthly_premium > 0:
        total_annual_premium += person1_monthly_premium * 12
    
    # Check if person 2 is in ACA coverage period
    if person2_aca_start_age <= age_spouse < person2_aca_end_age and person2_monthly_premium > 0:
        total_annual_premium += person2_monthly_premium * 12
    
    return total_annual_premium


def calculate_cash_buffer_targets(expenses: float) -> Tuple[float, float]:
    """
    Calculate the target buffer amounts for Cash and Taxable accounts
    
    Args:
        expenses: Annual expenses
    
    Returns:
        Tuple of (cash_target, taxable_target)
        - cash_target: Full "Recommended Cash Reserve" (expenses * years_of_expenses_in_cash)
        - taxable_target: Additional buffer in Taxable (1 year of expenses)
    """
    # Get years_of_expenses from session state or fall back to config
    from config import get_value_with_session_override
    years_of_expenses = float(get_value_with_session_override('financial_assumptions', 'years_of_expenses_in_cash', 'EXPENSE_MULTIPLIER', 4))
    
    # Use the full "Recommended Cash Reserve" value from configuration page
    # This matches: expected_annual_expenses * years_of_expenses_in_cash
    cash_target = expenses * years_of_expenses
    
    # Keep an additional 1 year buffer in taxable/brokerage account
    taxable_target = expenses * 1.0
    
    return cash_target, taxable_target


def calculate_cash_buffer_targets_accumulation(wages: float) -> float:
    """
    Calculate the target cash buffer for the accumulation phase.

    During working years the cash target is expressed as a number of months of
    gross wages rather than years of expenses.  The default is 6 months; the
    user can adjust this between 3 and 24 months via the Configuration page.

    Args:
        wages: Annual gross wages (person1 + person2 combined)

    Returns:
        cash_target: Target cash balance (wages * months / 12)
    """
    from config import get_config_manager
    try:
        config_mgr = get_config_manager()
        months = float(config_mgr.get(
            'financial_assumptions', 'accumulation_cash_buffer_months', 6
        ))
    except Exception:
        months = 6.0

    # Clamp to the allowed UI range just in case the stored value is out of bounds
    months = max(3.0, min(24.0, months))
    return wages * months / 12.0

def calculate_stage2_cash_target(wages: float, expenses: float,
                                  years_to_retirement: int,
                                  prep_window: int = 10) -> float:
    """
    Calculate the linearly-ramped cash buffer target for Stage 2 (Prep for Retirement).

    At the *start* of Stage 2 (``years_to_retirement == prep_window``) the target
    equals the wages-based accumulation buffer (same as Stage 1).  By the *end* of
    Stage 2 (``years_to_retirement == 1``) the target has ramped up to **75 %** of
    the full retirement cash reserve (``expenses × years_of_expenses_in_cash``).

    Linear interpolation formula::

        progress = (prep_window - years_to_retirement) / (prep_window - 1)
        target   = accum_target + progress * (0.75 * retirement_target - accum_target)

    Args:
        wages:               Annual gross wages (combined).
        expenses:            Annual living expenses.
        years_to_retirement: Years remaining until the earlier retirement date.
        prep_window:         Number of years that Stage 2 spans (default 10).

    Returns:
        cash_target: Interpolated cash buffer target for the current year.
    """
    accum_target = calculate_cash_buffer_targets_accumulation(wages)
    retirement_cash_target, _ = calculate_cash_buffer_targets(expenses)
    end_target = 0.75 * retirement_cash_target

    # Clamp years_to_retirement to the valid window [1, prep_window]
    years_to_retirement = max(1, min(prep_window, years_to_retirement))

    # progress: 0.0 at the start of Stage 2, 1.0 in the final year
    progress = (prep_window - years_to_retirement) / max(1, prep_window - 1)
    return accum_target + progress * (end_target - accum_target)


def calculate_buffer_ramp_up(current_year: int, start_year: int,
                             cash_target: float, taxable_target: float,
                             current_cash: float, current_taxable: float) -> Tuple[float, float]:
    """
    Calculate how much to add to each buffer during 3-year ramp-up period
    
    Args:
        current_year: Current projection year
        start_year: Year when strategy started
        cash_target: Target cash buffer (2 years expenses)
        taxable_target: Target taxable buffer (3 years expenses)
        current_cash: Current cash balance
        current_taxable: Current taxable balance
    
    Returns:
        Tuple of (cash_needed, taxable_needed) - amounts to add this year
    """
    years_elapsed = current_year - start_year
    
    # Ramp up over 3 years
    if years_elapsed >= 3:
        # After 3 years, maintain targets
        cash_needed = max(0, cash_target - current_cash)
        taxable_needed = max(0, taxable_target - current_taxable)
    else:
        # During ramp-up, aim for proportional progress
        progress_ratio = (years_elapsed + 1) / 3
        cash_target_for_year = cash_target * progress_ratio
        taxable_target_for_year = taxable_target * progress_ratio
        
        cash_needed = max(0, cash_target_for_year - current_cash)
        taxable_needed = max(0, taxable_target_for_year - current_taxable)
    
    return cash_needed, taxable_needed


def get_target_conversion_bracket(max_rate: float, tax_brackets: pd.DataFrame) -> Tuple[float, float]:
    """
    Dynamically find the best tax bracket for Roth conversions up to max_rate.
    
    Args:
        max_rate: Maximum tax rate from sidebar (e.g., 0.24 for 24%)
        tax_brackets: DataFrame with tax bracket data
        
    Returns:
        Tuple of (target_rate, upper_limit) for the conversion bracket
        
    Raises:
        ValueError: If no suitable bracket is found
    """
    # Get all available rates up to and including max_rate
    available_rates = pd.unique(tax_brackets[tax_brackets['rate'] <= max_rate]['rate'])
    available_rates = sorted(available_rates, reverse=True)  # Highest first
    
    # Remove 0% bracket (not useful for conversions)
    available_rates = [r for r in available_rates if r > 0]
    
    if not available_rates:
        raise ValueError(f"No suitable tax brackets found up to {max_rate:.2%}")
    
    # Try each rate from highest to lowest until we find one that exists
    for rate in available_rates:
        try:
            upper_limit = float(getUpperIncomeRate(rate, tax_brackets))
            logger.debug(f"Using {rate:.2%} bracket (upper: ${upper_limit:,.2f}) for conversions")
            return rate, upper_limit
        except ValueError:
            continue
    
    raise ValueError(f"Could not find valid conversion bracket up to {max_rate:.2%}")


def optimize_rmd_lookback(strategies: list,
                         initial_balances,
                         max_conversion_rate: float = 0.24,
                         growth_rate: float = 1.07) -> Tuple[list, Dict]:
    """
    Review projected RMDs and optimize earlier conversions/withdrawals to reduce future RMD burden.
    
    After initial strategy calculation, analyze Stage 5 RMDs to determine if they exceed expenses.
    If so, increase Roth conversions in earlier stages (2-4) to reduce future RMD burden and
    improve tax efficiency.
    
    Args:
        strategies: List of YearlyStrategy objects from initial calculation
        initial_balances: Initial portfolio balances (for reference)
        max_conversion_rate: Maximum tax rate for conversions (default: 0.24)
        growth_rate: Annual portfolio growth rate (default: 1.07)
    
    Returns:
        Tuple of (adjusted_strategies, optimization_report)
        - adjusted_strategies: Optimized strategy list with increased early conversions
        - optimization_report: Dictionary with optimization metrics
    """
    logger.info("Starting RMD lookback optimization...")
    
    # Step 1: Analyze Stage 5 RMDs
    rmd_years = [s for s in strategies if s.stage == "Stage 6: RMD"]
    
    if not rmd_years:
        logger.info("No RMD years found - no optimization needed")
        return strategies, {"status": "No RMD years to optimize"}
    
    # Step 2: Calculate average RMD excess over expenses
    total_rmd_excess = 0
    rmd_count = 0
    
    for year_strategy in rmd_years:
        rmd_excess = year_strategy.rmd_amount - year_strategy.expenses
        if rmd_excess > 0:
            total_rmd_excess += rmd_excess
            rmd_count += 1
    
    if rmd_count == 0 or total_rmd_excess <= 0:
        logger.info("RMDs do not exceed expenses - no optimization needed")
        return strategies, {"status": "RMDs within expenses - no optimization needed"}
    
    avg_rmd_excess = total_rmd_excess / rmd_count
    logger.info(f"Average RMD excess: ${avg_rmd_excess:,.0f} across {rmd_count} years")
    
    # Step 3: Identify pre-RMD years for optimization
    pre_rmd_years = [s for s in strategies if s.stage in [
        "Stage 2: Prep for Retirement",
        "Stage 3: Early Retirement",
        "Stage 4: Medicare",
        "Stage 5: Social Security"
    ]]
    
    if not pre_rmd_years:
        logger.info("No pre-RMD years available for optimization")
        return strategies, {"status": "No pre-RMD years available"}
    
    # Step 4: Calculate additional conversions needed
    years_available = len(pre_rmd_years)
    additional_conversion_per_year = avg_rmd_excess / years_available
    
    logger.info(f"Distributing ${avg_rmd_excess:,.0f} excess across {years_available} years")
    logger.info(f"Target additional conversion: ${additional_conversion_per_year:,.0f} per year")
    
    # Step 5: Adjust strategies for each pre-RMD year
    adjusted_strategies = []
    total_additional_conversions = 0
    years_adjusted = 0
    
    for year_strategy in strategies:
        if year_strategy.stage in ["Stage 2: Prep for Retirement",
                                   "Stage 3: Early Retirement",
                                   "Stage 4: Medicare",
                                   "Stage 5: Social Security"]:
            # Calculate maximum additional conversion (limit to 15% of Traditional balance)
            max_additional_conversion = min(
                additional_conversion_per_year,
                year_strategy.balances.traditional * 0.15
            )
            
            if max_additional_conversion > 1000:  # Only adjust if meaningful amount
                # Verify with BETR that additional conversion is beneficial
                try:
                    betr_inputs = BETRInputs(
                        current_marginal_rate=0.24,  # Assume 24% bracket
                        expected_future_rate=0.24,   # Assume same in RMD years
                        conversion_amount=year_strategy.roth_conversion + max_additional_conversion,
                        traditional_ira_balance=year_strategy.balances.traditional,
                        pay_from_taxable=True,
                        taxable_account_balance=year_strategy.balances.taxable,
                        years_to_withdrawal=max(1, 73 - year_strategy.age_primary),
                        annual_return=growth_rate - 1.0
                    )
                    
                    betr_results = calculate_betr(betr_inputs)
                    
                    if betr_results.conversion_recommended:
                        # Log balances before adjustment
                        logger.info(f"Year {year_strategy.year}: Before optimization adjustment:")
                        logger.info(f"  Traditional: ${year_strategy.balances.traditional:,.2f}")
                        logger.info(f"  Roth: ${year_strategy.balances.roth:,.2f}")
                        logger.info(f"  Taxable: ${year_strategy.balances.taxable:,.2f}")
                        logger.info(f"  Original conversion: ${year_strategy.roth_conversion:,.2f}")
                        
                        # Validate that we have sufficient traditional balance BEFORE modifying conversion
                        if year_strategy.balances.traditional < max_additional_conversion:
                            logger.warning(f"Year {year_strategy.year}: Insufficient traditional balance "
                                         f"(${year_strategy.balances.traditional:,.2f}) for additional conversion "
                                         f"(${max_additional_conversion:,.2f}). Skipping adjustment.")
                            continue
                        
                        # Increase conversion
                        year_strategy.roth_conversion += max_additional_conversion
                        
                        # CRITICAL: Recalculate balances to reflect the increased conversion
                        # The additional conversion reduces Traditional and increases Roth
                        year_strategy.balances = PortfolioBalances(
                            cash=year_strategy.balances.cash,
                            taxable=year_strategy.balances.taxable,
                            traditional=year_strategy.balances.traditional - max_additional_conversion,
                            roth=year_strategy.balances.roth + max_additional_conversion,
                            daf=year_strategy.balances.daf
                        )
                        
                        total_additional_conversions += max_additional_conversion
                        years_adjusted += 1
                        
                        # Log balances after adjustment
                        logger.info(f"  After optimization adjustment:")
                        logger.info(f"  Traditional: ${year_strategy.balances.traditional:,.2f} (reduced by ${max_additional_conversion:,.2f})")
                        logger.info(f"  Roth: ${year_strategy.balances.roth:,.2f} (increased by ${max_additional_conversion:,.2f})")
                        logger.info(f"  New conversion total: ${year_strategy.roth_conversion:,.2f}")
                        logger.info(f"  BETR: {betr_results.betr:.2%}")
                    else:
                        logger.debug(f"Year {year_strategy.year}: BETR {betr_results.betr:.2%} - "
                                   f"additional conversion not recommended")
                        
                except Exception as e:
                    logger.warning(f"Year {year_strategy.year}: BETR verification failed: {e}")
        
        adjusted_strategies.append(year_strategy)
    
    # Step 6: Generate optimization report
    estimated_rmd_reduction = total_additional_conversions * 0.04  # Approximate RMD % reduction
    avg_additional_per_adjusted_year = total_additional_conversions / years_adjusted if years_adjusted > 0 else None
    
    optimization_report = {
        "status": "Optimization complete",
        "avg_rmd_excess": avg_rmd_excess,
        "rmd_years_analyzed": rmd_count,
        "pre_rmd_years_available": years_available,
        "years_adjusted": years_adjusted,
        "additional_conversion_per_year_target": additional_conversion_per_year,
        "total_additional_conversions": total_additional_conversions,
        "estimated_rmd_reduction": estimated_rmd_reduction,
        "avg_additional_per_adjusted_year": avg_additional_per_adjusted_year if years_adjusted > 0 else "N/A - no years adjusted"
    }
    
    logger.info(f"RMD Optimization Complete:")
    logger.info(f"  - Adjusted {years_adjusted} years")
    logger.info(f"  - Total additional conversions: ${total_additional_conversions:,.0f}")
    logger.info(f"  - Estimated RMD reduction: ${estimated_rmd_reduction:,.0f}")
    
    return adjusted_strategies, optimization_report


# State Unemployment Tax Act (SUTA) rates and taxable wage bases by state (2024 estimates).
# Format: state_code -> (employee_rate, wage_base)
# Sources: DOL state UI tax tables; rates shown are new-employer / average rates.
_SUTA_BY_STATE: Dict[str, Tuple[float, float]] = {
    'AL': (0.0270, 8_000),
    'AK': (0.0100, 49_700),
    'AZ': (0.0200, 8_000),
    'AR': (0.0310, 10_000),
    'CA': (0.0340, 7_000),
    'CO': (0.0170, 23_800),
    'CT': (0.0290, 25_000),
    'DE': (0.0180, 10_500),
    'FL': (0.0270, 7_000),
    'GA': (0.0270, 9_500),
    'HI': (0.0240, 59_100),
    'ID': (0.0207, 53_500),
    'IL': (0.0350, 13_590),
    'IN': (0.0250, 9_500),
    'IA': (0.0100, 38_200),
    'KS': (0.0270, 14_000),
    'KY': (0.0270, 11_100),
    'LA': (0.0270, 7_700),
    'ME': (0.0220, 12_000),
    'MD': (0.0270, 8_500),
    'MA': (0.0290, 15_000),
    'MI': (0.0270, 9_500),
    'MN': (0.0100, 42_000),
    'MS': (0.0100, 14_000),
    'MO': (0.0270, 10_500),
    'MT': (0.0100, 43_000),
    'NE': (0.0125, 9_000),
    'NV': (0.0295, 40_600),
    'NH': (0.0270, 14_000),
    'NJ': (0.0028, 42_300),
    'NM': (0.0100, 31_700),
    'NY': (0.0290, 12_500),
    'NC': (0.0120, 31_400),
    'ND': (0.0100, 43_800),
    'OH': (0.0270, 9_000),
    'OK': (0.0270, 25_700),
    'OR': (0.0270, 52_800),
    'PA': (0.0370, 10_000),
    'RI': (0.0099, 29_200),
    'SC': (0.0270, 14_000),
    'SD': (0.0120, 15_000),
    'TN': (0.0270, 7_000),
    'TX': (0.0270, 9_000),
    'UT': (0.0100, 47_000),
    'VT': (0.0100, 14_300),
    'VA': (0.0270, 8_000),
    'WA': (0.0100, 72_800),
    'WV': (0.0270, 9_000),
    'WI': (0.0350, 14_000),
    'WY': (0.0270, 29_100),
    'DC': (0.0270, 9_000),
}


def calculate_payroll_taxes(wages: float, year: int = 2024) -> Tuple[float, Dict]:
    """
    Calculate payroll taxes on wage income: FICA (Social Security), Medicare,
    state income tax, and unemployment insurance (FUTA/SUTA).

    SUTA rate and wage base are looked up by the state configured in personal_info.
    These are deducted from gross wages before any savings or investment decisions.

    Args:
        wages: Gross annual wages
        year:  Tax year (used for wage-base inflation; base year 2024)

    Returns:
        Tuple of (total_payroll_tax, breakdown_dict)
    """
    if wages <= 0:
        return 0.0, {}

    # ── Resolve state from config ─────────────────────────────────────────────
    try:
        _cfg = get_config_manager()
        state = (_cfg.get('personal_info', 'retirement_state', 'FL') or 'FL').upper()
    except Exception:
        state = 'FL'

    # ── Social Security (OASDI) ────────────────────────────────────────────────
    # 2024 wage base: $168,600; employee share: 6.2 %
    # Inflate wage base by ~3.5 % per year beyond 2024
    ss_wage_base = 168_600 * (1.035 ** max(0, year - 2024))
    ss_tax = min(wages, ss_wage_base) * 0.062

    # ── Medicare ──────────────────────────────────────────────────────────────
    # 1.45 % on all wages; additional 0.9 % on wages > $250k (MFJ)
    medicare_tax = wages * 0.0145
    additional_medicare_threshold = 250_000
    if wages > additional_medicare_threshold:
        medicare_tax += (wages - additional_medicare_threshold) * 0.009

    # ── State income tax on wages ─────────────────────────────────────────────
    state_tax, _ = calculate_state_tax(state_agi=wages, year=year, state=state)

    # ── FUTA ──────────────────────────────────────────────────────────────────
    # Federal Unemployment Tax Act: 0.6 % on first $7,000 (net of SUTA credit)
    futa_wage_base = 7_000
    futa_tax = min(wages, futa_wage_base) * 0.006

    # ── SUTA (state unemployment insurance) ───────────────────────────────────
    # Rate and wage base vary by state; fall back to national average if unknown.
    suta_rate, suta_wage_base = _SUTA_BY_STATE.get(state, (0.027, 7_000))
    suta_tax = min(wages, suta_wage_base) * suta_rate
    logger.debug(f"SUTA ({state}): rate={suta_rate:.2%}, wage_base=${suta_wage_base:,}, tax=${suta_tax:,.0f}")

    total = ss_tax + medicare_tax + state_tax + futa_tax + suta_tax

    breakdown = {
        'state':               state,
        'social_security_tax': ss_tax,
        'medicare_tax':        medicare_tax,
        'state_tax':           state_tax,
        'futa_tax':            futa_tax,
        'suta_rate':           suta_rate,
        'suta_wage_base':      suta_wage_base,
        'suta_tax':            suta_tax,
        'total_payroll_tax':   total,
    }
    logger.info(
        f"Payroll taxes ({state}) on ${wages:,.0f} wages: SS=${ss_tax:,.0f}, "
        f"Medicare=${medicare_tax:,.0f}, State=${state_tax:,.0f}, "
        f"FUTA=${futa_tax:,.0f}, SUTA={suta_rate:.2%}×${suta_wage_base:,}=${suta_tax:,.0f}"
        f"  →  Total=${total:,.0f}"
    )
    return total, breakdown


def calculate_state_tax(state_agi: float, state: Optional[str] = None, year: int = 2024,
                       filing_status: str = "married_filing_jointly",
                       retirement_income: float = 0,
                       ss_benefits: float = 0) -> Tuple[float, Dict]:
    """
    Calculate state income tax with retirement exemptions
    
    Args:
        state_agi: State Adjusted Gross Income
        state: Two-letter state code (e.g., "CA", "NY", "FL"). If None, uses config value.
        year: Tax year
        filing_status: Filing status
        retirement_income: IRA/401k distributions for exemption calculation
        ss_benefits: Social Security benefits
    
    Returns:
        Tuple of (state_tax, calculation_details)
        
    Implementation Notes:
        - No-tax states: Return 0
        - Retirement-friendly states: Apply retirement income exemptions
        - High-tax states: Apply progressive brackets
        - Simplified implementation using hardcoded rates
        - Uses retirement_state from config.py if state parameter is None
    """
    # Get state from config if not provided
    if state is None:
        try:
            config_mgr = get_config_manager()
            state = config_mgr.get('personal_info', 'retirement_state', 'FL')
            logger.debug(f"Using state from config: {state}")
        except Exception as e:
            logger.warning(f"Could not load state from config: {e}, defaulting to FL")
            state = 'FL'
    
    logger.debug(f"Calculating state tax for {state}, AGI: ${state_agi:,.2f}")
    
    # No-tax states
    NO_TAX_STATES = ['FL', 'TX', 'WA', 'NV', 'SD', 'WY', 'AK', 'TN', 'NH']
    if state in NO_TAX_STATES:
        return 0.0, {'state': state, 'note': 'No state income tax'}
    
    # Retirement-friendly states (exempt all retirement income)
    RETIREMENT_EXEMPT_STATES = {
        'PA': 999999999,  # Pennsylvania - all retirement income exempt
        'IL': 999999999,  # Illinois - all retirement income exempt
        'MS': 999999999,  # Mississippi - all retirement income exempt
    }
    
    # States that don't tax Social Security
    SS_EXEMPT_STATES = ['PA', 'IL', 'MS', 'AL', 'AZ', 'AR', 'DE', 'GA', 'HI', 'ID',
                        'IN', 'IA', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'NC', 'ND',
                        'OH', 'OK', 'OR', 'SC', 'TN', 'VA', 'WI', 'DC']
    
    # Apply retirement income exemptions
    adjusted_agi = state_agi
    exemption_applied = 0.0
    
    if state in RETIREMENT_EXEMPT_STATES:
        exemption = min(retirement_income, RETIREMENT_EXEMPT_STATES[state])
        adjusted_agi -= exemption
        exemption_applied += exemption
        logger.debug(f"{state}: Applied retirement income exemption: ${exemption:,.0f}")
    
    if state in SS_EXEMPT_STATES:
        adjusted_agi -= ss_benefits
        exemption_applied += ss_benefits
        logger.debug(f"{state}: Exempted SS benefits: ${ss_benefits:,.0f}")
    
    # Simplified state tax brackets (2024 estimates)
    # In production, load from CSV files
    STATE_TAX_RATES = {
        'CA': [(0, 10412, 0.01), (10412, 24684, 0.02), (24684, 38959, 0.04),
               (38959, 54081, 0.06), (54081, 68350, 0.08), (68350, 349137, 0.093),
               (349137, 418961, 0.103), (418961, 698271, 0.113), (698271, float('inf'), 0.123)],
        'NY': [(0, 17150, 0.04), (17150, 23600, 0.045), (23600, 27900, 0.0525),
               (27900, 161550, 0.055), (161550, 323200, 0.06), (323200, 2155350, 0.0685),
               (2155350, float('inf'), 0.109)],
        'NJ': [(0, 20000, 0.014), (20000, 35000, 0.0175), (35000, 40000, 0.035),
               (40000, 75000, 0.05525), (75000, 500000, 0.0637), (500000, 1000000, 0.0897),
               (1000000, float('inf'), 0.1075)],
        'MA': [(0, float('inf'), 0.05)],    # Flat 5%
        'CO': [(0, float('inf'), 0.044)],   # Flat 4.4%
        'NC': [(0, float('inf'), 0.0475)],  # Flat 4.75%
        'PA': [(0, float('inf'), 0.0307)],  # Flat 3.07%
        'IL': [(0, float('inf'), 0.0495)],  # Flat 4.95%
        'MS': [(0, 10000, 0.0), (10000, float('inf'), 0.05)],  # 0% up to $10k, 5% above
    }
    
    # Standard deductions by state (simplified)
    STANDARD_DEDUCTIONS = {
        'CA': 10404, 'NY': 16050, 'NJ': 0, 'MA': 0, 'CO': 0, 'NC': 25500
    }
    
    # Apply standard deduction
    std_deduction = STANDARD_DEDUCTIONS.get(state or '', 0)
    taxable_income = max(0, adjusted_agi - std_deduction)
    
    # Calculate tax using brackets
    state_tax = 0.0
    if state in STATE_TAX_RATES:
        brackets = STATE_TAX_RATES[state]
        for bracket_min, bracket_max, rate in brackets:
            if taxable_income > bracket_min:
                taxable_in_bracket = min(taxable_income, bracket_max) - bracket_min
                state_tax += taxable_in_bracket * rate
    else:
        # Default: assume 5% flat rate for unknown states
        state_tax = taxable_income * 0.05
        logger.warning(f"Using default 5% rate for state: {state}")
    
    details = {
        'state': state,
        'state_agi': state_agi,
        'retirement_exemption': exemption_applied,
        'standard_deduction': std_deduction,
        'taxable_income': taxable_income,
        'state_tax': state_tax
    }
    
    logger.info(f"State tax ({state}): ${state_tax:,.0f} on taxable income ${taxable_income:,.0f}")
    
    return state_tax, details


def calculate_amt(income: float, conversions: float, deductions: float,
                 state_taxes: float = 0, year: int = 2024,
                 filing_status: str = "married_filing_jointly",
                 iso_spread: float = 0,
                 private_activity_bonds: float = 0) -> Tuple[float, float, float, Dict]:
    """
    Calculate Alternative Minimum Tax
    
    Args:
        income: Regular taxable income
        conversions: Roth conversion amount
        deductions: Regular tax deductions
        state_taxes: State and local taxes paid (AMT adjustment)
        year: Tax year
        filing_status: Filing status
        iso_spread: ISO exercise spread (if applicable)
        private_activity_bonds: Private activity bond interest
    
    Returns:
        Tuple of (amt_owed, tentative_amt, regular_tax, details)
        - amt_owed: Additional tax due to AMT (0 if regular tax higher)
        - tentative_amt: Total AMT calculated
        - regular_tax: Regular income tax
        - details: Dictionary with calculation breakdown
    """
    logger.debug(f"Calculating AMT: income=${income:,.0f}, conversions=${conversions:,.0f}")
    
    # AMT Parameters (2024 values - in production, load from atm.csv)
    AMT_PARAMS = {
        'married_filing_jointly': {
            'exemption': 133300,
            'phase_out_threshold': 1218700,
            'phase_out_rate': 0.25,
            'rate_1': 0.26,
            'rate_1_threshold': 220700,
            'rate_2': 0.28
        },
        'single': {
            'exemption': 85700,
            'phase_out_threshold': 609350,
            'phase_out_rate': 0.25,
            'rate_1': 0.26,
            'rate_1_threshold': 220700,
            'rate_2': 0.28
        }
    }
    
    params = AMT_PARAMS.get(filing_status, AMT_PARAMS['married_filing_jointly'])
    
    # Step 1: Calculate regular tax (simplified - use existing function)
    try:
        _tax_brackets = get_income_tax_brackets(year)
        regular_tax, _, _ = calculate_taxable_income(
            income + conversions - deductions,
            pd.DataFrame(_tax_brackets)
        )
    except (ValueError, TypeError, KeyError) as e:
        # Fallback to simple calculation
        logging.warning(f"calculate_taxable_income failed, using fallback: {e}")
        regular_tax = (income + conversions - deductions) * 0.24
    
    # Step 2: Calculate AMTI (Alternative Minimum Taxable Income)
    amti = income + conversions
    
    # Add back AMT adjustments
    amti += state_taxes  # State taxes added back for AMT
    
    # Add AMT preferences
    amti += iso_spread  # ISO exercise spread
    amti += private_activity_bonds  # Private activity bond interest
    
    # Step 3: Calculate AMT exemption (with phase-out)
    if amti <= params['phase_out_threshold']:
        amt_exemption = params['exemption']
    else:
        excess = amti - params['phase_out_threshold']
        reduction = excess * params['phase_out_rate']
        amt_exemption = max(0, params['exemption'] - reduction)
    
    # Step 4: Calculate tentative AMT
    amti_after_exemption = max(0, amti - amt_exemption)
    
    if amti_after_exemption <= params['rate_1_threshold']:
        tentative_amt = amti_after_exemption * params['rate_1']
    else:
        tentative_amt = (
            params['rate_1_threshold'] * params['rate_1'] +
            (amti_after_exemption - params['rate_1_threshold']) * params['rate_2']
        )
    
    # Step 5: AMT owed is excess over regular tax
    amt_owed = max(0, tentative_amt - regular_tax)
    
    # Calculation details
    details = {
        'amti': amti,
        'amt_exemption': amt_exemption,
        'amti_after_exemption': amti_after_exemption,
        'tentative_amt': tentative_amt,
        'regular_tax': regular_tax,
        'amt_owed': amt_owed,
        'in_amt': amt_owed > 0,
        'adjustments': {
            'state_taxes': state_taxes,
            'iso_spread': iso_spread,
            'private_activity_bonds': private_activity_bonds
        }
    }
    
    if amt_owed > 0:
        logger.warning(f"AMT triggered: ${amt_owed:,.0f} additional tax")
    else:
        logger.debug(f"No AMT: Regular tax ${regular_tax:,.0f} >= Tentative AMT ${tentative_amt:,.0f}")
    
    return amt_owed, tentative_amt, regular_tax, details


def calculate_net_investment_income(interest: float = 0,
                                   dividends: float = 0,
                                   capital_gains: float = 0,
                                   rental_income: float = 0,
                                   royalties: float = 0) -> float:
    """
    Calculate Net Investment Income for NIIT
    
    Args:
        interest: Interest income (taxable)
        dividends: Dividend income (qualified and non-qualified)
        capital_gains: Capital gains (long-term and short-term)
        rental_income: Passive rental income
        royalties: Royalty income
    
    Returns:
        Total net investment income
        
    Note:
        Excludes wages, SS benefits, IRA/401k distributions, tax-exempt interest
    """
    nii = interest + dividends + capital_gains + rental_income + royalties
    
    logger.debug(f"Net Investment Income: Interest=${interest:,.0f}, "
                f"Dividends=${dividends:,.0f}, "
                f"Capital Gains=${capital_gains:,.0f}, "
                f"Total NII=${nii:,.0f}")
    
    return nii


# Named tuple for the resolved IRMAA bracket values — avoids positional confusion
# when _resolve_irmaa returns four floats to its caller.
from typing import NamedTuple

class _IrmaaResolved(NamedTuple):
    """All per-bracket Medicare cost components resolved in a single CSV scan."""
    annual_irmaa_penalty: float   # Part B IRMAA penalty × 12 (per eligible person)
    part_b_monthly: float         # All-in monthly Part B premium (base + surcharge)
    part_a_monthly: float         # Monthly Part A premium (0 for premium-free Part A)
    part_d_monthly_total: float   # Part D base + IRMAA surcharge, monthly


# Sentinel returned by _resolve_irmaa when no IRMAA bracket matches (e.g. the
# CSV is unavailable or the year is out of range).  Centralising the fallback
# values here eliminates the duplicate _IrmaaResolved(...) literal that
# previously appeared in both _resolve_irmaa and calculate_medicare_costs.
_STANDARD_IRMAA_RESOLVED = _IrmaaResolved(
    annual_irmaa_penalty=0.0,
    part_b_monthly=PART_B_MONTHLY_STANDARD_PREMIUM,
    part_a_monthly=0.0,
    part_d_monthly_total=PART_D_ANNUAL_BASE_PREMIUM / 12,
)


def _resolve_irmaa(
    magi: float,
    irmaa_bracket_df: pd.DataFrame,
) -> _IrmaaResolved:
    """Return all per-bracket Medicare cost components in a single CSV scan.

    ``irmaa.csv`` is the single source of truth for Part A, Part B, and Part D
    costs.  Each row carries:

    * ``part_b_monthly``      — all-in monthly Part B premium (base + IRMAA surcharge)
    * ``part_a_monthly``      — monthly Part A premium (0 for premium-free Part A)
    * ``part_d_base_monthly`` — CMS national base Part D beneficiary premium
    * ``part_d_irmaa_monthly``— income-tiered Part D IRMAA surcharge

    A single loop finds the matched bracket and extracts all four values at once,
    replacing the previous two-pass pattern (``calculate_irmma_penalty`` + a
    second ``.loc[]`` scan).

    ``annual_irmaa_penalty`` is returned as a **per-person** value (``part_b *
    12``).  The caller is responsible for multiplying by the number of
    Medicare-eligible persons so that mixed-age couples (one person on Medicare,
    one not yet eligible) are handled correctly.

    Args:
        magi: MAGI used for IRMAA bracket matching (2-year lookback value).
        irmaa_bracket_df: DataFrame with columns ``lower``, ``upper``,
            ``part_b_monthly``, ``part_a_monthly``, ``part_d_base_monthly``,
            ``part_d_irmaa_monthly`` as returned by :func:`get_medicare_costs`.

    Returns:
        :class:`_IrmaaResolved` namedtuple.  Falls back to
        :data:`_STANDARD_IRMAA_RESOLVED` when no bracket matches.
    """
    cols = ['lower', 'upper', 'part_b_monthly', 'part_a_monthly',
            'part_d_base_monthly', 'part_d_irmaa_monthly']
    for lower, upper, part_b, part_a, part_d_base, part_d_irmaa in irmaa_bracket_df[cols].values:
        if lower <= magi <= upper:
            annual_penalty = max(0.0, (float(part_b) - PART_B_MONTHLY_STANDARD_PREMIUM) * 12)   # per-person; caller multiplies by eligible count
            part_d_total   = float(part_d_base) + float(part_d_irmaa)
            return _IrmaaResolved(
                annual_irmaa_penalty=annual_penalty,
                part_b_monthly=float(part_b),
                part_a_monthly=float(part_a),
                part_d_monthly_total=part_d_total,
            )
    # Fallback: no bracket matched — use statutory standard premiums
    return _STANDARD_IRMAA_RESOLVED


def _medicare_costs_for_person(
    age: int,
    label: str,
    part_b_monthly: float,
    part_a_monthly: float,
    part_d_monthly_total: float,
    has_medigap: bool,
) -> Tuple[Dict[str, float], float]:
    """Return (breakdown_slice, subtotal) for one Medicare-eligible person.

    All premium inputs come from the matched ``irmaa.csv`` bracket row via
    :func:`_resolve_irmaa`, making ``irmaa.csv`` the single source of truth for
    Part A, Part B, and Part D costs.

    Args:
        age: Person's current age.
        label: Key suffix used in the breakdown dict — ``"primary"`` or ``"spouse"``.
        part_b_monthly: All-in monthly Part B premium (base + IRMAA surcharge).
        part_a_monthly: Monthly Part A premium (0 for premium-free Part A).
        part_d_monthly_total: Monthly Part D cost (base + IRMAA surcharge).
        has_medigap: Whether the person carries Medigap supplemental coverage.

    Returns:
        Tuple of (breakdown_slice, subtotal) where breakdown_slice contains the
        four cost components keyed by label, and subtotal is their sum.
        Returns ({}, 0.0) when the person is not yet Medicare-eligible.
    """
    if age < MEDICARE_ELIGIBILITY_AGE:
        return {}, 0.0

    part_a   = part_a_monthly * 12
    part_b   = part_b_monthly * 12
    part_d   = part_d_monthly_total * 12
    medigap  = MEDIGAP_ANNUAL_PREMIUM if has_medigap else 0.0
    subtotal = part_a + part_b + part_d + medigap

    return {
        f'part_a_{label}':  part_a,
        f'part_b_{label}':  part_b,
        f'part_d_{label}':  part_d,
        f'medigap_{label}': medigap,
    }, subtotal


def calculate_medicare_costs(age_primary: int,
                            age_spouse: int,
                            magi_two_years_ago: float,
                            year: int,
                            filing_status: str = "married_filing_jointly",
                            has_medigap: bool = True) -> Tuple[float, "MedicareBreakdown"]:
    """
    Calculate total Medicare costs including IRMAA.

    Uses :func:`get_medicare_costs` (from ``load_data``) to load the IRMAA
    bracket table and :func:`_resolve_irmaa` for a single-pass surcharge and
    premium lookup.  Per-person cost assembly is delegated to the private helper
    :func:`_medicare_costs_for_person`.

    Args:
        age_primary: Primary person age.
        age_spouse: Spouse age.
        magi_two_years_ago: MAGI from 2 years prior for IRMAA (2-year lookback).
        year: Current year.
        filing_status: Filing status (``"married_filing_jointly"`` or ``"single"``).
        has_medigap: Whether they carry Medigap supplemental coverage.

    Returns:
        Tuple of (total_medicare_cost, cost_breakdown).
    """
    logger.debug(f"Calculating Medicare costs for year {year}, ages {age_primary}/{age_spouse}")

    # --- Load IRMAA bracket table (I/O — isolated in its own try/except) ------
    try:
        irmaa_bracket_df = get_medicare_costs(year - 2)
    except Exception as e:
        logger.warning(f"IRMAA bracket load failed: {e}, using standard premium")
        irmaa_bracket_df = None

    # --- Single-pass bracket scan: all Part A/B/D costs from irmaa.csv --------
    # _resolve_irmaa returns a per-person annual_irmaa_penalty; we multiply by
    # the actual number of Medicare-eligible persons below (after the helper
    # calls) so that mixed-age couples are handled correctly.
    if isinstance(irmaa_bracket_df, pd.DataFrame):
        resolved = _resolve_irmaa(magi_two_years_ago, irmaa_bracket_df)
    else:
        resolved = _STANDARD_IRMAA_RESOLVED

    # --- Compute per-person costs via the shared helper -----------------------
    primary_slice, primary_subtotal = _medicare_costs_for_person(
        age_primary, "primary",
        resolved.part_b_monthly, resolved.part_a_monthly,
        resolved.part_d_monthly_total, has_medigap,
    )
    spouse_slice, spouse_subtotal = _medicare_costs_for_person(
        age_spouse, "spouse",
        resolved.part_b_monthly, resolved.part_a_monthly,
        resolved.part_d_monthly_total, has_medigap,
    )

    total_cost = primary_subtotal + spouse_subtotal

    # Multiply the per-person IRMAA penalty by the number of persons who are
    # actually on Medicare (primary_subtotal > 0 means that person is eligible).
    # This fixes the previous over-count for mixed-age couples where only one
    # person is 65+ but filing_status is "married_filing_jointly".
    medicare_eligible_count = int(primary_subtotal > 0) + int(spouse_subtotal > 0)
    irmaa_penalty = resolved.annual_irmaa_penalty * medicare_eligible_count

    # --- Assemble the full breakdown dict -------------------------------------
    # _EMPTY_MEDICARE_BREAKDOWN zero-initialises all per-person keys so that
    # ineligible persons (age < 65, whose slice is {}) are represented as 0.0
    # rather than missing entirely.  Dict-unpack (**primary_slice, **spouse_slice)
    # overwrites the zeros for eligible persons.
    # cast() is required because TypedDict cannot be assigned from a plain dict
    # literal that contains **-unpacked entries (basedpyright limitation).
    _breakdown: MedicareBreakdown = cast("MedicareBreakdown", {
        **_EMPTY_MEDICARE_BREAKDOWN,
        **primary_slice,
        **spouse_slice,
        'irmaa_penalty':       irmaa_penalty,
        'total_medicare_cost': total_cost,
    })

    logger.info(f"Year {year}: Medicare costs = ${total_cost:,.0f} "
                f"(IRMAA penalty: ${irmaa_penalty:,.0f})")

    return total_cost, _breakdown


@dataclass(frozen=True)
class _AgeStatus:
    """Medicare/pre-Medicare eligibility status for both persons.

    Computed once by :func:`_classify_ages` and consumed by
    :func:`calculate_total_healthcare_costs` to eliminate repeated age
    comparisons and the inconsistent ``age_spouse > 0`` idiom.
    """
    primary_on_medicare: bool
    spouse_on_medicare: bool
    primary_pre_medicare: bool
    spouse_pre_medicare: bool
    medicare_count: int       # 0, 1, or 2 — persons on Medicare
    pre_medicare_count: int   # 0, 1, or 2 — persons not yet on Medicare
    total_persons: int        # 1 (no spouse) or 2


class MedicareBreakdown(TypedDict, total=False):
    """Typed mapping of Medicare cost components returned by :func:`calculate_medicare_costs`.

    Using ``TypedDict`` (rather than a plain ``Dict`` or a nested dataclass)
    keeps the existing :func:`calculate_medicare_costs` return type unchanged at
    runtime while giving callers and type-checkers a precise, documented
    contract for every key.  ``total=False`` marks all keys as optional so that
    the empty-dict default on :class:`HealthcareCostBreakdown` is also valid.

    All premium values originate from ``irmaa.csv`` via :func:`_resolve_irmaa`,
    making that file the single source of truth for Part A, Part B, and Part D
    costs including income-related IRMAA surcharges.

    Keys
    ----
    part_a_primary, part_a_spouse   : Part A annual premiums per person.
    part_b_primary, part_b_spouse   : Part B annual premiums per person.
    part_d_primary, part_d_spouse   : Part D annual premiums per person (base + IRMAA).
    medigap_primary, medigap_spouse : Medigap annual premiums per person.
    irmaa_penalty                   : Total Part B IRMAA surcharge for the year.
    total_medicare_cost             : Sum of all Medicare components.
    """
    part_a_primary: float
    part_a_spouse: float
    part_b_primary: float
    part_b_spouse: float
    part_d_primary: float
    part_d_spouse: float
    medigap_primary: float
    medigap_spouse: float
    irmaa_penalty: float
    total_medicare_cost: float




# Module-level sentinel used as the default value for medicare_detail when no
# Medicare-eligible person is present.  All ten keys are zero-initialised so
# that callers can safely iterate the breakdown without checking for missing keys.
# Defined here — after MedicareBreakdown — so both calculate_medicare_costs and
# calculate_total_healthcare_costs can reference it.
# cast() is required because TypedDict cannot be assigned from a plain dict literal
# (basedpyright limitation).
_EMPTY_MEDICARE_BREAKDOWN: MedicareBreakdown = cast("MedicareBreakdown", {
    'part_a_primary':      0.0,
    'part_a_spouse':       0.0,
    'part_b_primary':      0.0,
    'part_b_spouse':       0.0,
    'part_d_primary':      0.0,
    'part_d_spouse':       0.0,
    'medigap_primary':     0.0,
    'medigap_spouse':      0.0,
    'irmaa_penalty':       0.0,
    'total_medicare_cost': 0.0,
})


def _classify_ages(age_primary: int, age_spouse: int) -> _AgeStatus:
    """Return Medicare/pre-Medicare eligibility status for both persons.

    Args:
        age_primary: Primary person's age (must be > 0).
        age_spouse:  Spouse's age; pass 0 to indicate no spouse.

    Returns:
        Frozen :class:`_AgeStatus` instance capturing all derived booleans
        and person counts needed by :func:`calculate_total_healthcare_costs`.

    Raises:
        ValueError: If ``age_primary`` is not a positive integer.
    """
    if age_primary <= 0:
        raise ValueError(
            f"age_primary must be a positive integer, got {age_primary!r}"
        )
    has_spouse = age_spouse > 0
    p_med = age_primary >= MEDICARE_ELIGIBILITY_AGE
    s_med = has_spouse and age_spouse >= MEDICARE_ELIGIBILITY_AGE
    return _AgeStatus(
        primary_on_medicare=p_med,
        spouse_on_medicare=s_med,
        primary_pre_medicare=not p_med,
        spouse_pre_medicare=has_spouse and not s_med,
        medicare_count=int(p_med) + int(s_med),
        pre_medicare_count=int(not p_med) + int(has_spouse and not s_med),
        total_persons=1 + int(has_spouse),
    )


@dataclass(frozen=True)
class HealthcareCostBreakdown:
    """Itemised healthcare costs returned by :func:`calculate_total_healthcare_costs`.

    Using a frozen dataclass instead of a plain ``dict`` provides:
    - Attribute-style access with IDE auto-complete and type checking.
    - A computed :attr:`total` property that is always consistent with the
      individual fields (no separately maintained ``total_healthcare_cost`` key).
    - An auto-generated ``__repr__`` useful for logging and debugging.
    - Immutability — callers cannot accidentally mutate the breakdown.
    """
    medicare: float = 0.0
    pre_medicare: float = 0.0
    out_of_pocket: float = 0.0
    ltc_insurance: float = 0.0
    medicare_detail: MedicareBreakdown = field(default_factory=lambda: _EMPTY_MEDICARE_BREAKDOWN)

    @property
    def total(self) -> float:
        """Sum of all cost components."""
        return self.medicare + self.pre_medicare + self.out_of_pocket + self.ltc_insurance


def _calculate_medicare(
    status: _AgeStatus,
    age_primary: int,
    age_spouse: int,
    magi_two_years_ago: float,
    year: int,
    filing_status: str,
    has_medigap: bool,
) -> Tuple[float, MedicareBreakdown]:
    """Return ``(cost, detail)`` for Medicare-eligible persons; ``(0.0, empty)`` otherwise.

    Centralises the ``medicare_count`` guard and the ``_EMPTY_MEDICARE_BREAKDOWN``
    sentinel so that :func:`calculate_total_healthcare_costs` does not need to
    manage mutable initialisation before a conditional call.

    Args:
        status:             Pre-computed eligibility flags from :func:`_classify_ages`.
        age_primary:        Primary person's age.
        age_spouse:         Spouse's age; 0 means no spouse.
        magi_two_years_ago: MAGI from 2 years prior (used for IRMAA).
        year:               Current year.
        filing_status:      Filing status string (e.g. ``"married_filing_jointly"``).
        has_medigap:        Whether they carry Medigap coverage.

    Returns:
        Tuple of ``(medicare_cost, MedicareBreakdown)``.
    """
    if status.medicare_count == 0:
        return 0.0, _EMPTY_MEDICARE_BREAKDOWN
    return calculate_medicare_costs(
        age_primary, age_spouse, magi_two_years_ago, year, filing_status, has_medigap
    )


def calculate_total_healthcare_costs(age_primary: int,
                                     age_spouse: int,
                                     magi_two_years_ago: float,
                                     year: int,
                                     filing_status: str = "married_filing_jointly",
                                     health_status: str = "average",
                                     has_ltc_insurance: bool = False,
                                     has_medigap: bool = True) -> Tuple[float, HealthcareCostBreakdown]:
    """
    Calculate comprehensive healthcare costs for the year.

    Args:
        age_primary: Primary person's age.
        age_spouse: Spouse's age; pass 0 to indicate no spouse.
        magi_two_years_ago: MAGI from 2 years prior (used for IRMAA).
        year: Current year.
        filing_status: Filing status (e.g. ``"married_filing_jointly"``).
        health_status: One of ``"healthy"``, ``"average"``, or ``"chronic"``.
        has_ltc_insurance: Whether they carry LTC insurance.
        has_medigap: Whether they carry Medigap coverage.

    Returns:
        Tuple of ``(total_healthcare_cost, HealthcareCostBreakdown)``.
    """
    status = _classify_ages(age_primary, age_spouse)
    logger.debug(
        f"calculate_total_healthcare_costs: year={year}, "
        f"ages={age_primary}/{age_spouse}, "
        f"{status.total_persons} person(s), "
        f"{status.medicare_count} on Medicare, "
        f"{status.pre_medicare_count} pre-Medicare"
    )

    # --- Medicare costs (one or both persons aged 65+) -------------------
    medicare_cost, medicare_detail = _calculate_medicare(
        status, age_primary, age_spouse, magi_two_years_ago, year,
        filing_status, has_medigap
    )

    # --- Pre-Medicare / ACA costs (one or both persons under 65) ---------
    # calculate_aca_premium_for_year returns 0.0 when neither person is in
    # their configured ACA age window, so no guard is needed here.
    aca_cost = calculate_aca_premium_for_year(year, age_primary, age_spouse)

    # --- Out-of-pocket expenses -------------------------------------------
    # Falls back to OOP_COST_DEFAULT ("average") for unrecognised health_status values.
    oop_cost: int = OOP_COSTS_BY_HEALTH_STATUS.get(health_status, OOP_COST_DEFAULT)

    # --- Long-term care insurance premiums --------------------------------
    ltc_cost = LTC_ANNUAL_PREMIUM_PER_PERSON * status.total_persons if has_ltc_insurance else 0.0

    breakdown = HealthcareCostBreakdown(
        medicare=medicare_cost,
        pre_medicare=aca_cost,
        out_of_pocket=oop_cost,
        ltc_insurance=ltc_cost,
        medicare_detail=medicare_detail,
    )

    logger.info(f"Year {year}: Total healthcare cost = ${breakdown.total:,.0f}")

    return breakdown.total, breakdown


def _validate_healthcare_projection_inputs(
    start_year: int,
    end_year: int,
    magi_projections: List[float],
) -> None:
    """Raise ValueError for invalid project_healthcare_costs arguments."""
    if start_year > end_year:
        raise ValueError(
            f"start_year ({start_year}) must be <= end_year ({end_year})"
        )
    if not magi_projections:
        raise ValueError(
            "magi_projections must contain at least one value "
            f"(one per year from {start_year} to {end_year})"
        )


def _build_magi_lookback(magi_projections: Sequence[float]) -> List[float]:
    """Prepend ``_IRMAA_LOOKBACK_YEARS`` sentinel values to *magi_projections*.

    IRMAA surcharges in year N are based on MAGI from year N-2.  By prepending
    ``_IRMAA_LOOKBACK_YEARS`` copies of the first projected value, index
    ``year_index`` into the returned list always yields the correct lookback
    MAGI for projection year ``year_index``, with no special-casing for the
    first two years.

    Args:
        magi_projections: Already-padded sequence of MAGI values, one per
            projection year.  Must be non-empty.

    Returns:
        New list of length ``len(magi_projections) + _IRMAA_LOOKBACK_YEARS``.
    """
    return [magi_projections[0]] * _IRMAA_LOOKBACK_YEARS + list(magi_projections)


def _healthcare_projection_row(
    year_index: int,
    year: int,
    age_primary_start: int,
    age_spouse_start: int,
    magi_lookback: Sequence[float],
    health_status: str,
    has_ltc_insurance: bool,
    has_medigap: bool,
    filing_status: str = "married_filing_jointly",
) -> Dict:
    """Compute a single year's healthcare projection row."""
    age_primary = age_primary_start + year_index
    age_spouse = age_spouse_start + year_index
    total_cost, breakdown = calculate_total_healthcare_costs(
        age_primary=age_primary,
        age_spouse=age_spouse,
        magi_two_years_ago=magi_lookback[year_index],
        year=year,
        filing_status=filing_status,
        health_status=health_status,
        has_ltc_insurance=has_ltc_insurance,
        has_medigap=has_medigap,
    )
    return {
        'year': year,
        'age_primary': age_primary,
        'age_spouse': age_spouse,
        'total_healthcare_cost': total_cost,
        **asdict(breakdown),
    }


def project_healthcare_costs(
    start_year: int,
    end_year: int,
    age_primary_start: int,
    age_spouse_start: int,
    magi_projections: List[float],
    health_status: str = "average",
    has_ltc_insurance: bool = False,
    has_medigap: bool = True,
    filing_status: str = "married_filing_jointly",
) -> pd.DataFrame:
    """
    Project healthcare costs over retirement period

    Args:
        start_year: Starting year
        end_year: Ending year
        age_primary_start: Primary person's starting age
        age_spouse_start: Spouse's starting age
        magi_projections: List of projected MAGI values
        health_status: Health status assumption
        has_ltc_insurance: Whether they have LTC insurance
        has_medigap: Whether they have Medigap coverage
        filing_status: Filing status used for IRMAA calculations
            (e.g. ``"married_filing_jointly"`` or ``"single"``).

    Returns:
        DataFrame with one row per year and the following columns:

        - ``year`` — calendar year
        - ``age_primary`` / ``age_spouse`` — ages for that year
        - ``total_healthcare_cost`` — combined annual cost for both persons
        - All fields from :class:`HealthcareCostBreakdown` (via
          :func:`dataclasses.asdict`), including Medicare part costs,
          IRMAA penalty, ACA premiums, LTC premiums, and OOP costs.
    """
    logger.info(f"Projecting healthcare costs from {start_year} to {end_year}")

    _validate_healthcare_projection_inputs(start_year, end_year, magi_projections)

    expected_years = end_year - start_year + 1
    if len(magi_projections) < expected_years:
        logger.warning(
            f"MAGI projections ({len(magi_projections)}) shorter than year range "
            f"({expected_years}). Padding with last value."
        )
        # Use itertools.chain + repeat + islice to lazily extend the sequence
        # without re-binding the parameter or allocating an intermediate list
        # larger than needed.
        magi_padded: Sequence[float] = list(itertools.islice(
            itertools.chain(magi_projections, itertools.repeat(magi_projections[-1])),
            expected_years,
        ))
    else:
        magi_padded = magi_projections

    # Prepend _IRMAA_LOOKBACK_YEARS sentinel values so that index year_index
    # always yields the MAGI from 2 years before projection year year_index.
    magi_lookback = _build_magi_lookback(magi_padded)

    return pd.DataFrame.from_records(
        _healthcare_projection_row(
            year_index, year,
            age_primary_start, age_spouse_start,
            magi_lookback,
            health_status, has_ltc_insurance, has_medigap,
            filing_status,
        )
        for year_index, year in enumerate(range(start_year, end_year + 1))
    )


def calculate_niit(
    net_investment_income: float,
    magi: float,
    filing_status: str = "married_filing_jointly",
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate Net Investment Income Tax (3.8% surtax).

    Args:
        net_investment_income: Total investment income (must be non-negative).
        magi: Modified Adjusted Gross Income (must be non-negative).
        filing_status: Filing status — must be a key in NIIT_THRESHOLDS;
            raises ValueError for unrecognised values.

    Returns:
        Tuple of (niit_amount, calculation_details).

    Formula:
        NIIT = min(NII, max(0, MAGI - threshold)) * NIIT_RATE

    Key Thresholds (NOT indexed for inflation since 2013):
        - Married Filing Jointly:     $250,000
        - Single:                     $200,000
        - Married Filing Separately:  $125,000
        - Head of Household:          $200,000
    """
    logger.debug("Calculating NIIT: NII=$%,.0f, MAGI=$%,.0f",
                 net_investment_income, magi)

    if net_investment_income < 0 or magi < 0:
        raise ValueError(
            f"Inputs must be non-negative: "
            f"net_investment_income={net_investment_income}, magi={magi}"
        )

    if filing_status not in NIIT_THRESHOLDS:
        raise ValueError(
            f"Unknown filing_status {filing_status!r}. "
            f"Valid values: {sorted(NIIT_THRESHOLDS)}"
        )

    threshold   = NIIT_THRESHOLDS[filing_status]
    niit_amount = min(net_investment_income, max(0, magi - threshold)) * NIIT_RATE

    details: Dict[str, Any] = {
        'net_investment_income': net_investment_income,
        'magi':            magi,
        'threshold':       threshold,
        'niit_rate':       NIIT_RATE,
        'niit_amount':     niit_amount,
        'subject_to_niit': niit_amount > 0,
    }

    if niit_amount > 0:
        logger.info("NIIT Triggered: MAGI=$%,.0f exceeds threshold=$%,.0f, NIIT=$%,.0f",
                    magi, threshold, niit_amount)
    else:
        logger.debug("No NIIT: MAGI=$%,.0f below threshold=$%,.0f", magi, threshold)

    return niit_amount, details



# Configure logging
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants
WITHDRAWAL_RATE = 0.04  # 4% withdrawal rate
MEDICARE_AGE = 65
RMD_AGE = 73  # Updated for 2023+ (SECURE Act 2.0)
ACA_SUBSIDY_THRESHOLD = 400  # % of Federal Poverty Level for max subsidies
TAXABLE_SS_RATE = 0.85  # 85% of SS benefits are taxable at higher incomes
FUND_CONSERVATION_TOLERANCE = 1.0  # Allow $1 rounding error in fund conservation checks
ROTH_IRA_INCOME_LIMIT = 240_000  # MFJ 2024 phase-out upper bound (update annually)
IRA_CONTRIBUTION_LIMIT = 7_000   # 2024 limit (age < 50); 8_000 if ≥ 50 (update annually)


# ==============================================================================
# DECISION LOGGING
# ==============================================================================

@dataclass
class DecisionReason:
    """A single named decision with its rationale and the values that drove it."""
    decision: str        # Short label, e.g. "Roth Conversion"
    action: str          # What was decided, e.g. "Convert $45,000"
    reason: str          # Human-readable explanation
    values: Dict[str, Any] = field(default_factory=dict)  # Supporting numbers


@dataclass
class DecisionLog:
    """
    Structured record of every material decision made for a single strategy year.

    Each stage populates the relevant fields.  Consumers (UI, reports) can
    iterate ``all_decisions()`` to get a flat list of every reason recorded.
    """
    # --- Tax strategy ---
    tax_strategy: List[DecisionReason] = field(default_factory=list)

    # --- Roth conversion ---
    roth_conversion: List[DecisionReason] = field(default_factory=list)

    # --- ACA / healthcare ---
    aca_decisions: List[DecisionReason] = field(default_factory=list)

    # --- IRMAA ---
    irmaa_decisions: List[DecisionReason] = field(default_factory=list)

    # --- Cash replenishment ---
    cash_replenishment: List[DecisionReason] = field(default_factory=list)

    # --- Brokerage replenishment ---
    brokerage_replenishment: List[DecisionReason] = field(default_factory=list)

    # --- Accumulation / contributions ---
    contribution_decisions: List[DecisionReason] = field(default_factory=list)

    # --- RMD ---
    rmd_decisions: List[DecisionReason] = field(default_factory=list)

    # --- LTCG harvesting ---
    ltcg_decisions: List[DecisionReason] = field(default_factory=list)

    # --- SS income ---
    ss_decisions: List[DecisionReason] = field(default_factory=list)

    def add(self, category: str, decision: str, action: str,
            reason: str, **values: Any) -> None:
        """Convenience method to append a :class:`DecisionReason` to *category*.

        Args:
            category: One of the field names on this dataclass
                      (e.g. ``"roth_conversion"``).
            decision: Short label for the decision point.
            action:   What was chosen.
            reason:   Human-readable explanation.
            **values: Arbitrary keyword arguments stored in
                      :attr:`DecisionReason.values` for display.

        Raises:
            AttributeError: If *category* is not a valid field name.
        """
        entry = DecisionReason(decision=decision, action=action,
                               reason=reason, values=dict(values))
        target: List[DecisionReason] = getattr(self, category)
        target.append(entry)

    def all_decisions(self) -> List[DecisionReason]:
        """Return every :class:`DecisionReason` across all categories, in
        insertion order per category."""
        out: List[DecisionReason] = []
        for f in (
            self.tax_strategy,
            self.roth_conversion,
            self.aca_decisions,
            self.irmaa_decisions,
            self.cash_replenishment,
            self.brokerage_replenishment,
            self.contribution_decisions,
            self.rmd_decisions,
            self.ltcg_decisions,
            self.ss_decisions,
        ):
            out.extend(f)
        return out

    def summary_lines(self) -> List[str]:
        """Return a flat list of human-readable summary strings, one per
        decision, suitable for logging or display."""
        lines = []
        for dr in self.all_decisions():
            vals = ", ".join(f"{k}={v}" for k, v in dr.values.items()) if dr.values else ""
            line = f"[{dr.decision}] {dr.action} — {dr.reason}"
            if vals:
                line += f" ({vals})"
            lines.append(line)
        return lines


def _category_for(entry: "DecisionReason") -> str:
    """Return the :class:`DecisionLog` field name that best matches *entry*.

    This is used when merging a sub-log (e.g. from ``rebalance_accounts``)
    into a stage-level :class:`DecisionLog`.  The mapping is based on the
    ``decision`` label stored on the entry.
    """
    label = entry.decision.lower()
    if "cash" in label:
        return "cash_replenishment"
    if "brokerage" in label or "taxable" in label:
        return "brokerage_replenishment"
    if "roth" in label and "conversion" not in label:
        return "roth_conversion"
    if "conversion" in label:
        return "roth_conversion"
    if "irmaa" in label:
        return "irmaa_decisions"
    if "aca" in label or "healthcare" in label:
        return "aca_decisions"
    if "rmd" in label:
        return "rmd_decisions"
    if "ltcg" in label or "capital gain" in label:
        return "ltcg_decisions"
    if "social security" in label or "ss " in label:
        return "ss_decisions"
    if "contribution" in label or "401k" in label or "ira" in label:
        return "contribution_decisions"
    # Default bucket
    return "tax_strategy"


@dataclass
class PortfolioBalances:
    """Container for portfolio account balances"""
    cash: float
    taxable: float  # Brokerage account
    traditional: float  # Tax-deferred (401k, Traditional IRA)
    roth: float  # Tax-free (Roth IRA, Roth 401k)
    daf: float  # Donor Advised Fund
    
    def total(self) -> float:
        """Calculate total portfolio value"""
        return self.cash + self.taxable + self.traditional + self.roth + self.daf


class BrokerageTransactionLog(TypedDict):
    """Typed transaction log returned by :func:`replenish_brokerage_buffer`.

    Keys
    ----
    traditional_to_brokerage:
        Amount distributed from the Traditional account to the Brokerage buffer.
    brokerage_replenishment:
        Total amount added to the Brokerage buffer this year (equals
        ``traditional_to_brokerage`` since Roth→Brokerage is intentionally omitted).
    """
    traditional_to_brokerage: float
    brokerage_replenishment:  float


class ScenarioType(str, Enum):
    """Available retirement scenario types"""
    DEFAULT = "default"
    EARLY_RETIRE = "early_retire"
    HIGH_INCOME = "high_income"


@dataclass(frozen=True)
class ScenarioConfig:
    """Configuration for a retirement scenario
    
    This dataclass defines the structure of scenario parameters used
    for retirement withdrawal strategy calculations.
    """
    start_year: int
    end_year: int
    initial_balances: PortfolioBalances
    initial_expenses: float
    person1_name: str
    person2_name: str
    growth_rate: float
    expense_inflation: float
    ss_claiming_age: int
    retirement_year: int
    has_wages: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility"""
        return {
            'start_year': self.start_year,
            'end_year': self.end_year,
            'initial_balances': self.initial_balances,
            'initial_expenses': self.initial_expenses,
            'person1_name': self.person1_name,
            'person2_name': self.person2_name,
            'growth_rate': self.growth_rate,
            'expense_inflation': self.expense_inflation,
            'ss_claiming_age': self.ss_claiming_age,
            'retirement_year': self.retirement_year,
            'has_wages': self.has_wages
        }


@dataclass
class YearlyStrategy:
    """Container for a year's withdrawal strategy"""
    year: int
    age_primary: int
    age_spouse: int
    stage: str
    
    # Income sources
    wages: float
    ss_benefits: float
    rmd_amount: float
    
    # Withdrawals and conversions
    traditional_withdrawal: float
    taxable_withdrawal: float
    roth_withdrawal: float
    roth_conversion: float
    
    # Tax optimization
    ltcg_harvested: float  # Long-term capital gains harvested
    daf_contribution: float
    
    # Expenses and taxes
    expenses: float
    agi: float  # Adjusted Gross Income
    magi: float  # Modified Adjusted Gross Income
    federal_tax: float
    irmaa_penalty: float
    aca_premium: float
    
    # Account balances (end of year)
    balances: PortfolioBalances
    
    # NEW: Fund movement tracking (v2.0 - Account Rebalancing)
    cash_replenishment: float = 0.0
    payroll_tax: float = 0.0    # FICA + Medicare + State + FUTA/SUTA (wages years only)
    wages_to_trad: float = 0.0  # Wages → Traditional 401k contribution
    wages_to_roth: float = 0.0  # Wages → Roth 401k / Roth IRA contribution
    brokerage_replenishment: float = 0.0
    traditional_to_cash: float = 0.0
    traditional_to_brokerage: float = 0.0
    brokerage_to_cash: float = 0.0
    roth_to_cash: float = 0.0
    roth_to_brokerage: float = 0.0
    conversion_executed: float = 0.0
    # Accumulation-phase contributions routed from take-home cash
    cash_to_roth: float = 0.0
    cash_to_brokerage: float = 0.0

    # Decision reasoning log (v2.1 - Strategy Instrumentation)
    decision_log: DecisionLog = field(default_factory=DecisionLog)
    
    def _collect_fund_movements(self) -> Dict[str, float]:
        """
        Collect all fund movements with signed amounts.
        
        Returns:
            Dictionary mapping movement descriptions to signed amounts
            (negative = outflow, positive = inflow)
        """
        return {
            "Traditional → Cash": -self.traditional_to_cash,
            "Traditional → Brokerage": -self.traditional_to_brokerage,
            "Brokerage → Cash": -self.brokerage_to_cash,
            "Roth → Cash": -self.roth_to_cash,
            "Roth → Brokerage": -self.roth_to_brokerage,
            "Conversion (Trad→Roth)": 0.0,  # Net zero: -trad, +roth
            "Cash Replenishment": self.cash_replenishment,
            "Brokerage Replenishment": self.brokerage_replenishment,
        }
    
    def _log_fund_movements(self, movements: Dict[str, float]) -> None:
        """
        Log fund movements categorized by sign.
        
        Args:
            movements: Dictionary mapping movement descriptions to signed amounts
                      (negative = outflow, positive = inflow)
        """
        outflows = {k: v for k, v in movements.items() if v < 0}
        inflows = {k: v for k, v in movements.items() if v > 0}
        
        if outflows:
            logger.info("  OUTFLOWS (money leaving accounts):")
            for description, amount in outflows.items():
                logger.info(f"    {description}: ${abs(amount):,.2f}")
            logger.info(f"    TOTAL OUTFLOWS: ${abs(sum(outflows.values())):,.2f}")
        
        if inflows:
            logger.info("  INFLOWS (money entering accounts):")
            for description, amount in inflows.items():
                logger.info(f"    {description}: ${amount:,.2f}")
            logger.info(f"    TOTAL INFLOWS: ${sum(inflows.values()):,.2f}")
    
    def validate_fund_conservation(self) -> bool:
        """
        Verify that all fund movements balance to zero
        (what leaves one account enters another)
        
        Returns:
            True if funds are conserved, False otherwise
        """
        # Collect all fund movements with signed amounts
        movements = self._collect_fund_movements()
        
        # Early return if no movements occurred
        if all(amount == 0 for amount in movements.values()):
            logger.info(f"Year {self.year}: No fund movements this year")
            return True
        
        # Calculate net balance (should be zero)
        net_balance = sum(movements.values())
        
        # Log fund conservation details at INFO level
        logger.info(f"Year {self.year}: Fund Conservation Check")
        self._log_fund_movements(movements)
        logger.info(f"  NET BALANCE: ${abs(net_balance):,.2f} (should be ~$0)")
        
        # Check if balance is within tolerance
        if abs(net_balance) > FUND_CONSERVATION_TOLERANCE:
            logger.error(
                f"Year {self.year}: Fund conservation VIOLATED: "
                f"${abs(net_balance):,.2f} imbalance (see details above)"
            )
            return False
        
        logger.info(f"  Fund conservation: ✓ PASSED")
        return True


# ==============================================================================
# ACCOUNT REBALANCING HELPER FUNCTIONS (v2.0)
# ==============================================================================

def replenish_cash_buffer(balances: PortfolioBalances,
                          expenses: float,
                          age_primary: int,
                          year: int,
                          cash_target_override: Optional[float] = None) -> Tuple[PortfolioBalances, Dict[str, float], DecisionLog]:
    """
    Replenish cash buffer to target based on configured years of expenses.

    Implements tax-efficient cash buffer maintenance by transferring funds
    from other accounts in priority order:
    1. Brokerage → Cash (60% tax-free return of basis, 40% LTCG)
    2. Roth → Cash (tax-free if qualified, avoids LTCG from Brokerage→Cash)
    3. Traditional → Cash (ordinary income tax, last resort)
    4. Emergency Roth → Cash (if still short after Traditional)

    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        age_primary: Primary person's age
        year: Current year
        cash_target_override: If provided, use this value as the cash target
            instead of the expenses-based retirement target.  Used during the
            accumulation phase where the target is wages-based.

    Returns:
        Tuple of (updated_balances, transaction_log, decision_log)
        - updated_balances: PortfolioBalances after replenishment
        - transaction_log: Dict with all fund movements
        - decision_log: DecisionLog recording why each source was chosen
    """
    dl = DecisionLog()

    if cash_target_override is not None:
        cash_target = cash_target_override
    else:
        cash_target, _ = calculate_cash_buffer_targets(expenses)
    cash_deficit = max(0, cash_target - balances.cash)

    if cash_deficit < 100:  # Ignore trivial amounts
        dl.add("cash_replenishment", "Cash Buffer Check", "No action needed",
               "Cash balance meets or exceeds target — no replenishment required.",
               cash_balance=f"${balances.cash:,.0f}",
               cash_target=f"${cash_target:,.0f}")
        return balances, {
            'brokerage_to_cash': 0.0,
            'traditional_to_cash': 0.0,
            'roth_to_cash': 0.0,
            'cash_replenishment': 0.0
        }, dl

    logger.warning(f"Year {year}: Cash buffer below target (${balances.cash:,.0f} < ${cash_target:,.0f})")
    logger.warning(f"  Cash deficit: ${cash_deficit:,.0f}")
    logger.warning(f"  Current account balances:")
    logger.warning(f"    Cash: ${balances.cash:,.2f}")
    logger.warning(f"    Taxable (Brokerage): ${balances.taxable:,.2f}")
    logger.warning(f"    Traditional: ${balances.traditional:,.2f}")
    logger.warning(f"    Roth: ${balances.roth:,.2f}")
    logger.warning(f"    DAF: ${balances.daf:,.2f}")

    dl.add("cash_replenishment", "Cash Buffer Deficit",
           f"Replenish ${cash_deficit:,.0f}",
           "Cash balance fell below the configured target; sourcing funds in tax-efficient priority order "
           "(Brokerage first, then Roth if age-qualified, then Traditional as last resort).",
           cash_balance=f"${balances.cash:,.0f}",
           cash_target=f"${cash_target:,.0f}",
           deficit=f"${cash_deficit:,.0f}")

    transactions = {
        'brokerage_to_cash': 0.0,
        'traditional_to_cash': 0.0,
        'roth_to_cash': 0.0,
        'cash_replenishment': 0.0
    }

    # Step 1: Transfer from Brokerage (tax-free return of basis / LTCG)
    if cash_deficit > 0 and balances.taxable > 0:
        transfer = min(cash_deficit, balances.taxable)
        balances = PortfolioBalances(
            cash=balances.cash + transfer,
            taxable=balances.taxable - transfer,
            traditional=balances.traditional,
            roth=balances.roth,
            daf=balances.daf
        )
        transactions['brokerage_to_cash'] = transfer
        cash_deficit -= transfer
        logger.info(f"  Transferred ${transfer:,.0f} from Brokerage to Cash (tax-free)")
        dl.add("cash_replenishment", "Brokerage → Cash",
               f"Transfer ${transfer:,.0f}",
               "Brokerage is the first source: 60% is tax-free return of cost basis and "
               "40% is long-term capital gains — preferred over Traditional (ordinary income).",
               transferred=f"${transfer:,.0f}",
               remaining_deficit=f"${cash_deficit:,.0f}")

    # Step 2: Roth distribution (tax-free if qualified, preferred over Traditional to avoid future LTCG)
    if cash_deficit > 0 and balances.roth > 0 and age_primary >= 59.5:
        distribution = min(cash_deficit, balances.roth * 0.10)  # Max 10% per year
        balances = PortfolioBalances(
            cash=balances.cash + distribution,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth - distribution,
            daf=balances.daf
        )
        transactions['roth_to_cash'] = distribution
        cash_deficit -= distribution
        logger.info(f"  Distributed ${distribution:,.0f} from Roth to Cash (tax-free, avoids LTCG)")
        dl.add("cash_replenishment", "Roth → Cash",
               f"Distribute ${distribution:,.0f}",
               "Roth is used before Traditional: qualified distributions are 100% tax-free and "
               "avoid the LTCG that would arise from routing through Brokerage. "
               "Capped at 10% of Roth balance to preserve long-term tax-free growth.",
               distributed=f"${distribution:,.0f}",
               roth_balance=f"${balances.roth:,.0f}",
               age=age_primary,
               remaining_deficit=f"${cash_deficit:,.0f}")
    elif cash_deficit > 0 and balances.roth > 0 and age_primary < 59.5:
        dl.add("cash_replenishment", "Roth → Cash Skipped",
               "No distribution (age < 59½)",
               "Roth distributions before age 59½ may incur a 10% early-withdrawal penalty; "
               "Traditional is used instead to avoid the penalty.",
               age=age_primary)

    # Step 3: Distribute from Traditional (ordinary income tax, last resort for cash)
    # Blocked before age 59½ — early withdrawal triggers a 10% IRS penalty (IRC §72(t))
    if cash_deficit > 0 and balances.traditional > 0:
        if age_primary < EARLY_WITHDRAWAL_PENALTY_AGE:
            dl.add("cash_replenishment", "Traditional → Cash Blocked",
                   "No distribution (age < 59½)",
                   "Withdrawals from Traditional IRA/401k before age 59½ incur a 10% IRS early-withdrawal "
                   "penalty (IRC §72(t)). This transfer is blocked to avoid the penalty. "
                   "Build cash reserves from wages or after-tax savings instead.",
                   age=age_primary)
        else:
            distribution = min(cash_deficit, balances.traditional * 0.10)  # Max 10% per year
            balances = PortfolioBalances(
                cash=balances.cash + distribution,
                taxable=balances.taxable,
                traditional=balances.traditional - distribution,
                roth=balances.roth,
                daf=balances.daf
            )
            transactions['traditional_to_cash'] = distribution
            logger.info(f"  Distributed ${distribution:,.0f} from Traditional to Cash (ordinary income tax)")
            dl.add("cash_replenishment", "Traditional → Cash",
                   f"Distribute ${distribution:,.0f}",
                   "Traditional is the last resort for cash: every dollar withdrawn is taxed as ordinary income. "
                   "Capped at 10% of Traditional balance to limit tax impact in a single year.",
                   distributed=f"${distribution:,.0f}",
                   traditional_balance=f"${balances.traditional:,.0f}",
                   remaining_deficit=f"${cash_deficit:,.0f}")

    # Step 4: Emergency Roth if still needed (after Traditional exhausted)
    if cash_deficit > 0 and balances.roth > 0:
        distribution = min(cash_deficit, balances.roth * 0.05)  # Max 5% additional
        balances = PortfolioBalances(
            cash=balances.cash + distribution,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth - distribution,
            daf=balances.daf
        )
        transactions['roth_to_cash'] += distribution
        logger.warning(f"  EMERGENCY - Additional ${distribution:,.0f} from Roth to Cash (total: ${transactions['roth_to_cash']:,.0f})")
        dl.add("cash_replenishment", "Emergency Roth → Cash",
               f"Emergency distribute ${distribution:,.0f}",
               "EMERGENCY: Traditional balance was insufficient to cover the remaining deficit. "
               "An additional Roth distribution (capped at 5% of Roth balance) was taken as a last resort.",
               distributed=f"${distribution:,.0f}",
               total_roth_to_cash=f"${transactions['roth_to_cash']:,.0f}",
               remaining_deficit=f"${cash_deficit:,.0f}")

    transactions['cash_replenishment'] = sum([
        transactions['brokerage_to_cash'],
        transactions['traditional_to_cash'],
        transactions['roth_to_cash']
    ])

    logger.info(f"  Total cash replenishment: ${transactions['cash_replenishment']:,.0f}")
    logger.info(f"  New cash balance: ${balances.cash:,.0f}")

    return balances, transactions, dl


def replenish_brokerage_buffer(balances: PortfolioBalances,
                               expenses: float,
                               age_primary: int,
                               year: int) -> Tuple[PortfolioBalances, BrokerageTransactionLog, DecisionLog]:
    """
    Replenish brokerage buffer to target based on configured years of expenses.

    Implements tax-efficient brokerage buffer maintenance by distributing
    funds from retirement accounts:
    1. Traditional → Brokerage (ordinary income tax)

    Note: Roth → Brokerage transfers have been removed to avoid triggering
    unnecessary LTCG when those funds are later moved to Cash.

    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        age_primary: Primary person's age
        year: Current year

    Returns:
        Tuple of (updated_balances, transaction_log, decision_log)
        - updated_balances: PortfolioBalances after replenishment
        - transaction_log: BrokerageTransactionLog with all fund movements
        - decision_log: DecisionLog recording why each source was chosen
    """
    dl = DecisionLog()
    _, brokerage_target = calculate_cash_buffer_targets(expenses)
    brokerage_deficit = max(0, brokerage_target - balances.taxable)

    if brokerage_deficit < _BUFFER_REPLENISHMENT_MIN_DEFICIT:
        dl.add("brokerage_replenishment", "Brokerage Buffer Check", "No action needed",
               "Brokerage balance meets or exceeds target — no replenishment required.",
               brokerage_balance=f"${balances.taxable:,.0f}",
               brokerage_target=f"${brokerage_target:,.0f}")
        return balances, BrokerageTransactionLog(
            traditional_to_brokerage=0.0,
            brokerage_replenishment=0.0,
        ), dl

    logger.info(f"Year {year}: Brokerage buffer below target (${balances.taxable:,.0f} < ${brokerage_target:,.0f})")
    logger.info(f"  Brokerage deficit: ${brokerage_deficit:,.0f}")

    dl.add("brokerage_replenishment", "Brokerage Buffer Deficit",
           f"Replenish ${brokerage_deficit:,.0f}",
           "Brokerage balance fell below the configured target. "
           "Sourcing from Traditional (ordinary income) — Roth→Brokerage is intentionally avoided "
           "because it would trigger LTCG when those funds are later moved to Cash.",
           brokerage_balance=f"${balances.taxable:,.0f}",
           brokerage_target=f"${brokerage_target:,.0f}",
           deficit=f"${brokerage_deficit:,.0f}")

    transactions: BrokerageTransactionLog = BrokerageTransactionLog(
        traditional_to_brokerage=0.0,
        brokerage_replenishment=0.0,
    )

    # Step 1: Distribute from Traditional (taxable)
    # Blocked before age 59½ — early withdrawal triggers a 10% IRS penalty (IRC §72(t))
    if brokerage_deficit > 0 and balances.traditional > 0:
        if age_primary < EARLY_WITHDRAWAL_PENALTY_AGE:
            dl.add("brokerage_replenishment", "Traditional → Brokerage Blocked",
                   "No distribution (age < 59½)",
                   "Withdrawals from Traditional IRA/401k before age 59½ incur a 10% IRS early-withdrawal "
                   "penalty (IRC §72(t)). This transfer is blocked to avoid the penalty. "
                   "Use after-tax wages or Roth contributions to build the brokerage balance instead.",
                   age=age_primary)
        else:
            distribution = min(brokerage_deficit, balances.traditional * _MAX_TRADITIONAL_TO_BROKERAGE_RATE)
            balances = replace(
                balances,
                taxable=balances.taxable + distribution,
                traditional=balances.traditional - distribution,
            )
            transactions['traditional_to_brokerage'] = distribution
            brokerage_deficit -= distribution
            logger.info(f"  Distributed ${distribution:,.0f} from Traditional to Brokerage (ordinary income tax)")
            dl.add("brokerage_replenishment", "Traditional → Brokerage",
                   f"Distribute ${distribution:,.0f}",
                   "Traditional is the sole source for brokerage replenishment. "
                   "Capped at 15% of Traditional balance to limit the ordinary-income tax hit in a single year.",
                   distributed=f"${distribution:,.0f}",
                   traditional_balance=f"${balances.traditional:,.0f}",
                   remaining_deficit=f"${brokerage_deficit:,.0f}")

    # Roth → Brokerage intentionally omitted — see docstring
    if brokerage_deficit > _BUFFER_REPLENISHMENT_MIN_DEFICIT:
        dl.add("brokerage_replenishment", "Roth → Brokerage Skipped",
               "No Roth transfer to Brokerage",
               "Roth→Brokerage transfers are intentionally skipped: moving Roth funds to Brokerage "
               "would create a taxable LTCG event when those funds are later moved to Cash. "
               "Any remaining deficit will be covered by direct Roth→Cash transfers instead.",
               remaining_deficit=f"${brokerage_deficit:,.0f}")

    transactions['brokerage_replenishment'] = transactions['traditional_to_brokerage']

    logger.info(f"  Total brokerage replenishment: ${transactions['brokerage_replenishment']:,.0f}")
    logger.info(f"  New brokerage balance: ${balances.taxable:,.0f}")

    return balances, transactions, dl


def execute_roth_conversion(balances: PortfolioBalances,
                           conversion_amount: float,
                           year: int) -> PortfolioBalances:
    """
    Execute Roth conversion by moving funds from Traditional to Roth
    
    This function implements the actual fund transfer for Roth conversions
    calculated by the BETR algorithm. It ensures funds are properly moved
    between accounts.
    
    Args:
        balances: Current portfolio balances
        conversion_amount: Amount to convert (from BETR algorithm)
        year: Current year
    
    Returns:
        Updated balances with conversion executed
    """
    if conversion_amount <= 0:
        return balances
    
    # Verify sufficient Traditional balance
    if balances.traditional < conversion_amount:
        logger.warning(f"Year {year}: Insufficient Traditional balance for conversion "
                     f"(requested: ${conversion_amount:,.0f}, available: ${balances.traditional:,.0f})")
        conversion_amount = balances.traditional
    
    # Execute conversion
    updated_balances = PortfolioBalances(
        cash=balances.cash,
        taxable=balances.taxable,
        traditional=balances.traditional - conversion_amount,
        roth=balances.roth + conversion_amount,
        daf=balances.daf
    )
    
    logger.info(f"Year {year}: Converted ${conversion_amount:,.0f} from Traditional to Roth")
    logger.debug(f"  Traditional: ${updated_balances.traditional:,.0f}, Roth: ${updated_balances.roth:,.0f}")
    
    return updated_balances


def rebalance_accounts(balances: PortfolioBalances,
                      expenses: float,
                      roth_conversion: float,
                      year: int,
                      age_primary: int,
                      stage: str,
                      federal_tax: float = 0.0,
                      irmaa_penalty: float = 0.0,
                      aca_premium: float = 0.0,
                      medical_costs: float = 0.0,
                      cash_target_override: Optional[float] = None) -> Tuple[PortfolioBalances, Dict[str, float], DecisionLog]:
    """
    Execute all account rebalancing operations for a given year
    
    This function orchestrates:
    1. Deduct expenses, taxes, IRMAA, ACA, and medical costs from cash
    2. Cash buffer maintenance (2-year target)
    3. Brokerage buffer maintenance (3-year target)
    4. Roth conversion execution
    5. Fund movement tracking
    
    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        roth_conversion: Roth conversion amount (from BETR algorithm)
        year: Current year
        age_primary: Primary person's age
        stage: Current life stage
        federal_tax: Federal tax amount to deduct from cash
        irmaa_penalty: IRMAA penalty to deduct from cash
        aca_premium: ACA premium to deduct from cash
        medical_costs: Medical costs to deduct from cash
        cash_target_override: If provided, pass to replenish_cash_buffer as the
            cash target (used during accumulation for wages-based buffer).
    
    Returns:
        Tuple of (updated_balances, transaction_log, decision_log)
        - updated_balances: PortfolioBalances after all movements
        - transaction_log: Dict with all fund movements for reporting
        - decision_log: DecisionLog with reasons for every buffer/conversion action
    """
    dl = DecisionLog()

    logger.info(f"Year {year} ({stage}): Starting account rebalancing")
    logger.info(f"  Initial balances: Cash=${balances.cash:,.0f}, "
                f"Taxable=${balances.taxable:,.0f}, "
                f"Traditional=${balances.traditional:,.0f}, "
                f"Roth=${balances.roth:,.0f}")

    # Initialize transaction log
    transactions = {
        'brokerage_to_cash': 0.0,
        'traditional_to_cash': 0.0,
        'traditional_to_brokerage': 0.0,
        'roth_to_cash': 0.0,
        'roth_to_brokerage': 0.0,
        'conversion_executed': 0.0,
        'cash_replenishment': 0.0,
        'brokerage_replenishment': 0.0
    }

    # Step 1: Deduct expenses, taxes, IRMAA, ACA, and medical costs from cash account FIRST
    total_cash_outflow = expenses + federal_tax + irmaa_penalty + aca_premium + medical_costs

    logger.info(f"Year {year}: Deducting costs from cash")
    logger.info(f"  Cash before deductions: ${balances.cash:,.2f}")
    logger.info(f"  Expenses: ${expenses:,.2f}")
    logger.info(f"  Federal Tax: ${federal_tax:,.2f}")
    logger.info(f"  IRMAA Penalty: ${irmaa_penalty:,.2f}")
    logger.info(f"  ACA Premium: ${aca_premium:,.2f}")
    logger.info(f"  Medical Costs: ${medical_costs:,.2f}")
    logger.info(f"  Total cash outflow: ${total_cash_outflow:,.2f}")

    balances = PortfolioBalances(
        cash=balances.cash - total_cash_outflow,
        taxable=balances.taxable,
        traditional=balances.traditional,
        roth=balances.roth,
        daf=balances.daf
    )
    transactions['expenses_paid'] = expenses
    transactions['taxes_paid'] = federal_tax
    transactions['irmaa_paid'] = irmaa_penalty
    transactions['aca_paid'] = aca_premium
    transactions['medical_paid'] = medical_costs

    logger.info(f"  Cash after deductions: ${balances.cash:,.2f}")

    # Step 2: Replenish cash buffer (after expenses paid)
    balances, cash_txns, cash_dl = replenish_cash_buffer(
        balances, expenses, age_primary, year,
        cash_target_override=cash_target_override
    )
    transactions['brokerage_to_cash'] = cash_txns['brokerage_to_cash']
    transactions['traditional_to_cash'] = cash_txns['traditional_to_cash']
    transactions['roth_to_cash'] = cash_txns['roth_to_cash']
    transactions['cash_replenishment'] = cash_txns['cash_replenishment']
    dl.cash_replenishment.extend(cash_dl.cash_replenishment)

    # Step 3: Replenish brokerage buffer
    balances, brokerage_txns, brok_dl = replenish_brokerage_buffer(balances, expenses, age_primary, year)
    transactions['traditional_to_brokerage'] = brokerage_txns['traditional_to_brokerage']
    transactions['brokerage_replenishment'] = brokerage_txns['brokerage_replenishment']
    dl.brokerage_replenishment.extend(brok_dl.brokerage_replenishment)

    # Step 4: Execute Roth conversion (after buffers are replenished)
    if roth_conversion > 0:
        balances = execute_roth_conversion(balances, roth_conversion, year)
        transactions['conversion_executed'] = roth_conversion

    # Step 5: Log all fund movements
    logger.info(f"Year {year}: Transaction Summary")
    logger.info(f"  Expenses paid: ${transactions.get('expenses_paid', 0):,.2f}")
    logger.info(f"  Fund Movements:")
    logger.info(f"    Brokerage → Cash: ${transactions['brokerage_to_cash']:,.2f}")
    logger.info(f"    Traditional → Cash: ${transactions['traditional_to_cash']:,.2f}")
    logger.info(f"    Roth → Cash: ${transactions['roth_to_cash']:,.2f}")
    logger.info(f"    Traditional → Brokerage: ${transactions['traditional_to_brokerage']:,.2f}")
    logger.info(f"    Roth Conversion (Trad→Roth): ${transactions.get('conversion_executed', 0):,.2f}")
    logger.info(f"  Buffer Replenishments:")
    logger.info(f"    Cash replenishment: ${transactions['cash_replenishment']:,.2f}")
    logger.info(f"    Brokerage replenishment: ${transactions['brokerage_replenishment']:,.2f}")

    total_movements = sum([
        transactions['brokerage_to_cash'],
        transactions['traditional_to_cash'],
        transactions['traditional_to_brokerage'],
        transactions['roth_to_cash'],
        transactions['roth_to_brokerage']
    ])

    logger.info(f"  Total fund movements: ${total_movements:,.2f}")
    logger.info(f"  Final balances: Cash=${balances.cash:,.2f}, "
                f"Taxable=${balances.taxable:,.2f}, "
                f"Traditional=${balances.traditional:,.2f}, "
                f"Roth=${balances.roth:,.2f}")

    return balances, transactions, dl


class LifeStage:
    """Base class for life stage strategies"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        logger.debug(f"Initialized {name} stage")
    
    def applies(self, age_primary: int, age_spouse: int, year: int, 
                has_wages: bool, has_ss: bool) -> bool:
        """Determine if this stage applies to the current situation"""
        raise NotImplementedError
    
    def calculate_strategy(self, year: int, balances: PortfolioBalances,
                          expenses: float, **kwargs) -> YearlyStrategy:
        """Calculate withdrawal strategy for this stage"""
        raise NotImplementedError


def _get_retirement_years() -> tuple:
    """Return (earliest, latest) calendar year either person is expected to retire."""
    cfg = get_config_manager()
    p1 = int(cfg.get("personal_info", "person1_birth_date", "1965-01-01").split('-')[0]) + int(cfg.get("personal_info", "person1_retirement_age", 67))
    p2 = int(cfg.get("personal_info", "person2_birth_date", "1967-01-01").split('-')[0]) + int(cfg.get("personal_info", "person2_retirement_age", 62))
    return min(p1, p2), max(p1, p2)


def _get_earliest_retirement_year() -> int:
    """Return the earliest calendar year either person is expected to retire."""
    return _get_retirement_years()[0]


def _get_latest_retirement_year() -> int:
    """Return the latest calendar year either person is expected to retire.

    Stage 1 (Accumulation) and Stage 2 (Prep for Retirement) should remain
    active until the *last* earner retires.  Using the earliest retirement year
    caused a regression where the stages reverted to Stage 1 after the first
    person retired while the second was still working.
    """
    return _get_retirement_years()[1]


def _calculate_daf_for_year(age_primary: int, std_deduction: float) -> Tuple[float, float]:
    """Calculate DAF contribution and tax deduction excess for a given year/age.

    Uses the same bundling formula as the Configuration page:
      bundle_interval = floor(std_ded / annual_giving) + 1  (capped at 5, min 2)
      bundle_amount   = annual_giving * bundle_interval
      bundle_years    = years where (age_primary - daf_start_age) % bundle_interval == 0

    Returns:
        (daf_contribution, daf_tax_deduction_excess)
        daf_contribution          — amount contributed to DAF this year (0 in non-bundle years)
        daf_tax_deduction_excess  — amount by which the DAF contribution exceeds the standard
                                    deduction (i.e. the incremental itemized deduction benefit).
                                    This is subtracted from taxable income in bundle years.
    """
    try:
        config_mgr = get_config_manager()
        has_daf = config_mgr.get("charitable_giving", "has_daf", False)
        annual_giving = float(config_mgr.get("charitable_giving", "annual_charitable_giving", 0))
        daf_start_age = int(config_mgr.get("charitable_giving", "daf_contribution_start_age", 60))
        daf_end_age = int(config_mgr.get("charitable_giving", "daf_contribution_end_age", 75))
        daf_initial = float(config_mgr.get("charitable_giving", "daf_initial_contribution", 0))
    except Exception:
        return 0.0, 0.0

    # No DAF or no giving configured — guard before any division
    if not has_daf or annual_giving <= 0:
        return 0.0, 0.0

    # Compute bundle interval: floor(std_ded / giving) + 1, capped [2, 5]
    bundle_interval = max(2, min(int(std_deduction // annual_giving) + 1, 5))
    years_into_window = age_primary - daf_start_age

    # Outside the DAF contribution age window, or not a bundle year — single guard
    if not (daf_start_age <= age_primary <= daf_end_age
            and years_into_window % bundle_interval == 0):
        return 0.0, 0.0

    bundle_amount = annual_giving * bundle_interval

    # First year of the window: add initial contribution
    daf_contribution = bundle_amount
    if years_into_window == 0 and daf_initial > 0:
        daf_contribution += daf_initial

    # Tax deduction excess: amount above the standard deduction (itemized benefit)
    daf_tax_excess = max(0.0, daf_contribution - std_deduction)

    logger.debug(
        f"DAF bundle year (age {age_primary}): "
        f"contribution=${daf_contribution:,.0f}, "
        f"tax excess above std_ded=${daf_tax_excess:,.0f} "
        f"(interval={bundle_interval} yrs, bundle=${bundle_amount:,.0f})"
    )
    return daf_contribution, daf_tax_excess


class Stage1Accumulation(LifeStage):
    """
    Stage 1: Accumulation Phase
    - Employed with wages
    - Focus on tax-efficient contributions
    - Maximize 401k/IRA contributions
    - Consider Roth vs Traditional based on current tax bracket
    """
    
    def __init__(self):
        super().__init__(
            "Stage 1: Accumulation",
            "Employed, earning wages, building retirement assets tax-efficiently"
        )
    
    def applies(self, age_primary: int, age_spouse: int, year: int,
                has_wages: bool, has_ss: bool) -> bool:
        """Applies when employed with wages AND outside the Stage 2 prep window.

        Uses the *latest* retirement year so that Stage 1 remains active (and
        correctly yields to Stage 2) until the last earner in the household
        retires.  Using the earliest retirement year caused a false reversion
        back to Stage 1 after the first person retired while the second was
        still working.
        """
        if not has_wages:
            return False
        # Yield to Stage 2 when within the 10-year prep window of the LAST
        # person to retire (household is not in prep mode until the final
        # earner is within the window).
        try:
            latest_retirement_year = _get_latest_retirement_year()
            years_to_retirement = latest_retirement_year - year
            # If within the prep window, Stage 2 should handle this year
            if 0 < years_to_retirement <= Stage2PrepForRetirement.PREP_WINDOW_YEARS:
                return False
        except Exception as e:
            logger.warning(f"Stage1.applies: config lookup failed ({e}), defaulting to Stage 1")
        return True
    
    def calculate_strategy(self, year: int, balances: PortfolioBalances,
                          expenses: float, wages: float = 0,
                          contribution_401k: float = 0,
                          contribution_roth: float = 0,
                          **kwargs) -> YearlyStrategy:
        """
        Calculate accumulation strategy focusing on tax efficiency
        
        During accumulation, consider Roth conversions using BETR algorithm
        to reduce future RMDs in Stage 5, especially if in lower tax brackets.
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            wages: Annual wages/salary
            contribution_401k: Traditional 401k contribution
            contribution_roth: Roth contribution (401k or IRA)
        """
        logger.debug(f"Stage 1 calculation for year {year}, wages=${wages:,.2f}")
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        
        # Get tax brackets for the year
        tax_brackets = get_income_tax_brackets(year)
        std_deduction_df = get_std_deduction(year)
        std_deduction = std_deduction_df.iloc[0]['deduction']
        
        # -----------------------------------------------------------------------
        # Compute contribution amounts from config rates (% of gross wages)
        # -----------------------------------------------------------------------
        try:
            config_mgr = get_config_manager()
            trad_pct  = float(config_mgr.get("income", "contribution_401k_percent",  10.0)) / 100.0
            roth_pct  = float(config_mgr.get("income", "contribution_roth_percent",   5.0)) / 100.0
            brok_pct  = float(config_mgr.get("income", "contribution_brokerage_percent", 5.0)) / 100.0
        except Exception:
            trad_pct, roth_pct, brok_pct = 0.10, 0.05, 0.05

        # Clamp each rate to [0, 1] and ensure total ≤ 100 %
        trad_pct = max(0.0, min(1.0, trad_pct))
        roth_pct = max(0.0, min(1.0, roth_pct))
        brok_pct = max(0.0, min(1.0, brok_pct))
        total_pct = trad_pct + roth_pct + brok_pct
        if total_pct > 1.0:
            scale = 1.0 / total_pct
            trad_pct *= scale; roth_pct *= scale; brok_pct *= scale

        # Dollar amounts withheld from gross wages before take-home
        contribution_401k  = wages * trad_pct   # pre-tax → reduces AGI
        contribution_roth  = wages * roth_pct   # after-tax Roth (no AGI reduction)
        contribution_brok  = wages * brok_pct   # after-tax brokerage

        # -----------------------------------------------------------------------
        # Calculate AGI: gross wages minus pre-tax 401k contribution
        # -----------------------------------------------------------------------
        agi = wages - contribution_401k

        # -----------------------------------------------------------------------
        # DAF contribution and tax deduction for this year
        # -----------------------------------------------------------------------
        daf_contribution, daf_tax_excess = _calculate_daf_for_year(age_primary, std_deduction)

        # In a DAF bundle year, the contribution exceeds the standard deduction,
        # so we itemize instead of taking the standard deduction.  The incremental
        # tax benefit is the amount above the standard deduction.
        # taxable_income = agi - max(std_deduction, daf_contribution)
        effective_deduction = std_deduction + daf_tax_excess  # = daf_contribution when bundling
        taxable_income = agi - effective_deduction
        federal_tax, max_rate, upper_max = calculate_taxable_income(taxable_income, tax_brackets)

        logger.debug(f"AGI: ${agi:,.2f}, DAF contrib: ${daf_contribution:,.0f}, "
                     f"effective deduction: ${effective_deduction:,.0f}, "
                     f"Tax bracket: {max_rate:.1%}, Tax: ${federal_tax:,.2f}")
        logger.debug(
            f"Stage 1 contributions — Traditional 401k: ${contribution_401k:,.0f} "
            f"({trad_pct:.0%}), Roth: ${contribution_roth:,.0f} ({roth_pct:.0%}), "
            f"Brokerage: ${contribution_brok:,.0f} ({brok_pct:.0%})"
        )

        # -----------------------------------------------------------------------
        # Consider Roth conversions during accumulation using BETR
        # Only convert if in favorable tax bracket (≤ max_conversion_rate)
        # -----------------------------------------------------------------------
        dl = DecisionLog()

        # Record tax strategy decision
        dl.add("tax_strategy", "Contribution Type",
               f"Traditional 401k {trad_pct:.0%} / Roth {roth_pct:.0%} / Brokerage {brok_pct:.0%}",
               "During accumulation, contributions are split per config rates. "
               "Pre-tax 401k reduces AGI now; Roth contributions grow tax-free.",
               trad_401k=f"${contribution_401k:,.0f}",
               roth=f"${contribution_roth:,.0f}",
               brokerage=f"${contribution_brok:,.0f}",
               agi=f"${agi:,.0f}",
               bracket=f"{max_rate:.1%}")

        roth_conversion = 0
        if balances.traditional > 0 and max_rate <= max_conversion_rate:
            try:
                # Use BETR to determine optimal conversion amount
                # During accumulation, we want to reduce future RMDs
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, pd.DataFrame(tax_brackets)
                )

                # Calculate conversion room in current bracket
                current_income = agi
                conversion_room = max(0, target_bracket_upper - current_income - std_deduction)

                if conversion_room > 10000:  # Only convert if meaningful room
                    proposed_conversion = min(conversion_room, balances.traditional * 0.15)
                    if proposed_conversion > 1000:  # Meaningful minimum
                        # Use BETR to validate conversion is beneficial
                        betr_inputs = BETRInputs(
                            current_marginal_rate=max_rate,
                            expected_future_rate=max_conversion_rate,  # Assume higher rate in retirement
                            conversion_amount=proposed_conversion,
                            traditional_ira_balance=balances.traditional,
                            pay_from_taxable=True,
                            taxable_account_balance=balances.taxable,
                            years_to_withdrawal=max(1, 73 - age_primary),
                            annual_return=0.07
                        )

                        betr_results = calculate_betr(betr_inputs)

                        if betr_results.conversion_recommended:
                            roth_conversion = proposed_conversion
                            logger.info(f"Stage 1 Roth conversion: ${roth_conversion:,.0f} "
                                      f"(BETR: {betr_results.betr:.2%}, "
                                      f"Current rate: {max_rate:.1%})")
                            dl.add("roth_conversion", "BETR Conversion (Stage 1)",
                                   f"Convert ${roth_conversion:,.0f}",
                                   "BETR analysis recommends converting during accumulation: current marginal rate "
                                   "is at or below the expected retirement rate, so paying tax now is cheaper "
                                   "than paying it on RMDs later.",
                                   betr=f"{betr_results.betr:.2%}",
                                   current_rate=f"{max_rate:.1%}",
                                   expected_future_rate=f"{max_conversion_rate:.1%}",
                                   conversion_room=f"${conversion_room:,.0f}",
                                   proposed=f"${proposed_conversion:,.0f}")
                        else:
                            logger.debug(f"BETR {betr_results.betr:.2%} - conversion not recommended")
                            dl.add("roth_conversion", "BETR Conversion (Stage 1)",
                                   "No conversion",
                                   "BETR analysis does not recommend converting: the break-even tax rate "
                                   "is below the current marginal rate, meaning it is cheaper to defer.",
                                   betr=f"{betr_results.betr:.2%}",
                                   current_rate=f"{max_rate:.1%}",
                                   proposed=f"${proposed_conversion:,.0f}")
                else:
                    dl.add("roth_conversion", "BETR Conversion (Stage 1)",
                           "No conversion — insufficient bracket room",
                           f"Conversion room (${conversion_room:,.0f}) is below the $10,000 minimum threshold; "
                           "no conversion executed to avoid disproportionate tax cost.",
                           conversion_room=f"${conversion_room:,.0f}")

            except (ValueError, Exception) as e:
                logger.debug(f"Could not calculate BETR conversion: {e}")
                dl.add("roth_conversion", "BETR Conversion (Stage 1)",
                       "No conversion — calculation error",
                       f"BETR calculation failed ({e}); conversion skipped to avoid incorrect tax decisions.")
        else:
            if balances.traditional <= 0:
                dl.add("roth_conversion", "BETR Conversion (Stage 1)",
                       "No conversion — no Traditional balance",
                       "Traditional account balance is zero; nothing to convert.")
            else:
                dl.add("roth_conversion", "BETR Conversion (Stage 1)",
                       "No conversion — bracket too high",
                       f"Current marginal rate ({max_rate:.1%}) exceeds the max conversion rate "
                       f"({max_conversion_rate:.1%}); converting now would cost more than deferring.",
                       current_rate=f"{max_rate:.1%}",
                       max_conversion_rate=f"{max_conversion_rate:.1%}")

        # Calculate tax on conversion if any
        if roth_conversion > 0:
            total_income = agi + roth_conversion
            taxable_income_with_conversion = total_income - effective_deduction
            federal_tax, _, _ = calculate_taxable_income(taxable_income_with_conversion, tax_brackets)

        # -----------------------------------------------------------------------
        # Compute payroll taxes (FICA, Medicare, State, FUTA/SUTA) on gross wages
        # These are deducted before any savings or investment decisions.
        # -----------------------------------------------------------------------
        payroll_tax, _payroll_breakdown = calculate_payroll_taxes(wages, year) if wages > 0 else (0.0, {})

        # -----------------------------------------------------------------------
        # Compute take-home cash after all taxes and after-tax contributions
        # Take-home = gross wages - federal tax - payroll tax - Roth contribution - brokerage contribution
        # (Traditional 401k is pre-tax so it already reduced AGI; it does NOT come out of
        #  take-home again — it was never in the paycheck to begin with.)
        # -----------------------------------------------------------------------
        after_tax_wages = wages - federal_tax - payroll_tax - contribution_roth - contribution_brok

        # -----------------------------------------------------------------------
        # Update balances: route each dollar to the right account
        # -----------------------------------------------------------------------
        # Cash target for this year (wages-based buffer)
        accum_cash_target = calculate_cash_buffer_targets_accumulation(wages)

        # How much cash do we need to add to reach the target?
        cash_shortfall = max(0.0, accum_cash_target - (balances.cash + after_tax_wages))

        # If after-tax wages exceed what's needed to top up cash, route the surplus
        # to brokerage (on top of the explicit brokerage contribution).
        cash_to_add = min(after_tax_wages, accum_cash_target - balances.cash)
        cash_to_add = max(0.0, cash_to_add)  # never negative
        surplus_to_brokerage = max(0.0, after_tax_wages - cash_to_add)

        balances_with_contributions = PortfolioBalances(
            cash=balances.cash + cash_to_add,
            taxable=balances.taxable + contribution_brok + surplus_to_brokerage,
            traditional=balances.traditional + contribution_401k,
            roth=balances.roth + contribution_roth,
            daf=balances.daf + daf_contribution
        )

        logger.info(
            f"Year {year}: wages=${wages:,.0f}, tax=${federal_tax:,.0f}, "
            f"trad401k=${contribution_401k:,.0f}, roth=${contribution_roth:,.0f}, "
            f"brok_contrib=${contribution_brok:,.0f}, "
            f"cash_added=${cash_to_add:,.0f}, surplus_to_brok=${surplus_to_brokerage:,.0f}"
        )
        
        # Calculate ACA premium based on configuration
        aca_premium = calculate_aca_premium_for_year(year, age_primary, age_spouse)
        
        # Execute account rebalancing (includes Roth conversion and expense payment)
        new_balances, transactions, rebal_dl = rebalance_accounts(
            balances=balances_with_contributions,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name,
            federal_tax=federal_tax,
            irmaa_penalty=0.0,
            aca_premium=aca_premium,
            medical_costs=0.0,
            cash_target_override=accum_cash_target,
        )
        
        # Calculate MAGI for this year
        # agi = wages - contribution_401k (pre-tax); include it so IRMAA lookback history
        # is correct for workers who reach Medicare within 2 years of their last working year.
        trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage']
        magi = (agi +              # Wages minus pre-tax 401k contributions
                trad_withdrawal +  # Traditional distributions from rebalance_accounts()
                roth_conversion)   # Roth conversion income
        
        # Record Cash→Roth and Cash→Brokerage contribution decisions
        dl.add("contribution_decisions", "Cash → Roth Contribution",
               f"Contribute ${contribution_roth:,.0f} from take-home pay",
               "After-tax wages are routed directly to the Roth account. "
               "This builds tax-free savings without triggering any early-withdrawal penalty "
               "because it is a contribution, not a distribution.",
               amount=f"${contribution_roth:,.0f}",
               roth_pct=f"{roth_pct:.0%}")
        dl.add("contribution_decisions", "Cash → Brokerage Contribution",
               f"Contribute ${contribution_brok + surplus_to_brokerage:,.0f} from take-home pay",
               "After-tax wages in excess of the cash buffer target are routed to the taxable "
               "brokerage account. This builds liquid, after-tax savings that can fund future "
               "Roth conversions in early retirement without penalty.",
               explicit_contrib=f"${contribution_brok:,.0f}",
               surplus=f"${surplus_to_brokerage:,.0f}",
               brok_pct=f"{brok_pct:.0%}")

        # Merge rebalancing decisions into stage decision log
        dl.cash_replenishment.extend(rebal_dl.cash_replenishment)
        dl.brokerage_replenishment.extend(rebal_dl.brokerage_replenishment)

        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=wages,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=0,
            taxable_withdrawal=0,
            roth_withdrawal=0,
            roth_conversion=roth_conversion,
            ltcg_harvested=0,
            daf_contribution=daf_contribution,
            expenses=expenses,
            agi=agi,
            magi=magi,
            federal_tax=federal_tax,
            irmaa_penalty=0,
            aca_premium=aca_premium,
            balances=new_balances,
            payroll_tax=payroll_tax,
            wages_to_trad=contribution_401k,
            wages_to_roth=contribution_roth,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed'],
            # Accumulation contributions from take-home cash
            cash_to_roth=contribution_roth,
            cash_to_brokerage=contribution_brok + surplus_to_brokerage,
            decision_log=dl,
        )


class Stage2PrepForRetirement(LifeStage):
    """
    Stage 2: Prep for Retirement (within 10 years of planned retirement)
    - Still employed with wages
    - Focus: balance Roth, Traditional, and Taxable account ratios
    - Evaluate Roth 401k vs Traditional 401k based on prior-year taxes
    - Backdoor Roth: contribute to Traditional IRA then convert (if income too high for direct Roth)
    - Mega backdoor Roth via employer 401k after-tax contributions
    - If Traditional accounts are too large, redirect new savings to taxable brokerage
      (funds future Roth conversions in early retirement)
    - Healthcare costs still covered by employer / payroll deductions
    """

    # Number of years before retirement that this stage activates
    PREP_WINDOW_YEARS: int = 10

    def __init__(self):
        super().__init__(
            "Stage 2: Prep for Retirement",
            "Within 10 years of retirement — balance Roth/Traditional/Taxable, optimize contribution type"
        )

    def applies(self, age_primary: int, age_spouse: int, year: int,
                has_wages: bool, has_ss: bool) -> bool:
        """Applies when employed AND within PREP_WINDOW_YEARS of the last retirement date.

        Anchored to the *latest* retirement year so that Stage 2 covers the
        full prep window up until the last earner retires, preventing a false
        reversion to Stage 1 after the first person retires.
        """
        if not has_wages:
            return False
        try:
            latest_retirement_year = _get_latest_retirement_year()
            years_to_retirement = latest_retirement_year - year
            return 0 < years_to_retirement <= self.PREP_WINDOW_YEARS
        except Exception:
            return False

    def calculate_strategy(self, year: int, balances: PortfolioBalances,
                           expenses: float, wages: float = 0,
                           contribution_401k: float | None = None,
                           contribution_roth: float | None = None,
                           **kwargs) -> YearlyStrategy:
        """
        Calculate pre-retirement optimisation strategy.

        Key decisions made each year:
        1. Assess whether Roth 401k or Traditional 401k is more tax-efficient
           (compare current marginal rate vs expected retirement rate).
        2. If Traditional balance is already large relative to Roth, redirect
           new 401k contributions to Roth 401k instead.
        3. If income is too high for a direct Roth IRA contribution, execute a
           backdoor Roth (contribute to empty Traditional IRA → immediate conversion).
        4. If Traditional balance is very large, consider investing new savings in
           taxable brokerage to fund future Roth conversions in early retirement.
        5. Use BETR to validate any Roth conversion is beneficial.
        """
        logger.debug(f"Stage 2 Prep calculation for year {year}, wages=${wages:,.2f}")

        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)

        # -----------------------------------------------------------------------
        # Compute contribution amounts from config rates (same pattern as Stage 1).
        # The caller does not pass these values, so derive them here.
        # -----------------------------------------------------------------------
        if wages > 0 and (contribution_401k is None or contribution_roth is None):
            try:
                config_mgr = get_config_manager()
                trad_pct = float(config_mgr.get("income", "contribution_401k_percent",  10.0)) / 100.0
                roth_pct = float(config_mgr.get("income", "contribution_roth_percent",   5.0)) / 100.0
            except Exception:
                trad_pct, roth_pct = 0.10, 0.05
            trad_pct = max(0.0, min(1.0, trad_pct))
            roth_pct = max(0.0, min(1.0, roth_pct))
            if contribution_401k is None:
                contribution_401k = wages * trad_pct
            if contribution_roth is None:
                contribution_roth = wages * roth_pct
        # Normalize any remaining None (e.g. wages==0 or only one was None) to 0.0
        if contribution_401k is None:
            contribution_401k = 0.0
        if contribution_roth is None:
            contribution_roth = 0.0

        # Get tax data
        tax_brackets = get_income_tax_brackets(year)
        std_deduction_df = get_std_deduction(year)
        std_deduction = std_deduction_df.iloc[0]['deduction']

        # -----------------------------------------------------------------------
        # Decision 1: Should new 401k contributions go Roth or Traditional?
        # Rule: if current marginal rate <= expected retirement rate → Traditional
        #       if current marginal rate >  expected retirement rate → Roth 401k
        # Use a preliminary Traditional-assumption AGI to determine the bracket,
        # then recompute AGI correctly once contribution type is known.
        # -----------------------------------------------------------------------
        expected_retirement_rate = max_conversion_rate  # proxy for retirement bracket
        _preliminary_agi = wages - contribution_401k
        _preliminary_taxable = _preliminary_agi - std_deduction
        _, _preliminary_rate, _ = calculate_taxable_income(_preliminary_taxable, tax_brackets)
        prefer_roth_401k = _preliminary_rate > expected_retirement_rate

        # -----------------------------------------------------------------------
        # Decision 2: Is Traditional balance disproportionately large?
        # Heuristic: if Traditional > 2× Roth, redirect contributions to Roth
        # -----------------------------------------------------------------------
        trad_heavy = (balances.roth > 0 and balances.traditional > 2 * balances.roth)
        if trad_heavy:
            prefer_roth_401k = True
            logger.info(f"Year {year}: Traditional (${balances.traditional:,.0f}) > 2× Roth "
                        f"(${balances.roth:,.0f}) — redirecting contributions to Roth 401k")

        # Roth 401k contributions are after-tax and do NOT reduce AGI.
        # Traditional 401k contributions are pre-tax and DO reduce AGI.
        agi = wages if prefer_roth_401k else wages - contribution_401k

        # -----------------------------------------------------------------------
        # DAF contribution and tax deduction for this year (Stage 2)
        # -----------------------------------------------------------------------
        daf_contribution, daf_tax_excess = _calculate_daf_for_year(age_primary, std_deduction)
        effective_deduction = std_deduction + daf_tax_excess

        taxable_income = agi - effective_deduction
        federal_tax, max_rate, upper_max = calculate_taxable_income(taxable_income, tax_brackets)

        logger.debug(f"Stage 2 Prep: AGI=${agi:,.2f}, DAF contrib=${daf_contribution:,.0f}, "
                     f"effective deduction=${effective_deduction:,.0f}, "
                     f"bracket={max_rate:.1%}, tax=${federal_tax:,.2f}")

        dl = DecisionLog()

        # Record contribution type decision
        if prefer_roth_401k:
            if trad_heavy:
                contrib_reason = (
                    f"Traditional balance (${balances.traditional:,.0f}) exceeds 2× Roth "
                    f"(${balances.roth:,.0f}). Redirecting 401k contributions to Roth to rebalance "
                    "the tax-deferred vs tax-free ratio and reduce future RMD exposure."
                )
            else:
                contrib_reason = (
                    f"Current marginal rate ({max_rate:.1%}) exceeds expected retirement rate "
                    f"({expected_retirement_rate:.1%}). Paying Roth tax now is cheaper than "
                    "paying ordinary income tax on Traditional withdrawals in retirement."
                )
            dl.add("contribution_decisions", "401k Contribution Type",
                   "Roth 401k",
                   contrib_reason,
                   current_rate=f"{max_rate:.1%}",
                   expected_retirement_rate=f"{expected_retirement_rate:.1%}",
                   trad_balance=f"${balances.traditional:,.0f}",
                   roth_balance=f"${balances.roth:,.0f}")
        else:
            dl.add("contribution_decisions", "401k Contribution Type",
                   "Traditional 401k",
                   f"Current marginal rate ({max_rate:.1%}) is at or below the expected retirement rate "
                   f"({expected_retirement_rate:.1%}). Deferring tax now is more efficient; "
                   "Traditional 401k reduces AGI and current-year tax bill.",
                   current_rate=f"{max_rate:.1%}",
                   expected_retirement_rate=f"{expected_retirement_rate:.1%}")

        # -----------------------------------------------------------------------
        # Decision 3: Backdoor Roth IRA
        # Execute if income exceeds direct Roth IRA contribution limit (~$161k single / $240k MFJ 2024)
        # Assumes Traditional IRA is kept empty for this purpose.
        # -----------------------------------------------------------------------
        # ROTH_IRA_INCOME_LIMIT and IRA_CONTRIBUTION_LIMIT are module-level constants
        backdoor_roth_amount = 0.0
        if agi > ROTH_IRA_INCOME_LIMIT:
            backdoor_roth_amount = IRA_CONTRIBUTION_LIMIT
            logger.info(f"Year {year}: AGI ${agi:,.0f} exceeds Roth IRA limit — "
                        f"executing backdoor Roth ${backdoor_roth_amount:,.0f}")
            dl.add("contribution_decisions", "Backdoor Roth IRA",
                   f"Execute ${backdoor_roth_amount:,.0f} backdoor Roth",
                   f"AGI (${agi:,.0f}) exceeds the direct Roth IRA income limit (${ROTH_IRA_INCOME_LIMIT:,.0f}). "
                   "Executing backdoor Roth: contribute to empty Traditional IRA then immediately convert, "
                   "achieving Roth tax treatment without the income restriction.",
                   agi=f"${agi:,.0f}",
                   income_limit=f"${ROTH_IRA_INCOME_LIMIT:,.0f}",
                   amount=f"${backdoor_roth_amount:,.0f}")
        else:
            dl.add("contribution_decisions", "Backdoor Roth IRA",
                   "Direct Roth IRA contribution eligible",
                   f"AGI (${agi:,.0f}) is below the Roth IRA income limit (${ROTH_IRA_INCOME_LIMIT:,.0f}); "
                   "backdoor Roth not needed.",
                   agi=f"${agi:,.0f}")

        # -----------------------------------------------------------------------
        # Decision 4: BETR-validated Roth conversion
        # Only convert if in a favorable bracket AND Traditional is large
        # -----------------------------------------------------------------------
        roth_conversion = 0.0
        if balances.traditional > 0 and max_rate <= max_conversion_rate:
            try:
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, pd.DataFrame(tax_brackets)
                )
                current_income = agi
                conversion_room = max(0, target_bracket_upper - current_income - std_deduction)

                if conversion_room > 10_000:
                    proposed_conversion = min(conversion_room, balances.traditional * 0.10)
                    if proposed_conversion > 1_000:
                        betr_inputs = BETRInputs(
                            current_marginal_rate=max_rate,
                            expected_future_rate=max_conversion_rate,
                            conversion_amount=proposed_conversion,
                            traditional_ira_balance=balances.traditional,
                            pay_from_taxable=True,
                            taxable_account_balance=balances.taxable,
                            years_to_withdrawal=max(1, 73 - age_primary),
                            annual_return=0.07
                        )
                        betr_results = calculate_betr(betr_inputs)
                        if betr_results.conversion_recommended:
                            roth_conversion = proposed_conversion
                            logger.info(f"Stage 2 Prep Roth conversion: ${roth_conversion:,.0f} "
                                        f"(BETR: {betr_results.betr:.2%}, rate: {max_rate:.1%})")
                            dl.add("roth_conversion", "BETR Conversion (Stage 2 Prep)",
                                   f"Convert ${roth_conversion:,.0f}",
                                   "BETR recommends converting while still employed: current rate is at or below "
                                   "the expected retirement rate, so paying tax now is cheaper than paying it "
                                   "on RMDs later. Capped at 10% of Traditional balance.",
                                   betr=f"{betr_results.betr:.2%}",
                                   current_rate=f"{max_rate:.1%}",
                                   expected_future_rate=f"{max_conversion_rate:.1%}",
                                   conversion_room=f"${conversion_room:,.0f}")
                        else:
                            logger.debug(f"BETR {betr_results.betr:.2%} — conversion not recommended")
                            dl.add("roth_conversion", "BETR Conversion (Stage 2 Prep)",
                                   "No conversion",
                                   "BETR does not recommend converting: break-even tax rate is below the "
                                   "current marginal rate — deferring is more efficient.",
                                   betr=f"{betr_results.betr:.2%}",
                                   current_rate=f"{max_rate:.1%}")
                else:
                    dl.add("roth_conversion", "BETR Conversion (Stage 2 Prep)",
                           "No conversion — insufficient bracket room",
                           f"Conversion room (${conversion_room:,.0f}) is below the $10,000 minimum; "
                           "no conversion executed.",
                           conversion_room=f"${conversion_room:,.0f}")
            except Exception as e:
                logger.debug(f"Could not calculate BETR conversion in Stage 2 Prep: {e}")
                dl.add("roth_conversion", "BETR Conversion (Stage 2 Prep)",
                       "No conversion — calculation error",
                       f"BETR calculation failed ({e}); conversion skipped.")
        else:
            if balances.traditional <= 0:
                dl.add("roth_conversion", "BETR Conversion (Stage 2 Prep)",
                       "No conversion — no Traditional balance",
                       "Traditional account balance is zero; nothing to convert.")
            else:
                dl.add("roth_conversion", "BETR Conversion (Stage 2 Prep)",
                       "No conversion — bracket too high",
                       f"Current marginal rate ({max_rate:.1%}) exceeds the max conversion rate "
                       f"({max_conversion_rate:.1%}); converting now would cost more than deferring.",
                       current_rate=f"{max_rate:.1%}",
                       max_conversion_rate=f"{max_conversion_rate:.1%}")

        # Recalculate tax including any conversion
        if roth_conversion > 0:
            total_income = agi + roth_conversion
            taxable_with_conv = total_income - effective_deduction
            federal_tax, _, _ = calculate_taxable_income(taxable_with_conv, tax_brackets)

        # -----------------------------------------------------------------------
        # Compute payroll taxes (FICA, Medicare, State, FUTA/SUTA) on gross wages
        # These are deducted before any savings or investment decisions.
        # -----------------------------------------------------------------------
        payroll_tax, _payroll_breakdown = calculate_payroll_taxes(wages, year) if wages > 0 else (0.0, {})

        after_tax_wages = wages - federal_tax - payroll_tax - (contribution_401k if prefer_roth_401k else 0) - contribution_roth - backdoor_roth_amount

        # Update balances — backdoor Roth moves cash → Roth (net zero on Traditional IRA)
        balances_updated = PortfolioBalances(
            cash=balances.cash + after_tax_wages,
            taxable=balances.taxable,
            traditional=balances.traditional + (0 if prefer_roth_401k else contribution_401k),
            roth=balances.roth + (contribution_401k if prefer_roth_401k else 0)
                 + contribution_roth + backdoor_roth_amount,
            daf=balances.daf + daf_contribution
        )

        logger.info(f"Year {year} Stage 2 Prep: after-tax wages ${after_tax_wages:,.2f}, "
                    f"prefer_roth_401k={prefer_roth_401k}, backdoor_roth=${backdoor_roth_amount:,.0f}")

        # ACA premium — not applicable (employer-sponsored healthcare)
        aca_premium = 0.0

        # Calculate ramped cash buffer target for Stage 2:
        # linearly scales from the wages-based accumulation target (Stage 1 level)
        # up to 75 % of the full retirement cash reserve over the 10-year prep window.
        try:
            latest_retirement_year = _get_latest_retirement_year()
            years_to_retirement = max(1, latest_retirement_year - year)
        except Exception:
            years_to_retirement = self.PREP_WINDOW_YEARS // 2  # safe fallback

        accum_cash_target = calculate_stage2_cash_target(
            wages=wages,
            expenses=expenses,
            years_to_retirement=years_to_retirement,
            prep_window=self.PREP_WINDOW_YEARS,
        )
        logger.debug(
            f"Stage 2 Prep cash target: ${accum_cash_target:,.0f} "
            f"(wages=${wages:,.0f}, years_to_retirement={years_to_retirement}, "
            f"progress={(self.PREP_WINDOW_YEARS - years_to_retirement) / max(1, self.PREP_WINDOW_YEARS - 1):.0%})"
        )

        # Execute rebalancing (includes Roth conversion if any)
        new_balances, transactions, rebal_dl = rebalance_accounts(
            balances=balances_updated,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name,
            federal_tax=federal_tax,
            irmaa_penalty=0.0,
            aca_premium=aca_premium,
            medical_costs=0.0,
            cash_target_override=accum_cash_target,
        )

        trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage']
        magi = agi + trad_withdrawal + roth_conversion  # agi includes wages net of 401k deduction; no SS

        # Record Cash→Roth and Cash→Brokerage contribution decisions for Stage 2
        # In Stage 2, the contribution_401k may go to Roth 401k (prefer_roth_401k)
        # and backdoor_roth_amount is also a cash→roth flow
        stage2_cash_to_roth = (contribution_401k if prefer_roth_401k else 0) + contribution_roth + backdoor_roth_amount
        # Stage 2 does not have an explicit brokerage contribution from wages in this path,
        # but after-tax wages flow to cash first; any surplus above cash target goes to brokerage
        stage2_cash_to_brokerage = 0.0  # Stage 2 routes surplus via rebalance_accounts

        dl.add("contribution_decisions", "Cash → Roth Contribution",
               f"Contribute ${stage2_cash_to_roth:,.0f} from take-home pay",
               "After-tax wages are routed to Roth (Roth 401k and/or backdoor Roth IRA). "
               "This builds tax-free savings without triggering any early-withdrawal penalty "
               "because it is a contribution, not a distribution.",
               roth_401k=f"${contribution_401k if prefer_roth_401k else 0:,.0f}",
               roth_ira=f"${contribution_roth:,.0f}",
               backdoor_roth=f"${backdoor_roth_amount:,.0f}")

        dl.cash_replenishment.extend(rebal_dl.cash_replenishment)
        dl.brokerage_replenishment.extend(rebal_dl.brokerage_replenishment)

        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=wages,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=0,
            taxable_withdrawal=0,
            roth_withdrawal=0,
            roth_conversion=roth_conversion,
            ltcg_harvested=0,
            daf_contribution=daf_contribution,
            expenses=expenses,
            agi=agi,
            magi=magi,
            federal_tax=federal_tax,
            irmaa_penalty=0,
            aca_premium=aca_premium,
            balances=new_balances,
            payroll_tax=payroll_tax,
            wages_to_trad=0 if prefer_roth_401k else contribution_401k,
            wages_to_roth=(contribution_401k if prefer_roth_401k else 0) + contribution_roth + backdoor_roth_amount,
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed'],
            # Accumulation contributions from take-home cash
            cash_to_roth=stage2_cash_to_roth,
            cash_to_brokerage=stage2_cash_to_brokerage,
            decision_log=dl,
        )


class Stage3EarlyRetirement(LifeStage):
    """
    Stage 3: Early Retirement (Pre-Medicare, Pre-SS, Pre-RMD)
    - No wages, no SS benefits yet
    - Optimize Roth conversions (low/no income years)
    - Use LTCG to fund living expenses (0% or 15% rate)
    - Consider ACA subsidies (keep income below 400% FPL)
    - 4% withdrawal strategy
    """

    def __init__(self):
        super().__init__(
            "Stage 3: Early Retirement",
            "Pre-Medicare, pre-SS, pre-RMD - Roth conversion opportunity"
        )

    def applies(self, age_primary: int, age_spouse: int, year: int,
                has_wages: bool, has_ss: bool) -> bool:
        """Applies when retired but before Medicare and SS"""
        return (not has_wages and not has_ss and
                age_primary < MEDICARE_AGE and age_spouse < MEDICARE_AGE)
    
    def calculate_strategy(self, year: int, balances: PortfolioBalances,
                          expenses: float, target_conversion: float = 0,
                          aca_optimize: bool = True, **kwargs) -> YearlyStrategy:
        """
        Calculate early retirement strategy with Roth conversions
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            target_conversion: Target Roth conversion amount
            aca_optimize: Whether to optimize for ACA subsidies
        """
        logger.debug(f"Stage 3 calculation for year {year}, target conversion=${target_conversion:,.2f}")
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        
        # Get tax data
        tax_brackets = get_income_tax_brackets(year)
        cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
        std_deduction_df = get_std_deduction(year)
        std_deduction = std_deduction_df.iloc[0]['deduction']
        
        # NEW STRATEGY: Maintain cash buffer using configured target values
        start_year = kwargs.get('start_year', year)
        cash_target, taxable_target = calculate_cash_buffer_targets(expenses)
        
        # Calculate ramp-up amounts for this year
        cash_need, taxable_need = calculate_buffer_ramp_up(
            year, start_year, cash_target, taxable_target,
            balances.cash, balances.taxable
        )
        
        total_buffer_need = cash_need + taxable_need
        logger.debug(f"Cash target: ${cash_target:,.2f} (need ${cash_need:,.2f}), "
                    f"Taxable target: ${taxable_target:,.2f} (need ${taxable_need:,.2f})")
        
        dl = DecisionLog()

        # Strategy: Use LTCG to fund expenses, maximize Roth conversions
        # Harvest LTCG from taxable account (preferably at 0% rate)

        # Determine optimal LTCG harvest (stay in 0% bracket if possible)
        cg_0_percent = pd.DataFrame(cg_brackets[cg_brackets['rate'] == 0])
        if len(cg_0_percent) > 0:
            cg_0_percent_limit = float(cg_0_percent['upper'].iloc[0])
        else:
            # Fallback: use standard deduction if no 0% bracket exists
            cg_0_percent_limit = std_deduction
            logger.warning(f"No 0% capital gains bracket found for year {year}, using standard deduction")

        # Calculate how much we can withdraw from Brokerage at 0% LTCG rate
        # With 60% cost basis / 40% LTCG assumption:
        # - Total withdrawal = ltcg_room / BROKERAGE_LTCG_RATIO
        # - Only 40% of withdrawal is taxable LTCG
        ltcg_room = cg_0_percent_limit - std_deduction
        estimated_withdrawal_need = expenses * 1.15  # Rough estimate including taxes

        # Calculate maximum withdrawal from brokerage (considering only 40% is taxable)
        max_brokerage_withdrawal = min(
            estimated_withdrawal_need / BROKERAGE_LTCG_RATIO,  # Withdrawal needed to get desired LTCG
            ltcg_room / BROKERAGE_LTCG_RATIO,  # Max withdrawal to stay in 0% bracket
            balances.taxable * 0.5  # Don't withdraw more than 50% of brokerage
        )

        # The taxable LTCG portion is 40% of the withdrawal
        ltcg_harvested = max_brokerage_withdrawal * BROKERAGE_LTCG_RATIO

        logger.debug(f"Brokerage withdrawal: ${max_brokerage_withdrawal:,.2f} (LTCG portion: ${ltcg_harvested:,.2f}, 0% bracket room: ${ltcg_room:,.2f})")

        dl.add("ltcg_decisions", "LTCG Harvest (Stage 3)",
               f"Harvest ${ltcg_harvested:,.0f} LTCG from Brokerage",
               "Early retirement is the prime window for 0% LTCG harvesting: no wages, no SS, no RMDs. "
               "Brokerage withdrawals are capped so that only 40% (the LTCG portion) stays within the "
               "0% capital-gains bracket, minimising tax while funding living expenses.",
               ltcg_room=f"${ltcg_room:,.0f}",
               max_brokerage_withdrawal=f"${max_brokerage_withdrawal:,.0f}",
               ltcg_harvested=f"${ltcg_harvested:,.0f}",
               brokerage_balance=f"${balances.taxable:,.0f}")

        # Calculate Roth conversion using BETR algorithm
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        current_income = ltcg_harvested

        # Initialize roth_conversion
        roth_conversion = 0

        # Use BETR algorithm to optimize conversion amount
        try:
            optimal_amount, betr_results = optimize_conversion_amount(
                traditional_ira_balance=balances.traditional,
                current_agi=current_income,
                target_tax_bracket=max_conversion_rate,
                year=year,
                pay_from_taxable=True,
                taxable_account_balance=balances.taxable,
                years_to_withdrawal=(73 - age_primary) if age_primary > 0 else 20,
                annual_return=kwargs.get('growth_rate', 1.07) - 1.0
            )

            if optimal_amount <= 0:
                roth_conversion = 0
                logger.info('No conversion: insufficient tax bracket room')
                dl.add("roth_conversion", "BETR Conversion (Stage 3)",
                       "No conversion — no bracket room",
                       "BETR optimizer found no room to convert within the target bracket after "
                       "accounting for LTCG income.",
                       current_income=f"${current_income:,.0f}",
                       target_bracket=f"{max_conversion_rate:.1%}")
            else:
                if betr_results.conversion_recommended:
                    roth_conversion = optimal_amount
                    logger.info(f'BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f}')
                    dl.add("roth_conversion", "BETR Conversion (Stage 3)",
                           f"Convert ${roth_conversion:,.0f}",
                           "Early retirement is the optimal Roth conversion window: income is low (LTCG only), "
                           "so the marginal rate on conversions is at its lifetime minimum. "
                           "BETR confirms converting now is cheaper than paying ordinary income tax on "
                           "Traditional withdrawals or RMDs later.",
                           betr=f"{betr_results.betr:.2%}",
                           current_income=f"${current_income:,.0f}",
                           target_bracket=f"{max_conversion_rate:.1%}",
                           optimal_amount=f"${optimal_amount:,.0f}")
                else:
                    roth_conversion = 0
                    logger.info(f'BETR: {betr_results.betr:.2%}, Conversion not recommended')
                    dl.add("roth_conversion", "BETR Conversion (Stage 3)",
                           "No conversion",
                           "BETR does not recommend converting: the break-even tax rate is below the "
                           "current marginal rate — deferring is more efficient.",
                           betr=f"{betr_results.betr:.2%}",
                           optimal_amount=f"${optimal_amount:,.0f}")

        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to bracket-filling method")
            dl.add("roth_conversion", "BETR Conversion (Stage 3)",
                   "Fallback bracket-fill conversion",
                   f"BETR calculation failed ({e}). Falling back to simple bracket-filling: "
                   "converting up to the top of the target bracket.",
                   error=str(e))
            # Fallback to original method
            try:
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, pd.DataFrame(tax_brackets)
                )
            except ValueError:
                target_bracket_rate = 0.12
                target_bracket_upper = float(getUpperIncomeRate(0.12, tax_brackets))

            conversion_room = max(0, target_bracket_upper - std_deduction - current_income)
            roth_conversion = min(conversion_room, balances.traditional)

        logger.debug(f"Roth conversion: ${roth_conversion:,.2f}")

        # Calculate taxes
        total_income = ltcg_harvested + roth_conversion
        agi = total_income - std_deduction

        # Income tax on conversions
        federal_tax, max_rate, upper_max = calculate_taxable_income(agi, tax_brackets)

        # Capital gains tax
        cg_tax = calculate_cap_gains(agi - ltcg_harvested, cg_brackets, ltcg_harvested)

        total_tax = federal_tax + cg_tax

        logger.debug(f"Total tax: ${total_tax:,.2f} (income: ${federal_tax:,.2f}, CG: ${cg_tax:,.2f})")

        # Calculate ACA premium based on configuration
        aca_premium = calculate_aca_premium_for_year(year, age_primary, age_spouse)
        dl.add("aca_decisions", "ACA Premium (Stage 3)",
               f"ACA premium: ${aca_premium:,.0f}",
               "Pre-Medicare retirees must purchase ACA marketplace coverage. "
               "The premium is calculated from config (age, number of people). "
               "Roth conversions and LTCG harvesting are sized to keep MAGI below 400% FPL "
               "to preserve ACA premium tax credits.",
               aca_premium=f"${aca_premium:,.0f}",
               age_primary=age_primary,
               age_spouse=age_spouse)
        
        # Execute account rebalancing (includes Roth conversion and buffer maintenance)
        new_balances, transactions, rebal_dl = rebalance_accounts(
            balances=balances,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name,
            federal_tax=total_tax,
            irmaa_penalty=0.0,
            aca_premium=aca_premium,
            medical_costs=0.0
        )
        
        # Apply growth rate to remaining balances
        growth_rate = kwargs.get('growth_rate', 1.07)
        new_balances = PortfolioBalances(
            cash=new_balances.cash,
            taxable=new_balances.taxable * growth_rate,
            traditional=new_balances.traditional * growth_rate,
            roth=new_balances.roth * growth_rate,
            daf=new_balances.daf
        )
        
        # Calculate MAGI for this year
        trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage']
        magi = (0 * TAXABLE_SS_RATE +  # No SS benefits yet
                trad_withdrawal +
                roth_conversion +
                ltcg_harvested)
        
        dl.cash_replenishment.extend(rebal_dl.cash_replenishment)
        dl.brokerage_replenishment.extend(rebal_dl.brokerage_replenishment)

        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=trad_withdrawal,
            taxable_withdrawal=transactions['brokerage_to_cash'],
            roth_withdrawal=transactions['roth_to_cash'] + transactions['roth_to_brokerage'],
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            agi=agi,
            magi=magi,
            federal_tax=total_tax,
            irmaa_penalty=0,
            aca_premium=aca_premium,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed'],
            decision_log=dl,
        )


class Stage4Medicare(LifeStage):
    """
    Stage 4: Medicare Stage (Pre-SS, Pre-RMD)
    - On Medicare, optimize for IRMAA
    - Continue Roth conversions but watch IRMAA thresholds
    - IRMAA based on MAGI from 2 years prior
    - Balance conversions vs IRMAA penalties
    """

    def __init__(self):
        super().__init__(
            "Stage 4: Medicare",
            "On Medicare, optimizing for IRMAA while continuing Roth conversions"
        )
    
    def applies(self, age_primary: int, age_spouse: int, year: int,
                has_wages: bool, has_ss: bool) -> bool:
        """Applies when on Medicare but before SS and RMDs"""
        return (not has_wages and not has_ss and
                (age_primary >= MEDICARE_AGE or age_spouse >= MEDICARE_AGE) and
                age_primary < RMD_AGE)
    
    def calculate_strategy(self, year: int, balances: PortfolioBalances,
                          expenses: float, target_conversion: float = 0,
                          prior_magi: float = 0, **kwargs) -> YearlyStrategy:
        """
        Calculate Medicare stage strategy optimizing for IRMAA
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            target_conversion: Target Roth conversion amount
            prior_magi: MAGI from 2 years prior (for IRMAA calculation)
        """
        logger.debug(f"Stage 4 calculation for year {year}, prior MAGI=${prior_magi:,.2f}")
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        
        # Get tax and IRMAA data
        tax_brackets = get_income_tax_brackets(year)
        cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
        std_deduction_df = get_std_deduction(year)
        irmaa_brackets = get_medicare_costs(year)
        std_deduction = std_deduction_df.iloc[0]['deduction']
        
        # Calculate IRMAA penalty based on prior year MAGI
        people_on_medicare = sum([age_primary >= MEDICARE_AGE, age_spouse >= MEDICARE_AGE])
        irmaa_penalty = calculate_irmma_penalty(prior_magi, irmaa_brackets, people_on_medicare)
        
        logger.debug(f"IRMAA penalty: ${irmaa_penalty:,.2f} for {people_on_medicare} people")
        
        # Find IRMAA threshold to avoid jumping to next bracket
        current_irmaa_bracket = None
        next_irmaa_threshold = float('inf')
        
        for _, row in irmaa_brackets.iterrows():
            if row['lower'] <= prior_magi <= row['upper']:
                current_irmaa_bracket = row
                # Find next bracket
                next_brackets = pd.DataFrame(irmaa_brackets[irmaa_brackets['lower'] > row['upper']])
                if not next_brackets.empty:
                    next_irmaa_threshold = float(next_brackets.iloc[0]['lower'])
                break
        
        logger.debug(f"Next IRMAA threshold: ${next_irmaa_threshold:,.2f}")
        
        # Calculate cash buffer target (2 years in Cash, 3 years in Taxable)
        start_year = kwargs.get('start_year', year)
        cash_target, taxable_target = calculate_cash_buffer_targets(expenses)
        cash_need, taxable_need = calculate_buffer_ramp_up(
            year, start_year, cash_target, taxable_target,
            balances.cash, balances.taxable
        )
        total_buffer_need = cash_need + taxable_need
        
        logger.debug(f"Cash target: ${cash_target:,.2f} (need ${cash_need:,.2f}), "
                    f"Taxable target: ${taxable_target:,.2f} (need ${taxable_need:,.2f})")
        
        # Calculate withdrawal need
        total_need = expenses + irmaa_penalty
        
        # Harvest LTCG for expenses
        cg_0_percent = pd.DataFrame(cg_brackets[cg_brackets['rate'] == 0])
        if len(cg_0_percent) > 0:
            cg_0_percent_limit = float(cg_0_percent['upper'].iloc[0])
        else:
            cg_0_percent_limit = std_deduction
            logger.warning(f"No 0% capital gains bracket found for year {year}, using standard deduction")
        ltcg_room = cg_0_percent_limit - std_deduction
        
        # Calculate maximum withdrawal from brokerage (considering only 40% is taxable LTCG)
        max_brokerage_withdrawal = min(
            (total_need * 1.2) / BROKERAGE_LTCG_RATIO,  # Withdrawal needed
            ltcg_room / BROKERAGE_LTCG_RATIO,  # Max to stay in 0% bracket
            balances.taxable * 0.5  # Don't withdraw more than 50%
        )
        ltcg_harvested = max_brokerage_withdrawal * BROKERAGE_LTCG_RATIO
        
        # Calculate Roth conversion using BETR algorithm with IRMAA consideration
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        current_income = ltcg_harvested
        
        # Calculate IRMAA headroom
        irmaa_headroom = next_irmaa_threshold - ltcg_harvested - std_deduction
        
        # Initialize roth_conversion and optimal_amount
        roth_conversion = 0
        optimal_amount = 0
        
        # Use BETR algorithm to optimize conversion
        try:
            optimal_amount, betr_results = optimize_conversion_amount(
                traditional_ira_balance=balances.traditional,
                current_agi=current_income,
                target_tax_bracket=max_conversion_rate,
                year=year,
                pay_from_taxable=True,
                taxable_account_balance=balances.taxable,
                years_to_withdrawal=(73 - age_primary) if age_primary > 0 else 15,
                annual_return=kwargs.get('growth_rate', 1.07) - 1.0
            )
            
            # Check if optimal_amount is positive before proceeding
            if optimal_amount <= 0:
                roth_conversion = 0
                logger.info('No conversion: insufficient tax bracket room')
            else:
                # Check IRMAA impact of proposed conversion
                if optimal_amount > irmaa_headroom:
                    # Conversion would cross IRMAA threshold
                    irmaa_safe_amount = max(0, irmaa_headroom)
                    
                    # Recalculate BETR with reduced amount
                    if irmaa_safe_amount > 0:
                        reduced_inputs = BETRInputs(
                            current_marginal_rate=max_conversion_rate,
                            expected_future_rate=0.24,
                            conversion_amount=irmaa_safe_amount,
                            traditional_ira_balance=balances.traditional,
                            pay_from_taxable=True,
                            taxable_account_balance=balances.taxable,
                            years_to_withdrawal=(73 - age_primary) if age_primary > 0 else 15,
                            annual_return=kwargs.get('growth_rate', 1.07) - 1.0
                        )
                        reduced_results = calculate_betr(reduced_inputs)
                        
                        if reduced_results.conversion_recommended:
                            roth_conversion = irmaa_safe_amount
                            logger.info(f"BETR: {reduced_results.betr:.2%}, Converting ${irmaa_safe_amount:,.0f} (IRMAA-limited)")
                        else:
                            logger.info(f"BETR: {reduced_results.betr:.2%}, Conversion not recommended even at IRMAA limit")
                    else:
                        logger.info("No conversion room due to IRMAA threshold")
                else:
                    # Conversion fits within IRMAA headroom
                    if betr_results.conversion_recommended:
                        roth_conversion = optimal_amount
                        logger.info(f"BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f}")
                    else:
                        logger.info(f"BETR: {betr_results.betr:.2%}, Conversion not recommended")
                    
        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to IRMAA-aware method")
            # Fallback to original IRMAA-aware method
            try:
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, pd.DataFrame(tax_brackets)
                )
            except ValueError:
                target_bracket_rate = 0.12
                target_bracket_upper = float(getUpperIncomeRate(0.12, tax_brackets))
            
            tax_headroom = target_bracket_upper - std_deduction - ltcg_harvested
            conversion_room = min(irmaa_headroom, tax_headroom)
            roth_conversion = min(conversion_room, balances.traditional)
        
        logger.debug(f"Roth conversion: ${roth_conversion:,.2f} (IRMAA headroom: ${irmaa_headroom:,.2f})")
        
        # Calculate taxes
        total_income = ltcg_harvested + roth_conversion
        agi = total_income - std_deduction
        
        federal_tax, max_rate, upper_max = calculate_taxable_income(agi, tax_brackets)
        cg_tax = calculate_cap_gains(agi - ltcg_harvested, cg_brackets, ltcg_harvested)
        total_tax = federal_tax + cg_tax
        
        # Calculate ACA premium based on configuration (may still apply if under 65)
        aca_premium = calculate_aca_premium_for_year(year, age_primary, age_spouse)
        
        # --- Decision log for Stage 4 ---
        dl = DecisionLog()

        # Execute account rebalancing (includes Roth conversion and buffer maintenance)
        new_balances, transactions, rebal_dl = rebalance_accounts(
            balances=balances,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=aca_premium,
            medical_costs=0.0
        )
        
        # Apply growth
        growth_rate = kwargs.get('growth_rate', 1.07)
        new_balances = PortfolioBalances(
            cash=new_balances.cash,
            taxable=new_balances.taxable * growth_rate,
            traditional=new_balances.traditional * growth_rate,
            roth=new_balances.roth * growth_rate,
            daf=new_balances.daf
        )
        
        # Calculate MAGI for this year
        trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage']
        magi = (0 * TAXABLE_SS_RATE +  # No SS benefits yet
                trad_withdrawal +
                roth_conversion +
                ltcg_harvested)
        
        # IRMAA assessment
        dl.add(
            "irmaa_decisions",
            "IRMAA Assessment",
            f"${irmaa_penalty:,.0f} penalty ({people_on_medicare} person(s) on Medicare)",
            "IRMAA is based on MAGI from 2 years prior. "
            "Roth conversions are capped at the IRMAA headroom to avoid crossing into the next bracket.",
            prior_magi=f"${prior_magi:,.0f}",
            people_on_medicare=people_on_medicare,
            next_irmaa_threshold=f"${next_irmaa_threshold:,.0f}" if next_irmaa_threshold != float('inf') else "None",
            irmaa_headroom=f"${irmaa_headroom:,.0f}",
        )

        # LTCG harvest decision
        dl.add(
            "ltcg_decisions",
            "LTCG Harvest",
            f"Harvested ${ltcg_harvested:,.0f} from brokerage",
            f"Harvesting LTCG up to the 0% bracket limit (${ltcg_room:,.0f} room). "
            f"Only {BROKERAGE_LTCG_RATIO:.0%} of brokerage withdrawals are taxable LTCG.",
            ltcg_room=f"${ltcg_room:,.0f}",
            ltcg_harvested=f"${ltcg_harvested:,.0f}",
            brokerage_ltcg_ratio=f"{BROKERAGE_LTCG_RATIO:.0%}",
        )

        # Roth conversion decision (mirrors the logic above)
        if roth_conversion > 0 and roth_conversion == irmaa_headroom:
            dl.add(
                "roth_conversion",
                "Roth Conversion",
                f"Convert ${roth_conversion:,.0f} (IRMAA-limited)",
                "BETR algorithm recommended a larger conversion but it was capped at the IRMAA "
                "headroom to avoid triggering a higher Medicare premium bracket next year.",
                optimal_betr_amount=f"${optimal_amount:,.0f}",
                irmaa_headroom=f"${irmaa_headroom:,.0f}",
                conversion_executed=f"${roth_conversion:,.0f}",
            )
        elif roth_conversion > 0:
            dl.add(
                "roth_conversion",
                "Roth Conversion",
                f"Convert ${roth_conversion:,.0f}",
                "BETR algorithm recommended this conversion amount. "
                "It fits within the IRMAA headroom so no Medicare penalty increase is expected.",
                irmaa_headroom=f"${irmaa_headroom:,.0f}",
                conversion_executed=f"${roth_conversion:,.0f}",
            )
        else:
            dl.add(
                "roth_conversion",
                "Roth Conversion",
                "No conversion",
                "Either BETR did not recommend a conversion at current rates, "
                "there was no room within the IRMAA headroom, or the Traditional balance is zero.",
                irmaa_headroom=f"${irmaa_headroom:,.0f}",
                traditional_balance=f"${balances.traditional:,.0f}",
            )

        # ACA premium
        dl.add(
            "aca_decisions",
            "ACA Premium",
            f"${aca_premium:,.0f}/yr" if aca_premium > 0 else "No ACA premium",
            "ACA premium applies if either person is under 65 and not yet on Medicare.",
            aca_premium=f"${aca_premium:,.0f}",
        )

        # Merge rebalancing decisions
        for entry in rebal_dl.all_decisions():
            getattr(dl, _category_for(entry)).append(entry)

        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=trad_withdrawal,
            taxable_withdrawal=transactions['brokerage_to_cash'],
            roth_withdrawal=transactions['roth_to_cash'] + transactions['roth_to_brokerage'],
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            agi=agi,
            magi=magi,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=aca_premium,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed'],
            decision_log=dl,
        )


class Stage5SocialSecurity(LifeStage):
    """
    Stage 5: Social Security Stage (SS + Medicare, Pre-RMD)
    - Collecting SS benefits
    - On Medicare (IRMAA considerations)
    - Continue strategic Roth conversions
    - Balance SS taxation (up to 85% taxable)
    """

    def __init__(self):
        super().__init__(
            "Stage 5: Social Security",
            "Collecting SS + Medicare, pre-RMD optimization"
        )
    
    def applies(self, age_primary: int, age_spouse: int, year: int,
                has_wages: bool, has_ss: bool) -> bool:
        """Applies when collecting SS but before RMDs"""
        return (not has_wages and has_ss and age_primary < RMD_AGE)
    
    def calculate_strategy(self, year: int, balances: PortfolioBalances,
                          expenses: float, ss_benefits: float = 0,
                          target_conversion: float = 0, prior_magi: float = 0,
                          **kwargs) -> YearlyStrategy:
        """
        Calculate SS stage strategy with IRMAA and SS taxation
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            ss_benefits: Annual SS benefits
            target_conversion: Target Roth conversion amount
            prior_magi: MAGI from 2 years prior (for IRMAA)
        """
        logger.debug(f"Stage 5 calculation for year {year}, SS=${ss_benefits:,.2f}")
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        
        # Get tax data
        tax_brackets = get_income_tax_brackets(year)
        cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
        std_deduction_df = get_std_deduction(year)
        irmaa_brackets = get_medicare_costs(year)
        std_deduction = std_deduction_df.iloc[0]['deduction']
        
        # Calculate IRMAA
        people_on_medicare = sum([age_primary >= MEDICARE_AGE, age_spouse >= MEDICARE_AGE])
        irmaa_penalty = calculate_irmma_penalty(prior_magi, irmaa_brackets, people_on_medicare)
        
        # 85% of SS is taxable at higher incomes
        taxable_ss = ss_benefits * TAXABLE_SS_RATE
        
        # Calculate cash buffer target (2 years in Cash, 3 years in Taxable)
        start_year = kwargs.get('start_year', year)
        cash_target, taxable_target = calculate_cash_buffer_targets(expenses)
        cash_need, taxable_need = calculate_buffer_ramp_up(
            year, start_year, cash_target, taxable_target,
            balances.cash, balances.taxable
        )
        total_buffer_need = cash_need + taxable_need
        
        logger.debug(f"Cash target: ${cash_target:,.2f} (need ${cash_need:,.2f}), "
                    f"Taxable target: ${taxable_target:,.2f} (need ${taxable_need:,.2f})")
        
        # Calculate withdrawal need (SS covers part of expenses)
        withdrawal_need = max(0, expenses + irmaa_penalty - ss_benefits)
        
        # Harvest LTCG if needed
        ltcg_harvested = 0
        if withdrawal_need > 0 and balances.taxable > 0:
            cg_0_percent = pd.DataFrame(cg_brackets[cg_brackets['rate'] == 0])
            if len(cg_0_percent) > 0:
                cg_0_percent_limit = float(cg_0_percent['upper'].iloc[0])
            else:
                cg_0_percent_limit = std_deduction
                logger.warning(f"No 0% capital gains bracket found for year {year}, using standard deduction")
            ltcg_room = max(0, cg_0_percent_limit - taxable_ss - std_deduction)
            
            # Calculate maximum withdrawal from brokerage (considering only 40% is taxable LTCG)
            max_brokerage_withdrawal = min(
                withdrawal_need / BROKERAGE_LTCG_RATIO,  # Withdrawal needed
                ltcg_room / BROKERAGE_LTCG_RATIO,  # Max to stay in 0% bracket
                balances.taxable * 0.5  # Don't withdraw more than 50%
            )
            ltcg_harvested = max_brokerage_withdrawal * BROKERAGE_LTCG_RATIO
        
        # Calculate Roth conversion room
        current_income = taxable_ss + ltcg_harvested
        
        # Find IRMAA threshold
        next_irmaa_threshold = float('inf')
        for _, row in irmaa_brackets.iterrows():
            if row['lower'] <= prior_magi <= row['upper']:
                next_brackets = pd.DataFrame(irmaa_brackets[irmaa_brackets['lower'] > row['upper']])
                if not next_brackets.empty:
                    next_irmaa_threshold = float(next_brackets.iloc[0]['lower'])
                break
        
        irmaa_headroom = next_irmaa_threshold - current_income - std_deduction
        
        # Calculate Roth conversion using BETR algorithm with SS income
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        
        # Initialize roth_conversion and optimal_amount
        roth_conversion = 0
        optimal_amount = 0
        
        # Use BETR algorithm - SS income is already in current_income
        try:
            optimal_amount, betr_results = optimize_conversion_amount(
                traditional_ira_balance=balances.traditional,
                current_agi=current_income,
                target_tax_bracket=max_conversion_rate,
                year=year,
                pay_from_taxable=True,
                taxable_account_balance=balances.taxable,
                years_to_withdrawal=(73 - age_primary) if age_primary > 0 else 10,
                annual_return=kwargs.get('growth_rate', 1.07) - 1.0
            )
            
            # Early check: skip all IRMAA checks if no conversion is optimal
            if optimal_amount <= 0:
                roth_conversion = 0
                logger.info('No conversion: insufficient tax bracket room with SS income')
            else:
                # Check IRMAA impact
                if optimal_amount > irmaa_headroom:
                    # Would cross IRMAA threshold - reduce conversion
                    irmaa_safe_amount = max(0, irmaa_headroom)
                    
                    if irmaa_safe_amount > 0:
                        # Verify reduced amount is still beneficial
                        reduced_inputs = BETRInputs(
                            current_marginal_rate=max_conversion_rate,
                            expected_future_rate=0.24,
                            conversion_amount=irmaa_safe_amount,
                            traditional_ira_balance=balances.traditional,
                            pay_from_taxable=True,
                            taxable_account_balance=balances.taxable,
                            years_to_withdrawal=(73 - age_primary) if age_primary > 0 else 10,
                            annual_return=kwargs.get('growth_rate', 1.07) - 1.0
                        )
                        reduced_results = calculate_betr(reduced_inputs)
                        
                        if reduced_results.conversion_recommended:
                            roth_conversion = irmaa_safe_amount
                            logger.info(f"BETR: {reduced_results.betr:.2%}, Converting ${irmaa_safe_amount:,.0f} (IRMAA-limited, with SS)")
                        else:
                            logger.info(f"BETR: {reduced_results.betr:.2%}, Conversion not recommended with SS income")
                    else:
                        logger.info("No conversion room due to SS income and IRMAA threshold")
                else:
                    # Conversion fits within IRMAA headroom
                    if betr_results.conversion_recommended:
                        roth_conversion = optimal_amount
                        logger.info(f"BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f} with SS income")
                    else:
                        logger.info(f"BETR: {betr_results.betr:.2%}, Conversion not recommended despite SS income")
                    
        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to conservative method")
            # Fallback to original method
            try:
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, pd.DataFrame(tax_brackets)
                )
            except ValueError:
                target_bracket_rate = 0.22
                target_bracket_upper = float(getUpperIncomeRate(0.22, tax_brackets))
            
            tax_headroom = target_bracket_upper - std_deduction - current_income
            conversion_room = min(irmaa_headroom, tax_headroom)
            roth_conversion = min(conversion_room * 0.8, balances.traditional)
        
        logger.debug(f"Roth conversion: ${roth_conversion:,.2f} with SS income")
        
        # Calculate taxes
        total_income = taxable_ss + ltcg_harvested + roth_conversion
        agi = total_income - std_deduction
        
        federal_tax, max_rate, upper_max = calculate_taxable_income(agi, tax_brackets)
        cg_tax = calculate_cap_gains(agi - ltcg_harvested, cg_brackets, ltcg_harvested)
        total_tax = federal_tax + cg_tax
        
        # Add SS benefits to cash before rebalancing
        balances_with_ss = PortfolioBalances(
            cash=balances.cash + ss_benefits,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth,
            daf=balances.daf
        )
        
        logger.info(f"Year {year}: Added SS benefits ${ss_benefits:,.2f} to cash")
        
        # Calculate ACA premium (should be 0 at this stage, but check anyway)
        aca_premium = calculate_aca_premium_for_year(year, age_primary, age_spouse)
        
        # Execute account rebalancing (includes Roth conversion and buffer maintenance)
        new_balances, transactions, rebal_dl = rebalance_accounts(
            balances=balances_with_ss,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=aca_premium,
            medical_costs=0.0
        )
        
        # Apply growth
        growth_rate = kwargs.get('growth_rate', 1.07)
        new_balances = PortfolioBalances(
            cash=new_balances.cash,
            taxable=new_balances.taxable * growth_rate,
            traditional=new_balances.traditional * growth_rate,
            roth=new_balances.roth * growth_rate,
            daf=new_balances.daf
        )
        
        # Calculate MAGI for this year
        trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage']
        magi = (ss_benefits * TAXABLE_SS_RATE +
                trad_withdrawal +
                roth_conversion +
                ltcg_harvested)
        
        # --- Decision log for Stage 5 ---
        dl = DecisionLog()

        # SS income / taxation
        dl.add(
            "ss_decisions",
            "Social Security Income",
            f"${ss_benefits:,.0f}/yr (${taxable_ss:,.0f} taxable at {TAXABLE_SS_RATE:.0%})",
            f"Up to {TAXABLE_SS_RATE:.0%} of SS benefits are included in taxable income at higher "
            "income levels. SS income reduces the amount that must be withdrawn from investment accounts.",
            ss_benefits=f"${ss_benefits:,.0f}",
            taxable_ss=f"${taxable_ss:,.0f}",
            taxable_ss_rate=f"{TAXABLE_SS_RATE:.0%}",
        )

        # IRMAA assessment
        dl.add(
            "irmaa_decisions",
            "IRMAA Assessment",
            f"${irmaa_penalty:,.0f} penalty ({people_on_medicare} person(s) on Medicare)",
            "IRMAA is based on MAGI from 2 years prior. "
            "Roth conversions are capped at the IRMAA headroom to avoid crossing into the next bracket.",
            prior_magi=f"${prior_magi:,.0f}",
            people_on_medicare=people_on_medicare,
            next_irmaa_threshold=f"${next_irmaa_threshold:,.0f}" if next_irmaa_threshold != float('inf') else "None",
            irmaa_headroom=f"${irmaa_headroom:,.0f}",
        )

        # LTCG harvest decision
        dl.add(
            "ltcg_decisions",
            "LTCG Harvest",
            f"Harvested ${ltcg_harvested:,.0f} from brokerage",
            f"Harvesting LTCG up to the 0% bracket limit after accounting for taxable SS income. "
            f"Only {BROKERAGE_LTCG_RATIO:.0%} of brokerage withdrawals are taxable LTCG.",
            ltcg_harvested=f"${ltcg_harvested:,.0f}",
            brokerage_ltcg_ratio=f"{BROKERAGE_LTCG_RATIO:.0%}",
        )

        # Roth conversion decision
        if roth_conversion > 0 and roth_conversion < optimal_amount:
            dl.add(
                "roth_conversion",
                "Roth Conversion",
                f"Convert ${roth_conversion:,.0f} (IRMAA-limited with SS income)",
                "BETR algorithm recommended a larger conversion but it was capped at the IRMAA "
                "headroom. SS income reduces available conversion room.",
                optimal_betr_amount=f"${optimal_amount:,.0f}",
                irmaa_headroom=f"${irmaa_headroom:,.0f}",
                conversion_executed=f"${roth_conversion:,.0f}",
            )
        elif roth_conversion > 0:
            dl.add(
                "roth_conversion",
                "Roth Conversion",
                f"Convert ${roth_conversion:,.0f} (with SS income)",
                "BETR algorithm recommended this conversion. "
                "It fits within the IRMAA headroom despite SS income.",
                irmaa_headroom=f"${irmaa_headroom:,.0f}",
                conversion_executed=f"${roth_conversion:,.0f}",
            )
        else:
            dl.add(
                "roth_conversion",
                "Roth Conversion",
                "No conversion",
                "BETR did not recommend a conversion, or SS income plus IRMAA constraints "
                "left no room for a beneficial conversion.",
                irmaa_headroom=f"${irmaa_headroom:,.0f}",
                traditional_balance=f"${balances.traditional:,.0f}",
            )

        # ACA premium
        dl.add(
            "aca_decisions",
            "ACA Premium",
            f"${aca_premium:,.0f}/yr" if aca_premium > 0 else "No ACA premium",
            "ACA premium applies if either person is under 65 and not yet on Medicare.",
            aca_premium=f"${aca_premium:,.0f}",
        )

        # Merge rebalancing decisions
        for entry in rebal_dl.all_decisions():
            getattr(dl, _category_for(entry)).append(entry)

        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=ss_benefits,
            rmd_amount=0,
            traditional_withdrawal=trad_withdrawal,
            taxable_withdrawal=transactions['brokerage_to_cash'],
            roth_withdrawal=transactions['roth_to_cash'] + transactions['roth_to_brokerage'],
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            agi=agi,
            magi=magi,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=aca_premium,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed'],
            decision_log=dl,
        )


class Stage6RMD(LifeStage):
    """
    Stage 6: RMD Stage (Full Retirement)
    - Required Minimum Distributions from Traditional accounts
    - SS benefits + Medicare
    - RMDs may push into higher tax brackets
    - Limited Roth conversion opportunity
    - Focus on tax-efficient withdrawal sequencing
    """

    def __init__(self):
        super().__init__(
            "Stage 6: RMD",
            "RMD age - managing required distributions with SS and Medicare"
        )
    
    def applies(self, age_primary: int, age_spouse: int, year: int,
                has_wages: bool, has_ss: bool) -> bool:
        """Applies when at RMD age"""
        return age_primary >= RMD_AGE or age_spouse >= RMD_AGE
    
    def calculate_strategy(self, year: int, balances: PortfolioBalances,
                          expenses: float, ss_benefits: float = 0,
                          prior_magi: float = 0, **kwargs) -> YearlyStrategy:
        """
        Calculate RMD stage strategy
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            ss_benefits: Annual SS benefits
            prior_magi: MAGI from 2 years prior (for IRMAA)
        """
        logger.debug(f"Stage 5 calculation for year {year}")
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        
        # Get tax data
        tax_brackets = get_income_tax_brackets(year)
        cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
        std_deduction_df = get_std_deduction(year)
        irmaa_brackets = get_medicare_costs(year)
        std_deduction = std_deduction_df.iloc[0]['deduction']
        
        # Calculate RMD
        rmd_rate = get_rmd_value(age_primary)
        rmd_amount = 0
        if rmd_rate > 0 and balances.traditional > 0:
            rmd_amount = balances.traditional / rmd_rate
        
        logger.debug(f"RMD amount: ${rmd_amount:,.2f} (rate: {rmd_rate})")
        
        # Calculate IRMAA
        people_on_medicare = sum([age_primary >= MEDICARE_AGE, age_spouse >= MEDICARE_AGE])
        irmaa_penalty = calculate_irmma_penalty(prior_magi, irmaa_brackets, people_on_medicare)
        
        # Calculate cash buffer target (2 years in Cash, 3 years in Taxable)
        start_year = kwargs.get('start_year', year)
        cash_target, taxable_target = calculate_cash_buffer_targets(expenses)
        cash_need, taxable_need = calculate_buffer_ramp_up(
            year, start_year, cash_target, taxable_target,
            balances.cash, balances.taxable
        )
        total_buffer_need = cash_need + taxable_need
        
        logger.debug(f"Cash target: ${cash_target:,.2f} (need ${cash_need:,.2f}), "
                    f"Taxable target: ${taxable_target:,.2f} (need ${taxable_need:,.2f})")
        
        # Taxable SS
        taxable_ss = ss_benefits * TAXABLE_SS_RATE
        
        # Total income includes RMD (required)
        total_income = taxable_ss + rmd_amount
        
        # Calculate if additional withdrawals needed
        withdrawal_need = max(0, expenses + irmaa_penalty - ss_benefits - rmd_amount)
        
        # Harvest LTCG if beneficial
        ltcg_harvested = 0
        if withdrawal_need > 0 and balances.taxable > 0:
            # Check if we can harvest at favorable rates
            cg_15_percent = pd.DataFrame(cg_brackets[cg_brackets['rate'] == 0.15])
            if len(cg_15_percent) > 0:
                cg_15_percent_limit = float(cg_15_percent['upper'].iloc[0])
                ltcg_room = max(0, cg_15_percent_limit - total_income - std_deduction)
                
                # Calculate maximum withdrawal from brokerage (considering only 40% is taxable LTCG)
                max_brokerage_withdrawal = min(
                    withdrawal_need / BROKERAGE_LTCG_RATIO,  # Withdrawal needed
                    ltcg_room / BROKERAGE_LTCG_RATIO,  # Max to stay in 15% bracket
                    balances.taxable * 0.5  # Don't withdraw more than 50%
                )
                ltcg_harvested = max_brokerage_withdrawal * BROKERAGE_LTCG_RATIO
                total_income += ltcg_harvested
        
        # Limited Roth conversion opportunity (if RMD doesn't fill bracket)
        roth_conversion = 0
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        try:
            target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                max_conversion_rate, pd.DataFrame(tax_brackets)
            )
            conversion_room = max(0, target_bracket_upper - total_income - std_deduction)
            
            if conversion_room > 10000 and balances.traditional > rmd_amount:
                # Only convert if meaningful room and won't trigger higher IRMAA
                next_irmaa_threshold = float('inf')
                for _, row in irmaa_brackets.iterrows():
                    if row['lower'] <= prior_magi <= row['upper']:
                        next_brackets = pd.DataFrame(irmaa_brackets[irmaa_brackets['lower'] > row['upper']])
                        if not next_brackets.empty:
                            next_irmaa_threshold = float(next_brackets.iloc[0]['lower'])
                        break
                
                irmaa_headroom = next_irmaa_threshold - total_income - std_deduction
                safe_conversion = min(conversion_room, irmaa_headroom, balances.traditional - rmd_amount)
                
                if safe_conversion > 10000:
                    roth_conversion = safe_conversion * 0.5  # Conservative
                    total_income += roth_conversion
        except ValueError:
            pass  # No conversion if bracket not found
        
        logger.debug(f"Roth conversion: ${roth_conversion:,.2f} (limited by RMD)")
        
        # Calculate taxes
        agi = total_income - std_deduction
        federal_tax, max_rate, upper_max = calculate_taxable_income(agi, tax_brackets)
        cg_tax = calculate_cap_gains(agi - ltcg_harvested, cg_brackets, ltcg_harvested)
        total_tax = federal_tax + cg_tax
        
        # Add SS benefits to cash before rebalancing
        balances_with_ss = PortfolioBalances(
            cash=balances.cash + ss_benefits,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth,
            daf=balances.daf
        )
        
        logger.info(f"Year {year}: Added SS benefits ${ss_benefits:,.2f} to cash")
        
        # Calculate ACA premium (should be 0 at this stage, but check anyway)
        aca_premium = calculate_aca_premium_for_year(year, age_primary, age_spouse)
        
        # Execute account rebalancing (includes Roth conversion and buffer maintenance)
        # Note: RMD is handled separately as it's mandatory
        new_balances, transactions, rebal_dl = rebalance_accounts(
            balances=balances_with_ss,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=aca_premium,
            medical_costs=0.0
        )
        
        # Apply RMD (mandatory distribution from Traditional to Brokerage)
        if rmd_amount > 0:
            new_balances = PortfolioBalances(
                cash=new_balances.cash,
                taxable=new_balances.taxable + rmd_amount,
                traditional=new_balances.traditional - rmd_amount,
                roth=new_balances.roth,
                daf=new_balances.daf
            )
            logger.info(f"Year {year}: RMD ${rmd_amount:,.0f} distributed to Brokerage")
        
        # Apply growth
        growth_rate = kwargs.get('growth_rate', 1.07)
        new_balances = PortfolioBalances(
            cash=new_balances.cash,
            taxable=new_balances.taxable * growth_rate,
            traditional=new_balances.traditional * growth_rate,
            roth=new_balances.roth * growth_rate,
            daf=new_balances.daf
        )
        
        # Calculate MAGI for this year
        trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage'] + rmd_amount
        magi = (ss_benefits * TAXABLE_SS_RATE +
                trad_withdrawal +
                roth_conversion +
                ltcg_harvested)
        
        # --- Decision log for Stage 6 ---
        dl = DecisionLog()

        # RMD decision
        dl.add(
            "rmd_decisions",
            "Required Minimum Distribution",
            f"${rmd_amount:,.0f} distributed from Traditional to Brokerage",
            f"RMD is mandatory at age {age_primary}. "
            f"The divisor for this age is {rmd_rate:.1f}, giving RMD = "
            f"${balances.traditional:,.0f} / {rmd_rate:.1f} = ${rmd_amount:,.0f}.",
            age_primary=age_primary,
            traditional_balance=f"${balances.traditional:,.0f}",
            rmd_divisor=f"{rmd_rate:.1f}",
            rmd_amount=f"${rmd_amount:,.0f}",
        )

        # SS income / taxation
        dl.add(
            "ss_decisions",
            "Social Security Income",
            f"${ss_benefits:,.0f}/yr (${taxable_ss:,.0f} taxable at {TAXABLE_SS_RATE:.0%})",
            f"Up to {TAXABLE_SS_RATE:.0%} of SS benefits are included in taxable income. "
            "Combined with the RMD, this determines the effective tax bracket.",
            ss_benefits=f"${ss_benefits:,.0f}",
            taxable_ss=f"${taxable_ss:,.0f}",
        )

        # IRMAA assessment
        people_on_medicare_s6 = sum([age_primary >= MEDICARE_AGE, age_spouse >= MEDICARE_AGE])
        dl.add(
            "irmaa_decisions",
            "IRMAA Assessment",
            f"${irmaa_penalty:,.0f} penalty ({people_on_medicare_s6} person(s) on Medicare)",
            "IRMAA is based on MAGI from 2 years prior. "
            "Any additional Roth conversion is capped at the IRMAA headroom.",
            prior_magi=f"${prior_magi:,.0f}",
            people_on_medicare=people_on_medicare_s6,
        )

        # LTCG harvest decision
        dl.add(
            "ltcg_decisions",
            "LTCG Harvest",
            f"Harvested ${ltcg_harvested:,.0f} from brokerage",
            "In the RMD stage, LTCG is harvested up to the 15% bracket limit "
            "(not the 0% limit) since RMD income already occupies the lower brackets.",
            ltcg_harvested=f"${ltcg_harvested:,.0f}",
        )

        # Roth conversion decision (limited by RMD)
        if roth_conversion > 0:
            dl.add(
                "roth_conversion",
                "Roth Conversion",
                f"Convert ${roth_conversion:,.0f} (conservative, RMD-limited)",
                "A small conversion was possible after the RMD filled the lower brackets. "
                "Only 50% of the available room is used to stay conservative.",
                conversion_room=f"${roth_conversion / 0.5:,.0f}" if roth_conversion > 0 else "N/A",
                conversion_executed=f"${roth_conversion:,.0f}",
            )
        else:
            dl.add(
                "roth_conversion",
                "Roth Conversion",
                "No conversion",
                "The RMD plus SS income filled the target tax bracket, "
                "leaving no room for an additional Roth conversion.",
                rmd_amount=f"${rmd_amount:,.0f}",
                taxable_ss=f"${taxable_ss:,.0f}",
            )

        # ACA premium
        dl.add(
            "aca_decisions",
            "ACA Premium",
            f"${aca_premium:,.0f}/yr" if aca_premium > 0 else "No ACA premium",
            "ACA premium applies if either person is under 65 and not yet on Medicare.",
            aca_premium=f"${aca_premium:,.0f}",
        )

        # Merge rebalancing decisions
        for entry in rebal_dl.all_decisions():
            getattr(dl, _category_for(entry)).append(entry)

        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=ss_benefits,
            rmd_amount=rmd_amount,
            traditional_withdrawal=trad_withdrawal,
            taxable_withdrawal=transactions['brokerage_to_cash'],
            roth_withdrawal=transactions['roth_to_cash'] + transactions['roth_to_brokerage'],
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            agi=agi,
            magi=magi,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=aca_premium,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'] + rmd_amount,
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed'],
            decision_log=dl,
        )


class WithdrawalStrategyEngine:
    """
    Main engine for calculating withdrawal strategy across all life stages
    """
    
    def __init__(self):
        self.stages = [
            Stage1Accumulation(),
            Stage2PrepForRetirement(),
            Stage3EarlyRetirement(),
            Stage4Medicare(),
            Stage5SocialSecurity(),
            Stage6RMD()
        ]
        logger.info("Withdrawal Strategy Engine initialized with 6 life stages")
    
    def determine_stage(self, age_primary: int, age_spouse: int, year: int,
                       has_wages: bool, has_ss: bool) -> LifeStage:
        """Determine which life stage applies"""
        for stage in self.stages:
            if stage.applies(age_primary, age_spouse, year, has_wages, has_ss):
                logger.debug(f"Year {year}: {stage.name}")
                return stage
        
        # Default to Stage 5 if nothing else applies
        return self.stages[-1]
    
    def calculate_multi_year_strategy(self, start_year: int, end_year: int,
                                     initial_balances: PortfolioBalances,
                                     initial_expenses: float,
                                     person1_name: Optional[str] = None,
                                     person2_name: Optional[str] = None,
                                     **kwargs) -> pd.DataFrame:
        """
        Calculate withdrawal strategy for multiple years
        
        Args:
            start_year: Starting year
            end_year: Ending year (inclusive)
            initial_balances: Starting portfolio balances
            initial_expenses: Initial annual expenses
            person1_name: Name of person 1 (defaults to config value)
            person2_name: Name of person 2 (defaults to config value)
            initial_balances: Starting portfolio balances
            initial_expenses: Starting annual expenses
            person1_name: Name of primary person
            person2_name: Name of spouse
            **kwargs: Additional parameters (growth_rate, expense_inflation_rate, etc.)
        
        Returns:
            DataFrame with yearly strategies
        """
        logger.info(f"Calculating strategy from {start_year} to {end_year}")
        
        # Get person names from config if not provided
        if person1_name is None or person2_name is None:
            config_mgr = get_config_manager()
            if person1_name is None:
                person1_name = config_mgr.get("personal_info", "person1_name", "Person1")
            if person2_name is None:
                person2_name = config_mgr.get("personal_info", "person2_name", "Person2")
        
        logger.info(f"Using person names: {person1_name}, {person2_name}")
        
        results = []
        balances = initial_balances
        expenses = initial_expenses

        # Get parameters
        growth_rate = kwargs.get('growth_rate', 1.07)
        expense_inflation_rate = kwargs.get('expense_inflation_rate', 0.03)  # 3% inflation rate
        spending_decrease_rate = 0.01  # 1% annual decrease in spending
        ss_claiming_age = kwargs.get('ss_claiming_age', 67)
        
        # Track MAGI for IRMAA (2-year lookback)
        magi_history = {}
        
        for year in range(start_year, end_year + 1):
            # Get ages from config (calculate from birth year)
            config_mgr = get_config_manager()
            person1_birth_date = config_mgr.get("personal_info", "person1_birth_date", "1965-01-01")
            person1_birth_year = int(person1_birth_date.split('-')[0])
            age_primary = year - person1_birth_year
            
            person2_birth_date = config_mgr.get("personal_info", "person2_birth_date", "1967-01-01")
            person2_birth_year = int(person2_birth_date.split('-')[0])
            age_spouse = year - person2_birth_year
            
            # Calculate retirement years for both people
            config_mgr = get_config_manager()
            person1_retirement_age = config_mgr.get("personal_info", "person1_retirement_age", 67)
            person2_retirement_age = config_mgr.get("personal_info", "person2_retirement_age", 62)
            person1_retirement_year = person1_birth_year + person1_retirement_age
            person2_retirement_year = person2_birth_year + person2_retirement_age
            
            # Calculate wages from config - check each person's retirement status individually
            wages = 0
            person1_wages_this_year = 0
            person2_wages_this_year = 0
            
            person1_base_wages = config_mgr.get("income", "person1_annual_wages", 0)
            person2_base_wages = config_mgr.get("income", "person2_annual_wages", 0)
            wage_inflation_rate = config_mgr.get("income", "wage_inflation_rate", 3.0) / 100.0
            
            # Apply wage inflation from start_year to current year
            years_elapsed = year - start_year
            inflation_multiplier = (1 + wage_inflation_rate) ** years_elapsed
            
            # Check if person1 is still working (before their retirement year)
            if year < person1_retirement_year and person1_base_wages > 0:
                person1_wages_this_year = person1_base_wages * inflation_multiplier
            
            # Check if person2 is still working (before their retirement year)
            if year < person2_retirement_year and person2_base_wages > 0:
                person2_wages_this_year = person2_base_wages * inflation_multiplier
            
            # Total household wages
            wages = person1_wages_this_year + person2_wages_this_year
            
            if wages > 0:
                logger.info(f"Year {year} Wages: Person1=${person1_wages_this_year:,.2f} "
                          f"({'working' if person1_wages_this_year > 0 else 'retired'}), "
                          f"Person2=${person2_wages_this_year:,.2f} "
                          f"({'working' if person2_wages_this_year > 0 else 'retired'}), "
                          f"Total=${wages:,.2f} (inflation factor: {inflation_multiplier:.4f})")
            
            has_wages = wages > 0
            
            # Get SS benefits using dynamic calculator
            # Check each person's individual claiming age from config
            ss_benefits = 0
            try:
                # Get config for SSI settings
                config_mgr = get_config_manager()
                
                # Person 1 SSI calculation
                person1_birth_date = config_mgr.get("personal_info", "person1_birth_date", "1965-01-01")
                person1_birth_year = int(person1_birth_date.split('-')[0])
                person1_claiming_age = config_mgr.get("social_security", "person1_ssi_age", 70)
                person1_fra_benefit = config_mgr.get("social_security", "person1_ssi_amount", 0)
                
                ss_primary = 0
                if person1_fra_benefit > 0 and age_primary >= person1_claiming_age:
                    ss_primary = calculate_ssi_benefits_dynamic(
                        year=year,
                        person_name=person1_name or "Person 1",
                        birth_year=person1_birth_year,
                        claiming_age=person1_claiming_age,
                        fra_benefit=person1_fra_benefit,
                        cola_rate=kwargs.get('cola_rate', DEFAULT_COLA_RATE)
                    )
                
                # Person 2 SSI calculation
                person2_birth_date = config_mgr.get("personal_info", "person2_birth_date", "1967-01-01")
                person2_birth_year = int(person2_birth_date.split('-')[0])
                person2_claiming_age = config_mgr.get("social_security", "person2_ssi_age", 70)
                person2_fra_benefit = config_mgr.get("social_security", "person2_ssi_amount", 0)
                
                ss_spouse = 0
                if person2_fra_benefit > 0 and age_spouse >= person2_claiming_age:
                    ss_spouse = calculate_ssi_benefits_dynamic(
                        year=year,
                        person_name=person2_name or "Person 2",
                        birth_year=person2_birth_year,
                        claiming_age=person2_claiming_age,
                        fra_benefit=person2_fra_benefit,
                        cola_rate=kwargs.get('cola_rate', DEFAULT_COLA_RATE)
                    )
                
                # Convert monthly to annual and combine both persons
                ss_benefits = (ss_primary + ss_spouse) * 12
                
                # Log individual and combined benefits
                if ss_primary > 0 or ss_spouse > 0:
                    logger.info(f"Year {year} SSI Benefits: "
                              f"{person1_name or 'Person 1'}=${ss_primary:,.2f}/mo (age {age_primary}), "
                              f"{person2_name or 'Person 2'}=${ss_spouse:,.2f}/mo (age {age_spouse}), "
                              f"Combined Annual=${ss_benefits:,.2f}")
                
            except Exception as e:
                logger.warning(f"Could not calculate dynamic SS benefits for {year}: {e}")
                # Fallback: use zero if dynamic calculation fails
                ss_benefits = 0
                logger.warning(f"SSI calculation failed, using $0 for year {year}")
                try:
                    # Optional: Try CSV-based method as last resort
                    # Get claiming ages from config for fallback
                    config_mgr = get_config_manager()
                    person1_claiming_age = config_mgr.get("social_security", "person1_ssi_age", 70)
                    person2_claiming_age = config_mgr.get("social_security", "person2_ssi_age", 70)
                    
                    ss_primary = get_monthly_benefit(year, person1_name) if age_primary >= person1_claiming_age else 0
                    ss_spouse = get_monthly_benefit(year, person2_name) if age_spouse >= person2_claiming_age else 0
                    if ss_primary > 0 or ss_spouse > 0:
                        ss_benefits = (ss_primary + ss_spouse) * 12
                        logger.info(f"Using CSV fallback for SSI: ${ss_benefits:,.2f}")
                except Exception as e2:
                    logger.error(f"Both dynamic and CSV SSI calculation failed: {e2}")
            
            # Determine if has_ss for stage determination
            has_ss = ss_benefits > 0
            
            # Get prior MAGI for IRMAA
            prior_magi = magi_history.get(year - 2, 0)
            
            # Log starting balances for this year
            logger.info(f"=== Year {year} Starting Balances ===")
            logger.info(f"  Cash: ${balances.cash:,.2f}")
            logger.info(f"  Taxable: ${balances.taxable:,.2f}")
            logger.info(f"  Traditional: ${balances.traditional:,.2f}")
            logger.info(f"  Roth: ${balances.roth:,.2f}")
            logger.info(f"  Total: ${balances.total():,.2f}")
            logger.info(f"  Expenses for year: ${expenses:,.2f}")
            
            # Determine stage
            stage = self.determine_stage(age_primary, age_spouse, year, has_wages, has_ss)
            
            # Calculate strategy (add start_year for buffer ramp-up calculation)
            strategy = stage.calculate_strategy(
                year=year,
                balances=balances,
                expenses=expenses,
                wages=wages,
                age_primary=age_primary,
                age_spouse=age_spouse,
                ss_benefits=ss_benefits,
                prior_magi=prior_magi,
                start_year=start_year,
                **kwargs
            )
            
            # Log ending balances for this year
            logger.info(f"=== Year {year} Ending Balances (after strategy) ===")
            logger.info(f"  Cash: ${strategy.balances.cash:,.2f}")
            logger.info(f"  Taxable: ${strategy.balances.taxable:,.2f}")
            logger.info(f"  Traditional: ${strategy.balances.traditional:,.2f}")
            logger.info(f"  Roth: ${strategy.balances.roth:,.2f}")
            logger.info(f"  Total: ${strategy.balances.total():,.2f}")
            
            # Store MAGI for future IRMAA calculations
            current_magi = (strategy.ss_benefits * TAXABLE_SS_RATE + 
                          strategy.traditional_withdrawal + 
                          strategy.roth_conversion + 
                          strategy.ltcg_harvested)
            magi_history[year] = current_magi
            
            # Update for next year
            balances = strategy.balances
            # Apply 1% spending decrease, then inflation: expenses × 0.99 × (1 + inflation_rate)
            expenses = expenses * (1 - spending_decrease_rate) * (1 + expense_inflation_rate)
            
            # Store result
            results.append(strategy)
            
            logger.debug(f"Year {year} complete: Stage={stage.name}, "
                        f"Total balance=${balances.total():,.2f}")
        
        # Apply RMD lookback optimization
        logger.info("=" * 80)
        logger.info("APPLYING RMD LOOKBACK OPTIMIZATION")
        logger.info("=" * 80)
        logger.info(f"Total years in initial strategy: {len(results)}")
        
        # Log a few sample years before optimization
        for i, s in enumerate(results[:3]):
            logger.info(f"Before optimization - Year {s.year}:")
            logger.info(f"  Traditional: ${s.balances.traditional:,.2f}")
            logger.info(f"  Roth: ${s.balances.roth:,.2f}")
            logger.info(f"  Roth Conversion: ${s.roth_conversion:,.2f}")
        
        optimized_results, optimization_report = optimize_rmd_lookback(
            results,
            initial_balances,
            kwargs.get('max_conversion_rate', 0.24),
            growth_rate
        )
        
        # Log optimization results
        logger.info("=" * 80)
        if optimization_report.get('status') == 'Optimization complete':
            logger.info(f"RMD Lookback Optimization Report:")
            logger.info(f"  RMD years analyzed: {optimization_report['rmd_years_analyzed']}")
            logger.info(f"  Years adjusted: {optimization_report['years_adjusted']}")
            logger.info(f"  Total additional conversions: ${optimization_report['total_additional_conversions']:,.2f}")
            logger.info(f"  Estimated RMD reduction: ${optimization_report['estimated_rmd_reduction']:,.2f}")
            if optimization_report['years_adjusted'] > 0:
                logger.info(f"  Average per adjusted year: ${optimization_report['avg_additional_per_adjusted_year']:,.2f}")
        else:
            logger.info(f"  {optimization_report.get('status', 'No optimization needed')}")
        
        # Log a few sample years after optimization
        logger.info("=" * 80)
        logger.info("AFTER OPTIMIZATION - Sample Years:")
        for i, s in enumerate(optimized_results[:3]):
            logger.info(f"After optimization - Year {s.year}:")
            logger.info(f"  Traditional: ${s.balances.traditional:,.2f}")
            logger.info(f"  Roth: ${s.balances.roth:,.2f}")
            logger.info(f"  Roth Conversion: ${s.roth_conversion:,.2f}")
        logger.info("=" * 80)
        
        # Convert to DataFrame
        return self._strategies_to_dataframe(optimized_results)
    
    def _strategies_to_dataframe(self, strategies: list) -> pd.DataFrame:
        """Convert list of YearlyStrategy objects to DataFrame with account movements"""
        data = []
        for s in strategies:
            data.append({
                'Year': s.year,
                'Age': f"{s.age_primary}/{s.age_spouse}",
                'Stage': s.stage,
                # Income sources (in requested order)
                'Wages': s.wages,
                'SS Benefits': s.ss_benefits,
                'Traditional Withdrawal': s.traditional_withdrawal,
                'Roth Conversion': s.roth_conversion,
                # Expenses and costs
                'Expenses': s.expenses,
                'Healthcare Cost': s.irmaa_penalty + s.aca_premium,
                'IRMAA Penalty': s.irmaa_penalty,
                'ACA Premium': s.aca_premium,
                'DAF Contribution': s.daf_contribution,
                'AGI': s.agi,
                'MAGI': s.magi,
                'Federal Tax': s.federal_tax,
                'Cash Balance': s.balances.cash,
                # Additional withdrawal details
                'RMD': s.rmd_amount,
                'Taxable Withdrawal': s.taxable_withdrawal,
                'Roth Withdrawal': s.roth_withdrawal,
                'LTCG Harvested': s.ltcg_harvested,
                # Account movements (fund transfers between accounts) - using shorter names with line breaks
                'Trad→\nCash': s.traditional_to_cash,
                'Trad→\nBrok': s.traditional_to_brokerage,
                'Trad→\nRoth': s.conversion_executed,
                'Brok→\nCash': s.brokerage_to_cash,
                'Roth→\nCash': s.roth_to_cash,
                'Roth→\nBrok': s.roth_to_brokerage,
                'Cash\nReplen': s.cash_replenishment,
                'Brok\nReplen': s.brokerage_replenishment,
                # Accumulation-phase contributions (non-zero only in Stage 1 & 2)
                'Wages→\nPayroll': s.payroll_tax,
                'Wages→\nTrad': s.wages_to_trad,
                'Wages→\nRoth': s.wages_to_roth,
                'Cash→\nRoth': s.cash_to_roth,
                'Cash→\nBrok': s.cash_to_brokerage,
                # Account balances
                'Taxable Balance': s.balances.taxable,
                'Traditional Balance': s.balances.traditional,
                'Roth Balance': s.balances.roth,
                'DAF Balance': s.balances.daf,
                'Total Portfolio': s.balances.total(),
                'Decision Log': s.decision_log,
            })
        
        return pd.DataFrame(data)


def build_withdrawal_strategy_display(start_year: Optional[int] = None,
                                      end_year: Optional[int] = None,
                                      **kwargs) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build withdrawal strategy display for 3 years by default
    
    Args:
        start_year: Starting year (defaults to current year)
        end_year: Ending year (defaults to start_year + 2, for 3-year forecast)
        **kwargs: Additional parameters
    
    Returns:
        Tuple of (strategy_df, balances_df)
    """
    if start_year is None:
        start_year = datetime.now().year
    
    if end_year is None:
        end_year = start_year + 2  # 3-year forecast by default
    
    logger.info(f"Building withdrawal strategy display: {start_year}-{end_year}")
    
    # Get initial balances from current portfolio
    try:
        current_month = datetime.now().month
        detailed_df, summary_df = get_networth_by_month(current_month, start_year)
       
        if summary_df.empty:
            logger.warning("No portfolio data found, using default values")
            initial_balances = PortfolioBalances(
                cash=50000,
                taxable=200000,
                traditional=600000,
                roth=150000,
                daf=0
            )
        else:
            cash_balance = float(summary_df[summary_df['account_type'] == 'Cash']['market_value'].sum())
            taxable_balance = float(summary_df[summary_df['account_type'] == 'Brokerage']['market_value'].sum())
            traditional_balance = float(summary_df[summary_df['account_type'] == 'Traditional']['market_value'].sum())
            roth_balance = float(summary_df[summary_df['account_type'] == 'Roth']['market_value'].sum())
            daf_balance = 0
            
            logger.info(f"Initial account balances loaded:")
            logger.info(f"  Cash: ${cash_balance:,.2f}")
            logger.info(f"  Taxable (Brokerage): ${taxable_balance:,.2f}")
            logger.info(f"  Traditional: ${traditional_balance:,.2f}")
            logger.info(f"  Roth: ${roth_balance:,.2f}")
            logger.info(f"  DAF: ${daf_balance:,.2f}")
            logger.info(f"  Total: ${cash_balance + taxable_balance + traditional_balance + roth_balance + daf_balance:,.2f}")
            
            initial_balances = PortfolioBalances(
                cash=cash_balance,
                taxable=taxable_balance,
                traditional=traditional_balance,
                roth=roth_balance,
                daf=daf_balance
            )
    except Exception as e:
        logger.error(f"Error loading portfolio data: {e}")
        initial_balances = PortfolioBalances(
            cash=50000,
            taxable=200000,
            traditional=600000,
            roth=150000,
            daf=0
        )
    # Log first 4 years of data at INFO level for planning_app.py visibility
    # Get initial expenses from session state or use default
    # Get initial expenses from session state or fall back to config
    from config import get_value_with_session_override
    try:
        initial_expenses = float(get_value_with_session_override('financial_assumptions', 'expected_annual_expenses', 'EXPENSE', kwargs.get('initial_expenses', 120000)))
    except (ImportError, AttributeError, KeyError) as e:
        logger.debug(f'Using default expenses (Streamlit not available): {e}')
        initial_expenses = kwargs.get('initial_expenses', 120000)
    
    # Remove initial_balances and initial_expenses from kwargs to avoid duplicate arguments
    kwargs_filtered = {k: v for k, v in kwargs.items() if k not in ['initial_balances', 'initial_expenses']}
    
    # Create engine and calculate
    engine = WithdrawalStrategyEngine()
    strategy_df = engine.calculate_multi_year_strategy(
        start_year=start_year,
        end_year=end_year,
        initial_balances=initial_balances,
        initial_expenses=initial_expenses,
        **kwargs_filtered
    )
    
    # Create balances DataFrame
    balances_df = strategy_df[[
        'Year', 'Cash Balance', 'Taxable Balance',
        'Traditional Balance', 'Roth Balance', 'DAF Balance', 'Total Portfolio'
    ]].copy()

    # Log first 4 years of data at INFO level for planning_app.py visibility
    logger.info("=" * 80)
    logger.info("WITHDRAWAL STRATEGY - First 4 Years Preview")
    logger.info("=" * 80)
    
    if len(strategy_df) > 0:
        preview_rows = min(4, len(strategy_df))
        logger.info(f"\nStrategy DataFrame (first {preview_rows} years):")
        logger.info("-" * 80)
        
        # Display key columns for strategy
        key_cols = ['Year', 'Age', 'Stage', 'Wages', 'SS Benefits', 'RMD',
                   'Traditional Withdrawal', 'Roth Conversion', 'Expenses',
                   'IRMAA Penalty', 'Federal Tax', 'Cash Balance']
        available_key_cols = [col for col in key_cols if col in strategy_df.columns]
        
        for idx in range(preview_rows):
            row = strategy_df.iloc[idx]
            logger.info(f"\nYear {int(row['Year'])} (Age {row.get('Age', 'N/A')}) - {row.get('Stage', 'N/A')}")
            for col in available_key_cols[3:]:  # Skip Year, Age, Stage (already shown)
                if col in row:
                    val = row[col]
                    if pd.notna(val) and val != 0:
                        logger.info(f"  {col:25s}: ${val:>12,.2f}")
        
        logger.info("\n" + "-" * 80)
        logger.info(f"\nBalances DataFrame (first {preview_rows} years):")
        logger.info("-" * 80)
        
        for idx in range(preview_rows):
            row = balances_df.iloc[idx]
            logger.info(f"\nYear {int(row['Year'])}:")
            logger.info(f"  {'Cash Balance':25s}: ${row['Cash Balance']:>12,.2f}")
            logger.info(f"  {'Taxable Balance':25s}: ${row['Taxable Balance']:>12,.2f}")
            logger.info(f"  {'Traditional Balance':25s}: ${row['Traditional Balance']:>12,.2f}")
            logger.info(f"  {'Roth Balance':25s}: ${row['Roth Balance']:>12,.2f}")
            logger.info(f"  {'DAF Balance':25s}: ${row['DAF Balance']:>12,.2f}")
            logger.info(f"  {'Total Portfolio':25s}: ${row['Total Portfolio']:>12,.2f}")
    
    logger.info("\n" + "=" * 80)
    logger.info(f"Total years calculated: {len(strategy_df)}")
    logger.info("=" * 80)
    
    return strategy_df, cast(pd.DataFrame, balances_df)


def build_accumulation_strategy_display(start_year: Optional[int] = None,
                                        end_year: Optional[int] = None,
                                        **kwargs) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build accumulation (pre-retirement) strategy display.

    Runs the same WithdrawalStrategyEngine as the withdrawal display but scopes
    the projection to the years *before* the earliest retirement date so only
    Stage 1 (Accumulation) and Stage 2 (Prep for Retirement) rows appear.

    Args:
        start_year: Starting year (defaults to current year).
        end_year:   Ending year (defaults to the year before the earliest
                    retirement date, or start_year + 10 if config unavailable).
        **kwargs:   Forwarded to the engine (growth_rate, expense_inflation_rate, …).

    Returns:
        Tuple of (strategy_df, balances_df) — same column schema as
        build_withdrawal_strategy_display().
    """
    if start_year is None:
        start_year = datetime.now().year

    if end_year is None:
        try:
            config_mgr = get_config_manager()
            p1_birth_year = int(config_mgr.get("personal_info", "person1_birth_date", "1965-01-01").split('-')[0])
            p1_ret_age = config_mgr.get("personal_info", "person1_retirement_age", 67)
            p2_birth_year = int(config_mgr.get("personal_info", "person2_birth_date", "1967-01-01").split('-')[0])
            p2_ret_age = config_mgr.get("personal_info", "person2_retirement_age", 62)
            earliest_retirement = min(p1_birth_year + p1_ret_age, p2_birth_year + p2_ret_age)
            # Project up to (but not including) the retirement year
            end_year = max(start_year, earliest_retirement - 1)
        except Exception:
            end_year = start_year + 10

    logger.info(f"Building accumulation strategy display: {start_year}-{end_year}")

    # Load current portfolio balances (same logic as withdrawal display)
    try:
        current_month = datetime.now().month
        detailed_df, summary_df = get_networth_by_month(current_month, start_year)

        if summary_df.empty:
            logger.warning("No portfolio data found for accumulation display, using defaults")
            initial_balances = PortfolioBalances(
                cash=50_000, taxable=200_000, traditional=300_000, roth=100_000, daf=0
            )
        else:
            initial_balances = PortfolioBalances(
                cash=float(summary_df[summary_df['account_type'] == 'Cash']['market_value'].sum()),
                taxable=float(summary_df[summary_df['account_type'] == 'Brokerage']['market_value'].sum()),
                traditional=float(summary_df[summary_df['account_type'] == 'Traditional']['market_value'].sum()),
                roth=float(summary_df[summary_df['account_type'] == 'Roth']['market_value'].sum()),
                daf=0
            )
    except Exception as e:
        logger.error(f"Error loading portfolio data for accumulation display: {e}")
        initial_balances = PortfolioBalances(
            cash=50_000, taxable=200_000, traditional=300_000, roth=100_000, daf=0
        )

    # Load initial expenses
    from config import get_value_with_session_override
    try:
        initial_expenses = float(get_value_with_session_override(
            'financial_assumptions', 'expected_annual_expenses', 'EXPENSE',
            kwargs.get('initial_expenses', 120_000)
        ))
    except (ImportError, AttributeError, KeyError) as e:
        logger.debug(f"Using default expenses for accumulation display: {e}")
        initial_expenses = kwargs.get('initial_expenses', 120_000)

    kwargs_filtered = {k: v for k, v in kwargs.items() if k not in ['initial_balances', 'initial_expenses']}

    engine = WithdrawalStrategyEngine()
    strategy_df = engine.calculate_multi_year_strategy(
        start_year=start_year,
        end_year=end_year,
        initial_balances=initial_balances,
        initial_expenses=initial_expenses,
        **kwargs_filtered
    )

    # Filter to accumulation stages only (belt-and-suspenders guard)
    accum_stages = {"Stage 1: Accumulation", "Stage 2: Prep for Retirement"}
    if not strategy_df.empty and 'Stage' in strategy_df.columns:
        strategy_df = strategy_df[strategy_df['Stage'].isin(list(accum_stages))].reset_index(drop=True)

    balances_df = strategy_df[[
        'Year', 'Cash Balance', 'Taxable Balance',
        'Traditional Balance', 'Roth Balance', 'DAF Balance', 'Total Portfolio'
    ]].copy()

    logger.info(f"Accumulation strategy: {len(strategy_df)} years calculated")

    return cast(pd.DataFrame, strategy_df), cast(pd.DataFrame, balances_df)


def calculate_aca_subsidy(magi: float, year: int, household_size: int = 2) -> Tuple[float, float]:
    """
    Calculate ACA marketplace subsidy based on MAGI and Federal Poverty Level
    
    Args:
        magi: Modified Adjusted Gross Income
        year: Tax year
        household_size: Number in household (default 2)
    
    Returns:
        Tuple of (subsidy_amount, net_premium)
    """
    # Federal Poverty Level (approximate, adjust annually)
    fpl_2026 = 20440 + (7320 * (household_size - 1))  # Base + per additional person
    
    # Calculate % of FPL
    fpl_percentage = (magi / fpl_2026) * 100
    
    # Benchmark premium (Silver plan, approximate)
    benchmark_premium = 12000  # Annual premium for 2 people
    
    # Premium cap based on FPL percentage (2024 ACA rules)
    if fpl_percentage <= 150:
        premium_cap_pct = 0.0  # Free
    elif fpl_percentage <= 200:
        premium_cap_pct = 0.02
    elif fpl_percentage <= 250:
        premium_cap_pct = 0.04
    elif fpl_percentage <= 300:
        premium_cap_pct = 0.06
    elif fpl_percentage <= 400:
        premium_cap_pct = 0.085
    else:
        premium_cap_pct = 1.0  # No subsidy
    
    # Calculate subsidy
    max_premium = magi * premium_cap_pct
    subsidy = max(0, benchmark_premium - max_premium)
    net_premium = benchmark_premium - subsidy
    
    logger.debug(f"ACA: MAGI=${magi:,.0f}, FPL%={fpl_percentage:.0f}%, "
                f"Subsidy=${subsidy:,.0f}, Net=${net_premium:,.0f}")
    
    return subsidy, net_premium


# Default configuration shared across all scenarios.
# Wrapped in MappingProxyType to prevent accidental mutation; the dict-unpack
# syntax ({**_DEFAULT_SCENARIO_CONFIG, **overrides}) works identically.
_DEFAULT_SCENARIO_CONFIG: types.MappingProxyType = types.MappingProxyType({
    "start_year": 2026,
    "end_year": 2050,
    "person1_name": "Tom",
    "person2_name": "Sarah",
    "growth_rate": 1.07,
    "expense_inflation": 1.02,
    "ss_claiming_age": 67,
    "retirement_year": 2026,
    "has_wages": False
})


# Scenario-specific configuration overrides
# Each scenario overrides specific values from _DEFAULT_SCENARIO_CONFIG
_SCENARIO_OVERRIDES = {
    ScenarioType.DEFAULT: {
        # Default retirement scenario with moderate portfolio
        # Features:
        # - Moderate portfolio size (~$1.1M total)
        # - Standard retirement age (67)
        # - Deflation scenario (0.993 expense inflation)
        "initial_balances": PortfolioBalances(
            cash=55000,
            taxable=225000,
            traditional=670000,
            roth=168000,
            daf=0
        ),
        "initial_expenses": 120000,
        "expense_inflation": 0.993,  # Override base: deflation scenario
    },
    ScenarioType.EARLY_RETIRE: {
        # Early retirement scenario with larger portfolio and delayed Social Security
        # Features:
        # - Larger portfolio (~$1.75M total)
        # - Delayed SS claiming to age 70 for higher benefits
        # - Includes DAF for charitable giving
        "initial_balances": PortfolioBalances(
            cash=100000,
            taxable=400000,
            traditional=1000000,
            roth=200000,
            daf=50000
        ),
        "initial_expenses": 100000,
        "ss_claiming_age": 70,  # Delay SS for higher benefits
    },
    ScenarioType.HIGH_INCOME: {
        # High income scenario with large portfolio and higher growth assumptions
        # Features:
        # - Large portfolio (~$3.8M total)
        # - Higher growth rate (8% vs 7%)
        # - Higher expense inflation (2.5% vs 2%)
        # - Substantial DAF for charitable giving
        "initial_balances": PortfolioBalances(
            cash=200000,
            taxable=1000000,
            traditional=2000000,
            roth=500000,
            daf=100000
        ),
        "initial_expenses": 200000,
        "growth_rate": 1.08,  # Override base: higher growth
        "expense_inflation": 1.025,  # Override base: higher inflation
    },
}

# Fail fast at import time if a ScenarioType member has no entry in
# _SCENARIO_OVERRIDES.  This converts a silent runtime fallback into a loud,
# early error that is caught during development and CI before it can silently
# return wrong data in production.
_missing = set(ScenarioType) - set(_SCENARIO_OVERRIDES)
if _missing:
    raise RuntimeError(
        f"Missing _SCENARIO_OVERRIDES entries for: {_missing}"
    )


def _resolve_scenario_key(scenario_name: Union[str, ScenarioType]) -> ScenarioType:
    """Resolve a scenario name or enum member to a validated :class:`ScenarioType` key.

    Accepts either a :class:`ScenarioType` member or its string value.  Unknown
    strings fall back to :attr:`ScenarioType.DEFAULT` with a ``WARNING`` log entry.
    All :class:`ScenarioType` members are guaranteed to be present in
    :data:`_SCENARIO_OVERRIDES` by the module-level guard above.

    Args:
        scenario_name: A :class:`ScenarioType` member or its string value
            (e.g. ``"default"``, ``"early_retire"``).

    Returns:
        A :class:`ScenarioType` member guaranteed to be present in
        :data:`_SCENARIO_OVERRIDES`.
    """
    if isinstance(scenario_name, ScenarioType):
        return scenario_name
    try:
        return ScenarioType(scenario_name)
    except ValueError:
        logger.warning("Unknown scenario '%s', using default", scenario_name)
        return ScenarioType.DEFAULT


@functools.lru_cache(maxsize=None)
def _build_scenario_config(key: ScenarioType) -> ScenarioConfig:
    """Build and cache a :class:`ScenarioConfig` for a validated *key*.

    Results are cached indefinitely because both :data:`_DEFAULT_SCENARIO_CONFIG`
    and :data:`_SCENARIO_OVERRIDES` are module-level constants that never change
    at runtime.  :class:`ScenarioConfig` is ``frozen=True``, so cached instances
    are safe to share across callers without risk of mutation.

    Args:
        key: A :class:`ScenarioType` member present in :data:`_SCENARIO_OVERRIDES`.

    Returns:
        An immutable :class:`ScenarioConfig` populated from the merged base and
        scenario-specific configuration.
    """
    return ScenarioConfig(**{**_DEFAULT_SCENARIO_CONFIG, **_SCENARIO_OVERRIDES[key]})


def create_example_scenario(scenario_name: Union[str, ScenarioType] = "default") -> ScenarioConfig:
    """
    Create example scenarios for testing withdrawal strategies

    This function provides pre-configured retirement scenarios with different
    portfolio sizes, expense levels, and assumptions. Each scenario can be
    used to test withdrawal strategies under various conditions.

    Args:
        scenario_name: Scenario identifier. Accepts a :class:`ScenarioType` enum
            member or its string value (e.g. ``"default"``, ``"early_retire"``,
            ``"high_income"``). Prefer the enum form for type safety. Unknown
            strings fall back to ``ScenarioType.DEFAULT`` with a warning.

    Returns:
        ScenarioConfig: Fully populated scenario configuration.
        See ``ScenarioConfig`` for field descriptions.

    Note:
        Results are cached via :func:`_build_scenario_config`; repeated calls
        with the same argument are O(1) after the first call.

    Example:
        >>> scenario = create_example_scenario(ScenarioType.DEFAULT)
        >>> scenario = create_example_scenario(ScenarioType.EARLY_RETIRE)
        >>> scenario = create_example_scenario("high_income")  # string form also accepted
        >>> config_dict = scenario.to_dict()  # Convert to dict if needed
    """
    return _build_scenario_config(_resolve_scenario_key(scenario_name))


def generate_strategy_summary(strategy_df: pd.DataFrame) -> Dict:
    """
    Generate summary statistics from withdrawal strategy
    
    Args:
        strategy_df: DataFrame from calculate_multi_year_strategy
    
    Returns:
        Dictionary with summary statistics
    """
    summary = {
        "total_years": len(strategy_df),
        "stages": strategy_df['Stage'].value_counts().to_dict(),
        "total_roth_conversions": strategy_df['Roth Conversion'].sum(),
        "total_taxes_paid": strategy_df['Federal Tax'].sum(),
        "total_irmaa_penalties": strategy_df['IRMAA Penalty'].sum(),
        "avg_annual_expenses": strategy_df['Expenses'].mean(),
        "final_portfolio_value": strategy_df['Total Portfolio'].iloc[-1],
        "initial_portfolio_value": strategy_df['Total Portfolio'].iloc[0],
        "portfolio_growth": strategy_df['Total Portfolio'].iloc[-1] - strategy_df['Total Portfolio'].iloc[0],
        "years_with_conversions": (strategy_df['Roth Conversion'] > 0).sum(),
        "max_conversion_year": strategy_df.loc[strategy_df['Roth Conversion'].idxmax(), 'Year'] if strategy_df['Roth Conversion'].max() > 0 else None,
        "max_conversion_amount": strategy_df['Roth Conversion'].max(),
        "total_ss_benefits": strategy_df['SS Benefits'].sum(),
        "total_rmd": strategy_df['RMD'].sum(),
        "roth_percentage_final": (strategy_df['Roth Balance'].iloc[-1] / strategy_df['Total Portfolio'].iloc[-1] * 100) if strategy_df['Total Portfolio'].iloc[-1] > 0 else 0
    }
    
    return summary


def _format_currency(value: float) -> str:
    """Format currency values consistently"""
    return f"${value:,.0f}"


def _format_percentage(value: float) -> str:
    """Format percentage values consistently"""
    return f"{value:.1f}%"


def _build_overview_section(summary: Dict) -> List[str]:
    """Build overview section lines"""
    return [
        "\n📊 OVERVIEW",
        f"   Years Analyzed: {summary['total_years']}",
        f"   Initial Portfolio: {_format_currency(summary['initial_portfolio_value'])}",
        f"   Final Portfolio: {_format_currency(summary['final_portfolio_value'])}",
        f"   Portfolio Growth: {_format_currency(summary['portfolio_growth'])}"
    ]


def _build_life_stages_section(summary: Dict) -> List[str]:
    """Build life stages section lines"""
    lines = ["\n🎯 LIFE STAGES"]
    for stage, years in summary['stages'].items():
        lines.append(f"   {stage}: {years} years")
    return lines


def _build_roth_conversion_section(summary: Dict) -> List[str]:
    """Build Roth conversion section lines"""
    lines = [
        "\n💰 ROTH CONVERSION STRATEGY",
        f"   Total Conversions: {_format_currency(summary['total_roth_conversions'])}",
        f"   Years with Conversions: {summary['years_with_conversions']}"
    ]
    if summary['max_conversion_year']:
        lines.append(f"   Largest Conversion: {_format_currency(summary['max_conversion_amount'])} in {summary['max_conversion_year']}")
    lines.append(f"   Final Roth %: {_format_percentage(summary['roth_percentage_final'])}")
    return lines


def _build_taxes_costs_section(summary: Dict) -> List[str]:
    """Build taxes and costs section lines"""
    return [
        "\n💵 TAXES & COSTS",
        f"   Total Federal Taxes: {_format_currency(summary['total_taxes_paid'])}",
        f"   Total IRMAA Penalties: {_format_currency(summary['total_irmaa_penalties'])}",
        f"   Average Annual Expenses: {_format_currency(summary['avg_annual_expenses'])}"
    ]


def _build_income_sources_section(summary: Dict) -> List[str]:
    """Build income sources section lines"""
    return [
        "\n📈 INCOME SOURCES",
        f"   Total SS Benefits: {_format_currency(summary['total_ss_benefits'])}",
        f"   Total RMDs: {_format_currency(summary['total_rmd'])}"
    ]


def _build_year_summary_section(strategy_df: pd.DataFrame, first_n: int, last_n: int,
                                display_cols: Sequence[str]) -> List[str]:
    """Build year-by-year summary section lines"""
    lines = [
        "\n" + "="*80,
        f"YEAR-BY-YEAR SUMMARY (First {first_n} & Last {last_n} years)",
        "="*80,
        f"\nFirst {first_n} Years:",
        strategy_df[display_cols].head(first_n).to_string(index=False),
        f"\nLast {last_n} Years:",
        strategy_df[display_cols].tail(last_n).to_string(index=False)
    ]
    return lines


def _resolve_display_bounds(first_n: int, last_n: int, total_rows: int) -> tuple:
    """Validate and adjust first_n / last_n against the available row count.

    Args:
        first_n: Requested number of initial rows to display.
        last_n: Requested number of final rows to display.
        total_rows: Total rows available in the strategy DataFrame.

    Returns:
        Adjusted (first_n, last_n) tuple guaranteed to fit within total_rows.

    Raises:
        ValueError: If first_n or last_n are not positive integers.
    """
    if first_n < 1 or last_n < 1:
        raise ValueError("first_n and last_n must be positive integers")

    if total_rows == 0:
        return 0, 0

    if first_n + last_n > total_rows:
        logger.warning(
            f"Requested {first_n + last_n} rows but only {total_rows} available. "
            f"Adjusting to show all rows."
        )
        first_n = min(first_n, total_rows)
        last_n = min(last_n, total_rows - first_n)

    return first_n, last_n


def _report_lines(summary: Dict, strategy_df: pd.DataFrame,
                  first_n: int, last_n: int,
                  display_cols: Sequence[str]) -> Iterator[str]:
    """Yield each line of the strategy report without performing any I/O.

    Separating content construction from output makes the report content
    independently testable (``list(_report_lines(...))``) without capturing
    stdout, and avoids building an intermediate list in memory.

    Args:
        summary: Pre-calculated summary dict from generate_strategy_summary.
        strategy_df: DataFrame from calculate_multi_year_strategy.
        first_n: Number of initial years to include.
        last_n: Number of final years to include.
        display_cols: Column names to render in the year-by-year table.

    Yields:
        Individual report lines (without a trailing newline each).
    """
    yield "\n" + "=" * 80
    yield "RETIREMENT WITHDRAWAL STRATEGY REPORT"
    yield "=" * 80

    yield from _build_overview_section(summary)
    yield from _build_life_stages_section(summary)
    yield from _build_roth_conversion_section(summary)
    yield from _build_taxes_costs_section(summary)
    yield from _build_income_sources_section(summary)
    yield from _build_year_summary_section(strategy_df, first_n, last_n, display_cols)


def print_strategy_report(strategy_df: pd.DataFrame, summary: Optional[Dict] = None,
                          first_n: int = 10, last_n: int = 5,
                          display_cols: Optional[tuple] = None) -> None:
    """
    Print a formatted report of the withdrawal strategy.

    Args:
        strategy_df: DataFrame from calculate_multi_year_strategy.
        summary: Optional pre-calculated summary dict.
        first_n: Number of initial years to display (default: 10).
        last_n: Number of final years to display (default: 5).
        display_cols: Columns to display in year summary.
            Defaults to _REPORT_DEFAULT_DISPLAY_COLS.

    Raises:
        ValueError: If first_n or last_n are not positive integers.
    """
    first_n, last_n = _resolve_display_bounds(first_n, last_n, len(strategy_df))

    if summary is None:
        summary = generate_strategy_summary(strategy_df)

    if display_cols is None:
        display_cols = _REPORT_DEFAULT_DISPLAY_COLS

    print("\n".join(_report_lines(summary, strategy_df, first_n, last_n, display_cols)))
    print("\n" + "=" * 80 + "\n")


# Example usage function
def run_example():
    """
    Run an example withdrawal strategy calculation and display results
    """
    print("Running Retirement Withdrawal Strategy Example...")
    print("="*80)
    
    # Create example scenario
    scenario = create_example_scenario("default")
    
    print(f"\nScenario: Default Retirement")
    print(f"Starting Year: {scenario.start_year}")
    print(f"Ending Year: {scenario.end_year}")
    print(f"Initial Portfolio: ${scenario.initial_balances.total():,.0f}")
    print(f"Annual Expenses: ${scenario.initial_expenses:,.0f}")
    
    # Calculate strategy
    strategy_df, balances_df = build_withdrawal_strategy_display(**scenario.to_dict())
    
    # Generate and print report
    summary = generate_strategy_summary(strategy_df)
    print_strategy_report(strategy_df, summary)
    
    return strategy_df, balances_df, summary


if __name__ == "__main__":
    # Run example when script is executed directly
    strategy_df, balances_df, summary = run_example()
    
    # Optionally save to CSV
    strategy_df.to_csv("withdrawal_strategy_output.csv", index=False)
    print("Strategy saved to withdrawal_strategy_output.csv")
