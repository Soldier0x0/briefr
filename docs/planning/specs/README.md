# Planning specs (execution detail)

One file per **active program** — dependency-ordered PR plans, acceptance criteria, open questions.

**How to execute any of these:** [`execution-playbook.md`](execution-playbook.md) —
entry gates, dual-DB test runs, browser verification walk, stop-and-replan triggers.
A phase is complete only when merged with evidence in the PR body.

Open checklist rows: [`../BACKLOG.md`](../BACKLOG.md).

| Spec | Program | Committed scope |
|------|---------|-----------------|
| [`threat-modeling-security-architecture.md`](threat-modeling-security-architecture.md) | Security Architecture module (v2, evidence-gated) | TM-1…TM-5; frameworks gated TM-6+ |
| [`forge-redesign.md`](forge-redesign.md) | Forge IA redesign + Hunt Pack Library | FR-1…FR-3 |
| [`correlation-engine-v2.md`](correlation-engine-v2.md) | Correlation engine v3 (evidence-honest) | PR-1…PR-13 |
| [`codebase-audit.md`](codebase-audit.md) | Security / reliability / performance remediation | Remaining PRs per BACKLOG §3 |
| [`ai-operations.md`](ai-operations.md) | AI ops (conditional AI-3 tail) | Gated on 28-day `ai_operations` evidence |
| [`ux-audit.md`](ux-audit.md) | UX audit deferred issues (28–33 etc.) | Per BACKLOG §5 |
| [`resource-benchmarking.md`](resource-benchmarking.md) | BRIEFR + Postgres utilization telemetry (admin RESOURCES page) | RB-1…RB-2 |
| [`api-key-health-and-quota-findings.md`](api-key-health-and-quota-findings.md) | Findings only (P0 bug RCA + quota-system clarity) — no runtime changes yet | AKH-1…AKH-2 (not started) |
| [`qa-audit-2026-07-12.md`](qa-audit-2026-07-12.md) | Findings only (live-verified functionality/UI/ops QA pass) — no runtime changes yet | QA-F1, QA-U1…U3 (not started) |
