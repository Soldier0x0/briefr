"""Stack Tier-A backfill runs / checkpoints / ETA (Q4)."""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any

from db.config import is_postgres
from db.types import DbConnection

logger = logging.getLogger(__name__)

DEFAULT_MAX_PRODUCTS = 10
DEFAULT_MAX_CVES = 5000
DEFAULT_MAX_RUNTIME = 3600
COVERAGE_MIN_PER_PRODUCT = 3
EST_CVES_PER_PRODUCT = 400
NVD_PAGE_SIZE = 2000


def _row0(rows: list[Any] | None) -> Any | None:
    if not rows:
        return None
    return rows[0]


def _as_dict(row: Any) -> dict:
    try:
        return dict(row)
    except Exception:
        return {}


def stack_backfill_enabled() -> bool:
    raw = os.environ.get("STACK_BACKFILL_ENABLED", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _paced_seconds() -> float:
    if os.environ.get("NVD_API_KEY", "").strip():
        return 60.0 / 50.0
    return 60.0 / 5.0


def estimate_eta(products: list[dict[str, Any]]) -> dict[str, Any]:
    """Preflight ETA range for Tier A (NVD pages + EPSS/KEV constants)."""
    n = max(0, len(products))
    nvd_calls = sum(
        max(1, math.ceil(EST_CVES_PER_PRODUCT / NVD_PAGE_SIZE)) for _ in range(n)
    )
    paced = _paced_seconds()
    nvd_eta = nvd_calls * paced
    epss_eta = 30.0
    kev_eta = 15.0
    low = int(nvd_eta * 0.7 + epss_eta + kev_eta)
    high = int(nvd_eta * 1.4 + epss_eta + kev_eta)
    return {
        "products": n,
        "nvd_calls_est": nvd_calls,
        "paced_seconds": paced,
        "has_nvd_key": bool(os.environ.get("NVD_API_KEY", "").strip()),
        "eta_low_seconds": low,
        "eta_high_seconds": high,
        "notes": "Tier A = NVD catalog pages + EPSS bulk + KEV flags. Deep intel stays on background jobs.",
    }


def products_from_profile(profile: dict | None, stack_terms: str) -> list[dict[str, Any]]:
    """Normalize stack inventory into backfill product rows."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(vendor: str, product: str, version: str = "", category: str = "app") -> None:
        product = (product or "").strip()
        if not product:
            return
        vendor = (vendor or "").strip()
        key = f"{vendor.lower()}::{product.lower()}"
        if key in seen:
            return
        seen.add(key)
        out.append(
            {
                "product_key": key,
                "vendor": vendor,
                "product": product,
                "version": (version or "").strip(),
                "category": category,
            }
        )

    if isinstance(profile, dict):
        for row in profile.get("operatingSystems") or []:
            if isinstance(row, dict):
                _add(row.get("vendor") or "", row.get("product") or "", row.get("version") or "", "os")
        for row in profile.get("applications") or []:
            if isinstance(row, dict):
                prod = row.get("cpeProduct") or row.get("product") or ""
                _add(row.get("vendor") or "", prod, row.get("version") or "", "app")
    for term in (stack_terms or "").split(","):
        term = term.strip()
        if term:
            _add("", term, "", "app")
    return out


async def count_corpus_hits(db: DbConnection, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-product CVE hit counts (shallow coverage signal)."""
    results = []
    for p in products:
        needle = (p.get("product") or "").strip().lower()
        if len(needle) < 2:
            results.append({**p, "hit_count": 0, "shallow": True})
            continue
        like = f"%{needle}%"
        # Stop early once we know coverage clears the shallow threshold.
        limit = COVERAGE_MIN_PER_PRODUCT
        if is_postgres():
            rows = await db.execute_fetchall(
                """
                SELECT COUNT(*)::int AS n FROM (
                    SELECT 1 FROM cves
                    WHERE lower(affected_products) LIKE $1
                       OR lower(description) LIKE $1
                    LIMIT $2
                ) AS sample
                """,
                (like, limit),
            )
        else:
            rows = await db.execute_fetchall(
                """
                SELECT COUNT(*) AS n FROM (
                    SELECT 1 FROM cves
                    WHERE lower(affected_products) LIKE ?
                       OR lower(description) LIKE ?
                    LIMIT ?
                )
                """,
                (like, like, limit),
            )
        n = 0
        row = _row0(rows)
        if row is not None:
            try:
                n = int(_as_dict(row).get("n") or 0)
            except Exception:
                n = int(row[0] or 0)
        results.append(
            {
                **p,
                "hit_count": n,
                "shallow": n < COVERAGE_MIN_PER_PRODUCT,
            }
        )
    return results


async def create_run(
    db: DbConnection,
    *,
    user_id: int,
    products: list[dict[str, Any]],
    eta: dict[str, Any],
) -> int:
    max_products = int(os.environ.get("STACK_BACKFILL_MAX_PRODUCTS", str(DEFAULT_MAX_PRODUCTS)))
    max_cves = int(os.environ.get("STACK_BACKFILL_MAX_CVES", str(DEFAULT_MAX_CVES)))
    max_runtime = int(os.environ.get("STACK_BACKFILL_MAX_RUNTIME_SECONDS", str(DEFAULT_MAX_RUNTIME)))
    capped = products[: max(1, max_products)]
    now = datetime.now(timezone.utc)
    ts: Any = now if is_postgres() else now.replace(tzinfo=None).isoformat(sep=" ")
    products_json = json.dumps(capped)
    if is_postgres():
        rows = await db.execute_fetchall(
            """
            INSERT INTO stack_backfill_runs (
                user_id, status, products_json, max_products, max_cves, max_runtime_seconds,
                eta_low_seconds, eta_high_seconds, pages_total, progress_message,
                created_at, updated_at
            ) VALUES (
                $1, 'pending', $2, $3, $4, $5, $6, $7, $8, $9, $10, $10
            )
            RETURNING id
            """,
            (
                user_id,
                products_json,
                max_products,
                max_cves,
                max_runtime,
                eta.get("eta_low_seconds"),
                eta.get("eta_high_seconds"),
                len(capped),
                "Queued Tier A backfill…",
                ts,
            ),
        )
        row = _row0(rows)
        run_id = int(_as_dict(row).get("id") if row is not None else 0)
        if not run_id and row is not None:
            run_id = int(row[0])
    else:
        await db.execute(
            """
            INSERT INTO stack_backfill_runs (
                user_id, status, products_json, max_products, max_cves, max_runtime_seconds,
                eta_low_seconds, eta_high_seconds, pages_total, progress_message,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                "pending",
                products_json,
                max_products,
                max_cves,
                max_runtime,
                eta.get("eta_low_seconds"),
                eta.get("eta_high_seconds"),
                len(capped),
                "Queued Tier A backfill…",
                ts,
                ts,
            ),
        )
        id_rows = await db.execute_fetchall("SELECT last_insert_rowid() AS id")
        row = _row0(id_rows)
        run_id = int(_as_dict(row).get("id") if row is not None else 0)
        if not run_id and row is not None:
            run_id = int(row[0])
    for p in capped:
        await upsert_checkpoint(
            db,
            run_id=run_id,
            product_key=p["product_key"],
            vendor=p.get("vendor"),
            product=p["product"],
            version=p.get("version"),
            status="pending",
        )
    return run_id


async def upsert_checkpoint(
    db: DbConnection,
    *,
    run_id: int,
    product_key: str,
    vendor: str | None,
    product: str,
    version: str | None = None,
    status: str = "pending",
    start_index: int = 0,
    total_results: int = 0,
    cves_upserted: int = 0,
    last_error: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    ts: Any = now if is_postgres() else now.replace(tzinfo=None).isoformat(sep=" ")
    if is_postgres():
        await db.execute(
            """
            INSERT INTO stack_backfill_checkpoints (
                run_id, product_key, vendor, product, version, status,
                start_index, total_results, cves_upserted, last_error, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (run_id, product_key) DO UPDATE SET
                status = EXCLUDED.status,
                start_index = EXCLUDED.start_index,
                total_results = EXCLUDED.total_results,
                cves_upserted = EXCLUDED.cves_upserted,
                last_error = EXCLUDED.last_error,
                updated_at = EXCLUDED.updated_at
            """,
            (
                run_id, product_key, vendor, product, version, status,
                start_index, total_results, cves_upserted, last_error, ts,
            ),
        )
    else:
        await db.execute(
            """
            INSERT INTO stack_backfill_checkpoints (
                run_id, product_key, vendor, product, version, status,
                start_index, total_results, cves_upserted, last_error, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id, product_key) DO UPDATE SET
                status = excluded.status,
                start_index = excluded.start_index,
                total_results = excluded.total_results,
                cves_upserted = excluded.cves_upserted,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (
                run_id, product_key, vendor, product, version, status,
                start_index, total_results, cves_upserted, last_error, ts,
            ),
        )


async def get_run(db: DbConnection, run_id: int, *, user_id: int | None = None) -> dict | None:
    if is_postgres():
        if user_id is not None:
            rows = await db.execute_fetchall(
                "SELECT * FROM stack_backfill_runs WHERE id = $1 AND user_id = $2",
                (run_id, user_id),
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT * FROM stack_backfill_runs WHERE id = $1",
                (run_id,),
            )
    else:
        if user_id is not None:
            rows = await db.execute_fetchall(
                "SELECT * FROM stack_backfill_runs WHERE id = ? AND user_id = ?",
                (run_id, user_id),
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT * FROM stack_backfill_runs WHERE id = ?",
                (run_id,),
            )
    row = _row0(rows)
    if not row:
        return None
    d = _as_dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    try:
        d["products"] = json.loads(d.get("products_json") or "[]")
    except Exception:
        d["products"] = []
    return d


async def list_checkpoints(db: DbConnection, run_id: int) -> list[dict]:
    if is_postgres():
        rows = await db.execute_fetchall(
            "SELECT * FROM stack_backfill_checkpoints WHERE run_id = $1 ORDER BY id",
            (run_id,),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT * FROM stack_backfill_checkpoints WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
    out = []
    for row in rows or []:
        d = dict(row)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        out.append(d)
    return out


async def update_run(
    db: DbConnection,
    run_id: int,
    **fields: Any,
) -> None:
    if not fields:
        return
    now = datetime.now(timezone.utc)
    fields["updated_at"] = now if is_postgres() else now.replace(tzinfo=None).isoformat(sep=" ")
    cols = list(fields.keys())
    if is_postgres():
        sets = ", ".join(f"{c} = ${i+2}" for i, c in enumerate(cols))
        await db.execute(
            f"UPDATE stack_backfill_runs SET {sets} WHERE id = $1",
            (run_id, *[fields[c] for c in cols]),
        )
    else:
        sets = ", ".join(f"{c} = ?" for c in cols)
        await db.execute(
            f"UPDATE stack_backfill_runs SET {sets} WHERE id = ?",
            (*[fields[c] for c in cols], run_id),
        )


async def next_pending_checkpoint(db: DbConnection, run_id: int) -> dict | None:
    if is_postgres():
        rows = await db.execute_fetchall(
            """
            SELECT * FROM stack_backfill_checkpoints
            WHERE run_id = $1 AND status IN ('pending', 'running', 'deferred', 'on_hold')
            ORDER BY id LIMIT 1
            """,
            (run_id,),
        )
    else:
        rows = await db.execute_fetchall(
            """
            SELECT * FROM stack_backfill_checkpoints
            WHERE run_id = ? AND status IN ('pending', 'running', 'deferred', 'on_hold')
            ORDER BY id LIMIT 1
            """,
            (run_id,),
        )
    row = _row0(rows)
    return _as_dict(row) if row else None
