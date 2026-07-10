"""Phase 4 cluster list for brief/feed consumers."""

from __future__ import annotations

from typing import Any

from correlation.copy import sanitize_pulse_text
from routers.cves import _stack_match_clause

_LIFECYCLE_RANK = {
    "emerging": 0,
    "active": 1,
    "declining": 2,
    "stale": 3,
}


def _cluster_sort_key(item: dict) -> tuple:
    lifecycle = item.get("lifecycle") or "active"
    return (
        -int(item.get("stack_member_count") or 0),
        -int(item.get("watchlisted_member_count") or 0),
        -int(item.get("member_count") or 0),
        _LIFECYCLE_RANK.get(lifecycle, 4),
        item.get("label") or "",
    )


async def list_correlation_clusters(
    db: Any,
    *,
    stack: str | None = None,
    cve_id: str | None = None,
    limit: int = 20,
    include_stale: bool = False,
) -> dict[str, Any]:
    """Return campaign clusters ranked for stack + watchlist relevance."""
    cve_filter = (cve_id or "").strip().upper()
    stack_clause, stack_params, stack_terms = _stack_match_clause(stack)
    stale_filter = "" if include_stale else "AND camp.lifecycle != 'stale'"
    campaign_scope_sql = ""
    campaign_scope_params: list[Any] = []
    if cve_filter:
        campaign_scope_sql = """
          AND EXISTS (
              SELECT 1 FROM correlation_campaign_members m0
              WHERE m0.campaign_id = camp.campaign_id
                AND m0.cve_id = ?
          )
        """
        campaign_scope_params.append(cve_filter)

    rows = await db.execute_fetchall(
        f"""
        SELECT camp.campaign_id, camp.primary_pulse_id, camp.label, camp.adversary,
               camp.confidence, camp.member_count, camp.lifecycle
        FROM correlation_campaigns camp
        WHERE camp.member_count >= 2
          {stale_filter}
          {campaign_scope_sql}
        ORDER BY camp.member_count DESC, camp.label ASC
        LIMIT ?
        """,
        (*campaign_scope_params, max(limit * 5, limit)),
    )

    watchlist_rows = await db.execute_fetchall(
        """
        SELECT cve_id FROM watchlist
        WHERE state = 'pin'
           OR (state = 'snooze'
               AND snooze_until IS NOT NULL
               AND TRIM(snooze_until) != ''
               AND datetime(snooze_until) > datetime('now'))
        """
    )
    watchlisted = {row["cve_id"] for row in watchlist_rows}

    clusters: list[dict] = []
    for row in rows:
        member_rows = await db.execute_fetchall(
            """
            SELECT m.cve_id
            FROM correlation_campaign_members m
            INNER JOIN cves c ON c.cve_id = m.cve_id
            WHERE m.campaign_id = ?
            ORDER BY m.cve_id ASC
            """,
            (row["campaign_id"],),
        )
        members = [r["cve_id"] for r in member_rows]
        if len(members) < 2:
            continue

        members_on_stack: list[str] = []
        if stack_clause:
            stack_member_rows = await db.execute_fetchall(
                f"""
                SELECT m.cve_id
                FROM correlation_campaign_members m
                INNER JOIN cves c ON c.cve_id = m.cve_id
                WHERE m.campaign_id = ?
                  AND {stack_clause}
                ORDER BY m.cve_id ASC
                """,
                (row["campaign_id"], *stack_params),
            )
            members_on_stack = [r["cve_id"] for r in stack_member_rows]
            if not members_on_stack:
                continue

        watchlisted_members = [cve_id for cve_id in members if cve_id in watchlisted]
        clusters.append(
            {
                "campaign_id": row["campaign_id"],
                "primary_pulse_id": row["primary_pulse_id"],
                "label": sanitize_pulse_text(row["label"] or ""),
                "adversary": sanitize_pulse_text(row["adversary"] or "", 120),
                "confidence": row["confidence"],
                "lifecycle": row["lifecycle"] or "active",
                "member_count": len(members),
                "stack_member_count": len(members_on_stack),
                "watchlisted_member_count": len(watchlisted_members),
                "members_on_stack": members_on_stack,
                "watchlisted_members": watchlisted_members,
            }
        )

    clusters.sort(key=_cluster_sort_key)
    clusters = clusters[:limit]

    return {
        "meta": {
            "stack_terms": stack_terms,
            "cve_id": cve_filter or None,
            "limit": limit,
            "include_stale": include_stale,
            "count": len(clusters),
        },
        "clusters": clusters,
    }
