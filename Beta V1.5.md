# BRIEFR Beta V1.5 — Detection & Threat Depth

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Document version:** 1.0  
**Last updated:** 2026-06-10  
**Status:** Planning — **after Beta V1.4**

**Prerequisite:** [`Beta V1.4.md`](Beta%20V1.4.md)  
**Index:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## Purpose

V1.5 closes the **intel → detect → validate** loop: **environment threat modeling**, **rule proof bench**, and **KEV-driven detection backlog**. Still honest TI / detection-content scope — not log SIEM.

Optional integration with **ClickStack** (HyperDX API) for provisioning dashboards — not required for core criteria.

---

## Theme 1 — Environment threat model (product UI)

| Item | Goal |
|------|------|
| **Stack threat profile** | Asset profile → relevant ATT&CK / ATLAS techniques |
| **Scenario cards** | Plain-language threat scenarios per technique |
| **CVE as evidence** | Map techniques to open CVEs on stack |
| **Coverage integration** | Forge gaps highlighted in threat view |
| **Mitigation queue** | Patch / hunt pack / accept risk |
| **STRIDE-lite worksheet** | Optional per-asset scores (stored in DB) |

**Not:** full IriusRisk / enterprise GRC data-flow modeling.

---

## Theme 2 — Rule proof bench

| Item | Goal |
|------|------|
| **Proof API** | Run rule against sample log lines or uploaded file |
| **Hit/miss report** | Count, sample events, FP pattern hints |
| **Pack integration** | Proof from Forge-generated Sigma/SQL |
| **Optional ClickHouse** | Point at local CH for last 7d (Jupiter sidecar) |

**Portfolio:** 5 tuned detection cards in `docs/detections/` with proof evidence.

---

## Theme 3 — KEV delta → detection backlog

| Item | Goal |
|------|------|
| **Weekly backlog job** | New KEV entries affecting stack |
| **Gap detection** | No rule for technique X on nginx |
| **Admin + analyst UI** | Backlog list with priority |
| **Webhook hook** | Optional notify from V1.4 engine |

---

## Theme 4 — Forge v2

| Item | Goal |
|------|------|
| **HyperDX provisioning script** | Optional `scripts/provision_hyperdx.py` via API v2 |
| **Enriched alerts API** | `GET /api/alerts/enriched` — stub until CH worker exists |
| **Export formats** | Sigma pack zip, STIX-lite JSON |

---

## Theme 5 — Priority ranker (explainable)

Transparent function (not black-box ML):

```text
priority = f(KEV, EPSS, asset_match, coverage_gap, public_exploit_signals)
```

Optional: learn weights from analyst dismiss/promote actions later.

---

## Explicit non-goals for V1.5

| Non-goal | Reason |
|----------|--------|
| Streaming ML on logs in BRIEFR core | jupiter-detection worker |
| SIEM case management | Investigation thread sufficient |
| Fork HyperDX | API integration only |

---

## Implementation order

```
Phase 1  Threat model UI (stack → techniques → CVEs)
Phase 2  Rule proof bench (file-based)
Phase 3  KEV delta backlog job + UI
Phase 4  Forge export + detection card templates
Phase 5  Optional HyperDX provisioner + CH proof path
```

---

## Success criteria

| Criterion | Measure |
|-----------|---------|
| Threat model | Demo stack shows techniques + gaps + linked CVEs |
| Proof bench | T1190 nginx rule shows hits on sample traversal lines |
| Backlog | KEV update creates ≥1 actionable backlog item |
| Interview | 5 detection cards with ATT&CK + tuning notes |

---

## Related documents

| Document | Role |
|----------|------|
| [`docs/JUPITER_VISION.md`](docs/JUPITER_VISION.md) | ML / ClickStack split |
| [`Beta V2.0.md`](Beta%20V2.0.md) | Platform packaging |
