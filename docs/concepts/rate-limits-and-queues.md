# Rate limits and API queue

Protecting your server and external API quotas.

---

![Rate limits and queue — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/rate-limits-and-queue.png`](../assets/rate-limits-and-queue.png)  
> **Miro prompt:** [IMAGE_BRIEFS §9](../IMAGE_BRIEFS.md#9-rate-limits-and-queue)

## Inbound (client → BRIEFR)

Token buckets in `backend/rate_limit.py`:

| Bucket | Typical default | Endpoints |
|--------|-----------------|-----------|
| IOC | 30/min | `POST /api/ioc/lookup` |
| Refresh | 10/min | `POST /api/refresh*` |
| Admin read | generous | `GET /api/admin/*` |
| Login / refresh | strict | `/api/auth/login`, refresh |
| Wallboard | 60/min | `GET /api/wallboard` |

Set `RATE_LIMIT_ENABLED=1` in production.

## Outbound (BRIEFR → NVD, OTX, …)

API queue (#221) serializes external calls to avoid quota stampedes and coordinated 503 handling.

## Decision log

| Decision | Why |
|----------|-----|
| Separate admin read bucket | Admin UI hammers GETs (#225) |
| X-Forwarded-For not trusted for bypass | Spoofable on LAN |
| Warn if `RATE_LIMIT_ENABLED=0` in prod | Startup log in `main.py` |

## Errors & remediation

| Symptom | Fix |
|---------|-----|
| Security page "RATE LIMIT OFF" | `RATE_LIMIT_ENABLED=1`, restart backend |
| 429 on IOC | Wait `Retry-After`; raise limits only if intentional |
| NVD still 503 | Queue + breaker — not always rate limit |

## Env vars

See [environment-variables.md](../reference/environment-variables.md).
