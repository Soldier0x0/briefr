# Underutilized capacity — utilization design (operator env)

**Status:** Draft for plan approval  
**Date:** 2026-07-20  
**Context:** Live-tree multi-agent audit (no graphify). Operator reports nearly all env flags are **on** (unlike `.env.example` defaults).

## 1. Operator environment assumption (SSOT for this work)

Do **not** treat `backend/.env.example` as the operator’s runtime. For this program assume:

| Area | Operator state |
|------|----------------|
| `PROCRASTINATE_ENABLED` | **1** (confirmed) |
| Embeddings + auto-on-ingest | **1** |
| LLM product extraction | **1** |
| Correlation precompute | **1** |
| Rate limits / CPE / stack backfill / API metering / backups / OTX continuous / exploit sync / etc. | **1** (operator: “everything enabled”) |
| Disabled / empty | Telegram bot token, Telegram webhook, generic webhook URL / generic webhook enablement |

**Implication:** Utilization work is **not** “turn flags on.” It is **wire product surfaces, durable execution, Catch-up drain, and FE adoption** so enabled capacity is actually used and operable.

## 2. Problem

Infrastructure and features are shipped, but:

1. Procrastinate has only **one** production task (`stack_backfill`); LLM extraction and other heavy work still fail hard on APScheduler with manual Retry.
2. `GET /api/admin/jobs/outbound` has **no frontend**.
3. Catch-up only nudges embeddings (+ precompute); does not drain other enabled backlogs.
4. Semantic search can return technique/campaign hits; FEED maps to CVE cards only.
5. Stack backfill claims “will resume automatically” without re-defer.
6. FE dead code and misplaced `openpyxl` waste clarity.

## 3. Goals / non-goals

**Goals**

- Make Procrastinate the durable engine for restart-sensitive / retryable heavy work (starting with LLM product extraction).
- Give operators visibility into durable jobs (Admin UI).
- Expand Catch-up to kick more **already-enabled** backlog jobs.
- Surface embeddings typed hits; fix false “auto-resume”; clean obvious FE/deps waste.

**Non-goals**

- New brokers (Redis/Rabbit/Temporal).
- Replacing `api_queue` pacing.
- Migrating every APScheduler cron into Procrastinate in v1.
- Enabling Telegram/generic webhooks (operator deliberately unset).
- Reading or committing operator `.env` secrets.

## 4. Architecture

```
APScheduler (cron / Catch-up tick / manual Run)
    → enqueue durable unit (Procrastinate) when restart/retry matters
    → keep short syncs & pacing on existing paths

api_queue          = outbound HTTP pacing (unchanged)
Procrastinate      = durable job rows + in-process worker (already on)
Admin outbound UI  = read procrastinate_jobs + optional health_ping
```

**Ownership registry (unchanged rule):** APScheduler ids never use `jobs:` prefix; new Procrastinate tasks update `DOCUMENTED_PROCRASTINATE_TASKS` + `SYSTEM_DESIGN.md`.

## 5. Priority lanes (v1)

| Priority | Sources |
|----------|---------|
| High | Manual Retry / Agree / Admin Run that enqueues durable work |
| Normal | Catch-up tick kicks |
| Low | Periodic canary `health_ping` |

Implement via Procrastinate `priority` / queue naming already supported; do not invent a second queue store.

## 6. Retry policy (retryable errors)

For durable tasks (LLM extraction first):

- Retryable: `Database command timeout`, lock/contention class, transient network to LLM after provider chain exhausted only if task policy says so.
- Backoff: ~180s → ~240s → ~300s (bounded); then `dead` / failed terminal visible in Admin.
- Non-retryable: auth/config missing keys — fail once, surface in Admin.

## 7. Phased delivery

| Wave | Name | Ships independently |
|------|------|---------------------|
| W1 | Admin outbound jobs panel | Yes |
| W2 | Durable LLM product extraction + bounded auto-retry | Yes |
| W3 | Catch-up drains more enabled backlogs | Yes |
| W4 | FEED/semantic typed hits (techniques/campaigns) | Yes |
| W5 | Stack backfill true auto-resume | Yes |
| W6 | FE dead-code + `openpyxl` hygiene | Yes |
| W7 | Docs drift + health canary + Admin schema gaps | Yes |

## 8. Success criteria

- Operator can open Admin and see Procrastinate job rows when enabled.
- LLM extraction DB timeout schedules a durable retry without manual Retry (within backoff caps).
- Catch-up tick kicks at least embeddings + correlation precompute + LLM extraction + CPE sync (when those jobs exist / enabled).
- Semantic technique/campaign hits visible somehow in FEED or a clear secondary list (not silently dropped).
- `verify-local.sh` green per wave PR.
