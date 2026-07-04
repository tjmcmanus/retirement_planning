# Feature 2: Factor-Based Portfolio Analysis - Implementation Plan

**Date:** 2026-03-17
**Status:** ✅ COMPLETED (March 2026)

> **Note:** This document served as the implementation plan. For the complete implementation summary, see [`FEATURE2_IMPLEMENTATION_COMPLETE.md`](FEATURE2_IMPLEMENTATION_COMPLETE.md) and [`ADVANCED_PORTFOLIO_FEATURES_COMPLETE.md`](ADVANCED_PORTFOLIO_FEATURES_COMPLETE.md).

## Overview

Implement institutional-grade factor analysis to provide deep insights into portfolio composition and risk exposures across four key investment factors:

1. **Value** - Low P/E, P/B ratios (undervalued stocks)
2. **Growth** - High earnings/revenue growth
3. **Momentum** - Recent price trends and relative strength
4. **Quality** - High ROE, low debt, stable earnings

## Architecture

### Core Module: `portfolio_factors.py`

**Data Classes:**
- `FactorMetrics` - Individual security factor scores
- `PortfolioFactorExposure` - Portfolio-level factor analysis
- `FactorAttribution` - Performance attribution by factor
- `FactorDrift` - Factor drift analysis over time

**Key Functions:**
- `fetch_factor_data()` - Retrieve factor data from Yahoo Finance
- `calculate_factor_scores()` - Score securities 0-100 on each factor
- `calculate_portfolio_exposure()` - Aggregate portfolio-level exposures
- `analyze_factor_drift()` - Track factor changes over time
- `perform_factor_attribution()` - Attribute returns to factors

### Data Sources

**Yahoo Finance API (via yfinance):**
- **Value Factors:**
  - `ticker.info['trailingPE']` - P/E ratio
  - `ticker.info['priceToBook']` - P/B ratio
  - `ticker.info['priceToSalesTrailing12Months']` - P/S ratio
  - `ticker.info['dividendYield']` - Dividend yield

- **Growth Factors:**
  - `ticker.info['earningsGrowth']` - Earnings growth rate
  - `ticker.info['revenueGrowth']` - Revenue growth rate
  - `ticker.info['earningsQuarterlyGrowth']` - Quarterly EPS growth

- **Momentum Factors:**
  - `ticker.history()` - Historical prices for return calculations
  - Calculate 1M, 3M, 6M, 12M returns
  - Relative strength vs benchmark

- **Quality Factors:**
  - `ticker.info['returnOnEquity']` - ROE
  - `ticker.info['returnOnAssets']` - ROA
  - `ticker.info['debtToEquity']` - Debt/Equity ratio
  - `ticker.info['currentRatio']` - Current ratio
  - `ticker.info['profitMargins']` - Profit margin

### Scoring Methodology

Each factor scored 0-100 using percentile ranking:

**Value Score (Lower is Better):**
- P/E < 10: 100 points
- P/E 10-15: 80 points
- P/E 15-20: 60 points
- P/E 20-30: 40 points
- P/E > 30: 20 points
- Similar for P/B, P/S
- Composite: Average of available metrics

**Growth Score (Higher is Better):**
- Earnings growth > 20%: 100 points
- Earnings growth 15-20%: 80 points
- Earnings growth 10-15%: 60 points
- Earnings growth 5-10%: 40 points
- Earnings growth < 5%: 20 points
- Composite: Average of earnings, revenue, EPS growth

**Momentum Score (Higher Returns = Higher Score):**
- 12M return > 30%: 100 points
- 12M return 20-30%: 80 points
- 12M return 10-20%: 60 points
- 12M return 0-10%: 40 points
- 12M return < 0%: 20 points
- Composite: Weighted average (1M: 10%, 3M: 20%, 6M: 30%, 12M: 40%)

**Quality Score (Better Metrics = Higher Score):**
- ROE > 20%: 100 points
- ROE 15-20%: 80 points
- ROE 10-15%: 60 points
- ROE 5-10%: 40 points
- ROE < 5%: 20 points
- Debt/Equity < 0.5: +20 bonus
- Current ratio > 2.0: +10 bonus
- Composite: Weighted average with bonuses

### Portfolio-Level Calculations

**Factor Exposure:**
```
Portfolio Factor Score = Σ(Security Weight × Security Factor Score)
```

**Factor Tilt:**
```
Factor Tilt = Portfolio Factor Score - Benchmark Factor Score
Range: -50 (strong underweight) to +50 (strong overweight)
```

**Style Classification:**
- **Value**: Value score > 70, Growth score < 50
- **Growth**: Growth score > 70, Value score < 50
- **Blend**: Both Value and Growth 50-70
- **Quality**: Quality score > 80
- **Momentum**: Momentum score > 80

**Style Purity:**
```
Purity = (Primary Factor Score - Average of Other Factors) / 100
Range: 0 (no clear style) to 100 (pure style)
```

## Implementation Phases

### Phase 1: Core Infrastructure ✅ (Current)
- [x] Design architecture
- [x] Define data classes
- [x] Plan data sources
- [x] Design scoring methodology
- [ ] Create `portfolio_factors.py` module
- [ ] Implement `FactorMetrics` dataclass
- [ ] Implement `PortfolioFactorExposure` dataclass

### Phase 2: Data Collection (Week 1)
- [ ] Implement `fetch_factor_data()` with Yahoo Finance
- [ ] Add caching mechanism for API calls
- [ ] Handle missing data gracefully
- [ ] Implement retry logic for API failures
- [ ] Add data quality indicators

### Phase 3: Factor Scoring (Week 1)
- [ ] Implement value scoring algorithm
- [ ] Implement growth scoring algorithm
- [ ] Implement momentum scoring algorithm
- [ ] Implement quality scoring algorithm
- [ ] Add composite score calculations
- [ ] Write unit tests for scoring

### Phase 4: Portfolio Analysis (Week 2)
- [ ] Implement `calculate_portfolio_exposure()`
- [ ] Calculate weighted factor scores
- [ ] Determine factor tilts vs benchmark
- [ ] Classify portfolio style
- [ ] Identify top holdings by factor
- [ ] Calculate factor concentration

### Phase 5: Advanced Features (Week 2)
- [ ] Implement factor drift analysis
- [ ] Add factor attribution
- [ ] Create factor correlation matrix
- [ ] Add historical tracking
- [ ] Implement recommendations engine

### Phase 6: UI Integration (Week 3)
- [ ] Create factor analysis page
- [ ] Add factor exposure charts (radar/spider)
- [ ] Display top holdings by factor
- [ ] Show factor drift over time
- [ ] Add style classification display
- [ ] Create factor attribution charts

### Phase 7: Testing & Documentation (Week 3)
- [ ] Write comprehensive unit tests
- [ ] Create integration tests
- [ ] Test with real portfolio data
- [ ] Write user guide
- [ ] Add API documentation
- [ ] Create example notebooks

## Integration Points

### 1. Portfolio Hub Integration
Add factor analysis tab to existing Portfolio Hub:
```python
# pages/4_portfolio_hub.py
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Overview",
    "📈 Performance", 
    "⚖️ Rebalancing",
    "🎯 Factor Analysis"  # NEW
])
```

### 2. Security Selection Integration
Use factor scores to enhance liquidation decisions:
```python
# security_selection.py
def score_securities_for_liquidation(...):
    # Add factor-based scoring
    if factor_data:
        # Prefer selling low-quality, low-momentum positions
        quality_penalty = (100 - factor_data.quality_score) * 0.1
        momentum_penalty = (100 - factor_data.momentum_score) * 0.1
```

### 3. Rebalancing Integration
Factor-aware rebalancing recommendations:
```python
# portfolio_rebalancing.py
def generate_rebalancing_plan(...):
    # Consider factor exposures
    if factor_exposure.value_tilt > 20:
        recommendations.append("Consider reducing value tilt")
```

## Data Quality Handling

**Missing Data Strategy:**
1. **Complete Data** (all metrics available): Use full scoring
2. **Partial Data** (some metrics missing): Use available metrics, mark as "partial"
3. **Limited Data** (< 50% metrics): Use simplified scoring, mark as "limited"
4. **No Data** (ETFs, Mutual Funds): Use category averages or skip factor analysis

**Cache Strategy:**
- Cache factor data for 24 hours
- Refresh on user request
- Store in SQLite database
- Implement LRU eviction

## Performance Considerations

**Optimization Strategies:**
1. **Batch API Calls**: Fetch multiple securities in parallel
2. **Caching**: Store factor data locally
3. **Lazy Loading**: Only fetch when needed
4. **Progressive Enhancement**: Show basic data first, enrich later
5. **Background Updates**: Refresh cache in background

**Expected Performance:**
- Initial load (10 securities): < 5 seconds
- Cached load: < 1 second
- Large portfolio (50 securities): < 15 seconds
- Background refresh: Non-blocking

## Testing Strategy

### Unit Tests
- Factor data fetching with mocked API
- Scoring algorithms with known inputs
- Portfolio aggregation logic
- Edge cases (missing data, extreme values)

### Integration Tests
- Real Yahoo Finance API calls
- Full portfolio analysis workflow
- UI rendering and interaction
- Performance benchmarks

### Validation Tests
- Compare factor scores to known benchmarks
- Validate style classifications
- Check mathematical correctness
- Verify data quality indicators

## Success Metrics

**Functionality:**
- ✅ Fetch factor data for 95%+ of stocks
- ✅ Calculate factor scores accurately
- ✅ Classify portfolio style correctly
- ✅ Generate actionable insights

**Performance:**
- ✅ Load time < 5 seconds for typical portfolio
- ✅ Cache hit rate > 80%
- ✅ API error rate < 5%

**User Experience:**
- ✅ Clear, intuitive visualizations
- ✅ Actionable recommendations
- ✅ Responsive UI
- ✅ Helpful documentation

## Risk Mitigation

**API Limitations:**
- Yahoo Finance rate limits: Use caching, batch requests
- Data availability: Graceful degradation for missing data
- API changes: Version checking, fallback strategies

**Data Quality:**
- Outliers: Cap extreme values at 99th percentile
- Stale data: Show last update timestamp
- Incomplete data: Clear quality indicators

**Performance:**
- Large portfolios: Pagination, lazy loading
- Slow API: Background loading, progress indicators
- Memory usage: Stream processing for large datasets

## Next Steps

1. **Immediate**: Create `portfolio_factors.py` with core data classes
2. **Week 1**: Implement data fetching and scoring algorithms
3. **Week 2**: Build portfolio analysis and UI components
4. **Week 3**: Testing, documentation, and refinement

## Dependencies

**Required Packages:**
- `yfinance` - Yahoo Finance API (already installed)
- `pandas` - Data manipulation (already installed)
- `numpy` - Numerical calculations (already installed)
- `streamlit` - UI components (already installed)

**Optional Enhancements:**
- `plotly` - Interactive charts (already installed)
- `scipy` - Statistical analysis (for percentile ranking)
- `sklearn` - Factor analysis (for advanced attribution)

## References

- Fama-French Factor Models
- Morningstar Style Box methodology
- Academic research on factor investing
- Industry best practices for factor analysis