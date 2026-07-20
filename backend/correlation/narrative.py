"""Analyst-facing correlation narrative helpers (Correlation v2 Phase 2)."""

from __future__ import annotations

import html


def sanitize_pulse_text(value: str, max_len: int = 240) -> str:
    text = html.escape((value or "").strip())
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def infrastructure_summary(peer_cve: str, counts: dict[str, int]) -> str:
    parts = []
    if counts.get("HASH"):
        parts.append(f"{counts['HASH']} hash{'es' if counts['HASH'] != 1 else ''}")
    if counts.get("DOMAIN"):
        parts.append(f"{counts['DOMAIN']} domain{'s' if counts['DOMAIN'] != 1 else ''}")
    if counts.get("URL"):
        parts.append(f"{counts['URL']} URL{'s' if counts['URL'] != 1 else ''}")
    if counts.get("IP"):
        parts.append(f"{counts['IP']} IP{'s' if counts['IP'] != 1 else ''}")
    joined = ", ".join(parts) if parts else "shared indicators"
    return f"Shares {joined} with {peer_cve} via OTX pulses."


def campaign_summary(label: str, peer_count: int, *, has_ioc: bool = False) -> str:
    safe_label = sanitize_pulse_text(label)
    base = f"Linked to {peer_count} other CVE(s) via OTX pulse \"{safe_label}\"."
    if has_ioc:
        base += " Shared indicators strengthen this link."
    return base
