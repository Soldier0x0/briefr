"""TXT/CSV/JSON serialization for the malicious-domain-candidates blocklist.

All serializers read from the same canonical payload produced by
`blocklist.build.build_blocklist` (one build, three representations) so the
formats cannot diverge:
- TXT   — simple machine consumption, one canonical domain per line.
- CSV   — analyst-friendly rows with explicit IOC type + exact value.
- JSON  — lossless/complete representation (full evidence provenance).
"""

from __future__ import annotations

import csv
import io
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


def to_csv(payload: dict[str, Any]) -> str:
    """Analyst-friendly CSV with explicit IOC type + exact value per row.

    Columns: type, value, source, confidence, first_seen, malware, threat_type.
    ``value`` is the exact upstream IOC (``raw_ioc``/``ioc_value``) — a URL is
    preserved verbatim and never replaced by its derived domain. Multi-valued
    cells (source/malware/threat_type) are joined with ``;`` so the CSV stays
    parseable. Eligible candidates only, matching the TXT body semantics.
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        ["type", "value", "source", "confidence", "first_seen", "malware", "threat_type"]
    )
    for record in payload.get("domains", []):
        if not record.get("eligible"):
            continue
        writer.writerow([
            record.get("ioc_type") or "domain",
            record.get("exact_ioc") or "",
            ";".join(record.get("sources") or []),
            record.get("confidence") or "",
            record.get("first_seen") or "",
            ";".join(record.get("malware") or []),
            ";".join(record.get("threat_type") or []),
        ])
    return out.getvalue()


def to_json(payload: dict[str, Any]) -> dict[str, Any]:
    """Structured JSON export. Includes both eligible candidates and excluded
    ones (with their reason) so consumers can audit exactly why a domain is or
    is not on the list. Deterministic field order is preserved by the dict."""
    return {
        "meta": dict(payload["meta"]),
        "domains": list(payload.get("domains", [])),
        "excluded": list(payload.get("excluded", [])),
    }
