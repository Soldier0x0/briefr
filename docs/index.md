# BRIEFR documentation

Choose your path — each section is a separate doc. **Diagrams:** create in Miro (or similar), export to [`assets/`](assets/), using prompts in [`IMAGE_BRIEFS.md`](IMAGE_BRIEFS.md).

---

## I want to…

| Goal | Start here |
|------|------------|
| **Deploy on my server** | [Quickstart](deploy/quickstart.md) → [Production](deploy/production.md) |
| **Use the product** | [BRIEF & FEED](use/brief-and-feed.md) |
| **Fix a problem** | [Troubleshooting index](troubleshoot/index.md) |
| **Understand how it works** | [Concepts](concepts/architecture.md) |
| **Configure / integrate** | [Reference](reference/environment-variables.md) |
| **Develop or contribute** | [Developer onboarding](develop/onboarding.md) |
| **What's true today?** | [Product status](PRODUCT_STATUS.md) |

---

## Sections

### Deploy — install & operate

| Doc | Contents |
|-----|----------|
| [quickstart.md](deploy/quickstart.md) | Dev install, first run, seed data |
| [production.md](deploy/production.md) | systemd, nginx, cloudflared, topology |
| [postgres.md](deploy/postgres.md) | PostgreSQL required, Docker, migrations |
| [updates-and-backups.md](deploy/updates-and-backups.md) | `briefr-update.sh`, backup/restore |

### Use — analyst & enthusiast guides

| Doc | Contents |
|-----|----------|
| [brief-and-feed.md](use/brief-and-feed.md) | BRIEF tab, FEED, filters, heatmap |
| [ioc-lookup.md](use/ioc-lookup.md) | IOC enrichment, quotas |
| [investigation-and-correlation.md](use/investigation-and-correlation.md) | Drawer, correlation, pivots |
| [detection-and-forge.md](use/detection-and-forge.md) | Detect tab, Forge, hunt packs |
| [admin-and-wallboard.md](use/admin-and-wallboard.md) | Admin console, wallboard, webhooks |

### Concepts — how & why

| Doc | Contents |
|-----|----------|
| [architecture.md](concepts/architecture.md) | System overview, data model groups |
| [ingest-pipeline.md](concepts/ingest-pipeline.md) | Schedulers, NVD/KEV/EPSS, feeds |
| [correlation.md](concepts/correlation.md) | Engine v2, lanes, OTX, decisions |
| [auth-and-sessions.md](concepts/auth-and-sessions.md) | Edge vs app auth, sessions |
| [rate-limits-and-queues.md](concepts/rate-limits-and-queues.md) | Token buckets, API queue, 429s |

### Troubleshoot — symptom → fix

| Doc | Contents |
|-----|----------|
| [index.md](troubleshoot/index.md) | Symptom lookup table |
| [empty-feed-and-ingest.md](troubleshoot/empty-feed-and-ingest.md) | Empty feed, slow ingest, NVD 503 |
| [rate-limits-and-429.md](troubleshoot/rate-limits-and-429.md) | 429, RATE LIMIT OFF |
| [postgres-and-backups.md](troubleshoot/postgres-and-backups.md) | DB connection, restore |
| [api-keys-and-quotas.md](troubleshoot/api-keys-and-quotas.md) | Missing keys, quota exhaustion |
| [auth-and-security.md](troubleshoot/auth-and-security.md) | Login, setup, CORS |

### Reference — lookup tables

| Doc | Contents |
|-----|----------|
| [environment-variables.md](reference/environment-variables.md) | Key env vars |
| [api.md](reference/api.md) | API catalog (links to API_REFERENCE) |
| [keyboard-shortcuts.md](reference/keyboard-shortcuts.md) | Shortcuts |

### Develop — contributors only

| Doc | Contents |
|-----|----------|
| [onboarding.md](develop/onboarding.md) | Local dev, tests, reading order |
| [contributing.md](develop/contributing.md) | PR expectations, doc updates |

---

## Meta

| Doc | Purpose |
|-----|---------|
| [DOCUMENTATION_PLAN.md](DOCUMENTATION_PLAN.md) | Why this structure exists |
| [IMAGE_BRIEFS.md](IMAGE_BRIEFS.md) | **All diagram filenames + Miro prompts** |
| [PRODUCT_STATUS.md](PRODUCT_STATUS.md) | Living “what’s shipped” truth |
| [TEMPLATE_concept.md](TEMPLATE_concept.md) | Template for new concept pages |
| [TEMPLATE_adr.md](TEMPLATE_adr.md) | Template for architecture decisions |

**Legacy docs** (still valid, migrating gradually): [ONBOARDING.md](ONBOARDING.md), [OPERATIONS.md](OPERATIONS.md), [POSTGRES.md](POSTGRES.md), [ROADMAP.md](ROADMAP.md).
