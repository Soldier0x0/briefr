/** If clicking the active value, clear to `cleared`; else set `next`. */
export function toggleChipSelection(current, next, cleared = null) {
  return current === next ? cleared : next
}
