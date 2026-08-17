# Investigation layer (trust, not a new product) — Implementation Plan

> **Revision:** 2026-08-17 — scoped from the original 10-task platform roadmap (PR #835).  
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement **this plan’s P0 tasks only**. Later work is listed so it is not invented mid-flight — do not implement it from this document.

**Goal:** Make existing CVE / IOC / ATT&CK / campaign / TI-mirror relationships **typed, bounded, and honest** so an analyst can start from a CVE or IOC and see *what BRIEFR already knows, how sure it is, and what it does not know* — without replacing PostgreSQL, adding a graph database, or building a second case-management product.

**Architecture:** Keep FastAPI + PostgreSQL 16 + React/Vite. Add a **read-only investigation projection** over tables that already exist (`cves`, technique maps, OTX pulse/IOC, `ti_mirror_iocs`, campaigns, SigmaHQ joins, embeddings). Persist **assertions** only if the projection cannot attach provenance without inventing a second source of truth. The existing session-only investigation thread (`InvestigationContext.jsx`) stays the UI seed; **do not** add saved cases, notes, or sharing in this plan.

**Tech Stack:** FastAPI, Pydantic, Alembic (only if Task 4 is unblocked), pytest, existing analyst session auth, `./scripts/verify-local.sh`.

## Vision (what this tool is for)

BRIEFR is a **self-hosted analyst intelligence pane**: daily brief, stack-ranked CVEs, IOC lookup, correlation, detection starters (Forge/Detect), one operator, one box. Success is **trust fast enough to act** — not a cloud TI platform, not a SIEM, not a scanner, not multi-tenant caseware.

The investigation vision is: start from a CVE or IOC, expand **one hop** of evidence-backed links, see community vs derived vs semantic clearly, then decide (patch / hunt / watch). Minutes saved come from not opening five vendor tabs — same north star as maintainer strategy (analyst time), not from more chrome.

**This plan serves strategy gap (2) — trust / verifiability.** It is deliberately *not* “more features.” Detection quality and install/adoption are out of scope here.

## Product constraints (non-negotiable)

Copied from living product truth (`docs/PRODUCT.md`, `docs/PRODUCT_STATUS.md`):

- PostgreSQL production; SQLite is test/dev fallback only.
- No Neo4j / Memgraph / Redis / microservices / graph DB.
- Single operator per instance — no owner/member ACL, share links, or multi-user cases.
- Community intel stays labeled (OTX, TI mirrors). Do not flatten disagreements into facts.
- LLM output is advisory; never scoring or relationship evidence.
- Heavy work stays off the request path (scheduler / bounded reads only).
- Free/OSS deploy: paid sources optional.
- STIX/TAXII remains out (v1.5 already excluded Phase 4 STIX).

## What already exists (do not rebuild)

| Piece | Where | Use it |
|-------|--------|--------|
| Session investigation thread | `frontend/src/context/InvestigationContext.jsx` | CVE / IOC / actor / technique pins; PDF export |
| Scoring / OP / SSVC | `backend/scoring/`, `POST /api/cves/{id}/risk` | Still the “what first” answer for CVEs |
| Correlation + confidence | `backend/correlation/` | Derived edges; expose factors, do not hide |
| TI mirrors | `ti_mirror_iocs` (038–039), ThreatFox/URLhaus/MalwareBazaar | Corroboration already shipped (#821–#822) |
| Blocklist export | admin threat-intel (#834–#837) | Action path exists; do not automate from weak edges |
| Provenance fragments | `backend/intel/provenance.py`, `correlation/source_evidence.py` | Reuse in projection metadata |
| Auth | session cookie + optional search tokens | Same gates on new GETs |

Latest schema work in-tree is Alembic **040** (`infra_classifications`). If assertions ever ship, next revision is **041** — only after Task 3 proves a gap.

## File map (P0 only)

| File | Responsibility |
|------|----------------|
| `backend/investigations/contracts.py` | Entity types, edge classes, knowledge states, filter/pagination models |
| `backend/investigations/projection.py` | Bounded reads over existing tables; no writes |
| `backend/routers/investigations.py` | GET entity / relationships / timeline (timeline may be thin: timestamps from existing rows) |
| `backend/tests/test_investigation_contracts.py` | Contract validation |
| `backend/tests/test_investigation_projection.py` | Fixture-backed hops |
| `backend/tests/test_investigation_routes.py` | Auth, caps, pagination |
| `docs/API_REFERENCE.md` | Document the three GETs |
| `docs/PRODUCT_STATUS.md` | One row when APIs exist |

Do **not** create `RelationshipExplorer.jsx`, case tables, or alias tables in this plan.

## Global Constraints

- Default expansion **depth 1**, max **2**. Hard node/edge caps + keyset cursor. Truncation must be visible in the JSON (`truncated`, `next_cursor`).
- Every edge: `edge_class` ∈ `direct_fact | reported | derived | analyst_assertion | semantic`, plus source key, confidence if known, freshness timestamps if known.
- Missing data is `partial` / `unknown` / `stale` — never silent empty.
- Semantic (pgvector) edges only when `include_semantic=1`; never used as scoring input.
- No new scheduler jobs in P0.
- Merge gate: `./scripts/verify-local.sh` on the last P0 PR.

---

## P0 — this document’s work queue

Stop after Task 3 unless the gate in Task 3 fails for provenance (then Task 4).

### Task 1: Shared contracts

**Files:**
- Create: `backend/investigations/contracts.py`
- Create: `backend/investigations/__init__.py` (export public types only)
- Create: `backend/tests/test_investigation_contracts.py`
- Modify: `docs/API_REFERENCE.md` (stub section is enough until Task 3)

**Interfaces:**
- Produce: `EntityType`, `EdgeClass`, `KnowledgeState` (string enums / Literals)
- Produce: `EntityRef`, `RelationshipRef`, `RelationshipFilters`, `RelationshipPage`
- Entity types for P0: `cve`, `ioc`, `technique`, `campaign` only. Actor / malware / infrastructure / advisory are **not** first-class roots in P0 (they may appear as **edge targets** with source-qualified ids).

- [ ] **Step 1: Write failing tests** for valid/invalid `entity_type`, `edge_class`, depth > 2 rejected, `include_semantic` default false.

- [ ] **Step 2: Run** `cd backend && pytest tests/test_investigation_contracts.py -q` — expect fail (module missing).

- [ ] **Step 3: Implement** immutable Pydantic v2 models with explicit `serialization_alias` where JSON names differ. Reject unknown entity types.

- [ ] **Step 4: Re-run tests** — expect pass.

- [ ] **Step 5: Commit** `feat: define investigation relationship contracts`

### Task 2: Read-only projection

**Files:**
- Create: `backend/investigations/projection.py`
- Create: `backend/tests/test_investigation_projection.py`
- Modify: correlation/db helpers **only** if a batch fetch already exists and must be reused — do not duplicate hub-cap logic; call existing correlation/IOC helpers.

**Interfaces:**
- `async def get_entity(db, entity_type: str, entity_id: str) -> EntityRef | None`
- `async def expand_relationships(db, root: EntityRef, filters: RelationshipFilters) -> RelationshipPage`

**Required hops (fixture tests):**
1. CVE → ATT&CK technique (`cve_technique_map` or equivalent)
2. CVE → OTX pulse → IOC (existing OTX tables)
3. CVE → campaign membership (correlation campaign tables)
4. CVE → TI-mirror IOC corroboration (`ti_mirror_iocs`) when present
5. CVE → SigmaHQ rule join when index has a CVE-exact hit
6. Optional: related CVE via existing related/heuristic path as `derived` or `semantic` per current code — label honestly

- [ ] **Step 1: Failing tests** with seeded CVE + one technique + one pulse IOC (follow patterns in `backend/tests/test_*correlation*` / OTX tests).

- [ ] **Step 2: Implement** bounded SQL; no N+1 per neighbor. Cap lists. Set `edge_class` from how the row was produced (FK = `direct_fact` or `reported`; correlation engine = `derived`; vector = `semantic`).

- [ ] **Step 3: Run** projection tests + existing `tests/test_*correlation*` / search tests that you touch.

- [ ] **Step 4: Commit** `feat: add bounded intelligence relationship projection`

### Task 3: Bounded GET APIs

**Files:**
- Create: `backend/routers/investigations.py`
- Create: `backend/tests/test_investigation_routes.py`
- Modify: `backend/main.py` (include router)
- Modify: `docs/API_REFERENCE.md`, `docs/PRODUCT_STATUS.md`

**Interfaces:**
- `GET /api/investigations/entities/{entity_type}/{entity_id}`
- `GET /api/investigations/entities/{entity_type}/{entity_id}/relationships`

Timeline endpoint is **optional in P0**: only add `GET .../timeline` if it is a thin wrapper over `cve_change_history` / `epss_history` for CVE roots. Do not invent a universal timeline.

Query: `depth` (default 1, max 2), `limit`, `cursor`, `edge_class`, `min_confidence`, `include_semantic`, `include_stale`.

- [ ] **Step 1: Tests** — unauthenticated 401; analyst session 200; invalid type 422; depth 3 422; `truncated` true when cap hit.

- [ ] **Step 2: Implement** same rate-limit class as other analyst GETs. Response metadata: `source_status`, `truncated`, `next_cursor`, `generated_at`.

- [ ] **Step 3: Run** `pytest tests/test_investigation_routes.py tests/test_investigation_projection.py tests/test_investigation_contracts.py -q` then `./scripts/verify-local.sh`.

- [ ] **Step 4: Commit** `feat: expose bounded investigation relationship APIs`

**Gate after Task 3:** If relationship payloads cannot attach source/freshness without lying, do Task 4. If they can (reuse provenance + mirror receipts), **stop P0**. Do not start frontend graph work.

### Task 4: Assertions table (conditional)

**Only if** Task 3 gate fails.

**Files:**
- Create: `backend/alembic/versions/041_intel_assertions.py` (next free after 040)
- Create: `backend/db/assertions.py`, `backend/intel/assertions.py`
- Create: `backend/tests/test_assertions.py`
- Modify: `backend/db/schema_inventory.py` — classify as **intel** if published in snapshots
- Modify: snapshot tests / `docs/DATA_SNAPSHOT.md` if intel-classified

**Interfaces:**
- Append-friendly assertions; **retract**, do not overwrite silently.
- Adapters from existing correlation receipts / provenance only — do not duplicate `cves` rows.

- [ ] Tests for uniqueness, retraction, snapshot classification.
- [ ] Commit `feat: persist intelligence assertions and evidence provenance`

---

## Explicitly not this plan (P1+)

Do not implement from this file. Separate plans later, after P0 is in production and used.

| Later idea | Why wait |
|------------|----------|
| Canonical aliases (actor/malware/infra identity) | Silent merge is worse than source-qualified strings; needs collision UX |
| Persistent cases, notes, findings, sharing | Single-operator product; session thread + PDF already exists |
| `RelationshipExplorer.jsx` / graph chrome | Contracts + API first; drawer can call the GET later in a small UX PR |
| Universal timeline / knowledge-gap UI states | Needs assertion history or it is theater |
| Actor/malware/advisory as investigation roots | No durable identity yet |
| Saved-query alerts, case exports, STIX | After semantics stabilize |
| Graph database evaluation | Only if measured Postgres expansion misses latency targets |

## Decision gates (keep)

- Do not add a graph database unless bounded Postgres expansion fails agreed latency on representative data.
- Do not merge source claims on display-name equality.
- Do not treat semantic similarity as fact or scoring input.
- Do not auto-block or auto-patch from a relationship lacking current evidence, confidence, and freshness.
- Do not automate response from generated/community detection without validation state.

## Risks (P0)

| Risk | Mitigation |
|------|------------|
| Projection becomes a slow god-query | Caps, depth 1 default, reuse indexed correlation/IOC paths |
| Edges look more certain than sources | Distinct `edge_class`; keep `why_not_higher` / unverified copy |
| Second source of truth | Prefer Task 2–3 only; Task 4 only if provenance is actually missing |
| Scope creep into cases/graph UI | This file forbids those files |

## Verification (P0 done)

- [ ] `cd backend && pytest tests/test_investigation_contracts.py tests/test_investigation_projection.py tests/test_investigation_routes.py -q`
- [ ] `./scripts/verify-local.sh`
- [ ] New routes require analyst session (and search-token only if you explicitly opt in, matching existing search routes)
- [ ] Responses cap nodes/edges and set `truncated`
- [ ] No frontend graph; no Alembic 041 unless Task 4 unblocked
- [ ] `PRODUCT_STATUS.md` one-line: bounded investigation GETs exist; cases still session-only

## Recommendation (why this cut)

The original 10-task sequence was the right **north star** and the wrong **work queue**. BRIEFR already has the hard ingredients (feeds, scoring, TI mirrors, correlation, investigation thread). The highest-return next layer is **honest, bounded relationship reads** so the drawer and IOC tab can tell the truth. Persistent cases and a graph explorer are a different product; they wait until this API is something an analyst would actually call.
