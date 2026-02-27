import streamlit as st
from streamlit_card import card
import sys
import os

# Add pages directory to path to import sync function
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pages'))

try:
    from configuration import sync_config_to_session_state
except ImportError:
    # Fallback if import fails - define locally
    from config import get_config_manager
    
    def sync_config_to_session_state():
        """
        Sync configuration values to session state for sidebar compatibility.
        This ensures that changes made in the configuration page are immediately
        available to other parts of the application that read from session state.
        """
        config_mgr = get_config_manager()
        
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


def clear_all_cache():
    """Clear all Streamlit cache data and resources."""
    st.cache_data.clear()
    st.cache_resource.clear()


def clear_withdrawal_strategy_cache():
    """Clear only withdrawal strategy related cache when expense values change."""
    st.cache_data.clear()


# Keys that require cache clearing when changed
CACHE_CLEAR_KEYS = {"EXPENSE", "EXPENSE_MULTIPLIER"}

# Configuration for all sidebar inputs
# Format: (label, key, placeholder, help_text)
# Note: Social Security Age removed - configure via Configuration page
SIDEBAR_CONFIGS = [
    ("Max Tax rate for a Roth conversion", "CONV_TAX_RATE",
     "Add the max Tax rate for a Roth conversion", None),
    ("Expected Annual Expenses", "EXPENSE",
     "Add the expected annual expenses", None),
    ("Desired multiple of expenses available", "EXPENSE_MULTIPLIER",
     "Add the desired multiplier of expenses", None),
    ("Expected Annual Rate of Return", "RATE",
     "Add the expected annual rate of return investments", None),
    ("Donor Advised Fund Disbursement rate", "DAF_RATE",
     "Add Percentage number to give from Donor advised fund", None),
    ("Planned Distribution for 2027", "PLANNED_DIST_2027",
     "Add the planned distribution amount for year 2027", None),
]


def save_sidebar_value_to_config(key: str, value: str):
    """
    Save a sidebar value back to the configuration file.
    
    Args:
        key: The session state key
        value: The new value to save
    """
    from config import get_config_manager
    
    # Map session state keys to config sections and keys
    config_mappings = {
        "CONV_TAX_RATE": ("tax_strategy", "max_roth_conversion_tax_rate"),
        "EXPENSE": ("financial_assumptions", "expected_annual_expenses"),
        "EXPENSE_MULTIPLIER": ("financial_assumptions", "years_of_expenses_in_cash"),
        "RATE": ("financial_assumptions", "expected_rate_of_return"),
        "DAF_RATE": ("tax_strategy", "daf_disbursement_rate"),
        "PLANNED_DIST_2027": ("tax_strategy", "planned_distribution_2027"),
    }
    
    if key in config_mappings:
        section, config_key = config_mappings[key]
        config_mgr = get_config_manager()
        try:
            # Convert string value to appropriate type
            if value:
                numeric_value = float(value)
                config_mgr.set(section, config_key, numeric_value)
                config_mgr.save_config()
        except (ValueError, TypeError):
            pass  # Ignore invalid values


def sidebar():
    """
    Render the sidebar with retirement planning configuration inputs.
    All inputs are stored in session state for persistence across reruns.
    Values are loaded from configuration file on first run.
    """
    # Only sync config values to session state on first load
    # Use a flag to track if we've already synced
    if 'sidebar_config_synced' not in st.session_state:
        sync_config_to_session_state()
        st.session_state['sidebar_config_synced'] = True
    
    with st.sidebar:
        st.button("Refresh All Data", on_click=clear_all_cache)
        
        # Add link to configuration page
        st.markdown("---")
        st.markdown("⚙️ **[Open Configuration Page](configuration)**")
        st.caption("Edit detailed settings and personal information")
        st.markdown("---")
        
        # Create all text inputs with automatic session state management
        for label, key, placeholder, help_text in SIDEBAR_CONFIGS:
            # Create a combined callback that clears cache and saves to config
            def create_on_change_callback(k):
                def callback():
                    # Clear cache if needed
                    if k in CACHE_CLEAR_KEYS:
                        clear_withdrawal_strategy_cache()
                    # Save value to config file
                    save_sidebar_value_to_config(k, st.session_state.get(k, ""))
                return callback
            
            st.text_input(
                label,
                key=key,  # Streamlit auto-manages session state
                value=st.session_state.get(key, ""),
                placeholder=placeholder,
                help=help_text,
                on_change=create_on_change_callback(key)
            )