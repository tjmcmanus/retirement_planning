"""
Transaction History UI Components
Provides user interface for transaction import, viewing, and analysis
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from components.transaction_importer import TransactionImporter
from components.credential_manager import CredentialManager
import logging

logger = logging.getLogger(__name__)


def _calculate_gains_losses(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate cost basis and gains/losses for transactions using FIFO method.
    Supports both stocks and options trading.
    
    Args:
        transactions_df: DataFrame with transactions
        
    Returns:
        DataFrame with added gain_loss, term, and wash_sale columns
    """
    if transactions_df.empty:
        return transactions_df
    
    logger.info(f"Calculating gains/losses for {len(transactions_df)} transactions")
    
    def is_option(symbol):
        """
        Detect if a symbol is an option.
        Options format: "TICKER  YYMMDDCPSTRIKE" (e.g., "SOFI  260123P00027000")
        """
        if not symbol or not isinstance(symbol, str):
            return False
        # Options have spaces and date/strike format
        return '  ' in symbol and len(symbol) > 15
    
    def get_option_multiplier(symbol):
        """
        Get the multiplier for options (typically 100 shares per contract).
        """
        return 100 if is_option(symbol) else 1
    
    def parse_option_symbol(symbol):
        """
        Parse option symbol to extract underlying, expiration, type, and strike.
        Format: "TICKER  YYMMDDCPSTRIKE"
        Example: "SOFI  260123P00027000" = SOFI Put expiring 2026-01-23 strike $27
        """
        if not is_option(symbol):
            return None
        
        parts = symbol.split('  ')
        if len(parts) != 2:
            return None
        
        ticker = parts[0].strip()
        option_code = parts[1].strip()
        
        if len(option_code) < 15:
            return None
        
        # Parse: YYMMDD C/P STRIKE
        date_str = option_code[:6]  # YYMMDD
        option_type = option_code[6]  # C or P
        strike_str = option_code[7:]  # Strike price (8 digits)
        
        try:
            # Convert strike: 00027000 = $27.00
            strike = float(strike_str) / 1000
            
            return {
                'underlying': ticker,
                'expiration': date_str,
                'type': 'CALL' if option_type == 'C' else 'PUT',
                'strike': strike,
                'full_symbol': symbol
            }
        except (ValueError, IndexError):
            return None
    
    # Initialize columns
    if 'gain_loss' not in transactions_df.columns:
        transactions_df['gain_loss'] = 0.0
    if 'term' not in transactions_df.columns:
        transactions_df['term'] = ''
    if 'wash_sale' not in transactions_df.columns:
        transactions_df['wash_sale'] = False
    if 'wash_sale_adjustment' not in transactions_df.columns:
        transactions_df['wash_sale_adjustment'] = 0.0
    
    # Ensure date column is datetime
    if 'date' in transactions_df.columns:
        transactions_df['date'] = pd.to_datetime(transactions_df['date'])
    
    # Log transaction types
    if 'type' in transactions_df.columns:
        type_counts = transactions_df['type'].value_counts()
        logger.info(f"Transaction types: {dict(type_counts)}")
    
    # Group by account_id and symbol for proper lot tracking
    group_cols = ['symbol']
    if 'account_id' in transactions_df.columns:
        group_cols = ['account_id', 'symbol']
    
    total_gains_calculated = 0
    
    for group_key, group_df in transactions_df.groupby(group_cols):
        if isinstance(group_key, tuple):
            account_id, symbol = group_key
        else:
            symbol = group_key
            account_id = None
        
        # Skip if no symbol
        if not symbol or (isinstance(symbol, str) and symbol.strip() == ''):
            continue
        
        # Sort by date
        group_df = group_df.sort_values('date')
        
        # Track purchase lots (FIFO)
        lots = []
        
        # Get option multiplier for this symbol
        multiplier = get_option_multiplier(symbol)
        is_opt = is_option(symbol)
        
        if is_opt:
            logger.info(f"Detected option: {symbol}, multiplier: {multiplier}")
        
        for idx, row in group_df.iterrows():
            trans_type = row['type'].upper() if isinstance(row['type'], str) else ''
            
            # For options: BUY = Sell to Open (credit), SELL = Buy to Close (debit)
            # We need to match "Sell to Open" with "Buy to Close"
            if trans_type in ['BUY', 'BUY TO CLOSE']:
                # Add to lots (opening position)
                lot = {
                    'date': row['date'],
                    'quantity': abs(row['quantity']),
                    'price': abs(row['price']) * multiplier,  # Apply multiplier for options
                    'remaining': abs(row['quantity'])
                }
                lots.append(lot)
                logger.debug(f"Added lot for {symbol}: {lot['quantity']} @ ${lot['price']}")
            
            elif trans_type in ['SELL', 'SELL TO OPEN']:
                # Calculate gain/loss using FIFO (closing position)
                sell_quantity = abs(row['quantity'])
                sell_price = abs(row['price']) * multiplier  # Apply multiplier for options
                sell_date = row['date']
                
                logger.debug(f"Processing {trans_type}: {symbol} {sell_quantity} @ ${sell_price}, {len(lots)} lots available")
                
                total_cost = 0.0
                total_days = 0
                quantity_matched = 0
                
                # Match with purchase lots (FIFO)
                for lot in lots:
                    if quantity_matched >= sell_quantity:
                        break
                    
                    if lot['remaining'] <= 0:
                        continue
                    
                    # Use quantity from this lot
                    qty_from_lot = min(lot['remaining'], sell_quantity - quantity_matched)
                    
                    # Calculate cost
                    cost_from_lot = qty_from_lot * lot['price']
                    total_cost += cost_from_lot
                    
                    # Calculate holding period
                    days_held = (sell_date - lot['date']).days
                    total_days += days_held * qty_from_lot
                    
                    # Update lot
                    lot['remaining'] -= qty_from_lot
                    quantity_matched += qty_from_lot
                    
                    logger.debug(f"Matched {qty_from_lot} from lot @ ${lot['price']}, cost: ${cost_from_lot}")
                
                # Calculate gain/loss
                if quantity_matched > 0:
                    proceeds = sell_quantity * sell_price
                    gain_loss = proceeds - total_cost
                    
                    # Calculate average holding period
                    avg_holding_period = int(total_days / quantity_matched) if quantity_matched > 0 else 0
                    term = 'LONG' if avg_holding_period > 365 else 'SHORT'
                    
                    # Update transaction
                    transactions_df.at[idx, 'gain_loss'] = gain_loss
                    transactions_df.at[idx, 'term'] = term
                    
                    total_gains_calculated += 1
                    logger.info(f"Calculated gain for {symbol}: ${gain_loss:.2f} ({term}), proceeds: ${proceeds:.2f}, cost: ${total_cost:.2f}")
                else:
                    logger.warning(f"No matching lots found for {trans_type} of {symbol}")
    
    logger.info(f"Calculated gains for {total_gains_calculated} sell transactions")
    return transactions_df


# Helper functions for creating instances (must be at module level for import)
def create_transaction_importer(connector):
    """
    Create a TransactionImporter instance.
    
    Args:
        connector: SnapTrade or Schwab connector
        
    Returns:
        TransactionImporter instance
    """
    try:
        cred_mgr = CredentialManager()
        return TransactionImporter(cred_mgr)
    except Exception as e:
        logger.error(f"Failed to create transaction importer: {e}")
        raise


def create_transaction_storage():
    """
    Create a TransactionStorage instance.
    
    Returns:
        TransactionStorage instance or None if not available
    """
    try:
        from components.transaction_storage import TransactionStorage
        return TransactionStorage()
    except ImportError:
        logger.warning("TransactionStorage not available")
        return None
    except Exception as e:
        logger.error(f"Failed to create transaction storage: {e}")
        return None


def render_transaction_history_tab(
    connector,
    transaction_importer,
    transaction_storage,
    user_id: str = "default"
):
    """
    Render the transaction history tab with import and viewing capabilities.
    
    Args:
        connector: SnapTrade or Schwab connector instance
        transaction_importer: TransactionImporter instance
        transaction_storage: TransactionStorage instance
        user_id: User identifier
    """
    st.markdown("## 💳 Transaction History")
    st.caption("Import and analyze your investment transactions")
    
    # First, check if we have transactions in the database
    if transaction_storage:
        try:
            transaction_storage.backfill_account_names(user_id=user_id)
            all_transactions = transaction_storage.get_transactions(user_id=user_id)
            logger.info(f"Loaded {len(all_transactions)} transactions from database")
            
            if len(all_transactions) > 0:
                st.success(f"📊 Found {len(all_transactions)} transactions in database (automatically imported from Schwab)")
                
                # Rename columns to match expected format
                column_mapping = {
                    'transaction_date': 'date',
                    'transaction_type': 'type',
                    'transaction_id': 'id',
                    'account_name': 'account_name',
                    'account_id': 'account_id'
                }
                all_transactions = all_transactions.rename(columns=column_mapping)
                
                # Calculate cost basis and gains/losses
                logger.info("Calculating cost basis and gains/losses...")
                all_transactions = _calculate_gains_losses(all_transactions)
                
                st.session_state['imported_transactions'] = all_transactions
                logger.info(f"Stored {len(all_transactions)} transactions with calculated gains in session state")
            else:
                st.info("ℹ️ No transactions found. Transactions are automatically imported when you sync Schwab accounts in the **🔗 Connections** tab")
        except Exception as e:
            logger.error(f"Could not load transactions from database: {e}", exc_info=True)
            st.error(f"Error loading transactions: {e}")
    
    # Get connected accounts for manual import
    try:
        from components.credential_manager import CredentialManager
        cred_mgr = CredentialManager()
        connections = cred_mgr.list_connections(user_id=user_id)
        
        if not connections:
            # No connections, but we might have transactions from Schwab auto-import
            if 'imported_transactions' not in st.session_state or st.session_state['imported_transactions'].empty:
                st.info("👆 Transactions are automatically imported when you sync Schwab accounts in the **🔗 Connections** tab")
                return
            # else: continue to display section below
        
        # Manual import UI (only shown if connections exist)
        if connections:
            # Account selector
            account_options = [
                f"{conn['brokerage_name']} - {conn['account_id']}"
                for conn in connections
            ]
            
            selected_account = st.selectbox(
                "Select Account",
                options=account_options,
                key="txn_account_selector"
            )
        
            if not selected_account:
                return
            
            # Get selected connection details
            conn_idx = account_options.index(selected_account)
            connection = connections[conn_idx]
            
            # Date range selector
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                start_date = st.date_input(
                    "Start Date",
                    value=datetime.now() - timedelta(days=365),
                    key="txn_start_date"
                )
            
            with col2:
                end_date = st.date_input(
                    "End Date",
                    value=datetime.now(),
                    key="txn_end_date"
                )
            
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                import_button = st.button("📥 Import Transactions", type="primary", use_container_width=True)
            
            # Import transactions
            if import_button:
                selected_connector = connector
                if connection['brokerage_name'] == 'Schwab':
                    selected_connector = st.session_state.get("schwab_connector")

                if not transaction_importer or not selected_connector:
                    provider_name = connection['brokerage_name']
                    st.error(f"Transaction importer not available for {provider_name}. Please ensure that connector is properly configured.")
                    return
                    
                with st.spinner("Importing transactions..."):
                    try:
                        # Get user secret from connection
                        conn_details = cred_mgr.get_connection(connection['id'])
                        if conn_details:
                            user_secret = conn_details.get('access_token', '')
                        else:
                            user_secret = ''
                        
                        if connection['brokerage_name'] != 'Schwab' and not user_secret:
                            st.error("Failed to retrieve account credentials")
                            return
                        
                        transactions_df = transaction_importer.import_transactions(
                            connector=selected_connector,
                            user_id=user_id,
                            user_secret=user_secret,
                            account_id=connection['account_id'],
                            start_date=start_date.strftime('%Y-%m-%d'),
                            end_date=end_date.strftime('%Y-%m-%d')
                        )
                        
                        if not transactions_df.empty:
                            st.success(f"✅ Imported {len(transactions_df)} transactions")
                            
                            # Store in session state for display
                            st.session_state['imported_transactions'] = transactions_df
                            st.session_state['import_account'] = selected_account
                            
                            # Optionally store in database
                            if transaction_storage:
                                try:
                                    transaction_storage.store_transactions(
                                        user_id=user_id,
                                        account_id=connection['account_id'],
                                        transactions_df=transactions_df
                                    )
                                    st.success("💾 Transactions saved to database")
                                except Exception as e:
                                    logger.warning(f"Could not save to database: {e}")
                        else:
                            st.warning("No transactions found for the selected period")
                    
                    except Exception as e:
                        st.error(f"Failed to import transactions: {e}")
                        logger.error(f"Transaction import error: {e}", exc_info=True)
        
        # Display imported transactions
        if 'imported_transactions' in st.session_state and not st.session_state['imported_transactions'].empty:
            st.markdown("---")
            st.markdown("### 📊 Transaction History")
            
            transactions_df = st.session_state['imported_transactions']
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Transactions", len(transactions_df))
            
            with col2:
                buys = len(transactions_df[transactions_df['type'] == 'BUY'])
                st.metric("Buy Transactions", buys)
            
            with col3:
                sells = len(transactions_df[transactions_df['type'] == 'SELL'])
                st.metric("Sell Transactions", sells)
            
            with col4:
                total_gain_loss = transactions_df['gain_loss'].sum()
                st.metric(
                    "Total Gains/Losses",
                    f"${total_gain_loss:,.2f}",
                    delta=f"${total_gain_loss:,.2f}" if total_gain_loss != 0 else None
                )
            
            # Transaction table
            st.markdown("#### Transaction Details")
            
            # Format for display - prefer friendly account_name when available
            account_column = 'account_name' if 'account_name' in transactions_df.columns else 'account_id'
            display_columns = ['date', account_column, 'type', 'symbol', 'quantity', 'price',
                             'amount', 'gain_loss', 'term', 'wash_sale']
            
            # Only include columns that exist in the dataframe
            available_columns = [col for col in display_columns if col in transactions_df.columns]
            display_df = transactions_df[available_columns].copy()
            
            # Format columns
            if 'date' in display_df.columns:
                display_df['date'] = pd.to_datetime(display_df['date']).dt.strftime('%Y-%m-%d')
            if 'quantity' in display_df.columns:
                display_df['quantity'] = display_df['quantity'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "")
            if 'price' in display_df.columns:
                display_df['price'] = display_df['price'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "")
            if 'amount' in display_df.columns:
                display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "")
            if 'gain_loss' in display_df.columns:
                display_df['gain_loss'] = display_df['gain_loss'].apply(
                    lambda x: f"${x:,.2f}" if pd.notna(x) and x != 0 else "-"
                )
            if 'wash_sale' in display_df.columns:
                display_df['wash_sale'] = display_df['wash_sale'].apply(lambda x: "⚠️ Yes" if x else "")
            
            # Rename columns for better display
            column_names = {
                'date': 'Date',
                'account_id': 'Account',
                'account_name': 'Account',
                'type': 'Type',
                'symbol': 'Symbol',
                'quantity': 'Quantity',
                'price': 'Price',
                'amount': 'Amount',
                'gain_loss': 'Gain/Loss',
                'term': 'Term',
                'wash_sale': 'Wash Sale'
            }
            display_df = display_df.rename(columns={k: v for k, v in column_names.items() if k in display_df.columns})
            
            # Display with filtering
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400
            )
            
            # Export button
            col1, col2 = st.columns([1, 4])
            with col1:
                csv = transactions_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"transactions_{start_date}_{end_date}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            # Tax report (only if transaction_importer is available)
            if transaction_importer:
                st.markdown("---")
                st.markdown("### 📊 Tax Summary")
                
                tax_year = st.selectbox(
                    "Tax Year",
                    options=list(range(datetime.now().year, datetime.now().year - 5, -1)),
                    key="txn_tax_year"
                )
                
                tax_report = transaction_importer.generate_tax_report(transactions_df, tax_year)
            else:
                # Create a temporary importer for tax report generation
                st.markdown("---")
                st.markdown("### 📊 Tax Summary")
                
                tax_year = st.selectbox(
                    "Tax Year",
                    options=list(range(datetime.now().year, datetime.now().year - 5, -1)),
                    key="txn_tax_year"
                )
                
                # Simple tax summary without full importer
                st.info("💡 Tax reporting requires transaction importer. Showing basic summary.")
                
                # Calculate basic metrics from transactions
                year_transactions = transactions_df[
                    pd.to_datetime(transactions_df['date']).dt.year == tax_year
                ]
                
                tax_report = {
                    'short_term_gains': 0,
                    'long_term_gains': 0,
                    'dividend_income': 0,
                    'interest_income': 0,
                    'wash_sale_adjustments': 0
                }
                
                # Sum up amounts by type
                if len(year_transactions) > 0:
                    sells = year_transactions[year_transactions['type'] == 'SELL']
                    if len(sells) > 0 and 'gain_loss' in sells.columns:
                        tax_report['short_term_gains'] = sells['gain_loss'].sum()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Short-Term Gains",
                    f"${tax_report['short_term_gains']:,.2f}",
                    delta=f"${tax_report['short_term_gains']:,.2f}" if tax_report['short_term_gains'] != 0 else None
                )
            
            with col2:
                st.metric(
                    "Long-Term Gains",
                    f"${tax_report['long_term_gains']:,.2f}",
                    delta=f"${tax_report['long_term_gains']:,.2f}" if tax_report['long_term_gains'] != 0 else None
                )
            
            with col3:
                st.metric(
                    "Dividend Income",
                    f"${tax_report['dividend_income']:,.2f}"
                )
            
            with col4:
                st.metric(
                    "Wash Sale Adjustments",
                    f"${tax_report['wash_sale_adjustments']:,.2f}"
                )
            
            # Detailed tax breakdown
            with st.expander("📋 Detailed Tax Report"):
                st.json(tax_report)
    
    except Exception as e:
        st.error(f"Error loading transaction history: {e}")
        logger.error(f"Transaction history error: {e}", exc_info=True)


def render_cost_basis_tab(transaction_storage, user_id: str = "default"):
    """
    Render the cost basis tab showing cost basis tracking and lot details.
    
    Args:
        transaction_storage: TransactionStorage instance
        user_id: User identifier
    """
    st.markdown("## 💰 Cost Basis Tracking")
    st.caption("Track cost basis and tax lots for your holdings")
    
    try:
        # Load transactions from database
        if transaction_storage:
            transactions = transaction_storage.get_transactions(user_id=user_id)
            
            if len(transactions) == 0:
                st.info("🚀 **Cost Basis Feature Available** — Import transactions to see cost basis details")
                
                st.markdown("### Features")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Cost Basis Methods:**")
                    st.markdown("- ✅ FIFO (First In, First Out)")
                    st.markdown("- ✅ LIFO (Last In, First Out)")
                    st.markdown("- ✅ Specific Lot Identification")
                    st.markdown("- ✅ Average Cost (mutual funds)")
                
                with col2:
                    st.markdown("**Tracking Features:**")
                    st.markdown("- ✅ Lot-level tracking")
                    st.markdown("- ✅ Wash sale detection")
                    st.markdown("- ✅ Long-term vs. short-term")
                    st.markdown("- ✅ Realized/unrealized gains")
                
                st.markdown("---")
                st.markdown("### Getting Started")
                st.markdown("1. Import your transaction history in the **💳 Transactions** tab")
                st.markdown("2. Cost basis will be automatically calculated")
                st.markdown("3. View detailed lot information here")
                return
            
            # Rename columns to match expected format
            column_mapping = {
                'transaction_date': 'date',
                'transaction_type': 'type',
                'transaction_id': 'id'
            }
            transactions = transactions.rename(columns=column_mapping)

            account_column = 'account_name' if 'account_name' in transactions.columns else 'account_id'
            
            # Filter for BUY transactions to show current lots
            buy_transactions = transactions[transactions['type'] == 'BUY'].copy()
            
            if len(buy_transactions) == 0:
                st.warning("No purchase transactions found. Cost basis tracking requires BUY transactions.")
                return
            
            # Calculate current lots by symbol and account
            st.markdown("### 📊 Current Tax Lots")
            st.caption("Active purchase lots grouped by account for proper tax treatment")
            
            # Group by account and symbol for proper tax tracking
            group_cols = ['symbol']
            if account_column in buy_transactions.columns:
                group_cols = [account_column, 'symbol']
            
            lots_summary = buy_transactions.groupby(group_cols).agg({
                'quantity': 'sum',
                'price': 'mean',
                'amount': 'sum',
                'date': 'min'
            }).reset_index()
            
            if account_column in lots_summary.columns:
                lots_summary.columns = ['Account', 'Symbol', 'Total Shares', 'Avg Price', 'Total Cost', 'First Purchase']
            else:
                lots_summary.columns = ['Symbol', 'Total Shares', 'Avg Price', 'Total Cost', 'First Purchase']
            lots_summary['Total Cost'] = lots_summary['Total Cost'].abs()
            lots_summary['Cost/Share'] = lots_summary['Total Cost'] / lots_summary['Total Shares']
            
            # Display summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Positions", len(lots_summary))
            with col2:
                st.metric("Total Invested", f"${lots_summary['Total Cost'].sum():,.2f}")
            with col3:
                unique_symbols = lots_summary['Symbol'].nunique()
                st.metric("Unique Securities", unique_symbols)
            with col4:
                if 'Account' in lots_summary.columns and lots_summary.columns[0] == 'Account':
                    unique_accounts = lots_summary['Account'].nunique()
                    st.metric("Accounts", unique_accounts)
                else:
                    st.metric("Accounts", 1)
            
            # Display lots table
            st.dataframe(
                lots_summary.style.format({
                    'Total Shares': '{:.4f}',
                    'Avg Price': '${:.2f}',
                    'Total Cost': '${:,.2f}',
                    'Cost/Share': '${:.2f}'
                }),
                use_container_width=True,
                height=400
            )
            
            # Detailed lot-level view
            with st.expander("📋 Detailed Lot Information"):
                st.markdown("**Individual Purchase Lots (grouped by account for tax purposes)**")
                
                # Show all buy transactions with details including account
                detail_cols = ['date', 'symbol', 'quantity', 'price', 'amount']
                if account_column in buy_transactions.columns:
                    detail_cols = ['date', account_column, 'symbol', 'quantity', 'price', 'amount']
                
                lot_details = buy_transactions[detail_cols].copy()
                
                if account_column in lot_details.columns:
                    lot_details.columns = ['Purchase Date', 'Account', 'Symbol', 'Shares', 'Price/Share', 'Total Cost']
                else:
                    lot_details.columns = ['Purchase Date', 'Symbol', 'Shares', 'Price/Share', 'Total Cost']
                
                lot_details['Total Cost'] = lot_details['Total Cost'].abs()
                
                if 'Account' in lot_details.columns and lot_details.columns[1] == 'Account':
                    lot_details = lot_details.sort_values(['Account', 'Symbol', 'Purchase Date'])
                else:
                    lot_details = lot_details.sort_values(['Symbol', 'Purchase Date'])
                
                st.dataframe(
                    lot_details.style.format({
                        'Shares': '{:.4f}',
                        'Price/Share': '${:.2f}',
                        'Total Cost': '${:,.2f}'
                    }),
                    use_container_width=True,
                    height=400
                )
            
            # Cost basis method explanation
            with st.expander("ℹ️ Cost Basis Methods"):
                st.markdown("""
                **FIFO (First In, First Out):**
                - Sells the oldest shares first
                - Most common method
                - Generally results in higher capital gains (older shares have lower cost basis)
                
                **LIFO (Last In, First Out):**
                - Sells the newest shares first
                - Can minimize short-term gains
                - May result in lower taxes in rising markets
                
                **Specific Lot Identification:**
                - You choose which specific shares to sell
                - Provides maximum tax optimization flexibility
                - Requires detailed record keeping
                
                **Average Cost:**
                - Used primarily for mutual funds
                - Averages the cost of all shares
                - Simpler calculation method
                """)
        else:
            st.error("Transaction storage not available")
    
    except Exception as e:
        st.error(f"Error loading cost basis data: {e}")
        logger.error(f"Cost basis tab error: {e}", exc_info=True)


def render_capital_gains_tab(transaction_storage, user_id: str = "default"):
    """
    Render the capital gains tab showing realized and unrealized gains.
    
    Args:
        transaction_storage: TransactionStorage instance
        user_id: User identifier
    """
    st.markdown("## 📈 Capital Gains Analysis")
    st.caption("Track realized and unrealized capital gains")
    
    try:
        # Debug logging
        logger.info(f"Capital Gains tab: session_state keys: {list(st.session_state.keys())}")
        logger.info(f"Capital Gains tab: transaction_storage is {'available' if transaction_storage else 'None'}")
        
        # Use transactions from session state if available (already has calculated gains)
        if 'imported_transactions' in st.session_state and len(st.session_state['imported_transactions']) > 0:
            transactions = st.session_state['imported_transactions'].copy()
            logger.info(f"✅ Using {len(transactions)} transactions from session state with calculated gains")
        elif transaction_storage:
            # Fallback: Load from database and calculate gains
            logger.info("Session state empty, loading from database...")
            transactions = transaction_storage.get_transactions(user_id=user_id)
            logger.info(f"Loaded {len(transactions)} transactions from database")
            
            if len(transactions) > 0:
                # Rename columns
                column_mapping = {
                    'transaction_date': 'date',
                    'transaction_type': 'type',
                    'transaction_id': 'id'
                }
                transactions = transactions.rename(columns=column_mapping)
                
                # Calculate gains
                logger.info("Calculating gains...")
                transactions = _calculate_gains_losses(transactions)
                logger.info(f"✅ Calculated gains for {len(transactions)} transactions from database")
        else:
            logger.warning("⚠️ No session state and no transaction storage!")
            transactions = pd.DataFrame()
        
        logger.info(f"Total transactions available: {len(transactions)}")
        
        if len(transactions) == 0:
                st.info("🚀 **Capital Gains Feature Available** — Import transactions to see gains analysis")
                
                st.markdown("### Features")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Realized Gains:**")
                    st.markdown("- ✅ Short-term capital gains")
                    st.markdown("- ✅ Long-term capital gains")
                    st.markdown("- ✅ Wash sale adjustments")
                    st.markdown("- ✅ 1099-B reconciliation")
                
                with col2:
                    st.markdown("**Unrealized Gains:**")
                    st.markdown("- ✅ Current position gains/losses")
                    st.markdown("- ✅ Tax lot details")
                    st.markdown("- ✅ Holding period tracking")
                    st.markdown("- ✅ Tax optimization opportunities")
                
                st.markdown("---")
                st.markdown("### Getting Started")
                st.markdown("1. Import your transaction history in the **💳 Transactions** tab")
                st.markdown("2. Capital gains will be automatically calculated")
                st.markdown("3. View detailed analysis here")
                return
        
        # Filter for SELL transactions (realized gains)
        sell_transactions = transactions[transactions['type'] == 'SELL'].copy()
            
        if len(sell_transactions) == 0:
            st.warning("No sell transactions found. Capital gains analysis requires SELL transactions.")
            
            # Show what we're waiting for
            st.info("💡 Once you have sell transactions, this tab will show:")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("- Short-term vs long-term gains breakdown")
                st.markdown("- Gains/losses by security")
                st.markdown("- Gains/losses by account")
            with col2:
                st.markdown("- Tax year summaries")
                st.markdown("- Wash sale adjustments")
                st.markdown("- 1099-B reconciliation data")
            return
        
        # Calculate realized gains summary
        st.markdown("### 💰 Realized Gains Summary")
        st.caption("Capital gains from completed sales")
        
        # Overall metrics
        total_gains = sell_transactions['gain_loss'].sum()
        short_term = sell_transactions[sell_transactions['term'] == 'SHORT']['gain_loss'].sum()
        long_term = sell_transactions[sell_transactions['term'] == 'LONG']['gain_loss'].sum()
        wash_sales = sell_transactions[sell_transactions['wash_sale'] == True]['gain_loss'].sum()
            
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Realized Gains",
                f"${total_gains:,.2f}",
                delta="Gain" if total_gains > 0 else "Loss"
            )
        
        with col2:
            st.metric(
                "Short-Term Gains",
                f"${short_term:,.2f}",
                help="Held ≤ 365 days, taxed as ordinary income"
            )
        
        with col3:
            st.metric(
                "Long-Term Gains",
                f"${long_term:,.2f}",
                help="Held > 365 days, preferential tax rates"
            )
        
        with col4:
            wash_sale_count = sell_transactions['wash_sale'].sum()
            st.metric(
                "Wash Sales",
                f"{wash_sale_count}",
                help="Sales with potential wash sale issues"
            )
        
        # Gains by year
        st.markdown("### 📅 Gains by Tax Year")
        sell_transactions.loc[:, 'year'] = pd.to_datetime(sell_transactions['date']).dt.year
            
        yearly_gains = sell_transactions.groupby('year').agg({
            'gain_loss': 'sum',
            'symbol': 'count'
        }).reset_index()
        yearly_gains.columns = ['Year', 'Total Gains', 'Number of Sales']
        
        # Add short-term and long-term breakdown
        yearly_short = sell_transactions[sell_transactions['term'] == 'SHORT'].groupby('year')['gain_loss'].sum()
        yearly_long = sell_transactions[sell_transactions['term'] == 'LONG'].groupby('year')['gain_loss'].sum()
        
        yearly_gains['Short-Term'] = yearly_gains['Year'].map(yearly_short).fillna(0)
        yearly_gains['Long-Term'] = yearly_gains['Year'].map(yearly_long).fillna(0)
        
        st.dataframe(
            yearly_gains.style.format({
                'Total Gains': '${:,.2f}',
                'Short-Term': '${:,.2f}',
                'Long-Term': '${:,.2f}',
                'Number of Sales': '{:.0f}'
            }),
            use_container_width=True
        )
        
        # Gains by security
        st.markdown("### 📊 Gains by Security")
        
        security_gains = sell_transactions.groupby('symbol').agg({
            'gain_loss': 'sum',
            'quantity': 'sum',
            'amount': 'sum'
        }).reset_index()
        security_gains.columns = ['Symbol', 'Total Gains', 'Shares Sold', 'Proceeds']
        security_gains['Proceeds'] = security_gains['Proceeds'].abs()
        security_gains = security_gains.sort_values('Total Gains', ascending=False)
        
        st.dataframe(
            security_gains.style.format({
                'Total Gains': '${:,.2f}',
                'Shares Sold': '{:.4f}',
                'Proceeds': '${:,.2f}'
            }).background_gradient(subset=['Total Gains'], cmap='RdYlGn', vmin=-1000, vmax=1000),
            use_container_width=True,
            height=300
        )
        
        # Gains by account (prefer friendly account name when available)
        account_column = 'account_name' if 'account_name' in sell_transactions.columns else 'account_id'
        if account_column in sell_transactions.columns:
            st.markdown("### 🏦 Gains by Account")
            st.caption("Grouped by account to properly track tax treatment (Roth, Traditional, Brokerage)")
            
            # Group by account
            account_gains = sell_transactions.groupby(account_column).agg({
                'gain_loss': 'sum',
                'symbol': 'count'
            }).reset_index()
            account_gains.columns = ['Account', 'Total Gains', 'Number of Sales']
            account_gains = account_gains.sort_values('Total Gains', ascending=False)
            
            st.dataframe(
                account_gains.style.format({
                    'Total Gains': '${:,.2f}',
                    'Number of Sales': '{:.0f}'
                }).background_gradient(subset=['Total Gains'], cmap='RdYlGn'),
                use_container_width=True
            )
            
            # Add explanation of tax treatment by account type
            with st.expander("ℹ️ Tax Treatment by Account Type"):
                st.markdown("""
                **Roth IRA:**
                - Qualified withdrawals are tax-free
                - No capital gains tax on sales within the account
                - Gains shown here are for tracking only, not taxable
                
                **Traditional IRA:**
                - Withdrawals taxed as ordinary income
                - No capital gains tax on sales within the account
                - Gains shown here are for tracking only, not taxable
                
                **Brokerage (Taxable):**
                - Capital gains are taxable
                - Short-term gains (≤365 days) taxed as ordinary income
                - Long-term gains (>365 days) have preferential rates (0%, 15%, 20%)
                - These gains MUST be reported on your tax return
                """)
        
        # Detailed transaction list
        with st.expander("📋 Detailed Sale Transactions"):
            st.markdown("**All Realized Gains/Losses (with account for tax tracking)**")
            
            detail_cols = ['date', 'symbol', 'quantity', 'price', 'amount', 'gain_loss', 'term', 'wash_sale']
            if account_column in sell_transactions.columns:
                detail_cols = ['date', account_column, 'symbol', 'quantity', 'price', 'amount', 'gain_loss', 'term', 'wash_sale']
            
            available_cols = [col for col in detail_cols if col in sell_transactions.columns]
            
            detail_df = sell_transactions[available_cols].copy()
            detail_df = detail_df.sort_values('date', ascending=False)
            
            # Rename for display
            display_names = {
                'date': 'Sale Date',
                'account_id': 'Account',
                'account_name': 'Account',
                'symbol': 'Symbol',
                'quantity': 'Shares',
                'price': 'Price',
                'amount': 'Proceeds',
                'gain_loss': 'Gain/Loss',
                'term': 'Term',
                'wash_sale': 'Wash Sale'
            }
            detail_df = detail_df.rename(columns={k: v for k, v in display_names.items() if k in detail_df.columns})
            
            st.dataframe(
                detail_df.style.format({
                    'Shares': '{:.4f}',
                    'Price': '${:.2f}',
                    'Proceeds': '${:,.2f}',
                    'Gain/Loss': '${:,.2f}'
                }).background_gradient(subset=['Gain/Loss'], cmap='RdYlGn'),
                use_container_width=True,
                height=400
            )
        
        # Tax optimization insights
        with st.expander("💡 Tax Optimization Insights"):
            st.markdown("""
            **Short-Term vs Long-Term:**
            - Short-term gains (≤365 days) are taxed as ordinary income (up to 37%)
            - Long-term gains (>365 days) have preferential rates (0%, 15%, or 20%)
            - Consider holding positions >1 year for better tax treatment
            
            **Wash Sale Rule:**
            - Selling at a loss and repurchasing within 30 days triggers wash sale
            - Loss deduction is disallowed and added to cost basis of new purchase
            - Wait 31 days before repurchasing to preserve tax loss
            
            **Tax Loss Harvesting:**
            - Realize losses to offset gains
            - Can offset up to $3,000 of ordinary income per year
                - Excess losses carry forward to future years
                
                **1099-B Reconciliation:**
                - Compare these figures with your broker's 1099-B form
                - Report discrepancies to your tax professional
                - Keep detailed records for audit purposes
                """)
    
    except Exception as e:
        st.error(f"Error loading capital gains data: {e}")
        logger.error(f"Capital gains tab error: {e}", exc_info=True)



# Made with Bob
