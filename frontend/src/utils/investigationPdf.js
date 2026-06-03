/**
 * Investigation thread PDF (browser-side jsPDF).
 */
import { jsPDF } from 'jspdf'
import { fetchInvestigationSummary } from '../api.js'
import { enrichCveForPdf } from './pdfReport.js'
import { TLP_OPTIONS } from './pdfReport.js'
import { getReportTimestamp } from './timezone.js'
const T_CVE = 'cve'
const T_IOC = 'ioc'
const T_ACTOR = 'actor'
const T_TECHNIQUE = 'technique'

const BRAND = '#e85533'
const PAGE_W = 210
const PAGE_H = 297
const MARGIN = 15
const CONTENT_TOP = 20
const CONTENT_BOTTOM = 262
const FOOTER_Y = 285
const STRIPE_H = 4
const FONT_BODY = 'helvetica'
const FONT_MONO = 'courier'

function hexToRgb(hex) {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

function buildMeta(options) {
  const tlp = TLP_OPTIONS.find(t => t.id === options.tlp) || TLP_OPTIONS[0]
  return {
    timestamp: getReportTimestamp(),
    analystName: (options.analystName || '').trim(),
    tlpColor: tlp.color,
    tlpLabel: tlp.label,
  }
}

function drawTlpStripes(doc, tlpColor) {
  if (!tlpColor) return
  doc.setFillColor(...tlpColor)
  doc.rect(0, 0, PAGE_W, STRIPE_H, 'F')
  doc.rect(0, PAGE_H - STRIPE_H, PAGE_W, STRIPE_H, 'F')
}

function applyFooters(doc, meta) {
  const total = doc.getNumberOfPages()
  for (let p = 1; p <= total; p += 1) {
    doc.setPage(p)
    drawTlpStripes(doc, meta.tlpColor)
    doc.setFont(FONT_BODY, 'normal')
    doc.setFontSize(7)
    doc.setTextColor(100, 100, 100)
    doc.text(
      `BRIEFR — projectjupiter.in | Generated ${meta.timestamp} | Page ${p} of ${total}`,
      PAGE_W / 2,
      FOOTER_Y,
      { align: 'center' },
    )
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
  const meta = buildMeta(options)
  const durationMin = Math.max(1, Math.round((Date.now() - startTime) / 60000))

  const apiItems = items.map(i => ({
    type: i.type,
    id: i.id,
    description: i.description,
    pivotFrom: i.pivotFrom
      ? { type: i.pivotFrom.type, id: i.pivotFrom.id }
      : null,
  }))

  let summaryData
  try {
    summaryData = await fetchInvestigationSummary(apiItems, durationMin)
  } catch {
    summaryData = {
      summary: `Investigation with ${items.length} items over ${durationMin} minutes.`,
      source: 'template',
    }
  }

  const cveIds = [...new Set(items.filter(i => i.type === T_CVE).map(i => i.id))]
  const cveDetails = await Promise.all(
    cveIds.map(id => enrichCveForPdf({ cve_id: id }).catch(() => ({ cve_id: id }))),
  )

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
  doc.text(`Classification: ${meta.tlpLabel}`, MARGIN, meta.analystName ? 72 : 66)
  doc.text(`Items in thread: ${items.length}`, MARGIN, meta.analystName ? 78 : 72)

  doc.addPage()
  drawTimelinePage(doc, items, startTime)

  doc.addPage()
  ctx.y = CONTENT_TOP
  drawSectionBody(ctx, 'EXECUTIVE SUMMARY', summaryData.summary)
  if (summaryData.source === 'template') {
    doc.setFontSize(7)
    doc.setTextColor(120, 120, 120)
    doc.text('(Template summary — set GROQ_API_KEY for AI-generated text)', MARGIN, ctx.y)
    ctx.y += 8
  }

  const iocs = items.filter(i => i.type === T_IOC)
  const actors = items.filter(i => i.type === T_ACTOR)
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
