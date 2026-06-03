import { fetchAiSummary } from '../api.js'

/**
 * Load executive summary for PDF export only (called from download handlers).
 */
export async function loadPdfExecutiveSummary({
  cves = [],
  iocs = [],
  actors = [],
  investigationDuration = 1,
}) {
  try {
    return await fetchAiSummary({
      cves,
      iocs,
      actors,
      investigationDuration,
    })
  } catch {
    return null
  }
}

export function isAiAssistedSource(source) {
  return source === 'groq' || source === 'anthropic'
}

export function aiFooterNoteForSource(source) {
  if (source === 'groq') {
    return 'Executive summary AI-assisted via Groq / Llama 3.3'
  }
  if (source === 'anthropic') {
    return 'Executive summary AI-assisted via Anthropic Claude Haiku'
  }
  return null
}

export function formatExecutiveSummaryBody(summaryData) {
  if (!summaryData?.executive_summary) {
    return 'Executive summary unavailable.'
  }
  const parts = [summaryData.executive_summary]
  const findings = summaryData.key_findings
  if (Array.isArray(findings) && findings.length) {
    parts.push('\n\nKey findings:\n' + findings.map(f => `• ${f}`).join('\n'))
  }
  return parts.join('')
}
