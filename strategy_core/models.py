"""
Core Data Models for Strategy Components

Defines all data structures used throughout the strategy system with
comprehensive type hints and validation.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union
from enum import Enum


@dataclass
class PortfolioBalances:
    """
    Container for portfolio account balances.

    Attributes:
        cash: Cash/money market balance
        taxable: Taxable brokerage account balance
        traditional: Tax-deferred account balance (401k, Traditional IRA) — combined total
        roth: Tax-free account balance (Roth IRA, Roth 401k)
        daf: Donor Advised Fund balance
        traditional_person1: Tax-deferred balance owned by person 1 (Tom).
            None until explicitly populated from the portfolio DB.
        traditional_person2: Tax-deferred balance owned by person 2 (Sarah).
            None until explicitly populated from the portfolio DB.

    Per-person split notes
    ----------------------
    ``traditional_person1 + traditional_person2`` should equal ``traditional``
    (aside from rounding).  When either is ``None`` callers fall back to a
    proportional split of ``traditional`` based on the last known ratio, or to
    a 70/30 heuristic derived from the current portfolio snapshot.

    The combined ``traditional`` field is kept as the single source of truth for
    all balance arithmetic so that existing code paths are unchanged.  The
    per-person fields are *additive metadata* used only by Stage 6 RMD
    calculations and the monthly calendar.
    """
    cash: float
    taxable: float
    traditional: float
    roth: float
    daf: float = 0.0
    # Per-person Traditional split — optional; None = not yet populated
    traditional_person1: Optional[float] = None
    traditional_person2: Optional[float] = None

    def total(self) -> float:
        """Calculate total portfolio value across all accounts"""
        return self.cash + self.taxable + self.traditional + self.roth + self.daf

    def person1_fraction(self) -> float:
        """Fraction of traditional balance owned by person 1 (0.0–1.0).

        Returns the exact fraction when per-person data is available, otherwise
        falls back to 0.70 (Tom's approximate share from the July 2026 snapshot).
        """
        if (self.traditional_person1 is not None
                and self.traditional_person2 is not None
                and self.traditional > 0):
            return self.traditional_person1 / self.traditional
        return 0.70  # fallback: Tom ~70%, Sarah ~30%

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization"""
        return asdict(self)

    def __post_init__(self) -> None:
        """Validate required balances are non-negative."""
        for field_name in ['cash', 'taxable', 'traditional', 'roth', 'daf']:
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} balance cannot be negative: {value}")
        # Per-person fields are allowed to be None (not yet populated) or non-negative.
        for field_name in ['traditional_person1', 'traditional_person2']:
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} balance cannot be negative: {value}")


@dataclass
class BrokerageTransaction:
    """
    Represents a single transaction in a brokerage account.
    
    Tracks cost basis and gains for tax-efficient withdrawal strategies.
    
    Attributes:
        amount: Transaction amount (positive for deposits, negative for withdrawals)
        basis: Cost basis of the transaction
        year: Year of transaction
        description: Optional description
    """
    amount: float
    basis: float
    year: int
    description: str = ""
    
    def apply_growth(self, growth_rate: float) -> None:
        """
        Apply annual growth to this transaction.
        
        Args:
            growth_rate: Annual growth rate (e.g., 0.07 for 7%)
        """
        self.amount *= (1 + growth_rate)
    
    def calculate_gain(self) -> float:
        """Calculate unrealized gain on this transaction"""
        return max(0.0, self.amount - self.basis)
    
    def calculate_gain_percentage(self) -> float:
        """Calculate gain as percentage of basis"""
        if self.basis <= 0:
            return 0.0
        return (self.amount - self.basis) / self.basis


@dataclass
class BrokerageAccount:
    """
    Manages a taxable brokerage account with FIFO withdrawal tracking.
    
    Tracks individual transactions to calculate cost basis and capital gains
    for tax-efficient withdrawals.
    
    Attributes:
        transactions: List of transactions in chronological order
        owner: Account owner ('primary', 'spouse', or 'joint')
    """
    transactions: List[BrokerageTransaction] = field(default_factory=list)
    owner: str = "joint"
    
    def total_value(self) -> float:
        """Calculate total account value"""
        return sum(t.amount for t in self.transactions)
    
    def total_basis(self) -> float:
        """Calculate total cost basis"""
        return sum(t.basis for t in self.transactions)
    
    def total_gains(self) -> float:
        """Calculate total unrealized gains"""
        return self.total_value() - self.total_basis()
    
    def ltcg_ratio(self) -> float:
        """
        Calculate ratio of long-term capital gains to total value.
        
        Returns:
            Ratio between 0 and 1
        """
        total = self.total_value()
        if total <= 0:
            return 0.0
        return min(1.0, self.total_gains() / total)
    
    def basis_ratio(self) -> float:
        """
        Calculate ratio of cost basis to total value.
        
        Returns:
            Ratio between 0 and 1
        """
        total = self.total_value()
        if total <= 0:
            return 1.0
        return min(1.0, self.total_basis() / total)
    
    def add_transfer(self, amount: float, basis: float, year: int, 
                     description: str = "") -> None:
        """
        Add a new transaction to the account.
        
        Args:
            amount: Transaction amount
            basis: Cost basis
            year: Transaction year
            description: Optional description
        """
        if amount > 0:
            self.transactions.append(
                BrokerageTransaction(amount, basis, year, description)
            )
    
    def apply_annual_growth(self, growth_rate: float) -> None:
        """
        Apply annual growth to all transactions.
        
        Args:
            growth_rate: Annual growth rate (e.g., 0.07 for 7%)
        """
        for transaction in self.transactions:
            transaction.apply_growth(growth_rate)
    
    def withdraw_fifo(self, amount: float) -> tuple[float, float]:
        """
        Withdraw using FIFO (First In, First Out) method.
        
        Args:
            amount: Amount to withdraw
            
        Returns:
            Tuple of (amount_withdrawn, ltcg_realized)
        """
        if amount <= 0:
            return 0.0, 0.0
        
        remaining = amount
        total_withdrawn = 0.0
        total_ltcg = 0.0
        
        # Process transactions in order (FIFO)
        transactions_to_remove = []
        for i, transaction in enumerate(self.transactions):
            if remaining <= 0:
                break
            
            if transaction.amount <= remaining:
                # Withdraw entire transaction
                withdrawn = transaction.amount
                ltcg = transaction.calculate_gain()
                remaining -= withdrawn
                total_withdrawn += withdrawn
                total_ltcg += ltcg
                transactions_to_remove.append(i)
            else:
                # Partial withdrawal from this transaction
                withdrawn = remaining
                basis_ratio = transaction.basis / transaction.amount
                basis_withdrawn = withdrawn * basis_ratio
                ltcg = withdrawn - basis_withdrawn
                
                transaction.amount -= withdrawn
                transaction.basis -= basis_withdrawn
                
                total_withdrawn += withdrawn
                total_ltcg += ltcg
                remaining = 0.0
        
        # Remove fully withdrawn transactions (in reverse to maintain indices)
        for i in reversed(transactions_to_remove):
            del self.transactions[i]
        
        return total_withdrawn, total_ltcg
    
    def get_summary(self) -> Dict[str, Any]:
        """Get account summary statistics"""
        return {
            'total_value': self.total_value(),
            'total_basis': self.total_basis(),
            'total_gains': self.total_gains(),
            'ltcg_ratio': self.ltcg_ratio(),
            'basis_ratio': self.basis_ratio(),
            'num_transactions': len(self.transactions),
            'owner': self.owner,
        }


@dataclass
class DecisionReason:
    """
    A single named decision with its rationale and supporting values.
    
    Attributes:
        decision: Short label (e.g., "Roth Conversion")
        action: What was decided (e.g., "Convert $45,000")
        reason: Human-readable explanation
        values: Supporting numerical values for display
    """
    decision: str
    action: str
    reason: str
    values: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)


@dataclass
class DecisionLog:
    """
    Structured record of every material decision made for a single strategy year.
    
    Each stage populates the relevant fields. Consumers (UI, reports) can
    iterate all_decisions() to get a flat list of every reason recorded.
    
    Attributes:
        stage_info: Life stage information and context
        tax_strategy: Tax-related decisions
        roth_conversion: Roth conversion decisions
        aca_decisions: ACA/healthcare decisions
        irmaa_decisions: IRMAA-related decisions
        cash_replenishment: Cash buffer decisions
        brokerage_replenishment: Brokerage buffer decisions
        contribution_decisions: Contribution/accumulation decisions
        rmd_decisions: RMD-related decisions
        ltcg_decisions: Capital gains harvesting decisions
        ss_decisions: Social Security decisions
        daf_decisions: Donor Advised Fund decisions
    """
    stage_info: List[DecisionReason] = field(default_factory=list)
    tax_strategy: List[DecisionReason] = field(default_factory=list)
    roth_conversion: List[DecisionReason] = field(default_factory=list)
    aca_decisions: List[DecisionReason] = field(default_factory=list)
    irmaa_decisions: List[DecisionReason] = field(default_factory=list)
    cash_replenishment: List[DecisionReason] = field(default_factory=list)
    brokerage_replenishment: List[DecisionReason] = field(default_factory=list)
    contribution_decisions: List[DecisionReason] = field(default_factory=list)
    rmd_decisions: List[DecisionReason] = field(default_factory=list)
    ltcg_decisions: List[DecisionReason] = field(default_factory=list)
    ss_decisions: List[DecisionReason] = field(default_factory=list)
    daf_decisions: List[DecisionReason] = field(default_factory=list)
    
    def add(self, category: str, decision: str, action: str,
            reason: str, **values: Any) -> None:
        """
        Convenience method to append a DecisionReason to a category.
        
        Args:
            category: One of the field names on this dataclass
            decision: Short label for the decision point
            action: What was chosen
            reason: Human-readable explanation
            **values: Arbitrary keyword arguments stored in DecisionReason.values
            
        Raises:
            AttributeError: If category is not a valid field name
        """
        entry = DecisionReason(
            decision=decision,
            action=action,
            reason=reason,
            values=dict(values)
        )
        target: List[DecisionReason] = getattr(self, category)
        target.append(entry)
    
    def all_decisions(self) -> List[DecisionReason]:
        """
        Return every DecisionReason across all categories.
        
        Returns:
            List of all decisions in insertion order per category
        """
        out: List[DecisionReason] = []
        for field_list in [
            self.stage_info,
            self.tax_strategy,
            self.roth_conversion,
            self.aca_decisions,
            self.irmaa_decisions,
            self.cash_replenishment,
            self.brokerage_replenishment,
            self.contribution_decisions,
            self.rmd_decisions,
            self.ltcg_decisions,
            self.ss_decisions,
            self.daf_decisions,
        ]:
            out.extend(field_list)
        return out
    
    def summary_lines(self) -> List[str]:
        """
        Return a flat list of human-readable summary strings.
        
        Returns:
            List of formatted decision strings, one per decision
        """
        lines = []
        for dr in self.all_decisions():
            vals = ", ".join(f"{k}={v}" for k, v in dr.values.items()) if dr.values else ""
            line = f"[{dr.decision}] {dr.action} — {dr.reason}"
            if vals:
                line += f" ({vals})"
            lines.append(line)
        return lines


@dataclass
class BrokerageTransactionLog:
    """
    Log of brokerage transactions for a single year.
    
    Attributes:
        withdrawals: List of withdrawal transactions
        deposits: List of deposit transactions
        total_ltcg: Total long-term capital gains realized
    """
    withdrawals: List[Dict[str, Any]] = field(default_factory=list)
    deposits: List[Dict[str, Any]] = field(default_factory=list)
    total_ltcg: float = 0.0


class ScenarioType(Enum):
    """Enumeration of scenario types for planning"""
    BASE = "base"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    CUSTOM = "custom"


@dataclass
class ScenarioConfig:
    """
    Configuration for a planning scenario.
    
    Attributes:
        name: Scenario name
        scenario_type: Type of scenario
        growth_rate: Annual portfolio growth rate
        inflation_rate: Annual inflation rate
        description: Optional description
    """
    name: str
    scenario_type: ScenarioType
    growth_rate: float
    inflation_rate: float
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'scenario_type': self.scenario_type.value,
            'growth_rate': self.growth_rate,
            'inflation_rate': self.inflation_rate,
            'description': self.description,
        }


@dataclass
class YearlyStrategy:
    """
    Complete strategy calculation results for a single year.
    
    Contains all financial calculations, decisions, and account balances
    for one year of the retirement plan.
    """
    year: int
    age_primary: int
    age_spouse: int
    stage: str
    
    # Income sources
    wages: float = 0.0
    ss_benefits: float = 0.0
    rmd_amount: float = 0.0        # combined RMD (both persons)
    rmd_person1: float = 0.0       # person 1's individual RMD (Tom)
    rmd_person2: float = 0.0       # person 2's individual RMD (Sarah)
    
    # Withdrawals
    cash_withdrawal: float = 0.0
    taxable_withdrawal: float = 0.0
    traditional_withdrawal: float = 0.0
    roth_withdrawal: float = 0.0
    
    # Conversions and transfers
    roth_conversion: float = 0.0
    
    # Taxes and costs
    federal_tax: float = 0.0
    state_tax: float = 0.0
    fica_tax: float = 0.0
    ltcg_tax: float = 0.0
    healthcare_costs: float = 0.0
    irmaa_penalty: float = 0.0
    aca_premium: float = 0.0
    payroll_tax: float = 0.0
    
    # Expenses
    expenses: float = 0.0
    
    # Charitable giving
    daf_contribution: float = 0.0
    
    # Wage contributions (accumulation phase)
    wages_to_trad: float = 0.0
    wages_to_roth: float = 0.0
    cash_to_roth: float = 0.0
    cash_to_brokerage: float = 0.0
    
    # Account balances (end of year)
    cash_balance: float = 0.0
    taxable_balance: float = 0.0
    traditional_balance: float = 0.0
    roth_balance: float = 0.0
    daf_balance: float = 0.0
    
    # Tax metrics
    agi: float = 0.0
    magi: float = 0.0
    taxable_income: float = 0.0
    ltcg_realized: float = 0.0
    
    # Transaction tracking
    traditional_to_cash: float = 0.0
    traditional_to_brokerage: float = 0.0
    brokerage_to_cash: float = 0.0
    roth_to_cash: float = 0.0
    roth_to_brokerage: float = 0.0
    conversion_executed: float = 0.0
    cash_replenishment: float = 0.0
    brokerage_replenishment: float = 0.0
    basis_returned: float = 0.0
    brokerage_ltcg_ratio: float = 0.0
    brokerage_basis_ratio: float = 0.0
    
    # Decision log
    decisions: DecisionLog = field(default_factory=DecisionLog)
    
    # Brokerage transactions
    brokerage_transactions: BrokerageTransactionLog = field(
        default_factory=BrokerageTransactionLog
    )
    
    def _collect_fund_movements(self) -> List[tuple[str, float]]:
        """Collect all fund movements for validation"""
        movements = []
        if self.wages > 0:
            movements.append(("wages", self.wages))
        if self.ss_benefits > 0:
            movements.append(("ss_benefits", self.ss_benefits))
        if self.rmd_amount > 0:
            movements.append(("rmd", self.rmd_amount))
        if self.cash_withdrawal > 0:
            movements.append(("cash_withdrawal", -self.cash_withdrawal))
        if self.taxable_withdrawal > 0:
            movements.append(("taxable_withdrawal", -self.taxable_withdrawal))
        if self.traditional_withdrawal > 0:
            movements.append(("traditional_withdrawal", -self.traditional_withdrawal))
        if self.roth_withdrawal > 0:
            movements.append(("roth_withdrawal", -self.roth_withdrawal))
        if self.roth_conversion > 0:
            movements.append(("roth_conversion", 0.0))  # Net zero movement
        return movements
    
    def validate_fund_conservation(self, expenses: float, tolerance: float = 1.0) -> bool:
        """
        Validate that funds are conserved (income matches expenses + taxes).
        
        Args:
            expenses: Expected annual expenses
            tolerance: Acceptable difference in dollars
            
        Returns:
            True if validation passes
            
        Raises:
            ValueError: If validation fails
        """
        total_income = (
            self.wages +
            self.ss_benefits +
            self.rmd_amount +
            self.cash_withdrawal +
            self.taxable_withdrawal +
            self.traditional_withdrawal +
            self.roth_withdrawal
        )
        
        total_outflow = (
            expenses +
            self.federal_tax +
            self.state_tax +
            self.fica_tax +
            self.ltcg_tax +
            self.healthcare_costs +
            self.irmaa_penalty
        )
        
        difference = abs(total_income - total_outflow)
        
        if difference > tolerance:
            raise ValueError(
                f"Fund conservation violated in year {self.year}: "
                f"Income={total_income:,.2f}, Outflow={total_outflow:,.2f}, "
                f"Difference={difference:,.2f}"
            )
        
        return True
    
    @property
    def ltcg_harvested(self) -> float:
        """
        Alias for ltcg_realized for backward compatibility.
        
        The old code uses 'ltcg_harvested' while the refactored model uses
        'ltcg_realized'. This property provides transparent access.
        
        Returns:
            Long-term capital gains realized/harvested amount
        """
        return self.ltcg_realized
    
    @ltcg_harvested.setter
    def ltcg_harvested(self, value: float) -> None:
        """Set ltcg_realized via the ltcg_harvested alias."""
        self.ltcg_realized = value
    
    @property
    def balances(self) -> PortfolioBalances:
        """
        Get account balances as a PortfolioBalances object.

        Returns a PortfolioBalances that carries the per-person traditional split
        if it was previously stored on this strategy object via the setter.

        Returns:
            PortfolioBalances object with current account balances
        """
        return PortfolioBalances(
            cash=self.cash_balance,
            taxable=self.taxable_balance,
            traditional=self.traditional_balance,
            roth=self.roth_balance,
            daf=self.daf_balance,
            traditional_person1=getattr(self, '_traditional_person1', None),
            traditional_person2=getattr(self, '_traditional_person2', None),
        )
    
    @balances.setter
    def balances(self, value: PortfolioBalances) -> None:
        """
        Set account balances from a PortfolioBalances object.

        This setter provides backward compatibility with code that sets
        the balances attribute.  The per-person traditional split carried on
        ``value`` is preserved on this strategy object so Stage 6 calculations
        can propagate it to subsequent years.

        Args:
            value: PortfolioBalances object with new balances
        """
        self.cash_balance = value.cash
        self.taxable_balance = value.taxable
        self.traditional_balance = value.traditional
        self.roth_balance = value.roth
        self.daf_balance = value.daf
        # Preserve per-person split so it survives the balance hand-off
        self._traditional_person1 = value.traditional_person1
        self._traditional_person2 = value.traditional_person2
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        # Convert nested dataclasses
        result['decisions'] = [dr.to_dict() for dr in self.decisions.all_decisions()]
        return result


@dataclass
class HealthcareCostBreakdown:
    """
    Breakdown of healthcare costs for a year.
    
    Attributes:
        medicare: Medicare costs (Part B, D, IRMAA)
        aca_premium: ACA marketplace premium
        aca_subsidy: ACA subsidy received
        out_of_pocket: Out-of-pocket medical expenses
        ltc_insurance: Long-term care insurance premium
    """
    medicare: float = 0.0
    aca_premium: float = 0.0
    aca_subsidy: float = 0.0
    out_of_pocket: float = 0.0
    ltc_insurance: float = 0.0
    
    def total(self) -> float:
        """Calculate total healthcare costs"""
        return (
            self.medicare +
            max(0.0, self.aca_premium - self.aca_subsidy) +
            self.out_of_pocket +
            self.ltc_insurance
        )


@dataclass
class MedicareBreakdown:
    """
    Breakdown of Medicare costs.
    
    Attributes:
        part_b_primary: Part B premium for primary
        part_b_spouse: Part B premium for spouse
        part_d_primary: Part D premium for primary
        part_d_spouse: Part D premium for spouse
        irmaa_primary: IRMAA surcharge for primary
        irmaa_spouse: IRMAA surcharge for spouse
    """
    part_b_primary: float = 0.0
    part_b_spouse: float = 0.0
    part_d_primary: float = 0.0
    part_d_spouse: float = 0.0
    irmaa_primary: float = 0.0
    irmaa_spouse: float = 0.0
    
    def total(self) -> float:
        """Calculate total Medicare costs"""
        return (
            self.part_b_primary +
            self.part_b_spouse +
            self.part_d_primary +
            self.part_d_spouse +
            self.irmaa_primary +
            self.irmaa_spouse
        )
    
    def total_irmaa(self) -> float:
        """Calculate total IRMAA surcharges"""
        return self.irmaa_primary + self.irmaa_spouse

# Made with Bob
