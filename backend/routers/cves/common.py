"""CVE router package.

Split from `routers.cves` (F1.2) without changing route registration order or
handler behavior.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

import json


def row_to_cve_dict(row) -> dict:
    d = dict(row)
    for field in ("affected_products", "source_urls", "cwe_ids"):
        val = d.get(field)
        if val and isinstance(val, str):
            try:
                d[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        elif not val:
            # NULL/'' columns surface as a stable [] — API_REFERENCE.md
            # documents these fields as arrays, never null.
            d[field] = []
    for num_field in ("cvss_score", "epss_score", "epss_percentile"):
        if d.get(num_field) is not None:
            try:
                d[num_field] = float(d[num_field])
            except (TypeError, ValueError):
                d[num_field] = None
    d["is_kev"] = bool(d.get("is_kev", 0))
    d["has_poc"] = bool(d.get("has_poc", 0))
    if "affected_products_source" in d:
        # '' = official CPE / unset; 'llm' = LLM-extracted (provenance marker)
        d["affected_products_source"] = d.get("affected_products_source") or ""
    d["patch_available"] = bool(d.get("patch_available", 0))
    d["has_ai_context"] = bool(d.get("has_ai_context", 0))
    d["member_of_campaign"] = bool(d.pop("member_of_campaign", 0))
    lifecycle = d.pop("campaign_lifecycle", None)
    if d["member_of_campaign"] and lifecycle:
        d["campaign_lifecycle"] = str(lifecycle).strip() or None
    kev_date = d.get("kev_date_added")
    d["kev_date_added"] = (kev_date or "").strip() or None
    kev_due = d.get("kev_due_date")
    d["kev_due_date"] = (kev_due or "").strip() or None
    d["kev_ransomware_use"] = bool(d.pop("kev_ransomware_use", 0))
    wl_state = d.pop("watchlist_state", None)
    wl_snooze = d.pop("watchlist_snooze_until", None)
    if wl_state:
        d["watchlist_state"] = wl_state
        d["watchlist_snooze_until"] = (wl_snooze or "").strip() or None
    return d


_row_to_cve_dict = row_to_cve_dict
