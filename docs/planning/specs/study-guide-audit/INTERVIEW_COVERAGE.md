# Interview coverage scores

_Scored 2026-07-19 against `docs/STUDY_GUIDE.html` structure (Concept / Why / How / Self-check). Manual review of heuristic pass; `strong`/`adequate`/`weak`/`missing`._

**Interview-ready** = all four dimensions `adequate` or better, and How cites paths that still exist.

Legend: C=Concept, W=Why, H=How, S=Self-check, IR=interview-ready?

## Current TOC

| Chapter id | Title | C | W | H | S | IR? | Notes |
|------------|-------|---|---|---|---|-----|-------|
| preface | Preface | adequate | adequate | adequate | weak | no | Add multi-file study UX notes later |
| system-design | System Design — 4 diagrams | strong | adequate | strong | strong | yes | |
| primer-mechanics | Concepts primer | adequate | strong | weak | missing | no | Card grid; optional self-check |
| arch-monolith | Monolith by design | strong | strong | strong | strong | yes | |
| arch-resources | Resource-consciousness | strong | strong | strong | strong | yes | |
| arch-connectivity | How pieces connect | strong | strong | adequate | strong | yes | |
| arch-ai-restraint | Why AI sparingly | strong | strong | strong | strong | yes | |
| arch-license | Why BSL-1.1 | strong | strong | strong | strong | yes | |
| fe-react | Why React 19 | strong | strong | strong | strong | yes | |
| fe-design | Tokens + Radix | strong | strong | strong | strong | yes | |
| fe-libs | Library registry | adequate | strong | strong | strong | yes | |
| fe-state | State & data flow | strong | strong | strong | strong | yes | Does not inventory pages/components |
| fe-tooling | Fonts, exports, testing | adequate | strong | strong | strong | yes | |
| be-bootstrap | Bootstrap & lifespan | strong | strong | strong | strong | yes | |
| be-config | Config & secrets | strong | strong | strong | strong | yes | Missing `operator_settings.py` chip |
| be-shim | database.py shim | adequate | strong | strong | adequate | yes | |
| be-data | Data layer | strong | strong | strong | strong | yes | Historical `dialect.py` OK |
| be-alembic | Alembic | adequate | strong | strong | strong | yes | Glob covers versions |
| be-auth | Authentication | strong | strong | strong | strong | yes | |
| be-ratelimit | Rate limiting | adequate | strong | strong | strong | yes | |
| be-logging | Logging & redaction | strong | strong | strong | strong | yes | |
| in-feeds | Feed sources | strong | strong | strong | strong | yes | |
| in-scheduler | Scheduler & locks | adequate | strong | strong | strong | yes | |
| in-queue | Outbound queue | strong | strong | strong | strong | yes | Extend for metering/ops modules |
| in-jobs | Procrastinate | adequate | strong | strong | strong | yes | |
| ie-scoring | Risk & Threat scoring | strong | strong | strong | strong | yes | |
| ie-matching | Asset/CPE matching | adequate | strong | strong | strong | yes | |
| ie-correlation | Correlation engine | strong | strong | strong | strong | yes | |
| ie-detection | Detection engineering | strong | strong | strong | strong | yes | |
| ie-brief | Morning brief | adequate | strong | strong | strong | yes | |
| ie-threatmodel | Threat modeling | adequate | strong | strong | strong | yes | |
| ie-ml | ML & LLM enrichment | strong | strong | strong | strong | yes | Add retrieval-ops follow-on |
| ie-ml-providers | Inside LLM chain | strong | strong | strong | strong | yes | |
| api-routers | Routers | adequate | strong | strong | strong | yes | |
| api-secarch | Security architecture | adequate | strong | strong | weak | no | Add self-check |
| api-webhooks | Webhooks & SSRF | strong | strong | strong | strong | yes | |
| api-usersettings | User-facing settings | adequate | strong | strong | strong | yes | Tie to operator_settings |
| api-proof | Proof, services, templates | adequate | strong | strong | strong | yes | retrieval_health weak-covered |
| api-ops | Ops & observability | adequate | strong | strong | strong | yes | Name storage/resource collectors |
| api-scripts | Scripts & guardrails | adequate | strong | strong | strong | yes | |
| devops-deploy | Deployment | adequate | strong | strong | strong | yes | Expand deploy script map |
| devops-ci | CI/CD & testing | adequate | strong | strong | strong | yes | Testing strategy home |
| sec-identity | Identity & session | adequate | weak | weak | missing | no | Digest; needs self-check |
| sec-network | Network trust | adequate | adequate | weak | missing | no | |
| sec-secrets | Secrets | adequate | weak | weak | missing | no | |
| sec-availability | Availability | adequate | weak | weak | missing | no | |
| sec-selfassess | Self-assessment | adequate | weak | weak | missing | no | |
| roadmap-nongoals | Non-goals | adequate | strong | weak | adequate | no | |
| roadmap-reversed | Tried and reversed | adequate | strong | weak | strong | no | |
| roadmap-future | What's next | adequate | strong | weak | strong | no | Point at this audit |
| glossary-content | Glossary | adequate | weak | weak | missing | n/a | Reference |
| self-check | Self-check index | adequate | weak | weak | missing | n/a | Index only |

| fe-analyst-shell | Analyst shell | strong | strong | strong | strong | yes | Added 2026-07-19 |
| fe-admin-shell | Admin shell | strong | strong | strong | strong | yes | Added 2026-07-19 |
| fe-forge-wallboard | Forge / wallboard | strong | strong | strong | strong | yes | Added 2026-07-19 |
| fe-shared-utils | Hooks & utils | strong | strong | strong | strong | yes | Pattern chapter |
| ie-retrieval-ops | Retrieval ops | strong | strong | strong | strong | yes | Added 2026-07-19 |
| api-secarch | Security architecture | adequate | strong | strong | adequate | yes | Self-check added |
| sec-identity | Identity & session | adequate | adequate | adequate | adequate | yes | Self-check added |
| sec-network | Network trust | adequate | adequate | adequate | adequate | yes | Self-check added |
| sec-secrets | Secrets | adequate | adequate | adequate | adequate | yes | Self-check added |
| sec-availability | Availability | adequate | adequate | adequate | adequate | yes | Self-check added |
| sec-selfassess | Self-assessment | adequate | adequate | adequate | adequate | yes | Self-check added |

## Coverage status (2026-07-19 evening)

Mechanical inventory: **0 gaps** for in-scope runtime/deploy files after Part I-B,
retrieval-ops, UI primitives, corpus, and deploy chip expansion. Remaining
`weak` rows are mostly `__init__.py` / sibling-dir associations — acceptable.
Only `orphan_mention` remains intentional historical `db/dialect.py`.
