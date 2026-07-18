# Embeddings E5 — Admin search service token

**Design:** [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md) §8

## Acceptance

- [x] bcrypt (not bare SHA) at rest; plaintext show-once
- [x] Bearer `briefr_search_…` for allowlisted GET routes only
- [x] Dedicated rate-limit bucket
- [x] Admin create/list/revoke + audit
- [x] Docs + tests
