"""
Harvest Review Modal
====================
Inline Streamlit component that shows a comprehensive review panel for a
single harvest opportunity before the user approves execution.

Displays:
- Sell position details (lots, holding period, term)
- Replacement buy details with alternatives selector
- Tax impact breakdown
- Wash sale warnings
- Action buttons: Cancel / Generate Instructions / Approve

Usage
-----
    from components.harvest_review_modal import render_harvest_review

    if render_harvest_review(opportunity, key="review_AAPL"):
        # User approved — execution plan was created and saved
        st.success("Harvest approved!")

Author: Bob
Date: April 2026
Version: 1.0
"""

from __future__ import annotations

import logging
from typing import Optional

import streamlit as st

from components.direct_index_harvester import HarvestOpportunity
from components.harvest_executor import (
    HarvestExecution,
    create_harvest_execution,
    export_trade_instructions,
)
from components.harvest_approval import (
    create_pending_trade,
    approve_pending_trade,
)
from components.cost_basis_tracker import LotSelectionMethod
from components.replacement_selector import find_replacement_stock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lot method labels
# ---------------------------------------------------------------------------

_LOT_METHOD_LABELS = {
    LotSelectionMethod.HIFO: "HIFO — Highest cost first (maximise loss)",
    LotSelectionMethod.FIFO: "FIFO — First in, first out",
    LotSelectionMethod.LIFO: "LIFO — Last in, first out",
    LotSelectionMethod.LOFO: "LOFO — Lowest cost first",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _priority_stars(priority: int) -> str:
    filled = "⭐" * priority
    empty = "☆" * (5 - priority)
    return filled + empty


def _term_label(is_long_term: bool) -> str:
    return "Long-term (≥365 days)" if is_long_term else "Short-term (<365 days)"


def _tax_rate(opp: HarvestOpportunity) -> float:
    return opp.ltcg_rate if opp.is_long_term else opp.marginal_rate


# ---------------------------------------------------------------------------
# Public component
# ---------------------------------------------------------------------------

def render_harvest_review(
    opportunity: HarvestOpportunity,
    *,
    key: str,
    on_approved: Optional[callable] = None,
) -> Optional[HarvestExecution]:
    """
    Render a detailed harvest review panel for *opportunity*.

    Parameters
    ----------
    opportunity:
        The ``HarvestOpportunity`` to review.
    key:
        Unique Streamlit key prefix (use the ticker, e.g. ``"AAPL"``).
    on_approved:
        Optional callback called with the ``HarvestExecution`` after approval.

    Returns
    -------
    HarvestExecution if the user approved, else None.
    """
    opp = opportunity

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    replacement_sym = opp.recommended_replacement or "N/A"
    st.markdown(
        f"### Review Harvest: {opp.symbol} → {replacement_sym}  "
        f"&nbsp;&nbsp;{_priority_stars(opp.harvest_priority)}"
    )

    if opp.is_wash_sale_risk:
        st.error(f"⛔ Wash Sale Risk: {opp.wash_sale_reason}")
    elif not opp.can_harvest:
        st.warning("⚠️ This position cannot be harvested (see notes below).")

    # ------------------------------------------------------------------
    # Two-column layout
    # ------------------------------------------------------------------
    left, right = st.columns([3, 2])

    with left:
        # ---- Sell side -----------------------------------------------
        st.markdown("#### Sell Position")

        loss_pct_color = "red" if opp.loss_percentage < 0 else "green"
        sell_rows = [
            ("Symbol", opp.symbol),
            ("Account", opp.account_name),
            ("Shares", f"{opp.shares:,.4f}"),
            ("Purchase price", f"${opp.purchase_price:,.2f}"),
            ("Current price", f"${opp.current_price:,.2f}"),
            ("Cost basis", f"${opp.shares * opp.purchase_price:,.2f}"),
            ("Current value", f"${opp.shares * opp.current_price:,.2f}"),
            (
                "Unrealized loss",
                f"**${opp.unrealized_loss:+,.2f}  ({opp.loss_percentage:.1f}%)**",
            ),
            ("Holding period", f"{opp.holding_period_days} days"),
            ("Term", _term_label(opp.is_long_term)),
        ]
        for label, value in sell_rows:
            col_a, col_b = st.columns([2, 3])
            col_a.markdown(f"**{label}**")
            col_b.markdown(value)

        st.divider()

        # ---- Buy side ------------------------------------------------
        st.markdown("#### Buy Replacement")

        # Let user pick replacement from the alternatives
        all_replacements = []
        if opp.recommended_replacement:
            all_replacements.append(opp.recommended_replacement)
        all_replacements.extend(
            [r for r in opp.alternative_replacements if r != opp.recommended_replacement]
        )

        if not all_replacements:
            st.warning("No replacement candidates available for this position.")
            selected_replacement = None
        else:
            selected_replacement = st.selectbox(
                "Select replacement stock",
                options=all_replacements,
                index=0,
                key=f"{key}_replacement_select",
                help="Primary replacement shown first; alternatives are same-sector stocks.",
            )

        if selected_replacement:
            buy_value = opp.shares * opp.current_price
            buy_shares = (
                buy_value / opp.replacement_price if opp.replacement_price > 0 else 0.0
            )
            buy_rows = [
                ("Symbol", selected_replacement),
                ("Sector", opp.replacement_sector),
                ("Estimated price", f"${opp.replacement_price:,.2f}"),
                ("Shares to buy", f"~{buy_shares:,.2f}"),
                ("Investment amount", f"${buy_value:,.2f}"),
            ]
            for label, value in buy_rows:
                col_a, col_b = st.columns([2, 3])
                col_a.markdown(f"**{label}**")
                col_b.markdown(value)

    with right:
        # ---- Tax impact ----------------------------------------------
        st.markdown("#### Tax Impact")

        rate_pct = _tax_rate(opp) * 100
        tax_rows = [
            ("Realized loss", f"**${abs(opp.unrealized_loss):,.2f}**"),
            ("Tax rate", f"{rate_pct:.0f}%"),
            ("Est. tax savings", f"**${opp.estimated_tax_savings:,.2f}**"),
            (
                "Wash sale risk",
                "✅ None" if not opp.is_wash_sale_risk else "⛔ Present",
            ),
        ]
        for label, value in tax_rows:
            col_a, col_b = st.columns([2, 3])
            col_a.markdown(f"**{label}**")
            col_b.markdown(value)

        st.divider()

        # ---- Lot selection ----------------------------------------
        st.markdown("#### Lot Selection")
        lot_method_label = st.selectbox(
            "Cost basis method",
            options=list(_LOT_METHOD_LABELS.keys()),
            format_func=lambda m: _LOT_METHOD_LABELS[m],
            index=0,  # HIFO default
            key=f"{key}_lot_method",
            help="HIFO maximises the loss realised and is usually optimal for tax harvesting.",
        )

        st.divider()

        # ---- Important notes --------------------------------------
        st.markdown("#### Notes")
        st.info(
            f"• Do **not** repurchase **{opp.symbol}** for 30 days after selling "
            f"(IRS wash sale rule).\n"
            f"• Replacement maintains **{opp.replacement_sector}** sector exposure.\n"
            f"• Review replacement stock fundamentals before approving."
        )

        if opp.notes:
            st.caption(f"Additional: {opp.notes}")

    # ------------------------------------------------------------------
    # Action buttons
    # ------------------------------------------------------------------
    st.divider()
    btn_cancel, btn_instructions, btn_approve = st.columns([2, 3, 3])

    result: Optional[HarvestExecution] = None

    with btn_cancel:
        if st.button("✖ Cancel", key=f"{key}_cancel", use_container_width=True):
            # Signal caller to close the review panel
            st.session_state[f"{key}_cancelled"] = True
            st.rerun()

    with btn_instructions:
        if selected_replacement and st.button(
            "📄 Generate Instructions",
            key=f"{key}_instructions",
            use_container_width=True,
        ):
            try:
                execution = create_harvest_execution(
                    opportunity=opp,
                    replacement_symbol=selected_replacement,
                    lot_selection_method=lot_method_label,
                )
                csv_path = export_trade_instructions(execution.execution_id)
                import pandas as pd
                dl_df = pd.read_csv(csv_path)
                st.download_button(
                    "⬇ Download CSV",
                    data=dl_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"harvest_{opp.symbol}_instructions.csv",
                    mime="text/csv",
                    key=f"{key}_dl",
                )
                st.session_state[f"{key}_pending_execution"] = execution
            except Exception as exc:
                logger.exception("Failed to generate trade instructions")
                st.error(f"Error: {exc}")

    with btn_approve:
        disabled = (
            not opp.can_harvest
            or not selected_replacement
            or opp.is_wash_sale_risk
        )
        if st.button(
            "✅ Approve Harvest",
            key=f"{key}_approve",
            type="primary",
            disabled=disabled,
            use_container_width=True,
        ):
            try:
                # Re-use a pending execution if instructions were already generated
                if f"{key}_pending_execution" in st.session_state:
                    execution = st.session_state.pop(f"{key}_pending_execution")
                else:
                    execution = create_harvest_execution(
                        opportunity=opp,
                        replacement_symbol=selected_replacement,
                        lot_selection_method=lot_method_label,
                    )

                from components.harvest_executor import approve_execution
                approve_execution(execution.execution_id)

                # Bridge: create a linked PendingTrade so this harvest appears
                # in the Execution Queue tab (which reads from pending_trades).
                # We immediately approve it to match the HarvestExecution status.
                buy_value = opp.shares * opp.current_price
                buy_shares = (
                    buy_value / opp.replacement_price
                    if opp.replacement_price > 0 else 0.0
                )
                pending = create_pending_trade(
                    sell_symbol=opp.symbol,
                    buy_symbol=selected_replacement,
                    account_name=opp.account_name,
                    shares=opp.shares,
                    sell_price=opp.current_price,
                    buy_price=opp.replacement_price,
                    estimated_loss=opp.unrealized_loss,
                    estimated_savings=opp.estimated_tax_savings,
                    lot_method=lot_method_label.value
                        if hasattr(lot_method_label, "value") else str(lot_method_label),
                    execution_id=execution.execution_id,
                )
                approve_pending_trade(pending.trade_id)

                result = execution
                st.session_state[f"{key}_approved"] = True
                st.success(
                    f"✅ Harvest approved! Execution ID: `{execution.execution_id[:8]}…`  \n"
                    f"Execute the trades in Schwab, then confirm on the **Execution Queue** tab."
                )

                if on_approved is not None:
                    on_approved(execution)

            except Exception as exc:
                logger.exception("Harvest approval failed")
                st.error(f"Approval failed: {exc}")

    return result
