import streamlit as st
from streamlit_card import card
import sys
import os
import importlib.util as _importlib_util

# ---------------------------------------------------------------------------
# Import sync_config_to_session_state from the configuration page.
# The pages/ directory uses numeric prefixes for Streamlit ordering
# (e.g. "2_configuration.py"), which are not valid Python identifiers.
# We use importlib to load the module by file path so the digit prefix
# doesn't cause a SyntaxError.
# ---------------------------------------------------------------------------
def _load_sync_fn():
    """Load sync_config_to_session_state from the configuration page module."""
    _pages_dir = os.path.join(os.path.dirname(__file__), '..', 'pages')
    # Try prefixed name first (e.g. 2_configuration.py), then bare name
    for _candidate in ('2_configuration.py', 'configuration.py'):
        _path = os.path.join(_pages_dir, _candidate)
        if os.path.exists(_path):
            try:
                _spec = _importlib_util.spec_from_file_location('_configuration_page', _path)
                if _spec and _spec.loader:
                    _mod = _importlib_util.module_from_spec(_spec)
                    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
                    return getattr(_mod, 'sync_config_to_session_state', None)
            except Exception:
                pass
    return None

_sync_fn = _load_sync_fn()
if _sync_fn is not None:
    sync_config_to_session_state = _sync_fn
else:
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


# ---------------------------------------------------------------------------
# Numeric input configuration
# Format: (label, key, min_val, max_val, step, format_str, help_text, unit_hint)
# ---------------------------------------------------------------------------
SIDEBAR_NUMBER_CONFIGS = [
    (
        "Max Roth Conversion Tax Rate",
        "CONV_TAX_RATE",
        0.0, 50.0, 1.0, "%.0f",
        "Maximum marginal tax rate (%) at which Roth conversions are performed.",
        "%",
    ),
    (
        "Expected Annual Expenses",
        "EXPENSE",
        0.0, 500_000.0, 1_000.0, "%.0f",
        "Projected annual living expenses in today's dollars.",
        "$",
    ),
    (
        "Expense Cash Multiplier",
        "EXPENSE_MULTIPLIER",
        1.0, 10.0, 0.5, "%.1f",
        "Number of years of expenses to keep in cash as a buffer.",
        "× expenses",
    ),
    (
        "Expected Annual Rate of Return",
        "RATE",
        0.0, 20.0, 0.5, "%.1f",
        "Expected average annual portfolio growth rate (%).",
        "%",
    ),
]

# Validation rules: (key, condition_fn, warning_message)
VALIDATION_RULES = [
    ("RATE",             lambda v: v > 15,      "⚠️ Rate of return > 15% is unusually high."),
    ("EXPENSE",          lambda v: v < 1_000,   "⚠️ Annual expenses below $1,000 seems too low."),
    ("CONV_TAX_RATE",    lambda v: v > 40,      "⚠️ Roth conversion rate > 40% — double-check."),
    ("EXPENSE_MULTIPLIER", lambda v: v < 1,     "⚠️ Cash multiplier below 1× may leave insufficient buffer."),
]


def _safe_float(value, default: float = 0.0) -> float:
    """Convert a session-state value (str or numeric) to float safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def save_sidebar_value_to_config(key: str, value: float):
    """
    Save a sidebar numeric value back to the configuration file.

    Args:
        key: The session state key.
        value: The new numeric value to save.
    """
    from config import get_config_manager

    config_mappings = {
        "CONV_TAX_RATE": ("tax_strategy", "max_roth_conversion_tax_rate"),
        "EXPENSE": ("financial_assumptions", "expected_annual_expenses"),
        "EXPENSE_MULTIPLIER": ("financial_assumptions", "years_of_expenses_in_cash"),
        "RATE": ("financial_assumptions", "expected_rate_of_return"),
    }

    if key in config_mappings:
        section, config_key = config_mappings[key]
        config_mgr = get_config_manager()
        try:
            config_mgr.set(section, config_key, float(value))
            config_mgr.save_config()
        except Exception:
            pass  # Ignore save errors silently


def _get_retirement_date_display() -> tuple[str, str]:
    """Return (person1_label, person2_label) retirement year strings from config.

    Falls back to ("Not configured", "") if config is unavailable.
    """
    try:
        from config import get_config_manager
        cfg = get_config_manager()
        p1_name  = cfg.get("personal_info", "person1_name",           "Person 1")
        p1_year  = cfg.get("personal_info", "person1_retirement_year", None)
        p2_name  = cfg.get("personal_info", "person2_name",           "Person 2")
        p2_year  = cfg.get("personal_info", "person2_retirement_year", None)

        p1_label = f"{p1_name}: {int(p1_year)}" if p1_year else f"{p1_name}: —"
        p2_label = f"{p2_name}: {int(p2_year)}" if p2_year else ""
        return p1_label, p2_label
    except Exception:
        pass
    return "Not configured", ""


def sidebar():
    """
    Render the sidebar with retirement planning configuration inputs.

    Inputs are grouped under a collapsible expander and use st.number_input
    for type-safe entry with inline validation warnings.  Values are loaded
    from the configuration file on first run and persisted to session state.
    """
    # Sync config → session state on first load only
    if 'sidebar_config_synced' not in st.session_state:
        sync_config_to_session_state()
        st.session_state['sidebar_config_synced'] = True

    with st.sidebar:
        # ------------------------------------------------------------------ #
        # Header actions                                                       #
        # ------------------------------------------------------------------ #
        st.button("🔄 Refresh All Data", on_click=clear_all_cache, use_container_width=True)

        st.markdown("---")
        st.markdown("⚙️ **[Open Configuration Page](2_configuration)**")
        st.caption("Edit personal info, healthcare, Social Security & tax strategy")
        st.markdown("---")

        # ------------------------------------------------------------------ #
        # Retirement Dates (read-only, from config)                           #
        # ------------------------------------------------------------------ #
        p1_label, p2_label = _get_retirement_date_display()
        lines_html = f"<div>{p1_label}</div>"
        if p2_label:
            lines_html += f"<div>{p2_label}</div>"
        st.markdown(
            f'<div style="background:#1a1a2e;color:white;border-radius:6px;'
            f'padding:8px 12px;margin-bottom:8px;">'
            f'<span style="font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.05em;opacity:.7;">🎯 Target Retirement</span><br>'
            f'<div style="font-size:15px;font-weight:600;margin-top:4px;">'
            f'{lines_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.caption("Adjust strategy parameters in the **⚙️ Settings** tab.")

# Made with Bob
