# BRIEFR documentation

Pick **one** guide — you do not need to read anything else unless something breaks or you want depth.

| I want to… | Read | Authority |
|------------|------|-----------|
| **Install BRIEFR** (SQLite, Postgres+pgvector, production) | [Self-host guide](SELF_HOST.md) | **Authoritative** — step-by-step install + verify checklist |
| **Postgres / pgvector / backups** (after choosing install path) | [PostgreSQL guide](POSTGRES.md) | **Authoritative** — database ops |
| **Use BRIEFR** | [User guide](USE.md) | **Authoritative** (analyst UX) |
| **Fix something** | [Troubleshooting](TROUBLESHOOTING.md) | **Authoritative** (symptom → fix) |
| **Understand how it works** | [How it works](HOW_IT_WORKS.md) *(optional)* | Overview (defers to SYSTEM_DESIGN / PRODUCT_STATUS) |
| **Change the code** | [Onboarding](ONBOARDING.md) | **Authoritative** (dev setup) |
| **Learn the whole architecture, file by file** | [Study Guide book](study-guide/) | Generated teaching corpus (not runtime SSOT) |

Deep reference: [API catalog](API_REFERENCE.md) · [System design](SYSTEM_DESIGN.md) · [Product principles](PRODUCT.md)

[What's shipped today](PRODUCT_STATUS.md) · [Planned work](planning/) · [Decisions (ADRs)](decisions/) · [Archive](archive/) *(historical — skip unless curious)*

Study-guide source: [`STUDY_GUIDE.html`](STUDY_GUIDE.html) is the editable standalone source; [`study-guide/`](study-guide/) is the generated book readers should use.

## Authority map (top-level `docs/`)

| Doc | Label |
|-----|--------|
| [PRODUCT_STATUS.md](PRODUCT_STATUS.md) | **Authoritative** — living production truth (wins over stale docs) |
| [API_REFERENCE.md](API_REFERENCE.md) | **Authoritative** — HTTP API contract |
| [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) | **Authoritative** — architecture / runtime design |
| [PRODUCT.md](PRODUCT.md) | **Authoritative** — product principles / anti-references |
| [OPERATIONS.md](OPERATIONS.md) | **Authoritative** — operator runbooks |
| [POSTGRES.md](POSTGRES.md) | **Authoritative** — Postgres ops |
| [SELF_HOST.md](SELF_HOST.md) | **Authoritative** — install / self-host |
| [USE.md](USE.md) | **Authoritative** — analyst user guide |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | **Authoritative** — symptom → fix |
| [ONBOARDING.md](ONBOARDING.md) | **Authoritative** — developer onboarding |
| [HANDOVER.md](HANDOVER.md) | **Authoritative** — session context (newest first) |
| [AGENT_METHODOLOGY.md](AGENT_METHODOLOGY.md) | **Authoritative** — agent working method |
| [DOCUMENTATION_PLAN.md](DOCUMENTATION_PLAN.md) | **Authoritative** — docs structure rules |
| [BRIEFR_PRODUCT_VOICE.md](BRIEFR_PRODUCT_VOICE.md) | **Authoritative** — product voice / copy |
| [design/design-system.md](design/design-system.md) | **Authoritative** — UI design system (§23 repo-wide) |
| [decisions/](decisions/) | **Authoritative** — ADRs |
| [planning/](planning/) | **Authoritative** — open work queue / specs (not runtime truth) |
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | Overview — optional; prefer SYSTEM_DESIGN for depth |
| [LEARNING_PATH.md](LEARNING_PATH.md) | Teaching path — points into study-guide / learn |
| [DATA_SNAPSHOT.md](DATA_SNAPSHOT.md) | **Snapshot** — may lag code; verify against source |
| [IMAGE_BRIEFS.md](IMAGE_BRIEFS.md) | Reference — image-brief feature notes |
| [TEMPLATE_concept.md](TEMPLATE_concept.md) | Template — not product truth |
| [study-guide/](study-guide/) | Teaching corpus — generated book; primary reader path |
| [STUDY_GUIDE.html](STUDY_GUIDE.html) | Editable standalone study-guide source |
| [learn/](learn/) | Teaching path chooser into the generated book |
| [archive/](archive/) | **Snapshot / historical** — never resurrect as living truth |
| [archive/snapshots/](archive/snapshots/) | **Snapshot** — periodic inventories; may lag |

### Config module ownership (F1.9)

| Module | Owns |
|--------|------|
| `backend/settings.py` | Process/env `Settings` (Pydantic); not admin writable keys |
| `backend/config_schema.py` | `WRITABLE_CONFIG_KEYS` schema (admin operator settings) |
| `backend/operator_settings.py` | DB seed/hydrate of writable keys (env wins); does not define keys |
| `backend/db/config.py` | `DATABASE_URL` resolution / backend detection only |
| `backend/routers/config.py` | `GET /api/config/risk` (scoring weight display); not admin keys |
