"""
Base Implementation for Life Stage Strategies

Provides a concrete base class that implements common functionality
for all life stage strategies, reducing code duplication.
"""

import logging
from typing import Any, Optional, Dict, Tuple, Union, List
from abc import abstractmethod

from .interfaces import ILifeStageStrategy, ITaxCalculator, IAccountManager, IDecisionLogger
from .models import PortfolioBalances, YearlyStrategy, DecisionLog, WithdrawalSequence, RothConversionTarget

logger = logging.getLogger(__name__)


class BaseLifeStageStrategy(ILifeStageStrategy):
    """
    Base implementation of ILifeStageStrategy with common functionality.
    
    Provides dependency injection support and common helper methods
    that all life stage strategies can use.
    
    Attributes:
        _name: Strategy name
        _description: Strategy description
        tax_calculator: Injected tax calculator
        account_manager: Injected account manager
        decision_logger: Injected decision logger
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        tax_calculator: Optional[ITaxCalculator] = None,
        account_manager: Optional[IAccountManager] = None,
        decision_logger: Optional[IDecisionLogger] = None
    ):
        """
        Initialize base strategy.
        
        Args:
            name: Human-readable strategy name
            description: Detailed strategy description
            tax_calculator: Optional tax calculator (can be injected later)
            account_manager: Optional account manager (can be injected later)
            decision_logger: Optional decision logger (can be injected later)
        """
        self._name = name
        self._description = description
        self.tax_calculator = tax_calculator
        self.account_manager = account_manager
        self.decision_logger = decision_logger
        
        logger.debug(f"Initialized {name} strategy")
    
    @property
    def name(self) -> str:
        """Human-readable name of this strategy stage"""
        return self._name
    
    @property
    def description(self) -> str:
        """Detailed description of this strategy stage"""
        return self._description
    
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
        
        Must be implemented by subclasses.
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
        
        Must be implemented by subclasses.
        """
        pass
    
    def _create_yearly_strategy(
        self,
        year: int,
        age_primary: int,
        age_spouse: int,
        balances: PortfolioBalances
    ) -> YearlyStrategy:
        """
        Create a YearlyStrategy object with initial values.
        
        Helper method to reduce boilerplate in subclasses.
        
        Args:
            year: Current year
            age_primary: Primary person's age
            age_spouse: Spouse's age
            balances: Current portfolio balances
            
        Returns:
            YearlyStrategy with stage name and balances set
        """
        return YearlyStrategy(
            year=year,
            age_primary=age_primary,
            age_spouse=age_spouse,
            stage=self.name,
            cash_balance=balances.cash,
            taxable_balance=balances.taxable,
            traditional_balance=balances.traditional,
            roth_balance=balances.roth,
            daf_balance=balances.daf,
            decisions=DecisionLog()
        )
    
    def _log_decision(
        self,
        strategy: YearlyStrategy,
        category: str,
        decision: str,
        action: str,
        reason: str,
        **values: Any
    ) -> None:
        """
        Log a decision to the strategy's decision log.
        
        Helper method that handles both the strategy's internal log
        and any injected decision logger.
        
        Args:
            strategy: YearlyStrategy to log to
            category: Decision category
            decision: Short decision label
            action: What was decided
            reason: Human-readable explanation
            **values: Supporting numerical values
        """
        # Log to strategy's internal log
        strategy.decisions.add(category, decision, action, reason, **values)
        
        # Also log to injected logger if available
        if self.decision_logger:
            self.decision_logger.log_decision(
                category, decision, action, reason, **values
            )
    
    def _calculate_daf_trad_prefund(
        self,
        strategy: YearlyStrategy,
        age_primary: int,
        year: int,
        traditional_balance: float,
        already_reserved: float,
    ) -> float:
        """
        Return the Traditional → Brokerage distribution amount for pre-funding.

        The only source is the year schedule: ``tax_strategy.trad_prefund_schedule``
        is a list of ``{"year", "amount"}`` rows used to seed a Direct Indexing
        portfolio. It does not require a DAF. What you set in the UI is exactly
        what executes.

        Args:
            strategy:            YearlyStrategy to log to
            age_primary:         Primary person's age (informational only)
            year:                Current calendar year
            traditional_balance: Current Traditional IRA / 401k balance
            already_reserved:    Amount already earmarked for normal buffer needs

        Returns:
            Pre-fund distribution amount (0 if not applicable this year)
        """
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()

            prefund_amount = 0.0
            for row in config_mgr.get("tax_strategy", "trad_prefund_schedule", []) or []:
                if int(row.get("year", 0)) == year:
                    prefund_amount += max(0.0, float(row.get("amount", 0) or 0))

            if prefund_amount <= 0:
                return 0.0

            # Cap to Traditional balance available after normal buffer needs
            available = max(0.0, traditional_balance - already_reserved)
            actual_amount = min(prefund_amount, available)

            if actual_amount <= 0:
                logger.info(
                    f"Year {year}: Trad→Brok pre-fund skipped — insufficient Traditional balance "
                    f"(available=${available:,.0f} after ${already_reserved:,.0f} reserved)"
                )
                return 0.0

            logger.info(
                f"Year {year}: Trad→Brok pre-fund: ${actual_amount:,.0f} "
                f"(scheduled ${prefund_amount:,.0f}, age {age_primary})"
            )
            self._log_decision(
                strategy,
                'tax_strategy',
                'Traditional → Brokerage Pre-Fund',
                f'Distribute ${actual_amount:,.0f} from Traditional → Brokerage',
                f'Pre-funding Brokerage with a Traditional distribution in {year} from '
                f'your pre-fund schedule (${prefund_amount:,.0f}) to seed Direct Indexing. '
                f'Roth conversion is suppressed this year; the distribution is taxed '
                f'as ordinary income.',
                year=year,
                prefund_amount=actual_amount,
                schedule_amount=prefund_amount,
            )
            return actual_amount

        except Exception as e:
            logger.warning(f"Trad→Brok pre-fund calculation failed: {e}")
            return 0.0

    def _apply_trad_prefund(
        self,
        strategy: YearlyStrategy,
        year: int,
        age_primary: int,
        balances: PortfolioBalances,
        already_reserved: float,
        pending_trad_withdrawal: float,
        brokerage_account: Any,
    ) -> Tuple[PortfolioBalances, float]:
        """
        Execute the scheduled Traditional → Brokerage pre-fund for ``year``.

        Shared by Stages 1, 2 and 4-7 (Stage 3 has its own inline path). When the schedule
        has an amount for ``year`` this:
          * moves the amount Traditional → Brokerage in the returned balances
            (per-person Traditional split is reduced pro rata),
          * registers a zero-gain lot so later Brokerage→Cash draws realise $0 LTCG,
          * logs that the Roth conversion is suppressed.

        The caller must set ``roth_conversion = 0`` and merge the returned amount
        into ``transactions['traditional_to_brokerage']`` (which feeds AGI).

        Args:
            pending_trad_withdrawal: Traditional→Cash already planned this year
                                     but not yet deducted from ``balances``.

        Returns:
            (new_balances, amount_moved). Amount is 0 when no pre-fund applies.
        """
        amount = self._calculate_daf_trad_prefund(
            strategy, age_primary, year,
            max(0.0, balances.traditional - pending_trad_withdrawal),
            already_reserved,
        )
        amount = min(amount, balances.traditional)
        if amount <= 0:
            return balances, 0.0

        if brokerage_account is not None:
            brokerage_account.add_transfer(year, amount, "trad_to_brok_zero_gain")

        p1 = p2 = None
        if (balances.traditional_person1 is not None
                and balances.traditional_person2 is not None
                and balances.traditional > 0):
            share = amount / balances.traditional
            p1 = balances.traditional_person1 * (1 - share)
            p2 = balances.traditional_person2 * (1 - share)

        new_balances = PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable + amount,
            traditional=balances.traditional - amount,
            roth=balances.roth,
            daf=balances.daf,
            traditional_person1=p1,
            traditional_person2=p2,
        )
        self._log_decision(
            strategy,
            'roth_conversion',
            'Roth Conversion Suppressed (Direct Indexing Pre-Fund Year)',
            'No conversion — Trad→Brok pre-fund active',
            f'A Traditional → Brokerage pre-fund of ${amount:,.0f} is executing this year '
            f'to seed Direct Indexing. The distribution is ordinary income, so no Roth '
            f'conversion is performed; the DAF contribution offsets taxable income.',
            daf_trad_prefund=amount,
        )
        return new_balances, amount

    @staticmethod
    def _merge_prefund_transactions(transactions: Dict[str, Any], amount: float) -> None:
        """Record a pre-fund transfer in the transaction dict (feeds AGI and reports)."""
        if amount <= 0:
            return
        transactions['traditional_to_brokerage'] = (
            transactions.get('traditional_to_brokerage', 0.0) + amount
        )
        transactions['brokerage_replenishment'] = (
            transactions.get('brokerage_replenishment', 0.0) + amount
        )

    def _calculate_total_income(
        self,
        wages: float = 0.0,
        ss_benefits: float = 0.0,
        rmd_amount: float = 0.0,
        withdrawals: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate total income from all sources.
        
        Args:
            wages: Wage income
            ss_benefits: Social Security benefits
            rmd_amount: Required Minimum Distribution
            withdrawals: Dict of withdrawal amounts by account type
            
        Returns:
            Total income
        """
        total = wages + ss_benefits + rmd_amount
        
        if withdrawals:
            total += sum(withdrawals.values())
        
        return total
    
    def _calculate_total_taxes(
        self,
        federal_tax: float = 0.0,
        state_tax: float = 0.0,
        fica_tax: float = 0.0,
        ltcg_tax: float = 0.0
    ) -> float:
        """
        Calculate total taxes.
        
        Args:
            federal_tax: Federal income tax
            state_tax: State income tax
            fica_tax: FICA/payroll tax
            ltcg_tax: Long-term capital gains tax
            
        Returns:
            Total taxes
        """
        return federal_tax + state_tax + fica_tax + ltcg_tax

    def _deduct_tax_from_balances(
        self,
        balances: PortfolioBalances,
        tax_amount: float,
        tax_name: str = "State Tax",
        year: int = 0
    ) -> PortfolioBalances:
        """Deduct tax from cash, pulling shortfall from Taxable, Traditional, or Roth if cash is insufficient."""
        if tax_amount <= 0:
            return balances

        cash_after = balances.cash - tax_amount
        if cash_after >= 0:
            return PortfolioBalances(
                cash=cash_after,
                taxable=balances.taxable,
                traditional=balances.traditional,
                roth=balances.roth,
                daf=balances.daf
            )

        # Cash is insufficient — pull shortfall from available liquid accounts
        shortfall = -cash_after
        pull_taxable = min(balances.taxable, shortfall)
        shortfall -= pull_taxable
        pull_trad = min(balances.traditional, shortfall)
        shortfall -= pull_trad
        pull_roth = min(balances.roth, shortfall)
        shortfall -= pull_roth

        logger.info(
            f"Year {year}: Insufficient cash for {tax_name} (${tax_amount:,.2f}). "
            f"Pulled shortfall: Taxable=${pull_taxable:,.2f}, Trad=${pull_trad:,.2f}, Roth=${pull_roth:,.2f}"
        )

        return PortfolioBalances(
            cash=0.0,
            taxable=max(0.0, balances.taxable - pull_taxable),
            traditional=max(0.0, balances.traditional - pull_trad),
            roth=max(0.0, balances.roth - pull_roth),
            daf=balances.daf
        )
    
    def _get_split_settings(self) -> tuple[bool, float, float]:
        """
        Get rate-aware contribution split settings from config.
        
        Returns:
            (auto_split enabled, employer match as fraction of wages,
             expected retirement marginal rate as a fraction)
        """
        try:
            from config import get_config_manager
            config_mgr = get_config_manager()
            
            auto = config_mgr.get("income", "contribution_auto_split", False) is True
            match = float(config_mgr.get("income", "employer_match_percent", 0.0)) / 100.0
            retire_rate = float(
                config_mgr.get("income", "expected_retirement_tax_rate", 22.0)
            ) / 100.0
        except Exception:
            return False, 0.0, 0.22
        
        return auto, max(0.0, min(1.0, match)), max(0.0, min(1.0, retire_rate))
    
    def _validate_dependencies(self) -> None:
        """
        Validate that required dependencies are injected.
        
        Raises:
            RuntimeError: If required dependencies are missing
        """
        if not self.tax_calculator:
            raise RuntimeError(
                f"{self.name} requires a tax_calculator to be injected"
            )
        if not self.account_manager:
            raise RuntimeError(
                f"{self.name} requires an account_manager to be injected"
            )
    
    def _apply_growth_to_balances(
        self,
        balances: PortfolioBalances,
        growth_rate: float
    ) -> PortfolioBalances:
        """
        Apply annual growth to portfolio balances.
        
        Args:
            balances: Current balances
            growth_rate: Annual growth rate (e.g., 0.07 for 7%)
            
        Returns:
            New PortfolioBalances with growth applied
        """
        multiplier = 1 + growth_rate
        
        return PortfolioBalances(
            cash=balances.cash * multiplier,
            taxable=balances.taxable * multiplier,
            traditional=balances.traditional * multiplier,
            roth=balances.roth * multiplier,
            daf=balances.daf * multiplier
        )
    
    def _deduct_daf_annual_grant(
        self,
        balances: PortfolioBalances,
        year: int,
        start_year: int,
        inflation_rate: float = 0.02,
    ) -> PortfolioBalances:
        """
        Deduct the inflation-adjusted annual charitable grant from the DAF balance.

        The DAF account holds funds that will be granted to charities over time.
        Each year the ``annual_charitable_giving`` amount (from config, inflated
        from ``start_year``) is paid out.  Without this deduction the DAF balance
        grows indefinitely, which is misleading.

        Args:
            balances:      Current balances after contributions and growth.
            year:          Current calendar year.
            start_year:    First year of the strategy (used for inflation base).
            inflation_rate: Annual charitable giving inflation rate (default 2%).

        Returns:
            New PortfolioBalances with DAF reduced by the annual grant amount.
            The DAF balance is floored at 0 (no negative balance).
        """
        try:
            from config import get_config_manager
            cfg = get_config_manager()
            has_daf        = bool(cfg.get("charitable_giving", "has_daf", False))
            annual_giving  = float(cfg.get("charitable_giving", "annual_charitable_giving", 0))
            giving_start   = int(cfg.get("charitable_giving", "charitable_giving_start_age", 61))
            giving_end     = int(cfg.get("charitable_giving", "charitable_giving_end_age", 95))
            giving_inflation = float(cfg.get("charitable_giving", "charitable_giving_inflation_rate", 2.0)) / 100.0
        except Exception:
            return balances

        if not has_daf or annual_giving <= 0 or balances.daf <= 0:
            return balances

        # Check age window — only deduct while active charitable giving is configured
        try:
            from config import get_config_manager as _cfg
            _c = _cfg()
            p1_birth = _c.get("personal_info", "person1_birth_date", "1966-01-01")
            p1_birth_year = int(str(p1_birth).split("-")[0])
            age_primary = year - p1_birth_year
        except Exception:
            age_primary = 61  # safe default: allow deduction

        if age_primary < giving_start or age_primary > giving_end:
            return balances

        # Inflate from start_year
        years_elapsed = max(0, year - start_year)
        grant = annual_giving * ((1 + giving_inflation) ** years_elapsed)
        new_daf = max(0.0, balances.daf - grant)

        logger.info(
            f"Year {year}: DAF annual grant deducted: ${grant:,.0f} "
            f"(base=${annual_giving:,.0f}, {years_elapsed} yrs inflation), "
            f"DAF balance: ${balances.daf:,.0f} → ${new_daf:,.0f}"
        )

        return PortfolioBalances(
            cash=balances.cash,
            taxable=balances.taxable,
            traditional=balances.traditional,
            roth=balances.roth,
            daf=new_daf,
            traditional_person1=balances.traditional_person1,
            traditional_person2=balances.traditional_person2,
        )

    def _calculate_shortfall(
        self,
        expenses: float,
        income: float,
        taxes: float,
        healthcare: float
    ) -> float:
        """
        Calculate funding shortfall that needs to be covered by withdrawals.
        
        Args:
            expenses: Annual expenses
            income: Income from wages, SS, etc.
            taxes: Total taxes
            healthcare: Healthcare costs
            
        Returns:
            Shortfall amount (positive means need more funds)
        """
        total_needs = expenses + taxes + healthcare
        shortfall = total_needs - income
        
        return max(0.0, shortfall)
    
    def _determine_withdrawal_sequence(
        self,
        shortfall: float,
        balances: PortfolioBalances,
        sequence_order: Optional[Union[str, WithdrawalSequence, List[str]]] = None,
        prefer_roth: bool = False
    ) -> Dict[str, float]:
        """
        Determine optimal withdrawal sequence to cover shortfall.
        
        Supports configurable withdrawal sequence:
        - "pro_rata": Draw cash first, then proportionally across all non-cash accounts
        - "taxable_deferred_free": Taxable -> Traditional -> Roth
        - "taxable_free_deferred": Taxable -> Roth -> Traditional
        - "deferred_taxable_free": Traditional -> Taxable -> Roth
        - "deferred_free_taxable": Traditional -> Roth -> Taxable
        - "free_deferred_taxable": Roth -> Traditional -> Taxable
        - "free_taxable_deferred": Roth -> Taxable -> Traditional
        - Custom list of account names, e.g. ['taxable', 'roth', 'traditional']
        
        Args:
            shortfall: Amount needed
            balances: Current balances
            sequence_order: Optional withdrawal sequence enum, identifier string, or list of accounts
            prefer_roth: If True (and sequence_order is None), prefer Roth over Traditional
            
        Returns:
            Dict mapping account type to withdrawal amount
        """
        withdrawals = {
            'cash': 0.0,
            'taxable': 0.0,
            'traditional': 0.0,
            'roth': 0.0
        }
        
        if shortfall <= 0:
            return withdrawals

        remaining = shortfall
        
        # 1. Cash first (no tax impact)
        if balances.cash > 0:
            cash_withdrawal = min(remaining, balances.cash)
            withdrawals['cash'] = cash_withdrawal
            remaining -= cash_withdrawal

        if remaining <= 0:
            return withdrawals

        # Determine sequence if not explicitly provided
        if sequence_order is None:
            try:
                from config import get_config_manager
                cfg = get_config_manager()
                sequence_order = cfg.get("tax_strategy", "withdrawal_sequence", None)
            except Exception:
                sequence_order = None

        if sequence_order is None:
            if prefer_roth:
                sequence_order = WithdrawalSequence.TAXABLE_FREE_DEFERRED
            else:
                sequence_order = WithdrawalSequence.TAXABLE_DEFERRED_FREE

        # Handle Pro-Rata withdrawal
        is_pro_rata = False
        if isinstance(sequence_order, WithdrawalSequence) and sequence_order == WithdrawalSequence.PRO_RATA:
            is_pro_rata = True
        elif isinstance(sequence_order, str) and sequence_order.lower().replace("-", "_") == "pro_rata":
            is_pro_rata = True

        if is_pro_rata:
            tot_non_cash = max(0.0, balances.taxable) + max(0.0, balances.traditional) + max(0.0, balances.roth)
            if tot_non_cash > 0:
                fraction = min(1.0, remaining / tot_non_cash)
                taxable_pull = max(0.0, balances.taxable) * fraction
                trad_pull = max(0.0, balances.traditional) * fraction
                roth_pull = max(0.0, balances.roth) * fraction

                withdrawals['taxable'] += taxable_pull
                withdrawals['traditional'] += trad_pull
                withdrawals['roth'] += roth_pull
                remaining = max(0.0, remaining - (taxable_pull + trad_pull + roth_pull))
        else:
            # Parse order list
            if isinstance(sequence_order, WithdrawalSequence):
                order_list = sequence_order.account_order or ['taxable', 'traditional', 'roth']
            elif isinstance(sequence_order, list):
                order_list = [str(x).lower() for x in sequence_order]
            elif isinstance(sequence_order, str):
                s_key = sequence_order.lower().replace("-", "_")
                order_map = {
                    "taxable_deferred_free": ['taxable', 'traditional', 'roth'],
                    "taxable_free_deferred": ['taxable', 'roth', 'traditional'],
                    "deferred_taxable_free": ['traditional', 'taxable', 'roth'],
                    "deferred_free_taxable": ['traditional', 'roth', 'taxable'],
                    "free_deferred_taxable": ['roth', 'traditional', 'taxable'],
                    "free_taxable_deferred": ['roth', 'taxable', 'traditional'],
                }
                order_list = order_map.get(s_key, ['taxable', 'traditional', 'roth'])
            else:
                order_list = ['taxable', 'traditional', 'roth']

            avail = {
                'taxable': max(0.0, balances.taxable),
                'traditional': max(0.0, balances.traditional),
                'roth': max(0.0, balances.roth),
            }

            for acct in order_list:
                if remaining <= 0:
                    break
                if acct in avail and avail[acct] > 0:
                    pull = min(remaining, avail[acct])
                    withdrawals[acct] += pull
                    avail[acct] -= pull
                    remaining -= pull

            # Fallback across any remaining account with balance
            if remaining > 0:
                for acct in ['taxable', 'traditional', 'roth']:
                    if remaining <= 0:
                        break
                    if avail.get(acct, 0.0) > 0:
                        pull = min(remaining, avail[acct])
                        withdrawals[acct] += pull
                        avail[acct] -= pull
                        remaining -= pull
        
        if remaining > 0.01:  # Small tolerance for rounding
            logger.warning(
                f"Unable to fully cover shortfall: ${remaining:,.2f} remaining"
            )
        
        return withdrawals
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"{self.__class__.__name__}(name='{self.name}')"

# Made with Bob
