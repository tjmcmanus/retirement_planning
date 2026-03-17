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
import streamlit.components.v1 as components
from streamlit_extras.add_vertical_space import add_vertical_space

from components.navbar import navbar
from config import get_config_manager
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
    
    # Get person names from config
    try:
        from config import get_config_manager
        cfg = get_config_manager()
        person1_name = cfg.get("personal_info", "person1_name", "Person 1")
        person2_name = cfg.get("personal_info", "person2_name", "Person 2")
        person1_ss_age = cfg.get("social_security", "person1_ssi_age", 70)
        person2_ss_age = cfg.get("social_security", "person2_ssi_age", 70)
        person1_retirement_age = cfg.get("personal_info", "person1_retirement_age", 67)
        person2_retirement_age = cfg.get("personal_info", "person2_retirement_age", 62)
    except Exception:
        person1_name = "Person 1"
        person2_name = "Person 2"
        person1_ss_age = 70
        person2_ss_age = 70
        person1_retirement_age = 67
        person2_retirement_age = 62
    
    # Identify key events (limit to first 15 years)
    events = []
    person1_ss_started = False
    person2_ss_started = False
    person1_medicare_added = False
    person2_medicare_added = False
    
    # Get the starting year and limit timeline to 15 years
    start_year = int(strategy_df.iloc[0]['Year'])
    timeline_limit_year = start_year + 15
    
    for idx, row in strategy_df.iterrows():
        year = int(row['Year'])
        
        # Skip events beyond 15 years
        if year > timeline_limit_year:
            break
        age_str = row.get('Age', '')
        
        # Parse individual ages from "age1/age2" format
        age_primary = 0
        age_spouse = 0
        if '/' in str(age_str):
            ages = str(age_str).split('/')
            try:
                age_primary = int(ages[0].strip())
                age_spouse = int(ages[1].strip()) if len(ages) > 1 else 0
            except (ValueError, IndexError):
                pass
        
        # Retirement events (individual)
        if 'Stage' in row and 'Retirement' in str(row['Stage']) and idx == 0:
            # Check if this is person1's retirement year
            if age_primary == person1_retirement_age:
                events.append({
                    'year': year,
                    'event': f'🎯 {person1_name} Retires',
                    'details': f"Age {age_primary}",
                    'color': '#FF6B6B'
                })
            # Check if this is person2's retirement year
            if age_spouse == person2_retirement_age and age_spouse > 0:
                events.append({
                    'year': year,
                    'event': f'🎯 {person2_name} Retires',
                    'details': f"Age {age_spouse}",
                    'color': '#FF8C8C'
                })
        
        # Medicare eligibility (individual)
        if age_primary == 65 and not person1_medicare_added:
            events.append({
                'year': year,
                'event': f'🏥 {person1_name} Medicare',
                'details': f"Age 65",
                'color': '#4ECDC4'
            })
            person1_medicare_added = True
        
        if age_spouse == 65 and not person2_medicare_added and age_spouse > 0:
            events.append({
                'year': year,
                'event': f'🏥 {person2_name} Medicare',
                'details': f"Age 65",
                'color': '#6EDDD5'
            })
            person2_medicare_added = True
        
        # Social Security start (individual)
        if 'SS Benefits' in row and row['SS Benefits'] > 0:
            # Check if person1 just started SS
            if age_primary >= person1_ss_age and not person1_ss_started:
                events.append({
                    'year': year,
                    'event': f'💰 {person1_name} SS Begins',
                    'details': f"Age {age_primary}",
                    'color': '#95E1D3'
                })
                person1_ss_started = True
            
            # Check if person2 just started SS
            if age_spouse >= person2_ss_age and not person2_ss_started and age_spouse > 0:
                events.append({
                    'year': year,
                    'event': f'💰 {person2_name} SS Begins',
                    'details': f"Age {age_spouse}",
                    'color': '#B5F1E3'
                })
                person2_ss_started = True
        
        # RMD start (combined event since it's household-level)
        if 'RMD' in row and row['RMD'] > 0 and (idx == 0 or strategy_df.iloc[idx-1]['RMD'] == 0):
            events.append({
                'year': year,
                'event': '📊 RMDs Begin',
                'details': f"${row['RMD']:,.0f} required",
                'color': '#F38181'
            })
        
        # Large Roth conversions (household-level)
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
        # Create timeline visualization based on actual event years (not full strategy period)
        event_years = [e['year'] for e in events]
        min_event_year = min(event_years)
        max_event_year = max(event_years)
        
        # Add some padding to the timeline (1 year on each side)
        timeline_start = min_event_year - 1
        timeline_end = max_event_year + 1
        year_range = timeline_end - timeline_start if timeline_end > timeline_start else 1
        
        # Add year markers along the timeline for better context
        year_markers = []
        # Determine interval based on range (every 1-5 years depending on span)
        if year_range <= 10:
            year_interval = 1
        elif year_range <= 20:
            year_interval = 2
        else:
            year_interval = 5
            
        for year in range(timeline_start, timeline_end + 1, year_interval):
            # Use same coordinate system as events: 2.5% to 97.5%
            position = 2.5 + ((year - timeline_start) / year_range) * 95
            year_markers.append(f'''
                <div style="position: absolute; left: {position}%; top: 50%; transform: translate(-50%, 0);">
                    <div style="width: 2px; height: 12px; background: #999; margin: 0 auto;"></div>
                    <div style="text-align: center; font-size: 10px; color: #999; margin-top: 4px;">{year}</div>
                </div>
            ''')
        
        # Group events by year to handle overlaps better
        from collections import defaultdict
        events_by_year = defaultdict(list)
        for event in events:
            events_by_year[event['year']].append(event)
        
        # Build event markers with smart vertical positioning for overlaps
        event_markers = []
        for year, year_events in events_by_year.items():
            position = 2.5 + ((year - timeline_start) / year_range) * 95
            
            # For multiple events in same year, spread them vertically
            num_events = len(year_events)
            if num_events == 1:
                # Single event: alternate top/bottom based on year
                vertical_offset = -70 if year % 2 == 0 else 30
                offsets = [vertical_offset]
            elif num_events == 2:
                # Two events: one top, one bottom
                offsets = [-70, 30]
            elif num_events == 3:
                # Three events: top, middle-top, bottom
                offsets = [-90, -50, 30]
            else:
                # Four or more: spread them out
                offsets = [-110, -70, -30, 30] + [50 + (i * 20) for i in range(num_events - 4)]
            
            for idx, event in enumerate(year_events):
                vertical_offset = offsets[idx] if idx < len(offsets) else 50
                
                marker_html = f'''<div style="position: absolute; left: {position}%; top: 50%; transform: translate(-50%, -50%);">
                    <div style="width: 16px; height: 16px; border-radius: 50%; background: {event["color"]}; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.2); z-index: 10; position: relative;"></div>
                    <div style="position: absolute; top: {vertical_offset}px; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap; font-size: 11px; min-width: 120px; z-index: 5;">
                        <div style="font-weight: 600; color: #333; margin-bottom: 2px;">{event["event"]}</div>
                        <div style="color: #666; margin-bottom: 1px;">{event["year"]}</div>
                        <div style="color: #888; font-size: 10px;">{event["details"]}</div>
                    </div>
                </div>'''
                event_markers.append(marker_html)
        
        # Create the timeline with year markers and events
        timeline_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; padding: 0; }}
            </style>
        </head>
        <body>
        <div style="position: relative; height: 240px; margin: 30px 0; padding: 0 20px;">
            <div style="position: absolute; top: 50%; left: 2.5%; right: 2.5%; height: 3px; background: linear-gradient(to right, #ddd 0%, #999 50%, #ddd 100%); border-radius: 2px;"></div>
            {"".join(year_markers)}
            {"".join(event_markers)}
        </div>
        </body>
        </html>
        '''
        components.html(timeline_html, height=280)
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
                q1_fed = row['Federal Tax'] / 4
                q1_state = (row.get('State Tax', 0) / 4) if 'State Tax' in row else 0
                q1_total = q1_fed + q1_state
                if q1_state > 0:
                    actions.append("📋 Q1 Estimated Tax Payment")
                    amounts.append(f"${q1_total:,.0f} (Fed ${q1_fed:,.0f} + State ${q1_state:,.0f})")
                else:
                    actions.append("📋 Q1 Estimated Tax Payment (Federal)")
                    amounts.append(f"${q1_fed:,.0f}")
        
        # Q2 estimated taxes (June 15)
        if month_num == 6:
            if 'Federal Tax' in row and row['Federal Tax'] > 0:
                q2_fed = row['Federal Tax'] / 4
                q2_state = (row.get('State Tax', 0) / 4) if 'State Tax' in row else 0
                q2_total = q2_fed + q2_state
                if q2_state > 0:
                    actions.append("📋 Q2 Estimated Tax Payment")
                    amounts.append(f"${q2_total:,.0f} (Fed ${q2_fed:,.0f} + State ${q2_state:,.0f})")
                else:
                    actions.append("📋 Q2 Estimated Tax Payment (Federal)")
                    amounts.append(f"${q2_fed:,.0f}")
        
        # Q3 estimated taxes (September 15)
        if month_num == 9:
            if 'Federal Tax' in row and row['Federal Tax'] > 0:
                q3_fed = row['Federal Tax'] / 4
                q3_state = (row.get('State Tax', 0) / 4) if 'State Tax' in row else 0
                q3_total = q3_fed + q3_state
                if q3_state > 0:
                    actions.append("📋 Q3 Estimated Tax Payment")
                    amounts.append(f"${q3_total:,.0f} (Fed ${q3_fed:,.0f} + State ${q3_state:,.0f})")
                else:
                    actions.append("📋 Q3 Estimated Tax Payment (Federal)")
                    amounts.append(f"${q3_fed:,.0f}")
        
        # Roth conversions (spread throughout year, focus on low-income months)
        if 'Trad→\nRoth' in row and row['Trad→\nRoth'] > 0:
            # Spread conversions across Jan, Apr, Jul, Oct
            if month_num in [1, 4, 7, 10]:
                quarterly_conversion = row['Trad→\nRoth'] / 4
                actions.append("🔄 Roth Conversion (Trad→Roth)")
                amounts.append(f"${quarterly_conversion:,.0f}")
        
        # RMDs (must be taken by December 31, suggest monthly or quarterly)
        if 'RMD' in row and row['RMD'] > 0:
            if month_num in [3, 6, 9, 12]:  # Quarterly RMD distributions
                quarterly_rmd = row['RMD'] / 4
                actions.append("📊 RMD Distribution (Trad→Brokerage)")
                amounts.append(f"${quarterly_rmd:,.0f}")
        
        # Traditional IRA withdrawals (monthly for living expenses)
        if 'Trad→\nCash' in row and row['Trad→\nCash'] > 0:
            monthly_withdrawal = row['Trad→\nCash'] / 12
            if monthly_withdrawal > 1000:  # Only show if significant
                actions.append("💵 Traditional → Cash (for expenses)")
                amounts.append(f"${monthly_withdrawal:,.0f}")
        
        # Portfolio rebalancing (quarterly)
        if month_num in [3, 6, 9, 12]:
            actions.append("⚖️ Portfolio Rebalance Review")
            amounts.append("—")
        
        # Annual strategy review (January and July)
        if month_num in [1, 7]:
            actions.append("📈 Strategy Review & Adjustment")
            amounts.append("—")
        
        # Q4 estimated taxes (January 15 of following year)
        if month_num == 1:
            if 'Federal Tax' in row and row['Federal Tax'] > 0:
                q4_fed = row['Federal Tax'] / 4
                q4_state = (row.get('State Tax', 0) / 4) if 'State Tax' in row else 0
                q4_total = q4_fed + q4_state
                if q4_state > 0:
                    actions.append("📋 Q4 Estimated Tax Payment (Prior Year)")
                    amounts.append(f"${q4_total:,.0f} (Fed ${q4_fed:,.0f} + State ${q4_state:,.0f})")
                else:
                    actions.append("📋 Q4 Estimated Tax Payment (Prior Year, Federal)")
                    amounts.append(f"${q4_fed:,.0f}")
        
        # Healthcare premium payments (monthly)
        if 'Healthcare Cost' in row and row['Healthcare Cost'] > 0:
            monthly_healthcare = row['Healthcare Cost'] / 12
            if month_num == 1:  # Show in January as annual note
                actions.append("🏥 Healthcare Premiums")
                amounts.append(f"${monthly_healthcare:,.0f}/month")
        
        # DAF (Donor Advised Fund) contributions (typically made in December for tax deduction)
        if 'DAF Contribution' in row and row['DAF Contribution'] > 0:
            if month_num == 12:  # Suggest December for year-end tax planning
                actions.append("🎁 DAF Contribution (Charitable Giving)")
                amounts.append(f"${row['DAF Contribution']:,.0f}")
        
        # Combine actions with their amounts for clearer display
        combined_actions = []
        for i, action in enumerate(actions):
            if i < len(amounts) and amounts[i] and amounts[i] != '—':
                combined_actions.append(f"{action}: **{amounts[i]}**")
            else:
                combined_actions.append(action)
        
        monthly_plan.append({
            'Month': month_name,
            'Actions': '\n\n'.join(combined_actions) if combined_actions else '—',
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
    
    # Calculate after-tax wages (wages minus retirement contributions and payroll taxes)
    wages = float(year_data.get('Wages', 0) or 0)
    wages_to_trad = float(year_data.get('Wages→\nTrad', 0) or 0)
    wages_to_roth = float(year_data.get('Wages→\nRoth', 0) or 0)
    payroll_tax = float(year_data.get('Wages→\nPayroll', 0) or 0)
    ss_benefits = float(year_data.get('SS Benefits', 0) or 0)
    federal_tax = float(year_data.get('Federal Tax', 0) or 0)
    state_tax = float(year_data.get('State Tax', 0) or 0)
    
    # Wages to retirement accounts and cash
    if wages > 1000:
        if wages_to_trad > 1000:
            sources.append("Wages/Salary")
            targets.append("Traditional 401(k)/IRA")
            values.append(wages_to_trad)
        
        if wages_to_roth > 1000:
            sources.append("Wages/Salary")
            targets.append("Roth IRA/401(k)")
            values.append(wages_to_roth)
        
        # Payroll tax from wages
        if payroll_tax > 1000:
            sources.append("Wages/Salary")
            targets.append("Payroll Taxes")
            values.append(payroll_tax)
        
        # After-tax wages to cash/spending (for expenses)
        after_tax_wages = wages - wages_to_trad - wages_to_roth - payroll_tax
        if after_tax_wages > 1000:
            sources.append("Wages/Salary")
            targets.append("Cash/Spending")
            values.append(after_tax_wages)
        elif wages > 1000:
            # If no retirement contributions and after-tax is small, still show wages → cash
            # This handles cases where wages exist but aren't being saved
            sources.append("Wages/Salary")
            targets.append("Cash/Spending")
            values.append(wages - payroll_tax)
    
    # Social Security to cash (for age-gap marriages where one person collects SS while other still works)
    if ss_benefits > 1000:
        sources.append("Social Security")
        targets.append("Cash/Spending")
        values.append(ss_benefits)
    
    # Cash to expenses
    expenses = float(year_data.get('Expenses', 0) or 0)
    if expenses > 1000:
        sources.append("Cash/Spending")
        targets.append("Living Expenses")
        values.append(expenses)
    
    # Cash to healthcare
    healthcare = float(year_data.get('Healthcare Cost', 0) or 0)
    if healthcare > 1000:
        sources.append("Cash/Spending")
        targets.append("Healthcare")
        values.append(healthcare)
    
    # Cash to federal taxes
    if federal_tax > 1000:
        sources.append("Cash/Spending")
        targets.append("Federal Income Tax")
        values.append(federal_tax)
    
    # Cash to state taxes
    if state_tax > 1000:
        sources.append("Cash/Spending")
        targets.append("State Income Tax")
        values.append(state_tax)
    
    # After-tax flows to investments
    if 'Cash→\nBrok' in year_data and year_data['Cash→\nBrok'] > 1000:
        sources.append("Cash/Spending")
        targets.append("Brokerage Account")
        values.append(float(year_data['Cash→\nBrok']))
    
    if 'Cash→\nRoth' in year_data and year_data['Cash→\nRoth'] > 1000:
        sources.append("Cash/Spending")
        targets.append("Roth IRA/401(k)")
        values.append(float(year_data['Cash→\nRoth']))
    
    # Conversions
    if 'Trad→\nRoth' in year_data and year_data['Trad→\nRoth'] > 1000:
        sources.append("Traditional 401(k)/IRA")
        targets.append("Roth Conversion")
        values.append(float(year_data['Trad→\nRoth']))
    
    if sources:
        _render_sankey_diagram(sources, targets, values,
                              f"💰 Money Flow for {int(year_data['Year'])}: Income → Accounts & Expenses")
    else:
        st.info("No significant money flows to visualize for this year.")


def render_withdrawal_sankey_for_year(year_data: pd.Series, portfolio: pd.DataFrame,
                                     annual_expenses: float) -> None:
    """Render withdrawal Sankey for a specific year using actual data."""
    sources = []
    targets = []
    values = []
    
    # Wages to cash and payroll tax (for age-gap marriages where one person still works during withdrawal phase)
    wages = float(year_data.get('Wages', 0) or 0)
    payroll_tax = float(year_data.get('Wages→\nPayroll', 0) or 0)
    federal_tax = float(year_data.get('Federal Tax', 0) or 0)
    state_tax = float(year_data.get('State Tax', 0) or 0)
    
    if wages > 1000:
        # Payroll tax from wages
        if payroll_tax > 1000:
            sources.append("Wages/Salary")
            targets.append("Payroll Taxes")
            values.append(payroll_tax)
        
        after_tax_wages = wages - payroll_tax
        sources.append("Wages/Salary")
        targets.append("Cash/Spending")
        values.append(after_tax_wages)
    
    # Traditional withdrawals to cash
    if 'Trad→\nCash' in year_data and year_data['Trad→\nCash'] > 1000:
        sources.append("Traditional IRA/401(k)")
        targets.append("Cash/Spending")
        values.append(float(year_data['Trad→\nCash']))
    
    # Brokerage withdrawals to cash
    if 'Brok→\nCash' in year_data and year_data['Brok→\nCash'] > 1000:
        sources.append("Brokerage Account")
        targets.append("Cash/Spending")
        values.append(float(year_data['Brok→\nCash']))
    
    # Roth withdrawals to cash
    if 'Roth→\nCash' in year_data and year_data['Roth→\nCash'] > 1000:
        sources.append("Roth IRA/401(k)")
        targets.append("Cash/Spending")
        values.append(float(year_data['Roth→\nCash']))
    
    # Social Security to cash
    if 'SS Benefits' in year_data and year_data['SS Benefits'] > 1000:
        sources.append("Social Security")
        targets.append("Cash/Spending")
        values.append(float(year_data['SS Benefits']))
    
    # Cash to expenses
    if 'Expenses' in year_data and year_data['Expenses'] > 1000:
        sources.append("Cash/Spending")
        targets.append("Living Expenses")
        values.append(float(year_data['Expenses']))
    
    # Cash to healthcare
    if 'Healthcare Cost' in year_data and year_data['Healthcare Cost'] > 1000:
        sources.append("Cash/Spending")
        targets.append("Healthcare")
        values.append(float(year_data['Healthcare Cost']))
    
    # Cash to federal taxes
    if federal_tax > 1000:
        sources.append("Cash/Spending")
        targets.append("Federal Income Tax")
        values.append(federal_tax)
    
    # Cash to state taxes
    if state_tax > 1000:
        sources.append("Cash/Spending")
        targets.append("State Income Tax")
        values.append(state_tax)
    
    # Roth conversions
    if 'Trad→\nRoth' in year_data and year_data['Trad→\nRoth'] > 1000:
        sources.append("Traditional IRA/401(k)")
        targets.append("Roth Conversion")
        values.append(float(year_data['Trad→\nRoth']))
    
    # RMDs to brokerage
    if 'Trad→\nBrok' in year_data and year_data['Trad→\nBrok'] > 1000:
        sources.append("Traditional IRA/401(k)")
        targets.append("Brokerage Account")
        values.append(float(year_data['Trad→\nBrok']))
    
    # DAF contributions from brokerage
    if 'DAF Contribution' in year_data and year_data['DAF Contribution'] > 1000:
        sources.append("Brokerage Account")
        targets.append("DAF (Charitable)")
        values.append(float(year_data['DAF Contribution']))
    
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
        "Cash/Spending": "rgba(152, 223, 138, 0.8)",
        "Social Security": "rgba(23, 190, 207, 0.8)"
    }
    
    target_colors = {
        "Traditional 401(k)/IRA": "rgba(214, 39, 40, 0.6)",
        "Roth IRA/401(k)": "rgba(148, 103, 189, 0.6)",
        "Brokerage Account": "rgba(255, 187, 120, 0.6)",
        "Cash/Savings": "rgba(152, 223, 138, 0.6)",
        "Cash/Spending": "rgba(152, 223, 138, 0.6)",
        "Living Expenses": "rgba(31, 119, 180, 0.6)",
        "Healthcare": "rgba(255, 127, 14, 0.6)",
        "Roth Conversion": "rgba(148, 103, 189, 0.6)",
        "RMD → Brokerage": "rgba(255, 187, 120, 0.6)",
        "Traditional 401(k)": "rgba(214, 39, 40, 0.6)",
        "DAF (Charitable)": "rgba(140, 86, 75, 0.6)",
        "Payroll Taxes": "rgba(227, 119, 194, 0.6)",
        "Federal Income Tax": "rgba(188, 189, 34, 0.6)",
        "State Income Tax": "rgba(23, 190, 207, 0.6)"
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
# Tax Analytics Helper Functions
# ---------------------------------------------------------------------------

def prepare_tax_analytics_data(strategy_df: pd.DataFrame, phase: str) -> dict:
    """
    Extract and calculate all tax metrics from strategy DataFrame.
    
    Args:
        strategy_df: Strategy DataFrame with financial projections
        phase: "accumulation" or "withdrawal"
    
    Returns:
        Dictionary with calculated tax metrics and insights
    """
    if strategy_df.empty:
        return {}
    
    # Calculate total income by source
    income_sources = {}
    if phase == "accumulation":
        if 'Wages' in strategy_df.columns:
            income_sources['Wages'] = strategy_df['Wages'].sum()
    else:  # withdrawal
        if 'Wages' in strategy_df.columns:
            income_sources['Wages'] = strategy_df['Wages'].sum()
        if 'SS Benefits' in strategy_df.columns:
            income_sources['Social Security'] = strategy_df['SS Benefits'].sum()
        if 'Trad→\nCash' in strategy_df.columns:
            income_sources['Traditional Withdrawals'] = strategy_df['Trad→\nCash'].sum()
        if 'Roth→\nCash' in strategy_df.columns:
            income_sources['Roth Withdrawals'] = strategy_df['Roth→\nCash'].sum()
        if 'Brok→\nCash' in strategy_df.columns:
            income_sources['Brokerage Withdrawals'] = strategy_df['Brok→\nCash'].sum()
        if 'RMD' in strategy_df.columns:
            income_sources['RMDs'] = strategy_df['RMD'].sum()
    
    # Roth conversions (not spendable income but important for tax planning)
    roth_conversion_col = 'Trad→\nRoth' if 'Trad→\nRoth' in strategy_df.columns else 'Roth Conversion'
    if roth_conversion_col in strategy_df.columns:
        income_sources['Roth Conversions'] = strategy_df[roth_conversion_col].sum()
    
    # Calculate total taxes by type
    tax_breakdown = {}
    if 'Federal Tax' in strategy_df.columns:
        tax_breakdown['Federal Income Tax'] = strategy_df['Federal Tax'].sum()
    if 'State Tax' in strategy_df.columns:
        tax_breakdown['State Income Tax'] = strategy_df['State Tax'].sum()
    if 'IRMAA Penalty' in strategy_df.columns:
        tax_breakdown['IRMAA Penalties'] = strategy_df['IRMAA Penalty'].sum()
    if 'Wages→\nPayroll' in strategy_df.columns:
        tax_breakdown['Payroll Taxes (FICA)'] = strategy_df['Wages→\nPayroll'].sum()
    
    # Calculate Long-Term Capital Gains Tax
    # LTCG is taxed at 0%, 15%, or 20% depending on income
    # Now uses actual LTCG amounts from cost basis tracking
    if 'LTCG Harvested' in strategy_df.columns:
        total_ltcg = strategy_df['LTCG Harvested'].sum()
        # Calculate LTCG tax using actual LTCG amounts (not 60/40 assumption)
        estimated_ltcg_tax = 0
        for idx, row in strategy_df.iterrows():
            ltcg = row.get('LTCG Harvested', 0)
            agi = row.get('AGI', 0)
            # Simplified LTCG tax calculation
            # 0% up to ~$89k (MFJ), 15% up to ~$553k, 20% above
            if agi < 89075:
                ltcg_tax = 0  # 0% bracket
            elif agi < 553850:
                ltcg_tax = ltcg * 0.15  # 15% bracket
            else:
                ltcg_tax = ltcg * 0.20  # 20% bracket
            estimated_ltcg_tax += ltcg_tax
        
        if estimated_ltcg_tax > 0:
            tax_breakdown['Long-Term Capital Gains Tax'] = estimated_ltcg_tax
    
    # Add cost basis insights if available
    cost_basis_insights = {}
    if 'Basis Returned' in strategy_df.columns:
        total_basis_returned = strategy_df['Basis Returned'].sum()
        if total_basis_returned > 0:
            cost_basis_insights['total_basis_returned'] = total_basis_returned
    
    if 'Brokerage LTCG Ratio' in strategy_df.columns:
        # Calculate average LTCG ratio (weighted by withdrawals)
        ltcg_ratios = strategy_df[strategy_df['Brokerage LTCG Ratio'] > 0]['Brokerage LTCG Ratio']
        if not ltcg_ratios.empty:
            cost_basis_insights['avg_ltcg_ratio'] = ltcg_ratios.mean()
            cost_basis_insights['min_ltcg_ratio'] = ltcg_ratios.min()
            cost_basis_insights['max_ltcg_ratio'] = ltcg_ratios.max()
    
    # Calculate NIIT if available (Net Investment Income Tax)
    # NIIT is 3.8% on investment income above thresholds ($250k MFJ)
    if 'LTCG Harvested' in strategy_df.columns and 'MAGI' in strategy_df.columns:
        niit_threshold = 250000  # MFJ threshold
        total_niit = 0
        for idx, row in strategy_df.iterrows():
            magi = row.get('MAGI', 0)
            ltcg = row.get('LTCG Harvested', 0)
            if magi > niit_threshold:
                # NIIT applies to lesser of: NII or (MAGI - threshold)
                excess_magi = magi - niit_threshold
                niit_base = min(ltcg, excess_magi)
                total_niit += niit_base * 0.038
        
        if total_niit > 0:
            tax_breakdown['Net Investment Income Tax (NIIT)'] = total_niit
    
    # Calculate effective tax rates
    total_income = sum(v for k, v in income_sources.items() if k != 'Roth Conversions')
    total_taxes = sum(tax_breakdown.values())
    avg_effective_rate = (total_taxes / total_income * 100) if total_income > 0 else 0
    
    # Calculate marginal rates using actual tax bracket data from CSV files
    marginal_rates = []
    effective_rates = []
    
    # Import tax bracket loading function
    from load_data import get_income_tax_brackets
    from config import get_config_manager
    
    # Get filing status from config
    config_mgr = get_config_manager()
    filing_status = config_mgr.get("tax_info", "filing_status", "married_filing_jointly")
    
    for idx, row in strategy_df.iterrows():
        year = row.get('Year', 2026)
        
        # Calculate taxable income FIRST (needed for both marginal and effective rates)
        # IMPORTANT: Marginal rate is based on TAXABLE INCOME, not AGI
        # Taxable Income includes:
        # - Roth Conversions (fully taxable)
        # - Wages (after 401k contributions)
        # - Traditional IRA withdrawals (fully taxable)
        # - RMDs (fully taxable)
        # - LTCG from brokerage (taxable gains only)
        # - Roth conversions (fully taxable)
        # - Taxable portion of Social Security
        # - Less: DAF contributions (deductible)
        # - Less: Standard deduction
        
        # The simplest and most accurate approach is to use AGI directly
        # AGI already includes all income sources (wages, conversions, withdrawals, etc.)
        agi = row.get('AGI', 0)
        daf = row.get('DAF Contribution', 0)
        
        # Get standard deduction for this year
        from load_data import get_std_deduction
        try:
            std_ded_df = get_std_deduction(year, filing_status)
            if not std_ded_df.empty:
                std_ded = float(std_ded_df['deduction'].iloc[0])
            else:
                std_ded = 24800  # Fallback
        except:
            # Fallback to approximate standard deduction for MFJ
            std_ded = 24800  # Approximate for married filing jointly
        
        # Taxable Income = AGI - Standard Deduction - DAF (if itemizing)
        # Note: DAF only provides benefit if itemized deductions exceed standard deduction
        # For simplicity, subtract both (this may slightly overstate the deduction benefit)
        taxable_income = agi - std_ded - daf
        
        # Ensure taxable income is not negative
        taxable_income = max(0, taxable_income)
        
        # Calculate year taxes (actual taxes + IRMAA surcharges)
        # IRMAA is effectively a tax on high income, so include it in effective rate
        # Do NOT include ACA premiums as those are insurance costs, not taxes
        year_taxes = (row.get('Federal Tax', 0) +
                     row.get('State Tax', 0) +
                     row.get('IRMAA Penalty', 0))
        
        # Effective rate for this year = (taxes + IRMAA) / taxable income
        eff_rate = (year_taxes / taxable_income * 100) if taxable_income > 0 else 0
        effective_rates.append(eff_rate)
        
        # Marginal rate calculation using actual tax brackets from CSV
        marg_rate = 0
        
        try:
            # Load tax brackets for this year
            tax_brackets_df = get_income_tax_brackets(year)
            
            # Filter for the correct filing status
            brackets = tax_brackets_df[tax_brackets_df['filing_status'] == filing_status]
            
            if not brackets.empty:
                # Find the bracket that contains this taxable income
                # Sort by lower bound to ensure we check in order
                brackets = brackets.sort_values('lower')
                
                for _, bracket in brackets.iterrows():
                    if bracket['lower'] <= taxable_income <= bracket['upper']:
                        marg_rate = bracket['rate'] * 100  # Convert to percentage
                        break
                
                # If taxable income exceeds all brackets, use the highest rate
                if marg_rate == 0 and taxable_income > 0:
                    marg_rate = brackets['rate'].max() * 100
            else:
                # Fallback if no brackets found for filing status
                marg_rate = 0
                
        except Exception as e:
            # Fallback to 0 if there's any error loading brackets
            st.warning(f"Could not load tax brackets for year {year}: {e}")
            marg_rate = 0
        
        marginal_rates.append(marg_rate)
    
    # Add rates to dataframe for charting
    strategy_df_copy = strategy_df.copy()
    strategy_df_copy['Marginal Rate'] = marginal_rates
    strategy_df_copy['Effective Rate'] = effective_rates
    
    # Generate tax optimization insights
    insights = generate_tax_insights(strategy_df, phase)
    
    return {
        'income_sources': income_sources,
        'tax_breakdown': tax_breakdown,
        'total_income': total_income,
        'total_taxes': total_taxes,
        'avg_effective_rate': avg_effective_rate,
        'strategy_df_with_rates': strategy_df_copy,
        'insights': insights,
        'cost_basis_insights': cost_basis_insights
    }


def generate_tax_insights(strategy_df: pd.DataFrame, phase: str) -> list:
    """
    Analyze strategy and generate actionable tax insights.
    
    Args:
        strategy_df: Strategy DataFrame
        phase: "accumulation" or "withdrawal"
    
    Returns:
        List of insight strings
    """
    insights = []
    
    if strategy_df.empty:
        return insights
    
    # Check for high effective tax rate years
    for idx, row in strategy_df.iterrows():
        year = row.get('Year', 0)
        federal_tax = row.get('Federal Tax', 0)
        agi = row.get('AGI', 0)
        
        if agi > 0:
            eff_rate = (federal_tax / agi * 100)
            if eff_rate > 25:
                insights.append(f"⚠️ **Year {year}**: High effective tax rate ({eff_rate:.1f}%). Consider tax-loss harvesting or timing income.")
    
    # Check for IRMAA penalties
    if 'IRMAA Penalty' in strategy_df.columns:
        irmaa_years = strategy_df[strategy_df['IRMAA Penalty'] > 0]
        if not irmaa_years.empty:
            total_irmaa = irmaa_years['IRMAA Penalty'].sum()
            insights.append(f"💊 **IRMAA Impact**: ${total_irmaa:,.0f} in Medicare surcharges over {len(irmaa_years)} years. Consider managing MAGI to avoid IRMAA brackets.")
    
    # Check for Roth conversion opportunities
    roth_conv_col = 'Trad→\nRoth' if 'Trad→\nRoth' in strategy_df.columns else 'Roth Conversion'
    if roth_conv_col in strategy_df.columns:
        low_income_years = strategy_df[strategy_df['AGI'] < 100000]
        if not low_income_years.empty and low_income_years[roth_conv_col].sum() < 50000:
            insights.append(f"💡 **Roth Opportunity**: {len(low_income_years)} years with AGI < $100k. Consider increasing Roth conversions in these low-tax years.")
    
    # Check for state tax burden
    if 'State Tax' in strategy_df.columns:
        total_state = strategy_df['State Tax'].sum()
        total_federal = strategy_df['Federal Tax'].sum() if 'Federal Tax' in strategy_df.columns else 0
        if total_state > 0 and total_federal > 0:
            state_pct = (total_state / (total_state + total_federal) * 100)
            if state_pct > 15:
                insights.append(f"🏛️ **State Tax Burden**: State taxes are {state_pct:.1f}% of total tax burden (${total_state:,.0f}). Consider state tax planning strategies.")
    
    # Check for tax bracket optimization
    if 'AGI' in strategy_df.columns:
        # Check if AGI is consistently near bracket thresholds
        bracket_thresholds = [89075, 190750, 364200]  # MFJ 2024 thresholds
        for threshold in bracket_thresholds:
            near_threshold = strategy_df[(strategy_df['AGI'] > threshold - 10000) & (strategy_df['AGI'] < threshold + 10000)]
            if not near_threshold.empty:
                insights.append(f"📊 **Bracket Management**: {len(near_threshold)} years near ${threshold:,.0f} bracket threshold. Small adjustments could optimize tax burden.")
    
    # Check for LTCG harvesting opportunities
    if 'LTCG Harvested' in strategy_df.columns and 'AGI' in strategy_df.columns:
        # Find years with low AGI where more LTCG could be harvested at 0%
        ltcg_0_percent_threshold = 89075  # MFJ 2024 threshold for 0% LTCG
        low_agi_years = strategy_df[strategy_df['AGI'] < ltcg_0_percent_threshold]
        if not low_agi_years.empty:
            total_ltcg_harvested = low_agi_years['LTCG Harvested'].sum()
            avg_agi = low_agi_years['AGI'].mean()
            if total_ltcg_harvested > 0:
                insights.append(f"💎 **LTCG Harvesting**: {len(low_agi_years)} years with AGI < ${ltcg_0_percent_threshold:,.0f} (0% LTCG bracket). Total LTCG harvested: ${total_ltcg_harvested:,.0f} at 0% tax rate. Excellent tax-free gains!")
            else:
                insights.append(f"💎 **LTCG Opportunity**: {len(low_agi_years)} years with low AGI (avg ${avg_agi:,.0f}). Consider harvesting long-term capital gains at 0% tax rate in these years.")
    
    return insights


def render_tax_overview(tax_data: dict) -> None:
    """Render tax overview with key metrics and summary charts."""
    st.markdown("### 📊 Tax Overview")
    st.caption("Comprehensive tax analysis across your financial strategy")
    
    # Metric cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Taxes Paid",
            f"${tax_data['total_taxes']:,.0f}",
            help="Sum of all federal, state, and other taxes over planning period"
        )
    
    with col2:
        st.metric(
            "Average Effective Rate",
            f"{tax_data['avg_effective_rate']:.1f}%",
            help="Total taxes divided by total income"
        )
    
    with col3:
        total_irmaa = tax_data['tax_breakdown'].get('IRMAA Penalties', 0)
        st.metric(
            "IRMAA Penalties",
            f"${total_irmaa:,.0f}",
            help="Total Medicare surcharges due to high income"
        )
    
    with col4:
        # Tax efficiency score (lower is better)
        tax_efficiency = 100 - min(tax_data['avg_effective_rate'], 100)
        st.metric(
            "Tax Efficiency Score",
            f"{tax_efficiency:.0f}/100",
            help="Higher score = more tax-efficient strategy"
        )
    
    st.markdown("---")
    
    # Combined tax burden visualization
    st.markdown("#### Tax Burden Over Time")
    
    df = tax_data['strategy_df_with_rates']
    
    fig = go.Figure()
    
    # Add stacked bars for different tax types
    if 'Federal Tax' in df.columns:
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=df['Federal Tax'],
            name='Federal Tax',
            marker_color='#ff4b4b',
            hovertemplate='Year %{x}<br>Federal: $%{y:,.0f}<extra></extra>'
        ))
    
    if 'State Tax' in df.columns:
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=df['State Tax'],
            name='State Tax',
            marker_color='#ffa500',
            hovertemplate='Year %{x}<br>State: $%{y:,.0f}<extra></extra>'
        ))
    
    if 'IRMAA Penalty' in df.columns:
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=df['IRMAA Penalty'],
            name='IRMAA',
            marker_color='#AA96DA',
            hovertemplate='Year %{x}<br>IRMAA: $%{y:,.0f}<extra></extra>'
        ))
    
    if 'Wages→\nPayroll' in df.columns:
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=df['Wages→\nPayroll'],
            name='Payroll (FICA)',
            marker_color='#4c78a8',
            hovertemplate='Year %{x}<br>Payroll: $%{y:,.0f}<extra></extra>'
        ))
    
    # Add LTCG tax if available
    if 'LTCG Harvested' in df.columns:
        ltcg_tax_by_year = []
        for idx, row in df.iterrows():
            ltcg = row.get('LTCG Harvested', 0)
            agi = row.get('AGI', 0)
            if agi < 89075:
                ltcg_tax = 0
            elif agi < 553850:
                ltcg_tax = ltcg * 0.15
            else:
                ltcg_tax = ltcg * 0.20
            ltcg_tax_by_year.append(ltcg_tax)
        
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=ltcg_tax_by_year,
            name='Capital Gains Tax',
            marker_color='#F38181',
            hovertemplate='Year %{x}<br>Cap Gains: $%{y:,.0f}<extra></extra>'
        ))
    
    fig.update_layout(
        barmode='stack',
        title='Annual Tax Burden by Type',
        xaxis_title='Year',
        yaxis_title='Tax Amount ($)',
        hovermode='x unified',
        height=400,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display cost basis insights if available
    cost_basis_insights = tax_data.get('cost_basis_insights', {})
    if cost_basis_insights:
        st.markdown("---")
        st.markdown("#### 📊 Cost Basis Tracking Insights")
        st.caption("Actual cost basis tracking replaces the traditional 60/40 LTCG assumption")
        
        cb_col1, cb_col2, cb_col3 = st.columns(3)
        
        with cb_col1:
            total_basis = cost_basis_insights.get('total_basis_returned', 0)
            if total_basis > 0:
                st.metric(
                    "Total Basis Returned",
                    f"${total_basis:,.0f}",
                    help="Tax-free return of original investment cost basis from brokerage withdrawals"
                )
        
        with cb_col2:
            avg_ltcg_ratio = cost_basis_insights.get('avg_ltcg_ratio', 0)
            if avg_ltcg_ratio > 0:
                st.metric(
                    "Avg LTCG Ratio",
                    f"{avg_ltcg_ratio*100:.1f}%",
                    help="Average percentage of brokerage withdrawals that are taxable long-term capital gains"
                )
        
        with cb_col3:
            min_ltcg = cost_basis_insights.get('min_ltcg_ratio', 0)
            max_ltcg = cost_basis_insights.get('max_ltcg_ratio', 0)
            if min_ltcg > 0 or max_ltcg > 0:
                st.metric(
                    "LTCG Ratio Range",
                    f"{min_ltcg*100:.1f}% - {max_ltcg*100:.1f}%",
                    help="Range of LTCG ratios across all years with brokerage withdrawals"
                )
        
        if avg_ltcg_ratio > 0:
            # Compare to 60/40 assumption
            assumed_ltcg = 0.40
            difference = (avg_ltcg_ratio - assumed_ltcg) * 100
            if abs(difference) > 5:
                comparison_text = "higher" if difference > 0 else "lower"
                st.info(
                    f"💡 **Cost Basis Insight**: Your actual LTCG ratio ({avg_ltcg_ratio*100:.1f}%) is "
                    f"{abs(difference):.1f}% {comparison_text} than the traditional 60/40 assumption (40% LTCG). "
                    f"This {'increases' if difference > 0 else 'reduces'} your actual tax burden on brokerage withdrawals."
                )


def render_income_sources_chart(tax_data: dict, phase: str) -> None:
    """Render detailed income sources breakdown."""
    st.markdown("### 💵 Income Sources")
    st.caption("Breakdown of all income sources over the planning period")
    
    df = tax_data['strategy_df_with_rates']
    
    # Create stacked bar chart
    fig = go.Figure()
    
    if phase == "accumulation":
        if 'Wages' in df.columns:
            fig.add_trace(go.Bar(
                x=df['Year'],
                y=df['Wages'],
                name='Wages',
                marker_color='#21c354',
                hovertemplate='Year %{x}<br>Wages: $%{y:,.0f}<extra></extra>'
            ))
    else:  # withdrawal
        if 'Wages' in df.columns and df['Wages'].sum() > 0:
            fig.add_trace(go.Bar(
                x=df['Year'],
                y=df['Wages'],
                name='Wages',
                marker_color='#21c354',
                hovertemplate='Year %{x}<br>Wages: $%{y:,.0f}<extra></extra>'
            ))
        
        if 'SS Benefits' in df.columns:
            fig.add_trace(go.Bar(
                x=df['Year'],
                y=df['SS Benefits'],
                name='Social Security',
                marker_color='#95E1D3',
                hovertemplate='Year %{x}<br>SS: $%{y:,.0f}<extra></extra>'
            ))
        
        if 'Trad→\nCash' in df.columns:
            fig.add_trace(go.Bar(
                x=df['Year'],
                y=df['Trad→\nCash'],
                name='Traditional Withdrawals',
                marker_color='#ff4b4b',
                hovertemplate='Year %{x}<br>Traditional: $%{y:,.0f}<extra></extra>'
            ))
        
        if 'Roth→\nCash' in df.columns:
            fig.add_trace(go.Bar(
                x=df['Year'],
                y=df['Roth→\nCash'],
                name='Roth Withdrawals',
                marker_color='#AA96DA',
                hovertemplate='Year %{x}<br>Roth: $%{y:,.0f}<extra></extra>'
            ))
        
        if 'Brok→\nCash' in df.columns:
            fig.add_trace(go.Bar(
                x=df['Year'],
                y=df['Brok→\nCash'],
                name='Brokerage Withdrawals',
                marker_color='#ffa500',
                hovertemplate='Year %{x}<br>Brokerage: $%{y:,.0f}<extra></extra>'
            ))
        
        if 'RMD' in df.columns:
            fig.add_trace(go.Bar(
                x=df['Year'],
                y=df['RMD'],
                name='RMDs',
                marker_color='#FF6B9D',
                hovertemplate='Year %{x}<br>RMD: $%{y:,.0f}<extra></extra>'
            ))
    
    fig.update_layout(
        barmode='stack',
        title='Annual Income by Source',
        xaxis_title='Year',
        yaxis_title='Income Amount ($)',
        hovermode='x unified',
        height=450,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Income composition pie chart
    st.markdown("#### Average Income Composition")
    income_sources = tax_data['income_sources']
    # Exclude Roth conversions from income composition
    income_for_pie = {k: v for k, v in income_sources.items() if k != 'Roth Conversions' and v > 0}
    
    if income_for_pie:
        fig_pie = go.Figure(data=[go.Pie(
            labels=list(income_for_pie.keys()),
            values=list(income_for_pie.values()),
            hole=0.3,
            marker=dict(colors=['#21c354', '#95E1D3', '#ff4b4b', '#AA96DA', '#ffa500', '#FF6B9D']),
            hovertemplate='%{label}<br>$%{value:,.0f}<br>%{percent}<extra></extra>'
        )])
        
        fig_pie.update_layout(
            title='Income Source Distribution',
            height=350
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)


def render_tax_breakdown_chart(tax_data: dict) -> None:
    """Render detailed tax breakdown."""
    st.markdown("### 💰 Tax Breakdown")
    st.caption("Detailed breakdown of all tax types over the planning period")
    
    df = tax_data['strategy_df_with_rates']
    
    # Stacked bar chart (same as overview but larger)
    fig = go.Figure()
    
    if 'Federal Tax' in df.columns:
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=df['Federal Tax'],
            name='Federal Income Tax',
            marker_color='#ff4b4b',
            hovertemplate='Year %{x}<br>Federal: $%{y:,.0f}<extra></extra>'
        ))
    
    if 'State Tax' in df.columns:
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=df['State Tax'],
            name='State Income Tax',
            marker_color='#ffa500',
            hovertemplate='Year %{x}<br>State: $%{y:,.0f}<extra></extra>'
        ))
    
    if 'IRMAA Penalty' in df.columns:
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=df['IRMAA Penalty'],
            name='IRMAA (Medicare Surcharges)',
            marker_color='#AA96DA',
            hovertemplate='Year %{x}<br>IRMAA: $%{y:,.0f}<extra></extra>'
        ))
    
    if 'Wages→\nPayroll' in df.columns:
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=df['Wages→\nPayroll'],
            name='Payroll Taxes (FICA)',
            marker_color='#4c78a8',
            hovertemplate='Year %{x}<br>Payroll: $%{y:,.0f}<extra></extra>'
        ))
    
    # Add LTCG tax if available
    if 'LTCG Harvested' in df.columns:
        ltcg_tax_by_year = []
        for idx, row in df.iterrows():
            ltcg = row.get('LTCG Harvested', 0)
            agi = row.get('AGI', 0)
            if agi < 89075:
                ltcg_tax = 0
            elif agi < 553850:
                ltcg_tax = ltcg * 0.15
            else:
                ltcg_tax = ltcg * 0.20
            ltcg_tax_by_year.append(ltcg_tax)
        
        fig.add_trace(go.Bar(
            x=df['Year'],
            y=ltcg_tax_by_year,
            name='Capital Gains Tax',
            marker_color='#F38181',
            hovertemplate='Year %{x}<br>Cap Gains: $%{y:,.0f}<extra></extra>'
        ))
    
    fig.update_layout(
        barmode='stack',
        title='Annual Tax Burden by Type',
        xaxis_title='Year',
        yaxis_title='Tax Amount ($)',
        hovermode='x unified',
        height=500,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Tax composition pie chart
    st.markdown("#### Tax Type Distribution")
    tax_breakdown = tax_data['tax_breakdown']
    
    if tax_breakdown:
        fig_pie = go.Figure(data=[go.Pie(
            labels=list(tax_breakdown.keys()),
            values=list(tax_breakdown.values()),
            hole=0.3,
            marker=dict(colors=['#ff4b4b', '#ffa500', '#AA96DA', '#4c78a8', '#F38181']),
            hovertemplate='%{label}<br>$%{value:,.0f}<br>%{percent}<extra></extra>'
        )])
        
        fig_pie.update_layout(
            title='Total Tax Distribution',
            height=350
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)


def render_tax_rates_chart(tax_data: dict) -> None:
    """Render marginal and effective tax rate analysis."""
    st.markdown("### 📈 Tax Rates Over Time")
    st.caption("Marginal and effective tax rates throughout your financial strategy")
    
    df = tax_data['strategy_df_with_rates']
    
    # Dual-axis line chart
    fig = go.Figure()
    
    # Marginal rate
    fig.add_trace(go.Scatter(
        x=df['Year'],
        y=df['Marginal Rate'],
        name='Marginal Tax Rate',
        mode='lines+markers',
        line=dict(color='#ff4b4b', width=3),
        marker=dict(size=8),
        hovertemplate='Year %{x}<br>Marginal: %{y:.1f}%<extra></extra>'
    ))
    
    # Effective rate
    fig.add_trace(go.Scatter(
        x=df['Year'],
        y=df['Effective Rate'],
        name='Effective Tax Rate',
        mode='lines+markers',
        line=dict(color='#4c78a8', width=3),
        marker=dict(size=8),
        hovertemplate='Year %{x}<br>Effective: %{y:.1f}%<extra></extra>'
    ))
    
    fig.update_layout(
        title='Marginal vs Effective Tax Rates',
        xaxis_title='Year',
        yaxis_title='Tax Rate (%)',
        hovermode='x unified',
        height=450,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Interactive Annual Tax Analysis
    st.markdown("#### 🔍 Annual Tax Analysis")
    st.caption("Select a year to see detailed tax breakdown and explanation")
    
    # Year selector
    years = df['Year'].tolist()
    selected_year = st.selectbox(
        "Select Year",
        years,
        index=0,
        key="tax_analysis_year_selector"
    )
    
    # Get data for selected year
    year_data = df[df['Year'] == selected_year].iloc[0]
    
    # Display key metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Age",
            year_data['Age'],
            help="Your age(s) in this year"
        )
    
    with col2:
        marginal_rate = year_data['Marginal Rate']
        st.metric(
            "Marginal Rate",
            f"{marginal_rate:.1f}%",
            help="Tax rate on your last dollar of income"
        )
    
    with col3:
        effective_rate = year_data['Effective Rate']
        st.metric(
            "Effective Rate",
            f"{effective_rate:.1f}%",
            help="Average tax rate across all income"
        )
    
    with col4:
        rate_diff = marginal_rate - effective_rate
        st.metric(
            "Rate Difference",
            f"{rate_diff:.1f}pp",
            help="Marginal minus Effective rate (percentage points)"
        )
    
    # Detailed analysis
    st.markdown("##### 📊 Tax Breakdown")
    
    # Get income and tax details
    roth_conv = year_data.get('Roth Conversion', 0)
    trad_withdrawal = year_data.get('Traditional Withdrawal', 0)
    ltcg = year_data.get('LTCG Harvested', 0)
    ss_benefits = year_data.get('SS Benefits', 0)
    rmd = year_data.get('RMD', 0)
    daf = year_data.get('DAF Contribution', 0)
    
    fed_tax = year_data.get('Federal Tax', 0)
    state_tax = year_data.get('State Tax', 0)
    irmaa = year_data.get('IRMAA Penalty', 0)
    
    # Calculate taxable income (same logic as in prepare_tax_analytics_data)
    trad_income = max(trad_withdrawal, rmd)
    taxable_ss = ss_benefits * 0.85 if ss_benefits > 0 else 0
    
    # Get actual standard deduction from CSV for this year
    from load_data import get_std_deduction
    from config import get_config_manager
    
    config_mgr = get_config_manager()
    filing_status = config_mgr.get("tax_info", "filing_status", "married_filing_jointly")
    
    try:
        std_ded_df = get_std_deduction(selected_year, filing_status)
        if not std_ded_df.empty:
            std_ded = float(std_ded_df['deduction'].iloc[0])
        else:
            std_ded = 33500  # Fallback for MFJ
    except:
        std_ded = 33500  # Fallback for MFJ
    
    # Get property tax from config
    try:
        property_tax = float(config_mgr.get("expenses", "living_expenses", {}).get("property_tax", 0))
    except:
        property_tax = 0.0
    
    # Calculate itemized deductions (DAF + SALT)
    # SALT = State Tax + Property Tax, capped at $10,000
    salt_deduction = min(10000.0, state_tax + property_tax)
    total_itemized = daf + salt_deduction
    
    # Determine actual deduction used
    # If itemized > standard, use itemized; otherwise use standard
    if total_itemized > std_ded:
        actual_deduction = total_itemized
        using_itemized = True
        itemized_benefit = total_itemized - std_ded
    else:
        actual_deduction = std_ded
        using_itemized = False
        itemized_benefit = 0
    
    # Calculate taxable income: AGI - deduction
    # Use AGI from the data (which includes wages, conversions, withdrawals, etc.)
    agi = year_data.get('AGI', 0)
    taxable_income = max(0, agi - actual_deduction)
    
    # Income sources
    income_col1, income_col2 = st.columns(2)
    
    with income_col1:
        st.markdown("**Income Sources:**")
        
        # Get wages from year data
        wages = year_data.get('Wages', 0)
        if wages > 0:
            st.write(f"• Wages (after 401k): ${wages:,.0f}")
        
        if roth_conv > 0:
            st.write(f"• Roth Conversion: ${roth_conv:,.0f}")
        if trad_income > 0:
            st.write(f"• Traditional/RMD: ${trad_income:,.0f}")
        if ltcg > 0:
            st.write(f"• Long-Term Cap Gains: ${ltcg:,.0f}")
        if ss_benefits > 0:
            st.write(f"• Social Security: ${ss_benefits:,.0f}")
            st.write(f"  (85% taxable: ${taxable_ss:,.0f})")
        
        # Show total AGI
        st.write(f"• **Total AGI: ${agi:,.0f}**")
    
    with income_col2:
        st.markdown("**Deductions & Taxes:**")
        if using_itemized:
            st.write(f"• **Itemized Deductions: ${actual_deduction:,.0f}**")
            if daf > 0:
                st.write(f"  - DAF: ${daf:,.0f}")
            st.write(f"  - SALT (State+Property, capped): ${salt_deduction:,.0f}")
            st.write(f"  - Benefit over standard: ${itemized_benefit:,.0f}")
        else:
            st.write(f"• **Standard Deduction: ${std_ded:,.0f}**")
            if daf > 0 or salt_deduction > 0:
                st.write(f"  (Itemized ${total_itemized:,.0f} < Standard)")
        st.write(f"• **Taxable Income: ${taxable_income:,.0f}**")
        st.write(f"• Federal Tax: ${fed_tax:,.0f}")
        st.write(f"• State Tax: ${state_tax:,.0f}")
        if irmaa > 0:
            st.write(f"• IRMAA: ${irmaa:,.0f}")
    
    # Explanation
    st.markdown("##### 💡 Why These Rates?")
    
    # Get actual tax brackets for this year from CSV
    from load_data import get_income_tax_brackets
    try:
        brackets_df = get_income_tax_brackets(selected_year)
        brackets = brackets_df[brackets_df['filing_status'] == filing_status].sort_values('lower')
        
        # Find the bracket that contains this taxable income
        bracket = "10%"
        bracket_floor = 0
        bracket_desc = "$0 - $24,800"
        
        for _, row in brackets.iterrows():
            lower = float(row['lower'])
            upper = float(row['upper'])
            rate = float(row['rate'])
            
            if taxable_income >= lower:
                bracket = f"{rate*100:.1f}%"
                bracket_floor = lower
                if upper == float('inf'):
                    bracket_desc = f"${lower:,.0f}+"
                else:
                    bracket_desc = f"${lower:,.0f} - ${upper:,.0f}"
    except Exception as e:
        # Fallback to 2026 brackets if CSV load fails
        if taxable_income > 768700:
            bracket = "37%"
            bracket_floor = 768700
            bracket_desc = "$768,700+"
        elif taxable_income > 512450:
            bracket = "35%"
            bracket_floor = 512450
            bracket_desc = "$512,450 - $768,700"
        elif taxable_income > 403550:
            bracket = "32%"
            bracket_floor = 403550
            bracket_desc = "$403,550 - $512,450"
        elif taxable_income > 211400:
            bracket = "24%"
            bracket_floor = 211400
            bracket_desc = "$211,400 - $403,550"
        elif taxable_income > 100800:
            bracket = "22%"
            bracket_floor = 100800
            bracket_desc = "$100,800 - $211,400"
        elif taxable_income > 24800:
            bracket = "12%"
            bracket_floor = 24800
            bracket_desc = "$24,800 - $100,800"
        else:
            bracket = "10%"
            bracket_floor = 0
            bracket_desc = "$0 - $24,800"
    
    # Format numbers for display
    taxable_income_fmt = f"${taxable_income:,.0f}"
    into_bracket_fmt = f"${taxable_income - bracket_floor:,.0f}"
    bracket_floor_fmt = f"${bracket_floor:,.0f}"
    total_taxes_fmt = f"${fed_tax + state_tax + irmaa:,.0f}"
    
    # Build marginal rate explanation
    marginal_pct = f"{marginal_rate:.1f}%"
    
    st.info(
        f"**Marginal Rate ({marginal_pct}):** "
        f"Your taxable income of {taxable_income_fmt} "
        f"places you in the **{bracket} bracket** ({bracket_desc}). "
        f"You are {into_bracket_fmt} into this bracket. "
        f"This means your next dollar of income would be taxed at {bracket}."
    )
    
    # Build effective rate explanation
    effective_pct = f"{effective_rate:.1f}%"
    
    st.success(
        f"**Effective Rate ({effective_pct}):** "
        f"This is your average tax rate. "
        f"It's lower than your marginal rate because of progressive taxation - "
        f"the first {bracket_floor_fmt} of income is taxed at lower rates. "
        f"Total taxes ({total_taxes_fmt}) ÷ Taxable Income ({taxable_income_fmt}) = {effective_pct}."
    )


def render_tax_table(tax_data: dict, phase: str) -> None:
    """Render comprehensive year-by-year tax table."""
    st.markdown("### 📋 Year-by-Year Tax Details")
    st.caption("Complete tax data for every year in your strategy")
    
    df = tax_data['strategy_df_with_rates'].copy()
    
    # Select columns based on phase
    if phase == "accumulation":
        display_cols = [
            'Year', 'Age', 'Wages', 'Wages→\nPayroll',
            'AGI', 'Federal Tax', 'State Tax',
            'Marginal Rate', 'Effective Rate'
        ]
    else:  # withdrawal
        display_cols = [
            'Year', 'Age', 'Wages', 'SS Benefits', 'RMD', 'Trad→\nCash', 'Trad→\nBrok',
            'LTCG Harvested', 'Trad→\nRoth', 'AGI',
            'Federal Tax', 'State Tax', 'IRMAA Penalty', 'Marginal Rate', 'Effective Rate'
        ]
    
    # Filter to available columns
    available_cols = [c for c in display_cols if c in df.columns]
    display_df = df[available_cols].copy()
    
    # Format numeric columns
    for col in available_cols:
        if col not in ['Year', 'Age', 'Marginal Rate', 'Effective Rate']:
            display_df[col] = display_df[col].apply(lambda x: f"${x:,.0f}")
        elif col in ['Marginal Rate', 'Effective Rate']:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%")
    
    # Export button
    col1, col2 = st.columns([3, 1])
    with col2:
        # Convert to CSV for download
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Export to CSV",
            data=csv,
            file_name=f"tax_analytics_{phase}.csv",
            mime="text/csv",
            help="Download complete tax data as CSV file"
        )
    
    # Add column configuration with helpful tooltips
    column_config = {
        "Year": st.column_config.NumberColumn("Year", format="%d"),
        "Age": st.column_config.TextColumn("Age"),
        "Wages": st.column_config.TextColumn("Wages", help="W-2 wages (included in AGI)"),
        "SS Benefits": st.column_config.TextColumn("SS Benefits", help="Social Security benefits (partially taxable, included in AGI)"),
        "RMD": st.column_config.TextColumn("RMD", help="Required Minimum Distribution from Traditional IRA/401k (included in AGI)"),
        "Trad→\nCash": st.column_config.TextColumn("Trad→Cash", help="Traditional IRA/401k withdrawal to cash (included in AGI)"),
        "Trad→\nBrok": st.column_config.TextColumn("Trad→Brok", help="Traditional IRA/401k withdrawal to replenish brokerage (included in AGI)"),
        "LTCG Harvested": st.column_config.TextColumn("LTCG", help="Long-term capital gains from brokerage (taxable portion, included in AGI)"),
        "Trad→\nRoth": st.column_config.TextColumn("Roth Conversion", help="Traditional IRA/401k converted to Roth (included in AGI)"),
        "AGI": st.column_config.TextColumn("AGI", help="Adjusted Gross Income = Wages + SS (taxable) + RMD + Trad withdrawals + LTCG + Roth conversions"),
        "Federal Tax": st.column_config.TextColumn("Federal Tax"),
        "State Tax": st.column_config.TextColumn("State Tax"),
        "IRMAA Penalty": st.column_config.TextColumn("IRMAA", help="Medicare surcharge based on MAGI from 2 years ago"),
        "Marginal Rate": st.column_config.TextColumn("Marginal Rate", help="Highest tax bracket that applies to your income"),
        "Effective Rate": st.column_config.TextColumn("Effective Rate", help="Total tax burden as % of income (includes Federal + State + IRMAA + ACA)"),
        "Wages→\nPayroll": st.column_config.TextColumn("Payroll Tax", help="FICA + Medicare + State payroll taxes"),
    }
    
    st.dataframe(
        display_df,
        column_config=column_config,
        hide_index=True,
        use_container_width=True
    )


def render_tax_insights(tax_data: dict) -> None:
    """Render tax optimization insights."""
    insights = tax_data.get('insights', [])
    
    if insights:
        st.markdown("### 💡 Tax Optimization Insights")
        st.caption("Actionable recommendations to optimize your tax strategy")
        
        for insight in insights:
            st.info(insight)
    else:
        st.success("✅ Your tax strategy appears well-optimized! No major concerns identified.")


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

# Sync configuration to session state on page load
config_mgr = get_config_manager()
config_to_session_mappings = {
    "SSI_AGE": ("social_security", "person1_ssi_age"),
    "CONV_TAX_RATE": ("tax_strategy", "max_roth_conversion_tax_rate"),
    "EXPENSE": ("financial_assumptions", "expected_annual_expenses"),
    "EXPENSE_MULTIPLIER": ("financial_assumptions", "years_of_expenses_in_cash"),
    "RATE": ("financial_assumptions", "expected_rate_of_return"),
}

for session_key, (section, config_key) in config_to_session_mappings.items():
    value = config_mgr.get(section, config_key)
    if value is not None:
        st.session_state[session_key] = str(value)

navbar("📋 Strategy")

st.header("📈 Long-Term Financial Strategy")
st.markdown("Comprehensive planning across all life stages with granular flow-of-funds tracking.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Check if accumulation phase has data (peek at strategy to determine options)
# ---------------------------------------------------------------------------
try:
    from strategy import build_accumulation_strategy_display
    # Quick check to see if there's accumulation data
    _temp_accum_df, _ = build_accumulation_strategy_display(
        start_year=curr_year,
        growth_rate=1.06,  # Default values for check
        expense_inflation_rate=0.03,
        person1_name="Person1",
        person2_name="Person2",
    )
    _has_accumulation_data = not _temp_accum_df.empty and len(_temp_accum_df) > 0
except Exception:
    _has_accumulation_data = True  # Default to showing it if check fails

# ---------------------------------------------------------------------------
# Phase toggle - only show accumulation option if there's data
# ---------------------------------------------------------------------------
if _has_accumulation_data:
    phase = st.radio(
        "Planning Phase",
        options=["📈 Accumulation (Pre-Retirement)", "💸 Withdrawal (Distribution)"],
        horizontal=True,
        label_visibility="collapsed",
    )
else:
    # Only show withdrawal option if no accumulation data
    st.info("ℹ️ You are in the retirement/withdrawal phase. No accumulation phase data available.")
    phase = "💸 Withdrawal (Distribution)"
    
st.markdown("---")

# Create tabs with new monthly calendar view, bucket strategy, and tax analytics
long_term_tab, monthly_tab, balances_tab, charts_tab, bucket_tab, tax_tab = st.tabs(
    ["📋 Long-Term Plan", "📅 Monthly Calendar", "💰 Account Balances", "📊 Visualizations", "🪣 Bucket Strategy", "💰 Tax Analytics"]
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
            
            # Enhanced table with state taxes - only show if there are rows
            if not accum_strategy_df.empty and len(accum_strategy_df) > 0:
                st.subheader("📋 Year-by-Year Details")
                display_df_a = accum_strategy_df.copy()
                
                # State tax is now calculated in the strategy engine (strategy.py)
                # No need to add placeholder - it's already in the dataframe
                
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
                    "AGI":            st.column_config.TextColumn("AGI", help="Adjusted Gross Income (after 401k contributions, before itemized deductions)"),
                    "Federal Tax":    st.column_config.TextColumn("Fed Tax"),
                    "State Tax":      st.column_config.TextColumn("State Tax", help=f"Estimated {accum_state} state income tax"),
                    "Cash Balance":   st.column_config.TextColumn("Cash End"),
                }
                st.dataframe(display_df_a, column_config=accum_column_config, hide_index=True, use_container_width=True)
                
                # Life Stage Guide - only show if we have data
                _accum_stages_present = display_df_a['Stage'].unique() if 'Stage' in display_df_a.columns else []
                with st.expander("ℹ️ Life Stage Guide", expanded=False):
                    for _stage_name, _stage_desc in LIFE_STAGE_DESCRIPTIONS.items():
                        if _stage_name in list(_accum_stages_present):
                            st.markdown(f"**{_stage_name}**")
                            st.caption(_stage_desc)
                            st.markdown("---")
            else:
                st.info("ℹ️ No accumulation phase data to display. You may already be in retirement phase.")

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
        
        with bucket_tab:
            st.subheader("🪣 Bucket Strategy Analysis")
            
            try:
                from config import get_config_manager as _get_bucket_cfg
                from bucket_strategy import analyze_portfolio_buckets, load_bucket_config, BucketType, AssetClass, format_bucket_summary
                from load_data import get_latest_portfolio_month_year
                import plotly.graph_objects as go
                
                _bucket_cfg = _get_bucket_cfg()
                _bucket_enabled = _bucket_cfg.get("bucket_strategy", "enabled", False)
                
                if not _bucket_enabled:
                    st.info("""
                    **🪣 Bucket Strategy Not Enabled**
                    
                    The bucket strategy helps manage sequence of returns risk by dividing your portfolio into three buckets:
                    - **Bucket 1 (Safety)**: Cash for near-term expenses
                    - **Bucket 2 (Transition)**: Graduated stock/bond mix
                    - **Bucket 3 (Growth)**: Long-term growth stocks
                    
                    Enable it in the Configuration page to see detailed bucket analysis here.
                    """)
                    st.page_link("pages/2_configuration.py", label="⚙️ Go to Configuration", icon="⚙️")
                else:
                    month, year = get_latest_portfolio_month_year()
                    bucket_config = load_bucket_config(_bucket_cfg)
                    bucket_summary = analyze_portfolio_buckets(month, year, bucket_config)
                    
                    # ============================================================
                    # BUCKET STRATEGY STATUS (moved from Dashboard)
                    # ============================================================
                    st.markdown("#### 📊 Bucket Strategy Status")
                    
                    bucket_col1, bucket_col2, bucket_col3, bucket_col4 = st.columns(4)
                    
                    with bucket_col1:
                        bucket1_current = bucket_summary.bucket_1_value
                        bucket1_target = bucket_summary.bucket_1_target
                        bucket1_pct = (bucket1_current / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                        
                        # Calculate annual need (expenses + taxes)
                        annual_need = bucket_config.annual_expenses + bucket_config.annual_taxes
                        help_text = f"Target: ${bucket1_target:,.0f}\n"
                        help_text += f"= {bucket_config.bucket_1_years} years × ${annual_need:,.0f}/year\n"
                        help_text += f"  (${bucket_config.annual_expenses:,.0f} expenses + ${bucket_config.annual_taxes:,.0f} taxes)"
                        
                        st.metric(
                            "🛡️ Bucket 1 (Safety)",
                            f"${bucket1_current:,.0f}",
                            delta=f"{bucket1_pct:.1f}% of portfolio",
                            help=help_text
                        )
                    
                    with bucket_col2:
                        bucket2_current = bucket_summary.bucket_2_value
                        bucket2_target = bucket_summary.bucket_2_target
                        bucket2_pct = (bucket2_current / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                        
                        # Calculate base target and market adjustment
                        annual_need = bucket_config.annual_expenses + bucket_config.annual_taxes
                        base_bucket2_target = annual_need * bucket_config.bucket_2_years
                        market_adjustment = bucket2_target - base_bucket2_target
                        
                        help_text = f"Base target: ${base_bucket2_target:,.0f}\n"
                        help_text += f"= {bucket_config.bucket_2_years} years × ${annual_need:,.0f}/year\n"
                        help_text += f"  (${bucket_config.annual_expenses:,.0f} expenses + ${bucket_config.annual_taxes:,.0f} taxes)"
                        if market_adjustment != 0:
                            if market_adjustment > 0:
                                help_text += f"\n+ Market adjustment: ${market_adjustment:,.0f} (defensive)"
                            else:
                                help_text += f"\n- Market adjustment: ${abs(market_adjustment):,.0f} (aggressive)"
                        help_text += f"\n= Total target: ${bucket2_target:,.0f}"
                        
                        st.metric(
                            "🔄 Bucket 2 (Transition)",
                            f"${bucket2_current:,.0f}",
                            delta=f"{bucket2_pct:.1f}% of portfolio",
                            help=help_text
                        )
                    
                    with bucket_col3:
                        bucket3_current = bucket_summary.bucket_3_value
                        bucket3_target = bucket_summary.bucket_3_target
                        bucket3_pct = (bucket3_current / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                        
                        st.metric(
                            "🚀 Bucket 3 (Growth)",
                            f"${bucket3_current:,.0f}",
                            delta=f"{bucket3_pct:.1f}% of portfolio",
                            help=f"Target: ${bucket3_target:,.0f} (remaining funds)"
                        )
                    
                    with bucket_col4:
                        # Rebalancing status
                        if bucket_summary.needs_rebalancing:
                            st.error("⚠️ **Rebalancing Needed**")
                            max_drift = max(
                                abs(bucket_summary.get_bucket_drift(BucketType.BUCKET_1_SAFETY)),
                                abs(bucket_summary.get_bucket_drift(BucketType.BUCKET_2_TRANSITION)),
                                abs(bucket_summary.get_bucket_drift(BucketType.BUCKET_3_GROWTH))
                            )
                            st.caption(f"Max drift: {max_drift:.1f}%")
                        else:
                            st.success("✅ **Balanced**")
                            st.caption("All buckets within target range")
                    
                    # Bucket Allocation Visualization
                    st.markdown("#### Bucket Allocation Breakdown")
                    
                    # Create stacked bar chart showing current vs target
                    fig = go.Figure()
                    
                    # Current allocation
                    fig.add_trace(go.Bar(
                        name='Current',
                        x=['Bucket 1<br>(Safety)', 'Bucket 2<br>(Transition)', 'Bucket 3<br>(Growth)'],
                        y=[bucket1_current, bucket2_current, bucket3_current],
                        marker_color=['#21c354', '#ffa500', '#1f77b4'],
                        text=[f'${bucket1_current:,.0f}', f'${bucket2_current:,.0f}', f'${bucket3_current:,.0f}'],
                        textposition='inside',
                        textfont=dict(color='white', size=12),
                        hovertemplate='<b>%{x}</b><br>Current: %{y:$,.0f}<extra></extra>'
                    ))
                    
                    # Target allocation
                    fig.add_trace(go.Bar(
                        name='Target',
                        x=['Bucket 1<br>(Safety)', 'Bucket 2<br>(Transition)', 'Bucket 3<br>(Growth)'],
                        y=[bucket1_target, bucket2_target, bucket3_target],
                        marker_color=['rgba(33, 195, 84, 0.3)', 'rgba(255, 165, 0, 0.3)', 'rgba(31, 119, 180, 0.3)'],
                        text=[f'${bucket1_target:,.0f}', f'${bucket2_target:,.0f}', f'${bucket3_target:,.0f}'],
                        textposition='inside',
                        textfont=dict(color='#333', size=12),
                        hovertemplate='<b>%{x}</b><br>Target: %{y:$,.0f}<extra></extra>'
                    ))
                    
                    fig.update_layout(
                        barmode='group',
                        title='Current vs Target Bucket Allocation',
                        xaxis_title='',
                        yaxis_title='Value ($)',
                        hovermode='x unified',
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        height=400,
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("---")
                    
                    # Visual bucket allocation summary (detailed breakdown)
                    st.markdown("#### 📋 Detailed Bucket Breakdown")
                    
                    # Total portfolio metric
                    col_total = st.columns([1, 2, 1])
                    with col_total[1]:
                        st.metric(
                            "💰 Total Portfolio Value",
                            f"${bucket_summary.total_portfolio_value:,.0f}",
                            help="Total value across all buckets"
                        )
                    
                    st.markdown("---")
                    
                    # Bucket metrics in columns
                    bucket_col1, bucket_col2, bucket_col3 = st.columns(3)
                    
                    # Bucket 1
                    with bucket_col1:
                        st.markdown("##### 🛡️ Bucket 1: Safety")
                        st.caption(f"{bucket_config.bucket_1_years} years of expenses in cash")
                        
                        drift1 = bucket_summary.get_bucket_drift(BucketType.BUCKET_1_SAFETY)
                        delta_color = "normal" if abs(drift1) < 10 else "inverse"
                        
                        st.metric(
                            "Current Value",
                            f"${bucket_summary.bucket_1_value:,.0f}",
                            delta=f"{drift1:+.1f}% drift",
                            delta_color=delta_color
                        )
                        
                        st.caption(f"**Target:** ${bucket_summary.bucket_1_target:,.0f}")
                        st.caption(f"**Allocation:** {bucket_summary.bucket_1_pct:.1f}% of portfolio")
                        
                        # Progress bar
                        progress_pct = min(bucket_summary.bucket_1_value / bucket_summary.bucket_1_target, 1.0) if bucket_summary.bucket_1_target > 0 else 0
                        st.progress(progress_pct)
                    
                    # Bucket 2
                    with bucket_col2:
                        st.markdown("##### 🔄 Bucket 2: Transition")
                        st.caption(f"{bucket_config.bucket_2_years} years with graduated allocation")
                        
                        drift2 = bucket_summary.get_bucket_drift(BucketType.BUCKET_2_TRANSITION)
                        delta_color = "normal" if abs(drift2) < 10 else "inverse"
                        
                        st.metric(
                            "Current Value",
                            f"${bucket_summary.bucket_2_value:,.0f}",
                            delta=f"{drift2:+.1f}% drift",
                            delta_color=delta_color
                        )
                        
                        st.caption(f"**Target:** ${bucket_summary.bucket_2_target:,.0f}")
                        st.caption(f"**Allocation:** {bucket_summary.bucket_2_pct:.1f}% of portfolio")
                        
                        # Progress bar
                        progress_pct = min(bucket_summary.bucket_2_value / bucket_summary.bucket_2_target, 1.0) if bucket_summary.bucket_2_target > 0 else 0
                        st.progress(progress_pct)
                    
                    # Bucket 3
                    with bucket_col3:
                        st.markdown("##### 🚀 Bucket 3: Growth")
                        st.caption("Long-term growth with 100% stocks")
                        
                        drift3 = bucket_summary.get_bucket_drift(BucketType.BUCKET_3_GROWTH)
                        delta_color = "normal" if abs(drift3) < 10 else "inverse"
                        
                        st.metric(
                            "Current Value",
                            f"${bucket_summary.bucket_3_value:,.0f}",
                            delta=f"{drift3:+.1f}% drift",
                            delta_color=delta_color
                        )
                        
                        st.caption(f"**Target:** ${bucket_summary.bucket_3_target:,.0f}")
                        st.caption(f"**Allocation:** {bucket_summary.bucket_3_pct:.1f}% of portfolio")
                        
                        # Progress bar
                        progress_pct = min(bucket_summary.bucket_3_value / bucket_summary.bucket_3_target, 1.0) if bucket_summary.bucket_3_target > 0 else 0
                        st.progress(progress_pct)
                    
                    # Market condition and rebalancing status
                    st.markdown("---")
                    status_col1, status_col2 = st.columns(2)
                    
                    with status_col1:
                        if bucket_summary.market_condition:
                            condition_name = bucket_summary.market_condition.value.replace("_", " ").title()
                            if "BULL" in bucket_summary.market_condition.value:
                                st.success(f"📈 **Market Condition:** {condition_name}")
                            elif "WARNING" in bucket_summary.market_condition.value:
                                st.warning(f"⚠️ **Market Condition:** {condition_name}")
                            elif "BEAR" in bucket_summary.market_condition.value:
                                st.error(f"📉 **Market Condition:** {condition_name}")
                            else:
                                st.info(f"**Market Condition:** {condition_name}")
                    
                    with status_col2:
                        if bucket_summary.needs_rebalancing:
                            max_drift = max(abs(drift1), abs(drift2), abs(drift3))
                            st.error(f"⚠️ **Rebalancing Needed** (max drift: {max_drift:.1f}%)")
                        else:
                            st.success("✅ **Portfolio Balanced**")
                    
                    # Allocation visualization chart
                    st.markdown("---")
                    st.markdown("#### 📊 Allocation Breakdown")
                    
                    fig = go.Figure()
                    
                    # Current allocation
                    fig.add_trace(go.Bar(
                        name='Current',
                        x=['Bucket 1<br>Safety', 'Bucket 2<br>Transition', 'Bucket 3<br>Growth'],
                        y=[bucket_summary.bucket_1_value, bucket_summary.bucket_2_value, bucket_summary.bucket_3_value],
                        marker_color=['#21c354', '#ffa500', '#1f77b4'],
                        text=[f'${bucket_summary.bucket_1_value:,.0f}', f'${bucket_summary.bucket_2_value:,.0f}', f'${bucket_summary.bucket_3_value:,.0f}'],
                        textposition='inside',
                        textfont=dict(color='white', size=11),
                        hovertemplate='<b>%{x}</b><br>Current: %{y:$,.0f}<extra></extra>'
                    ))
                    
                    # Target allocation
                    fig.add_trace(go.Bar(
                        name='Target',
                        x=['Bucket 1<br>Safety', 'Bucket 2<br>Transition', 'Bucket 3<br>Growth'],
                        y=[bucket_summary.bucket_1_target, bucket_summary.bucket_2_target, bucket_summary.bucket_3_target],
                        marker_color=['rgba(33, 195, 84, 0.3)', 'rgba(255, 165, 0, 0.3)', 'rgba(31, 119, 180, 0.3)'],
                        text=[f'${bucket_summary.bucket_1_target:,.0f}', f'${bucket_summary.bucket_2_target:,.0f}', f'${bucket_summary.bucket_3_target:,.0f}'],
                        textposition='inside',
                        textfont=dict(color='#333', size=11),
                        hovertemplate='<b>%{x}</b><br>Target: %{y:$,.0f}<extra></extra>'
                    ))
                    
                    fig.update_layout(
                        barmode='group',
                        xaxis_title='',
                        yaxis_title='Value ($)',
                        hovermode='x unified',
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        height=350,
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Detailed holdings breakdown
                    st.markdown("---")
                    st.markdown("#### 📋 Holdings by Bucket")
                    
                    if bucket_summary.holdings:
                        # Create DataFrame from holdings
                        holdings_data = []
                        for holding in bucket_summary.holdings:
                            holdings_data.append({
                                "Account": holding.account_name,
                                "Account Type": holding.account_type,
                                "Symbol": holding.symbol,
                                "Name": holding.name,
                                "Asset Class": holding.asset_class.value.title(),
                                "Bucket": holding.bucket_assignment.value.replace("_", " ").title(),
                                "Year": holding.year_in_bucket if holding.year_in_bucket else "-",
                                "Value": holding.current_value,
                            })
                        
                        holdings_df = pd.DataFrame(holdings_data)
                        
                        # Group by bucket
                        for bucket_type in [BucketType.BUCKET_1_SAFETY, BucketType.BUCKET_2_TRANSITION, BucketType.BUCKET_3_GROWTH]:
                            bucket_name = bucket_type.value.replace("_", " ").title()
                            bucket_holdings = holdings_df[holdings_df["Bucket"] == bucket_name]
                            
                            if not bucket_holdings.empty:
                                with st.expander(f"**{bucket_name}** ({len(bucket_holdings)} holdings)", expanded=True):
                                    # Calculate total before formatting
                                    total_value = bucket_holdings["Value"].sum()
                                    
                                    # Format value column for display
                                    display_df = bucket_holdings.copy()
                                    
                                    st.dataframe(
                                        display_df,
                                        column_config={
                                            "Account": st.column_config.TextColumn("Account", width="medium"),
                                            "Account Type": st.column_config.TextColumn("Account Type", width="small"),
                                            "Symbol": st.column_config.TextColumn("Symbol", width="small"),
                                            "Name": st.column_config.TextColumn("Name", width="large"),
                                            "Asset Class": st.column_config.TextColumn("Asset Class", width="small"),
                                            "Year": st.column_config.TextColumn("Year", width="small"),
                                            "Value": st.column_config.NumberColumn("Value", format="$%.0f"),
                                        },
                                        hide_index=True,
                                        use_container_width=True
                                    )
                                    
                                    st.caption(f"**Total:** ${total_value:,.0f}")
                    else:
                        st.info("No holdings data available for bucket analysis.")
                    
                    # Rebalancing recommendations
                    if bucket_summary.needs_rebalancing:
                        st.markdown("---")
                        st.markdown("#### ⚠️ Rebalancing Recommendations")
                        
                        st.warning("""
                        **Action Required:** Your portfolio has drifted from target bucket allocations.
                        
                        Consider rebalancing to maintain your bucket strategy:
                        """)
                        
                        # Calculate current asset allocation within each bucket
                        bucket_asset_allocations = {}
                        for bucket_type in [BucketType.BUCKET_1_SAFETY, BucketType.BUCKET_2_TRANSITION, BucketType.BUCKET_3_GROWTH]:
                            bucket_holdings = [h for h in bucket_summary.holdings if h.bucket_assignment == bucket_type]
                            total_value = sum(h.current_value for h in bucket_holdings)
                            
                            if total_value > 0:
                                cash_value = sum(h.current_value for h in bucket_holdings if h.asset_class == AssetClass.CASH)
                                bonds_value = sum(h.current_value for h in bucket_holdings if h.asset_class == AssetClass.BONDS)
                                stocks_value = sum(h.current_value for h in bucket_holdings if h.asset_class == AssetClass.STOCKS)
                                
                                bucket_asset_allocations[bucket_type] = {
                                    'cash_pct': (cash_value / total_value * 100),
                                    'bonds_pct': (bonds_value / total_value * 100),
                                    'stocks_pct': (stocks_value / total_value * 100)
                                }
                            else:
                                bucket_asset_allocations[bucket_type] = {'cash_pct': 0, 'bonds_pct': 0, 'stocks_pct': 0}
                        
                        drift_data = []
                        for bucket_type, bucket_name in [
                            (BucketType.BUCKET_1_SAFETY, "Bucket 1 (Safety)"),
                            (BucketType.BUCKET_2_TRANSITION, "Bucket 2 (Transition)"),
                            (BucketType.BUCKET_3_GROWTH, "Bucket 3 (Growth)")
                        ]:
                            drift = bucket_summary.get_bucket_drift(bucket_type)
                            
                            # Get current asset allocation
                            alloc = bucket_asset_allocations[bucket_type]
                            current_alloc = f"Cash: {alloc['cash_pct']:.0f}%, Bonds: {alloc['bonds_pct']:.0f}%, Stocks: {alloc['stocks_pct']:.0f}%"
                            
                            # Define target asset allocation for each bucket
                            if bucket_type == BucketType.BUCKET_1_SAFETY:
                                target_alloc = "Cash: 100%, Bonds: 0%, Stocks: 0%"
                            elif bucket_type == BucketType.BUCKET_2_TRANSITION:
                                # Average of graduated allocation (10-80% stocks)
                                avg_stocks = (bucket_config.bucket_2_start_stock_pct + bucket_config.bucket_2_end_stock_pct) / 2
                                avg_bonds = 100 - avg_stocks
                                target_alloc = f"Cash: 0%, Bonds: {avg_bonds:.0f}%, Stocks: {avg_stocks:.0f}%"
                            else:  # BUCKET_3_GROWTH
                                target_alloc = "Cash: 0%, Bonds: 0%, Stocks: 100%"
                            
                            # Calculate current and target bucket percentages
                            if bucket_type == BucketType.BUCKET_1_SAFETY:
                                current_pct = bucket_summary.bucket_1_pct
                                target_pct = (bucket_summary.bucket_1_target / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                            elif bucket_type == BucketType.BUCKET_2_TRANSITION:
                                current_pct = bucket_summary.bucket_2_pct
                                target_pct = (bucket_summary.bucket_2_target / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                            else:  # BUCKET_3_GROWTH
                                current_pct = bucket_summary.bucket_3_pct
                                target_pct = (bucket_summary.bucket_3_target / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                            
                            drift_data.append({
                                "Bucket": bucket_name,
                                "Current %": f"{current_pct:.1f}%",
                                "Target %": f"{target_pct:.1f}%",
                                "Current Asset Mix": current_alloc,
                                "Target Asset Mix": target_alloc,
                                "Drift": f"{drift:+.1f}%",
                                "Status": "✅ OK" if abs(drift) < 10 else "⚠️ Rebalance"
                            })
                        
                        drift_df = pd.DataFrame(drift_data)
                        st.dataframe(
                            drift_df,
                            column_config={
                                "Bucket": st.column_config.TextColumn("Bucket", width="medium"),
                                "Current %": st.column_config.TextColumn("Current %", width="small"),
                                "Target %": st.column_config.TextColumn("Target %", width="small"),
                                "Current Asset Mix": st.column_config.TextColumn("Current Asset Mix", width="large"),
                                "Target Asset Mix": st.column_config.TextColumn("Target Asset Mix", width="large"),
                                "Drift": st.column_config.TextColumn("Drift", width="small"),
                                "Status": st.column_config.TextColumn("Status", width="small"),
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                    else:
                        st.success("✅ **Portfolio is well-balanced** - No rebalancing needed at this time.")
            
            except ImportError as e:
                st.error(f"Bucket strategy module not available: {e}")
            except Exception as e:
                st.error(f"Error analyzing bucket strategy: {e}")
                st.info("Please ensure bucket strategy is properly configured.")
        
        with tax_tab:
            st.subheader("💰 Tax Analytics")
            st.markdown("Comprehensive tax analysis for your accumulation strategy")
            
            # Prepare tax data
            tax_data = prepare_tax_analytics_data(accum_strategy_df, "accumulation")
            
            if tax_data:
                # Create sub-tabs for different views
                tax_overview_tab, tax_income_tab, tax_breakdown_tab, tax_rates_tab, tax_table_tab = st.tabs([
                    "📊 Overview", "💵 Income Sources", "💰 Tax Breakdown", "📈 Tax Rates", "📋 Detailed Table"
                ])
                
                with tax_overview_tab:
                    render_tax_overview(tax_data)
                    st.markdown("---")
                    render_tax_insights(tax_data)
                
                with tax_income_tab:
                    render_income_sources_chart(tax_data, "accumulation")
                
                with tax_breakdown_tab:
                    render_tax_breakdown_chart(tax_data)
                
                with tax_rates_tab:
                    render_tax_rates_chart(tax_data)
                
                with tax_table_tab:
                    render_tax_table(tax_data, "accumulation")
            else:
                st.info("No tax data available for analysis.")

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
        # Check for early SS filing and display warnings
        if 'SS Benefits' in strategy_df_w.columns:
            first_ss_year = strategy_df_w[strategy_df_w['SS Benefits'] > 0]
            if not first_ss_year.empty:
                age_str = str(first_ss_year.iloc[0]['Age'])
                # Handle age format like "63/62" (person1/person2) or just "63"
                if '/' in age_str:
                    first_ss_age = int(age_str.split('/')[0])  # Use person1's age
                else:
                    first_ss_age = int(age_str)
                first_ss_amount = float(first_ss_year.iloc[0]['SS Benefits'])
                
                if first_ss_age < 70:
                    # Calculate taxable portion (approximate)
                    taxable_ss_pct = 85  # Conservative estimate
                    if first_ss_age < 65:
                        # Check if under Medicare age
                        taxable_ss_income = first_ss_amount * 0.85
                        warning_msg = (
                            f"⚠️ **Early Social Security Impact (Age {first_ss_age})**: Taking SS at age {first_ss_age} adds approximately "
                            f"\\${taxable_ss_income:,.2f} "
                            f"of taxable income annually (up to 85% of "
                            f"\\${first_ss_amount:,.0f} benefits). This:\n\n"
                            "- **Reduces Roth conversion capacity** by filling lower tax brackets\n"
                            "- **May eliminate ACA subsidies** if MAGI exceeds 400% FPL (approximately \\$111,000 for couple), costing \\$10,000-\\$15,000/year until Medicare at 65\n"
                            "- **Increases IRMAA risk** (2-year lookback affects Medicare premiums)\n"
                            "- **Limits tax planning flexibility** for Traditional IRA distributions\n\n"
                            f"💡 **Consider**: Delaying SS to age 70 maximizes lifetime benefits and preserves "
                            f"Roth conversion opportunities during ages {first_ss_age}-69."
                        )
                        st.warning(warning_msg)
                    else:
                        taxable_ss_income = first_ss_amount * 0.85
                        info_msg = (
                            f"ℹ️ **Social Security Impact (Age {first_ss_age})**: "
                            f"Taking SS at age {first_ss_age} adds approximately ${taxable_ss_income:,.0f} "
                            f"of taxable income annually. This reduces Roth conversion capacity and may affect "
                            f"IRMAA surcharges (2-year lookback). Delaying to age 70 would increase lifetime "
                            f"benefits by approximately 24% and preserve more conversion room."
                        )
                        st.info(info_msg)


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
            
            # Add info box about DAF and AGI/MAGI if DAF contributions are present
            if 'DAF Contribution' in strategy_df_w.columns and strategy_df_w['DAF Contribution'].sum() > 0:
                st.info(
                    "ℹ️ **Understanding AGI/MAGI in DAF Contribution Years**\n\n"
                    "You'll notice AGI and MAGI appear higher in years with DAF (Donor-Advised Fund) contributions. "
                    "This is **correct** per IRS rules:\n\n"
                    "- **DAF contributions are itemized deductions** that reduce your taxable income and tax bill\n"
                    "- **They do NOT reduce AGI or MAGI** (which are calculated before itemized deductions)\n"
                    "- **MAGI affects IRMAA** (Medicare surcharges) with a 2-year lookback, so higher MAGI in DAF years "
                    "will increase Medicare costs 2 years later\n"
                    "- **The tax benefit is real** — you'll see lower Federal Tax in DAF years despite higher AGI\n\n"
                    "💡 This is why strategic timing of DAF contributions matters for IRMAA planning!"
                )
            
            display_df_w = strategy_df_w.copy()

            try:
                # Use the latest available portfolio data, not current month
                # (current month may not have data yet)
                from load_data import get_latest_portfolio_month_year
                latest_month, latest_year = get_latest_portfolio_month_year()
                _, summary_df_w = get_networth_by_month(latest_month, latest_year)
                actual_cash_start = float(
                    summary_df_w[summary_df_w['account_type'] == 'Savings']['market_value'].sum()
                ) if not summary_df_w.empty else display_df_w.loc[display_df_w.index[0], 'Cash Balance']
            except Exception:
                actual_cash_start = display_df_w.loc[display_df_w.index[0], 'Cash Balance']

            display_df_w['Cash Start'] = display_df_w['Cash Balance'].shift(1)
            display_df_w.loc[display_df_w.index[0], 'Cash Start'] = actual_cash_start
            
            # State tax is now calculated in the strategy engine (strategy.py)
            # No need to add placeholder - it's already in the dataframe

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
                "DAF Contribution": st.column_config.TextColumn("DAF", help="Donor-Advised Fund contribution (itemized deduction)"),
                "AGI":              st.column_config.TextColumn("AGI", help="Adjusted Gross Income (before itemized deductions like DAF). DAF contributions reduce taxable income but not AGI per IRS rules."),
                "MAGI":             st.column_config.TextColumn("MAGI", help="Modified AGI used for IRMAA (2-year lookback) and ACA calculations. Higher in DAF years because charitable contributions don't reduce MAGI."),
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
        
        with bucket_tab:
            st.subheader("🪣 Bucket Strategy Analysis")
            
            try:
                from config import get_config_manager as _get_bucket_cfg
                from bucket_strategy import analyze_portfolio_buckets, load_bucket_config, BucketType, AssetClass, format_bucket_summary
                from load_data import get_latest_portfolio_month_year
                
                _bucket_cfg = _get_bucket_cfg()
                _bucket_enabled = _bucket_cfg.get("bucket_strategy", "enabled", False)
                
                if not _bucket_enabled:
                    st.info("""
                    **🪣 Bucket Strategy Not Enabled**
                    
                    The bucket strategy helps manage sequence of returns risk by dividing your portfolio into three buckets:
                    - **Bucket 1 (Safety)**: Cash for near-term expenses
                    - **Bucket 2 (Transition)**: Graduated stock/bond mix
                    - **Bucket 3 (Growth)**: Long-term growth stocks
                    
                    Enable it in the Configuration page to see detailed bucket analysis here.
                    """)
                    st.page_link("pages/2_configuration.py", label="⚙️ Go to Configuration", icon="⚙️")
                else:
                    month, year = get_latest_portfolio_month_year()
                    bucket_config = load_bucket_config(_bucket_cfg)
                    bucket_summary = analyze_portfolio_buckets(month, year, bucket_config)
                    
                    # Visual bucket allocation summary
                    st.markdown("#### 📊 Current Bucket Allocation")
                    
                    # Total portfolio metric
                    col_total = st.columns([1, 2, 1])
                    with col_total[1]:
                        st.metric(
                            "💰 Total Portfolio Value",
                            f"${bucket_summary.total_portfolio_value:,.0f}",
                            help="Total value across all buckets"
                        )
                    
                    st.markdown("---")
                    
                    # Bucket metrics in columns
                    bucket_col1, bucket_col2, bucket_col3 = st.columns(3)
                    
                    # Bucket 1
                    with bucket_col1:
                        st.markdown("##### 🛡️ Bucket 1: Safety")
                        st.caption(f"{bucket_config.bucket_1_years} years of expenses in cash")
                        
                        drift1 = bucket_summary.get_bucket_drift(BucketType.BUCKET_1_SAFETY)
                        delta_color = "normal" if abs(drift1) < 10 else "inverse"
                        
                        st.metric(
                            "Current Value",
                            f"${bucket_summary.bucket_1_value:,.0f}",
                            delta=f"{drift1:+.1f}% drift",
                            delta_color=delta_color
                        )
                        
                        st.caption(f"**Target:** ${bucket_summary.bucket_1_target:,.0f}")
                        st.caption(f"**Allocation:** {bucket_summary.bucket_1_pct:.1f}% of portfolio")
                        
                        # Progress bar
                        progress_pct = min(bucket_summary.bucket_1_value / bucket_summary.bucket_1_target, 1.0) if bucket_summary.bucket_1_target > 0 else 0
                        st.progress(progress_pct)
                    
                    # Bucket 2
                    with bucket_col2:
                        st.markdown("##### 🔄 Bucket 2: Transition")
                        st.caption(f"{bucket_config.bucket_2_years} years with graduated allocation")
                        
                        drift2 = bucket_summary.get_bucket_drift(BucketType.BUCKET_2_TRANSITION)
                        delta_color = "normal" if abs(drift2) < 10 else "inverse"
                        
                        st.metric(
                            "Current Value",
                            f"${bucket_summary.bucket_2_value:,.0f}",
                            delta=f"{drift2:+.1f}% drift",
                            delta_color=delta_color
                        )
                        
                        st.caption(f"**Target:** ${bucket_summary.bucket_2_target:,.0f}")
                        st.caption(f"**Allocation:** {bucket_summary.bucket_2_pct:.1f}% of portfolio")
                        
                        # Progress bar
                        progress_pct = min(bucket_summary.bucket_2_value / bucket_summary.bucket_2_target, 1.0) if bucket_summary.bucket_2_target > 0 else 0
                        st.progress(progress_pct)
                    
                    # Bucket 3
                    with bucket_col3:
                        st.markdown("##### 🚀 Bucket 3: Growth")
                        st.caption("Long-term growth with 100% stocks")
                        
                        drift3 = bucket_summary.get_bucket_drift(BucketType.BUCKET_3_GROWTH)
                        delta_color = "normal" if abs(drift3) < 10 else "inverse"
                        
                        st.metric(
                            "Current Value",
                            f"${bucket_summary.bucket_3_value:,.0f}",
                            delta=f"{drift3:+.1f}% drift",
                            delta_color=delta_color
                        )
                        
                        st.caption(f"**Target:** ${bucket_summary.bucket_3_target:,.0f}")
                        st.caption(f"**Allocation:** {bucket_summary.bucket_3_pct:.1f}% of portfolio")
                        
                        # Progress bar
                        progress_pct = min(bucket_summary.bucket_3_value / bucket_summary.bucket_3_target, 1.0) if bucket_summary.bucket_3_target > 0 else 0
                        st.progress(progress_pct)
                    
                    # Market condition and rebalancing status
                    st.markdown("---")
                    status_col1, status_col2 = st.columns(2)
                    
                    with status_col1:
                        if bucket_summary.market_condition:
                            condition_name = bucket_summary.market_condition.value.replace("_", " ").title()
                            if "BULL" in bucket_summary.market_condition.value:
                                st.success(f"📈 **Market Condition:** {condition_name}")
                            elif "WARNING" in bucket_summary.market_condition.value:
                                st.warning(f"⚠️ **Market Condition:** {condition_name}")
                            elif "BEAR" in bucket_summary.market_condition.value:
                                st.error(f"📉 **Market Condition:** {condition_name}")
                            else:
                                st.info(f"**Market Condition:** {condition_name}")
                    
                    with status_col2:
                        if bucket_summary.needs_rebalancing:
                            max_drift = max(abs(drift1), abs(drift2), abs(drift3))
                            st.error(f"⚠️ **Rebalancing Needed** (max drift: {max_drift:.1f}%)")
                        else:
                            st.success("✅ **Portfolio Balanced**")
                    
                    # Allocation visualization chart
                    st.markdown("---")
                    st.markdown("#### 📊 Allocation Breakdown")
                    
                    fig = go.Figure()
                    
                    # Current allocation
                    fig.add_trace(go.Bar(
                        name='Current',
                        x=['Bucket 1<br>Safety', 'Bucket 2<br>Transition', 'Bucket 3<br>Growth'],
                        y=[bucket_summary.bucket_1_value, bucket_summary.bucket_2_value, bucket_summary.bucket_3_value],
                        marker_color=['#21c354', '#ffa500', '#1f77b4'],
                        text=[f'${bucket_summary.bucket_1_value:,.0f}', f'${bucket_summary.bucket_2_value:,.0f}', f'${bucket_summary.bucket_3_value:,.0f}'],
                        textposition='inside',
                        textfont=dict(color='white', size=11),
                        hovertemplate='<b>%{x}</b><br>Current: %{y:$,.0f}<extra></extra>'
                    ))
                    
                    # Target allocation
                    fig.add_trace(go.Bar(
                        name='Target',
                        x=['Bucket 1<br>Safety', 'Bucket 2<br>Transition', 'Bucket 3<br>Growth'],
                        y=[bucket_summary.bucket_1_target, bucket_summary.bucket_2_target, bucket_summary.bucket_3_target],
                        marker_color=['rgba(33, 195, 84, 0.3)', 'rgba(255, 165, 0, 0.3)', 'rgba(31, 119, 180, 0.3)'],
                        text=[f'${bucket_summary.bucket_1_target:,.0f}', f'${bucket_summary.bucket_2_target:,.0f}', f'${bucket_summary.bucket_3_target:,.0f}'],
                        textposition='inside',
                        textfont=dict(color='#333', size=11),
                        hovertemplate='<b>%{x}</b><br>Target: %{y:$,.0f}<extra></extra>'
                    ))
                    
                    fig.update_layout(
                        barmode='group',
                        xaxis_title='',
                        yaxis_title='Value ($)',
                        hovermode='x unified',
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        height=350,
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Detailed holdings breakdown
                    st.markdown("---")
                    st.markdown("#### 📋 Holdings by Bucket")
                    
                    if bucket_summary.holdings:
                        # Create DataFrame from holdings
                        holdings_data = []
                        for holding in bucket_summary.holdings:
                            holdings_data.append({
                                "Account": holding.account_name,
                                "Account Type": holding.account_type,
                                "Symbol": holding.symbol,
                                "Name": holding.name,
                                "Asset Class": holding.asset_class.value.title(),
                                "Bucket": holding.bucket_assignment.value.replace("_", " ").title(),
                                "Year": holding.year_in_bucket if holding.year_in_bucket else "-",
                                "Value": holding.current_value,
                            })
                        
                        holdings_df = pd.DataFrame(holdings_data)
                        
                        # Group by bucket
                        for bucket_type in [BucketType.BUCKET_1_SAFETY, BucketType.BUCKET_2_TRANSITION, BucketType.BUCKET_3_GROWTH]:
                            bucket_name = bucket_type.value.replace("_", " ").title()
                            bucket_holdings = holdings_df[holdings_df["Bucket"] == bucket_name]
                            
                            if not bucket_holdings.empty:
                                with st.expander(f"**{bucket_name}** ({len(bucket_holdings)} holdings)", expanded=True):
                                    # Calculate total before formatting
                                    total_value = bucket_holdings["Value"].sum()
                                    
                                    # Format value column for display
                                    display_df = bucket_holdings.copy()
                                    
                                    st.dataframe(
                                        display_df,
                                        column_config={
                                            "Account": st.column_config.TextColumn("Account", width="medium"),
                                            "Account Type": st.column_config.TextColumn("Account Type", width="small"),
                                            "Symbol": st.column_config.TextColumn("Symbol", width="small"),
                                            "Name": st.column_config.TextColumn("Name", width="large"),
                                            "Asset Class": st.column_config.TextColumn("Asset Class", width="small"),
                                            "Year": st.column_config.TextColumn("Year", width="small"),
                                            "Value": st.column_config.NumberColumn("Value", format="$%.0f"),
                                        },
                                        hide_index=True,
                                        use_container_width=True
                                    )
                                    
                                    st.caption(f"**Total:** ${total_value:,.0f}")
                    else:
                        st.info("No holdings data available for bucket analysis.")
                    
                    # Rebalancing recommendations
                    if bucket_summary.needs_rebalancing:
                        st.markdown("---")
                        st.markdown("#### ⚠️ Rebalancing Recommendations")
                        
                        st.warning("""
                        **Action Required:** Your portfolio has drifted from target bucket allocations.
                        
                        Consider rebalancing to maintain your bucket strategy:
                        """)
                        
                        # Calculate current asset allocation within each bucket
                        bucket_asset_allocations = {}
                        for bucket_type in [BucketType.BUCKET_1_SAFETY, BucketType.BUCKET_2_TRANSITION, BucketType.BUCKET_3_GROWTH]:
                            bucket_holdings = [h for h in bucket_summary.holdings if h.bucket_assignment == bucket_type]
                            total_value = sum(h.current_value for h in bucket_holdings)
                            
                            if total_value > 0:
                                cash_value = sum(h.current_value for h in bucket_holdings if h.asset_class == AssetClass.CASH)
                                bonds_value = sum(h.current_value for h in bucket_holdings if h.asset_class == AssetClass.BONDS)
                                stocks_value = sum(h.current_value for h in bucket_holdings if h.asset_class == AssetClass.STOCKS)
                                
                                bucket_asset_allocations[bucket_type] = {
                                    'cash_pct': (cash_value / total_value * 100),
                                    'bonds_pct': (bonds_value / total_value * 100),
                                    'stocks_pct': (stocks_value / total_value * 100)
                                }
                            else:
                                bucket_asset_allocations[bucket_type] = {'cash_pct': 0, 'bonds_pct': 0, 'stocks_pct': 0}
                        
                        drift_data = []
                        for bucket_type, bucket_name in [
                            (BucketType.BUCKET_1_SAFETY, "Bucket 1 (Safety)"),
                            (BucketType.BUCKET_2_TRANSITION, "Bucket 2 (Transition)"),
                            (BucketType.BUCKET_3_GROWTH, "Bucket 3 (Growth)")
                        ]:
                            drift = bucket_summary.get_bucket_drift(bucket_type)
                            
                            # Get current asset allocation
                            alloc = bucket_asset_allocations[bucket_type]
                            current_alloc = f"Cash: {alloc['cash_pct']:.0f}%, Bonds: {alloc['bonds_pct']:.0f}%, Stocks: {alloc['stocks_pct']:.0f}%"
                            
                            # Define target asset allocation for each bucket
                            if bucket_type == BucketType.BUCKET_1_SAFETY:
                                target_alloc = "Cash: 100%, Bonds: 0%, Stocks: 0%"
                            elif bucket_type == BucketType.BUCKET_2_TRANSITION:
                                # Average of graduated allocation (10-80% stocks)
                                avg_stocks = (bucket_config.bucket_2_start_stock_pct + bucket_config.bucket_2_end_stock_pct) / 2
                                avg_bonds = 100 - avg_stocks
                                target_alloc = f"Cash: 0%, Bonds: {avg_bonds:.0f}%, Stocks: {avg_stocks:.0f}%"
                            else:  # BUCKET_3_GROWTH
                                target_alloc = "Cash: 0%, Bonds: 0%, Stocks: 100%"
                            
                            # Calculate current and target bucket percentages
                            if bucket_type == BucketType.BUCKET_1_SAFETY:
                                current_pct = bucket_summary.bucket_1_pct
                                target_pct = (bucket_summary.bucket_1_target / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                            elif bucket_type == BucketType.BUCKET_2_TRANSITION:
                                current_pct = bucket_summary.bucket_2_pct
                                target_pct = (bucket_summary.bucket_2_target / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                            else:  # BUCKET_3_GROWTH
                                current_pct = bucket_summary.bucket_3_pct
                                target_pct = (bucket_summary.bucket_3_target / bucket_summary.total_portfolio_value * 100) if bucket_summary.total_portfolio_value > 0 else 0
                            
                            drift_data.append({
                                "Bucket": bucket_name,
                                "Current %": f"{current_pct:.1f}%",
                                "Target %": f"{target_pct:.1f}%",
                                "Current Asset Mix": current_alloc,
                                "Target Asset Mix": target_alloc,
                                "Drift": f"{drift:+.1f}%",
                                "Status": "✅ OK" if abs(drift) < 10 else "⚠️ Rebalance"
                            })
                        
                        drift_df = pd.DataFrame(drift_data)
                        st.dataframe(
                            drift_df,
                            column_config={
                                "Bucket": st.column_config.TextColumn("Bucket", width="medium"),
                                "Current %": st.column_config.TextColumn("Current %", width="small"),
                                "Target %": st.column_config.TextColumn("Target %", width="small"),
                                "Current Asset Mix": st.column_config.TextColumn("Current Asset Mix", width="large"),
                                "Target Asset Mix": st.column_config.TextColumn("Target Asset Mix", width="large"),
                                "Drift": st.column_config.TextColumn("Drift", width="small"),
                                "Status": st.column_config.TextColumn("Status", width="small"),
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                    else:
                        st.success("✅ **Portfolio is well-balanced** - No rebalancing needed at this time.")
            
            except ImportError as e:
                st.error(f"Bucket strategy module not available: {e}")
            except Exception as e:
                st.error(f"Error analyzing bucket strategy: {e}")
                st.info("Please ensure bucket strategy is properly configured.")
        
        with tax_tab:
            st.subheader("💰 Tax Analytics")
            st.markdown("Comprehensive tax analysis for your withdrawal strategy")
            
            # Prepare tax data
            tax_data = prepare_tax_analytics_data(strategy_df_w, "withdrawal")
            
            if tax_data:
                # Create sub-tabs for different views
                tax_overview_tab, tax_income_tab, tax_breakdown_tab, tax_rates_tab, tax_table_tab = st.tabs([
                    "📊 Overview", "💵 Income Sources", "💰 Tax Breakdown", "📈 Tax Rates", "📋 Detailed Table"
                ])
                
                with tax_overview_tab:
                    render_tax_overview(tax_data)
                    st.markdown("---")
                    render_tax_insights(tax_data)
                
                with tax_income_tab:
                    render_income_sources_chart(tax_data, "withdrawal")
                
                with tax_breakdown_tab:
                    render_tax_breakdown_chart(tax_data)
                
                with tax_rates_tab:
                    render_tax_rates_chart(tax_data)
                
                with tax_table_tab:
                    render_tax_table(tax_data, "withdrawal")
            else:
                st.info("No tax data available for analysis.")

    except Exception as e:
        st.error(f"Error calculating withdrawal strategy: {e}")
        st.info("Please ensure all configuration parameters are properly set.")

# Made with Bob