# Portfolio Data Integration Review
## Bucket Strategy Implementation - Code Review Notes

**Date**: 2026-03-07  
**Reviewer**: Bob  
**Purpose**: Verify portfolio data integration and design market trend-based rebalancing enhancements

---

## Executive Summary

✅ **Portfolio Data Integration**: VERIFIED - The system successfully uses `portfolio_data_truth.csv` as the single source of truth for all portfolio operations.

✅ **Rebalancing Infrastructure**: CONFIRMED - Robust rebalancing logic exists in `portfolio_rebalancing.py` that can be extended for bucket strategy.

⚠️ **Market Trend Integration**: NOT IMPLEMENTED - New module required for SPY moving average analysis and market-condition-based rebalancing.

---

## 1. Portfolio Data Integration Verification

### 1.1 Data Source: `portfolio_data_truth.csv`

**Location**: Root directory  
**Format**: CSV with monthly snapshots  
**Schema**:
```csv
month,year,account_name,account_type,symbol,name,sector,qty,purchase_price,purchase_date
```

**Key Findings**:
- ✅ Monthly snapshots available (Dec 2025, Jan 2026, Feb 2026 confirmed)
- ✅ Multiple account types supported: Traditional, Roth, Brokerage, Savings
- ✅ Multiple institutions: Schwab, Fidelity, Vanguard, PNC
- ✅ Cash positions tracked as `MF:CASH` symbol
- ✅ Holdings include stocks, bonds, mutual funds, and cash

**Sample Data Structure**:
```
Account Types: Traditional, Roth, Brokerage, Savings
Institutions: Schwab, Fidelity, Vanguard, PNC
Asset Classes: Stocks (TSLA, NVDA, META, etc.), Bonds (via MF: prefix), Cash (MF:CASH)
```

### 1.2 Data Loading Infrastructure (`load_data.py`)

**Primary Functions**:

1. **`load_portfolio_truth(_file_mtime=None)`** (Line 237)
   - Cached function that loads complete portfolio dataset
   - Uses file modification time for cache invalidation
   - Returns full DataFrame with all historical snapshots

2. **`get_portfolio_truth_by_month(month, year)`** (Line 280)
   - Filters portfolio data for specific month/year
   - Used by all portfolio operations
   - Returns empty DataFrame if no data exists for period

3. **`get_latest_portfolio_month_year()`** (Line 262)
   - Returns most recent (month, year) available in dataset
   - Used for fallback when requested period has no data
   - Critical for handling current month before data entry

4. **`get_networth_by_month(month, year)`** (Line 365)
   - **PERFORMANCE OPTIMIZED**: Batch fetches all prices via `_fetch_current_prices()`
   - Calculates current market values using live Yahoo Finance prices
   - Returns detailed holdings and summary by account_type
   - Cached for 5 minutes (TTL=300)

**Integration Points for Bucket Strategy**:
- ✅ All portfolio data flows through `get_portfolio_truth_by_month()`
- ✅ Account type classification already available (`account_type` column)
- ✅ Asset class can be derived from `sector` field
- ✅ Current market values calculated with live prices
- ✅ Fallback mechanism ensures data always available

### 1.3 Portfolio Display Layer (`portfolio.py`)

**Primary Functions**:

1. **`getPortfolioData(month=None, year=None)`** (Line 167)
   - Cached wrapper around `get_portfolio_truth_by_month()`
   - Handles month/year defaults (current month if not specified)
   - Falls back to latest available data
   - Returns DataFrame with: account_name, account_type, symbol, name, sector, qty, purchase_price, purchase_date

2. **`build_portfolio_display(month=None, year=None)`** (Line 286)
   - Builds complete portfolio display with current prices
   - Pre-fetches prices for all unique symbols (performance optimization)
   - Calculates: Current value, Cost Basis, Net Return, Dividends
   - Includes totals row
   - **DISK CACHE**: Uses Parquet cache for instant startup

3. **`render_portfolio(month, year, done_event)`** (Line 462)
   - **BACKGROUND REFRESH**: Loads from cache immediately, refreshes in background thread
   - Non-blocking UI rendering
   - Automatic cache invalidation after 5 minutes

**Key Design Patterns**:
- ✅ Separation of concerns: data loading vs. display logic
- ✅ Performance optimization: batch price fetching, caching
- ✅ User experience: instant rendering with background updates
- ✅ Unique identification: (account_name, symbol) tuples prevent duplicates

### 1.4 Account Type Mapping for Bucket Strategy

**Current Account Types** → **Bucket Strategy Mapping**:

| Account Type | Current Usage | Bucket Strategy Role |
|--------------|---------------|---------------------|
| `Savings` | PNC savings account | Bucket 1 (Safety) - Cash only |
| `Brokerage` | Schwab/Vanguard taxable | Buckets 1-3 - Tax-efficient placement |
| `Traditional` | Fidelity Traditional IRA | Buckets 2-3 - Bonds preferred |
| `Roth` | Schwab Roth IRA | Buckets 2-3 - Stocks preferred |

**Asset Class Detection** (from `sector` field):
- **Cash**: `MF:Cash`, `Money Market`
- **Bonds**: `MF:` prefix with bond keywords (Treasury, Municipal, Fixed Income)
- **Stocks**: All other securities

---

## 2. Rebalancing Infrastructure Review

### 2.1 Current Rebalancing Logic (`portfolio_rebalancing.py`)

**Architecture**: Comprehensive 1,407-line module with sophisticated rebalancing logic

**Key Components**:

1. **Asset Classification** (Lines 103-157)
   - `_classify_asset()`: Determines Cash/Bonds/Stocks from sector/name
   - Handles edge cases: Municipal bonds, Treasuries, Money Market funds
   - Uses regex patterns for bond detection

2. **Main Rebalancing Function** (Lines 1069-1224)
   - `compute_rebalance_plan()`: Generates complete rebalancing report
   - **Inputs**: month, year, target allocations (cash/bonds/stocks %), drift threshold
   - **Outputs**: `RebalanceReport` with actions, holdings, drift analysis

3. **Rebalancing Strategy** (Priority Order):
   ```
   Step 7a: Rebalance inside tax-advantaged accounts (no tax event)
   Step 7b: Buy using available cash in tax-advantaged accounts
   Step 7c: Tax-loss harvest in Brokerage
   Step 7d: Redirect contributions/dividends
   Step 7e: Brokerage cash cushion top-up (10% minimum)
   ```

4. **Data Structures**:
   - `AssetClassSummary`: Current vs. target allocation analysis
   - `HoldingDetail`: Individual position details
   - `RebalanceAction`: Specific buy/sell recommendations
   - `RebalanceReport`: Complete rebalancing plan

**Integration Points for Bucket Strategy**:
- ✅ Already uses `getPortfolioData()` - same data source
- ✅ Asset classification logic can be reused
- ✅ Tax-efficient rebalancing logic applicable to bucket transitions
- ✅ Account-location rules align with bucket strategy principles
- ✅ Drift threshold mechanism can trigger bucket rebalancing

### 2.2 Rebalancing UI Integration

**Current UI** (from implementation plan):
- Strategy page has rebalancing visualizations
- Configuration page allows setting target allocations
- Dashboard shows portfolio summary

**Bucket Strategy Integration Needs**:
- New tab: "🪣 Bucket Strategy" on Strategy page
- Bucket allocation display alongside asset class allocation
- Bucket transition actions in rebalancing recommendations

---

## 3. Market Trend-Based Rebalancing Design

### 3.1 Requirements Analysis

**User Request**: Implement 4-state market condition system using SPY moving averages

**Market States**:
1. **Bull Case**: 10-week MA ↑ AND 50-week MA ↑
2. **Warning Negative (Bull)**: 10-week MA ↓ AND 50-week MA ↑
3. **Warning Positive (Bear)**: 10-week MA ↑ AND 50-week MA ↓
4. **Bear Case**: 10-week MA ↓ AND 50-week MA ↓

**Impact on Bucket Strategy**:
- Adjust bucket allocations based on market conditions
- Modify rebalancing triggers (more defensive in bear markets)
- Influence bucket refill timing and amounts

### 3.2 Proposed Module: `market_trend_analysis.py`

**Module Purpose**: Analyze SPY moving averages and determine market conditions

**Key Components**:

```python
# Data Structures
@dataclass
class MovingAverageData:
    """SPY moving average data point."""
    date: datetime
    price: float
    ma_10week: float
    ma_50week: float
    ma_10week_slope: float  # Positive = trending up
    ma_50week_slope: float

@dataclass
class MarketCondition:
    """Current market condition assessment."""
    date: datetime
    state: str  # 'bull', 'warning_negative', 'warning_positive', 'bear'
    ma_10week_trending: str  # 'positive', 'negative'
    ma_50week_trending: str  # 'positive', 'negative'
    confidence: float  # 0.0-1.0
    recommendation: str  # Human-readable guidance
    
    # Historical context
    days_in_current_state: int
    previous_state: str
    state_change_date: Optional[datetime]

@dataclass
class MarketTrendConfig:
    """Configuration for market trend analysis."""
    ma_short_period: int = 10  # weeks
    ma_long_period: int = 50   # weeks
    slope_lookback_days: int = 5  # Days to calculate slope
    min_confidence_threshold: float = 0.7
    cache_ttl_seconds: int = 3600  # 1 hour

# Core Functions
def fetch_spy_data(lookback_weeks: int = 52) -> pd.DataFrame:
    """Fetch SPY price data from Yahoo Finance."""
    
def calculate_moving_averages(
    spy_data: pd.DataFrame,
    short_period: int = 10,
    long_period: int = 50
) -> pd.DataFrame:
    """Calculate moving averages and slopes."""
    
def determine_market_condition(
    ma_data: pd.DataFrame,
    config: MarketTrendConfig
) -> MarketCondition:
    """Determine current market state from MA data."""
    
def get_current_market_condition(
    config: Optional[MarketTrendConfig] = None
) -> MarketCondition:
    """Main entry point - get current market condition (cached)."""

# Bucket Strategy Integration
def adjust_bucket_allocation_for_market(
    base_allocation: dict,
    market_condition: MarketCondition,
    risk_profile: str = "moderate"
) -> dict:
    """Adjust bucket allocations based on market conditions."""
    # Bull: Maintain aggressive allocation
    # Warning: Shift 10% from stocks to bonds
    # Bear: Shift 20% from stocks to bonds, increase cash
```

**Caching Strategy**:
- Cache market condition for 1 hour (avoid excessive API calls)
- Store historical state transitions for trend analysis
- Invalidate cache on user request for manual refresh

**Data Source**:
- Yahoo Finance via `yfinance` library (already in use)
- SPY (S&P 500 ETF) as market proxy
- Weekly data for moving averages

### 3.3 Integration with Bucket Strategy

**Configuration Schema Addition**:
```python
"bucket_strategy": {
    # ... existing fields ...
    
    "market_trend_adjustment": {
        "enabled": True,
        "ma_short_period_weeks": 10,
        "ma_long_period_weeks": 50,
        "adjustment_mode": "moderate",  # conservative, moderate, aggressive
        
        # Allocation adjustments by market state
        "bull_adjustment": {
            "bucket2_stock_shift": 0.0,   # No change
            "bucket3_stock_shift": 0.0
        },
        "warning_adjustment": {
            "bucket2_stock_shift": -10.0,  # Reduce stocks by 10%
            "bucket3_stock_shift": -5.0
        },
        "bear_adjustment": {
            "bucket2_stock_shift": -20.0,  # Reduce stocks by 20%
            "bucket3_stock_shift": -10.0,
            "bucket1_cash_increase": 0.5   # Add 6 months to safety bucket
        }
    }
}
```

**Rebalancing Trigger Logic**:
```python
def should_rebalance_buckets(
    current_allocation: BucketAllocation,
    market_condition: MarketCondition,
    config: BucketStrategyConfig
) -> tuple[bool, str]:
    """Determine if bucket rebalancing is needed."""
    
    # Standard drift-based trigger
    if current_allocation.needs_rebalancing:
        return True, "Drift threshold exceeded"
    
    # Market condition change trigger
    if market_condition.state_change_date:
        days_since_change = (datetime.now() - market_condition.state_change_date).days
        if days_since_change <= 7:  # Recent state change
            return True, f"Market condition changed to {market_condition.state}"
    
    # Defensive trigger in bear market
    if market_condition.state == 'bear' and config.market_trend_adjustment.enabled:
        if current_allocation.bucket2_allocation['Stocks'] > adjusted_target:
            return True, "Bear market defensive rebalancing"
    
    return False, "No rebalancing needed"
```

### 3.4 UI Integration for Market Trends

**Dashboard Addition**:
```
┌─────────────────────────────────────────────────────────┐
│ 📊 Market Condition                                      │
│                                                          │
│ Current State: ⚠️ Warning Negative (Bull)                │
│ 10-week MA: ↓ Trending Down                             │
│ 50-week MA: ↑ Trending Up                               │
│                                                          │
│ Recommendation: Consider defensive positioning          │
│ Last State Change: 3 days ago (Bull → Warning)          │
│                                                          │
│ [View Detailed Analysis] [Refresh Market Data]          │
└─────────────────────────────────────────────────────────┘
```

**Strategy Page Enhancement**:
- Market condition indicator at top of bucket strategy tab
- Historical state transitions chart
- Impact on current bucket allocations shown
- Override option for manual control

---

## 4. Implementation Recommendations

### 4.1 Portfolio Data Integration

**Status**: ✅ READY - No changes needed

**Verification**:
- Portfolio data flows correctly through `portfolio_data_truth.csv`
- Account types properly classified
- Asset classes can be derived from existing data
- Current market values calculated accurately

**Bucket Strategy Mapping**:
```python
def map_holdings_to_buckets(
    portfolio_data: pd.DataFrame,
    bucket_config: BucketStrategyConfig,
    annual_expenses: float
) -> Dict[int, List[HoldingDetail]]:
    """Map portfolio holdings to buckets based on account type and time horizon."""
    
    # Bucket 1 (Safety): Cash in Savings + Brokerage MF:CASH
    # Bucket 2 (Transition): Bonds in Traditional, some stocks in Roth
    # Bucket 3 (Growth): Remaining stocks in Roth + Brokerage
    
    bucket1_target = annual_expenses * bucket_config.bucket1_years
    bucket2_target = annual_expenses * bucket_config.bucket2_years
    
    # Algorithm:
    # 1. Allocate all Savings account to Bucket 1
    # 2. Allocate Brokerage cash to Bucket 1 (up to target)
    # 3. Allocate bonds to Bucket 2 (prefer Traditional IRA)
    # 4. Allocate conservative stocks to Bucket 2
    # 5. Allocate growth stocks to Bucket 3
```

### 4.2 Rebalancing Integration

**Status**: ✅ READY - Extension points identified

**Integration Approach**:
1. Extend `compute_rebalance_plan()` to accept bucket strategy config
2. Add bucket-aware allocation targets
3. Incorporate market condition adjustments
4. Generate bucket transition actions alongside asset class rebalancing

**Proposed Function**:
```python
def compute_bucket_rebalance_plan(
    month: int,
    year: int,
    bucket_config: BucketStrategyConfig,
    market_condition: Optional[MarketCondition] = None,
    drift_threshold_pct: float = 5.0
) -> BucketRebalanceReport:
    """Compute bucket strategy rebalancing plan."""
    
    # 1. Get current portfolio
    portfolio_data = getPortfolioData(month=month, year=year)
    
    # 2. Map holdings to buckets
    bucket_holdings = map_holdings_to_buckets(portfolio_data, bucket_config)
    
    # 3. Calculate target allocations (with market adjustments)
    target_allocations = calculate_bucket_targets(
        bucket_config, market_condition
    )
    
    # 4. Identify drift and generate actions
    actions = generate_bucket_rebalance_actions(
        bucket_holdings, target_allocations, drift_threshold_pct
    )
    
    # 5. Leverage existing rebalancing logic for execution
    asset_actions = compute_rebalance_plan(
        month, year,
        target_cash_pct=target_allocations['Cash'],
        target_bonds_pct=target_allocations['Bonds'],
        target_stocks_pct=target_allocations['Stocks']
    )
    
    return BucketRebalanceReport(
        bucket_allocations=bucket_holdings,
        target_allocations=target_allocations,
        bucket_actions=actions,
        asset_rebalance_actions=asset_actions,
        market_condition=market_condition
    )
```

### 4.3 Market Trend Module Implementation

**Status**: ⚠️ NEW MODULE REQUIRED

**Implementation Steps**:
1. Create `market_trend_analysis.py` module
2. Implement SPY data fetching with caching
3. Calculate moving averages and slopes
4. Determine market state with confidence scoring
5. Add configuration schema to `config.py`
6. Integrate with bucket strategy rebalancing logic
7. Add UI components for market condition display

**Testing Requirements**:
- Unit tests for MA calculations
- Historical backtesting with known market conditions
- Edge case handling (missing data, API failures)
- Performance testing (caching effectiveness)

### 4.4 Configuration Schema Updates

**Required Changes to `config.py`**:
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
            "adjustment_mode": "moderate",
            "cache_ttl_hours": 1,
            
            # Allocation shifts by market state (percentage points)
            "bull_stock_shift": 0.0,
            "warning_stock_shift": -10.0,
            "bear_stock_shift": -20.0,
            "bear_cash_increase_months": 6,  # Add 6 months to Bucket 1
        }
    }
}
```

---

## 5. Risk Assessment & Mitigation

### 5.1 Data Integration Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Missing portfolio data for current month | Low | Fallback to latest available month (already implemented) |
| Yahoo Finance API failures | Medium | Use purchase price as fallback (already implemented) |
| Account type misclassification | Low | Clear mapping rules, validation in tests |

### 5.2 Market Trend Analysis Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| SPY data unavailable | Medium | Cache last known state, show warning to user |
| False signals from MA crossovers | Medium | Add confidence scoring, require sustained trends |
| Over-trading due to frequent state changes | High | Implement minimum holding period, transaction cost awareness |
| User confusion about market states | Medium | Clear UI explanations, educational tooltips |

### 5.3 Performance Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Slow MA calculations | Low | Pre-calculate and cache, use vectorized pandas operations |
| Excessive API calls to Yahoo Finance | Medium | 1-hour cache TTL, batch requests |
| UI lag from market data fetching | Low | Background refresh pattern (already used for portfolio) |

---

## 6. Next Steps

### 6.1 Immediate Actions

1. ✅ **COMPLETED**: Verify portfolio data integration
2. ✅ **COMPLETED**: Review existing rebalancing infrastructure
3. 🔄 **IN PROGRESS**: Design market trend analysis module
4. ⏳ **PENDING**: Update implementation plan with findings

### 6.2 Implementation Priority

**Phase 1: Foundation** (Week 1)
- [ ] Create `market_trend_analysis.py` module
- [ ] Implement SPY data fetching and MA calculations
- [ ] Add market condition determination logic
- [ ] Write unit tests for MA calculations

**Phase 2: Integration** (Week 2)
- [ ] Update `config.py` with market trend schema
- [ ] Integrate market conditions with bucket strategy
- [ ] Implement allocation adjustment logic
- [ ] Add rebalancing trigger enhancements

**Phase 3: UI** (Week 3)
- [ ] Add market condition dashboard widget
- [ ] Enhance bucket strategy page with market data
- [ ] Add configuration UI for market trend settings
- [ ] Implement manual refresh controls

**Phase 4: Testing** (Week 4)
- [ ] Historical backtesting with known market conditions
- [ ] Integration testing with bucket strategy
- [ ] Performance testing and optimization
- [ ] User acceptance testing

---

## 7. Conclusion

### 7.1 Portfolio Integration: VERIFIED ✅

The system successfully uses `portfolio_data_truth.csv` as the single source of truth:
- Monthly snapshots with complete holdings data
- Account types properly classified for bucket mapping
- Asset classes derivable from sector information
- Current market values calculated with live prices
- Robust fallback mechanisms for missing data

**Recommendation**: No changes needed to portfolio data integration. The bucket strategy can directly leverage existing infrastructure.

### 7.2 Rebalancing Infrastructure: READY ✅

The existing `portfolio_rebalancing.py` module provides:
- Sophisticated asset classification logic
- Tax-efficient rebalancing strategies
- Account-location optimization
- Drift-based rebalancing triggers
- Comprehensive action generation

**Recommendation**: Extend existing rebalancing logic rather than replacing it. The bucket strategy should generate bucket-level targets that feed into the existing rebalancing engine.

### 7.3 Market Trend Integration: DESIGN COMPLETE ⚠️

New module required for SPY moving average analysis:
- 4-state market condition system designed
- Integration points with bucket strategy identified
- Configuration schema defined
- UI components specified
- Risk mitigation strategies outlined

**Recommendation**: Implement `market_trend_analysis.py` as a standalone module with clear interfaces. Use caching aggressively to minimize API calls and ensure responsive UI.

### 7.4 Overall Assessment

**Readiness Score**: 8/10
- Portfolio data integration: 10/10 (ready)
- Rebalancing infrastructure: 9/10 (minor extensions needed)
- Market trend module: 5/10 (new development required)
- Configuration schema: 7/10 (additions needed)
- UI integration: 6/10 (enhancements needed)

**Estimated Implementation Effort**: 40-50 hours
- Market trend module: 16-20 hours
- Bucket strategy integration: 12-16 hours
- Configuration and validation: 4-6 hours
- UI enhancements: 8-10 hours
- Testing and documentation: 8-10 hours

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-07  
**Next Review**: After Phase 1 implementation