# SnapTrade Integration Quick Start Guide

## Overview
This guide will help you set up secure brokerage account connections using SnapTrade API, enabling automatic portfolio synchronization.

---

## Prerequisites

- Python 3.8 or higher
- Active SnapTrade account (sign up at [snaptrade.com](https://snaptrade.com))
- Brokerage account at a supported institution

---

## Step 1: Install Dependencies

```bash
pip install snaptrade-python-sdk cryptography python-dotenv
```

Or update from requirements.txt:
```bash
pip install -r requirements.txt
```

---

## Step 2: Get SnapTrade API Credentials

1. **Sign up for SnapTrade**
   - Go to [https://snaptrade.com](https://snaptrade.com)
   - Create an account
   - Choose your plan:
     - **Free**: Up to 5 connections (perfect for testing)
     - **Pro**: $10/month for unlimited connections
     - **Enterprise**: Custom pricing

2. **Create an Application**
   - Log into SnapTrade dashboard
   - Navigate to "Applications" or "API Keys"
   - Create a new application
   - Note your **Client ID** and **Consumer Key**

3. **Choose Environment**
   - **Sandbox**: For testing with demo accounts (recommended first)
   - **Production**: For real brokerage connections

---

## Step 3: Generate Encryption Key

Run this command to generate a secure encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Important**: Save this key securely! You'll need it to decrypt your stored credentials.

---

## Step 4: Configure Environment Variables

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file** with your credentials:
   ```bash
   # SnapTrade API Credentials
   SNAPTRADE_CLIENT_ID=your_actual_client_id
   SNAPTRADE_CONSUMER_KEY=your_actual_consumer_key

   # Encryption Key (from Step 3)
   ENCRYPTION_KEY=your_generated_encryption_key

   # OPTIONAL: If you already have a registered user (RECOMMENDED)
   # This skips the registration step and uses your existing credentials
   SNAPTRADE_USER_ID=your_user_id
   SNAPTRADE_USER_SECRET=your_user_secret

   # Optional: Environment (sandbox or production)
   SNAPTRADE_ENV=sandbox
   ```

3. **Getting Your User ID and Secret** (Recommended):
   - If you've already registered a user with SnapTrade
   - Add `SNAPTRADE_USER_ID` and `SNAPTRADE_USER_SECRET` to `.env`
   - This bypasses registration and works immediately
   - Especially useful with personal API keys (which only allow one user)

3. **Verify `.env` is in `.gitignore`**:
   ```bash
   grep -q "^\.env$" .gitignore && echo "✅ .env is ignored" || echo "❌ Add .env to .gitignore"
   ```

---

## Step 5: Test the Setup

Run this test script to verify everything is configured correctly:

```python
# test_snaptrade_setup.py
from components.credential_manager import CredentialManager, generate_encryption_key
from components.snaptrade_connector import create_snaptrade_connector

try:
    # Test credential manager
    print("Testing credential manager...")
    cred_manager = CredentialManager()
    print("✅ Credential manager initialized")
    
    # Test SnapTrade connector
    print("\nTesting SnapTrade connector...")
    connector = create_snaptrade_connector()
    print("✅ SnapTrade connector initialized")
    
    # Test connection status
    print("\nTesting connection status...")
    status = connector.get_connection_status()
    print(f"✅ Connection status: {status}")
    
    print("\n🎉 Setup complete! You're ready to connect brokerage accounts.")
    
except Exception as e:
    print(f"❌ Setup failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check that .env file exists and contains all required variables")
    print("2. Verify SnapTrade credentials are correct")
    print("3. Ensure encryption key is valid")
```

Run it:
```bash
python test_snaptrade_setup.py
```

---

## Step 6: Connect Your First Account

1. **Start the application**:
   ```bash
   streamlit run planning_app.py
   ```

2. **Navigate to Portfolio Hub**:
   - Click "📊 Portfolio" in the sidebar
   - Go to "🔗 Connections" tab

3. **Click "Connect Account"**:
   - You'll get an authorization link
   - Click the link to authenticate with your brokerage
   - Complete the OAuth flow
   - Return to the app

4. **Verify Connection**:
   - You should see your connected account listed
   - Click "🔄 Sync Now" to test synchronization

---

## Step 7: Sync Your Portfolio

1. **Manual Sync**:
   - Click "🔄 Sync Now" on any connected account
   - Review the synced holdings
   - Click "💾 Merge with Portfolio" to import

2. **Automatic Sync** (Coming Soon):
   - Configure sync schedule (daily/weekly)
   - Holdings will update automatically

---

## Security Best Practices

### ✅ DO:
- Keep `.env` file secure and never commit it to version control
- Use strong, unique encryption keys
- Regularly rotate API credentials
- Use read-only API permissions
- Back up your encryption key securely
- Review sync history regularly
- Disconnect unused accounts

### ❌ DON'T:
- Share your `.env` file or encryption key
- Commit credentials to git
- Use the same encryption key across environments
- Grant write/trade permissions unless necessary
- Store credentials in plain text

---

## Troubleshooting

### "Encryption key not found"
**Solution**: Ensure `ENCRYPTION_KEY` is set in `.env` file

### "snaptrade_client module not found"
**Solution**: Install the correct package: `pip install snaptrade-python-sdk`

### "SnapTrade credentials not found"
**Solution**: Verify `SNAPTRADE_CLIENT_ID` and `SNAPTRADE_CONSUMER_KEY` are in `.env`

### "Failed to generate auth link"
**Solution**: 
- Check your SnapTrade credentials are correct
- Verify you're using the right environment (sandbox vs production)
- Check SnapTrade dashboard for API status

### "No holdings found to sync"
**Solution**:
- Verify your brokerage account has holdings
- Check that authentication completed successfully
- Try disconnecting and reconnecting the account

### "Token expired"
**Solution**: Click "🔄 Sync Now" to refresh the token, or disconnect and reconnect

---

## Supported Brokerages

SnapTrade supports 12,000+ financial institutions including:

### Major Brokerages:
- ✅ Charles Schwab
- ✅ Fidelity Investments
- ✅ Vanguard
- ✅ TD Ameritrade
- ✅ E*TRADE
- ✅ Merrill Edge
- ✅ Interactive Brokers
- ✅ Robinhood

### Retirement Accounts:
- ✅ Fidelity NetBenefits (401k)
- ✅ Vanguard Retirement
- ✅ TIAA
- ✅ Principal Financial

### Banks with Investment Accounts:
- ✅ Chase You Invest
- ✅ Bank of America
- ✅ Wells Fargo Advisors
- ✅ US Bank

For a complete list, visit [SnapTrade's supported institutions](https://snaptrade.com/institutions).

---

## Data Privacy & Security

### How Your Data is Protected:

1. **OAuth 2.0 Authentication**
   - Industry-standard secure login
   - No password storage
   - Revocable access tokens

2. **Encryption at Rest**
   - AES-256 encryption for all credentials
   - Fernet symmetric encryption
   - Secure key management

3. **Read-Only Access**
   - No trading permissions
   - View-only account access
   - Cannot move money

4. **Local Storage**
   - Credentials stored locally in SQLite
   - No cloud storage of sensitive data
   - You control your data

5. **Easy Disconnect**
   - One-click account disconnection
   - Immediate token revocation
   - Complete data removal

---

## Cost Breakdown

### SnapTrade Pricing:
- **Free Tier**: Up to 5 connections (perfect for personal use)
- **Pro Tier**: $10/month for unlimited connections
- **Enterprise**: Custom pricing for advanced features

### Recommended for Most Users:
Start with **Free Tier** to test, upgrade to **Pro** if you need more than 5 accounts.

---

## Next Steps

1. ✅ Complete setup (Steps 1-5)
2. ✅ Connect your first account (Step 6)
3. ✅ Sync and verify holdings (Step 7)
4. 📊 Use Portfolio Hub features:
   - View consolidated holdings
   - Track performance
   - Rebalance across accounts
   - Optimize tax efficiency

---

## Support

### Documentation:
- **SnapTrade Docs**: [https://docs.snaptrade.com](https://docs.snaptrade.com)
- **Implementation Plan**: See `SNAPTRADE_INTEGRATION_PLAN.md`
- **API Reference**: [https://docs.snaptrade.com/reference](https://docs.snaptrade.com/reference)

### Need Help?
- Check troubleshooting section above
- Review SnapTrade documentation
- Contact SnapTrade support for API issues
- File an issue in the project repository

---

## Advanced Configuration

### Custom Database Location:
```python
from components.credential_manager import CredentialManager

cred_manager = CredentialManager(db_path="custom/path/credentials.db")
```

### Multiple Users:
```python
# User 1
connector.sync_holdings(user_id="user1")

# User 2
connector.sync_holdings(user_id="user2")
```

### Scheduled Sync (Coming Soon):
```python
# Configure automatic daily sync at 6 AM
schedule_sync(user_id="default", frequency="daily", time="06:00")
```

---

**Ready to get started?** Follow Step 1 above! 🚀