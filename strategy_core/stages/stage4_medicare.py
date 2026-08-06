"""
Stage 4: Medicare

Refactored implementation using BaseLifeStageStrategy with dependency injection.
On Medicare, optimizing for IRMAA while continuing Roth conversions.
"""

import logging
from typing import Any, Optional
from datetime import datetime

from ..base_strategy import BaseLifeStageStrategy
from ..interfaces import ITaxCalculator, IAccountManager
from ..models import PortfolioBalances, YearlyStrategy
from ..agi_calculator import AGICalculator
from ..january_bracket_fill_strategy import JanuaryBracketFillStrategy
from .stage6_rmd import get_rmd_age

logger = logging.getLogger(__name__)

# Constants
MEDICARE_AGE = 65


class Stage4Medicare(BaseLifeStageStrategy):
    """
    Stage 4: Medicare Stage (Pre-SS, Pre-RMD)
    
    - On Medicare, optimize for IRMAA (2-year lookback)
    - Continue Roth conversions but watch IRMAA thresholds
    - Balance conversions vs IRMAA penalties
    - Use BETR with higher expected future rate (RMDs + SS coming)
    - Maintain cash and taxable buffers
    - Standard deduction optimization (90% target)
    """
    
    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """
        Initialize Stage 4 Medicare strategy.
        
        Args:
            tax_calculator: Tax calculator for tax computations
            account_manager: Account manager for withdrawals/conversions
        """
        super().__init__(
            name="Stage 4: Medicare",
            description="On Medicare, optimizing for IRMAA while continuing Roth conversions",
            tax_calculator=tax_calculator,
            account_manager=account_manager
        )
    
    def applies(
        self,
        age_primary: int,
        age_spouse: int,
        year: int,
        has_wages: bool,
        has_ss: bool
    ) -> bool:
        """
        Applies when on Medicare but before SS and RMDs.
        
        Uses the OLDER spouse's age for RMD threshold to ensure tax strategy
        is driven by the person closest to RMD age (more conservative approach).
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            True if this stage applies
        """
        older_age = max(age_primary, age_spouse)
        # RMD age depends on birth year (SECURE 2.0): 73 if born 1951–1959, 75 if born 1960+
        birth_year_primary = year - age_primary
        birth_year_spouse = year - age_spouse
        rmd_age = get_rmd_age(max(birth_year_primary, birth_year_spouse))  # older person drives threshold
        return (
            not has_wages and
            not has_ss and
            (age_primary >= MEDICARE_AGE or age_spouse >= MEDICARE_AGE) and
            older_age < rmd_age
        )
    
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate Medicare stage strategy optimizing for IRMAA.
        
        Strategy:
        1. Calculate IRMAA penalty based on prior year MAGI (2-year lookback)
        2. Determine IRMAA headroom to next bracket
        3. Calculate anticipated buffer needs
        4. Use BETR to optimize Roth conversion with IRMAA constraints
        5. Apply DAF optimization if applicable
        6. Execute account rebalancing
        7. Ensure 90% standard deduction target met
        8. Calculate final taxes with actual withdrawals
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            **kwargs: Additional parameters including:
                - age_primary: Primary person's age
                - age_spouse: Spouse's age
                - prior_magi: MAGI from 2 years prior (for IRMAA)
                - filing_status: Tax filing status
                - state: State for tax calculation
                - max_conversion_rate: Maximum tax rate for conversions
                - growth_rate: Annual portfolio growth rate
                - brokerage_account: BrokerageAccount instance
                - start_year: First year of retirement (for buffer ramp-up)
                
        Returns:
            YearlyStrategy with all calculations
        """
        # Validate dependencies
        self._validate_dependencies()
        
        # Extract parameters
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        prior_magi = kwargs.get('prior_magi', 0.0)
        filing_status = kwargs.get('filing_status', 'married_filing_jointly')
        state = kwargs.get('state', 'PA')
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        growth_rate = kwargs.get('growth_rate', 1.07)
        brokerage_account = kwargs.get('brokerage_account')
        start_year = kwargs.get('start_year', year)
        
        logger.debug(
            f"Stage 4 calculation for year {year}, prior MAGI=${prior_magi:,.2f}"
        )
        
        # Create base strategy object
        strategy = self._create_yearly_strategy(
            year, age_primary, age_spouse, balances
        )
        
        # Get standard deduction (using direct import like Stage 3)
        std_deduction = self._get_standard_deduction(
            filing_status, year, age_primary, age_spouse
        )
        
        # Calculate minimum ordinary income target (90% of standard deduction)
        min_ordinary_income_target = std_deduction * 0.90
        
        # Calculate IRMAA penalty and headroom
        irmaa_penalty, irmaa_headroom, people_on_medicare, next_irmaa_threshold = (
            self._calculate_irmaa_metrics(
                strategy, prior_magi, age_primary, age_spouse, year, filing_status
            )
        )
        
        # Calculate ACA premium (may still apply if under 65)
        aca_premium = self._calculate_aca_premium(
            strategy, year, age_primary, age_spouse
        )

        # Calculate full healthcare costs (Medicare + IRMAA + Medigap + OOP + LTC)
        # irmaa_penalty and aca_premium above are kept for rebalancing/conversion logic;
        # healthcare_total is the comprehensive figure stored on the strategy for reporting.
        try:
            from strategy import calculate_total_healthcare_costs, get_health_status_from_config
            _health_status = get_health_status_from_config()
            healthcare_total, _hc_breakdown = calculate_total_healthcare_costs(
                age_primary=age_primary,
                age_spouse=age_spouse,
                magi_two_years_ago=prior_magi,
                year=year,
                filing_status=filing_status,
                health_status=_health_status,
                has_medigap=True
            )
            logger.info(f"Stage 4: Total healthcare costs=${healthcare_total:,.2f} "
                        f"(IRMAA=${irmaa_penalty:,.2f}, ACA=${aca_premium:,.2f}, "
                        f"health_status={_health_status})")
        except Exception as e:
            logger.warning(f"Stage 4: Could not calculate full healthcare costs, falling back: {e}")
            healthcare_total = irmaa_penalty + aca_premium

        # Calculate anticipated buffer needs (lookahead)
        anticipated_needs = self._calculate_anticipated_buffer_needs(
            strategy,
            balances,
            expenses,
            age_primary,
            irmaa_penalty,
            aca_premium,
            brokerage_account,
            start_year,
            year
        )
        
        # Validate anticipated_needs is a dict
        if not isinstance(anticipated_needs, dict):
            logger.error(f"Stage 4: anticipated_needs is not a dict after _calculate_anticipated_buffer_needs: "
                        f"type={type(anticipated_needs)}, value={anticipated_needs}")
            anticipated_needs = {
                'total_traditional_need': 0.0,
                'traditional_to_cash': 0.0,
                'traditional_to_brokerage': 0.0,
                'estimated_ltcg': 0.0
            }
        
        # ── PHASE 1: FUND SPENDING ─────────────────────────────────────────
        # Use January strategy to determine spending shortfall and Traditional→Cash withdrawal
        _jan_plan = self._plan_january_bracket_fill_withdrawal(
            year=year,
            pnc_savings_balance=balances.cash,
            annual_expenses=expenses,
            aca_premium=aca_premium,
            age_primary=age_primary,
            age_spouse=age_spouse,
            filing_status=filing_status,
        )

        # Extract spending withdrawal from January plan (shortfall only, no conversion)
        _jan_spending_withdrawal = 0.0
        if _jan_plan is not None:
            _jan_spending_withdrawal = _jan_plan['pnc_shortfall']
            self._log_decision(
                strategy,
                'tax_strategy',
                'January Strategy - Spending Phase',
                f'Traditional withdrawal for spending: ${_jan_spending_withdrawal:,.0f}',
                f'PNC shortfall (spending + ACA) requires Traditional withdrawal of ${_jan_spending_withdrawal:,.0f} '
                f'to supplement existing cash.',
                spending_withdrawal=_jan_spending_withdrawal,
            )

        # ── PHASE 2: ROTH CONVERSIONS ─────────────────────────────────────
        # After spending is funded, calculate Roth conversion based on remaining bracket space
        # Use config max_conversion_rate and IRMAA thresholds (Stage 4 specific)
        available_for_conversion = max(
            0,
            balances.traditional - anticipated_needs['total_traditional_need'] - _jan_spending_withdrawal
        )
        
        # Calculate optimal Roth conversion using BETR with IRMAA constraints
        roth_conversion, optimal_amount = self._calculate_irmaa_aware_roth_conversion(
            strategy,
            available_for_conversion,
            anticipated_needs,
            irmaa_headroom,
            max_conversion_rate,
            age_primary,
            balances.taxable,
            growth_rate,
            year
        )
        
        if roth_conversion > 0:
            self._log_decision(
                strategy,
                'roth_conversion',
                'Roth Conversion - After Spending (IRMAA-Aware)',
                f'Roth conversion: ${roth_conversion:,.0f} at {max_conversion_rate:.0%}',
                f'After funding spending with ${_jan_spending_withdrawal:,.0f}, available bracket space '
                f'for Roth conversions up to {max_conversion_rate:.0%} bracket (IRMAA limit: ${irmaa_headroom:,.0f}) '
                f'is ${roth_conversion:,.0f}.',
                roth_conversion=roth_conversion,
            )
        
        # Calculate DAF contribution and optimization
        daf_contribution, daf_tax_excess = self._calculate_daf_optimization(
            strategy,
            age_primary,
            age_spouse,
            std_deduction,
            state,
            balances.taxable,
            year,
            filing_status
        )
        
        # Apply DAF enhancement to Roth conversion if applicable (respecting IRMAA)
        if daf_contribution > 0 and daf_tax_excess > 0 and roth_conversion > 0:
            additional_conversion = min(
                daf_tax_excess,
                available_for_conversion - roth_conversion,
                irmaa_headroom - roth_conversion if irmaa_headroom < float('inf') else float('inf')
            )
            if additional_conversion > 0:
                roth_conversion += additional_conversion
                self._log_daf_conversion_enhancement(
                    strategy,
                    daf_contribution,
                    daf_tax_excess,
                    additional_conversion,
                    roth_conversion,
                    irmaa_headroom
                )
        
        # Subtract DAF from balances before rebalancing
        # HIFO lot removal: donate highest-gain lots to DAF first
        balances_for_rebalance = self._apply_daf_contribution(
            balances, daf_contribution, year, brokerage_account
        )
        
        # Estimate preliminary tax before rebalancing
        preliminary_tax = self._estimate_preliminary_tax(
            expenses=expenses,
            roth_conversion=roth_conversion,
            anticipated_needs=anticipated_needs,
            irmaa_penalty=irmaa_penalty,
            aca_premium=aca_premium,
            filing_status=filing_status,
            state=state,
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            brokerage_account=brokerage_account
        )
        
        # ── PHASE 1 APPLIED: pull Traditional→Cash BEFORE rebalancing ─────
        # Apply spending withdrawal directly so rebalance_accounts sees pre-funded cash
        _jan_trad_to_cash = 0.0
        if _jan_spending_withdrawal > 0:
            # Apply spending withdrawal only (no conversion tax here)
            _jan_trad_to_cash = min(
                _jan_spending_withdrawal,
                balances_for_rebalance.traditional
            )
            if _jan_trad_to_cash > 0:
                balances_for_rebalance = PortfolioBalances(
                    cash=balances_for_rebalance.cash + _jan_trad_to_cash,
                    taxable=balances_for_rebalance.taxable,
                    traditional=balances_for_rebalance.traditional - _jan_trad_to_cash,
                    roth=balances_for_rebalance.roth,
                    daf=balances_for_rebalance.daf,
                    traditional_person1=balances_for_rebalance.traditional_person1,
                    traditional_person2=balances_for_rebalance.traditional_person2,
                )
                logger.info(
                    f"Year {year} Stage 4 [Phase 1 - Spending]: "
                    f"Traditional→Cash ${_jan_trad_to_cash:,.0f} "
                    f"(spending shortfall), "
                    f"Roth conversion Phase 2: ${roth_conversion:,.0f}"
                )
        
        # Execute account rebalancing with preliminary tax estimate
        new_balances, transactions = self._execute_rebalancing(
            strategy,
            balances_for_rebalance,
            expenses,
            roth_conversion,
            irmaa_penalty,
            aca_premium,
            preliminary_tax,
            year,
            age_primary,
            brokerage_account
        )
        
        # ── PHASE 1 RECORDED: merge January Traditional→Cash into transaction log ──
        # _execute_rebalancing only knows about transfers it made; add the pre-funded
        # spending withdrawal so the year-by-year report shows the correct amount.
        if _jan_trad_to_cash > 0:
            transactions['traditional_to_cash'] = (
                transactions.get('traditional_to_cash', 0.0) + _jan_trad_to_cash
            )
            transactions['cash_replenishment'] = (
                transactions.get('cash_replenishment', 0.0) + _jan_trad_to_cash
            )

        # Ensure 90% standard deduction target is met
        new_balances, transactions = self._ensure_standard_deduction_target(
            strategy,
            new_balances,
            transactions,
            roth_conversion,
            min_ordinary_income_target,
            std_deduction,
            year
        )
        
        # Calculate final AGI and taxes (returns updated balances with state tax deducted)
        new_balances = self._calculate_final_taxes(
            strategy,
            new_balances,
            transactions,
            roth_conversion,
            daf_contribution,
            daf_tax_excess,
            std_deduction,
            filing_status,
            state,
            year,
            expenses,
            age_primary=age_primary,
            age_spouse=age_spouse,
            daf_carryforward_prior=0.0,  # TODO: track across years
            property_tax=0.0  # TODO: add to config
        )
        
        # Deduct DAF contribution from Brokerage (HIFO lot removal) and credit DAF balance
        if daf_contribution > 0:
            try:
                from strategy import apply_daf_to_brokerage_account
                new_balances = apply_daf_to_brokerage_account(
                    new_balances, daf_contribution, year, brokerage_account
                )
            except ImportError:
                new_balances = PortfolioBalances(
                    cash=new_balances.cash,
                    taxable=new_balances.taxable - daf_contribution,
                    traditional=new_balances.traditional,
                    roth=new_balances.roth,
                    daf=new_balances.daf,
                )
            new_balances = PortfolioBalances(
                cash=new_balances.cash,
                taxable=new_balances.taxable,
                traditional=new_balances.traditional,
                roth=new_balances.roth,
                daf=new_balances.daf + daf_contribution,
            )
        
        # Apply growth to balances
        new_balances = PortfolioBalances(
            cash=new_balances.cash,
            taxable=new_balances.taxable * growth_rate,
            traditional=new_balances.traditional * growth_rate,
            roth=new_balances.roth * growth_rate,
            daf=new_balances.daf * growth_rate
        )

        # Deduct annual charitable grant from DAF (grants paid out each year)
        new_balances = self._deduct_daf_annual_grant(new_balances, year, start_year)

        # Update strategy with final values
        strategy.balances = new_balances
        strategy.roth_conversion = roth_conversion
        strategy.daf_contribution = daf_contribution
        strategy.irmaa_penalty = irmaa_penalty
        strategy.aca_premium = aca_premium
        strategy.healthcare_costs = healthcare_total  # Full costs: Medicare + IRMAA + Medigap + OOP
        strategy.hc_oop = getattr(_hc_breakdown, 'out_of_pocket', 0.0)
        
        # Set transaction tracking
        strategy.traditional_to_cash = transactions['traditional_to_cash']
        strategy.traditional_to_brokerage = transactions['traditional_to_brokerage']
        strategy.brokerage_to_cash = transactions['brokerage_to_cash']
        strategy.roth_to_cash = transactions['roth_to_cash']
        strategy.roth_to_brokerage = transactions['roth_to_brokerage']
        strategy.conversion_executed = transactions['conversion_executed']
        strategy.cash_replenishment = transactions['cash_replenishment']
        strategy.brokerage_replenishment = transactions['brokerage_replenishment']
        
        # Set cost basis tracking
        strategy.basis_returned = transactions.get('basis_returned', 0.0)
        strategy.brokerage_ltcg_ratio = transactions.get('brokerage_ltcg_ratio', 0.0)
        strategy.brokerage_basis_ratio = transactions.get('brokerage_basis_ratio', 0.0)
        
        logger.debug(
            f"Stage 4 complete: AGI=${strategy.agi:,.2f}, "
            f"Federal Tax=${strategy.federal_tax:,.2f}, "
            f"IRMAA=${irmaa_penalty:,.2f}, "
            f"Roth Conversion=${roth_conversion:,.2f}"
        )
        
        return strategy
    
    def _get_standard_deduction(
        self,
        filing_status: str,
        year: int,
        age_primary: int,
        age_spouse: int
    ) -> float:
        """Get standard deduction from load_data module."""
        # Normalize 'married' → 'married_filing_jointly' to match CSV data
        _fs = 'married_filing_jointly' if filing_status == 'married' else filing_status
        try:
            from load_data import get_std_deduction
            std_deduction_df = get_std_deduction(year, _fs)
            return float(std_deduction_df.iloc[0]['deduction'])
        except Exception as e:
            logger.warning(f"Could not get standard deduction: {e}, using default")
            return 29200.0  # 2024 MFJ default
    
    def _calculate_irmaa_metrics(
        self,
        strategy: YearlyStrategy,
        prior_magi: float,
        age_primary: int,
        age_spouse: int,
        year: int,
        filing_status: str = 'married_filing_jointly'
    ) -> tuple[float, float, int, float]:
        """
        Calculate IRMAA penalty and headroom to next bracket.
        
        Args:
            strategy: YearlyStrategy to log to
            prior_magi: MAGI from 2 years prior
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            filing_status: Tax filing status (for standard deduction lookup)
            
        Returns:
            Tuple of (irmaa_penalty, irmaa_headroom, people_on_medicare, next_threshold)
        """
        try:
            from load_data import get_medicare_costs
            from calculations import calculate_irmma_penalty
            import pandas as pd
            
            irmaa_brackets = get_medicare_costs(year)
            people_on_medicare = sum([
                age_primary >= MEDICARE_AGE,
                age_spouse >= MEDICARE_AGE
            ])
            
            irmaa_penalty = calculate_irmma_penalty(
                prior_magi, irmaa_brackets, people_on_medicare
            )
            
            # Find current bracket and next threshold
            next_irmaa_threshold = float('inf')
            for _, row in irmaa_brackets.iterrows():
                if row['lower'] <= prior_magi <= row['upper']:
                    # Find next bracket
                    next_brackets = irmaa_brackets[irmaa_brackets['lower'] > row['upper']]
                    if not next_brackets.empty:
                        next_irmaa_threshold = float(next_brackets.iloc[0]['lower'])
                    break
            
            # Calculate headroom (how much we can increase MAGI before hitting next bracket)
            std_deduction = self._get_standard_deduction(filing_status, year, age_primary, age_spouse)
            irmaa_headroom = next_irmaa_threshold - std_deduction
            
            logger.debug(
                f"IRMAA: penalty=${irmaa_penalty:,.2f}, "
                f"people={people_on_medicare}, "
                f"next_threshold=${next_irmaa_threshold:,.2f}, "
                f"headroom=${irmaa_headroom:,.2f}"
            )
            
            self._log_decision(
                strategy,
                'irmaa_decisions',
                'IRMAA Assessment',
                f'${irmaa_penalty:,.0f} penalty ({people_on_medicare} person(s) on Medicare)',
                'IRMAA is based on MAGI from 2 years prior. '
                'Roth conversions are capped at the IRMAA headroom to avoid crossing into the next bracket.',
                prior_magi=prior_magi,
                people_on_medicare=people_on_medicare,
                next_irmaa_threshold=next_irmaa_threshold if next_irmaa_threshold != float('inf') else 'None',
                irmaa_headroom=irmaa_headroom
            )
            
            return irmaa_penalty, irmaa_headroom, people_on_medicare, next_irmaa_threshold
            
        except Exception as e:
            logger.warning(f"IRMAA calculation failed: {e}")
            return 0.0, float('inf'), 0, float('inf')
    
    def _calculate_aca_premium(
        self,
        strategy: YearlyStrategy,
        year: int,
        age_primary: int,
        age_spouse: int
    ) -> float:
        """Calculate ACA premium (may still apply if under 65)."""
        try:
            from calculations import calculate_aca_premium_for_year
            aca_premium = calculate_aca_premium_for_year(year, age_primary, age_spouse)
            
            if aca_premium > 0:
                self._log_decision(
                    strategy,
                    'aca_decisions',
                    'ACA Premium',
                    f'${aca_premium:,.0f}/yr',
                    'ACA premium applies if either person is under 65 and not yet on Medicare.',
                    aca_premium=aca_premium
                )
            
            return aca_premium
        except ImportError:
            return 0.0
    
    def _calculate_anticipated_buffer_needs(
        self,
        strategy: YearlyStrategy,
        balances: PortfolioBalances,
        expenses: float,
        age_primary: int,
        irmaa_penalty: float,
        aca_premium: float,
        brokerage_account: Any,
        start_year: int,
        year: int
    ) -> dict:
        """Calculate anticipated buffer needs before conversion optimization."""
        try:
            from strategy import (
                calculate_cash_buffer_targets,
                calculate_buffer_ramp_up,
                calculate_anticipated_buffer_needs
            )
            
            cash_target, taxable_target = calculate_cash_buffer_targets(expenses)
            cash_need, taxable_need = calculate_buffer_ramp_up(
                year, start_year, cash_target, taxable_target,
                balances.cash, balances.taxable
            )
            
            anticipated_needs = calculate_anticipated_buffer_needs(
                balances=balances,
                expenses=expenses,
                age_primary=age_primary,
                federal_tax=0.0,  # Preliminary
                irmaa_penalty=irmaa_penalty,
                aca_premium=aca_premium,
                medical_costs=0.0,
                brokerage_account=brokerage_account
            )
            
            logger.info(f"Year {year}: Lookahead buffer analysis (Stage 4)")
            logger.info(f"  Traditional balance: ${balances.traditional:,.0f}")
            logger.info(f"  Anticipated buffer needs: ${anticipated_needs['total_traditional_need']:,.0f}")
            logger.info(f"    - Trad→Cash: ${anticipated_needs['traditional_to_cash']:,.0f}")
            logger.info(f"    - Trad→Brok: ${anticipated_needs['traditional_to_brokerage']:,.0f}")
            logger.info(f"    - Estimated LTCG: ${anticipated_needs.get('estimated_ltcg', 0):,.0f}")
            logger.info(f"  Available for conversion: ${max(0, balances.traditional - anticipated_needs['total_traditional_need']):,.0f}")
            
            self._log_decision(
                strategy,
                'roth_conversion',
                'Lookahead Buffer Analysis',
                f"Reserved ${anticipated_needs['total_traditional_need']:,.0f} for buffers",
                "Before optimizing Roth conversions, we anticipate how much Traditional will be needed "
                "to maintain cash and brokerage buffers. This prevents over-converting.",
                traditional_balance=balances.traditional,
                anticipated_trad_to_cash=anticipated_needs['traditional_to_cash'],
                anticipated_trad_to_brok=anticipated_needs['traditional_to_brokerage'],
                available_for_conversion=max(0, balances.traditional - anticipated_needs['total_traditional_need'])
            )
            
            return anticipated_needs
            
        except ImportError:
            logger.warning("Buffer strategy module not available")
            return {
                'total_traditional_need': 0.0,
                'traditional_to_cash': 0.0,
                'traditional_to_brokerage': 0.0,
                'estimated_ltcg': 0.0
            }
    
    def _calculate_irmaa_aware_roth_conversion(
        self,
        strategy: YearlyStrategy,
        available_for_conversion: float,
        anticipated_needs: dict,
        irmaa_headroom: float,
        max_conversion_rate: float,
        age_primary: int,
        taxable_balance: float,
        growth_rate: float,
        year: int
    ) -> tuple[float, float]:
        """
        Calculate optimal Roth conversion using BETR with IRMAA constraints.
        
        Returns:
            Tuple of (roth_conversion, optimal_amount_before_irmaa)
        """
        if available_for_conversion <= 0:
            self._log_decision(
                strategy,
                'roth_conversion',
                'Roth Conversion',
                'No conversion — insufficient balance',
                'All Traditional balance is needed for buffer maintenance.',
                available_balance=available_for_conversion
            )
            return 0.0, 0.0
        
        # Calculate current income
        current_income = (
            anticipated_needs['traditional_to_cash'] +
            anticipated_needs['traditional_to_brokerage'] +
            anticipated_needs.get('estimated_ltcg', 0.0)
        )
        
        # Get stage-specific conversion rate
        try:
            from calculations import get_stage_specific_conversion_rate, getNextHigherTaxRate, get_income_tax_brackets
            stage_max_rate = get_stage_specific_conversion_rate(self.name)
            
            # Use next higher rate as expected future rate (RMDs + SS coming)
            tax_brackets = get_income_tax_brackets(year)
            expected_future_rate = getNextHigherTaxRate(stage_max_rate, tax_brackets)
        except Exception as e:
            logger.warning(f"Could not determine tax rates: {e}")
            stage_max_rate = max_conversion_rate
            expected_future_rate = max_conversion_rate
        
        # Use BETR algorithm
        try:
            from betr_roth_conversion import optimize_conversion_amount, calculate_betr, BETRInputs
            
            optimal_amount, betr_results = optimize_conversion_amount(
                traditional_ira_balance=available_for_conversion,
                current_agi=current_income,
                target_tax_bracket=stage_max_rate,
                year=year,
                pay_from_taxable=True,
                taxable_account_balance=taxable_balance,
                years_to_withdrawal=(get_rmd_age(year - age_primary) - age_primary) if age_primary > 0 else 15,
                annual_return=growth_rate - 1.0,
                expected_future_rate=expected_future_rate
            )
            
            if optimal_amount <= 0:
                self._log_decision(
                    strategy,
                    'roth_conversion',
                    'Roth Conversion',
                    'No conversion — no bracket room',
                    'BETR optimizer found no room to convert within the target bracket.',
                    current_income=current_income,
                    target_bracket=stage_max_rate
                )
                return 0.0, 0.0
            
            # Check IRMAA impact
            if optimal_amount > irmaa_headroom:
                # Conversion would cross IRMAA threshold
                irmaa_safe_amount = max(0, irmaa_headroom)
                
                if irmaa_safe_amount > 0:
                    # Recalculate BETR with reduced amount
                    reduced_inputs = BETRInputs(
                        current_marginal_rate=stage_max_rate,
                        expected_future_rate=expected_future_rate,
                        conversion_amount=irmaa_safe_amount,
                        traditional_ira_balance=available_for_conversion,
                        pay_from_taxable=True,
                        taxable_account_balance=taxable_balance,
                        years_to_withdrawal=(get_rmd_age(year - age_primary) - age_primary) if age_primary > 0 else 15,
                        annual_return=growth_rate - 1.0
                    )
                    reduced_results = calculate_betr(reduced_inputs)
                    
                    if reduced_results.conversion_recommended:
                        logger.info(
                            f'BETR: {reduced_results.betr:.2%}, '
                            f'Converting ${irmaa_safe_amount:,.0f} (IRMAA-limited)'
                        )
                        
                        self._log_decision(
                            strategy,
                            'roth_conversion',
                            'Roth Conversion',
                            f'Convert ${irmaa_safe_amount:,.0f} (IRMAA-limited)',
                            'BETR algorithm recommended a larger conversion but it was capped at the IRMAA '
                            'headroom to avoid triggering a higher Medicare premium bracket next year.',
                            optimal_betr_amount=optimal_amount,
                            irmaa_headroom=irmaa_headroom,
                            conversion_executed=irmaa_safe_amount,
                            betr=reduced_results.betr
                        )
                        
                        return irmaa_safe_amount, optimal_amount
                    else:
                        logger.info(
                            f'BETR: {reduced_results.betr:.2%}, '
                            'Conversion not recommended even at IRMAA limit'
                        )
                        return 0.0, optimal_amount
                else:
                    logger.info("No conversion room due to IRMAA threshold")
                    return 0.0, optimal_amount
            else:
                # Conversion fits within IRMAA headroom
                if betr_results.conversion_recommended:
                    logger.info(
                        f'BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f}'
                    )
                    
                    self._log_decision(
                        strategy,
                        'roth_conversion',
                        'Roth Conversion',
                        f'Convert ${optimal_amount:,.0f}',
                        'BETR algorithm recommended this conversion amount. '
                        'It fits within the IRMAA headroom so no Medicare penalty increase is expected.',
                        irmaa_headroom=irmaa_headroom,
                        conversion_executed=optimal_amount,
                        betr=betr_results.betr
                    )
                    
                    return optimal_amount, optimal_amount
                else:
                    logger.info(
                        f'BETR: {betr_results.betr:.2%}, Conversion not recommended'
                    )
                    
                    self._log_decision(
                        strategy,
                        'roth_conversion',
                        'Roth Conversion',
                        'No conversion',
                        'Either BETR did not recommend a conversion at current rates, '
                        'there was no room within the IRMAA headroom, or the Traditional balance is zero.',
                        irmaa_headroom=irmaa_headroom,
                        traditional_balance=available_for_conversion
                    )
                    
                    return 0.0, optimal_amount
                    
        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to IRMAA-aware method")
            return self._calculate_fallback_conversion(
                available_for_conversion,
                current_income,
                irmaa_headroom,
                stage_max_rate,
                year
            ), 0.0
    
    def _estimate_preliminary_tax(
        self,
        expenses: float,
        roth_conversion: float,
        anticipated_needs: dict,
        irmaa_penalty: float,
        aca_premium: float,
        filing_status: str,
        state: str,
        year: int,
        age_primary: int,
        age_spouse: int,
        brokerage_account: Any
    ) -> float:
        """
        Estimate tax before rebalancing using anticipated withdrawals.
        
        This provides a close-enough estimate for buffer calculations.
        The difference between preliminary and final tax is typically < 5%.
        
        Args:
            expenses: Annual expenses
            roth_conversion: Roth conversion amount
            anticipated_needs: Dict with anticipated withdrawal needs
            irmaa_penalty: IRMAA penalty cost
            aca_premium: ACA premium cost
            filing_status: Tax filing status
            state: State for tax calculation
            year: Current year
            age_primary: Primary person's age
            age_spouse: Spouse's age
            brokerage_account: BrokerageAccount instance for LTCG ratio
            
        Returns:
            Estimated total tax (federal + state)
        """
        # Ensure anticipated_needs is a dict
        if not isinstance(anticipated_needs, dict):
            logger.error(f"anticipated_needs is not a dict: {type(anticipated_needs)}, value: {anticipated_needs}")
            anticipated_needs = {
                'total_traditional_need': 0.0,
                'brokerage_need': 0.0
            }
        
        # Estimate Traditional withdrawals needed
        estimated_trad_withdrawal = anticipated_needs.get('total_traditional_need', 0.0)
        
        # Estimate brokerage LTCG
        estimated_brokerage_withdrawal = anticipated_needs.get('brokerage_need', 0.0)
        
        # Use actual brokerage LTCG ratio if available, otherwise use 40% default
        if brokerage_account is not None:
            summary = brokerage_account.get_summary()
            ltcg_ratio = summary.get('ltcg_ratio', 0.4)
        else:
            ltcg_ratio = 0.4
            
        estimated_ltcg = estimated_brokerage_withdrawal * ltcg_ratio
        
        # Calculate estimated AGI
        estimated_agi = estimated_ltcg + roth_conversion + estimated_trad_withdrawal
        
        # Get standard deduction
        std_deduction = self._get_standard_deduction(
            filing_status, year, age_primary, age_spouse
        )
        
        # Calculate estimated federal tax
        taxable_income = max(0, estimated_agi - std_deduction)
        ordinary_income = max(0, taxable_income - estimated_ltcg)
        
        federal_tax, _, _ = self.tax_calculator.calculate_federal_tax(
            ordinary_income, filing_status, year
        )
        
        cg_tax = self.tax_calculator.calculate_capital_gains_tax(
            estimated_ltcg, ordinary_income, filing_status, year
        )
        
        # Calculate estimated state tax
        state_tax = self.tax_calculator.calculate_state_tax(
            agi=estimated_agi,
            state=state,
            year=year,
            filing_status=filing_status,
            retirement_income=estimated_trad_withdrawal,
            ss_benefits=0.0,  # No SS in Stage 4
            roth_conversion=roth_conversion
        )
        
        total_tax = federal_tax + cg_tax + state_tax
        
        logger.info(
            f"Year {year} Stage 4 preliminary tax estimate: "
            f"Federal=${federal_tax:,.0f}, CG=${cg_tax:,.0f}, "
            f"State=${state_tax:,.0f}, Total=${total_tax:,.0f}"
        )
        logger.debug(
            f"  Estimated AGI=${estimated_agi:,.0f} "
            f"(LTCG=${estimated_ltcg:,.0f}, Conv=${roth_conversion:,.0f}, "
            f"Trad=${estimated_trad_withdrawal:,.0f})"
        )
        
        return total_tax
    
    def _calculate_fallback_conversion(
        self,
        available_balance: float,
        current_income: float,
        irmaa_headroom: float,
        target_rate: float,
        year: int
    ) -> float:
        """Fallback conversion: fill to target bracket respecting IRMAA."""
        try:
            from calculations import get_income_tax_brackets, get_target_conversion_bracket, getUpperIncomeRate
            from load_data import get_std_deduction
            import pandas as pd
            
            tax_brackets = get_income_tax_brackets(year)
            std_deduction_df = get_std_deduction(year, 'married_filing_jointly')
            std_deduction = std_deduction_df.iloc[0]['deduction']
            
            try:
                target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                    target_rate, pd.DataFrame(tax_brackets)
                )
            except ValueError:
                target_bracket_rate = 0.12
                target_bracket_upper = float(getUpperIncomeRate(0.12, tax_brackets))
            
            tax_headroom = target_bracket_upper - std_deduction - current_income
            conversion_room = min(irmaa_headroom, tax_headroom)
            
            return min(conversion_room, available_balance)
            
        except Exception as e:
            logger.error(f"Fallback conversion calculation failed: {e}")
            return 0.0
    
    def _calculate_daf_optimization(
        self,
        strategy: YearlyStrategy,
        age_primary: int,
        age_spouse: int,
        std_deduction: float,
        state: str,
        taxable_balance: float,
        year: int,
        filing_status: str
    ) -> tuple[float, float]:
        """Calculate DAF contribution and tax optimization."""
        try:
            from strategy import _calculate_daf_for_year, calculate_state_tax
            from config import get_config_manager
            
            config_mgr = get_config_manager()
            property_tax = float(
                config_mgr.get("expenses", "living_expenses", {}).get("property_tax", 0)
            )
            
            state_tax, _ = calculate_state_tax(
                state_agi=0.0,
                year=year,
                filing_status=filing_status,
                retirement_income=0.0,
                ss_benefits=0.0
            )
            
            daf_contribution, daf_tax_excess = _calculate_daf_for_year(
                age_primary, age_spouse, std_deduction, 
                state_tax, property_tax, taxable_balance
            )
            
            return daf_contribution, daf_tax_excess
            
        except Exception as e:
            logger.warning(f"DAF calculation failed: {e}")
            return 0.0, 0.0
    
    def _log_daf_conversion_enhancement(
        self,
        strategy: YearlyStrategy,
        daf_contribution: float,
        daf_tax_excess: float,
        additional_conversion: float,
        total_conversion: float,
        irmaa_headroom: float
    ) -> None:
        """Log DAF-enhanced Roth conversion decision with IRMAA consideration."""
        logger.info(
            f"Year {strategy.year}: DAF optimization - increasing Roth conversion by "
            f"${additional_conversion:,.0f} (from ${total_conversion - additional_conversion:,.0f} "
            f"to ${total_conversion:,.0f})"
        )
        
        self._log_decision(
            strategy,
            'tax_strategy',
            'DAF Conversion Optimization',
            f'Increased Roth conversion by ${additional_conversion:,.0f}',
            f'Instead of simply reducing taxes, the DAF contribution (${daf_contribution:,.0f}) creates '
            f'${daf_tax_excess:,.0f} of additional itemized deduction above the standard deduction. '
            f'This "tax space" allows for ${additional_conversion:,.0f} more Roth conversion at the same '
            f'effective tax rate, while staying within IRMAA constraints. This accelerates the Traditional→Roth '
            f'transition before RMDs begin.',
            daf_contribution=daf_contribution,
            daf_tax_excess=daf_tax_excess,
            additional_conversion=additional_conversion,
            original_conversion=total_conversion - additional_conversion,
            enhanced_conversion=total_conversion,
            irmaa_headroom=irmaa_headroom
        )
    
    def _apply_daf_contribution(
        self,
        balances: PortfolioBalances,
        daf_contribution: float,
        year: int = 0,
        brokerage_account: Any = None,
    ) -> PortfolioBalances:
        """Apply DAF contribution using HIFO lot removal for maximum gain elimination."""
        try:
            from strategy import apply_daf_to_brokerage_account
            return apply_daf_to_brokerage_account(
                balances, daf_contribution, year, brokerage_account
            )
        except ImportError:
            if daf_contribution > 0:
                return PortfolioBalances(
                    cash=balances.cash,
                    taxable=balances.taxable - daf_contribution,
                    traditional=balances.traditional,
                    roth=balances.roth,
                    daf=balances.daf,
                )
            return balances
    
    def _execute_rebalancing(
        self,
        strategy: YearlyStrategy,
        balances: PortfolioBalances,
        expenses: float,
        roth_conversion: float,
        irmaa_penalty: float,
        aca_premium: float,
        preliminary_tax: float,
        year: int,
        age_primary: int,
        brokerage_account: Any
    ) -> tuple[PortfolioBalances, dict]:
        """Execute account rebalancing with preliminary tax estimate."""
        try:
            from strategy import rebalance_accounts
            
            new_balances, transactions, rebal_dl = rebalance_accounts(
                balances=balances,
                expenses=expenses,
                roth_conversion=roth_conversion,
                year=year,
                age_primary=age_primary,
                stage=self.name,
                federal_tax=preliminary_tax,  # Pass preliminary tax estimate
                irmaa_penalty=irmaa_penalty,
                aca_premium=aca_premium,
                medical_costs=0.0,
                brokerage_account=brokerage_account
            )
            
            strategy.decisions.cash_replenishment.extend(rebal_dl.cash_replenishment)
            strategy.decisions.brokerage_replenishment.extend(rebal_dl.brokerage_replenishment)
            
            return new_balances, transactions
            
        except ImportError:
            logger.warning("Rebalancing module not available")
            return balances, {
                'traditional_to_cash': 0.0,
                'traditional_to_brokerage': 0.0,
                'brokerage_to_cash': 0.0,
                'roth_to_cash': 0.0,
                'roth_to_brokerage': 0.0,
                'conversion_executed': roth_conversion,
                'cash_replenishment': 0.0,
                'brokerage_replenishment': 0.0,
                'brokerage_ltcg': 0.0
            }
    
    def _ensure_standard_deduction_target(
        self,
        strategy: YearlyStrategy,
        balances: PortfolioBalances,
        transactions: dict,
        roth_conversion: float,
        min_ordinary_income_target: float,
        std_deduction: float,
        year: int
    ) -> tuple[PortfolioBalances, dict]:
        """Ensure 90% standard deduction target is met."""
        trad_withdrawal = (
            transactions['traditional_to_cash'] + 
            transactions['traditional_to_brokerage']
        )
        ordinary_income = roth_conversion + trad_withdrawal
        
        if ordinary_income < min_ordinary_income_target and balances.traditional > 0:
            additional_needed = min_ordinary_income_target - ordinary_income
            additional_withdrawal = min(additional_needed, balances.traditional)
            
            balances = PortfolioBalances(
                cash=balances.cash + additional_withdrawal,
                taxable=balances.taxable,
                traditional=balances.traditional - additional_withdrawal,
                roth=balances.roth,
                daf=balances.daf
            )
            transactions['traditional_to_cash'] += additional_withdrawal
            
            logger.info(
                f"Year {year}: Added ${additional_withdrawal:,.0f} Traditional withdrawal "
                f"to reach 90% std deduction target"
            )
            
            self._log_decision(
                strategy,
                'tax_strategy',
                'Standard Deduction Optimization (0% Tax)',
                f'Added ${additional_withdrawal:,.0f} Traditional withdrawal',
                f'Roth conversion + buffer withdrawals totaled ${ordinary_income:,.0f}. '
                f'Added ${additional_withdrawal:,.0f} to reach 90% of standard deduction (${min_ordinary_income_target:,.0f}).',
                std_deduction=std_deduction,
                target_income=min_ordinary_income_target,
                additional_withdrawal=additional_withdrawal
            )
        elif ordinary_income >= min_ordinary_income_target:
            logger.info(
                f"Year {year}: Ordinary income ${ordinary_income:,.0f} already meets target"
            )
            
            self._log_decision(
                strategy,
                'tax_strategy',
                'Standard Deduction Optimization (0% Tax)',
                'Target met via Roth conversion + buffer withdrawals',
                f'Ordinary income of ${ordinary_income:,.0f} meets the 90% standard deduction target.',
                std_deduction=std_deduction,
                target_income=min_ordinary_income_target
            )
        
        return balances, transactions
    
    def _calculate_final_taxes(
        self,
        strategy: YearlyStrategy,
        balances: PortfolioBalances,
        transactions: dict,
        roth_conversion: float,
        daf_contribution: float,
        daf_tax_excess: float,
        std_deduction: float,
        filing_status: str,
        state: str,
        year: int,
        expenses: float,
        age_primary: int = 0,
        age_spouse: int = 0,
        daf_carryforward_prior: float = 0.0,
        property_tax: float = 0.0
    ) -> PortfolioBalances:
        """
        Calculate final AGI and taxes with correct order.
        
        Uses AGICalculator to implement correct IRC-compliant calculation.
        Stage 4 is Medicare-eligible but no SS yet.
        """
        # Calculate AGI components from transactions
        trad_withdrawal = (
            transactions['traditional_to_cash'] +
            transactions['traditional_to_brokerage']
        )
        brokerage_ltcg = transactions.get('brokerage_ltcg', 0.0)
        brokerage_basis = transactions.get('brokerage_basis', 0.0)
        
        # Use AGICalculator with correct order
        agi_calc = AGICalculator(self.tax_calculator)
        tax_result = agi_calc.calculate_agi_and_taxes(
            year=year,
            filing_status=filing_status,
            age_primary=age_primary,
            age_spouse=age_spouse,
            traditional_withdrawal=trad_withdrawal,
            roth_conversion=roth_conversion,
            brokerage_ltcg=brokerage_ltcg,
            brokerage_basis=brokerage_basis,
            daf_fmv=daf_contribution,
            state=state,
            pa_rate=0.0307,  # PA flat income tax rate (3.07%)
            property_tax=property_tax,
            daf_carryforward_prior=daf_carryforward_prior,
            tax_calculator=self.tax_calculator
        )
        
        # Extract results
        federal_tax = tax_result['federal_ordinary_tax']
        cg_tax = tax_result['ltcg_tax']
        state_tax = tax_result['state_tax']
        total_tax = tax_result['total_tax']
        agi = tax_result['agi_pre_deduction']
        magi = agi  # Same as AGI in Stage 4 (no SS benefits)
        ordinary_income = tax_result['taxable_ordinary']
        taxable_income = ordinary_income + brokerage_ltcg
        
        logger.info(
            f"Year {year} Stage 4 AGI (CORRECTED): Trad=${trad_withdrawal:,.0f}, "
            f"Roth=${roth_conversion:,.0f}, Basis=${brokerage_basis:,.0f}, "
            f"LTCG=${brokerage_ltcg:,.0f} → AGI=${agi:,.0f}; "
            f"Taxable Ordinary=${ordinary_income:,.0f}; "
            f"Taxes: Fed=${federal_tax:,.0f}, LTCG=${cg_tax:,.0f}, "
            f"State=${state_tax:,.0f}, Total=${total_tax:,.0f}"
        )
        
        # Calculate tax estimation error
        actual_total_tax = total_tax + state_tax
        preliminary_tax = transactions.get('taxes_paid', 0.0)
        tax_difference = actual_total_tax - preliminary_tax
        
        if abs(tax_difference) > 100:
            logger.info(
                f"Year {year} Stage 4 tax estimation adjustment: "
                f"Preliminary=${preliminary_tax:,.0f}, "
                f"Actual=${actual_total_tax:,.0f}, "
                f"Difference=${tax_difference:,.0f}"
            )
        
        # Deduct any additional tax from cash (or credit back if we over-estimated)
        # If cash is insufficient, pull from taxable account
        new_cash = balances.cash - tax_difference
        
        if new_cash < 0:
            logger.warning(
                f"Year {year}: Cash insufficient for tax adjustment "
                f"(${balances.cash:,.2f} - ${tax_difference:,.2f} = ${new_cash:,.2f}). "
                f"Pulling ${-new_cash:,.2f} from taxable account."
            )
            balances = PortfolioBalances(
                cash=0,
                taxable=balances.taxable + new_cash,  # new_cash is negative, so this reduces taxable
                traditional=balances.traditional,
                roth=balances.roth,
                daf=balances.daf
            )
        else:
            balances = PortfolioBalances(
                cash=new_cash,
                taxable=balances.taxable,
                traditional=balances.traditional,
                roth=balances.roth,
                daf=balances.daf
            )
            
            if tax_difference > 0:
                logger.info(f"Year {year}: Deducted additional tax ${tax_difference:,.2f} from cash")
            elif tax_difference < 0:
                logger.info(f"Year {year}: Credited back over-estimated tax ${-tax_difference:,.2f} to cash")
        
        if daf_contribution > 0:
            logger.info(f"Year {year}: Final tax with DAF:")
            logger.info(f"  AGI: ${agi:,.2f}")
            logger.info(f"  DAF deductible: ${tax_result['daf_deductible_this_year']:,.2f}")
            logger.info(f"  DAF carryforward: ${tax_result['daf_carryforward_new']:,.2f}")
            logger.info(f"  Deduction ({tax_result['deduction_type']}): ${tax_result['deduction']:,.2f}")
            logger.info(f"  Total Tax: ${total_tax:,.2f}")
        
        # Update strategy
        strategy.expenses = expenses  # Store expenses in strategy
        strategy.agi = agi
        strategy.magi = magi
        strategy.taxable_income = taxable_income
        strategy.federal_tax = total_tax
        strategy.ltcg_tax = cg_tax
        strategy.state_tax = state_tax
        strategy.ltcg_harvested = brokerage_ltcg
        strategy.traditional_withdrawal = trad_withdrawal
        strategy.taxable_withdrawal = transactions['brokerage_to_cash']
        strategy.roth_withdrawal = (
            transactions['roth_to_cash'] +
            transactions['roth_to_brokerage']
        )
        
        # Return updated balances with tax adjustments applied
        return balances

    def _plan_january_bracket_fill_withdrawal(
        self,
        year: int,
        pnc_savings_balance: float,
        annual_expenses: float,
        aca_premium: float,
        age_primary: int,
        age_spouse: int,
        filing_status: str
    ) -> Optional[dict]:
        """
        Use January Bracket-Fill Strategy if enabled in configuration.
        
        This is an OPTIONAL path that can complement or replace the existing BETR logic.
        Returns withdrawal plan if enabled; None otherwise.
        
        Args:
            year: Current year
            pnc_savings_balance: PNC Savings account balance (actual spendable cash)
            annual_expenses: Annual living expenses
            aca_premium: ACA insurance premium
            age_primary: Primary person's age
            age_spouse: Spouse's age
            filing_status: Tax filing status
        
        Returns:
            JanuaryWithdrawalPlan dict or None if not enabled
        """
        # Check if January Bracket-Fill is enabled in config
        try:
            from config import get_config_value
            use_january_strategy = get_config_value(
                'tax_strategy', 
                'use_january_bracket_fill_strategy', 
                False
            )
        except:
            use_january_strategy = False
        
        if not use_january_strategy:
            logger.debug("Stage 4: January Bracket-Fill Strategy not enabled in config")
            return None
        
        # Get bracket parameters for this year
        try:
            import csv
            bracket_12_upper = None
            std_deduction_value = None
            
            # Read bracket from income_rates.csv
            import os as _os
            _csv_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), 'income_rates.csv')
            with open(_csv_path) as f:
                for row in csv.DictReader(f):
                    if (int(row['year']) == year and 
                        row['filing_status'] == filing_status and 
                        abs(float(row['rate']) - 0.12) < 0.001):
                        bracket_12_upper = float(row['upper'])
                        break
            
            # Get standard deduction
            std_deduction_value = self.tax_calculator.calculate_standard_deduction(
                filing_status, year, age_primary, age_spouse
            )
        except Exception as e:
            logger.warning(f"Stage 4: Could not read bracket data: {e}")
            return None
        
        if not bracket_12_upper or not std_deduction_value:
            logger.warning("Stage 4: Missing bracket or deduction data for January strategy")
            return None
        
        # Read safety reserve from config (default = 5 months of expenses)
        try:
            from config import get_config_value
            _safety_reserve = float(get_config_value(
                'tax_strategy', 'savings_safety_reserve',
                round(annual_expenses / 12 * 5)
            ))
        except:
            _safety_reserve = round(annual_expenses / 12 * 5)
        
        # Initialize January strategy
        strategy = JanuaryBracketFillStrategy(
            annual_expenses=annual_expenses,
            savings_account_safety_reserve=_safety_reserve,
            bracket_12_upper=bracket_12_upper,
            standard_deduction=std_deduction_value
        )
        
        # Plan the withdrawal
        try:
            # Withholding rate = stage 4 max conversion rate (from config) ÷ 100
            try:
                from config import get_config_value
                _stage_rate_pct = float(get_config_value(
                    'tax_strategy', 'stage_4_max_conversion_rate', 12
                ))
            except:
                _stage_rate_pct = 12.0
            _withholding_rate = _stage_rate_pct / 100.0
            
            plan = strategy.plan_january_withdrawal(
                    pnc_savings_balance_jan1=pnc_savings_balance,
                    estimated_tax_rate=_withholding_rate,
                    aca_premium=aca_premium,
                    conversion_date=datetime(year, 1, 15),
                    year=year,
                    filing_status=filing_status,
                    age_primary=age_primary,
                    age_spouse=age_spouse,
                    tax_calculator=self.tax_calculator
                )
            
            logger.info(
                f"Stage 4: January Bracket-Fill plan generated: "
                f"Shortfall=${plan.pnc_shortfall:,.0f}, "
                f"Traditional withdrawal=${plan.total_traditional_withdrawal:,.0f}, "
                f"Roth conversion=${plan.roth_conversion_amount:,.0f}"
            )
            
            return {
                'plan': plan,
                'pnc_shortfall': plan.pnc_shortfall,
                'traditional_withdrawal': plan.total_traditional_withdrawal,
                'roth_conversion': plan.roth_conversion_amount,
                'conversion_withholding': plan.conversion_withholding,
                'redeposit_deadline': plan.sixty_day_redeposit_deadline,
            }
        except Exception as e:
            logger.warning(f"Stage 4: January Bracket-Fill planning failed: {e}")
            return None


# Made with Bob