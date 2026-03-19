# Schwab Direct API Integration Guide

## Overview

This guide explains how to set up and use the Schwab Direct API integration for automatic portfolio synchronization.

**Status**: ✅ Implementation Complete  
**Version**: 1.0  
**Last Updated**: March 17, 2026

---

## Features

### What's Included

✅ **OAuth 2.0 Authentication** - Secure PKCE-based authentication  
✅ **Account Data Sync** - Automatic position and balance updates  
✅ **Transaction History** - Import complete transaction records  
✅ **Real-Time Quotes** - Live market data for your holdings  
✅ **Secure Token Storage** - Encrypted credential management  
✅ **Auto Token Refresh** - Seamless re-authentication  

### Benefits Over SnapTrade

- **More Reliable** - Direct connection to Schwab
- **Real-Time Data** - Live quotes and positions
- **No Intermediary** - Fewer points of failure
- **Complete History** - Full transaction records
- **Free** - No additional service fees

---

## Prerequisites

### 1. Schwab Developer Account

1. Visit [Schwab Developer Portal](https://developer.schwab.com/)
2. Sign up for a developer account
3. Create a new application
4. Note your credentials:
   - **App Key** (Client ID)
   - **App Secret** (Client Secret)
   - **Callback URL** (e.g., `https://localhost:8080/callback`)

### 2. Python Dependencies

Already included in `requirements.txt`:
```bash
schwab-py>=1.0.0
requests>=2.31.0
oauthlib>=3.2.0
```

Install if needed:
```bash
pip install -r requirements.txt
```

---

## Setup Instructions

### Step 1: Configure Environment Variables

Add to your `.env` file:

```bash
# Schwab API Credentials
SCHWAB_APP_KEY=your_app_key_here
SCHWAB_APP_SECRET=your_app_secret_here
SCHWAB_CALLBACK_URL=https://localhost:8080/callback

# Encryption Key (if not already set)
ENCRYPTION_KEY=your_encryption_key_here
```

**Generate Encryption Key** (if needed):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Step 2: Restart Application

After configuring `.env`, restart the Streamlit application:
```bash
streamlit run planning_app.py
```

---

## Usage

### Connecting Your Schwab Account

1. **Navigate to Portfolio Hub**
   - Go to the Portfolio Hub page
   - Click on the "Connections" tab

2. **Select Schwab Direct**
   - You'll see both SnapTrade and Schwab Direct options
   - Click "Connect Schwab Direct"

3. **Authorize Access**
   - Click the authorization link
   - Log in to your Schwab account
   - Approve the application
   - Copy the callback URL

4. **Complete Connection**
   - Paste the callback URL
   - Click "Complete Authorization"
   - Your account is now connected!

### Syncing Portfolio Data

#### Manual Sync

1. Go to Connections tab
2. Find your Schwab account
3. Click "🔄 Sync Now"
4. Review synced holdings
5. Click "💾 Merge with Portfolio"

#### Automatic Sync

- Positions are automatically refreshed when you view the Portfolio Hub
- Token refresh happens automatically when needed
- No manual intervention required

### Viewing Synced Data

**Holdings Tab:**
- See all positions from Schwab
- Source indicator shows "Schwab" for synced holdings
- Real-time values and P&L

**Transactions Tab:**
- Import transaction history
- Filter by date range
- Export to CSV

---

## API Components

### Core Files

```
components/
├── schwab_oauth.py              # OAuth 2.0 authentication
├── schwab_connector.py          # Main API client
├── schwab_data_transformer.py   # Data transformation
└── portfolio_connections.py     # UI integration (updated)
```

### Key Classes

#### SchwabOAuth
Handles OAuth 2.0 authentication with PKCE:
```python
from components.schwab_oauth import SchwabOAuth

oauth = SchwabOAuth(app_key, app_secret, callback_url)
auth_url, code_verifier = oauth.get_authorization_url()
# User authorizes...
tokens = oauth.exchange_code_for_token(auth_code, code_verifier)
```

#### SchwabConnector
High-level interface for Schwab API:
```python
from components.schwab_connector import SchwabConnector

connector = SchwabConnector(app_key, app_secret, callback_url)
connector.complete_authorization(callback_url)
accounts = connector.get_accounts()
positions = connector.get_positions()
```

#### SchwabDataTransformer
Converts Schwab data to portfolio format:
```python
from components.schwab_data_transformer import SchwabDataTransformer

transformer = SchwabDataTransformer()
portfolio_df = transformer.transform_positions_to_portfolio(positions)
```

---

## Data Transformation

### Position Mapping

**Schwab Format:**
```json
{
  "instrument": {
    "symbol": "AAPL",
    "description": "Apple Inc",
    "assetType": "EQUITY"
  },
  "longQuantity": 100,
  "averagePrice": 150.00,
  "marketValue": 15500.00
}
```

**Portfolio Format:**
```csv
month,year,account_name,account_type,owner,symbol,name,sector,qty,purchase_price
3,2026,Schwab-1234,Brokerage,Self,AAPL,Apple Inc,Stock,100,150.00
```

### Transaction Mapping

**Schwab Format:**
```json
{
  "activityId": 123456789,
  "type": "TRADE",
  "tradeDate": "2024-01-15",
  "netAmount": -15000.00,
  "transferItems": [{
    "instrument": {"symbol": "AAPL"},
    "amount": 100,
    "price": 150.00
  }]
}
```

**Standardized Format:**
```csv
transaction_id,date,type,symbol,quantity,price,amount
123456789,2024-01-15,TRADE,AAPL,100,150.00,-15000.00
```

---

## Security

### Token Storage

- **Encrypted at Rest** - Fernet symmetric encryption
- **Secure Database** - SQLite with encrypted fields
- **Auto Refresh** - Tokens refreshed before expiry
- **No Plaintext** - Credentials never stored in plain text

### Best Practices

✅ **Never commit `.env` file** to version control  
✅ **Keep encryption key secure** and backed up  
✅ **Use HTTPS** for callback URLs in production  
✅ **Rotate credentials** periodically  
✅ **Monitor API usage** for unusual activity  

### OAuth Flow Security

- **PKCE** (Proof Key for Code Exchange) prevents authorization code interception
- **State Parameter** prevents CSRF attacks
- **Short-lived Tokens** minimize exposure window
- **Refresh Tokens** stored encrypted

---

## Troubleshooting

### Connection Issues

**Problem:** "Failed to generate authorization URL"
- **Solution:** Check that `SCHWAB_APP_KEY` and `SCHWAB_APP_SECRET` are set correctly

**Problem:** "Token exchange failed"
- **Solution:** Ensure callback URL matches exactly what's registered with Schwab

**Problem:** "API client not initialized"
- **Solution:** Complete authorization flow first

### Sync Issues

**Problem:** "No holdings found"
- **Solution:** Verify your Schwab account has positions

**Problem:** "Token expired"
- **Solution:** Tokens auto-refresh, but you may need to re-authorize if refresh token expired

**Problem:** "Rate limit exceeded"
- **Solution:** Schwab has API rate limits; wait a few minutes and try again

### Data Issues

**Problem:** "Positions not showing in portfolio"
- **Solution:** Click "Merge with Portfolio" after syncing

**Problem:** "Duplicate holdings"
- **Solution:** Check source indicator; you may have both manual and synced entries

---

## API Limits

### Schwab API Rate Limits

- **120 requests per minute** per user
- **Quotes:** 120 requests/minute
- **Accounts:** 60 requests/minute
- **Transactions:** 60 requests/minute

### Best Practices

- Cache quote data for 15 seconds
- Batch symbol requests (up to 500 symbols)
- Use webhooks for real-time updates (if available)
- Implement exponential backoff for retries

---

## Advanced Usage

### Programmatic Access

```python
from components.schwab_connector import SchwabConnector
from components.schwab_data_transformer import SchwabDataTransformer

# Initialize
connector = SchwabConnector(app_key, app_secret, callback_url)
transformer = SchwabDataTransformer()

# Load saved tokens
if connector.load_saved_tokens():
    # Get positions
    positions = connector.get_positions()
    
    # Transform to portfolio format
    portfolio_df = transformer.transform_positions_to_portfolio(positions)
    
    # Get real-time quotes
    symbols = portfolio_df['symbol'].unique().tolist()
    quotes = connector.get_quotes(symbols)
    
    # Get transactions
    for account in connector.get_accounts():
        account_hash = account['securitiesAccount']['hashValue']
        transactions = connector.get_transactions(account_hash, days_back=30)
```

### Custom Data Processing

```python
# Merge with existing portfolio
merged_df = transformer.merge_with_existing_portfolio(
    schwab_positions=portfolio_df,
    existing_portfolio=existing_df
)

# Filter by account type
ira_positions = portfolio_df[portfolio_df['account_type'] == 'IRA']

# Calculate totals
total_value = portfolio_df['current_value'].sum()
```

---

## Support

### Resources

- **Schwab API Docs:** [developer.schwab.com](https://developer.schwab.com/)
- **Project Issues:** GitHub Issues (if applicable)
- **Community:** Schwab Developer Forum

### Getting Help

1. Check this guide first
2. Review error messages carefully
3. Check Schwab API status page
4. Verify credentials and configuration
5. Enable debug logging for detailed errors

### Debug Logging

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Comparison: Schwab Direct vs SnapTrade

| Feature | Schwab Direct | SnapTrade |
|---------|--------------|-----------|
| **Brokerages** | Schwab only | 12,000+ institutions |
| **Reliability** | ⭐⭐⭐⭐⭐ Direct | ⭐⭐⭐⭐ Via intermediary |
| **Real-Time Data** | ✅ Yes | ⚠️ Delayed |
| **Transaction History** | ✅ Complete | ✅ Complete |
| **Setup Complexity** | Medium | Easy |
| **Cost** | Free | Free tier available |
| **Maintenance** | Self-managed | Managed service |

### When to Use Each

**Use Schwab Direct when:**
- You only have Schwab accounts
- You need real-time data
- You want maximum reliability
- You're comfortable with OAuth setup

**Use SnapTrade when:**
- You have multiple brokerages
- You want quick setup
- You prefer managed service
- You don't need real-time data

**Use Both when:**
- You have Schwab + other brokerages
- You want best of both worlds
- You need maximum coverage

---

## Changelog

### Version 1.0 (March 17, 2026)
- ✅ Initial implementation
- ✅ OAuth 2.0 with PKCE
- ✅ Account and position sync
- ✅ Transaction history import
- ✅ Real-time quotes
- ✅ Secure token storage
- ✅ UI integration

### Planned Features
- 🔄 Webhook support for real-time updates
- 🔄 Trade execution capabilities
- 🔄 Options chain data
- 🔄 Historical price data
- 🔄 Performance analytics

---

## Conclusion

The Schwab Direct API integration provides a robust, reliable way to automatically sync your Schwab portfolio data. With secure OAuth authentication, real-time data access, and seamless integration with the Portfolio Hub, you can maintain an up-to-date view of your investments with minimal manual effort.

**Ready to get started?** Follow the setup instructions above and connect your Schwab account today!

---

**Questions or Issues?** Check the Troubleshooting section or review the Schwab API documentation.