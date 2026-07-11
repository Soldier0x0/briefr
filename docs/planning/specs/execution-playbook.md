# Execution Playbook — shipping these specs at full quality

**Scope:** [`forge-redesign.md`](forge-redesign.md) and
[`threat-modeling-security-architecture.md`](threat-modeling-security-architecture.md).
The specs say **what** to build. This document says **how** to execute them — written so
that any competent agent or human, starting with zero conversation context, ships the
same quality. If you are an AI model executing a phase: follow this literally; it
encodes judgment you would otherwise have to rediscover the hard way.

---

## 0. Non-negotiables (read before anything)

- `CLAUDE.md` danger zones bind every phase. The ones that will bite in this program:
  Postgres-native SQL with **dual test runs** (zone 1), scheduler job-id/lock sync
  (zone 2), secrets never in log message strings (zone 4), heavy work never on the
  request path (zone 6).
- A phase is **done only when merged to main with evidence in the PR body**. "Code
  complete" is not a state this playbook recognizes.
- **Code is ground truth; specs are intent.** Every `file:line` reference in a spec must
  be re-verified before you rely on it. If reality has moved, update the spec in the
  same PR — silent divergence between doc and code is the failure mode this whole
  program exists to kill.

## 1. Session start ritual (every session, ~2 minutes)

1. `git fetch origin` — local main goes stale; never trust it unfetched.
2. `git log --oneline -10 origin/main` and the newest `docs/HANDOVER.md` entry — what
   changed since the spec (or your last session)?
3. `git branch -r --sort=-committerdate | head` — is an in-flight branch touching your
   files? If yes, read its diff before starting; coordinate via HANDOVER, don't collide.
4. Confirm your phase's entry gate (§2 step 1) before writing anything.

## 2. The phase loop

Every phase (TM-1…TM-5, FR-1…FR-3) runs the same nine steps. No skipping, no reordering.

1. **Entry gate.** Previous phase is merged. Re-run *its* acceptance commands; they must
   be green before you begin. If they're red, fixing that *is* your phase now.
2. **Recon.** Read end-to-end every file the phase names — whole files, not grep
   excerpts. List what the spec got wrong or stale; fixing the spec is part of your PR.
3. **Plan.** Smallest diff that meets acceptance. Write your assumptions down.
   Decision rule: *spec silent + user-visible consequence* → **stop and ask**, then
   record the answer in the spec's Open Questions. *Spec silent + internal detail* →
   take the boring default and note it in one line in the PR body.
4. **Test first.** Backend logic gets a failing test before implementation. Anything
   touching `db/`: run `cd backend && pytest tests/ -q` **twice** — default (SQLite)
   and with `DATABASE_URL` pointing at Postgres. A query that passes one and fails the
   other is a production incident you almost shipped.
5. **Build.** Match neighboring style. No new dependencies — jsPDF, Chart.js,
   lucide-react are already installed and are the entire budget. No abstraction with one
   caller. Every changed line traces to the phase.
6. **Verify with evidence.** Run the exact commands; for UI phases run the browser walk
   (§3). Command output and screenshots go in the PR body. "It should work" is a
   sentence about your beliefs, not about the software.
7. **Self-review.** Read the full diff as a hostile reviewer. Remove orphans your own
   change created. Docs rule from CLAUDE.md: behavior changed → `PRODUCT_STATUS.md` +
   `SYSTEM_DESIGN.md`; endpoints changed → `API_REFERENCE.md` — **same PR**, never
   "later."
8. **Ship.** Commit and push atomically (this environment has previously reset and
   destroyed uncommitted work). PR body: what/why, assumptions taken, evidence, spec
   deltas made.
9. **Record.** HANDOVER entry: what merged, what was decided, what the next phase needs
   to know. Write it for a stranger.

## 3. UI verification walk (any phase with frontend changes)

In a real browser against dev servers — `npm run build` passing is necessary, nowhere
near sufficient.

- **The three states.** For every async view, force all three: loading (network
  throttle), empty (fresh DB), error (backend stopped). Each must be *designed*, and
  none may dead-end — every state offers a next action or an explanation with the
  `ref:` request id.
- **The smoothness budget** — this is what "feels smooth" means, measurably:
  - click/hover feedback within 100ms; view transitions 120–180ms, opacity/transform only
  - zero layout shift when selecting a node or row — the context rail must never reflow
    the workspace
  - graph pan/zoom rides `transform` exclusively; never re-layout during drag
  - selection is never lost by navigation inside the module — the URL carries it
- **Keyboard-only pass.** Tab order sane, Enter selects, Escape closes overlays, focus
  always visible.
- **Widths 375 / 960 / 1280**, plus `prefers-reduced-motion: reduce` (motion collapses,
  nothing breaks).
- **Every status word explains itself.** A new pill, badge, or count without a
  discoverable tooltip/legend is an incomplete feature (PRODUCT.md principle 1).

## 4. Stop-and-replan triggers

Halt, write findings into HANDOVER plus a spec amendment, and ask — do **not** push
through — when any of these occur:

- acceptance cannot be met without violating a CLAUDE.md danger zone or a spec constraint
- a table, endpoint, or function the spec references doesn't exist or behaves differently
- the diff is heading past roughly **2×** what the phase plausibly needs (scope rot)
- a test failure reveals a *design* error rather than a code error

Silently narrowing scope and silently gold-plating are the same sin: the document no
longer matches reality.

## 5. Post-merge iteration loop (the difference between shipped and good)

After every phase merges:

1. **Dogfood.** Ten minutes using the feature as an analyst, not as its author. Real
   flows: pick a technique, generate a pack, delete it, refresh mid-flow, deep-link a
   section, break the network and watch what the UI says.
2. **Friction log.** Every hesitation, confusing label, and dead click goes on a list.
3. **Triage.** Broken promise of *this* phase → fix now. New idea → spec backlog /
   Open Questions for the next planning pass. Never mid-phase feature creep.
4. **Regression gate.** Re-run *all* prior phases' acceptance commands after each merge.

## 6. Program-level definition of done

Everything in each spec's acceptance section, plus:

- every acceptance criterion has pasted evidence in a merged PR
- all friction logs triaged to zero (fixed or explicitly backlogged)
- HANDOVER tells the whole story — a stranger could pick up the program from it alone
