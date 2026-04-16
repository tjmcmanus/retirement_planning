"""
Unit Tests for Strategy Core Components

Tests the refactored strategy core modules with dependency injection
and comprehensive type checking.
"""

import pytest
from typing import Tuple

from strategy_core.models import (
    PortfolioBalances,
    BrokerageAccount,
    BrokerageTransaction,
    DecisionLog,
    DecisionReason,
    YearlyStrategy,
)
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager
from strategy_core.decision_logger import DecisionLogger
from strategy_core.base_strategy import BaseLifeStageStrategy


class TestPortfolioBalances:
    """Test PortfolioBalances model"""
    
    def test_creation(self):
        """Test creating portfolio balances"""
        balances = PortfolioBalances(
            cash=50000,
            taxable=500000,
            traditional=800000,
            roth=200000,
            daf=50000
        )
        
        assert balances.cash == 50000
        assert balances.taxable == 500000
        assert balances.traditional == 800000
        assert balances.roth == 200000
        assert balances.daf == 50000
    
    def test_total(self):
        """Test total calculation"""
        balances = PortfolioBalances(
            cash=50000,
            taxable=500000,
            traditional=800000,
            roth=200000,
            daf=50000
        )
        
        assert balances.total() == 1600000
    
    def test_negative_balance_validation(self):
        """Test that negative balances raise ValueError"""
        with pytest.raises(ValueError):
            PortfolioBalances(
                cash=-1000,
                taxable=500000,
                traditional=800000,
                roth=200000
            )


class TestBrokerageAccount:
    """Test BrokerageAccount model"""
    
    def test_creation(self):
        """Test creating brokerage account"""
        account = BrokerageAccount(owner="joint")
        assert account.owner == "joint"
        assert len(account.transactions) == 0
    
    def test_add_transaction(self):
        """Test adding transactions"""
        account = BrokerageAccount()
        account.add_transfer(100000, 80000, 2020, "Initial deposit")
        
        assert len(account.transactions) == 1
        assert account.total_value() == 100000
        assert account.total_basis() == 80000
        assert account.total_gains() == 20000
    
    def test_ltcg_ratio(self):
        """Test LTCG ratio calculation"""
        account = BrokerageAccount()
        account.add_transfer(100000, 80000, 2020)
        
        assert account.ltcg_ratio() == 0.2  # 20k gains / 100k value
    
    def test_withdraw_fifo(self):
        """Test FIFO withdrawal"""
        account = BrokerageAccount()
        account.add_transfer(100000, 80000, 2020)
        account.add_transfer(50000, 45000, 2021)
        
        # Withdraw 120k (should take all of first, part of second)
        withdrawn, ltcg = account.withdraw_fifo(120000)
        
        assert withdrawn == 120000
        assert ltcg == pytest.approx(22000, rel=0.01)  # 20k + 2k
        assert account.total_value() == 30000
    
    def test_apply_growth(self):
        """Test applying annual growth"""
        account = BrokerageAccount()
        account.add_transfer(100000, 80000, 2020)
        
        account.apply_annual_growth(0.07)
        
        assert account.total_value() == pytest.approx(107000, rel=0.01)
        assert account.total_basis() == 80000  # Basis doesn't grow


class TestDecisionLog:
    """Test DecisionLog model"""
    
    def test_creation(self):
        """Test creating decision log"""
        log = DecisionLog()
        assert len(log.all_decisions()) == 0
    
    def test_add_decision(self):
        """Test adding decisions"""
        log = DecisionLog()
        log.add(
            'roth_conversion',
            'Roth Conversion',
            'Convert $45,000',
            'Optimize BETR',
            amount=45000,
            tax=10800
        )
        
        assert len(log.all_decisions()) == 1
        assert len(log.roth_conversion) == 1
        
        decision = log.roth_conversion[0]
        assert decision.decision == 'Roth Conversion'
        assert decision.action == 'Convert $45,000'
        assert decision.values['amount'] == 45000
    
    def test_summary_lines(self):
        """Test summary generation"""
        log = DecisionLog()
        log.add('roth_conversion', 'Convert', 'Convert $45k', 'Test', amount=45000)
        
        summary = log.summary_lines()
        assert len(summary) == 1
        assert 'Convert' in summary[0]
        assert 'amount=45000' in summary[0]


class TestAccountManager:
    """Test AccountManager implementation"""
    
    def test_withdraw_from_cash(self):
        """Test cash withdrawal"""
        manager = AccountManager()
        
        withdrawn, remaining = manager.withdraw_from_cash(30000, 50000)
        
        assert withdrawn == 30000
        assert remaining == 20000
    
    def test_withdraw_from_cash_insufficient(self):
        """Test cash withdrawal with insufficient funds"""
        manager = AccountManager()
        
        withdrawn, remaining = manager.withdraw_from_cash(60000, 50000)
        
        assert withdrawn == 50000
        assert remaining == 0
    
    def test_withdraw_from_taxable(self):
        """Test taxable withdrawal"""
        manager = AccountManager()
        account = BrokerageAccount()
        account.add_transfer(100000, 80000, 2020)
        
        withdrawn, ltcg, remaining = manager.withdraw_from_taxable(
            50000, account
        )
        
        assert withdrawn == 50000
        assert ltcg == pytest.approx(10000, rel=0.01)
        assert remaining == 50000
    
    def test_convert_traditional_to_roth(self):
        """Test Roth conversion"""
        manager = AccountManager()
        
        converted, new_trad, new_roth = manager.convert_traditional_to_roth(
            45000, 800000, 200000
        )
        
        assert converted == 45000
        assert new_trad == 755000
        assert new_roth == 245000


class TestDecisionLogger:
    """Test DecisionLogger implementation"""
    
    def test_creation(self):
        """Test creating decision logger"""
        logger = DecisionLogger()
        assert len(logger.get_all_decisions()) == 0
    
    def test_log_decision(self):
        """Test logging decisions"""
        logger = DecisionLogger()
        
        logger.log_decision(
            'roth_conversion',
            'Roth Conversion',
            'Convert $45,000',
            'Optimize tax bracket',
            amount=45000
        )
        
        decisions = logger.get_all_decisions()
        assert len(decisions) == 1
        assert decisions[0].decision == 'Roth Conversion'
    
    def test_get_summary(self):
        """Test getting summary"""
        logger = DecisionLogger()
        logger.log_decision('roth_conversion', 'Convert', 'Convert $45k', 'Test')
        
        summary = logger.get_summary()
        assert len(summary) == 1
        assert 'Convert' in summary[0]
    
    def test_clear(self):
        """Test clearing log"""
        logger = DecisionLogger()
        logger.log_decision('roth_conversion', 'Convert', 'Convert $45k', 'Test')
        
        logger.clear()
        assert len(logger.get_all_decisions()) == 0


class MockLifeStageStrategy(BaseLifeStageStrategy):
    """Mock strategy for testing base class"""
    
    def __init__(self, tax_calculator=None, account_manager=None):
        super().__init__(
            name="Mock Strategy",
            description="Test strategy",
            tax_calculator=tax_calculator,
            account_manager=account_manager
        )
    
    def applies(self, age_primary, age_spouse, year, has_wages, has_ss):
        return True
    
    def calculate_strategy(self, year, balances, expenses, **kwargs):
        strategy = self._create_yearly_strategy(
            year,
            kwargs.get('age_primary', 65),
            kwargs.get('age_spouse', 63),
            balances
        )
        return strategy


class TestBaseLifeStageStrategy:
    """Test BaseLifeStageStrategy implementation"""
    
    def test_creation(self):
        """Test creating strategy"""
        strategy = MockLifeStageStrategy()
        assert strategy.name == "Mock Strategy"
        assert strategy.description == "Test strategy"
    
    def test_create_yearly_strategy(self):
        """Test creating yearly strategy"""
        strategy = MockLifeStageStrategy()
        balances = PortfolioBalances(
            cash=50000,
            taxable=500000,
            traditional=800000,
            roth=200000
        )
        
        yearly = strategy._create_yearly_strategy(2024, 65, 63, balances)
        
        assert yearly.year == 2024
        assert yearly.age_primary == 65
        assert yearly.age_spouse == 63
        assert yearly.stage == "Mock Strategy"
        assert yearly.cash_balance == 50000
    
    def test_calculate_total_income(self):
        """Test total income calculation"""
        strategy = MockLifeStageStrategy()
        
        total = strategy._calculate_total_income(
            wages=75000,
            ss_benefits=30000,
            withdrawals={'cash': 10000, 'taxable': 20000}
        )
        
        assert total == 135000
    
    def test_calculate_shortfall(self):
        """Test shortfall calculation"""
        strategy = MockLifeStageStrategy()
        
        shortfall = strategy._calculate_shortfall(
            expenses=80000,
            income=50000,
            taxes=10000,
            healthcare=5000
        )
        
        assert shortfall == 45000  # 80k + 10k + 5k - 50k
    
    def test_determine_withdrawal_sequence(self):
        """Test withdrawal sequence"""
        strategy = MockLifeStageStrategy()
        balances = PortfolioBalances(
            cash=30000,
            taxable=500000,
            traditional=800000,
            roth=200000
        )
        
        withdrawals = strategy._determine_withdrawal_sequence(50000, balances)
        
        assert withdrawals['cash'] == 30000
        assert withdrawals['taxable'] == 20000
        assert withdrawals['traditional'] == 0
        assert withdrawals['roth'] == 0


class TestYearlyStrategy:
    """Test YearlyStrategy model"""
    
    def test_creation(self):
        """Test creating yearly strategy"""
        strategy = YearlyStrategy(
            year=2024,
            age_primary=65,
            age_spouse=63,
            stage="Test Stage"
        )
        
        assert strategy.year == 2024
        assert strategy.age_primary == 65
        assert strategy.stage == "Test Stage"
    
    def test_validate_fund_conservation(self):
        """Test fund conservation validation"""
        strategy = YearlyStrategy(
            year=2024,
            age_primary=65,
            age_spouse=63,
            stage="Test",
            wages=75000,
            cash_withdrawal=10000,
            federal_tax=15000,
            state_tax=5000
        )
        
        # Should pass: 75k + 10k = 85k, 80k expenses + 20k taxes = 100k
        # This will fail, which is expected for this test
        with pytest.raises(ValueError):
            strategy.validate_fund_conservation(expenses=80000)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
