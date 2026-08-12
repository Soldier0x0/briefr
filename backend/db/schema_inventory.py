"""Intel vs app schema table inventory (ADR-001 / plan Appendix A).

Single source of truth for Alembic 036, export scripts, and verification tools.
"""

from __future__ import annotations

INTEL_TABLES: tuple[str, ...] = (
    "cves",
    "kev_deadlines",
    "epss_history",
    "cve_change_history",
    "mitre_techniques",
    "cve_technique_map",
    "atlas_techniques",
    "atlas_case_studies",
    "cve_atlas_map",
    "cve_exploits",
    "otx_pulses",
    "otx_cve_pulses",
    "otx_pulse_iocs",
    "detection_rules",
    "detection_rule_cves",
    "detection_rule_techniques",
    "correlation_actor",
    "correlation_temporal",
    "correlation_campaigns",
    "correlation_campaign_members",
    "correlation_cve_snapshot",
    "cve_embeddings",
    "embeddings",
    "mitre_groups",
    "group_technique_map",
    "pulse_families",
    "ioc_degree",
    "software_catalog",
    "feed_cache",
    "sync_state",
)

APP_TABLES: tuple[str, ...] = (
    "users",
    "sessions",
    "user_preferences",
    "app_settings",
    "ioc_cache",
    "ioc_watchlist",
    "threatfox_iocs",
    "ti_mirror_iocs",
    "infra_classifications",
    "watchlist",
    "audit_log",
    "api_usage",
    "api_call_events",
    "webhook_destinations",
    "webhook_delivery_log",
    "webhook_alert_log",
    "webhook_destination_dedupe",
    "correlation_suppressions",
    "correlation_feedback",
    "hunt_packs",
    "detection_backlog",
    "user_notifications",
    "search_api_tokens",
    "ai_operations",
    "ai_operation_payloads",
    "stack_backfill_runs",
    "stack_backfill_checkpoints",
    "correlation_metrics",
    "resource_metrics",
)

OPERATOR_GUARD_TABLES: tuple[str, ...] = (
    "users",
    "sessions",
    "user_preferences",
)

FORBIDDEN_EXPORT_TABLES: frozenset[str] = frozenset(APP_TABLES) | frozenset(
    {"alembic_version"}
)

SYNC_STATE_INGEST_KEYS: frozenset[str] = frozenset({
    "nvd_last_mod_end",
    "epss_backfill_done",
    "epss_csv_file_identity",
    "atlas_upstream_version",
    "cvelistv5_head_sha",
    "poc_github_commit",
    "correlation_build_watermark",
    "correlation_last_run",
    "sigmahq_archive_identity",
})

# Prefixes safe to publish in intel feed_cache bundles (operator keys excluded).
FEED_CACHE_PUBLISH_PREFIXES: tuple[str, ...] = (
    "ssvc:",
    "correlation:v1:",
    "correlation:v2:",
    "circl:",
    "circl_miss:",
    "sploitus:",
    "otx:cve:",
    "otx:pulse:",
    "otx:ioc:",
    "malwarebazaar:",
    "urlhaus:",
    "greynoise:",
    "sigma:",
    "elastic:",
    "incident_rss:",
)

FEED_CACHE_FORBIDDEN_EXACT: frozenset[str] = frozenset({
    "admin_db_integrity",
    "incident_feed:snapshot",
    "wallboard:snapshot",
})

# Move order: parents before children within each schema (FK-safe).
INTEL_TABLE_MOVE_ORDER: tuple[str, ...] = (
    "cves",
    "kev_deadlines",
    "epss_history",
    "cve_change_history",
    "mitre_techniques",
    "atlas_techniques",
    "atlas_case_studies",
    "cve_exploits",
    "otx_pulses",
    "detection_rules",
    "correlation_actor",
    "correlation_temporal",
    "correlation_campaigns",
    "correlation_cve_snapshot",
    "mitre_groups",
    "pulse_families",
    "ioc_degree",
    "software_catalog",
    "feed_cache",
    "cve_technique_map",
    "cve_atlas_map",
    "otx_cve_pulses",
    "otx_pulse_iocs",
    "detection_rule_cves",
    "detection_rule_techniques",
    "correlation_campaign_members",
    "cve_embeddings",
    "embeddings",
    "group_technique_map",
    "sync_state",
)

APP_TABLE_MOVE_ORDER: tuple[str, ...] = (
    "users",
    "stack_backfill_runs",
    "webhook_destinations",
    "app_settings",
    "ioc_cache",
    "ioc_watchlist",
    "threatfox_iocs",
    "ti_mirror_iocs",
    "infra_classifications",
    "watchlist",
    "audit_log",
    "api_usage",
    "api_call_events",
    "webhook_delivery_log",
    "webhook_alert_log",
    "webhook_destination_dedupe",
    "correlation_suppressions",
    "correlation_feedback",
    "hunt_packs",
    "detection_backlog",
    "search_api_tokens",
    "ai_operations",
    "correlation_metrics",
    "resource_metrics",
    "sessions",
    "user_preferences",
    "user_notifications",
    "ai_operation_payloads",
    "stack_backfill_checkpoints",
)

PUBLIC_INFRA_TABLES: frozenset[str] = frozenset({
    "alembic_version",
    "procrastinate_jobs",
    "procrastinate_events",
    "procrastinate_periodic_defers",
    "procrastinate_workers",
})


def table_schema(table: str) -> str:
    """Return ``intel`` or ``app`` for a classified BRIEFR table."""
    if table in INTEL_TABLES:
        return "intel"
    if table in APP_TABLES:
        return "app"
    raise KeyError(f"unclassified table: {table}")


def sync_state_qualified_table(key: str, *, postgres: bool, split: bool) -> str:
    """Qualified sync_state table for reads/writes."""
    if not postgres or not split:
        return "sync_state"
    if key in SYNC_STATE_INGEST_KEYS:
        return "intel.sync_state"
    return "app.sync_state"


def feed_cache_key_publishable(cache_key: str) -> bool:
    if cache_key in FEED_CACHE_FORBIDDEN_EXACT:
        return False
    if cache_key.startswith(("llm_products:", "llm_products_raw:", "detection_ctx")):
        return False
    return any(cache_key.startswith(prefix) for prefix in FEED_CACHE_PUBLISH_PREFIXES)
