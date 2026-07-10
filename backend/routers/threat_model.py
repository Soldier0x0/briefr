"""Threat model read API (V1.5 Theme 1).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from database import get_db
from threat_model.scenarios import build_threat_scenarios

router = APIRouter()


@router.get("/api/threat-model/scenarios")
async def threat_model_scenarios(
    stack: str | None = Query(
        default=None,
        max_length=500,
        description="Comma-separated stack terms (same matching as /api/cves and Forge)",
    ),
):
    """Stack-scoped ATT&CK threat scenario cards with CVE evidence and mitigation hints."""
    db = await get_db()
    try:
        return await build_threat_scenarios(db, stack)
    finally:
        await db.close()
