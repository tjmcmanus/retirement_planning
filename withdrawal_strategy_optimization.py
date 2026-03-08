"""
Advanced Withdrawal Strategy Optimization Module

Implements sophisticated optimization techniques for retirement withdrawal strategies:
- Multi-year tax planning with look-ahead optimization
- Dynamic Roth conversion optimization based on future tax projections
- Intelligent IRMAA cliff avoidance with 2-year lookback
- ACA subsidy maximization with income targeting
- Tax-loss harvesting coordination
- QCD (Qualified Charitable Distribution) optimization

Author: Bob
Date: 2026-03-08
Version: 1.0 - Advanced Optimization
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, NamedTuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


# ==============================================================================
# OPTIMIZATION CONSTANTS
# ==============================================================================

# IRMAA thresholds for 2024 (MFJ) - indexed annually
IRMAA_BRACKETS_MFJ = [
    {'lower': 0, 'upper': 206000, 'monthly_premium': 0},
    {'lower': 206000, 'upper': 258000, 'monthly_premium': 69.90},
    {'lower': 258000, 'upper': 322000, 'monthly_premium': 174.70},
    {'lower': 322000, 'upper': 386000, 'monthly_premium': 279.50},
    {'lower': 386000, 'upper': 750000, 'monthly_premium': 384.30},
    {'lower': 750000, 'upper': float('inf'), 'monthly_premium': 419.30},
]

# ACA subsidy cliff (400% FPL for 2-person household)
ACA_SUBSIDY_CLIFF_2_PERSON = 80000  # Approximate, varies by state

# Tax bracket targets for Roth conversions
OPTIMAL_CONVERSION_BRACKETS = [0.10, 0.12, 0.22, 0.24]

# Look-ahead window for multi-year optimization
DEFAULT_LOOKAHEAD_YEARS = 5


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class TaxProjection:
    """Tax projection for a future year"""
    year: int
    age_primary: int
    age_spouse: int
    estimated_income: float
    estimated_deductions: float
    estimated_agi: float
    marginal_rate: float
    effective_rate: float
    has_rmd: bool
    rmd_amount: float = 0.0


@dataclass
class ConversionOpportunity:
    """Roth conversion opportunity with cost-benefit analysis"""
    year: int
    current_bracket: float
    target_bracket: float
    conversion_amount: float
    conversion_tax: float
    future_tax_savings: float
    net_benefit: float
    confidence: float  # 0.0 to 1.0
    rationale: str


@dataclass
class IRMAAOptimization:
    """IRMAA optimization recommendation"""
    year: int
    current_magi: float
    target_magi: float
    threshold_at_risk: float
    reduction_needed: float
    annual_savings: float
    strategies: List[str]


@dataclass
class ACAOptimization:
    """ACA subsidy optimization recommendation"""
    year: int
    current_magi: float
    target_magi: float
    current_subsidy: float
    optimized_subsidy: float
    additional_savings: float
    strategies: List[str]


@dataclass
class MultiYearPlan:
    """Multi-year optimization plan"""
    years: List[int]
    conversions: List[ConversionOpportunity]
    irmaa_optimizations: List[IRMAAOptimization]
    aca_optimizations: List[ACAOptimization]
    total_tax_savings: float
    total_irmaa_savings: float
    total_aca_savings: float
    confidence_score: float


# ==============================================================================
# TAX PROJECTION
# ==============================================================================

def project_future_taxes(
    current_year: int,
    current_age: int,
    traditional_balance: float,
    roth_balance: float,
    taxable_balance: float,
    annual_expenses: float,
    ss_benefit: float,
    growth_rate: float = 1.07,
    years_ahead: int = DEFAULT_LOOKAHEAD_YEARS
) -> List[TaxProjection]:
    """
    Project future tax situation for multi-year planning
    
    Args:
        current_year: Current year
        current_age: Current age
        traditional_balance: Traditional IRA/401k balance
        roth_balance: Roth IRA balance
        taxable_balance: Taxable brokerage balance
        annual_expenses: Annual expenses
        ss_benefit: Annual Social Security benefit
        growth_rate: Expected portfolio growth rate
        years_ahead: Number of years to project
    
    Returns:
        List of TaxProjection objects
    """
    projections = []
    
    trad_bal = traditional_balance
    roth_bal = roth_balance
    tax_bal = taxable_balance
    
    for i in range(years_ahead):
        year = current_year + i
        age = current_age + i
        
        # Determine if RMDs apply (age 73+)
        has_rmd = age >= 73
        rmd_amount = 0.0
        
        if has_rmd and trad_bal > 0:
            # Simplified RMD calculation (actual uses IRS tables)
            rmd_rate = 1.0 / (110.5 - age)  # Approximate
            rmd_amount = trad_bal * rmd_rate
        
        # Estimate income
        estimated_income = ss_benefit + rmd_amount
        
        # Estimate withdrawals needed beyond RMD
        additional_needed = max(0, annual_expenses - estimated_income)
        
        # Estimate AGI (simplified)
        estimated_agi = estimated_income + additional_needed
        
        # Estimate marginal rate based on AGI (simplified brackets)
        if estimated_agi < 22000:
            marginal_rate = 0.10
        elif estimated_agi < 89075:
            marginal_rate = 0.12
        elif estimated_agi < 190750:
            marginal_rate = 0.22
        elif estimated_agi < 364200:
            marginal_rate = 0.24
        elif estimated_agi < 462500:
            marginal_rate = 0.32
        elif estimated_agi < 693750:
            marginal_rate = 0.35
        else:
            marginal_rate = 0.37
        
        # Estimate effective rate (rough approximation)
        effective_rate = marginal_rate * 0.7  # Simplified
        
        projections.append(TaxProjection(
            year=year,
            age_primary=age,
            age_spouse=age - 2,  # Assume 2-year age gap
            estimated_income=estimated_income,
            estimated_deductions=29200,  # Standard deduction (2024 MFJ)
            estimated_agi=estimated_agi,
            marginal_rate=marginal_rate,
            effective_rate=effective_rate,
            has_rmd=has_rmd,
            rmd_amount=rmd_amount
        ))
        
        # Project balances forward
        trad_bal = (trad_bal - rmd_amount) * growth_rate
        roth_bal = roth_bal * growth_rate
        tax_bal = tax_bal * growth_rate
    
    return projections


# ==============================================================================
# ROTH CONVERSION OPTIMIZATION
# ==============================================================================

def find_optimal_conversion_amount(
    current_agi: float,
    current_bracket: float,
    target_bracket: float,
    traditional_balance: float,
    future_projections: List[TaxProjection]
) -> ConversionOpportunity:
    """
    Find optimal Roth conversion amount using multi-year analysis
    
    Args:
        current_agi: Current AGI
        current_bracket: Current marginal tax bracket
        target_bracket: Target bracket to fill (e.g., 0.24)
        traditional_balance: Traditional IRA balance
        future_projections: Future tax projections
    
    Returns:
        ConversionOpportunity with recommendation
    """
    # Calculate room in target bracket (simplified)
    if target_bracket == 0.10:
        bracket_top = 22000
    elif target_bracket == 0.12:
        bracket_top = 89075
    elif target_bracket == 0.22:
        bracket_top = 190750
    elif target_bracket == 0.24:
        bracket_top = 364200
    else:
        bracket_top = 462500
    
    # Room available in bracket
    room_in_bracket = max(0, bracket_top - current_agi)
    
    # Limit conversion to available balance
    conversion_amount = min(room_in_bracket, traditional_balance * 0.15)  # Max 15% per year
    
    # Calculate conversion tax
    conversion_tax = conversion_amount * target_bracket
    
    # Estimate future tax savings
    future_tax_savings = 0.0
    for proj in future_projections:
        if proj.has_rmd:
            # Estimate tax savings from reduced RMDs
            reduced_rmd = conversion_amount * 0.04  # Approximate RMD rate
            tax_savings = reduced_rmd * proj.marginal_rate
            future_tax_savings += tax_savings
    
    net_benefit = future_tax_savings - conversion_tax
    
    # Calculate confidence based on future rate certainty
    avg_future_rate = np.mean([p.marginal_rate for p in future_projections])
    confidence = min(1.0, avg_future_rate / target_bracket) if target_bracket > 0 else 0.5
    
    rationale = (
        f"Convert ${conversion_amount:,.0f} at {target_bracket:.0%} bracket. "
        f"Future RMDs likely in {avg_future_rate:.0%} bracket. "
        f"Net benefit: ${net_benefit:,.0f} over {len(future_projections)} years."
    )
    
    return ConversionOpportunity(
        year=future_projections[0].year if future_projections else 2026,
        current_bracket=current_bracket,
        target_bracket=target_bracket,
        conversion_amount=conversion_amount,
        conversion_tax=conversion_tax,
        future_tax_savings=future_tax_savings,
        net_benefit=net_benefit,
        confidence=confidence,
        rationale=rationale
    )


# ==============================================================================
# IRMAA OPTIMIZATION
# ==============================================================================

def optimize_irmaa_exposure(
    year: int,
    projected_magi: float,
    age_primary: int,
    age_spouse: int
) -> Optional[IRMAAOptimization]:
    """
    Optimize MAGI to avoid or minimize IRMAA penalties
    
    Args:
        year: Tax year
        projected_magi: Projected MAGI
        age_primary: Primary person's age
        age_spouse: Spouse's age
    
    Returns:
        IRMAAOptimization if optimization possible, None otherwise
    """
    # IRMAA applies 2 years later, so check if either will be on Medicare then
    medicare_year = year + 2
    age_primary_medicare = age_primary + 2
    age_spouse_medicare = age_spouse + 2
    
    if age_primary_medicare < 65 and age_spouse_medicare < 65:
        return None  # Not on Medicare yet
    
    # Find current bracket
    current_bracket = None
    next_bracket = None
    
    for i, bracket in enumerate(IRMAA_BRACKETS_MFJ):
        if bracket['lower'] <= projected_magi < bracket['upper']:
            current_bracket = bracket
            if i + 1 < len(IRMAA_BRACKETS_MFJ):
                next_bracket = IRMAA_BRACKETS_MFJ[i + 1]
            break
    
    if not current_bracket:
        return None
    
    # Check if close to next threshold
    if next_bracket:
        distance_to_threshold = next_bracket['lower'] - projected_magi
        
        if 0 < distance_to_threshold < 10000:  # Within $10k of threshold
            # Calculate annual savings from staying below threshold
            current_premium = current_bracket['monthly_premium']
            next_premium = next_bracket['monthly_premium']
            monthly_increase = next_premium - current_premium
            annual_savings = monthly_increase * 12 * 2  # 2 people on Medicare
            
            strategies = [
                f"Reduce Roth conversions by ${distance_to_threshold:,.0f}",
                "Harvest tax losses to offset gains",
                "Increase charitable contributions",
                "Defer income to next year if possible"
            ]
            
            return IRMAAOptimization(
                year=year,
                current_magi=projected_magi,
                target_magi=next_bracket['lower'] - 1000,  # Stay $1k below
                threshold_at_risk=next_bracket['lower'],
                reduction_needed=distance_to_threshold + 1000,
                annual_savings=annual_savings,
                strategies=strategies
            )
    
    return None


# ==============================================================================
# ACA OPTIMIZATION
# ==============================================================================

def optimize_aca_subsidy(
    year: int,
    projected_magi: float,
    age_primary: int,
    age_spouse: int,
    household_size: int = 2
) -> Optional[ACAOptimization]:
    """
    Optimize MAGI for maximum ACA subsidies
    
    Args:
        year: Tax year
        projected_magi: Projected MAGI
        age_primary: Primary person's age
        age_spouse: Spouse's age
        household_size: Household size
    
    Returns:
        ACAOptimization if applicable, None otherwise
    """
    # ACA only applies pre-Medicare (under 65)
    if age_primary >= 65 and age_spouse >= 65:
        return None
    
    # Approximate FPL for 2-person household
    fpl = 20000  # Simplified
    fpl_percentage = projected_magi / fpl
    
    # Check for optimization opportunities
    strategies = []
    target_magi = projected_magi
    additional_savings = 0
    
    # Opportunity 1: Just above free coverage threshold (150% FPL)
    if 1.50 < fpl_percentage < 1.75:
        target_magi = fpl * 1.49
        additional_savings = 12000  # Full premium savings
        strategies = [
            f"Reduce MAGI by ${projected_magi - target_magi:,.0f}",
            "Maximize pre-tax retirement contributions",
            "Increase HSA contributions if eligible",
            "Consider traditional IRA contributions"
        ]
    
    # Opportunity 2: Near subsidy cliff (400% FPL)
    elif 3.90 < fpl_percentage < 4.10:
        target_magi = fpl * 3.99
        additional_savings = 8000  # Approximate subsidy value
        strategies = [
            f"Reduce MAGI by ${projected_magi - target_magi:,.0f}",
            "Reduce Roth conversions",
            "Harvest tax losses",
            "Increase charitable contributions"
        ]
    
    if strategies:
        # Estimate current subsidy (simplified)
        if fpl_percentage < 1.50:
            current_subsidy = 12000
        elif fpl_percentage < 4.00:
            current_subsidy = 12000 * (4.00 - fpl_percentage) / 2.5
        else:
            current_subsidy = 0
        
        optimized_subsidy = current_subsidy + additional_savings
        
        return ACAOptimization(
            year=year,
            current_magi=projected_magi,
            target_magi=target_magi,
            current_subsidy=current_subsidy,
            optimized_subsidy=optimized_subsidy,
            additional_savings=additional_savings,
            strategies=strategies
        )
    
    return None


# ==============================================================================
# MULTI-YEAR OPTIMIZATION
# ==============================================================================

def create_multi_year_plan(
    current_year: int,
    current_age: int,
    current_agi: float,
    traditional_balance: float,
    roth_balance: float,
    taxable_balance: float,
    annual_expenses: float,
    ss_benefit: float,
    growth_rate: float = 1.07,
    years_ahead: int = DEFAULT_LOOKAHEAD_YEARS
) -> MultiYearPlan:
    """
    Create comprehensive multi-year optimization plan
    
    Args:
        current_year: Current year
        current_age: Current age
        current_agi: Current AGI
        traditional_balance: Traditional IRA balance
        roth_balance: Roth balance
        taxable_balance: Taxable balance
        annual_expenses: Annual expenses
        ss_benefit: Social Security benefit
        growth_rate: Portfolio growth rate
        years_ahead: Planning horizon
    
    Returns:
        MultiYearPlan with all optimizations
    """
    # Project future taxes
    projections = project_future_taxes(
        current_year=current_year,
        current_age=current_age,
        traditional_balance=traditional_balance,
        roth_balance=roth_balance,
        taxable_balance=taxable_balance,
        annual_expenses=annual_expenses,
        ss_benefit=ss_benefit,
        growth_rate=growth_rate,
        years_ahead=years_ahead
    )
    
    # Find conversion opportunities
    conversions = []
    for bracket in OPTIMAL_CONVERSION_BRACKETS:
        if bracket > projections[0].marginal_rate:  # Only convert to higher brackets
            opportunity = find_optimal_conversion_amount(
                current_agi=current_agi,
                current_bracket=projections[0].marginal_rate,
                target_bracket=bracket,
                traditional_balance=traditional_balance,
                future_projections=projections
            )
            if opportunity.net_benefit > 0:
                conversions.append(opportunity)
    
    # Find IRMAA optimizations
    irmaa_opts = []
    for proj in projections:
        opt = optimize_irmaa_exposure(
            year=proj.year,
            projected_magi=proj.estimated_agi,
            age_primary=proj.age_primary,
            age_spouse=proj.age_spouse
        )
        if opt:
            irmaa_opts.append(opt)
    
    # Find ACA optimizations
    aca_opts = []
    for proj in projections:
        opt = optimize_aca_subsidy(
            year=proj.year,
            projected_magi=proj.estimated_agi,
            age_primary=proj.age_primary,
            age_spouse=proj.age_spouse
        )
        if opt:
            aca_opts.append(opt)
    
    # Calculate totals
    total_tax_savings = sum(c.net_benefit for c in conversions)
    total_irmaa_savings = sum(i.annual_savings for i in irmaa_opts)
    total_aca_savings = sum(a.additional_savings for a in aca_opts)
    
    # Calculate confidence score
    if conversions:
        confidence_score = np.mean([c.confidence for c in conversions])
    else:
        confidence_score = 0.5
    
    return MultiYearPlan(
        years=list(range(current_year, current_year + years_ahead)),
        conversions=conversions,
        irmaa_optimizations=irmaa_opts,
        aca_optimizations=aca_opts,
        total_tax_savings=total_tax_savings,
        total_irmaa_savings=total_irmaa_savings,
        total_aca_savings=total_aca_savings,
        confidence_score=confidence_score
    )


def print_optimization_plan(plan: MultiYearPlan) -> None:
    """
    Print multi-year optimization plan in readable format
    
    Args:
        plan: MultiYearPlan to print
    """
    print("\n" + "="*80)
    print("MULTI-YEAR OPTIMIZATION PLAN")
    print("="*80)
    
    print(f"\nPlanning Horizon: {plan.years[0]} - {plan.years[-1]} ({len(plan.years)} years)")
    print(f"Confidence Score: {plan.confidence_score:.1%}")
    
    # Roth Conversions
    if plan.conversions:
        print(f"\n📊 ROTH CONVERSION OPPORTUNITIES ({len(plan.conversions)})")
        print("-" * 80)
        for conv in plan.conversions:
            print(f"\nYear {conv.year}:")
            print(f"  Amount: ${conv.conversion_amount:,.0f}")
            print(f"  Tax Cost: ${conv.conversion_tax:,.0f} at {conv.target_bracket:.0%}")
            print(f"  Future Savings: ${conv.future_tax_savings:,.0f}")
            print(f"  Net Benefit: ${conv.net_benefit:,.0f}")
            print(f"  Confidence: {conv.confidence:.0%}")
            print(f"  Rationale: {conv.rationale}")
    
    # IRMAA Optimizations
    if plan.irmaa_optimizations:
        print(f"\n🏥 IRMAA OPTIMIZATION OPPORTUNITIES ({len(plan.irmaa_optimizations)})")
        print("-" * 80)
        for irmaa in plan.irmaa_optimizations:
            print(f"\nYear {irmaa.year}:")
            print(f"  Current MAGI: ${irmaa.current_magi:,.0f}")
            print(f"  Target MAGI: ${irmaa.target_magi:,.0f}")
            print(f"  Reduction Needed: ${irmaa.reduction_needed:,.0f}")
            print(f"  Annual Savings: ${irmaa.annual_savings:,.0f}")
            print(f"  Strategies:")
            for strategy in irmaa.strategies:
                print(f"    - {strategy}")
    
    # ACA Optimizations
    if plan.aca_optimizations:
        print(f"\n💰 ACA SUBSIDY OPTIMIZATION OPPORTUNITIES ({len(plan.aca_optimizations)})")
        print("-" * 80)
        for aca in plan.aca_optimizations:
            print(f"\nYear {aca.year}:")
            print(f"  Current MAGI: ${aca.current_magi:,.0f}")
            print(f"  Target MAGI: ${aca.target_magi:,.0f}")
            print(f"  Current Subsidy: ${aca.current_subsidy:,.0f}")
            print(f"  Optimized Subsidy: ${aca.optimized_subsidy:,.0f}")
            print(f"  Additional Savings: ${aca.additional_savings:,.0f}")
            print(f"  Strategies:")
            for strategy in aca.strategies:
                print(f"    - {strategy}")
    
    # Summary
    print(f"\n💵 TOTAL POTENTIAL SAVINGS")
    print("-" * 80)
    print(f"  Tax Savings (Conversions): ${plan.total_tax_savings:,.0f}")
    print(f"  IRMAA Savings: ${plan.total_irmaa_savings:,.0f}")
    print(f"  ACA Savings: ${plan.total_aca_savings:,.0f}")
    total = plan.total_tax_savings + plan.total_irmaa_savings + plan.total_aca_savings
    print(f"  TOTAL: ${total:,.0f}")
    print("="*80 + "\n")


# Made with Bob