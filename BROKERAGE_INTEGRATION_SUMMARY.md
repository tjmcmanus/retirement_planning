# Brokerage Integration Summary

## Overview

This document provides a comprehensive overview of all brokerage integration capabilities in the retirement planning application, including SnapTrade universal aggregation and Schwab direct API integration.

## Table of Contents

1. [Integration Options](#integration-options)
2. [SnapTrade Integration](#snaptrade-integration)
3. [Schwab Direct API Integration](#schwab-direct-api-integration)
4. [Feature Comparison](#feature-comparison)
5. [Setup Instructions](#setup-instructions)
6. [Usage Guide](#usage-guide)
7. [Troubleshooting](#troubleshooting)
8. [API Reference](#api-reference)

---

## Integration Options

The application supports two primary methods for connecting to brokerage accounts:

### 1. SnapTrade Universal Aggregation
**Best for:** Multi-brokerage portfolios, quick setup, broad institution support

- **Supported Institutions:** 5,000+ brokerages, banks, and financial institutions
- **Setup Time:** 5-10 minutes
- **Authentication:** OAuth 2.0 through SnapTrade
- **Cost:** Free tier available, paid plans for advanced features
- **Maintenance:** Automatic connection management

### 2. Schwab Direct API
**Best for:** Schwab-only accounts, maximum control, direct integration

- **Supported Institutions:** Charles Schwab only
- **Setup Time:** 15-20 minutes (requires Schwab developer account)
- **Authentication:** OAuth 2.0 directly with Schwab
- **Cost:** Free (Schwab API is free)
- **Maintenance:** Manual token refresh required

---

## SnapTrade Integration

### Overview

SnapTrade provides universal aggregation across 5,000+ financial institutions through a single API. It handles authentication, data normalization, and connection maintenance automatically.

### Key Features

**Account Synchronization:**
- Real-time balance updates
- Holdings with current market values
- Cost basis tracking (FIFO method)
- Transaction history import
- Automatic daily sync

**Supported Account Types:**
- Taxable brokerage accounts
- Traditional IRAs
- Roth IRAs
- 401(k) and 403(b) plans
- HSAs
- 529 plans
- Bank accounts

**Data Retrieved:**
- Account balances and types
- Individual holdings (ticker, shares, value)
- Cost basis per lot
- Transaction history (buys, sells, dividends, transfers)
- Account metadata (account numbers, institution names)

### Setup Process

**Prerequisites:**
1. SnapTrade account (sign up at [snaptrade.com](https://snaptrade.com))
2. API credentials (Client ID and Consumer Key)
3. Brokerage account credentials

**Configuration:**
1. Add credentials to `.env`:
   ```bash
   SNAPTRADE_CLIENT_ID=your_client_id
   SNAPTRADE_CONSUMER_KEY=your_consumer_key
   SNAPTRADE_ENV=production  # or 'sandbox' for testing
   ```

2. Optional: Pre-register user:
   ```bash
   SNAPTRADE_USER_ID=your_user_id
   SNAPTRADE_USER_SECRET=your_user_secret
   ```

**Connection Steps:**
1. Navigate to Portfolio Hub → Connections tab
2. Click "Connect with SnapTrade"
3. Select your brokerage from the list
4. Enter credentials and authorize
5. Wait for initial sync (30-60 seconds)
6. Review imported accounts and holdings

### Architecture

**Components:**
- `components/snaptrade_integration.py` (450 lines) — Core integration logic
- `components/snaptrade_auth.py` (280 lines) — Authentication and token management
- `components/snaptrade_sync.py` (320 lines) — Data synchronization engine

**Data Flow:**
```
User → SnapTrade Auth → Brokerage OAuth → SnapTrade API
                                              ↓
                                    Account Data Retrieval
                                              ↓
                                    Data Normalization
                                              ↓
                                    Local Database Storage
                                              ↓
                                    Portfolio Display
```

**Security:**
- OAuth 2.0 token-based authentication
- No passwords stored locally
- Encrypted credential storage
- Read-only API access (no trading permissions)
- Automatic token refresh

### Documentation

- **[`SNAPTRADE_QUICKSTART.md`](SNAPTRADE_QUICKSTART.md)** (330 lines) — User-friendly setup guide
  - Step-by-step connection instructions
  - Troubleshooting common issues
  - FAQ section
  - Best practices

- **[`SNAPTRADE_IMPLEMENTATION_SUMMARY.md`](SNAPTRADE_IMPLEMENTATION_SUMMARY.md)** (450 lines) — Technical implementation details
  - Architecture overview
  - Component descriptions
  - API integration patterns
  - Testing guide

- **[`SNAPTRADE_INTEGRATION_PLAN.md`](SNAPTRADE_INTEGRATION_PLAN.md)** (330 lines) — Original implementation plan
  - 6-week development timeline
  - Feature specifications
  - Security considerations
  - Future enhancements

---

## Schwab Direct API Integration

### Overview

Direct integration with Charles Schwab's official API provides maximum control and eliminates third-party dependencies for Schwab account holders.

### Key Features

**Account Access:**
- Real-time account balances
- Detailed holdings information
- Transaction history (up to 3 years)
- Cost basis tracking
- Pending orders and settlements

**Advanced Features:**
- Transaction import with categorization
- Automatic cost basis calculation
- Tax lot tracking
- Dividend and distribution history
- Corporate actions (splits, mergers)

**Data Synchronization:**
- Manual refresh on-demand
- Scheduled daily sync (optional)
- Delta sync for efficiency
- Conflict detection and resolution

### Setup Process

**Prerequisites:**
1. Charles Schwab brokerage account
2. Schwab Developer account ([developer.schwab.com](https://developer.schwab.com))
3. Registered application with OAuth 2.0 credentials

**Configuration:**
1. Register app at Schwab Developer Portal:
   - Create new application
   - Set callback URL: `https://localhost:8080/callback`
   - Note App Key and App Secret

2. Add credentials to `.env`:
   ```bash
   SCHWAB_APP_KEY=your_app_key
   SCHWAB_APP_SECRET=your_app_secret
   SCHWAB_CALLBACK_URL=https://localhost:8080/callback
   ```

3. Optional: Store refresh token:
   ```bash
   SCHWAB_REFRESH_TOKEN=your_refresh_token
   ```

**Connection Steps:**
1. Navigate to Portfolio Hub → Connections tab
2. Click "Connect Schwab Account"
3. Authorize application in browser
4. Copy authorization code
5. Paste code to complete connection
6. Wait for initial sync
7. Review imported accounts

### Architecture

**Components:**
- `components/schwab_api.py` (580 lines) — Core API client
- `components/schwab_auth.py` (320 lines) — OAuth 2.0 authentication
- `components/schwab_sync.py` (450 lines) — Data synchronization
- `components/schwab_transactions.py` (380 lines) — Transaction import

**Data Flow:**
```
User → Schwab OAuth → Authorization Code → Token Exchange
                                                ↓
                                        Access Token
                                                ↓
                                        API Requests
                                                ↓
                                    Account Data Retrieval
                                                ↓
                                    Transaction Import
                                                ↓
                                    Cost Basis Calculation
                                                ↓
                                    Local Storage
                                                ↓
                                    Portfolio Display
```

**Security:**
- OAuth 2.0 with PKCE (Proof Key for Code Exchange)
- Encrypted token storage
- Automatic token refresh
- Read-only API scopes
- No trading permissions

### Transaction Import

**Supported Transaction Types:**
- Buys and sells
- Dividends (qualified and ordinary)
- Interest income
- Capital gains distributions
- Transfers (in/out)
- Corporate actions (splits, mergers, spinoffs)
- Options trades
- Margin interest

**Cost Basis Tracking:**
- FIFO (First In, First Out) method
- Lot-level tracking
- Wash sale detection
- Adjusted cost basis for corporate actions
- Long-term vs. short-term classification

**Tax Reporting:**
- Realized gains/losses by year
- Unrealized gains/losses
- Dividend income (qualified vs. ordinary)
- Interest income
- 1099-B reconciliation support

### Documentation

- **[`SCHWAB_INTEGRATION_GUIDE.md`](SCHWAB_INTEGRATION_GUIDE.md)** (476 lines) — Complete user guide
  - Developer account setup
  - OAuth 2.0 configuration
  - Connection instructions
  - Troubleshooting guide
  - API reference

- **[`SCHWAB_DIRECT_API_IMPLEMENTATION_COMPLETE.md`](SCHWAB_DIRECT_API_IMPLEMENTATION_COMPLETE.md)** (560 lines) — Implementation summary
  - Architecture overview
  - Component descriptions
  - Testing results
  - Known limitations

- **[`SCHWAB_TRANSACTION_IMPORT_IMPLEMENTATION.md`](SCHWAB_TRANSACTION_IMPORT_IMPLEMENTATION.md)** (557 lines) — Transaction import guide
  - Transaction type mapping
  - Cost basis calculation
  - Tax reporting features
  - Integration with portfolio

- **[`SCHWAB_DIRECT_API_INTEGRATION_PLAN.md`](SCHWAB_DIRECT_API_INTEGRATION_PLAN.md)** (315 lines) — Original implementation plan
  - Feature specifications
  - Security design
  - Development timeline

---

## Feature Comparison

| Feature | SnapTrade | Schwab Direct API |
|---------|-----------|-------------------|
| **Supported Institutions** | 5,000+ | Schwab only |
| **Setup Complexity** | Low | Medium |
| **Setup Time** | 5-10 min | 15-20 min |
| **Authentication** | OAuth via SnapTrade | OAuth directly with Schwab |
| **Account Types** | All types | All Schwab account types |
| **Real-time Data** | Yes | Yes |
| **Transaction History** | Yes (varies by institution) | Yes (3 years) |
| **Cost Basis Tracking** | Yes | Yes (detailed) |
| **Automatic Sync** | Yes (daily) | Optional (manual or scheduled) |
| **Token Refresh** | Automatic | Automatic |
| **API Cost** | Free tier + paid plans | Free |
| **Maintenance** | Low (automatic) | Low (automatic token refresh) |
| **Data Normalization** | Automatic | Manual (handled by app) |
| **Multi-Brokerage** | Yes | No |
| **Transaction Import** | Yes | Yes (advanced) |
| **Tax Reporting** | Basic | Advanced |
| **Corporate Actions** | Limited | Full support |
| **Options Trading** | Limited | Full support |

### When to Use Each

**Use SnapTrade if:**
- You have accounts at multiple brokerages
- You want the simplest setup process
- You need broad institution support
- You prefer automatic connection management
- You don't need advanced transaction details

**Use Schwab Direct API if:**
- You only have Schwab accounts
- You want maximum control over data
- You need detailed transaction history
- You require advanced tax reporting
- You want to eliminate third-party dependencies

**Use Both if:**
- You have Schwab accounts plus other brokerages
- You want Schwab detail + multi-brokerage coverage
- You need comprehensive portfolio view

---

## Setup Instructions

### Quick Start (SnapTrade)

1. **Get API Credentials:**
   - Sign up at [snaptrade.com](https://snaptrade.com)
   - Navigate to API settings
   - Copy Client ID and Consumer Key

2. **Configure Application:**
   ```bash
   # Add to .env file
   SNAPTRADE_CLIENT_ID=your_client_id
   SNAPTRADE_CONSUMER_KEY=your_consumer_key
   SNAPTRADE_ENV=production
   ```

3. **Connect Accounts:**
   - Open Portfolio Hub → Connections
   - Click "Connect with SnapTrade"
   - Select brokerage and authorize
   - Wait for sync to complete

4. **Verify Data:**
   - Check Portfolio Hub → Overview
   - Verify account balances
   - Review holdings
   - Check transaction history

### Quick Start (Schwab)

1. **Register Developer Account:**
   - Visit [developer.schwab.com](https://developer.schwab.com)
   - Create developer account
   - Verify email

2. **Create Application:**
   - Navigate to "My Apps"
   - Click "Create New App"
   - Set callback URL: `https://localhost:8080/callback`
   - Save App Key and App Secret

3. **Configure Application:**
   ```bash
   # Add to .env file
   SCHWAB_APP_KEY=your_app_key
   SCHWAB_APP_SECRET=your_app_secret
   SCHWAB_CALLBACK_URL=https://localhost:8080/callback
   ```

4. **Connect Account:**
   - Open Portfolio Hub → Connections
   - Click "Connect Schwab Account"
   - Authorize in browser
   - Copy authorization code
   - Paste code to complete setup

5. **Verify Data:**
   - Check Portfolio Hub → Overview
   - Verify account balances
   - Review holdings and transactions
   - Check cost basis tracking

---

## Usage Guide

### Daily Workflow

**Automatic Sync (SnapTrade):**
- Runs daily at 6 AM local time
- Updates all connected accounts
- Imports new transactions
- Updates cost basis
- No user action required

**Manual Refresh:**
1. Navigate to Portfolio Hub → Connections
2. Click "Refresh All Accounts"
3. Wait for sync to complete (30-60 seconds)
4. Review updated data

### Transaction Management

**Viewing Transactions:**
1. Portfolio Hub → Holdings Management
2. Select account
3. Click "View Transactions"
4. Filter by date, type, or security

**Cost Basis Tracking:**
1. Portfolio Hub → Holdings Management
2. Select security
3. View "Cost Basis Details"
4. See lot-level information
5. Review realized/unrealized gains

**Tax Reporting:**
1. Portfolio Hub → Performance & Analytics
2. Navigate to "Tax Analytics" section
3. Select tax year
4. View realized gains/losses
5. Export for tax preparation

### Account Management

**Adding Accounts:**
- Use "Connect New Account" button
- Follow authentication flow
- Wait for initial sync
- Verify data accuracy

**Removing Accounts:**
- Navigate to Connections tab
- Click "Disconnect" next to account
- Confirm removal
- Data will be archived (not deleted)

**Reconnecting Accounts:**
- If connection expires, click "Reconnect"
- Re-authenticate with brokerage
- Sync will resume automatically

---

## Troubleshooting

### Common Issues

#### "SnapTrade credentials not found"
**Cause:** Missing or incorrect API credentials

**Solution:**
1. Verify `.env` file contains:
   ```bash
   SNAPTRADE_CLIENT_ID=your_client_id
   SNAPTRADE_CONSUMER_KEY=your_consumer_key
   ```
2. Check credentials in SnapTrade dashboard
3. Ensure no extra spaces or quotes
4. Restart application

#### "Schwab authorization failed"
**Cause:** Invalid App Key/Secret or callback URL mismatch

**Solution:**
1. Verify credentials in `.env`:
   ```bash
   SCHWAB_APP_KEY=your_app_key
   SCHWAB_APP_SECRET=your_app_secret
   SCHWAB_CALLBACK_URL=https://localhost:8080/callback
   ```
2. Check callback URL matches Schwab app settings
3. Ensure app is approved in Schwab Developer Portal
4. Try generating new credentials

#### "Connection expired"
**Cause:** OAuth token expired (typically after 90 days)

**Solution:**
1. Click "Reconnect" button
2. Re-authenticate with brokerage
3. Connection will be restored
4. No data loss occurs

#### "Sync failed"
**Cause:** Temporary API issue or network problem

**Solution:**
1. Wait 5 minutes and try again
2. Check internet connection
3. Verify brokerage website is accessible
4. Check API status pages:
   - SnapTrade: [status.snaptrade.com](https://status.snaptrade.com)
   - Schwab: [developer.schwab.com/status](https://developer.schwab.com/status)

#### "Duplicate transactions"
**Cause:** Multiple syncs or manual import conflicts

**Solution:**
1. Navigate to Holdings Management
2. Click "Review Duplicates"
3. Select transactions to keep
4. Delete duplicates
5. System will prevent future duplicates

#### "Cost basis incorrect"
**Cause:** Missing transaction history or corporate actions

**Solution:**
1. Verify all transactions imported
2. Check for missing buys/sells
3. Review corporate actions (splits, mergers)
4. Manually adjust if necessary
5. Contact support if issue persists

### Getting Help

**Documentation:**
- SnapTrade: [`SNAPTRADE_QUICKSTART.md`](SNAPTRADE_QUICKSTART.md)
- Schwab: [`SCHWAB_INTEGRATION_GUIDE.md`](SCHWAB_INTEGRATION_GUIDE.md)

**API Documentation:**
- SnapTrade: [docs.snaptrade.com](https://docs.snaptrade.com)
- Schwab: [developer.schwab.com/docs](https://developer.schwab.com/docs)

**Support:**
- SnapTrade: support@snaptrade.com
- Schwab: developer-support@schwab.com

---

## API Reference

### SnapTrade Integration

**Key Functions:**

```python
from components.snaptrade_integration import SnapTradeClient

# Initialize client
client = SnapTradeClient(
    client_id="your_client_id",
    consumer_key="your_consumer_key"
)

# Register user
user = client.register_user(user_id="unique_user_id")

# Get authorization URL
auth_url = client.get_authorization_url(user_id="user_id")

# List accounts
accounts = client.get_accounts(user_id="user_id")

# Get holdings
holdings = client.get_holdings(
    user_id="user_id",
    account_id="account_id"
)

# Get transactions
transactions = client.get_transactions(
    user_id="user_id",
    account_id="account_id",
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# Sync all accounts
client.sync_all_accounts(user_id="user_id")
```

### Schwab Direct API

**Key Functions:**

```python
from components.schwab_api import SchwabClient

# Initialize client
client = SchwabClient(
    app_key="your_app_key",
    app_secret="your_app_secret",
    callback_url="https://localhost:8080/callback"
)

# Get authorization URL
auth_url = client.get_authorization_url()

# Exchange code for tokens
tokens = client.exchange_code(authorization_code="code")

# Get accounts
accounts = client.get_accounts()

# Get account details
account = client.get_account(account_id="account_id")

# Get transactions
transactions = client.get_transactions(
    account_id="account_id",
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# Refresh token
new_tokens = client.refresh_access_token(refresh_token="token")
```

---

## Best Practices

### Security

1. **Never commit credentials to version control**
   - Use `.env` file (included in `.gitignore`)
   - Use environment variables in production
   - Rotate credentials periodically

2. **Use read-only API scopes**
   - Never request trading permissions
   - Limit to account and transaction data
   - Review permissions regularly

3. **Encrypt sensitive data**
   - Use OS keychain for token storage
   - Encrypt local database
   - Use HTTPS for all API calls

### Data Management

1. **Regular backups**
   - Export portfolio data monthly
   - Backup transaction history
   - Store cost basis records

2. **Verify data accuracy**
   - Compare with brokerage statements
   - Review cost basis calculations
   - Check transaction categorization

3. **Monitor sync status**
   - Check for failed syncs
   - Review error logs
   - Reconnect expired connections

### Performance

1. **Optimize sync frequency**
   - Daily sync is usually sufficient
   - Use manual refresh for real-time needs
   - Avoid excessive API calls

2. **Use delta sync**
   - Only fetch changed data
   - Reduces API usage
   - Improves performance

3. **Cache data locally**
   - Store account data in database
   - Use cached data for display
   - Refresh periodically

---

## Future Enhancements

### Planned Features

1. **Additional Brokerages**
   - Fidelity direct API
   - Vanguard integration
   - Interactive Brokers support

2. **Advanced Analytics**
   - Performance attribution
   - Risk metrics
   - Benchmark comparison

3. **Tax Optimization**
   - Tax-loss harvesting automation
   - Wash sale detection
   - Optimal withdrawal strategies

4. **Alerts & Notifications**
   - Balance change alerts
   - Transaction notifications
   - Sync failure warnings

5. **Mobile Support**
   - iOS app
   - Android app
   - Mobile-optimized web interface

---

## Conclusion

The brokerage integration features provide comprehensive connectivity to financial institutions, enabling automatic portfolio tracking, transaction import, and cost basis management. Whether using SnapTrade for multi-brokerage aggregation or Schwab's direct API for detailed account access, the application provides production-ready tools for managing retirement portfolios.

For detailed setup instructions, refer to the specific integration guides:
- **SnapTrade:** [`SNAPTRADE_QUICKSTART.md`](SNAPTRADE_QUICKSTART.md)
- **Schwab:** [`SCHWAB_INTEGRATION_GUIDE.md`](SCHWAB_INTEGRATION_GUIDE.md)

---

**Last Updated:** March 20, 2026
**Version:** 1.0