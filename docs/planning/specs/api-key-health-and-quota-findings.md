# API Key Health & Quota System — Findings (RCA, no implementation)

**Status:** Observation only — this document contains **no code changes**. Findings are
verified against `main` at the commit this document merges on. Implementation is a
separate future phase (proposed as **AKH-1**/**AKH-2** below), executed per
[`execution-playbook.md`](execution-playbook.md) once activated.

**Trigger:** maintainer reported the notification bell flooding with "API key
unhealthy" alerts for every configured provider, every 6 hours, and separately asked
for a clear explanation of how API rate limits are calculated — reporting they
were "not sure."

---

## Finding 1 (P0 — active, ongoing) — API key health check has never once succeeded

**Summary:** the `api_key_health_check` scheduler job has been structurally incapable
of completing a single successful provider check since it shipped. It has run every 6
hours, unconditionally reporting every configured provider "unhealthy," for as long as
the feature has existed.

### Root cause

[`backend/monitoring/api_key_health.py:44-53`](../../../backend/monitoring/api_key_health.py) —
`_ping_json()` calls the shared HTTP helper:

```python
response = await resilient_request(
    method,
    url,
    source=source,
    operation="api_key_health",
    ...
)
```

`resilient_request`'s real signature
([`backend/resilient_client.py:245-248`](../../../backend/resilient_client.py)):

```python
async def resilient_request(
    source: str,
    method: str,
    url: str,
    *,
    ...
```

`source` is the **first positional parameter**, not keyword-only. The call above
passes `method` positionally into the `source` slot, `url` positionally into the
`method` slot — then *also* passes `source=source` as a keyword, which collides with
the already-bound first positional argument. Python raises exactly the error the
maintainer saw: `TypeError: resilient_request() got multiple values for argument
'source'`. This is unconditional — every one of the 10 provider check functions in
this file (`_check_nvd`, `_check_groq`, `_check_gemini`, `_check_cerebras`,
`_check_openrouter`, `_check_virustotal`, `_check_github`, `_check_otx`,
`_check_greynoise`, `_check_abuseipdb`) calls `_ping_json` the same broken way, so
every provider fails identically, every run, regardless of whether its actual API key
is valid.

### Why the job doesn't show as failed anywhere

`_ping_json`'s own `try/except` (line 62) catches the `TypeError` and returns a normal
`{"healthy": False, "error": "TypeError: ..."}` result instead of letting it propagate.
`run_api_key_health_checks()` treats that as a legitimate (if unhealthy) result and
completes normally — so the scheduler job status shows **success**, `_write_job_last_run`
records no error, and nothing on the Scheduler admin page flags this job as broken. The
only visible symptom is the flood of "unhealthy" notifications and (if it's rendered — see
Finding 1b) a permanently red status per provider.

### Why the notification bell floods instead of showing 10 alerts once

[`backend/monitoring/api_key_health.py:281`](../../../backend/monitoring/api_key_health.py):

```python
dedupe_key=f"api_key:{provider}:{payload['checked_at']}",
```

`checked_at` is a fresh per-run ISO timestamp (second precision). The dedupe key is
therefore **unique on every single run** — deduplication is structurally disabled for
this notification type. Every 6-hour run mints 10 brand-new "unique" notifications at
`severity="high"` that can never collapse or supersede the previous run's. This has
been running since the feature shipped; the bell will keep growing without bound until
either the bug is fixed or a maintainer manually clears it.

### Finding 1b — blast radius beyond the notification bell

`GET /api/admin/api-keys/health` and `POST /api/admin/api-keys/health/run`
([`backend/routers/admin.py:483-503`](../../../backend/routers/admin.py)) both call into
this same broken payload builder. Any admin surface reading this endpoint — and a
manual "run health check now" trigger — will show every configured provider red,
permanently, regardless of whether the underlying key actually works for real traffic
(feed ingestion, IOC lookups, LLM calls all use *different* code paths and are
**not** affected by this bug — this is purely the standalone health-ping feature).
BACKLOG already tracked the frontend half of this feature as unclear
("Issue 21 — API key suffix + provider health ping in UI | 🔶 backend #435 — UI tail?");
no committed frontend page currently renders this payload (checked: not in
`ApiKeysPage.jsx`), so the only *currently* user-visible symptom is the notification
flood. If/when the UI tail ships, it will inherit this bug and show every key red on
day one unless fixed first.

### Severity and urgency

**P0, but low-risk to fix and zero-risk to leave unpatched functionally** — this is a
monitoring-only feature; it does not gate or block any real provider call. The
*operational* cost is real, though: constant false HIGH-severity alarms teach the
operator to ignore the notification bell, which is exactly the condition under which a
genuine future alert gets missed ("cry wolf"). Recommend prioritizing the fix.

### Proposed fix (not implemented here)

Swap the argument order in the four calls inside `_ping_json` to
`resilient_request(source, method, url, ...)`, matching the real signature — a one-line
change repeated at one call site (the function is shared by all 10 checks). Separately,
fix the dedupe key to omit the timestamp (e.g. `f"api_key:{provider}:{payload['healthy']}"`
so the key changes only when status actually flips, not every run) — otherwise the
underlying bug's fix alone won't stop a *healthy*-provider re-notify loop from also being
possible in miniature. Both belong in one PR (proposed **AKH-1**) with a regression test
asserting `_ping_json` actually reaches the HTTP call (mock `resilient_request` and assert
it was awaited with the right positional args) — the bug would have been caught
immediately by any test that didn't mock past the buggy call.

---

## Finding 2 — "How are rate limits calculated" is genuinely hard to answer, because three unrelated systems share the name

This is not a bug — it's an architecture-clarity gap that directly explains the
maintainer's stated confusion.

### The three systems

| # | System | File | What it actually measures | Where it's surfaced |
|---|--------|------|---------------------------|----------------------|
| 1 | **Inbound throttling** | `rate_limit.py` | Requests made *to BRIEFR's own API* by its users, per endpoint bucket, since last restart. Protects BRIEFR from being hammered by its own analysts/scripts. | Admin nav → **"Rate limit"** page (`frontend/src/pages/admin/RateLimitPage.jsx`, `GET /api/admin/ratelimit`) |
| 2 | **Outbound quota accounting** | `tracking.py` (`API_LIMITS`, `get_usage_stats`, `get_ioc_usage_stats`) | Calls BRIEFR has made *to upstream providers* (NVD, VirusTotal, GreyNoise, OTX, etc.) against each provider's *published* daily/weekly/monthly/hourly limit (a hardcoded reference table sourced from provider docs, not live data from the provider). Drives the pre-flight `has_quota()` gate that blocks a local call before it would exceed quota. | Partially: `fetchIOCUsage()` → `GET /api/usage/ioc` is consumed by `IOCLookup.jsx` and `DetailDrawer`. **`fetchUsage()` → `GET /api/usage` (the full provider set, including NVD/feed sources) has zero frontend callers — dead code, unreachable in the UI today**, confirmed by repo-wide grep. |
| 3 | **Outbound request pacing** | `source_rate_limits.py` + `api_queue.py` / `resilient_client.py` | Minimum spacing *between individual requests* to each provider (e.g. OTX: 2 req/sec cap derived from its 10,000/hour published limit) — independent of the daily/monthly counters in system 2. Enforced by making calls wait in an internal queue; never surfaced anywhere in the UI. | Not surfaced in the UI at all |

### Why this reads as confusing

- The single word **"rate limit"** is the literal label on the Admin nav item for
  system 1 — which has nothing to do with NVD/VirusTotal/OTX quota. An operator
  looking for "how much of my NVD quota is used" who clicks "Rate limit" in Admin will
  see BRIEFR's own inbound bucket counters instead, with no cross-link or disambiguating
  copy pointing them anywhere else.
- System 2's full picture (`GET /api/usage`, covering every provider in `API_LIMITS`
  including NVD, KEV, EPSS, OSV, sploitus, circl, malwarebazaar, urlhaus — 12
  providers) is **fully computed correctly on the backend and completely invisible in
  the UI** — `fetchUsage()` exists in `api.js` but is never imported or called by any
  page or component. Only the 6-provider IOC-Lookup subset is visible, and only inside
  the IOC Lookup tab and drawer — not as a standalone "quota" page anyone would think
  to look for.
- System 3 (per-request pacing) is real and load-bearing (it's what actually prevents
  BRIEFR from tripping a provider's real rate limit) but has **no UI representation at
  all** — an operator has no way to see, e.g., "OTX calls are paced to 1 every 0.36s"
  without reading `source_rate_limits.py` directly.
- The notification-bell "API key unhealthy" feature (Finding 1) uses the phrase
  "API key" too, which is a *fourth*, unrelated concept (connectivity/auth health, not
  quota or rate limiting at all) — compounding the terminology collision.

### Proposed fix (not implemented here)

1. Rename the Admin nav "Rate limit" page label to something that doesn't imply
   provider quota — e.g. **"Inbound limits"** or **"Request throttling"** — plus one
   sentence of `HelpTip` copy distinguishing it from provider quota, per PRODUCT.md
   design principle 1 (every status word ships with a discoverable explanation).
2. Either wire `fetchUsage()` into a real page (a natural home: extend the existing
   `ApiKeysPage.jsx` with a full-provider quota table, reusing the `IOC_QUOTA_SERVICES`
   table pattern already built for the IOC tab) or delete the dead endpoint/function
   pair if it's judged not worth surfacing — currently it is neither used nor removed,
   which is the worst of both (maintained dead code).
3. Add one `HelpTip`-covered summary line to whichever page ends up showing provider
   quota, explaining the three-tier model in one sentence: *"Quota = calls counted
   against each provider's published daily/monthly limit. Pacing = minimum spacing
   between individual requests, enforced automatically. Neither is BRIEFR's own inbound
   rate limit (see Admin → Inbound limits)."*

This maps cleanly onto BACKLOG's existing **Issue 21** ("API key suffix + provider
health ping in UI") and **UX-J1** (domain-term explanation sweep) — both already queued;
this finding narrows their scope with concrete detail rather than opening new items.

---

## Backlog entries

Recorded in [`BACKLOG.md`](../BACKLOG.md) §3 as **AKH-1** (fix the TypeError + dedupe
key, P0, small) and **AKH-2** (quota-system clarity: nav rename, wire or remove dead
`/api/usage`, HelpTip copy — folds into the existing Issue 21 / UX-J1 scope).

## Related documents

| Doc | Relationship |
|-----|--------------|
| [`execution-playbook.md`](execution-playbook.md) | AKH-1/AKH-2 execute under its phase loop once activated |
| [`ux-audit.md`](ux-audit.md) Issue 21 | Frontend tail for the health-ping feature — now scoped precisely |
| [`BACKLOG.md`](../BACKLOG.md) §5 UX-J1 | Domain-term sweep — AKH-2's HelpTip copy belongs in the same pass |
