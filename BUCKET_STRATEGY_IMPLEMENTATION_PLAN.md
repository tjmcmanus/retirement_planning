# Bucket Strategy Implementation Plan

## Document Overview

**Purpose**: Technical implementation plan for integrating the bucket strategy framework into the existing retirement planning system.

**Date**: 2026-03-07
**Status**: Planning Phase - Portfolio Integration Verified
**Version**: 1.1
**Last Updated**: 2026-03-07

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Portfolio Data Integration Verification](#portfolio-data-integration-verification) ⭐ NEW
3. [Current System Architecture](#current-system-architecture)
4. [Integration Strategy](#integration-strategy)
5. [Market Trend-Based Rebalancing](#market-trend-based-rebalancing) ⭐ NEW
6. [Data Structure Changes](#data-structure-changes)
7. [Module Design](#module-design)
8. [Configuration Schema Updates](#configuration-schema-updates)
9. [UI/UX Considerations](#uiux-considerations)
10. [Implementation Phases](#implementation-phases)
11. [Backward Compatibility](#backward-compatibility)
12. [Testing Strategy](#testing-strategy)
13. [Risk Assessment](#risk-assessment)

---

## Executive Summary

### Integration Approach

The bucket strategy will be implemented as a **complementary overlay** to the existing 6-stage life-cycle approach, not a replacement. This hybrid architecture allows users to:

1. Continue using the existing stage-based withdrawal strategy (default)
2. Optionally enable bucket strategy for enhanced sequence-of-returns risk management
3. Combine both approaches for optimal tax efficiency and risk mitigation

### Key Design Principles

- **Non-Breaking**: Existing functionality remains unchanged
- **Opt-In**: Bucket strategy is an optional enhancement
- **Composable**: Works alongside BETR Roth conversions and tax optimization
- **Transparent**: Clear visualization of bucket allocations and transitions

### Implementation Complexity

- **Estimated Effort**: 40-60 hours
- **Risk Level**: Medium (requires careful integration with existing withdrawal logic)
## Portfolio Data Integration Verification

### Overview

**Status**: ✅ VERIFIED - Portfolio data integration confirmed working correctly  
**Review Date**: 2026-03-07  
**Reviewer**: Technical Architecture Team  
**Reference**: See [PORTFOLIO_INTEGRATION_REVIEW.md](PORTFOLIO_INTEGRATION_REVIEW.md) for detailed analysis

### Data Source Confirmation

The bucket strategy implementation will use **`portfolio_data_truth.csv`** as the single source of truth for all portfolio operations. This has been verified through comprehensive code review.

**File Location**: `./portfolio_data_truth.csv`  
**Format**: CSV with monthly snapshots  
**Schema**:
```csv
month,year,account_name,account_type,symbol,name,sector,qty,purchase_price,purchase_date
```

**Key Characteristics**:
- ✅ Monthly snapshots available (Dec 2025, Jan 2026, Feb 2026 confirmed)
- ✅ Multiple account types: Traditional, Roth, Brokerage, Savings
- ✅ Multiple institutions: Schwab, Fidelity, Vanguard, PNC
- ✅ Cash positions tracked as `MF:CASH` symbol
- ✅ Complete holdings data: stocks, bonds, mutual funds, cash

### Data Loading Infrastructure

**Primary Module**: `load_data.py`

**Key Functions Verified**:

1. **`load_portfolio_truth(_file_mtime=None)`**
   - Cached function with automatic invalidation on file changes
   - Returns complete historical dataset
   - Used by all downstream portfolio operations

2. **`get_portfolio_truth_by_month(month, year)`**
   - Filters data for specific month/year
   - Returns empty DataFrame if no data exists
   - Primary data access point for bucket strategy

3. **`get_latest_portfolio_month_year()`**
   - Returns most recent (month, year) in dataset
   - Critical for fallback when current month has no data
   - Ensures bucket strategy always has data to work with

4. **`get_networth_by_month(month, year)`**
   - **PERFORMANCE OPTIMIZED**: Batch fetches all prices
   - Calculates current market values using live Yahoo Finance data
   - Returns detailed holdings and summary by account_type
   - Cached for 5 minutes (TTL=300)

### Portfolio Display Layer

**Primary Module**: `portfolio.py`

**Key Functions Verified**:

1. **`getPortfolioData(month=None, year=None)`**
   - Wrapper around `get_portfolio_truth_by_month()`
   - Handles defaults and fallbacks automatically
   - Returns: account_name, account_type, symbol, name, sector, qty, purchase_price, purchase_date

2. **`build_portfolio_display(month=None, year=None)`**
   - Builds complete display with current prices
   - Pre-fetches prices for all symbols (performance optimization)
   - Calculates: Current value, Cost Basis, Net Return, Dividends
   - Uses Parquet disk cache for instant startup

3. **`render_portfolio(month, year, done_event)`**
   - Background refresh pattern for non-blocking UI
   - Loads from cache immediately, updates in background thread
   - Automatic cache invalidation after 5 minutes

### Account Type Mapping for Bucket Strategy

The existing account type classification maps directly to bucket strategy requirements:

| Account Type | Current System | Bucket Strategy Role |
|--------------|----------------|---------------------|
| `Savings` | PNC savings account | **Bucket 1 (Safety)** - Cash only |
| `Brokerage` | Schwab/Vanguard taxable | **Buckets 1-3** - Tax-efficient placement |
| `Traditional` | Fidelity Traditional IRA | **Buckets 2-3** - Bonds preferred |
| `Roth` | Schwab Roth IRA | **Buckets 2-3** - Stocks preferred |

**Asset Class Detection** (from `sector` field):
- **Cash**: `MF:Cash`, `Money Market`
- **Bonds**: `MF:` prefix with bond keywords (Treasury, Municipal, Fixed Income)
- **Stocks**: All other securities

### Integration Points for Bucket Strategy

**✅ Ready to Use**:

1. **Data Access**:
   ```python
   # Get current portfolio holdings
   portfolio_data = getPortfolioData(month=month, year=year)
   
   # Get net worth by account type
   detailed_df, summary_df = get_networth_by_month(month, year)
   ```

2. **Account Classification**:
   ```python
   # Holdings already include account_type
   savings_holdings = portfolio_data[portfolio_data['account_type'] == 'Savings']
   brokerage_holdings = portfolio_data[portfolio_data['account_type'] == 'Brokerage']
   traditional_holdings = portfolio_data[portfolio_data['account_type'] == 'Traditional']
   roth_holdings = portfolio_data[portfolio_data['account_type'] == 'Roth']
   ```

3. **Asset Class Derivation**:
   ```python
   # Use existing classification logic from portfolio_rebalancing.py
   from portfolio_rebalancing import _classify_asset
   
   asset_class = _classify_asset(symbol, sector, name)  # Returns 'Cash', 'Bonds', or 'Stocks'
   ```

4. **Current Market Values**:
   ```python
   # Already calculated with live prices
   current_value = holding['qty'] * current_price
   cost_basis = holding['qty'] * holding['purchase_price']
   ```

### Bucket Mapping Algorithm

**Proposed Implementation**:

```python
def map_holdings_to_buckets(
    portfolio_data: pd.DataFrame,
    bucket_config: BucketStrategyConfig,
    annual_expenses: float
) -> Dict[int, List[HoldingDetail]]:
    """
    Map portfolio holdings to buckets based on account type and time horizon.
    
    Algorithm:
    1. Calculate bucket targets based on annual expenses
    2. Allocate Savings account holdings to Bucket 1 (Safety)
    3. Allocate Brokerage cash to Bucket 1 (up to target)
    4. Allocate bonds to Bucket 2 (prefer Traditional IRA)
    5. Allocate conservative stocks to Bucket 2
    6. Allocate growth stocks to Bucket 3
    
    Returns:
        Dictionary mapping bucket number (1, 2, 3) to list of holdings
    """
    bucket1_target = annual_expenses * bucket_config.bucket1_years
    bucket2_target = annual_expenses * bucket_config.bucket2_years
    
    buckets = {1: [], 2: [], 3: []}
    
    # Step 1: Allocate all Savings to Bucket 1
    savings = portfolio_data[portfolio_data['account_type'] == 'Savings']
    buckets[1].extend(savings.to_dict('records'))
    
    # Step 2: Allocate Brokerage cash to Bucket 1 (up to target)
    brokerage_cash = portfolio_data[
        (portfolio_data['account_type'] == 'Brokerage') & 
        (portfolio_data['symbol'] == 'MF:CASH')
    ]
    buckets[1].extend(brokerage_cash.to_dict('records'))
    
    # Step 3: Allocate bonds to Bucket 2 (prefer Traditional)
    bonds = portfolio_data[portfolio_data['sector'].str.contains('Bond|Treasury|Municipal', case=False, na=False)]
    buckets[2].extend(bonds.to_dict('records'))
    
    # Step 4: Allocate remaining stocks to Bucket 2 and 3 based on allocation targets
    stocks = portfolio_data[~portfolio_data['symbol'].isin(['MF:CASH']) & 
                           ~portfolio_data['sector'].str.contains('Bond|Treasury|Municipal', case=False, na=False)]
    
    # Conservative stocks (dividend-paying, large-cap) → Bucket 2
    # Growth stocks (tech, small-cap) → Bucket 3
    # (Implementation details based on sector classification)
    
    return buckets
```

### Rebalancing Integration

**Existing Infrastructure**: `portfolio_rebalancing.py` (1,407 lines)

**Key Function**: `compute_rebalance_plan(month, year, target_cash_pct, target_bonds_pct, target_stocks_pct, drift_threshold_pct)`

**Integration Approach**:

The bucket strategy will **extend** (not replace) the existing rebalancing logic:

```python
def compute_bucket_rebalance_plan(
    month: int,
    year: int,
    bucket_config: BucketStrategyConfig,
    market_condition: Optional[MarketCondition] = None,
    drift_threshold_pct: float = 5.0
) -> BucketRebalanceReport:
    """
    Compute bucket strategy rebalancing plan.
    
    This function:
    1. Maps current holdings to buckets
    2. Calculates target allocations (with market adjustments)
    3. Identifies drift and generates bucket-level actions
    4. Leverages existing rebalancing logic for execution
    """
    # Get current portfolio using verified data source
    portfolio_data = getPortfolioData(month=month, year=year)
    
    # Map holdings to buckets
    bucket_holdings = map_holdings_to_buckets(portfolio_data, bucket_config, annual_expenses)
    
    # Calculate target allocations (with optional market adjustments)
    target_allocations = calculate_bucket_targets(bucket_config, market_condition)
    
    # Generate bucket-level rebalancing actions
    bucket_actions = generate_bucket_rebalance_actions(
        bucket_holdings, target_allocations, drift_threshold_pct
    )
    
    # Convert bucket targets to asset class targets for existing rebalancing engine
    asset_targets = convert_bucket_to_asset_targets(target_allocations)
    
    # Leverage existing rebalancing logic
    asset_rebalance_plan = compute_rebalance_plan(
        month, year,
        target_cash_pct=asset_targets['Cash'],
        target_bonds_pct=asset_targets['Bonds'],
        target_stocks_pct=asset_targets['Stocks'],
        drift_threshold_pct=drift_threshold_pct
    )
    
    return BucketRebalanceReport(
        bucket_allocations=bucket_holdings,
        target_allocations=target_allocations,
        bucket_actions=bucket_actions,
        asset_rebalance_actions=asset_rebalance_plan,
        market_condition=market_condition
    )
```

**Rebalancing Strategy** (Priority Order - from existing system):
1. Rebalance inside tax-advantaged accounts (no tax event)
2. Buy using available cash in tax-advantaged accounts
3. Tax-loss harvest in Brokerage
4. Redirect contributions/dividends
5. Brokerage cash cushion top-up (10% minimum)

**Bucket Strategy Enhancement**:
- Add bucket refill logic (Bucket 3 → Bucket 2 → Bucket 1)
- Incorporate market condition adjustments
- Maintain tax efficiency through existing account-location rules

### Verification Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Data Source | ✅ Verified | `portfolio_data_truth.csv` confirmed as single source of truth |
| Data Loading | ✅ Verified | Robust loading with caching and fallbacks |
| Account Types | ✅ Verified | Direct mapping to bucket strategy requirements |
| Asset Classification | ✅ Verified | Existing logic in `portfolio_rebalancing.py` reusable |
| Current Prices | ✅ Verified | Live Yahoo Finance data with batch fetching |
| Rebalancing Logic | ✅ Verified | Sophisticated tax-efficient rebalancing ready to extend |
| Performance | ✅ Verified | Optimized with caching and background refresh |
| Fallback Handling | ✅ Verified | Graceful degradation when data unavailable |

**Conclusion**: The portfolio data integration is production-ready. The bucket strategy can be implemented as a complementary layer on top of the existing infrastructure without requiring changes to the core portfolio data handling.

---

- **Dependencies**: None (self-contained enhancement)

---

## Current System Architecture

### Core Components Analysis

#### 1. **strategy.py** (5,612 lines)
**Current Functionality**:
- 6-stage life-cycle framework (Accumulation → RMD)
- BETR-optimized Roth conversions
- Tax-efficient withdrawal sequencing
- IRMAA and ACA subsidy optimization
- RMD lookback optimization

**Key Classes**:
```python
class LifeStage:
    - applies(age, year, has_wages, has_ss) -> bool
    - calculate_strategy(year, balances, expenses) -> YearlyStrategy

class Stage1Accumulation(LifeStage)
class Stage2PrepForRetirement(LifeStage)
class Stage3EarlyRetirement(LifeStage)
class Stage4Medicare(LifeStage)
class Stage5SocialSecurity(LifeStage)
class Stage6RMD(LifeStage)

class WithdrawalStrategyEngine:
    - determine_stage() -> LifeStage
    - calculate_multi_year_strategy() -> DataFrame
```

**Key Data Structures**:
```python
@dataclass
class PortfolioBalances:
    traditional: float
    roth: float
    brokerage: float
    cash: float
    
@dataclass
class YearlyStrategy:
    year: int
    age_primary: int
    stage: str
    expenses: float
    # ... withdrawal amounts, taxes, conversions
```

## Market Trend-Based Rebalancing

### Overview

**Purpose**: Enhance bucket strategy with market condition awareness using SPY moving averages  
**Status**: Design Complete - Implementation Pending  
**Design Date**: 2026-03-07

### Market Condition System

The bucket strategy will incorporate a **4-state market condition system** based on SPY (S&P 500 ETF) moving averages to dynamically adjust allocations and rebalancing triggers.

#### Market States

| State | 10-Week MA | 50-Week MA | Description | Bucket Strategy Impact |
|-------|------------|------------|-------------|----------------------|
| **Bull Case** | ↑ Positive | ↑ Positive | Strong uptrend | Maintain aggressive allocation |
| **Warning Negative** | ↓ Negative | ↑ Positive | Short-term weakness | Reduce stocks by 10% in Bucket 2 |
| **Warning Positive** | ↑ Positive | ↓ Negative | Bear market rally | Reduce stocks by 10% in Bucket 2 |
| **Bear Case** | ↓ Negative | ↓ Negative | Confirmed downtrend | Reduce stocks by 20%, increase Bucket 1 |

**Trend Determination**:
- **Positive Trend**: Moving average slope > 0 over last 5 trading days
- **Negative Trend**: Moving average slope < 0 over last 5 trading days

### Technical Design

#### New Module: `market_trend_analysis.py`

**Purpose**: Analyze SPY moving averages and determine market conditions

**Core Data Structures**:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd

@dataclass
class MovingAverageData:
    """SPY moving average data point."""
    date: datetime
    price: float
    ma_10week: float
    ma_50week: float
    ma_10week_slope: float  # Positive = trending up
    ma_50week_slope: float  # Positive = trending up
    
    def is_10week_positive(self) -> bool:
        """Check if 10-week MA is trending positive."""
        return self.ma_10week_slope > 0
    
    def is_50week_positive(self) -> bool:
        """Check if 50-week MA is trending positive."""
        return self.ma_50week_slope > 0

@dataclass
class MarketCondition:
    """Current market condition assessment."""
    date: datetime
    state: str  # 'bull', 'warning_negative', 'warning_positive', 'bear'
    ma_10week_trending: str  # 'positive', 'negative'
    ma_50week_trending: str  # 'positive', 'negative'
    confidence: float  # 0.0-1.0 (based on slope magnitude)
    recommendation: str  # Human-readable guidance
    
    # Historical context
    days_in_current_state: int
    previous_state: Optional[str]
    state_change_date: Optional[datetime]
    
    # Raw data for display
    spy_price: float
    ma_10week_value: float
    ma_50week_value: float
    ma_10week_slope: float
    ma_50week_slope: float
    
    def is_bull_market(self) -> bool:
        """Check if in bull market."""
        return self.state == 'bull'
    
    def is_bear_market(self) -> bool:
        """Check if in bear market."""
        return self.state == 'bear'
    
    def is_warning_state(self) -> bool:
        """Check if in warning state."""
        return self.state in ['warning_negative', 'warning_positive']
    
    def should_be_defensive(self) -> bool:
        """Check if defensive positioning recommended."""
        return self.state in ['warning_negative', 'warning_positive', 'bear']

@dataclass
class MarketTrendConfig:
    """Configuration for market trend analysis."""
    ma_short_period_weeks: int = 10  # 10-week moving average
    ma_long_period_weeks: int = 50   # 50-week moving average
    slope_lookback_days: int = 5     # Days to calculate slope
    min_confidence_threshold: float = 0.7  # Minimum confidence for state change
    cache_ttl_seconds: int = 3600    # 1 hour cache
    
    # State transition thresholds
    min_days_in_state: int = 3  # Minimum days before state change
    slope_threshold: float = 0.001  # Minimum slope magnitude to consider trending
```

**Core Functions**:

```python
import yfinance as yf
import streamlit as st
from typing import Tuple

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_spy_data(lookback_weeks: int = 52) -> pd.DataFrame:
    """
    Fetch SPY price data from Yahoo Finance.
    
    Args:
        lookback_weeks: Number of weeks of historical data to fetch
        
    Returns:
        DataFrame with columns: Date (index), Close, Volume
        
    Raises:
        RuntimeError: If data fetch fails
    """
    try:
        spy = yf.Ticker("SPY")
        # Fetch weekly data for moving average calculations
        hist = spy.history(period=f"{lookback_weeks}w", interval="1wk")
        
        if hist.empty:
            raise RuntimeError("No SPY data returned from Yahoo Finance")
        
        return hist[['Close', 'Volume']]
    
    except Exception as e:
        raise RuntimeError(f"Failed to fetch SPY data: {e}")

def calculate_moving_averages(
    spy_data: pd.DataFrame,
    short_period: int = 10,
    long_period: int = 50,
    slope_lookback: int = 5
) -> pd.DataFrame:
    """
    Calculate moving averages and slopes.
    
    Args:
        spy_data: DataFrame with 'Close' column
        short_period: Short MA period in weeks
        long_period: Long MA period in weeks
        slope_lookback: Days to calculate slope
        
    Returns:
        DataFrame with MA columns and slopes
    """
    df = spy_data.copy()
    
    # Calculate moving averages
    df['ma_10week'] = df['Close'].rolling(window=short_period).mean()
    df['ma_50week'] = df['Close'].rolling(window=long_period).mean()
    
    # Calculate slopes (rate of change over lookback period)
    df['ma_10week_slope'] = df['ma_10week'].diff(slope_lookback) / slope_lookback
    df['ma_50week_slope'] = df['ma_50week'].diff(slope_lookback) / slope_lookback
    
    # Drop rows with NaN (insufficient data for MA calculation)
    df = df.dropna()
    
    return df

def determine_market_state(
    ma_10week_positive: bool,
    ma_50week_positive: bool
) -> Tuple[str, str]:
    """
    Determine market state from MA trends.
    
    Args:
        ma_10week_positive: Is 10-week MA trending positive?
        ma_50week_positive: Is 50-week MA trending positive?
        
    Returns:
        Tuple of (state, recommendation)
    """
    if ma_10week_positive and ma_50week_positive:
        return 'bull', 'Maintain aggressive allocation - both MAs trending positive'
    
    elif not ma_10week_positive and ma_50week_positive:
        return 'warning_negative', 'Consider defensive positioning - short-term weakness detected'
    
    elif ma_10week_positive and not ma_50week_positive:
        return 'warning_positive', 'Caution advised - potential bear market rally'
    
    else:  # Both negative
        return 'bear', 'Defensive positioning recommended - both MAs trending negative'

def calculate_confidence(
    ma_10week_slope: float,
    ma_50week_slope: float,
    slope_threshold: float = 0.001
) -> float:
    """
    Calculate confidence score based on slope magnitudes.
    
    Higher slopes = higher confidence in trend direction.
    
    Args:
        ma_10week_slope: 10-week MA slope
        ma_50week_slope: 50-week MA slope
        slope_threshold: Minimum slope to consider significant
        
    Returns:
        Confidence score 0.0-1.0
    """
    # Normalize slopes to 0-1 range
    slope_10_confidence = min(abs(ma_10week_slope) / slope_threshold, 1.0)
    slope_50_confidence = min(abs(ma_50week_slope) / slope_threshold, 1.0)
    
    # Average confidence from both MAs
    return (slope_10_confidence + slope_50_confidence) / 2.0

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_current_market_condition(
    config: Optional[MarketTrendConfig] = None
) -> MarketCondition:
    """
    Get current market condition based on SPY moving averages.
    
    This is the main entry point for market trend analysis.
    Results are cached for 1 hour to minimize API calls.
    
    Args:
        config: Market trend configuration (uses defaults if None)
        
    Returns:
        MarketCondition object with current state and analysis
        
    Raises:
        RuntimeError: If SPY data cannot be fetched
    """
    if config is None:
        config = MarketTrendConfig()
    
    # Fetch SPY data
    spy_data = fetch_spy_data(lookback_weeks=config.ma_long_period_weeks + 10)
    
    # Calculate moving averages
    ma_data = calculate_moving_averages(
        spy_data,
        short_period=config.ma_short_period_weeks,
        long_period=config.ma_long_period_weeks,
        slope_lookback=config.slope_lookback_days
    )
    
    # Get most recent data point
    latest = ma_data.iloc[-1]
    
    # Determine trends
    ma_10week_positive = latest['ma_10week_slope'] > config.slope_threshold
    ma_50week_positive = latest['ma_50week_slope'] > config.slope_threshold
    
    # Determine market state
    state, recommendation = determine_market_state(ma_10week_positive, ma_50week_positive)
    
    # Calculate confidence
    confidence = calculate_confidence(
        latest['ma_10week_slope'],
        latest['ma_50week_slope'],
        config.slope_threshold
    )
    
    # Get historical context (simplified - would need state persistence)
    # For now, assume this is the first observation
    days_in_state = 1
    previous_state = None
    state_change_date = None
    
    return MarketCondition(
        date=latest.name.to_pydatetime(),
        state=state,
        ma_10week_trending='positive' if ma_10week_positive else 'negative',
        ma_50week_trending='positive' if ma_50week_positive else 'negative',
        confidence=confidence,
        recommendation=recommendation,
        days_in_current_state=days_in_state,
        previous_state=previous_state,
        state_change_date=state_change_date,
        spy_price=latest['Close'],
        ma_10week_value=latest['ma_10week'],
        ma_50week_value=latest['ma_50week'],
        ma_10week_slope=latest['ma_10week_slope'],
        ma_50week_slope=latest['ma_50week_slope']
    )
```

### Integration with Bucket Strategy

#### Allocation Adjustments by Market State

**Base Allocations** (from bucket strategy config):
- Bucket 1 (Safety): 100% Cash
- Bucket 2 (Transition): 10% Cash, 50% Bonds, 40% Stocks
- Bucket 3 (Growth): 20% Bonds, 80% Stocks

**Market-Adjusted Allocations**:

```python
def adjust_bucket_allocation_for_market(
    base_allocation: dict,
    bucket_num: int,
    market_condition: MarketCondition,
    adjustment_mode: str = "moderate"
) -> dict:
    """
    Adjust bucket allocations based on market conditions.
    
    Args:
        base_allocation: Base allocation dict {'Cash': %, 'Bonds': %, 'Stocks': %}
        bucket_num: Bucket number (1, 2, or 3)
        market_condition: Current market condition
        adjustment_mode: 'conservative', 'moderate', or 'aggressive'
        
    Returns:
        Adjusted allocation dict
    """
    adjusted = base_allocation.copy()
    
    # Bucket 1 (Safety) never changes - always 100% cash
    if bucket_num == 1:
        return adjusted
    
    # Define adjustment magnitudes by mode
    adjustments = {
        'conservative': {'warning': -15.0, 'bear': -30.0},
        'moderate':     {'warning': -10.0, 'bear': -20.0},
        'aggressive':   {'warning': -5.0,  'bear': -10.0}
    }
    
    mode_adjustments = adjustments.get(adjustment_mode, adjustments['moderate'])
    
    # Apply adjustments based on market state
    if market_condition.state == 'bull':
        # No adjustment in bull market
        return adjusted
    
    elif market_condition.is_warning_state():
        # Warning state: reduce stocks, increase bonds
        stock_reduction = mode_adjustments['warning']
        adjusted['Stocks'] = max(0, adjusted.get('Stocks', 0) + stock_reduction)
        adjusted['Bonds'] = adjusted.get('Bonds', 0) - stock_reduction
        
    elif market_condition.state == 'bear':
        # Bear market: significant reduction in stocks
        stock_reduction = mode_adjustments['bear']
        adjusted['Stocks'] = max(0, adjusted.get('Stocks', 0) + stock_reduction)
        
        # Split reduction between bonds and cash
        if bucket_num == 2:
            # Bucket 2: Increase both bonds and cash
            adjusted['Bonds'] = adjusted.get('Bonds', 0) - (stock_reduction * 0.6)
            adjusted['Cash'] = adjusted.get('Cash', 0) - (stock_reduction * 0.4)
        else:
            # Bucket 3: Increase bonds
            adjusted['Bonds'] = adjusted.get('Bonds', 0) - stock_reduction
    
    # Ensure allocations sum to 100%
    total = sum(adjusted.values())
    if total != 100.0:
        # Normalize
        adjusted = {k: (v / total * 100.0) for k, v in adjusted.items()}
    
    return adjusted
```

#### Rebalancing Trigger Enhancement

```python
def should_rebalance_buckets(
    current_allocation: BucketAllocation,
    market_condition: MarketCondition,
    config: BucketStrategyConfig,
    drift_threshold_pct: float = 5.0
) -> Tuple[bool, str]:
    """
    Determine if bucket rebalancing is needed.
    
    Considers both drift-based and market-condition-based triggers.
    
    Args:
        current_allocation: Current bucket allocation
        market_condition: Current market condition
        config: Bucket strategy configuration
        drift_threshold_pct: Drift threshold percentage
        
    Returns:
        Tuple of (should_rebalance, reason)
    """
    # Standard drift-based trigger
    if current_allocation.needs_rebalancing:
        return True, f"Drift threshold of {drift_threshold_pct}% exceeded"
    
    # Market condition change trigger
    if market_condition.state_change_date:
        days_since_change = (datetime.now() - market_condition.state_change_date).days
        if days_since_change <= 7:  # Recent state change (within 1 week)
            return True, f"Market condition changed to {market_condition.state} {days_since_change} days ago"
    
    # Defensive trigger in bear market
    if market_condition.state == 'bear' and config.market_trend_adjustment['enabled']:
        # Check if current stock allocation exceeds adjusted target
        bucket2_current_stocks = current_allocation.bucket2_allocation.get('Stocks', 0)
        bucket2_target_stocks = config.bucket2_stock_allocation
        
        # In bear market, target should be reduced
        adjusted_target = bucket2_target_stocks - config.market_trend_adjustment['bear_stock_shift']
        
        if bucket2_current_stocks > adjusted_target + drift_threshold_pct:
            return True, "Bear market defensive rebalancing needed"
    
    # Warning state trigger (optional, based on config)
    if market_condition.is_warning_state() and config.market_trend_adjustment.get('warning_triggers_rebalance', False):
        return True, f"Warning state detected: {market_condition.recommendation}"
    
    return False, "No rebalancing needed"
```

### Configuration Schema

**Addition to `config.py`**:

```python
DEFAULT_CONFIG = {
    # ... existing sections ...
    
    "bucket_strategy": {
        "enabled": False,
        "bucket1_years": 2,
        "bucket2_years": 8,
        "bucket2_stock_allocation": 40.0,
        "bucket3_stock_allocation": 80.0,
        "rebalance_threshold_pct": 5.0,
        "annual_refill_enabled": True,
        "risk_profile": "moderate",
        
        # NEW: Market trend-based rebalancing
        "market_trend_adjustment": {
            "enabled": True,
            "ma_short_period_weeks": 10,
            "ma_long_period_weeks": 50,
            "slope_lookback_days": 5,
            "adjustment_mode": "moderate",  # conservative, moderate, aggressive
            "cache_ttl_hours": 1,
            "warning_triggers_rebalance": False,  # Only rebalance on drift or bear market
            
            # Allocation shifts by market state (percentage points)
            "bull_stock_shift": 0.0,           # No change in bull market
            "warning_stock_shift": -10.0,      # Reduce stocks by 10% in warning
            "bear_stock_shift": -20.0,         # Reduce stocks by 20% in bear
            "bear_cash_increase_months": 6,    # Add 6 months to Bucket 1 in bear market
            
            # Advanced settings
            "min_confidence_threshold": 0.7,   # Minimum confidence for state change
            "min_days_in_state": 3,            # Minimum days before state change
            "slope_threshold": 0.001,          # Minimum slope to consider trending
        }
    }
}
```

**Validation Function**:

```python
def validate_market_trend_config(config: dict) -> List[str]:
    """Validate market trend configuration."""
    errors = []
    
    mt_config = config.get("bucket_strategy", {}).get("market_trend_adjustment", {})
    
    # Validate MA periods
    short_period = mt_config.get("ma_short_period_weeks", 10)
    long_period = mt_config.get("ma_long_period_weeks", 50)
    
    if short_period >= long_period:
        errors.append("Short MA period must be less than long MA period")
    
    if short_period < 5 or short_period > 20:
        errors.append("Short MA period should be between 5-20 weeks")
    
    if long_period < 30 or long_period > 100:
        errors.append("Long MA period should be between 30-100 weeks")
    
    # Validate adjustment mode
    mode = mt_config.get("adjustment_mode", "moderate")
    if mode not in ['conservative', 'moderate', 'aggressive']:
        errors.append("Adjustment mode must be 'conservative', 'moderate', or 'aggressive'")
    
    # Validate stock shifts
    warning_shift = mt_config.get("warning_stock_shift", -10.0)
    bear_shift = mt_config.get("bear_stock_shift", -20.0)
    
    if warning_shift > 0:
        errors.append("Warning stock shift should be negative (reduction)")
    
    if bear_shift > 0:
        errors.append("Bear stock shift should be negative (reduction)")
    
    if abs(bear_shift) <= abs(warning_shift):
        errors.append("Bear market shift should be more defensive than warning shift")
    
    return errors
```

### UI Integration

#### Dashboard Widget

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 Market Condition Analysis                                 │
│                                                              │
│ Current State: ⚠️ Warning Negative (Bull Market Weakness)    │
│                                                              │
│ SPY Price: $450.25                                           │
│ 10-Week MA: $455.30 ↓ Trending Down (-0.15% per day)        │
│ 50-Week MA: $440.50 ↑ Trending Up (+0.08% per day)          │
│                                                              │
│ Confidence: ████████░░ 80%                                   │
│                                                              │
│ Recommendation: Consider defensive positioning               │
│ Short-term weakness detected while long-term trend positive  │
│                                                              │
│ Last State Change: 3 days ago (Bull → Warning Negative)     │
│                                                              │
│ Impact on Bucket Strategy:                                   │
│ • Bucket 2 stocks reduced from 40% to 30%                   │
│ • Bucket 3 stocks reduced from 80% to 75%                   │
│                                                              │
│ [View Historical Chart] [Refresh Market Data] [Override]    │
└─────────────────────────────────────────────────────────────┘
```

#### Strategy Page Enhancement

**New Section on Bucket Strategy Tab**:

```python
# In pages/5_strategy.py

def render_market_condition_section():
    """Render market condition analysis section."""
    st.subheader("📊 Market Condition Analysis")
    
    # Get current market condition
    try:
        market_condition = get_current_market_condition()
        
        # Display state with appropriate icon
        state_icons = {
            'bull': '🟢',
            'warning_negative': '🟡',
            'warning_positive': '🟡',
            'bear': '🔴'
        }
        
        icon = state_icons.get(market_condition.state, '⚪')
        st.markdown(f"### {icon} {market_condition.state.replace('_', ' ').title()}")
        
        # Display metrics in columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "SPY Price",
                f"${market_condition.spy_price:.2f}",
                delta=None
            )
        
        with col2:
            trend_10 = "↑" if market_condition.ma_10week_trending == 'positive' else "↓"
            st.metric(
                "10-Week MA",
                f"${market_condition.ma_10week_value:.2f}",
                delta=f"{trend_10} {market_condition.ma_10week_slope:.4f}"
            )
        
        with col3:
            trend_50 = "↑" if market_condition.ma_50week_trending == 'positive' else "↓"
            st.metric(
                "50-Week MA",
                f"${market_condition.ma_50week_value:.2f}",
                delta=f"{trend_50} {market_condition.ma_50week_slope:.4f}"
            )
        
        # Display recommendation
        st.info(f"**Recommendation**: {market_condition.recommendation}")
        
        # Display confidence
        st.progress(market_condition.confidence, text=f"Confidence: {market_condition.confidence:.0%}")
        
        # Display impact on bucket allocations
        if market_condition.should_be_defensive():
            st.warning("**Impact on Bucket Strategy**: Defensive adjustments applied to allocations")
            
            # Show adjusted allocations
            with st.expander("View Adjusted Allocations"):
                # Display comparison table
                st.markdown("Allocation adjustments based on current market condition:")
                # ... render comparison table ...
        
    except Exception as e:
        st.error(f"Unable to fetch market condition: {e}")
        st.info("Using base bucket allocations without market adjustments")
```

### Performance Considerations

**Caching Strategy**:
- Market condition cached for 1 hour (configurable)
- SPY data cached separately for 1 hour
- Historical state transitions stored in session state
- Manual refresh button available for users

**API Call Optimization**:
- Single SPY data fetch per hour (max 24 calls/day)
- Batch calculation of all moving averages
- Reuse existing yfinance infrastructure

**Error Handling**:
- Graceful degradation if Yahoo Finance unavailable
- Use last known market condition from cache
- Display warning to user but continue with base allocations
- Log errors for monitoring

### Testing Strategy

**Unit Tests**:
```python
def test_market_state_determination():
    """Test market state logic."""
    assert determine_market_state(True, True)[0] == 'bull'
    assert determine_market_state(False, True)[0] == 'warning_negative'
    assert determine_market_state(True, False)[0] == 'warning_positive'
    assert determine_market_state(False, False)[0] == 'bear'

def test_allocation_adjustments():
    """Test allocation adjustment logic."""
    base = {'Cash': 10, 'Bonds': 50, 'Stocks': 40}
    
    # Bull market - no change
    bull_condition = MarketCondition(state='bull', ...)
    adjusted = adjust_bucket_allocation_for_market(base, 2, bull_condition)
    assert adjusted == base
    
    # Bear market - reduce stocks
    bear_condition = MarketCondition(state='bear', ...)
    adjusted = adjust_bucket_allocation_for_market(base, 2, bear_condition, 'moderate')
    assert adjusted['Stocks'] < base['Stocks']
    assert sum(adjusted.values()) == 100.0

def test_confidence_calculation():
    """Test confidence scoring."""
    # Strong trends = high confidence
    confidence = calculate_confidence(0.01, 0.01, 0.001)
    assert confidence > 0.9
    
    # Weak trends = low confidence
    confidence = calculate_confidence(0.0001, 0.0001, 0.001)
    assert confidence < 0.2
```

**Integration Tests**:
- Historical backtesting with known market conditions (2008, 2020, 2022)
- Verify state transitions match expected behavior
- Test allocation adjustments across all market states
- Validate rebalancing trigger logic

**Performance Tests**:
- Measure API call frequency
- Verify cache effectiveness
- Test UI responsiveness with market data loading

### Implementation Priority

**Phase 1** (Week 1):
- [ ] Create `market_trend_analysis.py` module
- [ ] Implement SPY data fetching
- [ ] Calculate moving averages and slopes
- [ ] Determine market states
- [ ] Write unit tests

**Phase 2** (Week 2):
- [ ] Integrate with bucket strategy configuration
- [ ] Implement allocation adjustment logic
- [ ] Add rebalancing trigger enhancements
- [ ] Write integration tests

**Phase 3** (Week 3):
- [ ] Add dashboard market condition widget
- [ ] Enhance bucket strategy page
- [ ] Add configuration UI
- [ ] Implement manual refresh controls

**Phase 4** (Week 4):
- [ ] Historical backtesting
- [ ] Performance optimization
- [ ] Error handling refinement
- [ ] User acceptance testing

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Yahoo Finance API failures | Cache last known state, show warning, continue with base allocations |
| False signals from MA crossovers | Require sustained trends (min 3 days), confidence scoring |
| Over-trading | Minimum holding period, transaction cost awareness |
| User confusion | Clear UI explanations, educational tooltips, override option |
| Performance impact | Aggressive caching (1 hour TTL), background refresh |

---

#### 2. **portfolio_rebalancing.py** (1,407 lines)
**Current Functionality**:
- Asset class allocation (Cash/Bonds/Stocks)
- Drift detection and rebalancing recommendations
- Tax-efficient rebalancing (tax-advantaged first, then TLH)
- Account location optimization

**Key Functions**:
```python
def compute_rebalance_plan(
    target_allocation: dict,  # {'Cash': 10, 'Bonds': 30, 'Stocks': 60}
    drift_threshold: float = 5.0
) -> RebalanceReport
```

**Asset Classification**:
- Cash: MF:CASH, money market
- Bonds: Fixed income, treasuries, municipals
- Stocks: Everything else

#### 3. **withdrawal_strategy.py** (10 lines)
**Current State**: Placeholder module with no implementation

**Opportunity**: This is the ideal location for bucket strategy implementation

#### 4. **config.py** (383 lines)
**Current Configuration Structure**:
```python
DEFAULT_CONFIG = {
    "personal_info": {...},
    "financial_assumptions": {
        "expected_annual_expenses": 50000,
        "expense_inflation_rate": 3.0,
        "expected_rate_of_return": 6.0,
        "years_of_expenses_in_cash": 4,
        "accumulation_cash_buffer_months": 6,
    },
    "income": {...},
    "social_security": {...},
    "healthcare": {...},
    "tax_strategy": {...},
    "charitable_giving": {...},
    "rebalancing_preferences": {...}
}
```

#### 5. **planning_app.py** & **pages/5_strategy.py**
**Current UI Structure**:
- Multi-page Streamlit app with horizontal navigation
- Strategy page has 4 tabs:
  - Long-Term Plan (multi-year table)
  - Monthly Calendar (execution timeline)
  - Account Balances (projected balances)
  - Visualizations (charts)

---

## Integration Strategy

### Hybrid Architecture Design

The bucket strategy will integrate with the existing system through a **strategy composition pattern**:

```
┌─────────────────────────────────────────────────────────────┐
│                   WithdrawalStrategyEngine                   │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Life-Cycle Stage Determination             │    │
│  │  (Stage1-6: Accumulation → RMD)                    │    │
│  └────────────────────────────────────────────────────┘    │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Bucket Strategy Layer (Optional)           │    │
│  │  • Bucket allocation calculation                   │    │
│  │  • Time-horizon-based asset allocation             │    │
│  │  • Sequence risk mitigation                        │    │
│  └────────────────────────────────────────────────────┘    │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Tax Optimization Layer                     │    │
│  │  • BETR Roth conversions                           │    │
│  │  • IRMAA optimization                              │    │
│  │  • ACA subsidy optimization                        │    │
│  └────────────────────────────────────────────────────┘    │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Withdrawal Execution                       │    │
│  │  • Account sequencing                              │    │
│  │  • Tax-efficient withdrawals                       │    │
│  │  • Buffer replenishment                            │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Integration Points

#### 1. **Portfolio Allocation Integration**
- Bucket strategy provides **target allocations** by time horizon
- Existing `portfolio_rebalancing.py` executes the rebalancing
- No changes to rebalancing logic required

#### 2. **Withdrawal Sequencing Integration**
- Bucket strategy determines **which bucket** to draw from
- Existing stage logic determines **which account type** (Traditional/Roth/Brokerage)
- Combined logic: "Draw from Bucket 1 (Safety) using Traditional IRA"

#### 3. **Cash Buffer Integration**
- Existing: `years_of_expenses_in_cash` (single value)
- Bucket strategy: Bucket 1 = 2 years, Bucket 2 = 8 years
- Integration: Bucket 1 size becomes the new cash buffer target

#### 4. **Rebalancing Trigger Integration**
- Existing: Annual rebalancing in `calculate_strategy()`
- Bucket strategy: Annual bucket refill from Bucket 3 → Bucket 2 → Bucket 1
- Integration: Add bucket refill logic to annual rebalancing cycle

---

## Data Structure Changes

### New Data Structures

#### 1. **BucketAllocation** (new dataclass)
```python
@dataclass
class BucketAllocation:
    """Represents the bucket strategy allocation for a given year."""
    year: int
    
    # Bucket 1: Safety (Years 1-2)
    bucket1_target: float      # Target amount (2 years expenses)
    bucket1_actual: float      # Current amount
    bucket1_allocation: dict   # {'Cash': 100.0}
    
    # Bucket 2: Transition (Years 3-10)
    bucket2_target: float      # Target amount (8 years expenses)
    bucket2_actual: float      # Current amount
    bucket2_allocation: dict   # {'Cash': 10%, 'Bonds': 50%, 'Stocks': 40%}
    
    # Bucket 3: Growth (Years 11+)
    bucket3_target: float      # Target amount (remaining portfolio)
    bucket3_actual: float      # Current amount
    bucket3_allocation: dict   # {'Stocks': 80%, 'Bonds': 20%}
    
    # Rebalancing needs
    needs_rebalancing: bool
    rebalancing_actions: List[BucketRebalanceAction]
```

#### 2. **BucketRebalanceAction** (new dataclass)
```python
@dataclass
class BucketRebalanceAction:
    """Represents a single bucket rebalancing action."""
    action_type: str  # 'refill', 'rebalance_within', 'sell_for_expenses'
    from_bucket: int  # 1, 2, or 3
    to_bucket: int    # 1, 2, or 3
    amount: float
    asset_class: str  # 'Cash', 'Bonds', 'Stocks'
    account_type: str # 'Traditional', 'Roth', 'Brokerage'
    tax_impact: str
    rationale: str
```

#### 3. **BucketStrategyConfig** (new dataclass)
```python
@dataclass
class BucketStrategyConfig:
    """Configuration for bucket strategy."""
    enabled: bool = False
    
    # Bucket sizing
    bucket1_years: int = 2
    bucket2_years: int = 8
    
    # Asset allocation progression
    bucket2_stock_allocation: float = 0.4  # 40% stocks in transition bucket
    bucket3_stock_allocation: float = 0.8  # 80% stocks in growth bucket
    
    # Rebalancing triggers
    rebalance_threshold_pct: float = 5.0
    annual_refill_enabled: bool = True
    
    # Risk adjustments
    risk_profile: str = "moderate"  # conservative, moderate, aggressive
    market_condition_adjustment: bool = True
```

### Enhanced Existing Structures

#### 1. **YearlyStrategy** (enhanced)
```python
@dataclass
class YearlyStrategy:
    # ... existing fields ...
    
    # New bucket strategy fields
    bucket_allocation: Optional[BucketAllocation] = None
    bucket_withdrawals: Dict[int, float] = field(default_factory=dict)  # {bucket_num: amount}
    bucket_refills: Dict[int, float] = field(default_factory=dict)      # {bucket_num: amount}
```

#### 2. **PortfolioBalances** (enhanced)
```python
@dataclass
class PortfolioBalances:
    # ... existing fields ...
    
    # New bucket-aware fields
    bucket1_balance: float = 0.0
    bucket2_balance: float = 0.0
    bucket3_balance: float = 0.0
    
    def get_bucket_balance(self, bucket_num: int) -> float:
        """Get balance for a specific bucket."""
        return getattr(self, f'bucket{bucket_num}_balance', 0.0)
```

---

## Module Design

### New Modules

#### 1. **bucket_strategy.py** (new module)
```python
"""
Bucket Strategy Implementation

Implements the 3-bucket retirement withdrawal strategy:
- Bucket 1: Safety (2 years expenses, 100% cash/bonds)
- Bucket 2: Transition (8 years expenses, 40% stocks, 60% bonds/cash)
- Bucket 3: Growth (remaining portfolio, 80% stocks, 20% bonds)
"""

class BucketStrategyEngine:
    """Main engine for bucket strategy calculations."""
    
    def __init__(self, config: BucketStrategyConfig):
        self.config = config
    
    def calculate_bucket_targets(self, annual_expenses: float, 
                               total_portfolio: float) -> BucketAllocation:
        """Calculate target amounts for each bucket."""
        
    def determine_withdrawal_bucket(self, expenses: float, 
                                  allocation: BucketAllocation) -> int:
        """Determine which bucket to withdraw from."""
        
    def calculate_annual_refill(self, allocation: BucketAllocation) -> List[BucketRebalanceAction]:
        """Calculate bucket refill actions for annual rebalancing."""
        
    def optimize_bucket_allocation(self, current_allocation: dict, 
                                 target_allocation: dict, 
                                 market_conditions: dict) -> dict:
        """Optimize bucket allocation based on market conditions."""

def integrate_with_life_stage(stage: LifeStage, 
                            bucket_config: BucketStrategyConfig) -> LifeStage:
    """Wrap a life stage with bucket strategy logic."""
```

#### 2. **bucket_rebalancing.py** (new module)
```python
"""
Bucket-Aware Rebalancing

Extends the existing portfolio rebalancing logic to work with bucket allocations.
"""

def compute_bucket_rebalance_plan(
    current_allocation: BucketAllocation,
    target_allocation: BucketAllocation,
    portfolio_data: pd.DataFrame
) -> List[BucketRebalanceAction]:
    """Compute rebalancing actions to achieve target bucket allocation."""

def execute_bucket_refill(
    from_bucket: int,
    to_bucket: int, 
    amount: float,
    portfolio_balances: PortfolioBalances
) -> List[BucketRebalanceAction]:
    """Execute bucket refill (e.g., Bucket 3 → Bucket 2)."""
```

### Enhanced Existing Modules

#### 1. **strategy.py** (enhancements)
```python
# New function to integrate bucket strategy
def create_bucket_aware_strategy_engine(
    bucket_config: BucketStrategyConfig
) -> WithdrawalStrategyEngine:
    """Create a withdrawal strategy engine with bucket strategy integration."""

# Enhanced WithdrawalStrategyEngine
class WithdrawalStrategyEngine:
    def __init__(self, bucket_config: Optional[BucketStrategyConfig] = None):
        self.bucket_config = bucket_config
        self.bucket_engine = BucketStrategyEngine(bucket_config) if bucket_config else None
    
    def calculate_multi_year_strategy(self, ...) -> pd.DataFrame:
        # Enhanced to include bucket calculations
        for year in years:
            stage_strategy = stage.calculate_strategy(...)
            
            if self.bucket_engine:
                bucket_allocation = self.bucket_engine.calculate_bucket_targets(...)
                stage_strategy.bucket_allocation = bucket_allocation
                
                # Modify withdrawal logic based on bucket strategy
                bucket_withdrawals = self.bucket_engine.determine_withdrawal_bucket(...)
                stage_strategy.bucket_withdrawals = bucket_withdrawals
```

#### 2. **portfolio_rebalancing.py** (enhancements)
```python
# Enhanced to support bucket-aware rebalancing
def compute_rebalance_plan(
    target_allocation: dict,
    drift_threshold: float = 5.0,
    bucket_allocation: Optional[BucketAllocation] = None  # New parameter
) -> RebalanceReport:
    """Enhanced to consider bucket constraints."""
```

---

## Configuration Schema Updates

**Updated**: 2026-03-07 - Added market trend-based rebalancing parameters

### New Configuration Section

```python
# Addition to DEFAULT_CONFIG in config.py
DEFAULT_CONFIG = {
    # ... existing sections ...
    
    "bucket_strategy": {
        "enabled": False,
        "bucket1_years": 2,
        "bucket2_years": 8,
        "bucket2_stock_allocation": 40.0,  # 40% stocks in transition bucket
        "bucket3_stock_allocation": 80.0,  # 80% stocks in growth bucket
        "rebalance_threshold_pct": 5.0,
        "annual_refill_enabled": True,
        "risk_profile": "moderate",  # conservative, moderate, aggressive
        
        # Advanced settings
        "bucket1_max_stock_allocation": 0.0,   # Safety bucket: no stocks
        "bucket2_min_bond_allocation": 40.0,   # Transition: min 40% bonds
        "bucket3_min_stock_allocation": 60.0,  # Growth: min 60% stocks
        
        # Rebalancing preferences
        "refill_frequency": "annual",  # annual, semi-annual, quarterly
        "rebalance_trigger": "drift",  # drift, calendar, market_condition
        "tax_efficiency_priority": True,
        
        # ⭐ NEW: Market trend-based rebalancing
        "market_trend_adjustment": {
            "enabled": True,
            "ma_short_period_weeks": 10,
            "ma_long_period_weeks": 50,
            "slope_lookback_days": 5,
            "adjustment_mode": "moderate",
            "cache_ttl_hours": 1,
            "warning_triggers_rebalance": False,
            "bull_stock_shift": 0.0,
            "warning_stock_shift": -10.0,
            "bear_stock_shift": -20.0,
            "bear_cash_increase_months": 6,
            "min_confidence_threshold": 0.7,
            "min_days_in_state": 3,
            "slope_threshold": 0.001,
            "show_market_widget": True,
            "show_historical_chart": True,
            "allow_manual_override": True,
        }
    }
}
```

### Configuration Validation

```python
# New validation functions in config.py
def validate_bucket_strategy_config(config: dict) -> List[str]:
    """Validate bucket strategy configuration and return any errors."""
    errors = []
    
    bucket_config = config.get("bucket_strategy", {})
    
    # Validate bucket sizing
    bucket1_years = bucket_config.get("bucket1_years", 2)
    bucket2_years = bucket_config.get("bucket2_years", 8)
    
    if bucket1_years < 1 or bucket1_years > 5:
        errors.append("Bucket 1 must be between 1-5 years")
    
    if bucket2_years < 3 or bucket2_years > 15:
        errors.append("Bucket 2 must be between 3-15 years")
    
    # Validate allocations
    bucket2_stocks = bucket_config.get("bucket2_stock_allocation", 40.0)
    bucket3_stocks = bucket_config.get("bucket3_stock_allocation", 80.0)
    
    if not (0 <= bucket2_stocks <= 100):
        errors.append("Bucket 2 stock allocation must be 0-100%")
    
    if not (0 <= bucket3_stocks <= 100):
        errors.append("Bucket 3 stock allocation must be 0-100%")
    
    if bucket2_stocks >= bucket3_stocks:
        errors.append("Bucket 3 should have higher stock allocation than Bucket 2")
    
    # ⭐ NEW: Validate market trend configuration
    mt_config = bucket_config.get("market_trend_adjustment", {})
    if mt_config.get("enabled", False):
        mt_errors = validate_market_trend_config(config)
        errors.extend(mt_errors)
    
    return errors

def validate_market_trend_config(config: dict) -> List[str]:
    """Validate market trend configuration (see Market Trend-Based Rebalancing section for full implementation)."""
    errors = []
    mt_config = config.get("bucket_strategy", {}).get("market_trend_adjustment", {})
    
    # Validate MA periods
    short_period = mt_config.get("ma_short_period_weeks", 10)
    long_period = mt_config.get("ma_long_period_weeks", 50)
    
    if short_period >= long_period:
        errors.append("Short MA period must be less than long MA period")
    if short_period < 5 or short_period > 20:
        errors.append("Short MA period should be between 5-20 weeks")
    if long_period < 30 or long_period > 100:
        errors.append("Long MA period should be between 30-100 weeks")
    
    # Validate stock shifts
    warning_shift = mt_config.get("warning_stock_shift", -10.0)
    bear_shift = mt_config.get("bear_stock_shift", -20.0)
    
    if warning_shift > 0 or bear_shift > 0:
        errors.append("Stock shifts should be negative (reductions)")
    if abs(bear_shift) <= abs(warning_shift):
        errors.append("Bear market shift should be more defensive than warning shift")
    
    return errors
```

---

## UI/UX Considerations

### Strategy Page Enhancements

#### 1. **New Tab: "🪣 Bucket Strategy"**
```python
# Addition to pages/5_strategy.py
def render_bucket_strategy_tab():
    """Render the bucket strategy configuration and visualization tab."""
    
    st.subheader("🪣 Bucket Strategy Configuration")
    
    # Configuration section
    col1, col2 = st.columns(2)
    
    with col1:
        bucket_enabled = st.checkbox(
            "Enable Bucket Strategy",
            value=st.session_state.get("bucket_strategy_enabled", False),
            help="Overlay bucket strategy on top of life-cycle stages"
        )
        
        if bucket_enabled:
            bucket1_years = st.slider("Safety Bucket (Years)", 1, 5, 2)
            bucket2_years = st.slider("Transition Bucket (Years)", 3, 15, 8)
            
    with col2:
        if bucket_enabled:
            bucket2_stocks = st.slider("Transition Bucket Stock %", 0, 80, 40)
            bucket3_stocks = st.slider("Growth Bucket Stock %", 40, 100, 80)
    
    if bucket_enabled:
        # Bucket allocation visualization
        render_bucket_allocation_chart()
        
        # Bucket balance table
        render_bucket_balance_table()
        
        # Bucket rebalancing actions
        render_bucket_rebalancing_actions()
```

#### 2. **Enhanced Visualizations**
```python
def render_bucket_allocation_chart():
    """Render bucket allocation over time as a stacked area chart."""
    
    # Create stacked area chart showing bucket balances over time
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=years, y=bucket1_balances,
        mode='lines', stackgroup='one',
        name='Bucket 1 (Safety)', fill='tonexty',
        line=dict(color='#2E8B57')  # Sea green
    ))
    
    fig.add_trace(go.Scatter(
        x=years, y=bucket2_balances,
        mode='lines', stackgroup='one',
        name='Bucket 2 (Transition)', fill='tonexty',
        line=dict(color='#4682B4')  # Steel blue
    ))
    
    fig.add_trace(go.Scatter(
        x=years, y=bucket3_balances,
        mode='lines', stackgroup='one',
        name='Bucket 3 (Growth)', fill='tonexty',
        line=dict(color='#B8860B')  # Dark goldenrod
    ))
    
    fig.update_layout(
        title="Bucket Strategy Allocation Over Time",
        xaxis_title="Year",
        yaxis_title="Portfolio Value ($)",
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
```

#### 3. **Bucket Balance Table**
```python
def render_bucket_balance_table():
    """Render detailed bucket balance and allocation table."""
    
    bucket_df = pd.DataFrame({
        'Bucket': ['Bucket 1 (Safety)', 'Bucket 2 (Transition)', 'Bucket 3 (Growth)'],
        'Time Horizon': ['Years 1-2', 'Years 3-10', 'Years 11+'],
        'Target Amount': [f"${bucket1_target:,.0f}", f"${bucket2_target:,.0f}", f"${bucket3_target:,.0f}"],
        'Current Amount': [f"${bucket1_actual:,.0f}", f"${bucket2_actual:,.0f}", f"${bucket3_actual:,.0f}"],
        'Stock %': ['0%', f'{bucket2_stocks}%', f'{bucket3_stocks}%'],
        'Bond %': ['60%', f'{100-bucket2_stocks-10}%', f'{100-bucket3_stocks}%'],
        'Cash %': ['40%', '10%', '0%'],
        'Status': [bucket1_status, bucket2_status, bucket3_status]
    })
    
    st.dataframe(
        bucket_df,
        use_container_width=True,
        column_config={
            'Status': st.column_config.TextColumn(
                help="✅ On target, ⚠️ Needs rebalancing, 🔄 Refill needed"
            )
        }
    )
```

### Configuration Page Integration

#### 1. **New Section: "Bucket Strategy"**
```python
# Addition to pages/2_configuration.py
def render_bucket_strategy_section():
    """Render bucket strategy configuration section."""
    
    st.subheader("🪣 Bucket Strategy")
    
    with st.expander("What is the Bucket Strategy?", expanded=False):
        st.markdown("""
        The bucket strategy divides your portfolio into three time-based buckets:
        
        - **Bucket 1 (Safety)**: 2 years of expenses in cash/bonds for immediate needs
        - **Bucket 2 (Transition)**: 8 years of expenses in balanced allocation
        - **Bucket 3 (Growth)**: Remaining portfolio in growth investments
        
        This approach helps manage sequence-of-returns risk while maintaining growth potential.
        """)
    
    bucket_enabled = st.checkbox(
        "Enable Bucket Strategy",
        value=config_mgr.get("bucket_strategy", "enabled", False),
        help="Overlay bucket strategy on your withdrawal plan"
    )
    
    if bucket_enabled:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Bucket Sizing")
            bucket1_years = st.slider(
                "Safety Bucket (Years of Expenses)",
                min_value=1, max_value=5, 
                value=config_mgr.get("bucket_strategy", "bucket1_years", 2)
            )
            
            bucket2_years = st.slider(
                "Transition Bucket (Years of Expenses)",
                min_value=3, max_value=15,
                value=config_mgr.get("bucket_strategy", "bucket2_years", 8)
            )
        
        with col2:
            st.subheader("Asset Allocation")
            bucket2_stocks = st.slider(
                "Transition Bucket Stock Allocation (%)",
                min_value=0, max_value=80,
                value=config_mgr.get("bucket_strategy", "bucket2_stock_allocation", 40)
            )
            
            bucket3_stocks = st.slider(
                "Growth Bucket Stock Allocation (%)",
                min_value=40, max_value=100,
                value=config_mgr.get("bucket_strategy", "bucket3_stock_allocation", 80)
            )
    
    # Save configuration
    if st.button("Save Bucket Strategy Settings"):
        config_mgr.set("bucket_strategy", "enabled", bucket_enabled)
        if bucket_enabled:
            config_mgr.set("bucket_strategy", "bucket1_years", bucket1_years)
            config_mgr.set("bucket_strategy", "bucket2_years", bucket2_years)
            config_mgr.set("bucket_strategy", "bucket2_stock_allocation", bucket2_stocks)
            config_mgr.set("bucket_strategy", "bucket3_stock_allocation", bucket3_stocks)
        
        config_mgr.save_config()
        st.success("Bucket strategy settings saved!")
```

### Dashboard Integration

#### 1. **Bucket Strategy Summary Card**
```python
# Addition to pages/3_dashboard.py
def render_bucket_strategy_summary():
    """Render bucket strategy summary on dashboard."""
    
    config_mgr = get_config_manager()
    bucket_enabled = config_mgr.get("bucket_strategy", "enabled", False)
    
    if bucket_enabled:
        st.subheader("🪣 Bucket Strategy Status")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Safety Bucket",
                f"${bucket1_balance:,.0f}",
                delta=f"{bucket1_status}",
                help="2 years of expenses in safe investments"
            )
        
        with col2:
            st.metric(
                "Transition Bucket", 
                f"${bucket2_balance:,.0f}",
                delta=f"{bucket2_status}",
                help="8 years of expenses in balanced allocation"
            )
        
        with col3:
            st.metric(
                "Growth Bucket",
                f"${bucket3_balance:,.0f}",
                delta=f"{bucket3_status}",
                help="Long-term growth investments"
            )
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
**Estimated Effort**: 16-20 hours

**Deliverables**:
1. **bucket_strategy.py** - Core bucket strategy engine
2. **BucketAllocation** and related data structures
3. **Configuration schema updates** in config.py
4. **Unit tests** for bucket calculations

**Key Tasks**:
- [ ] Create `BucketAllocation`, `BucketRebalanceAction`, `BucketStrategyConfig` dataclasses
- [ ] Implement `BucketStrategyEngine.calculate_bucket_targets()`
- [ ] Implement `BucketStrategyEngine.determine_withdrawal_bucket()`
- [ ] Add bucket strategy configuration section to `DEFAULT_CONFIG`
- [ ] Create configuration validation functions
- [ ] Write comprehensive unit tests

**Success Criteria**:
- Bucket target calculations work correctly for various portfolio sizes
- Configuration validation prevents invalid settings
- All unit tests pass

### Phase 2: Integration (Weeks 3-4)
**Estimated Effort**: 16-20 hours

**Deliverables**:
1. **Enhanced WithdrawalStrategyEngine** with bucket integration
2. **bucket_rebalancing.py** - Bucket-aware rebalancing logic
3. **Integration with existing life stages**
4. **Enhanced YearlyStrategy** with bucket data

**Key Tasks**:
- [ ] Enhance `WithdrawalStrategyEngine` to support bucket strategy
- [ ] Implement bucket refill logic in annual rebalancing
- [ ] Create `compute_bucket_rebalance_plan()` function
- [ ] Integrate bucket withdrawals with existing withdrawal sequencing
- [ ] Update `YearlyStrategy` to include bucket allocation data
- [ ] Write integration tests

**Success Criteria**:
- Bucket strategy works alongside existing life-cycle stages
- Annual bucket refill logic executes correctly
- Withdrawal sequencing respects bucket priorities
- Integration tests pass

### Phase 3: User Interface (Weeks 5-6)
**Estimated Effort**: 12-16 hours

**Deliverables**:
1. **Bucket Strategy tab** in Strategy page
2. **Configuration UI** in Configuration page
3. **Dashboard integration** with bucket status
4. **Enhanced visualizations** showing bucket allocations

**Key Tasks**:
- [ ] Add "🪣 Bucket Strategy" tab to pages/5_strategy.py
- [ ] Implement bucket allocation visualization charts
- [ ] Create bucket balance and status tables
- [ ] Add bucket strategy section to pages/2_configuration.py
- [ ] Integrate bucket summary into pages/3_dashboard.py
- [ ] Add bucket-aware columns to strategy display tables
- [ ] Create user documentation and help text

**Success Criteria**:
- Users can enable/configure bucket strategy through UI
- Bucket allocations are clearly visualized
- Strategy tables show bucket-specific data
- Dashboard provides bucket status overview

### Phase 4: Testing & Refinement (Week 7)
**Estimated Effort**: 8-12 hours

**Deliverables**:
1. **Comprehensive test suite**
2. **Performance optimization**
3. **Documentation updates**
4. **Bug fixes and refinements**

**Key Tasks**:
- [ ] Create end-to-end test scenarios
- [ ] Performance testing with large portfolios
- [ ] Update README.md and documentation
- [ ] Code review and refactoring
- [ ] User acceptance testing
- [ ] Bug fixes based on testing feedback

**Success Criteria**:
- All tests pass consistently
- Performance is acceptable (< 2 seconds for strategy calculation)
- Documentation is complete and accurate
- No critical bugs remain

---

## Backward Compatibility

### Compatibility Strategy

#### 1. **Opt-In Design**
- Bucket strategy is **disabled by default**
- Existing users see no changes unless they explicitly enable it
- All existing functionality remains unchanged

#### 2. **Configuration Compatibility**
```python
# Existing configurations continue to work
# New bucket_strategy section is optional
def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced to handle missing bucket_strategy section."""
    merged = DEFAULT_CONFIG.copy()
    for section, values in config.items():
        if section in merged and isinstance(values, dict):
            merged[section].update(values)
        else:
            merged[section] = values
    
    # Ensure bucket_strategy section exists with defaults
    if "bucket_strategy" not in merged:
        merged["bucket_strategy"] = DEFAULT_CONFIG["bucket_strategy"].copy()
    
    return merged
```

#### 3. **Data Structure Compatibility**
```python
# Enhanced YearlyStrategy maintains backward compatibility
@dataclass
class YearlyStrategy:
    # ... existing fields remain unchanged ...
    
    # New optional fields with defaults
    bucket_allocation: Optional[BucketAllocation] = None
    bucket_withdrawals: Dict[int, float] = field(default_factory=dict)
    bucket_refills: Dict[int, float] = field(default_factory=dict)
    
    # Backward compatibility methods
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None bucket fields for compatibility."""
        result = asdict(self)
        if self.bucket_allocation is None:
            result.pop('bucket_allocation', None)
        if not self.bucket_withdrawals:
            result.pop('bucket_withdrawals', None)
        if not self.bucket_refills:
            result.pop('bucket_refills', None)
        return result
```

#### 4. **UI Compatibility**
- Existing strategy tables show the same columns by default
- Bucket-specific columns are only shown when bucket strategy is enabled
- No changes to existing page layouts or navigation

#### 5. **API Compatibility**
```python
# Existing function signatures remain unchanged
def calculate_multi_year_strategy(
    start_year: int,
    end_year: int,
    # ... existing parameters ...
    bucket_config: Optional[BucketStrategyConfig] = None  # New optional parameter
) -> pd.DataFrame:
    """Enhanced function maintains backward compatibility."""
```

### Migration Strategy

#### 1. **Automatic Migration**
- No migration required for existing users
- New bucket_strategy section is added to config with safe defaults
- Existing behavior is preserved exactly

#### 2. **Gradual Adoption**
- Users can enable bucket strategy at any time
- Can disable bucket strategy to revert to original behavior
- No data loss or corruption during enable/disable cycles

#### 3. **Configuration Validation**
```python
def validate_configuration_compatibility(config: dict) -> List[str]:
    """Validate that configuration changes don't break existing functionality."""
    warnings = []
    
    # Check for conflicting settings
    bucket_enabled = config.get("bucket_strategy", {}).get("enabled", False)
    cash_years = config.get("financial_assumptions", {}).get("years_of_expenses_in_cash", 4)
    
    if bucket_enabled:
        bucket1_years = config.get("bucket_strategy", {}).get("bucket1_years", 2)
        if cash_years != bucket1_years:
            warnings.append(
                f"Bucket 1 size ({bucket1_years} years) differs from cash buffer "
                f"({cash_years} years). Bucket 1 will take precedence."
            )
    
    return warnings
```

---

## Testing Strategy

### Unit Tests

#### 1. **Bucket Calculation Tests**
```python
# test_bucket_strategy.py
class TestBucketStrategyEngine:
    def test_calculate_bucket_targets_basic(self):
        """Test basic bucket target calculations."""
        engine = BucketStrategyEngine(BucketStrategyConfig())
        allocation = engine.calculate_bucket_targets(
            annual_expenses=50000,
            total_portfolio=1000000
        )
        
        assert allocation.bucket1_target == 100000  # 2 years * 50k
        assert allocation.bucket2_target == 400000  # 8 years * 50k
        assert allocation.bucket3_target == 500000  # remaining
    
    def test_determine_withdrawal_bucket(self):
        """Test withdrawal bucket determination logic."""
        # Test bucket 1 withdrawal when sufficient
        # Test bucket 2 fallback when bucket 1 insufficient
        # Test bucket 3 fallback when buckets 1&2 insufficient
    
    def test_calculate_annual_refill(self):
        """Test annual bucket refill calculations."""
        # Test normal refill from bucket 3 to bucket 2
        # Test refill from bucket 2 to bucket 1
        # Test no refill when buckets are full
```

#### 2. **Integration Tests**
```python
# test_bucket_integration.py
class TestBucketIntegration:
    def test_withdrawal_strategy_with_buckets(self):
        """Test that bucket strategy integrates correctly with withdrawal logic."""
        
    def test_rebalancing_with_buckets(self):
        """Test that rebalancing respects bucket constraints."""
        
    def test_life_stage_bucket_interaction(self):
        """Test interaction between life stages and bucket strategy."""
```

#### 3. **Configuration Tests**
```python
# test_bucket_config.py
class TestBucketConfiguration:
    def test_config_validation(self):
        """Test configuration validation logic."""
        
    def test_backward_compatibility(self):
        """Test that existing configs continue to work."""
        
    def test_config_migration(self):
        """Test automatic addition of bucket_strategy section."""
```

### Integration Tests

#### 1. **End-to-End Scenarios**
```python
# test_bucket_e2e.py
class TestBucketEndToEnd:
    def test_full_retirement_scenario_with_buckets(self):
        """Test complete retirement scenario with bucket strategy enabled."""
        # Setup: 30-year retirement with bucket strategy
        # Verify: Correct bucket allocations throughout retirement
        # Verify: Proper bucket refills and withdrawals
        # Verify: Tax efficiency maintained
    
    def test_market_crash_scenario(self):
        """Test bucket strategy during market downturn."""
        # Simulate market crash in year 2 of retirement
        # Verify bucket 1 provides protection
        # Verify bucket refill logic handles depleted bucket 3
    
    def test_bucket_disable_enable_cycle(self):
        """Test enabling and disabling bucket strategy."""
        # Start with bucket strategy disabled
        # Enable bucket strategy mid-retirement
        # Disable bucket strategy later
        # Verify no data corruption or calculation errors
```

### Performance Tests

#### 1. **Calculation Performance**
```python
# test_bucket_performance.py
class TestBucketPerformance:
    def test_large_portfolio_performance(self):
        """Test performance with large portfolios and long time horizons."""
        # Test 50-year projection with bucket strategy
        # Verify calculation completes in < 2 seconds
        
    def test_memory_usage(self):
        """Test memory usage with bucket strategy enabled."""
        # Verify no memory leaks in bucket calculations
        # Verify reasonable memory usage for large scenarios
```

### User Acceptance Tests

#### 1. **UI/UX Tests**
- [ ] Configuration UI is intuitive and clear
- [ ] Bucket visualizations are helpful and accurate
- [ ] Strategy tables include relevant bucket information
- [ ] Help text and documentation are comprehensive
- [ ] Error messages are clear and actionable

#### 2. **Functional Tests**
- [ ] Bucket strategy produces reasonable allocations
- [ ] Withdrawal sequencing follows bucket priorities
- [ ] Rebalancing actions are tax-efficient
- [ ] Integration with existing features works seamlessly
- [ ] Performance is acceptable for typical use cases

---

## Risk Assessment

### Technical Risks

#### 1. **Integration Complexity** (Medium Risk)
**Risk**: Bucket strategy integration may interfere with existing withdrawal logic
**Mitigation**: 
- Implement as optional overlay, not replacement
- Extensive integration testing
- Gradual rollout with feature flags

#### 2. **Performance Impact** (Low Risk)
**Risk**: Additional calculations may slow down strategy generation
**Mitigation**:
- Optimize bucket calculations for performance
- Cache bucket allocations where appropriate
- Performance testing with large portfolios

#### 3. **Configuration Complexity** (Medium Risk)
**Risk**: Too many configuration options may confuse users
**Mitigation**:
- Provide sensible defaults
- Progressive disclosure of advanced options
- Clear documentation and help text

### Business Risks

#### 1. **User Confusion** (Medium Risk)
**Risk**: Users may not understand when to use bucket strategy vs. life-cycle stages
**Mitigation**:
- Clear documentation explaining the differences
- Guided setup wizard
- Default to disabled to avoid confusion

#### 2. **Maintenance Burden** (Low Risk)
**Risk**: Additional code complexity increases maintenance overhead
**Mitigation**:
- Comprehensive test coverage
- Clear code documentation
- Modular design for easy maintenance

### Data Risks

#### 1. **Calculation Errors** (High Risk)
**Risk**: Incorrect bucket calculations could lead to poor financial advice
**Mitigation**:
- Extensive unit and integration testing
- Manual verification of calculations
- Gradual rollout with monitoring

#### 2. **Configuration Corruption** (Low Risk)
**Risk**: Configuration changes could break existing setups
**Mitigation**:
- Backward compatibility guarantees
- Configuration validation
- Automatic migration with fallbacks

### Mitigation Summary

| Risk Category | Risk Level | Primary Mitigation |
|---------------|------------|-------------------|
| Integration Complexity | Medium | Optional overlay design + extensive testing |
| Performance Impact | Low | Optimization + performance testing |
| Configuration Complexity | Medium | Sensible defaults + progressive disclosure |
| User Confusion | Medium | Clear documentation + guided setup |
| Maintenance Burden | Low | Comprehensive tests + modular design |
| Calculation Errors | High | Extensive testing + manual verification |
| Configuration Corruption | Low | Backward compatibility + validation |

---

## Conclusion

The bucket strategy implementation represents a significant enhancement to the retirement planning system that can be delivered with manageable risk through careful design and implementation. The hybrid architecture approach ensures that existing functionality remains unchanged while providing users with an optional, powerful tool for managing sequence-of-returns risk.

### Key Success Factors

1. **Backward Compatibility**: Existing users see no changes unless they opt in
2. **Modular Design**: Bucket strategy is cleanly separated from core logic
3. **Comprehensive Testing**: Extensive test coverage ensures reliability
4. **Clear Documentation**: Users understand when and how to use bucket strategy
5. **Performance**: Additional calculations don't significantly impact user experience

### Next Steps

1. **Stakeholder Review**: Review this implementation plan with key stakeholders
2. **Technical Validation**: Validate technical approach with development team
3. **Resource Planning**: Confirm availability of 40-60 hours of development time
4. **Phase 1 Kickoff**: Begin implementation with foundation phase

The bucket strategy implementation will provide users with a sophisticated tool for retirement income planning while maintaining the system's existing strengths in tax optimization and life-cycle planning.