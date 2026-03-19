# Security Selection Guide

**Dynamic Security Selection for Intelligent Withdrawals**

## Overview

The Security Selection module provides intelligent, security-specific liquidation decisions when withdrawals are needed from your portfolio. Instead of generic account-level withdrawals, it analyzes each holding and selects the optimal securities to sell based on multiple factors.

## Key Benefits

### 1. Tax Optimization
- **Harvest losses first** - Automatically prioritizes selling positions with unrealized losses
- **Optimize gain timing** - Sells gains at 0% LTCG rate when possible
- **Minimize tax burden** - Considers holding periods and tax rates for each security
- **Wash sale avoidance** - Detects and avoids triggering wash sale rules

### 2. Portfolio Rebalancing
- **Sell overweight positions** - Automatically rebalances by selling overweight asset classes
- **Maintain target allocation** - Keeps portfolio aligned with your goals
- **Drift reduction** - Measures and improves allocation drift with each withdrawal

### 3. Cost Basis Optimization
- **FIFO tracking** - First In, First Out methodology for accurate tax basis
- **Strategic selection** - Chooses lots with optimal basis characteristics
- **Transparent tracking** - Complete audit trail of all transactions

## How It Works

### Scoring System

Each security is scored on four factors (0-100 scale):

#### 1. Tax Efficiency (30% weight)
- **100 points**: Loss positions (harvest losses)
- **90 points**: Gains at 0% LTCG rate (free step-up in basis)
- **60 points**: Gains at 15% LTCG rate
- **40 points**: Gains at 20% LTCG rate
- **20 points**: Short-term gains (ordinary income rates)

#### 2. Rebalancing (30% weight)
- **100 points**: Overweight by 10%+ (sell to rebalance)
- **80 points**: Overweight by 5-10%
- **60 points**: Overweight by 0-5%
- **40 points**: At target allocation
- **20 points**: Underweight (avoid selling)

#### 3. Liquidity (20% weight)
- **100 points**: High volume stocks/ETFs, cash
- **80 points**: Mutual funds
- **60 points**: Low volume stocks
- **40 points**: Illiquid positions

#### 4. Cost Basis (20% weight)
- **100 points**: Loss positions or high basis (low gain)
- **70 points**: Medium basis
- **40 points**: Low basis (high gain)

### Selection Algorithm

1. **Score all securities** in the account using the multi-factor system
2. **Sort by total score** (highest to lowest)
3. **Select securities** until withdrawal amount is met
4. **Handle partial shares** if needed
5. **Calculate tax impact** and rebalancing effect
6. **Generate plan** with complete details

## Usage Examples

### Example 1: Basic Withdrawal

```python
from security_selection import score_securities_for_liquidation, create_liquidation_plan

# Score securities in brokerage account
scores = score_securities_for_liquidation(
    portfolio_df=portfolio_df,
    withdrawal_amount=50000,
    account_type='Brokerage',
    target_allocation={'Cash': 10, 'Bonds': 30, 'Stocks': 60},
    current_agi=100000,
    filing_status='single',
)

# Create liquidation plan
plan = create_liquidation_plan(
    scored_securities=scores,
    withdrawal_amount=50000,
    account_type='Brokerage',
    target_allocation={'Cash': 10, 'Bonds': 30, 'Stocks': 60},
)

# View plan summary
print(plan.summary())
```

**Output:**
```
Liquidation Plan for Brokerage Account
============================================================
Total Needed: $50,000.00
Total Selected: $50,500.00
Securities to Sell: 3

Tax Impact:
  Long-term Capital Gains: $2,500.00
  Short-term Capital Gains: $0.00
  Cost Basis Returned: $48,000.00
  Estimated Tax: $375.00

Rebalancing Impact:
  Cash: 12.0% → 10.5% (-1.5%)
  Bonds: 35.0% → 32.0% (-3.0%)
  Stocks: 53.0% → 57.5% (+4.5%)
  Drift Improvement: +2.5%
```

### Example 2: Multi-Account Withdrawal

```python
from security_selection import optimize_multi_account_withdrawal

# Optimize across multiple accounts
plans = optimize_multi_account_withdrawal(
    total_needed=100000,
    portfolio_df=portfolio_df,
    account_priorities=['Brokerage', 'Traditional', 'Roth'],
    target_allocation={'Cash': 10, 'Bonds': 30, 'Stocks': 60},
    tax_context={
        'agi': 100000,
        'filing_status': 'single',
        'recent_sales': [],
    },
)

# View summary
from security_selection import format_liquidation_summary
print(format_liquidation_summary(plans))
```

**Output:**
```
Multi-Account Liquidation Summary
============================================================

Total Withdrawn: $100,000.00
Total Tax: $3,750.00
Total Securities: 6

Brokerage Account:
----------------------------------------
  Amount: $60,000.00
  Securities: 4
  Tax: $3,750.00
  Top Securities:
    • GOOGL: $25,000 (Loss harvest)
    • BND: $20,000 (Overweight)
    • AAPL: $15,000 (Tax-efficient)

Traditional Account:
----------------------------------------
  Amount: $40,000.00
  Securities: 2
  Tax: $0.00
  Top Securities:
    • VTI: $30,000 (Overweight)
    • VXUS: $10,000 (Best available)
```

### Example 3: Tax-Loss Harvesting Focus

```python
# Score securities with emphasis on loss harvesting
scores = score_securities_for_liquidation(
    portfolio_df=portfolio_df,
    withdrawal_amount=30000,
    account_type='Brokerage',
    target_allocation={'Cash': 10, 'Bonds': 30, 'Stocks': 60},
    current_agi=100000,
    filing_status='single',
)

# Filter to loss positions
loss_positions = [s for s in scores if s.unrealized_gain_loss < 0]

print(f"Found {len(loss_positions)} loss positions:")
for pos in loss_positions:
    print(f"  {pos.symbol}: ${pos.unrealized_gain_loss:,.0f} loss, "
          f"score={pos.total_score:.1f}")
```

**Output:**
```
Found 2 loss positions:
  GOOGL: $-15,000 loss, score=92.5
  TSLA: $-5,000 loss, score=88.3
```

## Integration with Withdrawal Strategy

### Stage 3: Early Retirement (Pre-Medicare)

```python
def withdraw_from_brokerage_smart(amount, state, portfolio_df, year, tax_context):
    """Smart withdrawal with security selection."""
    from security_selection import (
        score_securities_for_liquidation,
        create_liquidation_plan,
    )
    
    # Score securities
    scores = score_securities_for_liquidation(
        portfolio_df=portfolio_df,
        withdrawal_amount=amount,
        account_type='Brokerage',
        target_allocation=state['target_allocation'],
        current_agi=tax_context['agi'],
        filing_status=tax_context['filing_status'],
        recent_sales=state.get('recent_sales', []),
    )
    
    # Create plan
    plan = create_liquidation_plan(
        scores,
        amount,
        'Brokerage',
        state['target_allocation'],
    )
    
    # Update state
    state['brokerage'] -= plan.total_selected
    state['recent_sales'].extend([
        {
            'symbol': liq.symbol,
            'date': datetime(year, 12, 31),
            'gain_loss': liq.gain_loss,
        }
        for liq in plan.securities
    ])
    
    return plan.total_selected, plan
```

## Understanding the Liquidation Plan

### Plan Components

```python
@dataclass
class LiquidationPlan:
    total_needed: float              # Amount requested
    total_selected: float            # Amount actually selected
    securities: List[SecurityLiquidation]  # Securities to sell
    
    # Tax impact
    total_ltcg: float               # Long-term capital gains
    total_stcg: float               # Short-term capital gains
    total_basis_returned: float     # Tax-free basis
    estimated_tax: float            # Total estimated tax
    
    # Rebalancing impact
    pre_allocation: Dict[str, float]   # Before liquidation
    post_allocation: Dict[str, float]  # After liquidation
    drift_improvement: float           # Positive = better
    
    # Metadata
    account_type: str
    created_at: datetime
    notes: List[str]                # Warnings or recommendations
```

### Security Liquidation Details

```python
@dataclass
class SecurityLiquidation:
    symbol: str                     # Ticker symbol
    account_type: str               # Account
    shares_to_sell: float           # Shares to liquidate
    amount_to_liquidate: float      # Dollar amount
    cost_basis: float               # Tax basis
    gain_loss: float                # Realized gain/loss
    tax_impact: float               # Estimated tax
    reason: str                     # Why selected
    is_partial: bool                # Partial position?
    remaining_shares: float         # Shares left
    remaining_value: float          # Value left
```

## Best Practices

### 1. Regular Rebalancing
- Run security selection quarterly to maintain target allocation
- Use small, frequent adjustments rather than large, infrequent ones
- Consider tax impact of rebalancing trades

### 2. Tax-Loss Harvesting
- Harvest losses throughout the year, not just at year-end
- Be mindful of wash sale rules (30-day window)
- Consider replacement securities to maintain market exposure

### 3. Withdrawal Sequencing
- **Brokerage first**: Tax-efficient with loss harvesting opportunities
- **Traditional second**: Ordinary income, but no early withdrawal penalty after 59.5
- **Roth last**: Preserve tax-free growth as long as possible

### 4. Cost Basis Tracking
- Maintain accurate purchase dates and prices
- Use FIFO methodology consistently
- Keep records for audit purposes

### 5. Multi-Year Planning
- Consider future tax brackets when harvesting gains
- Plan Roth conversions around low-income years
- Coordinate with RMD requirements

## Advanced Features

### Wash Sale Detection

The system automatically detects potential wash sales:

```python
# Recent sales tracked
recent_sales = [
    {
        'symbol': 'AAPL',
        'date': datetime(2024, 11, 15),
        'gain_loss': -5000,
    }
]

# Selling AAPL again within 30 days would trigger wash sale
scores = score_securities_for_liquidation(
    portfolio_df=portfolio_df,
    withdrawal_amount=50000,
    account_type='Brokerage',
    target_allocation=target_allocation,
    current_agi=100000,
    filing_status='single',
    recent_sales=recent_sales,  # Passed to detect wash sales
)

# AAPL score will be penalized if within 30-day window
aapl_score = next(s for s in scores if s.symbol == 'AAPL')
if aapl_score.is_wash_sale_risk:
    print(f"Warning: Selling {aapl_score.symbol} may trigger wash sale")
```

### Custom Scoring Weights

You can adjust scoring weights in `security_selection.py`:

```python
# Default weights
WEIGHT_TAX_EFFICIENCY = 0.30
WEIGHT_REBALANCING = 0.30
WEIGHT_LIQUIDITY = 0.20
WEIGHT_COST_BASIS = 0.20

# Example: Prioritize tax efficiency
WEIGHT_TAX_EFFICIENCY = 0.50  # Increase
WEIGHT_REBALANCING = 0.20     # Decrease
WEIGHT_LIQUIDITY = 0.15       # Decrease
WEIGHT_COST_BASIS = 0.15      # Decrease
```

### Partial Share Handling

Control whether partial shares are allowed:

```python
plan = create_liquidation_plan(
    scored_securities=scores,
    withdrawal_amount=50000,
    account_type='Brokerage',
    target_allocation=target_allocation,
    allow_partial_shares=False,  # Only sell whole shares
)
```

## Troubleshooting

### Issue: Insufficient Securities

**Problem**: Plan shows shortfall warning

**Solution**:
```python
if plan.total_selected < plan.total_needed:
    shortfall = plan.total_needed - plan.total_selected
    print(f"Shortfall: ${shortfall:,.0f}")
    print("Consider:")
    print("  1. Allowing partial shares")
    print("  2. Withdrawing from another account")
    print("  3. Reducing withdrawal amount")
```

### Issue: High Tax Impact

**Problem**: Estimated tax exceeds 20% of withdrawal

**Solution**:
```python
if plan.estimated_tax > plan.total_needed * 0.20:
    print("High tax impact detected!")
    print("Consider:")
    print("  1. Harvesting losses first")
    print("  2. Spreading withdrawal across multiple years")
    print("  3. Using Traditional IRA instead")
```

### Issue: Wash Sale Risk

**Problem**: Securities flagged with wash sale risk

**Solution**:
```python
risky_securities = [
    liq for liq in plan.securities 
    if hasattr(liq, 'is_wash_sale_risk') and liq.is_wash_sale_risk
]

if risky_securities:
    print("Wash sale risks detected:")
    for liq in risky_securities:
        print(f"  {liq.symbol}: Wait 30 days or use replacement")
```

## Performance Considerations

### Large Portfolios

For portfolios with 100+ holdings:

```python
# Score only top candidates
scores = score_securities_for_liquidation(
    portfolio_df=portfolio_df.nlargest(50, 'market_value'),  # Top 50 by value
    withdrawal_amount=50000,
    account_type='Brokerage',
    target_allocation=target_allocation,
    current_agi=100000,
    filing_status='single',
)
```

### Caching

Results can be cached for repeated analysis:

```python
import functools

@functools.lru_cache(maxsize=128)
def cached_score_securities(portfolio_hash, withdrawal_amount, account_type):
    # Score securities with caching
    pass
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest test_security_selection.py -v

# Run specific test class
pytest test_security_selection.py::TestTaxEfficiencyScoring -v

# Run with coverage
pytest test_security_selection.py --cov=security_selection --cov-report=html
```

## Future Enhancements

### Planned Features

1. **Machine Learning Integration**
   - Learn from user preferences
   - Predict optimal liquidation strategies
   - Forecast tax impact

2. **Real-Time Execution**
   - Brokerage API integration
   - Automated trade execution
   - Real-time portfolio monitoring

3. **Advanced Tax Strategies**
   - Multi-year tax optimization
   - Estate planning integration
   - Charitable giving coordination

4. **Enhanced Analytics**
   - Historical performance tracking
   - What-if scenario analysis
   - Optimization recommendations

## References

- [IRS Publication 550](https://www.irs.gov/publications/p550) - Investment Income and Expenses
- [IRS Publication 564](https://www.irs.gov/publications/p564) - Mutual Fund Distributions
- [Wash Sale Rules](https://www.irs.gov/taxtopics/tc409) - IRC §1091
- [Cost Basis Tracking Guide](COST_BASIS_TRACKING_GUIDE.md) - Internal documentation

## Support

For questions or issues:
1. Check this guide first
2. Review test cases in `test_security_selection.py`
3. Consult implementation plan in `ADVANCED_PORTFOLIO_FEATURES_IMPLEMENTATION_PLAN.md`
4. Review source code in `security_selection.py`

---

**Version**: 1.0  
**Last Updated**: 2026-03-17  
**Author**: Bob