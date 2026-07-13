# Planning (the future)

**Rule:** everything about work that is *not shipped yet* — direction, queues, sprints, specs — lives here. If it is done or replaced, it moves to [`../archive/`](../archive/) — never stays under `planning/`.

| File / folder | Purpose |
|---------------|---------|
| [`SPRINT_2026-07.md`](SPRINT_2026-07.md) | Current work queue with acceptance criteria (merge checkboxes) |
| [`BACKLOG.md`](BACKLOG.md) | Single queue — open, parked, optional (checklist rows) |
| [`specs/`](specs/) | Full PR specs for active programs (correlation v3, audit remediation, etc.) |
| [`PROGRAM_PRODUCT_OPEN_CORE.md`](PROGRAM_PRODUCT_OPEN_CORE.md) | Active program: product polish & open-core readiness |
| [`STRATEGY.md`](STRATEGY.md) | Direction and positioning |
| [`ROADMAP.md`](ROADMAP.md) | Release index (historical framing) + the deploy **compatibility promise** |

**Session log (living, parent `docs/`):** [`HANDOVER.md`](../HANDOVER.md).

**Runtime truth:** [`../PRODUCT_STATUS.md`](../PRODUCT_STATUS.md) — when a doc here disagrees with it or the code, they win.

When a spec is fully shipped: move the doc to [`../archive/superseded/`](../archive/superseded/), leave only any remaining rows in `BACKLOG.md`.
