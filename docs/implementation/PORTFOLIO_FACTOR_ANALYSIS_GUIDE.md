# Portfolio Factor Analysis Guide

## Overview

The Portfolio Factor Analysis feature provides deep insights into your portfolio's investment style and characteristics through multi-factor analysis. It evaluates holdings across four key investment factors: Value, Growth, Momentum, and Quality.

## Key Features

### 1. **Multi-Factor Scoring System**
- **Value Factor (30% weight)**: Identifies undervalued stocks using P/E and P/B ratios
- **Growth Factor (25% weight)**: Measures earnings and revenue growth potential
- **Momentum Factor (25% weight)**: Analyzes price trends and relative strength
- **Quality Factor (25% weight)**: Evaluates financial health through ROE and profit margins

### 2. **Portfolio-Level Analysis**
- Aggregated factor exposures weighted by market value
- Style classification (Value/Growth/Blend/Quality/Momentum/Balanced)
- Factor tilt analysis showing deviations from neutral (50)
- Concentration metrics and diversification insights

### 3. **Visual Analytics**
- **Radar Chart**: 360° view of factor exposures
- **Factor Tilts**: Bar chart showing over/under-weighting
- **Style Classification**: Primary and secondary style identification
- **Top Holdings**: Best performers in each factor category
- **Detailed Table**: Complete holdings with factor scores and progress bars

### 4. **Performance Optimization**
- SQLite caching system with 24-hour TTL
- LRU eviction for memory management
- Batch processing for multiple holdings
- Graceful error handling for missing data

## Accessing Factor Analysis

1. Navigate to **Portfolio Hub** page
2. Select the **Factor Analysis** tab
3. Choose month and year for analysis
4. Click **Analyze Portfolio Factors**

## Understanding Factor Scores

### Score Range: 0-100
- **0-30**: Low exposure (defensive/conservative)
- **30-50**: Below average exposure
- **50**: Neutral/Market average
- **50-70**: Above average exposure
- **70-100**: High exposure (aggressive)

### Factor Definitions

#### Value Factor
Measures how undervalued a stock is relative to fundamentals:
- **P/E Ratio**: Price-to-Earnings (lower is better)
- **P/B Ratio**: Price-to-Book (lower is better)
- **High Score**: Stock trading below intrinsic value
- **Low Score**: Stock may be overvalued

#### Growth Factor
Evaluates company's growth trajectory:
- **Earnings Growth**: Year-over-year EPS growth
- **Revenue Growth**: Top-line expansion rate
- **High Score**: Strong growth momentum
- **Low Score**: Mature/declining growth

#### Momentum Factor
Analyzes price trends and market sentiment:
- **6-Month Return**: Recent price performance
- **Relative Strength**: Performance vs. market
- **High Score**: Strong upward trend
- **Low Score**: Weak or declining trend

#### Quality Factor
Assesses financial strength and stability:
- **ROE**: Return on Equity (profitability)
- **Profit Margin**: Operating efficiency
- **High Score**: Strong fundamentals
- **Low Score**: Weaker financial position

## Portfolio Style Classification

### Primary Styles

1. **Value Portfolio** (Value > 60)
   - Focus on undervalued stocks
   - Lower P/E and P/B ratios
   - Defensive positioning
   - Income-oriented

2. **Growth Portfolio** (Growth > 60)
   - Emphasis on expanding companies
   - Higher earnings growth
   - Aggressive positioning
   - Capital appreciation focus

3. **Blend Portfolio** (Value + Growth > 110)
   - Balanced value/growth mix
   - Moderate risk profile
   - Diversified approach

4. **Quality Portfolio** (Quality > 60)
   - High-quality companies
   - Strong fundamentals
   - Lower volatility
   - Consistent performance

5. **Momentum Portfolio** (Momentum > 60)
   - Trend-following strategy
   - Recent outperformers
   - Higher turnover potential
   - Market-timing oriented

6. **Balanced Portfolio** (All factors 40-60)
   - Neutral across all factors
   - Maximum diversification
   - Market-representative

### Style Purity
Measures how strongly the portfolio aligns with its primary style:
- **80-100%**: Pure style (highly concentrated)
- **60-80%**: Strong style bias
- **40-60%**: Moderate style bias
- **<40%**: Weak style definition

## Interpreting Results

### Factor Exposure Analysis

**Example Portfolio:**
```
Value:     45 (Slight underweight)
Growth:    65 (Overweight)
Momentum:  55 (Neutral)
Quality:   70 (Strong overweight)
```

**Interpretation:**
- Growth-oriented with quality emphasis
- Less focus on value opportunities
- Balanced momentum exposure
- Higher risk/return profile

### Factor Tilts

Tilts show deviation from neutral (50):
- **+20 tilt**: Significantly overweight
- **+10 tilt**: Moderately overweight
- **0 tilt**: Neutral positioning
- **-10 tilt**: Moderately underweight
- **-20 tilt**: Significantly underweight

### Coverage Metrics

- **Analyzed Holdings**: Number of stocks with factor data
- **Total Holdings**: All portfolio positions
- **Coverage %**: Percentage successfully analyzed
- **Target**: >80% coverage for reliable analysis

## Use Cases

### 1. Portfolio Rebalancing
- Identify factor imbalances
- Adjust holdings to target style
- Maintain desired risk profile

### 2. Risk Management
- Monitor factor concentration
- Detect style drift
- Ensure diversification

### 3. Performance Attribution
- Understand return drivers
- Identify successful factors
- Optimize factor allocation

### 4. Tax-Loss Harvesting
- Find underperforming factors
- Identify replacement candidates
- Maintain factor exposure

### 5. Strategic Asset Allocation
- Align with investment goals
- Match risk tolerance
- Implement factor-based strategies

## Data Sources and Caching

### Yahoo Finance Integration
- Real-time fundamental data
- Historical price information
- Automatic data refresh

### Caching System
- **Cache Duration**: 24 hours
- **Storage**: SQLite database (`factor_cache.db`)
- **Eviction**: LRU (Least Recently Used)
- **Capacity**: 1,000 entries
- **Benefits**: Faster analysis, reduced API calls

### Cache Management
```python
# Clear cache if needed
from portfolio_factors import clear_factor_cache
clear_factor_cache()

# Check cache statistics
from portfolio_factors import get_cache_stats
stats = get_cache_stats()
print(f"Entries: {stats['entries']}, Hit rate: {stats['hit_rate']}")
```

## Technical Implementation

### Core Module: `portfolio_factors.py`

**Key Functions:**
- `fetch_factor_data(symbol)`: Retrieve factor metrics for a security
- `calculate_portfolio_factor_exposure(portfolio_df, factor_data)`: Aggregate portfolio-level analysis
- `score_value_factor(metrics)`: Calculate value score
- `score_growth_factor(metrics)`: Calculate growth score
- `score_momentum_factor(metrics)`: Calculate momentum score
- `score_quality_factor(metrics)`: Calculate quality score

**Data Classes:**
- `FactorMetrics`: Individual security factor data
- `PortfolioFactorExposure`: Portfolio-level factor analysis
- `FactorAttribution`: Performance attribution by factor
- `FactorDrift`: Historical factor drift tracking

### UI Component: `components/portfolio_factor_analysis.py`

**Rendering Functions:**
- `render_factor_analysis_tab()`: Main UI entry point
- `_render_summary_cards()`: Key metrics display
- `_render_factor_radar_chart()`: Visual factor exposure
- `_render_factor_tilts()`: Tilt analysis chart
- `_render_style_classification()`: Style identification
- `_render_top_holdings_by_factor()`: Top performers
- `_render_holdings_detail_table()`: Complete holdings table

## Best Practices

### 1. Regular Analysis
- Review factor exposure monthly
- Track style drift over time
- Adjust as market conditions change

### 2. Diversification
- Avoid extreme factor concentration (>80)
- Maintain balanced exposure across factors
- Consider correlation between factors

### 3. Alignment with Goals
- Match factor profile to investment objectives
- Consider time horizon and risk tolerance
- Adjust factors for life stage

### 4. Rebalancing Strategy
- Use factor analysis to guide rebalancing
- Maintain target factor exposures
- Consider tax implications

### 5. Performance Monitoring
- Track which factors drive returns
- Identify successful factor bets
- Learn from underperforming factors

## Troubleshooting

### Issue: Low Coverage Percentage
**Cause**: Missing data for some holdings
**Solution**: 
- Check ticker symbols are correct
- Verify holdings are publicly traded
- Wait for cache refresh (24 hours)

### Issue: Unexpected Factor Scores
**Cause**: Stale data or market changes
**Solution**:
- Clear cache and re-analyze
- Verify data sources
- Check for corporate actions (splits, mergers)

### Issue: Slow Analysis
**Cause**: First-time data fetch or cache miss
**Solution**:
- Wait for initial data load
- Subsequent analyses will be faster
- Consider analyzing fewer holdings

## Integration with Other Features

### Portfolio Rebalancing
Factor analysis informs rebalancing decisions:
- Identify overweight/underweight factors
- Select securities to buy/sell
- Maintain target factor profile

### Tax Harvesting
Factor scores help identify candidates:
- Find underperforming securities
- Maintain factor exposure with replacements
- Optimize tax-loss harvesting

### Withdrawal Strategy
Factor analysis guides liquidation:
- Sell from overweight factors
- Preserve desired factor balance
- Minimize portfolio disruption

## Advanced Topics

### Factor Correlation
Factors can be correlated:
- Value and Quality often align
- Growth and Momentum tend to correlate
- Consider factor interactions

### Market Cycles
Factor performance varies by cycle:
- Value outperforms in recoveries
- Growth leads in expansions
- Quality shines in downturns
- Momentum works in trends

### Factor Timing
Strategic factor allocation:
- Overweight factors expected to outperform
- Underweight factors expected to lag
- Requires market insight and discipline

## API Reference

### Main Functions

```python
from portfolio_factors import (
    fetch_factor_data,
    calculate_portfolio_factor_exposure,
    clear_factor_cache,
    get_cache_stats
)

# Fetch data for a single security
metrics = fetch_factor_data('AAPL', use_cache=True)

# Analyze portfolio
exposure = calculate_portfolio_factor_exposure(
    portfolio_df=df,
    factor_data=factor_dict
)

# Cache management
clear_factor_cache()
stats = get_cache_stats()
```

### Data Structures

```python
# FactorMetrics
@dataclass
class FactorMetrics:
    symbol: str
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    roe: Optional[float]
    profit_margin: Optional[float]
    earnings_growth: Optional[float]
    revenue_growth: Optional[float]
    momentum_6m: Optional[float]
    value_score: float
    growth_score: float
    momentum_score: float
    quality_score: float

# PortfolioFactorExposure
@dataclass
class PortfolioFactorExposure:
    value_exposure: float
    growth_exposure: float
    momentum_exposure: float
    quality_exposure: float
    primary_style: PortfolioStyle
    secondary_style: Optional[PortfolioStyle]
    style_purity: float
    factor_concentration: float
    # ... additional fields
```

## Support and Resources

### Documentation
- [Portfolio Rebalancing Guide](../user/PORTFOLIO_REBALANCING_GUIDE.md)
- [Tax Harvesting Guide](TAX_HARVESTING_GUIDE.md)
- [Portfolio Analytics Guide](../user/PORTFOLIO_ANALYTICS_GUIDE.md)

### Testing
- Run tests: `pytest test_portfolio_factors.py -v`
- Integration tests: `pytest test_portfolio_hub_integration.py -v`

### Logging
Factor analysis logs to `logs/portfolio_factors.log`:
- Data fetch operations
- Cache hits/misses
- Calculation results
- Error conditions

## Conclusion

Portfolio Factor Analysis provides powerful insights into your investment strategy. By understanding your portfolio's factor exposures, you can:

- Make informed rebalancing decisions
- Manage risk more effectively
- Align investments with goals
- Optimize tax efficiency
- Track performance drivers

Regular factor analysis helps maintain a disciplined, data-driven investment approach aligned with your long-term objectives.