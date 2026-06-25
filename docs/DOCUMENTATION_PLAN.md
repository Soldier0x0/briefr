# BRIEFR documentation plan

**Purpose:** This file explains *why* each doc area exists, *who* it is for, and *where* images go. Use it before you start writing or drawing.

**Image workflow (Miro / Figma / Penpot):**

1. Open [`IMAGE_BRIEFS.md`](IMAGE_BRIEFS.md) — copy the **Miro prompt** for the diagram you need.
2. Create on one reusable board → export PNG (2×) or SVG.
3. Save as `docs/assets/<filename>` (exact name from the brief).
4. Replace the placeholder in the doc page (image will render automatically).

---

## Design principles

| Principle | What it means |
|-----------|----------------|
| **Intent-first** | Readers choose by goal (deploy, use, fix, understand), not by how we wrote beta plans. |
| **Visual-first** | Hero diagram or screenshot near the top; long text in collapsible sections or tables. |
| **One page = one job** | No megadoc; no 29 root-level planning files in the README. |
| **Living vs archive** | `PRODUCT_STATUS.md` = truth today; `archive/` = history; `planned/` = not shipped. |
| **Granular why** | Decisions, errors, limits, and remediation in tables — not essay prose. |

---

## Folder map

```text
docs/
├── index.md                 ← START HERE (choose your path)
├── PRODUCT_STATUS.md        ← What's true in production today
├── IMAGE_BRIEFS.md          ← All diagrams: filename + Miro prompt
├── DOCUMENTATION_PLAN.md    ← This file
│
├── deploy/                  ← Self-hosters: install & run
├── use/                     ← Analysts & enthusiasts: product features
├── concepts/                ← How subsystems work (with decision tables)
├── troubleshoot/            ← Symptom → fix
├── reference/               ← Lookup (env, API, shortcuts)
├── develop/                 ← Contributors & AI assistants
├── decisions/               ← ADRs (one decision per file)
├── assets/                  ← Exported images from Miro/Figma/Penpot
│
├── archive/                 ← (Phase 2) Beta plans, HANDOVER, session notes
├── planned/                 ← (Phase 2) V1.5, correlation phases 3–5
│
├── ONBOARDING.md            ← Legacy path; develop/ links here
├── OPERATIONS.md            ← Legacy; deploy/ will absorb over time
├── POSTGRES.md              ← Legacy; deploy/postgres.md summarizes + links
└── diagrams/                ← Old Mermaid sources (internal/dev only)
```

---

## Who reads what

| I want to… | Start here | Then |
|------------|------------|------|
| **Deploy on my server** | [`deploy/quickstart.md`](deploy/quickstart.md) | [`deploy/production.md`](deploy/production.md) |
| **Use BRIEFR as an analyst** | [`use/brief-and-feed.md`](use/brief-and-feed.md) | Other `use/*` pages |
| **Understand how X works** | [`concepts/`](concepts/) | Linked ADRs in `decisions/` |
| **Fix an error** | [`troubleshoot/index.md`](troubleshoot/index.md) | Symptom page |
| **Look up env / API** | [`reference/`](reference/) | `backend/.env.example`, `API_REFERENCE.md` |
| **Change the code** | [`develop/onboarding.md`](develop/onboarding.md) | `CODEBASE_CONTEXT.md` |
| **What's shipped vs planned?** | [`PRODUCT_STATUS.md`](PRODUCT_STATUS.md) | [`ROADMAP.md`](ROADMAP.md) |

---

## What goes inside each doc type

### `deploy/*` — Tutorials & runbooks

- Prerequisites, commands, paths (`/opt/briefr`, `/var/lib/briefr`).
- **Diagram:** production topology (required).
- Tables: env vars, systemd units, backup schedule.
- Links to troubleshoot pages when things fail.

### `use/*` — Product guides

- What the user sees in each tab/feature.
- **Diagram or annotated screenshot** per major feature.
- Short “tips” — no implementation detail.

### `concepts/*` — Deep dives

Each concept page follows [`TEMPLATE_concept.md`](TEMPLATE_concept.md):

1. Hero image (placeholder until you add asset)
2. At-a-glance table
3. How it works (visual)
4. Decision log (why we chose X)
5. What was wrong before → what changed
6. Errors we hit & fixes
7. Limits & quotas
8. Code map (links to `backend/`, `frontend/`)
9. Collapsible deep dive (optional)

### `troubleshoot/*` — Symptom index

- [`troubleshoot/index.md`](troubleshoot/index.md) lists symptoms → page.
- Each page: symptom → cause → fix → related env vars.
- Small diagram only when it helps (e.g. backup restore).

### `reference/*` — Lookup

- Tables, not narrative. Minimal or no images.
- `api.md` points to root [`API_REFERENCE.md`](../API_REFERENCE.md).

### `decisions/*` — ADRs

- One architectural choice per file ([`TEMPLATE_adr.md`](TEMPLATE_adr.md)).
- Before/after diagram optional.

### `develop/*` — Contributors

- Links to `ONBOARDING.md`, `CODEBASE_CONTEXT.md`, tests.
- Not linked from main README for self-hosters.

---

## Image placeholder convention

Until you add a real file, pages show:

```markdown
![Diagram title](assets/placeholder-diagram.svg)
```

And a block like:

```markdown
> **Asset:** `docs/assets/production-architecture.png`  
> **Brief:** [IMAGE_BRIEFS.md §1](IMAGE_BRIEFS.md#1-production-architecture)
```

When `production-architecture.png` exists in `assets/`, change the `![...]()` line to that filename — remove the placeholder SVG reference.

---

## README & repo root (Phase 2, not this batch)

- README keeps pitch + quick start; **Documentation** section links only to [`docs/index.md`](index.md).
- Move `Beta V*.md`, `HANDOVER`, `SESSION_*` → `docs/archive/`.
- Optional later: MkDocs Material site publishing `docs/`.

---

## Status of this rollout

| Phase | Scope | Status |
|-------|--------|--------|
| **1** | Folder structure, index, PRODUCT_STATUS, IMAGE_BRIEFS, pages with placeholders | **This PR** |
| **2** | Archive beta docs, fix stale claims in README/API_REFERENCE | Pending |
| **3** | MkDocs site + CI | Pending |
| **4** | Fill body text from OPERATIONS, CORRELATION_V2_PLAN, etc. | Ongoing |
