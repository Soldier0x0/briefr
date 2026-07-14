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

**Not in main nav:** [`IMAGE_BRIEFS.md`](IMAGE_BRIEFS.md), [`DOCUMENTATION_PLAN.md`](this file), templates ([`decisions/TEMPLATE.md`](decisions/TEMPLATE.md), [`TEMPLATE_concept.md`](TEMPLATE_concept.md)).

---

## Layout

```
docs/                  # THE PRESENT — what is true today
├── index.md, SELF_HOST, USE, TROUBLESHOOTING, HOW_IT_WORKS   # readers
├── PRODUCT_STATUS.md, HANDOVER.md                            # living ops
├── ONBOARDING, OPERATIONS, POSTGRES, LEARNING_PATH           # deep guides
├── API_REFERENCE, SYSTEM_DESIGN, PRODUCT,                    # deep reference
│   DATA_SNAPSHOT, BRIEFR_PRODUCT_VOICE, IMAGE_BRIEFS
├── planning/          # THE FUTURE — direction + queue + specs
│   ├── SPRINT_*.md, BACKLOG.md
│   ├── STRATEGY.md, ROADMAP.md, PROGRAM_*.md
│   ├── ui-modernization-plan.md, reliability-and-bug-backlog.md   # 2026-07-14 program
│   └── specs/
├── archive/           # THE PAST — immutable history
│   ├── beta/
│   ├── sessions/
│   ├── snapshots/
│   └── superseded/
├── decisions/         # ADRs (incl. TEMPLATE.md)
├── design/            # UI single source of truth (design-system.md; tokens live in
│                      #   frontend/src/styles/tokens.css — spec until wired, plan E0-1)
├── diagrams/          # Mermaid sources
└── assets/            # SVGs + committed screenshots (README embeds)

repo root (code + entrypoints only):
├── README.md, LICENSE, CONTRIBUTING.md, SECURITY.md   # community standards
├── CLAUDE.md, AGENTS.md                               # agent entrypoints (tooling pins these to root)
└── backend/ frontend/ deploy/ scripts/                # code + ops
```

**Root rule:** no other Markdown at repo root. Reference material lives in
`docs/`; generated artifacts (`graphify-out/`, `*.xlsx`, `*.pdf`) are
gitignored and regenerated on demand.

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
| [`planning/ROADMAP.md`](planning/ROADMAP.md) | Release index |
| [`PRODUCT_STATUS.md`](PRODUCT_STATUS.md) | Living truth |

---

## Rule

**Do not split reader docs into more files** unless a section exceeds ~2 screens — add a subsection heading, not a new file.
