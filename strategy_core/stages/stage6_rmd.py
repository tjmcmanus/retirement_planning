"""
Stage 6: RMD (Required Minimum Distributions)

Refactored implementation using BaseLifeStageStrategy with dependency injection.
Handles the RMD stage where required distributions from Traditional accounts begin.
"""

import logging
from typing import Any, Optional, Tuple

from ..base_strategy import BaseLifeStageStrategy
from ..interfaces import ITaxCalculator, IAccountManager
from ..models import PortfolioBalances, YearlyStrategy

logger = logging.getLogger(__name__)

# Constants
MEDICARE_AGE = 65
TAXABLE_SS_RATE = 0.85  # Up to 85% of SS benefits are taxable
BROKERAGE_LTCG_RATIO = 0.60  # Fallback: 60% LTCG
BROKERAGE_COST_BASIS_RATIO = 0.40  # Fallback: 40% cost basis


def get_rmd_age(birth_year: int) -> int:
    """
    Calculate RMD starting age based on birth year (SECURE 2.0 Act).
    
    Args:
        birth_year: Year of birth
        
    Returns:
        RMD starting age
        
    Rules (SECURE 2.0 Act):
    - Born before 1951: Age 72
    - Born 1951-1959: Age 73
    - Born 1960 or later: Age 75
    """
    if birth_year < 1951:
        return 72
    elif birth_year <= 1959:
        return 73
    else:  # 1960 or later
        return 75


class Stage6RMD(BaseLifeStageStrategy):
    """
    Stage 6: RMD (Required Minimum Distributions)
    
    - Required Minimum Distributions from Traditional accounts
    - Social Security benefits + Medicare costs
    - RMDs may push into higher tax brackets
    - Limited Roth conversion opportunity (only if RMD doesn't fill bracket)
    - Focus on tax-efficient withdrawal sequencing
    - IRMAA optimization with 2-year lookback
    """
    
    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """
        Initialize Stage 6 RMD strategy.
        
        Args:
            tax_calculator: Tax calculator for tax computations
            account_manager: Account manager for withdrawals/conversions
        """
        super().__init__(
            name="Stage 6: RMD",
            description="RMD age - managing required distributions with SS and Medicare",
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
        
        Stage 6 applies when either spouse reaches RMD age (varies by birth year).
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            True if either spouse is at or above RMD age
        """
        # Calculate birth years
        birth_year_primary = year - age_primary
        birth_year_spouse = year - age_spouse
        
        # Get RMD ages based on birth years
        rmd_age_primary = get_rmd_age(birth_year_primary)
        rmd_age_spouse = get_rmd_age(birth_year_spouse)
        
        return age_primary >= rmd_age_primary or age_spouse >= rmd_age_spouse
    
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate withdrawal strategy for RMD stage.
        
        Key features:
        - Calculate and execute mandatory RMD
        - Optimize LTCG harvesting at 15% bracket (not 0% - RMD fills lower brackets)
        - Limited Roth conversions only if RMD doesn't fill target bracket
        - IRMAA-aware conversions with 2-year lookback
        - DAF optimization for tax efficiency
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            **kwargs: Additional parameters including:
                - age_primary: Primary person's age
                - age_spouse: Spouse's age
                - ss_benefits: Social Security benefits
                - prior_magi: MAGI from 2 years ago (for IRMAA)
                - filing_status: Tax filing status
                - brokerage_account: BrokerageAccount object for LTCG tracking
                - growth_rate: Portfolio growth rate
                - start_year: Simulation start year
                
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
        
        logger.debug(f"Stage 6 (RMD) calculation for year {year}")
        
        # Create base strategy object
        strategy = self._create_yearly_strategy(
            year, age_primary, age_spouse, balances
        )
        
        # Calculate RMD (mandatory distribution)
        rmd_amount = self._calculate_rmd(age_primary, year, balances.traditional)
        logger.debug(f"RMD amount: ${rmd_amount:,.2f}")
        
        # Calculate healthcare costs (Medicare for both at this stage)
        healthcare_costs = self._calculate_healthcare_costs(
            age_primary, age_spouse, prior_magi, year, filing_status
        )
        
        # Calculate buffer targets
        cash_need, taxable_need = self._calculate_buffer_needs(
            expenses, year, start_year, balances
        )
        
        # Calculate taxable SS
        taxable_ss = ss_benefits * TAXABLE_SS_RATE
        
        # Initial income includes RMD (required) and taxable SS
        total_income = taxable_ss + rmd_amount

        # Calculate withdrawal need after SS, RMD, and full healthcare costs
        withdrawal_need = max(0, expenses + healthcare_costs['total'] - ss_benefits - rmd_amount)
        
        # Harvest LTCG if beneficial (at 15% bracket, not 0% - RMD fills lower brackets)
        ltcg_harvested, basis_returned, balances = self._harvest_ltcg_for_withdrawals(
            withdrawal_need, balances, total_income, year, brokerage_account
        )
        total_income += ltcg_harvested
        
        # Get standard deduction
        std_deduction = self._get_standard_deduction(year, filing_status)
        
        # Limited Roth conversion opportunity (only if RMD doesn't fill bracket)
        roth_conversion = self._calculate_rmd_limited_roth_conversion(
            total_income, std_deduction, balances, rmd_amount, prior_magi, year, filing_status
        )
        total_income += roth_conversion
        
        # Calculate initial taxes
        agi = total_income
        taxable_income = agi - std_deduction
        federal_tax, cg_tax = self._calculate_taxes(
            taxable_income, ltcg_harvested, year, filing_status
        )
        total_tax = federal_tax + cg_tax
        
        # Add SS benefits to cash before rebalancing
        balances_with_ss = PortfolioBalances(
            cash=balances.cash + ss_benefits,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth,
            daf=balances.daf
        )
        logger.info(f"Year {year}: Added SS benefits ${ss_benefits:,.2f} to cash")
        
        # Calculate DAF contribution (before rebalancing)
        daf_contribution, daf_tax_excess = self._calculate_daf_contribution(
            age_primary, age_spouse, std_deduction, agi, year, filing_status,
            balances_with_ss.taxable
        )
        
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
            total_tax, healthcare_costs, brokerage_account
        )
        
        # Apply RMD (mandatory distribution from Traditional to Brokerage)
        if rmd_amount > 0:
            new_balances = PortfolioBalances(
                cash=new_balances.cash,
                taxable=new_balances.taxable + rmd_amount,
                traditional=new_balances.traditional - rmd_amount,
                roth=new_balances.roth,
                daf=new_balances.daf
            )
            logger.info(f"Year {year}: RMD ${rmd_amount:,.0f} distributed to Brokerage")
            
            self._log_decision(
                strategy, 'rmd_decisions', 'Required Minimum Distribution',
                f'${rmd_amount:,.0f} distributed from Traditional to Brokerage',
                f'RMD is mandatory at age {age_primary}',
                rmd_amount=rmd_amount
            )
        
        # Apply growth
        new_balances = PortfolioBalances(
            cash=new_balances.cash,
            taxable=new_balances.taxable * growth_rate,
            traditional=new_balances.traditional * growth_rate,
            roth=new_balances.roth * growth_rate,
            daf=new_balances.daf * growth_rate
        )
        
        # Calculate final AGI and MAGI
        trad_withdrawal = transactions['traditional_to_cash'] + transactions['traditional_to_brokerage'] + rmd_amount
        brokerage_ltcg = transactions.get('brokerage_ltcg', 0.0)
        total_ltcg = ltcg_harvested + brokerage_ltcg
        
        agi = (taxable_ss + trad_withdrawal + roth_conversion + total_ltcg)
        magi = agi  # MAGI same as AGI in Stage 6
        
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
        
        # If DAF contribution made, recalculate federal tax with increased deduction
        if daf_contribution > 0:
            new_balances = PortfolioBalances(
                cash=new_balances.cash,
                taxable=new_balances.taxable - daf_contribution,  # Subtract DAF from taxable
                traditional=new_balances.traditional,
                roth=new_balances.roth,
                daf=new_balances.daf + daf_contribution
            )
            
            # Recalculate taxes with DAF deduction
            effective_deduction = std_deduction + daf_tax_excess
            taxable_income_with_daf = agi - effective_deduction
            federal_tax, cg_tax = self._calculate_taxes(
                taxable_income_with_daf, total_ltcg, year, filing_status
            )
            total_tax = federal_tax + cg_tax
            
            logger.info(f"Year {year}: Federal tax reduced by DAF deduction (excess: ${daf_tax_excess:,.0f})")
            
            self._log_decision(
                strategy, 'daf_decisions', 'DAF Contribution',
                f'${daf_contribution:,.0f} contributed to DAF',
                f'Tax excess: ${daf_tax_excess:,.0f}',
                daf_contribution=daf_contribution,
                daf_tax_excess=daf_tax_excess
            )
        
        # Get cost basis ratios
        if brokerage_account:
            brokerage_ltcg_ratio = brokerage_account.ltcg_ratio
            brokerage_basis_ratio = brokerage_account.basis_ratio
        else:
            brokerage_ltcg_ratio = BROKERAGE_LTCG_RATIO
            brokerage_basis_ratio = BROKERAGE_COST_BASIS_RATIO
        
        # Log key decisions
        self._log_ss_income(strategy, ss_benefits, taxable_ss)
        self._log_irmaa_assessment(strategy, healthcare_costs['irmaa_penalty'], prior_magi, age_primary, age_spouse)
        self._log_ltcg_harvest(strategy, ltcg_harvested)
        self._log_roth_conversion_decision(strategy, roth_conversion, rmd_amount, taxable_ss)
        
        # Populate strategy object
        strategy.wages = 0
        strategy.ss_benefits = ss_benefits
        strategy.rmd_amount = rmd_amount
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
        strategy.healthcare_costs = healthcare_costs['total']
        strategy.irmaa_penalty = healthcare_costs['irmaa_penalty']
        strategy.aca_premium = healthcare_costs['aca_premium']
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
    
    # ==================== Helper Methods ====================
    
    def _calculate_rmd(self, age_primary: int, year: int, traditional_balance: float) -> float:
        """
        Calculate Required Minimum Distribution based on birth year.
        
        Args:
            age_primary: Primary person's age
            year: Current year
            traditional_balance: Traditional IRA balance
            
        Returns:
            RMD amount
        """
        logger.info(f"RMD calculation: age={age_primary}, year={year}, traditional_balance=${traditional_balance:,.2f}")
        
        # Calculate birth year and RMD age
        birth_year = year - age_primary
        rmd_age = get_rmd_age(birth_year)
        
        logger.info(f"Birth year: {birth_year}, RMD age: {rmd_age}")
        
        # Check age requirement
        if age_primary < rmd_age:
            logger.info(f"RMD not required: age {age_primary} < {rmd_age} (born {birth_year})")
            return 0.0
        
        # Check balance requirement
        if traditional_balance <= 0:
            logger.info(f"RMD not required: traditional balance is ${traditional_balance:,.2f}")
            return 0.0
        
        try:
            from calculations import get_rmd_value
            rmd_rate = get_rmd_value(age_primary)
            logger.info(f"RMD rate for age {age_primary}: {rmd_rate}")
            
            if rmd_rate > 0 and traditional_balance > 0:
                rmd = traditional_balance / rmd_rate
                logger.info(f"RMD calculated: ${rmd:,.2f} (balance ${traditional_balance:,.2f} / rate {rmd_rate})")
                return rmd
            else:
                logger.warning(f"Invalid RMD rate: {rmd_rate} for age {age_primary}")
                return 0.0
        except Exception as e:
            logger.error(f"Error calculating RMD: {e}", exc_info=True)
            return 0.0
    
    def _calculate_healthcare_costs(
        self,
        age_primary: int,
        age_spouse: int,
        prior_magi: float,
        year: int,
        filing_status: str
    ) -> dict:
        """
        Calculate healthcare costs including Medicare and IRMAA.
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            prior_magi: MAGI from 2 years ago
            year: Current year
            filing_status: Tax filing status
            
        Returns:
            Dictionary with healthcare cost components
        """
        try:
            from strategy import calculate_total_healthcare_costs, get_health_status_from_config
            _health_status = get_health_status_from_config()

            healthcare_total, healthcare_breakdown = calculate_total_healthcare_costs(
                age_primary=age_primary,
                age_spouse=age_spouse,
                magi_two_years_ago=prior_magi,
                year=year,
                filing_status=filing_status,
                health_status=_health_status,
                has_medigap=True
            )

            medical_costs = healthcare_breakdown.medicare
            aca_premium = healthcare_breakdown.pre_medicare + healthcare_breakdown.preretirement_working
            irmaa_penalty = healthcare_breakdown.medicare_detail.get('irmaa_penalty', 0.0)

            if medical_costs > 0:
                logger.info(f"Stage 6: Medicare costs=${medical_costs:,.2f} (IRMAA=${irmaa_penalty:,.2f})")

            return {
                'medical_costs': medical_costs,
                'aca_premium': aca_premium,
                'irmaa_penalty': irmaa_penalty,
                'total': healthcare_total,
            }
        except Exception as e:
            logger.warning(f"Could not calculate healthcare costs: {e}")
            return {
                'medical_costs': 0.0,
                'aca_premium': 0.0,
                'irmaa_penalty': 0.0,
                'total': 0.0,
            }
    
    def _calculate_buffer_needs(
        self,
        expenses: float,
        year: int,
        start_year: int,
        balances: PortfolioBalances
    ) -> Tuple[float, float]:
        """
        Calculate cash and taxable buffer needs.
        
        Args:
            expenses: Annual expenses
            year: Current year
            start_year: Simulation start year
            balances: Current balances
            
        Returns:
            Tuple of (cash_need, taxable_need)
        """
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
    
    def _harvest_ltcg_for_withdrawals(
        self,
        withdrawal_need: float,
        balances: PortfolioBalances,
        total_income: float,
        year: int,
        brokerage_account: Any
    ) -> Tuple[float, float, PortfolioBalances]:
        """
        Harvest LTCG from taxable account at 15% bracket (not 0% - RMD fills lower brackets).
        
        Args:
            withdrawal_need: Amount needed for withdrawals
            balances: Current balances
            total_income: Current total income
            year: Current year
            brokerage_account: BrokerageAccount object
            
        Returns:
            Tuple of (ltcg_harvested, basis_returned, updated_balances)
        """
        ltcg_harvested = 0.0
        basis_returned = 0.0
        
        if withdrawal_need <= 0 or balances.taxable <= 0:
            return ltcg_harvested, basis_returned, balances
        
        try:
            from load_data import get_cap_gains_brackets
            import pandas as pd
            
            cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
            std_deduction = self._get_standard_deduction(year, 'married')
            
            # Target 15% bracket (not 0% - RMD already fills lower brackets)
            cg_15_percent = pd.DataFrame(cg_brackets[cg_brackets['rate'] == 0.15])
            if len(cg_15_percent) > 0:
                cg_15_percent_limit = float(cg_15_percent['upper'].iloc[0])
                ltcg_room = max(0, cg_15_percent_limit - total_income - std_deduction)
                
                # Get actual LTCG ratio
                actual_ltcg_ratio = brokerage_account.ltcg_ratio if brokerage_account else BROKERAGE_LTCG_RATIO
                
                # Calculate maximum withdrawal
                max_brokerage_withdrawal = min(
                    withdrawal_need / actual_ltcg_ratio if actual_ltcg_ratio > 0 else withdrawal_need,
                    ltcg_room / actual_ltcg_ratio if actual_ltcg_ratio > 0 else ltcg_room,
                    balances.taxable * 0.5  # Don't withdraw more than 50%
                )
                
                # Execute withdrawal
                if brokerage_account and max_brokerage_withdrawal > 0:
                    try:
                        basis_returned, ltcg_harvested = brokerage_account.withdraw_fifo(max_brokerage_withdrawal, year)
                    except Exception as e:
                        logger.warning(f"Error withdrawing from brokerage: {e}, using fallback")
                        ltcg_harvested = max_brokerage_withdrawal * BROKERAGE_LTCG_RATIO
                        basis_returned = max_brokerage_withdrawal * BROKERAGE_COST_BASIS_RATIO
                else:
                    ltcg_harvested = max_brokerage_withdrawal * BROKERAGE_LTCG_RATIO
                    basis_returned = max_brokerage_withdrawal * BROKERAGE_COST_BASIS_RATIO
                
                # Move funds from brokerage to cash
                balances = PortfolioBalances(
                    cash=balances.cash + max_brokerage_withdrawal,
                    taxable=balances.taxable - max_brokerage_withdrawal,
                    traditional=balances.traditional,
                    roth=balances.roth,
                    daf=balances.daf
                )
        except Exception as e:
            logger.warning(f"Could not harvest LTCG: {e}")
        
        return ltcg_harvested, basis_returned, balances
    
    def _calculate_rmd_limited_roth_conversion(
        self,
        total_income: float,
        std_deduction: float,
        balances: PortfolioBalances,
        rmd_amount: float,
        prior_magi: float,
        year: int,
        filing_status: str
    ) -> float:
        """
        Calculate limited Roth conversion opportunity after RMD.
        
        Only converts if RMD doesn't fill the target bracket and respects IRMAA headroom.
        
        Args:
            total_income: Current total income
            std_deduction: Standard deduction
            balances: Current balances
            rmd_amount: RMD amount
            prior_magi: MAGI from 2 years ago
            year: Current year
            filing_status: Tax filing status
            
        Returns:
            Roth conversion amount
        """
        roth_conversion = 0.0
        
        try:
            from load_data import get_income_tax_brackets, get_medicare_costs
            from config import get_config_manager
            import pandas as pd
            
            # Get stage-specific conversion rate
            from calculations import get_stage_specific_conversion_rate
            stage_max_conversion_rate = get_stage_specific_conversion_rate(self.name)
            
            tax_brackets = pd.DataFrame(get_income_tax_brackets(year))
            irmaa_brackets = get_medicare_costs(year)
            
            # Find target bracket
            target_bracket = tax_brackets[tax_brackets['rate'] == stage_max_conversion_rate]
            if target_bracket.empty:
                return 0.0
            
            target_bracket_upper = float(target_bracket.iloc[0]['upper'])
            conversion_room = max(0, target_bracket_upper - total_income - std_deduction)
            
            if conversion_room > 10000 and balances.traditional > rmd_amount:
                # Find next IRMAA threshold
                next_irmaa_threshold = float('inf')
                for _, row in irmaa_brackets.iterrows():
                    if row['lower'] <= prior_magi <= row['upper']:
                        next_brackets = pd.DataFrame(irmaa_brackets[irmaa_brackets['lower'] > row['upper']])
                        if not next_brackets.empty:
                            next_irmaa_threshold = float(next_brackets.iloc[0]['lower'])
                        break
                
                irmaa_headroom = next_irmaa_threshold - total_income - std_deduction
                safe_conversion = min(conversion_room, irmaa_headroom, balances.traditional - rmd_amount)
                
                if safe_conversion > 10000:
                    roth_conversion = safe_conversion * 0.5  # Conservative: only 50% of room
                    logger.debug(f"Roth conversion: ${roth_conversion:,.2f} (limited by RMD)")
        except Exception as e:
            logger.warning(f"Could not calculate Roth conversion: {e}")
        
        return roth_conversion
    
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
        """
        Calculate DAF contribution for tax optimization.
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            std_deduction: Standard deduction
            agi: Adjusted Gross Income
            year: Current year
            filing_status: Tax filing status
            taxable_balance: Taxable account balance
            
        Returns:
            Tuple of (daf_contribution, daf_tax_excess)
        """
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
    
    def _execute_rebalancing(
        self,
        balances: PortfolioBalances,
        expenses: float,
        roth_conversion: float,
        year: int,
        age_primary: int,
        total_tax: float,
        healthcare_costs: dict,
        brokerage_account: Any
    ) -> Tuple[PortfolioBalances, dict]:
        """
        Execute account rebalancing.
        
        Args:
            balances: Current balances
            expenses: Annual expenses
            roth_conversion: Roth conversion amount
            year: Current year
            age_primary: Primary person's age
            total_tax: Total tax
            healthcare_costs: Healthcare costs dictionary
            brokerage_account: BrokerageAccount object
            
        Returns:
            Tuple of (new_balances, transactions)
        """
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
                irmaa_penalty=healthcare_costs['irmaa_penalty'],
                aca_premium=healthcare_costs['aca_premium'],
                medical_costs=healthcare_costs['medical_costs'],
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
    
    def _calculate_taxes(
        self,
        taxable_income: float,
        ltcg: float,
        year: int,
        filing_status: str
    ) -> Tuple[float, float]:
        """
        Calculate federal and capital gains taxes.
        
        Args:
            taxable_income: Taxable income
            ltcg: Long-term capital gains
            year: Current year
            filing_status: Tax filing status
            
        Returns:
            Tuple of (federal_tax, cg_tax)
        """
        try:
            from load_data import get_income_tax_brackets, get_cap_gains_brackets
            from calculations import calculate_taxable_income, calculate_cap_gains
            import pandas as pd
            
            tax_brackets = get_income_tax_brackets(year)
            cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
            
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
        """
        Calculate state income tax.
        
        Args:
            agi: Adjusted Gross Income
            year: Current year
            filing_status: Tax filing status
            trad_withdrawal: Traditional withdrawal amount
            roth_conversion: Roth conversion amount
            taxable_ss: Taxable Social Security
            
        Returns:
            State tax amount
        """
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
    
    def _get_standard_deduction(self, year: int, filing_status: str) -> float:
        """Get standard deduction for the year."""
        try:
            from load_data import get_std_deduction
            std_deduction_df = get_std_deduction(year, filing_status)
            return std_deduction_df.iloc[0]['deduction']
        except Exception as e:
            logger.warning(f"Could not get standard deduction: {e}")
            return 29200.0  # 2024 married filing jointly default
    
    # ==================== Decision Logging ====================
    
    def _log_ss_income(self, strategy: YearlyStrategy, ss_benefits: float, taxable_ss: float) -> None:
        """Log Social Security income decision."""
        self._log_decision(
            strategy, 'ss_decisions', 'Social Security Income',
            f'${ss_benefits:,.0f}/yr (${taxable_ss:,.0f} taxable at {TAXABLE_SS_RATE:.0%})',
            f'Up to {TAXABLE_SS_RATE:.0%} of SS benefits are included in taxable income',
            ss_benefits=ss_benefits,
            taxable_ss=taxable_ss
        )
    
    def _log_irmaa_assessment(
        self,
        strategy: YearlyStrategy,
        irmaa_penalty: float,
        prior_magi: float,
        age_primary: int,
        age_spouse: int
    ) -> None:
        """Log IRMAA assessment decision."""
        people_on_medicare = sum([age_primary >= MEDICARE_AGE, age_spouse >= MEDICARE_AGE])
        self._log_decision(
            strategy, 'irmaa_decisions', 'IRMAA Assessment',
            f'${irmaa_penalty:,.0f} penalty ({people_on_medicare} person(s) on Medicare)',
            'IRMAA is based on MAGI from 2 years prior',
            prior_magi=prior_magi,
            people_on_medicare=people_on_medicare
        )
    
    def _log_ltcg_harvest(self, strategy: YearlyStrategy, ltcg_harvested: float) -> None:
        """Log LTCG harvest decision."""
        self._log_decision(
            strategy, 'ltcg_decisions', 'LTCG Harvest',
            f'Harvested ${ltcg_harvested:,.0f} from brokerage',
            'In RMD stage, LTCG is harvested up to 15% bracket (not 0% - RMD fills lower brackets)',
            ltcg_harvested=ltcg_harvested
        )
    
    def _log_roth_conversion_decision(
        self,
        strategy: YearlyStrategy,
        roth_conversion: float,
        rmd_amount: float,
        taxable_ss: float
    ) -> None:
        """Log Roth conversion decision."""
        if roth_conversion > 0:
            self._log_decision(
                strategy, 'roth_conversion', 'Roth Conversion',
                f'Convert ${roth_conversion:,.0f} (conservative, RMD-limited)',
                'Small conversion possible after RMD filled lower brackets. Only 50% of room used.',
                roth_conversion=roth_conversion
            )
        else:
            self._log_decision(
                strategy, 'roth_conversion', 'Roth Conversion',
                'No conversion',
                'RMD plus SS income filled target tax bracket, leaving no room for conversion',
                rmd_amount=rmd_amount,
                taxable_ss=taxable_ss
            )

# Made with Bob
