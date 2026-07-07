/** Fired when admin config save or manual restart triggers backend reload. */

export const BACKEND_RESTART_EVENT = 'briefr-backend-restarting'

export function notifyBackendRestarting() {
  try {
    window.dispatchEvent(new CustomEvent(BACKEND_RESTART_EVENT))
  } catch { /* non-browser */ }
}
