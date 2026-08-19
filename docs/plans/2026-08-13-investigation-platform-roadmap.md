# Investigation graph APIs (backend first) — Implementation Plan

> **Revision:** 2026-08-19 — backend graph contract so a later **INVESTIGATE** graph browser can render CVE / IOC / hash hops without a graph database. Aligns parse order, caps, cursor, and resolve-vs-graph types with the P0 APIs.  
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement **this plan’s P0 tasks only**. Do **not** implement the Investigate tab or canvas from this file.

**Goal:** Ship a read-only, session-gated investigation API that returns a **graph-shaped** page (nodes + edges + truncation) over data BRIEFR already stores, so a later full-canvas **INVESTIGATE** panel can search a CVE / IOC / hash and expand honest one-hop relationships.

**Architecture:** FastAPI + PostgreSQL 16 (SQLite test fallback). New package `backend/investigations/` projects existing tables into a frozen JSON graph. No Neo4j, no Redis, no new ingest jobs, no LLM as evidence. Layout, animation, and the header tab are **P1 UI** and must not land in P0. The session pin list (`InvestigationContext.jsx` / `InvestigationPanel.jsx`) stays as-is until P1.

**Tech Stack:** FastAPI, Pydantic v2, pytest, existing analyst session auth (`require_user` / session middleware), `./scripts/verify-local.sh`. Alembic **041** only if Task 5 is unblocked after the Task 4 provenance gate.

## North star (P1, not this work queue)

Analyst opens **INVESTIGATE** (new header tab, full canvas — not the pin overlay). Types a CVE, hash, IP, or domain. Backend **resolve** + **relationships** return nodes/edges. Client draws a force-directed graph (Obsidian-like motion is frontend-only). Click a node → same GET on that node, merge into the canvas. Edge stroke/opacity encodes `edge_class`. Truncation is visible (“+N more”). FORGE stays; this tab does not replace it.

P0 exists so that UI can be built later **without inventing a second data model**.

## Product constraints (non-negotiable)

- PostgreSQL production; SQLite is test/dev fallback only.
- No Neo4j / Memgraph / Redis / microservices / graph DB.
- Single operator — no ACL, share links, or saved cases in this plan.
- Community intel stays labeled (OTX, TI mirrors). Do not flatten disagreements into facts.
- LLM output is never relationship evidence or scoring input.
- Heavy work stays off the request path. P0 adds **no** scheduler jobs and **no** outbound HTTP (no VirusTotal / NVD / AbuseIPDB on expand).
- Default expansion **depth 1**, max **2**. Caps + keyset cursor. Never “all connections in the database.”
- Semantic (pgvector) edges only when `include_semantic=1`.
- Free/OSS deploy: paid sources optional and unused by these GETs.

## What already exists (do not rebuild)

| Piece | Where | Use it |
|-------|--------|--------|
| Session pin thread | `frontend/src/context/InvestigationContext.jsx` | Leave until P1; do not turn it into the graph |
| Scoring / OP / SSVC | `backend/scoring/`, `POST /api/cves/{id}/risk` | Still “what first” for CVEs; not graph evidence |
| Correlation | `backend/correlation/` | Derived edges; expose factors |
| TI mirrors | `ti_mirror_iocs` | Corroboration (#821–#822) |
| IOC normalize | `backend/correlation/ioc_normalize.py` | `normalize_ioc` / `normalize_ioc_type` for resolve |
| Provenance | `backend/intel/provenance.py`, `correlation/source_evidence.py` | `source`, freshness |
| Auth | session cookie | Same gates as other analyst GETs |
| Header tabs | `frontend/src/components/Header.jsx` | P1 adds INVESTIGATE; P0 does not touch |

Latest Alembic in-tree: **040**. Assertions = **041** only after the **Task 4** provenance gate (Task 5).

## Frozen graph JSON (P1 UI must consume this — do not change names later)

Stable **node id**: `{entity_type}:{entity_id}`  
IOC `entity_id`: `{ioc_kind}:{canonical_value}` where `ioc_kind` is `ip` \| `hash` \| `domain` \| `url` (lowercase).  
`normalize_ioc` returns uppercase kinds (`IP` / `HASH` / `DOMAIN` / `URL`); map them before composing `entity_id` (`IP`→`ip`, `HASH`→`hash`, `DOMAIN`→`domain`, `URL`→`url`). Never store `IP:` / `HASH:` in the node id.  
Examples: `cve:CVE-2024-1234`, `ioc:hash:e3b0c442…`, `ioc:ip:1.2.3.4`, `technique:T1059.003`, `campaign:camp_ab12cd34ef56`.

Path params: percent-encode `entity_id` (domains, URLs). Do not put raw `/` in the id.

```json
{
  "root": {
    "node_id": "cve:CVE-2024-1234",
    "entity_type": "cve",
    "entity_id": "CVE-2024-1234",
    "label": "CVE-2024-1234",
    "knowledge_state": "known"
  },
  "nodes": [
    {
      "node_id": "cve:CVE-2024-1234",
      "entity_type": "cve",
      "entity_id": "CVE-2024-1234",
      "label": "CVE-2024-1234",
      "knowledge_state": "known"
    }
  ],
  "edges": [
    {
      "edge_id": "cve:CVE-2024-1234|technique:T1059|direct_fact|cve_technique_map",
      "source_node_id": "cve:CVE-2024-1234",
      "target_node_id": "technique:T1059",
      "edge_class": "direct_fact",
      "source_key": "cve_technique_map",
      "confidence": null,
      "observed_at": null,
      "fetched_at": null,
      "note": "one directed hop; canvas treats the node pair as undirected"
    }
  ],
  "source_status": "ok",
  "knowledge_state": "partial",
  "truncated": false,
  "next_cursor": null,
  "generated_at": "2026-08-17T10:00:00Z",
  "depth": 1
}
```

`edge_class` ∈ `direct_fact` \| `reported` \| `derived` \| `analyst_assertion` \| `semantic`.  
`knowledge_state` ∈ `known` \| `partial` \| `unknown` \| `stale`.  
Edges are **undirected for display**: the canvas treats a hop as the unordered pair of node ids plus `edge_class` + `source_key`. The API still emits a single directed record (expand root → neighbor). `edge_id` is `source_node_id|target_node_id|edge_class|source_key` as stored; do not emit both A→B and B→A for the same hop.  
API **must not** return `x` / `y` / color / animation fields. Layout is client-only.

**Do not implement from this file:** `RelationshipExplorer.jsx`, `InvestigateGraph.jsx`, Header tab `investigate`, case tables, alias tables.

## File map (P0)

| File | Responsibility |
|------|----------------|
| `backend/investigations/contracts.py` | Enums + Pydantic graph models |
| `backend/investigations/__init__.py` | Public exports only |
| `backend/investigations/resolve.py` | Parse query → `EntityRef` (CVE regex, `normalize_ioc`) |
| `backend/investigations/projection.py` | Bounded SQL; build `GraphPage` |
| `backend/routers/investigations.py` | Three GETs |
| `backend/tests/test_investigation_contracts.py` | Model validation |
| `backend/tests/test_investigation_resolve.py` | Query parsing |
| `backend/tests/test_investigation_projection.py` | Fixture hops |
| `backend/tests/test_investigation_routes.py` | Auth, 422, caps |
| `backend/tests/test_router_split.py` | Append new routes to `EXPECTED_ROUTES` |
| `backend/main.py` | `include_router` |
| `docs/API_REFERENCE.md` | Document the three GETs |
| `docs/PRODUCT_STATUS.md` | One row when APIs exist |

## Caps, cursor, and page identity

- Default `depth=1`, reject `depth > 2` with 422.
- Default `limit=50`, max `100`. **`limit` is an edge cap.** Root is always present in `nodes`, so that list may hold `limit + 1` nodes. Set `truncated=true` when the edge cap or that node cap is hit.
- Keyset `cursor`: opaque base64 JSON with `after_edge_id` equal to the last `edge_id` served. An empty expansion is valid (`nodes == [root]`).
- Optional flags: `include_semantic` and `include_stale` both default off.

## Global Constraints

- Expand with batched SQL (no per-neighbor round trips). Reuse existing correlation / OTX / TI-mirror helpers and their hub caps.
- Merge gate: `./scripts/verify-local.sh` on the last P0 PR.
- Router snapshot: additive append only in `EXPECTED_ROUTES` (same pattern as Forge).

---

## P0 — work queue (implement in this order)

Stop after Task 4 unless **Task 4’s** provenance gate fails (then Task 5). Do not start Task 5 because Task 3 tests failed.

### Task 1: Shared graph contracts

**Files:**
- Create: `backend/investigations/contracts.py`
- Create: `backend/investigations/__init__.py`
- Create: `backend/tests/test_investigation_contracts.py`

**Interfaces:**
- Produce: `EntityType`, `IocKind`, `EdgeClass`, `KnowledgeState` (`Literal` or `StrEnum`)
- Produce: `EntityRef`, `GraphNode`, `GraphEdge`, `GraphPage`, `RelationshipFilters`
- `node_id` helper: `def make_node_id(entity_type: str, entity_id: str) -> str`
- `RelationshipFilters`: `depth: int = 1`, `limit: int = 50`, `cursor: str | None = None`, `edge_class: EdgeClass | None = None`, `min_confidence: str | None = None`, `include_semantic: bool = False`, `include_stale: bool = False`
- Frozen Pydantic models: `model_config = ConfigDict(frozen=True)` and extra fields forbidden.
- Resolve vs graph types: `RESOLVE_ROOT_ENTITY_TYPES = {cve, ioc, technique, campaign}`. `GRAPH_ENTITY_TYPES = RESOLVE_ROOT ∪ {publication}` (`sigma_rule` may appear as a hop target). Actor / malware / infra / advisory may appear as **targets** with source-qualified ids, never as resolve roots.
- `GET .../entities/{entity_type}/...` and `parse_investigation_query` accept only resolve roots. Neighbor `nodes` may use any graph entity type.

- [ ] **Step 1: Write failing tests**

```python
import pytest
from pydantic import ValidationError

from investigations.contracts import (
    EdgeClass,
    GraphEdge,
    GraphPage,
    RelationshipFilters,
    make_node_id,
)


def test_make_node_id_ioc_hash():
    assert make_node_id("ioc", "hash:abc") == "ioc:hash:abc"


def test_filters_reject_depth_above_two():
    with pytest.raises(ValidationError):
        RelationshipFilters(depth=3)


def test_include_semantic_defaults_false():
    assert RelationshipFilters().include_semantic is False


def test_unknown_edge_class_rejected():
    with pytest.raises(ValidationError):
        GraphEdge(
            edge_id="x",
            source_node_id="cve:CVE-1",
            target_node_id="technique:T1",
            edge_class="guess",  # type: ignore[arg-type]
            source_key="t",
        )


def test_graph_page_requires_nodes_and_edges():
    root = {
        "node_id": "cve:CVE-1",
        "entity_type": "cve",
        "entity_id": "CVE-1",
        "label": "CVE-1",
        "knowledge_state": "known",
    }
    page = GraphPage(
        root=root,
        nodes=[root],
        edges=[],
        source_status="ok",
        knowledge_state="unknown",
        truncated=False,
        next_cursor=None,
        generated_at="2026-08-17T00:00:00Z",
        depth=1,
    )
    assert page.truncated is False
    assert any(node["node_id"] == root["node_id"] for node in page.nodes)


def test_graph_page_always_includes_root_in_nodes():
    root = {
        "node_id": "cve:CVE-1",
        "entity_type": "cve",
        "entity_id": "CVE-1",
        "label": "CVE-1",
        "knowledge_state": "known",
    }
    page = GraphPage(
        root=root,
        nodes=[root],
        edges=[],
        source_status="ok",
        knowledge_state="unknown",
        truncated=False,
        next_cursor=None,
        generated_at="2026-08-17T00:00:00Z",
        depth=1,
    )
    assert {n.node_id for n in page.nodes} == {page.root.node_id}
```

- [ ] **Step 2: Run** `cd backend && pytest tests/test_investigation_contracts.py -q` — expect fail (module missing).

- [ ] **Step 3: Implement** Pydantic v2 models. `RelationshipFilters.depth` `ge=1, le=2`. `limit` `ge=1, le=100`. Reject unknown `entity_type` / `edge_class`.

- [ ] **Step 4: Re-run tests** — expect pass.

- [ ] **Step 5: Commit** `feat: define investigation graph contracts`

### Task 2: Resolve search string → entity

**Files:**
- Create: `backend/investigations/resolve.py`
- Create: `backend/tests/test_investigation_resolve.py`

**Interfaces:**
- Consumes: `EntityRef`, `normalize_ioc` from `correlation.ioc_normalize`
- Produce: `def parse_investigation_query(q: str) -> EntityRef`
- Produce: `async def resolve_entity(db, q: str) -> EntityRef | None` — parse, then existence check (`cves` row, IOC in `otx_pulse_iocs` / `ti_mirror_iocs`, technique in `mitre_techniques` / `cve_technique_map`, campaign id in correlation campaign tables — `camp_` + 12 hex). Missing row → `None` (route maps to 404 with `knowledge_state: unknown`, not an empty graph that looks like “no intel”).

Parse order:
1. Strip; reject empty / `len > 512` → `ValueError` (route 422).
2. If `CVE-\d{4}-\d{4,}` (case-insensitive) → type `cve`, id uppercased.
3. Else if `T\d{4}(?:\.\d{3})?` ATT&CK id → `technique` (**before** IOC fallback so `T1059.003` is not guessed as a domain).
4. Else if `camp_[0-9a-f]{12}` or `campaign:camp_[0-9a-f]{12}` → `campaign` (preserve `camp_…` case; do not invent numeric campaign ids).
5. Else `normalize_ioc` with guessed kind: hash if hex 32/40/64; else IP; else URL if `://` or path; else domain. Map uppercase kinds to lowercase `ioc_kind`.
6. Else fail `ValueError`.

- [ ] **Step 1: Failing tests**

```python
import pytest
from investigations.resolve import parse_investigation_query


def test_parse_cve():
    ref = parse_investigation_query("cve-2024-1234")
    assert ref.entity_type == "cve"
    assert ref.entity_id == "CVE-2024-1234"


def test_parse_sha256():
    q = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ref = parse_investigation_query(q)
    assert ref.entity_type == "ioc"
    assert ref.entity_id.startswith("hash:")


def test_parse_technique_before_ioc_fallback():
    ref = parse_investigation_query("T1059.003")
    assert ref.entity_type == "technique"
    assert ref.entity_id == "T1059.003"


def test_parse_campaign_id():
    ref = parse_investigation_query("campaign:camp_ab12cd34ef56")
    assert ref.entity_type == "campaign"
    assert ref.entity_id == "camp_ab12cd34ef56"


def test_parse_rejects_empty():
    with pytest.raises(ValueError):
        parse_investigation_query("  ")
```

- [ ] **Step 2: Run** `cd backend && pytest tests/test_investigation_resolve.py -q` — expect fail.

- [ ] **Step 3: Implement** using `normalize_ioc`; do not call external APIs.

- [ ] **Step 4: Re-run** — expect pass.

- [ ] **Step 5: Commit** `feat: resolve investigation search queries to entity refs`

### Task 3: Read-only graph projection

**Files:**
- Create: `backend/investigations/projection.py`
- Create: `backend/tests/test_investigation_projection.py`

**Interfaces:**
- Consumes: `EntityRef`, `RelationshipFilters`, `GraphPage`
- Produce: `async def get_entity(db, entity_type: str, entity_id: str) -> EntityRef | None`
- Produce: `async def expand_relationships(db, root: EntityRef, filters: RelationshipFilters) -> GraphPage`
- Root is always included in `nodes` (assert this in projection tests even when `edges` is empty). Edges are undirected for display but stored as source=root (or discovered node) → target; do not emit duplicate A→B and B→A for the same hop (`edge_id` as above).

**Required hops (fixture tests; seed like `tests/test_*correlation*` / OTX tests):**
1. CVE → ATT&CK (`cve_technique_map`) → `direct_fact`, `source_key=cve_technique_map`
2. CVE → OTX pulse IOC (`otx_cve_pulses` / `otx_pulse_iocs`) → `reported`, `source_key=otx`
3. CVE → campaign membership → `derived`, `source_key=correlation`
4. CVE → TI-mirror IOC (`ti_mirror_iocs`) when present → `reported`, `source_key=threatfox|urlhaus|malwarebazaar` as stored
5. CVE → SigmaHQ CVE-exact hit → `reported` or `direct_fact` per how the index row is stored; label honestly
6. Related CVE via existing related/heuristic path → `derived` or `semantic` (semantic **only** if `include_semantic` and vector path used)

`depth=2`: expand neighbors of neighbors with the same caps on the **total** page, not per node. Prefer breadth-first and stop when cap hits.

- [ ] **Step 1: Failing tests** with seeded CVE + one technique + one pulse IOC. Assert `edge_class`, `truncated` when `limit=1` and two edges exist, root `node_id` present **in `nodes`**.

- [ ] **Step 2: Implement** bounded SQL / batch helpers. Set `knowledge_state=partial` if any hop source is missing/stale; `unknown` only when root does not exist (caller should 404 first).

- [ ] **Step 3: Run** `cd backend && pytest tests/test_investigation_projection.py tests/test_investigation_contracts.py tests/test_investigation_resolve.py -q` plus any correlation tests you touched.

- [ ] **Step 4: Commit** `feat: add bounded investigation graph projection`

### Task 4: Bounded GET APIs

**Files:**
- Create: `backend/routers/investigations.py`
- Create: `backend/tests/test_investigation_routes.py`
- Modify: `backend/main.py` (import + `app.include_router(investigations_router.router)` next to other analyst routers)
- Modify: `backend/tests/test_router_split.py` — append to `EXPECTED_ROUTES` and assert module `routers.investigations`
- Modify: `docs/API_REFERENCE.md`, `docs/PRODUCT_STATUS.md`

**Interfaces:**
- `GET /api/investigations/resolve?q=` → `{ "root": GraphNode, "query": "<normalized>" }` or 404 `{ "detail": "unknown entity", "knowledge_state": "unknown" }`
- `GET /api/investigations/entities/{entity_type}/{entity_id}` → `GraphNode` (or `EntityRef` serialized the same) or 404
- `GET /api/investigations/entities/{entity_type}/{entity_id}/relationships` → `GraphPage`

Query on relationships: `depth`, `limit`, `cursor`, `edge_class`, `min_confidence`, `include_semantic`, `include_stale`.

Do **not** add a universal timeline in P0. Optional later: thin CVE-only wrapper over `cve_change_history` / `epss_history` — out of this task.

Auth: same as `/api/cves` (session middleware). Unauthenticated 401. Invalid `entity_type` or `depth=3` → 422. Rate-limit class: same as other analyst GETs (no new IOC-lookup bucket unless you share `RATE_LIMIT_IOC` by mistake — do not).

Response metadata on `GraphPage`: `source_status`, `truncated`, `next_cursor`, `generated_at`, `depth`.

- [ ] **Step 1: Tests** — 401 without cookie; analyst 200; invalid type 422; depth 3 422; `truncated` true when cap hit; resolve hash and CVE; `test_router_split` updated.

- [ ] **Step 2: Implement** router; `GraphPage.model_dump(mode="json")`.

- [ ] **Step 3: Run** `cd backend && pytest tests/test_investigation_routes.py tests/test_investigation_projection.py tests/test_investigation_contracts.py tests/test_investigation_resolve.py tests/test_router_split.py -q` then `./scripts/verify-local.sh`.

- [ ] **Step 4: Commit** `feat: expose investigation resolve and graph relationship APIs`

**Gate after Task 4:** If edges cannot attach `source_key` / freshness without lying, do Task 5. If they can (provenance + mirror receipts), **P0 is done**. Do not start frontend graph work.

### Task 5: Assertions table (conditional)

**Only if** Task 4 gate fails.

**Files:**
- Create: `backend/alembic/versions/041_intel_assertions.py` (next free after 040)
- Create: `backend/db/assertions.py`, `backend/intel/assertions.py`
- Create: `backend/tests/test_assertions.py`
- Modify: `backend/db/schema_inventory.py` if intel-classified
- Modify: snapshot tests / `docs/DATA_SNAPSHOT.md` if needed

**Interfaces:** Append-only assertions; **retract**, do not overwrite. Adapters from correlation receipts only — do not duplicate `cves` rows. Graph edges with `edge_class=analyst_assertion` only from this table.

- [ ] Tests for uniqueness, retraction, snapshot classification.
- [ ] Commit `feat: persist intelligence assertions and evidence provenance`

---

## P1 — Investigate graph browser (separate plan; do not implement here)

Start a new plan only after P0 is merged and `verify-local.sh` is green. That plan must consume the frozen JSON above with **zero** schema invention.

| Piece | Planned files (P1) |
|-------|-------------------|
| Header tab | `frontend/src/components/Header.jsx` — add `{ id: 'investigate', label: 'INVESTIGATE' }` after IOC LOOKUP (before INCIDENTS & NEWS). `App.jsx` panel + `shellUrlState.js` `tab=investigate`. Keep FORGE. |
| Canvas | New `frontend/src/components/investigate/InvestigateGraph.jsx` (or equivalent). Full viewport; not `InvestigationPanel.jsx`. |
| Search | Debounced `GET /api/investigations/resolve?q=` then `.../relationships`. No `POST /api/ioc/lookup` on each keystroke. |
| Expand | On node click, GET relationships for that node; merge nodes/edges by `node_id` / `edge_id`. Honor `truncated`. |
| Visual honesty | Distinct stroke per `edge_class`; stale/partial copy; never draw missing hops as empty space without a gap state. |
| Motion | Client-only (e.g. existing force-layout / canvas). No layout coordinates from API. |
| Pin thread | Overlay may still pin from graph nodes; do not replace the canvas with the pin list. |

P1 still forbids: graph database, “expand everything”, LLM-generated edges, auto-block from a hop.

## Explicitly not P0

| Idea | Why wait |
|------|----------|
| INVESTIGATE tab / Obsidian canvas | Needs this API in production first |
| Persistent cases, notes, sharing | Single-operator; pin PDF already exists |
| Actor/malware as resolve roots | No durable identity |
| Saved-query alerts, STIX | After semantics stabilize |
| Graph DB | Only if measured Postgres expand misses latency |

## Decision gates (keep)

- Do not add a graph database unless bounded Postgres expansion fails agreed latency on representative data.
- Do not merge source claims on display-name equality.
- Do not treat semantic similarity as fact or scoring input.
- Do not auto-block or auto-patch from a relationship lacking current evidence, confidence, and freshness.

## Risks (P0)

| Risk | Mitigation |
|------|------------|
| Projection becomes a slow god-query | Caps, depth 1 default, reuse indexed paths |
| Graph UI later assumes coordinates / unlimited hops | Frozen JSON has no x/y; truncation required |
| Edges look more certain than sources | Distinct `edge_class` |
| Second source of truth | Prefer Tasks 1–4; Task 5 only if provenance is missing |

## Verification (P0 done)

- [ ] `cd backend && pytest tests/test_investigation_contracts.py tests/test_investigation_resolve.py tests/test_investigation_projection.py tests/test_investigation_routes.py tests/test_router_split.py -q`
- [ ] `./scripts/verify-local.sh`
- [ ] Resolve + entity + relationships require analyst session
- [ ] Responses are graph-shaped (`nodes`, `edges`), cap, set `truncated`
- [ ] No frontend graph; no Header tab; no Alembic 041 unless Task 5 unblocked
- [ ] `PRODUCT_STATUS.md`: bounded investigation graph GETs exist; INVESTIGATE canvas not shipped; cases still session-only

## Recommendation

P0 is the **graph data plane**. P1 is the **graph browser**. Shipping canvas first would animate incomplete or outbound-enrichment data. Shipping APIs with a list-shaped payload would force a breaking change when the tab lands. This order freezes nodes/edges/resolve now so INVESTIGATE can be a later, full-canvas UI without touching FORGE or pretending the pin overlay is a graph.
