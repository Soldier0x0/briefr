"""Owns WRITABLE_CONFIG_KEYS schema for admin operator settings (single source).

Replaces the three separately-maintained sets that used to live in
routers/admin.py (WRITABLE_CONFIG_KEYS, INTEGER_KEYS, RESTART_REQUIRED_KEYS)
with one schema carrying type, bounds, help text, and section grouping —
so the frontend can render labels/help text and pre-validate without a
second hand-maintained copy of the same key list, and adding a new
writable key is a one-line addition here instead of three.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

from dataclasses import dataclass, field


# How a saved value takes effect in the running process.
APPLY_IMMEDIATE = "immediate"
APPLY_SCHEDULER_RESCHEDULE = "scheduler_reschedule"
APPLY_RESTART = "restart"

_SCHEDULER_RESCHEDULE_KEYS: frozenset[str] = frozenset({
    "NVD_SYNC_INTERVAL_HOURS",
    "KEV_SYNC_INTERVAL_MINUTES",
    "EPSS_SYNC_INTERVAL_HOURS",
    "INCIDENT_FEED_REFRESH_MINUTES",
    "VULNRICHMENT_SYNC_INTERVAL_HOURS",
    "CVELISTV5_SYNC_INTERVAL_MINUTES",
    "MITRE_REFRESH_HOUR",
    "MITRE_REFRESH_MINUTE",
    "CORRELATION_HOUR",
    "CORRELATION_MINUTE",
    "OTX_CORRELATION_HOUR",
    "OTX_CORRELATION_MINUTE",
    "EXPLOIT_SOURCES_SYNC_INTERVAL_HOURS",
    "EMBEDDINGS_SYNC_INTERVAL_HOURS",
    "LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS",
    "BACKUP_INTERVAL_HOURS",
})


@dataclass(frozen=True)
class ConfigField:
    key: str
    section: str  # UI grouping: matches the admin panel's card titles
    type: str = "str"  # "int" | "str" | "bool" | "enum" | "secret" | "url"
    min: int | None = None
    max: int | None = None
    enum_values: tuple[str, ...] = field(default_factory=tuple)
    help_text: str = ""
    restart_required: bool = False
    apply_strategy: str = ""  # empty = derive from restart_required / scheduler map
    display_label: str = ""
    unit: str = ""


CONFIG_SCHEMA: tuple[ConfigField, ...] = (
    # ── Scheduler intervals — NVD / KEV / EPSS ──────────────────────────────
    ConfigField("NVD_SYNC_INTERVAL_HOURS", "scheduler_main", "int", min=1, max=24,
                help_text="How often the NVD incremental sync job runs.",
                display_label="NVD sync interval", unit="h"),
    ConfigField("KEV_SYNC_INTERVAL_MINUTES", "scheduler_main", "int", min=1, max=1440,
                help_text="How often the CISA KEV catalog is re-fetched.",
                display_label="KEV sync interval", unit="min"),
    ConfigField("EPSS_SYNC_INTERVAL_HOURS", "scheduler_main", "int", min=1, max=24,
                help_text="How often FIRST EPSS scores are re-fetched.",
                display_label="EPSS sync interval", unit="h"),
    ConfigField("INCIDENT_FEED_REFRESH_MINUTES", "scheduler_main", "int", min=1, max=1440,
                help_text="How often the incident/news RSS snapshot is rebuilt.",
                display_label="Incident feed refresh", unit="min"),
    ConfigField("VULNRICHMENT_SYNC_INTERVAL_HOURS", "scheduler_main", "int", min=1, max=24,
                help_text="How often the CISA Vulnrichment gap-fill sync runs.",
                display_label="Vulnrichment sync interval", unit="h"),
    ConfigField("CVELISTV5_SYNC_INTERVAL_MINUTES", "scheduler_main", "int", min=1, max=1440,
                help_text="How often the CVE List V5 (GitHub) delta sync runs.",
                display_label="CVE List V5 sync interval", unit="min"),
    ConfigField("SCHEDULER_DB_CONCURRENCY", "scheduler_main", "int", min=1, max=10,
                help_text="Max concurrent background scheduler jobs that may hold DB pool connections.",
                restart_required=True, display_label="Scheduler DB concurrency"),

    # ── Scheduler intervals — cron & timezone ───────────────────────────────
    ConfigField("SCHEDULER_TIMEZONE", "scheduler_cron", "str", restart_required=True,
                help_text="IANA timezone (e.g. Asia/Kolkata) the weekly MITRE refresh is scheduled in."),
    ConfigField("MITRE_REFRESH_HOUR", "scheduler_cron", "int", min=0, max=23,
                help_text="Hour (0-23, SCHEDULER_TIMEZONE) the weekly MITRE/ATLAS refresh runs.",
                display_label="MITRE refresh hour", unit="h"),
    ConfigField("MITRE_REFRESH_MINUTE", "scheduler_cron", "int", min=0, max=59,
                help_text="Minute (0-59) the weekly MITRE/ATLAS refresh runs.",
                display_label="MITRE refresh minute", unit="min"),
    ConfigField("CORRELATION_HOUR", "scheduler_cron", "int", min=0, max=23,
                help_text="Hour (0-23, CORRELATION_TIMEZONE) the nightly correlation job runs.",
                display_label="Correlation hour", unit="h"),
    ConfigField("CORRELATION_MINUTE", "scheduler_cron", "int", min=0, max=59,
                help_text="Minute (0-59) the nightly correlation job runs.",
                display_label="Correlation minute", unit="min"),
    ConfigField("CORRELATION_TIMEZONE", "scheduler_cron", "str", restart_required=True,
                help_text="IANA timezone the nightly correlation job is scheduled in."),
    ConfigField("OTX_CORRELATION_HOUR", "scheduler_cron", "int", min=0, max=23,
                help_text="Hour (0-23, OTX_CORRELATION_TIMEZONE) the OTX correlation job runs.",
                display_label="OTX correlation hour", unit="h"),
    ConfigField("OTX_CORRELATION_MINUTE", "scheduler_cron", "int", min=0, max=59,
                help_text="Minute (0-59) the OTX correlation job runs.",
                display_label="OTX correlation minute", unit="min"),
    ConfigField("OTX_CORRELATION_TIMEZONE", "scheduler_cron", "str", restart_required=True,
                help_text="IANA timezone the OTX correlation job is scheduled in."),
    ConfigField("CACHE_REFRESH_HOUR", "scheduler_cron", "int", min=0, max=23,
                help_text="Unused — no APScheduler job reads CACHE_REFRESH_HOUR (kept for env compatibility)."),
    ConfigField("CACHE_REFRESH_MINUTE", "scheduler_cron", "int", min=0, max=59,
                help_text="Unused — no APScheduler job reads CACHE_REFRESH_MINUTE (kept for env compatibility)."),

    # ── Ingest tuning ────────────────────────────────────────────────────────
    ConfigField("MAX_CVES_PER_FETCH", "ingest", "int", min=1,
                help_text="Maximum CVEs fetched per NVD API page."),
    ConfigField("NVD_DAYS_BACK", "ingest", "int", min=1,
                help_text="Days of history to backfill when re-running a full NVD ingest."),
    ConfigField("KEV_CROSS_FETCH_NVD", "ingest", "bool",
                help_text="When a KEV entry has no matching CVE row yet, fetch it from NVD directly."),
    ConfigField("VULNRICHMENT_BRANCH", "ingest", "str",
                help_text="GitHub branch of the CISA Vulnrichment mirror to sync from."),
    ConfigField("CVELISTV5_BRANCH", "ingest", "str",
                help_text="GitHub branch of the CVEListV5 mirror to sync from."),
    ConfigField("CVELISTV5_INITIAL_SINCE_DAYS", "ingest", "int", min=1,
                help_text="Days of history for the first-ever CVEListV5 sync."),
    ConfigField("CIRCUIT_FAILURE_THRESHOLD", "ingest", "int", min=1, max=20, restart_required=True,
                help_text="Consecutive failures before a feed source's circuit breaker opens."),
    ConfigField("CIRCUIT_COOLDOWN_SECONDS", "ingest", "int", min=1, restart_required=True,
                help_text="Seconds an open circuit breaker waits before allowing a retry."),
    ConfigField("NVD_SYNC_OVERLAP_MINUTES", "ingest", "int", min=0,
                help_text="Minutes of overlap re-fetched each NVD sync, to absorb clock skew."),
    ConfigField("EXPLOIT_SOURCES_SYNC_ENABLED", "ingest", "bool",
                help_text="Enable the PoC-in-GitHub/ExploitDB/Metasploit/Nuclei exploit-availability sync."),
    ConfigField("EXPLOIT_SOURCES_SYNC_INTERVAL_HOURS", "ingest", "int", min=1,
                help_text="How often the exploit-availability sync runs, when enabled.",
                display_label="Exploit sources sync interval", unit="h"),
    ConfigField("EXPLOIT_SOURCES_THROTTLE_SECONDS", "ingest", "int", min=0,
                help_text="Delay between exploit-source requests, to stay polite to upstream APIs."),
    ConfigField("ATLAS_YAML_URL", "ingest", "url",
                help_text="Override URL for the MITRE ATLAS techniques YAML (blank = upstream default)."),
    ConfigField("MITRE_CVE_MAPPINGS_JSON_URL", "ingest", "url",
                help_text="Override URL for the MITRE ATT&CK CVE-mappings JSON (blank = upstream default)."),

    # ── Durable outbound jobs (Procrastinate; Postgres only) ─────────────────
    ConfigField("PROCRASTINATE_ENABLED", "queue", "bool", restart_required=True,
                help_text="Enable Postgres-backed durable job queue (Procrastinate). Off = zero behavior change."),
    ConfigField("API_CALL_EVENTS_ENABLED", "queue", "bool", restart_required=True,
                help_text="Record every outbound HTTP attempt from resilient_request into api_call_events (default on)."),
    ConfigField("CPE_CATALOG_SYNC_ENABLED", "ingest", "bool", restart_required=True,
                help_text="Sync NVD CPE dictionary into software_catalog for stack autocomplete (default off)."),
    ConfigField("CPE_CATALOG_SYNC_INTERVAL_HOURS", "ingest", "int", min=1,
                help_text="How often the CPE catalog sync job runs when enabled.",
                display_label="CPE catalog sync interval", unit="h"),
    ConfigField("CPE_CATALOG_MAX_PAGES", "ingest", "int", min=1,
                help_text="Max NVD CPE API pages per sync run (checkpointed; default 10)."),
    ConfigField("STACK_BACKFILL_ENABLED", "ingest", "bool", restart_required=True,
                help_text="Enable Agree Tier-A historical CVE backfill for shallow stack coverage (default off)."),
    ConfigField("STACK_BACKFILL_MAX_PRODUCTS", "ingest", "int", min=1,
                help_text="Max products per Tier A backfill run."),
    ConfigField("STACK_BACKFILL_MAX_CVES", "ingest", "int", min=100,
                help_text="Max CVEs upserted per Tier A backfill run."),

    # ── ML toggles ───────────────────────────────────────────────────────────
    ConfigField("EMBEDDINGS_ENABLED", "ml", "bool", restart_required=True,
                help_text="Enable local ONNX embeddings for hybrid search and related CVEs."),
    ConfigField("EMBEDDINGS_AUTO_ON_INGEST", "ml", "bool",
                help_text="After NVD ingest, embed new/updated CVEs immediately (capped). Default on.",
                display_label="Embeddings auto on ingest"),
    ConfigField("EMBEDDINGS_INGEST_MAX_PER_RUN", "ml", "int", min=1, max=500,
                help_text="Max CVEs embedded in the NVD ingest tail.",
                display_label="Embeddings ingest max per run"),
    ConfigField("EMBEDDINGS_SYNC_INTERVAL_HOURS", "ml", "int", min=1,
                help_text="How often the embeddings backfill job runs, when enabled.",
                display_label="Embeddings sync interval", unit="h"),
    ConfigField("EMBEDDINGS_MAX_PER_RUN", "ml", "int", min=1,
                help_text="Maximum CVEs embedded per backfill run."),
    ConfigField("EMBEDDINGS_MODEL", "ml", "str",
                help_text="ONNX embeddings model name (e.g. BAAI/bge-small-en-v1.5)."),
    ConfigField("EMBEDDINGS_CACHE_DIR", "ml", "str",
                help_text="Directory the embeddings model is cached in (blank = default)."),
    ConfigField("LLM_PRODUCT_EXTRACTION_ENABLED", "ml", "bool", restart_required=True,
                help_text="Enable Groq-powered affected-product extraction for NVD-unanalyzed CVEs."),
    ConfigField("LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS", "ml", "int", min=1,
                help_text="How often the LLM product-extraction job runs, when enabled.",
                display_label="LLM product extraction interval", unit="h"),
    ConfigField("LLM_PRODUCT_EXTRACTION_MAX_PER_RUN", "ml", "int", min=1,
                help_text="Maximum CVEs processed per LLM product-extraction run."),
    ConfigField("CORRELATION_PRECOMPUTE_ENABLED", "ml", "bool",
                help_text="Enable nightly correlation snapshots so CVE risk reads prefer cheap precomputed rows.",
                display_label="Correlation precompute"),
    ConfigField("DETECTION_CONTEXT_SYNC_ENABLED", "ml", "bool",
                help_text="Enable deterministic detection-context cache refresh from CVE and exploit metadata.",
                display_label="Detection context sync"),
    ConfigField("DETECTION_CONTEXT_LLM_ENABLED", "ml", "bool", restart_required=True,
                help_text="Enable optional LLM extraction of detection artifacts into detection context.",
                display_label="Detection context LLM"),
    ConfigField("DETECTION_CONTEXT_NUCLEI_ENABLED", "ml", "bool",
                help_text="Enable deterministic Nuclei YAML artifact enrichment during exploit sync.",
                display_label="Detection context Nuclei"),

    # ── Backup ───────────────────────────────────────────────────────────────
    ConfigField("BACKUP_ENABLED", "backup", "bool",
                help_text="Enable the scheduled SQLite backup job."),
    ConfigField("BACKUP_RETENTION_COUNT", "backup", "int", min=1,
                help_text="Number of backup archives to keep before pruning the oldest."),
    ConfigField("BACKUP_INTERVAL_HOURS", "backup", "int", min=1,
                help_text="How often the scheduled backup runs.",
                display_label="Backup interval", unit="h"),
    ConfigField("BACKUP_DIR", "backup", "str",
                help_text="Directory backup archives are written to."),
    ConfigField("BACKUP_AGE_KEY_FILE", "backup", "str",
                help_text="Path to the age encryption key file used to encrypt backup archives."),

    # ── Application behaviour ───────────────────────────────────────────────
    ConfigField("BRIEFR_STACK_TERMS", "app", "str",
                help_text="Comma-separated product/vendor terms used to match KEV entries against your stack."),
    ConfigField("LOG_FORMAT", "app", "enum", enum_values=("json", "plain"), restart_required=True,
                help_text="Structured JSON logs (journald-friendly) or plain text."),
    ConfigField("RATE_LIMIT_ENABLED", "app", "bool", restart_required=True,
                help_text="Enable per-IP token-bucket rate limiting on IOC lookup, refresh, admin, wallboard, and auth routes."),
    ConfigField("RATE_LIMIT_IOC_PER_MINUTE", "app", "int", min=1, restart_required=True,
                help_text="Max IOC lookups per minute per client IP, when rate limiting is enabled."),
    ConfigField("RATE_LIMIT_REFRESH_PER_MINUTE", "app", "int", min=1, restart_required=True,
                help_text="Max manual refresh/ingest and admin POST requests per minute per client IP."),
    ConfigField("RATE_LIMIT_ADMIN_READ_PER_MINUTE", "app", "int", min=1, restart_required=True,
                help_text="Max read-only admin GET requests per minute per client IP."),
    ConfigField("RATE_LIMIT_LOGIN_PER_MINUTE", "app", "int", min=1, restart_required=True,
                help_text="Max login/setup attempts per minute per client IP and per username."),
    ConfigField("RATE_LIMIT_AUTH_REFRESH_PER_MINUTE", "app", "int", min=1, restart_required=True,
                help_text="Max session refresh requests per minute per client IP."),
    ConfigField("RATE_LIMIT_WALLBOARD_PER_MINUTE", "app", "int", min=1, restart_required=True,
                help_text="Max wallboard snapshot requests per minute per client IP (kiosk polling)."),
    ConfigField("RATE_LIMIT_SEARCH_TOKEN_PER_MINUTE", "app", "int", min=1, restart_required=True,
                help_text="Max Bearer search-token API requests per minute per client IP (Embeddings E5)."),
    ConfigField("ALLOWED_ORIGINS", "app", "str",
                help_text="Comma-separated CORS origins allowed to call the API.",
                restart_required=True,
                display_label="Allowed CORS origins"),
    ConfigField("DEFAULT_TIMEZONE", "app", "str",
                help_text="IANA timezone used for displaying dates/times when no client timezone is known."),
    ConfigField("BRIEFR_ENV", "app", "enum", enum_values=("development", "production"),
                help_text="production disables /api/docs, /api/redoc, and /api/openapi.json."),
    ConfigField("DATABASE_URL", "app", "secret", restart_required=True,
                help_text="postgresql://user:pass@host:5432/db — blank uses the default SQLite file."),
    ConfigField("DATABASE_POOL_SIZE", "app", "int", min=1, max=100, restart_required=True,
                help_text="asyncpg connection pool size, when DATABASE_URL points at PostgreSQL."),
    ConfigField("DATABASE_POOL_ACQUIRE_TIMEOUT_SECONDS", "app", "int", min=1, max=120,
                restart_required=True,
                help_text="Seconds to wait for a free pool connection before HTTP 503."),
    ConfigField("DATABASE_POOL_COMMAND_TIMEOUT_SECONDS", "app", "int", min=1, max=600,
                restart_required=True,
                help_text=(
                    "asyncpg per-SQL-statement timeout (seconds) for pooled connections. "
                    "Applies to database work only — not feed/API HTTP. Source timeouts "
                    "live per feed (CIRCL, Sploitus, ThreatFox, …). Do not raise this to "
                    "paper over slow APIs; commit/close before outbound source I/O instead."
                ),
    ),
    # ── Webhooks — Discord / Telegram / generic ─────────────────────────────
    ConfigField("DISCORD_WEBHOOK_URL", "webhooks", "secret",
                help_text="Discord channel webhook URL for KEV/backup/health alerts."),
    ConfigField("DISCORD_WEBHOOK_ENABLED", "webhooks", "bool",
                help_text="Enable Discord alert delivery."),
    ConfigField("DISCORD_WEBHOOK_EVENTS", "webhooks", "str",
                help_text="Comma-separated event types to send to Discord (blank = all)."),
    ConfigField("TELEGRAM_BOT_TOKEN", "webhooks", "secret",
                help_text="Telegram bot token, from @BotFather."),
    ConfigField("TELEGRAM_CHAT_ID", "webhooks", "str",
                help_text="Telegram chat/channel ID the bot posts alerts to."),
    ConfigField("TELEGRAM_WEBHOOK_ENABLED", "webhooks", "bool",
                help_text="Enable Telegram alert delivery."),
    ConfigField("TELEGRAM_WEBHOOK_EVENTS", "webhooks", "str",
                help_text="Comma-separated event types to send to Telegram (blank = all)."),
    ConfigField("WEBHOOK_GENERIC_URL", "webhooks", "secret",
                help_text="Generic HTTPS webhook endpoint (e.g. Slack incoming webhook, custom receiver)."),
    ConfigField("WEBHOOK_GENERIC_ENABLED", "webhooks", "bool",
                help_text="Enable generic webhook delivery."),
    ConfigField("WEBHOOK_GENERIC_LABEL", "webhooks", "str",
                help_text="Display label for the generic webhook destination in the admin panel."),
    ConfigField("WEBHOOK_GENERIC_EVENTS", "webhooks", "str",
                help_text="Comma-separated event types to send to the generic webhook (blank = all)."),

    # ── Security / kiosk ────────────────────────────────────────────────────
    ConfigField("WALLBOARD_TOKEN", "security", "secret", restart_required=True,
                display_label="Wallboard kiosk token",
                help_text="Optional read-only gate for GET /api/wallboard and /wallboard. "
                "Clients send X-BRIEFR-Wallboard-Token once to obtain a session cookie. "
                "Leave blank to keep the wallboard open (production warns when unset)."),

    # ── API Keys ─────────────────────────────────────────────────────────────
    ConfigField("NVD_API_KEY", "api_keys", "secret",
                help_text="Raises the NVD API rate limit from 5 to 50 requests per 30s."),
    ConfigField("VIRUSTOTAL_API_KEY", "api_keys", "secret",
                help_text="Used for IOC lookup (hash/IP/domain reputation)."),
    ConfigField("ABUSEIPDB_API_KEY", "api_keys", "secret",
                help_text="Used for IP abuse-score IOC lookups."),
    ConfigField("GREYNOISE_API_KEY", "api_keys", "secret",
                help_text="Used for IP classification + CVE scan context (free tier: 50/week)."),
    ConfigField("GITHUB_TOKEN", "api_keys", "secret",
                help_text="Raises the GitHub API limit from 60/hr to 5000/hr for rule search and feed syncs."),
    ConfigField("GROQ_API_KEY", "api_keys", "secret",
                help_text="Primary LLM provider for scheduler tasks (Groq first in failover chain)."),
    ConfigField("GEMINI_API_KEY", "api_keys", "secret",
                help_text="Gemini Flash-Lite last-resort failover for scheduler-side LLM tasks."),
    ConfigField("CEREBRAS_API_KEY", "api_keys", "secret",
                help_text="Cerebras failover for scheduler-side LLM tasks."),
    ConfigField("OPENROUTER_API_KEY", "api_keys", "secret",
                help_text="OpenRouter :free tier last-resort failover for LLM tasks."),
    ConfigField("ANTHROPIC_API_KEY", "api_keys", "secret",
                help_text="Deprecated — no longer used by the LLM router."),
    ConfigField("OTX_API_KEY", "api_keys", "secret",
                help_text="Used for AlienVault OTX campaign pulses and nightly IOC correlation."),
    ConfigField("CIRCL_API_KEY", "api_keys", "secret",
                help_text="Optional — used for extended CVE references and CAPEC mapping."),
    ConfigField("ABUSECH_AUTH_KEY", "api_keys", "secret",
                help_text="Used for MalwareBazaar, URLhaus, and ThreatFox IOC mirror sync."),
    ConfigField("VULNCHECK_API_KEY", "api_keys", "secret",
                help_text="Optional — VulnCheck community KEV catalog for exploited-not-yet-CISA tier."),
)

_BY_KEY: dict[str, ConfigField] = {f.key: f for f in CONFIG_SCHEMA}

WRITABLE_CONFIG_KEYS: frozenset[str] = frozenset(_BY_KEY)
INTEGER_KEYS: frozenset[str] = frozenset(f.key for f in CONFIG_SCHEMA if f.type == "int")
RESTART_REQUIRED_KEYS: frozenset[str] = frozenset(f.key for f in CONFIG_SCHEMA if f.restart_required)
SCHEDULER_RESCHEDULE_KEYS: frozenset[str] = _SCHEDULER_RESCHEDULE_KEYS


def resolved_apply_strategy(field: ConfigField) -> str:
    """Return the effective apply strategy for a schema field."""
    if field.apply_strategy:
        return field.apply_strategy
    if field.restart_required:
        return APPLY_RESTART
    if field.key in _SCHEDULER_RESCHEDULE_KEYS:
        return APPLY_SCHEDULER_RESCHEDULE
    return APPLY_IMMEDIATE


def resolved_display_label(field: ConfigField) -> str:
    if field.display_label:
        return field.display_label
    return field.key.replace("_", " ").title()


def get_field(key: str) -> ConfigField | None:
    return _BY_KEY.get(key)


def validate_value(key: str, value: str) -> str | None:
    """Return an error message if value violates the field's type/bounds, else None.

    Existing callers only checked "is this parseable as an int" — this adds
    min/max/enum checks on top without changing what counts as a valid type.
    """
    field_def = _BY_KEY.get(key)
    if field_def is None:
        return None

    if "…" in value or "***" in value or value == "not configured":
        return f"Cannot write masked or placeholder value for key '{key}'"

    if field_def.type == "int":
        try:
            parsed = int(value)
        except (ValueError, TypeError):
            return f"Key '{key}' requires an integer value"
        if field_def.min is not None and parsed < field_def.min:
            return f"Key '{key}' must be >= {field_def.min}"
        if field_def.max is not None and parsed > field_def.max:
            return f"Key '{key}' must be <= {field_def.max}"
    elif field_def.type == "bool":
        if value.lower() not in ("0", "1", "true", "false"):
            return f"Key '{key}' must be a boolean value ('1', '0', 'true', or 'false')"
    elif field_def.type == "enum" and field_def.enum_values:
        if value not in field_def.enum_values:
            return f"Key '{key}' must be one of: {', '.join(field_def.enum_values)}"
    return None


def list_schema() -> list[dict]:
    return [
        {
            "key": f.key,
            "section": f.section,
            "type": f.type,
            "min": f.min,
            "max": f.max,
            "enum_values": list(f.enum_values),
            "help_text": f.help_text,
            "restart_required": f.restart_required,
            "apply_strategy": resolved_apply_strategy(f),
            "display_label": resolved_display_label(f),
            "unit": f.unit,
        }
        for f in CONFIG_SCHEMA
    ]
