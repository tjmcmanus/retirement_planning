"""
Portfolio Withdrawal Strategy Module - 5 Stages of Life

This module implements a comprehensive withdrawal strategy across 5 life stages:
1. Accumulation: Employed, earning wages, tax-efficient asset accumulation
2. Early Retirement: Pre-Medicare, pre-SS, pre-RMD with Roth conversions
3. Medicare Stage: IRMAA optimization with continued Roth conversions
4. Social Security Stage: SS benefits + Medicare, pre-RMD optimization
5. RMD Stage: Required Minimum Distributions with full retirement income

Author: IBM Bob
Date: 2026-02-22
"""

import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from load_data import (
    get_income_tax_brackets,
    get_cap_gains_brackets,
    get_std_deduction,
    get_medicare_costs,
    get_atm_costs,
    get_networth_by_month
)
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
        
        # Get tax brackets for the year
        tax_brackets = get_income_tax_brackets(year)
        std_deduction_df = get_std_deduction(year)
        
        # Calculate AGI after 401k contributions (pre-tax)
        agi = wages - contribution_401k
        
        # Determine optimal contribution strategy based on tax bracket
        taxable_income = agi - std_deduction_df.iloc[0]['deduction']
        federal_tax, max_rate, upper_max = calculate_taxable_income(taxable_income, tax_brackets)
        
        logger.debug(f"AGI: ${agi:,.2f}, Tax bracket: {max_rate:.1%}, Tax: ${federal_tax:,.2f}")
        
        # Update balances with contributions
        new_balances = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable,
            traditional=balances.traditional + contribution_401k,
            roth=balances.roth + contribution_roth,
            daf=balances.daf
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
            roth_conversion=0,
            ltcg_harvested=0,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=federal_tax,
            irmaa_penalty=0,
            aca_premium=0,
            balances=new_balances
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
        
        # Calculate 4% withdrawal need (includes taxes)
        total_need = expenses * 1.15  # Add 15% buffer for taxes
        
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
        ltcg_harvested = min(total_need, ltcg_room, balances.taxable * 0.5)
        
        logger.debug(f"LTCG harvested: ${ltcg_harvested:,.2f} (0% bracket room: ${ltcg_room:,.2f})")
        
        # Calculate Roth conversion opportunity
        # Find the 12% or 22% bracket upper limit for conversions
        target_bracket_rate = 0.12  # Target 12% bracket for conversions
        try:
            target_bracket_upper = getUpperIncomeRate(target_bracket_rate, tax_brackets)
        except ValueError:
            target_bracket_rate = 0.22
            target_bracket_upper = getUpperIncomeRate(target_bracket_rate, tax_brackets)
        
        # Calculate conversion room
        current_income = ltcg_harvested
        conversion_room = target_bracket_upper - std_deduction - current_income
        
        # Determine actual conversion amount
        if target_conversion > 0:
            roth_conversion = min(target_conversion, conversion_room, balances.traditional)
        else:
            # Default: fill up to target bracket
            roth_conversion = min(conversion_room, balances.traditional)
        
        logger.debug(f"Roth conversion: ${roth_conversion:,.2f} (room: ${conversion_room:,.2f})")
        
        # Calculate taxes
        total_income = ltcg_harvested + roth_conversion
        agi = total_income - std_deduction
        
        # Income tax on conversions
        federal_tax, max_rate, upper_max = calculate_taxable_income(agi, tax_brackets)
        
        # Capital gains tax
        cg_tax = calculate_cap_gains(agi - ltcg_harvested, cg_brackets, ltcg_harvested)
        
        total_tax = federal_tax + cg_tax
        
        logger.debug(f"Total tax: ${total_tax:,.2f} (income: ${federal_tax:,.2f}, CG: ${cg_tax:,.2f})")
        
        # Determine withdrawal sources to cover expenses + taxes
        total_outflow = expenses + total_tax
        
        # Withdraw from taxable first (already harvested LTCG)
        taxable_withdrawal = ltcg_harvested
        
        # If need more, withdraw from traditional or Roth
        remaining_need = total_outflow - taxable_withdrawal
        traditional_withdrawal = 0
        roth_withdrawal = 0
        
        if remaining_need > 0:
            if balances.traditional > roth_conversion:
                traditional_withdrawal = min(remaining_need, balances.traditional - roth_conversion)
                remaining_need -= traditional_withdrawal
            
            if remaining_need > 0:
                roth_withdrawal = min(remaining_need, balances.roth)
        
        # Update balances
        new_balances = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable - taxable_withdrawal,
            traditional=balances.traditional - traditional_withdrawal - roth_conversion,
            roth=balances.roth + roth_conversion - roth_withdrawal,
            daf=balances.daf
        )
        
        # Apply growth rate to remaining balances
        growth_rate = kwargs.get('growth_rate', 1.07)
        new_balances.taxable *= growth_rate
        new_balances.traditional *= growth_rate
        new_balances.roth *= growth_rate
        
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=traditional_withdrawal,
            taxable_withdrawal=taxable_withdrawal,
            roth_withdrawal=roth_withdrawal,
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=total_tax,
            irmaa_penalty=0,
            aca_premium=0,
            balances=new_balances
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
        
        # Calculate Roth conversion with IRMAA awareness
        # Stay below next IRMAA threshold
        irmaa_headroom = next_irmaa_threshold - ltcg_harvested - std_deduction
        
        # Also consider tax bracket optimization (12% or 22%)
        target_bracket_rate = 0.12
        try:
            target_bracket_upper = getUpperIncomeRate(target_bracket_rate, tax_brackets)
        except ValueError:
            target_bracket_rate = 0.22
            target_bracket_upper = getUpperIncomeRate(target_bracket_rate, tax_brackets)
        
        tax_headroom = target_bracket_upper - std_deduction - ltcg_harvested
        
        # Use the more conservative limit
        conversion_room = min(irmaa_headroom, tax_headroom)
        
        if target_conversion > 0:
            roth_conversion = min(target_conversion, conversion_room, balances.traditional)
        else:
            roth_conversion = min(conversion_room, balances.traditional)
        
        logger.debug(f"Roth conversion: ${roth_conversion:,.2f} (IRMAA room: ${irmaa_headroom:,.2f}, tax room: ${tax_headroom:,.2f})")
        
        # Calculate taxes
        total_income = ltcg_harvested + roth_conversion
        agi = total_income - std_deduction
        
        federal_tax, max_rate, upper_max = calculate_taxable_income(agi, tax_brackets)
        cg_tax = calculate_cap_gains(agi - ltcg_harvested, cg_brackets, ltcg_harvested)
        total_tax = federal_tax + cg_tax
        
        # Determine withdrawals
        total_outflow = expenses + total_tax + irmaa_penalty
        taxable_withdrawal = ltcg_harvested
        
        remaining_need = total_outflow - taxable_withdrawal
        traditional_withdrawal = 0
        roth_withdrawal = 0
        
        if remaining_need > 0:
            if balances.traditional > roth_conversion:
                traditional_withdrawal = min(remaining_need, balances.traditional - roth_conversion)
                remaining_need -= traditional_withdrawal
            
            if remaining_need > 0:
                roth_withdrawal = min(remaining_need, balances.roth)
        
        # Update balances
        new_balances = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable - taxable_withdrawal,
            traditional=balances.traditional - traditional_withdrawal - roth_conversion,
            roth=balances.roth + roth_conversion - roth_withdrawal,
            daf=balances.daf
        )
        
        # Apply growth
        growth_rate = kwargs.get('growth_rate', 1.07)
        new_balances.taxable *= growth_rate
        new_balances.traditional *= growth_rate
        new_balances.roth *= growth_rate
        
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=traditional_withdrawal,
            taxable_withdrawal=taxable_withdrawal,
            roth_withdrawal=roth_withdrawal,
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=0,
            balances=new_balances
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
        
        # Tax bracket optimization
        target_bracket_rate = 0.22
        try:
            target_bracket_upper = getUpperIncomeRate(target_bracket_rate, tax_brackets)
        except ValueError:
            target_bracket_rate = 0.24
            target_bracket_upper = getUpperIncomeRate(target_bracket_rate, tax_brackets)
        
        tax_headroom = target_bracket_upper - std_deduction - current_income
        conversion_room = min(irmaa_headroom, tax_headroom)
        
        if target_conversion > 0:
            roth_conversion = min(target_conversion, conversion_room, balances.traditional)
        else:
            roth_conversion = min(conversion_room * 0.8, balances.traditional)  # Conservative
        
        logger.debug(f"Roth conversion: ${roth_conversion:,.2f} with SS income")
        
        # Calculate taxes
        total_income = taxable_ss + ltcg_harvested + roth_conversion
        agi = total_income - std_deduction
        
        federal_tax, max_rate, upper_max = calculate_taxable_income(agi, tax_brackets)
        cg_tax = calculate_cap_gains(agi - ltcg_harvested, cg_brackets, ltcg_harvested)
        total_tax = federal_tax + cg_tax
        
        # Determine withdrawals
        total_outflow = expenses + total_tax + irmaa_penalty - ss_benefits
        taxable_withdrawal = ltcg_harvested
        
        remaining_need = max(0, total_outflow - taxable_withdrawal)
        traditional_withdrawal = 0
        roth_withdrawal = 0
        
        if remaining_need > 0:
            if balances.traditional > roth_conversion:
                traditional_withdrawal = min(remaining_need, balances.traditional - roth_conversion)
                remaining_need -= traditional_withdrawal
            
            if remaining_need > 0:
                roth_withdrawal = min(remaining_need, balances.roth)
        
        # Update balances
        new_balances = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable - taxable_withdrawal,
            traditional=balances.traditional - traditional_withdrawal - roth_conversion,
            roth=balances.roth + roth_conversion - roth_withdrawal,
            daf=balances.daf
        )
        
        # Apply growth
        growth_rate = kwargs.get('growth_rate', 1.07)
        new_balances.taxable *= growth_rate
        new_balances.traditional *= growth_rate
        new_balances.roth *= growth_rate
        
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=ss_benefits,
            rmd_amount=0,
            traditional_withdrawal=traditional_withdrawal,
            taxable_withdrawal=taxable_withdrawal,
            roth_withdrawal=roth_withdrawal,
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=0,
            balances=new_balances
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
        target_bracket_rate = 0.24
        try:
            target_bracket_upper = getUpperIncomeRate(target_bracket_rate, tax_brackets)
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
        
        # Determine withdrawals
        total_outflow = expenses + total_tax + irmaa_penalty - ss_benefits
        
        # RMD is mandatory withdrawal
        traditional_withdrawal = rmd_amount + roth_conversion
        taxable_withdrawal = ltcg_harvested
        
        remaining_need = max(0, total_outflow - rmd_amount - taxable_withdrawal)
        roth_withdrawal = 0
        
        if remaining_need > 0:
            # Additional traditional withdrawal if needed
            if balances.traditional > traditional_withdrawal:
                additional_trad = min(remaining_need, balances.traditional - traditional_withdrawal)
                traditional_withdrawal += additional_trad
                remaining_need -= additional_trad
            
            # Roth as last resort
            if remaining_need > 0:
                roth_withdrawal = min(remaining_need, balances.roth)
        
        # Update balances
        new_balances = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable - taxable_withdrawal,
            traditional=balances.traditional - traditional_withdrawal,
            roth=balances.roth + roth_conversion - roth_withdrawal,
            daf=balances.daf
        )
        
        # Apply growth
        growth_rate = kwargs.get('growth_rate', 1.07)
        new_balances.taxable *= growth_rate
        new_balances.traditional *= growth_rate
        new_balances.roth *= growth_rate
        
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            wages=0,
            ss_benefits=ss_benefits,
            rmd_amount=rmd_amount,
            traditional_withdrawal=traditional_withdrawal,
            taxable_withdrawal=taxable_withdrawal,
            roth_withdrawal=roth_withdrawal,
            roth_conversion=roth_conversion,
            ltcg_harvested=ltcg_harvested,
            daf_contribution=0,
            expenses=expenses,
            federal_tax=total_tax,
            irmaa_penalty=irmaa_penalty,
            aca_premium=0,
            balances=new_balances
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
            **kwargs: Additional parameters (growth_rate, expense_inflation, etc.)
        
        Returns:
            DataFrame with yearly strategies
        """
        logger.info(f"Calculating strategy from {start_year} to {end_year}")
        
        results = []
        balances = initial_balances
        expenses = initial_expenses
        
        # Get parameters
        growth_rate = kwargs.get('growth_rate', 1.07)
        expense_inflation = kwargs.get('expense_inflation', 0.993)  # Slight deflation
        ss_claiming_age = kwargs.get('ss_claiming_age', 67)
        
        # Track MAGI for IRMAA (2-year lookback)
        magi_history = {}
        
        for year in range(start_year, end_year + 1):
            # Get ages
            age_primary = get_age(year, person1_name)
            age_spouse = get_age(year, person2_name)
            
            # Determine if has wages or SS
            has_wages = kwargs.get('has_wages', False) and year < kwargs.get('retirement_year', 2026)
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
            
            # Determine stage
            stage = self.determine_stage(age_primary, age_spouse, year, has_wages, has_ss)
            
            # Calculate strategy
            strategy = stage.calculate_strategy(
                year=year,
                balances=balances,
                expenses=expenses,
                age_primary=age_primary,
                age_spouse=age_spouse,
                ss_benefits=ss_benefits,
                prior_magi=prior_magi,
                **kwargs
            )
            
            # Store MAGI for future IRMAA calculations
            current_magi = (strategy.ss_benefits * TAXABLE_SS_RATE + 
                          strategy.traditional_withdrawal + 
                          strategy.roth_conversion + 
                          strategy.ltcg_harvested)
            magi_history[year] = current_magi
            
            # Update for next year
            balances = strategy.balances
            expenses *= expense_inflation
            
            # Store result
            results.append(strategy)
            
            logger.debug(f"Year {year} complete: Stage={stage.name}, "
                        f"Total balance=${balances.total():,.2f}")
        
        # Convert to DataFrame
        return self._strategies_to_dataframe(results)
    
    def _strategies_to_dataframe(self, strategies: list) -> pd.DataFrame:
        """Convert list of YearlyStrategy objects to DataFrame"""
        data = []
        for s in strategies:
            data.append({
                'Year': s.year,
                'Age': f"{s.age_primary}/{s.age_spouse}",
                'Stage': s.stage,
                'Wages': s.wages,
                'SS Benefits': s.ss_benefits,
                'RMD': s.rmd_amount,
                'Traditional Withdrawal': s.traditional_withdrawal,
                'Taxable Withdrawal': s.taxable_withdrawal,
                'Roth Withdrawal': s.roth_withdrawal,
                'Roth Conversion': s.roth_conversion,
                'LTCG Harvested': s.ltcg_harvested,
                'DAF Contribution': s.daf_contribution,
                'Expenses': s.expenses,
                'Federal Tax': s.federal_tax,
                'IRMAA Penalty': s.irmaa_penalty,
                'ACA Premium': s.aca_premium,
                'Cash Balance': s.balances.cash,
                'Taxable Balance': s.balances.taxable,
                'Traditional Balance': s.balances.traditional,
                'Roth Balance': s.balances.roth,
                'DAF Balance': s.balances.daf,
                'Total Portfolio': s.balances.total()
            })
        
        return pd.DataFrame(data)


def build_withdrawal_strategy_display(start_year: int = None, 
                                      end_year: int = 2051,
                                      **kwargs) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build withdrawal strategy display for years current through 2051
    
    Args:
        start_year: Starting year (defaults to current year)
        end_year: Ending year (default 2051)
        **kwargs: Additional parameters
    
    Returns:
        Tuple of (strategy_df, balances_df)
    """
    if start_year is None:
        start_year = datetime.now().year
    
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
            initial_balances = PortfolioBalances(
                cash=float(summary_df[summary_df['account_type'] == 'Cash']['market_value'].sum()),
                taxable=float(summary_df[summary_df['account_type'] == 'Brokerage']['market_value'].sum()),
                traditional=float(summary_df[summary_df['account_type'] == 'Traditional']['market_value'].sum()),
                roth=float(summary_df[summary_df['account_type'] == 'Roth']['market_value'].sum()),
                daf=0
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
                traditional=800000,
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
