# Auth and security

## Symptoms

- Can't complete first-run setup
- Login succeeds but API 401
- CORS errors in browser console
- LAN access bypasses Cloudflare but app still asks login

## Fixes

| Issue | Fix |
|-------|-----|
| CORS | Set `ALLOWED_ORIGINS` to your browser origin (scheme+host+port) |
| Setup already done | Use login, not setup |
| Edge vs app confusion | CF Zero Trust ≠ app session — both may apply |
| Session cookie | HTTPS in prod; check SameSite / proxy headers |

## Two auth layers

[auth-and-sessions.md](../concepts/auth-and-sessions.md)

## Threat model

[THREAT_MODEL.md](../THREAT_MODEL.md)
