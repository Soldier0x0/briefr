# BRIEFR documentation plan

**For maintainers.** End users should only see [`index.md`](index.md) — **4 guides + optional depth**.

---

## Two-bucket rule (planning vs archive)

| Bucket | Location | What goes here |
|--------|----------|----------------|
| **To execute** | `docs/planning/` | `BACKLOG.md` + `specs/` for programs still open |
| **Done / replaced** | `docs/archive/` | Beta specs, session logs, `superseded/` plans |

**Never:** `archive/planned/` or `planning/completed/` — those mixed “todo” and “done” and caused confusion.

**Partial completion:** extract remaining rows into `planning/BACKLOG.md`; move the full spec to `archive/superseded/` when the program closes (or keep in `specs/` while PRs remain open).

---

## Reader-facing (5 files max)

| File | Audience | Length goal |
|------|----------|-------------|
| [`index.md`](index.md) | Everyone | 1 screen — pick a path |
| [`SELF_HOST.md`](SELF_HOST.md) | Self-hosters | 1 scroll — install, prod, backups |
| [`USE.md`](USE.md) | Analysts / enthusiasts | 1 scroll — tabs, drawer, IOC |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | Anyone stuck | 1 table — symptom → fix |
| [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) | Curious readers | Optional — diagrams + short sections |

**Not in main nav:** [`IMAGE_BRIEFS.md`](IMAGE_BRIEFS.md), [`DOCUMENTATION_PLAN.md`](this file), [`TEMPLATE_*.md`](TEMPLATE_concept.md).

---

## Layout

```
docs/
├── index.md, SELF_HOST, USE, TROUBLESHOOTING, HOW_IT_WORKS   # readers
├── PRODUCT_STATUS.md, HANDOVER.md, SPRINT_*.md               # living ops
├── ONBOARDING, OPERATIONS, POSTGRES, ROADMAP                 # deep refs
├── planning/          # FUTURE WORK
│   ├── BACKLOG.md
│   └── specs/
├── archive/           # HISTORY
│   ├── beta/
│   ├── sessions/
│   └── superseded/
├── decisions/         # ADRs
├── diagrams/
└── assets/

repo root (agent + product entrypoints only):
├── README.md, PRODUCT.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md
├── API_REFERENCE.md, SYSTEM_DESIGN.md, SECURITY.md              # canonical refs (linked everywhere)
└── CODEBASE_CONTEXT.md, TECHNICAL_INVENTORY.md, …             # periodic snapshots — prefer archive/snapshots/ long-term
```

---

## What to delete (not keep)

- One-off bot review dumps (e.g. Gemini inline JSON reconciliations) — fix in code/PR threads, not permanent docs
- Duplicate stubs that only redirect to another doc — fix links instead
- Generated artifacts in git (`*.xlsx`, `*.pdf` from scripts) — regenerate on demand

---

## Legacy (linked from guides, not index)

| Doc | Role |
|-----|------|
| [`ONBOARDING.md`](ONBOARDING.md) | Developers |
| [`OPERATIONS.md`](OPERATIONS.md) | Deep ops |
| [`POSTGRES.md`](POSTGRES.md) | Deep Postgres |
| [`ROADMAP.md`](ROADMAP.md) | Release index |
| [`PRODUCT_STATUS.md`](PRODUCT_STATUS.md) | Living truth |

---

## Rule

**Do not split reader docs into more files** unless a section exceeds ~2 screens — add a subsection heading, not a new file.
