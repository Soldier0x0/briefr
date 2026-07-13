# BRIEFR intel snapshot specification

**Status:** Active (Wave 3 PR 8)  
**Purpose:** Define which PostgreSQL tables and `sync_state` keys belong in a
**public intel bundle** vs operator-only production data. The export script
(`scripts/export_intel_snapshot.py`, Wave 3 PR 9) and CI restore smoke (Track J2)
implement this spec.

**Related:** `docs/planning/PROGRAM_PRODUCT_OPEN_CORE.md` § INTEL vs OPERATOR,
`docs/decisions/ADR-001-intel-app-schema-split.md`.

---

## Bundle format (v1)

| Field | Value |
|-------|--------|
| Container | `briefr-intel-YYYY-MM.pgdump.gz` (gzip of custom-format `pg_dump`) |
| Sidecar | `briefr-intel-YYYY-MM.manifest.json` (or `*.pgdump.manifest.json` next to export) |
| `format_version` | **1** — increment when table allowlist or manifest schema changes |
| `bundle_kind` | `briefr-intel` |
| Dump scope | Allowlisted tables + filtered `sync_state` rows only |
| Operator rows | **Zero** — verified by export script exit code + row-count guards |
| Restore target | Empty Postgres 16+ database; `pg_restore --no-owner --no-acl` |
| Schema | `schema_revision` + `alembic_head_at_export` in manifest; run `alembic upgrade head` after restore when importing into a newer BRIEFR release |

Manifest fields (v1):

| Key | Purpose |
|-----|---------|
| `format_version` | Bundle format semver (integer) |
| `bundle_kind` | Always `briefr-intel` |
| `schema_revision` | `alembic_version.version_num` at export time (may be absent on empty DB) |
| `alembic_head_at_export` | Alembic head revision baked into the exporting BRIEFR release |
| `briefr_commit` | Optional git commit from `backend/.build-info.json` |
| `exported_at` | UTC ISO timestamp |
| `tables` / `row_counts` / `sync_state_keys` | Allowlist verification |

Verify before import: `python scripts/verify_intel_snapshot.py briefr-intel-YYYY-MM.pgdump.gz`

Import (greenfield / intel seed): `python scripts/import_intel_snapshot.py --input … --database-url …`

Full operator steps: `docs/OPERATIONS.md` § Intel snapshot import and upgrade.

Future v2 may add portable JSONL per-table exports; v1 is Postgres-native for
adoption speed and fidelity with BRIEFR compute columns (`cve_embeddings`, etc.).

---

## INTEL tables (include)

Derived public intelligence and BRIEFR-computed enrichment. Safe to publish in
the monthly open-core snapshot.

| Table | Role |
|-------|------|
| `cves` | Core CVE feed |
| `kev_deadlines` | CISA KEV remediation deadlines |
| `epss_history` | EPSS score history |
| `cve_change_history` | Tracked field deltas (CVSS, EPSS, KEV, PoC) |
| `mitre_techniques` | ATT&CK technique mirror |
| `cve_technique_map` | CVE ↔ technique links |
| `atlas_techniques` | ATLAS technique mirror |
| `atlas_case_studies` | ATLAS case study mirror |
| `cve_atlas_map` | CVE ↔ ATLAS links |
| `cve_exploits` | Exploit / PoC references |
| `feed_cache` | Scheduler-side cache (detection context, wallboard snapshot, etc.) |
| `otx_cve_pulses` | OTX pulse ↔ CVE mirror |
| `otx_pulse_iocs` | OTX IOC rows (public pulse data) |
| `otx_pulses` | OTX pulse metadata |
| `correlation_actor` | Actor-sector correlation |
| `correlation_temporal` | Vendor temporal anomalies |
| `correlation_campaigns` | Campaign objects |
| `correlation_campaign_members` | Campaign membership |
| `cve_embeddings` | ML embedding vectors |
| `mitre_groups` | ATT&CK group mirror |
| `group_technique_map` | Group ↔ technique links |

### `sync_state` keys (include subset)

Export **only** ingest watermarks and upstream version markers:

| Key pattern | Purpose |
|-------------|---------|
| `nvd_last_mod_end` | NVD incremental watermark |
| `epss_backfill_done` | EPSS backfill completion flag |
| `atlas_upstream_version` | ATLAS upstream version |
| `cvelistv5_head_sha` | CVEList v5 git head |
| `poc_github_commit` | PoC GitHub mirror commit |
| `correlation_build_watermark` | Correlation build cursor |
| `correlation_last_run` | Correlation last-run timestamp |

**Exclude** all other `sync_state` rows (scheduler pause flags, last-run
telemetry, backup dead-man baselines, operator stack overrides, etc.).

---

## OPERATOR tables (never include)

Instance-specific, authentication, IOC lookups, webhooks, or analyst workflow
data. A production `pg_dump` must **never** be published as an intel bundle.

| Table | Why excluded |
|-------|----------------|
| `users` | Credentials |
| `sessions` | Refresh tokens |
| `user_preferences` | Per-user stack, display prefs, optional My Stack inventory |
| `watchlist` | Analyst pins |
| `audit_log` | Admin actions |
| `ioc_cache` | IOC lookup results (may contain queried indicators) |
| `api_usage` | Rate-limit / usage counters |
| `webhook_destinations` | Webhook URLs and secrets in `config_json` |
| `webhook_delivery_log` | Delivery attempts |
| `webhook_alert_log` | Alert dedupe state |
| `correlation_suppressions` | Operator suppressions |
| `hunt_packs` | Operator-authored hunt content |
| `alembic_version` | Instance migration pointer (re-derived on restore) |

### `sync_state` keys (exclude)

| Key pattern | Why excluded |
|-------------|----------------|
| `scheduler.paused.%` | Job pause flags |
| `scheduler.last_run.%` | Operational telemetry |
| `backup_deadman_baseline_utc` | Backup watchdog |
| Any key not in the INTEL allowlist above | Default deny |

---

## Export verification (PR 9 / Track J2)

The export script must:

1. Dump only INTEL tables via `pg_dump --table=…` (and filtered `sync_state`).
2. Refuse to run if `DATABASE_URL` points at a database containing operator
   tables with **any rows** in `users`, `sessions`, or `user_preferences`
   (configurable `--allow-operator-seed` for dev fixtures only).
3. Emit a manifest JSON alongside the archive: table list, row counts, export
   timestamp, schema revision.
4. Exit non-zero if a forbidden table name appears in the dump catalog.

Restore smoke (CI):

1. Create empty Postgres 16 database.
2. `pg_restore` the published fixture.
3. Assert row counts for core tables (`cves`, `mitre_techniques`) match manifest.
4. Assert zero rows in `users`, `sessions`, `user_preferences`.

---

## Restore operator runbook (summary)

Full steps: `docs/OPERATIONS.md` § Intel snapshot import and upgrade.

Minimum path:

```bash
python3 scripts/verify_intel_snapshot.py briefr-intel-YYYY-MM.pgdump.gz
python3 scripts/import_intel_snapshot.py --input briefr-intel-YYYY-MM.pgdump.gz --database-url "$DATABASE_URL"
```

Do not overwrite a production operator database with an intel bundle.

---

## Schema split ADR

Long-term `intel` vs `app` Postgres schemas are **design-only** in Wave 3.
Runtime remains a single database with allowlist export until Post-B schema
split lands. See `docs/decisions/ADR-001-intel-app-schema-split.md`.
