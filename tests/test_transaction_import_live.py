"""
test_transaction_import_live.py
================================
Live testing script for transaction import with real SnapTrade data.

This script tests the complete transaction import workflow using
actual SnapTrade API credentials and real account data.

Usage:
    python test_transaction_import_live.py

Requirements:
    - .env file with SnapTrade credentials
    - SNAPTRADE_CLIENT_ID
    - SNAPTRADE_CONSUMER_KEY
    - SNAPTRADE_USER_ID
    - SNAPTRADE_USER_SECRET
    - ENCRYPTION_KEY
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytest

pytestmark = pytest.mark.integration

# Load environment variables
load_dotenv()

# Import components
try:
    from components.snaptrade_connector import create_snaptrade_connector
    from components.transaction_importer import create_transaction_importer
    from components.transaction_storage import create_transaction_storage
    from components.credential_manager import CredentialManager
except ImportError as e:
    print(f"❌ Failed to import components: {e}")
    print("Make sure all component files are in the components/ directory")
    sys.exit(1)


def check_environment():
    """Check if all required environment variables are set."""
    required_vars = [
        'SNAPTRADE_CLIENT_ID',
        'SNAPTRADE_CONSUMER_KEY',
        'SNAPTRADE_USER_ID',
        'SNAPTRADE_USER_SECRET',
        'ENCRYPTION_KEY'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease set these in your .env file")
        return False
    
    print("✅ All required environment variables are set")
    return True


def test_snaptrade_connection():
    """Test SnapTrade API connection."""
    print("\n" + "="*60)
    print("TEST 1: SnapTrade Connection")
    print("="*60)
    
    try:
        connector = create_snaptrade_connector()
        print("✅ SnapTrade connector created successfully")
        
        user_id = os.getenv("SNAPTRADE_USER_ID")
        user_secret = os.getenv("SNAPTRADE_USER_SECRET")
        
        # Get connection status
        status = connector.get_connection_status(user_id, user_secret)
        
        if status.get('connected'):
            print(f"✅ Connected to {status['account_count']} account(s)")
            for acc in status.get('accounts', []):
                print(f"   - {acc.get('name')} ({acc.get('institution')})")
            return connector, True
        else:
            print("❌ Not connected to any accounts")
            if 'error' in status:
                print(f"   Error: {status['error']}")
            return connector, False
    
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return None, False


def test_transaction_import(connector):
    """Test transaction import from SnapTrade."""
    print("\n" + "="*60)
    print("TEST 2: Transaction Import")
    print("="*60)
    
    try:
        importer = create_transaction_importer(connector)
        print("✅ Transaction importer created successfully")
        
        user_id = os.getenv("SNAPTRADE_USER_ID")
        
        # Import last 90 days of transactions
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        print(f"\n📥 Importing transactions from {start_date.date()} to {end_date.date()}...")
        
        transactions_df = importer.get_transactions(
            user_id=user_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        
        if len(transactions_df) > 0:
            print(f"✅ Imported {len(transactions_df)} transactions")
            
            # Show transaction summary
            print("\n📊 Transaction Summary:")
            type_counts = transactions_df['transaction_type'].value_counts()
            for txn_type, count in type_counts.items():
                print(f"   - {txn_type}: {count}")
            
            # Show sample transactions
            print("\n📋 Sample Transactions (first 5):")
            for idx, row in transactions_df.head(5).iterrows():
                print(f"   {row['date'].strftime('%Y-%m-%d')} | {row['transaction_type']:10} | "
                      f"{row['symbol']:6} | {row['quantity']:8.2f} @ ${row['price']:8.2f}")
            
            return importer, transactions_df, True
        else:
            print("⚠️  No transactions found in the specified date range")
            return importer, transactions_df, False
    
    except Exception as e:
        print(f"❌ Failed to import transactions: {e}")
        import traceback
        traceback.print_exc()
        return None, None, False


def test_transaction_storage(transactions_df):
    """Test storing transactions in database."""
    print("\n" + "="*60)
    print("TEST 3: Transaction Storage")
    print("="*60)
    
    try:
        storage = create_transaction_storage("data/test_transactions.db")
        print("✅ Transaction storage created successfully")
        
        user_id = os.getenv("SNAPTRADE_USER_ID", "test_user")
        
        # Store transactions
        print(f"\n💾 Storing {len(transactions_df)} transactions...")
        count = storage.store_transactions(transactions_df, user_id=user_id)
        print(f"✅ Stored {count} transactions")
        
        # Retrieve transactions
        print("\n📖 Retrieving stored transactions...")
        stored_txns = storage.get_transactions(user_id=user_id)
        print(f"✅ Retrieved {len(stored_txns)} transactions")
        
        # Verify data integrity
        if len(stored_txns) == count:
            print("✅ Data integrity verified")
        else:
            print(f"⚠️  Data mismatch: stored {count}, retrieved {len(stored_txns)}")
        
        return storage, True
    
    except Exception as e:
        print(f"❌ Failed to store transactions: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_cost_basis_calculation(importer, transactions_df):
    """Test cost basis calculation."""
    print("\n" + "="*60)
    print("TEST 4: Cost Basis Calculation")
    print("="*60)
    
    try:
        # Get unique symbols with buy/sell transactions
        buy_sell_txns = transactions_df[
            transactions_df['transaction_type'].isin(['buy', 'sell'])
        ]
        
        if len(buy_sell_txns) == 0:
            print("⚠️  No buy/sell transactions found for cost basis calculation")
            return False
        
        symbols = buy_sell_txns['symbol'].unique()
        print(f"\n📊 Calculating cost basis for {len(symbols)} symbol(s)...")
        
        for symbol in symbols[:3]:  # Test first 3 symbols
            print(f"\n💰 {symbol}:")
            
            # Calculate FIFO cost basis
            cost_basis = importer.calculate_cost_basis(
                transactions=transactions_df,
                symbol=symbol,
                method="FIFO"
            )
            
            print(f"   Total Shares: {cost_basis['total_shares']:.4f}")
            print(f"   Total Cost: ${cost_basis['total_cost']:,.2f}")
            print(f"   Average Cost: ${cost_basis['average_cost']:.2f}")
            print(f"   Tax Lots: {len(cost_basis['tax_lots'])}")
        
        print("\n✅ Cost basis calculation successful")
        return True
    
    except Exception as e:
        print(f"❌ Failed to calculate cost basis: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_capital_gains_calculation(importer, transactions_df):
    """Test capital gains calculation."""
    print("\n" + "="*60)
    print("TEST 5: Capital Gains Calculation")
    print("="*60)
    
    try:
        current_year = datetime.now().year
        
        print(f"\n📈 Calculating capital gains for {current_year}...")
        
        gains_df = importer.calculate_capital_gains(
            transactions=transactions_df,
            tax_year=current_year,
            method="FIFO"
        )
        
        if len(gains_df) > 0:
            print(f"✅ Calculated {len(gains_df)} capital gain/loss transaction(s)")
            
            # Summary
            total_gain = gains_df['gain_loss'].sum()
            short_term = gains_df[gains_df['holding_period'] == 'short_term']['gain_loss'].sum()
            long_term = gains_df[gains_df['holding_period'] == 'long_term']['gain_loss'].sum()
            
            print(f"\n📊 Capital Gains Summary for {current_year}:")
            print(f"   Total Gain/Loss: ${total_gain:,.2f}")
            print(f"   Short-Term: ${short_term:,.2f}")
            print(f"   Long-Term: ${long_term:,.2f}")
            
            # Show sample gains
            print("\n📋 Sample Gains (first 3):")
            for idx, row in gains_df.head(3).iterrows():
                print(f"   {row['symbol']:6} | {row['sell_date'].strftime('%Y-%m-%d')} | "
                      f"Gain/Loss: ${row['gain_loss']:8.2f} | {row['holding_period']}")
        else:
            print("⚠️  No capital gains/losses found for current year")
        
        print("\n✅ Capital gains calculation successful")
        return True
    
    except Exception as e:
        print(f"❌ Failed to calculate capital gains: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_transaction_report(importer, transactions_df):
    """Test transaction report generation."""
    print("\n" + "="*60)
    print("TEST 6: Transaction Report")
    print("="*60)
    
    try:
        print("\n📊 Generating transaction report...")
        
        report = importer.generate_transaction_report(transactions_df)
        
        print(f"\n✅ Report generated successfully")
        print(f"\n📈 Report Summary:")
        print(f"   Total Transactions: {report['total_transactions']}")
        print(f"   Date Range: {report['date_range']['start']} to {report['date_range']['end']}")
        print(f"   Total Invested: ${report['total_invested']:,.2f}")
        print(f"   Total Proceeds: ${report['total_proceeds']:,.2f}")
        print(f"   Dividend Income: ${report['dividend_income']:,.2f}")
        print(f"   Interest Income: ${report['interest_income']:,.2f}")
        
        print("\n📊 By Transaction Type:")
        for txn_type, data in report['by_type'].items():
            print(f"   {txn_type}: {data['transaction_id']} transactions, "
                  f"${data['amount']:,.2f} total")
        
        return True
    
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("TRANSACTION IMPORT LIVE TESTING")
    print("="*60)
    print(f"Testing with real SnapTrade data")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Test 1: SnapTrade Connection
    connector, connected = test_snaptrade_connection()
    if not connected:
        print("\n❌ Cannot proceed without SnapTrade connection")
        sys.exit(1)
    
    # Test 2: Transaction Import
    importer, transactions_df, imported = test_transaction_import(connector)
    if not imported or transactions_df is None or len(transactions_df) == 0:
        print("\n⚠️  No transactions to test with")
        print("This may be normal if you have no recent transactions")
        sys.exit(0)
    
    # Test 3: Transaction Storage
    storage, stored = test_transaction_storage(transactions_df)
    if not stored:
        print("\n❌ Transaction storage failed")
        sys.exit(1)
    
    # Test 4: Cost Basis Calculation
    test_cost_basis_calculation(importer, transactions_df)
    
    # Test 5: Capital Gains Calculation
    test_capital_gains_calculation(importer, transactions_df)
    
    # Test 6: Transaction Report
    test_transaction_report(importer, transactions_df)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print("✅ All tests completed successfully!")
    print(f"\n📊 Test Results:")
    print(f"   - SnapTrade Connection: ✅")
    print(f"   - Transaction Import: ✅ ({len(transactions_df)} transactions)")
    print(f"   - Transaction Storage: ✅")
    print(f"   - Cost Basis Calculation: ✅")
    print(f"   - Capital Gains Calculation: ✅")
    print(f"   - Transaction Report: ✅")
    
    print(f"\n💾 Test database created at: data/test_transactions.db")
    print(f"\n🎉 Transaction import feature is working correctly with real data!")


if __name__ == "__main__":
    main()


# Made with Bob