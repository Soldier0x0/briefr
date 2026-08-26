# Daily brief — channel format standard

**Status:** Draft for implementation (pairs with `docs/superpowers/specs/2026-08-26-daily-brief-webhook-design.md`).  
**Analogy:** CVE PDF reports (`frontend/src/utils/pdfReport.js` + `pdfReportSections.js`) are a **section grammar** plus overflow rules. Daily briefs are the same idea for Discord / Telegram / generic HTTPS — not a second PDF.

When this file and a webhook payload disagree, **this file wins** for layout. When this file and `PRODUCT_STATUS.md` disagree after ship, **PRODUCT_STATUS wins**.

---

## 1. Why a standard

Webhook channels are not the BRIEFR UI. Discord caps **2000** characters (`DISCORD_MAX_CONTENT`). Telegram caps **4096** (`TELEGRAM_MAX_TEXT`). Generic HTTPS gets the same body as Discord plus `event_type`. Without a grammar, each destination will drift into a dump of CVE IDs.

The brief must be **scannable in 10 seconds**: headline, counts, then ranked lists, then a footer that says how the facts were built.

## 2. Canonical sections (order is fixed)

Render only sections that have rows, except **HEADLINE** and **COUNTS**, which always render. Quiet windows still send COUNTS of zeros plus HEADLINE `Quiet window.` so a missing ping means the job failed, not “nothing happened.”

| Order | Section id | Title line | Body |
|-------|------------|------------|------|
| 0 | `masthead` | `BRIEFR {SLOT}` | One line: window start → end, IANA tz |
| 1 | `headline` | `// HEADLINE` | 1–3 short sentences. Template or optional LLM (see spec). Never invent CVEs. |
| 2 | `counts` | `// COUNTS` | Fixed keys, one per line, integer values |
| 3 | `kev` | `// KEV` | New KEV in window (max 8 lines) |
| 4 | `stack` | `// STACK` | KEV or Critical/High matching admin My Stack CPE (max 8) |
| 5 | `watchlist` | `// WATCHLIST` | Pinned-CVE monitor reasons in window (max 8) |
| 6 | `ioc` | `// IOC` | IOC watchlist hits in window (max 5) |
| 7 | `ops` | `// OPS` | Job errors, unhealthy API keys, webhook delivery failures (max 5) |
| 8 | `footer` | (no `//` title) | Generator line |

Section titles use the PDF convention: **`// TITLE` in ASCII**, not emoji, not Markdown headings. Discord markdown (`**bold**`) is allowed only on the masthead first line.

### COUNTS keys (always all six, in this order)

```
KEV new: {n}
Stack matches: {n}
Watchlist: {n}
IOC hits: {n}
Critical/High new: {n}
Ops issues: {n}
```

`n` is the **untruncated** total for the window, even when the list below is capped.

### List line grammar

```
• {CVE-YYYY-N} — {one-line reason} · {severity-or-blank}
```

IOC lines:

```
• {type} {value} — {source}
```

Ops lines:

```
• {job_id or destination_id} — {short error}
```

No nested bullets. No tables. No JSON inside Discord/Telegram text.

## 3. Overflow (same job as PDF page breaks)

When the assembled body exceeds the destination cap:

1. Drop lowest-priority list sections first: `ops` → `ioc` → `watchlist` → `stack` → `kev`. Never drop `masthead`, `headline`, `counts`, `footer`.
2. If still over, shorten HEADLINE to its first sentence.
3. If still over, replace remaining list bodies with `+{hidden} more in BRIEFR.`
4. Last resort: truncate with a Unicode ellipsis `…` (existing `_truncate` in `webhooks/engine.py`).

The `text` field is capped at Discord's **2000-character** limit for every destination kind, including Generic HTTPS. Machine consumers should read the structured `brief` object for the bounded item lists and untruncated window totals.

## 4. Worked examples

### Quiet standup

```
BRIEFR STANDUP
2026-08-25 18:00 → 2026-08-26 07:00 (Asia/Kolkata)

// HEADLINE
Quiet window.

// COUNTS
KEV new: 0
Stack matches: 0
Watchlist: 0
IOC hits: 0
Critical/High new: 0
Ops issues: 0

BRIEFR — generated 2026-08-26 07:00 Asia/Kolkata | slot=standup | facts=local | lede=template
```

### Busy end-of-day (abridged)

```
BRIEFR EOD
2026-08-25 18:00 → 2026-08-26 18:00 (Asia/Kolkata)

// HEADLINE
2 new KEV entries. 1 matches My Stack. Watchlist: EPSS jump on CVE-2026-1234.

// COUNTS
KEV new: 2
Stack matches: 1
Watchlist: 1
IOC hits: 0
Critical/High new: 4
Ops issues: 0

// KEV
• CVE-2026-1111 — added to KEV · CRITICAL
• CVE-2026-2222 — added to KEV · HIGH

// STACK
• CVE-2026-1111 — CPE match · CRITICAL

// WATCHLIST
• CVE-2026-1234 — EPSS jump

BRIEFR — generated 2026-08-26 18:00 Asia/Kolkata | slot=eod | facts=local | lede=groq
```

## 5. What this is not

- Not a PDF, email, or in-app notification dump.
- Not a substitute for `watchlist_alert` / `kev_alert` (those stay real-time).
- Not per-user prose (“since *you* logged off”) on a shared webhook — window copy is clock + timezone (see spec).
