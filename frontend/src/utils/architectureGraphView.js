import { NODE_H, NODE_W } from './architectureGraphLayout.js'

export const MIN_SCALE = 0.4
export const MAX_SCALE = 4
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

/**
 * Fit all laid-out nodes inside the viewport with uniform scale.
 */
export function computeFitView(bounds, viewportWidth, viewportHeight) {
  if (viewportWidth <= 0 || viewportHeight <= 0) return { ...DEFAULT_VIEW }
  const contentW = bounds.maxX - bounds.minX
  const contentH = bounds.maxY - bounds.minY
  if (contentW <= 0 || contentH <= 0) return { ...DEFAULT_VIEW }
  const scale = clampScale(Math.min(viewportWidth / contentW, viewportHeight / contentH))
  const cx = (bounds.minX + bounds.maxX) / 2
  const cy = (bounds.minY + bounds.maxY) / 2
  return {
    x: viewportWidth / 2 - cx * scale,
    y: viewportHeight / 2 - cy * scale,
    scale,
  }
}
