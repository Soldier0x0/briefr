"""IOC lookup + OTX pulse IOC endpoints, moved verbatim from main.py
(V1.2 §5.2 router split, phase 2). The two inline imports
(`greynoise_for_ip`, `lookup_otx_for_ioc`) were hoisted to module top per
house convention. One robustness fix on top of the verbatim move (review
finding on PR #95): the cached-hit path now commits, so the feed_cache
writes made by on-demand GreyNoise/OTX enrichment are no longer rolled
back on connection close.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_db, get_ioc_cache, set_ioc_cache
from db.ioc_watchlist import (
    delete_ioc_watchlist_entry,
    list_ioc_watchlist,
    upsert_ioc_watchlist_entry,
)
from dependencies import require_user
from rate_limit import rate_limit_ioc
from enrichment.ioc import lookup_ioc, normalize_ioc_value
from feeds.extended import greynoise_for_ip
from feeds.otx import load_pulse_iocs, lookup_otx_for_ioc, top_pulse_ipv4s
from templates.intelligence import greynoise_sentence, otx_sentence

router = APIRouter()


class IocLookupRequest(BaseModel):
    value: str
    type: str
    greynoise: bool = False


class IocWatchlistBody(BaseModel):
    value: str = Field(min_length=1, max_length=512)
    type: str
    label: str = Field(default="", max_length=200)


@router.get("/api/otx/pulses/{pulse_id}/iocs")
async def get_otx_pulse_iocs(
    pulse_id: str,
    limit: int = Query(default=10, ge=1, le=50),
):
    otx_key = os.environ.get("OTX_API_KEY", "")
    if not otx_key:
        raise HTTPException(status_code=503, detail="OTX_API_KEY not configured")

    db = await get_db()
    try:
        iocs = await load_pulse_iocs(db, pulse_id, otx_key)
        ips = await top_pulse_ipv4s(db, pulse_id, otx_key, limit=3)
        await db.commit()
    finally:
        await db.close()

    indicators: list[dict[str, str]] = []
    for ip in ips:
        indicators.append({"type": "ip", "value": ip})
    for row in iocs:
        ioc_t = (row.get("ioc_type") or "").upper()
        val = row.get("ioc_value") or ""
        if not val:
            continue
        if ioc_t in ("IPV4", "IPV6"):
            mapped = "ip"
        elif ioc_t in ("DOMAIN", "HOSTNAME"):
            mapped = "domain"
        elif ioc_t.startswith("FILE_HASH") or ioc_t == "FILE":
            mapped = "hash"
        else:
            continue
        entry = {"type": mapped, "value": val}
        if entry not in indicators:
            indicators.append(entry)
        if len(indicators) >= limit:
            break

    return {"data": {"iocs": iocs, "ips": ips, "indicators": indicators[:limit]}}


@router.post("/api/ioc/lookup", dependencies=[Depends(rate_limit_ioc)])
async def ioc_lookup(body: IocLookupRequest):
    value = body.value.strip()
    ioc_type = body.type.strip().lower()

    if not value:
        raise HTTPException(status_code=400, detail="value is required")
    if ioc_type not in ("ip", "hash", "domain"):
        raise HTTPException(status_code=400, detail="type must be ip, hash, or domain")
    if len(value) > 512:
        raise HTTPException(status_code=400, detail="value too long")

    vt_key = os.environ.get("VIRUSTOTAL_API_KEY", "")
    abuse_key = os.environ.get("ABUSEIPDB_API_KEY", "")
    greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
    abusech_key = os.environ.get("ABUSECH_AUTH_KEY", "")
    otx_key = os.environ.get("OTX_API_KEY", "")

    db = await get_db()
    try:
        cached = await get_ioc_cache(db, value)
        if cached is not None:
            cached["cached"] = True
            if ioc_type == "ip" and body.greynoise and greynoise_key:
                gn = await greynoise_for_ip(db, value, greynoise_key)
                cached["greynoise"] = gn
                cached["greynoise_sentence"] = greynoise_sentence(gn)
            elif ioc_type == "ip":
                cached["greynoise"] = None
                cached["greynoise_sentence"] = None
            if otx_key:
                otx = await lookup_otx_for_ioc(db, value, ioc_type, otx_key)
                cached["otx"] = otx
                cached["otx_sentence"] = otx_sentence(otx)
            # Persist the feed_cache rows written by the enrichment calls
            # above; without this they roll back on close and every cached
            # hit re-spends GreyNoise/OTX quota.
            await db.commit()
            return cached

        result = await lookup_ioc(
            value,
            ioc_type,
            vt_key,
            abuse_key,
            greynoise_key,
            abusech_key,
            db=db,
            include_greynoise=body.greynoise,
            otx_key=otx_key,
        )
        result["cached"] = False

        if result.get("error") == "Invalid domain format":
            raise HTTPException(status_code=422, detail=result["error"])

        await set_ioc_cache(db, value, ioc_type, result)
        await db.commit()
    finally:
        await db.close()

    return result


@router.get("/api/ioc/watchlist")
async def get_ioc_watchlist(payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        items = await list_ioc_watchlist(db, int(payload["sub"]))
    finally:
        await db.close()
    return {"items": items}


@router.post("/api/ioc/watchlist")
async def post_ioc_watchlist(body: IocWatchlistBody, payload: dict = Depends(require_user)):
    ioc_type = body.type.strip().lower()
    if ioc_type not in ("ip", "hash", "domain"):
        raise HTTPException(400, "type must be ip, hash, or domain")
    normalized = normalize_ioc_value(body.value.strip(), ioc_type)
    if not normalized:
        raise HTTPException(400, "value is required")

    db = await get_db()
    try:
        try:
            item = await upsert_ioc_watchlist_entry(
                db,
                int(payload["sub"]),
                ioc_type,
                normalized,
                label=body.label.strip(),
            )
            await db.commit()
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    finally:
        await db.close()
    return {"item": item}


@router.delete("/api/ioc/watchlist/{entry_id}")
async def delete_ioc_watchlist(entry_id: int, payload: dict = Depends(require_user)):
    db = await get_db()
    try:
        deleted = await delete_ioc_watchlist_entry(db, int(payload["sub"]), entry_id)
        if not deleted:
            raise HTTPException(404, "Watchlist entry not found")
        await db.commit()
    finally:
        await db.close()
    return {"deleted": True, "id": entry_id}
