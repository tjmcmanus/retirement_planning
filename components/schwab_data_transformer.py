"""
Schwab Data Transformation Utilities
Converts Schwab API responses to portfolio format
"""

import pandas as pd
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def get_account_config(account_name: str) -> Dict:
    """
    Look up account configuration from config.
    
    Args:
        account_name: Name of the account to look up
        
    Returns:
        Dict with account_type and owner, or defaults if not found
    """
    try:
        from config import get_config_manager
        config_mgr = get_config_manager()
        accounts = config_mgr.get("portfolio_accounts", "accounts", [])
        
        # Find matching account
        for account in accounts:
            if account.get('account_name') == account_name:
                return {
                    'account_type': account.get('account_type', 'Brokerage'),
                    'owner': account.get('owner', 'Joint')
                }
        
        # Not found, return defaults
        return {'account_type': 'Brokerage', 'owner': 'Joint'}
    except Exception as e:
        logger.warning(f"Could not load account config: {e}")
        return {'account_type': 'Brokerage', 'owner': 'Joint'}


class SchwabDataTransformer:
    """
    Transform Schwab API data to portfolio format
    
    Handles conversion of:
    - Account positions to portfolio holdings
    - Transactions to standardized format
    - Quotes to market data
    """
    
    # Asset type mapping
    ASSET_TYPE_MAP = {
        'EQUITY': 'Stock',
        'MUTUAL_FUND': 'Mutual Fund',
        'FIXED_INCOME': 'Bond',
        'OPTION': 'MF:OTHER',  # Options marked as MF:OTHER
        'WARRANT': 'MF:OTHER',  # Warrants marked as MF:OTHER
        'CASH_EQUIVALENT': 'Cash',
        'MONEY_MARKET_FUND': 'Money Market',
        'INDEX': 'Index Fund',
        'COLLECTIVE_INVESTMENT': 'Fund'
    }
    
    # Account type mapping
    ACCOUNT_TYPE_MAP = {
        'CASH': 'Brokerage',
        'MARGIN': 'Brokerage',
        'IRA': 'IRA',
        'ROTH_IRA': 'Roth IRA',
        'ROLLOVER_IRA': 'Rollover IRA',
        'SIMPLE_IRA': 'SIMPLE IRA',
        'SEP_IRA': 'SEP IRA',
        'INDIVIDUAL': 'Individual',
        'JOINT': 'Joint',
        'TRUST': 'Trust',
        'CORPORATE': 'Corporate'
    }
    
    @staticmethod
    def transform_positions_to_portfolio(
        positions_data: List[Dict],
        owner: str = "Self",
        enrich_with_transactions: bool = True
    ) -> pd.DataFrame:
        """
        Transform Schwab positions to portfolio format
        
        Args:
            positions_data: List of position dictionaries from Schwab API
            owner: Owner name for the positions
            enrich_with_transactions: Whether to enrich with purchase dates from transactions (default: True)
            
        Returns:
            DataFrame in portfolio format with columns:
            month, year, account_name, account_type, owner, symbol,
            name, sector, qty, purchase_price, purchase_date
            
        Schwab Position Format:
        {
            'account_number': '123456789',
            'position': {
                'instrument': {
                    'symbol': 'AAPL',
                    'description': 'Apple Inc',
                    'assetType': 'EQUITY'
                },
                'longQuantity': 100,
                'shortQuantity': 0,
                'averagePrice': 150.00,
                'currentDayProfitLoss': 50.00,
                'marketValue': 15500.00,
                'maintenanceRequirement': 0.0
            }
        }
        """
        if not positions_data:
            logger.warning("No positions data to transform")
            return pd.DataFrame()
        
        rows = []
        current_date = datetime.now()
        
        for item in positions_data:
            account_number = item.get('account_number', 'Unknown')
            position = item.get('position', {})
            
            # Extract instrument details
            instrument = position.get('instrument', {})
            symbol = instrument.get('symbol', '')
            description = instrument.get('description', '')
            asset_type = instrument.get('assetType', 'EQUITY')
            
            # Get position details
            quantity = position.get('longQuantity', 0) - position.get('shortQuantity', 0)
            avg_price = position.get('averagePrice', 0)
            market_value = position.get('marketValue', 0)
            
            # Skip if no quantity
            if quantity == 0:
                continue
            
            # Map asset type to sector
            sector = SchwabDataTransformer.ASSET_TYPE_MAP.get(
                asset_type,
                asset_type.replace('_', ' ').title()
            )
            
            # Additional check: if symbol contains special characters, likely option/warrant
            if any(char in symbol for char in ['/', ' ', '.']):
                sector = 'MF:OTHER'
                logger.info(f"Detected option/warrant by symbol pattern: {symbol}")
            
            # Generate account name
            account_name = f"Schwab-{account_number[-4:]}"
            
            # Look up account configuration
            logger.info(f"Looking up account config for: {account_name}")
            account_config = get_account_config(account_name)
            logger.info(f"Account config result: {account_config}")
            
            # Create portfolio row
            row = {
                'month': current_date.month,
                'year': current_date.year,
                'account_name': account_name,
                'account_type': account_config['account_type'],
                'owner': account_config['owner'],
                'symbol': symbol,
                'name': description,
                'sector': sector,
                'qty': quantity,
                'purchase_price': avg_price,
                'purchase_date': None,  # Will be enriched from transactions if available
                'current_value': market_value,
                'account_number': account_number  # Keep for transaction matching
            }
            
            rows.append(row)
        
        if not rows:
            logger.warning("No valid positions found after transformation")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        logger.info(f"Transformed {len(df)} positions to portfolio format")
        
        # Enrich with purchase dates from transaction history if requested
        if enrich_with_transactions and len(df) > 0:
            df = SchwabDataTransformer._enrich_with_purchase_dates(df)
        
        return df
    
    @staticmethod
    def _enrich_with_purchase_dates(positions_df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich positions with purchase dates from transaction history
        
        Args:
            positions_df: DataFrame with positions
            
        Returns:
            DataFrame with purchase_date filled from transaction history
        """
        try:
            from components.transaction_storage import TransactionStorage
            
            storage = TransactionStorage()
            
            # First check if we have any transactions at all
            all_transactions = storage.get_transactions(user_id="default")
            logger.info(f"Found {len(all_transactions)} total transactions in database")
            
            if len(all_transactions) == 0:
                logger.warning("No transactions found in database - cannot enrich purchase dates")
                return positions_df
            
            # Log unique symbols in transactions
            if len(all_transactions) > 0:
                unique_txn_symbols = all_transactions['symbol'].unique() if 'symbol' in all_transactions.columns else []
                logger.info(f"Transactions available for symbols: {list(unique_txn_symbols)[:10]}...")  # Show first 10
            
            # Process each position
            enriched_count = 0
            for idx, row in positions_df.iterrows():
                try:
                    symbol_val = row['symbol']
                    # Handle both scalar and Series values
                    if isinstance(symbol_val, pd.Series):
                        symbol = str(symbol_val.iloc[0]) if len(symbol_val) > 0 and pd.notna(symbol_val.iloc[0]) else ''
                    else:
                        symbol = str(symbol_val) if pd.notna(symbol_val) else ''
                    
                    if not symbol or symbol == '':
                        continue
                    
                    # Get buy transactions for this symbol
                    transactions = storage.get_transactions(
                        user_id="default",
                        symbol=symbol,
                        transaction_types=['BUY']  # Must be uppercase to match stored values
                    )
                    
                    logger.debug(f"Found {len(transactions)} BUY transactions for {symbol}")
                    
                    if len(transactions) > 0:
                        # Use the earliest purchase date
                        earliest_purchase = transactions['transaction_date'].min()
                        positions_df.at[idx, 'purchase_date'] = earliest_purchase
                        enriched_count += 1
                        logger.info(f"✅ Enriched {symbol} with purchase date: {earliest_purchase}")
                    else:
                        logger.debug(f"No BUY transactions found for {symbol}")
                
                except Exception as e:
                    logger.error(f"Error enriching position with purchase date: {e}", exc_info=True)
                    continue
            
            logger.info(f"Successfully enriched {enriched_count} of {len(positions_df)} positions with purchase dates")
            
        except Exception as e:
            logger.error(f"Failed to enrich positions with purchase dates: {e}", exc_info=True)
        
        return positions_df
    
    @staticmethod
    def transform_account_details(account_data: Dict) -> Dict:
        """
        Transform Schwab account details to simplified format
        
        Args:
            account_data: Account data from Schwab API
            
        Returns:
            Dictionary with account summary
        """
        securities_account = account_data.get('securitiesAccount', {})
        
        account_type = securities_account.get('type', 'UNKNOWN')
        account_number = securities_account.get('accountNumber', 'Unknown')
        
        # Get balances
        current_balances = securities_account.get('currentBalances', {})
        
        return {
            'account_number': account_number,
            'account_type': SchwabDataTransformer.ACCOUNT_TYPE_MAP.get(
                account_type, 
                account_type.replace('_', ' ').title()
            ),
            'cash_balance': current_balances.get('cashBalance', 0),
            'market_value': current_balances.get('liquidationValue', 0),
            'buying_power': current_balances.get('buyingPower', 0),
            'is_day_trader': securities_account.get('isDayTrader', False),
            'round_trips': securities_account.get('roundTrips', 0),
            'position_count': len(securities_account.get('positions', []))
        }
    
    @staticmethod
    def transform_transactions(
        transactions: List[Dict],
        account_number: str
    ) -> pd.DataFrame:
        """
        Transform Schwab transactions to standardized format
        
        Args:
            transactions: List of transaction dictionaries from Schwab API
            account_number: Account number for the transactions
            
        Returns:
            DataFrame with transaction data
            
        Schwab Transaction Format:
        {
            'activityId': 123456789,
            'time': '2024-01-15T10:30:00Z',
            'type': 'TRADE',
            'status': 'EXECUTED',
            'tradeDate': '2024-01-15',
            'settlementDate': '2024-01-17',
            'netAmount': -15000.00,
            'transferItems': [
                {
                    'instrument': {
                        'symbol': 'AAPL',
                        'description': 'Apple Inc'
                    },
                    'amount': 100,
                    'cost': 150.00,
                    'price': 150.00,
                    'positionEffect': 'OPENING'
                }
            ]
        }
        """
        if not transactions:
            logger.warning("No transactions to transform")
            return pd.DataFrame()
        
        rows = []
        
        for txn in transactions:
            txn_id = txn.get('activityId', '')
            txn_type = txn.get('type', 'UNKNOWN')
            status = txn.get('status', 'UNKNOWN')
            
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
                    'account_number': account_number,
                    'date': trade_date,
                    'settlement_date': settlement_date,
                    'type': txn_type,
                    'status': status,
                    'symbol': None,
                    'description': txn_type.replace('_', ' ').title(),
                    'quantity': 0,
                    'price': 0,
                    'amount': net_amount,
                    'fees': 0
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
                    
                    row = {
                        'transaction_id': txn_id,
                        'account_number': account_number,
                        'date': trade_date,
                        'settlement_date': settlement_date,
                        'type': txn_type,
                        'status': status,
                        'symbol': symbol,
                        'description': description,
                        'quantity': quantity,
                        'price': price,
                        'amount': cost * quantity if cost else price * quantity,
                        'fees': 0  # Schwab doesn't separate fees in API
                    }
                    rows.append(row)
        
        if not rows:
            logger.warning("No valid transactions found after transformation")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        logger.info(f"Transformed {len(df)} transactions")
        
        return df
    
    @staticmethod
    def transform_quotes(quotes_data: Dict) -> pd.DataFrame:
        """
        Transform Schwab quotes to market data format
        
        Args:
            quotes_data: Dictionary mapping symbols to quote data
            
        Returns:
            DataFrame with quote data
            
        Schwab Quote Format:
        {
            'AAPL': {
                'symbol': 'AAPL',
                'description': 'Apple Inc',
                'bidPrice': 149.50,
                'askPrice': 149.55,
                'lastPrice': 149.52,
                'mark': 149.525,
                'highPrice': 150.00,
                'lowPrice': 148.00,
                'openPrice': 148.50,
                'closePrice': 148.75,
                'totalVolume': 50000000,
                'netChange': 0.77,
                'netPercentChange': 0.52
            }
        }
        """
        if not quotes_data:
            logger.warning("No quotes data to transform")
            return pd.DataFrame()
        
        rows = []
        
        for symbol, quote in quotes_data.items():
            row = {
                'symbol': quote.get('symbol', symbol),
                'name': quote.get('description', ''),
                'last_price': quote.get('lastPrice', 0),
                'bid': quote.get('bidPrice', 0),
                'ask': quote.get('askPrice', 0),
                'open': quote.get('openPrice', 0),
                'high': quote.get('highPrice', 0),
                'low': quote.get('lowPrice', 0),
                'close': quote.get('closePrice', 0),
                'volume': quote.get('totalVolume', 0),
                'change': quote.get('netChange', 0),
                'change_percent': quote.get('netPercentChange', 0),
                'timestamp': datetime.now().isoformat()
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        logger.info(f"Transformed {len(df)} quotes")
        
        return df
    
    @staticmethod
    def merge_with_existing_portfolio(
        schwab_positions: pd.DataFrame,
        existing_portfolio: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge Schwab positions with existing portfolio data
        
        Args:
            schwab_positions: DataFrame with Schwab positions
            existing_portfolio: DataFrame with existing portfolio
            
        Returns:
            Merged DataFrame with source indicator
        """
        if schwab_positions.empty:
            return existing_portfolio
        
        if existing_portfolio.empty:
            schwab_positions['source'] = 'Schwab'
            return schwab_positions
        
        # Add source indicators
        schwab_positions = schwab_positions.copy()
        schwab_positions['source'] = 'Schwab'
        
        existing_portfolio = existing_portfolio.copy()
        if 'source' not in existing_portfolio.columns:
            existing_portfolio['source'] = 'Manual'
        
        # Concatenate
        merged = pd.concat([existing_portfolio, schwab_positions], ignore_index=True)
        
        logger.info(f"Merged portfolio: {len(existing_portfolio)} existing + {len(schwab_positions)} Schwab = {len(merged)} total")
        
        return merged
    
    @staticmethod
    def detect_account_type_from_number(account_number: str) -> str:
        """
        Attempt to detect account type from account number pattern
        
        Args:
            account_number: Schwab account number
            
        Returns:
            Detected account type
        """
        # Schwab account number patterns (approximate)
        # This is a simplified heuristic and may need adjustment
        
        if not account_number:
            return 'Brokerage'
        
        # IRA accounts often have specific prefixes
        # This is a placeholder - actual patterns may vary
        first_digit = account_number[0] if account_number else '0'
        
        if first_digit in ['4', '5']:
            return 'IRA'
        elif first_digit in ['6', '7']:
            return 'Roth IRA'
        else:
            return 'Brokerage'

# Made with Bob
