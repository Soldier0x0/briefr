"""Frozen graph contracts for investigation APIs (P0)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESOLVE_ROOT_ENTITY_TYPES = frozenset({"cve", "ioc", "technique", "campaign"})
GRAPH_ENTITY_TYPES = RESOLVE_ROOT_ENTITY_TYPES | {"publication"}


class EntityType(StrEnum):
    CVE = "cve"
    IOC = "ioc"
    TECHNIQUE = "technique"
    CAMPAIGN = "campaign"
    SIGMA_RULE = "sigma_rule"
    PUBLICATION = "publication"


class IocKind(StrEnum):
    IP = "ip"
    HASH = "hash"
    DOMAIN = "domain"
    URL = "url"


class EdgeClass(StrEnum):
    DIRECT_FACT = "direct_fact"
    REPORTED = "reported"
    DERIVED = "derived"
    ANALYST_ASSERTION = "analyst_assertion"
    SEMANTIC = "semantic"


class KnowledgeState(StrEnum):
    KNOWN = "known"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    STALE = "stale"


def make_node_id(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def make_edge_id(
    source_node_id: str,
    target_node_id: str,
    edge_class: EdgeClass | str,
    source_key: str,
) -> str:
    return f"{source_node_id}|{target_node_id}|{edge_class}|{source_key}"


class EntityRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_type: str
    entity_id: str
    label: str

    @field_validator("entity_type")
    @classmethod
    def _validate_entity_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("entity_type is required")
        return normalized


class GraphNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    entity_type: str
    entity_id: str
    label: str
    knowledge_state: KnowledgeState


class GraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_class: EdgeClass
    source_key: str
    confidence: str | None = None
    observed_at: str | None = None
    fetched_at: str | None = None


class RelationshipFilters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    depth: int = Field(default=1, ge=1, le=2)
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = None
    edge_class: EdgeClass | None = None
    min_confidence: str | None = None
    include_semantic: bool = False
    include_stale: bool = False


class GraphPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    root: GraphNode
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    source_status: Literal["ok", "degraded"]
    knowledge_state: KnowledgeState
    truncated: bool
    next_cursor: str | None
    generated_at: str
    depth: int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
