# ADR-001: Intel vs app schema split (open-core data plane)

**Status:** Accepted — **implemented** (Alembic `036_intel_app_schema_split`, 2026-07-26)  
**Date:** 2026-07-08

## Context

BRIEFR will flip to open-core with a **free monthly intel snapshot** so
self-hosters can bootstrap CVE/correlation data without vendor lock-in.
Production instances also hold **operator data**: accounts, sessions, IOC
cache, webhooks, watchlists, and per-user preferences.

Publishing a raw production `pg_dump` would leak operator configuration and
analyst workflow. We need a clear boundary between:

- **Intel** — derived public data + BRIEFR compute safe to redistribute.
- **App** — per-instance operator state that must never ship in public bundles.

Track B (Postgres-native `db/`) is landing but a physical schema split is not
required for the first snapshot release.

## Decision

1. **Document the boundary** in `docs/DATA_SNAPSHOT.md` with explicit table
   and `sync_state` key allowlists (implemented Wave 3 PR 8).
2. **Export via allowlist script** (`scripts/export_intel_snapshot.py`, PR 9)
   using `pg_dump` table filters — not ad-hoc production dumps.
3. **Physical `intel` / `app` schemas** via Alembic `036_intel_app_schema_split`
   (one-time in-place migration on upgrade; `search_path = app, intel, public`).
4. **Default deny** for `sync_state`: ingest watermarks in `intel.sync_state`;
   operator keys in `app.sync_state`.

## Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Publish full production `pg_dump` with docs “don’t leak” | Irreversible operator data exposure; violates privacy posture |
| JSONL-only portable export (v1) | Slower adoption; loses Postgres types and embedding columns fidelity |
| Immediate `CREATE SCHEMA intel/app` split | Blocks open-core timeline; doubles migration/test surface before export path proven |
| Strip operator tables with `pg_restore` post-hoc | Easy to miss tables; no manifest verification |

## Consequences

- Positive: Clear legal/ops story for open-core; export script can be CI-gated;
  aligns with PROGRAM “never raw prod dump” rule.
- Negative: Single-schema coupling remains until a follow-up migration; export
  script must be updated when new tables are added (manifest review in PRs).
- Follow-up: Physical schema split ADR revision when `intel` schema migration
  ships; update `DATA_SNAPSHOT.md` table lists to schema-qualified names.

## Diagram

![Intel vs app data plane](../assets/adr-001-intel-app-split.svg)

Single database today; export tooling enforces the boundary via allowlisted tables and `sync_state` keys (`DATA_SNAPSHOT.md`).
