# Auto Scheduler Authentication Fix

## Problem Summary

The auto scheduler was throwing authentication errors when trying to sync SnapTrade accounts:

```
2026-04-09 09:41:47 - ERROR - get_accounts:312 - Failed to get accounts: (401)
Reason: Unauthorized
HTTP response body: {'detail': 'Invalid userID or userSecret provided', 'status_code': 401, 'code': '1083'}
```

## Root Cause

The issue occurred because:

1. **Background Thread Context**: The auto scheduler runs in a background thread that may not have access to environment variables
2. **Missing Credential Retrieval**: The `sync_orchestrator.py` was calling `get_holdings(user_id)` without passing the `user_secret` parameter
3. **Environment Variable Dependency**: The SnapTrade connector relied solely on environment variables (`SNAPTRADE_USER_SECRET`) which may not be accessible in background threads

## Solution

### 1. Enhanced Credential Manager (`components/credential_manager.py`)

Added two new methods to securely store and retrieve SnapTrade user credentials:

```python
def store_snaptrade_user(self, user_id: str, user_secret: str) -> bool:
    """Store SnapTrade user credentials in encrypted database."""
    
def get_snaptrade_user(self, user_id: str) -> Optional[dict]:
    """Retrieve SnapTrade user credentials from encrypted database."""
```

These methods:
- Store credentials in an encrypted SQLite database
- Use Fernet symmetric encryption (AES-128)
- Persist credentials across application restarts
- Are accessible from any thread context

### 2. Updated Sync Orchestrator (`components/sync_orchestrator.py`)

Modified `_sync_snaptrade()` method to retrieve credentials from multiple sources:

```python
def _sync_snaptrade(self, user_id: str) -> Dict[str, Any]:
    # 1. Try environment variable first
    user_secret = os.getenv("SNAPTRADE_USER_SECRET")
    
    # 2. Try credential manager if environment variable not available
    if not user_secret and hasattr(self.snaptrade_connector, 'credential_manager'):
        snaptrade_user = self.snaptrade_connector.credential_manager.get_snaptrade_user(user_id)
        if snaptrade_user:
            user_secret = snaptrade_user.get('user_secret')
    
    # 3. Pass user_secret to get_holdings()
    holdings_data = self.snaptrade_connector.get_holdings(user_id, user_secret=user_secret)
```

### 3. Updated SnapTrade Connector (`components/snaptrade_connector.py`)

Enhanced both `get_accounts()` and `get_holdings()` methods to:

1. **Retrieve credentials from multiple sources**:
   - Environment variables (primary)
   - Credential manager (fallback)

2. **Auto-store credentials**: When credentials are successfully used, they're automatically stored in the credential manager for future use

```python
# Store credentials in credential manager for future use
if user_secret and self.credential_manager:
    stored_user = self.credential_manager.get_snaptrade_user(user_id)
    if not stored_user:
        self.credential_manager.store_snaptrade_user(user_id, user_secret)
```

## How It Works

### First-Time Setup

1. User sets `SNAPTRADE_USER_SECRET` environment variable
2. User connects SnapTrade account through UI
3. Connector automatically stores credentials in credential manager
4. Credentials are now available for background scheduler

### Background Scheduler Execution

1. Scheduler triggers sync in background thread
2. Orchestrator calls `_sync_snaptrade(user_id)`
3. Orchestrator retrieves `user_secret` from credential manager
4. Orchestrator passes `user_secret` to connector methods
5. Sync completes successfully

### Credential Priority

The system checks for credentials in this order:

1. **Environment Variable** (`SNAPTRADE_USER_SECRET`) - Highest priority
2. **Credential Manager** (encrypted database) - Fallback
3. **Error** - If neither source has credentials

## Testing

Run the test script to verify the fix:

```bash
python test_auto_scheduler_fix.py
```

This will test:
- Credential storage and retrieval
- Orchestrator credential access
- Background thread compatibility

## Migration Guide

### For Existing Users

No action required! The system will automatically:

1. Continue using environment variables if set
2. Auto-store credentials on first successful sync
3. Use stored credentials for future background syncs

### For New Users

1. Set environment variables:
   ```bash
   export SNAPTRADE_CLIENT_ID="your_client_id"
   export SNAPTRADE_CONSUMER_KEY="your_consumer_key"
   export SNAPTRADE_USER_ID="your_user_id"
   export SNAPTRADE_USER_SECRET="your_user_secret"
   ```

2. Connect SnapTrade account through UI
3. Credentials are automatically stored
4. Auto-scheduler will work immediately

## Security Notes

- Credentials are encrypted using Fernet (AES-128)
- Encryption key must be set via `ENCRYPTION_KEY` environment variable
- Database file is stored in `data/credentials.db` (excluded from git)
- No plaintext credentials are stored anywhere

## Files Modified

1. `components/credential_manager.py` - Added SnapTrade credential storage
2. `components/sync_orchestrator.py` - Enhanced credential retrieval
3. `components/snaptrade_connector.py` - Auto-store credentials on use
4. `test_auto_scheduler_fix.py` - Test script (new)
5. `AUTO_SCHEDULER_FIX.md` - This documentation (new)

## Troubleshooting

### Error: "No user_secret found for user"

**Solution**: Ensure either:
- `SNAPTRADE_USER_SECRET` environment variable is set, OR
- Credentials were previously stored by connecting through the UI

### Error: "Encryption key not found"

**Solution**: Set the `ENCRYPTION_KEY` environment variable:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export ENCRYPTION_KEY="<generated_key>"
```

### Scheduler still failing

**Solution**: 
1. Stop the scheduler
2. Manually sync once through the UI (this stores credentials)
3. Restart the scheduler

## Future Enhancements

Potential improvements for future versions:

1. **UI for Credential Management**: Add UI to view/edit stored credentials
2. **Multi-User Support**: Better handling of multiple SnapTrade users
3. **Credential Rotation**: Automatic credential refresh/rotation
4. **Audit Logging**: Track when credentials are accessed
5. **Credential Expiry**: Add expiration dates for stored credentials

## Summary

This fix ensures the auto scheduler can reliably access SnapTrade credentials even when running in background threads. The solution is:

- ✅ **Secure**: Uses encrypted storage
- ✅ **Reliable**: Multiple credential sources with fallback
- ✅ **Automatic**: Auto-stores credentials on first use
- ✅ **Backward Compatible**: Works with existing environment variable setup
- ✅ **Thread-Safe**: Accessible from any thread context

The auto scheduler should now work without authentication errors!