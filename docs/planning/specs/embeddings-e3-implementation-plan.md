# Embeddings E3 — related ANN + hybrid search API

**Design:** [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md) §7  
**Depends on:** E1 (table + extension), E2 (rich vectors + content_hash)

## In scope

| Done | Out of scope (later) |
|------|----------------------|
| Related → `embeddings` ANN / BLOB cosine, legacy NumPy fallback | UI one-box (**E4**) |
| `GET /api/search/semantic` hybrid/keyword/semantic | Admin search token (**E5**) |
| Query-shape + RRF + keyword fallback | Technique embeddings (**E6**) |

## Acceptance

- [x] Related uses stored vectors only (no inference)
- [x] `meta.method` still `embeddings` \| `product_heuristic` for related
- [x] Search API documents `meta.method` / `match_reasons`
- [x] SQLite CI: keyword + embeddings-table cosine; ANN SQL Postgres-gated
- [x] Docs: API_REFERENCE, PRODUCT_STATUS, HANDOVER, SPRINT, BACKLOG

## Operator

No Postgres image change. After merge, `briefr-update.sh` only. ANN quality
improves as E2 re-embeds `migrated:` rows.
