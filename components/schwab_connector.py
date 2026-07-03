"""
Schwab API Direct Integration
Main connector for Schwab brokerage accounts

Note: This implementation provides the framework for Schwab API integration.
The actual Schwab API endpoints and authentication flow may require the official
schwab-py library or adjustments based on your specific Schwab developer account setup.
"""

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from components.schwab_oauth import SchwabOAuth, TokenManager
from components.credential_manager import CredentialManager

logger = logging.getLogger(__name__)

# Try to import schwab-py library if available
try:
    import schwab
    SCHWAB_PY_AVAILABLE = True
except ImportError:
    SCHWAB_PY_AVAILABLE = False
    logger.warning("schwab-py library not available, using direct API calls")


class SchwabAPI:
    """
    Schwab API client for making authenticated requests
    Handles all API endpoints for account data, positions, transactions, and quotes
    """
    
    BASE_URL = "https://api.schwabapi.com"
    
    def __init__(self, access_token: str):
        """
        Initialize Schwab API client
        
        Args:
            access_token: Valid OAuth access token
        """
        self.access_token = access_token
        # Note: Schwab API is sensitive to headers - only include what's needed
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'accept': 'application/json'  # lowercase 'accept' as per Schwab docs
        }
        logger.debug(f"Initialized Schwab API client with token: {access_token[:20]}...")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict:
        """
        Make authenticated API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        # Log request details for debugging
        logger.debug(f"Making {method} request to {url}")
        logger.debug(f"Headers: {self.headers}")
        logger.debug(f"Params: {params}")
        
        try:
            # Make request - don't send Content-Type for GET requests
            request_headers = self.headers.copy()
            
            response = requests.request(
                method=method,
                url=url,
                headers=request_headers,
                params=params,
                json=data if method != 'GET' else None,
                timeout=30
            )
            
            # Log response for debugging
            logger.debug(f"Response status: {response.status_code}")
            if response.headers:
                logger.debug(f"Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            # Some endpoints return empty responses
            if response.status_code == 204 or not response.content:
                return {}
            
            return response.json()
            
        except requests.HTTPError as e:
            logger.error(f"API request failed: {method} {endpoint}")
            logger.error(f"Status: {e.response.status_code if e.response else 'No response'}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Request headers: {request_headers}")
            raise
    
    def get_account_numbers(self) -> List[Dict]:
        """
        Get list of account numbers linked to the user
        
        Returns:
            List of account dictionaries with accountNumber and hashValue
            
        Example response:
        [
            {
                "accountNumber": "123456789",
                "hashValue": "encrypted_hash"
            }
        ]
        """
        endpoint = "/trader/v1/accounts/accountNumbers"
        return self._make_request('GET', endpoint)
    
    def get_account_details(
        self, 
        account_hash: str, 
        include_positions: bool = True
    ) -> Dict:
        """
        Get detailed account information including positions
        
        Args:
            account_hash: Encrypted account hash from get_account_numbers
            include_positions: Whether to include position data
            
        Returns:
            Account details dictionary
            
        Example response:
        {
            "securitiesAccount": {
                "type": "MARGIN",
                "accountNumber": "123456789",
                "roundTrips": 0,
                "isDayTrader": false,
                "isClosingOnlyRestricted": false,
                "positions": [...],
                "initialBalances": {...},
                "currentBalances": {...},
                "projectedBalances": {...}
            }
        }
        """
        endpoint = f"/trader/v1/accounts/{account_hash}"
        params = {}
        
        if include_positions:
            params['fields'] = 'positions'
        
        return self._make_request('GET', endpoint, params=params)
    
    def get_all_accounts(self, include_positions: bool = True) -> List[Dict]:
        """
        Get details for all linked accounts
        
        Args:
            include_positions: Whether to include position data
            
        Returns:
            List of account detail dictionaries
        """
        # First get account numbers
        account_numbers = self.get_account_numbers()
        
        if not account_numbers:
            return []
        
        # Then get details for each account
        accounts = []
        for account_info in account_numbers:
            account_hash = account_info.get('hashValue')
            if account_hash:
                try:
                    account_details = self.get_account_details(account_hash, include_positions)
                    accounts.append(account_details)
                except Exception as e:
                    logger.error(f"Failed to get details for account {account_hash}: {e}")
        
        return accounts
    
    def get_orders(
        self,
        account_hash: str,
        from_entered_time: str,
        to_entered_time: str,
        max_results: int = 1000,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get order history for an account
        
        Note: This method is kept for compatibility but orders endpoint provides less
        comprehensive data than transactions endpoint. Use get_transactions() instead.
        
        Args:
            account_hash: Encrypted account hash
            from_entered_time: Start datetime in ISO 8601 format (e.g., "2024-01-15T00:00:00.000Z")
            to_entered_time: End datetime in ISO 8601 format (e.g., "2024-12-31T23:59:59.999Z")
            max_results: Maximum number of results (default: 1000)
            status: Optional order status filter (FILLED, CANCELED, etc.)
        
        Returns:
            List of order dictionaries
            
        Example response:
        [
            {
                "session": "NORMAL",
                "duration": "DAY",
                "orderType": "LIMIT",
                "complexOrderStrategyType": "NONE",
                "quantity": 100.0,
                "filledQuantity": 100.0,
                "remainingQuantity": 0.0,
                "requestedDestination": "AUTO",
                "destinationLinkName": "NSDQ",
                "price": 150.00,
                "orderLegCollection": [
                    {
                        "orderLegType": "EQUITY",
                        "legId": 1,
                        "instrument": {
                            "assetType": "EQUITY",
                            "cusip": "037833100",
                            "symbol": "AAPL"
                        },
                        "instruction": "BUY",
                        "positionEffect": "OPENING",
                        "quantity": 100.0
                    }
                ],
                "orderStrategyType": "SINGLE",
                "orderId": 123456789,
                "cancelable": false,
                "editable": false,
                "status": "FILLED",
                "enteredTime": "2024-01-15T10:30:00+0000",
                "closeTime": "2024-01-15T10:30:15+0000",
                "accountNumber": 123456789,
                "orderActivityCollection": [
                    {
                        "activityType": "EXECUTION",
                        "executionType": "FILL",
                        "quantity": 100.0,
                        "orderRemainingQuantity": 0.0,
                        "executionLegs": [
                            {
                                "legId": 1,
                                "quantity": 100.0,
                                "mismarkedQuantity": 0.0,
                                "price": 150.00,
                                "time": "2024-01-15T10:30:15+0000"
                            }
                        ]
                    }
                ]
            }
        ]
        """
        endpoint = f"/trader/v1/accounts/{account_hash}/orders"
        
        params = {
            'fromEnteredTime': from_entered_time,
            'toEnteredTime': to_entered_time,
            'maxResults': max_results
        }
        
        if status:
            params['status'] = status
        
        return self._make_request('GET', endpoint, params=params)
    
    def get_transactions(
        self,
        account_hash: str,
        start_date: str,
        end_date: str,
        transaction_types: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> List[Dict]:
        """
        Get transaction history for an account
        
        Args:
            account_hash: Encrypted account hash
            start_date: Start date in ISO 8601 format (e.g., "2025-03-08T21:10:42.000Z")
            end_date: End date in ISO 8601 format (e.g., "2026-03-08T21:10:42.000Z")
            transaction_types: Transaction types to filter (e.g., "TRADE", "DIVIDEND_OR_INTEREST")
                              Available types: TRADE, RECEIVE_AND_DELIVER, DIVIDEND_OR_INTEREST,
                              ACH_RECEIPT, ACH_DISBURSEMENT, CASH_RECEIPT, CASH_DISBURSEMENT,
                              ELECTRONIC_FUND, WIRE_OUT, WIRE_IN, JOURNAL, MEMORANDUM,
                              MARGIN_CALL, MONEY_MARKET, SMA_ADJUSTMENT
            symbol: Optional symbol to filter transactions (e.g., "VPV")
        
        Returns:
            List of transaction dictionaries
            
        Example response:
        [
            {
                "activityId": 123456789,
                "time": "2024-01-15T10:30:00Z",
                "type": "TRADE",
                "status": "EXECUTED",
                "subAccount": "1",
                "tradeDate": "2024-01-15",
                "settlementDate": "2024-01-17",
                "netAmount": -15000.00,
                "activityType": "EXECUTION",
                "transferItems": [
                    {
                        "instrument": {
                            "symbol": "AAPL",
                            "description": "Apple Inc"
                        },
                        "amount": 100,
                        "cost": 150.00,
                        "price": 150.00,
                        "feeType": "COMMISSION",
                        "positionEffect": "OPENING"
                    }
                ]
            }
        ]
        """
        endpoint = f"/trader/v1/accounts/{account_hash}/transactions"
        
        params = {
            'startDate': start_date,
            'endDate': end_date
        }
        
        if transaction_types:
            params['types'] = transaction_types
        
        if symbol:
            params['symbol'] = symbol
        
        return self._make_request('GET', endpoint, params=params)
    
    def get_transaction_details(
        self,
        account_hash: str,
        transaction_id: str
    ) -> Dict:
        """
        Get detailed information for a specific transaction
        
        Args:
            account_hash: Encrypted account hash
            transaction_id: Transaction ID
            
        Returns:
            Transaction detail dictionary
        """
        endpoint = f"/trader/v1/accounts/{account_hash}/transactions/{transaction_id}"
        return self._make_request('GET', endpoint)
    
    def get_quotes(self, symbols: List[str]) -> Dict:
        """
        Get real-time quotes for securities
        
        Args:
            symbols: List of ticker symbols
            
        Returns:
            Dictionary mapping symbols to quote data
            
        Example response:
        {
            "AAPL": {
                "symbol": "AAPL",
                "description": "Apple Inc",
                "bidPrice": 149.50,
                "askPrice": 149.55,
                "lastPrice": 149.52,
                "mark": 149.525,
                "bidSize": 100,
                "askSize": 100,
                "highPrice": 150.00,
                "lowPrice": 148.00,
                "openPrice": 148.50,
                "closePrice": 148.75,
                "totalVolume": 50000000,
                "quoteTime": 1705334400000,
                "tradeTime": 1705334400000,
                "netChange": 0.77,
                "netPercentChange": 0.52
            }
        }
        """
        endpoint = "/marketdata/v1/quotes"
        params = {'symbols': ','.join(symbols)}
        
        return self._make_request('GET', endpoint, params=params)
    
    def get_price_history(
        self,
        symbol: str,
        period_type: str = 'month',
        period: int = 1,
        frequency_type: str = 'daily',
        frequency: int = 1
    ) -> Dict:
        """
        Get historical price data for a security
        
        Args:
            symbol: Ticker symbol
            period_type: Type of period (day, month, year, ytd)
            period: Number of periods
            frequency_type: Type of frequency (minute, daily, weekly, monthly)
            frequency: Frequency value
            
        Returns:
            Price history dictionary with candles
        """
        endpoint = f"/marketdata/v1/pricehistory"
        params = {
            'symbol': symbol,
            'periodType': period_type,
            'period': period,
            'frequencyType': frequency_type,
            'frequency': frequency
        }
        
        return self._make_request('GET', endpoint, params=params)


class SchwabConnector:
    """
    High-level Schwab integration connector
    Manages authentication, account data, and provides simplified interface
    """
    
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        callback_url: str,
        credential_manager: Optional[CredentialManager] = None
    ):
        """
        Initialize Schwab connector
        
        Args:
            app_key: Schwab application key
            app_secret: Schwab application secret
            callback_url: OAuth callback URL
            credential_manager: Optional credential manager for token storage
        """
        self.oauth = SchwabOAuth(app_key, app_secret, callback_url)
        self.token_manager = TokenManager(self.oauth)
        self.credential_manager = credential_manager or CredentialManager()
        self.api = None
        
        logger.info("Schwab connector initialized")
    
    def get_authorization_url(self) -> str:
        """
        Get OAuth authorization URL for user to visit
        
        Returns:
            Authorization URL string
        """
        auth_url, code_verifier = self.oauth.get_authorization_url()
        
        # Store code verifier for later use
        self._code_verifier = code_verifier
        
        return auth_url
    
    def complete_authorization(self, callback_url: str) -> bool:
        """
        Complete OAuth flow after user authorization
        
        Args:
            callback_url: Full callback URL with authorization code
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract authorization code
            auth_code = SchwabOAuth.parse_callback_url(callback_url)
            
            if not auth_code:
                logger.error("No authorization code found in callback URL")
                return False
            
            # Exchange code for tokens
            token_data = self.oauth.exchange_code_for_token(
                auth_code, 
                self._code_verifier
            )
            
            # Store tokens
            self.token_manager.set_tokens(token_data)
            
            # Initialize API client
            self.api = SchwabAPI(token_data['access_token'])
            
            # Save tokens to credential manager
            self._save_tokens(token_data)
            
            logger.info("Authorization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Authorization failed: {e}")
            return False
    
    def load_saved_tokens(self, user_id: str = "default") -> bool:
        """
        Load previously saved tokens from credential manager
        
        Args:
            user_id: User identifier
            
        Returns:
            True if tokens loaded successfully
        """
        try:
            # Get all connections for user
            connections = self.credential_manager.list_connections(user_id=user_id)
            
            # Find Schwab connection
            schwab_conn = None
            for conn in connections:
                if conn.get('brokerage_name') == 'Schwab':
                    schwab_conn = conn
                    break
            
            if not schwab_conn:
                logger.info("No saved Schwab connection found")
                return False
            
            # Get full connection details with tokens
            connection = self.credential_manager.get_connection(schwab_conn['id'])
            
            if not connection:
                logger.info("Failed to retrieve Schwab connection details")
                return False
            
            # Reconstruct token data
            expires_at = connection.get('token_expiry')
            if expires_at and isinstance(expires_at, datetime):
                expires_at = expires_at.isoformat()
            
            token_data = {
                'access_token': connection.get('access_token'),
                'refresh_token': connection.get('refresh_token'),
                'expires_at': expires_at
            }
            
            # Store tokens
            self.token_manager.set_tokens(token_data)
            
            # Get valid access token (will refresh if needed)
            access_token = self.token_manager.get_valid_access_token()
            
            if access_token:
                self.api = SchwabAPI(access_token)
                logger.info("Loaded saved tokens successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to load saved tokens: {e}")
            return False
    
    def _save_tokens(self, token_data: Dict, user_id: str = "default"):
        """
        Save tokens to credential manager
        
        Args:
            token_data: Token data dictionary
            user_id: User identifier
        """
        try:
            # Parse expiry timestamp
            expires_at = token_data.get('expires_at')
            if expires_at and isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            
            self.credential_manager.store_connection(
                brokerage_name="Schwab",
                account_id="primary",
                access_token=token_data.get('access_token', ''),
                refresh_token=token_data.get('refresh_token'),
                token_expiry=expires_at,
                user_id=user_id
            )
            logger.info("Tokens saved to credential manager")
            
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
    
    def is_connected(self) -> bool:
        """
        Check if connector is authenticated and ready
        
        Returns:
            True if connected with valid token
        """
        if not self.api:
            return False
        
        access_token = self.token_manager.get_valid_access_token()
        return access_token is not None
    
    def get_accounts(self) -> List[Dict]:
        """
        Get all linked Schwab accounts
        
        Returns:
            List of account dictionaries with details and positions
        """
        if not self.is_connected():
            raise RuntimeError("Not connected. Complete authorization first.")
        
        if not self.api:
            raise RuntimeError("API client not initialized")
        
        # Ensure we have a fresh token
        fresh_token = self.token_manager.get_valid_access_token()
        if fresh_token and fresh_token != self.api.access_token:
            logger.info("Updating API client with refreshed token")
            self.api = SchwabAPI(fresh_token)
        
        try:
            accounts = self.api.get_all_accounts(include_positions=True)
            logger.info(f"Retrieved {len(accounts)} accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            raise
    
    def get_positions(
        self,
        account_hash: Optional[str] = None,
        import_transactions: bool = True,
        transaction_days_back: int = 365
    ) -> List[Dict]:
        """
        Get positions for account(s) and optionally import transaction history
        
        Args:
            account_hash: Specific account hash, or None for all accounts
            import_transactions: Whether to automatically import transaction history (default: True)
            transaction_days_back: Number of days of transaction history to import (default: 365)
            
        Returns:
            List of position dictionaries
        """
        if not self.is_connected():
            raise RuntimeError("Not connected. Complete authorization first.")
        
        if not self.api:
            raise RuntimeError("API client not initialized")
        
        try:
            # Get account hashes first
            if account_hash:
                # Single account specified
                account_hashes = [account_hash]
                account_data = self.api.get_account_details(account_hash)
                accounts = [account_data]
            else:
                # Get all accounts - need to get hashes first
                account_numbers = self.api.get_account_numbers()
                # Filter out None values and ensure we have valid hashes
                account_hashes = [h for h in (acc.get('hashValue') for acc in account_numbers) if h]
                
                # Then get details for each
                accounts = []
                for acc_hash in account_hashes:
                    if not acc_hash:  # Extra safety check
                        continue
                    try:
                        account_data = self.api.get_account_details(acc_hash, include_positions=True)
                        accounts.append(account_data)
                    except Exception as e:
                        logger.error(f"Failed to get details for account {acc_hash}: {e}")
            
            # Extract positions from all accounts
            all_positions = []
            
            for account in accounts:
                account_info = account.get('securitiesAccount', {})
                positions = account_info.get('positions', [])
                account_number = account_info.get('accountNumber', 'Unknown')
                balances = account_info.get('currentBalances', {})
                
                for position in positions:
                    all_positions.append({
                        'account_number': account_number,
                        'position': position
                    })
                
                # Inject cash / sweep / money-market balances as synthetic positions
                # Schwab reports these in currentBalances, not positions
                cash_items = {
                    'CASH':         ('CASH', 'Cash Balance',         'CASH_EQUIVALENT'),
                    'moneyMarketFund': ('SWVXX', 'Money Market Fund','MONEY_MARKET_FUND'),
                    'cashDebitCallValue': ('SWEEP', 'Cash Sweep',    'CASH_EQUIVALENT'),
                }
                
                for balance_key, (sym, desc, asset_type) in cash_items.items():
                    amount = balances.get(balance_key, 0) or 0
                    if amount != 0:
                        all_positions.append({
                            'account_number': account_number,
                            'position': {
                                'instrument': {
                                    'symbol': sym,
                                    'description': desc,
                                    'assetType': asset_type,
                                },
                                'longQuantity': amount,
                                'shortQuantity': 0,
                                'averagePrice': 1.0,
                                'marketValue': amount,
                                '_is_cash_balance': True,
                            }
                        })
                        logger.info(
                            f"Injected {desc} balance of ${amount:,.2f} "
                            f"for account {account_number[-4:]}"
                        )
            
            logger.info(f"Retrieved {len(all_positions)} positions from {len(account_hashes)} accounts")
            
            # Automatically import transactions if requested
            if import_transactions:
                # Import transactions for each account
                for acc_hash in account_hashes:
                    try:
                        logger.info(f"Importing transaction history for account {acc_hash[:8]}...")
                        self._import_transactions_for_positions(
                            account_hash=acc_hash,
                            days_back=transaction_days_back
                        )
                    except Exception as e:
                        logger.warning(f"Failed to import transactions for account {acc_hash[:8]}: {e}")
                        # Don't fail the whole operation if transaction import fails for one account
            
            return all_positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise
    
    def _import_transactions_for_positions(
        self,
        account_hash: Optional[str] = None,
        days_back: int = 365
    ):
        """
        Import order history for positions (internal helper)
        
        Note: Schwab API uses "orders" endpoint, not "transactions".
        This method fetches filled orders which provide purchase dates for positions.
        
        Args:
            account_hash: Specific account hash, or None for all accounts
            days_back: Number of days of order history to import
        """
        try:
            from components.transaction_importer import TransactionImporter
            from components.transaction_storage import TransactionStorage
            
            logger.info(f"Starting transaction import for Schwab (days_back={days_back})")
            
            # Ensure API is initialized
            if not self.api:
                logger.error("Schwab API not initialized - cannot import transactions")
                return
            
            # Ensure account_hash is provided
            if not account_hash:
                logger.error("Account hash required for transaction import")
                return
            
            # Initialize storage component
            storage = TransactionStorage()
            
            # Calculate date range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)
            
            # Format dates for Schwab API (ISO 8601)
            start_date = start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            end_date = end_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            # Fetch transactions from Schwab API (better than orders endpoint)
            logger.info(f"Fetching transactions from Schwab API ({start_date} to {end_date})...")
            raw_transactions = self.api.get_transactions(
                account_hash=account_hash,
                start_date=start_date,
                end_date=end_date,
                transaction_types='TRADE'  # Focus on trades (buys/sells)
            )
            
            logger.info(f"Fetched {len(raw_transactions)} transactions from Schwab")
            
            # Convert Schwab transactions to standard format
            transactions = []
            for txn in raw_transactions:
                try:
                    # Extract basic transaction info
                    activity_id = txn.get('activityId', '')
                    txn_time = txn.get('time', '')
                    trade_date = txn.get('tradeDate', '')
                    txn_type = txn.get('type', '')
                    
                    # Process transfer items (the actual trades)
                    for item in txn.get('transferItems', []):
                        instrument = item.get('instrument', {})
                        symbol = instrument.get('symbol', '')
                        
                        # Determine if BUY or SELL based on amount sign
                        amount = item.get('amount', 0)
                        quantity = abs(amount)
                        transaction_type = 'BUY' if amount > 0 else 'SELL'
                        
                        # Get price
                        price = item.get('price', 0)
                        if not price:
                            price = item.get('cost', 0)
                        
                        # Create transaction record
                        transaction = {
                            'transaction_id': f"{activity_id}",
                            'date': trade_date if trade_date else txn_time[:10],
                            'symbol': symbol,
                            'transaction_type': transaction_type,
                            'quantity': quantity,
                            'price': price,
                            'amount': quantity * price,
                            'account_id': account_hash,
                            'description': f"{transaction_type} {quantity} {symbol} @ ${price}"
                        }
                        transactions.append(transaction)
                        
                except Exception as e:
                    logger.warning(f"Failed to process transaction {txn.get('activityId')}: {e}")
                    continue
            
            # Convert to DataFrame
            transactions_df = pd.DataFrame(transactions)
            logger.info(f"Converted {len(transactions_df)} transactions to standard format")
            
            if len(transactions_df) > 0:
                # Log transaction types
                if 'transaction_type' in transactions_df.columns:
                    type_counts = transactions_df['transaction_type'].value_counts()
                    logger.info(f"Transaction types: {dict(type_counts)}")
                
                # Log unique symbols
                if 'symbol' in transactions_df.columns:
                    unique_symbols = transactions_df['symbol'].unique()
                    logger.info(f"Transactions for {len(unique_symbols)} unique symbols")
                    logger.info(f"Sample symbols: {list(unique_symbols)[:10]}")
                
                # Store transactions
                logger.info("Storing transactions in database...")
                storage.store_transactions(
                    transactions_df,
                    user_id="default"
                )
                logger.info(f"✅ Successfully imported and stored {len(transactions_df)} orders as transactions")
            else:
                logger.warning("⚠️ No orders to import - this may be normal if no filled orders in date range")
                
        except Exception as e:
            logger.error(f"❌ Failed to import orders: {e}", exc_info=True)
            raise
    
    def get_transactions(
        self,
        account_hash: str,
        days_back: int = 30
    ) -> List[Dict]:
        """
        Get recent transactions for an account
        
        Args:
            account_hash: Account hash
            days_back: Number of days of history to retrieve
            
        Returns:
            List of transaction dictionaries
        """
        if not self.is_connected():
            raise RuntimeError("Not connected. Complete authorization first.")
        
        if not self.api:
            raise RuntimeError("API client not initialized")
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            transactions = self.api.get_transactions(
                account_hash=account_hash,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            logger.info(f"Retrieved {len(transactions)} transactions")
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise
    
    def get_quotes(self, symbols: List[str]) -> Dict:
        """
        Get real-time quotes for securities
        
        Args:
            symbols: List of ticker symbols
            
        Returns:
            Dictionary mapping symbols to quote data
        """
        if not self.is_connected():
            raise RuntimeError("Not connected. Complete authorization first.")
        
        if not self.api:
            raise RuntimeError("API client not initialized")
        
        try:
            quotes = self.api.get_quotes(symbols)
            logger.info(f"Retrieved quotes for {len(symbols)} symbols")
            return quotes
            
        except Exception as e:
            logger.error(f"Failed to get quotes: {e}")
            raise
    
    def merge_holdings_to_portfolio(
        self,
        synced_holdings: pd.DataFrame,
        portfolio_file: str = 'portfolio_data_truth.csv'  # kept for API compatibility, unused
    ) -> pd.DataFrame:
        """
        Merge synced holdings with existing portfolio data.

        Logic for automated/synced accounts:
        - Remove ALL existing holdings for synced accounts in the current month/year
        - Replace with current synced holdings only
        - Keep holdings from other accounts and other months unchanged

        This prevents old securities from being retained when investments are switched.

        Args:
            synced_holdings: DataFrame from sync_holdings()
            portfolio_file: Ignored — data is read from portfolio.db via db_load_all().

        Returns:
            Updated portfolio DataFrame
        """
        from portfolio_db import db_load_all

        # Debug: Log incoming synced holdings
        logger.info(f"=== SCHWAB MERGE DEBUG ===")
        logger.info(f"Synced holdings columns: {synced_holdings.columns.tolist()}")
        logger.info(f"Synced holdings shape: {synced_holdings.shape}")
        if 'purchase_date' in synced_holdings.columns:
            purchase_date_count = synced_holdings['purchase_date'].notna().sum()
            logger.info(f"Purchase dates populated: {purchase_date_count} of {len(synced_holdings)}")
            logger.info(f"Sample purchase dates: {synced_holdings[synced_holdings['purchase_date'].notna()]['purchase_date'].head().tolist()}")
        else:
            logger.warning("⚠️ purchase_date column NOT FOUND in synced holdings!")

        # Load existing portfolio data directly from the DB
        existing_df = db_load_all()
        if existing_df.empty and len(synced_holdings) == 0:
            logger.warning("No synced holdings to merge and DB is empty")
            return synced_holdings
        if existing_df.empty:
            logger.info("DB is empty — returning synced holdings as full portfolio")
            return synced_holdings

        logger.info(f"Starting merge: {len(synced_holdings)} synced holdings, {len(existing_df)} existing holdings")
        
        # Get unique synced accounts and their month/year
        if len(synced_holdings) == 0:
            logger.warning("No synced holdings to merge")
            return existing_df
        
        # Extract unique (month, year, account_name) combinations from synced data
        synced_accounts = synced_holdings[['month', 'year', 'account_name']].drop_duplicates()
        
        logger.info(f"Synced accounts to replace: {len(synced_accounts)}")
        for _, acc in synced_accounts.iterrows():
            logger.info(f"  - {acc['account_name']} for {acc['month']}/{acc['year']}")
        
        # Remove ALL existing holdings for these synced accounts in the current month/year
        # This ensures old securities are removed when investments are switched
        mask_to_remove = pd.Series([False] * len(existing_df))
        for _, acc in synced_accounts.iterrows():
            account_mask = (
                (existing_df['month'] == acc['month']) &
                (existing_df['year'] == acc['year']) &
                (existing_df['account_name'] == acc['account_name'])
            )
            mask_to_remove |= account_mask
            removed_count = account_mask.sum()
            logger.info(f"Removing {removed_count} existing holdings from {acc['account_name']} for {acc['month']}/{acc['year']}")
        
        # Keep only holdings NOT in synced accounts for this month/year
        remaining_df = existing_df[~mask_to_remove].copy()
        logger.info(f"Kept {len(remaining_df)} holdings from other accounts/months")
        
        # Combine remaining holdings with new synced holdings
        updated_rows = []
        if len(remaining_df) > 0:
            updated_rows.extend([row.to_dict() for _, row in remaining_df.iterrows()])
        
        # Add all synced holdings (these replace the old ones completely)
        for _, synced_row in synced_holdings.iterrows():
            logger.info(f"✓ Adding synced holding: {synced_row['symbol']} in {synced_row['account_name']} for {synced_row['month']}/{synced_row['year']}")
            updated_rows.append(synced_row.to_dict())
        
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
    
    def disconnect(self):
        """Disconnect and clear tokens"""
        self.token_manager.clear_tokens()
        self.api = None
        logger.info("Disconnected from Schwab")

# Made with Bob
