# Using BRIEFR

For analysts, security enthusiasts, and anyone using the UI — not deploying it.

Screenshots are not committed yet. Use [`IMAGE_BRIEFS.md`](IMAGE_BRIEFS.md) for capture prompts.

---

## Main shell

| URL tab | Header label | What you get |
|---------|--------------|--------------|
| `brief` | **BRIEF** | Morning queue, OP/Threat-ranked cards, charts, heatmap, what changed |
| `feed` | **FEED** | Full CVE list, filters, KEV deadlines, export, hybrid search |
| `ioc` | **IOC LOOKUP** | IP / hash / domain enrichment and investigation pivots |
| `atlas` | **INCIDENTS & NEWS** | RSS × 5 security news + MITRE ATLAS narratives |
| `forge` | **FORGE** | ATT&CK navigator, hunt packs, scenarios, campaigns, backlog, library |

Tab changes push browser history; hygiene cleanup replaces it. Back restores the last tab or Forge context. Opening a CVE writes `?cve=CVE-...`, so Back closes the drawer before leaving the page.

---

## FEED

Search is hybrid when a query is present: keyword/CVE hits plus semantic results. It can show **TECHNIQUES**, **CAMPAIGNS**, then **CVES** in one result set.

The stack filter is server-side. If BRIEFR needs historical coverage, FEED shows a backfill banner; approve it, watch progress, and resume if a run is deferred or partial.

Exports: CSV, Excel, selected-CVE PDF, and markdown copy.

---

## CVE detail drawer

Click any CVE. The drawer stays mounted while you switch drawer tabs.

| Tab | Order / purpose |
|-----|-----------------|
| **OVERVIEW** | Description → Operational Priority + Environment Relevance → Why this matters → CVSS/EPSS/exploitation → affected products → patch/references → SSVC/OSV |
| **INTEL** | Exploits, KEV, ATT&CK/ATLAS, GreyNoise, OTX pulses, active campaigns, explainable correlation |
| **DETECT** | Sigma, Elastic, SIEM queries, YARA, generated fallbacks |
| **RELATED** | Related CVEs and related news |

OTX pulse names are normalized with `formatIntelLabel`, so cluster labels stay readable. Pulse clustering is explainable: campaigns, shared infrastructure, actor/sector, and temporal lanes show why items are connected.

**Investigation:** pivot CVE → IOC → ATLAS/Forge/related CVE. The thread is session-only in the browser.

---

## IOC lookup

Sources depend on keys: VirusTotal, AbuseIPDB, GreyNoise, OTX, abuse.ch. Results cache about 6 hours; GreyNoise is opt-in per lookup.

---

## Forge

Views: **ATT&CK navigator**, **Threat scenarios**, **Campaigns**, **Backlog**, **Library**.

The ATT&CK navigator is the primary workspace for CVE inventory and hunt-pack generation. Library packs can deep-link back into navigator context.

---

## Admin & wallboard

Operators use `/admin`: Scheduler includes **Catch-up mode** and the durable outbound jobs panel; Security posture lives inside Admin.

`/wallboard` is a read-only kiosk surface. It uses `WALLBOARD_TOKEN`, rotates OP/Threat-ranked CVEs, KEV-on-stack, campaign, source-health, and coverage-gap tiles.

---

## Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus FEED search |
| `F` | Cycle FEED filters |
| `g` then `d` | Generate digest from visible FEED cards |
| `↑` / `↓` | Move through FEED cards |
| `Enter` | Open highlighted CVE |
| `Esc` | Close the topmost drawer/modal |
| `C` | Copy CVE markdown (drawer open) |

Deploying? Read [SELF_HOST.md](SELF_HOST.md).
