"""Regression: migration 026 must drop TEXT default before TIMESTAMPTZ cast."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "026_cve_change_detected_at_timestamptz.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_026", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_upgrade_drops_default_before_type_change():
  """Postgres rejects ALTER TYPE when a TEXT default cannot cast to timestamptz."""
  source = _MIGRATION.read_text(encoding="utf-8")
  drop_idx = source.index("ALTER COLUMN detected_at DROP DEFAULT")
  type_idx = source.index("ALTER COLUMN detected_at TYPE TIMESTAMPTZ")
  assert drop_idx < type_idx, "DROP DEFAULT must precede TYPE TIMESTAMPTZ in upgrade()"
