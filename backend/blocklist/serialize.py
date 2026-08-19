"""TXT/CSV/JSON serialization for the malicious-domain-candidates blocklist.

All serializers read from the same canonical payload produced by
`blocklist.build.build_blocklist` (one build, three representations) so the
formats cannot diverge:
- TXT   — simple machine consumption; ``mode=domains`` (default) emits one
          canonical domain per line; ``mode=urls`` emits one exact URL per line.
- CSV   — analyst-friendly rows with explicit IOC type + exact value.
- JSON  — lossless/complete representation (full evidence provenance).
"""

from __future__ import annotations

import csv
import io
from typing import Any, Literal

ExportMode = Literal["domains", "urls", "all"]

_VALID_MODES: frozenset[str] = frozenset({"domains", "urls", "all"})


def normalize_export_mode(mode: str | None) -> ExportMode:
    normalized = (mode or "domains").strip().lower()
    if normalized not in _VALID_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(_VALID_MODES))}")
    return normalized  # type: ignore[return-value]


def _record_matches_mode(record: dict[str, Any], mode: ExportMode) -> bool:
    if not record.get("eligible"):
        return False
    if mode == "domains":
        return bool(record.get("eligible_domain"))
    if mode == "urls":
        return bool(record.get("eligible_url"))
    return bool(record.get("eligible_domain") or record.get("eligible_url"))


def _eligible_count(payload: dict[str, Any], mode: ExportMode) -> int:
    return sum(1 for record in payload.get("domains", []) if _record_matches_mode(record, mode))


def to_txt(payload: dict[str, Any], *, mode: ExportMode = "domains") -> str:
    """Eligible candidates as plain lines (domains or exact URLs per mode)."""
    lines: list[str] = []
    for record in payload.get("domains", []):
        if not _record_matches_mode(record, mode):
            continue
        if mode == "urls":
            value = (record.get("exact_ioc") or "").strip()
            if value:
                lines.append(value)
        else:
            lines.append(record["domain"])
    lines.sort()
    eligible = _eligible_count(payload, mode)
    header = (
        "# BRIEFR malicious-domain candidates\n"
        f"# generated_at: {payload['meta']['generated_at']}\n"
        f"# mode: {mode}\n"
        f"# eligible: {eligible}\n"
        f"# excluded: {payload['meta']['excluded_count']}\n"
    )
    body = "\n".join(lines)
    return (header + body + "\n") if body else header


def _escape_spreadsheet_value(value: str) -> str:
    """Escape a value for spreadsheet consumption.

    Excel and Google Sheets interpret cell values starting with ``=``, ``+``,
    ``-``, or ``@`` as formulas.  Prefixing with ``'`` (single quote) forces
    the value to be treated as literal text.
    """
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def to_csv(payload: dict[str, Any], *, mode: ExportMode = "all") -> str:
    """Analyst-friendly CSV with explicit IOC type + exact value per row."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        ["type", "value", "source", "confidence", "first_seen", "malware", "threat_type"]
    )
    for record in payload.get("domains", []):
        if not _record_matches_mode(record, mode):
            continue
        writer.writerow([
            _escape_spreadsheet_value(record.get("ioc_type") or "domain"),
            _escape_spreadsheet_value(record.get("exact_ioc") or ""),
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
