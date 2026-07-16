# Embeddings, pgvector & hybrid search — design

**Status:** Design — awaiting maintainer review before implementation plan  
**Created:** 2026-07-16  
**Audience:** Implementers (Cursor agents / maintainers)

**Goal:** One retrieval engine for **humans and agents**: local embeddings, **pgvector** in existing Postgres 16, **hybrid** search (vector + `pg_trgm`), related-CVE upgrade, and a scoped Admin-managed search API token — without a separate vector database.

**Related:** Existing V1.3 path in `backend/ml/embeddings.py` + `cve_embeddings` (BLOB + NumPy). Durable jobs: [`durable-outbound-queue-and-stack-backfill.md`](durable-outbound-queue-and-stack-backfill.md) (Procrastinate) — embedding backfill may later run as a Procrastinate task; v1 may keep APScheduler.

---

## 1. Problem

| Today | Gap |
|-------|-----|
| Optional `fastembed` / `BAAI/bge-small-en-v1.5` | Env-gated; many deploys still off |
| Vectors as BLOBs; related = brute-force NumPy | Fine at ~25k; not ANN; no shared search API |
| Feed search = keyword / `pg_trgm` | No semantic / paraphrased incident search |
| No first-class agent retrieval | Scripts/IDE agents lack a scoped, documented tool |
| Prod Postgres 16 image | **`vector` extension not available** (`pg_available_extensions` empty for `vector`) |
| `pg_trgm` 1.6 | Already installed — keep for hybrid keyword side |

Prod evidence (2026-07-16): PostgreSQL 16.14; `pg_trgm` installed; `unaccent` available unused; **`vector` absent** → image must become pgvector-capable at feature deploy (not during design).

---

## 2. Goals / non-goals

### Goals

- **A** Human semantic/hybrid search (one search box)  
- **B** Better related CVEs via pgvector  
- **C** Agent retrieval via same API + **search service token** (C-full)  
- Stay **self-hosted**, CPU-local embeddings, **no Redis/Qdrant**  
- **Future-proof:** multi-entity schema; model name swappable; techniques next slice  

### Non-goals (this design)

- Remote embedding APIs as default  
- Replacing Postgres with a dedicated vector product  
- Enabling `unaccent` in v1 (optional later)  
- Full RAG chat UI / LLM answer synthesis (retrieval only)  
- Re-embedding entire corpus on every schedule tick  

---

## 3. Locked decisions

| Topic | Decision |
|-------|----------|
| Architecture | Single retrieval engine; UI + agents are clients |
| Storage | **pgvector inside existing BRIEFR Postgres** |
| PG version | **16** (prod confirmed); use `pgvector/pgvector:pg16` (pin tag at implement) |
| Image cutover | **With feature deploy**, not during design; backup + **same volume** |
| Corpus v1 | **CVE-rich** text (description + summary + products/CWE signals) |
| Corpus next | **MITRE techniques** in same table (same program, next PR after CVE path green) |
| Schema | Multi-entity from day one: `(entity_type, entity_id, model, …)` |
| Model | Keep **`BAAI/bge-small-en-v1.5`**; `EMBEDDINGS_MODEL` swappable; model change ⇒ one-time re-embed |
| Search UX | **Hybrid** under one box (no default Keyword\|Semantic toggle) |
| API | `mode=hybrid\|keyword\|semantic`; query-shape boosts (CVE id / short query → keyword-heavy) |
| Agent auth | Admin UI token; **hash at rest**; show-once; rate-limited |
| Token scope | Hybrid/semantic search + related + **read-only CVE detail** |
| Inference | Scheduler / job only — **never** model load on request path |
| Extensions | Must add `vector`; keep `pg_trgm`; defer `unaccent` |

---

## 4. Architecture

```text
                    ┌─────────────────┐
  Analyst UI ──────►│  Auth: session  │──┐
                    └─────────────────┘  │
                    ┌─────────────────┐  │    ┌──────────────────────────┐
  Agent / script ──►│ Auth: search    │──┼───►│ Retrieval service         │
                    │ token (hashed)  │  │    │ hybrid | keyword | vector │
                    └─────────────────┘  │    └────────────┬─────────────┘
                                         │                 │
                                         │         ┌───────┴────────┐
                                         │         │ Postgres 16    │
                                         │         │ pg_trgm +      │
                                         │         │ pgvector       │
                                         │         │ embeddings[]   │
                                         │         └───────▲────────┘
                                         │                 │
                    ┌─────────────────┐  │    ┌────────────┴─────────────┐
  Scheduler/jobs ───►│ Embed pipeline  │──┘    │ fastembed bge-small      │
                    │ (no request)    │       │ worker thread / job      │
                    └─────────────────┘       └──────────────────────────┘
```

**Request path:** embed query text (lightweight) + SQL ANN / trigram — **no** bulk model backfill on request.  
**Write path:** backfill / ingest / content-hash change / model change jobs only.

---

## 5. Data model

### 5.1 New / evolved table: `embeddings`

Prefer a new first-class table (migrate from `cve_embeddings` BLOBs):

```text
embeddings (
  entity_type   TEXT NOT NULL,             -- 'cve' | 'technique' | …
  entity_id     TEXT NOT NULL,             -- CVE-… or Txxxx
  model         TEXT NOT NULL,             -- e.g. BAAI/bge-small-en-v1.5
  dims          INT  NOT NULL,             -- 384 for bge-small (informational)
  embedding     vector(384) NOT NULL,      -- pgvector requires fixed dims at column DDL
  content_hash  TEXT NOT NULL,             -- hash of embedded source text
  updated_at    TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (entity_type, entity_id, model)
)

-- ANN index (HNSW cosine) for active model queries
-- CREATE INDEX … ON embeddings USING hnsw (embedding vector_cosine_ops)
--   WHERE entity_type = 'cve' AND model = '<active>';
```

**Notes:**

- pgvector columns need a **compile-time dimension** (e.g. `vector(384)`). Switching to bge-base (768) ⇒ new column/table or migration that replaces the vector column — document as part of model-upgrade runbook; do not pretend `vector(dims)` is dynamic SQL.  
- Timestamps **TIMESTAMPTZ**.  
- SQLite tests: keep a **BLOB fallback** or skip pgvector tests under Postgres-only marker (same dual-DB rule as Procrastinate).  
- Legacy `cve_embeddings`: migrate then drop or leave read-fallback one release.

### 5.2 CVE embed text (v1 “rich”)

Deterministic concatenation (cap ~2000 chars, match today’s `EMBED_TEXT_MAX_CHARS` unless raised carefully):

1. Description  
2. Summary (if present)  
3. Affected products (joined)  
4. CWE ids (joined)  

`content_hash = sha256(normalized_text + '\n' + model)` so model change invalidates naturally.

### 5.3 Technique rows (slice 2)

`entity_type = 'technique'`, text = name + description (+ tactic label). Same model/index pattern; API returns typed hits.

---

## 6. Embedding pipeline

| Trigger | Behavior |
|---------|----------|
| First enable / empty index | Backfill missing CVEs, capped per run (`EMBEDDINGS_MAX_PER_RUN`) |
| Interval job (default 6h) | Only missing or `content_hash` mismatch |
| Auto-on-ingest | Bounded batch of new/updated CVE ids |
| `EMBEDDINGS_MODEL` change | New model key; backfill under new model; cut over search `model=` when coverage threshold met; delete/orphan old model rows later |
| Technique ATT&CK refresh | Re-embed changed technique texts (slice 2) |

**Resources (steady state):** inference **not** continuous — periodic spikes; model may stay resident in process (~100–250 MB RSS for small). Full corpus embed is **one-time** (or on model change), not daily.

**Feature flags:** keep `EMBEDDINGS_ENABLED`; add `EMBEDDINGS_PGVECTOR=1` or imply pgvector when migration applied + extension present.

---

## 7. Retrieval API

### 7.1 Search

`GET /api/search/semantic` (name final at implement; document in `API_REFERENCE.md`)

| Param | Meaning |
|-------|---------|
| `q` | Query text |
| `mode` | `hybrid` (default) \| `keyword` \| `semantic` |
| `limit` | top_k (capped) |
| filters | severity, kev, stack — reuse existing filter vocabulary where possible |

**Hybrid merge:** run keyword (`pg_trgm` / existing CVE search SQL) and vector ANN in parallel; merge (RRF or weighted).  

**Query-shape rules:**

- Matches `CVE-\d{4}-\d+` → keyword-first (vector optional)  
- 1–2 tokens → keyword-heavy hybrid  
- Long natural language → balanced / vector-heavier hybrid  

**Response (honest):** `results[]` with `entity_type`, `entity_id`, `score`, `match_reasons[]` (`keyword`, `vector`), plus CVE card fields as needed.

**Fallback:** embeddings disabled / extension missing / cold index → keyword-only; `meta.method` reports path (same spirit as today’s related `meta.method`).

### 7.2 Related

Upgrade `GET /api/cves/{id}/related` to pgvector kNN on that CVE’s vector; keep shared-product heuristic fallback.

### 7.3 CVE detail (token scope)

Existing read-only detail (or drawer-safe subset) allowed for search token so agents can hydrate hits.

---

## 8. Auth: search service token (C-full)

| Property | Design |
|----------|--------|
| Create / revoke | **Admin UI only** (API keys / security surface) |
| Storage | **HMAC/SHA-256 hash only** — plaintext shown **once** at create |
| Scope | `search:semantic`, `cves:related`, `cves:read` (names illustrative) |
| Transport | `Authorization: Bearer …` or `X-BRIEFR-Search-Token` (pick one; document) |
| Rate limit | Dedicated bucket (stricter than interactive user) |
| Audit | `last_used_at`; optional meter via outbound… N/A — these are **inbound** calls; use existing inbound rate-limit + audit_log on create/revoke |

Humans continue using normal session/JWT. Same handlers resolve identity → call shared retrieval service.

---

## 9. UI

- **One search box** — hybrid by default; no Keyword\|Semantic toggle in v1 chrome.  
- Optional later: advanced “keyword only” or show `match_reasons` on results.  
- Drawer **Related** uses upgraded endpoint.  
- Empty/cold semantic: silent keyword fallback or quiet status — never blank error if keyword works.

---

## 10. Deploy / ops (Postgres 16 + pgvector)

### 10.1 Images

| Env | Today | Target |
|-----|-------|--------|
| Prod `/opt/infra/postgres` | Image **without** `vector` | `pgvector/pgvector:pg16` (pin digest/tag) |
| `deploy/docker-compose.postgres.yml` | `postgres:16-alpine` | pgvector pg16 |
| `scripts/postgres-dev.sh` / CI | `postgres:16-alpine` | pgvector pg16 |

### 10.2 Cutover sequence (prod) — **with feature deploy, not during design**

1. Backup (`pg_dump` / existing backup job)  
2. Stop container; set image to pgvector pg16; **same volume mounts**  
3. Start; verify `SELECT version()`, CVE count  
4. `CREATE EXTENSION IF NOT EXISTS vector` (Alembic)  
5. App migrate BLOB → `embeddings.embedding`  
6. Backfill gaps; enable hybrid search flags  
7. Smoke: health, feed, semantic search, related  

**Data loss:** not inherent to extension or pgvector; risk is wrong volume on recreate — backup + same volume name mitigate.

### 10.3 Other extensions

- `pg_trgm` — already installed; required for hybrid  
- `unaccent` — available, not installed; out of v1  
- Do not add PostGIS / Timescale / etc. for this program  

---

## 11. Error handling / isolation

| Failure | Behavior |
|---------|----------|
| No `vector` extension | Keyword path; admin/health hint “pgvector not ready” |
| Model not downloaded | Job error; search falls back |
| Partial backfill | Related/search degrade gracefully |
| Token invalid | 401; no session confusion |
| Bad hybrid ranking | Tunable weights + API `mode=` escape hatch |

Must not break feed when embeddings disabled (current contract).

---

## 12. Testing

| Layer | What |
|-------|------|
| Unit | content_hash, merge/RRF, query-shape router, token hash verify |
| Postgres | extension present; HNSW query; hybrid SQL — **Postgres required** |
| SQLite CI | skip pgvector or shim; keyword path still tested |
| API | mode flags; token scope denial for admin routes |
| Browser | one-box hybrid; related drawer |
| Merge gate | `./scripts/verify-local.sh`; `--full` with pgvector image |

---

## 13. PR sequence (suggested — detail in implementation plan)

| PR | Scope |
|----|--------|
| **E1** | Dev/CI/prod docs: pgvector pg16 image; Alembic `CREATE EXTENSION vector`; `embeddings` table; migrate from `cve_embeddings` |
| **E2** | Embed pipeline writes pgvector; backfill/hash; keep flags |
| **E3** | Related + hybrid search API; query-shape + fallbacks |
| **E4** | UI one-box hybrid wiring |
| **E5** | Admin search token (hash, show-once, rate limit) |
| **E6** | MITRE technique embeddings + typed search hits |

Optional: wire backfill to Procrastinate after Q1 lands.

---

## 14. Approaches considered

| # | Approach | Verdict |
|---|----------|---------|
| 1 | pgvector in-Postgres + hybrid API + thin clients | **Chosen** |
| 2 | Keep BLOB+NumPy only | Rejected — not agent/future-proof |
| 3 | External vector DB | Rejected — extra infra |

---

## 15. Open questions (minor — defaults below)

| # | Question | Default if unanswered |
|---|----------|------------------------|
| 1 | Exact search route path (`/api/search/semantic` vs extend `/api/cves`) | Dedicated semantic route + keep list API for filters |
| 2 | HNSW vs IVFFlat | **HNSW** cosine for ≤100k–few×100k rows |
| 3 | Show `match_reasons` in UI v1 | API yes; UI optional tooltip later |
| 4 | Token header name | `Authorization: Bearer` with token prefix `briefr_search_` |

---

## 16. Success criteria

- [ ] Prod/dev on pg16+pgvector; `vector` installed  
- [ ] CVE embeddings in pgvector; related uses ANN  
- [ ] Human hybrid search works with keyword fallback  
- [ ] Agent token can search + related + CVE detail only  
- [ ] Model change documented as one-time re-embed  
- [ ] Technique slice designed; shipped as E6 without schema rewrite  
- [ ] Docs: `PRODUCT_STATUS`, `API_REFERENCE`, `POSTGRES`, `SYSTEM_DESIGN`  

---

## 17. Activation

1. Maintainer reviews **this design**  
2. Implementation plan via writing-plans (checkbox PR tasks)  
3. Do **not** swap prod image until E1 deploy  
4. Link from BACKLOG + SPRINT when activated  

**Out of scope link:** stack Tier-A backfill / Procrastinate — separate program; complementary (more CVEs to embed over time).
