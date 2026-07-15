"""Alembic revision hygiene — IDs must fit alembic_version.version_num."""

from __future__ import annotations

import re
from pathlib import Path

_VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
_REVISION_RE = re.compile(r'^revision\s*=\s*"([^"]+)"', re.MULTILINE)
_DOWN_REVISION_RE = re.compile(r'^down_revision\s*=\s*(?:"([^"]+)"|None)', re.MULTILINE)

# Alembic default version_num is VARCHAR(32) until migration 027 widens it.
_MAX_REVISION_LEN_BEFORE_WIDEN = 32


def _load_revisions() -> list[tuple[str, str | None, Path]]:
    rows: list[tuple[str, str | None, Path]] = []
    for path in sorted(_VERSIONS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        rev_match = _REVISION_RE.search(text)
        down_match = _DOWN_REVISION_RE.search(text)
        assert rev_match, f"missing revision in {path.name}"
        rows.append((rev_match.group(1), down_match.group(1) if down_match else None, path))
    return rows


def test_revision_ids_fit_default_alembic_version_column():
    """Production Postgres ships alembic_version.version_num as VARCHAR(32)."""
    revisions = _load_revisions()
    by_id = {rev for rev, _, _ in revisions}
    for rev, down, path in revisions:
        assert len(rev) <= _MAX_REVISION_LEN_BEFORE_WIDEN, (
            f"{path.name}: revision '{rev}' is {len(rev)} chars "
            f"(limit {_MAX_REVISION_LEN_BEFORE_WIDEN})"
        )
        if down is not None:
            assert down in by_id, f"{path.name}: unknown down_revision '{down}'"


def test_026_drops_default_before_timestamptz_cast():
    path = _VERSIONS_DIR / "026_cve_detected_at_tz.py"
    source = path.read_text(encoding="utf-8")
    drop_idx = source.index("ALTER COLUMN detected_at DROP DEFAULT")
    type_idx = source.index("ALTER COLUMN detected_at TYPE TIMESTAMPTZ")
    assert drop_idx < type_idx, "DROP DEFAULT must precede TYPE TIMESTAMPTZ in upgrade()"


def test_027_widens_alembic_version_num():
    path = _VERSIONS_DIR / "027_alembic_version_num_widen.py"
    source = path.read_text(encoding="utf-8")
    assert "ALTER TABLE alembic_version" in source
    assert "VARCHAR(128)" in source
