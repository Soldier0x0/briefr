/**
 * Returns true when the event target (or focused element) is a typing surface
 * where document-level navigation shortcuts must not fire (E6-4 / UI-10).
 */
export function isEditableTarget(node) {
  if (!node || typeof node !== 'object') return false
  const el = node instanceof Element ? node : null
  if (!el) return false

  const field = el.closest('input, textarea, select, [data-keyboard-suspend]')
  if (field) {
    if (field instanceof HTMLInputElement) {
      const type = (field.type || 'text').toLowerCase()
      if (type === 'button' || type === 'submit' || type === 'reset' || type === 'checkbox') {
        return false
      }
    }
    return true
  }

  const editable = el.closest('[contenteditable]')
  if (editable && editable.isContentEditable) return true

  const roleEl = el.closest('[role="textbox"], [role="combobox"], [role="searchbox"]')
  if (roleEl) return true

  return false
}

export function shouldIgnoreGlobalShortcut(event) {
  if (!event) return true
  if (event.isComposing) return true
  if (isEditableTarget(event.target)) return true
  if (typeof document !== 'undefined' && isEditableTarget(document.activeElement)) return true
  return false
}
