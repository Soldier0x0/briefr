# Threat Modeling & Security Architecture Module

**Status:** Plan of record — **no implementation in this document**  
**Date:** 2026-07-11  
**Audit basis:** Direct codebase trace on `main` (post-#454). Existing threat-model API,
Forge MITRE coverage, admin Security page, `architecture-map.html` generator, ADRs, and
`SECURITY_AND_OPS_AUDIT_2026-07` used as inputs.

**Central principle (non-negotiable):**

> This module is an **interactive operational workspace**, not a documentation viewer.
> Every surface must be backed by structured models that can later be populated automatically
> from repository analysis, security audits, ADRs, and live runtime data — never hardcoded
> prose in JSX.

**Explicitly NOT in scope (this program):**

- STIX 2.1 export (V1.5 Phase 4 — parked)
- Automated pen-test orchestration or external ASM scanners
- Replacing Forge detection engineering workflows (cross-link only)
- Light theme (BRIEFR ships dark-only)

---

## 1. Executive summary

BRIEFR already ships **fragments** of security architecture intelligence:

| Asset | Location | Today |
|-------|----------|-------|
| Threat scenarios API | `GET /api/threat-model/scenarios` | Stack-scoped ATT&CK cards with CVE evidence; consumed by Forge |
| MITRE coverage | Forge tab + `mitre_techniques` DB | Technique list, hunt packs, community templates |
| Admin Security | `/admin?p=security` | Rate limits, auth failures, wallboard guidance |
| Architecture map | `scripts/generate_architecture_map.py` → `architecture-map.html` | Static HTML graph (maintainer tool, not in-app) |
| Security audit | `docs/archive/superseded/SECURITY_AND_OPS_AUDIT_2026-07.md` | Findings catalog (not surfaced in UI) |
| ADRs | `docs/decisions/` | Two ADRs (intel schema, operational priority) |

**What's missing:** A unified, first-class module where operators and security-minded
analysts can **explore, review, and improve** BRIEFR's security architecture across
STRIDE, OWASP, MITRE ATT&CK, CAPEC, CWE, NIST CSF, ASVS, trust boundaries, controls,
abuse cases, threat scenarios, risk register, security decisions, and review history —
with live posture metrics and relationship graphs.

**Recommendation:** Deliver as a **standalone authenticated route**
(`/security-architecture`) with a three-panel executive dashboard layout patterned after
`AdminPage` (left nav, center workspace, right context rail). Seed content from a
versioned **Security Architecture Corpus** (YAML/JSON in-repo) merged at read time with
live DB/API data (MITRE tables, audit log, scheduler jobs, existing threat scenarios).
Implement in **eight dependency-ordered PRs** (TM-0 … TM-7).

---

## 2. Module placement & navigation

### 2.1 Route strategy

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Route | `/security-architecture/*` | 17 sections exceed header-tab capacity; matches Admin/Wallboard full-page pattern |
| Auth | `RequireAuth` — analyst + operator | Read-only for analysts; operator sees edit/review affordances (future) |
| URL state | `?section=overview` (default `overview`) | Deep-linkable sections; bookmarkable |
| Header entry | New header tab **ARCH** (short label) | First-class visibility; lazy-loaded like FORGE |
| Command palette | `Go to Security Architecture` | Matches Track E palette pattern |
| Admin cross-link | Security page → “Open security architecture workspace” | Bridges operator config and architecture review |

**Alternative rejected:** Admin-only sub-page — undersells “first-class module” goal and
hides from analysts who need posture context during triage.

### 2.2 Navigation catalog (left sidebar)

Sections grouped for scanability (flat list in spec; UI uses section headers like admin):

| Group | Section ID | Label |
|-------|------------|-------|
| **Posture** | `overview` | Overview |
| **Architecture** | `system-architecture` | System Architecture |
| | `trust-boundaries` | Trust Boundaries |
| | `attack-surface` | Attack Surface |
| **Frameworks** | `stride` | STRIDE |
| | `owasp` | OWASP |
| | `api-security` | API Security |
| | `mitre-attack` | MITRE ATT&CK |
| | `capec` | CAPEC |
| | `cwe` | CWE |
| | `nist-csf` | NIST CSF |
| | `asvs` | ASVS |
| **Threats** | `abuse-cases` | Abuse Cases |
| | `threat-scenarios` | Threat Scenarios |
| **Governance** | `security-controls` | Security Controls |
| | `security-decisions` | Security Decisions |
| | `risk-register` | Risk Register |
| | `review-history` | Review History |

Global search (⌘K scoped or in-module search bar) spans all corpus entities.

---

## 3. Layout architecture

### 3.1 Three-panel shell

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Header (existing) — tab ARCH active                                          │
├──────────────┬───────────────────────────────────────────┬───────────────────┤
│ Left nav     │ Center workspace                          │ Context rail      │
│ 240px        │ flex 1, min-width 0                       │ 320px, collapsible│
│              │                                           │                   │
│ Section list │ Section-specific interactive content      │ Selection context │
│ + search     │ (graphs, matrices, tables, timelines)     │ Related links     │
│              │                                           │ Evidence          │
│              │                                           │ Documentation     │
└──────────────┴───────────────────────────────────────────┴───────────────────┘
```

**Responsive breakpoints** (match admin patterns):

| Viewport | Behavior |
|----------|----------|
| ≥1280px | Three panels visible; context rail pinned |
| 960–1279px | Context rail overlays on selection (slide-in, 180ms) |
| ≤959px | Left nav → hamburger drawer; context rail bottom sheet |

### 3.2 Frontend file tree (target)

```
frontend/src/pages/security-architecture/
├── SecurityArchitecturePage.jsx      # Shell: nav, routing, context provider
├── SecurityArchitecturePage.css      # Scoped tokens (--sa-* mirrors --admin-*)
├── constants.js                      # NAV sections, VALID_SECTIONS
├── context/
│   └── SecurityArchitectureContext.jsx  # selection, search, corpus cache
├── components/
│   ├── SectionShell.jsx              # Title, subtitle, loading/error slots
│   ├── ContextRail.jsx               # Right panel
│   ├── SummaryCardRow.jsx            # Reuses StatCard pattern
│   ├── ArchitectureGraph.jsx         # Pan/zoom graph (SVG + transform)
│   ├── TrustBoundaryFlow.jsx         # Vertical boundary stacks
│   ├── StrideMatrix.jsx              # Component × STRIDE grid
│   ├── OwaspCategoryPanel.jsx        # Coverage + endpoints
│   ├── AttackNavigatorMatrix.jsx     # ATT&CK Navigator style
│   ├── CapecExplorer.jsx
│   ├── CweExplorer.jsx
│   ├── ControlsInventory.jsx
│   ├── ThreatScenarioTimeline.jsx
│   ├── AbuseCaseCatalog.jsx
│   ├── RiskRegisterTable.jsx         # AdminDataGrid wrapper
│   ├── DecisionRecordsList.jsx
│   ├── ReviewHistoryTimeline.jsx
│   └── GlobalSearch.jsx
└── sections/
    ├── OverviewSection.jsx
    ├── SystemArchitectureSection.jsx
    └── … (one file per section ID)
```

**Reuse mandate:** `StatCard`, `HelpTip`, `ExplainTip`, `Tooltip`, `AdminDataGrid`,
`AsyncState`, `ErrorState`, `EmptyState`, `Skeleton`, `ToolErrorBoundary`.

### 3.3 CSS scoping

Mirror `AdminPage.css` approach:

```css
.sa-root {
  /* inherit global :root tokens — do NOT introduce new palette */
  --sa-nav-width: 240px;
  --sa-context-width: 320px;
  --sa-section-gap: 1.25rem;
}
.sa-card { /* extends .admin-card geometry */ }
.sa-graph-node { /* hover: opacity + border-color, 150ms ease-out */ }
```

**Forbidden:** neon accents, new font families, hero marketing blocks, centered narrow
columns on data surfaces, gradients except existing subtle `--surface-raised` elevation.

---

## 4. Data architecture

### 4.1 Security Architecture Corpus (SAC)

Versioned structured data under `backend/security_architecture/corpus/`:

```
corpus/
├── manifest.yaml              # version, schema_version, last_reviewed
├── components.yaml            # system nodes (frontend, api, scheduler, …)
├── trust_boundaries.yaml
├── controls.yaml
├── abuse_cases.yaml
├── threat_scenarios.yaml      # operational attack paths (distinct from Forge API)
├── security_decisions.yaml    # ADR-style records
├── risks.yaml
├── reviews.yaml
├── frameworks/
│   ├── stride.yaml            # per-component STRIDE entries
│   ├── owasp_top10.yaml
│   ├── owasp_api.yaml
│   ├── nist_csf.yaml
│   ├── asvs.yaml
│   └── capec_mappings.yaml
└── graphs/
    ├── architecture.json      # nodes/edges for system graph
    └── attack_surface.json
```

**Schema rules:**

- Every entity has stable `id` (kebab-case), `title`, `summary`, `status`, `owner`,
  `review_date`, `evidence[]`, `related_ids[]`.
- Framework entries reference `component_id`, `control_ids[]`, `cwe_ids[]`,
  `technique_ids[]` where applicable.
- `source_refs[]` on each record: `{ type: "file"|"adr"|"endpoint"|"table"|"job", ref: "..." }`.
- Corpus validated in CI via `backend/tests/test_security_architecture_corpus.py`.

### 4.2 Live data merge (read-time, not duplicated)

| Surface | Live source |
|---------|-------------|
| MITRE ATT&CK matrix | `mitre_techniques`, `cve_technique_map`, Forge coverage API |
| Threat scenarios (stack) | Existing `build_threat_scenarios()` |
| CAPEC/CWE on CVEs | Drawer enrichment paths (CIRCL CAPEC) |
| API endpoints | OpenAPI introspection or static `api_inventory.yaml` (generated) |
| Background jobs | Scheduler job registry (`scheduler.py` id strings) |
| DB tables | `database.py` schema metadata |
| Review events | `audit_log` filtered by security-related actions |
| Posture metrics | Admin `/api/admin/security`, health, rate limits |
| Recent changes | Git-less: `cve_change_history`, ingest log ERROR count, job errors |

### 4.3 Backend package layout

```
backend/security_architecture/
├── __init__.py
├── corpus_loader.py       # load + validate YAML; in-memory cache with mtime
├── merge.py               # join corpus + live queries
├── posture.py             # overview aggregate metrics
├── graphs.py              # architecture graph builder
├── frameworks/            # per-framework aggregators
│   ├── stride.py
│   ├── owasp.py
│   ├── mitre.py
│   └── …
└── routers/
    └── security_architecture.py   # mounted at /api/security-architecture/*
```

Extend existing `backend/threat_model/` — do **not** duplicate scenario logic; wrap and
enrich for the Threat Scenarios section.

### 4.4 API surface (read-only v1)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/security-architecture/manifest` | Corpus version, section index |
| GET | `/api/security-architecture/overview` | Posture summary cards |
| GET | `/api/security-architecture/graph/architecture` | System architecture graph |
| GET | `/api/security-architecture/graph/attack-surface` | Attack surface score + nodes |
| GET | `/api/security-architecture/trust-boundaries` | Boundary list + detail |
| GET | `/api/security-architecture/stride` | STRIDE matrices by component |
| GET | `/api/security-architecture/owasp` | Top 10 + API Top 10 |
| GET | `/api/security-architecture/mitre` | Navigator matrix + coverage layers |
| GET | `/api/security-architecture/capec` | Pattern catalog |
| GET | `/api/security-architecture/cwe` | Secure coding explorer |
| GET | `/api/security-architecture/controls` | Controls inventory |
| GET | `/api/security-architecture/abuse-cases` | Abuse case catalog |
| GET | `/api/security-architecture/threat-scenarios` | Timeline scenarios (+ optional `stack`) |
| GET | `/api/security-architecture/risks` | Risk register rows |
| GET | `/api/security-architecture/decisions` | Security decision records |
| GET | `/api/security-architecture/reviews` | Review history timeline |
| GET | `/api/security-architecture/search?q=` | Global search |
| GET | `/api/security-architecture/context/{entity_type}/{id}` | Context rail payload |

All routes: session auth (analyst+). Rate limit: default API bucket. Responses: ORJSON.

**Future (out of v1):** PATCH review status, operator annotations — requires audit trail.

---

## 5. Section specifications

### 5.1 Overview (landing)

**Goal:** Immediate security posture communication.

**Top summary cards** (8 tiles, `SummaryCardRow`):

| Card | Metric source |
|------|---------------|
| Overall Security Posture | Weighted score from controls coverage + open critical risks |
| Critical Threats | Count of `severity=critical` open risks + high-likelihood abuse cases |
| Open Risks | Risk register `status=open` count |
| Security Controls | `implemented / total` from controls corpus |
| Framework Coverage | Mean compliance % across OWASP + ASVS + NIST |
| Trust Boundaries | Count + highest residual risk boundary |
| Attack Surface Score | Computed from exposed endpoints × missing controls |
| Review Freshness | Days since last architecture review event |

**Interactive Architecture Overview** (vertical stack, clickable nodes):

Frontend → API → Authentication → Business Services → Scheduler → Feeds → Correlation →
AI → Database → Backups → Webhooks → External Intelligence

- Hover: highlight inbound/outbound edges (SVG or CSS-connected list)
- Click: set selection → open context rail with component detail
- Uses simplified graph from `graphs/architecture.json` (subset of full System Architecture)

### 5.2 System Architecture

Large interactive graph (`ArchitectureGraph.jsx`):

| Capability | Implementation |
|------------|----------------|
| Zoom | `transform: scale()` + wheel handler; min 0.4 max 2.5 |
| Pan | pointer drag on canvas |
| Collapse/expand | cluster nodes (External, Scheduler, API, UI, DB) |
| Filter | tag chips: `all`, `security-critical`, `external`, `data` |
| Highlight | search match pulses border (`--amber`) |
| Search | filter node labels + paths |

**Node selection panel** (center, below or beside graph):

Purpose, Responsibilities, Owner, Dependencies, Inbound/Outbound calls, Database tables,
API endpoints, Background jobs, Security controls, Threats, Related ADRs, Related source
files — all from corpus `components.yaml` + live merge.

**Reuse:** Port node/edge model from `architecture-map.html` into React SVG; do not
iframe the static HTML.

### 5.3 Trust Boundaries

Visual vertical flows (`TrustBoundaryFlow.jsx`):

Examples seeded in corpus:

- Browser ↓ API ↓ Database
- BRIEFR ↓ Groq / ThreatFox / GitHub / Webhook receivers

Each boundary card:

| Field | Source |
|-------|--------|
| Data classification | corpus |
| Authentication | corpus + live auth config |
| Encryption | corpus (TLS, at-rest) |
| Threats | linked STRIDE/abuse case IDs |
| Controls | linked control IDs |
| Residual risk | corpus enum: low/med/high/critical |

### 5.4 STRIDE Workspace

Matrix: rows = components, columns = S/T/R/I/D/E.

Each cell expands to threat record:

Description, Likelihood, Impact, Current controls, Residual risk, Owner, Review date,
Evidence, Status (open/mitigated/accepted/wont-fix).

### 5.5 OWASP + API Security

Dedicated sub-views under `owasp` section with tabs:

- OWASP Top 10 (2021)
- OWASP API Security Top 10 (2023)

Per category row:

Coverage %, Related endpoints, Existing controls, Open findings, Recommended improvements,
Evidence links.

Compliance % = `(mitigated_categories / applicable_categories) * 100`.

### 5.6 MITRE ATT&CK

ATT&CK Navigator-style heat matrix (`AttackNavigatorMatrix.jsx`):

| Coverage layer | Color intensity source |
|----------------|------------------------|
| Detection | Forge hunt pack / Sigma presence |
| Correlation | `cve_technique_map` + OTX edges |
| YARA | detection context artifacts (future) |
| Threat feed | CVE mapping density |
| AI | AI operations tasks (informational) |

Filters: Platform, Tactic, Technique, Coverage % threshold.

Click technique → context rail with sub-techniques, linked CVEs, Forge deep link.

### 5.7 CAPEC

Attack pattern explorer — pattern ID, description, related components, mitigations,
likelihood, residual risk. Seed from CIRCL CAPEC IDs already surfaced in drawer + corpus
mappings.

### 5.8 CWE

Secure coding explorer — maps corpus + audit findings to CWE, affected code paths,
related APIs, DB objects, mitigation, review status.

Cross-link to codebase-audit remediation items (`docs/planning/specs/codebase-audit.md`).

### 5.9 Security Controls

Inventory table + detail drawer:

JWT, refresh tokens, rate limiting, input validation, parameterized SQL, webhook signing,
SSRF protection, TLS, password hashing, backup encryption, structured logging, audit logs,
role authorization — each with purpose, threats mitigated, coverage scope, related code/API
refs, review status.

**Live enrichment:** mark control `active: true/false` from runtime (e.g. `RATE_LIMIT_ENABLED`).

### 5.10 Threat Scenarios

**Highest-priority section.** Timeline visualization (`ThreatScenarioTimeline.jsx`):

```
Attacker → Compromised Feed → Feed Parser → Normalization → Correlation → Risk Score → Dashboard
```

Each step: Threat, Likelihood, Mitigation, Residual risk.

**Two scenario types:**

1. **Operational paths** — from `threat_scenarios.yaml` (architecture-focused)
2. **Stack-scoped ATT&CK** — from existing `/api/threat-model/scenarios` (Forge parity)

Toggle between catalogs; stack filter inherits user stack from `/api/me/stack`.

### 5.11 Abuse Cases

Searchable catalog (`AbuseCaseCatalog.jsx`):

Webhook SSRF, prompt injection, feed poisoning, duplicate replay, massive payload, stored
XSS, broken authorization, rate limit bypass — seeded from security audit + corpus.

Fields: Description, Attack flow (steps), Impact, Current protection, Remaining risk.

### 5.12 Risk Register

Enterprise table via `AdminDataGrid`:

Columns: Risk, Category, Severity, Likelihood, Business impact, Owner, Mitigation, Status,
Review date.

Sort/filter by severity and status. Export CSV (client-side, v1).

### 5.13 Security Decision Records

ADR-style list — Why JWT, PostgreSQL, HTTPS, signed webhooks, Argon2/bcrypt, no Redis.

Each record: Decision, Alternatives, Tradeoffs, Consequences, Review history.

Seed from `docs/decisions/` + new corpus entries for undocumented decisions.

### 5.14 Review History

Timeline (`ReviewHistoryTimeline.jsx`):

Architecture review, threat model review, audit, pen test, dependency review, OWASP review
— chronological cards with participants, outcome, linked artifacts.

Merge `audit_log` security actions + corpus `reviews.yaml`.

### 5.15 Context rail (right panel)

Always reflects current selection (node, technique, control, risk, etc.):

| Block | Content |
|-------|---------|
| Current risk | severity + residual |
| Threat level | derived score |
| Related components | linked graph nodes |
| Related APIs | endpoint list |
| Affected services | scheduler jobs, feeds |
| Recent changes | last 5 relevant events |
| Documentation | links to ADR, spec, source file |
| Evidence | audit refs, test names |
| Links | Forge, admin Security, external MITRE |

Collapsible on desktop; `Escape` closes overlay on tablet/mobile.

### 5.16 Global search

In-module search bar + ⌘K entries:

Index built server-side from corpus + MITRE names + control titles + API paths.
Results grouped by entity type; arrow-key navigable; Enter opens section + selection.

---

## 6. Visual design system mapping

| Requirement | BRIEFR implementation |
|-------------|----------------------|
| Spacing | `--sa-section-gap: 1.25rem`; card padding matches `.admin-card` |
| Elevation | `--surface-raised` cards; no drop shadows beyond existing admin |
| Border radius | `--radius-sm` chips, `--radius-md` cards |
| Typography | `--type-title` section headers, `--type-label` mono labels, `--type-body` prose |
| Cards | Extend `.admin-card`, `.stat-card-row` |
| Navigation | Mirror `pages/admin/Sidebar.jsx` section headers + active state |
| Icons | `lucide-react` (Shield, Network, GitBranch, AlertTriangle, …) |
| Colors | `--green`/`--amber`/`--red` semantic only; graph uses `--text2` edges |
| Hover | 150ms ease-out opacity/border (global `--motion-fast`) |
| Motion | Expand/collapse max-height transition 180ms; `prefers-reduced-motion: reduce` |
| Charts | Chart.js via existing `chartLoader.js` for coverage donuts/sparklines |
| Graphs | SVG + CSS transforms (no D3 dependency unless already present) |
| Accessibility | Focus rings (`--focus-ring`), `aria-current` on nav, live regions for search |
| Dark mode | Only theme; test all graph text against `--bg` contrast |

**Premium feel without new language:** generous whitespace between sections, mono labels
above human titles, subtle `--border2` dividers, glass overlay on context rail
(`background: color-mix(in srgb, var(--surface-raised) 92%, transparent)` — only if
contrast passes WCAG AA).

---

## 7. Extensibility

Adding a framework (e.g. ISO 27001) in the future:

1. Add `frameworks/iso27001.yaml` to corpus
2. Register in `manifest.yaml` `frameworks[]`
3. Add aggregator in `backend/security_architecture/frameworks/`
4. Add nav item + section component (no shell redesign)
5. Extend search indexer

Framework plugin interface:

```python
class FrameworkProvider(Protocol):
    framework_id: str
    def aggregate(self, corpus: Corpus, db: Any) -> dict: ...
```

---

## 8. Implementation phases

### TM-0 — Design merge (this document)

- [x] Spec authored
- [ ] BACKLOG + HANDOVER updated
- [ ] No runtime code

### TM-1 — Corpus + API skeleton

- Corpus YAML seed (components, controls, trust boundaries, abuse cases, decisions, risks)
- `corpus_loader.py` + validation tests
- Router stub returning manifest + overview placeholders
- Acceptance: `pytest tests/test_security_architecture_corpus.py`; corpus validates

### TM-2 — Shell UI + Overview

- Route `/security-architecture`, header tab ARCH, lazy page
- Three-panel shell, nav, context rail empty state
- Overview summary cards + simplified architecture stack
- Acceptance: `npm run build`; keyboard nav between sections; browser verify

### TM-3 — System Architecture + Trust Boundaries + Attack Surface

- Interactive graph component
- Trust boundary flows
- Attack surface scoring
- Acceptance: pan/zoom works; node selection populates context rail

### TM-4 — Framework workspaces (STRIDE, OWASP, API Security, NIST, ASVS)

- Matrix/table sections
- Compliance % calculations
- Acceptance: each framework renders from corpus; no hardcoded JSX strings

### TM-5 — MITRE ATT&CK + CAPEC + CWE

- Navigator matrix with coverage layers
- CAPEC/CWE explorers with live CVE cross-links where available
- Acceptance: technique click opens Forge link; coverage matches DB

### TM-6 — Threat Scenarios + Abuse Cases + Controls

- Timeline component
- Integrate existing `build_threat_scenarios()`
- Controls inventory with live `active` flags
- Acceptance: stack filter works; scenarios match Forge API output

### TM-7 — Risk Register + Decisions + Review History + Search

- Risk register grid
- Decision records from ADRs
- Review timeline merged with audit log
- Global search endpoint + UI
- Acceptance: search finds control by name; review history shows audit entries
- Docs: `PRODUCT_STATUS.md`, `API_REFERENCE.md`, `SYSTEM_DESIGN.md` updated

**Parallelization rule:** TM-2 must merge before TM-3+. TM-5 depends on TM-1 corpus
MITRE IDs. Do not parallelize TM-2 and TM-3 if both touch `SecurityArchitecturePage.jsx`.

---

## 9. Acceptance criteria (program complete)

1. Module reachable at `/security-architecture` and via header tab ARCH
2. All 17 sections render with designed loading/empty/error states
3. No prose hardcoded in JSX — all copy from API/corpus
4. Context rail updates on selection across graph, matrix, and table rows
5. Visual audit: side-by-side with Admin page — indistinguishable design language
6. Responsive at 375px, 960px, 1280px widths
7. Keyboard: Tab through nav, Enter to select, Escape closes overlays
8. `./scripts/verify-local.sh` green
9. Runtime docs updated per `CLAUDE.md`

---

## 10. Open questions

| ID | Question | Default if silent |
|----|----------|-------------------|
| Q1 | Header label: ARCH vs full name? | **ARCH** (mono, matches BRIEF/FEED/IOC) |
| Q2 | Analyst write access to review status? | Read-only v1; operator PATCH in TM-8+ |
| Q3 | Auto-regenerate corpus from `generate_architecture_map.py`? | Manual sync v1; script hook in TM-7 |
| Q4 | Embed vs link to static `architecture-map.html`? | **Embed** as React SVG (no iframe) |

---

## 11. Related documents

| Doc | Relationship |
|-----|--------------|
| [`docs/planning/specs/codebase-audit.md`](codebase-audit.md) | CWE + control findings source |
| [`docs/archive/superseded/SECURITY_AND_OPS_AUDIT_2026-07.md`](../../archive/superseded/SECURITY_AND_OPS_AUDIT_2026-07.md) | Abuse cases + risks seed |
| [`docs/decisions/`](../../decisions/) | Security decision records seed |
| [`backend/threat_model/scenarios.py`](../../../backend/threat_model/scenarios.py) | Existing threat scenarios API |
| [`scripts/generate_architecture_map.py`](../../../scripts/generate_architecture_map.py) | Graph node seed |

---

## Appendix A — Example corpus snippets

### `components.yaml` (excerpt)

```yaml
version: 1
components:
  - id: frontend
    title: React Frontend
    summary: Vite SPA; proxies /api to backend; session cookie auth.
    owner: platform
    responsibilities:
      - Render analyst workspace tabs and admin UI
      - Never store secrets in localStorage (except display prefs)
    dependencies: [api]
    inbound_calls: [browser]
    outbound_calls: [api]
    security_controls: [jwt-session, csrf-same-site, output-encoding]
    threats: [xss, broken-auth]
    source_refs:
      - { type: file, ref: frontend/src/App.jsx }
```

### `controls.yaml` (excerpt)

```yaml
controls:
  - id: jwt-session
    title: JWT session cookies
    purpose: Authenticate analyst and operator API requests
    threats_mitigated: [broken-auth, session-hijack]
    coverage: full
    related_code: [backend/auth/session.py]
    related_apis: ["/api/auth/*"]
    review_status: current
    live_flag: AUTH_ENABLED
```

### `threat_scenarios.yaml` (excerpt)

```yaml
scenarios:
  - id: feed-poisoning-to-dashboard
    title: Poisoned feed → inflated risk on dashboard
    steps:
      - { actor: Attacker, threat: Malicious CVE metadata injected at source }
      - { component: feed-parser, threat: Unvalidated upstream JSON }
      - { component: normalization, threat: Bad data enters scoring pipeline }
      - { component: correlation, threat: False positive cluster escalation }
      - { component: risk-score, threat: Elevated Operational Priority }
      - { component: dashboard, threat: Analyst acts on bad intel }
    mitigations: [input-validation, feed-circuit-breaker, manual-refresh-rate-limit]
```

---

## Appendix B — Wireframe reference (Overview)

```
┌─────────────────────────────────────────────────────────────────┐
│ OVERVIEW                                        [Search…    ⌘K] │
├─────────────────────────────────────────────────────────────────┤
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ …      │
│ │Posture │ │Critical│ │ Open   │ │Controls│ │Framework│       │
│ │  B+    │ │   3    │ │ Risks 8│ │ 42/48  │ │  78%   │       │
│ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘         │
├─────────────────────────────────────────────────────────────────┤
│ ARCHITECTURE OVERVIEW                                           │
│                                                                 │
│   [Frontend] ──► [API] ──► [Auth] ──► [Services] ──► …         │
│        │            │                         │                 │
│        └────────────┴────── Scheduler ◄───────┘                 │
│                                                                 │
│   hover: highlight path │ click: select node                    │
└─────────────────────────────────────────────────────────────────┘
```

---

*End of plan — implementation begins after TM-0 merges to `main`.*
