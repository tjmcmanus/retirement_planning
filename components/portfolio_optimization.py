"""
components/portfolio_optimization.py
====================================
Portfolio Optimization Component - Rebalancing, DAF bundling and withdrawal planning.

Exports:
- render_rebalancing_tab()  — top-level Portfolio Hub Rebalancing tab
- render_daf_tab()          — called from the Analytics tab
- render_withdrawals_tab()  — called from the Analytics tab

Note: Tax Harvesting is now rendered via components/portfolio_harvest_tab.py.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pandas as pd
import streamlit as st

if TYPE_CHECKING:
    from pandas import DataFrame

from portfolio_rebalancing import (
    compute_rebalance_plan,
    build_rebalance_display_df,
    build_actions_display_df,
)
from tax_harvesting import (
    build_harvesting_analysis,
    get_ltcg_rate_for_income,
    analyze_daf_bundling,
    identify_daf_candidates,
)


# ==============================================================================
# PUBLIC ENTRY POINTS
# ==============================================================================

def render_rebalancing_tab(
    portdf: DataFrame,
    networth: DataFrame,
    curr_month: int,
    curr_year: int,
) -> None:
    """
    Render the Rebalancing tab (top-level Portfolio Hub tab).

    Args:
        portdf: Current portfolio display DataFrame
        networth: Net worth history DataFrame
        curr_month: Current month (1-12)
        curr_year: Current year
    """
    st.markdown("### ⚖️ Portfolio Rebalancing")
    st.caption(
        "Calculates your current Cash / Bonds / Stocks allocation and flags drift from targets. "
        "Rebalancing suggestions prioritize tax-advantaged accounts first."
    )
    _render_rebalancing_body(portdf, networth, curr_month, curr_year)


def render_daf_tab(
    portdf: DataFrame,
    networth: DataFrame,
    curr_month: int,
    curr_year: int,
) -> None:
    """Render the DAF Bundling section (called from the Analytics tab)."""
    _render_daf_body(curr_month, curr_year)


def render_withdrawals_tab(
    portdf: DataFrame,
    networth: DataFrame,
    curr_month: int,
    curr_year: int,
) -> None:
    """Render the Withdrawal Planning section (called from the Analytics tab)."""
    _render_withdrawal_body()


# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

def _render_rebalancing_body(
    portdf: DataFrame,
    networth: DataFrame,
    curr_month: int,
    curr_year: int,
) -> None:
    """Core rebalancing UI."""
    # Try to get bucket strategy cumulative target mix as defaults
    _default_cash = 10
    _default_bonds = 10
    _default_stocks = 80

    try:
        from config import get_config_manager
        from bucket_strategy import load_bucket_config

        cfg = get_config_manager()
        bucket_enabled = cfg.get("bucket_strategy", "enabled", False)

        if bucket_enabled:
            bucket_config = load_bucket_config(cfg)

            # Calculate cumulative target mix based on bucket strategy
            total_value = float(networth["total"].iloc[-1]) if not networth.empty else 0.0

            if total_value > 0:
                annual_need = bucket_config.annual_expenses + bucket_config.annual_taxes
                bucket_1_target = annual_need * bucket_config.bucket_1_years
                bucket_2_target = annual_need * bucket_config.bucket_2_years
                bucket_3_target = max(0, total_value - bucket_1_target - bucket_2_target)

                # Calculate weighted percentages
                bucket_1_weight = bucket_1_target / total_value
                bucket_2_weight = bucket_2_target / total_value
                bucket_3_weight = bucket_3_target / total_value

                # Bucket 1: 100% cash
                cash_from_b1 = 100 * bucket_1_weight

                # Bucket 2: graduated allocation (average)
                avg_stocks_b2 = (bucket_config.bucket_2_start_stock_pct + bucket_config.bucket_2_end_stock_pct) / 2
                avg_bonds_b2 = 100 - avg_stocks_b2
                stocks_from_b2 = avg_stocks_b2 * bucket_2_weight
                bonds_from_b2 = avg_bonds_b2 * bucket_2_weight

                # Bucket 3: 100% stocks
                stocks_from_b3 = 100 * bucket_3_weight

                # Cumulative targets — clamp each to [0, 100] individually
                # before the sum-to-100 correction so no single value can
                # exceed the widget's max_value.
                _default_cash   = max(0, min(100, round(cash_from_b1)))
                _default_bonds  = max(0, min(100, round(bonds_from_b2)))
                _default_stocks = max(0, min(100, round(stocks_from_b2 + stocks_from_b3)))

                # Ensure they sum to 100 by adjusting stocks (largest bucket)
                total = _default_cash + _default_bonds + _default_stocks
                if total != 100:
                    _default_stocks = max(0, 100 - _default_cash - _default_bonds)
    except Exception:
        # If bucket strategy not available or any error, use hardcoded defaults
        pass

    st.markdown("#### 🎯 Target Allocation & Drift Threshold")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        cash_tgt = st.number_input(
            "Target Cash %",
            min_value=0,
            max_value=100,
            value=_default_cash,
            step=1,
            key="rb_cash_tgt"
        )

    with col2:
        bonds_tgt = st.number_input(
            "Target Bonds %",
            min_value=0,
            max_value=100,
            value=_default_bonds,
            step=1,
            key="rb_bonds_tgt"
        )

    with col3:
        stocks_tgt = st.number_input(
            "Target Stocks %",
            min_value=0,
            max_value=100,
            value=_default_stocks,
            step=1,
            key="rb_stocks_tgt"
        )

    with col4:
        drift_thresh = st.number_input(
            "Drift Threshold %",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            key="rb_drift"
        )

    # Show current total and validation status
    total_pct = cash_tgt + bonds_tgt + stocks_tgt
    is_valid = total_pct == 100

    if is_valid:
        st.success(f"✅ Target allocation totals: **{total_pct}%** (Ready to calculate)")
    else:
        st.warning(f"⚠️ Target allocation totals: **{total_pct}%** (Must equal 100% to calculate rebalancing)")

    # Show cache status and save button
    st.markdown("#### 💾 Save Target Allocation")

    try:
        from components.rebalancing_cache import get_cache_manager, get_target_allocation

        cache_mgr = get_cache_manager()
        saved_target = get_target_allocation()

        col_save1, col_save2 = st.columns([3, 1])

        with col_save1:
            if saved_target:
                st.info(
                    f"📌 **Saved Target:** {saved_target['cash_pct']:.0f}% cash, "
                    f"{saved_target['bonds_pct']:.0f}% bonds, {saved_target['stocks_pct']:.0f}% stocks "
                    f"(Threshold: {saved_target['drift_threshold_pct']:.0f}%)\n\n"
                    f"Last updated: {saved_target['last_updated'][:10]}"
                )
            else:
                st.info("💡 No saved target allocation. Save your targets to use in reports.")

        with col_save2:
            save_btn = st.button(
                "💾 Save Targets",
                disabled=not is_valid,
                use_container_width=True,
                key="rb_save_targets_btn",
                help="Save these targets for use in Portfolio Review reports"
            )

            if save_btn and is_valid:
                try:
                    from components.rebalancing_cache import set_target_allocation

                    success = set_target_allocation(
                        cash_pct=float(cash_tgt),
                        bonds_pct=float(bonds_tgt),
                        stocks_pct=float(stocks_tgt),
                        drift_threshold_pct=float(drift_thresh)
                    )

                    if success:
                        st.success("✅ Target allocation saved! Will be used in Portfolio Review reports.")
                        st.rerun()
                    else:
                        st.error("❌ Failed to save target allocation")
                except Exception as e:
                    st.error(f"❌ Error saving targets: {e}")

        # Show cache status
        latest_analysis = cache_mgr.get_latest_analysis()
        if latest_analysis:
            needs_update = cache_mgr.needs_update()
            status_icon = "⚠️" if needs_update else "✅"
            status_text = "Stale (will update)" if needs_update else "Fresh"
            st.caption(
                f"{status_icon} **Cache Status:** {status_text} | "
                f"Last analysis: {latest_analysis['calculation_date']} | "
                f"Total value: ${latest_analysis['total_value']:,.0f}"
            )
        else:
            st.caption("ℹ️ No cached analysis yet. Will be created when you calculate or save targets.")

    except Exception as e:
        st.warning(f"⚠️ Cache system unavailable: {e}")

    st.markdown("---")

    calculate_btn = st.button(
        "🔄 Calculate Rebalancing Plan",
        disabled=not is_valid,
        type="primary" if is_valid else "secondary",
        use_container_width=True,
        key="rb_calculate_btn"
    )

    if calculate_btn and is_valid:
        st.markdown("---")
        try:
            with st.spinner("Computing rebalancing plan..."):
                report = compute_rebalance_plan(
                    month=curr_month,
                    year=curr_year,
                    target_cash_pct=float(cash_tgt),
                    target_bonds_pct=float(bonds_tgt),
                    target_stocks_pct=float(stocks_tgt),
                    drift_threshold_pct=float(drift_thresh),
                )

            if report.drift_triggered:
                st.warning(
                    f"🔴 **Rebalancing Required** — one or more asset classes have drifted "
                    f"more than {report.drift_threshold_pct:.0f}% from their targets."
                )
            else:
                st.success(
                    f"✅ **Portfolio is balanced** — all asset classes are within "
                    f"{report.drift_threshold_pct:.0f}% of their targets."
                )

            st.markdown(f"#### 📊 Asset Class Allocation (Total: ${report.total_portfolio_value:,.0f})")
            sum_df = build_rebalance_display_df(report)

            mc1, mc2, mc3 = st.columns(3)
            for mc, ac in zip([mc1, mc2, mc3], ["Cash", "Bonds", "Stocks"]):
                row = sum_df[sum_df["Asset Class"] == ac]
                if not row.empty:
                    r = row.iloc[0]
                    with mc:
                        drift_val = float(r["Drift %"])
                        st.metric(
                            label=ac,
                            value=f"{r['Current %']:.1f}% (${r['Current Value']:,.0f})",
                            delta=f"{drift_val:+.1f}% vs {r['Target %']:.0f}% target",
                            delta_color="normal" if abs(drift_val) < drift_thresh else "inverse",
                        )

            st.markdown("#### 🔄 Rebalancing Action Plan")
            act_df = build_actions_display_df(report)

            if act_df.empty:
                st.info("No specific actions generated.")
            else:
                for _, act in act_df.iterrows():
                    action_str = str(act["Action"])
                    is_sell = "Sell" in action_str
                    is_buy = "Buy" in action_str

                    if is_sell and "Brokerage" in action_str:
                        bg, border = "#fff8f0", "#f58518"
                    elif is_sell:
                        bg, border = "#f0f8ff", "#4c78a8"
                    elif is_buy:
                        bg, border = "#f0fff4", "#21c354"
                    else:
                        bg, border = "#f8f9fa", "#6c757d"

                    st.markdown(
                        f'<div style="border-left:4px solid {border};background:{bg};'
                        f'padding:12px 16px;border-radius:6px;margin-bottom:10px;">'
                        f'<div style="font-size:14px;font-weight:700;">#{int(act["Priority"])} — {action_str} '
                        f'<span style="color:#555;font-weight:400;">[{act["Asset Class"]}]</span> '
                        f'<span style="font-size:13px;color:#1a73e8;">{act["Symbol"]}</span></div>'
                        f'<div style="font-size:12px;margin-top:4px;">Account: <b>{act["Account"]}</b> | '
                        f'Amount: <b>${float(act["Amount"]):,.0f}</b> | Tax: <b>{act["Tax Impact"]}</b></div>'
                        f'<div style="font-size:12px;color:#444;margin-top:6px;">{act["Rationale"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        except Exception as e:
            st.error(f"⚠️ Error computing rebalancing plan: {e}")


def _render_daf_body(curr_month: int, curr_year: int) -> None:
    """Core DAF bundling UI."""
    st.markdown("#### 🏦 Donor Advised Fund (DAF) Bundling")
    st.caption(
        "Identifies long-term appreciated securities in your brokerage account that are ideal "
        "for donating to a Donor Advised Fund — avoiding capital gains tax while maximizing "
        "your charitable deduction."
    )

    st.markdown("#### ⚙️ DAF Analysis Parameters")
    daf_col1, daf_col2, daf_col3 = st.columns(3)

    with daf_col1:
        daf_agi = st.number_input(
            "Estimated AGI ($)",
            min_value=0,
            max_value=5_000_000,
            value=150_000,
            step=5_000,
            key="daf_agi"
        )

    with daf_col2:
        daf_annual_giving = st.number_input(
            "Annual Charitable Giving ($)",
            min_value=0,
            max_value=500_000,
            value=5_000,
            step=500,
            key="daf_annual_giving"
        )

    with daf_col3:
        daf_bundle_years = st.number_input(
            "Bundle Years",
            min_value=2,
            max_value=10,
            value=3,
            step=1,
            key="daf_bundle_years"
        )

    st.markdown("---")

    try:
        with st.spinner("Analyzing DAF bundling opportunities..."):
            h_analysis_daf = build_harvesting_analysis(curr_month, curr_year)
            daf_candidates_list = identify_daf_candidates(
                h_analysis_daf,
                ltcg_rate=get_ltcg_rate_for_income(float(daf_agi), curr_year)
            )

            from load_data import get_std_deduction
            from config import get_config_manager

            config_mgr = get_config_manager()
            filing_status = config_mgr.get_filing_status()
            daf_std_ded_df = get_std_deduction(curr_year, filing_status)

            try:
                daf_std_ded = float(daf_std_ded_df.iloc[0]['deduction'])
            except (KeyError, IndexError, AttributeError):
                daf_std_ded = 32200.0  # Default 2026 married filing jointly

            daf_ltcg = get_ltcg_rate_for_income(float(daf_agi), curr_year)

            daf_analysis = analyze_daf_bundling(
                estimated_agi=float(daf_agi),
                annual_giving=float(daf_annual_giving),
                years_to_bundle=int(daf_bundle_years),
                marginal_rate=0.22,
                standard_deduction=daf_std_ded,
                ltcg_rate=daf_ltcg,
                securities_candidates=daf_candidates_list,
                year=curr_year,
            )

        if daf_analysis:
            st.markdown("#### 📊 DAF Bundling Analysis Results")
            daf_c1, daf_c2, daf_c3, daf_c4 = st.columns(4)

            with daf_c1:
                st.metric("Bundled Contribution", f"${daf_analysis.bundled_contribution:,.0f}")
            with daf_c2:
                st.metric("Standard Deduction", f"${daf_analysis.standard_deduction:,.0f}")
            with daf_c3:
                st.metric("Deductible Amount", f"${daf_analysis.deductible_amount:,.0f}")
            with daf_c4:
                daf_net = daf_analysis.tax_savings_vs_standard
                st.metric(
                    "Tax Savings",
                    f"${abs(daf_net):,.0f}",
                    delta=f"{'Save' if daf_net >= 0 else 'Owe'} ${abs(daf_net):,.0f}",
                    delta_color="normal" if daf_net >= 0 else "inverse"
                )

            if daf_analysis.recommendation:
                if "Strong" in daf_analysis.recommendation:
                    st.success(f"✅ {daf_analysis.recommendation}")
                elif "Moderate" in daf_analysis.recommendation:
                    st.info(f"💡 {daf_analysis.recommendation}")
                else:
                    st.warning(f"⚠️ {daf_analysis.recommendation}")

        st.markdown("---")
        st.markdown("#### 🎯 Appreciated Securities — DAF Donation Candidates")

        if daf_candidates_list:
            daf_cand_rows = [
                {
                    "Account": c.account,
                    "Symbol": c.symbol,
                    "Name": c.name,
                    "Qty": f"{c.qty:,.2f}",
                    "Cost Basis": f"${c.cost_basis:,.0f}",
                    "Current Value": f"${c.current_value:,.0f}",
                    "Unrealized Gain": f"${c.unrealized_gain:,.0f}",
                    "Gain %": f"{c.gain_pct:.1f}%",
                    "Days Held": c.days_held,
                    "Gain Type": c.gain_type,
                    "CG Tax Avoided": f"${c.avoided_cg_tax:,.0f}",
                }
                for c in daf_candidates_list
            ]
            st.dataframe(pd.DataFrame(daf_cand_rows), hide_index=True, use_container_width=True)

            st.markdown("---")
            st.markdown("#### 💡 DAF Bundling Strategy")
            st.markdown(f"""
            **How DAF Bundling Works:**

            1. **Bundle {daf_bundle_years} years** of charitable giving (${daf_annual_giving * daf_bundle_years:,.0f}) into one year
            2. **Donate appreciated securities** to avoid capital gains tax
            3. **Exceed standard deduction** (${daf_std_ded:,.0f}) to itemize and maximize tax benefit
            4. **Distribute from DAF** over the next {daf_bundle_years} years to your favorite charities

            **Benefits:**
            - Avoid capital gains tax on appreciated securities
            - Maximize charitable deduction by exceeding standard deduction threshold
            - Maintain annual giving schedule through DAF distributions
            - Simplify tax planning by bunching deductions

            **Next Steps:**
            1. Open a DAF account (Fidelity Charitable, Schwab Charitable, Vanguard Charitable)
            2. Transfer appreciated securities from your brokerage account
            3. Take the charitable deduction in the year of contribution
            4. Recommend grants to charities over time
            """)
        else:
            st.info("ℹ️ No long-term appreciated securities found in your brokerage account.")
            st.markdown("""
            **To use DAF bundling, you need:**
            - Long-term holdings (>1 year) in your brokerage account
            - Appreciated securities with unrealized gains
            - Regular charitable giving that could benefit from bundling
            """)

    except Exception as e:
        st.error(f"⚠️ Error running DAF analysis: {e}")
        st.info("💡 Ensure you have brokerage holdings with long-term gains to analyze DAF opportunities.")


def _render_withdrawal_body() -> None:
    """Core withdrawal planning UI."""
    st.markdown("#### 💰 Withdrawal Planning")
    st.caption("Plan tax-efficient withdrawals from your portfolio")

    st.info(
        "💡 For comprehensive withdrawal strategy planning, visit the "
        "**🎯 Strategy** page where you can model multi-year withdrawal scenarios."
    )

    st.markdown("##### Quick Withdrawal Calculator")
    col1, col2 = st.columns(2)
    with col1:
        withdrawal_amount = st.number_input(
            "Withdrawal Amount ($)",
            min_value=0,
            max_value=1_000_000,
            value=50_000,
            step=1_000,
            key="withdrawal_amount"
        )
    with col2:
        st.selectbox(
            "Purpose",
            options=["Living Expenses", "Large Purchase", "Emergency", "Other"],
            key="withdrawal_purpose"
        )

    if st.button("💡 Get Withdrawal Recommendations", use_container_width=True, key="withdrawal_recs"):
        st.markdown("##### 📋 Recommended Withdrawal Sequence")
        st.markdown(f"""
        **Tax-Efficient Withdrawal Order for ${withdrawal_amount:,.0f}:**

        1. **Taxable Brokerage** (first)
           - Lowest tax impact
           - Harvest losses to offset gains
           - Long-term capital gains taxed at preferential rates

        2. **Traditional IRA/401(k)** (second)
           - Ordinary income tax rates
           - Consider Roth conversions in low-income years
           - Watch for RMD requirements at age 73

        3. **Roth IRA** (last)
           - Tax-free withdrawals
           - No RMDs during lifetime
           - Preserve for later years or heirs

        **Specific Recommendation:**
        - Take ${min(withdrawal_amount, 30000):,.0f} from Brokerage (harvest losses if available)
        - If needed, take ${max(0, withdrawal_amount - 30000):,.0f} from Traditional accounts
        - Preserve Roth for future tax-free growth
        """)

        st.info(
            "💡 Visit the **🎯 Strategy** page to model this withdrawal "
            "in your multi-year retirement plan and see the long-term tax impact."
        )

# Made with Bob
