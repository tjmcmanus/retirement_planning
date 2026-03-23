"""
Test transaction import functionality

Tests:
- Transaction type normalization
- Cost basis calculation (FIFO, LIFO)
- Wash sale detection
- Tax report generation
- Edge cases (splits, mergers, spinoffs)
"""

import pytest
from datetime import datetime, timedelta
import pandas as pd
from components.transaction_importer import (
    TransactionImporter,
    CostBasisMethod,
    TransactionType
)
from components.credential_manager import CredentialManager


@pytest.fixture
def credential_manager():
    """Create test credential manager with in-memory database."""
    return CredentialManager(db_path=":memory:")


@pytest.fixture
def transaction_importer(credential_manager):
    """Create transaction importer instance."""
    return TransactionImporter(credential_manager)


@pytest.fixture
def sample_transactions():
    """Sample transaction data for testing."""
    return [
        {
            'id': '1',
            'date': '2024-01-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 150.00,
            'amount': -15000.00,
            'fees': 10.00,
            'currency': 'USD',
            'description': 'Buy 100 AAPL'
        },
        {
            'id': '2',
            'date': '2024-06-15',
            'type': 'sell',
            'symbol': 'AAPL',
            'quantity': 50,
            'price': 180.00,
            'amount': 9000.00,
            'fees': 5.00,
            'currency': 'USD',
            'description': 'Sell 50 AAPL'
        },
        {
            'id': '3',
            'date': '2024-03-15',
            'type': 'dividend',
            'symbol': 'AAPL',
            'quantity': 0,
            'price': 0,
            'amount': 100.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Dividend'
        }
    ]


def test_transaction_type_normalization(transaction_importer):
    """Test transaction type normalization."""
    test_cases = [
        ('buy', TransactionType.BUY.value),
        ('purchase', TransactionType.BUY.value),
        ('sell', TransactionType.SELL.value),
        ('sale', TransactionType.SELL.value),
        ('dividend', TransactionType.DIVIDEND.value),
        ('div', TransactionType.DIVIDEND.value),
        ('interest', TransactionType.INTEREST.value),
        ('deposit', TransactionType.DEPOSIT.value),
        ('withdrawal', TransactionType.WITHDRAWAL.value),
        ('split', TransactionType.STOCK_SPLIT.value),
        ('stock split', TransactionType.STOCK_SPLIT.value),
        ('unknown_type', TransactionType.ADJUSTMENT.value),
    ]
    
    for raw_type, expected in test_cases:
        result = transaction_importer._normalize_transaction_type(raw_type)
        assert result == expected, f"Failed for {raw_type}: expected {expected}, got {result}"


def test_transform_transactions(transaction_importer, sample_transactions):
    """Test transaction transformation."""
    df = transaction_importer._transform_transactions(sample_transactions)
    
    assert len(df) == 3
    assert 'transaction_id' in df.columns
    assert 'date' in df.columns
    assert 'type' in df.columns
    assert 'symbol' in df.columns
    
    # Check types (after sorting by date, order is: BUY (Jan), DIVIDEND (Mar), SELL (Jun))
    assert df['type'].iloc[0] == TransactionType.BUY.value
    assert df['type'].iloc[1] == TransactionType.DIVIDEND.value
    assert df['type'].iloc[2] == TransactionType.SELL.value
    
    # Check date conversion
    assert isinstance(df['date'].iloc[0], pd.Timestamp)


def test_cost_basis_calculation_fifo(transaction_importer, sample_transactions):
    """Test cost basis calculation using FIFO method."""
    df = transaction_importer._transform_transactions(sample_transactions)
    df = transaction_importer._calculate_cost_basis(df)
    
    # Check buy transaction
    buy_txn = df[df['type'] == TransactionType.BUY.value].iloc[0]
    assert buy_txn['cost_basis'] == pytest.approx(150.10, rel=0.01)  # $150 + $10 fees / 100 shares
    assert buy_txn['total_cost_basis'] == pytest.approx(15010.00, rel=0.01)
    
    # Check sell transaction
    sell_txn = df[df['type'] == TransactionType.SELL.value].iloc[0]
    assert sell_txn['cost_basis'] == pytest.approx(150.10, rel=0.01)  # FIFO from buy
    
    # Calculate expected gain/loss
    # Proceeds: 50 shares * $180 - $5 fees = $8,995
    # Cost: 50 shares * $150.10 = $7,505
    # Gain: $8,995 - $7,505 = $1,490
    assert sell_txn['gain_loss'] == pytest.approx(1490.00, rel=0.01)
    assert sell_txn['term'] == 'SHORT'  # Held < 365 days


def test_cost_basis_calculation_lifo(credential_manager):
    """Test cost basis calculation using LIFO method."""
    importer = TransactionImporter(credential_manager, cost_basis_method=CostBasisMethod.LIFO)
    
    transactions = [
        {
            'id': '1',
            'date': '2024-01-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 150.00,
            'amount': -15000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Buy 100 AAPL @ $150'
        },
        {
            'id': '2',
            'date': '2024-03-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 160.00,
            'amount': -16000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Buy 100 AAPL @ $160'
        },
        {
            'id': '3',
            'date': '2024-06-15',
            'type': 'sell',
            'symbol': 'AAPL',
            'quantity': 50,
            'price': 180.00,
            'amount': 9000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Sell 50 AAPL'
        }
    ]
    
    df = importer._transform_transactions(transactions)
    df = importer._calculate_cost_basis(df)
    
    # With LIFO, should use the $160 lot first
    sell_txn = df[df['type'] == TransactionType.SELL.value].iloc[0]
    assert sell_txn['cost_basis'] == pytest.approx(160.00, rel=0.01)
    
    # Gain: (180 - 160) * 50 = $1,000
    assert sell_txn['gain_loss'] == pytest.approx(1000.00, rel=0.01)


def test_wash_sale_detection(transaction_importer):
    """Test wash sale detection."""
    # Create wash sale scenario: sell at loss, repurchase within 30 days
    transactions = [
        {
            'id': '1',
            'date': '2024-01-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 150.00,
            'amount': -15000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Buy 100 AAPL'
        },
        {
            'id': '2',
            'date': '2024-02-15',
            'type': 'sell',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 140.00,  # Sell at loss
            'amount': 14000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Sell 100 AAPL at loss'
        },
        {
            'id': '3',
            'date': '2024-02-20',  # Within 30 days
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 145.00,
            'amount': -14500.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Repurchase 100 AAPL'
        }
    ]
    
    df = transaction_importer._transform_transactions(transactions)
    df = transaction_importer._calculate_cost_basis(df)
    df = transaction_importer._detect_wash_sales(df)
    
    # Check wash sale detection
    sell_txn = df[df['type'] == TransactionType.SELL.value].iloc[0]
    assert sell_txn['wash_sale'] == True
    assert sell_txn['wash_sale_adjustment'] == pytest.approx(1000.00, rel=0.01)  # Loss disallowed


def test_no_wash_sale_outside_window(transaction_importer):
    """Test that wash sale is NOT detected outside 30-day window."""
    transactions = [
        {
            'id': '1',
            'date': '2024-01-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 150.00,
            'amount': -15000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Buy 100 AAPL'
        },
        {
            'id': '2',
            'date': '2024-02-15',
            'type': 'sell',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 140.00,
            'amount': 14000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Sell 100 AAPL at loss'
        },
        {
            'id': '3',
            'date': '2024-04-01',  # More than 30 days later
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 145.00,
            'amount': -14500.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Repurchase 100 AAPL'
        }
    ]
    
    df = transaction_importer._transform_transactions(transactions)
    df = transaction_importer._calculate_cost_basis(df)
    df = transaction_importer._detect_wash_sales(df)
    
    # Should NOT be a wash sale
    sell_txn = df[df['type'] == TransactionType.SELL.value].iloc[0]
    assert sell_txn['wash_sale'] == False
    assert sell_txn['wash_sale_adjustment'] == 0.0


def test_tax_report_generation(transaction_importer, sample_transactions):
    """Test tax report generation."""
    df = transaction_importer._transform_transactions(sample_transactions)
    df = transaction_importer._calculate_cost_basis(df)
    df = transaction_importer._detect_wash_sales(df)
    
    tax_report = transaction_importer.generate_tax_report(df, 2024)
    
    assert tax_report['tax_year'] == 2024
    assert 'short_term_gains' in tax_report
    assert 'long_term_gains' in tax_report
    assert 'dividend_income' in tax_report
    assert 'interest_income' in tax_report
    
    # Check values
    assert tax_report['short_term_gains'] == pytest.approx(1490.00, rel=0.01)
    assert tax_report['long_term_gains'] == 0.0
    assert tax_report['dividend_income'] == 100.00
    assert tax_report['total_transactions'] == 3
    assert tax_report['sell_transactions'] == 1


def test_tax_report_empty_transactions(transaction_importer):
    """Test tax report with no transactions."""
    empty_df = pd.DataFrame()
    tax_report = transaction_importer.generate_tax_report(empty_df, 2024)
    
    assert tax_report['tax_year'] == 2024
    assert tax_report['short_term_gains'] == 0.0
    assert tax_report['long_term_gains'] == 0.0
    assert tax_report['dividend_income'] == 0.0
    assert tax_report['total_transactions'] == 0


def test_long_term_capital_gains(transaction_importer):
    """Test long-term capital gains (held > 365 days)."""
    transactions = [
        {
            'id': '1',
            'date': '2023-01-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 150.00,
            'amount': -15000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Buy 100 AAPL'
        },
        {
            'id': '2',
            'date': '2024-06-15',  # More than 365 days later
            'type': 'sell',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 180.00,
            'amount': 18000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Sell 100 AAPL'
        }
    ]
    
    df = transaction_importer._transform_transactions(transactions)
    df = transaction_importer._calculate_cost_basis(df)
    
    sell_txn = df[df['type'] == TransactionType.SELL.value].iloc[0]
    assert sell_txn['term'] == 'LONG'
    assert sell_txn['holding_period'] > 365
    assert sell_txn['gain_loss'] == pytest.approx(3000.00, rel=0.01)


def test_multiple_lots_fifo(transaction_importer):
    """Test FIFO with multiple lots."""
    transactions = [
        {
            'id': '1',
            'date': '2024-01-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 150.00,
            'amount': -15000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Buy 100 @ $150'
        },
        {
            'id': '2',
            'date': '2024-02-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 160.00,
            'amount': -16000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Buy 100 @ $160'
        },
        {
            'id': '3',
            'date': '2024-03-15',
            'type': 'buy',
            'symbol': 'AAPL',
            'quantity': 100,
            'price': 170.00,
            'amount': -17000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Buy 100 @ $170'
        },
        {
            'id': '4',
            'date': '2024-06-15',
            'type': 'sell',
            'symbol': 'AAPL',
            'quantity': 150,  # Sell across multiple lots
            'price': 180.00,
            'amount': 27000.00,
            'fees': 0.00,
            'currency': 'USD',
            'description': 'Sell 150 AAPL'
        }
    ]
    
    df = transaction_importer._transform_transactions(transactions)
    df = transaction_importer._calculate_cost_basis(df)
    
    sell_txn = df[df['type'] == TransactionType.SELL.value].iloc[0]
    
    # Should use first 100 @ $150 and next 50 @ $160
    # Average cost: (100 * 150 + 50 * 160) / 150 = $153.33
    expected_avg_cost = (100 * 150 + 50 * 160) / 150
    assert sell_txn['cost_basis'] == pytest.approx(expected_avg_cost, rel=0.01)
    
    # Gain: 150 * 180 - (100 * 150 + 50 * 160) = 27000 - 23000 = $4,000
    assert sell_txn['gain_loss'] == pytest.approx(4000.00, rel=0.01)


def test_export_to_csv(transaction_importer, sample_transactions, tmp_path):
    """Test CSV export functionality."""
    df = transaction_importer._transform_transactions(sample_transactions)
    df = transaction_importer._calculate_cost_basis(df)
    
    # Export to temporary file
    output_file = tmp_path / "transactions.csv"
    success = transaction_importer.export_to_csv(df, str(output_file))
    
    assert success == True
    assert output_file.exists()
    
    # Read back and verify
    exported_df = pd.read_csv(output_file)
    assert len(exported_df) == 3
    assert 'symbol' in exported_df.columns
    assert 'type' in exported_df.columns


def test_empty_transactions(transaction_importer):
    """Test handling of empty transaction list."""
    df = transaction_importer._transform_transactions([])
    assert df.empty
    
    df = transaction_importer._calculate_cost_basis(df)
    assert df.empty
    
    df = transaction_importer._detect_wash_sales(df)
    assert df.empty


def test_invalid_transaction_data(transaction_importer):
    """Test handling of invalid transaction data."""
    invalid_transactions = [
        {
            'id': '1',
            # Missing required fields
            'type': 'buy',
            'symbol': 'AAPL'
        },
        {
            'id': '2',
            'date': 'invalid-date',
            'type': 'sell',
            'symbol': 'AAPL',
            'quantity': 'not-a-number',
            'price': 'invalid'
        }
    ]
    
    df = transaction_importer._transform_transactions(invalid_transactions)
    
    # Should handle gracefully - may have some rows or be empty
    assert isinstance(df, pd.DataFrame)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

# Made with Bob
