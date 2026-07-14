"""Analyst confirm / reject feedback for correlation findings (CORR-PR-12)."""

from __future__ import annotations

from typing import Any

from correlation.suppressions import VALID_SCOPES, scope_key_for

VALID_VERDICTS = frozenset({"confirm", "reject", "resolve_conflict"})


async def add_feedback(
    db,
    cve_id: str,
    scope: str,
    key: dict[str, Any],
    verdict: str,
    reason: str = "",
    created_by: str = "",
) -> dict:
    from database import insert_correlation_feedback

    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope: {scope}")
    verdict_norm = (verdict or "").strip().lower()
    if verdict_norm not in VALID_VERDICTS:
        raise ValueError(f"Invalid verdict: {verdict}")
    sk = scope_key_for(scope, key)
    if not sk:
        raise ValueError("Missing scope key")
    return await insert_correlation_feedback(
        db,
        cve_id.upper(),
        scope,
        sk,
        verdict_norm,
        reason.strip(),
        created_by.strip(),
    )


async def remove_feedback(
    db,
    cve_id: str,
    scope: str,
    key: dict[str, Any],
    verdict: str,
) -> bool:
    from database import delete_correlation_feedback

    verdict_norm = (verdict or "").strip().lower()
    if verdict_norm not in VALID_VERDICTS:
        raise ValueError(f"Invalid verdict: {verdict}")
    sk = scope_key_for(scope, key)
    return await delete_correlation_feedback(
        db, cve_id.upper(), scope, sk, verdict_norm
    )


async def load_feedback(db, cve_id: str) -> list[dict]:
    from database import list_correlation_feedback

    return await list_correlation_feedback(db, cve_id.upper())
