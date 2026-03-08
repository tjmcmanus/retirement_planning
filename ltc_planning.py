"""
Long-Term Care (LTC) Planning Module

Comprehensive long-term care cost projections and planning tools including:
- Nursing home cost projections by state
- Home health care expense modeling
- Medicaid spend-down strategies
- Self-insurance vs LTC insurance analysis

Based on 2024 Genworth Cost of Care Survey and Medicaid regulations.
"""

import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# 2024 National Average Costs (Annual)
# Source: Genworth Cost of Care Survey 2024
NATIONAL_NURSING_HOME_PRIVATE = 116_800  # Private room
NATIONAL_NURSING_HOME_SEMI = 104_000     # Semi-private room
NATIONAL_ASSISTED_LIVING = 64_200
NATIONAL_HOME_HEALTH_AIDE = 75_504       # 44 hours/week
NATIONAL_ADULT_DAY_CARE = 23_400         # 5 days/week

# LTC Cost Inflation Rate (historical average 3-5%)
LTC_INFLATION_RATE = 0.04  # 4% annual increase

# Medicaid Asset Limits (varies by state, these are common)
MEDICAID_ASSET_LIMIT_SINGLE = 2000
MEDICAID_ASSET_LIMIT_MARRIED_APPLICANT = 2000
MEDICAID_ASSET_LIMIT_MARRIED_SPOUSE = 148_620  # 2024 CSRA maximum
MEDICAID_LOOKBACK_YEARS = 5

# LTC Insurance typical parameters
LTC_INSURANCE_DAILY_BENEFIT_OPTIONS = [150, 200, 250, 300, 350]
LTC_INSURANCE_BENEFIT_PERIODS = [2, 3, 4, 5, 'lifetime']
LTC_INSURANCE_WAITING_PERIODS = [0, 30, 60, 90, 180]  # days


# State-specific nursing home costs (2024 estimates)
# Private room annual costs by state
STATE_NURSING_HOME_COSTS = {
    'AL': 87_600, 'AK': 328_500, 'AZ': 102_200, 'AR': 73_000, 'CA': 131_400,
    'CO': 102_200, 'CT': 160_000, 'DE': 131_400, 'FL': 102_200, 'GA': 87_600,
    'HI': 160_000, 'ID': 87_600, 'IL': 87_600, 'IN': 87_600, 'IA': 73_000,
    'KS': 73_000, 'KY': 87_600, 'LA': 73_000, 'ME': 116_800, 'MD': 131_400,
    'MA': 160_000, 'MI': 102_200, 'MN': 116_800, 'MS': 73_000, 'MO': 73_000,
    'MT': 87_600, 'NE': 73_000, 'NV': 102_200, 'NH': 145_000, 'NJ': 160_000,
    'NM': 87_600, 'NY': 160_000, 'NC': 87_600, 'ND': 116_800, 'OH': 87_600,
    'OK': 58_400, 'OR': 116_800, 'PA': 116_800, 'RI': 131_400, 'SC': 87_600,
    'SD': 73_000, 'TN': 73_000, 'TX': 58_400, 'UT': 87_600, 'VT': 116_800,
    'VA': 102_200, 'WA': 116_800, 'WV': 87_600, 'WI': 102_200, 'WY': 87_600,
    'DC': 160_000
}

# State Medicaid asset limits for married couples (Community Spouse Resource Allowance)
STATE_MEDICAID_CSRA = {
    'default': 148_620,  # 2024 federal maximum
    'CA': 137_400,
    'NY': 148_620,
    'FL': 148_620,
    'TX': 148_620,
    # Add more state-specific values as needed
}


@dataclass
class LTCCostProjection:
    """Long-term care cost projection"""
    care_type: str
    annual_cost: float
    years_needed: int
    total_cost: float
    inflation_adjusted_total: float
    state: str


@dataclass
class MedicaidSpendDownAnalysis:
    """Medicaid spend-down analysis results"""
    current_assets: float
    asset_limit: float
    excess_assets: float
    months_to_qualify: int
    spend_down_strategies: List[str]
    protected_spouse_assets: float
    lookback_concerns: List[str]


@dataclass
class LTCInsuranceAnalysis:
    """LTC Insurance vs Self-Insurance analysis"""
    annual_premium: float
    total_premiums_paid: float
    daily_benefit: float
    benefit_period_years: int
    total_insurance_benefit: float
    self_insurance_cost: float
    break_even_year: int
    recommendation: str
    notes: List[str]


def get_nursing_home_cost(state: str = 'National', room_type: str = 'private') -> float:
    """
    Get annual nursing home cost for a state.
    
    Args:
        state: Two-letter state code or 'National'
        room_type: 'private' or 'semi-private'
        
    Returns:
        Annual cost in dollars
    """
    if state == 'National':
        return NATIONAL_NURSING_HOME_PRIVATE if room_type == 'private' else NATIONAL_NURSING_HOME_SEMI
    
    base_cost = STATE_NURSING_HOME_COSTS.get(state.upper(), NATIONAL_NURSING_HOME_PRIVATE)
    
    if room_type == 'semi-private':
        # Semi-private typically 10-15% less than private
        base_cost = base_cost * 0.88
    
    return base_cost


def project_ltc_costs(
    care_type: str,
    years_until_need: int,
    years_of_care: int,
    state: str = 'National',
    inflation_rate: float = LTC_INFLATION_RATE
) -> LTCCostProjection:
    """
    Project long-term care costs with inflation.
    
    Args:
        care_type: 'nursing_home_private', 'nursing_home_semi', 'assisted_living',
                   'home_health_full', 'home_health_part', 'adult_day_care'
        years_until_need: Years until care is needed
        years_of_care: Expected years of care needed
        state: State code or 'National'
        inflation_rate: Annual inflation rate for LTC costs
        
    Returns:
        LTCCostProjection with detailed cost breakdown
    """
    # Get base annual cost
    if care_type == 'nursing_home_private':
        annual_cost = get_nursing_home_cost(state, 'private')
    elif care_type == 'nursing_home_semi':
        annual_cost = get_nursing_home_cost(state, 'semi-private')
    elif care_type == 'assisted_living':
        annual_cost = NATIONAL_ASSISTED_LIVING
    elif care_type == 'home_health_full':
        # Full-time home health aide (168 hours/week)
        annual_cost = NATIONAL_HOME_HEALTH_AIDE * (168 / 44)
    elif care_type == 'home_health_part':
        # Part-time home health aide (44 hours/week)
        annual_cost = NATIONAL_HOME_HEALTH_AIDE
    elif care_type == 'adult_day_care':
        annual_cost = NATIONAL_ADULT_DAY_CARE
    else:
        raise ValueError(f"Unknown care type: {care_type}")
    
    # Project cost at time of need
    future_annual_cost = annual_cost * ((1 + inflation_rate) ** years_until_need)
    
    # Calculate total cost over care period with continued inflation
    total_inflated = 0
    for year in range(years_of_care):
        year_cost = future_annual_cost * ((1 + inflation_rate) ** year)
        total_inflated += year_cost
    
    # Simple total without additional inflation during care period
    total_simple = future_annual_cost * years_of_care
    
    return LTCCostProjection(
        care_type=care_type,
        annual_cost=future_annual_cost,
        years_needed=years_of_care,
        total_cost=total_simple,
        inflation_adjusted_total=total_inflated,
        state=state
    )


def analyze_medicaid_spend_down(
    current_assets: float,
    is_married: bool,
    spouse_assets: float = 0,
    state: str = 'default',
    recent_transfers: Optional[List[Tuple[float, int]]] = None
) -> MedicaidSpendDownAnalysis:
    """
    Analyze Medicaid eligibility and spend-down requirements.
    
    Args:
        current_assets: Current countable assets
        is_married: Whether applicant is married
        spouse_assets: Assets in spouse's name (if married)
        state: State code for state-specific rules
        recent_transfers: List of (amount, months_ago) for lookback analysis
        
    Returns:
        MedicaidSpendDownAnalysis with eligibility and strategies
    """
    if recent_transfers is None:
        recent_transfers = []
    
    # Determine asset limits
    if is_married:
        applicant_limit = MEDICAID_ASSET_LIMIT_MARRIED_APPLICANT
        spouse_limit = STATE_MEDICAID_CSRA.get(state, STATE_MEDICAID_CSRA['default'])
        total_limit = applicant_limit + spouse_limit
    else:
        applicant_limit = MEDICAID_ASSET_LIMIT_SINGLE
        total_limit = applicant_limit
        spouse_limit = 0
    
    # Calculate excess assets
    total_assets = current_assets + spouse_assets
    excess_assets = max(0, total_assets - total_limit)
    
    # Estimate months to qualify (assuming $10,000/month nursing home cost)
    avg_monthly_cost = 10_000
    months_to_qualify = int(excess_assets / avg_monthly_cost) if excess_assets > 0 else 0
    
    # Spend-down strategies
    strategies = []
    if excess_assets > 0:
        strategies.append(f"Pay for care privately for ~{months_to_qualify} months")
        strategies.append("Pay off debts (mortgage, car loans)")
        strategies.append("Make home improvements (exempt asset)")
        strategies.append("Purchase exempt assets (car, burial funds up to $15,000)")
        strategies.append("Purchase Medicaid-compliant annuity for spouse")
        if is_married:
            strategies.append(f"Transfer up to ${spouse_limit:,.0f} to community spouse")
    else:
        strategies.append("Currently eligible for Medicaid")
    
    # Check lookback period concerns
    lookback_concerns = []
    lookback_months = MEDICAID_LOOKBACK_YEARS * 12
    
    for amount, months_ago in recent_transfers:
        if months_ago < lookback_months:
            penalty_months = int(amount / avg_monthly_cost)
            lookback_concerns.append(
                f"Transfer of ${amount:,.0f} {months_ago} months ago may cause "
                f"{penalty_months} month penalty period"
            )
    
    if not lookback_concerns:
        lookback_concerns.append("No concerning transfers in lookback period")
    
    return MedicaidSpendDownAnalysis(
        current_assets=current_assets,
        asset_limit=total_limit,
        excess_assets=excess_assets,
        months_to_qualify=months_to_qualify,
        spend_down_strategies=strategies,
        protected_spouse_assets=spouse_limit if is_married else 0,
        lookback_concerns=lookback_concerns
    )


def analyze_ltc_insurance_vs_self_insurance(
    current_age: int,
    annual_premium: float,
    daily_benefit: float,
    benefit_period_years: int,
    waiting_period_days: int,
    years_until_need: int,
    expected_years_of_care: int,
    state: str = 'National',
    inflation_protection: bool = True
) -> LTCInsuranceAnalysis:
    """
    Compare LTC insurance to self-insurance.
    
    Args:
        current_age: Current age
        annual_premium: Annual LTC insurance premium
        daily_benefit: Daily benefit amount from policy
        benefit_period_years: Years of coverage (or 'lifetime')
        waiting_period_days: Elimination period in days
        years_until_need: Expected years until LTC is needed
        expected_years_of_care: Expected years of care needed
        state: State for cost projections
        inflation_protection: Whether policy has inflation protection
        
    Returns:
        LTCInsuranceAnalysis with comparison and recommendation
    """
    # Calculate total premiums paid
    years_paying_premiums = years_until_need
    total_premiums = annual_premium * years_paying_premiums
    
    # Calculate insurance benefit
    if inflation_protection:
        # Assume 3% compound inflation protection
        adjusted_daily_benefit = daily_benefit * ((1.03) ** years_until_need)
    else:
        adjusted_daily_benefit = daily_benefit
    
    # Account for waiting period
    waiting_period_cost = (waiting_period_days / 365) * adjusted_daily_benefit * 365
    
    # Calculate total insurance benefit
    benefit_years = min(benefit_period_years, expected_years_of_care) if isinstance(benefit_period_years, int) else expected_years_of_care
    annual_insurance_benefit = adjusted_daily_benefit * 365
    total_insurance_benefit = annual_insurance_benefit * benefit_years
    
    # Calculate self-insurance cost
    ltc_projection = project_ltc_costs(
        'nursing_home_private',
        years_until_need,
        expected_years_of_care,
        state
    )
    self_insurance_cost = ltc_projection.inflation_adjusted_total
    
    # Calculate break-even
    net_insurance_benefit = total_insurance_benefit - total_premiums - waiting_period_cost
    net_insurance_cost = self_insurance_cost - net_insurance_benefit
    
    # Determine break-even year
    if net_insurance_benefit > 0:
        break_even_year = int(total_premiums / annual_insurance_benefit) + 1
    else:
        break_even_year = 999  # Never breaks even
    
    # Generate recommendation
    notes = []
    
    if net_insurance_benefit > self_insurance_cost * 0.5:
        recommendation = "LTC Insurance Recommended"
        notes.append(f"Insurance provides ${net_insurance_benefit:,.0f} net benefit")
        notes.append(f"Protects against catastrophic costs")
    elif net_insurance_benefit > 0:
        recommendation = "LTC Insurance Marginally Beneficial"
        notes.append(f"Insurance provides ${net_insurance_benefit:,.0f} net benefit")
        notes.append(f"Consider if family history suggests high LTC risk")
    else:
        recommendation = "Self-Insurance May Be Better"
        notes.append(f"Self-insurance saves ${abs(net_insurance_cost):,.0f}")
        notes.append(f"Consider if you have substantial assets (>${self_insurance_cost:,.0f})")
    
    notes.append(f"Total premiums over {years_paying_premiums} years: ${total_premiums:,.0f}")
    notes.append(f"Projected LTC cost: ${self_insurance_cost:,.0f}")
    notes.append(f"Insurance benefit: ${total_insurance_benefit:,.0f}")
    
    if waiting_period_days > 0:
        notes.append(f"Waiting period cost: ${waiting_period_cost:,.0f}")
    
    return LTCInsuranceAnalysis(
        annual_premium=annual_premium,
        total_premiums_paid=total_premiums,
        daily_benefit=adjusted_daily_benefit,
        benefit_period_years=benefit_period_years,
        total_insurance_benefit=total_insurance_benefit,
        self_insurance_cost=self_insurance_cost,
        break_even_year=break_even_year,
        recommendation=recommendation,
        notes=notes
    )


def calculate_ltc_probability(age: int, gender: str) -> Dict[str, float]:
    """
    Calculate probability of needing long-term care.
    
    Based on Department of Health and Human Services statistics:
    - 70% of people turning 65 will need some form of LTC
    - Average duration: 3 years for men, 3.7 years for women
    
    Args:
        age: Current age
        gender: 'M' or 'F'
        
    Returns:
        Dictionary with probabilities and expected duration
    """
    # Base probability at age 65
    base_probability = 0.70
    
    # Adjust for current age
    if age < 65:
        # Lower probability for younger ages
        age_factor = 0.5 + (age / 65) * 0.5
    else:
        # Higher probability for older ages
        age_factor = 1.0 + ((age - 65) / 20) * 0.2
    
    probability = min(0.95, base_probability * age_factor)
    
    # Expected duration
    if gender == 'F':
        expected_duration = 3.7
    else:
        expected_duration = 3.0
    
    # Probability of needing care for different durations
    return {
        'any_ltc': probability,
        'less_than_1_year': probability * 0.20,
        '1_to_3_years': probability * 0.35,
        '3_to_5_years': probability * 0.25,
        'more_than_5_years': probability * 0.20,
        'expected_duration_years': expected_duration
    }


def generate_ltc_cost_comparison(
    state: str = 'National',
    years_until_need: int = 10
) -> pd.DataFrame:
    """
    Generate comparison table of different LTC options.
    
    Args:
        state: State for cost projections
        years_until_need: Years until care is needed
        
    Returns:
        DataFrame with cost comparison
    """
    care_types = [
        ('Nursing Home - Private Room', 'nursing_home_private'),
        ('Nursing Home - Semi-Private', 'nursing_home_semi'),
        ('Assisted Living Facility', 'assisted_living'),
        ('Home Health Aide - Full Time', 'home_health_full'),
        ('Home Health Aide - Part Time', 'home_health_part'),
        ('Adult Day Care', 'adult_day_care')
    ]
    
    data = []
    for name, care_type in care_types:
        projection = project_ltc_costs(care_type, years_until_need, 3, state)
        
        data.append({
            'Care Type': name,
            'Current Annual Cost': projection.annual_cost / ((1 + LTC_INFLATION_RATE) ** years_until_need),
            'Projected Annual Cost': projection.annual_cost,
            'Monthly Cost': projection.annual_cost / 12,
            '3-Year Total Cost': projection.inflation_adjusted_total
        })
    
    return pd.DataFrame(data)

# Made with Bob
