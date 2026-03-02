"""
Configuration page for retirement planning application.
Allows users to view and edit application constants and preferences.
"""

import streamlit as st
from datetime import datetime
import json
import pandas as pd
import os
import shutil
import zipfile
import io
from config import get_config_manager, reload_config
from components.navbar import navbar
from portfolio import build_portfolio_display
from portfolio_data_entry import (
    validate_portfolio_dataframe,
    validate_ticker_symbol,
    load_previous_month_data,
    create_empty_entry_template,
    save_portfolio_data,
    start_from_scratch,
    revert_to_last_backup,
    VALID_ACCOUNT_TYPES,
    VALID_SECTORS,
)
from ssi_calculator import generate_ssi_schedule_from_config, export_ssi_schedule_to_csv

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")

navbar("⚙️ Settings")

# Initialize configuration manager
config_mgr = get_config_manager()


def sync_config_to_session_state():
    """
    Sync configuration values to session state for sidebar compatibility.
    This ensures that changes made in the configuration page are immediately
    available to other parts of the application that read from session state.
    """
    # Map configuration to session state keys used by sidebar
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

st.title("⚙️ Retirement Planning Configuration")
st.markdown("Configure your personal information, financial assumptions, and planning parameters.")

# Create tabs for different configuration sections
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "👤 Personal Info",
    "💰 Financial Assumptions",
    "🏥 Healthcare",
    "📊 Social Security",
    "📈 Tax Strategy",
    "📊 Portfolio Data",
    "🏠 Real Estate",
    "🔧 Advanced"
])

# Sync configuration to session state on page load
sync_config_to_session_state()

# Track if any changes were made
changes_made = False

# Personal Information Tab
with tab1:
    st.header("Personal Information")
    st.markdown("Enter information about yourself and your spouse/partner.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Primary Person")
        person1_name = st.text_input(
            "Name",
            value=config_mgr.get("personal_info", "person1_name", ""),
            key="person1_name"
        )
        person1_birth_date = st.date_input(
            "Birth Date",
            value=datetime.strptime(
                config_mgr.get("personal_info", "person1_birth_date", "1965-01-01"),
                "%Y-%m-%d"
            ),
            key="person1_birth_date"
        )
        person1_retirement_age = st.number_input(
            "Planned Retirement Age",
            min_value=50,
            max_value=75,
            value=config_mgr.get("personal_info", "person1_retirement_age", 67),
            key="person1_retirement_age"
        )
        
        # Display current age
        current_age_1 = config_mgr.calculate_age(person1_birth_date.strftime("%Y-%m-%d"))
        st.info(f"Current Age: {current_age_1} years")
    
    with col2:
        st.subheader("Spouse/Partner")
        person2_name = st.text_input(
            "Name",
            value=config_mgr.get("personal_info", "person2_name", ""),
            key="person2_name"
        )
        person2_birth_date = st.date_input(
            "Birth Date",
            value=datetime.strptime(
                config_mgr.get("personal_info", "person2_birth_date", "1967-01-01"),
                "%Y-%m-%d"
            ),
            key="person2_birth_date"
        )
        person2_retirement_age = st.number_input(
            "Planned Retirement Age",
            min_value=50,
            max_value=75,
            value=config_mgr.get("personal_info", "person2_retirement_age", 62),
            key="person2_retirement_age"
        )
        
        # Display current age
        current_age_2 = config_mgr.calculate_age(person2_birth_date.strftime("%Y-%m-%d"))
        st.info(f"Current Age: {current_age_2} years")
    
    # Retirement Location
    st.subheader("Retirement Location")
    
    # List of US states (abbreviated)
    us_states = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    ]
    
    current_state = config_mgr.get("personal_info", "retirement_state", "FL")
    try:
        state_index = us_states.index(current_state)
    except ValueError:
        state_index = us_states.index("FL")  # Default to Florida
    
    retirement_state = st.selectbox(
        "Retirement State",
        options=us_states,
        index=state_index,
        help="State where you plan to retire (affects state tax calculations)",
        key="retirement_state"
    )
    
    st.info(f"Selected state: {retirement_state} - State tax calculations will be applied based on this selection.")

    # -----------------------------------------------------------------------
    # Children
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.subheader("👶 Children")
    st.markdown(
        "Add children and their birth dates. This information is used for "
        "estate planning suggestions, dependent tax calculations, and college "
        "funding stage strategies."
    )

    # Load existing children from config (list of {name, birth_date} dicts)
    _existing_children = config_mgr.get("personal_info", "children", [])
    if not isinstance(_existing_children, list):
        _existing_children = []

    # Build an editable DataFrame — include special_needs flag
    _seed_row = [{"name": "", "birth_date": "", "special_needs": False}]
    _children_df = pd.DataFrame(
        _existing_children if _existing_children else _seed_row,
    )
    # Ensure all three columns always exist (handles legacy data without special_needs)
    for _col, _default in (("name", ""), ("birth_date", ""), ("special_needs", False)):
        if _col not in _children_df.columns:
            _children_df[_col] = _default

    st.caption(
        "Enter each child's name, birth date (YYYY-MM-DD), and whether they have special needs. "
        "Add rows with the ➕ button; delete rows by selecting them and pressing Delete."
    )

    children_df = st.data_editor(
        _children_df,
        column_config={
            "name": st.column_config.TextColumn(
                "Child's Name",
                help="First name (or full name) of the child",
                max_chars=60,
            ),
            "birth_date": st.column_config.TextColumn(
                "Birth Date (YYYY-MM-DD)",
                help="Date of birth in YYYY-MM-DD format, e.g. 2005-03-15",
                max_chars=10,
            ),
            "special_needs": st.column_config.CheckboxColumn(
                "Special Needs",
                help=(
                    "Check if this child has a disability or special needs. "
                    "Used in estate planning to recommend a Special Needs Trust."
                ),
                default=False,
            ),
        },
        num_rows="dynamic",
        width='stretch',
        key="children_editor",
    )

    # Validate birth dates and show a live summary
    _valid_children = []
    _child_errors = []
    for _row_num, (_idx, _row) in enumerate(children_df.iterrows(), start=1):
        _cname = str(_row.get("name", "")).strip()
        _cbdate = str(_row.get("birth_date", "")).strip()
        _cspecial = bool(_row.get("special_needs", False))
        if not _cname and not _cbdate:
            continue  # skip blank rows
        try:
            datetime.strptime(_cbdate, "%Y-%m-%d")
            _cage = config_mgr.calculate_age(_cbdate)
            _sn_tag = " 🔹 Special Needs" if _cspecial else ""
            _valid_children.append({"name": _cname, "birth_date": _cbdate, "special_needs": _cspecial})
            st.caption(f"  • **{_cname}** — born {_cbdate} (age {_cage}){_sn_tag}")
        except ValueError:
            _child_errors.append(f"Row {_row_num}: '{_cbdate}' is not a valid YYYY-MM-DD date for '{_cname}'")

    if _child_errors:
        for _err in _child_errors:
            st.warning(f"⚠️ {_err}")

# Financial Assumptions Tab
with tab2:
    st.header("Financial Assumptions")
    st.markdown("Set your expected expenses and investment return assumptions.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        expected_annual_expenses = st.number_input(
            "Expected Annual Expenses ($)",
            min_value=0,
            max_value=1000000,
            value=config_mgr.get("financial_assumptions", "expected_annual_expenses", 50000),
            step=1000,
            help="Your estimated annual living expenses in retirement",
            key="expected_annual_expenses"
        )
        
        expense_inflation_rate = st.number_input(
            "Expense Inflation Rate (%)",
            min_value=0.0,
            max_value=10.0,
            value=config_mgr.get("financial_assumptions", "expense_inflation_rate", 3.0),
            step=0.1,
            help="Expected annual increase in expenses",
            key="expense_inflation_rate"
        )
    
    with col2:
        expected_rate_of_return = st.number_input(
            "Expected Rate of Return (%)",
            min_value=0.0,
            max_value=20.0,
            value=config_mgr.get("financial_assumptions", "expected_rate_of_return", 6.0),
            step=0.1,
            help="Expected annual investment return",
            key="expected_rate_of_return"
        )
        
        years_of_expenses_in_cash = st.number_input(
            "Years of Expenses in Cash",
            min_value=1,
            max_value=10,
            value=config_mgr.get("financial_assumptions", "years_of_expenses_in_cash", 4),
            help="How many years of expenses to keep in cash/safe assets (retirement phase)",
            key="years_of_expenses_in_cash"
        )

        accumulation_cash_buffer_months = st.slider(
            "Accumulation Phase: Cash Buffer (months of wages)",
            min_value=3,
            max_value=24,
            value=int(config_mgr.get("financial_assumptions", "accumulation_cash_buffer_months", 6)),
            step=1,
            help=(
                "During working years, target this many months of gross wages in cash. "
                "6 months is the standard emergency fund recommendation. "
                "Range: 3 months (lean) to 24 months (very conservative)."
            ),
            key="accumulation_cash_buffer_months"
        )
        # Show the dollar equivalent based on total household income
        total_wages = (
            config_mgr.get("income", "person1_annual_wages", 0) +
            config_mgr.get("income", "person2_annual_wages", 0)
        )
        if total_wages > 0:
            accum_cash_target = total_wages * accumulation_cash_buffer_months / 12
            st.caption(
                f"≈ ${accum_cash_target:,.0f} target cash balance "
                f"({accumulation_cash_buffer_months} months × ${total_wages:,.0f}/yr wages)"
            )
    
    # Income Section
    st.markdown("---")
    st.subheader("Income (Pre-Retirement)")
    st.markdown("Enter annual wages/salary for each person. These will be used in withdrawal strategy calculations for pre-retirement years.")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown(f"**{person1_name}'s Income**")
        person1_annual_wages = st.number_input(
            "Annual Wages/Salary ($)",
            min_value=0,
            max_value=1000000,
            value=config_mgr.get("income", "person1_annual_wages", 0),
            step=5000,
            help=f"Annual wages/salary for {person1_name} (used until retirement year)",
            key="person1_annual_wages"
        )
    
    with col4:
        st.markdown(f"**{person2_name}'s Income**")
        person2_annual_wages = st.number_input(
            "Annual Wages/Salary ($)",
            min_value=0,
            max_value=1000000,
            value=config_mgr.get("income", "person2_annual_wages", 0),
            step=5000,
            help=f"Annual wages/salary for {person2_name} (used until retirement year)",
            key="person2_annual_wages"
        )
    
    wage_inflation_rate = st.number_input(
        "Wage Inflation Rate (%)",
        min_value=0.0,
        max_value=10.0,
        value=config_mgr.get("income", "wage_inflation_rate", 3.0),
        step=0.1,
        help="Expected annual increase in wages/salary",
        key="wage_inflation_rate"
    )
    
    # Display calculated values
    st.markdown("---")
    st.subheader("Calculated Values")
    
    col_calc1, col_calc2 = st.columns(2)
    with col_calc1:
        cash_reserve = expected_annual_expenses * years_of_expenses_in_cash
        st.metric("Recommended Cash Reserve", f"${cash_reserve:,.0f}")
    
    with col_calc2:
        total_household_income = person1_annual_wages + person2_annual_wages
        st.metric("Total Household Income", f"${total_household_income:,.0f}")

# Healthcare Tab
with tab3:
    st.header("Healthcare Costs")
    st.markdown("Configure healthcare insurance and Medicare assumptions for both people.")
    
    # ACA Marketplace enrollment (household level)
    aca_marketplace_enrolled = st.checkbox(
        "Enrolled in ACA Marketplace",
        value=config_mgr.get("healthcare", "aca_marketplace_enrolled", False),
        help="Check if you plan to purchase insurance from the ACA marketplace. This affects withdrawal strategy optimization for subsidy eligibility.",
        key="aca_marketplace_enrolled"
    )
    
    if aca_marketplace_enrolled:
        st.info("💡 Withdrawal strategy will optimize income to maximize ACA subsidies (typically keeping MAGI below 400% FPL)")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"{person1_name}'s Healthcare")
        
        st.markdown("**ACA Insurance (Pre-Medicare)**")
        person1_aca_insurance_monthly = st.number_input(
            "Monthly ACA Premium ($)",
            min_value=0,
            max_value=5000,
            value=config_mgr.get("healthcare", "person1_aca_insurance_monthly", 0),
            step=50,
            help=f"Monthly premium for {person1_name}'s ACA marketplace insurance (before subsidies)",
            key="person1_aca_insurance_monthly"
        )
        
        person1_aca_start_age = st.number_input(
            "ACA Coverage Start Age",
            min_value=50,
            max_value=65,
            value=config_mgr.get("healthcare", "person1_aca_start_age",
                                config_mgr.get("personal_info", "person1_retirement_age", 62)),
            help=f"Age when {person1_name}'s ACA coverage begins (typically at retirement)",
            key="person1_aca_start_age"
        )
        
        person1_aca_end_age = st.number_input(
            "ACA Coverage End Age",
            min_value=60,
            max_value=70,
            value=config_mgr.get("healthcare", "person1_aca_end_age", 65),
            help=f"Age when {person1_name}'s ACA coverage ends (typically when Medicare starts)",
            key="person1_aca_end_age"
        )
        
        st.markdown("**Medicare**")
        person1_medicare_start_age = st.number_input(
            "Medicare Start Age",
            min_value=60,
            max_value=70,
            value=config_mgr.get("healthcare", "person1_medicare_start_age", 65),
            help=f"Age when {person1_name}'s Medicare coverage begins",
            key="person1_medicare_start_age"
        )
        
        # Display calculated costs for person1
        if person1_aca_insurance_monthly > 0:
            annual_aca_cost_1 = person1_aca_insurance_monthly * 12
            years_on_aca_1 = max(0, person1_aca_end_age - person1_aca_start_age)
            total_aca_cost_1 = annual_aca_cost_1 * years_on_aca_1
            
            st.metric("Annual ACA Cost", f"${annual_aca_cost_1:,.0f}")
            st.metric("Total ACA Cost", f"${total_aca_cost_1:,.0f}",
                     help=f"Total cost for {years_on_aca_1} years on ACA")
    
    with col2:
        st.subheader(f"{person2_name}'s Healthcare")
        
        st.markdown("**ACA Insurance (Pre-Medicare)**")
        person2_aca_insurance_monthly = st.number_input(
            "Monthly ACA Premium ($)",
            min_value=0,
            max_value=5000,
            value=config_mgr.get("healthcare", "person2_aca_insurance_monthly", 0),
            step=50,
            help=f"Monthly premium for {person2_name}'s ACA marketplace insurance (before subsidies)",
            key="person2_aca_insurance_monthly"
        )
        
        person2_aca_start_age = st.number_input(
            "ACA Coverage Start Age",
            min_value=50,
            max_value=65,
            value=config_mgr.get("healthcare", "person2_aca_start_age",
                                config_mgr.get("personal_info", "person2_retirement_age", 62)),
            help=f"Age when {person2_name}'s ACA coverage begins (typically at retirement)",
            key="person2_aca_start_age"
        )
        
        person2_aca_end_age = st.number_input(
            "ACA Coverage End Age",
            min_value=60,
            max_value=70,
            value=config_mgr.get("healthcare", "person2_aca_end_age", 65),
            help=f"Age when {person2_name}'s ACA coverage ends (typically when Medicare starts)",
            key="person2_aca_end_age"
        )
        
        st.markdown("**Medicare**")
        person2_medicare_start_age = st.number_input(
            "Medicare Start Age",
            min_value=60,
            max_value=70,
            value=config_mgr.get("healthcare", "person2_medicare_start_age", 65),
            help=f"Age when {person2_name}'s Medicare coverage begins",
            key="person2_medicare_start_age"
        )
        
        # Display calculated costs for person2
        if person2_aca_insurance_monthly > 0:
            annual_aca_cost_2 = person2_aca_insurance_monthly * 12
            years_on_aca_2 = max(0, person2_aca_end_age - person2_aca_start_age)
            total_aca_cost_2 = annual_aca_cost_2 * years_on_aca_2
            
            st.metric("Annual ACA Cost", f"${annual_aca_cost_2:,.0f}")
            st.metric("Total ACA Cost", f"${total_aca_cost_2:,.0f}",
                     help=f"Total cost for {years_on_aca_2} years on ACA")
    
    # Display combined household costs
    if person1_aca_insurance_monthly > 0 or person2_aca_insurance_monthly > 0:
        st.markdown("---")
        st.subheader("Combined Household Healthcare Costs")
        
        col_health1, col_health2 = st.columns(2)
        
        with col_health1:
            total_monthly_aca = person1_aca_insurance_monthly + person2_aca_insurance_monthly
            st.metric("Total Monthly ACA Premium", f"${total_monthly_aca:,.0f}")
        
        with col_health2:
            total_annual_aca = total_monthly_aca * 12
            st.metric("Total Annual ACA Cost", f"${total_annual_aca:,.0f}")

# Social Security Tab
with tab4:
    st.header("Social Security Benefits")
    st.markdown("Configure when you plan to start collecting Social Security.")
    
    st.info("💡 **Important:** Enter your estimated benefit at **Full Retirement Age (67)**. The system will automatically adjust for early or delayed claiming.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"{person1_name}'s Social Security")
        person1_ssi_age = st.number_input(
            "Age to Start Benefits",
            min_value=62,
            max_value=70,
            value=max(62, min(70, config_mgr.get("social_security", "person1_ssi_age", 70))),
            help="Age when you plan to start collecting Social Security (62-70)",
            key="person1_ssi_age"
        )
        
        person1_ssi_amount = st.number_input(
            "Monthly Benefit at Age 67 ($)",
            min_value=0,
            max_value=10000,
            value=config_mgr.get("social_security", "person1_ssi_amount", 0),
            step=100,
            help="Your estimated MONTHLY benefit at Full Retirement Age (67). The system will adjust for your claiming age.",
            key="person1_ssi_amount"
        )
        
        if person1_ssi_amount > 0:
            # Calculate adjusted benefit based on claiming age
            from ssi_calculator import calculate_benefit_at_claiming_age
            adjusted_benefit = calculate_benefit_at_claiming_age(person1_ssi_amount, person1_ssi_age)
            annual_benefit = adjusted_benefit * 12
            
            if person1_ssi_age < 67:
                reduction_pct = ((adjusted_benefit / person1_ssi_amount) - 1) * 100
                st.warning(f"📉 Early claiming at {person1_ssi_age}: ${adjusted_benefit:,.0f}/mo ({reduction_pct:.1f}%)")
            elif person1_ssi_age > 67:
                increase_pct = ((adjusted_benefit / person1_ssi_amount) - 1) * 100
                st.success(f"📈 Delayed claiming at {person1_ssi_age}: ${adjusted_benefit:,.0f}/mo (+{increase_pct:.1f}%)")
            else:
                st.info(f"Monthly Benefit at FRA: ${adjusted_benefit:,.0f}/mo")
            
            st.metric("Annual Benefit", f"${annual_benefit:,.0f}")
    
    with col2:
        st.subheader(f"{person2_name}'s Social Security")
        person2_ssi_age = st.number_input(
            "Age to Start Benefits",
            min_value=62,
            max_value=70,
            value=max(62, min(70, config_mgr.get("social_security", "person2_ssi_age", 70))),
            help="Age when you plan to start collecting Social Security (62-70)",
            key="person2_ssi_age"
        )
        
        person2_ssi_amount = st.number_input(
            "Monthly Benefit at Age 67 ($)",
            min_value=0,
            max_value=10000,
            value=config_mgr.get("social_security", "person2_ssi_amount", 0),
            step=100,
            help="Your estimated MONTHLY benefit at Full Retirement Age (67). The system will adjust for your claiming age.",
            key="person2_ssi_amount"
        )
        
        if person2_ssi_amount > 0:
            # Calculate adjusted benefit based on claiming age
            from ssi_calculator import calculate_benefit_at_claiming_age
            adjusted_benefit = calculate_benefit_at_claiming_age(person2_ssi_amount, person2_ssi_age)
            annual_benefit = adjusted_benefit * 12
            
            if person2_ssi_age < 67:
                reduction_pct = ((adjusted_benefit / person2_ssi_amount) - 1) * 100
                st.warning(f"📉 Early claiming at {person2_ssi_age}: ${adjusted_benefit:,.0f}/mo ({reduction_pct:.1f}%)")
            elif person2_ssi_age > 67:
                increase_pct = ((adjusted_benefit / person2_ssi_amount) - 1) * 100
                st.success(f"📈 Delayed claiming at {person2_ssi_age}: ${adjusted_benefit:,.0f}/mo (+{increase_pct:.1f}%)")
            else:
                st.info(f"Monthly Benefit at FRA: ${adjusted_benefit:,.0f}/mo")
            
            st.metric("Annual Benefit", f"${annual_benefit:,.0f}")
    
    # Display combined benefits
    if person1_ssi_amount > 0 or person2_ssi_amount > 0:
        st.markdown("---")
        st.subheader("Combined Benefits")
        
        from ssi_calculator import calculate_benefit_at_claiming_age
        
        person1_adjusted = calculate_benefit_at_claiming_age(person1_ssi_amount, person1_ssi_age) if person1_ssi_amount > 0 else 0
        person2_adjusted = calculate_benefit_at_claiming_age(person2_ssi_amount, person2_ssi_age) if person2_ssi_amount > 0 else 0
        
        total_monthly = person1_adjusted + person2_adjusted
        total_annual = total_monthly * 12
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Total Monthly Benefits", f"${total_monthly:,.0f}")
        with col_b:
            st.metric("Total Annual Benefits", f"${total_annual:,.0f}")
        
        st.info("💡 These benefits will be automatically calculated with COLA adjustments in the withdrawal strategy.")

# Tax Strategy Tab
with tab5:
    st.header("Tax Strategy")
    st.markdown("Configure Roth conversion and tax planning parameters.")
    
    st.subheader("Roth Conversions")
    st.info("ℹ️ Roth conversions are now automatically optimized using the BETR (Better Efficient Tax Rate) algorithm based on your maximum tax rate preference.")

    max_roth_conversion_tax_rate = st.number_input(
        "Maximum Tax Rate for Conversions (%)",
        min_value=0,
        max_value=37,
        value=int(config_mgr.get("tax_strategy", "max_roth_conversion_tax_rate", 12)),
        help="Maximum marginal tax rate you're willing to pay for Roth conversions",
        key="max_roth_conversion_tax_rate"
    )

    
    # Charitable Giving Section
    st.markdown("---")
    st.subheader("🎁 Charitable Giving")

    # Placeholder: Charitable Giving Summary will be rendered here (after inputs are collected)
    _cg_summary_placeholder = st.empty()

    st.markdown("Configure your charitable giving strategy and Donor Advised Fund (DAF) contributions.")

    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("**Annual Charitable Contributions**")
        annual_charitable_giving = st.number_input(
            "Annual Charitable Giving Goal ($)",
            min_value=0,
            max_value=1000000,
            value=config_mgr.get("charitable_giving", "annual_charitable_giving", 0),
            step=1000,
            help="Your target annual charitable giving amount",
            key="annual_charitable_giving"
        )
        
        charitable_giving_start_age = st.number_input(
            "Start Age for Charitable Giving",
            min_value=50,
            max_value=100,
            value=config_mgr.get("charitable_giving", "charitable_giving_start_age", 65),
            help="Age when you plan to start regular charitable giving",
            key="charitable_giving_start_age"
        )

        charitable_giving_end_age = st.number_input(
            "End Age for Charitable Giving",
            min_value=50,
            max_value=110,
            value=config_mgr.get("charitable_giving", "charitable_giving_end_age", 95),
            help="Age when you plan to stop charitable giving (used to calculate Projected Lifetime Giving)",
            key="charitable_giving_end_age"
        )
        
        charitable_giving_inflation_rate = st.number_input(
            "Charitable Giving Inflation Rate (%)",
            min_value=0.0,
            max_value=10.0,
            value=config_mgr.get("charitable_giving", "charitable_giving_inflation_rate", 2.0),
            step=0.1,
            help="Expected annual increase in charitable giving",
            key="charitable_giving_inflation_rate"
        )
    
    with col4:
        st.markdown("**Donor Advised Fund (DAF)**")

        # ── DAF setup status checkbox ──────────────────────────────────────
        has_daf = st.checkbox(
            "I already have a Donor Advised Fund set up",
            value=config_mgr.get("charitable_giving", "has_daf", False),
            key="has_daf",
            help="Check this if you have already opened a DAF account (e.g. Fidelity Charitable, "
                 "Schwab Charitable, Vanguard Charitable).",
        )

        # Initialize DAF variables with config defaults (overridden by widgets when has_daf is True)
        daf_initial_contribution = config_mgr.get("charitable_giving", "daf_initial_contribution", 0)
        daf_annual_contribution = config_mgr.get("charitable_giving", "daf_annual_contribution", 0)
        daf_contribution_start_age = config_mgr.get("charitable_giving", "daf_contribution_start_age", 60)
        daf_contribution_end_age = config_mgr.get("charitable_giving", "daf_contribution_end_age", 75)
        daf_provider = config_mgr.get("charitable_giving", "daf_provider", "")

        if not has_daf:
            with st.expander("💡 What is a Donor Advised Fund and how do I set one up?", expanded=False):
                st.markdown("""
**What is a Donor Advised Fund (DAF)?**

A DAF is a charitable giving account sponsored by a public charity (the "sponsoring organization").
You make an irrevocable contribution of cash or appreciated securities, receive an **immediate tax
deduction**, and then recommend grants to your favorite charities over time — on your own schedule.

DAFs are not just a retirement vehicle — they can be used at **any stage of your financial life**:
accumulation years, early retirement, or as part of your estate plan.

**Key benefits:**
- 📋 **Immediate deduction** in the year you contribute, even if grants are distributed later.
- 📈 **Donate appreciated securities** (stocks, mutual funds) directly — you avoid capital gains
  tax on the embedded gain AND deduct the full fair-market value.
- 🗓️ **Bundling strategy:** Contribute 2–5 years of giving in one year to exceed the standard
  deduction and itemize; take the standard deduction in the other years.
- 💰 **Tax-free growth:** Assets in the DAF grow tax-free until distributed to charities.
- 🏦 **QCD alternative in retirement:** Once you reach age 73 and must take RMDs, consider
  Qualified Charitable Distributions (QCDs) directly from your IRA instead — up to $105,000/yr
  tax-free, satisfying your RMD without increasing your AGI.

**How to open a DAF (takes ~15 minutes online):**

| Provider | Minimum | Notes |
|---|---|---|
| [Fidelity Charitable](https://www.fidelitycharitable.org) | $5,000 | No annual fees; broad investment options |
| [Schwab Charitable](https://www.schwabcharitable.org) | $5,000 | Integrates with Schwab brokerage |
| [Vanguard Charitable](https://www.vanguardcharitable.org) | $25,000 | Low-cost index fund options |
| [National Philanthropic Trust](https://www.nptrust.org) | $10,000 | Independent, advisor-friendly |

**Steps:**
1. Choose a sponsoring organization (above).
2. Open the account online — similar to opening a brokerage account.
3. Make your initial contribution (cash or appreciated securities).
4. Invest the assets in the DAF's available funds.
5. Recommend grants to IRS-qualified charities at any time.

> ⚠️ *Contributions to a DAF are irrevocable — the assets must eventually go to charity.*
> *Consult a tax advisor to confirm the strategy fits your situation.*
                """)
        else:
            st.success("✅ DAF account configured.")

            # ── Provider selection ─────────────────────────────────────────
            _daf_providers = [
                "Fidelity Charitable",
                "Schwab Charitable",
                "Vanguard Charitable",
                "National Philanthropic Trust",
                "American Endowment Foundation",
                "Goldman Sachs Philanthropy Fund",
                "Other",
            ]
            _saved_provider = config_mgr.get("charitable_giving", "daf_provider", "")
            # Determine the selectbox index: match saved value or default to first item
            if _saved_provider in _daf_providers:
                _provider_index = _daf_providers.index(_saved_provider)
            elif _saved_provider and _saved_provider not in _daf_providers:
                # Previously saved a custom "Other" name — show "Other" selected
                _provider_index = _daf_providers.index("Other")
            else:
                _provider_index = 0

            _provider_choice = st.selectbox(
                "DAF Provider",
                options=_daf_providers,
                index=_provider_index,
                help="Select the sponsoring organization where your DAF is held. "
                     "Used for estate planning documentation.",
                key="daf_provider_choice",
            )

            if _provider_choice == "Other":
                _custom_provider = st.text_input(
                    "Provider name",
                    value=_saved_provider if _saved_provider not in _daf_providers else "",
                    placeholder="e.g. Community Foundation of Greater Atlanta",
                    key="daf_provider_custom",
                )
                daf_provider = _custom_provider.strip() if _custom_provider.strip() else "Other"
            else:
                daf_provider = _provider_choice

            st.info(
                "🔗 **DAF Bundling Advisor:** For a full analysis — including identifying "
                "appreciated securities to donate, computing exact tax savings, and modeling "
                "multi-year bundling scenarios — visit **Portfolio → Tax Harvesting → "
                "DAF Bundling Advisor**."
            )

            st.markdown("---")

            daf_initial_contribution = st.number_input(
                "Initial DAF Contribution ($)",
                min_value=0,
                max_value=10000000,
                value=config_mgr.get("charitable_giving", "daf_initial_contribution", 0),
                step=5000,
                help="One-time initial contribution to establish your DAF",
                key="daf_initial_contribution"
            )

            daf_contribution_start_age = st.number_input(
                "DAF Contribution Start Age",
                min_value=18,
                max_value=100,
                value=config_mgr.get("charitable_giving", "daf_contribution_start_age", 60),
                help="Age when you plan to start making DAF contributions",
                key="daf_contribution_start_age"
            )

            daf_contribution_end_age = st.number_input(
                "DAF Contribution End Age",
                min_value=18,
                max_value=100,
                value=config_mgr.get("charitable_giving", "daf_contribution_end_age", 75),
                help="Age when you plan to stop making DAF contributions",
                key="daf_contribution_end_age"
            )

            # ── Optimal bundling suggestion ────────────────────────────────
            _rmd_age = 73
            _giving_years = max(1, daf_contribution_end_age - daf_contribution_start_age)
            _std_ded = 30_000  # 2025 MFJ standard deduction reference

            if annual_charitable_giving > 0:
                # Compute optimal bundle interval to EXCEED (not just meet) the standard deduction.
                # Need: interval * annual_giving > std_ded  →  interval > std_ded / annual_giving
                # So: interval = floor(std_ded / annual_giving) + 1
                _opt_interval = (_std_ded // annual_charitable_giving) + 1
                _opt_interval = max(2, min(int(_opt_interval), 5))
                _opt_bundle_amt = annual_charitable_giving * _opt_interval
                # Number of bundle events over the contribution window
                _num_bundles = max(1, _giving_years // _opt_interval)
                # Suggested annual contribution = total giving spread over bundle interval
                daf_annual_contribution = int(_opt_bundle_amt)

                st.markdown("#### 💡 Suggested DAF Contribution Strategy")
                _sug_col1, _sug_col2 = st.columns(2)
                with _sug_col1:
                    st.metric(
                        "Suggested Bundle Interval",
                        f"Every {_opt_interval} years",
                        help=f"Contribute {_opt_interval} years of giving at once to exceed the "
                             f"${_std_ded:,} standard deduction and itemize.",
                    )
                    st.metric(
                        "Bundle Contribution Amount",
                        f"${_opt_bundle_amt:,.0f}",
                        help=f"{_opt_interval} × ${annual_charitable_giving:,.0f}/yr",
                    )
                with _sug_col2:
                    st.metric(
                        "Estimated Bundle Events",
                        f"~{_num_bundles}",
                        help=f"Over your {_giving_years}-year contribution window "
                             f"(age {daf_contribution_start_age}–{daf_contribution_end_age}).",
                    )
                    # Total Lifetime DAF Contributions = giving from start age to age 73
                    # (after 73, QCDs from Traditional IRA take over — see QCD Potential above)
                    _sug_daf_end = min(73, charitable_giving_end_age)
                    _sug_daf_years = max(0, _sug_daf_end - charitable_giving_start_age)
                    _sug_daf_total = annual_charitable_giving * _sug_daf_years
                    st.metric(
                        "Total Lifetime DAF Contributions",
                        f"${_sug_daf_total:,.0f}",
                        help=(
                            f"Giving from age {charitable_giving_start_age} to {_sug_daf_end} "
                            f"({_sug_daf_years} yrs × ${annual_charitable_giving:,.0f}/yr). "
                            f"Funded via {_num_bundles} bundled DAF contribution(s) of "
                            f"${_opt_bundle_amt:,.0f} each (every {_opt_interval} years) from "
                            f"Brokerage/cash. After age 73, QCDs from your Traditional IRA "
                            f"satisfy giving tax-free. "
                            f"Matches 'Total DAF Contributions' in the Charitable Giving Summary above."
                        ),
                    )

                # QCD tip when RMD age falls within or after the contribution window
                if daf_contribution_end_age >= _rmd_age:
                    st.info(
                        f"**💡 QCD Tip:** Once you reach age **{_rmd_age}** and must take Required "
                        f"Minimum Distributions (RMDs), consider switching from DAF contributions "
                        f"to **Qualified Charitable Distributions (QCDs)** directly from your IRA. "
                        f"QCDs satisfy your RMD (up to **\\$105,000/yr** in 2025) and are excluded "
                        f"from your taxable income entirely — more tax-efficient than a DAF "
                        f"contribution in most cases. You can use both strategies: DAF for "
                        f"bundling appreciated securities, QCD for satisfying RMDs tax-free."
                    )
            else:
                daf_annual_contribution = config_mgr.get("charitable_giving", "daf_annual_contribution", 0)
        
    
    # ── Charitable Giving Summary (rendered into placeholder above the config inputs) ──
    if annual_charitable_giving > 0 or (has_daf and daf_initial_contribution > 0) or (has_daf and daf_annual_contribution > 0):
        # ── Split giving into DAF window (pre-73) and QCD window (73+) ───
        # DAF contributions: funded from Brokerage/cash via bundled contributions.
        #   Window: charitable_giving_start_age → min(73, charitable_giving_end_age)
        # QCD potential: funded from Traditional IRA, tax-free (age 73+, up to $105k/yr).
        #   Window: max(73, charitable_giving_start_age) → charitable_giving_end_age
        # Projected Lifetime Giving = DAF portion + QCD portion (they don't overlap).
        _qcd_threshold = 73
        _daf_end_age = min(_qcd_threshold, charitable_giving_end_age)
        _daf_years = max(0, _daf_end_age - charitable_giving_start_age)
        _qcd_start_age = max(_qcd_threshold, charitable_giving_start_age)
        _qcd_years = max(0, charitable_giving_end_age - _qcd_start_age)

        total_daf_contributions = annual_charitable_giving * _daf_years
        _qcd_amount = annual_charitable_giving * _qcd_years
        lifetime_giving = total_daf_contributions + _qcd_amount  # == annual × total_years

        if has_daf and annual_charitable_giving > 0:
            _cg_bundle_help = (
                f"Giving from age {charitable_giving_start_age} to {_daf_end_age} "
                f"(before QCDs begin at 73): "
                f"${annual_charitable_giving:,.0f}/yr × {_daf_years} yrs = "
                f"${total_daf_contributions:,.0f}. "
                f"Funded via bundled DAF contributions from Brokerage/cash "
                f"(see Suggested DAF Contribution Strategy below)."
            )
        elif has_daf:
            _cg_bundle_help = (
                f"Annual contributions of ${daf_annual_contribution:,.0f} "
                f"from age {daf_contribution_start_age} to {daf_contribution_end_age}."
            )
        else:
            _cg_bundle_help = "No DAF configured. Check 'I already have a Donor Advised Fund set up' to add DAF contributions."

        # Render the summary into the placeholder defined above the config inputs
        with _cg_summary_placeholder.container():
            st.subheader("Charitable Giving Summary")
            col_char1, col_char2, col_char3, col_char4 = st.columns(4)

            with col_char1:
                st.metric(
                    "Annual Charitable Goal",
                    f"${annual_charitable_giving:,.0f}",
                    help="Your target annual charitable giving amount",
                )

            with col_char2:
                st.metric(
                    "Total DAF Contributions",
                    f"${total_daf_contributions:,.0f}",
                    help=_cg_bundle_help,
                )

            with col_char3:
                st.metric(
                    "QCD Potential",
                    f"${_qcd_amount:,.0f}",
                    help=(
                        f"Giving from age {_qcd_start_age} to {charitable_giving_end_age} "
                        f"({_qcd_years} yr{'s' if _qcd_years != 1 else ''}) fulfilled via "
                        f"**Qualified Charitable Distributions (QCDs)** directly from your "
                        f"Traditional IRA. QCDs satisfy RMDs (up to $105,000/yr) and are "
                        f"excluded from taxable income — more tax-efficient than a DAF "
                        f"contribution. Funded from Traditional IRA (not Brokerage/cash)."
                        if _qcd_years > 0 else
                        "Set your End Age for Charitable Giving above 73 to see QCD-eligible years."
                    ),
                )

            with col_char4:
                _cg_giving_years = max(0, charitable_giving_end_age - charitable_giving_start_age)
                st.metric(
                    "Projected Lifetime Giving",
                    f"${lifetime_giving:,.0f}",
                    help=(
                        f"Total giving from age {charitable_giving_start_age} to "
                        f"{charitable_giving_end_age} ({_cg_giving_years} yrs): "
                        f"**DAF** ${total_daf_contributions:,.0f} (age {charitable_giving_start_age}–{_daf_end_age}) "
                        f"+ **QCD** ${_qcd_amount:,.0f} (age {_qcd_start_age}–{charitable_giving_end_age}). "
                        f"Not adjusted for inflation."
                    ),
                )
            st.markdown("---")

        # ── DAF Bundling Suggestion ────────────────────────────────────────
        # 2025 standard deduction: MFJ $30,000 / Single $15,000
        # Use a conservative MFJ figure as the default reference.
        _std_ded_mfj_2025 = 30_000

        if annual_charitable_giving > 0 and annual_charitable_giving < _std_ded_mfj_2025:
            # Determine how many years to bundle to EXCEED (not just meet) the standard deduction.
            # We need: bundle_years * annual_giving > std_ded
            # i.e. bundle_years > std_ded / annual_giving
            # So bundle_years = floor(std_ded / annual_giving) + 1
            _bundle_years = (_std_ded_mfj_2025 // annual_charitable_giving) + 1
            _bundle_years = max(2, min(int(_bundle_years), 5))
            _bundled_amount = annual_charitable_giving * _bundle_years

            st.markdown("---")
            st.markdown("#### 💡 DAF Bundling Opportunity Detected")
            st.warning(
                f"Your annual charitable giving of **\\${annual_charitable_giving:,.0f}** is below the "
                f"2025 standard deduction (**\\${_std_ded_mfj_2025:,.0f}** MFJ). "
                f"This means you likely receive **no tax benefit** from your charitable giving each year "
                f"because you take the standard deduction instead of itemizing."
            )

            _bundle_col1, _bundle_col2, _bundle_col3 = st.columns(3)
            with _bundle_col1:
                st.metric(
                    "Suggested Bundle",
                    f"{_bundle_years} years",
                    help=f"Front-load {_bundle_years} years of giving into one DAF contribution.",
                )
            with _bundle_col2:
                st.metric(
                    "Bundled Contribution",
                    f"${_bundled_amount:,.0f}",
                    help=f"{_bundle_years} × ${annual_charitable_giving:,.0f}/yr contributed to DAF in one year.",
                )
            with _bundle_col3:
                _excess = max(0, _bundled_amount - _std_ded_mfj_2025)
                st.metric(
                    "Itemized Deduction Excess",
                    f"${_excess:,.0f}",
                    help="Amount above the standard deduction — this generates real tax savings.",
                )

            st.info(
                f"**How bundling works:** Instead of giving \\${annual_charitable_giving:,.0f}/year "
                f"(and never exceeding the standard deduction), contribute "
                f"**\\${_bundled_amount:,.0f}** to a Donor Advised Fund every {_bundle_years} years. "
                f"In the bundle year you **itemize** and deduct the full amount. "
                f"In the other {_bundle_years - 1} year(s) you take the standard deduction. "
                f"The DAF distributes grants to your charities on your normal schedule — "
                f"your charities receive the same amount, but you get a larger tax deduction. "
                f"\n\n**Best practice:** Donate **appreciated securities** (low-cost-basis stock) "
                f"to the DAF instead of cash — you avoid capital gains tax on the gain AND "
                f"deduct the full fair-market value. See the 🌾 Tax Harvesting tab for candidates."
            )

            if not has_daf:
                st.error(
                    "⚠️ You don't have a DAF set up yet. Open the **'I already have a Donor Advised Fund'** "
                    "checkbox above to see setup instructions. Opening a DAF takes about 15 minutes online."
                )
        else:
            st.info("💡 **Tax Benefits:** Charitable contributions and DAF contributions may provide significant tax deductions. Consult with a tax advisor to optimize your giving strategy.")

# Portfolio Data Tab
with tab6:
    st.header("Portfolio Data Configuration")
    st.markdown("Enter your portfolio holdings. This data will be saved to `portfolio_data_truth.csv`.")
    
    # Important notice about data requirements
    st.info("⚠️ **Important:** You need at least 2 months of portfolio data for the application to work properly. Make sure to enter holdings for at least two different months.")
    
    # Accounts Section
    st.subheader("📋 Account Configuration")
    st.markdown("Define your investment accounts. These will be available when entering portfolio holdings.")
    
    # Initialize session state for accounts
    if 'accounts_list' not in st.session_state:
        # Try to load from config or use defaults
        st.session_state['accounts_list'] = config_mgr.get("portfolio_accounts", "accounts", [
            {"account_name": "Schwab", "account_type": "Roth"},
            {"account_name": "Fidelity", "account_type": "Traditional"},
            {"account_name": "Vanguard", "account_type": "Brokerage"}
        ])
    
    # Display accounts in a data editor
    accounts_df = pd.DataFrame(st.session_state['accounts_list'])
    if accounts_df.empty:
        accounts_df = pd.DataFrame(columns=pd.Index(['account_name', 'account_type']))
    
    col_acc1, col_acc2, col_acc3 = st.columns([2, 1, 1])
    
    with col_acc1:
        st.markdown("**Your Accounts:**")
    
    with col_acc2:
        if st.button("➕ Add Account", width='stretch', key="add_account_btn"):
            new_account = pd.DataFrame({
                'account_name': ['New Account'],
                'account_type': ['Brokerage']
            })
            accounts_df = pd.concat([accounts_df, new_account], ignore_index=True)
            st.session_state['accounts_list'] = accounts_df.to_dict('records')
            st.rerun()
    
    with col_acc3:
        if st.button("💾 Save Accounts", width='stretch', key="save_accounts_btn"):
            config_mgr.update_section("portfolio_accounts", {
                "accounts": st.session_state['accounts_list']
            })
            if config_mgr.save_config():
                st.success("✅ Accounts saved!")
            else:
                st.error("❌ Error saving accounts")
    
    # Configure column settings for accounts editor
    accounts_column_config = {
        'account_name': st.column_config.TextColumn('Account Name', required=True, help="Name of your investment account"),
        'account_type': st.column_config.SelectboxColumn('Account Type', options=VALID_ACCOUNT_TYPES, required=True, help="Type of account")
    }
    
    # Display editable accounts dataframe
    edited_accounts_df = st.data_editor(
        accounts_df,
        column_config=accounts_column_config,
        num_rows="dynamic",
        width='stretch',
        hide_index=True,
        key="accounts_editor"
    )
    
    # Update session state with edited accounts
    st.session_state['accounts_list'] = edited_accounts_df.to_dict('records')
    
    st.markdown("---")
    
    # Initialize session state for portfolio data
    if 'portfolio_df' not in st.session_state:
        # Try to load existing data
        if os.path.exists('portfolio_data_truth.csv'):
            try:
                st.session_state['portfolio_df'] = pd.read_csv('portfolio_data_truth.csv')
            except Exception as e:
                st.error(f"Error loading portfolio data: {e}")
                st.session_state['portfolio_df'] = pd.DataFrame(columns=pd.Index([
                    'month', 'year', 'account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
                ]))
        else:
            st.session_state['portfolio_df'] = pd.DataFrame(columns=pd.Index([
                'month', 'year', 'account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
            ]))
    
    # Month/Year selector for loading prior month data
    _now = datetime.now()
    _sel_col1, _sel_col2, _ = st.columns([1, 1, 4])
    with _sel_col1:
        entry_month = st.number_input("Month", min_value=1, max_value=12,
                                      value=_now.month, step=1, key="cfg_entry_month")
    with _sel_col2:
        entry_year = st.number_input("Year", min_value=2000, max_value=2100,
                                     value=_now.year, step=1, key="cfg_entry_year")

    # File management buttons — row 1
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📂 Load Current Data", use_container_width=True):
            if os.path.exists('portfolio_data_truth.csv'):
                try:
                    st.session_state['portfolio_df'] = pd.read_csv('portfolio_data_truth.csv')
                    st.success(f"Loaded {len(st.session_state['portfolio_df'])} rows from portfolio_data_truth.csv")
                except Exception as e:
                    st.error(f"Error loading data: {e}")
            else:
                st.warning("portfolio_data_truth.csv not found")

    with col2:
        if st.button("➕ Add Empty Row", use_container_width=True):
            new_row = pd.DataFrame({
                'month': [entry_month],
                'year': [entry_year],
                'account_name': [''],
                'account_type': ['Brokerage'],
                'symbol': [''],
                'name': [''],
                'sector': [''],
                'qty': [0.0],
                'purchase_price': [0.0]
            })
            # Prepend new row so it appears at the top of the reversed display
            st.session_state['portfolio_df'] = pd.concat(
                [new_row, st.session_state['portfolio_df']], ignore_index=True
            )
            st.rerun()

    with col3:
        # Determine the "last month" to copy from
        if _now.month == 1:
            _src_month, _src_year = 12, _now.year - 1
        else:
            _src_month, _src_year = _now.month - 1, _now.year
        _tgt_month, _tgt_year = _now.month, _now.year

        if st.button(
            f"📋 Copy {_src_month}/{_src_year} → {_tgt_month}/{_tgt_year}",
            use_container_width=True,
            help=f"Copies all entries from {_src_month}/{_src_year}, updates month/year to "
                 f"{_tgt_month}/{_tgt_year}, and prepends them for editing."
        ):
            existing = st.session_state['portfolio_df']
            last_month_rows = existing[
                (existing['month'] == _src_month) & (existing['year'] == _src_year)
            ].copy()

            if last_month_rows.empty:
                st.warning(
                    f"No entries found for {_src_month}/{_src_year}. "
                    "Load the data first or check the source month."
                )
            else:
                # Update month/year to current month
                last_month_rows['month'] = _tgt_month
                last_month_rows['year']  = _tgt_year
                # Prepend copied rows so they appear at the top of the reversed display
                st.session_state['portfolio_df'] = pd.concat(
                    [last_month_rows, existing], ignore_index=True
                )
                st.success(
                    f"✅ Copied {len(last_month_rows)} entries from "
                    f"{_src_month}/{_src_year} → {_tgt_month}/{_tgt_year}. "
                    "Review and edit above, then save."
                )
                st.rerun()

    with col4:
        if st.button("🗑️ Clear All", use_container_width=True):
            st.session_state['portfolio_df'] = pd.DataFrame(columns=pd.Index([
                'month', 'year', 'account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
            ]))
            st.rerun()

    # File management buttons — row 2 (ticker validation & backup/restore)
    col5, col6, col7 = st.columns(3)

    with col5:
        if st.button("🔍 Validate & Lookup Tickers", use_container_width=True,
                     help="Validates all ticker symbols against Yahoo Finance and auto-fills Name and Sector"):
            current_df = st.session_state['portfolio_df']
            non_empty = current_df[current_df['symbol'].str.strip() != ''].copy()
            if non_empty.empty:
                st.warning("No entries to validate. Add rows with ticker symbols first.")
            else:
                validation_results = []
                with st.spinner("Validating ticker symbols with Yahoo Finance..."):
                    for idx, row in non_empty.iterrows():
                        symbol = str(row['symbol']).strip().upper()
                        is_valid, name, sector, error = validate_ticker_symbol(symbol)
                        if is_valid:
                            non_empty.at[idx, 'name'] = name
                            non_empty.at[idx, 'sector'] = sector
                            validation_results.append({'Symbol': symbol, 'Status': '✅ Valid', 'Name': name, 'Sector': sector})
                        else:
                            validation_results.append({'Symbol': symbol, 'Status': '❌ Invalid', 'Name': '', 'Sector': error})
                # Merge validated rows back into full dataframe
                st.session_state['portfolio_df'].update(non_empty)
                results_df = pd.DataFrame(validation_results)
                invalid_count = sum(1 for r in validation_results if '❌' in r['Status'])
                if invalid_count == 0:
                    st.success(f"✅ All {len(validation_results)} ticker symbols validated successfully!")
                else:
                    st.error(f"❌ {invalid_count} invalid ticker symbol(s). Please correct them before saving.")
                st.dataframe(results_df, width='stretch', hide_index=True)
                st.rerun()

    with col6:
        if st.button("🆕 Start from Scratch", type="secondary", use_container_width=True,
                     help="Backs up current data and creates a blank portfolio file"):
            if 'cfg_confirm_scratch' not in st.session_state:
                st.session_state.cfg_confirm_scratch = False
            if not st.session_state.cfg_confirm_scratch:
                st.session_state.cfg_confirm_scratch = True
                st.warning("⚠️ This will backup your current data and create a blank file. Click again to confirm.")
                st.rerun()
            else:
                with st.spinner("Creating backup and blank file..."):
                    success, message = start_from_scratch()
                if success:
                    st.success(f"✅ {message}")
                    st.cache_data.clear()
                    st.session_state['portfolio_df'] = create_empty_entry_template(entry_month, entry_year)
                    st.session_state.cfg_confirm_scratch = False
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
                    st.session_state.cfg_confirm_scratch = False

    with col7:
        if st.button("⏮️ Revert to Last Backup", type="secondary", use_container_width=True,
                     help="Restores the most recent backup of portfolio_data_truth.csv"):
            if 'cfg_confirm_revert' not in st.session_state:
                st.session_state.cfg_confirm_revert = False
            if not st.session_state.cfg_confirm_revert:
                st.session_state.cfg_confirm_revert = True
                st.warning("⚠️ This will restore the most recent backup. Click again to confirm.")
                st.rerun()
            else:
                with st.spinner("Reverting to last backup..."):
                    success, message = revert_to_last_backup()
                if success:
                    st.success(f"✅ {message}")
                    st.cache_data.clear()
                    st.session_state['portfolio_df'] = pd.read_csv('portfolio_data_truth.csv') \
                        if os.path.exists('portfolio_data_truth.csv') else create_empty_entry_template(entry_month, entry_year)
                    st.session_state.cfg_confirm_revert = False
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
                    st.session_state.cfg_confirm_revert = False
    
    st.markdown("---")
    
    # Display data editor
    st.subheader("Portfolio Holdings")
    
    # Configure column settings for the data editor
    column_config = {
        'month': st.column_config.NumberColumn('Month', min_value=1, max_value=12, step=1, required=True),
        'year': st.column_config.NumberColumn('Year', min_value=2000, max_value=2100, step=1, required=True),
        'account_name': st.column_config.TextColumn('Account Name', required=True),
        'account_type': st.column_config.SelectboxColumn('Account Type', options=VALID_ACCOUNT_TYPES, required=True),
        'symbol': st.column_config.TextColumn('Symbol', required=True),
        'name': st.column_config.TextColumn('Name', required=True),
        'sector': st.column_config.SelectboxColumn('Sector', options=VALID_SECTORS, required=True),
        'qty': st.column_config.NumberColumn('Quantity', min_value=0, step=0.01, format="%.2f", required=True),
        'purchase_price': st.column_config.NumberColumn('Purchase Price', min_value=0, step=0.01, format="%.2f", required=True)
    }
    
    # Display editable dataframe — reversed so newest entries appear at top
    display_df = st.session_state['portfolio_df'].iloc[::-1].reset_index(drop=True)
    edited_df = st.data_editor(
        display_df,
        column_config=column_config,
        num_rows="dynamic",
        width='stretch',
        hide_index=True,
        key="portfolio_editor"
    )

    # Reverse back to chronological order before storing in session state
    # (preserves original append-order for CSV saves)
    st.session_state['portfolio_df'] = edited_df.iloc[::-1].reset_index(drop=True)
    
    st.markdown("---")
    
    # ------------------------------------------------------------------ #
    # Validation alert dialog                                              #
    # ------------------------------------------------------------------ #
    @st.dialog("⚠️ Validation Errors — Cannot Save")
    def _show_validation_errors_dialog(invalid_df: pd.DataFrame, valid_df: pd.DataFrame) -> None:
        """Modal dialog shown when save is attempted with invalid rows."""
        st.error(
            f"**{len(invalid_df)} row(s) failed validation** and cannot be saved. "
            "Review the errors below, fix them in the editor, then try saving again."
        )
        # Show the invalid rows with their error messages
        error_cols = [c for c in ['month', 'year', 'account_name', 'symbol', 'validation_error']
                      if c in invalid_df.columns]
        st.dataframe(invalid_df[error_cols], hide_index=True, width='stretch')

        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔙 Fix Errors & Cancel", type="secondary", use_container_width=True):
                st.rerun()   # closes the dialog
        with col_b:
            save_anyway_disabled = len(valid_df) == 0
            if st.button(
                f"💾 Save {len(valid_df)} Valid Rows Anyway",
                type="primary",
                use_container_width=True,
                disabled=save_anyway_disabled,
            ):
                _do_save(valid_df)

    def _do_save(df_to_save: pd.DataFrame) -> None:
        """Perform the actual CSV save with backup, then refresh the portfolio display cache."""
        try:
            if os.path.exists('portfolio_data_truth.csv'):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f'portfolio_data_truth_{timestamp}.csv'
                shutil.copy2('portfolio_data_truth.csv', backup_name)
                st.info(f"✅ Backed up existing data to {backup_name}")
            df_to_save.to_csv('portfolio_data_truth.csv', index=False)
            st.success(f"✅ Successfully saved {len(df_to_save)} rows to portfolio_data_truth.csv")

            # ── Refresh portfolio display cache ───────────────────────────
            # Clear the cached result so the next call fetches fresh data
            # from the newly saved CSV, then pre-warm the cache immediately.
            build_portfolio_display.clear()
            try:
                # Determine the most recent month/year from the saved data
                _save_month = int(df_to_save['month'].max()) if 'month' in df_to_save.columns else None
                _save_year  = int(df_to_save['year'].max())  if 'year'  in df_to_save.columns else None
                with st.spinner("📈 Refreshing portfolio display — fetching live prices…"):
                    build_portfolio_display(month=_save_month, year=_save_year)
                st.success("✅ Portfolio display refreshed with new data.")
            except Exception as _cache_err:
                st.warning(f"⚠️ Portfolio saved, but cache refresh failed: {_cache_err}")

            st.balloons()
        except Exception as e:
            st.error(f"Error saving portfolio data: {e}")

    # ------------------------------------------------------------------ #
    # Save section UI                                                      #
    # ------------------------------------------------------------------ #
    st.subheader("Save Portfolio Data")

    col_save1, col_save2 = st.columns(2)

    with col_save1:
        st.info(f"**Current rows:** {len(edited_df)}")

        # Live validation summary (always visible)
        if len(edited_df) > 0:
            valid_df, invalid_df = validate_portfolio_dataframe(edited_df)
            if len(invalid_df) > 0:
                st.warning(f"⚠️ {len(invalid_df)} row(s) have validation errors — fix before saving.")
            if len(valid_df) > 0:
                st.success(f"✅ {len(valid_df)} row(s) are valid and ready to save.")
        else:
            valid_df = pd.DataFrame()
            invalid_df = pd.DataFrame()

    with col_save2:
        if st.button("💾 Save Portfolio Data", type="primary", use_container_width=True, disabled=len(edited_df) == 0):
            # Re-validate at save time
            valid_df_save, invalid_df_save = validate_portfolio_dataframe(edited_df)

            if len(invalid_df_save) > 0:
                # Open blocking modal alert listing all errors
                _show_validation_errors_dialog(invalid_df_save, valid_df_save)
            elif len(valid_df_save) == 0:
                st.error("No valid data to save.")
            else:
                _do_save(valid_df_save)
    
    # Display sample data format
    with st.expander("📋 View Sample Data Format", expanded=False):
        st.markdown("""
        **Required Columns:**
        - `month`: Month (1-12)
        - `year`: Year (e.g., 2026)
        - `account_name`: Name of the account (e.g., "Fidelity", "Schwab")
        - `account_type`: Type of account (Cash, Brokerage, Traditional, Roth)
        - `symbol`: Ticker symbol (e.g., "AAPL", "MF:CASH")
        - `name`: Security name (e.g., "Apple Inc.", "Money Market")
        - `sector`: Sector classification
        - `qty`: Quantity/shares owned
        - `purchase_price`: Purchase price per share
        """)
        
        sample_data = pd.DataFrame({
            'month': [1, 1],
            'year': [2026, 2026],
            'account_name': ['Schwab', 'Fidelity'],
            'account_type': ['Brokerage', 'Traditional'],
            'symbol': ['AAPL', 'MF:CASH'],
            'name': ['Apple Inc.', 'Money Market'],
            'sector': ['Technology', 'MF:Cash'],
            'qty': [100.0, 50000.0],
            'purchase_price': [150.0, 1.0]
        })
        st.dataframe(sample_data, width='stretch')

# Advanced Tab
with tab8:
    st.header("Advanced Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Configuration Management")
        
        if st.button("💾 Save All Changes", type="primary", width='stretch'):
            # Update all configuration values
            config_mgr.update_section("personal_info", {
                "person1_name": person1_name,
                "person1_birth_date": person1_birth_date.strftime("%Y-%m-%d"),
                "person1_retirement_age": person1_retirement_age,
                "person2_name": person2_name,
                "person2_birth_date": person2_birth_date.strftime("%Y-%m-%d"),
                "person2_retirement_age": person2_retirement_age,
                "retirement_state": retirement_state,
                "children": _valid_children,
            })
            
            config_mgr.update_section("financial_assumptions", {
                "expected_annual_expenses": expected_annual_expenses,
                "expense_inflation_rate": expense_inflation_rate,
                "expected_rate_of_return": expected_rate_of_return,
                "years_of_expenses_in_cash": years_of_expenses_in_cash,
                "accumulation_cash_buffer_months": accumulation_cash_buffer_months,
            })
            
            config_mgr.update_section("healthcare", {
                "aca_marketplace_enrolled": aca_marketplace_enrolled,
                "person1_aca_insurance_monthly": person1_aca_insurance_monthly,
                "person1_aca_start_age": person1_aca_start_age,
                "person1_aca_end_age": person1_aca_end_age,
                "person1_medicare_start_age": person1_medicare_start_age,
                "person2_aca_insurance_monthly": person2_aca_insurance_monthly,
                "person2_aca_start_age": person2_aca_start_age,
                "person2_aca_end_age": person2_aca_end_age,
                "person2_medicare_start_age": person2_medicare_start_age,
            })
            
            config_mgr.update_section("social_security", {
                "person1_ssi_age": person1_ssi_age,
                "person1_ssi_amount": person1_ssi_amount,
                "person2_ssi_age": person2_ssi_age,
                "person2_ssi_amount": person2_ssi_amount,
            })
            
            config_mgr.update_section("income", {
                "person1_annual_wages": person1_annual_wages,
                "person2_annual_wages": person2_annual_wages,
                "wage_inflation_rate": wage_inflation_rate,
                "contribution_401k_percent": st.session_state.get("contribution_401k_percent", config_mgr.get("income", "contribution_401k_percent", 10.0)),
                "contribution_roth_percent": st.session_state.get("contribution_roth_percent", config_mgr.get("income", "contribution_roth_percent", 5.0)),
                "contribution_brokerage_percent": st.session_state.get("contribution_brokerage_percent", config_mgr.get("income", "contribution_brokerage_percent", 5.0)),
            })
            
            config_mgr.update_section("tax_strategy", {
                "max_roth_conversion_tax_rate": max_roth_conversion_tax_rate,
            })
            
            config_mgr.update_section("charitable_giving", {
                "annual_charitable_giving": annual_charitable_giving,
                "charitable_giving_start_age": charitable_giving_start_age,
                "charitable_giving_end_age": charitable_giving_end_age,
                "charitable_giving_inflation_rate": charitable_giving_inflation_rate,
                "has_daf": has_daf,
                "daf_provider": daf_provider,
                "daf_initial_contribution": daf_initial_contribution,
                "daf_annual_contribution": daf_annual_contribution,
                "daf_contribution_start_age": daf_contribution_start_age,
                "daf_contribution_end_age": daf_contribution_end_age,
            })
            
            if config_mgr.save_config():
                # Sync configuration to session state for sidebar compatibility
                sync_config_to_session_state()
                st.success("✅ Configuration saved successfully!")
                
                # Generate SSI schedule if SSI amounts are configured
                if person1_ssi_amount > 0 or person2_ssi_amount > 0:
                    try:
                        with st.spinner("Generating SSI schedule..."):
                            # Generate schedule from current year to 30 years out
                            from datetime import datetime
                            start_year = datetime.now().year
                            end_year = start_year + 30
                            
                            ssi_schedule = generate_ssi_schedule_from_config(
                                config_manager=config_mgr,
                                start_year=start_year,
                                end_year=end_year,
                                cola_rate=0.02  # 2% COLA
                            )
                            
                            if not ssi_schedule.empty:
                                export_ssi_schedule_to_csv(ssi_schedule, "ssincome.csv")
                                st.success(f"✅ Generated SSI schedule for {start_year}-{end_year} → ssincome.csv")
                                st.info(f"📊 Schedule contains {len(ssi_schedule)} rows covering both persons")
                            else:
                                st.warning("⚠️ No SSI schedule generated (check that SSI amounts are > 0)")
                    except Exception as e:
                        st.error(f"❌ Error generating SSI schedule: {e}")
                        st.info("💡 You can manually generate the schedule using: python generate_ssi_schedule.py")
                
                st.balloons()
            else:
                st.error("❌ Error saving configuration. Please try again.")
        
        if st.button("🔄 Reset to Defaults", width='stretch'):
            config_mgr.reset_to_defaults()
            if config_mgr.save_config():
                st.success("Configuration reset to defaults. Please refresh the page.")
                st.rerun()
            else:
                st.error("Error resetting configuration.")
        
        if st.button("♻️ Reload from File", width='stretch'):
            reload_config()
            st.success("Configuration reloaded from file. Please refresh the page.")
            st.rerun()
    
    with col2:
        st.subheader("Export/Import")
        
        # Export configuration — bundles config JSON + portfolio CSV + estate planning JSON into one ZIP
        if st.button("📤 Export Configuration", width='stretch'):
            try:
                # Resolve person names for the header comment
                _p1_name = config_mgr.get("personal_info", "person1_name", "Person 1")
                _p2_name = config_mgr.get("personal_info", "person2_name", "Person 2")
                _header_comment = (
                    f"// Primary person: {_p1_name}\n"
                    f"// Spouse: {_p2_name}\n"
                )

                # Build annotated config JSON (comment prepended, valid JSON block follows)
                _config_dict = json.loads(config_mgr.export_config())
                _config_json_bytes = (
                    _header_comment + json.dumps(_config_dict, indent=2)
                ).encode("utf-8")

                # Read portfolio CSV
                _portfolio_bytes = b""
                if os.path.exists("portfolio_data_truth.csv"):
                    with open("portfolio_data_truth.csv", "rb") as _pf:
                        _portfolio_bytes = _pf.read()

                # Read estate planning JSON
                _estate_bytes = b""
                if os.path.exists("estate_planning_data.json"):
                    with open("estate_planning_data.json", "rb") as _ef:
                        _estate_bytes = _ef.read()

                # Pack everything into an in-memory ZIP
                _zip_buffer = io.BytesIO()
                with zipfile.ZipFile(_zip_buffer, "w", zipfile.ZIP_DEFLATED) as _zf:
                    _zf.writestr("retirement_config.json", _config_json_bytes)
                    if _portfolio_bytes:
                        _zf.writestr("portfolio_data_truth.csv", _portfolio_bytes)
                    if _estate_bytes:
                        _zf.writestr("estate_planning_data.json", _estate_bytes)
                _zip_buffer.seek(0)

                _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="⬇️ Download Configuration Bundle (.zip)",
                    data=_zip_buffer.getvalue(),
                    file_name=f"retirement_config_{_ts}.zip",
                    mime="application/zip",
                    width='stretch'
                )
            except Exception as _ex:
                st.error(f"❌ Error building export bundle: {_ex}")
        
        # Import configuration — accepts new ZIP bundle or legacy JSON file
        st.markdown("**Import Configuration**")
        uploaded_file = st.file_uploader(
            "Choose a configuration file (.zip bundle or legacy .json)",
            type=["zip", "json"],
        )
        if uploaded_file is not None:
            try:
                _fname = uploaded_file.name.lower()
                if _fname.endswith(".zip"):
                    # ── New bundled ZIP format ──────────────────────────────
                    _zip_data = io.BytesIO(uploaded_file.read())
                    with zipfile.ZipFile(_zip_data, "r") as _zf:
                        _names = _zf.namelist()
                        
                        # Debug: Show what files are in the ZIP
                        st.info(f"📦 Files found in ZIP: {', '.join(_names)}")
                        
                        # Normalize file names (strip paths, lowercase for comparison)
                        # Handle both forward slashes (Mac/Linux) and backslashes (Windows)
                        _name_map = {}
                        for name in _names:
                            # Get basename by splitting on both / and \
                            basename = name.replace('\\', '/').split('/')[-1]
                            _name_map[basename.lower()] = name

                        # Import retirement_config.json (strip leading comment lines)
                        if "retirement_config.json" in _name_map:
                            _actual_name = _name_map["retirement_config.json"]
                            _raw = _zf.read(_actual_name).decode("utf-8")
                            # Strip any leading // comment lines before parsing JSON
                            _json_lines = [
                                ln for ln in _raw.splitlines()
                                if not ln.strip().startswith("//")
                            ]
                            _config_str = "\n".join(_json_lines)
                            if not config_mgr.import_config(_config_str):
                                st.error("❌ Error parsing retirement_config.json from bundle.")
                                st.stop()
                        else:
                            st.error("❌ ZIP bundle does not contain retirement_config.json.")
                            st.stop()

                        # Restore portfolio CSV
                        if "portfolio_data_truth.csv" in _name_map:
                            _actual_csv = _name_map["portfolio_data_truth.csv"]
                            _csv_bytes = _zf.read(_actual_csv)
                            with open("portfolio_data_truth.csv", "wb") as _out:
                                _out.write(_csv_bytes)
                            st.success("✅ portfolio_data_truth.csv restored.")

                        # Restore estate planning JSON
                        if "estate_planning_data.json" in _name_map:
                            _actual_ep = _name_map["estate_planning_data.json"]
                            _ep_bytes = _zf.read(_actual_ep)
                            with open("estate_planning_data.json", "wb") as _out:
                                _out.write(_ep_bytes)
                            st.success("✅ estate_planning_data.json restored.")

                    if config_mgr.save_config():
                        st.success("✅ Configuration bundle imported successfully! Please refresh the page.")
                        st.rerun()
                    else:
                        st.error("❌ Error saving imported configuration.")

                else:
                    # ── Legacy plain-JSON format ────────────────────────────
                    _raw = uploaded_file.read().decode("utf-8")
                    # Strip any leading // comment lines before parsing JSON
                    _json_lines = [
                        ln for ln in _raw.splitlines()
                        if not ln.strip().startswith("//")
                    ]
                    config_json = "\n".join(_json_lines)
                    if config_mgr.import_config(config_json):
                        if config_mgr.save_config():
                            st.success("✅ Configuration imported successfully! Please refresh the page.")
                            st.rerun()
                        else:
                            st.error("❌ Error saving imported configuration.")
                    else:
                        st.error("❌ Error importing configuration. Please check the file format.")
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
    
    # Display current configuration
    st.subheader("Current Configuration")
    with st.expander("View Raw Configuration", expanded=False):
        st.json(config_mgr.config)
    
    # Display metadata
    metadata = config_mgr.get_section("metadata")
    if metadata.get("last_updated"):
        st.caption(f"Last updated: {metadata['last_updated']}")
    st.caption(f"Version: {metadata.get('version', 'Unknown')}")

# Real Estate Tab
with tab7:
    st.header("🏠 Real Estate")
    st.markdown("Track your real estate properties. Purchase prices are included in your net worth statement.")

    # Initialize session state for real estate
    if 'real_estate_list' not in st.session_state:
        st.session_state['real_estate_list'] = config_mgr.get("real_estate", "properties", [])
    
    # Initialize edit mode state
    if 'real_estate_edit_mode' not in st.session_state:
        st.session_state['real_estate_edit_mode'] = False

    re_df = pd.DataFrame(st.session_state['real_estate_list'])
    if re_df.empty:
        re_df = pd.DataFrame(columns=pd.Index(['property_name', 'address', 'purchase_price']))

    # Ensure required columns exist
    for _col in ['property_name', 'address', 'purchase_price']:
        if _col not in re_df.columns:
            re_df[_col] = '' if _col != 'purchase_price' else 0.0

    re_col1, re_col2, re_col3, re_col4 = st.columns([2, 1, 1, 1])
    with re_col1:
        st.markdown("**Your Properties:**")
    with re_col2:
        # Toggle edit mode button
        edit_label = "🔒 Lock" if st.session_state['real_estate_edit_mode'] else "✏️ Edit"
        if st.button(edit_label, width='stretch', key="toggle_edit_btn"):
            st.session_state['real_estate_edit_mode'] = not st.session_state['real_estate_edit_mode']
            st.rerun()
    with re_col3:
        if st.button("➕ Add Property", width='stretch', key="add_property_btn",
                     disabled=not st.session_state['real_estate_edit_mode']):
            new_prop = pd.DataFrame({
                'property_name': ['New Property'],
                'address': [''],
                'purchase_price': [0.0]
            })
            re_df = pd.concat([re_df, new_prop], ignore_index=True)
            st.session_state['real_estate_list'] = re_df.to_dict('records')
            st.rerun()
    with re_col4:
        if st.button("💾 Save Properties", width='stretch', key="save_properties_btn",
                     disabled=not st.session_state['real_estate_edit_mode']):
            # Sync latest edits from editor into session state before validating
            _current_re = st.session_state.get('real_estate_list', [])
            _validation_errors = []
            for _i, _prop in enumerate(_current_re):
                _row_num = _i + 1
                _name = str(_prop.get('property_name', '') or '').strip()
                _addr = str(_prop.get('address', '') or '').strip()
                _price = _prop.get('purchase_price', None)
                if not _name:
                    _validation_errors.append(f"Row {_row_num}: Property Name is required.")
                if not _addr:
                    _validation_errors.append(f"Row {_row_num}: Address is required.")
                if _price is None or str(_price).strip() == '' or float(_price) <= 0:
                    _validation_errors.append(f"Row {_row_num}: Purchase Price must be greater than $0.")
            if _validation_errors:
                st.error("❌ Please fix the following before saving:")
                for _err in _validation_errors:
                    st.markdown(f"  - {_err}")
            else:
                config_mgr.update_section("real_estate", {
                    "properties": _current_re
                })
                if config_mgr.save_config():
                    st.success("✅ Properties saved!")
                else:
                    st.error("❌ Error saving properties")

    re_column_config = {
        'property_name': st.column_config.TextColumn(
            'Property Name', required=True,
            help="Descriptive name (e.g. Primary Residence, Vacation Home)"
        ),
        'address': st.column_config.TextColumn(
            'Address', required=True,
            help="Full street address of the property"
        ),
        'purchase_price': st.column_config.NumberColumn(
            'Purchase Price ($)', required=True, min_value=0,
            format="$%d",
            help="Original purchase price — used in net worth statement"
        ),
    }

    # Show data editor or static dataframe based on edit mode
    if st.session_state['real_estate_edit_mode']:
        edited_re_df = st.data_editor(
            re_df,
            column_config=re_column_config,
            num_rows="dynamic",
            width='stretch',
            hide_index=True,
            key="real_estate_editor"
        )
    else:
        # Display as read-only dataframe
        edited_re_df = re_df.copy()
        st.dataframe(
            re_df,
            column_config=re_column_config,
            width='stretch',
            hide_index=True,
            use_container_width=True
        )

    # Keep session state in sync with edits (supports row deletion via num_rows="dynamic")
    st.session_state['real_estate_list'] = edited_re_df.to_dict('records')

    # Per-row delete buttons (only show in edit mode)
    if not edited_re_df.empty and st.session_state['real_estate_edit_mode']:
        st.markdown("**Delete a property:**")
        _del_cols = st.columns(min(len(edited_re_df), 4))
        for _enum_idx, (_, _row) in enumerate(edited_re_df.iterrows()):
            _prop_label = str(_row.get('property_name', f'Row {_enum_idx + 1}')) or f'Row {_enum_idx + 1}'
            _col_idx = _enum_idx % 4
            with _del_cols[_col_idx]:
                if st.button(f"🗑️ {_prop_label}", key=f"del_re_{_enum_idx}", help=f"Delete '{_prop_label}'"):
                    _updated = [
                        r for i, r in enumerate(st.session_state['real_estate_list'])
                        if i != _enum_idx
                    ]
                    st.session_state['real_estate_list'] = _updated
                    st.rerun()

    # Summary metrics
    if not edited_re_df.empty and 'purchase_price' in edited_re_df.columns:
        _re_prices = pd.to_numeric(edited_re_df['purchase_price'], errors='coerce')
        _re_series: pd.Series = pd.Series(_re_prices)  # type: ignore[assignment]
        total_re_value = float(_re_series.fillna(0).sum())
        st.markdown("---")
        re_m1, re_m2 = st.columns(2)
        with re_m1:
            st.metric("Total Properties", len(edited_re_df))
        with re_m2:
            st.metric("Total Real Estate Value (Purchase Price)", f"${total_re_value:,.0f}")

    st.info("💡 **Note:** Real estate values appear in the Net Worth Statement on the Dashboard under the 'Real Estate' category.")


# Add helpful information at the bottom
st.markdown("---")
st.info("""
**💡 Tips:**
- Changes are not saved automatically. Click the "Save All Changes" button in the Advanced tab to persist your changes.
- Use the Export/Import feature to backup your configuration or share it across devices.
- The configuration file is stored as `retirement_config.json` in your application directory.
""")

# Made with Bob
