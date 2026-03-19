"""
test_transaction_import.py
===========================
Comprehensive test suite for transaction import functionality.

Tests:
- Transaction import from SnapTrade
- Transaction storage and retrieval
- Cost basis calculation
- Tax lot management
- Capital gains calculation
- UI components
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import sqlite3
import os

# Import components to test
from components.transaction_importer import TransactionImporter, TransactionType
from components.transaction_storage import TransactionStorage
from components.snaptrade_connector import SnapTradeConnector


class TestTransactionImporter:
    """Test TransactionImporter class."""
    
    @pytest.fixture
    def mock_connector(self):
        """Create mock SnapTrade connector."""
        connector = Mock(spec=SnapTradeConnector)
        connector.client = Mock()
        connector._convert_to_dict = lambda x: x if isinstance(x, dict) else {}
        return connector
    
    @pytest.fixture
    def importer(self, mock_connector):
        """Create TransactionImporter instance."""
        return TransactionImporter(mock_connector)
    
    @pytest.fixture
    def sample_transactions(self):
        """Create sample transaction data."""
        return pd.DataFrame([
            {
                'transaction_id': 'txn1',
                'date': datetime(2024, 1, 15),
                'transaction_type': 'buy',
                'symbol': 'AAPL',
                'description': 'Apple Inc.',
                'quantity': 10,
                'price': 150.00,
                'amount': -1500.00,
                'fee': 0.00,
                'account_id': 'acc1',
                'account_name': 'Brokerage',
                'account_type': 'taxable'
            },
            {
                'transaction_id': 'txn2',
                'date': datetime(2024, 6, 15),
                'transaction_type': 'sell',
                'symbol': 'AAPL',
                'description': 'Apple Inc.',
                'quantity': 5,
                'price': 180.00,
                'amount': 900.00,
                'fee': 0.00,
                'account_id': 'acc1',
                'account_name': 'Brokerage',
                'account_type': 'taxable'
            },
            {
                'transaction_id': 'txn3',
                'date': datetime(2024, 3, 15),
                'transaction_type': 'dividend',
                'symbol': 'AAPL',
                'description': 'Dividend',
                'quantity': 0,
                'price': 0,
                'amount': 10.00,
                'fee': 0.00,
                'account_id': 'acc1',
                'account_name': 'Brokerage',
                'account_type': 'taxable'
            }
        ])
    
    def test_transaction_type_mapping(self, importer):
        """Test transaction type mapping."""
        assert importer._map_transaction_type('buy') == 'buy'
        assert importer._map_transaction_type('sell') == 'sell'
        assert importer._map_transaction_type('div') == 'dividend'
        assert importer._map_transaction_type('dividend') == 'dividend'
        assert importer._map_transaction_type('unknown') == 'other'
    
    def test_transform_transactions(self, importer):
        """Test transaction transformation."""
        raw_transactions = [
            {
                'id': 'txn1',
                'trade_date': '2024-01-15',
                'type': 'buy',
                'symbol': {'raw_symbol': 'AAPL', 'description': 'Apple Inc.'},
                'units': 10,
                'price': 150.00,
                'amount': -1500.00,
                'fee': 0.00,
                'account_id': 'acc1',
                'account_name': 'Brokerage',
                'account_type': 'taxable'
            }
        ]
        
        df = importer._transform_transactions(raw_transactions)
        
        assert len(df) == 1
        assert df.iloc[0]['transaction_id'] == 'txn1'
        assert df.iloc[0]['symbol'] == 'AAPL'
        assert df.iloc[0]['quantity'] == 10
        assert df.iloc[0]['price'] == 150.00
    
    def test_calculate_cost_basis_fifo(self, importer, sample_transactions):
        """Test FIFO cost basis calculation."""
        result = importer.calculate_cost_basis(
            transactions=sample_transactions,
            symbol='AAPL',
            method='FIFO'
        )
        
        assert result['symbol'] == 'AAPL'
        assert result['total_shares'] == 5  # 10 bought - 5 sold
        assert result['method'] == 'FIFO'
        assert len(result['tax_lots']) > 0
    
    def test_calculate_cost_basis_lifo(self, importer, sample_transactions):
        """Test LIFO cost basis calculation."""
        result = importer.calculate_cost_basis(
            transactions=sample_transactions,
            symbol='AAPL',
            method='LIFO'
        )
        
        assert result['symbol'] == 'AAPL'
        assert result['total_shares'] == 5
        assert result['method'] == 'LIFO'
    
    def test_calculate_capital_gains(self, importer, sample_transactions):
        """Test capital gains calculation."""
        gains = importer.calculate_capital_gains(
            transactions=sample_transactions,
            tax_year=2024,
            method='FIFO'
        )
        
        assert len(gains) > 0
        assert 'symbol' in gains.columns
        assert 'gain_loss' in gains.columns
        assert 'holding_period' in gains.columns
    
    def test_generate_transaction_report(self, importer, sample_transactions):
        """Test transaction report generation."""
        report = importer.generate_transaction_report(sample_transactions)
        
        assert 'total_transactions' in report
        assert report['total_transactions'] == 3
        assert 'by_type' in report
        assert 'total_invested' in report
        assert 'dividend_income' in report


class TestTransactionStorage:
    """Test TransactionStorage class."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database."""
        db_path = tmp_path / "test_transactions.db"
        return str(db_path)
    
    @pytest.fixture
    def storage(self, temp_db):
        """Create TransactionStorage instance."""
        return TransactionStorage(temp_db)
    
    @pytest.fixture
    def sample_transactions_df(self):
        """Create sample transaction DataFrame."""
        return pd.DataFrame([
            {
                'transaction_id': 'txn1',
                'date': datetime(2024, 1, 15),
                'transaction_type': 'buy',
                'symbol': 'AAPL',
                'description': 'Apple Inc.',
                'quantity': 10,
                'price': 150.00,
                'amount': -1500.00,
                'fee': 0.00,
                'account_id': 'acc1',
                'account_name': 'Brokerage',
                'account_type': 'taxable',
                'raw_data': '{}'
            }
        ])
    
    def test_database_initialization(self, storage, temp_db):
        """Test database tables are created."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Check transactions table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
        )
        assert cursor.fetchone() is not None
        
        # Check tax_lots table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tax_lots'"
        )
        assert cursor.fetchone() is not None
        
        # Check capital_gains table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='capital_gains'"
        )
        assert cursor.fetchone() is not None
        
        conn.close()
    
    def test_store_transactions(self, storage, sample_transactions_df):
        """Test storing transactions."""
        count = storage.store_transactions(sample_transactions_df, user_id="test_user")
        
        assert count == 1
        
        # Verify stored
        transactions = storage.get_transactions(user_id="test_user")
        assert len(transactions) == 1
        assert transactions.iloc[0]['symbol'] == 'AAPL'
    
    def test_get_transactions_with_filters(self, storage, sample_transactions_df):
        """Test retrieving transactions with filters."""
        storage.store_transactions(sample_transactions_df, user_id="test_user")
        
        # Filter by symbol
        transactions = storage.get_transactions(
            user_id="test_user",
            symbol="AAPL"
        )
        assert len(transactions) == 1
        
        # Filter by account
        transactions = storage.get_transactions(
            user_id="test_user",
            account_id="acc1"
        )
        assert len(transactions) == 1
        
        # Filter by date range
        transactions = storage.get_transactions(
            user_id="test_user",
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
        assert len(transactions) == 1
    
    def test_store_tax_lot(self, storage):
        """Test storing tax lot."""
        lot_id = storage.store_tax_lot(
            user_id="test_user",
            account_id="acc1",
            symbol="AAPL",
            purchase_date="2024-01-15",
            quantity=10,
            price=150.00,
            transaction_id="txn1"
        )
        
        assert lot_id > 0
        
        # Verify stored
        lots = storage.get_tax_lots(user_id="test_user", symbol="AAPL")
        assert len(lots) == 1
        assert lots.iloc[0]['quantity'] == 10
    
    def test_update_tax_lot_quantity(self, storage):
        """Test updating tax lot quantity."""
        # Create tax lot
        lot_id = storage.store_tax_lot(
            user_id="test_user",
            account_id="acc1",
            symbol="AAPL",
            purchase_date="2024-01-15",
            quantity=10,
            price=150.00
        )
        
        # Update quantity
        success = storage.update_tax_lot_quantity(lot_id, 5)
        assert success
        
        # Verify updated
        lots = storage.get_tax_lots(user_id="test_user", symbol="AAPL")
        assert lots.iloc[0]['remaining_quantity'] == 5
    
    def test_store_capital_gain(self, storage):
        """Test storing capital gain."""
        gain_id = storage.store_capital_gain(
            user_id="test_user",
            account_id="acc1",
            symbol="AAPL",
            sell_date="2024-06-15",
            sell_transaction_id="txn2",
            quantity=5,
            proceeds=900.00,
            cost_basis=750.00,
            holding_period="long_term",
            tax_year=2024
        )
        
        assert gain_id > 0
        
        # Verify stored
        gains = storage.get_capital_gains(user_id="test_user", tax_year=2024)
        assert len(gains) == 1
        assert gains.iloc[0]['gain_loss'] == 150.00
    
    def test_get_transaction_summary(self, storage, sample_transactions_df):
        """Test transaction summary generation."""
        storage.store_transactions(sample_transactions_df, user_id="test_user")
        
        summary = storage.get_transaction_summary(user_id="test_user")
        
        assert 'total_transactions' in summary
        assert summary['total_transactions'] == 1
        assert 'by_type' in summary


class TestIntegration:
    """Integration tests for complete workflow."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database."""
        db_path = tmp_path / "test_integration.db"
        return str(db_path)
    
    @pytest.fixture
    def mock_connector(self):
        """Create mock SnapTrade connector."""
        connector = Mock(spec=SnapTradeConnector)
        connector.client = Mock()
        connector._convert_to_dict = lambda x: x if isinstance(x, dict) else {}
        
        # Mock get_accounts
        connector.get_accounts = Mock(return_value=[
            {'id': 'acc1', 'name': 'Brokerage', 'type': 'taxable'}
        ])
        
        # Mock transactions API
        mock_activities = Mock()
        mock_activities.body = [
            {
                'id': 'txn1',
                'trade_date': '2024-01-15',
                'type': 'buy',
                'symbol': {'raw_symbol': 'AAPL', 'description': 'Apple Inc.'},
                'units': 10,
                'price': 150.00,
                'amount': -1500.00,
                'fee': 0.00
            }
        ]
        connector.client.transactions = Mock()
        connector.client.transactions.get_activities = Mock(return_value=mock_activities)
        
        return connector
    
    def test_end_to_end_workflow(self, mock_connector, temp_db):
        """Test complete transaction import workflow."""
        # Initialize components
        importer = TransactionImporter(mock_connector)
        storage = TransactionStorage(temp_db)
        
        # Import transactions
        transactions_df = importer.get_transactions(
            user_id="test_user",
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
        
        assert len(transactions_df) > 0
        
        # Store transactions
        count = storage.store_transactions(transactions_df, user_id="test_user")
        assert count > 0
        
        # Retrieve transactions
        stored_txns = storage.get_transactions(user_id="test_user")
        assert len(stored_txns) == count
        
        # Calculate cost basis
        cost_basis = importer.calculate_cost_basis(
            transactions=stored_txns,
            symbol='AAPL',
            method='FIFO'
        )
        assert cost_basis['symbol'] == 'AAPL'
        
        # Generate report
        report = importer.generate_transaction_report(stored_txns)
        assert report['total_transactions'] > 0


def test_transaction_type_enum():
    """Test TransactionType enum."""
    assert TransactionType.BUY.value == 'buy'
    assert TransactionType.SELL.value == 'sell'
    assert TransactionType.DIVIDEND.value == 'dividend'
    assert TransactionType.INTEREST.value == 'interest'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# Made with Bob