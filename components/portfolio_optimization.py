"""
components/portfolio_optimization.py
====================================
Portfolio Optimization Component - Rebalancing, tax harvesting, and charitable giving optimization.

Features:
- Portfolio rebalancing with drift detection
- Tax-loss harvesting opportunities
- Tax-gain harvesting at 0% LTCG rate
- DAF (Donor Advised Fund) bundling analysis
- Withdrawal planning guidance
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
    classify_harvest_opportunities,
    compute_harvest_summary,
    compute_net_tax_impact,
    get_ltcg_rate_for_income,
    get_ltcg_zero_threshold,
    get_replacement_detail,
    analyze_daf_bundling,
    identify_daf_candidates,
)


def render_optimization_tab(
    portdf: DataFrame,
    networth: DataFrame,
    curr_month: int,
    curr_year: int,
) -> None:
    """
    Render the Optimization tab with rebalancing, tax harvesting, and DAF bundling.
    
    Args:
        portdf: Current portfolio display DataFrame
        networth: Net worth history DataFrame
        curr_month: Current month (1-12)
        curr_year: Current year
    """
    st.markdown("### ⚖️ Portfolio Optimization")
    st.caption("Rebalancing, tax harvesting, and charitable giving optimization")
    
    # Create expandable sections for each optimization strategy
    rebalance_expander = st.expander("⚖️ Portfolio Rebalancing", expanded=True)
    harvest_expander = st.expander("🌾 Tax Loss/Gain Harvesting", expanded=False)
    daf_expander = st.expander("🏦 DAF Bundling Analysis", expanded=False)
    withdrawal_expander = st.expander("💰 Withdrawal Planning", expanded=False)
    
    # ========================================================================
    # REBALANCING SECTION
    # ========================================================================
    with rebalance_expander:
        st.markdown("#### ⚖️ Portfolio Rebalancing")
        st.caption(
            "Calculates your current Cash / Bonds / Stocks allocation and flags drift from targets. "
            "Rebalancing suggestions prioritize tax-advantaged accounts first."
        )
        
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
                    
                    # Cumulative targets
                    _default_cash = round(cash_from_b1)
                    _default_bonds = round(bonds_from_b2)
                    _default_stocks = round(stocks_from_b2 + stocks_from_b3)
                    
                    # Ensure they sum to 100
                    total = _default_cash + _default_bonds + _default_stocks
                    if total != 100:
                        _default_stocks = 100 - _default_cash - _default_bonds
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
        
        # Display total with color coding
        if is_valid:
            st.success(f"✅ Target allocation totals: **{total_pct}%** (Ready to calculate)")
        else:
            st.warning(f"⚠️ Target allocation totals: **{total_pct}%** (Must equal 100% to calculate rebalancing)")
        
        # Only show the calculate button when targets are valid
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
                
                # Display drift status
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
                
                # Asset class allocation metrics
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
                
                # Rebalancing action plan
                st.markdown("#### 🔄 Rebalancing Action Plan")
                act_df = build_actions_display_df(report)
                
                if act_df.empty:
                    st.info("No specific actions generated.")
                else:
                    for _, act in act_df.iterrows():
                        action_str = str(act["Action"])
                        is_sell = "Sell" in action_str
                        is_buy = "Buy" in action_str
                        
                        # Color coding based on action type
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
    
    # ========================================================================
    # TAX HARVESTING SECTION
    # ========================================================================
    with harvest_expander:
        st.markdown("#### 🌾 Tax Loss & Gain Harvesting")
        st.caption(
            "Analyzes your **Brokerage (taxable) account** holdings to identify opportunities to "
            "harvest losses (offset gains or up to $3,000 of ordinary income) and harvest gains "
            "at the **0% LTCG rate**. Wash-sale-safe replacement securities are suggested."
        )
        st.info(
            "💡 **This section** identifies *which* positions to harvest today. "
            "To model how harvested losses carry forward, go to "
            "**🎯 Advanced Strategies → 🌾 Capital Loss Harvesting**.",
            icon=None,
        )
        
        st.markdown("#### ⚙️ Analysis Parameters")
        h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns(5)
        
        with h_col1:
            h_agi = st.number_input(
                "Estimated AGI ($)",
                min_value=0,
                max_value=2_000_000,
                value=80_000,
                step=1_000,
                key="harvest_agi"
            )
        
        with h_col2:
            h_marginal = st.number_input(
                "Marginal Tax Rate (%)",
                min_value=0,
                max_value=50,
                value=22,
                step=1,
                key="harvest_marginal"
            )
        
        with h_col3:
            h_loss_thresh = st.number_input(
                "Loss Threshold ($)",
                min_value=0,
                max_value=100_000,
                value=500,
                step=100,
                key="harvest_loss_thresh"
            )
        
        with h_col4:
            h_drop_pct = st.number_input(
                "Market Drop Trigger (%)",
                min_value=1,
                max_value=50,
                value=10,
                step=1,
                key="harvest_drop_pct"
            )
        
        with h_col5:
            h_gain_thresh = st.number_input(
                "Gain Threshold ($)",
                min_value=0,
                max_value=100_000,
                value=500,
                step=100,
                key="harvest_gain_thresh"
            )
        
        st.markdown("---")
        
        # Calculate LTCG rates and thresholds
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
            h_strategy_label = (
                "🟢 Harvest Gains (0% rate!)" if h_ltcg_rate == 0.0
                else ("🟡 Harvest Losses" if h_ltcg_rate == 0.15 else "🔴 Harvest Losses (High Rate)")
            )
            st.metric("Recommended Strategy", h_strategy_label)
        
        st.markdown("---")
        
        # Analyze holdings
        try:
            with st.spinner("Fetching current prices and analyzing brokerage holdings..."):
                h_analysis = build_harvesting_analysis(curr_month, curr_year)
            
            if h_analysis.empty:
                st.info("ℹ️ No taxable (Brokerage) holdings found for the current period.")
            else:
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
                
                # Portfolio gain/loss summary
                st.markdown("#### 📊 Portfolio Gain/Loss Summary (Brokerage Only)")
                sm_c1, sm_c2, sm_c3, sm_c4, sm_c5 = st.columns(5)
                
                with sm_c1:
                    st.metric("Total Unrealized Gains", f"${h_summary['total_unrealized_gain']:,.0f}")
                
                with sm_c2:
                    loss_val = h_summary['total_unrealized_loss']
                    st.metric(
                        "Total Unrealized Losses",
                        f"${abs(loss_val):,.0f}",
                        delta=f"-${abs(loss_val):,.0f}" if loss_val < 0 else None,
                        delta_color="inverse"
                    )
                
                with sm_c3:
                    net = h_summary['net_unrealized']
                    st.metric(
                        "Net Unrealized",
                        f"${net:,.0f}",
                        delta=f"{'▲' if net >= 0 else '▼'} ${abs(net):,.0f}",
                        delta_color="normal" if net >= 0 else "inverse"
                    )
                
                with sm_c4:
                    st.metric("Harvestable Losses", f"${abs(h_summary['harvestable_losses']):,.0f}")
                
                with sm_c5:
                    st.metric("Harvestable Gains (0%)", f"${h_summary.get('harvestable_gains_at_zero', 0.0):,.0f}")
                
                # Tax impact summary
                st.markdown("#### 💰 Estimated Tax Impact")
                ti_c1, ti_c2, ti_c3 = st.columns(3)
                
                with ti_c1:
                    tax_savings = h_tax_impact.ordinary_income_savings
                    st.metric(
                        "Tax Savings from Losses",
                        f"${tax_savings:,.0f}",
                        help="Estimated tax savings from harvesting losses"
                    )
                
                with ti_c2:
                    tax_cost = h_tax_impact.tax_on_net_gains
                    st.metric(
                        "Tax Cost from Gains",
                        f"${tax_cost:,.0f}",
                        help="Tax cost if harvesting gains"
                    )
                
                with ti_c3:
                    net_benefit = h_tax_impact.net_tax_impact
                    st.metric(
                        "Net Tax Impact",
                        f"${net_benefit:,.0f}",
                        delta=f"{'▲' if net_benefit >= 0 else '▼'} ${abs(net_benefit):,.0f}",
                        delta_color="normal" if net_benefit >= 0 else "inverse",
                        help="Net tax impact from all harvesting opportunities"
                    )
                
                st.markdown("---")
                
                # Market drop trigger analysis
                from tax_harvesting import check_market_drop_trigger
                h_drop_result = check_market_drop_trigger(h_analysis, drop_threshold_pct=float(h_drop_pct))
                if h_drop_result["triggered"]:
                    st.warning(h_drop_result["message"])
                else:
                    st.success(f"✅ {h_drop_result['message']}")
                
                st.markdown("---")
                
                # Detailed harvesting recommendations table
                st.markdown("#### 🎯 Harvesting Recommendations")
                
                display_cols = [
                    "Account", "Symbol", "Name", "Sector",
                    "Qty", "Purchase Price", "Current Price",
                    "Current Value", "Cost Basis", "Unrealized G/L",
                    "Return %", "Days Held", "Gain Type", "Recommendation",
                ]
                
                h_display = cast(pd.DataFrame, h_classified[display_cols].copy())
                
                # Format currency and percentage columns
                h_display["Purchase Price"] = cast(pd.Series, h_display["Purchase Price"]).map(lambda x: f"${x:,.2f}")
                h_display["Current Price"] = cast(pd.Series, h_display["Current Price"]).map(lambda x: f"${x:,.2f}")
                h_display["Current Value"] = cast(pd.Series, h_display["Current Value"]).map(lambda x: f"${x:,.0f}")
                h_display["Cost Basis"] = cast(pd.Series, h_display["Cost Basis"]).map(lambda x: f"${x:,.0f}")
                h_display["Unrealized G/L"] = cast(pd.Series, h_display["Unrealized G/L"]).map(lambda x: f"${x:,.0f}")
                h_display["Return %"] = cast(pd.Series, h_display["Return %"]).map(lambda x: f"{x:.1f}%")
                h_display["Qty"] = cast(pd.Series, h_display["Qty"]).map(lambda x: f"{x:,.0f}")
                
                st.dataframe(
                    h_display,
                    hide_index=True,
                    height=(len(h_display) + 1) * 38 + 3,
                    use_container_width=True
                )
                
                # Replacement suggestions for harvest opportunities
                st.markdown("---")
                st.markdown("#### 🔄 Wash-Sale-Safe Replacement Suggestions")
                
                harvest_opps = h_classified[h_classified["Recommendation"].str.contains("Harvest", na=False)]
                
                if not harvest_opps.empty:
                    for _, opp in harvest_opps.iterrows():
                        symbol = str(opp["Symbol"])
                        recommendation = str(opp["Recommendation"])
                        
                        # Get replacement suggestions
                        replacement_info = get_replacement_detail(symbol)
                        
                        with st.expander(f"🔄 {symbol} — {recommendation}", expanded=False):
                            st.markdown(f"**Current Position:**")
                            st.markdown(f"- Symbol: {symbol}")
                            st.markdown(f"- Unrealized G/L: ${opp['Unrealized G/L']}")
                            st.markdown(f"- Return: {opp['Return %']}")
                            
                            if replacement_info:
                                st.markdown(f"\n**Suggested Replacements:**")
                                st.markdown(replacement_info)
                            else:
                                st.info("No specific replacement suggestions available. Consider similar ETFs or index funds in the same sector.")
                else:
                    st.info("No harvest opportunities identified with current thresholds.")
        
        except Exception as e:
            st.error(f"⚠️ Error analyzing tax harvesting opportunities: {e}")
    
    # ========================================================================
    # DAF BUNDLING SECTION
    # ========================================================================
    with daf_expander:
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
            # Analyze DAF bundling opportunities
            with st.spinner("Analyzing DAF bundling opportunities..."):
                h_analysis_daf = build_harvesting_analysis(curr_month, curr_year)
                daf_candidates_list = identify_daf_candidates(
                    h_analysis_daf,
                    ltcg_rate=get_ltcg_rate_for_income(float(daf_agi), curr_year)
                )
                
                # Get required parameters for bundling analysis
                from load_data import get_std_deduction
                from config import get_config_manager
                
                config_mgr = get_config_manager()
                filing_status = config_mgr.get_filing_status()
                daf_std_ded_df = get_std_deduction(curr_year, filing_status)
                
                # Extract standard deduction for the current filing status
                try:
                    daf_std_ded = float(daf_std_ded_df.iloc[0]['deduction'])
                except (KeyError, IndexError, AttributeError):
                    daf_std_ded = 32200.0  # Default 2026 married filing jointly
                
                daf_ltcg = get_ltcg_rate_for_income(float(daf_agi), curr_year)
                
                daf_analysis = analyze_daf_bundling(
                    estimated_agi=float(daf_agi),
                    annual_giving=float(daf_annual_giving),
                    years_to_bundle=int(daf_bundle_years),
                    marginal_rate=0.22,  # Default marginal rate
                    standard_deduction=daf_std_ded,
                    ltcg_rate=daf_ltcg,
                    securities_candidates=daf_candidates_list,
                    year=curr_year,
                )
            
            # Display results
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
                
                # Display recommendation
                if daf_analysis.recommendation:
                    if "Strong" in daf_analysis.recommendation:
                        st.success(f"✅ {daf_analysis.recommendation}")
                    elif "Moderate" in daf_analysis.recommendation:
                        st.info(f"💡 {daf_analysis.recommendation}")
                    else:
                        st.warning(f"⚠️ {daf_analysis.recommendation}")
            
            st.markdown("---")
            
            # Display appreciated securities candidates
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
                st.dataframe(
                    pd.DataFrame(daf_cand_rows),
                    hide_index=True,
                    use_container_width=True
                )
                
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
    
    # ========================================================================
    # WITHDRAWAL PLANNING SECTION
    # ========================================================================
    with withdrawal_expander:
        st.markdown("#### 💰 Withdrawal Planning")
        st.caption("Plan tax-efficient withdrawals from your portfolio")
        
        st.info(
            "💡 For comprehensive withdrawal strategy planning, visit the "
            "**🎯 Strategy** page where you can model multi-year withdrawal scenarios."
        )
        
        # Quick calculator
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
            withdrawal_purpose = st.selectbox(
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
