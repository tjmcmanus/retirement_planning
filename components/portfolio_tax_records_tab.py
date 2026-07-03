"""
components/portfolio_tax_records_tab.py
========================================
Unified Tax Records tab for Portfolio Hub.

Four sub-tabs:
  💳 Transactions    — import and view transaction history (all accounts)
  💰 Cost Basis      — FIFO/LIFO/HIFO/LOFO/SPEC_ID lot tracking
  📈 Capital Gains   — realized gains/losses by tax year, export for tax software
  🌱 Harvest Savings — YTD direct-index harvest savings tracker
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st
from typing import TYPE_CHECKING

# ---------------------------------------------------------------------------
# Transaction history components (existing)
# ---------------------------------------------------------------------------
try:
    from components.transaction_history_ui import (
        render_transaction_history_tab,
        render_cost_basis_tab,
        render_capital_gains_tab,
        create_transaction_storage,
    )
    TRANSACTION_FEATURES_AVAILABLE = True
except ImportError:
    TRANSACTION_FEATURES_AVAILABLE = False
    render_transaction_history_tab = None  # type: ignore
    render_cost_basis_tab = None           # type: ignore
    render_capital_gains_tab = None        # type: ignore
    create_transaction_storage = None      # type: ignore

# ---------------------------------------------------------------------------
# Tax savings tracker (from Direct Indexing)
# ---------------------------------------------------------------------------
try:
    from components.tax_savings_tracker import (
        get_ytd_summary,
        get_harvest_history,
        get_performance_metrics,
    )
    TAX_SAVINGS_AVAILABLE = True
except ImportError:
    TAX_SAVINGS_AVAILABLE = False
    get_ytd_summary = None        # type: ignore
    get_harvest_history = None    # type: ignore
    get_performance_metrics = None  # type: ignore


# ==============================================================================
# PUBLIC ENTRY POINT
# ==============================================================================

def render_tax_records_tab(curr_year: int) -> None:
    """
    Render the Tax Records tab (top-level Portfolio Hub tab).

    Merges the three existing transaction/cost-basis/capital-gains tabs with
    the Direct Indexing harvest savings tracker into a single, unified view.

    Args:
        curr_year: Current year (used as default tax year).
    """
    st.markdown("### 💰 Tax Records")
    st.caption(
        "Consolidated view of transactions, cost basis, capital gains, "
        "and harvest savings across all accounts."
    )

    transactions_sub, cost_basis_sub, cap_gains_sub, harvest_sub = st.tabs([
        "💳 Transactions",
        "💰 Cost Basis",
        "📈 Capital Gains",
        "🌱 Harvest Savings",
    ])

    # Initialise transaction storage once; share across sub-tabs
    txn_storage = None
    if TRANSACTION_FEATURES_AVAILABLE and create_transaction_storage is not None:
        if "tax_records_transaction_storage" not in st.session_state:
            try:
                st.session_state["tax_records_transaction_storage"] = create_transaction_storage()
            except Exception as e:
                st.session_state["tax_records_transaction_storage"] = None
                st.error(f"Failed to initialise transaction storage: {e}")
        txn_storage = st.session_state.get("tax_records_transaction_storage")

    with transactions_sub:
        _render_transactions(txn_storage)

    with cost_basis_sub:
        _render_cost_basis(txn_storage)

    with cap_gains_sub:
        _render_capital_gains(txn_storage)

    with harvest_sub:
        _render_harvest_savings(curr_year)


# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

def _render_transactions(txn_storage) -> None:
    if TRANSACTION_FEATURES_AVAILABLE and render_transaction_history_tab is not None and txn_storage is not None:
        render_transaction_history_tab(
            connector=st.session_state.get("snaptrade_connector"),
            transaction_importer=st.session_state.get("transaction_importer"),
            transaction_storage=txn_storage,
            user_id="default",
        )
    else:
        st.markdown("## 💳 Transaction History")
        st.caption("Import and analyse your investment transactions")
        st.info("🚀 **Transaction Import Feature Available** — Connect your brokerage account to get started")
        st.markdown("### Getting Started")
        st.markdown("1. Go to the **🔗 Connections** tab")
        st.markdown("2. Connect your brokerage account via SnapTrade")
        st.markdown("3. Return here to import your transaction history")


def _render_cost_basis(txn_storage) -> None:
    if TRANSACTION_FEATURES_AVAILABLE and render_cost_basis_tab is not None and txn_storage is not None:
        render_cost_basis_tab(
            transaction_storage=txn_storage,
            user_id="default",
        )
    else:
        st.markdown("## 💰 Cost Basis Tracking")
        st.caption("Track cost basis and tax lots for accurate tax reporting")
        st.info("🚀 **Cost Basis Tracking Available** — Import transactions to get started")
        st.markdown("### Getting Started")
        st.markdown("1. Import your transaction history in the **💳 Transactions** sub-tab")
        st.markdown("2. Cost basis will be automatically calculated using FIFO/LIFO/HIFO/LOFO/SPEC_ID")
        st.markdown("3. View detailed tax lots and cost basis here")


def _render_capital_gains(txn_storage) -> None:
    if TRANSACTION_FEATURES_AVAILABLE and render_capital_gains_tab is not None and txn_storage is not None:
        render_capital_gains_tab(
            transaction_storage=txn_storage,
            user_id="default",
        )
    else:
        st.markdown("## 📈 Capital Gains & Losses")
        st.caption("Track realized capital gains and losses for tax reporting")
        st.info("🚀 **Capital Gains Reporting Available** — Import transactions to get started")
        st.markdown("### Getting Started")
        st.markdown("1. Import your transaction history in the **💳 Transactions** sub-tab")
        st.markdown("2. Capital gains will be automatically calculated")
        st.markdown("3. Select tax year and export for filing")


def _render_harvest_savings(curr_year: int) -> None:
    st.markdown("#### 🌱 Harvest Savings Tracker")
    st.caption(
        "Year-to-date summary of realized losses and estimated tax savings "
        "from direct-index tax loss harvesting."
    )

    if not TAX_SAVINGS_AVAILABLE:
        st.info("Harvest savings tracker unavailable — tax_savings_tracker module not found.")
        return

    current_year = curr_year
    selected_year = st.selectbox(
        "Tax Year",
        [current_year, current_year - 1, current_year - 2],
        index=0,
        key="tax_records_selected_year",
    )

    try:
        ytd = get_ytd_summary(selected_year, None)
    except Exception as e:
        st.error(f"Could not load YTD summary: {e}")
        return

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Total Harvests", ytd.total_harvests)
    sc2.metric("Realized Losses", f"${abs(ytd.total_realized_losses):,.0f}")
    sc3.metric("Est. Tax Savings", f"${ytd.total_estimated_savings:,.0f}")
    sc4.metric(
        "Actual Savings",
        f"${ytd.total_actual_savings:,.0f}" if ytd.total_actual_savings > 0 else "TBD",
    )

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("By Term")
        term_df = pd.DataFrame({
            "Term": ["Short-Term", "Long-Term"],
            "Losses ($)": [abs(ytd.short_term_losses), abs(ytd.long_term_losses)],
            "Savings ($)": [ytd.short_term_savings, ytd.long_term_savings],
        })
        st.dataframe(
            term_df.style.format({"Losses ($)": "${:,.0f}", "Savings ($)": "${:,.0f}"}),
            use_container_width=True,
            hide_index=True,
        )

    with col2:
        st.subheader("By Account")
        if ytd.by_account:
            acct_rows = [
                {
                    "Account": acct,
                    "Harvests": stats["harvests"],
                    "Savings ($)": stats["estimated_savings"],
                }
                for acct, stats in ytd.by_account.items()
            ]
            st.dataframe(
                pd.DataFrame(acct_rows).style.format({"Savings ($)": "${:,.0f}"}),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No account-level data available for this year.")

    st.divider()

    # Performance metrics
    st.subheader("Performance Metrics")
    try:
        metrics = get_performance_metrics(selected_year)
        pm1, pm2, pm3 = st.columns(3)
        pm1.metric("Avg Loss / Harvest", f"${abs(metrics['avg_loss_per_harvest']):,.0f}")
        pm2.metric("Avg Savings / Harvest", f"${metrics['avg_savings_per_harvest']:,.0f}")
        if metrics.get("estimate_accuracy_pct", 0) > 0:
            pm3.metric("Estimate Accuracy", f"{metrics['estimate_accuracy_pct']:.1f}%")
    except Exception as e:
        st.warning(f"Could not load performance metrics: {e}")

    st.divider()

    # Harvest history
    st.subheader("Harvest History")
    try:
        history_df = get_harvest_history(selected_year, None)
        if not history_df.empty:
            display_cols = [
                "harvest_date", "symbol_sold", "symbol_bought",
                "shares", "realized_loss", "estimated_tax_savings",
            ]
            available = [c for c in display_cols if c in history_df.columns]
            st.dataframe(
                history_df[available].style.format({
                    "shares": "{:.4f}",
                    "realized_loss": "${:+,.2f}",
                    "estimated_tax_savings": "${:,.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )
            dl_bytes = history_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Export History CSV",
                data=dl_bytes,
                file_name=f"harvest_history_{selected_year}.csv",
                mime="text/csv",
                key="tax_records_harvest_export",
            )
        else:
            st.info("No harvest history for the selected period.")
    except Exception as e:
        st.warning(f"Could not load harvest history: {e}")

# Made with Bob
