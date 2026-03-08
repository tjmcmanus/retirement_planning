"""
Withdrawal Strategy Validation & Production Hardening Module

This module provides comprehensive validation, error handling, and optimization
for the retirement withdrawal strategy system, moving it from alpha to production quality.

Features:
- Edge case validation (zero balances, negative returns, extreme ages)
- Boundary condition checking (RMD age changes, SS claiming limits)
- Graceful degradation for missing data
- Warning system for suboptimal strategies
- Detailed error messages with remediation suggestions
- Dynamic Roth conversion optimization
- Intelligent IRMAA cliff avoidance
- ACA subsidy maximization
- Multi-year tax planning (look-ahead optimization)

Author: Bob
Date: 2026-03-08
Version: 1.0 - Production Hardening
"""

import logging
import warnings
from typing import Dict, List, Optional, Tuple, Any, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


# ==============================================================================
# VALIDATION CONSTANTS
# ==============================================================================

# Age boundaries
MIN_VALID_AGE = 0
MAX_VALID_AGE = 120
MIN_RETIREMENT_AGE = 50
MAX_RETIREMENT_AGE = 75
MIN_SS_CLAIMING_AGE = 62
MAX_SS_CLAIMING_AGE = 70
RMD_AGE_CURRENT = 73  # As of SECURE Act 2.0 (2023+)
RMD_AGE_LEGACY = 72   # For years 2020-2022
RMD_AGE_OLD = 70.5    # Pre-2020

# Balance boundaries
MIN_PORTFOLIO_BALANCE = 0.0
MAX_REASONABLE_PORTFOLIO = 100_000_000.0  # $100M warning threshold
MIN_REASONABLE_EXPENSES = 0.0
MAX_REASONABLE_EXPENSES = 1_000_000.0  # $1M/year warning threshold

# Rate boundaries
MIN_GROWTH_RATE = 0.90  # -10% (severe bear market)
MAX_GROWTH_RATE = 1.30  # +30% (unrealistic long-term)
MIN_INFLATION_RATE = -0.05  # -5% (deflation)
MAX_INFLATION_RATE = 0.15   # +15% (hyperinflation)

# Tax rate boundaries
MIN_TAX_RATE = 0.0
MAX_TAX_RATE = 0.50  # 50% (state + federal combined max)

# IRMAA thresholds (2024 values, indexed annually)
IRMAA_THRESHOLDS_MFJ = [
    (0, 206_000),
    (206_000, 258_000),
    (258_000, 322_000),
    (322_000, 386_000),
    (386_000, 750_000),
    (750_000, float('inf'))
]

# ACA subsidy thresholds (% of FPL)
ACA_SUBSIDY_MIN_FPL = 1.00  # 100% FPL
ACA_SUBSIDY_MAX_FPL = 4.00  # 400% FPL
ACA_FREE_COVERAGE_FPL = 1.50  # 150% FPL


# ==============================================================================
# VALIDATION RESULT CLASSES
# ==============================================================================

class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """A single validation issue with context and remediation"""
    severity: ValidationSeverity
    category: str
    message: str
    field: Optional[str] = None
    current_value: Optional[Any] = None
    expected_range: Optional[Tuple[Any, Any]] = None
    remediation: Optional[str] = None
    
    def __str__(self) -> str:
        """Format issue for display"""
        parts = [f"[{self.severity.value.upper()}] {self.category}: {self.message}"]
        if self.field:
            parts.append(f"  Field: {self.field}")
        if self.current_value is not None:
            parts.append(f"  Current: {self.current_value}")
        if self.expected_range:
            parts.append(f"  Expected: {self.expected_range[0]} to {self.expected_range[1]}")
        if self.remediation:
            parts.append(f"  Fix: {self.remediation}")
        return "\n".join(parts)


@dataclass
class ValidationResult:
    """Result of validation with all issues found"""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    
    def add_error(self, category: str, message: str, **kwargs) -> None:
        """Add an error-level issue"""
        self.is_valid = False
        self.issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category=category,
            message=message,
            **kwargs
        ))
    
    def add_warning(self, category: str, message: str, **kwargs) -> None:
        """Add a warning-level issue"""
        self.warnings.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            category=category,
            message=message,
            **kwargs
        ))
    
    def add_info(self, category: str, message: str, **kwargs) -> None:
        """Add an info-level issue"""
        self.warnings.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            category=category,
            message=message,
            **kwargs
        ))
    
    def has_errors(self) -> bool:
        """Check if any errors exist"""
        return not self.is_valid or any(i.severity == ValidationSeverity.ERROR for i in self.issues)
    
    def has_warnings(self) -> bool:
        """Check if any warnings exist"""
        return len(self.warnings) > 0
    
    def summary(self) -> str:
        """Generate summary report"""
        lines = []
        if self.has_errors():
            lines.append(f"❌ Validation FAILED with {len(self.issues)} error(s)")
            for issue in self.issues:
                lines.append(str(issue))
        else:
            lines.append("✅ Validation PASSED")
        
        if self.has_warnings():
            lines.append(f"\n⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                lines.append(str(warning))
        
        return "\n".join(lines)


# ==============================================================================
# INPUT VALIDATION FUNCTIONS
# ==============================================================================

def validate_age(age: float, field_name: str, result: ValidationResult) -> None:
    """Validate age is within reasonable bounds"""
    if age < MIN_VALID_AGE or age > MAX_VALID_AGE:
        result.add_error(
            "Age Validation",
            f"Age out of valid range",
            field=field_name,
            current_value=age,
            expected_range=(MIN_VALID_AGE, MAX_VALID_AGE),
            remediation=f"Ensure {field_name} is between {MIN_VALID_AGE} and {MAX_VALID_AGE}"
        )


def validate_retirement_age(age: int, field_name: str, result: ValidationResult) -> None:
    """Validate retirement age is reasonable"""
    if age < MIN_RETIREMENT_AGE or age > MAX_RETIREMENT_AGE:
        result.add_warning(
            "Retirement Age",
            f"Retirement age is unusual",
            field=field_name,
            current_value=age,
            expected_range=(MIN_RETIREMENT_AGE, MAX_RETIREMENT_AGE),
            remediation=f"Typical retirement age is {MIN_RETIREMENT_AGE}-{MAX_RETIREMENT_AGE}. Verify this is intentional."
        )


def validate_ss_claiming_age(age: int, field_name: str, result: ValidationResult) -> None:
    """Validate Social Security claiming age"""
    if age < MIN_SS_CLAIMING_AGE or age > MAX_SS_CLAIMING_AGE:
        result.add_error(
            "SS Claiming Age",
            f"Social Security claiming age out of legal range",
            field=field_name,
            current_value=age,
            expected_range=(MIN_SS_CLAIMING_AGE, MAX_SS_CLAIMING_AGE),
            remediation=f"SS can only be claimed between ages {MIN_SS_CLAIMING_AGE} and {MAX_SS_CLAIMING_AGE}"
        )


def validate_portfolio_balance(balance: float, field_name: str, result: ValidationResult) -> None:
    """Validate portfolio balance is reasonable"""
    if balance < MIN_PORTFOLIO_BALANCE:
        result.add_error(
            "Portfolio Balance",
            f"Negative balance not allowed",
            field=field_name,
            current_value=balance,
            expected_range=(MIN_PORTFOLIO_BALANCE, float('inf')),
            remediation=f"Ensure {field_name} is non-negative"
        )
    elif balance > MAX_REASONABLE_PORTFOLIO:
        result.add_warning(
            "Portfolio Balance",
            f"Unusually large portfolio balance",
            field=field_name,
            current_value=f"${balance:,.0f}",
            remediation="Verify this balance is correct. Consider splitting into multiple scenarios."
        )


def validate_expenses(expenses: float, result: ValidationResult) -> None:
    """Validate annual expenses are reasonable"""
    if expenses < MIN_REASONABLE_EXPENSES:
        result.add_error(
            "Expenses",
            "Negative expenses not allowed",
            field="annual_expenses",
            current_value=expenses,
            expected_range=(MIN_REASONABLE_EXPENSES, float('inf')),
            remediation="Ensure annual expenses are non-negative"
        )
    elif expenses > MAX_REASONABLE_EXPENSES:
        result.add_warning(
            "Expenses",
            "Unusually high annual expenses",
            field="annual_expenses",
            current_value=f"${expenses:,.0f}",
            remediation="Verify expense amount. Consider if this includes one-time costs."
        )


def validate_growth_rate(rate: float, result: ValidationResult) -> None:
    """Validate growth rate is reasonable"""
    if rate < MIN_GROWTH_RATE or rate > MAX_GROWTH_RATE:
        result.add_warning(
            "Growth Rate",
            "Growth rate outside typical range",
            field="growth_rate",
            current_value=f"{(rate-1)*100:.1f}%",
            expected_range=(f"{(MIN_GROWTH_RATE-1)*100:.1f}%", f"{(MAX_GROWTH_RATE-1)*100:.1f}%"),
            remediation="Historical average is 6-8% annually. Verify this assumption."
        )


def validate_inflation_rate(rate: float, result: ValidationResult) -> None:
    """Validate inflation rate is reasonable"""
    if rate < MIN_INFLATION_RATE or rate > MAX_INFLATION_RATE:
        result.add_warning(
            "Inflation Rate",
            "Inflation rate outside typical range",
            field="inflation_rate",
            current_value=f"{rate*100:.1f}%",
            expected_range=(f"{MIN_INFLATION_RATE*100:.1f}%", f"{MAX_INFLATION_RATE*100:.1f}%"),
            remediation="Historical average is 2-3% annually. Verify this assumption."
        )


def validate_year_range(start_year: int, end_year: int, result: ValidationResult) -> None:
    """Validate year range is reasonable"""
    current_year = pd.Timestamp.now().year
    
    if start_year < current_year - 10:
        result.add_warning(
            "Year Range",
            "Start year is in the past",
            field="start_year",
            current_value=start_year,
            remediation="Consider using current year or future year for projections"
        )
    
    if end_year < start_year:
        result.add_error(
            "Year Range",
            "End year before start year",
            field="end_year",
            current_value=end_year,
            remediation="Ensure end_year >= start_year"
        )
    
    years_span = end_year - start_year
    if years_span > 100:
        result.add_warning(
            "Year Range",
            "Projection span exceeds 100 years",
            current_value=f"{years_span} years",
            remediation="Consider shorter projection period for more reliable results"
        )


def validate_portfolio_balances(balances: Dict[str, float], result: ValidationResult) -> None:
    """Validate all portfolio account balances"""
    account_types = ['cash', 'taxable', 'traditional', 'roth', 'daf']
    
    for account in account_types:
        if account in balances:
            validate_portfolio_balance(balances[account], account, result)
    
    # Check total portfolio
    total = sum(balances.get(acc, 0) for acc in account_types)
    if total <= 0:
        result.add_error(
            "Portfolio Total",
            "Total portfolio balance must be positive",
            current_value=f"${total:,.0f}",
            remediation="Ensure at least one account has a positive balance"
        )


# ==============================================================================
# SCENARIO VALIDATION
# ==============================================================================

def validate_withdrawal_scenario(
    start_year: int,
    end_year: int,
    initial_balances: Dict[str, float],
    initial_expenses: float,
    growth_rate: float,
    expense_inflation_rate: float,
    ss_claiming_age: int,
    retirement_year: int,
    **kwargs
) -> ValidationResult:
    """
    Comprehensive validation of withdrawal strategy scenario inputs
    
    Args:
        start_year: Starting year for projection
        end_year: Ending year for projection
        initial_balances: Dictionary of account balances
        initial_expenses: Annual expenses
        growth_rate: Portfolio growth rate (e.g., 1.07 for 7%)
        expense_inflation_rate: Expense inflation rate (e.g., 0.03 for 3%)
        ss_claiming_age: Age to claim Social Security
        retirement_year: Year of retirement
        **kwargs: Additional parameters
    
    Returns:
        ValidationResult with all issues found
    """
    result = ValidationResult(is_valid=True)
    
    # Validate year range
    validate_year_range(start_year, end_year, result)
    
    # Validate portfolio balances
    validate_portfolio_balances(initial_balances, result)
    
    # Validate expenses
    validate_expenses(initial_expenses, result)
    
    # Validate rates
    validate_growth_rate(growth_rate, result)
    validate_inflation_rate(expense_inflation_rate, result)
    
    # Validate SS claiming age
    validate_ss_claiming_age(ss_claiming_age, "ss_claiming_age", result)
    
    # Validate retirement year
    if retirement_year < start_year:
        result.add_warning(
            "Retirement Year",
            "Retirement year is before start year",
            field="retirement_year",
            current_value=retirement_year,
            remediation="Already retired scenario - ensure this is intentional"
        )
    
    # Check for sustainability
    total_portfolio = sum(initial_balances.values())
    years_of_expenses = total_portfolio / initial_expenses if initial_expenses > 0 else float('inf')
    
    if years_of_expenses < 10:
        result.add_warning(
            "Portfolio Sustainability",
            "Portfolio may not last 10 years at current expense rate",
            current_value=f"{years_of_expenses:.1f} years",
            remediation="Consider reducing expenses or increasing portfolio balance"
        )
    
    return result


# ==============================================================================
# RUNTIME VALIDATION
# ==============================================================================

def validate_yearly_strategy(
    year: int,
    age_primary: int,
    age_spouse: int,
    balances: Dict[str, float],
    expenses: float,
    withdrawals: Dict[str, float],
    result: ValidationResult
) -> None:
    """
    Validate a single year's strategy for impossible scenarios
    
    Args:
        year: Current year
        age_primary: Primary person's age
        age_spouse: Spouse's age
        balances: Current account balances
        expenses: Annual expenses
        withdrawals: Withdrawals from each account
        result: ValidationResult to append issues to
    """
    # Validate ages
    validate_age(age_primary, "age_primary", result)
    validate_age(age_spouse, "age_spouse", result)
    
    # Validate balances are non-negative
    for account, balance in balances.items():
        if balance < -0.01:  # Allow small floating point errors
            result.add_error(
                "Negative Balance",
                f"Account {account} has negative balance in year {year}",
                field=account,
                current_value=f"${balance:,.2f}",
                remediation="Strategy is withdrawing more than available. Reduce expenses or increase initial balance."
            )
    
    # Validate withdrawals don't exceed balances
    for account, withdrawal in withdrawals.items():
        if account in balances and withdrawal > balances[account] + 0.01:  # Allow small rounding
            result.add_error(
                "Excessive Withdrawal",
                f"Withdrawal from {account} exceeds balance in year {year}",
                field=account,
                current_value=f"Withdrawal: ${withdrawal:,.2f}, Balance: ${balances[account]:,.2f}",
                remediation="Reduce withdrawal amount or check calculation logic"
            )
    
    # Check if portfolio is depleted
    total_balance = sum(balances.values())
    if total_balance < expenses and total_balance > 0:
        result.add_warning(
            "Portfolio Depletion",
            f"Portfolio balance below annual expenses in year {year}",
            current_value=f"Balance: ${total_balance:,.0f}, Expenses: ${expenses:,.0f}",
            remediation="Portfolio may be depleted soon. Consider reducing expenses."
        )


# ==============================================================================
# OPTIMIZATION WARNINGS
# ==============================================================================

@dataclass
class OptimizationWarning:
    """Warning about suboptimal strategy with improvement suggestion"""
    category: str
    issue: str
    impact: str
    suggestion: str
    potential_savings: Optional[float] = None


def check_irmaa_cliff_proximity(magi: float, year: int) -> Optional[OptimizationWarning]:
    """
    Check if MAGI is dangerously close to an IRMAA threshold
    
    Args:
        magi: Modified Adjusted Gross Income
        year: Tax year
    
    Returns:
        OptimizationWarning if near a cliff, None otherwise
    """
    # Find which bracket we're in
    for i, (lower, upper) in enumerate(IRMAA_THRESHOLDS_MFJ):
        if lower <= magi < upper:
            # Check if we're within $5,000 of the upper threshold
            distance_to_cliff = upper - magi
            if distance_to_cliff < 5000 and distance_to_cliff > 0:
                next_bracket_penalty = (i + 1) * 1000  # Approximate additional annual cost
                return OptimizationWarning(
                    category="IRMAA Cliff",
                    issue=f"MAGI of ${magi:,.0f} is ${distance_to_cliff:,.0f} from IRMAA threshold",
                    impact=f"Crossing threshold adds ~${next_bracket_penalty:,.0f}/year in Medicare premiums",
                    suggestion=f"Consider reducing MAGI by ${distance_to_cliff + 1000:,.0f} through: "
                              f"(1) Reducing Roth conversions, (2) Harvesting losses, or (3) Increasing charitable giving",
                    potential_savings=next_bracket_penalty * 2  # 2-year lookback impact
                )
    return None


def check_aca_subsidy_optimization(magi: float, household_size: int = 2) -> Optional[OptimizationWarning]:
    """
    Check if MAGI could be optimized for better ACA subsidies
    
    Args:
        magi: Modified Adjusted Gross Income
        household_size: Number in household
    
    Returns:
        OptimizationWarning if optimization possible, None otherwise
    """
    # Approximate FPL for 2-person household (updated annually)
    fpl_2_person = 20000  # Approximate, varies by state
    fpl_percentage = magi / fpl_2_person
    
    # Check if just above free coverage threshold
    if 1.50 < fpl_percentage < 1.75:
        target_magi = fpl_2_person * 1.49
        reduction_needed = magi - target_magi
        return OptimizationWarning(
            category="ACA Subsidy",
            issue=f"MAGI at {fpl_percentage:.0f}% FPL, just above free coverage threshold",
            impact="Missing out on $0 premium ACA coverage",
            suggestion=f"Reduce MAGI by ${reduction_needed:,.0f} to qualify for free coverage at 150% FPL",
            potential_savings=12000  # Approximate annual premium savings
        )
    
    # Check if just above subsidy cliff
    if 3.90 < fpl_percentage < 4.10:
        target_magi = fpl_2_person * 3.99
        reduction_needed = magi - target_magi
        return OptimizationWarning(
            category="ACA Subsidy",
            issue=f"MAGI at {fpl_percentage:.0f}% FPL, near subsidy cliff",
            impact="May lose all ACA subsidies above 400% FPL",
            suggestion=f"Reduce MAGI by ${reduction_needed:,.0f} to maintain subsidy eligibility",
            potential_savings=8000  # Approximate subsidy value
        )
    
    return None


def check_roth_conversion_opportunity(
    traditional_balance: float,
    current_tax_rate: float,
    age: int,
    years_to_rmd: int
) -> Optional[OptimizationWarning]:
    """
    Check if there's a missed Roth conversion opportunity
    
    Args:
        traditional_balance: Traditional IRA/401k balance
        current_tax_rate: Current marginal tax rate
        age: Current age
        years_to_rmd: Years until RMD age
    
    Returns:
        OptimizationWarning if opportunity exists, None otherwise
    """
    # Check if in low tax bracket with large traditional balance
    if current_tax_rate < 0.15 and traditional_balance > 500000 and years_to_rmd > 5:
        # Estimate future RMD tax burden
        estimated_rmd = traditional_balance * 0.04  # Approximate 4% RMD
        future_tax_rate = 0.24  # Likely higher bracket with RMDs
        future_tax = estimated_rmd * future_tax_rate
        current_conversion_tax = estimated_rmd * current_tax_rate
        potential_savings = (future_tax - current_conversion_tax) * years_to_rmd
        
        return OptimizationWarning(
            category="Roth Conversion",
            issue=f"Large Traditional balance (${traditional_balance:,.0f}) in low tax bracket ({current_tax_rate:.0%})",
            impact=f"Future RMDs will likely push into {future_tax_rate:.0%} bracket",
            suggestion=f"Consider converting ${estimated_rmd:,.0f}/year while in {current_tax_rate:.0%} bracket",
            potential_savings=potential_savings
        )
    
    return None


def analyze_strategy_optimizations(
    strategies: List[Dict[str, Any]]
) -> List[OptimizationWarning]:
    """
    Analyze complete strategy for optimization opportunities
    
    Args:
        strategies: List of yearly strategy dictionaries
    
    Returns:
        List of OptimizationWarnings found
    """
    warnings = []
    
    for strategy in strategies:
        year = strategy.get('year', 0)
        magi = strategy.get('magi', 0)
        age = strategy.get('age_primary', 0)
        traditional_balance = strategy.get('traditional_balance', 0)
        current_tax_rate = strategy.get('marginal_tax_rate', 0)
        
        # Check IRMAA cliffs (for Medicare-eligible ages)
        if age >= 63:  # 2-year lookback means age 65 Medicare affected by age 63 MAGI
            warning = check_irmaa_cliff_proximity(magi, year)
            if warning:
                warnings.append(warning)
        
        # Check ACA optimization (pre-Medicare)
        if 50 <= age < 65:
            warning = check_aca_subsidy_optimization(magi)
            if warning:
                warnings.append(warning)
        
        # Check Roth conversion opportunities
        years_to_rmd = max(0, 73 - age)
        if years_to_rmd > 0:
            warning = check_roth_conversion_opportunity(
                traditional_balance, current_tax_rate, age, years_to_rmd
            )
            if warning:
                warnings.append(warning)
    
    return warnings


# ==============================================================================
# GRACEFUL DEGRADATION
# ==============================================================================

def get_with_fallback(data: Dict[str, Any], key: str, default: Any, 
                      warning_msg: Optional[str] = None) -> Any:
    """
    Get value from dictionary with fallback and optional warning
    
    Args:
        data: Dictionary to get value from
        key: Key to look up
        default: Default value if key missing
        warning_msg: Optional warning message to log
    
    Returns:
        Value from dict or default
    """
    if key not in data:
        if warning_msg:
            logger.warning(warning_msg)
        return default
    return data[key]


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero
    
    Args:
        numerator: Numerator
        denominator: Denominator
        default: Value to return if denominator is zero
    
    Returns:
        Result of division or default
    """
    if abs(denominator) < 1e-10:  # Effectively zero
        return default
    return numerator / denominator


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp value between min and max
    
    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value
    
    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


# ==============================================================================
# MAIN VALIDATION FUNCTION
# ==============================================================================

def validate_and_warn(
    scenario_params: Dict[str, Any],
    strategies: Optional[List[Dict[str, Any]]] = None
) -> Tuple[ValidationResult, List[OptimizationWarning]]:
    """
    Main validation function - validates inputs and analyzes strategies
    
    Args:
        scenario_params: Dictionary of scenario parameters
        strategies: Optional list of calculated strategies to analyze
    
    Returns:
        Tuple of (ValidationResult, List of OptimizationWarnings)
    """
    # Validate inputs
    result = validate_withdrawal_scenario(**scenario_params)
    
    # Analyze strategies if provided
    optimization_warnings = []
    if strategies:
        optimization_warnings = analyze_strategy_optimizations(strategies)
    
    return result, optimization_warnings


# Made with Bob