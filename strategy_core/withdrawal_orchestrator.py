"""
January Bracket-Fill Withdrawal Orchestrator

Implements a simplified, single-decision-point withdrawal strategy:
1. Assess actual PNC cash balance
2. Calculate annual spending need (expenses + estimated taxes)
3. Calculate shortfall (spending - PNC balance)
4. Calculate 12% bracket available space
5. Split Traditional withdrawal: Part A (shortfall) + Part B (Roth conversion)
6. Execute Roth conversion with strategy optimization (DAF > RMD > BETR)
7. Mid-year supplement from Brokerage as needed (safety threshold = $50k)

Special handling for Stage 3 (Early Retirement): ACA subsidy is highest priority
if enabled—keep MAGI under 400% FPL threshold.
"""

import logging
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass

from .interfaces import ITaxCalculator, IAccountManager
from .models import PortfolioBalances, YearlyStrategy
from .decision_logger import DecisionLog

logger = logging.getLogger(__name__)

# Safety threshold for PNC cash balance
SAFETY_THRESHOLD_PNC = 50000.0

# Priority order for Roth conversion optimization
ROTH_CONVERSION_PRIORITY = [
    'daf',           # 1. Donor Advised Fund optimization
    'rmd_lookback',  # 2. RMD lookback to reduce future burden
    'betr'           # 3. Break-Even Tax Rate
]


@dataclass
class BracketFillCalculation:
    """Result of bracket-fill calculations."""
    pnc_balance: float
    annual_spending_need: float
    shortfall: float
    bracket_12_available: float
    traditional_part_a: float  # Amount to cover shortfall
    traditional_part_b: float  # Amount for Roth conversion (from remaining bracket)
    traditional_total: float   # Part A + Part B
    roth_conversion_amount: float
    estimated_total_tax: float
    aca_magi_threshold: Optional[float] = None  # For Stage 3 if ACA enabled


class JanuaryBracketFillOrchestrator:
    """
    Orchestrates the January bracket-fill withdrawal strategy.
    
    This replaces the complex BETR lookahead with a simple, deterministic
    decision made once per year in January.
    """

    def __init__(
        self,
        tax_calculator: ITaxCalculator,
        account_manager: IAccountManager
    ):
        """
        Initialize the orchestrator.

        Args:
            tax_calculator: Tax calculator for all tax computations
            account_manager: Account manager for executing withdrawals
        """
        self.tax_calculator = tax_calculator
        self.account_manager = account_manager

    def calculate_bracket_fill_withdrawal(
        self,
        year: int,
        pnc_balance: float,
        annual_expenses: float,
        filing_status: str,
        age_primary: int,
        age_spouse: int,
        other_ordinary_income: float = 0.0,
        aca_enabled: bool = False,
        aca_magi_threshold: Optional[float] = None,
        stage: str = "early_retirement"
    ) -> BracketFillCalculation:
        """
        Calculate the January bracket-fill withdrawal strategy.

        Args:
            year: Current tax year
            pnc_balance: Current PNC cash balance (actual spendable money)
            annual_expenses: Projected annual living expenses
            filing_status: Tax filing status (e.g., 'married_filing_jointly')
            age_primary: Primary person's age
            age_spouse: Spouse's age (0 if single)
            other_ordinary_income: Dividends, interest, rental, pension, etc.
            aca_enabled: Whether ACA subsidy optimization applies (Stage 3)
            aca_magi_threshold: Maximum MAGI to preserve ACA subsidy (typically 400% FPL)
            stage: Life stage for decision logging

        Returns:
            BracketFillCalculation with all withdrawal amounts
        """
        logger.info(
            f"[{stage}] Calculating bracket-fill withdrawal for year {year}\n"
            f"  PNC Balance: ${pnc_balance:,.2f}\n"
            f"  Annual Expenses: ${annual_expenses:,.2f}\n"
            f"  Filing Status: {filing_status}, Ages: {age_primary}/{age_spouse}"
        )

        # Step 1: Get standard deduction
        std_deduction = self.tax_calculator.calculate_standard_deduction(
            filing_status, year, age_primary, age_spouse
        )

        # Step 2: Get 12% bracket threshold
        bracket_12_threshold = self._get_12_percent_bracket_threshold(
            filing_status, year
        )

        # Step 3: Calculate available bracket space (accounting for other income)
        bracket_available = max(
            0,
            bracket_12_threshold - std_deduction - other_ordinary_income
        )

        logger.debug(
            f"Tax Bracket Analysis:\n"
            f"  Standard Deduction: ${std_deduction:,.2f}\n"
            f"  12% Bracket Threshold: ${bracket_12_threshold:,.2f}\n"
            f"  Other Ordinary Income: ${other_ordinary_income:,.2f}\n"
            f"  Available Bracket Space: ${bracket_available:,.2f}"
        )

        # Step 4: Estimate total tax (preliminary)
        # This is simplified; actual tax will be calculated after withdrawals
        estimated_tax = self._estimate_withdrawal_tax(
            annual_expenses, bracket_available, filing_status, year,
            age_primary, age_spouse
        )

        # Step 5: Calculate annual spending need
        annual_spending_need = annual_expenses + estimated_tax

        # Step 6: Calculate shortfall
        shortfall = max(0, annual_spending_need - pnc_balance)

        logger.info(
            f"Annual Spending Calculation:\n"
            f"  Living Expenses: ${annual_expenses:,.2f}\n"
            f"  Estimated Tax: ${estimated_tax:,.2f}\n"
            f"  Total Need: ${annual_spending_need:,.2f}\n"
            f"  PNC Balance: ${pnc_balance:,.2f}\n"
            f"  Shortfall: ${shortfall:,.2f}"
        )

        # Step 7: Split Traditional withdrawal
        traditional_part_a = shortfall  # Amount to cover shortfall
        traditional_part_b = max(0, bracket_available - traditional_part_a)

        # Step 8: ACA constraint (Stage 3 only)
        if aca_enabled and aca_magi_threshold is not None:
            traditional_part_b = self._constrain_for_aca_magi(
                traditional_part_b,
                traditional_part_a,
                other_ordinary_income,
                aca_magi_threshold
            )
            logger.info(
                f"ACA MAGI Constraint Applied: Roth conversion limited to "
                f"${traditional_part_b:,.2f} to preserve subsidy"
            )

        traditional_total = traditional_part_a + traditional_part_b
        roth_conversion_amount = traditional_part_b  # Same as Part B

        logger.info(
            f"Traditional Withdrawal Plan:\n"
            f"  Part A (Cover Shortfall): ${traditional_part_a:,.2f}\n"
            f"  Part B (Roth Conversion): ${traditional_part_b:,.2f}\n"
            f"  Total Traditional: ${traditional_total:,.2f}\n"
            f"  Roth Conversion Amount: ${roth_conversion_amount:,.2f}"
        )

        return BracketFillCalculation(
            pnc_balance=pnc_balance,
            annual_spending_need=annual_spending_need,
            shortfall=shortfall,
            bracket_12_available=bracket_available,
            traditional_part_a=traditional_part_a,
            traditional_part_b=traditional_part_b,
            traditional_total=traditional_total,
            roth_conversion_amount=roth_conversion_amount,
            estimated_total_tax=estimated_tax,
            aca_magi_threshold=aca_magi_threshold
        )

    def _get_12_percent_bracket_threshold(
        self,
        filing_status: str,
        year: int
    ) -> float:
        """
        Get the upper limit of the 12% federal tax bracket for the given year.
        
        Reads from income_rates.csv which contains actual tax bracket data.

        Args:
            filing_status: Tax filing status ('married_filing_jointly', 'single', etc.)
            year: Tax year

        Returns:
            Upper limit of 12% bracket
        """
        import csv
        import os
        
        # Path to income_rates.csv (in project root)
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'income_rates.csv')
        
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (int(row['year']) == year and
                        row['filing_status'] == filing_status and
                        float(row['rate']) == 0.12):
                        # Found the 12% bracket row; return the upper limit
                        return float(row['upper'])
        except Exception as e:
            logger.warning(f"Could not read income_rates.csv: {e}")
        
        # Fallback to hardcoded values if CSV not found
        logger.warning(f"Using fallback 12% bracket thresholds for {year}")
        brackets = {
            'single': 50400,
            'married_filing_jointly': 100800,
            'married_filing_separately': 50400,
            'head_of_household': 67500,
        }
        return brackets.get(filing_status, 100800)

    def _estimate_withdrawal_tax(
        self,
        expenses: float,
        traditional_withdrawal: float,
        filing_status: str,
        year: int,
        age_primary: int,
        age_spouse: int
    ) -> float:
        """
        Estimate total tax on withdrawals (preliminary, before execution).

        This is a simplified estimate used to calculate annual spending need.
        The actual tax will be calculated after all withdrawals are executed.

        Args:
            expenses: Annual living expenses
            traditional_withdrawal: Amount being withdrawn from Traditional
            filing_status: Tax filing status
            year: Tax year
            age_primary: Primary person's age
            age_spouse: Spouse's age

        Returns:
            Estimated total federal + state tax
        """
        # Simplified estimate: assume 12% federal rate on Traditional withdrawal
        # Add ~5% state tax (varies by state)
        # This is intentionally conservative to avoid under-funding
        
        federal_tax_estimate = traditional_withdrawal * 0.12
        state_tax_estimate = traditional_withdrawal * 0.05
        
        return federal_tax_estimate + state_tax_estimate

    def _constrain_for_aca_magi(
        self,
        traditional_part_b: float,
        traditional_part_a: float,
        other_ordinary_income: float,
        aca_magi_threshold: float
    ) -> float:
        """
        Constrain Roth conversion amount to preserve ACA subsidy.

        For Stage 3 (Early Retirement), if ACA is enabled, keep MAGI below
        400% FPL to preserve the ACA premium tax credit subsidy.

        Args:
            traditional_part_b: Proposed Roth conversion amount
            traditional_part_a: Required Traditional withdrawal (shortfall)
            other_ordinary_income: Other ordinary income sources
            aca_magi_threshold: Maximum MAGI threshold (typically 400% FPL)

        Returns:
            Constrained Roth conversion amount
        """
        # MAGI includes: standard income + capital gains (LTCG)
        # For simplicity, approximate MAGI as: Part A + Part B + other ordinary income
        # (ignoring LTCG and deductions for this preliminary estimate)
        
        total_proposed_withdrawals = traditional_part_a + traditional_part_b
        magi_if_full_conversion = total_proposed_withdrawals + other_ordinary_income
        
        if magi_if_full_conversion <= aca_magi_threshold:
            # Full conversion fits within ACA threshold
            return traditional_part_b
        
        # Reduce conversion to stay under ACA threshold
        max_allowed_agi = aca_magi_threshold - other_ordinary_income
        constrained_part_b = max(0, max_allowed_agi - traditional_part_a)
        
        logger.info(
            f"ACA MAGI Constraint: Reducing Roth conversion from "
            f"${traditional_part_b:,.2f} to ${constrained_part_b:,.2f}\n"
            f"  Threshold: ${aca_magi_threshold:,.2f}\n"
            f"  Part A + Other Income: ${traditional_part_a + other_ordinary_income:,.2f}"
        )
        
        return constrained_part_b

    def should_supplement_pnc(self, current_pnc_balance: float) -> bool:
        """
        Determine if mid-year PNC supplementation is needed.

        Args:
            current_pnc_balance: Current PNC cash balance

        Returns:
            True if balance is below safety threshold and needs supplementation
        """
        return current_pnc_balance < SAFETY_THRESHOLD_PNC

    def calculate_brokerage_supplement(
        self,
        current_pnc_balance: float,
        target_pnc_balance: float = SAFETY_THRESHOLD_PNC
    ) -> float:
        """
        Calculate how much to withdraw from Brokerage to restore PNC.

        Args:
            current_pnc_balance: Current PNC balance
            target_pnc_balance: Target PNC balance (default = safety threshold)

        Returns:
            Amount to withdraw from Brokerage to PNC
        """
        if current_pnc_balance >= target_pnc_balance:
            return 0.0
        
        supplement_amount = target_pnc_balance - current_pnc_balance
        return supplement_amount
