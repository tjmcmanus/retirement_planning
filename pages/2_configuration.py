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
    VALID_ACCOUNT_OWNERS,
    VALID_SECTORS,
)
from ssi_calculator import generate_ssi_schedule_from_config, export_ssi_schedule_to_csv
from ltc_hsa_export import (
    export_ltc_analysis_to_csv, export_ltc_analysis_to_json, export_ltc_analysis_to_markdown,
    export_hsa_analysis_to_csv, export_hsa_analysis_to_json, export_hsa_analysis_to_markdown
)

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "👤 Personal Info",
    "💰 Financial Assumptions",
    "🏥 Healthcare",
    "📊 Social Security",
    "📈 Tax Strategy",
    "📊 Portfolio Data",
    "🏠 Real Estate",
    "⚖️ Rebalancing",
    "🪣 Bucket Strategy",
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
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"{person1_name}'s Healthcare")
        
        st.markdown("**Pre-Retirement Healthcare (While Working)**")
        
        # Healthcare type selection for pre-retirement
        person1_preretirement_coverage_type = st.selectbox(
            "Pre-Retirement Coverage Type",
            options=["None", "Employer", "ACA Marketplace"],
            index=["None", "Employer", "ACA Marketplace"].index(
                config_mgr.get("healthcare", "person1_preretirement_coverage_type", "None")
            ),
            help=f"Select {person1_name}'s healthcare coverage type before retirement",
            key="person1_preretirement_coverage_type"
        )
        
        if person1_preretirement_coverage_type != "None":
            person1_preretirement_insurance_monthly = st.number_input(
                "Monthly Pre-Retirement Premium ($)",
                min_value=0,
                max_value=5000,
                value=config_mgr.get("healthcare", "person1_preretirement_insurance_monthly", 0),
                step=50,
                help=f"Monthly premium for {person1_name}'s {person1_preretirement_coverage_type.lower()} insurance before retirement",
                key="person1_preretirement_insurance_monthly"
            )
            
            if person1_preretirement_insurance_monthly > 0:
                annual_preretirement_cost_1 = person1_preretirement_insurance_monthly * 12
                st.metric("Annual Pre-Retirement Cost", f"${annual_preretirement_cost_1:,.0f}")
        else:
            person1_preretirement_insurance_monthly = 0
        
        st.markdown("---")
        
        st.markdown("**Retirement Healthcare (Pre-Medicare)**")
        
        # Retirement coverage type selection
        person1_retirement_coverage_type = st.selectbox(
            "Retirement Coverage Type (Post-Retirement, Pre-Medicare)",
            options=["None", "Employer Retiree", "ACA Marketplace"],
            index=["None", "Employer Retiree", "ACA Marketplace"].index(
                config_mgr.get("healthcare", "person1_retirement_coverage_type", "None")
            ),
            help=f"Select {person1_name}'s healthcare coverage type after retirement but before Medicare eligibility",
            key="person1_retirement_coverage_type"
        )
        
        if person1_retirement_coverage_type == "ACA Marketplace":
            st.info("💡 Withdrawal strategy will optimize income to maximize ACA subsidies (typically keeping MAGI below 400% FPL)")
        
        if person1_retirement_coverage_type != "None":
            person1_aca_insurance_monthly = st.number_input(
                f"Monthly {person1_retirement_coverage_type} Premium ($)",
                min_value=0,
                max_value=5000,
                value=config_mgr.get("healthcare", "person1_aca_insurance_monthly", 0),
                step=50,
                help=f"Monthly premium for {person1_name}'s {person1_retirement_coverage_type.lower()} insurance (before subsidies if ACA)",
                key="person1_aca_insurance_monthly"
            )
        else:
            person1_aca_insurance_monthly = 0
        
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
            
            st.metric("Annual Retirement Healthcare Cost", f"${annual_aca_cost_1:,.0f}")
            st.metric("Total Retirement Healthcare Cost", f"${total_aca_cost_1:,.0f}",
                     help=f"Total cost for {years_on_aca_1} years on ACA")
    
    with col2:
        st.subheader(f"{person2_name}'s Healthcare")
        
        st.markdown("**Pre-Retirement Healthcare (While Working)**")
        
        # Healthcare type selection for pre-retirement
        person2_preretirement_coverage_type = st.selectbox(
            "Pre-Retirement Coverage Type",
            options=["None", "Employer", "ACA Marketplace"],
            index=["None", "Employer", "ACA Marketplace"].index(
                config_mgr.get("healthcare", "person2_preretirement_coverage_type", "None")
            ),
            help=f"Select {person2_name}'s healthcare coverage type before retirement",
            key="person2_preretirement_coverage_type"
        )
        
        if person2_preretirement_coverage_type != "None":
            person2_preretirement_insurance_monthly = st.number_input(
                "Monthly Pre-Retirement Premium ($)",
                min_value=0,
                max_value=5000,
                value=config_mgr.get("healthcare", "person2_preretirement_insurance_monthly", 0),
                step=50,
                help=f"Monthly premium for {person2_name}'s {person2_preretirement_coverage_type.lower()} insurance before retirement",
                key="person2_preretirement_insurance_monthly"
            )
            
            if person2_preretirement_insurance_monthly > 0:
                annual_preretirement_cost_2 = person2_preretirement_insurance_monthly * 12
                st.metric("Annual Pre-Retirement Cost", f"${annual_preretirement_cost_2:,.0f}")
        else:
            person2_preretirement_insurance_monthly = 0
        
        st.markdown("---")
        st.markdown("**Retirement Healthcare (Pre-Medicare)**")
        
        # Retirement coverage type selection
        person2_retirement_coverage_type = st.selectbox(
            "Retirement Coverage Type (Post-Retirement, Pre-Medicare)",
            options=["None", "Employer Retiree", "ACA Marketplace"],
            index=["None", "Employer Retiree", "ACA Marketplace"].index(
                config_mgr.get("healthcare", "person2_retirement_coverage_type", "None")
            ),
            help=f"Select {person2_name}'s healthcare coverage type after retirement but before Medicare eligibility",
            key="person2_retirement_coverage_type"
        )
        
        if person2_retirement_coverage_type == "ACA Marketplace":
            st.info("💡 Withdrawal strategy will optimize income to maximize ACA subsidies (typically keeping MAGI below 400% FPL)")
        
        if person2_retirement_coverage_type != "None":
            person2_aca_insurance_monthly = st.number_input(
                f"Monthly {person2_retirement_coverage_type} Premium ($)",
                min_value=0,
                max_value=5000,
                value=config_mgr.get("healthcare", "person2_aca_insurance_monthly", 0),
                step=50,
                help=f"Monthly premium for {person2_name}'s {person2_retirement_coverage_type.lower()} insurance (before subsidies if ACA)",
                key="person2_aca_insurance_monthly"
            )
        else:
            person2_aca_insurance_monthly = 0
        
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
            
            st.metric("Annual Retirement Healthcare Cost", f"${annual_aca_cost_2:,.0f}")
            st.metric("Total Retirement Healthcare Cost", f"${total_aca_cost_2:,.0f}",
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
    
    # Long-Term Care Planning Section
    st.markdown("---")
    st.header("🏥 Long-Term Care (LTC) Planning")
    st.markdown("Plan for potential long-term care needs and evaluate insurance options.")
    
    with st.expander("📊 LTC Cost Projections & Analysis", expanded=False):
        from ltc_planning import (
            project_ltc_costs, analyze_medicaid_spend_down,
            analyze_ltc_insurance_vs_self_insurance, calculate_ltc_probability,
            generate_ltc_cost_comparison, STATE_NURSING_HOME_COSTS
        )
        
        st.subheader("LTC Planning Parameters")
        
        ltc_col1, ltc_col2, ltc_col3 = st.columns(3)
        
        with ltc_col1:
            ltc_state = st.selectbox(
                "State for Cost Projections",
                options=['National'] + sorted(STATE_NURSING_HOME_COSTS.keys()),
                index=0,
                help="Select your state for accurate LTC cost projections",
                key="ltc_state"
            )
            
            ltc_years_until_need = st.number_input(
                "Years Until LTC Needed",
                min_value=0,
                max_value=40,
                value=config_mgr.get("ltc_planning", "years_until_need", 15),
                help="Estimated years until long-term care is needed",
                key="ltc_years_until_need"
            )
        
        with ltc_col2:
            ltc_expected_duration = st.number_input(
                "Expected Years of Care",
                min_value=1,
                max_value=10,
                value=config_mgr.get("ltc_planning", "expected_duration", 3),
                help="Expected duration of long-term care (average is 3 years)",
                key="ltc_expected_duration"
            )
            
            ltc_current_assets = st.number_input(
                "Current Countable Assets ($)",
                min_value=0,
                max_value=10000000,
                value=config_mgr.get("ltc_planning", "current_assets", 500000),
                step=10000,
                help="Assets that count toward Medicaid eligibility (excludes primary home)",
                key="ltc_current_assets"
            )
        
        with ltc_col3:
            ltc_is_married = st.checkbox(
                "Married/Partnered",
                value=config_mgr.get("ltc_planning", "is_married", True),
                help="Affects Medicaid asset limits and spend-down strategies",
                key="ltc_is_married"
            )
            
            if ltc_is_married:
                ltc_spouse_assets = st.number_input(
                    "Spouse's Assets ($)",
                    min_value=0,
                    max_value=10000000,
                    value=config_mgr.get("ltc_planning", "spouse_assets", 250000),
                    step=10000,
                    help="Assets in spouse's name",
                    key="ltc_spouse_assets"
                )
            else:
                ltc_spouse_assets = 0
        
        # Run LTC Analysis
        if st.button("🔍 Run LTC Analysis", key="run_ltc_analysis"):
            st.markdown("---")
            st.subheader("LTC Analysis Results")
            
            # Cost Comparison Table
            st.markdown("#### Cost Comparison by Care Type")
            cost_comparison = generate_ltc_cost_comparison(ltc_state, ltc_years_until_need)
            st.dataframe(
                cost_comparison.style.format({
                    'Current Annual Cost': '${:,.0f}',
                    'Projected Annual Cost': '${:,.0f}',
                    'Monthly Cost': '${:,.0f}',
                    '3-Year Total Cost': '${:,.0f}'
                }),
                use_container_width=True
            )
            
            # Medicaid Spend-Down Analysis
            st.markdown("#### Medicaid Eligibility Analysis")
            medicaid_analysis = analyze_medicaid_spend_down(
                ltc_current_assets,
                ltc_is_married,
                ltc_spouse_assets,
                ltc_state if ltc_state != 'National' else 'default'
            )
            
            med_col1, med_col2, med_col3 = st.columns(3)
            with med_col1:
                st.metric("Current Assets", f"${medicaid_analysis.current_assets:,.0f}")
            with med_col2:
                st.metric("Asset Limit", f"${medicaid_analysis.asset_limit:,.0f}")
            with med_col3:
                if medicaid_analysis.excess_assets > 0:
                    st.metric("Excess Assets", f"${medicaid_analysis.excess_assets:,.0f}", 
                             delta=f"{medicaid_analysis.months_to_qualify} months to qualify")
                else:
                    st.success("✅ Currently Medicaid Eligible")
            
            st.markdown("**Spend-Down Strategies:**")
            for strategy in medicaid_analysis.spend_down_strategies:
                st.write(f"• {strategy}")
            
            if ltc_is_married:
                st.info(f"💡 **Protected Spouse Assets:** ${medicaid_analysis.protected_spouse_assets:,.0f} can be retained by community spouse")
            
            st.markdown("**Lookback Period Concerns:**")
            for concern in medicaid_analysis.lookback_concerns:
                if "No concerning" in concern:
                    st.success(f"✅ {concern}")
                else:
                    st.warning(f"⚠️ {concern}")
            
            # LTC Probability
            st.markdown("#### Probability of Needing LTC")
            person1_age = config_mgr.calculate_age(config_mgr.get("personal_info", "person1_birth_date", "1965-01-01"))
            person1_gender = config_mgr.get("personal_info", "person1_gender", "M")
            
            ltc_prob = calculate_ltc_probability(person1_age, person1_gender)
            
            prob_col1, prob_col2, prob_col3 = st.columns(3)
            with prob_col1:
                st.metric("Probability of Any LTC", f"{ltc_prob['any_ltc']*100:.0f}%")
            with prob_col2:
                st.metric("Expected Duration", f"{ltc_prob['expected_duration_years']:.1f} years")
            with prob_col3:
                st.metric("Expected Cost", f"${ltc_prob.get('expected_cost', 0):,.0f}")
            
            # Export LTC Analysis
            st.markdown("---")
            st.markdown("#### 📥 Export LTC Analysis")
            
            export_col1, export_col2, export_col3 = st.columns(3)
            
            with export_col1:
                # CSV Export
                csv_data = export_ltc_analysis_to_csv(
                    cost_comparison,
                    medicaid_analysis,
                    ltc_probability=ltc_prob
                )
                st.download_button(
                    label="📄 Download CSV",
                    data=csv_data,
                    file_name=f"ltc_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="download_ltc_csv"
                )
            
            with export_col2:
                # JSON Export
                json_data = export_ltc_analysis_to_json(
                    cost_comparison,
                    medicaid_analysis,
                    ltc_probability=ltc_prob
                )
                st.download_button(
                    label="📋 Download JSON",
                    data=json_data,
                    file_name=f"ltc_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key="download_ltc_json"
                )
            
            with export_col3:
                # Markdown Export
                md_data = export_ltc_analysis_to_markdown(
                    cost_comparison,
                    medicaid_analysis,
                    ltc_probability=ltc_prob
                )
                st.download_button(
                    label="📝 Download Markdown",
                    data=md_data,
                    file_name=f"ltc_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    key="download_ltc_md"
                )
                st.metric("Probability >5 Years", f"{ltc_prob['more_than_5_years']*100:.0f}%")
    
    # LTC Insurance Analysis
    with st.expander("💰 LTC Insurance vs Self-Insurance Analysis", expanded=False):
        st.markdown("Compare purchasing LTC insurance versus self-insuring (paying out of pocket).")
        
        ins_col1, ins_col2, ins_col3 = st.columns(3)
        
        with ins_col1:
            ltc_ins_annual_premium = st.number_input(
                "Annual LTC Insurance Premium ($)",
                min_value=0,
                max_value=20000,
                value=config_mgr.get("ltc_planning", "insurance_annual_premium", 3000),
                step=100,
                help="Annual premium for LTC insurance policy",
                key="ltc_ins_annual_premium"
            )
            
            ltc_ins_daily_benefit = st.number_input(
                "Daily Benefit Amount ($)",
                min_value=0,
                max_value=500,
                value=config_mgr.get("ltc_planning", "insurance_daily_benefit", 200),
                step=10,
                help="Daily benefit amount from insurance policy",
                key="ltc_ins_daily_benefit"
            )
        
        with ins_col2:
            ltc_ins_benefit_period = st.selectbox(
                "Benefit Period (Years)",
                options=[2, 3, 4, 5, 'lifetime'],
                index=2,
                help="How many years the policy will pay benefits",
                key="ltc_ins_benefit_period"
            )
            
            ltc_ins_waiting_period = st.selectbox(
                "Waiting Period (Days)",
                options=[0, 30, 60, 90, 180],
                index=3,
                help="Days before benefits begin (elimination period)",
                key="ltc_ins_waiting_period"
            )
        
        with ins_col3:
            ltc_ins_inflation_protection = st.checkbox(
                "Inflation Protection (3% compound)",
                value=config_mgr.get("ltc_planning", "insurance_inflation_protection", True),
                help="Policy includes 3% compound inflation protection",
                key="ltc_ins_inflation_protection"
            )
        
        if st.button("📊 Compare Insurance vs Self-Insurance", key="compare_ltc_insurance"):
            person1_age = config_mgr.calculate_age(config_mgr.get("personal_info", "person1_birth_date", "1965-01-01"))
            
            insurance_analysis = analyze_ltc_insurance_vs_self_insurance(
                person1_age,
                ltc_ins_annual_premium,
                ltc_ins_daily_benefit,
                ltc_ins_benefit_period if isinstance(ltc_ins_benefit_period, int) else 99,
                ltc_ins_waiting_period,
                ltc_years_until_need,
                ltc_expected_duration,
                ltc_state,
                ltc_ins_inflation_protection
            )
            
            st.markdown("---")
            st.subheader("Insurance Analysis Results")
            
            # Key Metrics
            ins_metric_col1, ins_metric_col2, ins_metric_col3, ins_metric_col4 = st.columns(4)
            
            with ins_metric_col1:
                st.metric("Total Premiums Paid", f"${insurance_analysis.total_premiums_paid:,.0f}")
            with ins_metric_col2:
                st.metric("Insurance Benefit", f"${insurance_analysis.total_insurance_benefit:,.0f}")
            with ins_metric_col3:
                st.metric("Self-Insurance Cost", f"${insurance_analysis.self_insurance_cost:,.0f}")
            with ins_metric_col4:
                if insurance_analysis.break_even_year < 99:
                    st.metric("Break-Even Year", f"{insurance_analysis.break_even_year}")
                else:
                    st.metric("Break-Even", "Never")
            
            # Recommendation
            if "Recommended" in insurance_analysis.recommendation:
                st.success(f"✅ **{insurance_analysis.recommendation}**")
            elif "Marginally" in insurance_analysis.recommendation:
                st.info(f"ℹ️ **{insurance_analysis.recommendation}**")
            else:
                st.warning(f"⚠️ **{insurance_analysis.recommendation}**")
            
            # Detailed Notes
            st.markdown("**Analysis Details:**")
            for note in insurance_analysis.notes:
                st.markdown(f"- {note}")
            
            # Export LTC Insurance Analysis
            st.markdown("---")
            st.markdown("#### 📥 Export Insurance Analysis")
            
            ins_export_col1, ins_export_col2, ins_export_col3 = st.columns(3)
            
            # Need to get cost comparison for complete export
            cost_comparison_ins = generate_ltc_cost_comparison(ltc_state, ltc_years_until_need)
            medicaid_analysis_ins = analyze_medicaid_spend_down(
                ltc_current_assets,
                ltc_is_married,
                ltc_spouse_assets,
                ltc_state if ltc_state != 'National' else 'default'
            )
            
            with ins_export_col1:
                # CSV Export
                csv_data = export_ltc_analysis_to_csv(
                    cost_comparison_ins,
                    medicaid_analysis_ins,
                    insurance_analysis=insurance_analysis
                )
                st.download_button(
                    label="📄 Download CSV",
                    data=csv_data,
                    file_name=f"ltc_insurance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="download_ltc_ins_csv"
                )
            
            with ins_export_col2:
                # JSON Export
                json_data = export_ltc_analysis_to_json(
                    cost_comparison_ins,
                    medicaid_analysis_ins,
                    insurance_analysis=insurance_analysis
                )
                st.download_button(
                    label="📋 Download JSON",
                    data=json_data,
                    file_name=f"ltc_insurance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key="download_ltc_ins_json"
                )
            
            with ins_export_col3:
                # Markdown Export
                md_data = export_ltc_analysis_to_markdown(
                    cost_comparison_ins,
                    medicaid_analysis_ins,
                    insurance_analysis=insurance_analysis
                )
                st.download_button(
                    label="📝 Download Markdown",
                    data=md_data,
                    file_name=f"ltc_insurance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    key="download_ltc_ins_md"
                )
                st.write(f"• {note}")
    
    # HSA Integration Section
    st.markdown("---")
    st.header("💳 Health Savings Account (HSA) Planning")
    st.markdown("Maximize your HSA's triple tax advantage for retirement healthcare costs.")
    
    with st.expander("📈 HSA Contribution Planning & Projections", expanded=False):
        from hsa_integration import (
            get_hsa_contribution_limit, project_hsa_growth,
            optimize_hsa_contribution_strategy, estimate_retirement_healthcare_costs
        )
        
        st.subheader("HSA Account Information")
        
        hsa_col1, hsa_col2, hsa_col3 = st.columns(3)
        
        with hsa_col1:
            hsa_current_balance = st.number_input(
                "Current HSA Balance ($)",
                min_value=0,
                max_value=1000000,
                value=config_mgr.get("hsa", "current_balance", 0),
                step=1000,
                help="Your current HSA account balance",
                key="hsa_current_balance"
            )
            
            hsa_coverage_type = st.selectbox(
                "Coverage Type",
                options=['individual', 'family'],
                index=1 if config_mgr.get("hsa", "coverage_type", "family") == "family" else 0,
                help="Individual or family HDHP coverage",
                key="hsa_coverage_type"
            )
        
        with hsa_col2:
            hsa_employer_contribution = st.number_input(
                "Annual Employer Contribution ($)",
                min_value=0,
                max_value=10000,
                value=config_mgr.get("hsa", "employer_contribution", 1000),
                step=100,
                help="Annual employer HSA contribution",
                key="hsa_employer_contribution"
            )
            
            hsa_employee_contribution = st.number_input(
                "Annual Employee Contribution ($)",
                min_value=0,
                max_value=10000,
                value=config_mgr.get("hsa", "employee_contribution", 3000),
                step=100,
                help="Your annual HSA contribution",
                key="hsa_employee_contribution"
            )
        
        with hsa_col3:
            hsa_investment_return = st.slider(
                "Expected Investment Return (%)",
                min_value=0.0,
                max_value=12.0,
                value=config_mgr.get("hsa", "investment_return", 6.0),
                step=0.5,
                help="Expected annual return on HSA investments",
                key="hsa_investment_return"
            ) / 100
            
            hsa_annual_medical_expenses = st.number_input(
                "Annual Medical Expenses from HSA ($)",
                min_value=0,
                max_value=50000,
                value=config_mgr.get("hsa", "annual_medical_expenses", 0),
                step=500,
                help="Annual medical expenses paid from HSA (reduces balance)",
                key="hsa_annual_medical_expenses"
            )
        
        # Show current year contribution limit
        person1_age = config_mgr.calculate_age(config_mgr.get("personal_info", "person1_birth_date", "1965-01-01"))
        current_limit = get_hsa_contribution_limit(2024, hsa_coverage_type, person1_age)
        
        st.info(f"💡 **2024 HSA Contribution Limit:** ${current_limit:,.0f} ({hsa_coverage_type} coverage" + 
                (f", includes $1,000 catch-up for age 55+" if person1_age >= 55 else "") + ")")
        
        # Check if maxing out
        total_contribution = hsa_employer_contribution + hsa_employee_contribution
        if total_contribution < current_limit:
            shortfall = current_limit - total_contribution
            st.warning(f"⚠️ You're contributing ${total_contribution:,.0f}, which is ${shortfall:,.0f} below the maximum. Consider increasing contributions to maximize tax benefits!")
        elif total_contribution == current_limit:
            st.success(f"✅ You're maxing out your HSA contributions!")
        
        if st.button("📊 Run HSA Analysis", key="run_hsa_analysis"):
            st.markdown("---")
            st.subheader("HSA Growth Projection")
            
            # Project HSA growth
            projection = project_hsa_growth(
                hsa_current_balance,
                person1_age,
                hsa_coverage_type,
                hsa_employer_contribution,
                hsa_employee_contribution,
                hsa_investment_return,
                hsa_annual_medical_expenses
            )
            
            # Display key metrics
            hsa_metric_col1, hsa_metric_col2, hsa_metric_col3, hsa_metric_col4 = st.columns(4)
            
            with hsa_metric_col1:
                st.metric("Current Balance", f"${projection.current_balance:,.0f}")
            with hsa_metric_col2:
                st.metric("Years to Medicare", projection.years_to_medicare)
            with hsa_metric_col3:
                st.metric("Total Contributions", f"${projection.total_contributions:,.0f}")
            with hsa_metric_col4:
                st.metric("Balance at Age 65", f"${projection.final_balance:,.0f}")
            
            # Show year-by-year projection
            if projection.annual_projections:
                st.markdown("#### Year-by-Year Projection")
                proj_df = pd.DataFrame(projection.annual_projections)
                proj_df_display = proj_df[['year', 'age', 'contributions', 'medical_expenses', 'investment_growth', 'ending_balance']].copy()
                proj_df_display.columns = ['Year', 'Age', 'Contributions', 'Medical Expenses', 'Investment Growth', 'Ending Balance']
                
                st.dataframe(
                    proj_df_display.style.format({
                        'Contributions': '${:,.0f}',
                        'Medical Expenses': '${:,.0f}',
                        'Investment Growth': '${:,.0f}',
                        'Ending Balance': '${:,.0f}'
                    }),
                    use_container_width=True,
                    height=300
                )
            
            # Estimate retirement healthcare costs
            person1_retirement_age = config_mgr.get("personal_info", "person1_retirement_age", 65)
            person1_life_expectancy = config_mgr.get("personal_info", "person1_life_expectancy", 85)
            
            healthcare_costs = estimate_retirement_healthcare_costs(
                person1_retirement_age,
                person1_life_expectancy,
                include_ltc=False
            )
            
            st.markdown("---")
            st.subheader("Retirement Healthcare Cost Estimates")
            
            cost_col1, cost_col2, cost_col3 = st.columns(3)
            
            with cost_col1:
                st.metric("Total Healthcare Costs", f"${healthcare_costs['total_healthcare_costs']:,.0f}",
                         help="Estimated total healthcare costs in retirement (excluding LTC)")
            with cost_col2:
                st.metric("Annual Average", f"${healthcare_costs['annual_average']:,.0f}",
                         help="Average annual healthcare cost")
            with cost_col3:
                coverage_pct = (projection.final_balance / healthcare_costs['total_healthcare_costs']) * 100
                st.metric("HSA Coverage", f"{coverage_pct:.0f}%",
                         help="Percentage of healthcare costs covered by projected HSA balance")
            
            # Coverage assessment
            if coverage_pct >= 100:
                st.success("✅ **Excellent!** Your projected HSA balance will cover all estimated healthcare costs in retirement.")
            elif coverage_pct >= 75:
                st.info("ℹ️ **Good!** Your HSA will cover most healthcare costs. Consider increasing contributions if possible.")
            elif coverage_pct >= 50:
                st.warning("⚠️ **Fair.** Your HSA will cover about half of healthcare costs. Strongly consider maxing out contributions.")
            else:
                st.error("❌ **Insufficient!** Your HSA will cover less than half of healthcare costs. Maximize contributions immediately.")
            
            # Export HSA Analysis
            st.markdown("---")
            st.markdown("#### 📥 Export HSA Analysis")
            
            hsa_export_col1, hsa_export_col2, hsa_export_col3 = st.columns(3)
            
            with hsa_export_col1:
                # CSV Export
                csv_data = export_hsa_analysis_to_csv(
                    projection,
                    healthcare_costs=healthcare_costs
                )
                st.download_button(
                    label="📄 Download CSV",
                    data=csv_data,
                    file_name=f"hsa_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="download_hsa_csv"
                )
            
            with hsa_export_col2:
                # JSON Export
                json_data = export_hsa_analysis_to_json(
                    projection,
                    healthcare_costs=healthcare_costs
                )
                st.download_button(
                    label="📋 Download JSON",
                    data=json_data,
                    file_name=f"hsa_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key="download_hsa_json"
                )
            
            with hsa_export_col3:
                # Markdown Export
                md_data = export_hsa_analysis_to_markdown(
                    projection,
                    healthcare_costs=healthcare_costs
                )
                st.download_button(
                    label="📝 Download Markdown",
                    data=md_data,
                    file_name=f"hsa_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    key="download_hsa_md"
                )
                st.error("❌ **Low Coverage.** Your HSA will cover less than half of healthcare costs. Maximize contributions to take advantage of tax benefits!")
    
    # HSA Withdrawal Strategies
    with st.expander("💰 HSA Withdrawal Strategies in Retirement", expanded=False):
        from hsa_integration import analyze_hsa_withdrawal_strategies, calculate_hsa_triple_tax_advantage
        
        st.markdown("Compare different strategies for using your HSA in retirement.")
        
        # Get retirement parameters
        person1_retirement_age = config_mgr.get("personal_info", "person1_retirement_age", 65)
        person1_life_expectancy = config_mgr.get("personal_info", "person1_life_expectancy", 85)
        marginal_tax_rate = config_mgr.get("tax_strategy", "max_roth_conversion_tax_rate", 22) / 100
        
        hsa_ret_col1, hsa_ret_col2 = st.columns(2)
        
        with hsa_ret_col1:
            hsa_balance_at_retirement = st.number_input(
                "Projected HSA Balance at Retirement ($)",
                min_value=0,
                max_value=1000000,
                value=int(hsa_current_balance * 1.5) if hsa_current_balance > 0 else 50000,
                step=5000,
                help="Your estimated HSA balance when you retire",
                key="hsa_balance_at_retirement"
            )
        
        with hsa_ret_col2:
            hsa_annual_medical_ret = st.number_input(
                "Expected Annual Medical Expenses ($)",
                min_value=0,
                max_value=50000,
                value=8000,
                step=500,
                help="Expected annual medical expenses in retirement",
                key="hsa_annual_medical_ret"
            )
        
        if st.button("📊 Analyze Withdrawal Strategies", key="analyze_hsa_withdrawal"):
            strategies = analyze_hsa_withdrawal_strategies(
                hsa_balance_at_retirement,
                hsa_annual_medical_ret,
                person1_retirement_age,
                person1_life_expectancy,
                marginal_tax_rate
            )
            
            st.markdown("---")
            st.subheader("Withdrawal Strategy Comparison")
            
            for i, strategy in enumerate(strategies, 1):
                with st.container():
                    st.markdown(f"### Strategy {i}: {strategy.strategy_name}")
                    
                    strat_col1, strat_col2, strat_col3, strat_col4 = st.columns(4)
                    
                    with strat_col1:
                        st.metric("HSA Withdrawals", f"${strategy.hsa_withdrawals:,.0f}")
                    with strat_col2:
                        st.metric("Taxable Withdrawals", f"${strategy.taxable_withdrawals:,.0f}")
                    with strat_col3:
                        st.metric("Years HSA Lasts", strategy.years_hsa_lasts)
                    with strat_col4:
                        st.metric("Total Tax Savings", f"${strategy.total_tax_savings:,.0f}")
                    
                    st.markdown("**Strategy Notes:**")
                    for note in strategy.notes:
                        st.write(f"• {note}")
                    
                    st.markdown("---")
            
            # Calculate triple tax advantage
            st.subheader("HSA Triple Tax Advantage")
            st.markdown("HSAs offer three unique tax benefits:")
            
            # Estimate total contributions and growth
            years_contributing = max(1, 65 - person1_age)
            total_contributions = (hsa_employer_contribution + hsa_employee_contribution) * years_contributing
            investment_growth = hsa_balance_at_retirement - hsa_current_balance - total_contributions
            
            tax_advantage = calculate_hsa_triple_tax_advantage(
                total_contributions,
                investment_growth,
                marginal_tax_rate,
                0.15,  # Long-term capital gains rate
                years_contributing
            )
            
            tax_col1, tax_col2, tax_col3 = st.columns(3)
            
            with tax_col1:
                st.metric("Tax Savings on Contributions", f"${tax_advantage.tax_savings_contributions:,.0f}",
                         help="Contributions are tax-deductible")
            with tax_col2:
                st.metric("Tax Savings on Growth", f"${tax_advantage.tax_savings_growth:,.0f}",
                         help="Investment growth is tax-free")
            with tax_col3:
                st.metric("Tax Savings on Withdrawals", f"${tax_advantage.tax_savings_withdrawals:,.0f}",
                         help="Qualified medical withdrawals are tax-free")
            
            st.success(f"💰 **Total Tax Advantage: ${tax_advantage.total_tax_advantage:,.0f}**")
            
            
            # Export HSA Withdrawal Strategies
            st.markdown("---")
            st.markdown("#### 📥 Export Withdrawal Strategy Analysis")
            
            strat_export_col1, strat_export_col2, strat_export_col3 = st.columns(3)
            
            with strat_export_col1:
                # CSV Export
                csv_data = export_hsa_analysis_to_csv(
                    projection=None,  # Not available in this context
                    strategies=strategies,
                    tax_advantage=tax_advantage
                )
                st.download_button(
                    label="📄 Download CSV",
                    data=csv_data,
                    file_name=f"hsa_withdrawal_strategies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="download_hsa_strat_csv"
                )
            
            with strat_export_col2:
                # JSON Export
                json_data = export_hsa_analysis_to_json(
                    projection=None,  # Not available in this context
                    strategies=strategies,
                    tax_advantage=tax_advantage
                )
                st.download_button(
                    label="📋 Download JSON",
                    data=json_data,
                    file_name=f"hsa_withdrawal_strategies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key="download_hsa_strat_json"
                )
            
            with strat_export_col3:
                # Markdown Export
                md_data = export_hsa_analysis_to_markdown(
                    projection=None,  # Not available in this context
                    strategies=strategies,
                    tax_advantage=tax_advantage
                )
                st.download_button(
                    label="📝 Download Markdown",
                    data=md_data,
                    file_name=f"hsa_withdrawal_strategies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    key="download_hsa_strat_md"
                )
            st.info(f"💡 To achieve the same after-tax value in a taxable account, you would need ${tax_advantage.equivalent_taxable_account:,.0f}")

            st.metric("Total Annual Retirement Healthcare Cost", f"${total_annual_aca:,.0f}")

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
    
    # Social Security Optimization Section
    st.markdown("---")
    st.header("🎯 Social Security Optimization")
    st.markdown("Analyze optimal claiming strategies to maximize lifetime benefits.")
    
    with st.expander("📊 **Run Optimization Analysis**", expanded=False):
        st.markdown("""
        This tool analyzes different claiming age combinations to help you make informed decisions about when to claim Social Security.
        
        **What it considers:**
        - Individual and spousal benefits
        - Break-even analysis
        - Net present value (NPV)
        - Life expectancy assumptions
        - Survivor benefits
        """)
        
        # Optimization inputs
        opt_col1, opt_col2 = st.columns(2)
        
        with opt_col1:
            st.subheader(f"{person1_name}'s Profile")
            person1_birth_year = st.number_input(
                "Birth Year",
                min_value=1940,
                max_value=2010,
                value=config_mgr.get("social_security", "person1_birth_year", 1960),
                key="person1_birth_year_opt"
            )
            person1_gender = st.selectbox(
                "Gender",
                options=['M', 'F'],
                index=0 if config_mgr.get("social_security", "person1_gender", 'M') == 'M' else 1,
                help="Used for default life expectancy (M=84, F=87)",
                key="person1_gender_opt"
            )
            person1_life_exp = st.number_input(
                "Life Expectancy",
                min_value=65,
                max_value=110,
                value=config_mgr.get("social_security", "person1_life_expectancy", 84 if person1_gender == 'M' else 87),
                help="Expected age at death (affects lifetime benefit calculations)",
                key="person1_life_exp_opt"
            )
            person1_earnings = st.number_input(
                "Current Annual Earnings ($)",
                min_value=0,
                max_value=500000,
                value=config_mgr.get("social_security", "person1_current_earnings", 0),
                step=5000,
                help="If still working, used for earnings test analysis",
                key="person1_earnings_opt"
            )
        
        with opt_col2:
            st.subheader(f"{person2_name}'s Profile")
            person2_birth_year = st.number_input(
                "Birth Year",
                min_value=1940,
                max_value=2010,
                value=config_mgr.get("social_security", "person2_birth_year", 1962),
                key="person2_birth_year_opt"
            )
            person2_gender = st.selectbox(
                "Gender",
                options=['M', 'F'],
                index=0 if config_mgr.get("social_security", "person2_gender", 'F') == 'M' else 1,
                help="Used for default life expectancy (M=84, F=87)",
                key="person2_gender_opt"
            )
            person2_life_exp = st.number_input(
                "Life Expectancy",
                min_value=65,
                max_value=110,
                value=config_mgr.get("social_security", "person2_life_expectancy", 84 if person2_gender == 'M' else 87),
                help="Expected age at death (affects lifetime benefit calculations)",
                key="person2_life_exp_opt"
            )
            person2_earnings = st.number_input(
                "Current Annual Earnings ($)",
                min_value=0,
                max_value=500000,
                value=config_mgr.get("social_security", "person2_current_earnings", 0),
                step=5000,
                help="If still working, used for earnings test analysis",
                key="person2_earnings_opt"
            )
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            cola_rate = st.slider(
                "Annual COLA Rate (%)",
                min_value=0.0,
                max_value=5.0,
                value=2.0,
                step=0.1,
                help="Expected annual cost-of-living adjustment"
            ) / 100
            
            discount_rate = st.slider(
                "Discount Rate for NPV (%)",
                min_value=0.0,
                max_value=10.0,
                value=3.0,
                step=0.5,
                help="Real discount rate for net present value calculations"
            ) / 100
            
            portfolio_return = st.slider(
                "Expected Portfolio Return (%)",
                min_value=0.0,
                max_value=15.0,
                value=7.0,
                step=0.5,
                help="Expected annual portfolio return rate (used for opportunity cost analysis)"
            ) / 100
        
        # Run optimization button
        if st.button("🚀 Run Optimization Analysis", type="primary", use_container_width=True):
            if person1_ssi_amount == 0 and person2_ssi_amount == 0:
                st.error("❌ Please enter Social Security benefit amounts above before running optimization.")
            else:
                with st.spinner("Analyzing claiming strategies..."):
                    try:
                        from ss_optimization import (
                            PersonProfile,
                            optimize_couple_claiming_strategy,
                            calculate_break_even_age,
                            calculate_break_even_with_portfolio_impact,
                            generate_claiming_age_comparison,
                            calculate_earnings_test_impact
                        )
                        
                        # Create person profiles
                        person1_profile = PersonProfile(
                            name=person1_name,
                            birth_year=person1_birth_year,
                            fra_benefit=person1_ssi_amount,
                            gender=person1_gender,
                            life_expectancy=person1_life_exp,
                            current_earnings=person1_earnings
                        )
                        
                        person2_profile = PersonProfile(
                            name=person2_name,
                            birth_year=person2_birth_year,
                            fra_benefit=person2_ssi_amount,
                            gender=person2_gender,
                            life_expectancy=person2_life_exp,
                            current_earnings=person2_earnings
                        )
                        
                        # Run couple optimization
                        strategies = optimize_couple_claiming_strategy(
                            person1_profile,
                            person2_profile,
                            cola_rate=cola_rate,
                            discount_rate=discount_rate
                        )
                        
                        # Display results
                        st.success("✅ Optimization Complete!")
                        
                        # Top 5 strategies
                        st.subheader("🏆 Top 5 Claiming Strategies")
                        st.markdown("Ranked by Net Present Value (NPV)")
                        
                        for i, strategy in enumerate(strategies[:5], 1):
                            with st.container():
                                rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                                
                                col_a, col_b, col_c = st.columns([2, 1, 1])
                                with col_a:
                                    st.markdown(f"**{rank_emoji} {strategy.strategy_name}**")
                                    for note in strategy.notes:
                                        st.caption(f"• {note}")
                                with col_b:
                                    st.metric("NPV", f"${strategy.net_present_value:,.0f}")
                                with col_c:
                                    st.metric("Lifetime Total", f"${strategy.total_lifetime_benefits:,.0f}")
                                
                                if i < 5:
                                    st.markdown("---")
                        
                        # Break-even analysis
                        st.markdown("---")
                        st.subheader("📈 Break-Even Analysis")
                        st.markdown("Comparing claiming at age 62 vs 70")
                        
                        # Explanation of opportunity cost
                        with st.expander("ℹ️ Understanding Portfolio Opportunity Cost"):
                            st.markdown("""
                            **Simple Break-Even**: Compares only Social Security benefits received.
                            
                            **Portfolio-Adjusted Break-Even**: Accounts for the opportunity cost of delaying SS.
                            
                            **Why it matters:**
                            - When you delay SS, you must withdraw from your portfolio to cover expenses
                            - Those withdrawals lose the opportunity to grow at your portfolio return rate
                            - This "opportunity cost" typically adds 2-4 years to the break-even age
                            - Higher portfolio returns = longer break-even age
                            
                            **Example:** If you withdraw $21,000/year from age 62-70 (8 years) and your portfolio
                            grows at 7%/year, you're giving up ~$280,000 in potential growth by age 80.
                            """)
                        
                        be_col1, be_col2 = st.columns(2)
                        
                        with be_col1:
                            if person1_ssi_amount > 0:
                                st.markdown(f"**{person1_name}**: Age 62 vs 70")
                                
                                # Calculate both simple and portfolio-adjusted
                                be_results_1 = calculate_break_even_with_portfolio_impact(
                                    person1_ssi_amount, 62, 70, cola_rate, portfolio_return
                                )
                                
                                # Display side-by-side comparison
                                metric_col1, metric_col2 = st.columns(2)
                                with metric_col1:
                                    st.metric(
                                        "Simple Break-Even",
                                        f"Age {be_results_1['simple'].break_even_age}",
                                        help="Comparing only SS benefits"
                                    )
                                with metric_col2:
                                    st.metric(
                                        "Portfolio-Adjusted",
                                        f"Age {be_results_1['portfolio_adjusted'].break_even_age}",
                                        delta=f"+{be_results_1['additional_years']} years",
                                        delta_color="off",
                                        help="Including portfolio opportunity cost"
                                    )
                                
                                st.caption(f"💰 Monthly difference: ${be_results_1['simple'].monthly_difference:,.0f}")
                                st.caption(f"📊 Portfolio return assumption: {portfolio_return*100:.1f}%")
                                
                                if be_results_1['additional_years'] > 0:
                                    st.warning(
                                        f"⚠️ Portfolio opportunity cost adds **{be_results_1['additional_years']} years** "
                                        f"to break-even age"
                                    )
                        
                        with be_col2:
                            if person2_ssi_amount > 0:
                                st.markdown(f"**{person2_name}**: Age 62 vs 70")
                                
                                # Calculate both simple and portfolio-adjusted
                                be_results_2 = calculate_break_even_with_portfolio_impact(
                                    person2_ssi_amount, 62, 70, cola_rate, portfolio_return
                                )
                                
                                # Display side-by-side comparison
                                metric_col1, metric_col2 = st.columns(2)
                                with metric_col1:
                                    st.metric(
                                        "Simple Break-Even",
                                        f"Age {be_results_2['simple'].break_even_age}",
                                        help="Comparing only SS benefits"
                                    )
                                with metric_col2:
                                    st.metric(
                                        "Portfolio-Adjusted",
                                        f"Age {be_results_2['portfolio_adjusted'].break_even_age}",
                                        delta=f"+{be_results_2['additional_years']} years",
                                        delta_color="off",
                                        help="Including portfolio opportunity cost"
                                    )
                                
                                st.caption(f"💰 Monthly difference: ${be_results_2['simple'].monthly_difference:,.0f}")
                                st.caption(f"📊 Portfolio return assumption: {portfolio_return*100:.1f}%")
                                
                                if be_results_2['additional_years'] > 0:
                                    st.warning(
                                        f"⚠️ Portfolio opportunity cost adds **{be_results_2['additional_years']} years** "
                                        f"to break-even age"
                                    )
                        
                        # Earnings test impact (if applicable)
                        if person1_earnings > 0 or person2_earnings > 0:
                            st.markdown("---")
                            st.subheader("💼 Earnings Test Impact")
                            st.markdown("Impact of working while collecting Social Security before Full Retirement Age")
                            
                            et_col1, et_col2 = st.columns(2)
                            
                            with et_col1:
                                if person1_earnings > 0 and person1_ssi_age < 67:
                                    st.markdown(f"**{person1_name}** (Age {person1_ssi_age})")
                                    from ssi_calculator import calculate_benefit_at_claiming_age
                                    person1_monthly = calculate_benefit_at_claiming_age(person1_ssi_amount, person1_ssi_age)
                                    et_impact_1 = calculate_earnings_test_impact(
                                        person1_earnings,
                                        person1_ssi_age,
                                        person1_monthly
                                    )
                                    
                                    if et_impact_1.annual_reduction > 0:
                                        st.warning(f"⚠️ Benefit reduced by ${et_impact_1.annual_reduction:,.0f}/year")
                                        st.caption(f"Before: ${et_impact_1.monthly_benefit_before:,.0f}/mo")
                                        st.caption(f"After: ${et_impact_1.monthly_benefit_after:,.0f}/mo")
                                        st.caption(f"Months withheld: {et_impact_1.months_withheld}")
                                    else:
                                        st.success("✅ No earnings test impact")
                            
                            with et_col2:
                                if person2_earnings > 0 and person2_ssi_age < 67:
                                    st.markdown(f"**{person2_name}** (Age {person2_ssi_age})")
                                    from ssi_calculator import calculate_benefit_at_claiming_age
                                    person2_monthly = calculate_benefit_at_claiming_age(person2_ssi_amount, person2_ssi_age)
                                    et_impact_2 = calculate_earnings_test_impact(
                                        person2_earnings,
                                        person2_ssi_age,
                                        person2_monthly
                                    )
                                    
                                    if et_impact_2.annual_reduction > 0:
                                        st.warning(f"⚠️ Benefit reduced by ${et_impact_2.annual_reduction:,.0f}/year")
                                        st.caption(f"Before: ${et_impact_2.monthly_benefit_before:,.0f}/mo")
                                        st.caption(f"After: ${et_impact_2.monthly_benefit_after:,.0f}/mo")
                                        st.caption(f"Months withheld: {et_impact_2.months_withheld}")
                                    else:
                                        st.success("✅ No earnings test impact")
                        
                        # Claiming age comparison table
                        st.markdown("---")
                        st.subheader("📊 Claiming Age Comparison")
                        
                        comp_tab1, comp_tab2 = st.tabs([f"{person1_name}", f"{person2_name}"])
                        
                        with comp_tab1:
                            if person1_ssi_amount > 0:
                                comparison_df_1 = generate_claiming_age_comparison(
                                    person1_ssi_amount,
                                    person1_life_exp,
                                    cola_rate,
                                    discount_rate
                                )
                                st.dataframe(
                                    comparison_df_1.style.format({
                                        'Monthly Benefit': '${:,.0f}',
                                        'Annual Benefit': '${:,.0f}',
                                        'Lifetime Total': '${:,.0f}',
                                        'Net Present Value': '${:,.0f}'
                                    }).background_gradient(subset=['Net Present Value'], cmap='RdYlGn'),
                                    use_container_width=True,
                                    height=400
                                )
                        
                        with comp_tab2:
                            if person2_ssi_amount > 0:
                                comparison_df_2 = generate_claiming_age_comparison(
                                    person2_ssi_amount,
                                    person2_life_exp,
                                    cola_rate,
                                    discount_rate
                                )
                                st.dataframe(
                                    comparison_df_2.style.format({
                                        'Monthly Benefit': '${:,.0f}',
                                        'Annual Benefit': '${:,.0f}',
                                        'Lifetime Total': '${:,.0f}',
                                        'Net Present Value': '${:,.0f}'
                                    }).background_gradient(subset=['Net Present Value'], cmap='RdYlGn'),
                                    use_container_width=True,
                                    height=400
                                )
                        
                        # Key insights
                        st.markdown("---")
                        st.info("""
                        **💡 Key Insights:**
                        - **NPV** accounts for time value of money (higher is better)
                        - **Break-even age** shows when delayed claiming pays off
                        - **Earnings test** only applies before Full Retirement Age (67)
                        - **Survivor benefits** favor higher earner delaying to age 70
                        - Consider health, longevity, and cash flow needs in your decision
                        """)
                        
                    except Exception as e:
                        st.error(f"❌ Error running optimization: {e}")
                        st.exception(e)

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
                    'month', 'year', 'account_name', 'account_type', 'owner', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
                ]))
        else:
            st.session_state['portfolio_df'] = pd.DataFrame(columns=pd.Index([
                'month', 'year', 'account_name', 'account_type', 'owner', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
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
                'owner': ['Joint'],
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
                'month', 'year', 'account_name', 'account_type', 'owner', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
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
        'owner': st.column_config.SelectboxColumn('Owner', options=VALID_ACCOUNT_OWNERS, required=True,
                                                   help="Joint (both spouses), Primary (person 1), or Spouse (person 2)"),
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
        - `owner`: Account owner (Joint, Primary, Spouse)
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
            'owner': ['Joint', 'Primary'],
            'symbol': ['AAPL', 'MF:CASH'],
            'name': ['Apple Inc.', 'Money Market'],
            'sector': ['Technology', 'MF:Cash'],
            'qty': [100.0, 50000.0],
            'purchase_price': [150.0, 1.0]
        })
        st.dataframe(sample_data, width='stretch')
# Rebalancing Preferences Tab
with tab8:
    st.header("⚖️ Portfolio Rebalancing Preferences")
    st.markdown("""
    Configure your preferred ETFs and mutual funds for portfolio rebalancing recommendations.
    These symbols will be suggested when the rebalancing algorithm identifies buy opportunities.
    """)
    
    st.subheader("💵 Cash")
    cash_symbol = st.text_input(
        "Cash Symbol",
        value=config_mgr.get("rebalancing_preferences", "cash_symbol", "MF:CASH"),
        help="Symbol for cash/money market positions",
        key="rebal_cash_symbol"
    )
    
    st.markdown("---")
    st.subheader("📊 Bonds")
    st.markdown("**Traditional IRA** (Tax-deferred bond income)")
    bonds_traditional = st.text_input(
        "Bonds - Traditional IRA",
        value=config_mgr.get("rebalancing_preferences", "bonds_traditional", "VBTLX (Vanguard Total Bond Market Admiral)"),
        help="Mutual fund recommended for bonds in Traditional IRA",
        key="rebal_bonds_trad"
    )
    
    st.markdown("**Roth IRA** (Tax-free growth)")
    bonds_roth = st.text_input(
        "Bonds - Roth IRA",
        value=config_mgr.get("rebalancing_preferences", "bonds_roth", "BND (Vanguard Total Bond Market ETF)"),
        help="ETF recommended for bonds in Roth IRA",
        key="rebal_bonds_roth"
    )
    
    st.markdown("**Brokerage** (Taxable account)")
    bonds_brokerage = st.text_input(
        "Bonds - Brokerage",
        value=config_mgr.get("rebalancing_preferences", "bonds_brokerage", "VGIT (Vanguard Intermediate-Term Treasury ETF)"),
        help="ETF recommended for bonds in Brokerage (prefer Treasuries/munis for tax efficiency)",
        key="rebal_bonds_brok"
    )
    
    st.markdown("---")
    st.subheader("📈 Stocks")
    st.markdown("**Traditional IRA** (Tax-deferred growth)")
    stocks_traditional = st.text_input(
        "Stocks - Traditional IRA",
        value=config_mgr.get("rebalancing_preferences", "stocks_traditional", "VFIAX (Vanguard 500 Index Admiral)"),
        help="Mutual fund recommended for stocks in Traditional IRA",
        key="rebal_stocks_trad"
    )
    
    st.markdown("**Roth IRA** (Tax-free growth)")
    stocks_roth = st.text_input(
        "Stocks - Roth IRA",
        value=config_mgr.get("rebalancing_preferences", "stocks_roth", "VTI (Vanguard Total Market ETF)"),
        help="ETF recommended for stocks in Roth IRA",
        key="rebal_stocks_roth"
    )
    
    st.markdown("**Brokerage** (Taxable account)")
    stocks_brokerage = st.text_input(
        "Stocks - Brokerage",
        value=config_mgr.get("rebalancing_preferences", "stocks_brokerage", "VTI (Vanguard Total Market ETF)"),
        help="ETF recommended for stocks in Brokerage (for LTCG rates and tax-loss harvesting)",
        key="rebal_stocks_brok"
    )
    
    st.markdown("---")
    
    # Helper function to extract ticker symbol from input (handles "SYMBOL (Description)" format)
    def extract_ticker(symbol_input: str | None) -> str:
        """Extract ticker symbol from input like 'VTI (Vanguard Total Market ETF)'"""
        if not symbol_input:
            return ""
        # If there's a parenthesis, take everything before it
        if "(" in symbol_input:
            return symbol_input.split("(")[0].strip()
        return symbol_input.strip()
    
    # Validate and Save buttons side by side
    rebal_col1, rebal_col2 = st.columns(2)
    
    with rebal_col1:
        if st.button("🔍 Validate Tickers", use_container_width=True, key="validate_rebal_tickers"):
            validation_results = []
            symbols_to_validate = {
                "Cash": extract_ticker(cash_symbol),
                "Bonds - Traditional": extract_ticker(bonds_traditional),
                "Bonds - Roth": extract_ticker(bonds_roth),
                "Bonds - Brokerage": extract_ticker(bonds_brokerage),
                "Stocks - Traditional": extract_ticker(stocks_traditional),
                "Stocks - Roth": extract_ticker(stocks_roth),
                "Stocks - Brokerage": extract_ticker(stocks_brokerage),
            }
            
            all_valid = True
            with st.spinner("Validating ticker symbols..."):
                for label, ticker in symbols_to_validate.items():
                    if not ticker or ticker.upper() == "MF:CASH":
                        # Skip validation for cash and empty fields
                        validation_results.append((label, ticker, True, "Cash symbol", ""))
                        continue
                    
                    is_valid, name, sector, error_msg = validate_ticker_symbol(ticker)
                    validation_results.append((label, ticker, is_valid, name, error_msg))
                    if not is_valid:
                        all_valid = False
            
            # Display results
            if all_valid:
                st.success("✅ All ticker symbols are valid!")
                for label, ticker, is_valid, name, error_msg in validation_results:
                    if ticker and ticker.upper() != "MF:CASH":
                        st.markdown(f"  - **{label}**: `{ticker}` - {name} ✓")
            else:
                st.error("❌ Some ticker symbols are invalid:")
                for label, ticker, is_valid, name, error_msg in validation_results:
                    if not is_valid:
                        st.markdown(f"  - **{label}**: `{ticker}` ❌ {error_msg}")
                    elif ticker and ticker.upper() != "MF:CASH":
                        st.markdown(f"  - **{label}**: `{ticker}` - {name} ✓")
    
    with rebal_col2:
        if st.button("💾 Save Preferences", type="primary", use_container_width=True, key="save_rebal_prefs"):
            config_mgr.set("rebalancing_preferences", "cash_symbol", cash_symbol)
            config_mgr.set("rebalancing_preferences", "bonds_traditional", bonds_traditional)
            config_mgr.set("rebalancing_preferences", "bonds_roth", bonds_roth)
            config_mgr.set("rebalancing_preferences", "bonds_brokerage", bonds_brokerage)
            config_mgr.set("rebalancing_preferences", "stocks_traditional", stocks_traditional)
            config_mgr.set("rebalancing_preferences", "stocks_roth", stocks_roth)
            config_mgr.set("rebalancing_preferences", "stocks_brokerage", stocks_brokerage)
            
            if config_mgr.save_config():
                st.success("✅ Rebalancing preferences saved successfully!")
                changes_made = True
            else:
                st.error("❌ Failed to save rebalancing preferences")
    
    st.info("""
    💡 **Tips:**
    - Use mutual funds (e.g., VBTLX, VFIAX) in Traditional IRAs for lower costs
    - Use ETFs (e.g., VTI, BND) in Roth IRAs and Brokerage for flexibility
    - For bonds in Brokerage, prefer Treasury ETFs (VGIT) or municipal bonds for tax efficiency
    - Include the full name in parentheses for clarity (e.g., "VTI (Vanguard Total Market ETF)")
    """)

# Bucket Strategy Tab
with tab9:
    st.header("🪣 Bucket Strategy Configuration")
    st.markdown("""
    The **Bucket Strategy** is a retirement portfolio management approach that divides your assets into three buckets 
    based on when you'll need the money. This helps manage sequence of returns risk and provides peace of mind.
    """)
    
    # Enable/Disable Bucket Strategy
    bucket_enabled = st.checkbox(
        "Enable Bucket Strategy",
        value=config_mgr.get("bucket_strategy", "enabled", False),
        help="Enable the three-bucket retirement strategy for your portfolio",
        key="bucket_enabled"
    )
    
    if bucket_enabled:
        st.info("""
        **📚 How the Bucket Strategy Works:**
        - **Bucket 1 (Safety)**: Cash for near-term expenses (Years 1-2)
        - **Bucket 2 (Transition)**: Graduated stock/bond mix (Years 3-10)
        - **Bucket 3 (Growth)**: Long-term growth stocks (Years 11+)
        
        The strategy automatically rebalances based on market conditions to protect against sequence of returns risk.
        """)
        
        st.markdown("---")
        st.subheader("Bucket Sizing")
        
        col1, col2 = st.columns(2)
        
        with col1:
            bucket_1_years = st.number_input(
                "Bucket 1: Years of Expenses (Safety)",
                min_value=1.0,
                max_value=5.0,
                value=float(config_mgr.get("bucket_strategy", "bucket_1_years", 2)),
                step=0.5,
                help="Number of years of expenses to keep in cash/money market (typically 1-3 years)",
                key="bucket_1_years"
            )
            
            bucket_2_years = st.number_input(
                "Bucket 2: Years of Expenses (Transition)",
                min_value=5,
                max_value=15,
                value=int(config_mgr.get("bucket_strategy", "bucket_2_years", 8)),
                step=1,
                help="Number of years of expenses in the transition zone with graduated allocation (typically 5-10 years)",
                key="bucket_2_years"
            )
        
        with col2:
            st.markdown("**Bucket 3: Growth**")
            st.info(f"""
            Bucket 3 automatically contains all remaining funds beyond Buckets 1 and 2.
            
            **Total Coverage:** {bucket_1_years + bucket_2_years} years of expenses in Buckets 1 & 2
            """)
        
        st.markdown("---")
        st.subheader("Bucket 2 Allocation Strategy")
        st.markdown("Configure how stock allocation graduates through Bucket 2 years:")
        
        col3, col4 = st.columns(2)
        
        with col3:
            bucket_2_start_stock_pct = st.slider(
                "Starting Stock % (Year 1 of Bucket 2)",
                min_value=0,
                max_value=50,
                value=int(config_mgr.get("bucket_strategy", "bucket_2_start_stock_pct", 10)),
                step=5,
                help="Stock allocation at the beginning of Bucket 2 (typically 10-20%)",
                key="bucket_2_start_stock_pct"
            )
        
        with col4:
            bucket_2_end_stock_pct = st.slider(
                "Ending Stock % (Final Year of Bucket 2)",
                min_value=50,
                max_value=100,
                value=int(config_mgr.get("bucket_strategy", "bucket_2_end_stock_pct", 80)),
                step=5,
                help="Stock allocation at the end of Bucket 2 (typically 70-90%)",
                key="bucket_2_end_stock_pct"
            )
        
        # Show allocation progression
        st.markdown("**Allocation Progression Through Bucket 2:**")
        progression_data = []
        for year in range(1, bucket_2_years + 1):
            stock_pct = bucket_2_start_stock_pct + (
                (bucket_2_end_stock_pct - bucket_2_start_stock_pct) * (year - 1) / (bucket_2_years - 1)
            )
            bond_pct = 100 - stock_pct
            progression_data.append({
                "Year": f"Year {year}",
                "Stocks %": f"{stock_pct:.0f}%",
                "Bonds %": f"{bond_pct:.0f}%"
            })
        
        progression_df = pd.DataFrame(progression_data)
        st.dataframe(progression_df, hide_index=True, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Market Trend Adjustments")
        st.markdown("Automatically adjust allocations based on market conditions:")
        
        market_trend_enabled = st.checkbox(
            "Enable Market Trend-Based Adjustments",
            value=config_mgr.get("bucket_strategy", "market_trend_adjustment", {}).get("enabled", True),
            help="Dynamically adjust stock allocations based on market moving averages",
            key="market_trend_enabled"
        )
        
        if market_trend_enabled:
            st.info("""
            **📈 Market Trend Analysis:**
            - Uses 10-week and 50-week moving averages of SPY (S&P 500)
            - Automatically reduces stock exposure in warning/bear markets
            - Helps protect against market downturns
            """)
            
            col5, col6 = st.columns(2)
            
            with col5:
                short_ma_weeks = st.number_input(
                    "Short-term Moving Average (weeks)",
                    min_value=5,
                    max_value=20,
                    value=int(config_mgr.get("bucket_strategy", "market_trend_adjustment", {}).get("short_ma_weeks", 10)),
                    help="Short-term MA for trend detection (default: 10 weeks)",
                    key="short_ma_weeks"
                )
                
                long_ma_weeks = st.number_input(
                    "Long-term Moving Average (weeks)",
                    min_value=30,
                    max_value=100,
                    value=int(config_mgr.get("bucket_strategy", "market_trend_adjustment", {}).get("long_ma_weeks", 50)),
                    help="Long-term MA for trend detection (default: 50 weeks)",
                    key="long_ma_weeks"
                )
            
            with col6:
                st.markdown("**Allocation Adjustments by Market Condition:**")
                
                bull_adjustment = st.number_input(
                    "Bull Market Adjustment (%)",
                    min_value=-10.0,
                    max_value=10.0,
                    value=float(config_mgr.get("bucket_strategy", "market_trend_adjustment", {}).get("bull_adjustment", 0.0)),
                    step=1.0,
                    help="Stock % adjustment in bull markets (typically 0%)",
                    key="bull_adjustment"
                )
                
                warning_adjustment = st.number_input(
                    "Warning Market Adjustment (%)",
                    min_value=-30.0,
                    max_value=0.0,
                    value=float(config_mgr.get("bucket_strategy", "market_trend_adjustment", {}).get("warning_adjustment", -10.0)),
                    step=1.0,
                    help="Stock % adjustment in warning markets (typically -10%)",
                    key="warning_adjustment"
                )
                
                bear_adjustment = st.number_input(
                    "Bear Market Adjustment (%)",
                    min_value=-50.0,
                    max_value=0.0,
                    value=float(config_mgr.get("bucket_strategy", "market_trend_adjustment", {}).get("bear_adjustment", -20.0)),
                    step=1.0,
                    help="Stock % adjustment in bear markets (typically -20%)",
                    key="bear_adjustment"
                )
        
        st.markdown("---")
        st.success("""
        ✅ **Bucket Strategy Enabled**
        
        Your portfolio will be analyzed and managed according to the bucket strategy. 
        View your current bucket allocation on the Dashboard.
        """)
    else:
        st.warning("""
        ⚠️ **Bucket Strategy Disabled**
        
        Enable the bucket strategy to:
        - Manage sequence of returns risk
        - Automatically rebalance based on market conditions
        - Maintain appropriate cash reserves
        - Graduate stock allocation over time
        
        Check the box above to enable this feature.
        """)


# Advanced Tab
with tab10:
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
                "person1_preretirement_coverage_type": person1_preretirement_coverage_type,
                "person1_preretirement_insurance_monthly": person1_preretirement_insurance_monthly,
                "person1_retirement_coverage_type": person1_retirement_coverage_type,
                "person1_aca_insurance_monthly": person1_aca_insurance_monthly,
                "person1_aca_start_age": person1_aca_start_age,
                "person1_aca_end_age": person1_aca_end_age,
                "person1_medicare_start_age": person1_medicare_start_age,
                "person2_preretirement_coverage_type": person2_preretirement_coverage_type,
                "person2_preretirement_insurance_monthly": person2_preretirement_insurance_monthly,
                "person2_retirement_coverage_type": person2_retirement_coverage_type,
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
                # SS Optimization fields
                "person1_birth_year": st.session_state.get("person1_birth_year_opt", 1960),
                "person1_gender": st.session_state.get("person1_gender_opt", 'M'),
                "person1_life_expectancy": st.session_state.get("person1_life_exp_opt", 84),
                "person1_current_earnings": st.session_state.get("person1_earnings_opt", 0),
                "person2_birth_year": st.session_state.get("person2_birth_year_opt", 1962),
                "person2_gender": st.session_state.get("person2_gender_opt", 'F'),
                "person2_life_expectancy": st.session_state.get("person2_life_exp_opt", 87),
                "person2_current_earnings": st.session_state.get("person2_earnings_opt", 0),
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
            
            # Save bucket strategy configuration
            if st.session_state.get("bucket_enabled", False):
                market_trend_config = {}
                if st.session_state.get("market_trend_enabled", True):
                    market_trend_config = {
                        "enabled": True,
                        "short_ma_weeks": st.session_state.get("short_ma_weeks", 10),
                        "long_ma_weeks": st.session_state.get("long_ma_weeks", 50),
                        "bull_adjustment": st.session_state.get("bull_adjustment", 0.0),
                        "warning_adjustment": st.session_state.get("warning_adjustment", -10.0),
                        "bear_adjustment": st.session_state.get("bear_adjustment", -20.0),
                    }
                else:
                    market_trend_config = {"enabled": False}
                
                config_mgr.update_section("bucket_strategy", {
                    "enabled": True,
                    "bucket_1_years": st.session_state.get("bucket_1_years", 2),
                    "bucket_2_years": st.session_state.get("bucket_2_years", 8),
                    "bucket_2_start_stock_pct": st.session_state.get("bucket_2_start_stock_pct", 10),
                    "bucket_2_end_stock_pct": st.session_state.get("bucket_2_end_stock_pct", 80),
                    "market_trend_adjustment": market_trend_config,
                })
            else:
                config_mgr.update_section("bucket_strategy", {
                    "enabled": False,
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
