# Portfolio Market Indicators Guide

## Overview

The Portfolio Market Indicators feature adds real-time market condition analysis for each security in your portfolio. This helps you make informed decisions about buying, holding, or selling positions based on technical analysis using moving averages.

## Features

### 1. Individual Security Analysis
Each security in your portfolio is analyzed using:
- **10-Week Moving Average (Short-term trend)**
- **50-Week Moving Average (Long-term trend)**
- **Current Price Position**
- **Trend Slopes** (rate of change)

### 2. Market Condition Categories

The system classifies each security into one of six conditions:

| Condition | Emoji | Description | Recommendation |
|-----------|-------|-------------|----------------|
| **Strong Buy** | 🚀 | Both MAs trending up, price above both | Strong uptrend - consider buying |
| **Buy** | 📈 | Both MAs trending up | Uptrend - favorable |
| **Hold** | ➖ | Mixed signals or neutral | Hold position |
| **Caution** | ⚠️ | Short-term MA down, long-term MA up | Early warning - monitor closely |
| **Sell** | 📉 | Both MAs trending down | Downtrend - consider reducing |
| **Unknown** | ❓ | Unable to calculate (insufficient data) | N/A |

### 3. Holdings Tab Integration

The market indicators are displayed in the **Holdings tab** of the Portfolio Hub:

#### Main Data Table
- A new **"Market Indicator"** column shows the emoji and condition for each security
- This column is read-only and automatically calculated
- Updates are cached for 1 hour to improve performance

#### Data Summary Expander
- Shows count of securities in each market condition
- Provides quick portfolio-wide market sentiment overview

#### Market Indicator Details Expander
- Detailed analysis for each security including:
  - Current price
  - 10-week and 50-week moving averages
  - Trend directions (up/down/neutral)
  - Confidence score (0-100%)
  - Specific recommendation

## Technical Details

### Algorithm

The market indicator algorithm is based on the short-term market forecast methodology:

1. **Fetch Historical Data**: Retrieves 50+ weeks of price history for each security
2. **Calculate Moving Averages**: 
   - 10-week MA for short-term trend
   - 50-week MA for long-term trend
3. **Determine Trend Direction**: 
   - Calculates slope (rate of change) over 4-week lookback period
   - Uses 0.05% per week threshold to filter noise
4. **Classify Condition**: Based on combination of:
   - Short-term MA trend (up/down/neutral)
   - Long-term MA trend (up/down/neutral)
   - Current price position relative to MAs
5. **Calculate Confidence**: Based on magnitude of trend slopes

### Performance Optimization

- **Caching**: Indicators are cached for 1 hour per security
- **Batch Processing**: All portfolio securities are analyzed together
- **Efficient Data Fetching**: Uses yfinance with optimized date ranges

### Special Cases

- **Cash Holdings** (MF:CASH, CASH): Always show as "Hold" with 💵 emoji
- **Insufficient Data**: Securities with less than 50 weeks of history show as "Unknown"
- **Data Fetch Failures**: Network issues result in "Unknown" status

## Usage

### Viewing Market Indicators

1. Navigate to **Portfolio Hub** → **Holdings tab**
2. The market indicator column appears automatically in the holdings table
3. Expand **"Market Indicator Details"** for comprehensive analysis

### Interpreting Indicators

**Strong Buy (🚀)**
- Both short and long-term trends are positive
- Price is above both moving averages
- Strong momentum - consider adding to position

**Buy (📈)**
- Both trends are positive
- Favorable market conditions
- Good time to hold or accumulate

**Hold (➖)**
- Mixed or neutral signals
- Maintain current position
- Wait for clearer direction

**Caution (⚠️)**
- Short-term weakness appearing
- Long-term trend still positive
- Early warning - monitor closely
- Consider taking profits or tightening stops

**Sell (📉)**
- Both trends are negative
- Downtrend established
- Consider reducing exposure or exiting

### Best Practices

1. **Don't Rely Solely on Indicators**: Use as one input among many (fundamentals, news, personal goals)
2. **Consider Your Time Horizon**: Short-term indicators may not align with long-term investment goals
3. **Review Regularly**: Market conditions change - check indicators weekly or monthly
4. **Use Confidence Scores**: Higher confidence (>50%) indicates stronger signals
5. **Account for Volatility**: Some securities are naturally more volatile than others

## Integration with Other Features

### Bucket Strategy
- Market indicators can inform bucket rebalancing decisions
- Caution/Sell signals may trigger defensive positioning
- Strong Buy signals may support aggressive allocation

### Tax Loss Harvesting
- Sell signals combined with losses may indicate good harvesting opportunities
- Caution signals can help identify positions to monitor for tax loss harvesting

### Rebalancing
- Market indicators provide context for rebalancing decisions
- Strong trends may justify delaying rebalancing
- Weak trends may accelerate rebalancing needs

## Files Modified/Created

### New Files
- **`portfolio_market_indicators.py`**: Core indicator calculation module
- **`test_portfolio_market_indicators.py`**: Test suite for indicator functionality
- **`PORTFOLIO_MARKET_INDICATORS_GUIDE.md`**: This documentation

### Modified Files
- **`components/portfolio_holdings_editor.py`**: Added market indicator display to Holdings tab

## API Reference

### Main Functions

#### `calculate_security_indicator(symbol, short_ma_weeks=10, long_ma_weeks=50)`
Calculate market indicator for a single security.

**Parameters:**
- `symbol` (str): Ticker symbol
- `short_ma_weeks` (int): Short MA period (default: 10)
- `long_ma_weeks` (int): Long MA period (default: 50)

**Returns:**
- `SecurityIndicator` object or `None` if calculation fails

#### `get_portfolio_indicators(symbols)`
Calculate indicators for multiple securities.

**Parameters:**
- `symbols` (list[str]): List of ticker symbols

**Returns:**
- `dict`: Mapping of symbols to SecurityIndicator objects

#### `get_indicator_summary(indicator)`
Get formatted text summary of an indicator.

**Parameters:**
- `indicator` (SecurityIndicator): Indicator object

**Returns:**
- `str`: Formatted summary text

### Data Classes

#### `SecurityIndicator`
```python
@dataclass
class SecurityIndicator:
    symbol: str
    condition: SecurityMarketCondition
    short_ma: float
    long_ma: float
    current_price: float
    short_trend: str  # "up", "down", "neutral"
    long_trend: str   # "up", "down", "neutral"
    confidence: float  # 0.0-1.0
    recommendation: str
    emoji: str
    calculation_date: datetime
```

## Troubleshooting

### Indicators Show as "Unknown"
- **Cause**: Insufficient historical data or network issues
- **Solution**: Check internet connection, verify ticker symbol is correct

### Indicators Not Updating
- **Cause**: Cache is active (1-hour TTL)
- **Solution**: Wait for cache to expire or restart the application

### Slow Performance
- **Cause**: Fetching data for many securities
- **Solution**: Indicators are calculated once and cached; subsequent views are fast

### Unexpected Condition
- **Cause**: Market volatility or recent price movements
- **Solution**: Check the detailed analysis in the expander for context

## Future Enhancements

Potential improvements for future versions:

1. **Customizable MA Periods**: Allow users to adjust 10/50 week defaults
2. **Multiple Timeframes**: Add daily, monthly analysis alongside weekly
3. **Alert System**: Notify when conditions change significantly
4. **Historical Tracking**: Track condition changes over time
5. **Sector Analysis**: Aggregate indicators by sector
6. **Benchmark Comparison**: Compare security indicators to market (SPY)
7. **Export Functionality**: Export indicator analysis to CSV/PDF

## Support

For issues or questions:
1. Check this guide first
2. Review test results: `python3 test_portfolio_market_indicators.py`
3. Check logs for error messages
4. Verify yfinance is installed and working

## Version History

- **v1.0** (2026-03-12): Initial release
  - Basic indicator calculation
  - Holdings tab integration
  - Caching system
  - Test suite

---

**Made with Bob** 🤖