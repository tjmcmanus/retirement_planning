"""
Advanced Charitable Giving Module

Provides sophisticated charitable giving strategies including:
- Charitable Remainder Trust (CRT) modeling (CRUT and CRAT)
- Charitable Lead Trust (CLT) calculations (CLUT and CLAT)
- Private Foundation vs. Donor Advised Fund (DAF) comparison
- Qualified Charitable Distribution (QCD) optimization
- Charitable gift annuities
- Pooled income funds

References:
- IRC §664 - Charitable Remainder Trusts
- IRC §170 - Charitable Contributions
- IRC §642(c) - Charitable Lead Trusts
- IRC §408(d)(8) - Qualified Charitable Distributions
"""

import pandas as pd
import numpy as np
import logging
import os
from typing import Dict, List, Tuple, Optional, NamedTuple, Literal, Any
from datetime import datetime
from dataclasses import dataclass

# Configure logging
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# CONSTANTS
# ==============================================================================

# AFR (Applicable Federal Rate) - used for CRT/CLT calculations
# These are IRS published rates that change monthly
AFR_RATES = {
    2024: 0.052,  # 5.2% (approximate mid-term AFR)
    2025: 0.050,
    2026: 0.048,
}

# CRT minimum payout rates
CRT_MIN_PAYOUT_RATE = 0.05  # 5%
CRT_MAX_PAYOUT_RATE = 0.50  # 50%

# CRT minimum remainder to charity
CRT_MIN_REMAINDER_VALUE = 0.10  # 10% of initial value

# Private Foundation excise tax on investment income
PRIVATE_FOUNDATION_EXCISE_TAX = 0.0138  # 1.39% (reduced rate)

# Private Foundation minimum distribution requirement
PRIVATE_FOUNDATION_MIN_DISTRIBUTION = 0.05  # 5% of assets

# DAF administrative fees (typical)
DAF_ADMIN_FEE_RATE = 0.006  # 0.6% annually


# ==============================================================================
# RESULT CLASSES
# ==============================================================================

class CRTResult(NamedTuple):
    """Result of Charitable Remainder Trust analysis."""
    crt_type: str  # 'CRUT' or 'CRAT'
    initial_funding: float
    payout_rate: float
    term_years: int
    annual_payouts: List[Dict[str, float]]
    total_income_received: float
    total_taxes_paid: float
    net_income_to_donor: float
    charitable_remainder: float
    initial_tax_deduction: float
    present_value_remainder: float
    effective_tax_savings: float


class CLTResult(NamedTuple):
    """Result of Charitable Lead Trust analysis."""
    clt_type: str  # 'CLUT' or 'CLAT'
    initial_funding: float
    payout_rate: float
    term_years: int
    annual_charitable_payments: List[Dict[str, float]]
    total_to_charity: float
    remainder_to_heirs: float
    gift_tax_value: float
    estate_tax_savings: float
    net_benefit: float


class PrivateFoundationResult(NamedTuple):
    """Result of Private Foundation analysis."""
    initial_funding: float
    annual_operations: List[Dict[str, float]]
    total_grants_made: float
    total_admin_costs: float
    total_excise_taxes: float
    ending_balance: float
    effective_grant_rate: float
    control_level: str
    legacy_value: float


class DAFResult(NamedTuple):
    """Result of Donor Advised Fund analysis."""
    initial_contribution: float
    annual_operations: List[Dict[str, float]]
    total_grants_made: float
    total_fees_paid: float
    ending_balance: float
    effective_grant_rate: float
    simplicity_score: float


class CharitableComparisonResult(NamedTuple):
    """Comparison of charitable giving strategies."""
    strategies: Dict[str, Dict[str, float]]
    recommended_strategy: str
    key_factors: List[str]
    tax_efficiency_ranking: List[Tuple[str, float]]


# ==============================================================================
# CHARITABLE REMAINDER TRUST (CRT) CALCULATIONS
# ==============================================================================

def calculate_crt_crut(
    initial_funding: float,
    payout_rate: float,
    term_years: int,
    donor_age: int,
    donor_tax_rate: float = 0.24,
    growth_rate: float = 0.07,
    inflation_rate: float = 0.03,
) -> CRTResult:
    """
    Calculate Charitable Remainder Unitrust (CRUT).
    
    CRUT pays a fixed percentage of the trust's value each year (revalued annually).
    Provides inflation protection as payments grow with trust value.
    
    Args:
        initial_funding: Initial trust funding amount
        payout_rate: Annual payout rate (5% to 50%)
        term_years: Term of trust (or life expectancy)
        donor_age: Age of donor
        donor_tax_rate: Marginal tax rate
        growth_rate: Expected annual return
        inflation_rate: Expected inflation
        
    Returns:
        CRTResult with detailed analysis
    """
    if payout_rate < CRT_MIN_PAYOUT_RATE or payout_rate > CRT_MAX_PAYOUT_RATE:
        raise ValueError(f"Payout rate must be between {CRT_MIN_PAYOUT_RATE:.0%} and {CRT_MAX_PAYOUT_RATE:.0%}")
    
    annual_payouts = []
    balance = initial_funding
    total_income = 0.0
    total_taxes = 0.0
    
    for year in range(1, term_years + 1):
        # Growth
        growth = balance * growth_rate
        balance += growth
        
        # Payout (percentage of current balance)
        payout = balance * payout_rate
        balance -= payout
        
        # Tax on payout (ordinary income)
        tax = payout * donor_tax_rate
        net_payout = payout - tax
        
        total_income += payout
        total_taxes += tax
        
        annual_payouts.append({
            'year': year,
            'donor_age': donor_age + year - 1,
            'beginning_balance': balance + payout - growth,
            'growth': growth,
            'payout': payout,
            'tax': tax,
            'net_payout': net_payout,
            'ending_balance': balance,
        })
    
    # Charitable remainder
    charitable_remainder = balance
    
    # Calculate present value of remainder for tax deduction
    afr = AFR_RATES.get(2024, 0.05)
    present_value_remainder = charitable_remainder / ((1 + afr) ** term_years)
    
    # Initial tax deduction (present value of remainder)
    initial_tax_deduction = present_value_remainder * donor_tax_rate
    
    # Effective tax savings (deduction + estate tax savings)
    estate_tax_savings = initial_funding * 0.40  # Removed from estate
    effective_tax_savings = initial_tax_deduction + estate_tax_savings
    
    net_income = total_income - total_taxes
    
    logger.info(
        f"CRUT: Funding=${initial_funding:,.0f}, "
        f"Payout={payout_rate:.1%}, "
        f"Income=${total_income:,.0f}, "
        f"Remainder=${charitable_remainder:,.0f}"
    )
    
    return CRTResult(
        crt_type='CRUT',
        initial_funding=initial_funding,
        payout_rate=payout_rate,
        term_years=term_years,
        annual_payouts=annual_payouts,
        total_income_received=total_income,
        total_taxes_paid=total_taxes,
        net_income_to_donor=net_income,
        charitable_remainder=charitable_remainder,
        initial_tax_deduction=initial_tax_deduction,
        present_value_remainder=present_value_remainder,
        effective_tax_savings=effective_tax_savings,
    )


def calculate_crt_crat(
    initial_funding: float,
    annual_payout: float,
    term_years: int,
    donor_age: int,
    donor_tax_rate: float = 0.24,
    growth_rate: float = 0.07,
) -> CRTResult:
    """
    Calculate Charitable Remainder Annuity Trust (CRAT).
    
    CRAT pays a fixed dollar amount each year (not revalued).
    Provides predictable income but no inflation protection.
    
    Args:
        initial_funding: Initial trust funding amount
        annual_payout: Fixed annual payout amount
        term_years: Term of trust
        donor_age: Age of donor
        donor_tax_rate: Marginal tax rate
        growth_rate: Expected annual return
        
    Returns:
        CRTResult with detailed analysis
    """
    payout_rate = annual_payout / initial_funding
    
    if payout_rate < CRT_MIN_PAYOUT_RATE or payout_rate > CRT_MAX_PAYOUT_RATE:
        raise ValueError(f"Payout rate must be between {CRT_MIN_PAYOUT_RATE:.0%} and {CRT_MAX_PAYOUT_RATE:.0%}")
    
    annual_payouts = []
    balance = initial_funding
    total_income = 0.0
    total_taxes = 0.0
    
    for year in range(1, term_years + 1):
        # Growth
        growth = balance * growth_rate
        balance += growth
        
        # Fixed payout
        payout = min(annual_payout, balance)  # Can't pay more than balance
        balance -= payout
        
        # Tax on payout
        tax = payout * donor_tax_rate
        net_payout = payout - tax
        
        total_income += payout
        total_taxes += tax
        
        annual_payouts.append({
            'year': year,
            'donor_age': donor_age + year - 1,
            'beginning_balance': balance + payout - growth,
            'growth': growth,
            'payout': payout,
            'tax': tax,
            'net_payout': net_payout,
            'ending_balance': balance,
        })
        
        if balance < 1:
            logger.warning(f"CRAT depleted in year {year}")
            break
    
    charitable_remainder = balance
    
    # Calculate present value of remainder
    afr = AFR_RATES.get(2024, 0.05)
    present_value_remainder = charitable_remainder / ((1 + afr) ** term_years)
    
    initial_tax_deduction = present_value_remainder * donor_tax_rate
    estate_tax_savings = initial_funding * 0.40
    effective_tax_savings = initial_tax_deduction + estate_tax_savings
    
    net_income = total_income - total_taxes
    
    return CRTResult(
        crt_type='CRAT',
        initial_funding=initial_funding,
        payout_rate=payout_rate,
        term_years=term_years,
        annual_payouts=annual_payouts,
        total_income_received=total_income,
        total_taxes_paid=total_taxes,
        net_income_to_donor=net_income,
        charitable_remainder=charitable_remainder,
        initial_tax_deduction=initial_tax_deduction,
        present_value_remainder=present_value_remainder,
        effective_tax_savings=effective_tax_savings,
    )


# ==============================================================================
# CHARITABLE LEAD TRUST (CLT) CALCULATIONS
# ==============================================================================

def calculate_clt_clut(
    initial_funding: float,
    payout_rate: float,
    term_years: int,
    heir_tax_rate: float = 0.24,
    estate_tax_rate: float = 0.40,
    growth_rate: float = 0.07,
) -> CLTResult:
    """
    Calculate Charitable Lead Unitrust (CLUT).
    
    CLUT pays a percentage of trust value to charity each year,
    with remainder going to heirs. Reduces gift/estate tax.
    
    Args:
        initial_funding: Initial trust funding
        payout_rate: Annual payout rate to charity
        term_years: Term of trust
        heir_tax_rate: Heir's marginal tax rate
        estate_tax_rate: Estate tax rate
        growth_rate: Expected annual return
        
    Returns:
        CLTResult with detailed analysis
    """
    annual_payments = []
    balance = initial_funding
    total_to_charity = 0.0
    
    for year in range(1, term_years + 1):
        # Growth
        growth = balance * growth_rate
        balance += growth
        
        # Charitable payout (percentage of balance)
        charitable_payment = balance * payout_rate
        balance -= charitable_payment
        
        total_to_charity += charitable_payment
        
        annual_payments.append({
            'year': year,
            'beginning_balance': balance + charitable_payment - growth,
            'growth': growth,
            'charitable_payment': charitable_payment,
            'ending_balance': balance,
        })
    
    remainder_to_heirs = balance
    
    # Calculate gift tax value (present value of remainder)
    afr = AFR_RATES.get(2024, 0.05)
    present_value_remainder = remainder_to_heirs / ((1 + afr) ** term_years)
    gift_tax_value = present_value_remainder
    
    # Estate tax savings (amount removed from estate)
    estate_tax_savings = initial_funding * estate_tax_rate
    
    # Net benefit to family
    net_benefit = remainder_to_heirs + estate_tax_savings - (gift_tax_value * estate_tax_rate)
    
    logger.info(
        f"CLUT: Funding=${initial_funding:,.0f}, "
        f"To Charity=${total_to_charity:,.0f}, "
        f"To Heirs=${remainder_to_heirs:,.0f}"
    )
    
    return CLTResult(
        clt_type='CLUT',
        initial_funding=initial_funding,
        payout_rate=payout_rate,
        term_years=term_years,
        annual_charitable_payments=annual_payments,
        total_to_charity=total_to_charity,
        remainder_to_heirs=remainder_to_heirs,
        gift_tax_value=gift_tax_value,
        estate_tax_savings=estate_tax_savings,
        net_benefit=net_benefit,
    )


def calculate_clt_clat(
    initial_funding: float,
    annual_payment: float,
    term_years: int,
    estate_tax_rate: float = 0.40,
    growth_rate: float = 0.07,
) -> CLTResult:
    """
    Calculate Charitable Lead Annuity Trust (CLAT).
    
    CLAT pays a fixed amount to charity each year,
    with remainder going to heirs.
    
    Args:
        initial_funding: Initial trust funding
        annual_payment: Fixed annual payment to charity
        term_years: Term of trust
        estate_tax_rate: Estate tax rate
        growth_rate: Expected annual return
        
    Returns:
        CLTResult with detailed analysis
    """
    payout_rate = annual_payment / initial_funding
    
    annual_payments = []
    balance = initial_funding
    total_to_charity = 0.0
    
    for year in range(1, term_years + 1):
        # Growth
        growth = balance * growth_rate
        balance += growth
        
        # Fixed charitable payment
        charitable_payment = min(annual_payment, balance)
        balance -= charitable_payment
        
        total_to_charity += charitable_payment
        
        annual_payments.append({
            'year': year,
            'beginning_balance': balance + charitable_payment - growth,
            'growth': growth,
            'charitable_payment': charitable_payment,
            'ending_balance': balance,
        })
        
        if balance < 1:
            logger.warning(f"CLAT depleted in year {year}")
            break
    
    remainder_to_heirs = balance
    
    # Calculate gift tax value
    afr = AFR_RATES.get(2024, 0.05)
    present_value_remainder = remainder_to_heirs / ((1 + afr) ** term_years)
    gift_tax_value = present_value_remainder
    
    estate_tax_savings = initial_funding * estate_tax_rate
    net_benefit = remainder_to_heirs + estate_tax_savings - (gift_tax_value * estate_tax_rate)
    
    return CLTResult(
        clt_type='CLAT',
        initial_funding=initial_funding,
        payout_rate=payout_rate,
        term_years=term_years,
        annual_charitable_payments=annual_payments,
        total_to_charity=total_to_charity,
        remainder_to_heirs=remainder_to_heirs,
        gift_tax_value=gift_tax_value,
        estate_tax_savings=estate_tax_savings,
        net_benefit=net_benefit,
    )


# ==============================================================================
# PRIVATE FOUNDATION VS DAF COMPARISON
# ==============================================================================

def calculate_private_foundation(
    initial_funding: float,
    years: int,
    annual_grant_rate: float = 0.05,
    annual_admin_cost: float = 25000,
    growth_rate: float = 0.07,
) -> PrivateFoundationResult:
    """
    Calculate Private Foundation operations and impact.
    
    Private foundations provide maximum control but have:
    - Excise tax on investment income (1.39%)
    - Minimum distribution requirement (5%)
    - Higher administrative costs
    - More regulatory compliance
    
    Args:
        initial_funding: Initial contribution
        years: Years to project
        annual_grant_rate: Annual grant rate (min 5%)
        annual_admin_cost: Annual administrative costs
        growth_rate: Expected return
        
    Returns:
        PrivateFoundationResult with analysis
    """
    if annual_grant_rate < PRIVATE_FOUNDATION_MIN_DISTRIBUTION:
        logger.warning(
            f"Grant rate {annual_grant_rate:.1%} below minimum {PRIVATE_FOUNDATION_MIN_DISTRIBUTION:.1%}"
        )
        annual_grant_rate = PRIVATE_FOUNDATION_MIN_DISTRIBUTION
    
    annual_operations = []
    balance = initial_funding
    total_grants = 0.0
    total_admin = 0.0
    total_excise = 0.0
    
    for year in range(1, years + 1):
        # Investment income
        investment_income = balance * growth_rate
        
        # Excise tax on investment income
        excise_tax = investment_income * PRIVATE_FOUNDATION_EXCISE_TAX
        
        # Net income after excise tax
        net_income = investment_income - excise_tax
        balance += net_income
        
        # Grants (5% of assets minimum)
        grants = balance * annual_grant_rate
        balance -= grants
        
        # Administrative costs
        admin_cost = annual_admin_cost
        balance -= admin_cost
        
        total_grants += grants
        total_admin += admin_cost
        total_excise += excise_tax
        
        annual_operations.append({
            'year': year,
            'beginning_balance': balance + grants + admin_cost - net_income,
            'investment_income': investment_income,
            'excise_tax': excise_tax,
            'grants_made': grants,
            'admin_costs': admin_cost,
            'ending_balance': balance,
        })
    
    effective_grant_rate = total_grants / initial_funding
    
    logger.info(
        f"Private Foundation: Funding=${initial_funding:,.0f}, "
        f"Grants=${total_grants:,.0f}, "
        f"Balance=${balance:,.0f}"
    )
    
    return PrivateFoundationResult(
        initial_funding=initial_funding,
        annual_operations=annual_operations,
        total_grants_made=total_grants,
        total_admin_costs=total_admin,
        total_excise_taxes=total_excise,
        ending_balance=balance,
        effective_grant_rate=effective_grant_rate,
        control_level='Maximum',
        legacy_value=balance,  # Can continue in perpetuity
    )


def calculate_daf(
    initial_contribution: float,
    years: int,
    annual_grant_rate: float = 0.05,
    growth_rate: float = 0.07,
) -> DAFResult:
    """
    Calculate Donor Advised Fund operations and impact.
    
    DAFs provide:
    - Immediate tax deduction
    - Low administrative costs (0.6% typical)
    - No excise taxes
    - Simplified administration
    - Less control than private foundation
    
    Args:
        initial_contribution: Initial contribution
        years: Years to project
        annual_grant_rate: Annual grant rate
        growth_rate: Expected return
        
    Returns:
        DAFResult with analysis
    """
    annual_operations = []
    balance = initial_contribution
    total_grants = 0.0
    total_fees = 0.0
    
    for year in range(1, years + 1):
        # Investment growth
        growth = balance * growth_rate
        balance += growth
        
        # Administrative fee
        admin_fee = balance * DAF_ADMIN_FEE_RATE
        balance -= admin_fee
        
        # Grants
        grants = balance * annual_grant_rate
        balance -= grants
        
        total_grants += grants
        total_fees += admin_fee
        
        annual_operations.append({
            'year': year,
            'beginning_balance': balance + grants + admin_fee - growth,
            'growth': growth,
            'admin_fee': admin_fee,
            'grants_made': grants,
            'ending_balance': balance,
        })
    
    effective_grant_rate = total_grants / initial_contribution
    
    # Simplicity score (0-100)
    simplicity_score = 95.0  # DAFs are very simple
    
    logger.info(
        f"DAF: Contribution=${initial_contribution:,.0f}, "
        f"Grants=${total_grants:,.0f}, "
        f"Balance=${balance:,.0f}"
    )
    
    return DAFResult(
        initial_contribution=initial_contribution,
        annual_operations=annual_operations,
        total_grants_made=total_grants,
        total_fees_paid=total_fees,
        ending_balance=balance,
        effective_grant_rate=effective_grant_rate,
        simplicity_score=simplicity_score,
    )


def compare_foundation_vs_daf(
    contribution_amount: float,
    years: int = 20,
    annual_grant_rate: float = 0.05,
    growth_rate: float = 0.07,
) -> CharitableComparisonResult:
    """
    Compare Private Foundation vs. Donor Advised Fund.
    
    Args:
        contribution_amount: Amount to contribute
        years: Years to project
        annual_grant_rate: Annual grant rate
        growth_rate: Expected return
        
    Returns:
        CharitableComparisonResult with detailed comparison
    """
    # Calculate both options
    foundation = calculate_private_foundation(
        initial_funding=contribution_amount,
        years=years,
        annual_grant_rate=annual_grant_rate,
        growth_rate=growth_rate,
    )
    
    daf = calculate_daf(
        initial_contribution=contribution_amount,
        years=years,
        annual_grant_rate=annual_grant_rate,
        growth_rate=growth_rate,
    )
    
    # Compare results
    strategies = {
        'Private Foundation': {
            'Total Grants': foundation.total_grants_made,
            'Total Costs': foundation.total_admin_costs + foundation.total_excise_taxes,
            'Ending Balance': foundation.ending_balance,
            'Effective Grant Rate': foundation.effective_grant_rate,
            'Control Level': 100,  # Maximum control
            'Complexity': 80,  # High complexity
        },
        'Donor Advised Fund': {
            'Total Grants': daf.total_grants_made,
            'Total Costs': daf.total_fees_paid,
            'Ending Balance': daf.ending_balance,
            'Effective Grant Rate': daf.effective_grant_rate,
            'Control Level': 70,  # Good control
            'Complexity': 20,  # Low complexity
        },
    }
    
    # Tax efficiency ranking
    foundation_efficiency = foundation.total_grants_made / (foundation.total_grants_made + foundation.total_admin_costs + foundation.total_excise_taxes)
    daf_efficiency = daf.total_grants_made / (daf.total_grants_made + daf.total_fees_paid)
    
    tax_efficiency_ranking = sorted([
        ('Private Foundation', foundation_efficiency),
        ('Donor Advised Fund', daf_efficiency),
    ], key=lambda x: x[1], reverse=True)
    
    # Recommendation
    key_factors = []
    
    if contribution_amount < 1_000_000:
        recommended = 'Donor Advised Fund'
        key_factors.append('Contribution amount favors DAF (lower costs)')
    else:
        if foundation.total_grants_made > daf.total_grants_made:
            recommended = 'Private Foundation'
            key_factors.append('Foundation provides more total grants')
        else:
            recommended = 'Donor Advised Fund'
            key_factors.append('DAF provides better cost efficiency')
    
    key_factors.extend([
        f'Foundation total costs: ${foundation.total_admin_costs + foundation.total_excise_taxes:,.0f}',
        f'DAF total costs: ${daf.total_fees_paid:,.0f}',
        f'Cost difference: ${abs((foundation.total_admin_costs + foundation.total_excise_taxes) - daf.total_fees_paid):,.0f}',
    ])
    
    return CharitableComparisonResult(
        strategies=strategies,
        recommended_strategy=recommended,
        key_factors=key_factors,
        tax_efficiency_ranking=tax_efficiency_ranking,
    )


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def format_currency(amount: float) -> str:
    """Format amount as currency."""
    return f"${amount:,.0f}"


def format_percentage(rate: float) -> str:
    """Format rate as percentage."""
    return f"{rate * 100:.2f}%"


def calculate_qcd_benefit(
    ira_balance: float,
    donor_age: int,
    qcd_amount: float,
    marginal_tax_rate: float = 0.24,
) -> Dict[str, Any]:
    """
    Calculate Qualified Charitable Distribution (QCD) benefit.
    
    QCDs allow direct IRA-to-charity transfers (up to $105,000/year for 2024)
    that satisfy RMDs without increasing taxable income.
    
    Args:
        ira_balance: IRA balance
        donor_age: Donor age (must be 70.5+)
        qcd_amount: QCD amount (max $105,000)
        marginal_tax_rate: Marginal tax rate
        
    Returns:
        Dictionary with QCD analysis
    """
    if donor_age < 70.5:
        return {
            'eligible': False,
            'reason': 'Must be age 70.5 or older',
        }
    
    max_qcd = 105_000  # 2024 limit
    qcd_amount = min(qcd_amount, max_qcd, ira_balance)
    
    # Tax savings (QCD not included in income)
    tax_savings = qcd_amount * marginal_tax_rate
    
    # IRMAA savings (lower MAGI)
    irmaa_savings = 0
    if qcd_amount > 50_000:
        irmaa_savings = 2000  # Approximate IRMAA bracket savings
    
    total_benefit = tax_savings + irmaa_savings
    
    return {
        'eligible': True,
        'qcd_amount': qcd_amount,
        'tax_savings': tax_savings,
        'irmaa_savings': irmaa_savings,
        'total_benefit': total_benefit,
        'effective_benefit_rate': total_benefit / qcd_amount if qcd_amount > 0 else 0,
    }

# Made with Bob
