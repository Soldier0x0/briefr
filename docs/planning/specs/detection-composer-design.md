# Detection composer (evidence-composed packs)

**Status:** Shipped — DC-1…DC-4 complete  
**Created:** 2026-07-16  
**Goal:** One shared engine for drawer Detect + Forge: retrieve CVE-grounded community/Nuclei/observables first, then compose Sigma/KQL/SPL/QRadar/YARA — **no LLM default**.

## Locked decisions

| Topic | Lock |
|-------|------|
| LLM | Off by default; never required for compose |
| Community rules | Primary when present |
| Keyword templates | Fallback only after evidence pack is empty/thin |
| Surfaces | Shared engine for Detect tab + Forge hunt packs |
| Request path | Compose from DB/cache + existing rule_sources; no new heavy sync |

## PR sequence

| PR | Scope |
|----|--------|
| **DC-1** | `compose_detection_evidence()` — community Sigma/Elastic + detection_context artifacts + nuclei URLs + YARA hashes; additive `evidence` on Detect API |
| **DC-2** | Emit composed Sigma + KQL/SPL/QRadar/YARA from evidence (still no LLM) |
| **DC-3** | Detect tab consumes composer pack / provenance |
| **DC-4** | Forge hunt-pack generate uses same engine; drop keyword-only default when evidence exists |

## DC-1 evidence pack shape

```json
{
  "cve_id": "CVE-…",
  "technique_ids": [],
  "detection_class": "path_traversal|null",
  "community": {
    "sigma_rules": [],
    "elastic_rules": [],
    "has_community_rules": false
  },
  "artifacts": [],
  "observables": {
    "nuclei_urls": [],
    "yara_rules": []
  },
  "detection_context": null,
  "evidence_summary": {
    "community_count": 0,
    "artifact_count": 0,
    "nuclei_count": 0,
    "primary_source": "community|nuclei_artifacts|yara|none"
  }
}
```

## DC-2 emission shape

`emit_composed_detection(evidence, *, description="")` → composed pack:

```json
{
  "generated_sigma": "…yaml…",
  "generated_sigma_meta": {
    "briefr_basis": "cwe|attack_technique|generic",
    "briefr_class": "path_traversal|…",
    "status": "experimental",
    "compose_basis": "community|nuclei_artifacts|yara|template_fallback"
  },
  "siem_queries": { "elastic_kql": {}, "splunk_spl": {}, "sentinel_kql": {}, "qradar_aql": {}, "log_patterns": [], "detection_class": "…" },
  "yara_rules": [],
  "compose_basis": "community|nuclei_artifacts|yara|template_fallback"
}
```

| Rule | Behavior |
|------|----------|
| Evidence artifacts | Inject paths/keywords into Sigma **and** SIEM queries |
| `compose_basis` | From `evidence_summary.primary_source`; `none` → `template_fallback` |
| Community present | Still emit template Sigma as supplement; basis = `community` |
| No LLM | Emission is deterministic templates + evidence fields only |

## Non-goals (this program)

- STIX export
- SIEM push / auto-deploy
- Free-form LLM Sigma YAML on the request path
