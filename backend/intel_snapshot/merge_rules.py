"""Per-table merge strategies for intel snapshot import."""

from __future__ import annotations

from db.schema_inventory import INTEL_TABLE_MOVE_ORDER

MERGE_STRATEGIES: dict[str, str] = {
    "cves": "update",
    "kev_deadlines": "update",
    "epss_history": "nothing",
    "cve_change_history": "nothing",
    "mitre_techniques": "update",
    "cve_technique_map": "nothing",
    "atlas_techniques": "update",
    "atlas_case_studies": "update",
    "cve_atlas_map": "nothing",
    "cve_exploits": "nothing",
    "otx_pulses": "update",
    "otx_cve_pulses": "nothing",
    "otx_pulse_iocs": "nothing",
    "detection_rules": "update",
    "detection_rule_cves": "nothing",
    "detection_rule_techniques": "nothing",
    "correlation_actor": "update",
    "correlation_temporal": "update",
    "correlation_campaigns": "update",
    "correlation_campaign_members": "nothing",
    "correlation_cve_snapshot": "update",
    "cve_embeddings": "update",
    "embeddings": "update",
    "mitre_groups": "update",
    "group_technique_map": "nothing",
    "pulse_families": "update",
    "ioc_degree": "update",
    "software_catalog": "update",
    "feed_cache": "update",
    "sync_state": "update",
}

MERGE_TABLE_ORDER: tuple[str, ...] = INTEL_TABLE_MOVE_ORDER
