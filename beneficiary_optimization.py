"""
Beneficiary Optimization Module

Provides advanced beneficiary planning and optimization including:
- Stretch IRA calculations (SECURE Act 2.0 compliant)
- Trust beneficiary modeling with tax implications
- Spousal rollover vs. inherited IRA detailed analysis
- 10-year rule modeling for non-spouse beneficiaries
- Eligible Designated Beneficiary (EDB) analysis
- RMD calculations for inherited accounts

References:
- SECURE Act (2019) - Changed stretch IRA rules
- SECURE Act 2.0 (2022) - RMD age changes, catch-up contributions
- IRC §401(a)(9) - Required Minimum Distributions
- IRS Publication 590-B - Distributions from IRAs
"""

import pandas as pd
import numpy as np
import logging
import os
from typing import Dict, List, Tuple, Optional, NamedTuple, Literal
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# Configure logging
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# CONSTANTS - SECURE ACT 2.0
# ==============================================================================

# RMD Starting Ages (SECURE Act 2.0)
RMD_START_AGES = {
    2023: 73,  # SECURE Act 2.0 raised from 72
    2033: 75,  # Further increase in 2033
}

# Life Expectancy Tables (IRS Uniform Lifetime Table)
UNIFORM_LIFETIME_TABLE = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9,
    78: 22.0, 79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7,
    84: 16.8, 85: 16.0, 86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9,
    90: 12.2, 91: 11.5, 92: 10.8, 93: 10.1, 94: 9.5, 95: 8.9,
    96: 8.4, 97: 7.8, 98: 7.3, 99: 6.8, 100: 6.4, 101: 6.0,
    102: 5.6, 103: 5.2, 104: 4.9, 105: 4.6, 106: 4.3, 107: 4.1,
    108: 3.9, 109: 3.7, 110: 3.5, 111: 3.4, 112: 3.3, 113: 3.1,
    114: 3.0, 115: 2.9, 116: 2.8, 117: 2.7, 118: 2.5, 119: 2.3,
    120: 2.0,
}

# Single Life Expectancy Table (for inherited IRAs)
SINGLE_LIFE_EXPECTANCY_TABLE = {
    0: 84.6, 1: 83.7, 2: 82.8, 3: 81.8, 4: 80.8, 5: 79.8,
    10: 74.8, 15: 69.9, 20: 65.0, 25: 60.1, 30: 55.3, 35: 50.5,
    40: 45.7, 45: 41.0, 50: 36.5, 55: 32.0, 60: 27.7, 65: 23.7,
    70: 19.8, 75: 16.3, 80: 13.1, 85: 10.3, 90: 7.9, 95: 6.0,
    100: 4.5, 105: 3.4, 110: 2.6, 115: 2.0, 120: 1.5,
}

# Eligible Designated Beneficiary (EDB) Categories
EDB_CATEGORIES = {
    'spouse': 'Surviving Spouse',
    'minor_child': 'Minor Child (under 21)',
    'disabled': 'Disabled Individual',
    'chronically_ill': 'Chronically Ill Individual',
    'not_more_than_10_years_younger': 'Not More Than 10 Years Younger',
}


# ==============================================================================
# RESULT CLASSES
# ==============================================================================

class InheritedIRAResult(NamedTuple):
    """Result of inherited IRA analysis."""
    account_type: str  # 'Traditional IRA', 'Roth IRA', '401(k)', etc.
    initial_balance: float
    beneficiary_type: str  # 'spouse', 'non-spouse', 'trust', 'charity', 'estate'
    is_edb: bool  # Eligible Designated Beneficiary
    distribution_method: str  # '10-year', 'stretch', 'lump-sum', '5-year'
    annual_distributions: List[Dict[str, float]]  # Year-by-year distributions
    total_distributions: float
    total_taxes_paid: float
    net_to_beneficiary: float
    effective_tax_rate: float


class SpousalOptionsResult(NamedTuple):
    """Comparison of spousal beneficiary options."""
    rollover_option: InheritedIRAResult
    inherited_option: InheritedIRAResult
    recommended_option: str
    savings_amount: float
    key_factors: List[str]


class TrustBeneficiaryResult(NamedTuple):
    """Result of trust as beneficiary analysis."""
    trust_type: str  # 'conduit', 'accumulation', 'see-through'
    qualifies_as_designated_beneficiary: bool
    distribution_method: str
    annual_trust_distributions: List[Dict[str, float]]
    annual_beneficiary_distributions: List[Dict[str, float]]
    total_trust_taxes: float
    total_beneficiary_taxes: float
    total_taxes_paid: float
    net_to_beneficiaries: float
    trust_administration_costs: float


class StretchIRAResult(NamedTuple):
    """Result of stretch IRA analysis (for EDBs)."""
    beneficiary_age: int
    life_expectancy: float
    annual_rmds: List[Dict[str, float]]
    total_distributions: float
    total_growth: float
    total_taxes: float
    net_inherited: float
    years_of_distributions: int


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_rmd_start_age(year: int) -> int:
    """
    Get RMD starting age for a given year (SECURE Act 2.0).
    
    Args:
        year: Year to check
        
    Returns:
        RMD starting age
    """
    if year >= 2033:
        return 75
    elif year >= 2023:
        return 73
    else:
        return 72  # Pre-SECURE Act 2.0


def get_life_expectancy(age: int, table: str = 'uniform') -> float:
    """
    Get life expectancy from IRS tables.
    
    Args:
        age: Current age
        table: 'uniform' or 'single'
        
    Returns:
        Life expectancy in years
    """
    if table == 'uniform':
        lookup_table = UNIFORM_LIFETIME_TABLE
    else:
        lookup_table = SINGLE_LIFE_EXPECTANCY_TABLE
    
    # Use closest age if exact age not in table
    if age in lookup_table:
        return lookup_table[age]
    
    # Find closest age
    ages = sorted(lookup_table.keys())
    closest_age = min(ages, key=lambda x: abs(x - age))
    
    logger.warning(f"Age {age} not in {table} table, using closest age {closest_age}")
    return lookup_table[closest_age]


def is_eligible_designated_beneficiary(
    beneficiary_type: str,
    beneficiary_age: int,
    owner_age: int,
    is_disabled: bool = False,
    is_chronically_ill: bool = False,
) -> bool:
    """
    Determine if beneficiary qualifies as Eligible Designated Beneficiary (EDB).
    
    EDBs can use stretch IRA rules instead of 10-year rule.
    
    Args:
        beneficiary_type: Type of beneficiary
        beneficiary_age: Age of beneficiary
        owner_age: Age of account owner at death
        is_disabled: Whether beneficiary is disabled
        is_chronically_ill: Whether beneficiary is chronically ill
        
    Returns:
        True if qualifies as EDB
    """
    # Spouse is always EDB
    if beneficiary_type == 'spouse':
        return True
    
    # Minor child (under 21) is EDB until age 21
    if beneficiary_type == 'minor_child' and beneficiary_age < 21:
        return True
    
    # Disabled or chronically ill
    if is_disabled or is_chronically_ill:
        return True
    
    # Not more than 10 years younger than owner
    if owner_age - beneficiary_age <= 10:
        return True
    
    return False


def calculate_income_tax(
    income: float,
    filing_status: str = 'single',
    year: int = 2024,
) -> float:
    """
    Calculate federal income tax (simplified).
    
    Args:
        income: Taxable income
        filing_status: 'single' or 'married_filing_jointly'
        year: Tax year
        
    Returns:
        Federal income tax
    """
    # 2024 tax brackets (simplified)
    if filing_status == 'married_filing_jointly':
        brackets = [
            (0, 23200, 0.10),
            (23200, 94300, 0.12),
            (94300, 201050, 0.22),
            (201050, 383900, 0.24),
            (383900, 487450, 0.32),
            (487450, 731200, 0.35),
            (731200, float('inf'), 0.37),
        ]
    else:  # single
        brackets = [
            (0, 11600, 0.10),
            (11600, 47150, 0.12),
            (47150, 100525, 0.22),
            (100525, 191950, 0.24),
            (191950, 243725, 0.32),
            (243725, 609350, 0.35),
            (609350, float('inf'), 0.37),
        ]
    
    tax = 0.0
    remaining = income
    
    for lower, upper, rate in brackets:
        if remaining <= 0:
            break
        
        bracket_amount = min(remaining, upper - lower)
        tax += bracket_amount * rate
        remaining -= bracket_amount
    
    return tax


# ==============================================================================
# INHERITED IRA CALCULATIONS
# ==============================================================================

def calculate_inherited_ira_10_year_rule(
    initial_balance: float,
    beneficiary_age: int,
    beneficiary_tax_rate: float = 0.24,
    annual_growth_rate: float = 0.07,
    account_type: str = 'Traditional IRA',
) -> InheritedIRAResult:
    """
    Calculate inherited IRA distributions under 10-year rule (SECURE Act).
    
    Non-spouse beneficiaries (non-EDBs) must withdraw entire balance within 10 years.
    No annual RMDs required, but entire balance must be withdrawn by end of year 10.
    
    Args:
        initial_balance: Starting IRA balance
        beneficiary_age: Age of beneficiary
        beneficiary_tax_rate: Marginal tax rate
        annual_growth_rate: Expected annual return
        account_type: Type of account
        
    Returns:
        InheritedIRAResult with 10-year distribution analysis
    """
    is_roth = 'Roth' in account_type
    
    # Strategy: Equal annual distributions to minimize tax bracket creep
    annual_distribution = initial_balance / 10
    
    annual_distributions = []
    balance = initial_balance
    total_taxes = 0.0
    
    for year in range(1, 11):
        # Growth for the year
        growth = balance * annual_growth_rate
        balance += growth
        
        # Distribution
        distribution = min(annual_distribution, balance)
        balance -= distribution
        
        # Tax (Roth is tax-free)
        if is_roth:
            tax = 0.0
            after_tax_distribution = distribution
        else:
            tax = distribution * beneficiary_tax_rate
            after_tax_distribution = distribution - tax
        
        total_taxes += tax
        
        annual_distributions.append({
            'year': year,
            'beginning_balance': balance + distribution - growth,
            'growth': growth,
            'distribution': distribution,
            'tax': tax,
            'after_tax_distribution': after_tax_distribution,
            'ending_balance': balance,
        })
    
    total_distributions = sum(d['distribution'] for d in annual_distributions)
    net_to_beneficiary = total_distributions - total_taxes
    effective_tax_rate = total_taxes / total_distributions if total_distributions > 0 else 0
    
    return InheritedIRAResult(
        account_type=account_type,
        initial_balance=initial_balance,
        beneficiary_type='non-spouse',
        is_edb=False,
        distribution_method='10-year',
        annual_distributions=annual_distributions,
        total_distributions=total_distributions,
        total_taxes_paid=total_taxes,
        net_to_beneficiary=net_to_beneficiary,
        effective_tax_rate=effective_tax_rate,
    )


def calculate_stretch_ira(
    initial_balance: float,
    beneficiary_age: int,
    beneficiary_tax_rate: float = 0.24,
    annual_growth_rate: float = 0.07,
    account_type: str = 'Traditional IRA',
    max_years: int = 40,
) -> StretchIRAResult:
    """
    Calculate stretch IRA distributions for Eligible Designated Beneficiaries.
    
    EDBs can take RMDs based on their life expectancy, allowing the account
    to grow tax-deferred for many years.
    
    Args:
        initial_balance: Starting IRA balance
        beneficiary_age: Age of beneficiary
        beneficiary_tax_rate: Marginal tax rate
        annual_growth_rate: Expected annual return
        account_type: Type of account
        max_years: Maximum years to project
        
    Returns:
        StretchIRAResult with lifetime distribution analysis
    """
    is_roth = 'Roth' in account_type
    
    # Get initial life expectancy
    life_expectancy = get_life_expectancy(beneficiary_age, 'single')
    
    annual_rmds = []
    balance = initial_balance
    total_taxes = 0.0
    total_growth = 0.0
    
    for year in range(1, min(int(life_expectancy) + 1, max_years + 1)):
        # Growth for the year
        growth = balance * annual_growth_rate
        balance += growth
        total_growth += growth
        
        # Calculate RMD
        remaining_life_expectancy = life_expectancy - (year - 1)
        if remaining_life_expectancy < 1:
            remaining_life_expectancy = 1
        
        rmd = balance / remaining_life_expectancy
        rmd = min(rmd, balance)  # Can't distribute more than balance
        
        balance -= rmd
        
        # Tax (Roth is tax-free)
        if is_roth:
            tax = 0.0
            after_tax_rmd = rmd
        else:
            tax = rmd * beneficiary_tax_rate
            after_tax_rmd = rmd - tax
        
        total_taxes += tax
        
        annual_rmds.append({
            'year': year,
            'beneficiary_age': beneficiary_age + year - 1,
            'life_expectancy': remaining_life_expectancy,
            'beginning_balance': balance + rmd - growth,
            'growth': growth,
            'rmd': rmd,
            'tax': tax,
            'after_tax_rmd': after_tax_rmd,
            'ending_balance': balance,
        })
        
        if balance < 1:
            break
    
    total_distributions = sum(d['rmd'] for d in annual_rmds)
    net_inherited = total_distributions - total_taxes
    
    return StretchIRAResult(
        beneficiary_age=beneficiary_age,
        life_expectancy=life_expectancy,
        annual_rmds=annual_rmds,
        total_distributions=total_distributions,
        total_growth=total_growth,
        total_taxes=total_taxes,
        net_inherited=net_inherited,
        years_of_distributions=len(annual_rmds),
    )


# ==============================================================================
# SPOUSAL BENEFICIARY OPTIONS
# ==============================================================================

def compare_spousal_options(
    initial_balance: float,
    spouse_age: int,
    spouse_tax_rate: float = 0.24,
    annual_growth_rate: float = 0.07,
    account_type: str = 'Traditional IRA',
) -> SpousalOptionsResult:
    """
    Compare spousal rollover vs. inherited IRA options.
    
    Surviving spouse has unique options:
    1. Rollover to own IRA (treat as own)
    2. Remain as beneficiary (inherited IRA)
    
    Args:
        initial_balance: IRA balance
        spouse_age: Age of surviving spouse
        spouse_tax_rate: Marginal tax rate
        annual_growth_rate: Expected return
        account_type: Type of account
        
    Returns:
        SpousalOptionsResult with comparison
    """
    is_roth = 'Roth' in account_type
    
    # Option 1: Rollover to own IRA
    # RMDs start at age 73 (or 75 if after 2033)
    rmd_age = get_rmd_start_age(2024)
    years_until_rmd = max(0, rmd_age - spouse_age)
    
    rollover_distributions = []
    balance = initial_balance
    total_taxes_rollover = 0.0
    
    # Growth period before RMDs
    for year in range(1, years_until_rmd + 1):
        growth = balance * annual_growth_rate
        balance += growth
        
        rollover_distributions.append({
            'year': year,
            'age': spouse_age + year - 1,
            'balance': balance,
            'distribution': 0,
            'tax': 0,
        })
    
    # RMD period (project 30 years)
    for year in range(years_until_rmd + 1, years_until_rmd + 31):
        age = spouse_age + year - 1
        growth = balance * annual_growth_rate
        balance += growth
        
        life_expectancy = get_life_expectancy(age, 'uniform')
        rmd = balance / life_expectancy
        rmd = min(rmd, balance)
        
        balance -= rmd
        
        if is_roth:
            tax = 0
        else:
            tax = rmd * spouse_tax_rate
        
        total_taxes_rollover += tax
        
        rollover_distributions.append({
            'year': year,
            'age': age,
            'balance': balance,
            'distribution': rmd,
            'tax': tax,
        })
        
        if balance < 1:
            break
    
    rollover_result = InheritedIRAResult(
        account_type=account_type,
        initial_balance=initial_balance,
        beneficiary_type='spouse',
        is_edb=True,
        distribution_method='rollover',
        annual_distributions=rollover_distributions,
        total_distributions=sum(d['distribution'] for d in rollover_distributions),
        total_taxes_paid=total_taxes_rollover,
        net_to_beneficiary=sum(d['distribution'] for d in rollover_distributions) - total_taxes_rollover,
        effective_tax_rate=total_taxes_rollover / sum(d['distribution'] for d in rollover_distributions) if sum(d['distribution'] for d in rollover_distributions) > 0 else 0,
    )
    
    # Option 2: Inherited IRA (stretch)
    inherited_result_data = calculate_stretch_ira(
        initial_balance=initial_balance,
        beneficiary_age=spouse_age,
        beneficiary_tax_rate=spouse_tax_rate,
        annual_growth_rate=annual_growth_rate,
        account_type=account_type,
        max_years=40,
    )
    
    inherited_result = InheritedIRAResult(
        account_type=account_type,
        initial_balance=initial_balance,
        beneficiary_type='spouse',
        is_edb=True,
        distribution_method='stretch',
        annual_distributions=inherited_result_data.annual_rmds,
        total_distributions=inherited_result_data.total_distributions,
        total_taxes_paid=inherited_result_data.total_taxes,
        net_to_beneficiary=inherited_result_data.net_inherited,
        effective_tax_rate=inherited_result_data.total_taxes / inherited_result_data.total_distributions if inherited_result_data.total_distributions > 0 else 0,
    )
    
    # Determine recommendation
    key_factors = []
    
    if spouse_age < rmd_age:
        key_factors.append(f"Spouse is under RMD age ({rmd_age})")
        if spouse_age < 59.5:
            key_factors.append("Inherited IRA avoids 10% early withdrawal penalty")
            recommended = 'inherited'
        else:
            key_factors.append("Rollover delays RMDs for maximum tax-deferred growth")
            recommended = 'rollover'
    else:
        key_factors.append(f"Spouse is over RMD age ({rmd_age})")
        if inherited_result.net_to_beneficiary > rollover_result.net_to_beneficiary:
            key_factors.append("Inherited IRA provides better after-tax outcome")
            recommended = 'inherited'
        else:
            key_factors.append("Rollover provides better after-tax outcome")
            recommended = 'rollover'
    
    savings_amount = abs(rollover_result.net_to_beneficiary - inherited_result.net_to_beneficiary)
    
    return SpousalOptionsResult(
        rollover_option=rollover_result,
        inherited_option=inherited_result,
        recommended_option=recommended,
        savings_amount=savings_amount,
        key_factors=key_factors,
    )


# ==============================================================================
# TRUST AS BENEFICIARY
# ==============================================================================

def calculate_trust_beneficiary(
    initial_balance: float,
    trust_type: str,
    oldest_beneficiary_age: int,
    trust_tax_rate: float = 0.37,  # Trusts hit top rate quickly
    beneficiary_tax_rate: float = 0.24,
    annual_growth_rate: float = 0.07,
    account_type: str = 'Traditional IRA',
    annual_admin_cost: float = 5000,
) -> TrustBeneficiaryResult:
    """
    Calculate distributions when trust is named as IRA beneficiary.
    
    Trust types:
    - Conduit Trust: Passes all RMDs directly to beneficiaries
    - Accumulation Trust: Can accumulate income (taxed at trust rates)
    - See-Through Trust: Qualifies as designated beneficiary
    
    Args:
        initial_balance: IRA balance
        trust_type: Type of trust
        oldest_beneficiary_age: Age of oldest trust beneficiary
        trust_tax_rate: Trust tax rate (typically 37%)
        beneficiary_tax_rate: Beneficiary tax rate
        annual_growth_rate: Expected return
        account_type: Type of account
        annual_admin_cost: Annual trust administration cost
        
    Returns:
        TrustBeneficiaryResult with analysis
    """
    is_roth = 'Roth' in account_type
    
    # Determine if trust qualifies as designated beneficiary
    qualifies = trust_type in ['conduit', 'see-through']
    
    # Distribution method
    if qualifies:
        # Can use stretch based on oldest beneficiary
        distribution_method = 'stretch'
        life_expectancy = get_life_expectancy(oldest_beneficiary_age, 'single')
    else:
        # Must use 5-year rule or 10-year rule
        distribution_method = '10-year'
        life_expectancy = 10
    
    annual_trust_distributions = []
    annual_beneficiary_distributions = []
    balance = initial_balance
    total_trust_taxes = 0.0
    total_beneficiary_taxes = 0.0
    total_admin_costs = 0.0
    
    years = int(life_expectancy) if distribution_method == 'stretch' else 10
    
    for year in range(1, years + 1):
        # Growth
        growth = balance * annual_growth_rate
        balance += growth
        
        # Calculate distribution
        if distribution_method == 'stretch':
            remaining_life = life_expectancy - (year - 1)
            if remaining_life < 1:
                remaining_life = 1
            distribution = balance / remaining_life
        else:
            distribution = balance / (years - year + 1)
        
        distribution = min(distribution, balance)
        balance -= distribution
        
        # Trust administration cost
        admin_cost = annual_admin_cost
        total_admin_costs += admin_cost
        
        # Trust receives distribution
        if trust_type == 'conduit':
            # Pass through to beneficiaries immediately
            trust_tax = 0
            to_beneficiaries = distribution
            
            # Beneficiaries pay tax
            if is_roth:
                beneficiary_tax = 0
            else:
                beneficiary_tax = to_beneficiaries * beneficiary_tax_rate
            
            total_beneficiary_taxes += beneficiary_tax
            
        elif trust_type == 'accumulation':
            # Trust can accumulate - pays trust tax rates
            if is_roth:
                trust_tax = 0
                to_beneficiaries = 0  # Accumulated in trust
            else:
                trust_tax = distribution * trust_tax_rate
                to_beneficiaries = 0  # Accumulated in trust
            
            total_trust_taxes += trust_tax
            beneficiary_tax = 0
            
        else:  # see-through
            # Hybrid - some passed through
            pass_through_pct = 0.5
            to_beneficiaries = distribution * pass_through_pct
            accumulated = distribution * (1 - pass_through_pct)
            
            if is_roth:
                trust_tax = 0
                beneficiary_tax = 0
            else:
                trust_tax = accumulated * trust_tax_rate
                beneficiary_tax = to_beneficiaries * beneficiary_tax_rate
            
            total_trust_taxes += trust_tax
            total_beneficiary_taxes += beneficiary_tax
        
        annual_trust_distributions.append({
            'year': year,
            'balance': balance + distribution - growth,
            'growth': growth,
            'distribution': distribution,
            'trust_tax': trust_tax,
            'admin_cost': admin_cost,
        })
        
        annual_beneficiary_distributions.append({
            'year': year,
            'amount_received': to_beneficiaries,
            'beneficiary_tax': beneficiary_tax,
            'net_to_beneficiary': to_beneficiaries - beneficiary_tax,
        })
        
        if balance < 1:
            break
    
    total_distributions = sum(d['distribution'] for d in annual_trust_distributions)
    total_taxes = total_trust_taxes + total_beneficiary_taxes
    net_to_beneficiaries = total_distributions - total_taxes - total_admin_costs
    
    return TrustBeneficiaryResult(
        trust_type=trust_type,
        qualifies_as_designated_beneficiary=qualifies,
        distribution_method=distribution_method,
        annual_trust_distributions=annual_trust_distributions,
        annual_beneficiary_distributions=annual_beneficiary_distributions,
        total_trust_taxes=total_trust_taxes,
        total_beneficiary_taxes=total_beneficiary_taxes,
        total_taxes_paid=total_taxes,
        net_to_beneficiaries=net_to_beneficiaries,
        trust_administration_costs=total_admin_costs,
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


def compare_beneficiary_strategies(
    initial_balance: float,
    scenarios: List[Dict],
    annual_growth_rate: float = 0.07,
) -> pd.DataFrame:
    """
    Compare multiple beneficiary strategies side-by-side.
    
    Args:
        initial_balance: IRA balance
        scenarios: List of scenario dicts with beneficiary parameters
        annual_growth_rate: Expected return
        
    Returns:
        DataFrame with comparison
    """
    results = []
    
    for scenario in scenarios:
        scenario_name = scenario.get('name', 'Unnamed')
        beneficiary_type = scenario.get('beneficiary_type', 'non-spouse')
        
        if beneficiary_type == 'spouse':
            spousal_result = compare_spousal_options(
                initial_balance=initial_balance,
                spouse_age=scenario.get('age', 65),
                spouse_tax_rate=scenario.get('tax_rate', 0.24),
                annual_growth_rate=annual_growth_rate,
            )
            if spousal_result.recommended_option == 'rollover':
                net = spousal_result.rollover_option.net_to_beneficiary
                eff_rate = spousal_result.rollover_option.effective_tax_rate
            else:
                net = spousal_result.inherited_option.net_to_beneficiary
                eff_rate = spousal_result.inherited_option.effective_tax_rate
            
        elif beneficiary_type == 'trust':
            trust_result = calculate_trust_beneficiary(
                initial_balance=initial_balance,
                trust_type=scenario.get('trust_type', 'conduit'),
                oldest_beneficiary_age=scenario.get('age', 40),
                annual_growth_rate=annual_growth_rate,
            )
            net = trust_result.net_to_beneficiaries
            total_dist = sum(d['distribution'] for d in trust_result.annual_trust_distributions)
            eff_rate = trust_result.total_taxes_paid / total_dist if total_dist > 0 else 0
            
        else:
            ira_result = calculate_inherited_ira_10_year_rule(
                initial_balance=initial_balance,
                beneficiary_age=scenario.get('age', 40),
                beneficiary_tax_rate=scenario.get('tax_rate', 0.24),
                annual_growth_rate=annual_growth_rate,
            )
            net = ira_result.net_to_beneficiary
            eff_rate = ira_result.effective_tax_rate
        
        results.append({
            'Scenario': scenario_name,
            'Beneficiary Type': beneficiary_type,
            'Net to Beneficiary': net,
            'Effective Tax Rate': eff_rate,
        })
    
    return pd.DataFrame(results)

# Made with Bob
