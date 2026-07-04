"""
Bucket Strategy Module
=====================
Implements the three-bucket retirement strategy for managing sequence of returns risk.

Cash Needed Calculation:
The bucket strategy is based on "cash needed" from the portfolio, which is calculated as:
  Cash Needed = Outflows - Inflows

Outflows (money going out):
- Living expenses
- Healthcare costs
- Taxes

Inflows (money coming in):
- Wages/salary
- Social Security benefits
- Pension income
- Annuity income

Bucket Structure:
- Bucket 1 (Safety): 2 years of cash needed in cash/money market
- Bucket 2 (Transition): 8 years of cash needed with graduated stock/bond allocation
  - Year 1: 10% stocks, 90% bonds/money market
  - Year 2: 20% stocks, 80% bonds/money market
  - ...
  - Year 8: 80% stocks, 20% bonds/money market
- Bucket 3 (Growth): Remaining funds in 100% stocks

The strategy integrates with:
- Existing portfolio data from portfolio_data_truth.csv
- Market trend analysis for dynamic adjustments
- Tax-efficient account location rules
- Existing rebalancing infrastructure
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config import ConfigManager, get_config_manager
from load_data import get_portfolio_truth_by_month, get_latest_portfolio_month_year
from market_trend_analysis import (
    MarketCondition,
    MarketTrendConfig,
    get_market_condition,
    get_allocation_adjustment,
)
from portfolio import getPortfolioData
from portfolio_rebalancing import (
    BROKERAGE,
    TRADITIONAL,
    ROTH,
    CASH_ACCT,
    CASH_SYMBOL,
    _classify_asset,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default bucket configuration
DEFAULT_BUCKET_1_YEARS = 2  # Years of expenses in cash
DEFAULT_BUCKET_2_YEARS = 8  # Years of expenses in transition zone
DEFAULT_BUCKET_2_START_STOCK_PCT = 10  # Starting stock % in Bucket 2
DEFAULT_BUCKET_2_END_STOCK_PCT = 80  # Ending stock % in Bucket 2

# Account type preferences for each bucket
BUCKET_1_ACCOUNTS = [CASH_ACCT, BROKERAGE]  # Savings, then Brokerage cash
BUCKET_2_ACCOUNTS = [TRADITIONAL, ROTH, BROKERAGE]  # Tax-deferred first
BUCKET_3_ACCOUNTS = [ROTH, BROKERAGE]  # Tax-free growth preferred


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BucketType(Enum):
    """Bucket classification."""
    BUCKET_1_SAFETY = "bucket_1_safety"
    BUCKET_2_TRANSITION = "bucket_2_transition"
    BUCKET_3_GROWTH = "bucket_3_growth"
    UNASSIGNED = "unassigned"


class AssetClass(Enum):
    """Asset class classification."""
    CASH = "cash"
    BONDS = "bonds"
    STOCKS = "stocks"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class BucketConfig:
    """Configuration for bucket strategy."""
    enabled: bool = False
    bucket_1_years: float = DEFAULT_BUCKET_1_YEARS
    bucket_2_years: int = DEFAULT_BUCKET_2_YEARS
    bucket_2_start_stock_pct: float = DEFAULT_BUCKET_2_START_STOCK_PCT
    bucket_2_end_stock_pct: float = DEFAULT_BUCKET_2_END_STOCK_PCT
    annual_expenses: float = 50000  # From config
    annual_healthcare: float = 0  # Annual healthcare costs
    annual_taxes: float = 0  # Estimated annual tax burden
    annual_wages: float = 0  # Annual wage income (person1 + person2)
    annual_ssi: float = 0  # Annual Social Security income
    annual_pension: float = 0  # Annual pension income
    annual_annuities: float = 0  # Annual annuity income
    market_trend_enabled: bool = True
    market_trend_config: MarketTrendConfig = field(default_factory=MarketTrendConfig)
    
    def get_annual_cash_needed(self) -> float:
        """
        Calculate annual cash needed from portfolio.
        
        Cash Needed = Outflows - Inflows
        
        Outflows:
        - Living expenses
        - Healthcare costs
        - Taxes
        
        Inflows:
        - Wages/salary
        - Social Security benefits
        - Pension income
        - Annuity income
        
        Returns:
            Annual cash needed from portfolio (can be negative if inflows exceed outflows)
        """
        total_outflows = self.annual_expenses + self.annual_healthcare + self.annual_taxes
        total_inflows = self.annual_wages + self.annual_ssi + self.annual_pension + self.annual_annuities
        cash_needed = total_outflows - total_inflows
        
        logger.debug(
            f"Cash needed calculation: "
            f"Outflows=${total_outflows:,.0f} "
            f"(expenses=${self.annual_expenses:,.0f} + "
            f"healthcare=${self.annual_healthcare:,.0f} + "
            f"taxes=${self.annual_taxes:,.0f}) - "
            f"Inflows=${total_inflows:,.0f} "
            f"(wages=${self.annual_wages:,.0f} + "
            f"SSI=${self.annual_ssi:,.0f} + "
            f"pension=${self.annual_pension:,.0f} + "
            f"annuities=${self.annual_annuities:,.0f}) = "
            f"${cash_needed:,.0f}"
        )
        
        return max(0, cash_needed)  # Don't allow negative (excess inflows handled elsewhere)
    
    def get_bucket_2_allocation(self, year_num: int) -> Tuple[float, float]:
        """
        Get stock/bond allocation for a specific year in Bucket 2.
        
        Args:
            year_num: Year number (1-8)
            
        Returns:
            Tuple of (stock_pct, bond_pct)
        """
        if year_num < 1 or year_num > self.bucket_2_years:
            raise ValueError(f"Year number must be 1-{self.bucket_2_years}")
        
        # Linear interpolation from start to end percentage
        stock_pct = self.bucket_2_start_stock_pct + (
            (self.bucket_2_end_stock_pct - self.bucket_2_start_stock_pct) *
            (year_num - 1) / (self.bucket_2_years - 1)
        )
        bond_pct = 100 - stock_pct
        
        return stock_pct, bond_pct


@dataclass
class BucketAllocation:
    """Target allocation for a bucket."""
    bucket_type: BucketType
    target_value: float  # Dollar amount
    target_cash_pct: float = 0.0
    target_bonds_pct: float = 0.0
    target_stocks_pct: float = 0.0
    year_in_bucket: Optional[int] = None  # For Bucket 2 years
    
    def __post_init__(self):
        """Validate that percentages sum to 100."""
        total = self.target_cash_pct + self.target_bonds_pct + self.target_stocks_pct
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Allocation percentages must sum to 100, got {total}")


@dataclass
class HoldingClassification:
    """Classification of a portfolio holding."""
    account_name: str
    account_type: str
    symbol: str
    name: str
    sector: str
    quantity: float
    purchase_price: float
    current_price: float
    current_value: float
    asset_class: AssetClass
    bucket_assignment: BucketType
    year_in_bucket: Optional[int] = None


@dataclass
class BucketSummary:
    """Summary of current bucket allocations."""
    bucket_1_value: float
    bucket_1_target: float
    bucket_2_value: float
    bucket_2_target: float
    bucket_3_value: float
    bucket_3_target: float
    total_portfolio_value: float
    bucket_1_pct: float
    bucket_2_pct: float
    bucket_3_pct: float
    needs_rebalancing: bool
    market_condition: Optional[MarketCondition] = None
    holdings: List[HoldingClassification] = field(default_factory=list)
    
    def get_bucket_drift(self, bucket_type: BucketType) -> float:
        """
        Calculate drift percentage for a bucket.
        
        Args:
            bucket_type: Which bucket to check
            
        Returns:
            Drift percentage (positive = over-allocated, negative = under-allocated)
        """
        if bucket_type == BucketType.BUCKET_1_SAFETY:
            if self.bucket_1_target == 0:
                return 0.0
            return ((self.bucket_1_value - self.bucket_1_target) / self.bucket_1_target) * 100
        elif bucket_type == BucketType.BUCKET_2_TRANSITION:
            if self.bucket_2_target == 0:
                return 0.0
            return ((self.bucket_2_value - self.bucket_2_target) / self.bucket_2_target) * 100
        elif bucket_type == BucketType.BUCKET_3_GROWTH:
            if self.bucket_3_target == 0:
                return 0.0
            return ((self.bucket_3_value - self.bucket_3_target) / self.bucket_3_target) * 100
        return 0.0


# ---------------------------------------------------------------------------
# Tax Estimation
# ---------------------------------------------------------------------------

def estimate_annual_taxes(
    annual_expenses: float,
    config_mgr: Optional[ConfigManager] = None
) -> float:
    """
    Estimate annual tax burden for bucket strategy planning.
    
    This provides a rough estimate based on typical withdrawal scenarios.
    For more accurate tax planning, use the full strategy module.
    
    Args:
        annual_expenses: Expected annual expenses
        config_mgr: Configuration manager
        
    Returns:
        Estimated annual tax amount
    """
    if config_mgr is None:
        config_mgr = get_config_manager()
    
    try:
        # Import here to avoid circular dependency
        from calculations import calculate_taxable_income
        from load_data import get_income_tax_brackets, get_std_deduction
        
        # Get current year for tax brackets
        current_year = datetime.now().year
        
        # Estimate taxable income as expenses (assuming withdrawals cover expenses)
        # This is a simplified estimate - actual taxes depend on:
        # - Account types (Traditional vs Roth vs Brokerage)
        # - Social Security income
        # - Other income sources
        # - Deductions and credits
        
        # Get standard deduction
        std_deduction_df = get_std_deduction(current_year, 'married_filing_jointly')
        std_deduction = std_deduction_df['deduction'].iloc[0] if not std_deduction_df.empty else 29200
        
        # Assume 85% of expenses come from taxable sources (Traditional IRA/401k)
        # The rest from Roth (tax-free) or already-taxed sources
        taxable_withdrawals = annual_expenses * 0.85
        
        # Calculate AGI (withdrawals minus standard deduction)
        agi = max(0, taxable_withdrawals - std_deduction)
        
        if agi == 0:
            return 0
        
        # Get tax brackets and calculate tax
        tax_brackets = get_income_tax_brackets(current_year)
        result = calculate_taxable_income(agi, tax_brackets)
        
        # Add estimated state tax (assume 5% effective rate on AGI)
        state_tax = agi * 0.05
        
        total_tax = result.total_tax + state_tax
        
        logger.info(
            f"Estimated annual taxes: ${total_tax:,.0f} "
            f"(Federal: ${result.total_tax:,.0f}, State: ${state_tax:,.0f}) "
            f"based on ${annual_expenses:,.0f} expenses"
        )
        
        return total_tax
        
    except Exception as e:
        logger.warning(f"Could not estimate taxes, using 15% of expenses: {e}")
        # Fallback: assume 15% effective tax rate on expenses
        return annual_expenses * 0.15


# ---------------------------------------------------------------------------
# Configuration Loading
# ---------------------------------------------------------------------------

def load_bucket_config(config_mgr: Optional[ConfigManager] = None) -> BucketConfig:
    """
    Load bucket strategy configuration.
    
    Args:
        config_mgr: Configuration manager (uses global if None)
        
    Returns:
        BucketConfig instance
    """
    if config_mgr is None:
        config_mgr = get_config_manager()
    
    # Check if bucket strategy section exists
    bucket_section = config_mgr.get_section("bucket_strategy")
    
    if not bucket_section:
        # Return default config with enabled=False
        annual_expenses = config_mgr.get("financial_assumptions", "expected_annual_expenses", 50000)
        return BucketConfig(enabled=False, annual_expenses=annual_expenses)
    
    # Load market trend config
    market_trend_section = bucket_section.get("market_trend_adjustment", {})
    market_trend_config = MarketTrendConfig(
        enabled=market_trend_section.get("enabled", True),
        short_ema_weeks=market_trend_section.get("short_ma_weeks", 10),
        long_ema_weeks=market_trend_section.get("long_ma_weeks", 50),
        bull_adjustment=market_trend_section.get("bull_adjustment", 0.0),
        neutral_adjustment=market_trend_section.get("warning_adjustment", -10.0),
        bear_adjustment=market_trend_section.get("bear_adjustment", -20.0),
    )
    
    # Load outflows
    annual_expenses = config_mgr.get("financial_assumptions", "expected_annual_expenses", 50000)
    annual_healthcare = config_mgr.get("healthcare", "aca_insurance_monthly", 0) * 12
    annual_taxes = estimate_annual_taxes(annual_expenses, config_mgr)
    
    # Load inflows
    annual_wages = (
        config_mgr.get("income", "person1_annual_wages", 0) +
        config_mgr.get("income", "person2_annual_wages", 0)
    )
    annual_ssi = (
        config_mgr.get("social_security", "person1_ssi_amount", 0) +
        config_mgr.get("social_security", "person2_ssi_amount", 0)
    )
    annual_pension = config_mgr.get("income", "annual_pension", 0)
    annual_annuities = config_mgr.get("income", "annual_annuities", 0)
    
    logger.info(
        f"Loaded bucket config - Outflows: expenses=${annual_expenses:,.0f}, "
        f"healthcare=${annual_healthcare:,.0f}, taxes=${annual_taxes:,.0f} | "
        f"Inflows: wages=${annual_wages:,.0f}, SSI=${annual_ssi:,.0f}, "
        f"pension=${annual_pension:,.0f}, annuities=${annual_annuities:,.0f}"
    )
    
    return BucketConfig(
        enabled=bucket_section.get("enabled", False),
        bucket_1_years=bucket_section.get("bucket_1_years", DEFAULT_BUCKET_1_YEARS),
        bucket_2_years=bucket_section.get("bucket_2_years", DEFAULT_BUCKET_2_YEARS),
        bucket_2_start_stock_pct=bucket_section.get("bucket_2_start_stock_pct", DEFAULT_BUCKET_2_START_STOCK_PCT),
        bucket_2_end_stock_pct=bucket_section.get("bucket_2_end_stock_pct", DEFAULT_BUCKET_2_END_STOCK_PCT),
        annual_expenses=annual_expenses,
        annual_healthcare=annual_healthcare,
        annual_taxes=annual_taxes,
        annual_wages=annual_wages,
        annual_ssi=annual_ssi,
        annual_pension=annual_pension,
        annual_annuities=annual_annuities,
        market_trend_enabled=market_trend_section.get("enabled", True),
        market_trend_config=market_trend_config,
    )


# ---------------------------------------------------------------------------
# Asset Classification
# ---------------------------------------------------------------------------

def classify_holding_asset_class(symbol: str, sector: str, name: str) -> AssetClass:
    """
    Classify a holding into an asset class.
    
    Uses the same logic as portfolio_rebalancing._classify_asset.
    
    Args:
        symbol: Ticker symbol
        sector: Sector classification
        name: Security name
        
    Returns:
        AssetClass enum value
    """
    # Use existing classification logic from portfolio_rebalancing
    asset_class_str = _classify_asset(symbol, sector, name)
    
    if asset_class_str == "Cash":
        return AssetClass.CASH
    elif asset_class_str == "Bonds":
        return AssetClass.BONDS
    else:  # "Stocks"
        return AssetClass.STOCKS


# ---------------------------------------------------------------------------
# Bucket Assignment
# ---------------------------------------------------------------------------

def assign_holding_to_bucket(
    account_type: str,
    asset_class: AssetClass,
    config: BucketConfig,
    current_bucket_values: Optional[Dict[BucketType, float]] = None,
    total_portfolio_value: float = 0
) -> Tuple[BucketType, Optional[int]]:
    """
    Assign a holding to a bucket based on account type, asset class, and current allocations.
    
    Assignment rules (strict account type requirements):
    
    Bucket 1 (Safety) - Fully liquid cash/money market:
    - ONLY Savings/Checking accounts (any asset)
    - ONLY Brokerage cash/money market
    - NOT Traditional or Roth accounts (not liquid enough)
    
    Bucket 2 (Transition) - Moderate risk with graduated allocation:
    - Traditional IRA accounts (bonds and stocks ONLY, no cash)
    - Roth IRA accounts (can hold cash, bonds, or stocks)
    - Bonds should be held in Traditional for tax efficiency
    - NOT Brokerage accounts
    
    Bucket 3 (Growth) - Long-term growth:
    - Brokerage accounts (stocks and bonds)
    - Traditional IRA accounts (stocks when Bucket 2 is full, or cash)
    - Roth IRA accounts (stocks and bonds when not needed in Bucket 2)
    
    Args:
        account_type: Account type (Traditional, Roth, Brokerage, Savings)
        asset_class: Asset class of the holding
        config: Bucket configuration
        current_bucket_values: Current values in each bucket (for smart allocation)
        total_portfolio_value: Total portfolio value (for percentage calculations)
        
    Returns:
        Tuple of (BucketType, year_in_bucket)
    """
    # ============================================================
    # BUCKET 1: Only liquid cash in Savings/Checking/Brokerage
    # ============================================================
    
    # Savings/Checking accounts → Bucket 1 (any asset, but typically cash)
    if account_type == CASH_ACCT:
        return BucketType.BUCKET_1_SAFETY, None
    
    # Brokerage cash/money market → Bucket 1
    if account_type == BROKERAGE and asset_class == AssetClass.CASH:
        return BucketType.BUCKET_1_SAFETY, None
    
    # Traditional/Roth cash should NOT go to Bucket 1 (not liquid enough)
    # They will be assigned to Bucket 2 or 3 below
    
    # ============================================================
    # BUCKET 2: Brokerage or Traditional (NOT Roth)
    # ============================================================
    
    # Bonds in Traditional → Bucket 2 (tax-efficient location for bonds)
    if asset_class == AssetClass.BONDS and account_type == TRADITIONAL:
        return BucketType.BUCKET_2_TRANSITION, 4
    
    # Bonds in Brokerage or Roth → Bucket 3 (not ideal for Bucket 2)
    if asset_class == AssetClass.BONDS and account_type in [BROKERAGE, ROTH]:
        return BucketType.BUCKET_3_GROWTH, None
    
    # Cash/Money Market handling:
    # - Traditional cash → Bucket 3 (Traditional should only hold bonds/stocks in Bucket 2)
    # - Roth cash → Bucket 2 (can be in Bucket 2)
    if asset_class == AssetClass.CASH and account_type == TRADITIONAL:
        return BucketType.BUCKET_3_GROWTH, None
    
    if asset_class == AssetClass.CASH and account_type == ROTH:
        return BucketType.BUCKET_2_TRANSITION, 2
    
    # ============================================================
    # STOCKS: Intelligent allocation based on account type
    # ============================================================
    if asset_class == AssetClass.STOCKS:
        # Calculate target allocations based on cash needed from portfolio
        annual_cash_needed = config.get_annual_cash_needed()
        bucket_1_target = annual_cash_needed * config.bucket_1_years
        bucket_2_target = annual_cash_needed * config.bucket_2_years
        
        # Roth accounts → ALWAYS Bucket 3 (tax-free growth is best for long-term)
        if account_type == ROTH:
            return BucketType.BUCKET_3_GROWTH, None
        
        # Traditional and Brokerage stocks → Bucket 2 or 3 based on allocation needs
        if current_bucket_values and total_portfolio_value > 0:
            bucket_2_current = current_bucket_values.get(BucketType.BUCKET_2_TRANSITION, 0)
            bucket_2_pct = (bucket_2_current / total_portfolio_value * 100)
            bucket_2_target_pct = (bucket_2_target / total_portfolio_value * 100)
            
            # If Bucket 2 is under target, allocate there
            if bucket_2_pct < bucket_2_target_pct * 0.9:  # Less than 90% of target
                if account_type == TRADITIONAL:
                    return BucketType.BUCKET_2_TRANSITION, 6
                elif account_type == BROKERAGE:
                    return BucketType.BUCKET_2_TRANSITION, 5
        
        # Default allocation when Bucket 2 is at target
        if account_type == TRADITIONAL:
            return BucketType.BUCKET_3_GROWTH, None
        elif account_type == BROKERAGE:
            return BucketType.BUCKET_3_GROWTH, None
    
    # Fallback
    return BucketType.UNASSIGNED, None


# ---------------------------------------------------------------------------
# Portfolio Analysis
# ---------------------------------------------------------------------------

def analyze_portfolio_buckets(
    month: Optional[int] = None,
    year: Optional[int] = None,
    config: Optional[BucketConfig] = None
) -> BucketSummary:
    """
    Analyze current portfolio and classify holdings into buckets.
    
    Args:
        month: Portfolio month (None = current)
        year: Portfolio year (None = current)
        config: Bucket configuration (None = load from config)
        
    Returns:
        BucketSummary with current allocations
    """
    if config is None:
        config = load_bucket_config()
    
    if not config.enabled:
        logger.info("Bucket strategy not enabled")
        return BucketSummary(
            bucket_1_value=0, bucket_1_target=0,
            bucket_2_value=0, bucket_2_target=0,
            bucket_3_value=0, bucket_3_target=0,
            total_portfolio_value=0,
            bucket_1_pct=0, bucket_2_pct=0, bucket_3_pct=0,
            needs_rebalancing=False
        )
    
    # Get portfolio data
    portfolio_df = getPortfolioData(month=month, year=year)
    
    if portfolio_df.empty:
        logger.warning("No portfolio data available")
        return BucketSummary(
            bucket_1_value=0, bucket_1_target=0,
            bucket_2_value=0, bucket_2_target=0,
            bucket_3_value=0, bucket_3_target=0,
            total_portfolio_value=0,
            bucket_1_pct=0, bucket_2_pct=0, bucket_3_pct=0,
            needs_rebalancing=False
        )
    
    # Get market condition if enabled
    market_condition = None
    if config.market_trend_enabled:
        market_condition, _ = get_market_condition(config.market_trend_config)
    
    # First pass: calculate total portfolio value and classify assets
    from portfolio import get_current_price
    
    holdings_data = []
    total_value = 0.0
    
    for _, row in portfolio_df.iterrows():
        current_price = get_current_price(row['symbol'])
        current_value = row['qty'] * current_price
        total_value += current_value
        
        asset_class = classify_holding_asset_class(
            row['symbol'],
            row['sector'],
            row['name']
        )
        
        holdings_data.append({
            'row': row,
            'current_price': current_price,
            'current_value': current_value,
            'asset_class': asset_class
        })
    
    # Second pass: assign to buckets with intelligent allocation
    holdings: List[HoldingClassification] = []
    bucket_1_value = 0.0
    bucket_2_value = 0.0
    bucket_3_value = 0.0
    current_bucket_values = {
        BucketType.BUCKET_1_SAFETY: 0.0,
        BucketType.BUCKET_2_TRANSITION: 0.0,
        BucketType.BUCKET_3_GROWTH: 0.0
    }
    
    for holding_data in holdings_data:
        row = holding_data['row']
        current_price = holding_data['current_price']
        current_value = holding_data['current_value']
        asset_class = holding_data['asset_class']
        
        # Assign to bucket with current allocation context
        bucket_type, year_in_bucket = assign_holding_to_bucket(
            row['account_type'],
            asset_class,
            config,
            current_bucket_values,
            total_value
        )
        
        # Create classification
        holding = HoldingClassification(
            account_name=row['account_name'],
            account_type=row['account_type'],
            symbol=row['symbol'],
            name=row['name'],
            sector=row['sector'],
            quantity=row['qty'],
            purchase_price=row['purchase_price'],
            current_price=current_price,
            current_value=current_value,
            asset_class=asset_class,
            bucket_assignment=bucket_type,
            year_in_bucket=year_in_bucket
        )
        holdings.append(holding)
        
        # Accumulate bucket values
        if bucket_type == BucketType.BUCKET_1_SAFETY:
            bucket_1_value += current_value
            current_bucket_values[BucketType.BUCKET_1_SAFETY] += current_value
        elif bucket_type == BucketType.BUCKET_2_TRANSITION:
            bucket_2_value += current_value
            current_bucket_values[BucketType.BUCKET_2_TRANSITION] += current_value
        elif bucket_type == BucketType.BUCKET_3_GROWTH:
            bucket_3_value += current_value
            current_bucket_values[BucketType.BUCKET_3_GROWTH] += current_value
    
    # Calculate target allocations based on cash needed from portfolio
    annual_cash_needed = config.get_annual_cash_needed()
    bucket_1_target = annual_cash_needed * config.bucket_1_years
    bucket_2_target = annual_cash_needed * config.bucket_2_years
    bucket_3_target = max(0, total_value - bucket_1_target - bucket_2_target)
    
    # Calculate total outflows and inflows for logging
    total_outflows = config.annual_expenses + config.annual_healthcare + config.annual_taxes
    total_inflows = config.annual_wages + config.annual_ssi + config.annual_pension + config.annual_annuities
    
    logger.info(
        f"Bucket targets calculated: Annual cash needed=${annual_cash_needed:,.0f} "
        f"(Outflows=${total_outflows:,.0f} - Inflows=${total_inflows:,.0f})"
    )
    
    # Apply market trend adjustments if enabled
    if market_condition and market_condition != MarketCondition.UNKNOWN:
        adjustment = get_allocation_adjustment(market_condition, config.market_trend_config)
        if adjustment != 0:
            logger.info(f"Applying market trend adjustment: {adjustment:+.1f}%")
            # Adjust Bucket 2 (increase transition allocation in bear markets, decrease in bull markets)
            if adjustment < 0:
                # Negative adjustment (bear/warning): Increase Bucket 2 by reducing Bucket 3
                # This moves more assets to the safer transition bucket
                adjustment_amount = total_value * abs(adjustment) / 100
                bucket_2_target += adjustment_amount
                bucket_3_target = max(0, bucket_3_target - adjustment_amount)
                logger.info(f"Defensive: Moving ${adjustment_amount:,.0f} from Bucket 3 to Bucket 2")
            elif adjustment > 0:
                # Positive adjustment (bull): Decrease Bucket 2, increase Bucket 3
                # This allows more aggressive growth allocation
                adjustment_amount = total_value * adjustment / 100
                # Don't reduce Bucket 2 below its base target (based on cash needed)
                base_bucket_2_target = annual_cash_needed * config.bucket_2_years
                max_reduction = bucket_2_target - base_bucket_2_target
                adjustment_amount = min(adjustment_amount, max_reduction)
                if adjustment_amount > 0:
                    bucket_2_target -= adjustment_amount
                    bucket_3_target += adjustment_amount
                    logger.info(f"Aggressive: Moving ${adjustment_amount:,.0f} from Bucket 2 to Bucket 3")
    
    # Calculate percentages
    if total_value > 0:
        bucket_1_pct = (bucket_1_value / total_value) * 100
        bucket_2_pct = (bucket_2_value / total_value) * 100
        bucket_3_pct = (bucket_3_value / total_value) * 100
    else:
        bucket_1_pct = bucket_2_pct = bucket_3_pct = 0.0
    
    # Determine if rebalancing needed (>10% drift in any bucket)
    summary = BucketSummary(
        bucket_1_value=bucket_1_value,
        bucket_1_target=bucket_1_target,
        bucket_2_value=bucket_2_value,
        bucket_2_target=bucket_2_target,
        bucket_3_value=bucket_3_value,
        bucket_3_target=bucket_3_target,
        total_portfolio_value=total_value,
        bucket_1_pct=bucket_1_pct,
        bucket_2_pct=bucket_2_pct,
        bucket_3_pct=bucket_3_pct,
        needs_rebalancing=False,
        market_condition=market_condition,
        holdings=holdings
    )
    
    # Check if rebalancing needed
    drift_threshold = 10.0  # 10% drift triggers rebalancing
    for bucket_type in [BucketType.BUCKET_1_SAFETY, BucketType.BUCKET_2_TRANSITION, BucketType.BUCKET_3_GROWTH]:
        drift = abs(summary.get_bucket_drift(bucket_type))
        if drift > drift_threshold:
            summary.needs_rebalancing = True
            logger.info(f"{bucket_type.value} drift: {drift:.1f}% (threshold: {drift_threshold}%)")
            break
    
    logger.info(
        f"Bucket analysis complete: B1=${bucket_1_value:,.0f} ({bucket_1_pct:.1f}%), "
        f"B2=${bucket_2_value:,.0f} ({bucket_2_pct:.1f}%), "
        f"B3=${bucket_3_value:,.0f} ({bucket_3_pct:.1f}%), "
        f"Total=${total_value:,.0f}"
    )
    
    return summary


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def format_bucket_summary(summary: BucketSummary) -> str:
    """
    Format bucket summary as human-readable text.
    
    Args:
        summary: Bucket summary to format
        
    Returns:
        Formatted string
    """
    lines = [
        "=" * 60,
        "BUCKET STRATEGY SUMMARY",
        "=" * 60,
        f"Total Portfolio Value: ${summary.total_portfolio_value:,.2f}",
        "",
        f"Bucket 1 (Safety - Cash Reserve):",
        f"  Current: ${summary.bucket_1_value:,.2f} ({summary.bucket_1_pct:.1f}%)",
        f"  Target:  ${summary.bucket_1_target:,.2f}",
        f"  Drift:   {summary.get_bucket_drift(BucketType.BUCKET_1_SAFETY):+.1f}%",
        "",
        f"Bucket 2 (Transition - Graduated Allocation):",
        f"  Current: ${summary.bucket_2_value:,.2f} ({summary.bucket_2_pct:.1f}%)",
        f"  Target:  ${summary.bucket_2_target:,.2f}",
        f"  Drift:   {summary.get_bucket_drift(BucketType.BUCKET_2_TRANSITION):+.1f}%",
        "",
        f"Bucket 3 (Growth - 100% Stocks):",
        f"  Current: ${summary.bucket_3_value:,.2f} ({summary.bucket_3_pct:.1f}%)",
        f"  Target:  ${summary.bucket_3_target:,.2f}",
        f"  Drift:   {summary.get_bucket_drift(BucketType.BUCKET_3_GROWTH):+.1f}%",
        "",
    ]
    
    if summary.market_condition:
        lines.extend([
            f"Market Condition: {summary.market_condition.value.upper()}",
            ""
        ])
    
    lines.append(f"Rebalancing Needed: {'YES' if summary.needs_rebalancing else 'NO'}")
    lines.append("=" * 60)
    
    return "\n".join(lines)


# Made with Bob