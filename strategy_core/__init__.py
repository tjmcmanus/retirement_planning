"""
Strategy Core Module - Refactored Architecture

This module provides the core abstractions and interfaces for the retirement
planning withdrawal strategy system.

Key Components:
- Abstract base classes for strategy patterns
- Type-safe interfaces with comprehensive type hints
- Dependency injection support for testability
- Modular, composable components

Author: IBM Bob
Date: 2026-04-13
Version: 3.0 - Refactored Architecture
"""

from .interfaces import (
    ILifeStageStrategy,
    ITaxCalculator,
    IWithdrawalEngine,
    IAccountManager,
    IDecisionLogger,
)

from .models import (
    PortfolioBalances,
    YearlyStrategy,
    DecisionReason,
    DecisionLog,
    BrokerageTransaction,
    BrokerageAccount,
    HealthcareCostBreakdown,
    MedicareBreakdown,
)

from .base_strategy import BaseLifeStageStrategy
from .tax_calculator import TaxCalculator
from .account_manager import AccountManager
from .decision_logger import DecisionLogger

__all__ = [
    # Interfaces
    'ILifeStageStrategy',
    'ITaxCalculator',
    'IWithdrawalEngine',
    'IAccountManager',
    'IDecisionLogger',
    
    # Models
    'PortfolioBalances',
    'YearlyStrategy',
    'DecisionReason',
    'DecisionLog',
    'BrokerageTransaction',
    'BrokerageAccount',
    'HealthcareCostBreakdown',
    'MedicareBreakdown',
    
    # Implementations
    'BaseLifeStageStrategy',
    'TaxCalculator',
    'AccountManager',
    'DecisionLogger',
]

# Made with Bob
