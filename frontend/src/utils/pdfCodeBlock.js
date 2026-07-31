/**
 * Shared PDF code-block renderer — Geist-inspired panel with header strip,
 * light fill, and generous margins for copy-paste from exported PDFs.
 * Paginates long YAML across pages.
 */
import { FONT_MONO } from './exportCommon.js'

const CODE_PAD_X = 7
const CODE_PAD_TOP = 14
const CODE_HEADER_H = 8
const CODE_LINE_H = 4.35
const CODE_BOTTOM_PAD = 8
const CODE_BG = [248, 247, 244]
const CODE_BORDER = [220, 218, 212]

function drawCodeHeader(doc, title, x, y0, accentRgb, attribution, innerW) {
  if (accentRgb) {
    doc.setFillColor(...accentRgb)
    doc.rect(x, y0, 2.5, CODE_HEADER_H + CODE_PAD_TOP + (attribution ? 5 : 0), 'F')
  }
  doc.setFont(FONT_MONO, 'bold')
  doc.setFontSize(7)
  doc.setTextColor(100, 98, 92)
  doc.text(String(title).toUpperCase(), x + CODE_PAD_X, y0 + 5.5)
  if (attribution) {
    doc.setFont(FONT_MONO, 'normal')
    doc.setFontSize(6.5)
    doc.setTextColor(120, 118, 112)
    const attrLines = doc.splitTextToSize(String(attribution), innerW)
    doc.text(attrLines.slice(0, 2), x + CODE_PAD_X, y0 + 9.5)
  }
}

function drawCodeLine(doc, line, x, y) {
  doc.setFont(FONT_MONO, 'normal')
  doc.setFontSize(7.75)
  doc.setTextColor(40, 40, 40)
  doc.text(line, x + CODE_PAD_X, y)
}

export function drawPdfCodeBlock(ctx, title, code, accentRgb, layout, attribution = '') {
  if (!code) return

  const { doc, margin, pageW, ensureSpace, splitLines } = layout
  const innerW = pageW - margin * 2 - CODE_PAD_X * 2
  const lines = splitLines(doc, code, innerW)
  if (!lines.length) return

  const x = margin
  const w = pageW - margin * 2
  const attributionPad = attribution ? 5 : 0
  let lineIndex = 0
  let firstChunk = true

  while (lineIndex < lines.length) {
    const available = layout.contentBottom != null
      ? layout.contentBottom - ctx.y - CODE_HEADER_H - CODE_PAD_TOP - attributionPad - CODE_BOTTOM_PAD - 6
      : 220
    const maxLines = Math.max(1, Math.floor(available / CODE_LINE_H))
    const chunk = lines.slice(lineIndex, lineIndex + maxLines)
    const bodyH = chunk.length * CODE_LINE_H
    const blockH = (firstChunk ? CODE_HEADER_H + CODE_PAD_TOP + attributionPad : CODE_PAD_TOP)
      + bodyH + CODE_BOTTOM_PAD + 4

    ensureSpace(ctx, blockH + 4)

    const y0 = ctx.y + 2
    doc.setDrawColor(...CODE_BORDER)
    doc.setFillColor(...CODE_BG)
    doc.setLineWidth(0.35)
    doc.roundedRect(x, y0, w, blockH, 2, 2, 'FD')

    if (firstChunk) {
      drawCodeHeader(doc, title, x, y0, accentRgb, attribution, innerW)
    }

    let y = y0 + (firstChunk ? CODE_PAD_TOP + CODE_HEADER_H + attributionPad : CODE_PAD_TOP)
    chunk.forEach((line) => {
      drawCodeLine(doc, line, x, y)
      y += CODE_LINE_H
    })

    ctx.y = y0 + blockH + 4
    lineIndex += chunk.length
    firstChunk = false
  }
}

export function hexAccent(accentHex, hexToRgbFn) {
  return hexToRgbFn(accentHex)
}
