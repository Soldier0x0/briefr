/**
 * Hunt pack PDF export (FR-3, forge-redesign.md §4/§5) — jsPDF on the same
 * pattern as pdfReport.js: lazy-loaded jsPDF, shared exportCommon.js layout
 * constants/branding, local page-layout helpers (pdfReport.js keeps its own
 * drawSection/drawCodeBlock private too — no shared abstraction worth
 * extracting for one more caller). No new dependency.
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
import { drawPdfCodeBlock } from './pdfCodeBlock.js'

const CONTENT_TOP = 18

let jsPdfPromise = null

function loadJsPdf() {
  if (!jsPdfPromise) {
    jsPdfPromise = import('jspdf').then(({ jsPDF }) => jsPDF)
  }
  return jsPdfPromise
}

const SIEM_LABELS = {
  elastic_kql: 'Elastic KQL',
  splunk_spl: 'Splunk SPL',
  sentinel_kql: 'Sentinel KQL',
  qradar_aql: 'QRadar AQL',
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

function applyFootersAndStripes(doc, meta) {
  const total = doc.getNumberOfPages()
  for (let p = 1; p <= total; p += 1) {
    doc.setPage(p)
    doc.setFont(FONT_BODY, 'normal')
    doc.setFontSize(7)
    doc.setTextColor(100, 100, 100)
    doc.text(FOOTER_COPYRIGHT, PAGE_W / 2, FOOTER_Y - 3, { align: 'center' })
    const footer = `BRIEFR — Hunt Pack Export | Generated ${meta.timestamp} | Page ${p} of ${total}`
    doc.text(footer, PAGE_W / 2, FOOTER_Y, { align: 'center' })
  }
}

function drawHeader(doc, meta, pack) {
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
  doc.text(pack.title || `${pack.technique_id} — ${pack.cve_id}`, MARGIN, 24, { maxWidth: PAGE_W - MARGIN * 2 })

  let badgeX = MARGIN
  const badgeY = 32
  const badges = []
  if (pack.priority) badges.push(pack.priority.toUpperCase())
  if (pack.is_kev) badges.push('KEV')
  if (pack.cvss_score != null) badges.push(`CVSS ${Number(pack.cvss_score).toFixed(1)}`)
  if (pack.epss_score != null) badges.push(`EPSS ${(pack.epss_score * 100).toFixed(1)}%`)
  ;(pack.cwe_ids || []).forEach(cwe => badges.push(cwe))

  doc.setFontSize(8)
  badges.forEach(b => {
    const w = doc.getTextWidth(b) + 6
    doc.setDrawColor(...hexToRgb(BRAND))
    doc.setLineWidth(0.3)
    doc.rect(badgeX, badgeY - 4, w, 6)
    doc.setTextColor(...hexToRgb(BRAND))
    doc.text(b, badgeX + 3, badgeY)
    badgeX += w + 4
  })

  return 42
}

function buildMeta() {
  const now = new Date()
  return {
    timestamp: getReportTimestamp(),
    dateLine: now.toLocaleString('en-GB', {
      year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit',
    }),
  }
}

/**
 * Export one saved hunt pack to PDF: Sigma rule, SIEM quick-search queries,
 * log patterns, notes, CVE/KEV/CWE/EPSS context, related case studies (when
 * known) — everything the Hunt Pack rail shows for the pack, on paper.
 *
 * @param {object} pack - hunt_packs row shape (from fetchHuntPacks or
 *   fetchHuntPack): technique_id, cve_id, title, priority, sigma_yaml,
 *   siem_queries, log_patterns, notes, is_kev, cwe_ids, cvss_score, epss_score.
 * @param {object} [context]
 * @param {object} [context.technique] - { technique_id, name, tactic } — only
 *   known when exporting from the Hunt Pack rail (technique detail already
 *   loaded there); Library exports fall back to pack.technique_id.
 * @param {object[]} [context.caseStudies]
 */
export async function downloadHuntPackPdf(pack, context = {}) {
  const jsPDF = await loadJsPdf()
  const meta = buildMeta()
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const ctx = { doc, y: CONTENT_TOP }

  ctx.y = drawHeader(doc, meta, pack)

  const technique = context.technique
  const techLine = technique
    ? `${technique.technique_id} — ${technique.name}${technique.tactic ? ` (${technique.tactic})` : ''}`
    : pack.technique_id
  drawSection(ctx, 'TECHNIQUE', techLine, hexToRgb(BRAND))

  drawPdfCodeBlock(ctx, 'SIGMA RULE (experimental)', pack.sigma_yaml, hexToRgb(BRAND), {
    doc: ctx.doc,
    margin: MARGIN,
    pageW: PAGE_W,
    ensureSpace,
    splitLines,
  })

  const siem = pack.siem_queries || {}
  const codeLayout = {
    doc: ctx.doc,
    margin: MARGIN,
    pageW: PAGE_W,
    ensureSpace,
    splitLines,
  }
  Object.entries(SIEM_LABELS).forEach(([platform, label]) => {
    const entry = siem[platform]
    if (entry?.query) {
      drawPdfCodeBlock(ctx, `SIEM QUERY — ${label}`, entry.query, hexToRgb(BRAND), codeLayout)
    }
  })

  if (pack.log_patterns?.length) {
    drawSection(ctx, 'LOG PATTERNS', pack.log_patterns.map(p => `• ${p}`), hexToRgb(BRAND))
  }

  if (pack.notes) {
    drawSection(ctx, 'NOTES', pack.notes, hexToRgb(BRAND))
  }

  if (context.caseStudies?.length) {
    const lines = context.caseStudies.map(s => {
      const meta2 = [s.target, s.incident_date].filter(Boolean).join(' · ')
      return `${s.name}${meta2 ? ` (${meta2})` : ''}${s.summary ? `\n${s.summary}` : ''}`
    })
    drawSection(ctx, 'RELATED CASE STUDIES (MITRE ATLAS)', lines.join('\n\n'), hexToRgb(BRAND))
  }

  applyFootersAndStripes(doc, meta)
  doc.save(`hunt-pack-${pack.technique_id}-${pack.cve_id}.pdf`)
}
