# ADR-006: Encrypted `app_settings` secrets (env still primary)

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Operator writable config can persist in Postgres `app_settings` so values survive
`.env` refresh on deploy. Secret-typed keys (API tokens, webhook URLs, wallboard
token, etc.) were previously stored as plaintext in that table when saved via
Admin → config. Operators typically still keep secrets in `.env` / process env.

We need at-rest protection for DB-stored secrets without forcing a cutover away
from `.env`.

## Decision

1. **Precedence unchanged:** process env (keys present before `.env` load) →
   `app_settings` → `.env` / dotenv hydrate. Real host env always wins.
2. **Encrypt only secret-typed rows** in `app_settings` (schema
   `ConfigField.type == "secret"`). Non-secret settings stay plaintext.
3. **Cipher:** Fernet (AES-128-CBC + HMAC) via the `cryptography` package.
   Values stored as `enc:v1:<token>`. Master material from optional env
   `BRIEFR_SETTINGS_KEY` (any high-entropy string; derived to a Fernet key).
4. **No key ⇒ no secret rows:** if `BRIEFR_SETTINGS_KEY` is unset, Admin save
   still writes secrets to `.env` + `os.environ`, but **does not** persist
   secret keys into `app_settings` (matches existing seed skip for secrets).
5. **Legacy plaintext rows:** on hydrate, plaintext secret values still apply;
   when a key is present, the next Admin save re-writes them encrypted.
6. **`.env` remains supported forever** for this decision — encryption is
   additive for DB SSOT, not a migration mandate.

## Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Env-only (never store secrets in DB) | Blocks durable Admin save across `.env` refresh |
| Encrypt all `app_settings` rows | Unnecessary for intervals/bools; harder to debug |
| Reuse `JWT_SECRET` as settings key | Couples token signing to config crypto; rotation pain |
| age/X25519 (backup stack) | Wrong tool for many small string values; heavier ops |

## Consequences

- Positive: DB dumps / intel-adjacent access no longer expose Admin-saved API
  keys in cleartext when the settings key is configured.
- Positive: Existing `.env`-only installs keep working with zero change.
- Negative: Operators who want DB-durable secrets must set
  `BRIEFR_SETTINGS_KEY` (and back it up — loss = cannot decrypt those rows).
- Follow-up: optional Admin UI hint when saving a secret without the key.
