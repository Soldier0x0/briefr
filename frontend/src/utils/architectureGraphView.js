import { NODE_H, NODE_W } from './architectureGraphLayout.js'

/** Wheel-zoom floor — users can still zoom out further via Fit. */
export const MIN_SCALE = 0.15
export const MAX_SCALE = 4
/** Fit may go slightly lower so a tall multi-column graph still frames. */
export const FIT_MIN_SCALE = 0.08
export const DEFAULT_VIEW = { x: 40, y: 20, scale: 1 }

export function clampScale(scale, min = MIN_SCALE, max = MAX_SCALE) {
  return Math.min(max, Math.max(min, scale))
}

/**
 * Wheel zoom anchored at a screen-space cursor so the graph point under the
 * cursor stays fixed while scale changes.
 */
export function zoomAtCursor(view, cursorX, cursorY, scaleFactor) {
  const nextScale = clampScale(view.scale * scaleFactor)
  if (nextScale === view.scale) return view
  const graphX = (cursorX - view.x) / view.scale
  const graphY = (cursorY - view.y) / view.scale
  return {
    x: cursorX - graphX * nextScale,
    y: cursorY - graphY * nextScale,
    scale: nextScale,
  }
}

export function computeGraphBounds(positioned, nodeW = NODE_W, nodeH = NODE_H, padding = 24) {
  if (!positioned?.length) {
    return { minX: 0, minY: 0, maxX: 400, maxY: 300 }
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of positioned) {
    minX = Math.min(minX, node.x)
    minY = Math.min(minY, node.y)
    maxX = Math.max(maxX, node.x + nodeW)
    maxY = Math.max(maxY, node.y + nodeH)
  }
  return {
    minX: minX - padding,
    minY: minY - padding,
    maxX: maxX + padding,
    maxY: maxY + padding,
  }
}

/** Bounding box for force-layout dots (cx, cy) rather than architecture rects. */
export function computePointCloudBounds(positions, radius = 12, padding = 48) {
  if (!positions?.length) {
    return { minX: 0, minY: 0, maxX: 400, maxY: 300 }
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of positions) {
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) continue
    minX = Math.min(minX, node.x - radius)
    minY = Math.min(minY, node.y - radius)
    maxX = Math.max(maxX, node.x + radius)
    maxY = Math.max(maxY, node.y + radius)
  }
  if (!Number.isFinite(minX)) {
    return { minX: 0, minY: 0, maxX: 400, maxY: 300 }
  }
  return {
    minX: minX - padding,
    minY: minY - padding,
    maxX: maxX + padding,
    maxY: maxY + padding,
  }
}

/**
 * Fit all laid-out nodes inside the viewport with uniform scale.
 * Does not use wheel MIN_SCALE — tall graphs must be allowed to shrink.
 */
export function computeFitView(bounds, viewportWidth, viewportHeight) {
  if (viewportWidth <= 0 || viewportHeight <= 0) return { ...DEFAULT_VIEW }
  const contentW = bounds.maxX - bounds.minX
  const contentH = bounds.maxY - bounds.minY
  if (contentW <= 0 || contentH <= 0) return { ...DEFAULT_VIEW }
  const raw = Math.min(viewportWidth / contentW, viewportHeight / contentH)
  const scale = clampScale(raw, FIT_MIN_SCALE, MAX_SCALE)
  const cx = (bounds.minX + bounds.maxX) / 2
  const cy = (bounds.minY + bounds.maxY) / 2
  return {
    x: viewportWidth / 2 - cx * scale,
    y: viewportHeight / 2 - cy * scale,
    scale,
  }
}

/** Truncate node labels so SVG text stays inside the node rect. */
export function truncateNodeLabel(label, maxChars = 26) {
  const text = String(label || '')
  if (text.length <= maxChars) return text
  return `${text.slice(0, Math.max(1, maxChars - 1))}…`
}
