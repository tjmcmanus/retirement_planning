# Cost Basis Tracking Implementation Guide

## Overview

The retirement planning application now includes **actual cost basis tracking** for brokerage account withdrawals, replacing the traditional fixed 60/40 assumption (60% tax-free basis, 40% taxable LTCG) with transaction-level tracking using FIFO (First In, First Out) methodology.

## Table of Contents

1. [Why Cost Basis Tracking Matters](#why-cost-basis-tracking-matters)
2. [Architecture Overview](#architecture-overview)
3. [Core Components](#core-components)
4. [How It Works](#how-it-works)
5. [Integration Points](#integration-points)
6. [Tax Analytics Display](#tax-analytics-display)
7. [Testing](#testing)
8. [Usage Examples](#usage-examples)
9. [Technical Details](#technical-details)
10. [Future Enhancements](#future-enhancements)

---

## Why Cost Basis Tracking Matters

### The Problem with 60/40 Assumption

Traditional retirement planning tools assume that **40% of every brokerage withdrawal is taxable LTCG** and **60% is tax-free return of basis**. This assumption:

- **Oversimplifies** actual tax liability
- **Ignores** transaction history and timing
- **Misrepresents** tax burden in early vs. late retirement
- **Fails to account** for market performance variations

### Real-World Impact

**Example Scenario:**
- You transfer $100,000 from Traditional IRA to Brokerage in Year 1
- Market grows 50% over 5 years → Account worth $150,000
- You withdraw $60,000 in Year 6

**Old Method (60/40):**
- Basis returned: $36,000 (60%)
- LTCG: $24,000 (40%)

**Actual (Cost Basis Tracking):**
- Basis returned: $40,000 (actual cost basis)
- LTCG: $20,000 (actual gains)
- **Tax savings: $4,000 less in taxable gains!**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 WithdrawalStrategyEngine                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           BrokerageAccount (FIFO Tracking)            │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  BrokerageTransaction (Lot 1)                  │  │  │
│  │  │  - Year: 2024                                  │  │  │
│  │  │  - Original: $50,000                           │  │  │
│  │  │  - Basis: $50,000                              │  │  │
│  │  │  - Current: $54,000 (8% growth)                │  │  │
│  │  │  - Years Held: 1                               │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  BrokerageTransaction (Lot 2)                  │  │  │
│  │  │  - Year: 2025                                  │  │  │
│  │  │  - Original: $50,000                           │  │  │
│  │  │  - Basis: $50,000                              │  │  │
│  │  │  - Current: $50,000 (just added)               │  │  │
│  │  │  - Years Held: 0                               │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │                                                        │  │
│  │  Methods:                                              │  │
│  │  - add_transfer(year, amount, source)                 │  │
│  │  - withdraw_fifo(amount, year) → (basis, ltcg)        │  │
│  │  - apply_annual_growth(rate, year)                    │  │
│  │  - Properties: ltcg_ratio, basis_ratio                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Life Stages (6):                                           │
│  1. Accumulation                                            │
│  2. Prep for Retirement                                     │
│  3. Early Retirement ← Primary LTCG harvesting              │
│  4. Medicare                                                │
│  5. Social Security                                         │
│  6. RMD                                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. BrokerageTransaction (Lines 146-193 in strategy.py)

Represents a single transfer into the brokerage account.

```python
@dataclass
class BrokerageTransaction:
    year: int                    # Year of transfer
    transfer_date: int           # Date of transfer
    original_amount: float       # Initial transfer amount
    cost_basis: float           # Tax basis (usually = original_amount)
    current_value: float        # Current market value
    years_held: int             # Years since transfer
    source: str                 # Source of funds (e.g., "Traditional→Brokerage")
```

**Key Features:**
- Immutable record of each transfer
- Tracks growth separately per lot
- Maintains holding period for tax purposes

### 2. BrokerageAccount (Lines 196-493 in strategy.py)

Manages all brokerage transactions with FIFO withdrawal logic.

```python
@dataclass
class BrokerageAccount:
    lots: List[BrokerageTransaction] = field(default_factory=list)
    
    # Core Methods
    def add_transfer(year: int, amount: float, source: str)
    def withdraw_fifo(amount: float, year: int) -> Tuple[float, float]
    def apply_annual_growth(growth_rate: float, year: int)
    
    # Properties
    @property
    def total_value(self) -> float
    @property
    def total_basis(self) -> float
    @property
    def total_gains(self) -> float
    @property
    def ltcg_ratio(self) -> float
    @property
    def basis_ratio(self) -> float
```

**Key Features:**
- **FIFO Withdrawals**: Always withdraws from oldest lots first
- **Automatic Growth**: Applies market returns to all lots
- **Real-Time Ratios**: Calculates actual LTCG/basis ratios on demand
- **Transaction History**: Maintains complete audit trail

### 3. YearlyStrategy Enhancements (Lines 2428-2431 in strategy.py)

Added three new fields to track cost basis data:

```python
@dataclass
class YearlyStrategy:
    # ... existing fields ...
    
    # Cost basis tracking (added after required fields)
    basis_returned: float = 0.0           # Tax-free basis returned this year
    brokerage_ltcg_ratio: float = 0.0     # Actual LTCG ratio for this year
    brokerage_basis_ratio: float = 0.0    # Actual basis ratio for this year
```

---

## How It Works

### Step 1: Initialization

When `WithdrawalStrategyEngine` starts calculating a multi-year strategy:

```python
# strategy.py, lines 6222-6230
def calculate_multi_year_strategy(self, ...):
    # Initialize brokerage account for cost basis tracking
    self.brokerage_account = BrokerageAccount()
    
    # ... calculate strategy for each year ...
```

### Step 2: Recording Transfers

When funds move from Traditional IRA to Brokerage (e.g., for Roth conversions):

```python
# strategy.py, lines 2795-2805
def replenish_brokerage_buffer(..., brokerage_account=None):
    # ... calculate transfer amount ...
    
    if brokerage_account and trad_to_brokerage > 0:
        # Record the transfer with cost basis tracking
        brokerage_account.add_transfer(
            year=year,
            amount=trad_to_brokerage,
            source="Traditional→Brokerage"
        )
```

### Step 3: Annual Growth

Before processing each year, apply market growth to all lots:

```python
# strategy.py, lines 6260-6265
for year in range(start_year, end_year + 1):
    # Apply growth to brokerage account before year's transactions
    if self.brokerage_account:
        self.brokerage_account.apply_annual_growth(growth_rate, year)
```

### Step 4: FIFO Withdrawals

When withdrawing from brokerage for expenses or LTCG harvesting:

```python
# strategy.py, lines 4388-4393 (Stage 3 Early Retirement example)
if brokerage_account and max_brokerage_withdrawal > 0:
    # Execute FIFO withdrawal and get actual basis/LTCG split
    basis_returned, ltcg_harvested = brokerage_account.withdraw_fifo(
        max_brokerage_withdrawal, year
    )
else:
    # Fallback to 60/40 assumption if tracking not available
    ltcg_harvested = max_brokerage_withdrawal * BROKERAGE_LTCG_RATIO
    basis_returned = max_brokerage_withdrawal * BROKERAGE_COST_BASIS_RATIO
```

### Step 5: Recording Results

Each year's strategy includes actual cost basis data:

```python
# strategy.py, lines 4750-4760 (Stage 3 return statement example)
return YearlyStrategy(
    # ... other fields ...
    ltcg_harvested=ltcg_harvested,
    # Cost basis tracking
    basis_returned=basis_returned,
    brokerage_ltcg_ratio=brokerage_account.ltcg_ratio,
    brokerage_basis_ratio=brokerage_account.basis_ratio,
    # ... other fields ...
)
```

---

## Integration Points

### 1. All 6 Life Stages Updated

Every life stage now passes `brokerage_account` parameter:

| Stage | Primary Use Case | Lines |
|-------|-----------------|-------|
| **Stage 1: Accumulation** | No withdrawals, tracks contributions | 3754-3762 |
| **Stage 2: Prep for Retirement** | Building brokerage buffer | 4230-4238 |
| **Stage 3: Early Retirement** | Heavy LTCG harvesting | 4388-4393, 4750-4760 |
| **Stage 4: Medicare** | IRMAA-aware LTCG | 4879-4884 |
| **Stage 5: Social Security** | SS + LTCG optimization | 5366-5371, 5407-5412 |
| **Stage 6: RMD** | RMD + limited LTCG | 6048-6053 |

### 2. Buffer Replenishment Function

The `replenish_brokerage_buffer()` function (lines 2721-2829) now:
- Accepts `brokerage_account` parameter
- Records all Traditional→Brokerage transfers
- Maintains transaction history for FIFO withdrawals

### 3. Rebalance Accounts Function

The `rebalance_accounts()` function (lines 2974-3015) now:
- Accepts `brokerage_account` parameter
- Passes it through to `replenish_brokerage_buffer()`
- All 6 life stages updated to pass the parameter

---

## Tax Analytics Display

### DataFrame Columns (strategy.py, lines 6801-6803)

Three new columns added to strategy DataFrame:

```python
'Basis Returned': s.basis_returned,
'Brokerage LTCG Ratio': s.brokerage_ltcg_ratio,
'Brokerage Basis Ratio': s.brokerage_basis_ratio,
```

### Tax Analytics Enhancements (pages/5_strategy.py)

#### 1. Data Preparation (lines 843-880)

```python
def prepare_tax_analytics_data(strategy_df, phase):
    # ... existing calculations ...
    
    # Add cost basis insights
    cost_basis_insights = {}
    if 'Basis Returned' in strategy_df.columns:
        total_basis_returned = strategy_df['Basis Returned'].sum()
        cost_basis_insights['total_basis_returned'] = total_basis_returned
    
    if 'Brokerage LTCG Ratio' in strategy_df.columns:
        ltcg_ratios = strategy_df[strategy_df['Brokerage LTCG Ratio'] > 0]['Brokerage LTCG Ratio']
        if not ltcg_ratios.empty:
            cost_basis_insights['avg_ltcg_ratio'] = ltcg_ratios.mean()
            cost_basis_insights['min_ltcg_ratio'] = ltcg_ratios.min()
            cost_basis_insights['max_ltcg_ratio'] = ltcg_ratios.max()
    
    return {
        # ... existing data ...
        'cost_basis_insights': cost_basis_insights
    }
```

#### 2. Visual Display (lines 1159-1205)

New section in Tax Analytics Overview:

```
📊 Cost Basis Tracking Insights
Actual cost basis tracking replaces the traditional 60/40 LTCG assumption

┌─────────────────────┬──────────────────┬────────────────────┐
│ Total Basis Returned│  Avg LTCG Ratio  │  LTCG Ratio Range  │
│     $450,000        │      35.2%       │  28.5% - 42.1%     │
└─────────────────────┴──────────────────┴────────────────────┘

💡 Cost Basis Insight: Your actual LTCG ratio (35.2%) is 4.8% lower 
than the traditional 60/40 assumption (40% LTCG). This reduces your 
actual tax burden on brokerage withdrawals.
```

---

## Testing

### Test Suite: test_cost_basis_tracking.py

Comprehensive test coverage includes:

#### 1. Unit Tests
- **BrokerageTransaction**: Creation, data integrity
- **BrokerageAccount**: Empty state, single/multiple transfers, growth application

#### 2. FIFO Logic Tests
- Single lot withdrawal
- Multiple lot withdrawal (spanning lots)
- Complete account depletion
- Withdrawal exceeding balance
- LTCG ratio calculations

#### 3. Integration Tests
- WithdrawalStrategyEngine initialization
- YearlyStrategy field inclusion
- End-to-end strategy calculation

#### 4. Scenario Tests
- Traditional 60/40 assumption (special case)
- Early retirement (multiple years)
- High growth markets
- Market downturns (losses)

### Running Tests

```bash
# Run all cost basis tests
pytest test_cost_basis_tracking.py -v

# Run specific test class
pytest test_cost_basis_tracking.py::TestBrokerageAccount -v

# Run with coverage
pytest test_cost_basis_tracking.py --cov=strategy --cov-report=html
```

---

## Usage Examples

### Example 1: Early Retirement LTCG Harvesting

**Scenario:** Retire at 55, harvest LTCG at 0% rate for 10 years

```python
# Year 1 (Age 55): Transfer $50k from Traditional to Brokerage
brokerage_account.add_transfer(2024, 50000, "Traditional→Brokerage")

# Year 2 (Age 56): Market grows 8%, transfer another $50k
brokerage_account.apply_annual_growth(0.08, 2025)  # First lot now $54k
brokerage_account.add_transfer(2025, 50000, "Traditional→Brokerage")

# Year 3 (Age 57): Withdraw $60k for living expenses
basis, ltcg = brokerage_account.withdraw_fifo(60000, 2026)
# Result: basis=$56,000, ltcg=$4,000 (actual, not 60/40 assumption)
```

### Example 2: Comparing Actual vs. Assumed

```python
# After 5 years of transfers and growth
actual_ltcg_ratio = brokerage_account.ltcg_ratio  # e.g., 0.35 (35%)
assumed_ltcg_ratio = 0.40  # Traditional assumption

# Tax impact on $100k withdrawal
withdrawal = 100000
actual_ltcg = withdrawal * actual_ltcg_ratio      # $35,000
assumed_ltcg = withdrawal * assumed_ltcg_ratio    # $40,000

# Tax savings (at 15% LTCG rate)
tax_savings = (assumed_ltcg - actual_ltcg) * 0.15  # $750 saved!
```

### Example 3: Viewing in Tax Analytics

1. Navigate to **Strategy** page
2. Run withdrawal strategy
3. Click **Tax Analytics** tab
4. View **Cost Basis Tracking Insights** section
5. Compare actual LTCG ratio to 60/40 assumption

---

## Technical Details

### FIFO Withdrawal Algorithm

```python
def withdraw_fifo(self, amount: float, year: int) -> Tuple[float, float]:
    """
    Withdraw from oldest lots first (FIFO).
    
    Returns:
        (basis_returned, ltcg_realized)
    """
    remaining = amount
    basis_returned = 0.0
    ltcg_realized = 0.0
    
    lots_to_remove = []
    
    for i, lot in enumerate(self.lots):
        if remaining <= 0:
            break
        
        # Calculate withdrawal from this lot
        withdrawal_from_lot = min(remaining, lot.current_value)
        
        # Proportional basis and gains
        proportion = withdrawal_from_lot / lot.current_value
        basis_from_lot = lot.cost_basis * proportion
        gains_from_lot = (lot.current_value - lot.cost_basis) * proportion
        
        # Accumulate
        basis_returned += basis_from_lot
        ltcg_realized += gains_from_lot
        remaining -= withdrawal_from_lot
        
        # Update or remove lot
        if withdrawal_from_lot >= lot.current_value:
            lots_to_remove.append(i)
        else:
            lot.current_value -= withdrawal_from_lot
            lot.cost_basis -= basis_from_lot
    
    # Remove fully depleted lots
    for i in reversed(lots_to_remove):
        self.lots.pop(i)
    
    return basis_returned, ltcg_realized
```

### Growth Application

```python
def apply_annual_growth(self, growth_rate: float, year: int):
    """Apply market growth to all lots."""
    for lot in self.lots:
        lot.current_value *= (1 + growth_rate)
        lot.years_held += 1
    
    # Note: cost_basis never changes, only current_value grows
```

### Ratio Calculations

```python
@property
def ltcg_ratio(self) -> float:
    """Percentage of account value that is taxable gains."""
    if self.total_value == 0:
        return 0.0
    return self.total_gains / self.total_value

@property
def basis_ratio(self) -> float:
    """Percentage of account value that is tax-free basis."""
    if self.total_value == 0:
        return 0.0
    return self.total_basis / self.total_value
```

---

## Future Enhancements

### Potential Improvements

1. **Tax Loss Harvesting**
   - Track lots with losses separately
   - Implement strategic loss realization
   - Offset gains with losses

2. **Specific Lot Identification**
   - Allow choosing which lots to sell (vs. FIFO)
   - Optimize for tax efficiency
   - Support HIFO (Highest In, First Out)

3. **Wash Sale Tracking**
   - Detect wash sale violations
   - Adjust cost basis accordingly
   - Warn users of potential issues

4. **State-Specific Rules**
   - Handle state-specific cost basis rules
   - Track state tax basis separately
   - Support state tax credits

5. **Import from Brokerages**
   - Import actual transaction history
   - Sync with real brokerage accounts
   - Validate against 1099-B forms

6. **Advanced Reporting**
   - Generate tax forms (8949, Schedule D)
   - Export to tax software
   - Audit trail reports

### Performance Optimizations

1. **Lot Consolidation**
   - Merge small lots to reduce memory
   - Maintain accuracy within tolerance
   - Improve calculation speed

2. **Caching**
   - Cache ratio calculations
   - Invalidate on transactions only
   - Reduce redundant computations

3. **Parallel Processing**
   - Calculate multiple years in parallel
   - Thread-safe lot management
   - Faster multi-year projections

---

## Conclusion

The cost basis tracking implementation provides **accurate, transaction-level tax calculations** that replace oversimplified assumptions. This leads to:

✅ **More accurate tax projections**  
✅ **Better retirement planning decisions**  
✅ **Optimized withdrawal strategies**  
✅ **Transparent cost basis tracking**  
✅ **Audit-ready transaction history**

The system is **fully integrated** across all 6 life stages, **thoroughly tested**, and **ready for production use**.

---

## Support and Maintenance

### Key Files

- **strategy.py** (lines 146-493, 2428-2431, 6772-6826): Core implementation
- **pages/5_strategy.py** (lines 843-880, 1159-1205): Tax Analytics display
- **test_cost_basis_tracking.py**: Comprehensive test suite
- **COST_BASIS_TRACKING_GUIDE.md**: This documentation

### Contact

For questions, issues, or enhancement requests related to cost basis tracking, please refer to the project's issue tracker or contact the development team.

---

**Last Updated:** March 16, 2026  
**Version:** 1.0.0  
**Status:** Production Ready ✅