# E2E audit results — 2026-07-15 (exhaustive pass)

**Method:** Playwright exhaustive click-map (`scripts/e2e_audit_exhaustive.py`), auth `agentctl`.
**Steps:** 276 total · 257 OK · 8 WARN · 11 SKIP · 0 BUG
**Raw log:** `/opt/cursor/artifacts/e2e-audit-exhaustive-2026-07-15.json`

## Coverage

This pass attempts every item in `e2e-click-map-2026-07-15.md`: global chrome,
all main tabs, FilterBar controls, drawer actions, IOC variants, FORGE views + library,
ARCH sections + graph, admin analyst + operator nav pages with per-page control sweep,
static routes, and mobile tab bar. SKIP = element absent (empty data), not automation skip.

## Bugs / failures

_None recorded._

## Warnings

- **[admin-analyst]** Alert channels: refresh/control: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto
- **[admin-analyst]** Alert channels: refresh/control: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto
- **[admin-operator]** Scheduler: refresh/control: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto
- **[admin-operator]** Scheduler: refresh/control: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto
- **[admin-operator]** Webhooks: refresh/control: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto
- **[admin-operator]** Webhooks: refresh/control: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto
- **[admin-operator]** AI operations: refresh/control: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto
- **[admin-operator]** Audit log: refresh/control: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto

## Skips (element absent)

- **[chrome]** overflow menu: not in DOM
- **[chrome]** My Stack menu: hidden when authed
- **[chrome]** dismiss one notification: no notifications
- **[chrome]** logout: skipped to keep session
- **[drawer]** close: not in DOM
- **[feed-sidebar]** top technique: no techniques
- **[drawer]** related CVE: no related rows
- **[drawer]** close: not in DOM
- **[drawer]** related CVE: no related rows
- **[drawer]** close: not in DOM
- **[arch]** corpus footer: not in DOM

## Full step log

| Status | Area | Action | Detail |
|--------|------|--------|--------|
| OK | auth | load dashboard |  |
| OK | nav | reset home |  |
| OK | chrome | logo home |  |
| OK | nav | tab BRIEF |  |
| OK | nav | reset home |  |
| OK | nav | tab FEED |  |
| OK | nav | reset home |  |
| OK | nav | tab IOC LOOKUP |  |
| OK | nav | reset home |  |
| OK | nav | tab INCIDENTS |  |
| OK | nav | reset home |  |
| OK | nav | tab FORGE |  |
| OK | nav | reset home |  |
| OK | nav | tab ARCH (route) |  |
| SKIP | chrome | overflow menu | not in DOM |
| SKIP | chrome | My Stack menu | hidden when authed |
| OK | nav | reset home |  |
| OK | chrome | timezone |  |
| OK | chrome | notifications |  |
| SKIP | chrome | dismiss one notification | no notifications |
| OK | chrome | account menu |  |
| OK | chrome | menu item Admin panel visible |  |
| OK | chrome | open Preferences |  |
| SKIP | chrome | logout | skipped to keep session |
| OK | chrome | command palette open |  |
| OK | nav | reset home |  |
| OK | nav | tab BRIEF |  |
| OK | brief | filter All |  |
| OK | brief | filter KEV due soon |  |
| OK | brief | filter EPSS movers |  |
| OK | brief | filter New KEV |  |
| OK | brief | filter Stack match |  |
| OK | brief | open full feed |  |
| OK | nav | tab BRIEF |  |
| OK | brief | toggle charts |  |
| OK | brief | toggle charts collapse |  |
| OK | brief | epss row click |  |
| OK | nav | tab BRIEF |  |
| OK | brief | brief row |  |
| OK | drawer | tab OVERVIEW |  |
| OK | drawer | reference link |  |
| OK | drawer | tab INTEL |  |
| OK | drawer | PoC/reference link visible |  |
| OK | drawer | tab DETECT |  |
| OK | drawer | copy detect rule |  |
| OK | drawer | tab RELATED |  |
| OK | drawer | related CVE |  |
| OK | drawer | REPORT menu |  |
| SKIP | drawer | close | not in DOM |
| OK | brief | stats card 3,115
+38
CRITICAL |  |
| OK | nav | tab BRIEF |  |
| OK | brief | stats card 9,725
+478
HIGH |  |
| OK | nav | tab BRIEF |  |
| OK | brief | stats card 1,644
+4
KEV (EXPLOITED) |  |
| OK | nav | tab BRIEF |  |
| OK | brief | stats card 9,945
+64
PATCHES AVAILABLE |  |
| OK | nav | tab BRIEF |  |
| OK | brief | patch filter via stats |  |
| OK | brief | scroll page |  |
| OK | nav | reset home |  |
| OK | nav | tab FEED |  |
| OK | feed | quick filter ALL |  |
| OK | feed | quick filter WATCHLIST |  |
| OK | feed | quick filter KEV |  |
| OK | feed | quick filter CRITICAL |  |
| OK | feed | quick filter HIGH |  |
| OK | feed | quick filter MEDIUM |  |
| OK | feed | quick filter PoC |  |
| OK | feed | quick filter KEV OVERDUE |  |
| OK | feed | search |  |
| OK | feed | stack input |  |
| OK | feed | clear stack |  |
| OK | feed | generate digest |  |
| OK | feed | export csv |  |
| OK | feed | export xlsx |  |
| OK | feed-sidebar | toggle toggle-kev |  |
| OK | feed-sidebar | toggle toggle-poc |  |
| OK | feed-sidebar | toggle toggle-epss |  |
| OK | feed-sidebar | toggle toggle-my-stack |  |
| SKIP | feed-sidebar | top technique | no techniques |
| OK | nav | reset home |  |
| OK | nav | tab FEED |  |
| OK | feed | quick filter KEV |  |
| OK | feed | open cve card |  |
| OK | drawer | tab OVERVIEW |  |
| OK | drawer | reference link |  |
| OK | drawer | tab INTEL |  |
| OK | drawer | PoC/reference link visible |  |
| OK | drawer | technique pill |  |
| OK | drawer | tab DETECT |  |
| OK | drawer | copy detect rule |  |
| OK | drawer | tab RELATED |  |
| SKIP | drawer | related CVE | no related rows |
| OK | drawer | REPORT menu |  |
| SKIP | drawer | close | not in DOM |
| OK | nav | reset home |  |
| OK | nav | tab FEED |  |
| OK | feed | open cve card |  |
| OK | drawer | tab OVERVIEW |  |
| OK | drawer | reference link |  |
| OK | drawer | tab INTEL |  |
| OK | drawer | tab DETECT |  |
| OK | drawer | copy detect rule |  |
| OK | drawer | tab RELATED |  |
| SKIP | drawer | related CVE | no related rows |
| OK | drawer | REPORT menu |  |
| SKIP | drawer | close | not in DOM |
| OK | feed | scroll feed |  |
| OK | nav | reset home |  |
| OK | nav | tab IOC LOOKUP |  |
| OK | ioc | lookup ip |  |
| OK | ioc | lookup ip-alt |  |
| OK | ioc | lookup domain |  |
| OK | ioc | lookup invalid |  |
| OK | ioc | scroll |  |
| OK | nav | reset home |  |
| OK | nav | tab INCIDENTS |  |
| OK | incidents | cards 211 |  |
| OK | incidents | open case |  |
| OK | nav | reset home |  |
| OK | nav | tab FORGE |  |
| OK | forge | view Coverage map |  |
| OK | forge | view Threat scenarios |  |
| OK | forge | view Campaigns |  |
| OK | forge | view Backlog |  |
| OK | forge | view Library |  |
| OK | forge | scenarios tab |  |
| OK | forge | backlog tab |  |
| OK | forge | coverage tab |  |
| OK | forge | coverage technique |  |
| OK | forge | hunt pack rail open |  |
| OK | forge | library tab |  |
| OK | arch | section Overview |  |
| OK | arch | export pdf in Overview |  |
| OK | arch | section Components |  |
| OK | arch | section System Architecture |  |
| OK | arch | section Trust Boundaries |  |
| OK | arch | section Attack Surface |  |
| OK | arch | section Mitre Attack |  |
| OK | arch | section Controls |  |
| OK | arch | section Abuse Cases |  |
| OK | arch | section Threat Scenarios |  |
| OK | arch | export pdf in Threat Scenarios |  |
| OK | arch | section Security Decisions |  |
| OK | arch | section Risks |  |
| OK | arch | export pdf in Risks |  |
| OK | arch | section Reviews |  |
| OK | arch | context rail visible |  |
| SKIP | arch | corpus footer | not in DOM |
| OK | admin | route loaded |  |
| OK | admin-analyst | page Intel status |  |
| OK | admin-analyst | Intel status: refresh/control Refresh all sources |  |
| OK | admin-analyst | Intel status: expand details STATUS LEGEND |  |
| OK | admin-analyst | Intel status: status legend STATUS LEGEND |  |
| OK | admin-analyst | page Source status |  |
| OK | admin-analyst | Source status: refresh/control Refresh all sources |  |
| OK | admin-analyst | Source status: expand details STATUS LEGEND |  |
| OK | admin-analyst | Source status: status legend STATUS LEGEND |  |
| OK | admin-analyst | page Alert channels |  |
| OK | admin-analyst | Alert channels: refresh/control Refresh all sources |  |
| WARN | admin-analyst | Alert channels: refresh/control | Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto |
| WARN | admin-analyst | Alert channels: refresh/control | Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto |
| OK | admin-analyst | Alert channels: expand details STATUS LEGEND |  |
| OK | admin-analyst | Alert channels: status legend STATUS LEGEND |  |
| OK | admin-analyst | page Pinned CVEs |  |
| OK | admin-analyst | Pinned CVEs: refresh/control Refresh all sources |  |
| OK | admin-analyst | Pinned CVEs: expand details STATUS LEGEND |  |
| OK | admin-analyst | Pinned CVEs: status legend STATUS LEGEND |  |
| OK | admin-analyst | page Display |  |
| OK | admin-analyst | Display: refresh/control Refresh all sources |  |
| OK | admin-analyst | Display: refresh/control Apply |  |
| OK | admin-analyst | Display: refresh/control Save as instance default |  |
| OK | admin-analyst | Display: refresh/control Reset draft |  |
| OK | admin-analyst | Display: refresh/control Reset to defaults |  |
| OK | admin-analyst | Display: expand details STATUS LEGEND |  |
| OK | admin-analyst | Display: status legend STATUS LEGEND |  |
| OK | admin | operator mode via reload |  |
| OK | admin-operator | page System health |  |
| OK | admin-operator | System health: expand details STATUS LEGEND |  |
| OK | admin-operator | System health: status legend STATUS LEGEND |  |
| OK | admin-operator | page Backups |  |
| OK | admin-operator | Backups: refresh/control Edit schedule & retention |  |
| OK | admin-operator | Backups: refresh/control Upload archive |  |
| OK | admin-operator | Backups: expand details STATUS LEGEND |  |
| OK | admin-operator | Backups: status legend STATUS LEGEND |  |
| OK | admin-operator | page Storage |  |
| OK | admin-operator | Storage: refresh/control Columns (3/3) |  |
| OK | admin-operator | Storage: expand details STATUS LEGEND |  |
| OK | admin-operator | Storage: status legend STATUS LEGEND |  |
| OK | admin-operator | page Resources |  |
| OK | admin-operator | Resources: expand details STATUS LEGEND |  |
| OK | admin-operator | Resources: expand details View chart data as table |  |
| OK | admin-operator | Resources: expand details View chart data as table |  |
| OK | admin-operator | Resources: expand details View chart data as table |  |
| OK | admin-operator | Resources: expand details View chart data as table |  |
| OK | admin-operator | Resources: expand details View chart data as table |  |
| OK | admin-operator | Resources: status legend STATUS LEGEND |  |
| OK | admin-operator | page Database |  |
| OK | admin-operator | Database: refresh/control Got it |  |
| OK | admin-operator | Database: expand details STATUS LEGEND |  |
| OK | admin-operator | Database: status legend STATUS LEGEND |  |
| OK | admin-operator | page Watchlist & cache |  |
| OK | admin-operator | Watchlist & cache: expand details STATUS LEGEND |  |
| OK | admin-operator | Watchlist & cache: status legend STATUS LEGEND |  |
| OK | admin-operator | page API keys & config |  |
| OK | admin-operator | API keys & config: refresh/control Refresh |  |
| OK | admin-operator | API keys & config: refresh/control Columns (7/7) |  |
| OK | admin-operator | API keys & config: refresh/control Edit |  |
| OK | admin-operator | API keys & config: refresh/control Edit |  |
| OK | admin-operator | API keys & config: refresh/control Edit |  |
| OK | admin-operator | API keys & config: refresh/control Edit |  |
| OK | admin-operator | API keys & config: expand details STATUS LEGEND |  |
| OK | admin-operator | API keys & config: status legend STATUS LEGEND |  |
| OK | admin-operator | page Scheduler |  |
| WARN | admin-operator | Scheduler: refresh/control | Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto |
| OK | admin-operator | Scheduler: refresh/control KEV only |  |
| OK | admin-operator | Scheduler: refresh/control EPSS only |  |
| WARN | admin-operator | Scheduler: refresh/control | Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto |
| OK | admin-operator | Scheduler: refresh/control Incident RSS |  |
| OK | admin-operator | Scheduler: refresh/control Correlation |  |
| OK | admin-operator | Scheduler: expand details STATUS LEGEND |  |
| OK | admin-operator | Scheduler: status legend STATUS LEGEND |  |
| OK | admin-operator | page Webhooks |  |
| OK | admin-operator | Webhooks: refresh/control Refresh |  |
| OK | admin-operator | Webhooks: refresh/control Test send |  |
| OK | admin-operator | Webhooks: refresh/control Events |  |
| OK | admin-operator | Webhooks: refresh/control Refresh |  |
| WARN | admin-operator | Webhooks: refresh/control | Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto |
| WARN | admin-operator | Webhooks: refresh/control | Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto |
| OK | admin-operator | Webhooks: expand details STATUS LEGEND |  |
| OK | admin-operator | Webhooks: status legend STATUS LEGEND |  |
| OK | admin-operator | page AI operations |  |
| OK | admin-operator | AI operations: refresh/control Providers |  |
| OK | admin-operator | AI operations: refresh/control Models |  |
| OK | admin-operator | AI operations: refresh/control Usage |  |
| OK | admin-operator | AI operations: refresh/control Activity |  |
| WARN | admin-operator | AI operations: refresh/control | Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto |
| OK | admin-operator | AI operations: expand details STATUS LEGEND |  |
| OK | admin-operator | AI operations: status legend STATUS LEGEND |  |
| OK | admin-operator | page Security |  |
| OK | admin-operator | Security: expand details STATUS LEGEND |  |
| OK | admin-operator | Security: status legend STATUS LEGEND |  |
| OK | admin-operator | page Inbound limits |  |
| OK | admin-operator | Inbound limits: expand details STATUS LEGEND |  |
| OK | admin-operator | Inbound limits: status legend STATUS LEGEND |  |
| OK | admin-operator | page Feed health |  |
| OK | admin-operator | Feed health: expand details STATUS LEGEND |  |
| OK | admin-operator | Feed health: status legend STATUS LEGEND |  |
| OK | admin-operator | page Application logs |  |
| OK | admin-operator | Application logs: refresh/control Refresh |  |
| OK | admin-operator | Application logs: refresh/control Export logs |  |
| OK | admin-operator | Application logs: expand details STATUS LEGEND |  |
| OK | admin-operator | Application logs: status legend STATUS LEGEND |  |
| OK | admin-operator | page Audit log |  |
| WARN | admin-operator | Audit log: refresh/control | Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("butto |
| OK | admin-operator | Audit log: refresh/control Load more → |  |
| OK | admin-operator | Audit log: expand details STATUS LEGEND |  |
| OK | admin-operator | Audit log: status legend STATUS LEGEND |  |
| OK | admin-operator | page Display |  |
| OK | admin-operator | Display: refresh/control Apply |  |
| OK | admin-operator | Display: refresh/control Save as instance default |  |
| OK | admin-operator | Display: refresh/control Reset draft |  |
| OK | admin-operator | Display: refresh/control Reset to defaults |  |
| OK | admin-operator | Display: expand details STATUS LEGEND |  |
| OK | admin-operator | Display: status legend STATUS LEGEND |  |
| OK | admin | analyst mode via reload |  |
| OK | admin | breadcrumbs |  |
| OK | static | /wallboard |  |
| OK | static | /login |  |
| OK | static | /privacy |  |
| OK | static | /terms |  |
| OK | mobile | tab bar visible |  |
| OK | mobile | tab BRIEF |  |
| OK | mobile | tab FEED |  |
| OK | mobile | tab IOC LOOKUP |  |
| OK | mobile | tab INCIDENTS & NEWS |  |
