"""
components/transaction_storage.py
==================================
Transaction data storage and management for portfolio tracking.

Handles:
- Transaction history storage in SQLite
- Cost basis tracking
- Tax lot management
- Transaction queries and reporting
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class TransactionStorage:
    """
    Manages transaction data storage and retrieval.
    
    Features:
    - SQLite database for transaction history
    - Cost basis tracking per symbol
    - Tax lot management
    - Transaction queries and filtering
    - Data integrity and validation
    """
    
    def __init__(self, db_path: str = "data/transactions.db"):
        """
        Initialize transaction storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Ensure database directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Transactions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    account_id TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    transaction_date DATE NOT NULL,
                    transaction_type TEXT NOT NULL,
                    symbol TEXT,
                    description TEXT,
                    quantity REAL,
                    price REAL,
                    amount REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    raw_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_user_account 
                ON transactions(user_id, account_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_date 
                ON transactions(transaction_date)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_symbol 
                ON transactions(symbol)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_type 
                ON transactions(transaction_type)
            """)
            
            # Tax lots table for cost basis tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tax_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    purchase_date DATE NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    cost_basis REAL NOT NULL,
                    remaining_quantity REAL NOT NULL,
                    transaction_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
                )
            """)
            
            # Create indexes for tax lots
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tax_lots_symbol 
                ON tax_lots(symbol, user_id, account_id)
            """)
            
            # Capital gains table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capital_gains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    sell_date DATE NOT NULL,
                    sell_transaction_id TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    proceeds REAL NOT NULL,
                    cost_basis REAL NOT NULL,
                    gain_loss REAL NOT NULL,
                    holding_period TEXT NOT NULL,
                    tax_year INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sell_transaction_id) REFERENCES transactions(transaction_id)
                )
            """)
            
            # Create index for capital gains
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_capital_gains_tax_year 
                ON capital_gains(tax_year, user_id)
            """)
            
            conn.commit()

    def backfill_account_names(self, user_id: str = "default") -> int:
        """
        Backfill blank transaction account names from account IDs.

        Args:
            user_id: User identifier

        Returns:
            Number of transactions updated
        """
        from components.credential_manager import CredentialManager

        cred_mgr = CredentialManager()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT id, account_id
                FROM transactions
                WHERE user_id = ?
                  AND (account_name IS NULL OR TRIM(account_name) = '')
                  AND account_id IS NOT NULL
                  AND TRIM(account_id) != ''
            """, (user_id,)).fetchall()

            updated_count = 0
            for row in rows:
                account_id = row['account_id']
                account_name = cred_mgr.get_schwab_account_name(account_id, user_id=user_id)
                if not account_name:
                    if account_id.startswith('Schwab'):
                        account_name = account_id
                    elif len(account_id) >= 4:
                        account_name = f"Schwab-{account_id[-4:]}"
                    else:
                        account_name = account_id

                conn.execute("""
                    UPDATE transactions
                    SET account_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (account_name, row['id']))
                updated_count += 1

            conn.commit()

        logger.info(f"Backfilled account names for {updated_count} transactions")
        return updated_count
    
    def store_transactions(
        self,
        transactions: pd.DataFrame,
        user_id: str = "default"
    ) -> int:
        """
        Store transactions in database.
        
        Args:
            transactions: DataFrame with transaction data
            user_id: User identifier
        
        Returns:
            Number of transactions stored
        """
        if len(transactions) == 0:
            return 0
        
        stored_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            for _, txn in transactions.iterrows():
                try:
                    # Convert date to string if it's a Timestamp
                    date_value = txn.get('date', '')
                    if hasattr(date_value, 'strftime'):
                        # It's a datetime/Timestamp object
                        date_value = date_value.strftime('%Y-%m-%d')
                    elif date_value and not isinstance(date_value, str):
                        # Try to convert to string
                        date_value = str(date_value)
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO transactions (
                            transaction_id, user_id, account_id, account_name,
                            account_type, transaction_date, transaction_type,
                            symbol, description, quantity, price, amount, fee, raw_data
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        txn.get('transaction_id', ''),
                        user_id,
                        txn.get('account_id', ''),
                        txn.get('account_name', ''),
                        txn.get('account_type', ''),
                        date_value,
                        txn.get('transaction_type', ''),
                        txn.get('symbol', ''),
                        txn.get('description', ''),
                        float(txn.get('quantity', 0)),
                        float(txn.get('price', 0)),
                        float(txn.get('amount', 0)),
                        float(txn.get('fee', 0)),
                        txn.get('raw_data', '')
                    ))
                    stored_count += 1
                except Exception as e:
                    logger.error(f"Failed to store transaction: {e}")
                    continue
            
            conn.commit()
        
        logger.info(f"Stored {stored_count} transactions")
        return stored_count
    
    def get_transactions(
        self,
        user_id: str = "default",
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        transaction_types: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Retrieve transactions from database.
        
        Args:
            user_id: User identifier
            account_id: Filter by account ID (optional)
            symbol: Filter by symbol (optional)
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
            transaction_types: Filter by transaction types (optional)
        
        Returns:
            DataFrame with transaction data
        """
        query = "SELECT * FROM transactions WHERE user_id = ?"
        params: List[Any] = [user_id]
        
        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)
        
        if transaction_types:
            placeholders = ','.join('?' * len(transaction_types))
            query += f" AND transaction_type IN ({placeholders})"
            params.extend(transaction_types)
        
        query += " ORDER BY transaction_date DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        # Convert date column to datetime
        if 'transaction_date' in df.columns and len(df) > 0:
            df['transaction_date'] = pd.to_datetime(df['transaction_date'])
        
        return df
    
    def store_tax_lot(
        self,
        user_id: str,
        account_id: str,
        symbol: str,
        purchase_date: str,
        quantity: float,
        price: float,
        transaction_id: Optional[str] = None
    ) -> int:
        """
        Store a tax lot for cost basis tracking.
        
        Args:
            user_id: User identifier
            account_id: Account ID
            symbol: Stock symbol
            purchase_date: Purchase date
            quantity: Number of shares
            price: Purchase price per share
            transaction_id: Related transaction ID (optional)
        
        Returns:
            Tax lot ID
        """
        cost_basis = quantity * price
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO tax_lots (
                    user_id, account_id, symbol, purchase_date,
                    quantity, price, cost_basis, remaining_quantity, transaction_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, account_id, symbol, purchase_date,
                quantity, price, cost_basis, quantity, transaction_id
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_tax_lots(
        self,
        user_id: str = "default",
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
        only_open: bool = True
    ) -> pd.DataFrame:
        """
        Retrieve tax lots from database.
        
        Args:
            user_id: User identifier
            account_id: Filter by account ID (optional)
            symbol: Filter by symbol (optional)
            only_open: Only return lots with remaining quantity > 0
        
        Returns:
            DataFrame with tax lot data
        """
        query = "SELECT * FROM tax_lots WHERE user_id = ?"
        params: List[Any] = [user_id]
        
        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if only_open:
            query += " AND remaining_quantity > 0"
        
        query += " ORDER BY purchase_date ASC"
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        return df
    
    def update_tax_lot_quantity(
        self,
        lot_id: int,
        quantity_sold: float
    ) -> bool:
        """
        Update remaining quantity for a tax lot after a sale.
        
        Args:
            lot_id: Tax lot ID
            quantity_sold: Quantity sold from this lot
        
        Returns:
            True if updated successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE tax_lots 
                    SET remaining_quantity = remaining_quantity - ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (quantity_sold, lot_id))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update tax lot: {e}")
            return False
    
    def store_capital_gain(
        self,
        user_id: str,
        account_id: str,
        symbol: str,
        sell_date: str,
        sell_transaction_id: str,
        quantity: float,
        proceeds: float,
        cost_basis: float,
        holding_period: str,
        tax_year: int
    ) -> int:
        """
        Store a capital gain/loss record.
        
        Args:
            user_id: User identifier
            account_id: Account ID
            symbol: Stock symbol
            sell_date: Sale date
            sell_transaction_id: Transaction ID of the sale
            quantity: Quantity sold
            proceeds: Sale proceeds
            cost_basis: Cost basis of shares sold
            holding_period: "short_term" or "long_term"
            tax_year: Tax year for reporting
        
        Returns:
            Capital gain record ID
        """
        gain_loss = proceeds - cost_basis
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO capital_gains (
                    user_id, account_id, symbol, sell_date, sell_transaction_id,
                    quantity, proceeds, cost_basis, gain_loss, holding_period, tax_year
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, account_id, symbol, sell_date, sell_transaction_id,
                quantity, proceeds, cost_basis, gain_loss, holding_period, tax_year
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_capital_gains(
        self,
        user_id: str = "default",
        tax_year: Optional[int] = None,
        account_id: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Retrieve capital gains records.
        
        Args:
            user_id: User identifier
            tax_year: Filter by tax year (optional)
            account_id: Filter by account ID (optional)
            symbol: Filter by symbol (optional)
        
        Returns:
            DataFrame with capital gains data
        """
        query = "SELECT * FROM capital_gains WHERE user_id = ?"
        params: List[Any] = [user_id]
        
        if tax_year:
            query += " AND tax_year = ?"
            params.append(tax_year)
        
        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        query += " ORDER BY sell_date DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        return df
    
    def get_transaction_summary(
        self,
        user_id: str = "default",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get summary statistics for transactions.
        
        Args:
            user_id: User identifier
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
        
        Returns:
            Dictionary with summary statistics
        """
        query = """
            SELECT 
                transaction_type,
                COUNT(*) as count,
                SUM(amount) as total_amount,
                AVG(amount) as avg_amount
            FROM transactions
            WHERE user_id = ?
        """
        params: List[Any] = [user_id]
        
        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)
        
        query += " GROUP BY transaction_type"
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        summary = {
            'by_type': df.to_dict('records') if len(df) > 0 else [],
            'total_transactions': int(df['count'].sum()) if len(df) > 0 else 0
        }
        
        return summary


def create_transaction_storage(db_path: str = "data/transactions.db") -> TransactionStorage:
    """
    Factory function to create TransactionStorage instance.
    
    Args:
        db_path: Path to SQLite database file
    
    Returns:
        Configured TransactionStorage instance
    """
    return TransactionStorage(db_path)


# Made with Bob