# Portfolio Analytics Guide

## Overview

The Portfolio Analytics module (`portfolio_analytics.py`) provides comprehensive performance measurement and risk analysis for your investment portfolio. It calculates industry-standard metrics used by professional portfolio managers and financial advisors.

**Key Features:**
- Time-weighted and money-weighted returns
- Risk-adjusted performance metrics (Sharpe, Sortino ratios)
- Drawdown analysis and recovery tracking
- Contribution vs. growth attribution
- Benchmark comparison (S&P 500, custom indices)
- Alpha and beta calculation

---

## Table of Contents

1. [Performance Metrics](#performance-metrics)
2. [Risk Metrics](#risk-metrics)
3. [Drawdown Analysis](#drawdown-analysis)
4. [Attribution Analysis](#attribution-analysis)
5. [Benchmark Comparison](#benchmark-comparison)
6. [Usage Examples](#usage-examples)
7. [Interpreting Results](#interpreting-results)
8. [Best Practices](#best-practices)

---

## Performance Metrics

### Time-Weighted Return (TWR)

**What it measures:** The compound rate of growth in your portfolio, eliminating the distorting effects of cash flows (contributions and withdrawals).

**When to use:** 
- Comparing your portfolio's performance to benchmarks
- Evaluating your investment manager's skill
- Measuring how well your investment strategy performed

**Formula:**
```
TWR = [(1 + R₁) × (1 + R₂) × ... × (1 + Rₙ)]^(1/years) - 1
```

**Example:**
```python
from portfolio_analytics import calculate_time_weighted_return

# Portfolio values over time
portfolio_values = pd.Series([
    100000,  # Jan 2024
    102000,  # Feb 2024
    105000,  # Mar 2024
    # ...
], index=pd.date_range('2024-01-01', periods=12, freq='ME'))

# Calculate annualized TWR
twr = calculate_time_weighted_return(portfolio_values, annualize=True)
print(f"Time-Weighted Return: {twr:.2%}")  # e.g., "7.50%"
```

**Interpretation:**
- **Positive TWR:** Your investments grew in value
- **Negative TWR:** Your investments declined in value
- **TWR > Benchmark:** You outperformed the market
- **TWR < Benchmark:** You underperformed the market

---

### Money-Weighted Return (MWR/IRR)

**What it measures:** The actual return you experienced, accounting for the timing and size of your contributions and withdrawals.

**When to use:**
- Understanding your personal investment experience
- Evaluating whether your timing of contributions helped or hurt
- Calculating the true growth rate of your wealth

**Formula:**
```
NPV = Σ [CFₜ / (1 + MWR)^t] = 0
```

**Example:**
```python
from portfolio_analytics import calculate_money_weighted_return

# Portfolio values and cash flows
portfolio_values = pd.Series([...], index=dates)
contributions = pd.Series([5000, 5000, 5000, ...], index=dates)
withdrawals = pd.Series([0, 0, 2000, ...], index=dates)

cash_flows = contributions - withdrawals

# Calculate annualized MWR
mwr = calculate_money_weighted_return(portfolio_values, cash_flows, annualize=True)
print(f"Money-Weighted Return: {mwr:.2%}")  # e.g., "6.25%"
```

**Interpretation:**
- **MWR > TWR:** Your timing of contributions was beneficial (bought low)
- **MWR < TWR:** Your timing of contributions was detrimental (bought high)
- **MWR ≈ TWR:** Timing had minimal impact

---

## Risk Metrics

### Volatility (Standard Deviation)

**What it measures:** The variability of your portfolio's returns. Higher volatility means more unpredictable returns.

**Formula:**
```
σ = √[Σ(Rᵢ - R̄)² / (n-1)]
```

**Example:**
```python
from portfolio_analytics import calculate_volatility

# Calculate monthly returns
returns = portfolio_values.pct_change().dropna()

# Calculate annualized volatility
volatility = calculate_volatility(returns, annualize=True)
print(f"Annualized Volatility: {volatility:.2%}")  # e.g., "15.50%"
```

**Interpretation:**
- **< 10%:** Low volatility (conservative portfolio)
- **10-20%:** Moderate volatility (balanced portfolio)
- **> 20%:** High volatility (aggressive portfolio)

---

### Sharpe Ratio

**What it measures:** Risk-adjusted return. How much excess return you earned per unit of risk taken.

**Formula:**
```
Sharpe Ratio = (Portfolio Return - Risk-Free Rate) / Portfolio Volatility
```

**Example:**
```python
from portfolio_analytics import calculate_sharpe_ratio

returns = portfolio_values.pct_change().dropna()
sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.04, annualize=True)
print(f"Sharpe Ratio: {sharpe:.2f}")  # e.g., "1.25"
```

**Interpretation:**
- **< 0:** Returns below risk-free rate (poor performance)
- **0 - 1:** Acceptable risk-adjusted returns
- **1 - 2:** Good risk-adjusted returns
- **> 2:** Excellent risk-adjusted returns

**Rule of Thumb:**
- Sharpe > 1.0 is generally considered good
- Sharpe > 2.0 is excellent
- Sharpe > 3.0 is exceptional (rare)

---

### Sortino Ratio

**What it measures:** Similar to Sharpe ratio, but only considers downside volatility (negative returns). Better for investors who don't mind upside volatility.

**Formula:**
```
Sortino Ratio = (Portfolio Return - Risk-Free Rate) / Downside Deviation
```

**Example:**
```python
from portfolio_analytics import calculate_sortino_ratio

returns = portfolio_values.pct_change().dropna()
sortino = calculate_sortino_ratio(returns, risk_free_rate=0.04, annualize=True)
print(f"Sortino Ratio: {sortino:.2f}")  # e.g., "1.75"
```

**Interpretation:**
- Sortino ratio is typically higher than Sharpe ratio
- Same thresholds as Sharpe ratio apply
- Preferred metric for asymmetric return distributions

---

## Drawdown Analysis

### Maximum Drawdown

**What it measures:** The largest peak-to-trough decline in your portfolio value. Shows the worst-case loss you experienced.

**Example:**
```python
from portfolio_analytics import find_max_drawdown

max_dd_pct, start_date, end_date, recovery_days = find_max_drawdown(portfolio_values)

print(f"Maximum Drawdown: {max_dd_pct:.2f}%")
print(f"Drawdown Period: {start_date} to {end_date}")
print(f"Recovery Time: {recovery_days} days")
```

**Interpretation:**
- **< -10%:** Mild drawdown (normal market volatility)
- **-10% to -20%:** Moderate drawdown (correction)
- **-20% to -40%:** Severe drawdown (bear market)
- **> -40%:** Extreme drawdown (market crash)

**Recovery Time:**
- **< 6 months:** Quick recovery
- **6-12 months:** Normal recovery
- **1-2 years:** Slow recovery
- **> 2 years:** Extended recovery

---

### Drawdown Periods

**What it measures:** All significant decline periods in your portfolio, not just the maximum.

**Example:**
```python
from portfolio_analytics import find_all_drawdown_periods

drawdown_periods = find_all_drawdown_periods(
    portfolio_values,
    min_drawdown_pct=-5.0  # Only show drawdowns > 5%
)

for dd in drawdown_periods:
    print(f"Drawdown: {dd.drawdown_pct:.2f}%")
    print(f"Duration: {dd.duration_days} days")
    print(f"Recovery: {dd.recovery_days} days" if dd.recovery_days else "Not recovered")
    print("---")
```

---

## Attribution Analysis

**What it measures:** Breaks down your portfolio's growth into contributions, withdrawals, and investment returns.

**Example:**
```python
from portfolio_analytics import calculate_attribution

total_contrib, total_withdr, inv_growth = calculate_attribution(
    portfolio_values,
    contributions,
    withdrawals
)

print(f"Total Contributions: ${total_contrib:,.0f}")
print(f"Total Withdrawals: ${total_withdr:,.0f}")
print(f"Investment Growth: ${inv_growth:,.0f}")

# Calculate percentages
ending_value = portfolio_values.iloc[-1]
contrib_pct = (total_contrib / ending_value) * 100
growth_pct = (inv_growth / ending_value) * 100

print(f"\nContributions: {contrib_pct:.1f}% of portfolio")
print(f"Investment Growth: {growth_pct:.1f}% of portfolio")
```

**Interpretation:**
- High contribution % = You're building wealth through savings
- High growth % = Your investments are performing well
- Negative growth % = Your investments are losing money

---

## Benchmark Comparison

### Alpha and Beta

**Alpha:** Excess return above what would be predicted by your portfolio's beta.
**Beta:** Sensitivity to market movements (1.0 = moves with market).

**Example:**
```python
from portfolio_analytics import calculate_alpha_beta

portfolio_returns = portfolio_values.pct_change().dropna()
benchmark_returns = sp500_values.pct_change().dropna()

alpha, beta = calculate_alpha_beta(
    portfolio_returns,
    benchmark_returns,
    risk_free_rate=0.04
)

print(f"Alpha: {alpha:.2%}")  # e.g., "2.50%"
print(f"Beta: {beta:.2f}")    # e.g., "1.15"
```

**Beta Interpretation:**
- **Beta < 1.0:** Less volatile than market (defensive)
- **Beta = 1.0:** Moves with market
- **Beta > 1.0:** More volatile than market (aggressive)

**Alpha Interpretation:**
- **Alpha > 0:** Outperforming risk-adjusted expectations
- **Alpha = 0:** Performing as expected
- **Alpha < 0:** Underperforming risk-adjusted expectations

---

## Usage Examples

### Complete Portfolio Analysis

```python
from portfolio_analytics import calculate_portfolio_analytics
import pandas as pd

# Load your portfolio data
portfolio_values = pd.Series([...], index=dates)
contributions = pd.Series([...], index=dates)
withdrawals = pd.Series([...], index=dates)

# Calculate all metrics at once
metrics = calculate_portfolio_analytics(
    portfolio_values,
    contributions=contributions,
    withdrawals=withdrawals,
    benchmark_symbol='^GSPC',  # S&P 500
    risk_free_rate=0.04
)

# Display results
print("=== PERFORMANCE METRICS ===")
print(f"Time-Weighted Return: {metrics.time_weighted_return:.2%}")
print(f"Money-Weighted Return: {metrics.money_weighted_return:.2%}")
print(f"Total Return: {metrics.total_return_pct:.2f}%")

print("\n=== RISK METRICS ===")
print(f"Volatility: {metrics.volatility:.2%}")
print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
print(f"Sortino Ratio: {metrics.sortino_ratio:.2f}")

print("\n=== DRAWDOWN ANALYSIS ===")
print(f"Maximum Drawdown: {metrics.max_drawdown_pct:.2f}%")
print(f"Current Drawdown: {metrics.current_drawdown_pct:.2f}%")
if metrics.recovery_days:
    print(f"Recovery Time: {metrics.recovery_days} days")

print("\n=== ATTRIBUTION ===")
print(f"Contributions: ${metrics.total_contributions:,.0f}")
print(f"Withdrawals: ${metrics.total_withdrawals:,.0f}")
print(f"Investment Growth: ${metrics.investment_growth:,.0f}")

if metrics.benchmark_return:
    print("\n=== BENCHMARK COMPARISON ===")
    print(f"Benchmark Return: {metrics.benchmark_return:.2%}")
    print(f"Alpha: {metrics.alpha:.2%}")
    print(f"Beta: {metrics.beta:.2f}")
```

---

## Interpreting Results

### Example Portfolio Report

```
Portfolio: Retirement Account
Period: Jan 2024 - Dec 2024
Starting Value: $500,000
Ending Value: $575,000

=== PERFORMANCE ===
Time-Weighted Return: 8.50%
Money-Weighted Return: 7.25%
Total Return: 15.00%

Analysis: TWR > MWR indicates you made contributions when prices were higher,
slightly reducing your personal return. However, both returns are positive
and above the risk-free rate.

=== RISK ===
Volatility: 12.50%
Sharpe Ratio: 1.35
Sortino Ratio: 1.85

Analysis: Moderate volatility with good risk-adjusted returns. Sharpe ratio
above 1.0 indicates you're being adequately compensated for the risk taken.

=== DRAWDOWN ===
Maximum Drawdown: -15.25%
Recovery Time: 4 months
Current Drawdown: 0.00%

Analysis: Experienced a moderate correction but recovered quickly. Currently
at all-time highs.

=== ATTRIBUTION ===
Contributions: $50,000 (8.7% of portfolio)
Investment Growth: $25,000 (4.3% of portfolio)

Analysis: Most of your portfolio growth came from contributions. Consider
whether your asset allocation is appropriate for your goals.

=== BENCHMARK (S&P 500) ===
Benchmark Return: 7.50%
Alpha: +0.75%
Beta: 1.10

Analysis: You outperformed the S&P 500 by 1.00% (8.50% vs 7.50%). Your
portfolio is 10% more volatile than the market (beta 1.10) but generated
positive alpha, indicating good security selection or timing.
```

---

## Best Practices

### 1. Use Appropriate Time Periods

- **Short-term (< 1 year):** Returns may be misleading due to volatility
- **Medium-term (1-3 years):** Good for evaluating recent strategy changes
- **Long-term (3+ years):** Best for evaluating overall investment approach

### 2. Compare Apples to Apples

- Compare your portfolio to an appropriate benchmark
- If you hold 60% stocks / 40% bonds, compare to a 60/40 index
- Don't compare a conservative portfolio to the S&P 500

### 3. Consider Risk-Adjusted Returns

- High returns with high volatility may not be better than moderate returns with low volatility
- Use Sharpe and Sortino ratios to evaluate risk-adjusted performance

### 4. Track Drawdowns

- Know your maximum historical drawdown
- Ensure you can emotionally handle similar declines in the future
- Consider reducing risk if drawdowns exceed your tolerance

### 5. Understand Attribution

- If most growth comes from contributions, you're in accumulation phase
- If most growth comes from returns, your investments are working well
- Both are important for long-term wealth building

### 6. Monitor Alpha and Beta

- Positive alpha indicates skill or good strategy
- Beta shows your portfolio's risk profile
- Adjust allocation if beta doesn't match your risk tolerance

### 7. Regular Review

- Review analytics quarterly or annually
- Look for trends, not single data points
- Adjust strategy based on changing goals and market conditions

---

## Common Questions

### Q: Why is my MWR lower than my TWR?

**A:** This typically means you made larger contributions when prices were higher (buying high). While this reduces your personal return, it's often unavoidable with regular contributions. Focus on consistent investing rather than timing the market.

### Q: What's a good Sharpe ratio?

**A:** 
- < 1.0: Below average
- 1.0 - 2.0: Good
- > 2.0: Excellent
- > 3.0: Exceptional (rare)

### Q: How much drawdown should I expect?

**A:**
- Conservative (bonds): -5% to -15%
- Balanced (60/40): -15% to -25%
- Aggressive (stocks): -25% to -50%

### Q: Should I worry about negative alpha?

**A:** Not necessarily. Small negative alpha (< -1%) could be due to fees or market timing. Consistent large negative alpha suggests you should reconsider your strategy or use index funds.

### Q: How often should I calculate these metrics?

**A:** Quarterly or annually is sufficient. More frequent calculations can lead to overreacting to short-term volatility.

---

## Technical Notes

### Data Requirements

- **Minimum:** 2 data points (start and end values)
- **Recommended:** Monthly data for at least 1 year
- **Optimal:** Monthly data for 3+ years

### Assumptions

- Returns are calculated using adjusted close prices
- Contributions/withdrawals occur at end of period
- Risk-free rate defaults to 4% (10-year Treasury)
- Benchmark defaults to S&P 500 (^GSPC)

### Limitations

- Past performance doesn't guarantee future results
- Metrics assume normal distribution of returns (may not hold during crises)
- Short time periods may not be statistically significant
- Doesn't account for taxes or transaction costs

---

## Related Documentation

- [Portfolio Rebalancing Guide](PORTFOLIO_REBALANCING_GUIDE.md)
- [Tax Harvesting Guide](tax_harvesting.py)
- [Monte Carlo Simulation](monte_carlo.py)
- [Withdrawal Strategy Guide](WITHDRAWAL_STRATEGY_PRODUCTION_GUIDE.md)

---

## Support

For questions or issues with portfolio analytics:
1. Check the test file (`test_portfolio_analytics.py`) for usage examples
2. Review the module docstrings for detailed parameter descriptions
3. Consult financial planning resources for interpretation guidance

**Disclaimer:** This tool provides analytical metrics for informational purposes only. It does not constitute financial advice. Consult with a qualified financial advisor for personalized investment guidance.