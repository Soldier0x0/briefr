# BRIEFR documentation plan

**For maintainers.** End users should only see [`index.md`](index.md) — **4 guides + optional depth**.

---

## Reader-facing (5 files max)

| File | Audience | Length goal |
|------|----------|-------------|
| [`index.md`](index.md) | Everyone | 1 screen — pick a path |
| [`SELF_HOST.md`](SELF_HOST.md) | Self-hosters | 1 scroll — install, prod, backups |
| [`USE.md`](USE.md) | Analysts / enthusiasts | 1 scroll — tabs, drawer, IOC |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | Anyone stuck | 1 table — symptom → fix |
| [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) | Curious readers | Optional — diagrams + short sections |

**Not in main nav:** [`IMAGE_BRIEFS.md`](IMAGE_BRIEFS.md) (diagram prompts), [`DOCUMENTATION_PLAN.md`](this file), [`TEMPLATE_*.md`](TEMPLATE_concept.md).

---

## Archive (hidden from index)

```
docs/archive/
├── beta/          Beta V1.2–V2.0 specs
├── sessions/      HANDOVER, SESSION_*
├── planned/       CORRELATION_V2, UI overhaul
└── LIGHT_THEME.md
```

Root `Beta V*.md` stubs redirect to `docs/archive/beta/`.

---

## Images

1. Prompts in [`IMAGE_BRIEFS.md`](IMAGE_BRIEFS.md)
2. Export from Miro/Figma → [`assets/`](assets/)
3. Reference in the 4 guides (replace `placeholder-diagram.svg`)

---

## Legacy (linked from guides, not index)

| Doc | Role |
|-----|------|
| [`ONBOARDING.md`](ONBOARDING.md) | Developers |
| [`OPERATIONS.md`](OPERATIONS.md) | Deep ops (linked from SELF_HOST) |
| [`POSTGRES.md`](POSTGRES.md) | Deep Postgres |
| [`ROADMAP.md`](ROADMAP.md) | Release index |
| [`PRODUCT_STATUS.md`](PRODUCT_STATUS.md) | Living truth (short) |

Everything else under [`archive/`](archive/) is historical.

---

## Rule

**Do not split reader docs into more files** unless a section exceeds ~2 screens — then add a subsection heading, not a new file.
