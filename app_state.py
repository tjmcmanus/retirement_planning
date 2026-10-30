"""
app_state.py

Streamlit-free access to per-session state, for the data/logic modules.

* Inside the Streamlit app (``streamlit`` already imported by the UI) this is
  ``st.session_state``: per browser session, exactly as before.
* In a headless process (tests, scripts, the future API service) ``streamlit`` is
  never imported and this is a process-wide dict. The app is single-user, so one
  dict is the right scope.

``streamlit`` is looked up in ``sys.modules`` at call time and never imported here.
"""

import logging
import sys
from typing import Any, MutableMapping

logger = logging.getLogger(__name__)

_headless_state: "dict[str, Any]" = {}


def session() -> MutableMapping[str, Any]:
    """Return the current session-state mapping."""
    st = sys.modules.get("streamlit")
    if st is not None:
        return st.session_state
    return _headless_state


def ui_warning(message: str) -> None:
    """Show a warning banner when running inside the Streamlit UI; no-op headless."""
    st = sys.modules.get("streamlit")
    if st is not None:
        st.warning(message)
