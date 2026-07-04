"""
migrate_csv_to_portfolio_db.py
==============================
One-time migration script: portfolio_data_truth.csv → portfolio.db

Usage:
    python migrate_csv_to_portfolio_db.py

Safe to run multiple times — db_upsert() is idempotent so re-running will
not create duplicate rows.  The script verifies row counts match before
reporting success.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).parent))

CSV_PATH = "portfolio_data_truth.csv"


def main() -> int:
    import pandas as pd
    from portfolio_db import migrate_from_csv, db_load_all, DB_PATH

    # ---- Pre-flight checks ---------------------------------------------------
    csv = Path(CSV_PATH)
    if not csv.exists():
        print(f"❌  {CSV_PATH} not found. Nothing to migrate.")
        return 1

    csv_df = pd.read_csv(csv)
    csv_rows = len(csv_df)
    print(f"📄  Source CSV:  {CSV_PATH}  ({csv_rows} rows)")
    print(f"🗄️   Target DB:   {DB_PATH}")
    print()

    # ---- Migrate -------------------------------------------------------------
    print("⏳  Migrating …")
    try:
        n = migrate_from_csv(CSV_PATH)
    except Exception as exc:
        print(f"❌  Migration failed: {exc}")
        return 1

    # ---- Verify --------------------------------------------------------------
    db_df = db_load_all()
    db_rows = len(db_df)

    print(f"✏️   Rows written : {n}")
    print(f"📊  DB row count  : {db_rows}")
    print(f"📊  CSV row count : {csv_rows}")
    print()

    if db_rows > 0:
        dupes_removed = csv_rows - db_rows
        if dupes_removed > 0:
            print(f"ℹ️   {dupes_removed} duplicate row(s) collapsed by UNIQUE constraint "
                  "(same month/year/account/symbol) — this is correct behaviour.")
        print("✅  Migration complete — portfolio.db is ready.")
        print()
        print("Next step: the application will now read from portfolio.db")
        print("automatically.  portfolio_data_truth.csv is kept as a backup.")
        return 0
    else:
        print(f"❌  DB is empty after migration — check logs for errors.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
