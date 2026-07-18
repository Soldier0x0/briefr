# Retrieval engine E7 — Phase 1 Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkbox steps track progress.

**Goal:** Make hybrid search the default retrieval path with stack filters and fresh CVE embeddings.

**Architecture:** Extend `run_semantic_search` with filter params; widen CVE pending selection for hash drift; relax FEED `shouldUseHybridSearch` for stack; add golden-query contract tests.

**Tech Stack:** FastAPI, pgvector/SQLite embeddings table, React FEED (`CVEFeed` / `hybridFeedSearch.js`).

## Global Constraints

- Retrieval only — no RAG.
- Keep one FEED search box (no Keyword|Semantic toggle).
- Postgres-native SQL with SQLite test fallback; run dual DB when touching `db/`.
- Do not enable `EMBEDDINGS_ENABLED=1` by force in code — document ops cutover; filters must work either way.

---

### Task 1: CVE embedding freshness (content_hash drift)

**Files:**
- Modify: `backend/db/embeddings_store.py`
- Test: `backend/tests/test_embeddings_e2.py` (or new `test_embeddings_e7_freshness.py`)

- [x] Pending CVE query fills missing/`migrated:` first, then scans oldest existing embeds for hash mismatch via `_row_to_pending`
- [x] Test: upsert embed → change description text → pending includes that CVE
- [x] Commit

### Task 2: Semantic API filters (stack / severity / kev)

**Files:**
- Modify: `backend/routers/search.py`, `backend/services/semantic_search.py`
- Test: `backend/tests/test_embeddings_e7_filters.py`
- Docs: `docs/API_REFERENCE.md`

- [x] Query params: `stack`, `severity`, `kev_only`
- [x] After hydrate, restrict CVE hits; `meta.stack_terms` / filter flags
- [x] Tests for stack narrowing
- [x] Commit

### Task 3: FEED keeps hybrid with stack

**Files:**
- Modify: `frontend/src/utils/hybridFeedSearch.js`, `frontend/src/api.js`, `frontend/src/components/CVEFeed.jsx`
- Test: `frontend/src/utils/hybridFeedSearch.test.js` (node:test)

- [x] `shouldUseHybridSearch` allows `stack` / `my_stack_only`
- [x] Pass `stack` into `fetchSemanticSearch`
- [x] Client severity/KEV filter remains as defense in depth
- [x] Commit

### Task 4: Golden eval foundation + sprint docs

**Files:**
- Create: `backend/tests/fixtures/retrieval_golden_queries.json`
- Create: `backend/tests/test_retrieval_golden.py`
- Modify: `docs/planning/SPRINT_2026-07.md`, `docs/PRODUCT_STATUS.md`, `docs/HANDOVER.md`

- [x] Fixture of paraphrase / CVE-ID / short shapes (contract-level asserts)
- [x] Tick E7 Phase 1 items in SPRINT
- [x] Commit

### Task 5 (follow-up PR): Campaigns entity_type

Out of Phase 1 — see design Phase 2.
