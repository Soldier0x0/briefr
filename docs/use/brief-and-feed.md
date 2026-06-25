# BRIEF and FEED

Morning brief, full CVE feed, filters, and heatmap.

---

![BRIEF tab — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/ui-brief-tab.png`](../assets/ui-brief-tab.png)  
> **Miro prompt:** [IMAGE_BRIEFS §11](../IMAGE_BRIEFS.md#11-ui-brief-tab)

![FEED tab — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/ui-feed-tab.png`](../assets/ui-feed-tab.png)  
> **Miro prompt:** [IMAGE_BRIEFS §12](../IMAGE_BRIEFS.md#12-ui-feed-tab)

## BRIEF tab

| Feature | What it does |
|---------|--------------|
| Morning brief | Action queue — KEV, critical, momentum |
| What changed | CVSS/EPSS/KEV deltas (24h–7d) |
| Heatmap | 90-day publication timeline |
| Charts | Analyst KPIs |

## FEED tab

| Feature | What it does |
|---------|--------------|
| CVE list | Paginated, max 50/page |
| Filter bar | KEV, severity, stack, search |
| KEV sidebar | Remediation deadlines |
| Export | CSV / Excel |

## Tips

- Press `/` to focus search, `F` to cycle filters.
- Tab state persists when switching tabs (panels stay mounted).

## Related

- [investigation-and-correlation.md](investigation-and-correlation.md) — detail drawer
- [../concepts/ingest-pipeline.md](../concepts/ingest-pipeline.md) — where data comes from
