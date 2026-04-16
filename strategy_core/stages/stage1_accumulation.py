"""
Stage 1: Accumulation Phase

Refactored implementation using BaseLifeStageStrategy with dependency injection.
"""

import logging
from typing import Any, Optional

from ..base_strategy import BaseLifeStageStrategy
from ..interfaces import ITaxCalculator, IAccountManager
from ..models import PortfolioBalances, YearlyStrategy

logger = logging.getLogger(__name__)


class Stage1Accumulation(BaseLifeStageStrategy):
    """
    Stage 1: Accumulation Phase
    
    - Employed with wages
    - Focus on tax-efficient contributions
    - Maximize 401k/IRA contributions
    - Consider Roth vs Traditional based on current tax bracket
    - Optional Roth conversions using BETR during low tax years
    """
    
    PREP_WINDOW_YEARS = 10  # Years before retirement to switch to Stage 2
    
    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """
        Initialize Stage 1 Accumulation strategy.
        
        Args:
            tax_calculator: Tax calculator for tax computations
            account_manager: Account manager for withdrawals/conversions
        """
        super().__init__(
            name="Stage 1: Accumulation",
            description="Employed, earning wages, building retirement assets tax-efficiently",
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
        Applies when employed with wages AND outside the Stage 2 prep window.
        
        Uses the *latest* retirement year so that Stage 1 remains active until
        the last earner in the household retires.
        
        Args:
            age_primary: Primary person's age
            age_spouse: Spouse's age
            year: Current year
            has_wages: Whether there is wage income
            has_ss: Whether Social Security has started
            
        Returns:
            True if this stage applies
        """
        if not has_wages:
            return False
        
        # Yield to Stage 2 when within the 10-year prep window of the LAST
        # person to retire (household is not in prep mode until the final
        # earner is within the window).
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()
            
            # Get retirement years for both people
            # Use None as default to detect if not configured
            retirement_year_primary = config_mgr.get("personal_info", "person1_retirement_year", None)
            retirement_year_spouse = config_mgr.get("personal_info", "person2_retirement_year", None)
            
            # If retirement years are not configured, stay in Stage 1
            if retirement_year_primary is None and retirement_year_spouse is None:
                return True
            
            # Use the latest retirement year (handle None values)
            latest_retirement_year = max(
                retirement_year_primary if retirement_year_primary is not None else year,
                retirement_year_spouse if retirement_year_spouse is not None else year
            )
            years_to_retirement = latest_retirement_year - year
            
            # If within the prep window (1-10 years), Stage 2 should handle this year
            if 0 < years_to_retirement <= self.PREP_WINDOW_YEARS:
                return False
                
        except Exception as e:
            logger.warning(
                f"Stage1.applies: config lookup failed ({e}), defaulting to Stage 1"
            )
        
        return True
    
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate accumulation strategy focusing on tax efficiency.
        
        During accumulation, consider Roth conversions using BETR algorithm
        to reduce future RMDs, especially if in lower tax brackets.
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            **kwargs: Additional parameters including:
                - wages: Annual wages/salary
                - age_primary: Primary person's age
                - age_spouse: Spouse's age
                - max_conversion_rate: Maximum tax rate for conversions
                
        Returns:
            YearlyStrategy with all calculations
        """
        # Validate dependencies
        self._validate_dependencies()
        
        # Extract parameters
        wages = kwargs.get('wages', 0.0)
        age_primary = kwargs.get('age_primary', 0)
        age_spouse = kwargs.get('age_spouse', 0)
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        filing_status = kwargs.get('filing_status', 'married_filing_jointly')
        
        logger.debug(
            f"Stage 1 calculation for year {year}, wages=${wages:,.2f}"
        )
        
        # Create base strategy object
        strategy = self._create_yearly_strategy(
            year, age_primary, age_spouse, balances
        )
        
        # Set wages
        strategy.wages = wages
        
        # Calculate contribution amounts from config rates
        contribution_rates = self._get_contribution_rates()
        contribution_401k = wages * contribution_rates['traditional']
        contribution_roth = wages * contribution_rates['roth']
        contribution_brokerage = wages * contribution_rates['brokerage']
        
        # Calculate AGI (wages minus pre-tax 401k contribution)
        agi_before_conversion = wages - contribution_401k
        
        # Calculate taxes
        std_deduction = self.tax_calculator.calculate_standard_deduction(
            filing_status, year, age_primary, age_spouse
        )
        
        taxable_income = max(0, agi_before_conversion - std_deduction)
        federal_tax, max_rate, upper_bracket = self.tax_calculator.calculate_federal_tax(
            taxable_income, filing_status, year
        )
        
        state_tax = self.tax_calculator.calculate_state_tax(
            agi_before_conversion, kwargs.get('state', 'PA'), year
        )
        
        # Deduct state tax from cash balance
        balances = PortfolioBalances(
            cash=balances.cash - state_tax,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth,
            daf=balances.daf
        )
        logger.info(f"Year {year}: Deducted state tax ${state_tax:,.2f} from cash")
        
        # Calculate FICA taxes on wages
        fica_tax = self._calculate_fica_tax(wages)
        
        # Log contribution decision
        self._log_decision(
            strategy,
            'contribution_decisions',
            'Contribution Type',
            f'Traditional 401k {contribution_rates["traditional"]:.0%} / '
            f'Roth {contribution_rates["roth"]:.0%} / '
            f'Brokerage {contribution_rates["brokerage"]:.0%}',
            'During accumulation, contributions are split per config rates. '
            'Pre-tax 401k reduces AGI now; Roth contributions grow tax-free.',
            trad_401k=contribution_401k,
            roth=contribution_roth,
            brokerage=contribution_brokerage,
            agi=agi_before_conversion,
            bracket=max_rate
        )
        
        # Consider Roth conversions during accumulation
        roth_conversion = 0.0
        if balances.traditional > 0 and max_rate <= max_conversion_rate:
            roth_conversion = self._calculate_accumulation_roth_conversion(
                strategy,
                balances,
                agi_before_conversion,
                std_deduction,
                max_rate,
                upper_bracket,
                max_conversion_rate,
                filing_status,
                year
            )
        
        # Update strategy with calculated values
        strategy.expenses = expenses  # Store expenses in strategy
        strategy.agi = agi_before_conversion + roth_conversion
        strategy.magi = strategy.agi
        strategy.taxable_income = taxable_income
        strategy.federal_tax = federal_tax
        strategy.state_tax = state_tax
        strategy.fica_tax = fica_tax
        strategy.roth_conversion = roth_conversion
        
        # Update balances after contributions and conversions
        strategy.traditional_balance = (
            balances.traditional + contribution_401k - roth_conversion
        )
        strategy.roth_balance = balances.roth + contribution_roth + roth_conversion
        strategy.taxable_balance = balances.taxable + contribution_brokerage
        strategy.cash_balance = balances.cash
        
        # Calculate take-home pay
        take_home = wages - contribution_401k - contribution_roth - contribution_brokerage
        take_home -= federal_tax + state_tax + fica_tax
        
        # Add to cash if take-home exceeds expenses
        if take_home > expenses:
            strategy.cash_balance += (take_home - expenses)
        
        logger.debug(
            f"Stage 1 complete: AGI=${strategy.agi:,.2f}, "
            f"Federal Tax=${federal_tax:,.2f}, "
            f"Roth Conversion=${roth_conversion:,.2f}"
        )
        
        return strategy
    
    def _get_contribution_rates(self) -> dict[str, float]:
        """
        Get contribution rates from config.
        
        Returns:
            Dict with 'traditional', 'roth', 'brokerage' rates (0-1)
        """
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()
            
            trad_pct = float(config_mgr.get("income", "contribution_401k_percent", 10.0)) / 100.0
            roth_pct = float(config_mgr.get("income", "contribution_roth_percent", 5.0)) / 100.0
            brok_pct = float(config_mgr.get("income", "contribution_brokerage_percent", 5.0)) / 100.0
        except Exception:
            trad_pct, roth_pct, brok_pct = 0.10, 0.05, 0.05
        
        # Clamp each rate to [0, 1] and ensure total ≤ 100%
        trad_pct = max(0.0, min(1.0, trad_pct))
        roth_pct = max(0.0, min(1.0, roth_pct))
        brok_pct = max(0.0, min(1.0, brok_pct))
        
        total_pct = trad_pct + roth_pct + brok_pct
        if total_pct > 1.0:
            scale = 1.0 / total_pct
            trad_pct *= scale
            roth_pct *= scale
            brok_pct *= scale
        
        return {
            'traditional': trad_pct,
            'roth': roth_pct,
            'brokerage': brok_pct
        }
    
    def _calculate_fica_tax(self, wages: float) -> float:
        """
        Calculate FICA (Social Security + Medicare) taxes.
        
        Args:
            wages: Annual wages
            
        Returns:
            FICA tax amount
        """
        try:
            from calculations import calculate_payroll_taxes
            return calculate_payroll_taxes(wages)
        except ImportError:
            # Simple approximation: 7.65% (employee portion)
            return wages * 0.0765
    
    def _calculate_accumulation_roth_conversion(
        self,
        strategy: YearlyStrategy,
        balances: PortfolioBalances,
        agi: float,
        std_deduction: float,
        max_rate: float,
        upper_bracket: float,
        max_conversion_rate: float,
        filing_status: str,
        year: int
    ) -> float:
        """
        Calculate optimal Roth conversion during accumulation using BETR.
        
        Args:
            strategy: YearlyStrategy to log decisions to
            balances: Current balances
            agi: AGI before conversion
            std_deduction: Standard deduction
            max_rate: Current marginal tax rate
            upper_bracket: Upper limit of current bracket
            max_conversion_rate: Maximum rate for conversions
            filing_status: Filing status
            year: Current year
            
        Returns:
            Optimal conversion amount
        """
        # Calculate conversion room in current bracket
        current_income = agi
        conversion_room = max(0, upper_bracket - current_income - std_deduction)
        
        if conversion_room < 10000:
            # Not enough room for meaningful conversion
            return 0.0
        
        # Propose conversion: lesser of room or 15% of traditional balance
        proposed_conversion = min(
            conversion_room,
            balances.traditional * 0.15
        )
        
        if proposed_conversion < 1000:
            # Too small to be meaningful
            return 0.0
        
        # Use BETR to validate conversion is beneficial
        try:
            from betr_roth_conversion import calculate_betr, BETRInputs
            
            betr_inputs = BETRInputs(
                current_marginal_rate=max_rate,
                expected_future_rate=max_conversion_rate,
                conversion_amount=proposed_conversion,
                traditional_ira_balance=balances.traditional,
                pay_from_taxable=True,
                taxable_account_balance=balances.taxable,
                years_to_withdrawal=30,
                growth_rate=0.07
            )
            
            betr_result = calculate_betr(betr_inputs)
            
            if betr_result.is_beneficial:
                self._log_decision(
                    strategy,
                    'roth_conversion',
                    'Accumulation Roth Conversion',
                    f'Convert ${proposed_conversion:,.0f}',
                    f'BETR analysis shows conversion beneficial. '
                    f'Current rate {max_rate:.1%}, expected future {max_conversion_rate:.1%}',
                    amount=proposed_conversion,
                    betr=betr_result.betr,
                    current_rate=max_rate,
                    future_rate=max_conversion_rate
                )
                return proposed_conversion
            else:
                logger.debug(
                    f"BETR analysis shows conversion not beneficial: "
                    f"BETR={betr_result.betr:.3f}"
                )
                return 0.0
                
        except ImportError:
            logger.warning("BETR module not available, skipping conversion analysis")
            return 0.0
        except Exception as e:
            logger.error(f"Error in BETR calculation: {e}")
            return 0.0

# Made with Bob
