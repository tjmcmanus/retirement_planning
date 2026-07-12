"""
Transaction Import and Cost Basis Tracking
Handles transaction history import and cost basis calculations

Features:
- Transaction categorization and normalization
- Cost basis calculation (FIFO, LIFO, specific lot)
- Wash sale detection
- Tax lot management
- Performance attribution
- Tax reporting (1099-B reconciliation)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class CostBasisMethod(Enum):
    """Cost basis calculation methods."""
    FIFO = "FIFO"  # First In, First Out
    LIFO = "LIFO"  # Last In, First Out
    SPECIFIC_LOT = "SPECIFIC_LOT"  # User-specified lots
    AVERAGE_COST = "AVERAGE_COST"  # Average cost (mutual funds)


class TransactionType(Enum):
    """Standardized transaction types."""
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    STOCK_SPLIT = "STOCK_SPLIT"
    MERGER = "MERGER"
    SPINOFF = "SPINOFF"
    OPTION_BUY = "OPTION_BUY"
    OPTION_SELL = "OPTION_SELL"
    OPTION_EXERCISE = "OPTION_EXERCISE"
    OPTION_ASSIGNMENT = "OPTION_ASSIGNMENT"
    OPTION_EXPIRATION = "OPTION_EXPIRATION"
    FEE = "FEE"
    ADJUSTMENT = "ADJUSTMENT"


class TransactionImporter:
    """
    Imports and processes transaction history from brokerages.
    
    Features:
    - Transaction categorization
    - Cost basis calculation (FIFO, LIFO, specific lot)
    - Wash sale detection
    - Tax lot management
    - Performance attribution
    """
    
    def __init__(self, credential_manager, cost_basis_method: CostBasisMethod = CostBasisMethod.FIFO):
        """
        Initialize transaction importer.
        
        Args:
            credential_manager: Credential manager instance
            cost_basis_method: Method for cost basis calculation
        """
        self.credential_manager = credential_manager
        self.cost_basis_method = cost_basis_method
        self.tax_lots = {}  # Symbol -> List of lots
    
    def import_transactions(
        self,
        connector,
        user_id: str,
        user_secret: str,
        account_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Import transaction history from brokerage.
        
        Args:
            connector: SnapTrade or Schwab connector instance
            user_id: User identifier
            user_secret: User secret for authentication
            account_id: Account to import from
            start_date: Start date (YYYY-MM-DD), defaults to 1 year ago
            end_date: End date (YYYY-MM-DD), defaults to today
            
        Returns:
            DataFrame with standardized transaction data
        """
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        logger.info(f"Importing transactions from {start_date} to {end_date} for account {account_id}")
        
        try:
            if not hasattr(connector, 'get_transactions'):
                logger.error("Connector does not support transaction import")
                return pd.DataFrame()

            connector_class_name = connector.__class__.__name__
            if connector_class_name == 'SchwabConnector':
                raw_transactions = connector.get_transactions(
                    account_hash=account_id,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                raw_transactions = connector.get_transactions(
                    user_id=user_id,
                    user_secret=user_secret,
                    account_id=account_id,
                    start_date=start_date,
                    end_date=end_date
                )
            
            if not raw_transactions:
                logger.warning(f"No transactions found for account {account_id}")
                return pd.DataFrame()
            
            account_name = account_id
            if connector_class_name == 'SchwabConnector':
                account_name = self.credential_manager.get_schwab_account_name(account_id, user_id=user_id) or f"Schwab-{account_id[-4:]}"
            
            # Transform to standardized format
            transactions_df = self._transform_transactions(raw_transactions)
            if not transactions_df.empty:
                transactions_df['account_id'] = account_id
                transactions_df['account_name'] = account_name
            
            # Calculate cost basis
            transactions_df = self._calculate_cost_basis(transactions_df)
            
            # Detect wash sales
            transactions_df = self._detect_wash_sales(transactions_df)
            
            logger.info(f"Successfully imported {len(transactions_df)} transactions")
            return transactions_df
            
        except Exception as e:
            logger.error(f"Failed to import transactions: {e}", exc_info=True)
            return pd.DataFrame()
    
    def _transform_transactions(self, raw_transactions: List[Dict]) -> pd.DataFrame:
        """
        Transform raw transaction data to standardized format.
        
        Standardized columns:
        - transaction_id: Unique identifier
        - date: Transaction date
        - type: Transaction type (BUY, SELL, DIVIDEND, etc.)
        - symbol: Security symbol
        - quantity: Number of shares/units
        - price: Price per share
        - amount: Total transaction amount
        - fees: Transaction fees
        - currency: Transaction currency
        - description: Transaction description
        """
        transactions = []
        
        for txn in raw_transactions:
            try:
                # Extract common fields with safe defaults
                transaction = {
                    'transaction_id': str(txn.get('id', txn.get('activityId', ''))),
                    'date': txn.get('date', txn.get('tradeDate', '')),
                    'type': self._normalize_transaction_type(txn.get('type', txn.get('activityType', ''))),
                    'symbol': txn.get('symbol', ''),
                    'quantity': float(txn.get('quantity', txn.get('amount', 0))),
                    'price': float(txn.get('price', 0)),
                    'amount': float(txn.get('amount', txn.get('netAmount', 0))),
                    'fees': float(txn.get('fees', txn.get('commission', 0))),
                    'currency': txn.get('currency', 'USD'),
                    'description': txn.get('description', txn.get('activityDescription', ''))
                }
                
                transactions.append(transaction)
                
            except Exception as e:
                logger.warning(f"Failed to transform transaction {txn.get('id', 'unknown')}: {e}")
                continue
        
        if not transactions:
            return pd.DataFrame()
        
        df = pd.DataFrame(transactions)
        
        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Remove rows with invalid dates
        df = df.dropna(subset=['date'])
        
        # Sort by date
        df = df.sort_values('date').reset_index(drop=True)
        
        logger.info(f"Transformed {len(df)} transactions")
        return df
    
    def _normalize_transaction_type(self, raw_type: str) -> str:
        """Normalize transaction type to standard categories."""
        if not raw_type:
            return TransactionType.ADJUSTMENT.value
        
        raw_type_lower = raw_type.lower().strip()
        
        # Transaction type mapping
        type_mapping = {
            # Buy transactions
            'buy': TransactionType.BUY,
            'purchase': TransactionType.BUY,
            'buy to open': TransactionType.BUY,
            'bought': TransactionType.BUY,
            
            # Sell transactions
            'sell': TransactionType.SELL,
            'sale': TransactionType.SELL,
            'sell to close': TransactionType.SELL,
            'sold': TransactionType.SELL,
            
            # Income
            'dividend': TransactionType.DIVIDEND,
            'div': TransactionType.DIVIDEND,
            'cash dividend': TransactionType.DIVIDEND,
            'interest': TransactionType.INTEREST,
            'int': TransactionType.INTEREST,
            
            # Transfers
            'deposit': TransactionType.DEPOSIT,
            'cash deposit': TransactionType.DEPOSIT,
            'withdrawal': TransactionType.WITHDRAWAL,
            'cash withdrawal': TransactionType.WITHDRAWAL,
            'transfer in': TransactionType.TRANSFER_IN,
            'transfer out': TransactionType.TRANSFER_OUT,
            'journal': TransactionType.TRANSFER_IN,
            
            # Corporate actions
            'split': TransactionType.STOCK_SPLIT,
            'stock split': TransactionType.STOCK_SPLIT,
            'merger': TransactionType.MERGER,
            'spinoff': TransactionType.SPINOFF,
            'spin-off': TransactionType.SPINOFF,
            
            # Options
            'option buy': TransactionType.OPTION_BUY,
            'option sell': TransactionType.OPTION_SELL,
            'option exercise': TransactionType.OPTION_EXERCISE,
            'option assignment': TransactionType.OPTION_ASSIGNMENT,
            'option expiration': TransactionType.OPTION_EXPIRATION,
            'expired': TransactionType.OPTION_EXPIRATION,
            
            # Other
            'fee': TransactionType.FEE,
            'commission': TransactionType.FEE,
            'adjustment': TransactionType.ADJUSTMENT,
            'adj': TransactionType.ADJUSTMENT
        }
        
        # Try exact match first
        if raw_type_lower in type_mapping:
            return type_mapping[raw_type_lower].value
        
        # Try partial match
        for key, value in type_mapping.items():
            if key in raw_type_lower:
                return value.value
        
        # Default to adjustment if unknown
        logger.warning(f"Unknown transaction type: {raw_type}, defaulting to ADJUSTMENT")
        return TransactionType.ADJUSTMENT.value
    
    def _calculate_cost_basis(self, transactions_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate cost basis for each transaction using specified method.
        
        Adds columns:
        - cost_basis: Cost basis per share
        - total_cost_basis: Total cost basis
        - gain_loss: Realized gain/loss (for sells)
        - holding_period: Days held (for sells)
        - term: SHORT or LONG (for sells)
        """
        if transactions_df.empty:
            return transactions_df
        
        # Initialize new columns
        transactions_df['cost_basis'] = 0.0
        transactions_df['total_cost_basis'] = 0.0
        transactions_df['gain_loss'] = 0.0
        transactions_df['holding_period'] = 0
        transactions_df['term'] = ''
        
        # Group by symbol for lot tracking
        symbols = transactions_df['symbol'].unique()
        
        for symbol in symbols:
            if not symbol:  # Skip empty symbols
                continue
                
            symbol_txns = transactions_df[transactions_df['symbol'] == symbol].copy()
            
            # Track lots (purchases) for this symbol
            lots = []
            
            for idx, txn in symbol_txns.iterrows():
                txn_type = txn['type']
                
                if txn_type == TransactionType.BUY.value:
                    # Add to lots
                    lot = {
                        'date': txn['date'],
                        'quantity': txn['quantity'],
                        'price': txn['price'],
                        'remaining': txn['quantity'],
                        'fees': txn['fees']
                    }
                    lots.append(lot)
                    
                    # Set cost basis for buy (including fees)
                    cost_per_share = txn['price'] + (txn['fees'] / txn['quantity'] if txn['quantity'] > 0 else 0)
                    transactions_df.at[idx, 'cost_basis'] = cost_per_share
                    transactions_df.at[idx, 'total_cost_basis'] = txn['price'] * txn['quantity'] + txn['fees']
                
                elif txn_type == TransactionType.SELL.value:
                    # Calculate gain/loss using specified method
                    result = self._calculate_sell_gain_loss(
                        lots=lots,
                        sell_quantity=txn['quantity'],
                        sell_price=txn['price'],
                        sell_date=txn['date'],
                        sell_fees=txn['fees']
                    )
                    
                    # Update transaction
                    transactions_df.at[idx, 'cost_basis'] = result['avg_cost_basis']
                    transactions_df.at[idx, 'total_cost_basis'] = result['total_cost']
                    transactions_df.at[idx, 'gain_loss'] = result['gain_loss']
                    transactions_df.at[idx, 'holding_period'] = result['holding_period']
                    transactions_df.at[idx, 'term'] = result['term']
        
        return transactions_df
    
    def _calculate_sell_gain_loss(
        self,
        lots: List[Dict],
        sell_quantity: float,
        sell_price: float,
        sell_date: datetime,
        sell_fees: float
    ) -> Dict:
        """
        Calculate gain/loss for a sell transaction using specified cost basis method.
        
        Returns:
            Dictionary with cost basis, gain/loss, holding period, and term
        """
        if not lots or sell_quantity <= 0:
            return {
                'avg_cost_basis': 0.0,
                'total_cost': 0.0,
                'gain_loss': 0.0,
                'holding_period': 0,
                'term': 'UNKNOWN'
            }
        
        quantity_to_sell = sell_quantity
        total_cost = 0.0
        total_days = 0
        lots_used = 0
        
        # Sort lots based on method
        if self.cost_basis_method == CostBasisMethod.FIFO:
            # Use oldest lots first (already in order)
            sorted_lots = lots
        elif self.cost_basis_method == CostBasisMethod.LIFO:
            # Use newest lots first
            sorted_lots = sorted(lots, key=lambda x: x['date'], reverse=True)
        else:
            # Default to FIFO
            sorted_lots = lots
        
        # Calculate cost basis
        for lot in sorted_lots:
            if quantity_to_sell <= 0:
                break
            
            if lot['remaining'] <= 0:
                continue
            
            # Determine quantity to use from this lot
            qty_from_lot = min(lot['remaining'], quantity_to_sell)
            
            # Calculate cost from this lot (including proportional fees)
            cost_from_lot = qty_from_lot * lot['price']
            if lot['quantity'] > 0:
                cost_from_lot += (qty_from_lot / lot['quantity']) * lot['fees']
            
            total_cost += cost_from_lot
            
            # Calculate holding period
            days_held = (sell_date - lot['date']).days
            total_days += days_held * qty_from_lot
            lots_used += 1
            
            # Update lot
            lot['remaining'] -= qty_from_lot
            quantity_to_sell -= qty_from_lot
        
        # Calculate metrics
        avg_cost_basis = total_cost / sell_quantity if sell_quantity > 0 else 0
        proceeds = sell_price * sell_quantity - sell_fees
        gain_loss = proceeds - total_cost
        
        # Calculate weighted average holding period
        avg_holding_period = int(total_days / sell_quantity) if sell_quantity > 0 else 0
        term = 'LONG' if avg_holding_period > 365 else 'SHORT'
        
        return {
            'avg_cost_basis': avg_cost_basis,
            'total_cost': total_cost,
            'gain_loss': gain_loss,
            'holding_period': avg_holding_period,
            'term': term
        }
    
    def _detect_wash_sales(self, transactions_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect wash sales (selling at a loss and repurchasing within 30 days).
        
        IRS Wash Sale Rule: If you sell a security at a loss and buy substantially
        identical security within 30 days before or after the sale, the loss is disallowed.
        
        Adds columns:
        - wash_sale: Boolean indicating if transaction is a wash sale
        - wash_sale_adjustment: Amount of loss disallowed
        """
        if transactions_df.empty:
            return transactions_df
        
        transactions_df['wash_sale'] = False
        transactions_df['wash_sale_adjustment'] = 0.0
        
        # Group by symbol
        for symbol in transactions_df['symbol'].unique():
            if not symbol:
                continue
            
            symbol_txns = transactions_df[transactions_df['symbol'] == symbol].copy()
            
            # Find sells with losses
            sells_with_loss = symbol_txns[
                (symbol_txns['type'] == TransactionType.SELL.value) & 
                (symbol_txns['gain_loss'] < 0)
            ]
            
            for idx, sell_txn in sells_with_loss.iterrows():
                # Check for purchases within 30 days before or after
                wash_sale_window_start = sell_txn['date'] - timedelta(days=30)
                wash_sale_window_end = sell_txn['date'] + timedelta(days=30)
                
                purchases_in_window = symbol_txns[
                    (symbol_txns['type'] == TransactionType.BUY.value) &
                    (symbol_txns['date'] >= wash_sale_window_start) &
                    (symbol_txns['date'] <= wash_sale_window_end) &
                    (symbol_txns['date'] != sell_txn['date'])
                ]
                
                if not purchases_in_window.empty:
                    # Wash sale detected
                    transactions_df.at[idx, 'wash_sale'] = True
                    transactions_df.at[idx, 'wash_sale_adjustment'] = abs(sell_txn['gain_loss'])
                    
                    logger.info(f"Wash sale detected for {symbol} on {sell_txn['date'].strftime('%Y-%m-%d')}: ${abs(sell_txn['gain_loss']):.2f} loss disallowed")
        
        return transactions_df
    
    def generate_tax_report(
        self,
        transactions_df: pd.DataFrame,
        tax_year: int
    ) -> Dict:
        """
        Generate tax report for specified year.
        
        Returns:
            Dictionary with tax reporting data:
            - short_term_gains: Total short-term capital gains
            - long_term_gains: Total long-term capital gains
            - dividend_income: Total dividend income
            - qualified_dividends: Qualified dividend income (estimated)
            - interest_income: Total interest income
            - wash_sale_adjustments: Total wash sale adjustments
            - net_capital_gains: Net capital gains after wash sales
        """
        if transactions_df.empty:
            return self._empty_tax_report(tax_year)
        
        # Filter to tax year
        year_txns = transactions_df[
            transactions_df['date'].dt.year == tax_year
        ].copy()
        
        if year_txns.empty:
            return self._empty_tax_report(tax_year)
        
        # Calculate capital gains
        sells = year_txns[year_txns['type'] == TransactionType.SELL.value]
        short_term = sells[sells['term'] == 'SHORT']['gain_loss'].sum()
        long_term = sells[sells['term'] == 'LONG']['gain_loss'].sum()
        
        # Calculate income
        dividends = year_txns[year_txns['type'] == TransactionType.DIVIDEND.value]['amount'].sum()
        interest = year_txns[year_txns['type'] == TransactionType.INTEREST.value]['amount'].sum()
        
        # Wash sale adjustments
        wash_sales = year_txns[year_txns['wash_sale'] == True]['wash_sale_adjustment'].sum()
        
        # Estimate qualified dividends (typically 80-90% of total dividends)
        # This should ideally come from transaction data
        qualified_dividends = dividends * 0.85
        
        return {
            'tax_year': tax_year,
            'short_term_gains': round(short_term, 2),
            'long_term_gains': round(long_term, 2),
            'total_capital_gains': round(short_term + long_term, 2),
            'dividend_income': round(dividends, 2),
            'qualified_dividends': round(qualified_dividends, 2),
            'ordinary_dividends': round(dividends - qualified_dividends, 2),
            'interest_income': round(interest, 2),
            'wash_sale_adjustments': round(wash_sales, 2),
            'net_capital_gains': round(short_term + long_term - wash_sales, 2),
            'total_transactions': len(year_txns),
            'sell_transactions': len(sells)
        }
    
    def _empty_tax_report(self, tax_year: int) -> Dict:
        """Return empty tax report structure."""
        return {
            'tax_year': tax_year,
            'short_term_gains': 0.0,
            'long_term_gains': 0.0,
            'total_capital_gains': 0.0,
            'dividend_income': 0.0,
            'qualified_dividends': 0.0,
            'ordinary_dividends': 0.0,
            'interest_income': 0.0,
            'wash_sale_adjustments': 0.0,
            'net_capital_gains': 0.0,
            'total_transactions': 0,
            'sell_transactions': 0
        }
    
    def export_to_csv(self, transactions_df: pd.DataFrame, filename: str) -> bool:
        """
        Export transactions to CSV file.
        
        Args:
            transactions_df: Transactions DataFrame
            filename: Output filename
            
        Returns:
            True if successful
        """
        try:
            # Format dates for export
            export_df = transactions_df.copy()
            export_df['date'] = export_df['date'].dt.strftime('%Y-%m-%d')
            
            # Round numeric columns
            numeric_cols = ['quantity', 'price', 'amount', 'fees', 'cost_basis', 
                          'total_cost_basis', 'gain_loss', 'wash_sale_adjustment']
            for col in numeric_cols:
                if col in export_df.columns:
                    export_df[col] = export_df[col].round(2)
            
            # Export
            export_df.to_csv(filename, index=False)
            logger.info(f"Exported {len(export_df)} transactions to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export transactions: {e}")
            return False


# Helper function for UI integration
def import_and_display_transactions(
    connector,
    user_id: str,
    user_secret: str,
    account_id: str,
    credential_manager,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Import transactions and return formatted DataFrame for display.
    
    Args:
        connector: SnapTrade or Schwab connector instance
        user_id: User identifier
        user_secret: User secret
        account_id: Account ID
        credential_manager: Credential manager instance
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        
    Returns:
        Formatted DataFrame for display
    """
    importer = TransactionImporter(credential_manager)
    
    transactions_df = importer.import_transactions(
        connector=connector,
        user_id=user_id,
        user_secret=user_secret,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if not transactions_df.empty:
        # Format for display
        display_df = transactions_df[[
            'date', 'type', 'symbol', 'quantity', 'price', 
            'amount', 'gain_loss', 'term', 'wash_sale'
        ]].copy()
        
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        display_df['quantity'] = display_df['quantity'].apply(lambda x: f"{x:.4f}")
        display_df['price'] = display_df['price'].apply(lambda x: f"${x:,.2f}")
        display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:,.2f}")
        display_df['gain_loss'] = display_df['gain_loss'].apply(
            lambda x: f"${x:,.2f}" if x != 0 else "-"
        )
        display_df['wash_sale'] = display_df['wash_sale'].apply(lambda x: "⚠️ Yes" if x else "")
        
        return display_df
    
    return pd.DataFrame()

# Made with Bob
