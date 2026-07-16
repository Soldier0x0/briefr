# Forge ATT&CK path navigator — design

**Status:** DRAFT (awaiting maintainer review before implementation)  
**Date:** 2026-07-16  
**Type:** Design only — no application code in this document  
**Related:** PM-4d/4e (shipped), `forge-redesign.md` (FR-2 shell), parked detection composer (BACKLOG)

---

## 1. Problem

1. Forge left sidebar + coverage “overview” chrome wastes horizontal space; sub-views should feel like main app tabs (BRIEF / FEED / IOC).
2. ATT&CK navigator cells look like misshapen bricks (variable width/height, chips reshaping layout, `+` to reveal names).
3. Technique → CVE sidebar is a **catalog browser**, not a detection workflow. Hunt packs are per-CVE; the matrix is technique-centric — mismatch.
4. Desired product story: **My Stack → prioritized CVE → Show attack path in ATT&CK → lit path → detect on a technique**, with honest confidence (no fake kill-chains).

---

## 2. Product shape (approved)

### 2.1 Job

| Step | Behavior |
|------|----------|
| Urgency | Stack-prioritized CVEs (affected + KEV/EPSS/severity) |
| CVE | Open drawer / intel already gathered |
| Action | **Show attack path in ATT&CK** |
| Matrix | Highlight evidence-based path for that CVE |
| Technique click | **Detection workbench** (packs / SIEM / proof); CVEs as evidence strip |

### 2.2 Chrome

- Forge sub-views = **horizontal top tabs** (like BRIEF/FEED) — remove left `fg-nav` sidebar.
- Counts / stack toggle / legend = compact strip under tabs.
- Detail / hunt-pack panel only on technique selection (overlay or below) — not a permanent CVE-browser column.

### 2.3 Matrix visual (ATT&CK Navigator–style)

- Fixed **column width** per tactic; equal cell chrome (border, padding, font).
- **Full technique name wraps** onto new lines inside the cell (no truncate-as-default; no `+` expand for identity).
- Optional mono ID line above the name.
- Cell **height grows with wrapped text** (uniform width + structure; not random brick geometry).
- Status = color (gap / community / yours); keep meta chips out of the tile body (tooltip / detail panel).

### 2.4 Path confidence tiers

| Tier | Source | UI | Ship |
|------|--------|----|------|
| 1 Observed | Explicit maps (CTID columns, existing `cve_technique_map`) | Solid highlight + solid links in tactic order | PR-2 |
| 2 Inferred entry | One entry technique from CWE/CAPEC/keywords when score ≥ threshold | Labeled inferred | PR-2 |
| 3 Correlated | Campaigns / Atlas / correlation when linked | Promote when evidence exists | PR-2 |
| 4 Playbook | Curated class→follow-ons | Dashed + **Suggested** | PR-3 only if entry exists |

**Will not:** invent unlabeled multi-step kill-chains; claim ~95% confidence on a full attacker path without evidence.

Sparse state: one mapped technique → highlight it + honest copy; no mapping + failed inference → no fake path.

---

## 3. Implementation scope

### PR-1 — Chrome + matrix visual

- Top tabs; reclaim workspace width.
- Navigator-style wrapped-name tiles; drop identity `+`.
- Selection → detection workbench panel.

### PR-2 — CVE-anchored path (tiers 1–3)

- Drawer/Forge control + URL anchor CVE.
- Prefer CTID exploitation / primary / secondary impact fields for path (already parsed in `feeds/mitre.py`).
- Inferred entry via CWE→CAPEC→ATT&CK bridges when needed.
- Optional weak candidates from CVE2CAPEC (labeled, not observed).

### PR-3 — Soft playbooks (tier 4)

- Curated templates; dashed + Suggested.

### Out of scope

- Paid intel APIs for path quality.
- Detection composer / replacing keyword templates (parked).
- Full multi-select attack-path builder.
- Embedding official ATT&CK Navigator iframe.

---

## 4. Free data sources — endpoint research (verified 2026-07-16)

**None of the recommended path-quality sources require API keys.**  
Probed with HTTP from this environment; statuses below are live as of research date.

### 4.1 Already used by BRIEFR (`backend/feeds/mitre.py`, CIRCL, etc.)

| Resource | URL | Key? | Probe | Notes |
|----------|-----|------|-------|--------|
| ATT&CK Enterprise STIX (current BRIEFR) | `https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json` | No | **200** (~47 MB) | STIX 2.0; repo still maintained |
| ATT&CK Enterprise STIX 2.1 (preferred long-term) | `https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json` | No | **200** (~53 MB) | Canonical QoL improvements; plan migration in a feed PR |
| CTID CVE→ATT&CK CSV | `https://raw.githubusercontent.com/center-for-threat-informed-defense/mappings-explorer/main/src/mapex_convert/mappings/Att%26ckToCveMappings.csv` | No | **200** (~33 KB) | Columns: CVE ID, Primary Impact, Secondary Impact, Exploitation Technique, Uncategorized, Phase — **already wired** |
| CTID KEV→ATT&CK JSON | `https://raw.githubusercontent.com/center-for-threat-informed-defense/mappings-explorer/main/mappings/kev/attack-16.1/kev-07.28.2025/enterprise/kev-07.28.2025_attack-16.1-enterprise.json` | No | **200** (~1.2 MB) | `metadata` + `mapping_objects`; ATT&CK **16.1**, framework date **07/28/2025**, last_update **08/28/2025** — **already wired**; path is **versioned** |
| CIRCL vulnerability API | `https://vulnerability.circl.lu/api/vulnerability/{CVE}` | No | **200** | BRIEFR uses this for CAPEC/refs (`feeds/extended.py`) |

**Stale / avoid**

| URL | Status | Action |
|-----|--------|--------|
| `https://center-for-threat-informed-defense.github.io/mappings-explorer/external/cve/` | **404** | Do not document as download page; use CSV raw URL above |
| Spec path `CVE_mappings.json` on GitHub | Historical 404 (noted in `mitre.py`) | Keep CSV |

**KEV path drift risk:** only `mappings/kev/attack-15.1/` and `attack-16.1/` exist today. When CTID publishes a newer folder, hard-coded `kev-07.28.2025_…` will go stale. **Plan:** discover latest under `mappings/kev/` (list GitHub contents API or git tree) and pin the newest enterprise JSON; fall back to current URL if discovery fails.

### 4.2 Recommended additions (no API key)

| Resource | Stable URL pattern | Key? | Probe | Role in design |
|----------|-------------------|------|-------|----------------|
| CTID Mappings Explorer site | `https://center-for-threat-informed-defense.github.io/mappings-explorer/` | No | **200** | Human docs |
| CTID KEV page | `https://center-for-threat-informed-defense.github.io/mappings-explorer/external/kev/` | No | **200** | Human docs |
| CTID repo | `https://github.com/center-for-threat-informed-defense/mappings-explorer` | No | **200** | Source of truth |
| CWE latest XML zip | `https://cwe.mitre.org/data/xml/cwec_latest.xml.zip` | No | **200** (~2.0 MB) | Tier-2 bridges |
| CAPEC latest XML | `https://capec.mitre.org/data/xml/capec_latest.xml` | No | **200** (~3.8 MB) | Tier-2 bridges |
| CVE2CAPEC yearly DB | `https://raw.githubusercontent.com/Galeax/CVE2CAPEC/main/database/CVE-{YYYY}.jsonl.gz` | No | **200** (e.g. 2024/2025/2026 present) | Weak candidates only; **GPL-3.0** project — use as ingest input, label derived tips; legal review before vendoring large redistributes |
| FKIE NVD year feed | `https://github.com/fkie-cad/nvd-json-data-feeds/releases/latest/download/CVE-{YYYY}.json.xz` | No | **200** | Optional richer text for inference; daily releases |
| SigmaHQ | `https://github.com/SigmaHQ/sigma` (rules under repo) | No | **200** | Community detection quality (workbench) |
| Atomic Red Team index (CSV) | `https://raw.githubusercontent.com/redcanaryco/atomic-red-team/master/atomics/Indexes/Indexes-CSV/index.csv` | No | **200** | Proof / validate hooks |
| Atomic index (YAML) | `https://raw.githubusercontent.com/redcanaryco/atomic-red-team/master/atomics/Indexes/index.yaml` | No | (repo present) | Alternate index |
| Atomic Navigator layer | `https://raw.githubusercontent.com/redcanaryco/atomic-red-team/master/atomics/Indexes/Attack-Navigator-Layers/art-navigator-layer.json` | No | **200** | Optional layer import later |

**Stale / avoid**

| URL | Status | Use instead |
|-----|--------|-------------|
| `…/CVE2CAPEC/main/results/new_cves.jsonl` | **404** | `database/CVE-{YYYY}.jsonl.gz` |
| `…/capec_latest.xml.zip` | **404** | `capec_latest.xml` (unzipped) |
| `…/atomic-red-team/…/Indexes-JSON/index.json` | **404** | `Indexes-CSV/index.csv` or `Indexes/index.yaml` |

### 4.3 Optional / not required for path v1

| Resource | Key? | Notes |
|----------|------|-------|
| NVD API | Optional | Already in BRIEFR; key only raises rate limits |
| OTX | **Yes** | Already optional; not required for ATT&CK path |
| HuggingFace CVE→ATT&CK datasets | Usually no | Eval/training only — never paint as observed path |
| Local open CVE→CWE classifiers | No | Later inferred-entry improvement |

### 4.4 Research conclusion

Endpoints needed for **PR-2 path quality are live and keyless**. Primary path evidence (CTID CSV + KEV JSON + ATT&CK STIX) is **already integrated**; design work is UI + using CTID **impact/exploitation columns** as a visible path, plus CWE/CAPEC bridges. Watch **versioned KEV JSON path** and prefer **attack-stix-data** when touching the MITRE feed next.

---

## 5. Success criteria

- Matrix looks intentional (Navigator-like columns, readable wrapped names).
- From a stack-relevant CVE, analyst sees an evidence-based path and can open detection for a lit technique.
- Suggestions never look like facts (labels + tiers).
- No new paid APIs or keys for path quality.

---

## 6. Open follow-ups (post-approval)

- Implementation plan via writing-plans (only after maintainer approves this spec).
- KEV mapping auto-discovery for new CTID releases.
- Optional STIX 2.1 feed URL switch (`mitre/cti` → `mitre-attack/attack-stix-data`).
- GPL-3.0 implications if shipping CVE2CAPEC-derived artifacts in-repo (prefer runtime fetch + cache).
