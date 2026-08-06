"""
Tax Calculator Implementation

Provides concrete implementation of tax calculations with dependency
injection support for testability.
"""

import logging
from typing import Tuple, Dict, Any, Optional

from .interfaces import ITaxCalculator

logger = logging.getLogger(__name__)


class TaxCalculator(ITaxCalculator):
    """
    Concrete implementation of tax calculations.
    
    Supports dependency injection of tax data sources for testing.
    
    Attributes:
        tax_data_provider: Optional provider for tax bracket data
    """
    
    def __init__(self, tax_data_provider: Optional[Any] = None):
        """
        Initialize tax calculator.
        
        Args:
            tax_data_provider: Optional provider for tax data (defaults to load_data module)
        """
        self.tax_data_provider = tax_data_provider
        
        # Import default data provider if none specified
        if self.tax_data_provider is None:
            try:
                from load_data import (
                    get_income_tax_brackets,
                    get_cap_gains_brackets,
                    get_std_deduction
                )
                from calculations import (
                    calculate_taxable_income,
                    calculate_cap_gains,
                )
                
                self._get_income_tax_brackets_raw = get_income_tax_brackets
                self._get_cap_gains_brackets = get_cap_gains_brackets
                self._get_std_deduction = get_std_deduction
                self._calculate_taxable_income = calculate_taxable_income
                self._calculate_cap_gains = calculate_cap_gains
                
            except ImportError as e:
                logger.warning(f"Could not import tax data functions: {e}")
                raise
    
    def _get_income_tax_brackets(self, filing_status: str, year: int):
        """
        Get income tax brackets for the given filing status and year.

        Delegates directly to the raw function, which already filters by both
        year and filing_status, so no manual post-filter is needed.
        """
        brackets_df = self._get_income_tax_brackets_raw(year, filing_status)
        return [row.to_dict() for _, row in brackets_df.iterrows()]
    
    def calculate_federal_tax(
        self,
        taxable_income: float,
        filing_status: str,
        year: int
    ) -> Tuple[float, float, float]:
        """
        Calculate federal income tax using progressive brackets.
        
        Args:
            taxable_income: Income subject to tax
            filing_status: 'single', 'married', 'married_separate'
            year: Tax year
            
        Returns:
            Tuple of (total_tax, max_rate, upper_bracket_limit)
        """
        if taxable_income <= 0:
            return 0.0, 0.0, 0.0
        
        try:
            brackets = self._get_income_tax_brackets(filing_status, year)
        except Exception as e:
            logger.error(f"Error getting tax brackets: {e}")
            raise
        
        total_tax = 0.0
        remaining_income = taxable_income
        max_rate = 0.0
        upper_bracket_limit = 0.0
        
        for i, bracket in enumerate(brackets):
            lower = bracket.get('lower', 0.0)
            upper = bracket.get('upper', float('inf'))
            rate = bracket.get('rate', 0.0)
            
            if remaining_income <= 0:
                break
            
            # Calculate taxable amount in this bracket
            bracket_width = upper - lower
            taxable_in_bracket = min(remaining_income, bracket_width)
            
            # Calculate tax for this bracket
            tax_in_bracket = taxable_in_bracket * rate
            total_tax += tax_in_bracket
            
            # Update tracking variables
            remaining_income -= taxable_in_bracket
            max_rate = rate
            upper_bracket_limit = float(upper)
            
            logger.debug(
                f"Bracket {i}: ${lower:,.0f}-${upper:,.0f} @ {rate:.1%}, "
                f"taxable=${taxable_in_bracket:,.2f}, tax=${tax_in_bracket:,.2f}"
            )
        
        logger.debug(
            f"Federal tax: income=${taxable_income:,.2f}, "
            f"tax=${total_tax:,.2f}, max_rate={max_rate:.1%}"
        )
        
        return total_tax, max_rate, upper_bracket_limit
    
    def calculate_capital_gains_tax(
        self,
        ltcg: float,
        ordinary_income: float,
        filing_status: str,
        year: int
    ) -> float:
        """
        Calculate long-term capital gains tax with income stacking.
        
        Args:
            ltcg: Long-term capital gains amount
            ordinary_income: Ordinary income (for stacking)
            filing_status: Filing status
            year: Tax year
            
        Returns:
            Capital gains tax owed
        """
        if ltcg <= 0:
            return 0.0
        
        try:
            brackets = self._get_cap_gains_brackets(year, filing_status)
        except Exception as e:
            logger.error(f"Error getting capital gains brackets: {e}")
            raise
        
        # Stack capital gains on top of ordinary income
        stacked_income = ordinary_income
        total_tax = 0.0
        remaining_gains = ltcg
        
        # Iterate over DataFrame rows properly
        for _, bracket in brackets.iterrows():
            lower = float(bracket.get('lower', 0.0))
            upper = float(bracket.get('upper', float('inf')))
            rate = float(bracket.get('rate', 0.0))
            
            if remaining_gains <= 0:
                break
            
            # Determine how much of this bracket is available
            if stacked_income >= upper:
                # Already above this bracket
                continue
            
            # Calculate gains taxed in this bracket
            available_in_bracket = upper - max(stacked_income, lower)
            gains_in_bracket = min(remaining_gains, available_in_bracket)
            
            # Calculate tax
            tax_in_bracket = gains_in_bracket * rate
            total_tax += tax_in_bracket
            
            # Update tracking
            stacked_income += gains_in_bracket
            remaining_gains -= gains_in_bracket
            
            logger.debug(
                f"LTCG bracket: ${lower:,.0f}-${upper:,.0f} @ {rate:.1%}, "
                f"gains=${gains_in_bracket:,.2f}, tax=${tax_in_bracket:,.2f}"
            )
        
        logger.debug(
            f"Capital gains tax: ltcg=${ltcg:,.2f}, "
            f"ordinary=${ordinary_income:,.2f}, tax=${total_tax:,.2f}"
        )
        
        return total_tax
    
    def calculate_state_tax(
        self,
        agi: float,
        state: str,
        year: int,
        filing_status: str = "married_filing_jointly",
        retirement_income: float = 0.0,
        ss_benefits: float = 0.0,
        roth_conversion: float = 0.0
    ) -> float:
        """
        Calculate state income tax with retirement exemptions.
        
        Args:
            agi: Adjusted Gross Income
            state: State code (e.g., 'CA', 'NY', 'PA')
            year: Tax year
            filing_status: Filing status for tax calculation
            retirement_income: Traditional IRA/401k distributions for exemption
            ss_benefits: Social Security benefits (full amount)
            roth_conversion: Roth conversion amount
            
        Returns:
            State tax owed
        """
        if agi <= 0:
            return 0.0
        
        # Import state tax calculation
        try:
            from strategy import calculate_state_tax as calc_state_tax
            tax, _ = calc_state_tax(
                state_agi=agi,
                state=state,
                year=year,
                filing_status=filing_status,
                retirement_income=retirement_income,
                ss_benefits=ss_benefits,
                roth_conversion=roth_conversion
            )
            return tax
        except ImportError as e:
            logger.warning(f"State tax calculation not available: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating state tax: {e}")
            return 0.0
    
    def calculate_irmaa_penalty(
        self,
        magi: float,
        filing_status: str,
        year: int
    ) -> Tuple[float, float]:
        """
        Calculate IRMAA (Medicare surcharge) penalty.
        
        Uses 2-year lookback for MAGI.
        
        Args:
            magi: Modified Adjusted Gross Income (from 2 years prior)
            filing_status: Filing status
            year: Year for IRMAA calculation
            
        Returns:
            Tuple of (irmaa_penalty_primary, irmaa_penalty_spouse)
        """
        if magi <= 0:
            return 0.0, 0.0
        
        try:
            return self._simple_irmaa_calculation(magi, filing_status, year)
            
        except Exception as e:
            logger.error(f"Error calculating IRMAA: {e}")
            return 0.0, 0.0
    
    def _simple_irmaa_calculation(
        self,
        magi: float,
        filing_status: str,
        year: int
    ) -> Tuple[float, float]:
        """
        Simple IRMAA calculation fallback.
        
        Uses approximate 2024 thresholds (should be replaced with actual data).
        """
        # 2024 IRMAA thresholds (approximate)
        if filing_status in ('married', 'married_filing_jointly'):
            thresholds = [
                (206000, 0),
                (258000, 69.90 * 12),
                (322000, 174.70 * 12),
                (386000, 279.50 * 12),
                (750000, 384.30 * 12),
                (float('inf'), 419.30 * 12)
            ]
        else:  # single
            thresholds = [
                (103000, 0),
                (129000, 69.90 * 12),
                (161000, 174.70 * 12),
                (193000, 279.50 * 12),
                (500000, 384.30 * 12),
                (float('inf'), 419.30 * 12)
            ]
        
        penalty = 0.0
        for threshold, amount in thresholds:
            if magi <= threshold:
                penalty = amount
                break
        
        # For married filing jointly, split between spouses
        if filing_status in ('married', 'married_filing_jointly'):
            return penalty / 2, penalty / 2
        else:
            return penalty, 0.0
    
    def calculate_standard_deduction(
        self,
        filing_status: str,
        year: int,
        age_primary: int = 0,
        age_spouse: int = 0
    ) -> float:
        """
        Calculate standard deduction with age adjustments.
        
        Args:
            filing_status: Filing status
            year: Tax year
            age_primary: Primary person's age
            age_spouse: Spouse's age
            
        Returns:
            Standard deduction amount
        """
        # Normalize 'married' → 'married_filing_jointly' to match CSV data
        _fs = 'married_filing_jointly' if filing_status == 'married' else filing_status
        try:
            deduction_df = self._get_std_deduction(year, _fs)
            # Extract the numeric value from the DataFrame
            if hasattr(deduction_df, 'empty') and not deduction_df.empty and 'deduction' in deduction_df.columns:
                base_deduction = float(deduction_df['deduction'].iloc[0])
            else:
                raise ValueError("No deduction value found in DataFrame")
        except Exception as e:
            logger.error(f"Error getting standard deduction for year {year}, filing_status {filing_status}: {e}")
            # Fallback to 2024 values
            base_deduction = float({
                'single': 14600,
                'married': 29200,
                'married_separate': 14600
            }.get(filing_status, 14600))
        
        # Add additional deduction for age 65+
        additional = 0.0
        _is_married = filing_status in ('married', 'married_filing_jointly')
        if age_primary >= 65:
            additional += 1950 if _is_married else 1850
        if age_spouse >= 65 and _is_married:
            additional += 1950
        
        return base_deduction + additional

# Made with Bob
