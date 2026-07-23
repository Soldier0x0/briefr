"""Alembic revision hygiene — IDs must fit alembic_version.version_num."""

from __future__ import annotations

import re
from pathlib import Path

_VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
_REVISION_RE = re.compile(r'^revision\s*=\s*"([^"]+)"', re.MULTILINE)
_DOWN_REVISION_RE = re.compile(r'^down_revision\s*=\s*(?:"([^"]+)"|None)', re.MULTILINE)

# Alembic default version_num is VARCHAR(32) until migration 027 widens it.
_MAX_REVISION_LEN_BEFORE_WIDEN = 32

# Postgres reserved words that fail as *unquoted column names* in CREATE TABLE.
# (Not the full keyword list — e.g. KEY is unreserved and used in sync_state.)
# Source incident: 2026-07-23 unquoted ``references`` broke Alembic 035 on prod.
_RESERVED_COLUMN_RE = re.compile(
    r"(?im)^[ \t]+(?P<ident>references|user|order|group|table|select|limit|offset|"
    r"check|default|constraint|primary|foreign|unique|grant|revoke|"
    r"analyze|end|all|any|as|on|or|and|not|null|true|false|"
    r"case|when|then|else|into|from|where|join|left|right|inner|outer|"
    r"window|over|filter|returning|values|with|using|like|"
    r"exists|in|is|distinct|asc|desc|full|natural|cross|union|except|intersect|"
    r"create|drop|alter|to|do|for|"
    r"current_user|current_date|current_time|current_timestamp|"
    r"localtime|localtimestamp|session_user|leading|trailing|both|"
    r"cast|array|fetch|having|initially|lateral|only|placing|some|"
    r"symmetric|asymmetric|variadic|collate|column|deferrable)"
    r"[ \t]+(?P<type>BIGSERIAL|SERIAL|SMALLINT|INTEGER|BIGINT|NUMERIC|DECIMAL|"
    r"REAL|DOUBLE|BOOLEAN|BOOL|TEXT|VARCHAR|CHAR|BYTEA|JSON|JSONB|"
    r"TIMESTAMPTZ|TIMESTAMP|DATE|TIME|UUID|INET|CIDR)\b"
)


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


def test_no_unquoted_postgres_reserved_column_names_in_migrations():
    """Guard against prod-breaking DDL (2026-07-23: unquoted ``references``).

    Quote reserved identifiers (``\"references\"``) or rename the column
    (preferred: ``rule_references``). Bare ``references JSONB`` fails on Postgres.
    """
    offenders: list[str] = []
    for path in sorted(_VERSIONS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for match in _RESERVED_COLUMN_RE.finditer(source):
            # Allow already-quoted forms: "references" JSONB
            start = match.start("ident")
            if start > 0 and source[start - 1] == '"':
                continue
            offenders.append(
                f"{path.name}:{source.count(chr(10), 0, start) + 1}: "
                f"unquoted reserved column '{match.group('ident')}' "
                f"before type {match.group('type')}"
            )
    assert not offenders, (
        "Postgres reserved words used as unquoted column names:\n  "
        + "\n  ".join(offenders)
        + "\nQuote them (\"references\") or rename (rule_references)."
    )
