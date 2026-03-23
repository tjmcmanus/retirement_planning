"""
components/snaptrade_connector.py
==================================
SnapTrade API integration for brokerage account connections.

Handles OAuth flow, account syncing, and data transformation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

try:
    from snaptrade_client import SnapTrade  # type: ignore
    SNAPTRADE_AVAILABLE = True
except ImportError:
    SNAPTRADE_AVAILABLE = False
    SnapTrade = None  # type: ignore
    logging.warning("snaptrade-python not installed. Run: pip install snaptrade-python")

from components.credential_manager import CredentialManager


logger = logging.getLogger(__name__)


class SnapTradeConnector:
    """
    Manages SnapTrade API connections and data synchronization.
    
    Features:
    - OAuth authentication flow
    - Holdings synchronization
    - Account management
    - Data transformation to portfolio format
    """
    
    def __init__(self, client_id: str, consumer_key: str, credential_manager: CredentialManager):
        """
        Initialize SnapTrade connector.
        
        Args:
            client_id: SnapTrade client ID
            consumer_key: SnapTrade consumer key
            credential_manager: Credential manager for secure storage
        """
        if not SNAPTRADE_AVAILABLE or SnapTrade is None:
            raise ImportError("snaptrade-python library not installed")
        
        self.client_id = client_id
        self.consumer_key = consumer_key
        self.credential_manager = credential_manager
        self.client = SnapTrade(  # type: ignore
            consumer_key=consumer_key,
            client_id=client_id
        )
    
    def delete_user(self, user_id: str = "default") -> bool:
        """
        Delete a registered user (useful for re-registration with personal keys).
        
        Args:
            user_id: User identifier
        
        Returns:
            True if deleted successfully
        """
        try:
            self.client.authentication.delete_snap_trade_user(user_id=user_id)
            logger.info(f"Deleted user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            return False
    
    def get_auth_link(self, user_id: str = "default", redirect_uri: Optional[str] = None, force_reregister: bool = False) -> dict:
        """
        Generate OAuth authentication link for user.
        
        Args:
            user_id: User identifier
            redirect_uri: Where to redirect after auth (optional)
            force_reregister: Force delete and re-register user
        
        Returns:
            Dictionary with 'auth_link' and 'user_id'
        """
        try:
            user_secret = None
            
            # Check if user credentials are in environment variables
            import os
            env_user_id = os.getenv("SNAPTRADE_USER_ID")
            env_user_secret = os.getenv("SNAPTRADE_USER_SECRET")
            
            if env_user_id and env_user_secret and not force_reregister:
                logger.info(f"Using userID and userSecret from environment variables")
                user_id = env_user_id
                user_secret = env_user_secret
                
                # Generate login link directly
                auth_link = self.client.authentication.login_snap_trade_user(
                    user_id=user_id,
                    user_secret=user_secret,
                    custom_redirect=redirect_uri
                )
                
                logger.info(f"Generated auth link for user {user_id} from env vars")
                
                # Extract redirectURI from ApiResponseFor200 object
                redirect_uri_value = None
                if hasattr(auth_link, 'body'):
                    body = auth_link.body
                    if isinstance(body, dict):
                        redirect_uri_value = body.get('redirectURI')
                    elif hasattr(body, 'get'):
                        redirect_uri_value = body.get('redirectURI')
                    elif hasattr(body, 'redirectURI'):
                        redirect_uri_value = body.redirectURI
                elif isinstance(auth_link, dict):
                    redirect_uri_value = auth_link.get('redirectURI')
                elif hasattr(auth_link, 'redirectURI'):
                    redirect_uri_value = auth_link.redirectURI
                
                return {
                    'auth_link': redirect_uri_value,
                    'user_id': user_id,
                    'user_secret': user_secret
                }
            
            # If force_reregister, delete existing user first
            if force_reregister:
                logger.info(f"Force re-registering user {user_id}")
                self.delete_user(user_id)
            
            # Try to register user (will fail if already registered with personal keys)
            try:
                response = self.client.authentication.register_snap_trade_user(
                    user_id=user_id
                )
                # Extract userSecret from response - try multiple ways
                if hasattr(response, 'body'):
                    body = response.body
                    if isinstance(body, dict):
                        user_secret = body.get('userSecret') or body.get('user_secret')
                    elif hasattr(body, 'get'):
                        user_secret = body.get('userSecret') or body.get('user_secret')
                    elif hasattr(body, 'userSecret'):
                        user_secret = body.userSecret
                    elif hasattr(body, 'user_secret'):
                        user_secret = body.user_secret
                elif isinstance(response, dict):
                    user_secret = response.get('userSecret') or response.get('user_secret')
                elif hasattr(response, 'userSecret'):
                    user_secret = response.userSecret
                elif hasattr(response, 'user_secret'):
                    user_secret = response.user_secret
                
                logger.info(f"Registered new user {user_id}, userSecret: {'Found' if user_secret else 'NOT FOUND'}")
                
                # Store userSecret in credential manager for future use
                if user_secret:
                    try:
                        self.credential_manager.store_connection(
                            brokerage_name="SnapTrade",
                            account_id=user_id,
                            access_token=user_secret,  # Store userSecret as token
                            user_id=user_id
                        )
                        logger.info(f"Stored userSecret for {user_id}")
                    except Exception as store_error:
                        logger.warning(f"Could not store userSecret: {store_error}")
            except Exception as reg_error:
                # If user already registered (error 1012), that's okay
                if "1012" in str(reg_error) or "already" in str(reg_error).lower():
                    logger.info(f"User {user_id} already registered, attempting to retrieve userSecret")
                    
                    # First, try to get from credential manager (if we stored it before)
                    try:
                        connections = self.credential_manager.list_connections(user_id=user_id)
                        for conn in connections:
                            if conn['brokerage_name'] == "SnapTrade" and conn['account_id'] == user_id:
                                conn_details = self.credential_manager.get_connection(conn['id'])
                                if conn_details:
                                    user_secret = conn_details['access_token']  # We stored userSecret as token
                                    logger.info(f"Retrieved userSecret from credential manager")
                                    break
                    except Exception as cred_error:
                        logger.warning(f"Could not retrieve from credential manager: {cred_error}")
                    
                    # If not found, try to list users from API
                    if not user_secret:
                        try:
                            users = self.client.authentication.list_snap_trade_users()
                            logger.info(f"Retrieved {len(users) if users else 0} users from API")
                            if users and len(users) > 0:
                                # Try different ways to access userSecret
                                first_user = users[0]
                                if hasattr(first_user, 'userSecret'):
                                    user_secret = first_user.userSecret
                                elif hasattr(first_user, 'user_secret'):
                                    user_secret = first_user.user_secret
                                elif isinstance(first_user, dict):
                                    user_secret = first_user.get('userSecret') or first_user.get('user_secret')
                                logger.info(f"Retrieved userSecret from API: {'Yes' if user_secret else 'No'}")
                        except Exception as list_error:
                            logger.error(f"Failed to list users from API: {list_error}")
                else:
                    # Other registration errors should be raised
                    raise
            
            if not user_secret:
                raise ValueError(
                    "Could not obtain userSecret. For personal API keys, you may need to "
                    "delete the existing user and re-register, or contact SnapTrade support."
                )
            
            # Generate login link with userSecret
            auth_link_response = self.client.authentication.login_snap_trade_user(
                user_id=user_id,
                user_secret=user_secret,
                custom_redirect=redirect_uri
            )
            
            # Extract redirectURI from response
            redirect_uri_value = None
            if hasattr(auth_link_response, 'body'):
                body = auth_link_response.body
                if isinstance(body, dict):
                    redirect_uri_value = body.get('redirectURI')
                elif hasattr(body, 'get'):
                    redirect_uri_value = body.get('redirectURI')
                elif hasattr(body, 'redirectURI'):
                    redirect_uri_value = body.redirectURI
            elif isinstance(auth_link_response, dict):
                redirect_uri_value = auth_link_response.get('redirectURI')
            elif hasattr(auth_link_response, 'redirectURI'):
                redirect_uri_value = auth_link_response.redirectURI
            
            logger.info(f"Generated auth link for user {user_id}")
            return {
                'auth_link': redirect_uri_value,
                'user_id': user_id,
                'user_secret': user_secret
            }
        except Exception as e:
            logger.error(f"Failed to generate auth link: {e}", exc_info=True)
            raise
    
    def list_brokerage_authorizations(self, user_id: str = "default") -> list[dict]:
        """
        List all brokerage authorizations for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            List of authorization dictionaries
        """
        try:
            authorizations = self.client.authentication.list_snap_trade_users()
            
            user_auths = [
                auth for auth in authorizations 
                if auth.get('userId') == user_id
            ]
            
            return user_auths
        except Exception as e:
            logger.error(f"Failed to list authorizations: {e}")
            return []
    
    def get_accounts(self, user_id: str = "default", user_secret: Optional[str] = None) -> list[dict]:
        """
        Get all brokerage accounts for a user.
        
        Args:
            user_id: User identifier
            user_secret: User secret (from env if not provided)
        
        Returns:
            List of account dictionaries
        """
        try:
            # Get userSecret if not provided
            if not user_secret:
                import os
                user_secret = os.getenv("SNAPTRADE_USER_SECRET")
            
            if not user_secret:
                raise ValueError("userSecret is required but not provided")
            
            accounts = self.client.account_information.list_user_accounts(
                user_id=user_id,
                user_secret=user_secret
            )
            
            # Extract account list from ApiResponseFor200 object
            account_list = []
            if hasattr(accounts, 'body'):
                account_list = accounts.body if isinstance(accounts.body, list) else []
            elif isinstance(accounts, list):
                account_list = accounts
            
            logger.info(f"Retrieved {len(account_list)} accounts for user {user_id}")
            return account_list
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            return []
    
    def get_holdings(self, user_id: str = "default", user_secret: Optional[str] = None, account_id: Optional[str] = None) -> list[dict]:
        """
        Get holdings for user's accounts.
        
        Args:
            user_id: User identifier
            user_secret: User secret (from env if not provided)
            account_id: Specific account ID (optional, gets all if not provided)
        
        Returns:
            List of holding dictionaries
        """
        try:
            # Get userSecret if not provided
            if not user_secret:
                import os
                user_secret = os.getenv("SNAPTRADE_USER_SECRET")
            
            if not user_secret:
                raise ValueError("userSecret is required but not provided")
            
            if account_id:
                # Get holdings for specific account
                holdings = self.client.account_information.get_user_account_positions(
                    user_id=user_id,
                    user_secret=user_secret,
                    account_id=account_id
                )
            else:
                # Get holdings for all accounts
                accounts = self.get_accounts(user_id, user_secret)
                holdings = []
                for account in accounts:
                    acc_holdings = self.client.account_information.get_user_account_positions(
                        user_id=user_id,
                        user_secret=user_secret,
                        account_id=account['id']
                    )
                    # Extract holdings from ApiResponseFor200 object
                    holdings_list = []
                    if hasattr(acc_holdings, 'body'):
                        holdings_list = acc_holdings.body if isinstance(acc_holdings.body, list) else []
                    elif isinstance(acc_holdings, list):
                        holdings_list = acc_holdings
                    
                    # Add account info to each holding and convert to dict
                    for holding in holdings_list:
                        # Convert holding to dict if it's an object
                        holding_dict: dict = {}
                        if hasattr(holding, '__dict__'):
                            converted = self._convert_to_dict(holding)
                            if isinstance(converted, dict):
                                holding_dict = converted
                        elif isinstance(holding, dict):
                            holding_dict = holding
                        else:
                            continue
                        
                        # Add account metadata - use raw_type for accurate account type
                        holding_dict['account_name'] = account.get('name', 'Unknown')
                        holding_dict['account_raw_type'] = account.get('raw_type', '')  # Use raw_type from account
                        holding_dict['account_type'] = account.get('type', 'Unknown')  # Keep old field for compatibility
                        holding_dict['account_number'] = account.get('number', '')
                        holdings.append(holding_dict)
            
            logger.info(f"Retrieved {len(holdings)} holdings for user {user_id}")
            return holdings
            
        except Exception as e:
            logger.error(f"Failed to get holdings: {e}")
            return []
    
    def get_transactions(
        self,
        user_id: str,
        user_secret: str,
        account_id: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        Fetch transaction history from brokerage account.
        
        Args:
            user_id: User identifier
            user_secret: User secret for authentication
            account_id: Account ID to fetch transactions from
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of transaction dictionaries
        """
        try:
            logger.info(f"Fetching transactions for account {account_id} from {start_date} to {end_date}")
            
            # Get activities (transactions) from SnapTrade
            activities = self.client.transactions.get_activities(
                user_id=user_id,
                user_secret=user_secret,
                account_id=account_id,
                start_date=start_date,
                end_date=end_date
            )
            
            # Extract activities from ApiResponseFor200 object
            activities_list = []
            if hasattr(activities, 'body'):
                activities_list = activities.body if isinstance(activities.body, list) else []
            elif isinstance(activities, list):
                activities_list = activities
            
            # Convert activities to dictionaries
            transactions = []
            for activity in activities_list:
                if hasattr(activity, '__dict__'):
                    converted = self._convert_to_dict(activity)
                    if isinstance(converted, dict):
                        transactions.append(converted)
                elif isinstance(activity, dict):
                    transactions.append(activity)
            
            logger.info(f"Retrieved {len(transactions)} transactions")
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to fetch transactions: {e}", exc_info=True)
            return []
            logger.info(f"Retrieved {len(holdings)} holdings for user {user_id}")
            return holdings
        except Exception as e:
            logger.error(f"Failed to get holdings: {e}")
            return []
    
    def sync_holdings(
        self, 
        user_id: str = "default",
        month: Optional[int] = None,
        year: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Sync holdings from SnapTrade and transform to portfolio format.
        
        Args:
            user_id: User identifier
            month: Target month (default: current)
            year: Target year (default: current)
        
        Returns:
            DataFrame in portfolio_data_truth.csv format
        """
        # Get current month/year if not provided
        now = datetime.now()
        month = month or now.month
        year = year or now.year
        
        # Fetch holdings from SnapTrade
        holdings = self.get_holdings(user_id)
        
        if not holdings:
            logger.warning("No holdings found to sync")
            return pd.DataFrame()
        
        # Transform to portfolio format
        portfolio_data = self._transform_holdings_to_portfolio(
            holdings, month, year
        )
        
        logger.info(f"Synced {len(portfolio_data)} holdings for {month}/{year}")
        return portfolio_data
    
    def _convert_to_dict(self, obj):
        """Convert an object to a dictionary recursively."""
        if isinstance(obj, dict):
            return {k: self._convert_to_dict(v) for k, v in obj.items()}
        elif hasattr(obj, '__dict__'):
            return {k: self._convert_to_dict(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
        elif isinstance(obj, list):
            return [self._convert_to_dict(item) for item in obj]
        else:
            return obj
    
    def _transform_holdings_to_portfolio(
        self,
        holdings: list[dict],
        month: int,
        year: int
    ) -> pd.DataFrame:
        """
        Transform SnapTrade holdings to portfolio_data_truth.csv format.
        
        SnapTrade API returns holdings with nested symbol data:
        Example holding format:
        - symbol: dict with raw_symbol, description, type
        - units: quantity held
        - price: current price
        - account_name: from our enrichment
        - account_type: from our enrichment
        
        Portfolio format columns:
        month, year, account_name, account_type, owner, symbol, name,
        sector, qty, purchase_price, purchase_date
        """
        rows = []
        
        for idx, holding_item in enumerate(holdings):
            # Log the raw holding object for debugging
            logger.info(f"=== Processing holding {idx + 1} ===")
            logger.info(f"Raw holding type: {type(holding_item)}")
            logger.info(f"Raw holding: {holding_item}")
            
            # Convert holding to dict if needed
            holding: dict = {}
            if hasattr(holding_item, '__dict__'):
                converted = self._convert_to_dict(holding_item)
                if isinstance(converted, dict):
                    holding = converted
                    logger.info(f"Converted holding to dict: {holding}")
            elif isinstance(holding_item, dict):
                holding = holding_item
                logger.info(f"Holding is already dict: {holding}")
            else:
                logger.warning(f"Skipping holding - unknown type: {type(holding_item)}")
                continue
            
            # Extract symbol data - it's nested: holding['symbol']['symbol']
            symbol_wrapper = holding.get('symbol', {})
            logger.info(f"Symbol wrapper type: {type(symbol_wrapper)}")
            logger.info(f"Symbol wrapper: {symbol_wrapper}")
            
            # Get the actual symbol data (nested one level deeper)
            symbol_data = {}
            if isinstance(symbol_wrapper, dict):
                # Check if there's a nested 'symbol' key
                if 'symbol' in symbol_wrapper and isinstance(symbol_wrapper['symbol'], dict):
                    symbol_data = symbol_wrapper['symbol']
                    logger.info(f"Found nested symbol data: {symbol_data}")
                else:
                    # No nesting, use wrapper directly
                    symbol_data = symbol_wrapper
            
            # Extract raw_symbol and description from the symbol data
            raw_symbol = ''
            description = ''
            symbol_type = {}
            
            if symbol_data:
                raw_symbol = symbol_data.get('raw_symbol') or symbol_data.get('symbol', '')
                description = symbol_data.get('description', '')
                symbol_type = symbol_data.get('type', {})
            
            logger.info(f"Extracted raw_symbol: '{raw_symbol}'")
            logger.info(f"Extracted description: '{description}'")
            logger.info(f"Extracted symbol_type: {symbol_type}")
            
            if not raw_symbol:
                logger.warning(f"Skipping holding with no symbol: {holding}")
                continue
            
            # Ensure raw_symbol is a string
            raw_symbol = str(raw_symbol) if raw_symbol else ''
            
            # Parse fund name from description
            # Format: "Company Name. - Fund Name" -> extract "Fund Name"
            fund_name = raw_symbol  # Default to symbol
            if description and ' - ' in description:
                parts = description.split(' - ', 1)
                if len(parts) == 2:
                    fund_name = parts[1].strip()
            elif description:
                fund_name = str(description)
            
            logger.info(f"Final parsed - symbol: '{raw_symbol}', name: '{fund_name}'")
            
            # Get quantity
            quantity = holding.get('units', 0)
            if quantity is None:
                quantity = 0
            if quantity <= 0:
                continue
            
            # Get prices
            current_price = holding.get('price', 0)
            if current_price is None:
                current_price = 0
            
            cost_basis = holding.get('average_purchase_price')
            if cost_basis is None:
                cost_basis = current_price if current_price else 0
            
            # Get account info
            account_name = holding.get('account_name', 'Unknown')
            account_number = holding.get('account_number', '')
            
            # Map account type from SnapTrade to portfolio format
            # Use raw_type from account data (e.g., "401K") for accurate mapping
            account_raw_type = holding.get('account_raw_type', '')
            
            # If raw_type is available, use it; otherwise fall back to old logic
            if account_raw_type:
                account_type = self._map_account_type(account_raw_type)
            else:
                # Fallback: Check account metadata for type info
                account_type_raw = holding.get('account_type', '').lower()
                account_meta = holding.get('account', {})
                if hasattr(account_meta, '__dict__'):
                    account_meta = self._convert_to_dict(account_meta)
                
                # Try to get more specific account type from metadata
                if isinstance(account_meta, dict):
                    meta_type = account_meta.get('type', '').lower()
                    if meta_type:
                        account_type_raw = meta_type
                account_type = self._map_account_type(account_type_raw)
            
            # Look up account configuration for owner and type override
            try:
                from components.schwab_data_transformer import get_account_config
                account_config = get_account_config(str(account_name))
                # Use config values if available, otherwise use detected values
                account_type = account_config.get('account_type', account_type)
                owner = account_config.get('owner', 'Joint')
            except Exception as e:
                logger.warning(f"Could not load account config for {account_name}: {e}")
                owner = 'Joint'  # Default fallback
            
            # Determine sector based on symbol type
            sector = ''
            if isinstance(symbol_type, dict):
                type_code = symbol_type.get('code', '').lower()
                if type_code in ['oef', 'cef', 'etf']:
                    sector = 'MF:Unknown'  # Mutual fund/ETF - user can specify category
            
            # Create row with explicit string conversions and None handling
            row = {
                'month': int(month),
                'year': int(year),
                'account_name': str(account_name) if account_name else 'Unknown',
                'account_type': str(account_type) if account_type else 'Brokerage',
                'owner': str(owner) if owner else 'Joint',  # From account config lookup
                'symbol': str(raw_symbol) if raw_symbol else '',
                'name': str(fund_name) if fund_name else '',
                'sector': str(sector) if sector else '',
                'qty': float(quantity) if quantity is not None else 0.0,
                'purchase_price': float(cost_basis) if cost_basis is not None else 0.0,
                'purchase_date': ''  # SnapTrade doesn't provide this
            }
            
            logger.debug(f"Created row: symbol={row['symbol']}, name={row['name']}")
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Ensure correct column order
        expected_columns = [
            'month', 'year', 'account_name', 'account_type', 'owner',
            'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date'
        ]
        
        result: pd.DataFrame = df[expected_columns]  # type: ignore
        
        # Ensure symbol and name are strings (not objects)
        result['symbol'] = result['symbol'].astype(str)
        result['name'] = result['name'].astype(str)
        
        logger.info(f"Transformed {len(result)} holdings to portfolio format")
        logger.debug(f"Sample row: {result.iloc[0].to_dict() if len(result) > 0 else 'No rows'}")
        
        return result
    
    def merge_holdings_to_portfolio(
        self,
        synced_holdings: pd.DataFrame,
        portfolio_file: str = 'portfolio_data_truth.csv'
    ) -> pd.DataFrame:
        """
        Merge synced holdings with existing portfolio data.
        
        Logic:
        - If month/year/account_name/symbol match exactly: keep existing (no update)
        - If month/year/account_name/symbol match but qty differs: update that row
        - If no match for month/year/account_name/symbol: add new row
        
        Args:
            synced_holdings: DataFrame from sync_holdings()
            portfolio_file: Path to portfolio CSV file
        
        Returns:
            Updated portfolio DataFrame
        """
        import os
        
        # Load existing portfolio data
        if os.path.exists(portfolio_file):
            existing_df = pd.read_csv(portfolio_file)
        else:
            logger.warning(f"Portfolio file {portfolio_file} not found, creating new")
            return synced_holdings
        
        # Create merge key for matching
        merge_cols = ['month', 'year', 'account_name', 'symbol']
        
        # Process each synced holding
        updated_rows = []
        logger.info(f"Starting merge: {len(synced_holdings)} synced holdings, {len(existing_df)} existing holdings")
        
        for idx, synced_row in synced_holdings.iterrows():
            # Find matching row in existing data
            mask = (
                (existing_df['month'] == synced_row['month']) &
                (existing_df['year'] == synced_row['year']) &
                (existing_df['account_name'] == synced_row['account_name']) &
                (existing_df['symbol'] == synced_row['symbol'])
            )
            
            matching_rows = existing_df[mask]
            
            logger.info(f"Processing synced row {idx}: symbol={synced_row['symbol']}, account={synced_row['account_name']}, month={synced_row['month']}/{synced_row['year']}, matches={len(matching_rows)}")
            
            if len(matching_rows) == 0:
                # No match - add new row
                logger.info(f"✓ Adding new holding: {synced_row['symbol']} in {synced_row['account_name']} for {synced_row['month']}/{synced_row['year']}")
                updated_rows.append(synced_row.to_dict())
            elif len(matching_rows) == 1:
                existing_row = matching_rows.iloc[0]
                
                # Check if we should update purchase_date
                synced_has_date = pd.notna(synced_row.get('purchase_date')) and synced_row.get('purchase_date') != ''
                existing_has_date = pd.notna(existing_row.get('purchase_date')) and existing_row.get('purchase_date') != ''
                should_update_date = synced_has_date and not existing_has_date
                
                # Check if quantity differs
                qty_differs = abs(existing_row['qty'] - synced_row['qty']) > 0.01
                
                if qty_differs:
                    logger.info(f"✓ Updating {synced_row['symbol']}: qty {existing_row['qty']} -> {synced_row['qty']}")
                    updated_rows.append(synced_row.to_dict())
                elif should_update_date:
                    # Quantity same but we have a new purchase date - merge them
                    logger.info(f"✓ Enriching {synced_row['symbol']} with purchase_date: {synced_row['purchase_date']}")
                    merged_row = existing_row.to_dict()
                    merged_row['purchase_date'] = synced_row['purchase_date']
                    updated_rows.append(merged_row)
                else:
                    # No changes needed - keep existing
                    logger.info(f"= Keeping existing {synced_row['symbol']}: qty unchanged at {existing_row['qty']}")
                    updated_rows.append(existing_row.to_dict())
                
                # Remove from existing_df to avoid duplicates
                existing_df = existing_df[~mask]
            else:
                # Multiple matches - log warning and use first
                logger.warning(f"⚠ Multiple matches found for {synced_row['symbol']}, using synced version")
                updated_rows.append(synced_row.to_dict())
                existing_df = existing_df[~mask]
        
        # Add remaining rows from existing_df (holdings not in synced data)
        logger.info(f"Adding {len(existing_df)} remaining holdings from existing portfolio")
        if len(existing_df) > 0:
            updated_rows.extend([row.to_dict() for _, row in existing_df.iterrows()])
        
        # Create final DataFrame
        logger.info(f"Creating final DataFrame with {len(updated_rows)} total rows")
        result_df = pd.DataFrame(updated_rows)
        
        # Fill any NaN owner values with 'Joint' as default
        if 'owner' in result_df.columns:
            result_df['owner'] = result_df['owner'].fillna('Joint')
            logger.info(f"Filled NaN owner values with 'Joint'")
        
        # Ensure correct column order
        expected_columns = [
            'month', 'year', 'account_name', 'account_type', 'owner',
            'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date'
        ]
        
        # Reorder columns if all expected columns exist
        if all(col in result_df.columns for col in expected_columns):
            result_df = result_df[expected_columns]
        
        # Normalize purchase_date to YYYY-MM-DD format (no time component)
        if 'purchase_date' in result_df.columns:
            # Convert to datetime first, then to date-only string
            result_df['purchase_date'] = pd.to_datetime(result_df['purchase_date'], errors='coerce')
            # Convert to string in YYYY-MM-DD format, handling NaT as empty string
            result_df['purchase_date'] = result_df['purchase_date'].apply(
                lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else ''
            )
            logger.info("Normalized purchase_date to YYYY-MM-DD format")
        
        # Sort by year, month, account_name, symbol
        result_df = result_df.sort_values(['year', 'month', 'account_name', 'symbol'])
        
        logger.info(f"Merged portfolio: {len(result_df)} total holdings")
        return result_df
    
    def _map_account_type(self, snaptrade_type: str) -> str:
        """
        Map SnapTrade account type to portfolio account type.
        
        SnapTrade types: taxable, ira, roth_ira, 401k, roth_401k, etc.
        Portfolio types: Brokerage, Traditional, Roth, 401k, etc.
        """
        type_mapping = {
            'taxable': 'Brokerage',
            'margin': 'Brokerage',
            'cash': 'Brokerage',
            'brokerage': 'Brokerage',
            'ira': 'Traditional',
            'traditional_ira': 'Traditional',
            'traditional': 'Traditional',
            'roth_ira': 'Roth',
            'roth': 'Roth',
            '401k': 'Traditional',  # Default 401k to Traditional
            'traditional_401k': 'Traditional',
            'roth_401k': 'Roth',  # Roth 401k
            '403b': 'Traditional',
            'roth_403b': 'Roth',
            'sep_ira': 'Traditional',
            'simple_ira': 'Traditional',
        }
        
        return type_mapping.get(snaptrade_type.lower(), 'Brokerage')
    
    def disconnect_authorization(self, user_id: str = "default") -> bool:
        """
        Disconnect SnapTrade authorization for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            True if disconnected successfully
        """
        try:
            self.client.authentication.delete_snap_trade_user(
                user_id=user_id
            )
            logger.info(f"Disconnected authorization for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect authorization: {e}")
            return False
    
    def get_connection_status(self, user_id: str = "default", user_secret: Optional[str] = None) -> dict:
        """
        Get connection status for a user.
        
        Args:
            user_id: User identifier
            user_secret: User secret (from env if not provided)
        
        Returns:
            Dictionary with connection status information
        """
        try:
            accounts = self.get_accounts(user_id, user_secret)
            
            return {
                'connected': len(accounts) > 0,
                'account_count': len(accounts),
                'accounts': [
                    {
                        'id': acc.get('id'),
                        'name': acc.get('name'),
                        'type': acc.get('type'),
                        'institution': acc.get('institution', {}).get('name', 'Unknown')
                    }
                    for acc in accounts
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get connection status: {e}")
            return {
                'connected': False,
                'account_count': 0,
                'accounts': [],
                'error': str(e)
            }
    
    def get_transactions(
        self,
        user_id: str = "default",
        user_secret: Optional[str] = None,
        account_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> list[dict]:
        """
        Get transaction history for user's accounts.
        
        Args:
            user_id: User identifier
            user_secret: User secret (from env if not provided)
            account_id: Specific account ID (optional, gets all if not provided)
            start_date: Start date in YYYY-MM-DD format (default: 1 year ago)
            end_date: End date in YYYY-MM-DD format (default: today)
        
        Returns:
            List of transaction dictionaries
        """
        try:
            # Get userSecret if not provided
            if not user_secret:
                import os
                user_secret = os.getenv("SNAPTRADE_USER_SECRET")
            
            if not user_secret:
                raise ValueError("userSecret is required but not provided")
            
            # Set default date range (1 year)
            from datetime import timedelta
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")
            if not start_date:
                start = datetime.now() - timedelta(days=365)
                start_date = start.strftime("%Y-%m-%d")
            
            logger.info(f"Fetching transactions from {start_date} to {end_date}")
            
            # Get accounts if account_id not specified
            accounts_to_process = []
            if account_id:
                accounts_to_process = [{'id': account_id}]
            else:
                accounts = self.get_accounts(user_id, user_secret)
                accounts_to_process = accounts
            
            all_transactions = []
            
            for account in accounts_to_process:
                acc_id = account.get('id')
                if not acc_id:
                    continue
                
                try:
                    # Fetch activities (transactions) from SnapTrade
                    activities = self.client.account_information.get_account_activities(
                        user_id=user_id,
                        user_secret=user_secret,
                        account_id=acc_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    # Extract activities list
                    activities_list = []
                    if hasattr(activities, 'body'):
                        activities_list = activities.body if isinstance(activities.body, list) else []
                    elif isinstance(activities, list):
                        activities_list = activities
                    
                    logger.info(f"Retrieved {len(activities_list)} transactions for account {acc_id}")
                    
                    # Transform each activity
                    for activity in activities_list:
                        # Convert to dict
                        if hasattr(activity, '__dict__'):
                            activity_dict = self._convert_to_dict(activity)
                        elif isinstance(activity, dict):
                            activity_dict = activity
                        else:
                            continue
                        
                        # Add account info
                        activity_dict['account_id'] = acc_id
                        activity_dict['account_name'] = account.get('name', 'Unknown')
                        activity_dict['account_type'] = account.get('type', 'Unknown')
                        
                        all_transactions.append(activity_dict)
                
                except Exception as e:
                    logger.error(f"Failed to get transactions for account {acc_id}: {e}")
                    continue
            
            logger.info(f"Retrieved {len(all_transactions)} total transactions")
            return all_transactions
        
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}", exc_info=True)
            return []


def create_snaptrade_connector(
    client_id: Optional[str] = None,
    consumer_key: Optional[str] = None,
    credential_manager: Optional[CredentialManager] = None
) -> SnapTradeConnector:
    """
    Factory function to create SnapTrade connector with environment variables.
    
    Args:
        client_id: SnapTrade client ID (from env if not provided)
        consumer_key: SnapTrade consumer key (from env if not provided)
        credential_manager: Credential manager instance
    
    Returns:
        Configured SnapTradeConnector instance
    """
    import os
    
    # Load .env file if it exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    client_id = client_id or os.getenv("SNAPTRADE_CLIENT_ID")
    consumer_key = consumer_key or os.getenv("SNAPTRADE_CONSUMER_KEY")
    
    if not client_id or not consumer_key:
        raise ValueError(
            "SnapTrade credentials not found. Set SNAPTRADE_CLIENT_ID and "
            "SNAPTRADE_CONSUMER_KEY environment variables."
        )
    
    if credential_manager is None:
        credential_manager = CredentialManager()
    
    return SnapTradeConnector(client_id, consumer_key, credential_manager)

# Made with Bob
