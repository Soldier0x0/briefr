# ADR-001: Intel vs app schema split (open-core data plane)

**Status:** Accepted (design phase — Wave 3 PR 8)  
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
3. **Defer physical `intel` / `app` schemas** to a later migration tranche after
   Wave 2 user prefs are stable and Post-B CI is green. Until then, one
   database, enforced export boundary in tooling.
4. **Default deny** for `sync_state`: only ingest watermarks in the published
   bundle; scheduler and backup keys stay operator-local.

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

## Diagram (optional)

![Intel vs app data plane — pending](../assets/placeholder-diagram.svg)

> **Asset:** `docs/assets/adr-001-intel-app-split.png`  
> **Brief:** Two Postgres schemas feeding one export allowlist gate.
