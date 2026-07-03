"""
components/portfolio_setup_config_tab.py
=========================================
Setup & Config tab for Portfolio Hub.

Two sub-tabs:
  ⚙️ Setup Wizard   — initial direct-index portfolio generation wizard
  🔧 Harvest Config — edit thresholds, replacement strategy, wash-sale rules (YAML)
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------
try:
    from components.initial_setup_wizard import render_setup_wizard
    SETUP_WIZARD_AVAILABLE = True
except ImportError:
    SETUP_WIZARD_AVAILABLE = False
    render_setup_wizard = None  # type: ignore


# ==============================================================================
# PUBLIC ENTRY POINT
# ==============================================================================

def render_setup_config_tab() -> None:
    """
    Render the Setup & Config tab (top-level Portfolio Hub tab).

    Combines the Direct Indexing Setup Wizard and the YAML Configuration editor.
    """
    st.markdown("### ⚙️ Setup & Config")
    st.caption(
        "First-time setup wizard for your direct-index portfolio, "
        "and configuration for harvest thresholds and replacement strategy."
    )

    setup_sub, config_sub = st.tabs(["⚙️ Setup Wizard", "🔧 Harvest Config"])

    with setup_sub:
        _render_setup()

    with config_sub:
        _render_config()


# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

def _render_setup() -> None:
    """Render the initial portfolio generation wizard."""
    if not SETUP_WIZARD_AVAILABLE or render_setup_wizard is None:
        st.info("Setup Wizard component unavailable.")
        return

    setup_complete = st.session_state.get("di_setup_complete", False)

    if setup_complete:
        st.success(
            "✅ Setup complete! Your initial portfolio has been generated. "
            "Import executed positions via **🔗 Connections → Schwab Direct → Direct Index Sync**."
        )
        if st.button("🔄 Re-run Setup Wizard"):
            st.session_state.pop("di_setup_complete", None)
            st.session_state.pop("di_wizard", None)
            st.rerun()
    else:
        render_setup_wizard()


def _render_config() -> None:
    """Render the YAML harvest configuration editor."""
    st.markdown("#### 🔧 Harvest Configuration")
    st.caption("Changes here update `config/direct_indexing_config.yaml` on save.")

    CONFIG_PATH = Path("config/direct_indexing_config.yaml")

    try:
        import yaml
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f)
        di = cfg.get("direct_indexing", {})
    except Exception as exc:
        st.error(f"Could not load config: {exc}")
        di = {}
        cfg = {}

    thresh = di.get("thresholds", {})
    repl = di.get("replacement", {})
    wash = di.get("wash_sale", {})
    data_cfg = di.get("data", {})
    setup_cfg = di.get("initial_setup", {})

    st.subheader("Harvest Thresholds")
    tc1, tc2 = st.columns(2)
    with tc1:
        new_loss_pct = st.number_input(
            "Loss threshold (%)",
            min_value=1.0, max_value=50.0,
            value=float(thresh.get("loss_threshold_pct", 10.0)),
            step=1.0,
            key="hub_cfg_loss_threshold_pct",
        )
        new_min_loss = st.number_input(
            "Min loss amount ($)",
            min_value=0.0,
            value=float(thresh.get("min_loss_amount", 500.0)),
            step=100.0,
            key="hub_cfg_min_loss_amount",
        )
        new_max_q = st.number_input(
            "Max harvests per quarter",
            min_value=1, max_value=100,
            value=int(thresh.get("max_harvests_per_quarter", 10)),
            step=1,
            key="hub_cfg_max_harvests_per_quarter",
        )
    with tc2:
        new_gains_harvest = st.checkbox(
            "Enable gains harvesting (0% LTCG bracket)",
            value=bool(thresh.get("enable_gains_harvesting", True)),
            key="hub_cfg_enable_gains_harvesting",
        )
        new_gains_pct = st.number_input(
            "Gains threshold (%)",
            min_value=1.0, max_value=100.0,
            value=float(thresh.get("gains_threshold_pct", 15.0)),
            step=1.0,
            disabled=not new_gains_harvest,
            key="hub_cfg_gains_threshold_pct",
        )
        new_min_hold = st.number_input(
            "Min holding period (days)",
            min_value=0, max_value=365,
            value=int(thresh.get("min_holding_period_days", 0)),
            step=1,
            key="hub_cfg_min_holding_period_days",
        )

    st.subheader("Replacement Strategy")
    rc1, rc2 = st.columns(2)
    with rc1:
        new_strategy = st.selectbox(
            "Strategy",
            ["sector_based", "correlation_based", "manual"],
            index=["sector_based", "correlation_based", "manual"].index(
                repl.get("strategy", "sector_based")
            ),
            key="hub_cfg_strategy",
        )
        new_prefer_large = st.checkbox(
            "Prefer larger-cap replacements",
            value=bool(repl.get("prefer_larger_cap", True)),
            key="hub_cfg_prefer_large",
        )
    with rc2:
        new_num_alt = st.number_input(
            "# of alternative suggestions",
            min_value=1, max_value=10,
            value=int(repl.get("num_alternatives", 3)),
            step=1,
            key="hub_cfg_num_alternatives",
        )
        new_allow_cross = st.checkbox(
            "Allow cross-sector replacements",
            value=bool(repl.get("allow_cross_sector", False)),
            key="hub_cfg_allow_cross",
        )
        new_exclude_repl_raw = st.text_input(
            "Exclude from replacements (comma-separated)",
            value=", ".join(repl.get("exclude_from_replacements", [])),
            key="hub_cfg_exclude_repl",
        )

    st.subheader("Wash Sale Settings")
    wc1, wc2 = st.columns(2)
    with wc1:
        new_wash_window = st.number_input(
            "Wash sale window (days)",
            min_value=1, max_value=90,
            value=int(wash.get("window_days", 30)),
            step=1,
            key="hub_cfg_wash_window_days",
        )
        new_auto_exclude = st.checkbox(
            "Auto-exclude wash sale risks",
            value=bool(wash.get("auto_exclude", True)),
            key="hub_cfg_auto_exclude",
        )
    with wc2:
        new_check_similar = st.checkbox(
            "Check substantially identical securities",
            value=bool(wash.get("check_similar_securities", True)),
            key="hub_cfg_check_similar",
        )
        new_etfs_identical = st.checkbox(
            "Consider ETFs as substantially identical",
            value=bool(wash.get("consider_etfs_identical", False)),
            key="hub_cfg_etfs_identical",
        )

    st.subheader("Index Coverage & Weighting")
    import math as _math
    new_weighting_mode = st.radio(
        "Position weighting",
        options=["stock", "sector"],
        index=0 if setup_cfg.get("weighting_mode", "stock") == "stock" else 1,
        format_func=lambda x: (
            "Equal weight per stock (RSP-style)"
            if x == "stock"
            else "Equal weight per sector (balanced sectors)"
        ),
        key="hub_cfg_weighting_mode",
        help=(
            "Stock: every stock gets the same dollar amount — matches RSP's construction. "
            "Sector: each of the 11 GICS sectors gets ~9.1% of the portfolio, "
            "then stocks within each sector are equal-weighted."
        ),
    )

    new_coverage_pct = st.slider(
        "Index coverage (%)",
        min_value=10,
        max_value=100,
        value=int(setup_cfg.get("index_coverage_pct", 100)),
        step=5,
        key="hub_cfg_index_coverage_pct",
        help=(
            "Percentage of the ~500 S&P 500 stocks to BUY as your direct index. "
            "Stocks are chosen proportionally across all 11 GICS sectors so sector "
            "balance is preserved. The remainder form your replacement pool."
        ),
    )
    _est_total = 503
    _est_buy = max(1, _math.ceil(_est_total * new_coverage_pct / 100.0))
    _est_pool = _est_total - _est_buy
    st.caption(
        f"At {new_coverage_pct}%: ~**{_est_buy}** stocks purchased, "
        f"~**{_est_pool}** in replacement pool"
    )
    st.info(
        "ℹ️ This setting is applied when you **Generate Portfolio** in the Setup Wizard sub-tab. "
        "It does not modify an already-imported portfolio."
    )

    st.subheader("Data Refresh")
    dc1, dc2 = st.columns(2)
    with dc1:
        new_rsp_refresh = st.number_input(
            "RSP holdings refresh (days)",
            min_value=1, max_value=30,
            value=int(data_cfg.get("rsp_refresh_days", 7)),
            step=1,
            key="hub_cfg_rsp_refresh_days",
        )
    with dc2:
        new_price_refresh = st.number_input(
            "Price refresh (hours)",
            min_value=1, max_value=72,
            value=int(data_cfg.get("price_refresh_hours", 4)),
            step=1,
            key="hub_cfg_price_refresh_hours",
        )

    st.divider()

    if st.button("💾 Save Configuration", type="primary", key="hub_cfg_save"):
        try:
            import yaml

            exclude_repl = [
                s.strip().upper()
                for s in new_exclude_repl_raw.split(",")
                if s.strip()
            ]

            cfg.setdefault("direct_indexing", {})
            cfg["direct_indexing"]["thresholds"] = {
                "loss_threshold_pct": new_loss_pct,
                "min_loss_amount": new_min_loss,
                "max_harvests_per_quarter": new_max_q,
                "enable_gains_harvesting": new_gains_harvest,
                "gains_threshold_pct": new_gains_pct,
                "min_holding_period_days": new_min_hold,
            }
            cfg["direct_indexing"]["replacement"] = {
                "strategy": new_strategy,
                "prefer_larger_cap": new_prefer_large,
                "num_alternatives": new_num_alt,
                "allow_cross_sector": new_allow_cross,
                "min_market_cap": repl.get("min_market_cap", 1.0),
                "exclude_from_replacements": exclude_repl,
            }
            cfg["direct_indexing"]["wash_sale"] = {
                "window_days": new_wash_window,
                "auto_exclude": new_auto_exclude,
                "check_similar_securities": new_check_similar,
                "consider_etfs_identical": new_etfs_identical,
            }
            cfg["direct_indexing"]["data"] = {
                "rsp_refresh_days": new_rsp_refresh,
                "price_refresh_hours": new_price_refresh,
                "cache_duration": data_cfg.get("cache_duration", 1),
                "auto_refresh_on_startup": data_cfg.get("auto_refresh_on_startup", True),
            }
            cfg["direct_indexing"].setdefault("initial_setup", {})
            cfg["direct_indexing"]["initial_setup"]["index_coverage_pct"] = new_coverage_pct
            cfg["direct_indexing"]["initial_setup"]["weighting_mode"] = new_weighting_mode

            with open(CONFIG_PATH, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

            st.success("✅ Configuration saved successfully!")
        except Exception as exc:
            st.error(f"Failed to save config: {exc}")

# Made with Bob
