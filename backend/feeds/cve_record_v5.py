"""Parse CVE JSON 5.x records (cvelistV5 / vulnrichment) into BRIEFR CVE dicts."""

from __future__ import annotations

import json
import re
from typing import Any

CVE_ID_RE = re.compile(r"^CVE-\d{4}-\d{4,7}$", re.IGNORECASE)
CISA_VULNRICHMENT_TITLE = "CISA ADP Vulnrichment"
CVE_RECORD_STATE_REJECTED = "REJECTED"

SEVERITY_RANK = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "NONE": 1,
    "UNKNOWN": 0,
    "": 0,
}


def cve_tree_bucket(cve_id: str) -> str | None:
    """Year/bucket segment shared by cvelistV5 and vulnrichment paths."""
    match = CVE_ID_RE.match(cve_id.strip().upper())
    if not match:
        return None
    year = cve_id.split("-")[1]
    seq = int(cve_id.split("-")[2])
    return f"{year}/{seq // 1000}xxx"


def cvelistv5_repo_path(cve_id: str) -> str:
    bucket = cve_tree_bucket(cve_id)
    if not bucket:
        return ""
    return f"cves/{bucket}/{cve_id.strip().upper()}.json"


def vulnrichment_repo_path(cve_id: str) -> str:
    bucket = cve_tree_bucket(cve_id)
    if not bucket:
        return ""
    return f"{bucket}/{cve_id.strip().upper()}.json"


def cve_id_from_repo_path(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    if name.lower().endswith(".json"):
        candidate = name[:-5].upper()
        if CVE_ID_RE.match(candidate):
            return candidate
    return None


def _extract_description(container: dict | None) -> str:
    if not isinstance(container, dict):
        return ""
    descriptions = container.get("descriptions")
    if not isinstance(descriptions, list):
        return ""
    for item in descriptions:
        if isinstance(item, dict) and item.get("lang") == "en":
            value = item.get("value")
            if isinstance(value, str):
                value = value.strip()
                if value:
                    return value
    for item in descriptions:
        if isinstance(item, dict):
            value = item.get("value")
            if isinstance(value, str):
                value = value.strip()
                if value:
                    return value
    return ""


def _extract_cvss(metrics: Any) -> tuple[float | None, str]:
    if not isinstance(metrics, list):
        return None, "UNKNOWN"
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        for key in ("cvssV3_1", "cvssV3_0", "cvssV4_0"):
            data = metric.get(key)
            if not isinstance(data, dict):
                continue
            score = data.get("baseScore")
            severity_raw = data.get("baseSeverity")
            severity = severity_raw.upper() if isinstance(severity_raw, str) else "UNKNOWN"
            if score is not None:
                try:
                    return float(score), severity
                except (TypeError, ValueError):
                    continue
    return None, "UNKNOWN"


def _extract_cwes(container: dict | None) -> list[str]:
    if not isinstance(container, dict):
        return []
    cwes: set[str] = set()
    problem_types = container.get("problemTypes")
    if not isinstance(problem_types, list):
        return []
    for problem in problem_types:
        if not isinstance(problem, dict):
            continue
        descriptions = problem.get("descriptions")
        if not isinstance(descriptions, list):
            continue
        for desc in descriptions:
            if not isinstance(desc, dict):
                continue
            cwe_id = desc.get("cweId")
            if isinstance(cwe_id, str):
                cwe_id = cwe_id.strip().upper()
                if cwe_id.startswith("CWE-"):
                    cwes.add(cwe_id)
            else:
                value = desc.get("description")
                if isinstance(value, str):
                    value = value.strip()
                    if value.upper().startswith("CWE-"):
                        token = value.split()[0].upper()
                        if token.startswith("CWE-"):
                            cwes.add(token)
    return sorted(cwes)


def _vendor_product_key(vendor: str, product: str) -> str:
    return f"{vendor.strip().lower()}:{product.strip().lower()}"


def _extract_affected_products(*containers: dict | None) -> list[str]:
    products: set[str] = set()
    for container in containers:
        if not isinstance(container, dict):
            continue
        affected = container.get("affected")
        if not isinstance(affected, list):
            continue
        for item in affected:
            if not isinstance(item, dict):
                continue
            vendor = item.get("vendor")
            product = item.get("product")
            if isinstance(vendor, str) and isinstance(product, str):
                vendor = vendor.strip()
                product = product.strip()
                if vendor and product:
                    products.add(_vendor_product_key(vendor, product))
            cpes = item.get("cpes")
            if isinstance(cpes, list):
                for cpe in cpes:
                    if not isinstance(cpe, str):
                        continue
                    parts = cpe.split(":")
                    if len(parts) >= 5:
                        vendor = parts[3]
                        product = parts[4]
                        if vendor and product and vendor not in ("*", "-") and product not in ("*", "-"):
                            products.add(_vendor_product_key(vendor, product))
    return sorted(products)


def is_cve_record_rejected(record: dict) -> str | None:
    """Return CVE ID when the CVE JSON 5.x record is REJECTED, else None."""
    if not isinstance(record, dict):
        return None
    meta = record.get("cveMetadata")
    if not isinstance(meta, dict):
        return None
    state = meta.get("state")
    if not isinstance(state, str) or state.strip().upper() != CVE_RECORD_STATE_REJECTED:
        return None
    cve_id = meta.get("cveId")
    if not isinstance(cve_id, str):
        return None
    cve_id = cve_id.strip().upper()
    if CVE_ID_RE.match(cve_id):
        return cve_id
    return None


def _find_cisa_adp(adp_list: list) -> dict | None:
    for item in adp_list:
        if isinstance(item, dict) and item.get("title") == CISA_VULNRICHMENT_TITLE:
            return item
    return None


def _extract_ssvc(metrics: Any) -> dict | None:
    """Parse CISA SSVC decision points from CVE JSON 5.x ADP metrics."""
    if not isinstance(metrics, list):
        return None
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        other = metric.get("other")
        if not isinstance(other, dict) or str(other.get("type") or "").lower() != "ssvc":
            continue
        content = other.get("content")
        if not isinstance(content, dict):
            continue
        decisions: dict[str, str] = {}
        for opt in content.get("options") or []:
            if not isinstance(opt, dict):
                continue
            for key, value in opt.items():
                if isinstance(value, str) and value.strip():
                    decisions[str(key)] = value.strip()
        computed = content.get("computed")
        if isinstance(computed, str) and computed.strip():
            decisions["computed"] = computed.strip()
        if not decisions:
            continue
        return {
            "decisions": decisions,
            "version": str(content.get("version") or "").strip(),
            "role": str(content.get("role") or "").strip(),
        }
    return None


def parse_vulnrichment_record(record: dict) -> dict | None:
    """Extract CISA ADP enrichment fields; used for gap-filling before NVD analysis."""
    if not isinstance(record, dict):
        return None
    meta = record.get("cveMetadata")
    if not isinstance(meta, dict):
        return None
    cve_id = (meta.get("cveId") or "").upper()
    if not CVE_ID_RE.match(cve_id):
        return None
    if is_cve_record_rejected(record):
        return None

    containers = record.get("containers")
    if not isinstance(containers, dict):
        return None
    cisa_adp = _find_cisa_adp(containers.get("adp") or [])
    if not cisa_adp:
        return None

    cvss_score, severity = _extract_cvss(cisa_adp.get("metrics"))
    cwe_ids = _extract_cwes(cisa_adp)
    affected_products = _extract_affected_products(cisa_adp)
    ssvc = _extract_ssvc(cisa_adp.get("metrics"))

    if cvss_score is None and not cwe_ids and not affected_products and not ssvc:
        return None

    parsed: dict[str, Any] = {
        "cve_id": cve_id,
        "cvss_score": cvss_score,
        "severity": severity if cvss_score is not None else "UNKNOWN",
        "cwe_ids": cwe_ids,
        "affected_products": affected_products,
        "published": meta.get("datePublished") or "",
        "modified": meta.get("dateUpdated") or "",
        "description": "",
    }
    if ssvc:
        parsed["ssvc"] = ssvc
    return parsed


def parse_cvelistv5_record(record: dict) -> dict | None:
    """Parse a full cvelistV5 CVE record; CNA metrics take precedence over ADP."""
    if not isinstance(record, dict):
        return None
    meta = record.get("cveMetadata")
    if not isinstance(meta, dict):
        return None
    cve_id = (meta.get("cveId") or "").upper()
    if not CVE_ID_RE.match(cve_id):
        return None
    if is_cve_record_rejected(record):
        return None

    containers = record.get("containers")
    if not isinstance(containers, dict):
        return None
    cna = containers.get("cna") if isinstance(containers.get("cna"), dict) else {}
    adp_list = containers.get("adp") if isinstance(containers.get("adp"), list) else []
    cisa_adp = _find_cisa_adp(adp_list)

    description = _extract_description(cna) or _extract_description(cisa_adp)

    cvss_score, severity = _extract_cvss(cna.get("metrics"))
    if cvss_score is None:
        cvss_score, severity = _extract_cvss(cisa_adp.get("metrics") if cisa_adp else None)

    cwe_ids = _extract_cwes(cna)
    if not cwe_ids:
        cwe_ids = _extract_cwes(cisa_adp)

    affected_products = _extract_affected_products(cna, cisa_adp)

    return {
        "cve_id": cve_id,
        "description": description,
        "cvss_score": cvss_score,
        "severity": severity if cvss_score is not None else "UNKNOWN",
        "published": meta.get("datePublished") or "",
        "modified": meta.get("dateUpdated") or "",
        "affected_products": affected_products,
        "cwe_ids": cwe_ids,
    }


def merge_additive_cve_fields(existing: dict, incoming: dict) -> dict | None:
    """Merge enrichment into an existing row without downgrading richer data.

    Returns a dict of column updates, or None when nothing would change.
    """
    updates: dict[str, Any] = {}

    incoming_cvss = incoming.get("cvss_score")
    existing_cvss = existing.get("cvss_score")
    if incoming_cvss is not None and existing_cvss is None:
        updates["cvss_score"] = incoming_cvss

    incoming_severity = (incoming.get("severity") or "UNKNOWN").upper()
    existing_severity = (existing.get("severity") or "UNKNOWN").upper()
    if incoming_severity != "UNKNOWN":
        if existing_severity in ("", "UNKNOWN"):
            updates["severity"] = incoming_severity
        elif (
            SEVERITY_RANK.get(incoming_severity, 0)
            > SEVERITY_RANK.get(existing_severity, 0)
        ):
            updates["severity"] = incoming_severity

    existing_cwes = existing.get("cwe_ids") or []
    if isinstance(existing_cwes, str):
        try:
            existing_cwes = json.loads(existing_cwes)
        except json.JSONDecodeError:
            existing_cwes = []
    incoming_cwes = incoming.get("cwe_ids") or []
    merged_cwes = sorted({str(c).upper() for c in existing_cwes if c} | {str(c).upper() for c in incoming_cwes if c})
    if merged_cwes != sorted({str(c).upper() for c in existing_cwes if c}):
        updates["cwe_ids"] = merged_cwes

    if not (existing.get("description") or "").strip():
        incoming_desc = (incoming.get("description") or "").strip()
        if incoming_desc:
            updates["description"] = incoming_desc

    existing_products = existing.get("affected_products") or []
    if isinstance(existing_products, str):
        try:
            existing_products = json.loads(existing_products)
        except json.JSONDecodeError:
            existing_products = []
    incoming_products = incoming.get("affected_products") or []
    merged_products = sorted(
        {str(p) for p in existing_products if p} | {str(p) for p in incoming_products if p}
    )
    if merged_products != sorted({str(p) for p in existing_products if p}):
        updates["affected_products"] = merged_products

    if not (existing.get("published") or "").strip():
        published = (incoming.get("published") or "").strip()
        if published:
            updates["published"] = published

    if not (existing.get("modified") or "").strip():
        modified = (incoming.get("modified") or "").strip()
        if modified:
            updates["modified"] = modified

    return updates or None
