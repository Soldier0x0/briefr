# Daily brief webhooks — design spec

**Date:** 2026-08-26  
**Status:** Ready for planning  
**Plan:** `docs/superpowers/plans/2026-08-26-daily-brief-webhook-plan.md`  
**Format standard:** `docs/design/daily-brief-format.md`  
**Related:** `backend/webhooks/` (dispatch, destinations, 2k/4k caps), `backend/ai/summary.py` (PDF executive summary + template fallback), Admin → Webhooks event checkboxes.

Locked instance rules this spec does not reopen: no email, no per-user webhook URLs, no `tenant_id`, no OS push, KEV Forge gaps stay Forge (not a bell event). Watchlist/KEV **real-time** webhooks stay as they are.

---

## 1. Problem

Real-time Discord/Telegram alerts are one CVE at a time. An operator who was away overnight gets a scroll of `watchlist_alert` / `kev_alert` with no ranking and no “was the box quiet?” signal.

They asked for a **reporting** channel: end-of-day summary, early-morning “what happened while I was away,” or both, chosen independently, readable the way PDF export is readable (fixed sections, overflow rules, honest AI footer).

Facts in code today:

- Destinations are **instance-level** (`discord` / `telegram` / `generic` env + DB rows). Cap 20 per kind. Per-destination `event_types`.
- `ALL_EVENT_TYPES` has no digest/report event. Messages are free-form strings (`_format_watchlist_alert`).
- Users have `last_login_at`, but a shared webhook cannot honestly say “since you logged off” for multiple analysts.
- PDF executive summary already uses the LLM router with **template fallback** when keys are missing or the call fails (`generate_executive_summary` never raises).
- Core CVE feed works **without** AI keys. LLM is optional for PDF and product extraction.

## 2. Approaches considered

| Approach | Pros | Cons |
|----------|------|------|
| **A. Instance clock brief → existing webhooks** | Matches destination model; one Discord; timezone already `SCHEDULER_TIMEZONE` / `DEFAULT_TIMEZONE`; no new inbound channel | Not personalized per analyst |
| B. Per-user last_login window, still one webhook | Matches the spoken “logged off” line | Two users → contradictory windows on one channel; login ≠ “logged off” (sessions linger) |
| C. LLM-only narrative from the CVE table | Feels like a “report” | Hallucinations; fails closed without keys; contradicts PDF’s facts-first model |
| D. Email / digest inbox in the bell | Familiar | Email is locked out; the bell is an **alert tray**, not a report archive |

**Chosen: A**, with optional LLM **lede** only (Approach C as a non-authoritative overlay, same as PDF).

## 3. Product contract

### What ships

A **Daily brief**: a scheduled, windowed rollup posted to destinations that subscribe to event type `daily_brief`.

Two **slots**, independently enabled:

| Slot | Default local time | Window | Operator copy |
|------|--------------------|--------|----------------|
| `eod` | 18:00 | Previous 24 hours ending at fire time | End of day |
| `standup` | 07:00 | From the previous `eod` fire (or last 12h if EOD is off) | Overnight / morning |

Times are **hour + minute** in `SCHEDULER_TIMEZONE` (same IANA clock as other cron jobs). Defaults 18:00 and 07:00. Both off until the operator enables them.

Granularity:

- Enable EOD, standup, both, or neither (scheduler flags).
- Per destination: subscribe to `daily_brief` or not (same checkbox model as `watchlist_alert`). One event type covers both slots so a channel does not need two checkboxes.
- **Send test** / **Preview** on Admin → Webhooks (preview does not dispatch).

### What the window is *not*

Do **not** use `users.last_login_at` for webhook copy. Login is per-user; the webhook is shared. Sessions stay valid after the analyst walks away, so last_login is not “logged off.”

Honest masthead: `2026-08-25 18:00 → 2026-08-26 07:00 (Asia/Kolkata)`, not “since you logged off.”

In-app per-user “since last session” is out of scope (would belong in the alert tray, which is the wrong surface for a daily report).

### Actors

- **Admin** configures slots, times, destination subscription, preview, test send.
- **Anyone in the Discord/Telegram** reads the brief. There is no per-analyst variant in v1.

### Quiet windows

Still send. Headline `Quiet window.` plus zero COUNTS. A skipped quiet day is indistinguishable from a dead scheduler.

### Real-time alerts

Unchanged. The brief **does not** suppress `watchlist_alert` / `kev_alert` / `ioc_watchlist_hit`. It is an extra channel, not a digest-mode replacement (watchlist policy already has a per-CVE digest when every trigger is on).

## 4. Are AI API keys required?

**No. Facts never come from an LLM.**

| Layer | Needs keys? | Behavior without keys |
|-------|-------------|------------------------|
| Window, SQL rollups, section lists, COUNTS | No | Full brief |
| `// HEADLINE` | Optional | Deterministic template from COUNTS + top 3 IDs (`lede=template`) |
| Footer `lede=` | — | `template` or provider name (`groq`, `gemini`, …) like PDF `aiFooterNoteForSource` |

When keys exist **and** `DAILY_BRIEF_LLM_ENABLED=1` (default **0** so a newly subscribed Discord is not a surprise LLM spend): call `chat_completion_task("pdf_summary", …)` with `context_type="daily_brief"` and `context_id="{slot}:{local_date}"`. Prompt input is **only** the already-built COUNTS + truncated list lines (no raw CVE descriptions dump). Output: 1–3 sentences. If the call fails, empty, or invents an ID not in the fact list → drop to template. Timeout = existing `llm_provider_timeout()`. This is the same never-raise contract as `generate_executive_summary`.

Do **not** add a fourth `LLMTask` in v1. Reuse the PDF summary failover chain (Groq 120b → …). Metering still lands in `ai_operations` via `context_type`.

Do **not** send the LLM the webhook URL, secrets, or ops error strings that might include host paths — OPS lines may be included as `{job_id} — {error_class}` only.

## 5. Data collected (local DB only)

Window `[start_utc, end_utc)` computed from slot + timezone.

| Count / list | Source of truth |
|--------------|-----------------|
| KEV new | `kev_deadlines.date_added` in window (join `cves` for severity/title) |
| Stack matches | Same matching rules as `kev_alert` (admin My Stack CPE / structured products — **not** description LIKE, **not** `BRIEFR_STACK_TERMS` fallback) intersected with KEV-new **or** new Critical/High `cves.published` in window |
| Watchlist | Successful `watchlist_alert` rows in `webhook_delivery_log` **or** `user_notifications` category `watchlist` created in window — prefer notifications so muted webhooks still appear in the brief |
| IOC hits | `ioc_watchlist_hit` notifications / matching retro hits timestamped in window |
| Critical/High new | `cves.published` in window, severity in `CRITICAL`/`HIGH` |
| Ops issues | `user_notifications` scope operator (`job_error`, `api_key_unhealthy`, `webhook_failure`) created in window |

Caps and overflow: `docs/design/daily-brief-format.md`.

No NVD fetch on the job path. Empty DB → quiet brief, not an ingest kickoff.

## 6. Dispatch and dedupe

- `dispatch_event("daily_brief", text, dedupe_key="{slot}:{local_date}")`.
- Generic payload: existing `webhook_json_payload` **plus** `brief` (structured dict: slot, window, counts, items, lede_source) so collectors are not Discord-truncated.
- `skip_dedupe=True` only for **Send test**.
- Manual **Run now** on the scheduler job uses today’s key (second run same slot/date is a no-op thanks to destination dedupe). Preview never writes dedupe.

Env destinations with unset `DISCORD_WEBHOOK_EVENTS` currently mean **all** `ALL_EVENT_TYPES`. Adding `daily_brief` would auto-subscribe those. **Mitigation:** jobs default **off**. Adding the event type is still a behavior change for “all events” filters — document it. DB destinations with an explicit list do not auto-gain the event (operator checks the box).

## 7. Config (admin Config + `.env`)

| Key | Type | Default | Apply |
|-----|------|---------|--------|
| `DAILY_BRIEF_EOD_ENABLED` | bool | `0` | scheduler reschedule |
| `DAILY_BRIEF_STANDUP_ENABLED` | bool | `0` | scheduler reschedule |
| `DAILY_BRIEF_EOD_HOUR` / `_MINUTE` | int | 18 / 0 | scheduler reschedule |
| `DAILY_BRIEF_STANDUP_HOUR` / `_MINUTE` | int | 7 / 0 | scheduler reschedule |
| `DAILY_BRIEF_LLM_ENABLED` | bool | `0` | immediate |

Timezone: `SCHEDULER_TIMEZONE` (do not invent a fourth tz key). Display of window strings may use `DEFAULT_TIMEZONE` only if scheduler tz is unset — implementer uses the same tz object as `CronTrigger(..., timezone=sched_tz)`.

If EOD and standup would fire in the same minute, standup waits until EOD in that run (single job `daily_brief_tick` that checks “which slots are due in this minute”) **or** two cron jobs with coalesce. Prefer **two job ids** (`daily_brief_eod`, `daily_brief_standup`) mapped in `_JOB_RUN_MAP` so Run now is obvious. If both enabled at the same clock time, standup window still starts at previous EOD watermark, not a nested 0-length window — if computed window duration `< 15 minutes`, skip standup and log (do not send an empty overlapping brief).

Watermark: `sync_state` key `daily_brief:last_eod_end` (ISO UTC) written after a successful EOD dispatch (or after a quiet EOD that still sent). Standup reads it.

## 8. Admin UI

- **Webhooks page:** `EVENT_OPTIONS` adds `{ id: 'daily_brief', label: 'Daily brief (EOD / standup)' }`. HelpTip: “Scheduled rollup; enable slots under Config. Does not replace real-time KEV/watchlist alerts.”
- Same page: **Preview brief** (slot select) renders `<pre>` using the format standard (tokens, mono, dark). **Send test** uses skip_dedupe.
- **Config** scheduler_cron card: the five flags/hours (LLM toggle in the AI/LLM section, not cron).
- Scheduler list shows both jobs; disabled flags → job still registered but run is a no-op with `skipped: disabled` in last-run history (same pattern as other gated jobs).

No new analyst tab. No PDF of the brief in v1.

## 9. Error handling

- Builder exceptions → log + **do not** send a partial hallucinated list; operator notification `job_error` is enough.
- Dispatch failures: existing webhook engine retries + `webhook_failure` notifications. Do not advance EOD watermark if **no** destination accepted the message (`sent` empty and at least one destination was subscribed). If zero destinations subscribe, skip send, do not error-spam (log `reason: no_subscribers`).
- LLM failure → template lede, still send.

## 10. Testing

- Collector: fixture CVEs / KEV / notifications in and out of window.
- Formatter: quiet example exact string; overflow drops `ops` before `kev`; Discord 2000 respected.
- LLM: monkeypatched completion that cites a fake CVE is discarded.
- Engine: dest without `daily_brief` in `event_types` is skipped.
- Jobs: disabled flag → no dispatch.

## 11. Out of scope

Email; per-user webhooks; last_login windows; weekly/monthly briefs; attaching PDFs to Discord; changing real-time alert copy; using the alert tray as a report archive; inventing `job_id` on `resource_metrics`; KEV backlog in the brief (Forge-only, same as bell).

## 12. Docs to update when implementing

`PRODUCT_STATUS.md`, `API_REFERENCE.md` (event type + config keys + preview/test routes), `backend/.env.example`, Webhooks help copy.
