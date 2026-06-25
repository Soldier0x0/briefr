# Correlation engine

Explainable CVE linking — campaigns, shared IOCs, actor/sector, temporal spikes.

---

![Correlation pipeline — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/correlation-pipeline.png`](../assets/correlation-pipeline.png)  
> **Miro prompt:** [IMAGE_BRIEFS §5](../IMAGE_BRIEFS.md#5-correlation-pipeline)

## At a glance

| Question | Answer |
|----------|--------|
| What it does | Surfaces why CVEs appear related (with receipts) |
| Request path | **No live OTX/NVD** on drawer open — reads DB |
| OTX | Spine for campaigns; optional (`OTX_API_KEY`) |

## Four lanes

| Lane | Signal |
|------|--------|
| **Campaigns** | Pulse-seeded clusters + strong shared IOCs |
| **Infrastructure** | Weaker shared-IOC peers |
| **Actor / sector** | ATT&CK groups vs your sector keywords |
| **Temporal** | Vendor CVE volume 7d vs 90d baseline |

## Before → after

| v1 problem | Fix |
|------------|-----|
| L1/L2 recomputed every API hit | DB-backed campaigns (#222) |
| IOC pivot ≠ correlation engine | Unified graph tables |
| `otx_pulse_iocs_pkey` races | Upsert + per-pulse locks (#225) |
| max 100 pulse prefetch | Configurable + continuous OTX job |

## Errors & remediation

| Symptom | Cause | Fix |
|---------|-------|-----|
| Empty Intel tab | No OTX key / no nightly run | Set key; check admin job status |
| Duplicate key warnings | Concurrent prefetch | Merged #225 — upsert path |
| Stale clusters | Job failed | Check scheduler logs; manual refresh |

## Limits

| Limit | Why |
|-------|-----|
| OTX monthly quota | Nightly batch, not per-CVE |
| `OTX_IOC_SYNC_MAX_PER_RUN` | Runtime + quota cap |
| 6h cache | Balance freshness vs load |

## Code map

| Area | Path |
|------|------|
| Engine | `backend/correlation/engine.py` |
| Campaigns | `backend/correlation/campaigns.py` |
| OTX feeds | `backend/feeds/otx.py` |
| UI | `frontend/src/components/DetailDrawer.jsx` |

## Planned

Phases 3–5: [`CORRELATION_V2_PLAN.md`](../CORRELATION_V2_PLAN.md)
