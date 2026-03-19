"""
components/transaction_history_ui.py
=====================================
Transaction history UI component for Portfolio Hub.

Provides interface for viewing, filtering, and analyzing transaction history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


def render_transaction_history_tab(
    connector,
    transaction_importer,
    transaction_storage,
    user_id: str = "default"
) -> None:
    """
    Render the Transaction History tab.
    
    Args:
        connector: SnapTradeConnector instance
        transaction_importer: TransactionImporter instance
        transaction_storage: TransactionStorage instance
        user_id: User identifier
    """
    st.markdown("## 📊 Transaction History")
    st.caption("View and analyze your investment transactions")
    
    # Import transactions section
    with st.expander("🔄 Import Transactions", expanded=False):
        _render_import_section(connector, transaction_importer, transaction_storage, user_id)
    
    # Get stored transactions
    transactions = transaction_storage.get_transactions(user_id=user_id)
    
    if len(transactions) == 0:
        st.info("📭 No transactions found. Import transactions from your brokerage accounts above.")
        return
    
    # Filter section
    st.markdown("### 🔍 Filter Transactions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Account filter
        accounts = ['All'] + sorted(transactions['account_name'].unique().tolist())
        selected_account = st.selectbox("Account", accounts, key="txn_account_filter")
    
    with col2:
        # Transaction type filter
        txn_types = ['All'] + sorted(transactions['transaction_type'].unique().tolist())
        selected_type = st.selectbox("Type", txn_types, key="txn_type_filter")
    
    with col3:
        # Date range
        date_range = st.selectbox(
            "Date Range",
            ["Last 30 Days", "Last 90 Days", "Last Year", "All Time", "Custom"],
            key="txn_date_range"
        )
    
    with col4:
        # Symbol filter
        symbols = ['All'] + sorted([s for s in transactions['symbol'].unique() if pd.notna(s)])
        selected_symbol = st.selectbox("Symbol", symbols, key="txn_symbol_filter")
    
    # Apply filters
    filtered_txns = transactions.copy()
    
    if selected_account != 'All':
        filtered_txns = filtered_txns[filtered_txns['account_name'] == selected_account]
    
    if selected_type != 'All':
        filtered_txns = filtered_txns[filtered_txns['transaction_type'] == selected_type]
    
    if selected_symbol != 'All':
        filtered_txns = filtered_txns[filtered_txns['symbol'] == selected_symbol]
    
    # Date range filter
    if date_range != 'All Time':
        end_date = datetime.now()
        if date_range == 'Last 30 Days':
            start_date = end_date - timedelta(days=30)
        elif date_range == 'Last 90 Days':
            start_date = end_date - timedelta(days=90)
        elif date_range == 'Last Year':
            start_date = end_date - timedelta(days=365)
        else:  # Custom
            col_start, col_end = st.columns(2)
            with col_start:
                start_date = st.date_input("Start Date", end_date - timedelta(days=90))
            with col_end:
                end_date = st.date_input("End Date", end_date)
        
        filtered_txns = filtered_txns[
            (filtered_txns['transaction_date'] >= pd.Timestamp(start_date)) &
            (filtered_txns['transaction_date'] <= pd.Timestamp(end_date))
        ]
    
    # Summary metrics
    st.markdown("### 📈 Summary")
    _render_transaction_summary(filtered_txns)
    
    # Visualizations
    st.markdown("### 📊 Visualizations")
    _render_transaction_charts(filtered_txns)
    
    # Transaction table
    st.markdown("### 📋 Transaction Details")
    _render_transaction_table(filtered_txns)
    
    # Export options
    st.markdown("### 💾 Export")
    _render_export_options(filtered_txns)


def _render_import_section(
    connector,
    transaction_importer,
    transaction_storage,
    user_id: str
) -> None:
    """Render transaction import section."""
    st.markdown("Import transaction history from your connected brokerage accounts.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Date range for import
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        import_start = st.date_input(
            "Start Date",
            start_date,
            key="import_start_date"
        )
        import_end = st.date_input(
            "End Date",
            end_date,
            key="import_end_date"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("🔄 Import Transactions", type="primary", key="import_txns_btn"):
            with st.spinner("Importing transactions..."):
                try:
                    # Get transactions from SnapTrade
                    transactions_df = transaction_importer.get_transactions(
                        user_id=user_id,
                        start_date=import_start.strftime("%Y-%m-%d"),
                        end_date=import_end.strftime("%Y-%m-%d")
                    )
                    
                    if len(transactions_df) > 0:
                        # Store in database
                        count = transaction_storage.store_transactions(transactions_df, user_id)
                        st.success(f"✅ Imported {count} transactions")
                        st.rerun()
                    else:
                        st.warning("No transactions found in the specified date range")
                
                except Exception as e:
                    st.error(f"Failed to import transactions: {e}")
                    logger.error(f"Transaction import error: {e}", exc_info=True)


def _render_transaction_summary(transactions: pd.DataFrame) -> None:
    """Render summary metrics for transactions."""
    if len(transactions) == 0:
        st.info("No transactions match the selected filters")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Transactions", f"{len(transactions):,}")
    
    with col2:
        buys = transactions[transactions['transaction_type'] == 'buy']
        total_invested = abs(buys['amount'].sum()) if len(buys) > 0 else 0
        st.metric("Total Invested", f"${total_invested:,.2f}")
    
    with col3:
        sells = transactions[transactions['transaction_type'] == 'sell']
        total_proceeds = abs(sells['amount'].sum()) if len(sells) > 0 else 0
        st.metric("Total Proceeds", f"${total_proceeds:,.2f}")
    
    with col4:
        dividends = transactions[transactions['transaction_type'] == 'dividend']
        total_dividends = abs(dividends['amount'].sum()) if len(dividends) > 0 else 0
        st.metric("Dividend Income", f"${total_dividends:,.2f}")


def _render_transaction_charts(transactions: pd.DataFrame) -> None:
    """Render transaction visualizations."""
    if len(transactions) == 0:
        return
    
    tab1, tab2, tab3 = st.tabs(["By Type", "Over Time", "By Account"])
    
    with tab1:
        # Transaction count by type
        type_counts = transactions['transaction_type'].value_counts()
        fig = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            title="Transactions by Type"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Transactions over time
        txns_by_date = transactions.copy()
        txns_by_date['month'] = txns_by_date['transaction_date'].dt.to_period('M').astype(str)
        monthly_counts = txns_by_date.groupby(['month', 'transaction_type']).size().reset_index(name='count')
        
        fig = px.bar(
            monthly_counts,
            x='month',
            y='count',
            color='transaction_type',
            title="Transactions Over Time",
            labels={'month': 'Month', 'count': 'Number of Transactions'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        # Transactions by account
        account_counts = transactions['account_name'].value_counts()
        fig = px.bar(
            x=account_counts.index,
            y=account_counts.values,
            title="Transactions by Account",
            labels={'x': 'Account', 'y': 'Number of Transactions'}
        )
        st.plotly_chart(fig, use_container_width=True)


def _render_transaction_table(transactions: pd.DataFrame) -> None:
    """Render transaction details table."""
    if len(transactions) == 0:
        return
    
    # Prepare display dataframe
    display_df = transactions[[
        'transaction_date', 'transaction_type', 'symbol', 'description',
        'quantity', 'price', 'amount', 'fee', 'account_name'
    ]].copy()
    
    # Format columns
    display_df['transaction_date'] = display_df['transaction_date'].dt.strftime('%Y-%m-%d')
    display_df['quantity'] = display_df['quantity'].apply(lambda x: f"{x:.4f}" if pd.notna(x) and x != 0 else "")
    display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x != 0 else "")
    display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "")
    display_df['fee'] = display_df['fee'].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x != 0 else "")
    
    # Rename columns for display
    display_df.columns = [
        'Date', 'Type', 'Symbol', 'Description',
        'Quantity', 'Price', 'Amount', 'Fee', 'Account'
    ]
    
    # Show dataframe with pagination
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400
    )
    
    st.caption(f"Showing {len(display_df)} transactions")


def _render_export_options(transactions: pd.DataFrame) -> None:
    """Render export options for transactions."""
    if len(transactions) == 0:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Export to CSV
        csv = transactions.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="download_txns_csv"
        )
    
    with col2:
        # Export to Excel (if openpyxl is available)
        try:
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                transactions.to_excel(writer, index=False, sheet_name='Transactions')
            
            st.download_button(
                label="📥 Download Excel",
                data=buffer.getvalue(),
                file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_txns_excel"
            )
        except ImportError:
            st.caption("Excel export requires openpyxl package")


def render_cost_basis_tab(
    transaction_storage,
    user_id: str = "default"
) -> None:
    """
    Render the Cost Basis tab.
    
    Args:
        transaction_storage: TransactionStorage instance
        user_id: User identifier
    """
    st.markdown("## 💰 Cost Basis Tracking")
    st.caption("Track cost basis and tax lots for your holdings")
    
    # Get tax lots
    tax_lots = transaction_storage.get_tax_lots(user_id=user_id, only_open=True)
    
    if len(tax_lots) == 0:
        st.info("📭 No open tax lots found. Import transactions to track cost basis.")
        return
    
    # Summary by symbol
    st.markdown("### 📊 Cost Basis by Symbol")
    
    summary = tax_lots.groupby('symbol').agg({
        'remaining_quantity': 'sum',
        'cost_basis': 'sum'
    }).reset_index()
    
    summary['avg_cost'] = summary['cost_basis'] / summary['remaining_quantity']
    summary.columns = ['Symbol', 'Total Shares', 'Total Cost', 'Avg Cost/Share']
    
    # Format for display
    display_summary = summary.copy()
    display_summary['Total Shares'] = display_summary['Total Shares'].apply(lambda x: f"{x:.4f}")
    display_summary['Total Cost'] = display_summary['Total Cost'].apply(lambda x: f"${x:,.2f}")
    display_summary['Avg Cost/Share'] = display_summary['Avg Cost/Share'].apply(lambda x: f"${x:.2f}")
    
    st.dataframe(display_summary, use_container_width=True)
    
    # Detailed tax lots
    st.markdown("### 📋 Tax Lot Details")
    
    # Symbol filter
    symbols = ['All'] + sorted(tax_lots['symbol'].unique().tolist())
    selected_symbol = st.selectbox("Filter by Symbol", symbols, key="cost_basis_symbol_filter")
    
    filtered_lots = tax_lots if selected_symbol == 'All' else tax_lots[tax_lots['symbol'] == selected_symbol]
    
    # Display tax lots
    display_lots = filtered_lots[[
        'symbol', 'purchase_date', 'quantity', 'price',
        'remaining_quantity', 'cost_basis', 'account_name'
    ]].copy()
    
    # Format columns
    display_lots['purchase_date'] = pd.to_datetime(display_lots['purchase_date']).dt.strftime('%Y-%m-%d')
    display_lots['quantity'] = display_lots['quantity'].apply(lambda x: f"{x:.4f}")
    display_lots['price'] = display_lots['price'].apply(lambda x: f"${x:.2f}")
    display_lots['remaining_quantity'] = display_lots['remaining_quantity'].apply(lambda x: f"{x:.4f}")
    display_lots['cost_basis'] = display_lots['cost_basis'].apply(lambda x: f"${x:,.2f}")
    
    display_lots.columns = [
        'Symbol', 'Purchase Date', 'Original Qty', 'Price',
        'Remaining Qty', 'Cost Basis', 'Account'
    ]
    
    st.dataframe(display_lots, use_container_width=True, height=400)
    
    st.caption(f"Showing {len(display_lots)} open tax lots")


def render_capital_gains_tab(
    transaction_storage,
    user_id: str = "default"
) -> None:
    """
    Render the Capital Gains tab.
    
    Args:
        transaction_storage: TransactionStorage instance
        user_id: User identifier
    """
    st.markdown("## 📈 Capital Gains & Losses")
    st.caption("Track realized capital gains and losses for tax reporting")
    
    # Tax year selector
    current_year = datetime.now().year
    tax_years = list(range(current_year, current_year - 10, -1))
    selected_year = st.selectbox("Tax Year", tax_years, key="cap_gains_year")
    
    # Get capital gains for selected year
    gains = transaction_storage.get_capital_gains(user_id=user_id, tax_year=selected_year)
    
    if len(gains) == 0:
        st.info(f"📭 No capital gains/losses recorded for {selected_year}")
        return
    
    # Summary metrics
    st.markdown("### 📊 Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_gains = gains['gain_loss'].sum()
        st.metric("Total Gain/Loss", f"${total_gains:,.2f}")
    
    with col2:
        short_term = gains[gains['holding_period'] == 'short_term']['gain_loss'].sum()
        st.metric("Short-Term", f"${short_term:,.2f}")
    
    with col3:
        long_term = gains[gains['holding_period'] == 'long_term']['gain_loss'].sum()
        st.metric("Long-Term", f"${long_term:,.2f}")
    
    with col4:
        st.metric("Transactions", f"{len(gains):,}")
    
    # Detailed table
    st.markdown("### 📋 Detailed Gains/Losses")
    
    display_gains = gains[[
        'symbol', 'sell_date', 'quantity', 'proceeds',
        'cost_basis', 'gain_loss', 'holding_period', 'account_name'
    ]].copy()
    
    # Format columns
    display_gains['sell_date'] = pd.to_datetime(display_gains['sell_date']).dt.strftime('%Y-%m-%d')
    display_gains['quantity'] = display_gains['quantity'].apply(lambda x: f"{x:.4f}")
    display_gains['proceeds'] = display_gains['proceeds'].apply(lambda x: f"${x:,.2f}")
    display_gains['cost_basis'] = display_gains['cost_basis'].apply(lambda x: f"${x:,.2f}")
    display_gains['gain_loss'] = display_gains['gain_loss'].apply(
        lambda x: f"${x:,.2f}" if x >= 0 else f"-${abs(x):,.2f}"
    )
    display_gains['holding_period'] = display_gains['holding_period'].str.replace('_', ' ').str.title()
    
    display_gains.columns = [
        'Symbol', 'Sell Date', 'Quantity', 'Proceeds',
        'Cost Basis', 'Gain/Loss', 'Holding Period', 'Account'
    ]
    
    st.dataframe(display_gains, use_container_width=True, height=400)
    
    # Export for tax filing
    st.markdown("### 💾 Export for Tax Filing")
    csv = gains.to_csv(index=False)
    st.download_button(
        label="📥 Download Capital Gains Report",
        data=csv,
        file_name=f"capital_gains_{selected_year}.csv",
        mime="text/csv",
        key="download_cap_gains"
    )


# Made with Bob