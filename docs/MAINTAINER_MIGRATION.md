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

## Create `briefr-maintainer` (one-time)

**Prepared bundle:** `/opt/cursor/artifacts/briefr-maintainer-bundle` (214 files, ready to push).

```bash
cd /opt/cursor/artifacts/briefr-maintainer-bundle
git remote add origin https://github.com/Soldier0x0/briefr-maintainer.git 2>/dev/null || true
gh repo create briefr-maintainer --private --source=. --remote=origin --push
```

If the repo already exists, just push:

```bash
git push -u origin main
```

Recover from git history (alternative):

```bash
git checkout <commit-before-cleanup>
# copy moved paths into a fresh briefr-maintainer repo
```

## Public repo now points to

- **Operators / users:** [docs.projectjupiter.in](https://docs.projectjupiter.in)
- **Contributors:** `docs/ONBOARDING.md`, `docs/CONTRIBUTOR_RULES.md`, `CONTRIBUTING.md`
