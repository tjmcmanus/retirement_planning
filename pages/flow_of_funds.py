import streamlit as st
import graphviz
from datetime import datetime
from load_data import get_portfolio_truth_by_month

st.title("Flow of funds")

# Get current month/year or allow user selection
col1, col2 = st.columns(2)
with col1:
    selected_month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1)
with col2:
    selected_year = st.selectbox("Year", [2025, 2026], index=1)

flow_tab, account_tab = st.tabs(["Investment Flow", "Account Details"])

with account_tab:
    # Display actual account structure from CSV
    portfolio_data = get_portfolio_truth_by_month(selected_month, selected_year)
    
    if not portfolio_data.empty:
        # Remove "MF:" prefix from symbols for display
        portfolio_data['symbol'] = portfolio_data['symbol'].str.replace('^MF:', '', regex=True)
        
        # Show holdings by account
        st.subheader("Holdings by Account")
        for account_type in portfolio_data['account_type'].unique():
            with st.expander(f"{account_type} Accounts"):
                type_data = portfolio_data[portfolio_data['account_type'] == account_type]
                st.dataframe(type_data[['account_name', 'symbol', 'name', 'qty', 'purchase_price']], hide_index=True)
    else:
        st.warning(f"No portfolio data found for {selected_month}/{selected_year}")

with flow_tab:
    # Build dynamic flow diagram based on actual accounts
    portfolio_data = get_portfolio_truth_by_month(selected_month, selected_year)
    
    if not portfolio_data.empty:
        # Get unique account combinations
        accounts = portfolio_data.groupby(['account_name', 'account_type']).size().reset_index()
        
        buckets = graphviz.Digraph()
        buckets.attr(rankdir='LR')  # Left to right layout
        buckets.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
        
        # Categorize accounts dynamically
        cash_accounts = []
        brokerage_accounts = []
        traditional_accounts = []
        roth_accounts = []
        
        for _, row in accounts.iterrows():
            account_label = f"{row['account_name']}\n({row['account_type']})"
            
            if row['account_type'] == 'Cash':
                cash_accounts.append(account_label)
                buckets.node(account_label, fillcolor='lightgreen')
            elif row['account_type'] == 'Brokerage':
                brokerage_accounts.append(account_label)
                buckets.node(account_label, fillcolor='lightyellow')
            elif row['account_type'] == 'Traditional':
                traditional_accounts.append(account_label)
                buckets.node(account_label, fillcolor='lightcoral')
            elif row['account_type'] == 'Roth':
                roth_accounts.append(account_label)
                buckets.node(account_label, fillcolor='lavender')
        
        # Add Donor Advised Fund node
        buckets.node("Donor Advised\nFund", fillcolor='lightgray')
        
        # Create flow relationships based on actual accounts
        # Traditional -> Cash (withdrawals when stocks down)
        for trad in traditional_accounts:
            for cash in cash_accounts:
                buckets.edge(trad, cash, "Withdrawals\n(stocks down)")
        
        # Brokerage -> Cash (withdrawals when stocks up)
        for brok in brokerage_accounts:
            for cash in cash_accounts:
                buckets.edge(brok, cash, "Withdrawals\n(stocks up)")
        
        # Traditional -> Brokerage (RMDs/Replenish)
        for trad in traditional_accounts:
            for brok in brokerage_accounts:
                buckets.edge(trad, brok, "RMDs/\nReplenish")
        
        # Traditional -> Roth (Conversions)
        for trad in traditional_accounts:
            for roth in roth_accounts:
                buckets.edge(trad, roth, "Roth\nConversions")
        
        # Roth -> Cash (Big purchases)
        for roth in roth_accounts:
            for cash in cash_accounts:
                buckets.edge(roth, cash, "Big\nPurchases")
        
        # Brokerage -> DAF
        for brok in brokerage_accounts:
            buckets.edge(brok, "Donor Advised\nFund", "Charitable\nGiving")
        
        st.graphviz_chart(buckets)
        
        # Add summary statistics
        st.subheader("Account Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cash_data = portfolio_data[portfolio_data['account_type'] == 'Cash']
            cash_total = (cash_data['qty'] * cash_data['purchase_price']).sum()
            st.metric("Cash Accounts", f"${cash_total:,.0f}")
        
        with col2:
            brok_data = portfolio_data[portfolio_data['account_type'] == 'Brokerage']
            brok_total = (brok_data['qty'] * brok_data['purchase_price']).sum()
            st.metric("Brokerage Accounts", f"${brok_total:,.0f}")
        
        with col3:
            trad_data = portfolio_data[portfolio_data['account_type'] == 'Traditional']
            trad_total = (trad_data['qty'] * trad_data['purchase_price']).sum()
            st.metric("Traditional Accounts", f"${trad_total:,.0f}")
        
        with col4:
            roth_data = portfolio_data[portfolio_data['account_type'] == 'Roth']
            roth_total = (roth_data['qty'] * roth_data['purchase_price']).sum()
            st.metric("Roth Accounts", f"${roth_total:,.0f}")
        
        # Additional insights
        st.subheader("Flow Strategy Notes")
        st.info("""
        **Investment Flow Strategy:**
        - **Traditional → Cash**: Withdraw from tax-deferred accounts when market is down
        - **Brokerage → Cash**: Withdraw from taxable accounts when market is up (tax-efficient)
        - **Traditional → Roth**: Convert to Roth during low-income years for tax optimization
        - **Traditional → Brokerage**: Required Minimum Distributions (RMDs) after age 73
        - **Roth → Cash**: Emergency funds or large purchases (tax-free withdrawals)
        - **Brokerage → DAF**: Donate appreciated securities for tax deduction
        """)
    else:
        st.warning(f"No portfolio data found for {selected_month}/{selected_year}")

# Made with Bob
