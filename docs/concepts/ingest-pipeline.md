# Ingest pipeline

How CVE and threat data enters PostgreSQL — schedulers, watermarks, resilience.

---

![Ingest pipeline — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/ingest-pipeline.png`](../assets/ingest-pipeline.png)  
> **Miro prompt:** [IMAGE_BRIEFS §6](../IMAGE_BRIEFS.md#6-ingest-pipeline)

![NVD sync detail — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/nvd-sync-detail.png`](../assets/nvd-sync-detail.png)  
> **Miro prompt:** [IMAGE_BRIEFS §7](../IMAGE_BRIEFS.md#7-nvd-sync-detail)

## Scheduler jobs (summary)

| Job | Default cadence | Writes |
|-----|-----------------|--------|
| NVD incremental | 1h | `cves`, `sync_state` |
| KEV | 15m | `cves`, `kev_deadlines` |
| EPSS | 6h | `cves`, `epss_history` |
| cvelistV5 | 30m | `cves` |
| Vulnrichment | 6h | `cves` gap-fill |
| OTX | nightly | `otx_*` |
| Correlation | nightly | `correlation_*` |
| MITRE+ATLAS | weekly Sun | `mitre_*`, `atlas_*` |
| Incident feed | 30m | RSS snapshot cache |
| Exploit sources | opt-in | `cve_exploits` |
| Embeddings | opt-in | semantic related CVEs |

## Decision log

| Decision | Why |
|----------|-----|
| Watermarks in `sync_state` | Idempotent retries after NVD 503 |
| `MAX_CVES_PER_FETCH` cap | Bound single-run duration |
| API queue (#221) | Serialize outbound calls |
| Bootstrap if &lt;10 CVEs | First-run UX |

## Errors & remediation

| Symptom | Cause | Fix |
|---------|-------|-----|
| Empty feed | Bootstrap running / NVD down | Wait; check `/api/health` |
| NVD 503 storms | NIST transient | Circuit breaker; retry later |
| Stale EPSS | Job skipped | `POST /api/refresh/epss` |

## Code map

`backend/scheduler.py`, `backend/feeds/`, `backend/database.py`
