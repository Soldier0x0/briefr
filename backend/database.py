import os
import json
import asyncio
import aiosqlite
from pathlib import Path
from typing import Any

from db.config import is_postgres
from db.connection import get_connection

DB_PATH = os.environ.get("DB_PATH", "briefr.db")


async def get_db():
    """Return a database connection (SQLite default, PostgreSQL when configured)."""
    return await get_connection()


async def _init_postgres_schema() -> None:
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(Path(__file__).resolve().parent / "alembic.ini"))
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    db = await get_db()
    try:
        await db.execute("UPDATE cves SET epss_score = NULL WHERE epss_score = 0.0")
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
                has_poc INTEGER DEFAULT 0,
                patch_available INTEGER DEFAULT 0,
                has_ai_context INTEGER DEFAULT 0,
                source_urls TEXT DEFAULT '[]',
                cwe_ids TEXT DEFAULT '[]',
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_cves_severity ON cves(severity);
            CREATE INDEX IF NOT EXISTS idx_cves_published ON cves(published);
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
                PRIMARY KEY (service, date_utc)
            );

            CREATE INDEX IF NOT EXISTS idx_api_usage_month ON api_usage(month_utc);
            CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(date_utc);

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

            CREATE TABLE IF NOT EXISTS otx_pulse_iocs (
                pulse_id TEXT NOT NULL,
                ioc_type TEXT NOT NULL DEFAULT '',
                ioc_value TEXT NOT NULL,
                description TEXT DEFAULT '',
                fetched_at TEXT DEFAULT (datetime('now')),
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
                computed_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_correlation_campaigns_pulse
                ON correlation_campaigns(primary_pulse_id);

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

            CREATE TABLE IF NOT EXISTS correlation_infrastructure (
                cve_id_a TEXT NOT NULL,
                cve_id_b TEXT NOT NULL,
                shared_ip_count INTEGER DEFAULT 0,
                confidence TEXT DEFAULT 'low',
                detected_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (cve_id_a, cve_id_b)
            );

            CREATE INDEX IF NOT EXISTS idx_correlation_infra_a
                ON correlation_infrastructure(cve_id_a);
            CREATE INDEX IF NOT EXISTS idx_correlation_infra_b
                ON correlation_infrastructure(cve_id_b);

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
        """)
        await db.commit()

        for migration in (
            "ALTER TABLE kev_deadlines ADD COLUMN date_added TEXT DEFAULT ''",
            "ALTER TABLE kev_deadlines ADD COLUMN vendor_project TEXT DEFAULT ''",
            "ALTER TABLE kev_deadlines ADD COLUMN vulnerability_name TEXT DEFAULT ''",
            "ALTER TABLE kev_deadlines ADD COLUMN known_ransomware TEXT DEFAULT ''",
            "ALTER TABLE kev_deadlines ADD COLUMN cwes TEXT DEFAULT '[]'",
            "ALTER TABLE cves ADD COLUMN has_poc INTEGER DEFAULT 0",
            "ALTER TABLE cves ADD COLUMN cpe_matches TEXT DEFAULT '[]'",
            "ALTER TABLE cves ADD COLUMN has_ai_context INTEGER DEFAULT 0",
            "ALTER TABLE cves ADD COLUMN affected_products_source TEXT DEFAULT ''",
            "ALTER TABLE mitre_techniques ADD COLUMN detection TEXT DEFAULT ''",
            "CREATE TABLE IF NOT EXISTS cve_atlas_map (cve_id TEXT NOT NULL, technique_id TEXT NOT NULL, PRIMARY KEY (cve_id, technique_id), FOREIGN KEY (technique_id) REFERENCES atlas_techniques(technique_id))",
            "CREATE INDEX IF NOT EXISTS idx_cve_atlas_map_cve ON cve_atlas_map(cve_id)",
            # Correlation engine tables (added in correlation session)
            "CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_value ON otx_pulse_iocs(ioc_value)",
            "CREATE TABLE IF NOT EXISTS correlation_infrastructure (cve_id_a TEXT NOT NULL, cve_id_b TEXT NOT NULL, shared_ip_count INTEGER DEFAULT 0, confidence TEXT DEFAULT 'low', detected_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (cve_id_a, cve_id_b))",
            "CREATE INDEX IF NOT EXISTS idx_correlation_infra_a ON correlation_infrastructure(cve_id_a)",
            "CREATE INDEX IF NOT EXISTS idx_correlation_infra_b ON correlation_infrastructure(cve_id_b)",
            "CREATE TABLE IF NOT EXISTS correlation_actor (cve_id TEXT NOT NULL, actor_name TEXT NOT NULL, actor_sectors TEXT DEFAULT '[]', user_sector_match INTEGER DEFAULT 0, confidence TEXT DEFAULT 'low', detected_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (cve_id, actor_name))",
            "CREATE INDEX IF NOT EXISTS idx_correlation_actor_cve ON correlation_actor(cve_id)",
            "CREATE TABLE IF NOT EXISTS correlation_temporal (vendor TEXT PRIMARY KEY, current_week_count INTEGER DEFAULT 0, average_weekly_count REAL DEFAULT 0, anomaly_score REAL DEFAULT 0, detected_at TEXT DEFAULT (datetime('now')))",
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
                computed_at TEXT DEFAULT (datetime('now'))
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_correlation_campaigns_pulse ON correlation_campaigns(primary_pulse_id)",
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
            "ALTER TABLE correlation_suppressions ADD COLUMN dismissed_by TEXT DEFAULT ''",
        ):
            try:
                await db.execute(migration)
                await db.commit()
            except Exception:
                pass

        try:
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cves_has_poc ON cves(has_poc)"
            )
            await db.commit()
        except Exception:
            pass

        await db.execute(
            "UPDATE cves SET epss_score = NULL WHERE epss_score = 0.0"
        )
        await db.commit()
    finally:
        await db.close()


async def write_audit_log(
    db: aiosqlite.Connection,
    actor: str | None,
    action: str,
    target: str = "",
) -> None:
    """Append one audit row (caller commits). Actor is '' when no identity."""
    await db.execute(
        "INSERT INTO audit_log (actor, action, target) VALUES (?, ?, ?)",
        ((actor or "").strip(), action, target or ""),
    )


# Active watchlist rows: pins, or snoozes whose deadline has not passed.
_WATCHLIST_ACTIVE_SQL = """
    state = 'pin'
    OR (state = 'snooze'
        AND snooze_until IS NOT NULL
        AND datetime(snooze_until) > datetime('now'))
"""


async def list_watchlist_entries(db: aiosqlite.Connection) -> list[dict]:
    """Return active watchlist rows (pins + unexpired snoozes)."""
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, state, snooze_until, created_at
        FROM watchlist
        WHERE {_WATCHLIST_ACTIVE_SQL}
        ORDER BY
            CASE state WHEN 'pin' THEN 0 ELSE 1 END,
            created_at DESC
        """
    )
    return [dict(row) for row in rows]


async def get_watchlist_entry(
    db: aiosqlite.Connection, cve_id: str
) -> dict | None:
    """Return one active watchlist row, or None."""
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, state, snooze_until, created_at
        FROM watchlist
        WHERE cve_id = ? AND ({_WATCHLIST_ACTIVE_SQL})
        """,
        (cve_id.upper(),),
    )
    return dict(rows[0]) if rows else None


async def upsert_watchlist_entry(
    db: aiosqlite.Connection,
    cve_id: str,
    state: str,
    snooze_until: str | None = None,
) -> dict:
    """Insert or replace a watchlist row (caller commits)."""
    key = cve_id.upper()
    await db.execute(
        """
        INSERT INTO watchlist (cve_id, state, snooze_until, created_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(cve_id) DO UPDATE SET
            state = excluded.state,
            snooze_until = excluded.snooze_until,
            created_at = datetime('now')
        """,
        (key, state, snooze_until),
    )
    rows = await db.execute_fetchall(
        "SELECT cve_id, state, snooze_until, created_at FROM watchlist WHERE cve_id = ?",
        (key,),
    )
    return dict(rows[0])


async def delete_watchlist_entry(db: aiosqlite.Connection, cve_id: str) -> bool:
    """Remove a watchlist row. Returns True when a row was deleted."""
    cursor = await db.execute(
        "DELETE FROM watchlist WHERE cve_id = ?",
        (cve_id.upper(),),
    )
    return cursor.rowcount > 0


async def delete_all_snooze_entries(db: aiosqlite.Connection) -> int:
    """Remove every snoozed watchlist row. Returns rows deleted."""
    cursor = await db.execute("DELETE FROM watchlist WHERE state = 'snooze'")
    return cursor.rowcount


async def cve_exists(db: aiosqlite.Connection, cve_id: str) -> bool:
    rows = await db.execute_fetchall(
        "SELECT 1 FROM cves WHERE cve_id = ? LIMIT 1",
        (cve_id.upper(),),
    )
    return bool(rows)


TRACKED_CVE_FIELDS = frozenset({"cvss_score", "epss_score", "is_kev", "has_poc"})


def _change_value_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            text = f"{value:.6f}".rstrip("0").rstrip(".")
            return text or "0"
        return str(value)
    return str(value)


def _values_differ(old: object, new: object) -> bool:
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    if isinstance(old, float) and isinstance(new, float):
        return abs(old - new) > 1e-9
    return old != new


def _normalize_epss_score(value: object) -> float | None:
    """NULL and ~0 are equivalent — matches init_db epss_score NULL normalization."""
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if abs(score) < 1e-9:
        return None
    return score


def _epss_display_percent(score: float | None) -> float:
    """One decimal place in percent — matches WhatChangedPanel EPSS formatting."""
    if score is None:
        return 0.0
    return round(score * 100, 1)


def _epss_scores_differ(old: object, new: object) -> bool:
    """True only when EPSS would display differently to an analyst (0.1% precision)."""
    return _epss_display_percent(_normalize_epss_score(old)) != _epss_display_percent(
        _normalize_epss_score(new)
    )


_SQLITE_IN_CHUNK = 500

_UPSERT_CVE_SQL = """
    INSERT INTO cves (
        cve_id, description, cvss_score, severity, published, modified,
        affected_products, mitre_technique, summary, is_kev, epss_score,
        has_poc, patch_available, has_ai_context, source_urls, cwe_ids, updated_at
    ) VALUES (
        :cve_id, :description, :cvss_score, :severity, :published, :modified,
        :affected_products, :mitre_technique, :summary, :is_kev, :epss_score,
        :has_poc, :patch_available, :has_ai_context, :source_urls, :cwe_ids, datetime('now')
    )
    ON CONFLICT(cve_id) DO UPDATE SET
        description = excluded.description,
        cvss_score = excluded.cvss_score,
        severity = excluded.severity,
        published = excluded.published,
        modified = excluded.modified,
        -- LLM-derived products survive feed upserts that carry no CPE data;
        -- any non-empty official product list supersedes them (and clears
        -- the 'llm' provenance marker).
        affected_products = CASE
            WHEN cves.affected_products_source = 'llm'
                 AND (excluded.affected_products IS NULL
                      OR excluded.affected_products IN ('', '[]'))
            THEN cves.affected_products
            ELSE excluded.affected_products
        END,
        affected_products_source = CASE
            WHEN cves.affected_products_source = 'llm'
                 AND (excluded.affected_products IS NULL
                      OR excluded.affected_products IN ('', '[]'))
            THEN 'llm'
            ELSE ''
        END,
        cpe_matches = excluded.cpe_matches,
        mitre_technique = COALESCE(excluded.mitre_technique, cves.mitre_technique),
        summary = COALESCE(excluded.summary, cves.summary),
        has_poc = CASE WHEN excluded.has_poc = 1 THEN 1 ELSE cves.has_poc END,
        patch_available = excluded.patch_available,
        has_ai_context = excluded.has_ai_context,
        source_urls = excluded.source_urls,
        cwe_ids = excluded.cwe_ids,
        updated_at = datetime('now')
"""


def _cve_upsert_params(cve: dict) -> dict:
    return {
        "cve_id": cve.get("cve_id", ""),
        "description": cve.get("description", ""),
        "cvss_score": cve.get("cvss_score"),
        "severity": cve.get("severity", "UNKNOWN"),
        "published": cve.get("published", ""),
        "modified": cve.get("modified", ""),
        "affected_products": json.dumps(cve.get("affected_products", [])),
        "cpe_matches": json.dumps(cve.get("cpe_matches", [])),
        "mitre_technique": cve.get("mitre_technique"),
        "summary": cve.get("summary"),
        "is_kev": 1 if cve.get("is_kev") else 0,
        "epss_score": cve.get("epss_score"),
        "has_poc": 1 if cve.get("has_poc") else 0,
        "patch_available": 1 if cve.get("patch_available") else 0,
        "has_ai_context": 1 if cve.get("has_ai_context") else 0,
        "source_urls": json.dumps(cve.get("source_urls", [])),
        "cwe_ids": json.dumps(cve.get("cwe_ids", [])),
    }


def _append_upsert_change_rows(
    cve_id: str,
    cve: dict,
    prior: dict | None,
    history: list[tuple[str, str, str, str]],
) -> None:
    incoming_poc = 1 if cve.get("has_poc") else 0
    incoming_kev = 1 if cve.get("is_kev") else 0
    new_poc = (1 if prior["has_poc"] or incoming_poc else 0) if prior else incoming_poc
    new_cvss = cve.get("cvss_score")

    if prior:
        if _values_differ(prior["cvss_score"], new_cvss):
            history.append(
                (
                    cve_id,
                    "cvss_score",
                    _change_value_str(prior["cvss_score"]),
                    _change_value_str(new_cvss),
                )
            )
        if prior["has_poc"] == 0 and new_poc == 1:
            history.append((cve_id, "has_poc", "0", "1"))
    else:
        if incoming_kev:
            history.append((cve_id, "is_kev", "0", "1"))
        if incoming_poc:
            history.append((cve_id, "has_poc", "0", "1"))
        if new_cvss is not None:
            history.append(
                (cve_id, "cvss_score", "", _change_value_str(new_cvss))
            )


async def _insert_cve_changes_batch(
    db: aiosqlite.Connection,
    rows: list[tuple[str, str, str, str]],
) -> None:
    if not rows:
        return
    await db.executemany(
        """
        INSERT INTO cve_change_history (cve_id, field_name, old_value, new_value, detected_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        rows,
    )


async def _load_cve_change_snapshots(
    db: aiosqlite.Connection, cve_ids: list[str]
) -> dict[str, dict]:
    snapshots: dict[str, dict] = {}
    normalized = [c.upper() for c in cve_ids if c]
    for i in range(0, len(normalized), _SQLITE_IN_CHUNK):
        chunk = normalized[i : i + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, cvss_score, epss_score, is_kev, has_poc
            FROM cves WHERE cve_id IN ({placeholders})
            """,
            chunk,
        )
        for row in rows:
            snapshots[row["cve_id"]] = {
                "cvss_score": row["cvss_score"],
                "epss_score": row["epss_score"],
                "is_kev": int(row["is_kev"] or 0),
                "has_poc": int(row["has_poc"] or 0),
            }
    return snapshots


def _cve_id_filter_clause(cve_ids: list[str] | None) -> tuple[str, list[str]]:
    if not cve_ids:
        return "", []
    normalized = [c.upper() for c in cve_ids if c]
    if not normalized:
        return "", []
    placeholders = ",".join("?" * len(normalized))
    return f" AND cve_id IN ({placeholders})", normalized


async def upsert_cves(db: aiosqlite.Connection, cves: list[dict]) -> None:
    if not cves:
        return
    valid = [c for c in cves if (c.get("cve_id") or "").strip()]
    if not valid:
        return

    ids = [(c.get("cve_id") or "").upper() for c in valid]
    snapshots = await _load_cve_change_snapshots(db, ids)
    history: list[tuple[str, str, str, str]] = []

    from feeds.ai_context import analyze_cve_ai_context

    for cve in valid:
        cve_id = (cve.get("cve_id") or "").upper()
        has_ai, _atlas_tids = analyze_cve_ai_context(cve)
        cve["has_ai_context"] = has_ai
        _append_upsert_change_rows(cve_id, cve, snapshots.get(cve_id), history)
        await db.execute(_UPSERT_CVE_SQL, _cve_upsert_params(cve))

    await _insert_cve_changes_batch(db, history)


async def upsert_cve(db: aiosqlite.Connection, cve: dict) -> None:
    await upsert_cves(db, [cve])


async def get_cves_needing_intel_enrichment(
    db: aiosqlite.Connection,
    *,
    limit: int = 5000,
) -> list[str]:
    """CVE IDs that may still benefit from vulnrichment / cvelist enrichment."""
    rows = await db.execute_fetchall(
        """
        SELECT cve_id FROM cves
        WHERE cvss_score IS NULL
           OR severity IS NULL
           OR severity = 'UNKNOWN'
           OR cwe_ids IS NULL
           OR cwe_ids = '[]'
           OR cwe_ids = ''
        ORDER BY published DESC, cve_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [row["cve_id"] for row in rows]


async def apply_additive_cve_enrichments(
    db: aiosqlite.Connection,
    enrichments: list[dict],
) -> int:
    """Merge scheduler intel into cves without downgrading richer NVD fields."""
    from feeds.cve_record_v5 import merge_additive_cve_fields

    if not enrichments:
        return 0

    updated = 0
    for incoming in enrichments:
        cve_id = (incoming.get("cve_id") or "").upper()
        if not cve_id:
            continue

        rows = await db.execute_fetchall(
            """
            SELECT cve_id, description, cvss_score, severity, published, modified,
                   affected_products, cwe_ids
            FROM cves WHERE cve_id = ?
            """,
            (cve_id,),
        )

        if rows:
            existing = dict(rows[0])
            changes = merge_additive_cve_fields(existing, incoming)
            if not changes:
                continue
            params = {"cve_id": cve_id}
            set_parts: list[str] = []
            if "cvss_score" in changes:
                set_parts.append("cvss_score = :cvss_score")
                params["cvss_score"] = changes["cvss_score"]
            if "severity" in changes:
                set_parts.append("severity = :severity")
                params["severity"] = changes["severity"]
            if "description" in changes:
                set_parts.append("description = :description")
                params["description"] = changes["description"]
            if "published" in changes:
                set_parts.append("published = :published")
                params["published"] = changes["published"]
            if "modified" in changes:
                set_parts.append("modified = :modified")
                params["modified"] = changes["modified"]
            if "cwe_ids" in changes:
                set_parts.append("cwe_ids = :cwe_ids")
                params["cwe_ids"] = json.dumps(changes["cwe_ids"])
            if "affected_products" in changes:
                set_parts.append("affected_products = :affected_products")
                params["affected_products"] = json.dumps(changes["affected_products"])
            set_parts.append("updated_at = datetime('now')")
            await db.execute(
                f"UPDATE cves SET {', '.join(set_parts)} WHERE cve_id = :cve_id",
                params,
            )
            updated += 1
        else:
            await upsert_cve(db, incoming)
            updated += 1

    return updated


async def delete_cves_by_ids(db: aiosqlite.Connection, cve_ids: list[str]) -> int:
    """Remove CVE rows (and purge legacy rejected-description rows). Caller commits."""
    normalized = sorted({c.strip().upper() for c in cve_ids if c and str(c).strip()})
    deleted = 0
    for i in range(0, len(normalized), _SQLITE_IN_CHUNK):
        chunk = normalized[i : i + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        cursor = await db.execute(
            f"DELETE FROM cves WHERE cve_id IN ({placeholders})",
            chunk,
        )
        deleted += cursor.rowcount
    return deleted


async def purge_legacy_rejected_cves(db: aiosqlite.Connection) -> int:
    """Delete rows ingested before reject-filtering (NVD 'Rejected reason:' text)."""
    cursor = await db.execute(
        """
        DELETE FROM cves
        WHERE LOWER(description) LIKE 'rejected reason:%'
        """
    )
    return cursor.rowcount


async def mark_cves_as_kev(db: aiosqlite.Connection, cve_ids: list) -> list[str]:
    """Mark CVEs as KEV; return IDs that transitioned from is_kev=0 to 1."""
    if not cve_ids:
        return []
    normalized = [c.upper() for c in cve_ids if c]
    if not normalized:
        return []
    placeholders = ",".join("?" * len(normalized))
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, is_kev FROM cves
        WHERE cve_id IN ({placeholders}) AND is_kev = 0
        """,
        normalized,
    )
    newly_kev = [row["cve_id"] for row in rows]
    history = [(row["cve_id"], "is_kev", "0", "1") for row in rows]
    await _insert_cve_changes_batch(db, history)
    await db.execute(
        f"UPDATE cves SET is_kev = 1 WHERE cve_id IN ({placeholders})",
        normalized,
    )
    return newly_kev


async def snapshot_epss_scores(db: aiosqlite.Connection, recorded_date: str | None = None) -> int:
    """Persist current EPSS scores before a bulk update (one row per CVE per day)."""
    from datetime import date

    day = recorded_date or date.today().isoformat()
    cursor = await db.execute(
        """
        INSERT OR REPLACE INTO epss_history (cve_id, score, recorded_date)
        SELECT cve_id, epss_score, ?
        FROM cves
        WHERE epss_score IS NOT NULL
        """,
        (day,),
    )
    return cursor.rowcount


async def update_epss_scores(db: aiosqlite.Connection, scores: dict) -> None:
    if not scores:
        return

    needed_list = list({cve_id.upper() for cve_id in scores})
    existing: dict[str, float | None] = {}
    for i in range(0, len(needed_list), _SQLITE_IN_CHUNK):
        chunk = needed_list[i : i + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows = await db.execute_fetchall(
            f"SELECT cve_id, epss_score FROM cves WHERE cve_id IN ({placeholders})",
            chunk,
        )
        for row in rows:
            existing[row["cve_id"].upper()] = row["epss_score"]

    history: list[tuple[str, str, str, str]] = []
    updates: list[tuple[float, str]] = []
    for cve_id, score in scores.items():
        key = cve_id.upper()
        if key not in existing:
            continue
        old = existing[key]
        if not _epss_scores_differ(old, score):
            continue
        history.append(
            (
                key,
                "epss_score",
                _change_value_str(old),
                _change_value_str(score),
            )
        )
        updates.append((score, key))

    await _insert_cve_changes_batch(db, history)
    if updates:
        await db.executemany(
            "UPDATE cves SET epss_score = ? WHERE cve_id = ?",
            updates,
        )


async def get_epss_history(
    db: aiosqlite.Connection, cve_id: str, days: int = 30
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT recorded_date AS date, score
        FROM epss_history
        WHERE cve_id = ?
          AND recorded_date >= DATE('now', ?)
        ORDER BY recorded_date ASC
        """,
        (cve_id.upper(), f"-{days - 1} days"),
    )
    return [{"date": row["date"], "score": row["score"]} for row in rows]


async def get_related_cves(
    db: aiosqlite.Connection, cve_id: str, limit: int = 5
) -> list[dict]:
    """CVEs sharing an affected product (vendor:product), published in last 30 days."""
    cve_key = cve_id.upper()
    rows = await db.execute_fetchall(
        "SELECT affected_products FROM cves WHERE cve_id = ?",
        (cve_key,),
    )
    if not rows:
        return []

    raw = rows[0]["affected_products"] or "[]"
    try:
        products = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        products = []

    products = [p for p in products if isinstance(p, str) and ":" in p]
    if not products:
        return []

    conditions: list[str] = []
    params: list = [cve_key]
    for product in products[:10]:
        needle = f'%"{product.lower()}"%'
        conditions.append("LOWER(affected_products) LIKE ?")
        params.append(needle)

    where_products = "(" + " OR ".join(conditions) + ")"
    params.append(limit)

    related = await db.execute_fetchall(
        f"""
        SELECT cve_id, description, cvss_score, severity, published, epss_score
        FROM cves
        WHERE cve_id != ?
          AND published IS NOT NULL
          AND published != ''
          AND DATE(published) >= DATE('now', '-30 days')
          AND {where_products}
        ORDER BY
          CASE WHEN cvss_score IS NULL THEN -1 ELSE cvss_score END DESC,
          published DESC
        LIMIT ?
        """,
        params,
    )

    seen: set[str] = set()
    out: list[dict] = []
    for row in related:
        rid = row["cve_id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(
            {
                "cve_id": rid,
                "description": row["description"] or "",
                "cvss_score": row["cvss_score"],
                "severity": row["severity"],
                "published": row["published"],
                "epss_score": row["epss_score"],
            }
        )
        if len(out) >= limit:
            break
    return out




# --- CVE description embeddings (V1.3 Theme 7 — env-gated, scheduler-side) ---


async def upsert_cve_embedding(
    db: aiosqlite.Connection, cve_id: str, model: str, dim: int, vector: bytes
) -> None:
    """Store one embedding BLOB (float32 little-endian). One row per CVE;
    a model change replaces the old vector on the next backfill pass."""
    await db.execute(
        """
        INSERT INTO cve_embeddings (cve_id, model, dim, vector, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(cve_id) DO UPDATE SET
            model = excluded.model,
            dim = excluded.dim,
            vector = excluded.vector,
            updated_at = datetime('now')
        """,
        (cve_id.upper(), model, dim, vector),
    )


async def get_cve_embedding(
    db: aiosqlite.Connection, cve_id: str, model: str
) -> bytes | None:
    rows = await db.execute_fetchall(
        "SELECT vector FROM cve_embeddings WHERE cve_id = ? AND model = ?",
        (cve_id.upper(), model),
    )
    return rows[0]["vector"] if rows else None


async def get_all_cve_embeddings(
    db: aiosqlite.Connection, model: str, exclude_cve_id: str | None = None
) -> list[tuple[str, bytes]]:
    """All stored vectors for one model — input to the brute-force cosine scan."""
    if exclude_cve_id:
        rows = await db.execute_fetchall(
            "SELECT cve_id, vector FROM cve_embeddings WHERE model = ? AND cve_id != ?",
            (model, exclude_cve_id.upper()),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT cve_id, vector FROM cve_embeddings WHERE model = ?",
            (model,),
        )
    return [(row["cve_id"], row["vector"]) for row in rows]


async def count_cve_embeddings(db: aiosqlite.Connection, model: str) -> int:
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) AS n FROM cve_embeddings WHERE model = ?", (model,)
    )
    return int(rows[0]["n"]) if rows else 0


async def get_cves_missing_embeddings(
    db: aiosqlite.Connection, model: str, limit: int = 500
) -> list[dict]:
    """CVEs with a description but no vector for the active model (newest first)."""
    rows = await db.execute_fetchall(
        """
        SELECT c.cve_id, c.description
        FROM cves c
        LEFT JOIN cve_embeddings e
          ON e.cve_id = c.cve_id AND e.model = ?
        WHERE e.cve_id IS NULL
          AND c.description IS NOT NULL
          AND c.description != ''
        ORDER BY c.published DESC
        LIMIT ?
        """,
        (model, limit),
    )
    return [{"cve_id": row["cve_id"], "description": row["description"]} for row in rows]


async def get_cve_summaries_by_ids(
    db: aiosqlite.Connection, cve_ids: list[str]
) -> dict[str, dict]:
    """Hydrate related-CVE cards (same fields the product heuristic returns)."""
    result: dict[str, dict] = {}
    normalized = [c.upper() for c in cve_ids if c]
    for i in range(0, len(normalized), _SQLITE_IN_CHUNK):
        chunk = normalized[i : i + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, description, cvss_score, severity, published, epss_score
            FROM cves WHERE cve_id IN ({placeholders})
            """,
            chunk,
        )
        for row in rows:
            result[row["cve_id"]] = {
                "cve_id": row["cve_id"],
                "description": row["description"] or "",
                "cvss_score": row["cvss_score"],
                "severity": row["severity"],
                "published": row["published"],
                "epss_score": row["epss_score"],
            }
    return result


# --- LLM product extraction for NVD-unanalyzed CVEs (V1.3 Theme 7) ---


async def get_cves_for_llm_product_extraction(
    db: aiosqlite.Connection, limit: int = 25, retry_hours: float = 168
) -> list[dict]:
    """CVEs with no CPE data and no affected products yet (NVD-unanalyzed).

    Skips CVEs attempted within the negative-cache window
    (feed_cache key ``llm_products:<cve_id>``).
    """
    rows = await db.execute_fetchall(
        """
        SELECT c.cve_id, c.description
        FROM cves c
        LEFT JOIN feed_cache fc
          ON fc.cache_key = 'llm_products:' || c.cve_id
         AND fc.cached_at > datetime('now', ?)
        WHERE fc.cache_key IS NULL
          AND (c.affected_products IS NULL OR c.affected_products IN ('', '[]'))
          AND (c.cpe_matches IS NULL OR c.cpe_matches IN ('', '[]'))
          AND c.description IS NOT NULL
          AND c.description != ''
        ORDER BY c.published DESC
        LIMIT ?
        """,
        (f"-{retry_hours} hours", limit),
    )
    return [{"cve_id": row["cve_id"], "description": row["description"]} for row in rows]


async def set_llm_affected_products(
    db: aiosqlite.Connection, cve_id: str, products: list[str]
) -> bool:
    """Write LLM-derived products ONLY if the field is still empty; mark
    provenance so the data stays distinguishable from official CPE."""
    if not products:
        return False
    cursor = await db.execute(
        """
        UPDATE cves
        SET affected_products = ?,
            affected_products_source = 'llm',
            updated_at = datetime('now')
        WHERE cve_id = ?
          AND (affected_products IS NULL OR affected_products IN ('', '[]'))
        """,
        (json.dumps(products), cve_id.upper()),
    )
    return cursor.rowcount > 0


async def backfill_display_fields(
    db: aiosqlite.Connection, cve_ids: list[str] | None = None
) -> int:
    """Fill MITRE / PoC from stored NVD fields when missing (no auto plain-summary)."""
    from enrichment.cve import extract_mitre_from_urls, has_public_poc_from_urls

    id_clause, id_params = _cve_id_filter_clause(cve_ids)
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, description, source_urls, mitre_technique, has_poc
        FROM cves
        WHERE (mitre_technique IS NULL OR has_poc = 0){id_clause}
        """,
        id_params,
    )
    updated = 0
    for row in rows:
        urls = json.loads(row["source_urls"] or "[]")
        mitre = row["mitre_technique"] or extract_mitre_from_urls(urls)
        poc_flag = row["has_poc"]
        if not poc_flag:
            poc_flag = 1 if has_public_poc_from_urls(urls) else 0
        if not mitre and not poc_flag:
            continue
        await db.execute(
            """
            UPDATE cves
            SET mitre_technique = COALESCE(?, mitre_technique),
                has_poc = CASE WHEN ? = 1 THEN 1 ELSE has_poc END
            WHERE cve_id = ?
            """,
            (mitre, poc_flag, row["cve_id"]),
        )
        updated += 1
    return updated


async def strip_auto_generated_summaries(
    db: aiosqlite.Connection, cve_ids: list[str] | None = None
) -> int:
    """Remove NVD first-sentence summaries so Plain English filter is meaningful."""
    from enrichment.cve import is_auto_generated_summary

    id_clause, id_params = _cve_id_filter_clause(cve_ids)
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, description, summary
        FROM cves
        WHERE summary IS NOT NULL AND TRIM(summary) != ''{id_clause}
        """,
        id_params,
    )
    cleared = 0
    for row in rows:
        if is_auto_generated_summary(row["summary"], row["description"]):
            await db.execute(
                "UPDATE cves SET summary = NULL WHERE cve_id = ?",
                (row["cve_id"],),
            )
            cleared += 1
    return cleared




async def backfill_has_poc(
    db: aiosqlite.Connection, cve_ids: list[str] | None = None
) -> int:
    """Set has_poc from stored reference URLs (no NVD re-fetch)."""
    from enrichment.cve import has_public_poc_from_urls

    id_clause, id_params = _cve_id_filter_clause(cve_ids)
    rows = await db.execute_fetchall(
        f"SELECT cve_id, source_urls FROM cves WHERE has_poc = 0{id_clause}",
        id_params,
    )
    history: list[tuple[str, str, str, str]] = []
    updates: list[tuple[str]] = []
    for row in rows:
        urls = json.loads(row["source_urls"] or "[]")
        if not has_public_poc_from_urls(urls):
            continue
        history.append((row["cve_id"], "has_poc", "0", "1"))
        updates.append((row["cve_id"],))
    await _insert_cve_changes_batch(db, history)
    if updates:
        await db.executemany(
            "UPDATE cves SET has_poc = 1 WHERE cve_id = ?",
            updates,
        )
    return len(updates)


async def get_recent_cve_changes(
    db: aiosqlite.Connection,
    *,
    limit: int = 100,
    field_name: str | None = None,
    since_hours: int | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if field_name:
        clauses.append("field_name = ?")
        params.append(field_name)
    if since_hours is not None and since_hours > 0:
        clauses.append("detected_at >= datetime('now', ?)")
        params.append(f"-{since_hours} hours")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = await db.execute_fetchall(
        f"""
        SELECT id, cve_id, field_name, old_value, new_value, detected_at
        FROM cve_change_history
        {where}
        ORDER BY detected_at DESC, id DESC
        LIMIT ?
        """,
        params,
    )
    return [dict(r) for r in rows]


async def enrich_kev_summaries(db: aiosqlite.Connection) -> int:
    """Fill plain-English summary from CISA KEV short descriptions."""
    cursor = await db.execute(
        """
        UPDATE cves
        SET summary = (
            SELECT k.short_description
            FROM kev_deadlines k
            WHERE k.cve_id = cves.cve_id
              AND k.short_description IS NOT NULL
              AND k.short_description != ''
        )
        WHERE is_kev = 1
          AND (summary IS NULL OR summary = '')
          AND EXISTS (
            SELECT 1 FROM kev_deadlines k
            WHERE k.cve_id = cves.cve_id
              AND k.short_description IS NOT NULL
              AND k.short_description != ''
          )
        """
    )
    return cursor.rowcount


async def upsert_kev(db: aiosqlite.Connection, entry: dict) -> None:
    cwes = entry.get("cwes") or []
    if not isinstance(cwes, list):
        cwes = []
    await db.execute(
        """
        INSERT INTO kev_deadlines (
            cve_id, product, short_description, required_action, due_date,
            date_added, vendor_project, vulnerability_name, known_ransomware,
            cwes, updated_at
        )
        VALUES (
            :cve_id, :product, :short_description, :required_action, :due_date,
            :date_added, :vendor_project, :vulnerability_name, :known_ransomware,
            :cwes, datetime('now')
        )
        ON CONFLICT(cve_id) DO UPDATE SET
            product = excluded.product,
            short_description = excluded.short_description,
            required_action = excluded.required_action,
            due_date = excluded.due_date,
            date_added = excluded.date_added,
            vendor_project = excluded.vendor_project,
            vulnerability_name = excluded.vulnerability_name,
            known_ransomware = excluded.known_ransomware,
            cwes = excluded.cwes,
            updated_at = datetime('now')
        """,
        {
            "cve_id": entry.get("cveID", ""),
            "product": entry.get("product", ""),
            "short_description": entry.get("shortDescription", ""),
            "required_action": entry.get("requiredAction", ""),
            "due_date": entry.get("dueDate", ""),
            "date_added": entry.get("dateAdded", ""),
            "vendor_project": entry.get("vendorProject", ""),
            "vulnerability_name": entry.get("vulnerabilityName", ""),
            "known_ransomware": entry.get("knownRansomwareCampaignUse", ""),
            "cwes": json.dumps(cwes),
        },
    )


async def get_ioc_cache(db: aiosqlite.Connection, value: str) -> dict | None:
    row = await db.execute_fetchall(
        """
        SELECT result FROM ioc_cache
        WHERE value = ? AND cached_at > datetime('now', '-6 hours')
        """,
        (value,),
    )
    if row:
        return json.loads(row[0]["result"])
    return None


async def get_ioc_cache_batch(
    db: aiosqlite.Connection, values: list[str]
) -> dict[str, dict]:
    """Batch lookup of cached IOC enrichment results, keyed by value."""
    if not values:
        return {}
    distinct = sorted(set(values))
    placeholders = ",".join("?" * len(distinct))
    rows = await db.execute_fetchall(
        f"""
        SELECT value, result FROM ioc_cache
        WHERE value IN ({placeholders}) AND cached_at > datetime('now', '-6 hours')
        """,
        tuple(distinct),
    )
    return {row["value"]: json.loads(row["result"]) for row in rows}


async def set_ioc_cache(db: aiosqlite.Connection, value: str, ioc_type: str, result: dict) -> None:
    await db.execute(
        """
        INSERT INTO ioc_cache (value, ioc_type, result, cached_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(value) DO UPDATE SET
            result = excluded.result,
            cached_at = datetime('now')
        """,
        (value, ioc_type, json.dumps(result)),
    )


async def delete_feed_cache_prefix(db: aiosqlite.Connection, prefix: str) -> int:
    """Delete feed_cache rows whose key starts with prefix."""
    cursor = await db.execute(
        "DELETE FROM feed_cache WHERE cache_key LIKE ?",
        (f"{prefix}%",),
    )
    return cursor.rowcount or 0


async def get_feed_cache(
    db: aiosqlite.Connection, cache_key: str, max_age_hours: float
) -> dict | None:
    row = await db.execute_fetchall(
        """
        SELECT result FROM feed_cache
        WHERE cache_key = ?
          AND cached_at > datetime('now', ?)
        """,
        (cache_key, f"-{max_age_hours} hours"),
    )
    if row:
        return json.loads(row[0]["result"])
    return None


async def set_feed_cache(db: aiosqlite.Connection, cache_key: str, result: dict) -> None:
    await db.execute(
        """
        INSERT INTO feed_cache (cache_key, result, cached_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(cache_key) DO UPDATE SET
            result = excluded.result,
            cached_at = datetime('now')
        """,
        (cache_key, json.dumps(result)),
    )


async def get_cached_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    cached = await get_feed_cache(db, f"sploitus:{cve_id.upper()}", max_age_hours)
    if cached is None:
        return None
    return cached.get("exploits", [])


async def store_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, exploits: list[dict]
) -> None:
    await merge_cve_exploits(db, cve_id, exploits)
    merged = await read_cve_exploits_from_db(db, cve_id, max_age_hours=24 * 365)
    await set_feed_cache(
        db,
        f"sploitus:{cve_id.upper()}",
        {"exploits": merged or exploits},
    )


async def read_cve_exploits_from_db(
    db: aiosqlite.Connection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    rows = await db.execute_fetchall(
        """
        SELECT title, type, source, url, published_date
        FROM cve_exploits
        WHERE cve_id = ?
          AND fetched_at > datetime('now', ?)
        ORDER BY published_date DESC
        """,
        (cve_id.upper(), f"-{max_age_hours} hours"),
    )
    if not rows:
        return None
    return [
        {
            "title": row["title"],
            "type": row["type"],
            "source": row["source"],
            "url": row["url"],
            "published_date": row["published_date"],
        }
        for row in rows
    ]


async def update_cve_source_urls(
    db: aiosqlite.Connection, cve_id: str, source_urls: list[str]
) -> None:
    await db.execute(
        """
        UPDATE cves
        SET source_urls = ?, updated_at = datetime('now')
        WHERE cve_id = ?
        """,
        (json.dumps(source_urls), cve_id.upper()),
    )


async def get_cve_ids_missing_circl_capec(
    db: aiosqlite.Connection, limit: int = 100
) -> list[str]:
    rows = await db.execute_fetchall(
        """
        SELECT c.cve_id
        FROM cves c
        LEFT JOIN feed_cache fc
          ON fc.cache_key = 'circl:' || c.cve_id
         AND fc.cached_at > datetime('now', '-168 hours')
        WHERE fc.cache_key IS NULL
        ORDER BY c.is_kev DESC, c.has_poc DESC, c.published DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [row["cve_id"] for row in rows]


async def replace_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, exploits: list[dict]
) -> None:
    key = cve_id.upper()
    await db.execute("DELETE FROM cve_exploits WHERE cve_id = ?", (key,))
    if exploits:
        await db.executemany(
            """
            INSERT INTO cve_exploits (
                cve_id, title, type, source, url, published_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            [
                (
                    key,
                    exp.get("title") or "",
                    exp.get("type") or "poc",
                    exp.get("source") or "",
                    exp.get("url") or "",
                    exp.get("published_date") or "",
                )
                for exp in exploits
            ],
        )


async def _sqlite_changes(db: aiosqlite.Connection) -> int:
    """Rows changed by the last statement — reliable when rowcount is -1/0."""
    row = await db.execute_fetchall("SELECT changes() AS n")
    return int(row[0]["n"] or 0)


async def merge_cve_exploits(
    db: aiosqlite.Connection, cve_id: str, exploits: list[dict]
) -> int:
    """Insert exploit rows for a CVE; skip duplicates by (cve_id, url)."""
    key = cve_id.upper()
    inserted = 0
    for exp in exploits:
        url = (exp.get("url") or "").strip()
        if not url:
            continue
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO cve_exploits (
                cve_id, title, type, source, url, published_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                key,
                exp.get("title") or "",
                exp.get("type") or "poc",
                exp.get("source") or "",
                url,
                exp.get("published_date") or "",
            ),
        )
        rc = cursor.rowcount
        if rc is None or rc < 0:
            inserted += await _sqlite_changes(db)
        elif rc > 0:
            inserted += rc
    return inserted


async def replace_cve_exploits_by_source(
    db: aiosqlite.Connection, source: str, cve_exploits: dict[str, list[dict]]
) -> tuple[int, int]:
    """Replace all rows for a feed source; returns (rows_inserted, cves_touched)."""
    await db.execute("DELETE FROM cve_exploits WHERE source = ?", (source,))
    rows: list[tuple] = []
    seen: set[tuple[str, str]] = set()
    for cve_id, exploits in cve_exploits.items():
        key = cve_id.upper()
        for exp in exploits:
            url = (exp.get("url") or "").strip()
            if not url:
                continue
            dedupe_key = (key, url)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                (
                    key,
                    exp.get("title") or "",
                    exp.get("type") or "poc",
                    source,
                    url,
                    exp.get("published_date") or "",
                )
            )
    if rows:
        await db.executemany(
            """
            INSERT OR IGNORE INTO cve_exploits (
                cve_id, title, type, source, url, published_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            rows,
        )
    return len(rows), len(cve_exploits)


async def mark_has_poc_additive(
    db: aiosqlite.Connection, cve_ids: list[str] | set[str]
) -> int:
    """Set has_poc=1 for the given CVE IDs; never downgrade from 1."""
    ids = sorted({str(c).upper() for c in cve_ids if c})
    if not ids:
        return 0
    rows: list = []
    for offset in range(0, len(ids), _SQLITE_IN_CHUNK):
        chunk = ids[offset : offset + _SQLITE_IN_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        chunk_rows = await db.execute_fetchall(
            f"""
            SELECT cve_id FROM cves
            WHERE cve_id IN ({placeholders}) AND COALESCE(has_poc, 0) = 0
            """,
            chunk,
        )
        rows.extend(chunk_rows)
    if not rows:
        return 0
    history = [(row["cve_id"], "has_poc", "0", "1") for row in rows]
    await _insert_cve_changes_batch(db, history)
    updated = 0
    for row in rows:
        cve_key = row["cve_id"]
        cursor = await db.execute(
            """
            UPDATE cves SET has_poc = 1
            WHERE cve_id = ? AND COALESCE(has_poc, 0) = 0
            """,
            (cve_key,),
        )
        rc = cursor.rowcount
        if rc is None or rc < 0:
            updated += await _sqlite_changes(db)
        elif rc > 0:
            updated += rc
    return updated



async def upsert_otx_pulses(
    db: aiosqlite.Connection, pulses: list[dict]
) -> None:
    """Upsert pulse dimension rows (caller commits)."""
    if not pulses:
        return
    await db.executemany(
        """
        INSERT INTO otx_pulses (
            pulse_id, pulse_name, author, created_date, adversary,
            malware_families, tags, targeted_countries, ioc_count, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(pulse_id) DO UPDATE SET
            pulse_name = excluded.pulse_name,
            author = excluded.author,
            created_date = excluded.created_date,
            adversary = excluded.adversary,
            malware_families = excluded.malware_families,
            tags = excluded.tags,
            targeted_countries = excluded.targeted_countries,
            ioc_count = excluded.ioc_count,
            fetched_at = excluded.fetched_at
        """,
        [
            (
                p.get("pulse_id") or "",
                p.get("pulse_name") or "",
                p.get("author") or "",
                p.get("created_date") or "",
                p.get("adversary") or "",
                json.dumps(p.get("malware_families") or []),
                json.dumps(p.get("tags") or []),
                json.dumps(p.get("targeted_countries") or []),
                int(p.get("ioc_count") or 0),
            )
            for p in pulses
            if p.get("pulse_id")
        ],
    )


async def replace_otx_cve_pulses(
    db: aiosqlite.Connection, cve_id: str, pulses: list[dict]
) -> None:
    key = cve_id.upper()
    await db.execute("DELETE FROM otx_cve_pulses WHERE cve_id = ?", (key,))
    if pulses:
        await upsert_otx_pulses(db, pulses)
        await db.executemany(
            """
            INSERT INTO otx_cve_pulses (
                cve_id, pulse_id, pulse_name, author, created_date,
                adversary, malware_families, ioc_count, tags, targeted_countries,
                fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            [
                (
                    key,
                    p.get("pulse_id") or "",
                    p.get("pulse_name") or "",
                    p.get("author") or "",
                    p.get("created_date") or "",
                    p.get("adversary") or "",
                    json.dumps(p.get("malware_families") or []),
                    int(p.get("ioc_count") or 0),
                    json.dumps(p.get("tags") or []),
                    json.dumps(p.get("targeted_countries") or []),
                )
                for p in pulses
                if p.get("pulse_id")
            ],
        )


async def store_otx_cve_pulses(
    db: aiosqlite.Connection, cve_id: str, pulses: list[dict]
) -> None:
    key = cve_id.upper()
    await replace_otx_cve_pulses(db, key, pulses)
    await set_feed_cache(db, f"otx:cve:{key}", {"pulses": pulses})


async def read_otx_cve_pulses(
    db: aiosqlite.Connection, cve_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    rows = await db.execute_fetchall(
        """
        SELECT pulse_id, pulse_name, author, created_date, adversary,
               malware_families, ioc_count, tags, targeted_countries
        FROM otx_cve_pulses
        WHERE cve_id = ?
          AND fetched_at > datetime('now', ?)
        ORDER BY created_date DESC
        """,
        (cve_id.upper(), f"-{max_age_hours} hours"),
    )
    if not rows:
        return None
    return [
        {
            "pulse_id": row["pulse_id"],
            "pulse_name": row["pulse_name"],
            "author": row["author"],
            "created_date": row["created_date"],
            "adversary": row["adversary"],
            "malware_families": json.loads(row["malware_families"] or "[]"),
            "ioc_count": row["ioc_count"],
            "tags": json.loads(row["tags"] or "[]"),
            "targeted_countries": json.loads(row["targeted_countries"] or "[]"),
        }
        for row in rows
    ]


async def replace_otx_pulse_iocs(
    db: aiosqlite.Connection, pulse_id: str, iocs: list[dict]
) -> None:
    from correlation.ioc_normalize import normalize_ioc_row

    await db.execute("DELETE FROM otx_pulse_iocs WHERE pulse_id = ?", (pulse_id,))
    if not iocs:
        return
    normalized_rows: list[tuple] = []
    for row in iocs:
        norm = normalize_ioc_row(row)
        if norm is None:
            continue
        normalized_rows.append(
            (
                pulse_id,
                norm.get("ioc_type") or "",
                norm.get("ioc_value") or "",
                norm.get("description") or "",
            )
        )
    if not normalized_rows:
        return
    await db.executemany(
        """
        INSERT INTO otx_pulse_iocs (
            pulse_id, ioc_type, ioc_value, description, fetched_at
        ) VALUES (?, ?, ?, ?, datetime('now'))
        """,
        normalized_rows,
    )


async def store_otx_pulse_iocs(
    db: aiosqlite.Connection, pulse_id: str, iocs: list[dict]
) -> None:
    await replace_otx_pulse_iocs(db, pulse_id, iocs)
    await set_feed_cache(db, f"otx:pulse:{pulse_id}", {"iocs": iocs})


async def read_otx_pulse_iocs(
    db: aiosqlite.Connection, pulse_id: str, max_age_hours: float = 6
) -> list[dict] | None:
    rows = await db.execute_fetchall(
        """
        SELECT ioc_type, ioc_value, description
        FROM otx_pulse_iocs
        WHERE pulse_id = ?
          AND fetched_at > datetime('now', ?)
        """,
        (pulse_id, f"-{max_age_hours} hours"),
    )
    if not rows:
        return None
    return [
        {
            "ioc_type": row["ioc_type"],
            "ioc_value": row["ioc_value"],
            "description": row["description"],
        }
        for row in rows
    ]


async def list_correlation_suppressions(
    db: aiosqlite.Connection, cve_id: str
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT id, cve_id, scope, scope_key, reason, dismissed_by, created_at
        FROM correlation_suppressions
        WHERE cve_id = ?
        ORDER BY created_at DESC
        """,
        (cve_id.upper(),),
    )
    return [dict(row) for row in rows]


async def insert_correlation_suppression(
    db: aiosqlite.Connection,
    cve_id: str,
    scope: str,
    scope_key: str,
    reason: str = "",
    dismissed_by: str = "",
) -> dict:
    await db.execute(
        """
        INSERT INTO correlation_suppressions (cve_id, scope, scope_key, reason, dismissed_by, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(cve_id, scope, scope_key) DO UPDATE SET
            reason = excluded.reason,
            dismissed_by = excluded.dismissed_by,
            created_at = datetime('now')
        """,
        (cve_id.upper(), scope, scope_key, reason, dismissed_by),
    )
    rows = await db.execute_fetchall(
        """
        SELECT id, cve_id, scope, scope_key, reason, dismissed_by, created_at
        FROM correlation_suppressions
        WHERE cve_id = ? AND scope = ? AND scope_key = ?
        """,
        (cve_id.upper(), scope, scope_key),
    )
    return dict(rows[0]) if rows else {
        "cve_id": cve_id.upper(),
        "scope": scope,
        "scope_key": scope_key,
        "reason": reason,
        "dismissed_by": dismissed_by,
    }


async def delete_correlation_suppression(
    db: aiosqlite.Connection, cve_id: str, scope: str, scope_key: str
) -> bool:
    cursor = await db.execute(
        """
        DELETE FROM correlation_suppressions
        WHERE cve_id = ? AND scope = ? AND scope_key = ?
        """,
        (cve_id.upper(), scope, scope_key),
    )
    return (cursor.rowcount or 0) > 0


async def get_recent_cve_ids_for_otx(
    db: aiosqlite.Connection, days: int = 7
) -> list[str]:
    rows = await db.execute_fetchall(
        """
        SELECT cve_id FROM cves
        WHERE published >= DATE('now', ?)
        ORDER BY published DESC
        """,
        (f"-{days} days",),
    )
    return [row["cve_id"] for row in rows]


async def get_prioritized_cve_ids_for_otx(
    db: aiosqlite.Connection,
    days: int | None = None,
    backlog_cap: int = 200,
) -> list[str]:
    """
    Tiered CVE set for OTX pulse refresh (P0 → P3).
    P0: KEV or watchlisted. P1: high EPSS, PoC, or changed in 7d.
    P2: published within sync window. P3: backlog cap by recency.
    """
    from correlation.config import get_otx_cve_sync_days

    window_days = days if days is not None else get_otx_cve_sync_days()
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(rows: list) -> None:
        for row in rows:
            cid = row["cve_id"]
            if cid not in seen:
                seen.add(cid)
                ordered.append(cid)

    p0 = await db.execute_fetchall(
        """
        SELECT c.cve_id
        FROM cves c
        LEFT JOIN watchlist w ON w.cve_id = c.cve_id AND w.state = 'pin'
        WHERE COALESCE(c.is_kev, 0) = 1 OR w.cve_id IS NOT NULL
        ORDER BY c.published DESC
        """
    )
    _add(p0)

    p1 = await db.execute_fetchall(
        """
        SELECT c.cve_id
        FROM cves c
        WHERE (
            COALESCE(c.epss_score, 0) >= 0.5
            OR COALESCE(c.has_poc, 0) = 1
            OR datetime(c.modified) >= datetime('now', '-7 days')
        )
        ORDER BY COALESCE(c.epss_score, 0) DESC, c.published DESC
        LIMIT 500
        """
    )
    _add(p1)

    p2 = await db.execute_fetchall(
        """
        SELECT cve_id FROM cves
        WHERE published >= DATE('now', ?)
        ORDER BY published DESC
        """,
        (f"-{window_days} days",),
    )
    _add(p2)

    if len(ordered) < backlog_cap:
        p3 = await db.execute_fetchall(
            """
            SELECT cve_id FROM cves
            ORDER BY published DESC
            LIMIT ?
            """,
            (backlog_cap,),
        )
        _add(p3)

    return ordered[:backlog_cap] if backlog_cap > 0 else ordered


async def get_cve_count(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM cves")
    return rows[0]["cnt"] if rows else 0


async def get_last_updated(db: aiosqlite.Connection) -> str | None:
    rows = await db.execute_fetchall(
        "SELECT MAX(updated_at) as ts FROM cves"
    )
    return rows[0]["ts"] if rows else None


async def get_all_cve_ids(db: aiosqlite.Connection) -> list:
    rows = await db.execute_fetchall("SELECT cve_id FROM cves")
    return [r["cve_id"] for r in rows]


async def get_all_cve_ids_set(db: aiosqlite.Connection) -> set[str]:
    rows = await db.execute_fetchall("SELECT cve_id FROM cves")
    return {r["cve_id"] for r in rows}


async def replace_mitre_techniques(db: aiosqlite.Connection, techniques: list[dict]) -> None:
    await db.execute("DELETE FROM mitre_techniques")
    if not techniques:
        return
    await db.executemany(
        """
        INSERT INTO mitre_techniques (
            technique_id, name, description, tactic, url, platforms, detection
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                t["technique_id"],
                t["name"],
                t.get("description", ""),
                t.get("tactic", ""),
                t["url"],
                json.dumps(t.get("platforms", [])),
                t.get("detection", ""),
            )
            for t in techniques
        ],
    )


async def clear_cve_technique_map(db: aiosqlite.Connection) -> None:
    await db.execute("DELETE FROM cve_technique_map")


async def upsert_cve_technique_pairs(
    db: aiosqlite.Connection, pairs: list[tuple[str, str]], *, chunk_size: int = 5000
) -> int:
    if not pairs:
        return 0
    sql = """
        INSERT OR IGNORE INTO cve_technique_map (cve_id, technique_id)
        VALUES (?, ?)
    """
    for i in range(0, len(pairs), chunk_size):
        chunk = pairs[i : i + chunk_size]
        await db.executemany(sql, chunk)
    return len(pairs)


async def get_techniques_for_cve(db: aiosqlite.Connection, cve_id: str) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT m.technique_id, m.name, m.tactic, m.url, m.description, m.detection
        FROM cve_technique_map c
        JOIN mitre_techniques m ON c.technique_id = m.technique_id
        WHERE c.cve_id = ?
        ORDER BY m.technique_id
        """,
        (cve_id.upper(),),
    )
    return [
        {
            "id": r["technique_id"],
            "name": r["name"],
            "tactic": r["tactic"],
            "url": r["url"],
            "detection": (r["detection"] or "").strip(),
            "description": (r["description"] or "").strip(),
        }
        for r in rows
    ]


async def get_top_techniques(db: aiosqlite.Connection, limit: int = 10) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT m.technique_id, m.name, m.tactic, m.url, COUNT(*) AS cnt
        FROM cve_technique_map c
        JOIN mitre_techniques m ON c.technique_id = m.technique_id
        GROUP BY m.technique_id, m.name, m.tactic, m.url
        ORDER BY cnt DESC, m.technique_id
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "technique_id": r["technique_id"],
            "name": r["name"],
            "tactic": r["tactic"],
            "cve_count": r["cnt"],
            "count": r["cnt"],
            "url": r["url"],
        }
        for r in rows
    ]


async def get_mitre_technique_count(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM mitre_techniques")
    return rows[0]["cnt"] if rows else 0


async def replace_atlas_techniques(db: aiosqlite.Connection, techniques: list[dict]) -> None:
    await db.execute("DELETE FROM atlas_techniques")
    if not techniques:
        return
    await db.executemany(
        """
        INSERT INTO atlas_techniques (
            technique_id, name, description, tactic, tactic_id, url
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                t["technique_id"],
                t["name"],
                t.get("description", ""),
                t.get("tactic", ""),
                t.get("tactic_id", ""),
                t["url"],
            )
            for t in techniques
        ],
    )


async def replace_atlas_case_studies(db: aiosqlite.Connection, studies: list[dict]) -> None:
    await db.execute("DELETE FROM atlas_case_studies")
    if not studies:
        return
    await db.executemany(
        """
        INSERT INTO atlas_case_studies (
            study_id, name, summary, summary_full, techniques,
            target, date, study_type, cve_ids
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                s["study_id"],
                s["name"],
                s.get("summary", ""),
                s.get("summary_full", ""),
                json.dumps(s.get("techniques", [])),
                s.get("target", ""),
                s.get("date", ""),
                s.get("study_type", ""),
                json.dumps(s.get("cve_ids", [])),
            )
            for s in studies
        ],
    )


async def get_atlas_technique_count(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM atlas_techniques")
    return rows[0]["cnt"] if rows else 0


async def get_atlas_techniques_grouped(db: aiosqlite.Connection) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT technique_id, name, description, tactic, tactic_id, url
        FROM atlas_techniques
        ORDER BY tactic, technique_id
        """
    )
    groups: dict[str, dict] = {}
    for row in rows:
        tactic_name = row["tactic"] or "Uncategorized"
        tactic_id = row["tactic_id"] or tactic_name
        key = tactic_id
        if key not in groups:
            groups[key] = {
                "tactic_id": tactic_id,
                "tactic_name": tactic_name,
                "techniques": [],
            }
        groups[key]["techniques"].append(
            {
                "technique_id": row["technique_id"],
                "name": row["name"],
                "description": row["description"],
                "url": row["url"],
            }
        )
    return sorted(groups.values(), key=lambda g: g["tactic_name"])


def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def get_atlas_case_studies(
    db: aiosqlite.Connection, *, limit: int = 50
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT study_id, name, summary, summary_full, techniques,
               target, date, study_type, cve_ids
        FROM atlas_case_studies
        ORDER BY date DESC, name
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "study_id": r["study_id"],
            "name": r["name"],
            "summary": r["summary"],
            "summary_full": r["summary_full"],
            "techniques": _parse_json_list(r["techniques"]),
            "target": r["target"],
            "date": r["date"],
            "study_type": r["study_type"],
            "cve_ids": _parse_json_list(r["cve_ids"]),
        }
        for r in rows
    ]

NVD_SYNC_WATERMARK_KEY = "nvd_last_mod_end"
EPSS_BACKFILL_DONE_KEY = "epss_backfill_done"


async def get_sync_state_value(db: aiosqlite.Connection, key: str) -> str | None:
    """Read any sync_state key; returns None when absent."""
    rows = await db.execute_fetchall(
        "SELECT value FROM sync_state WHERE key = ?",
        (key,),
    )
    return rows[0]["value"] if rows else None


async def set_sync_state_value(db: aiosqlite.Connection, key: str, value: str) -> None:
    """Upsert any sync_state key (caller commits)."""
    await db.execute(
        """
        INSERT INTO sync_state (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = datetime('now')
        """,
        (key, value),
    )


def get_stack_terms() -> str:
    """Operator stack profile for server-side matching (BRIEFR_STACK_TERMS)."""
    return os.environ.get("BRIEFR_STACK_TERMS", "").strip()


_WEBHOOK_ALERT_ALIASES = {
    "kev_alert": ("kev_alert", "kev_stack"),
    "kev_stack": ("kev_alert", "kev_stack"),
    "backup_failure": ("backup_failure", "backup_deadman"),
    "backup_deadman": ("backup_failure", "backup_deadman"),
}


def _webhook_alert_types(alert_type: str) -> tuple[str, ...]:
    return _WEBHOOK_ALERT_ALIASES.get(alert_type, (alert_type,))


async def was_webhook_alert_sent(
    db: aiosqlite.Connection, alert_type: str, target: str
) -> bool:
    types = _webhook_alert_types(alert_type)
    placeholders = ", ".join("?" for _ in types)
    rows = await db.execute_fetchall(
        f"""
        SELECT 1 FROM webhook_alert_log
        WHERE alert_type IN ({placeholders}) AND target = ?
        """,
        (*types, target),
    )
    return bool(rows)


async def record_webhook_alert(
    db: aiosqlite.Connection, alert_type: str, target: str
) -> None:
    await db.execute(
        """
        INSERT OR IGNORE INTO webhook_alert_log (alert_type, target)
        VALUES (?, ?)
        """,
        (alert_type, target),
    )


async def clear_webhook_alert(
    db: aiosqlite.Connection, alert_type: str, target: str
) -> None:
    types = _webhook_alert_types(alert_type)
    placeholders = ", ".join("?" for _ in types)
    await db.execute(
        f"DELETE FROM webhook_alert_log WHERE alert_type IN ({placeholders}) AND target = ?",
        (*types, target),
    )


async def record_webhook_delivery(
    db: aiosqlite.Connection,
    *,
    destination_id: str,
    event_type: str,
    dedupe_key: str | None,
    status: str,
    error: str | None,
) -> None:
    await db.execute(
        """
        INSERT INTO webhook_delivery_log (
            destination_id, event_type, dedupe_key, status, error
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (destination_id, event_type, dedupe_key, status, error),
    )


async def list_webhook_destinations(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    return await db.execute_fetchall(
        """
        SELECT id, kind, label, enabled, event_types, config_json, source,
               created_at, updated_at
        FROM webhook_destinations
        ORDER BY id
        """
    )


async def update_webhook_destination(
    db: aiosqlite.Connection,
    destination_id: str,
    *,
    enabled: bool | None = None,
    event_types: list[str] | None = None,
    label: str | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if enabled is not None:
        fields.append("enabled = ?")
        params.append(int(enabled))
    if event_types is not None:
        fields.append("event_types = ?")
        params.append(json.dumps(event_types))
    if label is not None:
        fields.append("label = ?")
        params.append(label)
    if not fields:
        return False
    fields.append("updated_at = datetime('now')")
    params.append(destination_id)
    cursor = await db.execute(
        f"UPDATE webhook_destinations SET {', '.join(fields)} WHERE id = ?",
        params,
    )
    return cursor.rowcount > 0


async def list_webhook_delivery_log(
    db: aiosqlite.Connection,
    *,
    destination_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[aiosqlite.Row], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if destination_id:
        conditions.append("destination_id = ?")
        params.append(destination_id)
    if event_type:
        types = _webhook_alert_types(event_type)
        placeholders = ", ".join("?" for _ in types)
        conditions.append(f"event_type IN ({placeholders})")
        params.extend(types)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_row = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM webhook_delivery_log {where}",
        params,
    )
    total = count_row[0]["cnt"] if count_row else 0
    rows = await db.execute_fetchall(
        f"""
        SELECT id, destination_id, event_type, dedupe_key, status, error, attempted_at
        FROM webhook_delivery_log
        {where}
        ORDER BY attempted_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return rows, total


async def filter_cves_matching_stack(
    db: aiosqlite.Connection, cve_ids: list[str], stack: str
) -> list[dict]:
    """Return CVE rows from cve_ids that match the comma-separated stack terms."""
    from routers.cves import _stack_match_clause

    normalized = [c.upper() for c in cve_ids if c]
    if not normalized or not stack.strip():
        return []
    clause, params, _terms = _stack_match_clause(stack)
    if not clause:
        return []
    placeholders = ",".join("?" * len(normalized))
    rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.description, c.severity, c.summary,
               (SELECT due_date FROM kev_deadlines k WHERE k.cve_id = c.cve_id) AS kev_due_date
        FROM cves c
        WHERE c.cve_id IN ({placeholders}) AND {clause}
        """,
        normalized + params,
    )
    return [dict(row) for row in rows]


async def insert_epss_history_rows(
    db: aiosqlite.Connection,
    rows: list[dict],
) -> int:
    """Bulk-insert EPSS history rows, skipping already-present (cve_id, date) pairs.

    Each dict must have keys ``cve_id`` (str), ``score`` (float), ``date`` (str).
    Returns the number of rows actually written.
    """
    if not rows:
        return 0
    tuples = [
        (r["cve_id"].upper(), r["score"], r["date"])
        for r in rows
        if r.get("cve_id") and r.get("date") and r.get("score") is not None
    ]
    if not tuples:
        return 0
    cursor = await db.executemany(
        "INSERT OR IGNORE INTO epss_history (cve_id, score, recorded_date) VALUES (?, ?, ?)",
        tuples,
    )
    return cursor.rowcount


async def get_nvd_sync_watermark(db: aiosqlite.Connection) -> str | None:
    rows = await db.execute_fetchall(
        "SELECT value FROM sync_state WHERE key = ?",
        (NVD_SYNC_WATERMARK_KEY,),
    )
    return rows[0]["value"] if rows else None


async def set_nvd_sync_watermark(db: aiosqlite.Connection, value: str) -> None:
    await db.execute(
        """
        INSERT INTO sync_state (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = datetime('now')
        """,
        (NVD_SYNC_WATERMARK_KEY, value),
    )


async def seed_nvd_watermark_from_cves(db: aiosqlite.Connection) -> str | None:
    rows = await db.execute_fetchall(
        """
        SELECT MAX(modified) AS latest
        FROM cves
        WHERE modified IS NOT NULL AND modified != ''
        """
    )
    latest = rows[0]["latest"] if rows else None
    if not latest:
        return None
    await set_nvd_sync_watermark(db, latest)
    return latest


async def resolve_nvd_watermark(db: aiosqlite.Connection, *, min_cves: int = 10) -> str | None:
    watermark = await get_nvd_sync_watermark(db)
    if watermark:
        return watermark
    count = await get_cve_count(db)
    if count < min_cves:
        return None
    return await seed_nvd_watermark_from_cves(db)

async def clear_cve_atlas_map(db: aiosqlite.Connection) -> None:
    await db.execute("DELETE FROM cve_atlas_map")


async def upsert_cve_atlas_pairs(
    db: aiosqlite.Connection, pairs: list[tuple[str, str]]
) -> int:
    if not pairs:
        return 0
    await db.executemany(
        """
        INSERT OR IGNORE INTO cve_atlas_map (cve_id, technique_id)
        VALUES (?, ?)
        """,
        pairs,
    )
    return len(pairs)


async def replace_cve_atlas_map_for_cve(
    db: aiosqlite.Connection, cve_id: str, technique_ids: list[str]
) -> None:
    cve_key = cve_id.upper()
    await db.execute("DELETE FROM cve_atlas_map WHERE cve_id = ?", (cve_key,))
    if technique_ids:
        await upsert_cve_atlas_pairs(
            db, [(cve_key, tid.upper()) for tid in technique_ids if tid]
        )


async def get_atlas_techniques_for_cve(
    db: aiosqlite.Connection, cve_id: str
) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT t.technique_id, t.name, t.description, t.tactic, t.url
        FROM cve_atlas_map m
        JOIN atlas_techniques t ON t.technique_id = m.technique_id
        WHERE m.cve_id = ?
        ORDER BY t.technique_id
        """,
        (cve_id.upper(),),
    )
    return [
        {
            "technique_id": r["technique_id"],
            "id": r["technique_id"],
            "name": r["name"],
            "description": r["description"],
            "tactic": r["tactic"],
            "url": r["url"],
        }
        for r in rows
    ]


async def get_atlas_case_studies_for_cve(
    db: aiosqlite.Connection, cve_id: str, *, limit: int = 2
) -> list[dict]:
    cve_key = cve_id.upper()
    rows = await db.execute_fetchall(
        """
        SELECT study_id, name, summary, techniques, target, date, cve_ids
        FROM atlas_case_studies
        WHERE cve_ids LIKE ?
        ORDER BY date DESC, name
        LIMIT ?
        """,
        (f'%"{cve_key}"%', limit),
    )
    return [
        {
            "study_id": row["study_id"],
            "name": row["name"],
            "summary": row["summary"],
            "techniques": _parse_json_list(row["techniques"]),
            "target": row["target"],
            "incident_date": row["date"],
        }
        for row in rows
    ]


async def count_ai_ml_profile_alerts(
    db: aiosqlite.Connection, frameworks: list[str]
) -> int:
    if not frameworks:
        return 0
    rows = await db.execute_fetchall(
        """
        SELECT cve_id, description, affected_products
        FROM cves
        WHERE has_ai_context = 1
        """
    )
    from feeds.ai_context import cve_matches_declared_frameworks

    count = 0
    for row in rows:
        cve = {
            "description": row["description"],
            "affected_products": _parse_json_list(row["affected_products"])
            if isinstance(row["affected_products"], str)
            else row["affected_products"],
        }
        if cve_matches_declared_frameworks(cve, frameworks):
            count += 1
    return count


async def refresh_all_cve_ai_context(db: aiosqlite.Connection) -> dict[str, int]:
    """Recompute has_ai_context and cve_atlas_map for every CVE."""
    from feeds.ai_context import analyze_cve_ai_context

    rows = await db.execute_fetchall(
        """
        SELECT cve_id, description, affected_products
        FROM cves
        """
    )
    atlas_rows = await db.execute_fetchall(
        "SELECT technique_id FROM atlas_techniques"
    )
    known_atlas = {r["technique_id"] for r in atlas_rows}

    cve_updates: list[tuple[int, str]] = []
    atlas_pairs: list[tuple[str, str]] = []
    flagged = 0

    for row in rows:
        cve_id = row["cve_id"]
        products = _parse_json_list(row["affected_products"])
        cve = {"description": row["description"], "affected_products": products}
        has_ai, tids = analyze_cve_ai_context(cve)
        cve_updates.append((1 if has_ai else 0, cve_id))
        if has_ai:
            flagged += 1
        cve_key = cve_id.upper()
        for tid in tids:
            if tid in known_atlas:
                atlas_pairs.append((cve_key, tid.upper()))

    if cve_updates:
        await db.executemany(
            "UPDATE cves SET has_ai_context = ? WHERE cve_id = ?",
            cve_updates,
        )

    await db.execute("DELETE FROM cve_atlas_map")
    if atlas_pairs:
        await db.executemany(
            """
            INSERT OR IGNORE INTO cve_atlas_map (cve_id, technique_id)
            VALUES (?, ?)
            """,
            atlas_pairs,
        )

    await db.commit()
    return {"cves_flagged": flagged, "atlas_links": len(atlas_pairs)}


async def replace_mitre_groups(
    db: aiosqlite.Connection, groups: list[dict]
) -> int:
    """Upsert ATT&CK group rows parsed from STIX."""
    if not groups:
        return 0
    await db.executemany(
        """
        INSERT INTO mitre_groups (group_id, name, aliases, description, sectors, url)
        VALUES (:group_id, :name, :aliases, :description, :sectors, :url)
        ON CONFLICT(group_id) DO UPDATE SET
            name        = excluded.name,
            aliases     = excluded.aliases,
            description = excluded.description,
            sectors     = excluded.sectors,
            url         = excluded.url
        """,
        [
            {
                "group_id": g["group_id"],
                "name": g["name"],
                "aliases": json.dumps(g.get("aliases") or []),
                "description": g.get("description") or "",
                "sectors": json.dumps(g.get("sectors") or []),
                "url": g.get("url") or "",
            }
            for g in groups
        ],
    )
    return len(groups)


async def upsert_group_technique_pairs(
    db: aiosqlite.Connection, pairs: list[tuple[str, str]]
) -> int:
    """Insert (group_id, technique_id) links, ignoring duplicates."""
    if not pairs:
        return 0
    await db.executemany(
        "INSERT OR IGNORE INTO group_technique_map (group_id, technique_id) VALUES (?, ?)",
        pairs,
    )
    return len(pairs)


async def get_mitre_group_count(db: aiosqlite.Connection) -> int:
    row = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM mitre_groups")
    return int(row[0]["cnt"]) if row else 0


async def match_cves_for_assets(
    db: aiosqlite.Connection, assets: list[dict]
) -> dict[str, int]:
    """Score every CVE in the database against analyst assets (in-memory request only)."""
    from matching.cpe import score_cve_for_assets

    rows = await db.execute_fetchall(
        "SELECT cve_id, cpe_matches, affected_products FROM cves"
    )
    scores: dict[str, int] = {}
    for row in rows:
        cpe_matches = _parse_json_list(row["cpe_matches"])
        if not cpe_matches:
            for entry in _parse_json_list(row["affected_products"]):
                if isinstance(entry, str) and ":" in entry:
                    vendor, product = entry.split(":", 1)
                    cpe_matches.append({"vendor": vendor, "product": product})

        score = score_cve_for_assets(cpe_matches, assets)
        if score > 0:
            scores[row["cve_id"]] = score
    return scores
