"""
components/navbar.py
====================
Faux-tab navigation bar for the Financial Planner application.

Uses streamlit-option-menu to render a horizontal nav bar that looks and
feels like tabs but routes between Streamlit multi-page app pages.

Usage (call at the top of every page, after st.set_page_config):
    from components.navbar import navbar
    navbar("📊 Dashboard")
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Navigation route map: display label → page file path (relative to root)
# ---------------------------------------------------------------------------
NAV_ROUTES: dict[str, str] = {
    "🏠 Dashboard":                "pages/3_dashboard.py",
    "📊 Portfolio":                "pages/4_portfolio.py",
    "📋 Strategy":                 "pages/5_strategy.py",
    "🧠 Advanced Strategy Tools":  "pages/8_advanced_strategies.py",
    "🎲 Monte Carlo":              "pages/6_monte_carlo.py",
    "🏛️ Estate Planning":          "pages/1_estate_planning.py",
    "⚙️ Settings":                 "pages/2_configuration.py",
    "🔧 Tax Data Admin":           "pages/9_admin_tax_data.py",
}

NAV_LABELS = list(NAV_ROUTES.keys())

# Primary brand colour (matches .streamlit/config.toml primaryColor)
_PRIMARY = "#F63366"
_PRIMARY_TEXT = "white"


def navbar(current_page: str = "Dashboard") -> None:
    """
    Render the horizontal faux-tab navigation bar.

    Parameters
    ----------
    current_page : str
        The label of the currently active page (must match a key in NAV_ROUTES).
        The matching tab will be highlighted as active.

    Notes
    -----
    * Uses streamlit-option-menu when available; falls back to st.page_link()
      columns if the package is not installed.
    * Navigates via st.switch_page() so the full Streamlit page lifecycle runs
      (session state is preserved across pages via st.session_state).
    """
    default_index = NAV_LABELS.index(current_page) if current_page in NAV_LABELS else 0

    try:
        from streamlit_option_menu import option_menu  # type: ignore[import]

        selected = option_menu(
            menu_title=None,
            options=NAV_LABELS,
            icons=[],  # Empty list - emoji are in the labels
            default_index=default_index,
            orientation="horizontal",
            styles={
                "container": {
                    "padding": "0!important",
                    "background-color": "#fafafa",
                    "border-bottom": "2px solid #e0e0e0",
                    "margin-bottom": "12px",
                    "width": "100%",
                    "max-width": "100%",
                },
                "icon": {"color": _PRIMARY, "font-size": "14px"},
                "nav-link": {
                    "font-size": "13px",
                    "text-align": "center",
                    "margin": "0px",
                    "padding": "8px 10px",
                    "--hover-color": "#f0f0f0",
                    "flex": "1",
                },
                "nav-link-selected": {
                    "background-color": _PRIMARY,
                    "color": _PRIMARY_TEXT,
                    "font-weight": "600",
                },
            },
            key=f"main_navbar_{current_page}",
        )

        if selected != current_page:
            target = NAV_ROUTES.get(selected)
            if target:
                st.switch_page(target)

    except ImportError:
        # Fallback: plain st.page_link() columns (no active-tab highlighting)
        _navbar_fallback(current_page)


def _navbar_fallback(current_page: str) -> None:
    """
    Fallback navigation using st.page_link() when streamlit-option-menu is
    not installed.  Active page is shown in bold; others are plain links.
    """
    cols = st.columns(len(NAV_LABELS))
    for col, label in zip(cols, NAV_LABELS):
        route = NAV_ROUTES[label]
        with col:
            if label == current_page:
                # Active page — show as bold text (not a link)
                st.markdown(
                    f'<div style="text-align:center;font-weight:700;'
                    f'color:{_PRIMARY};border-bottom:3px solid {_PRIMARY};'
                    f'padding:6px 0;font-size:13px;">{label}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.page_link(route, label=label)
    st.markdown("---")

# Made with Bob
