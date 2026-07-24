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

## Secure deployment reminders

- Set a strong `JWT_SECRET` (32+ random bytes) before production use
- Keep `DATABASE_URL`, API keys, and backup encryption material out of version control
- Run Postgres with network isolation; expose only the reverse-proxy front door
- Review `docs/OPERATIONS.md` and `docs/POSTGRES.md` for backup and restore procedures
