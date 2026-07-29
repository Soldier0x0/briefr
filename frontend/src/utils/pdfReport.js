/**
 * Browser-side CVE PDF reports (jsPDF + optional html2canvas capture).
 * Heavy PDF libs load on first export via dynamic import — not on first paint.
 */
import { fetchCVE, fetchCVECorrelation, fetchCVEDetection, fetchCVESentences } from '../api.js'
import {
  aiFooterNoteForSource,
  formatExecutiveSummaryBody,
  loadPdfExecutiveSummary,
} from './pdfAiSummary.js'
import { getReportTimestamp } from './timezone.js'
import { sanitizePdfText, pdfContentWidth } from './pdfText.js'
import {
  BRAND,
  PAGE_W,
  MARGIN,
  CONTENT_BOTTOM,
  FOOTER_Y,
  FONT_BODY,
  FONT_MONO,
  FOOTER_COPYRIGHT,
  PUBLIC_SITE_URL,
  hexToRgb,
} from './exportCommon.js'

const CONTENT_TOP = 18

let pdfLibsPromise = null

function loadPdfLibs() {
  if (!pdfLibsPromise) {
    pdfLibsPromise = Promise.all([
      import('jspdf'),
      import('html2canvas'),
    ]).then(([{ jsPDF }, { default: html2canvas }]) => ({ jsPDF, html2canvas }))
  }
  return pdfLibsPromise
}

const DATA_SOURCES = [
  { name: 'NVD (NIST)', url: 'https://nvd.nist.gov' },
  { name: 'CISA KEV', url: 'https://www.cisa.gov/known-exploited-vulnerabilities-catalog' },
  { name: 'FIRST EPSS', url: 'https://www.first.org/epss' },
  { name: 'OSV.dev', url: 'https://osv.dev' },
  { name: 'MITRE ATT&CK', url: 'https://attack.mitre.org' },
  { name: 'Sploitus', url: 'https://sploitus.com' },
  { name: 'GreyNoise', url: 'https://www.greynoise.io' },
]

function severityBorderColor(sev) {
  const s = (sev || '').toUpperCase()
  if (s === 'CRITICAL') return [232, 85, 51]
  if (s === 'HIGH') return [245, 158, 11]
  return [200, 200, 200]
}

function splitLines(doc, text, maxWidth) {
  if (!text) return []
  return doc.splitTextToSize(sanitizePdfText(text), maxWidth)
}

function ensureSpace(ctx, needed) {
  if (ctx.y + needed > CONTENT_BOTTOM) {
    ctx.doc.addPage()
    ctx.pageNum += 1
    ctx.y = CONTENT_TOP
  }
}

function applyFootersAndStripes(doc, meta) {
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
    const footer = `BRIEFR — ${PUBLIC_SITE_URL} | Generated ${meta.timestamp} | Page ${p} of ${total}`
    doc.text(footer, PAGE_W / 2, FOOTER_Y, { align: 'center' })
    if (meta.aiFooterNote) {
      doc.setFontSize(6)
      doc.setTextColor(110, 110, 110)
      doc.text(meta.aiFooterNote, PAGE_W / 2, FOOTER_Y + 4, { align: 'center' })
    }
  }
}

function drawSection(ctx, title, bodyLines, borderRgb) {
  const innerPad = 10
  const maxW = pdfContentWidth(PAGE_W, MARGIN, innerPad)
  const body = Array.isArray(bodyLines) ? bodyLines.join('\n\n') : bodyLines
  const lines = splitLines(ctx.doc, body, maxW)
  const lineH = 4.5
  const blockH = 9 + lines.length * lineH + 4
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
  ctx.doc.text(`// ${title}`, x + innerPad - 5, y0 + 5)

  ctx.doc.setFont(FONT_BODY, 'normal')
  ctx.doc.setFontSize(9)
  ctx.doc.setTextColor(30, 30, 30)
  ctx.doc.text(lines, x + innerPad - 5, y0 + 11, { maxWidth: maxW, lineHeightFactor: 1.35 })
  ctx.y = y0 + blockH
}

function drawCodeBlock(ctx, title, code, borderRgb) {
  if (!code) return
  const maxW = PAGE_W - MARGIN * 2 - 8
  const lines = splitLines(ctx.doc, code, maxW)
  const blockH = 12 + lines.length * 4.2 + 8
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

  ctx.doc.setFont(FONT_MONO, 'normal')
  ctx.doc.setFontSize(7.5)
  ctx.doc.setTextColor(40, 40, 40)
  let y = y0 + 12
  lines.forEach(line => {
    ctx.doc.text(line, x + 5, y)
    y += 4.2
  })
  ctx.y = y0 + blockH
}

function pickSigmaYaml(detection) {
  if (!detection) return ''
  const rules = detection.sigma_rules || []
  if (rules.length && rules[0].content) return rules[0].content
  if (detection.generated_sigma) return detection.generated_sigma
  return ''
}

function drawCheckboxList(ctx, title, items, borderRgb) {
  const maxW = PAGE_W - MARGIN * 2 - 12
  const lines = items.flatMap(item => splitLines(ctx.doc, item, maxW))
  const blockH = 10 + lines.length * 5 + 6
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
  let y = y0 + 12
  items.forEach(item => {
    const itemLines = splitLines(ctx.doc, item, maxW)
    itemLines.forEach((line, idx) => {
      if (idx === 0) {
        ctx.doc.rect(x + 5, y - 3, 3, 3)
      }
      ctx.doc.text(line, x + 11, y)
      y += 5
    })
  })
  ctx.y = y0 + blockH
}

function drawPageHeader(doc, meta, cve, isFirstPageOfCve = true) {
  doc.setFont(FONT_MONO, 'bold')
  doc.setFontSize(14)
  doc.setTextColor(...hexToRgb(BRAND))
  doc.text('BRIEFR', MARGIN, 12)

  doc.setFont(FONT_BODY, 'normal')
  doc.setFontSize(8)
  doc.setTextColor(80, 80, 80)
  doc.text(meta.dateLine, PAGE_W - MARGIN, 10, { align: 'right' })
  if (meta.analystName) {
    doc.text(`Analyst: ${meta.analystName}`, PAGE_W - MARGIN, 14, { align: 'right' })
  }

  if (isFirstPageOfCve && cve) {
    doc.setFont(FONT_MONO, 'bold')
    doc.setFontSize(18)
    doc.setTextColor(20, 20, 20)
    doc.text(cve.cve_id || '', MARGIN, 24)

    let badgeX = MARGIN
    const badgeY = 30
    const badges = []
    if (cve.severity) badges.push((cve.severity || '').toUpperCase())
    if (cve.is_kev) badges.push('KEV')
    if (cve.cvss_score != null) badges.push(`CVSS ${Number(cve.cvss_score).toFixed(1)}`)
    if (cve.epss_score != null) badges.push(`EPSS ${(cve.epss_score * 100).toFixed(1)}%`)

    doc.setFontSize(8)
    badges.forEach(b => {
      const padX = 3
      const padY = 1.5
      const textW = doc.getTextWidth(b)
      const boxW = textW + padX * 2
      const boxH = 5
      doc.setDrawColor(...hexToRgb(BRAND))
      doc.setLineWidth(0.3)
      doc.rect(badgeX, badgeY - boxH + padY, boxW, boxH)
      doc.setTextColor(...hexToRgb(BRAND))
      doc.text(b, badgeX + padX, badgeY)
      badgeX += boxW + 4
    })
    return 38
  }
  return CONTENT_TOP
}

function detectionLinesFromTechniques(techniques) {
  const lines = []
  ;(techniques || []).forEach(tech => {
    const desc = (tech.description || '').trim()
    if (!desc) return
    const short = desc.length > 400 ? `${desc.slice(0, 397)}…` : desc
    lines.push(`${tech.id || tech.technique_id}: ${short}`)
  })
  if (!lines.length) {
    return ['No ATT&CK detection guidance text is stored for mapped techniques.']
  }
  return lines
}

function recommendedActions(cve, sentences) {
  const items = []
  if (cve.patch_available) {
    items.push(`Immediate: Apply vendor patch${cve.is_kev ? ' (CISA KEV — priority)' : ''}.`)
  } else {
    items.push('Immediate: Apply vendor mitigations; monitor for patch release.')
  }
  const techCount = (cve.techniques || []).length
  items.push(
    techCount > 0
      ? `Short term: Review logs and detections for ${techCount} mapped ATT&CK technique(s).`
      : 'Short term: Review authentication and exposure logs for suspicious activity.',
  )
  items.push(
    cve.epss_score != null
      ? `Ongoing: Monitor EPSS trend (current ${(cve.epss_score * 100).toFixed(1)}%).`
      : 'Ongoing: Monitor EPSS and threat feeds for exploitation signals.',
  )
  if (sentences?.patch) items[0] = `Immediate: ${sentences.patch}`
  return items
}

function formatActorIntel(correlation) {
  const actors = correlation?.actor || []
  if (!actors.length) {
    return 'Actor attribution: None identified in BRIEFR correlation data.'
  }
  return actors
    .map(a => {
      const sectors = a.actor_sectors?.length ? ` — sectors: ${a.actor_sectors.join(', ')}` : ''
      return `• ${a.actor_name}${sectors} (${(a.confidence || 'low')} confidence)`
    })
    .join('\n')
}

function formatCampaignIntel(correlation) {
  const campaigns = correlation?.campaigns
  if (!Array.isArray(campaigns) || !campaigns.length) {
    return ''
  }
  const sorted = [...campaigns].sort((a, b) => {
    const countA = a.member_count ?? (a.members?.length ?? 0)
    const countB = b.member_count ?? (b.members?.length ?? 0)
    return countB - countA
  })
  const primary = sorted[0]
  const label = (primary.label || primary.campaign_id || 'Campaign cluster').trim()
  const lifecycle = (primary.lifecycle || 'active').trim()
  const confidence = (primary.confidence || 'medium').trim()
  const members = Array.isArray(primary.members) ? primary.members : []
  const count = primary.member_count ?? members.length
  const memberNote = count ? `${count} linked CVEs` : 'linked CVEs'
  const pulse = (primary.primary_pulse_id || primary.pulse_id || '').trim()
  const pulseNote = pulse ? ` OTX pulse: ${pulse}.` : ''
  return (
    `Campaign link: ${label} (${lifecycle}, ${memberNote}, ${confidence} confidence).${pulseNote} `
    + 'Grouped from shared OTX pulse intelligence — validate before action.'
  )
}

function sourcesForCve(cve) {
  const urls = new Set(DATA_SOURCES.map(s => s.url))
  const list = [...DATA_SOURCES]
  ;(cve.source_urls || []).slice(0, 8).forEach(u => {
    if (u && !urls.has(u)) {
      urls.add(u)
      list.push({ name: 'Reference', url: u })
    }
  })
  return list
}

async function captureSparkline(element) {
  if (!element) return null
  try {
    const { html2canvas } = await loadPdfLibs()
    const canvas = await html2canvas(element, {
      backgroundColor: '#ffffff',
      scale: 2,
      logging: false,
    })
    return canvas.toDataURL('image/png')
  } catch {
    return null
  }
}

function renderSingleCvePages(doc, ctx, cve, meta, sparklineDataUrl, { newPage = false, executiveSummaryText = null } = {}) {
  const border = severityBorderColor(cve.severity)
  const sentences = cve.sentences || {}
  const techniques = cve.techniques || []
  const exploits = cve.public_exploits || []
  const scans = cve.greynoise_scans || []
  const products = (cve.affected_products || []).map(p => p.split(':').pop() || p).join(', ')
  const cwes = (cve.cwe_ids || []).join(', ')
  const fix = cve.osv_packages?.[0]?.fix || ''

  if (newPage) {
    doc.addPage()
    ctx.pageNum += 1
  }
  ctx.y = drawPageHeader(doc, meta, cve, true)

  const execBody = executiveSummaryText || [
    sentences.risk || `Severity: ${cve.severity || 'Unknown'}.`,
    cve.summary || cve.description || 'No plain-language summary available.',
    sentences.exploit_likelihood || (cve.epss_score != null
      ? `EPSS exploitation probability: ${(cve.epss_score * 100).toFixed(1)}%.`
      : ''),
    sentences.patch || (cve.patch_available ? 'Patch is available.' : 'No patch flagged in BRIEFR.'),
  ].filter(Boolean).join('\n\n')

  drawSection(ctx, 'EXECUTIVE SUMMARY', execBody, border)

  if (sparklineDataUrl) {
    ensureSpace(ctx, 28)
    const imgW = 70
    const imgH = 18
    ctx.doc.addImage(sparklineDataUrl, 'PNG', MARGIN + 5, ctx.y, imgW, imgH)
    ctx.y += imgH + 6
  }

  const techParts = [
    cve.description || 'No description.',
    products ? `Affected: ${products}` : '',
    fix ? `Fix: ${fix}` : '',
    cwes ? `CWE: ${cwes}` : '',
  ].filter(Boolean)
  drawSection(ctx, 'TECHNICAL DETAIL', techParts.join('\n\n'), border)

  const intelParts = [
    sentences.exploit_likelihood || '',
    sentences.kev || (cve.is_kev ? 'Listed on CISA KEV.' : 'Not on CISA KEV.'),
    sentences.public_exploits || '',
    exploits.length
      ? exploits.map(e => `• ${e.title || 'Exploit'} (${e.type || 'poc'})`).join('\n')
      : '',
    scans.length
      ? scans.map(s => `• ${s.ip}: ${s.classification || 'unknown'}${s.sentence ? ` — ${s.sentence}` : ''}`).join('\n')
      : '',
    formatActorIntel(cve.correlation),
    formatCampaignIntel(cve.correlation),
  ].filter(Boolean)
  drawSection(ctx, 'THREAT INTELLIGENCE', intelParts.join('\n\n'), border)

  if (techniques.length) {
    const mitreLines = techniques.map(t => {
      const tid = t.id || t.technique_id
      return `${tid} — ${t.name || 'Unknown'} (${t.tactic || 'tactic n/a'})`
    })
    drawSection(ctx, 'MITRE ATT&CK', mitreLines.join('\n'), border)
    drawSection(ctx, 'DETECTION OPPORTUNITIES', detectionLinesFromTechniques(techniques), border)
    const sigmaYaml = pickSigmaYaml(cve.detection)
    if (sigmaYaml) {
      drawCodeBlock(ctx, 'SIGMA RULE (copy-ready)', sigmaYaml, border)
    }
  } else {
    drawSection(ctx, 'MITRE ATT&CK', 'No techniques mapped.', border)
    drawSection(ctx, 'DETECTION OPPORTUNITIES', 'No detection guidance — no ATT&CK mapping.', border)
  }

  drawCheckboxList(ctx, 'RECOMMENDED ACTIONS', recommendedActions(cve, sentences), border)

  const srcLines = sourcesForCve(cve).map(s => `${s.name}: ${s.url}`)
  drawSection(ctx, 'SOURCES', srcLines.join('\n'), border)
}

export async function enrichCveForPdf(cve) {
  const id = cve?.cve_id
  if (!id) return cve

  let full = cve
  if (!cve.techniques?.length && !cve.description) {
    try {
      full = await fetchCVE(id)
    } catch {
      full = cve
    }
  } else if (!cve.techniques?.length) {
    try {
      const fetched = await fetchCVE(id)
      full = { ...cve, ...fetched }
    } catch {
      full = cve
    }
  }

  let sentences = null
  try {
    sentences = await fetchCVESentences(id)
  } catch {
    sentences = null
  }

  let correlation = null
  let detection = null
  try {
    correlation = await fetchCVECorrelation(id)
  } catch {
    correlation = null
  }
  try {
    const product = full.affected_products?.[0]?.split(':')?.[1] || ''
    detection = await fetchCVEDetection(id, product)
  } catch {
    detection = null
  }

  return { ...full, sentences: sentences || {}, correlation: correlation || {}, detection: detection || null }
}

export async function downloadSingleCvePdf(cve, options = {}) {
  const { jsPDF } = await loadPdfLibs()
  const enriched = await enrichCveForPdf(cve)
  const summaryData = await loadPdfExecutiveSummary({
    cves: [enriched],
    investigationDuration: 1,
  })
  const meta = buildMeta({
    ...options,
    aiFooterNote: summaryData ? aiFooterNoteForSource(summaryData.source) : null,
  })
  const sparklineDataUrl = await captureSparkline(options.sparklineElement)
  const executiveSummaryText = summaryData
    ? formatExecutiveSummaryBody(summaryData)
    : null

  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const ctx = { doc, y: CONTENT_TOP, pageNum: 1 }
  renderSingleCvePages(doc, ctx, enriched, meta, sparklineDataUrl, { executiveSummaryText })
  applyFootersAndStripes(doc, meta)
  doc.save(`${enriched.cve_id}-briefr-report.pdf`)
}

export async function downloadBulkCvePdf(cves, options = {}) {
  const { jsPDF } = await loadPdfLibs()
  const enrichedList = await Promise.all(cves.map(c => enrichCveForPdf(c)))
  const summaryData = await loadPdfExecutiveSummary({
    cves: enrichedList,
    investigationDuration: 1,
  })
  const meta = buildMeta({
    ...options,
    aiFooterNote: summaryData ? aiFooterNoteForSource(summaryData.source) : null,
  })

  const critical = enrichedList.filter(c => (c.severity || '').toUpperCase() === 'CRITICAL').length
  const kev = enrichedList.filter(c => c.is_kev).length
  const immediate = enrichedList
    .filter(c => c.is_kev || (c.severity || '').toUpperCase() === 'CRITICAL')
    .map(c => c.cve_id)

  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const ctx = { doc, y: CONTENT_TOP, pageNum: 1 }

  ctx.y = drawPageHeader(doc, meta, null, false)
  doc.setFont(FONT_BODY, 'normal')
  doc.setFontSize(7)
  doc.setTextColor(100, 100, 100)
  doc.text(
    'Aggregated from public sources (NVD, CISA KEV, EPSS, and related OSINT).',
    MARGIN,
    ctx.y,
  )
  ctx.y += 8

  const bulkSummaryBody = summaryData
    ? formatExecutiveSummaryBody(summaryData)
    : [
        `Total CVEs: ${enrichedList.length}`,
        `Critical: ${critical}`,
        `CISA KEV: ${kev}`,
        immediate.length
          ? `Immediate action:\n${immediate.map(id => `• ${id}`).join('\n')}`
          : 'Immediate action: Review selected CVEs by severity.',
      ].join('\n\n')

  drawSection(
    ctx,
    'BULK CVE REPORT — EXECUTIVE SUMMARY',
    bulkSummaryBody,
    [232, 85, 51],
  )

  enrichedList.forEach(cve => {
    renderSingleCvePages(doc, ctx, cve, meta, null, { newPage: true })
  })

  applyFootersAndStripes(doc, meta)
  const stamp = new Date().toISOString().slice(0, 10)
  doc.save(`briefr-bulk-report-${stamp}.pdf`)
}

function buildMeta(options) {
  const now = new Date()
  const dateLine = now.toLocaleString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
  return {
    timestamp: getReportTimestamp(),
    dateLine,
    analystName: (options.analystName || '').trim(),
    aiFooterNote: options.aiFooterNote || null,
  }
}
