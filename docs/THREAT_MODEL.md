# BRIEFR — Application Threat Model

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Last updated:** 2026-06-10  
**Status:** Planning — security design reference for V1.2+

This document models threats to the **BRIEFR application** (not environment threat scenarios for the analyst — those ship in Beta V1.5 product UI).

---

## System context

```text
[Analyst browser] ──HTTPS──► [Cloudflare] ──► [cloudflared] ──► [nginx :80]
                                                                    │
                                                                    ▼
                                                          [briefr-backend :8000]
                                                                    │
                    ┌───────────────────────────────────────────────┼───────────────┐
                    ▼               ▼               ▼               ▼               ▼
              briefr.db      /var/lib/briefr/    .env secrets    External APIs    (future admin)
              (SQLite)         backups/                           NVD, VT, etc.
```

**Trust boundaries:**

1. Internet → Cloudflare edge  
2. Edge → origin (cloudflared tunnel / LAN)  
3. nginx → uvicorn  
4. BRIEFR → external intel APIs (outbound HTTPS)  
5. BRIEFR → webhook destinations (outbound HTTPS, V1.4)

---

## Assets

| Asset | Sensitivity |
|-------|-------------|
| `briefr.db` | High — CVE cache, IOC cache, investigation data |
| `.env` / API keys | Critical |
| Backup archives | High — DB + env snapshot |
| Admin credentials / API keys | Critical |
| Webhook URLs/tokens | High |
| Application logs | Medium — may contain paths, IPs |
| Public CVE intel in UI | Low — already public sources |

---

## STRIDE summary

| Threat | Example | Mitigations (planned / existing) |
|--------|---------|--------------------------------|
| **Spoofing** | Fake admin session | `BRIEFR_ADMIN_API_KEY`; V1.2 auth; Cloudflare Access optional |
| **Tampering** | Restore malicious DB | Integrity check before write; admin-only restore; audit log |
| **Repudiation** | Deny config change | Audit log (V1.4); structured logging |
| **Information disclosure** | Leak VT key in logs | Log redaction; mask secrets in admin UI; `.env` 640 |
| **Denial of service** | Flood IOC lookup | Rate limits (V1.2); feed snapshots; webhook dedupe |
| **Elevation** | Analyst triggers restore | Separate `/admin` routes; role check (V2.0) |

---

## Attack surfaces

| Surface | Risk | Controls |
|---------|------|----------|
| Public `/api/*` read | Low–medium | Rate limit; CORS; optional auth tightening |
| `/api/ioc/lookup` | Medium — API quota burn | Rate limit; keys server-side only |
| `/api/refresh` POST | Medium | Admin auth required (V1.2) |
| Admin backup/restore | **Critical** | Strong auth; confirm phrase; audit |
| Webhook generic URL | **SSRF** | Block private IP ranges; allowlist schemes |
| Swagger `/api/docs` | Info leak | Disable in production |
| SQLite file perms | Local privilege escalation | `briefr` user; 750 backend dir |
| Supply chain | Dependency compromise | Lock files; CI tests |

---

## Deployment-specific notes

### systemd + nginx (current)

- Bind uvicorn to `127.0.0.1:8000` when UFW allows only :80  
- SSH restricted to LAN where possible  
- cloudflared — no inbound firewall rules for BRIEFR  

### Docker (V2.0)

- Secrets via env_file / Docker secrets — not in image layers  
- Read-only container filesystem; volumes for state  
- No `--privileged`  
- Publish localhost only unless nginx in compose  

---

## Data flow — outbound

BRIEFR calls external APIs (NVD, GitHub, VT, etc.). Threats:

- **Key exfil via SSRF** — webhook module must not fetch arbitrary URLs with internal keys in headers  
- **Supply chain in RSS** — parse XML safely; size limits; timeouts (`resilient_client`)  

---

## Backup & restore threats

| Threat | Mitigation |
|--------|------------|
| Unencrypted off-site backup stolen | Optional GPG/age encryption |
| Restore of tampered archive | Integrity check in `backup/manager.py` |
| Ransomware on host | Off-site second copy; immutable object storage optional |

---

## Future features — security requirements

| Feature | Requirement |
|---------|-------------|
| Admin pane | Auth on all routes; CSRF for cookie sessions |
| Wallboard token | Read-only scope; rotatable; rate limited |
| Multi-user V2.0 | Password hashing (argon2/bcrypt); lockout optional |
| Postgres V2.0 | TLS to DB; least-privilege DB user |

---

## Related documents

- [`OPERATIONS.md`](OPERATIONS.md) — backup, logs, container  
- [`Beta V1.2.md`](../Beta%20V1.2.md) — auth and resilience  
- [`Beta V1.4.md`](../Beta%20V1.4.md) — admin and webhooks  

Review this document when adding admin, webhooks, or container support.
