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
├── STUDY_GUIDE.html                                          # source for generated study-guide/ book
├── study-guide/                                              # generated multi-file book from STUDY_GUIDE.html
├── learn/                                                    # generated pathway chooser linking into study-guide/pages/
├── API_REFERENCE, SYSTEM_DESIGN, PRODUCT,                    # deep reference
│   DATA_SNAPSHOT, BRIEFR_PRODUCT_VOICE, IMAGE_BRIEFS
├── AGENT_METHODOLOGY.md                                      # agent working method (linked from AGENTS.md)
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
├── design/            # UI single source of truth (design-system.md; runtime tokens in
│                      #   frontend/src/styles/tokens.css — E0-1 shipped / wired)
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

## Generated study guide / learn site

`docs/STUDY_GUIDE.html` is the editable source of truth for the long-form textbook. After changing it, regenerate derived reader surfaces from the repo root:

1. `python scripts/build_study_guide_book.py` — writes `docs/study-guide/` from `STUDY_GUIDE.html`.
2. `python scripts/build_learn_site.py` — writes `docs/learn/` pathway pages from `docs/learn/pathways.json` and links into `docs/study-guide/pages/`.

Do not hand-edit generated `study-guide/` or `learn/` pages unless the generator itself is being fixed; edit the source/generator and rebuild.

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
