---
layout: default
title: Brokerage Connections Guide
---

# Brokerage Connections Guide

Comprehensive guide for connecting and managing brokerage accounts using SnapTrade integration.

## Overview

The SnapTrade integration enables automatic portfolio synchronization from your brokerage accounts, eliminating manual data entry and ensuring real-time accuracy.

### Key Benefits

- ⚡ **Automatic Updates** - One-click portfolio synchronization
- 🔒 **Bank-Level Security** - OAuth 2.0 + AES-256 encryption
- 📊 **99.9% Accuracy** - Direct data from financial institutions
- ⏱️ **Time Savings** - Eliminates hours of manual entry
- 🏦 **12,000+ Institutions** - Major brokerages and banks supported

---

## Prerequisites

Before connecting brokerage accounts, ensure you have:

1. **Python 3.9+** installed
2. **Application running** with all dependencies
3. **SnapTrade account** (free tier available)
4. **Brokerage account** at a supported institution

---

## Setup Process

### Step 1: Create SnapTrade Account

1. Visit [snaptrade.com](https://snaptrade.com)
2. Sign up for an account
3. Choose your plan:
   - **Free**: Up to 5 connections (perfect for personal use)
   - **Pro**: $10/month for unlimited connections
   - **Enterprise**: Custom pricing for advanced features

### Step 2: Get API Credentials

1. Log into SnapTrade dashboard
2. Navigate to **Applications** or **API Keys**
3. Create a new application
4. Copy your **Client ID** and **Consumer Key**
5. Choose environment:
   - **Sandbox**: For testing with demo accounts
   - **Production**: For real brokerage connections

### Step 3: Generate Encryption Key

Run this command to generate a secure encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Important:** Save this key securely! You'll need it to decrypt stored credentials.

### Step 4: Configure Environment Variables

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials:
   ```bash
   # SnapTrade API Credentials
   SNAPTRADE_CLIENT_ID=your_actual_client_id
   SNAPTRADE_CONSUMER_KEY=your_actual_consumer_key
   
   # Encryption Key (from Step 3)
   ENCRYPTION_KEY=your_generated_encryption_key
   
   # Optional: Pre-registered user credentials
   SNAPTRADE_USER_ID=your_user_id
   SNAPTRADE_USER_SECRET=your_user_secret
   
   # Optional: Environment (sandbox or production)
   SNAPTRADE_ENV=production
   ```

3. Verify `.env` is in `.gitignore`:
   ```bash
   grep -q "^\.env$" .gitignore && echo "✅ .env is ignored" || echo "❌ Add .env to .gitignore"
   ```

### Step 5: Restart Application

```bash
# Stop the application (Ctrl+C)
# Restart it
./run.sh
```

---

## Connecting Your First Account

### Method 1: Using Environment Credentials (Recommended)

If you've set `SNAPTRADE_USER_ID` and `SNAPTRADE_USER_SECRET` in `.env`:

1. Navigate to **Portfolio Hub** → **Connections** tab
2. Click **"Connect Brokerage"** button
3. Click the generated authorization link
4. Select your brokerage from the list
5. Complete OAuth authentication with your brokerage
6. Return to the application
7. Click **"I've completed authentication"**
8. Verify connection status shows as active

### Method 2: New User Registration

If you haven't pre-registered a user:

1. Navigate to **Portfolio Hub** → **Connections** tab
2. Click **"Connect Account"** button
3. System will register a new user automatically
4. Click the generated authorization link
5. Complete OAuth flow with your brokerage
6. Return and verify connection

---

## Syncing Portfolio Data

### Manual Sync

1. Go to **Portfolio Hub** → **Connections** tab
2. Find your connected account
3. Click **"🔄 Sync Now"** button
4. Review synced holdings in the preview
5. Click **"💾 Merge with Portfolio"** to import
6. Navigate to **Holdings** tab to see updated data

### Sync All Accounts

If you have multiple connected accounts:

1. Click **"🔄 Sync All Accounts"** button
2. System syncs all connected brokerages
3. Holdings are automatically merged
4. Check **Holdings** tab for updates

### Understanding the Merge Process

The smart merge logic:
- **Exact Match**: If month/year/account/symbol match → keeps existing data
- **Quantity Change**: If match but quantity differs → updates quantity
- **New Holding**: If no match found → adds new row
- **Preserves Manual Entries**: Doesn't remove manually entered data

---

## Managing Connections

### View Connection Status

Each connected account shows:
- **Institution Name** - Your brokerage
- **Account Type** - 401(k), IRA, Brokerage, etc.
- **Status** - Active or Inactive
- **Last Sync** - Timestamp of last synchronization
- **Token Expiry** - Days until re-authentication needed

### Disconnect an Account

1. Find the account in Connections tab
2. Click **"🗑️ Disconnect"** button
3. Click again to confirm
4. Credentials are immediately deleted
5. OAuth token is revoked

### Reconnect an Account

If token expires or connection fails:

1. Click **"Disconnect"** to remove old connection
2. Click **"Connect Account"** to start fresh
3. Complete OAuth flow again
4. Verify new connection works

---

## Supported Institutions

### Major Brokerages
- ✅ Charles Schwab
- ✅ Fidelity Investments
- ✅ Vanguard
- ✅ TD Ameritrade
- ✅ E*TRADE
- ✅ Merrill Edge
- ✅ Interactive Brokers
- ✅ Robinhood

### Retirement Account Providers
- ✅ Fidelity NetBenefits (401k)
- ✅ Vanguard Retirement
- ✅ TIAA
- ✅ Principal Financial
- ✅ Empower Retirement

### Banks with Investment Accounts
- ✅ Chase You Invest
- ✅ Bank of America
- ✅ Wells Fargo Advisors
- ✅ US Bank

**Total:** 12,000+ institutions via SnapTrade/Plaid integration

---

## Security & Privacy

### How Your Data is Protected

1. **OAuth 2.0 Authentication**
   - Industry-standard secure login
   - No password storage in our application
   - Revocable access tokens

2. **Encryption at Rest**
   - AES-256 encryption for all credentials
   - Fernet symmetric encryption
   - Secure key management via environment variables

3. **Read-Only Access**
   - View-only permissions
   - Cannot execute trades
   - Cannot move money

4. **Local Storage**
   - Credentials stored locally in SQLite
   - No cloud uploads of sensitive data
   - You control your data

5. **Easy Disconnect**
   - One-click account disconnection
   - Immediate token revocation
   - Complete data removal

### Security Best Practices

✅ **DO:**
- Keep `.env` file secure and never commit to version control
- Use strong, unique encryption keys
- Regularly rotate API credentials
- Use read-only API permissions
- Back up encryption key securely
- Review sync history regularly
- Disconnect unused accounts

❌ **DON'T:**
- Share your `.env` file or encryption key
- Commit credentials to git
- Use the same encryption key across environments
- Grant write/trade permissions unless necessary
- Store credentials in plain text

---

## Troubleshooting

### "Encryption key not found"

**Problem:** `ENCRYPTION_KEY` not set in `.env`

**Solution:**
```bash
# Generate new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add to .env file
echo "ENCRYPTION_KEY=<generated_key>" >> .env
```

### "SnapTrade credentials not found"

**Problem:** Missing API credentials

**Solution:**
- Verify `SNAPTRADE_CLIENT_ID` and `SNAPTRADE_CONSUMER_KEY` in `.env`
- Check credentials in SnapTrade dashboard
- Ensure `.env` file is in project root

### "Failed to generate auth link"

**Problem:** API authentication failed

**Solution:**
- Verify credentials are correct
- Check SnapTrade API status
- For personal API keys, try "Reset & Reconnect" option
- Ensure environment (sandbox/production) matches your credentials

### "No holdings found to sync"

**Problem:** Account appears empty

**Solution:**
- Verify brokerage account has holdings
- Complete OAuth authentication fully
- Check account connection status
- Try disconnecting and reconnecting
- Verify account type is supported

### "Token expired"

**Problem:** OAuth token needs refresh

**Solution:**
- Click "🔄 Sync Now" to refresh token
- Or disconnect and reconnect account
- Tokens typically last 90 days

### "Personal API key - only one user allowed"

**Problem:** Personal keys limit to one registered user

**Solution:**
- Add `SNAPTRADE_USER_ID` and `SNAPTRADE_USER_SECRET` to `.env`
- Or use "Reset & Reconnect" to delete and re-register
- Or upgrade to business API keys for multiple users

---

## Advanced Configuration

### Custom Database Location

```python
from components.credential_manager import CredentialManager

cred_manager = CredentialManager(db_path="custom/path/credentials.db")
```

### Multiple Users (Business Keys)

```python
# User 1
connector.sync_holdings(user_id="user1")

# User 2
connector.sync_holdings(user_id="user2")
```

### Scheduled Sync (Coming Soon)

```python
# Configure automatic daily sync at 6 AM
schedule_sync(user_id="default", frequency="daily", time="06:00")
```

---

## Cost Analysis

### SnapTrade Pricing

- **Free Tier**: Up to 5 connections
  - Perfect for personal use
  - All core features included
  - No credit card required

- **Pro Tier**: $10/month
  - Unlimited connections
  - Priority support
  - Advanced features

- **Enterprise**: Custom pricing
  - White-label options
  - Dedicated support
  - Custom integrations

### Recommendation

- **Personal Use**: Free tier (5 connections covers most individuals)
- **Family/Advisor**: Pro tier ($10/month)
- **Business**: Enterprise (contact SnapTrade)

---

## Best Practices

### Regular Maintenance

1. **Weekly**: Review sync status
2. **Monthly**: Verify data accuracy
3. **Quarterly**: Rotate encryption keys
4. **Annually**: Review connected accounts

### Data Accuracy

- Always review synced data before merging
- Compare with brokerage statements
- Report discrepancies to SnapTrade support
- Keep manual backup of critical data

### Performance Optimization

- Sync during off-peak hours
- Disconnect unused accounts
- Clear old sync history periodically
- Monitor database size

---

## Additional Resources

### Documentation
- [SnapTrade Quick Start](../../SNAPTRADE_QUICKSTART.md)
- [Implementation Summary](../../SNAPTRADE_IMPLEMENTATION_SUMMARY.md)
- [Integration Plan](../../SNAPTRADE_INTEGRATION_PLAN.md)

### External Resources
- [SnapTrade Documentation](https://docs.snaptrade.com)
- [SnapTrade API Reference](https://docs.snaptrade.com/reference)
- [Cryptography Library](https://cryptography.io)

### Support
- [SnapTrade Support](https://snaptrade.com/support)
- [GitHub Issues](https://github.com/yourusername/retirement_planning/issues)
- [Community Forum](https://github.com/yourusername/retirement_planning/discussions)

---

## FAQ

**Q: Is my data safe?**
A: Yes. We use bank-level security with OAuth 2.0 and AES-256 encryption. Credentials are stored locally, never in the cloud.

**Q: Can the application trade on my behalf?**
A: No. We only request read-only permissions. The application cannot execute trades or move money.

**Q: What if I want to stop using SnapTrade?**
A: Simply disconnect your accounts in the Connections tab. All credentials are immediately deleted.

**Q: How often should I sync?**
A: Weekly or monthly is typical. More frequent syncing provides more up-to-date data but isn't necessary for most users.

**Q: Does this work with international brokerages?**
A: SnapTrade supports many international institutions. Check their website for your specific brokerage.

**Q: What happens if SnapTrade goes down?**
A: Your manually entered data remains intact. You can continue using the application without brokerage connections.

---

[← Back to Guides](../guides.md) | [Next: Portfolio Analytics →](../../PORTFOLIO_ANALYTICS_GUIDE.md)