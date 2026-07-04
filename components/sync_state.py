"""
components/sync_state.py
========================
Manages sync state persistence and conflict detection.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class SyncState:
    """Manages synchronization state and conflict detection."""
    
    def __init__(self, state_file: str = "data/sync_state.json"):
        """
        Initialize sync state manager.
        
        Args:
            state_file: Path to state file
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load sync state: {e}")
        
        return {
            'last_sync': None,
            'holdings_hash': None,
            'accounts': {},
            'sync_count': 0
        }
    
    def _save_state(self) -> None:
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")
    
    def update_sync_time(self) -> None:
        """Update last sync timestamp."""
        self.state['last_sync'] = datetime.now().isoformat()
        self.state['sync_count'] = self.state.get('sync_count', 0) + 1
        self._save_state()
    
    def get_last_sync(self) -> Optional[datetime]:
        """Get last sync timestamp."""
        if self.state['last_sync']:
            try:
                return datetime.fromisoformat(self.state['last_sync'])
            except ValueError:
                logger.debug("Could not parse last_sync timestamp %r", self.state['last_sync'])
                return None
        return None
    
    def get_sync_count(self) -> int:
        """Get total number of syncs performed."""
        return self.state.get('sync_count', 0)
    
    def detect_conflicts(self, new_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect conflicts between cached and new data.
        
        Args:
            new_data: New holdings data
            
        Returns:
            Dictionary with conflict information
        """
        # Calculate hash of new data
        try:
            # Use pandas hash_pandas_object if available
            import pandas.util as pd_util
            new_hash = int(pd_util.hash_pandas_object(new_data).sum())
        except AttributeError:
            # Fallback to simple hash if pandas util API unavailable
            logger.debug("hash_pandas_object unavailable, falling back to str hash")
            new_hash = hash(str(new_data.to_dict()))
        
        old_hash = self.state.get('holdings_hash')
        
        conflicts = {
            'has_conflicts': False,
            'changed': old_hash != new_hash if old_hash else False,
            'details': []
        }
        
        # Update hash
        self.state['holdings_hash'] = new_hash
        self._save_state()
        
        return conflicts
    
    def update_account_state(self, account_id: str, data: Dict[str, Any]) -> None:
        """
        Update state for a specific account.
        
        Args:
            account_id: Account identifier
            data: Account state data
        """
        if 'accounts' not in self.state:
            self.state['accounts'] = {}
        
        self.state['accounts'][account_id] = {
            **data,
            'last_updated': datetime.now().isoformat()
        }
        self._save_state()
    
    def get_account_state(self, account_id: str) -> Optional[Dict[str, Any]]:
        """
        Get state for a specific account.
        
        Args:
            account_id: Account identifier
            
        Returns:
            Account state data or None
        """
        return self.state.get('accounts', {}).get(account_id)
    
    def clear_state(self) -> None:
        """Clear all state data."""
        self.state = {
            'last_sync': None,
            'holdings_hash': None,
            'accounts': {},
            'sync_count': 0
        }
        self._save_state()
        logger.info("Sync state cleared")
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of current state."""
        last_sync = self.get_last_sync()
        
        return {
            'last_sync': last_sync.isoformat() if last_sync else None,
            'sync_count': self.get_sync_count(),
            'accounts_tracked': len(self.state.get('accounts', {})),
            'has_cached_data': self.state.get('holdings_hash') is not None
        }

# Made with Bob
