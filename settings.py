"""
settings.py

Central location for filesystem roots.

APP_DIR  - directory containing the application code.
DATA_DIR - directory holding user data (config JSON, CSV tables, SQLite DBs, caches).

DATA_DIR defaults to APP_DIR, so running from a source checkout behaves exactly as
before. In a container, set DATA_DIR=/data (a volume) and start the process with
that directory as the working directory: the many modules that use paths relative
to the working directory then read and write the volume automatically, and modules
that previously built paths from __file__ use data_path().
"""

import os
from pathlib import Path

APP_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = Path(os.environ.get("DATA_DIR") or APP_DIR).resolve()


def data_path(*parts: str) -> Path:
    """Return a path under DATA_DIR."""
    return DATA_DIR.joinpath(*parts)
