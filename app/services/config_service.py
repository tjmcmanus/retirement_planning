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
import re
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

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
    if "portfolio_accounts" in touched:  # like the Streamlit "Save Accounts" button
        try:
            from portfolio_db import DB_PATH, db_update_account_metadata
            db_update_account_metadata(mgr.get_section("portfolio_accounts").get("accounts", []),
                                       db_path=Path(DB_PATH).resolve())
        except Exception as exc:  # the config is already saved
            logger.exception("Updating holdings from the account table failed")
            warnings.append(f"Accounts were saved but existing holdings were not updated: {exc}")
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


MAX_IMPORT_BYTES = 50 * 1024 * 1024  # config + portfolio CSV + estate JSON are small; refuse anything absurd

# What a bundle carries besides retirement_config.json (same set export_bundle writes).
#   plain files   : bundle name -> path restored to
#   SQLite files  : bundle name -> (path restored to, table that must exist)
#   scenarios     : scenarios/<id>.json -> data/scenarios/<id>.json
# Not bundled on purpose: data/credentials.db (brokerage secrets, encrypted with the machine's
# ENCRYPTION_KEY) and the re-downloadable caches. Re-link brokerage accounts on the new machine.
_PORTFOLIO_CSV = "portfolio_data_truth.csv"
_ESTATE_JSON = "estate_planning_data.json"
_BUNDLE_DATA_FILES = (_PORTFOLIO_CSV, _ESTATE_JSON)
_BUNDLE_DB_FILES = {
    "transactions.db": ("data/transactions.db", "transactions"),
    "performance_history.db": ("data/performance_history.db", "portfolio_snapshots"),
}
_SCENARIO_DIR = "data/scenarios"
_SCENARIO_NAME = re.compile(r"^[A-Za-z0-9_.-]+\.json$")
_REQUIRED_HOLDINGS_COLUMNS = {"month", "year", "account_name", "symbol", "qty"}


def _parse_config_text(raw: bytes) -> str:
    """Decode a config file and drop the leading ``//`` comment lines the export adds."""
    text = raw.decode("utf-8-sig")
    return "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("//"))


def _snapshot_db(src: str, dst: str) -> None:
    """Consistent copy of a live SQLite file (safe while it is in WAL mode / being written)."""
    src_conn, dst_conn = sqlite3.connect(src), sqlite3.connect(dst)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()


def _backup_file(name: str) -> None:
    """Copy an existing data file to ``.backups/`` before it is overwritten."""
    if not os.path.exists(name):
        return
    os.makedirs(".backups", exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(name))
    dst = os.path.join(".backups", f"{stem}_{datetime.now():%Y%m%d_%H%M%S}{ext}")
    if ext == ".db":
        _snapshot_db(name, dst)
    else:
        shutil.copy2(name, dst)


def _validate_sqlite(content: bytes, label: str, required_table: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "check.db")
        with open(path, "wb") as fh:
            fh.write(content)
        conn = sqlite3.connect(path)
        try:
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"{label} is not a valid SQLite database") from exc
        finally:
            conn.close()
    if not ok or required_table not in tables:
        raise ValueError(f"{label} is not a valid {required_table} database")


def _validate_holdings_csv(content: bytes) -> None:
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise ValueError(f"{_PORTFOLIO_CSV} could not be read: {exc}") from exc
    missing = _REQUIRED_HOLDINGS_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"{_PORTFOLIO_CSV} is missing column(s): {', '.join(sorted(missing))}")


def _write_atomic(path: str, content: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".importing"
    with open(tmp, "wb") as fh:
        fh.write(content)
    os.replace(tmp, path)


def _install_db(path: str, content: bytes) -> None:
    for suffix in ("-wal", "-shm"):  # stale journal files of the replaced database must not be applied to the new one
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    _write_atomic(path, content)


def import_bundle(filename: str, data: bytes) -> dict[str, Any]:
    """Restore a config ``.zip`` bundle (or a legacy ``.json``) onto this machine.

    Everything in the file is read and validated before anything is written, so a bad file
    changes nothing. Existing files are backed up to ``.backups/`` first (portfolio.db too).
    The portfolio table is *replaced* by the bundle's CSV (not merged), SQLite files are swapped
    in whole, scenarios are added/overwritten by id.
    Returns ``{"config", "restored", "warnings"}``; raises ``ValueError`` for an unusable file.
    """
    if not data:
        raise ValueError("The file is empty")
    if len(data) > MAX_IMPORT_BYTES:
        raise ValueError("The file is too large")

    extras: dict[str, bytes] = {}                 # plain files by bundle name
    dbs: dict[str, bytes] = {}                    # SQLite files by bundle name
    scenarios: dict[str, bytes] = {}              # scenario file name -> content
    if filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # Match by basename so bundles made on Windows or in a subfolder still import.
                members = {n.replace("\\", "/"): n for n in zf.namelist() if not n.endswith("/")}
                names = {m.split("/")[-1].lower(): n for m, n in members.items()}
                if "retirement_config.json" not in names:
                    raise ValueError("The ZIP bundle does not contain retirement_config.json")

                def read(member: str) -> bytes:
                    if zf.getinfo(member).file_size > MAX_IMPORT_BYTES:
                        raise ValueError(f"{member} is too large")
                    return zf.read(member)

                config_raw = read(names["retirement_config.json"])
                for n in _BUNDLE_DATA_FILES:
                    if n in names and (content := read(names[n])):
                        extras[n] = content
                for n in _BUNDLE_DB_FILES:
                    if n in names and (content := read(names[n])):
                        dbs[n] = content
                for m, n in members.items():
                    parts = m.split("/")
                    if len(parts) >= 2 and parts[-2].lower() == "scenarios" and parts[-1].lower().endswith(".json"):
                        if not _SCENARIO_NAME.match(parts[-1]):
                            raise ValueError(f"Unsafe scenario file name: {parts[-1]}")
                        scenarios[parts[-1]] = read(n)
        except zipfile.BadZipFile as exc:
            raise ValueError("The file is not a valid ZIP archive") from exc
    elif filename.lower().endswith(".json"):
        config_raw = data
    else:
        raise ValueError("Choose a .zip bundle or a .json configuration file")

    try:
        config_text = _parse_config_text(config_raw)
        parsed = json.loads(config_text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read the configuration JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("The configuration JSON must be an object of sections")

    # Validate every companion file now, so a bad one aborts before anything is overwritten.
    if _PORTFOLIO_CSV in extras:
        _validate_holdings_csv(extras[_PORTFOLIO_CSV])
    if _ESTATE_JSON in extras:
        try:
            json.loads(extras[_ESTATE_JSON].decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{_ESTATE_JSON} is not valid JSON: {exc}") from exc
    for n, content in dbs.items():
        _validate_sqlite(content, n, _BUNDLE_DB_FILES[n][1])
    for n, content in scenarios.items():
        try:
            json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"scenarios/{n} is not valid JSON: {exc}") from exc

    with _lock:
        mgr = ConfigManager()
        if not mgr.import_config(config_text):  # merges with DEFAULT_CONFIG so newer settings get defaults
            raise ValueError("Could not import the configuration JSON")

        restored = ["retirement_config.json"]
        warnings: list[str] = []
        for name, content in extras.items():
            _backup_file(name)
            _write_atomic(name, content)
            restored.append(name)
        if _PORTFOLIO_CSV in extras:
            try:
                from portfolio_db import DB_PATH, replace_from_csv
                db_path = Path(DB_PATH).resolve()  # connections are cached per path string
                _backup_file(str(db_path))
                rows = replace_from_csv(_PORTFOLIO_CSV, db_path=db_path)
                restored.append(f"portfolio.db replaced ({rows} rows)")
            except Exception as exc:  # CSV is restored; the DB can be rebuilt from it
                logger.exception("portfolio.db update after import failed")
                warnings.append(f"{_PORTFOLIO_CSV} was restored but portfolio.db was not updated: {exc}")
        for name, content in dbs.items():
            dest = _BUNDLE_DB_FILES[name][0]
            _backup_file(dest)
            _install_db(dest, content)
            restored.append(dest)
        for name, content in scenarios.items():
            dest = os.path.join(_SCENARIO_DIR, name)
            _backup_file(dest)
            _write_atomic(dest, content)
        if scenarios:
            restored.append(f"{len(scenarios)} scenario(s)")

        warnings += _persist(mgr, {"social_security", "personal_info"})
        return {"config": mgr.config, "restored": restored, "warnings": warnings}


def export_bundle() -> tuple[str, bytes]:
    """ZIP with everything needed to rebuild this install on another machine.

    retirement_config.json, portfolio CSV, estate planning JSON, the transaction / performance
    SQLite databases (consistent snapshots) and saved scenarios. See ``import_bundle``.
    """
    mgr = ConfigManager()
    pi = mgr.config.get("personal_info", {})
    header = f"// Primary person: {pi.get('person1_name', 'Person 1')}\n// Spouse: {pi.get('person2_name', 'Person 2')}\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("retirement_config.json", (header + json.dumps(mgr.config, indent=2)).encode("utf-8"))
        for name in _BUNDLE_DATA_FILES:
            if os.path.exists(name):
                with open(name, "rb") as fh:
                    content = fh.read()
                if content:
                    zf.writestr(name, content)
        with tempfile.TemporaryDirectory() as tmp:
            for name, (path, _table) in _BUNDLE_DB_FILES.items():
                if os.path.exists(path):
                    snap = os.path.join(tmp, name)
                    _snapshot_db(path, snap)
                    zf.write(snap, name)
        if os.path.isdir(_SCENARIO_DIR):
            for sc in sorted(Path(_SCENARIO_DIR).glob("*.json")):
                zf.write(sc, f"scenarios/{sc.name}")
    return f"retirement_config_{datetime.now():%Y%m%d_%H%M%S}.zip", buf.getvalue()


def ss_preview(fra_amount: float, claiming_age: int) -> dict[str, Any]:
    """Monthly benefit at the claiming age, from the monthly benefit at Full Retirement Age."""
    monthly = ssi_calculator.calculate_benefit_at_claiming_age(fra_amount, claiming_age)
    return {"monthly": round(monthly, 2), "annual": round(monthly * 12, 2),
            "pct_of_fra": round(monthly / fra_amount * 100, 1) if fra_amount else None}
