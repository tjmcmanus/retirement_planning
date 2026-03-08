"""
Health Savings Account (HSA) Integration Module

Comprehensive HSA planning and optimization tools including:
- HSA contribution tracking and limits
- HSA investment growth projections
- HSA withdrawal strategies in retirement
- Triple tax advantage optimization
- Medicare coordination

HSAs offer triple tax advantages:
1. Tax-deductible contributions
2. Tax-free growth
3. Tax-free withdrawals for qualified medical expenses
"""

import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# 2024 HSA Contribution Limits
HSA_LIMIT_INDIVIDUAL_2024 = 4_150
HSA_LIMIT_FAMILY_2024 = 8_300
HSA_CATCHUP_AGE = 55
HSA_CATCHUP_AMOUNT = 1_000

# Historical HSA limit increases (average ~3% annually)
HSA_LIMIT_INFLATION_RATE = 0.03

# Medicare enrollment age (HSA contributions must stop)
MEDICARE_ENROLLMENT_AGE = 65

# Typical HSA investment returns (conservative to aggressive)
HSA_CONSERVATIVE_RETURN = 0.04
HSA_MODERATE_RETURN = 0.06
HSA_AGGRESSIVE_RETURN = 0.08

# Average healthcare costs in retirement (Fidelity 2024 estimate)
# $165,000 per person for healthcare costs in retirement
RETIREMENT_HEALTHCARE_COST_PER_PERSON = 165_000
HEALTHCARE_INFLATION_RATE = 0.05  # Healthcare inflation typically higher


@dataclass
class HSAContributionPlan:
    """HSA contribution plan details"""
    year: int
    age: int
    coverage_type: str  # 'individual' or 'family'
    contribution_limit: float
    employer_contribution: float
    employee_contribution: float
    total_contribution: float
    catchup_eligible: bool
    catchup_amount: float


@dataclass
class HSAProjection:
    """HSA balance projection over time"""
    current_balance: float
    years_to_medicare: int
    total_contributions: float
    investment_growth: float
    final_balance: float
    annual_projections: List[Dict]


@dataclass
class HSAWithdrawalStrategy:
    """HSA withdrawal strategy in retirement"""
    strategy_name: str
    annual_medical_expenses: float
    hsa_withdrawals: float
    taxable_withdrawals: float
    years_hsa_lasts: int
    total_tax_savings: float
    notes: List[str]


@dataclass
class HSATaxAdvantageAnalysis:
    """Analysis of HSA triple tax advantage"""
    total_contributions: float
    tax_savings_contributions: float
    investment_growth: float
    tax_savings_growth: float
    qualified_withdrawals: float
    tax_savings_withdrawals: float
    total_tax_advantage: float
    equivalent_taxable_account: float


def get_hsa_contribution_limit(year: int, coverage_type: str, age: int) -> float:
    """
    Get HSA contribution limit for a given year.
    
    Args:
        year: Tax year
        coverage_type: 'individual' or 'family'
        age: Age of account holder
        
    Returns:
        Maximum HSA contribution limit
    """
    # Base limits for 2024
    if coverage_type == 'individual':
        base_limit = HSA_LIMIT_INDIVIDUAL_2024
    else:
        base_limit = HSA_LIMIT_FAMILY_2024
    
    # Project future limits with inflation
    years_from_2024 = year - 2024
    projected_limit = base_limit * ((1 + HSA_LIMIT_INFLATION_RATE) ** years_from_2024)
    
    # Round to nearest $50 (IRS typically rounds)
    projected_limit = round(projected_limit / 50) * 50
    
    # Add catch-up contribution if eligible
    if age >= HSA_CATCHUP_AGE:
        projected_limit += HSA_CATCHUP_AMOUNT
    
    return projected_limit


def create_hsa_contribution_plan(
    current_age: int,
    coverage_type: str,
    employer_contribution: float,
    max_out_contributions: bool = True,
    custom_employee_contribution: Optional[float] = None
) -> List[HSAContributionPlan]:
    """
    Create HSA contribution plan until Medicare enrollment.
    
    Args:
        current_age: Current age
        coverage_type: 'individual' or 'family'
        employer_contribution: Annual employer HSA contribution
        max_out_contributions: Whether to max out employee contributions
        custom_employee_contribution: Custom employee contribution amount
        
    Returns:
        List of HSAContributionPlan for each year until Medicare
    """
    plans = []
    current_year = 2024
    
    for age in range(current_age, MEDICARE_ENROLLMENT_AGE):
        year = current_year + (age - current_age)
        
        # Get contribution limit
        limit = get_hsa_contribution_limit(year, coverage_type, age)
        
        # Determine employee contribution
        if max_out_contributions:
            employee_contrib = max(0, limit - employer_contribution)
        elif custom_employee_contribution is not None:
            employee_contrib = min(custom_employee_contribution, limit - employer_contribution)
        else:
            employee_contrib = 0
        
        total_contrib = employer_contribution + employee_contrib
        
        # Check catch-up eligibility
        catchup_eligible = age >= HSA_CATCHUP_AGE
        catchup_amount = HSA_CATCHUP_AMOUNT if catchup_eligible else 0
        
        plans.append(HSAContributionPlan(
            year=year,
            age=age,
            coverage_type=coverage_type,
            contribution_limit=limit,
            employer_contribution=employer_contribution,
            employee_contribution=employee_contrib,
            total_contribution=total_contrib,
            catchup_eligible=catchup_eligible,
            catchup_amount=catchup_amount
        ))
    
    return plans


def project_hsa_growth(
    current_balance: float,
    current_age: int,
    coverage_type: str,
    employer_contribution: float,
    employee_contribution: float,
    investment_return: float = HSA_MODERATE_RETURN,
    annual_medical_expenses: float = 0
) -> HSAProjection:
    """
    Project HSA balance growth until Medicare enrollment.
    
    Args:
        current_balance: Current HSA balance
        current_age: Current age
        coverage_type: 'individual' or 'family'
        employer_contribution: Annual employer contribution
        employee_contribution: Annual employee contribution
        investment_return: Expected annual return
        annual_medical_expenses: Annual medical expenses paid from HSA
        
    Returns:
        HSAProjection with detailed growth projections
    """
    balance = current_balance
    total_contributions = 0
    total_growth = 0
    annual_projections = []
    
    years_to_medicare = max(0, MEDICARE_ENROLLMENT_AGE - current_age)
    
    for year in range(years_to_medicare):
        age = current_age + year
        
        # Get contribution limit
        limit = get_hsa_contribution_limit(2024 + year, coverage_type, age)
        
        # Calculate actual contribution (capped at limit)
        total_contrib = min(employer_contribution + employee_contribution, limit)
        
        # Add contributions
        balance += total_contrib
        total_contributions += total_contrib
        
        # Subtract medical expenses
        balance -= annual_medical_expenses
        
        # Apply investment growth
        growth = balance * investment_return
        balance += growth
        total_growth += growth
        
        annual_projections.append({
            'year': 2024 + year,
            'age': age,
            'beginning_balance': balance - growth - total_contrib + annual_medical_expenses,
            'contributions': total_contrib,
            'medical_expenses': annual_medical_expenses,
            'investment_growth': growth,
            'ending_balance': balance
        })
    
    return HSAProjection(
        current_balance=current_balance,
        years_to_medicare=years_to_medicare,
        total_contributions=total_contributions,
        investment_growth=total_growth,
        final_balance=balance,
        annual_projections=annual_projections
    )


def analyze_hsa_withdrawal_strategies(
    hsa_balance_at_retirement: float,
    annual_medical_expenses: float,
    retirement_age: int,
    life_expectancy: int,
    marginal_tax_rate: float
) -> List[HSAWithdrawalStrategy]:
    """
    Analyze different HSA withdrawal strategies in retirement.
    
    Args:
        hsa_balance_at_retirement: HSA balance at retirement
        annual_medical_expenses: Expected annual medical expenses
        retirement_age: Age at retirement
        life_expectancy: Expected life expectancy
        marginal_tax_rate: Marginal tax rate for taxable withdrawals
        
    Returns:
        List of HSAWithdrawalStrategy options
    """
    strategies = []
    years_in_retirement = life_expectancy - retirement_age
    
    # Strategy 1: Use HSA first for all medical expenses
    hsa_years = min(years_in_retirement, int(hsa_balance_at_retirement / annual_medical_expenses))
    remaining_years = years_in_retirement - hsa_years
    taxable_medical = remaining_years * annual_medical_expenses
    tax_savings_1 = hsa_balance_at_retirement * marginal_tax_rate
    
    strategies.append(HSAWithdrawalStrategy(
        strategy_name="HSA First - Deplete Early",
        annual_medical_expenses=annual_medical_expenses,
        hsa_withdrawals=hsa_balance_at_retirement,
        taxable_withdrawals=taxable_medical,
        years_hsa_lasts=hsa_years,
        total_tax_savings=tax_savings_1,
        notes=[
            f"Use HSA for first {hsa_years} years of retirement",
            f"Pay ${taxable_medical:,.0f} from taxable accounts later",
            "Provides certainty but may not be optimal"
        ]
    ))
    
    # Strategy 2: Preserve HSA, pay from taxable first
    # This allows HSA to continue growing tax-free
    years_taxable_first = min(10, years_in_retirement)  # Pay from taxable for 10 years
    taxable_medical_2 = years_taxable_first * annual_medical_expenses
    
    # HSA grows during this period
    hsa_growth_rate = HSA_MODERATE_RETURN
    grown_hsa = hsa_balance_at_retirement * ((1 + hsa_growth_rate) ** years_taxable_first)
    
    remaining_years_2 = years_in_retirement - years_taxable_first
    hsa_years_2 = min(remaining_years_2, int(grown_hsa / annual_medical_expenses))
    
    tax_savings_2 = grown_hsa * marginal_tax_rate
    
    strategies.append(HSAWithdrawalStrategy(
        strategy_name="Preserve HSA - Let It Grow",
        annual_medical_expenses=annual_medical_expenses,
        hsa_withdrawals=grown_hsa,
        taxable_withdrawals=taxable_medical_2,
        years_hsa_lasts=hsa_years_2,
        total_tax_savings=tax_savings_2,
        notes=[
            f"Pay from taxable accounts for first {years_taxable_first} years",
            f"HSA grows to ${grown_hsa:,.0f}",
            f"Use HSA for final {hsa_years_2} years",
            "Maximizes tax-free growth"
        ]
    ))
    
    # Strategy 3: Balanced approach - use HSA proportionally
    annual_hsa_withdrawal = hsa_balance_at_retirement / years_in_retirement
    annual_taxable = max(0, annual_medical_expenses - annual_hsa_withdrawal)
    total_taxable_3 = annual_taxable * years_in_retirement
    tax_savings_3 = hsa_balance_at_retirement * marginal_tax_rate
    
    strategies.append(HSAWithdrawalStrategy(
        strategy_name="Balanced - Proportional Use",
        annual_medical_expenses=annual_medical_expenses,
        hsa_withdrawals=hsa_balance_at_retirement,
        taxable_withdrawals=total_taxable_3,
        years_hsa_lasts=years_in_retirement,
        total_tax_savings=tax_savings_3,
        notes=[
            f"Withdraw ${annual_hsa_withdrawal:,.0f} from HSA annually",
            f"Supplement with ${annual_taxable:,.0f} from taxable accounts",
            "Spreads HSA benefit over entire retirement"
        ]
    ))
    
    return strategies


def calculate_hsa_triple_tax_advantage(
    total_contributions: float,
    investment_growth: float,
    marginal_tax_rate: float,
    capital_gains_rate: float,
    years_invested: int
) -> HSATaxAdvantageAnalysis:
    """
    Calculate the value of HSA's triple tax advantage.
    
    Args:
        total_contributions: Total HSA contributions over time
        investment_growth: Total investment growth in HSA
        marginal_tax_rate: Marginal income tax rate
        capital_gains_rate: Long-term capital gains tax rate
        years_invested: Years money was invested
        
    Returns:
        HSATaxAdvantageAnalysis showing tax savings
    """
    # Advantage 1: Tax-deductible contributions
    tax_savings_contributions = total_contributions * marginal_tax_rate
    
    # Advantage 2: Tax-free growth
    # In taxable account, would pay capital gains on growth
    tax_savings_growth = investment_growth * capital_gains_rate
    
    # Advantage 3: Tax-free withdrawals for medical expenses
    # Medical expenses are not deductible unless they exceed 7.5% of AGI
    # Assume 50% of medical expenses would not be deductible
    qualified_withdrawals = total_contributions + investment_growth
    tax_savings_withdrawals = qualified_withdrawals * 0.5 * marginal_tax_rate
    
    # Total tax advantage
    total_tax_advantage = (
        tax_savings_contributions +
        tax_savings_growth +
        tax_savings_withdrawals
    )
    
    # Calculate equivalent taxable account value needed
    # To have same after-tax value as HSA
    equivalent_taxable = qualified_withdrawals / (1 - marginal_tax_rate)
    
    return HSATaxAdvantageAnalysis(
        total_contributions=total_contributions,
        tax_savings_contributions=tax_savings_contributions,
        investment_growth=investment_growth,
        tax_savings_growth=tax_savings_growth,
        qualified_withdrawals=qualified_withdrawals,
        tax_savings_withdrawals=tax_savings_withdrawals,
        total_tax_advantage=total_tax_advantage,
        equivalent_taxable_account=equivalent_taxable
    )


def estimate_retirement_healthcare_costs(
    retirement_age: int,
    life_expectancy: int,
    include_ltc: bool = False,
    ltc_years: int = 3
) -> Dict[str, float]:
    """
    Estimate total healthcare costs in retirement.
    
    Args:
        retirement_age: Age at retirement
        life_expectancy: Expected life expectancy
        include_ltc: Whether to include long-term care costs
        ltc_years: Expected years of long-term care
        
    Returns:
        Dictionary with healthcare cost breakdown
    """
    years_in_retirement = life_expectancy - retirement_age
    
    # Base healthcare costs (Fidelity estimate)
    base_healthcare = RETIREMENT_HEALTHCARE_COST_PER_PERSON
    
    # Adjust for retirement age (earlier retirement = more years)
    age_factor = years_in_retirement / 20  # 20 years is baseline
    adjusted_healthcare = base_healthcare * age_factor
    
    # Medicare premiums (Part B + Part D + Medigap)
    # Average ~$6,000/year in 2024
    annual_medicare_premium = 6_000
    total_medicare_premiums = annual_medicare_premium * years_in_retirement
    
    # Out-of-pocket costs
    annual_oop = 3_000  # Deductibles, copays, etc.
    total_oop = annual_oop * years_in_retirement
    
    # Long-term care costs
    ltc_costs = 0
    if include_ltc:
        # Average nursing home cost ~$100,000/year
        annual_ltc = 100_000
        ltc_costs = annual_ltc * ltc_years
    
    total_costs = adjusted_healthcare + total_medicare_premiums + total_oop + ltc_costs
    
    return {
        'base_healthcare': adjusted_healthcare,
        'medicare_premiums': total_medicare_premiums,
        'out_of_pocket': total_oop,
        'long_term_care': ltc_costs,
        'total_healthcare_costs': total_costs,
        'annual_average': total_costs / years_in_retirement
    }


def optimize_hsa_contribution_strategy(
    current_age: int,
    current_income: float,
    current_hsa_balance: float,
    employer_contribution: float,
    marginal_tax_rate: float,
    coverage_type: str = 'family'
) -> Dict:
    """
    Optimize HSA contribution strategy.
    
    Args:
        current_age: Current age
        current_income: Current annual income
        current_hsa_balance: Current HSA balance
        employer_contribution: Annual employer HSA contribution
        marginal_tax_rate: Current marginal tax rate
        coverage_type: 'individual' or 'family'
        
    Returns:
        Dictionary with optimization recommendations
    """
    # Calculate maximum contribution
    max_contrib = get_hsa_contribution_limit(2024, coverage_type, current_age)
    employee_contrib = max_contrib - employer_contribution
    
    # Calculate tax savings from maxing out
    annual_tax_savings = employee_contrib * marginal_tax_rate
    
    # Project HSA growth to Medicare
    projection = project_hsa_growth(
        current_hsa_balance,
        current_age,
        coverage_type,
        employer_contribution,
        employee_contrib,
        HSA_MODERATE_RETURN
    )
    
    # Estimate retirement healthcare costs
    healthcare_costs = estimate_retirement_healthcare_costs(65, 85)
    
    # Calculate coverage percentage
    coverage_pct = (projection.final_balance / healthcare_costs['total_healthcare_costs']) * 100
    
    # Generate recommendation
    if coverage_pct >= 100:
        recommendation = "Excellent - HSA will cover all estimated healthcare costs"
    elif coverage_pct >= 75:
        recommendation = "Good - HSA will cover most healthcare costs"
    elif coverage_pct >= 50:
        recommendation = "Fair - Consider increasing contributions if possible"
    else:
        recommendation = "Low - Strongly consider maxing out HSA contributions"
    
    return {
        'max_annual_contribution': max_contrib,
        'recommended_employee_contribution': employee_contrib,
        'annual_tax_savings': annual_tax_savings,
        'projected_balance_at_65': projection.final_balance,
        'estimated_healthcare_costs': healthcare_costs['total_healthcare_costs'],
        'coverage_percentage': coverage_pct,
        'recommendation': recommendation,
        'years_to_medicare': projection.years_to_medicare,
        'total_contributions': projection.total_contributions,
        'investment_growth': projection.investment_growth
    }

# Made with Bob
