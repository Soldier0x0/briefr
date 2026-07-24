"""Admin dashboard API — shared APIRouter.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dependencies import require_admin
from rate_limit import rate_limit_admin

router = APIRouter(
    prefix="/api/admin",
    dependencies=[Depends(require_admin), Depends(rate_limit_admin)],
)
