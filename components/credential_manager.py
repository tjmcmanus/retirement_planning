"""
components/credential_manager.py
================================
Secure credential storage and encryption for brokerage connections.

Uses Fernet symmetric encryption to protect OAuth tokens and API credentials.
Stores encrypted data in local SQLite database.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet


class CredentialManager:
    """
    Manages encrypted storage of brokerage credentials.
    
    Security Features:
    - Fernet symmetric encryption (AES-128)
    - Encryption key from environment variable
    - No plaintext credentials in database
    - Automatic token expiry tracking
    """
    
    def __init__(self, db_path: str = "data/credentials.db", encryption_key: Optional[str] = None):
        """
        Initialize credential manager.
        
        Args:
            db_path: Path to SQLite database file
            encryption_key: Base64-encoded Fernet key (from environment if not provided)
        """
        self.db_path = db_path
        
        # Load .env file if it exists
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        # Get encryption key from environment or parameter
        key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "Encryption key not found. Set ENCRYPTION_KEY environment variable "
                "or generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        
        try:
            self.cipher = Fernet(key.encode())
        except Exception as e:
            raise ValueError(f"Invalid encryption key format: {e}")
        
        # Ensure database directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS brokerage_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    brokerage_name TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    encrypted_token TEXT NOT NULL,
                    encrypted_refresh_token TEXT,
                    token_expiry TIMESTAMP,
                    last_sync TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, brokerage_name, account_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id INTEGER NOT NULL,
                    sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    holdings_count INTEGER,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    FOREIGN KEY (connection_id) REFERENCES brokerage_connections(id)
                )
            """)
            
            conn.commit()
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not data:
            return ""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not encrypted_data:
            return ""
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {e}")
    
    def store_connection(
        self,
        brokerage_name: str,
        account_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expiry: Optional[datetime] = None,
        user_id: str = "default"
    ) -> int:
        """
        Store encrypted brokerage connection credentials.
        
        Args:
            brokerage_name: Name of brokerage (e.g., 'Schwab', 'Fidelity')
            account_id: Account identifier from brokerage
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            token_expiry: When access token expires
            user_id: User identifier (default: 'default')
        
        Returns:
            Connection ID
        """
        encrypted_token = self.encrypt(access_token)
        encrypted_refresh = self.encrypt(refresh_token) if refresh_token else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO brokerage_connections 
                (user_id, brokerage_name, account_id, encrypted_token, 
                 encrypted_refresh_token, token_expiry, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (user_id, brokerage_name, account_id, encrypted_token, 
                  encrypted_refresh, token_expiry))
            
            conn.commit()
            return cursor.lastrowid or 0
    
    def get_connection(self, connection_id: int) -> Optional[dict]:
        """
        Retrieve and decrypt connection credentials.
        
        Args:
            connection_id: Database connection ID
        
        Returns:
            Dictionary with decrypted credentials or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM brokerage_connections WHERE id = ? AND status = 'active'
            """, (connection_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row['id'],
                'user_id': row['user_id'],
                'brokerage_name': row['brokerage_name'],
                'account_id': row['account_id'],
                'access_token': self.decrypt(row['encrypted_token']),
                'refresh_token': self.decrypt(row['encrypted_refresh_token']) if row['encrypted_refresh_token'] else None,
                'token_expiry': datetime.fromisoformat(row['token_expiry']) if row['token_expiry'] else None,
                'last_sync': datetime.fromisoformat(row['last_sync']) if row['last_sync'] else None,
                'created_at': datetime.fromisoformat(row['created_at'])
            }
    
    def list_connections(self, user_id: str = "default") -> list[dict]:
        """
        List all active connections for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            List of connection dictionaries (without decrypted tokens)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, brokerage_name, account_id, token_expiry, 
                       last_sync, status, created_at
                FROM brokerage_connections 
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC
            """, (user_id,))
            
            connections = []
            for row in cursor.fetchall():
                connections.append({
                    'id': row['id'],
                    'brokerage_name': row['brokerage_name'],
                    'account_id': row['account_id'],
                    'token_expiry': datetime.fromisoformat(row['token_expiry']) if row['token_expiry'] else None,
                    'last_sync': datetime.fromisoformat(row['last_sync']) if row['last_sync'] else None,
                    'status': row['status'],
                    'created_at': datetime.fromisoformat(row['created_at']),
                    'is_expired': self._is_token_expired(row['token_expiry'])
                })
            
            return connections
    
    def update_sync_time(self, connection_id: int) -> None:
        """Update last sync timestamp for a connection."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE brokerage_connections 
                SET last_sync = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (connection_id,))
            conn.commit()
    
    def disconnect_account(self, connection_id: int) -> bool:
        """
        Disconnect (deactivate) a brokerage account.
        
        Args:
            connection_id: Database connection ID
        
        Returns:
            True if disconnected successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE brokerage_connections 
                SET status = 'disconnected' 
                WHERE id = ?
            """, (connection_id,))
            
            conn.commit()
            return cursor.rowcount > 0
    
    def log_sync_attempt(
        self,
        connection_id: int,
        status: str,
        holdings_count: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log a sync attempt to history.
        
        Args:
            connection_id: Database connection ID
            status: 'success', 'error', 'partial'
            holdings_count: Number of holdings synced
            error_message: Error details if status is 'error'
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sync_history 
                (connection_id, status, holdings_count, error_message)
                VALUES (?, ?, ?, ?)
            """, (connection_id, status, holdings_count, error_message))
            conn.commit()
    
    def get_sync_history(self, connection_id: int, limit: int = 10) -> list[dict]:
        """
        Get sync history for a connection.
        
        Args:
            connection_id: Database connection ID
            limit: Maximum number of records to return
        
        Returns:
            List of sync history records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM sync_history 
                WHERE connection_id = ? 
                ORDER BY sync_timestamp DESC 
                LIMIT ?
            """, (connection_id, limit))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'id': row['id'],
                    'sync_timestamp': datetime.fromisoformat(row['sync_timestamp']),
                    'status': row['status'],
                    'holdings_count': row['holdings_count'],
                    'error_message': row['error_message']
                })
            
            return history
    
    def _is_token_expired(self, token_expiry: Optional[str]) -> bool:
        """Check if token is expired."""
        if not token_expiry:
            return False
        
        expiry = datetime.fromisoformat(token_expiry)
        return datetime.now() >= expiry
    
    def refresh_token(self, connection_id: int, new_access_token: str, new_expiry: datetime) -> bool:
        """
        Update access token after refresh.
        
        Args:
            connection_id: Database connection ID
            new_access_token: New access token
            new_expiry: New expiry time
        
        Returns:
            True if updated successfully
        """
        encrypted_token = self.encrypt(new_access_token)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE brokerage_connections 
                SET encrypted_token = ?, token_expiry = ?
                WHERE id = ?
            """, (encrypted_token, new_expiry, connection_id))
            
            conn.commit()
            return cursor.rowcount > 0


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    # Generate encryption key for setup
    print("Generated encryption key:")
    print(generate_encryption_key())
    print("\nAdd this to your .env file as:")
    print("ENCRYPTION_KEY=<key_above>")

# Made with Bob
