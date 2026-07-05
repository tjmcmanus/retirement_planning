"""
Stage 5: Social Security (SS + Medicare, Pre-RMD)

Refactored implementation using BaseLifeStageStrategy with dependency injection.
Handles the Social Security stage with Medicare but before RMDs begin.

This file is Part 1 of 2 - Core structure and main calculation flow.
"""

import logging
from typing import Any, Optional, Tuple, Dict

from ..base_strategy import BaseLifeStageStrategy
from ..interfaces import ITaxCalculator, IAccountManager
from ..models import PortfolioBalances, YearlyStrategy
from .stage6_rmd import get_rmd_age

logger = logging.getLogger(__name__)

# Constants
MEDICARE_AGE = 65
TAXABLE_SS_RATE = 0.85  # Up to 85% of SS benefits are taxable
BROKERAGE_LTCG_RATIO = 0.60  # Fallback: 60% LTCG
BROKERAGE_COST_BASIS_RATIO = 0.40  # Fallback: 40% cost basis


class Stage5SocialSecurity(BaseLifeStageStrategy):
    """
    Stage 5: Social Security (SS + Medicare, Pre-RMD)
    
    - Collecting Social Security benefits
    - On Medicare (IRMAA considerations with 2-year lookback)
    - Continue strategic Roth conversions with BETR optimization
    - Balance SS taxation (up to 85% taxable based on combined income)
    - Multi-constraint optimization (SS income + IRMAA + ACA subsidies)
    - RMD planning outlook (years until RMDs and projected impact)
    - DAF optimization with conversion enhancement
    - Standard deduction optimization (90% target with ordinary income)
    """
    
    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """
        Initialize Stage 5 Social Security strategy.
        
        Args:
            tax_calculator: Tax calculator for tax computations
            account_manager: Account manager for withdrawals/conversions
        """
        super().__init__(
            name="Stage 5: Social Security",
            description="Collecting SS + Medicare, pre-RMD optimization",
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
        Determine if this strategy applies.
        
        Stage 5 applies when collecting SS but before RMDs.
        Uses the OLDER spouse's age for RMD threshold (conservative approach).
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            True if collecting SS and older spouse is under RMD age
        """
        older_age = max(age_primary, age_spouse)
        # RMD age depends on birth year (SECURE 2.0): 73 if born 1951–1959, 75 if born 1960+
        birth_year_primary = year - age_primary
        birth_year_spouse = year - age_spouse
        rmd_age = get_rmd_age(max(birth_year_primary, birth_year_spouse))  # older person drives threshold
        return (not has_wages and has_ss and older_age < rmd_age)
    
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate withdrawal strategy for Social Security stage.
        
        Key features:
        - SS taxation calculation (up to 85% taxable based on combined income)
        - IRMAA optimization with 2-year lookback
        - Multi-constraint Roth conversion (SS + IRMAA + ACA)
        - BETR-optimized conversions with fallback
        - DAF optimization with conversion enhancement
        - Standard deduction optimization (90% target)
        - RMD planning outlook
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            **kwargs: Additional parameters including:
                - age_primary, age_spouse: Ages
                - ss_benefits: Social Security benefits
                - prior_magi: MAGI from 2 years ago (for IRMAA)
                - filing_status: Tax filing status
                - brokerage_account: BrokerageAccount object
                - growth_rate: Portfolio growth rate
                - start_year: Simulation start year
                - max_conversion_rate: Maximum conversion tax rate
                
        Returns:
            YearlyStrategy with all calculations
        """
        # Validate dependencies
        self._validate_dependencies()
        
        # Extract parameters
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        ss_benefits = kwargs.get('ss_benefits', 0.0)
        prior_magi = kwargs.get('prior_magi', 0.0)
        filing_status = kwargs.get('filing_status', 'married_filing_jointly')
        brokerage_account = kwargs.get('brokerage_account')
        growth_rate = kwargs.get('growth_rate', 1.07)
        start_year = kwargs.get('start_year', year)
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        
        logger.debug(f"Stage 5 (SS) calculation for year {year}, SS=${ss_benefits:,.2f}")
        
        # Create base strategy object
        strategy = self._create_yearly_strategy(
            year, age_primary, age_spouse, balances
        )
        
        # Get standard deduction and tax data
        std_deduction = self._get_standard_deduction(year, filing_status)
        
        # Calculate minimum ordinary income target (90% of standard deduction)
        min_ordinary_income_target = std_deduction * 0.90
        
        # Calculate IRMAA penalty
        irmaa_penalty = self._calculate_irmaa_penalty(
            prior_magi, age_primary, age_spouse, year
        )

        # Calculate full healthcare costs (Medicare + IRMAA + Medigap + OOP + LTC)
        # irmaa_penalty and aca_premium are kept separately for rebalancing/conversion logic;
        # healthcare_total is the comprehensive figure stored on the strategy for reporting.
        try:
            from strategy import calculate_total_healthcare_costs
            healthcare_total, _hc_breakdown = calculate_total_healthcare_costs(
                age_primary=age_primary,
                age_spouse=age_spouse,
                magi_two_years_ago=prior_magi,
                year=year,
                filing_status=filing_status,
                has_medigap=True
            )
            logger.info(f"Stage 5: Total healthcare costs=${healthcare_total:,.2f} "
                        f"(IRMAA=${irmaa_penalty:,.2f})")
        except Exception as e:
            logger.warning(f"Stage 5: Could not calculate full healthcare costs, falling back: {e}")
            healthcare_total = irmaa_penalty  # aca_premium not yet computed; added below if needed

        # Calculate buffer needs
        cash_need, taxable_need = self._calculate_buffer_needs(
            expenses, year, start_year, balances
        )
        
        # Initialize LTCG tracking
        ltcg_harvested = 0.0
        basis_returned = 0.0
        
        # Calculate preliminary taxable SS with conservative conversion estimate
        conservative_conversion_estimate = self._estimate_conversion_amount(
            max_conversion_rate, std_deduction, year
        )
        
        taxable_ss = self._calculate_ss_taxation(
            ss_benefits, conservative_conversion_estimate, filing_status
        )
        
        logger.debug(f"SS taxation (preliminary): ${ss_benefits:,.0f} → ${taxable_ss:,.0f} taxable "
                    f"({taxable_ss/ss_benefits*100 if ss_benefits > 0 else 0:.1f}%)")
        
        # Add SS benefits to cash
        balances_with_ss = PortfolioBalances(
            cash=balances.cash + ss_benefits,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth,
            daf=balances.daf
        )
        
        # Calculate preliminary tax estimate
        preliminary_tax = self._calculate_preliminary_tax(
            taxable_ss, ltcg_harvested, conservative_conversion_estimate,
            std_deduction, year, filing_status
        )
        
        # Calculate ACA premium
        aca_premium = self._calculate_aca_premium(year, age_primary, age_spouse)
        
        # Calculate anticipated buffer needs
        anticipated_needs = self._calculate_anticipated_buffer_needs(
            balances_with_ss, expenses, age_primary, preliminary_tax,
            irmaa_penalty, aca_premium, brokerage_account
        )
        
        logger.debug(f"Anticipated buffer needs: Trad→Cash=${anticipated_needs['traditional_to_cash']:,.0f}, "
                    f"Trad→Brok=${anticipated_needs['traditional_to_brokerage']:,.0f}")
        
        # Calculate current income for conversion calculation
        current_income = (taxable_ss +
                         anticipated_needs['traditional_to_cash'] +
                         anticipated_needs['traditional_to_brokerage'])
        
        # Check ACA subsidy considerations
        aca_info = self._check_aca_subsidy_constraints(
            age_primary, age_spouse, current_income, std_deduction
        )
        
        # Find IRMAA headroom
        irmaa_headroom = self._calculate_irmaa_headroom(
            prior_magi, current_income, std_deduction, year
        )
        
        # Calculate available Traditional for conversion
        available_for_conversion = (balances.traditional -
                                   anticipated_needs['traditional_to_cash'] -
                                   anticipated_needs['traditional_to_brokerage'])
        
        logger.info(f"Stage 5 Conversion Inputs: current_income=${current_income:,.0f}, "
                   f"available_for_conversion=${available_for_conversion:,.0f}")
        
        # Calculate optimal Roth conversion with BETR
        roth_conversion, optimal_amount = self._calculate_optimal_roth_conversion(
            available_for_conversion, current_income, max_conversion_rate,
            irmaa_headroom, aca_info, balances, age_primary, year, growth_rate,
            std_deduction, filing_status
        )
        
        logger.debug(f"Roth conversion: ${roth_conversion:,.2f}")
        
        # Recalculate preliminary tax with conversion
        preliminary_tax_with_conv = self._calculate_preliminary_tax(
            taxable_ss, ltcg_harvested, roth_conversion,
            std_deduction, year, filing_status
        )
        
        # Calculate DAF contribution
        daf_contribution, daf_tax_excess = self._calculate_daf_contribution(
            age_primary, age_spouse, std_deduction, taxable_ss, year,
            filing_status, balances_with_ss.taxable
        )
        
        # DAF optimization: enhance Roth conversion with DAF tax space
        daf_enhanced_conversion = self._calculate_daf_enhanced_conversion(
            daf_contribution, daf_tax_excess, roth_conversion,
            available_for_conversion, irmaa_headroom, aca_info,
            current_income, max_conversion_rate, std_deduction, year
        )
        
        if daf_enhanced_conversion > 0:
            roth_conversion += daf_enhanced_conversion
            logger.info(f"Year {year}: DAF optimization - increased Roth conversion by ${daf_enhanced_conversion:,.0f}")
        
        # Subtract DAF from brokerage before rebalancing (HIFO lot removal)
        balances_for_rebalance = balances_with_ss
        if daf_contribution > 0:
            try:
                from strategy import apply_daf_to_brokerage_account
                balances_for_rebalance = apply_daf_to_brokerage_account(
                    balances_with_ss, daf_contribution, year, brokerage_account
                )
            except ImportError:
                balances_for_rebalance = PortfolioBalances(
                    cash=balances_with_ss.cash,
                    taxable=balances_with_ss.taxable - daf_contribution,
                    traditional=balances_with_ss.traditional,
                    roth=balances_with_ss.roth,
                    daf=balances_with_ss.daf,
                )
            logger.info(f"Year {year}: DAF HIFO donation ${daf_contribution:,.0f} from Brokerage")
        
        # Execute account rebalancing
        new_balances, transactions = self._execute_rebalancing(
            balances_for_rebalance, expenses, roth_conversion, year, age_primary,
            preliminary_tax_with_conv, irmaa_penalty, aca_premium, brokerage_account
        )
        
        # Ensure 90% standard deduction target met
        new_balances, transactions = self._ensure_standard_deduction_target(
            new_balances, transactions, taxable_ss, roth_conversion,
            min_ordinary_income_target, year
        )
        
        # Apply growth
        new_balances = PortfolioBalances(
            cash=new_balances.cash,
            taxable=new_balances.taxable * growth_rate,
            traditional=new_balances.traditional * growth_rate,
            roth=new_balances.roth * growth_rate,
            daf=new_balances.daf * growth_rate
        )
        
        # Calculate final AGI and taxes
        trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage']
        brokerage_ltcg = transactions.get('brokerage_ltcg', 0.0)
        total_ltcg = ltcg_harvested + brokerage_ltcg
        
        # Recalculate taxable SS with actual income
        taxable_ss = self._calculate_ss_taxation(
            ss_benefits, total_ltcg + roth_conversion + trad_withdrawal, filing_status
        )
        
        logger.debug(f"SS taxation (final): ${ss_benefits:,.0f} → ${taxable_ss:,.0f} taxable")
        
        # Calculate final taxes
        total_income = taxable_ss + total_ltcg + roth_conversion + trad_withdrawal
        agi = total_income
        magi = agi
        
        federal_tax, cg_tax = self._calculate_taxes(
            agi, std_deduction, total_ltcg, year, filing_status
        )
        total_tax = federal_tax + cg_tax
        
        # Calculate state tax
        state_tax = self._calculate_state_tax(
            agi, year, filing_status, trad_withdrawal, roth_conversion, taxable_ss
        )
        
        # Deduct state tax from cash balance
        new_balances = PortfolioBalances(
            cash=new_balances.cash - state_tax,
            taxable=new_balances.taxable,
            traditional=new_balances.traditional,
            roth=new_balances.roth,
            daf=new_balances.daf
        )
        logger.info(f"Year {year}: Deducted state tax ${state_tax:,.2f} from cash")
        
        # If DAF contribution made, recalculate taxes with increased deduction
        if daf_contribution > 0:
            new_balances = PortfolioBalances(
                cash=new_balances.cash,
                taxable=new_balances.taxable,
                traditional=new_balances.traditional,
                roth=new_balances.roth,
                daf=new_balances.daf + daf_contribution
            )
            
            effective_deduction = std_deduction + daf_tax_excess
            federal_tax, cg_tax = self._calculate_taxes(
                agi, effective_deduction, total_ltcg, year, filing_status
            )
            total_tax = federal_tax + cg_tax
            
            logger.info(f"Year {year}: Federal tax reduced by DAF deduction (excess: ${daf_tax_excess:,.0f})")
        
        # Get cost basis ratios
        if brokerage_account:
            brokerage_ltcg_ratio = brokerage_account.ltcg_ratio
            brokerage_basis_ratio = brokerage_account.basis_ratio
        else:
            brokerage_ltcg_ratio = BROKERAGE_LTCG_RATIO
            brokerage_basis_ratio = BROKERAGE_COST_BASIS_RATIO
        
        # Log key decisions
        self._log_ss_income(strategy, ss_benefits, taxable_ss)
        self._log_irmaa_assessment(strategy, irmaa_penalty, prior_magi, age_primary, age_spouse, irmaa_headroom, year)
        self._log_roth_conversion_decision(strategy, roth_conversion, optimal_amount, age_primary, age_spouse, aca_info, balances, year)
        self._log_rmd_planning_outlook(strategy, age_primary, age_spouse, roth_conversion, balances, year)
        
        if daf_contribution > 0 and daf_enhanced_conversion > 0:
            self._log_daf_conversion_enhancement(
                strategy, daf_contribution, daf_tax_excess, daf_enhanced_conversion,
                roth_conversion, irmaa_headroom, aca_info
            )
        
        # Populate strategy object
        strategy.wages = 0
        strategy.ss_benefits = ss_benefits
        strategy.rmd_amount = 0
        strategy.traditional_withdrawal = trad_withdrawal
        strategy.taxable_withdrawal = transactions['brokerage_to_cash']
        strategy.roth_withdrawal = transactions['roth_to_cash'] + transactions['roth_to_brokerage']
        strategy.roth_conversion = roth_conversion
        strategy.ltcg_harvested = total_ltcg
        strategy.daf_contribution = daf_contribution
        strategy.expenses = expenses
        strategy.agi = agi
        strategy.magi = magi
        strategy.federal_tax = total_tax
        strategy.irmaa_penalty = irmaa_penalty
        strategy.aca_premium = aca_premium
        strategy.healthcare_costs = healthcare_total  # Full costs: Medicare + IRMAA + Medigap + OOP
        strategy.balances = new_balances
        strategy.state_tax = state_tax
        
        # Fund movement tracking
        strategy.cash_replenishment = transactions['cash_replenishment']
        strategy.brokerage_replenishment = transactions['brokerage_replenishment']
        strategy.traditional_to_cash = transactions['traditional_to_cash']
        strategy.traditional_to_brokerage = transactions['traditional_to_brokerage']
        strategy.brokerage_to_cash = transactions['brokerage_to_cash']
        strategy.roth_to_cash = transactions['roth_to_cash']
        strategy.roth_to_brokerage = transactions['roth_to_brokerage']
        strategy.conversion_executed = transactions['conversion_executed']
        
        # Cost basis tracking
        strategy.basis_returned = basis_returned
        strategy.brokerage_ltcg_ratio = brokerage_ltcg_ratio
        strategy.brokerage_basis_ratio = brokerage_basis_ratio
        
        return strategy

# Made with Bob

    
    # ==================== Helper Methods ====================
    
    def _get_standard_deduction(self, year: int, filing_status: str) -> float:
        """Get standard deduction for the year."""
        try:
            from load_data import get_std_deduction
            std_deduction_df = get_std_deduction(year, filing_status)
            return std_deduction_df.iloc[0]['deduction']
        except Exception as e:
            logger.warning(f"Could not get standard deduction: {e}")
            return 29200.0  # 2024 married filing jointly default
    
    def _calculate_irmaa_penalty(
        self,
        prior_magi: float,
        age_primary: int,
        age_spouse: int,
        year: int
    ) -> float:
        """Calculate IRMAA penalty based on prior MAGI."""
        try:
            from load_data import get_medicare_costs
            from calculations import calculate_irmma_penalty
            
            irmaa_brackets = get_medicare_costs(year)
            people_on_medicare = sum([age_primary >= MEDICARE_AGE, age_spouse >= MEDICARE_AGE])
            return calculate_irmma_penalty(prior_magi, irmaa_brackets, people_on_medicare)
        except Exception as e:
            logger.warning(f"Could not calculate IRMAA penalty: {e}")
            return 0.0
    
    def _calculate_buffer_needs(
        self,
        expenses: float,
        year: int,
        start_year: int,
        balances: PortfolioBalances
    ) -> Tuple[float, float]:
        """Calculate cash and taxable buffer needs."""
        try:
            from bucket_strategy import calculate_cash_buffer_targets, calculate_buffer_ramp_up
            
            cash_target, taxable_target = calculate_cash_buffer_targets(expenses)
            cash_need, taxable_need = calculate_buffer_ramp_up(
                year, start_year, cash_target, taxable_target,
                balances.cash, balances.taxable
            )
            
            logger.debug(f"Cash target: ${cash_target:,.2f} (need ${cash_need:,.2f}), "
                        f"Taxable target: ${taxable_target:,.2f} (need ${taxable_need:,.2f})")
            
            return cash_need, taxable_need
        except Exception as e:
            logger.warning(f"Could not calculate buffer needs: {e}")
            return 0.0, 0.0
    
    def _estimate_conversion_amount(
        self,
        max_conversion_rate: float,
        std_deduction: float,
        year: int
    ) -> float:
        """Estimate conservative conversion amount for preliminary calculations."""
        try:
            from load_data import get_income_tax_brackets
            from calculations import getUpperIncomeRate
            
            tax_brackets = get_income_tax_brackets(year)
            target_bracket_upper = float(getUpperIncomeRate(max_conversion_rate, tax_brackets))
            return max(0, (target_bracket_upper - std_deduction) * 0.5)
        except Exception as e:
            logger.warning(f"Could not estimate conversion amount: {e}")
            return 0.0
    
    def _calculate_ss_taxation(
        self,
        ss_benefits: float,
        agi_without_ss: float,
        filing_status: str
    ) -> float:
        """Calculate taxable portion of Social Security benefits."""
        try:
            from calculations import calculate_ss_taxable_amount
            return calculate_ss_taxable_amount(
                ss_benefits=ss_benefits,
                agi_without_ss=agi_without_ss,
                filing_status=filing_status
            )
        except Exception as e:
            logger.warning(f"Could not calculate SS taxation: {e}")
            return ss_benefits * TAXABLE_SS_RATE  # Fallback to 85%
    
    def _calculate_preliminary_tax(
        self,
        taxable_ss: float,
        ltcg: float,
        conversion: float,
        std_deduction: float,
        year: int,
        filing_status: str
    ) -> float:
        """Calculate preliminary tax estimate."""
        try:
            from load_data import get_income_tax_brackets, get_cap_gains_brackets
            from calculations import calculate_taxable_income, calculate_cap_gains
            import pandas as pd
            
            tax_brackets = get_income_tax_brackets(year)
            cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
            
            preliminary_income = taxable_ss + ltcg + conversion
            preliminary_taxable_income = preliminary_income - std_deduction
            
            result = calculate_taxable_income(preliminary_taxable_income, tax_brackets)
            federal_tax = result.total_tax
            cg_tax = calculate_cap_gains(preliminary_taxable_income - ltcg, cg_brackets, ltcg)
            
            return federal_tax + cg_tax
        except Exception as e:
            logger.warning(f"Could not calculate preliminary tax: {e}")
            return 0.0
    
    def _calculate_aca_premium(self, year: int, age_primary: int, age_spouse: int) -> float:
        """
        Calculate ACA premium for people under Medicare age (65) with ACA Marketplace coverage.
        
        In Stage 5, people may be collecting Social Security but not yet on Medicare.
        Only calculate ACA premiums if their retirement_coverage_type is "ACA Marketplace".
        If they have "Employer Retiree" coverage, use that premium instead.
        """
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()
            
            total_premium = 0.0
            medicare_age = 65
            
            # Person 1 healthcare (if under 65 and retired)
            if age_primary < medicare_age:
                coverage_type = config_mgr.get("healthcare", "person1_retirement_coverage_type", "None")
                
                if coverage_type == "ACA Marketplace":
                    monthly_premium = float(config_mgr.get("healthcare", "person1_aca_insurance_monthly", 1000))
                    total_premium += monthly_premium * 12
                    logger.debug(f"Person 1 ACA Marketplace (age {age_primary}): ${monthly_premium * 12:,.2f}/year")
                elif coverage_type == "Employer Retiree":
                    # Use employer retiree premium (typically lower than ACA)
                    monthly_premium = float(config_mgr.get("healthcare", "person1_aca_insurance_monthly", 1000))
                    total_premium += monthly_premium * 12
                    logger.debug(f"Person 1 Employer Retiree coverage (age {age_primary}): ${monthly_premium * 12:,.2f}/year")
            
            # Person 2 healthcare (if under 65 and retired)
            if age_spouse > 0 and age_spouse < medicare_age:
                coverage_type = config_mgr.get("healthcare", "person2_retirement_coverage_type", "None")
                
                if coverage_type == "ACA Marketplace":
                    monthly_premium = float(config_mgr.get("healthcare", "person2_aca_insurance_monthly", 1000))
                    total_premium += monthly_premium * 12
                    logger.debug(f"Person 2 ACA Marketplace (age {age_spouse}): ${monthly_premium * 12:,.2f}/year")
                elif coverage_type == "Employer Retiree":
                    # Use employer retiree premium
                    monthly_premium = float(config_mgr.get("healthcare", "person2_aca_insurance_monthly", 1000))
                    total_premium += monthly_premium * 12
                    logger.debug(f"Person 2 Employer Retiree coverage (age {age_spouse}): ${monthly_premium * 12:,.2f}/year")
            
            if total_premium > 0:
                logger.info(f"Year {year}: Retirement healthcare premiums for pre-Medicare individuals: ${total_premium:,.2f}")
            
            return total_premium
            
        except Exception as e:
            logger.warning(f"Could not calculate retirement healthcare premium: {e}")
            return 0.0
    
    def _calculate_anticipated_buffer_needs(
        self,
        balances: PortfolioBalances,
        expenses: float,
        age_primary: int,
        federal_tax: float,
        irmaa_penalty: float,
        aca_premium: float,
        brokerage_account: Any
    ) -> Dict[str, float]:
        """Calculate anticipated buffer needs before conversion optimization."""
        try:
            from bucket_strategy import calculate_anticipated_buffer_needs
            
            return calculate_anticipated_buffer_needs(
                balances=balances,
                expenses=expenses,
                age_primary=age_primary,
                federal_tax=federal_tax,
                irmaa_penalty=irmaa_penalty,
                aca_premium=aca_premium,
                medical_costs=0.0,
                brokerage_account=brokerage_account
            )
        except Exception as e:
            logger.warning(f"Could not calculate anticipated buffer needs: {e}")
            return {
                'traditional_to_cash': 0.0,
                'traditional_to_brokerage': 0.0
            }
    
    def _check_aca_subsidy_constraints(
        self,
        age_primary: int,
        age_spouse: int,
        current_income: float,
        std_deduction: float
    ) -> Dict[str, Any]:
        """Check ACA subsidy constraints if applicable."""
        person_under_medicare = (age_primary < MEDICARE_AGE or age_spouse < MEDICARE_AGE)
        
        if not person_under_medicare:
            return {
                'applicable': False,
                'threshold': float('inf'),
                'headroom': float('inf'),
                'preserved': False
            }
        
        # Federal Poverty Level for 2-person household (approximate)
        fpl_2026 = 20440 + 7320  # Base + 1 additional person
        aca_subsidy_threshold = fpl_2026 * 4.0  # 400% FPL threshold (~$111,040)
        
        projected_magi = current_income + std_deduction
        aca_headroom = max(0, aca_subsidy_threshold - projected_magi)
        
        logger.debug(f"ACA subsidy threshold (400% FPL): ${aca_subsidy_threshold:,.0f}, headroom: ${aca_headroom:,.0f}")
        
        return {
            'applicable': True,
            'threshold': aca_subsidy_threshold,
            'headroom': aca_headroom,
            'preserved': False  # Will be updated if conversion is limited
        }
    
    def _calculate_irmaa_headroom(
        self,
        prior_magi: float,
        current_income: float,
        std_deduction: float,
        year: int
    ) -> float:
        """Calculate IRMAA headroom to next bracket."""
        try:
            from load_data import get_medicare_costs
            import pandas as pd
            
            irmaa_brackets = get_medicare_costs(year)
            next_irmaa_threshold = float('inf')
            
            for _, row in irmaa_brackets.iterrows():
                if row['lower'] <= prior_magi <= row['upper']:
                    next_brackets = pd.DataFrame(irmaa_brackets[irmaa_brackets['lower'] > row['upper']])
                    if not next_brackets.empty:
                        next_irmaa_threshold = float(next_brackets.iloc[0]['lower'])
                    break
            
            return next_irmaa_threshold - current_income - std_deduction
        except Exception as e:
            logger.warning(f"Could not calculate IRMAA headroom: {e}")
            return float('inf')
    
    def _calculate_optimal_roth_conversion(
        self,
        available_for_conversion: float,
        current_income: float,
        max_conversion_rate: float,
        irmaa_headroom: float,
        aca_info: Dict[str, Any],
        balances: PortfolioBalances,
        age_primary: int,
        year: int,
        growth_rate: float,
        std_deduction: float,
        filing_status: str
    ) -> Tuple[float, float]:
        """Calculate optimal Roth conversion using BETR with constraints."""
        roth_conversion = 0.0
        optimal_amount = 0.0
        
        try:
            from betr_roth_conversion import optimize_conversion_amount, BETRInputs, calculate_betr
            from calculations import get_stage_specific_conversion_rate
            
            stage_max_conversion_rate = get_stage_specific_conversion_rate(self.name)
            
            # Use BETR algorithm
            optimal_amount, betr_results = optimize_conversion_amount(
                traditional_ira_balance=available_for_conversion,
                current_agi=current_income,
                target_tax_bracket=stage_max_conversion_rate,
                year=year,
                pay_from_taxable=True,
                taxable_account_balance=balances.taxable,
                years_to_withdrawal=(get_rmd_age(year - age_primary) - age_primary) if age_primary > 0 else 10,
                annual_return=growth_rate - 1.0
            )
            
            if optimal_amount <= 0:
                logger.info('No conversion: insufficient tax bracket room with SS income')
                return 0.0, 0.0
            
            # Apply constraints
            max_safe_conversion = optimal_amount
            limiting_factor = "tax_bracket"
            
            # Check ACA subsidy impact (highest priority)
            if aca_info['applicable'] and aca_info['headroom'] < max_safe_conversion:
                max_safe_conversion = max(0, aca_info['headroom'])
                limiting_factor = "aca_subsidy"
                aca_info['preserved'] = True
                logger.info(f"ACA subsidy constraint: limiting conversion to ${max_safe_conversion:,.0f}")
            
            # Check IRMAA impact (second priority)
            if irmaa_headroom < max_safe_conversion:
                max_safe_conversion = max(0, irmaa_headroom)
                limiting_factor = "irmaa" if limiting_factor == "tax_bracket" else f"{limiting_factor}+irmaa"
                logger.info(f"IRMAA constraint: limiting conversion to ${max_safe_conversion:,.0f}")
            
            # Verify reduced amount is still beneficial
            if max_safe_conversion > 0 and max_safe_conversion < optimal_amount:
                reduced_inputs = BETRInputs(
                    current_marginal_rate=stage_max_conversion_rate,
                    expected_future_rate=0.24,
                    conversion_amount=max_safe_conversion,
                    traditional_ira_balance=balances.traditional,
                    pay_from_taxable=True,
                    taxable_account_balance=balances.taxable,
                    years_to_withdrawal=(get_rmd_age(year - age_primary) - age_primary) if age_primary > 0 else 10,
                    annual_return=growth_rate - 1.0
                )
                reduced_results = calculate_betr(reduced_inputs)
                
                if reduced_results.conversion_recommended:
                    roth_conversion = max_safe_conversion
                    logger.info(f"BETR: {reduced_results.betr:.2%}, Converting ${max_safe_conversion:,.0f} ({limiting_factor}-limited)")
                else:
                    logger.info(f"BETR: {reduced_results.betr:.2%}, Conversion not recommended at {limiting_factor}-limited amount")
            elif max_safe_conversion <= 0:
                logger.info(f"No conversion room due to SS income and {limiting_factor} constraint")
            else:
                if betr_results.conversion_recommended:
                    roth_conversion = optimal_amount
                    logger.info(f"BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f} with SS income")
                else:
                    logger.info(f"BETR: {betr_results.betr:.2%}, Conversion not recommended despite SS income")
        
        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to conservative method")
            # Fallback to conservative method
            try:
                from load_data import get_income_tax_brackets
                from calculations import get_target_conversion_bracket, getUpperIncomeRate
                import pandas as pd
                
                tax_brackets = get_income_tax_brackets(year)
                try:
                    target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                        max_conversion_rate, pd.DataFrame(tax_brackets)
                    )
                except ValueError:
                    target_bracket_upper = float(getUpperIncomeRate(0.22, tax_brackets))
                
                tax_headroom = target_bracket_upper - std_deduction - current_income
                conversion_room = min(irmaa_headroom, tax_headroom)
                if aca_info['applicable']:
                    conversion_room = min(conversion_room, aca_info['headroom'])
                roth_conversion = min(conversion_room * 0.8, available_for_conversion)
            except Exception as e2:
                logger.warning(f"Fallback conversion calculation failed: {e2}")
        
        return roth_conversion, optimal_amount
    
    def _calculate_daf_contribution(
        self,
        age_primary: int,
        age_spouse: int,
        std_deduction: float,
        agi: float,
        year: int,
        filing_status: str,
        taxable_balance: float
    ) -> Tuple[float, float]:
        """Calculate DAF contribution for tax optimization."""
        try:
            from charitable_giving_advanced import _calculate_daf_for_year
            from config import get_config_manager
            from calculations import calculate_state_tax
            
            config_mgr = get_config_manager()
            
            # Get property tax
            try:
                property_tax = float(config_mgr.get("expenses", "living_expenses", {}).get("property_tax", 0))
            except Exception:
                property_tax = 0.0
            
            # Calculate state tax
            state_tax, _ = calculate_state_tax(
                state_agi=agi,
                year=year,
                filing_status=filing_status,
                retirement_income=0,
                ss_benefits=0
            )
            
            return _calculate_daf_for_year(
                age_primary, age_spouse, std_deduction, state_tax, property_tax, taxable_balance
            )
        except Exception as e:
            logger.warning(f"Could not calculate DAF contribution: {e}")
            return 0.0, 0.0
    
    def _calculate_daf_enhanced_conversion(
        self,
        daf_contribution: float,
        daf_tax_excess: float,
        roth_conversion: float,
        available_for_conversion: float,
        irmaa_headroom: float,
        aca_info: Dict[str, Any],
        current_income: float,
        max_conversion_rate: float,
        std_deduction: float,
        year: int
    ) -> float:
        """Calculate DAF-enhanced Roth conversion."""
        if daf_contribution <= 0 or daf_tax_excess <= 0 or roth_conversion <= 0:
            return 0.0
        
        try:
            from load_data import get_income_tax_brackets
            from calculations import getUpperIncomeRate
            
            # Calculate how much additional conversion we can do
            max_additional = daf_tax_excess
            
            # Respect available Traditional balance
            max_additional = min(max_additional, available_for_conversion - roth_conversion)
            
            # Respect IRMAA headroom
            if irmaa_headroom < float('inf'):
                max_additional = min(max_additional, irmaa_headroom - roth_conversion)
            
            # Respect ACA subsidy threshold
            if aca_info['applicable'] and aca_info['headroom'] < float('inf'):
                max_additional = min(max_additional, aca_info['headroom'] - roth_conversion)
            
            # Ensure total conversion doesn't exceed max_conversion_rate bracket
            tax_brackets = get_income_tax_brackets(year)
            target_bracket_upper = float(getUpperIncomeRate(max_conversion_rate, tax_brackets))
            total_income_with_enhancement = current_income + roth_conversion + max_additional
            projected_agi = total_income_with_enhancement - std_deduction
            
            if projected_agi > target_bracket_upper:
                room_in_bracket = max(0, target_bracket_upper - (current_income + roth_conversion - std_deduction))
                max_additional = min(max_additional, room_in_bracket)
                logger.debug(f"DAF optimization capped to stay within {max_conversion_rate:.0%} bracket")
            
            return max(0, max_additional)
        except Exception as e:
            logger.warning(f"Could not calculate DAF-enhanced conversion: {e}")
            return 0.0
    
    def _execute_rebalancing(
        self,
        balances: PortfolioBalances,
        expenses: float,
        roth_conversion: float,
        year: int,
        age_primary: int,
        total_tax: float,
        irmaa_penalty: float,
        aca_premium: float,
        brokerage_account: Any
    ) -> Tuple[PortfolioBalances, Dict[str, float]]:
        """Execute account rebalancing."""
        try:
            from bucket_strategy import rebalance_accounts
            
            new_balances, transactions, rebal_dl = rebalance_accounts(
                balances=balances,
                expenses=expenses,
                roth_conversion=roth_conversion,
                year=year,
                age_primary=age_primary,
                stage=self.name,
                federal_tax=total_tax,
                irmaa_penalty=irmaa_penalty,
                aca_premium=aca_premium,
                medical_costs=0.0,
                brokerage_account=brokerage_account,
            )
            
            return new_balances, transactions
        except Exception as e:
            logger.warning(f"Could not execute rebalancing: {e}")
            return balances, {
                'cash_replenishment': 0.0,
                'brokerage_replenishment': 0.0,
                'traditional_to_cash': 0.0,
                'traditional_to_brokerage': 0.0,
                'brokerage_to_cash': 0.0,
                'roth_to_cash': 0.0,
                'roth_to_brokerage': 0.0,
                'conversion_executed': 0.0,
                'brokerage_ltcg': 0.0
            }
    
    def _ensure_standard_deduction_target(
        self,
        balances: PortfolioBalances,
        transactions: Dict[str, float],
        taxable_ss: float,
        roth_conversion: float,
        min_ordinary_income_target: float,
        year: int
    ) -> Tuple[PortfolioBalances, Dict[str, float]]:
        """Ensure 90% standard deduction target is met with ordinary income."""
        trad_withdrawal_so_far = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage']
        ordinary_income_so_far = taxable_ss + roth_conversion + trad_withdrawal_so_far
        
        if ordinary_income_so_far < min_ordinary_income_target and balances.traditional > 0:
            additional_needed = min_ordinary_income_target - ordinary_income_so_far
            additional_withdrawal = min(additional_needed, balances.traditional)
            
            balances = PortfolioBalances(
                cash=balances.cash + additional_withdrawal,
                taxable=balances.taxable,
                traditional=balances.traditional - additional_withdrawal,
                roth=balances.roth,
                daf=balances.daf
            )
            transactions['traditional_to_cash'] += additional_withdrawal
            
            logger.info(f"Year {year}: Added ${additional_withdrawal:,.0f} Traditional withdrawal to reach 90% std deduction target")
            
            self._log_decision(
                None, 'tax_strategy', 'Standard Deduction Optimization (0% Tax)',
                f'Added ${additional_withdrawal:,.0f} Traditional withdrawal',
                f'Reached 90% of standard deduction target',
                additional_withdrawal=additional_withdrawal
            )
        elif ordinary_income_so_far >= min_ordinary_income_target:
            logger.info(f"Year {year}: Ordinary income ${ordinary_income_so_far:,.0f} already meets target")
        
        return balances, transactions
    
    def _calculate_taxes(
        self,
        agi: float,
        deduction: float,
        ltcg: float,
        year: int,
        filing_status: str
    ) -> Tuple[float, float]:
        """Calculate federal and capital gains taxes."""
        try:
            from load_data import get_income_tax_brackets, get_cap_gains_brackets
            from calculations import calculate_taxable_income, calculate_cap_gains
            import pandas as pd
            
            tax_brackets = get_income_tax_brackets(year)
            cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
            
            taxable_income = agi - deduction
            result = calculate_taxable_income(taxable_income, tax_brackets)
            federal_tax = result.total_tax
            
            cg_tax = calculate_cap_gains(taxable_income - ltcg, cg_brackets, ltcg)
            
            return federal_tax, cg_tax
        except Exception as e:
            logger.warning(f"Could not calculate taxes: {e}")
            return 0.0, 0.0
    
    def _calculate_state_tax(
        self,
        agi: float,
        year: int,
        filing_status: str,
        trad_withdrawal: float,
        roth_conversion: float,
        taxable_ss: float
    ) -> float:
        """Calculate state income tax."""
        try:
            from calculations import calculate_state_tax
            
            state_tax, _ = calculate_state_tax(
                state_agi=agi,
                year=year,
                filing_status=filing_status,
                retirement_income=trad_withdrawal + roth_conversion,
                ss_benefits=taxable_ss
            )
            
            logger.info(f"Year {year}: State tax calculated: ${state_tax:,.2f}")
            return state_tax
        except Exception as e:
            logger.warning(f"Could not calculate state tax: {e}")
            return 0.0
    
    # ==================== Decision Logging ====================
    
    def _log_ss_income(self, strategy: YearlyStrategy, ss_benefits: float, taxable_ss: float) -> None:
        """Log Social Security income decision."""
        ss_tax_pct = (taxable_ss / ss_benefits * 100) if ss_benefits > 0 else 0
        self._log_decision(
            strategy, 'ss_decisions', 'Social Security Income',
            f'${ss_benefits:,.0f}/yr (${taxable_ss:,.0f} taxable = {ss_tax_pct:.1f}%)',
            f'Social Security taxation uses IRS formula based on combined income. At this income level, {ss_tax_pct:.1f}% of SS benefits are taxable.',
            ss_benefits=ss_benefits,
            taxable_ss=taxable_ss,
            taxable_ss_pct=ss_tax_pct
        )
    
    def _log_irmaa_assessment(
        self,
        strategy: YearlyStrategy,
        irmaa_penalty: float,
        prior_magi: float,
        age_primary: int,
        age_spouse: int,
        irmaa_headroom: float,
        year: int
    ) -> None:
        """Log IRMAA assessment decision."""
        people_on_medicare = sum([age_primary >= MEDICARE_AGE, age_spouse >= MEDICARE_AGE])
        self._log_decision(
            strategy, 'irmaa_decisions', 'IRMAA Assessment',
            f'${irmaa_penalty:,.0f} penalty ({people_on_medicare} person(s) on Medicare)',
            'IRMAA is based on MAGI from 2 years prior. Roth conversions are capped at IRMAA headroom.',
            prior_magi=prior_magi,
            people_on_medicare=people_on_medicare,
            irmaa_headroom=irmaa_headroom
        )
    
    def _log_roth_conversion_decision(
        self,
        strategy: YearlyStrategy,
        roth_conversion: float,
        optimal_amount: float,
        age_primary: int,
        age_spouse: int,
        aca_info: Dict[str, Any],
        balances: PortfolioBalances,
        year: int = 0
    ) -> None:
        """Log Roth conversion decision."""
        older_age = max(age_primary, age_spouse)
        birth_year_primary = year - age_primary if year and age_primary else 1960
        birth_year_spouse = year - age_spouse if year and age_spouse else 1960
        rmd_age = get_rmd_age(max(birth_year_primary, birth_year_spouse))
        years_to_rmd = max(0, rmd_age - older_age)
        
        if roth_conversion > 0 and roth_conversion < optimal_amount:
            constraint_reason = "IRMAA"
            if aca_info['applicable'] and aca_info['preserved']:
                constraint_reason = "ACA subsidy preservation"
            
            self._log_decision(
                strategy, 'roth_conversion', 'Roth Conversion',
                f'Convert ${roth_conversion:,.0f} ({constraint_reason}-limited)',
                f'BETR recommended ${optimal_amount:,.0f} but limited by {constraint_reason}. {years_to_rmd} years until RMDs.',
                roth_conversion=roth_conversion,
                optimal_amount=optimal_amount,
                years_to_rmd=years_to_rmd
            )
        elif roth_conversion > 0:
            self._log_decision(
                strategy, 'roth_conversion', 'Roth Conversion',
                f'Convert ${roth_conversion:,.0f} (with SS income)',
                f'BETR recommended this conversion. Fits within all constraints. {years_to_rmd} years until RMDs.',
                roth_conversion=roth_conversion,
                years_to_rmd=years_to_rmd
            )
        else:
            self._log_decision(
                strategy, 'roth_conversion', 'Roth Conversion',
                'No conversion',
                f'BETR did not recommend conversion, or SS income plus constraints left no room. {years_to_rmd} years until RMDs.',
                years_to_rmd=years_to_rmd
            )
    
    def _log_rmd_planning_outlook(
        self,
        strategy: YearlyStrategy,
        age_primary: int,
        age_spouse: int,
        roth_conversion: float,
        balances: PortfolioBalances,
        year: int = 0
    ) -> None:
        """Log RMD planning outlook."""
        older_age = max(age_primary, age_spouse)
        birth_year_primary = year - age_primary if year and age_primary else 1960
        birth_year_spouse = year - age_spouse if year and age_spouse else 1960
        rmd_age = get_rmd_age(max(birth_year_primary, birth_year_spouse))
        years_to_rmd = max(0, rmd_age - older_age)
        
        if years_to_rmd > 0 and years_to_rmd <= 10:
            projected_rmd = balances.traditional / 26.5
            total_conversion_capacity = roth_conversion * years_to_rmd if roth_conversion > 0 else 0
            projected_balance_at_rmd = max(0, balances.traditional - total_conversion_capacity)
            projected_rmd_reduced = projected_balance_at_rmd / 26.5
            
            self._log_decision(
                strategy, 'rmd_decisions', 'RMD Planning Outlook',
                f'{years_to_rmd} years until RMDs (age {rmd_age})',
                f'At current conversion rate, could reduce first RMD from ${projected_rmd:,.0f} to ${projected_rmd_reduced:,.0f}',
                years_to_rmd=years_to_rmd,
                projected_first_rmd=projected_rmd_reduced
            )
    
    def _log_daf_conversion_enhancement(
        self,
        strategy: YearlyStrategy,
        daf_contribution: float,
        daf_tax_excess: float,
        daf_enhanced_conversion: float,
        total_roth_conversion: float,
        irmaa_headroom: float,
        aca_info: Dict[str, Any]
    ) -> None:
        """Log DAF conversion enhancement decision."""
        constraint_note = ""
        if aca_info['applicable'] and aca_info['headroom'] < float('inf'):
            constraint_note = " while preserving ACA subsidies"
        elif irmaa_headroom < float('inf'):
            constraint_note = " while staying within IRMAA constraints"
        
        self._log_decision(
            strategy, 'tax_strategy', 'DAF Conversion Optimization',
            f'Increased Roth conversion by ${daf_enhanced_conversion:,.0f}',
            f'DAF contribution (${daf_contribution:,.0f}) creates ${daf_tax_excess:,.0f} of additional deduction. '
            f'This allows ${daf_enhanced_conversion:,.0f} more Roth conversion at same effective tax rate{constraint_note}.',
            daf_contribution=daf_contribution,
            daf_tax_excess=daf_tax_excess,
            additional_conversion=daf_enhanced_conversion,
            total_conversion=total_roth_conversion
        )
