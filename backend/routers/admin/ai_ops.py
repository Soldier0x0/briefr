"""Admin dashboard API — AI operations and retrieval health.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

from fastapi import Query, Request

from .router import router

@router.get("/ai/operations/models")
async def get_ai_operations_models(request: Request):
    from ai.operations_admin import build_models_payload

    return build_models_payload()


@router.get("/ai/operations/overview")
async def get_ai_operations_overview(request: Request):
    from ai.operations_admin import build_overview_payload
    from database import (
        ai_operations_usage_since,
        count_ai_operations,
        count_cve_embeddings,
        get_db,
    )
    from db.embeddings_store import count_embeddings_by_entity
    from ml.embeddings import get_embeddings_model_name

    db = await get_db()
    try:
        usage_24h = await ai_operations_usage_since(db, hours=24)
        usage_7d = await ai_operations_usage_since(db, hours=24 * 7)
        total = await count_ai_operations(db)
        live_counts = await count_embeddings_by_entity(db, get_embeddings_model_name())
        legacy_count = await count_cve_embeddings(db)
    finally:
        await db.close()

    return build_overview_payload(
        usage_24h=usage_24h,
        usage_7d=usage_7d,
        total_operations=total,
        embeddings_vector_count=int(live_counts.get("total") or 0),
        legacy_cve_embeddings=legacy_count,
        embeddings_counts=live_counts,
    )


@router.get("/retrieval/health")
async def get_retrieval_health(request: Request):
    """Ops honesty for the live embeddings / hybrid retrieval index."""
    from database import get_db
    from services.retrieval_health import build_retrieval_health

    db = await get_db()
    try:
        return await build_retrieval_health(db)
    finally:
        await db.close()


@router.get("/ai/operations/providers")
async def get_ai_operations_providers(request: Request):
    from ai.operations_admin import build_providers_payload

    return build_providers_payload()


@router.get("/ai/operations/activity")
async def get_ai_operations_activity(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    task_class: str | None = Query(None),
    provider: str | None = Query(None),
):
    from database import get_db, list_ai_operations_page

    db = await get_db()
    try:
        rows, total = await list_ai_operations_page(
            db,
            limit=limit,
            offset=offset,
            task_class=task_class,
            provider=provider,
        )
    finally:
        await db.close()

    return {
        "rows": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }

