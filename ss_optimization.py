"""
Social Security Optimization Module

Advanced Social Security claiming strategies including:
- Spousal benefit optimization
- Break-even analysis for claiming ages
- Survivor benefit planning
- Earnings test impact modeling
- Net present value comparisons
- Longevity-adjusted recommendations

Based on Social Security Administration rules (2024+)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import logging

from ssi_calculator import (
    calculate_benefit_at_claiming_age,
    calculate_benefit_with_cola,
    FULL_RETIREMENT_AGE,
    MIN_CLAIMING_AGE,
    MAX_BENEFIT_AGE,
    DEFAULT_COLA_RATE
)

logger = logging.getLogger(__name__)

# Constants for spousal and survivor benefits
SPOUSAL_BENEFIT_RATE = 0.50  # Spouse can receive up to 50% of worker's FRA benefit
SURVIVOR_BENEFIT_RATE = 1.00  # Survivor can receive 100% of deceased's benefit
EARNINGS_TEST_LIMIT_UNDER_FRA = 22320  # 2024 limit (annual)
EARNINGS_TEST_LIMIT_FRA_YEAR = 59520   # 2024 limit for year reaching FRA
EARNINGS_TEST_REDUCTION_RATE_UNDER_FRA = 0.50  # $1 reduction for every $2 over limit
EARNINGS_TEST_REDUCTION_RATE_FRA_YEAR = 0.33   # $1 reduction for every $3 over limit

# Life expectancy assumptions (can be customized)
DEFAULT_LIFE_EXPECTANCY_MALE = 84
DEFAULT_LIFE_EXPECTANCY_FEMALE = 87
DEFAULT_DISCOUNT_RATE = 0.03  # 3% real discount rate for NPV calculations


@dataclass
class PersonProfile:
    """Profile for a person's Social Security benefits"""
    name: str
    birth_year: int
    fra_benefit: float  # Monthly benefit at FRA
    gender: str  # 'M' or 'F' for life expectancy defaults
    life_expectancy: int = 0  # Override default if provided (0 = use default)
    current_earnings: float = 0.0  # Annual earnings if working
    
    def __post_init__(self):
        if self.life_expectancy == 0:
            self.life_expectancy = (
                DEFAULT_LIFE_EXPECTANCY_MALE if self.gender == 'M'
                else DEFAULT_LIFE_EXPECTANCY_FEMALE
            )


@dataclass
class ClaimingStrategy:
    """Represents a Social Security claiming strategy"""
    person1_claiming_age: int
    person2_claiming_age: int
    strategy_name: str
    total_lifetime_benefits: float
    net_present_value: float
    break_even_age: Optional[int]
    notes: List[str]


@dataclass
class BreakEvenAnalysis:
    """Break-even analysis results"""
    early_age: int
    late_age: int
    break_even_age: int
    early_total: float
    late_total: float
    years_to_break_even: int
    monthly_difference: float


@dataclass
class EarningsTestImpact:
    """Impact of earnings test on benefits"""
    annual_earnings: float
    age: int
    monthly_benefit_before: float
    annual_reduction: float
    monthly_benefit_after: float
    months_withheld: int
    notes: str


def calculate_spousal_benefit(
    worker_fra_benefit: float,
    spouse_fra_benefit: float,
    spouse_claiming_age: int,
    worker_claiming_age: int,
    fra: int = FULL_RETIREMENT_AGE
) -> float:
    """
    Calculate spousal benefit amount.
    
    Spousal benefit is the greater of:
    1. Spouse's own benefit
    2. Up to 50% of worker's FRA benefit (reduced if claimed early)
    
    Args:
        worker_fra_benefit: Worker's monthly benefit at FRA
        spouse_fra_benefit: Spouse's own monthly benefit at FRA
        spouse_claiming_age: Age when spouse claims
        worker_claiming_age: Age when worker claims (must be claimed first)
        fra: Full Retirement Age
        
    Returns:
        Monthly spousal benefit amount
    """
    # Spouse's own benefit
    own_benefit = calculate_benefit_at_claiming_age(
        spouse_fra_benefit, spouse_claiming_age, fra
    )
    
    # Maximum spousal benefit (50% of worker's FRA benefit)
    max_spousal = worker_fra_benefit * SPOUSAL_BENEFIT_RATE
    
    # Apply early claiming reduction to spousal benefit if applicable
    if spouse_claiming_age < fra:
        months_early = (fra - spouse_claiming_age) * 12
        # Spousal benefits use same reduction schedule as retirement benefits
        from ssi_calculator import _calculate_early_claiming_reduction
        reduction = _calculate_early_claiming_reduction(months_early)
        max_spousal = max_spousal * (1 - reduction)
    
    # Spousal benefit is the excess over own benefit (if any)
    spousal_supplement = max(0, max_spousal - own_benefit)
    
    return own_benefit + spousal_supplement


def calculate_survivor_benefit(
    deceased_benefit: float,
    survivor_fra_benefit: float,
    survivor_claiming_age: int,
    deceased_claiming_age: int,
    fra: int = FULL_RETIREMENT_AGE
) -> float:
    """
    Calculate survivor benefit amount.
    
    Survivor can receive the greater of:
    1. Their own retirement benefit
    2. 100% of deceased's benefit (including any delayed credits)
    
    Args:
        deceased_benefit: Deceased's monthly benefit amount at time of death
        survivor_fra_benefit: Survivor's own FRA benefit
        survivor_claiming_age: Age when survivor claims survivor benefits
        deceased_claiming_age: Age when deceased claimed benefits
        fra: Full Retirement Age
        
    Returns:
        Monthly survivor benefit amount
    """
    # Survivor's own benefit
    own_benefit = calculate_benefit_at_claiming_age(
        survivor_fra_benefit, survivor_claiming_age, fra
    )
    
    # Survivor benefit is 100% of what deceased was receiving
    # (or would have received at FRA if they died before claiming)
    survivor_benefit = deceased_benefit
    
    # If survivor claims before FRA, survivor benefit may be reduced
    if survivor_claiming_age < fra:
        months_early = (fra - survivor_claiming_age) * 12
        # Survivor benefits have different reduction schedule (28.5% max reduction)
        reduction_rate = min(0.285, months_early * 0.00475)  # ~0.475% per month
        survivor_benefit = survivor_benefit * (1 - reduction_rate)
    
    return max(own_benefit, survivor_benefit)


def calculate_earnings_test_impact(
    annual_earnings: float,
    age: int,
    monthly_benefit: float,
    fra: int = FULL_RETIREMENT_AGE
) -> EarningsTestImpact:
    """
    Calculate impact of earnings test on Social Security benefits.
    
    The earnings test applies if you claim before FRA and continue working:
    - Under FRA: $1 reduction for every $2 earned over limit
    - Year reaching FRA: $1 reduction for every $3 earned over limit
    - At/after FRA: No earnings test
    
    Args:
        annual_earnings: Annual earnings from work
        age: Current age
        monthly_benefit: Monthly SS benefit before earnings test
        fra: Full Retirement Age
        
    Returns:
        EarningsTestImpact with reduction details
    """
    if age >= fra:
        return EarningsTestImpact(
            annual_earnings=annual_earnings,
            age=age,
            monthly_benefit_before=monthly_benefit,
            annual_reduction=0,
            monthly_benefit_after=monthly_benefit,
            months_withheld=0,
            notes="No earnings test at or after FRA"
        )
    
    # Determine which limit and reduction rate apply
    if age == fra - 1:  # Year reaching FRA
        limit = EARNINGS_TEST_LIMIT_FRA_YEAR
        reduction_rate = EARNINGS_TEST_REDUCTION_RATE_FRA_YEAR
        period = "year reaching FRA"
    else:  # Under FRA
        limit = EARNINGS_TEST_LIMIT_UNDER_FRA
        reduction_rate = EARNINGS_TEST_REDUCTION_RATE_UNDER_FRA
        period = "under FRA"
    
    # Calculate reduction
    excess_earnings = max(0, annual_earnings - limit)
    annual_reduction = excess_earnings * reduction_rate
    
    # Convert to monthly and calculate months withheld
    monthly_reduction = annual_reduction / 12
    months_withheld = int(annual_reduction / monthly_benefit) if monthly_benefit > 0 else 0
    
    # Adjusted benefit
    monthly_benefit_after = max(0, monthly_benefit - monthly_reduction)
    
    notes = (
        f"Earnings test ({period}): ${annual_earnings:,.0f} earnings exceeds "
        f"${limit:,.0f} limit by ${excess_earnings:,.0f}. "
        f"Benefit reduced by ${annual_reduction:,.0f}/year "
        f"(${monthly_reduction:,.0f}/month)"
    )
    
    return EarningsTestImpact(
        annual_earnings=annual_earnings,
        age=age,
        monthly_benefit_before=monthly_benefit,
        annual_reduction=annual_reduction,
        monthly_benefit_after=monthly_benefit_after,
        months_withheld=months_withheld,
        notes=notes
    )


def calculate_break_even_age(
    fra_benefit: float,
    early_age: int,
    late_age: int,
    cola_rate: float = DEFAULT_COLA_RATE,
    fra: int = FULL_RETIREMENT_AGE,
    portfolio_return: float = 0.07,
    include_opportunity_cost: bool = False
) -> BreakEvenAnalysis:
    """
    Calculate break-even age between two claiming strategies.
    
    This function compares cumulative benefits from early vs late claiming.
    Optionally accounts for portfolio opportunity cost when delaying SS.
    
    Args:
        fra_benefit: Monthly benefit at FRA
        early_age: Earlier claiming age
        late_age: Later claiming age
        cola_rate: Annual COLA rate
        fra: Full Retirement Age
        portfolio_return: Expected portfolio return rate (default: 7%)
        include_opportunity_cost: If True, accounts for lost portfolio growth
                                  from spending portfolio funds while delaying SS
        
    Returns:
        BreakEvenAnalysis with detailed comparison
        
    Note:
        When include_opportunity_cost=True, the calculation considers that
        delaying SS requires withdrawing from portfolio, which loses growth
        opportunity. This typically increases the break-even age by 2-4 years.
    """
    # Calculate monthly benefits at each age
    early_benefit = calculate_benefit_at_claiming_age(fra_benefit, early_age, fra)
    late_benefit = calculate_benefit_at_claiming_age(fra_benefit, late_age, fra)
    
    # Calculate cumulative benefits over time
    max_age = 100
    early_cumulative = 0
    late_cumulative = 0
    portfolio_opportunity_cost = 0
    break_even_age = None
    
    for age in range(early_age, max_age + 1):
        # Early claiming accumulates from early_age
        years_since_early = age - early_age
        if years_since_early >= 0:
            annual_early = early_benefit * 12 * ((1 + cola_rate) ** years_since_early)
            early_cumulative += annual_early
        
        # Late claiming accumulates from late_age
        years_since_late = age - late_age
        if years_since_late >= 0:
            annual_late = late_benefit * 12 * ((1 + cola_rate) ** years_since_late)
            late_cumulative += annual_late
        
        # Account for portfolio opportunity cost if enabled
        if include_opportunity_cost and age < late_age:
            # During delay period, must withdraw from portfolio
            # This amount loses opportunity to grow
            annual_withdrawal = early_benefit * 12 * ((1 + cola_rate) ** years_since_early)
            years_remaining = late_age - age
            # Calculate future value of this withdrawal if it had stayed invested
            opportunity_cost = annual_withdrawal * ((1 + portfolio_return) ** years_remaining)
            portfolio_opportunity_cost += opportunity_cost
        
        # Find break-even point
        if include_opportunity_cost:
            # Compare late claiming benefits vs (early benefits + opportunity cost)
            early_total_with_cost = early_cumulative + portfolio_opportunity_cost
            if break_even_age is None and late_cumulative >= early_total_with_cost and age >= late_age:
                break_even_age = age
        else:
            # Simple comparison without opportunity cost
            if break_even_age is None and late_cumulative >= early_cumulative and age >= late_age:
                break_even_age = age
    
    if break_even_age is None:
        break_even_age = max_age  # Never breaks even within lifespan
    
    return BreakEvenAnalysis(
        early_age=early_age,
        late_age=late_age,
        break_even_age=break_even_age,
        early_total=early_cumulative,
        late_total=late_cumulative,
        years_to_break_even=break_even_age - late_age,
        monthly_difference=late_benefit - early_benefit
    )


def calculate_break_even_with_portfolio_impact(
    fra_benefit: float,
    early_age: int,
    late_age: int,
    cola_rate: float = DEFAULT_COLA_RATE,
    portfolio_return: float = 0.07,
    fra: int = FULL_RETIREMENT_AGE
) -> Dict:
    """
    Calculate break-even age with and without portfolio opportunity cost.
    
    This provides a comprehensive comparison showing:
    1. Simple break-even (just comparing SS benefits)
    2. Portfolio-adjusted break-even (accounting for lost growth)
    
    Args:
        fra_benefit: Monthly benefit at FRA
        early_age: Earlier claiming age
        late_age: Later claiming age
        cola_rate: Annual COLA rate
        portfolio_return: Expected portfolio return rate
        fra: Full Retirement Age
        
    Returns:
        Dictionary with 'simple' and 'portfolio_adjusted' BreakEvenAnalysis,
        plus 'additional_years' and 'portfolio_return_assumption'
        
    Example:
        >>> results = calculate_break_even_with_portfolio_impact(2500, 62, 70)
        >>> print(f"Simple break-even: {results['simple'].break_even_age}")
        >>> print(f"With portfolio cost: {results['portfolio_adjusted'].break_even_age}")
        >>> print(f"Difference: {results['portfolio_adjusted'].break_even_age - results['simple'].break_even_age} years")
    """
    simple = calculate_break_even_age(
        fra_benefit, early_age, late_age, cola_rate, fra,
        portfolio_return=portfolio_return,
        include_opportunity_cost=False
    )
    
    portfolio_adjusted = calculate_break_even_age(
        fra_benefit, early_age, late_age, cola_rate, fra,
        portfolio_return=portfolio_return,
        include_opportunity_cost=True
    )
    
    return {
        'simple': simple,
        'portfolio_adjusted': portfolio_adjusted,
        'additional_years': portfolio_adjusted.break_even_age - simple.break_even_age,
        'portfolio_return_assumption': portfolio_return
    }


def calculate_lifetime_benefits(
    fra_benefit: float,
    claiming_age: int,
    life_expectancy: int,
    cola_rate: float = DEFAULT_COLA_RATE,
    fra: int = FULL_RETIREMENT_AGE
) -> float:
    """
    Calculate total lifetime benefits for a claiming strategy.
    
    Args:
        fra_benefit: Monthly benefit at FRA
        claiming_age: Age when benefits are claimed
        life_expectancy: Expected age at death
        cola_rate: Annual COLA rate
        fra: Full Retirement Age
        
    Returns:
        Total lifetime benefits (nominal dollars)
    """
    monthly_benefit = calculate_benefit_at_claiming_age(fra_benefit, claiming_age, fra)
    
    total = 0
    for age in range(claiming_age, life_expectancy + 1):
        years_since_claiming = age - claiming_age
        annual_benefit = monthly_benefit * 12 * ((1 + cola_rate) ** years_since_claiming)
        total += annual_benefit
    
    return total


def calculate_net_present_value(
    fra_benefit: float,
    claiming_age: int,
    life_expectancy: int,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    cola_rate: float = DEFAULT_COLA_RATE,
    fra: int = FULL_RETIREMENT_AGE
) -> float:
    """
    Calculate net present value of lifetime benefits.
    
    Args:
        fra_benefit: Monthly benefit at FRA
        claiming_age: Age when benefits are claimed
        life_expectancy: Expected age at death
        discount_rate: Real discount rate for NPV
        cola_rate: Annual COLA rate
        fra: Full Retirement Age
        
    Returns:
        Net present value of lifetime benefits
    """
    monthly_benefit = calculate_benefit_at_claiming_age(fra_benefit, claiming_age, fra)
    
    npv = 0
    for age in range(claiming_age, life_expectancy + 1):
        years_since_claiming = age - claiming_age
        annual_benefit = monthly_benefit * 12 * ((1 + cola_rate) ** years_since_claiming)
        # Discount back to claiming age
        discounted_benefit = annual_benefit / ((1 + discount_rate) ** years_since_claiming)
        npv += discounted_benefit
    
    return npv


def optimize_couple_claiming_strategy(
    person1: PersonProfile,
    person2: PersonProfile,
    cola_rate: float = DEFAULT_COLA_RATE,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    fra: int = FULL_RETIREMENT_AGE
) -> List[ClaimingStrategy]:
    """
    Analyze optimal claiming strategies for a married couple.
    
    Considers:
    - Individual claiming at different ages
    - Spousal benefits
    - Survivor benefits
    - Longevity differences
    
    Args:
        person1: First person's profile
        person2: Second person's profile
        cola_rate: Annual COLA rate
        discount_rate: Discount rate for NPV
        fra: Full Retirement Age
        
    Returns:
        List of ClaimingStrategy options ranked by NPV
    """
    strategies = []
    
    # Analyze various claiming age combinations
    claiming_ages = [62, 65, 67, 70]  # Common claiming ages
    
    for age1 in claiming_ages:
        for age2 in claiming_ages:
            # Calculate individual benefits
            benefit1 = calculate_benefit_at_claiming_age(person1.fra_benefit, age1, fra)
            benefit2 = calculate_benefit_at_claiming_age(person2.fra_benefit, age2, fra)
            
            # Calculate spousal benefit if applicable
            spousal1 = calculate_spousal_benefit(
                person2.fra_benefit, person1.fra_benefit, age1, age2, fra
            )
            spousal2 = calculate_spousal_benefit(
                person1.fra_benefit, person2.fra_benefit, age2, age1, fra
            )
            
            # Use higher of own or spousal benefit
            effective_benefit1 = max(benefit1, spousal1)
            effective_benefit2 = max(benefit2, spousal2)
            
            # Calculate lifetime benefits for each person
            lifetime1 = calculate_lifetime_benefits(
                person1.fra_benefit, age1, person1.life_expectancy, cola_rate, fra
            )
            lifetime2 = calculate_lifetime_benefits(
                person2.fra_benefit, age2, person2.life_expectancy, cola_rate, fra
            )
            
            # Calculate NPV
            npv1 = calculate_net_present_value(
                person1.fra_benefit, age1, person1.life_expectancy, discount_rate, cola_rate, fra
            )
            npv2 = calculate_net_present_value(
                person2.fra_benefit, age2, person2.life_expectancy, discount_rate, cola_rate, fra
            )
            
            total_lifetime = lifetime1 + lifetime2
            total_npv = npv1 + npv2
            
            # Generate strategy notes
            notes = []
            if age1 == age2:
                notes.append(f"Both claim at {age1}")
            else:
                notes.append(f"{person1.name} claims at {age1}, {person2.name} claims at {age2}")
            
            if spousal1 > benefit1:
                notes.append(f"{person1.name} receives spousal benefit")
            if spousal2 > benefit2:
                notes.append(f"{person2.name} receives spousal benefit")
            
            # Calculate break-even
            break_even = None
            if age1 != age2:
                be_analysis = calculate_break_even_age(
                    person1.fra_benefit if age1 < age2 else person2.fra_benefit,
                    min(age1, age2),
                    max(age1, age2),
                    cola_rate,
                    fra
                )
                break_even = be_analysis.break_even_age
                notes.append(f"Break-even age: {break_even}")
            
            strategy = ClaimingStrategy(
                person1_claiming_age=age1,
                person2_claiming_age=age2,
                strategy_name=f"{person1.name}@{age1}, {person2.name}@{age2}",
                total_lifetime_benefits=total_lifetime,
                net_present_value=total_npv,
                break_even_age=break_even,
                notes=notes
            )
            strategies.append(strategy)
    
    # Sort by NPV (highest first)
    strategies.sort(key=lambda s: s.net_present_value, reverse=True)
    
    return strategies


def generate_claiming_age_comparison(
    fra_benefit: float,
    life_expectancy: int,
    cola_rate: float = DEFAULT_COLA_RATE,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    fra: int = FULL_RETIREMENT_AGE
) -> pd.DataFrame:
    """
    Generate a comparison table of claiming ages.
    
    Args:
        fra_benefit: Monthly benefit at FRA
        life_expectancy: Expected age at death
        cola_rate: Annual COLA rate
        discount_rate: Discount rate for NPV
        fra: Full Retirement Age
        
    Returns:
        DataFrame with claiming age comparison
    """
    data = []
    
    for claiming_age in range(MIN_CLAIMING_AGE, MAX_BENEFIT_AGE + 1):
        monthly_benefit = calculate_benefit_at_claiming_age(fra_benefit, claiming_age, fra)
        lifetime_total = calculate_lifetime_benefits(
            fra_benefit, claiming_age, life_expectancy, cola_rate, fra
        )
        npv = calculate_net_present_value(
            fra_benefit, claiming_age, life_expectancy, discount_rate, cola_rate, fra
        )
        
        # Calculate break-even vs age 62
        if claiming_age > MIN_CLAIMING_AGE:
            be_analysis = calculate_break_even_age(
                fra_benefit, MIN_CLAIMING_AGE, claiming_age, cola_rate, fra
            )
            break_even = be_analysis.break_even_age
        else:
            break_even = None
        
        data.append({
            'Claiming Age': claiming_age,
            'Monthly Benefit': monthly_benefit,
            'Annual Benefit': monthly_benefit * 12,
            'Lifetime Total': lifetime_total,
            'Net Present Value': npv,
            'Break-Even Age': break_even,
            'Reduction/Increase': f"{((monthly_benefit / calculate_benefit_at_claiming_age(fra_benefit, fra, fra)) - 1) * 100:.1f}%"
        })
    
    return pd.DataFrame(data)

# Made with Bob
