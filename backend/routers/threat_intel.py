"""Threat-intel malicious-domain-candidates export API.

Public, token-gated, rate-limited endpoints for DNS-blocklist operators.
Fails closed: when THREAT_INTEL_TOKEN is unset the endpoints return HTTP 503;
an invalid/missing token returns HTTP 401; the rate limit returns HTTP 429.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from blocklist.build import build_blocklist
from blocklist.serialize import to_csv, to_json, to_txt
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


@router.get(
    "/blocklist.txt",
    response_class=PlainTextResponse,
    summary="Malicious-domain candidates (TXT, one domain per line)",
)
async def blocklist_txt():
    """One canonical malicious-domain candidate per line, eligible only."""
    payload = await _build_payload()
    return PlainTextResponse(
        to_txt(payload),
        media_type="text/plain",
        headers={
            "Content-Disposition": 'attachment; filename="briefr-blocklist.txt"',
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
async def blocklist_csv():
    """CSV rows with explicit IOC type and the exact upstream value, alongside
    source/confidence/first_seen/malware/threat_type — for filtering and copy."""
    payload = await _build_payload()
    return Response(
        to_csv(payload),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="briefr-blocklist.csv"',
            "Cache-Control": "no-store",
        },
    )
