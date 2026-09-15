/** Feature gates for INVESTIGATE graph rendering paths. */

export function canvasEdgesEnabled() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_INVESTIGATE_CANVAS_EDGES === '1') {
    return true
  }
  if (typeof globalThis !== 'undefined' && globalThis.__BRIEFR_INVESTIGATE_CANVAS_EDGES__ === true) {
    return true
  }
  return false
}
