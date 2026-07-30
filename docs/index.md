# BRIEFR documentation

Pick **one** guide — you do not need to read everything unless something breaks or you want depth.

| I want to… | Read | Authority |
|------------|------|-----------|
| **Install BRIEFR** (SQLite, Postgres+pgvector, production) | [Self-host guide](SELF_HOST.md) | **Authoritative** |
| **Postgres / pgvector / backups** | [PostgreSQL guide](POSTGRES.md) | **Authoritative** |
| **Use BRIEFR** | [User guide](USE.md) | **Authoritative** |
| **Fix something** | [Troubleshooting](TROUBLESHOOTING.md) | **Authoritative** |
| **Understand how it works** | [How it works](HOW_IT_WORKS.md) | Overview |
| **Change the code** | [Onboarding](ONBOARDING.md) | **Authoritative** |
| **Try the UI (no install)** | https://briefrdemo.projectjupiter.in | Static demo — 1:1 analyst shell, fixture data ([`briefr-demo`](https://github.com/Soldier0x0/briefr-demo)) |
| **Self-host BRIEFR** | [Self-host guide](SELF_HOST.md) | PostgreSQL-backed deployment on your infrastructure |
| **Learn architecture online** | https://docs.projectjupiter.in | Synced from this repo |
| **Internal maintainer docs** | [Maintainer migration](MAINTAINER_MIGRATION.md) | Planning, HANDOVER, archive (private repo) |

Deep reference: [API catalog](API_REFERENCE.md) · [System design](SYSTEM_DESIGN.md) · [Product principles](PRODUCT.md) · [What's shipped](PRODUCT_STATUS.md) · [ADRs](decisions/)

## Authority map (top-level `docs/`)

| Doc | Label |
|-----|--------|
| [PRODUCT_STATUS.md](PRODUCT_STATUS.md) | **Authoritative** — living production truth |
| [API_REFERENCE.md](API_REFERENCE.md) | **Authoritative** — HTTP API contract |
| [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) | **Authoritative** — architecture / runtime design |
| [PRODUCT.md](PRODUCT.md) | **Authoritative** — product principles |
| [OPERATIONS.md](OPERATIONS.md) | **Authoritative** — operator runbooks |
| [POSTGRES.md](POSTGRES.md) | **Authoritative** — Postgres ops |
| [SELF_HOST.md](SELF_HOST.md) | **Authoritative** — install / self-host |
| [USE.md](USE.md) | **Authoritative** — analyst user guide |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | **Authoritative** — symptom → fix |
| [ONBOARDING.md](ONBOARDING.md) | **Authoritative** — developer onboarding |
| [CONTRIBUTOR_RULES.md](CONTRIBUTOR_RULES.md) | **Authoritative** — danger zones + conventions |
| [design/design-system.md](design/design-system.md) | **Authoritative** — UI design system (§23) |
| [decisions/](decisions/) | **Authoritative** — ADRs |
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | Overview — optional; prefer SYSTEM_DESIGN for depth |
| [DATA_SNAPSHOT.md](DATA_SNAPSHOT.md) | **Snapshot** — verify against source |
| [IMAGE_BRIEFS.md](IMAGE_BRIEFS.md) | Reference — screenshot/diagram briefs |
