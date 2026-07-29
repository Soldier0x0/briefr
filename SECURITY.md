# Security Policy

BRIEFR is maintained by Sai Harsha Vardhan.

## Supported versions

Security fixes are applied to the current `main` branch and the latest tagged release.
Self-hosted operators should track `main` or upgrade to the newest release promptly.

| Version | Supported |
| ------- | --------- |
| Latest release on `main` | Yes |
| Older tags / forks | Best effort only |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email **harsha@projectjupiter.in** with:

1. A description of the issue and the impact you believe it has
2. Steps to reproduce (proof-of-concept, request/response samples, or screenshots)
3. Affected component (backend API, frontend, deploy scripts, etc.)
4. Your contact details for follow-up

We aim to acknowledge reports within **3 business days** and provide a remediation
timeline within **10 business days** for confirmed issues.

### What to expect

- We will work with you to understand and reproduce the issue
- We will coordinate disclosure after a fix is available (or agree on a timeline if a
  fix needs more time)
- We will credit reporters in release notes when they want attribution

### Out of scope

- Issues in third-party services (NVD, VirusTotal, cloud providers, etc.)
- Missing security headers or rate limits on intentionally local/dev deployments
  without `BRIEFR_ENV=production`
- Social engineering or physical access scenarios

## Secret scanning

This repository runs [gitleaks](https://github.com/gitleaks/gitleaks) in CI on every
push and pull request. If you believe a real credential was committed, **rotate the
credential immediately** — this is a public repository, so git history cannot be
scrubbed after the fact; rotation is the only real fix.

## Code scanning (CodeQL, OSV)

GitHub **Security → Code scanning** runs CodeQL on Python, JavaScript, and GitHub
Actions workflows. Dependency supply-chain coverage includes **OSV-Scanner** and
Dependabot. Open alerts are triaged in-repo; many CodeQL findings on URL substring
checks and admin-only paths are intentional for a self-hosted operator tool.

When fixing alerts:

- **Workflow permissions** — CI jobs use least-privilege `permissions: contents: read`.
- **Admin file paths** — intel snapshot import and backup verify are rooted under
  `/var/lib/briefr/intel-publish` and `/var/lib/briefr/backups` (override with
  `INTEL_SNAPSHOT_IMPORT_DIRS`).
- **Client errors** — unhandled API failures return a generic message plus
  `request_id`; full tracebacks stay in server logs (admin log viewer / journald).

## Secrets and the browser

BRIEFR does **not** ship server API keys in the frontend bundle. Analyst routes never
return upstream provider keys. Admin config reads mask secrets and webhook URLs; search
tokens are shown once at creation only.

Operators should still:

- Use HTTPS in production (`BRIEFR_ENV=production`)
- Avoid putting credentials inside config URL fields (use separate secret keys)
- Treat the wallboard token like a password (prefer the httpOnly session cookie over
  `?token=` links when possible)

## Error handling and logging

- Every HTTP response includes **`X-Request-ID`**; unhandled **500** responses also
  include `request_id` in the JSON body for support correlation.
- Structured JSON logs (`LOG_FORMAT=json`) redact `*_KEY`, `*_TOKEN`, and URL/bearer
  patterns before entries reach the admin log ring buffer or support pack.
- **Do not** log API keys or raw webhook URLs in log message strings — use structured
  `extra` fields with redactable names, or omit secrets entirely.

See `docs/OPERATIONS.md` for journald, backups, and support-pack export.

## Secure deployment reminders

- Set a strong `JWT_SECRET` (32+ random bytes) before production use
- Keep `DATABASE_URL`, API keys, and backup encryption material out of version control
- Run Postgres with network isolation; expose only the reverse-proxy front door
- Review `docs/OPERATIONS.md` and `docs/POSTGRES.md` for backup and restore procedures
