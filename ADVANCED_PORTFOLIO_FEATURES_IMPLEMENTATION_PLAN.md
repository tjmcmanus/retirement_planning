# Advanced Portfolio Features Implementation Plan

**Date:** 2026-03-17
**Author:** Bob
**Status:** ✅ COMPLETED (March 2026)

> **Note:** This document served as the implementation plan. For the complete implementation summary, see [`ADVANCED_PORTFOLIO_FEATURES_COMPLETE.md`](ADVANCED_PORTFOLIO_FEATURES_COMPLETE.md).

## Overview

This document outlines the implementation plan for two advanced portfolio management features:

1. **Dynamic Security Selection** - Intelligent decision-making for which specific holdings to liquidate during withdrawals
2. **Factor-Based Portfolio Analysis** - Investment factor analysis (Value, Growth, Momentum, Quality)

---

## Feature 1: Dynamic Security Selection

### 1.1 Objective

Replace generic account-level withdrawals with intelligent, security-specific liquidation decisions that optimize for:
- Tax efficiency (minimize tax burden)
- Rebalancing needs (sell overweight positions)
- Cost basis optimization (FIFO with strategic selection)
- Wash sale rule compliance
- Transaction cost minimization

### 1.2 Current State Analysis

**Existing Infrastructure:**
- [`strategy.py`](strategy.py:1-200) - 6-stage withdrawal strategy with account-level withdrawals
- [`BrokerageTransaction`](strategy.py:152-200) class - FIFO cost basis tracking for brokerage
- [`portfolio_rebalancing.py`](portfolio_rebalancing.py:1-150) - Drift detection and recommendations (no execution)
- [`tax_harvesting.py`](tax_harvesting.py:1-150) - Opportunity identification (no execution)
- [`calculations.py`](calculations.py:1-150) - Tax calculation utilities

**Current Limitations:**
- Withdrawals are account-level only (e.g., "withdraw $50k from Brokerage")
- No logic for selecting which specific securities to sell
- Rebalancing and tax harvesting are separate recommendation tools
- No integration between withdrawal needs and portfolio optimization

### 1.3 Architecture Design

#### 1.3.1 New Module: `security_selection.py`

**Core Components:**

```python
@dataclass
class SecurityScore:
    """Score for a security's suitability for liquidation."""
    symbol: str
    account_type: str
    current_value: float
    
    # Scoring factors (0-100 each)
    tax_efficiency_score: float      # Higher = better tax outcome
    rebalancing_score: float          # Higher = more overweight
    liquidity_score: float            # Higher = easier to sell
    cost_basis_score: float           # Higher = better basis situation
    
    # Composite score
    total_score: float
    
    # Supporting data
    unrealized_gain_loss: float
    holding_period_days: int
    is_wash_sale_risk: bool
    asset_class: str
    current_allocation_pct: float
    target_allocation_pct: float

@dataclass
class LiquidationPlan:
    """Complete plan for liquidating securities to meet withdrawal need."""
    total_needed: float
    total_selected: float
    securities: List[SecurityLiquidation]
    
    # Tax impact summary
    total_ltcg: float
    total_stcg: float
    total_basis_returned: float
    estimated_tax: float
    
    # Rebalancing impact
    pre_allocation: Dict[str, float]
    post_allocation: Dict[str, float]
    drift_improvement: float

@dataclass
class SecurityLiquidation:
    """Details for liquidating a specific security."""
    symbol: str
    account_type: str
    shares_to_sell: float
    amount_to_liquidate: float
    cost_basis: float
    gain_loss: float
    tax_impact: float
    reason: str  # Why this security was selected
```

**Key Functions:**

```python
def score_securities_for_liquidation(
    portfolio_df: pd.DataFrame,
    withdrawal_amount: float,
    account_type: str,
    target_allocation: Dict[str, float],
    current_agi: float,
    filing_status: str,
    recent_sales: List[Dict],  # For wash sale detection
) -> List[SecurityScore]:
    """
    Score all securities in an account for liquidation suitability.
    
    Scoring Methodology:
    1. Tax Efficiency (30% weight):
       - Losses: 100 points (harvest losses first)
       - Gains at 0% LTCG: 90 points (free step-up in basis)
       - Gains at 15% LTCG: 60 points (reasonable tax)
       - Gains at 20% LTCG: 40 points (higher tax)
       - Short-term gains: 20 points (ordinary income rates)
    
    2. Rebalancing (30% weight):
       - Overweight by >10%: 100 points
       - Overweight by 5-10%: 80 points
       - Overweight by 0-5%: 60 points
       - At target: 40 points
       - Underweight: 20 points
    
    3. Liquidity (20% weight):
       - High volume stocks/ETFs: 100 points
       - Mutual funds: 80 points
       - Low volume stocks: 60 points
       - Illiquid positions: 40 points
    
    4. Cost Basis (20% weight):
       - High basis (low gain): 100 points
       - Medium basis: 70 points
       - Low basis (high gain): 40 points
       - Loss positions: 100 points
    """
    pass

def create_liquidation_plan(
    scored_securities: List[SecurityScore],
    withdrawal_amount: float,
    account_type: str,
    allow_partial_shares: bool = True,
) -> LiquidationPlan:
    """
    Create optimal liquidation plan to meet withdrawal need.
    
    Algorithm:
    1. Sort securities by total_score (descending)
    2. Select securities until withdrawal amount is met
    3. Handle partial share sales if needed
    4. Calculate tax impact and rebalancing effect
    5. Validate plan meets all constraints
    """
    pass

def execute_liquidation_plan(
    plan: LiquidationPlan,
    portfolio_state: Dict,
    year: int,
) -> Tuple[float, Dict]:
    """
    Execute liquidation plan and update portfolio state.
    
    Returns:
        Tuple of (cash_received, updated_portfolio_state)
    """
    pass

def optimize_multi_account_withdrawal(
    total_needed: float,
    portfolio_df: pd.DataFrame,
    account_priorities: List[str],
    target_allocation: Dict[str, float],
    tax_context: Dict,
) -> Dict[str, LiquidationPlan]:
    """
    Optimize withdrawals across multiple accounts.
    
    Strategy:
    1. Determine optimal account sequence (tax-efficient withdrawal order)
    2. For each account, create liquidation plan
    3. Ensure total meets withdrawal need
    4. Minimize total tax impact across all accounts
    """
    pass
```

#### 1.3.2 Integration Points

**1. Modify `strategy.py` withdrawal functions:**

```python
# Current (account-level):
def withdraw_from_brokerage(amount: float, state: Dict) -> float:
    state['brokerage'] -= amount
    return amount

# New (security-level):
def withdraw_from_brokerage_smart(
    amount: float, 
    state: Dict,
    portfolio_df: pd.DataFrame,
    year: int,
    tax_context: Dict,
) -> Tuple[float, LiquidationPlan]:
    """Smart withdrawal with security selection."""
    from security_selection import score_securities_for_liquidation, create_liquidation_plan
    
    # Get securities in brokerage account
    brokerage_holdings = portfolio_df[portfolio_df['account_type'] == 'Brokerage']
    
    # Score securities
    scored = score_securities_for_liquidation(
        brokerage_holdings,
        amount,
        'Brokerage',
        state['target_allocation'],
        tax_context['agi'],
        tax_context['filing_status'],
        state['recent_sales'],
    )
    
    # Create plan
    plan = create_liquidation_plan(scored, amount, 'Brokerage')
    
    # Execute plan
    cash_received, updated_state = execute_liquidation_plan(plan, state, year)
    
    return cash_received, plan
```

**2. Update all 6 life stages in `strategy.py`:**
- Stage 1 (Accumulation): Track purchases into brokerage
- Stage 2 (Prep): Smart Traditional→Brokerage transfers
- Stage 3 (Early Retirement): Smart LTCG harvesting
- Stage 4 (Medicare): IRMAA-aware smart withdrawals
- Stage 5 (Social Security): Coordinated SS + smart withdrawals
- Stage 6 (RMD): RMD + smart supplemental withdrawals

**3. Enhance `BrokerageTransaction` tracking:**

```python
@dataclass
class BrokerageTransaction:
    # ... existing fields ...
    
    # Add security-level tracking
    symbol: str
    shares: float
    price_per_share: float
    
    def split_transaction(self, shares_to_sell: float) -> Tuple['BrokerageTransaction', 'BrokerageTransaction']:
        """Split transaction for partial liquidation."""
        pass
```

### 1.4 Implementation Steps

#### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `security_selection.py` module
- [ ] Implement `SecurityScore` and `LiquidationPlan` dataclasses
- [ ] Implement `score_securities_for_liquidation()` function
- [ ] Implement `create_liquidation_plan()` function
- [ ] Write unit tests for scoring logic

#### Phase 2: Portfolio Integration (Week 2)
- [ ] Enhance `BrokerageTransaction` with security-level tracking
- [ ] Implement `execute_liquidation_plan()` function
- [ ] Implement `optimize_multi_account_withdrawal()` function
- [ ] Update portfolio state management in `strategy.py`
- [ ] Write integration tests

#### Phase 3: Strategy Integration (Week 3)
- [ ] Modify Stage 3 (Early Retirement) to use smart withdrawals
- [ ] Modify Stage 4 (Medicare) to use smart withdrawals
- [ ] Modify Stage 5 (Social Security) to use smart withdrawals
- [ ] Modify Stage 6 (RMD) to use smart withdrawals
- [ ] Update Stage 2 (Prep) for smart Traditional→Brokerage transfers

#### Phase 4: UI & Reporting (Week 4)
- [ ] Add liquidation plan visualization to Strategy page
- [ ] Show security-level transaction history
- [ ] Display tax impact by security
- [ ] Add "What-If" analysis for different liquidation strategies
- [ ] Create comprehensive documentation

### 1.5 Testing Strategy

**Unit Tests:**
- Security scoring with various tax scenarios
- Liquidation plan creation with different constraints
- Wash sale detection logic
- Partial share handling

**Integration Tests:**
- Multi-account withdrawal optimization
- Full withdrawal strategy with security selection
- Cost basis tracking accuracy
- Tax calculation validation

**Regression Tests:**
- Ensure existing withdrawal strategies still work
- Verify tax calculations match previous results
- Validate portfolio state consistency

---

## Feature 2: Factor-Based Portfolio Analysis

### 2.1 Objective

Provide institutional-grade factor analysis to help users understand their portfolio's exposure to key investment factors:
- **Value**: Low P/E, P/B ratios (undervalued stocks)
- **Growth**: High earnings growth, revenue growth
- **Momentum**: Recent price trends, relative strength
- **Quality**: High ROE, low debt, stable earnings

### 2.2 Current State Analysis

**Existing Infrastructure:**
- [`portfolio_analytics.py`](portfolio_analytics.py:1-150) - Performance metrics (TWR, MWR, Sharpe, Sortino)
- [`portfolio_rebalancing.py`](portfolio_rebalancing.py:1-150) - Asset class classification (Cash/Bonds/Stocks)
- [`portfolio.py`](portfolio.py:1-150) - Yahoo Finance integration for price data
- [`components/portfolio_performance.py`](components/portfolio_performance.py) - Performance UI

**Current Limitations:**
- Only basic asset class classification (Cash/Bonds/Stocks)
- No factor exposure analysis
- No style drift detection
- No factor-based attribution

### 2.3 Architecture Design

#### 2.3.1 New Module: `portfolio_factors.py`

**Core Components:**

```python
@dataclass
class FactorMetrics:
    """Factor metrics for a single security."""
    symbol: str
    name: str
    
    # Value factors
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    ps_ratio: Optional[float]
    dividend_yield: Optional[float]
    value_score: float  # 0-100 composite
    
    # Growth factors
    earnings_growth: Optional[float]
    revenue_growth: Optional[float]
    eps_growth: Optional[float]
    growth_score: float  # 0-100 composite
    
    # Momentum factors
    return_1m: Optional[float]
    return_3m: Optional[float]
    return_6m: Optional[float]
    return_12m: Optional[float]
    relative_strength: Optional[float]
    momentum_score: float  # 0-100 composite
    
    # Quality factors
    roe: Optional[float]
    roa: Optional[float]
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]
    profit_margin: Optional[float]
    quality_score: float  # 0-100 composite
    
    # Metadata
    market_cap: Optional[float]
    sector: str
    asset_class: str
    data_quality: str  # "complete", "partial", "limited"

@dataclass
class PortfolioFactorExposure:
    """Portfolio-level factor exposure analysis."""
    
    # Weighted average factor scores
    value_exposure: float  # 0-100
    growth_exposure: float  # 0-100
    momentum_exposure: float  # 0-100
    quality_exposure: float  # 0-100
    
    # Factor tilts (relative to market)
    value_tilt: float  # -50 to +50
    growth_tilt: float  # -50 to +50
    momentum_tilt: float  # -50 to +50
    quality_tilt: float  # -50 to +50
    
    # Style classification
    primary_style: str  # "Value", "Growth", "Blend", "Quality", "Momentum"
    style_purity: float  # 0-100, how pure the style is
    
    # Holdings breakdown
    value_holdings: List[Tuple[str, float, float]]  # (symbol, weight, score)
    growth_holdings: List[Tuple[str, float, float]]
    momentum_holdings: List[Tuple[str, float, float]]
    quality_holdings: List[Tuple[str, float, float]]
    
    # Factor diversification
    factor_concentration: float  # 0-100, lower = more diversified
    factor_correlation: pd.DataFrame  # Correlation matrix

@dataclass
class FactorAttribution:
    """Factor-based performance attribution."""
    
    # Total return breakdown
    total_return: float
    factor_return: float  # Return explained by factors
    alpha: float  # Return not explained by factors
    
    # Factor contributions
    value_contribution: float
    growth_contribution: float
    momentum_contribution: float
    quality_contribution: float
    
    # Time series
    factor_returns_ts: pd.DataFrame  # Time series of factor returns
```

**Key Functions:**

```python
def fetch_factor_data(
    symbol: str,
    use_cache: bool = True,
) -> FactorMetrics:
    """
    Fetch factor data for a security from Yahoo Finance.
    
    Data Sources:
    - Value: P/E, P/B, P/S from ticker.info
    - Growth: earnings/revenue growth from ticker.info
    - Momentum: Calculate from historical prices
    - Quality: ROE, ROA, debt ratios from ticker.info
    
    Scoring Methodology:
    - Each factor scored 0-100 based on percentile ranking
    - Value: Lower ratios = higher score
    - Growth: Higher growth = higher score
    - Momentum: Higher returns = higher score
    - Quality: Better metrics = higher score
    """
    pass

def calculate_portfolio_factor_exposure(
    portfolio_df: pd.DataFrame,
    factor_data: Dict[str, FactorMetrics],
) -> PortfolioFactorExposure:
    """
    Calculate portfolio-level factor exposure.
    
    Algorithm:
    1. Weight each security's factor scores by portfolio weight
    2. Calculate weighted average for each factor
    3. Compare to market benchmark (S&P 500)
    4. Determine primary style and purity
    5. Identify top holdings in each factor category
    """
    pass

def analyze_factor_drift(
    current_exposure: PortfolioFactorExposure,
    target_exposure: Optional[PortfolioFactorExposure],
    historical_exposures: List[PortfolioFactorExposure],
) -> Dict[str, Any]:
    """
    Analyze factor drift over time.
    
    Returns:
    - Drift from target (if specified)
    - Trend analysis (increasing/decreasing exposure)
    - Volatility of factor exposures
    - Recommendations for rebalancing
    """
    pass

def perform_factor_attribution(
    portfolio_returns: pd.Series,
    factor_exposures: pd.DataFrame,
    benchmark_returns: pd.Series,
) -> FactorAttribution:
    """
    Perform factor-based return attribution.
    
    Uses Fama-French style regression to decompose returns:
    R_portfolio = α + β_value*R_value + β_growth*R_growth + 
                  β_momentum*R_momentum + β_quality*R_quality + ε
    """
    pass

def generate_factor_recommendations(
    exposure: PortfolioFactorExposure,
    target_style: Optional[str],
    risk_tolerance: str,
) -> List[str]:
    """
    Generate actionable recommendations based on factor analysis.
    
    Examples:
    - "Your portfolio has high growth exposure (85/100). Consider adding value stocks for balance."
    - "Momentum score is declining. Review recent underperformers."
    - "Quality score is excellent (92/100). Portfolio is well-positioned for downturns."
    """
    pass
```

#### 2.3.2 Integration Points

**1. Extend `portfolio_analytics.py`:**

```python
# Add factor analysis to existing performance metrics
def calculate_comprehensive_analytics(
    portfolio_df: pd.DataFrame,
    historical_data: pd.DataFrame,
    benchmark: str = "^GSPC",
) -> Tuple[PerformanceMetrics, PortfolioFactorExposure]:
    """Calculate both performance and factor metrics."""
    
    # Existing performance metrics
    perf_metrics = calculate_performance_metrics(...)
    
    # New factor analysis
    from portfolio_factors import fetch_factor_data, calculate_portfolio_factor_exposure
    
    factor_data = {}
    for symbol in portfolio_df['symbol'].unique():
        factor_data[symbol] = fetch_factor_data(symbol)
    
    factor_exposure = calculate_portfolio_factor_exposure(portfolio_df, factor_data)
    
    return perf_metrics, factor_exposure
```

**2. Update `components/portfolio_performance.py`:**

Add new tab for factor analysis:
```python
def render_performance_tab(portdf, networth, curr_month, curr_year):
    tabs = st.tabs([
        "📊 Performance Metrics",
        "📈 Returns Analysis", 
        "⚖️ Risk Analysis",
        "🎯 Factor Analysis",  # NEW
        "📉 Drawdown Analysis"
    ])
    
    with tabs[3]:  # Factor Analysis tab
        render_factor_analysis(portdf, networth)
```

**3. Create new component: `components/portfolio_factors_ui.py`:**

```python
def render_factor_analysis(
    portfolio_df: pd.DataFrame,
    networth: pd.DataFrame,
) -> None:
    """
    Render factor analysis UI with:
    - Factor exposure radar chart
    - Style classification
    - Top holdings by factor
    - Factor drift over time
    - Recommendations
    """
    pass
```

### 2.4 Implementation Steps

#### Phase 1: Data Collection (Week 1)
- [ ] Create `portfolio_factors.py` module
- [ ] Implement `FactorMetrics` dataclass
- [ ] Implement `fetch_factor_data()` with Yahoo Finance
- [ ] Create factor scoring methodology
- [ ] Implement caching for factor data
- [ ] Write unit tests for data fetching

#### Phase 2: Analysis Engine (Week 2)
- [ ] Implement `calculate_portfolio_factor_exposure()`
- [ ] Implement `analyze_factor_drift()`
- [ ] Implement `perform_factor_attribution()`
- [ ] Implement `generate_factor_recommendations()`
- [ ] Write unit tests for analysis functions

#### Phase 3: UI Components (Week 3)
- [ ] Create `components/portfolio_factors_ui.py`
- [ ] Implement factor exposure radar chart
- [ ] Implement style classification display
- [ ] Implement top holdings by factor tables
- [ ] Implement factor drift visualization
- [ ] Add recommendations panel

#### Phase 4: Integration & Polish (Week 4)
- [ ] Integrate with existing Portfolio Hub
- [ ] Add factor analysis to Performance tab
- [ ] Create factor-based rebalancing suggestions
- [ ] Add factor data to CSV export
- [ ] Write comprehensive documentation
- [ ] Create user guide with examples

### 2.5 Testing Strategy

**Unit Tests:**
- Factor data fetching and parsing
- Factor scoring calculations
- Portfolio exposure calculations
- Style classification logic

**Integration Tests:**
- Full factor analysis pipeline
- UI rendering with real portfolio data
- Factor drift detection
- Recommendation generation

**Data Quality Tests:**
- Handle missing factor data gracefully
- Validate factor scores are in range
- Test with various portfolio compositions
- Verify calculations against known benchmarks

---

## Implementation Timeline

### Month 1: Dynamic Security Selection
- **Week 1**: Core infrastructure and scoring
- **Week 2**: Portfolio integration
- **Week 3**: Strategy integration
- **Week 4**: UI and reporting

### Month 2: Factor-Based Analysis
- **Week 1**: Data collection
- **Week 2**: Analysis engine
- **Week 3**: UI components
- **Week 4**: Integration and polish

### Month 3: Testing & Documentation
- **Week 1**: Comprehensive testing
- **Week 2**: Performance optimization
- **Week 3**: Documentation and guides
- **Week 4**: User acceptance testing

---

## Success Metrics

### Dynamic Security Selection
- ✅ Reduce average tax burden on withdrawals by 15-25%
- ✅ Improve portfolio rebalancing efficiency (fewer manual trades)
- ✅ Maintain wash sale compliance (0 violations)
- ✅ Reduce transaction costs through intelligent batching

### Factor-Based Analysis
- ✅ Provide factor exposure metrics for 95%+ of holdings
- ✅ Generate actionable recommendations for all portfolios
- ✅ Enable factor-based rebalancing decisions
- ✅ Improve user understanding of portfolio style

---

## Risk Mitigation

### Technical Risks
1. **Yahoo Finance API limitations**
   - Mitigation: Implement robust caching, fallback data sources
   
2. **Complex tax calculations**
   - Mitigation: Extensive testing, tax professional review
   
3. **Performance with large portfolios**
   - Mitigation: Optimize algorithms, implement pagination

### User Experience Risks
1. **Feature complexity**
   - Mitigation: Progressive disclosure, clear documentation
   
2. **Data quality issues**
   - Mitigation: Clear indicators of data completeness
   
3. **Overwhelming information**
   - Mitigation: Sensible defaults, optional advanced features

---

## Dependencies

### External Libraries
- `yfinance` - Already in use for price data
- `pandas` - Already in use for data manipulation
- `numpy` - Already in use for calculations
- `streamlit` - Already in use for UI

### Internal Modules
- `strategy.py` - Withdrawal strategy engine
- `portfolio_analytics.py` - Performance metrics
- `portfolio_rebalancing.py` - Rebalancing logic
- `tax_harvesting.py` - Tax optimization
- `calculations.py` - Tax calculations

---

## Future Enhancements

### Phase 2 Features (Post-Launch)
1. **Machine Learning Integration**
   - Predict optimal liquidation strategies
   - Learn from user preferences
   - Forecast factor performance

2. **Advanced Tax Strategies**
   - Multi-year tax optimization
   - Estate planning integration
   - Charitable giving optimization

3. **Real-Time Execution**
   - Brokerage API integration
   - Automated trade execution
   - Real-time portfolio monitoring

4. **Enhanced Factor Models**
   - Custom factor definitions
   - Sector-specific factors
   - ESG factor integration

---

## Conclusion

This implementation plan provides a comprehensive roadmap for adding sophisticated portfolio management capabilities to the Financial Planner application. The phased approach ensures:

1. **Incremental value delivery** - Each phase provides standalone benefits
2. **Risk management** - Testing and validation at each step
3. **User feedback integration** - Opportunity to adjust based on usage
4. **Maintainability** - Clean architecture and comprehensive documentation

The combination of Dynamic Security Selection and Factor-Based Analysis will transform the application from a planning tool into a complete portfolio management platform, rivaling institutional-grade systems while maintaining ease of use for individual investors.