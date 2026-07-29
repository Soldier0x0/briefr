/**
 * Shared PDF code-block renderer — Geist-inspired panel with header strip,
 * light fill, and generous margins for copy-paste from exported PDFs.
 */
import { FONT_MONO, hexToRgb } from './exportCommon.js'

const CODE_PAD_X = 7
const CODE_PAD_TOP = 14
const CODE_HEADER_H = 8
const CODE_LINE_H = 4.35
const CODE_BOTTOM_PAD = 8
const CODE_BG = [248, 247, 244]
const CODE_BORDER = [220, 218, 212]

export function drawPdfCodeBlock(ctx, title, code, accentRgb, layout) {
  if (!code) return

  const { doc, margin, pageW, ensureSpace, splitLines } = layout
  const innerW = pageW - margin * 2 - CODE_PAD_X * 2
  const lines = splitLines(doc, code, innerW)
  const bodyH = lines.length * CODE_LINE_H
  const blockH = CODE_HEADER_H + CODE_PAD_TOP + bodyH + CODE_BOTTOM_PAD + 4

  ensureSpace(ctx, blockH + 4)

  const x = margin
  const y0 = ctx.y + 2
  const w = pageW - margin * 2

  doc.setDrawColor(...CODE_BORDER)
  doc.setFillColor(...CODE_BG)
  doc.setLineWidth(0.35)
  doc.roundedRect(x, y0, w, blockH, 2, 2, 'FD')

  if (accentRgb) {
    doc.setFillColor(...accentRgb)
    doc.rect(x, y0, 2.5, blockH, 'F')
  }

  doc.setFont(FONT_MONO, 'bold')
  doc.setFontSize(7)
  doc.setTextColor(100, 98, 92)
  doc.text(String(title).toUpperCase(), x + CODE_PAD_X, y0 + 5.5)

  doc.setFont(FONT_MONO, 'normal')
  doc.setFontSize(7.75)
  doc.setTextColor(40, 40, 40)
  let y = y0 + CODE_PAD_TOP + CODE_HEADER_H
  lines.forEach((line) => {
    doc.text(line, x + CODE_PAD_X, y)
    y += CODE_LINE_H
  })

  ctx.y = y0 + blockH + 4
}

export function hexAccent(accentHex, hexToRgbFn) {
  return hexToRgbFn(accentHex)
}
