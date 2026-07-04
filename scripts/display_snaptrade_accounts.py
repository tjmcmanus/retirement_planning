"""
Display SnapTrade Account Details
==================================
Shows account information and holdings with focus on raw_type field.
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

def display_account_details():
    """Display account details from SnapTrade with focus on raw_type."""
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment
    user_id = os.getenv("SNAPTRADE_USER_ID", "default")
    user_secret = os.getenv("SNAPTRADE_USER_SECRET")
    
    if not user_secret:
        print("❌ SNAPTRADE_USER_SECRET not found in environment variables")
        print("Please set SNAPTRADE_USER_SECRET in your .env file")
        return
    
    try:
        # Create connector
        print("🔌 Connecting to SnapTrade...")
        credential_manager = CredentialManager()
        connector = create_snaptrade_connector(credential_manager=credential_manager)
        
        # Get accounts
        print(f"\n📊 Fetching accounts for user: {user_id}")
        accounts = connector.get_accounts(user_id=user_id, user_secret=user_secret)
        
        if not accounts:
            print("❌ No accounts found")
            return
        
        print(f"✅ Found {len(accounts)} account(s)\n")
        print("=" * 80)
        
        # Display each account
        for idx, account in enumerate(accounts, 1):
            print(f"\n🏦 ACCOUNT #{idx}")
            print("-" * 80)
            
            # Convert account to dict if needed
            if hasattr(account, '__dict__'):
                account_dict = connector._convert_to_dict(account)
            elif isinstance(account, dict):
                account_dict = account
            else:
                account_dict = {}
            
            # Display account details
            print(f"Account ID:     {account_dict.get('id', 'N/A')}")
            print(f"Account Name:   {account_dict.get('name', 'N/A')}")
            print(f"Account Number: {account_dict.get('number', 'N/A')}")
            print(f"Account Type:   {account_dict.get('type', 'N/A')}")
            
            # Display institution info
            institution = account_dict.get('institution', {})
            if isinstance(institution, dict):
                print(f"Institution:    {institution.get('name', 'N/A')}")
            
            # Display balance info
            balance = account_dict.get('balance', {})
            if isinstance(balance, dict):
                total = balance.get('total', {})
                if isinstance(total, dict):
                    amount = total.get('amount', 'N/A')
                    currency = total.get('currency', 'USD')
                    print(f"Balance:        {currency} {amount}")
            
            # Get holdings for this account
            print(f"\n📈 Holdings for {account_dict.get('name', 'Account')}:")
            print("-" * 80)
            
            holdings = connector.client.account_information.get_user_account_positions(
                user_id=user_id,
                user_secret=user_secret,
                account_id=account_dict.get('id')
            )
            
            # Extract holdings list
            holdings_list = []
            if hasattr(holdings, 'body'):
                holdings_list = holdings.body if isinstance(holdings.body, list) else []
            elif isinstance(holdings, list):
                holdings_list = holdings
            
            if not holdings_list:
                print("  No holdings found")
                continue
            
            print(f"  Found {len(holdings_list)} holding(s)\n")
            
            # Display each holding with focus on raw_type
            for h_idx, holding in enumerate(holdings_list, 1):
                # Convert to dict
                if hasattr(holding, '__dict__'):
                    holding_dict = connector._convert_to_dict(holding)
                elif isinstance(holding, dict):
                    holding_dict = holding
                else:
                    continue
                
                print(f"  [{h_idx}] Holding Details:")
                print(f"      Units/Qty:        {holding_dict.get('units', 'N/A')}")
                print(f"      Price:            ${holding_dict.get('price', 'N/A')}")
                print(f"      Cost Basis:       ${holding_dict.get('average_purchase_price', 'N/A')}")
                
                # Extract symbol information
                symbol_wrapper = holding_dict.get('symbol', {})
                if isinstance(symbol_wrapper, dict):
                    # Check for nested symbol
                    if 'symbol' in symbol_wrapper and isinstance(symbol_wrapper['symbol'], dict):
                        symbol_data = symbol_wrapper['symbol']
                    else:
                        symbol_data = symbol_wrapper
                    
                    print(f"      Symbol:           {symbol_data.get('raw_symbol', 'N/A')}")
                    print(f"      Description:      {symbol_data.get('description', 'N/A')}")
                    
                    # ⭐ FOCUS: Display raw_type information
                    symbol_type = symbol_data.get('type', {})
                    if isinstance(symbol_type, dict):
                        print(f"      🎯 RAW_TYPE:      {symbol_type.get('raw_type', 'N/A')}")
                        print(f"      Type Code:        {symbol_type.get('code', 'N/A')}")
                        print(f"      Type Description: {symbol_type.get('description', 'N/A')}")
                        print(f"      Is Supported:     {symbol_type.get('is_supported', 'N/A')}")
                    else:
                        print(f"      🎯 RAW_TYPE:      Not available (type field not a dict)")
                else:
                    print(f"      Symbol:           Not available")
                    print(f"      🎯 RAW_TYPE:      Not available")
                
                print()
        
        print("=" * 80)
        print("✅ Account details displayed successfully")
        
    except Exception as e:
        logger.error(f"Error displaying account details: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    display_account_details()

# Made with Bob
