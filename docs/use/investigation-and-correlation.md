# Investigation and correlation

CVE detail drawer, correlation Intel tab, and cross-tab pivots.

---

![Detail drawer — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/ui-detail-drawer.png`](../assets/ui-detail-drawer.png)  
> **Miro prompt:** [IMAGE_BRIEFS §13](../IMAGE_BRIEFS.md#13-ui-detail-drawer)

![Investigation pivots — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/investigation-pivot-flow.png`](../assets/investigation-pivot-flow.png)  
> **Miro prompt:** [IMAGE_BRIEFS §17](../IMAGE_BRIEFS.md#17-investigation-pivot-flow)

## Detail drawer

Opens from FEED or BRIEF. Tabs include Intel (correlation), Related, Detect, etc. Sub-requests load in parallel.

## Correlation (Intel tab)

Explainable findings with confidence labels — see [correlation.md](../concepts/correlation.md).

## Investigation thread

Session-only in browser — pivots CVE → IOC → related CVE. Not persisted server-side.

## Keyboard

`C` — copy CVE markdown when drawer open. `Esc` — close.
