"""Admin dashboard API — threat-intel blocklist management.

Infrastructure-classification CRUD operates against app.infra_classifications,
every mutation is audited, and exports are admin-session only (download from
the Threat-intel admin page and share manually).

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.
"""

from __future__ import annotations

from fastapi import HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from blocklist.build import build_blocklist
from blocklist.classify import canonical_host
from blocklist.infra_seed import CLASSIFICATIONS, EXCLUSION_CLASSIFICATIONS
from blocklist.serialize import normalize_export_mode, to_csv, to_json, to_txt
from database import get_db
from db.blocklist import (
    delete_infra_classification,
    fetch_infra_classifications,
    insert_infra_classification,
    update_infra_classification,
)
from dependencies import audit

from .router import router


@router.get("/threat-intel/status")
async def threat_intel_status():
    """Export status for the admin Threat-intel page."""
    db = await get_db()
    try:
        payload = await build_blocklist(db)
        infra_rows = await fetch_infra_classifications(db)
    finally:
        await db.close()

    genuine_host_count = sum(
        1
        for row in infra_rows
        if int(row.get("enabled") or 0)
        and (row.get("classification") or "") in EXCLUSION_CLASSIFICATIONS
    )
    meta = payload["meta"]
    return {
        "candidate_count": meta["candidate_count"],
        "eligible_count": meta["eligible_count"],
        "eligible_domain_count": meta.get("eligible_domain_count", 0),
        "eligible_url_count": meta.get("eligible_url_count", 0),
        "excluded_count": meta["excluded_count"],
        "genuine_host_count": genuine_host_count,
        "infra_classification_count": len(infra_rows),
        "generated_at": meta["generated_at"],
        "export_formats": [
            {
                "id": "txt",
                "label": "TXT",
                "description": "One value per line — DNS blocklists and simple deny lists.",
            },
            {
                "id": "csv",
                "label": "CSV",
                "description": "Spreadsheet rows with type, value, source, confidence, and timestamps.",
            },
            {
                "id": "json",
                "label": "JSON",
                "description": "Full audit payload including excluded candidates and evidence.",
            },
        ],
        "export_content_modes": [
            {
                "id": "domains",
                "label": "Domains only",
                "description": (
                    "Canonical malicious domains minus Tranco/curated genuine hosts. "
                    "Best for DNS deny lists."
                ),
            },
            {
                "id": "urls",
                "label": "Exact URLs only",
                "description": (
                    "Full malicious URIs, including paths on shared infrastructure "
                    "(e.g. drive.google.com/…). Genuine list does not apply."
                ),
            },
            {
                "id": "all",
                "label": "All eligible rows",
                "description": "Domain + URL rows in one CSV export (not available for TXT).",
            },
        ],
    }


def _admin_export_mode(mode: str | None, *, allow_all: bool = True) -> str:
    try:
        parsed = normalize_export_mode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not allow_all and parsed == "all":
        raise HTTPException(status_code=400, detail="mode must be domains or urls for TXT export")
    return parsed


@router.get("/threat-intel/blocklist.txt")
async def admin_blocklist_txt(mode: str | None = Query(default="domains")):
    """Admin-authorized TXT export."""
    export_mode = _admin_export_mode(mode, allow_all=False)
    db = await get_db()
    try:
        payload = await build_blocklist(db)
    finally:
        await db.close()
    suffix = "urls" if export_mode == "urls" else "domains"
    return PlainTextResponse(
        to_txt(payload, mode=export_mode),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="briefr-blocklist-{suffix}.txt"'},
    )


@router.get("/threat-intel/blocklist.json")
async def admin_blocklist_json():
    """Admin-authorized JSON export (full audit trail)."""
    db = await get_db()
    try:
        payload = await build_blocklist(db)
    finally:
        await db.close()
    return JSONResponse(to_json(payload))


@router.get("/threat-intel/blocklist.csv")
async def admin_blocklist_csv(mode: str | None = Query(default="all")):
    """Admin-authorized CSV export."""
    export_mode = _admin_export_mode(mode)
    db = await get_db()
    try:
        payload = await build_blocklist(db)
    finally:
        await db.close()
    return Response(
        to_csv(payload, mode=export_mode),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="briefr-blocklist-{export_mode}.csv"'},
    )


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
