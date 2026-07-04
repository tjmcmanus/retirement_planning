"""
withdrawal_strategy.py

Public facade for the retirement withdrawal strategy system.

Re-exports the key classes, functions, and types from the three underlying
modules so callers can import from a single, stable location:

    from withdrawal_strategy import (
        PortfolioBalances,
        YearlyStrategy,
        WithdrawalStrategyEngine,
        build_withdrawal_strategy_display,
        validate_withdrawal_scenario,
        create_multi_year_plan,
        ...
    )

Underlying modules:
  strategy.py                        – engine, stage classes, data models
  withdrawal_strategy_validation.py  – input validation & optimization warnings
  withdrawal_strategy_optimization.py – multi-year tax planning
"""

# --- Engine & data models (strategy.py) ---
from strategy import (
    PortfolioBalances,
    YearlyStrategy,
    DecisionLog,
    DecisionReason,
    ScenarioConfig,
    ScenarioType,
    WithdrawalStrategyEngine,
    build_withdrawal_strategy_display,
    build_accumulation_strategy_display,
    generate_strategy_summary,
    print_strategy_report,
    calculate_aca_subsidy,
    create_example_scenario,
)

# --- Validation (withdrawal_strategy_validation.py) ---
from withdrawal_strategy_validation import (
    ValidationSeverity,
    ValidationIssue,
    ValidationResult,
    OptimizationWarning,
    validate_withdrawal_scenario,
    validate_yearly_strategy,
    check_irmaa_cliff_proximity,
    check_aca_subsidy_optimization,
    check_roth_conversion_opportunity,
    analyze_strategy_optimizations,
)

# --- Multi-year optimization (withdrawal_strategy_optimization.py) ---
from withdrawal_strategy_optimization import (
    TaxProjection,
    ConversionOpportunity,
    IRMAAOptimization,
    ACAOptimization,
    MultiYearPlan,
    create_multi_year_plan,
    find_optimal_conversion_amount,
    optimize_irmaa_exposure,
    optimize_aca_subsidy,
)

__all__ = [
    # Engine & models
    "PortfolioBalances", "YearlyStrategy", "DecisionLog", "DecisionReason",
    "ScenarioConfig", "ScenarioType", "WithdrawalStrategyEngine",
    "build_withdrawal_strategy_display", "build_accumulation_strategy_display",
    "generate_strategy_summary", "print_strategy_report",
    "calculate_aca_subsidy", "create_example_scenario",
    # Validation
    "ValidationSeverity", "ValidationIssue", "ValidationResult",
    "OptimizationWarning", "validate_withdrawal_scenario", "validate_yearly_strategy",
    "check_irmaa_cliff_proximity", "check_aca_subsidy_optimization",
    "check_roth_conversion_opportunity", "analyze_strategy_optimizations",
    # Optimization
    "TaxProjection", "ConversionOpportunity", "IRMAAOptimization",
    "ACAOptimization", "MultiYearPlan", "create_multi_year_plan",
    "find_optimal_conversion_amount", "optimize_irmaa_exposure", "optimize_aca_subsidy",
]

# Made with Bob
