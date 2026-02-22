import streamlit as st
from streamlit_card import card
from config import get_config_manager


def clear_all_cache():
    """Clear all Streamlit cache data and resources."""
    st.cache_data.clear()
    st.cache_resource.clear()


def set_session_state(key: str, value: str):
    """
    Generic function to set session state values.
    
    Args:
        key: Session state key
        value: Value to set
    """
    st.session_state[key] = value


def get_config_default(session_key: str) -> str:
    """
    Look up default value from config.py for a given session state key.
    
    Args:
        session_key: Session state key to look up
    
    Returns:
        Default value as string from config file
    """
    config_mgr = get_config_manager()
    
    # Map session state keys to config locations
    config_mappings = {
        "SSI_AGE": ("social_security", "person1_ssi_age"),
        "CONV_AMOUNT_AT_SSI_AGE": ("tax_strategy", "roth_conversion_at_ssi_age"),
        "CONV_TAX_RATE": ("tax_strategy", "max_roth_conversion_tax_rate"),
        "EXPENSE": ("financial_assumptions", "expected_annual_expenses"),
        "EXPENSE_MULITPLIER": ("financial_assumptions", "years_of_expenses_in_cash"),
        "RATE": ("financial_assumptions", "expected_rate_of_return"),
        "DAF_RATE": ("tax_strategy", "daf_disbursement_rate"),
        "PLANNED_DIST_2027": ("tax_strategy", "planned_distribution_2027"),
    }
    
    if session_key in config_mappings:
        section, config_key = config_mappings[session_key]
        value = config_mgr.get(section, config_key)
        return str(value) if value is not None else ""
    
    return ""


def load_config_to_session_state():
    """Load configuration values into session state if not already present."""
    config_mgr = get_config_manager()
    
    # Map configuration to session state keys
    config_mappings = {
        "SSI_AGE": ("social_security", "person1_ssi_age"),
        "CONV_AMOUNT_AT_SSI_AGE": ("tax_strategy", "roth_conversion_at_ssi_age"),
        "CONV_TAX_RATE": ("tax_strategy", "max_roth_conversion_tax_rate"),
        "EXPENSE": ("financial_assumptions", "expected_annual_expenses"),
        "EXPENSE_MULITPLIER": ("financial_assumptions", "years_of_expenses_in_cash"),
        "RATE": ("financial_assumptions", "expected_rate_of_return"),
        "DAF_RATE": ("tax_strategy", "daf_disbursement_rate"),
        "PLANNED_DIST_2027": ("tax_strategy", "planned_distribution_2027"),
    }
    
    for session_key, (section, config_key) in config_mappings.items():
        if session_key not in st.session_state:
            value = config_mgr.get(section, config_key)
            st.session_state[session_key] = str(value) if value is not None else ""


def sidebar():
    """
    Render the sidebar with retirement planning configuration inputs.
    All inputs are stored in session state for persistence across reruns.
    Values are loaded from configuration file on first run.
    """
    # Load config values into session state if not present
    load_config_to_session_state()
    
    # Configuration for all sidebar inputs
    # Format: (label, key, placeholder, help_text)
    # Default values are now dynamically loaded from config.py
    sidebar_configs = [
        ("Social Security Age", "SSI_AGE",
         "Add your age you expect to collect Social Security", None),
        ("Roth Conversion at SSI age", "CONV_AMOUNT_AT_SSI_AGE",
         "Add the amount to convert to Roth here at SSI", None),
        ("Max Tax rate for a Roth conversion", "CONV_TAX_RATE",
         "Add the max Tax rate for a Roth conversion", None),
        ("Expected Annual Expenses", "EXPENSE",
         "Add the expected annual expenses", None),
        ("Desired multiple of expenses available", "EXPENSE_MULITPLIER",
         "Add the desired multiplier of expenses", None),
        ("Expected Annual Rate of Return", "RATE",
         "Add the expected annual rate of return investments", None),
        ("Donor Advised Fund Disbursement rate", "DAF_RATE",
         "Add Percentage number to give from Donor advised fund", None),
        ("Planned Distribution for 2027", "PLANNED_DIST_2027",
         "Add the planned distribution amount for year 2027", None),
    ]
    
    with st.sidebar:
        st.sidebar.button("Refresh All Data", on_click=clear_all_cache)
        
        # Add link to configuration page
        st.sidebar.markdown("---")
        st.sidebar.markdown("⚙️ **[Open Configuration Page](configuration)**")
        st.sidebar.caption("Edit detailed settings and personal information")
        st.sidebar.markdown("---")
        
        # Create all text inputs and update session state
        for label, key, placeholder, help_text in sidebar_configs:
            # Get default from config.py dynamically
            default_value = get_config_default(key)
            
            input_value = st.text_input(
                label,
                type="default",
                placeholder=placeholder,
                value=st.session_state.get(key, default_value),
                help=help_text
            )
            
            # Update session state if input has value
            if input_value:
                set_session_state(key, input_value)