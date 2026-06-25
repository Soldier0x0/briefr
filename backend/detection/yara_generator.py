"""YARA rule templates from OTX pulse file hashes (hash-led hunts)."""

from __future__ import annotations

import re
from typing import Any

_HASH_RE = re.compile(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$")


def _normalize_hash(value: str) -> str | None:
    text = (value or "").strip().lower()
    if _HASH_RE.match(text):
        return text
    return None


def _rule_name(cve_id: str, idx: int) -> str:
    safe = cve_id.replace("-", "_").lower()
    return f"briefr_otx_{safe}_{idx}"


def build_yara_rules_from_hashes(
    cve_id: str,
    hashes: list[str],
    *,
    pulse_name: str = "",
) -> list[dict[str, Any]]:
    """
    Build experimental YARA rules from OTX file hashes linked to a CVE.

    One rule per hash (up to caller limit). Rules are marked generated/experimental.
    """
    rules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in hashes:
        h = _normalize_hash(raw)
        if not h or h in seen:
            continue
        seen.add(h)
        idx = len(rules) + 1
        meta_pulse = pulse_name or "OTX pulse"
        if len(h) == 32:
            cond = f'hash.md5(0, filesize) == "{h}"'
        elif len(h) == 40:
            cond = f'hash.sha1(0, filesize) == "{h}"'
        else:
            cond = f'hash.sha256(0, filesize) == "{h}"'
        yara = f"""rule {_rule_name(cve_id, idx)} {{
    meta:
        author = "BRIEFR (generated from OTX)"
        description = "Hash from {meta_pulse} linked to {cve_id}"
        cve = "{cve_id.upper()}"
        confidence = "experimental"
    condition:
        {cond}
}}"""
        rules.append(
            {
                "rule_name": _rule_name(cve_id, idx),
                "hash": h,
                "hash_type": {32: "md5", 40: "sha1", 64: "sha256"}[len(h)],
                "source": "otx_pulse_iocs",
                "yara": yara,
                "confidence": "experimental",
            }
        )
    return rules


async def find_yara_rules_for_cve(
    db, cve_id: str, *, limit: int = 10
) -> list[dict[str, Any]]:
    """Load file hashes from OTX pulses for *cve_id* and emit YARA templates."""
    key = cve_id.upper()
    rows = await db.execute_fetchall(
        """
        SELECT DISTINCT opi.ioc_value, ocp.pulse_name
        FROM otx_cve_pulses ocp
        JOIN otx_pulse_iocs opi ON opi.pulse_id = ocp.pulse_id
        WHERE ocp.cve_id = ?
          AND UPPER(opi.ioc_type) IN (
            'FILEHASH-SHA256', 'FILEHASH-SHA1', 'FILEHASH-MD5',
            'SHA256', 'SHA1', 'MD5', 'HASH'
          )
        ORDER BY ocp.fetched_at DESC
        LIMIT ?
        """,
        (key, limit * 3),
    )
    if not rows:
        return []

    rules: list[dict[str, Any]] = []
    for row in rows:
        pulse = row.get("pulse_name") or ""
        batch = build_yara_rules_from_hashes(key, [row.get("ioc_value") or ""], pulse_name=pulse)
        rules.extend(batch)
        if len(rules) >= limit:
            break
    return rules[:limit]
