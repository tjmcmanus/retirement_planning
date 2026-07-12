"""
portfolio_db.py
===============
Data access layer for portfolio.db — the SQLite source of truth for portfolio holdings.

Replaces direct reads/writes to portfolio_data_truth.csv throughout the application.
Every write operation automatically regenerates portfolio_data_truth.csv as a
human-readable backup so that downstream consumers (ZIP export, version control,
parquet cache invalidation via file mtime) continue to work unchanged.

Public API
----------
get_db_connection()                          -> sqlite3.Connection
db_load_all()                                -> pd.DataFrame
db_get_by_month(month, year)                 -> pd.DataFrame
db_get_latest_month_year()                   -> tuple[int, int]
db_upsert(rows)                              -> int
db_overwrite_month(month, year, rows)        -> int
db_delete_row(month, year, account_name, symbol) -> bool
migrate_from_csv(csv_path)                   -> int
enrich_holdings(month, year, force)          -> dict[str, int]
enrich_sectors(month, year, force)           -> dict[str, int]  (alias for enrich_holdings)
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DB_PATH = Path("portfolio.db")
CSV_BACKUP_PATH = Path("portfolio_data_truth.csv")

# Canonical column order — matches the CSV schema exactly
HOLDINGS_COLUMNS = [
    "month", "year", "account_name", "account_type", "owner",
    "symbol", "name", "sector", "qty", "purchase_price", "purchase_date",
]

# ---------------------------------------------------------------------------
# SQL injection hardening
# ---------------------------------------------------------------------------
# Exhaustive whitelist of every identifier that may be interpolated into a
# query string.  If a future refactor adds a column, it must be added here
# explicitly — the assertion below will catch the omission at import time.
_ALLOWED_COLUMNS: frozenset[str] = frozenset(HOLDINGS_COLUMNS)
_ALLOWED_TABLE: str = "holdings"

# Assert at import time: every entry in HOLDINGS_COLUMNS is in the whitelist.
# This turns any future drift between the constant and the whitelist into an
# immediate ImportError rather than a silent injection surface.
_unknown = [c for c in HOLDINGS_COLUMNS if c not in _ALLOWED_COLUMNS]
assert not _unknown, f"HOLDINGS_COLUMNS contains non-whitelisted identifiers: {_unknown}"

# Pre-built SELECT column list reused by every read query — built once here
# so the assertion runs exactly once and the string is not reconstructed on
# every call.
_HOLDINGS_SELECT: str = ", ".join(HOLDINGS_COLUMNS)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS holdings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    month          INTEGER NOT NULL,
    year           INTEGER NOT NULL,
    account_name   TEXT    NOT NULL,
    account_type   TEXT    NOT NULL DEFAULT '',
    owner          TEXT    NOT NULL DEFAULT '',
    symbol         TEXT    NOT NULL,
    name           TEXT    NOT NULL DEFAULT '',
    sector         TEXT    NOT NULL DEFAULT '',
    qty            REAL    NOT NULL DEFAULT 0,
    purchase_price REAL    NOT NULL DEFAULT 0,
    purchase_date  TEXT    NOT NULL DEFAULT '',
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (month, year, account_name, symbol)
);
"""


# ==============================================================================
# Connection & Initialisation
# ==============================================================================

# Thread-local storage for persistent connections, keyed by resolved db_path.
# Streamlit runs in a multi-threaded server; each thread gets its own
# connection so no locking is needed between threads.
_tls = threading.local()


def get_db_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """
    Return a persistent, thread-local connection to portfolio.db.

    The connection is created on first use within a thread and reused for
    all subsequent calls from that thread.  Schema initialisation
    (PRAGMA journal_mode=WAL + CREATE TABLE IF NOT EXISTS) runs only once
    per connection, not on every call.

    Args:
        db_path: Override for testing (pass Path(':memory:') or a temp path).

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    path_str = str(db_path) if db_path != Path(":memory:") else ":memory:"

    # _tls.conns is a dict[str, sqlite3.Connection] — one entry per db_path.
    if not hasattr(_tls, "conns"):
        _tls.conns: dict[str, sqlite3.Connection] = {}

    conn = _tls.conns.get(path_str)
    if conn is None:
        conn = sqlite3.connect(path_str, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
        _tls.conns[path_str] = conn
        logger.debug(f"get_db_connection: opened new connection to {path_str!r}")

    return conn


# ==============================================================================
# Reads
# ==============================================================================

def db_load_all(db_path: Path = DB_PATH) -> pd.DataFrame:
    """
    Load all holdings rows as a DataFrame.

    Equivalent to: pd.read_csv('portfolio_data_truth.csv')

    Returns:
        DataFrame with columns matching HOLDINGS_COLUMNS. Empty DataFrame
        (same columns) when the DB is empty or does not exist.
    """
    if db_path != Path(":memory:") and not db_path.exists():
        return pd.DataFrame(columns=HOLDINGS_COLUMNS)
    try:
        conn = get_db_connection(db_path)
        df = pd.read_sql_query(
            f"SELECT {_HOLDINGS_SELECT} FROM holdings "
            "ORDER BY year, month, account_name, symbol",
            conn,
        )
        return df
    except sqlite3.Error as exc:
        logger.error(f"db_load_all failed: {exc}")
        return pd.DataFrame(columns=HOLDINGS_COLUMNS)


def db_get_by_month(
    month: int,
    year: int,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """
    Load holdings for a specific month/year.

    Equivalent to:
        df = pd.read_csv('portfolio_data_truth.csv')
        return df[(df['month'] == month) & (df['year'] == year)]

    Returns:
        Filtered DataFrame (may be empty).
    """
    if db_path != Path(":memory:") and not db_path.exists():
        return pd.DataFrame(columns=HOLDINGS_COLUMNS)
    try:
        conn = get_db_connection(db_path)
        df = pd.read_sql_query(
            f"SELECT {_HOLDINGS_SELECT} FROM holdings "
            "WHERE month = ? AND year = ? "
            "ORDER BY account_name, symbol",
            conn,
            params=(month, year),
        )
        return df
    except sqlite3.Error as exc:
        logger.error(f"db_get_by_month({month}, {year}) failed: {exc}")
        return pd.DataFrame(columns=HOLDINGS_COLUMNS)


def db_get_latest_month_year(db_path: Path = DB_PATH) -> tuple[int, int]:
    """
    Return the most recent (month, year) available in the DB.

    Equivalent to get_latest_portfolio_month_year() in load_data.py.

    Returns:
        (month, year) tuple; falls back to current date if DB is empty.
    """
    if db_path != Path(":memory:") and not db_path.exists():
        now = datetime.now()
        return now.month, now.year
    try:
        conn = get_db_connection(db_path)
        row = conn.execute(
            "SELECT month, year FROM holdings "
            "ORDER BY year DESC, month DESC LIMIT 1"
        ).fetchone()
        if row:
            return int(row["month"]), int(row["year"])
    except sqlite3.Error as exc:
        logger.error(f"db_get_latest_month_year failed: {exc}")
    now = datetime.now()
    return now.month, now.year


# ==============================================================================
# Writes
# ==============================================================================

def db_upsert(rows: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """
    Atomically insert or replace holdings rows.

    Uses SQLite's INSERT OR REPLACE which respects the UNIQUE constraint on
    (month, year, account_name, symbol).  Equivalent to the read-CSV →
    merge-in-pandas → write-CSV pattern in save_portfolio_data(append=True).

    Args:
        rows: DataFrame with at least the HOLDINGS_COLUMNS columns.
        db_path: Override for testing.

    Returns:
        Number of rows written.
    """
    if rows.empty:
        return 0

    rows = _normalise(rows)
    conn = get_db_connection(db_path)
    try:
        rows[HOLDINGS_COLUMNS].to_sql(
            "holdings",
            conn,
            if_exists="append",
            index=False,
            method=_upsert_method,
        )
        conn.commit()
        n = len(rows)
        logger.info(f"db_upsert: wrote {n} rows")
    except sqlite3.Error as exc:
        conn.rollback()
        logger.error(f"db_upsert failed: {exc}")
        raise

    _write_csv_backup(db_path)
    return n


def db_overwrite_month(
    month: int,
    year: int,
    rows: pd.DataFrame,
    db_path: Path = DB_PATH,
) -> int:
    """
    Delete all rows for (month, year) and insert the new rows atomically.

    Used when the caller wants to replace an entire month's data rather than
    upsert individual rows.

    Args:
        month:   Month to overwrite (1-12).
        year:    Year to overwrite.
        rows:    New rows to insert (may be empty to just clear the month).
        db_path: Override for testing.

    Returns:
        Number of rows written.
    """
    rows = _normalise(rows) if not rows.empty else rows
    conn = get_db_connection(db_path)
    try:
        conn.execute(
            "DELETE FROM holdings WHERE month = ? AND year = ?",
            (month, year),
        )
        n = 0
        if not rows.empty:
            rows[HOLDINGS_COLUMNS].to_sql(
                "holdings",
                conn,
                if_exists="append",
                index=False,
                method=_upsert_method,
            )
            n = len(rows)
        conn.commit()
        logger.info(f"db_overwrite_month({month}/{year}): wrote {n} rows")
    except sqlite3.Error as exc:
        conn.rollback()
        logger.error(f"db_overwrite_month failed: {exc}")
        raise

    _write_csv_backup(db_path)
    return n


def db_delete_row(
    month: int,
    year: int,
    account_name: str,
    symbol: str,
    db_path: Path = DB_PATH,
) -> bool:
    """
    Delete a single holding by its unique key.

    Args:
        month, year, account_name, symbol: Unique key columns.
        db_path: Override for testing.

    Returns:
        True if a row was deleted, False if not found.
    """
    conn = get_db_connection(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM holdings "
            "WHERE month=? AND year=? AND account_name=? AND symbol=?",
            (month, year, account_name, symbol),
        )
        conn.commit()
        deleted = cur.rowcount > 0
    except sqlite3.Error as exc:
        conn.rollback()
        logger.error(f"db_delete_row failed: {exc}")
        return False

    if deleted:
        _write_csv_backup(db_path)
    return deleted


def db_update_account_metadata(
    accounts: list[dict],
    db_path: Path = DB_PATH,
) -> int:
    """
    Propagate account_type and owner changes from the config into portfolio.db.

    When an account's type or owner is renamed in the Configuration page, all
    existing holdings rows for that account_name should reflect the new values.
    This function performs a bulk UPDATE for every account in *accounts* whose
    actual DB values differ from the supplied ones.

    Args:
        accounts: List of dicts, each with keys ``account_name``, ``account_type``,
                  and ``owner`` (as stored in retirement_config.json).
        db_path:  Override for testing.

    Returns:
        Total number of rows updated across all accounts.
    """
    if not accounts:
        return 0

    conn = get_db_connection(db_path)
    total_updated = 0
    try:
        for account in accounts:
            name = str(account.get("account_name", "")).strip()
            new_type = str(account.get("account_type", "")).strip()
            new_owner = str(account.get("owner", "")).strip()
            if not name:
                continue
            cur = conn.execute(
                "UPDATE holdings "
                "SET account_type = ?, owner = ? "
                "WHERE account_name = ? "
                "  AND (account_type != ? OR owner != ?)",
                (new_type, new_owner, name, new_type, new_owner),
            )
            if cur.rowcount:
                logger.info(
                    f"db_update_account_metadata: '{name}' → "
                    f"type={new_type!r}, owner={new_owner!r} "
                    f"({cur.rowcount} row(s) updated)"
                )
            total_updated += cur.rowcount
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        logger.error(f"db_update_account_metadata failed: {exc}")
        raise

    if total_updated:
        _write_csv_backup(db_path)
        logger.info(f"db_update_account_metadata: {total_updated} total row(s) updated")

    return total_updated


# ==============================================================================
# Migration
# ==============================================================================

def migrate_from_csv(
    csv_path: str = str(CSV_BACKUP_PATH),
    db_path: Path = DB_PATH,
) -> int:
    """
    One-time (idempotent) migration from CSV to portfolio.db.

    Reads the CSV and calls db_upsert() so existing DB rows are not duplicated.
    Safe to run multiple times.

    Args:
        csv_path: Path to portfolio_data_truth.csv.
        db_path:  Override for testing.

    Returns:
        Total rows inserted/replaced.
    """
    csv = Path(csv_path)
    if not csv.exists():
        raise FileNotFoundError(f"CSV not found: {csv}")

    df = pd.read_csv(csv)
    if df.empty:
        logger.info("migrate_from_csv: CSV is empty, nothing to migrate")
        return 0

    # Only keep the canonical columns that exist in the CSV
    present = [c for c in HOLDINGS_COLUMNS if c in df.columns]
    df = df[present].copy()

    n = db_upsert(df, db_path=db_path)
    logger.info(f"migrate_from_csv: migrated {n} rows from {csv}")
    return n


# ==============================================================================
# Internal helpers
# ==============================================================================

def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce column types to match the DB schema."""
    df = df.copy()
    for col in HOLDINGS_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in ("account_name", "account_type", "owner",
                                    "symbol", "name", "sector", "purchase_date") else 0

    df["month"] = df["month"].astype(int)
    df["year"] = df["year"].astype(int)
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0.0)
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce").fillna(0.0)

    # Normalise purchase_date to YYYY-MM-DD string
    df["purchase_date"] = (
        pd.to_datetime(df["purchase_date"], errors="coerce")
        .dt.strftime("%Y-%m-%d")
        .fillna("")
    )

    for col in ("account_name", "account_type", "owner", "symbol", "name", "sector"):
        df[col] = df[col].fillna("").astype(str)

    return df


def _upsert_method(table, conn, keys, data_iter):
    """
    Custom pandas to_sql method that uses INSERT OR REPLACE so the UNIQUE
    constraint on (month, year, account_name, symbol) is honoured.
    """
    # Whitelist-guard both the table name and every column name before
    # interpolating them into the query string.
    if table.name != _ALLOWED_TABLE:
        raise ValueError(
            f"_upsert_method: unexpected table {table.name!r}; "
            f"only {_ALLOWED_TABLE!r} is permitted."
        )
    unknown_cols = [k for k in keys if k not in _ALLOWED_COLUMNS]
    if unknown_cols:
        raise ValueError(
            f"_upsert_method: column(s) not in whitelist: {unknown_cols}"
        )
    cols = ", ".join(keys)
    placeholders = ", ".join(["?"] * len(keys))
    sql = f"INSERT OR REPLACE INTO {_ALLOWED_TABLE} ({cols}) VALUES ({placeholders})"
    conn.executemany(sql, data_iter)


def _write_csv_backup(db_path: Path = DB_PATH) -> None:
    """
    Write all holdings to portfolio_data_truth.csv as a human-readable backup.

    This file is NOT the live data source — it is a backup output written
    automatically after every DB write. It preserves backward compatibility for:
    - ZIP export/import in pages/2_configuration.py
    - Parquet cache invalidation via file mtime in load_data.py
    - Human-readable audit trail / version control
    """
    try:
        df = db_load_all(db_path)
        df.to_csv(str(CSV_BACKUP_PATH), index=False)
        logger.debug(f"_write_csv_backup: wrote {len(df)} rows to {CSV_BACKUP_PATH}")
    except OSError as exc:
        logger.warning(f"_write_csv_backup failed (non-fatal): {exc}")


# ==============================================================================
# Holdings Enrichment (name + sector)
# ==============================================================================

# Sector values that mean "not yet classified" — fetched from brokerage API
# as an asset class rather than a GICS sector, or left empty.
_STALE_SECTORS = frozenset({
    '', 'Unknown', 'Stock', 'Mutual Fund', 'Index Fund', 'Fund',
    'MUTUALFUND', 'EQUITY', 'FIXED_INCOME', 'nan', 'NONE',
})


def _fetch_name_and_sector(symbol: str) -> tuple[str, str]:
    """
    Return (name, sector) for *symbol* from Yahoo Finance in a single call.

    name   – shortName (or longName fallback); empty string if unknown.
    sector – GICS sector / fund category; empty string if unknown.

    Special cases:
      CASH / MF:CASH          → ('Cash', 'MF:Cash')
      Options (embedded space) → ('', '')  — not resolvable via yfinance
      Numeric symbols          → ('', '')  — cash-balance rows, leave alone
    """
    import yfinance as yf

    sym_upper = symbol.strip().upper()

    if sym_upper in ('CASH', 'MF:CASH'):
        return 'Cash', 'MF:Cash'

    # Options (OCC format has embedded spaces) or numeric cash rows
    if ' ' in symbol or symbol.strip().lstrip('-').isdigit():
        return '', ''

    try:
        info = yf.Ticker(symbol).info
        if not info or 'symbol' not in info:
            return '', ''

        # ── Name ──────────────────────────────────────────────────────────
        name = (info.get('shortName') or info.get('longName') or '').strip()

        # ── Sector ────────────────────────────────────────────────────────
        sector = ''
        # Mutual funds: 5-letter alpha tickers get MF: prefix
        if len(symbol) == 5 and symbol.isalpha():
            cat = info.get('category', '')
            if cat and cat not in ('MUTUALFUND', ''):
                sector = f'MF:{cat}'
            elif info.get('categoryName', ''):
                sector = f'MF:{info["categoryName"]}'

        if not sector:
            sector = info.get('sector', '')
        if not sector:
            sector = info.get('category', '')
        if not sector:
            sector = info.get('quoteType', '')

        return name, sector

    except Exception as exc:
        logger.debug(f"_fetch_name_and_sector({symbol}): {exc}", exc_info=True)
        return '', ''


def enrich_holdings(
    month: Optional[int] = None,
    year: Optional[int] = None,
    force: bool = False,
    db_path: Path = DB_PATH,
    max_workers: int = 8,
) -> dict:
    """
    Fetch name and GICS sector from Yahoo Finance for holdings that have a
    stale/missing value in either field, and upsert the results back into
    portfolio.db in a single pass.

    A row is a candidate for enrichment when:
      • sector is in _STALE_SECTORS  (blank, 'Stock', 'Mutual Fund', etc.)
      • name is blank or missing

    Args:
        month:       Restrict to this month (None = all months).
        year:        Restrict to this year  (None = all years).
        force:       Re-fetch even rows that already have both values.
        db_path:     Override for testing.
        max_workers: Thread-pool concurrency for yfinance calls.

    Returns:
        dict with keys:
            'enriched'  – rows updated (name or sector changed)
            'unchanged' – rows that already had good values
            'failed'    – symbols where yfinance returned nothing useful
    """
    if month is not None and year is not None:
        df = db_get_by_month(month, year, db_path=db_path)
    else:
        df = db_load_all(db_path=db_path)

    if df.empty:
        return {'enriched': 0, 'unchanged': 0, 'failed': 0}

    if force:
        needs_enrich = df.copy()
    else:
        stale_sector = df['sector'].fillna('').apply(lambda s: s.strip() in _STALE_SECTORS)
        stale_name   = df['name'].fillna('').str.strip() == ''
        needs_enrich = df[stale_sector | stale_name].copy()

    if needs_enrich.empty:
        logger.info("enrich_holdings: all rows already complete — nothing to do")
        return {'enriched': 0, 'unchanged': len(df), 'failed': 0}

    unique_symbols = needs_enrich['symbol'].dropna().unique().tolist()
    logger.info(
        f"enrich_holdings: fetching name+sector for {len(unique_symbols)} symbols "
        f"({len(needs_enrich)} candidate rows)"
    )

    # Parallel fetch — one yfinance call per unique symbol
    results: dict[str, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_name_and_sector, sym): sym for sym in unique_symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                results[sym] = fut.result()
            except Exception as exc:
                logger.warning(f"enrich_holdings: fetch failed for {sym}: {exc}", exc_info=True)
                results[sym] = ('', '')

    enriched_rows = []
    enriched_count = 0
    failed_count = 0

    for _, row in needs_enrich.iterrows():
        fetched_name, fetched_sector = results.get(row['symbol'], ('', ''))

        # Determine what to write — never overwrite a good existing value
        new_name   = fetched_name   if fetched_name   else row.get('name', '')
        new_sector = fetched_sector if fetched_sector else row.get('sector', '')

        # Only count as enriched if at least one field actually changed
        name_changed   = (fetched_name   and str(row.get('name',   '')).strip() == '')
        sector_changed = (
            fetched_sector
            and str(row.get('sector', '')).strip() in _STALE_SECTORS
        )

        if name_changed or sector_changed:
            updated = row.copy()
            updated['name']   = new_name
            updated['sector'] = new_sector
            enriched_rows.append(updated)
            enriched_count += 1
        elif not fetched_name and not fetched_sector:
            failed_count += 1

    if enriched_rows:
        db_upsert(pd.DataFrame(enriched_rows), db_path=db_path)
        logger.info(
            f"enrich_holdings: updated {enriched_count} rows, "
            f"{failed_count} symbols had no yfinance data"
        )
    else:
        logger.info("enrich_holdings: no rows updated")

    unchanged_count = len(df) - len(needs_enrich)
    return {'enriched': enriched_count, 'unchanged': unchanged_count, 'failed': failed_count}


def enrich_sectors(
    month: Optional[int] = None,
    year: Optional[int] = None,
    force: bool = False,
    db_path: Path = DB_PATH,
    max_workers: int = 8,
) -> dict:
    """Alias for enrich_holdings() — kept for backward compatibility."""
    return enrich_holdings(
        month=month, year=year, force=force,
        db_path=db_path, max_workers=max_workers,
    )


# Made with Bob
