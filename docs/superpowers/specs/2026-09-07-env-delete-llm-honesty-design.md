# ENV webhook delete + LLM honesty — design

**Status:** requirements (session-settled; ready to plan).  
**Not for** GitHub #820 round-robin, new frontier vendors, Docker, SQLite PR #752.  
**Product authority:** this spec until ship; then `docs/PRODUCT_STATUS.md`.

## Problem

Operators cannot remove the reserved ENV Discord (Telegram, generic) **card** while systemd/process env still injects the URL. Delete already clears `app_settings` and the row, then **409**s; `load_env_destinations` rebuilds the card.

LLM Activity labels most failures **unknown error**. Observed production excerpts were `[Errno -3] Temporary failure in name resolution` (DNS). Those hops never reached the provider (tokens `—`). Failover still walks every keyed provider. Exception paths do not always call `record_source_failure`, so circuits stay closed and the next CVE repeats the same dead hops.

View payload **500**s when `messages_json` is not a JSON array (truncation at 32k). The useful text is already in `response_excerpt`.

## Ideation survivors

| Kept | Rejected | Why rejected |
|------|----------|--------------|
| Tombstone + pop URL on reserved delete; HTTP **200**; card gone even if systemd still has the secret | Keep 409 / hide-disabled / preflight-block | Operator asked for card + in-process URL gone; 409 is the current bug-as-designed |
| Delete **one dest id** only | Cascade-delete every dest whose `config.url` matches | Other cards (`brief`) keep their own URL copy; cascade is easy to regret |
| Classify `dns` / `network`; `record_source_failure`; skip that provider for the rest of `llm_job_session` | Skip the entire remaining chain on first DNS | Groq may still resolve when Cerebras does not |
| Operator **disable** per provider without deleting the key | Issue #820 round-robin + YAML `rateLimit` + OpenAI/Anthropic/NVIDIA | Round-robin would send more traffic to 0% free hops |
| GET payload always 200; Activity shows class + short `error_detail` | Point operators at Application logs only | Row is the RCA; logs are not joined |

## Product contract

### 1. Reserved ENV destination delete

Applies to reserved ids `discord`, `telegram`, `generic`.

- Confirm remains `confirm_text=delete`.
- Persist in **one DB transaction**: clear matching keys in `app_settings`, write the tombstone, delete the destination row. **After that commit succeeds**, pop those keys from `os.environ` even if they were process-env at boot. Do not pop env if the transaction rolls back.
- Response **200** `{ok: true, destination_id}`. If process-env *would have* re-injected the URL, include a non-secret `warning` naming the env key(s) (systemd still holds the secret until the unit is edited). **Do not 409.**
- `load_env_destinations` stays env-only (no rename). `load_destinations` (env+DB merge) and `sync_env_destinations_to_db` skip a tombstoned reserved id even if env still has a URL after restart.
- Other destination rows are untouched (same Discord URL string in `brief` still delivers).
- Discord.com is not called; the webhook token is not revoked there.
- Clear tombstone when the operator **saves a non-empty** matching URL/token via API keys & config. Then ENV bootstrap may return.
- Add destination remains a **new db** id (reserved ids stay reserved). Multiple Discords with different URLs and `event_types` already exist (cap 20/kind) — not this spec.

### 2. LLM error class + circuits

- `classify_llm_error` adds **`dns`** (name resolution / `Errno -3` / `gaierror`) and **`network`** (connection refused/reset, TLS handshake / SSL errors **with no HTTP status**). Keep existing `empty`, `timeout`, `auth`, `rate_limit`, `model_not_found`, `circuit_open`. Any exception whose text includes an HTTP **4xx/5xx** status is **not** `dns`/`network` (401/403 → `auth`, 429 → `rate_limit`, other 4xx/5xx stay `unknown` or existing classes). Default remains `unknown` only when none match.
- On failed attempts (including `dns`/`network`/`timeout`/`unknown`), call `record_source_failure` so Feed Health / API health pauses after the existing circuit threshold.
- For `dns` (and `network` that is not an HTTP 4xx/5xx), mark that **provider** skipped for the rest of the current `llm_job_session` (same pattern as empty body). Do **not** skip other providers in the chain for that reason.
- DNS/network failures must not be described as wasting provider quota. Tokens stay unset. Overview copy may say attempts failed before the provider billed.

### 3. Activity honesty + payload viewer

- Persist a short redacted **`error_detail`** on `ai_operations` (max 200 chars, no secrets). Activity Result shows class label **and** that line (e.g. `dns` + `Temporary failure in name resolution`).
- Labels: `dns` → `dns failure`; `network` → `network error`. Keep `unknown error` only for class `unknown`.
- `GET /api/admin/ai/operations/{id}/payload` returns **200** when a payload row exists: `{messages, messages_parse_ok, messages_raw?, response_excerpt, …}`. If `messages_json` is not a message list, `messages` is `[]`, `messages_parse_ok` is false, and `messages_raw` is the truncated stored text. **Never 500** for invalid JSON.
- Retry: if messages cannot be parsed as a list, **400** with a short detail (cannot replay). Not 500.
- Truncate failure payloads inside each message `content`, never by slicing the JSON blob. If insert input is not a message list, store bounded raw text as a valid JSON object `{"parse_ok": false, "raw": "…"}` (or skip the payload row) — do not persist a mid-cut array as if it were replayable messages.

### 4. Per-provider enable (without deleting keys)

- Each catalog provider (`custom`, `groq`, `cerebras`, `openrouter`, `gemini`) has an immediate-apply bool, default **on** when unset. Key may remain set.
- Disabled providers are omitted from `get_configured_providers` / failover. Providers tab: enable switch + status **disabled** vs configured.
- Does not add round-robin, token buckets, or new vendors.

## Non-goals

- GitHub #820 routing modes, per-provider RPM YAML, OpenAI/Anthropic/NVIDIA/Deepseek/Kimi first-class connectors.
- Cascade-delete dests by matching URL; revoke Discord webhook at discord.com; edit systemd from the app.
- Per-destination brief **templates** (different formats per Discord). Multiple dests + event checkboxes stay as today.
- Host DNS repair (operator ops). App only classifies, pauses, and skips.
- Light theme, Docker, SQLite removal.

## Success

- Delete ENV Discord: list has no `discord` card after confirm, including when `DISCORD_WEBHOOK_URL` is still in systemd; `brief` still listed if it was a separate db dest.
- Activity shows `dns failure` plus excerpt for `[Errno -3]…`; View payload opens that row without a toast 500.
- Disabling Cerebras/OpenRouter stops those hops while keys remain.
- `./scripts/verify-local.sh` green.
