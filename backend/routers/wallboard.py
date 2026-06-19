"""Wallboard read-only API (Beta V1.4 Theme 4).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from fastapi import APIRouter, Depends

from dependencies import require_wallboard_token
from rate_limit import rate_limit_wallboard
from wallboard.service import get_wallboard_payload

router = APIRouter(
    dependencies=[Depends(rate_limit_wallboard), Depends(require_wallboard_token)],
)


@router.get("/api/wallboard")
async def wallboard():
    """Aggregated intel posture payload for kiosk / TV displays."""
    return await get_wallboard_payload()
