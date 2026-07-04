"""
Portfolio Withdrawal Strategy Module - 6 Stages of Life

This module implements a comprehensive withdrawal strategy across 6 life stages:
1. Accumulation: Employed, earning wages, tax-efficient asset accumulation
2. Prep for Retirement: Employed, within 10 years of retirement, balance Roth/Traditional/Taxable
3. Early Retirement: Pre-Medicare, pre-SS, pre-RMD with BETR-optimized Roth conversions
4. Medicare Stage: IRMAA optimization with BETR-based continued Roth conversions
5. Social Security Stage: SS benefits + Medicare, pre-RMD optimization with BETR
6. RMD Stage: Required Minimum Distributions with full retirement income

Key Features:
- BETR (Break-Even Tax Rate) algorithm for optimal Roth conversion decisions
- RMD lookback optimization to reduce future tax burden
- Tax-efficient withdrawal sequencing across all life stages
- IRMAA threshold management with 2-year lookback
- ACA subsidy optimization for early retirees
- Dynamic Security Selection for intelligent withdrawal decisions

Based on Vanguard Research: "A 'BETR' approach to Roth conversions" (July 2025)

Author: IBM Bob
Date: 2026-03-17
Version: 2.1 - Dynamic Security Selection Integration
"""

import functools
import itertools
import pandas as pd
import numpy as np
import logging
import os
import types
from datetime import datetime
from typing import Dict, Tuple, Optional, List, Any, Union, Iterator, Sequence, cast, TypedDict
from dataclasses import dataclass, field, asdict, replace
from enum import Enum

# Dynamic Security Selection Integration
# Note: Import is deferred to avoid circular dependency
SMART_SELECTION_AVAILABLE = False
withdraw_from_brokerage_smart = None
should_use_smart_selection = None
format_liquidation_summary_for_log = None
DEFAULT_TARGET_ALLOCATION = {'Cash': 10.0, 'Bonds': 30.0, 'Stocks': 60.0}

def _init_smart_selection():
    """Initialize smart selection module (deferred import to avoid circular dependency)."""
    global SMART_SELECTION_AVAILABLE, withdraw_from_brokerage_smart
    global should_use_smart_selection, format_liquidation_summary_for_log, DEFAULT_TARGET_ALLOCATION
    
    if SMART_SELECTION_AVAILABLE:
        return  # Already initialized
    
    try:
        from security_selection_integration import (
            withdraw_from_brokerage_smart as _withdraw,
            should_use_smart_selection as _should_use,
            format_liquidation_summary_for_log as _format,
            DEFAULT_TARGET_ALLOCATION as _default_alloc,
        )
        withdraw_from_brokerage_smart = _withdraw
        should_use_smart_selection = _should_use
        format_liquidation_summary_for_log = _format
        DEFAULT_TARGET_ALLOCATION = _default_alloc
        SMART_SELECTION_AVAILABLE = True
        logger.info("Smart security selection enabled")
    except ImportError as e:
        logger.warning(f"Security selection module not available: {e}, using FIFO fallback")
        SMART_SELECTION_AVAILABLE = False

from load_data import (
    get_income_tax_brackets,
    get_cap_gains_brackets,
    get_std_deduction,
    get_medicare_costs,
    get_atm_costs,
    get_networth_by_month,
    get_fica_limits,
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
    getUpperIncomeRate,
    getNextHigherTaxRate
)
from ssibenefits import get_monthly_benefit
from ssi_calculator import (
    calculate_benefit_at_claiming_age,
    calculate_benefit_with_cola,
    DEFAULT_COLA_RATE
)
from betr_roth_conversion import (
    optimize_conversion_amount,
    calculate_betr,
    BETRInputs,
    BETRResults
)

# ==============================================================================
# REFACTORED STAGES - Phase 1 Integration
# ==============================================================================
# Import refactored life stage implementations with dependency injection
# These are aliased to avoid conflicts with existing stage classes during migration
# Import refactored life stage implementations
from strategy_core.stages import (
    Stage1Accumulation,
    Stage2PrepForRetirement,
    Stage3EarlyRetirement,
    Stage4Medicare,
    Stage5SocialSecurity,
    Stage6RMD,
    Stage7SurvivingSpouse
)
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager

# Shared dependency instances (singleton pattern)
_tax_calculator: Optional[TaxCalculator] = None
_account_manager: Optional[AccountManager] = None

def get_tax_calculator() -> TaxCalculator:
    """Get or create singleton TaxCalculator instance."""
    global _tax_calculator
    if _tax_calculator is None:
        _tax_calculator = TaxCalculator()
    return _tax_calculator

def get_account_manager() -> AccountManager:
    """Get or create singleton AccountManager instance."""
    global _account_manager
    if _account_manager is None:
        _account_manager = AccountManager()
    return _account_manager

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Cost basis assumption for Brokerage account withdrawals
# Until intelligent portfolio management is implemented, assume:
# - 60% of withdrawal is return of cost basis (tax-free)
# - 40% of withdrawal is long-term capital gains (taxable)
BROKERAGE_COST_BASIS_RATIO = 0.60
BROKERAGE_LTCG_RATIO = 0.40

# Default columns shown in the year-by-year section of the strategy report.
# Stored as an immutable tuple so callers can reference it without risk of
# mutation and to avoid re-constructing the sequence on every call.
_REPORT_DEFAULT_DISPLAY_COLS: tuple = (
    'Year', 'Age', 'Stage', 'Roth Conversion',
    'Federal Tax', 'IRMAA Penalty', 'Total Portfolio',
)

# Net Investment Income Tax rate (IRC §1411, fixed since 2013)
NIIT_RATE: float = 0.038

# NIIT thresholds (not indexed for inflation since 2013, per IRC §1411)
NIIT_THRESHOLDS: Dict[str, int] = {
    'married_filing_jointly':    250_000,
    'single':                    200_000,
    'married_filing_separately': 125_000,
    'head_of_household':         200_000,
}

# Minimum age for Medicare eligibility (fixed by statute)
MEDICARE_ELIGIBILITY_AGE: int = 65

# Medicare Part D base premium (annual; updated each year by CMS)
PART_D_ANNUAL_BASE_PREMIUM: int = 480   # ~$40/month average

# Medigap supplemental insurance premium (annual estimate)
MEDIGAP_ANNUAL_PREMIUM: int = 2_400     # ~$200/month average

# Medicare Part B standard monthly premium (2024; updated annually by CMS).
# Used as the fallback when IRMAA bracket data is unavailable.
PART_B_MONTHLY_STANDARD_PREMIUM: float = 174.70

# Minimum age for penalty-free withdrawals from Traditional IRA / 401k (IRC §72(t))
EARLY_WITHDRAWAL_PENALTY_AGE: float = 59.5

# ACA marketplace premium estimate per person per month (pre-Medicare)
# Annualised: ACA_MONTHLY_PREMIUM_PER_PERSON * 12 = $12,000/year
ACA_MONTHLY_PREMIUM_PER_PERSON: int = 1_000

# Annual out-of-pocket healthcare costs by health status
OOP_COSTS_BY_HEALTH_STATUS: Dict[str, int] = {
    'healthy': 4_000,
    'average': 6_500,
    'chronic': 12_000,
}
OOP_COST_DEFAULT: int = OOP_COSTS_BY_HEALTH_STATUS['average']

# Long-term care insurance annual premium per person (average estimate)
LTC_ANNUAL_PREMIUM_PER_PERSON: int = 3_500

# IRMAA uses a 2-year lookback: the surcharge applied in year N is based on
# MAGI reported in year N-2.  This constant makes that window explicit and
# provides a single point of change should the IRS ever alter the period.
_IRMAA_LOOKBACK_YEARS: int = 2

# Minimum deficit below which buffer replenishment is skipped (de-minimis threshold).
# Avoids triggering taxable distributions for trivially small shortfalls.
# Used by both replenish_cash_buffer() and replenish_brokerage_buffer().
_BUFFER_REPLENISHMENT_MIN_DEFICIT: float = 100.0

# Maximum fraction of the Traditional balance that may be distributed to the
# brokerage buffer in a single year.  Caps the ordinary-income tax hit.
# Doubled from 0.15 to 0.30 to allow more aggressive buffer replenishment.
_MAX_TRADITIONAL_TO_BROKERAGE_RATE: float = 0.30


# ==============================================================================
# COST BASIS TRACKING - Brokerage Account Management
# ==============================================================================

@dataclass
class BrokerageTransaction:
    """
    Track individual transfers into brokerage account with cost basis.
    
    Each transaction represents a discrete transfer of funds into the brokerage
    account, maintaining its original cost basis for accurate LTCG calculations.
    Uses FIFO (First In, First Out) method for withdrawals.
    
    Attributes:
        year: Current year in the simulation
        transfer_date: Year when funds were transferred into brokerage
        original_amount: Initial amount when transferred (for reference)
        cost_basis: Tax basis - amount that can be withdrawn tax-free
        current_value: Current market value after growth
        years_held: Number of years since transfer (for holding period tracking)
        source: Origin of funds (e.g., "initial", "trad_to_brok", "rmd_to_brok")
    
    Example:
        >>> # Transfer $50k from Traditional IRA to Brokerage in 2024
        >>> txn = BrokerageTransaction(
        ...     year=2024, transfer_date=2024, original_amount=50000,
        ...     cost_basis=50000, current_value=50000, years_held=0,
        ...     source="trad_to_brok"
        ... )
        >>> # After 1 year with 7% growth
        >>> txn.apply_growth(1.07)
        >>> print(f"Value: ${txn.current_value:,.0f}, Gain: ${txn.calculate_gain():,.0f}")
        Value: $53,500, Gain: $3,500
    """
    year: int
    transfer_date: int
    original_amount: float
    cost_basis: float
    current_value: float
    years_held: int
    source: str
    
    def apply_growth(self, growth_rate: float) -> None:
        """
        Apply annual growth to this transaction.
        
        Args:
            growth_rate: Growth multiplier (e.g., 1.07 for 7% growth)
        """
        self.current_value *= growth_rate
        self.years_held += 1
    
    def calculate_gain(self) -> float:
        """
        Calculate unrealized capital gain.
        
        Returns:
            Unrealized gain (current_value - cost_basis)
        """
        return self.current_value - self.cost_basis
    
    def calculate_gain_percentage(self) -> float:
        """
        Calculate gain as percentage of cost basis.
        
        Returns:
            Gain percentage (0.0 if cost_basis is zero)
        """
        if self.cost_basis == 0:
            return 0.0
        return (self.current_value - self.cost_basis) / self.cost_basis * 100


@dataclass
class BrokerageAccount:
    """
    Manage brokerage account with actual cost basis tracking.
    
    Replaces the fixed 60/40 assumption with real transaction-level tracking.
    Each transfer into the brokerage account is recorded as a separate lot,
    maintaining its cost basis and tracking growth over time.
    
    Withdrawals use FIFO (First In, First Out) method, which:
    - Minimizes short-term capital gains (oldest lots are long-term)
    - Simplifies tax reporting
    - Is commonly used by brokerages
    
    Attributes:
        transactions: List of BrokerageTransaction objects (lots)
    
    Properties:
        total_value: Current market value of all holdings
        total_basis: Total cost basis of all holdings
        total_gains: Total unrealized gains
        ltcg_ratio: Actual LTCG ratio (gains / value)
        basis_ratio: Actual basis ratio (basis / value)
    
    Example:
        >>> account = BrokerageAccount()
        >>> account.add_transfer(2024, 100000, "initial_portfolio")
        >>> account.apply_annual_growth(1.07, 2025)
        >>> basis, ltcg = account.withdraw_fifo(50000, 2025)
        >>> print(f"Withdrew $50k: ${basis:,.0f} basis, ${ltcg:,.0f} LTCG")
    """
    transactions: List[BrokerageTransaction] = field(default_factory=list)
    
    @property
    def total_value(self) -> float:
        """Current market value of all holdings."""
        return sum(t.current_value for t in self.transactions)
    
    @property
    def total_basis(self) -> float:
        """Total cost basis of all holdings."""
        return sum(t.cost_basis for t in self.transactions)
    
    @property
    def total_gains(self) -> float:
        """Total unrealized gains."""
        return self.total_value - self.total_basis
    
    @property
    def ltcg_ratio(self) -> float:
        """
        Actual LTCG ratio (gains / value).
        
        Returns:
            Ratio of gains to total value (0.0 to 1.0)
            Falls back to 0.40 if account is empty
        """
        if self.total_value == 0:
            return BROKERAGE_LTCG_RATIO  # Fallback to 40% assumption
        return self.total_gains / self.total_value
    
    @property
    def basis_ratio(self) -> float:
        """
        Actual basis ratio (basis / value).
        
        Returns:
            Ratio of basis to total value (0.0 to 1.0)
        """
        return 1.0 - self.ltcg_ratio
    
    def add_transfer(self, year: int, amount: float, source: str) -> None:
        """
        Record new money entering brokerage account.
        
        Creates a new transaction lot with cost basis equal to the transfer amount.
        This represents tax-paid money entering the account (e.g., from Traditional
        IRA conversion, RMD distribution, or initial portfolio).
        
        Args:
            year: Current year
            amount: Amount being transferred
            source: Origin of funds (for tracking and reporting)
        """
        if amount <= 0:
            return
            
        transaction = BrokerageTransaction(
            year=year,
            transfer_date=year,
            original_amount=amount,
            cost_basis=amount,
            current_value=amount,
            years_held=0,
            source=source
        )
        self.transactions.append(transaction)
        logger.info(f"Brokerage: Added ${amount:,.0f} from {source} in year {year}")
    
    def apply_annual_growth(self, growth_rate: float, year: int) -> None:
        """
        Apply growth to all holdings.
        
        Args:
            growth_rate: Growth multiplier (e.g., 1.07 for 7% growth)
            year: Current year (for logging)
        """
        for transaction in self.transactions:
            transaction.apply_growth(growth_rate)
        
        logger.debug(
            f"Year {year}: Brokerage grew to ${self.total_value:,.0f} "
            f"(basis: ${self.total_basis:,.0f}, gains: ${self.total_gains:,.0f}, "
            f"LTCG ratio: {self.ltcg_ratio:.1%})"
        )
    
    def withdraw_fifo(self, amount: float, year: int) -> Tuple[float, float]:
        """
        Withdraw using FIFO (First In, First Out) method.
        
        Withdraws from oldest lots first, calculating the proportional split
        between tax-free basis return and taxable LTCG for each lot.
        
        Args:
            amount: Amount to withdraw
            year: Current year (for logging)
        
        Returns:
            Tuple of (basis_returned, ltcg_realized)
            - basis_returned: Tax-free return of cost basis
            - ltcg_realized: Taxable long-term capital gains
        
        Example:
            >>> # Lot 1: $100k basis, $150k value (50% gain)
            >>> # Withdraw $75k from this lot
            >>> # Returns: $50k basis (tax-free), $25k LTCG (taxable)
        """
        if amount > self.total_value:
            logger.warning(
                f"Withdrawal ${amount:,.0f} exceeds balance ${self.total_value:,.0f}"
            )
            amount = self.total_value
        
        if amount <= 0:
            return 0.0, 0.0
        
        remaining = amount
        basis_returned = 0.0
        ltcg_realized = 0.0
        
        # Sort by transfer date (FIFO = oldest first)
        sorted_transactions = sorted(self.transactions, key=lambda t: t.transfer_date)
        
        for transaction in sorted_transactions:
            if remaining <= 0:
                break
            
            if transaction.current_value <= 0:
                continue
            
            # Withdraw from this lot
            withdraw_from_lot = min(remaining, transaction.current_value)
            
            # Calculate proportional basis and gains
            lot_ratio = withdraw_from_lot / transaction.current_value
            basis_from_lot = transaction.cost_basis * lot_ratio
            gains_from_lot = withdraw_from_lot - basis_from_lot
            
            # Accumulate
            basis_returned += basis_from_lot
            ltcg_realized += gains_from_lot
            
            # Update transaction (reduce both value and basis proportionally)
            transaction.current_value -= withdraw_from_lot
            transaction.cost_basis -= basis_from_lot
            
            remaining -= withdraw_from_lot
            
            logger.debug(
                f"  Withdrew ${withdraw_from_lot:,.0f} from {transaction.source} "
                f"(year {transaction.transfer_date}, held {transaction.years_held} years): "
                f"basis ${basis_from_lot:,.0f}, gain ${gains_from_lot:,.0f}"
            )
        
        # Clean up depleted transactions (keep lots with >$0.01 to avoid floating point issues)
        self.transactions = [t for t in self.transactions if t.current_value > 0.01]
        
        logger.info(
            f"Year {year}: Withdrew ${amount:,.0f} from brokerage "
            f"(basis: ${basis_returned:,.0f}, LTCG: ${ltcg_realized:,.0f}, "
            f"LTCG ratio: {ltcg_realized/amount:.1%})"
        )
        
        return basis_returned, ltcg_realized
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get account summary for reporting.
        
        Returns:
            Dictionary with account metrics:
            - total_value: Current market value
            - total_basis: Total cost basis
            - total_gains: Total unrealized gains
            - ltcg_ratio: Gains as percentage of value
            - basis_ratio: Basis as percentage of value
            - num_lots: Number of transaction lots
            - oldest_lot_age: Age of oldest lot in years
            - avg_holding_period: Average holding period across all lots
        """
        return {
            'total_value': self.total_value,
            'total_basis': self.total_basis,
            'total_gains': self.total_gains,
            'ltcg_ratio': self.ltcg_ratio,
            'basis_ratio': self.basis_ratio,
            'num_lots': len(self.transactions),
            'oldest_lot_age': max((t.years_held for t in self.transactions), default=0),
            'avg_holding_period': (
                sum(t.years_held for t in self.transactions) / len(self.transactions)
                if self.transactions else 0
            )
        }


def initialize_brokerage_account(
    initial_balance: float,
    current_year: int,
    estimated_years_invested: int = 0,
    growth_rate: float = 1.07
) -> BrokerageAccount:
    """
    Initialize brokerage account with estimated cost basis.
    
    For existing portfolios, we estimate the cost basis by working backwards
    from current value using the growth rate. This provides a reasonable
    approximation until actual transaction history is available.
    
    Args:
        initial_balance: Current brokerage account value
        current_year: Current year in simulation
        estimated_years_invested: Approximate years the portfolio has been invested
                                 (0 = assume all basis, conservative)
        growth_rate: Annual growth multiplier (default: 1.07 for 7%)
    
    Returns:
        BrokerageAccount initialized with estimated cost basis
    
    Example:
        >>> # $200k portfolio, invested for 15 years at 7%
        >>> account = initialize_brokerage_account(200000, 2024, 15, 1.07)
        >>> # Estimated basis: $200k / (1.07^15) ≈ $72k
        >>> # Estimated gains: $200k - $72k = $128k (64% LTCG ratio)
    """
    account = BrokerageAccount()
    
    if initial_balance <= 0:
        return account
    
    # Estimate original cost basis by discounting current value
    # If portfolio grew at 7% for 10 years: basis = value / (1.07^10)
    if estimated_years_invested > 0:
        discount_factor = growth_rate ** estimated_years_invested
        estimated_basis = initial_balance / discount_factor
    else:
        # No history provided, assume all basis (conservative approach)
        # This means 0% gains, 100% basis - user can override if needed
        estimated_basis = initial_balance
    
    # Create initial transaction representing the existing portfolio
    account.add_transfer(
        year=current_year - estimated_years_invested,
        amount=estimated_basis,
        source="initial_portfolio"
    )
    
    # Grow it to current value over the estimated holding period
    for year_offset in range(estimated_years_invested):
        year = current_year - estimated_years_invested + year_offset + 1
        account.apply_annual_growth(growth_rate, year)
    
    summary = account.get_summary()
    logger.info(
        f"Initialized brokerage account:\n"
        f"  Current value: ${initial_balance:,.0f}\n"
        f"  Estimated basis: ${estimated_basis:,.0f}\n"
        f"  Estimated gains: ${initial_balance - estimated_basis:,.0f}\n"
        f"  LTCG ratio: {summary['ltcg_ratio']:.1%}\n"
        f"  Basis ratio: {summary['basis_ratio']:.1%}\n"
        f"  Years invested: {estimated_years_invested}"
    )
    
    return account


def calculate_ssi_benefits_dynamic(year: int, person_name: str, birth_year: int,
                                   claiming_age: int, fra_benefit: float,
                                   cola_rate: float = DEFAULT_COLA_RATE) -> float:
    """
    Calculate SSI benefits for a person in a given year using dynamic formula.
    
    Args:
        year: Current year
        person_name: Name of the person
        birth_year: Year of birth
        claiming_age: Age when benefits are claimed
        fra_benefit: Monthly benefit at Full Retirement Age (67)
        cola_rate: Annual COLA rate (default: 2%)
        
    Returns:
        Monthly SSI benefit amount for the year (0 if not yet claiming)
    """
    current_age = year - birth_year
    
    # Not yet claiming
    if current_age < claiming_age:
        return 0.0
    
    # Calculate initial benefit at claiming age
    initial_benefit = calculate_benefit_at_claiming_age(fra_benefit, claiming_age)
    
    # Apply COLA for years since claiming
    claiming_year = birth_year + claiming_age
    years_since_claiming = year - claiming_year
    
    monthly_benefit = calculate_benefit_with_cola(initial_benefit, years_since_claiming, cola_rate)
    
    logger.debug(f"SSI for {person_name} in {year}: Age {current_age}, "
                f"Claiming age {claiming_age}, Monthly benefit ${monthly_benefit:,.2f}")
    
    return monthly_benefit
def calculate_ss_taxable_amount(ss_benefits: float, agi_without_ss: float, 
                                filing_status: str = "married_filing_jointly") -> float:
    """
    Calculate the actual taxable portion of Social Security benefits.
    
    Uses the IRS formula for determining how much of SS benefits are taxable
    based on "combined income" (AGI + nontaxable interest + 50% of SS benefits).
    
    Args:
        ss_benefits: Annual Social Security benefits
        agi_without_ss: AGI excluding SS benefits (includes other income sources)
        filing_status: Tax filing status
        
    Returns:
        Taxable portion of SS benefits (0 to 85% of benefits)
        
    Reference: IRS Publication 915 - Social Security and Equivalent Railroad Retirement Benefits
    """
    if ss_benefits <= 0:
        return 0.0
    
    # Calculate combined income
    combined_income = agi_without_ss + (ss_benefits * 0.5)
    
    # Thresholds based on filing status
    if filing_status == "married_filing_jointly":
        threshold_1 = 32000  # 0% to 50% taxable range
        threshold_2 = 44000  # 50% to 85% taxable range
    else:  # single, head_of_household, married_filing_separately
        threshold_1 = 25000
        threshold_2 = 34000
    
    # Calculate taxable amount using IRS formula
    if combined_income <= threshold_1:
        # No SS benefits are taxable
        return 0.0
    elif combined_income <= threshold_2:
        # Up to 50% of benefits are taxable
        # Taxable = lesser of: (a) 50% of benefits, or (b) 50% of (combined income - threshold_1)
        taxable = min(
            ss_benefits * 0.5,
            (combined_income - threshold_1) * 0.5
        )
        return taxable
    else:
        # Up to 85% of benefits are taxable
        # Taxable = lesser of:
        #   (a) 85% of benefits, or
        #   (b) 85% of (combined income - threshold_2) + lesser of:
        #       - Amount from 50% calculation, or
        #       - $6,000 (MFJ) or $4,500 (Single)
        max_50_pct_amount = 6000 if filing_status == "married_filing_jointly" else 4500
        amount_from_50_pct = min(
            ss_benefits * 0.5,
            (threshold_2 - threshold_1) * 0.5
        )
        amount_from_50_pct = min(amount_from_50_pct, max_50_pct_amount)
        
        taxable = min(
            ss_benefits * 0.85,
            0.85 * (combined_income - threshold_2) + amount_from_50_pct
        )
        return taxable


def calculate_preretirement_healthcare_for_year(year: int, age_primary: int, age_spouse: int) -> float:
    """
    Calculate total pre-retirement (working) healthcare premium for a given year.
    
    This covers employer or private insurance while still working, before retirement.
    
    Args:
        year: Current year
        age_primary: Primary person's age
        age_spouse: Spouse's age
    
    Returns:
        Annual pre-retirement healthcare premium cost (sum of both people if applicable)
    """
    config_mgr = get_config_manager()
    
    # Get retirement ages
    person1_retirement_age = config_mgr.get("personal_info", "person1_retirement_age", 62)
    person2_retirement_age = config_mgr.get("personal_info", "person2_retirement_age", 62)
    
    # Get pre-retirement healthcare premiums
    person1_monthly_premium = config_mgr.get("healthcare", "person1_preretirement_insurance_monthly", 0)
    person2_monthly_premium = config_mgr.get("healthcare", "person2_preretirement_insurance_monthly", 0)
    
    total_annual_premium = 0.0
    
    # Person 1: pre-retirement healthcare applies if still working (before retirement age)
    if age_primary < person1_retirement_age and person1_monthly_premium > 0:
        total_annual_premium += person1_monthly_premium * 12
    
    # Person 2: pre-retirement healthcare applies if still working (before retirement age)
    if age_spouse > 0 and age_spouse < person2_retirement_age and person2_monthly_premium > 0:
        total_annual_premium += person2_monthly_premium * 12
    
    return total_annual_premium


def calculate_aca_premium_for_year(year: int, age_primary: int, age_spouse: int) -> float:
    """
    Calculate total ACA premium for a given year based on both people's ages and configuration.
    
    This covers ACA marketplace insurance after retirement but before Medicare eligibility.
    
    Args:
        year: Current year
        age_primary: Primary person's age
        age_spouse: Spouse's age
    
    Returns:
        Annual ACA premium cost (sum of both people if applicable)
    """
    config_mgr = get_config_manager()
    
    # Get person 1 ACA configuration
    person1_monthly_premium = config_mgr.get("healthcare", "person1_aca_insurance_monthly", 0)
    person1_aca_start_age = config_mgr.get("healthcare", "person1_aca_start_age", 62)
    person1_aca_end_age = config_mgr.get("healthcare", "person1_aca_end_age", 65)
    
    # Get person 2 ACA configuration
    person2_monthly_premium = config_mgr.get("healthcare", "person2_aca_insurance_monthly", 0)
    person2_aca_start_age = config_mgr.get("healthcare", "person2_aca_start_age", 62)
    person2_aca_end_age = config_mgr.get("healthcare", "person2_aca_end_age", 65)
    
    total_annual_premium = 0.0
    
    # Check if person 1 is in ACA coverage period (retired but not yet on Medicare)
    if person1_aca_start_age <= age_primary < person1_aca_end_age and person1_monthly_premium > 0:
        total_annual_premium += person1_monthly_premium * 12
    
    # Check if person 2 is in ACA coverage period (retired but not yet on Medicare)
    if person2_aca_start_age <= age_spouse < person2_aca_end_age and person2_monthly_premium > 0:
        total_annual_premium += person2_monthly_premium * 12
    
    return total_annual_premium


def calculate_cash_buffer_targets(expenses: float) -> Tuple[float, float]:
    """
    Calculate the target buffer amounts for Cash and Taxable accounts
    
    Args:
        expenses: Annual expenses
    
    Returns:
        Tuple of (cash_target, taxable_target)
        - cash_target: Full "Recommended Cash Reserve" (expenses * years_of_expenses_in_cash)
        - taxable_target: Buffer in Taxable (expenses * brokerage_rebalance_trigger_multiplier)
    """
    # Get years_of_expenses from session state or fall back to config
    from config import get_value_with_session_override
    years_of_expenses = float(get_value_with_session_override('financial_assumptions', 'years_of_expenses_in_cash', 'EXPENSE_MULTIPLIER', 4))
    
    # Get the brokerage buffer multiplier from config
    brokerage_multiplier = float(get_value_with_session_override(
        'financial_assumptions',
        'brokerage_rebalance_trigger_multiplier',
        'brokerage_rebalance_trigger_multiplier',
        1.0
    ))
    
    # Use the full "Recommended Cash Reserve" value from configuration page
    # This matches: expected_annual_expenses * years_of_expenses_in_cash
    cash_target = expenses * years_of_expenses
    
    # Taxable buffer based on configured multiplier (default 1 year of expenses)
    taxable_target = expenses * brokerage_multiplier
    
    return cash_target, taxable_target


def calculate_cash_buffer_targets_accumulation(wages: float) -> float:
    """
    Calculate the target cash buffer for the accumulation phase.

    During working years the cash target is expressed as a number of months of
    gross wages rather than years of expenses.  The default is 6 months; the
    user can adjust this between 3 and 24 months via the Configuration page.

    Args:
        wages: Annual gross wages (person1 + person2 combined)

    Returns:
        cash_target: Target cash balance (wages * months / 12)
    """
    from config import get_config_manager
    try:
        config_mgr = get_config_manager()
        months = float(config_mgr.get(
            'financial_assumptions', 'accumulation_cash_buffer_months', 6
        ))
    except Exception:
        months = 6.0

    # Clamp to the allowed UI range just in case the stored value is out of bounds
    months = max(3.0, min(24.0, months))
    return wages * months / 12.0

def calculate_stage2_cash_target(wages: float, expenses: float,
                                  years_to_retirement: int,
                                  prep_window: int = 10) -> float:
    """
    Calculate the linearly-ramped cash buffer target for Stage 2 (Prep for Retirement).

    At the *start* of Stage 2 (``years_to_retirement == prep_window``) the target
    equals the wages-based accumulation buffer (same as Stage 1).  By the *end* of
    Stage 2 (``years_to_retirement == 1``) the target has ramped up to **75 %** of
    the full retirement cash reserve (``expenses × years_of_expenses_in_cash``).

    Linear interpolation formula::

        progress = (prep_window - years_to_retirement) / (prep_window - 1)
        target   = accum_target + progress * (0.75 * retirement_target - accum_target)

    Args:
        wages:               Annual gross wages (combined).
        expenses:            Annual living expenses.
        years_to_retirement: Years remaining until the earlier retirement date.
        prep_window:         Number of years that Stage 2 spans (default 10).

    Returns:
        cash_target: Interpolated cash buffer target for the current year.
    """
    accum_target = calculate_cash_buffer_targets_accumulation(wages)
    retirement_cash_target, _ = calculate_cash_buffer_targets(expenses)
    end_target = 0.75 * retirement_cash_target

    # Clamp years_to_retirement to the valid window [1, prep_window]
    years_to_retirement = max(1, min(prep_window, years_to_retirement))

    # progress: 0.0 at the start of Stage 2, 1.0 in the final year
    progress = (prep_window - years_to_retirement) / max(1, prep_window - 1)
    return accum_target + progress * (end_target - accum_target)


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
    available_rates = pd.unique(tax_brackets[tax_brackets['rate'] <= max_rate]['rate'])
    available_rates = sorted(available_rates, reverse=True)  # Highest first
    
    # Remove 0% bracket (not useful for conversions)
    available_rates = [r for r in available_rates if r > 0]
    
    if not available_rates:
        raise ValueError(f"No suitable tax brackets found up to {max_rate:.2%}")
    
    # Try each rate from highest to lowest until we find one that exists
    for rate in available_rates:
        try:
            upper_limit = float(getUpperIncomeRate(rate, tax_brackets))
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
    rmd_years = [s for s in strategies if s.stage == "Stage 6: RMD"]
    
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
        "Stage 2: Prep for Retirement",
        "Stage 3: Early Retirement",
        "Stage 4: Medicare",
        "Stage 5: Social Security"
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
        if year_strategy.stage in ["Stage 2: Prep for Retirement",
                                   "Stage 3: Early Retirement",
                                   "Stage 4: Medicare",
                                   "Stage 5: Social Security"]:
            # Calculate maximum additional conversion (limit to 15% of Traditional balance)
            max_additional_conversion = min(
                additional_conversion_per_year,
                year_strategy.balances.traditional * 0.15
            )
            
            if max_additional_conversion > 1000:  # Only adjust if meaningful amount
                # Verify with BETR that additional conversion is beneficial
                try:
                    betr_inputs = BETRInputs(
                        current_marginal_rate=0.24,  # Assume 24% bracket
                        expected_future_rate=0.24,   # Assume same in RMD years
                        conversion_amount=year_strategy.roth_conversion + max_additional_conversion,
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
                        
                        # Validate that we have sufficient traditional balance BEFORE modifying conversion
                        if year_strategy.balances.traditional < max_additional_conversion:
                            logger.warning(f"Year {year_strategy.year}: Insufficient traditional balance "
                                         f"(${year_strategy.balances.traditional:,.2f}) for additional conversion "
                                         f"(${max_additional_conversion:,.2f}). Skipping adjustment.")
                            continue
                        
                        # Increase conversion
                        old_conversion = year_strategy.roth_conversion
                        year_strategy.roth_conversion += max_additional_conversion
                        
                        # CRITICAL: Recalculate balances to reflect the increased conversion
                        # The additional conversion reduces Traditional and increases Roth
                        year_strategy.balances = PortfolioBalances(
                            cash=year_strategy.balances.cash,
                            taxable=year_strategy.balances.taxable,
                            traditional=year_strategy.balances.traditional - max_additional_conversion,
                            roth=year_strategy.balances.roth + max_additional_conversion,
                            daf=year_strategy.balances.daf
                        )
                        
                        # CRITICAL: Recalculate AGI, MAGI, and taxes with the new conversion amount
                        # AGI includes the Roth conversion, so it must be updated
                        year_strategy.agi += max_additional_conversion
                        year_strategy.magi += max_additional_conversion
                        
                        # Recalculate federal tax with new AGI
                        # Get tax data for this year
                        try:
                            config_mgr = get_config_manager()
                            filing_status = config_mgr.get_filing_status()
                            tax_brackets = get_income_tax_brackets(year_strategy.year)
                            std_deduction_df = get_std_deduction(year_strategy.year, filing_status)
                            std_deduction = std_deduction_df.iloc[0]['deduction']
                            cg_brackets = pd.DataFrame(get_cap_gains_brackets(year_strategy.year))
                            
                            # CRITICAL: Account for DAF deduction if present
                            # DAF contribution creates additional itemized deduction above standard deduction
                            daf_tax_excess = 0
                            if year_strategy.daf_contribution > 0:
                                # Get property tax for SALT calculation
                                try:
                                    property_tax = float(config_mgr.get("expenses", "living_expenses", {}).get("property_tax", 0))
                                except Exception:
                                    property_tax = 0.0
                                
                                # Calculate SALT cap (state tax + property tax, capped at $10,000)
                                salt_deduction = min(year_strategy.state_tax + property_tax, 10000)
                                
                                # Total itemized deductions = SALT + DAF contribution
                                itemized_deduction = salt_deduction + year_strategy.daf_contribution
                                
                                # DAF tax excess = amount by which itemized exceeds standard
                                daf_tax_excess = max(0, itemized_deduction - std_deduction)
                            
                            effective_deduction = std_deduction + daf_tax_excess
                            
                            # Recalculate federal tax - MUST separate ordinary income from LTCG
                            taxable_income = year_strategy.agi - effective_deduction
                            
                            # CRITICAL: Ordinary income excludes LTCG (which is taxed separately)
                            ordinary_income = taxable_income - year_strategy.ltcg_harvested
                            result = calculate_taxable_income(ordinary_income, tax_brackets)
                            federal_tax = result.total_tax
                            
                            # Recalculate capital gains tax (use ordinary income as base for LTCG brackets)
                            cg_tax = calculate_cap_gains(
                                ordinary_income,
                                cg_brackets,
                                year_strategy.ltcg_harvested
                            )
                            year_strategy.federal_tax = federal_tax + cg_tax
                            
                            # Recalculate state tax with new AGI
                            # Get state from config
                            try:
                                state = config_mgr.get('personal_info', 'retirement_state', 'FL')
                            except (KeyError, AttributeError):
                                state = 'FL'
                            
                            # CRITICAL: Use the UPDATED conversion amount for retirement_income
                            # The year_strategy.roth_conversion has already been increased by max_additional_conversion
                            total_retirement_income = year_strategy.traditional_withdrawal + year_strategy.roth_conversion
                            
                            # CRITICAL: Calculate the taxable SS portion that's actually in the AGI
                            # AGI = retirement_income + taxable_ss + ltcg
                            # Therefore: taxable_ss = AGI - retirement_income - ltcg
                            #
                            # We MUST pass only the taxable SS portion to calculate_state_tax, not the full SS benefits.
                            # Otherwise, states like PA will try to exempt more than what's in the AGI, causing
                            # negative taxable income.
                            taxable_ss_in_agi = year_strategy.agi - total_retirement_income - year_strategy.ltcg_harvested
                            
                            # Ensure it's not negative (shouldn't happen, but safety check)
                            taxable_ss_in_agi = max(0, taxable_ss_in_agi)
                            
                            logger.info(f"  State tax inputs: AGI=${year_strategy.agi:,.0f}, "
                                      f"retirement_income=${total_retirement_income:,.0f}, "
                                      f"taxable_ss_in_agi=${taxable_ss_in_agi:,.0f}, "
                                      f"full_ss_benefits=${year_strategy.ss_benefits:,.0f}, "
                                      f"ltcg_harvested=${year_strategy.ltcg_harvested:,.0f}")
                            logger.info(f"  Expected state taxable after exemptions: "
                                      f"${year_strategy.agi - total_retirement_income - taxable_ss_in_agi:,.0f} "
                                      f"(should equal ltcg_harvested)")
                            
                            state_tax, state_details = calculate_state_tax(
                                state_agi=year_strategy.agi,
                                state=state,
                                year=year_strategy.year,
                                filing_status=filing_status,
                                retirement_income=total_retirement_income,
                                ss_benefits=taxable_ss_in_agi  # Pass only the taxable portion in AGI
                            )
                            year_strategy.state_tax = state_tax
                            
                            logger.info(f"  State tax result: taxable_income=${state_details.get('taxable_income', 0):,.0f}, "
                                      f"state_tax=${state_tax:,.0f}")
                            
                            logger.info(f"  Tax recalculation: AGI increased by ${max_additional_conversion:,.2f}")
                            logger.info(f"  New AGI: ${year_strategy.agi:,.2f}, New Federal Tax: ${year_strategy.federal_tax:,.2f}, New State Tax: ${year_strategy.state_tax:,.2f}")
                        except Exception as e:
                            logger.warning(f"  Could not recalculate taxes after optimization: {e}")
                        
                        total_additional_conversions += max_additional_conversion
                        years_adjusted += 1
                        
                        # Update conversion_executed to match roth_conversion for display consistency
                        year_strategy.conversion_executed = year_strategy.roth_conversion
                        
                        # Log balances after adjustment
                        logger.info(f"  After optimization adjustment:")
                        logger.info(f"  Traditional: ${year_strategy.balances.traditional:,.2f} (reduced by ${max_additional_conversion:,.2f})")
                        logger.info(f"  Roth: ${year_strategy.balances.roth:,.2f} (increased by ${max_additional_conversion:,.2f})")
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
    avg_additional_per_adjusted_year = total_additional_conversions / years_adjusted if years_adjusted > 0 else None
    
    optimization_report = {
        "status": "Optimization complete",
        "avg_rmd_excess": avg_rmd_excess,
        "rmd_years_analyzed": rmd_count,
        "pre_rmd_years_available": years_available,
        "years_adjusted": years_adjusted,
        "additional_conversion_per_year_target": additional_conversion_per_year,
        "total_additional_conversions": total_additional_conversions,
        "estimated_rmd_reduction": estimated_rmd_reduction,
        "avg_additional_per_adjusted_year": avg_additional_per_adjusted_year if years_adjusted > 0 else "N/A - no years adjusted"
    }
    
    logger.info(f"RMD Optimization Complete:")
    logger.info(f"  - Adjusted {years_adjusted} years")
    logger.info(f"  - Total additional conversions: ${total_additional_conversions:,.0f}")
    logger.info(f"  - Estimated RMD reduction: ${estimated_rmd_reduction:,.0f}")
    
    return adjusted_strategies, optimization_report


# State Unemployment Tax Act (SUTA) rates and taxable wage bases by state (2024 estimates).
# Format: state_code -> (employee_rate, wage_base)
# Sources: DOL state UI tax tables; rates shown are new-employer / average rates.
_SUTA_BY_STATE: Dict[str, Tuple[float, float]] = {
    'AL': (0.0270, 8_000),
    'AK': (0.0100, 49_700),
    'AZ': (0.0200, 8_000),
    'AR': (0.0310, 10_000),
    'CA': (0.0340, 7_000),
    'CO': (0.0170, 23_800),
    'CT': (0.0290, 25_000),
    'DE': (0.0180, 10_500),
    'FL': (0.0270, 7_000),
    'GA': (0.0270, 9_500),
    'HI': (0.0240, 59_100),
    'ID': (0.0207, 53_500),
    'IL': (0.0350, 13_590),
    'IN': (0.0250, 9_500),
    'IA': (0.0100, 38_200),
    'KS': (0.0270, 14_000),
    'KY': (0.0270, 11_100),
    'LA': (0.0270, 7_700),
    'ME': (0.0220, 12_000),
    'MD': (0.0270, 8_500),
    'MA': (0.0290, 15_000),
    'MI': (0.0270, 9_500),
    'MN': (0.0100, 42_000),
    'MS': (0.0100, 14_000),
    'MO': (0.0270, 10_500),
    'MT': (0.0100, 43_000),
    'NE': (0.0125, 9_000),
    'NV': (0.0295, 40_600),
    'NH': (0.0270, 14_000),
    'NJ': (0.0028, 42_300),
    'NM': (0.0100, 31_700),
    'NY': (0.0290, 12_500),
    'NC': (0.0120, 31_400),
    'ND': (0.0100, 43_800),
    'OH': (0.0270, 9_000),
    'OK': (0.0270, 25_700),
    'OR': (0.0270, 52_800),
    'PA': (0.0370, 10_000),
    'RI': (0.0099, 29_200),
    'SC': (0.0270, 14_000),
    'SD': (0.0120, 15_000),
    'TN': (0.0270, 7_000),
    'TX': (0.0270, 9_000),
    'UT': (0.0100, 47_000),
    'VT': (0.0100, 14_300),
    'VA': (0.0270, 8_000),
    'WA': (0.0100, 72_800),
    'WV': (0.0270, 9_000),
    'WI': (0.0350, 14_000),
    'WY': (0.0270, 29_100),
    'DC': (0.0270, 9_000),
}


def calculate_payroll_taxes(wages: float, year: int = 2024) -> Tuple[float, Dict]:
    """
    Calculate payroll taxes on wage income: FICA (Social Security), Medicare,
    state income tax, and unemployment insurance (FUTA/SUTA).

    SUTA rate and wage base are looked up by the state configured in personal_info.
    These are deducted from gross wages before any savings or investment decisions.

    Args:
        wages: Gross annual wages
        year:  Tax year (used for wage-base inflation; base year 2024)

    Returns:
        Tuple of (total_payroll_tax, breakdown_dict)
    """
    if wages <= 0:
        return 0.0, {}

    # ── Resolve state from config ─────────────────────────────────────────────
    try:
        _cfg = get_config_manager()
        state = (_cfg.get('personal_info', 'retirement_state', 'FL') or 'FL').upper()
    except Exception:
        state = 'FL'

    # ── Social Security (OASDI) ────────────────────────────────────────────────
    # Look up the wage base from fica_limits.csv; fall back to projecting from
    # the most recent CSV row when the year isn't covered yet.
    _fica_df = get_fica_limits(year)
    if not _fica_df.empty:
        ss_wage_base     = float(_fica_df['ss_wage_base'].iloc[0])
        _ss_rate         = float(_fica_df['ss_employee_rate'].iloc[0])
        _cola_rate       = float(_fica_df['cola_rate_estimate'].iloc[0])
    else:
        # Year beyond CSV range: project from last known row
        import pandas as _pd
        _all = _pd.read_csv('fica_limits.csv')
        _last = _all.iloc[-1]
        _base_year       = int(_last['year'])
        _cola_rate       = float(_last['cola_rate_estimate'])
        ss_wage_base     = float(_last['ss_wage_base']) * (
            (1 + _cola_rate) ** max(0, year - _base_year)
        )
        _ss_rate         = float(_last['ss_employee_rate'])
    ss_tax = min(wages, ss_wage_base) * _ss_rate

    # ── Medicare ──────────────────────────────────────────────────────────────
    # 1.45 % on all wages; additional 0.9 % on wages > $250k (MFJ)
    medicare_tax = wages * 0.0145
    additional_medicare_threshold = 250_000
    if wages > additional_medicare_threshold:
        medicare_tax += (wages - additional_medicare_threshold) * 0.009

    # ── State income tax on wages ─────────────────────────────────────────────
    state_tax, _ = calculate_state_tax(state_agi=wages, year=year, state=state)

    # ── FUTA ──────────────────────────────────────────────────────────────────
    # Federal Unemployment Tax Act: 0.6 % on first $7,000 (net of SUTA credit)
    futa_wage_base = 7_000
    futa_tax = min(wages, futa_wage_base) * 0.006

    # ── SUTA (state unemployment insurance) ───────────────────────────────────
    # Rate and wage base vary by state; fall back to national average if unknown.
    suta_rate, suta_wage_base = _SUTA_BY_STATE.get(state, (0.027, 7_000))
    suta_tax = min(wages, suta_wage_base) * suta_rate
    logger.debug(f"SUTA ({state}): rate={suta_rate:.2%}, wage_base=${suta_wage_base:,}, tax=${suta_tax:,.0f}")

    total = ss_tax + medicare_tax + state_tax + futa_tax + suta_tax

    breakdown = {
        'state':               state,
        'social_security_tax': ss_tax,
        'medicare_tax':        medicare_tax,
        'state_tax':           state_tax,
        'futa_tax':            futa_tax,
        'suta_rate':           suta_rate,
        'suta_wage_base':      suta_wage_base,
        'suta_tax':            suta_tax,
        'total_payroll_tax':   total,
    }
    logger.info(
        f"Payroll taxes ({state}) on ${wages:,.0f} wages: SS=${ss_tax:,.0f}, "
        f"Medicare=${medicare_tax:,.0f}, State=${state_tax:,.0f}, "
        f"FUTA=${futa_tax:,.0f}, SUTA={suta_rate:.2%}×${suta_wage_base:,}=${suta_tax:,.0f}"
        f"  →  Total=${total:,.0f}"
    )
    return total, breakdown


def calculate_state_tax(state_agi: float, state: Optional[str] = None, year: int = 2024,
                       filing_status: str = "married_filing_jointly",
                       retirement_income: float = 0,
                       ss_benefits: float = 0,
                       roth_conversion: float = 0) -> Tuple[float, Dict]:
    """
    Calculate state income tax with retirement exemptions
    
    Args:
        state_agi: State Adjusted Gross Income (includes all income sources)
        state: Two-letter state code (e.g., "CA", "NY", "FL"). If None, uses config value.
        year: Tax year
        filing_status: Filing status
        retirement_income: Traditional IRA/401k distributions for exemption calculation
        ss_benefits: Social Security benefits (full amount, not just taxable portion)
        roth_conversion: Roth conversion amount (exempt in retirement-friendly states)
    
    Returns:
        Tuple of (state_tax, calculation_details)
        
    Implementation Notes:
        - No-tax states: Return 0
        - Retirement-friendly states (PA, IL, MS): Exempt retirement income, SS, and Roth conversions
        - The remaining taxable income (typically LTCG from brokerage) is taxed
        - High-tax states: Apply progressive brackets to full AGI
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
        # Exempt Traditional IRA/401k withdrawals
        exemption = min(retirement_income, RETIREMENT_EXEMPT_STATES[state])
        adjusted_agi -= exemption
        exemption_applied += exemption
        logger.debug(f"{state}: Applied retirement income exemption: ${exemption:,.0f}")
        
        # Also exempt Roth conversions (they're retirement income too)
        roth_exemption = min(roth_conversion, RETIREMENT_EXEMPT_STATES[state])
        adjusted_agi -= roth_exemption
        exemption_applied += roth_exemption
        logger.debug(f"{state}: Applied Roth conversion exemption: ${roth_exemption:,.0f}")
    
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
        'MA': [(0, float('inf'), 0.05)],    # Flat 5%
        'CO': [(0, float('inf'), 0.044)],   # Flat 4.4%
        'NC': [(0, float('inf'), 0.0475)],  # Flat 4.75%
        'PA': [(0, float('inf'), 0.0307)],  # Flat 3.07%
        'IL': [(0, float('inf'), 0.0495)],  # Flat 4.95%
        'MS': [(0, 10000, 0.0), (10000, float('inf'), 0.05)],  # 0% up to $10k, 5% above
    }
    
    # Standard deductions by state (simplified)
    STANDARD_DEDUCTIONS = {
        'CA': 10404, 'NY': 16050, 'NJ': 0, 'MA': 0, 'CO': 0, 'NC': 25500
    }
    
    # Apply standard deduction
    std_deduction = STANDARD_DEDUCTIONS.get(state or '', 0)
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
        _tax_brackets = get_income_tax_brackets(year)
        result = calculate_taxable_income(
            income + conversions - deductions,
            pd.DataFrame(_tax_brackets)
        )
        regular_tax = result.total_tax
    except (ValueError, TypeError, KeyError) as e:
        # Fallback to simple calculation
        logging.warning(f"calculate_taxable_income failed, using fallback: {e}")
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


# Named tuple for the resolved IRMAA bracket values — avoids positional confusion
# when _resolve_irmaa returns four floats to its caller.
from typing import NamedTuple

class _IrmaaResolved(NamedTuple):
    """All per-bracket Medicare cost components resolved in a single CSV scan."""
    annual_irmaa_penalty: float   # Part B IRMAA penalty × 12 (per eligible person)
    part_b_monthly: float         # All-in monthly Part B premium (base + surcharge)
    part_a_monthly: float         # Monthly Part A premium (0 for premium-free Part A)
    part_d_monthly_total: float   # Part D base + IRMAA surcharge, monthly


# Sentinel returned by _resolve_irmaa when no IRMAA bracket matches (e.g. the
# CSV is unavailable or the year is out of range).  Centralising the fallback
# values here eliminates the duplicate _IrmaaResolved(...) literal that
# previously appeared in both _resolve_irmaa and calculate_medicare_costs.
_STANDARD_IRMAA_RESOLVED = _IrmaaResolved(
    annual_irmaa_penalty=0.0,
    part_b_monthly=PART_B_MONTHLY_STANDARD_PREMIUM,
    part_a_monthly=0.0,
    part_d_monthly_total=PART_D_ANNUAL_BASE_PREMIUM / 12,
)


def _resolve_irmaa(
    magi: float,
    irmaa_bracket_df: pd.DataFrame,
) -> _IrmaaResolved:
    """Return all per-bracket Medicare cost components in a single CSV scan.

    ``irmaa.csv`` is the single source of truth for Part A, Part B, and Part D
    costs.  Each row carries:

    * ``part_b_monthly``      — all-in monthly Part B premium (base + IRMAA surcharge)
    * ``part_a_monthly``      — monthly Part A premium (0 for premium-free Part A)
    * ``part_d_base_monthly`` — CMS national base Part D beneficiary premium
    * ``part_d_irmaa_monthly``— income-tiered Part D IRMAA surcharge

    A single loop finds the matched bracket and extracts all four values at once,
    replacing the previous two-pass pattern (``calculate_irmma_penalty`` + a
    second ``.loc[]`` scan).

    ``annual_irmaa_penalty`` is returned as a **per-person** value (``part_b *
    12``).  The caller is responsible for multiplying by the number of
    Medicare-eligible persons so that mixed-age couples (one person on Medicare,
    one not yet eligible) are handled correctly.

    Args:
        magi: MAGI used for IRMAA bracket matching (2-year lookback value).
        irmaa_bracket_df: DataFrame with columns ``lower``, ``upper``,
            ``part_b_monthly``, ``part_a_monthly``, ``part_d_base_monthly``,
            ``part_d_irmaa_monthly`` as returned by :func:`get_medicare_costs`.

    Returns:
        :class:`_IrmaaResolved` namedtuple.  Falls back to
        :data:`_STANDARD_IRMAA_RESOLVED` when no bracket matches.
    """
    cols = ['lower', 'upper', 'part_b_monthly', 'part_a_monthly',
            'part_d_base_monthly', 'part_d_irmaa_monthly']
    for lower, upper, part_b, part_a, part_d_base, part_d_irmaa in irmaa_bracket_df[cols].values:
        if lower <= magi <= upper:
            annual_penalty = max(0.0, (float(part_b) - PART_B_MONTHLY_STANDARD_PREMIUM) * 12)   # per-person; caller multiplies by eligible count
            part_d_total   = float(part_d_base) + float(part_d_irmaa)
            return _IrmaaResolved(
                annual_irmaa_penalty=annual_penalty,
                part_b_monthly=float(part_b),
                part_a_monthly=float(part_a),
                part_d_monthly_total=part_d_total,
            )
    # Fallback: no bracket matched — use statutory standard premiums
    return _STANDARD_IRMAA_RESOLVED


def _medicare_costs_for_person(
    age: int,
    label: str,
    part_b_monthly: float,
    part_a_monthly: float,
    part_d_monthly_total: float,
    has_medigap: bool,
) -> Tuple[Dict[str, float], float]:
    """Return (breakdown_slice, subtotal) for one Medicare-eligible person.

    All premium inputs come from the matched ``irmaa.csv`` bracket row via
    :func:`_resolve_irmaa`, making ``irmaa.csv`` the single source of truth for
    Part A, Part B, and Part D costs.

    Args:
        age: Person's current age.
        label: Key suffix used in the breakdown dict — ``"primary"`` or ``"spouse"``.
        part_b_monthly: All-in monthly Part B premium (base + IRMAA surcharge).
        part_a_monthly: Monthly Part A premium (0 for premium-free Part A).
        part_d_monthly_total: Monthly Part D cost (base + IRMAA surcharge).
        has_medigap: Whether the person carries Medigap supplemental coverage.

    Returns:
        Tuple of (breakdown_slice, subtotal) where breakdown_slice contains the
        four cost components keyed by label, and subtotal is their sum.
        Returns ({}, 0.0) when the person is not yet Medicare-eligible.
    """
    if age < MEDICARE_ELIGIBILITY_AGE:
        return {}, 0.0

    part_a   = part_a_monthly * 12
    part_b   = part_b_monthly * 12
    part_d   = part_d_monthly_total * 12
    medigap  = MEDIGAP_ANNUAL_PREMIUM if has_medigap else 0.0
    subtotal = part_a + part_b + part_d + medigap

    return {
        f'part_a_{label}':  part_a,
        f'part_b_{label}':  part_b,
        f'part_d_{label}':  part_d,
        f'medigap_{label}': medigap,
    }, subtotal


def calculate_medicare_costs(age_primary: int,
                            age_spouse: int,
                            magi_two_years_ago: float,
                            year: int,
                            filing_status: str = "married_filing_jointly",
                            has_medigap: bool = True) -> Tuple[float, "MedicareBreakdown"]:
    """
    Calculate total Medicare costs including IRMAA.

    Uses :func:`get_medicare_costs` (from ``load_data``) to load the IRMAA
    bracket table and :func:`_resolve_irmaa` for a single-pass surcharge and
    premium lookup.  Per-person cost assembly is delegated to the private helper
    :func:`_medicare_costs_for_person`.

    Args:
        age_primary: Primary person age.
        age_spouse: Spouse age.
        magi_two_years_ago: MAGI from 2 years prior for IRMAA (2-year lookback).
        year: Current year.
        filing_status: Filing status (``"married_filing_jointly"`` or ``"single"``).
        has_medigap: Whether they carry Medigap supplemental coverage.

    Returns:
        Tuple of (total_medicare_cost, cost_breakdown).
    """
    logger.debug(f"Calculating Medicare costs for year {year}, ages {age_primary}/{age_spouse}")

    # --- Load IRMAA bracket table (I/O — isolated in its own try/except) ------
    try:
        irmaa_bracket_df = get_medicare_costs(year - 2)
    except Exception as e:
        logger.warning(f"IRMAA bracket load failed: {e}, using standard premium")
        irmaa_bracket_df = None

    # --- Single-pass bracket scan: all Part A/B/D costs from irmaa.csv --------
    # _resolve_irmaa returns a per-person annual_irmaa_penalty; we multiply by
    # the actual number of Medicare-eligible persons below (after the helper
    # calls) so that mixed-age couples are handled correctly.
    if isinstance(irmaa_bracket_df, pd.DataFrame):
        resolved = _resolve_irmaa(magi_two_years_ago, irmaa_bracket_df)
    else:
        resolved = _STANDARD_IRMAA_RESOLVED

    # --- Compute per-person costs via the shared helper -----------------------
    primary_slice, primary_subtotal = _medicare_costs_for_person(
        age_primary, "primary",
        resolved.part_b_monthly, resolved.part_a_monthly,
        resolved.part_d_monthly_total, has_medigap,
    )
    spouse_slice, spouse_subtotal = _medicare_costs_for_person(
        age_spouse, "spouse",
        resolved.part_b_monthly, resolved.part_a_monthly,
        resolved.part_d_monthly_total, has_medigap,
    )

    total_cost = primary_subtotal + spouse_subtotal

    # Multiply the per-person IRMAA penalty by the number of persons who are
    # actually on Medicare (primary_subtotal > 0 means that person is eligible).
    # This fixes the previous over-count for mixed-age couples where only one
    # person is 65+ but filing_status is "married_filing_jointly".
    medicare_eligible_count = int(primary_subtotal > 0) + int(spouse_subtotal > 0)
    irmaa_penalty = resolved.annual_irmaa_penalty * medicare_eligible_count

    # --- Assemble the full breakdown dict -------------------------------------
    # _EMPTY_MEDICARE_BREAKDOWN zero-initialises all per-person keys so that
    # ineligible persons (age < 65, whose slice is {}) are represented as 0.0
    # rather than missing entirely.  Dict-unpack (**primary_slice, **spouse_slice)
    # overwrites the zeros for eligible persons.
    # cast() is required because TypedDict cannot be assigned from a plain dict
    # literal that contains **-unpacked entries (basedpyright limitation).
    _breakdown: MedicareBreakdown = cast("MedicareBreakdown", {
        **_EMPTY_MEDICARE_BREAKDOWN,
        **primary_slice,
        **spouse_slice,
        'irmaa_penalty':       irmaa_penalty,
        'total_medicare_cost': total_cost,
    })

    logger.info(f"Year {year}: Medicare costs = ${total_cost:,.0f} "
                f"(IRMAA penalty: ${irmaa_penalty:,.0f})")

    return total_cost, _breakdown


@dataclass(frozen=True)
class _AgeStatus:
    """Medicare/pre-Medicare eligibility status for both persons.

    Computed once by :func:`_classify_ages` and consumed by
    :func:`calculate_total_healthcare_costs` to eliminate repeated age
    comparisons and the inconsistent ``age_spouse > 0`` idiom.
    """
    primary_on_medicare: bool
    spouse_on_medicare: bool
    primary_pre_medicare: bool
    spouse_pre_medicare: bool
    medicare_count: int       # 0, 1, or 2 — persons on Medicare
    pre_medicare_count: int   # 0, 1, or 2 — persons not yet on Medicare
    total_persons: int        # 1 (no spouse) or 2


class MedicareBreakdown(TypedDict, total=False):
    """Typed mapping of Medicare cost components returned by :func:`calculate_medicare_costs`.

    Using ``TypedDict`` (rather than a plain ``Dict`` or a nested dataclass)
    keeps the existing :func:`calculate_medicare_costs` return type unchanged at
    runtime while giving callers and type-checkers a precise, documented
    contract for every key.  ``total=False`` marks all keys as optional so that
    the empty-dict default on :class:`HealthcareCostBreakdown` is also valid.

    All premium values originate from ``irmaa.csv`` via :func:`_resolve_irmaa`,
    making that file the single source of truth for Part A, Part B, and Part D
    costs including income-related IRMAA surcharges.

    Keys
    ----
    part_a_primary, part_a_spouse   : Part A annual premiums per person.
    part_b_primary, part_b_spouse   : Part B annual premiums per person.
    part_d_primary, part_d_spouse   : Part D annual premiums per person (base + IRMAA).
    medigap_primary, medigap_spouse : Medigap annual premiums per person.
    irmaa_penalty                   : Total Part B IRMAA surcharge for the year.
    total_medicare_cost             : Sum of all Medicare components.
    """
    part_a_primary: float
    part_a_spouse: float
    part_b_primary: float
    part_b_spouse: float
    part_d_primary: float
    part_d_spouse: float
    medigap_primary: float
    medigap_spouse: float
    irmaa_penalty: float
    total_medicare_cost: float




# Module-level sentinel used as the default value for medicare_detail when no
# Medicare-eligible person is present.  All ten keys are zero-initialised so
# that callers can safely iterate the breakdown without checking for missing keys.
# Defined here — after MedicareBreakdown — so both calculate_medicare_costs and
# calculate_total_healthcare_costs can reference it.
# cast() is required because TypedDict cannot be assigned from a plain dict literal
# (basedpyright limitation).
_EMPTY_MEDICARE_BREAKDOWN: MedicareBreakdown = cast("MedicareBreakdown", {
    'part_a_primary':      0.0,
    'part_a_spouse':       0.0,
    'part_b_primary':      0.0,
    'part_b_spouse':       0.0,
    'part_d_primary':      0.0,
    'part_d_spouse':       0.0,
    'medigap_primary':     0.0,
    'medigap_spouse':      0.0,
    'irmaa_penalty':       0.0,
    'total_medicare_cost': 0.0,
})


def _classify_ages(age_primary: int, age_spouse: int) -> _AgeStatus:
    """Return Medicare/pre-Medicare eligibility status for both persons.

    Args:
        age_primary: Primary person's age (must be > 0).
        age_spouse:  Spouse's age; pass 0 to indicate no spouse.

    Returns:
        Frozen :class:`_AgeStatus` instance capturing all derived booleans
        and person counts needed by :func:`calculate_total_healthcare_costs`.

    Raises:
        ValueError: If ``age_primary`` is not a positive integer.
    """
    if age_primary <= 0:
        raise ValueError(
            f"age_primary must be a positive integer, got {age_primary!r}"
        )
    has_spouse = age_spouse > 0
    p_med = age_primary >= MEDICARE_ELIGIBILITY_AGE
    s_med = has_spouse and age_spouse >= MEDICARE_ELIGIBILITY_AGE
    return _AgeStatus(
        primary_on_medicare=p_med,
        spouse_on_medicare=s_med,
        primary_pre_medicare=not p_med,
        spouse_pre_medicare=has_spouse and not s_med,
        medicare_count=int(p_med) + int(s_med),
        pre_medicare_count=int(not p_med) + int(has_spouse and not s_med),
        total_persons=1 + int(has_spouse),
    )


@dataclass(frozen=True)
class HealthcareCostBreakdown:
    """Itemised healthcare costs returned by :func:`calculate_total_healthcare_costs`.

    Using a frozen dataclass instead of a plain ``dict`` provides:
    - Attribute-style access with IDE auto-complete and type checking.
    - A computed :attr:`total` property that is always consistent with the
      individual fields (no separately maintained ``total_healthcare_cost`` key).
    - An auto-generated ``__repr__`` useful for logging and debugging.
    - Immutability — callers cannot accidentally mutate the breakdown.
    """
    medicare: float = 0.0
    pre_medicare: float = 0.0
    preretirement_working: float = 0.0
    out_of_pocket: float = 0.0
    ltc_insurance: float = 0.0
    medicare_detail: MedicareBreakdown = field(default_factory=lambda: _EMPTY_MEDICARE_BREAKDOWN)

    @property
    def total(self) -> float:
        """Sum of all cost components."""
        return self.medicare + self.pre_medicare + self.preretirement_working + self.out_of_pocket + self.ltc_insurance


def _calculate_medicare(
    status: _AgeStatus,
    age_primary: int,
    age_spouse: int,
    magi_two_years_ago: float,
    year: int,
    filing_status: str,
    has_medigap: bool,
) -> Tuple[float, MedicareBreakdown]:
    """Return ``(cost, detail)`` for Medicare-eligible persons; ``(0.0, empty)`` otherwise.

    Centralises the ``medicare_count`` guard and the ``_EMPTY_MEDICARE_BREAKDOWN``
    sentinel so that :func:`calculate_total_healthcare_costs` does not need to
    manage mutable initialisation before a conditional call.

    Args:
        status:             Pre-computed eligibility flags from :func:`_classify_ages`.
        age_primary:        Primary person's age.
        age_spouse:         Spouse's age; 0 means no spouse.
        magi_two_years_ago: MAGI from 2 years prior (used for IRMAA).
        year:               Current year.
        filing_status:      Filing status string (e.g. ``"married_filing_jointly"``).
        has_medigap:        Whether they carry Medigap coverage.

    Returns:
        Tuple of ``(medicare_cost, MedicareBreakdown)``.
    """
    if status.medicare_count == 0:
        return 0.0, _EMPTY_MEDICARE_BREAKDOWN
    return calculate_medicare_costs(
        age_primary, age_spouse, magi_two_years_ago, year, filing_status, has_medigap
    )


def calculate_total_healthcare_costs(age_primary: int,
                                     age_spouse: int,
                                     magi_two_years_ago: float,
                                     year: int,
                                     filing_status: str = "married_filing_jointly",
                                     health_status: str = "average",
                                     has_ltc_insurance: bool = False,
                                     has_medigap: bool = True) -> Tuple[float, HealthcareCostBreakdown]:
    """
    Calculate comprehensive healthcare costs for the year.

    Args:
        age_primary: Primary person's age.
        age_spouse: Spouse's age; pass 0 to indicate no spouse.
        magi_two_years_ago: MAGI from 2 years prior (used for IRMAA).
        year: Current year.
        filing_status: Filing status (e.g. ``"married_filing_jointly"``).
        health_status: One of ``"healthy"``, ``"average"``, or ``"chronic"``.
        has_ltc_insurance: Whether they carry LTC insurance.
        has_medigap: Whether they carry Medigap coverage.

    Returns:
        Tuple of ``(total_healthcare_cost, HealthcareCostBreakdown)``.
    """
    status = _classify_ages(age_primary, age_spouse)
    logger.debug(
        f"calculate_total_healthcare_costs: year={year}, "
        f"ages={age_primary}/{age_spouse}, "
        f"{status.total_persons} person(s), "
        f"{status.medicare_count} on Medicare, "
        f"{status.pre_medicare_count} pre-Medicare"
    )

    # --- Medicare costs (one or both persons aged 65+) -------------------
    medicare_cost, medicare_detail = _calculate_medicare(
        status, age_primary, age_spouse, magi_two_years_ago, year,
        filing_status, has_medigap
    )

    # --- Pre-retirement working healthcare (before retirement) ------------
    # Covers employer or private insurance while still working
    preretirement_cost = calculate_preretirement_healthcare_for_year(year, age_primary, age_spouse)

    # --- Pre-Medicare / ACA costs (retired but under 65) -----------------
    # calculate_aca_premium_for_year returns 0.0 when neither person is in
    # their configured ACA age window, so no guard is needed here.
    aca_cost = calculate_aca_premium_for_year(year, age_primary, age_spouse)

    # --- Out-of-pocket expenses -------------------------------------------
    # Falls back to OOP_COST_DEFAULT ("average") for unrecognised health_status values.
    base_oop_cost: int = OOP_COSTS_BY_HEALTH_STATUS.get(health_status, OOP_COST_DEFAULT)
    
    # Apply age-based adjustment to out-of-pocket costs
    # Healthcare costs increase with age (inverse of discretionary spending)
    from calculations import calculate_household_age_adjusted_healthcare_costs
    from config import get_config_manager
    
    config_mgr = get_config_manager()
    is_single = config_mgr.get("personal_info", "is_single_person", False)
    
    oop_cost = calculate_household_age_adjusted_healthcare_costs(
        float(base_oop_cost),
        age_primary,
        age_spouse if age_spouse > 0 else None,
        is_single
    )
    
    logger.debug(
        f"Out-of-pocket healthcare: base=${base_oop_cost:,.0f}, "
        f"age-adjusted=${oop_cost:,.0f} (ages {age_primary}/{age_spouse})"
    )

    # --- Long-term care insurance premiums --------------------------------
    ltc_cost = LTC_ANNUAL_PREMIUM_PER_PERSON * status.total_persons if has_ltc_insurance else 0.0

    breakdown = HealthcareCostBreakdown(
        medicare=medicare_cost,
        pre_medicare=aca_cost,
        preretirement_working=preretirement_cost,
        out_of_pocket=oop_cost,
        ltc_insurance=ltc_cost,
        medicare_detail=medicare_detail,
    )

    logger.info(f"Year {year}: Total healthcare cost = ${breakdown.total:,.0f}")

    return breakdown.total, breakdown


def _validate_healthcare_projection_inputs(
    start_year: int,
    end_year: int,
    magi_projections: List[float],
) -> None:
    """Raise ValueError for invalid project_healthcare_costs arguments."""
    if start_year > end_year:
        raise ValueError(
            f"start_year ({start_year}) must be <= end_year ({end_year})"
        )
    if not magi_projections:
        raise ValueError(
            "magi_projections must contain at least one value "
            f"(one per year from {start_year} to {end_year})"
        )


def _build_magi_lookback(magi_projections: Sequence[float]) -> List[float]:
    """Prepend ``_IRMAA_LOOKBACK_YEARS`` sentinel values to *magi_projections*.

    IRMAA surcharges in year N are based on MAGI from year N-2.  By prepending
    ``_IRMAA_LOOKBACK_YEARS`` copies of the first projected value, index
    ``year_index`` into the returned list always yields the correct lookback
    MAGI for projection year ``year_index``, with no special-casing for the
    first two years.

    Args:
        magi_projections: Already-padded sequence of MAGI values, one per
            projection year.  Must be non-empty.

    Returns:
        New list of length ``len(magi_projections) + _IRMAA_LOOKBACK_YEARS``.
    """
    return [magi_projections[0]] * _IRMAA_LOOKBACK_YEARS + list(magi_projections)


def _healthcare_projection_row(
    year_index: int,
    year: int,
    age_primary_start: int,
    age_spouse_start: int,
    magi_lookback: Sequence[float],
    health_status: str,
    has_ltc_insurance: bool,
    has_medigap: bool,
    filing_status: str = "married_filing_jointly",
) -> Dict:
    """Compute a single year's healthcare projection row."""
    age_primary = age_primary_start + year_index
    age_spouse = age_spouse_start + year_index
    total_cost, breakdown = calculate_total_healthcare_costs(
        age_primary=age_primary,
        age_spouse=age_spouse,
        magi_two_years_ago=magi_lookback[year_index],
        year=year,
        filing_status=filing_status,
        health_status=health_status,
        has_ltc_insurance=has_ltc_insurance,
        has_medigap=has_medigap,
    )
    return {
        'year': year,
        'age_primary': age_primary,
        'age_spouse': age_spouse,
        'total_healthcare_cost': total_cost,
        **asdict(breakdown),
    }


def project_healthcare_costs(
    start_year: int,
    end_year: int,
    age_primary_start: int,
    age_spouse_start: int,
    magi_projections: List[float],
    health_status: str = "average",
    has_ltc_insurance: bool = False,
    has_medigap: bool = True,
    filing_status: str = "married_filing_jointly",
) -> pd.DataFrame:
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
        filing_status: Filing status used for IRMAA calculations
            (e.g. ``"married_filing_jointly"`` or ``"single"``).

    Returns:
        DataFrame with one row per year and the following columns:

        - ``year`` — calendar year
        - ``age_primary`` / ``age_spouse`` — ages for that year
        - ``total_healthcare_cost`` — combined annual cost for both persons
        - All fields from :class:`HealthcareCostBreakdown` (via
          :func:`dataclasses.asdict`), including Medicare part costs,
          IRMAA penalty, ACA premiums, LTC premiums, and OOP costs.
    """
    logger.info(f"Projecting healthcare costs from {start_year} to {end_year}")

    _validate_healthcare_projection_inputs(start_year, end_year, magi_projections)

    expected_years = end_year - start_year + 1
    if len(magi_projections) < expected_years:
        logger.warning(
            f"MAGI projections ({len(magi_projections)}) shorter than year range "
            f"({expected_years}). Padding with last value."
        )
        # Use itertools.chain + repeat + islice to lazily extend the sequence
        # without re-binding the parameter or allocating an intermediate list
        # larger than needed.
        magi_padded: Sequence[float] = list(itertools.islice(
            itertools.chain(magi_projections, itertools.repeat(magi_projections[-1])),
            expected_years,
        ))
    else:
        magi_padded = magi_projections

    # Prepend _IRMAA_LOOKBACK_YEARS sentinel values so that index year_index
    # always yields the MAGI from 2 years before projection year year_index.
    magi_lookback = _build_magi_lookback(magi_padded)

    return pd.DataFrame.from_records(
        _healthcare_projection_row(
            year_index, year,
            age_primary_start, age_spouse_start,
            magi_lookback,
            health_status, has_ltc_insurance, has_medigap,
            filing_status,
        )
        for year_index, year in enumerate(range(start_year, end_year + 1))
    )


def calculate_niit(
    net_investment_income: float,
    magi: float,
    filing_status: str = "married_filing_jointly",
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate Net Investment Income Tax (3.8% surtax).

    Args:
        net_investment_income: Total investment income (must be non-negative).
        magi: Modified Adjusted Gross Income (must be non-negative).
        filing_status: Filing status — must be a key in NIIT_THRESHOLDS;
            raises ValueError for unrecognised values.

    Returns:
        Tuple of (niit_amount, calculation_details).

    Formula:
        NIIT = min(NII, max(0, MAGI - threshold)) * NIIT_RATE

    Key Thresholds (NOT indexed for inflation since 2013):
        - Married Filing Jointly:     $250,000
        - Single:                     $200,000
        - Married Filing Separately:  $125,000
        - Head of Household:          $200,000
    """
    logger.debug("Calculating NIIT: NII=$%,.0f, MAGI=$%,.0f",
                 net_investment_income, magi)

    if net_investment_income < 0 or magi < 0:
        raise ValueError(
            f"Inputs must be non-negative: "
            f"net_investment_income={net_investment_income}, magi={magi}"
        )

    if filing_status not in NIIT_THRESHOLDS:
        raise ValueError(
            f"Unknown filing_status {filing_status!r}. "
            f"Valid values: {sorted(NIIT_THRESHOLDS)}"
        )

    threshold   = NIIT_THRESHOLDS[filing_status]
    niit_amount = min(net_investment_income, max(0, magi - threshold)) * NIIT_RATE

    details: Dict[str, Any] = {
        'net_investment_income': net_investment_income,
        'magi':            magi,
        'threshold':       threshold,
        'niit_rate':       NIIT_RATE,
        'niit_amount':     niit_amount,
        'subject_to_niit': niit_amount > 0,
    }

    if niit_amount > 0:
        logger.info("NIIT Triggered: MAGI=$%,.0f exceeds threshold=$%,.0f, NIIT=$%,.0f",
                    magi, threshold, niit_amount)
    else:
        logger.debug("No NIIT: MAGI=$%,.0f below threshold=$%,.0f", magi, threshold)

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
FUND_CONSERVATION_TOLERANCE = 1.0  # Allow $1 rounding error in fund conservation checks


# ==============================================================================
# DECISION LOGGING
# ==============================================================================

@dataclass
class DecisionReason:
    """A single named decision with its rationale and the values that drove it."""
    decision: str        # Short label, e.g. "Roth Conversion"
    action: str          # What was decided, e.g. "Convert $45,000"
    reason: str          # Human-readable explanation
    values: Dict[str, Any] = field(default_factory=dict)  # Supporting numbers


@dataclass
class DecisionLog:
    """
    Structured record of every material decision made for a single strategy year.

    Each stage populates the relevant fields.  Consumers (UI, reports) can
    iterate ``all_decisions()`` to get a flat list of every reason recorded.
    """
    # --- Tax strategy ---
    tax_strategy: List[DecisionReason] = field(default_factory=list)

    # --- Roth conversion ---
    roth_conversion: List[DecisionReason] = field(default_factory=list)

    # --- ACA / healthcare ---
    aca_decisions: List[DecisionReason] = field(default_factory=list)

    # --- IRMAA ---
    irmaa_decisions: List[DecisionReason] = field(default_factory=list)

    # --- Cash replenishment ---
    cash_replenishment: List[DecisionReason] = field(default_factory=list)

    # --- Brokerage replenishment ---
    brokerage_replenishment: List[DecisionReason] = field(default_factory=list)

    # --- Accumulation / contributions ---
    contribution_decisions: List[DecisionReason] = field(default_factory=list)

    # --- RMD ---
    rmd_decisions: List[DecisionReason] = field(default_factory=list)

    # --- LTCG harvesting ---
    ltcg_decisions: List[DecisionReason] = field(default_factory=list)

    # --- SS income ---
    ss_decisions: List[DecisionReason] = field(default_factory=list)

    def add(self, category: str, decision: str, action: str,
            reason: str, **values: Any) -> None:
        """Convenience method to append a :class:`DecisionReason` to *category*.

        Args:
            category: One of the field names on this dataclass
                      (e.g. ``"roth_conversion"``).
            decision: Short label for the decision point.
            action:   What was chosen.
            reason:   Human-readable explanation.
            **values: Arbitrary keyword arguments stored in
                      :attr:`DecisionReason.values` for display.

        Raises:
            AttributeError: If *category* is not a valid field name.
        """
        entry = DecisionReason(decision=decision, action=action,
                               reason=reason, values=dict(values))
        target: List[DecisionReason] = getattr(self, category)
        target.append(entry)

    def all_decisions(self) -> List[DecisionReason]:
        """Return every :class:`DecisionReason` across all categories, in
        insertion order per category."""
        out: List[DecisionReason] = []
        for f in (
            self.tax_strategy,
            self.roth_conversion,
            self.aca_decisions,
            self.irmaa_decisions,
            self.cash_replenishment,
            self.brokerage_replenishment,
            self.contribution_decisions,
            self.rmd_decisions,
            self.ltcg_decisions,
            self.ss_decisions,
        ):
            out.extend(f)
        return out

    def summary_lines(self) -> List[str]:
        """Return a flat list of human-readable summary strings, one per
        decision, suitable for logging or display."""
        lines = []
        for dr in self.all_decisions():
            vals = ", ".join(f"{k}={v}" for k, v in dr.values.items()) if dr.values else ""
            line = f"[{dr.decision}] {dr.action} — {dr.reason}"
            if vals:
                line += f" ({vals})"
            lines.append(line)
        return lines


def _category_for(entry: "DecisionReason") -> str:
    """Return the :class:`DecisionLog` field name that best matches *entry*.

    This is used when merging a sub-log (e.g. from ``rebalance_accounts``)
    into a stage-level :class:`DecisionLog`.  The mapping is based on the
    ``decision`` label stored on the entry.
    """
    label = entry.decision.lower()
    if "cash" in label:
        return "cash_replenishment"
    if "brokerage" in label or "taxable" in label:
        return "brokerage_replenishment"
    if "roth" in label and "conversion" not in label:
        return "roth_conversion"
    if "conversion" in label:
        return "roth_conversion"
    if "irmaa" in label:
        return "irmaa_decisions"
    if "aca" in label or "healthcare" in label:
        return "aca_decisions"
    if "rmd" in label:
        return "rmd_decisions"
    if "ltcg" in label or "capital gain" in label:
        return "ltcg_decisions"
    if "social security" in label or "ss " in label:
        return "ss_decisions"
    if "contribution" in label or "401k" in label or "ira" in label:
        return "contribution_decisions"
    # Default bucket
    return "tax_strategy"


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


class BrokerageTransactionLog(TypedDict):
    """Typed transaction log returned by :func:`replenish_brokerage_buffer`.

    Keys
    ----
    traditional_to_brokerage:
        Amount distributed from the Traditional account to the Brokerage buffer.
    brokerage_replenishment:
        Total amount added to the Brokerage buffer this year (equals
        ``traditional_to_brokerage`` since Roth→Brokerage is intentionally omitted).
    """
    traditional_to_brokerage: float
    brokerage_replenishment:  float


class ScenarioType(str, Enum):
    """Available retirement scenario types"""
    DEFAULT = "default"
    EARLY_RETIRE = "early_retire"
    HIGH_INCOME = "high_income"


@dataclass(frozen=True)
class ScenarioConfig:
    """Configuration for a retirement scenario
    
    This dataclass defines the structure of scenario parameters used
    for retirement withdrawal strategy calculations.
    """
    start_year: int
    end_year: int
    initial_balances: PortfolioBalances
    initial_expenses: float
    person1_name: str
    person2_name: str
    growth_rate: float
    expense_inflation: float
    ss_claiming_age: int
    retirement_year: int
    has_wages: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility"""
        return {
            'start_year': self.start_year,
            'end_year': self.end_year,
            'initial_balances': self.initial_balances,
            'initial_expenses': self.initial_expenses,
            'person1_name': self.person1_name,
            'person2_name': self.person2_name,
            'growth_rate': self.growth_rate,
            'expense_inflation': self.expense_inflation,
            'ss_claiming_age': self.ss_claiming_age,
            'retirement_year': self.retirement_year,
            'has_wages': self.has_wages
        }


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
    ltcg_harvested: float  # Long-term capital gains harvested (taxable portion)
    daf_contribution: float
    
    # Expenses and taxes
    expenses: float
    agi: float  # Adjusted Gross Income
    magi: float  # Modified Adjusted Gross Income
    federal_tax: float
    irmaa_penalty: float
    aca_premium: float
    
    # Account balances (end of year)
    balances: PortfolioBalances
    
    # Cost basis tracking (added after required fields to maintain compatibility)
    basis_returned: float = 0.0  # Tax-free return of cost basis from brokerage withdrawals
    brokerage_ltcg_ratio: float = 0.0  # Actual LTCG ratio for this year (gains / value)
    brokerage_basis_ratio: float = 0.0  # Actual basis ratio for this year (basis / value)
    
    # State income tax (added after balances to maintain field order)
    state_tax: float = 0.0
    
    # NEW: Fund movement tracking (v2.0 - Account Rebalancing)
    cash_replenishment: float = 0.0
    payroll_tax: float = 0.0    # FICA + Medicare + State + FUTA/SUTA (wages years only)
    wages_to_trad: float = 0.0  # Wages → Traditional 401k contribution
    wages_to_roth: float = 0.0  # Wages → Roth 401k / Roth IRA contribution
    brokerage_replenishment: float = 0.0
    traditional_to_cash: float = 0.0
    traditional_to_brokerage: float = 0.0
    brokerage_to_cash: float = 0.0
    roth_to_cash: float = 0.0
    roth_to_brokerage: float = 0.0
    conversion_executed: float = 0.0
    # Accumulation-phase contributions routed from take-home cash
    cash_to_roth: float = 0.0
    cash_to_brokerage: float = 0.0

    # Decision reasoning log (v2.1 - Strategy Instrumentation)
    decision_log: DecisionLog = field(default_factory=DecisionLog)
    
    def _collect_fund_movements(self) -> Dict[str, float]:
        """
        Collect all fund movements with signed amounts.
        
        Returns:
            Dictionary mapping movement descriptions to signed amounts
            (negative = outflow, positive = inflow)
        """
        return {
            "Traditional → Cash": -self.traditional_to_cash,
            "Traditional → Brokerage": -self.traditional_to_brokerage,
            "Brokerage → Cash": -self.brokerage_to_cash,
            "Roth → Cash": -self.roth_to_cash,
            "Roth → Brokerage": -self.roth_to_brokerage,
            "Conversion (Trad→Roth)": 0.0,  # Net zero: -trad, +roth
            "Cash Replenishment": self.cash_replenishment,
            "Brokerage Replenishment": self.brokerage_replenishment,
        }
    
    def _log_fund_movements(self, movements: Dict[str, float]) -> None:
        """
        Log fund movements categorized by sign.
        
        Args:
            movements: Dictionary mapping movement descriptions to signed amounts
                      (negative = outflow, positive = inflow)
        """
        outflows = {k: v for k, v in movements.items() if v < 0}
        inflows = {k: v for k, v in movements.items() if v > 0}
        
        if outflows:
            logger.info("  OUTFLOWS (money leaving accounts):")
            for description, amount in outflows.items():
                logger.info(f"    {description}: ${abs(amount):,.2f}")
            logger.info(f"    TOTAL OUTFLOWS: ${abs(sum(outflows.values())):,.2f}")
        
        if inflows:
            logger.info("  INFLOWS (money entering accounts):")
            for description, amount in inflows.items():
                logger.info(f"    {description}: ${amount:,.2f}")
            logger.info(f"    TOTAL INFLOWS: ${sum(inflows.values()):,.2f}")
    
    def validate_fund_conservation(self) -> bool:
        """
        Verify that all fund movements balance to zero
        (what leaves one account enters another)
        
        Returns:
            True if funds are conserved, False otherwise
        """
        # Collect all fund movements with signed amounts
        movements = self._collect_fund_movements()
        
        # Early return if no movements occurred
        if all(amount == 0 for amount in movements.values()):
            logger.info(f"Year {self.year}: No fund movements this year")
            return True
        
        # Calculate net balance (should be zero)
        net_balance = sum(movements.values())
        
        # Log fund conservation details at INFO level
        logger.info(f"Year {self.year}: Fund Conservation Check")
        self._log_fund_movements(movements)
        logger.info(f"  NET BALANCE: ${abs(net_balance):,.2f} (should be ~$0)")
        
        # Check if balance is within tolerance
        if abs(net_balance) > FUND_CONSERVATION_TOLERANCE:
            logger.error(
                f"Year {self.year}: Fund conservation VIOLATED: "
                f"${abs(net_balance):,.2f} imbalance (see details above)"
            )
            return False
        
        logger.info(f"  Fund conservation: ✓ PASSED")
        return True


# ==============================================================================
# ACCOUNT REBALANCING HELPER FUNCTIONS (v2.0)
# ==============================================================================

def replenish_cash_buffer(balances: PortfolioBalances,
                          expenses: float,
                          age_primary: int,
                          year: int,
                          cash_target_override: Optional[float] = None,
                          brokerage_account: Optional[BrokerageAccount] = None,
                          portfolio_df: Optional[pd.DataFrame] = None,
                          target_allocation: Optional[Dict[str, float]] = None,
                          current_agi: float = 0,
                          filing_status: str = 'single',
                          recent_sales: Optional[List[Dict]] = None) -> Tuple[PortfolioBalances, Dict[str, float], DecisionLog]:
    """
    Replenish cash buffer to target based on configured years of expenses.

    Implements tax-efficient cash buffer maintenance by transferring funds
    from other accounts in priority order:
    1. Brokerage → Cash (with smart security selection when available)
    2. Roth → Cash (tax-free if qualified, avoids LTCG from Brokerage→Cash)
    3. Traditional → Cash (ordinary income tax, last resort)
    4. Emergency Roth → Cash (if still short after Traditional)

    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        age_primary: Primary person's age
        year: Current year
        cash_target_override: If provided, use this value as the cash target
            instead of the expenses-based retirement target.  Used during the
            accumulation phase where the target is wages-based.
        brokerage_account: Optional BrokerageAccount for cost basis tracking
        portfolio_df: Optional portfolio DataFrame for smart security selection
        target_allocation: Target allocation dict for smart selection
        current_agi: Current AGI for tax rate determination
        filing_status: Tax filing status
        recent_sales: Recent sales for wash sale detection

    Returns:
        Tuple of (updated_balances, transaction_log, decision_log)
        - updated_balances: PortfolioBalances after replenishment
        - transaction_log: Dict with all fund movements including 'brokerage_ltcg'
        - decision_log: DecisionLog recording why each source was chosen
    """
    dl = DecisionLog()

    if cash_target_override is not None:
        cash_target = cash_target_override
    else:
        cash_target, _ = calculate_cash_buffer_targets(expenses)
    cash_deficit = max(0, cash_target - balances.cash)

    if cash_deficit < 100:  # Ignore trivial amounts
        dl.add("cash_replenishment", "Cash Buffer Check", "No action needed",
               "Cash balance meets or exceeds target — no replenishment required.",
               cash_balance=f"${balances.cash:,.0f}",
               cash_target=f"${cash_target:,.0f}")
        return balances, {
            'brokerage_to_cash': 0.0,
            'traditional_to_cash': 0.0,
            'roth_to_cash': 0.0,
            'cash_replenishment': 0.0,
            'brokerage_ltcg': 0.0
        }, dl

    logger.warning(f"Year {year}: Cash buffer below target (${balances.cash:,.0f} < ${cash_target:,.0f})")
    logger.warning(f"  Cash deficit: ${cash_deficit:,.0f}")
    logger.warning(f"  Current account balances:")
    logger.warning(f"    Cash: ${balances.cash:,.2f}")
    logger.warning(f"    Taxable (Brokerage): ${balances.taxable:,.2f}")
    logger.warning(f"    Traditional: ${balances.traditional:,.2f}")
    logger.warning(f"    Roth: ${balances.roth:,.2f}")
    logger.warning(f"    DAF: ${balances.daf:,.2f}")

    dl.add("cash_replenishment", "Cash Buffer Deficit",
           f"Replenish ${cash_deficit:,.0f}",
           "Cash balance fell below the configured target; sourcing funds in tax-efficient priority order "
           "(Brokerage first, then Roth if age-qualified, then Traditional as last resort).",
           cash_balance=f"${balances.cash:,.0f}",
           cash_target=f"${cash_target:,.0f}",
           deficit=f"${cash_deficit:,.0f}")

    transactions = {
        'brokerage_to_cash': 0.0,
        'traditional_to_cash': 0.0,
        'roth_to_cash': 0.0,
        'cash_replenishment': 0.0,
        'brokerage_ltcg': 0.0
    }

    # Step 1: Transfer from Brokerage (tax-free return of basis / LTCG)
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
        
        # Calculate LTCG from brokerage withdrawal using smart selection if available
        if brokerage_account is not None and transfer > 0:
            try:
                # Try smart selection first if available
                if SMART_SELECTION_AVAILABLE and should_use_smart_selection(portfolio_df, 'Brokerage'):
                    basis_returned, ltcg_realized, plan = withdraw_from_brokerage_smart(
                        amount=transfer,
                        brokerage_account=brokerage_account,
                        portfolio_df=portfolio_df,
                        year=year,
                        target_allocation=target_allocation or DEFAULT_TARGET_ALLOCATION,
                        current_agi=current_agi,
                        filing_status=filing_status,
                        recent_sales=recent_sales or [],
                    )
                    transactions['brokerage_ltcg'] = ltcg_realized
                    
                    if plan:
                        logger.info(f"  Smart selection: ${transfer:,.0f} from Brokerage to Cash")
                        logger.info(f"    Basis: ${basis_returned:,.0f}, LTCG: ${ltcg_realized:,.0f}")
                        logger.info(f"    Securities: {len(plan.securities)}, Tax: ${plan.estimated_tax:,.0f}")
                    else:
                        logger.info(f"  FIFO: ${transfer:,.0f} from Brokerage to Cash: "
                                   f"${basis_returned:,.0f} basis, ${ltcg_realized:,.0f} LTCG")
                else:
                    # Fallback to FIFO
                    basis_returned, ltcg_realized = brokerage_account.withdraw_fifo(transfer, year)
                    transactions['brokerage_ltcg'] = ltcg_realized
                    logger.info(f"  FIFO: ${transfer:,.0f} from Brokerage to Cash: "
                               f"${basis_returned:,.0f} basis, ${ltcg_realized:,.0f} LTCG")
            except Exception as e:
                logger.warning(f"  Error in withdrawal: {e}, using estimated LTCG")
                transactions['brokerage_ltcg'] = transfer * BROKERAGE_LTCG_RATIO
                logger.info(f"  Transferred ${transfer:,.0f} from Brokerage to Cash "
                           f"(estimated ${transactions['brokerage_ltcg']:,.0f} LTCG)")
        else:
            # No brokerage account tracking, use default ratio
            transactions['brokerage_ltcg'] = transfer * BROKERAGE_LTCG_RATIO
            logger.info(f"  Transferred ${transfer:,.0f} from Brokerage to Cash "
                       f"(estimated ${transactions['brokerage_ltcg']:,.0f} LTCG)")
        
        cash_deficit -= transfer
        dl.add("cash_replenishment", "Brokerage → Cash",
               f"Transfer ${transfer:,.0f}",
               f"Brokerage is the first source: ${transfer - transactions['brokerage_ltcg']:,.0f} is tax-free return of cost basis and "
               f"${transactions['brokerage_ltcg']:,.0f} is long-term capital gains — preferred over Traditional (ordinary income).",
               transferred=f"${transfer:,.0f}",
               basis_returned=f"${transfer - transactions['brokerage_ltcg']:,.0f}",
               ltcg_realized=f"${transactions['brokerage_ltcg']:,.0f}",
               remaining_deficit=f"${cash_deficit:,.0f}")

    # Step 2: Roth distribution (tax-free if qualified, preferred over Traditional to avoid future LTCG)
    if cash_deficit > 0 and balances.roth > 0 and age_primary >= 59.5:
        distribution = min(cash_deficit, balances.roth * 0.20)  # Max 20% per year (doubled from 10%)
        balances = PortfolioBalances(
            cash=balances.cash + distribution,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth - distribution,
            daf=balances.daf
        )
        transactions['roth_to_cash'] = distribution
        cash_deficit -= distribution
        logger.info(f"  Distributed ${distribution:,.0f} from Roth to Cash (tax-free, avoids LTCG)")
        dl.add("cash_replenishment", "Roth → Cash",
               f"Distribute ${distribution:,.0f}",
               "Roth is used before Traditional: qualified distributions are 100% tax-free and "
               "avoid the LTCG that would arise from routing through Brokerage. "
               "Capped at 10% of Roth balance to preserve long-term tax-free growth.",
               distributed=f"${distribution:,.0f}",
               roth_balance=f"${balances.roth:,.0f}",
               age=age_primary,
               remaining_deficit=f"${cash_deficit:,.0f}")
    elif cash_deficit > 0 and balances.roth > 0 and age_primary < 59.5:
        dl.add("cash_replenishment", "Roth → Cash Skipped",
               "No distribution (age < 59½)",
               "Roth distributions before age 59½ may incur a 10% early-withdrawal penalty; "
               "Traditional is used instead to avoid the penalty.",
               age=age_primary)

    # Step 3: Distribute from Traditional (ordinary income tax, last resort for cash)
    # Blocked before age 59½ — early withdrawal triggers a 10% IRS penalty (IRC §72(t))
    if cash_deficit > 0 and balances.traditional > 0:
        if age_primary < EARLY_WITHDRAWAL_PENALTY_AGE:
            dl.add("cash_replenishment", "Traditional → Cash Blocked",
                   "No distribution (age < 59½)",
                   "Withdrawals from Traditional IRA/401k before age 59½ incur a 10% IRS early-withdrawal "
                   "penalty (IRC §72(t)). This transfer is blocked to avoid the penalty. "
                   "Build cash reserves from wages or after-tax savings instead.",
                   age=age_primary)
        else:
            distribution = min(cash_deficit, balances.traditional * 0.20)  # Max 20% per year (doubled from 10%)
            balances = PortfolioBalances(
                cash=balances.cash + distribution,
                taxable=balances.taxable,
                traditional=balances.traditional - distribution,
                roth=balances.roth,
                daf=balances.daf
            )
            transactions['traditional_to_cash'] = distribution
            logger.info(f"  Distributed ${distribution:,.0f} from Traditional to Cash (ordinary income tax)")
            dl.add("cash_replenishment", "Traditional → Cash",
                   f"Distribute ${distribution:,.0f}",
                   "Traditional is the last resort for cash: every dollar withdrawn is taxed as ordinary income. "
                   "Capped at 20% of Traditional balance to limit tax impact in a single year.",
                   distributed=f"${distribution:,.0f}",
                   traditional_balance=f"${balances.traditional:,.0f}",
                   remaining_deficit=f"${cash_deficit:,.0f}")

    # Step 4: Emergency Roth if still needed (after Traditional exhausted)
    if cash_deficit > 0 and balances.roth > 0:
        distribution = min(cash_deficit, balances.roth * 0.10)  # Max 10% additional (doubled from 5%)
        balances = PortfolioBalances(
            cash=balances.cash + distribution,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth - distribution,
            daf=balances.daf
        )
        transactions['roth_to_cash'] += distribution
        logger.warning(f"  EMERGENCY - Additional ${distribution:,.0f} from Roth to Cash (total: ${transactions['roth_to_cash']:,.0f})")
        dl.add("cash_replenishment", "Emergency Roth → Cash",
               f"Emergency distribute ${distribution:,.0f}",
               "EMERGENCY: Traditional balance was insufficient to cover the remaining deficit. "
               "An additional Roth distribution (capped at 5% of Roth balance) was taken as a last resort.",
               distributed=f"${distribution:,.0f}",
               total_roth_to_cash=f"${transactions['roth_to_cash']:,.0f}",
               remaining_deficit=f"${cash_deficit:,.0f}")

    transactions['cash_replenishment'] = sum([
        transactions['brokerage_to_cash'],
        transactions['traditional_to_cash'],
        transactions['roth_to_cash']
    ])

    logger.info(f"  Total cash replenishment: ${transactions['cash_replenishment']:,.0f}")
    logger.info(f"  New cash balance: ${balances.cash:,.0f}")

    return balances, transactions, dl


def replenish_brokerage_buffer(balances: PortfolioBalances,
                               expenses: float,
                               age_primary: int,
                               year: int,
                               brokerage_account: Optional[BrokerageAccount] = None) -> Tuple[PortfolioBalances, BrokerageTransactionLog, DecisionLog]:
    """
    Replenish brokerage buffer to target based on configured years of expenses.

    Implements tax-efficient brokerage buffer maintenance by distributing
    funds from retirement accounts:
    1. Traditional → Brokerage (ordinary income tax)

    Note: Roth → Brokerage transfers have been removed to avoid triggering
    unnecessary LTCG when those funds are later moved to Cash.
    
    When brokerage_account is provided, tracks transfers for accurate cost basis.
    
    The trigger for replenishment can be adjusted via the
    brokerage_rebalance_trigger_multiplier configuration parameter.

    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        age_primary: Primary person's age
        year: Current year
        brokerage_account: Optional BrokerageAccount for cost basis tracking

    Returns:
        Tuple of (updated_balances, transaction_log, decision_log)
        - updated_balances: PortfolioBalances after replenishment
        - transaction_log: BrokerageTransactionLog with all fund movements
        - decision_log: DecisionLog recording why each source was chosen
    """
    from config import get_value_with_session_override
    
    dl = DecisionLog()
    _, brokerage_target = calculate_cash_buffer_targets(expenses)
    
    # The brokerage_target now already includes the multiplier from calculate_cash_buffer_targets()
    # No need to apply it again here
    brokerage_deficit = max(0, brokerage_target - balances.taxable)

    if brokerage_deficit < _BUFFER_REPLENISHMENT_MIN_DEFICIT:
        dl.add("brokerage_replenishment", "Brokerage Buffer Check", "No action needed",
               "Brokerage balance meets or exceeds target level — no replenishment required.",
               brokerage_balance=f"${balances.taxable:,.0f}",
               brokerage_target=f"${brokerage_target:,.0f}")
        return balances, BrokerageTransactionLog(
            traditional_to_brokerage=0.0,
            brokerage_replenishment=0.0,
        ), dl

    logger.info(f"Year {year}: Brokerage buffer below target level (${balances.taxable:,.0f} < ${brokerage_target:,.0f})")
    logger.info(f"  Brokerage target: ${brokerage_target:,.0f}")
    logger.info(f"  Brokerage deficit: ${brokerage_deficit:,.0f}")

    dl.add("brokerage_replenishment", "Brokerage Buffer Deficit",
           f"Replenish ${brokerage_deficit:,.0f}",
           "Brokerage balance fell below the configured target level. "
           "Sourcing from Traditional (ordinary income) — Roth→Brokerage is intentionally avoided "
           "because it would trigger LTCG when those funds are later moved to Cash.",
           brokerage_balance=f"${balances.taxable:,.0f}",
           brokerage_target=f"${brokerage_target:,.0f}",
           deficit=f"${brokerage_deficit:,.0f}")

    transactions: BrokerageTransactionLog = BrokerageTransactionLog(
        traditional_to_brokerage=0.0,
        brokerage_replenishment=0.0,
    )

    # Step 1: Distribute from Traditional (taxable)
    # Blocked before age 59½ — early withdrawal triggers a 10% IRS penalty (IRC §72(t))
    if brokerage_deficit > 0 and balances.traditional > 0:
        if age_primary < EARLY_WITHDRAWAL_PENALTY_AGE:
            dl.add("brokerage_replenishment", "Traditional → Brokerage Blocked",
                   "No distribution (age < 59½)",
                   "Withdrawals from Traditional IRA/401k before age 59½ incur a 10% IRS early-withdrawal "
                   "penalty (IRC §72(t)). This transfer is blocked to avoid the penalty. "
                   "Use after-tax wages or Roth contributions to build the brokerage balance instead.",
                   age=age_primary)
        else:
            distribution = min(brokerage_deficit, balances.traditional * _MAX_TRADITIONAL_TO_BROKERAGE_RATE)
            balances = replace(
                balances,
                taxable=balances.taxable + distribution,
                traditional=balances.traditional - distribution,
            )
            transactions['traditional_to_brokerage'] = distribution
            brokerage_deficit -= distribution
            
            # Track transfer in brokerage account for cost basis
            if brokerage_account is not None:
                brokerage_account.add_transfer(year, distribution, "trad_to_brok")
            
            logger.info(f"  Distributed ${distribution:,.0f} from Traditional to Brokerage (ordinary income tax)")
            dl.add("brokerage_replenishment", "Traditional → Brokerage",
                   f"Distribute ${distribution:,.0f}",
                   "Traditional is the sole source for brokerage replenishment. "
                   "Capped at 30% of Traditional balance to limit the ordinary-income tax hit in a single year.",
                   distributed=f"${distribution:,.0f}",
                   traditional_balance=f"${balances.traditional:,.0f}",
                   remaining_deficit=f"${brokerage_deficit:,.0f}")

    # Roth → Brokerage intentionally omitted — see docstring
    if brokerage_deficit > _BUFFER_REPLENISHMENT_MIN_DEFICIT:
        dl.add("brokerage_replenishment", "Roth → Brokerage Skipped",
               "No Roth transfer to Brokerage",
               "Roth→Brokerage transfers are intentionally skipped: moving Roth funds to Brokerage "
               "would create a taxable LTCG event when those funds are later moved to Cash. "
               "Any remaining deficit will be covered by direct Roth→Cash transfers instead.",
               remaining_deficit=f"${brokerage_deficit:,.0f}")

    transactions['brokerage_replenishment'] = transactions['traditional_to_brokerage']

    logger.info(f"  Total brokerage replenishment: ${transactions['brokerage_replenishment']:,.0f}")
    logger.info(f"  New brokerage balance: ${balances.taxable:,.0f}")

    return balances, transactions, dl

def calculate_anticipated_buffer_needs(balances: PortfolioBalances,
                                       expenses: float,
                                       age_primary: int,
                                       federal_tax: float = 0.0,
                                       irmaa_penalty: float = 0.0,
                                       aca_premium: float = 0.0,
                                       medical_costs: float = 0.0,
                                       brokerage_account: Optional[BrokerageAccount] = None) -> Dict[str, float]:
    """
    Calculate anticipated buffer replenishment needs BEFORE executing conversions.
    
    This lookahead function estimates how much will need to be withdrawn from
    Traditional and Roth accounts to maintain cash and brokerage buffers, allowing
    the conversion optimizer to account for these needs and avoid over-converting.
    
    Args:
        balances: Current portfolio balances
        expenses: Annual expenses
        age_primary: Primary person's age
        federal_tax: Estimated federal tax
        irmaa_penalty: Estimated IRMAA penalty
        aca_premium: Estimated ACA premium
        medical_costs: Estimated medical costs
        brokerage_account: Optional BrokerageAccount for LTCG estimation
    
    Returns:
        Dict with anticipated withdrawals:
        - 'traditional_to_cash': Anticipated Traditional → Cash
        - 'traditional_to_brokerage': Anticipated Traditional → Brokerage
        - 'roth_to_cash': Anticipated Roth → Cash
        - 'brokerage_to_cash': Anticipated Brokerage → Cash
        - 'total_traditional_need': Total Traditional needed for buffers
        - 'estimated_ltcg': Estimated LTCG from brokerage withdrawals
    """
    # Simulate cash deductions
    total_cash_outflow = expenses + federal_tax + irmaa_penalty + aca_premium + medical_costs
    simulated_cash = balances.cash - total_cash_outflow
    
    # Calculate buffer targets
    cash_target, brokerage_target = calculate_cash_buffer_targets(expenses)
    
    # Anticipate cash buffer needs
    cash_deficit = max(0, cash_target - simulated_cash)
    traditional_to_cash = 0.0
    roth_to_cash = 0.0
    brokerage_to_cash = 0.0
    
    if cash_deficit > 100:  # Ignore trivial amounts
        # Step 1: Brokerage → Cash
        if balances.taxable > 0:
            transfer = min(cash_deficit, balances.taxable)
            brokerage_to_cash = transfer
            cash_deficit -= transfer
            simulated_cash += transfer
        
        # Step 2: Roth → Cash (if age qualified)
        if cash_deficit > 0 and balances.roth > 0 and age_primary >= 59.5:
            distribution = min(cash_deficit, balances.roth * 0.10)
            roth_to_cash = distribution
            cash_deficit -= distribution
            simulated_cash += distribution
        
        # Step 3: Traditional → Cash (if age qualified)
        if cash_deficit > 0 and balances.traditional > 0 and age_primary >= EARLY_WITHDRAWAL_PENALTY_AGE:
            distribution = min(cash_deficit, balances.traditional * 0.10)
            traditional_to_cash = distribution
            cash_deficit -= distribution
            simulated_cash += distribution
        
        # Step 4: Emergency Roth if still needed
        if cash_deficit > 0 and balances.roth > 0:
            distribution = min(cash_deficit, balances.roth * 0.05)
            roth_to_cash += distribution
    
    # Anticipate brokerage buffer needs
    simulated_brokerage = balances.taxable - brokerage_to_cash
    brokerage_deficit = max(0, brokerage_target - simulated_brokerage)
    traditional_to_brokerage = 0.0
    
    if brokerage_deficit > _BUFFER_REPLENISHMENT_MIN_DEFICIT:
        if balances.traditional > 0 and age_primary >= EARLY_WITHDRAWAL_PENALTY_AGE:
            # Account for Traditional already used for cash
            available_traditional = balances.traditional - traditional_to_cash
            distribution = min(brokerage_deficit, available_traditional * _MAX_TRADITIONAL_TO_BROKERAGE_RATE)
            traditional_to_brokerage = distribution
    
    total_traditional_need = traditional_to_cash + traditional_to_brokerage
    
    # Estimate LTCG from anticipated brokerage withdrawals
    # When brokerage is withdrawn to cash, it realizes capital gains based on the cost basis ratio
    estimated_ltcg = 0.0
    if brokerage_to_cash > 0:
        if brokerage_account is not None and brokerage_account.total_value > 0:
            # Use actual LTCG ratio from brokerage account tracking
            ltcg_ratio = brokerage_account.ltcg_ratio
            estimated_ltcg = brokerage_to_cash * ltcg_ratio
            logger.debug(f"Estimated LTCG using actual ratio: ${estimated_ltcg:,.0f} "
                        f"(${brokerage_to_cash:,.0f} * {ltcg_ratio:.1%})")
        else:
            # Fallback to default 40% LTCG ratio if no brokerage account tracking
            estimated_ltcg = brokerage_to_cash * BROKERAGE_LTCG_RATIO
            logger.debug(f"Estimated LTCG using default ratio: ${estimated_ltcg:,.0f} "
                        f"(${brokerage_to_cash:,.0f} * {BROKERAGE_LTCG_RATIO:.1%})")
    
    logger.debug(f"Anticipated buffer needs: Trad→Cash=${traditional_to_cash:,.0f}, "
                f"Trad→Brok=${traditional_to_brokerage:,.0f}, "
                f"Total Trad need=${total_traditional_need:,.0f}, "
                f"Estimated LTCG=${estimated_ltcg:,.0f}")
    
    return {
        'traditional_to_cash': traditional_to_cash,
        'traditional_to_brokerage': traditional_to_brokerage,
        'roth_to_cash': roth_to_cash,
        'brokerage_to_cash': brokerage_to_cash,
        'total_traditional_need': total_traditional_need,
        'estimated_ltcg': estimated_ltcg,
        'cash_deficit_after_buffers': max(0, cash_target - simulated_cash),
        'brokerage_deficit_after_buffers': max(0, brokerage_target - simulated_brokerage)
    }



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
                      stage: str,
                      federal_tax: float = 0.0,
                      irmaa_penalty: float = 0.0,
                      aca_premium: float = 0.0,
                      medical_costs: float = 0.0,
                      cash_target_override: Optional[float] = None,
                      brokerage_account: Optional[BrokerageAccount] = None,
                      portfolio_df: Optional[pd.DataFrame] = None,
                      target_allocation: Optional[Dict[str, float]] = None,
                      current_agi: float = 0,
                      filing_status: str = 'single',
                      recent_sales: Optional[List[Dict]] = None) -> Tuple[PortfolioBalances, Dict[str, float], DecisionLog]:
    """
    Execute all account rebalancing operations for a given year
    
    This function orchestrates:
    1. Deduct expenses, taxes, IRMAA, ACA, and medical costs from cash
    2. Cash buffer maintenance (2-year target)
    3. Brokerage buffer maintenance (3-year target)
    4. Roth conversion execution
    5. Fund movement tracking
    6. Dynamic security selection for intelligent withdrawals (when portfolio data available)
    
    Args:
        balances: Current portfolio balances
        expenses: Annual expenses for this year
        roth_conversion: Roth conversion amount (from BETR algorithm)
        year: Current year
        age_primary: Primary person's age
        stage: Current life stage
        federal_tax: Federal tax amount to deduct from cash
        irmaa_penalty: IRMAA penalty to deduct from cash
        aca_premium: ACA premium to deduct from cash
        medical_costs: Medical costs to deduct from cash
        cash_target_override: If provided, pass to replenish_cash_buffer as the
            cash target (used during accumulation for wages-based buffer).
        brokerage_account: Optional BrokerageAccount for cost basis tracking
        portfolio_df: Optional portfolio DataFrame for smart security selection
        target_allocation: Target allocation dict for rebalancing {'Cash': 10, 'Bonds': 30, 'Stocks': 60}
        current_agi: Current AGI for tax rate determination in smart selection
        filing_status: Tax filing status for smart selection
        recent_sales: Recent sales for wash sale detection in smart selection
    
    Returns:
        Tuple of (updated_balances, transaction_log, decision_log)
        - updated_balances: PortfolioBalances after all movements
        - transaction_log: Dict with all fund movements for reporting
        - decision_log: DecisionLog with reasons for every buffer/conversion action
    """
    dl = DecisionLog()

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
        'brokerage_replenishment': 0.0,
        'brokerage_ltcg': 0.0
    }

    # Step 1: Deduct expenses, taxes, IRMAA, ACA, and medical costs from cash account FIRST
    total_cash_outflow = expenses + federal_tax + irmaa_penalty + aca_premium + medical_costs

    logger.info(f"Year {year}: Deducting costs from cash")
    logger.info(f"  Cash before deductions: ${balances.cash:,.2f}")
    logger.info(f"  Expenses: ${expenses:,.2f}")
    logger.info(f"  Federal Tax: ${federal_tax:,.2f}")
    logger.info(f"  IRMAA Penalty: ${irmaa_penalty:,.2f}")
    logger.info(f"  ACA Premium: ${aca_premium:,.2f}")
    logger.info(f"  Medical Costs: ${medical_costs:,.2f}")
    logger.info(f"  Total cash outflow: ${total_cash_outflow:,.2f}")

    balances = PortfolioBalances(
        cash=balances.cash - total_cash_outflow,
        taxable=balances.taxable,
        traditional=balances.traditional,
        roth=balances.roth,
        daf=balances.daf
    )
    transactions['expenses_paid'] = expenses
    transactions['taxes_paid'] = federal_tax
    transactions['irmaa_paid'] = irmaa_penalty
    transactions['aca_paid'] = aca_premium
    transactions['medical_paid'] = medical_costs

    logger.info(f"  Cash after deductions: ${balances.cash:,.2f}")

    # Step 2: Optimized buffer replenishment strategy
    # Check if Brokerage can cover cash needs AND maintain its own buffer
    cash_target, brokerage_target = calculate_cash_buffer_targets(expenses)
    if cash_target_override is not None:
        cash_target = cash_target_override
    
    cash_deficit = max(0, cash_target - balances.cash)
    
    # Calculate what brokerage would have after covering cash deficit
    brokerage_after_cash = balances.taxable - cash_deficit
    brokerage_deficit_after_cash = max(0, brokerage_target - brokerage_after_cash)
    
    # Tax-efficient routing decision:
    # If Brokerage can cover cash AND maintain buffer: use normal flow (Brokerage→Cash, then Trad→Brokerage)
    # If Brokerage cannot maintain buffer after cash: route Traditional directly to Cash for the shortfall
    if cash_deficit > 0 and brokerage_deficit_after_cash > _BUFFER_REPLENISHMENT_MIN_DEFICIT:
        # Brokerage can't cover both - use optimized routing
        logger.info(f"Year {year}: Optimized routing - Brokerage insufficient for both cash and buffer")
        logger.info(f"  Cash deficit: ${cash_deficit:,.0f}")
        logger.info(f"  Brokerage balance: ${balances.taxable:,.0f}")
        logger.info(f"  Brokerage after cash transfer: ${brokerage_after_cash:,.0f}")
        logger.info(f"  Brokerage target: ${brokerage_target:,.0f}")
        logger.info(f"  Brokerage deficit after cash: ${brokerage_deficit_after_cash:,.0f}")
        
        # Route what Brokerage CAN provide to Cash (maintaining its buffer)
        brokerage_can_provide = max(0, balances.taxable - brokerage_target)
        
        if brokerage_can_provide > 0:
            # Transfer available brokerage to cash
            transfer = min(cash_deficit, brokerage_can_provide)
            balances = PortfolioBalances(
                cash=balances.cash + transfer,
                taxable=balances.taxable - transfer,
                traditional=balances.traditional,
                roth=balances.roth,
                daf=balances.daf
            )
            transactions['brokerage_to_cash'] = transfer
            
            # Calculate LTCG from brokerage withdrawal using smart selection if available
            if brokerage_account is not None and transfer > 0:
                try:
                    # Try smart selection first if available
                    _init_smart_selection()
                    if (SMART_SELECTION_AVAILABLE and should_use_smart_selection is not None
                        and should_use_smart_selection(portfolio_df, 'Brokerage')):
                        if withdraw_from_brokerage_smart is not None:
                            basis_returned, ltcg_realized, plan = withdraw_from_brokerage_smart(
                                amount=transfer,
                                brokerage_account=brokerage_account,
                                portfolio_df=portfolio_df,
                                year=year,
                                target_allocation=target_allocation or DEFAULT_TARGET_ALLOCATION,
                                current_agi=current_agi,
                                filing_status=filing_status,
                                recent_sales=recent_sales or [],
                            )
                            transactions['brokerage_ltcg'] = ltcg_realized
                            
                            if plan:
                                logger.info(f"  Smart selection used for ${transfer:,.0f} withdrawal:")
                                logger.info(f"    Securities: {len(plan.securities)}")
                                logger.info(f"    Basis: ${basis_returned:,.0f}, LTCG: ${ltcg_realized:,.0f}")
                                logger.info(f"    Tax impact: ${plan.estimated_tax:,.0f}")
                                logger.info(f"    Drift improvement: {plan.drift_improvement:+.2f}%")
                                
                                if format_liquidation_summary_for_log is not None:
                                    dl.add("brokerage_withdrawal", "Smart Security Selection",
                                           f"Withdrew ${transfer:,.0f} using intelligent selection",
                                           format_liquidation_summary_for_log(plan))
                            else:
                                logger.info(f"  FIFO fallback used: ${basis_returned:,.0f} basis, ${ltcg_realized:,.0f} LTCG")
                        else:
                            # Fallback to FIFO
                            basis_returned, ltcg_realized = brokerage_account.withdraw_fifo(transfer, year)
                    else:
                        # Fallback to FIFO
                        basis_returned, ltcg_realized = brokerage_account.withdraw_fifo(transfer, year)
                        transactions['brokerage_ltcg'] = ltcg_realized
                        logger.info(f"  FIFO withdrawal: ${transfer:,.0f} from Brokerage to Cash: "
                                   f"${basis_returned:,.0f} basis, ${ltcg_realized:,.0f} LTCG")
                except Exception as e:
                    logger.warning(f"  Error in withdrawal: {e}, using estimated LTCG")
                    transactions['brokerage_ltcg'] = transfer * BROKERAGE_LTCG_RATIO
                    logger.info(f"  Transferred ${transfer:,.0f} from Brokerage to Cash "
                               f"(estimated ${transactions['brokerage_ltcg']:,.0f} LTCG)")
            else:
                transactions['brokerage_ltcg'] = transfer * BROKERAGE_LTCG_RATIO
                logger.info(f"  Transferred ${transfer:,.0f} from Brokerage to Cash "
                           f"(estimated ${transactions['brokerage_ltcg']:,.0f} LTCG)")
            
            cash_deficit -= transfer
            
            dl.add("cash_replenishment", "Brokerage → Cash (Partial)",
                   f"Transfer ${transfer:,.0f}",
                   f"Brokerage provided what it could while maintaining its buffer target. "
                   f"${transfer - transactions['brokerage_ltcg']:,.0f} is tax-free basis return, "
                   f"${transactions['brokerage_ltcg']:,.0f} is LTCG. "
                   "Remaining cash deficit will be sourced directly from Traditional to avoid "
                   "double taxation (ordinary income on Trad→Broker, then LTCG on Broker→Cash).",
                   transferred=f"${transfer:,.0f}",
                   basis_returned=f"${transfer - transactions['brokerage_ltcg']:,.0f}",
                   ltcg_realized=f"${transactions['brokerage_ltcg']:,.0f}",
                   remaining_deficit=f"${cash_deficit:,.0f}")
        
        # Route remaining cash deficit directly from Traditional (avoiding Brokerage)
        if cash_deficit > _BUFFER_REPLENISHMENT_MIN_DEFICIT and balances.traditional > 0:
            if age_primary >= EARLY_WITHDRAWAL_PENALTY_AGE:
                distribution = min(cash_deficit, balances.traditional * 0.15)  # Cap at 15%
                balances = PortfolioBalances(
                    cash=balances.cash + distribution,
                    taxable=balances.taxable,
                    traditional=balances.traditional - distribution,
                    roth=balances.roth,
                    daf=balances.daf
                )
                transactions['traditional_to_cash'] = distribution
                cash_deficit -= distribution
                logger.info(f"  Distributed ${distribution:,.0f} directly from Traditional to Cash (optimized routing)")
                
                dl.add("cash_replenishment", "Traditional → Cash (Optimized)",
                       f"Distribute ${distribution:,.0f}",
                       "TAX OPTIMIZATION: Routing Traditional directly to Cash instead of through Brokerage. "
                       "This avoids double taxation: we pay ordinary income tax once on the Traditional withdrawal, "
                       "rather than paying ordinary income on Trad→Broker PLUS LTCG when those funds later move Broker→Cash. "
                       "This saves approximately 15-20% in LTCG on 40% of the amount.",
                       distributed=f"${distribution:,.0f}",
                       tax_savings_strategy="Direct routing avoids LTCG on replenishment",
                       remaining_deficit=f"${cash_deficit:,.0f}")
        
        # Handle any remaining deficit with Roth if needed
        if cash_deficit > _BUFFER_REPLENISHMENT_MIN_DEFICIT and balances.roth > 0 and age_primary >= 59.5:
            distribution = min(cash_deficit, balances.roth * 0.10)
            balances = PortfolioBalances(
                cash=balances.cash + distribution,
                taxable=balances.taxable,
                traditional=balances.traditional,
                roth=balances.roth - distribution,
                daf=balances.daf
            )
            transactions['roth_to_cash'] = distribution
            logger.info(f"  Distributed ${distribution:,.0f} from Roth to Cash")
            
            dl.add("cash_replenishment", "Roth → Cash",
                   f"Distribute ${distribution:,.0f}",
                   "Roth used to cover remaining cash deficit after Traditional.",
                   distributed=f"${distribution:,.0f}")
        
        transactions['cash_replenishment'] = (transactions['brokerage_to_cash'] +
                                             transactions['traditional_to_cash'] +
                                             transactions['roth_to_cash'])
        
        # After handling cash needs with optimized routing, check if brokerage still needs replenishment
        # This handles the case where brokerage was already below target before this year
        current_brokerage_deficit = max(0, brokerage_target - balances.taxable)
        if current_brokerage_deficit > _BUFFER_REPLENISHMENT_MIN_DEFICIT:
            logger.info(f"Year {year}: Brokerage still below target after optimized routing, replenishing...")
            balances, brokerage_txns, brok_dl = replenish_brokerage_buffer(
                balances, expenses, age_primary, year, brokerage_account
            )
            transactions['traditional_to_brokerage'] = brokerage_txns['traditional_to_brokerage']
            transactions['brokerage_replenishment'] = brokerage_txns['brokerage_replenishment']
            dl.brokerage_replenishment.extend(brok_dl.brokerage_replenishment)
        else:
            # Brokerage maintained its buffer through optimized routing
            transactions['traditional_to_brokerage'] = 0.0
            transactions['brokerage_replenishment'] = 0.0
        
    else:
        # Normal flow - Brokerage can handle it
        logger.info(f"Year {year}: Normal routing - Brokerage sufficient for cash and buffer")
        
        # Step 2a: Replenish cash buffer (after expenses paid)
        balances, cash_txns, cash_dl = replenish_cash_buffer(
            balances, expenses, age_primary, year,
            cash_target_override=cash_target_override,
            brokerage_account=brokerage_account
        )
        transactions['brokerage_to_cash'] = cash_txns['brokerage_to_cash']
        transactions['traditional_to_cash'] = cash_txns['traditional_to_cash']
        transactions['roth_to_cash'] = cash_txns['roth_to_cash']
        transactions['cash_replenishment'] = cash_txns['cash_replenishment']
        transactions['brokerage_ltcg'] = cash_txns.get('brokerage_ltcg', 0.0)
        dl.cash_replenishment.extend(cash_dl.cash_replenishment)

        # Step 2b: Replenish brokerage buffer
        balances, brokerage_txns, brok_dl = replenish_brokerage_buffer(
            balances, expenses, age_primary, year, brokerage_account
        )
        transactions['traditional_to_brokerage'] = brokerage_txns['traditional_to_brokerage']
        transactions['brokerage_replenishment'] = brokerage_txns['brokerage_replenishment']
        dl.brokerage_replenishment.extend(brok_dl.brokerage_replenishment)

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

    return balances, transactions, dl


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


def _get_retirement_years() -> tuple:
    """Return (earliest, latest) calendar year either person is expected to retire."""
    cfg = get_config_manager()
    p1 = int(cfg.get("personal_info", "person1_birth_date", "1965-01-01").split('-')[0]) + int(cfg.get("personal_info", "person1_retirement_age", 67))
    p2 = int(cfg.get("personal_info", "person2_birth_date", "1967-01-01").split('-')[0]) + int(cfg.get("personal_info", "person2_retirement_age", 62))
    return min(p1, p2), max(p1, p2)


def _get_earliest_retirement_year() -> int:
    """Return the earliest calendar year either person is expected to retire."""
    return _get_retirement_years()[0]


def _get_latest_retirement_year() -> int:
    """Return the latest calendar year either person is expected to retire.

    Stage 1 (Accumulation) and Stage 2 (Prep for Retirement) should remain
    active until the *last* earner retires.  Using the earliest retirement year
    caused a regression where the stages reverted to Stage 1 after the first
    person retired while the second was still working.
    """
    return _get_retirement_years()[1]


def _calculate_daf_for_year(age_primary: int, age_spouse: int, std_deduction: float,
                           state_tax: float = 0.0, property_tax: float = 0.0,
                           brokerage_balance: float = 0.0) -> Tuple[float, float]:
    """Calculate DAF contribution and tax deduction excess for a given year/age.

    Uses the eldest person's age for DAF contribution timing and stops contributions
    once the eldest reaches QCD eligibility age (70.5 years old).

    Bundling strategy:
      - First year: daf_initial_contribution (if configured)
      - Subsequent years: bundle based on daf_annual_contribution from config
      - Bundle interval calculated from config or defaults to every 2 years
      - Stops at QCD eligibility age (70.5) or daf_contribution_end_age, whichever is earlier

    When calculating itemized deductions, includes SALT (State And Local Taxes) which consists
    of state income tax and property tax, capped at $10,000 per IRS rules.

    Args:
        age_primary: Primary person's age
        age_spouse: Spouse's age (0 if single)
        std_deduction: Standard deduction amount for the year
        state_tax: State income tax paid (default 0.0)
        property_tax: Property tax paid (default 0.0)
        brokerage_balance: Current brokerage account balance (default 0.0)

    Returns:
        (daf_contribution, daf_tax_deduction_excess)
        daf_contribution          — amount contributed to DAF this year (0 in non-bundle years)
        daf_tax_deduction_excess  — amount by which total itemized deductions (DAF + SALT)
                                    exceed the standard deduction (i.e. the incremental
                                    itemized deduction benefit). This is subtracted from
                                    taxable income in bundle years.
    """
    # QCD (Qualified Charitable Distribution) eligibility age
    QCD_AGE = 70.5
    
    try:
        config_mgr = get_config_manager()
        has_daf = config_mgr.get("charitable_giving", "has_daf", False)
        annual_giving = float(config_mgr.get("charitable_giving", "annual_charitable_giving", 0))
        daf_start_age = int(config_mgr.get("charitable_giving", "daf_contribution_start_age", 60))
        daf_end_age = int(config_mgr.get("charitable_giving", "daf_contribution_end_age", 75))
        daf_initial = float(config_mgr.get("charitable_giving", "daf_initial_contribution", 0))
        daf_annual = float(config_mgr.get("charitable_giving", "daf_annual_contribution", 100000))
        
        # Get bundle interval from tax_strategy if available, otherwise calculate
        bundle_interval = config_mgr.get("tax_strategy", "daf_bundle_interval_years", None)
        if bundle_interval is None:
            # Calculate bundle interval: floor(std_ded / giving) + 1, capped [2, 5]
            bundle_interval = max(2, min(int(std_deduction // annual_giving) + 1, 5)) if annual_giving > 0 else 2
        else:
            bundle_interval = int(bundle_interval)
            
        # Get bundle contribution amount from tax_strategy if available
        bundle_contribution = config_mgr.get("tax_strategy", "daf_bundle_contribution_amount", None)
        if bundle_contribution is None:
            bundle_contribution = daf_annual
        else:
            bundle_contribution = float(bundle_contribution)
            
    except Exception:
        return 0.0, 0.0

    # No DAF or no giving configured — guard before any division
    if not has_daf or annual_giving <= 0:
        return 0.0, 0.0

    # Use eldest person's age for DAF contribution timing
    eldest_age = max(age_primary, age_spouse) if age_spouse > 0 else age_primary
    
    # Stop DAF contributions once eldest reaches QCD eligibility age (70.5)
    # QCD allows direct charitable distributions from IRA, which is more tax-efficient
    if eldest_age >= QCD_AGE:
        logger.debug(f"No DAF contribution: eldest age {eldest_age:.1f} >= QCD age {QCD_AGE}")
        return 0.0, 0.0
    
    # Also respect the configured end age
    if eldest_age < daf_start_age or eldest_age > daf_end_age:
        return 0.0, 0.0
    
    years_into_window = eldest_age - daf_start_age

    # Check if this is a bundle year
    if years_into_window % bundle_interval != 0:
        return 0.0, 0.0

    # First year of the window: use initial contribution
    if years_into_window == 0 and daf_initial > 0:
        daf_contribution = daf_initial
        logger.debug(f"DAF initial contribution year (eldest age {eldest_age}): ${daf_contribution:,.0f}")
    else:
        # Subsequent bundle years: use configured bundle amount
        daf_contribution = bundle_contribution
        logger.debug(f"DAF bundle year (eldest age {eldest_age}): ${daf_contribution:,.0f}")

    # Check if brokerage has sufficient funds for DAF contribution
    if daf_contribution > brokerage_balance:
        logger.warning(
            f"Insufficient brokerage balance for DAF contribution: "
            f"${brokerage_balance:,.2f} < ${daf_contribution:,.0f}. "
            f"Skipping DAF contribution for eldest age {eldest_age}."
        )
        return 0.0, 0.0

    # Calculate SALT (State And Local Taxes) deduction, capped at $10,000 per IRS rules
    salt_deduction = min(10000.0, state_tax + property_tax)
    
    # Total itemized deductions = DAF contribution + SALT
    total_itemized = daf_contribution + salt_deduction
    
    # Tax deduction excess: amount by which itemized deductions exceed standard deduction
    # Only itemize if total itemized deductions exceed the standard deduction
    daf_tax_excess = max(0.0, total_itemized - std_deduction)

    logger.debug(
        f"DAF bundle year (eldest age {eldest_age}): "
        f"contribution=${daf_contribution:,.0f}, "
        f"SALT=${salt_deduction:,.0f} (state=${state_tax:,.0f}, property=${property_tax:,.0f}), "
        f"total itemized=${total_itemized:,.0f}, "
        f"tax excess above std_ded=${daf_tax_excess:,.0f} "
        f"(interval={bundle_interval} yrs)"
    )
    return daf_contribution, daf_tax_excess


def get_stage_specific_conversion_rate(stage_name: str) -> float:
    """
    Get the stage-specific maximum Roth conversion tax rate from configuration.
    
    Args:
        stage_name: The life stage name (e.g., "Stage 1: Accumulation")
    
    Returns:
        Maximum conversion rate as a decimal (e.g., 0.12 for 12%)
    """
    config_mgr = get_config_manager()
    
    # Map stage names to configuration keys
    stage_config_map = {
        "Stage 1: Accumulation": "stage_1_max_conversion_rate",
        "Stage 2: Prep for Retirement": "stage_2_max_conversion_rate",
        "Stage 3: Early Retirement": "stage_3_max_conversion_rate",
        "Stage 4: Medicare": "stage_4_max_conversion_rate",
        "Stage 5: Social Security": "stage_5_max_conversion_rate",
        "Stage 6: RMD": "stage_6_max_conversion_rate",
        "Stage 7: Surviving Spouse": "stage_7_max_conversion_rate",
    }
    
    # Get stage-specific rate, fall back to global default
    config_key = stage_config_map.get(stage_name)
    if config_key:
        rate_pct = config_mgr.get("tax_strategy", config_key, None)
        if rate_pct is not None:
            return float(rate_pct) / 100.0
    
    # Fall back to global default
    global_rate = config_mgr.get("tax_strategy", "max_roth_conversion_tax_rate", 12)
    return float(global_rate) / 100.0



class WithdrawalStrategyEngine:
    """
    Main engine for calculating withdrawal strategy across all life stages.
    
    Manages the brokerage account with actual cost basis tracking across
    all life stages, replacing the fixed 60/40 LTCG assumption.
    """
    
    def __init__(self):
        """Initialize the Withdrawal Strategy Engine with refactored stages."""
        # Get singleton dependency instances
        tax_calc = get_tax_calculator()
        acct_mgr = get_account_manager()
        
        # Create refactored life stages with dependency injection
        # Stage 7 (Surviving Spouse) is checked first as it takes precedence
        self.stages = [
            Stage7SurvivingSpouse(tax_calc, acct_mgr),
            Stage1Accumulation(tax_calc, acct_mgr),
            Stage2PrepForRetirement(tax_calc, acct_mgr),
            Stage3EarlyRetirement(tax_calc, acct_mgr),
            Stage4Medicare(tax_calc, acct_mgr),
            Stage5SocialSecurity(tax_calc, acct_mgr),
            Stage6RMD(tax_calc, acct_mgr)
        ]
        self.brokerage_account: Optional[BrokerageAccount] = None
        
        logger.info("Withdrawal Strategy Engine initialized with 7 refactored life stages")
    
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
                                     person1_name: Optional[str] = None,
                                     person2_name: Optional[str] = None,
                                     **kwargs) -> pd.DataFrame:
        """
        Calculate withdrawal strategy for multiple years
        
        Args:
            start_year: Starting year
            end_year: Ending year (inclusive)
            initial_balances: Starting portfolio balances
            initial_expenses: Initial annual expenses
            person1_name: Name of person 1 (defaults to config value)
            person2_name: Name of person 2 (defaults to config value)
            initial_balances: Starting portfolio balances
            initial_expenses: Starting annual expenses
            person1_name: Name of primary person
            person2_name: Name of spouse
            **kwargs: Additional parameters (growth_rate, expense_inflation_rate, etc.)
        
        Returns:
            DataFrame with yearly strategies
        """
        logger.info(f"Calculating strategy from {start_year} to {end_year}")
        
        # Get person names from config if not provided
        if person1_name is None or person2_name is None:
            config_mgr = get_config_manager()
            if person1_name is None:
                person1_name = config_mgr.get("personal_info", "person1_name", "Person1")
            if person2_name is None:
                person2_name = config_mgr.get("personal_info", "person2_name", "Person2")
        
        logger.info(f"Using person names: {person1_name}, {person2_name}")
        
        results = []
        balances = initial_balances
        expenses = initial_expenses

        # Get parameters
        growth_rate = kwargs.get('growth_rate', 1.07)
        
        # Initialize brokerage account with cost basis tracking
        # Estimate years invested based on user's age (conservative: assume 10 years)
        estimated_years_invested = kwargs.get('brokerage_years_invested', 10)
        self.brokerage_account = initialize_brokerage_account(
            initial_balance=initial_balances.taxable,
            current_year=start_year,
            estimated_years_invested=estimated_years_invested,
            growth_rate=growth_rate
        )
        logger.info(f"Initialized brokerage account with cost basis tracking")
        summary = self.brokerage_account.get_summary()
        logger.info(f"  Initial LTCG ratio: {summary['ltcg_ratio']:.1%}")
        logger.info(f"  Initial basis ratio: {summary['basis_ratio']:.1%}")
        expense_inflation_rate = kwargs.get('expense_inflation_rate', 0.03)  # 3% inflation rate
        spending_decrease_rate = 0.01  # 1% annual decrease in spending
        ss_claiming_age = kwargs.get('ss_claiming_age', 67)
        
        # Track MAGI for IRMAA (2-year lookback)
        magi_history = {}
        
        for year in range(start_year, end_year + 1):
            # Get ages from config (calculate from birth year)
            config_mgr = get_config_manager()
            person1_birth_date = config_mgr.get("personal_info", "person1_birth_date", "1965-01-01")
            person1_birth_year = int(person1_birth_date.split('-')[0])
            age_primary = year - person1_birth_year
            
            person2_birth_date = config_mgr.get("personal_info", "person2_birth_date", "1967-01-01")
            person2_birth_year = int(person2_birth_date.split('-')[0])
            age_spouse = year - person2_birth_year
            
            # Calculate retirement years for both people
            config_mgr = get_config_manager()
            person1_retirement_age = config_mgr.get("personal_info", "person1_retirement_age", 67)
            person2_retirement_age = config_mgr.get("personal_info", "person2_retirement_age", 62)
            person1_retirement_year = person1_birth_year + person1_retirement_age
            person2_retirement_year = person2_birth_year + person2_retirement_age
            
            # Calculate wages from config - check each person's retirement status individually
            wages = 0
            person1_wages_this_year = 0
            person2_wages_this_year = 0
            
            person1_base_wages = config_mgr.get("income", "person1_annual_wages", 0)
            person2_base_wages = config_mgr.get("income", "person2_annual_wages", 0)
            wage_inflation_rate = config_mgr.get("income", "wage_inflation_rate", 3.0) / 100.0
            
            # Apply wage inflation from start_year to current year
            years_elapsed = year - start_year
            inflation_multiplier = (1 + wage_inflation_rate) ** years_elapsed
            
            # Check if person1 is still working (before their retirement year)
            if year < person1_retirement_year and person1_base_wages > 0:
                person1_wages_this_year = person1_base_wages * inflation_multiplier
            
            # Check if person2 is still working (before their retirement year)
            if year < person2_retirement_year and person2_base_wages > 0:
                person2_wages_this_year = person2_base_wages * inflation_multiplier
            
            # Total household wages
            wages = person1_wages_this_year + person2_wages_this_year
            
            if wages > 0:
                logger.info(f"Year {year} Wages: Person1=${person1_wages_this_year:,.2f} "
                          f"({'working' if person1_wages_this_year > 0 else 'retired'}), "
                          f"Person2=${person2_wages_this_year:,.2f} "
                          f"({'working' if person2_wages_this_year > 0 else 'retired'}), "
                          f"Total=${wages:,.2f} (inflation factor: {inflation_multiplier:.4f})")
            
            has_wages = wages > 0
            
            # Get SS benefits using dynamic calculator
            # Check each person's individual claiming age from config
            ss_benefits = 0
            try:
                # Get config for SSI settings
                config_mgr = get_config_manager()
                
                # Person 1 SSI calculation
                person1_birth_date = config_mgr.get("personal_info", "person1_birth_date", "1965-01-01")
                person1_birth_year = int(person1_birth_date.split('-')[0])
                person1_claiming_age = config_mgr.get("social_security", "person1_ssi_age", 70)
                person1_fra_benefit = config_mgr.get("social_security", "person1_ssi_amount", 0)
                
                ss_primary = 0
                if person1_fra_benefit > 0 and age_primary >= person1_claiming_age:
                    ss_primary = calculate_ssi_benefits_dynamic(
                        year=year,
                        person_name=person1_name or "Person 1",
                        birth_year=person1_birth_year,
                        claiming_age=person1_claiming_age,
                        fra_benefit=person1_fra_benefit,
                        cola_rate=kwargs.get('cola_rate', DEFAULT_COLA_RATE)
                    )
                
                # Person 2 SSI calculation
                person2_birth_date = config_mgr.get("personal_info", "person2_birth_date", "1967-01-01")
                person2_birth_year = int(person2_birth_date.split('-')[0])
                person2_claiming_age = config_mgr.get("social_security", "person2_ssi_age", 70)
                person2_fra_benefit = config_mgr.get("social_security", "person2_ssi_amount", 0)
                
                ss_spouse = 0
                if person2_fra_benefit > 0 and age_spouse >= person2_claiming_age:
                    ss_spouse = calculate_ssi_benefits_dynamic(
                        year=year,
                        person_name=person2_name or "Person 2",
                        birth_year=person2_birth_year,
                        claiming_age=person2_claiming_age,
                        fra_benefit=person2_fra_benefit,
                        cola_rate=kwargs.get('cola_rate', DEFAULT_COLA_RATE)
                    )
                
                # Convert monthly to annual and combine both persons
                ss_benefits = (ss_primary + ss_spouse) * 12
                
                # Log individual and combined benefits
                if ss_primary > 0 or ss_spouse > 0:
                    logger.info(f"Year {year} SSI Benefits: "
                              f"{person1_name or 'Person 1'}=${ss_primary:,.2f}/mo (age {age_primary}), "
                              f"{person2_name or 'Person 2'}=${ss_spouse:,.2f}/mo (age {age_spouse}), "
                              f"Combined Annual=${ss_benefits:,.2f}")
                
            except Exception as e:
                logger.warning(f"Could not calculate dynamic SS benefits for {year}: {e}")
                # Fallback: use zero if dynamic calculation fails
                ss_benefits = 0
                logger.warning(f"SSI calculation failed, using $0 for year {year}")
                try:
                    # Optional: Try CSV-based method as last resort
                    # Get claiming ages from config for fallback
                    config_mgr = get_config_manager()
                    person1_claiming_age = config_mgr.get("social_security", "person1_ssi_age", 70)
                    person2_claiming_age = config_mgr.get("social_security", "person2_ssi_age", 70)
                    
                    ss_primary = get_monthly_benefit(year, person1_name) if age_primary >= person1_claiming_age else 0
                    ss_spouse = get_monthly_benefit(year, person2_name) if age_spouse >= person2_claiming_age else 0
                    if ss_primary > 0 or ss_spouse > 0:
                        ss_benefits = (ss_primary + ss_spouse) * 12
                        logger.info(f"Using CSV fallback for SSI: ${ss_benefits:,.2f}")
                except Exception as e2:
                    logger.error(f"Both dynamic and CSV SSI calculation failed: {e2}")
            
            # Determine if has_ss for stage determination
            has_ss = ss_benefits > 0
            
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
            
            # Apply annual growth to brokerage account (at start of year, before transactions)
            if self.brokerage_account is not None and year > start_year:
                self.brokerage_account.apply_annual_growth(growth_rate, year)
            
            # Calculate strategy (add start_year for buffer ramp-up calculation)
            # Pass brokerage_account to stages for cost basis tracking
            strategy = stage.calculate_strategy(
                year=year,
                balances=balances,
                expenses=expenses,
                wages=wages,
                age_primary=age_primary,
                age_spouse=age_spouse,
                ss_benefits=ss_benefits,
                prior_magi=prior_magi,
                start_year=start_year,
                brokerage_account=self.brokerage_account,
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
            
            # Calculate age-adjusted expenses for next year
            # Import the age-adjustment function
            from calculations import calculate_household_age_adjusted_expenses
            from config import get_value_with_session_override
            
            # Get base expenses from config (without inflation)
            base_expenses = float(get_value_with_session_override(
                'financial_assumptions', 'expected_annual_expenses', 'EXPENSE',
                kwargs.get('initial_expenses', 120000)
            ))
            
            # Check if single person mode
            is_single = config_mgr.get("personal_info", "is_single_person", False)
            
            # Calculate next year's ages
            next_year_age_primary = age_primary + 1
            next_year_age_spouse = age_spouse + 1
            
            # Apply age-based adjustment to base expenses
            age_adjusted_base = calculate_household_age_adjusted_expenses(
                base_expenses,
                next_year_age_primary,
                next_year_age_spouse if not is_single else None,
                is_single
            )
            
            # Apply inflation to the age-adjusted base
            # Calculate years from start to get cumulative inflation
            years_from_start = (year + 1) - start_year
            inflation_multiplier = (1 + expense_inflation_rate) ** years_from_start
            expenses = age_adjusted_base * inflation_multiplier
            
            logger.debug(
                f"Year {year+1} expense calculation: "
                f"base=${base_expenses:,.2f}, "
                f"age_adjusted=${age_adjusted_base:,.2f} "
                f"(ages {next_year_age_primary}/{next_year_age_spouse}), "
                f"inflation_mult={inflation_multiplier:.4f}, "
                f"final=${expenses:,.2f}"
            )
            
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
        """Convert list of YearlyStrategy objects to DataFrame with account movements"""
        data = []
        for idx, s in enumerate(strategies):
            try:
                logger.info(f"Converting strategy {idx+1}/{len(strategies)}: Year {s.year}, "
                           f"Age primary={s.age_primary} (type={type(s.age_primary).__name__}), "
                           f"Age spouse={s.age_spouse} (type={type(s.age_spouse).__name__})")
                
                # Ensure ages are integers
                age_primary_int = int(s.age_primary) if s.age_primary is not None else 0
                age_spouse_int = int(s.age_spouse) if s.age_spouse is not None else 0
                age_str = f"{age_primary_int}/{age_spouse_int}"
                
                data.append({
                    'Year': s.year,
                    'Age': age_str,
                    'Stage': s.stage,
                # Income sources (in requested order)
                'Wages': s.wages,
                'SS Benefits': s.ss_benefits,
                'Traditional Withdrawal': s.traditional_withdrawal,
                'Roth Conversion': s.roth_conversion,
                # Expenses and costs
                'Expenses': s.expenses,
                'Healthcare Cost': s.healthcare_costs if s.healthcare_costs > 0 else (s.irmaa_penalty + s.aca_premium),
                'IRMAA Penalty': s.irmaa_penalty,
                'ACA Premium': s.aca_premium,
                'DAF Contribution': s.daf_contribution,
                'AGI': s.agi,
                'MAGI': s.magi,
                'Federal Tax': s.federal_tax,
                'State Tax': s.state_tax,
                'Cash Balance': s.balances.cash,
                # Additional withdrawal details
                'RMD': s.rmd_amount,
                'Taxable Withdrawal': s.taxable_withdrawal,
                'Roth Withdrawal': s.roth_withdrawal,
                'LTCG Harvested': s.ltcg_harvested,
                # Cost basis tracking
                'Basis Returned': s.basis_returned,
                'Brokerage LTCG Ratio': s.brokerage_ltcg_ratio,
                'Brokerage Basis Ratio': s.brokerage_basis_ratio,
                # Account movements (fund transfers between accounts) - using shorter names with line breaks
                'Trad→\nCash': s.traditional_to_cash,
                'Trad→\nBrok': s.traditional_to_brokerage,
                'Trad→\nRoth': s.conversion_executed,
                'Brok→\nCash': s.brokerage_to_cash,
                'Roth→\nCash': s.roth_to_cash,
                'Roth→\nBrok': s.roth_to_brokerage,
                'Cash\nReplen': s.cash_replenishment,
                'Brok\nReplen': s.brokerage_replenishment,
                # Accumulation-phase contributions (non-zero only in Stage 1 & 2)
                'Wages→\nPayroll': s.payroll_tax,
                'Wages→\nTrad': s.wages_to_trad,
                'Wages→\nRoth': s.wages_to_roth,
                'Cash→\nRoth': s.cash_to_roth,
                'Cash→\nBrok': s.cash_to_brokerage,
                # Account balances
                'Taxable Balance': s.balances.taxable,
                'Traditional Balance': s.balances.traditional,
                'Roth Balance': s.balances.roth,
                    'DAF Balance': s.balances.daf,
                    'Total Portfolio': s.balances.total(),
                    'Decision Log': getattr(s, 'decision_log', None),
                })
            except Exception as e:
                logger.error(f"Error converting strategy {idx+1} (Year {s.year}): {e}", exc_info=True)
                raise
        
        return pd.DataFrame(data)


def build_withdrawal_strategy_display(start_year: Optional[int] = None,
                                      end_year: Optional[int] = None,
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
            cash_balance = float(summary_df[summary_df['account_type'] == 'Savings']['market_value'].sum())
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
    # Log first 4 years of data at INFO level for planning_app.py visibility
    # Get initial expenses from session state or use default
    # Get initial expenses from session state or fall back to config
    from config import get_value_with_session_override
    try:
        initial_expenses = float(get_value_with_session_override('financial_assumptions', 'expected_annual_expenses', 'EXPENSE', kwargs.get('initial_expenses', 120000)))
    except (ImportError, AttributeError, KeyError) as e:
        logger.debug(f'Using default expenses (Streamlit not available): {e}')
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
    
    return strategy_df, cast(pd.DataFrame, balances_df)


def build_accumulation_strategy_display(start_year: Optional[int] = None,
                                        end_year: Optional[int] = None,
                                        **kwargs) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build accumulation (pre-retirement) strategy display.

    Runs the same WithdrawalStrategyEngine as the withdrawal display but scopes
    the projection to the years *before* the earliest retirement date so only
    Stage 1 (Accumulation) and Stage 2 (Prep for Retirement) rows appear.

    Args:
        start_year: Starting year (defaults to current year).
        end_year:   Ending year (defaults to the year before the earliest
                    retirement date, or start_year + 10 if config unavailable).
        **kwargs:   Forwarded to the engine (growth_rate, expense_inflation_rate, …).

    Returns:
        Tuple of (strategy_df, balances_df) — same column schema as
        build_withdrawal_strategy_display().
    """
    if start_year is None:
        start_year = datetime.now().year

    if end_year is None:
        try:
            config_mgr = get_config_manager()
            p1_birth_year = int(config_mgr.get("personal_info", "person1_birth_date", "1965-01-01").split('-')[0])
            p1_ret_age = config_mgr.get("personal_info", "person1_retirement_age", 67)
            p2_birth_year = int(config_mgr.get("personal_info", "person2_birth_date", "1967-01-01").split('-')[0])
            p2_ret_age = config_mgr.get("personal_info", "person2_retirement_age", 62)
            # Use LATEST retirement year so accumulation phase continues until last person retires
            # This is critical for age-gap marriages where one spouse retires before the other
            latest_retirement = max(p1_birth_year + p1_ret_age, p2_birth_year + p2_ret_age)
            # Project up to (but not including) the retirement year of the last person
            end_year = max(start_year, latest_retirement - 1)
        except Exception:
            end_year = start_year + 10

    logger.info(f"Building accumulation strategy display: {start_year}-{end_year}")

    # Load current portfolio balances (same logic as withdrawal display)
    try:
        current_month = datetime.now().month
        detailed_df, summary_df = get_networth_by_month(current_month, start_year)

        if summary_df.empty:
            logger.warning("No portfolio data found for accumulation display, using defaults")
            initial_balances = PortfolioBalances(
                cash=50_000, taxable=200_000, traditional=300_000, roth=100_000, daf=0
            )
        else:
            initial_balances = PortfolioBalances(
                cash=float(summary_df[summary_df['account_type'] == 'Savings']['market_value'].sum()),
                taxable=float(summary_df[summary_df['account_type'] == 'Brokerage']['market_value'].sum()),
                traditional=float(summary_df[summary_df['account_type'] == 'Traditional']['market_value'].sum()),
                roth=float(summary_df[summary_df['account_type'] == 'Roth']['market_value'].sum()),
                daf=0
            )
    except Exception as e:
        logger.error(f"Error loading portfolio data for accumulation display: {e}")
        initial_balances = PortfolioBalances(
            cash=50_000, taxable=200_000, traditional=300_000, roth=100_000, daf=0
        )

    # Load initial expenses
    from config import get_value_with_session_override
    try:
        initial_expenses = float(get_value_with_session_override(
            'financial_assumptions', 'expected_annual_expenses', 'EXPENSE',
            kwargs.get('initial_expenses', 120_000)
        ))
    except (ImportError, AttributeError, KeyError) as e:
        logger.debug(f"Using default expenses for accumulation display: {e}")
        initial_expenses = kwargs.get('initial_expenses', 120_000)

    kwargs_filtered = {k: v for k, v in kwargs.items() if k not in ['initial_balances', 'initial_expenses']}

    logger.info(f"Creating WithdrawalStrategyEngine for accumulation display")
    engine = WithdrawalStrategyEngine()
    
    logger.info(f"Calculating multi-year strategy from {start_year} to {end_year}")
    try:
        strategy_df = engine.calculate_multi_year_strategy(
            start_year=start_year,
            end_year=end_year,
            initial_balances=initial_balances,
            initial_expenses=initial_expenses,
            **kwargs_filtered
        )
        logger.info(f"Strategy calculation complete, {len(strategy_df)} rows returned")
    except Exception as e:
        logger.error(f"Error in calculate_multi_year_strategy: {e}", exc_info=True)
        raise

    # Filter to accumulation stages only (belt-and-suspenders guard)
    logger.info("Filtering to accumulation stages only")
    accum_stages = {"Stage 1: Accumulation", "Stage 2: Prep for Retirement"}
    if not strategy_df.empty and 'Stage' in strategy_df.columns:
        logger.info(f"Stages present: {strategy_df['Stage'].unique()}")
        strategy_df = strategy_df[strategy_df['Stage'].isin(list(accum_stages))].reset_index(drop=True)
        logger.info(f"After filtering: {len(strategy_df)} rows")

    logger.info("Creating balances DataFrame")
    try:
        balances_df = strategy_df[[
            'Year', 'Cash Balance', 'Taxable Balance',
            'Traditional Balance', 'Roth Balance', 'DAF Balance', 'Total Portfolio'
        ]].copy()
        logger.info(f"Balances DataFrame created with {len(balances_df)} rows")
    except Exception as e:
        logger.error(f"Error creating balances DataFrame: {e}", exc_info=True)
        raise

    logger.info(f"Accumulation strategy: {len(strategy_df)} years calculated")

    return cast(pd.DataFrame, strategy_df), cast(pd.DataFrame, balances_df)


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


# Default configuration shared across all scenarios.
# Wrapped in MappingProxyType to prevent accidental mutation; the dict-unpack
# syntax ({**_DEFAULT_SCENARIO_CONFIG, **overrides}) works identically.
_DEFAULT_SCENARIO_CONFIG: types.MappingProxyType = types.MappingProxyType({
    "start_year": 2026,
    "end_year": 2050,
    "person1_name": "Tom",
    "person2_name": "Sarah",
    "growth_rate": 1.07,
    "expense_inflation": 1.02,
    "ss_claiming_age": 67,
    "retirement_year": 2026,
    "has_wages": False
})


# Scenario-specific configuration overrides
# Each scenario overrides specific values from _DEFAULT_SCENARIO_CONFIG
_SCENARIO_OVERRIDES = {
    ScenarioType.DEFAULT: {
        # Default retirement scenario with moderate portfolio
        # Features:
        # - Moderate portfolio size (~$1.1M total)
        # - Standard retirement age (67)
        # - Deflation scenario (0.993 expense inflation)
        "initial_balances": PortfolioBalances(
            cash=55000,
            taxable=225000,
            traditional=670000,
            roth=168000,
            daf=0
        ),
        "initial_expenses": 120000,
        "expense_inflation": 0.993,  # Override base: deflation scenario
    },
    ScenarioType.EARLY_RETIRE: {
        # Early retirement scenario with larger portfolio and delayed Social Security
        # Features:
        # - Larger portfolio (~$1.75M total)
        # - Delayed SS claiming to age 70 for higher benefits
        # - Includes DAF for charitable giving
        "initial_balances": PortfolioBalances(
            cash=100000,
            taxable=400000,
            traditional=1000000,
            roth=200000,
            daf=50000
        ),
        "initial_expenses": 100000,
        "ss_claiming_age": 70,  # Delay SS for higher benefits
    },
    ScenarioType.HIGH_INCOME: {
        # High income scenario with large portfolio and higher growth assumptions
        # Features:
        # - Large portfolio (~$3.8M total)
        # - Higher growth rate (8% vs 7%)
        # - Higher expense inflation (2.5% vs 2%)
        # - Substantial DAF for charitable giving
        "initial_balances": PortfolioBalances(
            cash=200000,
            taxable=1000000,
            traditional=2000000,
            roth=500000,
            daf=100000
        ),
        "initial_expenses": 200000,
        "growth_rate": 1.08,  # Override base: higher growth
        "expense_inflation": 1.025,  # Override base: higher inflation
    },
}

# Fail fast at import time if a ScenarioType member has no entry in
# _SCENARIO_OVERRIDES.  This converts a silent runtime fallback into a loud,
# early error that is caught during development and CI before it can silently
# return wrong data in production.
_missing = set(ScenarioType) - set(_SCENARIO_OVERRIDES)
if _missing:
    raise RuntimeError(
        f"Missing _SCENARIO_OVERRIDES entries for: {_missing}"
    )


def _resolve_scenario_key(scenario_name: Union[str, ScenarioType]) -> ScenarioType:
    """Resolve a scenario name or enum member to a validated :class:`ScenarioType` key.

    Accepts either a :class:`ScenarioType` member or its string value.  Unknown
    strings fall back to :attr:`ScenarioType.DEFAULT` with a ``WARNING`` log entry.
    All :class:`ScenarioType` members are guaranteed to be present in
    :data:`_SCENARIO_OVERRIDES` by the module-level guard above.

    Args:
        scenario_name: A :class:`ScenarioType` member or its string value
            (e.g. ``"default"``, ``"early_retire"``).

    Returns:
        A :class:`ScenarioType` member guaranteed to be present in
        :data:`_SCENARIO_OVERRIDES`.
    """
    if isinstance(scenario_name, ScenarioType):
        return scenario_name
    try:
        return ScenarioType(scenario_name)
    except ValueError:
        logger.warning("Unknown scenario '%s', using default", scenario_name)
        return ScenarioType.DEFAULT


@functools.lru_cache(maxsize=None)
def _build_scenario_config(key: ScenarioType) -> ScenarioConfig:
    """Build and cache a :class:`ScenarioConfig` for a validated *key*.

    Results are cached indefinitely because both :data:`_DEFAULT_SCENARIO_CONFIG`
    and :data:`_SCENARIO_OVERRIDES` are module-level constants that never change
    at runtime.  :class:`ScenarioConfig` is ``frozen=True``, so cached instances
    are safe to share across callers without risk of mutation.

    Args:
        key: A :class:`ScenarioType` member present in :data:`_SCENARIO_OVERRIDES`.

    Returns:
        An immutable :class:`ScenarioConfig` populated from the merged base and
        scenario-specific configuration.
    """
    return ScenarioConfig(**{**_DEFAULT_SCENARIO_CONFIG, **_SCENARIO_OVERRIDES[key]})


def create_example_scenario(scenario_name: Union[str, ScenarioType] = "default") -> ScenarioConfig:
    """
    Create example scenarios for testing withdrawal strategies

    This function provides pre-configured retirement scenarios with different
    portfolio sizes, expense levels, and assumptions. Each scenario can be
    used to test withdrawal strategies under various conditions.

    Args:
        scenario_name: Scenario identifier. Accepts a :class:`ScenarioType` enum
            member or its string value (e.g. ``"default"``, ``"early_retire"``,
            ``"high_income"``). Prefer the enum form for type safety. Unknown
            strings fall back to ``ScenarioType.DEFAULT`` with a warning.

    Returns:
        ScenarioConfig: Fully populated scenario configuration.
        See ``ScenarioConfig`` for field descriptions.

    Note:
        Results are cached via :func:`_build_scenario_config`; repeated calls
        with the same argument are O(1) after the first call.

    Example:
        >>> scenario = create_example_scenario(ScenarioType.DEFAULT)
        >>> scenario = create_example_scenario(ScenarioType.EARLY_RETIRE)
        >>> scenario = create_example_scenario("high_income")  # string form also accepted
        >>> config_dict = scenario.to_dict()  # Convert to dict if needed
    """
    return _build_scenario_config(_resolve_scenario_key(scenario_name))


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


def _format_currency(value: float) -> str:
    """Format currency values consistently"""
    return f"${value:,.0f}"


def _format_percentage(value: float) -> str:
    """Format percentage values consistently"""
    return f"{value:.1f}%"


def _build_overview_section(summary: Dict) -> List[str]:
    """Build overview section lines"""
    return [
        "\n📊 OVERVIEW",
        f"   Years Analyzed: {summary['total_years']}",
        f"   Initial Portfolio: {_format_currency(summary['initial_portfolio_value'])}",
        f"   Final Portfolio: {_format_currency(summary['final_portfolio_value'])}",
        f"   Portfolio Growth: {_format_currency(summary['portfolio_growth'])}"
    ]


def _build_life_stages_section(summary: Dict) -> List[str]:
    """Build life stages section lines"""
    lines = ["\n🎯 LIFE STAGES"]
    for stage, years in summary['stages'].items():
        lines.append(f"   {stage}: {years} years")
    return lines


def _build_roth_conversion_section(summary: Dict) -> List[str]:
    """Build Roth conversion section lines"""
    lines = [
        "\n💰 ROTH CONVERSION STRATEGY",
        f"   Total Conversions: {_format_currency(summary['total_roth_conversions'])}",
        f"   Years with Conversions: {summary['years_with_conversions']}"
    ]
    if summary['max_conversion_year']:
        lines.append(f"   Largest Conversion: {_format_currency(summary['max_conversion_amount'])} in {summary['max_conversion_year']}")
    lines.append(f"   Final Roth %: {_format_percentage(summary['roth_percentage_final'])}")
    return lines


def _build_taxes_costs_section(summary: Dict) -> List[str]:
    """Build taxes and costs section lines"""
    return [
        "\n💵 TAXES & COSTS",
        f"   Total Federal Taxes: {_format_currency(summary['total_taxes_paid'])}",
        f"   Total IRMAA Penalties: {_format_currency(summary['total_irmaa_penalties'])}",
        f"   Average Annual Expenses: {_format_currency(summary['avg_annual_expenses'])}"
    ]


def _build_income_sources_section(summary: Dict) -> List[str]:
    """Build income sources section lines"""
    return [
        "\n📈 INCOME SOURCES",
        f"   Total SS Benefits: {_format_currency(summary['total_ss_benefits'])}",
        f"   Total RMDs: {_format_currency(summary['total_rmd'])}"
    ]


def _build_year_summary_section(strategy_df: pd.DataFrame, first_n: int, last_n: int,
                                display_cols: Sequence[str]) -> List[str]:
    """Build year-by-year summary section lines"""
    lines = [
        "\n" + "="*80,
        f"YEAR-BY-YEAR SUMMARY (First {first_n} & Last {last_n} years)",
        "="*80,
        f"\nFirst {first_n} Years:",
        strategy_df[display_cols].head(first_n).to_string(index=False),
        f"\nLast {last_n} Years:",
        strategy_df[display_cols].tail(last_n).to_string(index=False)
    ]
    return lines


def _resolve_display_bounds(first_n: int, last_n: int, total_rows: int) -> tuple:
    """Validate and adjust first_n / last_n against the available row count.

    Args:
        first_n: Requested number of initial rows to display.
        last_n: Requested number of final rows to display.
        total_rows: Total rows available in the strategy DataFrame.

    Returns:
        Adjusted (first_n, last_n) tuple guaranteed to fit within total_rows.

    Raises:
        ValueError: If first_n or last_n are not positive integers.
    """
    if first_n < 1 or last_n < 1:
        raise ValueError("first_n and last_n must be positive integers")

    if total_rows == 0:
        return 0, 0

    if first_n + last_n > total_rows:
        logger.warning(
            f"Requested {first_n + last_n} rows but only {total_rows} available. "
            f"Adjusting to show all rows."
        )
        first_n = min(first_n, total_rows)
        last_n = min(last_n, total_rows - first_n)

    return first_n, last_n


def _report_lines(summary: Dict, strategy_df: pd.DataFrame,
                  first_n: int, last_n: int,
                  display_cols: Sequence[str]) -> Iterator[str]:
    """Yield each line of the strategy report without performing any I/O.

    Separating content construction from output makes the report content
    independently testable (``list(_report_lines(...))``) without capturing
    stdout, and avoids building an intermediate list in memory.

    Args:
        summary: Pre-calculated summary dict from generate_strategy_summary.
        strategy_df: DataFrame from calculate_multi_year_strategy.
        first_n: Number of initial years to include.
        last_n: Number of final years to include.
        display_cols: Column names to render in the year-by-year table.

    Yields:
        Individual report lines (without a trailing newline each).
    """
    yield "\n" + "=" * 80
    yield "RETIREMENT WITHDRAWAL STRATEGY REPORT"
    yield "=" * 80

    yield from _build_overview_section(summary)
    yield from _build_life_stages_section(summary)
    yield from _build_roth_conversion_section(summary)
    yield from _build_taxes_costs_section(summary)
    yield from _build_income_sources_section(summary)
    yield from _build_year_summary_section(strategy_df, first_n, last_n, display_cols)


def print_strategy_report(strategy_df: pd.DataFrame, summary: Optional[Dict] = None,
                          first_n: int = 10, last_n: int = 5,
                          display_cols: Optional[tuple] = None) -> None:
    """
    Print a formatted report of the withdrawal strategy.

    Args:
        strategy_df: DataFrame from calculate_multi_year_strategy.
        summary: Optional pre-calculated summary dict.
        first_n: Number of initial years to display (default: 10).
        last_n: Number of final years to display (default: 5).
        display_cols: Columns to display in year summary.
            Defaults to _REPORT_DEFAULT_DISPLAY_COLS.

    Raises:
        ValueError: If first_n or last_n are not positive integers.
    """
    first_n, last_n = _resolve_display_bounds(first_n, last_n, len(strategy_df))

    if summary is None:
        summary = generate_strategy_summary(strategy_df)

    if display_cols is None:
        display_cols = _REPORT_DEFAULT_DISPLAY_COLS

    print("\n".join(_report_lines(summary, strategy_df, first_n, last_n, display_cols)))
    print("\n" + "=" * 80 + "\n")


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
    print(f"Starting Year: {scenario.start_year}")
    print(f"Ending Year: {scenario.end_year}")
    print(f"Initial Portfolio: ${scenario.initial_balances.total():,.0f}")
    print(f"Annual Expenses: ${scenario.initial_expenses:,.0f}")
    
    # Calculate strategy
    strategy_df, balances_df = build_withdrawal_strategy_display(**scenario.to_dict())
    
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
