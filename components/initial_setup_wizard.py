"""
Initial Setup Wizard
====================
Step-by-step wizard to guide a user through the first-time setup of their
Direct Indexing portfolio.

Workflow
--------
Step 1 – Investment Amount
Step 2 – Configuration (fractional shares, min trade size, exclusions)
Step 3 – Review & Export (summary + download links)
Step 4 – Execution Instructions (what to do next in Schwab)

The wizard is stateless between Streamlit reruns; all progress is stored in
st.session_state under the ``di_wizard`` key.

Author: Bob
Date: April 2026
Version: 1.0
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st

from components.initial_portfolio_generator import (
    PortfolioSummary,
    InitialPurchase,
    generate_initial_portfolio,
    load_taxable_symbols,
    export_to_csv,
    export_to_markdown,
    export_to_schwab_format,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------

_STATE_KEY = "di_wizard"
_STEP_KEY = f"{_STATE_KEY}.step"


def _state() -> dict:
    """Return the wizard's mutable state dict, initialising if absent."""
    if _STATE_KEY not in st.session_state:
        st.session_state[_STATE_KEY] = {
            "step": 1,
            "total_investment": 500_000.0,
            "allow_fractional": True,
            "min_trade_size": 100.0,
            "exclude_symbols_raw": "",
            "refresh_prices": False,
            "index_coverage_pct": 100,
            "weighting_mode": "stock",
            "purchases": None,    # List[InitialPurchase] after generation
            "summary": None,      # PortfolioSummary after generation
        }
    return st.session_state[_STATE_KEY]


def _go(step: int) -> None:
    _state()["step"] = step


# ---------------------------------------------------------------------------
# Step renderers
# ---------------------------------------------------------------------------

def _render_step_indicator(current: int) -> None:
    steps = ["Amount", "Configure", "Review", "Execute"]
    cols = st.columns(len(steps))
    for i, (col, label) in enumerate(zip(cols, steps), start=1):
        with col:
            if i < current:
                st.markdown(
                    f"<div style='text-align:center;color:#22c55e;font-weight:600'>"
                    f"✓ {label}</div>",
                    unsafe_allow_html=True,
                )
            elif i == current:
                st.markdown(
                    f"<div style='text-align:center;color:#3b82d4;font-weight:700'>"
                    f"● {label}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align:center;color:#9ca3af'>"
                    f"○ {label}</div>",
                    unsafe_allow_html=True,
                )
    st.divider()


def _step1_amount() -> None:
    """Step 1: ask how much to invest."""
    s = _state()

    st.subheader("Step 1 — Investment Amount")
    mode = s.get("weighting_mode", "stock")
    if mode == "sector":
        mode_note = (
            "Your investment will be split **equally across sectors** "
            "(each sector gets ~9.1%), then equally across stocks within each sector."
        )
    else:
        mode_note = (
            "Your investment will be split **equally across every stock** "
            "(true RSP equal-weight). Sector allocations reflect how many companies "
            "are in each sector."
        )
    st.markdown(mode_note + "  \nUse **Index Coverage** in Step 2 to control how many stocks you buy.")

    total = st.number_input(
        "Total amount to invest ($)",
        min_value=10_000.0,
        max_value=100_000_000.0,
        value=float(s["total_investment"]),
        step=10_000.0,
        format="%.0f",
        help="Minimum $10,000 recommended for sufficient diversification",
    )

    # Live preview — use coverage_pct from state if already set
    import math
    coverage_pct = float(s.get("index_coverage_pct", 100))
    est_total = 503  # full S&P 500 pool
    est_stocks = max(1, math.ceil(est_total * coverage_pct / 100.0))
    est_pool = est_total - est_stocks
    est_per_stock = total / est_stocks
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stocks to buy", f"~{est_stocks}")
    c2.metric("Replacement pool", f"~{est_pool}")
    c3.metric("Avg position size", f"${est_per_stock:,.0f}")
    c4.metric("Total investment", f"${total:,.0f}")

    if total < 50_000:
        st.warning(
            "⚠️ Below $50,000 some positions may fall under the minimum trade size "
            "and be excluded. Consider a larger initial investment."
        )

    st.markdown("")
    if st.button("Next →", type="primary"):
        s["total_investment"] = total
        _go(2)
        st.rerun()


def _step2_configure() -> None:
    """Step 2: portfolio configuration options."""
    s = _state()

    st.subheader("Step 2 — Configure Portfolio")

    col1, col2 = st.columns(2)

    with col1:
        allow_fractional = st.checkbox(
            "Allow fractional shares",
            value=bool(s["allow_fractional"]),
            help="Fractional shares maximise capital deployment but not all brokers support them.",
        )

        min_trade = st.number_input(
            "Minimum trade size ($)",
            min_value=0.0,
            max_value=10_000.0,
            value=float(s["min_trade_size"]),
            step=50.0,
            help="Positions below this size will be flagged in the export.",
        )

        import math
        coverage_pct = st.slider(
            "Index coverage (%)",
            min_value=10,
            max_value=100,
            value=int(s.get("index_coverage_pct", 100)),
            step=5,
            help=(
                "Percentage of the ~500 S&P 500 stocks to BUY as your direct index. "
                "The remaining stocks become your tax-loss harvesting replacement pool. "
                "Stocks are chosen proportionally across all 11 GICS sectors."
            ),
        )
        est_total = 503
        est_buy = max(1, math.ceil(est_total * coverage_pct / 100.0))
        est_pool = est_total - est_buy
        st.caption(f"~{est_buy} stocks purchased · ~{est_pool} in replacement pool")

    with col2:
        weighting_mode = st.radio(
            "Position weighting",
            options=["stock", "sector"],
            index=0 if s.get("weighting_mode", "stock") == "stock" else 1,
            format_func=lambda x: (
                "Equal weight per stock (RSP-style)"
                if x == "stock"
                else "Equal weight per sector (balanced sectors)"
            ),
            help=(
                "Stock: every stock gets the same dollar amount — matches RSP's construction. "
                "Sector: each of the 11 GICS sectors gets ~9.1% of the portfolio, "
                "then stocks within each sector are equal-weighted."
            ),
        )

        refresh = st.checkbox(
            "Refresh prices before generating",
            value=bool(s["refresh_prices"]),
            help="Pull latest prices from Yahoo Finance (takes ~30s).",
        )

        exclude_raw = st.text_area(
            "Symbols to exclude (comma-separated)",
            value=s["exclude_symbols_raw"],
            height=80,
            placeholder="e.g. TSLA, GME, AMC",
            help="Enter ticker symbols you do not want to hold.",
        )

        # Show taxable holdings that will be auto-excluded
        taxable_preview = load_taxable_symbols()
        if taxable_preview:
            st.caption(
                f"🚫 **Auto-excluded** ({len(taxable_preview)} taxable holdings): "
                + ", ".join(f"`{s}`" for s in taxable_preview)
            )
        else:
            st.caption("✅ No taxable holdings found — nothing auto-excluded.")

    nav_col1, nav_col2 = st.columns([1, 4])
    with nav_col1:
        if st.button("← Back"):
            s.update(
                allow_fractional=allow_fractional,
                min_trade_size=min_trade,
                refresh_prices=refresh,
                exclude_symbols_raw=exclude_raw,
                index_coverage_pct=coverage_pct,
                weighting_mode=weighting_mode,
            )
            _go(1)
            st.rerun()

    with nav_col2:
        if st.button("Generate Portfolio →", type="primary"):
            s.update(
                allow_fractional=allow_fractional,
                min_trade_size=min_trade,
                refresh_prices=refresh,
                exclude_symbols_raw=exclude_raw,
                index_coverage_pct=coverage_pct,
                weighting_mode=weighting_mode,
                purchases=None,
                summary=None,
            )
            exclude_list: List[str] = [
                sym.strip().upper()
                for sym in exclude_raw.split(",")
                if sym.strip()
            ]
            with st.spinner("Generating initial portfolio…"):
                try:
                    purchases, summary = generate_initial_portfolio(
                        total_investment=s["total_investment"],
                        min_trade_size=min_trade,
                        allow_fractional=allow_fractional,
                        exclude_symbols=exclude_list or None,
                        refresh_prices=refresh,
                        index_coverage_pct=coverage_pct,
                        weighting_mode=weighting_mode,
                    )
                    s["purchases"] = purchases
                    s["summary"] = summary
                    _go(3)
                    st.rerun()
                except Exception as exc:
                    logger.exception("Portfolio generation failed")
                    st.error(f"Generation failed: {exc}")


def _step3_review() -> None:
    """Step 3: review generated portfolio and download exports."""
    s = _state()
    purchases: Optional[List[InitialPurchase]] = s.get("purchases")
    summary: Optional[PortfolioSummary] = s.get("summary")

    if not purchases or not summary:
        st.error("Portfolio data missing — please go back and regenerate.")
        if st.button("← Back"):
            _go(2)
            st.rerun()
        return

    st.subheader("Step 3 — Review & Export")

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Stocks", f"{summary.total_stocks:,}")
    c2.metric("Total Investment", f"${summary.actual_investment:,.0f}")
    c3.metric("Unallocated Cash", f"${summary.unallocated_cash:,.0f}")
    c4.metric("Avg Position", f"${summary.average_position_size:,.0f}")

    if summary.taxable_excluded:
        st.info(
            f"ℹ️ **{len(summary.taxable_excluded)} symbol(s) excluded** — already held in a "
            f"taxable (Brokerage) account: `{'`, `'.join(summary.taxable_excluded)}`"
        )

    if summary.stocks_below_min > 0:
        st.warning(
            f"⚠️ {summary.stocks_below_min} positions are below the "
            f"${s['min_trade_size']:,.0f} minimum trade size — they are included "
            "but flagged. Consider raising your investment amount."
        )

    st.divider()

    # Sector breakdown
    with st.expander("Sector breakdown", expanded=True):
        sector_rows = [
            {
                "Sector": sec,
                "Stocks": info["num_stocks"],
                "Total ($)": info["total_amount"],
                "Weight (%)": info.get("weight", 0.0),
            }
            for sec, info in sorted(
                summary.by_sector.items(),
                key=lambda x: x[1]["total_amount"],
                reverse=True,
            )
        ]
        st.dataframe(
            pd.DataFrame(sector_rows).style.format(
                {"Total ($)": "${:,.0f}", "Weight (%)": "{:.1f}%"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    # Position table preview
    with st.expander("All positions (first 50 shown)", expanded=False):
        preview_df = pd.DataFrame([p.to_dict() for p in purchases[:50]])
        st.dataframe(
            preview_df[
                ["symbol", "name", "sector", "shares_to_buy",
                 "current_price", "actual_amount"]
            ].style.format(
                {"current_price": "${:.2f}", "actual_amount": "${:,.0f}"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # Download buttons
    st.markdown("**Download purchase instructions:**")
    dl_col1, dl_col2, dl_col3 = st.columns(3)

    # Build in-memory CSV bytes so Streamlit can serve without writing a file
    csv_df = pd.DataFrame([p.to_dict() for p in purchases])
    csv_bytes = csv_df.to_csv(index=False).encode("utf-8")

    schwab_data = [
        {
            "Action": "BUY",
            "Symbol": p.symbol,
            "Quantity": p.shares_to_buy + (round(p.fractional_shares, 4) if s["allow_fractional"] else 0),
            "OrderType": p.order_type,
            "TimeInForce": "DAY",
        }
        for p in purchases
    ]
    schwab_bytes = pd.DataFrame(schwab_data).to_csv(index=False).encode("utf-8")

    with dl_col1:
        st.download_button(
            "📥 Download CSV",
            data=csv_bytes,
            file_name="direct_index_initial_portfolio.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with dl_col2:
        st.download_button(
            "📥 Schwab Orders CSV",
            data=schwab_bytes,
            file_name="schwab_orders.csv",
            mime="text/csv",
            use_container_width=True,
            help="Import-ready CSV for Schwab order entry",
        )

    with dl_col3:
        md_lines = [
            "# Initial Direct Index Portfolio",
            f"Total stocks: {summary.total_stocks}",
            f"Total investment: ${summary.actual_investment:,.2f}",
            f"Unallocated: ${summary.unallocated_cash:,.2f}",
            "",
            "| Symbol | Name | Sector | Shares | Price | Amount |",
            "|--------|------|--------|--------|-------|--------|",
        ]
        for p in purchases:
            md_lines.append(
                f"| {p.symbol} | {p.name[:25]} | {p.sector} | {p.shares_to_buy} | "
                f"${p.current_price:.2f} | ${p.actual_amount:,.0f} |"
            )
        md_bytes = "\n".join(md_lines).encode("utf-8")
        st.download_button(
            "📥 Markdown Report",
            data=md_bytes,
            file_name="direct_index_portfolio.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.divider()

    nav_col1, nav_col2 = st.columns([1, 4])
    with nav_col1:
        if st.button("← Back"):
            _go(2)
            st.rerun()
    with nav_col2:
        if st.button("Complete Setup →", type="primary"):
            _go(4)
            st.rerun()


def _step4_instructions() -> None:
    """Step 4: execution instructions."""
    s = _state()

    st.subheader("Step 4 — Execute Trades in Schwab")
    st.success("✅ Your initial portfolio has been generated!")

    st.markdown("""
**Next steps to go live:**

1. **Download** the Schwab Orders CSV from Step 3 if you haven't already.
2. **Log in** to your Schwab account and navigate to *Trade → Order Entry*.
3. **Execute all buy orders** — use Market orders during regular market hours.
4. **Return here** once all trades have settled (T+1) and use the 
   **Import Positions** section on the Portfolio tab to load your confirmed positions.

**Important reminders:**
- Execute all trades on the **same day** to minimise tracking error.
- Keep all **trade confirmations** for cost-basis and tax records.
- Do not buy any **excluded symbols** for 30 days if you sold them recently.
""")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Back to Review"):
            _go(3)
            st.rerun()
    with c2:
        if st.button("🏁 Done — go to Dashboard", type="primary"):
            # Mark setup complete and hand off to main dashboard
            st.session_state["di_setup_complete"] = True
            st.rerun()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_setup_wizard() -> None:
    """
    Render the complete multi-step setup wizard.

    Call this from the Setup tab inside the Direct Indexing page.
    Returns immediately (no return value); all state lives in
    ``st.session_state["di_wizard"]``.
    """
    s = _state()
    step = s["step"]

    _render_step_indicator(step)

    if step == 1:
        _step1_amount()
    elif step == 2:
        _step2_configure()
    elif step == 3:
        _step3_review()
    elif step == 4:
        _step4_instructions()
    else:
        st.error(f"Unknown wizard step: {step}")
        _go(1)
        st.rerun()
