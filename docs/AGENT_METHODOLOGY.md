# Agent methodology — how to think when working on BRIEFR

**Audience:** any AI agent (or human) working in this repo. `CLAUDE.md` and
`AGENTS.md` tell you *what the rules are*; this document tells you *how to
think* so your work is correct on the first pass. It is a distillation of the
working method of a frontier-class engineering model, written down so every
session — whatever model runs it — operates at the same level.

**Read order for a fresh session:** `CLAUDE.md` → `docs/PRODUCT_STATUS.md` →
`docs/HANDOVER.md` (newest entry) → `docs/planning/SPRINT_2026-07.md` → this
file when you want the method behind the rules.

---

## 0. The core loop

Every task, from a one-line fix to a new subsystem, runs the same loop:

**Orient → Plan → Design → Implement → Verify → Self-review → Record.**

The single most common agent failure is skipping straight from "read the
request" to "write code". Each phase below exists because skipping it has
burned a real session in this repo. The phases are cheap — often seconds of
thought — and the loop is not bureaucracy; it is how you avoid the expensive
failure modes: fixing the wrong problem, breaking Postgres while SQLite tests
stay green, and shipping a patch that regresses next week.

---

## 1. Orient — build a true model before touching anything

Your first job on any task is to make your internal model of the system match
reality. Everything downstream inherits errors made here.

- **Code beats docs; newest beats oldest.** Trust hierarchy in this repo:
  source code > `docs/PRODUCT_STATUS.md` > newest `docs/HANDOVER.md` entry > other
  living docs > `docs/archive/` (never trust for current behavior). When two
  sources disagree, the one higher in this list wins — and note the
  discrepancy rather than silently picking one.
- **Read the actual code path, not just the file that looks relevant.** Before
  changing a function, find its callers (`Grep` for the symbol) and its
  callees. Most "simple" changes fail because of an unexamined caller.
- **Establish what "currently works" means.** Run the relevant tests *before*
  changing anything when the area is unfamiliar. A pre-existing red test
  discovered after your change wastes an hour of false debugging.
- **Name your assumptions out loud.** Write them in your plan or PR
  description: "Assumes `backend/scheduler.py` job ids match the admin lock map",
  "Assumes this endpoint is only called from FEED". A stated wrong assumption
  gets corrected in review; an unstated one becomes a production bug.
- **Distinguish the request from the requirement.** Users describe symptoms
  and sometimes prescribe fixes. The symptom is data; the prescribed fix is a
  hypothesis. If the user says "add a retry here", first ask *why it fails* —
  the right fix may be upstream. (See §4, RCA-first.)

---

## 2. Plan — decide what "done" means before writing code

- **Define verification first.** Before the first edit, write down the exact
  commands and observations that will prove the change works: which test
  files, `npm run build` in `frontend/`, which browser flow, which DB modes. If you cannot
  name the verification, you do not yet understand the task.
- **Decompose by risk, not by file.** List the sub-tasks, then reorder so the
  riskiest/most-uncertain one goes first. If the hard part is impossible,
  you want to learn that in minute five, not after building the easy 80%.
- **3+ items → checklist file, always.** Context gets compacted mid-session;
  verbal lists do not survive it. Write the checklist to a file (or the
  sprint doc) and tick items as you finish. This is a hard rule in
  `CLAUDE.md` because it has stalled real sessions.
- **Identify the blast radius up front.** For every plan, explicitly check it
  against the `CLAUDE.md` danger zones: does it touch `db/` (→ test both
  SQLite and Postgres)? `backend/scheduler.py` job ids (→ sync `backend/routers/admin.py`
  locks)? migrations (→ forward-only)? `deploy/` (→ additive only)? request
  handlers (→ no heavy work)? Logging (→ no secrets in message strings)?
- **Prefer the plan that can be abandoned.** When two approaches look equal,
  pick the one that is easier to revert or split into independent PRs.
  Optionality is worth more than elegance mid-task.
- **Ask only true forks.** Ask the maintainer when interpretations genuinely
  diverge *and* the wrong guess is expensive. Do not ask about things the
  repo already answers (read first) or that are cheaply reversible (pick the
  conventional option and state it). Never end a turn with "shall I proceed?"
  when the next step is already defined — `AGENTS.md` execution contract.

---

## 3. Design — smallest correct shape, in the repo's own idiom

- **Minimum diff that solves the whole problem.** No speculative
  configurability, no abstractions for a second caller that doesn't exist,
  no "while I'm here" refactors. Every changed line must trace back to the
  request. But "minimum" never means "symptom-only" — fixing the class of
  bug (§4) *is* the minimum correct diff.
- **Copy the house style before inventing one.** Before writing a new
  endpoint, service, component, or migration, open the nearest existing
  example and mirror its structure, naming, error handling, and test shape.
  A technically better pattern that fights the codebase is worse than a
  consistent one — inconsistency is a tax every future reader pays.
- **Design the failure modes, not just the happy path.** For backend work:
  what does the caller see on timeout, on bad input, on empty result? Use
  `HTTPException` with a short safe `detail` for expected 4xx; let the rest
  hit the global 500 handler. For frontend work: every async view needs
  designed loading / empty / error / data states before it is designed at all.
- **Write SQL Postgres-native.** The `db/` package is Post-B: production is
  Postgres-only, SQLite exists only as the zero-config test fallback. New
  queries are written for Postgres, with parallel `_SQLITE` / `_PG` constants
  only where the default test suite needs them. Never reintroduce a dialect
  translation layer.
- **Heavy work goes to the scheduler.** If a design puts ML, enrichment,
  external API sweeps, or anything unbounded on a request path, the design is
  wrong — move it to a `backend/scheduler.py` job and have the handler read cached
  results.
- **Architectural decisions get an ADR.** If you're choosing between
  approaches with long-lived consequences (new dependency, storage shape,
  job architecture), write it up in `docs/decisions/` using the template —
  a decision that lives only in a PR description is lost within a month.
- **UI: density, tokens, explanation.** Content fills the width (~24–32px
  gutters; `max-width` is for prose only). Use existing tokens in `App.css`
  and the standards in `docs/design/design-system.md` §23. Every status
  word/pill/badge ships with a discoverable explanation. No gradients, no
  hero sections, no icon-card grids.

---

## 4. Debug — root cause or it didn't happen

This repo's debugging doctrine is RCA-first (`.cursor/rules/rca-first-debugging.mdc`,
`AGENTS.md`). The method behind it:

1. **Reproduce before you theorize.** Confirm the failure on current HEAD
   with a log line, a failing test, or a minimal repro. If you cannot
   reproduce it, your first task is to explain *why not* (environment,
   data-dependent, already fixed) — not to patch blind.
2. **Form hypotheses, then rank them by cheapness of disproof.** Good
   debugging is not reading code until enlightenment; it is generating 2–4
   candidate causes and running the cheapest experiment that kills the most
   candidates. One targeted log line or one `pytest -k` beats an hour of
   staring.
3. **Bisect the path, don't scan the codebase.** Trace the failing request or
   job end-to-end and find the *first* point where reality diverges from
   expectation. Everything before that point is exonerated; everything after
   is downstream noise.
4. **Beware the pattern-match trap.** A symptom that looks like a known
   failure ("database is locked", NVD 503, port collision) may have a
   different cause this time. Confirm the specific evidence supports the
   specific fix before acting — especially before restarting things,
   deleting things, or widening timeouts.
5. **Fix the class, not the instance.** If one query does a full-table scan
   under load, look for its siblings. If one job id drifted from the admin
   lock map, check them all. The bug in front of you is usually the loudest
   member of a family.
6. **A wider timeout / retry / sleep is a fix only when the timing itself was
   wrong.** Otherwise it is a snooze button on the alarm.
7. **Guard against recurrence.** Add or extend a regression test, or a CI
   gate, whenever the bug plausibly returns. If neither is possible, say why
   in the PR.
8. **State the RCA in one sentence.** If you cannot write "it failed because
   X caused Y at Z", you have not finished debugging — you have finished
   experimenting. Record it in `docs/HANDOVER.md` when runtime behavior or
   operator expectations changed.

---

## 5. Implement — small verified steps, honest state

- **Work in compile-green increments.** Prefer several small edit→test cycles
  over one big edit→pray. After each meaningful unit, run the narrowest
  relevant check (a single test file, a type check, the build).
- **Test-first when behavior is specifiable.** For pure logic (URL state
  helpers, parsers, scoring), write the failing test first — it doubles as
  the spec and survives context compaction better than intent does.
- **Never let the two-database gap bite you.** Tests default to SQLite; a
  `db/`-layer change can pass the whole default suite and still break
  production Postgres. For any `db/` change, run the suite both ways —
  default *and* with `DATABASE_URL` at the Postgres test container. This is
  the single most repo-specific trap; treat "SQLite green" as half a result.
- **Environment discipline.** Absolute paths always (cwd resets between
  shell calls). No foreground `sleep`/polling — background the wait and act
  on completion. Dev servers only through the sanctioned launcher, never raw
  Bash (port collisions with other sessions). Never print `.env`, hashes, or
  tokens; never interpolate secrets into log message strings.
- **Migrations are forward-only.** Never edit an applied Alembic migration;
  add a new one. If a migration is wrong, the fix is another migration.
- **When you're interrupted or compacted, files are your memory.** Keep the
  checklist file current, commit at coherent points with descriptive
  messages, and write down mid-task discoveries (a surprising constraint, a
  half-diagnosed bug) somewhere durable before moving on.

---

## 6. Verify — prove it, don't vibe it

- **Run the verification you defined in §2 — all of it.** Backend: `pytest
  tests/ -q` from `backend/`. Frontend: `npm run build` from `frontend/` must pass
  before any frontend change is done. `db/` changes: both database modes. UI changes:
  verified *in the browser*, not just the build — a passing build proves the
  code parses, not that the feature works.
- **Exercise the change end-to-end, not just its unit.** Drive the affected
  flow the way a user or the scheduler would. Most escaped bugs live at the
  seam between the changed unit and its neighbors.
- **Verify the negative space.** Did you break the thing next to the thing?
  Re-run the tests of adjacent modules you touched even indirectly (shared
  fixtures, changed schema, altered response shape).
- **Report reality.** If tests fail, say so with the output. If a step was
  skipped, say it was skipped and why. "Done" means verified-done; anything
  else is "implemented, verification pending" and must be labeled as such.
  A false "done" costs the maintainer more than a true "stuck".

---

## 7. Self-review and correct — be your own harshest reviewer

Before pushing, re-read the full diff as if you were reviewing a stranger's
PR, specifically hunting:

- **Scope creep** — lines that don't trace to the request. Delete them.
- **The assumption check** — for each assumption named in §1, is it still
  true after seeing the real code? Which ones did the diff silently bet on?
- **Edge inputs** — empty list, first run (cold DB), huge input, concurrent
  scheduler run, missing API key. This repo runs unattended on a self-hosted
  box; "the operator will notice" is not a fallback.
- **The docs contract** — runtime behavior changed → `docs/PRODUCT_STATUS.md` +
  `docs/SYSTEM_DESIGN.md` in the same PR. Endpoints changed → `docs/API_REFERENCE.md`
  in the same PR. Decisions/context → `docs/HANDOVER.md` (newest entry first).
- **Sunk cost is not an argument.** If mid-review you realize the approach is
  wrong, discard it. Two hours of wrong code plus one hour of the right fix
  beats shipping the wrong code with apologies. Say plainly: "first approach
  was wrong because X; redid it as Y."
- **Correct forward with the same rigor.** When review (human, CI, or bot)
  finds a defect, treat the finding itself with RCA: why did my process miss
  this? If the answer is "no test covered it", add the test with the fix,
  not just the fix.

---

## 8. Review others' work (including bot reviews)

- **Verdict against HEAD, not against the diff summary.** Validate every
  substantive finding by reading the code as it exists on the PR HEAD. An
  "outdated" thread does not mean fixed; a mergeable status does not mean
  reviewed (`AGENTS.md` disposition rules).
- **Triage Gemini/automated findings into real vs noise, explicitly.** For
  each finding: *fix*, *false positive* (say why), *obsolete*, or
  *duplicate*. Bots are good at spotting inconsistency and bad at knowing
  intent — a bot finding that contradicts a deliberate repo convention
  (e.g. parallel `_SQLITE`/`_PG` constants) is noise; a bot finding about an
  unhandled error path is usually real.
- **Review for the class, comment on the instance.** If a PR has the same
  mistake in three places, one comment naming the pattern beats three
  comments naming lines.
- **Known-red is not new-red.** `dependency-audit` and `gitleaks` CI jobs are
  red on every run and are not merge blockers — but *new* failures in
  otherwise-green jobs always are. Learn which is which before dismissing a
  red check.
- **Never merge without an explicit instruction in the current message.**

---

## 9. Thinking habits — the meta-level

These are the habits that separate a sharp session from a flailing one:

- **Calibrate confidence to evidence.** "The tests pass" is evidence. "This
  looks right" is not. Track which of your claims are verified vs inferred,
  and never let an inference silently upgrade itself to a fact.
- **Notice surprise; it's your best signal.** When output differs from
  expectation — a test that passes when you expected failure, a grep with
  zero hits, a file that isn't where docs said — stop. Surprise means your
  model of the system is wrong somewhere, and proceeding on a wrong model
  compounds the error.
- **Prefer reversible probes to irreversible actions.** Read before write,
  dry-run before run, one-file change before ten-file change. Before any
  destructive or hard-to-reverse step (delete, force-push, prod script,
  overwrite), look at the target first and confirm the evidence supports
  *that specific* action.
- **Budget your context deliberately.** Read narrowly (the function, its
  callers, its tests) rather than whole files; summarize findings into your
  checklist file as you go. A session that reads everything remembers
  nothing after compaction.
- **Parallelize independent reads, serialize dependent writes.** Gathering
  (greps, file reads, test runs on different suites) can happen at once;
  edits whose correctness depends on each other cannot.
- **Time-box rabbit holes.** If an investigation has produced no new
  information in several attempts, change strategy: different search terms,
  read the tests instead of the source, add instrumentation, or write down
  what's known and ask. Repeating the same probe harder is not a strategy.
- **Distrust your own summary of long context.** After compaction or a long
  session, re-verify load-bearing facts (branch name, file paths, what was
  already pushed) against the repo, not against memory.
- **End turns on completed work, not on promises.** A turn that ends with
  "next I will…" should instead contain the doing. Stop only when the task
  is done, or blocked on input only the maintainer can provide — and then
  say precisely what is needed and why.

---

## 10. Pre-push self-check (the 60-second version)

Run down this list before every push:

1. Every changed line traces to the request; no drive-by edits.
2. Verification defined in the plan actually ran, and I watched it pass.
3. `db/` touched? → suite ran both SQLite *and* Postgres.
4. UI touched? → `npm run build` in `frontend/` green *and* the flow checked in a browser.
5. Scheduler/job ids, migrations, `deploy/` — danger zones re-checked.
6. No secrets in code, logs, output, or this PR's description.
7. Docs contract satisfied (`docs/PRODUCT_STATUS.md` / `docs/SYSTEM_DESIGN.md` /
   `docs/API_REFERENCE.md` / `docs/HANDOVER.md` as applicable, same PR).
8. Commit message says *why*, not just *what*.
9. If anything above is not true, the work is not done — say so honestly
   instead of pushing.
