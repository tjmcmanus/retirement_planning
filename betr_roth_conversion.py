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
import logging
import os
from datetime import datetime
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass

from load_data import (
    get_income_tax_brackets,
    get_cap_gains_brackets,
    get_std_deduction
)
from calculations import (
    calculate_taxable_income,
    calc_agi,
    getUpperIncomeRate
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
    
    Example:
        conversion_amount = 10000
        annual_return = 0.06 (6%)
        years = 20
        Result: 10000 × (1.06)^20 = 32,071.35
    
    Args:
        conversion_amount: Initial conversion amount (Present Value)
        annual_return: Annual rate of return as decimal (e.g., 0.06 for 6%)
        years: Number of years to compound
        
    Returns:
        Future value after compound growth
        
    Raises:
        ValueError: If inputs are invalid
    """
    if conversion_amount < 0:
        raise ValueError(f"Conversion amount must be non-negative, got ${conversion_amount:,.2f}")
    
    if years < 0:
        raise ValueError(f"Years must be non-negative, got {years}")
    
    if annual_return < -1:
        raise ValueError(f"Annual return must be >= -1 (cannot lose more than 100%), got {annual_return}")
    
    # Calculate compound growth: FV = PV × (1 + r)^n
    growth_factor = (1 + annual_return) ** years
    future_value = conversion_amount * growth_factor
    
    logger.debug(
        f"Conversion FV calculation: ${conversion_amount:,.2f} × {growth_factor:.6f} "
        f"({annual_return:.2%} over {years} years) = ${future_value:,.2f}"
    )
    
    return future_value


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


def calculate_conversion_after_tax_future_value(
    conversion_amount: float,
    annual_return: float,
    years: int,
    ordinary_income_tax_rate: float
) -> Tuple[float, float, float]:
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
        Tuple of (conversion_future_value, tax_future_value, after_tax_future_value)
        
    Raises:
        ValueError: If inputs are invalid
    """
    # Validate inputs
    if conversion_amount < 0:
        raise ValueError(f"Conversion amount must be non-negative, got ${conversion_amount:,.2f}")
    
    if years < 0:
        raise ValueError(f"Years must be non-negative, got {years}")
    
    if annual_return < -1:
        raise ValueError(f"Annual return must be >= -1 (cannot lose more than 100%), got {annual_return}")
    
    if not 0 <= ordinary_income_tax_rate <= 1:
        raise ValueError(
            f"Ordinary income tax rate must be between 0 and 1, got {ordinary_income_tax_rate}"
        )
    
    # Calculate future value of conversion (grows tax-free in Roth)
    conversion_fv = calculate_conversion_future_value(conversion_amount, annual_return, years)
    
    # Calculate conversion tax
    tax_amount = calculate_conversion_tax(conversion_amount, ordinary_income_tax_rate)
    
    # Calculate future value of tax using AFTER-TAX return
    # The tax payment would be in a taxable account, so it grows at an after-tax rate
    # After-tax return = r × (1 - tax_rate)
    after_tax_return = annual_return * (1 - ordinary_income_tax_rate)
    tax_fv = tax_amount * ((1 + after_tax_return) ** years)
    
    # Calculate net after-tax future value
    after_tax_fv = conversion_fv - tax_fv
    
    logger.info(
        f"Conversion after-tax FV: ${conversion_amount:,.2f} conversion over {years} years at {annual_return:.2%}"
    )
    logger.info(f"  Conversion FV: ${conversion_fv:,.2f}")
    logger.info(f"  Tax amount: ${tax_amount:,.2f} ({ordinary_income_tax_rate:.2%})")
    logger.info(f"  After-tax return for tax payment: {after_tax_return:.4%}")
    logger.info(f"  Tax FV (opportunity cost): ${tax_fv:,.2f}")
    logger.info(f"  After-tax FV: ${after_tax_fv:,.2f}")
    
    return conversion_fv, tax_fv, after_tax_fv


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
        ValueError: If inputs are invalid or if conversion_fv is zero
    """
    # Calculate the after-tax future value components
    conversion_fv, tax_fv, after_tax_fv = calculate_conversion_after_tax_future_value(
        conversion_amount, annual_return, years, ordinary_income_tax_rate
    )
    
    # Validate that conversion_fv is not zero to avoid division by zero
    if conversion_fv == 0:
        raise ValueError("Conversion future value cannot be zero")
    
    # Calculate BETR: 1 - (After-Tax FV / Conversion FV)
    betr = 1 - (after_tax_fv / conversion_fv)
    
    logger.info(f"BETR calculation:")
    logger.info(f"  After-Tax FV: ${after_tax_fv:,.2f}")
    logger.info(f"  Conversion FV: ${conversion_fv:,.2f}")
    logger.info(f"  BETR: 1 - ({after_tax_fv:,.2f} / {conversion_fv:,.2f}) = {betr:.4%}")
    logger.info(f"  Interpretation: Convert if future tax rate > {betr:.2%}")
    
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
        cap_gains_df = get_cap_gains_brackets(year)
        
        # Find the applicable bracket
        for _, row in cap_gains_df.iterrows():
            if row['lower'] <= income < row['upper']:
                return float(row['rate'])
        
        # If income exceeds all brackets, return highest rate
        return 0.20
    except Exception as e:
        logger.warning(f"Could not lookup LTCG rate for year {year}, using 15% default: {e}")
        return 0.15  # Conservative default


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
    
    # Step 4: Calculate Base BETR using helper function
    logger.info("--- Step 4: Calculate Base BETR ---")
    # Use the calculate_betr_rate helper function for consistent calculation
    betr = calculate_betr_rate(
        inputs.conversion_amount,
        inputs.annual_return,
        inputs.years_to_withdrawal,
        inputs.current_marginal_rate
    )
    logger.info(f"Base BETR calculated using helper function: {betr:.4%}")
    logger.info(f"Formula: BETR = 1 - (After-Tax FV / Conversion FV)")
    logger.info(f"Step 4 Result - Base BETR: {betr:.4%}")
    
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
    # Only consider backdoor Roth if there are wages (required for contributions)
    if inputs.wages > 0 and inputs.future_backdoor_roth and inputs.backdoor_contribution_years > 0:
        # Converting now enables future backdoor Roth contributions by eliminating pro-rata rule
        # This increases the BETR (makes conversion more attractive)
        # Benefit scales with number of years of future contributions
        backdoor_benefit = BACKDOOR_ROTH_BENEFIT_FACTOR * (inputs.backdoor_contribution_years / 10)
        betr_before = betr
        betr += backdoor_benefit
        logger.info(f"Wages: ${inputs.wages:,.0f} (backdoor Roth eligible)")
        logger.info(f"Backdoor Roth benefit: +{backdoor_benefit:.4%} for {inputs.backdoor_contribution_years} years")
        logger.info(f"Backdoor adjustment (BETR: {betr_before:.4%} → {betr:.4%})")
        analysis_notes.append(
            f"BETR increased by {backdoor_benefit:.2%} due to {inputs.backdoor_contribution_years} "
            f"years of future backdoor Roth contributions"
        )
    else:
        if inputs.wages <= 0:
            logger.info("No backdoor Roth adjustment (no wages - backdoor Roth not applicable)")
            if inputs.future_backdoor_roth:
                analysis_notes.append(
                    "Backdoor Roth contributions require wages. No adjustment applied."
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
        analysis_notes=analysis_notes
    )


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
    future_backdoor_roth: bool = False
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
        
    Returns:
        Tuple of (optimal_conversion_amount, BETRResults)
    """
    logger.info(f"Optimizing conversion for target bracket: {target_tax_bracket:.2%}")
    
    # Get tax brackets for the year
    tax_brackets_df = get_income_tax_brackets(year)
    
    # Find the upper limit of the target tax bracket
    try:
        bracket_upper_limit = getUpperIncomeRate(target_tax_bracket, tax_brackets_df)
    except ValueError:
        logger.error(f"Target tax bracket {target_tax_bracket:.2%} not found")
        # Return empty result
        empty_result = BETRResults(
            betr=0.0,
            conversion_recommended=False,
            conversion_tax=0.0,
            net_benefit=0.0,
            traditional_future_value=0.0,
            roth_future_value=0.0,
            taxable_account_impact=0.0,
            analysis_notes=["Error: Target tax bracket not found"]
        )
        return 0.0, empty_result
    
    # Calculate maximum conversion to stay within bracket
    # Conversion amount = (Bracket Upper Limit - Current AGI)
    max_conversion = max(0, bracket_upper_limit - current_agi)
    
    # Cap at Traditional IRA balance
    optimal_conversion = min(max_conversion, traditional_ira_balance)
    
    logger.info(f"Optimal conversion amount: ${optimal_conversion:,.0f}")
    
    # Validate with BETR analysis
    # Assume future rate is same as target bracket (conservative estimate)
    betr_inputs = BETRInputs(
        current_marginal_rate=target_tax_bracket,
        expected_future_rate=target_tax_bracket,  # Conservative: assume same rate
        conversion_amount=optimal_conversion,
        traditional_ira_balance=traditional_ira_balance,
        nontaxable_basis=nontaxable_basis,
        pay_from_taxable=pay_from_taxable,
        taxable_account_balance=taxable_account_balance,
        years_to_withdrawal=years_to_withdrawal,
        annual_return=annual_return,
        future_backdoor_roth=future_backdoor_roth,
        backdoor_contribution_years=10 if future_backdoor_roth else 0
    )
    
    betr_results = calculate_betr(betr_inputs)
    
    return optimal_conversion, betr_results


def analyze_conversion_scenarios(
    traditional_ira_balance: float,
    conversion_amounts: List[float],
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
        conversion_amounts: List of conversion amounts to analyze
        current_marginal_rate: Current marginal tax rate
        expected_future_rate: Expected future marginal tax rate
        pay_from_taxable: Whether to pay conversion tax from taxable account
        taxable_account_balance: Balance in taxable account
        nontaxable_basis: Nontaxable basis in Traditional IRA
        years_to_withdrawal: Years until withdrawal
        annual_return: Expected annual return
        
    Returns:
        DataFrame with scenario analysis results
    """
    logger.info(f"Analyzing {len(conversion_amounts)} conversion scenarios")
    
    results = []
    
    for amount in conversion_amounts:
        if amount > traditional_ira_balance:
            logger.warning(f"Skipping ${amount:,.0f} - exceeds IRA balance")
            continue
        
        inputs = BETRInputs(
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
        
        betr_result = calculate_betr(inputs)
        
        results.append({
            'conversion_amount': amount,
            'conversion_tax': betr_result.conversion_tax,
            'betr': betr_result.betr,
            'recommended': betr_result.conversion_recommended,
            'net_benefit': betr_result.net_benefit,
            'roth_future_value': betr_result.roth_future_value,
            'traditional_future_value': betr_result.traditional_future_value
        })
    
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
