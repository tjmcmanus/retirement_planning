"""
Stage 2: Prep for Retirement

Refactored implementation using BaseLifeStageStrategy with dependency injection.
Within 10 years of retirement - optimize contribution types and account balances.
"""

import logging
from typing import Any, Optional

from ..base_strategy import BaseLifeStageStrategy
from ..interfaces import ITaxCalculator, IAccountManager
from ..models import PortfolioBalances, YearlyStrategy

logger = logging.getLogger(__name__)

# Fallback constants — used only when ira_limits.csv has no row for the year
_ROTH_IRA_INCOME_LIMIT_FALLBACK = 240_000  # MFJ phase-out upper bound
_IRA_CONTRIBUTION_LIMIT_FALLBACK = 7_000   # base limit (age < 50)


class Stage2PrepForRetirement(BaseLifeStageStrategy):
    """
    Stage 2: Prep for Retirement (within 10 years of planned retirement)
    
    - Still employed with wages
    - Focus: balance Roth, Traditional, and Taxable account ratios
    - Evaluate Roth 401k vs Traditional 401k based on tax rates
    - Backdoor Roth: contribute to Traditional IRA then convert (if income too high)
    - Mega backdoor Roth via employer 401k after-tax contributions
    - If Traditional accounts are too large, redirect savings to taxable brokerage
    - Healthcare costs still covered by employer
    """
    
    PREP_WINDOW_YEARS = 10  # Years before retirement that this stage activates
    
    def __init__(
        self,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None
    ):
        """
        Initialize Stage 2 Prep for Retirement strategy.
        
        Args:
            tax_calculator: Tax calculator for tax computations
            account_manager: Account manager for withdrawals/conversions
        """
        super().__init__(
            name="Stage 2: Prep for Retirement",
            description="Within 10 years of retirement — balance Roth/Traditional/Taxable, optimize contribution type",
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
        Applies when employed AND within PREP_WINDOW_YEARS of the last retirement date.
        
        Anchored to the *latest* retirement year so that Stage 2 covers the
        full prep window up until the last earner retires.
        
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
        
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()
            
            # Get retirement years for both people
            # Use None as default to detect if not configured
            retirement_year_primary = config_mgr.get("personal_info", "person1_retirement_year", None)
            retirement_year_spouse = config_mgr.get("personal_info", "person2_retirement_year", None)
            
            # If retirement years are not configured, not in prep window
            if retirement_year_primary is None and retirement_year_spouse is None:
                return False
            
            # Use the latest retirement year (handle None values)
            latest_retirement_year = max(
                retirement_year_primary if retirement_year_primary is not None else year,
                retirement_year_spouse if retirement_year_spouse is not None else year
            )
            years_to_retirement = latest_retirement_year - year

            # Include the retirement year itself (years_to_retirement == 0):
            # the person works a partial year and contributions/taxes still apply.
            return 0 <= years_to_retirement <= self.PREP_WINDOW_YEARS

        except Exception:
            return False
    
    def calculate_strategy(
        self,
        year: int,
        balances: PortfolioBalances,
        expenses: float,
        **kwargs: Any
    ) -> YearlyStrategy:
        """
        Calculate pre-retirement optimization strategy.
        
        Key decisions made each year:
        1. Assess whether Roth 401k or Traditional 401k is more tax-efficient
        2. If Traditional balance is large relative to Roth, redirect to Roth 401k
        3. If income too high for direct Roth IRA, execute backdoor Roth
        4. If Traditional balance is very large, invest in taxable brokerage
        5. Use BETR to validate any Roth conversion is beneficial
        
        Args:
            year: Current year
            balances: Current portfolio balances
            expenses: Annual expenses
            **kwargs: Additional parameters including:
                - wages: Annual wages/salary
                - age_primary: Primary person's age
                - age_spouse: Spouse's age
                - ss_benefits: Social Security benefits (if any)
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
        ss_benefits = kwargs.get('ss_benefits', 0.0)
        max_conversion_rate = kwargs.get('max_conversion_rate', 0.24)
        filing_status = kwargs.get('filing_status', 'married_filing_jointly')
        state = kwargs.get('state', 'PA')
        
        logger.debug(
            f"Stage 2 Prep calculation for year {year}, wages=${wages:,.2f}"
        )
        
        # Log if SS benefits present (age-gap marriage scenario)
        if ss_benefits > 0:
            logger.info(
                f"Stage 2 Prep: SS Benefits=${ss_benefits:,.2f} "
                "(one spouse collecting while other still working)"
            )
        
        # Create base strategy object
        strategy = self._create_yearly_strategy(
            year, age_primary, age_spouse, balances
        )
        
        # Set wages and SS benefits
        strategy.wages = wages
        strategy.ss_benefits = ss_benefits
        
        # Calculate pre-retirement healthcare costs
        healthcare_costs = self._calculate_preretirement_healthcare(
            year, age_primary, age_spouse
        )
        strategy.healthcare_costs = healthcare_costs
        
        # Get contribution rates from config
        contribution_rates = self._get_contribution_rates()
        contribution_401k = wages * contribution_rates['traditional']
        contribution_roth = wages * contribution_rates['roth']
        
        # Decision 1: Should new 401k contributions go Roth or Traditional?
        prefer_roth_401k, contrib_reason = self._determine_contribution_type(
            wages,
            contribution_401k,
            balances,
            max_conversion_rate,
            filing_status,
            year
        )
        
        # Calculate AGI based on contribution type
        agi_before_conversion = wages if prefer_roth_401k else wages - contribution_401k
        
        # Calculate taxes
        std_deduction = self.tax_calculator.calculate_standard_deduction(
            filing_status, year, age_primary, age_spouse
        )
        
        taxable_income = max(0, agi_before_conversion - std_deduction)
        federal_tax, max_rate, upper_bracket = self.tax_calculator.calculate_federal_tax(
            taxable_income, filing_status, year
        )
        
        state_tax = self.tax_calculator.calculate_state_tax(
            agi_before_conversion, state, year
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
        
        # Calculate FICA taxes
        fica_tax = self._calculate_fica_tax(wages)
        
        # Log contribution type decision
        self._log_decision(
            strategy,
            'contribution_decisions',
            '401k Contribution Type',
            'Roth 401k' if prefer_roth_401k else 'Traditional 401k',
            contrib_reason,
            current_rate=max_rate,
            expected_retirement_rate=max_conversion_rate,
            trad_balance=balances.traditional,
            roth_balance=balances.roth
        )
        
        # Decision 2: Backdoor Roth IRA
        backdoor_roth_amount = self._calculate_backdoor_roth(
            strategy,
            agi_before_conversion
        )
        
        # Decision 3: BETR-validated Roth conversion
        roth_conversion = self._calculate_prep_roth_conversion(
            strategy,
            balances,
            agi_before_conversion,
            std_deduction,
            max_rate,
            upper_bracket,
            max_conversion_rate,
            age_primary,
            filing_status,
            year
        )
        
        # Update strategy with calculated values
        strategy.expenses = expenses  # Store expenses in strategy
        # AGI includes Roth conversions (they are taxable income)
        strategy.agi = agi_before_conversion + roth_conversion
        strategy.magi = strategy.agi
        strategy.taxable_income = taxable_income
        strategy.federal_tax = federal_tax
        strategy.state_tax = state_tax
        strategy.fica_tax = fica_tax
        strategy.payroll_tax = fica_tax  # Payroll tax is FICA
        strategy.roth_conversion = roth_conversion
        strategy.conversion_executed = roth_conversion  # For dataframe display
        
        # Set contribution fields for display
        if prefer_roth_401k:
            strategy.wages_to_roth = contribution_401k
            strategy.wages_to_trad = 0.0
        else:
            strategy.wages_to_trad = contribution_401k
            strategy.wages_to_roth = 0.0
        
        strategy.cash_to_roth = contribution_roth + backdoor_roth_amount
        strategy.cash_to_brokerage = 0.0  # Stage 2 doesn't contribute to brokerage
        
        # Update balances after contributions and conversions
        if prefer_roth_401k:
            strategy.traditional_balance = balances.traditional - roth_conversion
            strategy.roth_balance = (
                balances.roth + contribution_401k + contribution_roth + 
                backdoor_roth_amount + roth_conversion
            )
        else:
            strategy.traditional_balance = (
                balances.traditional + contribution_401k - roth_conversion
            )
            strategy.roth_balance = (
                balances.roth + contribution_roth + backdoor_roth_amount + roth_conversion
            )
        
        strategy.taxable_balance = balances.taxable
        strategy.cash_balance = balances.cash
        
        # Calculate take-home pay
        take_home = wages - contribution_401k - contribution_roth - backdoor_roth_amount
        take_home -= federal_tax + state_tax + fica_tax + healthcare_costs
        
        # Add to cash if take-home exceeds expenses
        total_costs = expenses + healthcare_costs
        if take_home > total_costs:
            strategy.cash_balance += (take_home - total_costs)
        else:
            # If take-home doesn't cover expenses + healthcare, draw from cash
            shortfall = total_costs - take_home
            strategy.cash_balance -= shortfall
        
        # Log cash to Roth contribution
        stage2_cash_to_roth = (
            (contribution_401k if prefer_roth_401k else 0) + 
            contribution_roth + 
            backdoor_roth_amount
        )
        
        if stage2_cash_to_roth > 0:
            self._log_decision(
                strategy,
                'contribution_decisions',
                'Cash → Roth Contribution',
                f'Contribute ${stage2_cash_to_roth:,.0f} from take-home pay',
                'After-tax wages routed to Roth (Roth 401k and/or backdoor Roth IRA). '
                'Builds tax-free savings without early-withdrawal penalty.',
                roth_401k=contribution_401k if prefer_roth_401k else 0,
                roth_ira=contribution_roth,
                backdoor_roth=backdoor_roth_amount
            )
        
        logger.debug(
            f"Stage 2 complete: AGI=${strategy.agi:,.2f}, "
            f"Federal Tax=${federal_tax:,.2f}, "
            f"Roth Conversion=${roth_conversion:,.2f}, "
            f"Prefer Roth 401k={prefer_roth_401k}"
        )
        
        return strategy
    
    def _get_contribution_rates(self) -> dict[str, float]:
        """
        Get contribution rates from config.
        
        Returns:
            Dict with 'traditional', 'roth' rates (0-1)
        """
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()
            
            trad_pct = float(config_mgr.get("income", "contribution_401k_percent", 10.0)) / 100.0
            roth_pct = float(config_mgr.get("income", "contribution_roth_percent", 5.0)) / 100.0
        except Exception:
            trad_pct, roth_pct = 0.10, 0.05
        
        # Clamp each rate to [0, 1]
        trad_pct = max(0.0, min(1.0, trad_pct))
        roth_pct = max(0.0, min(1.0, roth_pct))
        
        return {
            'traditional': trad_pct,
            'roth': roth_pct
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
    
    def _determine_contribution_type(
        self,
        wages: float,
        contribution_401k: float,
        balances: PortfolioBalances,
        expected_retirement_rate: float,
        filing_status: str,
        year: int
    ) -> tuple[bool, str]:
        """
        Determine whether to use Roth 401k or Traditional 401k.
        
        Decision logic:
        1. If Traditional > 2× Roth, prefer Roth 401k to rebalance
        2. If current marginal rate > expected retirement rate, prefer Roth 401k
        3. Otherwise, prefer Traditional 401k
        
        Args:
            wages: Annual wages
            contribution_401k: Traditional 401k contribution amount
            balances: Current balances
            expected_retirement_rate: Expected tax rate in retirement
            filing_status: Filing status
            year: Current year
            
        Returns:
            Tuple of (prefer_roth_401k, reason)
        """
        # Check if Traditional balance is disproportionately large
        trad_heavy = (
            balances.roth > 0 and 
            balances.traditional > 2 * balances.roth
        )
        
        if trad_heavy:
            reason = (
                f"Traditional balance (${balances.traditional:,.0f}) exceeds 2× Roth "
                f"(${balances.roth:,.0f}). Redirecting 401k contributions to Roth to rebalance "
                "the tax-deferred vs tax-free ratio and reduce future RMD exposure."
            )
            logger.info(
                f"Year {year}: Traditional > 2× Roth — redirecting to Roth 401k"
            )
            return True, reason
        
        # Calculate preliminary tax rate with Traditional assumption
        preliminary_agi = wages - contribution_401k
        std_deduction = self.tax_calculator.calculate_standard_deduction(
            filing_status, year, 0, 0
        )
        preliminary_taxable = max(0, preliminary_agi - std_deduction)
        _, preliminary_rate, _ = self.tax_calculator.calculate_federal_tax(
            preliminary_taxable, filing_status, year
        )
        
        # Compare current rate to expected retirement rate
        if preliminary_rate > expected_retirement_rate:
            reason = (
                f"Current marginal rate ({preliminary_rate:.1%}) exceeds expected retirement rate "
                f"({expected_retirement_rate:.1%}). Paying Roth tax now is cheaper than "
                "paying ordinary income tax on Traditional withdrawals in retirement."
            )
            return True, reason
        else:
            reason = (
                f"Current marginal rate ({preliminary_rate:.1%}) is at or below the expected retirement rate "
                f"({expected_retirement_rate:.1%}). Deferring tax now is more efficient; "
                "Traditional 401k reduces AGI and current-year tax bill."
            )
            return False, reason
    
    def _calculate_backdoor_roth(
        self,
        strategy: YearlyStrategy,
        agi: float
    ) -> float:
        """
        Calculate backdoor Roth IRA contribution if income exceeds limit.
        
        Args:
            strategy: YearlyStrategy to log decisions to
            agi: AGI before conversion
            
        Returns:
            Backdoor Roth amount
        """
        # Look up IRA limits for this strategy year from ira_limits.csv
        try:
            from load_data import get_ira_limits
            _df = get_ira_limits(strategy.year)
            if not _df.empty:
                roth_income_limit = int(_df["roth_phaseout_end_mfj"].iloc[0])
                ira_contribution_limit = int(_df["ira_contribution_base"].iloc[0])
            else:
                logger.warning(
                    f"IRA limits not found for year {strategy.year}, using fallback constants"
                )
                roth_income_limit = _ROTH_IRA_INCOME_LIMIT_FALLBACK
                ira_contribution_limit = _IRA_CONTRIBUTION_LIMIT_FALLBACK
        except Exception as e:
            logger.warning(f"Could not load IRA limits for year {strategy.year}: {e}")
            roth_income_limit = _ROTH_IRA_INCOME_LIMIT_FALLBACK
            ira_contribution_limit = _IRA_CONTRIBUTION_LIMIT_FALLBACK

        if agi > roth_income_limit:
            backdoor_amount = ira_contribution_limit

            logger.info(
                f"Year {strategy.year}: AGI ${agi:,.0f} exceeds Roth IRA limit — "
                f"executing backdoor Roth ${backdoor_amount:,.0f}"
            )

            self._log_decision(
                strategy,
                'contribution_decisions',
                'Backdoor Roth IRA',
                f'Execute ${backdoor_amount:,.0f} backdoor Roth',
                f'AGI (${agi:,.0f}) exceeds the direct Roth IRA income limit (${roth_income_limit:,.0f}). '
                'Executing backdoor Roth: contribute to empty Traditional IRA then immediately convert, '
                'achieving Roth tax treatment without the income restriction.',
                agi=agi,
                income_limit=roth_income_limit,
                amount=backdoor_amount
            )

            return backdoor_amount
        else:
            self._log_decision(
                strategy,
                'contribution_decisions',
                'Backdoor Roth IRA',
                'Direct Roth IRA contribution eligible',
                f'AGI (${agi:,.0f}) is below the Roth IRA income limit (${roth_income_limit:,.0f}); '
                'backdoor Roth not needed.',
                agi=agi
            )
            return 0.0
    
    def _calculate_prep_roth_conversion(
        self,
        strategy: YearlyStrategy,
        balances: PortfolioBalances,
        agi: float,
        std_deduction: float,
        max_rate: float,
        upper_bracket: float,
        max_conversion_rate: float,
        age_primary: int,
        filing_status: str,
        year: int
    ) -> float:
        """
        Calculate optimal Roth conversion during prep phase using BETR.
        
        Args:
            strategy: YearlyStrategy to log decisions to
            balances: Current balances
            agi: AGI before conversion
            std_deduction: Standard deduction
            max_rate: Current marginal tax rate
            upper_bracket: Upper limit of current bracket
            max_conversion_rate: Maximum rate for conversions
            age_primary: Primary person's age
            filing_status: Filing status
            year: Current year
            
        Returns:
            Optimal conversion amount
        """
        if balances.traditional <= 0 or max_rate > max_conversion_rate:
            return 0.0
        
        # Calculate conversion room in current bracket
        conversion_room = max(0, upper_bracket - agi - std_deduction)
        
        if conversion_room < 10000:
            return 0.0
        
        # Propose conversion: lesser of room or 10% of traditional balance
        proposed_conversion = min(
            conversion_room,
            balances.traditional * 0.10
        )
        
        if proposed_conversion < 1000:
            return 0.0
        
        # Use BETR to validate conversion
        try:
            from betr_roth_conversion import calculate_betr, BETRInputs
            
            betr_inputs = BETRInputs(
                current_marginal_rate=max_rate,
                expected_future_rate=max_conversion_rate,
                conversion_amount=proposed_conversion,
                traditional_ira_balance=balances.traditional,
                pay_from_taxable=True,
                taxable_account_balance=balances.taxable,
                years_to_withdrawal=max(1, 73 - age_primary),
                annual_return=0.07
            )
            
            betr_results = calculate_betr(betr_inputs)
            
            if betr_results.conversion_recommended:
                logger.info(
                    f"Stage 2 Prep Roth conversion: ${proposed_conversion:,.0f} "
                    f"(BETR: {betr_results.betr:.2%}, rate: {max_rate:.1%})"
                )
                
                self._log_decision(
                    strategy,
                    'roth_conversion',
                    'BETR Conversion (Stage 2 Prep)',
                    f'Convert ${proposed_conversion:,.0f}',
                    'BETR recommends converting while still employed: current rate is at or below '
                    'the expected retirement rate, so paying tax now is cheaper than paying it '
                    'on RMDs later. Capped at 10% of Traditional balance.',
                    betr=betr_results.betr,
                    current_rate=max_rate,
                    expected_rate=max_conversion_rate,
                    amount=proposed_conversion
                )
                
                return proposed_conversion
            else:
                logger.debug(
                    f"BETR analysis shows conversion not beneficial: "
                    f"BETR={betr_results.betr:.2%}"
                )
                return 0.0
                
        except ImportError:
            logger.warning("BETR module not available, skipping conversion analysis")
            return 0.0
        except Exception as e:
            logger.error(f"Error in BETR calculation: {e}")
            return 0.0
    
    def _calculate_preretirement_healthcare(
        self,
        year: int,
        age_primary: int,
        age_spouse: int
    ) -> float:
        """
        Calculate pre-retirement healthcare costs for employed individuals.

        In the retirement year the premium is prorated by the fraction of the
        year the person is still employed (from their configured retirement date).

        Args:
            year: Current year
            age_primary: Primary person's age
            age_spouse: Spouse's age

        Returns:
            Total annual healthcare costs (prorated in retirement year)
        """
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()

            total_cost = 0.0

            # Person 1 healthcare — prorate by fraction of year still employed
            p1_fraction = config_mgr.get_retirement_fraction(1, year)
            if p1_fraction > 0:
                coverage_type = config_mgr.get("healthcare", "person1_preretirement_coverage_type", "None")
                if coverage_type != "None":
                    monthly_premium = float(config_mgr.get("healthcare", "person1_preretirement_insurance_monthly", 0))
                    prorated = monthly_premium * 12 * p1_fraction
                    total_cost += prorated
                    logger.debug(
                        f"Person 1 pre-retirement healthcare: ${prorated:,.2f}/year "
                        f"(${monthly_premium * 12:,.2f} × {p1_fraction:.1%}, {coverage_type})"
                    )

            # Person 2 healthcare — prorate by fraction of year still employed
            p2_fraction = config_mgr.get_retirement_fraction(2, year)
            if p2_fraction > 0:
                coverage_type = config_mgr.get("healthcare", "person2_preretirement_coverage_type", "None")
                if coverage_type != "None":
                    monthly_premium = float(config_mgr.get("healthcare", "person2_preretirement_insurance_monthly", 0))
                    prorated = monthly_premium * 12 * p2_fraction
                    total_cost += prorated
                    logger.debug(
                        f"Person 2 pre-retirement healthcare: ${prorated:,.2f}/year "
                        f"(${monthly_premium * 12:,.2f} × {p2_fraction:.1%}, {coverage_type})"
                    )

            if total_cost > 0:
                logger.info(f"Year {year}: Pre-retirement healthcare costs: ${total_cost:,.2f}")

            return total_cost

        except Exception as e:
            logger.warning(f"Error calculating pre-retirement healthcare: {e}")
            return 0.0

# Made with Bob
