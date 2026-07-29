/**
 * Normalize text before jsPDF layout to avoid odd spacing, clipping, and markdown artifacts.
 */
export function sanitizePdfText(text) {
  return String(text ?? '')
    .replace(/\r\n/g, '\n')
    .replace(/[\u00a0\u2000-\u200b\u202f\u205f\u3000]/g, ' ')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[^\S\n]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function pdfContentWidth(pageW, margin, innerPad = 10) {
  return pageW - margin * 2 - innerPad
}
