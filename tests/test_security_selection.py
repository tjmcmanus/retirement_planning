"""
Tests for Security Selection Module
====================================
Comprehensive test suite for the intelligent security selection system.

Tests cover:
- Security scoring logic
- Liquidation plan creation
- Multi-account optimization
- Tax efficiency calculations
- Wash sale detection
- Edge cases and error handling

Author: Bob
Date: 2026-03-17
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List

from security_selection import (
    SecurityScore,
    SecurityLiquidation,
    LiquidationPlan,
    calculate_tax_efficiency_score,
    calculate_rebalancing_score,
    calculate_liquidity_score,
    calculate_cost_basis_score,
    calculate_composite_score,
    check_wash_sale_risk,
    score_securities_for_liquidation,
    create_liquidation_plan,
    optimize_multi_account_withdrawal,
    format_liquidation_summary,
    TAX_SCORE_LOSS,
    TAX_SCORE_GAIN_0PCT,
    TAX_SCORE_GAIN_15PCT,
    TAX_SCORE_GAIN_20PCT,
    TAX_SCORE_STCG,
    REBAL_SCORE_OVERWEIGHT_10PCT,
    REBAL_SCORE_AT_TARGET,
    REBAL_SCORE_UNDERWEIGHT,
    LIQUIDITY_SCORE_HIGH,
    LIQUIDITY_SCORE_MEDIUM,
    BASIS_SCORE_HIGH,
    BASIS_SCORE_LOSS,
)


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def sample_portfolio_df():
    """Create a sample portfolio DataFrame for testing."""
    return pd.DataFrame([
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
            'holding_period_days': 200,
        },
        {
            'symbol': 'BND',
            'account_type': 'Brokerage',
            'qty': 1000,
            'purchase_price': 80.0,
            'current_price': 82.0,
            'market_value': 82000.0,
            'sector': 'Bond',
            'name': 'Vanguard Total Bond Market ETF',
            'holding_period_days': 500,
        },
        {
            'symbol': 'VTI',
            'account_type': 'Traditional',
            'qty': 500,
            'purchase_price': 200.0,
            'current_price': 220.0,
            'market_value': 110000.0,
            'sector': 'Stocks',
            'name': 'Vanguard Total Stock Market ETF',
            'holding_period_days': 600,
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
        },
    ])


@pytest.fixture
def target_allocation():
    """Standard target allocation."""
    return {
        'Cash': 10.0,
        'Bonds': 30.0,
        'Stocks': 60.0,
    }


@pytest.fixture
def tax_context():
    """Standard tax context."""
    return {
        'agi': 100000,
        'filing_status': 'single',
        'recent_sales': [],
    }


# ==============================================================================
# SCORING TESTS
# ==============================================================================

class TestTaxEfficiencyScoring:
    """Tests for tax efficiency scoring."""
    
    def test_loss_position_highest_score(self):
        """Loss positions should get highest tax efficiency score."""
        score = calculate_tax_efficiency_score(
            unrealized_gain_loss=-5000,
            holding_period_days=400,
            ltcg_rate=0.15,
            account_type='Brokerage',
        )
        assert score == TAX_SCORE_LOSS
    
    def test_gain_at_0pct_ltcg(self):
        """Gains at 0% LTCG rate should score high."""
        score = calculate_tax_efficiency_score(
            unrealized_gain_loss=5000,
            holding_period_days=400,
            ltcg_rate=0.0,
            account_type='Brokerage',
        )
        assert score == TAX_SCORE_GAIN_0PCT
    
    def test_gain_at_15pct_ltcg(self):
        """Gains at 15% LTCG rate should score medium."""
        score = calculate_tax_efficiency_score(
            unrealized_gain_loss=5000,
            holding_period_days=400,
            ltcg_rate=0.15,
            account_type='Brokerage',
        )
        assert score == TAX_SCORE_GAIN_15PCT
    
    def test_gain_at_20pct_ltcg(self):
        """Gains at 20% LTCG rate should score lower."""
        score = calculate_tax_efficiency_score(
            unrealized_gain_loss=5000,
            holding_period_days=400,
            ltcg_rate=0.20,
            account_type='Brokerage',
        )
        assert score == TAX_SCORE_GAIN_20PCT
    
    def test_short_term_gain_lowest_score(self):
        """Short-term gains should score lowest."""
        score = calculate_tax_efficiency_score(
            unrealized_gain_loss=5000,
            holding_period_days=200,
            ltcg_rate=0.15,
            account_type='Brokerage',
        )
        assert score == TAX_SCORE_STCG
    
    def test_tax_advantaged_account(self):
        """Tax-advantaged accounts should score high."""
        score = calculate_tax_efficiency_score(
            unrealized_gain_loss=5000,
            holding_period_days=400,
            ltcg_rate=0.15,
            account_type='Traditional',
        )
        assert score == TAX_SCORE_GAIN_0PCT


class TestRebalancingScoring:
    """Tests for rebalancing scoring."""
    
    def test_overweight_10pct_highest_score(self):
        """Positions overweight by 10%+ should score highest."""
        score = calculate_rebalancing_score(
            current_allocation_pct=70.0,
            target_allocation_pct=60.0,
        )
        assert score == REBAL_SCORE_OVERWEIGHT_10PCT
    
    def test_at_target_medium_score(self):
        """Positions at target should score medium."""
        score = calculate_rebalancing_score(
            current_allocation_pct=60.0,
            target_allocation_pct=60.0,
        )
        assert score == REBAL_SCORE_AT_TARGET
    
    def test_underweight_lowest_score(self):
        """Underweight positions should score lowest."""
        score = calculate_rebalancing_score(
            current_allocation_pct=50.0,
            target_allocation_pct=60.0,
        )
        assert score == REBAL_SCORE_UNDERWEIGHT


class TestLiquidityScoring:
    """Tests for liquidity scoring."""
    
    def test_cash_highest_liquidity(self):
        """Cash should have highest liquidity score."""
        score = calculate_liquidity_score('MF:CASH', 'Cash')
        assert score == LIQUIDITY_SCORE_HIGH
    
    def test_mutual_fund_medium_liquidity(self):
        """Mutual funds should have medium liquidity."""
        score = calculate_liquidity_score('VTSAX', 'Stocks')
        assert score == LIQUIDITY_SCORE_MEDIUM
    
    def test_stock_high_liquidity(self):
        """Stocks should have high liquidity."""
        score = calculate_liquidity_score('AAPL', 'Stocks')
        assert score == LIQUIDITY_SCORE_HIGH


class TestCostBasisScoring:
    """Tests for cost basis scoring."""
    
    def test_loss_position_highest_score(self):
        """Loss positions should score highest."""
        score = calculate_cost_basis_score(
            unrealized_gain_loss=-5000,
            current_value=20000,
        )
        assert score == BASIS_SCORE_LOSS
    
    def test_low_gain_high_score(self):
        """Low gain positions should score high."""
        score = calculate_cost_basis_score(
            unrealized_gain_loss=1000,
            current_value=20000,
        )
        assert score == BASIS_SCORE_HIGH
    
    def test_high_gain_low_score(self):
        """High gain positions should score lower."""
        score = calculate_cost_basis_score(
            unrealized_gain_loss=15000,
            current_value=20000,
        )
        assert score < BASIS_SCORE_HIGH


class TestCompositeScoring:
    """Tests for composite scoring."""
    
    def test_weighted_average(self):
        """Composite score should be weighted average."""
        score = calculate_composite_score(
            tax_score=100.0,
            rebal_score=80.0,
            liquidity_score=60.0,
            basis_score=40.0,
        )
        # 100*0.3 + 80*0.3 + 60*0.2 + 40*0.2 = 30 + 24 + 12 + 8 = 74
        assert score == 74.0


# ==============================================================================
# WASH SALE TESTS
# ==============================================================================

class TestWashSaleDetection:
    """Tests for wash sale detection."""
    
    def test_no_wash_sale_risk(self):
        """No recent sales should mean no wash sale risk."""
        result = check_wash_sale_risk(
            symbol='AAPL',
            recent_sales=[],
            sale_date=datetime.now(),
        )
        assert result is False
    
    def test_wash_sale_within_30_days(self):
        """Sale within 30 days should trigger wash sale risk."""
        recent_sale = {
            'symbol': 'AAPL',
            'date': datetime.now() - timedelta(days=15),
            'gain_loss': -1000,
        }
        result = check_wash_sale_risk(
            symbol='AAPL',
            recent_sales=[recent_sale],
            sale_date=datetime.now(),
        )
        assert result is True
    
    def test_no_wash_sale_after_30_days(self):
        """Sale after 30 days should not trigger wash sale risk."""
        recent_sale = {
            'symbol': 'AAPL',
            'date': datetime.now() - timedelta(days=35),
            'gain_loss': -1000,
        }
        result = check_wash_sale_risk(
            symbol='AAPL',
            recent_sales=[recent_sale],
            sale_date=datetime.now(),
        )
        assert result is False
    
    def test_no_wash_sale_for_gains(self):
        """Gains should not trigger wash sale risk."""
        recent_sale = {
            'symbol': 'AAPL',
            'date': datetime.now() - timedelta(days=15),
            'gain_loss': 1000,
        }
        result = check_wash_sale_risk(
            symbol='AAPL',
            recent_sales=[recent_sale],
            sale_date=datetime.now(),
        )
        assert result is False


# ==============================================================================
# SECURITY SCORING TESTS
# ==============================================================================

class TestSecurityScoring:
    """Tests for complete security scoring."""
    
    def test_score_securities_basic(self, sample_portfolio_df, target_allocation, tax_context):
        """Test basic security scoring."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
            recent_sales=tax_context['recent_sales'],
        )
        
        assert len(scores) == 4  # 4 brokerage holdings
        assert all(isinstance(s, SecurityScore) for s in scores)
        assert all(0 <= s.total_score <= 100 for s in scores)
    
    def test_scores_sorted_descending(self, sample_portfolio_df, target_allocation, tax_context):
        """Scores should be sorted by total_score descending."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        for i in range(len(scores) - 1):
            assert scores[i].total_score >= scores[i + 1].total_score
    
    def test_loss_position_scores_highest(self, sample_portfolio_df, target_allocation, tax_context):
        """Loss positions should generally score highest."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        # GOOGL has a loss, should score high
        googl_score = next(s for s in scores if s.symbol == 'GOOGL')
        assert googl_score.unrealized_gain_loss < 0
        assert googl_score.tax_efficiency_score == TAX_SCORE_LOSS


# ==============================================================================
# LIQUIDATION PLAN TESTS
# ==============================================================================

class TestLiquidationPlan:
    """Tests for liquidation plan creation."""
    
    def test_create_plan_basic(self, sample_portfolio_df, target_allocation, tax_context):
        """Test basic liquidation plan creation."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
        )
        
        assert isinstance(plan, LiquidationPlan)
        assert plan.total_needed == 50000
        assert plan.total_selected >= 50000  # Should meet or exceed need
        assert len(plan.securities) > 0
    
    def test_plan_meets_withdrawal_need(self, sample_portfolio_df, target_allocation, tax_context):
        """Plan should meet withdrawal need."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=30000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=30000,
            account_type='Brokerage',
            target_allocation=target_allocation,
        )
        
        assert plan.total_selected >= 30000
    
    def test_plan_calculates_tax_impact(self, sample_portfolio_df, target_allocation, tax_context):
        """Plan should calculate tax impact."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
        )
        
        assert plan.estimated_tax >= 0
        assert plan.total_ltcg >= 0
        assert plan.total_stcg >= 0
        assert plan.total_basis_returned >= 0
    
    def test_plan_tracks_allocation_changes(self, sample_portfolio_df, target_allocation, tax_context):
        """Plan should track allocation changes."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
        )
        
        assert 'Cash' in plan.pre_allocation
        assert 'Bonds' in plan.pre_allocation
        assert 'Stocks' in plan.pre_allocation
        assert 'Cash' in plan.post_allocation
        assert 'Bonds' in plan.post_allocation
        assert 'Stocks' in plan.post_allocation
    
    def test_partial_share_handling(self, sample_portfolio_df, target_allocation, tax_context):
        """Plan should handle partial shares correctly."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=10000,  # Small amount requiring partial shares
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=10000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            allow_partial_shares=True,
        )
        
        # Should have at least one partial liquidation
        partial_liquidations = [liq for liq in plan.securities if liq.is_partial]
        assert len(partial_liquidations) > 0


# ==============================================================================
# MULTI-ACCOUNT OPTIMIZATION TESTS
# ==============================================================================

class TestMultiAccountOptimization:
    """Tests for multi-account withdrawal optimization."""
    
    def test_multi_account_basic(self, sample_portfolio_df, target_allocation, tax_context):
        """Test basic multi-account optimization."""
        plans = optimize_multi_account_withdrawal(
            total_needed=100000,
            portfolio_df=sample_portfolio_df,
            account_priorities=['Brokerage', 'Traditional'],
            target_allocation=target_allocation,
            tax_context=tax_context,
        )
        
        assert isinstance(plans, dict)
        assert len(plans) > 0
        
        total_selected = sum(p.total_selected for p in plans.values())
        assert total_selected >= 100000
    
    def test_respects_account_priorities(self, sample_portfolio_df, target_allocation, tax_context):
        """Should respect account priority order."""
        plans = optimize_multi_account_withdrawal(
            total_needed=50000,
            portfolio_df=sample_portfolio_df,
            account_priorities=['Brokerage', 'Traditional'],
            target_allocation=target_allocation,
            tax_context=tax_context,
        )
        
        # Should withdraw from Brokerage first
        assert 'Brokerage' in plans
        
        # If Brokerage has enough, shouldn't need Traditional
        if plans['Brokerage'].total_selected >= 50000:
            assert 'Traditional' not in plans


# ==============================================================================
# UTILITY TESTS
# ==============================================================================

class TestUtilities:
    """Tests for utility functions."""
    
    def test_format_liquidation_summary(self, sample_portfolio_df, target_allocation, tax_context):
        """Test liquidation summary formatting."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
        )
        
        plans = {'Brokerage': plan}
        summary = format_liquidation_summary(plans)
        
        assert isinstance(summary, str)
        assert 'Multi-Account Liquidation Summary' in summary
        assert 'Brokerage Account' in summary
        assert '$' in summary


# ==============================================================================
# EDGE CASES AND ERROR HANDLING
# ==============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_portfolio(self, target_allocation, tax_context):
        """Should handle empty portfolio gracefully."""
        empty_df = pd.DataFrame()
        
        scores = score_securities_for_liquidation(
            portfolio_df=empty_df,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        assert scores == []
    
    def test_insufficient_securities(self, target_allocation, tax_context):
        """Should handle insufficient securities."""
        small_portfolio = pd.DataFrame([{
            'symbol': 'AAPL',
            'account_type': 'Brokerage',
            'qty': 10,
            'purchase_price': 150.0,
            'current_price': 180.0,
            'market_value': 1800.0,
            'sector': 'Technology',
            'name': 'Apple Inc.',
            'holding_period_days': 400,
        }])
        
        scores = score_securities_for_liquidation(
            portfolio_df=small_portfolio,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=50000,
            account_type='Brokerage',
            target_allocation=target_allocation,
        )
        
        # Should note shortfall
        assert plan.total_selected < 50000
        assert any('shortfall' in note.lower() for note in plan.notes)
    
    def test_zero_withdrawal_amount(self, sample_portfolio_df, target_allocation, tax_context):
        """Should handle zero withdrawal amount."""
        scores = score_securities_for_liquidation(
            portfolio_df=sample_portfolio_df,
            withdrawal_amount=0,
            account_type='Brokerage',
            target_allocation=target_allocation,
            current_agi=tax_context['agi'],
            filing_status=tax_context['filing_status'],
        )
        
        plan = create_liquidation_plan(
            scored_securities=scores,
            withdrawal_amount=0,
            account_type='Brokerage',
            target_allocation=target_allocation,
        )
        
        assert plan.total_selected == 0
        assert len(plan.securities) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
