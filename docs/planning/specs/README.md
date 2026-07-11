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
