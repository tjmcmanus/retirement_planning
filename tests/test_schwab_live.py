"""
Live Integration Tests for Schwab Direct API
Tests actual connection to Schwab API using real credentials

WARNING: These tests make real API calls to Schwab.
Only run when you have valid credentials and want to test the live connection.

Usage:
    pytest test_schwab_live.py -v -s
"""

import pytest
import os
from datetime import datetime
from components.schwab_connector import SchwabConnector
from components.schwab_data_transformer import SchwabDataTransformer
from components.credential_manager import CredentialManager


# Skip all tests if credentials not available
pytestmark = pytest.mark.skipif(
    not os.getenv("SCHWAB_APP_KEY") or not os.getenv("SCHWAB_APP_SECRET"),
    reason="Schwab credentials not configured"
)


class TestSchwabLiveConnection:
    """Live tests against actual Schwab API"""
    
    @pytest.fixture(scope="class")
    def schwab_connector(self):
        """Create Schwab connector with real credentials"""
        app_key = os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_APP_SECRET")
        callback_url = os.getenv("SCHWAB_CALLBACK_URL", "https://localhost:8080/callback")
        
        connector = SchwabConnector(
            app_key=app_key,
            app_secret=app_secret,
            callback_url=callback_url,
            credential_manager=CredentialManager()
        )
        
        # Try to load saved tokens
        if not connector.load_saved_tokens():
            pytest.skip("No saved tokens found. Complete OAuth authorization first.")
        
        return connector
    
    @pytest.fixture(scope="class")
    def schwab_transformer(self):
        """Create data transformer"""
        return SchwabDataTransformer()
    
    def test_connection_status(self, schwab_connector):
        """Test that we can connect to Schwab API"""
        assert schwab_connector.is_connected(), "Should be connected with valid tokens"
        print("\n✅ Successfully connected to Schwab API")
    
    def test_get_accounts(self, schwab_connector):
        """Test fetching real account data from Schwab"""
        try:
            accounts = schwab_connector.get_accounts()
            
            assert accounts is not None, "Should return accounts list"
            assert len(accounts) > 0, "Should have at least one account"
            
            print(f"\n✅ Retrieved {len(accounts)} account(s) from Schwab")
            
            # Print account details
            for i, account in enumerate(accounts, 1):
                account_info = account.get('securitiesAccount', {})
                account_number = account_info.get('accountNumber', 'Unknown')
                account_type = account_info.get('type', 'Unknown')
                
                balances = account_info.get('currentBalances', {})
                market_value = balances.get('liquidationValue', 0)
                cash = balances.get('cashBalance', 0)
                
                print(f"\nAccount {i}:")
                print(f"  Number: ...{account_number[-4:]}")
                print(f"  Type: {account_type}")
                print(f"  Market Value: ${market_value:,.2f}")
                print(f"  Cash Balance: ${cash:,.2f}")
            
            return accounts
            
        except Exception as e:
            pytest.fail(f"Failed to get accounts: {e}")
    
    def test_get_positions(self, schwab_connector, schwab_transformer):
        """Test fetching and transforming positions"""
        try:
            positions = schwab_connector.get_positions()
            
            assert positions is not None, "Should return positions"
            
            if len(positions) == 0:
                print("\n⚠️  No positions found in accounts")
                return
            
            print(f"\n✅ Retrieved {len(positions)} position(s)")
            
            # Transform to portfolio format
            portfolio_df = schwab_transformer.transform_positions_to_portfolio(positions)
            
            assert not portfolio_df.empty, "Should create portfolio DataFrame"
            
            print(f"\n✅ Transformed to portfolio format:")
            print(portfolio_df[['symbol', 'qty', 'purchase_price', 'account_name']].to_string())
            
        except Exception as e:
            pytest.fail(f"Failed to get positions: {e}")
    
    def test_get_quotes(self, schwab_connector):
        """Test fetching real-time quotes"""
        try:
            # Test with common symbols
            symbols = ['AAPL', 'MSFT', 'SPY']
            quotes = schwab_connector.get_quotes(symbols)
            
            assert quotes is not None, "Should return quotes"
            assert len(quotes) > 0, "Should have at least one quote"
            
            print(f"\n✅ Retrieved quotes for {len(quotes)} symbol(s):")
            
            for symbol, quote in quotes.items():
                last_price = quote.get('lastPrice', 0)
                change = quote.get('netChange', 0)
                change_pct = quote.get('netPercentChange', 0)
                
                print(f"\n{symbol}:")
                print(f"  Last Price: ${last_price:.2f}")
                print(f"  Change: ${change:+.2f} ({change_pct:+.2f}%)")
            
        except Exception as e:
            pytest.fail(f"Failed to get quotes: {e}")
    
    def test_token_refresh(self, schwab_connector):
        """Test that token refresh works"""
        try:
            # Get current token
            current_token = schwab_connector.token_manager.access_token
            
            # Force a refresh by getting valid token
            fresh_token = schwab_connector.token_manager.get_valid_access_token()
            
            assert fresh_token is not None, "Should have valid token"
            print(f"\n✅ Token refresh working (token: {fresh_token[:20]}...)")
            
        except Exception as e:
            pytest.fail(f"Token refresh failed: {e}")
    
    def test_account_details(self, schwab_connector):
        """Test getting detailed account information"""
        try:
            accounts = schwab_connector.get_accounts()
            
            if not accounts:
                pytest.skip("No accounts to test")
            
            # Get first account
            account = accounts[0]
            account_info = account.get('securitiesAccount', {})
            
            # Verify account structure
            assert 'accountNumber' in account_info, "Should have account number"
            assert 'type' in account_info, "Should have account type"
            assert 'currentBalances' in account_info, "Should have balances"
            
            # Check positions if any
            positions = account_info.get('positions', [])
            print(f"\n✅ Account has {len(positions)} position(s)")
            
            if positions:
                print("\nSample position:")
                pos = positions[0]
                instrument = pos.get('instrument', {})
                print(f"  Symbol: {instrument.get('symbol', 'N/A')}")
                print(f"  Quantity: {pos.get('longQuantity', 0)}")
                print(f"  Market Value: ${pos.get('marketValue', 0):,.2f}")
            
        except Exception as e:
            pytest.fail(f"Failed to get account details: {e}")


class TestSchwabLiveDataTransformation:
    """Test data transformation with real Schwab data"""
    
    @pytest.fixture(scope="class")
    def schwab_connector(self):
        """Create Schwab connector"""
        app_key = os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_APP_SECRET")
        callback_url = os.getenv("SCHWAB_CALLBACK_URL", "https://localhost:8080/callback")
        
        connector = SchwabConnector(
            app_key=app_key,
            app_secret=app_secret,
            callback_url=callback_url,
            credential_manager=CredentialManager()
        )
        
        if not connector.load_saved_tokens():
            pytest.skip("No saved tokens found")
        
        return connector
    
    def test_full_sync_workflow(self, schwab_connector):
        """Test complete sync workflow from API to portfolio format"""
        try:
            transformer = SchwabDataTransformer()
            
            # Step 1: Get accounts
            print("\n📥 Step 1: Fetching accounts...")
            accounts = schwab_connector.get_accounts()
            print(f"✅ Retrieved {len(accounts)} account(s)")
            
            # Step 2: Get positions
            print("\n📥 Step 2: Fetching positions...")
            positions = schwab_connector.get_positions()
            print(f"✅ Retrieved {len(positions)} position(s)")
            
            if not positions:
                print("⚠️  No positions to transform")
                return
            
            # Step 3: Transform to portfolio format
            print("\n🔄 Step 3: Transforming to portfolio format...")
            portfolio_df = transformer.transform_positions_to_portfolio(positions)
            print(f"✅ Created portfolio DataFrame with {len(portfolio_df)} row(s)")
            
            # Step 4: Verify data quality
            print("\n✅ Step 4: Verifying data quality...")
            assert not portfolio_df.empty, "Portfolio should not be empty"
            assert 'symbol' in portfolio_df.columns, "Should have symbol column"
            assert 'qty' in portfolio_df.columns, "Should have quantity column"
            assert 'purchase_price' in portfolio_df.columns, "Should have price column"
            
            print("\n✅ Full sync workflow completed successfully!")
            print("\nPortfolio Summary:")
            print(portfolio_df[['symbol', 'name', 'qty', 'purchase_price', 'account_name']].to_string())
            
        except Exception as e:
            pytest.fail(f"Full sync workflow failed: {e}")


def test_credentials_configured():
    """Test that Schwab credentials are configured"""
    app_key = os.getenv("SCHWAB_APP_KEY")
    app_secret = os.getenv("SCHWAB_APP_SECRET")
    
    if not app_key or not app_secret:
        pytest.skip(
            "Schwab credentials not configured. "
            "Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET environment variables."
        )
    
    print(f"\n✅ Schwab credentials configured")
    print(f"   App Key: {app_key[:10]}...")
    print(f"   App Secret: {'*' * 20}")


if __name__ == "__main__":
    # Run live tests
    print("=" * 70)
    print("SCHWAB LIVE INTEGRATION TESTS")
    print("=" * 70)
    print("\nWARNING: These tests make real API calls to Schwab.")
    print("Make sure you have:")
    print("  1. Valid Schwab API credentials")
    print("  2. Completed OAuth authorization")
    print("  3. Saved tokens in credential manager")
    print("=" * 70)
    
    pytest.main([__file__, "-v", "-s", "--tb=short"])

# Made with Bob
