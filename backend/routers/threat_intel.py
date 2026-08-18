"""Threat-intel malicious-domain-candidates export API.

Public, token-gated, rate-limited endpoints for DNS-blocklist operators.
Fails closed: when THREAT_INTEL_TOKEN is unset the endpoints return HTTP 503;
an invalid/missing token returns HTTP 401; the rate limit returns HTTP 429.

Query ``mode`` on TXT/CSV exports:
- ``domains`` (default) — canonical domain per line / domain-eligible CSV rows
- ``urls`` — exact malicious URLs (including on classified shared hosts)
- ``all`` — domain + URL eligible rows (CSV only; TXT treats as domains)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from blocklist.build import build_blocklist
from blocklist.serialize import normalize_export_mode, to_csv, to_json, to_txt
from database import get_db
from dependencies import require_threat_intel_token
from rate_limit import rate_limit_threat_intel

router = APIRouter(
    prefix="/api/threat-intel",
    tags=["threat-intel"],
    dependencies=[
        Depends(rate_limit_threat_intel),
        Depends(require_threat_intel_token),
    ],
)


async def _build_payload():
    db = await get_db()
    try:
        return await build_blocklist(db)
    finally:
        await db.close()


def _parse_mode(mode: str | None, *, allow_all: bool = True) -> str:
    try:
        parsed = normalize_export_mode(mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not allow_all and parsed == "all":
        raise HTTPException(400, "mode must be domains or urls for TXT export")
    return parsed


@router.get(
    "/blocklist.txt",
    response_class=PlainTextResponse,
    summary="Malicious-domain candidates (TXT)",
)
async def blocklist_txt(mode: str | None = Query(default="domains")):
    """TXT export — one line per domain (default) or per exact URL."""
    export_mode = _parse_mode(mode, allow_all=False)
    payload = await _build_payload()
    suffix = "urls" if export_mode == "urls" else "domains"
    return PlainTextResponse(
        to_txt(payload, mode=export_mode),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="briefr-blocklist-{suffix}.txt"',
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/blocklist.json",
    response_class=JSONResponse,
    summary="Malicious-domain candidates (JSON, with audit reasons)",
)
async def blocklist_json():
    """Full structured payload: eligible candidates plus excluded domains with
    their reasons, and the exact eligibility criteria."""
    payload = await _build_payload()
    return JSONResponse(to_json(payload), headers={"Cache-Control": "no-store"})


@router.get(
    "/blocklist.csv",
    response_class=Response,
    summary="Malicious-domain candidates (CSV, analyst-friendly rows)",
)
async def blocklist_csv(mode: str | None = Query(default="all")):
    """CSV rows filtered by export mode (default ``all`` eligible rows)."""
    export_mode = _parse_mode(mode)
    payload = await _build_payload()
    return Response(
        to_csv(payload, mode=export_mode),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="briefr-blocklist-{export_mode}.csv"',
            "Cache-Control": "no-store",
        },
    )
