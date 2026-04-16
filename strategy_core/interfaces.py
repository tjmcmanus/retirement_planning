"""
Core Interfaces for Strategy Components

Defines abstract base classes and protocols for all strategy components,
enabling dependency injection and testability.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Protocol, Tuple
from dataclasses import dataclass

# Forward declarations for type hints
class PortfolioBalances(Protocol):
    """Protocol for portfolio balance containers"""
    cash: float
    taxable: float
    traditional: float
    roth: float
    daf: float
    
    def total(self) -> float: ...


class YearlyStrategy(Protocol):
    """Protocol for yearly strategy results"""
    year: int
    age_primary: int
    age_spouse: int
    stage: str
    # ... other fields defined in models.py


class DecisionLog(Protocol):
    """Protocol for decision logging"""
    def add(self, category: str, decision: str, action: str, 
            reason: str, **values: Any) -> None: ...
    def all_decisions(self) -> List[Any]: ...
    def summary_lines(self) -> List[str]: ...


class ILifeStageStrategy(ABC):
    """
    Abstract base class for life stage withdrawal strategies.
    
    Each life stage (Accumulation, Early Retirement, Medicare, etc.) 
    implements this interface to provide stage-specific logic.
    """
    
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
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age (0 if single)
            year: Current year
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            True if this strategy should be used
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
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses needed
            **kwargs: Additional context (ages, tax info, etc.)
            
        Returns:
            YearlyStrategy with all calculated values
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this strategy stage"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of this strategy stage"""
        pass


class ITaxCalculator(ABC):
    """
    Abstract interface for tax calculations.
    
    Separates tax logic from strategy logic for better testability
    and maintainability.
    """
    
    @abstractmethod
    def calculate_federal_tax(
        self,
        taxable_income: float,
        filing_status: str,
        year: int
    ) -> Tuple[float, float, float]:
        """
        Calculate federal income tax.
        
        Args:
            taxable_income: Income subject to tax
            filing_status: 'single', 'married', 'married_separate'
            year: Tax year
            
        Returns:
            Tuple of (total_tax, max_rate, upper_bracket_limit)
        """
        pass
    
    @abstractmethod
    def calculate_capital_gains_tax(
        self,
        ltcg: float,
        ordinary_income: float,
        filing_status: str,
        year: int
    ) -> float:
        """
        Calculate long-term capital gains tax.
        
        Args:
            ltcg: Long-term capital gains amount
            ordinary_income: Ordinary income (for stacking)
            filing_status: Filing status
            year: Tax year
            
        Returns:
            Capital gains tax owed
        """
        pass
    
    @abstractmethod
    def calculate_state_tax(
        self,
        agi: float,
        state: str,
        year: int
    ) -> float:
        """
        Calculate state income tax.
        
        Args:
            agi: Adjusted Gross Income
            state: State code (e.g., 'CA', 'NY')
            year: Tax year
            
        Returns:
            State tax owed
        """
        pass
    
    @abstractmethod
    def calculate_irmaa_penalty(
        self,
        magi: float,
        filing_status: str,
        year: int
    ) -> Tuple[float, float]:
        """
        Calculate IRMAA (Medicare surcharge) penalty.
        
        Args:
            magi: Modified Adjusted Gross Income
            filing_status: Filing status
            year: Year for IRMAA calculation
            
        Returns:
            Tuple of (irmaa_penalty_primary, irmaa_penalty_spouse)
        """
        pass


class IAccountManager(ABC):
    """
    Abstract interface for managing account withdrawals and transfers.
    
    Handles the mechanics of moving money between accounts while
    tracking tax implications.
    """
    
    @abstractmethod
    def withdraw_from_cash(
        self,
        amount: float,
        current_balance: float
    ) -> Tuple[float, float]:
        """
        Withdraw from cash account.
        
        Args:
            amount: Amount to withdraw
            current_balance: Current cash balance
            
        Returns:
            Tuple of (amount_withdrawn, remaining_balance)
        """
        pass
    
    @abstractmethod
    def withdraw_from_taxable(
        self,
        amount: float,
        brokerage_account: Any,
        decision_log: Optional[DecisionLog] = None
    ) -> Tuple[float, float, float]:
        """
        Withdraw from taxable brokerage account.
        
        Args:
            amount: Amount to withdraw
            brokerage_account: BrokerageAccount instance
            decision_log: Optional logger for decisions
            
        Returns:
            Tuple of (amount_withdrawn, ltcg_realized, remaining_balance)
        """
        pass
    
    @abstractmethod
    def withdraw_from_traditional(
        self,
        amount: float,
        current_balance: float
    ) -> Tuple[float, float]:
        """
        Withdraw from traditional IRA/401k.
        
        Args:
            amount: Amount to withdraw
            current_balance: Current traditional balance
            
        Returns:
            Tuple of (amount_withdrawn, remaining_balance)
        """
        pass
    
    @abstractmethod
    def withdraw_from_roth(
        self,
        amount: float,
        current_balance: float
    ) -> Tuple[float, float]:
        """
        Withdraw from Roth IRA/401k.
        
        Args:
            amount: Amount to withdraw
            current_balance: Current Roth balance
            
        Returns:
            Tuple of (amount_withdrawn, remaining_balance)
        """
        pass
    
    @abstractmethod
    def convert_traditional_to_roth(
        self,
        amount: float,
        traditional_balance: float,
        roth_balance: float
    ) -> Tuple[float, float, float]:
        """
        Convert traditional IRA to Roth IRA.
        
        Args:
            amount: Amount to convert
            traditional_balance: Current traditional balance
            roth_balance: Current Roth balance
            
        Returns:
            Tuple of (amount_converted, new_traditional, new_roth)
        """
        pass


class IDecisionLogger(ABC):
    """
    Abstract interface for logging strategy decisions.
    
    Provides structured logging of all material decisions made
    during strategy calculation.
    """
    
    @abstractmethod
    def log_decision(
        self,
        category: str,
        decision: str,
        action: str,
        reason: str,
        **values: Any
    ) -> None:
        """
        Log a strategy decision.
        
        Args:
            category: Decision category (e.g., 'roth_conversion')
            decision: Short decision label
            action: What was decided
            reason: Human-readable explanation
            **values: Supporting numerical values
        """
        pass
    
    @abstractmethod
    def get_all_decisions(self) -> List[Any]:
        """Get all logged decisions"""
        pass
    
    @abstractmethod
    def get_summary(self) -> List[str]:
        """Get human-readable summary of all decisions"""
        pass


class IWithdrawalEngine(ABC):
    """
    Abstract interface for the main withdrawal strategy engine.
    
    Orchestrates the overall strategy calculation across multiple years
    and life stages.
    """
    
    @abstractmethod
    def calculate_multi_year_strategy(
        self,
        start_year: int,
        end_year: int,
        initial_balances: PortfolioBalances,
        **config: Any
    ) -> List[YearlyStrategy]:
        """
        Calculate withdrawal strategy across multiple years.
        
        Args:
            start_year: Starting year
            end_year: Ending year
            initial_balances: Starting portfolio balances
            **config: Configuration parameters
            
        Returns:
            List of YearlyStrategy objects, one per year
        """
        pass
    
    @abstractmethod
    def determine_stage(
        self,
        year: int,
        age_primary: int,
        age_spouse: int,
        has_wages: bool,
        has_ss: bool
    ) -> ILifeStageStrategy:
        """
        Determine which life stage strategy applies.
        
        Args:
            year: Current year
            age_primary: Primary person's age
            age_spouse: Spouse's age
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            The appropriate ILifeStageStrategy implementation
        """
        pass

# Made with Bob
