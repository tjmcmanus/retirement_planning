"""Configuration read/write for the API.

Uses the same ``ConfigManager`` as the Streamlit app, so the file format, the
merge-with-defaults behaviour and the ``.backups/`` copy on every save are
identical. The file is re-read on each request because the Streamlit service
may have changed it.

Saving mirrors the "Save All Changes" button of ``pages/2_configuration.py``:
retirement age/year are derived from the dates, ``expected_annual_expenses`` is the
sum of the detailed expenses (only when that sum is > 0), and the Social Security
schedule (``ssincome.csv``) is regenerated.
"""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import zipfile
from datetime import datetime
from typing import Any

import app_cache
import ssi_calculator
from app.services import config_schema as schema
from config import DEFAULT_CONFIG, ConfigManager, reload_config, retirement_date_to_age_and_year

logger = logging.getLogger(__name__)
_lock = threading.Lock()

# Sections that are managed by the app, not by clients.
READ_ONLY_SECTIONS = {"metadata"}


class ValidationError(ValueError):
    """Raised with per-field errors: ``[{"path", "message"}]``."""

    def __init__(self, errors: list[dict[str, str]]):
        super().__init__("; ".join(f"{e['path']}: {e['message']}" for e in errors))
        self.errors = errors


def read_config() -> dict[str, Any]:
    return ConfigManager().config


def _deep_merge(target: dict[str, Any], changes: dict[str, Any]) -> None:
    """Merge nested dicts key by key; lists and scalars replace."""
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = schema.deep_copy(value)


def _derive(config: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Apply the values Streamlit derives on save. Returns what was derived."""
    derived: dict[str, Any] = {}
    flat = schema.flatten(changes)
    pi = config["personal_info"]

    for n in (1, 2):
        keys = (f"personal_info.person{n}_birth_date", f"personal_info.person{n}_retirement_date")
        if any(k in flat for k in keys) and pi.get(f"person{n}_birth_date") and pi.get(f"person{n}_retirement_date"):
            age, year = retirement_date_to_age_and_year(pi[f"person{n}_retirement_date"], pi[f"person{n}_birth_date"])
            pi[f"person{n}_retirement_age"], pi[f"person{n}_retirement_year"] = age, year
            derived[f"personal_info.person{n}_retirement_age"] = age
            derived[f"personal_info.person{n}_retirement_year"] = year

    if any(p.startswith("expenses.living_expenses.") or p.startswith("expenses.entertainment_expenses.") for p in flat):
        exp = config["expenses"]
        total = sum(exp.get("living_expenses", {}).get(k, 0) or 0 for k in schema.LIVING_KEYS)
        total += sum(exp.get("entertainment_expenses", {}).get(k, 0) or 0 for k in schema.ENTERTAINMENT_KEYS)
        if total > 0:  # same rule as Streamlit: keep the saved value when the breakdown is empty
            config["financial_assumptions"]["expected_annual_expenses"] = total
            derived["financial_assumptions.expected_annual_expenses"] = total
    return derived


def _regenerate_ssi_schedule(mgr: ConfigManager) -> str | None:
    """Rewrite ``ssincome.csv`` like Streamlit does. Returns a warning message on failure."""
    ss = mgr.get_section("social_security")
    if not (ss.get("person1_ssi_amount", 0) > 0 or ss.get("person2_ssi_amount", 0) > 0):
        return None
    try:
        start = datetime.now().year
        df = ssi_calculator.generate_ssi_schedule_from_config(mgr, start_year=start, end_year=start + 30, cola_rate=0.02)
        if df.empty:
            return "No Social Security schedule was generated"
        ssi_calculator.export_ssi_schedule_to_csv(df, "ssincome.csv")
    except Exception as exc:  # the config is already saved; report instead of failing the request
        logger.exception("SSI schedule generation failed")
        return f"Social Security schedule was not updated: {exc}"
    return None


def _persist(mgr: ConfigManager, touched: set[str]) -> list[str]:
    if not mgr.save_config():
        raise OSError("Could not write the configuration file")
    warnings: list[str] = []
    # Make the engine (which reads the shared headless manager) see the change,
    # and drop memoised results computed from the old values.
    reload_config()
    app_cache.clear_all()
    if touched & {"social_security", "personal_info"}:
        warning = _regenerate_ssi_schedule(mgr)
        if warning:
            warnings.append(warning)
    return warnings


def update_config(changes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Validate, deep-merge ``{section: {key: value}}`` into the saved config and persist it.

    Raises ``ValueError`` for unknown/read-only sections and ``ValidationError`` for bad values.
    Returns ``{"config", "derived", "warnings"}``.
    """
    for section in changes:
        if section not in DEFAULT_CONFIG:
            raise ValueError(f"Unknown config section: {section!r}")
        if section in READ_ONLY_SECTIONS:
            raise ValueError(f"Config section is read-only: {section!r}")

    with _lock:
        mgr = ConfigManager()
        errors = schema.validate_changes(changes, mgr.config, DEFAULT_CONFIG)
        if errors:
            raise ValidationError(errors)

        merged = schema.deep_copy(mgr.config)
        _deep_merge(merged, changes)
        errors = schema.validate_merged(merged)
        if errors:
            raise ValidationError(errors)

        derived = _derive(merged, changes)
        mgr.config = merged
        warnings = _persist(mgr, set(changes))
        return {"config": mgr.config, "derived": derived, "warnings": warnings}


def reset_config() -> dict[str, Any]:
    """Replace the saved config with ``DEFAULT_CONFIG`` (the previous file is backed up first)."""
    with _lock:
        mgr = ConfigManager()
        mgr.reset_to_defaults()
        warnings = _persist(mgr, set())
        return {"config": mgr.config, "derived": {}, "warnings": warnings}


def export_bundle() -> tuple[str, bytes]:
    """ZIP with config JSON, portfolio CSV and estate planning JSON, like the Streamlit export."""
    mgr = ConfigManager()
    pi = mgr.config.get("personal_info", {})
    header = f"// Primary person: {pi.get('person1_name', 'Person 1')}\n// Spouse: {pi.get('person2_name', 'Person 2')}\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("retirement_config.json", (header + json.dumps(mgr.config, indent=2)).encode("utf-8"))
        for name in ("portfolio_data_truth.csv", "estate_planning_data.json"):
            if os.path.exists(name):
                with open(name, "rb") as fh:
                    content = fh.read()
                if content:
                    zf.writestr(name, content)
    return f"retirement_config_{datetime.now():%Y%m%d_%H%M%S}.zip", buf.getvalue()


def ss_preview(fra_amount: float, claiming_age: int) -> dict[str, Any]:
    """Monthly benefit at the claiming age, from the monthly benefit at Full Retirement Age."""
    monthly = ssi_calculator.calculate_benefit_at_claiming_age(fra_amount, claiming_age)
    return {"monthly": round(monthly, 2), "annual": round(monthly * 12, 2),
            "pct_of_fra": round(monthly / fra_amount * 100, 1) if fra_amount else None}
