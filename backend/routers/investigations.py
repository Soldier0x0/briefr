"""Session-gated investigation graph APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database import get_db
from dependencies import require_user
from investigations.contracts import (
    EdgeClass,
    GraphNode,
    GraphPage,
    KnowledgeState,
    RelationshipFilters,
    make_node_id,
)
from investigations.projection import expand_relationships, get_entity
from investigations.resolve import is_resolve_root_entity_type, resolve_entity

router = APIRouter()


def _entity_to_graph_node(ref) -> GraphNode:
    return GraphNode(
        node_id=make_node_id(ref.entity_type, ref.entity_id),
        entity_type=ref.entity_type,
        entity_id=ref.entity_id,
        label=ref.label,
        knowledge_state=KnowledgeState.KNOWN,
    )


def _validate_entity_type(entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    if not is_resolve_root_entity_type(normalized):
        raise HTTPException(status_code=422, detail=f"Invalid entity_type: {entity_type}")
    return normalized


@router.get("/api/investigations/resolve")
async def investigations_resolve(
    q: str = Query(..., min_length=1, max_length=512),
    _payload: dict = Depends(require_user),
):
    db = await get_db()
    try:
        try:
            ref = await resolve_entity(db, q)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if ref is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "unknown entity", "knowledge_state": "unknown"},
            )
        return {
            "root": _entity_to_graph_node(ref).model_dump(mode="json"),
            "query": ref.entity_id if ref.entity_type == "cve" else q.strip(),
        }
    finally:
        await db.close()


@router.get("/api/investigations/entities/{entity_type}/{entity_id}")
async def investigations_entity(
    entity_type: str,
    entity_id: str,
    _payload: dict = Depends(require_user),
):
    normalized_type = _validate_entity_type(entity_type)
    db = await get_db()
    try:
        ref = await get_entity(db, normalized_type, entity_id)
        if ref is None:
            raise HTTPException(status_code=404, detail="unknown entity")
        return _entity_to_graph_node(ref).model_dump(mode="json")
    finally:
        await db.close()


@router.get("/api/investigations/entities/{entity_type}/{entity_id}/relationships")
async def investigations_relationships(
    entity_type: str,
    entity_id: str,
    depth: int = Query(default=1, ge=1, le=2),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    edge_class: EdgeClass | None = Query(default=None),
    min_confidence: str | None = Query(default=None),
    include_semantic: bool = Query(default=False),
    include_stale: bool = Query(default=False),
    _payload: dict = Depends(require_user),
) -> dict:
    normalized_type = _validate_entity_type(entity_type)
    db = await get_db()
    try:
        ref = await get_entity(db, normalized_type, entity_id)
        if ref is None:
            raise HTTPException(status_code=404, detail="unknown entity")
        filters = RelationshipFilters(
            depth=depth,
            limit=limit,
            cursor=cursor,
            edge_class=edge_class,
            min_confidence=min_confidence,
            include_semantic=include_semantic,
            include_stale=include_stale,
        )
        page: GraphPage = await expand_relationships(db, ref, filters)
        return page.model_dump(mode="json")
    finally:
        await db.close()
