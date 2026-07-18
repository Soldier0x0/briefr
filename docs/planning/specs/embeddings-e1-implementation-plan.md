# Embeddings E1 — implementation plan

**Status:** Active (maintainer go 2026-07-18)  
**Design:** [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md)  
**Parent backlog:** [`BACKLOG.md`](../BACKLOG.md) §14 · Sprint execution queue

## Scope (this PR only)

| In | Out (later PRs) |
|----|-----------------|
| Swap local/CI/dev images → `pgvector/pgvector:pg16` | Embed pipeline writes pgvector (**E2**) |
| Prod cutover docs → `pgvector/pgvector:pg16` (same major as prod) | Hybrid / related ANN API (**E3**) |
| Alembic `032`: `CREATE EXTENSION vector` + `embeddings` table | UI one-box (**E4**) |
| Migrate existing `cve_embeddings` BLOBs → `embeddings.embedding` | Search token (**E5**) |
| SQLite BLOB shim table for dual-DB tests | Technique rows (**E6**) |
| Docs: POSTGRES, PRODUCT_STATUS, SYSTEM_DESIGN, OPERATIONS, HANDOVER | Prod image swap on the live box |

**Locks:** Do **not** swap production `/opt/infra/postgres` image in this PR — document the cutover only. Legacy `cve_embeddings` stays for one release (read-fallback); do not drop.

## Acceptance

1. Fresh `postgres-dev.sh` / compose / CI Postgres has `vector` in `pg_available_extensions`.
2. `alembic upgrade head` creates `embeddings` with `vector(384)` + HNSW partial index.
3. Pre-existing `cve_embeddings` rows with `dim=384` land in `embeddings` (`entity_type='cve'`).
4. Migrated rows carry placeholder `content_hash` (`migrated:…`); E2 recomputes real hashes.
5. SQLite `init_db` creates a BLOB `embeddings` table (no pgvector type).
6. `./scripts/verify-local.sh` green; Postgres marker tests pass when pgvector image is up.
7. Runtime docs updated; design status → **Accepted / E1 shipping**.

## Files

- `deploy/docker-compose.postgres.yml`, `scripts/postgres-dev.sh`, `.github/workflows/backend-tests.yml`
- `backend/alembic/versions/032_embeddings_pgvector.py`
- `backend/db/init.py` (SQLite shim)
- `backend/tests/test_embeddings_pgvector_e1.py`
- Docs listed above + SPRINT / BACKLOG activation

## Follow-on

**E2** — write path to `embeddings` + `content_hash` of rich CVE text; keep `EMBEDDINGS_ENABLED`; optional `EMBEDDINGS_PGVECTOR` or imply when extension present.
