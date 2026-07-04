"""
Test SnapTrade raw_type Integration
====================================
Verify that raw_type from account data is used for account_type mapping.
"""

import os
import logging
from dotenv import load_dotenv
from components.snaptrade_connector import create_snaptrade_connector
from components.credential_manager import CredentialManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_raw_type_mapping():
    """Test that raw_type is correctly used for account_type mapping."""
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment
    user_id = os.getenv("SNAPTRADE_USER_ID", "default")
    user_secret = os.getenv("SNAPTRADE_USER_SECRET")
    
    if not user_secret:
        print("❌ SNAPTRADE_USER_SECRET not found in environment variables")
        return
    
    try:
        # Create connector
        print("🔌 Connecting to SnapTrade...")
        credential_manager = CredentialManager()
        connector = create_snaptrade_connector(credential_manager=credential_manager)
        
        # Get accounts to see raw_type
        print(f"\n📊 Fetching accounts for user: {user_id}")
        accounts = connector.get_accounts(user_id=user_id, user_secret=user_secret)
        
        print(f"\n✅ Found {len(accounts)} account(s)\n")
        print("=" * 100)
        
        for idx, account in enumerate(accounts, 1):
            # Convert to dict
            if hasattr(account, '__dict__'):
                account_dict = connector._convert_to_dict(account)
            elif isinstance(account, dict):
                account_dict = account
            else:
                continue
            
            print(f"\n🏦 ACCOUNT #{idx}: {account_dict.get('name', 'Unknown')}")
            print("-" * 100)
            print(f"Account raw_type:     {account_dict.get('raw_type', 'N/A')}")
            print(f"Account type (old):   {account_dict.get('type', 'N/A')}")
            
            # Map the raw_type
            raw_type = account_dict.get('raw_type', '')
            mapped_type = connector._map_account_type(raw_type)
            print(f"Mapped account_type:  {mapped_type}")
        
        # Now test the holdings sync
        print("\n\n" + "=" * 100)
        print("📈 TESTING HOLDINGS SYNC WITH raw_type")
        print("=" * 100)
        
        holdings = connector.get_holdings(user_id=user_id, user_secret=user_secret)
        
        print(f"\n✅ Retrieved {len(holdings)} holdings\n")
        
        # Check first few holdings to verify raw_type is included
        for idx, holding in enumerate(holdings[:3], 1):
            print(f"\n[{idx}] Holding: {holding.get('symbol', {}).get('symbol', {}).get('raw_symbol', 'N/A')}")
            print(f"    Account Name:     {holding.get('account_name', 'N/A')}")
            print(f"    Account raw_type: {holding.get('account_raw_type', 'N/A')}")
            print(f"    Account type:     {holding.get('account_type', 'N/A')}")
        
        # Now test the full sync to portfolio format
        print("\n\n" + "=" * 100)
        print("📊 TESTING PORTFOLIO SYNC WITH raw_type")
        print("=" * 100)
        
        from datetime import datetime
        now = datetime.now()
        portfolio_df = connector.sync_holdings(user_id=user_id, month=now.month, year=now.year)
        
        if len(portfolio_df) > 0:
            print(f"\n✅ Synced {len(portfolio_df)} holdings to portfolio format\n")
            
            # Show unique account types
            unique_types = portfolio_df['account_type'].unique()
            print(f"Unique account_type values: {list(unique_types)}")
            
            # Show sample rows
            print("\n📋 Sample Portfolio Rows:")
            print("-" * 100)
            for idx, row in portfolio_df.head(3).iterrows():
                print(f"\n[{idx}] {row['symbol']} - {row['name']}")
                print(f"    Account:      {row['account_name']}")
                print(f"    Account Type: {row['account_type']}")
                print(f"    Quantity:     {row['qty']}")
        else:
            print("❌ No holdings synced")
        
        print("\n" + "=" * 100)
        print("✅ Test complete!")
        
    except Exception as e:
        logger.error(f"Error testing raw_type mapping: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    test_raw_type_mapping()

# Made with Bob
