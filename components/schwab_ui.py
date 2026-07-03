"""
Schwab Direct API UI Components
UI functions for Schwab Direct integration in Portfolio Hub
"""

import os
import logging
import streamlit as st
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)


def render_schwab_direct_section(portdf: pd.DataFrame, curr_month: int, curr_year: int) -> None:
    """Render Schwab Direct API connection section."""
    st.markdown("### Direct Schwab API Integration")
    st.caption("Real-time data and enhanced features for Schwab accounts")
    
    # Check for Schwab credentials
    schwab_app_key = os.getenv("SCHWAB_APP_KEY")
    schwab_app_secret = os.getenv("SCHWAB_APP_SECRET")
    schwab_callback_url = os.getenv("SCHWAB_CALLBACK_URL", "https://localhost:8080/callback")
    
    if not schwab_app_key or not schwab_app_secret:
        render_schwab_setup_instructions()
        return
    
    # Initialize Schwab connector
    try:
        from components.schwab_connector import SchwabConnector
        from components.schwab_data_transformer import SchwabDataTransformer
        from components.credential_manager import CredentialManager
        
        if 'schwab_connector' not in st.session_state:
            st.session_state.schwab_connector = SchwabConnector(
                app_key=schwab_app_key,
                app_secret=schwab_app_secret,
                callback_url=schwab_callback_url,
                credential_manager=CredentialManager()
            )
            st.session_state.schwab_transformer = SchwabDataTransformer()
        
        schwab_connector = st.session_state.schwab_connector
        schwab_transformer = st.session_state.schwab_transformer
        
        # Try to load saved tokens
        if schwab_connector.load_saved_tokens():
            # Connected - show accounts
            render_schwab_connected_accounts(schwab_connector, schwab_transformer, curr_month, curr_year)
        else:
            # Not connected - show authorization flow
            render_schwab_authorization(schwab_connector)
            
    except ImportError as e:
        st.error(f"Schwab integration not available: {e}")
        st.info("Make sure schwab-py is installed: `pip install schwab-py requests oauthlib`")
    except Exception as e:
        st.error(f"Failed to initialize Schwab connector: {e}")
        logger.error(f"Schwab initialization error: {e}", exc_info=True)


def render_schwab_setup_instructions() -> None:
    """Render Schwab Direct setup instructions."""
    st.info("🚀 **Schwab Direct API Setup Required**")
    
    st.markdown("### Step 1: Get Schwab Developer Credentials")
    st.markdown("1. Visit [Schwab Developer Portal](https://developer.schwab.com/)")
    st.markdown("2. Sign up for a developer account")
    st.markdown("3. Create a new application")
    st.markdown("4. Note your App Key and App Secret")
    
    st.markdown("### Step 2: Configure Environment Variables")
    st.markdown("Add to your `.env` file:")
    st.code("""
# Schwab API Credentials
SCHWAB_APP_KEY=your_app_key_here
SCHWAB_APP_SECRET=your_app_secret_here
SCHWAB_CALLBACK_URL=https://localhost:8080/callback

# Encryption Key (if not already set)
ENCRYPTION_KEY=your_encryption_key_here
""", language="bash")
    
    st.markdown("### Step 3: Restart Application")
    st.markdown("After setting up `.env` file, restart the Streamlit application.")
    
    st.markdown("---")
    st.markdown("### Benefits of Schwab Direct")
    st.markdown("- ✅ Real-time position data")
    st.markdown("- ✅ Complete transaction history")
    st.markdown("- ✅ Live market quotes")
    st.markdown("- ✅ More reliable connection")
    st.markdown("- ✅ No intermediary service")
    
    st.markdown("---")
    st.markdown("📖 **See [SCHWAB_INTEGRATION_GUIDE.md](SCHWAB_INTEGRATION_GUIDE.md) for complete setup instructions**")


def render_schwab_authorization(schwab_connector) -> None:
    """Render Schwab OAuth authorization flow."""
    st.markdown("### Connect Your Schwab Account")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Ready to connect?**")
        st.markdown("Click the button to start the secure OAuth authorization process.")
        st.markdown("You'll be redirected to Schwab to approve access.")
    
    with col2:
        if st.button("🔗 Authorize Schwab", type="primary", use_container_width=True):
            try:
                auth_url = schwab_connector.get_authorization_url()
                st.session_state.schwab_auth_url = auth_url
                st.session_state.schwab_awaiting_callback = True
                st.rerun()
            except Exception as e:
                st.error(f"Failed to generate authorization URL: {e}")
    
    # Show authorization URL if generated
    if st.session_state.get('schwab_awaiting_callback'):
        st.markdown("---")
        st.success("✅ Authorization URL generated!")
        st.markdown("**Step 1:** Click the link below to authorize:")
        st.markdown(f"[Authorize with Schwab]({st.session_state.schwab_auth_url})")
        
        st.markdown("**Step 2:** After authorizing, paste the callback URL here:")
        callback_url = st.text_input(
            "Callback URL",
            placeholder="https://localhost:8080/callback?code=...",
            help="Copy the full URL from your browser after authorization"
        )
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Complete Authorization", type="primary", use_container_width=True):
                if callback_url:
                    try:
                        success = schwab_connector.complete_authorization(callback_url)
                        if success:
                            st.success("✅ Successfully connected to Schwab!")
                            del st.session_state.schwab_auth_url
                            del st.session_state.schwab_awaiting_callback
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("Authorization failed. Please try again.")
                    except Exception as e:
                        st.error(f"Authorization failed: {e}")
                        logger.error(f"Schwab authorization error: {e}", exc_info=True)
                else:
                    st.warning("Please paste the callback URL")


def render_schwab_connected_accounts(schwab_connector, schwab_transformer, curr_month: int, curr_year: int) -> None:
    """Render connected Schwab accounts."""
    st.success("✅ Connected to Schwab Direct API")
    
    try:
        accounts = schwab_connector.get_accounts()
        
        st.markdown(f"### Connected Accounts ({len(accounts)})")
        
        for account in accounts:
            account_info = account.get('securitiesAccount', {})
            account_number = account_info.get('accountNumber', 'Unknown')
            account_type = account_info.get('type', 'Unknown')
            
            # Get balances
            current_balances = account_info.get('currentBalances', {})
            market_value = current_balances.get('liquidationValue', 0)
            cash_balance = current_balances.get('cashBalance', 0)
            
            with st.expander(f"🏦 Schwab {account_type} - ...{account_number[-4:]}", expanded=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.metric("Account Type", account_type.replace('_', ' ').title())
                    st.caption(f"Account: ...{account_number[-4:]}")
                
                with col2:
                    st.metric("Total Value", f"${market_value:,.2f}")
                    st.metric("Cash Balance", f"${cash_balance:,.2f}")
                
                with col3:
                    if st.button("🔄 Sync", key=f"sync_schwab_single_{account_number}", use_container_width=True):
                        sync_schwab_account(schwab_connector, schwab_transformer, curr_month, curr_year)
        
        # Sync all button
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Sync All Accounts", key="sync_schwab_all", type="primary", use_container_width=True):
                sync_schwab_account(schwab_connector, schwab_transformer, curr_month, curr_year)
        
        # Show merge button if holdings are synced
        if 'schwab_synced_holdings' in st.session_state:
            st.markdown("---")
            st.markdown("### 📊 Synced Holdings Preview")
            st.dataframe(st.session_state.schwab_synced_holdings, use_container_width=True, hide_index=True)
            
            col1, col2, col3 = st.columns([2, 1, 2])
            with col2:
                if st.button("💾 Merge with Portfolio", key="merge_schwab", type="primary", use_container_width=True):
                    try:
                        # Import merge function
                        from components.portfolio_connections import _merge_synced_holdings
                        
                        _merge_synced_holdings(
                            st.session_state.schwab_synced_holdings,
                            st.session_state.schwab_sync_month,
                            st.session_state.schwab_sync_year
                        )
                        st.success("✅ Holdings merged successfully!")
                        
                        # Clear session state
                        del st.session_state.schwab_synced_holdings
                        del st.session_state.schwab_sync_month
                        del st.session_state.schwab_sync_year
                        st.rerun()
                    except Exception as e:
                        st.error(f"Merge failed: {e}")
                        logger.error(f"Schwab merge error: {e}", exc_info=True)
        
        # Disconnect option
        st.markdown("---")
        with st.expander("⚙️ Advanced Options"):
            if st.button("🔌 Disconnect Schwab", key="disconnect_schwab", type="secondary"):
                schwab_connector.disconnect()
                st.success("Disconnected from Schwab")
                st.rerun()
            
    except Exception as e:
        st.error(f"Failed to load accounts: {e}")
        logger.error(f"Schwab account load error: {e}", exc_info=True)


def sync_schwab_account(schwab_connector, schwab_transformer, month: int, year: int) -> None:
    """Sync Schwab account positions."""
    with st.spinner("Syncing Schwab positions..."):
        try:
            # Get raw positions (automatically imports transactions)
            positions = schwab_connector.get_positions(
                import_transactions=True,
                transaction_days_back=365
            )

            if not positions:
                st.warning("No positions found")
                return

            # Transform all positions to portfolio format (including direct-index holdings)
            portfolio_df = schwab_transformer.transform_positions_to_portfolio(
                positions,
                enrich_with_transactions=True,
            )

            if portfolio_df.empty:
                st.warning("No holdings to sync")
                return

            # Check how many positions have purchase dates
            enriched_count = portfolio_df['purchase_date'].notna().sum()
            logger.info(f"Enriched {enriched_count} of {len(portfolio_df)} positions with purchase dates")

            # Store in session state
            st.session_state.schwab_synced_holdings = portfolio_df
            st.session_state.schwab_sync_month = month
            st.session_state.schwab_sync_year = year

            st.success(f"✅ Synced {len(portfolio_df)} holdings from Schwab")
            if enriched_count > 0:
                st.info(f"📅 Enriched {enriched_count} holdings with purchase dates from transaction history")
            st.info("📊 Scroll down to see holdings preview and merge button")

        except Exception as e:
            st.error(f"Sync failed: {e}")
            logger.error(f"Schwab sync error: {e}", exc_info=True)

# Made with Bob
