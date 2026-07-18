# Embeddings E4 — UI one-box hybrid

**Design:** [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md) §9  
**Depends on:** E3 (`GET /api/search/semantic`)

## In scope

| Done | Out of scope |
|------|----------------|
| FEED search → hybrid API (default) | Mode toggle chrome |
| Quiet keyword-fallback status | Admin search token (**E5**) |
| Keep `/api/cves` when list filters need server fields | Technique typed hits (**E6**) |

## Acceptance

- [x] One search box; no Keyword\|Semantic toggle
- [x] Cold/disabled semantic → keyword path still shows results
- [x] `npm run build` green
