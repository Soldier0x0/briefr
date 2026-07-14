"""Alias-aware attribution conflict detection (CORR-PR-11)."""

from __future__ import annotations

import json
from typing import Any


def normalize_actor_token(name: str) -> str:
    return (name or "").strip().lower()


def build_alias_families(groups: list[dict]) -> dict[str, set[str]]:
    """Map normalized actor token -> alias family set."""
    index: dict[str, set[str]] = {}
    for row in groups:
        names: set[str] = set()
        primary = (row.get("name") or "").strip()
        if primary:
            names.add(primary)
        aliases = row.get("aliases")
        if isinstance(aliases, str):
            try:
                parsed = json.loads(aliases)
                aliases = parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                aliases = []
        if isinstance(aliases, list):
            for alias in aliases:
                text = str(alias or "").strip()
                if text:
                    names.add(text)
        family = {normalize_actor_token(n) for n in names if n}
        if not family:
            continue
        for token in family:
            index[token] = index.get(token, set()) | family
    return index


def actors_in_same_family(
    a: str, b: str, alias_index: dict[str, set[str]]
) -> bool:
    a_tok = normalize_actor_token(a)
    b_tok = normalize_actor_token(b)
    if not a_tok or not b_tok:
        return False
    if a_tok in b_tok or b_tok in a_tok:
        return True
    fam_a = alias_index.get(a_tok, {a_tok})
    fam_b = alias_index.get(b_tok, {b_tok})
    return bool(fam_a & fam_b)


async def load_mitre_alias_index(db) -> dict[str, set[str]]:
    rows = await db.execute_fetchall("SELECT name, aliases FROM mitre_groups")
    return build_alias_families([dict(row) for row in rows])


def attribution_conflict(
    otx_adversary: str,
    mitre_actors: list[str],
    *,
    alias_index: dict[str, set[str]] | None = None,
) -> bool:
    if not otx_adversary or not mitre_actors:
        return False
    alias_index = alias_index or {}
    for name in mitre_actors:
        if not name:
            continue
        if actors_in_same_family(otx_adversary, name, alias_index):
            return False
    return True


def build_attribution_claims(
    otx_adversary: str,
    mitre_actors: list[str],
    *,
    alias_index: dict[str, set[str]] | None = None,
    otx_observed_at: str = "",
) -> dict[str, Any] | None:
    if not attribution_conflict(
        otx_adversary, mitre_actors, alias_index=alias_index
    ):
        return None
    mitre_name = next((n for n in mitre_actors if n), "")
    return {
        "status": "unresolved",
        "claims": [
            {
                "value": otx_adversary.strip(),
                "source": "otx",
                "observed_at": otx_observed_at or "",
            },
            {
                "value": mitre_name,
                "source": "mitre_technique",
                "observed_at": "",
            },
        ],
    }
