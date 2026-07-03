"""
test_portfolio_db.py
====================
Manual test script for portfolio_db.py.

Run:
    python test_portfolio_db.py

All tests use an in-memory SQLite DB so nothing touches portfolio.db or the CSV.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
import pandas as pd

# Ensure repo root is on the path
sys.path.insert(0, str(Path(__file__).parent))

import portfolio_db as pdb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mem_path() -> Path:
    """Return the sentinel value that portfolio_db treats as :memory:."""
    return Path(":memory:")


def _sample_rows(month: int = 1, year: int = 2026) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "month": month, "year": year,
            "account_name": "Schwab", "account_type": "Brokerage",
            "owner": "Joint", "symbol": "AAPL", "name": "Apple Inc.",
            "sector": "Technology", "qty": 10.0, "purchase_price": 150.0,
            "purchase_date": "2023-01-15",
        },
        {
            "month": month, "year": year,
            "account_name": "Schwab", "account_type": "Brokerage",
            "owner": "Joint", "symbol": "GOOGL", "name": "Alphabet Inc.",
            "sector": "Communication Services", "qty": 5.0, "purchase_price": 140.0,
            "purchase_date": "2022-04-01",
        },
        {
            "month": month, "year": year,
            "account_name": "Fidelity", "account_type": "Traditional",
            "owner": "Morticia", "symbol": "VFIAX", "name": "Vanguard 500 Index",
            "sector": "MUTUALFUND", "qty": 900.0, "purchase_price": 450.0,
            "purchase_date": "2020-03-10",
        },
    ])


PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        print(f"  ✅ {name}")
        PASS += 1
    else:
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))
        FAIL += 1


# ---------------------------------------------------------------------------
# Test: get_db_connection creates schema
# ---------------------------------------------------------------------------
def test_create_schema():
    print("\n[1] Schema creation")
    conn = pdb.get_db_connection(_mem_path())
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    check("holdings table created", "holdings" in tables)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(holdings)").fetchall()]
    for col in pdb.HOLDINGS_COLUMNS:
        check(f"column '{col}' exists", col in cols)
    conn.close()


# ---------------------------------------------------------------------------
# Test: db_upsert inserts rows
# ---------------------------------------------------------------------------
def test_upsert_insert(tmp_db: Path):
    print("\n[2] db_upsert — insert new rows")
    rows = _sample_rows()
    n = pdb.db_upsert(rows, db_path=tmp_db)
    check("returns row count", n == 3, f"got {n}")
    loaded = pdb.db_load_all(db_path=tmp_db)
    check("all rows loaded back", len(loaded) == 3, f"got {len(loaded)}")
    check("columns match", list(loaded.columns) == pdb.HOLDINGS_COLUMNS,
          str(list(loaded.columns)))


# ---------------------------------------------------------------------------
# Test: db_upsert updates existing row (idempotent)
# ---------------------------------------------------------------------------
def test_upsert_update(tmp_db: Path):
    print("\n[3] db_upsert — update existing row (UNIQUE key)")
    update = _sample_rows().copy()
    update.loc[update["symbol"] == "AAPL", "qty"] = 20.0
    pdb.db_upsert(update, db_path=tmp_db)
    loaded = pdb.db_load_all(db_path=tmp_db)
    aapl = loaded[loaded["symbol"] == "AAPL"]
    check("row count still 3 after upsert", len(loaded) == 3, f"got {len(loaded)}")
    check("AAPL qty updated to 20", float(aapl["qty"].iloc[0]) == 20.0,
          str(aapl["qty"].values))


# ---------------------------------------------------------------------------
# Test: db_overwrite_month
# ---------------------------------------------------------------------------
def test_overwrite_month(tmp_db: Path):
    print("\n[4] db_overwrite_month")
    new_rows = pd.DataFrame([{
        "month": 1, "year": 2026,
        "account_name": "NewAcct", "account_type": "Roth",
        "owner": "Joint", "symbol": "VTI", "name": "Vanguard Total Market",
        "sector": "Stock/ETF", "qty": 50.0, "purchase_price": 200.0,
        "purchase_date": "2024-06-01",
    }])
    pdb.db_overwrite_month(1, 2026, new_rows, db_path=tmp_db)
    loaded = pdb.db_get_by_month(1, 2026, db_path=tmp_db)
    check("old rows removed", len(loaded) == 1, f"got {len(loaded)}")
    check("new row present", loaded.iloc[0]["symbol"] == "VTI")


# ---------------------------------------------------------------------------
# Test: db_get_by_month filters correctly
# ---------------------------------------------------------------------------
def test_get_by_month(tmp_db: Path):
    print("\n[5] db_get_by_month filtering")
    # Add a different month
    rows_feb = _sample_rows(month=2, year=2026)
    pdb.db_upsert(rows_feb, db_path=tmp_db)

    jan = pdb.db_get_by_month(1, 2026, db_path=tmp_db)
    feb = pdb.db_get_by_month(2, 2026, db_path=tmp_db)
    check("Jan returns 1 row (overwritten in test 4)", len(jan) == 1,
          f"got {len(jan)}")
    check("Feb returns 3 rows", len(feb) == 3, f"got {len(feb)}")
    check("empty for non-existent month", len(
        pdb.db_get_by_month(12, 2099, db_path=tmp_db)
    ) == 0)


# ---------------------------------------------------------------------------
# Test: db_get_latest_month_year
# ---------------------------------------------------------------------------
def test_latest_month_year(tmp_db: Path):
    print("\n[6] db_get_latest_month_year")
    month, year = pdb.db_get_latest_month_year(db_path=tmp_db)
    check("returns (2, 2026)", (month, year) == (2, 2026), f"got ({month}, {year})")

    # Empty DB
    empty = Path(tempfile.mktemp(suffix=".db"))
    conn = pdb.get_db_connection(empty)
    conn.close()
    import datetime
    now = datetime.datetime.now()
    m, y = pdb.db_get_latest_month_year(db_path=empty)
    check("empty DB falls back to current month/year",
          (m, y) == (now.month, now.year), f"got ({m}, {y})")
    empty.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test: db_delete_row
# ---------------------------------------------------------------------------
def test_delete_row(tmp_db: Path):
    print("\n[7] db_delete_row")
    before = pdb.db_get_by_month(2, 2026, db_path=tmp_db)
    pdb.db_delete_row(2, 2026, "Schwab", "AAPL", db_path=tmp_db)
    after = pdb.db_get_by_month(2, 2026, db_path=tmp_db)
    check("row count decremented", len(after) == len(before) - 1,
          f"before={len(before)} after={len(after)}")
    check("deleted row gone", "AAPL" not in after[after["account_name"] == "Schwab"]["symbol"].values)
    result = pdb.db_delete_row(2, 2026, "Nonexistent", "XYZ", db_path=tmp_db)
    check("returns False for non-existent row", result is False)


# ---------------------------------------------------------------------------
# Test: CSV backup is written on every write
# ---------------------------------------------------------------------------
def test_csv_backup():
    print("\n[8] CSV backup written on upsert")
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        csv = Path(tmpdir) / "backup.csv"

        # Monkey-patch the backup path
        original_csv = pdb.CSV_BACKUP_PATH
        pdb.CSV_BACKUP_PATH = csv

        try:
            pdb.db_upsert(_sample_rows(), db_path=db)
            check("CSV backup file created", csv.exists())
            df = pd.read_csv(csv)
            check("CSV has correct row count", len(df) == 3, f"got {len(df)}")
            check("CSV has correct columns",
                  list(df.columns) == pdb.HOLDINGS_COLUMNS,
                  str(list(df.columns)))
        finally:
            pdb.CSV_BACKUP_PATH = original_csv


# ---------------------------------------------------------------------------
# Test: migrate_from_csv
# ---------------------------------------------------------------------------
def test_migrate_from_csv():
    print("\n[9] migrate_from_csv")
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "test.db"
        csv_path = Path(tmpdir) / "portfolio_data_truth.csv"
        backup_path = Path(tmpdir) / "backup.csv"

        # Write a CSV to migrate
        _sample_rows().to_csv(csv_path, index=False)

        original_csv = pdb.CSV_BACKUP_PATH
        pdb.CSV_BACKUP_PATH = backup_path

        try:
            n = pdb.migrate_from_csv(str(csv_path), db_path=db)
            check("migrated 3 rows", n == 3, f"got {n}")

            # Idempotency — run again
            n2 = pdb.migrate_from_csv(str(csv_path), db_path=db)
            total = len(pdb.db_load_all(db_path=db))
            check("idempotent — still 3 rows after second run", total == 3,
                  f"got {total}")

            # Missing CSV raises FileNotFoundError
            try:
                pdb.migrate_from_csv("/nonexistent/path.csv", db_path=db)
                check("raises FileNotFoundError for missing CSV", False)
            except FileNotFoundError:
                check("raises FileNotFoundError for missing CSV", True)
        finally:
            pdb.CSV_BACKUP_PATH = original_csv


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("portfolio_db.py — unit tests")
    print("=" * 60)

    test_create_schema()

    # All write tests share a single temp DB for stateful progression
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "test_portfolio.db"
        # Patch CSV backup path so tests don't write to project root
        original_csv = pdb.CSV_BACKUP_PATH
        pdb.CSV_BACKUP_PATH = Path(tmpdir) / "backup.csv"

        try:
            test_upsert_insert(tmp_db)
            test_upsert_update(tmp_db)
            test_overwrite_month(tmp_db)
            test_get_by_month(tmp_db)
            test_latest_month_year(tmp_db)
            test_delete_row(tmp_db)
        finally:
            pdb.CSV_BACKUP_PATH = original_csv

    test_csv_backup()
    test_migrate_from_csv()

    print("\n" + "=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)
    sys.exit(0 if FAIL == 0 else 1)
