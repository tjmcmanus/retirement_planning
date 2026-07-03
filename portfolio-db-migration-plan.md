# Portfolio DB Migration Plan

## Overview

`portfolio_data_truth.csv` is currently the single source of truth for all portfolio
holdings. It is read in **20+ locations** across 9 files and written in 4 places. The
goal of this plan is to migrate that source of truth to a SQLite database (`portfolio.db`)
that:

- Supports atomic upserts, eliminating the read-merge-write race condition in the
  current CSV save logic
- Provides proper SQL filtering (replacing pandas row-filtering on every read)
- Is consistent with the existing `rsp_holdings.db` and `transactions.db` databases
- Automatically writes a CSV backup on every data change, preserving human-readable
  audit trail and backward compatibility with the ZIP export/import feature
- Leaves the parquet display cache layer (`portfolio_display_cache.parquet`) completely
  unchanged — it continues to sit on top of the data layer as before

### What Does NOT Change

- The parquet cache (`portfolio_display_cache.parquet`) and its 5-minute TTL refresh
  are untouched. The cache reads from memory (via `build_portfolio_display()`) not from
  the CSV directly, so swapping the underlying source is transparent to it.
- The portfolio display columns, enrichment logic (yfinance), and background threading
  model in `portfolio.py` are untouched.
- All UI components that receive `portdf` as a parameter and never touch the data layer
  (`portfolio_overview.py`, `portfolio_performance.py`, etc.) are untouched.
- Backup ZIP export/import in `pages/2_configuration.py` continues to work — the CSV
  backup file that `portfolio.db` writes on every change is the file that gets bundled.

### Schema

`portfolio.db` will contain a single table `holdings` that is a direct translation of
the CSV schema plus two bookkeeping columns:

```sql
CREATE TABLE IF NOT EXISTS holdings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    month         INTEGER NOT NULL,
    year          INTEGER NOT NULL,
    account_name  TEXT    NOT NULL,
    account_type  TEXT    NOT NULL,
    owner         TEXT    NOT NULL DEFAULT '',
    symbol        TEXT    NOT NULL,
    name          TEXT    NOT NULL DEFAULT '',
    sector        TEXT    NOT NULL DEFAULT '',
    qty           REAL    NOT NULL,
    purchase_price REAL   NOT NULL,
    purchase_date  TEXT   NOT NULL,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (month, year, account_name, symbol)
);
```

The `UNIQUE` constraint on `(month, year, account_name, symbol)` is the database
equivalent of the current merge key used in `save_portfolio_data()`.

---

## Sub-Tasks

---

### Sub-Task 1 — Create `portfolio_db.py` Data Access Layer

**Status:** `[x] done`

**Intent**

Introduce a new module `portfolio_db.py` that owns all SQLite interactions with
`portfolio.db`. No existing file is changed in this sub-task. This module is the
isolated data access layer (DAL) that the rest of the migration will route through.
Writing and validating it in isolation before touching any consumers reduces risk.

**Expected Outcomes**

- `portfolio_db.py` exists at the project root alongside `portfolio.py` and `load_data.py`.
- All functions are covered by a test script `test_portfolio_db.py` that can be run
  manually to verify correctness before migration continues.
- `portfolio.db` is created automatically on first use (no separate setup step needed).
- CSV backup is written to `portfolio_data_truth.csv` automatically on every write
  operation, preserving all downstream consumers that read the CSV.

**Todo List**

1. Create `portfolio_db.py` with the following public functions:

   **Schema & Init:**
   - `get_db_connection() -> sqlite3.Connection` — returns a connection to `portfolio.db`,
     creating the file and `holdings` table if they do not exist.

   **Reads (replacing `load_data.py` functions):**
   - `db_load_all() -> pd.DataFrame` — equivalent to `load_portfolio_truth()`;
     returns all rows as a DataFrame with the same 11 column names as the CSV.
   - `db_get_by_month(month: int, year: int) -> pd.DataFrame` — equivalent to
     `get_portfolio_truth_by_month()`; returns rows filtered to the given period.
   - `db_get_latest_month_year() -> tuple[int, int]` — equivalent to
     `get_latest_portfolio_month_year()`; returns the most recent (month, year) in DB.

   **Writes:**
   - `db_upsert(rows: pd.DataFrame) -> int` — equivalent to `save_portfolio_data(append=True)`;
     uses `INSERT OR REPLACE INTO holdings` for atomic upsert. Returns count of rows
     written. After writing, calls `_write_csv_backup()`.
   - `db_overwrite_month(month: int, year: int, rows: pd.DataFrame) -> int` — deletes
     all rows for the given (month, year) then inserts the new rows. Returns count.
     After writing, calls `_write_csv_backup()`.
   - `db_delete_row(month: int, year: int, account_name: str, symbol: str) -> bool` —
     deletes a single row by the unique key. After deleting, calls `_write_csv_backup()`.

   **Backup:**
   - `_write_csv_backup() -> None` — private function; called by every write operation.
     Reads all rows from `holdings` via `db_load_all()` and writes to
     `portfolio_data_truth.csv`. This is the mechanism that keeps the CSV in sync
     as a human-readable backup.

   **Migration:**
   - `migrate_from_csv(csv_path: str = 'portfolio_data_truth.csv') -> int` — one-time
     migration function; reads existing CSV and calls `db_upsert()` to populate the DB.
     Safe to run multiple times (upsert is idempotent). Returns total rows migrated.

2. Create `test_portfolio_db.py` with tests for each function above:
   - Uses a temporary in-memory SQLite DB (override `DB_PATH` for tests).
   - Tests: create table, insert rows, upsert updates, overwrite month, delete row,
     get_by_month filtering, get_latest_month_year, CSV backup written on write.

**Relevant Context**

- `portfolio_data_entry.py` lines 27-30 — `PORTFOLIO_TRUTH_FILE` constant and CSV schema
- `load_data.py` lines 237-300 — `load_portfolio_truth()`, `get_portfolio_truth_by_month()`,
  `get_latest_portfolio_month_year()` — exact equivalents to implement in DB form
- `portfolio_data_entry.py` lines 338-425 — `save_portfolio_data()` merge logic to replicate
  as atomic `INSERT OR REPLACE`
- `data/rsp_holdings.db` — reference for how other SQLite DBs in this project are structured

---

### Sub-Task 2 — One-Time Data Migration Script

**Status:** `[x] done`

**Intent**

Before routing any application code to `portfolio.db`, migrate the existing
`portfolio_data_truth.csv` data into it. This is a standalone script that can be run
once and verified before any code changes are made to consumers.

**Expected Outcomes**

- `portfolio.db` exists and contains all rows from `portfolio_data_truth.csv`.
- Row count in `portfolio.db` matches row count in CSV.
- Running the script a second time is safe (idempotent upsert).
- `portfolio_data_truth.csv` is unchanged after migration (it is the source being read,
  not modified).

**Todo List**

1. Create `migrate_csv_to_portfolio_db.py` as a standalone runnable script:
   ```
   python migrate_csv_to_portfolio_db.py
   ```
   The script should:
   a. Check that `portfolio_data_truth.csv` exists; exit with a clear error if not.
   b. Call `portfolio_db.migrate_from_csv()`.
   c. Print a summary: rows migrated, any duplicates skipped, final row count in DB.
   d. Verify by calling `db_load_all()` and comparing row count to CSV row count.
   e. Print `✅ Migration complete` or `❌ Mismatch: CSV has X rows, DB has Y rows`.

2. Run the script and verify the output before proceeding to Sub-Task 3.

**Relevant Context**

- `portfolio_db.py::migrate_from_csv()` — created in Sub-Task 1
- `portfolio_data_truth.csv` — source file, currently at project root

---

### Sub-Task 3 — Migrate `load_data.py` Reads to DB

**Status:** `[x] done`

**Intent**

`load_data.py` is the central read hub — it provides `load_portfolio_truth()`,
`get_portfolio_truth_by_month()`, and `get_latest_portfolio_month_year()` which are
called by `portfolio.py`, `tax_harvesting.py`, `portfolio_rebalancing.py`,
`bucket_strategy.py`, and `pages/5_strategy.py`. Migrating these three functions
to read from `portfolio.db` via `portfolio_db.py` changes the data source for all
downstream consumers in a single, contained edit.

The `@st.cache_data()` decorator on `load_portfolio_truth()` currently uses file
modification time (`_get_portfolio_file_mtime()`) as a cache key to invalidate when
the CSV changes. Since the DB write operations in `portfolio_db.py` also write the
CSV backup, this mtime-based invalidation continues to work without modification.

**Expected Outcomes**

- `load_portfolio_truth()` reads from `portfolio.db` via `db_load_all()`.
- `get_portfolio_truth_by_month()` reads from `portfolio.db` via `db_get_by_month()`.
- `get_latest_portfolio_month_year()` reads from `portfolio.db` via `db_get_latest_month_year()`.
- The `_get_portfolio_file_mtime()` cache-key helper remains unchanged (it still checks
  the CSV file mtime, which changes whenever `_write_csv_backup()` runs after a DB write).
- All callers of these functions (`portfolio.py`, `tax_harvesting.py`,
  `portfolio_rebalancing.py`, `bucket_strategy.py`, `pages/5_strategy.py`) continue to
  work without any changes — they call the same function signatures.

**Todo List**

1. In `load_data.py`, add import: `from portfolio_db import db_load_all, db_get_by_month, db_get_latest_month_year`.
2. Replace the body of `load_portfolio_truth()` (line 251): change `pd.read_csv(...)` to
   `db_load_all()`. Keep the `@st.cache_data()` decorator and `_file_mtime` parameter
   unchanged.
3. Replace the body of `get_portfolio_truth_by_month()` (line 298-299): change the
   `load_portfolio_truth()` call + filter to `db_get_by_month(month, year)`.
4. Replace the body of `get_latest_portfolio_month_year()` (line 269): change the
   `load_portfolio_truth()` call + max logic to `db_get_latest_month_year()`.
5. Keep `_get_portfolio_file_mtime()` unchanged — it is the cache invalidation key.
6. Verify no other functions in `load_data.py` read the CSV directly.

**Relevant Context**

- `load_data.py` lines 237-300 — three functions to migrate
- `portfolio_db.py` — `db_load_all()`, `db_get_by_month()`, `db_get_latest_month_year()`
- Callers: `portfolio.py:266`, `portfolio.py:272`, `tax_harvesting.py:318`,
  `portfolio_rebalancing.py:45`, `bucket_strategy.py:595`, `pages/5_strategy.py:2098`,
  `pages/5_strategy.py:2802`, `pages/5_strategy.py:2213`, `pages/5_strategy.py:2830`

---

### Sub-Task 4 — Migrate `portfolio_data_entry.py` Writes to DB

**Status:** `[x] done`

**Intent**

`portfolio_data_entry.py` is the primary write hub. It contains `save_portfolio_data()`,
the merge-write function called from the Holdings editor and indirectly from
`portfolio_connections.py`. Migrating its writes to DB eliminates the read-CSV →
merge-in-pandas → write-CSV race condition. The `_trigger_portfolio_cache_rebuild()`
background thread remains unchanged — it is a cache concern, not a data concern.

**Expected Outcomes**

- `save_portfolio_data(new_data, append=True)` calls `db_upsert(new_data)` instead of
  reading CSV → merging → writing CSV.
- `save_portfolio_data(new_data, append=False)` calls `db_overwrite_month()` for each
  (month, year) present in `new_data` instead of `new_data.to_csv(...)`.
- The CSV backup is written automatically by `portfolio_db._write_csv_backup()` — the
  explicit `combined_data.to_csv(PORTFOLIO_TRUTH_FILE, ...)` calls are removed.
- `_trigger_portfolio_cache_rebuild()` is unchanged.
- `backup_portfolio_data()` and `create_blank_portfolio_truth_file()` are updated to
  operate on the DB (backup = export CSV from DB; blank = truncate `holdings` table).

**Todo List**

1. In `portfolio_data_entry.py`, add import: `from portfolio_db import db_upsert, db_overwrite_month`.
2. In `save_portfolio_data()`:
   a. Replace the `append=True` branch (lines 377-413): remove the `pd.read_csv` /
      merge / `to_csv` block; replace with a single `db_upsert(new_data)` call.
   b. Replace the `FileNotFoundError` branch (lines 415-420): remove; `db_upsert`
      creates the DB automatically.
   c. Replace the `append=False` branch (lines 421-424): replace `new_data.to_csv(...)`
      with calls to `db_overwrite_month()` for each distinct (month, year) in `new_data`.
   d. Keep the `_trigger_portfolio_cache_rebuild(saved_data)` call at the end unchanged.
3. Update `backup_portfolio_data()` (lines 568-583): replace `shutil.copy2(PORTFOLIO_TRUTH_FILE, ...)`
   with: read all rows via `db_load_all()`, write to the timestamped backup CSV file.
4. Update `create_blank_portfolio_truth_file()` (lines 594-610): replace CSV write with
   `DELETE FROM holdings` via a direct `get_db_connection()` call, then write an empty
   CSV header file for backward compatibility.

**Relevant Context**

- `portfolio_data_entry.py` lines 338-470 — `save_portfolio_data()` and
  `_trigger_portfolio_cache_rebuild()` to modify
- `portfolio_data_entry.py` lines 568-610 — `backup_portfolio_data()` and
  `create_blank_portfolio_truth_file()` to update
- `portfolio_db.py` — `db_upsert()`, `db_overwrite_month()`, `db_load_all()`,
  `get_db_connection()`

---

### Sub-Task 5 — Migrate Remaining Direct CSV Readers

**Status:** `[x] done`

**Intent**

Three locations still read `portfolio_data_truth.csv` directly with `pd.read_csv()`
rather than going through `load_data.py`: the Holdings editor
(`portfolio_holdings_editor.py`), the configuration page (`pages/2_configuration.py`),
and the broker sync connector (`portfolio_connections.py`). These are migrated in this
sub-task. After this sub-task, no file in the project reads the CSV directly — all
reads go through `load_data.py` (which reads from DB) or `portfolio_db.py`.

**Expected Outcomes**

- `components/portfolio_holdings_editor.py::load_portfolio_data()` reads from DB via
  `db_get_by_month()` instead of `pd.read_csv()`.
- `pages/2_configuration.py` "Load Current Data" button reads from DB via `db_load_all()`
  instead of `pd.read_csv()`.
- `pages/2_configuration.py::_do_save()` writes to DB via `db_upsert()` instead of
  `df_to_save.to_csv(...)`. The backup logic is replaced by calling `backup_portfolio_data()`
  from `portfolio_data_entry.py` (which now backs up from DB).
- `components/portfolio_connections.py::merge_synced_holdings()` reads existing holdings
  via `db_get_by_month()` and writes back via `db_upsert()` instead of CSV read/merge/write.
- `components/schwab_connector.py` and `components/snaptrade_connector.py` hardcoded
  `portfolio_file = 'portfolio_data_truth.csv'` references are updated to write via
  `db_upsert()`.
- The ZIP export in `pages/2_configuration.py` reads the CSV backup file (which is always
  current, written by `_write_csv_backup()`) — no change needed to export logic.
- The ZIP import in `pages/2_configuration.py` writes the CSV file then calls
  `migrate_from_csv()` to populate the DB — one line added after the existing write.

**Todo List**

1. **`components/portfolio_holdings_editor.py`** — `load_portfolio_data()` (line 192):
   Replace `pd.read_csv(PORTFOLIO_TRUTH_FILE)` + filter with `db_get_by_month(month, year)`.
   Remove the manual column filtering/reordering (DB query returns correct columns directly).

2. **`components/portfolio_holdings_editor.py`** — `backup_before_save()` (line 269):
   Replace `shutil.copy2(PORTFOLIO_TRUTH_FILE, backup_file)` with a call to
   `backup_portfolio_data()` from `portfolio_data_entry.py`.

3. **`pages/2_configuration.py`** — `_do_save()` (lines 4708-4725):
   a. Replace `shutil.copy2('portfolio_data_truth.csv', backup_name)` with
      `backup_portfolio_data()` from `portfolio_data_entry.py`.
   b. Replace `df_to_save.to_csv('portfolio_data_truth.csv', index=False)` with
      `db_upsert(df_to_save)` (or `db_overwrite_month()` if the save is a full replacement).
   c. Keep `build_portfolio_display.clear()` and the spinner rebuild unchanged.

4. **`pages/2_configuration.py`** — "Load Current Data" button (lines 4409, 4437):
   Replace `pd.read_csv('portfolio_data_truth.csv')` with `db_load_all()`.

5. **`pages/2_configuration.py`** — ZIP import (line 5463-5464):
   After writing the CSV bytes to file, add one line:
   `portfolio_db.migrate_from_csv('portfolio_data_truth.csv')` to re-populate the DB.

6. **`components/portfolio_connections.py`** — `merge_synced_holdings()` (lines 498-512):
   Replace `pd.read_csv(portfolio_file)` with `db_get_by_month(month, year)`.
   Replace `merged_df.to_csv(portfolio_file, ...)` with `db_upsert(merged_df)`.
   Remove the verification re-read (line 517) — DB upsert is atomic, no verify needed.

7. **`components/schwab_connector.py`** (line 967) and
   **`components/snaptrade_connector.py`** (line 723): Replace the hardcoded
   `portfolio_file = 'portfolio_data_truth.csv'` pattern and any associated CSV
   read/write calls with `db_upsert()` / `db_get_by_month()`.

**Relevant Context**

- `components/portfolio_holdings_editor.py` lines 166-216 — `load_portfolio_data()`
- `components/portfolio_holdings_editor.py` lines 262-270 — `backup_before_save()`
- `pages/2_configuration.py` lines 4405-4442 — Load Current Data reads
- `pages/2_configuration.py` lines 4705-4730 — `_do_save()`
- `pages/2_configuration.py` lines 5385-5465 — ZIP export/import
- `components/portfolio_connections.py` lines 470-546 — `merge_synced_holdings()`
- `components/schwab_connector.py` line 967
- `components/snaptrade_connector.py` line 723

---

### Sub-Task 6 — Remove `portfolio_data_truth.csv` as a Live Read Target

**Status:** `[x] done`

**Intent**

After Sub-Tasks 3-5, all reads and writes go through `portfolio.db`. The CSV file
now exists solely as a human-readable backup (written by `_write_csv_backup()` on
every DB write). This sub-task formalises that role: the CSV constant
`PORTFOLIO_TRUTH_FILE` is redefined as a backup output path, a guard is added to
`load_data.py` to detect if the DB is empty and auto-migrate from CSV (for
first-run scenarios where an existing CSV predates the DB), and the old direct
`pd.read_csv` fallback paths in `portfolio_holdings_editor.py` are removed.

**Expected Outcomes**

- `portfolio.db` is the live data source. `portfolio_data_truth.csv` is a
  read-only backup output. No application code reads the CSV as a data source.
- On first run with an existing CSV but empty DB, `load_data.py` auto-migrates.
- The project `README` / `QUICKSTART.md` notes that `portfolio.db` is the source
  of truth and `portfolio_data_truth.csv` is the human-readable export.

**Todo List**

1. In `load_data.py`, add a startup guard in `load_portfolio_truth()`:
   Before calling `db_load_all()`, check if `portfolio.db` is missing or empty
   AND `portfolio_data_truth.csv` exists — if so, call `migrate_from_csv()` automatically
   and log a one-time info message: *"Auto-migrated portfolio_data_truth.csv → portfolio.db"*.

2. In `portfolio_data_entry.py`, rename `PORTFOLIO_TRUTH_FILE` constant comment from
   *"source of truth"* to *"CSV backup output"* so its intent is clear in code.

3. In `portfolio_db.py`, update `_write_csv_backup()` docstring to explicitly state
   it is a backup output, not the source.

4. Update `QUICKSTART.md` to note:
   - `portfolio.db` — SQLite source of truth for portfolio holdings
   - `portfolio_data_truth.csv` — auto-generated human-readable backup (do not edit manually)
   - To restore from CSV backup: run `python migrate_csv_to_portfolio_db.py`

5. Update `.gitignore` if present: add `portfolio.db` to ignored files (same as
   other `.db` files) so it is not committed to git, but leave
   `portfolio_data_truth.csv` tracked (it is the human-readable backup that should
   be version-controlled).

**Relevant Context**

- `load_data.py` lines 237-252 — `load_portfolio_truth()` — add startup guard here
- `portfolio_data_entry.py` line 27 — `PORTFOLIO_TRUTH_FILE` constant
- `migrate_csv_to_portfolio_db.py` — migration script from Sub-Task 2
- `QUICKSTART.md` — documentation to update

---

## File Change Summary

### New Files

| File | Purpose |
|---|---|
| `portfolio_db.py` | Data access layer — all SQLite reads/writes for `portfolio.db` |
| `test_portfolio_db.py` | Manual test script for `portfolio_db.py` |
| `migrate_csv_to_portfolio_db.py` | One-time migration script |

### Modified Files

| File | Sub-Task | Change Summary |
|---|---|---|
| `load_data.py` | 3 | 3 functions route reads to `portfolio_db` instead of CSV |
| `portfolio_data_entry.py` | 4 | `save_portfolio_data()` uses `db_upsert()`; backup/blank helpers updated |
| `components/portfolio_holdings_editor.py` | 5 | `load_portfolio_data()` and `backup_before_save()` use DB |
| `pages/2_configuration.py` | 5 | `_do_save()`, Load button, ZIP import use DB |
| `components/portfolio_connections.py` | 5 | `merge_synced_holdings()` uses DB |
| `components/schwab_connector.py` | 5 | CSV reference replaced with `db_upsert()` |
| `components/snaptrade_connector.py` | 5 | CSV reference replaced with `db_upsert()` |
| `load_data.py` | 6 | Auto-migration guard on startup |
| `portfolio_data_entry.py` | 6 | Constant comment updated |
| `QUICKSTART.md` | 6 | Document new data architecture |

### Unchanged Files

Everything else — including `portfolio.py`, all display/UI components,
`tax_harvesting.py`, `portfolio_rebalancing.py`, `bucket_strategy.py`,
`pages/5_strategy.py`, and all Direct Indexing components — is untouched.
They call `getPortfolioData()` or `get_portfolio_truth_by_month()` which
continue to work identically, now backed by SQLite instead of CSV.

---

## Sequencing vs the Consolidation Plan

This migration is **independent** of `portfolio-consolidation-plan.md` and can be
done in either order. However, the recommended sequence is:

1. **This plan first** — establishes `portfolio.db` as the stable data foundation
2. **Consolidation plan second** — UI work builds on a solid data layer

If the consolidation plan is already in progress, this migration can proceed
concurrently because it only touches the data layer (`load_data.py`,
`portfolio_data_entry.py`, connectors) which the consolidation plan does not modify.
