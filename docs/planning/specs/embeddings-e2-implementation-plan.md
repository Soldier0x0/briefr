# Embeddings E2 — implementation plan

**Status:** Shipping (this PR)  
**Design:** [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md) §5–6  
**Depends on:** E1 (#671) — `embeddings` table + pgvector extension

## Scope

| In | Out |
|----|-----|
| Rich CVE embed text (description + summary + products + CWEs) | ANN related / hybrid search (**E3**) |
| `content_hash = sha256(text + '\\n' + model)` | UI (**E4**) |
| Dual-write: `embeddings` + legacy `cve_embeddings` | Search token (**E5**) |
| Backfill selects missing **or** `migrated:` placeholder | Drop legacy table |
| Auto-on-ingest also re-embeds on hash mismatch for filtered IDs | |
| `EMBEDDINGS_PGVECTOR` (default **1**) to disable dual-write | |

## Acceptance

1. With `EMBEDDINGS_ENABLED=1`, backfill writes both tables; `embeddings.content_hash` is a real sha256 (not `migrated:`).
2. Rows with `migrated:` placeholders are re-selected until re-embedded (capped by `EMBEDDINGS_MAX_PER_RUN`).
3. `EMBEDDINGS_PGVECTOR=0` → legacy-only writes.
4. Related CVE path unchanged (still NumPy over `cve_embeddings`).
5. Tests green; docs updated.

## Operator note (prod after E1)

~23k `migrated:` rows will re-embed over successive scheduler runs (2000/run default). No image change required.
