"""
conftest.py — pytest configuration for the tests/ directory.

Adds the project root to sys.path so that all test files can import
application modules (strategy, calculations, config, etc.) by name,
regardless of whether pytest is invoked from the project root or
the tests/ subdirectory.
"""
import sys
import tempfile
from pathlib import Path

import pytest

# Project root is one level up from this file (tests/)
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def tmp_db(tmp_path_factory):
    """
    Shared temporary SQLite database for portfolio_db tests.

    Session-scoped so the six stateful tests (upsert → update → overwrite →
    get_by_month → latest_month_year → delete_row) all operate on the same DB
    in the order they are defined, matching the __main__ block in the test file.

    Also patches pdb.CSV_BACKUP_PATH for the duration of the session so no
    test writes touch the project root's portfolio_data_truth.csv.
    """
    import portfolio_db as pdb

    tmpdir = tmp_path_factory.mktemp("portfolio_db")
    db_path = tmpdir / "test_portfolio.db"
    backup_path = tmpdir / "backup.csv"

    original_csv = pdb.CSV_BACKUP_PATH
    pdb.CSV_BACKUP_PATH = backup_path
    try:
        yield db_path
    finally:
        pdb.CSV_BACKUP_PATH = original_csv
