"""TXT/JSON serialization for the malicious-domain-candidates blocklist."""

from __future__ import annotations

from typing import Any


def to_txt(payload: dict[str, Any]) -> str:
    """One canonical domain per line, sorted, eligible candidates only.

    Uses the canonical domain only (no wildcards, no parent-domain folding) so
    DNS-blocklist operators can append it verbatim to an adblock-style allow/
    deny file or load it into a resolver list.
    """
    lines = [record["domain"] for record in payload.get("domains", []) if record.get("eligible")]
    lines.sort()
    header = (
        "# BRIEFR malicious-domain candidates\n"
        f"# generated_at: {payload['meta']['generated_at']}\n"
        f"# eligible: {payload['meta']['eligible_count']}\n"
        f"# excluded: {payload['meta']['excluded_count']}\n"
    )
    body = "\n".join(lines)
    return (header + body + "\n") if body else header


def to_json(payload: dict[str, Any]) -> dict[str, Any]:
    """Structured JSON export. Includes both eligible candidates and excluded
    ones (with their reason) so consumers can audit exactly why a domain is or
    is not on the list. Deterministic field order is preserved by the dict."""
    return {
        "meta": dict(payload["meta"]),
        "domains": list(payload.get("domains", [])),
        "excluded": list(payload.get("excluded", [])),
    }
