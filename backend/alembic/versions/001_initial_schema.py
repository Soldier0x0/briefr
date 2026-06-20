"""Initial PostgreSQL schema — mirrors SQLite init_db baseline (V2.0).

Revision ID: 001_initial
"""

from __future__ import annotations

from alembic import op

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS cves (
            cve_id TEXT PRIMARY KEY,
            description TEXT,
            cvss_score DOUBLE PRECISION,
            severity TEXT,
            published TEXT,
            modified TEXT,
            affected_products TEXT DEFAULT '[]',
            affected_products_source TEXT DEFAULT '',
            mitre_technique TEXT,
            summary TEXT,
            is_kev INTEGER DEFAULT 0,
            epss_score DOUBLE PRECISION,
            has_poc INTEGER DEFAULT 0,
            patch_available INTEGER DEFAULT 0,
            has_ai_context INTEGER DEFAULT 0,
            source_urls TEXT DEFAULT '[]',
            cwe_ids TEXT DEFAULT '[]',
            cpe_matches TEXT DEFAULT '[]',
            updated_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_cves_severity ON cves(severity)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cves_published ON cves(published)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cves_is_kev ON cves(is_kev)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cves_epss ON cves(epss_score)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cves_has_poc ON cves(has_poc)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS ioc_cache (
            value TEXT PRIMARY KEY,
            ioc_type TEXT NOT NULL,
            result TEXT NOT NULL,
            cached_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_ioc_cached_at ON ioc_cache(cached_at)")

    op.execute(
        f"""
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
            updated_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_kev_due_date ON kev_deadlines(due_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_kev_date_added ON kev_deadlines(date_added)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_usage (
            service TEXT NOT NULL,
            date_utc TEXT NOT NULL,
            month_utc TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (service, date_utc)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_month ON api_usage(month_utc)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(date_utc)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT ({_TS})
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mitre_techniques (
            technique_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            tactic TEXT DEFAULT '',
            url TEXT NOT NULL,
            platforms TEXT DEFAULT '[]',
            detection TEXT DEFAULT ''
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cve_technique_map (
            cve_id TEXT NOT NULL,
            technique_id TEXT NOT NULL,
            PRIMARY KEY (cve_id, technique_id),
            FOREIGN KEY (technique_id) REFERENCES mitre_techniques(technique_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cve_technique_map_technique "
        "ON cve_technique_map(technique_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cve_technique_map_cve ON cve_technique_map(cve_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS atlas_techniques (
            technique_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            tactic TEXT DEFAULT '',
            tactic_id TEXT DEFAULT '',
            url TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_atlas_techniques_tactic ON atlas_techniques(tactic)"
    )

    op.execute(
        """
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
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_atlas_case_studies_date ON atlas_case_studies(date)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cve_atlas_map (
            cve_id TEXT NOT NULL,
            technique_id TEXT NOT NULL,
            PRIMARY KEY (cve_id, technique_id),
            FOREIGN KEY (technique_id) REFERENCES atlas_techniques(technique_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_cve_atlas_map_cve ON cve_atlas_map(cve_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS epss_history (
            cve_id TEXT NOT NULL,
            score DOUBLE PRECISION NOT NULL,
            recorded_date TEXT NOT NULL,
            PRIMARY KEY (cve_id, recorded_date)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_epss_history_cve_date "
        "ON epss_history(cve_id, recorded_date)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS cve_exploits (
            id SERIAL PRIMARY KEY,
            cve_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            type TEXT NOT NULL DEFAULT 'poc',
            source TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            published_date TEXT DEFAULT '',
            fetched_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_cve_exploits_cve ON cve_exploits(cve_id)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cve_exploits_cve_url "
        "ON cve_exploits(cve_id, url)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS feed_cache (
            cache_key TEXT PRIMARY KEY,
            result TEXT NOT NULL,
            cached_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_feed_cache_cached_at ON feed_cache(cached_at)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS cve_change_history (
            id SERIAL PRIMARY KEY,
            cve_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT NOT NULL DEFAULT '',
            new_value TEXT NOT NULL DEFAULT '',
            detected_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cve_change_history_cve ON cve_change_history(cve_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cve_change_history_detected "
        "ON cve_change_history(detected_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cve_change_history_field "
        "ON cve_change_history(field_name)"
    )

    op.execute(
        f"""
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
            fetched_at TEXT DEFAULT ({_TS}),
            PRIMARY KEY (cve_id, pulse_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_otx_cve_pulses_cve ON otx_cve_pulses(cve_id)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS otx_pulse_iocs (
            pulse_id TEXT NOT NULL,
            ioc_type TEXT NOT NULL DEFAULT '',
            ioc_value TEXT NOT NULL,
            description TEXT DEFAULT '',
            fetched_at TEXT DEFAULT ({_TS}),
            PRIMARY KEY (pulse_id, ioc_type, ioc_value)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_pulse ON otx_pulse_iocs(pulse_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_value ON otx_pulse_iocs(ioc_value)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS correlation_infrastructure (
            cve_id_a TEXT NOT NULL,
            cve_id_b TEXT NOT NULL,
            shared_ip_count INTEGER DEFAULT 0,
            confidence TEXT DEFAULT 'low',
            detected_at TEXT DEFAULT ({_TS}),
            PRIMARY KEY (cve_id_a, cve_id_b)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_infra_a "
        "ON correlation_infrastructure(cve_id_a)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_infra_b "
        "ON correlation_infrastructure(cve_id_b)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS correlation_actor (
            cve_id TEXT NOT NULL,
            actor_name TEXT NOT NULL,
            actor_sectors TEXT DEFAULT '[]',
            user_sector_match INTEGER DEFAULT 0,
            confidence TEXT DEFAULT 'low',
            detected_at TEXT DEFAULT ({_TS}),
            PRIMARY KEY (cve_id, actor_name)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_actor_cve ON correlation_actor(cve_id)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS correlation_temporal (
            vendor TEXT PRIMARY KEY,
            current_week_count INTEGER DEFAULT 0,
            average_weekly_count DOUBLE PRECISION DEFAULT 0,
            anomaly_score DOUBLE PRECISION DEFAULT 0,
            detected_at TEXT DEFAULT ({_TS})
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mitre_groups (
            group_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            aliases TEXT DEFAULT '[]',
            description TEXT DEFAULT '',
            sectors TEXT DEFAULT '[]',
            url TEXT DEFAULT ''
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS group_technique_map (
            group_id TEXT NOT NULL,
            technique_id TEXT NOT NULL,
            PRIMARY KEY (group_id, technique_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_group_technique_map_technique "
        "ON group_technique_map(technique_id)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS cve_embeddings (
            cve_id TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector BYTEA NOT NULL,
            updated_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cve_embeddings_model ON cve_embeddings(model)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS hunt_packs (
            id SERIAL PRIMARY KEY,
            technique_id TEXT NOT NULL,
            cve_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'medium',
            sigma_yaml TEXT NOT NULL DEFAULT '',
            siem_queries TEXT NOT NULL DEFAULT '{{}}',
            log_patterns TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT ({_TS}),
            updated_at TEXT DEFAULT ({_TS}),
            UNIQUE (technique_id, cve_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_hunt_packs_technique ON hunt_packs(technique_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hunt_packs_cve ON hunt_packs(cve_id)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            actor TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            target TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS watchlist (
            cve_id TEXT PRIMARY KEY,
            state TEXT NOT NULL CHECK(state IN ('pin', 'snooze')),
            snooze_until TEXT,
            created_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_state ON watchlist(state)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_watchlist_snooze_until ON watchlist(snooze_until)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS webhook_alert_log (
            alert_type TEXT NOT NULL,
            target TEXT NOT NULL,
            alerted_at TEXT DEFAULT ({_TS}),
            PRIMARY KEY (alert_type, target)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_alert_log_type ON webhook_alert_log(alert_type)"
    )


def downgrade() -> None:
    tables = [
        "webhook_alert_log",
        "watchlist",
        "audit_log",
        "hunt_packs",
        "cve_embeddings",
        "group_technique_map",
        "mitre_groups",
        "correlation_temporal",
        "correlation_actor",
        "correlation_infrastructure",
        "otx_pulse_iocs",
        "otx_cve_pulses",
        "cve_change_history",
        "feed_cache",
        "cve_exploits",
        "epss_history",
        "cve_atlas_map",
        "atlas_case_studies",
        "atlas_techniques",
        "cve_technique_map",
        "mitre_techniques",
        "sync_state",
        "api_usage",
        "kev_deadlines",
        "ioc_cache",
        "cves",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
