# Auth and sessions

Two layers: optional edge access (operator) and built-in application login.

---

![Auth layers — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/auth-layers.png`](../assets/auth-layers.png)  
> **Miro prompt:** [IMAGE_BRIEFS §8](../IMAGE_BRIEFS.md#8-auth-layers)

## At a glance

| Layer | Where | Purpose |
|-------|--------|---------|
| **Edge** | Cloudflare Zero Trust (optional) | Protect public URL |
| **App** | FastAPI sessions | Portable self-host identity |
| **Admin key** | `BRIEFR_ADMIN_API_KEY` | Optional gate on refresh routes |

## Decision log

| Date | Decision | Why |
|------|----------|-----|
| 2026-06-11 | Built-in login, not CF JWT in app | Self-hosters without Cloudflare (#93) |
| — | Sessions in PostgreSQL | Survive restarts; multi-tab |

## First run

1. Backend starts with no users → `POST /api/auth/setup` allowed once.
2. Create admin username/password.
3. Login → session cookie.

## Errors & remediation

| Symptom | Fix |
|---------|-----|
| Can't login after setup | Check `ALLOWED_ORIGINS`, cookie domain |
| 401 on API | Session expired — re-login |
| LAN bypass of edge | Edge is not app auth — still need app login |

## Code map

`backend/routers/auth.py`, `frontend/src/pages/LoginPage.jsx`

## Related

[`THREAT_MODEL.md`](../THREAT_MODEL.md)
