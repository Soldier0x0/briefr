# ENV webhook delete + LLM honesty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reserved ENV webhook Delete removes that card across restarts; LLM Activity names DNS/network failures, trips circuits, never 500s View payload, and lets operators disable a provider without deleting its key.

**Architecture:** Tombstone flags in `app_settings` (`WEBHOOK_TOMBSTONE_{DISCORD|TELEGRAM|GENERIC}`) skip env bootstrap in `load_destinations`. `classify_llm_error` gains `dns`/`network`; failed attempts call `record_source_failure` and job-session skip for that provider. `ai_operations.error_detail` stores a 200-char redacted excerpt. Payload GET is tolerant JSON. Per-provider `LLM_PROVIDER_<NAME>_ENABLED` (default on) filters `get_configured_providers`.

**Tech Stack:** FastAPI, `app_settings`, Alembic 044, existing `resilient_client` circuits, React admin AI ops / webhooks.

**Spec:** `docs/superpowers/specs/2026-09-07-env-delete-llm-honesty-design.md`  
**CE contract:** `docs/plans/2026-09-07-001-feat-env-delete-llm-honesty-plan.md`

## Global Constraints

- Merge gate: `./scripts/verify-local.sh`.
- Postgres-native SQL in `db/`; keep `_SQLITE` twins for default pytest.
- Alembic forward-only; next revision `044_ai_operations_error_detail` revises `043_ioc_value_digest`.
- No secrets in HTTP `detail`, toasts, or `error_detail`.
- Do not implement GitHub #820, URL cascade delete, Discord API revoke, new LLM vendors.
- Dark UI; HelpTip not emoji; `confirm_text=delete` unchanged.
- Docs: `docs/PRODUCT_STATUS.md` + `docs/API_REFERENCE.md` in the same PR as behavior.

---

### File map

| File | Responsibility |
|------|----------------|
| Modify: `backend/webhooks/destinations.py` | Tombstone helpers; skip bootstrap; pop process env on clear |
| Modify: `backend/routers/admin/webhooks.py` | Delete returns 200 + optional `warning` |
| Modify: `backend/operator_settings.py` | Clear tombstone when reserved URL/token saved non-empty |
| Modify: `backend/tests/test_webhooks_destinations_crud.py` | Replace 409 expectation; tombstone survives re-inject |
| Modify: `backend/ai/operations_recorder.py` | `dns`/`network`; `error_detail` on insert |
| Modify: `backend/ai/llm_session.py` | Skip provider after dns/network in job session |
| Modify: `backend/ai/llm_router.py` | `record_source_failure`; enabled-flag filter; safe payload truncate |
| Modify: `backend/db/ai_operations.py` | `error_detail` column in INSERT/SELECT |
| Modify: `backend/db/init.py` | SQLite `ai_operations.error_detail` |
| Create: `backend/alembic/versions/044_ai_operations_error_detail.py` | `ADD COLUMN error_detail TEXT` on `ai_operations` (schema `app` if split) |
| Modify: `backend/db/ai_operation_payloads.py` | Truncate per message content |
| Modify: `backend/routers/admin/ai_ops.py` | Payload 200 + `messages_parse_ok`; retry 400 |
| Modify: `backend/config_schema.py` | Five `LLM_PROVIDER_*_ENABLED` bools, immediate |
| Modify: `backend/.env.example` | Commented defaults |
| Modify: `frontend/src/pages/admin/circuitLabels.js` | `dns` / `network` labels |
| Modify: `frontend/src/pages/admin/AiOperationsPage.jsx` | Result excerpt; payload modal; provider Switch |
| Modify: `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md` | Shipped contract |

---

### Task 1: Tombstone ENV dest delete (200, card stays gone)

**Files:**
- Modify: `backend/webhooks/destinations.py`
- Modify: `backend/routers/admin/webhooks.py`
- Modify: `backend/operator_settings.py`
- Test: `backend/tests/test_webhooks_destinations_crud.py`

**Interfaces:**
- Produces: `TOMBSTONE_KEYS = {"discord": "WEBHOOK_TOMBSTONE_DISCORD", "telegram": "WEBHOOK_TOMBSTONE_TELEGRAM", "generic": "WEBHOOK_TOMBSTONE_GENERIC"}`; `async def is_env_dest_tombstoned(destination_id: str) -> bool`; `async def set_env_dest_tombstone(destination_id: str, *, tombstoned: bool) -> None`; `clear_env_bootstrap_config` pops URL keys even when listed in `PROCESS_ENV_KEYS`; `load_destinations` omits tombstoned reserved ids; DELETE 200 `{ok, destination_id, warning?: str}`

- [ ] **Step 1: Write the failing tests**

In `test_webhooks_destinations_crud.py`, change `test_delete_env_discord_409_when_process_env_set` to expect 200 and no `discord` on list. After delete, `monkeypatch.setenv` the URL again, `sync_env_destinations_to_db()`, list still has no `discord`. Keep a db dest `discord-ops` with the same URL — it remains.

```python
def test_delete_env_discord_tombstone_ignores_process_env(admin_client, monkeypatch):
    import settings as settings_mod
    from webhooks.destinations import load_destinations

    url = "https://discord.com/api/webhooks/1/token"
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", url)
    monkeypatch.setattr(
        settings_mod,
        "PROCESS_ENV_KEYS",
        frozenset({*settings_mod.PROCESS_ENV_KEYS, "DISCORD_WEBHOOK_URL"}),
    )
    run_db_test(sync_env_destinations_to_db())
    create = admin_client.post(
        "/api/admin/webhooks/destinations",
        json={
            "kind": "discord",
            "id": "discord-ops",
            "label": "Ops",
            "config": {"url": url},
        },
    )
    assert create.status_code == 200, create.text

    deleted = admin_client.delete(
        "/api/admin/webhooks/destinations/discord",
        params={"confirm_text": "delete"},
    )
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["ok"] is True
    assert "warning" in body
    assert "DISCORD_WEBHOOK_URL" in body["warning"]
    assert url not in deleted.text

    listed = admin_client.get("/api/admin/webhooks/destinations")
    ids = [row["id"] for row in listed.json()["destinations"]]
    assert "discord" not in ids
    assert "discord-ops" in ids

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", url)
    run_db_test(sync_env_destinations_to_db())
    listed2 = admin_client.get("/api/admin/webhooks/destinations")
    ids2 = [row["id"] for row in listed2.json()["destinations"]]
    assert "discord" not in ids2
    assert "discord-ops" in ids2
```

Also update `test_delete_env_discord_succeeds_when_url_only_in_db_config`: after re-`setenv` + sync, **do not** expect `configured_channels() == ["discord"]` unless tombstone was cleared by saving the URL through config persist. Split: re-inject env without config save → still gone.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_webhooks_destinations_crud.py::test_delete_env_discord_tombstone_ignores_process_env -q`

Expected: FAIL (409 or discord still listed).

- [ ] **Step 3: Implement tombstone + pop + 200**

`clear_env_bootstrap_config`: for every key in `_ENV_BOOTSTRAP_CLEAR_KEYS[id]`, `os.environ.pop(key, None)` **including** `PROCESS_ENV_KEYS`. Persist empty via existing `persist_operator_setting` / `set_app_setting`. `set_env_dest_tombstone(id, tombstoned=True)` writes `"1"`. `load_destinations`: after merge, drop dests whose id is reserved and tombstoned. `sync_env_destinations_to_db`: skip upsert for tombstoned ids. Delete route: if reserved, clear + tombstone + `db_delete`; return `{"ok": True, "destination_id": id}` plus `warning` when `_ENV_BOOTSTRAP_PROCESS_KEYS` were in `PROCESS_ENV_KEYS` at import (systemd will re-inject). In `persist_operator_setting`, if key is `DISCORD_WEBHOOK_URL` / `WEBHOOK_GENERIC_URL` / telegram token+chat and new value is non-empty, clear matching tombstone.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_webhooks_destinations_crud.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/webhooks/destinations.py backend/routers/admin/webhooks.py backend/operator_settings.py backend/tests/test_webhooks_destinations_crud.py
git commit -m "fix(webhooks): tombstone reserved env dest delete so the card stays gone"
```

---

### Task 2: Classify dns/network, circuit, job skip, error_detail

**Files:**
- Modify: `backend/ai/operations_recorder.py`
- Modify: `backend/ai/llm_session.py`
- Modify: `backend/ai/llm_router.py`
- Modify: `backend/db/ai_operations.py`
- Modify: `backend/db/init.py`
- Create: `backend/alembic/versions/044_ai_operations_error_detail.py`
- Test: `backend/tests/test_llm_router.py` (add cases)

**Interfaces:**
- Produces: `classify_llm_error` returns `"dns"` | `"network"` | existing classes; `record_llm_attempt(..., error_detail: str | None = None)`; `mark_provider_transport_failure(provider: str)` aliases empty-skip set; `insert_ai_operation(..., error_detail=None)`

- [ ] **Step 1: Write failing unit tests**

```python
def test_classify_llm_error_dns_errno_minus_3():
    from ai.operations_recorder import classify_llm_error
    exc = OSError(-3, "Temporary failure in name resolution")
    assert classify_llm_error(exc) == "dns"


def test_dns_failure_skips_provider_later_in_job(tmp_path, monkeypatch):
    from ai.llm_session import llm_job_session, is_provider_skipped_in_job
    from ai import llm_router as router
    from database import init_db, get_db, list_ai_operations
    from tests.conftest import run_db_test

    if not is_postgres():
        db_path = tmp_path / "llm_dns.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("AI_OPERATIONS_RECORD", "1")
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk_test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    calls = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        if step.provider == "cerebras":
            raise OSError(-3, "Temporary failure in name resolution")
        return '{"vendor":"x","product":"y"}'

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        await init_db()
        with llm_job_session():
            first = await chat_completion_task(
                "product_extraction",
                messages=[{"role": "user", "content": "cve"}],
            )
            skipped = is_provider_skipped_in_job("cerebras")
            second = await chat_completion_task(
                "product_extraction",
                messages=[{"role": "user", "content": "cve-2"}],
            )
        db = await get_db()
        try:
            rows = await list_ai_operations(db, limit=20)
        finally:
            await db.close()
        return first, second, skipped, rows, calls

    first, second, skipped, rows, calls = run_db_test(run())
    assert skipped is True
    assert calls.count("cerebras") == 1
    dns_rows = [r for r in rows if r["error_class"] == "dns"]
    assert dns_rows
    assert "name resolution" in (dns_rows[0].get("error_detail") or "").lower()
```

Confirm `list_ai_operations` SELECT includes `error_detail` once the column exists.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llm_router.py::test_classify_llm_error_dns_errno_minus_3 tests/test_llm_router.py::test_dns_failure_skips_provider_later_in_job -q`

Expected: FAIL (`unknown` class and/or cerebras called twice).

- [ ] **Step 3: Implement**

`classify_llm_error`: `msg = str(exc).lower()`; if `"name resolution" in msg` or `"errno -3" in msg` or `"gaierror" in msg` or getattr `errno == -3`: return `"dns"`. If `"connection refused"` / `"connection reset"` / `"connecterror"` / `"network is unreachable"`: `"network"`. Keep existing checks first for 429/401 so HTTP errors stay `rate_limit`/`auth`.

`llm_session.mark_provider_transport_failure` = same set as empty skip (reuse `_job_empty_providers` or rename to `_job_skip_providers` in that file only).

`llm_router` except `Exception`: `record_source_failure(step.provider, str(exc)[:200])`; `error_class = classify_llm_error(exc)`; if class in `{"dns", "network"}`: `mark_provider_transport_failure(step.provider)`; pass `error_detail=str(exc)[:200]` into `_record_attempt` (redact secrets the same way payloads do, or reuse `_redact_secrets` from payloads module). Same for `TimeoutError` / empty.

Alembic 044: `ALTER TABLE app.ai_operations ADD COLUMN IF NOT EXISTS error_detail TEXT` (`ai_operations` is an `APP_TABLES` relation after 036). SQLite `init.py` CREATE TABLE add `error_detail TEXT`. Extend INSERT placeholders to 20 params.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_llm_router.py tests/test_ai_operations_admin.py -q`

Expected: PASS (admin tests still work with extra column default null).

- [ ] **Step 5: Commit**

```bash
git add backend/ai/operations_recorder.py backend/ai/llm_session.py backend/ai/llm_router.py backend/db/ai_operations.py backend/db/init.py backend/alembic/versions/044_ai_operations_error_detail.py backend/tests/test_llm_router.py
git commit -m "fix(ai): classify dns/network failures and skip that provider for the job"
```

---

### Task 3: Payload GET never 500; truncate contents; Activity + modal

**Files:**
- Modify: `backend/db/ai_operation_payloads.py`
- Modify: `backend/routers/admin/ai_ops.py`
- Modify: `frontend/src/pages/admin/circuitLabels.js`
- Modify: `frontend/src/pages/admin/AiOperationsPage.jsx`
- Test: `backend/tests/test_ai_operations_admin.py`
- Test: `frontend/src/pages/admin/circuitLabels.test.js` (create)
- Test: `frontend/src/pages/admin/aiOperationsActivityActions.test.js` (extend if result helper extracted)

**Interfaces:**
- Produces: GET payload `{messages, messages_parse_ok: bool, messages_raw: str | null, response_excerpt, ...}`; retry 400 when parse fails

- [ ] **Step 1: Write failing tests**

```python
def test_get_payload_200_when_messages_json_invalid(admin_client):
    operation_id = "op-bad-json"
    async def _seed():
        await init_db()
        db = await get_db()
        try:
            await insert_ai_operation_payload(
                db,
                operation_id=operation_id,
                messages_json='[{"role":"user","content":"partial',
                response_excerpt="[Errno -3] Temporary failure in name resolution",
                task_class="product_extraction",
                provider="cerebras",
                model="gpt-oss-120b",
            )
            await db.commit()
        finally:
            await db.close()
    run_db_test(_seed())
    r = admin_client.get(f"/api/admin/ai/operations/{operation_id}/payload")
    assert r.status_code == 200
    body = r.json()
    assert body["messages_parse_ok"] is False
    assert body["messages"] == []
    assert "Errno -3" in body["response_excerpt"]
    assert "partial" in (body.get("messages_raw") or "")
```

Frontend: `circuitLabels.js` export `dns: 'dns failure'`, `network: 'network error'`. Test file:

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { LLM_ERROR_LABELS } from './circuitLabels.js'

describe('LLM_ERROR_LABELS', () => {
  it('labels dns and network', () => {
    assert.equal(LLM_ERROR_LABELS.dns, 'dns failure')
    assert.equal(LLM_ERROR_LABELS.network, 'network error')
    assert.equal(LLM_ERROR_LABELS.unknown, 'unknown error')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_operations_admin.py::test_get_payload_200_when_messages_json_invalid -q`

Expected: FAIL 500.

- [ ] **Step 3: Implement**

Replace `_parse_payload_messages` raising 500 with a helper that returns `(messages, parse_ok, raw)`. GET uses it. Retry: if not `parse_ok`, `HTTPException(400, "Stored payload cannot be replayed")`. `_truncate` in `insert_ai_operation_payload`: `json.loads` messages, truncate each `content` to keep dumped JSON under 32768, fallback to current truncate only if parse fails on insert. Activity `resultCell`: after reason, if `row.error_detail`, show it truncated to 80 chars. Payload modal: if `messages_parse_ok === false`, show `messages_raw` in the Messages pre and still show excerpt; do not toast on 200.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_ai_operations_admin.py -q`  
Run: `cd frontend && node --test src/pages/admin/circuitLabels.test.js`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db/ai_operation_payloads.py backend/routers/admin/ai_ops.py frontend/src/pages/admin/circuitLabels.js frontend/src/pages/admin/AiOperationsPage.jsx backend/tests/test_ai_operations_admin.py frontend/src/pages/admin/circuitLabels.test.js
git commit -m "fix(ai-ops): show dns excerpts and never 500 on invalid stored payloads"
```

---

### Task 4: Per-provider enable flags

**Files:**
- Modify: `backend/config_schema.py`
- Modify: `backend/.env.example`
- Modify: `backend/ai/llm_router.py` `get_configured_providers`
- Modify: `backend/ai/operations_admin.py` provider rows include `enabled`
- Modify: `frontend/src/pages/admin/AiOperationsPage.jsx` `ProvidersTab`
- Test: `backend/tests/test_llm_router.py`
- Test: `backend/tests/test_config_schema.py` (assert new keys exist)

**Interfaces:**
- Produces: env keys `LLM_PROVIDER_CUSTOM_ENABLED`, `LLM_PROVIDER_GROQ_ENABLED`, `LLM_PROVIDER_CEREBRAS_ENABLED`, `LLM_PROVIDER_OPENROUTER_ENABLED`, `LLM_PROVIDER_GEMINI_ENABLED` — bool, default on (`"1"` / unset = enabled). `apply_strategy` immediate (not restart). `get_configured_providers` requires usable key **and** enabled.

- [ ] **Step 1: Write failing test**

```python
def test_get_configured_providers_skips_disabled(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk_test")
    monkeypatch.setenv("LLM_PROVIDER_CEREBRAS_ENABLED", "0")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert router.get_configured_providers() == []
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_llm_router.py::test_get_configured_providers_skips_disabled -q`

Expected: FAIL (still `["cerebras"]`).

- [ ] **Step 3: Implement**

`_provider_enabled(name)` reads `LLM_PROVIDER_{NAME.upper()}_ENABLED`; unset/empty/`1`/`true`/`yes`/`on` → True; `0`/`false`/`no`/`off` → False. `config_schema` five fields under `ml`, `type=bool`, `display_label` e.g. `Cerebras LLM enabled`. Providers tab: `Switch` calling existing `POST /api/admin/config` with `{LLM_PROVIDER_CEREBRAS_ENABLED: "0"}` (same body as API keys save — `adminApi.postJson('/config', …)`). Do not add a new router. `providerStatus`: if `p.enabled === false`, `{label: 'Disabled', className: 'badge-muted'}` before configured check. HelpTip: disable without deleting the key.

- [ ] **Step 4: Run tests + frontend unit**

Run: `cd backend && pytest tests/test_llm_router.py tests/test_config_schema.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/config_schema.py backend/.env.example backend/ai/llm_router.py backend/ai/operations_admin.py frontend/src/pages/admin/AiOperationsPage.jsx backend/tests/test_llm_router.py backend/tests/test_config_schema.py
git commit -m "feat(ai): allow disabling an LLM provider without removing its key"
```

---

### Task 5: Living docs + verify-local

**Files:**
- Modify: `docs/PRODUCT_STATUS.md` (Admin webhook delete paragraph; LLM router paragraph)
- Modify: `docs/API_REFERENCE.md` (`DELETE …/destinations`, GET payload, provider enabled)

- [ ] **Step 1: Update PRODUCT_STATUS**

Replace ENV delete 409 sentence with tombstone + 200 + other dests unchanged. LLM: dns/network classes, error_detail, payload parse_ok, provider enable flags. Last updated date `2026-09-07`.

- [ ] **Step 2: Update API_REFERENCE**

DELETE reserved: 200, `warning` optional, tombstone keys named. GET payload fields. Provider health `enabled`.

- [ ] **Step 3: verify-local**

Run: `./scripts/verify-local.sh`

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add docs/PRODUCT_STATUS.md docs/API_REFERENCE.md
git commit -m "docs: ENV dest tombstone delete and LLM honesty contract"
```
