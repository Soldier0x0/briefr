"""db.timeutil helpers."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.timeutil import utcnow_for_db


def test_utcnow_for_db_postgres_returns_aware_datetime():
    value = utcnow_for_db(pg=True)
    assert isinstance(value, datetime)
    assert value.tzinfo is not None
