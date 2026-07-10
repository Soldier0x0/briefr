"""Database integrity checks — SQLite PRAGMA vs PostgreSQL pg_catalog probes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from db.config import is_postgres


@dataclass
class IntegrityResult:
    ok: bool
    integrity_ok: bool
    foreign_keys_ok: bool
    message: str
    foreign_key_violations: int = 0
    backend: str = "sqlite"
    method: str = "pragma"
    checks: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "integrity_ok": self.integrity_ok,
            "foreign_keys_ok": self.foreign_keys_ok,
            "message": self.message,
            "foreign_key_violations": self.foreign_key_violations,
            "backend": self.backend,
            "method": self.method,
            "checks": self.checks,
        }

    def as_summary(self) -> dict[str, Any]:
        """Lightweight shape for admin /system db_integrity cache."""
        return {
            "ok": self.ok,
            "message": self.message,
            "backend": self.backend,
            "method": self.method,
        }


async def run_integrity_check(db: Any) -> IntegrityResult:
    if is_postgres():
        return await _postgres_integrity(db)
    return await _sqlite_integrity(db)


async def _sqlite_integrity(db: Any) -> IntegrityResult:
    ic_rows = await db.execute_fetchall("PRAGMA integrity_check")
    fk_rows = await db.execute_fetchall("PRAGMA foreign_key_check")
    integrity_ok = bool(
        ic_rows and len(ic_rows) == 1 and ic_rows[0]["integrity_check"].lower() == "ok"
    )
    foreign_keys_ok = len(fk_rows) == 0
    msg = ic_rows[0]["integrity_check"] if ic_rows else "unknown"
    ok = integrity_ok and foreign_keys_ok
    return IntegrityResult(
        ok=ok,
        integrity_ok=integrity_ok,
        foreign_keys_ok=foreign_keys_ok,
        message=msg,
        foreign_key_violations=len(fk_rows),
        backend="sqlite",
        method="pragma",
    )


async def _postgres_integrity(db: Any) -> IntegrityResult:
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    invalid_row = await db.execute_fetchall(
        """
        SELECT COUNT(*) AS cnt
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND NOT i.indisvalid
        """
    )
    invalid_idx = int(invalid_row[0]["cnt"]) if invalid_row else 0
    checks.append({
        "name": "invalid_indexes",
        "passed": invalid_idx == 0,
        "detail": f"{invalid_idx} invalid index(es)",
    })
    if invalid_idx:
        issues.append(f"{invalid_idx} invalid index(es)")

    unvalidated_row = await db.execute_fetchall(
        """
        SELECT COUNT(*) AS cnt
        FROM pg_constraint con
        JOIN pg_namespace n ON n.oid = con.connamespace
        WHERE n.nspname = 'public' AND NOT con.convalidated
        """
    )
    unvalidated = int(unvalidated_row[0]["cnt"]) if unvalidated_row else 0
    checks.append({
        "name": "unvalidated_constraints",
        "passed": unvalidated == 0,
        "detail": f"{unvalidated} unvalidated constraint(s)",
    })
    if unvalidated:
        issues.append(f"{unvalidated} unvalidated constraint(s)")

    fk_violations = await _postgres_fk_violation_count(db)
    checks.append({
        "name": "foreign_key_violations",
        "passed": fk_violations == 0,
        "detail": f"{fk_violations} violation(s)",
    })
    if fk_violations:
        issues.append(f"{fk_violations} FK violation(s)")

    integrity_ok = not issues
    message = "ok" if not issues else "; ".join(issues)
    return IntegrityResult(
        ok=integrity_ok,
        integrity_ok=integrity_ok,
        foreign_keys_ok=fk_violations == 0,
        message=message,
        foreign_key_violations=fk_violations,
        backend="postgresql",
        method="pg_catalog",
        checks=checks,
    )


async def _postgres_fk_violation_count(db: Any) -> int:
    fks = await db.execute_fetchall(
        """
        SELECT
          child.relname AS child_table,
          parent.relname AS parent_table,
          a_child.attname AS child_column,
          a_parent.attname AS parent_column
        FROM pg_constraint con
        JOIN pg_class child ON child.oid = con.conrelid
        JOIN pg_class parent ON parent.oid = con.confrelid
        JOIN pg_namespace n ON n.oid = child.relnamespace
        JOIN pg_attribute a_child
          ON a_child.attrelid = child.oid
         AND a_child.attnum = con.conkey[1]
         AND NOT a_child.attisdropped
        JOIN pg_attribute a_parent
          ON a_parent.attrelid = parent.oid
         AND a_parent.attnum = con.confkey[1]
         AND NOT a_parent.attisdropped
        WHERE con.contype = 'f'
          AND n.nspname = 'public'
          AND array_length(con.conkey, 1) = 1
        """
    )
    total = 0
    for fk in fks or []:
        child = str(fk["child_table"])
        parent = str(fk["parent_table"])
        child_col = str(fk["child_column"])
        parent_col = str(fk["parent_column"])
        sql = (
            f'SELECT COUNT(*) AS cnt FROM "{child}" c '
            f'LEFT JOIN "{parent}" p ON p."{parent_col}" = c."{child_col}" '
            f'WHERE c."{child_col}" IS NOT NULL AND p."{parent_col}" IS NULL'
        )
        try:
            rows = await db.execute_fetchall(sql)
            total += int(rows[0]["cnt"]) if rows else 0
        except Exception:
            total += 1
    return total
