# Maintainer docs migration (2026-07-24)

Internal maintainer content was removed from the public `briefr` repo to prepare
for open-source visibility. It now lives in a separate **`briefr-maintainer`**
private repository.

## What moved out of `briefr`

- `CLAUDE.md`, full agent rulebook (replaced by `docs/CONTRIBUTOR_RULES.md` in product repo)
- `docs/HANDOVER.md` — session log
- `docs/planning/` — sprint, backlog, specs
- `docs/archive/` — historical beta docs and snapshots
- `docs/audit/` — internal audit reports
- `docs/superpowers/` — agent design/plan artifacts
- `docs/STUDY_GUIDE.html`, `docs/study-guide/`, `docs/learn/` — personal architecture textbook
- `docs/LEARNING_PATH.md`, `docs/AGENT_METHODOLOGY.md`, `docs/DOCUMENTATION_PLAN.md`
- Study-guide scripts and tests

## `briefr-maintainer` repo

**Live:** https://github.com/Soldier0x0/briefr-maintainer (private)

Contains HANDOVER, planning, archive, audit, study guide, `CLAUDE.md`, and agent scripts
copied from `briefr` before the public cleanup (PR #751).

## Public repo now points to

- **Operators / users:** https://docs.projectjupiter.in
- **Contributors:** `docs/ONBOARDING.md`, `docs/CONTRIBUTOR_RULES.md`, `CONTRIBUTING.md`
