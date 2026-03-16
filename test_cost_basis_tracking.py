"""
Comprehensive test suite for cost basis tracking feature.

Tests the BrokerageAccount and BrokerageTransaction classes, FIFO withdrawal logic,
and integration with the withdrawal strategy engine.
"""

import pytest
from datetime import datetime
from strategy import (
    BrokerageTransaction,
    BrokerageAccount,
    PortfolioBalances,
    WithdrawalStrategyEngine,
    YearlyStrategy
)


class TestBrokerageTransaction:
    """Test BrokerageTransaction data structure."""
    
    def test_transaction_creation(self):
        """Test creating a brokerage transaction."""
        txn = BrokerageTransaction(
            year=2024,
            transfer_date=datetime(2024, 1, 15),
            original_amount=10000.0,
            cost_basis=10000.0,
            current_value=10000.0,
            years_held=0,
            source="Traditional→Brokerage"
        )
        
        assert txn.year == 2024
        assert txn.original_amount == 10000.0
        assert txn.cost_basis == 10000.0
        assert txn.current_value == 10000.0
        assert txn.years_held == 0
        assert txn.source == "Traditional→Brokerage"
    
    def test_transaction_with_gains(self):
        """Test transaction with capital gains."""
        txn = BrokerageTransaction(
            year=2024,
            transfer_date=datetime(2024, 1, 15),
            original_amount=10000.0,
            cost_basis=10000.0,
            current_value=12000.0,  # 20% gain
            years_held=1,
            source="Traditional→Brokerage"
        )
        
        assert txn.current_value == 12000.0
        assert txn.years_held == 1


class TestBrokerageAccount:
    """Test BrokerageAccount with FIFO withdrawal logic."""
    
    def test_empty_account(self):
        """Test empty brokerage account."""
        account = BrokerageAccount()
        
        assert account.total_value == 0.0
        assert account.total_basis == 0.0
        assert account.total_gains == 0.0
        assert account.ltcg_ratio == 0.0
        assert account.basis_ratio == 0.0
        assert len(account.lots) == 0
    
    def test_add_single_transfer(self):
        """Test adding a single transfer to brokerage account."""
        account = BrokerageAccount()
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        
        assert account.total_value == 10000.0
        assert account.total_basis == 10000.0
        assert account.total_gains == 0.0
        assert account.ltcg_ratio == 0.0
        assert account.basis_ratio == 1.0
        assert len(account.lots) == 1
    
    def test_add_multiple_transfers(self):
        """Test adding multiple transfers."""
        account = BrokerageAccount()
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        account.add_transfer(2025, 5000.0, "Traditional→Brokerage")
        account.add_transfer(2026, 8000.0, "Traditional→Brokerage")
        
        assert account.total_value == 23000.0
        assert account.total_basis == 23000.0
        assert len(account.lots) == 3
    
    def test_annual_growth(self):
        """Test applying annual growth to account."""
        account = BrokerageAccount()
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        
        # Apply 10% growth
        account.apply_annual_growth(0.10, 2025)
        
        assert account.total_value == 11000.0
        assert account.total_basis == 10000.0  # Basis doesn't change
        assert account.total_gains == 1000.0
        assert account.ltcg_ratio == pytest.approx(1000.0 / 11000.0)
        assert account.basis_ratio == pytest.approx(10000.0 / 11000.0)
    
    def test_fifo_withdrawal_single_lot(self):
        """Test FIFO withdrawal from single lot."""
        account = BrokerageAccount()
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        account.apply_annual_growth(0.20, 2025)  # Grows to $12,000
        
        # Withdraw $6,000 (50% of account)
        basis_returned, ltcg = account.withdraw_fifo(6000.0, 2025)
        
        # Should return 50% of basis and 50% of gains
        assert basis_returned == pytest.approx(5000.0)
        assert ltcg == pytest.approx(1000.0)
        assert account.total_value == pytest.approx(6000.0)
        assert account.total_basis == pytest.approx(5000.0)
    
    def test_fifo_withdrawal_multiple_lots(self):
        """Test FIFO withdrawal across multiple lots."""
        account = BrokerageAccount()
        
        # Add three lots
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        account.apply_annual_growth(0.10, 2025)  # Lot 1: $11,000
        
        account.add_transfer(2025, 5000.0, "Traditional→Brokerage")
        account.apply_annual_growth(0.10, 2026)  # Lot 1: $12,100, Lot 2: $5,500
        
        account.add_transfer(2026, 3000.0, "Traditional→Brokerage")
        # Total: $20,600 ($18,000 basis, $2,600 gains)
        
        # Withdraw $15,000 (should take all of lot 1, all of lot 2, part of lot 3)
        basis_returned, ltcg = account.withdraw_fifo(15000.0, 2026)
        
        # Lot 1: $10,000 basis, $2,100 gains = $12,100 total
        # Lot 2: $5,000 basis, $500 gains = $5,500 total
        # Lot 3 (partial): Need $2,900 more, all basis (no gains yet)
        expected_basis = 10000.0 + 5000.0 + 2900.0
        expected_ltcg = 2100.0 + 500.0 + 0.0
        
        assert basis_returned == pytest.approx(expected_basis, rel=0.01)
        assert ltcg == pytest.approx(expected_ltcg, rel=0.01)
        assert len(account.lots) == 1  # Only partial lot 3 remains
    
    def test_fifo_withdrawal_complete_depletion(self):
        """Test withdrawing entire account balance."""
        account = BrokerageAccount()
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        account.apply_annual_growth(0.50, 2025)  # Grows to $15,000
        
        # Withdraw entire balance
        basis_returned, ltcg = account.withdraw_fifo(15000.0, 2025)
        
        assert basis_returned == pytest.approx(10000.0)
        assert ltcg == pytest.approx(5000.0)
        assert account.total_value == pytest.approx(0.0)
        assert len(account.lots) == 0
    
    def test_fifo_withdrawal_exceeds_balance(self):
        """Test withdrawal amount exceeding account balance."""
        account = BrokerageAccount()
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        
        # Try to withdraw more than available
        basis_returned, ltcg = account.withdraw_fifo(15000.0, 2024)
        
        # Should only withdraw what's available
        assert basis_returned == pytest.approx(10000.0)
        assert ltcg == pytest.approx(0.0)
        assert account.total_value == pytest.approx(0.0)
    
    def test_ltcg_ratio_calculation(self):
        """Test LTCG ratio calculation with various scenarios."""
        account = BrokerageAccount()
        
        # Scenario 1: No gains (new transfer)
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        assert account.ltcg_ratio == 0.0
        assert account.basis_ratio == 1.0
        
        # Scenario 2: 20% gains
        account.apply_annual_growth(0.20, 2025)
        assert account.ltcg_ratio == pytest.approx(2000.0 / 12000.0)
        assert account.basis_ratio == pytest.approx(10000.0 / 12000.0)
        
        # Scenario 3: After partial withdrawal
        account.withdraw_fifo(6000.0, 2025)
        # Remaining: $6,000 value, $5,000 basis, $1,000 gains
        assert account.ltcg_ratio == pytest.approx(1000.0 / 6000.0)
        assert account.basis_ratio == pytest.approx(5000.0 / 6000.0)
    
    def test_years_held_tracking(self):
        """Test that years_held is properly tracked."""
        account = BrokerageAccount()
        account.add_transfer(2024, 10000.0, "Traditional→Brokerage")
        
        assert account.lots[0].years_held == 0
        
        # Apply growth for multiple years
        account.apply_annual_growth(0.10, 2025)
        assert account.lots[0].years_held == 1
        
        account.apply_annual_growth(0.10, 2026)
        assert account.lots[0].years_held == 2
        
        account.apply_annual_growth(0.10, 2027)
        assert account.lots[0].years_held == 3


class TestWithdrawalStrategyIntegration:
    """Test integration of cost basis tracking with withdrawal strategy."""
    
    def test_brokerage_account_initialization(self):
        """Test that WithdrawalStrategyEngine initializes brokerage account."""
        engine = WithdrawalStrategyEngine()
        
        # Brokerage account should be None initially
        assert engine.brokerage_account is None
    
    def test_strategy_includes_cost_basis_fields(self):
        """Test that YearlyStrategy includes cost basis fields."""
        # Create a sample strategy result
        balances = PortfolioBalances(
            cash=50000,
            taxable=200000,
            traditional=600000,
            roth=150000,
            daf=0
        )
        
        strategy = YearlyStrategy(
            year=2024,
            age_primary=55,
            age_spouse=53,
            stage="Stage 1: Accumulation",
            wages=150000,
            ss_benefits=0,
            rmd_amount=0,
            traditional_withdrawal=0,
            taxable_withdrawal=0,
            roth_withdrawal=0,
            roth_conversion=0,
            ltcg_harvested=0,
            daf_contribution=0,
            expenses=80000,
            agi=150000,
            magi=150000,
            federal_tax=25000,
            state_tax=8000,
            irmaa_penalty=0,
            aca_premium=0,
            balances=balances,
            basis_returned=0.0,
            brokerage_ltcg_ratio=0.0,
            brokerage_basis_ratio=0.0
        )
        
        assert hasattr(strategy, 'basis_returned')
        assert hasattr(strategy, 'brokerage_ltcg_ratio')
        assert hasattr(strategy, 'brokerage_basis_ratio')
        assert strategy.basis_returned == 0.0


class TestCostBasisScenarios:
    """Test realistic cost basis scenarios."""
    
    def test_traditional_60_40_assumption(self):
        """Test that 60/40 assumption is a special case."""
        account = BrokerageAccount()
        
        # Create scenario where gains are exactly 40% of value
        account.add_transfer(2024, 60000.0, "Traditional→Brokerage")
        # Need to grow by 66.67% to get 40% LTCG ratio
        # $60k * 1.6667 = $100k, gains = $40k, ratio = 40%
        account.apply_annual_growth(0.6667, 2025)
        
        assert account.ltcg_ratio == pytest.approx(0.40, rel=0.01)
        assert account.basis_ratio == pytest.approx(0.60, rel=0.01)
    
    def test_early_retirement_scenario(self):
        """Test early retirement with multiple years of transfers and growth."""
        account = BrokerageAccount()
        
        # Year 1: Transfer $50k from Traditional
        account.add_transfer(2024, 50000.0, "Traditional→Brokerage")
        account.apply_annual_growth(0.08, 2025)  # 8% growth
        
        # Year 2: Transfer another $50k
        account.add_transfer(2025, 50000.0, "Traditional→Brokerage")
        account.apply_annual_growth(0.08, 2026)
        
        # Year 3: Transfer another $50k
        account.add_transfer(2026, 50000.0, "Traditional→Brokerage")
        account.apply_annual_growth(0.08, 2027)
        
        # Year 4: Start withdrawing for expenses
        # Account should have grown significantly
        initial_value = account.total_value
        initial_basis = account.total_basis
        
        # Withdraw $60k for living expenses
        basis_returned, ltcg = account.withdraw_fifo(60000.0, 2027)
        
        # Verify FIFO: oldest lots withdrawn first
        assert basis_returned > 0
        assert ltcg > 0
        assert basis_returned + ltcg == pytest.approx(60000.0)
        
        # Verify account state
        assert account.total_value == pytest.approx(initial_value - 60000.0)
        assert account.total_basis == pytest.approx(initial_basis - basis_returned)
    
    def test_high_growth_scenario(self):
        """Test scenario with high market growth."""
        account = BrokerageAccount()
        account.add_transfer(2024, 100000.0, "Traditional→Brokerage")
        
        # Simulate 5 years of 15% annual growth
        for year in range(2025, 2030):
            account.apply_annual_growth(0.15, year)
        
        # After 5 years at 15%: $100k * 1.15^5 = $201,136
        assert account.total_value == pytest.approx(201136.0, rel=0.01)
        assert account.total_basis == 100000.0
        
        # LTCG ratio should be high
        expected_ltcg_ratio = 101136.0 / 201136.0
        assert account.ltcg_ratio == pytest.approx(expected_ltcg_ratio, rel=0.01)
    
    def test_market_downturn_scenario(self):
        """Test scenario with market losses."""
        account = BrokerageAccount()
        account.add_transfer(2024, 100000.0, "Traditional→Brokerage")
        
        # Market drops 20%
        account.apply_annual_growth(-0.20, 2025)
        
        assert account.total_value == pytest.approx(80000.0)
        assert account.total_basis == 100000.0
        
        # Negative gains (losses)
        assert account.total_gains == pytest.approx(-20000.0)
        
        # LTCG ratio should be negative (but we treat as 0 for tax purposes)
        # In reality, this would be a capital loss
        assert account.ltcg_ratio < 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
