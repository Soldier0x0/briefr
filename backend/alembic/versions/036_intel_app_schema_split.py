"""Split BRIEFR tables into intel and app schemas (one-time, in-place).

Revision ID: 036_intel_app_schema_split
Revises: 035_detection_rules_sigmahq

Runs once when Alembic applies this revision during deploy (``alembic upgrade
head``). Subsequent backend starts skip Alembic when already at head — the
``SET SCHEMA`` moves are **not** re-run on every process start or ``briefr-update``.

Idempotent steps: safe to retry if a step partially completed before failure.
``alembic_version`` stays in ``public`` for bootstrap compatibility.
Procrastinate objects remain in ``public``.
"""

from __future__ import annotations

from alembic import op

revision = "036_intel_app_schema_split"
down_revision = "035_detection_rules_sigmahq"
branch_labels = None
depends_on = None

_INGEST_KEYS_SQL = (
    "'nvd_last_mod_end', 'epss_backfill_done', 'epss_csv_file_identity', "
    "'atlas_upstream_version', 'cvelistv5_head_sha', 'poc_github_commit', "
    "'correlation_build_watermark', 'correlation_last_run', 'sigmahq_archive_identity'"
)

_INTEL_ORDER = (
    "cves", "kev_deadlines", "epss_history", "cve_change_history",
    "mitre_techniques", "atlas_techniques", "atlas_case_studies", "cve_exploits",
    "otx_pulses", "detection_rules", "correlation_actor", "correlation_temporal",
    "correlation_campaigns", "correlation_cve_snapshot", "mitre_groups",
    "pulse_families", "ioc_degree", "software_catalog", "feed_cache",
    "cve_technique_map", "cve_atlas_map", "otx_cve_pulses", "otx_pulse_iocs",
    "detection_rule_cves", "detection_rule_techniques",
    "correlation_campaign_members", "cve_embeddings", "embeddings",
    "group_technique_map", "sync_state",
)

_APP_ORDER = (
    "users", "stack_backfill_runs", "webhook_destinations", "app_settings",
    "ioc_cache", "ioc_watchlist", "threatfox_iocs", "watchlist", "audit_log",
    "api_usage", "api_call_events", "webhook_delivery_log", "webhook_alert_log",
    "webhook_destination_dedupe", "correlation_suppressions", "correlation_feedback",
    "hunt_packs", "detection_backlog", "search_api_tokens", "ai_operations",
    "correlation_metrics", "resource_metrics", "sessions", "user_preferences",
    "user_notifications", "ai_operation_payloads", "stack_backfill_checkpoints",
)


def _move_table_if_in_public(table: str, target_schema: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = '{table}'
            ) THEN
                EXECUTE 'ALTER TABLE public.{table} SET SCHEMA {target_schema}';
            END IF;
        END $$;
        """
    )


def _split_sync_state_if_needed() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'sync_state'
            ) THEN
                RETURN;
            END IF;

            CREATE TABLE IF NOT EXISTS app.sync_state (
                LIKE public.sync_state INCLUDING ALL
            );

            INSERT INTO app.sync_state (key, value, updated_at)
            SELECT key, value, updated_at
            FROM public.sync_state
            WHERE key NOT IN ("""
        + _INGEST_KEYS_SQL
        + """)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at;

            DELETE FROM public.sync_state
            WHERE key NOT IN ("""
        + _INGEST_KEYS_SQL
        + """);
        END $$;
        """
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS intel")
    op.execute("CREATE SCHEMA IF NOT EXISTS app")

    _split_sync_state_if_needed()

    for table in _INTEL_ORDER:
        _move_table_if_in_public(table, "intel")

    for table in _APP_ORDER:
        _move_table_if_in_public(table, "app")


def downgrade() -> None:
    raise NotImplementedError(
        "036_intel_app_schema_split downgrade is not supported — restore encrypted backup"
    )
