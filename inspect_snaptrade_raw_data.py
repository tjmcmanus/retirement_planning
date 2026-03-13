"""
Inspect SnapTrade Raw Data
===========================
Deep inspection of all fields including raw_type at account and holding levels.
"""

import os
import json
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

def pretty_print_dict(data, indent=0):
    """Recursively print dictionary with indentation."""
    prefix = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{prefix}{key}:")
                pretty_print_dict(value, indent + 1)
            else:
                print(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            print(f"{prefix}[{idx}]:")
            pretty_print_dict(item, indent + 1)
    else:
        print(f"{prefix}{data}")

def inspect_raw_data():
    """Inspect all raw data from SnapTrade API."""
    
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
        
        # Get accounts
        print(f"\n📊 Fetching accounts for user: {user_id}\n")
        accounts = connector.get_accounts(user_id=user_id, user_secret=user_secret)
        
        if not accounts:
            print("❌ No accounts found")
            return
        
        print(f"✅ Found {len(accounts)} account(s)\n")
        print("=" * 100)
        
        # Inspect each account
        for idx, account in enumerate(accounts, 1):
            print(f"\n🏦 ACCOUNT #{idx} - RAW DATA INSPECTION")
            print("=" * 100)
            
            # Convert account to dict
            if hasattr(account, '__dict__'):
                account_dict = connector._convert_to_dict(account)
            elif isinstance(account, dict):
                account_dict = account
            else:
                account_dict = {}
            
            # Print all account fields
            print("\n📋 ALL ACCOUNT FIELDS:")
            print("-" * 100)
            pretty_print_dict(account_dict, indent=0)
            
            # Check specifically for raw_type at account level
            print("\n🔍 SEARCHING FOR 'raw_type' IN ACCOUNT DATA:")
            print("-" * 100)
            raw_type_found = False
            
            def search_raw_type(data, path=""):
                """Recursively search for raw_type field."""
                nonlocal raw_type_found
                if isinstance(data, dict):
                    for key, value in data.items():
                        current_path = f"{path}.{key}" if path else key
                        if 'raw_type' in key.lower():
                            print(f"  ✓ Found at {current_path}: {value}")
                            raw_type_found = True
                        if isinstance(value, (dict, list)):
                            search_raw_type(value, current_path)
                elif isinstance(data, list):
                    for idx, item in enumerate(data):
                        search_raw_type(item, f"{path}[{idx}]")
            
            search_raw_type(account_dict)
            if not raw_type_found:
                print("  ✗ No 'raw_type' field found in account data")
            
            # Get holdings for this account
            print(f"\n\n📈 HOLDINGS FOR ACCOUNT: {account_dict.get('name', 'Unknown')}")
            print("=" * 100)
            
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
            
            print(f"\n✅ Found {len(holdings_list)} holding(s)\n")
            
            # Inspect each holding
            for h_idx, holding in enumerate(holdings_list, 1):
                print(f"\n{'─' * 100}")
                print(f"📦 HOLDING #{h_idx} - RAW DATA INSPECTION")
                print(f"{'─' * 100}")
                
                # Convert to dict
                if hasattr(holding, '__dict__'):
                    holding_dict = connector._convert_to_dict(holding)
                elif isinstance(holding, dict):
                    holding_dict = holding
                else:
                    continue
                
                # Print all holding fields
                print("\n📋 ALL HOLDING FIELDS:")
                print("-" * 100)
                pretty_print_dict(holding_dict, indent=0)
                
                # Search for raw_type in holding
                print("\n🔍 SEARCHING FOR 'raw_type' IN HOLDING DATA:")
                print("-" * 100)
                raw_type_found = False
                search_raw_type(holding_dict)
                if not raw_type_found:
                    print("  ✗ No 'raw_type' field found in holding data")
                
                print()
        
        print("\n" + "=" * 100)
        print("✅ Raw data inspection complete")
        
    except Exception as e:
        logger.error(f"Error inspecting raw data: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    inspect_raw_data()

# Made with Bob
