"""
Stage 3 Early Retirement - January Bracket-Fill Implementation

Refactored to use the new simplified bracket-fill withdrawal strategy
with ACA subsidy optimization as the highest priority.
"""

import logging
from typing import Any, Optional, Dict, Tuple

from strategy_core.base_strategy import BaseLifeStageStrategy
from strategy_core.interfaces import ITaxCalculator, IAccountManager
from strategy_core.models import PortfolioBalances, YearlyStrategy
from strategy_core.withdrawal_orchestrator import (
    JanuaryBracketFillOrchestrator,
    BracketFillCalculation,
    SAFETY_THRESHOLD_PNC
)

logger = logging.getLogger(__name__)

# Constants
MEDICARE_AGE = 65
ACA_FPL_THRESHOLD = 4.0  # 400% of Federal Poverty Level


class Stage3EarlyRetirementBracketFill(BaseLifeStageStrategy):
    """
    Stage 3: Early Retirement (Pre-Medicare, Pre-SS, Pre-RMD)
    
    Uses January Bracket-Fill strategy with ACA subsidy as highest priority.
    
    Strategy:
    1. Assess PNC cash balance (actual spendable money)
    2. Calculate annual spending need (expenses + estimated taxes)
    3. Calculate shortfall (spending − PNC)
    4. Calculate 12% bracket available
    5. Split Traditional: Part A (shortfall) + Part B (Roth conversion)
    6. Apply ACA constraint if enabled (keep MAGI ≤ 400% FPL)
    7. Optimize remaining Roth conversion: DAF > RMD > BETR
    """

    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """Initialize Stage 3 with bracket-fill strategy."""
        super().__init__(
            name="Stage 3: Early Retirement (Bracket-Fill)",
            description="Pre-Medicare, pre-SS - January bracket-fill with ACA optimization",
            tax_calculator=tax_calculator,
            account_manager=account_manager
        )
        self.orchestrator = JanuaryBracketFillOrchestrator(
            tax_calculator=tax_calculator or self.tax_calculator,
            account_manager=account_manager or self.account_manager
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
        Calculate early retirement strategy with January bracket-fill.

        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            **kwargs: Additional parameters including:
                - pnc_balance: Current PNC cash balance (REQUIRED)
                - age_primary: Primary person's age
                - age_spouse: Spouse's age
                - filing_status: Tax filing status
                - state: State for state tax
                - aca_enabled: Whether ACA subsidy applies
                - brokerage_account: BrokerageAccount instance for LOFO

        Returns:
            YearlyStrategy with all calculations
        """
        # Validate dependencies
        self._validate_dependencies()

        # Extract parameters
        pnc_balance = kwargs.get('pnc_balance', 0.0)
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        filing_status = kwargs.get('filing_status', 'married_filing_jointly')
        state = kwargs.get('state', 'PA')
        aca_enabled = kwargs.get('aca_enabled', False)
        brokerage_account = kwargs.get('brokerage_account')

        logger.info(
            f"Stage 3 Bracket-Fill calculation for {year}\n"
            f"  PNC Balance: ${pnc_balance:,.2f}\n"
            f"  Expenses: ${expenses:,.2f}\n"
            f"  ACA Enabled: {aca_enabled}"
        )

        # Create base strategy
        strategy = self._create_yearly_strategy(
            year, age_primary, age_spouse, balances
        )

        # Get ACA premium and MAGI threshold (if applicable)
        aca_premium = 0.0
        aca_magi_threshold = None

        if aca_enabled:
            aca_premium = self._calculate_aca_premium(
                strategy, year, age_primary, age_spouse
            )
            aca_magi_threshold = self._calculate_aca_magi_threshold(year)
            logger.info(
                f"Stage 3: ACA Enabled\n"
                f"  Premium: ${aca_premium:,.2f}\n"
                f"  MAGI Threshold: ${aca_magi_threshold:,.2f}"
            )

        # Get other ordinary income sources
        other_ordinary_income = self._calculate_other_ordinary_income(
            year, age_primary, age_spouse
        )

        # Calculate bracket-fill withdrawal
        calc = self.orchestrator.calculate_bracket_fill_withdrawal(
            year=year,
            pnc_balance=pnc_balance,
            annual_expenses=expenses,
            filing_status=filing_status,
            age_primary=age_primary,
            age_spouse=age_spouse,
            other_ordinary_income=other_ordinary_income,
            aca_enabled=aca_enabled,
            aca_magi_threshold=aca_magi_threshold,
            stage="Stage 3"
        )

        # Log the calculation
        self._log_bracket_fill_decision(strategy, calc, aca_enabled)

        # Execute withdrawals
        # For now, store in strategy; actual execution happens at portfolio level
        strategy.transactions = {
            'pnc_balance_start': pnc_balance,
            'traditional_withdrawal_part_a': calc.traditional_part_a,
            'traditional_withdrawal_part_b': calc.traditional_part_b,
            'traditional_total': calc.traditional_total,
            'roth_conversion_amount': calc.roth_conversion_amount,
            'estimated_tax': calc.estimated_total_tax,
            'aca_premium': aca_premium,
            'safety_threshold': SAFETY_THRESHOLD_PNC
        }

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
            from strategy import calculate_aca_premium_for_year
            aca_premium = calculate_aca_premium_for_year(year, age_primary, age_spouse)
        except ImportError:
            # Fallback estimate
            num_people = 2 if age_spouse > 0 else 1
            aca_premium = 12000.0 * num_people

        self._log_decision(
            strategy,
            'aca_decisions',
            'ACA Premium (Stage 3 Bracket-Fill)',
            f'ACA premium: ${aca_premium:,.0f}',
            'Pre-Medicare retirees must purchase ACA marketplace coverage. '
            'This withdrawal strategy keeps MAGI below 400% FPL to preserve '
            'ACA premium tax credits.',
            aca_premium=aca_premium,
            age_primary=age_primary,
            age_spouse=age_spouse
        )

        return aca_premium

    def _calculate_aca_magi_threshold(self, year: int) -> float:
        """
        Calculate 400% of Federal Poverty Level for MAGI constraint.

        Args:
            year: Current year

        Returns:
            MAGI threshold amount (400% FPL)
        """
        try:
            from strategy import _get_medicare_premiums_row
            prem_row = _get_medicare_premiums_row(year)
            # Assume married couple (2 people)
            fpl = prem_row['fpl_base'] + prem_row['fpl_per_person'] * 1
            return fpl * ACA_FPL_THRESHOLD
        except (ImportError, KeyError):
            # Fallback: approximate 400% FPL for 2024
            # Single: ~$54,000, Married: ~$74,000
            return 74000.0

    def _calculate_other_ordinary_income(
        self,
        year: int,
        age_primary: int,
        age_spouse: int
    ) -> float:
        """
        Calculate other ordinary income sources (dividends, interest, rental, pension).

        Args:
            year: Current year
            age_primary: Primary person's age
            age_spouse: Spouse's age

        Returns:
            Total other ordinary income
        """
        # This is a placeholder; in full implementation, would pull from config
        # For now, assume minimal or zero other ordinary income in early retirement
        return 0.0

    def _log_bracket_fill_decision(
        self,
        strategy: YearlyStrategy,
        calc: BracketFillCalculation,
        aca_enabled: bool
    ) -> None:
        """
        Log the bracket-fill calculation decision.

        Args:
            strategy: YearlyStrategy to log to
            calc: BracketFillCalculation result
            aca_enabled: Whether ACA optimization is active
        """
        decision_text = (
            f"January Bracket-Fill Withdrawal Strategy\n"
            f"\n"
            f"PNC Analysis:\n"
            f"  Current Balance: ${calc.pnc_balance:,.2f}\n"
            f"  Annual Spending: ${calc.annual_spending_need:,.2f}\n"
            f"  Shortfall: ${calc.shortfall:,.2f}\n"
            f"\n"
            f"12% Bracket Analysis:\n"
            f"  Available Space: ${calc.bracket_12_available:,.2f}\n"
            f"\n"
            f"Traditional Withdrawal Plan:\n"
            f"  Part A (Shortfall): ${calc.traditional_part_a:,.2f}\n"
            f"  Part B (Roth Conv.): ${calc.traditional_part_b:,.2f}\n"
            f"  Total: ${calc.traditional_total:,.2f}\n"
            f"\n"
            f"Roth Conversion: ${calc.roth_conversion_amount:,.2f}\n"
            f"Estimated Tax: ${calc.estimated_total_tax:,.2f}\n"
        )

        if aca_enabled:
            decision_text += (
                f"\nACA MAGI Constraint (Priority 1):\n"
                f"  Threshold: ${calc.aca_magi_threshold:,.2f}\n"
                f"  Conversion limited to preserve subsidy\n"
            )

        self._log_decision(
            strategy,
            'withdrawal_orchestration',
            'January Bracket-Fill Strategy',
            decision_text,
            'Single annual decision point in January: fund annual spending need '
            'from PNC + Traditional withdrawal up to 12% bracket, with ACA subsidy '
            'as highest priority if applicable. Supplement from Brokerage (LOFO) '
            'mid-year if PNC drops below $50k safety threshold.'
        )
