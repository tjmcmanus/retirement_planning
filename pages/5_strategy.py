"""
pages/5_strategy.py
===================
📈 Strategy — Accumulation and Withdrawal planning across all life stages.

Enhanced UX with:
- Improved visual hierarchy for long-term planning
- State tax integration
- Month-by-month execution calendar
- Interactive Sankey diagrams
- Timeline view for key financial events
- Summary insight cards

Sub-tabs (st.tabs within the page):
  - 📋 Long-Term Plan     (multi-year strategy with state taxes)
  - 📅 Monthly Calendar   (month-by-month execution plan)
  - 💰 Account Balances   (projected balances table)
  - 📊 Visualizations     (stacked area + income bar charts)
"""
from __future__ import annotations

from typing import cast
import calendar

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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
from load_data import get_networth_by_month, get_portfolio_truth_by_month
from strategy import build_accumulation_strategy_display, build_withdrawal_strategy_display

_STAGE_COLUMN_HELP = (
    "The life stage determines which financial priorities and rules apply this year. "
    "Hover over the stage name in the legend below the table for a plain-English summary."
)

# Month names for calendar view
MONTH_NAMES = list(calendar.month_name)[1:]  # Skip empty first element

def render_summary_cards(strategy_df: pd.DataFrame, phase: str) -> None:
    """Render key insight cards at the top of the strategy view."""
    if strategy_df.empty:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_years = len(strategy_df)
        st.metric(
            "Planning Horizon",
            f"{total_years} years",
            help="Number of years in this financial plan"
        )
    
    with col2:
        if phase == "accumulation":
            total_contributions = strategy_df['Wages→\nTrad'].sum() + strategy_df['Wages→\nRoth'].sum() if 'Wages→\nTrad' in strategy_df.columns else 0
            st.metric(
                "Total Contributions",
                f"${total_contributions:,.0f}",
                help="Total retirement account contributions over planning period"
            )
        else:
            total_withdrawals = strategy_df['Trad→\nCash'].sum() if 'Trad→\nCash' in strategy_df.columns else 0
            st.metric(
                "Total Withdrawals",
                f"${total_withdrawals:,.0f}",
                help="Total withdrawals from retirement accounts"
            )
    
    with col3:
        total_taxes = strategy_df['Federal Tax'].sum() if 'Federal Tax' in strategy_df.columns else 0
        if 'State Tax' in strategy_df.columns:
            total_taxes += strategy_df['State Tax'].sum()
        st.metric(
            "Total Taxes",
            f"${total_taxes:,.0f}",
            help="Total federal and state taxes over planning period"
        )
    
    with col4:
        if 'Total Portfolio' in strategy_df.columns:
            final_portfolio = strategy_df['Total Portfolio'].iloc[-1]
            initial_portfolio = strategy_df['Total Portfolio'].iloc[0]
            growth = final_portfolio - initial_portfolio
            growth_pct = (growth / initial_portfolio * 100) if initial_portfolio > 0 else 0
            st.metric(
                "Portfolio Growth",
                f"${growth:,.0f}",
                f"{growth_pct:+.1f}%",
                help="Net portfolio growth over planning period"
            )


def render_timeline_view(strategy_df: pd.DataFrame) -> None:
    """Render a timeline visualization of key financial events."""
    if strategy_df.empty or 'Year' not in strategy_df.columns:
        return
    
    st.subheader("📍 Key Financial Events Timeline")
    
    # Identify key events
    events = []
    
    for idx, row in strategy_df.iterrows():
        year = int(row['Year'])
        age = row.get('Age', '')
        
        # Retirement event
        if 'Stage' in row and 'Retirement' in str(row['Stage']) and idx == 0:
            events.append({
                'year': year,
                'event': '🎯 Retirement Begins',
                'details': f"Age {age}",
                'color': '#FF6B6B'
            })
        
        # Medicare eligibility
        if 'Age' in row and '65' in str(age):
            events.append({
                'year': year,
                'event': '🏥 Medicare Eligible',
                'details': f"Age {age}",
                'color': '#4ECDC4'
            })
        
        # Social Security start
        if 'SS Benefits' in row and row['SS Benefits'] > 0 and (idx == 0 or strategy_df.iloc[idx-1]['SS Benefits'] == 0):
            events.append({
                'year': year,
                'event': '💰 Social Security Begins',
                'details': f"${row['SS Benefits']:,.0f}/year",
                'color': '#95E1D3'
            })
        
        # RMD start
        if 'RMD' in row and row['RMD'] > 0 and (idx == 0 or strategy_df.iloc[idx-1]['RMD'] == 0):
            events.append({
                'year': year,
                'event': '📊 RMDs Begin',
                'details': f"${row['RMD']:,.0f} required",
                'color': '#F38181'
            })
        
        # Large Roth conversions
        roth_conversion_col = 'Trad→\nRoth'
        if roth_conversion_col in row and row[roth_conversion_col] > 50000:
            conversion_amount = row[roth_conversion_col]
            events.append({
                'year': year,
                'event': '🔄 Major Roth Conversion',
                'details': f"${conversion_amount:,.0f}",
                'color': '#AA96DA'
            })
    
    if events:
        # Create timeline visualization
        years = strategy_df['Year'].tolist()
        min_year = min(years)
        max_year = max(years)
        year_range = max_year - min_year if max_year > min_year else 1
        
        # Build event markers
        event_markers = []
        for event in events:
            position = ((event['year'] - min_year) / year_range) * 100
            marker_html = f'<div style="position: absolute; left: {position}%; top: 50%; transform: translate(-50%, -50%);"><div style="width: 16px; height: 16px; border-radius: 50%; background: {event["color"]}; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"></div><div style="position: absolute; top: -60px; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap; font-size: 11px;"><div style="font-weight: 600; color: #333;">{event["event"]}</div><div style="color: #666;">{event["year"]}</div><div style="color: #888; font-size: 10px;">{event["details"]}</div></div></div>'
            event_markers.append(marker_html)
        
        timeline_html = f'<div style="position: relative; height: 120px; margin: 20px 0;"><div style="position: absolute; top: 50%; width: 100%; height: 2px; background: #ddd;"></div>{"".join(event_markers)}</div>'
        st.markdown(timeline_html, unsafe_allow_html=True)
    else:
        st.info("No significant financial events identified in this planning period.")


def create_monthly_execution_plan(strategy_df: pd.DataFrame, selected_year: int) -> pd.DataFrame:
    """
    Create a month-by-month execution plan for a specific year.
    
    Shows when to:
    - Make estimated tax payments
    - Execute Roth conversions
    - Take RMDs
    - Rebalance portfolio
    - Review and adjust strategy
    """
    if strategy_df.empty:
        return pd.DataFrame()
    
    # Find the row for the selected year
    year_data = strategy_df[strategy_df['Year'] == selected_year]
    if year_data.empty:
        return pd.DataFrame()
    
    row = year_data.iloc[0]
    
    # Create monthly plan
    monthly_plan = []
    
    for month_num in range(1, 13):
        month_name = MONTH_NAMES[month_num - 1]
        actions = []
        amounts = []
        
        # Q1 estimated taxes (April 15)
        if month_num == 4:
            if 'Federal Tax' in row and row['Federal Tax'] > 0:
                q1_tax = row['Federal Tax'] / 4
                actions.append("📋 Q1 Estimated Tax Payment")
                amounts.append(f"${q1_tax:,.0f}")
        
        # Q2 estimated taxes (June 15)
        if month_num == 6:
            if 'Federal Tax' in row and row['Federal Tax'] > 0:
                q2_tax = row['Federal Tax'] / 4
                actions.append("📋 Q2 Estimated Tax Payment")
                amounts.append(f"${q2_tax:,.0f}")
        
        # Q3 estimated taxes (September 15)
        if month_num == 9:
            if 'Federal Tax' in row and row['Federal Tax'] > 0:
                q3_tax = row['Federal Tax'] / 4
                actions.append("📋 Q3 Estimated Tax Payment")
                amounts.append(f"${q3_tax:,.0f}")
        
        # Roth conversions (spread throughout year, focus on low-income months)
        if 'Trad→\nRoth' in row and row['Trad→\nRoth'] > 0:
            # Spread conversions across Jan, Apr, Jul, Oct
            if month_num in [1, 4, 7, 10]:
                quarterly_conversion = row['Trad→\nRoth'] / 4
                actions.append("🔄 Roth Conversion")
                amounts.append(f"${quarterly_conversion:,.0f}")
        
        # RMDs (must be taken by December 31, suggest monthly or quarterly)
        if 'RMD' in row and row['RMD'] > 0:
            if month_num in [3, 6, 9, 12]:  # Quarterly RMD distributions
                quarterly_rmd = row['RMD'] / 4
                actions.append("📊 RMD Distribution")
                amounts.append(f"${quarterly_rmd:,.0f}")
        
        # Traditional IRA withdrawals (monthly for living expenses)
        if 'Trad→\nCash' in row and row['Trad→\nCash'] > 0:
            monthly_withdrawal = row['Trad→\nCash'] / 12
            if monthly_withdrawal > 1000:  # Only show if significant
                actions.append("💵 Traditional → Cash")
                amounts.append(f"${monthly_withdrawal:,.0f}")
        
        # Portfolio rebalancing (quarterly)
        if month_num in [3, 6, 9, 12]:
            actions.append("⚖️ Portfolio Rebalance Review")
            amounts.append("")
        
        # Annual strategy review (January and July)
        if month_num in [1, 7]:
            actions.append("📈 Strategy Review & Adjustment")
            amounts.append("")
        
        # Q4 estimated taxes (January 15 of following year)
        if month_num == 1:
            if 'Federal Tax' in row and row['Federal Tax'] > 0:
                q4_tax = row['Federal Tax'] / 4
                actions.append("📋 Q4 Estimated Tax Payment (Prior Year)")
                amounts.append(f"${q4_tax:,.0f}")
        
        # Healthcare premium payments (monthly)
        if 'Healthcare Cost' in row and row['Healthcare Cost'] > 0:
            monthly_healthcare = row['Healthcare Cost'] / 12
            if month_num == 1:  # Show in January as annual note
                actions.append("🏥 Healthcare Premiums")
                amounts.append(f"${monthly_healthcare:,.0f}/month")
        
        monthly_plan.append({
            'Month': month_name,
            'Actions': '\n\n'.join(actions) if actions else '—',
            'Amounts': '\n\n'.join(amounts) if amounts else '—',
            'Action_Count': len(actions)
        })
    
    return pd.DataFrame(monthly_plan)


def render_interactive_sankey(strategy_df: pd.DataFrame, portfolio: pd.DataFrame, 
                              annual_expenses: float, phase: str) -> None:
    """Render Sankey diagram with year selector."""
    if strategy_df.empty:
        return
    
    st.subheader("💸 Money Flow Visualization")
    
    # Year selector
    years = strategy_df['Year'].unique().tolist()
    selected_year = st.selectbox(
        "Select Year to Visualize",
        options=years,
        index=0,
        help="Choose a year to see the detailed money flow for that specific year"
    )
    
    # Get data for selected year
    year_data = strategy_df[strategy_df['Year'] == selected_year].iloc[0]
    
    # Build Sankey based on actual year data
    if phase == "accumulation":
        render_accumulation_sankey_for_year(year_data, portfolio, annual_expenses)
    else:
        render_withdrawal_sankey_for_year(year_data, portfolio, annual_expenses)


def render_accumulation_sankey_for_year(year_data: pd.Series, portfolio: pd.DataFrame, 
                                        annual_expenses: float) -> None:
    """Render accumulation Sankey for a specific year using actual data."""
    sources = []
    targets = []
    values = []
    
    # Wages to various accounts
    if 'Wages' in year_data and year_data['Wages'] > 0:
        if 'Wages→\nTrad' in year_data and year_data['Wages→\nTrad'] > 1000:
            sources.append("Wages/Salary")
            targets.append("Traditional 401(k)/IRA")
            values.append(float(year_data['Wages→\nTrad']))
        
        if 'Wages→\nRoth' in year_data and year_data['Wages→\nRoth'] > 1000:
            sources.append("Wages/Salary")
            targets.append("Roth IRA/401(k)")
            values.append(float(year_data['Wages→\nRoth']))
    
    # After-tax flows
    if 'Cash→\nBrok' in year_data and year_data['Cash→\nBrok'] > 1000:
        sources.append("After-Tax Income")
        targets.append("Brokerage Account")
        values.append(float(year_data['Cash→\nBrok']))
    
    if 'Cash→\nRoth' in year_data and year_data['Cash→\nRoth'] > 1000:
        sources.append("After-Tax Income")
        targets.append("Roth IRA/401(k)")
        values.append(float(year_data['Cash→\nRoth']))
    
    # Conversions
    if 'Trad→\nRoth' in year_data and year_data['Trad→\nRoth'] > 1000:
        sources.append("Traditional 401(k)/IRA")
        targets.append("Roth Conversion")
        values.append(float(year_data['Trad→\nRoth']))
    
    if sources:
        _render_sankey_diagram(sources, targets, values, 
                              f"💰 Money Flow for {int(year_data['Year'])}: Income → Accounts")
    else:
        st.info("No significant money flows to visualize for this year.")


def render_withdrawal_sankey_for_year(year_data: pd.Series, portfolio: pd.DataFrame,
                                     annual_expenses: float) -> None:
    """Render withdrawal Sankey for a specific year using actual data."""
    sources = []
    targets = []
    values = []
    
    # Traditional withdrawals
    if 'Trad→\nCash' in year_data and year_data['Trad→\nCash'] > 1000:
        sources.append("Traditional IRA/401(k)")
        targets.append("Living Expenses")
        values.append(float(year_data['Trad→\nCash']))
    
    # Brokerage withdrawals
    if 'Brok→\nCash' in year_data and year_data['Brok→\nCash'] > 1000:
        sources.append("Brokerage Account")
        targets.append("Living Expenses")
        values.append(float(year_data['Brok→\nCash']))
    
    # Roth withdrawals
    if 'Roth→\nCash' in year_data and year_data['Roth→\nCash'] > 1000:
        sources.append("Roth IRA/401(k)")
        targets.append("Living Expenses")
        values.append(float(year_data['Roth→\nCash']))
    
    # Roth conversions
    if 'Trad→\nRoth' in year_data and year_data['Trad→\nRoth'] > 1000:
        sources.append("Traditional IRA/401(k)")
        targets.append("Roth Conversion")
        values.append(float(year_data['Trad→\nRoth']))
    
    # RMDs to brokerage
    if 'Trad→\nBrok' in year_data and year_data['Trad→\nBrok'] > 1000:
        sources.append("Traditional IRA/401(k)")
        targets.append("RMD → Brokerage")
        values.append(float(year_data['Trad→\nBrok']))
    
    # Social Security
    if 'SS Benefits' in year_data and year_data['SS Benefits'] > 1000:
        sources.append("Social Security")
        targets.append("Living Expenses")
        values.append(float(year_data['SS Benefits']))
    
    # Healthcare
    if 'Healthcare Cost' in year_data and year_data['Healthcare Cost'] > 5000:
        sources.append("Traditional IRA/401(k)")
        targets.append("Healthcare")
        values.append(float(year_data['Healthcare Cost']))
    
    if sources:
        _render_sankey_diagram(sources, targets, values,
                              f"💸 Money Flow for {int(year_data['Year'])}: Accounts → Expenses & Conversions")
    else:
        st.info("No significant money flows to visualize for this year.")


def _render_sankey_diagram(sources: list, targets: list, values: list, title: str) -> None:
    """Helper to render a Sankey diagram."""
    # Color mappings
    source_colors = {
        "Wages/Salary": "rgba(31, 119, 180, 0.8)",
        "After-Tax Income": "rgba(44, 160, 44, 0.8)",
        "Employer Match": "rgba(255, 127, 14, 0.8)",
        "Traditional IRA/401(k)": "rgba(214, 39, 40, 0.8)",
        "Roth IRA/401(k)": "rgba(148, 103, 189, 0.8)",
        "Brokerage Account": "rgba(255, 187, 120, 0.8)",
        "Cash/Savings": "rgba(152, 223, 138, 0.8)",
        "Social Security": "rgba(23, 190, 207, 0.8)"
    }
    
    target_colors = {
        "Traditional 401(k)/IRA": "rgba(214, 39, 40, 0.6)",
        "Roth IRA/401(k)": "rgba(148, 103, 189, 0.6)",
        "Brokerage Account": "rgba(255, 187, 120, 0.6)",
        "Cash/Savings": "rgba(152, 223, 138, 0.6)",
        "Living Expenses": "rgba(31, 119, 180, 0.6)",
        "Healthcare": "rgba(255, 127, 14, 0.6)",
        "Roth Conversion": "rgba(148, 103, 189, 0.6)",
        "RMD → Brokerage": "rgba(255, 187, 120, 0.6)",
        "Traditional 401(k)": "rgba(214, 39, 40, 0.6)"
    }
    
    # Build node list
    all_nodes = list(dict.fromkeys(sources + targets))
    node_colors = []
    for node in all_nodes:
        if node in source_colors:
            node_colors.append(source_colors[node])
        else:
            node_colors.append(target_colors.get(node, "rgba(200, 200, 200, 0.6)"))
    
    # Map to indices
    source_indices = [all_nodes.index(s) for s in sources]
    target_indices = [all_nodes.index(t) for t in targets]
    
    # Create link colors
    link_colors = []
    for src in sources:
        if src in source_colors:
            color = source_colors[src].replace("0.8)", "0.3)")
            link_colors.append(color)
        else:
            link_colors.append("rgba(200, 200, 200, 0.3)")
    
    # Create Sankey diagram
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=20,
            thickness=25,
            line=dict(color="black", width=1),
            label=all_nodes,
            color=node_colors,
            hovertemplate='%{label}<br>Total: $%{value:,.0f}<extra></extra>'
        ),
        link=dict(
            source=source_indices,
            target=target_indices,
            value=values,
            color=link_colors,
            hovertemplate='%{source.label} → %{target.label}<br>Amount: $%{value:,.0f}<extra></extra>'
        ),
        textfont=dict(size=14, family="Arial, sans-serif", color="black")
    )])
    
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=16, family="Arial, sans-serif", color="#333")
        ),
        font=dict(size=14, family="Arial, sans-serif", color="#000"),
        height=400,
        margin=dict(l=20, r=20, t=60, b=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)


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

navbar("📋 Strategy")

st.header("📈 Long-Term Financial Strategy")
st.markdown("Comprehensive planning across all life stages with granular flow-of-funds tracking.")
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

# Create tabs with new monthly calendar view
long_term_tab, monthly_tab, balances_tab, charts_tab = st.tabs(
    ["📋 Long-Term Plan", "📅 Monthly Calendar", "💰 Account Balances", "📊 Visualizations"]
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
        accum_state             = _acfg.get("personal_info", "state", "CA")
    except Exception:
        accum_expense_inflation = 0.03
        accum_person1_name      = "Person1"
        accum_person2_name      = "Person2"
        accum_annual_expenses   = 120_000
        accum_state             = "CA"

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

        with long_term_tab:
            st.subheader("📊 Multi-Year Accumulation Plan")
            
            # Summary cards
            render_summary_cards(accum_strategy_df, "accumulation")
            st.markdown("---")
            
            # Timeline view
            render_timeline_view(accum_strategy_df)
            st.markdown("---")
            
            # Interactive Sankey
            portfolio = get_portfolio_truth_by_month(curr_month, curr_year)
            render_interactive_sankey(accum_strategy_df, cast(pd.DataFrame, portfolio), 
                                    accum_annual_expenses, "accumulation")
            st.markdown("---")
            
            # Enhanced table with state taxes
            st.subheader("📋 Year-by-Year Details")
            display_df_a = accum_strategy_df.copy()
            
            # Add state tax column (placeholder - would need actual calculation)
            if 'Federal Tax' in display_df_a.columns and 'State Tax' not in display_df_a.columns:
                # Estimate state tax as percentage of federal (simplified)
                state_rates = {'CA': 0.093, 'NY': 0.0685, 'TX': 0.0, 'FL': 0.0}
                state_rate = state_rates.get(accum_state, 0.05)
                display_df_a['State Tax'] = display_df_a['AGI'] * state_rate if 'AGI' in display_df_a.columns else 0
            
            display_cols_a = [
                'Year', 'Age', 'Stage',
                'Wages', 'Wages→\nPayroll', 'Wages→\nTrad', 'Wages→\nRoth',
                'Trad→\nRoth', 'Cash→\nRoth', 'Cash→\nBrok',
                'Expenses', 'Healthcare Cost', 'AGI', 'Federal Tax', 'State Tax', 'Cash Balance',
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
                "State Tax":      st.column_config.TextColumn("State Tax", help=f"Estimated {accum_state} state income tax"),
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

        with monthly_tab:
            st.subheader("📅 Month-by-Month Execution Plan")
            st.markdown("Detailed monthly action items for executing your financial strategy.")
            
            # Year selector for monthly view
            years_available = accum_strategy_df['Year'].unique().tolist()
            selected_year_monthly = st.selectbox(
                "Select Year for Monthly Plan",
                options=years_available,
                index=0,
                key="accum_monthly_year"
            )
            
            monthly_df = create_monthly_execution_plan(accum_strategy_df, selected_year_monthly)
            
            if not monthly_df.empty:
                # Display as cards for better UX
                for idx, row in monthly_df.iterrows():
                    if row['Action_Count'] > 0:
                        with st.expander(f"📆 {row['Month']}", expanded=(idx < 2)):
                            st.markdown(row['Actions'])
                            if row['Amounts'] != '—':
                                st.markdown(f"**Amounts:**\n\n{row['Amounts']}")
            else:
                st.info("No monthly actions for the selected year.")

        with balances_tab:
            st.subheader("Account Balances Over Time")
            render_balance_table(accum_balances_df)

        with charts_tab:
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
        state                    = _cfg.get("personal_info", "state", "CA")
    except Exception:
        aca_marketplace_enrolled = False; expense_inflation_rate = 0.03
        person1_name = "Person1"; person2_name = "Person2"; state = "CA"

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

        with long_term_tab:
            st.subheader("📊 Multi-Year Withdrawal Strategy")
            
            # Summary cards
            render_summary_cards(strategy_df_w, "withdrawal")
            st.markdown("---")
            
            # Timeline view
            render_timeline_view(strategy_df_w)
            st.markdown("---")
            
            # Interactive Sankey
            portfolio_w = get_portfolio_truth_by_month(curr_month, curr_year)
            render_interactive_sankey(strategy_df_w, cast(pd.DataFrame, portfolio_w),
                                    annual_expenses_s, "withdrawal")
            st.markdown("---")
            
            # Enhanced table with state taxes
            st.subheader("📋 Year-by-Year Details")
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
            
            # Add state tax column
            if 'Federal Tax' in display_df_w.columns and 'State Tax' not in display_df_w.columns:
                state_rates = {'CA': 0.093, 'NY': 0.0685, 'TX': 0.0, 'FL': 0.0}
                state_rate = state_rates.get(state, 0.05)
                display_df_w['State Tax'] = display_df_w['AGI'] * state_rate if 'AGI' in display_df_w.columns else 0

            display_cols_w = [
                'Year', 'Age', 'Stage', 'Cash Start',
                'Wages', 'SS Benefits', 'RMD',
                'Trad→\nCash', 'Trad→\nBrok', 'Trad→\nRoth',
                'Brok→\nCash', 'Roth→\nCash',
                'Expenses', 'Healthcare Cost',
                'DAF Contribution', 'AGI', 'MAGI', 'Federal Tax', 'State Tax', 'Cash Balance',
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
                "SS Benefits":      st.column_config.TextColumn("SS Benefits"),
                "RMD":              st.column_config.TextColumn("RMD"),
                "Trad→\nCash":      st.column_config.TextColumn("Trad→Cash"),
                "Trad→\nBrok":      st.column_config.TextColumn("Trad→Brok"),
                "Trad→\nRoth":      st.column_config.TextColumn("Trad→Roth"),
                "Brok→\nCash":      st.column_config.TextColumn("Brok→Cash"),
                "Roth→\nCash":      st.column_config.TextColumn("Roth→Cash"),
                "Expenses":         st.column_config.TextColumn("Expenses"),
                "Healthcare Cost":  st.column_config.TextColumn("Healthcare"),
                "DAF Contribution": st.column_config.TextColumn("DAF"),
                "AGI":              st.column_config.TextColumn("AGI"),
                "MAGI":             st.column_config.TextColumn("MAGI"),
                "Federal Tax":      st.column_config.TextColumn("Fed Tax"),
                "State Tax":        st.column_config.TextColumn("State Tax", help=f"Estimated {state} state income tax"),
                "Cash Balance":     st.column_config.TextColumn("Cash End"),
            }
            st.dataframe(display_df_w, column_config=withdrawal_column_config, hide_index=True, use_container_width=True)

            _withdrawal_stages_present = display_df_w['Stage'].unique() if 'Stage' in display_df_w.columns else []
            with st.expander("ℹ️ Life Stage Guide", expanded=False):
                for _stage_name, _stage_desc in LIFE_STAGE_DESCRIPTIONS.items():
                    if _stage_name in list(_withdrawal_stages_present):
                        st.markdown(f"**{_stage_name}**")
                        st.caption(_stage_desc)
                        st.markdown("---")

        with monthly_tab:
            st.subheader("📅 Month-by-Month Execution Plan")
            st.markdown("Detailed monthly action items for executing your withdrawal strategy.")
            
            # Year selector for monthly view
            years_available_w = strategy_df_w['Year'].unique().tolist()
            selected_year_monthly_w = st.selectbox(
                "Select Year for Monthly Plan",
                options=years_available_w,
                index=0,
                key="withdrawal_monthly_year"
            )
            
            monthly_df_w = create_monthly_execution_plan(strategy_df_w, selected_year_monthly_w)
            
            if not monthly_df_w.empty:
                # Display as cards for better UX
                for idx, row in monthly_df_w.iterrows():
                    if row['Action_Count'] > 0:
                        with st.expander(f"📆 {row['Month']}", expanded=(idx < 2)):
                            st.markdown(row['Actions'])
                            if row['Amounts'] != '—':
                                st.markdown(f"**Amounts:**\n\n{row['Amounts']}")
            else:
                st.info("No monthly actions for the selected year.")

        with balances_tab:
            st.subheader("Account Balances Over Time")
            render_balance_table(balances_df_w)

        with charts_tab:
            st.subheader("Portfolio Balance Projections")
            render_balance_chart(balances_df_w, title="Projected Account Balances (Withdrawal)")
            st.subheader("Income Sources Over Time")
            render_income_chart(strategy_df_w, title="Income Sources by Year (Withdrawal)")

    except Exception as e:
        st.error(f"Error calculating withdrawal strategy: {e}")
        st.info("Please ensure all configuration parameters are properly set.")

# Made with Bob