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
from config import get_config_manager, reload_config
from portfolio_data_entry import validate_portfolio_dataframe, VALID_ACCOUNT_TYPES, VALID_SECTORS
from ssi_calculator import generate_ssi_schedule_from_config, export_ssi_schedule_to_csv

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")

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
        "DAF_RATE": ("tax_strategy", "daf_disbursement_rate"),
        "PLANNED_DIST_2027": ("tax_strategy", "planned_distribution_2027"),
    }
    
    for session_key, (section, config_key) in config_to_session_mappings.items():
        value = config_mgr.get(section, config_key)
        if value is not None:
            st.session_state[session_key] = str(value)

st.title("⚙️ Retirement Planning Configuration")
st.markdown("Configure your personal information, financial assumptions, and planning parameters.")

# Create tabs for different configuration sections
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "👤 Personal Info",
    "💰 Financial Assumptions",
    "🏥 Healthcare",
    "📊 Social Security",
    "📈 Tax Strategy",
    "📊 Portfolio Data",
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
            help="How many years of expenses to keep in cash/safe assets",
            key="years_of_expenses_in_cash"
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
            value=config_mgr.get("social_security", "person1_ssi_age", 70),
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
            value=config_mgr.get("social_security", "person2_ssi_age", 70),
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
    
    col1, col2 = st.columns(2)
    
    with col1:
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
    
    with col2:
        st.subheader("Other Tax Planning")
        daf_disbursement_rate = st.number_input(
            "Donor Advised Fund Disbursement Rate (%)",
            min_value=0,
            max_value=100,
            value=config_mgr.get("tax_strategy", "daf_disbursement_rate", 25),
            help="Percentage of DAF to disburse annually",
            key="daf_disbursement_rate"
        )
        
        planned_distribution_2027 = st.number_input(
            "Planned Distribution for 2027 ($)",
            min_value=0,
            max_value=500000,
            value=config_mgr.get("tax_strategy", "planned_distribution_2027", 75000),
            step=5000,
            help="Specific planned distribution amount for 2027",
            key="planned_distribution_2027"
        )
    
    # Charitable Giving Section
    st.markdown("---")
    st.subheader("🎁 Charitable Giving")
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
        daf_initial_contribution = st.number_input(
            "Initial DAF Contribution ($)",
            min_value=0,
            max_value=10000000,
            value=config_mgr.get("charitable_giving", "daf_initial_contribution", 0),
            step=5000,
            help="One-time initial contribution to establish your DAF",
            key="daf_initial_contribution"
        )
        
        daf_annual_contribution = st.number_input(
            "Annual DAF Contribution ($)",
            min_value=0,
            max_value=1000000,
            value=config_mgr.get("charitable_giving", "daf_annual_contribution", 0),
            step=1000,
            help="Annual contribution to your DAF (in addition to initial contribution)",
            key="daf_annual_contribution"
        )
        
        daf_contribution_start_age = st.number_input(
            "DAF Contribution Start Age",
            min_value=50,
            max_value=100,
            value=config_mgr.get("charitable_giving", "daf_contribution_start_age", 60),
            help="Age when you plan to start making annual DAF contributions",
            key="daf_contribution_start_age"
        )
        
        daf_contribution_end_age = st.number_input(
            "DAF Contribution End Age",
            min_value=50,
            max_value=100,
            value=config_mgr.get("charitable_giving", "daf_contribution_end_age", 75),
            help="Age when you plan to stop making annual DAF contributions",
            key="daf_contribution_end_age"
        )
    
    # Display calculated charitable giving metrics
    if annual_charitable_giving > 0 or daf_initial_contribution > 0 or daf_annual_contribution > 0:
        st.markdown("---")
        st.subheader("Charitable Giving Summary")
        
        col_char1, col_char2, col_char3 = st.columns(3)
        
        with col_char1:
            st.metric("Annual Charitable Goal", f"${annual_charitable_giving:,.0f}")
        
        with col_char2:
            total_daf_contributions = daf_initial_contribution + (daf_annual_contribution * max(0, daf_contribution_end_age - daf_contribution_start_age))
            st.metric("Total DAF Contributions", f"${total_daf_contributions:,.0f}",
                     help=f"Initial contribution plus annual contributions from age {daf_contribution_start_age} to {daf_contribution_end_age}")
        
        with col_char3:
            # Calculate lifetime charitable giving (30 years from start age)
            years_of_giving = 30
            lifetime_giving = annual_charitable_giving * years_of_giving
            st.metric("Projected Lifetime Giving", f"${lifetime_giving:,.0f}",
                     help=f"Based on {years_of_giving} years of giving (not including inflation)")
        
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
        accounts_df = pd.DataFrame(columns=['account_name', 'account_type'])
    
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
                st.session_state['portfolio_df'] = pd.DataFrame(columns=[
                    'month', 'year', 'account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
                ])
        else:
            st.session_state['portfolio_df'] = pd.DataFrame(columns=[
                'month', 'year', 'account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
            ])
    
    # File management buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📂 Load Current Data", width='stretch'):
            if os.path.exists('portfolio_data_truth.csv'):
                try:
                    st.session_state['portfolio_df'] = pd.read_csv('portfolio_data_truth.csv')
                    st.success(f"Loaded {len(st.session_state['portfolio_df'])} rows from portfolio_data_truth.csv")
                except Exception as e:
                    st.error(f"Error loading data: {e}")
            else:
                st.warning("portfolio_data_truth.csv not found")
    
    with col2:
        if st.button("➕ Add Empty Row", width='stretch'):
            new_row = pd.DataFrame({
                'month': [datetime.now().month],
                'year': [datetime.now().year],
                'account_name': [''],
                'account_type': ['Brokerage'],
                'symbol': [''],
                'name': [''],
                'sector': [''],
                'qty': [0.0],
                'purchase_price': [0.0]
            })
            st.session_state['portfolio_df'] = pd.concat([st.session_state['portfolio_df'], new_row], ignore_index=True)
            st.rerun()
    
    with col3:
        if st.button("🗑️ Clear All", width='stretch'):
            st.session_state['portfolio_df'] = pd.DataFrame(columns=[
                'month', 'year', 'account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price'
            ])
            st.rerun()
    
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
    
    # Display editable dataframe
    edited_df = st.data_editor(
        st.session_state['portfolio_df'],
        column_config=column_config,
        num_rows="dynamic",
        width='stretch',
        hide_index=True,
        key="portfolio_editor"
    )
    
    # Update session state with edited data
    st.session_state['portfolio_df'] = edited_df
    
    st.markdown("---")
    
    # Save section
    st.subheader("Save Portfolio Data")
    
    col_save1, col_save2 = st.columns(2)
    
    with col_save1:
        st.info(f"**Current rows:** {len(edited_df)}")
        
        # Validate data before saving
        if len(edited_df) > 0:
            valid_df, invalid_df = validate_portfolio_dataframe(edited_df)
            
            if len(invalid_df) > 0:
                st.warning(f"⚠️ {len(invalid_df)} rows have validation errors")
                with st.expander("View Validation Errors"):
                    st.dataframe(invalid_df[['month', 'year', 'symbol', 'validation_error']], width='stretch')
            
            if len(valid_df) > 0:
                st.success(f"✅ {len(valid_df)} rows are valid and ready to save")
    
    with col_save2:
        if st.button("💾 Save Portfolio Data", type="primary", width='stretch', disabled=len(edited_df) == 0):
            # Validate the data
            valid_df, invalid_df = validate_portfolio_dataframe(edited_df)
            
            if len(invalid_df) > 0:
                st.error(f"Cannot save: {len(invalid_df)} rows have validation errors. Please fix them first.")
            elif len(valid_df) == 0:
                st.error("No valid data to save")
            else:
                try:
                    # Create timestamped backup of existing file
                    if os.path.exists('portfolio_data_truth.csv'):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_name = f'portfolio_data_truth_{timestamp}.csv'
                        shutil.copy2('portfolio_data_truth.csv', backup_name)
                        st.info(f"✅ Backed up existing data to {backup_name}")
                    
                    # Save the new data
                    valid_df.to_csv('portfolio_data_truth.csv', index=False)
                    st.success(f"✅ Successfully saved {len(valid_df)} rows to portfolio_data_truth.csv")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"Error saving portfolio data: {e}")
    
    # Display sample data format
    with st.expander("📋 View Sample Data Format"):
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
with tab7:
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
            })
            
            config_mgr.update_section("financial_assumptions", {
                "expected_annual_expenses": expected_annual_expenses,
                "expense_inflation_rate": expense_inflation_rate,
                "expected_rate_of_return": expected_rate_of_return,
                "years_of_expenses_in_cash": years_of_expenses_in_cash,
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
            })
            
            config_mgr.update_section("tax_strategy", {
                "max_roth_conversion_tax_rate": max_roth_conversion_tax_rate,
                "daf_disbursement_rate": daf_disbursement_rate,
                "planned_distribution_2027": planned_distribution_2027,
            })
            
            config_mgr.update_section("charitable_giving", {
                "annual_charitable_giving": annual_charitable_giving,
                "charitable_giving_start_age": charitable_giving_start_age,
                "charitable_giving_inflation_rate": charitable_giving_inflation_rate,
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
        
        # Export configuration
        if st.button("📤 Export Configuration", width='stretch'):
            config_json = config_mgr.export_config()
            st.download_button(
                label="Download Configuration JSON",
                data=config_json,
                file_name=f"retirement_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                width='stretch'
            )
        
        # Import configuration
        st.markdown("**Import Configuration**")
        uploaded_file = st.file_uploader("Choose a configuration file", type=['json'])
        if uploaded_file is not None:
            try:
                config_json = uploaded_file.read().decode('utf-8')
                if config_mgr.import_config(config_json):
                    if config_mgr.save_config():
                        st.success("Configuration imported successfully! Please refresh the page.")
                        st.rerun()
                    else:
                        st.error("Error saving imported configuration.")
                else:
                    st.error("Error importing configuration. Please check the file format.")
            except Exception as e:
                st.error(f"Error reading file: {e}")
    
    # Display current configuration
    st.subheader("Current Configuration")
    with st.expander("View Raw Configuration"):
        st.json(config_mgr.config)
    
    # Display metadata
    metadata = config_mgr.get_section("metadata")
    if metadata.get("last_updated"):
        st.caption(f"Last updated: {metadata['last_updated']}")
    st.caption(f"Version: {metadata.get('version', 'Unknown')}")

# Add helpful information at the bottom
st.markdown("---")
st.info("""
**💡 Tips:**
- Changes are not saved automatically. Click the "Save All Changes" button in the Advanced tab to persist your changes.
- Use the Export/Import feature to backup your configuration or share it across devices.
- The configuration file is stored as `retirement_config.json` in your application directory.
""")

# Made with Bob
