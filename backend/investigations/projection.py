"""Bounded SQL projection for investigation graph pages."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from correlation.ioc_normalize import normalize_ioc
from correlation.source_evidence import batch_source_evidence
from db.cve import get_related_cves
from db.ioc_digest import ioc_value_digest
from investigations.contracts import (
    EdgeClass,
    EntityRef,
    GraphEdge,
    GraphNode,
    GraphPage,
    KnowledgeState,
    RelationshipFilters,
    make_edge_id,
    make_node_id,
    utc_now_iso,
)
from investigations.resolve import (
    _mirror_ioc_type,
    is_valid_cve_id,
    is_valid_technique_id,
)

logger = logging.getLogger(__name__)

_SIGMA_SOURCE = "sigmahq"
_MAX_FRONTIER = 25
_MAX_CANDIDATES = 2000
_MAX_HOP_ROWS = 200


@dataclass
class _HopFlags:
    degraded: bool = False


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _optional_db_timestamp(value: Any) -> str | None:
    """Normalize SQLite TEXT / Postgres TIMESTAMPTZ for GraphEdge string fields."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_str_id(value: Any) -> str | None:
    """Non-empty string id from a DB row; None when NULL/blank."""
    return _optional_str(value)


@dataclass(frozen=True)
class _CandidateEdge:
    edge: GraphEdge
    target: GraphNode


def _node_from_ref(ref: EntityRef, knowledge_state: KnowledgeState) -> GraphNode:
    return GraphNode(
        node_id=make_node_id(ref.entity_type, ref.entity_id),
        entity_type=ref.entity_type,
        entity_id=ref.entity_id,
        label=ref.label,
        knowledge_state=knowledge_state,
    )


async def get_entity(db, entity_type: str, entity_id: str) -> EntityRef | None:
    """Load one entity when it exists in local stores."""
    ref = EntityRef(
        entity_type=entity_type.strip().lower(),
        entity_id=entity_id,
        label=entity_id,
    )
    if ref.entity_type == "cve":
        ref = EntityRef(entity_type="cve", entity_id=entity_id.upper(), label=entity_id.upper())
        rows = await db.execute_fetchall(
            "SELECT cve_id FROM cves WHERE cve_id = ?",
            (ref.entity_id,),
        )
        if not rows:
            return None
        return ref

    if ref.entity_type == "ioc":
        if not await _ioc_row_exists(db, entity_id):
            return None
        _kind, _, value = entity_id.partition(":")
        return EntityRef(entity_type="ioc", entity_id=entity_id, label=value)

    if ref.entity_type == "technique":
        technique_id = entity_id.upper()
        rows = await db.execute_fetchall(
            """
            SELECT name FROM (
                SELECT t.name AS name
                FROM mitre_techniques t
                WHERE t.technique_id = ?
                UNION
                SELECT NULL AS name
                FROM cve_technique_map m
                WHERE m.technique_id = ?
            ) matches
            ORDER BY (name IS NULL)
            LIMIT 1
            """,
            (technique_id, technique_id),
        )
        if not rows:
            return None
        label = _row_get(rows[0], "name") or technique_id
        return EntityRef(entity_type="technique", entity_id=technique_id, label=label)

    if ref.entity_type == "campaign":
        rows = await db.execute_fetchall(
            """
            SELECT label FROM correlation_campaigns
            WHERE campaign_id = ? AND retracted_at IS NULL
            """,
            (entity_id,),
        )
        if not rows:
            return None
        label = _row_get(rows[0], "label") or entity_id
        return EntityRef(entity_type="campaign", entity_id=entity_id, label=label)

    if ref.entity_type == "publication":
        try:
            pub_id = int(entity_id)
        except ValueError:
            return None
        rows = await db.execute_fetchall(
            """
            SELECT publication_id, title, source_key
            FROM publications
            WHERE publication_id = ?
            """,
            (pub_id,),
        )
        if not rows:
            return None
        title = _row_get(rows[0], "title") or f"publication:{pub_id}"
        return EntityRef(
            entity_type="publication",
            entity_id=str(pub_id),
            label=title,
        )

    return None


async def expand_relationships(
    db,
    root: EntityRef,
    filters: RelationshipFilters,
) -> GraphPage:
    """Breadth-first expansion with global node/edge caps and keyset cursor."""
    root_node = _node_from_ref(root, KnowledgeState.KNOWN)
    nodes_by_id: dict[str, GraphNode] = {root_node.node_id: root_node}
    seen_edges: set[str] = set()
    candidates: list[_CandidateEdge] = []
    partial = False
    flags = _HopFlags()

    frontier = [root]
    for current_depth in range(1, filters.depth + 1):
        next_frontier: list[EntityRef] = []
        for entity in frontier:
            hop_edges = await _edges_for_entity(db, entity, filters, flags)
            for candidate in hop_edges:
                if candidate.edge.edge_id in seen_edges:
                    continue
                seen_edges.add(candidate.edge.edge_id)
                candidates.append(candidate)
                if candidate.target.node_id not in nodes_by_id:
                    nodes_by_id[candidate.target.node_id] = candidate.target
                    if (
                        current_depth < filters.depth
                        and len(next_frontier) < _MAX_FRONTIER
                    ):
                        next_frontier.append(
                            EntityRef(
                                entity_type=candidate.target.entity_type,
                                entity_id=candidate.target.entity_id,
                                label=candidate.target.label,
                            )
                        )
            if len(candidates) >= _MAX_CANDIDATES:
                flags.degraded = True
                partial = True
                next_frontier = []
                break
        next_frontier.sort(key=lambda item: (item.entity_type, item.entity_id))
        frontier = next_frontier[:_MAX_FRONTIER]

    candidates.sort(key=lambda item: item.edge.edge_id)
    candidates = _apply_edge_filters(candidates, filters)
    candidates, truncated, next_cursor = _paginate_candidates(candidates, filters)

    if truncated:
        partial = True

    page_nodes = {root_node.node_id: root_node}
    page_edges: list[GraphEdge] = []
    for candidate in candidates:
        page_edges.append(candidate.edge)
        for node_id in (candidate.edge.source_node_id, candidate.edge.target_node_id):
            node = nodes_by_id.get(node_id)
            if node is not None:
                page_nodes[node_id] = node

    if flags.degraded:
        partial = True
    knowledge_state = KnowledgeState.PARTIAL if partial else KnowledgeState.KNOWN
    source_status = "degraded" if flags.degraded else "ok"
    return GraphPage(
        root=root_node,
        nodes=list(page_nodes.values()),
        edges=page_edges,
        source_status=source_status,
        knowledge_state=knowledge_state,
        truncated=truncated,
        next_cursor=next_cursor,
        generated_at=utc_now_iso(),
        depth=filters.depth,
    )


def _apply_edge_filters(
    candidates: list[_CandidateEdge],
    filters: RelationshipFilters,
) -> list[_CandidateEdge]:
    out: list[_CandidateEdge] = []
    for candidate in candidates:
        edge = candidate.edge
        if filters.edge_class is not None and edge.edge_class != filters.edge_class:
            continue
        if filters.min_confidence is not None:
            if edge.confidence is None:
                continue
            if edge.confidence < filters.min_confidence:
                continue
        out.append(candidate)
    return out


def _paginate_candidates(
    candidates: list[_CandidateEdge],
    filters: RelationshipFilters,
) -> tuple[list[_CandidateEdge], bool, str | None]:
    start_index = 0
    if filters.cursor:
        decoded = _decode_cursor(filters.cursor)
        after_edge_id = decoded.get("after_edge_id")
        if after_edge_id:
            start_index = len(candidates)
            for index, candidate in enumerate(candidates):
                if candidate.edge.edge_id > after_edge_id:
                    start_index = index
                    break

    selected: list[_CandidateEdge] = []
    node_ids: set[str] = set()
    truncated = False

    for candidate in candidates[start_index:]:
        if len(selected) >= filters.limit:
            truncated = True
            break
        needed_nodes = {
            candidate.edge.source_node_id,
            candidate.edge.target_node_id,
        }
        projected_nodes = node_ids | needed_nodes
        # Root is always present; allow up to limit edges and limit+1 distinct nodes.
        if len(projected_nodes) > filters.limit + 1:
            truncated = True
            break
        selected.append(candidate)
        node_ids = projected_nodes

    if not truncated and start_index + len(selected) < len(candidates):
        truncated = True

    next_cursor = None
    if truncated and selected:
        next_cursor = _encode_cursor({"after_edge_id": selected[-1].edge.edge_id})
    elif truncated and not selected and start_index < len(candidates):
        next_cursor = filters.cursor

    return selected, truncated, next_cursor


def _encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        decoded = json.loads(raw.decode("utf-8"))
        if isinstance(decoded, dict):
            return decoded
    except (ValueError, json.JSONDecodeError):
        logger.debug("invalid investigation cursor: %r", cursor)
    return {}


async def _edges_for_entity(
    db,
    entity: EntityRef,
    filters: RelationshipFilters,
    flags: _HopFlags,
) -> list[_CandidateEdge]:
    match entity.entity_type:
        case "cve":
            return await _cve_edges(db, entity, filters, flags)
        case "ioc":
            return await _ioc_edges(db, entity, flags)
        case "technique":
            return await _technique_edges(db, entity)
        case "campaign":
            return await _campaign_edges(db, entity)
        case "publication":
            return await _publication_edges(db, entity)
        case other:
            raise ValueError(f"unsupported entity_type: {other}")


async def _cve_edges(
    db,
    entity: EntityRef,
    filters: RelationshipFilters,
    flags: _HopFlags,
) -> list[_CandidateEdge]:
    cve_id = entity.entity_id.upper()
    source_node_id = make_node_id(entity.entity_type, entity.entity_id)
    edges: list[_CandidateEdge] = []

    technique_rows: list[Any] = []
    try:
        technique_rows = await db.execute_fetchall(
            """
            SELECT m.technique_id, t.name
            FROM cve_technique_map m
            LEFT JOIN mitre_techniques t ON t.technique_id = m.technique_id
            WHERE m.cve_id = ?
            ORDER BY m.technique_id ASC
            LIMIT ?
            """,
            (cve_id, _MAX_HOP_ROWS),
        )
    except Exception as exc:
        flags.degraded = True
        logger.warning("technique hop skipped for %s: %s", cve_id, exc)
    for row in technique_rows:
        technique_id = _required_str_id(_row_get(row, "technique_id"))
        if technique_id is None or not is_valid_technique_id(technique_id):
            continue
        target_ref = EntityRef(
            entity_type="technique",
            entity_id=technique_id,
            label=_optional_str(_row_get(row, "name")) or technique_id,
        )
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=EdgeClass.DIRECT_FACT,
                source_key="cve_technique_map",
            )
        )

    otx_rows: list[Any] = []
    try:
        otx_rows = await db.execute_fetchall(
            """
            SELECT DISTINCT pi.ioc_type, pi.ioc_value, pi.observed_at, cp.fetched_at
            FROM otx_cve_pulses cp
            INNER JOIN otx_pulse_iocs pi ON pi.pulse_id = cp.pulse_id
            WHERE cp.cve_id = ?
            ORDER BY pi.ioc_value ASC
            LIMIT ?
            """,
            (cve_id, _MAX_HOP_ROWS),
        )
    except Exception as exc:
        flags.degraded = True
        logger.warning("OTX hop skipped for %s: %s", cve_id, exc)
    otx_pairs: list[tuple[str, str]] = []
    for row in otx_rows:
        ioc_type = _row_get(row, "ioc_type") or ""
        ioc_value = _row_get(row, "ioc_value") or ""
        cve_ref = _cve_ref_from_otx_indicator(ioc_type, ioc_value, cve_id)
        if cve_ref is not None:
            edges.append(
                _candidate_edge(
                    source_node_id=source_node_id,
                    target_ref=cve_ref,
                    edge_class=EdgeClass.REPORTED,
                    source_key="otx",
                    observed_at=_row_get(row, "observed_at"),
                    fetched_at=_row_get(row, "fetched_at"),
                )
            )
            continue
        ioc_ref = _ioc_ref_from_row(ioc_type, ioc_value)
        if ioc_ref is None:
            continue
        otx_pairs.append((ioc_type, ioc_value))
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=ioc_ref,
                edge_class=EdgeClass.REPORTED,
                source_key="otx",
                observed_at=_row_get(row, "observed_at"),
                fetched_at=_row_get(row, "fetched_at"),
            )
        )

    try:
        mirror_hits = await batch_source_evidence(db, otx_pairs)
    except Exception as exc:
        flags.degraded = True
        logger.warning("TI mirror hop skipped for %s: %s", cve_id, exc)
        mirror_hits = {}
    for (_canon_type, canon_value), mirror_rows in mirror_hits.items():
        ioc_ref = _ioc_ref_from_row(_canon_type, canon_value)
        if ioc_ref is None:
            continue
        for mirror in mirror_rows:
            source_key = _optional_str(mirror.get("source")) or "ti_mirror"
            edges.append(
                _candidate_edge(
                    source_node_id=source_node_id,
                    target_ref=ioc_ref,
                    edge_class=EdgeClass.REPORTED,
                    source_key=source_key,
                    observed_at=_row_get(mirror, "first_seen"),
                    fetched_at=_row_get(mirror, "fetched_at"),
                    confidence=_optional_str(_row_get(mirror, "confidence_level")),
                )
            )

    campaign_rows: list[Any] = []
    try:
        campaign_rows = await db.execute_fetchall(
            """
            SELECT c.campaign_id, c.label
            FROM correlation_campaign_members m
            INNER JOIN correlation_campaigns c ON c.campaign_id = m.campaign_id
            WHERE m.cve_id = ? AND c.retracted_at IS NULL
            ORDER BY c.campaign_id ASC
            LIMIT ?
            """,
            (cve_id, _MAX_HOP_ROWS),
        )
    except Exception as exc:
        flags.degraded = True
        logger.warning("campaign hop skipped for %s: %s", cve_id, exc)
    for row in campaign_rows:
        campaign_id = _required_str_id(_row_get(row, "campaign_id"))
        if campaign_id is None:
            continue
        target_ref = EntityRef(
            entity_type="campaign",
            entity_id=campaign_id,
            label=_optional_str(_row_get(row, "label")) or campaign_id,
        )
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=EdgeClass.DERIVED,
                source_key="correlation",
            )
        )

    sigma_rows, sigma_degraded = await _sigma_rows_for_cve(db, cve_id)
    if sigma_degraded:
        flags.degraded = True
    for row in sigma_rows:
        repo_path = _required_str_id(_row_get(row, "repo_path"))
        if repo_path is None:
            continue
        target_ref = EntityRef(
            entity_type="sigma_rule",
            entity_id=repo_path,
            label=_optional_str(_row_get(row, "title")) or repo_path,
        )
        edge_class = (
            EdgeClass.DIRECT_FACT
            if (_row_get(row, "match_basis") or "") == "cve_exact"
            else EdgeClass.REPORTED
        )
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=edge_class,
                source_key="sigmahq",
                fetched_at=_row_get(row, "updated_at"),
            )
        )

    try:
        related = await get_related_cves(db, cve_id, limit=filters.limit)
    except Exception as exc:
        flags.degraded = True
        logger.warning("related CVE hop skipped for %s: %s", cve_id, exc)
        related = []
    for row in related:
        related_id = row["cve_id"]
        target_ref = EntityRef(
            entity_type="cve",
            entity_id=related_id,
            label=related_id,
        )
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=EdgeClass.DERIVED,
                source_key="related_cve_heuristic",
            )
        )

    publication_rows, publication_degraded = await _publication_rows_for_cve(
        db, cve_id
    )
    if publication_degraded:
        flags.degraded = True
    for row in publication_rows:
        pub_id = str(row["publication_id"])
        target_ref = EntityRef(
            entity_type="publication",
            entity_id=pub_id,
            label=row["title"] or f"publication:{pub_id}",
        )
        source_key = f"publication:{row['source_key']}"
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=EdgeClass.REPORTED,
                source_key=source_key,
                fetched_at=_row_get(row, "retrieved_at"),
            )
        )

    if filters.include_semantic:
        try:
            from ml.embeddings import embeddings_enabled, find_similar_cves
        except ImportError as exc:
            flags.degraded = True
            logger.debug("semantic related CVE hop unavailable: %s", exc)
        else:
            try:
                if embeddings_enabled():
                    similar = await find_similar_cves(db, cve_id, limit=filters.limit)
                    if similar:
                        for item in similar:
                            related_id = item["cve_id"]
                            target_ref = EntityRef(
                                entity_type="cve",
                                entity_id=related_id,
                                label=related_id,
                            )
                            edges.append(
                                _candidate_edge(
                                    source_node_id=source_node_id,
                                    target_ref=target_ref,
                                    edge_class=EdgeClass.SEMANTIC,
                                    source_key="embeddings",
                                    confidence=f"{_row_get(item, 'similarity', 0):.4f}",
                                )
                            )
            except Exception as exc:
                flags.degraded = True
                logger.debug("semantic related CVE hop skipped: %s", exc)

    return _dedupe_candidates(edges)


async def _ioc_edges(db, entity: EntityRef, flags: _HopFlags) -> list[_CandidateEdge]:
    source_node_id = make_node_id(entity.entity_type, entity.entity_id)
    kind, _, value = entity.entity_id.partition(":")
    canon_type = kind.upper()
    normalized = normalize_ioc(canon_type, value)
    if normalized is None:
        return []
    canon_type, canon_value, _meta = normalized
    value_digest = ioc_value_digest(canon_value)

    rows = await db.execute_fetchall(
        """
        SELECT DISTINCT cp.cve_id, cp.fetched_at
        FROM otx_pulse_iocs pi
        INNER JOIN otx_cve_pulses cp ON cp.pulse_id = pi.pulse_id
        WHERE LOWER(pi.ioc_type) = LOWER(?)
          AND (
            pi.ioc_value_digest = ?
            OR (pi.ioc_value_digest = '' AND LOWER(pi.ioc_value) = LOWER(?))
          )
        ORDER BY cp.cve_id ASC
        LIMIT ?
        """,
        (canon_type, value_digest, canon_value, _MAX_HOP_ROWS),
    )
    edges: list[_CandidateEdge] = []
    for row in rows:
        cve_id = row["cve_id"]
        target_ref = EntityRef(entity_type="cve", entity_id=cve_id, label=cve_id)
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=EdgeClass.REPORTED,
                source_key="otx",
                fetched_at=_row_get(row, "fetched_at"),
            )
        )

    mirror_hits = await batch_source_evidence(db, [(canon_type, canon_value)])
    mirror_rows = [
        row
        for rows_for_ioc in mirror_hits.values()
        for row in rows_for_ioc
    ]
    if edges:
        for row in rows:
            cve_id = row["cve_id"]
            target_ref = EntityRef(entity_type="cve", entity_id=cve_id, label=cve_id)
            for mirror in mirror_rows:
                source_key = mirror.get("source") or "ti_mirror"
                edges.append(
                    _candidate_edge(
                        source_node_id=source_node_id,
                        target_ref=target_ref,
                        edge_class=EdgeClass.REPORTED,
                        source_key=source_key,
                        observed_at=_row_get(mirror, "first_seen"),
                        fetched_at=_row_get(mirror, "fetched_at"),
                        confidence=str(_row_get(mirror, "confidence_level"))
                        if _row_get(mirror, "confidence_level") is not None
                        else None,
                    )
                )
    elif await _mirror_ioc_exists(db, canon_type, canon_value):
        flags.degraded = True

    return _dedupe_candidates(edges)


async def _technique_edges(db, entity: EntityRef) -> list[_CandidateEdge]:
    source_node_id = make_node_id(entity.entity_type, entity.entity_id)
    technique_id = entity.entity_id.upper()
    rows = await db.execute_fetchall(
        """
        SELECT cve_id FROM cve_technique_map
        WHERE technique_id = ?
        ORDER BY cve_id ASC
        LIMIT ?
        """,
        (technique_id, _MAX_HOP_ROWS),
    )
    edges: list[_CandidateEdge] = []
    for row in rows:
        cve_id = row["cve_id"]
        target_ref = EntityRef(entity_type="cve", entity_id=cve_id, label=cve_id)
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=EdgeClass.DIRECT_FACT,
                source_key="cve_technique_map",
            )
        )
    return _dedupe_candidates(edges)


async def _campaign_edges(db, entity: EntityRef) -> list[_CandidateEdge]:
    source_node_id = make_node_id(entity.entity_type, entity.entity_id)
    rows = await db.execute_fetchall(
        """
        SELECT cve_id FROM correlation_campaign_members
        WHERE campaign_id = ?
        ORDER BY cve_id ASC
        LIMIT ?
        """,
        (entity.entity_id, _MAX_HOP_ROWS),
    )
    edges: list[_CandidateEdge] = []
    for row in rows:
        cve_id = row["cve_id"]
        target_ref = EntityRef(entity_type="cve", entity_id=cve_id, label=cve_id)
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=EdgeClass.DERIVED,
                source_key="correlation",
            )
        )
    return _dedupe_candidates(edges)


async def _publication_edges(db, entity: EntityRef) -> list[_CandidateEdge]:
    source_node_id = make_node_id(entity.entity_type, entity.entity_id)
    try:
        pub_id = int(entity.entity_id)
    except ValueError:
        return []
    rows = await db.execute_fetchall(
        """
        SELECT entity_id, retrieved_at
        FROM publication_entity_links
        WHERE publication_id = ? AND entity_type = 'cve'
        ORDER BY entity_id ASC
        LIMIT ?
        """,
        (pub_id, _MAX_HOP_ROWS),
    )
    edges: list[_CandidateEdge] = []
    for row in rows:
        cve_id = row["entity_id"]
        target_ref = EntityRef(entity_type="cve", entity_id=cve_id, label=cve_id)
        edges.append(
            _candidate_edge(
                source_node_id=source_node_id,
                target_ref=target_ref,
                edge_class=EdgeClass.REPORTED,
                source_key="publication_entity_link",
                fetched_at=_row_get(row, "retrieved_at"),
            )
        )
    return _dedupe_candidates(edges)


def _candidate_edge(
    *,
    source_node_id: str,
    target_ref: EntityRef,
    edge_class: EdgeClass,
    source_key: str,
    confidence: Any = None,
    observed_at: Any = None,
    fetched_at: Any = None,
) -> _CandidateEdge:
    target_node = _node_from_ref(target_ref, KnowledgeState.KNOWN)
    target_node_id = target_node.node_id
    edge = GraphEdge(
        edge_id=make_edge_id(source_node_id, target_node_id, edge_class, source_key),
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_class=edge_class,
        source_key=source_key,
        confidence=_optional_str(confidence),
        observed_at=_optional_db_timestamp(observed_at),
        fetched_at=_optional_db_timestamp(fetched_at),
    )
    return _CandidateEdge(edge=edge, target=target_node)


def _cve_ref_from_otx_indicator(
    ioc_type: str, ioc_value: str, anchor_cve_id: str
) -> EntityRef | None:
    """Map OTX CVE-as-indicator rows to CVE graph nodes (not IOC nodes)."""
    normalized = normalize_ioc(ioc_type, ioc_value)
    if normalized is None:
        return None
    canon_type, canon_value, _meta = normalized
    if canon_type != "CVE" or not is_valid_cve_id(canon_value):
        return None
    related_id = canon_value.upper()
    if related_id == anchor_cve_id.upper():
        return None
    return EntityRef(entity_type="cve", entity_id=related_id, label=related_id)


def _ioc_ref_from_row(ioc_type: str, ioc_value: str) -> EntityRef | None:
    normalized = normalize_ioc(ioc_type, ioc_value)
    if normalized is None:
        return None
    canon_type, canon_value, _meta = normalized
    try:
        kind = _mirror_ioc_type(canon_type)
    except ValueError:
        # P0 graph contract: IocKind is ip/hash/domain/url only (see contracts.IocKind).
        # OTX also ships email/mutex/etc.; correlation stores them but INVESTIGATE
        # does not model them as IOC nodes until a future entity type lands.
        logger.debug("skip non-graph IOC indicator type %s", canon_type)
        return None
    entity_id = f"{kind}:{canon_value}"
    return EntityRef(entity_type="ioc", entity_id=entity_id, label=canon_value)


def _dedupe_candidates(candidates: list[_CandidateEdge]) -> list[_CandidateEdge]:
    seen: set[str] = set()
    out: list[_CandidateEdge] = []
    for candidate in candidates:
        if candidate.edge.edge_id in seen:
            continue
        seen.add(candidate.edge.edge_id)
        out.append(candidate)
    return out


async def _ioc_row_exists(db, entity_id: str) -> bool:
    if ":" not in entity_id:
        return False
    kind, _, value = entity_id.partition(":")
    canon_type = kind.upper()
    normalized = normalize_ioc(canon_type, value)
    if normalized is None:
        return False
    canon_type, canon_value, _meta = normalized
    value_digest = ioc_value_digest(canon_value)
    rows = await db.execute_fetchall(
        """
        SELECT 1 FROM otx_pulse_iocs
        WHERE LOWER(ioc_type) = LOWER(?)
          AND (
            ioc_value_digest = ?
            OR (ioc_value_digest = '' AND LOWER(ioc_value) = LOWER(?))
          )
        LIMIT 1
        """,
        (canon_type, value_digest, canon_value),
    )
    if rows:
        return True
    return await _mirror_ioc_exists(db, canon_type, canon_value)


async def _mirror_ioc_exists(db, canon_type: str, canon_value: str) -> bool:
    try:
        mirror_type = _mirror_ioc_type(canon_type)
    except ValueError:
        return False
    value_digest = ioc_value_digest(canon_value)
    rows = await db.execute_fetchall(
        """
        SELECT 1 FROM ti_mirror_iocs
        WHERE LOWER(ioc_type) = LOWER(?)
          AND (
            ioc_value_digest = ?
            OR (ioc_value_digest = '' AND LOWER(ioc_value) = LOWER(?))
          )
        LIMIT 1
        """,
        (mirror_type, value_digest, canon_value.lower()),
    )
    return bool(rows)


async def _publication_rows_for_cve(
    db, cve_id: str
) -> tuple[list[dict[str, Any]], bool]:
    try:
        rows = await db.execute_fetchall(
            """
            SELECT p.publication_id, p.title, p.source_key, p.retrieved_at
            FROM publications p
            INNER JOIN publication_entity_links l ON l.publication_id = p.publication_id
            WHERE l.entity_type = 'cve' AND l.entity_id = ?
            ORDER BY p.published_at DESC, p.publication_id ASC
            LIMIT ?
            """,
            (cve_id, _MAX_HOP_ROWS),
        )
    except Exception as exc:
        logger.debug("publication hop skipped: %s", exc)
        return [], True
    return [dict(row) for row in rows], False


async def _sigma_rows_for_cve(
    db, cve_id: str
) -> tuple[list[dict[str, Any]], bool]:
    try:
        rows = await db.execute_fetchall(
            """
            SELECT r.title, r.repo_path, r.updated_at, c.match_basis
            FROM detection_rules r
            INNER JOIN detection_rule_cves c ON c.rule_id = r.id
            WHERE c.cve_id = ? AND r.source = ? AND r.retired_at IS NULL
            ORDER BY r.title ASC
            LIMIT ?
            """,
            (cve_id, _SIGMA_SOURCE, _MAX_HOP_ROWS),
        )
    except Exception as exc:
        logger.debug("Sigma index hop skipped: %s", exc)
        return [], True
    return [dict(row) for row in rows], False
