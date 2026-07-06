/**
 * Investigation thread PDF (browser-side jsPDF).
 */
import { jsPDF } from 'jspdf'
import { enrichCveForPdf } from './pdfReport.js'
import {
  aiFooterNoteForSource,
  formatExecutiveSummaryBody,
  loadPdfExecutiveSummary,
} from './pdfAiSummary.js'
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

const T_CVE = 'cve'
const T_IOC = 'ioc'
const T_ACTOR = 'actor'
const T_TECHNIQUE = 'technique'

const CONTENT_TOP = 20

function buildMeta(options) {
  return {
    timestamp: getReportTimestamp(),
    analystName: (options.analystName || '').trim(),
    aiFooterNote: options.aiFooterNote || null,
  }
}

function applyFooters(doc, meta) {
  const total = doc.getNumberOfPages()
  for (let p = 1; p <= total; p += 1) {
    doc.setPage(p)
    doc.setFont(FONT_BODY, 'normal')
    doc.setFontSize(7)
    doc.setTextColor(100, 100, 100)
    doc.text(
      FOOTER_COPYRIGHT,
      PAGE_W / 2,
      FOOTER_Y - 3,
      { align: 'center' },
    )
    doc.text(
      `BRIEFR — projectjupiter.in | Generated ${meta.timestamp} | Page ${p} of ${total}`,
      PAGE_W / 2,
      FOOTER_Y,
      { align: 'center' },
    )
    if (meta.aiFooterNote) {
      doc.setFontSize(6)
      doc.setTextColor(110, 110, 110)
      doc.text(meta.aiFooterNote, PAGE_W / 2, FOOTER_Y + 4, { align: 'center' })
    }
  }
}

function splitLines(doc, text, maxW) {
  if (!text) return []
  return doc.splitTextToSize(String(text), maxW)
}

function ensureSpace(ctx, h) {
  if (ctx.y + h > CONTENT_BOTTOM) {
    ctx.doc.addPage()
    ctx.y = CONTENT_TOP
  }
}

function drawHeading(doc, y, text, size = 14) {
  doc.setFont(FONT_BODY, 'bold')
  doc.setFontSize(size)
  doc.setTextColor(...hexToRgb(BRAND))
  doc.text(text, MARGIN, y)
}

function formatDuration(startTime) {
  const min = Math.max(1, Math.round((Date.now() - startTime) / 60000))
  if (min < 60) return `${min} minute(s)`
  return `${Math.floor(min / 60)}h ${min % 60}m`
}

function formatElapsed(ts, startTime) {
  const sec = Math.floor((ts - startTime) / 1000)
  if (sec < 60) return `${sec}s`
  return `${Math.floor(sec / 60)}m ${sec % 60}s`
}

function drawTimelinePage(doc, items, startTime) {
  let y = CONTENT_TOP + 8
  drawHeading(doc, y, 'Investigation Timeline', 12)
  y += 14

  const step = Math.min(38, (PAGE_W - MARGIN * 2) / Math.max(items.length, 1))
  let x = MARGIN

  doc.setFont(FONT_MONO, 'normal')
  doc.setFontSize(7)
  items.forEach((item, idx) => {
    if (x + step > PAGE_W - MARGIN) {
      x = MARGIN
      y += 28
    }
    doc.setFillColor(...hexToRgb(BRAND))
    doc.circle(x + 4, y, 2, 'F')
    if (idx < items.length - 1) {
      doc.setDrawColor(200, 200, 200)
      doc.line(x + 6, y, x + step - 2, y)
    }
    doc.setTextColor(40, 40, 40)
    doc.text(item.id.slice(0, 14), x, y + 6)
    doc.setTextColor(120, 120, 120)
    doc.text(formatElapsed(item.timestamp, startTime), x, y + 10)
    doc.text((item.type || '').toUpperCase(), x, y + 14)
    x += step
  })
}

function drawSectionBody(ctx, title, lines) {
  const doc = ctx.doc
  const maxW = PAGE_W - MARGIN * 2
  const body = splitLines(doc, Array.isArray(lines) ? lines.join('\n') : lines, maxW)
  const h = 12 + body.length * 4.5
  ensureSpace(ctx, h)
  doc.setFont(FONT_MONO, 'bold')
  doc.setFontSize(9)
  doc.setTextColor(...hexToRgb(BRAND))
  doc.text(`// ${title}`, MARGIN, ctx.y)
  ctx.y += 6
  doc.setFont(FONT_BODY, 'normal')
  doc.setFontSize(9)
  doc.setTextColor(30, 30, 30)
  body.forEach(line => {
    doc.text(line, MARGIN, ctx.y)
    ctx.y += 4.5
  })
  ctx.y += 6
}

function consolidatedActions(cveDetails) {
  const actions = []
  cveDetails.forEach(cve => {
    if (cve.patch_available) {
      actions.push(`[${cve.cve_id}] Apply vendor patch immediately${cve.is_kev ? ' (KEV)' : ''}.`)
    } else {
      actions.push(`[${cve.cve_id}] Monitor for patch; apply mitigations.`)
    }
  })
  if (!actions.length) {
    actions.push('Review investigation thread and validate exposure for each CVE.')
  }
  actions.push('Short term: Correlate IOC activity with internal logs and detections.')
  actions.push('Ongoing: Track EPSS trends and KEV updates for listed vulnerabilities.')
  return actions
}

const SOURCES = [
  'NVD — https://nvd.nist.gov',
  'CISA KEV — https://www.cisa.gov/known-exploited-vulnerabilities-catalog',
  'FIRST EPSS — https://www.first.org/epss',
  'MITRE ATT&CK — https://attack.mitre.org',
  'MITRE ATLAS — https://atlas.mitre.org',
  'VirusTotal / AbuseIPDB / GreyNoise / abuse.ch (IOC Lookup)',
]

export async function downloadInvestigationPdf(items, startTime, options = {}) {
  const durationMin = Math.max(1, Math.round((Date.now() - startTime) / 60000))

  const cveIds = [...new Set(items.filter(i => i.type === T_CVE).map(i => i.id))]
  const cveDetails = await Promise.all(
    cveIds.map(id => enrichCveForPdf({ cve_id: id }).catch(() => ({ cve_id: id }))),
  )

  const iocItems = items.filter(i => i.type === T_IOC)
  const actorItems = items.filter(i => i.type === T_ACTOR)

  let summaryData = await loadPdfExecutiveSummary({
    cves: cveDetails,
    iocs: iocItems.map(i => ({
      value: i.id,
      description: i.description,
    })),
    actors: actorItems.map(i => ({
      name: i.title || i.id,
      description: i.description,
    })),
    investigationDuration: durationMin,
  })

  if (!summaryData) {
    summaryData = {
      executive_summary: `Investigation with ${items.length} items over ${durationMin} minutes.`,
      key_findings: [],
      confidence: 'low',
      source: 'template',
    }
  }

  const meta = buildMeta({
    ...options,
    aiFooterNote: aiFooterNoteForSource(summaryData.source),
  })

  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const ctx = { doc, y: CONTENT_TOP }

  // Cover
  doc.setFont(FONT_MONO, 'bold')
  doc.setFontSize(16)
  doc.setTextColor(...hexToRgb(BRAND))
  doc.text('BRIEFR', MARGIN, 30)
  doc.setFont(FONT_BODY, 'bold')
  doc.setFontSize(18)
  doc.setTextColor(20, 20, 20)
  doc.text('Security Investigation Report', MARGIN, 42)
  doc.setFont(FONT_BODY, 'normal')
  doc.setFontSize(10)
  doc.setTextColor(80, 80, 80)
  if (meta.analystName) doc.text(`Analyst: ${meta.analystName}`, MARGIN, 54)
  doc.text(`Date: ${new Date().toLocaleString('en-GB')}`, MARGIN, meta.analystName ? 60 : 54)
  doc.text(`Duration: ${formatDuration(startTime)}`, MARGIN, meta.analystName ? 66 : 60)
  let coverY = meta.analystName ? 72 : 66
  doc.text(`Items in thread: ${items.length}`, MARGIN, coverY)
  coverY += 8
  doc.setFontSize(8)
  doc.text(
    'Compiled from public OSINT (NVD, CISA KEV, EPSS, and related feeds).',
    MARGIN,
    coverY,
  )

  doc.addPage()
  drawTimelinePage(doc, items, startTime)

  doc.addPage()
  ctx.y = CONTENT_TOP
  drawSectionBody(ctx, 'EXECUTIVE SUMMARY', formatExecutiveSummaryBody(summaryData))
  if (summaryData.source === 'template') {
    doc.setFontSize(7)
    doc.setTextColor(120, 120, 120)
    doc.text(
      '(Template summary — set GROQ_API_KEY or ANTHROPIC_API_KEY for AI-generated text)',
      MARGIN,
      ctx.y,
    )
    ctx.y += 8
  }

  const iocs = iocItems
  const actors = actorItems
  const techniques = items.filter(i => i.type === T_TECHNIQUE)

  if (cveDetails.length) {
    doc.addPage()
    ctx.y = CONTENT_TOP
    cveDetails.forEach(cve => {
      const lines = [
        `${cve.severity || 'Unknown'} · CVSS ${cve.cvss_score != null ? Number(cve.cvss_score).toFixed(1) : 'N/A'}`,
        cve.summary || cve.description || '',
        cve.sentences?.risk || '',
        cve.sentences?.patch || '',
      ].filter(Boolean)
      drawSectionBody(ctx, `VULNERABILITY — ${cve.cve_id}`, lines)
    })
  }

  if (iocs.length) {
    ensureSpace(ctx, 40)
    if (ctx.y > CONTENT_BOTTOM - 30) {
      doc.addPage()
      ctx.y = CONTENT_TOP
    }
    drawSectionBody(
      ctx,
      'INDICATORS OF COMPROMISE',
      iocs.map(i => `${i.id}: ${i.description || 'IOC lookup'}`),
    )
  }

  if (actors.length) {
    drawSectionBody(
      ctx,
      'THREAT ACTOR CONTEXT',
      actors.map(a => `${a.title}: ${a.description || 'Actor pivot from IOC tags or case studies'}`),
    )
  }

  if (techniques.length || items.some(i => i.source === 'atlas')) {
    const atlasLines = techniques.map(t => t.title)
    if (!atlasLines.length) atlasLines.push('See ATLAS case studies in application for technique mappings.')
    drawSectionBody(ctx, 'AI THREAT CONTEXT', atlasLines)
  }

  doc.addPage()
  ctx.y = CONTENT_TOP
  drawSectionBody(ctx, 'RECOMMENDED ACTIONS', consolidatedActions(cveDetails))
  drawSectionBody(ctx, 'SOURCES', SOURCES.join('\n'))

  applyFooters(doc, meta)
  const stamp = new Date().toISOString().slice(0, 10)
  doc.save(`briefr-investigation-${stamp}.pdf`)
}
