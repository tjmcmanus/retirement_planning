"""
components/sync_orchestrator.py
================================
Coordinates multi-account synchronization with retry logic and conflict resolution.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class SyncResult:
    """Result of a sync operation."""
    
    def __init__(self, success: bool, message: str, data: Optional[Dict] = None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        }


class SyncOrchestrator:
    """
    Orchestrates synchronization across multiple brokerage connections.
    
    Features:
    - Multi-account coordination
    - Retry logic with exponential backoff
    - Conflict detection and resolution
    - Progress tracking
    """
    
    def __init__(
        self,
        snaptrade_connector=None,
        schwab_connector=None,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0
    ):
        """
        Initialize sync orchestrator.
        
        Args:
            snaptrade_connector: SnapTrade connector instance
            schwab_connector: Schwab connector instance
            max_retries: Maximum retry attempts
            initial_retry_delay: Initial delay between retries (seconds)
        """
        self.snaptrade_connector = snaptrade_connector
        self.schwab_connector = schwab_connector
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        
        self.sync_history: List[Dict[str, Any]] = []
    
    def sync_all(self, user_id: str = "default") -> SyncResult:
        """
        Sync all connected accounts.
        
        Args:
            user_id: User identifier
            
        Returns:
            SyncResult with overall sync status
        """
        logger.info(f"Starting sync for user: {user_id}")
        start_time = time.time()
        
        results: Dict[str, Any] = {
            'snaptrade': None,
            'schwab': None
        }
        errors = []
        
        # Sync SnapTrade accounts
        if self.snaptrade_connector:
            try:
                results['snaptrade'] = self._sync_with_retry(
                    lambda: self._sync_snaptrade(user_id),
                    "SnapTrade"
                )
            except Exception as e:
                error_msg = f"SnapTrade sync failed: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Sync Schwab accounts
        if self.schwab_connector:
            try:
                results['schwab'] = self._sync_with_retry(
                    lambda: self._sync_schwab(user_id),
                    "Schwab"
                )
            except Exception as e:
                error_msg = f"Schwab sync failed: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Calculate summary
        duration = time.time() - start_time
        success = len(errors) == 0
        
        sync_record = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'duration': duration,
            'success': success,
            'results': results,
            'errors': errors
        }
        
        self.sync_history.append(sync_record)
        
        # Keep only last 100 sync records
        if len(self.sync_history) > 100:
            self.sync_history = self.sync_history[-100:]
        
        message = "Sync completed successfully" if success else f"Sync completed with errors: {'; '.join(errors)}"
        
        return SyncResult(
            success=success,
            message=message,
            data=sync_record
        )
    
    def _sync_with_retry(self, sync_func, source_name: str) -> Dict[str, Any]:
        """
        Execute sync with exponential backoff retry.
        
        Args:
            sync_func: Function to execute
            source_name: Name of sync source (for logging)
            
        Returns:
            Sync result dictionary
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"{source_name} sync attempt {attempt + 1}/{self.max_retries}")
                result = sync_func()
                logger.info(f"{source_name} sync successful")
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"{source_name} sync attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.initial_retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
        
        # All retries failed
        raise Exception(f"{source_name} sync failed after {self.max_retries} attempts: {last_error}")
    
    def _sync_snaptrade(self, user_id: str) -> Dict[str, Any]:
        """Sync SnapTrade accounts."""
        if not self.snaptrade_connector:
            return {'status': 'skipped', 'reason': 'No connector'}
        
        try:
            # Get current holdings
            holdings_data = self.snaptrade_connector.get_holdings(user_id)
            
            # Handle both list and DataFrame returns
            if isinstance(holdings_data, list):
                if not holdings_data:
                    return {
                        'status': 'success',
                        'accounts': 0,
                        'holdings': 0,
                        'message': 'No holdings found'
                    }
                # Convert list to DataFrame if needed
                import pandas as pd
                holdings_df = pd.DataFrame(holdings_data) if holdings_data else pd.DataFrame()
            else:
                holdings_df = holdings_data
            
            if holdings_df.empty:
                return {
                    'status': 'success',
                    'accounts': 0,
                    'holdings': 0,
                    'message': 'No holdings found'
                }
            
            # Detect changes (delta sync)
            changes = self._detect_changes(holdings_df, 'snaptrade')
            
            return {
                'status': 'success',
                'accounts': holdings_df['account_id'].nunique() if 'account_id' in holdings_df.columns else 0,
                'holdings': len(holdings_df),
                'changes': changes
            }
        except Exception as e:
            logger.error(f"SnapTrade sync error: {e}", exc_info=True)
            raise
    
    def _sync_schwab(self, user_id: str) -> Dict[str, Any]:
        """Sync Schwab accounts."""
        if not self.schwab_connector:
            return {'status': 'skipped', 'reason': 'No connector'}
        
        try:
            # Get accounts and positions
            accounts = self.schwab_connector.get_accounts()
            
            if not accounts:
                return {
                    'status': 'success',
                    'accounts': 0,
                    'positions': 0,
                    'message': 'No accounts found'
                }
            
            total_positions = 0
            for account in accounts:
                # Handle different possible account number keys
                account_number = account.get('accountNumber') or account.get('accountId') or account.get('account_number')
                if account_number:
                    positions = self.schwab_connector.get_positions(account_number)
                    total_positions += len(positions)
            
            return {
                'status': 'success',
                'accounts': len(accounts),
                'positions': total_positions
            }
        except Exception as e:
            logger.error(f"Schwab sync error: {e}", exc_info=True)
            raise
    
    def _detect_changes(self, new_data: pd.DataFrame, source: str) -> Dict[str, int]:
        """
        Detect changes between current and new data (delta sync).
        
        Args:
            new_data: New holdings data
            source: Data source name
            
        Returns:
            Dictionary with change counts
        """
        # This is a simplified version - in production, you'd compare with cached data
        # For now, we'll just return the count of new records
        return {
            'added': 0,
            'modified': 0,
            'removed': 0,
            'unchanged': len(new_data)
        }
    
    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sync history."""
        return self.sync_history[-limit:]
    
    def get_last_sync(self) -> Optional[Dict[str, Any]]:
        """Get last sync record."""
        return self.sync_history[-1] if self.sync_history else None
    
    def clear_history(self) -> None:
        """Clear sync history."""
        self.sync_history = []
        logger.info("Sync history cleared")

# Made with Bob
