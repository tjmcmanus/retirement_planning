"""
Base Implementation for Life Stage Strategies

Provides a concrete base class that implements common functionality
for all life stage strategies, reducing code duplication.
"""

import logging
from typing import Any, Optional, Dict
from abc import abstractmethod

from .interfaces import ILifeStageStrategy, ITaxCalculator, IAccountManager, IDecisionLogger
from .models import PortfolioBalances, YearlyStrategy, DecisionLog

logger = logging.getLogger(__name__)


class BaseLifeStageStrategy(ILifeStageStrategy):
    """
    Base implementation of ILifeStageStrategy with common functionality.
    
    Provides dependency injection support and common helper methods
    that all life stage strategies can use.
    
    Attributes:
        _name: Strategy name
        _description: Strategy description
        tax_calculator: Injected tax calculator
        account_manager: Injected account manager
        decision_logger: Injected decision logger
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None,
        decision_logger: Optional[IDecisionLogger] = None
    ):
        """
        Initialize base strategy.
        
        Args:
            name: Human-readable strategy name
            description: Detailed strategy description
            tax_calculator: Optional tax calculator (can be injected later)
            account_manager: Optional account manager (can be injected later)
            decision_logger: Optional decision logger (can be injected later)
        """
        self._name = name
        self._description = description
        self.tax_calculator = tax_calculator
        self.account_manager = account_manager
        self.decision_logger = decision_logger
        
        logger.debug(f"Initialized {name} strategy")
    
    @property
    def name(self) -> str:
        """Human-readable name of this strategy stage"""
        return self._name
    
    @property
    def description(self) -> str:
        """Detailed description of this strategy stage"""
        return self._description
    
    @abstractmethod
    def applies(
        self,
        age_primary: int,
        age_spouse: int,
        year: int,
        has_wages: bool,
        has_ss: bool
    ) -> bool:
        """
        Determine if this strategy applies to the current situation.
        
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate the withdrawal strategy for this year.
        
        Must be implemented by subclasses.
        """
        pass
    
    def _create_yearly_strategy(
        self,
        year: int,
        age_primary: int,
        age_spouse: int,
        balances: PortfolioBalances
    ) -> YearlyStrategy:
        """
        Create a YearlyStrategy object with initial values.
        
        Helper method to reduce boilerplate in subclasses.
        
        Args:
            year: Current year
            age_primary: Primary person's age
            age_spouse: Spouse's age
            balances: Current portfolio balances
            
        Returns:
            YearlyStrategy with stage name and balances set
        """
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            cash_balance=balances.cash,
            taxable_balance=balances.taxable,
            traditional_balance=balances.traditional,
            roth_balance=balances.roth,
            daf_balance=balances.daf,
            decisions=DecisionLog()
        )
    
    def _log_decision(
        self,
        strategy: YearlyStrategy,
        category: str,
        decision: str,
        action: str,
        reason: str,
        **values: Any
    ) -> None:
        """
        Log a decision to the strategy's decision log.
        
        Helper method that handles both the strategy's internal log
        and any injected decision logger.
        
        Args:
            strategy: YearlyStrategy to log to
            category: Decision category
            decision: Short decision label
            action: What was decided
            reason: Human-readable explanation
            **values: Supporting numerical values
        """
        # Log to strategy's internal log
        strategy.decisions.add(category, decision, action, reason, **values)
        
        # Also log to injected logger if available
        if self.decision_logger:
            self.decision_logger.log_decision(
                category, decision, action, reason, **values
            )
    
    def _calculate_total_income(
        self,
        wages: float = 0.0,
        ss_benefits: float = 0.0,
        rmd_amount: float = 0.0,
        withdrawals: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate total income from all sources.
        
        Args:
            wages: Wage income
            ss_benefits: Social Security benefits
            rmd_amount: Required Minimum Distribution
            withdrawals: Dict of withdrawal amounts by account type
            
        Returns:
            Total income
        """
        total = wages + ss_benefits + rmd_amount
        
        if withdrawals:
            total += sum(withdrawals.values())
        
        return total
    
    def _calculate_total_taxes(
        self,
        federal_tax: float = 0.0,
        state_tax: float = 0.0,
        fica_tax: float = 0.0,
        ltcg_tax: float = 0.0
    ) -> float:
        """
        Calculate total taxes.
        
        Args:
            federal_tax: Federal income tax
            state_tax: State income tax
            fica_tax: FICA/payroll tax
            ltcg_tax: Long-term capital gains tax
            
        Returns:
            Total taxes
        """
        return federal_tax + state_tax + fica_tax + ltcg_tax
    
    def _validate_dependencies(self) -> None:
        """
        Validate that required dependencies are injected.
        
        Raises:
            RuntimeError: If required dependencies are missing
        """
        if not self.tax_calculator:
            raise RuntimeError(
                f"{self.name} requires a tax_calculator to be injected"
            )
        if not self.account_manager:
            raise RuntimeError(
                f"{self.name} requires an account_manager to be injected"
            )
    
    def _apply_growth_to_balances(
        self,
        balances: PortfolioBalances,
        growth_rate: float
    ) -> PortfolioBalances:
        """
        Apply annual growth to portfolio balances.
        
        Args:
            balances: Current balances
            growth_rate: Annual growth rate (e.g., 0.07 for 7%)
            
        Returns:
            New PortfolioBalances with growth applied
        """
        multiplier = 1 + growth_rate
        
        return PortfolioBalances(
            cash=balances.cash * multiplier,
            taxable=balances.taxable * multiplier,
            traditional=balances.traditional * multiplier,
            roth=balances.roth * multiplier,
            daf=balances.daf * multiplier
        )
    
    def _deduct_daf_annual_grant(
        self,
        balances: PortfolioBalances,
        year: int,
        start_year: int,
        inflation_rate: float = 0.02,
    ) -> PortfolioBalances:
        """
        Deduct the inflation-adjusted annual charitable grant from the DAF balance.

        The DAF account holds funds that will be granted to charities over time.
        Each year the ``annual_charitable_giving`` amount (from config, inflated
        from ``start_year``) is paid out.  Without this deduction the DAF balance
        grows indefinitely, which is misleading.

        Args:
            balances:      Current balances after contributions and growth.
            year:          Current calendar year.
            start_year:    First year of the strategy (used for inflation base).
            inflation_rate: Annual charitable giving inflation rate (default 2%).

        Returns:
            New PortfolioBalances with DAF reduced by the annual grant amount.
            The DAF balance is floored at 0 (no negative balance).
        """
        try:
            from config import get_config_manager
            cfg = get_config_manager()
            has_daf        = bool(cfg.get("charitable_giving", "has_daf", False))
            annual_giving  = float(cfg.get("charitable_giving", "annual_charitable_giving", 0))
            giving_start   = int(cfg.get("charitable_giving", "charitable_giving_start_age", 61))
            giving_end     = int(cfg.get("charitable_giving", "charitable_giving_end_age", 95))
            giving_inflation = float(cfg.get("charitable_giving", "charitable_giving_inflation_rate", 2.0)) / 100.0
        except Exception:
            return balances

        if not has_daf or annual_giving <= 0 or balances.daf <= 0:
            return balances

        # Check age window — only deduct while active charitable giving is configured
        try:
            from config import get_config_manager as _cfg
            _c = _cfg()
            p1_birth = _c.get("personal_info", "person1_birth_date", "1966-01-01")
            p1_birth_year = int(str(p1_birth).split("-")[0])
            age_primary = year - p1_birth_year
        except Exception:
            age_primary = 61  # safe default: allow deduction

        if age_primary < giving_start or age_primary > giving_end:
            return balances

        # Inflate from start_year
        years_elapsed = max(0, year - start_year)
        grant = annual_giving * ((1 + giving_inflation) ** years_elapsed)
        new_daf = max(0.0, balances.daf - grant)

        logger.info(
            f"Year {year}: DAF annual grant deducted: ${grant:,.0f} "
            f"(base=${annual_giving:,.0f}, {years_elapsed} yrs inflation), "
            f"DAF balance: ${balances.daf:,.0f} → ${new_daf:,.0f}"
        )

        return PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth,
            daf=new_daf,
            traditional_person1=balances.traditional_person1,
            traditional_person2=balances.traditional_person2,
        )

    def _calculate_shortfall(
        self,
        expenses: float,
        income: float,
        taxes: float,
        healthcare: float
    ) -> float:
        """
        Calculate funding shortfall that needs to be covered by withdrawals.
        
        Args:
            expenses: Annual expenses
            income: Income from wages, SS, etc.
            taxes: Total taxes
            healthcare: Healthcare costs
            
        Returns:
            Shortfall amount (positive means need more funds)
        """
        total_needs = expenses + taxes + healthcare
        shortfall = total_needs - income
        
        return max(0.0, shortfall)
    
    def _determine_withdrawal_sequence(
        self,
        shortfall: float,
        balances: PortfolioBalances,
        prefer_roth: bool = False
    ) -> Dict[str, float]:
        """
        Determine optimal withdrawal sequence to cover shortfall.
        
        Default sequence: Cash -> Taxable -> Traditional -> Roth
        Can be overridden by subclasses for stage-specific logic.
        
        Args:
            shortfall: Amount needed
            balances: Current balances
            prefer_roth: If True, prefer Roth over Traditional
            
        Returns:
            Dict mapping account type to withdrawal amount
        """
        withdrawals = {
            'cash': 0.0,
            'taxable': 0.0,
            'traditional': 0.0,
            'roth': 0.0
        }
        
        remaining = shortfall
        
        # 1. Cash first (no tax impact)
        if remaining > 0 and balances.cash > 0:
            cash_withdrawal = min(remaining, balances.cash)
            withdrawals['cash'] = cash_withdrawal
            remaining -= cash_withdrawal
        
        # 2. Taxable brokerage (capital gains tax)
        if remaining > 0 and balances.taxable > 0:
            taxable_withdrawal = min(remaining, balances.taxable)
            withdrawals['taxable'] = taxable_withdrawal
            remaining -= taxable_withdrawal
        
        # 3. Traditional or Roth (depending on preference)
        if remaining > 0:
            if prefer_roth and balances.roth > 0:
                roth_withdrawal = min(remaining, balances.roth)
                withdrawals['roth'] = roth_withdrawal
                remaining -= roth_withdrawal
            elif balances.traditional > 0:
                trad_withdrawal = min(remaining, balances.traditional)
                withdrawals['traditional'] = trad_withdrawal
                remaining -= trad_withdrawal
        
        # 4. Final fallback
        if remaining > 0:
            if balances.roth > 0:
                roth_withdrawal = min(remaining, balances.roth)
                withdrawals['roth'] = roth_withdrawal
                remaining -= roth_withdrawal
            elif balances.traditional > 0:
                trad_withdrawal = min(remaining, balances.traditional)
                withdrawals['traditional'] = trad_withdrawal
                remaining -= trad_withdrawal
        
        if remaining > 0.01:  # Small tolerance for rounding
            logger.warning(
                f"Unable to fully cover shortfall: ${remaining:,.2f} remaining"
            )
        
        return withdrawals
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"{self.__class__.__name__}(name='{self.name}')"

# Made with Bob
