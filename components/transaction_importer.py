"""
components/transaction_importer.py
===================================
Transaction history import and cost basis tracking for brokerage accounts.

Handles:
- Transaction history import from SnapTrade
- Cost basis calculation and tracking
- Tax lot management
- Capital gains/losses calculation
- Transaction categorization
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

import pandas as pd

logger = logging.getLogger(__name__)


class TransactionType(Enum):
    """Transaction type enumeration."""
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    SPLIT = "split"
    MERGER = "merger"
    SPINOFF = "spinoff"
    OTHER = "other"


class TransactionImporter:
    """
    Manages transaction history import and cost basis tracking.
    
    Features:
    - Import transaction history from SnapTrade
    - Calculate cost basis using FIFO, LIFO, or specific lot methods
    - Track tax lots for capital gains reporting
    - Generate transaction reports
    - Support for corporate actions (splits, mergers, etc.)
    """
    
    def __init__(self, snaptrade_connector=None, schwab_connector=None):
        """
        Initialize transaction importer.
        
        Args:
            snaptrade_connector: SnapTradeConnector instance (optional)
            schwab_connector: SchwabConnector instance (optional)
        """
        self.snaptrade_connector = snaptrade_connector
        self.schwab_connector = schwab_connector
        self.transactions_cache: Dict[str, pd.DataFrame] = {}
    
    def get_transactions(
        self,
        user_id: str = "default",
        user_secret: Optional[str] = None,
        account_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        transaction_types: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Fetch transaction history from SnapTrade.
        
        Args:
            user_id: User identifier
            user_secret: User secret (from env if not provided)
            account_id: Specific account ID (optional, gets all if not provided)
            start_date: Start date in YYYY-MM-DD format (default: 1 year ago)
            end_date: End date in YYYY-MM-DD format (default: today)
            transaction_types: Filter by transaction types (optional)
        
        Returns:
            DataFrame with transaction history
        """
        if not self.snaptrade_connector:
            logger.error("SnapTrade connector not initialized")
            return pd.DataFrame()
        
        try:
            # Get userSecret if not provided
            if not user_secret:
                import os
                user_secret = os.getenv("SNAPTRADE_USER_SECRET")
            
            if not user_secret:
                raise ValueError("userSecret is required but not provided")
            
            # Set default date range (1 year)
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
                # Pass user_secret to get_accounts
                accounts = self.snaptrade_connector.get_accounts(user_id=user_id, user_secret=user_secret)
                accounts_to_process = accounts
            
            all_transactions = []
            
            for account in accounts_to_process:
                acc_id = account.get('id')
                if not acc_id:
                    continue
                
                try:
                    # Fetch activities (transactions) from SnapTrade
                    activities = self.snaptrade_connector.client.account_information.get_account_activities(
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
                            activity_dict = self.snaptrade_connector._convert_to_dict(activity)
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
            
            if not all_transactions:
                logger.warning("No transactions found")
                return pd.DataFrame()
            
            # Transform to standardized format
            df = self._transform_transactions(all_transactions)
            
            # Filter by transaction types if specified
            if transaction_types:
                df = df[df['transaction_type'].isin(transaction_types)]
            
            logger.info(f"Imported {len(df)} transactions")
            return df
        
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}", exc_info=True)
            return pd.DataFrame()
    
    def get_schwab_transactions(
        self,
        account_hash: Optional[str] = None,
        days_back: int = 365
    ) -> pd.DataFrame:
        """
        Fetch transaction history from Schwab.
        
        Args:
            account_hash: Specific account hash (optional, gets all if not provided)
            days_back: Number of days of history to retrieve (default: 365)
        
        Returns:
            DataFrame with transaction history
        """
        if not self.schwab_connector:
            logger.error("Schwab connector not initialized")
            return pd.DataFrame()
        
        try:
            from datetime import datetime, timedelta
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Convert to ISO 8601 format required by Schwab API
            start_date_iso = start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            end_date_iso = end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            logger.info(f"Fetching Schwab transactions from {start_date.date()} to {end_date.date()}")
            
            # Get account numbers if not specified
            if account_hash:
                account_hashes = [account_hash]
            else:
                # Get all accounts
                account_numbers = self.schwab_connector.api.get_account_numbers()
                account_hashes = [acc.get('hashValue') for acc in account_numbers if acc.get('hashValue')]
            
            all_transactions = []
            
            for acc_hash in account_hashes:
                try:
                    # Fetch all transaction types
                    # Note: We fetch TRADE and DIVIDEND_OR_INTEREST separately as they're most common
                    for txn_type in ['TRADE', 'DIVIDEND_OR_INTEREST', 'RECEIVE_AND_DELIVER']:
                        try:
                            transactions = self.schwab_connector.api.get_transactions(
                                account_hash=acc_hash,
                                start_date=start_date_iso,
                                end_date=end_date_iso,
                                transaction_types=txn_type
                            )
                            
                            logger.info(f"Retrieved {len(transactions)} {txn_type} transactions for account {acc_hash}")
                            
                            # Add account hash to each transaction
                            for txn in transactions:
                                txn['account_hash'] = acc_hash
                                all_transactions.append(txn)
                        except Exception as e:
                            logger.warning(f"Failed to get {txn_type} transactions for account {acc_hash}: {e}")
                            continue
                
                except Exception as e:
                    logger.error(f"Failed to get transactions for account {acc_hash}: {e}")
                    continue
            
            if not all_transactions:
                logger.warning("No Schwab transactions found")
                return pd.DataFrame()
            
            # Transform to standardized format
            df = self._transform_schwab_transactions(all_transactions)
            
            logger.info(f"Imported {len(df)} Schwab transactions")
            return df
        
        except Exception as e:
            logger.error(f"Failed to get Schwab transactions: {e}", exc_info=True)
            return pd.DataFrame()
    
    def _transform_schwab_orders(self, orders: List[Dict]) -> pd.DataFrame:
        """
        Transform Schwab orders to standardized transaction format.
        
        Args:
            orders: List of order dictionaries from Schwab API
        
        Returns:
            DataFrame with standardized transaction format
        """
        rows = []
        
        for order in orders:
            # Extract order details
            order_id = str(order.get('orderId', ''))
            status = order.get('status', '')
            account_hash = order.get('account_hash', '')
            
            # Skip non-filled orders
            if status != 'FILLED':
                continue
            
            # Parse dates - use closeTime (execution time) as transaction date
            close_time = order.get('closeTime', '')
            entered_time = order.get('enteredTime', '')
            
            # Extract date from ISO 8601 timestamp (e.g., "2024-01-15T10:30:15+0000")
            if close_time:
                # Parse ISO format and extract date
                try:
                    from datetime import datetime
                    trade_date = datetime.fromisoformat(close_time.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                except:
                    trade_date = close_time.split('T')[0] if 'T' in close_time else close_time
            else:
                trade_date = ''
            
            # Process order legs (securities involved)
            order_legs = order.get('orderLegCollection', [])
            
            if not order_legs:
                logger.warning(f"Order {order_id} has no legs, skipping")
                continue
            
            # Get execution details from orderActivityCollection
            executions = []
            for activity in order.get('orderActivityCollection', []):
                if activity.get('activityType') == 'EXECUTION':
                    for exec_leg in activity.get('executionLegs', []):
                        executions.append(exec_leg)
            
            # Process each order leg
            for leg in order_legs:
                instrument = leg.get('instrument', {})
                symbol = instrument.get('symbol', '')
                asset_type = instrument.get('assetType', '')
                
                instruction = leg.get('instruction', '')  # BUY or SELL
                quantity = leg.get('quantity', 0)
                
                # Get execution price from activity collection
                price = 0.0
                if executions:
                    # Find matching execution leg
                    leg_id = leg.get('legId', 0)
                    for exec_leg in executions:
                        if exec_leg.get('legId') == leg_id:
                            price = exec_leg.get('price', 0.0)
                            break
                
                # If no execution price, try order price
                if not price:
                    price = order.get('price', 0.0)
                
                # Determine transaction type
                if instruction == 'BUY':
                    txn_type = TransactionType.BUY.value
                elif instruction == 'SELL' or instruction == 'SELL_SHORT':
                    txn_type = TransactionType.SELL.value
                else:
                    txn_type = TransactionType.OTHER.value
                
                row = {
                    'transaction_id': order_id,
                    'date': trade_date,
                    'transaction_type': txn_type,
                    'symbol': str(symbol),
                    'description': f"{instruction} {symbol}",
                    'quantity': float(quantity) if quantity else 0.0,
                    'price': float(price) if price else 0.0,
                    'amount': float(quantity * price) if quantity and price else 0.0,
                    'fee': 0.0,  # Schwab doesn't separate fees in orders API
                    'account_id': account_hash,
                    'account_name': f"Schwab-{account_hash[-4:]}",
                    'account_type': 'Brokerage',
                    'raw_data': str(order)
                }
                rows.append(row)
        
        if not rows:
            logger.warning("No valid Schwab orders found after transformation")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # Ensure date is datetime
        if 'date' in df.columns and len(df) > 0:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Sort by date
        if len(df) > 0:
            df = df.sort_values('date')
        
        return df
    
    def _transform_schwab_transactions(self, transactions: List[Dict]) -> pd.DataFrame:
        """
        Transform Schwab transactions to standardized format.
        
        Args:
            transactions: List of transaction dictionaries from Schwab API
        
        Returns:
            DataFrame with standardized transaction format
        """
        rows = []
        
        for txn in transactions:
            # Extract transaction details
            txn_id = str(txn.get('activityId', ''))
            txn_type = txn.get('type', 'UNKNOWN')
            status = txn.get('status', 'UNKNOWN')
            account_hash = txn.get('account_hash', '')
            
            # Parse dates
            trade_date = txn.get('tradeDate', '')
            settlement_date = txn.get('settlementDate', '')
            
            # Get transaction details
            net_amount = txn.get('netAmount', 0)
            
            # Process transfer items (securities involved)
            transfer_items = txn.get('transferItems', [])
            
            if not transfer_items:
                # Cash transaction or other non-security transaction
                row = {
                    'transaction_id': txn_id,
                    'date': trade_date,
                    'transaction_type': self._map_schwab_transaction_type(txn_type),
                    'symbol': '',
                    'description': txn_type.replace('_', ' ').title(),
                    'quantity': 0.0,
                    'price': 0.0,
                    'amount': float(net_amount) if net_amount else 0.0,
                    'fee': 0.0,
                    'account_id': account_hash,
                    'account_name': f"Schwab-{account_hash[-4:]}",
                    'account_type': 'Brokerage',
                    'raw_data': str(txn)
                }
                rows.append(row)
            else:
                # Security transaction
                for item in transfer_items:
                    instrument = item.get('instrument', {})
                    symbol = instrument.get('symbol', '')
                    description = instrument.get('description', '')
                    
                    quantity = item.get('amount', 0)
                    price = item.get('price', 0)
                    cost = item.get('cost', 0)
                    
                    # Determine if buy or sell based on position effect
                    position_effect = item.get('positionEffect', '')
                    if position_effect == 'CLOSING':
                        mapped_type = TransactionType.SELL.value
                    elif position_effect == 'OPENING':
                        mapped_type = TransactionType.BUY.value
                    else:
                        mapped_type = self._map_schwab_transaction_type(txn_type)
                    
                    row = {
                        'transaction_id': txn_id,
                        'date': trade_date,
                        'transaction_type': mapped_type,
                        'symbol': str(symbol),
                        'description': str(description),
                        'quantity': float(quantity) if quantity else 0.0,
                        'price': float(price) if price else 0.0,
                        'amount': float(cost * quantity if cost else price * quantity),
                        'fee': 0.0,  # Schwab doesn't separate fees in API
                        'account_id': account_hash,
                        'account_name': f"Schwab-{account_hash[-4:]}",
                        'account_type': 'Brokerage',
                        'raw_data': str(txn)
                    }
                    rows.append(row)
        
        if not rows:
            logger.warning("No valid Schwab transactions found after transformation")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # Ensure date is datetime, then normalize to date-only (no time component)
        if 'date' in df.columns and len(df) > 0:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            # Normalize to date-only format (YYYY-MM-DD) by removing time component
            df['date'] = df['date'].dt.normalize()
        
        # Sort by date
        if len(df) > 0:
            df = df.sort_values('date')
        
        return df
    
    def _map_schwab_transaction_type(self, schwab_type: str) -> str:
        """
        Map Schwab transaction type to standardized type.
        
        Args:
            schwab_type: Transaction type from Schwab
        
        Returns:
            Standardized transaction type
        """
        type_mapping = {
            'TRADE': TransactionType.BUY.value,  # Will be refined by positionEffect
            'RECEIVE_AND_DELIVER': TransactionType.TRANSFER_IN.value,
            'DIVIDEND_OR_INTEREST': TransactionType.DIVIDEND.value,
            'DIVIDEND': TransactionType.DIVIDEND.value,
            'INTEREST': TransactionType.INTEREST.value,
            'ACH_RECEIPT': TransactionType.DEPOSIT.value,
            'ACH_DISBURSEMENT': TransactionType.WITHDRAWAL.value,
            'CASH_RECEIPT': TransactionType.DEPOSIT.value,
            'CASH_DISBURSEMENT': TransactionType.WITHDRAWAL.value,
            'ELECTRONIC_FUND': TransactionType.TRANSFER_IN.value,
            'WIRE_OUT': TransactionType.WITHDRAWAL.value,
            'WIRE_IN': TransactionType.DEPOSIT.value,
            'JOURNAL': TransactionType.TRANSFER_IN.value,
            'MERGER': TransactionType.MERGER.value,
            'SPINOFF': TransactionType.SPINOFF.value,
            'STOCK_SPLIT': TransactionType.SPLIT.value,
        }
        
        return type_mapping.get(schwab_type.upper(), TransactionType.OTHER.value)
    
    def _transform_transactions(self, transactions: List[Dict]) -> pd.DataFrame:
        """
        Transform SnapTrade transactions to standardized format.
        
        Args:
            transactions: List of transaction dictionaries from SnapTrade
        
        Returns:
            DataFrame with standardized transaction format
        """
        rows = []
        
        for txn in transactions:
            # Extract transaction details
            txn_id = txn.get('id', '')
            txn_date = txn.get('trade_date') or txn.get('settlement_date') or txn.get('date', '')
            txn_type = self._map_transaction_type(txn.get('type', ''))
            
            # Extract symbol information
            symbol_data = txn.get('symbol', {})
            if isinstance(symbol_data, dict):
                symbol = symbol_data.get('raw_symbol') or symbol_data.get('symbol', '')
                description = symbol_data.get('description', '')
            else:
                symbol = ''
                description = ''
            
            # Extract amounts
            quantity = txn.get('units') or txn.get('quantity', 0)
            price = txn.get('price', 0)
            amount = txn.get('amount') or txn.get('net_amount', 0)
            fee = txn.get('fee') or txn.get('commission', 0)
            
            # Account information
            account_id = txn.get('account_id', '')
            account_name = txn.get('account_name', '')
            account_type = txn.get('account_type', '')
            
            row = {
                'transaction_id': str(txn_id),
                'date': txn_date,
                'transaction_type': txn_type,
                'symbol': str(symbol),
                'description': str(description),
                'quantity': float(quantity) if quantity else 0.0,
                'price': float(price) if price else 0.0,
                'amount': float(amount) if amount else 0.0,
                'fee': float(fee) if fee else 0.0,
                'account_id': str(account_id),
                'account_name': str(account_name),
                'account_type': str(account_type),
                'raw_data': str(txn)  # Store raw data for debugging
            }
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Ensure date is datetime
        if 'date' in df.columns and len(df) > 0:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Sort by date
        if len(df) > 0:
            df = df.sort_values('date')
        
        return df
    
    def _map_transaction_type(self, snaptrade_type: str) -> str:
        """
        Map SnapTrade transaction type to standardized type.
        
        Args:
            snaptrade_type: Transaction type from SnapTrade
        
        Returns:
            Standardized transaction type
        """
        type_mapping = {
            'buy': TransactionType.BUY.value,
            'sell': TransactionType.SELL.value,
            'dividend': TransactionType.DIVIDEND.value,
            'div': TransactionType.DIVIDEND.value,
            'interest': TransactionType.INTEREST.value,
            'int': TransactionType.INTEREST.value,
            'deposit': TransactionType.DEPOSIT.value,
            'cash_deposit': TransactionType.DEPOSIT.value,
            'withdrawal': TransactionType.WITHDRAWAL.value,
            'cash_withdrawal': TransactionType.WITHDRAWAL.value,
            'transfer_in': TransactionType.TRANSFER_IN.value,
            'transfer_out': TransactionType.TRANSFER_OUT.value,
            'split': TransactionType.SPLIT.value,
            'stock_split': TransactionType.SPLIT.value,
            'merger': TransactionType.MERGER.value,
            'spinoff': TransactionType.SPINOFF.value,
        }
        
        return type_mapping.get(snaptrade_type.lower(), TransactionType.OTHER.value)
    
    def calculate_cost_basis(
        self,
        transactions: pd.DataFrame,
        symbol: str,
        method: str = "FIFO"
    ) -> Dict[str, Any]:
        """
        Calculate cost basis for a specific symbol using specified method.
        
        Args:
            transactions: DataFrame with transaction history
            symbol: Stock symbol to calculate cost basis for
            method: Cost basis method ("FIFO", "LIFO", "AVERAGE")
        
        Returns:
            Dictionary with cost basis information
        """
        # Filter transactions for this symbol
        symbol_txns = transactions[
            (transactions['symbol'] == symbol) &
            (transactions['transaction_type'].isin(['buy', 'sell']))
        ].copy()
        
        if len(symbol_txns) == 0:
            return {
                'symbol': symbol,
                'total_shares': 0,
                'total_cost': 0,
                'average_cost': 0,
                'tax_lots': []
            }
        
        # Sort by date
        symbol_txns = symbol_txns.sort_values('date')
        
        # Track tax lots
        tax_lots = []
        total_shares = 0
        total_cost = 0
        
        for _, txn in symbol_txns.iterrows():
            if txn['transaction_type'] == 'buy':
                # Add new tax lot
                lot = {
                    'date': txn['date'],
                    'quantity': txn['quantity'],
                    'price': txn['price'],
                    'cost': txn['quantity'] * txn['price'] + txn['fee'],
                    'remaining': txn['quantity']
                }
                tax_lots.append(lot)
                total_shares += txn['quantity']
                total_cost += lot['cost']
            
            elif txn['transaction_type'] == 'sell':
                # Reduce tax lots based on method
                shares_to_sell = txn['quantity']
                
                if method == "FIFO":
                    # First In, First Out
                    for lot in tax_lots:
                        if shares_to_sell <= 0:
                            break
                        if lot['remaining'] > 0:
                            sold = min(lot['remaining'], shares_to_sell)
                            lot['remaining'] -= sold
                            shares_to_sell -= sold
                            total_shares -= sold
                
                elif method == "LIFO":
                    # Last In, First Out
                    for lot in reversed(tax_lots):
                        if shares_to_sell <= 0:
                            break
                        if lot['remaining'] > 0:
                            sold = min(lot['remaining'], shares_to_sell)
                            lot['remaining'] -= sold
                            shares_to_sell -= sold
                            total_shares -= sold
        
        # Calculate average cost
        remaining_lots = [lot for lot in tax_lots if lot['remaining'] > 0]
        remaining_cost = sum(lot['price'] * lot['remaining'] for lot in remaining_lots)
        average_cost = remaining_cost / total_shares if total_shares > 0 else 0
        
        return {
            'symbol': symbol,
            'total_shares': total_shares,
            'total_cost': remaining_cost,
            'average_cost': average_cost,
            'tax_lots': remaining_lots,
            'method': method
        }
    
    def calculate_capital_gains(
        self,
        transactions: pd.DataFrame,
        tax_year: int,
        method: str = "FIFO"
    ) -> pd.DataFrame:
        """
        Calculate capital gains/losses for a tax year.
        
        Args:
            transactions: DataFrame with transaction history
            tax_year: Tax year to calculate gains for
            method: Cost basis method ("FIFO", "LIFO", "AVERAGE")
        
        Returns:
            DataFrame with capital gains/losses by symbol
        """
        # Filter sell transactions for tax year
        year_start = datetime(tax_year, 1, 1)
        year_end = datetime(tax_year, 12, 31)
        
        sells = transactions[
            (transactions['transaction_type'] == 'sell') &
            (transactions['date'] >= year_start) &
            (transactions['date'] <= year_end)
        ].copy()
        
        if len(sells) == 0:
            return pd.DataFrame()
        
        gains_data = []
        
        for symbol in sells['symbol'].unique():
            # Get all transactions for this symbol up to end of tax year
            symbol_txns = transactions[
                (transactions['symbol'] == symbol) &
                (transactions['date'] <= year_end)
            ].copy()
            
            # Calculate cost basis
            cost_basis = self.calculate_cost_basis(symbol_txns, symbol, method)
            
            # Get sells for this symbol in tax year
            symbol_sells = sells[sells['symbol'] == symbol]
            
            for _, sell_txn in symbol_sells.iterrows():
                # Calculate gain/loss
                proceeds = sell_txn['amount']
                # Simplified: use average cost basis
                cost = sell_txn['quantity'] * cost_basis['average_cost']
                gain_loss = proceeds - cost
                
                # Determine holding period (short-term < 1 year, long-term >= 1 year)
                # This is simplified - proper implementation would track specific lots
                holding_period = "long_term"  # Default assumption
                
                gains_data.append({
                    'symbol': symbol,
                    'sell_date': sell_txn['date'],
                    'quantity': sell_txn['quantity'],
                    'proceeds': proceeds,
                    'cost_basis': cost,
                    'gain_loss': gain_loss,
                    'holding_period': holding_period,
                    'account_name': sell_txn['account_name']
                })
        
        return pd.DataFrame(gains_data)
    
    def generate_transaction_report(
        self,
        transactions: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive transaction report.
        
        Args:
            transactions: DataFrame with transaction history
            start_date: Start date for report (optional)
            end_date: End date for report (optional)
        
        Returns:
            Dictionary with report data
        """
        if len(transactions) == 0:
            return {
                'total_transactions': 0,
                'by_type': {},
                'by_account': {},
                'total_invested': 0,
                'total_withdrawn': 0,
                'dividend_income': 0,
                'interest_income': 0
            }
        
        # Filter by date range if specified
        df = transactions.copy()
        if start_date:
            df = df[df['date'] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df['date'] <= pd.to_datetime(end_date)]
        
        # Calculate summary statistics
        by_type = df.groupby('transaction_type').agg({
            'transaction_id': 'count',
            'amount': 'sum'
        }).to_dict('index')
        
        by_account = df.groupby('account_name').agg({
            'transaction_id': 'count',
            'amount': 'sum'
        }).to_dict('index')
        
        # Calculate totals
        buys = df[df['transaction_type'] == 'buy']
        sells = df[df['transaction_type'] == 'sell']
        dividends = df[df['transaction_type'] == 'dividend']
        interest = df[df['transaction_type'] == 'interest']
        
        return {
            'total_transactions': len(df),
            'date_range': {
                'start': df['date'].min().strftime('%Y-%m-%d') if len(df) > 0 else None,
                'end': df['date'].max().strftime('%Y-%m-%d') if len(df) > 0 else None
            },
            'by_type': by_type,
            'by_account': by_account,
            'total_invested': abs(buys['amount'].sum()) if len(buys) > 0 else 0,
            'total_proceeds': abs(sells['amount'].sum()) if len(sells) > 0 else 0,
            'dividend_income': abs(dividends['amount'].sum()) if len(dividends) > 0 else 0,
            'interest_income': abs(interest['amount'].sum()) if len(interest) > 0 else 0
        }


def create_transaction_importer(snaptrade_connector) -> TransactionImporter:
    """
    Factory function to create TransactionImporter instance.
    
    Args:
        snaptrade_connector: SnapTradeConnector instance
    
    Returns:
        Configured TransactionImporter instance
    """
    return TransactionImporter(snaptrade_connector)


# Made with Bob