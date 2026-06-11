# BRIEFR Beta V1.3 — Analyst Beast

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Document version:** 1.0  
**Last updated:** 2026-06-10  
**Status:** Planning — **starts after Beta V1.2 success criteria are met**

**Prerequisite:** [`Beta V1.2.md`](Beta%20V1.2.md) (foundation)  
**Index:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## Purpose

V1.3 makes BRIEFR the **best self-hosted analyst intelligence pane** — actionable intel, visual briefings, and detection engineering (Forge MVP). This is the first **product differentiation** release after structural hardening.

**Not in V1.3:** full admin pane, webhooks UI, wallboard, Docker official, Postgres.

---

## Theme 1 — Action queue & morning brief

| Item | Goal |
|------|------|
| **Morning brief view** | Single screen: new/changed for *my stack* since last visit |
| **Action queue** | Ranked worklist (KEV on stack, EPSS jumps, material CVSS changes) |
| **Explainable risk** | Score breakdown UI (KEV + EPSS + stack match + momentum components) |
| **Change intelligence** | Surface `cve_change_history` deltas filtered by asset profile (`GET /api/changes` UI — data already collected) |
| **KEV due-date countdown** | "Due in N days" chip on cards + sorted deadline list (`kev_deadlines` already populated) |
| **Pin / snooze / watchlist** | Analyst controls on CVE rows (stored in DB; single-user default now, keyed by app-login user once built-in auth ships — decision 2026-06-11) |

**API sketch:**

- `GET /api/brief` — aggregated queue + meta (`generated_at`, `stack_profile_id`)
- Extend `/api/stats` with brief-friendly aggregates where needed

---

## Theme 2 — Visual intelligence (Chart.js)

| Item | Goal |
|------|------|
| **Chart.js dependency** | Dashboard-grade charts; keep SVG sparklines on CVE cards |
| **Analyst Brief dashboard** | 4–6 charts: EPSS movers, KEV-on-stack, new/changed per day, stack exposure |
| **Live = polled** | 60s–5m refresh via React Query; no WebSocket requirement |
| **Chart export in PDF** | Optional Phase 2 within V1.3 |

**Do not:** chart every CVE card; avoid bundle bloat.

---

## Theme 3 — BRIEFR Forge (MVP)

Detection engineering inside the intel pane — **not** log execution.

| Item | Goal |
|------|------|
| **MITRE coverage map** | Stack profile × techniques × rule status (community / yours / gap) |
| **CVE → detection pack** | Sigma + SIEM snippets + optional ClickHouse SQL + ATT&CK + priority |
| **Detection cards** | Markdown docs per pack: hypothesis, logsource, FP notes, test method |
| **Hunt pack API** | `GET /api/hunt-packs/{technique_id}` |
| **Extend Detect tab** | “Generate pack” + link to coverage gap |

Build on existing: `backend/detection/` (`sigma_generator`, `siem_queries`, `rule_sources`).

**Out of scope for Forge MVP:** rule proof on live logs (V1.5), HyperDX API provisioning (V1.4/V1.5).

---

## Theme 4 — Incidents & News performance (carry-over)

If not fully completed in V1.2, finish here:

| Item | Goal |
|------|------|
| **Scheduler: `refresh_incident_feed`** | Every 15–30 min |
| **Combined snapshot** | `feed_cache` or `incident_feed_snapshot` table |
| **Parallel RSS fetch** | `asyncio.gather` inside job only — not on every API request |
| **API** | `GET /api/case-studies/feed` reads snapshot + `meta.stale`, `meta.refreshed_at` |
| **Frontend** | Stale-while-revalidate; show cached data immediately |

**Target:** tab open **<500ms** API; cold start after boot ≤ one scheduler cycle.

---

## Theme 5 — Frontend polish

| Item | Goal |
|------|------|
| **React Query** | Complete rollout from V1.2 start — brief, feed, drawer |
| **Incidents hook** | `useCaseStudyFeed` with persistent cache |
| **Investigation pivots** | Incidents ATLAS cards → CVE drawer |
| **Operator changes UI** | Surface `GET /api/changes` if not done in V1.2 |

---

## Theme 6 — Data depth (amendment 2026-06-10)

New free intel sources feeding stack matching and the exploit score component:

| Source | Feeds | Pattern |
|--------|-------|---------|
| **CISA Vulnrichment** (`cisagov/vulnrichment`) | SSVC / CVSS / CWE / CPE for CVEs NVD has not analyzed yet | Repo pull; superseded by NVD data when it arrives |
| **cvelistV5** (`CVEProject/cvelistV5`) | CVE records hours before NVD, ADP containers | Repo pull deltas |
| **PoC-in-GitHub** (`nomi-sec/PoC-in-GitHub`) | CVE → public PoC index (~daily) | Repo pull; exploit + momentum signal |
| **ExploitDB CSV** | Public exploits with CVE mapping | Full-snapshot upsert |
| **Metasploit module metadata** | "Weaponized in MSF" flag | Full-snapshot upsert |
| **Nuclei templates index** | CVE → template existence | Full-snapshot upsert; ties into Forge |

All ride the V1.2 `resilient_client` feed framework; snapshot sources need no watermark.

---

## Theme 7 — ML assist (amendment 2026-06-10)

Env-gated, CPU-only, scheduler-side, deterministic fallback — see ML placement rules in [`docs/ROADMAP.md`](docs/ROADMAP.md).

| Item | Goal |
|------|------|
| **Embeddings at ingest** | Small local model (e.g. bge-small via ONNX/fastembed); vectors stored as BLOBs in SQLite. **Default search: exact brute-force cosine (NumPy)** — adequate at BRIEFR scale (tens of thousands of embedded rows) and keeps the single-tool deploy contract. `sqlite-vec` is an optional accelerator only where its loadable extension is available (Python build must support `enable_load_extension`; document the Debian toolchain if adopted) |
| **Similar CVEs** | Semantic relatedness beyond same-product matching |
| **News ↔ CVE linking + RSS dedup** | Cluster multi-source coverage of one incident into one card |
| **Semantic search** | Across CVE descriptions, ATLAS studies, news |
| **LLM product extraction** | `{vendor, product, version_range}` from description text for NVD-unanalyzed CVEs (existing Groq/Anthropic integration); superseded by official CPE |
| **Action logging** | Pin/snooze/dismiss events retained as future re-ranker training data — no model training in V1.3 |

---

## Theme 8 — Push notifications (pulled forward from V1.4)

| Item | Goal |
|------|------|
| **One webhook channel** | Telegram or Discord, env-configured (no admin UI yet) |
| **KEV-on-stack rule** | Alert when a KEV entry matches the asset profile |
| **Backup dead-man ping** | `briefr-backup.sh` pings healthchecks-style URL on success; silence = alert |

The full webhook engine (channels UI, rules, delivery log, SSRF protection) stays in [`Beta V1.4.md`](Beta%20V1.4.md).

---

## Explicit non-goals for V1.3

| Non-goal | Reason |
|----------|--------|
| Admin backup/restore UI | V1.4 |
| Webhook channel configuration | V1.4 |
| Wallboard | V1.4 |
| Environment threat model UI | V1.5 |
| Rule proof bench | V1.5 |
| ClickStack in-repo | Jupiter sidecar doc only |
| Multi-user team management | V2.0 |

---

## Implementation order

```
Phase 1  Incident feed snapshot + scheduler (if not in V1.2)
Phase 2  Morning brief API + explainable risk UI
Phase 3  Chart.js Analyst Brief panel
Phase 4  Forge: coverage map + hunt-packs API
Phase 5  CVE → detection pack generation + detection cards (docs/)
Phase 6  Watchlist / pin / snooze + React Query cleanup
```

---

## Success criteria

| Criterion | Measure |
|-----------|---------|
| Incidents tab | p95 load <1s with warm snapshot |
| Morning brief | Shows stack-filtered queue in one screen |
| Forge | Coverage map shows ≥1 real gap for demo stack |
| Detection packs | 3 authored end-to-end packs with ATT&CK IDs |
| Charts | Brief dashboard renders without layout break on 1080p |
| No regression | V1.2 auth, tests, deploy scripts still pass |

---

## Related documents

| Document | Role |
|----------|------|
| [`Beta V1.2.md`](Beta%20V1.2.md) | Prerequisite |
| [`Beta V1.4.md`](Beta%20V1.4.md) | Next — operator features |
| [`docs/JUPITER_VISION.md`](docs/JUPITER_VISION.md) | Ecosystem context |
