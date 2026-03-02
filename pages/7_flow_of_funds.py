"""
pages/7_flow_of_funds.py
========================
💸 Flow of Funds — Graphviz diagram of money movement between accounts,
plus an account details sub-tab.
"""
from __future__ import annotations

from typing import cast

import graphviz
import pandas as pd
import streamlit as st

from components.navbar import navbar
from components.shared import auto_rerun_if_rebuilding, init_page
from load_data import get_portfolio_truth_by_month

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
(
    _networth,
    _portfolio_df,
    _portfolio_cache_ready,
    _stale_label,
    curr_month,
    curr_year,
    _eff_port_month,
    _eff_port_year,
) = init_page("💸 Flow of Funds — Financial Planner", "💸")

navbar("💸 Flow of Funds")

st.header("💸 Flow of Funds")
st.markdown("Visualize how money moves between your accounts and to charitable giving.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Month / Year selector
# ---------------------------------------------------------------------------
_ff_col1, _ff_col2, _ = st.columns([1, 1, 4])
with _ff_col1:
    _ff_month = st.selectbox("Month", range(1, 13), index=curr_month - 1, key="ff_month")
with _ff_col2:
    _ff_years = [2024, 2025, 2026]
    _ff_year_idx = _ff_years.index(curr_year) if curr_year in _ff_years else len(_ff_years) - 1
    _ff_year = st.selectbox("Year", _ff_years, index=_ff_year_idx, key="ff_year")

flow_sub_tab, account_sub_tab = st.tabs(["💹 Investment Flow", "📋 Account Details"])

# ---------------------------------------------------------------------------
# SUB-TAB 1: Investment Flow diagram
# ---------------------------------------------------------------------------
with flow_sub_tab:
    _ff_portfolio = get_portfolio_truth_by_month(_ff_month, _ff_year)
    if not _ff_portfolio.empty:
        _ff_accounts = _ff_portfolio.groupby(["account_name", "account_type"]).size().reset_index()

        buckets = graphviz.Digraph()
        buckets.attr(rankdir="LR")
        buckets.attr("node", shape="box", style="rounded,filled", fillcolor="lightblue")

        cash_accounts: list[str] = []
        brokerage_accounts: list[str] = []
        traditional_accounts: list[str] = []
        roth_accounts: list[str] = []

        for _, _row in _ff_accounts.iterrows():
            _label = f"{_row['account_name']}\n({_row['account_type']})"
            if _row["account_type"] == "Cash":
                cash_accounts.append(_label)
                buckets.node(_label, fillcolor="lightgreen")
            elif _row["account_type"] == "Brokerage":
                brokerage_accounts.append(_label)
                buckets.node(_label, fillcolor="lightyellow")
            elif _row["account_type"] == "Traditional":
                traditional_accounts.append(_label)
                buckets.node(_label, fillcolor="lightcoral")
            elif _row["account_type"] == "Roth":
                roth_accounts.append(_label)
                buckets.node(_label, fillcolor="lavender")

        buckets.node("Donor Advised\nFund", fillcolor="lightgray")

        for trad in traditional_accounts:
            for cash in cash_accounts:
                buckets.edge(trad, cash, "Withdrawals\n(stocks down)")
        for brok in brokerage_accounts:
            for cash in cash_accounts:
                buckets.edge(brok, cash, "Withdrawals\n(stocks up)")
        for trad in traditional_accounts:
            for brok in brokerage_accounts:
                buckets.edge(trad, brok, "RMDs/\nReplenish")
        for trad in traditional_accounts:
            for roth in roth_accounts:
                buckets.edge(trad, roth, "Roth\nConversions")
        for roth in roth_accounts:
            for cash in cash_accounts:
                buckets.edge(roth, cash, "Big\nPurchases")
        for brok in brokerage_accounts:
            buckets.edge(brok, "Donor Advised\nFund", "Charitable\nGiving")

        st.graphviz_chart(buckets)

        # Account summary metrics
        st.subheader("Account Summary")
        _s_col1, _s_col2, _s_col3, _s_col4 = st.columns(4)
        with _s_col1:
            _d = _ff_portfolio[_ff_portfolio["account_type"] == "Cash"]
            _cash_val = (_d["qty"] * _d["purchase_price"]).sum() if not _d.empty else 0.0  # type: ignore[union-attr]
            st.metric("Cash Accounts", f"${_cash_val:,.0f}")
        with _s_col2:
            _d = _ff_portfolio[_ff_portfolio["account_type"] == "Brokerage"]
            _brok_val = (_d["qty"] * _d["purchase_price"]).sum() if not _d.empty else 0.0  # type: ignore[union-attr]
            st.metric("Brokerage Accounts", f"${_brok_val:,.0f}")
        with _s_col3:
            _d = _ff_portfolio[_ff_portfolio["account_type"] == "Traditional"]
            _trad_val = (_d["qty"] * _d["purchase_price"]).sum() if not _d.empty else 0.0  # type: ignore[union-attr]
            st.metric("Traditional Accounts", f"${_trad_val:,.0f}")
        with _s_col4:
            _d = _ff_portfolio[_ff_portfolio["account_type"] == "Roth"]
            _roth_val = (_d["qty"] * _d["purchase_price"]).sum() if not _d.empty else 0.0  # type: ignore[union-attr]
            st.metric("Roth Accounts", f"${_roth_val:,.0f}")

        # Flow strategy notes
        st.subheader("Flow Strategy Notes")
        st.info(
            "**Investment Flow Strategy:**\n"
            "- **Traditional → Cash**: Withdraw from tax-deferred accounts when market is down\n"
            "- **Brokerage → Cash**: Withdraw from taxable accounts when market is up (tax-efficient)\n"
            "- **Traditional → Roth**: Convert to Roth during low-income years for tax optimization\n"
            "- **Traditional → Brokerage**: Required Minimum Distributions (RMDs) after age 73\n"
            "- **Roth → Cash**: Emergency funds or large purchases (tax-free withdrawals)\n"
            "- **Brokerage → DAF**: Donate appreciated securities for tax deduction"
        )
    else:
        st.warning(f"No portfolio data found for {_ff_month}/{_ff_year}")

# ---------------------------------------------------------------------------
# SUB-TAB 2: Account Details
# ---------------------------------------------------------------------------
with account_sub_tab:
    _ff_portfolio2 = get_portfolio_truth_by_month(_ff_month, _ff_year)
    if not _ff_portfolio2.empty:
        _ff_portfolio2 = _ff_portfolio2.copy()
        _ff_portfolio2["symbol"] = cast(pd.Series, _ff_portfolio2["symbol"]).str.replace(
            "^MF:", "", regex=True
        )
        st.subheader("Holdings by Account")
        for _acct_type in cast(pd.Series, _ff_portfolio2["account_type"]).unique():
            with st.expander(f"{_acct_type} Accounts", expanded=False):
                _type_data = _ff_portfolio2[_ff_portfolio2["account_type"] == _acct_type]
                _display_cols = [c for c in ["account_name", "symbol", "name", "qty", "purchase_price"] if c in _type_data.columns]  # type: ignore[union-attr]
                st.dataframe(_type_data[_display_cols], hide_index=True, use_container_width=True)
    else:
        st.warning(f"No portfolio data found for {_ff_month}/{_ff_year}")

# ---------------------------------------------------------------------------
auto_rerun_if_rebuilding()

# Made with Bob
