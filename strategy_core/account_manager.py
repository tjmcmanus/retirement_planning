"""
Account Manager Implementation

Handles account withdrawals, transfers, and balance management with
proper tracking of tax implications.
"""

import logging
from typing import Tuple, Optional, Any

from .interfaces import IAccountManager
from .models import BrokerageAccount, DecisionLog

logger = logging.getLogger(__name__)


class AccountManager(IAccountManager):
    """
    Concrete implementation of account management operations.
    
    Handles withdrawals from different account types while tracking
    tax implications and maintaining proper accounting.
    """
    
    def __init__(self):
        """Initialize account manager."""
        logger.debug("Initialized AccountManager")
    
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
        if amount <= 0:
            return 0.0, current_balance
        
        amount_withdrawn = min(amount, current_balance)
        remaining_balance = current_balance - amount_withdrawn
        
        logger.debug(
            f"Cash withdrawal: requested=${amount:,.2f}, "
            f"withdrawn=${amount_withdrawn:,.2f}, "
            f"remaining=${remaining_balance:,.2f}"
        )
        
        return amount_withdrawn, remaining_balance
    
    def withdraw_from_taxable(
        self,
        amount: float,
        brokerage_account: BrokerageAccount,
        decision_log: Optional[DecisionLog] = None
    ) -> Tuple[float, float, float]:
        """
        Withdraw from taxable brokerage account using FIFO.
        
        Args:
            amount: Amount to withdraw
            brokerage_account: BrokerageAccount instance
            decision_log: Optional logger for decisions
            
        Returns:
            Tuple of (amount_withdrawn, ltcg_realized, remaining_balance)
        """
        if amount <= 0:
            return 0.0, 0.0, brokerage_account.total_value()
        
        initial_balance = brokerage_account.total_value()
        
        # Use FIFO withdrawal from brokerage account
        amount_withdrawn, ltcg_realized = brokerage_account.withdraw_fifo(amount)
        
        remaining_balance = brokerage_account.total_value()
        
        logger.debug(
            f"Taxable withdrawal: requested=${amount:,.2f}, "
            f"withdrawn=${amount_withdrawn:,.2f}, "
            f"LTCG=${ltcg_realized:,.2f}, "
            f"remaining=${remaining_balance:,.2f}"
        )
        
        # Log decision if logger provided
        if decision_log and amount_withdrawn > 0:
            decision_log.add(
                'brokerage_replenishment',
                'Taxable Withdrawal',
                f'Withdraw ${amount_withdrawn:,.0f}',
                f'FIFO withdrawal realized ${ltcg_realized:,.0f} in LTCG',
                amount=amount_withdrawn,
                ltcg=ltcg_realized,
                remaining=remaining_balance
            )
        
        return amount_withdrawn, ltcg_realized, remaining_balance
    
    def withdraw_from_traditional(
        self,
        amount: float,
        current_balance: float
    ) -> Tuple[float, float]:
        """
        Withdraw from traditional IRA/401k.
        
        Withdrawals are fully taxable as ordinary income.
        
        Args:
            amount: Amount to withdraw
            current_balance: Current traditional balance
            
        Returns:
            Tuple of (amount_withdrawn, remaining_balance)
        """
        if amount <= 0:
            return 0.0, current_balance
        
        amount_withdrawn = min(amount, current_balance)
        remaining_balance = current_balance - amount_withdrawn
        
        logger.debug(
            f"Traditional withdrawal: requested=${amount:,.2f}, "
            f"withdrawn=${amount_withdrawn:,.2f}, "
            f"remaining=${remaining_balance:,.2f}"
        )
        
        return amount_withdrawn, remaining_balance
    
    def withdraw_from_roth(
        self,
        amount: float,
        current_balance: float
    ) -> Tuple[float, float]:
        """
        Withdraw from Roth IRA/401k.
        
        Qualified withdrawals are tax-free.
        
        Args:
            amount: Amount to withdraw
            current_balance: Current Roth balance
            
        Returns:
            Tuple of (amount_withdrawn, remaining_balance)
        """
        if amount <= 0:
            return 0.0, current_balance
        
        amount_withdrawn = min(amount, current_balance)
        remaining_balance = current_balance - amount_withdrawn
        
        logger.debug(
            f"Roth withdrawal: requested=${amount:,.2f}, "
            f"withdrawn=${amount_withdrawn:,.2f}, "
            f"remaining=${remaining_balance:,.2f}"
        )
        
        return amount_withdrawn, remaining_balance
    
    def convert_traditional_to_roth(
        self,
        amount: float,
        traditional_balance: float,
        roth_balance: float
    ) -> Tuple[float, float, float]:
        """
        Convert traditional IRA to Roth IRA.
        
        Conversion amount is taxable as ordinary income in the year of conversion.
        
        Args:
            amount: Amount to convert
            traditional_balance: Current traditional balance
            roth_balance: Current Roth balance
            
        Returns:
            Tuple of (amount_converted, new_traditional, new_roth)
        """
        if amount <= 0:
            return 0.0, traditional_balance, roth_balance
        
        amount_converted = min(amount, traditional_balance)
        new_traditional = traditional_balance - amount_converted
        new_roth = roth_balance + amount_converted
        
        logger.debug(
            f"Roth conversion: requested=${amount:,.2f}, "
            f"converted=${amount_converted:,.2f}, "
            f"traditional=${new_traditional:,.2f}, "
            f"roth=${new_roth:,.2f}"
        )
        
        return amount_converted, new_traditional, new_roth
    
    def transfer_to_cash(
        self,
        amount: float,
        source_balance: float,
        cash_balance: float,
        source_type: str = "unknown"
    ) -> Tuple[float, float, float]:
        """
        Transfer funds to cash account from another account.
        
        Args:
            amount: Amount to transfer
            source_balance: Current source account balance
            cash_balance: Current cash balance
            source_type: Type of source account (for logging)
            
        Returns:
            Tuple of (amount_transferred, new_source_balance, new_cash_balance)
        """
        if amount <= 0:
            return 0.0, source_balance, cash_balance
        
        amount_transferred = min(amount, source_balance)
        new_source_balance = source_balance - amount_transferred
        new_cash_balance = cash_balance + amount_transferred
        
        logger.debug(
            f"Transfer to cash from {source_type}: "
            f"amount=${amount_transferred:,.2f}, "
            f"source_remaining=${new_source_balance:,.2f}, "
            f"cash_new=${new_cash_balance:,.2f}"
        )
        
        return amount_transferred, new_source_balance, new_cash_balance
    
    def calculate_required_minimum_distribution(
        self,
        traditional_balance: float,
        age: int,
        year: int
    ) -> float:
        """
        Calculate Required Minimum Distribution (RMD).
        
        Args:
            traditional_balance: Traditional IRA/401k balance
            age: Account owner's age
            year: Current year
            
        Returns:
            RMD amount
        """
        if age < 73:  # RMD age as of 2024 (SECURE Act 2.0)
            return 0.0
        
        if traditional_balance <= 0:
            return 0.0
        
        # Import RMD calculation
        try:
            from calculations import get_rmd_value
            rmd = get_rmd_value(traditional_balance, age, year)
            
            logger.debug(
                f"RMD calculation: age={age}, "
                f"balance=${traditional_balance:,.2f}, "
                f"rmd=${rmd:,.2f}"
            )
            
            return rmd
            
        except ImportError:
            logger.warning("RMD calculation not available, using simple approximation")
            # Simple approximation using uniform lifetime table
            divisor = max(1.0, 110 - age)  # Simplified divisor
            rmd = traditional_balance / divisor
            return rmd
        except Exception as e:
            logger.error(f"Error calculating RMD: {e}")
            return 0.0
    
    def validate_withdrawal_feasibility(
        self,
        requested_amount: float,
        available_balance: float,
        account_type: str
    ) -> bool:
        """
        Validate that a withdrawal is feasible.
        
        Args:
            requested_amount: Amount requested
            available_balance: Available balance
            account_type: Type of account
            
        Returns:
            True if withdrawal is feasible
            
        Raises:
            ValueError: If withdrawal exceeds available balance by significant margin
        """
        if requested_amount <= 0:
            return True
        
        if requested_amount > available_balance * 1.01:  # 1% tolerance
            raise ValueError(
                f"Insufficient funds in {account_type}: "
                f"requested=${requested_amount:,.2f}, "
                f"available=${available_balance:,.2f}"
            )
        
        return True

# Made with Bob
