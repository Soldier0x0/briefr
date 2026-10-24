"""CRUD for saved investigation workspace cases."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

_NODE_ID_RE = re.compile(
    r"^(cve|ioc|technique|campaign|publication|sigma_rule):.+",
    re.IGNORECASE,
)
_MAX_NODES = 500
_MAX_EDGES = 600


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_snapshot(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise ValueError("snapshot must be a JSON object")


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    nodes = snapshot.get("nodes") or []
    edges = snapshot.get("edges") or []
    if len(nodes) > _MAX_NODES:
        raise ValueError(f"snapshot exceeds {_MAX_NODES} nodes")
    if len(edges) > _MAX_EDGES:
        raise ValueError(f"snapshot exceeds {_MAX_EDGES} edges")
    for node in nodes:
        node_id = (node or {}).get("node_id")
        if not node_id or not _NODE_ID_RE.match(str(node_id)):
            raise ValueError(f"invalid node_id: {node_id!r}")


def derive_root_node_id(snapshot: dict[str, Any]) -> str:
    root_id = snapshot.get("root_id")
    if root_id and _NODE_ID_RE.match(str(root_id)):
        return str(root_id)
    nodes = snapshot.get("nodes") or []
    if nodes and nodes[0].get("node_id"):
        return str(nodes[0]["node_id"])
    raise ValueError("snapshot missing root_id")


def default_case_title(snapshot: dict[str, Any], root_node_id: str) -> str:
    nodes = snapshot.get("nodes") or []
    label = root_node_id
    for node in nodes:
        if node.get("node_id") == root_node_id:
            label = node.get("label") or node.get("entity_id") or root_node_id
            break
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{label} · {date}"


def _snapshot_to_db(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, separators=(",", ":"), sort_keys=True)


def _snapshot_from_row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return json.loads(str(value))


async def list_cases(db, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    rows = await db.execute_fetchall(
        """
        SELECT id, title, root_node_id, created_at, updated_at
        FROM investigation_cases
        WHERE owner_user_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    return [
        {
            "id": str(row["id"]),
            "title": row["title"],
            "root_node_id": row["root_node_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


async def create_case(
    db,
    user_id: int,
    snapshot: dict[str, Any],
    title: str | None = None,
) -> str:
    validate_snapshot(snapshot)
    root_node_id = derive_root_node_id(snapshot)
    case_title = (title or "").strip() or default_case_title(snapshot, root_node_id)
    case_id = str(uuid.uuid4())
    now = _utc_now_iso()
    await db.execute(
        """
        INSERT INTO investigation_cases (
            id, owner_user_id, title, root_node_id, snapshot, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (case_id, user_id, case_title, root_node_id, _snapshot_to_db(snapshot), now, now),
    )
    await db.commit()
    return case_id


async def get_case(db, user_id: int, case_id: str) -> dict[str, Any] | None:
    rows = await db.execute_fetchall(
        """
        SELECT id, title, root_node_id, snapshot, created_at, updated_at
        FROM investigation_cases
        WHERE id = ? AND owner_user_id = ?
        """,
        (case_id, user_id),
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "root_node_id": row["root_node_id"],
        "snapshot": _snapshot_from_row(row["snapshot"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def update_case(
    db,
    user_id: int,
    case_id: str,
    snapshot: dict[str, Any],
    title: str | None = None,
) -> bool:
    validate_snapshot(snapshot)
    root_node_id = derive_root_node_id(snapshot)
    case_title = (title or "").strip()
    now = _utc_now_iso()
    if case_title:
        result = await db.execute(
            """
            UPDATE investigation_cases
            SET snapshot = ?, root_node_id = ?, title = ?, updated_at = ?
            WHERE id = ? AND owner_user_id = ?
            """,
            (_snapshot_to_db(snapshot), root_node_id, case_title, now, case_id, user_id),
        )
    else:
        result = await db.execute(
            """
            UPDATE investigation_cases
            SET snapshot = ?, root_node_id = ?, updated_at = ?
            WHERE id = ? AND owner_user_id = ?
            """,
            (_snapshot_to_db(snapshot), root_node_id, now, case_id, user_id),
        )
    await db.commit()
    return result.rowcount > 0


async def delete_case(db, user_id: int, case_id: str) -> bool:
    result = await db.execute(
        "DELETE FROM investigation_cases WHERE id = ? AND owner_user_id = ?",
        (case_id, user_id),
    )
    await db.commit()
    return result.rowcount > 0
