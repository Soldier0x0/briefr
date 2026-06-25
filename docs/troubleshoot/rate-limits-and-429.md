# Rate limits and 429

## Symptoms

- HTTP `429` on IOC or refresh
- Admin **Security** page shows rate limiting disabled
- `Retry-After` header on responses

## Fixes

| Issue | Fix |
|-------|-----|
| RATE LIMIT OFF in prod | Set `RATE_LIMIT_ENABLED=1` in `backend/.env`, restart `briefr-backend` |
| Legitimate 429 on IOC | Wait; avoid scripted hammering; tune limits only if needed |
| Admin UI 429 | Separate read bucket exists (#225) — ensure latest backend |

## Defaults

See [rate-limits-and-queues.md](../concepts/rate-limits-and-queues.md).

## Env vars

`RATE_LIMIT_IOC_PER_MINUTE`, `RATE_LIMIT_REFRESH_PER_MINUTE`, `RATE_LIMIT_LOGIN_PER_MINUTE`, etc.
