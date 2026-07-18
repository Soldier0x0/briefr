# Retrieval engine productization + multi-entity growth (E7+)

**Status:** Accepted (maintainer 2026-07-18) — proceed from brainstorming  
**Parent design:** [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md)  
**Implementation plan:** [`retrieval-engine-e7-implementation-plan.md`](retrieval-engine-e7-implementation-plan.md)

## Intent

Productize the existing hybrid/pgvector stack into BRIEFR’s **default retrieval
engine** (humans + agents), then grow the corpus by `entity_type` — **retrieval
only, no RAG / no answer synthesis**.

## Locked decisions

| Topic | Decision |
|-------|----------|
| Scope | Approach A + multi-entity growth; no LLM chat |
| Default | Hybrid is the normal FEED path when search is set |
| Filters | Stack / severity / KEV must not force-abandon hybrid |
| Freshness | Scheduled CVE backfill re-embeds on `content_hash` drift |
| Quality | Golden-query eval gate; similarity floor (follow-up if needed) |
| Next entity after techniques | **Campaigns** (hunt/backlog later, keyword-first) |
| Non-goals | Remote embeds, Qdrant, RAG answers, second vector DB |

## Phase 1 — Productize (this track)

1. **Freshness** — CVE pending selection includes content_hash mismatch (not only missing/`migrated:`).
2. **Stack-aware hybrid** — `GET /api/search/semantic` accepts `stack` (+ severity/kev); FEED keeps hybrid when My Stack is active.
3. **Eval foundation** — golden query fixtures + pytest that merge/shape/filter contracts stay honest.
4. **Ops honesty** — `meta` reports stack filter; status chip unchanged.

## Phase 2 — Grow index (later PRs)

| Order | Entity | Why |
|-------|--------|-----|
| Done / finishing | `technique` | Forge + MITRE pivots |
| Next | `campaign` | Intel similarity over OTX clusters |
| Later | hunt/backlog | Prefer filters unless retrieval gap proven |

## Phase 3 — Consumers

FEED one-box · Drawer Related · Forge · search service token. No new parallel search stacks.

## Acceptance (Phase 1)

- [ ] Typing a stack + NL query still uses hybrid (`meta.method` hybrid/semantic when embeddings on).
- [ ] Editing a CVE description eventually re-queues embed via scheduled backfill.
- [ ] Golden eval tests green in CI (SQLite path).
- [ ] `API_REFERENCE` + `PRODUCT_STATUS` + SPRINT E7 checkbox updated.
