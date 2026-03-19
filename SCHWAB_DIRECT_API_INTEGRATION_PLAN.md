# Schwab Direct API Integration Plan

## Overview
Implement direct integration with Charles Schwab API using your developer API keys, bypassing SnapTrade for better reliability and more features.

**Status**: 📋 Planning Phase
**Priority**: High (User Request)
**Estimated Time**: 2-3 weeks

---

## Why Direct Schwab API?

### Advantages:
✅ **More Reliable** - Direct connection, no intermediary
✅ **More Features** - Full access to Schwab's API capabilities
✅ **Real-Time Data** - Live quotes and positions
✅ **Transaction History** - Complete transaction records
✅ **Trade Execution** - Can place trades (if desired)
✅ **No Additional Cost** - Free with Schwab developer account

### Disadvantages:
❌ **Single Brokerage** - Only works with Schwab
❌ **More Maintenance** - Need to handle API changes
❌ **OAuth Complexity** - Must implement OAuth 2.0 flow

---

## Schwab API Capabilities

### Available Endpoints:

**Account Information:**
- Get account numbers
- Get account details
- Get account positions
- Get account balances

**Market Data:**
- Get quotes (real-time)
- Get price history
- Get option chains
- Get market hours

**Trading:**
- Place orders
- Get order status
- Cancel orders
- Get order history

**Transactions:**
- Get transaction history
- Get transaction details

---

## Implementation Plan

### Phase 1: Setup & Authentication (Week 1)

#### 1.1 Prerequisites
```bash
# Install Schwab SDK
pip install schwab-py

# Or use requests library for direct API calls
pip install requests oauthlib
```

#### 1.2 Environment Configuration
Add to `.env`:
```bash
# Schwab API Credentials
SCHWAB_APP_KEY=your_app_key
SCHWAB_APP_SECRET=your_app_secret
SCHWAB_CALLBACK_URL=https://localhost:8080/callback

# Optional: Refresh token (after first auth)
SCHWAB_REFRESH_TOKEN=your_refresh_token
```

#### 1.3 OAuth 2.0 Flow
Schwab uses OAuth 2.0 with PKCE (Proof Key for Code Exchange):
1. Generate authorization URL
2. User authorizes in browser
3. Receive authorization code
4. Exchange code for access token
5. Store refresh token for future use

### Phase 2: Core Integration (Week 2)

#### 2.1 Create Schwab Connector
**File**: `components/schwab_connector.py`

```python
"""
Schwab API Direct Integration
Handles authentication, account data, and transactions
"""

class SchwabConnector:
    def __init__(self, app_key: str, app_secret: str, callback_url: str):
        """Initialize Schwab API connector"""
        
    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL"""
        
    def authenticate(self, auth_code: str) -> dict:
        """Exchange auth code for tokens"""
        
    def refresh_access_token(self) -> bool:
        """Refresh expired access token"""
        
    def get_accounts(self) -> list:
        """Get all linked accounts"""
        
    def get_account_positions(self, account_id: str) -> list:
        """Get positions for specific account"""
        
    def get_transactions(self, account_id: str, 
                        start_date: str, end_date: str) -> list:
        """Get transaction history"""
        
    def get_quotes(self, symbols: list) -> dict:
        """Get real-time quotes"""
```

#### 2.2 Data Transformation
Transform Schwab data to match portfolio format:

```python
def transform_schwab_positions(positions: list) -> pd.DataFrame:
    """
    Transform Schwab positions to portfolio format
    
    Schwab Format:
    {
        'instrument': {
            'symbol': 'AAPL',
            'description': 'Apple Inc',
            'assetType': 'EQUITY'
        },
        'longQuantity': 100,
        'averagePrice': 150.00,
        'currentDayProfitLoss': 50.00,
        'marketValue': 15500.00
    }
    
    Portfolio Format:
    month, year, account_name, account_type, owner, symbol,
    name, sector, qty, purchase_price, purchase_date
    """
```

### Phase 3: UI Integration (Week 2-3)

#### 3.1 Add Schwab Tab to Connections
Modify `components/portfolio_connections.py`:
- Add "Schwab Direct" section
- Show Schwab accounts separately
- Provide OAuth authorization flow
- Display connection status

#### 3.2 Unified Holdings View
Merge Schwab and SnapTrade holdings:
- Show source (Schwab vs SnapTrade)
- Allow manual refresh
- Handle conflicts

### Phase 4: Transaction Import (Week 3)

#### 4.1 Extend Transaction Importer
Modify `components/transaction_importer.py`:
- Add Schwab transaction source
- Use existing storage and UI
- Merge with SnapTrade transactions

#### 4.2 Enhanced Features
- Real-time position updates
- Live P&L tracking
- Intraday transaction sync

---

## Implementation Details

### OAuth 2.0 Flow Implementation

```python
import requests
from urllib.parse import urlencode
import secrets
import hashlib
import base64

class SchwabOAuth:
    """Handle Schwab OAuth 2.0 with PKCE"""
    
    def __init__(self, app_key: str, app_secret: str, callback_url: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.callback_url = callback_url
        self.auth_url = "https://api.schwabapi.com/v1/oauth/authorize"
        self.token_url = "https://api.schwabapi.com/v1/oauth/token"
    
    def generate_pkce_pair(self):
        """Generate PKCE code verifier and challenge"""
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')
        
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    def get_authorization_url(self):
        """Generate authorization URL"""
        code_verifier, code_challenge = self.generate_pkce_pair()
        
        params = {
            'client_id': self.app_key,
            'redirect_uri': self.callback_url,
            'response_type': 'code',
            'scope': 'api',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        
        return auth_url, code_verifier
    
    def exchange_code_for_token(self, auth_code: str, code_verifier: str):
        """Exchange authorization code for access token"""
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.callback_url,
            'client_id': self.app_key,
            'code_verifier': code_verifier
        }
        
        response = requests.post(
            self.token_url,
            data=data,
            auth=(self.app_key, self.app_secret)
        )
        
        return response.json()
```

### API Endpoints

```python
class SchwabAPI:
    """Schwab API client"""
    
    BASE_URL = "https://api.schwabapi.com"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def get_accounts(self):
        """Get account numbers"""
        url = f"{self.BASE_URL}/trader/v1/accounts/accountNumbers"
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def get_account_details(self, account_id: str):
        """Get account details with positions"""
        url = f"{self.BASE_URL}/trader/v1/accounts/{account_id}"
        params = {'fields': 'positions'}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
    
    def get_transactions(self, account_id: str, start_date: str, end_date: str):
        """Get transaction history"""
        url = f"{self.BASE_URL}/trader/v1/accounts/{account_id}/transactions"
        params = {
            'startDate': start_date,
            'endDate': end_date,
            'types': 'TRADE,RECEIVE_AND_DELIVER,DIVIDEND_OR_INTEREST'
        }
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
    
    def get_quotes(self, symbols: list):
        """Get real-time quotes"""
        url = f"{self.BASE_URL}/marketdata/v1/quotes"
        params = {'symbols': ','.join(symbols)}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
```

---

## File Structure

```
components/
├── schwab_connector.py          # Main Schwab API connector
├── schwab_oauth.py              # OAuth 2.0 implementation
├── schwab_data_transformer.py   # Data transformation
└── portfolio_connections.py     # Updated with Schwab UI

pages/
└── 4_portfolio_hub.py          # Updated to show Schwab accounts

test_schwab_integration.py       # Test suite
SCHWAB_INTEGRATION_GUIDE.md      # User documentation
```

---

## Security Considerations

### Token Storage
```python
# Store tokens securely using existing credential manager
from components.credential_manager import CredentialManager

cred_manager = CredentialManager()
cred_manager.store_connection(
    brokerage_name="Schwab",
    account_id=account_id,
    access_token=access_token,
    refresh_token=refresh_token,
    user_id="default"
)
```

### Best Practices
✅ Store tokens encrypted
✅ Use HTTPS for callbacks
✅ Implement token refresh
✅ Handle token expiration
✅ Log API calls for debugging
✅ Rate limit API requests

---

## Testing Strategy

### Unit Tests
- OAuth flow
- Token refresh
- API calls
- Data transformation

### Integration Tests
- End-to-end authentication
- Account data retrieval
- Transaction import
- Quote fetching

### Manual Testing
- Connect real Schwab account
- Verify positions accuracy
- Test transaction import
- Check real-time quotes

---

## Deployment Checklist

### Prerequisites
- [ ] Schwab developer account created
- [ ] App registered with Schwab
- [ ] API keys obtained (App Key, App Secret)
- [ ] Callback URL configured
- [ ] Environment variables set

### Implementation
- [ ] Create schwab_connector.py
- [ ] Implement OAuth flow
- [ ] Add API endpoints
- [ ] Create data transformers
- [ ] Update UI components
- [ ] Write tests
- [ ] Create documentation

### Testing
- [ ] Test OAuth flow
- [ ] Verify account data
- [ ] Test transaction import
- [ ] Check data accuracy
- [ ] Performance testing

---

## Timeline

### Week 1: Setup & Authentication
- Day 1-2: OAuth 2.0 implementation
- Day 3-4: Token management
- Day 5: Testing authentication

### Week 2: Core Features
- Day 1-2: Account data retrieval
- Day 3-4: Position syncing
- Day 5: Data transformation

### Week 3: Integration & Testing
- Day 1-2: UI integration
- Day 3-4: Transaction import
- Day 5: Testing and documentation

---

## Next Steps

1. **Confirm Schwab API Access**
   - Verify you have Schwab developer account
   - Confirm API keys are active
   - Test API access

2. **Choose Implementation Approach**
   - Option A: Use schwab-py library (easier)
   - Option B: Direct API calls (more control)

3. **Start Implementation**
   - Create schwab_connector.py
   - Implement OAuth flow
   - Test with your account

---

## Resources

### Schwab API Documentation
- [Schwab Developer Portal](https://developer.schwab.com/)
- [API Documentation](https://developer.schwab.com/products/trader-api--individual)
- [OAuth Guide](https://developer.schwab.com/products/trader-api--individual/details/documentation/Retail%20Trader%20API%20Production)

### Python Libraries
- [schwab-py](https://github.com/alexgolec/schwab-py) - Unofficial Python wrapper
- [requests](https://requests.readthedocs.io/) - HTTP library
- [oauthlib](https://oauthlib.readthedocs.io/) - OAuth implementation

---

## Conclusion

Direct Schwab API integration will provide:
- ✅ More reliable connection
- ✅ Real-time data
- ✅ Complete transaction history
- ✅ Better control and features

**Ready to proceed?** Let me know and I'll start implementing the Schwab connector!

---

**Created**: March 17, 2026
**Status**: 📋 Planning - Awaiting Approval
**Priority**: High
**Estimated Effort**: 2-3 weeks