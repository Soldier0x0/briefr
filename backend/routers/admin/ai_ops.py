"""Admin dashboard API — AI operations and retrieval health.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel

from ai.llm_router import chat_completion_task
from ai.llm_session import provider_circuit_open
from ai.operations_admin import (
    build_models_payload,
    build_overview_payload,
    build_providers_payload,
)
from database import (
    ai_operations_usage_since,
    count_ai_operations,
    count_cve_embeddings,
    get_ai_operation_payload,
    get_db,
    get_latest_ai_operation_for_context,
    list_ai_operations_page,
)
from db.embeddings_store import count_embeddings_by_entity
from dependencies import audit
from ml.embeddings import get_embeddings_model_name
from services.retrieval_health import build_retrieval_health
from tracking import ai_request_quota_snapshot

from .router import router

_RETRYABLE_TASKS = {"product_extraction", "pdf_summary", "detection_context"}
_RETRY_CONTEXT = "replay"


class RetryRequest(BaseModel):
    force: bool = False


def _parse_payload_messages(messages_json: str) -> list[dict[str, str]]:
    try:
        parsed = json.loads(messages_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Stored payload is invalid JSON") from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=500, detail="Stored payload messages must be a list")
    cleaned: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise HTTPException(status_code=500, detail="Stored payload messages are malformed")
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", ""))
        cleaned.append({"role": role, "content": content})
    return cleaned


def _retryable_task(task_class: str) -> Literal["product_extraction", "pdf_summary", "detection_context"]:
    if task_class not in _RETRYABLE_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Task class '{task_class}' cannot be replayed",
        )
    return cast(Literal["product_extraction", "pdf_summary", "detection_context"], task_class)


@router.get("/ai/operations/models")
async def get_ai_operations_models(request: Request):
    return build_models_payload()


@router.get("/ai/operations/overview")
async def get_ai_operations_overview(request: Request):
    db = await get_db()
    try:
        usage_24h = await ai_operations_usage_since(db, hours=24)
        usage_7d = await ai_operations_usage_since(db, hours=24 * 7)
        total = await count_ai_operations(db)
        live_counts = await count_embeddings_by_entity(db, get_embeddings_model_name())
        legacy_count = await count_cve_embeddings(db)
    finally:
        await db.close()

    ai_quota = await ai_request_quota_snapshot()

    return build_overview_payload(
        usage_24h=usage_24h,
        usage_7d=usage_7d,
        total_operations=total,
        embeddings_vector_count=int(live_counts.get("total") or 0),
        legacy_cve_embeddings=legacy_count,
        embeddings_counts=live_counts,
        ai_quota=ai_quota,
    )


@router.get("/retrieval/health")
async def get_retrieval_health(request: Request):
    """Ops honesty for the live embeddings / hybrid retrieval index."""
    db = await get_db()
    try:
        return await build_retrieval_health(db)
    finally:
        await db.close()


@router.get("/ai/operations/providers")
async def get_ai_operations_providers(request: Request):
    return build_providers_payload()


@router.get("/ai/operations/activity")
async def get_ai_operations_activity(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    task_class: str | None = Query(None),
    provider: str | None = Query(None),
):
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


@router.get("/ai/operations/{operation_id}/payload")
async def get_ai_operation_payload_endpoint(operation_id: str, request: Request):
    db = await get_db()
    try:
        payload = await get_ai_operation_payload(db, operation_id=operation_id)
    finally:
        await db.close()

    if payload is None:
        raise HTTPException(status_code=404, detail="AI operation payload not found")

    return {
        "operation_id": payload["operation_id"],
        "messages": _parse_payload_messages(payload["messages_json"]),
        "response_excerpt": payload.get("response_excerpt"),
        "task_class": payload["task_class"],
        "provider": payload["provider"],
        "model": payload["model"],
        "created_at": payload["created_at"],
    }


@router.post("/ai/operations/{operation_id}/retry")
async def retry_ai_operation(
    operation_id: str,
    request: Request,
    body: RetryRequest | None = None,
):
    force = bool(body.force) if body else False

    db = await get_db()
    try:
        payload = await get_ai_operation_payload(db, operation_id=operation_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="AI operation payload not found")

        if provider_circuit_open(payload["provider"]) and not force:
            await audit(
                request,
                "ai.operations.retry",
                operation_id,
                metadata={"force": False, "blocked": "circuit_open", "provider": payload["provider"]},
            )
            raise HTTPException(
                status_code=409,
                detail="Provider paused - resume retries on Feed Health, or pass force=true",
            )

        replay_before = await get_latest_ai_operation_for_context(
            db,
            context_type=_RETRY_CONTEXT,
            context_id=operation_id,
        )
    finally:
        await db.close()

    task = _retryable_task(payload["task_class"])
    messages = _parse_payload_messages(payload["messages_json"])
    completion = await chat_completion_task(
        task,
        messages=messages,
        context_type=_RETRY_CONTEXT,
        context_id=operation_id,
        ignore_provider_circuit=force,
    )

    db = await get_db()
    try:
        replay_after = await get_latest_ai_operation_for_context(
            db,
            context_type=_RETRY_CONTEXT,
            context_id=operation_id,
        )
    finally:
        await db.close()

    replay_row: dict[str, Any] | None = None
    before_id = int(replay_before["id"]) if replay_before else None
    if replay_after is not None and (before_id is None or int(replay_after["id"]) != before_id):
        replay_row = replay_after

    if replay_row is None:
        raise HTTPException(
            status_code=503,
            detail="Retry did not execute a provider attempt; check provider config and try again",
        )

    response_payload = {
        "replay_operation_id": replay_row["operation_id"],
        "success": bool(replay_row["success"]),
        "provider": replay_row["provider"],
        "model": replay_row["model"],
        "error_class": replay_row.get("error_class"),
    }
    await audit(
        request,
        "ai.operations.retry",
        operation_id,
        metadata={
            "force": force,
            "replay_operation_id": replay_row["operation_id"],
            "success": bool(replay_row["success"]),
            "provider": replay_row["provider"],
            "model": replay_row["model"],
            "error_class": replay_row.get("error_class"),
            "completion_returned": completion is not None,
        },
    )
    return response_payload

