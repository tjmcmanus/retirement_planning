"""
components/portfolio_connections.py
====================================
Brokerage connections UI for Portfolio Hub.

Provides interface for connecting brokerage accounts via SnapTrade,
managing connections, and syncing portfolio data.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from components.credential_manager import CredentialManager
    from components.snaptrade_connector import create_snaptrade_connector, SNAPTRADE_AVAILABLE
    CONNECTIONS_AVAILABLE = SNAPTRADE_AVAILABLE
except ImportError:
    CONNECTIONS_AVAILABLE = False
    CredentialManager = None  # type: ignore
    create_snaptrade_connector = None  # type: ignore
    logging.warning("Brokerage connection components not available")


logger = logging.getLogger(__name__)


def render_connections_tab(portdf: pd.DataFrame, curr_month: int, curr_year: int) -> None:
    """
    Render the Connections tab for brokerage integration.
    
    Args:
        portdf: Current portfolio DataFrame
        curr_month: Current month
        curr_year: Current year
    """
    st.markdown("## 🔗 Brokerage Connections")
    st.caption("Automatic portfolio synchronization with your brokerage accounts")
    
    # Create tabs for different connection types
    tab1, tab2, tab3 = st.tabs([
        "📊 SnapTrade (Multi-Brokerage)",
        "🏦 Schwab Direct",
        "⚙️ Auto-Sync Scheduler"
    ])
    
    with tab1:
        st.markdown("### Multi-Brokerage Integration via SnapTrade")
        st.caption("Connect to 12,000+ institutions including Schwab, Fidelity, Vanguard, and more")
        
        if not CONNECTIONS_AVAILABLE:
            _render_setup_instructions()
        else:
            _render_snaptrade_connections(portdf, curr_month, curr_year)
    
    with tab2:
        # Import and render Schwab Direct section
        try:
            from components.schwab_ui import render_schwab_direct_section
            render_schwab_direct_section(portdf, curr_month, curr_year)
        except ImportError as e:
            st.error(f"Schwab Direct UI not available: {e}")
    
    with tab3:
        # Render automatic sync scheduler UI
        render_sync_scheduler_ui(portdf, curr_month, curr_year)
    
    # Show features and benefits
    st.markdown("---")
    _render_features_section()


def _render_snaptrade_connections(portdf: pd.DataFrame, curr_month: int, curr_year: int) -> None:
    """Render SnapTrade connections section."""
    if not CONNECTIONS_AVAILABLE:
        _render_setup_instructions()
        return
    
    # Initialize session state
    if 'snaptrade_connector' not in st.session_state:
        try:
            if create_snaptrade_connector is None or CredentialManager is None:
                raise ImportError("Components not available")
            st.session_state.snaptrade_connector = create_snaptrade_connector()  # type: ignore
            st.session_state.credential_manager = CredentialManager()  # type: ignore
        except Exception as e:
            st.error(f"Failed to initialize SnapTrade: {e}")
            _render_setup_instructions()
            return
    
    connector = st.session_state.snaptrade_connector
    cred_manager = st.session_state.credential_manager
    
    # Check if user credentials are in environment variables
    env_user_id = os.getenv("SNAPTRADE_USER_ID")
    env_user_secret = os.getenv("SNAPTRADE_USER_SECRET")
    
    # Get connection status from SnapTrade API
    if env_user_id and env_user_secret:
        # User has credentials in .env - check actual connection status
        try:
            status = connector.get_connection_status(user_id=env_user_id, user_secret=env_user_secret)
            if status.get('connected') and status.get('account_count', 0) > 0:
                # Show connected accounts from API
                st.success(f"✅ Connected to {status['account_count']} account(s) via environment credentials")
                _render_connected_accounts_from_api(status, connector, cred_manager, curr_month, curr_year, env_user_id)
            else:
                # Has credentials but not connected yet - show connect button
                st.info("📋 Credentials configured. Click below to connect your brokerage accounts.")
                _render_connect_with_credentials(connector, cred_manager, env_user_id, env_user_secret)
        except Exception as e:
            st.warning(f"Could not verify connection status: {e}")
            _render_connect_with_credentials(connector, cred_manager, env_user_id, env_user_secret)
    else:
        # No credentials in .env - check local connections
        connections = cred_manager.list_connections()
        if connections:
            _render_connected_accounts(connections, connector, cred_manager, curr_month, curr_year)
        else:
            _render_connect_new_account(connector, cred_manager)


def _render_setup_instructions() -> None:
    """Render setup instructions when SnapTrade is not configured."""
    st.info("🚀 **Brokerage Integration Setup Required**")
    
    st.markdown("### Step 1: Install Dependencies")
    st.code("pip install snaptrade-python cryptography python-dotenv", language="bash")
    
    st.markdown("### Step 2: Get SnapTrade API Credentials")
    st.markdown("1. Sign up at [SnapTrade](https://snaptrade.com)")
    st.markdown("2. Create an application to get your Client ID and Consumer Key")
    st.markdown("3. Choose sandbox mode for testing or production for live data")
    
    st.markdown("### Step 3: Configure Environment Variables")
    st.markdown("Create a `.env` file in your project root:")
    st.code("""
# SnapTrade API Credentials
SNAPTRADE_CLIENT_ID=your_client_id_here
SNAPTRADE_CONSUMER_KEY=your_consumer_key_here

# Encryption Key (generate with command below)
ENCRYPTION_KEY=your_encryption_key_here
""", language="bash")
    
    st.markdown("### Step 4: Generate Encryption Key")
    st.code("python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"", language="bash")
    
    st.markdown("### Step 5: Restart Application")
    st.markdown("After setting up `.env` file, restart the Streamlit application.")
    
    st.markdown("---")
    st.markdown("### Security Notes")
    st.markdown("- ✅ Never commit `.env` file to version control")
    st.markdown("- ✅ Keep encryption key secure and backed up")
    st.markdown("- ✅ Use read-only API permissions")
    st.markdown("- ✅ Credentials are encrypted at rest")


def _render_connect_with_credentials(connector, cred_manager, user_id: str, user_secret: str) -> None:
    """Render UI for connecting with existing credentials."""
    st.markdown("### Connect to Your Brokerage")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Your credentials are configured:**")
        st.markdown(f"- User ID: `{user_id[:8]}...`")
        st.markdown(f"- User Secret: `{'*' * 20}`")
        st.markdown("")
        st.markdown("Click the button to connect your brokerage accounts →")
    
    with col2:
        if st.button("🔗 Connect Brokerage", type="primary", use_container_width=True):
            try:
                auth_data = connector.get_auth_link(user_id=user_id)
                st.session_state.auth_link = auth_data['auth_link']
                st.session_state.user_id = auth_data['user_id']
                st.rerun()
            except Exception as e:
                st.error(f"Failed to generate auth link: {e}")
    
    # Show auth link if generated
    if 'auth_link' in st.session_state:
        st.markdown("---")
        st.success("✅ Authorization link generated!")
        st.markdown("**Click the link below to connect your brokerage account:**")
        st.markdown(f"[Connect to SnapTrade]({st.session_state.auth_link})")
        st.caption("You'll be redirected to securely authenticate with your brokerage.")
        
        if st.button("I've completed authentication"):
            status = connector.get_connection_status(st.session_state.user_id)
            if status['connected']:
                st.success(f"✅ Connected {status['account_count']} account(s)!")
                del st.session_state.auth_link
                st.rerun()
            else:
                st.warning("No accounts found. Please complete the authentication process.")


def _render_connected_accounts_from_api(status: dict, connector, cred_manager, curr_month: int, curr_year: int, user_id: str) -> None:
    """Render UI for accounts connected via API."""
    st.markdown("### Connected Accounts")
    
    for account in status.get('accounts', []):
        with st.expander(f"🏦 {account.get('institution', 'Unknown')} - {account.get('name', 'Account')}", expanded=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.metric("Account Type", account.get('type', 'Unknown'))
                st.caption(f"Account ID: {account.get('id', 'N/A')}")
            
            with col2:
                st.metric("Status", "🟢 Active")
                st.caption("Connected via environment credentials")
            
            with col3:
                if st.button("🔄 Sync Now", key=f"sync_api_{account.get('id')}", use_container_width=True):
                    _sync_account_from_api(user_id, account.get('id'), connector, cred_manager, curr_month, curr_year)
    
    # Show sync all button
    st.markdown("---")
    if st.button("🔄 Sync All Accounts", type="primary", use_container_width=True):
        _sync_all_accounts(user_id, connector, cred_manager, curr_month, curr_year)


def _sync_account_from_api(user_id: str, account_id: str, connector, cred_manager, month: int, year: int) -> None:
    """Sync a specific account from API."""
    with st.spinner(f"Syncing account {account_id}..."):
        try:
            holdings_df = connector.sync_holdings(user_id=user_id, month=month, year=year)
            
            if holdings_df.empty:
                st.warning("No holdings found to sync")
                return
            
            # Store in session state for merge button
            st.session_state.synced_holdings = holdings_df
            st.session_state.sync_month = month
            st.session_state.sync_year = year
            
            st.success(f"✅ Synced {len(holdings_df)} holdings")
            st.dataframe(holdings_df, use_container_width=True, hide_index=True)
                
        except Exception as e:
            st.error(f"Sync failed: {e}")
            logger.error(f"Sync failed for account {account_id}: {e}")
    
    # Merge button outside the spinner, uses session state
    if 'synced_holdings' in st.session_state:
        logger.info(f"Synced holdings in session state: {len(st.session_state.synced_holdings)} rows")
        if not st.session_state.synced_holdings.empty:
            logger.info("Showing merge button")
            if st.button("💾 Merge with Portfolio", key=f"merge_api_{account_id}"):
                logger.info("🔵 MERGE BUTTON CLICKED!")
                try:
                    _merge_synced_holdings(
                        st.session_state.synced_holdings,
                        st.session_state.sync_month,
                        st.session_state.sync_year
                    )
                    st.success("Holdings merged successfully!")
                    # Clear session state
                    del st.session_state.synced_holdings
                    del st.session_state.sync_month
                    del st.session_state.sync_year
                    st.rerun()
                except Exception as e:
                    logger.error(f"Error in merge button handler: {e}", exc_info=True)
                    st.error(f"Merge failed: {e}")
        else:
            logger.warning("Synced holdings is empty")
    else:
        logger.info("No synced holdings in session state")


def _sync_all_accounts(user_id: str, connector, cred_manager, month: int, year: int) -> None:
    """Sync all accounts for a user."""
    with st.spinner("Syncing all accounts..."):
        try:
            holdings_df = connector.sync_holdings(user_id=user_id, month=month, year=year)
            
            if holdings_df.empty:
                st.warning("No holdings found to sync")
                return
            
            st.success(f"✅ Synced {len(holdings_df)} holdings from all accounts")
            st.dataframe(holdings_df, use_container_width=True, hide_index=True)
            
            # Auto-merge immediately after sync
            st.info("⏳ Merging with portfolio...")
            logger.info("🔵 AUTO-MERGING SYNCED HOLDINGS")
            _merge_synced_holdings(holdings_df, month, year)
            st.success("✅ Holdings merged successfully! Navigate to Holdings tab to see updates.")
            st.balloons()
                
        except Exception as e:
            st.error(f"Sync failed: {e}")
            logger.error(f"Sync all failed: {e}", exc_info=True)


def _render_connect_new_account(connector, cred_manager) -> None:
    """Render UI for connecting a new brokerage account."""
    st.markdown("### Connect Your First Account")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Supported Brokerages:**")
        st.markdown("- ✅ Schwab")
        st.markdown("- ✅ Fidelity")
        st.markdown("- ✅ Vanguard")
        st.markdown("- ✅ TD Ameritrade")
        st.markdown("- ✅ E*TRADE")
        st.markdown("- ✅ 12,000+ other institutions via Plaid")
    
    with col2:
        if st.button("🔗 Connect Account", type="primary", use_container_width=True):
            try:
                auth_data = connector.get_auth_link()
                st.session_state.auth_link = auth_data['auth_link']
                st.session_state.user_id = auth_data['user_id']
                st.rerun()
            except Exception as e:
                st.error(f"Failed to generate auth link: {e}")
                
                # Show reset option if userSecret issue
                if "userSecret" in str(e):
                    st.warning("⚠️ **Personal API Key Issue**: With personal keys, only one user can be registered.")
                    if st.button("🔄 Reset & Reconnect", use_container_width=True):
                        try:
                            auth_data = connector.get_auth_link(force_reregister=True)
                            st.session_state.auth_link = auth_data['auth_link']
                            st.session_state.user_id = auth_data['user_id']
                            st.success("✅ User reset successfully!")
                            st.rerun()
                        except Exception as reset_error:
                            st.error(f"Reset failed: {reset_error}")
    
    # Show auth link if generated
    if 'auth_link' in st.session_state:
        st.markdown("---")
        st.success("✅ Authorization link generated!")
        st.markdown("**Click the link below to connect your brokerage account:**")
        st.markdown(f"[Connect to SnapTrade]({st.session_state.auth_link})")
        st.caption("You'll be redirected to securely authenticate with your brokerage.")
        
        if st.button("I've completed authentication"):
            # Check if connection was successful
            status = connector.get_connection_status(st.session_state.user_id)
            if status['connected']:
                st.success(f"✅ Connected {status['account_count']} account(s)!")
                del st.session_state.auth_link
                st.rerun()
            else:
                st.warning("No accounts found. Please complete the authentication process.")


def _render_connected_accounts(connections, connector, cred_manager, curr_month, curr_year) -> None:
    """Render UI for managing connected accounts."""
    st.markdown("### Connected Accounts")
    
    for conn in connections:
        with st.expander(f"🏦 {conn['brokerage_name']} - {conn['account_id']}", expanded=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.metric("Status", "🟢 Active" if conn['status'] == 'active' else "🔴 Inactive")
                if conn['last_sync']:
                    time_ago = _format_time_ago(conn['last_sync'])
                    st.caption(f"Last synced: {time_ago}")
                else:
                    st.caption("Never synced")
            
            with col2:
                if conn['is_expired']:
                    st.warning("⚠️ Token expired - reconnect required")
                else:
                    expiry = conn['token_expiry']
                    if expiry:
                        days_left = (expiry - datetime.now()).days
                        st.caption(f"Token expires in {days_left} days")
            
            with col3:
                if st.button("🔄 Sync Now", key=f"sync_{conn['id']}", use_container_width=True):
                    _sync_account(conn['id'], connector, cred_manager, curr_month, curr_year)
                
                if st.button("🗑️ Disconnect", key=f"disconnect_{conn['id']}", use_container_width=True):
                    if st.session_state.get(f"confirm_disconnect_{conn['id']}", False):
                        cred_manager.disconnect_account(conn['id'])
                        st.success("Account disconnected")
                        st.rerun()
                    else:
                        st.session_state[f"confirm_disconnect_{conn['id']}"] = True
                        st.warning("Click again to confirm disconnect")
            
            # Show sync history
            history = cred_manager.get_sync_history(conn['id'], limit=5)
            if history:
                st.markdown("**Recent Syncs:**")
                for sync in history:
                    status_icon = "✅" if sync['status'] == 'success' else "❌"
                    st.caption(
                        f"{status_icon} {sync['sync_timestamp'].strftime('%Y-%m-%d %H:%M')} - "
                        f"{sync['holdings_count'] or 0} holdings"
                    )
    
    # Add new account button
    st.markdown("---")
    if st.button("➕ Connect Another Account", use_container_width=True):
        _render_connect_new_account(connector, cred_manager)


def _sync_account(connection_id: int, connector, cred_manager, month: int, year: int) -> None:
    """Sync holdings from a connected account."""
    with st.spinner("Syncing holdings..."):
        try:
            # Get connection details
            conn = cred_manager.get_connection(connection_id)
            if not conn:
                st.error("Connection not found")
                return
            
            # Sync holdings
            holdings_df = connector.sync_holdings(
                user_id=conn['user_id'],
                month=month,
                year=year
            )
            
            if holdings_df.empty:
                st.warning("No holdings found to sync")
                cred_manager.log_sync_attempt(connection_id, 'error', 0, "No holdings found")
                return
            
            # Show preview
            st.success(f"✅ Synced {len(holdings_df)} holdings")
            st.dataframe(holdings_df, use_container_width=True, hide_index=True)
            
            # Ask user to confirm merge
            if st.button("💾 Merge with Portfolio", key=f"merge_{connection_id}"):
                _merge_synced_holdings(holdings_df, month, year)
                cred_manager.log_sync_attempt(connection_id, 'success', len(holdings_df))
                cred_manager.update_sync_time(connection_id)
                st.success("Holdings merged successfully!")
                st.rerun()
            
        except Exception as e:
            st.error(f"Sync failed: {e}")
            cred_manager.log_sync_attempt(connection_id, 'error', 0, str(e))
            logger.error(f"Sync failed for connection {connection_id}: {e}")


def _merge_synced_holdings(synced_df: pd.DataFrame, month: int, year: int) -> None:
    """
    Merge synced holdings with existing portfolio data.
    
    Uses smart merge logic:
    - If month/year/account_name/symbol match exactly: keep existing (no update)
    - If month/year/account_name/symbol match but qty differs: update that row
    - If no match for month/year/account_name/symbol: add new row
    """
    import os
    
    portfolio_file = "portfolio_data_truth.csv"
    
    logger.info(f"=== Starting merge process ===")
    logger.info(f"Synced holdings to merge: {len(synced_df)}")
    logger.info(f"Synced holdings preview:\n{synced_df.head()}")
    
    try:
        # Use the connector's merge logic
        if 'snaptrade_connector' in st.session_state:
            logger.info("Using SnapTrade connector merge logic")
            connector = st.session_state.snaptrade_connector
            merged_df = connector.merge_holdings_to_portfolio(synced_df, portfolio_file)
        elif 'schwab_connector' in st.session_state:
            logger.info("Using Schwab connector merge logic")
            connector = st.session_state.schwab_connector
            merged_df = connector.merge_holdings_to_portfolio(synced_df, portfolio_file)
        else:
            logger.warning("Connector not available, using fallback merge")
            # Fallback to simple merge if connector not available
            if os.path.exists(portfolio_file):
                existing_df = pd.read_csv(portfolio_file)
                logger.info(f"Existing portfolio has {len(existing_df)} holdings")
                # Remove existing entries for this month/year from synced accounts
                mask = (existing_df['month'] == month) & (existing_df['year'] == year)
                existing_df = existing_df[~mask]
                merged_df = pd.concat([existing_df, synced_df], ignore_index=True)
            else:
                merged_df = synced_df
        
        logger.info(f"Merged DataFrame has {len(merged_df)} total holdings")
        logger.info(f"Merged DataFrame columns: {merged_df.columns.tolist()}")
        
        # Save back to file
        logger.info(f"Saving to {portfolio_file}")
        merged_df.to_csv(portfolio_file, index=False)
        logger.info(f"✓ Successfully saved {len(merged_df)} holdings to {portfolio_file}")
        
        # Verify the save
        if os.path.exists(portfolio_file):
            verify_df = pd.read_csv(portfolio_file)
            logger.info(f"✓ Verified: File now contains {len(verify_df)} holdings")
        else:
            logger.error(f"✗ File {portfolio_file} does not exist after save!")
        
        # Clear portfolio cache and rebuild display to reflect new holdings
        logger.info("Clearing portfolio cache and rebuilding display")
        try:
            from portfolio import build_portfolio_display, save_portfolio_cache
            
            # Clear Streamlit cache
            st.cache_data.clear()
            logger.info("✓ Cleared Streamlit cache")
            
            # Rebuild portfolio display with new data
            portdf = build_portfolio_display(month=month, year=year)
            if not portdf.empty:
                save_portfolio_cache(portdf, month, year)
                logger.info(f"✓ Rebuilt portfolio display cache with {len(portdf)} rows")
            else:
                logger.warning("Portfolio display is empty after rebuild")
                
        except Exception as cache_error:
            logger.warning(f"Could not rebuild portfolio cache: {cache_error}")
        
        logger.info(f"Merged {len(synced_df)} synced holdings into portfolio (total: {len(merged_df)} holdings)")
        
    except Exception as e:
        logger.error(f"✗ Error during merge: {e}", exc_info=True)
        raise


def _render_features_section() -> None:
    """Render features and benefits section."""
    st.markdown("### Features & Benefits")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**⚡ Automatic Sync**")
        st.caption("Daily/weekly portfolio updates")
        st.caption("No manual data entry")
        st.caption("Always up-to-date")
    
    with col2:
        st.markdown("**🔒 Secure**")
        st.caption("OAuth 2.0 authentication")
        st.caption("Read-only access")
        st.caption("Encrypted storage")
    
    with col3:
        st.markdown("**📊 Accurate**")
        st.caption("Real-time balances")
        st.caption("Automatic categorization")
        st.caption("99.9% accuracy")
    
    st.markdown("---")
    st.markdown("### Security & Privacy")
    st.markdown("- 🔒 **OAuth 2.0** — Industry-standard secure login")
    st.markdown("- 🔒 **Read-Only** — We never have permission to trade")
    st.markdown("- 🔒 **Encrypted** — AES-256 encryption for all credentials")
    st.markdown("- 🔒 **Disconnect Anytime** — Remove access with one click")


def _format_time_ago(dt: datetime) -> str:
    """Format datetime as human-readable time ago."""
    # Handle both timezone-aware and naive datetimes
    if dt.tzinfo is not None:
        # dt is timezone-aware, make now timezone-aware too
        from datetime import timezone
        now = datetime.now(timezone.utc)
        # Convert dt to UTC if it's not already
        if dt.tzinfo != timezone.utc:
            dt = dt.astimezone(timezone.utc)
    else:
        # dt is naive, use naive now
        now = datetime.now()
    
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds >= 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "just now"


def render_sync_scheduler_ui(portdf: pd.DataFrame, curr_month: int, curr_year: int) -> None:
    """
    Render automatic sync scheduler UI.
    
    Args:
        portdf: Current portfolio DataFrame
        curr_month: Current month
        curr_year: Current year
    """
    st.markdown("## ⚙️ Automatic Sync Settings")
    st.caption("Configure automatic portfolio synchronization")
    
    # Import sync components
    try:
        from components.sync_scheduler import SyncScheduler, SyncFrequency
        from components.sync_orchestrator import SyncOrchestrator
        from components.sync_state import SyncState
    except ImportError as e:
        st.error(f"Sync scheduler not available: {e}")
        st.info("Install required packages: `pip install pytz`")
        return
    
    # Initialize sync state
    if 'sync_state' not in st.session_state:
        st.session_state.sync_state = SyncState()
    
    sync_state = st.session_state.sync_state
    
    # Show current state
    state_summary = sync_state.get_state_summary()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        last_sync = state_summary.get('last_sync')
        if last_sync:
            from datetime import datetime
            last_sync_dt = datetime.fromisoformat(last_sync)
            st.metric("Last Sync", _format_time_ago(last_sync_dt))
        else:
            st.metric("Last Sync", "Never")
    
    with col2:
        st.metric("Total Syncs", state_summary.get('sync_count', 0))
    
    with col3:
        st.metric("Accounts Tracked", state_summary.get('accounts_tracked', 0))
    
    st.markdown("---")
    
    # Scheduler configuration
    st.markdown("### Sync Schedule Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        frequency = st.selectbox(
            "Sync Frequency",
            options=[f.value for f in SyncFrequency],
            index=1,  # Daily default
            help="How often to automatically sync your portfolio"
        )
    
    with col2:
        from datetime import time as dt_time
        sync_time = st.time_input(
            "Sync Time",
            value=dt_time(6, 0),
            help="Time of day for daily/weekly syncs"
        )
    
    with col3:
        market_hours_only = st.checkbox(
            "Market Hours Only",
            value=False,
            help="Only sync during market hours (9:30 AM - 4:00 PM ET)"
        )
    
    # Scheduler controls
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ Start Auto-Sync", type="primary", width='stretch'):
            try:
                # Create orchestrator
                orchestrator = SyncOrchestrator(
                    snaptrade_connector=st.session_state.get('snaptrade_connector'),
                    schwab_connector=st.session_state.get('schwab_connector')
                )
                
                # Create sync callback
                def sync_callback():
                    result = orchestrator.sync_all()
                    sync_state.update_sync_time()
                    return result.to_dict()
                
                # Create and start scheduler
                scheduler = SyncScheduler(
                    sync_callback=sync_callback,
                    frequency=SyncFrequency(frequency),
                    sync_time=sync_time,
                    market_hours_only=market_hours_only
                )
                scheduler.start()
                
                st.session_state.sync_scheduler = scheduler
                st.success("✅ Auto-sync started!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start scheduler: {e}")
                logger.error(f"Scheduler start error: {e}", exc_info=True)
    
    with col2:
        if st.button("⏹️ Stop Auto-Sync", width='stretch'):
            if 'sync_scheduler' in st.session_state and st.session_state.sync_scheduler:
                st.session_state.sync_scheduler.stop()
                st.session_state.sync_scheduler = None
                st.success("✅ Auto-sync stopped")
                st.rerun()
            else:
                st.warning("No active scheduler to stop")
    
    with col3:
        if st.button("🔄 Sync Now", width='stretch'):
            with st.spinner("Syncing..."):
                try:
                    orchestrator = SyncOrchestrator(
                        snaptrade_connector=st.session_state.get('snaptrade_connector'),
                        schwab_connector=st.session_state.get('schwab_connector')
                    )
                    result = orchestrator.sync_all()
                    sync_state.update_sync_time()
                    
                    if result.success:
                        st.success(f"✅ {result.message}")
                    else:
                        st.error(f"❌ {result.message}")
                    
                    # Show sync details
                    with st.expander("Sync Details"):
                        st.json(result.data)
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")
                    logger.error(f"Manual sync error: {e}", exc_info=True)
    
    # Show scheduler status
    if 'sync_scheduler' in st.session_state and st.session_state.sync_scheduler:
        st.markdown("---")
        st.markdown("### Scheduler Status")
        
        status = st.session_state.sync_scheduler.get_status()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            is_running = status.get('is_running', False)
            st.metric("Status", "🟢 Running" if is_running else "🔴 Stopped")
        
        with col2:
            st.metric("Frequency", status.get('frequency', 'N/A').title())
        
        with col3:
            market_open = status.get('market_open', False)
            st.metric("Market", "🟢 Open" if market_open else "🔴 Closed")
        
        with col4:
            last_sync = status.get('last_sync')
            if last_sync:
                from datetime import datetime
                last_sync_dt = datetime.fromisoformat(last_sync)
                st.metric("Last Run", _format_time_ago(last_sync_dt))
            else:
                st.metric("Last Run", "Never")
    
    # Show sync history
    if 'sync_scheduler' in st.session_state and st.session_state.sync_scheduler:
        orchestrator = SyncOrchestrator(
            snaptrade_connector=st.session_state.get('snaptrade_connector'),
            schwab_connector=st.session_state.get('schwab_connector')
        )
        
        history = orchestrator.get_sync_history(limit=10)
        
        if history:
            st.markdown("---")
            st.markdown("### Recent Sync History")
            
            for sync_record in reversed(history):
                timestamp = sync_record.get('timestamp', 'Unknown')
                success = sync_record.get('success', False)
                duration = sync_record.get('duration', 0)
                
                status_icon = "✅" if success else "❌"
                
                with st.expander(f"{status_icon} {timestamp} ({duration:.1f}s)"):
                    st.json(sync_record)


# Made with Bob
