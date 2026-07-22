# AI Ops failure payload capture + manual retry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let self-hosted operators opt in to storing failed LLM request payloads (short TTL), inspect them from AI Operations, and manually retry the same payload — without changing the default metadata-only privacy posture (ADR-AI-5).

**Architecture:** Keep `ai_operations` metadata rows. Add a side table `ai_operation_payloads` (operation_id PK/FK) written only when `AI_OPERATIONS_STORE_FAILURE_PAYLOADS` is on and an attempt fails (empty body or provider exception after HTTP). Admin GET returns payload; Admin POST replays via `chat_completion_task` with stored messages and records a new attempt (link `replay_of_operation_id`). Support pack stays body-free. Feed Health remains circuit state; optional link/copy to AI Ops for `empty` class.

**Tech Stack:** Alembic, FastAPI admin routes, `ai/llm_router.py`, `ai/operations_recorder.py`, React `AiOperationsPage.jsx`, cache retention.

**Spec SSOT:** [`../specs/2026-07-22-ux-ops-rca-collection-design.md`](../specs/2026-07-22-ux-ops-rca-collection-design.md) Program E / decision 8.

## Global Constraints

- Default **off** — metadata-only remains the default (ADR-AI-5).
- Store **failures only**; truncate messages/response (e.g. 32 KiB each).
- Never store API keys; never put payloads in support pack.
- Admin-only endpoints + audit on retry.
- Retention: purge payloads at **7 days** (stricter than 30d `ai_operations`).
- Migrations forward-only.
- Manual retry only — no auto-retry from Feed Health.
- If provider circuit open, retry endpoint returns 409 with actionable detail (“Resume retries on Feed Health”) unless `force=true` admin flag (default false).
- Merge gate: `./scripts/verify-local.sh`.
- Docs: PRODUCT_STATUS, API_REFERENCE, HANDOVER, `.env.example`.

---

### Task 1: Schema + recorder hooks

**Files:**
- Create: `backend/alembic/versions/0XX_ai_operation_payloads.py` (use next free revision after pull)
- Create: `backend/db/ai_operation_payloads.py`
- Modify: `backend/ai/operations_recorder.py` / `backend/ai/llm_router.py` (pass messages on failure)
- Modify: `backend/db/cache_retention.py` (7d purge)
- Modify: `backend/.env.example` (`AI_OPERATIONS_STORE_FAILURE_PAYLOADS=0`)
- Test: `backend/tests/test_ai_operation_payloads.py`

**Interfaces:**
- Produces:

```python
def store_failure_payloads_enabled() -> bool: ...

async def insert_ai_operation_payload(
    db,
    *,
    operation_id: str,
    messages_json: str,
    response_excerpt: str | None,
    task_class: str,
    provider: str,
    model: str,
) -> None: ...
```

Table columns (minimum): `operation_id`, `created_at`, `messages_json`, `response_excerpt`, `task_class`, `provider`, `model`.

- [ ] **Step 1: Failing test — nothing stored when flag off**

```python
@pytest.mark.asyncio
async def test_failure_payload_not_stored_when_flag_off(monkeypatch, tmp_db):
    monkeypatch.setenv("AI_OPERATIONS_STORE_FAILURE_PAYLOADS", "0")
    monkeypatch.setenv("AI_OPERATIONS_RECORD", "1")
    # drive chat_completion_task with mock provider returning ""
    # assert ai_operations row exists with error_class=empty
    # assert no ai_operation_payloads row
```

- [ ] **Step 2: Failing test — stored when flag on**

```python
@pytest.mark.asyncio
async def test_failure_payload_stored_when_flag_on(monkeypatch, tmp_db):
    monkeypatch.setenv("AI_OPERATIONS_STORE_FAILURE_PAYLOADS", "1")
    # empty completion → payload row messages include user text "hello"
```

- [ ] **Step 3: Migration + insert helper + wire router**

On empty content / exception path in `chat_completion_task`, after `record_llm_attempt` returns/`operation_id` known: if flag on, insert payload. Refactor recorder to return `operation_id` from `record_llm_attempt`.

Truncate:

```python
def _truncate(s: str, limit: int = 32_768) -> str:
    return s if len(s) <= limit else s[: limit - 15] + "…[truncated]"
```

Serialize `messages` with `json.dumps`; never include env keys.

- [ ] **Step 4: Retention purge 7d**

Add purge SQL alongside existing `ai_operations` 30d purge.

- [ ] **Step 5: pytest + commit**

```bash
cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_ai_operation_payloads.py -q
git add backend/alembic/versions/ backend/db/ai_operation_payloads.py backend/ai/operations_recorder.py backend/ai/llm_router.py backend/db/cache_retention.py backend/.env.example backend/tests/test_ai_operation_payloads.py
git commit -m "feat(ai): opt-in store failed LLM payloads"
```

---

### Task 2: Admin API — get payload + retry

**Files:**
- Modify: `backend/ai/operations_admin.py` (or `routers/admin/ai_ops.py` — use existing AI ops router module)
- Modify: `backend/routers/admin/…` registration
- Test: `backend/tests/test_ai_operations_admin.py` (extend)
- Docs: `docs/API_REFERENCE.md`

**Interfaces:**
- `GET /api/admin/ai/operations/{operation_id}/payload` → `{ operation_id, messages, response_excerpt, task_class, provider, model, created_at }` or 404
- `POST /api/admin/ai/operations/{operation_id}/retry` → `{ replay_operation_id, success, provider, model, error_class }`  
  Body optional: `{ "force": false }`

- [ ] **Step 1: Failing API tests**

```python
def test_get_payload_404_when_missing(admin_client):
    r = admin_client.get("/api/admin/ai/operations/nope/payload")
    assert r.status_code == 404

def test_retry_replays_stored_messages(admin_client, monkeypatch):
    # seed payload + mock chat_completion_task
    r = admin_client.post(f"/api/admin/ai/operations/{oid}/retry")
    assert r.status_code == 200
    assert r.json()["replay_operation_id"]
```

- [ ] **Step 2: Implement handlers**

Retry loads messages, maps `task_class` → `LLMTask`, calls `chat_completion_task(...)`. On success/failure, normal recording runs (new row). Optionally set `fallback_from_*` unused; store `context_type='replay'`, `context_id=original_operation_id` **or** add column `replay_of_operation_id` on `ai_operations` in same migration if cleaner — prefer `context_type='replay'` + `context_id=original` to avoid second migration if possible.

Audit: `ai.operations.retry`.

- [ ] **Step 3: Circuit open → 409**

```python
if provider_circuit_open(provider) and not force:
    raise HTTPException(409, detail="Provider paused — Resume retries on Feed Health, or pass force=true")
```

- [ ] **Step 4: API_REFERENCE + commit**

```bash
cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_ai_operations_admin.py -q
git add backend/ docs/API_REFERENCE.md backend/tests/test_ai_operations_admin.py
git commit -m "feat(ai): admin payload inspect and manual LLM retry"
```

---

### Task 3: AI Operations UI — inspect + Retry

**Files:**
- Modify: `frontend/src/pages/admin/AiOperationsPage.jsx`
- Modify: admin CSS only if needed (tokens)
- Test: optional small unit for button enablement helper

**Interfaces:**
- Activity row: if `has_payload` (API must expose boolean on activity list — add `has_payload` via LEFT JOIN / exists subquery) show **View payload** + **Retry**
- View: Dialog (Radix) with messages JSON + response excerpt; no card-hero chrome
- Retry: confirm AlertDialog → POST → toast success/fail + refresh list

- [ ] **Step 1: Extend activity API with `has_payload: bool`**
- [ ] **Step 2: UI wiring**

HelpTip update: “Metadata always; failure bodies only when AI_OPERATIONS_STORE_FAILURE_PAYLOADS is on.”

- [ ] **Step 3: Feed Health optional one-liner** under Groq-like degraded card when `last_error` is `empty LLM response content`: “See Admin → AI operations (error: empty)” — keep factual, no heartbeat claim. File: `FeedHealthPage.jsx`.

- [ ] **Step 4: build + verify-local + docs + commit**

```bash
cd frontend && npm run build
./scripts/verify-local.sh
# PRODUCT_STATUS: opt-in failure payloads + manual retry; default still no prompts
# HANDOVER newest entry
git add frontend/src/pages/admin/AiOperationsPage.jsx frontend/src/pages/admin/FeedHealthPage.jsx docs/PRODUCT_STATUS.md docs/HANDOVER.md
git commit -m "feat(admin): AI Ops payload viewer and manual retry"
```

---

## Self-review

| Spec item | Task |
|-----------|------|
| Opt-in failure store | Task 1 |
| Short TTL / not in support pack | Task 1 (+ verify support pack tests still omit bodies) |
| Manual retry same payload | Task 2–3 |
| Default ADR-AI-5 preserved | Task 1 flag default off |
| Not a heartbeat fix | Feed Health remains circuit; copy points to AI Ops |

**Placeholder scan:** none intentional — implementers must pick next Alembic revision id after `git pull`.
