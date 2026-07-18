/**
 * Decide whether an external `filters.stack` update should overwrite the
 * in-progress STACK input value.
 *
 * Debounce paths often `trim()` before committing. Replacing local "nginx "
 * with "nginx" resets the caret — the spacebar cursor-jump bug.
 */
export function nextLocalStack(prevLocal, externalStack) {
  const next = externalStack || ''
  if ((prevLocal || '').trim() === next.trim()) return prevLocal || ''
  return next
}
