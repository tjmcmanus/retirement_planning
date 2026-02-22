import streamlit as st
from streamlit_card import card


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

def sidebar():
    """
    Render the sidebar with retirement planning configuration inputs.
    All inputs are stored in session state for persistence across reruns.
    """
    # Configuration for all sidebar inputs
    # Format: (label, key, default_value, placeholder, help_text)
    sidebar_configs = [
        ("Social Security Age", "SSI_AGE", "70",
         "Add your age you expect to collect Social Security", None),
        ("Roth Conversion at SSI age", "CONV_AMOUNT_AT_SSI_AGE", "5000",
         "Add the amount to convert to Roth here at SSI", "Consult docs to locate your project id"),
        ("Max Tax rate for a Roth conversion", "CONV_TAX_RATE", "12",
         "Add the max Tax rate for a Roth conversion", None),
        ("Expected Annual Expenses", "EXPENSE", "50000",
         "Add the expected annual expenses", None),
        ("Desired multiple of expenses available", "EXPENSE_MULITPLIER", "4",
         "Add the desired multiplier of expenses", None),
        ("Expected Annual Rate of Return", "RATE", "6",
         "Add the expected annual rate of return investments", None),
        ("Donor Advised Fund Disbursement rate", "DAF_RATE", "25",
         "Add Percentage number to give from Donor advised fund", None),
        ("Planned Distribution for 2027", "PLANNED_DIST_2027", "75000",
         "Add the planned distribution amount for year 2027", None),
    ]
    
    with st.sidebar:
        st.sidebar.button("Refresh All Data", on_click=clear_all_cache)
        
        # Create all text inputs and update session state
        for label, key, default, placeholder, help_text in sidebar_configs:
            input_value = st.text_input(
                label,
                type="default",
                placeholder=placeholder,
                value=st.session_state.get(key, default),
                help=help_text
            )
            
            # Update session state if input has value
            if input_value:
                set_session_state(key, input_value)