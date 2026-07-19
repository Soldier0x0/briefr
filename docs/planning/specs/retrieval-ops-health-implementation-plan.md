# Retrieval ops health + auto-on-ingest — Implementation Plan

> **Status:** Implemented on `cursor/retrieval-ops-health-design-0ece` (commits through Gemini fix pass). Remaining: maintainer browser-verify + merge.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Admin honest retrieval health for the live `embeddings` index, and make auto-on-ingest **default on** (with a real off switch) when embeddings are enabled — without breaking keyword fallback.

**Architecture:** RH-1 adds a cheap admin health API + fixes the AI ops count to use `embeddings`, plus a thin Admin panel. RH-2 promotes auto-on-ingest knobs into `config_schema`, flips the runtime default to on, and couples Admin enable (`EMBEDDINGS_ENABLED` 0→1) to set auto-on-ingest=1. No request-path model load; no Admin UI for `EMBEDDINGS_PGVECTOR`.

**Tech Stack:** FastAPI admin router, `db/embeddings_store.py`, AI ops overview, React Admin (`AiOperationsPage`), `config_schema` + `POST /api/admin/config`, pytest.

**Spec:** [`retrieval-ops-health-design.md`](retrieval-ops-health-design.md)

## Global Constraints

- Live index truth = multi-entity **`embeddings`** table (not legacy `cve_embeddings` alone).
- `EMBEDDINGS_ENABLED` remains opt-in default **`0`** (master kill).
- `EMBEDDINGS_AUTO_ON_INGEST` default becomes **`1`** (on); effective ingest-tail still requires `EMBEDDINGS_ENABLED=1`.
- `EMBEDDINGS_PGVECTOR` stays env-only; do not add to Admin UI.
- Caps stay: ingest max default 25, backfill max default 2000.
- Keyword fallback + FEED status labels unchanged.
- No RAG, ranking sliders, or request-path bulk embed.
- Merge gate: `./scripts/verify-local.sh` (at least pytest subset + `npm run build`).
- Docs in same PR when behavior changes (`PRODUCT_STATUS`, `API_REFERENCE`, HANDOVER/SPRINT).
- Branch pattern: `cursor/<task>-0ece`. Design tokens / Radix rules apply to any new Admin UI.

## File structure

| Path | Responsibility |
|------|----------------|
| `backend/db/embeddings_store.py` | Counts by `entity_type`; pending estimates; optional extension probe helper |
| `backend/services/retrieval_health.py` (new) | Build health payload (flags, counts, pending, last backfill, degraded) |
| `backend/routers/admin.py` | `GET /retrieval/health`; storage table list; config GET fields; enable coupling in `set_config` / `apply_all_config` |
| `backend/db/ai_operations.py` | `count_embeddings_by_entity` (or replace overview count source) |
| `backend/ai/operations_admin.py` | Overview payload uses live index count (+ optional legacy) |
| `backend/ml/embeddings.py` | Default `EMBEDDINGS_AUTO_ON_INGEST` → `"1"` |
| `backend/config_schema.py` | New fields for auto-on-ingest + ingest max |
| `backend/.env.example` | `EMBEDDINGS_AUTO_ON_INGEST=1` |
| `backend/db/explorer_registry.py` | Allowlist `embeddings` table |
| `frontend/src/pages/admin/catalog.js` | Job copy: CVE + technique + campaign |
| `frontend/src/pages/admin/AiOperationsPage.jsx` | Retrieval health panel |
| `frontend/src/api.js` (or adminApi usage) | Fetch health |
| `backend/tests/test_retrieval_health.py` (new) | Health + counts + coupling + default |
| Docs | `API_REFERENCE`, `PRODUCT_STATUS`, `HANDOVER`, `SPRINT_2026-07` |

---

### Task 1: Count live `embeddings` by entity_type

**Files:**
- Modify: `backend/db/embeddings_store.py`
- Modify: `backend/db/ai_operations.py` (or call store from admin overview)
- Modify: `backend/ai/operations_admin.py`
- Modify: `backend/routers/admin.py` (overview handler)
- Test: `backend/tests/test_retrieval_health.py`

**Interfaces:**
- Produces: `async def count_embeddings_by_entity(db, model: str) -> dict[str, int]` returning keys `cve`, `technique`, `campaign`, `total`
- Produces: overview `features.embeddings.vector_count` = `total` from `embeddings`; optional `legacy_cve_embeddings` secondary

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_retrieval_health.py
import pytest
from db.embeddings_store import count_embeddings_by_entity, upsert_cve_embedding_row
from db.embeddings_pgvector import DEFAULT_EMBEDDING_DIMS
from ml.embeddings import vector_to_blob, l2_normalize
import numpy as np

MODEL = "BAAI/bge-small-en-v1.5"

@pytest.mark.asyncio
async def test_count_embeddings_by_entity(tmp_path, monkeypatch):
    # use existing test DB fixture pattern from test_embeddings_e2.py
    ...
    counts = await count_embeddings_by_entity(db, MODEL)
    assert counts["cve"] >= 1
    assert counts["total"] == counts["cve"] + counts["technique"] + counts["campaign"]
```

- [ ] **Step 2: Run test — expect FAIL** (`count_embeddings_by_entity` missing)

```bash
cd backend && python -m pytest tests/test_retrieval_health.py::test_count_embeddings_by_entity -q
```

- [ ] **Step 3: Implement count helper**

```python
async def count_embeddings_by_entity(db: DbConnection, model: str) -> dict[str, int]:
    rows = await db.execute_fetchall(
        "SELECT entity_type, COUNT(*) AS cnt FROM embeddings WHERE model = ? GROUP BY entity_type",
        (model,),
    )
    # Postgres: use $1 placeholder via existing _is_postgres_connection branch
    out = {"cve": 0, "technique": 0, "campaign": 0, "total": 0}
    for row in rows:
        et = row["entity_type"]
        n = int(row["cnt"])
        if et in out:
            out[et] = n
        out["total"] += n
    return out
```

- [ ] **Step 4: Wire AI ops overview** to pass `embeddings_vector_count=counts["total"]` and include `legacy_cve_embeddings` via existing `count_cve_embeddings` if cheap.

- [ ] **Step 5: Tests pass; commit**

```bash
cd backend && python -m pytest tests/test_retrieval_health.py tests/test_ai_operations_admin.py -q
git add backend/db/embeddings_store.py backend/db/ai_operations.py backend/ai/operations_admin.py backend/routers/admin.py backend/tests/test_retrieval_health.py
git commit -m "fix(admin): AI ops embeddings count uses live embeddings table"
```

---

### Task 2: `GET /api/admin/retrieval/health`

**Files:**
- Create: `backend/services/retrieval_health.py`
- Modify: `backend/routers/admin.py`
- Modify: `backend/tests/test_retrieval_health.py`
- Modify: `docs/API_REFERENCE.md`

**Interfaces:**
- Produces: `async def build_retrieval_health(db) -> dict`
- Route: `GET /api/admin/retrieval/health` (same admin auth as other admin routes)

Payload keys (exact):

```python
{
  "embeddings_enabled": bool,
  "auto_on_ingest": bool,
  "pgvector_writes": bool,
  "model": str,
  "extension_vector": "present" | "absent" | "n/a",
  "counts": {"cve": int, "technique": int, "campaign": int, "total": int},
  "pending": {"cve": int, "technique": int, "campaign": int},  # capped estimates OK
  "last_backfill": {
      "last_run_utc": str | None,
      "records_upserted": int | None,
      "had_error": bool | None,
      "error_message": str | None,
  },
  "degraded": {"reason": str} | None,  # disabled | no_vector_extension | cold_index | None
}
```

- [ ] **Step 1: Failing test** — unauthenticated 401/403; authenticated returns keys above; with `EMBEDDINGS_ENABLED=0` → `degraded.reason == "disabled"`.

- [ ] **Step 2: Implement `build_retrieval_health`**
  - Flags from `ml.embeddings` + `embeddings_pgvector_writes_enabled`
  - Extension: Postgres `SELECT 1 FROM pg_extension WHERE extname='vector'`; SQLite → `"n/a"`
  - Counts: Task 1 helper
  - Pending: `len(await get_cves_needing_embeddings(db, model, limit=500))` (and tech/camp) as estimate — document as capped
  - Last backfill: reuse `_get_job_last_run(db, "embeddings_backfill")` pattern from admin.py
  - Degraded: disabled; or Postgres and extension absent; or enabled and `counts["total"]==0` → `cold_index`

- [ ] **Step 3: Register route on admin router** (prefix already `/api/admin`).

- [ ] **Step 4: Document in `API_REFERENCE.md`**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(admin): GET /api/admin/retrieval/health"
```

---

### Task 3: Storage + explorer + catalog copy

**Files:**
- Modify: `backend/routers/admin.py` (`_STORAGE_TABLES` add `"embeddings"`)
- Modify: `backend/db/explorer_registry.py`
- Modify: `frontend/src/pages/admin/catalog.js`
- Test: existing explorer/storage tests if any; add assertion embeddings allowlisted

- [ ] **Step 1: Add explorer spec**

```python
_spec(
    "embeddings",
    1,
    "Embeddings index",
    ("entity_type", "entity_id", "model", "dims", "content_hash", "updated_at"),
    filter_columns=("entity_type", "entity_id", "model"),
    order_by="updated_at DESC, entity_type ASC, entity_id ASC",
),
```

Do **not** expose the vector column in explorer.

- [ ] **Step 2: Update catalog.js**

```javascript
embeddings_backfill: {
  label: 'Semantic search index',
  short: 'Embeddings',
  operatorName: 'Embeddings Backfill (CVE / technique / campaign)',
  analystDescription: 'Builds the hybrid search index for CVEs, MITRE techniques, and campaigns.',
  refreshButton: 'Rebuild search index',
},
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(admin): expose embeddings table; fix backfill catalog copy"
```

---

### Task 4: Admin UI — retrieval health panel

**Files:**
- Modify: `frontend/src/pages/admin/AiOperationsPage.jsx`
- Possibly: `frontend/src/api.js` if a helper is cleaner
- Follow design-system tokens (no hardcoded colors)

- [ ] **Step 1: Fetch** `adminApi.get('/retrieval/health')` on Overview mount (four states: loading skeleton, empty N/A, error+ref, data).

- [ ] **Step 2: Render** compact mono section: enabled / auto / model / extension / counts by entity / pending / last backfill / degraded callout (`--status-error` or warn only when degraded).

- [ ] **Step 3: Show** `vector_count` as live total; if API returns `legacy_cve_embeddings`, show muted secondary line.

- [ ] **Step 4: `npm run build`**

- [ ] **Step 5: Commit** — end of **RH-1**

```bash
git commit -m "feat(admin): retrieval health panel on AI operations"
```

Update `PRODUCT_STATUS` Embeddings row + HANDOVER RH-1 done; tick SPRINT note if present.

---

### Task 5: Auto-on-ingest default on + config schema

**Files:**
- Modify: `backend/ml/embeddings.py` — default `"1"`
- Modify: `backend/.env.example` — `EMBEDDINGS_AUTO_ON_INGEST=1`
- Modify: `backend/config_schema.py` — add fields
- Modify: `backend/routers/admin.py` — include in `_get_config_response()["ml"]`
- Modify: `backend/tests/test_embeddings.py` (auto-on-ingest tests that assumed default 0)
- Modify: `backend/tests/test_retrieval_health.py`

**Interfaces:**
- `embeddings_auto_on_ingest_enabled()` reads default `"1"`
- Still requires `embeddings_enabled()`

```python
ConfigField(
    "EMBEDDINGS_AUTO_ON_INGEST", "ml", "bool",
    help_text="After NVD ingest, embed new/updated CVEs immediately (capped). Default on when unset.",
    display_label="Embeddings auto on ingest",
),
ConfigField(
    "EMBEDDINGS_INGEST_MAX_PER_RUN", "ml", "int", min=1, max=500,
    help_text="Max CVEs embedded in the NVD ingest tail.",
    display_label="Embeddings ingest max per run",
),
```

- [ ] **Step 1: Failing test** — with env deleted, `embeddings_enabled` monkeypatched True → `embeddings_auto_on_ingest_enabled()` is True; with `"0"` → False.

- [ ] **Step 2: Change default in `embeddings.py` and `.env.example`**

- [ ] **Step 3: Fix tests** that set/del env expecting old default 0

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(embeddings): default AUTO_ON_INGEST on; expose in config schema"
```

---

### Task 6: Admin enable coupling (approach B)

**Files:**
- Modify: `backend/routers/admin.py` (`set_config`, `apply_all_config`)
- Optionally small helper: `backend/config_coupling.py` or private `_couple_embeddings_auto_on_enable`
- Test: `backend/tests/test_retrieval_health.py`

**Rule:**
- When a write sets `EMBEDDINGS_ENABLED` to truthy (`1`/`true`/`yes`) and the **previous** effective value was off, and the same request does **not** include an explicit `EMBEDDINGS_AUTO_ON_INGEST` key, also persist `EMBEDDINGS_AUTO_ON_INGEST=1`.
- If the same request sets `AUTO_ON_INGEST=0`, respect that (no override).

```python
def _couple_embeddings_auto_on_enable(
    changed: list[tuple[str, str]],
    *,
    previous_enabled: bool,
) -> list[tuple[str, str]]:
    by_key = {k: v for k, v in changed}
    if "EMBEDDINGS_ENABLED" not in by_key:
        return changed
    new_on = by_key["EMBEDDINGS_ENABLED"].strip().lower() in ("1", "true", "yes")
    if not new_on or previous_enabled:
        return changed
    if "EMBEDDINGS_AUTO_ON_INGEST" in by_key:
        return changed
    return list(changed) + [("EMBEDDINGS_AUTO_ON_INGEST", "1")]
```

- [ ] **Step 1: Tests** for single-key `set_config` and `apply_all_config` batch.

- [ ] **Step 2: Implement** — read previous from `os.environ` before write.

- [ ] **Step 3: Commit** — end of **RH-2** code

```bash
git commit -m "feat(admin): enable embeddings couples auto-on-ingest=1"
```

---

### Task 7: Docs + verify

**Files:**
- `docs/PRODUCT_STATUS.md` — Embeddings row: health endpoint, auto-on-ingest default on, Admin knobs
- `docs/API_REFERENCE.md` — if not fully done in Task 2
- `docs/HANDOVER.md` — newest entry
- `docs/planning/SPRINT_2026-07.md` — note RH-1/RH-2 under E track optional tail
- `docs/planning/specs/retrieval-ops-health-design.md` — Status → Accepted / shipping

- [ ] **Step 1: Docs**

- [ ] **Step 2: Verify**

```bash
cd backend && python -m pytest tests/test_retrieval_health.py tests/test_embeddings.py tests/test_ai_operations_admin.py -q
cd frontend && npm run build
# preferred:
./scripts/verify-local.sh
```

- [ ] **Step 3: `graphify update .`** after code changes

- [ ] **Step 4: Push / update PR / Gemini disposition**

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Health API | Task 2 |
| Counts from `embeddings` | Task 1 |
| Thin Admin panel | Task 4 |
| Storage/explorer | Task 3 |
| Catalog copy | Task 3 |
| Auto default on | Task 5 |
| Config schema knobs | Task 5 |
| Enable coupling B | Task 6 |
| No PGVECTOR in Admin | Global Constraints |
| Caps / keyword fallback unchanged | Global Constraints |
| Docs | Tasks 2, 7 |

No TBD placeholders. RH-1 = Tasks 1–4; RH-2 = Tasks 5–7 (docs may split per PR if preferred — single branch OK if verify stays green).
