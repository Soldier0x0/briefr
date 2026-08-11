"""Dual-SQL dialect pair ratchet (F1.4 / Phase 1 W8).

Scans ``backend/db/`` for module-level ``*_PG`` SQL string constants and
requires each to have either:

1. A matching ``*_SQLITE`` sibling in the **same file** (strip the ``_PG``
   suffix and append ``_SQLITE``), or
2. An explicit ``# pg-only`` marker documenting that Postgres-only SQL is
   intentional.

``# pg-only`` marker convention
-------------------------------
Place ``# pg-only`` (optionally followed by ``:`` and a short reason) on:

- the same line as the ``_PG`` assignment, or
- any of the three non-empty comment/blank lines immediately above it.

Examples::

    # pg-only: pgvector ANN — no SQLite equivalent
    _ANN_RELATED_PG = '''SELECT ...'''

    _LIST_PG = "SELECT ..."  # pg-only

Ratchet
-------
``ALLOWED_MAX`` is the baseline count of same-file ``_PG``/``_SQLITE`` pairs.
The live pair count must stay ``<= ALLOWED_MAX``. When you remove a pair
(consolidate dialects), lower ``ALLOWED_MAX``. Raising it requires an
intentional review (do not grow the dual-maintenance surface casually).

This is the short-term F1.4 guard only — Testcontainers / Postgres-default
CI remain out of Phase 1 closeout.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB_DIR = BACKEND / "db"

# Baseline same-file _PG/_SQLITE pair count at W8 land (2026-07-20).
# May only stay equal or decrease unless intentionally raised in review.
# Raised 133→136 for Program E (2026-07-22): ai_operation_payloads INSERT +
# SELECT_BY_OPERATION_ID + cache_retention purge pair (SQLite parity required).
# Raised 136→137 for OTX stale fallback (#742): _READ_OTX_CVE_PULSES_ANY_AGE pair.
# Raised 137→138 for threat-intel blocklist (db/blocklist.py): catalog-evidence
# + OTX-candidate read pairs — both tables exist in the SQLite bootstrap too.
ALLOWED_MAX = 138

_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")
_PG_ONLY_RE = re.compile(r"#\s*pg-only\b", re.IGNORECASE)


def _module_level_assignments(lines: list[str]) -> list[tuple[int, str]]:
    """Return (1-based lineno, name) for top-level ``NAME =`` assignments."""
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if line.startswith((" ", "\t")):
            continue
        m = _ASSIGN_RE.match(line)
        if m:
            out.append((i + 1, m.group(1)))
    return out


def _has_pg_only_marker(lines: list[str], lineno: int) -> bool:
    """True if ``# pg-only`` appears on the assignment line or within 3 lines above."""
    idx = lineno - 1
    if idx < 0 or idx >= len(lines):
        return False
    if _PG_ONLY_RE.search(lines[idx]):
        return True
    checked = 0
    j = idx - 1
    while j >= 0 and checked < 3:
        raw = lines[j]
        stripped = raw.strip()
        if not stripped:
            j -= 1
            continue
        if stripped.startswith("#"):
            if _PG_ONLY_RE.search(raw):
                return True
            checked += 1
            j -= 1
            continue
        # Non-comment code above — stop looking.
        break
    return False


def _scan_db_dialect_pairs() -> tuple[list[str], int]:
    """Return (orphan messages, pair_count) across ``backend/db/**/*.py``."""
    orphans: list[str] = []
    pair_count = 0

    for path in sorted(DB_DIR.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assigns = _module_level_assignments(lines)
        names = {name for _, name in assigns}
        sqlite_names = {n for n in names if n.endswith("_SQLITE")}
        rel = path.relative_to(BACKEND)

        for lineno, name in assigns:
            if not name.endswith("_PG"):
                continue
            base = name[: -len("_PG")]
            sibling = f"{base}_SQLITE"
            if sibling in sqlite_names:
                pair_count += 1
                continue
            if _has_pg_only_marker(lines, lineno):
                continue
            orphans.append(
                f"{rel}:{lineno} {name} has no {sibling} sibling and no # pg-only marker"
            )

    return orphans, pair_count


def test_every_pg_constant_has_sqlite_sibling_or_pg_only_marker():
    orphans, _pair_count = _scan_db_dialect_pairs()
    assert not orphans, "Unmarked Postgres-only SQL constants:\n" + "\n".join(orphans)


def test_dialect_pair_count_ratchet():
    _orphans, pair_count = _scan_db_dialect_pairs()
    assert pair_count <= ALLOWED_MAX, (
        f"Dual-SQL pair count grew to {pair_count} (ALLOWED_MAX={ALLOWED_MAX}). "
        "Prefer consolidating dialects or mark true Postgres-only SQL with # pg-only. "
        "Only raise ALLOWED_MAX deliberately after review."
    )
    # When pair_count drops below ALLOWED_MAX, lower ALLOWED_MAX in the same PR
    # so the baseline tracks the real surface (optional but preferred).
