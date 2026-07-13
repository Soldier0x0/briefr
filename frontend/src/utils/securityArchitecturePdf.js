/**
 * Security Architecture PDF export (TM-5, spec §5.16) — jsPDF on the same
 * pattern as huntPackPdf.js / pdfReport.js: lazy-loaded jsPDF, shared
 * exportCommon.js layout constants/branding, local page-layout helpers.
 * No new dependency, no reinvented layout helpers.
 *
 * Per-section export, not a 17-section mega-document (spec §5.16): Overview
 * posture snapshot, Risk register, and a selected threat scenario each get
 * their own "Export PDF" action from their section component.
 *
 * Every export footer carries corpus version, generated timestamp, and --
 * when any included record is stale -- an explicit "contains N stale
 * records" disclaimer (spec §5.16: "a PDF must be at least as honest as
 * the screen it came from"). Staleness is read from each row's `stale`
 * flag, computed once server-side (security_architecture/merge.py::
 * annotate_stale) -- never recomputed client-side, so the screen and the
 * PDF can never disagree about which rows are stale.
 */
import { getReportTimestamp } from './timezone.js'
import {
  BRAND,
  PAGE_W,
  MARGIN,
  CONTENT_BOTTOM,
  FOOTER_Y,
  FONT_BODY,
  FONT_MONO,
  FOOTER_COPYRIGHT,
  hexToRgb,
} from './exportCommon.js'

const CONTENT_TOP = 18

let jsPdfPromise = null

function loadJsPdf() {
  if (!jsPdfPromise) {
    jsPdfPromise = import('jspdf').then(({ jsPDF }) => jsPDF)
  }
  return jsPdfPromise
}

function splitLines(doc, text, maxWidth) {
  if (!text) return []
  return doc.splitTextToSize(String(text).replace(/\r\n/g, '\n'), maxWidth)
}

function ensureSpace(ctx, needed) {
  if (ctx.y + needed > CONTENT_BOTTOM) {
    ctx.doc.addPage()
    ctx.y = CONTENT_TOP
  }
}

function drawSection(ctx, title, bodyLines, borderRgb) {
  const maxW = PAGE_W - MARGIN * 2 - 4
  const lines = Array.isArray(bodyLines)
    ? bodyLines.flatMap(item => splitLines(ctx.doc, item, maxW))
    : splitLines(ctx.doc, bodyLines, maxW)
  if (!lines.length) return
  const blockH = 10 + lines.length * 4.5 + 6
  ensureSpace(ctx, blockH)

  const x = MARGIN
  const y0 = ctx.y
  if (borderRgb) {
    ctx.doc.setFillColor(...borderRgb)
    ctx.doc.rect(x, y0, 2, blockH - 2, 'F')
  }

  ctx.doc.setFont(FONT_MONO, 'bold')
  ctx.doc.setFontSize(8)
  ctx.doc.setTextColor(...hexToRgb(BRAND))
  ctx.doc.text(`// ${title}`, x + 5, y0 + 5)

  ctx.doc.setFont(FONT_BODY, 'normal')
  ctx.doc.setFontSize(9)
  ctx.doc.setTextColor(30, 30, 30)
  let y = y0 + 11
  lines.forEach(line => {
    ctx.doc.text(line, x + 5, y)
    y += 4.5
  })
  ctx.y = y0 + blockH
}

function drawHeader(doc, meta, title) {
  doc.setFont(FONT_MONO, 'bold')
  doc.setFontSize(14)
  doc.setTextColor(...hexToRgb(BRAND))
  doc.text('BRIEFR', MARGIN, 12)

  doc.setFont(FONT_BODY, 'normal')
  doc.setFontSize(8)
  doc.setTextColor(80, 80, 80)
  doc.text(meta.dateLine, PAGE_W - MARGIN, 10, { align: 'right' })

  doc.setFont(FONT_MONO, 'bold')
  doc.setFontSize(16)
  doc.setTextColor(20, 20, 20)
  doc.text(title, MARGIN, 24, { maxWidth: PAGE_W - MARGIN * 2 })

  doc.setFont(FONT_MONO, 'normal')
  doc.setFontSize(8)
  doc.setTextColor(...hexToRgb(BRAND))
  doc.text('SECURITY ARCHITECTURE', MARGIN, 30)

  return 40
}

function applyFootersAndStripes(doc, meta, staleCount) {
  const total = doc.getNumberOfPages()
  const disclaimer = staleCount > 0
    ? ` | Contains ${staleCount} stale record${staleCount === 1 ? '' : 's'} (past ${meta.staleWindowDays}-day review window)`
    : ''
  for (let p = 1; p <= total; p += 1) {
    doc.setPage(p)
    doc.setFont(FONT_BODY, 'normal')
    doc.setFontSize(7)
    doc.setTextColor(100, 100, 100)
    doc.text(FOOTER_COPYRIGHT, PAGE_W / 2, FOOTER_Y - 6, { align: 'center' })
    const footer = `BRIEFR — Security Architecture | Corpus v${meta.corpusVersion} | Generated ${meta.timestamp} | Page ${p} of ${total}`
    doc.text(footer, PAGE_W / 2, FOOTER_Y - 3, { align: 'center' })
    if (disclaimer) {
      doc.setTextColor(...hexToRgb('#f59e0b'))
      doc.setFont(FONT_MONO, 'bold')
      doc.text(disclaimer.trim(), PAGE_W / 2, FOOTER_Y, { align: 'center' })
    }
  }
}

function buildMeta(corpusVersion) {
  const now = new Date()
  return {
    timestamp: getReportTimestamp(),
    corpusVersion: corpusVersion ?? '—',
    staleWindowDays: 90,
    dateLine: now.toLocaleString('en-GB', {
      year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit',
    }),
  }
}

/**
 * Overview posture snapshot: every tile as reported by the server (counts
 * and ratios only — no arithmetic invented on the client, matching the
 * module's central principle).
 */
export async function downloadOverviewPdf(overview) {
  const jsPDF = await loadJsPdf()
  const meta = buildMeta(overview?.corpus_version)
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const ctx = { doc, y: CONTENT_TOP }

  ctx.y = drawHeader(doc, meta, 'Overview — Posture Snapshot')

  const tiles = overview?.tiles || []
  const tileLines = tiles.map(t => `${t.label}: ${t.value}${t.unit ? ` ${t.unit}` : ''}`)
  drawSection(ctx, 'POSTURE TILES', tileLines, hexToRgb(BRAND))

  if (overview?.self_exposure) {
    const ex = overview.self_exposure
    drawSection(ctx, 'SELF CVE EXPOSURE', [
      `${ex.count} matching CVE(s) — ${ex.kev_count} KEV, ${ex.critical_count} critical`,
      `Self-stack terms (${ex.terms?.length ?? 0}): ${(ex.terms || []).join(', ') || '—'}`,
    ], hexToRgb(BRAND))
  }

  applyFootersAndStripes(doc, meta, 0)
  doc.save(`briefr-security-architecture-overview-${new Date().toISOString().slice(0, 10)}.pdf`)
}

/**
 * Risk register: the exact rows currently rendered on screen (curated +
 * live, whatever filter is active) — a stale curated row triggers the
 * footer disclaimer.
 */
export async function downloadRiskRegisterPdf(rows, meta = {}) {
  const jsPDF = await loadJsPdf()
  const pdfMeta = buildMeta(meta.corpusVersion)
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const ctx = { doc, y: CONTENT_TOP }

  ctx.y = drawHeader(doc, pdfMeta, 'Risk Register')

  const staleCount = rows.filter(r => r.stale).length

  if (!rows.length) {
    drawSection(ctx, 'RISK REGISTER', 'No risk rows in the current view.', hexToRgb(BRAND))
  } else {
    rows.forEach(r => {
      const flags = [
        r.origin ? r.origin.toUpperCase() : null,
        r.severity ? r.severity.toUpperCase() : null,
        r.status,
        r.stale ? 'STALE' : null,
        r.matched_term ? `term: ${r.matched_term}` : null,
      ].filter(Boolean).join(' · ')
      drawSection(
        ctx,
        r.title || r.id,
        [flags, r.summary].filter(Boolean),
        r.stale ? hexToRgb('#f59e0b') : hexToRgb(BRAND),
      )
    })
  }

  applyFootersAndStripes(doc, pdfMeta, staleCount)
  doc.save(`briefr-risk-register-${new Date().toISOString().slice(0, 10)}.pdf`)
}

/**
 * A single selected threat scenario (operational, stack, or self-stack
 * catalog) — timeline steps + mitigations, whichever shape the active
 * catalog returned.
 */
export async function downloadScenarioPdf(scenario, meta = {}) {
  const jsPDF = await loadJsPdf()
  const pdfMeta = buildMeta(meta.corpusVersion)
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const ctx = { doc, y: CONTENT_TOP }

  const title = scenario.title || scenario.scenario || `${scenario.technique_id ?? ''} scenario`
  ctx.y = drawHeader(doc, pdfMeta, title)

  if (scenario.summary) {
    drawSection(ctx, 'SUMMARY', scenario.summary, hexToRgb(BRAND))
  }
  if (scenario.scenario) {
    drawSection(ctx, 'SCENARIO', scenario.scenario, hexToRgb(BRAND))
  }
  if (Array.isArray(scenario.steps) && scenario.steps.length) {
    const lines = scenario.steps.map((s, i) => {
      const who = s.actor || s.component || `Step ${i + 1}`
      return `${i + 1}. ${who} — ${s.threat || ''}`
    })
    drawSection(ctx, 'ATTACK PATH', lines, hexToRgb(BRAND))
  }
  if (Array.isArray(scenario.mitigations) && scenario.mitigations.length) {
    drawSection(ctx, 'MITIGATIONS', scenario.mitigations.map(m => `• ${m}`), hexToRgb(BRAND))
  }
  if (scenario.technique_id) {
    drawSection(ctx, 'MITRE ATT&CK', `${scenario.technique_id} — ${scenario.name || ''} (${scenario.coverage_status || 'unknown coverage'})`, hexToRgb(BRAND))
  }

  applyFootersAndStripes(doc, pdfMeta, scenario.stale ? 1 : 0)
  doc.save(`briefr-threat-scenario-${(scenario.id || scenario.technique_id || 'scenario')}.pdf`)
}
