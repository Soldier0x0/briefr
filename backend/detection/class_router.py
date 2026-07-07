"""Unified detection class router (Sprint D3).

Single resolution path for CWE/ATT&CK → stable class slug used by
``sigma_generator``, ``siem_queries``, and log-pattern output.
"""

from __future__ import annotations

import json
from typing import Any

from detection.sigma_generator import _normalize_cwe_id

# CWE → stable class slug (aligned with D1 CWE Sigma templates).
CWE_CLASS_SLUGS: dict[str, str] = {
    "CWE-22": "path_traversal",
    "CWE-23": "path_traversal",
    "CWE-35": "path_traversal",
    "CWE-78": "cmd_injection",
    "CWE-89": "sqli",
    "CWE-79": "xss",
    "CWE-502": "deserialization",
    "CWE-94": "code_injection",
    "CWE-95": "code_injection",
    "CWE-434": "unsafe_upload",
    "CWE-918": "ssrf",
    "CWE-611": "xxe",
    "CWE-287": "auth_bypass",
    "CWE-288": "auth_bypass",
    "CWE-306": "auth_bypass",
    "CWE-416": "memory_corruption",
    "CWE-787": "memory_corruption",
    "CWE-119": "memory_corruption",
    "CWE-122": "memory_corruption",
    "CWE-798": "default_credentials",
}

TECHNIQUE_CLASS_SLUGS: dict[str, str] = {
    "T1190": "web_exploit",
    "T1133": "remote_access",
    "T1059": "script_execution",
    "T1203": "client_execution",
    "T1068": "privilege_escalation",
    "T1055": "process_injection",
    "T1027": "obfuscation",
    "T1036": "masquerading",
    "T1110": "brute_force",
    "T1003": "credential_dumping",
    "T1021": "lateral_movement",
    "T1570": "lateral_transfer",
    "T1071": "c2_application",
    "T1095": "c2_non_application",
}


def normalize_cwe_ids(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [norm for item in parsed if (norm := _normalize_cwe_id(str(item)))]


def resolve_detection_class(
    technique_id: str,
    cwe_ids: list[str] | None,
) -> str:
    """Map ATT&CK technique or CWE list to a stable detection class slug."""
    prefix = (technique_id or "").strip().upper()[:5]
    if prefix in TECHNIQUE_CLASS_SLUGS:
        return TECHNIQUE_CLASS_SLUGS[prefix]

    for raw in cwe_ids or []:
        cwe_id = _normalize_cwe_id(str(raw))
        slug = CWE_CLASS_SLUGS.get(cwe_id)
        if slug:
            return slug

    return "generic"


def _resolve_detection_class(cve: dict) -> str:
    """Resolve class from a CVE-like dict (single entry point for detection outputs)."""
    technique_id = (
        cve.get("mitre_technique")
        or cve.get("technique_id")
        or ""
    )
    cwe_ids = cve.get("cwe_ids")
    if cwe_ids is None and cve.get("detection_context"):
        cwe_ids = cve["detection_context"].get("cwe_ids")
    normalized = (
        normalize_cwe_ids(cwe_ids)
        if not isinstance(cwe_ids, list)
        else [_normalize_cwe_id(str(c)) for c in cwe_ids if _normalize_cwe_id(str(c))]
    )
    return resolve_detection_class(str(technique_id), normalized)
