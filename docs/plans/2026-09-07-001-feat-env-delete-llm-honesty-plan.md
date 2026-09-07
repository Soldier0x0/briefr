---
title: ENV webhook delete and LLM honesty - Plan
type: feat
date: 2026-09-07
topic: env-delete-llm-honesty
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: ce-brainstorm
execution: code
---

# ENV webhook delete and LLM honesty - Plan

## Goal Capsule

- **Objective:** Reserved ENV webhook Delete removes that card for good (tombstone), and AI operations tell the truth about DNS/network failures without a payload 500, with an operator disable for unused free-tier providers.
- **Product authority:** `docs/superpowers/specs/2026-09-07-env-delete-llm-honesty-design.md`. Surrounding #820 round-robin and per-dest report templates are not this plan.
- **Open blockers:** none. Host DNS remains an ops concern; this plan does not claim to prevent resolver outages.

---

## Product Contract

### Summary

Operators delete the reserved ENV Discord/Telegram/generic **card** and its in-process URL without a 409 resurrection. Other dest rows that copied the same URL keep delivering. LLM Activity names DNS and network failures, trips circuits, and shows a short excerpt on the row. View payload always returns a body. Providers can be disabled without deleting keys.

### Problem Frame

ENV Delete today clears persistence then 409s while process env rebuilds the card. LLM hops that never left the host (`[Errno -3] Temporary failure in name resolution`) are labeled unknown error, often skip circuit accounting, and View payload 500s on truncated `messages_json`. Free-tier keys stay in the failover chain with 0% success.

### Key Decisions

- Tombstone + pop process env; HTTP 200; no URL cascade. (session-settled: user-directed — chosen over 409/hide-card: operator wants that card gone; other dests keep their URL copies) Governs R1, R2, R3
- Classify dns/network; fail that provider in the job session; do not skip the whole chain. (session-settled: user-approved — chosen over full #820 round-robin: dead free hops would get more share) Governs R4, R5
- Activity excerpt + payload 200. (session-settled: user-directed — chosen over Application logs as the only RCA: View payload 500 hid the excerpt) Governs R6, R7
- Per-provider enable default on. (session-settled: user-approved — chosen over deleting keys or round-robin) Governs R8

<!-- ce-section: work-relationships -->
### How This Work Fits Together

This plan owns ENV dest delete honesty and LLM attempt honesty/disable.

- GitHub #820 round-robin, adaptive weights, new frontier vendors — **Can proceed independently of** this plan; **Still to decide**. Path: later spec. **Shares** the same router.
- Per-Discord custom report templates — **Can proceed independently of** this plan. Multiple dests + `event_types` already ship.
- Host DNS / systemd secret removal — **ops**, not app. Tombstone only ignores injected URLs.

### Actors

- A1. Operator on Admin → Webhooks and AI operations.
- A2. Scheduler LLM jobs (`product_extraction`, `detection_context`) using the failover chain.

### Requirements

#### Webhooks

- R1. Reserved dest Delete (`discord` / `telegram` / `generic`) clears app_settings keys, pops those keys from process env, deletes that row, and writes a tombstone so env bootstrap does not recreate that id after restart.
- R2. That Delete returns 200. Optional `warning` names leftover systemd key names only. Never 409 for process env. Never revoke discord.com. Never delete other dest ids.
- R3. Saving a non-empty matching URL/token on API keys & config clears the tombstone so ENV bootstrap may return. Add destination still cannot use reserved ids.

#### LLM attempts

- R4. Failed LLM attempts classify `dns` and `network` when the exception matches resolver/connect failures; Activity labels them `dns failure` / `network error`. Persist redacted `error_detail` (max 200 chars) on the operation row.
- R5. Those failures call `record_source_failure`. `dns` (and non-HTTP `network`) skip that provider for the rest of the current job session. Other providers in the chain still run. Tokens stay unset when the provider was not billed.
- R6. GET payload is 200 when a row exists. Invalid `messages_json` yields empty `messages`, `messages_parse_ok=false`, and `messages_raw`. Truncate per message content, not by slicing JSON. Retry is 400 when messages cannot replay.
- R7. View payload UI renders excerpt even when parse failed. No error toast for invalid JSON on a successful 200.
- R8. Immediate-apply per-provider enabled flags (default on). Disabled providers are not called and show disabled on the Providers tab. Keys remain.

### Key Flows

- F1. Delete ENV Discord
  - **Trigger:** Confirm delete on dest `discord`.
  - **Actors:** A1
  - **Steps:** Persist clear + pop + tombstone + row delete. List omits `discord`. Dest `brief` unchanged.
  - **Covered by:** R1, R2
- F2. DNS during product extraction
  - **Trigger:** Cerebras raises name-resolution error; Groq still keyed.
  - **Actors:** A2
  - **Steps:** Record Cerebras fail as `dns` with excerpt; skip Cerebras for later CVEs in the job; try Groq/Gemini. Activity shows `dns failure` without opening payload.
  - **Covered by:** R4, R5
- F3. Open truncated payload
  - **Trigger:** View payload on a stored failure whose JSON was truncated.
  - **Actors:** A1
  - **Steps:** Modal shows excerpt + raw text. No 500 toast.
  - **Covered by:** R6, R7

### Acceptance Examples

- AE1. Process env still has `DISCORD_WEBHOOK_URL` after Delete
  - **Covers R1, R2.**
  - **Given:** systemd-injected URL; dest `brief` has the same URL string.
  - **When:** operator deletes `discord`.
  - **Then:** 200; no `discord` card after restart; `brief` still listed and still subscribed.
- AE2. Errno -3 on Cerebras
  - **Covers R4, R5.**
  - **Given:** Cerebras key set; resolver fails for that host.
  - **When:** scheduler runs product extraction.
  - **Then:** row `error_class=dns`; `error_detail` contains name resolution; circuit counts a failure; Groq may still succeed; tokens null.
- AE3. Disable OpenRouter
  - **Covers R8.**
  - **Given:** `OPENROUTER_API_KEY` set; enable flag off.
  - **When:** `chat_completion_task` runs.
  - **Then:** OpenRouter is not attempted.

### Scope Boundaries

- In: reserved dest tombstone delete; LLM class/circuit/session skip; error_detail; payload 200; provider enable flags; PRODUCT_STATUS + API_REFERENCE.
- Out: #820; URL cascade delete; Discord API revoke; per-dest templates; host DNS; new LLM vendors.

### Outstanding Questions

- None blocking. **Deferred to Planning:** tombstone key names and Alembic revision id.
