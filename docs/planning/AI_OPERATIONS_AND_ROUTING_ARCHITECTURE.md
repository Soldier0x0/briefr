# BRIEFR AI Operations & Routing Architecture

**Status:** Planning only — **no implementation in this document**  
**Date:** 2026-07-10  
**Audit basis:** Direct codebase trace on `main` (commit family post-PR8, 2026-07-10).  
`graphify-out/` used only as supporting context — **not** source of truth (stale vs `main`).

**Central principle (non-negotiable):**

> The LLM interprets, extracts, and narrates where appropriate. BRIEFR remains
> deterministic for retrieval, correlation, enrichment, scoring, scheduling, and
> core intelligence operations.

BRIEFR must remain **fully functional** when AI is disabled or when every AI provider
is unavailable.

**Explicitly NOT in scope:** Ask BRIEFR, chatbot, agent, tool-calling, RAG, investigation
memory, MemPalace, browser automation, autonomous workflows. See §26.

---

## 1. Executive summary

BRIEFR already ships a **task-based multi-provider LLM router** (`backend/ai/llm_router.py`)
with three production task classes, four cloud providers (Groq, Gemini, Cerebras,
OpenRouter), scheduler-gated enrichment jobs, and **deterministic template fallbacks**
for PDF narratives. Local **embeddings** (fastembed/BGE) are a separate ONNX path for
related-CVE similarity.

**What works today:** Optional assistive features; no LLM on the hot request path except
explicit analyst-triggered `POST /api/ai/summary` (PDF export). Scheduler jobs for product
extraction and detection-context artifacts. SSRF-safe outbound HTTP via `resilient_client`.
Circuit breakers and API queue pacing per provider source key.

**What's missing:** Centralized **model catalog**, **persistent AI operation history**
(tokens/latency/fallback), **provider health/deprecation** surfacing, **quota semantics**
beyond conservative pacing defaults, and an **Admin AI Operations** view. Model IDs and
routing chains are **env-scattered**; `tracking.API_LIMITS` does **not** include LLM
providers (only IOC/feed services). Frontend PDF footer copy is **stale** (references
Anthropic; router no longer uses it).

**Recommendation:** **Evolve** `llm_router.py` into a thin **AI Operations facade** —
do **not** replace with an external gateway (OmniRoute) or a rewrite. Deliver in **8–10
small PRs**: catalog + operation log first, routing policy extraction second, admin UI
third. Quota-aware routing starts **advisory** (operator warnings), not automated
deprioritization. Keep **embeddings** operationally separate from generative routing but
visible on the same Admin page.

**Smallest architecture that solves current problems:**

1. Single module owns task classes, model catalog defaults, and completion recording.
2. Features call `ai_ops.complete(task_class, ...)` instead of importing provider clients.
3. `sync_state` + optional `ai_operations` table for observability (no prompt storage).
4. Admin page reads existing config keys + new health/usage aggregates.

---

## 2. Current-state AI architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Analyst-triggered (request path)                                        │
│   POST /api/ai/summary  →  ai/summary.py  →  llm_router (pdf_summary)   │
│   Frontend PDF export →  fetchAiSummary →  same                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Scheduler-side (background, env-gated)                                  │
│   llm_product_extraction  →  ml/product_extraction.py                   │
│   detection_context_llm   →  detection/context_llm_sync.py              │
│                             →  detection/artifact_extract.py            │
│   embeddings_backfill     →  ml/embeddings.py (local ONNX, not LLM API) │
│   detection_context_sync  →  detection/context_sync.py (NO LLM)        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ llm_router.py                                                           │
│   chat_completion_task(task, messages) → failover chain per LLMTask     │
│   Providers: groq | gemini | cerebras | openrouter                      │
│   Transport: openai_chat.py | gemini_client.py                          │
│   Pacing/queue: resilient_client + api_queue + source_rate_limits       │
│   Circuit: resilient_client per-source circuit breaker                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Deterministic fallbacks (no LLM)                                        │
│   ai/summary.py template narrative                                      │
│   templates/intelligence.py prose helpers                               │
│   routers/forge.py hunt packs → sigma_generator (rule templates)        │
│   detection/context_sync.py metadata-only DetectionContext              │
└─────────────────────────────────────────────────────────────────────────┘
```

**Config SSOT today:** `backend/config_schema.py` + `backend/.env.example` for API keys
and ML toggles. No dedicated AI routing admin beyond ApiKeys page secrets.

---

## 3. Current AI usage inventory

| Feature | Calling module | Entry point | Provider(s) | Model(s) | Prompt location | Config source | Fallback | Retry | Quota handling | Usage tracking | Required? |
|---------|----------------|-------------|-------------|----------|-----------------|---------------|----------|-------|----------------|----------------|-----------|
| **Executive / PDF summary** | `ai/summary.py` | `POST /api/ai/summary`, `generate_executive_summary` | Router chain | `GROQ_MODEL_SUMMARY`, `GEMINI_MODEL`, `CEREBRAS_MODEL`, `OPENROUTER_MODEL_PDF` | `summary.py` `SYSTEM_PROMPT`, `USER_PROMPT_TEMPLATE` | Env keys + model env vars | **Template** narrative (`source: template`) | Router tries next provider; `CircuitOpenError` skip; empty content skip | `groq_limits()`, `source_rate_limits` pacing, `api_queue` token headers | API queue op `report_summary`; **not** `api_usage` DB | **Optional** |
| **Investigation PDF summary** | `ai/summary.py` | `POST /api/investigation/summary` | Same as PDF | Same | Same (via `split_investigation_items`) | Same | Template | Same | Same | Same | **Optional** |
| **LLM product extraction** | `ml/product_extraction.py` | Scheduler `llm_product_extraction` | Router `product_extraction` chain | `GROQ_MODEL`, etc. | `product_extraction.py` prompts | `LLM_PRODUCT_EXTRACTION_*`, provider keys | Skip CVE; negative cache in `feed_cache` (`llm_products:`) | Router failover; **errors not cached** (retry next run) | Scheduler `MAX_PER_RUN`; pacing via queue | Queue op `product_extraction` | **Optional** (env `LLM_PRODUCT_EXTRACTION_ENABLED`) |
| **Detection context artifacts** | `detection/artifact_extract.py`, `context_llm_sync.py` | Scheduler `detection_context_llm` | Router `detection_context` (no Cerebras in chain) | Same family | `artifact_extract.py` prompts | `DETECTION_CONTEXT_LLM_*` | Empty artifacts; keep deterministic `build_detection_context` base | Router; `feed_cache` `detection_ctx_llm:` retry window | Scheduler caps | Queue op `detection_context` | **Optional** (`DETECTION_CONTEXT_LLM_ENABLED`) |
| **CVE embeddings** | `ml/embeddings.py` | Scheduler `embeddings_backfill` | **Local** fastembed/ONNX | `EMBEDDINGS_MODEL` (default `BAAI/bge-small-en-v1.5`) | N/A (embed CVE description text) | `EMBEDDINGS_*` | **Heuristic** related CVEs (`GET .../related`) | Batch in scheduler | CPU/memory bound, not API quota | None persisted | **Optional** (`EMBEDDINGS_ENABLED`) |
| **Legacy Groq client** | `ai/groq_client.py` | Tests only in prod trace | Groq direct | `GROQ_MODEL` | N/A | `groq_config` | N/A | `resilient_request` wait on 429 | `groq_limits` | Queue `report_summary` | **Unused** on main path |

### Features audited that do **not** use generative LLM

| Feature | Module | Notes |
|---------|--------|-------|
| Hunt pack generation | `routers/forge.py` → `detection/sigma_generator.py` | Bundled templates + DetectionContext; **no outbound LLM** |
| DetectionContext backfill | `detection/context_sync.py` | Deterministic from CVE row metadata |
| Display summaries / chips | `enrichment/cve.py`, `templates/intelligence.py` | Truncation + template sentences |
| MITRE feed strings | `feeds/mitre.py` | String filter only (`anthropic` as text) |
| Correlation / scoring / NVD ingest | `correlation/`, `feeds/`, `scheduler.py` | Fully deterministic |

### Duplication & inconsistency findings

| Issue | Evidence |
|-------|----------|
| **Scattered model IDs** | `groq_config.py`, `gemini_client.py`, `llm_router._openrouter_free_model`, env `OPENROUTER_MODEL_*`, `CEREBRAS_MODEL` |
| **Parallel Groq paths** | `groq_client.py` vs `openai_chat_completion(source="groq")` — production uses router → openai_chat only |
| **Stale API/docs copy** | `routers/meta.py` docstring "Groq → Anthropic"; `frontend/pdfAiSummary.js` Anthropic footer; router has no Anthropic |
| **Task taxonomy narrow** | `LLMTask` Literal has exactly 3 values — matches real usage (good) but naming doesn't match operator vocabulary (`pdf_summary` vs `executive_summary`) |
| **Hardcoded failover order** | `_task_chain()` per task — not quota/health-aware (by design today) |
| **No LLM rows in `api_usage`** | `tracking.API_LIMITS` omits groq/gemini/cerebras/openrouter — `/api/usage` invisible for AI |
| **ANTHROPIC_API_KEY** | Still in `config_schema` as deprecated; pacing profile exists but router unused |

### Direct HTTP to AI providers

| Client | URL pattern | Auth |
|--------|-------------|------|
| `openai_chat.py` | Groq, Cerebras, OpenRouter OpenAI-compatible URLs | Bearer |
| `gemini_client.py` | `generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | `x-goog-api-key` |
| `groq_client.py` | Groq URL (legacy/tests) | Bearer |

All use `resilient_request` → API queue registration when `queue_operation` passed.

---

## 4. Existing architectural strengths

1. **Task-based router already exists** — features do not import Groq/Gemini directly (except legacy `groq_client` tests).
2. **Optional-by-default** — ML flags default off; PDF summary falls back to templates without raising.
3. **Scheduler-only heavy AI** — product extraction and detection LLM never block feed/detail paths.
4. **Shared outbound spine** — `resilient_client` circuit breaker + `api_queue` pacing reused across providers.
5. **Negative caching** — product extraction and detection LLM avoid repeat quota burn (`feed_cache` keys).
6. **Prompt injection awareness (partial)** — bounded evidence bundles (CVE blocks truncated); JSON-only instructions for structured tasks.
7. **Embeddings isolation** — local ONNX path cleanly separated from cloud LLM keys.

---

## 5. Existing architectural problems

1. **No persistent AI operation log** — cannot answer "which model handled last PDF summary?" after the request completes.
2. **No model catalog SSOT** — changing `GROQ_MODEL_SUMMARY` requires env doc literacy; admin has no model visibility.
3. **Quota confusion** — `GROQ_RPM_LIMIT` / `GROQ_TPM_LIMIT` are configurable but treated as defaults; no provider-reported usage merge; no mismatch warning.
4. **Provider health opaque** — circuit state exists in `resilient_client` but not surfaced to admin.
5. **Deprecation not handled** — model-not-found errors log and failover; no operator alert or catalog staleness detection.
6. **Observability gap vs API queue** — queue shows in-flight ops; no historical token accounting.
7. **Frontend/backend drift** — PDF AI attribution strings wrong for multi-provider router.
8. **Dead code** — `groq_client.py` production path superseded; `ANTHROPIC` config remnants.

---

## 6. Proposed target architecture

```
┌──────────────────┐     ┌─────────────────────┐     ┌────────────────────┐
│ Feature modules  │────▶│ ai_ops.facade       │────▶│ Provider adapters  │
│ summary.py       │     │ complete(task, ...) │     │ groq/gemini/       │
│ product_extract  │     │ record_operation()  │     │ cerebras/openrouter│
│ artifact_extract │     └─────────┬───────────┘     └─────────┬──────────┘
└──────────────────┘               │                             │
                                   ▼                             ▼
                    ┌──────────────────────────┐    ┌─────────────────────┐
                    │ Routing policy engine    │    │ resilient_client +  │
                    │ (task class + health +   │    │ api_queue (existing)│
                    │  advisory quota)         │    └─────────────────────┘
                    └─────────┬────────────────┘
                              ▼
                    ┌──────────────────────────┐
                    │ Model catalog (SSOT)     │
                    │ Provider registry        │
                    │ ai_operations log (DB)   │
                    │ sync_state health keys   │
                    └─────────┬────────────────┘
                              ▼
                    ┌──────────────────────────┐
                    │ Admin → AI Operations    │
                    │ (read-mostly + links to  │
                    │  ApiKeys for secrets)    │
                    └──────────────────────────┘
```

**Migration strategy:** `llm_router.chat_completion_task` becomes the implementation behind
`ai_ops.complete` — signatures stable, internals refactored incrementally.

**Not proposed:** Embedding OmniRoute, LiteLLM proxy, or a second HTTP hop for all LLM traffic.
BRIEFR is self-hosted; adding a mandatory gateway increases ops burden without fixing the
core gap (visibility + catalog).

---

## 7. Provider abstraction design

### Layer model

| Layer | Responsibility |
|-------|----------------|
| **Feature** | Builds messages, chooses `task_class`, supplies `context_id` (e.g. CVE id) |
| **AI Ops facade** | `complete(task_class, messages, opts) → CompletionResult` |
| **Routing policy** | Ordered eligible `(provider, model)` candidates for task |
| **Provider adapter** | Translate to HTTP (existing clients) |
| **Transport** | `resilient_request` + queue metadata |

### Provider registry (initial catalog)

| Provider ID | Adapter module | Config key | Endpoint | Status |
|-------------|----------------|------------|----------|--------|
| `groq` | `openai_chat` | `GROQ_API_KEY` | fixed Groq URL | **Shipped** |
| `gemini` | `gemini_client` | `GEMINI_API_KEY` | Google Generative Language API | **Shipped** |
| `cerebras` | `openai_chat` | `CEREBRAS_API_KEY` | fixed Cerebras URL | **Shipped** |
| `openrouter` | `openai_chat` | `OPENROUTER_API_KEY` | fixed OpenRouter URL | **Shipped** |
| `openai` | `openai_chat` | (future `OPENAI_API_KEY`) | configurable | **Deferred** |
| `anthropic` | (removed) | deprecated key | — | **Do not reintroduce** without ADR |

**Max providers:** 4 active + 2 future slots in registry — not dozens. Self-hosted maintainability
caps the catalog unless a provider shares the OpenAI chat completions shape.

### Incremental vs replace

| Approach | Verdict |
|----------|---------|
| Extend `llm_router` | **Yes** — rename types, extract catalog, add recording hook |
| Replace router | **No** — working failover + tests (`test_llm_router.py`) |
| External OmniRoute | **No dependency** — borrow *concepts* only (§9) |

---

## 8. Task-class model

### Canonical task classes (from audit — not aspirational)

| Task class | Current `LLMTask` | Features | Structured output? |
|------------|-------------------|----------|-------------------|
| `report_narrative` | `pdf_summary` | Executive summary, investigation PDF | JSON preferred (`executive_summary`, `key_findings`, `confidence`) — parser tolerates prose |
| `structured_product_extraction` | `product_extraction` | Scheduler LLM product fill for NVD gaps | **Yes** — JSON `products[]` |
| `structured_detection_artifacts` | `detection_context` | Scheduler artifact extract for DetectionContext | **Yes** — JSON `artifacts[]` |

**Rename policy:** Introduce stable external names (`report_narrative`) aliased to existing
internal task keys during migration to avoid breaking env/docs references in one PR.

### Per-task requirements

| Task class | Capabilities needed | Context size (typical) | Max tokens | Temperature | Failure behaviour |
|------------|---------------------|------------------------|------------|-------------|-------------------|
| `report_narrative` | Long-form prose, JSON mode helpful | ~2–8 KB evidence bundle | 600 | 0.25 | Template summary (`source: template`) |
| `structured_product_extraction` | JSON extraction, low hallucination | CVE description ≤4 KB | 500 | 0.0 | Skip CVE; no DB write; retry next scheduler run |
| `structured_detection_artifacts` | JSON extraction | ≤6 KB text + optional Nuclei YAML | 700 | 0.0 | Keep deterministic DetectionContext; skip LLM artifacts |

### Task-specific routing policies

| Task | Current chain | Proposed policy change |
|------|---------------|------------------------|
| `report_narrative` | Groq summary model → Gemini → Cerebras → OpenRouter | Allow **larger model** preference; deprioritize providers with open circuit |
| `structured_product_extraction` | Groq → Gemini → Cerebras → OpenRouter | Prefer **fast/cheap**; structured-output-capable models first |
| `structured_detection_artifacts` | Groq → Gemini → OpenRouter (no Cerebras) | Keep omitting Cerebras unless eval shows benefit |

**Separate policies:** Yes — but implement as **data** on task class (preferred model tier, excluded providers), not separate code paths per feature.

---

## 9. Routing design

### Current behaviour (baseline)

- Static ordered failover per task (`_task_chain`).
- Skip provider if API key missing/placeholder.
- Skip on empty content, exception, or `CircuitOpenError`.
- One attempt per provider per call (no parallel fan-out).

### Target behaviour (evolved)

| Signal | Source today | Use in routing |
|--------|--------------|----------------|
| Provider configured | `get_configured_providers()` | Hard gate |
| Circuit open | `resilient_client` | Skip provider (already) |
| Recent failures | New: `sync_state` `ai.health.{provider}` | Deprioritize (not skip) in advisory phase |
| Quota headroom | `api_queue` rate-limit headers + configured limits | **Advisory** warning; optional skip when `remaining_tokens < estimated` |
| Model availability | New: catalog + provider model list job | Warn admin; suggest fallback model — **do not auto-rewrite env** |
| Latency p95 | New: `ai_operations` aggregates | Display only initially |
| Context window | Catalog metadata | Filter candidates |

### OmniRoute research (concepts only — no dependency)

Studied [OmniRoute architecture](https://github.com/diegosouzapw/OmniRoute/blob/main/docs/ARCHITECTURE.md) for:

| Concept | BRIEFR mapping |
|---------|----------------|
| Quota preflight / headroom routing | Map to `api_queue` token headers + configured `GROQ_TPM_LIMIT` — **advisory first** |
| Reset-aware / reset-window routing | Store `x-ratelimit-reset-*` in provider health snapshot; show "resets in …" in admin |
| Circuit breaker per provider | **Already have** — expose state |
| Model-level lockout | Future: mark model degraded in catalog when repeated 404 model errors |
| Multi-strategy routing (17 strategies) | **Overkill** for 3 tasks / 4 providers — use **priority list + health filters** |
| Quota-share / fair-share across keys | **N/A** — BRIEFR uses one key per provider per instance |

**Verdict:** Borrow **health + quota visibility** patterns; reject external gateway and
complex strategy engine for V1 of AI Ops.

### Single-provider mode

When only one provider key configured, router naturally runs single-provider — no special case
required. Admin UI should show "single-provider mode" explicitly.

---

## 10. Model catalog design

### SSOT module (proposed)

`backend/ai/model_catalog.py` (name TBD) — Python registry, not scattered env reads in features.

### Catalog entry fields

| Field | Source | Notes |
|-------|--------|-------|
| `provider_id` | registry | groq, gemini, … |
| `model_id` | env override + default | e.g. `openai/gpt-oss-120b` |
| `display_name` | static map | Operator-friendly |
| `enabled` | derived from provider key + per-model disable flag (future) | |
| `task_classes[]` | static | Which tasks may select this model |
| `supports_structured_output` | heuristic per model family | Guides structured tasks |
| `context_window` | docs default + optional override | For routing filter |
| `priority_weight` | optional int | Lower = preferred within task policy |
| `replacement_model_id` | admin suggestion only | On deprecation warning |
| `last_success_at` / `last_failure_at` | from `ai_operations` rollups | |
| `availability_status` | `ok` / `degraded` / `unknown` / `deprecated_suspected` | |

### Hardcoded model audit (must migrate to catalog defaults)

| Env var | Default | Used for |
|---------|---------|----------|
| `GROQ_MODEL` | `openai/gpt-oss-20b` | product_extraction, detection_context |
| `GROQ_MODEL_SUMMARY` | `openai/gpt-oss-120b` | pdf_summary |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | all tasks via `gemini_model()` |
| `CEREBRAS_MODEL` | `gpt-oss-120b` | product_extraction, pdf_summary |
| `OPENROUTER_MODEL_PRODUCT` | `google/gemini-2.0-flash-lite-001:free` | product_extraction |
| `OPENROUTER_MODEL_PDF` | `google/gemini-2.0-flash-lite-001:free` | pdf_summary |
| `OPENROUTER_MODEL_DETECTION` | `google/gemini-2.0-flash-lite-001:free` | detection_context |
| `EMBEDDINGS_MODEL` | `BAAI/bge-small-en-v1.5` | **Separate** embedding catalog row |

---

## 11. Model health and deprecation design

### Detection inputs (no generation tokens for existence checks)

| Provider | Metadata API (evaluate per provider docs) | Runtime errors |
|----------|-------------------------------------------|----------------|
| Groq | Models list endpoint | 404 model, 401 auth |
| Gemini | Model list / getModel | 404, 400 retired model |
| OpenRouter | Models API | model not found in routing |
| Cerebras | Documented models endpoint | same |

### Scheduler job (proposed)

`ai_model_catalog_refresh` — weekly + on admin "Refresh models" button.

- Fetches provider model lists where API exists.
- Compares configured catalog IDs → sets `deprecated_suspected` when missing.
- Writes `sync_state` keys `ai.catalog.{provider}.checked_at` and mismatch list.
- **Does not** auto-change `.env` or `app_settings`.

### Administrator notification

- Admin AI Operations → Models panel: warning badge.
- Optional webhook `health` event (existing channel) — **defer** to later PR.
- Support pack may include redacted catalog health summary.

### Fallback on model-not-found

1. Record failure class `model_not_found`.
2. Try next provider in task policy (existing).
3. If same model string wrong on all providers, surface admin fix instructions.
4. Optional per-task **fallback model override** in catalog (operator opt-in) — not silent env rewrite.

---

## 12. Quota architecture

### Current state

| Mechanism | What it does | Limitation |
|-----------|--------------|------------|
| `groq_config.groq_limits()` | RPM/TPM **defaults** + min interval | Not provider-reported |
| `source_rate_limits.PACING_PROFILES` | Min spacing per source | Conservative; not tier-aware |
| `api_queue.apply_rate_limit_headers` | Reads `x-ratelimit-remaining-tokens` etc. | Ephemeral; not stored |
| `tracking.API_LIMITS` | Daily/monthly for IOC services | **LLM providers absent** |
| Scheduler `MAX_PER_RUN` | Caps batch LLM work | Job-level, not quota |

### Target quota model

| Quota source | Precedence | Behaviour |
|--------------|------------|-----------|
| Provider-reported headers | Highest when present | Store last snapshot per provider in `sync_state` |
| Operator override (`AI_QUOTA_{PROVIDER}_*`) | Overrides defaults | Manual RPM/TPM/daily |
| Built-in defaults | Lowest | Documented as free-tier examples |
| Unknown | Explicit `unknown` | No automated routing block — pacing only |

### Rules (per user requirements)

- If observed usage **exceeds** configured quota → **configuration mismatch warning** in UI.
- **Do not clamp** displayed observed values to configured cap.
- Continue counting usage in `ai_operations` either way.
- Quota-aware routing phase 1: **advisory** (warn + sort candidates by headroom).
- Phase 2 (optional): skip provider when `remaining_tokens < reserve_threshold`.

### Reserve threshold

Operator-configurable per provider (default: 0 disabled). When enabled, router prefers
providers above reserve — never blocks template fallbacks for narratives.

---

## 13. AI observability design

### Reuse vs new

| Existing | Reuse for AI? |
|----------|---------------|
| `api_queue` | **Yes** — in-flight ops; extend LLM operation labels (already mapped in `api_queue_operations.py`) |
| `audit_log` | **Partial** — admin config changes only; not per-completion |
| Structured logging | **Yes** — log `task_class`, `provider`, `model`, `latency_ms`, `request_id`; **never** prompt body |
| `api_usage` table | **Extend or parallel** — counts only today; LLM needs token fields → new table preferred |
| `webhook_delivery_log` pattern | Template for append-only operation log |

### Proposed `ai_operations` table (PostgreSQL + SQLite parity)

| Column | Type | Notes |
|--------|------|-------|
| `id` | serial | |
| `operation_id` | text | UUID per completion attempt |
| `request_id` | text nullable | HTTP request id when on request path |
| `started_at` | timestamptz | |
| `latency_ms` | int | |
| `feature` | text | e.g. `pdf_summary`, `product_extraction` |
| `task_class` | text | canonical |
| `provider` | text | |
| `model` | text | |
| `success` | bool | |
| `error_class` | text nullable | `auth`, `rate_limit`, `model_not_found`, `circuit_open`, `timeout`, `empty`, `unknown` |
| `input_tokens` | int nullable | When provider reports |
| `output_tokens` | int nullable | When provider reports |
| `total_tokens` | int nullable | |
| `estimated_cost_usd` | numeric nullable | Only when catalog has pricing |
| `fallback_from_provider` | text nullable | |
| `fallback_from_model` | text nullable | |
| `retry_index` | int | 0 = first provider tried |
| `context_type` | text nullable |/cve/task |
| `context_id` | text nullable | Safe id only |

**Not stored:** raw prompts, raw completions, CVE description text.

### Retention

- Default keep 90 days (operator purge via existing cache retention patterns or dedicated admin action).
- Aggregate rollups daily in `sync_state` or materialized counters for Admin dashboard.

### Realistic provider fields

| Field | Groq | Gemini | OpenRouter | Cerebras |
|-------|------|--------|------------|----------|
| `input_tokens` | Often in response usage | Often | Often | Often |
| `output_tokens` | Often | Often | Often | Often |
| `cost` | Rare on free tier | Rare | Sometimes | Rare |
| Rate limit headers | Common | Varies | Common | Varies |

Plan UI for **nullable** fields — never require cost or tokens to render a row.

---

## 14. Admin AI Operations UX architecture

### Justification

**Yes, but start small.** Current usage: 3 task classes, 4 providers, 2 scheduler jobs + 1
on-demand endpoint — operators cannot see model health, fallback rate, or token trends without
logs. A single Admin page prevents misconfiguration of env model vars and demystifies failover.

### Information architecture

| Tab | Contents |
|-----|----------|
| **Overview** | AI enabled?, providers configured count, 24h request count, failure rate, active circuits, link to ApiKeys |
| **Providers** | Per-provider: key configured (masked), enabled, last success/fail, quota snapshot, circuit state, pacing interval |
| **Models** | Catalog table: model id, task classes, status, last used, deprecation warning |
| **Usage** | Charts/tables from `ai_operations` aggregates — requests, tokens (if known), by task/provider |
| **Activity** | Paginated operation log (redacted) |
| **Routing** | Read-only view of task → provider order; edit deferred to config PR |

### Config linking (no secret duplication)

- Secrets stay on **ApiKeys & config** (`GROQ_API_KEY`, etc.).
- AI Operations shows `configured: yes/no` + link anchor to ApiKeys section.
- Model env vars (`GROQ_MODEL_SUMMARY`) editable later via controlled admin fields writing to `app_settings` — **defer** auto-write until apply-strategy defined (PR8 pattern).

### Questions the page must answer (mapping)

| Question | Source |
|----------|--------|
| Is AI enabled? | Any provider configured OR ML flags on |
| Which providers configured? | `get_configured_providers()` + embeddings flag |
| Healthy? | Circuit + last error class |
| Models active? | Catalog + last_success |
| Deprecated? | Catalog refresh job |
| Features consuming AI? | Static map + scheduler job table |
| Requests/tokens? | `ai_operations` aggregates |
| Fallback? | `fallback_from_*` columns |
| Quota approaching? | Quota snapshot vs override |
| Config mismatch? | observed > configured |

---

## 15. Security and trust-boundary review

### Invariants

1. **API keys** only in env / `app_settings`; never in `ai_operations`, logs, or support pack.
2. **Prompts and completions** not persisted by default.
3. **Provider responses** parsed as untrusted data — JSON parsed defensively (already in product/artifact parsers).
4. **External intelligence in prompts** (CVE text, Nuclei YAML, exploit titles) treated as **data** — system prompts forbid obeying embedded instructions; keep system/user separation.
5. **Configurable provider endpoints** — if added for OpenAI-compatible custom URLs, apply **SSRF rules** analogous to `webhooks/ssrf.py` (HTTPS only, block private IPs). Default providers use fixed URLs.
6. **Admin-only** AI config surfaces — `require_admin` + rate limits.
7. **Audit** provider enable/disable and quota override changes.
8. **Error messages** to UI truncated; no API key echo from provider errors.

### Prompt injection surface

| Source | Risk | Mitigation |
|--------|------|------------|
| CVE description | Medium | Truncate; JSON-only output; validate schema |
| Nuclei YAML in detection extract | Medium | Cap 4000 chars; scheduler-only |
| News/incidents RSS | Low today (not in LLM prompts on main) | Keep out of LLM prompts |

### Logging

- `structured_logging` extra fields: `task_class`, `provider`, `model`, `operation_id` — not `messages`.

---

## 16. Embeddings architecture assessment

| Question | Answer |
|----------|--------|
| Why it exists | Semantic related-CVE similarity when vectors present |
| Consumers | `GET /api/cves/{id}/related` → `ml/embeddings.find_similar_cves` |
| Independent from generative AI? | **Yes** — local ONNX, separate env flag, no API key |
| Show in AI Operations? | **Yes** — separate **Embeddings** card (model name, enabled, vectors count, last backfill) |
| Same model catalog? | **Related registry** `embedding_models` — do not route through LLM router |
| Merge with generative routing? | **No** — avoids coupling GPU/CPU local inference to cloud quota |

**No RAG in this phase** — embeddings remain lookup-only over `cve_embeddings` table.

---

## 17. AI-disabled invariants

| Condition | Core BRIEFR | report_narrative | product_extraction | detection LLM | embeddings |
|-----------|-------------|------------------|--------------------|--------------|--------------|
| All AI keys empty | **Full** | Template summary | Job no-op / disabled | Job no-op | Heuristic related |
| `LLM_PRODUCT_EXTRACTION_ENABLED=0` | **Full** | — | Skipped | — | — |
| `DETECTION_CONTEXT_LLM_ENABLED=0` | **Full** | — | — | Skipped | — |
| `EMBEDDINGS_ENABLED=0` | **Full** | — | — | — | Heuristic related |
| All providers circuit-open | **Full** | Template summary | Skip/fail soft per CVE | Skip artifacts | Local unaffected |
| All rate-limited | **Full** | Template after timeout | Scheduler retries later | Same | Unaffected |
| Model unavailable everywhere | **Full** | Template | No DB poison — skip write | Deterministic context only | Unaffected |

**Invariant:** No HTTP 500 on core CVE/feed/detail paths due to AI failure. `generate_executive_summary` already never raises.

---

## 18. Token-efficiency findings

| Finding | Severity | Recommendation |
|---------|----------|----------------|
| PDF prompt sends up to 12 CVE blocks + IOCs + actors | Medium | Already capped; consider dedupe by `cve_id` |
| Product extraction sends full description | Low | Single CVE per call; acceptable |
| Detection extract up to 6000 chars + Nuclei YAML 4000 | Medium | YAML only first Nuclei exploit — good; monitor token use |
| Duplicate LLM calls | Low | `feed_cache` negative cache for scheduler tasks — extend pattern |
| Deterministic alternative | High value | Template fallback for PDF already saves tokens |
| Hunt packs without LLM | **Good** | Do not add LLM to sigma generation |
| `groq_client` duplicate path | Low | Remove in cleanup PR |

**Do not LLM:** correlation scoring, EPSS/KEV logic, IOC reputation parsing, scheduler orchestration.

---

## 19. Database/schema impact

| Object | Change | Migration |
|--------|--------|-----------|
| `ai_operations` | **New table** | Alembic `014_ai_operations.py` |
| `sync_state` keys `ai.health.*`, `ai.quota.*`, `ai.catalog.*` | Additive JSON blobs | No migration (existing table) |
| `app_settings` optional AI quota overrides | Additive keys | No schema change |
| `api_usage` | Optional later merge | Prefer separate table first |

SQLite + Postgres parity required per `CLAUDE.md` danger zone.

---

## 20. API impact

| Endpoint | Change |
|----------|--------|
| `GET /api/admin/ai/operations/overview` | **New** |
| `GET /api/admin/ai/operations/providers` | **New** |
| `GET /api/admin/ai/operations/models` | **New** |
| `GET /api/admin/ai/operations/activity` | **New** paginated |
| `POST /api/admin/ai/operations/catalog/refresh` | **New** optional manual refresh |
| `POST /api/ai/summary` | Response may add `provider`, `model` (already has `source` — align) |
| Existing ML scheduler | No new public endpoints |

---

## 21. Frontend impact

| Surface | Change |
|---------|--------|
| New `AiOperationsPage.jsx` | Admin nav entry |
| `pdfAiSummary.js` | Fix `aiFooterNoteForSource` for groq/gemini/cerebras/openrouter/template |
| ApiKeys page | Link from AI Ops; no duplicate key forms |
| DetailDrawer / Feed | No change in phase 1 |

---

## 22. Migration strategy

1. **Phase 0 (docs only):** This document + ADR drafts.
2. **Phase 1 (observability):** `ai_operations` + record from `llm_router` — no routing behaviour change.
3. **Phase 2 (catalog):** `model_catalog.py` reads env defaults; admin read API.
4. **Phase 3 (admin UI):** Overview + providers + activity.
5. **Phase 4 (health job):** Scheduler catalog refresh + warnings.
6. **Phase 5 (routing policy):** Extract `_task_chain` to data; advisory quota sort.
7. **Phase 6 (cleanup):** Deprecate `groq_client` prod exports; fix stale copy.

Backward compatibility: all env vars continue to work; new tables additive.

---

## 23. Dependency-ordered PR plan

### PR-AI-1 — AI operations schema + completion recorder

| Field | Value |
|-------|-------|
| **Objective** | Persist redacted AI operation rows on every `chat_completion_task` |
| **Boundary** | `llm_router` hook only; no routing change |
| **Files** | `ai/llm_router.py`, `db/ai_operations.py`, `alembic/014_*`, tests |
| **API** | None |
| **Frontend** | None |
| **Acceptance** | Successful/failed completions create rows; no prompt text stored |
| **Tests** | pytest insert + failure path; Postgres parity |
| **Rollback** | Drop table migration reversible only forward — disable recorder flag |

### PR-AI-2 — Model catalog SSOT (code-only)

| Field | Value |
|-------|-------|
| **Objective** | Centralize model defaults + task bindings |
| **Files** | `ai/model_catalog.py`, refactor `llm_router._task_chain` to read catalog |
| **DB** | None |
| **API** | `GET /api/admin/ai/operations/models` |
| **Acceptance** | No feature module reads `GROQ_MODEL*` directly |
| **Tests** | Catalog snapshot test; grep guard for hardcoded models in features |

### PR-AI-3 — Provider health snapshot

| Field | Value |
|-------|-------|
| **Objective** | Expose circuit state + last error per provider |
| **Files** | `resilient_client` export safe state, `sync_state` writer, admin API |
| **Scheduler** | None yet |
| **Acceptance** | Admin API returns health for groq/gemini/cerebras/openrouter |

### PR-AI-4 — Admin AI Operations page (Overview + Providers)

| Field | Value |
|-------|-------|
| **Objective** | Operator visibility shell |
| **Files** | `AiOperationsPage.jsx`, `AdminPage` nav, `routers/admin.py` overview endpoints |
| **Acceptance** | Page answers enabled/configured/healthy without logs |
| **Frontend** | Manual browser verify; loading/empty/error states |

### PR-AI-5 — Usage aggregates + Activity tab

| Field | Value |
|-------|-------|
| **Objective** | 24h/7d rollups + paginated activity |
| **Files** | admin API queries, frontend Usage + Activity tabs |
| **Acceptance** | Tokens nullable; mismatch warning when observed > configured quota |

### PR-AI-6 — Quota snapshot + advisory warnings

| Field | Value |
|-------|-------|
| **Objective** | Store rate-limit headers; config overrides in `app_settings` |
| **Files** | `ai/quota.py`, config_schema optional fields, admin UI warnings |
| **Acceptance** | UI shows mismatch; routing unchanged |

### PR-AI-7 — Model catalog refresh job

| Field | Value |
|-------|-------|
| **Objective** | Weekly provider model list check |
| **Files** | `scheduler.py` job, provider list clients, deprecation flags |
| **Acceptance** | Missing model → `deprecated_suspected` without env mutation |

### PR-AI-8 — Routing policy extraction + advisory headroom

| Field | Value |
|-------|-------|
| **Objective** | Data-driven task policies; optional skip low-headroom provider |
| **Files** | `ai/routing_policy.py`, `llm_router` |
| **Acceptance** | Existing failover tests pass; new tests for headroom sort |
| **Risk** | Medium — behaviour change behind env flag default off |

### PR-AI-9 — PDF footer + API response alignment

| Field | Value |
|-------|-------|
| **Objective** | Fix stale Anthropic/groq copy; expose `provider`/`model` in summary response |
| **Files** | `pdfAiSummary.js`, `routers/meta.py`, `PRODUCT_STATUS.md` |
| **Acceptance** | Footer matches actual router provider |

### PR-AI-10 — Cleanup: groq_client + anthropic remnants

| Field | Value |
|-------|-------|
| **Objective** | Remove dead paths; document deprecated `ANTHROPIC_API_KEY` |
| **Files** | `groq_client.py` shrink or test-only, config_schema help text |
| **Acceptance** | Production path single transport |

**Estimated PR count:** 10 incremental PRs — **not** one mega PR.

---

## 24. ADR recommendations

| ADR | Topic | Needed? |
|-----|-------|---------|
| ADR-AI-1 | Central AI provider abstraction (facade over router) | **Yes** — records boundary for features |
| ADR-AI-2 | Task-class taxonomy + naming | **Yes** — stabilizes operator vocabulary |
| ADR-AI-3 | Model catalog ownership (Python SSOT vs DB) | **Yes** — default Python + env; DB only for operator overrides later |
| ADR-AI-4 | Quota source precedence | **Yes** — provider headers > override > defaults |
| ADR-AI-5 | AI observability storage (no prompts) | **Yes** — privacy posture |
| ADR-AI-6 | AI-disabled invariants | **Lightweight** — may be section in PRODUCT_STATUS instead |
| ADR-AI-7 | OmniRoute/external gateway | **No** — rejected |

---

## 25. Risks and failure modes

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-engineering routing | High | Maintenance | Advisory quota only; 4 providers |
| `ai_operations` table growth | Medium | Disk | Retention + purge |
| Provider API model list drift | Medium | False deprecation warnings | Manual confirm + snooze |
| Behaviour change in PR-AI-8 | Medium | Surprise failover | Feature flag |
| SQLite/Postgres SQL drift | Medium | Prod break | Alembic + dialect tests |
| Prompt logging accident | Low | Critical | Code review + pytest asserts no prompt column |
| Custom endpoint SSRF | Low | Critical | Fixed URLs only in V1 |

---

## 26. Explicitly deferred future capabilities

- Ask BRIEFR / chat assistant
- AI agent / tool calling / workflow planner
- RAG / investigation memory / MemPalace
- Autonomous investigation workflow
- Browser automation
- STIX narrative export via LLM
- Multi-tenant per-org provider keys
- BRIEFR-hosted API keys (reseller model) — **permanently out**

Architecture leaves extension points: `task_class` registry, provider adapter interface, `ai_operations` feature column.

---

## 27. Final recommendation

### Challenge responses

| Question | Answer |
|----------|--------|
| Building infrastructure BRIEFR doesn't need? | **Partially** — full OmniRoute-style routing is overkill; **catalog + operation log + admin page** are justified by existing multi-provider router complexity. |
| Evolve router vs replace? | **Evolve** `llm_router.py` — tests and production paths prove it works. |
| AI Operations page justified? | **Yes** — 3 tasks × 4 providers × failover is already opaque to operators. |
| Which observability fields are realistic? | Latency, success, provider, model, retry index, token fields when present — **not** reliable cost on free tiers. |
| Quota-aware routing automate? | **No initially** — **advisory** warnings + manual overrides; automate skip only behind flag after data collection. |
| Highest maintenance risk providers? | **OpenRouter** (`:free` model churn) and **Gemini** (model rename/retirement); Groq rate limits tightly coupled to model choice. |
| Smallest solving architecture? | Recorder + catalog + admin read surfaces + health job; defer policy automation. |

### Proceed

1. Approve this plan.
2. Implement **PR-AI-1** first (observability, zero behaviour change).
3. Keep embeddings visible but not routed through LLM router.
4. Do not add chat/agent/RAG scope.

---

## Appendix A — Environment variables (AI-related)

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Groq provider |
| `GEMINI_API_KEY` | Gemini provider |
| `CEREBRAS_API_KEY` | Cerebras provider |
| `OPENROUTER_API_KEY` | OpenRouter provider |
| `GROQ_MODEL`, `GROQ_MODEL_SUMMARY` | Groq models |
| `GEMINI_MODEL` | Gemini model |
| `CEREBRAS_MODEL` | Cerebras model |
| `OPENROUTER_MODEL_*` | Per-task OpenRouter models |
| `GROQ_RPM_LIMIT`, `GROQ_TPM_LIMIT`, `GROQ_*` | Pacing defaults |
| `LLM_PRODUCT_EXTRACTION_*` | Scheduler product LLM |
| `DETECTION_CONTEXT_LLM_*` | Scheduler artifact LLM |
| `EMBEDDINGS_*` | Local embeddings (non-LLM API) |
| `ANTHROPIC_API_KEY` | **Deprecated** — unused by router |

---

## Appendix B — Scheduler interaction

| Job ID | AI role |
|--------|---------|
| `llm_product_extraction` | `structured_product_extraction` |
| `detection_context_llm` | `structured_detection_artifacts` |
| `embeddings_backfill` | Local embeddings (not generative) |
| `detection_context_sync` | **No AI** — deterministic cache |

Proposed: `ai_model_catalog_refresh` (weekly).

---

*Planning document only. Implementation branches: `cursor/ai-ops-pr-ai-N-*` (TBD after approval).*
