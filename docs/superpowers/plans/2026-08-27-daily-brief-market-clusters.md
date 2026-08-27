# Daily brief MARKET clusters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a SQL-only `// MARKET` product cluster section to the daily brief so a 700–2000 CVE day stays under Discord 2000 characters.

**Architecture:** Pure functions in `backend/reports/market_clusters.py` pick a primary product and rank clusters. `collect_daily_brief` loads every CVE published in the window (same published-timestamp normalization as Critical/High) and attaches a `market` rollup. The formatter renders `// MARKET` after COUNTS. No LLM call for clusters.

**Tech Stack:** FastAPI/Python daily brief collector, existing `cpe_matches` / `affected_products` JSON, pytest.

**Spec:** `docs/superpowers/specs/2026-08-27-daily-brief-market-clusters-design.md`

## Global Constraints

- No email, no per-user webhook URLs, no `last_login_at`, no description LIKE for product assignment.
- Facts are local SQL / local JSON parse. MARKET does **not** call `chat_completion_task`.
- One CVE → one product cluster. Weight: `critical*10 + high*3 + medium*1 + low*0`.
- Top 8 product lines; `+N products in BRIEFR.` for the rest.
- Discord 2000 assembly cap unchanged. Never drop `market` in overflow.
- No inline imports. Empty CPE → `unanalyzed`.
- Merge gate focused tests: `pytest tests/test_daily_brief.py tests/test_market_clusters.py`.

---

### File map

| File | Responsibility |
|------|----------------|
| Create: `backend/reports/market_clusters.py` | Primary product, cluster, rank, format lines |
| Create: `backend/tests/test_market_clusters.py` | Unit tests, no DB |
| Modify: `backend/reports/daily_brief.py` | Fetch published rows, attach market, format, payload, quiet headline |
| Modify: `backend/tests/test_daily_brief.py` | Collector + format integration |
| Modify: `docs/design/daily-brief-format.md` | MARKET grammar |
| Modify: `docs/API_REFERENCE.md`, `docs/PRODUCT_STATUS.md` | Contract |

---

### Task 1: Cluster functions

**Files:**
- Create: `backend/reports/market_clusters.py`
- Test: `backend/tests/test_market_clusters.py`

**Interfaces:**
- Consumes: CVE dicts with `severity`, `cpe_matches`, `affected_products`
- Produces: `UNANALYZED_LABEL = "unanalyzed"`; `def primary_product(cpe_matches, affected_products) -> str`; `def cluster_published(rows: list[dict]) -> dict` with keys `published, critical, high, medium, low, products, omitted_products`; `def format_market_section(market: dict) -> list[str]` (no `// MARKET` title if published==0, else title + header + bullets + optional omitted line); `def cluster_weight(c,h,m,l) -> int`

- [ ] **Step 1: Write the failing tests**

```python
"""Product clusters for daily brief MARKET (no DB)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reports.market_clusters import (
    cluster_published,
    cluster_weight,
    format_market_section,
    primary_product,
)


def test_primary_product_prefers_first_cpe_product():
    assert primary_product(
        [{"vendor": "f5", "product": "nginx", "version": "1.25"}],
        '["apache:httpd"]',
    ) == "nginx"


def test_primary_product_falls_back_to_affected_products():
    assert primary_product("", '["python:python"]') == "python"
    assert primary_product("[]", '["nginx"]') == "nginx"


def test_primary_product_unanalyzed_when_empty():
    assert primary_product("", "") == "unanalyzed"
    assert primary_product("[]", "[]") == "unanalyzed"


def test_cluster_one_cve_one_bucket_and_merges_same_product():
    rows = [
        {"severity": "CRITICAL", "cpe_matches": '[{"product":"nginx"}]', "affected_products": ""},
        {"severity": "HIGH", "cpe_matches": '[{"vendor":"f5","product":"nginx"}]', "affected_products": ""},
        {"severity": "MEDIUM", "cpe_matches": "", "affected_products": '["oracle:oracle_database"]'},
        {"severity": "LOW", "cpe_matches": "", "affected_products": ""},
    ]
    market = cluster_published(rows)
    assert market["published"] == 4
    assert market["critical"] == 1
    assert market["high"] == 1
    assert market["medium"] == 1
    assert market["low"] == 1
    by_label = {p["label"]: p for p in market["products"]}
    assert by_label["nginx"]["total"] == 2
    assert by_label["nginx"]["critical"] == 1
    assert by_label["nginx"]["high"] == 1
    assert by_label["oracle database"]["total"] == 1
    assert by_label["unanalyzed"]["total"] == 1


def test_weighted_rank_puts_openssl_above_medium_volume():
    rows = []
    for _ in range(40):
        rows.append({"severity": "MEDIUM", "cpe_matches": '[{"product":"windows"}]', "affected_products": ""})
    for _ in range(3):
        rows.append({"severity": "CRITICAL", "cpe_matches": '[{"product":"openssl"}]', "affected_products": ""})
    market = cluster_published(rows)
    assert market["products"][0]["label"] == "openssl"
    assert cluster_weight(3, 0, 0, 0) > cluster_weight(0, 0, 40, 0)


def test_top_eight_and_omitted_count():
    rows = []
    for i in range(12):
        rows.append({
            "severity": "HIGH",
            "cpe_matches": f'[{{"product":"p{i:02d}"}}]',
            "affected_products": "",
        })
    market = cluster_published(rows)
    assert len(market["products"]) == 8
    assert market["omitted_products"] == 4
    assert market["published"] == 12


def test_format_market_section_grammar():
    market = cluster_published([
        {"severity": "CRITICAL", "cpe_matches": '[{"product":"nginx"}]', "affected_products": ""},
    ])
    lines = format_market_section(market)
    assert lines[0] == "// MARKET"
    assert lines[1].startswith("Published: 1")
    assert "• nginx  1  (C 1 · H 0 · M 0 · L 0)" in lines
    assert not any(line.startswith("+") for line in lines)


def test_format_omits_section_when_empty():
    assert format_market_section(cluster_published([])) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 .venv/bin/python -m pytest tests/test_market_clusters.py -q`

Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation** in `backend/reports/market_clusters.py` matching the spec (JSON parse of list/str, unknown severity → medium, weight formula, display label `_` → space, top 8).

- [ ] **Step 4: Run tests to verify they pass**

Run: same pytest command. Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/reports/market_clusters.py backend/tests/test_market_clusters.py
git commit -m "feat(reports): cluster daily-brief published CVEs by product"
```

---

### Task 2: Collector, formatter, docs

**Files:**
- Modify: `backend/reports/daily_brief.py`
- Modify: `backend/tests/test_daily_brief.py`
- Modify: `docs/design/daily-brief-format.md`
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/PRODUCT_STATUS.md`

**Interfaces:**
- Consumes: `cluster_published`, `format_market_section` from Task 1
- Produces: `DailyBrief.market: dict`; `collect_daily_brief` fills it from all published-in-window rows (same `REPLACE(SUBSTR(published,1,19),'T',' ')` bounds as Critical/High, **no LIMIT** on this query); `format_daily_brief_text` inserts MARKET after COUNTS; `brief_to_payload` includes `market`; `template_headline` not quiet when `market["published"] > 0`; `LIST_DROP_ORDER` does **not** include `market`

- [ ] **Step 1: Write failing tests** in `backend/tests/test_daily_brief.py`:

```python
def test_market_clusters_all_published_not_just_critical(db_env):
    from reports.daily_brief import collect_daily_brief, format_daily_brief_text, template_headline

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            for cve_id, sev, cpe, pub in (
                ("CVE-2026-M1", "MEDIUM", '[{"product":"nginx"}]', "2026-08-26T10:00:00.000"),
                ("CVE-2026-M2", "CRITICAL", '[{"product":"openssl"}]', "2026-08-26T11:00:00.000"),
                ("CVE-2026-M3", "LOW", "", "2026-08-26T12:00:00.000"),
                ("CVE-2026-OLD", "HIGH", '[{"product":"nginx"}]', "2026-08-20T10:00:00.000"),
            ):
                await db.execute(
                    """
                    INSERT INTO cves (cve_id, description, affected_products, mitre_technique,
                                      severity, cvss_score, epss_score, is_kev, published, cpe_matches)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cve_id, "demo", "[]", "", sev, 0, 0, 0, pub, cpe),
                )
            await db.commit()
            return await collect_daily_brief(
                db, slot="eod", window_start_utc=start, window_end_utc=end, tz_name="UTC"
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.market["published"] == 3
    labels = [p["label"] for p in brief.market["products"]]
    assert "openssl" in labels
    assert "nginx" in labels
    assert "unanalyzed" in labels
    assert "Quiet window." not in template_headline(brief)
    text = format_daily_brief_text(brief, limit=2000)
    assert "// MARKET" in text
    assert text.index("// MARKET") > text.index("// COUNTS")
    assert "Published: 3" in text
    assert "CVE-2026-OLD" not in text
```

Also assert `brief_to_payload(brief)["market"]["published"] == 3`.

- [ ] **Step 2: Run the new test — expect FAIL** (`DailyBrief` has no `market`)

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 .venv/bin/python -m pytest tests/test_daily_brief.py::test_market_clusters_all_published_not_just_critical -q`

- [ ] **Step 3: Implement** `_fetch_published_market_rows` (columns `cve_id, severity, cpe_matches, affected_products`, no LIMIT), wire `cluster_published`, extend dataclass + `format_daily_brief_text` + `_section_counts` (do not add market to drop order) + `template_headline` + `brief_to_payload`. Update format doc section table (MARKET order 3, shift KEV+). One sentence in API_REFERENCE daily brief paragraph and PRODUCT_STATUS snapshot.

- [ ] **Step 4: Run** `pytest tests/test_daily_brief.py tests/test_market_clusters.py -q` — all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/reports/daily_brief.py backend/tests/test_daily_brief.py docs/design/daily-brief-format.md docs/API_REFERENCE.md docs/PRODUCT_STATUS.md
git commit -m "feat(reports): render MARKET product clusters on daily brief"
```
