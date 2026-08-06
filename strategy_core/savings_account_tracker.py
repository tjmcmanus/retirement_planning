"""
Savings Account (PNC) Tracking and Spending Cash Management

The PNC Savings Account is your actual checking/savings account ($138,772.54).

This module provides:
1. Track actual PNC Savings account balance
2. Calculate "spendable cash" = PNC balance minus safety reserve
3. Identify when to supplement from Brokerage (LOFO when PNC drops)
4. Plan mid-year funding if PNC falls below safety threshold

Concept:
  PNC Savings Account = Actual spendable cash
  Safety Reserve = Amount to maintain for 4-5 months emergency buffer ($50k)
  Spendable = PNC Savings - Safety Reserve

For example (Jan 1):
  PNC Savings account balance: $138,772.54
  Safety reserve (to maintain): $50,000
  Available for annual expenses: $88,772.54
"""

import logging
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SavingsAccountSnapshot:
    """Point-in-time snapshot of savings account status."""
    date: datetime
    pnc_balance: float
    safety_reserve: float
    available_for_spending: float
    is_below_reserve: bool
    supplementation_needed: float


class SavingsAccountTracker:
    """
    Tracks the PNC Savings Account balance and spending cash availability.
    
    This is a real bank account, not a portfolio category.
    """
    
    def __init__(
        self,
        account_name: str = "PNC",
        safety_reserve: float = 55667.0  # 5 months × ($133,600 / 12) ≈ $55,667
    ):
        """
        Initialize savings account tracker.
        
        Args:
            account_name: Name of the savings account (e.g., "PNC")
            safety_reserve: Minimum balance before triggering mid-year Brokerage
                supplementation. Default = 5 months of expenses ($133,600 base / 12 × 5 ≈ $55,667).
                Set via config: tax_strategy.savings_safety_reserve
        """
        self.account_name = account_name
        self.safety_reserve = safety_reserve
        self.snapshots = []
    
    def assess_available_for_spending(
        self,
        pnc_balance: float,
        date: Optional[datetime] = None
    ) -> SavingsAccountSnapshot:
        """
        Assess how much is available for spending vs. emergency reserve.
        
        Args:
            pnc_balance: Current PNC Savings account balance
            date: Snapshot date (default now)
        
        Returns:
            SavingsAccountSnapshot with breakdown
        """
        if date is None:
            date = datetime.now()
        
        available_for_spending = max(0, pnc_balance - self.safety_reserve)
        is_below_reserve = pnc_balance < self.safety_reserve
        supplementation_needed = max(0, self.safety_reserve - pnc_balance)
        
        snapshot = SavingsAccountSnapshot(
            date=date,
            pnc_balance=pnc_balance,
            safety_reserve=self.safety_reserve,
            available_for_spending=available_for_spending,
            is_below_reserve=is_below_reserve,
            supplementation_needed=supplementation_needed
        )
        
        self.snapshots.append(snapshot)
        
        logger.debug(
            f"Savings account snapshot {date.strftime('%Y-%m-%d')}: "
            f"PNC=${pnc_balance:,.0f}, "
            f"Safety=${self.safety_reserve:,.0f}, "
            f"Available=${available_for_spending:,.0f}, "
            f"Below reserve: {is_below_reserve}"
        )
        
        return snapshot
    
    def assess_supplementation_need(
        self,
        pnc_balance: float,
        monthly_spending_rate: float = 11300.0
    ) -> Tuple[bool, float, str]:
        """
        Determine if we need to supplement savings account from Brokerage.
        
        Trigger: PNC balance < safety reserve (roughly 4-5 months of expenses)
        
        Args:
            pnc_balance: Current PNC Savings balance
            monthly_spending_rate: Average monthly spending
        
        Returns:
            Tuple of (supplementation_needed, amount_to_supplement, reason)
        """
        months_of_cash = pnc_balance / monthly_spending_rate if monthly_spending_rate > 0 else 0
        
        if pnc_balance < self.safety_reserve:
            supplementation_needed = self.safety_reserve - pnc_balance
            reason = (
                f"PNC Savings below safety reserve. "
                f"Balance: ${pnc_balance:,.0f}, "
                f"Months of cash: {months_of_cash:.1f}, "
                f"Reserve: ${self.safety_reserve:,.0f}, "
                f"Need: ${supplementation_needed:,.0f}"
            )
            logger.info(f"Mid-year supplementation triggered: {reason}")
            return True, supplementation_needed, reason
        else:
            reason = (
                f"PNC Savings healthy. "
                f"Balance: ${pnc_balance:,.0f}, "
                f"Months of cash: {months_of_cash:.1f}, "
                f"Reserve: ${self.safety_reserve:,.0f}"
            )
            return False, 0.0, reason
    
    def plan_brokerage_supplementation(
        self,
        supplementation_amount: float,
        available_brokerage: float,
        brokerage_ltcg_ratio: float = 0.40
    ) -> Dict:
        """
        Plan to supplement PNC Savings from Brokerage using LOFO (Lowest-gain First).
        
        Args:
            supplementation_amount: Amount needed to restore to safety reserve
            available_brokerage: Available Brokerage balance
            brokerage_ltcg_ratio: Ratio of LTCG in brokerage
        
        Returns:
            Dictionary with supplementation plan
        """
        if available_brokerage < supplementation_amount:
            shortfall = supplementation_amount - available_brokerage
            logger.warning(
                f"Insufficient Brokerage for full supplementation. "
                f"Need: ${supplementation_amount:,.0f}, "
                f"Available: ${available_brokerage:,.0f}, "
                f"Shortfall: ${shortfall:,.0f}"
            )
        
        # LOFO: Sell lowest-gain lots first (minimize LTCG realization)
        basis_ratio = 1 - brokerage_ltcg_ratio
        amount_to_sell = min(supplementation_amount, available_brokerage)
        
        basis_realized = amount_to_sell * basis_ratio
        ltcg_realized = amount_to_sell * brokerage_ltcg_ratio
        
        plan = {
            'supplementation_amount': supplementation_amount,
            'available_brokerage': available_brokerage,
            'amount_to_sell': amount_to_sell,
            'basis_realized': basis_realized,
            'ltcg_realized': ltcg_realized,
            'feasible': available_brokerage >= supplementation_amount,
            'reason': (
                f"Sell ${amount_to_sell:,.0f} Brokerage (LOFO) → PNC Savings: "
                f"basis=${basis_realized:,.0f}, "
                f"LTCG=${ltcg_realized:,.0f}"
            )
        }
        
        logger.info(f"Brokerage supplementation plan: {plan['reason']}")
        return plan
    
    def get_summary(self) -> Dict:
        """Get summary of all snapshots."""
        if not self.snapshots:
            return {'message': 'No snapshots recorded'}
        
        latest = self.snapshots[-1]
        below_reserve_count = sum(1 for s in self.snapshots if s.is_below_reserve)
        
        return {
            'account_name': self.account_name,
            'latest_date': latest.date,
            'latest_balance': latest.pnc_balance,
            'latest_available': latest.available_for_spending,
            'total_snapshots': len(self.snapshots),
            'snapshots_below_reserve': below_reserve_count,
            'safety_reserve': self.safety_reserve,
            'all_snapshots': self.snapshots
        }
