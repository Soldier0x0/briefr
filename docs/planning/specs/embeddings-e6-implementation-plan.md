# Embeddings E6 — MITRE technique embeddings

**Design:** [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md) §5 / §13

## Acceptance

- [x] `entity_type=technique` in `embeddings` (no schema rewrite)
- [x] Scheduler embeds techniques with CVE backfill
- [x] Hybrid search returns typed technique hits
- [x] Tests + docs
