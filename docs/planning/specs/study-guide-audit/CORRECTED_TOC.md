# Corrected study-guide TOC (for multi-file shell)

_Proposed outline after 2026-07-19 audit. Stub titles only — prose rewrites are a later sub-project._

## Design rules for the shell

- **Hybrid paging:** Part hub HTML + one HTML file per chapter (short chapters may share a Part page).
- **Entry:** `docs/study-guide/index.html` (or keep `docs/STUDY_GUIDE.html` as redirect/landing).
- **Shared:** `assets/book.css`, `assets/book.js` (search, progress, theme, responsive nav).
- **Preserve:** BRIEFR token palette; self-checks; file chips; diagrams.

## Proposed map

### Front matter
| Id | Title | Notes |
|----|-------|-------|
| `preface` | Preface — how to use this book | Keep; add progress/search UX notes for multi-file |
| `system-design` | System Design — four diagrams | Keep; refresh if topology drifts |

### Part 0 — Foundations
| Id | Title | Notes |
|----|-------|-------|
| `primer-mechanics` | Concepts primer | Keep; optional mini self-check |
| `arch-monolith` | Monolith by design | Keep |
| `arch-resources` | Resource-consciousness thread | Keep |
| `arch-connectivity` | How the pieces connect | Keep |
| `arch-ai-restraint` | Why AI is used sparingly | Keep |
| `arch-license` | Why BSL-1.1 | Keep (AGPL reversal already covered) |

### Part I — Frontend decisions (keep)
| Id | Title | Notes |
|----|-------|-------|
| `fe-react` … `fe-tooling` | Ch 1–5 | Keep substance |

### Part I-B — Frontend surface map (**shipped 2026-07-19**)
| Id | Title | Owns gaps |
|----|-------|-----------|
| `fe-analyst-shell` | Analyst shell: tabs, feed, drawer, URL nav | App.jsx, feed, drawer, filters |
| `fe-admin-shell` | Admin shell: sidebar, grids, ops pages | pages/admin/* core |
| `fe-forge-wallboard` | Forge, ATLAS, wallboard, brief UI | Forge + WallboardPage |
| `fe-shared-utils` | Shared hooks, utils, scoring helpers | hooks/, utils/, scoring/ patterns |

### Part IV — Intelligence (keep + retrieval ops) **shipped 24C**
| Id | Title | Delta |
|----|-------|-------|
| `ie-scoring` … `ie-ml-providers` | Ch 18–24B | Keep |
| `ie-retrieval-ops` | Ch 24C · Retrieval ops & auto-on-ingest | **Shipped** |

### Part V — API & ops (keep + extend)
| Id | Title | Delta |
|----|-------|-------|
| `api-routers` … `api-scripts` | Ch 25–31 | Chip corpus + frameworks; name storage/resource collectors; fix `api-secarch` self-check |
| `devops-deploy` | Deployment & infrastructure | Add doctor/backup/update/restore/compose/nginx snippet map |
| `devops-ci` | CI/CD & testing | Keep; remains Testing strategy home |

### Part VI — Security digest
| Id | Title | Delta |
|----|-------|-------|
| `sec-*` | Five digests | Add self-checks; keep as digests not full rewrites |

### Part VII — Roadmap & reference
| Id | Title | Delta |
|----|-------|-------|
| `roadmap-*`, `glossary-content`, `self-check` | Keep | Future chapter should cite this audit folder |

## Explicit out-of-scope (still listed once)

- `backend/tests/**` — strategy in `devops-ci` only  
- `node_modules`, `.venv`, build artifacts  
- Individual Alembic revision narration (glob coverage in `be-alembic` is enough)

## Migration order (shell sub-project)

1. Scaffold `docs/study-guide/` + shared CSS/JS (responsive sidebar/drawer).  
2. Move preface + system-design + Part 0.  
3. Move Parts I–VII under corrected ids (stubs OK for new I-B / retrieval-ops).  
4. Wire search/progress across files.  
5. Leave deep prose fills to Part-by-Part rewrite PRs.
