import { prefersReducedMotion } from './motion.js'
import { readChartTheme } from './chartTheme.js'

export function chartAnimationDuration() {
  return prefersReducedMotion() ? 0 : 160
}

export function rechartsMargin({ left = 4, right = 8, top = 4, bottom = 4 } = {}) {
  return { top, right, bottom, left }
}

/** Pixel width for a Recharts category Y-axis from label strings (no truncation). */
export function categoryAxisWidth(labels, { min = 120, max = 300, charPx = 7.2, pad = 20 } = {}) {
  const longest = Math.max(0, ...(labels || []).map((label) => String(label || '').length))
  if (!longest) return min
  return Math.min(max, Math.max(min, Math.ceil(longest * charPx) + pad))
}

/** Height for horizontal bar charts — one row per category plus axis padding. */
export function verticalBarChartHeight(rowCount, { min = 200, rowPx = 28, pad = 48 } = {}) {
  const rows = Math.max(0, Number(rowCount) || 0)
  if (!rows) return min
  return Math.max(min, rows * rowPx + pad)
}

export function axisTickStyle(theme) {
  return {
    fill: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.mono,
  }
}

export function axisLabelStyle(theme) {
  return {
    fill: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.mono,
  }
}

export function tooltipContentStyle(theme) {
  return {
    backgroundColor: theme.panel,
    border: `1px solid ${theme.borderStrong || theme.grid}`,
    borderRadius: 0,
    fontFamily: theme.mono,
    fontSize: 13,
    color: theme.text,
    boxShadow: 'none',
  }
}

export function tooltipItemStyle(theme) {
  return {
    color: theme.text,
    fontFamily: theme.mono,
    fontSize: 13,
    padding: 0,
  }
}

export function tooltipCursorStyle(theme) {
  return {
    fill: theme.surfaceSelected || theme.redDim,
    stroke: theme.grid,
    strokeWidth: 1,
  }
}

export function barActiveProps(theme) {
  return {
    fill: theme.accent,
    stroke: theme.accent,
    strokeWidth: 1,
    opacity: 0.88,
  }
}

export function tooltipLabelStyle(theme) {
  return {
    color: theme.text,
    fontFamily: theme.mono,
    fontSize: 13,
    marginBottom: 4,
  }
}

export function legendStyle(theme) {
  return {
    fontSize: 12,
    fontFamily: theme.mono,
    color: theme.textSecondary,
  }
}

export function getRechartsTheme() {
  return readChartTheme()
}
