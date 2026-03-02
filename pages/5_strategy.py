"""
pages/5_strategy.py
===================
📈 Strategy — Accumulation and Withdrawal planning across all life stages.

Sub-tabs (st.tabs within the page):
  - 📋 Annual Plan       (year-by-year strategy table)
  - 💰 Account Balances  (projected balances table)
  - 📊 Visualizations    (stacked area + income bar charts)
"""
from __future__ import annotations

from typing import cast

import pandas as pd
import streamlit as st
from streamlit_extras.add_vertical_space import add_vertical_space

from components.navbar import navbar
from components.shared import (
    LIFE_STAGE_DESCRIPTIONS,
    BALANCE_COLUMN_CONFIG,
    auto_rerun_if_rebuilding,
    format_currency,
    init_page,
    render_balance_chart,
    render_balance_table,
    render_income_chart,
)
from load_data import get_networth_by_month
from strategy import build_accumulation_strategy_display, build_withdrawal_strategy_display

_STAGE_COLUMN_HELP = (
    "The life stage determines which financial priorities and rules apply this year. "
    "Hover over the stage name in the legend below the table for a plain-English summary."
)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
(
    networth,
    _portfolio_df,
    _portfolio_cache_ready,
    _stale_label,
    curr_month,
    curr_year,
    _eff_port_month,
    _eff_port_year,
) = init_page("📈 Strategy — Financial Planner", "📈")

navbar("📈 Strategy")

st.header("📈 Strategy")
st.markdown("Plan and review your accumulation and withdrawal strategy across all life stages.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Phase toggle
# ---------------------------------------------------------------------------
phase = st.radio(
    "Planning Phase",
    options=["📈 Accumulation (Pre-Retirement)", "💸 Withdrawal (Distribution)"],
    horizontal=True,
    label_visibility="collapsed",
)
st.markdown("---")

strategy_sub_tab, balances_sub_tab, charts_sub_tab = st.tabs(
    ["📋 Annual Plan", "💰 Account Balances", "📊 Visualizations"]
)

# ---------------------------------------------------------------------------
# ACCUMULATION PHASE
# ---------------------------------------------------------------------------
if phase == "📈 Accumulation (Pre-Retirement)":
    try:
        accum_rate_of_return_s = float(st.session_state.get("RATE", 6)) / 100
    except (ValueError, TypeError):
        accum_rate_of_return_s = 0.06

    try:
        from config import get_config_manager as _acfg_mgr
        _acfg = _acfg_mgr()
        accum_expense_inflation = _acfg.get("financial_assumptions", "expense_inflation_rate", 3.0) / 100.0
        accum_person1_name      = _acfg.get("personal_info", "person1_name", "Person1")
        accum_person2_name      = _acfg.get("personal_info", "person2_name", "Person2")
        accum_annual_expenses   = _acfg.get("financial_assumptions", "expected_annual_expenses", 120_000)
    except Exception:
        accum_expense_inflation = 0.03
        accum_person1_name      = "Person1"
        accum_person2_name      = "Person2"
        accum_annual_expenses   = 120_000

    ap_col1, ap_col2, ap_col3 = st.columns(3)
    with ap_col1:
        st.metric("Rate of Return", f"{accum_rate_of_return_s * 100:.1f}%")
    with ap_col2:
        st.metric("Expense Inflation", f"{accum_expense_inflation * 100:.1f}%")
    with ap_col3:
        st.metric("Annual Expenses", f"${accum_annual_expenses:,.0f}")

    add_vertical_space(1)

    try:
        with st.spinner("Calculating accumulation strategy..."):
            accum_strategy_df, accum_balances_df = build_accumulation_strategy_display(
                start_year=curr_year,
                growth_rate=1 + accum_rate_of_return_s,
                expense_inflation_rate=accum_expense_inflation,
                person1_name=accum_person1_name,
                person2_name=accum_person2_name,
            )

        with strategy_sub_tab:
            st.subheader("Annual Accumulation Plan")
            display_df_a = accum_strategy_df.copy()
            display_cols_a = [
                'Year', 'Age', 'Stage',
                'Wages', 'Wages→\nPayroll', 'Wages→\nTrad', 'Wages→\nRoth',
                'Trad→\nRoth', 'Cash→\nRoth', 'Cash→\nBrok',
                'Expenses', 'Healthcare Cost', 'AGI', 'Federal Tax', 'Cash Balance',
            ]
            available_cols_a = [c for c in display_cols_a if c in display_df_a.columns]
            display_df_a = cast(pd.DataFrame, display_df_a[available_cols_a].copy())
            numeric_cols_a = [c for c in available_cols_a if c not in ['Year', 'Age', 'Stage']]
            for col in numeric_cols_a:
                display_df_a[col] = display_df_a[col].map(format_currency)

            accum_column_config = {
                "Year":           st.column_config.NumberColumn("Year", format="%d"),
                "Age":            st.column_config.TextColumn("Age"),
                "Stage":          st.column_config.TextColumn("Life Stage", help=_STAGE_COLUMN_HELP),
                "Wages":          st.column_config.TextColumn("Wages"),
                "Wages→\nPayroll":st.column_config.TextColumn("Payroll Tax"),
                "Wages→\nTrad":   st.column_config.TextColumn("Wages→Trad"),
                "Wages→\nRoth":   st.column_config.TextColumn("Wages→Roth"),
                "Trad→\nRoth":    st.column_config.TextColumn("Trad→Roth"),
                "Cash→\nRoth":    st.column_config.TextColumn("Cash→Roth"),
                "Cash→\nBrok":    st.column_config.TextColumn("Cash→Brok"),
                "Expenses":       st.column_config.TextColumn("Expenses"),
                "Healthcare Cost":st.column_config.TextColumn("Healthcare"),
                "AGI":            st.column_config.TextColumn("AGI"),
                "Federal Tax":    st.column_config.TextColumn("Fed Tax"),
                "Cash Balance":   st.column_config.TextColumn("Cash End"),
            }
            st.dataframe(display_df_a, column_config=accum_column_config, hide_index=True, use_container_width=True)

            _accum_stages_present = display_df_a['Stage'].unique() if 'Stage' in display_df_a.columns else []
            with st.expander("ℹ️ Life Stage Guide", expanded=False):
                for _stage_name, _stage_desc in LIFE_STAGE_DESCRIPTIONS.items():
                    if _stage_name in list(_accum_stages_present):
                        st.markdown(f"**{_stage_name}**")
                        st.caption(_stage_desc)
                        st.markdown("---")

        with balances_sub_tab:
            st.subheader("Account Balances Over Time")
            render_balance_table(accum_balances_df)

        with charts_sub_tab:
            st.subheader("Portfolio Balance Projections")
            render_balance_chart(accum_balances_df, title="Projected Account Balances (Accumulation)")
            st.subheader("Income Sources Over Time")
            render_income_chart(accum_strategy_df, title="Income Sources by Year (Accumulation)")

    except Exception as e:
        st.error(f"Error calculating accumulation strategy: {e}")
        st.info("Please ensure all configuration parameters are properly set.")

# ---------------------------------------------------------------------------
# WITHDRAWAL / DISTRIBUTION PHASE
# ---------------------------------------------------------------------------
else:
    try:
        ssi_age_s          = int(st.session_state.get("SSI_AGE", 70))
        conv_tax_rate_s    = float(st.session_state.get("CONV_TAX_RATE", 12))
        annual_expenses_s  = float(st.session_state.get("EXPENSE", 50000))
        expense_multiplier_s = float(st.session_state.get("EXPENSE_MULTIPLIER", 4))
        rate_of_return_s   = float(st.session_state.get("RATE", 6)) / 100
    except (ValueError, TypeError):
        ssi_age_s = 70; conv_tax_rate_s = 12; annual_expenses_s = 50000
        expense_multiplier_s = 4; rate_of_return_s = 0.06

    param_col1, param_col2, param_col3 = st.columns(3)
    with param_col1:
        st.metric("Social Security Age", ssi_age_s)
        st.metric("Annual Expenses", f"${annual_expenses_s:,.0f}")
    with param_col2:
        st.metric("Max Roth Conv Rate", f"{conv_tax_rate_s}%")
        st.metric("Expense Multiplier", f"{expense_multiplier_s}x")
    with param_col3:
        st.metric("Rate of Return", f"{rate_of_return_s*100:.1f}%")

    add_vertical_space(1)

    try:
        max_conversion_rate = float(st.session_state.get("CONV_TAX_RATE", "24")) / 100.0
    except (ValueError, TypeError):
        max_conversion_rate = 0.24

    try:
        from config import get_config_manager as _cfg_mgr
        _cfg = _cfg_mgr()
        aca_marketplace_enrolled = _cfg.get("healthcare", "aca_marketplace_enrolled", False)
        expense_inflation_rate   = _cfg.get("financial_assumptions", "expense_inflation_rate", 3.0) / 100.0
        person1_name             = _cfg.get("personal_info", "person1_name", "Person1")
        person2_name             = _cfg.get("personal_info", "person2_name", "Person2")
    except Exception:
        aca_marketplace_enrolled = False; expense_inflation_rate = 0.03
        person1_name = "Person1"; person2_name = "Person2"

    try:
        with st.spinner("Calculating withdrawal strategy..."):
            strategy_df_w, balances_df_w = build_withdrawal_strategy_display(
                start_year=curr_year,
                end_year=2050,
                growth_rate=1 + rate_of_return_s,
                expense_inflation_rate=expense_inflation_rate,
                person1_name=person1_name,
                person2_name=person2_name,
                max_conversion_rate=max_conversion_rate,
                aca_optimize=aca_marketplace_enrolled,
                ss_claiming_age=ssi_age_s,
            )

        with strategy_sub_tab:
            st.subheader("Year-by-Year Withdrawal Strategy")
            display_df_w = strategy_df_w.copy()

            try:
                _, summary_df_w = get_networth_by_month(curr_month, curr_year)
                actual_cash_start = float(
                    summary_df_w[summary_df_w['account_type'] == 'Cash']['market_value'].sum()
                ) if not summary_df_w.empty else display_df_w.loc[display_df_w.index[0], 'Cash Balance']
            except Exception:
                actual_cash_start = display_df_w.loc[display_df_w.index[0], 'Cash Balance']

            display_df_w['Cash Start'] = display_df_w['Cash Balance'].shift(1)
            display_df_w.loc[display_df_w.index[0], 'Cash Start'] = actual_cash_start

            display_cols_w = [
                'Year', 'Age', 'Stage', 'Cash Start',
                'Wages', 'SS Benefits', 'RMD',
                'Trad→\nCash', 'Trad→\nBrok', 'Trad→\nRoth',
                'Brok→\nCash', 'Roth→\nCash',
                'Expenses', 'Healthcare Cost',
                'DAF Contribution', 'AGI', 'MAGI', 'Federal Tax', 'Cash Balance',
            ]
            available_cols_w = [c for c in display_cols_w if c in display_df_w.columns]
            display_df_w = cast(pd.DataFrame, display_df_w[available_cols_w].copy())
            numeric_cols_w = [c for c in available_cols_w if c not in ['Year', 'Age', 'Stage']]
            for col in numeric_cols_w:
                display_df_w[col] = display_df_w[col].map(format_currency)

            withdrawal_column_config = {
                "Year":             st.column_config.NumberColumn("Year", format="%d"),
                "Age":              st.column_config.TextColumn("Age"),
                "Stage":            st.column_config.TextColumn("Life Stage", help=_STAGE_COLUMN_HELP),
                "Cash Start":       st.column_config.TextColumn("Cash Start"),
                "Wages":            st.column_config.TextColumn("Wages"),
                "SS Benefits":      st.column_config.TextColumn("Social Security"),
                "RMD":              st.column_config.TextColumn("RMD"),
                "Trad→\nCash":      st.column_config.TextColumn("Trad→Cash"),
                "Trad→\nBrok":      st.column_config.TextColumn("Trad→Brok"),
                "Trad→\nRoth":      st.column_config.TextColumn("Trad→Roth"),
                "Brok→\nCash":      st.column_config.TextColumn("Brok→Cash"),
                "Roth→\nCash":      st.column_config.TextColumn("Roth→Cash"),
                "Expenses":         st.column_config.TextColumn("Expenses"),
                "Healthcare Cost":  st.column_config.TextColumn("Healthcare"),
                "DAF Contribution": st.column_config.TextColumn("DAF Contrib"),
                "AGI":              st.column_config.TextColumn("AGI"),
                "MAGI":             st.column_config.TextColumn("MAGI"),
                "Federal Tax":      st.column_config.TextColumn("Fed Tax"),
                "Cash Balance":     st.column_config.TextColumn("Cash End"),
            }
            st.dataframe(display_df_w, column_config=withdrawal_column_config, hide_index=True, use_container_width=True)

            _with_stages_present = display_df_w['Stage'].unique() if 'Stage' in display_df_w.columns else []
            with st.expander("ℹ️ Life Stage Guide", expanded=False):
                for _stage_name, _stage_desc in LIFE_STAGE_DESCRIPTIONS.items():
                    if _stage_name in list(_with_stages_present):
                        st.markdown(f"**{_stage_name}**")
                        st.caption(_stage_desc)
                        st.markdown("---")

        with balances_sub_tab:
            st.subheader("Account Balances Over Time")
            render_balance_table(balances_df_w)

        with charts_sub_tab:
            st.subheader("Portfolio Balance Projections")
            render_balance_chart(balances_df_w, title="Projected Account Balances (Withdrawal)")
            st.subheader("Income Sources Over Time")
            render_income_chart(strategy_df_w, title="Income Sources by Year (Withdrawal)")

    except Exception as e:
        st.error(f"Error calculating withdrawal strategy: {e}")
        st.info("Please ensure all sidebar parameters are properly configured.")

# ---------------------------------------------------------------------------
# Auto-rerun while background rebuilds are in flight
# ---------------------------------------------------------------------------
auto_rerun_if_rebuilding()

# Made with Bob
