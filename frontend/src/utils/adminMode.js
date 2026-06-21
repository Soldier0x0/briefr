const ADMIN_MODES = ['analyst', 'operator']

export function getAdminMode() {
  try {
    const v = localStorage.getItem('briefr-admin-mode')
    return ADMIN_MODES.includes(v) ? v : 'analyst'
  } catch {
    return 'analyst'
  }
}

export function setAdminMode(mode) {
  try {
    if (ADMIN_MODES.includes(mode)) localStorage.setItem('briefr-admin-mode', mode)
  } catch { /* localStorage unavailable, mode just won't persist */ }
}

export const ADMIN_MODE_OPTIONS = ADMIN_MODES
