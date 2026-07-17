"""DB init/bootstrap: get_db, init_db, run_postgres_migrations. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): runtime fixup SQL is dialect-neutral (no placeholders);
SQLite bootstrap DDL in ``init_db`` is not translated. Postgres schema is applied via
Alembic in ``run_postgres_migrations``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from db.config import is_postgres
from db.connection import get_connection
from db.types import DbConnection

_NORMALIZE_EPSS_SCORES_SQL = (
    "UPDATE cves SET epss_score = NULL WHERE epss_score = 0.0"
)

_CREATE_IDX_CVES_HAS_POC_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_cves_has_poc ON cves(has_poc)"
)

_CREATE_IDX_CVES_MODIFIED_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_cves_modified ON cves(modified)"
)

_ALEMBIC_VERSION_SQL = "SELECT version_num FROM alembic_version LIMIT 1"

_RESOURCE_METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS resource_metrics (
    ts TEXT PRIMARY KEY,
    briefr_cpu_pct REAL,
    briefr_rss_bytes INTEGER,
    briefr_io_read_bps REAL,
    briefr_io_write_bps REAL,
    briefr_iops_r REAL,
    briefr_iops_w REAL,
    pg_cpu_pct REAL,
    pg_rss_bytes INTEGER,
    pg_iops_r REAL,
    pg_iops_w REAL,
    req_count INTEGER,
    pg_xact_per_min REAL,
    pg_blks_read_per_min REAL,
    pg_cache_hit_pct REAL,
    pg_db_size_bytes INTEGER,
    disk_free_bytes INTEGER,
    sys_cpu_pct REAL,
    sys_mem_pct REAL
)
"""

_RESOURCE_METRICS_IDX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_resource_metrics_ts ON resource_metrics(ts)"
)


async def get_db() -> DbConnection:
    """Return a database connection (SQLite default, PostgreSQL when configured)."""
    return await get_connection()


async def _normalize_epss_scores(db: DbConnection) -> None:
    await db.execute(_NORMALIZE_EPSS_SCORES_SQL)

async def run_postgres_migrations() -> None:
    """Apply Alembic DDL before the asyncpg pool opens (avoids migration lock waits)."""
    import logging

    import asyncpg
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from db.config import postgres_dsn

    log = logging.getLogger(__name__)
    # __file__ is backend/db/init.py — alembic.ini lives in backend/, one
    # level up from this module's own directory (it was backend/database.py
    # before the Phase 3 split, where .parent already pointed at backend/).
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    head = ScriptDirectory.from_config(alembic_cfg).get_current_head()

    current: str | None = None
    skip_alembic = False
    try:
        conn = await asyncpg.connect(postgres_dsn(), timeout=15)
        try:
            row = await conn.fetchrow(_ALEMBIC_VERSION_SQL)
            current = row["version_num"] if row else None
            skip_alembic = current == head
        except asyncpg.UndefinedTableError:
            current = None
        finally:
            await conn.close()
    except Exception as exc:
        log.warning(
            "database.py run_postgres_migrations(): version check failed (%s) — falling back to Alembic",
            exc,
        )

    if skip_alembic:
        log.info(
            "database.py run_postgres_migrations(): already at head (%s) — skipping Alembic",
            head,
        )
        return

    log.info(
        "database.py run_postgres_migrations(): current=%s head=%s — running Alembic upgrade head",
        current or "(none)",
        head,
    )
    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    except Exception as exc:
        log.error(
            "database.py run_postgres_migrations(): Alembic failed — %s. "
            "Check DATABASE_URL and that Postgres is running.",
            exc,
        )
        raise
    log.info("database.py run_postgres_migrations(): Alembic upgrade head finished")

async def _init_postgres_schema() -> None:
    db = await get_db()
    try:
        await _normalize_epss_scores(db)
        await db.commit()
    finally:
        await db.close()

async def init_db() -> None:
    if is_postgres():
        await _init_postgres_schema()
        return

    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS cves (
                cve_id TEXT PRIMARY KEY,
                description TEXT,
                cvss_score REAL,
                severity TEXT,
                published TEXT,
                modified TEXT,
                affected_products TEXT DEFAULT '[]',
                affected_products_source TEXT DEFAULT '',
                mitre_technique TEXT,
                summary TEXT,
                is_kev INTEGER DEFAULT 0,
                epss_score REAL,
                epss_percentile REAL,
                has_poc INTEGER DEFAULT 0,
                patch_available INTEGER DEFAULT 0,
                has_ai_context INTEGER DEFAULT 0,
                source_urls TEXT DEFAULT '[]',
                cwe_ids TEXT DEFAULT '[]',
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_cves_severity ON cves(severity);
            CREATE INDEX IF NOT EXISTS idx_cves_published ON cves(published);
            CREATE INDEX IF NOT EXISTS idx_cves_modified ON cves(modified);
            CREATE INDEX IF NOT EXISTS idx_cves_is_kev ON cves(is_kev);
            CREATE INDEX IF NOT EXISTS idx_cves_epss ON cves(epss_score);

            CREATE TABLE IF NOT EXISTS ioc_cache (
                value TEXT PRIMARY KEY,
                ioc_type TEXT NOT NULL,
                result TEXT NOT NULL,
                cached_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_ioc_cached_at ON ioc_cache(cached_at);

            CREATE TABLE IF NOT EXISTS kev_deadlines (
                cve_id TEXT PRIMARY KEY,
                product TEXT,
                short_description TEXT,
                required_action TEXT,
                due_date TEXT,
                date_added TEXT,
                vendor_project TEXT DEFAULT '',
                vulnerability_name TEXT DEFAULT '',
                known_ransomware TEXT DEFAULT '',
                cwes TEXT DEFAULT '[]',
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_kev_due_date ON kev_deadlines(due_date);
            CREATE INDEX IF NOT EXISTS idx_kev_date_added ON kev_deadlines(date_added);

            CREATE TABLE IF NOT EXISTS api_usage (
                service TEXT NOT NULL,
                date_utc TEXT NOT NULL,
                month_utc TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                last_called_at TEXT,
                PRIMARY KEY (service, date_utc)
            );

            CREATE INDEX IF NOT EXISTS idx_api_usage_month ON api_usage(month_utc);
            CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(date_utc);

            CREATE TABLE IF NOT EXISTS api_call_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                source TEXT NOT NULL,
                pacing_key TEXT,
                method TEXT NOT NULL,
                host TEXT,
                path_template TEXT,
                status_code INTEGER,
                ok INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER,
                actor_type TEXT,
                actor_id TEXT,
                job_id TEXT,
                run_id TEXT,
                queue_task TEXT,
                request_id TEXT,
                error_class TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_api_call_events_ts ON api_call_events(ts);
            CREATE INDEX IF NOT EXISTS idx_api_call_events_source_ts ON api_call_events(source, ts);

            CREATE TABLE IF NOT EXISTS software_catalog (
                cpe_uri TEXT PRIMARY KEY,
                vendor TEXT NOT NULL,
                product TEXT NOT NULL,
                version TEXT,
                display_name TEXT,
                category TEXT NOT NULL DEFAULT 'other',
                title TEXT,
                versions_json TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_software_catalog_product ON software_catalog(product);
            CREATE INDEX IF NOT EXISTS idx_software_catalog_vendor_product
                ON software_catalog(vendor, product);

            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS mitre_techniques (
                technique_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                tactic TEXT DEFAULT '',
                url TEXT NOT NULL,
                platforms TEXT DEFAULT '[]',
                detection TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS cve_technique_map (
                cve_id TEXT NOT NULL,
                technique_id TEXT NOT NULL,
                PRIMARY KEY (cve_id, technique_id),
                FOREIGN KEY (technique_id) REFERENCES mitre_techniques(technique_id)
            );

            CREATE INDEX IF NOT EXISTS idx_cve_technique_map_technique
                ON cve_technique_map(technique_id);
            CREATE INDEX IF NOT EXISTS idx_cve_technique_map_cve
                ON cve_technique_map(cve_id);

            CREATE TABLE IF NOT EXISTS atlas_techniques (
                technique_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                tactic TEXT DEFAULT '',
                tactic_id TEXT DEFAULT '',
                url TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_atlas_techniques_tactic
                ON atlas_techniques(tactic);

            CREATE TABLE IF NOT EXISTS atlas_case_studies (
                study_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                summary TEXT DEFAULT '',
                summary_full TEXT DEFAULT '',
                techniques TEXT DEFAULT '[]',
                target TEXT DEFAULT '',
                date TEXT DEFAULT '',
                study_type TEXT DEFAULT '',
                cve_ids TEXT DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_atlas_case_studies_date
                ON atlas_case_studies(date);

            CREATE TABLE IF NOT EXISTS cve_atlas_map (
                cve_id TEXT NOT NULL,
                technique_id TEXT NOT NULL,
                PRIMARY KEY (cve_id, technique_id),
                FOREIGN KEY (technique_id) REFERENCES atlas_techniques(technique_id)
            );

            CREATE INDEX IF NOT EXISTS idx_cve_atlas_map_cve
                ON cve_atlas_map(cve_id);

            CREATE TABLE IF NOT EXISTS epss_history (
                cve_id TEXT NOT NULL,
                score REAL NOT NULL,
                recorded_date TEXT NOT NULL,
                PRIMARY KEY (cve_id, recorded_date)
            );

            CREATE INDEX IF NOT EXISTS idx_epss_history_cve_date
                ON epss_history(cve_id, recorded_date);

            CREATE TABLE IF NOT EXISTS cve_exploits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT 'poc',
                source TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                published_date TEXT DEFAULT '',
                fetched_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_cve_exploits_cve
                ON cve_exploits(cve_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cve_exploits_cve_url
                ON cve_exploits(cve_id, url);

            CREATE TABLE IF NOT EXISTS feed_cache (
                cache_key TEXT PRIMARY KEY,
                result TEXT NOT NULL,
                cached_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_feed_cache_cached_at
                ON feed_cache(cached_at);

            CREATE TABLE IF NOT EXISTS cve_change_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT NOT NULL DEFAULT '',
                new_value TEXT NOT NULL DEFAULT '',
                detected_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_cve_change_history_cve
                ON cve_change_history(cve_id);
            CREATE INDEX IF NOT EXISTS idx_cve_change_history_detected
                ON cve_change_history(detected_at);
            CREATE INDEX IF NOT EXISTS idx_cve_change_history_field
                ON cve_change_history(field_name);

            CREATE TABLE IF NOT EXISTS otx_cve_pulses (
                cve_id TEXT NOT NULL,
                pulse_id TEXT NOT NULL,
                pulse_name TEXT NOT NULL DEFAULT '',
                author TEXT DEFAULT '',
                created_date TEXT DEFAULT '',
                adversary TEXT DEFAULT '',
                malware_families TEXT DEFAULT '[]',
                ioc_count INTEGER DEFAULT 0,
                tags TEXT DEFAULT '[]',
                fetched_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (cve_id, pulse_id)
            );

            CREATE INDEX IF NOT EXISTS idx_otx_cve_pulses_cve
                ON otx_cve_pulses(cve_id);

            CREATE INDEX IF NOT EXISTS idx_otx_cve_pulses_pulse
                ON otx_cve_pulses(pulse_id);

            CREATE TABLE IF NOT EXISTS otx_pulse_iocs (
                pulse_id TEXT NOT NULL,
                ioc_type TEXT NOT NULL DEFAULT '',
                ioc_value TEXT NOT NULL,
                description TEXT DEFAULT '',
                fetched_at TEXT DEFAULT (datetime('now')),
                observed_at TEXT,
                PRIMARY KEY (pulse_id, ioc_type, ioc_value)
            );

            CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_pulse
                ON otx_pulse_iocs(pulse_id);

            CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_value
                ON otx_pulse_iocs(ioc_value);

            CREATE TABLE IF NOT EXISTS otx_pulses (
                pulse_id TEXT PRIMARY KEY,
                pulse_name TEXT NOT NULL DEFAULT '',
                author TEXT DEFAULT '',
                created_date TEXT DEFAULT '',
                adversary TEXT DEFAULT '',
                malware_families TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                targeted_countries TEXT DEFAULT '[]',
                ioc_count INTEGER DEFAULT 0,
                fetched_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS correlation_campaigns (
                campaign_id TEXT PRIMARY KEY,
                primary_pulse_id TEXT,
                label TEXT NOT NULL DEFAULT '',
                adversary TEXT DEFAULT '',
                malware_families TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                targeted_countries TEXT DEFAULT '[]',
                confidence TEXT DEFAULT 'medium',
                member_count INTEGER DEFAULT 0,
                lifecycle TEXT DEFAULT 'active',
                campaign_version TEXT DEFAULT '',
                computed_at TEXT DEFAULT (datetime('now')),
                family_id TEXT,
                first_seen TEXT,
                last_seen TEXT,
                independent_sources INTEGER DEFAULT 1,
                author_count INTEGER DEFAULT 1,
                retracted_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_correlation_campaigns_pulse
                ON correlation_campaigns(primary_pulse_id);

            CREATE TABLE IF NOT EXISTS pulse_families (
                pulse_id TEXT PRIMARY KEY,
                family_id TEXT NOT NULL,
                jaccard REAL,
                computed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_pulse_families_family
                ON pulse_families(family_id);

            CREATE TABLE IF NOT EXISTS correlation_campaign_members (
                campaign_id TEXT NOT NULL,
                cve_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                PRIMARY KEY (campaign_id, cve_id)
            );

            CREATE INDEX IF NOT EXISTS idx_correlation_campaign_members_cve
                ON correlation_campaign_members(cve_id);

            CREATE TABLE IF NOT EXISTS correlation_suppressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                reason TEXT DEFAULT '',
                dismissed_by TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE (cve_id, scope, scope_key)
            );

            CREATE INDEX IF NOT EXISTS idx_correlation_suppressions_cve
                ON correlation_suppressions(cve_id);

            CREATE TABLE IF NOT EXISTS correlation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                verdict TEXT NOT NULL,
                reason TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE (cve_id, scope, scope_key, verdict)
            );

            CREATE INDEX IF NOT EXISTS idx_correlation_feedback_cve
                ON correlation_feedback(cve_id);

            CREATE TABLE IF NOT EXISTS correlation_metrics (
                day TEXT PRIMARY KEY,
                computed_at TEXT,
                suppressions_30d INTEGER NOT NULL DEFAULT 0,
                feedback_confirm_30d INTEGER NOT NULL DEFAULT 0,
                feedback_reject_30d INTEGER NOT NULL DEFAULT 0,
                surfaced_findings_30d INTEGER NOT NULL DEFAULT 0,
                rejection_rate REAL,
                confirmation_rate REAL,
                weak_edge_ratio REAL,
                hub_suppressed_edge_count INTEGER NOT NULL DEFAULT 0,
                ioc_degree_p95 INTEGER NOT NULL DEFAULT 0,
                avg_independent_sources REAL,
                orphan_cve_ratio REAL,
                campaigns_active INTEGER NOT NULL DEFAULT 0,
                campaigns_retracted INTEGER NOT NULL DEFAULT 0,
                campaign_survival_rate REAL,
                campaign_member_count INTEGER NOT NULL DEFAULT 0,
                stale_campaign_ratio REAL,
                median_evidence_age_days REAL
            );

            CREATE TABLE IF NOT EXISTS ioc_degree (
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                cve_count INTEGER NOT NULL DEFAULT 0,
                pulse_count INTEGER NOT NULL DEFAULT 0,
                computed_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (ioc_type, ioc_value)
            );

            CREATE TABLE IF NOT EXISTS correlation_actor (
                cve_id TEXT NOT NULL,
                actor_name TEXT NOT NULL,
                actor_sectors TEXT DEFAULT '[]',
                user_sector_match INTEGER DEFAULT 0,
                confidence TEXT DEFAULT 'low',
                detected_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (cve_id, actor_name)
            );

            CREATE INDEX IF NOT EXISTS idx_correlation_actor_cve
                ON correlation_actor(cve_id);

            CREATE TABLE IF NOT EXISTS correlation_temporal (
                vendor TEXT PRIMARY KEY,
                current_week_count INTEGER DEFAULT 0,
                average_weekly_count REAL DEFAULT 0,
                anomaly_score REAL DEFAULT 0,
                detected_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS correlation_cve_snapshot (
                cve_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                engine_version TEXT NOT NULL DEFAULT '',
                computed_at TEXT NOT NULL,
                hub_edges_suppressed INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_correlation_cve_snapshot_computed
                ON correlation_cve_snapshot(computed_at);

            CREATE TABLE IF NOT EXISTS mitre_groups (
                group_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                aliases TEXT DEFAULT '[]',
                description TEXT DEFAULT '',
                sectors TEXT DEFAULT '[]',
                url TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS group_technique_map (
                group_id TEXT NOT NULL,
                technique_id TEXT NOT NULL,
                PRIMARY KEY (group_id, technique_id)
            );

            CREATE INDEX IF NOT EXISTS idx_group_technique_map_technique
                ON group_technique_map(technique_id);

            CREATE TABLE IF NOT EXISTS cve_embeddings (
                cve_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                dim INTEGER NOT NULL,
                vector BLOB NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_cve_embeddings_model
                ON cve_embeddings(model);

            CREATE TABLE IF NOT EXISTS hunt_packs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                technique_id TEXT NOT NULL,
                cve_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'medium',
                sigma_yaml TEXT NOT NULL DEFAULT '',
                siem_queries TEXT NOT NULL DEFAULT '{}',
                log_patterns TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE (technique_id, cve_id)
            );

            CREATE INDEX IF NOT EXISTS idx_hunt_packs_technique
                ON hunt_packs(technique_id);
            CREATE INDEX IF NOT EXISTS idx_hunt_packs_cve
                ON hunt_packs(cve_id);

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT '',
                metadata_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_audit_log_created
                ON audit_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_audit_log_action
                ON audit_log(action);

            CREATE TABLE IF NOT EXISTS watchlist (
                cve_id TEXT PRIMARY KEY,
                state TEXT NOT NULL CHECK(state IN ('pin', 'snooze')),
                snooze_until TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_watchlist_state
                ON watchlist(state);
            CREATE INDEX IF NOT EXISTS idx_watchlist_snooze_until
                ON watchlist(snooze_until);

            CREATE TABLE IF NOT EXISTS detection_backlog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                technique_id TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT 'kev_gap',
                priority TEXT NOT NULL DEFAULT 'high',
                status TEXT NOT NULL DEFAULT 'open',
                stack_terms TEXT NOT NULL DEFAULT '',
                technique_name TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                dismissed_at TEXT,
                UNIQUE (cve_id, technique_id, reason)
            );

            CREATE INDEX IF NOT EXISTS idx_detection_backlog_status
                ON detection_backlog(status);
            CREATE INDEX IF NOT EXISTS idx_detection_backlog_cve
                ON detection_backlog(cve_id);

            CREATE TABLE IF NOT EXISTS ioc_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE (user_id, ioc_type, ioc_value)
            );

            CREATE INDEX IF NOT EXISTS idx_ioc_watchlist_value
                ON ioc_watchlist(ioc_value);
            CREATE INDEX IF NOT EXISTS idx_ioc_watchlist_user
                ON ioc_watchlist(user_id);

            CREATE TABLE IF NOT EXISTS threatfox_iocs (
                ioc_id TEXT PRIMARY KEY,
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                raw_ioc TEXT NOT NULL DEFAULT '',
                malware TEXT NOT NULL DEFAULT '',
                threat_type TEXT NOT NULL DEFAULT '',
                confidence_level INTEGER NOT NULL DEFAULT 0,
                first_seen TEXT NOT NULL DEFAULT '',
                fetched_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_threatfox_iocs_value
                ON threatfox_iocs(ioc_value);
            CREATE INDEX IF NOT EXISTS idx_threatfox_iocs_type_value
                ON threatfox_iocs(ioc_type, ioc_value);

            CREATE TABLE IF NOT EXISTS resource_metrics (
                ts TEXT PRIMARY KEY,
                briefr_cpu_pct REAL,
                briefr_rss_bytes INTEGER,
                briefr_io_read_bps REAL,
                briefr_io_write_bps REAL,
                briefr_iops_r REAL,
                briefr_iops_w REAL,
                pg_cpu_pct REAL,
                pg_rss_bytes INTEGER,
                pg_iops_r REAL,
                pg_iops_w REAL,
                req_count INTEGER,
                pg_xact_per_min REAL,
                pg_blks_read_per_min REAL,
                pg_cache_hit_pct REAL,
                pg_db_size_bytes INTEGER,
                disk_free_bytes INTEGER,
                sys_cpu_pct REAL,
                sys_mem_pct REAL
            );

            CREATE INDEX IF NOT EXISTS idx_resource_metrics_ts
                ON resource_metrics(ts);
        """)
        await db.commit()

        for migration in (
            "ALTER TABLE kev_deadlines ADD COLUMN date_added TEXT DEFAULT ''",
            "ALTER TABLE kev_deadlines ADD COLUMN vendor_project TEXT DEFAULT ''",
            "ALTER TABLE kev_deadlines ADD COLUMN vulnerability_name TEXT DEFAULT ''",
            "ALTER TABLE kev_deadlines ADD COLUMN known_ransomware TEXT DEFAULT ''",
            "ALTER TABLE kev_deadlines ADD COLUMN cwes TEXT DEFAULT '[]'",
            "ALTER TABLE cves ADD COLUMN has_poc INTEGER DEFAULT 0",
            "ALTER TABLE cves ADD COLUMN epss_percentile REAL",
            "ALTER TABLE cves ADD COLUMN cpe_matches TEXT DEFAULT '[]'",
            "ALTER TABLE cves ADD COLUMN has_ai_context INTEGER DEFAULT 0",
            "ALTER TABLE cves ADD COLUMN affected_products_source TEXT DEFAULT ''",
            "ALTER TABLE mitre_techniques ADD COLUMN detection TEXT DEFAULT ''",
            "CREATE TABLE IF NOT EXISTS cve_atlas_map (cve_id TEXT NOT NULL, technique_id TEXT NOT NULL, PRIMARY KEY (cve_id, technique_id), FOREIGN KEY (technique_id) REFERENCES atlas_techniques(technique_id))",
            "CREATE INDEX IF NOT EXISTS idx_cve_atlas_map_cve ON cve_atlas_map(cve_id)",
            # Correlation engine tables (added in correlation session)
            "CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_value ON otx_pulse_iocs(ioc_value)",
            "CREATE TABLE IF NOT EXISTS correlation_actor (cve_id TEXT NOT NULL, actor_name TEXT NOT NULL, actor_sectors TEXT DEFAULT '[]', user_sector_match INTEGER DEFAULT 0, confidence TEXT DEFAULT 'low', detected_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (cve_id, actor_name))",
            "CREATE INDEX IF NOT EXISTS idx_correlation_actor_cve ON correlation_actor(cve_id)",
            "CREATE TABLE IF NOT EXISTS correlation_temporal (vendor TEXT PRIMARY KEY, current_week_count INTEGER DEFAULT 0, average_weekly_count REAL DEFAULT 0, anomaly_score REAL DEFAULT 0, detected_at TEXT DEFAULT (datetime('now')))",
            """
            CREATE TABLE IF NOT EXISTS correlation_cve_snapshot (
                cve_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                engine_version TEXT NOT NULL DEFAULT '',
                computed_at TEXT NOT NULL,
                hub_edges_suppressed INTEGER NOT NULL DEFAULT 0
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_correlation_cve_snapshot_computed ON correlation_cve_snapshot(computed_at)",
            "CREATE TABLE IF NOT EXISTS mitre_groups (group_id TEXT PRIMARY KEY, name TEXT NOT NULL, aliases TEXT DEFAULT '[]', description TEXT DEFAULT '', sectors TEXT DEFAULT '[]', url TEXT DEFAULT '')",
            "CREATE TABLE IF NOT EXISTS group_technique_map (group_id TEXT NOT NULL, technique_id TEXT NOT NULL, PRIMARY KEY (group_id, technique_id))",
            "CREATE INDEX IF NOT EXISTS idx_group_technique_map_technique ON group_technique_map(technique_id)",
            # Forge MVP (V1.3): saved hunt packs + CVE→pack linkage
            "CREATE TABLE IF NOT EXISTS hunt_packs (id INTEGER PRIMARY KEY AUTOINCREMENT, technique_id TEXT NOT NULL, cve_id TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '', priority TEXT NOT NULL DEFAULT 'medium', sigma_yaml TEXT NOT NULL DEFAULT '', siem_queries TEXT NOT NULL DEFAULT '{}', log_patterns TEXT NOT NULL DEFAULT '[]', notes TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')), UNIQUE (technique_id, cve_id))",
            "CREATE INDEX IF NOT EXISTS idx_hunt_packs_technique ON hunt_packs(technique_id)",
            "CREATE INDEX IF NOT EXISTS idx_hunt_packs_cve ON hunt_packs(cve_id)",
            # Watchlist (V1.3): single-user pin/snooze — user_id added with app login
            "CREATE TABLE IF NOT EXISTS watchlist (cve_id TEXT PRIMARY KEY, state TEXT NOT NULL CHECK(state IN ('pin', 'snooze')), snooze_until TEXT, created_at TEXT DEFAULT (datetime('now')))",
            "CREATE INDEX IF NOT EXISTS idx_watchlist_state ON watchlist(state)",
            "CREATE INDEX IF NOT EXISTS idx_watchlist_snooze_until ON watchlist(snooze_until)",
            # Exploit feeds: dedupe then enforce (cve_id, url) uniqueness
            """
            DELETE FROM cve_exploits
            WHERE id NOT IN (
                SELECT MIN(id) FROM cve_exploits GROUP BY cve_id, url
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_cve_exploits_cve_url ON cve_exploits(cve_id, url)",
            "CREATE TABLE IF NOT EXISTS webhook_alert_log (alert_type TEXT NOT NULL, target TEXT NOT NULL, alerted_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (alert_type, target))",
            "CREATE INDEX IF NOT EXISTS idx_webhook_alert_log_type ON webhook_alert_log(alert_type)",
            "CREATE TABLE IF NOT EXISTS webhook_destinations (id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1, event_types TEXT NOT NULL DEFAULT '[]', config_json TEXT NOT NULL DEFAULT '{}', source TEXT NOT NULL DEFAULT 'db', created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')))",
            "CREATE TABLE IF NOT EXISTS webhook_delivery_log (id INTEGER PRIMARY KEY AUTOINCREMENT, destination_id TEXT NOT NULL, event_type TEXT NOT NULL, dedupe_key TEXT, status TEXT NOT NULL, error TEXT, attempted_at TEXT DEFAULT (datetime('now')))",
            "CREATE INDEX IF NOT EXISTS idx_webhook_delivery_log_dest ON webhook_delivery_log(destination_id)",
            "CREATE INDEX IF NOT EXISTS idx_webhook_delivery_log_at ON webhook_delivery_log(attempted_at)",
            "CREATE INDEX IF NOT EXISTS idx_webhook_delivery_log_event ON webhook_delivery_log(event_type)",
            "CREATE TABLE IF NOT EXISTS webhook_destination_dedupe (destination_id TEXT NOT NULL, event_type TEXT NOT NULL, dedupe_key TEXT NOT NULL, recorded_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (destination_id, event_type, dedupe_key))",
            "CREATE INDEX IF NOT EXISTS idx_webhook_dest_dedupe_event ON webhook_destination_dedupe(event_type, dedupe_key)",
            "CREATE TABLE IF NOT EXISTS ai_operations (id INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT NOT NULL, request_id TEXT, started_at TEXT DEFAULT (datetime('now')), latency_ms INTEGER, feature TEXT NOT NULL, task_class TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, success INTEGER NOT NULL DEFAULT 0, error_class TEXT, input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER, estimated_cost_usd REAL, fallback_from_provider TEXT, fallback_from_model TEXT, retry_index INTEGER NOT NULL DEFAULT 0, context_type TEXT, context_id TEXT)",
            "CREATE INDEX IF NOT EXISTS idx_ai_operations_started ON ai_operations(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_ai_operations_task_provider ON ai_operations(task_class, provider)",
            # Correlation v2 Phase 1
            """
            CREATE TABLE IF NOT EXISTS otx_pulses (
                pulse_id TEXT PRIMARY KEY,
                pulse_name TEXT NOT NULL DEFAULT '',
                author TEXT DEFAULT '',
                created_date TEXT DEFAULT '',
                adversary TEXT DEFAULT '',
                malware_families TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                targeted_countries TEXT DEFAULT '[]',
                ioc_count INTEGER DEFAULT 0,
                fetched_at TEXT DEFAULT (datetime('now'))
            )
            """,
            "ALTER TABLE otx_cve_pulses ADD COLUMN targeted_countries TEXT DEFAULT '[]'",
            "ALTER TABLE otx_pulse_iocs ADD COLUMN observed_at TEXT",
            """
            CREATE TABLE IF NOT EXISTS correlation_campaigns (
                campaign_id TEXT PRIMARY KEY,
                primary_pulse_id TEXT,
                label TEXT NOT NULL DEFAULT '',
                adversary TEXT DEFAULT '',
                malware_families TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                targeted_countries TEXT DEFAULT '[]',
                confidence TEXT DEFAULT 'medium',
                member_count INTEGER DEFAULT 0,
                lifecycle TEXT DEFAULT 'active',
                campaign_version TEXT DEFAULT '',
                computed_at TEXT DEFAULT (datetime('now')),
                family_id TEXT,
                first_seen TEXT,
                last_seen TEXT,
                independent_sources INTEGER DEFAULT 1,
                author_count INTEGER DEFAULT 1,
                retracted_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_correlation_campaigns_pulse ON correlation_campaigns(primary_pulse_id)",
            """
            CREATE TABLE IF NOT EXISTS pulse_families (
                pulse_id TEXT PRIMARY KEY,
                family_id TEXT NOT NULL,
                jaccard REAL,
                computed_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_pulse_families_family ON pulse_families(family_id)",
            "ALTER TABLE correlation_campaigns ADD COLUMN family_id TEXT",
            "ALTER TABLE correlation_campaigns ADD COLUMN first_seen TEXT",
            "ALTER TABLE correlation_campaigns ADD COLUMN last_seen TEXT",
            "ALTER TABLE correlation_campaigns ADD COLUMN independent_sources INTEGER DEFAULT 1",
            "ALTER TABLE correlation_campaigns ADD COLUMN author_count INTEGER DEFAULT 1",
            "ALTER TABLE correlation_campaigns ADD COLUMN retracted_at TEXT",
            """
            CREATE TABLE IF NOT EXISTS correlation_campaign_members (
                campaign_id TEXT NOT NULL,
                cve_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                PRIMARY KEY (campaign_id, cve_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_correlation_campaign_members_cve ON correlation_campaign_members(cve_id)",
            "CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_type_value ON otx_pulse_iocs(ioc_type, ioc_value)",
            """
            CREATE TABLE IF NOT EXISTS correlation_suppressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                reason TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE (cve_id, scope, scope_key)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_correlation_suppressions_cve ON correlation_suppressions(cve_id)",
            """
            CREATE TABLE IF NOT EXISTS correlation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                verdict TEXT NOT NULL,
                reason TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE (cve_id, scope, scope_key, verdict)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_correlation_feedback_cve ON correlation_feedback(cve_id)",
            """
            CREATE TABLE IF NOT EXISTS correlation_metrics (
                day TEXT PRIMARY KEY,
                computed_at TEXT,
                suppressions_30d INTEGER NOT NULL DEFAULT 0,
                feedback_confirm_30d INTEGER NOT NULL DEFAULT 0,
                feedback_reject_30d INTEGER NOT NULL DEFAULT 0,
                surfaced_findings_30d INTEGER NOT NULL DEFAULT 0,
                rejection_rate REAL,
                confirmation_rate REAL,
                weak_edge_ratio REAL,
                hub_suppressed_edge_count INTEGER NOT NULL DEFAULT 0,
                ioc_degree_p95 INTEGER NOT NULL DEFAULT 0,
                avg_independent_sources REAL,
                orphan_cve_ratio REAL,
                campaigns_active INTEGER NOT NULL DEFAULT 0,
                campaigns_retracted INTEGER NOT NULL DEFAULT 0,
                campaign_survival_rate REAL,
                campaign_member_count INTEGER NOT NULL DEFAULT 0,
                stale_campaign_ratio REAL,
                median_evidence_age_days REAL
            )
            """,
            "ALTER TABLE correlation_suppressions ADD COLUMN dismissed_by TEXT DEFAULT ''",
            "CREATE INDEX IF NOT EXISTS idx_otx_cve_pulses_pulse ON otx_cve_pulses(pulse_id)",
            # Built-in app login (decision 2026-06-11): users + sessions.
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                last_login_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                refresh_token_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                last_used_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                user_agent TEXT DEFAULT '',
                ip TEXT DEFAULT '',
                remember_me INTEGER NOT NULL DEFAULT 0
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(refresh_token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)",
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                stack_terms TEXT NOT NULL DEFAULT '',
                profile_json TEXT,
                display_prefs_json TEXT,
                timezone TEXT NOT NULL DEFAULT 'UTC',
                remember_profile_on_server INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """,
            "ALTER TABLE user_preferences ADD COLUMN display_prefs_json TEXT",
            "ALTER TABLE user_preferences ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC'",
            "ALTER TABLE user_preferences ADD COLUMN remember_profile_on_server INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users RENAME COLUMN email TO username",
            "DROP INDEX IF EXISTS idx_users_email",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            """
            CREATE TABLE IF NOT EXISTS user_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                scope TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id TEXT NOT NULL DEFAULT '',
                dedupe_key TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                read_at TEXT,
                dismissed_at TEXT,
                UNIQUE (user_id, dedupe_key)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_user_notifications_user_active ON user_notifications(user_id, dismissed_at, created_at)",
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS detection_backlog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id TEXT NOT NULL,
                technique_id TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT 'kev_gap',
                priority TEXT NOT NULL DEFAULT 'high',
                status TEXT NOT NULL DEFAULT 'open',
                stack_terms TEXT NOT NULL DEFAULT '',
                technique_name TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                dismissed_at TEXT,
                UNIQUE (cve_id, technique_id, reason)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_detection_backlog_status ON detection_backlog(status)",
            "CREATE INDEX IF NOT EXISTS idx_detection_backlog_cve ON detection_backlog(cve_id)",
            """
            CREATE TABLE IF NOT EXISTS ioc_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE (user_id, ioc_type, ioc_value)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_ioc_watchlist_value ON ioc_watchlist(ioc_value)",
            "CREATE INDEX IF NOT EXISTS idx_ioc_watchlist_user ON ioc_watchlist(user_id)",
            """
            CREATE TABLE IF NOT EXISTS threatfox_iocs (
                ioc_id TEXT PRIMARY KEY,
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                raw_ioc TEXT NOT NULL DEFAULT '',
                malware TEXT NOT NULL DEFAULT '',
                threat_type TEXT NOT NULL DEFAULT '',
                confidence_level INTEGER NOT NULL DEFAULT 0,
                first_seen TEXT NOT NULL DEFAULT '',
                fetched_at TEXT DEFAULT (datetime('now'))
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_threatfox_iocs_value ON threatfox_iocs(ioc_value)",
            "CREATE INDEX IF NOT EXISTS idx_threatfox_iocs_type_value ON threatfox_iocs(ioc_type, ioc_value)",
            "ALTER TABLE cves ADD COLUMN is_vulncheck_exploited INTEGER DEFAULT 0",
            "CREATE INDEX IF NOT EXISTS idx_cves_vulncheck_exploited ON cves(is_vulncheck_exploited)",
            _CREATE_IDX_CVES_MODIFIED_SQL,
            "DROP INDEX IF EXISTS idx_correlation_infra_a",
            "DROP INDEX IF EXISTS idx_correlation_infra_b",
            "DROP TABLE IF EXISTS correlation_infrastructure",
            """
            CREATE TABLE IF NOT EXISTS ioc_degree (
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                cve_count INTEGER NOT NULL DEFAULT 0,
                pulse_count INTEGER NOT NULL DEFAULT 0,
                computed_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (ioc_type, ioc_value)
            )
            """,
            _RESOURCE_METRICS_TABLE_SQL,
            _RESOURCE_METRICS_IDX_SQL,
            "ALTER TABLE audit_log ADD COLUMN metadata_json TEXT",
        ):
            try:
                await db.execute(migration)
                await db.commit()
            except Exception:
                pass

        try:
            await db.execute(_CREATE_IDX_CVES_HAS_POC_SQL)
            await db.commit()
        except Exception:
            pass

        await _normalize_epss_scores(db)
        await db.commit()
    finally:
        await db.close()
