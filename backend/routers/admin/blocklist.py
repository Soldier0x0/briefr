"""Admin dashboard API — threat-intel blocklist management.

Infrastructure-classification CRUD operates against app.infra_classifications,
every mutation is audited, and the admin may fetch the same export payload the
public token-gated endpoints serve (no export token needed here — admin auth
already gates the shared /api/admin router).

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from blocklist.build import build_blocklist
from blocklist.classify import canonical_host
from blocklist.infra_seed import CLASSIFICATIONS
from blocklist.serialize import to_json, to_txt
from database import get_db
from db.blocklist import (
    delete_infra_classification,
    fetch_infra_classifications,
    insert_infra_classification,
    update_infra_classification,
)
from dependencies import audit
from settings import settings

from .router import router


@router.get("/threat-intel/status")
async def threat_intel_status():
    """Export status: token configured, rate limit, publish URLs."""
    db = await get_db()
    try:
        from blocklist.build import build_blocklist

        payload = await build_blocklist(db)
        candidate_count = payload["meta"]["candidate_count"]
    finally:
        await db.close()
    return {
        "token_configured": bool(settings.threat_intel_token),
        "rate_limit_per_minute": settings.rate_limit_threat_intel_per_minute,
        "candidate_count": candidate_count,
        "eligible_count": payload["meta"]["eligible_count"],
        "excluded_count": payload["meta"]["excluded_count"],
        "generated_at": payload["meta"]["generated_at"],
        "publish_urls": {
            "txt": "/api/threat-intel/blocklist.txt",
            "json": "/api/threat-intel/blocklist.json",
        },
    }


@router.get("/threat-intel/blocklist.txt")
async def admin_blocklist_txt():
    """Admin-authorized TXT export (no export token required)."""
    db = await get_db()
    try:
        payload = await build_blocklist(db)
    finally:
        await db.close()
    return PlainTextResponse(
        to_txt(payload),
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="briefr-blocklist.txt"'},
    )


@router.get("/threat-intel/blocklist.json")
async def admin_blocklist_json():
    """Admin-authorized JSON export (no export token required)."""
    db = await get_db()
    try:
        payload = await build_blocklist(db)
    finally:
        await db.close()
    return JSONResponse(to_json(payload))


@router.get("/infra-classifications")
async def list_infra_classifications():
    db = await get_db()
    try:
        rows = await fetch_infra_classifications(db)
    finally:
        await db.close()
    rows.sort(key=lambda r: (r.get("host") or ""))
    return {"data": rows}


def _validate_classification(classification: str) -> str:
    if not isinstance(classification, str):
        raise HTTPException(
            status_code=400,
            detail=(
                f"classification must be one of: "
                f"{', '.join(sorted(CLASSIFICATIONS))}"
            ),
        )
    classification = classification.strip().upper()
    if classification not in CLASSIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"classification must be one of: "
                f"{', '.join(sorted(CLASSIFICATIONS))}"
            ),
        )
    return classification


def _bool_int(value) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int) and value in (0, 1):
        return value
    if isinstance(value, str) and value.strip().lower() in ("1", "0", "true", "false"):
        return 1 if value.strip().lower() in ("1", "true") else 0
    raise HTTPException(status_code=400, detail="enabled must be 0 or 1")


@router.post("/infra-classifications")
async def create_infra_classification(body: dict, request: Request):
    host = canonical_host(body.get("host") or "")
    if not host or "." not in host:
        raise HTTPException(status_code=400, detail="host must be a valid domain")
    classification = _validate_classification(body.get("classification") or "")
    enabled = _bool_int(body.get("enabled", 1))
    provenance = str(body.get("provenance") or "").strip()[:200]
    reason = str(body.get("reason") or "").strip()[:500]
    notes = str(body.get("notes") or "").strip()[:1000]

    db = await get_db()
    try:
        try:
            row = await insert_infra_classification(
                db,
                host=host,
                classification=classification,
                enabled=enabled,
                provenance=provenance or "admin",
                reason=reason,
                notes=notes,
            )
            await db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        await db.close()
    await audit(
        request,
        "infra_classifications.create",
        host,
        metadata={"classification": classification, "enabled": enabled},
    )
    return row


@router.patch("/infra-classifications/{row_id}")
async def update_infra_classification_route(row_id: int, body: dict, request: Request):
    updates: dict = {}
    if "classification" in body:
        updates["classification"] = _validate_classification(body["classification"])
    if "enabled" in body:
        updates["enabled"] = _bool_int(body["enabled"])
    if "provenance" in body:
        updates["provenance"] = str(body["provenance"]).strip()[:200]
    if "reason" in body:
        updates["reason"] = str(body["reason"]).strip()[:500]
    if "notes" in body:
        updates["notes"] = str(body["notes"]).strip()[:1000]

    db = await get_db()
    try:
        row = await update_infra_classification(db, row_id, **updates)
        await db.commit()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Classification row not found")
    await audit(
        request,
        "infra_classifications.update",
        f"id={row_id}",
        metadata={"changes": sorted(updates)},
    )
    return row


@router.delete("/infra-classifications/{row_id}")
async def delete_infra_classification_route(row_id: int, request: Request):
    db = await get_db()
    try:
        ok = await delete_infra_classification(db, row_id)
        await db.commit()
    finally:
        await db.close()
    if not ok:
        raise HTTPException(status_code=404, detail="Classification row not found")
    await audit(request, "infra_classifications.delete", f"id={row_id}")
    return {"ok": True}
