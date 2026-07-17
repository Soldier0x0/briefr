# PHASE 7 — Security · Authentication · Authorization (RBAC) · Input Validation · API Security · Secrets Management · Privacy & Data Leakage · Dependency & Supply Chain

*Reviewed at commit `61c686f`. Auth in `backend/auth/*` + `auth_middleware.py` + `dependencies.py`;
crypto in `settings_crypto.py`; SSRF in `webhooks/ssrf.py`; redaction in `redact.py`.*

---

## Executive Summary

For a security product, this is a **security-literate codebase** — the defenses are textbook and
mostly correct. Highlights: **SSRF protection** (`webhooks/ssrf.py`) is comprehensive — blocks
RFC1918/CGNAT/loopback/link-local/ULA networks, pins resolved IPs on the wire, HTTPS-only, disables
redirects, and strips internal secret headers (`FORBIDDEN_OUTBOUND_HEADERS`) from outbound webhooks.
**Password handling** uses bcrypt (cost 12) with a `DUMMY_HASH` constant-time path to defeat username
enumeration via timing. **Session tokens** are `secrets.token_urlsafe(32)` stored as SHA-256 hashes,
not plaintext. **Secrets at rest** are Fernet-encrypted (`settings_crypto.py`, `enc:v1:` prefix,
ADR-006). **Security headers** are complete (CSP, `X-Frame-Options: DENY`, `nosniff`,
`Referrer-Policy`, `Permissions-Policy`). There's a **self-auditing production posture report**
(`production_posture_warnings`) and secure defaults (`rate_limit_enabled=True`,
`auth_cookie_secure=True`). SQL is parameterized (only **1** f-string `execute` in the whole
`db/`+`routers/` tree), and the DB explorer is **deny-by-default allowlist** validated
(`explorer_registry.py`) with identifiers drawn only from a validated `TableSpec`. A proper
`SECURITY.md` disclosure policy exists.

The findings are a small number of **real gaps**, not a weak posture: (1) the **production
"JWT_SECRET must be set" fail-closed guard is dead code** — an auto-generation block runs first and
always populates `settings.jwt_secret`, so the `RuntimeError` can never fire; production silently
auto-generates a secret, and in a multi-replica deploy each replica generates a *different* secret →
cross-replica session rejection; (2) **rate limiting is per-process by default** (shared DB store is
opt-in via `BRIEFR_RATE_LIMIT_STORE=db`), so multi-worker deployments enforce N× the configured
limit; (3) the **`dependency-audit` CI job is known-red**, so known-vulnerable dependencies may be
shipping without triage; (4) frontend deps use caret ranges (lockfile-mitigated, but no
frozen-lockfile guarantee beyond `npm ci`).

**Overall Score: 8 / 10.**

---

## Findings

### F7.1 — Production JWT-secret fail-closed guard is unreachable (dead code) · Priority: HIGH · Architectural
- **Location:** `backend/settings.py:96-113` — auto-generation block sets
  `os.environ["JWT_SECRET"]` and `settings.jwt_secret = _generated_secret` (lines 106-107)
  **before** the guard `if settings.is_production and not settings.jwt_secret: raise RuntimeError(...)`
  (line 110). Because line 107 always populates the secret, `not settings.jwt_secret` is always
  False and the guard never triggers.
- **Description:** The intended behavior — "refuse to start in production without an explicit
  `JWT_SECRET`" — cannot happen. In production with no `JWT_SECRET`, the app silently generates one
  and writes it to `.env`. Two concrete harms: (a) the fail-closed contract operators rely on is an
  illusion; (b) in any multi-replica / read-only-fs / ephemeral-container deployment, each replica
  generates a **different** secret (or fails the `set_key` silently via the `except OSError: pass`),
  so tokens signed by replica A are rejected by replica B → users randomly logged out, and secret
  provenance is non-deterministic.
- **Why it matters:** JWT signing key management is foundational auth security. A silently
  auto-generated, per-replica, `.env`-persisted secret undermines session integrity guarantees and
  makes horizontal scaling unsafe. This is the highest-severity finding in the security phase.
- **Evidence:** ordering at `settings.py:96-113`; `os.environ`/`settings` assignment precedes the
  `is_production` guard; `except OSError: pass` swallows write failures.
- **Risk:** No true production enforcement; cross-replica session invalidation; non-deterministic
  key provenance; secret written to disk unexpectedly.
- **Recommended solution:** Reorder so the production guard runs **before** any auto-generation:
  ```python
  if settings.is_production and not settings.jwt_secret:
      raise RuntimeError("JWT_SECRET must be set in production (openssl rand -hex 32)")
  if not settings.jwt_secret:            # dev/test only
      _generated = secrets.token_hex(32)
      ...persist to .env...
  ```
  Never auto-generate in production. If `set_key` fails, do not silently continue in dev either —
  log a clear warning. Document that all replicas must share `JWT_SECRET` from the environment.
- **Acceptance criteria:** Starting in production (`is_production`) with no `JWT_SECRET` raises and
  the process exits non-zero; a test asserts this; dev still auto-generates.
- **Effort:** Quick Win (reorder) but **High priority**. **Type:** Architectural (security).

### F7.2 — Rate limiting is per-process by default → N× effective limits under multi-worker · Priority: MEDIUM · Architectural
- **Location:** `backend/rate_limit_store.py` (in-memory default; shared DB buckets only when
  `BRIEFR_RATE_LIMIT_STORE=db`), `backend/rate_limit.py`.
- **Description:** Token buckets live in process memory unless the shared store is enabled. With
  `uvicorn --workers N` or multiple replicas, each worker maintains its own buckets, so a limit of
  "60/min" becomes "60/min × N" globally — weakening brute-force/abuse protection precisely on the
  auth and IOC endpoints the limiter is meant to protect.
- **Why it matters:** Rate limiting is a primary control against credential stuffing and API abuse;
  its guarantee silently degrades with horizontal scale, and the default hides this.
- **Evidence:** `shared_store_enabled()` gates the DB-backed buckets; default is in-memory.
- **Recommended solution:** Make the shared store the default when more than one worker/replica is
  configured (or detect and warn loudly at startup if multi-worker + in-memory limiter). Document
  the requirement in `OPERATIONS.md`. Add the "in-memory limiter with >1 worker" case to
  `production_posture_warnings`.
- **Acceptance criteria:** Multi-worker startup either uses the shared store or emits a posture
  warning; auth-endpoint limits hold globally under 2 workers in a test.
- **Effort:** Medium. **Type:** Architectural.

### F7.3 — `dependency-audit` CI job is known-red → unassessed vulnerable dependencies · Priority: HIGH · Quick Win
- **Location:** `.github/workflows/backend-tests.yml` `dependency-audit` job (`pip-audit` +
  `npm audit --audit-level=high`); CLAUDE.md declares it "known-red on every run."
- **Description:** The supply-chain gate is permanently failing and treated as non-blocking, which
  means nobody is triaging what it reports — the exact opposite of its purpose. A genuinely exploitable
  transitive CVE would be indistinguishable from the standing red.
- **Why it matters:** For a security product, shipping known-vulnerable dependencies is both a real
  risk and a reputational one; a red-and-ignored audit is worse than no audit because it signals
  "we looked and don't care."
- **Evidence:** CLAUDE.md "known-red"; job present but failing on this PR too.
- **Recommended solution:** Triage the current `pip-audit`/`npm audit` findings; for each, either
  upgrade, or record an explicit, time-boxed ignore with justification (`pip-audit --ignore-vuln
  GHSA-…`, npm `overrides`) tracked in an issue. Then make the job **required and green**. The
  existing `overrides` for `dompurify`/`uuid` show this pattern already works — extend it.
- **Acceptance criteria:** `dependency-audit` is green with any accepted risks explicitly listed and
  justified; a new high-severity advisory turns it red (actionable signal).
- **Effort:** Quick Win–Medium (triage-dependent). **Type:** Quick Win.

### F7.4 — Frontend dependencies use caret ranges; no frozen-lockfile guarantee beyond `npm ci` · Priority: MEDIUM · Quick Win
- **Location:** `frontend/package.json` (all deps `^x.y.z`); `package-lock.json` present; CI uses
  `npm ci --ignore-scripts`.
- **Description:** `npm ci` respects the lockfile (good), but caret ranges mean a lockfile refresh
  can silently pull new minor/patch versions, and there's no integrity/provenance check beyond the
  lock. `--ignore-scripts` is a good supply-chain hardening (prevents install-time script execution).
- **Why it matters:** Supply-chain attacks increasingly target minor/patch releases; a security
  product should have deterministic, reviewed dependency updates.
- **Recommended solution:** Keep `npm ci --ignore-scripts` everywhere (already done). Add
  `npm audit signatures` / provenance verification where available; consider pinning exact versions
  for the highest-risk deps (the ones handling untrusted content — `dompurify`, `jspdf`,
  `html2canvas`, `write-excel-file`). Enable Dependabot/Renovate with review gates for controlled
  updates.
- **Acceptance criteria:** Lockfile changes are reviewed; high-risk deps pinned; provenance checked
  in CI where supported.
- **Effort:** Quick Win. **Type:** Quick Win.

### F7.5 — DB-explorer builds SQL via `.format()` on identifiers — safe today, harden defensively · Priority: LOW · Quick Win
- **Location:** `backend/db/explorer.py:146-229` (`.format(table=spec.name, column=f_col)`),
  `explorer_registry.py::validate_table_name` (deny-by-default allowlist returning a `TableSpec`).
- **Description:** Identifier interpolation via `.format()` is **currently safe** because table and
  column names come only from a validated allowlist (`TableSpec`), never raw user input, and values
  are parameterized. This is the correct pattern — noted as a strength. The residual risk is future
  drift: a new code path that passes an unvalidated name into the same `.format()` helpers.
- **Why it matters:** Identifier interpolation is one refactor away from injection if the allowlist
  invariant is ever bypassed; defense-in-depth is cheap here.
- **Recommended solution:** Add belt-and-suspenders quoting (`psycopg.sql.Identifier` / an explicit
  `"…"`-quote + name-regex assert) inside the explorer helpers so even an unvalidated name can't
  break out; add a unit test feeding a hostile table name and asserting rejection.
- **Acceptance criteria:** A hostile `table`/`column` argument is rejected/quoted, not interpolated
  raw; test proves it.
- **Effort:** Quick Win. **Type:** Quick Win.

### F7.6 — Input validation: confirm Pydantic coverage on all mutation bodies + payload size limits · Priority: MEDIUM · Architectural
- **Location:** `backend/routers/*` (FastAPI + Pydantic), `python-multipart` for uploads; no global
  request-body size limit observed in `main.py` middleware.
- **Description:** FastAPI/Pydantic gives strong typed validation where request models are used, but
  (a) coverage should be confirmed for every POST/DELETE body (some handlers may accept `dict`/raw
  JSON), and (b) there's no visible global max-body-size / upload-size guard, so a large payload
  (import, bulk ops, webhook config) could pressure memory before validation.
- **Why it matters:** Unbounded/loosely-typed inputs are a DoS and injection surface; for a
  multi-org product, input hardening is table stakes.
- **Recommended solution:** Audit every mutation endpoint for an explicit Pydantic model (ban raw
  `dict` bodies); add a request-body size limit middleware and per-endpoint upload caps; validate
  content-type on uploads. Add fuzz/property tests for the IOC and import parsers.
- **Acceptance criteria:** Every mutation endpoint has a typed model; oversized bodies are rejected
  with 413 before processing; parser fuzz tests pass.
- **Effort:** Medium. **Type:** Architectural.

### F7.7 — Privacy & data leakage: strong redaction — extend to LLM egress and error paths · Priority: MEDIUM · Architectural
- **Location:** `backend/redact.py` (secret/URL masking), `structured_logging.py` (redacts
  `*_KEY/_TOKEN/_SECRET/_PASSWORD` extra fields), `ai/llm_router.py` + `ai/llm_payload.py` (outbound
  LLM calls to third-party providers).
- **Description:** In-house redaction is good for config/audit/API responses and structured logs.
  The higher-risk egress is the **LLM providers**: CVE/exploit text and detection artifacts are sent
  to Groq/Gemini/Cerebras/OpenRouter. For self-hosted security teams, what leaves the network to a
  third party is a privacy/compliance concern (some orgs cannot send internal asset names or
  intel to external LLMs).
- **Why it matters:** Data-residency/egress control is a common enterprise procurement gate; sending
  potentially sensitive fields to external LLMs without an explicit, documented data-flow and opt-out
  can be a dealbreaker.
- **Recommended solution:** Document exactly what fields are sent to which LLM providers (data-flow
  in `docs/`); ensure user asset/stack names are never included in LLM payloads unless explicitly
  opted in; provide a "no external LLM" mode (local-only) and make LLM features fully disable-able
  (some already are via flags — document and verify). Redact secrets from any error `detail` returned
  to clients (CLAUDE.md already mandates this — add a test).
- **Acceptance criteria:** A documented LLM data-flow; a config that disables all external egress;
  a test that internal asset names never appear in LLM payloads.
- **Effort:** Medium. **Type:** Architectural.

### F7.8 — Authorization is two-role (user/admin); no granular RBAC or per-object authz · Priority: LOW · Architectural
- **Location:** `dependencies.py::require_user`/`require_admin` (role re-read from DB each request —
  good), `routers/admin.py` router-level `require_admin`.
- **Description:** RBAC is binary (analyst vs admin). Role is re-read live so demotions take effect
  immediately (a genuine strength). But there's no finer granularity (read-only analyst, feed
  operator, billing/owner) and no per-object/tenant authorization — everything is single-tenant with
  two roles.
- **Why it matters:** Enterprise/multi-org deployments typically need least-privilege roles and, for
  SaaS, tenant isolation. Fine for single-team self-host; a gap for the "thousands of orgs" ambition
  if that means multi-tenant.
- **Recommended solution:** If multi-tenant SaaS is a goal (Phase 11), design a role/permission model
  and tenant-scoping now; if it remains single-tenant self-host, document that explicitly and add at
  least a read-only analyst role. Also close the Phase-2 F2.6 gap (middleware defense-in-depth for
  admin prefixes).
- **Acceptance criteria:** Documented authz model; either richer roles + tenant scoping, or an
  explicit single-tenant statement + read-only role.
- **Effort:** Medium–Large. **Type:** Architectural.

---

## Overall Score: **8 / 10**

| Sub-audit | Score |
|---|---|
| Security (general) | 8 / 10 |
| Authentication | 7.5 / 10 |
| Authorization (RBAC) | 7.5 / 10 |
| Input Validation | 8 / 10 |
| API Security | 8.5 / 10 |
| Secrets Management | 8 / 10 |
| Privacy & Data Leakage | 7.5 / 10 |
| Dependency & Supply Chain | 6.5 / 10 |

## Strengths
- Textbook SSRF defense (network allow/deny, IP pinning, no redirects, secret-header stripping).
- bcrypt(12) + `DUMMY_HASH` timing defense; SHA-256-hashed session tokens; Fernet-encrypted
  secrets at rest.
- Complete security headers incl. CSP; secure-by-default flags; self-auditing production posture
  report; live role re-read for instant demotion.
- Parameterized SQL (1 f-string in the entire query surface); deny-by-default DB-explorer allowlist;
  structured-log secret redaction; proper `SECURITY.md` disclosure policy; `--ignore-scripts` npm CI.

## Weaknesses
- Production JWT fail-closed guard is dead code (F7.1) — the standout issue.
- Per-process rate limiting default (F7.2); known-red dependency audit (F7.3); caret FE deps (F7.4).
- LLM egress privacy not documented/gated (F7.7); binary RBAC only (F7.8).

## Immediate Action Items
1. **Reorder the JWT guard so production fails closed without `JWT_SECRET` (F7.1).**
2. Triage and green the `dependency-audit` job; record justified ignores (F7.3).
3. Default/warn the shared rate-limit store under multi-worker (F7.2).

## Long-Term Recommendations
1. Document LLM data-flow + provide a no-external-egress mode (F7.7).
2. Audit all mutation bodies for typed models + add body-size limits and parser fuzzing (F7.6).
3. Decide the RBAC/tenancy model for multi-org (F7.8); add belt-and-suspenders identifier quoting
   in the DB explorer (F7.5); harden FE dependency provenance (F7.4).

## Production-Readiness Assessment (Phase 7 areas)
**Strong, with one must-fix — 8/10.** The security engineering is well above the bar for a
self-hosted tool and reflects genuine expertise (SSRF, timing defense, at-rest encryption, posture
self-audit). **F7.1 (dead production JWT guard) should be fixed before any production sign-off** —
it's a small code change with outsized correctness/scaling implications. The supply-chain gate
(F7.3) must be made trustworthy for a security vendor. LLM egress (F7.7) and RBAC/tenancy (F7.8) are
the items that gate *enterprise/multi-tenant* readiness specifically. Single-tenant self-host
security is production-ready once F7.1 and F7.3 are closed.
