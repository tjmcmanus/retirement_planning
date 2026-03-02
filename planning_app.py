"""
planning_app.py

Main entry point for the Retirement Planning Application.

This file now serves as a redirect to the new multi-page architecture.
All functionality has been moved to dedicated pages under pages/:
  - pages/3_dashboard.py - Main dashboard and overview
  - pages/4_portfolio.py - Portfolio management
  - pages/5_strategy.py - Strategy planning
  - pages/6_monte_carlo.py - Monte Carlo simulations
  - pages/8_advanced_strategies.py - Advanced tax strategies

The application uses a hybrid architecture with streamlit-option-menu
for horizontal navigation between pages.
"""

import streamlit as st

# Set page config (must be first Streamlit command)
st.set_page_config(
    page_title="Retirement Planning",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Redirect to Dashboard page
st.switch_page("pages/3_dashboard.py")

# Made with Bob
