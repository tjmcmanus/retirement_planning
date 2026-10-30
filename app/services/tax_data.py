"""Tax data administration for the API (the IRS lookup tables the engine reads).

Replaces ``pages/9_admin_tax_data.py``. The eight CSV files live in the working
directory (``/data`` in the container) and are read by ``load_data`` and the
strategy engine, so every write here is validated, backed up to ``.backups/``
(like every other save in the app), written atomically, and followed by
``app_cache.clear_all()``.

Differences from the Streamlit page, on purpose:
  * The column rules match the real files. The page's upload check required
    ``filing_status`` in irmaa.csv / atm.csv and lowercase ``age`` in rmd.csv,
    none of which exist, so re-uploading a downloaded copy of those tables failed.
  * Every write makes a backup (the page only did for uploads).
  * Cells are checked (blank, non-numeric, non-integer in whole-number columns)
    before anything is written.
"""
from __future__ import annotations

import io
import json
import logging
import math
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import app_cache

logger = logging.getLogger(__name__)
_lock = threading.Lock()

MAX_REPORTED_ERRORS = 50
YEAR_MIN, YEAR_MAX = 2020, 2100  # same bounds as the Streamlit page
FILING_STATUSES = ["married_filing_jointly", "single"]
BACKUP_DIR = ".backups"

# kind: "int" (whole number), "float", "text". ``choices`` restrict text columns.
TABLES: dict[str, dict[str, Any]] = {
    "standard": {
        "name": "Standard Deduction", "filename": "standard.csv",
        "columns": {"year": "int", "filing_status": "text", "deduction": "int"},
        "choices": {"filing_status": FILING_STATUSES},
    },
    "income_rates": {
        "name": "Income Tax Brackets", "filename": "income_rates.csv",
        "columns": {"year": "int", "filing_status": "text", "lower": "int", "upper": "int", "rate": "float"},
        "choices": {"filing_status": FILING_STATUSES},
    },
    "cap_gains": {
        "name": "Capital Gains Brackets", "filename": "cap_gains.csv",
        "columns": {"year": "int", "filing_status": "text", "lower": "int", "upper": "int", "rate": "float"},
        "choices": {"filing_status": FILING_STATUSES},
    },
    "ira_limits": {
        "name": "IRA & 401(k) Limits", "filename": "ira_limits.csv",
        "columns": {c: "int" for c in (
            "year", "ira_contribution_base", "ira_catchup_50plus",
            "roth_phaseout_start_mfj", "roth_phaseout_end_mfj",
            "roth_phaseout_start_single", "roth_phaseout_end_single",
            "k401_employee_limit", "k401_total_limit", "k401_catchup_50", "k401_catchup_60_63")},
        "choices": {},
    },
    "irmaa": {
        "name": "IRMAA (Medicare Surcharges)", "filename": "irmaa.csv",
        "columns": {"year": "int", "lower": "int", "upper": "int", "part_b_monthly": "float",
                    "part_a_monthly": "float", "part_d_base_monthly": "float", "part_d_irmaa_monthly": "float"},
        "choices": {},
    },
    "rmd": {
        "name": "RMD Life Expectancy", "filename": "rmd.csv",
        "columns": {"Age": "int", "Distribution": "float"},
        "choices": {},
    },
    "ssincome": {
        "name": "Social Security Income", "filename": "ssincome.csv",
        "columns": {"year": "int", "age": "int", "person": "text", "monthly_benefit": "float"},
        "choices": {},
    },
    "atm": {
        "name": "ATM (Alternative Minimum Tax)", "filename": "atm.csv",
        "columns": {"year": "int", "deduction": "int", "lower": "int", "upper": "int",
                    "phase_out": "int", "rate": "float", "exception_rate": "float"},
        "choices": {},
    },
}


class TableValidationError(ValueError):
    """Raised with ``[{"row", "column", "message"}]``. ``row`` is 0-based or None."""

    def __init__(self, errors: list[dict[str, Any]], message: str = "Tax data not saved"):
        super().__init__(message)
        self.message = message
        self.errors = errors


def _spec(key: str) -> dict[str, Any]:
    try:
        return TABLES[key]
    except KeyError:
        raise LookupError(f"Unknown tax table: {key!r}") from None


def _path(spec: dict[str, Any]) -> Path:
    return Path(spec["filename"])


def _read(spec: dict[str, Any]) -> pd.DataFrame:
    path = _path(spec)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {spec['filename']}")
    return pd.read_csv(path)


def _year_col(df_or_spec_columns) -> str | None:
    return "year" if "year" in df_or_spec_columns else None


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """JSON-safe records (numpy scalars -> Python, NaN -> None)."""
    return json.loads(df.to_json(orient="records"))


def _kind(spec: dict[str, Any], column: str, series: pd.Series | None = None) -> str:
    if column in spec["columns"]:
        return spec["columns"][column]
    if series is not None and pd.api.types.is_numeric_dtype(series):
        return "float"
    return "text"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def list_tables() -> list[dict[str, Any]]:
    out = []
    for key, spec in TABLES.items():
        item: dict[str, Any] = {"key": key, "name": spec["name"], "filename": spec["filename"], "exists": _path(spec).exists()}
        if item["exists"]:
            try:
                df = _read(spec)
                item.update(rows=len(df), columns=len(df.columns))
                if "year" in df.columns and len(df):
                    item["year_span"] = [int(df["year"].min()), int(df["year"].max())]
            except Exception as exc:  # a broken file must not hide the other tables
                logger.exception("Could not read %s", spec["filename"])
                item.update(exists=True, error=str(exc))
        out.append(item)
    return out


def get_table(key: str, year: int | None = None) -> dict[str, Any]:
    """The table's columns plus the rows of one year (tables without a year column return all rows)."""
    spec = _spec(key)
    df = _read(spec)
    has_year = "year" in df.columns
    this_year = datetime.now().year
    years: list[int] = []
    scope = None
    if has_year:
        years = sorted({int(y) for y in df["year"].dropna().unique()} | {this_year - 1, this_year, this_year + 1})
        scope = year if year is not None else this_year
        view = df[df["year"] == scope]
    else:
        view = df
    columns = []
    for c in df.columns:
        col: dict[str, Any] = {"name": str(c), "kind": _kind(spec, c, df[c])}
        if c in spec["choices"]:
            col["choices"] = spec["choices"][c]
        columns.append(col)
    span = [int(df["year"].min()), int(df["year"].max())] if has_year and len(df) else None
    return {
        "key": key, "name": spec["name"], "filename": spec["filename"],
        "columns": columns, "has_year": has_year, "year": scope, "years": years,
        "year_span": span, "total_rows": len(df), "rows": _records(view),
    }


def download(key: str) -> tuple[str, bytes]:
    spec = _spec(key)
    path = _path(spec)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {spec['filename']}")
    stem = spec["filename"].removesuffix(".csv")
    return f"{stem}_{datetime.now():%Y%m%d}.csv", path.read_bytes()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _num(value: Any) -> float | None:
    """A finite float, or None for blank / non-numeric / NaN / bool."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _check_records(spec: dict[str, Any], columns: list[str], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cell-level checks. Only the columns the spec knows about are constrained."""
    errors: list[dict[str, Any]] = []

    def add(row: int | None, column: str | None, message: str) -> None:
        errors.append({"row": row, "column": column, "message": message})

    missing = [c for c in spec["columns"] if c not in columns]
    if missing:
        add(None, None, f"Missing required columns: {', '.join(missing)}")
    known = [c for c in spec["columns"] if c in columns]

    for i, rec in enumerate(records):
        for col in known:
            kind, value = spec["columns"][col], rec.get(col)
            if kind == "text":
                text = "" if value is None or (isinstance(value, float) and math.isnan(value)) else str(value).strip()
                if not text:
                    add(i, col, "is blank")
                elif spec["choices"].get(col) and text not in spec["choices"][col]:
                    add(i, col, f"must be one of: {', '.join(spec['choices'][col])} (got {text!r})")
                continue
            number = _num(value)
            if number is None:
                add(i, col, "is blank" if value is None or str(value).strip() in ("", "nan") else f"is not a number ({value!r})")
            elif kind == "int" and number != round(number):
                add(i, col, f"must be a whole number (got {value})")
            elif col == "year" and not (YEAR_MIN <= number <= YEAR_MAX):
                add(i, col, f"must be between {YEAR_MIN} and {YEAR_MAX} (got {int(number)})")
    return errors


def _format_errors(errors: list[dict[str, Any]]) -> list[str]:
    lines = []
    for e in errors[:MAX_REPORTED_ERRORS]:
        where = "" if e["row"] is None else f"Row {e['row'] + 1}" + (f", {e['column']}" if e["column"] else "") + ": "
        lines.append(f"{where}{e['message']}")
    if len(errors) > MAX_REPORTED_ERRORS:
        lines.append(f"...and {len(errors) - MAX_REPORTED_ERRORS} more")
    return lines


def _normalise(spec: dict[str, Any], df: pd.DataFrame) -> pd.DataFrame:
    """Cast constrained columns to their kind (validated beforehand) and trim text."""
    df = df.copy()
    for col, kind in spec["columns"].items():
        if col not in df.columns:
            continue
        if kind == "text":
            df[col] = df[col].astype(str).str.strip()
        elif kind == "int":
            df[col] = pd.to_numeric(df[col]).round().astype("int64")
        else:
            df[col] = pd.to_numeric(df[col]).astype("float64")
    return df


def _parse_csv(text: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.StringIO(text))
    except pd.errors.EmptyDataError:
        raise TableValidationError([{"row": None, "column": None, "message": "The file is empty"}], "Invalid CSV") from None
    except pd.errors.ParserError as exc:
        raise TableValidationError([{"row": None, "column": None, "message": f"Could not parse the CSV: {exc}"}], "Invalid CSV") from None
    return df


def validate_upload(key: str, csv_text: str) -> dict[str, Any]:
    """Check an uploaded replacement file without writing anything."""
    spec = _spec(key)
    df = _parse_csv(csv_text)
    errors = _check_records(spec, [str(c) for c in df.columns], _records(df))
    if df.empty and not errors:
        errors.append({"row": None, "column": None, "message": "The file has no data rows"})
    extra = [str(c) for c in df.columns if c not in spec["columns"]]
    return {
        "valid": not errors,
        "errors": _format_errors(errors),
        "warnings": [f"Extra columns will be kept but are not checked: {', '.join(extra)}"] if extra else [],
        "rows": len(df), "columns": [str(c) for c in df.columns],
        "preview": _records(df.head(10)),
    }


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _backup(spec: dict[str, Any]) -> str | None:
    src = _path(spec)
    if not src.exists():
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stem = spec["filename"].removesuffix(".csv")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest, n = Path(BACKUP_DIR) / f"{stem}_{stamp}.csv", 1
    while dest.exists():  # two writes in the same second must not overwrite the first backup
        dest, n = Path(BACKUP_DIR) / f"{stem}_{stamp}_{n}.csv", n + 1
    dest.write_bytes(src.read_bytes())
    return str(dest)


def _write(spec: dict[str, Any], df: pd.DataFrame) -> str | None:
    """Back up, write atomically, drop memoised results."""
    backup = _backup(spec)
    path = _path(spec)
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
    app_cache.clear_all()
    return backup


def save_rows(key: str, year: int | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Replace the rows of ``year`` (or of the whole table when it has no year column).

    Rows of other years are not touched. Nothing is written when validation fails.
    """
    spec = _spec(key)
    with _lock:
        df = _read(spec)
        columns = [str(c) for c in df.columns]
        has_year = "year" in columns
        if has_year and year is None:
            raise ValueError("year is required for this table")

        records = [{c: r.get(c) for c in columns} for r in rows]
        errors = _check_records(spec, columns, records)
        if has_year:
            for i, rec in enumerate(records):
                number = _num(rec.get("year"))
                if number is not None and int(number) != year:
                    errors.append({"row": i, "column": "year", "message": f"must be {year} (this view edits {year} only)"})
        if errors:
            raise TableValidationError(errors)

        new = _normalise(spec, pd.DataFrame(records, columns=columns))
        for col in columns:  # keep columns the spec does not know (e.g. from an upload) in their file dtype
            if col not in spec["columns"] and pd.api.types.is_numeric_dtype(df[col]):
                new[col] = pd.to_numeric(new[col], errors="coerce")

        if has_year:
            others = df[df["year"] != year]
            was_sorted = bool(df["year"].is_monotonic_increasing)
            if was_sorted:
                out = pd.concat([others, new], ignore_index=True).sort_values("year", kind="stable", ignore_index=True)
            else:  # keep the file's own order: splice into the old block, else append
                idx = df.index[df["year"] == year]
                if len(idx):
                    first = int(idx[0])
                    before, after = df.iloc[:first], df.iloc[first:]
                    out = pd.concat([before[before["year"] != year], new, after[after["year"] != year]], ignore_index=True)
                else:
                    out = pd.concat([others, new], ignore_index=True)
        else:
            out = new
        if out.empty:
            raise TableValidationError([{"row": None, "column": None, "message": "A table cannot be left with no rows"}])

        backup = _write(spec, out)
    result = get_table(key, year)
    result["backup"] = backup
    return result


def replace_table(key: str, csv_text: str) -> dict[str, Any]:
    """Replace the whole file with a validated upload."""
    spec = _spec(key)
    report = validate_upload(key, csv_text)
    if not report["valid"]:
        raise TableValidationError(
            [{"row": None, "column": None, "message": m} for m in report["errors"]], "Upload failed validation")
    with _lock:
        df = _normalise(spec, _parse_csv(csv_text))
        backup = _write(spec, df)
    result = get_table(key)
    result["backup"] = backup
    return result
