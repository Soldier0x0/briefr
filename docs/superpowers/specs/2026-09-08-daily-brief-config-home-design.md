# Daily brief page enablement + config home — design

**Status:** requirements (session-settled; ready to plan).  
**Not for:** auto-subscribe Discord to `daily_brief`; URL cascade; systemd unit rewrite; dumping `DATABASE_URL` / `JWT_SECRET` out of env; SQLite PR #752.  
**Product authority:** this spec until ship; then `docs/PRODUCT_STATUS.md`.  
**Parent (slots already shipped):** `docs/superpowers/specs/2026-08-26-daily-brief-webhook-design.md`.

## Problem

Operators treat Admin → Daily brief **Slot** as the schedule. It is only Preview / Send test. Both cron slots already exist as independent flags (`DAILY_BRIEF_EOD_ENABLED`, `DAILY_BRIEF_STANDUP_ENABLED`, default off). The page copy says “enable under Config,” then Config **GET `/api/admin/config` omits those keys**, so the cron section shows empty/off after save.

A Discord dest with an explicit `DISCORD_WEBHOOK_EVENTS` list from `.env.example` (`kev_alert,backup_failure,health`) never gains `daily_brief`. The page shows zero subscribers. Slot changes do nothing. Real-time KEV/watchlist stay other event types.

Webhook URLs and most operator toggles still *feel* like `.env` work because process env wins, secrets skip `app_settings` without `BRIEFR_SETTINGS_KEY` (ADR-006), and `.env.example` keeps growing as if it were the live ledger.

## Ideation survivors

| Kept | Rejected | Why rejected |
|------|----------|--------------|
| Two independent Enable switches + hours on Daily brief; Slot stays Preview/Test | One dropdown that enables a slot | Preview needs one window; enablement is already two bools |
| One `daily_brief` subscription covers both slots | Two event types | Shipped contract; one Discord checkbox |
| Honest zero-subscriber CTA → Webhooks | Auto-tick `daily_brief` when enabling a slot | Silent add onto a KEV-only dest |
| Wave 1 page, then Wave 2 config home | Config-home-only | Page is the trap they hit |
| Process env still wins; secrets in DB only with `BRIEFR_SETTINGS_KEY` | “Put everything in Postgres, delete `.env`” | Breaks systemd/Docker pins and ADR-006 |
| GET config exposes daily-brief keys + pin/secret-persist honesty | Keep hardcoded GET dict forever | Config UI cannot show flags it never receives |

## Product contract

### Wave 1 — Daily brief page (do first)

- **Enable EOD** and **Enable standup** are independent switches on Admin → Daily brief. Both may be on. Saving uses existing `POST /api/admin/config` `{key,value}` (`1`/`0`). Jobs already no-op while disabled; no new event type.
- **Hour and minute** for each enabled slot sit beside that switch (0–23 / 0–59, `SCHEDULER_TIMEZONE`). Caption names the timezone. Defaults remain 18:00 and 07:00.
- **Slot** is labeled **Preview / test slot**. Changing it does not enable, disable, or subscribe. Preview and Send test keep using that slot (test still works while cron is off).
- **Subscribe line:** if zero enabled dests have `daily_brief`, treat as an alert with the Webhooks link (not a muted footnote). Copy: destinations must tick **Daily brief (EOD / standup)**; that is not real-time KEV/watchlist.
- **GET `/api/admin/config`** includes `DAILY_BRIEF_EOD_ENABLED`, `DAILY_BRIEF_STANDUP_ENABLED`, hours/minutes (bools as `"0"`/`"1"` strings like sibling flags), and `DAILY_BRIEF_LLM_ENABLED` in `ml`. After save, reload shows the saved values (today they vanish because the GET dict omits them).
- HelpTip: real-time alerts stay on Webhooks event checkboxes. This page is the scheduled rollup.

### Wave 2 — Config home (after Wave 1)

- Operator toggles and webhook URLs saved in Admin persist to `app_settings` when ADR-006 allows it. `.env` is bootstrap / process pin, not the operator ledger.
- GET config adds non-secret **meta**: `settings_key_configured` (bool), `process_pinned_keys` (writable keys present in `PROCESS_ENV_KEYS` at import — names only).
- API keys & config: badge **pinned by process env** on those keys; Save still writes process `os.environ` for this run but copy says restart will restore the pin.
- Saving a **secret** without `BRIEFR_SETTINGS_KEY` returns an explicit warning: not stored in DB; lost on restart unless already in host env / `.env`. Do not write plaintext secrets to `app_settings`.
- `.env.example` regroups: **bootstrap** (`DATABASE_URL`, `JWT_SECRET`, `BRIEFR_SETTINGS_KEY`, `ALLOWED_ORIGINS`, …) vs **optional process pins**. Comment that daily-brief and most scheduler bools belong in Admin. Keep listed keys; do not require operators to copy `DAILY_BRIEF_*` into `.env` to use the feature.
- Help on Webhooks legacy bootstrap and Daily brief: `DISCORD_WEBHOOK_EVENTS` explicit lists do not auto-gain `daily_brief`.

### Out of scope

- Auto-subscribe or rewrite `DISCORD_WEBHOOK_EVENTS` on enable.
- Removing process-env precedence.
- Encrypting non-secret rows.
- Per-dest report templates, inbound Discord commands, email.

## Actors

- Operator on Daily brief, Webhooks, API keys & config.
- Scheduler jobs `daily_brief_eod` / `daily_brief_standup` (unchanged collect/dispatch).

## Risks

- GET config is a hand-maintained dict; Wave 1 must add the missing keys or the page will lie after save.
- `PROCESS_ENV_KEYS` is import-time; Docker `-e` pins look identical to intentional systemd pins — honesty, not unblock.
- Without `BRIEFR_SETTINGS_KEY`, Wave 2 cannot make webhook URLs survive deploy `.env` refresh — that is ADR-006, not a bug to paper over.
