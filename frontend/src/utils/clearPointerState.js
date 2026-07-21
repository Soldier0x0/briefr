export function clearStalePointerState() {
  if (typeof document === 'undefined') return false

  const activeElement = document.activeElement
  if (!activeElement || typeof activeElement.closest !== 'function') return false

  const hiddenAncestor = activeElement.closest('[hidden]')
  if (!hiddenAncestor || typeof activeElement.blur !== 'function') return false

  activeElement.blur()
  return true
}
