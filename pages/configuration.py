"""
Configuration page for retirement planning application.
Allows users to view and edit application constants and preferences.
"""

import streamlit as st
from datetime import datetime
import json
from config import get_config_manager, reload_config

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")

# Initialize configuration manager
config_mgr = get_config_manager()

st.title("⚙️ Retirement Planning Configuration")
st.markdown("Configure your personal information, financial assumptions, and planning parameters.")

# Create tabs for different configuration sections
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "👤 Personal Info",
    "💰 Financial Assumptions",
    "🏥 Healthcare",
    "📊 Social Security",
    "📈 Tax Strategy",
    "🔧 Advanced"
])

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
            value=config_mgr.get("personal_info", "person1_retirement_age", 62),
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
    
    # Display calculated values
    st.subheader("Calculated Values")
    cash_reserve = expected_annual_expenses * years_of_expenses_in_cash
    st.metric("Recommended Cash Reserve", f"${cash_reserve:,.0f}")

# Healthcare Tab
with tab3:
    st.header("Healthcare Costs")
    st.markdown("Configure healthcare insurance and Medicare assumptions.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("ACA Insurance (Pre-Medicare)")
        aca_insurance_monthly = st.number_input(
            "Monthly ACA Insurance Premium ($)",
            min_value=0,
            max_value=5000,
            value=config_mgr.get("healthcare", "aca_insurance_monthly", 0),
            step=50,
            help="Monthly premium for ACA marketplace insurance",
            key="aca_insurance_monthly"
        )
        
        aca_start_age = st.number_input(
            "ACA Coverage Start Age",
            min_value=50,
            max_value=65,
            value=config_mgr.get("healthcare", "aca_start_age", 62),
            help="Age when ACA coverage begins (typically at retirement)",
            key="aca_start_age"
        )
        
        aca_end_age = st.number_input(
            "ACA Coverage End Age",
            min_value=60,
            max_value=70,
            value=config_mgr.get("healthcare", "aca_end_age", 65),
            help="Age when ACA coverage ends (typically when Medicare starts)",
            key="aca_end_age"
        )
    
    with col2:
        st.subheader("Medicare")
        medicare_start_age = st.number_input(
            "Medicare Start Age",
            min_value=60,
            max_value=70,
            value=config_mgr.get("healthcare", "medicare_start_age", 65),
            help="Age when Medicare coverage begins",
            key="medicare_start_age"
        )
        
        # Display calculated annual ACA cost
        if aca_insurance_monthly > 0:
            annual_aca_cost = aca_insurance_monthly * 12
            years_on_aca = max(0, aca_end_age - aca_start_age)
            total_aca_cost = annual_aca_cost * years_on_aca
            
            st.metric("Annual ACA Cost", f"${annual_aca_cost:,.0f}")
            st.metric("Total ACA Cost", f"${total_aca_cost:,.0f}", 
                     help=f"Total cost for {years_on_aca} years on ACA")

# Social Security Tab
with tab4:
    st.header("Social Security Benefits")
    st.markdown("Configure when you plan to start collecting Social Security.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"{person1_name}'s Social Security")
        person1_ssi_age = st.number_input(
            "Age to Start Benefits",
            min_value=62,
            max_value=70,
            value=config_mgr.get("social_security", "person1_ssi_age", 70),
            help="Age when you plan to start collecting Social Security",
            key="person1_ssi_age"
        )
        
        person1_ssi_amount = st.number_input(
            "Estimated Annual Benefit ($)",
            min_value=0,
            max_value=100000,
            value=config_mgr.get("social_security", "person1_ssi_amount", 0),
            step=1000,
            help="Estimated annual Social Security benefit",
            key="person1_ssi_amount"
        )
        
        if person1_ssi_amount > 0:
            monthly_benefit_1 = person1_ssi_amount / 12
            st.info(f"Monthly Benefit: ${monthly_benefit_1:,.0f}")
    
    with col2:
        st.subheader(f"{person2_name}'s Social Security")
        person2_ssi_age = st.number_input(
            "Age to Start Benefits",
            min_value=62,
            max_value=70,
            value=config_mgr.get("social_security", "person2_ssi_age", 70),
            help="Age when you plan to start collecting Social Security",
            key="person2_ssi_age"
        )
        
        person2_ssi_amount = st.number_input(
            "Estimated Annual Benefit ($)",
            min_value=0,
            max_value=100000,
            value=config_mgr.get("social_security", "person2_ssi_amount", 0),
            step=1000,
            help="Estimated annual Social Security benefit",
            key="person2_ssi_amount"
        )
        
        if person2_ssi_amount > 0:
            monthly_benefit_2 = person2_ssi_amount / 12
            st.info(f"Monthly Benefit: ${monthly_benefit_2:,.0f}")
    
    # Display combined benefits
    if person1_ssi_amount > 0 or person2_ssi_amount > 0:
        st.subheader("Combined Benefits")
        total_annual = person1_ssi_amount + person2_ssi_amount
        total_monthly = total_annual / 12
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Total Annual Benefits", f"${total_annual:,.0f}")
        with col_b:
            st.metric("Total Monthly Benefits", f"${total_monthly:,.0f}")

# Tax Strategy Tab
with tab5:
    st.header("Tax Strategy")
    st.markdown("Configure Roth conversion and tax planning parameters.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Roth Conversions")
        roth_conversion_at_ssi_age = st.number_input(
            "Annual Roth Conversion at SSI Age ($)",
            min_value=0,
            max_value=100000,
            value=config_mgr.get("tax_strategy", "roth_conversion_at_ssi_age", 5000),
            step=1000,
            help="Amount to convert to Roth annually when Social Security starts",
            key="roth_conversion_at_ssi_age"
        )
        
        max_roth_conversion_tax_rate = st.number_input(
            "Maximum Tax Rate for Conversions (%)",
            min_value=0,
            max_value=37,
            value=config_mgr.get("tax_strategy", "max_roth_conversion_tax_rate", 12),
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

# Advanced Tab
with tab6:
    st.header("Advanced Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Configuration Management")
        
        if st.button("💾 Save All Changes", type="primary", use_container_width=True):
            # Update all configuration values
            config_mgr.update_section("personal_info", {
                "person1_name": person1_name,
                "person1_birth_date": person1_birth_date.strftime("%Y-%m-%d"),
                "person1_retirement_age": person1_retirement_age,
                "person2_name": person2_name,
                "person2_birth_date": person2_birth_date.strftime("%Y-%m-%d"),
                "person2_retirement_age": person2_retirement_age,
            })
            
            config_mgr.update_section("financial_assumptions", {
                "expected_annual_expenses": expected_annual_expenses,
                "expense_inflation_rate": expense_inflation_rate,
                "expected_rate_of_return": expected_rate_of_return,
                "years_of_expenses_in_cash": years_of_expenses_in_cash,
            })
            
            config_mgr.update_section("healthcare", {
                "aca_insurance_monthly": aca_insurance_monthly,
                "aca_start_age": aca_start_age,
                "aca_end_age": aca_end_age,
                "medicare_start_age": medicare_start_age,
            })
            
            config_mgr.update_section("social_security", {
                "person1_ssi_age": person1_ssi_age,
                "person1_ssi_amount": person1_ssi_amount,
                "person2_ssi_age": person2_ssi_age,
                "person2_ssi_amount": person2_ssi_amount,
            })
            
            config_mgr.update_section("tax_strategy", {
                "roth_conversion_at_ssi_age": roth_conversion_at_ssi_age,
                "max_roth_conversion_tax_rate": max_roth_conversion_tax_rate,
                "daf_disbursement_rate": daf_disbursement_rate,
                "planned_distribution_2027": planned_distribution_2027,
            })
            
            if config_mgr.save_config():
                st.success("✅ Configuration saved successfully!")
                st.balloons()
            else:
                st.error("❌ Error saving configuration. Please try again.")
        
        if st.button("🔄 Reset to Defaults", use_container_width=True):
            config_mgr.reset_to_defaults()
            if config_mgr.save_config():
                st.success("Configuration reset to defaults. Please refresh the page.")
                st.rerun()
            else:
                st.error("Error resetting configuration.")
        
        if st.button("♻️ Reload from File", use_container_width=True):
            reload_config()
            st.success("Configuration reloaded from file. Please refresh the page.")
            st.rerun()
    
    with col2:
        st.subheader("Export/Import")
        
        # Export configuration
        if st.button("📤 Export Configuration", use_container_width=True):
            config_json = config_mgr.export_config()
            st.download_button(
                label="Download Configuration JSON",
                data=config_json,
                file_name=f"retirement_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
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
