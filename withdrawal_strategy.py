"""
Portfolio Withdrawal Strategy Module - 5 Stages of Life

This module implements a comprehensive withdrawal strategy across 5 life stages:
1. Accumulation: Employed, earning wages, tax-efficient asset accumulation
2. Early Retirement: Pre-Medicare, pre-SS, pre-RMD with BETR-optimized Roth conversions
3. Medicare Stage: IRMAA optimization with BETR-based continued Roth conversions
4. Social Security Stage: SS benefits + Medicare, pre-RMD optimization with BETR
5. RMD Stage: Required Minimum Distributions with full retirement income

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

import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass

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
from ssibenefits import get_age, get_monthly_benefit, get_claiming_age
from betr_roth_conversion import (
    optimize_conversion_amount,
    calculate_betr,
    BETRInputs,
    BETRResults
)


def calculate_cash_buffer_targets(expenses: float) -> Tuple[float, float]:
    """
    Calculate the target buffer amounts for Cash and Taxable accounts
    
    Args:
        expenses: Annual expenses
    
    Returns:
        Tuple of (cash_target, taxable_target)
        - cash_target: 2 years of expenses
        - taxable_target: 3 years of expenses
    """
    cash_target = expenses * 2.0  # 2 years in Cash
    taxable_target = expenses * 3.0  # 3 years in Taxable
    return cash_target, taxable_target


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
    available_rates = tax_brackets[tax_brackets['rate'] <= max_rate]['rate'].unique()
    available_rates = sorted(available_rates, reverse=True)  # Highest first
    
    # Remove 0% bracket (not useful for conversions)
    available_rates = [r for r in available_rates if r > 0]
    
    if not available_rates:
        raise ValueError(f"No suitable tax brackets found up to {max_rate:.2%}")
    
    # Try each rate from highest to lowest until we find one that exists
    for rate in available_rates:
        try:
            upper_limit = getUpperIncomeRate(rate, tax_brackets)
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
    rmd_years = [s for s in strategies if s.stage == "Stage 5: RMD"]
    
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
        "Stage 2: Early Retirement",
        "Stage 3: Medicare", 
        "Stage 4: Social Security"
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
        if year_strategy.stage in ["Stage 2: Early Retirement", 
                                   "Stage 3: Medicare",
                                   "Stage 4: Social Security"]:
            # Calculate maximum additional conversion (limit to 15% of Traditional balance)
            max_additional = min(
                additional_conversion_per_year,
                year_strategy.balances.traditional * 0.15
            )
            
            if max_additional > 1000:  # Only adjust if meaningful amount
                # Verify with BETR that additional conversion is beneficial
                try:
                    betr_inputs = BETRInputs(
                        current_marginal_rate=0.24,  # Assume 24% bracket
                        expected_future_rate=0.24,   # Assume same in RMD years
                        conversion_amount=year_strategy.roth_conversion + max_additional,
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
                        
                        # Increase conversion
                        year_strategy.roth_conversion += max_additional
                        
                        # CRITICAL: Recalculate balances to reflect the increased conversion
                        # The additional conversion reduces Traditional and increases Roth
                        year_strategy.balances = PortfolioBalances(
                            cash=year_strategy.balances.cash,
                            taxable=year_strategy.balances.taxable,
                            traditional=year_strategy.balances.traditional - max_additional,
                            roth=year_strategy.balances.roth + max_additional,
                            daf=year_strategy.balances.daf
                        )
                        
                        total_additional_conversions += max_additional
                        years_adjusted += 1
                        
                        # Log balances after adjustment
                        logger.info(f"  After optimization adjustment:")
                        logger.info(f"  Traditional: ${year_strategy.balances.traditional:,.2f} (reduced by ${max_additional:,.2f})")
                        logger.info(f"  Roth: ${year_strategy.balances.roth:,.2f} (increased by ${max_additional:,.2f})")
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
    
    optimization_report = {
        "status": "Optimization complete",
        "avg_rmd_excess": avg_rmd_excess,
        "rmd_years_analyzed": rmd_count,
        "pre_rmd_years_available": years_available,
        "years_adjusted": years_adjusted,
        "additional_conversion_per_year_target": additional_conversion_per_year,
        "total_additional_conversions": total_additional_conversions,
        "estimated_rmd_reduction": estimated_rmd_reduction,
        "avg_additional_per_adjusted_year": total_additional_conversions / years_adjusted if years_adjusted > 0 else 0
    }
    
    logger.info(f"RMD Optimization Complete:")
    logger.info(f"  - Adjusted {years_adjusted} years")
    logger.info(f"  - Total additional conversions: ${total_additional_conversions:,.0f}")
    logger.info(f"  - Estimated RMD reduction: ${estimated_rmd_reduction:,.0f}")
    
    return adjusted_strategies, optimization_report


def calculate_state_tax(state_agi: float, state: str = None, year: int = 2024,
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
        'MA': [(0, float('inf'), 0.05)],  # Flat 5%
        'CO': [(0, float('inf'), 0.044)],  # Flat 4.4%
        'NC': [(0, float('inf'), 0.0475)],  # Flat 4.75%
    }
    
    # Standard deductions by state (simplified)
    STANDARD_DEDUCTIONS = {
        'CA': 10404, 'NY': 16050, 'NJ': 0, 'MA': 0, 'CO': 0, 'NC': 25500
    }
    
    # Apply standard deduction
    std_deduction = STANDARD_DEDUCTIONS.get(state, 0)
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
        regular_tax = calculate_taxable_income(
            income + conversions,
            deductions,
            year,
            filing_status
        )
    except:
        # Fallback to simple calculation
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


def calculate_medicare_costs(age_primary: int,
                            age_spouse: int,
                            magi_two_years_ago: float,
                            year: int,
                            filing_status: str = "married_filing_jointly",
                            has_medigap: bool = True) -> Tuple[float, Dict]:
    """
    Calculate total Medicare costs including IRMAA.
    
    Uses existing get_medicare_costs(year) function from load_data module
    and calculate_irmma_penalty() for IRMAA calculations.
    
    Args:
        age_primary: Primary person age
        age_spouse: Spouse age
        magi_two_years_ago: MAGI from 2 years prior for IRMAA
        year: Current year
        filing_status: Filing status
        has_medigap: Whether they have Medigap coverage
    
    Returns:
        Tuple of (total_medicare_cost, cost_breakdown)
    """
    logger.debug(f"Calculating Medicare costs for year {year}, ages {age_primary}/{age_spouse}")
    
    total_cost = 0.0
    breakdown = {
        'part_b_primary': 0.0,
        'part_b_spouse': 0.0,
        'part_d_primary': 0.0,
        'part_d_spouse': 0.0,
        'medigap_primary': 0.0,
        'medigap_spouse': 0.0,
        'irmaa_penalty': 0.0
    }
    
    # Get IRMAA bracket using existing function
    try:
        irmaa_penalty, irmaa_details = calculate_irmma_penalty(
            magi_two_years_ago,
            year - 2,  # IRMAA based on 2 years prior
            filing_status
        )
    except Exception as e:
        logger.warning(f"IRMAA calculation failed: {e}, using standard premium")
        irmaa_penalty = 0
        irmaa_details = {'part_b_premium': 174.70}  # 2024 standard premium
    
    # Part B costs
    if age_primary >= 65:
        monthly_premium = irmaa_details.get('part_b_premium', 174.70)
        breakdown['part_b_primary'] = monthly_premium * 12
        total_cost += breakdown['part_b_primary']
    
    if age_spouse >= 65:
        monthly_premium = irmaa_details.get('part_b_premium', 174.70)
        breakdown['part_b_spouse'] = monthly_premium * 12
        total_cost += breakdown['part_b_spouse']
    
    # Part D costs (base premium + IRMAA)
    part_d_base = 480  # $40/month average
    if age_primary >= 65:
        part_d_irmaa = irmaa_details.get('part_d_irmaa', 0) * 12
        breakdown['part_d_primary'] = part_d_base + part_d_irmaa
        total_cost += breakdown['part_d_primary']
    
    if age_spouse >= 65:
        part_d_irmaa = irmaa_details.get('part_d_irmaa', 0) * 12
        breakdown['part_d_spouse'] = part_d_base + part_d_irmaa
        total_cost += breakdown['part_d_spouse']
    
    # Medigap costs
    if has_medigap:
        medigap_annual = 2400  # $200/month average
        if age_primary >= 65:
            breakdown['medigap_primary'] = medigap_annual
            total_cost += medigap_annual
        if age_spouse >= 65:
            breakdown['medigap_spouse'] = medigap_annual
            total_cost += medigap_annual
    
    breakdown['irmaa_penalty'] = irmaa_penalty
    breakdown['total_medicare_cost'] = total_cost
    
    logger.info(f"Year {year}: Medicare costs = ${total_cost:,.0f} "
               f"(IRMAA penalty: ${irmaa_penalty:,.0f})")
    
    return total_cost, breakdown


def calculate_total_healthcare_costs(age_primary: int,
                                    age_spouse: int,
                                    magi_two_years_ago: float,
                                    year: int,
                                    filing_status: str = "married_filing_jointly",
                                    health_status: str = "average",
                                    has_ltc_insurance: bool = False,
                                    has_medigap: bool = True) -> Tuple[float, Dict]:
    """
    Calculate comprehensive healthcare costs for the year
    
    Args:
        age_primary: Primary person's age
        age_spouse: Spouse's age
        magi_two_years_ago: MAGI from 2 years prior
        year: Current year
        filing_status: Filing status
        health_status: "healthy", "average", or "chronic"
        has_ltc_insurance: Whether they have LTC insurance
        has_medigap: Whether they have Medigap coverage
    
    Returns:
        Tuple of (total_healthcare_cost, cost_breakdown)
    """
    logger.debug(f"Calculating total healthcare costs for year {year}")
    
    total_cost = 0.0
    breakdown = {}
    
    # Medicare costs (if age 65+)
    if age_primary >= 65 or age_spouse >= 65:
        medicare_cost, medicare_breakdown = calculate_medicare_costs(
            age_primary, age_spouse, magi_two_years_ago, year, 
            filing_status, has_medigap
        )
        total_cost += medicare_cost
        breakdown['medicare'] = medicare_breakdown
    
    # Pre-Medicare costs (if under 65)
    if age_primary < 65 or age_spouse < 65:
        # Simplified: Use ACA marketplace estimate
        people_under_65 = (1 if age_primary < 65 else 0) + (1 if age_spouse < 65 else 0)
        aca_cost = people_under_65 * 12000  # $1,000/month per person
        total_cost += aca_cost
        breakdown['pre_medicare'] = aca_cost
        logger.debug(f"Pre-Medicare costs: ${aca_cost:,.0f} for {people_under_65} person(s)")
    
    # Out-of-pocket expenses
    oop_costs = {
        'healthy': 4000,
        'average': 6500,
        'chronic': 12000
    }
    oop_cost = oop_costs.get(health_status, 6500)
    total_cost += oop_cost
    breakdown['out_of_pocket'] = oop_cost
    
    # Long-term care insurance premiums
    if has_ltc_insurance:
        ltc_premium = 3500  # $3,500/year per person average
        people_count = 2 if age_spouse > 0 else 1
        ltc_cost = ltc_premium * people_count
        total_cost += ltc_cost
        breakdown['ltc_insurance'] = ltc_cost
    
    breakdown['total_healthcare_cost'] = total_cost
    
    logger.info(f"Year {year}: Total healthcare cost = ${total_cost:,.0f}")
    
    return total_cost, breakdown


def project_healthcare_costs(start_year: int,
                            end_year: int,
                            age_primary_start: int,
                            age_spouse_start: int,
                            magi_projections: List[float],
                            health_status: str = "average",
                            has_ltc_insurance: bool = False,
                            has_medigap: bool = True) -> pd.DataFrame:
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
    
    Returns:
        DataFrame with yearly healthcare cost projections
    """
    logger.info(f"Projecting healthcare costs from {start_year} to {end_year}")
    
    projections = []
    
    for i, year in enumerate(range(start_year, end_year + 1)):
        age_primary = age_primary_start + i
        age_spouse = age_spouse_start + i
        
        # Get MAGI from 2 years ago for IRMAA
        magi_idx = max(0, i - 2)
        magi_two_years_ago = magi_projections[magi_idx] if magi_idx < len(magi_projections) else 0
        
        # Calculate costs
        total_cost, breakdown = calculate_total_healthcare_costs(
            age_primary=age_primary,
            age_spouse=age_spouse,
            magi_two_years_ago=magi_two_years_ago,
            year=year,
            health_status=health_status,
            has_ltc_insurance=has_ltc_insurance,
            has_medigap=has_medigap
        )
        
        projections.append({
            'year': year,
            'age_primary': age_primary,
            'age_spouse': age_spouse,
            'total_healthcare_cost': total_cost,
            **breakdown
        })
    
    return pd.DataFrame(projections)


def calculate_niit(net_investment_income: float, magi: float,
                  filing_status: str = "married_filing_jointly") -> Tuple[float, Dict]:
    """
    Calculate Net Investment Income Tax (3.8% surtax)
    
    Args:
        net_investment_income: Total investment income
        magi: Modified Adjusted Gross Income
        filing_status: Filing status
    
    Returns:
        Tuple of (niit_amount, calculation_details)
        
    Formula:
        NIIT = min(NII, max(0, MAGI - threshold)) * 0.038
        
    Key Thresholds (NOT indexed for inflation since 2013):
        - Married Filing Jointly: $250,000
        - Single: $200,000
        - Married Filing Separately: $125,000
        - Head of Household: $200,000
    """
    logger.debug(f"Calculating NIIT: NII=${net_investment_income:,.0f}, MAGI=${magi:,.0f}")
    
    # NIIT thresholds (not indexed for inflation)
    NIIT_THRESHOLDS = {
        'married_filing_jointly': 250000,
        'single': 200000,
        'married_filing_separately': 125000,
        'head_of_household': 200000
    }
    
    threshold = NIIT_THRESHOLDS.get(filing_status, 250000)
    rate = 0.038  # 3.8% surtax
    
    # Calculate excess MAGI over threshold
    excess_magi = max(0, magi - threshold)
    
    # NIIT applies to lesser of NII or excess MAGI
    niit_base = min(net_investment_income, excess_magi)
    
    # Calculate NIIT
    niit_amount = niit_base * rate
    
    # Calculation details
    details = {
        'net_investment_income': net_investment_income,
        'magi': magi,
        'threshold': threshold,
        'excess_magi': excess_magi,
        'niit_base': niit_base,
        'niit_rate': rate,
        'niit_amount': niit_amount,
        'subject_to_niit': niit_amount > 0
    }
    
    if niit_amount > 0:
        logger.info(f"NIIT Triggered: MAGI=${magi:,.0f} exceeds threshold=${threshold:,.0f}, "
                   f"NIIT=${niit_amount:,.0f}")
    else:
        logger.debug(f"No NIIT: MAGI=${magi:,.0f} below threshold=${threshold:,.0f}")
    
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
    federal_tax: float
    irmaa_penalty: float
    aca_premium: float
    
    # Account balances (end of year)
    balances: PortfolioBalances
    
    # NEW: Fund movement tracking (v2.0 - Account Rebalancing)
    cash_replenishment: float = 0.0
    brokerage_replenishment: float = 0.0
    traditional_to_cash: float = 0.0
    traditional_to_brokerage: float = 0.0
    brokerage_to_cash: float = 0.0
    roth_to_cash: float = 0.0
    roth_to_brokerage: float = 0.0
    conversion_executed: float = 0.0
    
    def validate_fund_conservation(self) -> bool:
        """
        Verify that all fund movements balance to zero
        (what leaves one account enters another)
        
        Returns:
            True if funds are conserved, False otherwise
        """
        # Outflows (money leaving accounts)
        outflows = (
            self.traditional_to_cash +
            self.traditional_to_brokerage +
            self.brokerage_to_cash +
            self.roth_to_cash +
            self.roth_to_brokerage +
            self.conversion_executed  # Traditional → Roth
        )
        
        # Inflows (money entering accounts)
        inflows = (
            self.cash_replenishment +
            self.brokerage_replenishment +
            self.conversion_executed  # → Roth
        )
        
        # Log fund conservation details at INFO level
        logger.info(f"Year {self.year}: Fund Conservation Check")
        logger.info(f"  OUTFLOWS (money leaving accounts):")
        logger.info(f"    Traditional → Cash: ${self.traditional_to_cash:,.2f}")
        logger.info(f"    Traditional → Brokerage: ${self.traditional_to_brokerage:,.2f}")
        logger.info(f"    Brokerage → Cash: ${self.brokerage_to_cash:,.2f}")
        logger.info(f"    Roth → Cash: ${self.roth_to_cash:,.2f}")
        logger.info(f"    Roth → Brokerage: ${self.roth_to_brokerage:,.2f}")
        logger.info(f"    Conversion Executed (Trad→Roth): ${self.conversion_executed:,.2f}")
        logger.info(f"    TOTAL OUTFLOWS: ${outflows:,.2f}")
        logger.info(f"  INFLOWS (money entering accounts):")
        logger.info(f"    Cash Replenishment: ${self.cash_replenishment:,.2f}")
        logger.info(f"    Brokerage Replenishment: ${self.brokerage_replenishment:,.2f}")
        logger.info(f"    Conversion Executed (→Roth): ${self.conversion_executed:,.2f}")
        logger.info(f"    TOTAL INFLOWS: ${inflows:,.2f}")
        
        # Should balance (within rounding)
        balance = abs(outflows - inflows)
        logger.info(f"  NET BALANCE: ${balance:,.2f} (should be ~$0)")
        
        if balance > 1.0:  # Allow $1 rounding error
            logger.error(f"Year {self.year}: Fund conservation VIOLATED: ${balance:,.2f} imbalance")
            logger.error(f"  Outflows: ${outflows:,.2f}, Inflows: ${inflows:,.2f}")
            return False
        
        logger.info(f"  Fund conservation: ✓ PASSED")
        return True


# ==============================================================================
# ACCOUNT REBALANCING HELPER FUNCTIONS (v2.0)
# ==============================================================================

def replenish_cash_buffer(balances: PortfolioBalances, 
                          expenses: float,
                          age_primary: int,
                          year: int) -> Tuple[PortfolioBalances, Dict[str, float]]:
    """
    Replenish cash buffer to 2-year target
    
    Implements tax-efficient cash buffer maintenance by transferring funds
    from other accounts in priority order:
    1. Brokerage → Cash (tax-free, already in taxable account)
    2. Traditional → Cash (ordinary income tax)
    3. Roth → Cash (emergency only, tax-free if qualified)
    
    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        age_primary: Primary person's age
        year: Current year
    
    Returns:
        Tuple of (updated_balances, transaction_log)
        - updated_balances: PortfolioBalances after replenishment
        - transaction_log: Dict with all fund movements
    """
    cash_target = expenses * 2.0
    cash_deficit = max(0, cash_target - balances.cash)
    
    if cash_deficit < 100:  # Ignore trivial amounts
        return balances, {
            'brokerage_to_cash': 0.0,
            'traditional_to_cash': 0.0,
            'roth_to_cash': 0.0,
            'cash_replenishment': 0.0
        }
    
    logger.warning(f"Year {year}: Cash buffer below target (${balances.cash:,.0f} < ${cash_target:,.0f})")
    logger.warning(f"  Cash deficit: ${cash_deficit:,.0f}")
    logger.warning(f"  Current account balances:")
    logger.warning(f"    Cash: ${balances.cash:,.2f}")
    logger.warning(f"    Taxable (Brokerage): ${balances.taxable:,.2f}")
    logger.warning(f"    Traditional: ${balances.traditional:,.2f}")
    logger.warning(f"    Roth: ${balances.roth:,.2f}")
    logger.warning(f"    DAF: ${balances.daf:,.2f}")
    
    transactions = {
        'brokerage_to_cash': 0.0,
        'traditional_to_cash': 0.0,
        'roth_to_cash': 0.0,
        'cash_replenishment': 0.0
    }
    
    # Step 1: Transfer from Brokerage (tax-free)
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
    
    # Step 2: Distribute from Traditional (taxable)
    if cash_deficit > 0 and balances.traditional > 0:
        distribution = min(cash_deficit, balances.traditional * 0.10)  # Max 10% per year
        balances = PortfolioBalances(
            cash=balances.cash + distribution,
            taxable=balances.taxable,
            traditional=balances.traditional - distribution,
            roth=balances.roth,
            daf=balances.daf
        )
        transactions['traditional_to_cash'] = distribution
        cash_deficit -= distribution
        logger.info(f"  Distributed ${distribution:,.0f} from Traditional to Cash (ordinary income tax)")
    
    # Step 3: Emergency Roth distribution (tax-free if qualified)
    if cash_deficit > 0 and balances.roth > 0 and age_primary >= 59.5:
        distribution = min(cash_deficit, balances.roth * 0.05)  # Max 5% per year
        balances = PortfolioBalances(
            cash=balances.cash + distribution,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth - distribution,
            daf=balances.daf
        )
        transactions['roth_to_cash'] = distribution
        logger.warning(f"  EMERGENCY - Distributed ${distribution:,.0f} from Roth to Cash")
    
    transactions['cash_replenishment'] = sum([
        transactions['brokerage_to_cash'],
        transactions['traditional_to_cash'],
        transactions['roth_to_cash']
    ])
    
    logger.info(f"  Total cash replenishment: ${transactions['cash_replenishment']:,.0f}")
    logger.info(f"  New cash balance: ${balances.cash:,.0f}")
    
    return balances, transactions


def replenish_brokerage_buffer(balances: PortfolioBalances,
                               expenses: float,
                               age_primary: int,
                               year: int) -> Tuple[PortfolioBalances, Dict[str, float]]:
    """
    Replenish brokerage buffer to 3-year target
    
    Implements tax-efficient brokerage buffer maintenance by distributing
    funds from retirement accounts in priority order:
    1. Traditional → Brokerage (ordinary income tax)
    2. Roth → Brokerage (emergency only, tax-free if qualified)
    
    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        age_primary: Primary person's age
        year: Current year
    
    Returns:
        Tuple of (updated_balances, transaction_log)
        - updated_balances: PortfolioBalances after replenishment
        - transaction_log: Dict with all fund movements
    """
    brokerage_target = expenses * 3.0
    brokerage_deficit = max(0, brokerage_target - balances.taxable)
    
    if brokerage_deficit < 100:
        return balances, {
            'traditional_to_brokerage': 0.0,
            'roth_to_brokerage': 0.0,
            'brokerage_replenishment': 0.0
        }
    
    logger.info(f"Year {year}: Brokerage buffer below target (${balances.taxable:,.0f} < ${brokerage_target:,.0f})")
    logger.info(f"  Brokerage deficit: ${brokerage_deficit:,.0f}")
    
    transactions = {
        'traditional_to_brokerage': 0.0,
        'roth_to_brokerage': 0.0,
        'brokerage_replenishment': 0.0
    }
    
    # Step 1: Distribute from Traditional (taxable)
    if brokerage_deficit > 0 and balances.traditional > 0:
        distribution = min(brokerage_deficit, balances.traditional * 0.15)  # Max 15% per year
        balances = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable + distribution,
            traditional=balances.traditional - distribution,
            roth=balances.roth,
            daf=balances.daf
        )
        transactions['traditional_to_brokerage'] = distribution
        brokerage_deficit -= distribution
        logger.info(f"  Distributed ${distribution:,.0f} from Traditional to Brokerage (ordinary income tax)")
    
    # Step 2: Emergency Roth distribution (tax-free if qualified)
    if brokerage_deficit > 0 and balances.roth > 0 and age_primary >= 59.5:
        distribution = min(brokerage_deficit, balances.roth * 0.05)  # Max 5% per year
        balances = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable + distribution,
            traditional=balances.traditional,
            roth=balances.roth - distribution,
            daf=balances.daf
        )
        transactions['roth_to_brokerage'] = distribution
        logger.warning(f"  EMERGENCY - Distributed ${distribution:,.0f} from Roth to Brokerage")
    
    transactions['brokerage_replenishment'] = sum([
        transactions['traditional_to_brokerage'],
        transactions['roth_to_brokerage']
    ])
    
    logger.info(f"  Total brokerage replenishment: ${transactions['brokerage_replenishment']:,.0f}")
    logger.info(f"  New brokerage balance: ${balances.taxable:,.0f}")
    
    return balances, transactions


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
                      stage: str) -> Tuple[PortfolioBalances, Dict[str, float]]:
    """
    Execute all account rebalancing operations for a given year
    
    This function orchestrates:
    1. Cash buffer maintenance (2-year target)
    2. Brokerage buffer maintenance (3-year target)
    3. Roth conversion execution
    4. Fund movement tracking
    
    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        roth_conversion: Roth conversion amount (from BETR algorithm)
        year: Current year
        age_primary: Primary person's age
        stage: Current life stage
    
    Returns:
        Tuple of (updated_balances, transaction_log)
        - updated_balances: PortfolioBalances after all movements
        - transaction_log: Dict with all fund movements for reporting
    """
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
    
    # Step 1: Deduct expenses from cash account FIRST
    logger.info(f"Year {year}: Deducting expenses from cash")
    logger.info(f"  Cash before expenses: ${balances.cash:,.2f}")
    logger.info(f"  Annual expenses: ${expenses:,.2f}")
    
    balances = PortfolioBalances(
        cash=balances.cash - expenses,
        taxable=balances.taxable,
        traditional=balances.traditional,
        roth=balances.roth,
        daf=balances.daf
    )
    transactions['expenses_paid'] = expenses
    
    logger.info(f"  Cash after expenses: ${balances.cash:,.2f}")
    
    # Step 2: Replenish cash buffer (after expenses paid)
    balances, cash_txns = replenish_cash_buffer(balances, expenses, age_primary, year)
    transactions['brokerage_to_cash'] = cash_txns['brokerage_to_cash']
    transactions['traditional_to_cash'] = cash_txns['traditional_to_cash']
    transactions['roth_to_cash'] = cash_txns['roth_to_cash']
    transactions['cash_replenishment'] = cash_txns['cash_replenishment']
    
    # Step 3: Replenish brokerage buffer
    balances, brokerage_txns = replenish_brokerage_buffer(balances, expenses, age_primary, year)
    transactions['traditional_to_brokerage'] = brokerage_txns['traditional_to_brokerage']
    transactions['roth_to_brokerage'] = brokerage_txns['roth_to_brokerage']
    transactions['brokerage_replenishment'] = brokerage_txns['brokerage_replenishment']
    
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
    logger.info(f"    Roth → Brokerage: ${transactions['roth_to_brokerage']:,.2f}")
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
    
    return balances, transactions


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
        """Applies when still employed with wages"""
        return has_wages
    
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
        
        # Calculate AGI after 401k contributions (pre-tax)
        agi = wages - contribution_401k
        
        # Determine current tax bracket
        taxable_income = agi - std_deduction
        federal_tax, max_rate, upper_max = calculate_taxable_income(taxable_income, tax_brackets)
        
        logger.debug(f"AGI: ${agi:,.2f}, Tax bracket: {max_rate:.1%}, Tax: ${federal_tax:,.2f}")
        
        # Consider Roth conversions during accumulation using BETR
        # Only convert if in favorable tax bracket (≤ max_conversion_rate)
        roth_conversion = 0
        #print(f"calculate_strategy: balances.traditional equals {balances.traditional}")
        if balances.traditional > 0 and max_rate <= max_conversion_rate:
            try:
                # Use BETR to determine optimal conversion amount
                # During accumulation, we want to reduce future RMDs
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, tax_brackets
                )
                
                # Calculate conversion room in current bracket
                current_income = agi
                conversion_room = max(0, target_bracket_upper - current_income - std_deduction)
                
                if conversion_room > 10000:  # Only convert if meaningful room
                    # Use BETR to validate conversion is beneficial
                    betr_inputs = BETRInputs(
                        current_marginal_rate=max_rate,
                        expected_future_rate=max_conversion_rate,  # Assume higher rate in retirement
                        conversion_amount=min(conversion_room, balances.traditional * 0.15),
                        traditional_ira_balance=balances.traditional,
                        pay_from_taxable=True,
                        taxable_account_balance=balances.taxable,
                        years_to_withdrawal=max(1, 73 - age_primary),
                        annual_return=0.07
                    )
                    
                    betr_results = calculate_betr(betr_inputs)
                    
                    if betr_results.conversion_recommended:
                        roth_conversion = min(conversion_room, balances.traditional * 0.15)
                        logger.info(f"Stage 1 Roth conversion: ${roth_conversion:,.0f} "
                                  f"(BETR: {betr_results.betr:.2%}, "
                                  f"Current rate: {max_rate:.1%})")
                    else:
                        logger.debug(f"BETR {betr_results.betr:.2%} - conversion not recommended")
                        
            except (ValueError, Exception) as e:
                logger.debug(f"Could not calculate BETR conversion: {e}")
        
        # Calculate tax on conversion if any
        if roth_conversion > 0:
            total_income = agi + roth_conversion
            taxable_income_with_conversion = total_income - std_deduction
            federal_tax, _, _ = calculate_taxable_income(taxable_income_with_conversion, tax_brackets)
        
        # Update balances with contributions (before rebalancing)
        balances_with_contributions = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable,
            traditional=balances.traditional + contribution_401k,
            roth=balances.roth + contribution_roth,
            daf=balances.daf
        )
        
        # Execute account rebalancing (includes Roth conversion)
        new_balances, transactions = rebalance_accounts(
            balances=balances_with_contributions,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name
        )
        
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
            daf_contribution=0,
            expenses=expenses,
            federal_tax=federal_tax,
            irmaa_penalty=0,
            aca_premium=0,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed']
        )


class Stage2EarlyRetirement(LifeStage):
    """
    Stage 2: Early Retirement (Pre-Medicare, Pre-SS, Pre-RMD)
    - No wages, no SS benefits yet
    - Optimize Roth conversions (low/no income years)
    - Use LTCG to fund living expenses (0% or 15% rate)
    - Consider ACA subsidies (keep income below 400% FPL)
    - 4% withdrawal strategy
    """
    
    def __init__(self):
        super().__init__(
            "Stage 2: Early Retirement",
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
        logger.debug(f"Stage 2 calculation for year {year}, target conversion=${target_conversion:,.2f}")
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        
        # Get tax data
        tax_brackets = get_income_tax_brackets(year)
        cg_brackets = get_cap_gains_brackets(year)
        std_deduction_df = get_std_deduction(year)
        std_deduction = std_deduction_df.iloc[0]['deduction']
        
        # NEW STRATEGY: Maintain cash buffer (2 years in Cash, 3 years in Taxable)
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
        
        # Strategy: Use LTCG to fund expenses, maximize Roth conversions
        # Harvest LTCG from taxable account (preferably at 0% rate)
        
        # Determine optimal LTCG harvest (stay in 0% bracket if possible)
        cg_0_percent = cg_brackets[cg_brackets['rate'] == 0]
        if len(cg_0_percent) > 0:
            cg_0_percent_limit = cg_0_percent['upper'].iloc[0]
        else:
            # Fallback: use standard deduction if no 0% bracket exists
            cg_0_percent_limit = std_deduction
            logger.warning(f"No 0% capital gains bracket found for year {year}, using standard deduction")
        
        # Calculate how much LTCG we can harvest at 0%
        ltcg_room = cg_0_percent_limit - std_deduction
        estimated_withdrawal_need = expenses * 1.15  # Rough estimate including taxes
        ltcg_harvested = min(estimated_withdrawal_need, ltcg_room, balances.taxable * 0.5)
        
        logger.debug(f"LTCG harvested: ${ltcg_harvested:,.2f} (0% bracket room: ${ltcg_room:,.2f})")
        
        # Calculate Roth conversion using BETR algorithm
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        current_income = ltcg_harvested
        
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
            
            # Only convert if BETR analysis recommends it
            if betr_results.conversion_recommended:
                roth_conversion = optimal_amount
                logger.info(f"BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f}")
            else:
                roth_conversion = 0
                logger.info(f"BETR: {betr_results.betr:.2%}, Conversion not recommended")
                
        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to bracket-filling method")
            # Fallback to original method
            try:
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, tax_brackets
                )
            except ValueError:
                target_bracket_rate = 0.12
                target_bracket_upper = getUpperIncomeRate(0.12, tax_brackets)
            
            conversion_room = target_bracket_upper - std_deduction - current_income
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
        
        # Execute account rebalancing (includes Roth conversion and buffer maintenance)
        new_balances, transactions = rebalance_accounts(
            balances=balances,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name
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
        
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=transactions['traditional_to_cash'] + transactions['traditional_to_brokerage'],
            taxable_withdrawal=transactions['brokerage_to_cash'],
            roth_withdrawal=transactions['roth_to_cash'] + transactions['roth_to_brokerage'],
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=total_tax,
            irmaa_penalty=0,
            aca_premium=0,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed']
        )


class Stage3Medicare(LifeStage):
    """
    Stage 3: Medicare Stage (Pre-SS, Pre-RMD)
    - On Medicare, optimize for IRMAA
    - Continue Roth conversions but watch IRMAA thresholds
    - IRMAA based on MAGI from 2 years prior
    - Balance conversions vs IRMAA penalties
    """
    
    def __init__(self):
        super().__init__(
            "Stage 3: Medicare",
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
        logger.debug(f"Stage 3 calculation for year {year}, prior MAGI=${prior_magi:,.2f}")
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        
        # Get tax and IRMAA data
        tax_brackets = get_income_tax_brackets(year)
        cg_brackets = get_cap_gains_brackets(year)
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
                next_brackets = irmaa_brackets[irmaa_brackets['lower'] > row['upper']]
                if not next_brackets.empty:
                    next_irmaa_threshold = next_brackets.iloc[0]['lower']
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
        cg_0_percent = cg_brackets[cg_brackets['rate'] == 0]
        if len(cg_0_percent) > 0:
            cg_0_percent_limit = cg_0_percent['upper'].iloc[0]
        else:
            cg_0_percent_limit = std_deduction
            logger.warning(f"No 0% capital gains bracket found for year {year}, using standard deduction")
        ltcg_room = cg_0_percent_limit - std_deduction
        ltcg_harvested = min(total_need * 1.2, ltcg_room, balances.taxable * 0.5)
        
        # Calculate Roth conversion using BETR algorithm with IRMAA consideration
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        current_income = ltcg_harvested
        
        # Calculate IRMAA headroom
        irmaa_headroom = next_irmaa_threshold - ltcg_harvested - std_deduction
        
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
            
            # Check IRMAA impact of proposed conversion
            proposed_magi = current_income + optimal_amount
            
            # If conversion would trigger IRMAA penalty > 2% of conversion amount, reduce it
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
                        roth_conversion = 0
                        logger.info(f"BETR: {reduced_results.betr:.2%}, Conversion not recommended even at IRMAA limit")
                else:
                    roth_conversion = 0
                    logger.info("No conversion room due to IRMAA threshold")
            else:
                # Conversion fits within IRMAA headroom
                if betr_results.conversion_recommended:
                    roth_conversion = optimal_amount
                    logger.info(f"BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f}")
                else:
                    roth_conversion = 0
                    logger.info(f"BETR: {betr_results.betr:.2%}, Conversion not recommended")
                    
        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to IRMAA-aware method")
            # Fallback to original IRMAA-aware method
            try:
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, tax_brackets
                )
            except ValueError:
                target_bracket_rate = 0.12
                target_bracket_upper = getUpperIncomeRate(0.12, tax_brackets)
            
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
        
        # Execute account rebalancing (includes Roth conversion and buffer maintenance)
        new_balances, transactions = rebalance_accounts(
            balances=balances,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name
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
        
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=transactions['traditional_to_cash'] + transactions['traditional_to_brokerage'],
            taxable_withdrawal=transactions['brokerage_to_cash'],
            roth_withdrawal=transactions['roth_to_cash'] + transactions['roth_to_brokerage'],
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=0,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed']
        )


class Stage4SocialSecurity(LifeStage):
    """
    Stage 4: Social Security Stage (SS + Medicare, Pre-RMD)
    - Collecting SS benefits
    - On Medicare (IRMAA considerations)
    - Continue strategic Roth conversions
    - Balance SS taxation (up to 85% taxable)
    """
    
    def __init__(self):
        super().__init__(
            "Stage 4: Social Security",
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
        logger.debug(f"Stage 4 calculation for year {year}, SS=${ss_benefits:,.2f}")
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        
        # Get tax data
        tax_brackets = get_income_tax_brackets(year)
        cg_brackets = get_cap_gains_brackets(year)
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
            cg_0_percent = cg_brackets[cg_brackets['rate'] == 0]
            if len(cg_0_percent) > 0:
                cg_0_percent_limit = cg_0_percent['upper'].iloc[0]
            else:
                cg_0_percent_limit = std_deduction
                logger.warning(f"No 0% capital gains bracket found for year {year}, using standard deduction")
            ltcg_room = max(0, cg_0_percent_limit - taxable_ss - std_deduction)
            ltcg_harvested = min(withdrawal_need, ltcg_room, balances.taxable * 0.5)
        
        # Calculate Roth conversion room
        current_income = taxable_ss + ltcg_harvested
        
        # Find IRMAA threshold
        next_irmaa_threshold = float('inf')
        for _, row in irmaa_brackets.iterrows():
            if row['lower'] <= prior_magi <= row['upper']:
                next_brackets = irmaa_brackets[irmaa_brackets['lower'] > row['upper']]
                if not next_brackets.empty:
                    next_irmaa_threshold = next_brackets.iloc[0]['lower']
                break
        
        irmaa_headroom = next_irmaa_threshold - current_income - std_deduction
        
        # Calculate Roth conversion using BETR algorithm with SS income
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        
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
                        roth_conversion = 0
                        logger.info(f"BETR: {reduced_results.betr:.2%}, Conversion not recommended with SS income")
                else:
                    roth_conversion = 0
                    logger.info("No conversion room due to SS income and IRMAA threshold")
            else:
                # Conversion fits within IRMAA headroom
                if betr_results.conversion_recommended:
                    roth_conversion = optimal_amount
                    logger.info(f"BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f} with SS income")
                else:
                    roth_conversion = 0
                    logger.info(f"BETR: {betr_results.betr:.2%}, Conversion not recommended despite SS income")
                    
        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to conservative method")
            # Fallback to original method
            try:
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    max_conversion_rate, tax_brackets
                )
            except ValueError:
                target_bracket_rate = 0.22
                target_bracket_upper = getUpperIncomeRate(0.22, tax_brackets)
            
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
        
        # Execute account rebalancing (includes Roth conversion and buffer maintenance)
        new_balances, transactions = rebalance_accounts(
            balances=balances,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name
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
        
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=ss_benefits,
            rmd_amount=0,
            traditional_withdrawal=transactions['traditional_to_cash'] + transactions['traditional_to_brokerage'],
            taxable_withdrawal=transactions['brokerage_to_cash'],
            roth_withdrawal=transactions['roth_to_cash'] + transactions['roth_to_brokerage'],
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=0,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'],
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed']
        )


class Stage5RMD(LifeStage):
    """
    Stage 5: RMD Stage (Full Retirement)
    - Required Minimum Distributions from Traditional accounts
    - SS benefits + Medicare
    - RMDs may push into higher tax brackets
    - Limited Roth conversion opportunity
    - Focus on tax-efficient withdrawal sequencing
    """
    
    def __init__(self):
        super().__init__(
            "Stage 5: RMD",
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
        cg_brackets = get_cap_gains_brackets(year)
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
            cg_15_percent = cg_brackets[cg_brackets['rate'] == 0.15]
            if len(cg_15_percent) > 0:
                cg_15_percent_limit = cg_15_percent['upper'].iloc[0]
                ltcg_room = max(0, cg_15_percent_limit - total_income - std_deduction)
                ltcg_harvested = min(withdrawal_need, ltcg_room, balances.taxable * 0.5)
                total_income += ltcg_harvested
        
        # Limited Roth conversion opportunity (if RMD doesn't fill bracket)
        roth_conversion = 0
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        try:
            target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                max_conversion_rate, tax_brackets
            )
            conversion_room = max(0, target_bracket_upper - total_income - std_deduction)
            
            if conversion_room > 10000 and balances.traditional > rmd_amount:
                # Only convert if meaningful room and won't trigger higher IRMAA
                next_irmaa_threshold = float('inf')
                for _, row in irmaa_brackets.iterrows():
                    if row['lower'] <= prior_magi <= row['upper']:
                        next_brackets = irmaa_brackets[irmaa_brackets['lower'] > row['upper']]
                        if not next_brackets.empty:
                            next_irmaa_threshold = next_brackets.iloc[0]['lower']
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
        
        # Execute account rebalancing (includes Roth conversion and buffer maintenance)
        # Note: RMD is handled separately as it's mandatory
        new_balances, transactions = rebalance_accounts(
            balances=balances,
            expenses=expenses,
            roth_conversion=roth_conversion,
            year=year,
            age_primary=age_primary,
            stage=self.name
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
        
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=ss_benefits,
            rmd_amount=rmd_amount,
            traditional_withdrawal=transactions['traditional_to_cash'] + transactions['traditional_to_brokerage'] + rmd_amount,
            taxable_withdrawal=transactions['brokerage_to_cash'],
            roth_withdrawal=transactions['roth_to_cash'] + transactions['roth_to_brokerage'],
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=0,
            balances=new_balances,
            # Fund movement tracking
            cash_replenishment=transactions['cash_replenishment'],
            brokerage_replenishment=transactions['brokerage_replenishment'],
            traditional_to_cash=transactions['traditional_to_cash'],
            traditional_to_brokerage=transactions['traditional_to_brokerage'] + rmd_amount,
            brokerage_to_cash=transactions['brokerage_to_cash'],
            roth_to_cash=transactions['roth_to_cash'],
            roth_to_brokerage=transactions['roth_to_brokerage'],
            conversion_executed=transactions['conversion_executed']
        )


class WithdrawalStrategyEngine:
    """
    Main engine for calculating withdrawal strategy across all life stages
    """
    
    def __init__(self):
        self.stages = [
            Stage1Accumulation(),
            Stage2EarlyRetirement(),
            Stage3Medicare(),
            Stage4SocialSecurity(),
            Stage5RMD()
        ]
        logger.info("Withdrawal Strategy Engine initialized with 5 life stages")
    
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
                                     person1_name: str = "Tom",
                                     person2_name: str = "Sarah",
                                     **kwargs) -> pd.DataFrame:
        """
        Calculate withdrawal strategy for multiple years
        
        Args:
            start_year: Starting year
            end_year: Ending year (inclusive)
            initial_balances: Starting portfolio balances
            initial_expenses: Starting annual expenses
            person1_name: Name of primary person
            person2_name: Name of spouse
            **kwargs: Additional parameters (growth_rate, expense_inflation_rate, etc.)
        
        Returns:
            DataFrame with yearly strategies
        """
        logger.info(f"Calculating strategy from {start_year} to {end_year}")
        
        results = []
        balances = initial_balances
        expenses = initial_expenses
        #print(f"Engine: Initial balances trad {balances.traditional}")
       
        # Get parameters
        growth_rate = kwargs.get('growth_rate', 1.07)
        expense_inflation_rate = kwargs.get('expense_inflation_rate', 0.03)  # 3% inflation rate
        spending_decrease_rate = 0.01  # 1% annual decrease in spending
        ss_claiming_age = kwargs.get('ss_claiming_age', 67)
        
        # Track MAGI for IRMAA (2-year lookback)
        magi_history = {}
        
        for year in range(start_year, end_year + 1):
            # Get ages
            age_primary = get_age(year, person1_name)
            age_spouse = get_age(year, person2_name)
            
            # Determine if has wages or SS
            # Get retirement year from config if not provided in kwargs
            if 'retirement_year' not in kwargs:
                config_mgr = get_config_manager()
                retirement_year = config_mgr.get("personal_info", "person1_retirement_year", 2026)
            else:
                retirement_year = kwargs.get('retirement_year')
            
            has_wages = kwargs.get('has_wages', False) and year < retirement_year
            has_ss = age_primary >= ss_claiming_age or age_spouse >= ss_claiming_age
            
            # Get SS benefits if applicable
            ss_benefits = 0
            if has_ss:
                try:
                    ss_primary = get_monthly_benefit(year, person1_name) if age_primary >= ss_claiming_age else 0
                    ss_spouse = get_monthly_benefit(year, person2_name) if age_spouse >= ss_claiming_age else 0
                    ss_benefits = (ss_primary + ss_spouse) * 12
                except Exception as e:
                    logger.warning(f"Could not get SS benefits for {year}: {e}")
            
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
        """Convert list of YearlyStrategy objects to DataFrame"""
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
                'IRMAA Penalty': s.irmaa_penalty,
                'Federal Tax': s.federal_tax,
                'Cash Balance': s.balances.cash,
                # Additional withdrawal details
                'RMD': s.rmd_amount,
                'Taxable Withdrawal': s.taxable_withdrawal,
                'Roth Withdrawal': s.roth_withdrawal,
                'LTCG Harvested': s.ltcg_harvested,
                'DAF Contribution': s.daf_contribution,
                'ACA Premium': s.aca_premium,
                # Account balances
                'Taxable Balance': s.balances.taxable,
                'Traditional Balance': s.balances.traditional,
                'Roth Balance': s.balances.roth,
                'DAF Balance': s.balances.daf,
                'Total Portfolio': s.balances.total()
            })
        
        return pd.DataFrame(data)


def build_withdrawal_strategy_display(start_year: int = None,
                                      end_year: int = None,
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
    #print(f" Initial balances trad {initial_balances.traditional}")
#     p
#     # Log first 4 years of data at INFO level for planning_app.py visibility
    # Get initial expenses from session state or use default
    try:
        import streamlit as st
        initial_expenses = float(st.session_state.get("EXPENSE", 120000))
    except:
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
    #print(balances_df)
    
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
    
    return strategy_df, balances_df


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


def create_example_scenario(scenario_name: str = "default") -> Dict:
    """
    Create example scenarios for testing withdrawal strategies
    
    Args:
        scenario_name: Name of scenario ("default", "early_retire", "high_income")
    
    Returns:
        Dictionary with scenario parameters
    """
    scenarios = {
        "default": {
            "start_year": 2026,
            "end_year": 2050,
            "initial_balances": PortfolioBalances(
                cash=55000,
                taxable=225000,
                traditional=670000,
                roth=168000,
                daf=0
            ),
            "initial_expenses": 120000,
            "person1_name": "Tom",
            "person2_name": "Sarah",
            "growth_rate": 1.07,
            "expense_inflation": 0.993,
            "ss_claiming_age": 67,
            "retirement_year": 2026,
            "has_wages": False
        },
        "early_retire": {
            "start_year": 2026,
            "end_year": 2050,
            "initial_balances": PortfolioBalances(
                cash=100000,
                taxable=400000,
                traditional=1000000,
                roth=200000,
                daf=50000
            ),
            "initial_expenses": 100000,
            "person1_name": "Tom",
            "person2_name": "Sarah",
            "growth_rate": 1.07,
            "expense_inflation": 1.02,
            "ss_claiming_age": 70,  # Delay SS for higher benefits
            "retirement_year": 2026,
            "has_wages": False
        },
        "high_income": {
            "start_year": 2026,
            "end_year": 2050,
            "initial_balances": PortfolioBalances(
                cash=200000,
                taxable=1000000,
                traditional=2000000,
                roth=500000,
                daf=100000
            ),
            "initial_expenses": 200000,
            "person1_name": "Tom",
            "person2_name": "Sarah",
            "growth_rate": 1.08,
            "expense_inflation": 1.025,
            "ss_claiming_age": 67,
            "retirement_year": 2026,
            "has_wages": False
        }
    }
    
    return scenarios.get(scenario_name, scenarios["default"])


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


def print_strategy_report(strategy_df: pd.DataFrame, summary: Dict = None):
    """
    Print a formatted report of the withdrawal strategy
    
    Args:
        strategy_df: DataFrame from calculate_multi_year_strategy
        summary: Optional pre-calculated summary dict
    """
    if summary is None:
        summary = generate_strategy_summary(strategy_df)
    
    print("\n" + "="*80)
    print("RETIREMENT WITHDRAWAL STRATEGY REPORT")
    print("="*80)
    
    print(f"\n📊 OVERVIEW")
    print(f"   Years Analyzed: {summary['total_years']}")
    print(f"   Initial Portfolio: ${summary['initial_portfolio_value']:,.0f}")
    print(f"   Final Portfolio: ${summary['final_portfolio_value']:,.0f}")
    print(f"   Portfolio Growth: ${summary['portfolio_growth']:,.0f}")
    
    print(f"\n🎯 LIFE STAGES")
    for stage, years in summary['stages'].items():
        print(f"   {stage}: {years} years")
    
    print(f"\n💰 ROTH CONVERSION STRATEGY")
    print(f"   Total Conversions: ${summary['total_roth_conversions']:,.0f}")
    print(f"   Years with Conversions: {summary['years_with_conversions']}")
    if summary['max_conversion_year']:
        print(f"   Largest Conversion: ${summary['max_conversion_amount']:,.0f} in {summary['max_conversion_year']}")
    print(f"   Final Roth %: {summary['roth_percentage_final']:.1f}%")
    
    print(f"\n💵 TAXES & COSTS")
    print(f"   Total Federal Taxes: ${summary['total_taxes_paid']:,.0f}")
    print(f"   Total IRMAA Penalties: ${summary['total_irmaa_penalties']:,.0f}")
    print(f"   Average Annual Expenses: ${summary['avg_annual_expenses']:,.0f}")
    
    print(f"\n📈 INCOME SOURCES")
    print(f"   Total SS Benefits: ${summary['total_ss_benefits']:,.0f}")
    print(f"   Total RMDs: ${summary['total_rmd']:,.0f}")
    
    print("\n" + "="*80)
    print("YEAR-BY-YEAR SUMMARY (First 10 & Last 5 years)")
    print("="*80)
    
    # Show first 10 years
    display_cols = ['Year', 'Age', 'Stage', 'Roth Conversion', 'Federal Tax',
                   'IRMAA Penalty', 'Total Portfolio']
    print("\nFirst 10 Years:")
    print(strategy_df[display_cols].head(10).to_string(index=False))
    
    # Show last 5 years
    print("\nLast 5 Years:")
    print(strategy_df[display_cols].tail(5).to_string(index=False))
    
    print("\n" + "="*80 + "\n")


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
    print(f"Starting Year: {scenario['start_year']}")
    print(f"Ending Year: {scenario['end_year']}")
    print(f"Initial Portfolio: ${scenario['initial_balances'].total():,.0f}")
    print(f"Annual Expenses: ${scenario['initial_expenses']:,.0f}")
    
    # Calculate strategy
    strategy_df, balances_df = build_withdrawal_strategy_display(**scenario)
    
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
