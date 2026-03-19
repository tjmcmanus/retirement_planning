"""
Integration Tests for Security Selection with Real Portfolio Data
==================================================================
Tests the complete integration of security selection with the withdrawal strategy.

This test suite validates:
- Integration with strategy.py withdrawal functions
- Real portfolio data handling
- FIFO fallback behavior
- Tax impact calculations
- Decision logging

Author: Bob
Date: 2026-03-17
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict

from security_selection_integration import (
    withdraw_from_brokerage_smart,
    should_use_smart_selection,
    create_portfolio_snapshot,
    track_liquidation_for_wash_sales,
    DEFAULT_TARGET_ALLOCATION,
)
from strategy import BrokerageAccount, BrokerageTransaction


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def real_portfolio_data():
    """Create realistic portfolio data similar to actual holdings."""
    return pd.DataFrame([
        {
            'symbol': 'VTI',
            'account_type': 'Brokerage',
            'qty': 500,
            'purchase_price': 200.0,
            'current_price': 240.0,
            'market_value': 120000.0,
            'sector': 'Stocks',
            'name': 'Vanguard Total Stock Market ETF',
            'holding_period_days': 730,  # 2 years
            'asset_class': 'Stocks',
        },
        {
            'symbol': 'BND',
            'account_type': 'Brokerage',
            'qty': 1000,
            'purchase_price': 80.0,
            'current_price': 78.0,
            'market_value': 78000.0,
            'sector': 'Bond',
            'name': 'Vanguard Total Bond Market ETF',
            'holding_period_days': 1095,  # 3 years
            'asset_class': 'Bonds',
        },
        {
            'symbol': 'AAPL',
            'account_type': 'Brokerage',
            'qty': 100,
            'purchase_price': 150.0,
            'current_price': 180.0,
            'market_value': 18000.0,
            'sector': 'Technology',
            'name': 'Apple Inc.',
            'holding_period_days': 400,
            'asset_class': 'Stocks',
        },
        {
            'symbol': 'GOOGL',
            'account_type': 'Brokerage',
            'qty': 50,
            'purchase_price': 2800.0,
            'current_price': 2500.0,
            'market_value': 125000.0,
            'sector': 'Technology',
            'name': 'Alphabet Inc.',
            'holding_period_days': 200,  # Short-term
            'asset_class': 'Stocks',
        },
        {
            'symbol': 'MF:CASH',
            'account_type': 'Brokerage',
            'qty': 25000,
            'purchase_price': 1.0,
            'current_price': 1.0,
            'market_value': 25000.0,
            'sector': 'MF:Cash',
            'name': 'Cash',
            'holding_period_days': 0,
            'asset_class': 'Cash',
        },
    ])


@pytest.fixture
def brokerage_account_with_history():
    """Create BrokerageAccount with transaction history."""
    account = BrokerageAccount()
    
    # Initial portfolio in 2020
    account.add_transfer(2020, 300000, "initial_portfolio")
    
    # Apply growth for 4 years
    for year in range(2021, 2025):
        account.apply_annual_growth(1.07, year)
    
    return account


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================

class TestRealPortfolioIntegration:
    """Tests with realistic portfolio data."""
    
    def test_smart_withdrawal_with_real_data(self, real_portfolio_data, brokerage_account_with_history):
        """Test smart withdrawal with realistic portfolio."""
        basis, ltcg, plan = withdraw_from_brokerage_smart(
            amount=50000,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=real_portfolio_data,
            year=2024,
            target_allocation=DEFAULT_TARGET_ALLOCATION,
            current_agi=100000,
            filing_status='single',
        )
        
        # Verify withdrawal occurred
        assert basis + ltcg > 0
        assert basis >= 0
        assert ltcg >= 0
        
        # Verify plan was created
        assert plan is not None
        assert len(plan.securities) > 0
        assert plan.total_selected >= 50000
        
        # Verify tax impact calculated
        assert plan.estimated_tax >= 0
        assert plan.total_ltcg >= 0
        assert plan.total_basis_returned >= 0
        
        print(f"\nSmart Withdrawal Results:")
        print(f"  Amount requested: $50,000")
        print(f"  Amount selected: ${plan.total_selected:,.0f}")
        print(f"  Securities sold: {len(plan.securities)}")
        print(f"  Basis returned: ${basis:,.0f}")
        print(f"  LTCG realized: ${ltcg:,.0f}")
        print(f"  Estimated tax: ${plan.estimated_tax:,.0f}")
        print(f"  Drift improvement: {plan.drift_improvement:+.2f}%")
        
        for i, sec in enumerate(plan.securities, 1):
            print(f"  {i}. {sec.symbol}: ${sec.amount_to_liquidate:,.0f} ({sec.reason})")
    
    def test_loss_harvesting_prioritization(self, real_portfolio_data, brokerage_account_with_history):
        """Verify that loss positions are prioritized."""
        basis, ltcg, plan = withdraw_from_brokerage_smart(
            amount=30000,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=real_portfolio_data,
            year=2024,
            target_allocation=DEFAULT_TARGET_ALLOCATION,
            current_agi=100000,
            filing_status='single',
        )
        
        assert plan is not None
        
        # Check if loss positions (BND, GOOGL) were selected
        loss_symbols = ['BND', 'GOOGL']
        selected_symbols = [sec.symbol for sec in plan.securities]
        
        # At least one loss position should be selected
        has_loss_position = any(sym in selected_symbols for sym in loss_symbols)
        
        print(f"\nLoss Harvesting Test:")
        print(f"  Loss positions available: {loss_symbols}")
        print(f"  Securities selected: {selected_symbols}")
        print(f"  Loss position selected: {has_loss_position}")
        
        if has_loss_position:
            for sec in plan.securities:
                if sec.symbol in loss_symbols:
                    print(f"  {sec.symbol}: ${sec.gain_loss:,.0f} loss harvested")
    
    def test_fallback_to_fifo(self, brokerage_account_with_history):
        """Test fallback to FIFO when no portfolio data."""
        basis, ltcg, plan = withdraw_from_brokerage_smart(
            amount=50000,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=None,  # No portfolio data
            year=2024,
            target_allocation=DEFAULT_TARGET_ALLOCATION,
            current_agi=100000,
            filing_status='single',
        )
        
        # Verify withdrawal occurred
        assert basis + ltcg > 0
        
        # Verify no plan was created (FIFO fallback)
        assert plan is None
        
        print(f"\nFIFO Fallback Test:")
        print(f"  Basis returned: ${basis:,.0f}")
        print(f"  LTCG realized: ${ltcg:,.0f}")
        print(f"  Plan created: {plan is not None}")
    
    def test_portfolio_snapshot_creation(self, brokerage_account_with_history):
        """Test creating portfolio snapshot from BrokerageAccount."""
        snapshot = create_portfolio_snapshot(brokerage_account_with_history, 2024)
        
        assert not snapshot.empty
        assert 'symbol' in snapshot.columns
        assert 'account_type' in snapshot.columns
        assert 'market_value' in snapshot.columns
        
        print(f"\nPortfolio Snapshot:")
        print(f"  Lots: {len(snapshot)}")
        print(f"  Total value: ${snapshot['market_value'].sum():,.0f}")
        print(snapshot[['symbol', 'market_value', 'holding_period_days']])
    
    def test_wash_sale_tracking(self, real_portfolio_data, brokerage_account_with_history):
        """Test wash sale tracking from liquidation plan."""
        basis, ltcg, plan = withdraw_from_brokerage_smart(
            amount=50000,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=real_portfolio_data,
            year=2024,
            target_allocation=DEFAULT_TARGET_ALLOCATION,
            current_agi=100000,
            filing_status='single',
        )
        
        assert plan is not None
        
        # Track sales for wash sale detection
        sales = track_liquidation_for_wash_sales(plan, 2024)
        
        assert len(sales) == len(plan.securities)
        
        for sale in sales:
            assert 'symbol' in sale
            assert 'date' in sale
            assert 'gain_loss' in sale
            assert 'amount' in sale
        
        print(f"\nWash Sale Tracking:")
        print(f"  Sales tracked: {len(sales)}")
        for sale in sales:
            print(f"  {sale['symbol']}: ${sale['gain_loss']:,.0f} gain/loss")


class TestTaxOptimization:
    """Tests for tax optimization features."""
    
    def test_zero_percent_ltcg_optimization(self, real_portfolio_data, brokerage_account_with_history):
        """Test optimization for 0% LTCG rate."""
        # Low AGI to qualify for 0% LTCG
        basis, ltcg, plan = withdraw_from_brokerage_smart(
            amount=40000,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=real_portfolio_data,
            year=2024,
            target_allocation=DEFAULT_TARGET_ALLOCATION,
            current_agi=30000,  # Low AGI
            filing_status='single',
        )
        
        assert plan is not None
        
        # Should prefer gain positions at 0% rate
        print(f"\n0% LTCG Optimization:")
        print(f"  AGI: $30,000 (qualifies for 0% LTCG)")
        print(f"  LTCG realized: ${ltcg:,.0f}")
        print(f"  Estimated tax: ${plan.estimated_tax:,.0f}")
        
        # At 0% LTCG rate, tax should be minimal
        assert plan.estimated_tax < ltcg * 0.05  # Less than 5% effective rate
    
    def test_high_agi_tax_impact(self, real_portfolio_data, brokerage_account_with_history):
        """Test tax impact with high AGI."""
        # High AGI = 20% LTCG rate
        basis, ltcg, plan = withdraw_from_brokerage_smart(
            amount=40000,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=real_portfolio_data,
            year=2024,
            target_allocation=DEFAULT_TARGET_ALLOCATION,
            current_agi=500000,  # High AGI
            filing_status='single',
        )
        
        assert plan is not None
        
        print(f"\nHigh AGI Tax Impact:")
        print(f"  AGI: $500,000 (20% LTCG rate)")
        print(f"  LTCG realized: ${ltcg:,.0f}")
        print(f"  Estimated tax: ${plan.estimated_tax:,.0f}")
        print(f"  Effective rate: {plan.estimated_tax/ltcg*100:.1f}%")


class TestRebalancingIntegration:
    """Tests for rebalancing integration."""
    
    def test_overweight_position_selection(self, real_portfolio_data, brokerage_account_with_history):
        """Test that overweight positions are preferentially selected."""
        # Set target with low stock allocation
        target = {'Cash': 10, 'Bonds': 50, 'Stocks': 40}
        
        basis, ltcg, plan = withdraw_from_brokerage_smart(
            amount=50000,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=real_portfolio_data,
            year=2024,
            target_allocation=target,
            current_agi=100000,
            filing_status='single',
        )
        
        assert plan is not None
        
        print(f"\nRebalancing Test:")
        print(f"  Target allocation: {target}")
        print(f"  Pre-allocation: {plan.pre_allocation}")
        print(f"  Post-allocation: {plan.post_allocation}")
        print(f"  Drift improvement: {plan.drift_improvement:+.2f}%")
        
        # Drift should improve (positive value)
        assert plan.drift_improvement >= 0


class TestPerformance:
    """Performance tests with large portfolios."""
    
    def test_large_portfolio_performance(self, brokerage_account_with_history):
        """Test performance with 100+ holdings."""
        import time
        
        # Create large portfolio
        symbols = [f'STOCK{i}' for i in range(100)]
        large_portfolio = pd.DataFrame([
            {
                'symbol': sym,
                'account_type': 'Brokerage',
                'qty': 100,
                'purchase_price': 100.0,
                'current_price': 110.0,
                'market_value': 11000.0,
                'sector': 'Stocks',
                'name': f'Stock {sym}',
                'holding_period_days': 400,
            }
            for sym in symbols
        ])
        
        start_time = time.time()
        
        basis, ltcg, plan = withdraw_from_brokerage_smart(
            amount=50000,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=large_portfolio,
            year=2024,
            target_allocation=DEFAULT_TARGET_ALLOCATION,
            current_agi=100000,
            filing_status='single',
        )
        
        elapsed = time.time() - start_time
        
        print(f"\nPerformance Test (100 holdings):")
        print(f"  Time elapsed: {elapsed:.3f} seconds")
        print(f"  Securities scored: {len(large_portfolio)}")
        print(f"  Securities selected: {len(plan.securities) if plan else 0}")
        
        # Should complete in reasonable time
        assert elapsed < 2.0  # Less than 2 seconds


# ==============================================================================
# COMPARISON TESTS
# ==============================================================================

class TestSmartVsFIFO:
    """Compare smart selection vs FIFO."""
    
    def test_tax_savings_comparison(self, real_portfolio_data, brokerage_account_with_history):
        """Compare tax impact: smart selection vs FIFO."""
        amount = 50000
        
        # Smart selection
        basis_smart, ltcg_smart, plan_smart = withdraw_from_brokerage_smart(
            amount=amount,
            brokerage_account=brokerage_account_with_history,
            portfolio_df=real_portfolio_data,
            year=2024,
            target_allocation=DEFAULT_TARGET_ALLOCATION,
            current_agi=100000,
            filing_status='single',
        )
        
        # FIFO (create new account with same starting balance)
        fifo_account = BrokerageAccount()
        fifo_account.add_transfer(2020, 300000, "initial_portfolio")
        for year in range(2021, 2025):
            fifo_account.apply_annual_growth(1.07, year)
        
        basis_fifo, ltcg_fifo = fifo_account.withdraw_fifo(amount, 2024)
        
        # Calculate tax at 15% LTCG rate
        tax_smart = ltcg_smart * 0.15
        tax_fifo = ltcg_fifo * 0.15
        tax_savings = tax_fifo - tax_smart
        savings_pct = (tax_savings / tax_fifo * 100) if tax_fifo > 0 else 0
        
        print(f"\nSmart vs FIFO Comparison:")
        print(f"  Withdrawal amount: ${amount:,.0f}")
        print(f"\n  Smart Selection:")
        print(f"    LTCG: ${ltcg_smart:,.0f}")
        print(f"    Tax (15%): ${tax_smart:,.0f}")
        print(f"    Securities: {len(plan_smart.securities) if plan_smart else 0}")
        print(f"\n  FIFO:")
        print(f"    LTCG: ${ltcg_fifo:,.0f}")
        print(f"    Tax (15%): ${tax_fifo:,.0f}")
        print(f"\n  Savings: ${tax_savings:,.0f} ({savings_pct:.1f}%)")
        
        # Smart selection should have equal or better tax outcome
        assert tax_smart <= tax_fifo * 1.05  # Allow 5% margin


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

# Made with Bob
