# Self-stack Risk Register precision — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admit live Risk Register self-exposure rows only when CVE CPE/`affected_products` scores against pinned self-stack assets via `matching.cpe`, eliminating description-substring false positives.

**Architecture:** Enrich generated `self_stack.yaml` with ecosystem + version pins; rewrite `self_stack_risk_rows` to treat stack entries as assets and score with existing `score_cve_for_assets` (hydrate CPE from `cpe_matches` or `vendor:product` affected_products). UI shows match basis (`product+version` vs `product-only`).

**Tech Stack:** Python corpus generator, `matching.cpe`, security_architecture merge, React Risk Register copy, pytest.

## Global Constraints

- Spec SSOT: `docs/superpowers/specs/2026-07-21-self-stack-risk-precision-design.md`
- Branch: `cursor/self-stack-precision-91c2` off fresh `origin/main` **after** Program 1 (`verify-local-gate`) merges
- Reuse `backend/matching/cpe.py` — do not duplicate version-range logic
- **No** description-substring admission path for live risk rows
- Admission: score 100 → strong; score 55 → weaker labeled; score 0 → exclude
- Embeddings not used as primary matcher
- Do not change FEED/wallboard `_stack_match_clause` behavior in this plan
- No dismiss workflow; no Docker/Windows packaging; no full SBOM
- Update corpus generator tests that currently assert pin-stripping
- After generator shape change: regenerate corpus and keep drift tests green
- Docs: `PRODUCT_STATUS`, `HANDOVER`, methodology/help strings
- Gemini before merge; no graphify required

## File map

| Path | Responsibility |
|------|----------------|
| `scripts/generate_security_corpus.py` | Parse pins + ecosystem into self_stack entries |
| `backend/security_architecture/corpus/self_stack.yaml` | Regenerated richer terms |
| `backend/security_architecture/merge.py` | Structured live-risk matching |
| `backend/tests/test_security_architecture_corpus.py` | Generator pin/ecosystem tests |
| `backend/tests/test_security_architecture_live.py` | Live row FP/TP + match_basis |
| `frontend/.../RiskRegisterSection.jsx` (+ help/overview if needed) | Match-basis display |
| `docs/PRODUCT_STATUS.md`, `docs/HANDOVER.md` | Runtime truth |

---

### Task 1: Self-stack generator preserves pins + ecosystem

**Files:**
- Modify: `scripts/generate_security_corpus.py`
- Modify: `backend/tests/test_security_architecture_corpus.py`

**Interfaces:**
- Produces: each self_stack entry includes at least:
  - `term: str`
  - `source: str`
  - `ecosystem: "pypi" | "npm" | "runtime"`
  - `version: str | null` (pinned/exact when known; null when unpinned/`*`/range-only npm if not parseable to a single pin — prefer storing raw pin string when `==X.Y` / exact version; for npm ranges like `^18.2.0` store the range string in `version` and let scorer treat non-exact as version-present only when CPE compare accepts it, **or** set `version` null for non-exact ranges and rely on product-only score 55 — **choose: store exact pins only; npm `^`/`~` → `version: null` for v1**)
- Consumes: `requirements.txt`, `package.json`, `_RUNTIME_COMPONENTS`

**Decision (verbatim):**  
- PyPI: parse `name==1.2.3` → `version="1.2.3"`; bare name → `version=null`  
- npm: only exact versions (no `^`/`~`/`>=`) set `version`; otherwise `version=null`  
- ecosystem: requirements → `pypi`; package.json → `npm`; runtime list → `runtime`

- [ ] **Step 1: Update / replace failing tests**

Replace pin-stripping expectations with pin-preserving API. Example:

```python
def test_extract_requirements_entries_keeps_exact_pins():
    text = "fastapi==0.115.0\n# comment\nuvicorn\nbcrypt>=4.0\n"
    entries = gen.extract_requirements_entries(text)
    by_name = {e["name"]: e for e in entries}
    assert by_name["fastapi"]["version"] == "0.115.0"
    assert by_name["uvicorn"]["version"] is None
    assert by_name["bcrypt"]["version"] is None  # inequality → no exact pin

def test_build_self_stack_yaml_includes_ecosystem_and_version():
    out = gen.build_self_stack_yaml(
        [{"name": "fastapi", "version": "0.115.0"}],
        [{"name": "react", "version": None}],
        ["postgresql"],
    )
    fastapi = next(e for e in out if e["term"] == "fastapi")
    assert fastapi["ecosystem"] == "pypi"
    assert fastapi["version"] == "0.115.0"
    react = next(e for e in out if e["term"] == "react")
    assert react["ecosystem"] == "npm"
    assert react["version"] is None
    pg = next(e for e in out if e["term"] == "postgresql")
    assert pg["ecosystem"] == "runtime"
```

Adapt function names if you keep thin wrappers; tests must encode the decision above.

- [ ] **Step 2: Run FAIL**

```bash
cd backend && pytest tests/test_security_architecture_corpus.py -k self_stack -q
```

Expected: FAIL (API missing / old strip behavior)

- [ ] **Step 3: Implement extractors + `build_self_stack_yaml`**

Update call sites in the generator’s `main`/write path. Keep required corpus fields (`id`, `title`, `summary`, `owner`, `status`, `origin`, `term`, `source`) and add `ecosystem`, `version`.

- [ ] **Step 4: PASS + commit**

```bash
git commit -m "feat(secarch): preserve self-stack version pins and ecosystem"
```

---

### Task 2: Structured live risk matching via CPE scorer

**Files:**
- Modify: `backend/security_architecture/merge.py`
- Modify: `backend/tests/test_security_architecture_live.py`
- Possibly small shared hydrate helper in `merge.py` (mirror correlation’s `vendor:product` → cpe dict)

**Interfaces:**
- Produces: `self_stack_risk_rows` returns only score∈{55,100} rows with fields including:
  - existing live fields
  - `match_score: int` (55 or 100)
  - `match_basis: "product+version" | "product-only"`
- Consumes: corpus self_stack terms; `matching.cpe.score_cve_for_assets`; CVE `cpe_matches` / `affected_products`

**Hydration (verbatim pattern):**

```python
def _hydrate_cpe_matches(row: dict) -> list[dict]:
    import json
    raw = row.get("cpe_matches")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    matches = list(raw or [])
    if matches:
        return matches
    products = row.get("affected_products")
    if isinstance(products, str):
        try:
            products = json.loads(products)
        except json.JSONDecodeError:
            products = []
    out = []
    for entry in products or []:
        if isinstance(entry, str) and ":" in entry:
            vendor, product = entry.split(":", 1)
            out.append({"vendor": vendor, "product": product})
        elif isinstance(entry, dict) and entry.get("product"):
            out.append({
                "vendor": entry.get("vendor") or "",
                "product": entry.get("product") or "",
                "version": entry.get("version"),
                "version_start_including": entry.get("version_start_including"),
                "version_start_excluding": entry.get("version_start_excluding"),
                "version_end_including": entry.get("version_end_including"),
                "version_end_excluding": entry.get("version_end_excluding"),
            })
    return out
```

**Assets from corpus:**

```python
def _self_stack_assets(corpus) -> list[dict]:
    entries = (corpus.get("self_stack") or {}).get("terms") or []
    assets = []
    for e in entries:
        term = e.get("term") or e.get("title")
        if not term:
            continue
        assets.append({
            "product": term,
            "vendor": e.get("vendor") or "",
            "version": (e.get("version") or "").strip(),
        })
    return assets
```

- [ ] **Step 1: Failing tests**

```python
def test_curveball_does_not_match_pypi_cryptography(monkeypatch):
    # Build minimal corpus asset cryptography pypi; CVE row with Windows cryptoapi CPE only
    # Assert self_stack_risk_rows excludes it

def test_product_version_match_is_strong():
    # Asset react version 18.2.0; CVE cpe product react with version range including 18.2.0
    # Assert one live row match_basis == "product+version", match_score == 100

def test_product_only_match_is_weaker_labeled():
    # Asset without version; CPE product match without forcing version
    # Assert match_basis == "product-only", match_score == 55
```

Use DB seed helpers already in `test_security_architecture_live.py` where practical; pure unit tests of helpers are fine for CurveBall.

- [ ] **Step 2: FAIL then implement `self_stack_risk_rows`**

Remove `_stack_match_clause` usage from this function. Query strategy must not admit on description `LIKE`. Suggested approach:

1. Load KEV/CRITICAL CVEs that have non-empty `cpe_matches` OR non-empty `affected_products` (SQL), cap reasonably (e.g. existing LIMIT 50 **after** scoring, or fetch a larger candidate pool then filter — prefer fetch candidates then score, return top admitted ≤50 ordered by is_kev, score, published).
2. For each row, hydrate CPE, `score = score_cve_for_assets(cpes, assets)`; keep if score in (55, 100).
3. Set title/summary to include match basis and pinned version when present; stop claiming mere “term match” as the sole story.

- [ ] **Step 3: Update overview help string** in `security_architecture/routers/security_architecture.py` if it still says fuzzy term match only.

- [ ] **Step 4: PASS + commit**

```bash
git commit -m "feat(secarch): score self-stack live risks with CPE matcher"
```

---

### Task 3: UI match-basis honesty + docs + corpus regen

**Files:**
- Modify: `frontend/src/pages/security-architecture/sections/RiskRegisterSection.jsx`
- Modify: overview tile help if rendered from FE constants
- Modify: `docs/PRODUCT_STATUS.md`, `docs/HANDOVER.md`
- Regenerate: `backend/security_architecture/corpus/` via generator (self_stack shape change)

- [ ] **Step 1: Show match basis in grid**

Add column or annotate summary/title using `match_basis` / `match_score` when present:

- `product+version` → e.g. chip/text `MATCH: product+version`
- `product-only` → `MATCH: product-only (version unverified)`

Keep design tokens; no hardcoded colors. Left-align is fine; do **not** solve wrap/ellipsis in this task (out of scope).

- [ ] **Step 2: Regenerate corpus**

```bash
backend/.venv/bin/python scripts/generate_security_corpus.py
cd backend && pytest tests/test_security_architecture_corpus.py -q
```

- [ ] **Step 3: Docs**

HANDOVER newest entry; PRODUCT_STATUS note that live self-stack risks use CPE/`affected_products` scoring with version pins when available.

- [ ] **Step 4: `npm run build` + targeted pytest**

```bash
cd backend && pytest tests/test_security_architecture_live.py tests/test_security_architecture_corpus.py -q
cd frontend && npm run build
```

- [ ] **Step 5: Commit + PR**

```bash
git commit -m "feat(secarch): surface self-stack match basis and regenerate corpus"
```

Push `cursor/self-stack-precision-91c2`, Gemini, merge.

---

## Spec coverage self-review

| Design requirement | Task |
|--------------------|------|
| Preserve pins + ecosystem | Task 1 |
| CPE scorer admission 100/55/0 | Task 2 |
| No description LIKE path | Task 2 |
| UI match basis + docs | Task 3 |
| CurveBall FP excluded | Task 2 tests |
| Embeddings not primary | Global Constraints |
