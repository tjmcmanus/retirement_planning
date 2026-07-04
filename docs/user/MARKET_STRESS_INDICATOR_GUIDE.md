# Market Stress Indicator Guide

## Overview

The **EventHorizonIQ Market Stress Indicator** provides real-time market stress monitoring to help you make informed portfolio decisions. This feature is integrated into the Portfolio Hub's Overview tab under "Short-Term Market Forecast."

## What is the Stress Indicator?

The EventHorizonIQ Stress Index aggregates signals from **55+ market sensors** monitoring:
- Market volatility (VIX, realized volatility)
- Credit spreads (investment grade, high yield)
- Liquidity conditions (bid-ask spreads, trading volumes)
- Market sentiment (put/call ratios, investor surveys)
- Technical indicators (breadth, momentum)

The index ranges from **0-100**, with higher values indicating greater market stress.

## Stress Level Thresholds

### 🟢 Normal (0-50)
**Status:** Market conditions are stable  
**Action:** Continue normal operations

**What to do:**
- ✅ Continue normal investment strategy
- ✅ Execute planned rebalancing
- ✅ Consider opportunistic buying
- ✅ Review weekly for changes

**Monitoring:** Check stress indicator weekly

---

### 🟡 Warning (50-70)
**Status:** Elevated stress detected  
**Action:** Flag portfolio for review

**What to do:**
- 📋 Review portfolio allocation and risk exposure
- 📋 Prepare hedge strategies (identify put options, inverse positions)
- 📋 Assess cash reserves and liquidity needs
- 📋 Review rebalancing opportunities
- 📋 Monitor daily for further deterioration

**Threshold:** Activate hedges if stress crosses 70

---

### 🔴 Critical (70-100)
**Status:** High stress conditions  
**Action:** Activate hedges immediately

**What to do:**
- ✅ Activate portfolio hedges (put options, inverse ETFs)
- ✅ Reduce equity exposure to defensive levels
- ✅ Increase cash/bond allocation
- ✅ Review stop-loss orders on volatile positions
- ✅ Consider tax-loss harvesting opportunities

**Monitor:** Check stress indicator daily until it drops below 70

## How to Use

### Accessing the Indicator

1. Navigate to **💼 Portfolio Hub**
2. Go to the **📊 Overview** tab
3. Scroll to **📡 Short-Term Market Forecast** section
4. View the Market Stress Indicator card

### Understanding the Display

The indicator card shows:

1. **Stress Index Score** (0-100)
   - Large number with color-coded emoji
   - Green (🟢) = Normal
   - Yellow (🟡) = Warning
   - Red (🔴) = Critical

2. **Current Status**
   - Regime classification (NEUTRAL, ELEVATED, CRITICAL)
   - Number of active sensors

3. **Action Required**
   - Clear, actionable recommendation based on current stress level

4. **Detailed Breakdown** (expandable)
   - Distribution of sensor states:
     - 🔴 Severe
     - 🟠 Elevated
     - 🟡 Rising
     - ⚪ Neutral
     - 🟢 Stable

### Example Scenarios

#### Scenario 1: Normal Market (Stress = 22.4)
```
🟢 22.4/100
Status: NORMAL
Regime: NEUTRAL

Action: Continue normal operations
- Execute planned rebalancing
- Consider opportunistic buying
- Review weekly
```

#### Scenario 2: Warning Level (Stress = 58.3)
```
🟡 58.3/100
Status: WARNING
Regime: ELEVATED

Action: Flag portfolio for review
- Review allocation and risk
- Prepare hedge strategies
- Monitor daily
- Activate hedges if crosses 70
```

#### Scenario 3: Critical Level (Stress = 76.8)
```
🔴 76.8/100
Status: CRITICAL
Regime: CRITICAL

Action: Activate hedges immediately
- Reduce equity exposure
- Increase cash/bonds
- Review stop-losses
- Check daily until < 70
```

## Integration with Portfolio Strategy

### Defensive Positioning

When stress crosses **50**:
1. Review your current equity allocation
2. Identify positions with high beta (market sensitivity)
3. Prepare list of hedge instruments:
   - Put options on major holdings
   - Inverse ETFs (e.g., SH, PSQ)
   - VIX calls for volatility protection

### Hedge Activation

When stress crosses **70**:
1. **Immediate Actions:**
   - Purchase put options on 20-30% of equity exposure
   - Add inverse ETF positions (5-10% of portfolio)
   - Raise cash to 15-20% of portfolio

2. **Portfolio Adjustments:**
   - Reduce high-beta stocks
   - Increase defensive sectors (utilities, consumer staples)
   - Add treasury bonds or gold

3. **Risk Management:**
   - Set stop-losses on volatile positions
   - Review margin usage
   - Ensure adequate liquidity

### Tax-Loss Harvesting

High stress periods often create tax-loss harvesting opportunities:
- Use the **Optimization** tab to identify losses
- Harvest losses while maintaining market exposure
- Replace sold positions with similar (but not substantially identical) securities

## API Details

### Endpoint
```
GET https://eventhorizoniq.com/api/stress-index
```

### Response Format
```json
{
  "stress_index": 22.4,
  "regime": "NEUTRAL",
  "sensor_count": 55,
  "breakdown": {
    "severe": 0,
    "elevated": 2,
    "rising": 8,
    "neutral": 12,
    "stable": 33
  },
  "as_of": "2026-03-16T15:30:00Z",
  "methodology": "Weighted average of all active sensor states..."
}
```

### Caching
- Data is cached for **15 minutes** to reduce API calls
- Automatic refresh when cache expires
- Manual refresh available by reloading the page

## Code Example

If you want to access the stress indicator programmatically:

```python
import requests

# Fetch current stress index
r = requests.get("https://eventhorizoniq.com/api/stress-index")
data = r.json()

print(f"Stress Index: {data['stress_index']}/100")
print(f"Regime: {data['regime']}")
print(f"Breakdown: {data['breakdown']}")

# Check thresholds
if data['stress_index'] >= 70:
    print("🔴 CRITICAL: Activate hedges!")
elif data['stress_index'] >= 50:
    print("🟡 WARNING: Review portfolio!")
else:
    print("🟢 NORMAL: Continue operations")
```

## Best Practices

### 1. Regular Monitoring
- **Normal conditions (< 50):** Check weekly
- **Warning level (50-70):** Check daily
- **Critical level (> 70):** Check multiple times per day

### 2. Don't Panic
- The stress indicator is a **warning system**, not a sell signal
- Use it to **prepare** defensive strategies, not to exit the market entirely
- Historical data shows most stress spikes are temporary

### 3. Combine with Other Indicators
- Use alongside your portfolio's moving averages (10-week, 50-week)
- Consider fundamental analysis of your holdings
- Review economic calendar for upcoming events

### 4. Document Your Actions
- Keep a log of stress levels and actions taken
- Review effectiveness after stress periods pass
- Refine your response strategy over time

### 5. Pre-Plan Your Response
- **Before stress rises:** Identify hedge instruments and target allocations
- **Create action plans:** Document specific steps for each threshold
- **Set alerts:** Use the indicator to trigger portfolio reviews

## Troubleshooting

### Indicator Not Loading
**Problem:** "Unable to fetch market stress data"

**Solutions:**
1. Check internet connection
2. Verify API endpoint is accessible
3. Wait 1-2 minutes and refresh the page
4. Check browser console for error messages

### Outdated Data
**Problem:** Data timestamp is old

**Solutions:**
1. Refresh the page to clear cache
2. Check if API is experiencing issues
3. Data updates every 15 minutes during market hours

### Unexpected Stress Levels
**Problem:** Stress level seems inconsistent with market conditions

**Solutions:**
1. Check the detailed sensor breakdown
2. Review the "as_of" timestamp
3. Consider that stress can lead market moves (early warning)
4. Compare with other volatility indicators (VIX, credit spreads)

## Technical Implementation

### Files
- **Component:** `components/market_stress_indicator.py`
- **Integration:** `components/portfolio_overview.py`
- **Tests:** `test_market_stress_indicator.py`

### Dependencies
- `requests>=2.31.0` (already in requirements.txt)
- `streamlit>=1.31.0`

### Testing
Run the test suite:
```bash
pytest test_market_stress_indicator.py -v
```

## Future Enhancements

Potential improvements for future versions:

1. **Historical Tracking**
   - Store stress levels over time
   - Chart historical stress vs portfolio performance
   - Identify patterns and correlations

2. **Custom Alerts**
   - Email/SMS notifications when thresholds crossed
   - Configurable threshold levels
   - Integration with portfolio rebalancing triggers

3. **Automated Hedging**
   - Automatic hedge recommendations based on portfolio composition
   - Integration with brokerage API for one-click hedge execution
   - Backtesting of hedge strategies

4. **Sector-Specific Stress**
   - Break down stress by market sector
   - Identify which sectors are driving overall stress
   - Sector rotation recommendations

## Support

For questions or issues:
1. Check this guide first
2. Review the test file for usage examples
3. Consult the EventHorizonIQ API documentation
4. File an issue in the project repository

---

**Made with Bob** 🤖