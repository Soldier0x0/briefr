# PHASE 8 — Logging · Monitoring · Observability · Alerting · Operational Readiness · Configuration · Backup & Restore · Disaster Recovery · Deployment · Upgrade & Migration

*Reviewed at commit `61c686f`. `structured_logging.py`, `monitoring/`, `backup/`, `deploy/`,
`alembic/`, `routers/health.py`, `webhooks/alerts.py`, `docs/OPERATIONS.md`.*

---

## Executive Summary

Operational maturity for **self-hosted, single-node** deployment is a clear strength. Logging is
**JSON-structured** (one object per line, journald-friendly) with `request_id`/`job_id`/`run_id`
contextvars, an in-process ring buffer feeding an admin log viewer, secret redaction of
`*_KEY/_TOKEN/_SECRET/_PASSWORD` extra fields, and a `LOG_FORMAT=plain` dev mode. The `deploy/`
directory is genuinely production-grade for bare-metal: systemd units + timers for the backend and
**two** backup paths (SQLite + Postgres), a deadman-check, nginx configs (HTTP + HTTPS + reusable
security-header/gzip snippets), logrotate, a `briefr-doctor.sh` diagnostic, and `briefr-update.sh`/
`briefr-restore.sh`. Health has a **liveness/readiness split** (`/api/health/live` vs `/api/health`).
`OPERATIONS.md` contains real runbooks — a full production restore runbook (J5) with a pre-restore
safety backup, migration application, and an intel-snapshot upgrade runbook — and backup round-trip
is **CI-tested** on Postgres. Migrations are forward-only Alembic. Alerting exists via
`webhooks/alerts.py`, `monitoring/notifications.py`, `api_key_health`, and the backup deadman job.

The gaps are **cloud-native and standard-observability** shaped: (1) **no standard metrics
exposition** — there's an internal `request_counter` and admin resource sampling, but no
Prometheus/OpenMetrics `/metrics` endpoint, so no Grafana/Datadog/Alertmanager integration; (2) **no
distributed tracing** (no OpenTelemetry); (3) **no application container image** — deployment is
systemd/bare-metal only (only a Postgres `docker-compose` exists), so Docker/Kubernetes deployment
isn't first-class; (4) the DR runbooks are strong but state **no explicit RPO/RTO** and there's no
scheduled **restore-drill** proving backups actually restore; (5) the **CI baseline-red** (Phase 4
F4.1) directly undermines deployment confidence — `briefr-update.sh` upgrades toward a pipeline
whose green state isn't trustworthy.

**Overall Score: 7.5 / 10.**

---

## Findings

### F8.1 — No standard metrics exposition (no Prometheus/OpenMetrics endpoint) · Priority: HIGH · Architectural
- **Location:** `backend/metrics/request_counter.py` (in-process increment/read-reset only),
  `resource_collector.py`/`storage_metrics.py`/`db/resource_metrics.py` (sampled into DB for the
  admin UI); no `/metrics` route, no `prometheus_client` dependency.
- **Description:** Metrics exist but are trapped inside the app (admin UI + DB). There's no
  scrape-able endpoint in a standard format, so operators can't wire BRIEFR into their existing
  Prometheus/Grafana/Datadog/Alertmanager stack — the baseline expectation for enterprise SRE.
- **Why it matters:** "Deployed to thousands of organizations" almost always means integrating with
  the org's monitoring, not adopting a bespoke admin page. Without `/metrics`, BRIEFR is a
  monitoring island; SLOs, dashboards, and paging all have to be rebuilt by hand.
- **Evidence:** no `/metrics` route; `request_counter` is a bare int; metrics land in the DB for the
  admin viewer only.
- **Recommended solution:** Add `prometheus_client`, expose `GET /metrics` (gated/allowlisted or on
  a separate port), and emit: request rate/latency histograms per route, DB pool utilization
  (already available via `get_pool_stats`), cache hit-rate (Phase 3 F3.9), scheduler job
  success/duration, LLM provider attempts/failures/quota, backup age. Document Grafana dashboards.
- **Acceptance criteria:** `/metrics` returns OpenMetrics with the above series; a sample Grafana
  dashboard + Alertmanager rules are documented.
- **Effort:** Medium. **Type:** Architectural.

### F8.2 — No application container image (systemd/bare-metal only) · Priority: MEDIUM · Architectural
- **Location:** `deploy/` has systemd units + nginx + `docker-compose.postgres.yml` (Postgres only);
  no `Dockerfile` / app image / Helm chart / k8s manifests anywhere in the repo.
- **Description:** The only supported deployment is bare-metal systemd. This is well-executed, but
  it excludes the large population of orgs that deploy exclusively via containers/Kubernetes and
  can't run bespoke systemd units.
- **Why it matters:** Container/k8s is the default enterprise deployment substrate; its absence
  narrows the addressable install base and complicates reproducible, immutable deployments and
  horizontal scaling (which is separately blocked by Phase 3/6 F3.1/F3.2/F6.6).
- **Evidence:** no Dockerfile; compose file provisions Postgres, not the app.
- **Recommended solution:** Add a multi-stage `Dockerfile` (frontend build → backend runtime), a
  full `docker-compose.yml` (app + Postgres), and a minimal Helm chart / k8s manifest set with
  liveness/readiness probes wired to `/api/health/live` and `/api/health`, config via env/secrets,
  and the scheduler-ownership guidance from F3.2. Keep systemd as the bare-metal option.
- **Acceptance criteria:** `docker compose up` brings up a working app+DB; a documented k8s path with
  probes and single-scheduler-owner topology.
- **Effort:** Medium. **Type:** Architectural.

### F8.3 — DR runbooks lack explicit RPO/RTO and there is no automated restore drill · Priority: HIGH · Architectural
- **Location:** `docs/OPERATIONS.md` (backup policy §75; production restore runbook J5 §254; intel
  snapshot upgrade §394); `deploy/briefr-backup.*`, `briefr-pg-backup.*`, `briefr-restore.sh`;
  `backup_deadman_check` scheduler job; CI `test_backup_roundtrip_postgres.py`.
- **Description:** Backup/restore mechanics are excellent and even CI-round-trip-tested, but the DR
  *objectives* are unstated: no documented RPO (how much data loss is acceptable — tied to backup
  frequency) or RTO (how fast must service return). There's no scheduled **restore drill** that
  periodically proves a real production backup restores into a clean environment.
- **Why it matters:** "We have backups" is not DR readiness; untested backups fail exactly when
  needed. Enterprise/compliance audits (SOC 2, ISO 27001) require stated RPO/RTO and evidence of restore
  testing.
- **Evidence:** OPERATIONS.md sections cover mechanics/runbooks, not RPO/RTO; deadman alerts on
  *missing* backups but nothing verifies *restorability* of real backups on a schedule.
- **Recommended solution:** Document RPO/RTO targets tied to the backup timer cadence; add a
  scheduled (e.g. weekly) automated restore drill that restores the latest backup into a scratch DB
  and asserts row counts/integrity, alerting on failure. Extend the CI round-trip to include a
  `.env`-in-archive restore path.
- **Acceptance criteria:** Stated RPO/RTO in OPERATIONS.md; a passing scheduled restore drill with
  alerting; documented last-drill timestamp.
- **Effort:** Medium. **Type:** Architectural.

### F8.4 — No distributed tracing / correlation across the request→job boundary · Priority: MEDIUM · Architectural
- **Location:** `structured_logging.py` (`request_id`/`job_id`/`run_id` contextvars — good
  correlation IDs) but no OpenTelemetry/trace propagation; async scheduler jobs and LLM/webhook
  egress aren't traced.
- **Description:** Correlation IDs are a strong foundation, but there's no span-based tracing to see
  end-to-end latency across API → DB → scheduler job → external API. Debugging a slow request or a
  failing nightly pipeline means grepping logs by id, not viewing a trace.
- **Why it matters:** As the system scales and the engine pipeline deepens, log-grep debugging
  doesn't scale; tracing is the standard tool for latency and failure attribution across boundaries.
- **Recommended solution:** Add OpenTelemetry (FastAPI + asyncpg + httpx instrumentation), propagate
  trace context into scheduler jobs (reuse `run_id` as a span attribute), export OTLP. Keep it
  optional/off by default for minimal self-host.
- **Acceptance criteria:** A request that triggers DB + external calls produces a single trace;
  scheduler jobs emit spans linked by `run_id`.
- **Effort:** Medium. **Type:** Architectural.

### F8.5 — Deployment confidence undermined by CI baseline-red (carries F4.1) · Priority: HIGH · Architectural
- **Location:** `deploy/briefr-update.sh` (in-place upgrade on a live prod box, per CLAUDE.md danger
  zone 5), CI jobs `test`/`test-postgres` red on every push (Phase 4 F4.1).
- **Description:** The upgrade path is additive-by-design and scripted, but it advances toward
  commits whose test suite is red by default. An operator running `briefr-update.sh` can't rely on
  "CI was green for this release" as a safety signal because green isn't the norm.
- **Why it matters:** Safe upgrades of a live production box require a trustworthy green pipeline as
  the gate; a red baseline turns every upgrade into a leap of faith.
- **Recommended solution:** Fix F4.1 (green `test`/`test-postgres`, branch protection); have
  `briefr-update.sh` / release tagging require a green CI run for the target commit; add a
  post-upgrade smoke (the `check-backend.sh`/`smoke-intel.sh` scripts already exist — wire them into
  the update flow with automatic rollback on failure).
- **Acceptance criteria:** Releases are cut only from green commits; `briefr-update.sh` runs a
  post-upgrade smoke and rolls back on failure.
- **Effort:** Medium. **Type:** Architectural.

### F8.6 — Configuration sprawl without a single generated reference · Priority: MEDIUM · Quick Win
- **Location:** `config_schema.py`, `settings.py`, `operator_settings.py`, `db/config.py`,
  `routers/config.py` (Phase 1 F1.9); many env vars (`BRIEFR_*`, `RATE_LIMIT_ENABLED`,
  `AUTH_COOKIE_SECURE`, `BRIEFR_REQUIRE_POSTGRES`, `BRIEFR_SCHEDULER_ENABLED`,
  `BRIEFR_RATE_LIMIT_STORE`, `BRIEFR_SETTINGS_KEY`, `LOG_FORMAT`, …).
- **Description:** Configuration is spread across five modules and many env vars. `config_schema.py`
  is a good foundation, but there's no single generated, authoritative config reference (name,
  type, default, secret?, production-impact) — operators must read code/docs fragments.
- **Why it matters:** Misconfiguration is a top cause of production incidents; a self-hosted product
  needs one canonical, exhaustive config reference and validation.
- **Recommended solution:** Generate a config reference from `config_schema.py`/`settings.py`
  (name, default, description, secret flag, posture impact) into `docs/`; validate unknown/typo'd
  env vars at startup (warn); surface the `production_posture_warnings` report prominently. Ties to
  F1.9.
- **Acceptance criteria:** One generated config reference kept in sync via CI; startup warns on
  unknown `BRIEFR_*` vars.
- **Effort:** Quick Win. **Type:** Quick Win.

### F8.7 — Alerting exists but lacks routing/severity/dedup policy and self-monitoring of the alerter · Priority: MEDIUM · Architectural
- **Location:** `webhooks/alerts.py` (524 LOC), `monitoring/notifications.py`,
  `monitoring/api_key_health.py`, `backup_deadman_check`/`watchlist_monitor_alerts` jobs.
- **Description:** There's real alerting (webhook delivery, deadman, API-key health, watchlist). What
  isn't evident is an alert *policy*: severity levels, routing to different destinations by severity,
  dedup/rate-limiting of alert storms, and self-monitoring (who alerts if the alerter/webhook
  delivery itself fails? the SSRF-protected client has retries, but delivery failure escalation is
  unclear).
- **Why it matters:** Alert fatigue and silent alerter failure are the two classic ways alerting
  fails in production; both need explicit handling.
- **Recommended solution:** Define severity tiers and per-severity routing; add alert dedup/
  cooldown; add a heartbeat/self-check so a failed alert channel is itself detectable (e.g. a
  synthetic daily test alert). Document the alerting model in OPERATIONS.md.
- **Acceptance criteria:** Alerts carry severity + route accordingly; repeated identical alerts are
  deduped; a failed alert channel raises a secondary signal.
- **Effort:** Medium. **Type:** Architectural.

---

## Overall Score: **7.5 / 10**

| Sub-audit | Score |
|---|---|
| Logging | 8.5 / 10 |
| Monitoring | 6.5 / 10 |
| Observability | 6.5 / 10 |
| Alerting | 7 / 10 |
| Operational Readiness | 8 / 10 |
| Configuration | 7 / 10 |
| Backup & Restore | 8.5 / 10 |
| Disaster Recovery | 7 / 10 |
| Deployment | 7 / 10 |
| Upgrade & Migration | 7.5 / 10 |

## Strengths
- JSON structured logging with request/job/run correlation IDs, ring-buffer admin viewer, and secret
  redaction; `LOG_FORMAT=plain` dev mode.
- Production-grade bare-metal `deploy/`: systemd services+timers, dual backup paths, deadman check,
  nginx (HTTP/HTTPS + security-header/gzip snippets), logrotate, doctor + update + restore scripts.
- Liveness/readiness health split; forward-only Alembic migrations; **CI-tested** backup round-trip;
  detailed restore + intel-snapshot upgrade runbooks.
- Resource metrics already sampled; self-auditing production posture report.

## Weaknesses
- No Prometheus/OpenMetrics endpoint (F8.1); no tracing (F8.4); no app container image (F8.2).
- DR lacks RPO/RTO + restore drills (F8.3); config reference not generated (F8.6); alert policy/
  self-monitoring gaps (F8.7); deployment confidence undercut by red CI (F8.5).

## Immediate Action Items
1. Add a `/metrics` OpenMetrics endpoint with the core series (F8.1).
2. Document RPO/RTO and add a scheduled restore drill (F8.3).
3. Generate a single config reference + startup validation of unknown vars (F8.6).

## Long-Term Recommendations
1. Ship an app container image + compose + minimal Helm/k8s with health probes (F8.2).
2. Add OpenTelemetry tracing across the request→job→egress boundary (F8.4).
3. Gate releases/upgrades on green CI + post-upgrade smoke with rollback (F8.5, depends on F4.1).
4. Formalize alert severity/routing/dedup + alerter self-monitoring (F8.7).

## Production-Readiness Assessment (Phase 8 areas)
**Ready for self-hosted single-node; gaps for enterprise/cloud-native — 7.5/10.** Logging, backup,
and bare-metal deployment tooling are excellent and exceed the bar for a self-hosted security tool.
The blockers for *enterprise* operations are integration-shaped: a standard `/metrics` endpoint
(F8.1) and stated, drilled DR objectives (F8.3) are typically hard requirements in procurement/
compliance, and a container image (F8.2) unlocks the k8s install base. Fix the DR objectives and
metrics endpoint before enterprise sign-off; the CI-baseline dependency (F8.5) makes F4.1 a shared
prerequisite for safe upgrades.
