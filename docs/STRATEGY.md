# BRIEFR Strategy — from personal project to must-have analyst tool

**Last updated:** 2026-07-03
**Purpose:** Honest assessment of where BRIEFR stands today, and the strategy to
make it (a) genuinely save analysts 30–40 minutes per working day, and
(b) become a widely adopted, widely recognized tool in the security community.
Written to complement `ROADMAP.md` (release sequencing) — this document is about
*direction and positioning*, not phase-by-phase execution.

---

## 1. Where the tool actually is today

BRIEFR is **well past the "beginner project" stage**. Current state of the codebase:

- ~41,600 lines of backend Python across 210 files; ~126 frontend JS/JSX files
- ~90 backend test files covering auth, backups, correlation, admin, ingest
- PostgreSQL-required production path, Alembic migrations, asyncpg pooling
- Built-in auth + sessions, rate limiting, audit log, age-encrypted backups
  with startup auto-restore, structured JSON logging with request IDs
- 20+ upstream intel sources (NVD, KEV, EPSS, Vulnrichment, cvelistV5, OTX,
  ATT&CK, ATLAS, exploit indices, abuse.ch, CIRCL, OSV, RSS)
- Correlation Engine v2 (campaigns, infrastructure, actor/sector, temporal)
- 246 merged PRs and a documentation set most funded startups don't have

**Honest maturity label:** a strong late-beta, single-operator product.
The gap to "must-have community tool" is **not more features** — it is
(1) detection content quality, (2) trust/verifiability, and (3) adoption
mechanics (install friction, license, community). Those three gaps drive
everything below.

---

## 2. What BRIEFR is — and what it must accurately claim to be

The category from `ROADMAP.md` stands and is the right one:

> A self-hosted analyst intelligence pane — vulnerability and threat context
> ranked for **your stack**, connected to detection engineering and
> investigation, without enterprise TI pricing or log-scale infrastructure.

### Claims accuracy (important for credibility and for interviews)

The tool's reputation — and the maintainer's — depends on describing it
precisely. Current reality check:

| Claim sometimes made | Actual implementation today |
|---|---|
| "ML model generates detection rules" | Sigma generation is **template-based**: 14 static ATT&CK-technique templates (`detection/sigma_generator.py`) + a generic fallback. YARA rules are hash-led templates from OTX pulses. Community rules come from SigmaHQ/Elastic GitHub search. **No ML in the rule path.** |
| "ML in the product" | Two real, honest ML features: fastembed embeddings for semantic similar-CVEs (env-gated, CPU-only) and LLM product extraction for NVD-unanalyzed CVEs (Groq, provenance-marked). |
| "Reduces false positives" | Correlation has confidence scoring and suppressions, but there is no measured FP baseline yet. |

**Rule:** never describe template output as ML output. "Deterministic
templates with provenance, plus optional ML where it measurably helps" is a
*stronger* engineering story than "AI-generated rules" — it shows judgment.

### Known drift to fix

A claims-accuracy pass on the README is still needed to ensure alignment with
the current architecture. (Note: the SQLite/Postgres drift in
`ml/embeddings.py` has been resolved in this PR.)

---

## 3. The one metric: analyst minutes saved per day

"30–40 minutes saved per analyst per day" is the right north star, but today
it is an aspiration, not a measurement. Make it measurable:

**Where the minutes actually come from** (the defensible arithmetic):

| Manual workflow replaced | Typical daily cost | BRIEFR replacement |
|---|---|---|
| Morning sweep: NVD, KEV, EPSS movers, vendor advisories, news | 15–25 min | BRIEF tab action queue + "What changed" |
| Per-IOC lookup across VT / AbuseIPDB / OTX / GreyNoise tabs | 3–5 min each | IOC LOOKUP, one query, cached |
| "Is there a public exploit / rule for this CVE?" hunting | 5–15 min per CVE | Detail drawer: exploits, Detect tab, related CVEs |
| Building the daily report/hand-off | 10–20 min | PDF/CSV export + AI executive summary |

**Actions:**

1. **Instrument locally, privacy-preserving.** Add an opt-in, local-only
   usage counter (lookups performed, briefs opened, rules copied, exports
   generated) surfaced in the admin pane as "estimated minutes saved this
   week." No telemetry leaves the box — consistent with the privacy stance,
   and it gives every operator their own proof.
2. **Run the closed-beta stopwatch test.** Ask the 3 beta testers to do one
   week of morning triage without BRIEFR and one week with it, and record
   times. Publish the result honestly, whatever it is. A real "22 minutes
   median" number beats a claimed "40 minutes."
3. **Design reviews against the metric.** Every new feature answers: which
   row of the table above does this shrink?

---

## 4. Pillar 1 — Detection content quality (the Forge ladder)

This is the differentiation opportunity. The goal is **not** "train a better
ML model" — a custom-trained rule-generation model is the wrong tool at this
scale (no training data moat, unverifiable output, heavy maintenance). The
goal is **rules an analyst can trust without rewriting them**. Climb this
ladder in order:

**Level 1 (shipped):** ATT&CK-technique templates + community rule search
(SigmaHQ, Elastic), marked experimental with confidence notes.

**Level 2 — CVE-specific artifact injection (next, highest value):**
The ingest pipeline already collects PoC-in-GitHub links, ExploitDB entries,
Metasploit modules, Nuclei templates, and CIRCL/Vulnrichment references.
Extract *concrete observables* from those sources — URL paths, parameter
names, process/command patterns, ports, User-Agents — and inject them into
the generated Sigma rule for that CVE. A T1190 rule that matches
`/vendor/endpoint.php?cmd=` for this specific CVE is categorically more
useful than one that matches `../` generically. Nuclei templates are the
richest, most structured source: they are literally machine-readable
exploitation signatures already in the sync pipeline.

**Level 3 — deterministic validation (what creates trust):**
- Compile every generated/served rule through **pySigma** and refuse to
  display anything that doesn't compile to the major backends (Splunk SPL,
  Elastic, Microsoft KQL). This alone puts BRIEFR ahead of most "rule
  generator" hobby tools.
- Lint for known FP traps (bare keywords, unscoped wildcards, missing
  filters) and show the lint result next to the rule.

**Level 4 — the proof bench (V1.5, keep it):** replay rules against small
sample event sets (public EVTX corpora, Sigma test data) so the UI can say
"this rule fired on the attack sample and stayed quiet on the benign
sample." That statement — verifiable, per-rule — is the "must-have" moment
for detection engineers.

**LLM placement (optional, last):** LLM-assisted rule *drafting* is
acceptable only behind the existing rules — env-gated, provenance-marked,
and always passed through Level 3 validation before display. The LLM
proposes; pySigma disposes.

---

## 5. Pillar 2 — Correlation depth and false-positive discipline

- Finish Correlation v3 program (`planning/specs/correlation-engine-v2.md`, `planning/BACKLOG.md` §2).
- **Add the analyst feedback loop:** one-click "useful / not useful" on every
  correlation card and generated rule, stored locally. This is the cheapest
  FP-reduction mechanism that exists, it requires no ML, and the aggregate
  becomes tuning input (and, later, the only legitimate training data the
  project could ever own).
- Report correlation precision to the operator: "campaign links confirmed vs
  dismissed this month." Trust comes from the tool being honest about its
  own hit rate.

---

## 6. Pillar 3 — Adoption engineering

A tool becomes "must-have" through installs and word of mouth, not features.
Current blockers, in order:

1. **License.** **Decided 2026-07-10 (Track F2):** **AGPL-3.0-or-later**
   (`LICENSE`, `CONTRIBUTING.md`, SPDX headers). Repo flip to public GitHub
   remains gated on beta feedback; the license is in force in-tree now.
2. **Install friction.** `docker compose up` must work, first try, on a
   clean machine, in under 10 minutes, with sensible no-API-key defaults.
   V2.0's compose work was parked "while the deployment is private" — the
   open-source goal reverses that rationale. Unpark **only the compose
   part** of V2.0 (not multi-user).
3. **The demo instance** (briefr.projectjupiter.in) is the funnel — keep it
   seeded, fast, and linked from everything.
4. **Launch sequence** (after license + compose + a proof-bench-quality
   Detect tab): r/netsec and r/blueteamsec Saturday post, Hacker News
   Show HN, a detailed "how the correlation engine works" blog post, and a
   BSides CFP submission. Each of these also directly serves the career
   goal.
5. **Community surface:** CONTRIBUTING.md, "good first issue" labels,
   and accept community Sigma-template PRs — detection engineers who
   contribute one template become advocates.

---

## 7. Pillar 4 — The maintainer's knowledge (the career asset)

The project only advances the career goal if the maintainer can *defend
every architectural decision without the AI assistant in the room.* The
codebase already contains the syllabus:

- **Write ADRs retroactively** using `docs/TEMPLATE_adr.md` — one page each
  for: why PostgreSQL over SQLite; why APScheduler over Celery/cron; why the
  outbound API queue exists (#221); why rate limiting is token-bucket; why
  backups are age-encrypted with the key outside `BACKUP_DIR`; why EPSS is
  consumed and never re-derived; why ML is env-gated and off the request
  path; why edge auth (Cloudflare JWT) was dropped for app-owned auth (#93).
  Each ADR is an interview answer.
- **Interview narrative that is true and strong:** "I designed and operate a
  self-hosted threat-intel platform: 20+ upstream sources, incremental
  ingest with change tracking, a correlation engine, deterministic detection
  content with validation, encrypted backup/restore, and a documented threat
  model — and I can show you the audit log." No claim in that sentence
  outruns the code.
- The security-relevant depth to be able to explain, per subsystem: SSRF
  protection on the generic webhook, why read APIs are unauthenticated until
  a flag flips, session handling, and the application threat model in
  `archive/THREAT_MODEL.md`.

---

## 8. Sequencing (next ~90 days)

> Live execution checklist for the current month: [`SPRINT_2026-07.md`](SPRINT_2026-07.md).

| Order | Work | Why first |
|---|---|---|
| 1 | License decision + CONTRIBUTING.md | Blocks all adoption; zero code |
| 2 | Claims-accuracy pass on README (embeddings SQLite/Postgres drift fixed) | Trust and truthfulness |
| 3 | Forge Level 2: Nuclei/ExploitDB artifact injection into Sigma templates | Biggest differentiation per unit effort |
| 4 | Forge Level 3: pySigma compile validation + FP lint | Converts "generator" into "trustworthy generator" |
| 5 | Docker compose one-command install | Adoption gate |
| 6 | Local minutes-saved instrumentation + beta stopwatch test | Makes the 30–40 min claim real |
| 7 | Analyst feedback loop on correlations/rules | FP discipline, future data moat |
| 8 | Launch: demo + blog post + r/netsec + Show HN | Recognition |
| 9 | Proof bench (V1.5) | The long-term must-have feature |

Items 1–4 are achievable before touching anything else on the roadmap and do
not conflict with `ROADMAP.md` V1.2–V1.5 sequencing — items 3–4 *are* the
V1.5 "detection depth" theme, pulled forward because they are the
differentiator.

---

## 9. Explicit non-goals (reaffirmed)

Unchanged from `ROADMAP.md`, restated because ambition pressure will test
them: no SIEM replacement, no log ingestion in core, no multi-tenant SaaS in
V1.x, no generic LLM chat SOC, and — added here — **no custom-trained
rule-generation model**. Verifiable determinism plus optional, provenance-
marked ML is the brand.
