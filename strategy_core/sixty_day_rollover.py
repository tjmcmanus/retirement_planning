"""
60-Day Rollover Rule Handler for Roth Conversions

Implements the IRS 60-day rule for Roth conversions with withholding:
- When converting from Traditional IRA to Roth, if taxes are withheld
- The withheld amount must be redeposited within 60 days
- Using funds from cash or brokerage (not from the Traditional IRA itself)
- This allows the conversion without disrupting retirement funds

Reference: IRC §408(d)(3)(B) and Rev. Proc. 2023-19
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RolloverWithholdingPlan:
    """Plan for 60-day rollover withholding on Roth conversions."""
    conversion_amount: float
    withholding_amount: float
    net_conversion_deposit: float  # Conversion amount - withholding
    redeposit_amount: float  # Amount to redeposit within 60 days
    redeposit_deadline: datetime
    source_for_redeposit: str  # 'cash' or 'brokerage'
    reasoning: str


class SixtyDayRolloverHandler:
    """
    Handles the 60-day rollover mechanics for Roth conversions with withholding.
    
    Scenario:
    1. Traditional IRA has $100,000
    2. Convert $100,000 to Roth
    3. Withhold $10,000 (10% estimated taxes)
    4. $90,000 goes to Roth, $10,000 held in Traditional
    5. Within 60 days, deposit $10,000 back into Traditional from cash/brokerage
    6. Net result: $100,000 in Roth, $10,000 tax liability paid from cash/brokerage
    """

    def __init__(self):
        """Initialize the 60-day rollover handler."""
        pass

    def plan_conversion_with_withholding(
        self,
        conversion_amount: float,
        estimated_tax_rate: float = 0.12,
        conversion_date: Optional[datetime] = None,
        available_cash: float = 0.0,
        available_brokerage: float = 0.0
    ) -> RolloverWithholdingPlan:
        """
        Plan a Roth conversion with withholding and 60-day redeposit.

        Args:
            conversion_amount: Amount to convert from Traditional to Roth
            estimated_tax_rate: Estimated federal + state tax rate (default 12%)
            conversion_date: Date of conversion (default today)
            available_cash: Available cash to fund redeposit
            available_brokerage: Available brokerage to fund redeposit

        Returns:
            RolloverWithholdingPlan with all mechanics laid out
        """
        if conversion_date is None:
            conversion_date = datetime.now()

        # Calculate withholding
        withholding_amount = conversion_amount * estimated_tax_rate
        net_conversion_deposit = conversion_amount - withholding_amount
        redeposit_deadline = conversion_date + timedelta(days=60)

        # Determine redeposit source
        source_for_redeposit = self._determine_redeposit_source(
            withholding_amount,
            available_cash,
            available_brokerage
        )

        reasoning = (
            f"60-Day Rollover Plan for Roth Conversion:\n"
            f"\n"
            f"Conversion Amount: ${conversion_amount:,.2f}\n"
            f"Estimated Tax Rate: {estimated_tax_rate*100:.1f}%\n"
            f"Withholding Amount: ${withholding_amount:,.2f}\n"
            f"Net Roth Deposit: ${net_conversion_deposit:,.2f}\n"
            f"\n"
            f"60-Day Redeposit Requirement:\n"
            f"  Due by: {redeposit_deadline.strftime('%B %d, %Y')}\n"
            f"  Amount: ${withholding_amount:,.2f}\n"
            f"  Source: {source_for_redeposit}\n"
            f"\n"
            f"IRS Rule (IRC §408(d)(3)(B)):\n"
            f"  • Withholding from Traditional IRA conversion must be redeposited\n"
            f"    within 60 calendar days\n"
            f"  • Using non-IRA funds (cash or brokerage is acceptable)\n"
            f"  • Failure to redeposit = withholding amount treated as income\n"
            f"  • Penalties: 20% premature distribution penalty if under 59.5"
        )

        return RolloverWithholdingPlan(
            conversion_amount=conversion_amount,
            withholding_amount=withholding_amount,
            net_conversion_deposit=net_conversion_deposit,
            redeposit_amount=withholding_amount,
            redeposit_deadline=redeposit_deadline,
            source_for_redeposit=source_for_redeposit,
            reasoning=reasoning
        )

    def _determine_redeposit_source(
        self,
        withholding_amount: float,
        available_cash: float,
        available_brokerage: float
    ) -> str:
        """
        Determine whether redeposit should come from cash or brokerage.

        Priority: Cash first (liquid, no tax impact), then Brokerage.

        Args:
            withholding_amount: Amount to redeposit
            available_cash: Available cash balance
            available_brokerage: Available brokerage balance

        Returns:
            'cash' or 'brokerage'
        """
        if available_cash >= withholding_amount:
            logger.info(
                f"Redeposit source: CASH (${withholding_amount:,.2f} available)"
            )
            return 'cash'
        elif available_cash + available_brokerage >= withholding_amount:
            logger.info(
                f"Redeposit source: CASH (${available_cash:,.2f}) + "
                f"BROKERAGE (${withholding_amount - available_cash:,.2f})"
            )
            return 'cash_and_brokerage'
        else:
            logger.warning(
                f"Insufficient funds for 60-day redeposit! "
                f"Need: ${withholding_amount:,.2f}, "
                f"Available: ${available_cash + available_brokerage:,.2f}"
            )
            return 'brokerage'

    def validate_redeposit_feasibility(
        self,
        withholding_amount: float,
        available_cash: float,
        available_brokerage: float
    ) -> Tuple[bool, str]:
        """
        Validate that sufficient funds exist to complete the 60-day redeposit.

        Args:
            withholding_amount: Amount needing redeposit
            available_cash: Available cash
            available_brokerage: Available brokerage

        Returns:
            Tuple of (is_feasible, message)
        """
        total_available = available_cash + available_brokerage

        if total_available >= withholding_amount:
            return True, (
                f"Redeposit is feasible. "
                f"Need: ${withholding_amount:,.2f}, "
                f"Available: ${total_available:,.2f}"
            )
        else:
            shortfall = withholding_amount - total_available
            return False, (
                f"Redeposit CANNOT be completed. "
                f"Shortfall: ${shortfall:,.2f}\n"
                f"Need: ${withholding_amount:,.2f}, "
                f"Available: ${total_available:,.2f}\n"
                f"Consider reducing conversion amount or increasing cash/brokerage."
            )

    def calculate_effective_conversion_cost(
        self,
        conversion_amount: float,
        withholding_amount: float,
        capital_gains_if_brokerage_source: float = 0.0
    ) -> Dict[str, float]:
        """
        Calculate the total effective cost of a Roth conversion with 60-day redeposit.

        Args:
            conversion_amount: Amount converted
            withholding_amount: Tax withholding amount
            capital_gains_if_brokerage_source: If redeposit comes from brokerage,
                                               any capital gains realized

        Returns:
            Dictionary with cost breakdown
        """
        # Total cost = withholding + capital gains tax
        capital_gains_tax = capital_gains_if_brokerage_source * 0.15  # Assume 15% LTCG rate
        total_out_of_pocket = withholding_amount + capital_gains_tax

        # Net to Roth
        net_roth_increase = conversion_amount

        # Cost per dollar in Roth
        cost_per_dollar = total_out_of_pocket / net_roth_increase if net_roth_increase > 0 else 0

        return {
            'conversion_amount': conversion_amount,
            'withholding_tax': withholding_amount,
            'capital_gains_if_brokerage': capital_gains_if_brokerage_source,
            'capital_gains_tax': capital_gains_tax,
            'total_out_of_pocket': total_out_of_pocket,
            'net_to_roth': net_roth_increase,
            'cost_per_dollar_to_roth': cost_per_dollar,
            'effective_tax_rate': total_out_of_pocket / conversion_amount if conversion_amount > 0 else 0
        }

    def generate_execution_checklist(
        self,
        plan: RolloverWithholdingPlan
    ) -> str:
        """
        Generate a step-by-step checklist for executing the conversion.

        Args:
            plan: RolloverWithholdingPlan to execute

        Returns:
            Formatted checklist string
        """
        checklist = (
            f"60-Day Rollover Execution Checklist\n"
            f"{'='*50}\n"
            f"\n"
            f"[ ] Step 1: January Conversion (Day 1)\n"
            f"    • Convert ${plan.conversion_amount:,.2f} from Traditional IRA to Roth\n"
            f"    • Withhold ${plan.withholding_amount:,.2f} for taxes\n"
            f"    • Roth receives: ${plan.net_conversion_deposit:,.2f}\n"
            f"    • Document the conversion date and amounts\n"
            f"\n"
            f"[ ] Step 2: Redeposit Preparation (Day 1-59)\n"
            f"    • Identify ${plan.redeposit_amount:,.2f} from {plan.source_for_redeposit}\n"
            f"    • Ensure funds are available by redeposit deadline\n"
            f"    • Do NOT take another loan/distribution to fund this\n"
            f"\n"
            f"[ ] Step 3: Redeposit to Traditional IRA (By Day 60)\n"
            f"    • Transfer ${plan.redeposit_amount:,.2f} BACK to Traditional IRA\n"
            f"    • Must complete by: {plan.redeposit_deadline.strftime('%B %d, %Y')} (60 days)\n"
            f"    • Keep proof of transfer (bank statement, broker confirmation)\n"
            f"\n"
            f"[ ] Step 4: Tax Filing\n"
            f"    • Form 8606 (Non-Taxable IRA Conversions)\n"
            f"    • Report conversion amount: ${plan.conversion_amount:,.2f}\n"
            f"    • Report withheld taxes: ${plan.withholding_amount:,.2f}\n"
            f"    • Redeposited amount reduces pro-rata calculation\n"
            f"\n"
            f"CRITICAL DATES:\n"
            f"  Conversion Date: Day 1\n"
            f"  Redeposit Deadline: {plan.redeposit_deadline.strftime('%B %d, %Y')}\n"
            f"  Days Available: 60\n"
        )

        return checklist
