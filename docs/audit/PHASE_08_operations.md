# PHASE 8 — Logging · Monitoring · Observability · Alerting · Operational Readiness · Configuration · Backup & Restore · Disaster Recovery · Deployment · Upgrade & Migration

*Refreshed at pinned commit `ff23c18a4925b3b7082a2b1d1600884324d90d02`. Scope: logging, metrics, tracing, alerting, backup/restore, deploy/update scripts, configuration, and operations docs.*

---

## Executive Summary

BRIEFR remains operationally strong for **single-node, self-hosted, systemd** deployment. JSON logs carry `request_id` plus scheduler `job_id`/`run_id`; the admin log viewer reads an in-process ring buffer; backups include Postgres dump and `.env`; the restore runbook has a pre-restore safety backup and migration guidance; and `briefr-update.sh` now has a health gate, rollback on failed health/Alembic, and strict Intel smoke by default.

The major gaps remain standard observability and cloud-native packaging: no Prometheus/OpenMetrics endpoint, no OpenTelemetry tracing, no first-class application container/Helm path, and no stated RPO/RTO plus scheduled restore drill. Configuration and alerting are better than before, but still lack a generated operator reference and complete severity/routing/self-monitoring policy.

**Overall Score: 7.8 / 10.**

---

## Finding Status

| ID | Status | Current disposition |
|---|---|---|
| F8.1 | OPEN | Internal/admin metrics exist, but no Prometheus/OpenMetrics `/metrics` route was found. |
| F8.2 | OPEN | Postgres compose exists; no application `Dockerfile`, full app compose, Helm, or k8s manifests found. |
| F8.3 | UPDATED | Backup/restore runbooks are stronger, but explicit RPO/RTO and scheduled restore drill remain absent. |
| F8.4 | OPEN | Correlation IDs exist; OpenTelemetry/span tracing still absent. |
| F8.5 | UPDATED | Update script now has health gate, rollback, and strict smoke; release gating on green CI remains unproven. |
| F8.6 | UPDATED | Config schema/apply strategy are rich, but no generated exhaustive config reference or unknown-env warning gate was found. |
| F8.7 | UPDATED | Webhook destinations, per-event dedupe, delivery health, and some in-app severities exist; routing policy and alerter heartbeat remain incomplete. |

---

## Open / Updated Findings

### F8.1 — No standard metrics exposition · Status: OPEN · Priority: HIGH · Architectural
- **Location:** `backend/metrics/request_counter.py`, admin resource/storage metrics, router inventory.
- **Current evidence:** The repo has an internal request counter and admin/resource samples, but no `/metrics` route or `prometheus_client` dependency was found at the pinned tree.
- **Risk:** Operators cannot scrape BRIEFR into Prometheus/Grafana/Datadog/Alertmanager without bespoke adapters.
- **Recommended solution:** Add an authenticated/allowlisted OpenMetrics endpoint and export request latency/rate, DB pool, scheduler job, LLM provider, webhook, backup-age, and cache metrics.
- **Acceptance criteria:** `GET /metrics` returns standard metrics; docs include example scrape config and alert rules.

### F8.2 — No first-class application container or Kubernetes path · Status: OPEN · Priority: MEDIUM · Architectural
- **Location:** repo root/deploy inventory; `deploy/docker-compose.postgres.yml`.
- **Current evidence:** The pinned tree contains Postgres compose support, but no app `Dockerfile`, full `docker-compose.yml`, Helm chart, or k8s manifests.
- **Risk:** Container-first orgs cannot deploy BRIEFR through their standard platform, and immutable release verification is harder.
- **Recommended solution:** Add a multi-stage app image, full compose stack, and minimal k8s/Helm reference using `/api/health/live` and `/api/health`, with explicit single-scheduler-owner guidance.
- **Acceptance criteria:** `docker compose up` starts app + Postgres; k8s docs cover probes, secrets, volumes, and scheduler ownership.

### F8.3 — DR objectives and restore drills are still missing · Status: UPDATED · Priority: HIGH · Architectural
- **Location:** `docs/OPERATIONS.md`, backup scripts, `backup_deadman_check`.
- **Current evidence:** The backup policy states `BACKUP_INTERVAL_HOURS` default 6h, restore tooling handles `.env` in archives, J5 covers pre-restore safety backup and migration, and backup absence has dead-man alerting. No explicit RPO/RTO or scheduled restore drill was found.
- **Risk:** Backups may exist without an audited recovery objective or recurring proof that a production archive restores cleanly.
- **Recommended solution:** Document RPO/RTO tied to backup cadence; add a weekly restore drill into a scratch database with row-count/integrity assertions and alerting.
- **Acceptance criteria:** Operations docs state RPO/RTO; latest restore-drill result is visible; failed drills alert.

### F8.4 — No distributed tracing across request/job/egress boundaries · Status: OPEN · Priority: MEDIUM · Architectural
- **Location:** `structured_logging.py`, scheduler/job contexts, outbound HTTP/LLM/webhook paths.
- **Current evidence:** Logs carry request/job/run IDs, but no OpenTelemetry instrumentation or OTLP exporter was found.
- **Risk:** Latency and failure attribution still depends on log search instead of trace spans across API, DB, scheduler, and provider calls.
- **Recommended solution:** Add optional OpenTelemetry FastAPI, asyncpg, and httpx instrumentation; propagate context into scheduler jobs and outbound clients.
- **Acceptance criteria:** A request that reaches DB and external egress produces one trace; scheduler jobs emit spans linked by `run_id`.

### F8.5 — Deployment confidence improved, but release gating remains incomplete · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `deploy/briefr-update.sh`, `docs/OPERATIONS.md`, CI/dependency audit status.
- **Current evidence:** The update path records the pre-update commit, takes a backup, runs Alembic before restart, health-gates backend/nginx, rolls back code on failed health/Alembic, and runs strict Intel smoke by default. This refresh did not collect evidence that CI/dependency-audit is green or that releases are cut only from green commits.
- **Risk:** Runtime update mechanics are safer, but operators still lack a proven upstream green-release signal.
- **Recommended solution:** Keep health/smoke gates; add release metadata or script checks that target commits passed the local/CI gate before production pull.
- **Acceptance criteria:** Release tags or update targets are traceable to green verification; smoke failure disposition is documented, and health failures roll back.

### F8.6 — Configuration schema is rich, but no generated operator reference · Status: UPDATED · Priority: MEDIUM · Quick Win
- **Location:** `backend/config_schema.py`, `operator_settings.py`, `routers/config.py`, docs.
- **Current evidence:** `ConfigField` now exposes help text, type, bounds, units, display labels, restart requirements, and `apply_strategy`; API docs document `/api/admin/config/schema`. No generated exhaustive reference or startup warning for unknown `BRIEFR_*` variables was found.
- **Risk:** Operators can still misconfigure by typo or by missing a production-impact key spread across code/docs.
- **Recommended solution:** Generate a config reference from schema/settings into docs and add an unknown-env-var warning gate.
- **Acceptance criteria:** Generated config reference is checked in or published; CI detects drift; startup warns on unknown `BRIEFR_*` keys.

### F8.7 — Alerting has delivery health and dedupe, but not full policy/self-monitoring · Status: UPDATED · Priority: MEDIUM · Architectural
- **Location:** `backend/webhooks/alerts.py`, `backend/webhooks/engine.py`, `backend/db/webhooks.py`, notifications.
- **Current evidence:** Webhooks support destinations subscribed by event type, per-destination atomic dedupe claims, delivery logging, destination health, and in-app notifications for webhook failures. Watchlist in-app alerts carry severities such as `critical`/`high`. No general severity-to-route policy, cooldown model, or scheduled heartbeat/self-test alert was found.
- **Risk:** Alert fatigue and silent channel failure remain possible, especially when webhook failure notifications depend on the same application notification plane.
- **Recommended solution:** Define severity tiers, routing and cooldown policy, and a synthetic heartbeat/self-check for each alert channel.
- **Acceptance criteria:** Alerts carry severity consistently; destinations can route by severity/event; identical storms are cooldowned; failed channels are detected independently.

---

## Resolved since last audit

No Phase 8 finding is fully closed at the pinned commit. F8.5 is materially improved but remains **UPDATED** because release/CI green gating is still unproven.

---

## Scores

| Sub-audit | Score |
|---|---|
| Logging | 8.7 / 10 |
| Monitoring | 6.7 / 10 |
| Observability | 6.5 / 10 |
| Alerting | 7.4 / 10 |
| Operational Readiness | 8.4 / 10 |
| Configuration | 7.4 / 10 |
| Backup & Restore | 8.7 / 10 |
| Disaster Recovery | 7.2 / 10 |
| Deployment | 7.8 / 10 |
| Upgrade & Migration | 8.2 / 10 |

## Immediate Action Items
1. Add a standard `/metrics` endpoint and documented scrape/alert examples (F8.1).
2. Document RPO/RTO and implement a scheduled restore drill (F8.3).
3. Generate the configuration reference and warn on unknown production env vars (F8.6).

## Production-Readiness Assessment
**Ready for single-node self-host; enterprise/cloud-native gaps remain — 7.8/10.** The update/restore path is meaningfully safer than before, but enterprise operations still need standard metrics, tracing, container packaging, and drilled DR objectives.
