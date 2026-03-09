# Optimization Component Implementation Guide

## Overview
This document provides a complete implementation guide for `components/portfolio_optimization.py`, the final component needed to complete Phase 1 of the Portfolio Management Enhancements.

## Component Structure

### File: `components/portfolio_optimization.py`
**Estimated Size:** 600-700 lines  
**Estimated Time:** 3-4 days  
**Dependencies:** `portfolio_rebalancing.py`, `tax_harvesting.py`

## Implementation Sections

### 1. Imports and Setup (Lines 1-50)

```python
"""
components/portfolio_optimization.py
====================================
Portfolio Optimization Component - Rebalancing, tax harvesting, and charitable giving optimization.

Features:
- Portfolio rebalancing with drift detection
- Tax-loss harvesting opportunities
- Tax-gain harvesting at 0% LTCG rate
- DAF (Donor Advised Fund) bundling analysis
- Withdrawal planning links
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

if TYPE_CHECKING:
    from pandas import DataFrame

from portfolio_rebalancing import (
    compute_rebalance_plan,
    build_rebalance_display_df,
    build_actions_display_df,
)
from tax_harvesting import (
    build_harvesting_analysis,
    classify_harvest_opportunities,
    compute_harvest_summary,
    compute_net_tax_impact,
    get_ltcg_rate_for_income,
    get_ltcg_zero_threshold,
    get_replacement_detail,
    analyze_daf_bundling,
    identify_daf_candidates,
)
```

### 2. Main Render Function (Lines 51-100)

```python
def render_optimization_tab(
    portdf: DataFrame,
    networth: DataFrame,
    curr_month: int,
    curr_year: int,
) -> None:
    """
    Render the Optimization tab with rebalancing, tax harvesting, and DAF bundling.
    
    Args:
        portdf: Current portfolio display DataFrame
        networth: Net worth history DataFrame
        curr_month: Current month (1-12)
        curr_year: Current year
    """
    st.markdown("### ⚖️ Portfolio Optimization")
    st.caption("Rebalancing, tax harvesting, and charitable giving optimization")
    
    # Create expandable sections for each optimization strategy
    rebalance_expander = st.expander("⚖️ Portfolio Rebalancing", expanded=True)
    harvest_expander = st.expander("🌾 Tax Loss/Gain Harvesting", expanded=False)
    daf_expander = st.expander("🏦 DAF Bundling Analysis", expanded=False)
    withdrawal_expander = st.expander("💰 Withdrawal Planning", expanded=False)
```

### 3. Rebalancing Section (Lines 101-300)

**Source:** `pages/4_portfolio.py` lines 501-661

**Key Features:**
- Target allocation input (Cash/Bonds/Stocks %)
- Drift threshold configuration
- Bucket strategy integration for default targets
- Current vs target allocation comparison
- Account-by-account rebalancing actions
- Tax-efficient rebalancing recommendations
- Brokerage cash cushion management

**Implementation:**
```python
with rebalance_expander:
    st.markdown("#### 🎯 Target Allocation & Drift Threshold")
    
    # Try to get bucket strategy defaults
    _default_cash = 10
    _default_bonds = 10
    _default_stocks = 80
    
    try:
        from config import get_config_manager
        from bucket_strategy import load_bucket_config
        
        cfg = get_config_manager()
        bucket_enabled = cfg.get("bucket_strategy", "enabled", False)
        
        if bucket_enabled:
            bucket_config = load_bucket_config(cfg)
            total_value = float(networth["total"].iloc[-1]) if not networth.empty else 0.0
            
            if total_value > 0:
                # Calculate bucket-based targets
                annual_need = bucket_config.annual_expenses + bucket_config.annual_taxes
                bucket_1_target = annual_need * bucket_config.bucket_1_years
                bucket_2_target = annual_need * bucket_config.bucket_2_years
                bucket_3_target = max(0, total_value - bucket_1_target - bucket_2_target)
                
                # Calculate weighted percentages
                bucket_1_weight = bucket_1_target / total_value
                bucket_2_weight = bucket_2_target / total_value
                bucket_3_weight = bucket_3_target / total_value
                
                # Bucket 1: 100% cash
                cash_from_b1 = 100 * bucket_1_weight
                
                # Bucket 2: graduated allocation
                avg_stocks_b2 = (bucket_config.bucket_2_start_stock_pct + bucket_config.bucket_2_end_stock_pct) / 2
                avg_bonds_b2 = 100 - avg_stocks_b2
                stocks_from_b2 = avg_stocks_b2 * bucket_2_weight
                bonds_from_b2 = avg_bonds_b2 * bucket_2_weight
                
                # Bucket 3: 100% stocks
                stocks_from_b3 = 100 * bucket_3_weight
                
                # Cumulative targets
                _default_cash = round(cash_from_b1)
                _default_bonds = round(bonds_from_b2)
                _default_stocks = round(stocks_from_b2 + stocks_from_b3)
                
                # Ensure they sum to 100
                total = _default_cash + _default_bonds + _default_stocks
                if total != 100:
                    _default_stocks = 100 - _default_cash - _default_bonds
    except Exception:
        pass
    
    # Input controls
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        cash_tgt = st.number_input("Target Cash %", min_value=0, max_value=100, 
                                   value=_default_cash, step=1)
    with col2:
        bonds_tgt = st.number_input("Target Bonds %", min_value=0, max_value=100,
                                    value=_default_bonds, step=1)
    with col3:
        stocks_tgt = st.number_input("Target Stocks %", min_value=0, max_value=100,
                                     value=_default_stocks, step=1)
    with col4:
        drift_thresh = st.number_input("Drift Threshold %", min_value=1, max_value=20,
                                       value=5, step=1)
    
    # Validation
    total_pct = cash_tgt + bonds_tgt + stocks_tgt
    is_valid = total_pct == 100
    
    if is_valid:
        st.success(f"✅ Target allocation totals: **{total_pct}%** (Ready to calculate)")
    else:
        st.warning(f"⚠️ Target allocation totals: **{total_pct}%** (Must equal 100%)")
    
    # Calculate button
    if st.button("🔄 Calculate Rebalancing Plan", disabled=not is_valid, 
                 type="primary" if is_valid else "secondary", use_container_width=True):
        
        try:
            with st.spinner("Computing rebalancing plan..."):
                report = compute_rebalance_plan(
                    month=curr_month,
                    year=curr_year,
                    target_cash_pct=float(cash_tgt),
                    target_bonds_pct=float(bonds_tgt),
                    target_stocks_pct=float(stocks_tgt),
                    drift_threshold_pct=float(drift_thresh),
                )
            
            # Display results
            if report.drift_triggered:
                st.warning(f"🔴 **Rebalancing Required** — drift exceeds {report.drift_threshold_pct:.0f}%")
            else:
                st.success(f"✅ **Portfolio is balanced** — within {report.drift_threshold_pct:.0f}% threshold")
            
            # Asset class metrics
            st.markdown(f"#### 📊 Asset Class Allocation (Total: ${report.total_portfolio_value:,.0f})")
            sum_df = build_rebalance_display_df(report)
            
            mc1, mc2, mc3 = st.columns(3)
            for mc, ac in zip([mc1, mc2, mc3], ["Cash", "Bonds", "Stocks"]):
                row = sum_df[sum_df["Asset Class"] == ac]
                if not row.empty:
                    r = row.iloc[0]
                    with mc:
                        drift_val = float(r["Drift %"])
                        st.metric(
                            label=ac,
                            value=f"{r['Current %']:.1f}% (${r['Current Value']:,.0f})",
                            delta=f"{drift_val:+.1f}% vs {r['Target %']:.0f}% target",
                            delta_color="normal" if abs(drift_val) < drift_thresh else "inverse",
                        )
            
            # Action plan
            st.markdown("#### 🔄 Rebalancing Action Plan")
            act_df = build_actions_display_df(report)
            
            if act_df.empty:
                st.info("No specific actions generated.")
            else:
                for _, act in act_df.iterrows():
                    action_str = str(act["Action"])
                    is_sell = "Sell" in action_str
                    is_buy = "Buy" in action_str
                    
                    # Color coding
                    if is_sell and "Brokerage" in action_str:
                        bg, border = "#fff8f0", "#f58518"
                    elif is_sell:
                        bg, border = "#f0f8ff", "#4c78a8"
                    elif is_buy:
                        bg, border = "#f0fff4", "#21c354"
                    else:
                        bg, border = "#f8f9fa", "#6c757d"
                    
                    st.markdown(
                        f'<div style="border-left:4px solid {border};background:{bg};'
                        f'padding:12px 16px;border-radius:6px;margin-bottom:10px;">'
                        f'<div style="font-size:14px;font-weight:700;">#{int(act["Priority"])} — {action_str} '
                        f'<span style="color:#555;font-weight:400;">[{act["Asset Class"]}]</span> '
                        f'<span style="font-size:13px;color:#1a73e8;">{act["Symbol"]}</span></div>'
                        f'<div style="font-size:12px;margin-top:4px;">Account: <b>{act["Account"]}</b> | '
                        f'Amount: <b>${float(act["Amount"]):,.0f}</b> | Tax: <b>{act["Tax Impact"]}</b></div>'
                        f'<div style="font-size:12px;color:#444;margin-top:6px;">{act["Rationale"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        
        except Exception as e:
            st.error(f"⚠️ Error computing rebalancing plan: {e}")
```

### 4. Tax Harvesting Section (Lines 301-550)

**Source:** `pages/4_portfolio.py` lines 358-496

**Key Features:**
- AGI and tax rate inputs
- Loss/gain threshold configuration
- Market drop trigger analysis
- LTCG rate calculation and 0% threshold
- Harvestable losses/gains identification
- Wash-sale-safe replacement suggestions
- Net tax impact calculation

**Implementation:** (See pages/4_portfolio.py lines 358-496 for full code)

### 5. DAF Bundling Section (Lines 551-700)

**Source:** `pages/4_portfolio.py` lines 666-762

**Key Features:**
- Multi-year charitable giving analysis
- Tax deduction timing optimization
- Appreciated security donation recommendations
- Itemized vs standard deduction comparison

### 6. Withdrawal Planning Section (Lines 701-750)

**New Feature:**
- Link to Strategy page
- Quick withdrawal scenario calculator
- Tax-efficient withdrawal sequencing tips

```python
with withdrawal_expander:
    st.markdown("#### 💰 Withdrawal Planning")
    st.caption("Plan tax-efficient withdrawals from your portfolio")
    
    st.info(
        "💡 For comprehensive withdrawal strategy planning, visit the "
        "**🎯 Strategy** page where you can model multi-year withdrawal scenarios."
    )
    
    # Quick calculator
    st.markdown("##### Quick Withdrawal Calculator")
    
    col1, col2 = st.columns(2)
    with col1:
        withdrawal_amount = st.number_input(
            "Withdrawal Amount ($)",
            min_value=0,
            max_value=1_000_000,
            value=50_000,
            step=1_000,
        )
    
    with col2:
        withdrawal_purpose = st.selectbox(
            "Purpose",
            options=["Living Expenses", "Large Purchase", "Emergency", "Other"],
        )
    
    if st.button("💡 Get Withdrawal Recommendations", use_container_width=True):
        st.markdown("##### 📋 Recommended Withdrawal Sequence")
        
        st.markdown("""
        **Tax-Efficient Withdrawal Order:**
        
        1. **Taxable Brokerage** (first)
           - Lowest tax impact
           - Harvest losses to offset gains
           - Long-term capital gains taxed at preferential rates
        
        2. **Traditional IRA/401(k)** (second)
           - Ordinary income tax rates
           - Consider Roth conversions in low-income years
           - Watch for RMD requirements at age 73
        
        3. **Roth IRA** (last)
           - Tax-free withdrawals
           - No RMDs during lifetime
           - Preserve for later years or heirs
        
        **For your ${withdrawal_amount:,.0f} withdrawal:**
        - Consider taking from Brokerage first
        - If needed, supplement from Traditional accounts
        - Preserve Roth for future tax-free growth
        """)
        
        st.info(
            "💡 Visit the **🎯 Strategy** page to model this withdrawal "
            "in your multi-year retirement plan."
        )
```

## Testing Checklist

### Unit Tests
- [ ] Rebalancing calculation with various target allocations
- [ ] Drift detection with different thresholds
- [ ] Tax harvesting with various AGI levels
- [ ] LTCG rate calculation for different income brackets
- [ ] DAF bundling analysis with multiple scenarios

### Integration Tests
- [ ] Component renders without errors
- [ ] All expanders work correctly
- [ ] Data flows from Portfolio Hub correctly
- [ ] Calculations match existing implementation
- [ ] Error handling works for edge cases

### User Acceptance Tests
- [ ] Can set target allocations
- [ ] Can calculate rebalancing plan
- [ ] Can identify tax harvesting opportunities
- [ ] Can analyze DAF bundling
- [ ] Can access withdrawal planning guidance
- [ ] All features work on mobile

## Migration Notes

### Code to Migrate
1. **Rebalancing:** `pages/4_portfolio.py` lines 501-661 (160 lines)
2. **Tax Harvesting:** `pages/4_portfolio.py` lines 358-496 (138 lines)
3. **DAF Bundling:** `pages/4_portfolio.py` lines 666-762 (96 lines)

**Total:** ~394 lines to migrate + ~200 lines new structure = ~600 lines total

### Dependencies
- `portfolio_rebalancing.py` - Already exists
- `tax_harvesting.py` - Already exists
- `config.py` - For bucket strategy integration
- `bucket_strategy.py` - For default target calculation

### Breaking Changes
None - This is a consolidation, not a replacement. The old page can remain as backup.

## Deployment Plan

### Step 1: Create Component (Day 1-2)
- Create `components/portfolio_optimization.py`
- Implement rebalancing section
- Implement tax harvesting section
- Implement DAF bundling section
- Add withdrawal planning section

### Step 2: Integration (Day 3)
- Update `pages/4_portfolio_hub.py` to import component
- Test all features work correctly
- Verify data flows properly
- Check error handling

### Step 3: Testing & Polish (Day 4)
- Run all tests
- Fix any bugs
- Optimize performance
- Mobile testing
- User acceptance testing

### Step 4: Documentation (Day 4)
- Update README.md
- Create user guide
- Update existing documentation
- Create migration guide

## Success Criteria

- [ ] All rebalancing features work as before
- [ ] All tax harvesting features work as before
- [ ] All DAF bundling features work as before
- [ ] Withdrawal planning guidance added
- [ ] No functionality lost from migration
- [ ] Better organization and user experience
- [ ] All tests passing
- [ ] Documentation updated

## Estimated Timeline

- **Day 1:** Rebalancing section (160 lines + structure)
- **Day 2:** Tax harvesting section (138 lines)
- **Day 3:** DAF bundling + withdrawal planning (96 + 50 lines)
- **Day 4:** Testing, polish, documentation

**Total:** 3-4 days to complete

## Next Steps After Completion

1. Update `pages/4_portfolio_hub.py` to use new component
2. Run integration tests
3. Deploy to production
4. Monitor for issues
5. Gather user feedback
6. Archive old `pages/4_portfolio.py` as backup

## Phase 1 Completion

Once this component is complete, Phase 1 will be 100% done:
- ✅ Overview component
- ✅ Holdings editor component
- ✅ Performance component
- ✅ Optimization component (this one)
- 📋 Connections tab (Phase 2)

**Phase 1 Target:** March 15-17, 2026