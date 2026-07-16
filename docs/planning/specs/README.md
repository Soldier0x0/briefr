# Planning specs (execution detail)

One file per **active program** — dependency-ordered PR plans, acceptance criteria, open questions.

**How to execute any of these:** [`execution-playbook.md`](execution-playbook.md) —
entry gates, dual-DB test runs, browser verification walk, stop-and-replan triggers.
A phase is complete only when merged with evidence in the PR body.

Open checklist rows: [`../BACKLOG.md`](../BACKLOG.md).

| Spec | Program | Committed scope |
|------|---------|-----------------|
| [`threat-modeling-security-architecture.md`](threat-modeling-security-architecture.md) | Security Architecture module (v2, evidence-gated) | TM-1 shipped (#491); TM-2 blocked on browser verification tooling; TM-3…TM-5; frameworks gated TM-6+ |
| [`forge-redesign.md`](forge-redesign.md) | Forge IA redesign + Hunt Pack Library | FR-1 shipped (#490); FR-2/FR-3 blocked on browser verification tooling |
| [`correlation-engine-v2.md`](correlation-engine-v2.md) | Correlation engine v3 (evidence-honest) | Phase 0–1 (PR-1…PR-5) shipped; PR-6…PR-13 open (PG-001, BACKLOG §3, fixed 2026-07-12 — no longer a blocker) |
| [`codebase-audit.md`](codebase-audit.md) | Security / reliability / performance remediation | Remaining PRs per BACKLOG §3 |
| [`ai-operations.md`](ai-operations.md) | AI ops (conditional AI-3 tail) | Gated on 28-day `ai_operations` evidence |
| [`ux-audit.md`](ux-audit.md) | UX audit deferred issues (28–33 etc.) | Per BACKLOG §5 |
| [`resource-benchmarking.md`](resource-benchmarking.md) | BRIEFR + Postgres utilization telemetry (admin RESOURCES page) | RB-1…RB-2 |
| [`api-key-health-and-quota-findings.md`](api-key-health-and-quota-findings.md) | Findings — RCA doc, most findings now shipped | AKH-1 shipped (#482); AKH-2 nav rename shipped (#486), dead-endpoint removal + HelpTip still open |
| [`qa-audit-2026-07-12.md`](qa-audit-2026-07-12.md) | Findings — RCA doc, most findings now shipped | QA-F1 shipped (#484); QA-U1…U3 still open |
| [`e2e-ux-observations-2026-07-15.md`](e2e-ux-observations-2026-07-15.md) | **Post–UI E2E UX audit** — ordered observations + PM-0…PM-4 plan | BACKLOG §12; PRs #601–#602 |
| [`post-ui-audit-2026-07-15.md`](post-ui-audit-2026-07-15.md) | Phase detail (sibling to master observations doc) | See master doc §6 |
| [`durable-outbound-queue-and-stack-backfill.md`](durable-outbound-queue-and-stack-backfill.md) | Procrastinate durable jobs + universal API metering + CPE catalog + Tier-A stack backfill | 📋 awaiting activation; PR-Q1…Q4 (+ optional EPSS identity skip) |
| [`embeddings-pgvector-hybrid-search-design.md`](embeddings-pgvector-hybrid-search-design.md) | pgvector + hybrid search + agent search token (humans & agents) | 💬 design review — then implementation plan |
| [`forge-attack-path-navigator-design.md`](forge-attack-path-navigator-design.md) | Forge ATT&CK path navigator (design) | 💬 design review — separate from queue/stack program |
| [`detection-composer-design.md`](detection-composer-design.md) | Evidence-composed detection packs (Detect + Forge) | DC-1 engine + additive `evidence` on Detect API; DC-2…DC-4 follow |
