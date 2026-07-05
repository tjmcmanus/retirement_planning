"""
Stage 7: Surviving Spouse

Refactored implementation using BaseLifeStageStrategy with dependency injection.
Handles the surviving spouse stage after one spouse has passed away.
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


class Stage7SurvivingSpouse(BaseLifeStageStrategy):
    """
    Stage 7: Surviving Spouse
    
    Applies when one spouse has passed away and the survivor continues planning.
    
    Key characteristics:
    - Single filer tax status (less favorable brackets than MFJ)
    - Survivor receives higher of own SS benefit or 100% of deceased spouse's benefit
    - Survivor maintains own Medicare coverage (single person IRMAA)
    - More conservative Roth conversion strategy due to single filer brackets
    - Inherited IRA RMDs follow beneficiary rules
    - Focus on tax-efficient withdrawal with higher tax burden
    - Estate planning considerations
    """
    
    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """
        Initialize Stage 7 Surviving Spouse strategy.
        
        Args:
            tax_calculator: Tax calculator for tax computations
            account_manager: Account manager for withdrawals/conversions
        """
        super().__init__(
            name="Stage 7: Surviving Spouse",
            description="Single filer with survivor benefits - managing transition after spouse's death",
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
        
        Stage 7 applies when surviving_spouse_mode is enabled and year > year of death.
        This stage takes precedence over all other stages when activated.
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            True if in surviving spouse mode and past year of death
        """
        try:
            from config import get_config_manager
            
            config_mgr = get_config_manager()
            surviving_spouse_mode = config_mgr.get("personal_info", "surviving_spouse_mode", False)
            
            if not surviving_spouse_mode:
                return False
            
            # Check if we're past the date of death
            date_of_death = config_mgr.get("personal_info", "date_of_death", None)
            if not date_of_death:
                return False
            
            year_of_death = int(date_of_death.split('-')[0])
            # Stage 7 applies starting the year AFTER death (year of death uses MFJ)
            return year > year_of_death
        except Exception as e:
            logger.warning(f"Could not determine Stage 7 applicability: {e}")
            return False
    
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate withdrawal strategy for surviving spouse stage.
        
        Similar to Stage 6 (RMD) but with:
        - Single filer tax status (less favorable brackets)
        - Survivor Social Security benefits (higher of two)
        - More conservative Roth conversions (50% of available room)
        - Single person IRMAA calculation
        - Estate planning considerations
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            **kwargs: Additional parameters including:
                - age_primary, age_spouse: Ages
                - ss_benefits: Social Security benefits (survivor benefit)
                - prior_magi: MAGI from 2 years ago (for IRMAA)
                - brokerage_account: BrokerageAccount object
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
        brokerage_account = kwargs.get('brokerage_account')
        growth_rate = kwargs.get('growth_rate', 1.07)
        start_year = kwargs.get('start_year', year)
        
        logger.debug(f"Stage 7 (Surviving Spouse) calculation for year {year}")
        
        # Determine survivor's age
        survivor_age = self._get_survivor_age(age_primary, age_spouse)
        
        # IMPORTANT: Use Single filing status for Stage 7
        filing_status = "Single"
        logger.info(f"Stage 7: Using Single filing status (survivor age: {survivor_age})")
        
        # Create base strategy object
        strategy = self._create_yearly_strategy(
            year, survivor_age, 0, balances  # No spouse age
        )
        
        # Get standard deduction for single filer
        std_deduction = self._get_standard_deduction(year, filing_status)
        
        # Calculate RMD if applicable
        rmd_amount = self._calculate_rmd(survivor_age, balances.traditional)
        logger.debug(f"RMD amount: ${rmd_amount:,.2f}")
        
        # Calculate healthcare costs (survivor's Medicare only)
        healthcare_costs = self._calculate_healthcare_costs(
            survivor_age, prior_magi, year, filing_status
        )
        
        # Calculate buffer needs
        cash_need, taxable_need = self._calculate_buffer_needs(
            expenses, year, start_year, balances
        )
        
        # Calculate taxable SS (survivor receives higher benefit)
        taxable_ss = ss_benefits * TAXABLE_SS_RATE
        
        # Initial income includes RMD and taxable SS
        total_income = taxable_ss + rmd_amount
        
        # Calculate withdrawal need
        withdrawal_need = max(0, expenses + healthcare_costs['irmaa_penalty'] - ss_benefits - rmd_amount)
        
        # Harvest LTCG conservatively (up to 15% bracket for single filer)
        ltcg_harvested, basis_returned, balances = self._harvest_ltcg_conservative(
            balances, total_income, std_deduction, year, brokerage_account
        )
        total_income += ltcg_harvested
        
        # Conservative Roth conversion for single filer
        roth_conversion = self._calculate_conservative_roth_conversion(
            total_income, std_deduction, balances, rmd_amount, year
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
        
        # Calculate DAF contribution
        daf_contribution, daf_tax_excess = self._calculate_daf_contribution(
            survivor_age, std_deduction, agi, year, filing_status,
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
            balances_for_rebalance, expenses, roth_conversion, year, survivor_age,
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
                f'${rmd_amount:,.0f} from Traditional IRA',
                f'RMD required at age {survivor_age}',
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
        magi = agi
        
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
                daf_contribution=daf_contribution
            )
        
        # Get cost basis ratios
        if brokerage_account:
            brokerage_ltcg_ratio = brokerage_account.ltcg_ratio
            brokerage_basis_ratio = brokerage_account.basis_ratio
        else:
            brokerage_ltcg_ratio = BROKERAGE_LTCG_RATIO
            brokerage_basis_ratio = BROKERAGE_COST_BASIS_RATIO
        
        # Log key decisions
        self._log_stage_info(strategy, survivor_age, filing_status)
        self._log_ss_income(strategy, ss_benefits, taxable_ss)
        self._log_irmaa_assessment(strategy, healthcare_costs['irmaa_penalty'], prior_magi, survivor_age)
        self._log_roth_conversion_decision(strategy, roth_conversion)
        if ltcg_harvested > 0:
            self._log_ltcg_harvest(strategy, ltcg_harvested)
        
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
    
    def _get_survivor_age(self, age_primary: int, age_spouse: int) -> int:
        """Determine survivor's age based on who passed away."""
        try:
            from config import get_config_manager
            
            config_mgr = get_config_manager()
            decedent_person = config_mgr.get("personal_info", "decedent_person", "person1")
            return age_spouse if decedent_person == "person1" else age_primary
        except Exception as e:
            logger.warning(f"Could not determine survivor age: {e}, using primary age")
            return age_primary
    
    def _get_standard_deduction(self, year: int, filing_status: str) -> float:
        """Get standard deduction for single filer."""
        try:
            from load_data import get_std_deduction
            std_deduction_df = get_std_deduction(year, filing_status)
            return std_deduction_df.iloc[0]['deduction']
        except Exception as e:
            logger.warning(f"Could not get standard deduction: {e}")
            return 14600.0  # 2024 single filer default
    
    def _calculate_rmd(self, survivor_age: int, traditional_balance: float) -> float:
        """Calculate Required Minimum Distribution."""
        try:
            from load_data import get_rmd_value
            rmd_rate = get_rmd_value(survivor_age)
            if rmd_rate > 0 and traditional_balance > 0:
                return traditional_balance / rmd_rate
        except Exception as e:
            logger.warning(f"Could not calculate RMD: {e}")
        
        return 0.0
    
    def _calculate_healthcare_costs(
        self,
        survivor_age: int,
        prior_magi: float,
        year: int,
        filing_status: str
    ) -> dict:
        """Calculate healthcare costs for survivor (single person Medicare)."""
        try:
            from strategy import calculate_total_healthcare_costs
            
            # For Stage 7, only one person on Medicare
            healthcare_total, healthcare_breakdown = calculate_total_healthcare_costs(
                age_primary=survivor_age,
                age_spouse=0,  # No spouse
                magi_two_years_ago=prior_magi,
                year=year,
                filing_status=filing_status,
                has_medigap=True
            )
            
            medical_costs = healthcare_breakdown.medicare
            aca_premium = healthcare_breakdown.pre_medicare + healthcare_breakdown.preretirement_working
            irmaa_penalty = healthcare_breakdown.medicare_detail.get('irmaa_penalty', 0.0)
            
            if medical_costs > 0:
                logger.info(f"Stage 7: Medicare costs=${medical_costs:,.2f} (IRMAA=${irmaa_penalty:,.2f})")
            
            return {
                'medical_costs': medical_costs,
                'aca_premium': aca_premium,
                'irmaa_penalty': irmaa_penalty
            }
        except Exception as e:
            logger.warning(f"Could not calculate healthcare costs: {e}")
            return {
                'medical_costs': 0.0,
                'aca_premium': 0.0,
                'irmaa_penalty': 0.0
            }
    
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
    
    def _harvest_ltcg_conservative(
        self,
        balances: PortfolioBalances,
        total_income: float,
        std_deduction: float,
        year: int,
        brokerage_account: Any
    ) -> Tuple[float, float, PortfolioBalances]:
        """Harvest LTCG conservatively up to 15% bracket for single filer."""
        ltcg_harvested = 0.0
        basis_returned = 0.0
        
        if balances.taxable <= 0:
            return ltcg_harvested, basis_returned, balances
        
        try:
            from load_data import get_cap_gains_brackets
            import pandas as pd
            
            cg_brackets = pd.DataFrame(get_cap_gains_brackets(year))
            
            # Find 15% bracket limit (more conservative for single filer)
            cg_15_percent = pd.DataFrame(cg_brackets[cg_brackets['rate'] == 0.15])
            if len(cg_15_percent) > 0:
                cg_15_percent_limit = float(cg_15_percent['upper'].iloc[0])
                ltcg_room = max(0, cg_15_percent_limit - total_income - std_deduction)
                
                if ltcg_room > 1000:  # Only harvest if meaningful room
                    # Conservative 10% harvest for Stage 7
                    max_harvest = min(ltcg_room, balances.taxable * 0.10)
                    
                    # Get actual LTCG ratio
                    actual_ltcg_ratio = brokerage_account.ltcg_ratio if brokerage_account else BROKERAGE_LTCG_RATIO
                    
                    # Calculate withdrawal amount
                    max_brokerage_withdrawal = min(
                        max_harvest / actual_ltcg_ratio if actual_ltcg_ratio > 0 else max_harvest,
                        balances.taxable * 0.10
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
                    
                    logger.info(f"Stage 7: Harvested ${ltcg_harvested:,.2f} LTCG (room to 15%: ${ltcg_room:,.2f})")
        except Exception as e:
            logger.warning(f"Could not harvest LTCG: {e}")
        
        return ltcg_harvested, basis_returned, balances
    
    def _calculate_conservative_roth_conversion(
        self,
        total_income: float,
        std_deduction: float,
        balances: PortfolioBalances,
        rmd_amount: float,
        year: int
    ) -> float:
        """Calculate conservative Roth conversion for single filer (50% of available room)."""
        roth_conversion = 0.0
        
        try:
            from load_data import get_income_tax_brackets
            from calculations import get_stage_specific_conversion_rate

            stage_max_conversion_rate = get_stage_specific_conversion_rate(self.name)

            tax_brackets = get_income_tax_brackets(year)

            # Find the target bracket (rate column is decimal, e.g. 0.15)
            target_bracket_max = 0
            for _, row in tax_brackets.iterrows():
                if row['rate'] <= stage_max_conversion_rate:
                    target_bracket_max = row['max']
            
            # Calculate conversion room
            agi_before_conversion = total_income
            conversion_room = max(0, target_bracket_max - agi_before_conversion)
            
            # Be conservative - only use 50% of available room for Stage 7
            if conversion_room > 1000 and balances.traditional > rmd_amount:
                roth_conversion = min(
                    conversion_room * 0.5,  # Only 50% of room
                    balances.traditional - rmd_amount  # Don't convert more than available
                )
                logger.info(f"Stage 7: Roth conversion ${roth_conversion:,.2f} (conservative, 50% of ${conversion_room:,.2f} room)")
        except Exception as e:
            logger.warning(f"Could not calculate Roth conversion: {e}")
        
        return roth_conversion
    
    def _calculate_daf_contribution(
        self,
        survivor_age: int,
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
                survivor_age, 0, std_deduction, state_tax, property_tax, taxable_balance
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
        survivor_age: int,
        total_tax: float,
        healthcare_costs: dict,
        brokerage_account: Any
    ) -> Tuple[PortfolioBalances, dict]:
        """Execute account rebalancing."""
        try:
            from bucket_strategy import rebalance_accounts
            
            new_balances, transactions, rebal_dl = rebalance_accounts(
                balances=balances,
                expenses=expenses,
                roth_conversion=roth_conversion,
                year=year,
                age_primary=survivor_age,
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
        """Calculate federal and capital gains taxes."""
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
    
    def _log_stage_info(self, strategy: YearlyStrategy, survivor_age: int, filing_status: str) -> None:
        """Log stage information."""
        self._log_decision(
            strategy, 'stage_info', 'Life Stage',
            'Stage 7: Surviving Spouse',
            f'Single filer status with survivor benefits. More conservative tax planning due to less favorable single filer brackets. Survivor age: {survivor_age}',
            filing_status=filing_status,
            survivor_age=survivor_age
        )
    
    def _log_ss_income(self, strategy: YearlyStrategy, ss_benefits: float, taxable_ss: float) -> None:
        """Log Social Security income decision."""
        self._log_decision(
            strategy, 'ss_decisions', 'Social Security Income',
            f'${ss_benefits:,.0f}/yr (${taxable_ss:,.0f} taxable) - Survivor Benefit',
            f'Survivor receives the higher of their own benefit or 100% of deceased spouse\'s benefit. Up to {TAXABLE_SS_RATE:.0%} is taxable.',
            ss_benefits=ss_benefits,
            taxable_ss=taxable_ss
        )
    
    def _log_irmaa_assessment(
        self,
        strategy: YearlyStrategy,
        irmaa_penalty: float,
        prior_magi: float,
        survivor_age: int
    ) -> None:
        """Log IRMAA assessment decision."""
        self._log_decision(
            strategy, 'irmaa_decisions', 'IRMAA Assessment',
            f'${irmaa_penalty:,.0f} penalty (single person on Medicare)',
            'IRMAA is based on MAGI from 2 years prior. Single filer IRMAA brackets apply.',
            prior_magi=prior_magi,
            survivor_age=survivor_age
        )
    
    def _log_roth_conversion_decision(self, strategy: YearlyStrategy, roth_conversion: float) -> None:
        """Log Roth conversion decision."""
        if roth_conversion > 0:
            self._log_decision(
                strategy, 'roth_conversion', 'Roth Conversion',
                f'Convert ${roth_conversion:,.0f} (conservative for single filer)',
                'Stage 7 uses conservative conversions (50% of available room) due to less favorable single filer tax brackets.',
                roth_conversion=roth_conversion
            )
        else:
            self._log_decision(
                strategy, 'roth_conversion', 'Roth Conversion',
                'No conversion',
                'No conversion room available or not beneficial for single filer brackets.',
                roth_conversion=0
            )
    
    def _log_ltcg_harvest(self, strategy: YearlyStrategy, ltcg_harvested: float) -> None:
        """Log LTCG harvest decision."""
        self._log_decision(
            strategy, 'ltcg_decisions', 'LTCG Harvest',
            f'Harvested ${ltcg_harvested:,.0f} from brokerage',
            'Conservative LTCG harvest up to 15% bracket for single filer',
            ltcg_harvested=ltcg_harvested
        )

# Made with Bob
