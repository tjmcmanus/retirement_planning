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
    backup_portfolio_data,
    start_from_scratch,
    revert_to_last_backup,
    VALID_ACCOUNT_TYPES,
    get_valid_account_owners,
    VALID_SECTORS,
)
from portfolio_db import db_load_all, migrate_from_csv as _migrate_from_csv
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
tab1, tab2, tab2b, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "👤 Personal Info",
    "💰 Financial Assumptions",
    "💳 Expenses",
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
    
    # Single person checkbox
    is_single_person = st.checkbox(
        "Planning for single person (not a couple)",
        value=config_mgr.get("personal_info", "is_single_person", False),
        help="Check this if you are planning for yourself only. This will hide spouse/partner fields and use single filing status for tax calculations.",
        key="is_single_person"
    )
    
    if is_single_person:
        st.info("💡 **Single Person Mode**: The application will assume single filing status and optimize strategies for one person.")
    
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
        if not is_single_person:
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
        else:
            # Set default values for person2 when in single mode
            person2_name = ""
            person2_birth_date = datetime.strptime("1967-01-01", "%Y-%m-%d")
            person2_retirement_age = 62
            st.subheader("Spouse/Partner")
            st.info("👤 Single person mode - spouse/partner information hidden")
    
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
    # Stage 7: Surviving Spouse Configuration
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.subheader("💔 Stage 7: Surviving Spouse Planning")
    
    # Only show if not in single person mode
    if not is_single_person:
        surviving_spouse_mode = st.checkbox(
            "Planning for surviving spouse scenario (Stage 7)",
            value=config_mgr.get("personal_info", "surviving_spouse_mode", False),
            help="Check this if you are planning for a scenario where one spouse has passed away. This activates Stage 7 planning with single filer tax status and survivor benefits.",
            key="surviving_spouse_mode"
        )
        
        if surviving_spouse_mode:
            st.info("🔔 **Stage 7 Mode Active**: Planning will account for single filer tax status, survivor Social Security benefits, and estate transition considerations.")
            
            col_dec1, col_dec2 = st.columns(2)
            
            with col_dec1:
                # Select which person is deceased
                decedent_options = ["person1", "person2"]
                decedent_labels = [
                    f"{person1_name or 'Person 1'} (Primary)",
                    f"{person2_name or 'Person 2'} (Spouse/Partner)"
                ]
                
                current_decedent = config_mgr.get("personal_info", "decedent_person", None)
                try:
                    decedent_index = decedent_options.index(current_decedent) if current_decedent else 0
                except (ValueError, TypeError):
                    decedent_index = 0
                
                decedent_person = st.selectbox(
                    "Decedent (Deceased Person)",
                    options=decedent_options,
                    format_func=lambda x: decedent_labels[decedent_options.index(x)],
                    index=decedent_index,
                    help="Select which person has passed away",
                    key="decedent_person"
                )
                
                # Determine survivor name
                if decedent_person == "person1":
                    survivor_name = person2_name or "Person 2"
                    decedent_name = person1_name or "Person 1"
                else:
                    survivor_name = person1_name or "Person 1"
                    decedent_name = person2_name or "Person 2"
                
                st.caption(f"**Survivor**: {survivor_name}")
            
            with col_dec2:
                # Date of death
                current_dod = config_mgr.get("personal_info", "date_of_death", None)
                if current_dod:
                    try:
                        dod_value = datetime.strptime(current_dod, "%Y-%m-%d")
                    except ValueError:
                        dod_value = datetime.now()
                else:
                    dod_value = datetime.now()
                
                date_of_death = st.date_input(
                    "Date of Death",
                    value=dod_value,
                    help="Date when the decedent passed away. Used for tax filing status changes and benefit calculations.",
                    key="date_of_death"
                )
                
                # Calculate year of death for display
                year_of_death = date_of_death.year
                st.caption(f"**Year of Death**: {year_of_death}")
                st.caption(f"**Tax Status**: MFJ in {year_of_death}, Single from {year_of_death + 1} onward")
            
            # Stage 7 To-Do Checklist
            st.markdown("---")
            st.markdown("### 📋 Surviving Spouse Transition Checklist")
            st.markdown(f"**Important tasks for {survivor_name} after the loss of {decedent_name}:**")
            
            # Create checklist in an expander for better organization
            with st.expander("📝 View Complete Checklist", expanded=True):
                st.markdown("""
                #### Immediate Actions (First 30 Days)
                - ☐ Obtain multiple certified copies of death certificate (10-15 copies)
                - ☐ Contact Social Security Administration to report death and apply for survivor benefits
                - ☐ Notify Medicare and update coverage if applicable
                - ☐ Contact life insurance companies to file claims
                - ☐ Notify employer(s) and apply for any death benefits
                
                #### Financial Account Updates (30-90 Days)
                - ☐ Update beneficiary designations on all accounts
                - ☐ Retitle joint accounts to survivor's name only
                - ☐ Roll over inherited retirement accounts (IRA, 401k) within 60 days if needed
                - ☐ Review and update RMD requirements for inherited accounts
                - ☐ Consolidate accounts where appropriate
                - ☐ Update bank account signatories and access
                
                #### Tax and Legal (Within 1 Year)
                - ☐ File final joint tax return for year of death (MFJ status)
                - ☐ Update tax filing status to Single for subsequent years
                - ☐ Review and update estate planning documents (will, trust, POA)
                - ☐ Consult with estate attorney about probate if needed
                - ☐ File estate tax return if estate exceeds exemption threshold
                
                #### Benefits Optimization
                - ☐ **Social Security**: Survivor receives higher of own benefit or 100% of deceased spouse's benefit
                - ☐ **Medicare**: Continue own Medicare coverage (Part B premium based on survivor's income)
                - ☐ Review pension survivor benefits if applicable
                - ☐ Update health insurance coverage if needed
                
                #### Long-Term Planning (Ongoing)
                - ☐ Review and adjust investment strategy for single person household
                - ☐ Update budget for single person expenses
                - ☐ Review IRMAA thresholds (single filer has lower thresholds than MFJ)
                - ☐ Optimize Roth conversions with new single filer tax brackets
                - ☐ Consider downsizing or relocating if appropriate
                - ☐ Update emergency contacts and healthcare proxies
                
                #### Professional Guidance
                - ☐ Consult with financial advisor to review overall plan
                - ☐ Meet with tax professional for tax planning
                - ☐ Consider grief counseling or support groups
                """)
            
            st.warning(
                f"⚠️ **Important**: Stage 7 planning assumes {survivor_name} will file as Single starting in "
                f"{year_of_death + 1}. Single filer tax brackets are less favorable than Married Filing Jointly, "
                f"which may impact Roth conversion strategies and IRMAA thresholds."
            )
            
            st.info(
                f"💡 **Survivor Benefits**: {survivor_name} will receive the higher of their own Social Security "
                f"benefit or 100% of {decedent_name}'s benefit (not both). Medicare coverage continues based on "
                f"{survivor_name}'s own enrollment."
            )
        else:
            # Set default values when not in surviving spouse mode
            decedent_person = None
            date_of_death = None
    else:
        # Single person mode - hide surviving spouse options
        st.info("👤 Surviving spouse planning is not applicable in single person mode.")
        surviving_spouse_mode = False
        decedent_person = None
        date_of_death = None


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
    
    # Expected Annual Expenses Breakdown
    st.subheader("Expected Annual Expenses")
    st.markdown("Your annual expenses are calculated from the detailed breakdown in the **💳 Expenses** tab.")
    
    # Calculate living expenses total
    living_expenses_dict = config_mgr.get("expenses", "living_expenses", {})
    total_living = sum([
        living_expenses_dict.get("property_tax", 0),
        living_expenses_dict.get("homeowners_insurance", 0),
        living_expenses_dict.get("auto_insurance", 0),
        living_expenses_dict.get("food_groceries", 0),
        living_expenses_dict.get("utilities_phone", 0),
        living_expenses_dict.get("utilities_internet", 0),
        living_expenses_dict.get("utilities_cable", 0),
        living_expenses_dict.get("utilities_electric", 0),
        living_expenses_dict.get("utilities_gas", 0),
        living_expenses_dict.get("utilities_water", 0),
        living_expenses_dict.get("gifts_donations", 0),
        living_expenses_dict.get("other_living", 0)
    ])
    
    # Calculate entertainment expenses total
    entertainment_dict = config_mgr.get("expenses", "entertainment_expenses", {})
    total_entertainment = sum([
        entertainment_dict.get("travel_vacations", 0),
        entertainment_dict.get("dining_out", 0),
        entertainment_dict.get("clothing", 0),
        entertainment_dict.get("hobbies", 0),
        entertainment_dict.get("entertainment_other", 0)
    ])
    
    # Calculate big ticket items summary
    big_ticket_items = config_mgr.get("expenses", "big_ticket_items", [])
    if not isinstance(big_ticket_items, list):
        big_ticket_items = []
    
    big_ticket_summary = []
    for item in big_ticket_items:
        if isinstance(item, dict) and item.get("name") and item.get("amount", 0) > 0:
            big_ticket_summary.append(f"{item['name']}: ${item['amount']:,.0f} every {item.get('frequency_years', 10)} years")
    
    # Calculate total
    total_annual_expenses = total_living + total_entertainment
    
    # Display breakdown in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Living Expenses",
            f"${total_living:,.0f}",
            help="Ongoing expenses that don't go away in retirement (property tax, insurance, utilities, food, etc.)"
        )
    
    with col2:
        st.metric(
            "Entertainment Expenses",
            f"${total_entertainment:,.0f}",
            help="Lifestyle expenses that may decline with age (travel, dining out, hobbies, etc.)"
        )
    
    with col3:
        st.metric(
            "Total Annual Expenses",
            f"${total_annual_expenses:,.0f}",
            help="Sum of living and entertainment expenses (excludes big ticket items)"
        )
    
    # Show big ticket items if any exist
    if big_ticket_summary:
        st.markdown("---")
        st.markdown("**Big Ticket Items** (periodic major expenses):")
        for item_desc in big_ticket_summary:
            st.caption(f"• {item_desc}")
        st.caption("*Big ticket items are handled separately in the strategy engine based on their frequency and timing.*")
    else:
        st.info("💡 No big ticket items configured. Add them in the **💳 Expenses** tab if you have periodic major expenses (cars, home renovations, etc.).")
    
    st.markdown("---")
    st.caption("📝 To modify these values, go to the **💳 Expenses** tab and update the detailed breakdown.")
    
    # Store the calculated total in session state for compatibility
    st.session_state["expected_annual_expenses"] = total_annual_expenses
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
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
        
        brokerage_rebalance_trigger_multiplier = st.number_input(
            "Taxable Account Buffer Multiplier",
            min_value=0.5,
            max_value=5.0,
            value=float(config_mgr.get("financial_assumptions", "brokerage_rebalance_trigger_multiplier", 1.0)),
            step=0.5,
            help=(
                "Multiplier for taxable/brokerage account buffer target. "
                "The base target is 1 year of expenses. "
                "Example: 2.0 = maintain 2 years of expenses in taxable account. "
                "Higher values = more conservative buffer, triggers replenishment earlier."
            ),
            key="brokerage_rebalance_trigger_multiplier"
        )
        
        # Show the dollar equivalent
        if total_annual_expenses > 0:
            taxable_target = total_annual_expenses * brokerage_rebalance_trigger_multiplier
            st.caption(
                f"≈ ${taxable_target:,.0f} taxable account trigger level "
                f"({brokerage_rebalance_trigger_multiplier:.1f}x × ${total_annual_expenses:,.0f} expenses)"
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
        cash_reserve = st.session_state.get("expected_annual_expenses", 0) * years_of_expenses_in_cash
        st.metric("Recommended Cash Reserve", f"${cash_reserve:,.0f}")
    
    with col_calc2:
        total_household_income = person1_annual_wages + person2_annual_wages
        st.metric("Total Household Income", f"${total_household_income:,.0f}")

# Expenses Tab
with tab2b:
    st.header("💳 Expense Planning")
    st.markdown("Configure your detailed expenses to get accurate retirement planning projections.")
    
    # Create sub-tabs for different expense categories
    expense_tab1, expense_tab2, expense_tab3 = st.tabs([
        "🏠 Living Expenses",
        "🚗 Big Ticket Items",
        "🎭 Entertainment & Lifestyle"
    ])
    
    # Living Expenses Sub-tab
    with expense_tab1:
        st.subheader("Living Expenses")
        st.markdown("""
        These are ongoing expenses that **do not go away** in retirement. They typically increase with inflation.
        Enter annual amounts for each category.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Housing & Property**")
            property_tax = st.number_input(
                "Property Tax (Annual)",
                min_value=0,
                max_value=100000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("property_tax", 0),
                step=100,
                help="Annual property tax on your primary residence",
                key="property_tax"
            )
            
            homeowners_insurance = st.number_input(
                "Homeowners Insurance (Annual)",
                min_value=0,
                max_value=50000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("homeowners_insurance", 0),
                step=100,
                help="Annual homeowners or renters insurance premium",
                key="homeowners_insurance"
            )
            
            st.markdown("**Transportation**")
            auto_insurance = st.number_input(
                "Auto Insurance (Annual)",
                min_value=0,
                max_value=20000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("auto_insurance", 0),
                step=100,
                help="Annual auto insurance for all vehicles",
                key="auto_insurance"
            )
            
            st.markdown("**Food & Essentials**")
            food_groceries = st.number_input(
                "Food & Groceries (Annual)",
                min_value=0,
                max_value=100000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("food_groceries", 0),
                step=500,
                help="Annual spending on groceries and food",
                key="food_groceries"
            )
        
        with col2:
            st.markdown("**Utilities**")
            utilities_phone = st.number_input(
                "Phone (Annual)",
                min_value=0,
                max_value=10000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("utilities_phone", 0),
                step=50,
                help="Annual phone service costs (mobile, landline)",
                key="utilities_phone"
            )
            
            utilities_internet = st.number_input(
                "Internet (Annual)",
                min_value=0,
                max_value=10000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("utilities_internet", 0),
                step=50,
                help="Annual internet service costs",
                key="utilities_internet"
            )
            
            utilities_cable = st.number_input(
                "Cable/Streaming (Annual)",
                min_value=0,
                max_value=10000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("utilities_cable", 0),
                step=50,
                help="Annual cable TV or streaming service costs",
                key="utilities_cable"
            )
            
            utilities_electric = st.number_input(
                "Electric (Annual)",
                min_value=0,
                max_value=20000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("utilities_electric", 0),
                step=100,
                help="Annual electricity costs",
                key="utilities_electric"
            )
            
            utilities_gas = st.number_input(
                "Gas/Heating (Annual)",
                min_value=0,
                max_value=20000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("utilities_gas", 0),
                step=100,
                help="Annual natural gas or heating oil costs",
                key="utilities_gas"
            )
            
            utilities_water = st.number_input(
                "Water/Sewer (Annual)",
                min_value=0,
                max_value=10000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("utilities_water", 0),
                step=50,
                help="Annual water and sewer costs",
                key="utilities_water"
            )
        
        st.markdown("---")
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown("**Other Living Expenses**")
            gifts_donations = st.number_input(
                "Gifts & Donations (Annual)",
                min_value=0,
                max_value=100000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("gifts_donations", 0),
                step=100,
                help="Annual spending on gifts, charitable donations (non-tax-deductible)",
                key="gifts_donations"
            )
            
            other_living = st.number_input(
                "Other Living Expenses (Annual)",
                min_value=0,
                max_value=100000,
                value=config_mgr.get("expenses", "living_expenses", {}).get("other_living", 0),
                step=100,
                help="Other recurring annual expenses not listed above",
                key="other_living"
            )
        
        with col4:
            # Calculate total living expenses
            total_living = (
                property_tax + homeowners_insurance + auto_insurance + food_groceries +
                utilities_phone + utilities_internet + utilities_cable + utilities_electric +
                utilities_gas + utilities_water + gifts_donations + other_living
            )
            st.markdown("**Summary**")
            st.metric("Total Annual Living Expenses", f"${total_living:,.0f}")
            st.caption("These expenses will be included in your annual expense calculations and will increase with inflation.")
    
    # Big Ticket Items Sub-tab
    with expense_tab2:
        st.subheader("Big Ticket Items")
        st.markdown("""
        These are major purchases that occur periodically (every 10-20 years). Examples include:
        - **New car** every 10-15 years
        - **Weddings** for children
        - **College tuition** for children
        - **Major home renovations**
        - **Roof replacement**
        """)
        
        # Load existing big ticket items
        existing_items = config_mgr.get("expenses", "big_ticket_items", [])
        if not isinstance(existing_items, list):
            existing_items = []
        
        # Create DataFrame for editing
        if existing_items:
            big_ticket_df = pd.DataFrame(existing_items)
        else:
            # Empty template
            big_ticket_df = pd.DataFrame([{
                "name": "",
                "amount": 0,
                "frequency_years": 10,
                "start_year": datetime.now().year,
                "end_year": datetime.now().year + 30
            }])
        
        st.caption(
            "Add major expenses that occur periodically. The system will include these in your "
            "retirement projections at the specified frequency."
        )
        
        edited_big_ticket_df = st.data_editor(
            big_ticket_df,
            column_config={
                "name": st.column_config.TextColumn(
                    "Item Name",
                    help="Description of the expense (e.g., 'New Car', 'Daughter's Wedding')",
                    max_chars=100,
                    required=True
                ),
                "amount": st.column_config.NumberColumn(
                    "Amount ($)",
                    help="Cost of the item in today's dollars",
                    min_value=0,
                    max_value=1000000,
                    step=1000,
                    format="$%d",
                    required=True
                ),
                "frequency_years": st.column_config.NumberColumn(
                    "Frequency (Years)",
                    help="How often this expense occurs (e.g., 10 for every 10 years)",
                    min_value=1,
                    max_value=50,
                    step=1,
                    required=True
                ),
                "start_year": st.column_config.NumberColumn(
                    "Start Year",
                    help="First year this expense will occur",
                    min_value=2020,
                    max_value=2100,
                    step=1,
                    required=True
                ),
                "end_year": st.column_config.NumberColumn(
                    "End Year",
                    help="Last year this expense could occur",
                    min_value=2020,
                    max_value=2100,
                    step=1,
                    required=True
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            key="big_ticket_editor"
        )
        
        # Validate and show summary
        valid_items = []
        total_big_ticket = 0
        
        for idx, row in edited_big_ticket_df.iterrows():
            name = str(row.get("name", "")).strip()
            amount = float(row.get("amount", 0))
            freq = int(row.get("frequency_years", 10))
            start = int(row.get("start_year", datetime.now().year))
            end = int(row.get("end_year", datetime.now().year + 30))
            
            if name and amount > 0:
                valid_items.append({
                    "name": name,
                    "amount": amount,
                    "frequency_years": freq,
                    "start_year": start,
                    "end_year": end
                })
                # Calculate approximate total over planning period
                years_active = max(0, end - start)
                occurrences = max(1, years_active // freq)
                total_big_ticket += amount * occurrences
        
        if valid_items:
            st.markdown("---")
            st.markdown("**Summary of Big Ticket Items**")
            for item in valid_items:
                years_active = max(0, item["end_year"] - item["start_year"])
                occurrences = max(1, years_active // item["frequency_years"])
                st.caption(
                    f"• **{item['name']}**: ${item['amount']:,.0f} every {item['frequency_years']} years "
                    f"({item['start_year']}-{item['end_year']}) ≈ {occurrences} occurrences"
                )
            st.metric("Estimated Total (All Occurrences)", f"${total_big_ticket:,.0f}")
    
    # Entertainment & Lifestyle Sub-tab
    with expense_tab3:
        st.subheader("Entertainment & Lifestyle Expenses")
        st.markdown("""
        These expenses typically **decline in retirement** as activity levels decrease. 
        You can configure how much these expenses reduce after retirement.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Annual Entertainment Expenses**")
            
            travel_vacations = st.number_input(
                "Travel & Vacations (Annual)",
                min_value=0,
                max_value=200000,
                value=config_mgr.get("expenses", "entertainment_expenses", {}).get("travel_vacations", 0),
                step=500,
                help="Annual spending on travel, vacations, trips",
                key="travel_vacations"
            )
            
            dining_out = st.number_input(
                "Dining Out (Annual)",
                min_value=0,
                max_value=100000,
                value=config_mgr.get("expenses", "entertainment_expenses", {}).get("dining_out", 0),
                step=500,
                help="Annual spending on restaurants and dining out",
                key="dining_out"
            )
            
            clothing = st.number_input(
                "Clothing & Personal Care (Annual)",
                min_value=0,
                max_value=100000,
                value=config_mgr.get("expenses", "entertainment_expenses", {}).get("clothing", 0),
                step=500,
                help="Annual spending on clothing, shoes, personal care",
                key="clothing"
            )
            
            hobbies = st.number_input(
                "Hobbies & Recreation (Annual)",
                min_value=0,
                max_value=100000,
                value=config_mgr.get("expenses", "entertainment_expenses", {}).get("hobbies", 0),
                step=500,
                help="Annual spending on hobbies, sports, recreation",
                key="hobbies"
            )
            
            entertainment_other = st.number_input(
                "Other Entertainment (Annual)",
                min_value=0,
                max_value=100000,
                value=config_mgr.get("expenses", "entertainment_expenses", {}).get("entertainment_other", 0),
                step=500,
                help="Other entertainment and lifestyle expenses",
                key="entertainment_other"
            )
        
        with col2:
            st.markdown("**Retirement Decline Settings**")
            
            retirement_decline_enabled = st.checkbox(
                "Enable retirement decline",
                value=config_mgr.get("expenses", "entertainment_expenses", {}).get("retirement_decline_enabled", True),
                help="Reduce entertainment expenses in retirement",
                key="retirement_decline_enabled"
            )
            
            if retirement_decline_enabled:
                retirement_decline_percent = st.slider(
                    "Retirement Decline (%)",
                    min_value=0,
                    max_value=100,
                    value=config_mgr.get("expenses", "entertainment_expenses", {}).get("retirement_decline_percent", 30),
                    step=5,
                    help="Percentage reduction in entertainment expenses during retirement",
                    key="retirement_decline_percent"
                )
                
                retirement_decline_start_age = st.number_input(
                    "Decline Start Age",
                    min_value=50,
                    max_value=80,
                    value=config_mgr.get("expenses", "entertainment_expenses", {}).get("retirement_decline_start_age", 65),
                    help="Age when entertainment expenses begin to decline",
                    key="retirement_decline_start_age"
                )
            else:
                retirement_decline_percent = 0
                retirement_decline_start_age = 65
            
            # Calculate totals
            total_entertainment = (
                travel_vacations + dining_out + clothing + hobbies + entertainment_other
            )
            
            st.markdown("---")
            st.markdown("**Summary**")
            st.metric("Total Annual Entertainment", f"${total_entertainment:,.0f}")
            
            if retirement_decline_enabled and total_entertainment > 0:
                retirement_amount = total_entertainment * (1 - retirement_decline_percent / 100)
                st.metric(
                    f"In Retirement (Age {retirement_decline_start_age}+)",
                    f"${retirement_amount:,.0f}",
                    delta=f"-{retirement_decline_percent}%",
                    delta_color="normal"
                )
                st.caption(f"Entertainment expenses will decline by {retirement_decline_percent}% starting at age {retirement_decline_start_age}")
    
    # Overall Expense Summary
    st.markdown("---")
    st.subheader("📊 Total Expense Summary")
    
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    
    with col_sum1:
        st.metric("Living Expenses (Annual)", f"${total_living:,.0f}")
        st.caption("Ongoing expenses that don't go away")
    
    with col_sum2:
        st.metric("Entertainment (Annual)", f"${total_entertainment:,.0f}")
        st.caption(f"Declines {retirement_decline_percent}% in retirement" if retirement_decline_enabled else "No decline in retirement")
    
    with col_sum3:
        total_annual = total_living + total_entertainment
        st.metric("Total Annual Expenses", f"${total_annual:,.0f}")
        st.caption("Before retirement (working years)")
    
    # Show note about automatic calculation
    if total_annual > 0:
        st.success(
            f"✅ **Automatic Calculation**: When you save your configuration, the 'Expected Annual Expenses' "
            f"in Financial Assumptions will be automatically set to ${total_annual:,.0f} based on your detailed expense breakdown."
        )
    else:
        st.info(
            "💡 **Tip**: Enter your detailed expenses above. The system will automatically calculate your total "
            "annual expenses and use that value in your retirement planning strategy."
        )


# Healthcare Tab
with tab3:
    st.header("Healthcare Planning")
    st.markdown("Comprehensive healthcare planning including costs, long-term care, HSA, and Medicare enrollment.")
    
    # Create 4 sub-tabs within Healthcare tab
    healthcare_tab1, healthcare_tab2, healthcare_tab3, healthcare_tab4 = st.tabs([
        "💊 Healthcare Costs",
        "🏥 Long-Term Care Planning",
        "💳 Health Savings Account (HSA) Planning",
        "📋 Medicare Enrollment Guide"
    ])
    
    # Healthcare Costs Sub-tab
    with healthcare_tab1:
        st.subheader("Healthcare Costs")
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
        
        # Medicare Guide and Eligibility Checkboxes
        st.markdown("**Medicare Planning Checklist**")
        st.caption("📚 Review the **Medicare Enrollment Guide** tab above for comprehensive information.")
        
        person1_reviewed_medicare_guide = st.checkbox(
            f"✅ {person1_name} has reviewed the Medicare Enrollment Guide",
            value=config_mgr.get("healthcare", "person1_reviewed_medicare_guide", False),
            help=f"Check this after {person1_name} has reviewed the Medicare Enrollment Guide in Advanced Strategies",
            key="person1_reviewed_medicare_guide"
        )
        
        person1_medicare_eligible = st.checkbox(
            f"🏥 {person1_name} is Medicare eligible (or will be at age 65)",
            value=config_mgr.get("healthcare", "person1_medicare_eligible", False),
            help=f"Check this if {person1_name} is eligible for Medicare (typically at age 65, or earlier if disabled)",
            key="person1_medicare_eligible"
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
        if not is_single_person:
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
        else:
            person2_preretirement_coverage_type = "None"
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
        
        # Medicare Guide and Eligibility Checkboxes
        if not is_single_person:
            st.markdown("**Medicare Planning Checklist**")
            st.caption("📚 Review the **Medicare Enrollment Guide** tab above for comprehensive information.")
            
            person2_reviewed_medicare_guide = st.checkbox(
                f"✅ {person2_name} has reviewed the Medicare Enrollment Guide",
                value=config_mgr.get("healthcare", "person2_reviewed_medicare_guide", False),
                help=f"Check this after {person2_name} has reviewed the Medicare Enrollment Guide in Advanced Strategies",
                key="person2_reviewed_medicare_guide"
            )
            
            person2_medicare_eligible = st.checkbox(
                f"🏥 {person2_name} is Medicare eligible (or will be at age 65)",
                value=config_mgr.get("healthcare", "person2_medicare_eligible", False),
                help=f"Check this if {person2_name} is eligible for Medicare (typically at age 65, or earlier if disabled)",
                key="person2_medicare_eligible"
            )
        else:
            person2_reviewed_medicare_guide = False
            person2_medicare_eligible = False
        
        # Display calculated costs for person2
        if person2_aca_insurance_monthly > 0:
            annual_aca_cost_2 = person2_aca_insurance_monthly * 12
            years_on_aca_2 = max(0, person2_aca_end_age - person2_aca_start_age)
            total_aca_cost_2 = annual_aca_cost_2 * years_on_aca_2
            
            st.metric("Annual Retirement Healthcare Cost", f"${annual_aca_cost_2:,.0f}")
            st.metric("Total Retirement Healthcare Cost", f"${total_aca_cost_2:,.0f}",
                     help=f"Total cost for {years_on_aca_2} years on ACA")
        else:
            # Single person mode - set default values for person2
            st.subheader("Spouse/Partner Healthcare")
            st.info("👤 Single person mode - spouse/partner healthcare information hidden")
            person2_preretirement_coverage_type = "None"
            person2_preretirement_insurance_monthly = 0
            person2_retirement_coverage_type = "None"
            person2_aca_insurance_monthly = 0
            person2_aca_start_age = 62
            person2_aca_end_age = 65
            person2_medicare_start_age = 65
    
    # Long-Term Care Planning Sub-tab
    with healthcare_tab2:
        st.subheader("Long-Term Care (LTC) Planning")
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
        
    
    
    # HSA Planning Sub-tab
    with healthcare_tab3:
        st.subheader("Health Savings Account (HSA) Planning")
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
    
    # Medicare Enrollment Guide Sub-tab
    with healthcare_tab4:
        st.subheader("Medicare Enrollment Guide")
        st.markdown("""
        This comprehensive guide helps you navigate Medicare enrollment, understand your options,
        and avoid costly mistakes. Medicare decisions are complex and often irreversible, so it's
        crucial to understand your choices before enrolling.
        
        ⚠️ **Important Recommendation**: For most retirees, **Original Medicare + Medigap (Supplement)**
        is the safer choice despite higher premiums. While Medicare Advantage may seem attractive with
        lower costs, switching back to Medigap later is extremely difficult or impossible due to medical
        underwriting. The freedom and comprehensive coverage of Medigap is worth the extra cost.
        """)
        
        # Overview Section
        with st.expander("📋 Medicare Basics: Parts A, B, C, D", expanded=False):
            st.markdown("""
            #### Understanding Medicare Parts
            
            **Part A (Hospital Insurance)**
            - Covers inpatient hospital stays, skilled nursing facility care, hospice, and some home health care
            - Most people get Part A premium-free if they or their spouse paid Medicare taxes for 10+ years
            - 2026 deductible: $1,632 per benefit period
            
            **Part B (Medical Insurance)**
            - Covers doctor visits, outpatient care, preventive services, medical equipment
            - Standard monthly premium in 2026: $174.70
            - **⚠️ IRMAA Surcharges Apply**: Premium increases based on your MAGI from **2 years prior**
            - Annual deductible: $240, then typically 20% coinsurance
            
            **🚨 CRITICAL: IRMAA (Income-Related Monthly Adjustment Amount)**
            - Part B and Part D premiums increase based on your Modified Adjusted Gross Income (MAGI)
            - **Uses income from 2 years ago** (2026 premiums based on 2024 tax return)
            - Applies to individuals with MAGI > $103,000 or couples > $206,000 (2024 thresholds)
            - Surcharges range from $69.90 to $419.30/month added to Part B premium
            - Part D also has IRMAA surcharges ($12.90 to $81.00/month)
            - **Tax Planning Opportunity**: Manage Roth conversions and withdrawals to minimize IRMAA
            - Life-changing events (marriage, divorce, death of spouse, work stoppage) may allow appeals
            
            **Part C (Medicare Advantage) - ⚠️ Proceed with Caution**
            - Alternative to Original Medicare (Parts A & B)
            - Offered by private insurance companies approved by Medicare
            - Often includes prescription drug coverage (Part D)
            - May offer additional benefits like dental, vision, hearing
            - **Major Drawbacks**:
              - Network restrictions limit doctor and hospital choices
              - Prior authorization required for many services (delays care)
              - **Frequent denials** that can take months to resolve
              - **Very difficult to switch back to Medigap** due to medical underwriting
              - Networks change annually - you may lose your doctors
            - **⚠️ Warning**: This is often a one-way door - choose carefully
            
            **Part D (Prescription Drug Coverage)**
            - Covers prescription medications
            - Offered by private insurance companies
            - Required if you want drug coverage with Original Medicare
            - Late enrollment penalty applies if you delay without creditable coverage
            - Also subject to IRMAA surcharges based on 2-year-prior income
            """)
        
        # Enrollment Timing
        with st.expander("⏰ Critical Enrollment Periods & Penalties", expanded=False):
            st.markdown("""
            #### Initial Enrollment Period (IEP)
            
            **When to Enroll:**
            - 7-month window: 3 months before your 65th birthday month, your birthday month, and 3 months after
            - If still working with employer coverage (20+ employees), you may delay Part B without penalty
            
            **⚠️ Late Enrollment Penalties:**
            
            **Part A Penalty:**
            - If you don't have 40 work credits and miss your IEP
            - 10% premium increase for twice the number of years you were eligible but didn't enroll
            - **This penalty is permanent**
            
            **Part B Penalty:**
            - 10% premium increase for each 12-month period you were eligible but didn't enroll
            - **This penalty is permanent and compounds annually**
            - Example: 2 years late = 20% higher premiums for life
            
            **Part D Penalty:**
            - 1% of the national base beneficiary premium × number of months without coverage
            - **This penalty is permanent**
            - 2026 base premium: ~$34.70, so 1% = $0.35/month per month delayed
            
            #### Special Enrollment Periods (SEP)
            - When you lose employer coverage (8-month window)
            - When you move out of your plan's service area
            - If you qualify for Extra Help with costs
            - Other qualifying life events
            """)
        
        # Decision Tree
        with st.expander("🔀 Decision Guide: Original Medicare vs Medicare Advantage", expanded=False):
            st.markdown("""
            #### Key Decision Factors
            
            **Choose Original Medicare + Medigap if you:**
            - Want freedom to see any doctor/specialist nationwide who accepts Medicare
            - Travel frequently or spend time in multiple states
            - Have complex medical needs requiring specialist care
            - Value predictable out-of-pocket costs
            - Can afford higher monthly premiums for comprehensive coverage
            
            **Choose Medicare Advantage if you:**
            - Prefer lower monthly premiums (often $0)
            - Are comfortable with network restrictions (HMO/PPO)
            - Stay in one geographic area
            - Want extra benefits (dental, vision, hearing, gym membership)
            - Have relatively simple medical needs
            - Can handle potentially higher out-of-pocket costs when sick
            
            #### Cost Comparison Example
            
            **Original Medicare + Medigap Plan G:**
            - Part B Premium: $174.70/month
            - Medigap Plan G: $150-250/month (varies by age, location, company)
            - Part D: $30-80/month
            - **Total: ~$355-505/month**
            - Predictable costs, minimal out-of-pocket when you need care
            
            **Medicare Advantage:**
            - Combined premium: $0-100/month (often $0)
            - Out-of-pocket maximum: $3,000-8,000/year
            - Copays for services: $10-50 per visit
            - **Total: Variable based on usage**
            - Lower monthly cost, but higher costs when you need care
            """)
        
        # The 20% Gap
        with st.expander("💰 Covering the 20% Gap: Medigap vs Advantage", expanded=False):
            st.markdown("""
            #### Understanding the 20% Coinsurance
            
            Original Medicare Part B covers 80% of approved costs after you meet the deductible.
            You're responsible for the remaining 20%, which has **no annual limit**. This can be
            financially devastating for expensive treatments.
            
            **Example of 20% Risk Without Supplemental Coverage:**
            - $100,000 hospital bill = $20,000 out-of-pocket
            - $500,000 cancer treatment = $100,000 out-of-pocket
            - **This unlimited exposure is why supplemental coverage is essential**
            
            #### ✅ Option 1: Medigap (Medicare Supplement Insurance) - STRONGLY RECOMMENDED
            
            **What it covers:**
            - Fills the gaps in Original Medicare
            - Covers the 20% coinsurance with **no limit**
            - May cover Part A deductible, Part B deductible, foreign travel emergency care
            - **No claim denials** - if Medicare approves it, Medigap pays
            - **No prior authorization** - get care when you need it
            
            **Popular Plans:**
            - **Plan G** (most popular): Covers everything except Part B deductible ($240)
            - **Plan N**: Lower premiums, small copays ($20 office, $50 ER)
            - **High Deductible Plan G**: Lower premiums, $2,800 deductible (2026)
            
            **Key Features:**
            - Guaranteed renewable for life
            - Works with any doctor who accepts Medicare (no networks)
            - Premiums increase with age but coverage remains comprehensive
            - No network restrictions - travel freely
            - **No fighting with insurance when you're sick**
            
            **When to Buy:**
            - **CRITICAL**: Buy during 6-month Medigap Open Enrollment (starts when you turn 65 and enroll in Part B)
            - Guaranteed issue regardless of health conditions during this window
            - After this window, you may face medical underwriting and denial
            - **This is your one chance to get Medigap without health questions**
            
            **Why Medigap is Worth the Extra Cost:**
            - Peace of mind when you're sick
            - No surprise bills
            - No claim denials to fight
            - Freedom to see any doctor
            - Comprehensive protection against catastrophic costs
            
            #### ⚠️ Option 2: Medicare Advantage - Understand the Risks
            
            **What it covers:**
            - Replaces Original Medicare
            - Includes the 20% coverage
            - Has an annual out-of-pocket maximum
            
            **Major Drawbacks:**
            - **Frequent claim denials** that can take months to resolve
            - **Prior authorization required** for many services (delays care)
            - Network restrictions (HMO/PPO) limit doctor choices
            - Networks change annually - you may lose your doctors
            - **Very difficult to switch back to Medigap** later
            - May include extra benefits, but at the cost of freedom and comprehensive coverage
            
            **⚠️ Warning**: While Medicare Advantage has an out-of-pocket maximum, getting to that
            point often involves fighting denials, waiting for authorizations, and dealing with
            network restrictions when you're sick and need care most.
            
            #### ❌ Option 3: No Supplemental Coverage (NEVER RECOMMENDED)
            
            **Risks:**
            - Unlimited exposure to 20% coinsurance
            - Financial catastrophe from serious illness
            - **This is the biggest mistake retirees make**
            - Don't risk your retirement savings on medical bills
            """)
        
        # Switching Rules
        with st.expander("🔄 What You Can and Cannot Switch", expanded=False):
            st.markdown("""
            #### 🚨 CRITICAL: The One-Way Door Problem
            
            **Switching FROM Original Medicare + Medigap TO Medicare Advantage**
            
            **When you can switch:**
            - During Annual Enrollment Period (October 15 - December 7)
            - During Medicare Advantage Open Enrollment (January 1 - March 31)
            - Special Enrollment Periods (if you qualify)
            
            **What happens:**
            - You can easily drop your Medigap policy
            - ⚠️ **CRITICAL WARNING**: If you later want to return to Medigap, you'll face medical underwriting
            - You may be **permanently denied** Medigap coverage due to health conditions
            - **This is almost always a one-way door - you can't go back**
            
            **Why This is Dangerous:**
            - Most people who switch to Advantage do so for the lower premium
            - When they get sick and face denials/restrictions, they want to switch back
            - By then, they have health conditions that make them uninsurable for Medigap
            - They're stuck in Medicare Advantage forever
            - **Don't make this mistake - start with Medigap and stay there**
            
            ---
            
            #### ⚠️ Switching FROM Medicare Advantage TO Original Medicare + Medigap
            
            **When you can switch:**
            - During Annual Enrollment Period (October 15 - December 7)
            - During Medicare Advantage Open Enrollment (January 1 - March 31)
            
            **The Major Challenge:**
            - You'll need to apply for Medigap coverage
            - **Medical underwriting applies** (except in rare guaranteed issue situations)
            - Insurance companies will review your health history
            - **They can deny you or charge much higher premiums based on health**
            - Pre-existing conditions (diabetes, heart disease, cancer, etc.) often result in denial
            - Even minor health issues can make you uninsurable
            - **Most people who try to switch back are denied**
            
            **Guaranteed Issue Rights (No Medical Underwriting) - RARE:**
            - Your Medicare Advantage plan leaves your area or stops providing care
            - You move out of the plan's service area
            - Your plan violated contract or misled you
            - You're in a Medicare SELECT policy and move out of area
            - You have Original Medicare and employer coverage ends
            
            **Reality Check:**
            - These guaranteed issue situations are rare
            - Most people don't qualify
            - Don't count on being able to switch back
            - **Assume Medicare Advantage is permanent once you choose it**
            
            #### Switching Between Medicare Advantage Plans
            
            **When you can switch:**
            - Annual Enrollment Period (October 15 - December 7)
            - Medicare Advantage Open Enrollment (January 1 - March 31, one change allowed)
            
            **What to consider:**
            - Check if your doctors are in the new plan's network
            - Compare out-of-pocket maximums
            - Review prescription drug coverage
            - Verify hospital and specialist access
            
            #### Switching Between Medigap Plans
            
            **When you can switch:**
            - Anytime, but subject to medical underwriting
            - Some states have additional protections (birthday rule, annual open enrollment)
            
            **States with Special Rules:**
            - **California**: Birthday Rule (30 days after birthday to switch to equal/lesser plan)
            - **Oregon**: Birthday Rule (similar to California)
            - **Missouri**: Annual open enrollment for Medigap
            - Check your state's specific rules
            """)
        
        # Common Mistakes
        with st.expander("⚠️ Common Mistakes to Avoid", expanded=False):
            st.markdown("""
            #### Top 12 Medicare Enrollment Mistakes
            
            1. **Missing the Initial Enrollment Period**
               - Results in permanent late enrollment penalties
               - Can cost thousands over your lifetime
               - Set reminders 3 months before turning 65
            
            2. **Not Understanding Employer Coverage Coordination**
               - If you have employer coverage (20+ employees), you can delay Part B
               - If fewer than 20 employees, you MUST enroll in Medicare at 65
               - Get written confirmation from HR about your coverage
            
            3. **🚨 Choosing Medicare Advantage Over Medigap (BIGGEST MISTAKE)**
               - **This is the #1 regret among Medicare beneficiaries**
               - You may never be able to get Medigap later due to health conditions
               - Denials and prior authorization delays when you're sick
               - Network restrictions limit your doctor choices
               - **Start with Medigap - it's worth the extra cost**
            
            4. **Switching from Medigap to Medicare Advantage**
               - You may never be able to get Medigap again
               - Health conditions could make you permanently uninsurable
               - This is almost always irreversible
               - **Don't do it - even for a $0 premium**
            
            5. **Choosing Medicare Advantage Based Only on Premium**
               - $0 premium plans can have high out-of-pocket costs
               - Frequent denials can delay or prevent care
               - Check the out-of-pocket maximum and denial rates
               - Review copays, coinsurance, and prior authorization requirements
            
            6. **Not Checking if Your Doctors Are In-Network (Advantage Plans)**
               - Verify every doctor, specialist, and hospital
               - Networks change annually - you may lose your doctors
               - Out-of-network care can be very expensive or not covered
               - **With Medigap, this isn't a concern**
            
            7. **Ignoring Prescription Drug Coverage**
               - Part D late enrollment penalty is permanent
               - Check if your medications are covered
               - Review formulary tiers and restrictions
            
            8. **🚨 Not Understanding IRMAA Surcharges**
               - **IRMAA is based on your MAGI from 2 years prior**
               - 2026 premiums based on 2024 tax return
               - Can add $69.90 to $419.30/month to Part B premium
               - Plus $12.90 to $81.00/month to Part D premium
               - **Plan Roth conversions carefully to avoid IRMAA brackets**
               - Life-changing events may allow appeals
            
            9. **Not Buying Medigap During Open Enrollment**
               - 6-month window starting when you turn 65 and enroll in Part B
               - Guaranteed issue regardless of health
               - After this window, you may be denied or pay much more
               - **This is your one chance - don't miss it**
            
            10. **Assuming All Medigap Plans Are the Same**
                - Plans are standardized, but prices vary significantly
                - Shop around - same coverage, different prices
                - Consider financial strength of insurance company
            
            11. **Not Reviewing Coverage Annually**
                - Plans change benefits, costs, and networks every year
                - Annual Enrollment Period: October 15 - December 7
                - Review your coverage even if you're happy with it
            
            12. **Relying on Biased Advice**
                - Insurance agents may push Medicare Advantage for higher commissions
                - Use SHIP (State Health Insurance Assistance Program) for unbiased help
                - Get multiple quotes and opinions
                - **Be skeptical of agents pushing $0 premium plans**
            """)
        
        # Action Checklist
        with st.expander("✅ Medicare Enrollment Checklist", expanded=False):
            st.markdown("""
            #### 6 Months Before Turning 65
            - [ ] Determine if you need to enroll or can delay (employer coverage?)
            - [ ] Research Original Medicare vs Medicare Advantage
            - [ ] List your current doctors and medications
            - [ ] Contact SHIP for free counseling
            - [ ] Review your state's specific Medicare rules
            
            #### 3 Months Before Turning 65
            - [ ] Enroll in Part A (if not automatic)
            - [ ] Decide on Part B enrollment timing
            - [ ] If choosing Original Medicare, research Medigap plans
            - [ ] If choosing Medicare Advantage, compare plans in your area
            - [ ] Research Part D prescription drug plans
            - [ ] Verify doctor and hospital networks
            
            #### During Your Birthday Month
            - [ ] Complete all enrollment applications
            - [ ] Confirm coverage start dates
            - [ ] Set up premium payments
            - [ ] Request Medicare card if not received
            
            #### After Enrollment
            - [ ] Receive Medicare card and supplemental insurance cards
            - [ ] Inform doctors of your new coverage
            - [ ] Update pharmacy with Part D information
            - [ ] Keep all enrollment documents
            - [ ] Set calendar reminder for Annual Enrollment Period
            
            #### Annual Review (Every October)
            - [ ] Review Annual Notice of Change from your plans
            - [ ] Check if doctors are still in network
            - [ ] Verify medications are still covered
            - [ ] Compare plans during Annual Enrollment Period
            - [ ] Make changes if needed (effective January 1)
            """)
        
        # Resources
        with st.expander("📚 Additional Resources", expanded=False):
            st.markdown("""
            #### Official Medicare Resources
            
            **Medicare.gov**
            - Official Medicare website
            - Plan comparison tool
            - Coverage information
            - Find doctors and facilities
            
            **1-800-MEDICARE (1-800-633-4227)**
            - 24/7 customer service
            - TTY: 1-877-486-2048
            - Help with enrollment and questions
            
            **State Health Insurance Assistance Program (SHIP)**
            - Free, unbiased Medicare counseling
            - Find your local SHIP: www.shiphelp.org
            - One-on-one help with plan selection
            
            #### Plan Comparison Tools
            
            **Medicare Plan Finder**
            - Compare all plans in your area
            - Enter your medications for accurate cost estimates
            - Check doctor and pharmacy networks
            - Available at www.medicare.gov/plan-compare
            
            **Medigap Plan Comparison**
            - Compare standardized Medigap plans
            - Get quotes from multiple companies
            - Review financial ratings of insurers
            
            #### Educational Resources
            
            **Medicare & You Handbook**
            - Comprehensive annual guide
            - Mailed to all Medicare beneficiaries
            - Available online at Medicare.gov
            
            **State Insurance Department**
            - State-specific Medicare rules
            - Consumer protection
            - Complaint resolution
            
            #### Important Phone Numbers
            
            - **Social Security**: 1-800-772-1213
            - **Medicare**: 1-800-633-4227
            - **Medicare Rights Center**: 1-800-333-4114
            - **SHIP**: Find local number at shiphelp.org
            - **State Insurance Department**: Varies by state
            """)

# Social Security Tab
with tab4:
    st.header("Social Security Planning")
    st.markdown("Configure benefits, optimize claiming strategies, and learn about enrollment.")
    
    # Create 3 sub-tabs within Social Security tab
    ss_tab1, ss_tab2, ss_tab3 = st.tabs([
        "💰 Benefits",
        "🎯 Social Security Optimizer",
        "📋 Social Security Enrollment Guide"
    ])
    
    # Benefits Sub-tab
    with ss_tab1:
        st.subheader("Social Security Benefits")
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
        if not is_single_person:
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
        else:
            # Single person mode - set default values for person2
            st.subheader("Spouse/Partner Social Security")
            st.info("👤 Single person mode - spouse/partner Social Security information hidden")
            person2_ssi_age = 70
            person2_ssi_amount = 0
    
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
        
        st.info("""
        **💡 Tips:**
        - Changes are not saved automatically. Click the "Save All Changes" button in the Advanced tab to persist your changes.
        - Use the Export/Import feature to backup your configuration or share it across devices.
        - The configuration file is stored as `retirement_config.json` in your application directory.
        """)
    
    # Social Security Optimizer Sub-tab
    with ss_tab2:
        st.subheader("Social Security Optimization")
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
    
    # Social Security Enrollment Guide Sub-tab
    with ss_tab3:
        st.subheader("Social Security Enrollment Guide")
        st.markdown("""
        This comprehensive guide helps you navigate Social Security enrollment, understand your options,
        optimize your claiming strategy, and avoid costly mistakes. Social Security decisions are often
        irreversible, so it's crucial to understand your choices before enrolling.
        
        ⚠️ **Critical Connection with Medicare**: Enrolling in Social Security retirement benefits
        automatically enrolls you in Medicare Part A (and Part B unless you opt out). This has important
        implications for HSA contributions and healthcare planning.
        """)
        
        # Overview Section
        with st.expander("📋 Social Security Basics: What You Need to Know", expanded=False):
            st.markdown("""
            #### Understanding Social Security Retirement Benefits
            
            **What is Social Security?**
            - Monthly retirement income based on your lifetime earnings
            - Funded by payroll taxes (FICA) you paid during your working years
            - Provides inflation-adjusted income for life
            - Spousal and survivor benefits available
            
            **Key Ages:**
            - **Age 62**: Earliest you can claim (reduced benefits)
            - **Full Retirement Age (FRA)**: 66-67 depending on birth year
              - Born 1943-1954: FRA is 66
              - Born 1955: FRA is 66 and 2 months
              - Born 1956: FRA is 66 and 4 months
              - Born 1957: FRA is 66 and 6 months
              - Born 1958: FRA is 66 and 8 months
              - Born 1959: FRA is 66 and 10 months
              - Born 1960 or later: FRA is 67
            - **Age 70**: Maximum benefit (8% increase per year after FRA)
            
            **Benefit Calculation:**
            - Based on your highest 35 years of earnings
            - Indexed for inflation
            - If you worked fewer than 35 years, zeros are averaged in
            - Claiming early reduces benefits permanently
            - Delaying past FRA increases benefits permanently
            
            **Reduction for Early Claiming:**
            - Claim at 62 (FRA 67): ~30% reduction (70% of FRA benefit)
            - Claim at 63 (FRA 67): ~25% reduction
            - Claim at 64 (FRA 67): ~20% reduction
            - Claim at 65 (FRA 67): ~13.3% reduction
            - Claim at 66 (FRA 67): ~6.7% reduction
            
            **Increase for Delayed Claiming:**
            - Delay to 68 (FRA 67): +8% (108% of FRA benefit)
            - Delay to 69 (FRA 67): +16% (116% of FRA benefit)
            - Delay to 70 (FRA 67): +24% (124% of FRA benefit)
            - **No benefit to delaying past age 70**
            """)
        
        # Medicare Connection
        with st.expander("🏥 Critical: Social Security and Medicare Connection", expanded=False):
            st.markdown("""
            #### 🚨 Automatic Medicare Enrollment When You Claim Social Security
            
            **The Connection:**
            - When you apply for Social Security retirement benefits, you are **automatically enrolled
              in Medicare Part A and Part B**
            - Part A enrollment is backdated 6 months (or to age 65, whichever is later)
            - You can opt out of Part B, but Part A enrollment is automatic
            
            **Critical HSA Implications:**
            - Once enrolled in Medicare Part A, you **cannot contribute to an HSA**
            - Part A is backdated 6 months, so you may owe penalties for HSA contributions during that period
            - If you're still working and contributing to an HSA, **do not claim Social Security** until
              you're ready to stop HSA contributions
            
            **Strategies to Preserve HSA Contributions:**
            
            **Option 1: Delay Social Security Past 65**
            - Continue working and contributing to HSA
            - Delay Social Security until you're ready to stop HSA contributions
            - Enroll in Medicare separately when you stop working
            - Maximize both HSA contributions and Social Security delayed credits
            
            **Option 2: Claim Social Security, Stop HSA Contributions**
            - Stop HSA contributions 6 months before claiming Social Security
            - Accept automatic Medicare enrollment
            - Use existing HSA funds for Medicare premiums and expenses
            
            **Option 3: Opt Out of Part B (But Not Part A)**
            - You can decline Part B if you have employer coverage
            - Part A is still automatic (and free for most people)
            - HSA contributions still prohibited once Part A starts
            - Must enroll in Part B within 8 months of losing employer coverage to avoid penalties
            
            #### When to Enroll in Medicare vs Social Security
            
            **Scenario 1: Still Working at 65 with Employer Coverage (20+ employees)**
            - Delay Medicare Part B (keep employer coverage)
            - Part A is free, so usually accept it
            - Can delay Social Security to age 70 for maximum benefit
            - **Problem**: Part A enrollment stops HSA contributions
            
            **Scenario 2: Still Working at 65 with HSA**
            - Delay both Social Security and Medicare
            - Continue HSA contributions
            - Enroll in Medicare when you stop working
            - Claim Social Security when optimal (up to age 70)
            
            **Scenario 3: Retired Before 65**
            - Decide Social Security claiming age independently (62-70)
            - Must enroll in Medicare at 65 to avoid penalties
            - If claiming Social Security before 65, Medicare enrollment is separate
            - If claiming Social Security at/after 65, Medicare enrollment is automatic
            
            **Scenario 4: Need Income at 62, Want to Maximize Benefits**
            - Claim Social Security at 62 for income
            - Enroll in Medicare separately at 65
            - Accept reduced Social Security benefit
            - Consider if other income sources could delay claiming
            """)
        
        # When to Enroll
        with st.expander("⏰ When to Enroll: Timing Your Application", expanded=False):
            st.markdown("""
            #### Application Timeline
            
            **When Can You Apply?**
            - You can apply up to **4 months before** you want benefits to start
            - Earliest benefit start: Age 62
            - Latest benefit increase: Age 70
            
            **Recommended Application Timeline:**
            
            **If Claiming at 62:**
            - Apply 3-4 months before your 62nd birthday
            - Benefits can start as early as the month you turn 62
            - Allows time for processing
            
            **If Claiming at Full Retirement Age:**
            - Apply 3 months before your FRA birthday month
            - Ensures benefits start on time
            - Avoids processing delays
            
            **If Claiming at 70:**
            - Apply 3-4 months before turning 70
            - Don't wait past 70 - no additional benefit
            - Ensures you don't miss any payments
            
            #### Processing Timeline
            
            **Application to First Payment:**
            - **Application processing**: 2-4 weeks typically
            - **First payment**: Usually 2-3 months after application
            - **Direct deposit setup**: 1-2 weeks after approval
            - **Retroactive payments**: If applicable, paid in lump sum
            
            **Example Timeline (Claiming at FRA):**
            - 3 months before birthday: Submit application
            - 2-3 weeks later: Application approved
            - Birthday month: Benefits begin
            - 1 month after birthday: First payment received (for birthday month)
            - Ongoing: Payments on 2nd, 3rd, or 4th Wednesday based on birth date
            
            #### Payment Schedule
            
            **When You Get Paid:**
            - Benefits are paid the month after they're earned
            - Payment date based on your birth date:
              - Born 1st-10th: 2nd Wednesday of month
              - Born 11th-20th: 3rd Wednesday of month
              - Born 21st-31st: 4th Wednesday of month
            - If you claimed before May 1997: Payment on 3rd of month
            
            **Direct Deposit:**
            - Required for all new beneficiaries (since 2013)
            - Set up during application process
            - Funds typically available on payment date
            - Can take 1-2 business days to appear in account
            - More secure than paper checks
            """)
        
        # How to Enroll
        with st.expander("📝 How to Enroll: Application Process", expanded=False):
            st.markdown("""
            #### Three Ways to Apply
            
            **1. Online (Recommended) ✅**
            - **Website**: www.ssa.gov/benefits/retirement/apply.html
            - **Advantages**:
              - Apply anytime, 24/7
              - Save and return to application
              - Faster processing
              - Immediate confirmation
              - No appointment needed
            - **Time required**: 15-30 minutes
            - **Best for**: Most applicants, especially straightforward cases
            
            **2. By Phone**
            - **Number**: 1-800-772-1213 (TTY 1-800-325-0778)
            - **Hours**: Monday-Friday, 8:00 AM - 7:00 PM local time
            - **Advantages**:
              - Can ask questions during application
              - Help with complex situations
              - Assistance for those uncomfortable with online
            - **Disadvantages**:
              - Long wait times (especially Monday mornings)
              - Limited hours
            - **Best for**: Complex cases, need assistance
            
            **3. In Person**
            - **Location**: Local Social Security office
            - **Appointment**: Required - call 1-800-772-1213 or schedule online
            - **Advantages**:
              - Face-to-face assistance
              - Can bring documents for review
              - Help with complex situations
            - **Disadvantages**:
              - Must schedule appointment
              - Travel required
              - Limited office hours
            - **Best for**: Very complex cases, prefer in-person help
            
            #### Required Information for Application
            
            **Personal Information:**
            - [ ] Social Security number
            - [ ] Birth certificate or proof of birth
            - [ ] U.S. citizenship or lawful alien status documents
            - [ ] Military service papers (if applicable - DD-214)
            - [ ] W-2 forms or self-employment tax returns for last year
            
            **Banking Information for Direct Deposit:**
            - [ ] Bank name
            - [ ] Routing number (9 digits)
            - [ ] Account number
            - [ ] Account type (checking or savings)
            - [ ] Voided check or bank letter (helpful but not required)
            
            **Spouse Information (if applicable):**
            - [ ] Spouse's Social Security number
            - [ ] Spouse's date of birth
            - [ ] Marriage certificate
            - [ ] Divorce decree (if claiming on ex-spouse's record)
            
            **Children Information (if applicable):**
            - [ ] Children's Social Security numbers
            - [ ] Children's birth certificates
            - [ ] Proof of adoption (if applicable)
            
            **Work History:**
            - [ ] Employer names and addresses for last 2 years
            - [ ] Dates of employment
            - [ ] Self-employment information (if applicable)
            
            #### Documents to Have Ready
            
            **Essential Documents:**
            1. **Birth Certificate** - Original or certified copy
            2. **Social Security Card** - Or know your number
            3. **W-2 Forms** - Most recent year
            4. **Tax Returns** - If self-employed
            5. **Bank Information** - For direct deposit
            
            **Additional Documents (if applicable):**
            6. **Marriage Certificate** - For spousal benefits
            7. **Divorce Decree** - If claiming on ex-spouse
            8. **Death Certificate** - For survivor benefits
            9. **Military Discharge Papers** - DD-214
            10. **Proof of Citizenship** - If not born in U.S.
            
            **Tips for Document Preparation:**
            - Make copies of all documents before submitting
            - SSA will return original documents
            - If you don't have a document, SSA can help you get it
            - Some documents can be uploaded online
            - Keep confirmation numbers from online applications
            """)
        
        # Spousal Benefits
        with st.expander("👫 Spousal and Survivor Benefits", expanded=False):
            st.markdown("""
            #### Spousal Benefits
            
            **Eligibility:**
            - Married for at least 1 year
            - Spouse must have filed for their own benefit
            - You must be at least 62 years old
            - Or caring for child under 16 (or disabled)
            
            **Benefit Amount:**
            - Up to 50% of spouse's FRA benefit
            - Reduced if claimed before your FRA
            - Not increased by delaying past your FRA
            - You receive the higher of: your own benefit or spousal benefit
            
            **Claiming Strategy:**
            - If your own benefit is higher, claim your own
            - If spousal benefit is higher, you'll automatically receive it
            - Can't claim spousal benefit until spouse files
            - Deemed filing rules: If you claim before FRA, you must claim all benefits
            
            **Divorced Spouse Benefits:**
            - Marriage lasted at least 10 years
            - You're unmarried
            - You're at least 62
            - Ex-spouse is entitled to benefits (doesn't have to be claiming)
            - Your benefit doesn't affect ex-spouse's benefit
            - Ex-spouse doesn't need to know you're claiming
            
            #### Survivor Benefits
            
            **Eligibility:**
            - Widow/widower of deceased worker
            - At least 60 years old (50 if disabled)
            - Or caring for child under 16 (or disabled)
            - Marriage lasted at least 9 months (exceptions for accidents)
            
            **Benefit Amount:**
            - Up to 100% of deceased spouse's benefit
            - Amount depends on when deceased spouse claimed
            - Reduced if you claim before your FRA
            - Can switch from survivor to your own benefit later
            
            **Strategic Claiming:**
            - Claim survivor benefit at 60, switch to your own at 70
            - Claim your own benefit early, switch to survivor at FRA
            - Choose strategy that maximizes lifetime benefits
            - Survivor benefits have different FRA than retirement benefits
            
            **Divorced Survivor Benefits:**
            - Marriage lasted at least 10 years
            - You're unmarried (or remarried after age 60)
            - Same benefit as if still married
            - Ex-spouse's remarriage doesn't affect your benefit
            """)
        
        # Working While Receiving Benefits
        with st.expander("💼 Working While Receiving Social Security", expanded=False):
            st.markdown("""
            #### Earnings Test (Before Full Retirement Age)
            
            **If You're Under FRA for the Entire Year:**
            - **2026 Limit**: $22,320 per year
            - **Penalty**: $1 in benefits withheld for every $2 earned above limit
            - **Example**: Earn $32,320 = $10,000 over limit = $5,000 withheld
            
            **In the Year You Reach FRA:**
            - **2026 Limit**: $59,520 per year (only months before FRA count)
            - **Penalty**: $1 withheld for every $3 earned above limit
            - **After FRA month**: No earnings limit
            
            **After Full Retirement Age:**
            - **No earnings limit** - Earn as much as you want
            - No benefit reduction
            - Benefits may increase due to additional earnings
            
            #### What Counts as Earnings?
            
            **Counts Toward Limit:**
            - ✅ Wages from employment
            - ✅ Net self-employment income
            - ✅ Bonuses and commissions
            
            **Does NOT Count:**
            - ❌ Pensions
            - ❌ Annuities
            - ❌ Investment income
            - ❌ Interest and dividends
            - ❌ Capital gains
            - ❌ Rental income (if not real estate business)
            - ❌ IRA/401(k) withdrawals
            
            #### Benefits Are Not Lost Forever
            
            **Important**: Withheld benefits are not lost!
            - At FRA, SSA recalculates your benefit
            - Increases your benefit to account for months withheld
            - Essentially converts early claiming to later claiming
            - You'll eventually receive the money
            
            **Example:**
            - Claim at 62, work and have benefits withheld for 3 years
            - At FRA, benefit is recalculated as if you claimed at 65
            - Higher monthly benefit for rest of life
            """)
        
        # Taxation
        with st.expander("💰 Taxation of Social Security Benefits", expanded=False):
            st.markdown("""
            #### How Social Security is Taxed
            
            **Combined Income Formula:**
            - Adjusted Gross Income (AGI)
            - Plus: Tax-exempt interest
            - Plus: 50% of Social Security benefits
            - = Combined Income
            
            **Taxation Thresholds (2026):**
            
            **Single Filers:**
            - Combined income < $25,000: 0% taxable
            - Combined income $25,000-$34,000: Up to 50% taxable
            - Combined income > $34,000: Up to 85% taxable
            
            **Married Filing Jointly:**
            - Combined income < $32,000: 0% taxable
            - Combined income $32,000-$44,000: Up to 50% taxable
            - Combined income > $44,000: Up to 85% taxable
            
            **Married Filing Separately:**
            - Usually 85% of benefits are taxable
            - Very limited exceptions
            
            #### Tax Planning Strategies
            
            **Minimize Taxable Social Security:**
            1. **Roth conversions before claiming** - Reduce future RMDs
            2. **Qualified Charitable Distributions (QCDs)** - Reduce AGI
            3. **Tax-loss harvesting** - Offset capital gains
            4. **Manage retirement account withdrawals** - Control AGI
            5. **Consider Roth accounts** - Withdrawals don't count as income
            
            **State Taxation:**
            - 38 states don't tax Social Security benefits
            - 12 states do tax benefits (some with exemptions):
              - Colorado, Connecticut, Kansas, Minnesota, Missouri
              - Montana, Nebraska, New Mexico, Rhode Island
              - Utah, Vermont, West Virginia
            - Check your state's specific rules
            
            #### Withholding Options
            
            **Voluntary Withholding:**
            - You can request federal tax withholding
            - Choose 7%, 10%, 12%, or 22%
            - Use Form W-4V
            - Can change anytime
            - Helps avoid underpayment penalties
            
            **Estimated Tax Payments:**
            - If not withholding, may need quarterly estimated payments
            - Use Form 1040-ES
            - Due dates: April 15, June 15, September 15, January 15
            - Avoid underpayment penalties
            """)
        
        # Opting Out and Suspending
        with st.expander("🔄 Can You Opt Out, Suspend, or Change Your Mind?", expanded=False):
            st.markdown("""
            #### Withdrawing Your Application (Within 12 Months)
            
            **The Do-Over Option:**
            - Available only once in your lifetime
            - Must be within 12 months of claiming
            - Must repay all benefits received (including spousal/dependent benefits)
            - No interest charged on repayment
            - Resets your record as if you never claimed
            
            **How to Withdraw:**
            1. Complete Form SSA-521 (Request for Withdrawal)
            2. Submit to Social Security
            3. Repay all benefits within 60 days of approval
            4. Can reapply later for higher benefit
            
            **When This Makes Sense:**
            - Claimed early and regret it
            - Financial situation improved
            - Want to maximize lifetime benefits
            - Can afford to repay benefits
            
            **Example:**
            - Claimed at 62, received $20,000 in benefits
            - Within 12 months, repay $20,000
            - Wait until 70 to claim for 76% higher benefit
            - Lifetime benefit increase can be substantial
            
            #### Suspending Benefits (After Full Retirement Age)
            
            **Voluntary Suspension:**
            - Available only after reaching FRA
            - Can suspend for any reason
            - Benefits grow 8% per year while suspended
            - Can suspend up to age 70
            - No repayment required
            - Can restart anytime
            
            **How to Suspend:**
            1. Call Social Security: 1-800-772-1213
            2. Or visit local office
            3. Request voluntary suspension
            4. Effective the month after request
            
            **When This Makes Sense:**
            - Returned to work after claiming
            - Don't need the income currently
            - Want to increase future benefits
            - Maximize survivor benefit for spouse
            
            **Important Notes:**
            - Spousal benefits also suspended
            - Medicare premiums still deducted (if applicable)
            - Can restart benefits anytime
            - Automatic restart at age 70
            
            #### Changing Your Mind After FRA
            
            **After 12-Month Window:**
            - Can't withdraw application
            - Can suspend benefits (if at FRA)
            - Can't undo claiming decision
            - Stuck with reduced benefit if claimed early
            
            **This is Why Timing Matters:**
            - Early claiming decision is mostly permanent
            - Only one 12-month do-over opportunity
            - Suspension only available after FRA
            - Plan carefully before claiming
            """)
        
        # Common Mistakes
        with st.expander("⚠️ Common Social Security Mistakes to Avoid", expanded=False):
            st.markdown("""
            #### Top 15 Social Security Mistakes
            
            1. **Claiming Too Early Without Considering Longevity**
               - Claiming at 62 reduces benefits by ~30%
               - Break-even age is typically around 78-80
               - If you live past break-even, you lose money
               - Consider family longevity and health
            
            2. **Not Coordinating with Medicare and HSA**
               - Claiming Social Security auto-enrolls you in Medicare
               - Medicare Part A stops HSA contributions
               - Part A is backdated 6 months
               - Can owe penalties for HSA contributions during backdated period
            
            3. **Ignoring Spousal Benefits**
               - Spousal benefit can be up to 50% of spouse's FRA benefit
               - May be higher than your own benefit
               - Divorced spouses (10+ year marriage) also eligible
               - Doesn't reduce spouse's benefit
            
            4. **Not Understanding Survivor Benefits**
               - Survivor gets up to 100% of deceased spouse's benefit
               - Can claim survivor benefit and switch to own later
               - Strategic claiming can maximize lifetime benefits
               - Divorced spouses (10+ year marriage) eligible
            
            5. **Claiming Early While Still Working**
               - Earnings test reduces benefits before FRA
               - $1 withheld for every $2 over limit (under FRA)
               - Benefits are recalculated later, but creates cash flow issues
               - Better to delay claiming if still earning
            
            6. **Not Checking Your Earnings Record**
               - Benefits based on highest 35 years of earnings
               - Errors in earnings record reduce benefits
               - Check annually at www.ssa.gov/myaccount
               - Report errors immediately
            
            7. **Forgetting About Taxes**
               - Up to 85% of benefits may be taxable
               - Depends on combined income
               - Can push you into higher tax bracket
               - Plan for tax withholding or estimated payments
            
            8. **Not Maximizing Delayed Retirement Credits**
               - Benefits increase 8% per year from FRA to 70
               - That's a guaranteed 8% return
               - No benefit to delaying past 70
               - Consider if you can afford to wait
            
            9. **Claiming Before Reviewing All Options**
               - Many claiming strategies available
               - Spousal, survivor, divorced spouse benefits
               - File and suspend (if at FRA)
               - Consult with financial advisor
            
            10. **Not Setting Up Direct Deposit**
                - Required for new beneficiaries
                - More secure than paper checks
                - Faster access to funds
                - Set up during application
            
            11. **Ignoring State Taxation**
                - 12 states tax Social Security benefits
                - May affect where you retire
                - Some states have income exemptions
                - Factor into retirement planning
            
            12. **Not Understanding the Earnings Test**
                - Only applies before FRA
                - Many types of income don't count
                - Withheld benefits aren't lost forever
                - Benefits recalculated at FRA
            
            13. **Claiming Without Considering Inflation**
                - Benefits are adjusted for inflation (COLA)
                - Higher initial benefit = higher COLA increases
                - Compounds over lifetime
                - Delaying increases inflation-adjusted income
            
            14. **Not Coordinating with Overall Retirement Plan**
                - Social Security is one piece of retirement income
                - Coordinate with pensions, 401(k), IRA withdrawals
                - Consider tax implications of all income sources
                - Optimize total retirement income strategy
            
            15. **Relying on Social Security Alone**
                - Average benefit: ~$1,900/month (2026)
                - Replaces only ~40% of pre-retirement income
                - Need additional retirement savings
                - Plan for healthcare costs not covered by Medicare
            """)
        
        # Enrollment Checklist
        with st.expander("✅ Social Security Enrollment Checklist", expanded=False):
            st.markdown("""
            #### 12 Months Before Claiming
            - [ ] Review your earnings record at www.ssa.gov/myaccount
            - [ ] Correct any errors in your earnings history
            - [ ] Estimate your benefit at different claiming ages
            - [ ] Consider longevity, health, and family history
            - [ ] Review spousal and survivor benefit options
            - [ ] Coordinate with Medicare enrollment plans
            - [ ] Check HSA contribution implications
            - [ ] Consult with financial advisor on claiming strategy
            
            #### 6 Months Before Claiming
            - [ ] Decide on claiming age (62-70)
            - [ ] If claiming before 65, plan separate Medicare enrollment
            - [ ] If claiming at/after 65, understand automatic Medicare enrollment
            - [ ] Stop HSA contributions if claiming at/after 65
            - [ ] Gather required documents (birth certificate, W-2s, etc.)
            - [ ] Set up direct deposit information
            - [ ] Review tax withholding options
            - [ ] Plan for taxation of benefits
            
            #### 4 Months Before Claiming
            - [ ] Submit online application at www.ssa.gov
            - [ ] Or schedule phone/in-person appointment
            - [ ] Upload or mail required documents
            - [ ] Confirm direct deposit setup
            - [ ] Request tax withholding if desired (Form W-4V)
            - [ ] Save application confirmation number
            
            #### After Application Submitted
            - [ ] Wait for approval notification (2-4 weeks)
            - [ ] Confirm benefit start date
            - [ ] Confirm payment schedule (based on birth date)
            - [ ] Set up online account at www.ssa.gov/myaccount
            - [ ] Verify direct deposit is working
            - [ ] Keep all correspondence from SSA
            
            #### First Payment Received
            - [ ] Verify payment amount is correct
            - [ ] Confirm direct deposit is working properly
            - [ ] Set up tax withholding if not done already
            - [ ] Plan for quarterly estimated tax payments if needed
            - [ ] Update budget with actual benefit amount
            - [ ] Coordinate with other retirement income sources
            
            #### Annual Review
            - [ ] Review annual COLA adjustment notice
            - [ ] Check for any changes in benefit amount
            - [ ] Verify earnings record is still accurate
            - [ ] Review tax withholding adequacy
            - [ ] Adjust estimated tax payments if needed
            - [ ] Update retirement income plan
            """)
        
        # Resources
        with st.expander("📚 Additional Resources", expanded=False):
            st.markdown("""
            #### Official Social Security Resources
            
            **Social Security Administration Website**
            - www.ssa.gov
            - Create account: www.ssa.gov/myaccount
            - Benefit calculators and estimators
            - Online application portal
            - Check earnings record
            
            **Social Security Phone Numbers**
            - **Main number**: 1-800-772-1213
            - **TTY**: 1-800-325-0778
            - **Hours**: Monday-Friday, 8:00 AM - 7:00 PM local time
            - **Best times to call**: Mid-week, mid-month, mid-morning
            
            **Local Social Security Office**
            - Find office: www.ssa.gov/locator
            - Appointments required
            - Schedule online or by phone
            - Bring all required documents
            
            #### Planning Tools
            
            **Benefit Calculators**
            - **Quick Calculator**: www.ssa.gov/benefits/retirement/planner/AnypiaApplet.html
            - **Retirement Estimator**: www.ssa.gov/benefits/retirement/estimator.html
            - **Detailed Calculator**: www.ssa.gov/benefits/retirement/planner/anyPiaWepjs04.html
            
            **Publications**
            - **Retirement Benefits** (Publication No. 05-10035)
            - **Understanding the Benefits** (Publication No. 05-10024)
            - **Your Retirement Checklist** (Publication No. 05-10377)
            - **When to Start Receiving Benefits** (Publication No. 05-10147)
            - All available at www.ssa.gov/pubs
            
            #### Educational Resources
            
            **AARP Social Security Resource Center**
            - www.aarp.org/retirement/social-security
            - Claiming strategies
            - Benefit calculators
            - Educational articles
            
            **Financial Planning Association**
            - Find a CFP® professional
            - Social Security claiming strategies
            - Retirement income planning
            
            **Medicare.gov**
            - Coordinate Medicare enrollment
            - Understand Part A/B enrollment with Social Security
            - Plan for healthcare costs
            
            #### Important Forms
            
            - **SSA-1 (Application for Retirement Benefits)** - Online or paper
            - **SSA-521 (Request for Withdrawal)** - Within 12 months of claiming
            - **SSA-795 (Statement of Claimant)** - Correct earnings record
            - **W-4V (Voluntary Withholding Request)** - Tax withholding
            - **SSA-44 (Medicare Income-Related Monthly Adjustment Amount)** - IRMAA appeal
            
            #### State-Specific Information
            
            **State Taxation of Benefits**
            - Check your state's Department of Revenue website
            - Some states offer exemptions based on income
            - May affect retirement location decision
            
            **State Disability Programs**
            - Some states have additional disability benefits
            - May coordinate with Social Security Disability
            - Check your state's social services department
            """)


# Tax Strategy Tab
with tab5:
    st.header("Tax Strategy")
    st.markdown("Configure Roth conversion and tax planning parameters.")
    
    st.subheader("Roth Conversions")
    st.info("ℹ️ Roth conversions are now automatically optimized using the BETR (Better Efficient Tax Rate) algorithm based on your maximum tax rate preferences per life stage.")

    # Global default (for backward compatibility)
    max_roth_conversion_tax_rate = st.number_input(
        "Global Maximum Tax Rate for Conversions (%) - Legacy",
        min_value=0,
        max_value=37,
        value=int(config_mgr.get("tax_strategy", "max_roth_conversion_tax_rate", 12)),
        help="Global default maximum marginal tax rate (used if stage-specific rates not configured)",
        key="max_roth_conversion_tax_rate"
    )
    
    st.markdown("---")
    st.markdown("#### 🎯 Stage-Specific Conversion Rate Limits")
    st.caption("Set different maximum tax rates for Roth conversions at each life stage for optimal tax planning")
    
    # Create columns for stage-specific rates
    stage_col1, stage_col2 = st.columns(2)
    
    with stage_col1:
        st.markdown("**Early Career & Accumulation**")
        stage_1_rate = st.number_input(
            "Stage 1: Accumulation (%)",
            min_value=0,
            max_value=37,
            value=int(config_mgr.get("tax_strategy", "stage_1_max_conversion_rate", 32)),
            help="Employed, earning wages, building retirement accounts",
            key="stage_1_conversion_rate"
        )
        
        stage_2_rate = st.number_input(
            "Stage 2: Prep for Retirement (%)",
            min_value=0,
            max_value=37,
            value=int(config_mgr.get("tax_strategy", "stage_2_max_conversion_rate", 24)),
            help="Employed, within 10 years of retirement, optimizing Roth/Traditional balance",
            key="stage_2_conversion_rate"
        )
        
        stage_3_rate = st.number_input(
            "Stage 3: Early Retirement (%)",
            min_value=0,
            max_value=37,
            value=int(config_mgr.get("tax_strategy", "stage_3_max_conversion_rate", 12)),
            help="Pre-Medicare, pre-SS, pre-RMD - prime conversion years with low income",
            key="stage_3_conversion_rate"
        )
    
    with stage_col2:
        st.markdown("**Retirement Stages**")
        stage_4_rate = st.number_input(
            "Stage 4: Medicare Stage (%)",
            min_value=0,
            max_value=37,
            value=int(config_mgr.get("tax_strategy", "stage_4_max_conversion_rate", 12)),
            help="IRMAA optimization with Medicare, pre-SS, pre-RMD",
            key="stage_4_conversion_rate"
        )
        
        stage_5_rate = st.number_input(
            "Stage 5: Social Security Stage (%)",
            min_value=0,
            max_value=37,
            value=int(config_mgr.get("tax_strategy", "stage_5_max_conversion_rate", 22)),
            help="SS benefits + Medicare, pre-RMD - balance conversions with SS income",
            key="stage_5_conversion_rate"
        )
        
        stage_6_rate = st.number_input(
            "Stage 6: RMD Stage (%)",
            min_value=0,
            max_value=37,
            value=int(config_mgr.get("tax_strategy", "stage_6_max_conversion_rate", 10)),
            help="Required Minimum Distributions - limited conversion capacity",
            key="stage_6_conversion_rate"
        )
        
        stage_7_rate = st.number_input(
            "Stage 7: Surviving Spouse (%)",
            min_value=0,
            max_value=37,
            value=int(config_mgr.get("tax_strategy", "stage_7_max_conversion_rate", 15)),
            help="Single filer status with survivor benefits - conservative conversions due to less favorable tax brackets",
            key="stage_7_conversion_rate"
        )
    
    st.markdown("---")
    st.caption("💡 **Strategy Tip**: Lower rates in early retirement (Stages 3-4) maximize conversions when income is low. Higher rates in accumulation (Stage 1) allow conversions while earning. Stage 5-6 rates balance conversions with SS/RMD income. Stage 7 uses conservative rates due to single filer tax brackets.")

    
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
    
    # Get person names for owner dropdown
    owner_options = ['Joint', 'Primary', 'Spouse']
    if person1_name and person1_name.strip():
        owner_options = ['Joint', person1_name]
        if not is_single_person and person2_name and person2_name.strip():
            owner_options.append(person2_name)
    
    # Initialize session state for accounts
    if 'accounts_list' not in st.session_state:
        # Try to load from config or use defaults
        default_owner = owner_options[0] if owner_options else 'Joint'
        st.session_state['accounts_list'] = config_mgr.get("portfolio_accounts", "accounts", [
            {"account_name": "Schwab", "account_type": "Roth", "owner": default_owner},
            {"account_name": "Fidelity", "account_type": "Traditional", "owner": default_owner},
            {"account_name": "Vanguard", "account_type": "Brokerage", "owner": default_owner}
        ])
    
    # Ensure all accounts have owner field (for backward compatibility)
    for account in st.session_state['accounts_list']:
        if 'owner' not in account:
            account['owner'] = owner_options[0] if owner_options else 'Joint'
    
    # Display accounts in a data editor
    accounts_df = pd.DataFrame(st.session_state['accounts_list'])
    if accounts_df.empty:
        accounts_df = pd.DataFrame(columns=pd.Index(['account_name', 'account_type', 'owner']))
    
    col_acc1, col_acc2, col_acc3 = st.columns([2, 1, 1])
    
    with col_acc1:
        st.markdown("**Your Accounts:**")
    
    with col_acc2:
        if st.button("➕ Add Account", width='stretch', key="add_account_btn"):
            default_owner = owner_options[0] if owner_options else 'Joint'
            new_account = pd.DataFrame({
                'account_name': ['New Account'],
                'account_type': ['Brokerage'],
                'owner': [default_owner]
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
        'account_type': st.column_config.SelectboxColumn('Account Type', options=VALID_ACCOUNT_TYPES, required=True, help="Type of account"),
        'owner': st.column_config.SelectboxColumn('Owner', options=owner_options, required=True,
                                                   help=f"Account owner: Joint (both), {person1_name if person1_name else 'Primary'}, or {person2_name if person2_name and not is_single_person else 'Spouse'}")
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
        # Load from portfolio.db (source of truth)
        try:
            _loaded = db_load_all()
            st.session_state['portfolio_df'] = _loaded if not _loaded.empty else pd.DataFrame(columns=pd.Index([
                'month', 'year', 'account_name', 'account_type', 'owner', 'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date'
            ]))
        except Exception as e:
            st.error(f"Error loading portfolio data: {e}")
            st.session_state['portfolio_df'] = pd.DataFrame(columns=pd.Index([
                'month', 'year', 'account_name', 'account_type', 'owner', 'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date'
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
            try:
                _df = db_load_all()
                st.session_state['portfolio_df'] = _df
                st.success(f"Loaded {len(_df)} rows from portfolio.db")
            except Exception as e:
                st.error(f"Error loading data: {e}")

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
                     help="Validates ticker symbols, auto-fills Name/Sector, and maps Account Type/Owner from Your Accounts configuration"):
            current_df = st.session_state['portfolio_df'].copy()
            
            if current_df.empty:
                st.warning("No entries to process. Add rows first.")
            else:
                # Build account lookup from configured accounts
                account_lookup = {}
                for account in st.session_state.get('accounts_list', []):
                    acc_name = account.get('account_name', '')
                    if acc_name:
                        account_lookup[acc_name] = {
                            'account_type': account.get('account_type', 'Brokerage'),
                            'owner': account.get('owner', 'Joint')
                        }
                
                validation_results = []
                accounts_mapped = 0
                tickers_validated = 0
                
                with st.spinner("Validating ticker symbols and mapping accounts..."):
                    for idx, row in current_df.iterrows():
                        symbol = str(row.get('symbol', '')).strip().upper()
                        account_name = str(row.get('account_name', '')).strip()
                        
                        # Validate ticker only if symbol is not empty
                        status_parts = []
                        if symbol:
                            is_valid, name, sector, error = validate_ticker_symbol(symbol)
                            if is_valid:
                                current_df.at[idx, 'name'] = name
                                current_df.at[idx, 'sector'] = sector
                                status_parts.append('✅ Valid')
                                tickers_validated += 1
                            else:
                                status_parts.append('❌ Invalid')
                        
                        # Map account configuration if account_name matches (regardless of symbol)
                        if account_name and account_name in account_lookup:
                            config = account_lookup[account_name]
                            current_df.at[idx, 'account_type'] = config['account_type']
                            current_df.at[idx, 'owner'] = config['owner']
                            accounts_mapped += 1
                            status_parts.append('🔗 Mapped')
                        
                        # Only add to results if there was something to do
                        if symbol or (account_name and account_name in account_lookup):
                            validation_results.append({
                                'Symbol': symbol if symbol else '(no symbol)',
                                'Account': account_name,
                                'Status': ' + '.join(status_parts) if status_parts else 'No action',
                                'Name': current_df.at[idx, 'name'] if symbol else '',
                                'Sector': current_df.at[idx, 'sector'] if symbol else ''
                            })
                
                # Replace the entire dataframe
                st.session_state['portfolio_df'] = current_df
                
                # Show results
                if validation_results:
                    results_df = pd.DataFrame(validation_results)
                    invalid_count = sum(1 for r in validation_results if '❌' in r['Status'])
                
                    if tickers_validated > 0:
                        if invalid_count == 0:
                            st.success(f"✅ All {tickers_validated} ticker symbols validated successfully!")
                        else:
                            st.error(f"❌ {invalid_count} invalid ticker symbol(s). Please correct them before saving.")
                    
                    if accounts_mapped > 0:
                        st.success(f"🔗 Mapped {accounts_mapped} holdings to configured accounts (account_type and owner updated)")
                    
                    st.dataframe(results_df, width='stretch', hide_index=True)
                else:
                    st.info("No tickers to validate or accounts to map")
                
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
                    _reverted = db_load_all()
                    st.session_state['portfolio_df'] = _reverted if not _reverted.empty else create_empty_entry_template(entry_month, entry_year)
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
        'owner': st.column_config.SelectboxColumn('Owner', options=get_valid_account_owners(), required=True,
                                                   help="Account owner from Personal Info configuration"),
        'symbol': st.column_config.TextColumn('Symbol', required=True),
        'name': st.column_config.TextColumn('Name', required=True),
        # TextColumn so any value (including yfinance-enriched MF: categories not in
        # the dropdown list) is always visible and editable without being silently cleared.
        'sector': st.column_config.TextColumn(
            'Sector',
            help=(
                'Asset sector or fund category. Common values: Technology, Healthcare, '
                'Financial Services, Consumer Cyclical, Consumer Defensive, Communication Services, '
                'Industrials, Energy, Real Estate, Utilities, Basic Materials, '
                'MF:Cash, MF:US, MF:Bond, MF:Global, MF:Balanced, MF:Large-Cap, MF:Small-Cap, '
                'MF:Reit, MF:OTHER, Options:Call, Options:Put.'
            ),
            max_chars=60,
        ),
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
        """Save to portfolio.db (with auto CSV backup), then refresh the portfolio display cache."""
        try:
            _bk_ok, _bk_msg = backup_portfolio_data()
            if _bk_ok:
                st.info(f"✅ {_bk_msg}")
            ok, msg = save_portfolio_data(df_to_save, append=False)
            if not ok:
                st.error(f"❌ Save failed: {msg}")
                return
            st.success(f"✅ {msg}")

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
                "is_single_person": st.session_state.get("is_single_person", is_single_person),
                "person1_name": st.session_state.get("person1_name", person1_name),
                "person1_birth_date": st.session_state.get("person1_birth_date", person1_birth_date).strftime("%Y-%m-%d"),
                "person1_retirement_age": st.session_state.get("person1_retirement_age", person1_retirement_age),
                "person2_name": st.session_state.get("person2_name", person2_name),
                "person2_birth_date": st.session_state.get("person2_birth_date", person2_birth_date).strftime("%Y-%m-%d"),
                "person2_retirement_age": st.session_state.get("person2_retirement_age", person2_retirement_age),
                "retirement_state": st.session_state.get("retirement_state", retirement_state),
                "children": _valid_children,
                "surviving_spouse_mode": st.session_state.get("surviving_spouse_mode", False),
                "decedent_person": st.session_state.get("decedent_person", None),
                "date_of_death": st.session_state.get("date_of_death").strftime("%Y-%m-%d") if st.session_state.get("date_of_death") and hasattr(st.session_state.get("date_of_death"), 'strftime') else None,
            })
            
            # Calculate total annual expenses from detailed breakdown
            total_living = (
                property_tax + homeowners_insurance + auto_insurance + food_groceries +
                utilities_phone + utilities_internet + utilities_cable + utilities_electric +
                utilities_gas + utilities_water + gifts_donations + other_living
            )
            total_entertainment = (
                travel_vacations + dining_out + clothing + hobbies + entertainment_other
            )
            calculated_total_expenses = total_living + total_entertainment
            
            # Use calculated total if it's greater than 0, otherwise use the manual input
            final_annual_expenses = calculated_total_expenses if calculated_total_expenses > 0 else expected_annual_expenses
            
            config_mgr.update_section("financial_assumptions", {
                "expected_annual_expenses": final_annual_expenses,
                "expense_inflation_rate": expense_inflation_rate,
                "expected_rate_of_return": expected_rate_of_return,
                "years_of_expenses_in_cash": years_of_expenses_in_cash,
                "brokerage_rebalance_trigger_multiplier": brokerage_rebalance_trigger_multiplier,
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
            
            # Save expenses configuration
            config_mgr.update_section("expenses", {
                "living_expenses": {
                    "property_tax": property_tax,
                    "homeowners_insurance": homeowners_insurance,
                    "auto_insurance": auto_insurance,
                    "food_groceries": food_groceries,
                    "utilities_phone": utilities_phone,
                    "utilities_internet": utilities_internet,
                    "utilities_cable": utilities_cable,
                    "utilities_electric": utilities_electric,
                    "utilities_gas": utilities_gas,
                    "utilities_water": utilities_water,
                    "gifts_donations": gifts_donations,
                    "other_living": other_living,
                },
                "big_ticket_items": valid_items,
                "entertainment_expenses": {
                    "travel_vacations": travel_vacations,
                    "dining_out": dining_out,
                    "clothing": clothing,
                    "hobbies": hobbies,
                    "entertainment_other": entertainment_other,
                    "retirement_decline_enabled": retirement_decline_enabled,
                    "retirement_decline_percent": retirement_decline_percent,
                    "retirement_decline_start_age": retirement_decline_start_age,
                },
            })
            
            config_mgr.update_section("tax_strategy", {
                "max_roth_conversion_tax_rate": max_roth_conversion_tax_rate,
                "stage_1_max_conversion_rate": stage_1_rate,
                "stage_2_max_conversion_rate": stage_2_rate,
                "stage_3_max_conversion_rate": stage_3_rate,
                "stage_4_max_conversion_rate": stage_4_rate,
                "stage_5_max_conversion_rate": stage_5_rate,
                "stage_6_max_conversion_rate": stage_6_rate,
                "stage_7_max_conversion_rate": stage_7_rate,
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

                        # Restore portfolio CSV then re-populate portfolio.db
                        if "portfolio_data_truth.csv" in _name_map:
                            _actual_csv = _name_map["portfolio_data_truth.csv"]
                            _csv_bytes = _zf.read(_actual_csv)
                            with open("portfolio_data_truth.csv", "wb") as _out:
                                _out.write(_csv_bytes)
                            st.success("✅ portfolio_data_truth.csv restored.")
                            try:
                                _n = _migrate_from_csv("portfolio_data_truth.csv")
                                st.success(f"✅ portfolio.db re-populated ({_n} rows).")
                            except Exception as _db_err:
                                st.warning(f"⚠️ CSV restored but portfolio.db update failed: {_db_err}")

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
