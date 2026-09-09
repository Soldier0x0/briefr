---
title: Daily brief page enablement and config home - Plan
type: feat
date: 2026-09-08
topic: daily-brief-config-home
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

# Daily brief page enablement and config home - Plan

## Goal Capsule

- **Objective:** Operators enable EOD and standup independently on Daily brief, see true cron state, and understand that Admin Config / `app_settings` is the operator ledger (process env still wins). Surrounding auto-subscribe and env-abolition are not this plan.
- **Product authority:** `docs/superpowers/specs/2026-09-08-daily-brief-config-home-design.md`. Slot semantics stay Preview/Test per `docs/superpowers/specs/2026-08-26-daily-brief-webhook-design.md`.
- **Open blockers:** none (deferred: systemd pin removal is ops).

---

## Product Contract

### Summary

Wave 1 puts Enable EOD / Enable standup plus hours on Daily brief and fixes GET config so those keys round-trip. Wave 2 shows process-env pins and secret-persist-without-key warnings, and regroups `.env.example`. One `daily_brief` subscription still covers both slots. Auto-subscribe is out.

### Problem Frame

Slot is a preview picker. Cron flags default off and are omitted from GET `/api/admin/config`. Explicit env event lists omit `daily_brief`. Secrets skip DB without `BRIEFR_SETTINGS_KEY`. Operators edit `.env` because the UI never owns the schedule or explains precedence.

### Key Decisions

- Independent enables on Daily brief; Slot stays Preview/Test. (session-settled: user-directed — chosen over either/or dropdown as schedule: both slots already exist as two bools) Governs R1, R2, R3
- Sequence Wave 1 then Wave 2. (session-settled: user-directed — chosen over config-home-only or auto-subscribe: page is the trap) Governs R1–R9
- Process env wins; secrets need `BRIEFR_SETTINGS_KEY` for DB. (session-settled: user-approved — chosen over “everything in Postgres”: ADR-006 + systemd) Governs R6, R7, R8

<!-- ce-section: work-relationships -->
### How This Work Fits Together

This plan owns Daily brief enable UX and config-home honesty.

- Auto-subscribe Discord to `daily_brief` — **Can proceed independently**; **rejected here**. Path: later spec if wanted.
- ENV dest tombstone (#892) — **already shipped**; Wave 2 must not undo tombstone or process-env warning on Delete.
- Real-time KEV/watchlist events — **unchanged**; **Shares** Webhooks `event_types`.

### Actors

- A1. Operator on Daily brief, Webhooks, API keys & config.
- A2. Scheduler `daily_brief_eod` / `daily_brief_standup`.

### Requirements

#### Wave 1 — Daily brief page

- R1. Daily brief shows two independent Enable switches (EOD, standup). Both may be on. Persist via `POST /api/admin/config` with existing keys. Disabled jobs stay registered and no-op (`run_daily_brief_slot`).
- R2. Each slot has hour (0–23) and minute (0–59) fields. Caption uses `SCHEDULER_TIMEZONE`. Defaults 18:00 / 07:00. Hour/minute POST uses existing scheduler_reschedule keys.
- R3. Control labeled **Preview / test slot** (`eod` | `standup`) only feeds Preview and Send test. It does not write enable flags or `event_types`.
- R4. Zero enabled destinations with `daily_brief` is an alert + Webhooks link. Copy: tick **Daily brief (EOD / standup)**; that is not real-time KEV/watchlist.
- R5. `GET /api/admin/config` returns `DAILY_BRIEF_EOD_ENABLED`, `DAILY_BRIEF_STANDUP_ENABLED`, `DAILY_BRIEF_EOD_HOUR`, `DAILY_BRIEF_EOD_MINUTE`, `DAILY_BRIEF_STANDUP_HOUR`, `DAILY_BRIEF_STANDUP_MINUTE` under `scheduler` (bools as `"0"`/`"1"`), and `DAILY_BRIEF_LLM_ENABLED` under `ml`. Reload after save shows stored values.

#### Wave 2 — Config home

- R6. GET config includes `meta.settings_key_configured` (bool) and `meta.process_pinned_keys` (list of writable key names in `PROCESS_ENV_KEYS`). No secret values.
- R7. API keys & config badges **pinned by process env** on R6 keys. Copy: this-run Save updates the process; restart restores the pin.
- R8. POST `/config` and `/config/apply-all` for a secret-typed key when `BRIEFR_SETTINGS_KEY` is unset return `persisted_to_db: false` and a warning that the value is not in `app_settings`. Do not store plaintext secrets in DB.
- R9. `.env.example` splits bootstrap vs optional pins; comments say daily-brief flags belong in Admin. Do not require `DAILY_BRIEF_*` in `.env` to use the feature. Note that an explicit `DISCORD_WEBHOOK_EVENTS` list does not include `daily_brief` unless added.

### Key Flows

- F1. Enable both slots
  - **Trigger:** Operator turns on EOD and standup on Daily brief, hours 18:00 and 07:00.
  - **Actors:** A1, A2
  - **Steps:** Two POST `/config` (or sequential). GET config shows `"1"`. Cron fires; `run_daily_brief_slot` does not skip for `disabled`. Dest still needs `daily_brief` or dispatch skips.
  - **Covered by:** R1, R2, R5
- F2. Preview slot vs enable
  - **Trigger:** Standup enabled, Preview/test slot = End of day, Preview.
  - **Actors:** A1
  - **Steps:** Preview builds EOD copy. Standup flag stays on.
  - **Covered by:** R3
- F3. Secret save without settings key
  - **Trigger:** Save Discord URL; `BRIEFR_SETTINGS_KEY` unset.
  - **Actors:** A1
  - **Steps:** `os.environ` updates this process; response warns not in DB.
  - **Covered by:** R8

### Acceptance Examples

- AE1. Both enables
  - **Covers R1, R5.**
  - **Given:** flags off; Discord subscribed to `daily_brief`.
  - **When:** operator enables EOD and standup on Daily brief.
  - **Then:** GET config both `"1"`; Send test still works; scheduled jobs no longer skip `disabled`.
- AE2. Zero subscribers
  - **Covers R4.**
  - **Given:** Discord events `kev_alert` only.
  - **When:** Daily brief loads.
  - **Then:** alert CTA to Webhooks; Send test skipped no subscribers.
- AE3. GET round-trip
  - **Covers R5.**
  - **Given:** `DAILY_BRIEF_EOD_ENABLED=1` in env or DB.
  - **When:** GET `/api/admin/config`.
  - **Then:** `scheduler.DAILY_BRIEF_EOD_ENABLED` is `"1"` (not missing / `""`).
- AE4. Process pin
  - **Covers R6, R7.**
  - **Given:** `DISCORD_WEBHOOK_URL` in `PROCESS_ENV_KEYS`.
  - **When:** API keys page renders.
  - **Then:** pin badge; `meta.process_pinned_keys` contains that name.
- AE5. No settings key
  - **Covers R8.**
  - **Given:** `BRIEFR_SETTINGS_KEY` unset.
  - **When:** POST Discord URL.
  - **Then:** `persisted_to_db` false; warning present; `app_settings` has no plaintext URL.

### Scope Boundaries

- In: Daily brief enable/hours UI; GET config daily-brief keys; subscribe alert copy; config meta; persist warning; `.env.example` regroup; PRODUCT_STATUS + API_REFERENCE.
- Out: auto-subscribe; dropping process-env precedence; plaintext secret rows; systemd edits; new webhook event types; email.

### Outstanding Questions

- None blocking. **Deferred:** whether a later spec auto-adds `daily_brief` to env dests on first enable.

---

## Planning Contract

### Key Technical Decisions

- KTD1. Extend the existing hardcoded `_get_config_response` dict rather than generating GET from `config_schema` in this PR. Schema-driven GET is larger than Wave 1. Rationale: one missing cluster (`DAILY_BRIEF_*`) is the lie; full generator is a follow-up.
- KTD2. Daily brief page reads `GET /config` + destinations; writes `POST /config` like `AiOperationsPage` provider switches. No new routes. Rationale: flags already writable; GET was incomplete.
- KTD3. `persist_operator_setting` returns whether the row was stored; config routes add `persisted_to_db` + `warning`. Rationale: client cannot infer skip from 200 today.
- KTD4. `meta.process_pinned_keys` = `sorted(WRITABLE_CONFIG_KEYS & PROCESS_ENV_KEYS)`. Rationale: do not dump the whole process env.
- KTD5. Enable flags do not need `_CONFIG_KEY_TO_JOBS` entries; jobs always registered, skip inside `run_daily_brief_slot`. Hour/minute already reschedule.

### Technical Approach

Reuse `ToggleSwitch`, `adminApi.postJson('/config')`, `validate_value`, ADR-006 skip path. Daily brief toolbar grows a schedule row above Preview/test. CSS stays in `DailyBriefPage.css` (tokens, density). Tests: `test_admin_config.py` for GET keys + persist warning; frontend node:test for subscribe copy / both switches (pattern `toastCopy.test.js` or new `DailyBriefPage` extract of pure helpers if the page stays untestable without a DOM harness — prefer extracting `dailyBriefDeliveryCopy({ subscribedCount })` and enable payload builders).

### Assumptions

- `BRIEFR_SETTINGS_KEY` remains optional. Wave 2 documents it; does not force-generate it.
- PRODUCT_STATUS line “Admin Save still mirrors to `.env`” is stale vs current `set_config` (no `set_key` except JWT generate). Wave 2 docs match code.

### Sequenced work

1. U1 GET config daily-brief keys (unblocks honest UI).
2. U2 Daily brief page schedule controls + CTA (Wave 1 shippable).
3. U3 persist warning + meta (Wave 2 API).
4. U4 API keys badges + `.env.example` + living docs.

---

## Implementation Units

### U1. GET config exposes daily-brief keys

- **Goal:** Config GET round-trips DAILY_BRIEF flags and hours.
- **Requirements:** R5, AE3
- **Files:** `backend/routers/admin/config.py`, `backend/tests/test_admin_config.py`
- **Approach:** Add keys to `scheduler` and `DAILY_BRIEF_LLM_ENABLED` to `ml` with the same `_env` / `_env_int` helpers and defaults as `reports/daily_brief.py` / scheduler (`"0"`, 18, 0, 7, 0).
- **Tests:** `test_config_includes_daily_brief_defaults`; `test_config_daily_brief_enabled_round_trip` POST then GET `"1"`.
- **Depends on:** none

### U2. Daily brief schedule UI

- **Goal:** Enable both slots and hours on the page; Slot is Preview/test; zero subscribers is an alert.
- **Requirements:** R1–R4, AE1, AE2
- **Files:** `frontend/src/pages/admin/DailyBriefPage.jsx`, `frontend/src/pages/admin/DailyBriefPage.css`, `frontend/src/pages/admin/dailyBriefCopy.js` (new, testable copy helpers), `frontend/src/pages/admin/dailyBriefCopy.test.js`, `docs/PRODUCT_STATUS.md` Daily brief row, `docs/API_REFERENCE.md` GET config keys
- **Approach:** Load GET `/config`. Two `ToggleSwitch` + hour/minute inputs. Busy lock all schedule controls like providers. Slot `Select` label **Preview / test slot**. Delivery uses `dailyBriefDeliveryCopy`.
- **Tests:** copy helper — 0 dests → alert text; ≥1 → “Sends to …”. Optional: payload `value: next ? '1' : '0'`.
- **Depends on:** U1 (page will show `""` as off until GET exists)

### U3. Config meta and persist warning

- **Goal:** Clients can see pins and secret-not-in-DB.
- **Requirements:** R6, R8, AE4, AE5
- **Files:** `backend/operator_settings.py`, `backend/routers/admin/config.py`, `backend/tests/test_operator_settings.py`, `backend/tests/test_admin_config.py`
- **Approach:** `persist_operator_setting` returns `{"persisted_to_db": bool, "warning": str | None}`. Routes merge into JSON. `meta` on GET.
- **Tests:** secret POST without settings key → `persisted_to_db` false; with key → true (existing encrypt tests). GET `process_pinned_keys` contains monkeypatched writable key.
- **Depends on:** none (can overlap U2)

### U4. Config UI honesty + env.example

- **Goal:** Operators see pins and stop treating `.env.example` as the live SSOT.
- **Requirements:** R7, R9
- **Files:** `frontend/src/pages/admin/ApiKeysPage.jsx`, `backend/.env.example`, `docs/PRODUCT_STATUS.md` Admin / operator settings sentences, `docs/API_REFERENCE.md` config GET `meta`, `docs/decisions/ADR-006-encrypted-app-settings-secrets.md` if “Save still writes `.env`” is still claimed
- **Approach:** Badge when `meta.process_pinned_keys` includes `envKey`. Toast `data.warning`. `.env.example` two comment banners; keep keys.
- **Tests:** none required beyond U3 API; frontend copy is HelpTip/subtitle.
- **Depends on:** U3

---

## Verification Contract

- Backend: `cd backend && pytest tests/test_admin_config.py tests/test_operator_settings.py tests/test_daily_brief_admin.py -q`
- Frontend: `cd frontend && npm run test:unit` (includes new `dailyBriefCopy.test.js`)
- Merge gate: `./scripts/verify-local.sh`
- Docs: PRODUCT_STATUS Daily brief + Admin operator-settings sentences; API_REFERENCE GET config.

---

## Definition of Done

- Wave 1: U1+U2 green tests; operator can enable **both** slots on Daily brief and GET shows them; zero-subscriber alert visible.
- Wave 2: U3+U4; secret-without-key warning; pin badge; `.env.example` regrouped.
- No auto-subscribe. No plaintext secret rows. Process env still wins.
- Living docs updated in the same PR as behavior (or the Wave PR that ships it).
