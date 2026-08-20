import { computeFitView, DEFAULT_VIEW, zoomAtCursor } from './architectureGraphView.js'

const ZOOM_LERP_MS = 120
const FLY_MS = 280
const INERTIA_FRICTION = 0.92
const INERTIA_STOP = 0.5

function easeOutCubic(t) {
  return 1 - ((1 - t) ** 3)
}

function cloneView(view) {
  return { x: view.x, y: view.y, scale: view.scale }
}

function lerpView(from, to, t) {
  return {
    x: from.x + (to.x - from.x) * t,
    y: from.y + (to.y - from.y) * t,
    scale: from.scale + (to.scale - from.scale) * t,
  }
}

export function createCameraController(initialView = DEFAULT_VIEW, { reducedMotion = false } = {}) {
  let display = cloneView(initialView)
  let target = cloneView(initialView)
  let flyFrom = cloneView(initialView)
  let flyTo = null
  let flyElapsed = 0
  let flyDuration = FLY_MS
  let zoomLerpMs = 0
  let panVx = 0
  let panVy = 0

  function cancelMotion() {
    flyTo = null
    panVx = 0
    panVy = 0
    zoomLerpMs = 0
  }

  return {
    getDisplayView() {
      return cloneView(display)
    },
    getTargetView() {
      return cloneView(target)
    },
    isAnimating() {
      return Boolean(flyTo) || panVx !== 0 || panVy !== 0 || zoomLerpMs > 0
    },
    setTargetView(next, { immediate = false } = {}) {
      cancelMotion()
      target = cloneView(next)
      if (reducedMotion || immediate) {
        display = cloneView(target)
        return
      }
      zoomLerpMs = ZOOM_LERP_MS
    },
    zoomAtCursor(cursorX, cursorY, factor) {
      cancelMotion()
      target = zoomAtCursor(target, cursorX, cursorY, factor)
      if (reducedMotion) {
        display = cloneView(target)
        return display
      }
      zoomLerpMs = ZOOM_LERP_MS
      return cloneView(target)
    },
    flyToView(next, { durationMs = FLY_MS } = {}) {
      cancelMotion()
      target = cloneView(next)
      if (reducedMotion) {
        display = cloneView(target)
        return
      }
      flyFrom = cloneView(display)
      flyTo = cloneView(target)
      flyElapsed = 0
      flyDuration = durationMs
    },
    flyToBounds(bounds, viewportW, viewportH) {
      this.flyToView(computeFitView(bounds, viewportW, viewportH))
    },
    syncDisplayToTarget() {
      cancelMotion()
      display = cloneView(target)
      return cloneView(display)
    },
    nudgePan(dx, dy) {
      cancelMotion()
      target = { ...target, x: target.x + dx, y: target.y + dy }
      display = { ...display, x: display.x + dx, y: display.y + dy }
    },
    setPanOrigin(origin) {
      cancelMotion()
      target = cloneView(origin)
      display = cloneView(origin)
    },
    applyPanDelta(origin, dx, dy) {
      panVx = 0
      panVy = 0
      flyTo = null
      zoomLerpMs = 0
      target = { ...origin, x: origin.x + dx, y: origin.y + dy }
      display = cloneView(target)
    },
    nudgePanVelocity(vx, vy) {
      if (reducedMotion) return
      panVx = vx
      panVy = vy
    },
    tick(dtMs) {
      if (reducedMotion) {
        display = cloneView(target)
        return cloneView(display)
      }
      if (flyTo) {
        flyElapsed += dtMs
        const t = Math.min(1, flyElapsed / flyDuration)
        display = lerpView(flyFrom, flyTo, easeOutCubic(t))
        if (t >= 1) {
          display = cloneView(flyTo)
          target = cloneView(flyTo)
          flyTo = null
        }
        return cloneView(display)
      }
      if (zoomLerpMs > 0) {
        const t = Math.min(1, dtMs / zoomLerpMs)
        display = lerpView(display, target, t)
        zoomLerpMs = Math.max(0, zoomLerpMs - dtMs)
        if (zoomLerpMs === 0) display = cloneView(target)
        return cloneView(display)
      }
      if (panVx !== 0 || panVy !== 0) {
        target = { ...target, x: target.x + panVx, y: target.y + panVy }
        display = cloneView(target)
        panVx *= INERTIA_FRICTION
        panVy *= INERTIA_FRICTION
        if (Math.hypot(panVx, panVy) < INERTIA_STOP) {
          panVx = 0
          panVy = 0
        }
      }
      return cloneView(display)
    },
  }
}
