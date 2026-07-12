"""Read-only DB explorer allowlist — deny-by-default table registry.

Only tables listed here are browsable via /api/admin/db-explorer/*. Column names,
filters, and ORDER BY clauses are static; user input never becomes SQL fragments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExplorerTier = Literal[1, 2]

TRUNCATE_BYTES = 2048
MAX_ROW_LIMIT = 100
DEFAULT_ROW_LIMIT = 50
MAX_OFFSET = 10_000
MAX_FILTER_LEN = 256

_TABLE_NAME_RE = __import__("re").compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True)
class TableSpec:
    name: str
    tier: ExplorerTier
    label: str
    columns: tuple[str, ...]
    filter_columns: frozenset[str]
    order_by: str
    required_filter: str | None = None
    redact_columns: frozenset[str] = frozenset()
    truncate_columns: frozenset[str] = frozenset()


def _spec(
    name: str,
    tier: ExplorerTier,
    label: str,
    columns: tuple[str, ...],
    *,
    filter_columns: tuple[str, ...] = (),
    order_by: str,
    required_filter: str | None = None,
    redact_columns: tuple[str, ...] = (),
    truncate_columns: tuple[str, ...] = (),
) -> TableSpec:
    return TableSpec(
        name=name,
        tier=tier,
        label=label,
        columns=columns,
        filter_columns=frozenset(filter_columns),
        order_by=order_by,
        required_filter=required_filter,
        redact_columns=frozenset(redact_columns),
        truncate_columns=frozenset(truncate_columns),
    )


# Tier 1 — INTEL / ops-safe browse
_TIER1: tuple[TableSpec, ...] = (
    _spec(
        "cves",
        1,
        "CVEs",
        (
            "cve_id", "description", "cvss_score", "severity", "published", "modified",
            "affected_products", "affected_products_source", "mitre_technique", "summary",
            "is_kev", "epss_score", "epss_percentile", "has_poc", "patch_available",
            "has_ai_context", "source_urls", "cwe_ids", "cpe_matches",
            "is_vulncheck_exploited", "updated_at",
        ),
        filter_columns=("cve_id",),
        order_by="modified DESC, cve_id ASC",
        required_filter="cve_id",
        truncate_columns=("description", "summary", "source_urls", "cpe_matches", "affected_products"),
    ),
    _spec(
        "kev_deadlines",
        1,
        "KEV deadlines",
        (
            "cve_id", "product", "short_description", "required_action", "due_date",
            "date_added", "vendor_project", "vulnerability_name", "known_ransomware",
            "cwes", "updated_at",
        ),
        filter_columns=("cve_id",),
        order_by="date_added DESC, cve_id ASC",
        truncate_columns=("short_description", "required_action", "cwes"),
    ),
    _spec(
        "epss_history",
        1,
        "EPSS history",
        ("cve_id", "score", "recorded_date"),
        filter_columns=("cve_id",),
        order_by="recorded_date DESC, cve_id ASC",
    ),
    _spec(
        "cve_change_history",
        1,
        "CVE change history",
        ("id", "cve_id", "field_name", "old_value", "new_value", "detected_at"),
        filter_columns=("cve_id", "field_name"),
        order_by="detected_at DESC, id DESC",
        truncate_columns=("old_value", "new_value"),
    ),
    _spec(
        "mitre_techniques",
        1,
        "MITRE techniques",
        ("technique_id", "name", "description", "tactic", "url", "platforms", "detection"),
        filter_columns=("technique_id",),
        order_by="technique_id ASC",
        truncate_columns=("description", "detection", "platforms"),
    ),
    _spec(
        "mitre_groups",
        1,
        "MITRE groups",
        ("group_id", "name", "aliases", "description", "sectors", "url"),
        filter_columns=("group_id",),
        order_by="group_id ASC",
        truncate_columns=("description", "aliases", "sectors"),
    ),
    _spec(
        "cve_technique_map",
        1,
        "CVE ↔ technique",
        ("cve_id", "technique_id"),
        filter_columns=("cve_id", "technique_id"),
        order_by="cve_id ASC, technique_id ASC",
    ),
    _spec(
        "group_technique_map",
        1,
        "Group ↔ technique",
        ("group_id", "technique_id"),
        filter_columns=("group_id", "technique_id"),
        order_by="group_id ASC, technique_id ASC",
    ),
    _spec(
        "atlas_techniques",
        1,
        "ATLAS techniques",
        ("technique_id", "name", "description", "tactic", "tactic_id", "url"),
        filter_columns=("technique_id",),
        order_by="technique_id ASC",
        truncate_columns=("description",),
    ),
    _spec(
        "atlas_case_studies",
        1,
        "ATLAS case studies",
        (
            "study_id", "name", "summary", "summary_full", "techniques", "target",
            "date", "study_type", "cve_ids",
        ),
        filter_columns=("study_id",),
        order_by="date DESC, study_id ASC",
        truncate_columns=("summary", "summary_full", "techniques", "cve_ids"),
    ),
    _spec(
        "cve_atlas_map",
        1,
        "CVE ↔ ATLAS",
        ("cve_id", "technique_id"),
        filter_columns=("cve_id", "technique_id"),
        order_by="cve_id ASC, technique_id ASC",
    ),
    _spec(
        "cve_exploits",
        1,
        "CVE exploits",
        (
            "id", "cve_id", "title", "type", "source", "url", "published_date",
            "fetched_at",
        ),
        filter_columns=("cve_id",),
        order_by="fetched_at DESC, id DESC",
    ),
    _spec(
        "cve_embeddings",
        1,
        "CVE embeddings",
        ("cve_id", "model", "dim", "updated_at"),
        filter_columns=("cve_id", "model"),
        order_by="updated_at DESC, cve_id ASC",
    ),
    _spec(
        "otx_cve_pulses",
        1,
        "OTX CVE pulses",
        (
            "cve_id", "pulse_id", "pulse_name", "author", "created_date", "adversary",
            "malware_families", "ioc_count", "tags", "targeted_countries", "fetched_at",
        ),
        filter_columns=("cve_id", "pulse_id"),
        order_by="fetched_at DESC, pulse_id ASC",
        truncate_columns=("malware_families", "tags", "targeted_countries"),
    ),
    _spec(
        "otx_pulse_iocs",
        1,
        "OTX pulse IOCs",
        ("pulse_id", "ioc_type", "ioc_value", "description", "fetched_at"),
        filter_columns=("pulse_id", "ioc_value"),
        order_by="fetched_at DESC, pulse_id ASC",
        truncate_columns=("description",),
    ),
    _spec(
        "otx_pulses",
        1,
        "OTX pulses",
        (
            "pulse_id", "pulse_name", "author", "created_date", "adversary",
            "malware_families", "tags", "targeted_countries", "ioc_count", "fetched_at",
        ),
        filter_columns=("pulse_id",),
        order_by="fetched_at DESC, pulse_id ASC",
        truncate_columns=("malware_families", "tags", "targeted_countries"),
    ),
    _spec(
        "correlation_actor",
        1,
        "Correlation — actors",
        (
            "cve_id", "actor_name", "actor_sectors", "user_sector_match", "confidence",
            "detected_at",
        ),
        filter_columns=("cve_id", "actor_name"),
        order_by="detected_at DESC, cve_id ASC",
        truncate_columns=("actor_sectors",),
    ),
    _spec(
        "correlation_temporal",
        1,
        "Correlation — temporal",
        (
            "vendor", "current_week_count", "average_weekly_count", "anomaly_score",
            "detected_at",
        ),
        filter_columns=("vendor",),
        order_by="anomaly_score DESC, vendor ASC",
    ),
    _spec(
        "correlation_campaigns",
        1,
        "Correlation — campaigns",
        (
            "campaign_id", "primary_pulse_id", "label", "adversary", "malware_families",
            "tags", "targeted_countries", "confidence", "member_count", "lifecycle",
            "campaign_version", "computed_at",
        ),
        filter_columns=("campaign_id", "primary_pulse_id"),
        order_by="computed_at DESC, campaign_id ASC",
        truncate_columns=("malware_families", "tags", "targeted_countries"),
    ),
    _spec(
        "correlation_campaign_members",
        1,
        "Correlation — campaign members",
        ("campaign_id", "cve_id", "role"),
        filter_columns=("campaign_id", "cve_id"),
        order_by="campaign_id ASC, cve_id ASC",
    ),
)

# Tier 2 — browse with heavy masking
_TIER2: tuple[TableSpec, ...] = (
    _spec(
        "audit_log",
        2,
        "Audit log",
        ("id", "actor", "action", "target", "created_at"),
        filter_columns=("action", "actor"),
        order_by="created_at DESC, id DESC",
        redact_columns=("target",),
        truncate_columns=("target",),
    ),
    _spec(
        "webhook_delivery_log",
        2,
        "Webhook delivery log",
        (
            "id", "destination_id", "event_type", "dedupe_key", "status", "error",
            "attempted_at",
        ),
        filter_columns=("destination_id", "event_type", "status"),
        order_by="attempted_at DESC, id DESC",
        redact_columns=("error",),
        truncate_columns=("error", "dedupe_key"),
    ),
    _spec(
        "ai_operations",
        2,
        "AI operations",
        (
            "id", "operation_id", "request_id", "started_at", "latency_ms", "feature",
            "task_class", "provider", "model", "success", "error_class", "input_tokens",
            "output_tokens", "total_tokens", "estimated_cost_usd", "fallback_from_provider",
            "fallback_from_model", "retry_index", "context_type", "context_id",
        ),
        filter_columns=("feature", "provider", "context_id", "operation_id"),
        order_by="started_at DESC, id DESC",
    ),
)

TABLE_REGISTRY: dict[str, TableSpec] = {
    spec.name: spec for spec in (*_TIER1, *_TIER2)
}


def validate_table_name(name: str) -> TableSpec | None:
    """Return spec when browsable; None when unknown or denied (caller returns 404)."""
    if not name or not _TABLE_NAME_RE.match(name):
        return None
    return TABLE_REGISTRY.get(name)


def list_table_specs() -> list[TableSpec]:
    return sorted(TABLE_REGISTRY.values(), key=lambda s: (s.tier, s.name))
