# Life Stage Refactoring Template

## Overview

This document provides a template and guidelines for refactoring the remaining 6 life stages to use the new `BaseLifeStageStrategy` architecture with dependency injection.

## Refactoring Pattern

Each stage should follow this consistent pattern:

### 1. File Structure

```
strategy_core/stages/
├── __init__.py
├── stage1_accumulation.py      ✅ COMPLETED
├── stage2_prep_retirement.py   ⬜ TODO
├── stage3_early_retirement.py  ⬜ TODO
├── stage4_medicare.py          ⬜ TODO
├── stage5_social_security.py   ⬜ TODO
├── stage6_rmd.py               ⬜ TODO
└── stage7_surviving_spouse.py  ⬜ TODO
```

### 2. Class Template

```python
"""
Stage X: [Stage Name]

Refactored implementation using BaseLifeStageStrategy with dependency injection.
"""

import logging
from typing import Any, Optional

from ..base_strategy import BaseLifeStageStrategy
from ..interfaces import ITaxCalculator, IAccountManager
from ..models import PortfolioBalances, YearlyStrategy

logger = logging.getLogger(__name__)


class StageXName(BaseLifeStageStrategy):
    """
    Stage X: [Stage Name]
    
    - [Key characteristic 1]
    - [Key characteristic 2]
    - [Key characteristic 3]
    """
    
    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """
        Initialize Stage X strategy.
        
        Args:
            tax_calculator: Tax calculator for tax computations
            account_manager: Account manager for withdrawals/conversions
        """
        super().__init__(
            name="Stage X: [Name]",
            description="[Description]",
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
        Determine if this strategy applies.
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            True if this stage applies
        """
        # Implement stage-specific logic
        pass
    
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate withdrawal strategy for this stage.
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            **kwargs: Additional parameters
            
        Returns:
            YearlyStrategy with all calculations
        """
        # Validate dependencies
        self._validate_dependencies()
        
        # Extract parameters
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        filing_status = kwargs.get('filing_status', 'married')
        
        # Create base strategy object
        strategy = self._create_yearly_strategy(
            year, age_primary, age_spouse, balances
        )
        
        # Implement stage-specific calculations
        # Use helper methods from base class:
        # - self._calculate_shortfall()
        # - self._determine_withdrawal_sequence()
        # - self._log_decision()
        # - self.tax_calculator methods
        # - self.account_manager methods
        
        return strategy
```

## Stage-Specific Refactoring Guidelines

### Stage 2: Prep for Retirement
**File**: `stage2_prep_retirement.py`
**Original**: Lines 4088-4592 in strategy.py

**Key Features**:
- Within 10 years of retirement
- Cash buffer building
- Roth conversion optimization
- BETR-based decisions

**Refactoring Focus**:
- Extract cash buffer calculation logic
- Modularize Roth conversion decisions
- Use tax calculator for bracket analysis

### Stage 3: Early Retirement
**File**: `stage3_early_retirement.py`
**Original**: Lines 4595-5095 in strategy.py

**Key Features**:
- Pre-Medicare, pre-SS
- ACA subsidy optimization
- BETR-optimized Roth conversions
- Tax-efficient withdrawal sequencing

**Refactoring Focus**:
- Extract ACA subsidy calculations
- Modularize IRMAA avoidance logic
- Use account manager for optimal withdrawals

### Stage 4: Medicare
**File**: `stage4_medicare.py`
**Original**: Lines 5098-5651 in strategy.py

**Key Features**:
- Medicare Part B/D costs
- IRMAA optimization with 2-year lookback
- Continued Roth conversions
- Healthcare cost management

**Refactoring Focus**:
- Extract Medicare cost calculations
- Modularize IRMAA penalty logic
- Use tax calculator for MAGI calculations

### Stage 5: Social Security
**File**: `stage5_social_security.py`
**Original**: Lines 5654-6392 in strategy.py

**Key Features**:
- Social Security benefits
- SS taxation calculations
- Pre-RMD optimization
- BETR-based conversions

**Refactoring Focus**:
- Extract SS benefit calculations
- Modularize SS taxation logic
- Use tax calculator for combined income

### Stage 6: RMD
**File**: `stage6_rmd.py`
**Original**: Lines 6395-6855 in strategy.py

**Key Features**:
- Required Minimum Distributions
- RMD lookback optimization
- Full retirement income
- Tax management

**Refactoring Focus**:
- Extract RMD calculation logic
- Modularize lookback optimization
- Use account manager for RMD withdrawals

### Stage 7: Surviving Spouse
**File**: `stage7_surviving_spouse.py`
**Original**: Lines 6858-7178 in strategy.py

**Key Features**:
- Single filer status
- Adjusted tax brackets
- Modified withdrawal strategy
- Estate considerations

**Refactoring Focus**:
- Extract surviving spouse logic
- Modularize filing status changes
- Use tax calculator for single filer brackets

## Common Refactoring Steps

### 1. Extract Original Logic
```python
# Read original implementation from strategy.py
# Identify key calculations and decision points
# Note dependencies on external functions
```

### 2. Create Stage Class
```python
class StageXName(BaseLifeStageStrategy):
    def __init__(self, tax_calculator=None, account_manager=None):
        super().__init__(name, description, tax_calculator, account_manager)
```

### 3. Implement applies() Method
```python
def applies(self, age_primary, age_spouse, year, has_wages, has_ss):
    # Port original logic from LifeStage.applies()
    # Add type hints and validation
    return boolean_result
```

### 4. Implement calculate_strategy() Method
```python
def calculate_strategy(self, year, balances, expenses, **kwargs):
    # Validate dependencies
    self._validate_dependencies()
    
    # Create base strategy
    strategy = self._create_yearly_strategy(year, age_primary, age_spouse, balances)
    
    # Port original calculations
    # Use helper methods from base class
    # Use injected tax_calculator and account_manager
    # Log decisions with self._log_decision()
    
    return strategy
```

### 5. Extract Helper Methods
```python
def _calculate_stage_specific_logic(self, ...):
    """Extract complex calculations into helper methods"""
    pass

def _determine_stage_withdrawals(self, ...):
    """Stage-specific withdrawal logic"""
    pass
```

### 6. Add Type Hints
```python
# Add comprehensive type hints to all methods
# Use proper return types
# Document parameters with docstrings
```

### 7. Update Tests
```python
# Create test class for each stage
# Test applies() method with various scenarios
# Test calculate_strategy() with mock dependencies
# Test helper methods in isolation
```

## Helper Method Examples

### Using Tax Calculator
```python
# Federal tax calculation
federal_tax, max_rate, upper_bracket = self.tax_calculator.calculate_federal_tax(
    taxable_income, filing_status, year
)

# State tax calculation
state_tax = self.tax_calculator.calculate_state_tax(agi, state, year)

# IRMAA calculation
irmaa_primary, irmaa_spouse = self.tax_calculator.calculate_irmaa_penalty(
    magi, filing_status, year
)
```

### Using Account Manager
```python
# Cash withdrawal
cash_withdrawn, cash_remaining = self.account_manager.withdraw_from_cash(
    amount, balances.cash
)

# Taxable withdrawal with LTCG tracking
taxable_withdrawn, ltcg, taxable_remaining = self.account_manager.withdraw_from_taxable(
    amount, brokerage_account, strategy.decisions
)

# Roth conversion
converted, new_trad, new_roth = self.account_manager.convert_traditional_to_roth(
    conversion_amount, balances.traditional, balances.roth
)
```

### Using Base Class Helpers
```python
# Calculate shortfall
shortfall = self._calculate_shortfall(expenses, income, taxes, healthcare)

# Determine withdrawal sequence
withdrawals = self._determine_withdrawal_sequence(shortfall, balances)

# Log decisions
self._log_decision(
    strategy, 'roth_conversion', 'Roth Conversion',
    f'Convert ${amount:,.0f}', 'BETR analysis favorable',
    amount=amount, betr=betr_value
)
```

## Testing Pattern

Each stage should have comprehensive tests:

```python
class TestStageXName:
    def test_applies_conditions(self):
        """Test various applies() scenarios"""
        pass
    
    def test_calculate_strategy_basic(self):
        """Test basic strategy calculation"""
        pass
    
    def test_calculate_strategy_with_mocks(self):
        """Test with mock dependencies"""
        pass
    
    def test_helper_methods(self):
        """Test stage-specific helper methods"""
        pass
```

## Migration Checklist

For each stage:

- [ ] Create stage file in `strategy_core/stages/`
- [ ] Implement class extending `BaseLifeStageStrategy`
- [ ] Port `applies()` logic with type hints
- [ ] Port `calculate_strategy()` logic using helpers
- [ ] Extract stage-specific helper methods
- [ ] Add comprehensive type hints
- [ ] Create unit tests
- [ ] Update `stages/__init__.py`
- [ ] Test integration with existing code

## Benefits of This Pattern

1. **Consistency**: All stages follow the same structure
2. **Testability**: Easy to mock dependencies
3. **Maintainability**: Clear separation of concerns
4. **Type Safety**: Comprehensive type hints
5. **Reusability**: Common logic in base class
6. **Extensibility**: Easy to add new stages

## Example: Stage 3 Early Retirement Skeleton

```python
class Stage3EarlyRetirement(BaseLifeStageStrategy):
    def __init__(self, tax_calculator=None, account_manager=None):
        super().__init__(
            name="Stage 3: Early Retirement",
            description="Pre-Medicare, pre-SS, BETR-optimized Roth conversions",
            tax_calculator=tax_calculator,
            account_manager=account_manager
        )
    
    def applies(self, age_primary, age_spouse, year, has_wages, has_ss):
        return not has_wages and not has_ss and age_primary < 65
    
    def calculate_strategy(self, year, balances, expenses, **kwargs):
        self._validate_dependencies()
        
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        
        strategy = self._create_yearly_strategy(year, age_primary, age_spouse, balances)
        
        # Calculate ACA subsidy optimization
        aca_costs = self._calculate_aca_optimization(strategy, **kwargs)
        
        # Calculate shortfall after ACA
        shortfall = self._calculate_shortfall(expenses, 0, 0, aca_costs)
        
        # Determine optimal withdrawals
        withdrawals = self._determine_withdrawal_sequence(shortfall, balances)
        
        # Apply withdrawals using account manager
        # ... implementation
        
        return strategy
    
    def _calculate_aca_optimization(self, strategy, **kwargs):
        """Calculate ACA subsidy optimization"""
        # Stage-specific ACA logic
        pass
```

This template provides a clear roadmap for refactoring all remaining stages while maintaining consistency and quality.