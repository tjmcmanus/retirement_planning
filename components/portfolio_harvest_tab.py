"""
components/portfolio_harvest_tab.py
====================================
Unified Tax Harvesting tab for Portfolio Hub.

Two sub-tabs:
  🔍 Opportunities  — dual-scanner: portfolio_data_truth.csv (SELL) + rsp_holdings.db (BUY)
  📋 Execution Queue — approve / reject / confirm pending harvest trades

Data source architecture
------------------------
SELL side (what you own):
  Primary scan  — tax_harvesting.build_harvesting_analysis() reads portfolio_data_truth.csv,
                  filtered to Brokerage accounts. Results are enriched with RSP constituent
                  BUY candidates via replacement_selector.find_replacement_stock().
  DI scan       — direct_index_harvester.scan_harvest_opportunities() reads
                  rsp_holdings.db::direct_index_positions (positions already tracked as
                  direct-index tax lots). Deduplicated against primary scan by symbol.

BUY side (what to buy as replacement):
  replacement_selector.find_replacement_stock() queries rsp_holdings.db::rsp_constituents
  to surface wash-sale-safe, sector-matched RSP constituent buy candidates.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame

# ---------------------------------------------------------------------------
# Tax harvesting — primary SELL scanner (reads portfolio_data_truth.csv)
# ---------------------------------------------------------------------------
from tax_harvesting import (
    build_harvesting_analysis,
    classify_harvest_opportunities,
    compute_harvest_summary,
    compute_net_tax_impact,
    get_ltcg_rate_for_income,
    get_ltcg_zero_threshold,
    get_replacement_detail,
)

# ---------------------------------------------------------------------------
# RSP BUY-side replacement lookup (reads rsp_holdings.db)
# ---------------------------------------------------------------------------
try:
    from components.replacement_selector import find_replacement_stock
    REPLACEMENT_SELECTOR_AVAILABLE = True
except ImportError:
    REPLACEMENT_SELECTOR_AVAILABLE = False
    find_replacement_stock = None  # type: ignore

# ---------------------------------------------------------------------------
# DI SELL scanner (reads rsp_holdings.db::direct_index_positions)
# ---------------------------------------------------------------------------
try:
    from components.direct_index_harvester import scan_harvest_opportunities
    DI_HARVESTER_AVAILABLE = True
except ImportError:
    DI_HARVESTER_AVAILABLE = False
    scan_harvest_opportunities = None  # type: ignore

# ---------------------------------------------------------------------------
# Harvest review modal
# ---------------------------------------------------------------------------
try:
    from components.harvest_review_modal import render_harvest_review
    HARVEST_REVIEW_AVAILABLE = True
except ImportError:
    HARVEST_REVIEW_AVAILABLE = False
    render_harvest_review = None  # type: ignore

# ---------------------------------------------------------------------------
# Execution queue
# ---------------------------------------------------------------------------
from components.harvest_approval import (
    ApprovalStatus,
    get_pending_trades,
    approve_pending_trade,
    reject_pending_trade,
    confirm_trade_executed,
    revert_confirmation,
    cancel_pending_trade,
    get_approval_summary,
)


# ==============================================================================
# PUBLIC ENTRY POINT
# ==============================================================================

def render_harvest_tab(
    portdf: "DataFrame",
    curr_month: int,
    curr_year: int,
) -> None:
    """
    Render the Tax Harvesting tab (top-level Portfolio Hub tab).

    Args:
        portdf:      Current portfolio display DataFrame (all accounts).
        curr_month:  Current month (1-12).
        curr_year:   Current year.
    """
    st.markdown("### 🌾 Tax Harvesting")
    st.caption(
        "Scan your **Brokerage (taxable)** holdings for loss and gain harvesting "
        "opportunities. Replacements are sourced from the RSP S&P 500 equal-weight "
        "constituent universe to maintain market exposure while respecting wash-sale rules."
    )

    opps_tab, queue_tab = st.tabs(["🔍 Opportunities", "📋 Execution Queue"])

    with opps_tab:
        _render_opportunities(portdf, curr_month, curr_year)

    with queue_tab:
        _render_execution_queue()


# ==============================================================================
# INTERNAL: OPPORTUNITIES SUB-TAB
# ==============================================================================

def _render_opportunities(
    portdf: "DataFrame",
    curr_month: int,
    curr_year: int,
) -> None:
    """Dual-scanner harvest opportunities UI."""

    # ---- Settings expander ---------------------------------------------------
    with st.expander("⚙️ Harvest Settings", expanded=True):
        s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)

        with s_col1:
            h_agi = st.number_input(
                "Estimated AGI ($)",
                min_value=0,
                max_value=2_000_000,
                value=80_000,
                step=1_000,
                key="harvest_agi",
            )

        with s_col2:
            h_marginal = st.number_input(
                "Marginal Tax Rate (%)",
                min_value=0,
                max_value=50,
                value=22,
                step=1,
                key="harvest_marginal",
            )

        with s_col3:
            h_loss_thresh = st.number_input(
                "Loss Threshold ($)",
                min_value=0,
                max_value=100_000,
                value=500,
                step=100,
                key="harvest_loss_thresh",
            )

        with s_col4:
            h_gain_thresh = st.number_input(
                "Gain Threshold ($)",
                min_value=0,
                max_value=100_000,
                value=500,
                step=100,
                key="harvest_gain_thresh",
            )

        with s_col5:
            # Build Brokerage account list from portdf
            brokerage_accounts = ["All Brokerage"]
            if not portdf.empty and "Account" in portdf.columns:
                # portdf uses display column names; account_type is not exposed —
                # filter by accounts that have taxable positions (non-totals rows).
                # Best proxy: the Holdings editor uses "account_type" from CSV which
                # is not in the display portdf, so we expose all non-totals accounts
                # and label the selector as Brokerage only.
                accts = sorted(
                    portdf[portdf["Account"] != "Portfolio Totals"]["Account"]
                    .dropna()
                    .unique()
                    .tolist()
                )
                if accts:
                    brokerage_accounts = ["All Brokerage"] + accts

            h_account = st.selectbox(
                "Account (Brokerage)",
                brokerage_accounts,
                key="harvest_account",
                help="Harvesting only applies to taxable Brokerage accounts",
            )

        h_drop_pct = st.number_input(
            "Market Drop Trigger (%)",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            key="harvest_drop_pct",
            help="Flag when market has dropped by this % from recent high",
        )

    # ---- LTCG rate info bar --------------------------------------------------
    h_year = curr_year
    h_zero_thresh = get_ltcg_zero_threshold(h_year)
    h_ltcg_rate = get_ltcg_rate_for_income(float(h_agi), h_year)
    h_headroom = max(0.0, h_zero_thresh - float(h_agi))

    bc1, bc2, bc3, bc4 = st.columns(4)
    with bc1:
        rate_color = "🟢" if h_ltcg_rate == 0.0 else ("🟡" if h_ltcg_rate == 0.15 else "🔴")
        st.metric("Your LTCG Rate", f"{rate_color} {h_ltcg_rate:.0%}")
    with bc2:
        st.metric("0% LTCG Threshold", f"${h_zero_thresh:,.0f}")
    with bc3:
        st.metric("Headroom to 0% Rate", f"${h_headroom:,.0f}")
    with bc4:
        strategy_label = (
            "🟢 Harvest Gains (0% rate!)" if h_ltcg_rate == 0.0
            else ("🟡 Harvest Losses" if h_ltcg_rate == 0.15 else "🔴 Harvest Losses (High Rate)")
        )
        st.metric("Recommended Strategy", strategy_label)

    st.markdown("---")

    # ---- Primary scan (portfolio_data_truth.csv → Brokerage accounts) --------
    try:
        with st.spinner("Scanning portfolio holdings for harvest opportunities…"):
            h_analysis = build_harvesting_analysis(curr_month, curr_year)

        if h_analysis.empty:
            st.info("ℹ️ No taxable (Brokerage) holdings found for the current period.")
            _render_di_scan_only(h_account, h_agi, h_loss_thresh, curr_year)
            return

        h_classified = classify_harvest_opportunities(
            h_analysis,
            estimated_agi=float(h_agi),
            year=h_year,
            loss_threshold=-max(float(h_loss_thresh), 1.0),
            gain_threshold=float(h_gain_thresh),
        )
        h_summary = compute_harvest_summary(h_classified)
        h_tax_impact = compute_net_tax_impact(
            h_classified,
            estimated_agi=float(h_agi),
            year=h_year,
            marginal_ordinary_rate=float(h_marginal) / 100.0,
        )

    except Exception as e:
        st.error(f"⚠️ Error scanning portfolio holdings: {e}")
        return

    # ---- Portfolio gain/loss summary -----------------------------------------
    st.markdown("#### 📊 Portfolio Gain/Loss Summary (Brokerage Only)")
    sm1, sm2, sm3, sm4, sm5 = st.columns(5)
    with sm1:
        st.metric("Total Unrealized Gains", f"${h_summary['total_unrealized_gain']:,.0f}")
    with sm2:
        loss_val = h_summary['total_unrealized_loss']
        st.metric(
            "Total Unrealized Losses",
            f"${abs(loss_val):,.0f}",
            delta=f"-${abs(loss_val):,.0f}" if loss_val < 0 else None,
            delta_color="inverse",
        )
    with sm3:
        net = h_summary['net_unrealized']
        st.metric(
            "Net Unrealized",
            f"${net:,.0f}",
            delta=f"{'▲' if net >= 0 else '▼'} ${abs(net):,.0f}",
            delta_color="normal" if net >= 0 else "inverse",
        )
    with sm4:
        st.metric("Harvestable Losses", f"${abs(h_summary['harvestable_losses']):,.0f}")
    with sm5:
        st.metric("Harvestable Gains (0%)", f"${h_summary.get('harvestable_gains_at_zero', 0.0):,.0f}")

    # ---- Tax impact summary --------------------------------------------------
    st.markdown("#### 💰 Estimated Tax Impact")
    ti1, ti2, ti3 = st.columns(3)
    with ti1:
        st.metric(
            "Tax Savings from Losses",
            f"${h_tax_impact.ordinary_income_savings:,.0f}",
            help="Estimated tax savings from harvesting losses",
        )
    with ti2:
        st.metric(
            "Tax Cost from Gains",
            f"${h_tax_impact.tax_on_net_gains:,.0f}",
            help="Tax cost if harvesting gains",
        )
    with ti3:
        net_benefit = h_tax_impact.net_tax_impact
        st.metric(
            "Net Tax Impact",
            f"${net_benefit:,.0f}",
            delta=f"{'▲' if net_benefit >= 0 else '▼'} ${abs(net_benefit):,.0f}",
            delta_color="normal" if net_benefit >= 0 else "inverse",
            help="Net tax impact from all harvesting opportunities",
        )

    st.markdown("---")

    # ---- Market drop trigger -------------------------------------------------
    try:
        from tax_harvesting import check_market_drop_trigger
        drop_result = check_market_drop_trigger(h_analysis, drop_threshold_pct=float(h_drop_pct))
        if drop_result["triggered"]:
            st.warning(drop_result["message"])
        else:
            st.success(f"✅ {drop_result['message']}")
    except Exception:
        pass  # Non-critical

    st.markdown("---")

    # ---- Recommendations table -----------------------------------------------
    st.markdown("#### 🎯 Harvesting Recommendations")
    display_cols = [
        "Account", "Symbol", "Name", "Sector",
        "Qty", "Purchase Price", "Current Price",
        "Current Value", "Cost Basis", "Unrealized G/L",
        "Return %", "Days Held", "Gain Type", "Recommendation",
    ]
    h_display = h_classified[display_cols].copy()
    h_display["Purchase Price"] = h_display["Purchase Price"].map(lambda x: f"${x:,.2f}")
    h_display["Current Price"] = h_display["Current Price"].map(lambda x: f"${x:,.2f}")
    h_display["Current Value"] = h_display["Current Value"].map(lambda x: f"${x:,.0f}")
    h_display["Cost Basis"] = h_display["Cost Basis"].map(lambda x: f"${x:,.0f}")
    h_display["Unrealized G/L"] = h_display["Unrealized G/L"].map(lambda x: f"${x:,.0f}")
    h_display["Return %"] = h_display["Return %"].map(lambda x: f"{x:.1f}%")
    h_display["Qty"] = h_display["Qty"].map(lambda x: f"{x:,.0f}")
    st.dataframe(
        h_display,
        hide_index=True,
        height=(len(h_display) + 1) * 38 + 3,
        use_container_width=True,
    )

    st.markdown("---")

    # ---- Replacement suggestions (enriched with RSP constituents) ------------
    st.markdown("#### 🔄 Wash-Sale-Safe Replacement Suggestions")
    st.caption(
        "Static suggestions come from the curated wash-sale map. "
        "RSP constituent suggestions come from the direct-indexing universe in rsp_holdings.db."
    )

    harvest_opps = h_classified[h_classified["Recommendation"].str.contains("Harvest", na=False)]
    if not harvest_opps.empty:
        for _, opp in harvest_opps.iterrows():
            symbol = str(opp["Symbol"])
            recommendation = str(opp["Recommendation"])

            with st.expander(f"🔄 {symbol} — {recommendation}", expanded=False):
                c_left, c_right = st.columns(2)

                with c_left:
                    st.markdown("**Current Position:**")
                    st.markdown(f"- Symbol: `{symbol}`")
                    st.markdown(f"- Unrealized G/L: `{opp['Unrealized G/L']}`")
                    st.markdown(f"- Return: `{opp['Return %']}`")
                    st.markdown(f"- Term: `{opp['Gain Type']}`")

                with c_right:
                    # Static curated list
                    static_replacements = get_replacement_detail(symbol)

                    # RSP constituent replacements (BUY side from rsp_holdings.db)
                    rsp_replacements: list = []
                    if REPLACEMENT_SELECTOR_AVAILABLE and find_replacement_stock is not None:
                        try:
                            sector = str(opp.get("Sector", ""))
                            rsp_candidates = find_replacement_stock(
                                symbol=symbol,
                                sector=sector,
                            )
                            if rsp_candidates:
                                rsp_replacements = rsp_candidates if isinstance(rsp_candidates, list) else [rsp_candidates]
                        except Exception:
                            pass

                    if static_replacements or rsp_replacements:
                        st.markdown("**Suggested Replacements:**")
                        if rsp_replacements:
                            st.markdown("*RSP Universe (direct-index buy candidates):*")
                            for r in rsp_replacements[:3]:
                                if hasattr(r, "symbol"):
                                    st.markdown(
                                        f"- `{r.symbol}` — {getattr(r, 'name', '')} "
                                        f"({getattr(r, 'sector', '')})"
                                    )
                                else:
                                    st.markdown(f"- {r}")
                        if static_replacements:
                            st.markdown("*Curated wash-sale map:*")
                            st.markdown(static_replacements)
                    else:
                        st.info(
                            "No specific replacement suggestions available. "
                            "Consider similar ETFs or index funds in the same sector."
                        )
    else:
        st.info("No harvest opportunities identified with current thresholds.")

    # ---- DI portfolio scan (additive — positions in rsp_holdings.db) ---------
    _render_di_scan_additive(h_account, h_agi, h_loss_thresh, curr_year, primary_symbols=set(
        h_classified["Symbol"].astype(str).tolist()
    ))


def _render_di_scan_only(
    account_filter: str,
    agi: float,
    min_loss: float,
    curr_year: int,
) -> None:
    """Run the DI scan when the primary scan found no holdings."""
    _render_di_scan_additive(account_filter, agi, min_loss, curr_year, primary_symbols=set())


def _render_di_scan_additive(
    account_filter: str,
    agi: float,
    min_loss: float,
    curr_year: int,
    primary_symbols: set,
) -> None:
    """
    Run the Direct Index scanner against rsp_holdings.db and display any
    opportunities not already shown in the primary scan results.
    """
    if not DI_HARVESTER_AVAILABLE or scan_harvest_opportunities is None:
        return

    try:
        scan_acct = None if account_filter == "All Brokerage" else account_filter
        di_opps = scan_harvest_opportunities(
            account_name=scan_acct,
            current_agi=float(agi),
            loss_threshold_pct=10.0,
        )
        # Deduplicate: only show DI opportunities not in primary scan
        di_opps = [o for o in di_opps if o.symbol not in primary_symbols]
        di_opps = [o for o in di_opps if abs(o.unrealized_loss) >= min_loss]
    except Exception:
        return

    if not di_opps:
        return

    st.markdown("---")
    st.markdown("#### 🗂 Direct Index Portfolio — Additional Opportunities")
    st.caption(
        "These positions are tracked in your direct-index tax lot database "
        "(rsp_holdings.db) and are not in the list above."
    )

    total_losses = sum(abs(o.unrealized_loss) for o in di_opps)
    total_savings = sum(o.estimated_tax_savings for o in di_opps)
    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("DI Opportunities", len(di_opps))
    dc2.metric("Total DI Losses", f"${total_losses:,.0f}")
    dc3.metric("Est. DI Savings", f"${total_savings:,.0f}")

    st.divider()

    for i, opp in enumerate(di_opps):
        label = (
            f"{'⭐' * opp.harvest_priority}  "
            f"[DI] {opp.symbol} — "
            f"${abs(opp.unrealized_loss):,.0f} loss ({opp.loss_percentage:.1f}%)  "
            f"{'🔒 Wash-sale risk' if opp.is_wash_sale_risk else ''}"
        )
        reviewing_key = f"di_reviewing_{opp.symbol}_di_{i}"

        with st.expander(label, expanded=(i == 0)):
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Shares", f"{opp.shares:,.2f}")
            q2.metric("Loss", f"${abs(opp.unrealized_loss):,.0f}")
            q3.metric("Est. savings", f"${opp.estimated_tax_savings:,.0f}")
            q4.metric("Replacement", opp.recommended_replacement or "None")

            if not st.session_state.get(reviewing_key):
                if opp.can_harvest and HARVEST_REVIEW_AVAILABLE and render_harvest_review is not None:
                    if st.button(
                        "🔍 Full Review",
                        key=f"di_open_review_{i}",
                        use_container_width=False,
                    ):
                        st.session_state[reviewing_key] = True
                        st.rerun()
                elif not opp.can_harvest:
                    st.warning(
                        "⚠️ Cannot harvest: "
                        + (opp.wash_sale_reason or "No replacement available.")
                    )
            else:
                if render_harvest_review is not None:
                    execution = render_harvest_review(opp, key=f"di_hr_{opp.symbol}_{i}")
                    if execution is not None:
                        queue = st.session_state.setdefault("di_queue_executions", [])
                        queue.append(execution)
                        st.session_state.pop(reviewing_key, None)
                        st.rerun()
                    if st.session_state.get(f"di_hr_{opp.symbol}_{i}_cancelled"):
                        st.session_state.pop(f"di_hr_{opp.symbol}_{i}_cancelled", None)
                        st.session_state.pop(reviewing_key, None)
                        st.rerun()


# ==============================================================================
# INTERNAL: EXECUTION QUEUE SUB-TAB
# ==============================================================================

def _render_execution_queue() -> None:
    """Render the pending/approved/executed trade queue."""
    st.markdown("#### 📋 Execution Queue")
    st.caption(
        "Harvest plans awaiting manual execution in Schwab. "
        "Approve → execute in Schwab → Confirm Executed to record the tax savings."
    )

    # ---- Summary KPIs --------------------------------------------------------
    appr_summary = get_approval_summary()
    ks1, ks2, ks3, ks4 = st.columns(4)
    ks1.metric("Pending review", appr_summary["pending"])
    ks2.metric("Approved (ready)", appr_summary["approved"])
    ks3.metric("Executed YTD", appr_summary["executed"])
    ks4.metric("Pending savings", f"${appr_summary['pending_savings']:,.0f}")

    st.divider()

    # ---- Status filter -------------------------------------------------------
    status_filter = st.selectbox(
        "Show",
        ["Pending & Approved", "All", "Executed", "Rejected / Cancelled"],
        index=0,
        key="hub_q_status_filter",
    )

    _status_map = {
        "Pending & Approved": [ApprovalStatus.PENDING, ApprovalStatus.APPROVED],
        "All":                 None,
        "Executed":            [ApprovalStatus.EXECUTED],
        "Rejected / Cancelled": [ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED],
    }
    _filter = _status_map[status_filter]

    all_trades = get_pending_trades()
    if _filter is not None:
        all_trades = [t for t in all_trades if t.status in _filter]

    if not all_trades:
        st.info(
            "No trades match the selected filter. "
            "Approve a harvest on the **Opportunities** tab to create one."
        )
        return

    _STATUS_BADGE = {
        ApprovalStatus.PENDING:   "🟡 Pending review",
        ApprovalStatus.APPROVED:  "🟢 Approved — execute in Schwab",
        ApprovalStatus.EXECUTED:  "✅ Executed",
        ApprovalStatus.REJECTED:  "🔴 Rejected",
        ApprovalStatus.CANCELLED: "⚫ Cancelled",
    }

    for trade in all_trades:
        tid = trade.trade_id
        badge = _STATUS_BADGE.get(trade.status, trade.status.value)

        with st.expander(
            f"{trade.sell_symbol} → {trade.buy_symbol}  |  {badge}  |  "
            f"Est. savings: ${trade.estimated_savings:,.0f}  |  "
            f"ID: {tid[:8]}…",
            expanded=(trade.status == ApprovalStatus.APPROVED),
        ):
            d1, d2 = st.columns(2)
            with d1:
                st.markdown("**Sell**")
                st.markdown(
                    f"- Symbol: **{trade.sell_symbol}**\n"
                    f"- Shares: {trade.shares:,.4f}\n"
                    f"- Est. price: ${trade.sell_price:,.2f}\n"
                    f"- Est. value: ${trade.sell_value():,.2f}\n"
                    f"- Est. loss: ${trade.estimated_loss:+,.2f}"
                )
            with d2:
                st.markdown("**Buy**")
                st.markdown(
                    f"- Symbol: **{trade.buy_symbol}**\n"
                    f"- Shares: ~{trade.buy_shares:,.4f}\n"
                    f"- Est. price: ${trade.buy_price:,.2f}\n"
                    f"- Est. value: ${trade.buy_shares * trade.buy_price:,.2f}"
                )

            st.caption(
                f"Account: {trade.account_name}  |  "
                f"Lot method: {trade.lot_method}  |  "
                f"Created: {trade.created_at.strftime('%Y-%m-%d %H:%M')}"
            )
            if trade.review_notes:
                st.caption(f"Notes: {trade.review_notes}")

            # Download trade instructions CSV
            instr_df = pd.DataFrame([
                {
                    "Action": "SELL", "Symbol": trade.sell_symbol,
                    "Shares": round(trade.shares, 4),
                    "Est. Price": trade.sell_price,
                    "Est. Value": trade.sell_value(),
                    "Notes": f"Tax loss harvest — lot method {trade.lot_method}",
                },
                {
                    "Action": "BUY", "Symbol": trade.buy_symbol,
                    "Shares": round(trade.buy_shares, 4),
                    "Est. Price": trade.buy_price,
                    "Est. Value": round(trade.buy_shares * trade.buy_price, 2),
                    "Notes": f"Replacement for {trade.sell_symbol}",
                },
            ])
            st.download_button(
                "📄 Download Trade Instructions",
                data=instr_df.to_csv(index=False).encode("utf-8"),
                file_name=f"harvest_{trade.sell_symbol}_{tid[:8]}.csv",
                mime="text/csv",
                key=f"hub_q_dl_{tid}",
            )

            st.divider()

            # Action buttons — vary by status
            if trade.status == ApprovalStatus.PENDING:
                ba1, ba2, ba3 = st.columns(3)
                with ba1:
                    if st.button(
                        "✅ Approve",
                        key=f"hub_q_approve_{tid}",
                        type="primary",
                        use_container_width=True,
                    ):
                        approve_pending_trade(tid)
                        st.success("Approved! Execute the trades in Schwab then click Confirm Executed.")
                        st.rerun()
                with ba2:
                    reject_reason = st.text_input(
                        "Rejection reason (optional)",
                        key=f"hub_q_reject_reason_{tid}",
                        label_visibility="collapsed",
                        placeholder="Rejection reason…",
                    )
                    if st.button("✖ Reject", key=f"hub_q_reject_{tid}", use_container_width=True):
                        reject_pending_trade(tid, reason=reject_reason)
                        st.warning("Trade rejected.")
                        st.rerun()
                with ba3:
                    if st.button("🗑 Cancel", key=f"hub_q_cancel_{tid}", use_container_width=True):
                        cancel_pending_trade(tid)
                        st.warning("Trade cancelled.")
                        st.rerun()

            elif trade.status == ApprovalStatus.APPROVED:
                st.info("👆 Execute both trades manually in Schwab, then confirm below.")
                ce1, ce2, ce3, ce4 = st.columns(4)
                with ce1:
                    actual_sell = st.number_input(
                        "Actual sell price",
                        min_value=0.0,
                        value=float(trade.sell_price),
                        step=0.01,
                        key=f"hub_q_actual_sell_{tid}",
                        format="%.2f",
                    )
                with ce2:
                    actual_buy = st.number_input(
                        "Actual buy price",
                        min_value=0.0,
                        value=float(trade.buy_price),
                        step=0.01,
                        key=f"hub_q_actual_buy_{tid}",
                        format="%.2f",
                    )
                with ce3:
                    confirm_notes = st.text_input(
                        "Confirmation notes (optional)",
                        key=f"hub_q_confirm_notes_{tid}",
                        label_visibility="collapsed",
                        placeholder="e.g. order #12345…",
                    )
                with ce4:
                    if st.button(
                        "🏁 Confirm Executed",
                        key=f"hub_q_confirm_{tid}",
                        type="primary",
                        use_container_width=True,
                    ):
                        confirm_trade_executed(
                            tid,
                            actual_sell_price=actual_sell,
                            actual_buy_price=actual_buy,
                            notes=confirm_notes,
                        )
                        st.success(
                            f"Confirmed! Tax savings of "
                            f"${trade.estimated_savings:,.0f} recorded."
                        )
                        st.rerun()

                if st.button("✖ Cancel trade", key=f"hub_q_cancel_approved_{tid}"):
                    cancel_pending_trade(tid)
                    st.warning("Trade cancelled.")
                    st.rerun()

            elif trade.status == ApprovalStatus.EXECUTED:
                st.success("✅ Trade confirmed as executed.")
                if st.button(
                    "↩ Undo confirmation",
                    key=f"hub_q_revert_{tid}",
                    help="Revert to Approved status if you confirmed by mistake",
                ):
                    revert_confirmation(tid, reason="Reverted by user")
                    st.info("Reverted to Approved.")
                    st.rerun()

# Made with Bob
