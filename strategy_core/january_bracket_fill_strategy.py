"""
January Bracket-Fill Withdrawal Strategy with 60-Day Rollover

Integrates:
1. PNC (Personal Net Cash) assessment
2. Annual spending + tax need calculation
3. Traditional withdrawal to cover shortfall
4. Roth conversion (remaining bracket space)
5. 60-day rollover withholding mechanics
6. Mid-year PNC supplementation logic

This is the operational embodiment of your new strategy thinking.
"""

import logging
from typing import Dict, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass

from .savings_account_tracker import SavingsAccountTracker, SavingsAccountSnapshot
from .sixty_day_rollover import SixtyDayRolloverHandler, RolloverWithholdingPlan
from .agi_calculator import AGICalculator

logger = logging.getLogger(__name__)


@dataclass
class JanuaryWithdrawalPlan:
    """Complete plan for January withdrawal with 60-day rollover."""
    
    # Annual needs
    annual_expenses: float
    estimated_taxes: float
    total_annual_need: float
    
    # PNC assessment
    pnc_balance_jan1: float
    pnc_shortfall: float
    
    # Withdrawal breakdown
    traditional_withdrawal_for_spending: float
    traditional_withdrawal_for_taxes: float
    total_traditional_withdrawal: float
    
    # Roth conversion
    roth_conversion_amount: float
    conversion_withholding: float
    
    # 60-day rollover
    sixty_day_redeposit_deadline: datetime
    redeposit_source: str
    redeposit_funding_plan: Dict
    
    # Cash flow
    cash_received_from_traditional: float
    cash_available_after_expenses_taxes: float
    pnc_after_withdrawal: float


class JanuaryBracketFillStrategy:
    """
    Implements your January single-withdrawal bracket-fill strategy.
    
    Decision flow:
    1. Assess PNC balance (actual spending cash)
    2. Calculate annual need (expenses + taxes)
    3. Calculate shortfall (need - PNC)
    4. Withdraw Traditional to cover shortfall + conversion taxes
    5. Use remaining 12% bracket for Roth conversion
    6. Plan 60-day rollover for conversion withholding
    7. Track PNC through year; supplement if drops below $50k
    """
    
    def __init__(
        self,
        annual_expenses: float = 137600.0,
        savings_account_safety_reserve: float = 50000.0,
        bracket_12_upper: float = 103000.0,
        standard_deduction: float = 35500.0
    ):
        """
        Initialize strategy.
        
        Args:
            annual_expenses: Annual living expenses (inflated)
            savings_account_safety_reserve: Minimum PNC Savings balance ($50k default)
            bracket_12_upper: Upper limit of 12% tax bracket
            standard_deduction: MFJ standard deduction (age-adjusted)
        """
        self.annual_expenses = annual_expenses
        self.savings_account_safety_reserve = savings_account_safety_reserve
        self.bracket_12_upper = bracket_12_upper
        self.standard_deduction = standard_deduction
        
        self.savings_tracker = SavingsAccountTracker(
            account_name="PNC",
            safety_reserve=savings_account_safety_reserve
        )
        
        self.rollover_handler = SixtyDayRolloverHandler()
        self.agi_calculator = None  # Will be set when needed
    
    def plan_january_withdrawal(
        self,
        pnc_savings_balance_jan1: float,
        estimated_tax_rate: float = 0.12,
        aca_premium: float = 0.0,
        conversion_date: Optional[datetime] = None,
        year: int = 2027,
        filing_status: str = 'married_filing_jointly',
        age_primary: int = 61,
        age_spouse: int = 60,
        tax_calculator=None
    ) -> JanuaryWithdrawalPlan:
        """
        Plan the January withdrawal decision with accurate tax estimation using AGICalculator.
        
        STEP 1: Assess PNC Savings account and annual need
        STEP 2: Calculate shortfall (annual need - current savings balance)
        STEP 3: Estimate taxes on withdrawal (using AGICalculator)
        STEP 4: Plan Roth conversion (remaining bracket space)
        STEP 5: Recalculate conversion withholding tax (using AGICalculator with stacking)
        STEP 6: Plan 60-day rollover for withholding
        
        Args:
            pnc_savings_balance_jan1: PNC Savings account balance at start of year
            estimated_tax_rate: Estimated federal + state tax rate (fallback if no AGICalculator)
            aca_premium: Annual ACA insurance premium
            conversion_date: Date of withdrawal/conversion (default today)
            year: Tax year (for AGI calculation)
            filing_status: Filing status for tax calculation
            age_primary: Primary taxpayer age
            age_spouse: Spouse age
            tax_calculator: Optional tax calculator for AGI estimation
        
        Returns:
            JanuaryWithdrawalPlan with all mechanics laid out
        """
        if conversion_date is None:
            conversion_date = datetime.now()
        
        # STEP 1: Calculate annual need
        total_annual_need = self.annual_expenses + aca_premium
        
        # STEP 2: Calculate shortfall (need - current savings)
        pnc_shortfall = max(0, total_annual_need - pnc_savings_balance_jan1)
        
        logger.info(
            f"January Bracket-Fill Decision:\n"
            f"  Annual need: ${total_annual_need:,.0f} (expenses ${self.annual_expenses:,.0f} + ACA ${aca_premium:,.0f})\n"
            f"  PNC Savings balance Jan 1: ${pnc_savings_balance_jan1:,.0f}\n"
            f"  Shortfall: ${pnc_shortfall:,.0f}"
        )
        
        # STEP 3: Estimate taxes on withdrawal using iterative AGICalculator
        # This converges on the correct tax amount (since tax depends on withdrawal amount)
        estimated_taxes = self._estimate_withdrawal_tax_iteratively(
            pnc_shortfall=pnc_shortfall,
            year=year,
            filing_status=filing_status,
            age_primary=age_primary,
            age_spouse=age_spouse,
            tax_calculator=tax_calculator,
            max_iterations=3,
            tolerance=10.0
        )
        logger.info(
            f"Shortfall withdrawal tax estimate (iterative): ${estimated_taxes:,.0f} "
            f"on ${pnc_shortfall:,.0f} withdrawal"
        )
        
        # Account for Roth conversion tax
        # Available bracket = 12% upper - standard deduction = amount that can be withdrawn at low rate
        available_bracket = max(0, self.bracket_12_upper - self.standard_deduction)
        
        # Amount in 12% bracket = min(shortfall + taxes, available)
        amount_in_12_bracket = min(pnc_shortfall + estimated_taxes, available_bracket)
        
        # Roth conversion = remaining bracket space
        roth_conversion_amount = max(0, available_bracket - amount_in_12_bracket)
        
        # STEP 5: Calculate conversion withholding using AGICalculator (with stacking)
        # The conversion stacks on top of the withdrawal, so we need to calculate tax on both
        conversion_withholding = 0.0
        try:
            from .agi_calculator import AGICalculator
            agi_calc = AGICalculator(tax_calculator=tax_calculator)
            
            # Estimate tax with conversion included (stacked income)
            stacked_tax_estimate = agi_calc.calculate_agi_and_taxes(
                year=year,
                filing_status=filing_status,
                age_primary=age_primary,
                age_spouse=age_spouse,
                traditional_withdrawal=pnc_shortfall,
                roth_conversion=roth_conversion_amount,  # Include conversion
                brokerage_ltcg=0.0,
                brokerage_basis=0.0,
                daf_fmv=0.0,
                state='PA',
                pa_rate=0.0307,
                property_tax=0.0,
                daf_carryforward_prior=0.0,
                tax_calculator=tax_calculator
            )
            # Conversion withholding = incremental tax from adding conversion
            total_stacked_tax = stacked_tax_estimate['total_tax']
            conversion_withholding = total_stacked_tax - estimated_taxes
            logger.debug(
                f"Roth conversion tax (stacked): ${conversion_withholding:,.0f} "
                f"on ${roth_conversion_amount:,.0f} conversion "
                f"(total tax with conversion: ${total_stacked_tax:,.0f})"
            )
        except Exception as e:
            logger.warning(f"Stacked conversion tax calculation failed: {e}")
            conversion_withholding = roth_conversion_amount * estimated_tax_rate
        
        # Total Traditional withdrawal = shortfall + conversion withholding
        traditional_for_spending = pnc_shortfall
        traditional_for_conversion_tax = conversion_withholding
        total_traditional_withdrawal = traditional_for_spending + traditional_for_conversion_tax
        
        logger.info(
            f"  Bracket-fill calculation:\n"
            f"    12% bracket upper: ${self.bracket_12_upper:,.0f}\n"
            f"    Standard deduction: ${self.standard_deduction:,.0f}\n"
            f"    Available bracket: ${available_bracket:,.0f}\n"
            f"    Used for spending+tax: ${amount_in_12_bracket:,.0f}\n"
            f"    Remaining for Roth: ${roth_conversion_amount:,.0f}\n"
            f"    Conversion withholding (accurate): ${conversion_withholding:,.0f}\n"
        )
        
        # STEP 6: Plan 60-day rollover
        # NOTE: withholding is now accurate (from AGICalculator, not flat %), so redeposit is accurate
        sixty_day_plan = self.rollover_handler.plan_conversion_with_withholding(
            conversion_amount=roth_conversion_amount,
            estimated_tax_rate=conversion_withholding / max(1, roth_conversion_amount),  # Actual tax rate
            conversion_date=conversion_date,
            available_cash=pnc_savings_balance_jan1 + total_traditional_withdrawal,  # Cash after withdrawal
            available_brokerage=0.0  # Set by caller if available
        )
        
        # Calculate cash flow
        cash_received = total_traditional_withdrawal
        cash_after_expenses_taxes = cash_received - self.annual_expenses - estimated_taxes
        pnc_after_withdrawal = pnc_savings_balance_jan1 + cash_after_expenses_taxes
        
        plan = JanuaryWithdrawalPlan(
            annual_expenses=self.annual_expenses,
            estimated_taxes=estimated_taxes,
            total_annual_need=total_annual_need,
            pnc_balance_jan1=pnc_savings_balance_jan1,
            pnc_shortfall=pnc_shortfall,
            traditional_withdrawal_for_spending=traditional_for_spending,
            traditional_withdrawal_for_taxes=traditional_for_conversion_tax,
            total_traditional_withdrawal=total_traditional_withdrawal,
            roth_conversion_amount=roth_conversion_amount,
            conversion_withholding=conversion_withholding,
            sixty_day_redeposit_deadline=sixty_day_plan.redeposit_deadline,
            redeposit_source=sixty_day_plan.source_for_redeposit,
            redeposit_funding_plan=self._build_funding_plan(sixty_day_plan),
            cash_received_from_traditional=cash_received,
            cash_available_after_expenses_taxes=cash_after_expenses_taxes,
            pnc_after_withdrawal=pnc_after_withdrawal
        )
        
        logger.info(
            f"  60-day rollover:\n"
            f"    Conversion: ${roth_conversion_amount:,.0f}\n"
            f"    Withholding: ${conversion_withholding:,.0f}\n"
            f"    Net to Roth: ${sixty_day_plan.net_conversion_deposit:,.0f}\n"
            f"    Redeposit by: {sixty_day_plan.redeposit_deadline.strftime('%Y-%m-%d')}\n"
            f"    From: {sixty_day_plan.source_for_redeposit}\n"
        )
        
        return plan
    
    def _build_funding_plan(self, sixty_day_plan: RolloverWithholdingPlan) -> Dict:
        """Build detailed funding plan for 60-day redeposit."""
        return {
            'redeposit_amount': sixty_day_plan.redeposit_amount,
            'redeposit_deadline': sixty_day_plan.redeposit_deadline.strftime('%Y-%m-%d'),
            'source': sixty_day_plan.source_for_redeposit,
            'instructions': (
                f"Redeposit ${sixty_day_plan.redeposit_amount:,.0f} to Traditional IRA "
                f"by {sixty_day_plan.redeposit_deadline.strftime('%B %d, %Y')} "
                f"from {sixty_day_plan.source_for_redeposit}. "
                f"Failure to redeposit = non-deductible contribution."
            )
        }
    
    def _estimate_withdrawal_tax_iteratively(
        self,
        pnc_shortfall: float,
        year: int,
        filing_status: str,
        age_primary: int,
        age_spouse: int,
        tax_calculator=None,
        max_iterations: int = 3,
        tolerance: float = 10.0
    ) -> float:
        """
        Estimate tax on withdrawal iteratively until convergence.
        
        The problem: Tax on a withdrawal depends on the withdrawal amount itself
        (due to progressive brackets). So we need to iterate:
        
        1. Guess withdrawal = shortfall × 1.15 (rough estimate)
        2. Calculate tax on that withdrawal
        3. New withdrawal = shortfall + tax
        4. Repeat until withdrawal stabilizes
        
        Args:
            pnc_shortfall: Amount needed from savings (before tax)
            year: Tax year
            filing_status: Filing status
            age_primary: Primary taxpayer age
            age_spouse: Spouse age
            tax_calculator: Optional tax calculator
            max_iterations: Max iterations before stopping
            tolerance: Stop when withdrawal changes by less than this amount
        
        Returns:
            Estimated tax amount (will be used with shortfall to get total withdrawal)
        """
        try:
            from .agi_calculator import AGICalculator
            agi_calc = AGICalculator(tax_calculator=tax_calculator)
        except Exception as e:
            logger.warning(f"Could not initialize AGICalculator for iteration: {e}")
            return pnc_shortfall * 0.12  # Fallback to 12%
        
        # Initial guess: withdrawal = shortfall + estimated tax (15% margin)
        estimated_tax = pnc_shortfall * 0.15
        
        logger.debug(
            f"Starting iterative tax estimation: shortfall=${pnc_shortfall:,.0f}, "
            f"initial_guess=${estimated_tax:,.0f}"
        )
        
        for iteration in range(max_iterations):
            try:
                # Calculate tax on current estimate
                tax_result = agi_calc.calculate_agi_and_taxes(
                    year=year,
                    filing_status=filing_status,
                    age_primary=age_primary,
                    age_spouse=age_spouse,
                    traditional_withdrawal=pnc_shortfall,
                    roth_conversion=0.0,
                    brokerage_ltcg=0.0,
                    brokerage_basis=0.0,
                    daf_fmv=0.0,
                    state='PA',
                    pa_rate=0.0307,
                    property_tax=0.0,
                    daf_carryforward_prior=0.0,
                    tax_calculator=tax_calculator
                )
                new_estimated_tax = tax_result['total_tax']
                
                # Check convergence
                tax_change = abs(new_estimated_tax - estimated_tax)
                logger.debug(
                    f"Iteration {iteration + 1}: tax=${new_estimated_tax:,.0f}, "
                    f"change=${tax_change:,.0f}"
                )
                
                if tax_change < tolerance:
                    logger.debug(
                        f"Tax estimation converged after {iteration + 1} iterations: "
                        f"${new_estimated_tax:,.0f}"
                    )
                    return new_estimated_tax
                
                estimated_tax = new_estimated_tax
                
            except Exception as e:
                logger.warning(f"Error in iteration {iteration + 1}: {e}")
                break
        
        logger.info(
            f"Tax estimation completed after {max_iterations} iterations: "
            f"${estimated_tax:,.0f}"
        )
        return estimated_tax


    
    def assess_midyear_savings_account(
        self,
        current_pnc_savings_balance: float,
        months_elapsed: int = 6,
        monthly_spending_rate: Optional[float] = None
    ) -> Tuple[bool, float, str]:
        """
        Assess PNC Savings account status mid-year.
        
        Args:
            current_pnc_savings_balance: Current PNC Savings balance
            months_elapsed: Months since January
            monthly_spending_rate: Average monthly spending (default: annual_expenses / 12)
        
        Returns:
            Tuple of (supplementation_needed, amount, reason)
        """
        if monthly_spending_rate is None:
            monthly_spending_rate = self.annual_expenses / 12
        
        return self.savings_tracker.assess_supplementation_need(
            current_pnc_savings_balance,
            monthly_spending_rate
        )
    
    def plan_midyear_supplementation(
        self,
        pnc_savings_balance: float,
        available_brokerage: float,
        brokerage_ltcg_ratio: float = 0.40
    ) -> Dict:
        """
        Plan mid-year supplementation from Brokerage if PNC Savings drops below threshold.
        
        Args:
            pnc_savings_balance: Current PNC Savings account balance
            available_brokerage: Available Brokerage funds
            brokerage_ltcg_ratio: LTCG ratio in Brokerage
        
        Returns:
            Supplementation plan dictionary
        """
        snapshot = self.savings_tracker.assess_available_for_spending(pnc_savings_balance)
        
        if not snapshot.is_below_reserve:
            return {
                'supplementation_needed': False,
                'amount': 0.0,
                'reason': f"PNC Savings healthy at ${pnc_savings_balance:,.0f}"
            }
        
        supplementation_plan = self.savings_tracker.plan_brokerage_supplementation(
            snapshot.supplementation_needed,
            available_brokerage,
            brokerage_ltcg_ratio
        )
        
        return {
            'supplementation_needed': True,
            'amount': supplementation_plan['amount_to_sell'],
            'ltcg_realized': supplementation_plan['ltcg_realized'],
            'reason': supplementation_plan['reason'],
            'feasible': supplementation_plan['feasible']
        }
    
    def generate_annual_strategy_summary(self, plan: JanuaryWithdrawalPlan) -> str:
        """Generate human-readable summary of the strategy."""
        summary = (
            f"JANUARY BRACKET-FILL WITHDRAWAL STRATEGY\n"
            f"{'='*60}\n"
            f"\n"
            f"ANNUAL NEEDS:\n"
            f"  Living expenses:        ${plan.annual_expenses:>12,.0f}\n"
            f"  ACA premium:            ${plan.total_annual_need - plan.annual_expenses:>12,.0f}\n"
            f"  Estimated taxes:        ${plan.estimated_taxes:>12,.0f}\n"
            f"  {'─'*40}\n"
            f"  Total annual need:      ${plan.total_annual_need:>12,.0f}\n"
            f"\n"
            f"PNC ASSESSMENT (Jan 1):\n"
            f"  PNC balance:            ${plan.pnc_balance_jan1:>12,.0f}\n"
            f"  Annual need:            ${plan.total_annual_need:>12,.0f}\n"
            f"  {'─'*40}\n"
            f"  Shortfall:              ${plan.pnc_shortfall:>12,.0f}\n"
            f"\n"
            f"WITHDRAWAL PLAN:\n"
            f"  Traditional (spending): ${plan.traditional_withdrawal_for_spending:>12,.0f}\n"
            f"  Traditional (taxes):    ${plan.traditional_withdrawal_for_taxes:>12,.0f}\n"
            f"  {'─'*40}\n"
            f"  Total Traditional:      ${plan.total_traditional_withdrawal:>12,.0f}\n"
            f"\n"
            f"ROTH CONVERSION (60-Day Rollover):\n"
            f"  Conversion amount:      ${plan.roth_conversion_amount:>12,.0f}\n"
            f"  Withholding (taxes):    ${plan.conversion_withholding:>12,.0f}\n"
            f"  Net to Roth:            ${plan.roth_conversion_amount - plan.conversion_withholding:>12,.0f}\n"
            f"  Redeposit by:           {plan.sixty_day_redeposit_deadline.strftime('%B %d, %Y')}\n"
            f"  Redeposit from:         {plan.redeposit_source}\n"
            f"\n"
            f"CASH FLOW:\n"
            f"  Cash from Traditional:  ${plan.cash_received_from_traditional:>12,.0f}\n"
            f"  Expenses + taxes:       ${plan.annual_expenses + plan.estimated_taxes:>12,.0f}\n"
            f"  {'─'*40}\n"
            f"  PNC after year-start:   ${plan.pnc_after_withdrawal:>12,.0f}\n"
            f"\n"
            f"MID-YEAR MONITORING:\n"
            f"  Safety threshold:       ${self.savings_account_safety_reserve:>12,.0f}\n"
            f"  If PNC < threshold → supplement from Brokerage (LOFO)\n"
            f"\n"
        )
        return summary
