"""
Roth Conversion Optimizer

Optimizes Roth conversion amounts using priority-based strategy:
1. DAF (Donor Advised Fund) - maximize charitable contribution impact
2. RMD Lookback - reduce future Required Minimum Distribution burden  
3. BETR - Break-Even Tax Rate for pure wealth optimization

Each strategy is evaluated in order, and the best option is selected.
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConversionOptimization:
    """Result of Roth conversion optimization."""
    conversion_amount: float
    optimization_strategy: str  # 'daf', 'rmd_lookback', or 'betr'
    reasoning: str
    future_rmd_impact: float  # Estimated reduction in future RMD burden
    daf_potential: float  # Potential DAF contribution enabled by conversion


class RothConversionOptimizer:
    """
    Optimizes Roth conversion decision and amount using priority-based strategies.
    """

    def __init__(self):
        """Initialize the optimizer."""
        pass

    def optimize_conversion(
        self,
        available_bracket_space: float,
        traditional_balance: float,
        roth_balance: float,
        age_primary: int,
        age_spouse: int,
        year: int,
        has_daf: bool = False,
        daf_annual_contribution: float = 0.0,
        has_pension_or_other_ordinary_income: bool = False,
        life_expectancy_primary: int = 85,
        life_expectancy_spouse: int = 85,
        betr_max_rate: float = 0.24
    ) -> ConversionOptimization:
        """
        Optimize Roth conversion using priority strategy.

        Priority order:
        1. DAF Optimization - maximize charitable impact
        2. RMD Lookback - reduce future Traditional balance that triggers RMD
        3. BETR - maximize after-tax wealth

        Args:
            available_bracket_space: Remaining 12% bracket space after Part A
            traditional_balance: Current Traditional IRA/401k balance
            roth_balance: Current Roth balance
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            has_daf: Whether Donor Advised Fund is in use
            daf_annual_contribution: Annual DAF contribution amount
            has_pension_or_other_ordinary_income: Whether there's pension/rental/etc
            life_expectancy_primary: Projected life expectancy for primary
            life_expectancy_spouse: Projected life expectancy for spouse
            betr_max_rate: Maximum acceptable tax rate for BETR (default 24%)

        Returns:
            ConversionOptimization with recommended conversion amount and strategy
        """
        logger.info(
            f"Optimizing Roth conversion for year {year}\n"
            f"  Available Bracket Space: ${available_bracket_space:,.2f}\n"
            f"  Traditional Balance: ${traditional_balance:,.2f}\n"
            f"  Roth Balance: ${roth_balance:,.2f}\n"
            f"  Ages: {age_primary}/{age_spouse}\n"
            f"  Has DAF: {has_daf}\n"
            f"  DAF Annual Contribution: ${daf_annual_contribution:,.2f}"
        )

        # Strategy 1: DAF Optimization
        if has_daf and daf_annual_contribution > 0:
            daf_result = self._optimize_for_daf(
                available_bracket_space,
                traditional_balance,
                daf_annual_contribution,
                year
            )
            if daf_result is not None:
                logger.info(
                    f"DAF Optimization Selected: Convert ${daf_result.conversion_amount:,.2f}"
                )
                return daf_result

        # Strategy 2: RMD Lookback (only if approaching RMD age)
        if self._is_approaching_rmd_age(age_primary, age_spouse):
            rmd_result = self._optimize_for_rmd_reduction(
                available_bracket_space,
                traditional_balance,
                age_primary,
                age_spouse,
                life_expectancy_primary,
                life_expectancy_spouse,
                year
            )
            if rmd_result is not None:
                logger.info(
                    f"RMD Lookback Selected: Convert ${rmd_result.conversion_amount:,.2f}\n"
                    f"  Future RMD Reduction: ${rmd_result.future_rmd_impact:,.2f}"
                )
                return rmd_result

        # Strategy 3: BETR (Break-Even Tax Rate)
        betr_result = self._optimize_with_betr(
            available_bracket_space,
            traditional_balance,
            roth_balance,
            betr_max_rate,
            year
        )
        logger.info(
            f"BETR Strategy Selected: Convert ${betr_result.conversion_amount:,.2f}"
        )
        return betr_result

    def _optimize_for_daf(
        self,
        available_bracket_space: float,
        traditional_balance: float,
        daf_annual_contribution: float,
        year: int
    ) -> Optional[ConversionOptimization]:
        """
        Optimize for Donor Advised Fund impact.

        DAF strategy: Convert enough Traditional to:
        1. Fund DAF contribution (tax-efficient because DAF is deductible)
        2. Use remaining bracket space for additional Roth conversion

        Args:
            available_bracket_space: Remaining bracket space
            traditional_balance: Current Traditional balance
            daf_annual_contribution: Annual DAF contribution planned
            year: Current year

        Returns:
            ConversionOptimization if DAF strategy is viable, else None
        """
        # Conservative: DAF contribution should not exceed 20% of available bracket
        # (leave room for other optimization)
        daf_bracket_use = min(daf_annual_contribution, available_bracket_space * 0.5)

        if daf_bracket_use <= 0:
            return None

        # Use remaining bracket for Roth conversion (post-DAF)
        remaining_bracket = available_bracket_space - daf_bracket_use
        conversion_amount = min(remaining_bracket, traditional_balance)

        # Ensure we have enough Traditional balance
        if conversion_amount <= 0:
            return None

        reasoning = (
            f"DAF Optimization (Priority 1):\n"
            f"  DAF contribution uses ${daf_bracket_use:,.2f} of bracket\n"
            f"  Roth conversion uses remaining ${conversion_amount:,.2f}\n"
            f"  Tax-efficient: Charitable deduction + Roth growth"
        )

        return ConversionOptimization(
            conversion_amount=conversion_amount,
            optimization_strategy='daf',
            reasoning=reasoning,
            future_rmd_impact=conversion_amount,  # Full conversion reduces future RMD
            daf_potential=daf_bracket_use
        )

    def _is_approaching_rmd_age(self, age_primary: int, age_spouse: int) -> bool:
        """
        Check if primary person is approaching RMD age (73 in 2023+).

        RMD age: 73 (as of 2023 SECURE Act 2.0; may change with law)
        """
        RMD_AGE = 73
        years_to_rmd = RMD_AGE - age_primary

        # Consider "approaching" if within 10 years
        return 0 <= years_to_rmd <= 10

    def _optimize_for_rmd_reduction(
        self,
        available_bracket_space: float,
        traditional_balance: float,
        age_primary: int,
        age_spouse: int,
        life_expectancy_primary: int,
        life_expectancy_spouse: int,
        year: int
    ) -> Optional[ConversionOptimization]:
        """
        Optimize to reduce future Required Minimum Distribution burden.

        RMD strategy: Convert enough to materially reduce Traditional balance
        before RMD age is reached, reducing the tax burden in later years.

        Args:
            available_bracket_space: Remaining bracket space
            traditional_balance: Current Traditional balance
            age_primary: Primary person's age
            age_spouse: Spouse's age
            life_expectancy_primary: Primary's life expectancy
            life_expectancy_spouse: Spouse's life expectancy
            year: Current year

        Returns:
            ConversionOptimization if RMD strategy is viable, else None
        """
        if traditional_balance <= 0:
            return None

        # Conservative RMD reduction: convert up to 30% of bracket space
        # (leave room for later years)
        conversion_amount = min(
            traditional_balance,
            available_bracket_space * 0.6  # Use 60% of bracket for RMD optimization
        )

        if conversion_amount <= 0:
            return None

        # Estimate future RMD impact (simplified)
        # RMD is roughly 5-7% of Traditional balance at age 73
        rmd_age = 73
        years_to_rmd = max(1, rmd_age - age_primary)
        estimated_rmd_reduction_per_year = (conversion_amount / years_to_rmd) * 0.06

        reasoning = (
            f"RMD Lookback Optimization (Priority 2):\n"
            f"  Current Traditional: ${traditional_balance:,.2f}\n"
            f"  Conversion reduces Traditional by: ${conversion_amount:,.2f}\n"
            f"  Years to RMD: {years_to_rmd}\n"
            f"  Estimated RMD reduction: ${estimated_rmd_reduction_per_year:,.2f}/year\n"
            f"  Tax benefit: Avoid higher tax rates in RMD years"
        )

        return ConversionOptimization(
            conversion_amount=conversion_amount,
            optimization_strategy='rmd_lookback',
            reasoning=reasoning,
            future_rmd_impact=estimated_rmd_reduction_per_year * years_to_rmd,
            daf_potential=0.0
        )

    def _optimize_with_betr(
        self,
        available_bracket_space: float,
        traditional_balance: float,
        roth_balance: float,
        betr_max_rate: float,
        year: int
    ) -> ConversionOptimization:
        """
        Optimize using Break-Even Tax Rate (BETR) algorithm.

        BETR: Convert if the tax cost today (12%) is less than the
        marginal tax rate tomorrow (after RMD, social security, etc).

        Conservative BETR: Use full available bracket space up to max rate.

        Args:
            available_bracket_space: Remaining bracket space
            traditional_balance: Current Traditional balance
            roth_balance: Current Roth balance
            betr_max_rate: Maximum acceptable tax rate
            year: Current year

        Returns:
            ConversionOptimization with BETR strategy
        """
        # Simple BETR: convert full bracket space if we're in 12% bracket
        # (which we are by definition of "available bracket space")
        conversion_amount = min(available_bracket_space, traditional_balance)

        reasoning = (
            f"BETR Strategy (Priority 3 - Default):\n"
            f"  Current rate: 12% (within bracket space)\n"
            f"  Max acceptable rate: {betr_max_rate*100:.0f}%\n"
            f"  Conversion amount: ${conversion_amount:,.2f}\n"
            f"  Rationale: 12% tax today likely cheaper than future rates after RMD/SS"
        )

        return ConversionOptimization(
            conversion_amount=conversion_amount,
            optimization_strategy='betr',
            reasoning=reasoning,
            future_rmd_impact=conversion_amount * 0.5,  # Rough estimate
            daf_potential=0.0
        )
