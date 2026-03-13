# SnapTrade Integration Plan
## Secure Brokerage Account Connection

### Overview
Integrate SnapTrade API to automatically sync portfolio data from brokerage accounts (Schwab, Fidelity, Vanguard, etc.) with encrypted credential storage.

---

## Phase 1: Setup & Authentication (Week 1)

### 1.1 Dependencies
```bash
pip install snaptrade-python cryptography python-dotenv
```

### 1.2 Environment Configuration
Create `.env` file (never commit to git):
```
SNAPTRADE_CLIENT_ID=your_client_id
SNAPTRADE_CONSUMER_KEY=your_consumer_key
ENCRYPTION_KEY=your_generated_encryption_key
```

### 1.3 Encryption Setup
- Use `cryptography.fernet` for symmetric encryption
- Store encryption key in environment variable
- Encrypt OAuth tokens and refresh tokens before storing
- Store encrypted credentials in local SQLite database

---

## Phase 2: SnapTrade Integration (Week 2)

### 2.1 Core Components

#### `components/snaptrade_connector.py`
- Initialize SnapTrade client
- Handle OAuth flow
- Manage connection lifecycle
- Sync account data

#### `components/credential_manager.py`
- Encrypt/decrypt credentials
- Store in local database
- Secure key management
- Credential rotation

#### `components/brokerage_sync.py`
- Fetch holdings from connected accounts
- Transform to portfolio_data_truth.csv format
- Handle incremental updates
- Reconcile with manual entries

### 2.2 Database Schema
```sql
CREATE TABLE brokerage_connections (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    brokerage_name TEXT,
    account_id TEXT,
    encrypted_token TEXT,
    encrypted_refresh_token TEXT,
    token_expiry TIMESTAMP,
    last_sync TIMESTAMP,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sync_history (
    id INTEGER PRIMARY KEY,
    connection_id INTEGER,
    sync_timestamp TIMESTAMP,
    holdings_count INTEGER,
    status TEXT,
    error_message TEXT,
    FOREIGN KEY (connection_id) REFERENCES brokerage_connections(id)
);
```

---

## Phase 3: UI Integration (Week 3)

### 3.1 Connections Tab UI
Located in: `pages/4_portfolio_hub.py` → Connections tab

Features:
- **Connect Account** button → OAuth flow
- **Connected Accounts** list with status indicators
- **Sync Now** button for manual sync
- **Disconnect** button with confirmation
- **Last Sync** timestamp display
- **Sync Schedule** configuration (daily/weekly)

### 3.2 Holdings Tab Integration
- Show source indicator (Manual vs Auto-synced)
- Allow manual overrides of synced data
- Conflict resolution UI for discrepancies

---

## Phase 4: Security Implementation (Week 4)

### 4.1 Encryption Strategy
```python
from cryptography.fernet import Fernet

class CredentialManager:
    def __init__(self, encryption_key: str):
        self.cipher = Fernet(encryption_key.encode())
    
    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        return self.cipher.decrypt(encrypted_data.encode()).decode()
```

### 4.2 Security Best Practices
- ✅ Never log decrypted credentials
- ✅ Use environment variables for keys
- ✅ Implement token rotation
- ✅ Add rate limiting for API calls
- ✅ Implement connection timeout
- ✅ Add audit logging for access
- ✅ Use read-only API permissions

---

## Phase 5: Data Sync Logic (Week 5)

### 5.1 Sync Flow
```
1. User clicks "Sync Now"
2. Retrieve encrypted credentials
3. Decrypt and authenticate with SnapTrade
4. Fetch holdings for all connected accounts
5. Transform to standard format
6. Compare with existing portfolio_data_truth.csv
7. Identify new/changed/removed holdings
8. Present changes to user for approval
9. Update portfolio_data_truth.csv
10. Log sync history
```

### 5.2 Data Transformation
```python
def transform_snaptrade_to_portfolio(snaptrade_holdings):
    """
    Transform SnapTrade holdings to portfolio_data_truth.csv format.
    
    SnapTrade format:
    {
        'symbol': 'AAPL',
        'quantity': 100,
        'price': 150.00,
        'account': {...}
    }
    
    Portfolio format:
    month, year, account_name, account_type, owner, symbol, name, 
    sector, qty, purchase_price, purchase_date
    """
    pass
```

---

## Phase 6: Error Handling & Monitoring (Week 6)

### 6.1 Error Scenarios
- Connection timeout
- Invalid credentials
- API rate limits
- Account locked/suspended
- Data format changes
- Network errors

### 6.2 Monitoring
- Sync success/failure rates
- API response times
- Token expiration alerts
- Data discrepancy alerts

---

## Implementation Priority

### Must Have (MVP)
1. ✅ Secure credential storage with encryption
2. ✅ OAuth connection flow
3. ✅ Basic holdings sync
4. ✅ Manual sync trigger
5. ✅ Disconnect functionality

### Should Have
6. ⏳ Automatic scheduled sync
7. ⏳ Conflict resolution UI
8. ⏳ Multiple account support
9. ⏳ Sync history view
10. ⏳ Transaction import

### Nice to Have
11. 📋 Real-time balance updates
12. 📋 Trade execution
13. 📋 Performance tracking per account
14. 📋 Cost basis tracking
15. 📋 Tax lot management

---

## Security Checklist

- [ ] Encryption key stored in environment variable
- [ ] Credentials encrypted at rest
- [ ] OAuth tokens encrypted
- [ ] No credentials in logs
- [ ] Read-only API permissions
- [ ] Token rotation implemented
- [ ] Audit logging enabled
- [ ] Rate limiting implemented
- [ ] Connection timeout configured
- [ ] Error messages don't expose sensitive data
- [ ] Database file permissions restricted
- [ ] .env file in .gitignore
- [ ] Encryption key rotation procedure documented

---

## Testing Strategy

### Unit Tests
- Encryption/decryption
- Data transformation
- Error handling
- Token refresh

### Integration Tests
- OAuth flow (sandbox)
- Holdings sync (sandbox)
- Conflict resolution
- Disconnect flow

### Security Tests
- Encryption strength
- Key management
- Token security
- SQL injection prevention

---

## Deployment Considerations

### Local Development
- Use SnapTrade sandbox environment
- Test with demo accounts
- Verify encryption works correctly

### Production
- Obtain production SnapTrade API keys
- Set up secure key management
- Implement monitoring and alerts
- Document user setup process
- Create troubleshooting guide

---

## Cost Analysis

### SnapTrade Pricing (as of 2026)
- **Free Tier**: Up to 5 connections
- **Pro Tier**: $10/month for unlimited connections
- **Enterprise**: Custom pricing for advanced features

### Recommendation
Start with Free Tier for testing, upgrade to Pro for production use.

---

## User Documentation

### Setup Guide
1. Sign up for SnapTrade account
2. Get API credentials
3. Add to .env file
4. Generate encryption key
5. Connect first brokerage account
6. Verify sync works correctly

### Troubleshooting
- Connection fails → Check credentials
- Sync fails → Check account status
- Data mismatch → Review conflict resolution
- Token expired → Reconnect account

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Set up SnapTrade sandbox** account
3. **Implement Phase 1** (Setup & Authentication)
4. **Test encryption** thoroughly
5. **Build OAuth flow** UI
6. **Implement basic sync**
7. **Add error handling**
8. **User testing** with sandbox
9. **Security audit**
10. **Production deployment**

---

## References

- SnapTrade API Docs: https://docs.snaptrade.com/
- SnapTrade Python SDK: https://github.com/passiv/snaptrade-python-sdk
- Cryptography Library: https://cryptography.io/
- OAuth 2.0 Spec: https://oauth.net/2/

---

**Status**: Planning Phase
**Target Completion**: 6 weeks
**Priority**: High (Phase 2 feature)
**Risk Level**: Medium (security-sensitive)