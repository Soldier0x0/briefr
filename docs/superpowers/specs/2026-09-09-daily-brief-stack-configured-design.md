# Daily brief: omit My Stack unless configured — design

**Status:** requirements (session-settled; ready to plan).  
**Not for:** wallboard tiles, analyst BRIEF “Stack activity”, header Asset wizard, unifying session vs admin stack UIs.  
**Product authority:** this spec until ship; then `docs/PRODUCT_STATUS.md`.  
**Parents:** `docs/design/daily-brief-format.md`, `docs/superpowers/specs/2026-08-26-daily-brief-webhook-design.md`.

## Problem

Daily brief **matching** already skips My Stack when admin assets are empty (`_collect_stack` returns `[], 0`). Human copy does not: At a glance always prints `Matches My Stack: 0`. Operators with no stack still see “My Stack” on Discord, Telegram, generic HTTPS, and Admin preview.

Quiet-window examples in the format doc encode that lie.

## Ideation survivors

| Kept | Rejected | Why rejected |
|------|----------|--------------|
| Omit stack glance line, list field, and Summary stack sentences when admin assets are empty | Print “My Stack: not configured” | Still names a stack that is not in play |
| Gate on `get_alert_stack_assets()` (same list the matcher uses) | Gate on header session My Stack | Report already uses admin DB profile / `stack_terms` |
| Keep `counts.stack_matches` (0) plus `stack_configured: false` on structured `brief` | Drop the count key from JSON | Breaks COUNT_KEYS / machine consumers; honesty is the human report |
| Daily brief channels + Admin preview only | Also hide wallboard / analyst BRIEF stack sections | Different surfaces; not this report |

## Product contract

**Rule:** If admin My Stack is configured, the report includes it. If not, it does not appear.

Configured means `get_alert_stack_assets(db)` is non-empty (profile OS/apps or keyword `stack_terms` on the latest active admin `user_preferences`). Empty both → unconfigured.

When **unconfigured**:

- At a glance has **five** lines (no `Matches My Stack`).
- No Discord/Telegram field titled **My Stack**.
- Summary does not mention stack matches.
- Admin Daily brief preview At a glance matches the same five lines.
- `brief.stack` stays `[]`; `brief.counts.stack_matches` stays `0`.
- `brief.stack_configured` is `false`.

When **configured**:

- At a glance includes `Matches My Stack: {n}` even if `n` is 0 (honest zero).
- List field **My Stack** still only renders when there are rows (unchanged).
- Summary may mention stack matches only when `n > 0` (unchanged triage, additionally gated on configured).
- `brief.stack_configured` is `true`.

Never print “not configured” as a glance line.

## Implementation sketch

- Add `DailyBrief.stack_configured: bool` (default `False`).
- `collect_daily_brief` sets it from `bool(assets)` after `get_alert_stack_assets`.
- Single `glance_lines(brief) -> list[str]` used by `_glance_text`, `format_daily_brief_text`, `format_daily_brief_html` (via `_glance_text`), and Discord embed glance field.
- `template_headline`: stack sentence only if `brief.stack_configured and counts["stack_matches"]`.
- `brief_to_payload` includes `stack_configured`.
- Frontend: small helper (next to `dailyBriefCopy.js`) builds glance lines from `brief.stack_configured` + `brief.counts`; Daily brief page uses it. Do not hardcode six lines.

## Docs

- `docs/design/daily-brief-format.md`: At a glance keys are six **when configured**; omit Matches My Stack when not. Quiet example has no stack line.
- `docs/API_REFERENCE.md` preview/payload: `stack_configured`.
- `docs/PRODUCT_STATUS.md` Daily brief row: glance omits My Stack unless admin stack is configured.

## Out of scope

- Auto-creating a stack.
- Changing `filter_cves_matching_assets` or CPE matching.
- Header vs admin identity copy on Webhooks.
- Analyst `/api/brief` “Stack activity” section.

## Risks

- Tests that construct `DailyBrief(..., stack_matches=1)` without `stack_configured=True` will stop showing the glance line — update those fixtures.
- Overflow drop order still lists `stack`; no change needed when the field is absent.
