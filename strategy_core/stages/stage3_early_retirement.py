"""
Stage 3: Early Retirement

Refactored implementation using BaseLifeStageStrategy with dependency injection.
Pre-Medicare, pre-SS retirement phase with focus on ACA optimization and Roth conversions.
"""

import logging
from typing import Any, Optional

from ..base_strategy import BaseLifeStageStrategy
from ..interfaces import ITaxCalculator, IAccountManager
from ..models import PortfolioBalances, YearlyStrategy

logger = logging.getLogger(__name__)

# Constants
MEDICARE_AGE = 65
ACA_FPL_THRESHOLD = 4.0  # 400% of Federal Poverty Level


class Stage3EarlyRetirement(BaseLifeStageStrategy):
    """
    Stage 3: Early Retirement (Pre-Medicare, Pre-SS, Pre-RMD)
    
    - No wages, no SS benefits yet
    - Optimize Roth conversions using BETR (low/no income years)
    - Use LTCG to fund living expenses (0% or 15% rate)
    - Consider ACA subsidies (keep income below 400% FPL)
    - Maintain cash and taxable buffers
    - Standard deduction optimization (90% target for ordinary income)
    """
    
    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """
        Initialize Stage 3 Early Retirement strategy.
        
        Args:
            tax_calculator: Tax calculator for tax computations
            account_manager: Account manager for withdrawals/conversions
        """
        super().__init__(
            name="Stage 3: Early Retirement",
            description="Pre-Medicare, pre-SS, pre-RMD - Roth conversion opportunity with ACA optimization",
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
        Applies when retired but before Medicare and SS.
        
        Requires BOTH spouses to be under Medicare age to maximize the
        Roth conversion window before Medicare/IRMAA considerations begin.
        This is the optimal stage for aggressive Roth conversions.
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            True if this stage applies
        """
        return (
            not has_wages and 
            not has_ss and
            age_primary < MEDICARE_AGE and 
            age_spouse < MEDICARE_AGE
        )
    
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate early retirement strategy with Roth conversions and ACA optimization.
        
        Strategy:
        1. Calculate ACA premium based on age and household size
        2. Determine anticipated buffer needs (cash and taxable)
        3. Reserve Traditional balance for buffer maintenance
        4. Use BETR to optimize Roth conversion amount
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
        filing_status = kwargs.get('filing_status', 'married_filing_jointly')
        state = kwargs.get('state', 'PA')
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        growth_rate = kwargs.get('growth_rate', 1.07)
        brokerage_account = kwargs.get('brokerage_account')
        start_year = kwargs.get('start_year', year)
        
        logger.debug(
            f"Stage 3 calculation for year {year}, expenses=${expenses:,.2f}"
        )
        
        # Create base strategy object
        strategy = self._create_yearly_strategy(
            year, age_primary, age_spouse, balances
        )
        
        # Get standard deduction
        std_deduction = self.tax_calculator.calculate_standard_deduction(
            filing_status, year, age_primary, age_spouse
        )
        
        # Calculate minimum ordinary income target (90% of standard deduction)
        min_ordinary_income_target = std_deduction * 0.90
        
        # Calculate ACA premium
        aca_premium = self._calculate_aca_premium(
            strategy, year, age_primary, age_spouse
        )
        
        # Calculate anticipated buffer needs (lookahead)
        anticipated_needs = self._calculate_anticipated_buffer_needs(
            strategy,
            balances,
            expenses,
            age_primary,
            aca_premium,
            brokerage_account,
            start_year,
            year
        )
        
        # Validate anticipated_needs is a dict
        if not isinstance(anticipated_needs, dict):
            logger.error(f"Stage 3: anticipated_needs is not a dict after _calculate_anticipated_buffer_needs: "
                        f"type={type(anticipated_needs)}, value={anticipated_needs}")
            anticipated_needs = {
                'total_traditional_need': 0.0,
                'traditional_to_cash': 0.0,
                'traditional_to_brokerage': 0.0,
                'estimated_ltcg': 0.0
            }
        
        # ── DAF Traditional → Brokerage pre-fund sizing ───────────────────────
        # Check whether a pre-fund distribution is required this year.
        # When active it takes full precedence:
        #   • Roth conversion is suppressed (the large Traditional withdrawal fills the bracket)
        #   • Cash is funded directly from Traditional (not from Brokerage) so Brokerage stays intact
        #   • Normal brokerage replenishment is bypassed (the pre-fund IS the funding event)
        daf_trad_prefund = self._calculate_daf_trad_prefund(
            strategy, age_primary, year, balances.traditional,
            anticipated_needs['total_traditional_need']
        )

        if daf_trad_prefund > 0:
            # ── PRE-FUND PATH ─────────────────────────────────────────────────
            # Suppress Roth conversion — the big Traditional distribution consumes
            # all available bracket space; stacking a conversion on top would push
            # AGI above the target rate.
            roth_conversion = 0.0
            self._log_decision(
                strategy,
                'roth_conversion',
                'Roth Conversion Suppressed (DAF Pre-Fund Year)',
                'No conversion — DAF Trad→Brok pre-fund active',
                f'A Traditional → Brokerage pre-fund of ${daf_trad_prefund:,.0f} is executing this year '
                f'to build Brokerage liquidity for upcoming DAF contributions. The distribution itself '
                f'fills the available tax bracket, so no additional Roth conversion is performed.',
                daf_trad_prefund=daf_trad_prefund,
            )

            # Step 1: Deduct expenses + ACA from cash.
            # Clamp to zero; carry any shortfall into Step 2.
            total_cash_outflow = expenses + aca_premium
            cash_after_outflow = balances.cash - total_cash_outflow
            outflow_shortfall = max(0.0, -cash_after_outflow)
            new_balances = PortfolioBalances(
                cash=max(0.0, cash_after_outflow),
                taxable=balances.taxable,
                traditional=balances.traditional,
                roth=balances.roth,
                daf=balances.daf,
            )

            # Step 2: Fill the cash buffer using Brokerage → Cash (LOFO — lowest-gain
            # lots first).  This is more tax-efficient than pulling from Traditional
            # because:
            #   a) The Traditional distribution (Step 3) already generates a large
            #      ordinary-income hit; adding more Traditional withdrawals here would
            #      compound that.
            #   b) Low-gain brokerage lots realise minimal LTCG (potentially 0% rate
            #      for MFJ filers in Stage 3).
            #   c) It preserves the highest-gain lots in Brokerage for future DAF
            #      donations (HIFO), eliminating even more embedded gain tax-free.
            from strategy import calculate_cash_buffer_targets
            cash_target, _ = calculate_cash_buffer_targets(expenses)
            cash_deficit = max(0.0, cash_target - new_balances.cash) + outflow_shortfall

            brok_to_cash = 0.0
            brok_ltcg = 0.0
            trad_to_cash = 0.0

            if cash_deficit > 100:
                # How much Brokerage can provide without going below zero
                # (Step 3 needs Brokerage intact to receive the pre-fund deposit,
                # so we only use what is already there before the pre-fund.)
                brok_available = new_balances.taxable
                brok_transfer = min(cash_deficit, brok_available)

                if brok_transfer > 0:
                    if brokerage_account is not None:
                        _, brok_ltcg = brokerage_account.withdraw_lowest_gain(brok_transfer, year)
                    else:
                        # No lot tracker — estimate LTCG at account-level ratio
                        brok_ltcg = brok_transfer * getattr(brokerage_account, 'ltcg_ratio', 0.4) \
                                    if brokerage_account else brok_transfer * 0.4
                        brok_ltcg = 0.0  # no tracker means we can't compute it

                    new_balances = PortfolioBalances(
                        cash=new_balances.cash + brok_transfer,
                        taxable=new_balances.taxable - brok_transfer,
                        traditional=new_balances.traditional,
                        roth=new_balances.roth,
                        daf=new_balances.daf,
                    )
                    brok_to_cash = brok_transfer
                    cash_deficit -= brok_transfer
                    logger.info(
                        f"Year {year}: Pre-fund path: ${brok_to_cash:,.0f} Brokerage → Cash "
                        f"(LOFO, ${brok_ltcg:,.0f} LTCG realised)"
                    )

                # Any remaining deficit (Brokerage exhausted) falls back to Traditional
                if cash_deficit > 100 and new_balances.traditional > 0:
                    trad_to_cash = min(cash_deficit, new_balances.traditional)
                    new_balances = PortfolioBalances(
                        cash=new_balances.cash + trad_to_cash,
                        taxable=new_balances.taxable,
                        traditional=new_balances.traditional - trad_to_cash,
                        roth=new_balances.roth,
                        daf=new_balances.daf,
                    )
                    logger.info(
                        f"Year {year}: Pre-fund path: ${trad_to_cash:,.0f} Traditional → Cash "
                        f"(Brokerage insufficient; fallback)"
                    )

            # Step 3: Execute the pre-fund transfer Traditional → Brokerage
            actual_prefund = min(daf_trad_prefund, new_balances.traditional)
            if actual_prefund < daf_trad_prefund:
                logger.warning(
                    f"Year {year}: DAF pre-fund capped at ${actual_prefund:,.0f} "
                    f"(wanted ${daf_trad_prefund:,.0f}, Traditional balance insufficient)"
                )
            new_balances = PortfolioBalances(
                cash=new_balances.cash,
                taxable=new_balances.taxable + actual_prefund,
                traditional=new_balances.traditional - actual_prefund,
                roth=new_balances.roth,
                daf=new_balances.daf,
            )
            logger.info(
                f"Year {year}: DAF pre-fund executed: ${actual_prefund:,.0f} Traditional → Brokerage"
            )

            # Step 4: DAF bundling contribution — now that Brokerage is funded by the
            # pre-fund, the bundled DAF contribution can fire in this same year if the
            # balance is sufficient. Pass the post-prefund brokerage balance so the
            # sufficiency check inside _calculate_daf_for_year uses the updated amount.
            daf_contribution, daf_tax_excess = self._calculate_daf_optimization(
                strategy,
                age_primary,
                age_spouse,
                std_deduction,
                state,
                new_balances.taxable,   # post-prefund brokerage balance
                year,
                filing_status,
            )
            if daf_contribution > 0:
                new_balances = self._apply_daf_contribution(
                    new_balances, daf_contribution, year, brokerage_account
                )
                new_balances = PortfolioBalances(
                    cash=new_balances.cash,
                    taxable=new_balances.taxable,
                    traditional=new_balances.traditional,
                    roth=new_balances.roth,
                    daf=new_balances.daf + daf_contribution,
                )
                logger.info(
                    f"Year {year}: DAF bundling contribution: ${daf_contribution:,.0f} from Brokerage"
                )

            # Build transaction dict matching the shape the rest of the method expects.
            # brok_to_cash and brok_ltcg feed into _calculate_final_taxes so the LOFO
            # LTCG is included in AGI correctly.
            transactions = {
                'brokerage_to_cash': brok_to_cash,
                'traditional_to_cash': trad_to_cash,
                'traditional_to_brokerage': actual_prefund,
                'roth_to_cash': 0.0,
                'roth_to_brokerage': 0.0,
                'conversion_executed': 0.0,
                'cash_replenishment': brok_to_cash + trad_to_cash,
                'brokerage_replenishment': actual_prefund,
                'brokerage_ltcg': brok_ltcg,
                'taxes_paid': 0.0,
            }

        else:
            # ── NORMAL PATH ───────────────────────────────────────────────────
            # Calculate available Traditional balance for conversion
            available_for_conversion = max(
                0,
                balances.traditional - anticipated_needs['total_traditional_need']
            )

            # Calculate optimal Roth conversion using BETR
            roth_conversion = self._calculate_betr_roth_conversion(
                strategy,
                available_for_conversion,
                anticipated_needs,
                max_conversion_rate,
                age_primary,
                balances.taxable,
                growth_rate,
                year
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

            # Apply DAF enhancement to Roth conversion if applicable
            if daf_contribution > 0 and daf_tax_excess > 0 and roth_conversion > 0:
                additional_conversion = min(
                    daf_tax_excess,
                    available_for_conversion - roth_conversion
                )
                if additional_conversion > 0:
                    roth_conversion += additional_conversion
                    self._log_daf_conversion_enhancement(
                        strategy,
                        daf_contribution,
                        daf_tax_excess,
                        additional_conversion,
                        roth_conversion
                    )

            # Subtract DAF from balances before rebalancing (HIFO lot removal)
            balances_for_rebalance = self._apply_daf_contribution(
                balances, daf_contribution, year, brokerage_account
            )

            # Estimate preliminary tax before rebalancing
            preliminary_tax = self._estimate_preliminary_tax(
                expenses=expenses,
                roth_conversion=roth_conversion,
                anticipated_needs=anticipated_needs,
                aca_premium=aca_premium,
                filing_status=filing_status,
                state=state,
                year=year,
                age_primary=age_primary,
                age_spouse=age_spouse,
                brokerage_account=brokerage_account
            )

            # Execute account rebalancing with preliminary tax estimate
            new_balances, transactions = self._execute_rebalancing(
                strategy,
                balances_for_rebalance,
                expenses,
                roth_conversion,
                aca_premium,
                preliminary_tax,
                year,
                age_primary,
                brokerage_account
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
            expenses
        )
        
        # Add DAF contribution to DAF balance
        if daf_contribution > 0:
            new_balances = PortfolioBalances(
                cash=new_balances.cash,
                taxable=new_balances.taxable,
                traditional=new_balances.traditional,
                roth=new_balances.roth,
                daf=new_balances.daf + daf_contribution
            )
        
        # Apply growth to balances
        new_balances = PortfolioBalances(
            cash=new_balances.cash,
            taxable=new_balances.taxable * growth_rate,
            traditional=new_balances.traditional * growth_rate,
            roth=new_balances.roth * growth_rate,
            daf=new_balances.daf * growth_rate
        )
        
        # Update strategy with final values
        strategy.balances = new_balances
        strategy.roth_conversion = roth_conversion
        strategy.daf_contribution = daf_contribution
        strategy.aca_premium = aca_premium
        strategy.healthcare_costs = aca_premium  # Total healthcare costs for Stage 3
        
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
            f"Stage 3 complete: AGI=${strategy.agi:,.2f}, "
            f"Federal Tax=${strategy.federal_tax:,.2f}, "
            f"Roth Conversion=${roth_conversion:,.2f}"
        )
        
        return strategy
    
    def _calculate_aca_premium(
        self,
        strategy: YearlyStrategy,
        year: int,
        age_primary: int,
        age_spouse: int
    ) -> float:
        """
        Calculate ACA premium based on configuration.
        
        Args:
            strategy: YearlyStrategy to log to
            year: Current year
            age_primary: Primary person's age
            age_spouse: Spouse's age
            
        Returns:
            ACA premium amount
        """
        try:
            from calculations import calculate_aca_premium_for_year
            aca_premium = calculate_aca_premium_for_year(year, age_primary, age_spouse)
        except ImportError:
            # Fallback estimate: $1000/month per person
            num_people = 2 if age_spouse > 0 else 1
            aca_premium = 12000.0 * num_people
        
        self._log_decision(
            strategy,
            'aca_decisions',
            'ACA Premium (Stage 3)',
            f'ACA premium: ${aca_premium:,.0f}',
            'Pre-Medicare retirees must purchase ACA marketplace coverage. '
            'The premium is calculated from config (age, number of people). '
            'Roth conversions and LTCG harvesting are sized to keep MAGI below 400% FPL '
            'to preserve ACA premium tax credits.',
            aca_premium=aca_premium,
            age_primary=age_primary,
            age_spouse=age_spouse
        )
        
        return aca_premium
    
    def _calculate_anticipated_buffer_needs(
        self,
        strategy: YearlyStrategy,
        balances: PortfolioBalances,
        expenses: float,
        age_primary: int,
        aca_premium: float,
        brokerage_account: Any,
        start_year: int,
        year: int
    ) -> dict:
        """
        Calculate anticipated buffer needs before conversion optimization.
        
        This lookahead ensures we don't over-convert and then need to
        withdraw from Traditional for buffers.
        
        Args:
            strategy: YearlyStrategy to log to
            balances: Current balances
            expenses: Annual expenses
            age_primary: Primary person's age
            aca_premium: ACA premium cost
            brokerage_account: BrokerageAccount instance
            start_year: First year of retirement
            year: Current year
            
        Returns:
            Dict with anticipated needs breakdown
        """
        try:
            from strategy import (
                calculate_cash_buffer_targets,
                calculate_buffer_ramp_up,
                calculate_anticipated_buffer_needs
            )
            
            # Calculate target buffer amounts
            cash_target, taxable_target = calculate_cash_buffer_targets(expenses)
            
            # Calculate ramp-up amounts for this year
            cash_need, taxable_need = calculate_buffer_ramp_up(
                year, start_year, cash_target, taxable_target,
                balances.cash, balances.taxable
            )
            
            # Calculate anticipated needs
            anticipated_needs = calculate_anticipated_buffer_needs(
                balances=balances,
                expenses=expenses,
                age_primary=age_primary,
                federal_tax=0.0,  # Preliminary estimate
                irmaa_penalty=0.0,
                aca_premium=aca_premium,
                medical_costs=0.0,
                brokerage_account=brokerage_account
            )
            
            logger.info(f"Year {year}: Lookahead buffer analysis (Stage 3)")
            logger.info(f"  Traditional balance: ${balances.traditional:,.0f}")
            logger.info(f"  Anticipated buffer needs: ${anticipated_needs['total_traditional_need']:,.0f}")
            logger.info(f"    - Trad→Cash: ${anticipated_needs['traditional_to_cash']:,.0f}")
            logger.info(f"    - Trad→Brok: ${anticipated_needs['traditional_to_brokerage']:,.0f}")
            logger.info(f"  Available for conversion: ${max(0, balances.traditional - anticipated_needs['total_traditional_need']):,.0f}")
            
            self._log_decision(
                strategy,
                'roth_conversion',
                'Lookahead Buffer Analysis',
                f"Reserved ${anticipated_needs['total_traditional_need']:,.0f} for buffers",
                "Before optimizing Roth conversions, we anticipate how much Traditional will be needed "
                "to maintain cash and brokerage buffers. This prevents over-converting and ensures "
                "consistent year-over-year strategy for the same AGI target.",
                traditional_balance=balances.traditional,
                anticipated_trad_to_cash=anticipated_needs['traditional_to_cash'],
                anticipated_trad_to_brok=anticipated_needs['traditional_to_brokerage'],
                available_for_conversion=max(0, balances.traditional - anticipated_needs['total_traditional_need'])
            )
            
            return anticipated_needs
            
        except ImportError:
            logger.warning("Buffer strategy module not available, using simplified calculation")
            # Simplified fallback
            return {
                'total_traditional_need': 0.0,
                'traditional_to_cash': 0.0,
                'traditional_to_brokerage': 0.0,
                'estimated_ltcg': 0.0
            }
    
    def _calculate_betr_roth_conversion(
        self,
        strategy: YearlyStrategy,
        available_for_conversion: float,
        anticipated_needs: dict,
        max_conversion_rate: float,
        age_primary: int,
        taxable_balance: float,
        growth_rate: float,
        year: int
    ) -> float:
        """
        Calculate optimal Roth conversion using BETR algorithm.
        
        Args:
            strategy: YearlyStrategy to log to
            available_for_conversion: Traditional balance available after buffer needs
            anticipated_needs: Dict with anticipated buffer needs
            max_conversion_rate: Maximum tax rate for conversions
            age_primary: Primary person's age
            taxable_balance: Taxable account balance
            growth_rate: Annual growth rate
            year: Current year
            
        Returns:
            Optimal conversion amount
        """
        if available_for_conversion <= 0:
            self._log_decision(
                strategy,
                'roth_conversion',
                'BETR Conversion (Stage 3)',
                'No conversion — insufficient balance',
                'All Traditional balance is needed for buffer maintenance.',
                available_balance=available_for_conversion
            )
            return 0.0
        
        # Calculate current income (includes anticipated withdrawals and LTCG)
        current_income = (
            anticipated_needs['traditional_to_cash'] +
            anticipated_needs['traditional_to_brokerage'] +
            anticipated_needs.get('estimated_ltcg', 0.0)
        )
        
        # Get stage-specific conversion rate
        try:
            from calculations import get_stage_specific_conversion_rate
            stage_max_rate = get_stage_specific_conversion_rate(self.name)
        except ImportError:
            stage_max_rate = max_conversion_rate
        
        # Use BETR algorithm to optimize conversion
        try:
            from betr_roth_conversion import optimize_conversion_amount
            
            optimal_amount, betr_results = optimize_conversion_amount(
                traditional_ira_balance=available_for_conversion,
                current_agi=current_income,
                target_tax_bracket=stage_max_rate,
                year=year,
                pay_from_taxable=True,
                taxable_account_balance=taxable_balance,
                years_to_withdrawal=(73 - age_primary) if age_primary > 0 else 20,
                annual_return=growth_rate - 1.0
            )
            
            if optimal_amount <= 0:
                self._log_decision(
                    strategy,
                    'roth_conversion',
                    'BETR Conversion (Stage 3)',
                    'No conversion — no bracket room',
                    'BETR optimizer found no room to convert within the target bracket after '
                    'accounting for LTCG income.',
                    current_income=current_income,
                    target_bracket=stage_max_rate
                )
                return 0.0
            
            if betr_results.conversion_recommended:
                logger.info(
                    f'BETR: {betr_results.betr:.2%}, Converting ${optimal_amount:,.0f}'
                )
                
                self._log_decision(
                    strategy,
                    'roth_conversion',
                    'BETR Conversion (Stage 3)',
                    f'Convert ${optimal_amount:,.0f}',
                    'Early retirement is the optimal Roth conversion window: income is low (LTCG only), '
                    'so the marginal rate on conversions is at its lifetime minimum. '
                    'BETR confirms converting now is cheaper than paying ordinary income tax on '
                    'Traditional withdrawals or RMDs later.',
                    betr=betr_results.betr,
                    current_income=current_income,
                    target_bracket=stage_max_rate,
                    optimal_amount=optimal_amount
                )
                
                return optimal_amount
            else:
                logger.info(
                    f'BETR: {betr_results.betr:.2%}, Conversion not recommended'
                )
                
                self._log_decision(
                    strategy,
                    'roth_conversion',
                    'BETR Conversion (Stage 3)',
                    'No conversion',
                    'BETR does not recommend converting: the break-even tax rate is below the '
                    'current marginal rate — deferring is more efficient.',
                    betr=betr_results.betr,
                    optimal_amount=optimal_amount
                )
                
                return 0.0
                
        except Exception as e:
            logger.warning(f"BETR calculation failed: {e}, falling back to bracket-filling")
            
            self._log_decision(
                strategy,
                'roth_conversion',
                'BETR Conversion (Stage 3)',
                'Fallback bracket-fill conversion',
                f'BETR calculation failed ({e}). Falling back to simple bracket-filling: '
                'converting up to the top of the target bracket.',
                error=str(e)
            )
            
            # Fallback: fill to target bracket
            return self._calculate_bracket_fill_conversion(
                available_for_conversion,
                current_income,
                stage_max_rate,
                year
            )
    
    def _calculate_bracket_fill_conversion(
        self,
        available_balance: float,
        current_income: float,
        target_rate: float,
        year: int
    ) -> float:
        """
        Fallback conversion calculation: fill to target bracket.
        
        Args:
            available_balance: Available Traditional balance
            current_income: Current income before conversion
            target_rate: Target tax rate
            year: Current year
            
        Returns:
            Conversion amount
        """
        try:
            from calculations import (
                get_income_tax_brackets,
                get_target_conversion_bracket,
                get_std_deduction
            )
            import pandas as pd
            
            tax_brackets = get_income_tax_brackets(year)
            std_deduction_df = get_std_deduction(year, 'married_filing_jointly')
            std_deduction = std_deduction_df.iloc[0]['deduction']
            
            target_bracket_rate, target_bracket_upper = get_target_conversion_bracket(
                target_rate, pd.DataFrame(tax_brackets)
            )
            
            conversion_room = max(
                0,
                target_bracket_upper - std_deduction - current_income
            )
            
            return min(conversion_room, available_balance)
            
        except Exception as e:
            logger.error(f"Bracket fill calculation failed: {e}")
            return 0.0
    
    def _estimate_preliminary_tax(
        self,
        expenses: float,
        roth_conversion: float,
        anticipated_needs: dict,
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
        std_deduction = self.tax_calculator.calculate_standard_deduction(
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
            ss_benefits=0.0,  # No SS in Stage 3
            roth_conversion=roth_conversion
        )
        
        total_tax = federal_tax + cg_tax + state_tax
        
        logger.info(
            f"Year {year} Stage 3 preliminary tax estimate: "
            f"Federal=${federal_tax:,.0f}, CG=${cg_tax:,.0f}, "
            f"State=${state_tax:,.0f}, Total=${total_tax:,.0f}"
        )
        logger.debug(
            f"  Estimated AGI=${estimated_agi:,.0f} "
            f"(LTCG=${estimated_ltcg:,.0f}, Conv=${roth_conversion:,.0f}, "
            f"Trad=${estimated_trad_withdrawal:,.0f})"
        )
        
        return total_tax
    
    def _calculate_daf_trad_prefund(
        self,
        strategy: YearlyStrategy,
        age_primary: int,
        year: int,
        traditional_balance: float,
        already_reserved: float,
    ) -> float:
        """
        Return the Traditional → Brokerage distribution amount for DAF pre-funding.

        Fires in every calendar year within [start_year, end_year] inclusive.
        Year-based configuration removes all age/stage inference — what you set
        in the UI is exactly what executes, no conversion needed.

        Args:
            strategy:            YearlyStrategy to log to
            age_primary:         Primary person's age (informational only)
            year:                Current calendar year
            traditional_balance: Current Traditional IRA / 401k balance
            already_reserved:    Amount already earmarked for normal buffer needs

        Returns:
            Pre-fund distribution amount (0 if not applicable this year)
        """
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()

            enabled = bool(config_mgr.get("charitable_giving", "daf_trad_prefund_enabled", False))
            if not enabled:
                return 0.0

            prefund_amount = float(config_mgr.get("charitable_giving", "daf_trad_prefund_amount", 0))
            start_year = int(config_mgr.get("charitable_giving", "daf_trad_prefund_start_year", 9999))
            end_year   = int(config_mgr.get("charitable_giving", "daf_trad_prefund_end_year",   0))

            if prefund_amount <= 0:
                return 0.0

            if not (start_year <= year <= end_year):
                return 0.0

            # Cap to Traditional balance available after normal buffer needs
            available = max(0.0, traditional_balance - already_reserved)
            actual_amount = min(prefund_amount, available)

            if actual_amount <= 0:
                logger.info(
                    f"Year {year}: DAF pre-fund skipped — insufficient Traditional balance "
                    f"(available=${available:,.0f} after ${already_reserved:,.0f} reserved)"
                )
                return 0.0

            logger.info(
                f"Year {year}: DAF Trad→Brok pre-fund: ${actual_amount:,.0f} "
                f"(year window {start_year}–{end_year}, age {age_primary})"
            )
            self._log_decision(
                strategy,
                'tax_strategy',
                'DAF Traditional → Brokerage Pre-Fund',
                f'Distribute ${actual_amount:,.0f} from Traditional → Brokerage',
                f'Pre-funding Brokerage with a Traditional distribution in {year} '
                f'(configured window {start_year}–{end_year}) to ensure Brokerage has '
                f'sufficient liquidity to fund upcoming DAF contributions. '
                f'Roth conversion is suppressed this year; the distribution is taxed '
                f'as ordinary income.',
                year=year,
                prefund_amount=actual_amount,
                window_start=start_year,
                window_end=end_year,
            )
            return actual_amount

        except Exception as e:
            logger.warning(f"DAF trad prefund calculation failed: {e}")
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
        """
        Calculate DAF contribution and tax optimization.
        
        Args:
            strategy: YearlyStrategy to log to
            age_primary: Primary person's age
            age_spouse: Spouse's age
            std_deduction: Standard deduction
            state: State for tax calculation
            taxable_balance: Taxable account balance
            year: Current year
            filing_status: Filing status
            
        Returns:
            Tuple of (daf_contribution, daf_tax_excess)
        """
        try:
            from strategy import _calculate_daf_for_year, calculate_state_tax
            from config import get_config_manager
            
            # Get property tax from config
            config_mgr = get_config_manager()
            property_tax = float(
                config_mgr.get("expenses", "living_expenses", {}).get("property_tax", 0)
            )
            
            # Calculate preliminary state tax
            state_tax, _ = calculate_state_tax(
                state_agi=0.0,  # Preliminary
                year=year,
                filing_status=filing_status,
                retirement_income=0.0,
                ss_benefits=0.0
            )
            
            # Calculate DAF contribution
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
        total_conversion: float
    ) -> None:
        """Log DAF-enhanced Roth conversion decision."""
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
            f'effective tax rate. This accelerates the Traditional→Roth transition during low-income years.',
            daf_contribution=daf_contribution,
            daf_tax_excess=daf_tax_excess,
            additional_conversion=additional_conversion,
            original_conversion=total_conversion - additional_conversion,
            enhanced_conversion=total_conversion
        )
    
    def _apply_daf_contribution(
        self,
        balances: PortfolioBalances,
        daf_contribution: float,
        year: int = 0,
        brokerage_account: Any = None,
    ) -> PortfolioBalances:
        """
        Apply DAF contribution by reducing taxable balance and removing the
        highest-gain lots from the BrokerageAccount tracker (HIFO order).

        Donating appreciated securities to a DAF eliminates the embedded capital
        gain entirely.  Selecting the highest-gain lots first maximises the tax
        benefit and leaves the remaining portfolio with a higher basis ratio,
        permanently lowering LTCG on future Brokerage → Cash withdrawals.

        Args:
            balances:           Current portfolio balances.
            daf_contribution:   Amount contributed to the DAF.
            year:               Current year (passed through to lot tracker).
            brokerage_account:  Live BrokerageAccount for HIFO lot removal.

        Returns:
            Updated PortfolioBalances with taxable reduced by daf_contribution.
        """
        try:
            from strategy import apply_daf_to_brokerage_account
            return apply_daf_to_brokerage_account(
                balances, daf_contribution, year, brokerage_account
            )
        except ImportError:
            # Fallback: scalar deduction only (no lot tracking)
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
        aca_premium: float,
        preliminary_tax: float,
        year: int,
        age_primary: int,
        brokerage_account: Any
    ) -> tuple[PortfolioBalances, dict]:
        """
        Execute account rebalancing including Roth conversion and buffer maintenance.
        
        Args:
            strategy: YearlyStrategy to log to
            balances: Current balances (after DAF)
            expenses: Annual expenses
            roth_conversion: Roth conversion amount
            aca_premium: ACA premium cost
            preliminary_tax: Preliminary tax estimate (federal + state)
            year: Current year
            age_primary: Primary person's age
            brokerage_account: BrokerageAccount instance
            
        Returns:
            Tuple of (new_balances, transactions_dict)
        """
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
                irmaa_penalty=0.0,
                aca_premium=aca_premium,
                medical_costs=0.0,
                brokerage_account=brokerage_account
            )
            
            # Merge decision logs
            strategy.decisions.cash_replenishment.extend(rebal_dl.cash_replenishment)
            strategy.decisions.brokerage_replenishment.extend(rebal_dl.brokerage_replenishment)
            
            return new_balances, transactions
            
        except ImportError:
            logger.warning("Rebalancing module not available, using simplified approach")
            # Simplified fallback
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
        """
        Ensure 90% standard deduction target is met with ordinary income.
        
        Args:
            strategy: YearlyStrategy to log to
            balances: Current balances
            transactions: Transaction dict
            roth_conversion: Roth conversion amount
            min_ordinary_income_target: Minimum ordinary income target
            std_deduction: Standard deduction
            year: Current year
            
        Returns:
            Tuple of (updated_balances, updated_transactions)
        """
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
                f"to reach 90% std deduction target (${min_ordinary_income_target:,.0f})"
            )
            
            self._log_decision(
                strategy,
                'tax_strategy',
                'Standard Deduction Optimization (0% Tax)',
                f'Added ${additional_withdrawal:,.0f} Traditional withdrawal',
                f'Roth conversion (${roth_conversion:,.0f}) + buffer withdrawals (${trad_withdrawal:,.0f}) '
                f'= ${ordinary_income:,.0f} ordinary income. Added ${additional_withdrawal:,.0f} to reach '
                f'90% of standard deduction (${min_ordinary_income_target:,.0f}), resulting in ~0% tax on '
                'ordinary income and freeing the 0% LTCG bracket.',
                std_deduction=std_deduction,
                target_income=min_ordinary_income_target,
                roth_conversion=roth_conversion,
                buffer_withdrawals=trad_withdrawal,
                additional_withdrawal=additional_withdrawal,
                effective_tax_rate='~0%'
            )
        elif ordinary_income >= min_ordinary_income_target:
            logger.info(
                f"Year {year}: Ordinary income ${ordinary_income:,.0f} already meets "
                f"90% std deduction target (${min_ordinary_income_target:,.0f})"
            )
            
            self._log_decision(
                strategy,
                'tax_strategy',
                'Standard Deduction Optimization (0% Tax)',
                'Target met via Roth conversion + buffer withdrawals',
                f'Roth conversion (${roth_conversion:,.0f}) + buffer withdrawals (${trad_withdrawal:,.0f}) '
                f'= ${ordinary_income:,.0f}, which meets the 90% standard deduction target '
                f'(${min_ordinary_income_target:,.0f}). This results in ~0% tax on ordinary income.',
                std_deduction=std_deduction,
                target_income=min_ordinary_income_target,
                actual_income=ordinary_income,
                roth_conversion=roth_conversion,
                buffer_withdrawals=trad_withdrawal,
                effective_tax_rate='~0%'
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
        expenses: float
    ) -> PortfolioBalances:
        """
        Calculate final AGI and taxes with actual withdrawals.
        
        Updates the strategy object with final tax calculations.
        
        Args:
            strategy: YearlyStrategy to update
            balances: Final balances
            transactions: Transaction dict
            roth_conversion: Roth conversion amount
            daf_contribution: DAF contribution
            daf_tax_excess: DAF tax excess deduction
            std_deduction: Standard deduction
            filing_status: Filing status
            state: State for tax calculation
            year: Current year
            expenses: Annual expenses
        """
        # Calculate AGI components
        trad_withdrawal = (
            transactions['traditional_to_cash'] + 
            transactions['traditional_to_brokerage']
        )
        brokerage_ltcg = transactions.get('brokerage_ltcg', 0.0)
        
        # AGI = LTCG + Roth conversion + Traditional withdrawals
        agi = brokerage_ltcg + roth_conversion + trad_withdrawal
        magi = agi  # Same as AGI in Stage 3 (no SS benefits)
        
        logger.info(
            f"Year {year} Stage 3 AGI breakdown: "
            f"LTCG from Brokerage=${brokerage_ltcg:,.0f}, "
            f"Roth Conv=${roth_conversion:,.0f}, "
            f"Trad Withdrawal=${trad_withdrawal:,.0f}, "
            f"Total AGI=${agi:,.0f}"
        )
        
        # Calculate effective deduction
        effective_deduction = std_deduction + daf_tax_excess if daf_contribution > 0 else std_deduction
        
        # Calculate taxable income
        taxable_income = max(0, agi - effective_deduction)
        
        # Calculate ordinary income (exclude LTCG)
        ordinary_income = max(0, taxable_income - brokerage_ltcg)
        
        # Calculate federal tax on ordinary income
        federal_tax, max_rate, upper_bracket = self.tax_calculator.calculate_federal_tax(
            ordinary_income, filing_status, year
        )
        
        # Calculate capital gains tax
        cg_tax = self.tax_calculator.calculate_capital_gains_tax(
            brokerage_ltcg, ordinary_income, filing_status, year
        )
        
        total_tax = federal_tax + cg_tax
        
        # Calculate state tax with retirement income exemptions
        state_tax = self.tax_calculator.calculate_state_tax(
            agi=agi,
            state=state,
            year=year,
            filing_status=filing_status,
            retirement_income=trad_withdrawal,
            ss_benefits=0.0,  # No SS in Stage 3
            roth_conversion=roth_conversion
        )
        
        # Calculate tax estimation error
        actual_total_tax = total_tax + state_tax
        preliminary_tax = transactions.get('taxes_paid', 0.0)
        tax_difference = actual_total_tax - preliminary_tax
        
        if abs(tax_difference) > 100:
            logger.info(
                f"Year {year} Stage 3 tax estimation adjustment: "
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
            logger.info(f"Year {year}: Final tax calculation with DAF:")
            logger.info(f"  AGI: ${agi:,.2f}")
            logger.info(f"  Standard Deduction: ${std_deduction:,.2f}")
            logger.info(f"  DAF Tax Excess: ${daf_tax_excess:,.2f}")
            logger.info(f"  Effective Deduction: ${effective_deduction:,.2f}")
            logger.info(f"  Taxable Income: ${taxable_income:,.2f}")
            logger.info(f"  LTCG: ${brokerage_ltcg:,.2f}")
            logger.info(f"  Ordinary Income: ${ordinary_income:,.2f}")
            logger.info(f"  Federal Tax (ordinary): ${federal_tax:,.2f}")
            logger.info(f"  CG Tax: ${cg_tax:,.2f}")
            logger.info(f"  Total Tax: ${total_tax:,.2f}")
        else:
            logger.info(f"Year {year}: Final tax: ${total_tax:,.2f}")
        
        # Update strategy
        strategy.expenses = expenses  # Store expenses in strategy
        strategy.agi = agi
        strategy.magi = magi
        strategy.taxable_income = taxable_income
        strategy.federal_tax = total_tax
        strategy.state_tax = state_tax
        strategy.ltcg_harvested = brokerage_ltcg
        strategy.traditional_withdrawal = trad_withdrawal
        strategy.taxable_withdrawal = transactions['brokerage_to_cash']
        strategy.roth_withdrawal = (
            transactions['roth_to_cash'] +
            transactions['roth_to_brokerage']
        )
        
        # Return updated balances with state tax deducted
        return balances

# Made with Bob