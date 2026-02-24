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
    
    logger.info(f"Calculating BETR for ${inputs.conversion_amount:,.0f} conversion")
    
    analysis_notes = []
    
    # Determine tax year for lookups
    tax_year = inputs.tax_year if inputs.tax_year is not None else datetime.now().year
    
    # Step 1: Calculate conversion tax
    conversion_tax = inputs.conversion_amount * inputs.current_marginal_rate
    
    # Adjust for nontaxable basis (reduces taxable portion)
    if inputs.nontaxable_basis > 0:
        nontaxable_percentage = inputs.nontaxable_basis / inputs.traditional_ira_balance
        taxable_portion = inputs.conversion_amount * (1 - nontaxable_percentage)
        conversion_tax = taxable_portion * inputs.current_marginal_rate
        analysis_notes.append(
            f"Nontaxable basis of ${inputs.nontaxable_basis:,.0f} reduces taxable conversion to ${taxable_portion:,.0f}"
        )
    
    logger.debug(f"Conversion tax: ${conversion_tax:,.2f}")
    
    # Step 2: Calculate future value in Traditional IRA (no conversion scenario)
    growth_factor = (1 + inputs.annual_return) ** inputs.years_to_withdrawal
    traditional_future_gross = inputs.conversion_amount * growth_factor
    
    # Future withdrawal from Traditional IRA will be taxed at future rate
    traditional_future_net = traditional_future_gross * (1 - inputs.expected_future_rate)
    
    logger.debug(f"Traditional IRA future value (after tax): ${traditional_future_net:,.2f}")
    
    # Step 3: Calculate future value in Roth IRA (conversion scenario)
    if inputs.pay_from_taxable:
        # Paying from taxable account - full conversion amount grows tax-free
        roth_future_value = inputs.conversion_amount * growth_factor
        
        # Calculate opportunity cost of using taxable funds for tax payment
        # These funds could have grown in taxable account (with capital gains tax)
        # Look up actual LTCG rate based on income level
        ltcg_rate = _get_ltcg_rate(inputs.conversion_amount, tax_year)
        taxable_growth_factor = 1 + (inputs.annual_return * (1 - ltcg_rate))
        taxable_opportunity_cost = conversion_tax * (taxable_growth_factor ** inputs.years_to_withdrawal)
        
        # Net Roth value after accounting for taxable account impact
        roth_future_net = roth_future_value - taxable_opportunity_cost
        
        analysis_notes.append(
            f"Paying ${conversion_tax:,.0f} tax from taxable account. "
            f"Opportunity cost: ${taxable_opportunity_cost:,.0f}"
        )
    else:
        # Paying from IRA - reduces amount that can be converted
        net_conversion = inputs.conversion_amount - conversion_tax
        roth_future_value = net_conversion * growth_factor
        roth_future_net = roth_future_value  # Already tax-free
        
        analysis_notes.append(
            f"Paying ${conversion_tax:,.0f} tax from IRA. "
            f"Net conversion: ${net_conversion:,.0f}"
        )
    
    logger.debug(f"Roth IRA future value: ${roth_future_net:,.2f}")
    
    # Step 4: Calculate BETR
    # BETR is the future tax rate that makes Traditional and Roth outcomes equal
    
    if inputs.pay_from_taxable:
        # Formula: BETR = 1 - (Roth_FV / Traditional_FV_gross)
        # This accounts for the benefit of moving taxable dollars to tax-advantaged space
        betr = 1 - (roth_future_net / traditional_future_gross)
    else:
        # Formula: BETR = (Roth_FV / Traditional_FV_gross) * (1 / (1 - current_rate))
        # This accounts for the reduction in IRA assets from paying tax
        betr = (roth_future_net / traditional_future_gross) / (1 - inputs.current_marginal_rate)
    
    # Step 5: Adjust BETR for nontaxable basis
    if inputs.nontaxable_basis > 0:
        # Higher nontaxable basis increases BETR (makes conversion more attractive)
        # The adjustment is proportional to the percentage of nontaxable basis
        basis_percentage = inputs.nontaxable_basis / inputs.traditional_ira_balance
        basis_adjustment = basis_percentage * NONTAXABLE_BASIS_ADJUSTMENT_FACTOR
        betr += basis_adjustment
        analysis_notes.append(
            f"BETR increased by {basis_adjustment:.2%} due to {basis_percentage:.1%} nontaxable basis"
        )
    
    # Step 6: Adjust BETR for future backdoor Roth contributions
    if inputs.future_backdoor_roth and inputs.backdoor_contribution_years > 0:
        # Converting now enables future backdoor Roth contributions by eliminating pro-rata rule
        # This increases the BETR (makes conversion more attractive)
        # Benefit scales with number of years of future contributions
        backdoor_benefit = BACKDOOR_ROTH_BENEFIT_FACTOR * (inputs.backdoor_contribution_years / 10)
        betr += backdoor_benefit
        analysis_notes.append(
            f"BETR increased by {backdoor_benefit:.2%} due to {inputs.backdoor_contribution_years} "
            f"years of future backdoor Roth contributions"
        )
    
    # Step 7: Calculate net benefit
    net_benefit = roth_future_net - traditional_future_net
    
    # Step 8: Determine recommendation
    # Conversion is recommended if expected future tax rate > BETR
    # BETR is the break-even point - if future rate exceeds it, conversion is beneficial
    conversion_recommended = inputs.expected_future_rate > betr
    
    if conversion_recommended:
        analysis_notes.append(
            f"✓ CONVERSION RECOMMENDED: Expected Future Rate ({inputs.expected_future_rate:.2%}) > BETR ({betr:.2%})"
        )
        analysis_notes.append(
            f"Conversion is beneficial because your expected future tax rate exceeds the break-even rate"
        )
    else:
        analysis_notes.append(
            f"✗ CONVERSION NOT RECOMMENDED: Expected Future Rate ({inputs.expected_future_rate:.2%}) ≤ BETR ({betr:.2%})"
        )
        analysis_notes.append(
            f"Conversion not beneficial unless future tax rate exceeds {betr:.2%}"
        )
    
    logger.info(f"BETR calculated: {betr:.2%}, Recommended: {conversion_recommended}")
    
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
    
    # Example 1: Basic conversion analysis
    print("Example 1: Basic Conversion Analysis")
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
